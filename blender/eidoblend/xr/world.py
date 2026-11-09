"""eidoblend.xr.world: the scene's world as an equirectangular image an XR page draws as its sky and lights with.

glTF has no world. bake_world_equirect renders the world alone (Cycles, an equirectangular panorama from the origin,
in a throwaway scene that shares the world) into a Radiance .hdr: linear, unclipped, so the page uses the same file as
its background dome and as its image-based light (three's PMREM), at the radiance Blender lights with. A GPU job: run
it through the GPU slot.

    from eidoblend.xr import world as W
    W.bake_world_equirect(scene, 'work/<id>/vr/world.hdr', width=2048, frame=97)

Orientation: the image is in three.js's equirect convention, the one its background, PMREM and equirectUV() read
directly: for a three direction d, u = 0.5 + atan2(d.z, d.x) / 2 pi and v = 0.5 + asin(d.y) / pi. In Blender's axes
that is u = 0.5 + atan2(-y, x) / 2 pi, v = 0.5 + asin(z) / pi: half a turn from Blender's own Environment Texture,
which shows this image right with a Mapping node's Z rotation of 180 degrees. The panorama camera's rotation that
produces it, (90, 0, -90) degrees, was measured on a world coloured by its own direction (calib in the test notes):
(90, 0, +90) gives Blender's Environment Texture convention exactly, (90, 0, -90) three's.
"""
from __future__ import annotations

import math
import os

import bpy

from . import _bl


def equirect_direction(u, v):
    """The Blender world direction a pixel (u, v in 0..1, v up) of the baked image shows (three's convention)."""
    lon = (u - 0.5) * 2 * math.pi
    lat = (v - 0.5) * math.pi
    # three: d = (cos lon cos lat, sin lat, sin lon cos lat); Blender (x, y, z) = (d.x, -d.z, d.y)
    return (math.cos(lon) * math.cos(lat), -math.sin(lon) * math.cos(lat), math.sin(lat))


def bake_world_equirect(scene, path, width=2048, samples=32, frame=None, device='GPU', log=print,
                        camera_rotation=(math.pi / 2, 0.0, -math.pi / 2)):
    """Render scene.world alone to an equirectangular .hdr (width x width / 2). Returns {'path', 'seconds',
    'mean', 'max'}: the world's linear radiance averaged over the sphere (each pixel by its solid angle, cos latitude:
    an equirect's polar rows hold little of the sky) and its brightest pixel. device 'CPU' renders on the CPU (a tiny
    measurement needs no GPU slot)."""
    import time
    import numpy as np
    t0 = time.time()
    world = scene.world
    if world is None:
        raise ValueError('bake_world_equirect: the scene has no world')
    tmp = bpy.data.scenes.new('_xr_world_bake')
    try:
        tmp.world = world
        tmp.frame_start = scene.frame_start
        tmp.frame_end = scene.frame_end
        tmp.render.fps, tmp.render.fps_base = scene.render.fps, scene.render.fps_base
        tmp.frame_set(int(frame if frame is not None else scene.frame_current))
        cd = bpy.data.cameras.new('_xr_world_cam')
        cd.type = 'PANO'
        cd.panorama_type = 'EQUIRECTANGULAR'
        cam = bpy.data.objects.new('_xr_world_cam', cd)
        tmp.collection.objects.link(cam)
        cam.location = (0, 0, 0)
        cam.rotation_euler = camera_rotation
        tmp.camera = cam
        dev = _bl.cycles_gpu(tmp, log) if device == 'GPU' else 'CPU'
        if dev == 'CPU':
            tmp.cycles.device = 'CPU'
        tmp.render.engine = 'CYCLES'
        tmp.cycles.samples = int(samples)
        tmp.cycles.use_denoising = False
        tmp.render.resolution_x, tmp.render.resolution_y = int(width), int(width) // 2
        tmp.render.resolution_percentage = 100
        tmp.render.film_transparent = False
        tmp.view_settings.view_transform = 'Standard'
        tmp.view_settings.look = 'None'
        tmp.view_settings.exposure = 0.0
        tmp.render.image_settings.media_type = 'IMAGE'
        tmp.render.image_settings.file_format = 'HDR'
        tmp.render.image_settings.color_depth = '32'
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp.render.filepath = os.path.abspath(path)
        tmp.render.use_file_extension = False
        bpy.ops.render.render(write_still=True, scene=tmp.name)
        if not os.path.exists(path):
            raise RuntimeError(f'bake_world_equirect: the render wrote nothing at {path}')
        img = bpy.data.images.load(os.path.abspath(path), check_existing=False)
        a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
        img.pixels.foreach_get(a)
        h_, w_ = img.size[1], img.size[0]
        rgb = a.reshape(h_, w_, 4)[..., :3]
        lat = (np.arange(h_) + 0.5) / h_ * math.pi - math.pi / 2           # rows from the bottom (Blender's order)
        wt = np.cos(lat)[:, None, None]
        mean = (rgb * wt).sum((0, 1)) / (wt.sum() * w_)
        stats = {'mean': [round(float(x), 5) for x in mean], 'max': round(float(rgb.max()), 4)}
        bpy.data.images.remove(img)
    finally:
        for ob in list(tmp.collection.objects):
            d = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if d is not None and d.users == 0:
                bpy.data.cameras.remove(d)
        bpy.data.scenes.remove(tmp)
    out = {'path': os.path.abspath(path), 'seconds': round(time.time() - t0, 2), 'device': dev, **stats}
    if log:
        log(f'[xr.world] {world.name} -> {path} ({width} x {width // 2}, {out["seconds"]} s, mean {stats["mean"]})')
    return out
