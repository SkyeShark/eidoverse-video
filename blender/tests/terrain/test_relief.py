"""Probe: relief as real displacement. A brick wall carved by its height map beside the same
material as bump only, and a relief column whose bricks overhang its outline, under raking light.

    bash run_blender.sh blender/tests/terrain/test_relief.py
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

Then depth_metres under an UNAPPLIED scale: the same wall with scale 2 along its normal, carved in
world space (the default) and, for contrast, in object space. Close-ups from the same place relative
to each wall (relief_depth_applied / _scaled / _scaled_object.png) and the mean pixel difference
from the applied wall: world space must match it, object space doubles the depth and must not.

--shimmer: the first view with the camera turned by 0, 0.5 and 1 pixel, maps read 'Auto' and then
'Cubic' (relief_shimmer_<mode>_<k>.png), and how much each wall crawls in motion.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.terrain import find_set, relief  # noqa: E402
from eidoblend.placement import place_on  # noqa: E402

F.clean_scene()
F.render_settings(960, 540, 16)
F.test_daylight(sun_elevation=22, sun_azimuth=255)        # raking from the left
ground, h = F.ground(size=24, seed=9, clearing_m=8, relief_m=0.6)
tex = find_set('Bricks097')


def wall(name, x, method, y=0.0, normal_scale=None, space='WORLD'):
    """A 3 x 2.4 m wall facing -Y. normal_scale: leave the scale unapplied, this much along the
    wall's normal (its local Z)."""
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    w = bpy.context.active_object
    w.name = name
    w.scale = (3.0, 2.4, normal_scale or 1.0)
    if normal_scale is None:
        bpy.ops.object.transform_apply(scale=True)
    w.rotation_euler.x = math.radians(90)                  # face -Y, toward the camera
    m = relief.create_parallax_material(tex['displacement'], tex['color'], tex['normal'], tex['roughness'],
                                        uv_scale=(3.0, 2.4), tile_metres=1.0, depth_metres=0.03,
                                        roughness=0.85, method=method, space=space, name=name + '_mat')
    w.data.materials.append(m)
    if method != 'BUMP':
        print('[relief-test] %s subdivided %d levels' % (name, relief.subdivide(w, edge=0.008)))
    w.location = (x, y, 0.0)
    place_on(w, ground, xy=(x, y), surface_eps=0.0)
    print('[relief-test] %s check_relief_geometry: %s' % (name, relief.check_relief_geometry(w)))
    return w


wall('wall_relief', -1.7, 'BOTH')
wall('wall_bump', 1.7, 'BUMP')
wall('wall_scaled', -1.7, 'BOTH', y=3.5, normal_scale=2.0)
wall('wall_scaled_object', -1.7, 'BOTH', y=7.0, normal_scale=2.0, space='OBJECT')
col = relief.create_relief_column(tex['displacement'], tex['color'], tex['normal'], radius=0.42, height=2.6,
                                  around_tiles=3, depth_scale=0.05, name='column')
col.location = (0.0, -1.6, 0.0)
place_on(col, ground, xy=(0.0, -1.6))
cam = F.camera('cam_relief', (-0.6, -7.2, 1.5), (0.0, 0.0, 1.0), 35)
F.render(cam, F.OUT / 'relief.png')
cam2 = F.camera('cam_relief_graze', (-4.8, -2.2, 1.3), (-0.2, 0.0, 1.2), 50)
F.render(cam2, F.OUT / 'relief_graze.png')

shots = {}
for tag, y in (('applied', 0.0), ('scaled', 3.5), ('scaled_object', 7.0)):
    cam = F.camera('cam_depth_' + tag, (-2.6, y - 1.6, 0.9), (-1.75, y, 1.0), 50)
    shots[tag] = F.render(cam, F.OUT / ('relief_depth_%s.png' % tag))


def pixels(p):
    img = bpy.data.images.load(str(p))
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(-1, 4)[:, :3]


ref = pixels(shots['applied'])
for tag in ('scaled', 'scaled_object'):
    print('[relief-test] mean |%s - applied| = %.4f' % (tag, float(np.abs(pixels(shots[tag]) - ref).mean())))

if '--shimmer' in F.args():
    # the walls 7 m away with the camera turned by 0, 0.5 and 1 pixel, the albedo and normal maps read
    # 'Auto' (the default) and then 'Cubic' everywhere: the half-pixel frame against the average of
    # its neighbours, as a fraction of the real one-pixel change (shimmer_metric.py's measure)
    from mathutils import Matrix

    def lum(p):
        img = bpy.data.images.load(str(p))
        W_, H_ = img.size
        a = np.empty(W_ * H_ * 4, dtype=np.float32)
        img.pixels.foreach_get(a)
        bpy.data.images.remove(img)
        a = a.reshape(H_, W_, 4)[::-1, :, :3].astype(np.float64)
        y = a @ np.array([0.2126, 0.7152, 0.0722])
        k = np.exp(-np.arange(-4, 5) ** 2 / (2 * 1.5 ** 2))
        k /= k.sum()
        y = np.apply_along_axis(lambda r: np.convolve(r, k, mode='same'), 1, y)
        return np.apply_along_axis(lambda c: np.convolve(c, k, mode='same'), 0, y)

    regions = {'wall BOTH': (slice(100, 390), slice(60, 420)), 'wall BUMP': (slice(100, 380), slice(590, 870))}
    cam = bpy.data.objects['cam_relief']
    bpy.context.view_layer.update()
    base = cam.matrix_world.copy()
    px = (cam.data.sensor_width / 960) / cam.data.lens
    for mode in ('Auto', 'Cubic'):
        if mode == 'Cubic':
            for mt in bpy.data.materials:
                if 'eido_relief_depth' in mt and mt.node_tree:
                    for n in mt.node_tree.nodes:
                        if n.bl_idname == 'ShaderNodeTexImage':
                            n.interpolation = 'Cubic'
        fr = []
        for k in range(3):
            p = base.translation.copy()
            cam.matrix_world = Matrix.Translation(p) @ Matrix.Rotation(k * 0.5 * px, 4, 'Z') @ Matrix.Translation(-p) @ base
            bpy.context.view_layer.update()
            fr.append(lum(F.render(cam, F.OUT / ('relief_shimmer_%s_%d.png' % (mode.lower(), k)))))
        cam.matrix_world = base
        print('[relief-test] shimmer %-5s %s' % (mode, '  '.join(
            '%s %.2f' % (nm, np.abs(fr[1][s] - 0.5 * (fr[0][s] + fr[2][s])).mean() / np.abs(fr[2][s] - fr[0][s]).mean())
            for nm, s in regions.items())))
