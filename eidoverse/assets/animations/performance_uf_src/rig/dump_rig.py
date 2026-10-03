"""dump_rig.py — the rest geometry the clip checker tests hands against (UNKNOWN FORCE).

    bash run_blender.sh eidoverse/assets/animations/performance_uf_src/rig/dump_rig.py

Imports eidoverse/assets/vrms/claude_suit_wardrobe.vrm and writes eidoverse/assets/animations/performance_uf_src/rig/rig_points.npz:
for the petals (the 'flower' mesh) and the visible body surface (skin, tuta, boots, straps), every vertex in the
NORMALIZED frame (glTF metres: x = her left, y = up, z = toward the audience), its normal, and its four strongest
skin weights re-assigned to the nearest HUMANOID bone (petal springs and the tail ride their humanoid ancestor;
the springs are not simulated). check_vrma.py skins these with the .vrma's own FK (linear blend) and measures how
close the hands come to the petals and to the body. Also prints the mesh list and the bone tree once.
"""
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = HERE
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
VRM = os.path.join(REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe.vrm')
OUT = os.path.join(HERE, 'rig_points.npz')

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
bpy.ops.import_scene.vrm(filepath=VRM)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
ext = arm.data.vrm_addon_extension.vrm1
ext.humanoid.pose = 'restPositionPose'
human = {}
for name, h in ext.humanoid.human_bones.human_bone_name_to_human_bone().items():
    bn = h.node.bone_name
    if bn and bn in arm.data.bones:
        human[bn] = name.value
print('[dump] humanoid bones:', len(human))


def anc(bn):
    b = arm.data.bones.get(bn)
    while b is not None and b.name not in human:
        b = b.parent
    return human[b.name] if b is not None else None


for b in arm.data.bones:
    if b.name not in human:
        print(f"[dump] bone {b.name!r:28s} parent {b.parent.name if b.parent else None!r:24s} -> humanoid {anc(b.name)}")

AW = arm.matrix_world.inverted()


def to_n(v):            # Blender armature space -> normalized (glTF) frame
    return (v.x, v.z, -v.y)


HUMAN_ORDER = sorted(set(human.values()))
HIDX = {h: i for i, h in enumerate(HUMAN_ORDER)}
rows = {}
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    me = o.data
    vis = not o.hide_get() and not o.hide_render
    print(f"[dump] mesh {o.name!r:26s} v {len(me.vertices):6d}  hidden_vp {o.hide_get()}  hidden_render {o.hide_render}  parent {o.parent.name if o.parent else None}/{o.parent_bone}")
    M = AW @ o.matrix_world
    R = M.to_3x3()
    gname = {g.index: g.name for g in o.vertex_groups}
    pos, nor, wi, ww = [], [], [], []
    for v in me.vertices:
        p = M @ v.co
        n = (R @ v.normal).normalized()
        acc = {}
        for g in v.groups:
            h = anc(gname.get(g.group, ''))
            if h is not None and g.weight > 1e-4:
                acc[h] = acc.get(h, 0.0) + g.weight
        if not acc and o.parent_bone:
            acc = {anc(o.parent_bone): 1.0}
        if not acc:
            continue
        top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
        s = sum(w for _, w in top)
        idx = [HIDX[h] for h, _ in top] + [0] * (4 - len(top))
        wts = [w / s for _, w in top] + [0.0] * (4 - len(top))
        pos.append(to_n(p)); nor.append(to_n(n)); wi.append(idx); ww.append(wts)
    if pos:
        rows[o.name] = dict(pos=np.array(pos, np.float32), nor=np.array(nor, np.float32),
                            wi=np.array(wi, np.int16), ww=np.array(ww, np.float32), vis=vis)

out = {'human_names': np.array(HUMAN_ORDER)}
for name, r in rows.items():
    key = name.replace(' ', '_').replace('.', '_')
    for k in ('pos', 'nor', 'wi', 'ww'):
        out[f'{key}__{k}'] = r[k]
    out[f'{key}__vis'] = np.array([r['vis']])
np.savez_compressed(OUT, **out)
print('[dump] wrote', OUT, 'meshes:', ', '.join(f"{k}({len(v['pos'])}{'' if v['vis'] else ',hidden'})" for k, v in rows.items()))
