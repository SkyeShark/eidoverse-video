"""The demo's volumetric clouds against the app's own march (clouds.js run on the CPU, three's
RaymarchingBox step for step, composited the way three blends it), one cloud from two places:
close up (2.2 box widths away, a little below) and from the ground at the plant (50 mm).

    bash run_blender.sh blender/tests/trees2/cloud_probe.py

Renders out/cloud_<view>_sky.png (the sky alone), cloud_<view>_blender.png and
cloud_<view>_app.png (the CPU march over the same sky), and checks: the volume carries both
grids ('density' and 'shade'); the cloud adds about what the app's adds over the sky (within
25 %), core and wisps; and the per-pixel difference stays small.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.trees import raw  # noqa: E402

W, H = 640, 360


def setup(view):
    S.reset()
    from seedthree.scene import terrain as T, atmosphere as A, tonemap
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    ee = sc.eevee
    ee.taa_render_samples = 16
    ee.use_volumetric_shadows = False
    ee.volumetric_tile_size = '2'
    ee.volumetric_samples = 128
    tonemap.aces_view(sc, 1.3)
    sc.world = T.world_sky('temperate', T.sun_direction(40, 32))
    T.sun_lamp(sc, 40, 32)
    clouds = A.build_clouds(count=8, altitude=85, spread=190)
    for i, c in enumerate(clouds):
        c.hide_render = i != 0
    c0 = clouds[0]
    cd = bpy.data.cameras.new('cam')
    cd.clip_start, cd.clip_end = 0.1, 2000
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    if view == 'close':
        cd.lens = 35
        cam.location = c0.location + Vector((0.0, -1.0, -0.15)).normalized() * (max(c0.scale) * 2.2)
    else:
        cd.lens = 50
        cam.location = Vector((0.0, 0.0, 2.0))
    cam.rotation_euler = (c0.location - cam.location).to_track_quat('-Z', 'Y').to_euler()
    # concentrate the froxel slices on the cloud
    ee.use_volume_custom_range = True
    dist = (c0.location - cam.location).length
    ee.volumetric_start = max(0.1, dist - max(c0.scale) * 1.2)
    ee.volumetric_end = dist + max(c0.scale) * 1.2
    bpy.context.view_layer.update()
    return sc, c0, cam


def save_png(sc, px, path):
    img = bpy.data.images.new('probe', W, H, float_buffer=True)
    img.pixels.foreach_set(np.concatenate([px[::-1], np.ones((H, W, 1), np.float32)], axis=2).ravel())
    s = sc.render.image_settings
    keep = (s.file_format, s.color_depth)
    s.file_format, s.color_depth = 'PNG', '8'
    img.save_render(path, scene=sc)
    s.file_format, s.color_depth = keep
    bpy.data.images.remove(img)


def render_linear(sc, path_png):
    exr = os.path.splitext(path_png)[0] + '.exr'
    s = sc.render.image_settings
    s.file_format, s.color_depth = 'OPEN_EXR', '32'
    sc.render.filepath = exr
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(exr)
    px = np.array(img.pixels[:], np.float32).reshape(H, W, 4)[::-1, :, :3].copy()
    bpy.data.images.remove(img)
    os.remove(exr)
    save_png(sc, px, path_png)
    return px


def app_march(sc, c0, cam, bg):
    """clouds.js: per step a = smoothstep(0.30 +- 0.16, tex(p + 0.5)) x 0.13, col = 3 (tex(p - 0.01)
    - tex(p + 0.01)) + (p.x + p.y) 0.25 + 0.2, front-to-back until alpha 0.95; out (rgb + tint) a +
    sky (1 - a). p in three's box frame (x, y up, z) = Blender's (X, Z, -Y)."""
    from seedthree.core.cloud_noise import cloud_noise
    from seedthree.bl.materials import srgb_to_linear_hex
    size = 72
    tex = (cloud_noise(size).astype(np.float32) / 255.0).reshape(size, size, size)
    tint = np.array(srgb_to_linear_hex(0xe6eef7), np.float32)

    def sample(p):
        q = np.clip(p * size - 0.5, 0, size - 1)
        i0 = np.minimum(np.floor(q).astype(np.int64), size - 2)
        f = q - i0
        out = 0
        for dz in (0, 1):
            for dy in (0, 1):
                for dx in (0, 1):
                    wgt = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                    out = out + wgt * tex[i0[:, 2] + dz, i0[:, 1] + dy, i0[:, 0] + dx]
        return out
    tr, br, bl, tl = [np.array(v) for v in cam.data.view_frame(scene=sc)]
    X, Y = np.meshgrid((np.arange(W) + 0.5) / W, (np.arange(H) + 0.5) / H)
    left = tl[None, None] * (1 - Y[..., None]) + bl[None, None] * Y[..., None]
    right = tr[None, None] * (1 - Y[..., None]) + br[None, None] * Y[..., None]
    d_world = (left * (1 - X[..., None]) + right * X[..., None]).reshape(-1, 3) @ np.array(cam.matrix_world.to_3x3()).T
    inv = c0.matrix_world.inverted()
    o_l = np.array(inv @ cam.matrix_world.translation)
    d_l = d_world @ np.array(inv.to_3x3()).T
    o = np.array([o_l[0], o_l[2], -o_l[1]])
    d = np.stack([d_l[:, 0], d_l[:, 2], -d_l[:, 1]], 1)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    with np.errstate(divide='ignore', invalid='ignore'):
        ta, tb = (-0.5 - o[None]) / d, (0.5 - o[None]) / d
    tmin = np.nanmax(np.minimum(ta, tb), axis=1)
    tmax = np.nanmin(np.maximum(ta, tb), axis=1)
    idx = np.nonzero((tmin <= tmax) & (tmax > 0))[0]
    dd = d[idx]
    delta = np.min(1.0 / np.abs(dd), axis=1) / 60
    t = np.maximum(tmin[idx], 0.0)
    tend = tmax[idx]
    pos = o[None] + dd * t[:, None]
    col = np.zeros((len(idx), 3), np.float32)
    al = np.zeros(len(idx), np.float32)
    alive = np.ones(len(idx), bool)
    for _ in range(400):
        live = np.nonzero(alive & (t < tend))[0]
        if len(live) == 0:
            break
        p = pos[live]
        m = np.clip((sample(p + 0.5) - 0.14) / 0.32, 0, 1)
        m = m * m * (3 - 2 * m) * 0.13
        c = (sample(p - 0.01) - sample(p + 0.01)) * 3.0 + (p[:, 0] + p[:, 1]) * 0.25 + 0.2
        wa = (1 - al[live]) * m
        col[live] += wa[:, None] * c[:, None]
        al[live] += wa
        alive[live[al[live] >= 0.95]] = False
        pos[live] += dd[live] * delta[live, None]
        t[live] += delta[live]
    A = np.zeros(W * H, np.float32)
    C = np.zeros((W * H, 3), np.float32)
    A[idx] = al
    C[idx] = col + tint[None]
    A, C = A.reshape(H, W), C.reshape(H, W, 3)
    return C * A[..., None] + bg * (1 - A[..., None]), A


def main():
    raw()
    for view in ('close', 'ground'):
        sc, c0, cam = setup(view)
        dg = bpy.context.evaluated_depsgraph_get()
        gset = c0.evaluated_get(dg).evaluated_geometry()
        grids = sorted(g.name for g in gset.volume.grids) if gset.volume is not None else []
        S.check('%s: the cloud volume carries density and shade grids' % view, grids == ['density', 'shade'], str(grids))
        c0.hide_render = True
        bg = render_linear(sc, os.path.join(S.OUT, 'cloud_%s_sky.png' % view))
        c0.hide_render = False
        got = render_linear(sc, os.path.join(S.OUT, 'cloud_%s_blender.png' % view))
        app, A = app_march(sc, c0, cam, bg)
        save_png(sc, app, os.path.join(S.OUT, 'cloud_%s_app.png' % view))
        m, core = A > 0.05, A > 0.6
        dg_, da = (got - bg).mean(2), (app - bg).mean(2)
        for name, mask in (('cloud', m), ('core', core)):
            g, a = float(dg_[mask].mean()), float(da[mask].mean())
            S.check('%s: the %s adds what the app\'s adds over the sky (within 25 %%)' % (view, name),
                    abs(g - a) < 0.25 * a, 'Blender %+.3f, app %+.3f' % (g, a))
        diff = float(np.abs(got - app).mean(2)[m].mean())
        S.check('%s: per-pixel difference to the app\'s march under 0.06' % view, diff < 0.06, '%.4f' % diff)
    S.summary('cloud_probe')


main()
