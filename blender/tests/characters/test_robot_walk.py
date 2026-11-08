"""The characters family's first probe: me (claude_robot.vrm, my robot body) walking across uneven ground, the crown open
and a happy face, feet planted. Builds the scene, walks it (locomotion.walk_path), checks it (checks.py: on the walk's
result, the feet's points where Blender's skinned mesh puts them), saves out/robot_walk.blend and renders probe stills:

    out/<tag>_side_f<NNN>.png        a camera beside the path, following me (full body, 50 mm)
    out/<tag>_wide_f<NNN>.png        the whole walk from one fixed camera further out: the start, the middle and the end
    out/<tag>_gait_<k>_f<NNN>.png    one gait cycle in 8 frames, the side camera following
    out/<tag>_face_f<NNN>.png        a close-up of my face (85 mm, three-quarter front)
    out/<tag>_feet_right_f<NNN>.png  a fixed low camera on one planted foot through its stance (it must not move)
    out/<tag>_swing<k>_f<NNN>.png    a fixed low camera on a whole right swing, lift to landing (it must clear the ground:
                                     the swings over the mound and over the rolls before it, where the verifier saw drags)
    out/<tag>_double_f<NNN>.png      both feet down in a double support, low and close
    out/<tag>_front_f<NNN>.png       from in front
    out/<tag>.json                   the walk's report, the checks, the timings

    --path bend    the verifier's 45 deg bend, (0,-6) -> (4,-6) -> (6.83,-3.17), tag robot_walk_bend: instead of the
                   straight walk's stills, a fixed camera on the corner, a following one, and a low one on my outer
                   (right) foot through its stance in the turn
    --speed 0.9    a slower walk (tag robot_walk_slow; side stills and a planted foot)
    --tag NAME     the outputs' prefix;  --flat  a level floor;  --no-render  build, walk, check (and save) only;
    --no-save      no .blend;  --vrm claude_robot_2k   the 2K-texture body (faster to load)

Run (from the main checkout, through the shared GPU slot):
    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/characters/test_robot_walk.py [-- args]
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
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import Ground, key_expression, load_clip, load_vrm, walk_path  # noqa: E402
from eidoblend.characters import checks  # noqa: E402
from eidoblend.characters.locomotion import Body  # noqa: E402

ARGS = S.argv()


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


RENDER = '--no-render' not in ARGS
VRM = arg('--vrm', 'claude_robot')
PATH = arg('--path', 'straight')
SPEED = float(arg('--speed')) if arg('--speed') else None
TAG = arg('--tag', 'robot_walk' + ('_bend' if PATH == 'bend' else '') + ('_slow' if SPEED else ''))
PATHS = {'straight': [(0.0, 0.0), (10.0, 0.0)], 'bend': [(0.0, -6.0), (4.0, -6.0), (6.83, -3.17)]}
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'vrm': VRM, 'path': PATHS[PATH], 'speed': SPEED, 'steps': {}}
T0 = time.time()


def log(*a):
    print(f'[{TAG}]', *a, flush=True)


def terrain(x, y):
    """uneven ground: an 18 cm mound mid-path on a gentle rise, rolls of 3.5-6 cm and foot-sized ripples of 2 cm (slopes
    up to ~18 deg along the path, ~10 across it: inside the ankle's pitch and roll stops); --flat: a level floor"""
    if '--flat' in ARGS:
        return 0.0 * x
    return (0.06 * np.sin(1.3 * x + 0.4) * np.sin(1.7 * y + 0.3)
            + 0.035 * np.sin(2.9 * x + 1.1 * y)
            + 0.02 * np.sin(6.1 * x - 3.1 * y + 0.7)
            + 0.18 * np.exp(-((x - 5.0) ** 2) / (2 * 1.4 ** 2))
            + 0.015 * x)


def gz(x, y):
    return float(terrain(np.array([x]), np.array([y]))[0])


def out(name):
    return os.path.join(S.OUT, f'{TAG}_{name}.png')


try:
    sc = S.clean_scene(24)
    S.probe_render(sc)
    S.studio_world(sc, 0.8)
    S.sun('key', (-2.2, 3.2, 3.0), 0xfff4e8, 2.6, angle_deg=3.0)
    S.sun('rim', (2.5, 2.0, -3.0), 0xdfe8ff, 1.2, angle_deg=3.0)
    S.ground_mesh(terrain, -8.0, 18.0, -17.0, 10.0, step=0.04)
    ground = Ground(fn=terrain)
    R['steps']['stage_s'] = round(time.time() - T0, 1)

    t = time.time()
    p0, p1 = PATHS[PATH][0], PATHS[PATH][1]
    me = load_vrm(VRM, name='claude', location=(p0[0], p0[1], 0.0),
                  rotation=math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0])) + 90.0)
    R['steps']['load_vrm_s'] = round(time.time() - t, 1)
    t = time.time()
    walk = load_clip(me, 'walk')
    R['steps']['load_clip_s'] = round(time.time() - t, 2)
    R['clip'] = {'action': walk.action.name, 'duration_s': walk.duration, 'frames': list(walk.action.frame_range)}

    # the knee bends about +X in the normalized frame (the proof that read_pose's frame is three-vrm's): the clip's
    # left knee through one loop, as the add-on's own retarget keyed it
    body = Body(me)
    knee = []
    for k in range(12):
        rot, _loc = walk.sample(k * walk.duration / 12)
        b = me.humanoid['leftLowerLeg']
        n = me.normalized_from_basis(b, rot[b])
        ax, ang = n.to_axis_angle()
        knee.append((round(math.degrees(ang), 1), [round(c, 3) for c in ax]))
    R['clip_left_knee_axis_angle'] = knee

    key_expression(me, 'happy', [(1, 1.0)])
    t = time.time()
    rep = walk_path(me, walk, PATHS[PATH], ground, f0=1, speed=SPEED, face={'happy': 1.0}, body=body, log=log)
    R['steps']['walk_path_s'] = round(time.time() - t, 1)
    F0, F1 = rep['frames']
    sc.frame_start, sc.frame_end = F0, F1
    R['walk'] = {k: v for k, v in rep.items() if not k.startswith('_')}
    ok, bad = checks.feet(rep)
    # the FK the report measures against Blender's evaluated pose: at every landing and the frame after it (where the
    # verifier found the old lock's slip), and a few more
    fk_frames = sorted({F0, (F0 + F1) // 2, F1 - 3} | {f for s in ('left', 'right') for a, _b in
                                                        (r_['frames'] for r_ in rep['stances'][s]) for f in (a, a + 1)
                                                        if F0 < a < F1})
    R['checks'] = {'feet_ok': ok, 'feet_failures': bad[:20],
                   'fk_vs_blender_mm': checks.fk_matches_blender(me, body, rep, fk_frames), 'fk_frames': fk_frames,
                   'posed_vs_rest_deg': checks.posed_vs_rest(me, [F0, (F0 + F1) // 2]),
                   'happy': checks.expression_moved(me, 'happy', [F0, F1])}
    log('feet', ok, bad[:6])
    log('worst', rep['worst'], 'fk vs blender mm', R['checks']['fk_vs_blender_mm'])
    log('gait', rep['gait'], 'double support', len(rep['double_support']), 'pelvis lowered', rep['pelvis_lowered_mm'])
    sc.frame_set(F0)
    if '--no-save' not in ARGS and TAG == 'robot_walk':
        blend = os.path.join(S.OUT, 'robot_walk.blend')
        bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
        R['blend'] = blend

    fr = {x['f']: x for x in rep['_frames']}

    def hips(f):
        sc.frame_set(f)
        return me.arm.matrix_world @ me.arm.pose.bones[me.humanoid['hips']].head

    def side_of(f, cam, dist=5.6):
        """a camera square to my heading at frame f, on my right"""
        h = hips(f)
        psi = fr[f]['psi']
        right = Vector((math.sin(psi), -math.cos(psi), 0.0))
        g = gz(h.x, h.y)
        S.aim(cam, (h.x + right.x * dist, h.y + right.y * dist, 0.95 + g), (h.x, h.y, 0.88 + g))

    def foot_cam(cam, P, psi, back=1.35, up=0.22, along=0.25):
        c = P.mean(0)
        right = np.array([math.sin(psi), -math.cos(psi)])
        fwd = np.array([math.cos(psi), math.sin(psi)])
        e = c[:2] + right * back + fwd * along
        S.aim(cam, (e[0], e[1], c[2] + up), (c[0], c[1], c[2] + 0.05))

    rs = {}

    def still(cam, f, name):
        p = out(name)
        t_ = time.time()
        rs[os.path.basename(p)] = (S.still(sc, cam, f, p), round(time.time() - t_, 1))
        log('rendered', os.path.basename(p), rs[os.path.basename(p)])

    if RENDER and PATH == 'straight':
        cam = S.camera('cam_side', 50.0)
        sel = [F0 + 12, F0 + 40, (F0 + F1) // 2, F1 - 40, F1 - 8] if not SPEED else [F0 + 30, (F0 + F1) // 2, F1 - 30]
        for f in sel:
            side_of(f, cam)
            still(cam, f, f'side_f{f:03d}')
        # one planted foot through its stance, a fixed low camera on it (the near foot: my right, toward -Y)
        st = [r_ for r_ in rep['stances']['right'] if F0 + 30 < r_['frames'][0] and r_['frames'][1] < F1 - 10]
        if st:
            a, b = st[len(st) // 2]['frames']
            feet_cam = S.camera('cam_feet', 50.0)
            foot_cam(feet_cam, fr[a + (b - a) // 2]['meas']['right']['P'], fr[a]['psi'])
            for f in sorted({a, a + (b - a) // 3, a + 2 * (b - a) // 3, b}):
                still(feet_cam, f, f'feet_right_f{f:03d}')
            R['feet_strip'] = {'side': 'right', 'stance': [a, b]}
    if RENDER and PATH == 'straight' and not SPEED:
        # the whole walk from one fixed camera: me at the start, the middle and the end
        wide = S.camera('cam_wide', 28.0)
        S.aim(wide, (5.0, -13.5, 2.1), (5.0, 0.0, 0.55))
        for f in (F0, (F0 + F1) // 2, F1):
            still(wide, f, f'wide_f{f:03d}')
        # one gait cycle, 8 frames, the side camera following
        cyc = int(round(walk.duration * sc.render.fps / rep['time_scale']))
        g0 = F0 + 3 * cyc
        for k in range(8):
            f = g0 + round(k * cyc / 8)
            side_of(f, cam)
            still(cam, f, f'gait_{k}_f{f:03d}')
        face = S.camera('cam_face', 85.0)
        for f in (F0 + 30, F1 - 30):
            sc.frame_set(f)
            hd = me.arm.matrix_world @ me.arm.pose.bones[me.humanoid['head']].head
            fwd = me.arm.matrix_world.to_quaternion() @ Vector((0.0, -1.0, 0.0))
            fwd.z = 0
            fwd.normalize()
            side = Vector((fwd.y, -fwd.x, 0.0))
            tgt = hd + Vector((0, 0, 0.10))
            S.aim(face, tgt + fwd * 1.45 + side * 0.55 + Vector((0, 0, 0.04)), tgt)
            still(face, f, f'face_f{f:03d}')
        # whole right swings from a fixed low camera: over the mound (x 4-6) and over the rolls before it (x 1.5-3)
        swing_cam = S.camera('cam_swing', 40.0)
        picks = []
        for lo, hi in ((4.0, 6.0), (1.5, 3.0)):
            for w in rep['swings']['right']:
                a, b = w['frames']
                xm = fr[(a + b) // 2]['meas']['right']['P'][:, 0].mean()
                if lo <= xm <= hi and b - a >= 6 and w not in picks:
                    picks.append(w)
                    break
        R['swing_strips'] = []
        for k, w in enumerate(picks):
            a, b = w['frames']
            a, b = a - 1, b + 1                     # from the last stance frame to the landing
            P = np.concatenate([fr[f]['meas']['right']['P'] for f in (a, b)])
            c = P.mean(0)
            S.aim(swing_cam, (c[0], c[1] - 1.9, c[2] + 0.16), (c[0], c[1], c[2] + 0.06))
            sel = sorted({a + round(j * (b - a) / 5) for j in range(6)})
            for f in sel:
                still(swing_cam, f, f'swing{k}_f{f:03d}')
            R['swing_strips'].append({'frames': [a, b], 'stills': sel, 'clearance_mm': w['clearance_mm'],
                                      'mid_clearance_mm': w['mid_clearance_mm']})
        # a double support, low and close; and from in front
        ds = [f for f in rep['double_support'] if F0 + 40 < f < F1 - 20]
        dcam = S.camera('cam_double', 50.0)
        for f in ds[:1] + ds[len(ds) // 2: len(ds) // 2 + 1]:
            P = np.concatenate([fr[f]['meas'][s]['P'] for s in ('left', 'right')])
            foot_cam(dcam, P, fr[f]['psi'], back=1.6, up=0.25, along=0.0)
            still(dcam, f, f'double_f{f:03d}')
        front = S.camera('cam_front', 50.0)
        for f in ((F0 + F1) // 2 - 20, (F0 + F1) // 2 + 10):
            h = hips(f)
            S.aim(front, (h.x + 4.8, h.y + 0.3, 0.9 + gz(h.x, h.y)), (h.x, h.y, 0.75 + gz(h.x, h.y)))
            still(front, f, f'front_f{f:03d}')
    if RENDER and PATH == 'bend':
        # the corner from a fixed camera above and outside it, frames through the turn
        corner = S.camera('cam_corner', 35.0)
        S.aim(corner, (6.6, -9.4, 3.0), (4.3, -5.4, 0.45))
        fs = [fr_['f'] for fr_ in rep['_frames']]
        turn = [f for f in fs if abs(fr[f]['psi'] - fr[fs[0]]['psi']) > 0.02 and abs(fr[f]['psi'] - fr[fs[-1]]['psi']) > 0.02]
        f_in, f_out = (turn[0], turn[-1]) if turn else (fs[len(fs) // 2], fs[len(fs) // 2])
        R['turn_frames'] = [f_in, f_out]
        for f in sorted({f_in - 8, f_in, (f_in + f_out) // 2, f_out, f_out + 8}):
            still(corner, f, f'corner_f{f:03d}')
        cam = S.camera('cam_side', 50.0)
        for f in (f_in, (f_in + f_out) // 2, f_out):
            side_of(f, cam)
            still(cam, f, f'side_f{f:03d}')
        # my outer foot (the right, in this left turn) through its stance in the turn, a fixed low camera
        st = [r_ for r_ in rep['stances']['right'] if r_['frames'][0] <= (f_in + f_out) // 2 <= r_['frames'][1]] or \
             [r_ for r_ in rep['stances']['right'] if r_['frames'][0] >= f_in]
        if st:
            a, b = st[0]['frames']
            feet_cam = S.camera('cam_feet', 50.0)
            foot_cam(feet_cam, fr[a + (b - a) // 2]['meas']['right']['P'], fr[a]['psi'])
            for f in sorted({a, a + (b - a) // 3, a + 2 * (b - a) // 3, b}):
                still(feet_cam, f, f'feet_right_f{f:03d}')
            R['feet_strip'] = {'side': 'right', 'stance': [a, b]}
    R['renders'] = rs
    R['ok'] = True
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
with open(os.path.join(S.OUT, f'{TAG}.json'), 'w', encoding='utf-8') as f:
    json.dump(R, f, indent=1, default=str)
log('done', R['ok'], R['seconds'], 's')
