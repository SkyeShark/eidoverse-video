"""Where do the petals hide the suit? Front-view ASCII map (T-pose) of the shirt/pants with petal cover marked.
'#' = suit visible, 'p' = suit behind a petal, '.' = no suit. Used to place the modificanti where they read.

    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/probe_petals.py
"""
import os

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = HERE
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
bpy.ops.wm.open_mainfile(filepath=os.path.join(REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe_src', 'claude_suit_wardrobe.blend'))


def bvh(names):
    verts, polys = [], []
    for n in names:
        o = bpy.data.objects[n]
        dg = bpy.context.evaluated_depsgraph_get()
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        W = o.matrix_world
        base = len(verts)
        verts += [W @ v.co for v in me.vertices]
        polys += [tuple(base + i for i in p.vertices) for p in me.polygons]
        oe.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


suit = bvh(['shirt', 'pants'])
pet = bvh(['flower'])
face = bvh(['face', 'Body'])
for title, xs, zs in (('chest+belly (front view, x -0.30..0.30, z 1.42..0.90)', [i * 0.02 - 0.30 for i in range(31)], [1.42 - j * 0.02 for j in range(27)]),
                      ('shoulders+arms (x -0.78..0.78, z 1.44..1.24)', [i * 0.03 - 0.78 for i in range(53)], [1.44 - j * 0.02 for j in range(11)])):
    print('[pet]', title)
    for z in zs:
        row = ''
        for x in xs:
            o = Vector((x, -1.0, z))
            d = Vector((0, 1, 0))
            hs = suit.ray_cast(o, d)
            hp = pet.ray_cast(o, d)
            hf = face.ray_cast(o, d)
            if hs[0] is None:
                row += '.'
            elif (hp[0] is not None and hp[0].y < hs[0].y) or (hf[0] is not None and hf[0].y < hs[0].y):
                row += 'p'
            else:
                row += '#'
        print(f'[pet] z {z:5.2f} {row}')
# T-pose top-of-arm view (looking down -z): is the top of the upper arm under a petal?
print('[pet] arm tops seen from above (x -0.78..0.78, y -0.10..0.10)')
for y in [-0.10 + j * 0.02 for j in range(11)]:
    row = ''
    for x in [i * 0.03 - 0.78 for i in range(53)]:
        o = Vector((x, y, 2.5))
        d = Vector((0, 0, -1))
        hs = suit.ray_cast(o, d)
        hp = pet.ray_cast(o, d)
        if hs[0] is None:
            row += '.'
        elif hp[0] is not None and hp[0].z > hs[0].z:
            row += 'p'
        else:
            row += '#'
    print(f'[pet] y {y:5.2f} {row}')
