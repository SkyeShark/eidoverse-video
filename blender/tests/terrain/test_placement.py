"""Probe: the placement helpers on a terrain, and the audits catching deliberate mistakes.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/terrain/test_placement.py [--no-render]

Builds a small terrain with a clearing, then:
  place_on      a crate on the clearing, a second crate stacked on it, a third on the slope
  snap_to_ground  posts off the vertex grid on the hills, checked against the mesh's own triangle
                under each (and the mesh against the analytic height_at between vertices)
  scatter_on    concrete chunks, sunk and tilted, deterministic per seed
  drive_along   a barrel keyed along a path (heading checked against the path's tangent)
  find_clear_spot  a bench near the crates on the clearing, then place_on there: it must overlap nothing
and plants four mistakes the audits must name: a crate hanging 1.5 m in the air (far), one
resting 4 cm above the ground (near), a decal flush on a crate face (z-fighting) and a box buried
inside a crate (deep interpenetration). Prints PASS/FAIL per check; renders two probe stills.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from eidoblend.terrain import make_terrain  # noqa: E402
from eidoblend.placement import (place_on, snap_to_ground, scatter_on, drive_along, tight_box,  # noqa: E402
                                 run_placement_audits, place_against, face_toward, hinge, find_clear_spot)

MODELS = F.WORKTREE / 'eidoverse' / 'assets' / 'models'
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[placement-test] %s %s %s' % ('PASS' if ok else 'FAIL', name, detail))


def import_glb(stem, name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(MODELS / (stem + '.glb')))
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    for o in new:
        if o.parent is None:
            o.parent = root
        o['eido_loaded_asset'] = True
    root['eido_loaded_asset'] = True
    return root


def duplicate(root, name):
    """A copy of an imported hierarchy sharing its mesh data."""
    new_root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(new_root)
    new_root.matrix_world = root.matrix_world.copy()
    for c in root.children_recursive:
        if c.parent == root:
            cc = c.copy()
            bpy.context.scene.collection.objects.link(cc)
            cc.parent = new_root
            cc.matrix_parent_inverse = c.matrix_parent_inverse.copy()
    return new_root


F.clean_scene()
F.render_settings(960, 540, 16)
F.test_daylight(sun_elevation=34, sun_azimuth=220)
terrain, height_at = make_terrain(size=28, segments=280, amplitude=1.4, seed=11, frequency=2.0,
                                  flat_radius=4.5, layers=[{'set': 'Ground106', 'tile_metres': 2.3, 'roughness': 1.35},
                                                           {'set': 'withered_grass', 'tile_metres': 2.0,
                                                            'tint': (0.6, 0.58, 0.52)}],
                                  high_start=0.1)

# ── place_on: a crate on the clearing, a second stacked on it, a third on the slope ──
green = import_glb('crate_large_green', 'crate_green')
F.WORKTREE  # noqa
b = tight_box(green)
print('[placement-test] crate size %.2f x %.2f x %.2f m' % tuple(b[1] - b[0]))
check('place_on clearing', place_on(green, terrain, xy=(-1.2, 0.8)))
gb = tight_box(green)
check('crate rests on the clearing', abs(gb[0].z - (height_at(-1.2, 0.8) + 0.0006)) < 0.002,
      'bottom %.4f vs ground %.4f' % (gb[0].z, height_at(-1.2, 0.8)))
red = import_glb('crate_large_red', 'crate_red')
red.rotation_euler.z = math.radians(25)
check('place_on stacked', place_on(red, green, xy='centered'))
rb = tight_box(red)
check('stacked crate sits on the lower crate', abs(rb[0].z - (gb[1].z + 0.0006)) < 0.01,
      'bottom %.4f vs top %.4f' % (rb[0].z, gb[1].z))
blue = import_glb('crate_large_blue', 'crate_blue')
check('place_on slope', place_on(blue, terrain, xy=(6.2, 2.4)))

# ── snap_to_ground: posts off the vertex grid, on the hills ──
# the terrain mesh's own surface, independent of the placement rays: the triangle under (x, y),
# interpolated (make_terrain's object sits at the origin, unrotated: mesh = world)
_me = terrain.data
_me.calc_loop_triangles()
_co = np.empty(len(_me.vertices) * 3)
_me.vertices.foreach_get('co', _co)
_tv = np.empty(len(_me.loop_triangles) * 3, dtype=np.int64)
_me.loop_triangles.foreach_get('vertices', _tv)
TRI = _co.reshape(-1, 3)[_tv.reshape(-1, 3)]


def mesh_height(x, y):
    a, b, c = TRI[:, 0], TRI[:, 1], TRI[:, 2]
    e1, e2 = b[:, :2] - a[:, :2], c[:, :2] - a[:, :2]
    p = np.array([x, y]) - a[:, :2]
    den = e1[:, 0] * e2[:, 1] - e2[:, 0] * e1[:, 1]
    u = (p[:, 0] * e2[:, 1] - e2[:, 0] * p[:, 1]) / den
    v = (e1[:, 0] * p[:, 1] - p[:, 0] * e1[:, 1]) / den
    i = np.flatnonzero((u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9))[0]
    return float(a[i, 2] + u[i] * (b[i, 2] - a[i, 2]) + v[i] * (c[i, 2] - a[i, 2]))


errs, gaps, slopes = [], [], []
for k, (x, y) in enumerate([(-5.537, -3.071), (9.377, -7.871), (-8.467, 6.531), (5.213, 4.887)]):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=1.2, location=(x, y, 5.0))
    post = bpy.context.active_object
    post.name = 'post_%d' % k
    snap_to_ground(post, terrain, grid=1, surface_eps=0.0)
    pb = tight_box(post)
    errs.append(abs(pb[0].z - mesh_height(x, y)))
    gaps.append(abs(mesh_height(x, y) - height_at(x, y)))
    slopes.append(math.hypot(height_at(x + 0.05, y) - height_at(x - 0.05, y),
                             height_at(x, y + 0.05) - height_at(x, y - 0.05)) / 0.1)
check('snap_to_ground lands on the mesh (off the vertex grid, on slopes %s)' % ', '.join('%.2f' % s for s in slopes),
      max(errs) < 1e-4 and min(slopes) > 0.05, 'max |post - mesh| %.6f m' % max(errs))
# between vertices the mesh is flat where height_at curves: 0.1 m spacing keeps them within ~1 mm
check('the mesh follows height_at between vertices', max(gaps) < 0.002, 'max |mesh - height_at| %.5f m' % max(gaps))

# ── scatter_on: concrete chunks, sunk and tilted ──
chunk = import_glb('apocalyptic_destroyed_rubble_debris_concrete_rebar_chunk', 'chunk_0')
cb = tight_box(chunk)
s = 0.55 / max(cb[1] - cb[0])
chunk.scale = (s, s, s)
chunks = [chunk] + [duplicate(chunk, 'chunk_%d' % i) for i in range(1, 7)]
placed = scatter_on(chunks, terrain, min_spacing=1.2, rng_seed=7, sink=(0.15, 0.35), tilt_max=0.3)
check('scatter_on placed all', len(placed) == len(chunks), '%d of %d' % (len(placed), len(chunks)))
check('scatter sinks flagged', all(c.get('_sunk_placement') for c in placed))

# ── place_against + face_toward ──
bpy.ops.mesh.primitive_cube_add(size=0.5)
stool = bpy.context.active_object
stool.name = 'stool'
place_against(stool, green, 'front', 0.3)
place_on(stool, terrain)
sb_ = tight_box(stool)
check('place_against front gap', abs((gb[0].y - sb_[1].y) - 0.3) < 1e-3, 'gap %.4f' % (gb[0].y - sb_[1].y))

# ── hinge: a lid on the blue crate swings open about its back edge ──
bb = tight_box(blue)
bpy.ops.mesh.primitive_cube_add(size=1.0)
lid = bpy.context.active_object
lid.name = 'lid'
lid.scale = ((bb[1].x - bb[0].x) * 0.5, (bb[1].y - bb[0].y) * 0.5, 0.02)
bpy.context.view_layer.update()
place_on(lid, blue, xy='centered', surface_eps=0.0)
piv = hinge(lid, 'back')
check('hinge at back edge', abs(piv.matrix_world.translation.y - tight_box(lid)[1].y) < 1e-4)
piv.rotation_euler.x = math.radians(-35)                   # a back hinge opens with a NEGATIVE X turn
bpy.context.view_layer.update()
check('lid swings up, clear of the crate', tight_box(lid)[1].z > bb[1].z + 0.3)

# ── drive_along: a barrel keyed along a path, heading = travel ──
barrel_src = import_glb('scifi_barrels_single', 'barrel_model')
bpy.context.view_layer.update()
xb = tight_box(barrel_src)
barrel = bpy.data.objects.new('barrel', None)               # recentred rig: the GLB's pivot sits off its body
bpy.context.scene.collection.objects.link(barrel)
barrel.location = ((xb[0].x + xb[1].x) / 2, (xb[0].y + xb[1].y) / 2, xb[0].z)
bpy.context.view_layer.update()
barrel_src.parent = barrel
barrel_src.matrix_parent_inverse = barrel.matrix_world.inverted()
place_on(barrel, terrain, xy=(-6, -6))
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 48
drive = drive_along(barrel, [(-6, -6), (-2, -7.5), (3, -6.5)], duration=2.0, forward='-y')
sc.frame_set(24)
v1 = barrel.matrix_world.translation.copy()
sc.frame_set(25)
v2 = barrel.matrix_world.translation.copy()
d = (v2 - v1)
nose = barrel.matrix_world.to_3x3() @ Vector((0, -1, 0))
ang = math.degrees(Vector((d.x, d.y)).angle(Vector((nose.x, nose.y))))
check('drive_along heading follows travel', ang < 2.0, 'nose vs travel %.2f deg' % ang)
sc.frame_set(1)

# ── the deliberate mistakes ──
def nudge(obj, v):
    mw = obj.matrix_world.copy()
    mw.translation = mw.translation + Vector(v)
    obj.matrix_world = mw
    bpy.context.view_layer.update()


floater = duplicate(blue, 'MISTAKE_floating_crate')            # hand-placed 1.5 m up: 'far'
bpy.context.view_layer.update()
fb = tight_box(floater)
fc = (fb[0] + fb[1]) * 0.5
nudge(floater, (0.5 - fc.x, -3.2 - fc.y, height_at(0.5, -3.2) + 1.5 - fb[0].z))
near = duplicate(blue, 'MISTAKE_near_crate')                    # hand-placed 4 cm up: 'near'
bpy.context.view_layer.update()
nb = tight_box(near)
nc = (nb[0] + nb[1]) * 0.5
nudge(near, (-3.6 - nc.x, -1.0 - nc.y, 0.0))
nb = tight_box(near)
nudge(near, (0, 0, height_at(-3.6, -1.0) + 0.04 - nb[0].z))
bpy.ops.mesh.primitive_plane_add(size=0.5)
decal = bpy.context.active_object
decal.name = 'MISTAKE_flush_decal'
decal.rotation_euler.x = math.radians(90)
bpy.context.view_layer.update()
gb = tight_box(green)
decal.location = ((gb[0].x + gb[1].x) / 2, gb[0].y, (gb[0].z + gb[1].z) / 2)
bpy.ops.mesh.primitive_cube_add(size=0.3)
buried = bpy.context.active_object
buried.name = 'MISTAKE_box_inside_crate'
buried.location = tuple((gb[0] + gb[1]) * 0.5)
bpy.context.view_layer.update()

# ── find_clear_spot on this terrain (the ground is no obstacle), then place_on there ──
bpy.ops.mesh.primitive_cube_add(size=1.0)
bench = bpy.context.active_object
bench.name = 'bench'
bench.scale = (1.4, 0.45, 0.45)
bpy.context.view_layer.update()
gc = (tight_box(green)[0] + tight_box(green)[1]) * 0.5
spot = find_clear_spot(bench, (gc.x, gc.y, height_at(gc.x, gc.y)), radius=3.0)      # on the level clearing
if spot is None:
    check('find_clear_spot finds a spot on the terrain', False, 'None')
else:
    place_on(bench, terrain, xy=(spot.x, spot.y))
    bb = tight_box(bench)
    hits = [o.name for o in bpy.context.scene.objects if o.type == 'MESH' and o not in (bench, terrain)
            and all(bb[0][i] < tight_box(o)[1][i] and bb[1][i] > tight_box(o)[0][i] for i in range(3))]
    check('find_clear_spot finds a spot on the terrain', not hits,
          'spot (%.2f, %.2f), bench overlaps %s' % (spot.x, spot.y, hits or 'nothing'))

res = run_placement_audits()
hov = {h['obj'].name: h for h in res['hovering']}
check('audit: floater is far', hov.get('MISTAKE_floating_crate', {}).get('kind') == 'far')
check('audit: near gap measured', hov.get('MISTAKE_near_crate', {}).get('kind') == 'near')
check('audit: nothing placed by the helpers is flagged', all(n.startswith('MISTAKE_') for n in hov),
      'flagged %s' % sorted(hov))
zf = [(p['a'].name, p['b'].name) for p in res['z_fighting']]
check('audit: decal z-fights', any('MISTAKE_flush_decal' in p for p in zf), str(zf[:3]))
deep = [p for p in res['clipping'] if p.get('deep')]
check('audit: buried box is deep inside', any('MISTAKE_box_inside_crate' in (p['ar'].name, p['br'].name) for p in deep),
      str([(p['ar'].name, p['br'].name) for p in deep][:3]))
check('audit: only the buried box is deep', all('MISTAKE_box_inside_crate' in (p['ar'].name, p['br'].name) for p in deep),
      str([(p['ar'].name, p['br'].name) for p in deep]))

if '--no-render' not in F.args():
    F.OUT.mkdir(parents=True, exist_ok=True)
    cam = F.camera('cam_place', (3.5, -9.0, height_at(3.5, -9.0) + 1.7), (-0.5, 0.5, 0.6), 30)
    F.render(cam, F.OUT / 'placement_eye.png')
    cam2 = F.camera('cam_place_high', (-9.0, -11.0, 7.5), (0.0, 0.0, 0.0), 35)
    F.render(cam2, F.OUT / 'placement_high.png')

bad = [n for n, ok in results if not ok]
print('[placement-test] %s: %d checks, %d failed %s' % ('PASS' if not bad else 'FAIL', len(results), len(bad), bad))
