"""eidoblend.harness.render_common: what eidoverse/render_common.mjs (the render_*.mjs tools' shared RenderKit) means
in Blender.

    load_config(path)                      -> the checked scene.json (harness.config.load_config)
    get_camera_at_time(t, path, pos, tgt)  -> {'position', 'target'}: a camera path, smoothstepped per segment
    key_camera_path(cam, path, scene, ...) -> the same path KEYED on a Blender camera, every frame (three coords in)
    setup_scene(config, scene=None)        -> background, lights and camera from a config's "background" / "lights" /
                                              "camera" keys (the engine's default four-light rig when none)
    alpha_composite(frame, ui, dest=None)  -> a premultiplied RGBA layer over a frame (numpy, top-down rows)
    log_progress(tool, i, total, t)        -> the engine's progress line, every 15 frames and the last
    ffmpeg_rate_control(scene)             -> RENDER_CODEC / RENDER_CQ / RENDER_BITRATE on Blender's H.264 writer

What has no meaning here, and why: setupRenderer (a WebGPU device, a fake canvas context and browser shims: Blender is
the renderer), startFfmpegPipe / readbackFrame / drainReadback (EEVEE writes the video itself; its env controls are
ffmpeg_rate_control), rasterizeUI (Satori's HTML+CSS -> SVG -> RGBA: the media family's raster.Canvas and this
package's html_mesh draw UI here), loadAssets (the runner's ctx.assets, checked paths instead of base64), shutdown
(nothing to release).
"""

from __future__ import annotations

import os

import numpy as np

from .config import load_config  # noqa: F401  (render_common.mjs loadConfig)


def get_camera_at_time(t, camera_path, default_pos, default_target):
    """render_common.mjs getCameraAtTime: the segment holding t, smoothstep-eased between its two keys. Keys are
    {'time', 'position', 'target'} (missing values fall back to the defaults). Coordinates pass through as given."""
    if not camera_path:
        return {'position': default_pos, 'target': default_target}
    if len(camera_path) == 1:
        k = camera_path[0]
        return {'position': k.get('position') or default_pos, 'target': k.get('target') or default_target}
    i = 0
    while i < len(camera_path) - 1:
        if camera_path[i + 1]['time'] > t:
            break
        i += 1
    a = camera_path[i]
    b = camera_path[min(i + 1, len(camera_path) - 1)]
    if a is b:
        return {'position': a.get('position') or default_pos, 'target': a.get('target') or default_target}
    span = (b['time'] - a['time']) or 1
    u = max(0.0, min(1.0, (t - a['time']) / span))
    s = u * u * (3 - 2 * u)

    def lerp(p, q):
        return [p[0] + (q[0] - p[0]) * s, p[1] + (q[1] - p[1]) * s, p[2] + (q[2] - p[2]) * s]
    return {'position': lerp(a.get('position') or default_pos, b.get('position') or default_pos),
            'target': lerp(a.get('target') or default_target, b.get('target') or default_target)}


def key_camera_path(cam, camera_path, scene=None, default_pos=(0, 1.2, 3.0), default_target=(0, 0, 0),
                    three=True, frame_start=None):
    """Key a camera along get_camera_at_time on every frame of the scene (LINEAR keys, so the smoothstep is the
    motion): location at the path's position, aimed at its target. Path coordinates are three's (Y up) unless
    three=False. Returns the number of frames keyed."""
    import bpy
    from mathutils import Vector
    from .. import common
    scene = scene or bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    f0 = scene.frame_start if frame_start is None else frame_start
    conv = (lambda p: Vector(common.from_three(*p))) if three else (lambda p: Vector(p))
    n = 0
    for f in range(scene.frame_start, scene.frame_end + 1):
        k = get_camera_at_time((f - f0) / fps, camera_path, list(default_pos), list(default_target))
        pos, tgt = conv(k['position']), conv(k['target'])
        cam.location = pos
        cam.rotation_mode = 'XYZ'
        cam.rotation_euler = (tgt - pos).to_track_quat('-Z', 'Y').to_euler()
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_euler', frame=f)
        n += 1
    ad = cam.animation_data
    if ad and ad.action:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        for fc in (cb.fcurves if cb else ()):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    return n


