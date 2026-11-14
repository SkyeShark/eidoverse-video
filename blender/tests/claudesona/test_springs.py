"""Spring bones baked to keys, measured against the engine's own three-vrm (deno, CPU) on the same motion: the
character turns 90 deg and back while its head nods, 30 fps, from a cold start (preroll 0, as the engine starts).

For the claudesona (claude_suit.vrm at the films' 0.87, its 14 springs: tail, tie, 12 petals) and aletheia
(aletheia.vrm, 40 springs: hair, tail, coat skirt), each solver is baked and every joint's moving point (its child's
world position) compared with three-vrm's, frame by frame:
    solver='three' (the port)      must agree within 1 mm everywhere
    solver='addon' (the add-on's)  reported, and must agree within 10 mm (same maths, its own matrix path)
    rate=60 (the add-on's viewport schedule) is reported against the engine's one-step-per-frame, not judged.
The engine's tie limiter (render_scene.mjs's wrapper on vrm.update) is run in three-vrm too: it must leave every tail
exactly where the free springs put it (it is inert there: spring joints have matrixAutoUpdate off), which is why the
bake's default has no limiter. The limiter's intent (tie_limit_deg='engine') is checked on its own: the blade within
10 deg of down on every frame, and how far that pulls the tip back from the free tie.
Then the probe renders: the petals and the tie through the turn, and aletheia's hair and coat.

    out/springs_<who>.json, out/springs_<who>_sheet.png

    bash run_blender.sh blender/tests/claudesona/test_springs.py [--no-render] [--who claude_suit|aletheia]
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import json
import math
import os
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.springs import SpringRig, bake_springs  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
WHO = ARGS[ARGS.index('--who') + 1].split(',') if '--who' in ARGS else ['claude_suit', 'aletheia']
FPS = 30
DUR = 3.0
TURN = [[0.0, 0.0], [0.25, 0.0], [0.65, 90.0], [1.6, 90.0], [2.0, 0.0], [3.0, 0.0]]
NOD = [[0.0, 0.0], [0.9, 0.0], [1.1, 18.0], [1.3, -12.0], [1.5, 0.0], [3.0, 0.0]]
SCALE = {'claude_suit': 0.87, 'aletheia': 1.0}
if '--motion' in ARGS:                    # diagnosis: 'still' (gravity only), 'turn', 'nod' or 'both' (default)
    _m = ARGS[ARGS.index('--motion') + 1]
    if _m in ('still', 'nod'):
        TURN = [[0.0, 0.0], [3.0, 0.0]]
    if _m in ('still', 'turn'):
        NOD = [[0.0, 0.0], [3.0, 0.0]]
if '--scale' in ARGS:
    SCALE = {k: float(ARGS[ARGS.index('--scale') + 1]) for k in SCALE}


def log(*a):
    print('[springs]', *a, flush=True)


def key_motion(h, n):
    arm = h.arm
    arm.rotation_mode = 'XYZ'
    head = h.humanoid['head']
    pb = arm.pose.bones[head]
    pb.rotation_mode = 'QUATERNION'
    for i in range(n):
        f, t = 1 + i, i / FPS
        arm.rotation_euler = (0.0, 0.0, math.radians(S.lerp_keys(TURN, t)))
        arm.keyframe_insert('rotation_euler', index=2, frame=f)
        q3 = Quaternion((1.0, 0.0, 0.0), math.radians(S.lerp_keys(NOD, t)))
        h.write_pose({'head': q3})
        pb.keyframe_insert('rotation_quaternion', frame=f)
    from bpy_extras import anim_utils
    act = arm.animation_data.action
    cb = anim_utils.action_get_channelbag_for_slot(act, arm.animation_data.action_slot)
    for fc in cb.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def tails_blender(h, rig, frames):
    """per frame: each joint's child world position, three axes, read from the evaluated (keyed) pose"""
    sc = bpy.context.scene
    out = []
    for f in frames:
        sc.frame_set(f)
        mw = h.arm.matrix_world
        out.append({j.bone: S.to_three(mw @ h.arm.pose.bones[j.child].head) for j in rig.joints})
    return out


