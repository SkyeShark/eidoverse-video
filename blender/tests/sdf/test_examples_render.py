"""The solid EXAMPLES built as meshes, standing on a floor, rendered in EEVEE beside the engine's own raymarch of
the same SDF and shade() from the same camera.

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/sdf/test_examples_render.py -- examples=basic_sphere,mr_hege [quality=high] [t=0]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

For each example: out/ex_<name>_eevee.png (EEVEE, lit by suns that point where the shade()'s hand lights pointed,
plus a grey world for its ambient term), out/ex_<name>_ref.png (the engine's raymarch through AgX), and
out/ex_<name>_sheet.png (both side by side). PASS lines: the mesh is closed and outward, its lowest point sits on
the floor, its silhouette matches the reference's (IoU of coverage), it renders.
"""

import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402
import engine_march as EM  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import sdf  # noqa: E402

A = C.args()
NAMES = A.get('examples', 'basic_sphere').split(',')
T = float(A.get('t', '0'))
W, H = int(A.get('w', '960')), int(A.get('h', '540'))
SAMPLES = int(A.get('samples', '16'))
CACHE = os.path.join(C.OUT, 'cache')

# the hand lights of each example's shade(): (direction in three axes, colour, diffuse factor), and the ambient
# term's mean (a grey world); a Blender sun of irradiance pi * k matches a Lambert term k * N.L
RIG_SIMPLE = {'lights': [((0.5, 0.9, 0.4), (1.0, 1.0, 1.0), 0.8)], 'world': 0.45}
RIGS = {
    'basic_sphere': RIG_SIMPLE,
    'stylized_blob': {'lights': [((0.5, 0.9, 0.4), (1.0, 1.0, 1.0), 0.85)], 'world': 0.40},
    'detailed_coat': {'lights': [((0.6, 1.2, 0.4), (1.0, 1.0, 1.0), 0.85)], 'world': 0.39},
    'fractal_core': {'lights': [((0.5, 0.9, 0.4), (1.0, 1.0, 1.0), 0.8)], 'world': 0.33},
    'mr_hege': {'lights': [((5.0, 8.0, 5.0), (1.0, 0.94, 0.85), 1.1), ((-4.0, 3.0, -6.0), (0.35, 0.5, 0.85), 0.9 * 0.35)],
                'world': 0.2},
    'red_shoggoth': {'lights': [((5.0, 8.0, 5.0), (1.0, 0.94, 0.85), 1.1), ((-4.0, 3.0, -6.0), (0.35, 0.5, 0.85), 0.9 * 0.35)],
                     'world': 0.2},
}
RECIPE_RIG = {'lights': [((0.6, 0.8, -0.3), (1.0, 1.0, 1.0), 0.85)], 'world': 0.3}
# the camera, as (azimuth from the front in degrees, elevation in degrees, distance in bounds diagonals)
VIEWS = {'mr_hege': (20, 8, 1.5), 'red_shoggoth': (-25, 12, 1.35), 'detailed_coat': (55, 20, 1.35),
         'gyroid': (25, 18, 1.5)}
# overrides for close-ups: view=az,el,dist  lens=mm  aim=fraction of the bounds' height to look at  tag=suffix
VIEW_ARG = tuple(float(x) for x in A['view'].split(',')) if 'view' in A else None
LENS = float(A.get('lens', '50'))
AIM = float(A.get('aim', '0.5'))
TAG = A.get('tag', '')


def suns(rig):
    for i, (d3, col, k) in enumerate(rig['lights']):
        d = Vector((d3[0], -d3[2], d3[1])).normalized()       # three -> Blender
        ld = bpy.data.lights.new(f'key{i}', 'SUN')
        ld.energy = math.pi * k
        ld.color = col
        ld.angle = math.radians(1.5)
        ob = bpy.data.objects.new(f'key{i}', ld)
        bpy.context.scene.collection.objects.link(ob)
        ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()


def frame_camera(obj, view):
    az, el, dist = view
    bpy.context.view_layer.update()
    pts = np.array([obj.matrix_world @ Vector(c) for c in obj.bound_box])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    centre = (lo + hi) / 2
    centre[2] = lo[2] + (hi[2] - lo[2]) * AIM
    diag = float(np.linalg.norm(hi - lo))
    a, e = math.radians(az), math.radians(el)
    off = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * diag * dist * 1.6
    return C.camera(tuple(Vector(centre) + off), tuple(centre), lens=LENS)


# BVHTree.FromObject builds a tree that hits nothing past about 10 M quads (the 15.1 M-quad Menger sponge at 'high'),
# and a second render of such a mesh for its silhouette passes the job's 12 GB RAM cap: those meshes skip the
# silhouette check, saying so (test_mesh_depth_parity.py checks the mesher against the field)
BVH_MAX_QUADS = 10_000_000


