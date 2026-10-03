"""Where does digi's tail leave the tuta? (rest pose) The grommet in eidoverse/claudesona_wardrobe.js (TAIL_EXIT) and the belt's
tail port in build_tuta.py are seated from this.

    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/measure_tail_exit.py      # after build_tuta.py (it reads work/claude_suit_wardrobe_tuta.blend)

The tail-weighted vertices of BodyActual all lie OUTSIDE the cloth: the tail's root is weighted to the hips. So the
tail island is grown across edges from them into its root, every vertex is classed inside / outside the tuta, and the
tube's first centimetres outside the cloth give its axis, which is followed back into the cloth: that hit is the exit.
(Measured 2026-10-02: x 0, z 0.958 Blender = glTF (0, 0.958, -0.077), right on the belt line.)
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
bpy.ops.wm.open_mainfile(filepath=os.path.join(REPO, 'work', 'claude_suit_wardrobe_tuta.blend'))

body = bpy.data.objects['BodyActual']
tuta = bpy.data.objects['tuta']
for o in (body, tuta):                                   # the rest pose
    for md in o.modifiers:
        if md.type == 'ARMATURE':
            md.show_viewport = False
dg = bpy.context.evaluated_depsgraph_get()
te = tuta.evaluated_get(dg).to_mesh()
bvh = BVHTree.FromPolygons([tuta.matrix_world @ v.co for v in te.vertices], [tuple(p.vertices) for p in te.polygons])
me = body.data
W = body.matrix_world
names = {g.index: g.name for g in body.vertex_groups}
tail = {v.index for v in me.vertices if v.groups and names[max(v.groups, key=lambda g: g.weight).group].lower().startswith('tail')}
arm = bpy.data.objects['Armature']
root = arm.matrix_world @ arm.data.bones['tail_2'].head_local
adj = {}
for e in me.edges:
    a, b = e.vertices
    adj.setdefault(a, []).append(b)
    adj.setdefault(b, []).append(a)
front, island = list(tail), set(tail)                    # grow into the root, behind the body's mid plane, near the tail
while front:
    nxt = []
    for i in front:
        for j in adj.get(i, []):
            if j not in island and ((W @ me.vertices[j].co) - root).length < 0.36 and (W @ me.vertices[j].co).y > -0.02:
                island.add(j)
                nxt.append(j)
    front = nxt


def outside(p):
    hit, nrm, _, _ = bvh.find_nearest(p)
    return hit is None or (p - hit).dot(nrm) > 0


near = []
for i in island:
    p = W @ me.vertices[i].co
    if outside(p) and abs(p.x) < 0.06 and 0.75 < p.z < 1.0:
        d = bvh.find_nearest(p)[3]
        if d < 0.06:
            near.append((d, p))
bands = {}
for d, p in near:
    bands.setdefault(int(d / 0.01), []).append(p)
cents = [sum(bands[k], Vector()) / len(bands[k]) for k in sorted(bands)]
for k, c in zip(sorted(bands), cents):
    print(f'[tail] {k}-{k + 1} cm outside the cloth: {len(bands[k])} verts, centre {tuple(round(x, 4) for x in c)}')
axis = (cents[-1] - cents[0]).normalized()               # outward along the tail
hit, nrm, _, _ = bvh.ray_cast(cents[0] + axis * 0.002, -axis)
print('[tail] axis (blender)', tuple(round(x, 3) for x in axis))
print('[tail] EXIT (blender)', tuple(round(x, 4) for x in hit), '-> glTF', (round(hit.x, 4), round(hit.z, 4), round(-hit.y, 4)))
