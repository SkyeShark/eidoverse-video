"""The UNKNOWN FORCE cloud deck: its drawing order and its placement (the kit and its decks only: no city, no GPU).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_city/test_cloud_deck_order.py

three drew the deck (renderOrder 1, normal blending) before the city's additive signs (2), rain (3) and pillar of
light (4). EEVEE draws blended objects back to front by the depth of their origins along the view, so the deck's root
rides the camera CLOUD_SORT_PUSH metres down its view and a Geometry Nodes offset puts each sheet back. For camera
poses across the dive, the hole's eight moves and straight up / straight down, checks:
  - every sheet's quad lies where three's did: centred on the camera's x and y at its height, 4.8 km across
  - every sheet's origin is deeper along the view than the set root (where the signs, the rain and the pillar sit)
    and than the far clip, so EEVEE draws the deck before them
  - among themselves the sheets keep three's order (the depth of each quad's centre along the view)
  - after a cut to another camera the deck follows the new one, without a frame change
  - follow=False: the sheets stay over the origin (6 km across), still drawn first
  - sort_push=0: the sheets in the same place, in EEVEE's own order (at the dive's end, in front of the set root:
    the deck laid over the pillar of light, the dark veil this fixes)
  - no camera: the sheets at their heights over the origin
Prints PASS / FAIL.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from eidoblend.sets.unknown_force import citykit as KIT  # noqa: E402
from eidoblend.sets.unknown_force import city as C  # noqa: E402
from eidoblend.sets.unknown_force import hole as H  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[uf-cloud-deck] %s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


for c in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.node_groups,
          bpy.data.images):
    for x in list(c):
        c.remove(x)
scene = bpy.context.scene
K = KIT.make_kit()
coll = bpy.data.collections.new('uf_cloud_test')
scene.collection.children.link(coll)
deck = KIT.make_clouds(K, coll)
still = KIT.make_clouds(K, coll, {'follow': False}, name='uf_clouds_still')
eevee = KIT.make_clouds(K, coll, {'sort_push': 0}, name='uf_clouds_eevee')
check('the deck: 13 sheets, each with the placing Geometry Nodes', len(deck['sheets']) == 13 and
      all(s.modifiers and s.modifiers[0].type == 'NODES' for s in deck['sheets']), str(len(deck['sheets'])))
HEIGHTS = [KIT.CLOUD['base'] + (KIT.CLOUD['top'] - KIT.CLOUD['base']) * i / 12 for i in range(13)]


def new_cam(name):
    cd = bpy.data.cameras.new(name)
    cd.clip_start, cd.clip_end = 0.25, 6000.0
    ob = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(ob)
    return ob


cam = new_cam('deck_cam')
scene.camera = cam


def view(ob, dg):
    m = ob.evaluated_get(dg).matrix_world
    return m.translation.copy(), -(m.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()


def sheet_state(d, dg):
    """(quad centres, quad extents (x, y), origins) of a deck's sheets, in world space, as evaluated."""
    cs, ex, orig = [], [], []
    for s in d['sheets']:
        ev = s.evaluated_get(dg)
        co = np.empty(len(ev.data.vertices) * 3, np.float64)
        ev.data.vertices.foreach_get('co', co)
        M = np.array(ev.matrix_world, np.float64)
        w = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        cs.append(w.mean(0))
        ex.append(w.max(0)[:2] - w.min(0)[:2])
        orig.append(np.array(ev.matrix_world.translation, np.float64))
    return np.array(cs), np.array(ex), np.array(orig)


def place_err(cs, ex, over_xy, size):
    want = np.array([[over_xy[0], over_xy[1], h] for h in HEIGHTS])
    return float(np.abs(cs - want).max()), float(np.abs(ex - size).max())


POSES = [(f'dive {t:g} s', C.dive_cam(t)) for t in (0.0, 4.0, 10.0, 16.0, 24.0, 30.0, 33.0, 36.0, 40.8)]
POSES += [(f'hole {n}', H.hole_cam(n, H.HOLE_CAM_DUR[n] * 0.5)) for n in H.HOLE_CAMS]
POSES += [('straight up from the street', {'pos': (300.0, -200.0, 14.0), 'target': (300.0, -200.0, 200.0),
                                           'fov': 60, 'up': (0.0, 1.0, 0.0)}),
          ('straight down from over the deck', {'pos': (-400.0, 250.0, 900.0), 'target': (-400.0, 250.0, 0.0),
                                                'fov': 60, 'up': (0.0, 1.0, 0.0)})]
