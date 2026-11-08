"""The clip library on the claudesona (claude_suit.vrm, MToon as the add-on builds it): still_breathe from 0 s, the one-shot
turn_it_down crossfaded over it at 2 s (0.3 s) and holding its last frame, then turn_it_down_hold cut in on that last frame.
Checks that the NLA plays each clip's own pose (the evaluated basis against Clip.sample at frames inside each strip) and that
the hold hands over without a jump (the hand's travel across the handover frame); renders three stills.

    out/vrma_clips_f<NNN>.png   (still_breathe, turn_it_down mid-press, the hold)
    out/vrma_clips.json

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/characters/test_vrma_clips.py [--no-render]
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

from eidoblend.characters import load_clip, load_vrm, play_vrma, play_vrma_default  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()


def log(*a):
    print('[vrma_clips]', *a, flush=True)


try:
    sc = S.clean_scene(FPS)
    S.probe_render(sc)
    S.studio_world(sc, 0.8, background=0x121214)
    S.sun('key', (-2.2, 3.2, 3.0), 0xfff4e8, 2.2, angle_deg=3.0)
    S.sun('rim', (2.5, 2.0, -3.0), 0xdfe8ff, 1.0, angle_deg=3.0)
    S.floor_disc()
    me = load_vrm('claude_suit', name='digi')
    me.arm.scale = (0.87, 0.87, 0.87)                     # the films' scale for the claudesona (a human 1.74 m)
    breathe = load_clip(me, 'still_breathe')
    once = load_clip(me, 'turn_it_down')
    hold = load_clip(me, 'turn_it_down_hold')
    t_once, fade = 2.0, 0.3
    t_hold = t_once + once.duration
    play_vrma(me, breathe, t=0.0, loop=True, until=t_hold + 4.0)
    play_vrma(me, once, t=t_once, loop=False, fade=fade)
    play_vrma(me, hold, t=t_hold, loop=True, until=t_hold + 4.0)
    R['clips'] = {c.slot: {'duration_s': round(c.duration, 4), 'frames': list(c.action.frame_range)} for c in (breathe, once, hold)}
    f_once, f_hold = 1 + round(t_once * FPS), 1 + round(t_hold * FPS)
    sc.frame_start, sc.frame_end = 1, f_hold + 48

    def pose_err(clip, f, tc):
        sc.frame_set(f)
        rot, _loc = clip.sample(tc)
        worst = 0.0
        for b, q in rot.items():
            got = me.arm.pose.bones[b].rotation_quaternion
            worst = max(worst, math.degrees(2 * math.acos(min(1.0, abs(got.normalized().dot(q))))))
        return round(worst, 3)
    R['nla_vs_clip_deg'] = {
        'still_breathe@1.0s': pose_err(breathe, 1 + round(1.0 * FPS), 1.0),
        'turn_it_down@+1.0s (fade done)': pose_err(once, f_once + FPS, (f_once + FPS - 1) / FPS - t_once),
        'hold@+1.0s': pose_err(hold, f_hold + FPS, (f_hold + FPS - 1) / FPS - t_hold),
    }
    hand = me.humanoid['rightHand']
    travel = []
    for f in range(f_hold - 3, f_hold + 4):
        sc.frame_set(f)
        travel.append((f, (me.arm.matrix_world @ me.arm.pose.bones[hand].head).copy()))
    R['hand_step_mm_around_handover'] = [(travel[i + 1][0], round(1000 * (travel[i + 1][1] - travel[i][1]).length, 2))
                                         for i in range(len(travel) - 1)]
    try:
        play_vrma_default(me, 'walk')
        R['locomotion_guard'] = 'NOT refused'
    except ValueError as e:
        R['locomotion_guard'] = 'refused: ' + str(e)[:80]
    log(R['nla_vs_clip_deg'], R['hand_step_mm_around_handover'], R['locomotion_guard'][:20])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'vrma_clips.blend'), compress=True)
    if RENDER:
        cam = S.camera('cam', 50.0)
        cam.data.sensor_fit = 'VERTICAL'
        cam.data.angle_y = math.radians(30.0)
        S.aim(cam, (0.9, -3.3, 1.05), (0.0, 0.0, 0.92))
        rs = {}
        for f in (1 + FPS, f_once + round(1.6 * FPS), f_hold + FPS):
            p = os.path.join(S.OUT, f'vrma_clips_f{f:03d}.png')
            rs[os.path.basename(p)] = S.still(sc, cam, f, p)
        R['renders'] = rs
    R['ok'] = True
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
with open(os.path.join(S.OUT, 'vrma_clips.json'), 'w', encoding='utf-8') as f:
    json.dump(R, f, indent=1, default=str)
log('done', R['ok'], R['seconds'], 's')