def _hex(c):
    """'#rrggbb', a CSS name Pillow knows, or (r, g, b) 0..1 -> linear (r, g, b), as THREE.Color's sRGB input."""
    if isinstance(c, (list, tuple)):
        return tuple(float(v) for v in c[:3])
    from PIL import ImageColor
    r, g, b = ImageColor.getrgb(str(c))[:3]

    def lin(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return lin(r), lin(g), lin(b)


DEFAULT_LIGHTS = (                                   # setupScene's rig when the config names none (three coords)
    {'type': 'ambient', 'color': '#404040', 'intensity': 1.0},
    {'type': 'directional', 'color': '#ffffff', 'intensity': 2.5, 'position': [3, 5, 4]},
    {'type': 'point', 'color': '#8888ff', 'intensity': 1.5, 'position': [-2, 2, 1]},
    {'type': 'point', 'color': '#ff2d95', 'intensity': 1.0, 'position': [0, 2, -3]},
)
POINT_WATTS = 4 * 3.141592653589793 / 0.683          # three point candela -> Blender watts (683 lm/W, 4 pi sr)


def setup_scene(config: dict, scene=None):
    """render_common.mjs setupScene: the background, lights and camera of a config.

    background: 'transparent' (default) | a colour | [r, g, b]  -> film transparent or a world of that colour that
        the camera sees (it lights nothing: three's scene.background was never a light)
    lights: [{type: 'directional'|'point'|'ambient'|'spot', color, intensity, position, target, distance}] in three
        coordinates; none -> the engine's default rig (ambient 0x404040, key 2.5 from (3, 5, 4), a blue fill point
        and a pink rim point). Directional -> a sun (intensity as irradiance), point/spot -> watts from candela,
        ambient -> the world's light (the camera never sees it).
    camera: {fov (vertical degrees, default 45), position (default [0, 1.2, 3]), target (default origin)}
    Returns {'scene', 'camera', 'lights', 'default_pos', 'default_target'} (Blender coordinates)."""
    import bpy
    from mathutils import Vector
    from .. import common
    scene = scene or bpy.context.scene
    bg = config.get('background')
    ambient = [d for d in (config.get('lights') or DEFAULT_LIGHTS) if d.get('type') == 'ambient']
    w = bpy.data.worlds.new('setup_scene')
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    cam_bg = nt.nodes.new('ShaderNodeBackground')
    if bg is None or bg == 'transparent':
        scene.render.film_transparent = True
        cam_bg.inputs['Strength'].default_value = 0.0
    else:
        scene.render.film_transparent = False
        cam_bg.inputs['Color'].default_value = (*_hex(bg), 1.0)
    light_bg = nt.nodes.new('ShaderNodeBackground')
    if ambient:
        c = np.zeros(3)
        for d in ambient:
            c += np.array(_hex(d.get('color', '#ffffff'))) * float(d.get('intensity', 1.0))
        light_bg.inputs['Color'].default_value = (*(c / max(1e-9, c.max())), 1.0)
        light_bg.inputs['Strength'].default_value = float(c.max()) / 3.141592653589793
    else:
        light_bg.inputs['Strength'].default_value = 0.0
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(light_bg.outputs[0], mix.inputs[1])
    nt.links.new(cam_bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    scene.world = w
    made = []
    for i, d in enumerate(config.get('lights') or DEFAULT_LIGHTS):
        kind = d.get('type')
        if kind == 'ambient':
            continue
        col, inten = _hex(d.get('color', '#ffffff')), float(d.get('intensity', 1.0))
        if kind == 'directional':
            ld = bpy.data.lights.new(f'light_{i}_sun', 'SUN')
            ld.energy = inten
        elif kind in ('point', 'spot'):
            ld = bpy.data.lights.new(f'light_{i}_{kind}', 'POINT' if kind == 'point' else 'SPOT')
            ld.energy = inten * POINT_WATTS
            ld.shadow_soft_size = 0.05
            if d.get('distance'):
                ld.use_custom_distance = True
                ld.cutoff_distance = float(d['distance'])
        else:
            continue
        ld.color = col
        ob = bpy.data.objects.new(ld.name, ld)
        pos = Vector(common.from_three(*(d.get('position') or (0, 1, 0))))
        ob.location = pos
        tgt = Vector(common.from_three(*(d.get('target') or (0, 0, 0))))
        if kind != 'point':
            ob.rotation_euler = (tgt - pos).to_track_quat('-Z', 'Y').to_euler()
        scene.collection.objects.link(ob)
        made.append(ob)
    c = config.get('camera') or {}
    cd = bpy.data.cameras.new('setup_scene')
    cd.sensor_fit = 'VERTICAL'
    import math
    cd.angle_y = math.radians(float(c.get('fov') or 45))
    cd.clip_start, cd.clip_end = 0.01, 1000.0
    cam = bpy.data.objects.new('camera', cd)
    pos = Vector(common.from_three(*(c.get('position') or (0, 1.2, 3.0))))
    tgt = Vector(common.from_three(*(c.get('target') or (0, 0, 0))))
    cam.location = pos
    cam.rotation_euler = (tgt - pos).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam
    return {'scene': scene, 'camera': cam, 'lights': made, 'default_pos': tuple(pos), 'default_target': tuple(tgt)}


def alpha_composite(scene_frame, ui_pixels, dest=None):
    """render_common.mjs alphaComposite: a premultiplied RGBA layer (resvg's convention) over an RGBA frame, both
    uint8 (H, W, 4) or flat, top-down. Writes into dest (or the frame itself) and returns it; alpha comes out 255
    wherever the layer covers. Integer truncation as the engine's `| 0`."""
    f = np.asarray(scene_frame)
    u = np.asarray(ui_pixels)
    out = f if dest is None else dest
    fs, us = f.reshape(-1, 4).astype(np.float64), u.reshape(-1, 4).astype(np.float64)
    o = out.reshape(-1, 4)
    a = us[:, 3]
    cov = a > 0
    inv = 1.0 - a[cov] / 255.0
    o[cov, :3] = np.floor(us[cov, :3] + fs[cov, :3] * inv[:, None]).astype(o.dtype)
    o[cov, 3] = 255
    if dest is not None:
        o[~cov] = f.reshape(-1, 4)[~cov]
    return out


def log_progress(tool, i, total, t):
    """render_common.mjs logProgress: '[tool] frame i+1/total at t=X.XXs' every 15 frames and on the last."""
    if i % 15 == 0 or i == total - 1:
        print(f'[{tool}] frame {i + 1}/{total} at t={t:.2f}s', flush=True)


CODECS = {'libx264': 'H264', 'h264': 'H264', 'h264_nvenc': 'H264', 'libx265': 'H265', 'hevc': 'H265',
          'h265': 'H265', 'hevc_nvenc': 'H265', 'libaom-av1': 'AV1', 'av1': 'AV1', 'libsvtav1': 'AV1',
          'prores': 'PRORES', 'ffv1': 'FFV1'}


def ffmpeg_rate_control(scene, env=None) -> list:
    """startFfmpegPipe's environment controls on Blender's own ffmpeg writer: RENDER_CODEC (a name ffmpeg knows,
    mapped to Blender's codec list; NVENC has no Blender writer, so h264_nvenc means H.264), RENDER_CQ (a CRF number:
    lower is better) and RENDER_BITRATE ('20M' / '8000k': a constant target). Returns what it set."""
    env = os.environ if env is None else env
    ff = scene.render.ffmpeg
    notes = []
    codec = env.get('RENDER_CODEC')
    if codec:
        c = CODECS.get(codec.lower())
        if c:
            ff.codec = c
            notes.append(f'codec {c} (RENDER_CODEC={codec})')
        else:
            notes.append(f'RENDER_CODEC={codec}: not a codec Blender writes; H.264 kept')
    cq, br = env.get('RENDER_CQ'), env.get('RENDER_BITRATE')
    if cq:
        ff.constant_rate_factor = 'CUSTOM'
        ff.custom_constant_rate_factor = int(cq)
        notes.append(f'CRF {int(cq)} (RENDER_CQ)')
    elif br:
        s = str(br).strip().lower()
        kbps = int(float(s[:-1]) * 1000) if s.endswith('m') else int(float(s[:-1])) if s.endswith('k') else \
            int(float(s) / 1000)
        ff.constant_rate_factor = 'NONE'
        ff.video_bitrate = kbps
        ff.maxrate = kbps
        notes.append(f'{kbps} kb/s (RENDER_BITRATE={br})')
    return notes