def mesh_coverage(obj, cam, w, h):
    """(h, w) bool: camera rays (pixel centres) that hit the mesh, by BVH ray casts in the object's space."""
    from mathutils.bvhtree import BVHTree
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(obj, dg)
    inv = obj.matrix_world.inverted()
    frame = cam.data.view_frame(scene=sc)
    tr, br, bl = frame[0], frame[1], frame[2]
    origin = inv @ cam.matrix_world.translation
    m = np.zeros((h, w), bool)
    for j in range(h):
        v = 1.0 - (j + 0.5) / h
        for i in range(w):
            u = (i + 0.5) / w
            p_cam = bl + (br - bl) * u + (tr - br) * v
            d = (inv.to_3x3() @ (cam.matrix_world.to_3x3() @ p_cam)).normalized()
            hit = bvh.ray_cast(origin, d)
            m[j, i] = hit[0] is not None
    return m


for name in NAMES:
    ex = sdf.EXAMPLES[name]
    rig = RIGS.get(name, RECIPE_RIG)
    C.stage(W, H, SAMPLES, world_color=(rig['world'],) * 3, world_strength=1.0, sun=False,
            floor_color=(0.18, 0.18, 0.18))
    suns(rig)
    t0 = time.perf_counter()
    over = {'cache_dir': CACHE, 'name': f'ex_{name}', 'time': T}
    if 'quality' in A:
        over['quality'] = A['quality']
    if 'cells' in A:
        over['cells'] = int(A['cells'])
    obj = ex.make(**over)
    obj.place_on_ground(0.0)
    dt = time.perf_counter() - t0
    st = obj.stats
    print(f'[render] {name}: {st.get("quads")} quads, voxel {obj.voxel * 1000:.2f} mm, atlas {st.get("atlas")}, '
          f'texel {st.get("texel_mm")} mm, built in {dt:.1f} s', flush=True)
    c = obj.contour
    # closed + outward
    q = c.quads
    e = np.sort(np.stack([q, np.roll(q, -1, axis=1)], -1).reshape(-1, 2), axis=1)
    _u, cnt = np.unique(e, axis=0, return_counts=True)
    # a distance-estimator fractal, or a displaced field the engine marched at half steps (not a distance), has
    # sheets finer than a voxel where one dual vertex joins several: some edges there are shared by 4 quads (it
    # renders fine, but is not a manifold); every other example must close exactly
    need = 0.97 if (ex.get('iso', 0.0) or ex.get('step_scale', 1.0) <= 0.5) else 0.999
    C.check(f'{name}: closed mesh', float(np.mean(cnt == 2)) > need, f'{int((cnt != 2).sum())} of {len(cnt)} edges not 2-shared')
    bpy.context.view_layer.update()
    zmin = min((obj.object.matrix_world @ v.co).z for v in obj.object.data.vertices)
    C.check(f'{name}: on the floor', abs(zmin) < 1e-4, f'lowest point z = {zmin * 1000:.3f} mm')
    cam = frame_camera(obj.object, VIEW_ARG or VIEWS.get(name, (25, 18, 1.2)))
    eevee = os.path.join(C.OUT, f'ex_{name}{TAG}_eevee.png')
    ok = C.render(eevee)
    C.check(f'{name}: EEVEE render', ok, eevee)
    ref = EM.march(obj, cam, W, H, samples=4, t=T)
    refp = C.save_linear_png(os.path.join(C.OUT, f'ex_{name}{TAG}_ref.png'), ref)
    # silhouettes: the engine's march (one centred sample) against camera rays cast at the mesh, at quarter size
    # when the subject fills the frame; a distant subject is measured at full size, or its limbs are single pixels
    from bpy_extras.object_utils import world_to_camera_view
    ys = [world_to_camera_view(bpy.context.scene, cam, obj.object.matrix_world @ Vector(cb)).y
          for cb in obj.object.bound_box]
    tall = (max(ys) - min(ys)) * H
    div = 4 if tall >= 400 else (2 if tall >= 200 else 1)
    w4, h4 = W // div, H // div
    if len(c.quads) > BVH_MAX_QUADS:
        print(f'SKIP {name}: silhouette check: {len(c.quads)} quads pass what BVHTree holds and a second render '
              f'of them passes a 12 GB RAM cap; the mesher is checked against the field in test_mesh_depth_parity.py',
              flush=True)
    else:
        ref4 = EM.march(obj, cam, w4, h4, samples=1, t=T)
        m_ref = ref4[::-1, :, 3] > 0.5
        m_mesh = mesh_coverage(obj.object, cam, w4, h4)
        iou = float((m_ref & m_mesh).sum()) / max(1.0, float((m_ref | m_mesh).sum()))
        C.check(f'{name}: silhouette matches the raymarch', iou > 0.93,
                f'IoU {iou:.3f} at {w4}x{h4} (mesh {m_mesh.mean() * 100:.1f}%, raymarch {m_ref.mean() * 100:.1f}% '
                f'of the frame)')
    C.sheet([eevee, refp], os.path.join(C.OUT, f'ex_{name}{TAG}_sheet.png'), cols=2)
    for img in list(bpy.data.images):
        if img.users == 0:
            bpy.data.images.remove(img)

C.summary()
