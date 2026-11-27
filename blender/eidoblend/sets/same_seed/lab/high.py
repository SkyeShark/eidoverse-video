"""eidoblend.sets.same_seed.lab.high: the lab's build step (Blender): the shell (shell.py), the furniture
(furniture.py), and the houseplants grown in place (eidoblend.props.houseplants): a rubber plant at (-2.8, 2.4), a
Monstera at (-2.1, 2.4), a corn plant at (3.3, 2.4), the watering can on the window board; every blade kept clear of the
side walls, the window wall's board and blinds and the radiators under it, and of the other plants.

    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py lab high --dir <out>        -> <out>/lab_high.blend
"""

import os

import bpy
from mathutils.bvhtree import BVHTree

from ....props.hardsurface import masses as hs
from ....props.houseplants import plants as P
from .. import look as L
from . import furniture, kit as K, shell

PLANTS = (('rubber_plant', -2800.0, 2400.0), ('monstera', -2100.0, 2400.0), ('corn_plant', 3300.0, 2400.0))
CAN = (-3270.0, shell.Y1 + 82.0, 900.0, 90.0)                  # the watering can on the window board, its spout toward the plants
FOLIAGE = ('plant_rubber_leaves', 'plant_monstera_leaves', 'plant_dracaena_leaves')


def in_room(x, y, z):
    """where a blade may grow (mm): clear of the side walls, of the window wall's board and blinds (y 2955) and of the
    radiators beneath the board (y 2850 under z 700), and off the floor"""
    return not (y > (2850.0 if z < 700.0 else 2955.0) or x < shell.X0 + 15.0 or x > shell.X1 - 15.0 or z < 30.0)


def tris_of(names):
    """one BVH over the final meshes of the named parts (prefix match)"""
    dg = bpy.context.evaluated_depsgraph_get()
    V, T = [], []
    for o in hs.col.objects:
        if o.type != 'MESH' or not o.name.startswith(tuple(names)):
            continue
        me = o.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        base = len(V)
        M = o.matrix_world
        V += [M @ v.co for v in me.vertices]
        T += [tuple(base + i for i in t.vertices) for t in me.loop_triangles]
        o.evaluated_get(dg).to_mesh_clear()
    return BVHTree.FromPolygons(V, T) if T else None


def crossing(a, b):
    """how many triangle pairs of the parts named a cross the parts named b (a leaf through a wall, a chair in a bench)"""
    ta, tb = tris_of(a), tris_of(b)
    return len(ta.overlap(tb)) if ta and tb else 0


def crossings():
    """{what: triangle pairs} for the leaves against the shell, the furniture and each other"""
    return {'leaves through the shell': crossing(FOLIAGE, ('wall_', 'window_', 'blind_', 'radiator_', 'room_floor', 'skirting')),
            'leaves through the furniture': crossing(FOLIAGE, ('bench_', 'screen_', 'board_', 'chair_', 'pedestal_')),
            'rubber plant leaves through monstera leaves': crossing(('plant_rubber_leaves',), ('plant_monstera_leaves',)),
            'leaves through the other plants\' pots': crossing(('plant_rubber_leaves',), ('plant_monstera_pot', 'plant_monstera_pole'))
            + crossing(('plant_monstera_leaves',), ('plant_rubber_pot', 'plant_rubber_stem'))}


def build():
    hs.new_file()
    hs.start('lab_room', orient=False)
    clay = hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0)
    dark = hs.mat('clay_dark', (0.03, 0.03, 0.03), 0.4, 0.0)
    shell.build(hs, K, clay, dark)
    furniture.build(hs, K, clay, dark)
    g = P.Garden(bounds=in_room)
    for sp, x, y in PLANTS:
        getattr(P, sp)(g, x, y, clay)
    P.watering_can(CAN[0], CAN[1], CAN[2], clay, toward=CAN[3])
    hs.sweep_tmp()
    bpy.data.collections.remove(hs.tmp)
    opened = [r[0] for r in hs.REPORT if r[1]]
    cr = crossings()
    L.log('lab high', f'{len(hs.col.objects)} parts; open-edged: {opened or "none"}; blades turned {g.turned}, still crossing {g.crossing}, '
                      f'torn skin edges {g.torn}; crossings {cr}')
    return cr


def main(out_dir):
    build()
    return L.save(os.path.join(out_dir, 'lab_high.blend'))
