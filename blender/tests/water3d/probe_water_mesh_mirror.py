"""Does WaterMesh mirror the scene's objects (three's reflector(): a planar render of the scene)?

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/water3d/probe_water_mesh_mirror.py [-- samples=32]

A calm WaterMesh (a flat normal map, distortion 0) with a bright red post standing in it and an orange one off to the
side, a camera 1.5 m up. Variants (columns): the planar probe on (create_water_mesh's default) / off (ray tracing
only), each with the posts on screen. Checks that the water below each post takes its colour (the mirror image),
reading the water where the reflection must land against the same spot with the post removed.
Out: out/verify/wmesh_mirror_<variant>.png and wmesh_mirror_sheet.png.
"""

import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _scene as S  # noqa: E402
from eidoblend.fx.water_flat import create_water_mesh  # noqa: E402

A = S.args()
OUT = os.path.join(S.OUT, 'verify')
os.makedirs(OUT, exist_ok=True)
sc = S.fresh_scene(res=(640, 360), fps=24, end=24, samples=int(A.get('samples', 32)))
SKY = os.path.join(S.HERE, '..', '..', '..', 'eidoverse', 'assets', 'sky', 'kloppenheim_puresky_ldr.png')

# a flat normal map: (0.5, 0.5, 1) everywhere
flat = os.path.join(OUT, 'wmesh_flat_normals.png')
import OpenImageIO as oiio  # noqa: E402
a = np.zeros((16, 16, 3), dtype=np.uint8)
a[..., 0] = a[..., 1] = 128
a[..., 2] = 255
o = oiio.ImageOutput.create(flat)
o.open(flat, oiio.ImageSpec(16, 16, 3, 'uint8'))
o.write_image(a)
o.close()


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for p in list(bpy.data.lightprobes):
        bpy.data.lightprobes.remove(p)


def emissive(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*rgb, 1)
    em.inputs['Strength'].default_value = 4.0
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m


red, orange = emissive('red_post', (1, 0.02, 0.02)), emissive('orange_post', (1, 0.4, 0.0))
results = {}
shots = []
for variant in ('probe', 'raytrace'):
    for posts in (True, False):
        clear()
        S.world_panorama(sc, SKY, strength=0.6, rotate_deg=180)
        create_water_mesh(size_xy=(400, 400), location=(0, 150, 0), water_normals=flat, distortion_scale=0.0,
                          water_color=0x0b2a33, planar_probe=(variant == 'probe'))
        if posts:
            S.box(sc, 'red_post', (0.6, 0.6, 3.0), (0, 14, 1.5), red)
            S.box(sc, 'orange_post', (0.6, 0.6, 3.0), (-6, 30, 1.5), orange)
        S.camera_look(sc, (0, 0, 1.5), (0, 20, 1.0), lens=35)
        p = os.path.join(OUT, f'wmesh_mirror_{variant}_{"posts" if posts else "empty"}.png')
        S.render(sc, 1, p)
        shots.append(p)
        results[(variant, posts)] = S.read_png(p).astype(np.float64)
S.contact_sheet(shots, os.path.join(OUT, 'wmesh_mirror_sheet.png'), cols=2, half=False)

# where the red post's mirror image must land: project its base and its reflected top into the camera
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402
cam = sc.camera
ok = True
for variant in ('probe', 'raytrace'):
    for (x, y), nm in (((0, 14), 'red'), ((-6, 30), 'orange')):
        lo = world_to_camera_view(sc, cam, Vector((x, y, -0.3)))      # just under the waterline
        hi = world_to_camera_view(sc, cam, Vector((x, y, -2.0)))      # most of the reflected post
        W, H = 640, 360
        c0, c1 = int(lo.x * W), int(hi.y * H)
        r0, r1 = int((1 - lo.y) * H), int((1 - hi.y) * H)
        win = (slice(min(r0, r1), max(r0, r1) + 1), slice(max(c0 - 2, 0), c0 + 3))
        with_p = results[(variant, True)][win].mean(axis=(0, 1))
        without = results[(variant, False)][win].mean(axis=(0, 1))
        gain = with_p[0] - without[0]
        ok &= S.check(f'{variant}: the water mirrors the {nm} post (red channel under it rises)', gain > 8.0,
                      f'rgb {with_p.round(1)} with the post vs {without.round(1)} without (+{gain:.1f})')
print('ALL PASS' if ok else 'SOME FAIL')