def compare(ref, bl, rig_names):
    """max / mean distance (mm) between three-vrm's tails and Blender's, matched by name"""
    names = [d['child'] or d['bone'] for d in ref['joints']]
    bones = [S.match_bone(d['bone'], rig_names) for d in ref['joints']]
    worst, tot, n, worst_at = 0.0, 0.0, 0, None
    missing = [d['bone'] for d, b in zip(ref['joints'], bones) if b is None]
    per_joint = {}
    for fi, row in enumerate(ref['tails']):
        for ji, p in enumerate(row):
            b = bones[ji]
            if b is None or b not in bl[fi]:
                continue
            q = bl[fi][b]
            d = 1000 * math.dist(p, q)
            per_joint[b] = max(per_joint.get(b, 0.0), d)
            tot += d
            n += 1
            if d > worst:
                worst, worst_at = d, (fi + 1, b)
    return {'max_mm': round(worst, 3), 'mean_mm': round(tot / max(1, n), 4), 'at': worst_at, 'n': n,
            'unmatched': missing, 'worst_joints': sorted(per_joint.items(), key=lambda kv: -kv[1])[:5], 'names': len(names),
            'per_joint': per_joint}


def odd_chains(h, rig):
    """the springs whose nodes carry non-uniform scale (> 0.1 %) or a zero-length joint (< 0.01 mm), from the file:
    {spring name: why}, and the Blender bones of their joints"""
    from eidoblend.characters.vrm import glb_json
    g = glb_json(h.path)
    nodes = g['nodes']
    out, bones = {}, set()
    for s, rs in zip(g['extensions']['VRMC_springBone']['springs'], rig.springs):
        ids = [jj['node'] for jj in s['joints']]
        why = []
        if any(max(abs(c - 1.0) for c in nodes[i].get('scale', (1, 1, 1))) > 1e-3 for i in ids):
            why.append('non-uniform node scale')
        if any(math.hypot(*nodes[b].get('translation', (0, 0, 0))) < 1e-5 for b in ids[1:]):
            why.append('a zero-length joint')
        if why:
            out[rs['name']] = ', '.join(why)
            bones.update(rs['joints'])
    return out, bones


