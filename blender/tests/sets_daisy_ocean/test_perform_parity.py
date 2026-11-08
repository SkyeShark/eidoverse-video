"""Her gestures against perform.js itself: claude_suit's normalized rig (rest positions, humanoid parents) goes to deno,
where the untouched makePerformer runs handToFlower and lookAt on a three.js copy of that rig; the Blender port runs the
same calls on the imported VRM; the resulting normalized rotations must agree.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_perform_parity.py
"""
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.sets.daisy.ocean.perform import make_performer, _humanoid_parents, GESTURE_BONES  # noqa: E402

ck = C.Checks('perform')
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
me = load_vrm('claude_suit')
bpy.context.view_layer.update()
parents = _humanoid_parents(me)
rest = {n: me.rest_head[b] for n, b in me.humanoid.items()}
rig = {n: {'parent': parents[n], 'pos': [rest[n].x, rest[n].z, -rest[n].y]} for n in me.humanoid}   # three model axes
H = rest['head']
point_model = (0.45, H.z + 0.25, 0.9)                                 # three model space: front-left, above her eyes
point_world = tuple(me.arm.matrix_world @ Vector((point_model[0], -point_model[2], point_model[1])))
CASES = {
    'hand_right': {'call': 'hand', 'w': 1.0, 'opts': {'side': 'right', 'tilt': 0.16}},
    'hand_left_half': {'call': 'hand', 'w': 0.6, 'opts': {'side': 'left', 'reach': [0.02, 0.03, -0.01], 'curl': 0.3}},
    'look': {'call': 'look', 'w': 1.0, 'opts': {}},
    'look_clamped': {'call': 'look', 'w': 0.8, 'opts': {'maxYaw': 0.3, 'maxPitch': 0.1, 'neckShare': 0.35}},
}
ours = {}
for name, cs in CASES.items():
    me.zero_pose()
    bpy.context.view_layer.update()
    P = make_performer()
    o = cs['opts']
    if cs['call'] == 'hand':
        P.hand_to_flower(me, cs['w'], side=o['side'], reach=tuple(o.get('reach', (0, 0, 0))), tilt=o.get('tilt', 0.0),
                         curl=o.get('curl', 0.45))
    else:
        P.look_at(me, point_world, cs['w'], max_yaw=o.get('maxYaw', 1.1), max_pitch=o.get('maxPitch', 0.45),
                  neck_share=o.get('neckShare', 0.4))
    P.commit(me)
    bpy.context.view_layer.update()
    pose = me.read_pose()
    ours[name] = {n: [q.x, q.y, q.z, q.w] for n, q in pose.items() if n in GESTURE_BONES or n.startswith('left')}
src = os.path.join(C.OUT, 'perform_rig.json')
with open(src, 'w') as f:
    json.dump({'rig': rig, 'point': point_model, 'cases': CASES}, f)
dst = os.path.join(C.OUT, 'perform_js.json')
subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', os.path.join(C.HERE, 'perform_dump.mjs'), C.THREE_BUILD,
                src, dst], cwd=C.REPO, check=True)
with open(dst) as f:
    js = json.load(f)
for name in CASES:
    worst, which, n_cmp = -1.0, '', 0
    for n, q in js[name].items():
        if n not in ours[name]:
            continue
        b = ours[name][n]
        # the angle of q^-1 b, well conditioned (2 atan2(|v|, |w|); acos near 1 would turn float32 rounding of w into
        # a few hundredths of a degree)
        ax, ay, az, aw = -q[0], -q[1], -q[2], q[3]
        bx, by, bz, bw = b
        rx = ax * bw + aw * bx + ay * bz - az * by
        ry = ay * bw + aw * by + az * bx - ax * bz
        rz = az * bw + aw * bz + ax * by - ay * bx
        rw = aw * bw - ax * bx - ay * by - az * bz
        d = math.degrees(2 * math.atan2(math.sqrt(rx * rx + ry * ry + rz * rz), abs(rw)))
        n_cmp += 1
        if d > worst:
            worst, which = d, n
    moved = sum(1 for q in js[name].values() if abs(q[3]) < 0.99999)
    ck.check(f'{name}: normalized rotations = perform.js', n_cmp > 0 and worst < 0.05,
             f'{n_cmp} bones compared, worst {worst:.2e} deg ({which}), {moved} moved by the JS')
ck.summary()
with open(os.path.join(C.OUT, 'test_perform_parity.json'), 'w') as f:
    json.dump(ck.rows, f, indent=1)
