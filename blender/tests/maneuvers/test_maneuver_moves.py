"""The controller's parkour moves on simple geometry built for each, aimed by eidoblend.characters.maneuvers, each take at
a different heading (the axes of the original are three's; these runs turn every move off the course's one axis):

    test_maneuver_moves.py [--vrm aletheia] [--tag NAME] [--only parkour,ladder,...]

    parkour  heading 35 deg: vault_over a 0.55 m cover; climb_onto a 1.2 m block (climbLedge); across its top and off
             its far edge (a 1.2 m drop: fallIdle, then fallLand)
    ladder   heading -60 deg: climb_ladder up a 2.6 m wall's rungs (built 0.30 m apart from 0.30 m: measured off the
             geometry), the mantle over its top
    scramble heading 120 deg: scramble_up a 3.2 m wall (climbWall at rate 0.45, timeScale 1.25: not the defaults), the
             mantle over its top
    wall     heading 160 deg: climb_onto a 2.0 m wall (over mountMaxRise: the climbWallUp route, the climbLedge clip)
    run      heading 90 deg over a trench: cross a 0.85 m cover running (the auto-trigger's vault), run over the
             1.2 m trench (the auto-trigger's gap jump), turn back, jump_across it from standing (jump: height 0.5)
    gestures heading 0: walk with 'talk' over the gait (playGesture at 2.5), stopGesture; run with 'cheer' at 4.0; walk
             with a one-shot 'raise'

Prints PASS / FAIL per take: every move plays as the controller names it; the contacts the moves hold (the vault's
prop hand on the cover top, the mount's hands on the lip and feet on the top, the ladder's hands and boots on the
rungs, the scramble ending on top, the jumps landing beyond the trench, the drop's fallLand); no visible boot inside
any solid (FootMesh, rungs included); checks.feet on the walking and running stretches; the gestures' weights while
the legs walk; the keyed armature against the bake. Stills: a strip of each move and contact close-ups.
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _mnv_stage as T  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402
from eidoblend.characters import maneuvers as MV  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aletheia')
R = T.Report(T.arg(ARGS, '--tag', f'maneuver_moves_{VRM}'))
R['vrm'] = VRM
ONLY = set((T.arg(ARGS, '--only') or 'parkour,ladder,scramble,wall,run,gestures').split(','))
D2R = math.pi / 180.0


def slab(name, x0, x1, y0, y1, top=0.0, thick=1.0, mat='ground'):
    return T.box(name, ((x0 + x1) / 2, (y0 + y1) / 2, top - thick / 2), (x1 - x0, y1 - y0, thick), mat, role='ground')


def fwd(h):
    return Vector((math.sin(h), -math.cos(h), 0.0))


def at(o, h, d):
    p = Vector((o[0], o[1], 0.0)) + fwd(h) * d
    return (p.x, p.y)


def build():
    sc = T.S.clean_scene(fps=30)
    # the ground: one slab, and the run's trench region (two slabs with a 1.2 m trench between, 1 m deep, its bottom)
    slab('floor', -14, 14, -14, 9)
    slab('run_before', -14, 14, 9, 14)
    slab('run_after', -14, 14, 15.2, 22)
    slab('trench_bottom', -14, 14, 14, 15.2, top=-1.0)
    G = {}
    if 'parkour' in ONLY:
        h, o = 35 * D2R, (-6.0, 4.0)
        G['parkour'] = {'h': h, 'o': o,
                        'cover': T.obstacle('pk_cover', at(o, h, 2.6), h, 0.55, 0.5, width=1.6),
                        'block': T.obstacle('pk_block', at(o, h, 6.0), h, 1.2, 1.6, width=2.0)}
    if 'ladder' in ONLY:
        h, o = -60 * D2R, (7.0, -6.0)
        wall, rails, rungs = T.ladder('ld', at(o, h, 2.4), h, 2.6, first_rung=0.30, rung_spacing=0.30, wall_depth=1.6)
        G['ladder'] = {'h': h, 'o': o, 'wall': wall, 'rails': rails, 'rungs': rungs}
    if 'scramble' in ONLY:
        h, o = 120 * D2R, (-7.0, -6.0)
        G['scramble'] = {'h': h, 'o': o, 'wall': T.obstacle('sc_wall', at(o, h, 2.4), h, 3.2, 1.8, width=2.4)}
    if 'wall' in ONLY:
        h, o = 160 * D2R, (0.5, -9.0)
        G['wall'] = {'h': h, 'o': o, 'wall': T.obstacle('wl_wall', at(o, h, 2.2), h, 2.0, 1.8, width=2.4)}
    if 'run' in ONLY:
        h, o = math.pi, (-3.0, 3.0)                  # heading pi: +Y, toward the trench at y 14 .. 15.2
        G['run'] = {'h': h, 'o': o, 'cover': T.obstacle('rn_cover', (o[0], 7.0), h, 0.85, 0.6, width=1.6),
                    'landing': bpy.data.objects['run_after'], 'takeoff': bpy.data.objects['run_before']}
    if 'gestures' in ONLY:
        G['gestures'] = {'h': 0.0, 'o': (10.0, 6.0)}
    T.scene_camera((0.0, -20.0, 8.0), (0.0, 0.0, 0.0))
    return sc, G


def runs(recs, key):
    out = []
    for r in recs:
        v = key(r)
        if v and out and out[-1][0] == v and out[-1][2] == r['f'] - 1:
            out[-1][2] = r['f']
        elif v:
            out.append([v, r['f'], r['f']])
    return out


def bone(me, n):
    return T.bone_world(me, n)


def take(name, me, G, direct, world=None, contact_world=None):
    """one Locomotion take: directed by `direct(loco)`, baked into its own action -> (rep, action name)"""
    g = G[name]
    T.at_rest(me)                                  # the new controller measures the body at rest, not the last take
    loco = Locomotion(me, world or CollisionWorld(), start=(g['o'][0], g['o'][1], 0.0), heading=g['h'], log=R.log,
                      controller_opts={'contact_world': contact_world} if contact_world is not None else None)
    direct(loco, g)
    t0 = time.time()
    act = f'{me.name}|take_{name}'               # not '|run': the clip library names its clips' actions '<vrm>|<slot>'
    rep = loco.bake(f0=1, action_name=act)
    bpy.data.actions[act].use_fake_user = True  # every take's action survives the save (the shots name each)
    R['timing_s'][f'bake_{name}'] = round(time.time() - t0, 1)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = rep['frames_baked']
    man = runs(rep['_records'], lambda r: r['maneuver'] if r['mode'] == 'maneuver' else None)
    R[f'{name}_maneuvers'] = [(m, a, b) for m, a, b in man]
    R[f'{name}_segments'] = rep['segments']
    R.log(f'{name}: maneuvers {[(m, a, b) for m, a, b in man]}')
    return rep, act, man


def common(name, me, rep, skip=None):
    T.gait_checks(R, rep)
    f0, f1 = rep['frames_baked']
    T.mesh_feet_check(R, me, f0, f1, step=3, limit_mm=12.0, label=f'{name}: the whole take', skip=skip)
    R[f'{name}_feet_over_limit'] = R['mesh_feet_over_limit']
    T.keyed_matches(R, me, rep['_frames'])


def boots_low(me, f):
    """the visible boots (FootMesh) at frame f: {side: (lowest z, the mean xy of its points within 1 cm of that)}"""
    out = {}
    for s, v in T.FootMesh(me).at(f).items():
        P = v['P']
        low = P[P[:, 2] < v['zmin'] + 0.01]
        out[s] = (v['zmin'], low[:, :2].mean(axis=0))
    return out


# ------------------------------------------------------------------------------------------------ the takes
def t_parkour(me, G, S, sheets):
    g = G['parkour']
    h, o = g['h'], g['o']

    def direct(loco, g):
        loco.wait(0.4)
        MV.vault_over(loco, g['cover'])
        loco.move_to(at(o, h, 4.8), gait='walk')
        MV.climb_onto(loco, g['block'])
        loco.move_to(at(o, h, 9.6), gait='walk')               # across the top and off its far edge (1.2 m down)
        loco.wait(0.6)
    rep, act, man = take('parkour', me, G, direct)
    kinds = [m for m, _a, _b in man]
    R.check('parkour: the vault, the mount and the drop\'s landing play', 'vault' in kinds and 'mount' in kinds and
            'land' in kinds, f'{man}')
    recs = rep['_records']
    sc = bpy.context.scene
    cov = g['cover']
    top = cov.location.z + cov.dimensions.z / 2
    v = next(((a, b) for m, a, b in man if m == 'vault'), None)
    if v:
        best, peak = 9.0, -9.0
        for f in range(v[0], v[1] + 1):
            sc.frame_set(f)
            peak = max(peak, bone(me, 'hips').z)
            for s in ('left', 'right'):
                hp = bone(me, s + 'Hand')
                loc = cov.matrix_world.inverted() @ hp
                if abs(loc.x) < 0.8 and abs(loc.y) < 0.4:
                    best = min(best, abs(hp.z - top))
        R.check('parkour: the vault\'s prop hand comes onto the cover\'s top (its wrist within 6 cm of it)', best < 0.06,
                f'{best * 100:.1f} cm')
        R.check('parkour: the hips pass over the cover (peak over its top)', peak > top + 0.1,
                f'peak {peak:.2f} m, top {top:.2f} m')
    m = next(((a, b) for k, a, b in man if k == 'mount'), None)
    blk = g['block']
    btop = blk.location.z + blk.dimensions.z / 2
    if m:
        hands = 9.0
        for f in range(m[0], m[1] + 1):
            sc.frame_set(f)
            for s in ('left', 'right'):
                hp = bone(me, s + 'Hand')
                hands = min(hands, abs(hp.z - btop) if (blk.matrix_world.inverted() @ hp).y > -0.9 else 9.0)
        R.check('parkour: the mount\'s hands come onto the block\'s lip (a wrist within 5 cm of its top)', hands < 0.05,
                f'{hands * 100:.1f} cm')
        lows = [z - btop for z, _xy in boots_low(me, m[1] + 4).values()]
        R.check('parkour: the mount ends with both boots on the block\'s top (within -1 / +3 cm, 4 frames on)',
                all(-0.01 < z < 0.03 for z in lows), f'{[round(z * 100, 1) for z in lows]} cm')
    falls = [r['f'] for r in recs if not r['grounded']]
    R.check('parkour: off the block\'s far edge: airborne (fallIdle) before the landing', len(falls) >= 4,
            f'{len(falls)} airborne frames')
    common('parkour', me, rep)
    lo, hi = rep['frames_baked']
    T.strip(S, sheets, me, recs, 'parkour_vault', [v[0] - 6 + int((v[1] - v[0] + 12) * k / 7) for k in range(8)]
            if v else [], dist=3.6)
    T.strip(S, sheets, me, recs, 'parkour_mount', [m[0] - 4 + int((m[1] - m[0] + 8) * k / 7) for k in range(8)]
            if m else [], dist=4.2)
    land = next(((a, b) for k, a, b in man if k == 'land'), None)
    if land:
        T.strip(S, sheets, me, recs, 'parkour_drop', [land[0] - 14 + 4 * k for k in range(8)], dist=4.4)
    for s in S:
        s.setdefault('action', act)


def t_ladder(me, G, S, sheets):
    g = G['ladder']
    fixtures = g['rails'] + g['rungs']

    def direct(loco, g):
        loco.wait(0.4)
        MV.climb_ladder(loco, g['rungs'], g['wall'])
        loco.move_to(at(g['o'], g['h'], 3.6), gait='walk')
        loco.wait(0.4)
    lad = MV.measure_ladder(g['rungs'], g['wall'])
    R['ladder_measured'] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in lad.items()
                            if k in ('first_rung', 'rung_spacing', 'height', 'width', 'wall_gap')}
    R.check('ladder: its rungs measured off the geometry as built (first 0.30, every 0.30, the wall 2.6 m)',
            abs(lad['first_rung'] - 0.30) < 0.005 and abs(lad['rung_spacing'] - 0.30) < 0.005 and
            abs(lad['height'] - 2.6) < 0.01, f"{R['ladder_measured']}")
    rep, act, man = take('ladder', me, G, direct, world=CollisionWorld(exclude=fixtures), contact_world=CollisionWorld())
    kinds = [m for m, _a, _b in man]
    R.check('ladder: the climb and its mantle play (ladder, then mount)', 'ladder' in kinds and 'mount' in kinds,
            f'{man}')
    l = next(((a, b) for k, a, b in man if k == 'ladder'), None)
    sc = bpy.context.scene
    zs = lad['rungs']
    line, nrm = lad['line'], lad['normal']
    if l:
        n_h = n_f = n = 0
        span = range(l[0] + int(0.15 * (l[1] - l[0])), l[1] - 3, 3)
        fm = T.FootMesh(me)
        for f in span:
            sc.frame_set(f)
            n += 1
            got = 0
            for s in ('left', 'right'):
                hp = bone(me, s + 'Hand')
                d_line = abs((hp - line).dot(nrm))
                d_rung = min(abs(hp.z - z) for z in zs)
                got += math.hypot(d_line, d_rung) < 0.07
            n_h += got > 0
            got = 0
            for s, v in fm.at(f).items():
                P = v['P']
                near = P[np.abs((P[:, :2] - np.array(line.xy)) @ np.array(nrm.xy)) < 0.06]
                if len(near) and min(abs(float(near[:, 2].min()) - (z + 0.028)) for z in zs) < 0.025:
                    got += 1
            n_f += got > 0
        R['ladder_contact'] = {'frames': n, 'a_hand_on_a_rung': n_h, 'a_boot_on_a_rung': n_f}
        R.check('ladder: a hand grips a rung through the climb (a wrist within 7 cm of one in 70 % of its frames; the '
                'other reaches)', n and n_h / n >= 0.7, f'{n_h} of {n}')
        R.check('ladder: a boot stands on a rung through the climb (a sole on a rung\'s top within 2.5 cm in 70 % of '
                'its frames)', n and n_f / n >= 0.7, f'{n_f} of {n}')
    common('ladder', me, rep)
    recs = rep['_records']
    if l:
        # three-quarters from the front of the ladder, the whole wall in frame (a side shot looked along the wall's face
        # and lost her behind it)
        al = Vector((lad['along'].x, lad['along'].y, 0.0))
        pos = line + nrm * 3.6 + al * 2.2 + Vector((0.0, 0.0, 1.7))
        T.strip(S, sheets, me, recs, 'ladder', [l[0] + int((l[1] - l[0] + 40) * k / 9) for k in range(10)],
                at=(pos, line + Vector((0.0, 0.0, 1.45))), lens=26)
        mid = (l[0] + l[1]) // 2
        c3 = line + nrm * 1.3 + Vector((lad['along'].x, lad['along'].y, 0.0)) * 0.9 + Vector((0, 0, 1.4))
        S.append(T.fixed_shot('ladder_close', mid, c3, line + Vector((0, 0, 1.1)), lens=32))
    for s in S:
        s.setdefault('action', act)


def t_scramble(me, G, S, sheets):
    g = G['scramble']

    def direct(loco, g):
        loco.wait(0.4)
        MV.scramble_up(loco, g['wall'], rate=0.45, time_scale=1.25)
        loco.move_to(at(g['o'], g['h'], 3.3), gait='walk')
        loco.wait(0.4)
    rep, act, man = take('scramble', me, G, direct)
    kinds = [m for m, _a, _b in man]
    R.check('scramble: the wall scramble and its mantle play (wallScramble, then mount)',
            'wallScramble' in kinds and 'mount' in kinds, f'{man}')
    recs = rep['_records']
    w = g['wall']
    top = w.location.z + w.dimensions.z / 2
    lows = [z - top for z, _xy in boots_low(me, recs[-1]['f']).values()]
    R.check('scramble: she ends standing on the 3.2 m wall\'s top (both boots within -1 / +2 cm of it)',
            all(-0.01 < z < 0.02 for z in lows), f'{[round(z * 100, 1) for z in lows]} cm')
    common('scramble', me, rep)
    s_ = next(((a, b) for k, a, b in man if k == 'wallScramble'), None)
    m_ = next(((a, b) for k, a, b in man if k == 'mount'), None)
    if s_ and m_:
        # the whole 3.2 m wall in frame, from its front and to one side (the top's mantle included)
        h_ = g['h']
        face = Vector((*at(g['o'], h_, 2.4), 0.0))
        f_, r_ = fwd(h_), Vector((math.cos(h_), math.sin(h_), 0.0))
        T.strip(S, sheets, me, recs, 'scramble', [s_[0] + int((m_[1] + 20 - s_[0]) * k / 9) for k in range(10)],
                at=(face - f_ * 5.2 + r_ * 2.6 + Vector((0.0, 0.0, 2.3)), face + Vector((0.0, 0.0, 1.75))), lens=26)
    for s in S:
        s.setdefault('action', act)


def t_wall(me, G, S, sheets):
    g = G['wall']

    def direct(loco, g):
        loco.wait(0.4)
        MV.climb_onto(loco, g['wall'])
        loco.wait(0.6)
    rep, act, man = take('wall', me, G, direct)
    kinds = [m for m, _a, _b in man]
    R.check('wall: a 2.0 m wall is mounted (the climbWallUp route: mount)', kinds == ['mount'], f'{man}')
    recs = rep['_records']
    w = g['wall']
    top = w.location.z + w.dimensions.z / 2
    lows = [z - top for z, _xy in boots_low(me, recs[-1]['f']).values()]
    R.check('wall: she ends standing on its top (both boots within -1 / +2 cm of it)',
            all(-0.01 < z < 0.02 for z in lows), f'{[round(z * 100, 1) for z in lows]} cm')
    common('wall', me, rep)
    m_ = next(((a, b) for k, a, b in man if k == 'mount'), None)
    if m_:
        T.strip(S, sheets, me, recs, 'wall', [m_[0] + int((m_[1] - m_[0]) * k / 7) for k in range(8)], dist=4.2,
                height=0.8)
    for s in S:
        s.setdefault('action', act)


def t_run(me, G, S, sheets):
    g = G['run']
    o = g['o']

    def direct(loco, g):
        loco.wait(0.4)
        MV.cross(loco, g['cover'], beyond=3.0, gait='run')        # the auto-trigger's vault, running
        loco.follow_path([(o[0], 18.5)], gait='run')              # over the trench: the auto gap jump
        loco.turn_to(0.0)                                         # back toward it (heading 0: -Y)
        MV.jump_across(loco, g['takeoff'], height=0.5)            # from standing, the measured distance
        loco.wait(0.6)
    rep, act, man = take('run', me, G, direct)
    kinds = [m for m, _a, _b in man]
    R.check('run: the running vault and two jumps (the auto gap jump, then jump_across) play',
            kinds.count('vault') >= 1 and kinds.count('jump') >= 2, f'{man}')
    recs = rep['_records']
    jumps = [(a, b) for k, a, b in man if k == 'jump']
    if len(jumps) >= 2:
        # each boot touches down on the far side within ten frames of the jump's end (the walk on lifts one again)
        down = {}
        for f in range(jumps[0][1], jumps[0][1] + 11):
            for s, (z, xy) in boots_low(me, f).items():
                if s not in down or abs(z) < abs(down[s][0]):
                    down[s] = (z, xy)
        R.check('run: the gap jump lands beyond the trench (both boots down on the far side\'s top, y over 15.2)',
                len(down) == 2 and all(xy[1] > 15.25 and abs(z) < 0.02 for z, xy in down.values()),
                f'{[(round(z * 100, 1), round(float(xy[1]), 2)) for z, xy in down.values()]} (cm, y)')
        b2 = boots_low(me, recs[-1]['f'])
        R.check('run: jump_across lands back before the trench (both boots on its top, y under 14)',
                all(xy[1] < 13.95 and abs(z) < 0.02 for z, xy in b2.values()),
                f'{[(round(z * 100, 1), round(float(xy[1]), 2)) for z, xy in b2.values()]} (cm, y)')
    common('run', me, rep)
    v_ = next(((a, b) for k, a, b in man if k == 'vault'), None)
    if v_:
        T.strip(S, sheets, me, recs, 'run_vault', [v_[0] - 8 + int((v_[1] - v_[0] + 16) * k / 7) for k in range(8)],
                dist=4.4)
    for i, j in enumerate(jumps[:2]):
        T.strip(S, sheets, me, recs, f'run_jump{i}', [j[0] - 6 + int((j[1] - j[0] + 12) * k / 7) for k in range(8)],
                dist=4.6)
    for s in S:
        s.setdefault('action', act)


def t_gestures(me, G, S, sheets):
    g = G['gestures']
    o = g['o']

    def direct(loco, g):
        loco.wait(0.4)
        loco.gesture('talk', weight=2.5)
        loco.follow_path([(o[0], o[1] - 4.0)], gait='walk', stop=False)
        loco.stop_gesture()
        loco.follow_path([(o[0], o[1] - 6.0)], gait='walk', stop=False)
        loco.gesture('cheer', weight=4.0)
        loco.follow_path([(o[0], o[1] - 14.0)], gait='run', stop=False)
        loco.stop_gesture()
        loco.follow_path([(o[0], o[1] - 16.5)], gait='walk', stop=False)
        loco.gesture('raise', weight=2.5, loop=False)
        loco.follow_path([(o[0], o[1] - 19.0)], gait='walk')
        loco.wait(0.5)
    rep, act, man = take('gestures', me, G, direct)
    recs = rep['_records']
    for slot, w, gait in (('talk', 2.5, 'walk'), ('cheer', 4.0, 'run'), ('raise', 2.5, 'walk')):
        ws = [r['weights'].get(slot, 0.0) for r in recs if r['mode'] == 'loco' and r['lead'] == gait]
        top = max(ws) if ws else 0.0
        R.check(f"gestures: '{slot}' rides over the {gait} (its weight reaches {w * 0.9:.2f} while the {gait} leads)",
                top >= w * 0.9, f'max {top:.2f}')
    common('gestures', me, rep)
    for slot in ('talk', 'cheer', 'raise'):
        fs = [r['f'] for r in recs if r['weights'].get(slot, 0.0) > 1.0]
        if fs:
            T.strip(S, sheets, me, recs, f'gesture_{slot}', [fs[len(fs) // 3] + 3 * k for k in range(6)], dist=3.4)
    for s in S:
        s.setdefault('action', act)


def main():
    sc, G = build()
    me = load_vrm(VRM, name=VRM)
    shots, sheets = [], {}
    for name, fn in (('parkour', t_parkour), ('ladder', t_ladder), ('scramble', t_scramble), ('wall', t_wall),
                     ('run', t_run), ('gestures', t_gestures)):
        if name not in ONLY:
            continue
        S = []
        try:
            fn(me, G, S, sheets)
        except Exception:  # noqa: BLE001 - one take's failure must not stop the others
            traceback.print_exc()
            R.check(f'{name}: the take ran to the end', False, 'an exception (above)')
        shots += S
    T.light(sc)
    T.save(R, sc, shots, sheets)


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