def run(who, C, R):
    sc = S.clean_scene(FPS)
    sc.frame_start, sc.frame_end = 1, int(DUR * FPS)
    n = int(DUR * FPS)
    h = load_vrm(who)
    h.arm.scale = (SCALE[who],) * 3
    key_motion(h, n)
    rig = SpringRig(h)
    names = [b.name for b in h.arm.data.bones]
    has_tie = 'tie_1' in rig.by_bone
    job = {'vrm': h.path.replace('\\', '/'), 'scale': SCALE[who], 'fps': FPS, 'frames': n, 'turn': TURN, 'nod': NOD,
           'tie': None}
    t0 = time.time()
    ref = S.three_vrm(job, f'springs_{who}')
    R['three_vrm_s'] = round(time.time() - t0, 2)
    R['three_vrm_joints'] = len(ref['joints'])
    R['blender_joints'] = len(rig.joints)
    C.check(f'{who}: joint count matches three-vrm', len(ref['joints']) == len(rig.joints),
            f'three {len(ref["joints"])} / blender {len(rig.joints)}')
    if has_tie:                           # the engine's limiter, run in three-vrm: inert
        ref_lim = S.three_vrm(dict(job, tie=10.0), f'springs_{who}_enginelimiter')
        moved = max(math.dist(a, b) for ra, rb in zip(ref['tails'], ref_lim['tails']) for a, b in zip(ra, rb))
        R['engine_limiter_moved_mm'] = round(1000 * moved, 6)
        C.check(f"{who}: the engine's tie limiter is inert in three-vrm 3.5.2 (no tail moves)", moved < 1e-9,
                f'{1000 * moved:.6f} mm')
    frames = list(range(1, n + 1))
    res, tails = {}, {}
    for solver, rate, length in (('three', 'frame', 'engine'), ('three', 'frame', 'true'), ('addon', 'frame', 'true'),
                                 ('addon', 60, 'true')):
        t0 = time.time()
        rep = bake_springs(h, 1, n, solver=solver, rate=rate, preroll=0.0, length=length, log=log)
        bake_s = time.time() - t0
        bl = tails_blender(h, rig, frames)
        cmp = compare(ref, bl, names)
        rep.pop('spring_list', None)
        key = f'{solver}@{rate}/{length}'
        res[key], tails[key] = {'bake_s': round(bake_s, 2), 'report': rep, 'vs_three_vrm': cmp}, bl
        log(who, key, 'bake', round(bake_s, 2), 's; vs three-vrm', cmp['max_mm'], 'mm max', cmp['mean_mm'], 'mm mean', cmp['at'])
    eng, add = res['three@frame/engine'], res['addon@frame/true']
    C.check(f'{who}: every three-vrm joint has its Blender bone', not eng['vs_three_vrm']['unmatched'],
            str(eng['vs_three_vrm']['unmatched'][:3]))
    odd, odd_bones = odd_chains(h, rig)
    R['odd_chains'] = odd
    pj = eng['vs_three_vrm']['per_joint']
    plain = max([v for b, v in pj.items() if b not in odd_bones] or [0.0])
    oddmax = max([v for b, v in pj.items() if b in odd_bones] or [0.0])
    R['engine_parity_mm'] = {'plain_chains_max': round(plain, 4), 'odd_chains_max': round(oddmax, 3),
                             'mean': eng['vs_three_vrm']['mean_mm']}
    C.check(f"{who}: the bake (solver three, length engine) follows three-vrm within 1 mm on every plain chain",
            plain < 1.0, f'max {plain:.4f} mm over {len(pj) - len(odd_bones & set(pj))} joints x {n} frames')
    if odd:
        lengths = []
        for rs in rig.springs:
            if rs['name'] in odd:
                lengths.append(sum(rig.by_bone[b].child_local.length for b in rs['joints']) * SCALE[who])
        lim = 0.02 * 1000 * max(lengths)
        C.check(f"{who}: the chains with scaled nodes stay within 2 % of their length of three-vrm's",
                oddmax < lim, f'max {oddmax:.2f} mm (limit {lim:.1f} mm) on {len(odd)} chains: {sorted(set(odd.values()))}')
    # the port with the real length against the add-on's own step: the same physics, two implementations
    ta = [math.dist(tails['three@frame/true'][i][b], tails['addon@frame/true'][i][b])
          for i in range(len(frames)) for b in tails['addon@frame/true'][i] if b not in odd_bones]
    d_ta = max(ta)
    R['three_true_vs_addon_mm'] = round(1000 * d_ta, 4)
    C.check(f"{who}: the port with the real length matches the add-on's own step within 0.5 mm (plain chains)",
            1000 * d_ta < 0.5, f'{1000 * d_ta:.4f} mm')
    for v in res.values():
        v['vs_three_vrm'].pop('per_joint', None)
    R['solvers'] = res
    R['real_length_vs_three_vrm_mm'] = {'max': add['vs_three_vrm']['max_mm'], 'mean': add['vs_three_vrm']['mean_mm'],
                                       'at': add['vs_three_vrm']['at']}
    C.check(f'{who}: no NaN in any bake', all(v['report']['nan'] == 0 for v in res.values()))
    sw = eng['report']['swing_deg']
    C.check(f'{who}: the springs swing on the turn (a chain turns > 5 deg)', max(sw.values()) > 5.0,
            f'max {max(sw.values()):.1f} deg ({max(sw, key=sw.get)})')
    # the final bake for the renders: the port, from a settled start (preroll 1 s)
    rep = bake_springs(h, 1, n, solver='three', rate='frame', preroll=1.0, log=log)
    rep.pop('spring_list', None)
    R['final'] = rep
    if who == 'claude_suit':
        C.check('claude_suit: 14 springs (tail, tie, 12 petals)', rep['springs'] == 14, str(rep['springs']))

        def blade():
            out = []
            for f in frames:
                sc.frame_set(f)
                mw = h.arm.matrix_world
                a, b = mw @ h.arm.pose.bones['tie_1'].head, mw @ h.arm.pose.bones['tie_2'].head
                out.append((math.degrees((b - a).angle(Vector((0, 0, -1)))), b.copy()))
            return out
        free = blade()
        R['tie_blade_free_deg'] = [round(min(a for a, _ in free), 2), round(max(a for a, _ in free), 2)]
        # the limiter's intent, opt-in: the blade within 10 deg of down on every frame
        rep_l = bake_springs(h, 1, n, solver='three', rate='frame', preroll=1.0, tie_limit_deg='engine')
        lim = blade()
        worst = max(a for a, _ in lim)
        pull = max((p - q).length for (_a, p), (_b, q) in zip(free, lim))
        R['tie_limited'] = {'blade_max_deg': round(worst, 2), 'clamped_frames': rep_l['tie_clamped_frames'],
                            'tip_moved_mm_max': round(1000 * pull, 1)}
        C.check("claude_suit: tie_limit_deg='engine' keeps the blade within 10 deg of down", worst <= 10.05,
                f'{worst:.2f} deg (free {R["tie_blade_free_deg"]}); the tip moves up to {1000 * pull:.1f} mm')
        rep = bake_springs(h, 1, n, solver='three', rate='frame', preroll=1.0, log=log)     # back to the free tie
        rep.pop('spring_list', None)
        R['final'] = rep
    if who == 'aletheia':
        C.check('aletheia: 40 springs', rep['springs'] == 40, str(rep['springs']))
    if RENDER:
        render(who, h, R)
    sc.frame_set(1)
    return h


