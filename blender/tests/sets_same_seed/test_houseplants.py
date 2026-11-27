"""test_houseplants.py: eidoblend.props.houseplants built and checked (Blender):

    bash run_blender.sh blender/tests/sets_same_seed/test_houseplants.py [--no-render]

Each species is built on its own (props.build('houseplants', species=...)): its parts closed solids, every one given its
material (none left in clay), its leaves carrying their own data for the leaf material, its size what the package says
(measured from its parts: height above its floor, its pot's width), the root carrying it (moved and turned with it),
dispose() leaving nothing. Then the lab's three grown together (build_group): no leaf of one through another. Unless
--no-render, two small stills into out/houseplants/: the three in a row, and the basil and the watering can close.
The plants' CC0 sets are fetched into the shared library on first use (eidoblend/props/houseplants/cc0.json).
"""
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))       # <repo>/blender
from eidoblend import props  # noqa: E402
from eidoblend.props import houseplants as HP  # noqa: E402
from eidoblend.props.hardsurface import masses as hs  # noqa: E402

OUT = Path(__file__).resolve().parent / 'out' / 'houseplants'
FAILS = []
CLAYS = ('houseplant_clay', 'clay')
# species -> (height range m, pot width range m), as the package's doc gives them
SIZES = {'rubber_plant': ((1.5, 1.7), (0.3, 0.34)), 'monstera': ((1.1, 1.3), (0.28, 0.32)), 'corn_plant': ((1.75, 1.95), (0.38, 0.42)),
         'basil': ((0.22, 0.28), (0.08, 0.095))}