worst = {'place': 0.0, 'size': 0.0, 'still': 0.0, 'eevee_place': 0.0}
behind, beyond, order, n_order = [], [], [], 0
for name, pose in POSES:
    KIT.apply_cam(cam, pose)
    dg = bpy.context.evaluated_depsgraph_get()
    cp, fwd = view(cam, dg)
    cpn, fw = np.array(cp), np.array(fwd)
    cs, ex, orig = sheet_state(deck, dg)
    e_p, e_s = place_err(cs, ex, cpn[:2], 4800.0)
    worst['place'], worst['size'] = max(worst['place'], e_p), max(worst['size'], e_s)
    s_cs, s_ex, s_orig = sheet_state(still, dg)
    e_c, e_x = place_err(s_cs, s_ex, (0.0, 0.0), 6000.0)
    worst['still'] = max(worst['still'], e_c, e_x)
    v_cs, v_ex, v_orig = sheet_state(eevee, dg)
    worst['eevee_place'] = max(worst['eevee_place'], *place_err(v_cs, v_ex, cpn[:2], 4800.0))
    depth = (orig - cpn) @ fw                       # what EEVEE sorts by: each origin along the view
    s_depth = (s_orig - cpn) @ fw
    root_depth = float(-cpn @ fw)                   # the set root at the origin: the signs, the rain, the pillar
    behind.append((name, float(depth.min()) - root_depth, float(s_depth.min()) - root_depth))
    beyond.append((name, float(depth.min()) - cam.data.clip_end))
    if abs(fw[2]) > 1e-3:                           # three's order: back to front by each quad centre's depth
        n_order += 1
        order.append((name, list(np.argsort(-depth, kind='stable')) == list(np.argsort(-((cs - cpn) @ fw), kind='stable'))))
check('placement: every quad centred on the camera\'s x, y at its height (CLOUD base..top), every pose',
      worst['place'] < 0.02, f"worst {worst['place'] * 1000:.1f} mm over {len(POSES)} poses")
check('placement: every quad 4.8 km across, as the engine\'s', worst['size'] < 0.02, f"worst {worst['size']:.4f} m")
check('drawn first: every sheet\'s origin deeper along the view than the set root, every pose',
      all(b[1] > 1000.0 and b[2] > 1000.0 for b in behind),
      'margin min %.0f m (follow), %.0f m (still)' % (min(b[1] for b in behind), min(b[2] for b in behind)))
check('drawn first: every sheet\'s origin beyond the far clip (6 km), every pose', all(b[1] > 0 for b in beyond),
      'margin min %.0f m' % min(b[1] for b in beyond))
check('the sheets keep three\'s order among themselves (by each quad centre\'s depth)',
      n_order > 0 and all(o[1] for o in order), f'{sum(o[1] for o in order)}/{n_order} poses')
check('follow=False: the sheets stay over the origin, 6 km across', worst['still'] < 0.02,
      f"worst {worst['still'] * 1000:.1f} mm")
check('sort_push=0: the sheets in the same place', worst['eevee_place'] < 0.02,
      f"worst {worst['eevee_place'] * 1000:.1f} mm")
# EEVEE's own order at the dive's end (the veil): the deck's origins above the camera sort in front of the set root
KIT.apply_cam(cam, C.dive_cam(40.8))
dg = bpy.context.evaluated_depsgraph_get()
cp, fwd = view(cam, dg)
cpn, fw = np.array(cp), np.array(fwd)
_, _, v_orig = sheet_state(eevee, dg)
vd = (v_orig - cpn) @ fw
check('sort_push=0 at the dive\'s end: the sheets sort in front of the set root (EEVEE laid the deck over the '
      'pillar of light)', float(vd.max()) < float(-cpn @ fw),
      f'sheets {vd.min():.1f}..{vd.max():.1f} m, set root {float(-cpn @ fw):.1f} m')
# a cut to another camera: the deck follows the new active camera, no frame change
cam2 = new_cam('deck_cam_2')
KIT.apply_cam(cam2, H.hole_cam('riseUp', 9.0))
scene.camera = cam2
dg = bpy.context.evaluated_depsgraph_get()
cp2, fwd2 = view(cam2, dg)
cs, ex, orig = sheet_state(deck, dg)
e_p, _ = place_err(cs, ex, np.array(cp2)[:2], 4800.0)
d2 = (orig - np.array(cp2)) @ np.array(fwd2)
check('a cut: the deck follows the new active camera', e_p < 0.02 and float(d2.min()) > cam2.data.clip_end,
      f'{e_p * 1000:.1f} mm, origins {d2.min():.0f} m down its view')
# no camera: the sheets at their heights over the origin
scene.camera = None
dg = bpy.context.evaluated_depsgraph_get()
cs, ex, orig = sheet_state(deck, dg)
e_p, e_s = place_err(cs, ex, (0.0, 0.0), 4800.0)
check('no camera: the sheets at their heights over the origin', e_p < 0.02 and e_s < 0.02, f'{e_p * 1000:.1f} mm')
scene.camera = cam
K.made.dispose()
fails = [n for n, ok in results if not ok]
print(f'[uf-cloud-deck] {len(results) - len(fails)}/{len(results)} passed' + (f'; FAILED: {fails}' if fails else ''),
      flush=True)