def render(who, h, R):
    sc = bpy.context.scene
    S.probe_render(sc, res=(640, 640), samples=16)
    S.studio_world(sc, 0.7, background=0x2c3038)
    S.sun('key', (2.2, 3.0, 3.2), 0xfff1e2, 2.4, angle_deg=3.0)
    S.sun('fill', (-3.0, 1.6, 2.4), 0xd8e4ff, 0.8, angle_deg=6.0)
    S.sun('rim', (-0.8, 2.8, -3.4), 0xffffff, 1.6, angle_deg=3.0)
    S.floor_disc(radius=3.0, colour=0x4a4e57, roughness=0.9)
    cam = S.camera('cam', lens=50)
    hh = (h.arm.matrix_world @ h.arm.pose.bones[h.humanoid['head']].head).z
    if who == 'claude_suit':           # the head and chest from a three-quarter view: the petals and the tie
        S.aim(cam, (1.25, -1.9, hh + 0.05), (0.0, 0.0, hh - 0.25))
    else:
        S.aim(cam, (1.6, -2.6, hh - 0.2), (0.0, 0.0, hh - 0.45))
    paths = []
    for f in (8, 16, 20, 24, 30, 45, 60, 75):
        p = os.path.join(S.OUT, f'springs_{who}_f{f:03d}.png')
        S.still(sc, cam, f, p)
        paths.append(p)
    R['stills'] = paths
    R['sheet'] = S.sheet(paths, os.path.join(S.OUT, f'springs_{who}_sheet.png'), cols=4)


R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
C = S.Checks('springs')
try:
    for who in WHO:
        R[who] = {}
        run(who, C, R[who])
except Exception:
    traceback.print_exc()
    R['error'] = traceback.format_exc()
    C.check('ran without an exception', False)
R['checks'] = C.rows
R['all_pass'] = C.all_pass and 'error' not in R
with open(os.path.join(S.OUT, 'springs.json'), 'w', encoding='utf-8') as f:
    json.dump(R, f, indent=1, default=str)
print('[springs] ALL PASS' if R['all_pass'] else '[springs] SOME FAILED', flush=True)