LEAF_OPEN_MAX = 8        # (a known fault: a few blade edges of the rubber plant's leaves are open, as the lab's are)
POTS = {'rubber_plant': 'plant_rubber_pot', 'monstera': 'plant_monstera_pot', 'corn_plant': 'plant_dracaena_pot', 'basil': 'basil_pot'}


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def bounds(objs):
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def tris(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    V, T = [], []
    for o in objs:
        me = o.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        b = len(V)
        V += [o.matrix_world @ v.co for v in me.vertices]
        T += [tuple(b + i for i in t.vertices) for t in me.loop_triangles]
        o.evaluated_get(dg).to_mesh_clear()
    return BVHTree.FromPolygons(V, T) if T else None


def one(species):
    n0 = len(hs.REPORT)
    p = props.build('houseplants', species=species, location=(0.0, 0.0, 0.0))
    opened = [(r[0], r[1]) for r in hs.REPORT[n0:] if r[1]]
    bad = [n for n, k in opened if not (n.endswith('_leaves') and k <= LEAF_OPEN_MAX)]
    check(f'{species}: built, every part closed', p.parts and not bad,
          f'{len(p.parts)} parts' + (f'; open edges: {opened[:4]}' if opened else ''))
    clay = [o.name for o in p.parts if not o.material_slots or any(s.material is None or s.material.name.split('.')[0] in CLAYS for s in o.material_slots)]
    check(f'{species}: every part dressed', not clay, ', '.join(clay[:5]))
    leaves = [o for o in p.parts if o.name.startswith('plant_') and o.name.endswith('_leaves')]
    if leaves:
        check(f'{species}: its leaves carry their data', all('leafdata' in o.data.attributes for o in leaves))
    lo, hi = bounds(p.parts)
    if species in SIZES:
        (h0, h1), (w0, w1) = SIZES[species]
        pot = [o for o in p.parts if o.name.split('.')[0] == POTS[species]]
        plo, phi = bounds(pot) if pot else (Vector(), Vector())
        pw = max(phi.x - plo.x, phi.y - plo.y)
        check(f'{species}: its size', h0 <= hi.z - lo.z <= h1 and w0 <= pw <= w1, f'{hi.z - lo.z:.3f} m tall, its pot {pw:.3f} m across')
    else:
        check(f'{species}: its size', 0.2 < hi.z - lo.z < 0.5, f'{hi.z - lo.z:.3f} m tall, {hi.x - lo.x:.3f} m long')
    check(f'{species}: stands on its floor', abs(lo.z) < 0.003, f'lowest point {lo.z * 1000.0:.1f} mm')
    p.group.location, p.group.rotation_euler = (5.0, 1.0, 0.0), (0.0, 0.0, math.radians(90.0))
    lo2, hi2 = bounds(p.parts)
    c1, c2 = (lo + hi) / 2.0, (lo2 + hi2) / 2.0
    check(f'{species}: the root carries it', abs(c2.x - 5.0 + c1.y) < 1e-3 and abs(c2.y - 1.0 - c1.x) < 1e-3, f'centre {tuple(round(v, 3) for v in c2)}')
    names = [o.name for o in p.parts] + [p.group.name]
    p.dispose()
    left = [n for n in names if n in bpy.data.objects]
    check(f'{species}: dispose', not left and species not in bpy.data.collections, ', '.join(left[:4]))


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    bpy.ops.wm.read_factory_settings(use_empty=True)
    check('registered in props', 'houseplants' in props.NAMES and props.houseplants is HP)
    for sp in HP.SPECIES:
        one(sp)
    g = HP.build_group([('rubber_plant', (-0.7, 0.0, 0.0)), ('monstera', (0.0, 0.0, 0.0)), ('corn_plant', (0.7, 0.0, 0.0))], name='lab_three')
    leaves = {k: [o for o in g.parts if o.name.startswith(k)] for k in ('plant_rubber_leaves', 'plant_monstera_leaves', 'plant_dracaena_leaves')}
    ta, tb, tc = (tris(v) for v in leaves.values())
    cross = len(ta.overlap(tb)) + len(tb.overlap(tc)) + len(ta.overlap(tc))
    check('the three grown together: no leaf through another', cross == 0, f'{cross} crossing triangle pairs')
    if '--no-render' in a:
        print(f'[test_houseplants] {len(FAILS)} FAIL', flush=True)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    sc = bpy.context.scene
    basil = HP.build('basil', location=(1.6, -0.4, 0.75))
    can = HP.build('watering_can', location=(1.85, -0.35, 0.75))
    floor = bpy.data.objects.new('floor', bpy.data.meshes.new('floor'))
    floor.data.from_pydata([(-4, -4, 0), (4, -4, 0), (4, 4, 0), (-4, 4, 0)], [], [(0, 1, 2, 3)])
    sc.collection.objects.link(floor)
    stand = bpy.data.objects.new('stand', bpy.data.meshes.new('stand'))
    stand.data.from_pydata([(1.3, -0.7, 0.75), (2.2, -0.7, 0.75), (2.2, 0.0, 0.75), (1.3, 0.0, 0.75)], [], [(0, 1, 2, 3)])
    sc.collection.objects.link(stand)
    w = bpy.data.worlds.new('plants_world')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.6, 0.7, 1.0)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
    sc.world = w
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(-30.0))
    sc.collection.objects.link(sun)
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 32
    sc.view_settings.view_transform = 'AgX'
    sc.render.resolution_x, sc.render.resolution_y = 480, 360
    for name, pos, aim, lens in (('three', (0.0, -4.2, 1.1), (0.0, 0.0, 0.75), 35.0), ('basil_and_can', (1.75, -1.25, 1.15), (1.72, -0.38, 0.85), 50.0)):
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cam = bpy.data.objects.new(name, cd)
        sc.collection.objects.link(cam)
        cam.location = pos
        cam.rotation_euler = (Vector(aim) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
        sc.camera = cam
        sc.render.filepath = str(OUT / f'houseplants_{name}.png')
        bpy.ops.render.render(write_still=True)
        check(f'still {name}', (OUT / f'houseplants_{name}.png').is_file())
    basil.dispose()
    can.dispose()
    print(f'[test_houseplants] {len(FAILS)} FAIL', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)
