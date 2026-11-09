"""WaterMesh's ripple normal map, and the one engine scene that used WaterMesh, in Blender.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/water3d/probe_water_mesh_normals.py [-- samples=32 three_normals=<waternormals.jpg>]

Every WaterMesh scene in the engine sampled three's examples/textures/waternormals.jpg. The Blender edition has no
copy of it and synthesises one (make_water_normals). This renders the same sea three ways, rows of the sheet:
  three      three's own waternormals.jpg, read where it lies (three_normals=, a three.js checkout; not copied)
  generated  make_water_normals' defaults (the map create_water_mesh makes when it is given none)
  steep      the earlier defaults (strength 6, all along the wind): a mean slope of 44 degrees
Columns: liquids.md's example (a 10 km sea under a cloudy SkyMesh, camera 6 m up) and the antad_response coast's
WaterMesh (coast_master.js: waterColor 0x3d525c, sunColor 0xfff2e0, sunDirection (0.2, 0.4, -0.9), distortionScale
4.5, size 1.1, a 4000 m plane) seen from a jetty at a person's height, under a SkyMesh whose sun stands where that
sunDirection points. (The film's plane began 240 m out, past its own shore water, under a night sky and fog.)
Also saves out/verify/wmesh_default.blend (create_water_mesh with no normals_dir) for test_reopen_saved_blend.py.
Prints each map's slope statistics. Sheet: out/verify/wmesh_normals_sheet.png.
"""

import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _scene as S  # noqa: E402
from eidoblend.fx.water_flat import create_water_mesh, create_sky_mesh, make_water_normals  # noqa: E402

A = S.args()
SAMPLES = int(A.get('samples', 32))
THREE = A.get('three_normals', 'C:/Users/sdn52/OneDrive/Desktop/SPOM_threejs_example_contribution/three.js/examples/'
                               'textures/waternormals.jpg')
OUT = os.path.join(S.OUT, 'verify')
os.makedirs(OUT, exist_ok=True)
sc = S.fresh_scene(res=(960, 540), fps=24, end=48, samples=SAMPLES)
maps = {}
if os.path.exists(THREE):
    maps['three'] = THREE
maps['generated'] = make_water_normals(os.path.join(OUT, 'wmesh_normals_generated.png'))
maps['steep'] = make_water_normals(os.path.join(OUT, 'wmesh_normals_steep.png'), strength=6.0, directional=1.0)


def slope_stats(path):
    import OpenImageIO as oiio
    i = oiio.ImageInput.open(path)
    a = np.asarray(i.read_image('float'))[..., :3].astype(np.float64) * 2 - 1
    i.close()
    n = a / np.linalg.norm(a, axis=-1, keepdims=True)
    t = np.degrees(np.arccos(np.clip(n[..., 2], -1, 1)))
    return f'mean {t.mean():.1f} deg, median {np.median(t):.1f}, 90 % under {np.percentile(t, 90):.1f}'


for k, p in maps.items():
    print(f'[normals] {k}: {slope_stats(p)}', flush=True)


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for p in list(bpy.data.lightprobes):
        bpy.data.lightprobes.remove(p)


shots = []
for k, p in maps.items():
    # liquids.md's example (as test_water_flat part 5)
    clear()
    sd = np.array([0.5, -0.2, 0.8])
    create_sky_mesh(sun_position=tuple(sd / np.linalg.norm(sd)), turbidity=10.0, rayleigh=2.0, cloud_coverage=0.4,
                    cloud_density=0.4, cloud_elevation=0.5)
    create_water_mesh(size_xy=(10000, 10000), sun_direction=(0.5, 0.8, 0.2), sun_color=0xffffff,
                      water_color=0x285f66, distortion_scale=3.7, water_normals=p)
    S.camera_look(sc, (0, -30, 6), (0, 60, 4), lens=30)
    sc.view_settings.exposure = -1.0
    f = os.path.join(OUT, f'wmesh_{k}_example_f0024.png')
    S.render(sc, 24, f)
    shots.append(f)
    # the coast's WaterMesh: its options verbatim (three axes), the sky's sun where its sunDirection points (three
    # (0.2, 0.4, -0.9) = Blender (0.2, 0.9, 0.4): low, over the sea), a person's eye height
    clear()
    create_sky_mesh(sun_position=(0.2, 0.9, 0.4), turbidity=6.0, rayleigh=2.5, cloud_coverage=0.25)
    # (the coast's plane began 240 m out, past its shore water; here it starts under the camera, a person on a jetty)
    create_water_mesh(size_xy=(4000, 4000), location=(0, 1990, 0), waterNormals=p, sunDirection=(0.2, 0.4, -0.9),
                      sunColor=0xfff2e0, waterColor=0x3d525c, distortionScale=4.5, size=1.1)
    S.camera_look(sc, (0, 0, 1.7), (0, 60, 0.0), lens=32)
    sc.view_settings.exposure = -1.0
    f = os.path.join(OUT, f'wmesh_{k}_coast_f0024.png')
    S.render(sc, 24, f)
    shots.append(f)
sc.view_settings.exposure = 0.0
S.contact_sheet(shots, os.path.join(OUT, 'wmesh_normals_sheet.png'), cols=2)
# the default (generated) map with no normals_dir, saved: it must come back when the file is reopened
clear()
create_sky_mesh(sun_position=(0.3, 0.9, 0.3), turbidity=4.0, rayleigh=1.5, cloud_coverage=0.3)
create_water_mesh(size_xy=(2000, 2000), location=(0, 900, 0), water_color=0x285f66, distortion_scale=3.7)
S.camera_look(sc, (0, -10, 4), (0, 100, 1), lens=32)
sc.view_settings.exposure = -1.0
S.render(sc, 12, os.path.join(OUT, 'wmesh_default_f0012.png'))
packed = [im.name for im in bpy.data.images if im.packed_file is not None]
print(('PASS' if packed else 'FAIL') + ' the generated normal map is packed into the file  ' + ', '.join(packed))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'wmesh_default.blend'))
