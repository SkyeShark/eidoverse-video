"""My robot body's aimed emotes: set_emote_facing (robot_body.js sets the engine controller's _emoteFacingY) aims the
standing emotes perform_action plays. Within 15 deg of my heading the emote's root pivots to the aim during its fade-in,
the engine's own timing; further, I turn on the spot to the aim first (the turn clips), play the emote, and turn back to
my own heading after it (controller.PIVOT_MAX: my planted feet cannot follow a root that pivots further).

A room (6 x 6 m); I walk 2 m up it and stop, then:

    set_emote_facing(10 deg to my left)  + perform_action('salute', 1.5 s)        [it pivots]
    set_emote_facing(13 deg to my right) + perform_action('wave_goodbye', 2 s)    [it pivots]
    set_emote_facing(50 deg to my left)  + perform_action('salute', 1.5 s)        [I turn to it, salute, turn back]
    set_emote_facing(None)

Checks (PASS / FAIL), on the keyed result:
  - the pivots: no turn on the spot for an emote aimed within 15 deg; my facing comes to the aim within the emote's
    first half second (its fade-in and the controller's easing) and holds it (1 deg) to the emote's end; no planted
    sole point slides more than 2 mm in a frame through either
  - the turn first: the emote aimed 50 deg off plays after a turn on the spot to it, faces it (2 deg), and the turn
    back after it ends on my own heading (2 deg)
  - each perform_action resolves
Stills: out/aimed_emote_<emote>_<k>_f<frame>.png (a low side camera held over each emote); out/aimed_emote.json,
out/aimed_emote.blend.

    bash run_blender.sh blender/tests/robot_body/test_body_aimed_emote.py --no-render
"""

import math
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.robot import RobotRig, VRMRobotBody  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
R = S.Report('aimed_emote')
START, H0, STOP = (0.0, -2.0), math.pi, (0.0, 0.0)          # facing +Y, up the room
AIMS = [('salute', 10.0, 1.5), ('wave_goodbye', -13.0, 2.0), ('salute', 50.0, 1.5)]   # (clip, deg off my heading, s)


def heading_of_frame(fr):
    q = fr['M'].to_quaternion()
    return 2.0 * math.atan2(q.z, q.w)


def deg_off(a, b):
    return abs(math.degrees(math.remainder(a - b, 2.0 * math.pi)))


def main():
    sc = S.C.clean_scene(FPS)
    floor_m = S.textured('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = S.textured('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    floor = S.box('floor', -3.0, 3.0, -3.0, 3.0, -0.05, 0.0, floor_m)
    walls = [S.box('wall_n', -3.1, 3.1, 3.0, 3.1, 0.0, 2.6, wall_m), S.box('wall_s', -3.1, 3.1, -3.1, -3.0, 0.0, 2.6, wall_m),
             S.box('wall_w', -3.1, -3.0, -3.0, 3.0, 0.0, 2.6, wall_m), S.box('wall_e', 3.0, 3.1, -3.0, 3.0, 0.0, 2.6, wall_m)]
    from eidoblend.characters.robot.example import directional, studio_environment
    studio_environment(sc, 0.4, None)
    S.area_light(sc, 'ceiling', (0.0, 0.0, 2.5), 400.0, 2.0)
    directional('key', (-3.0, 4.0, -6.0), 0xfff2e4, 1.4)
    me = load_vrm('claude_robot', name='claude', location=(START[0], START[1], 0.0), rotation=math.degrees(H0))
    rig = RobotRig(me)
    body = VRMRobotBody.create(me, sc, {
        'collision_meshes': [floor] + walls,
        'motion': {'start_x': START[0], 'start_y': START[1], 'start_heading': H0, 'walk_speed': 0.9},
        'memory': {'size': 8.0, 'cell_size': 0.1}, 'sensors': {'h_rays': 12, 'v_rays': 10, 'range': 6.0}}, rig=rig)
    out, marks = {}, []

    def script(b):
        a = yield b.walk_to(*STOP)
        out['walk'] = (a.state, str(a.error) if a.error else None)
        a = yield b.wait(0.5)
        h = b.get_heading()
        out['heading'] = h
        for clip, off, secs in AIMS:
            aim = h + math.radians(off)
            b.set_emote_facing(aim)
            f_call = b.frame_count
            a = yield b.perform_action(clip, secs)
            marks.append({'clip': clip, 'off_deg': off, 'aim': aim, 'call': f_call, 'resolved': b.frame_count,
                          'state': a.state})
            b.set_emote_facing(None)
            a = yield b.wait(0.4 if abs(off) <= 15.0 else 2.2)       # the turn back, after the 50 deg one
    body.run(script(body))
    for k in range(FPS * 40):
        body.update(k / FPS, 1.0 / FPS)
        if body._script is None:
            break
    R['run'] = {'frames': body.frame_count, 'outcome': out, 'marks': marks}
    R.log('run', R['run'])
    rep = body.bake(face=lambda t: {'happy': 0.3}, action_name='claude|aimed_emote')
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('map', 'stances', 'swings')}
    frames = rep['_frames']
    f0 = rep['frames'][0]
    sc.frame_start, sc.frame_end = rep['frames']
    h = out.get('heading', H0)
    res = []
    for m in marks:
        a_, b_ = f0 + m['call'] - 1, f0 + m['resolved'] - 1
        play = [fr for fr in frames[a_ - f0:b_ - f0 + 1] if fr['mode'] == 'emote' and fr['lead'] == m['clip']]
        turns = [t for t in rep['turns'] if a_ - 2 <= t[0] <= b_]
        row = {'clip': m['clip'], 'off_deg': m['off_deg'], 'state': m['state'], 'frames': [a_, b_],
               'play': [play[0]['f'], play[-1]['f']] if play else None, 'turns': turns}
        if play:
            settled = [fr for fr in play if fr['f'] >= play[0]['f'] + FPS // 2]
            row['facing_off_aim_deg'] = round(max(deg_off(heading_of_frame(fr), m['aim']) for fr in settled), 2) \
                if settled else None
            row['slide_mm'] = S.feet_slide(rig, frames, lambda fr, p=play: p[0]['f'] <= fr['f'] <= p[-1]['f'])
        res.append(row)
    R['emotes'] = res
    piv = [r for r in res if abs(r['off_deg']) <= 15.0]
    R.check('the pivots: an emote aimed within 15 deg pivots in its fade-in, no turn on the spot',
            len(piv) == 2 and all(r['state'] == 'resolved' and r['play'] and not r['turns']
                                  and r['facing_off_aim_deg'] is not None and r['facing_off_aim_deg'] <= 1.0
                                  and max(v[0] for v in r['slide_mm'].values()) <= 2.0 for r in piv),
            f'{piv} (the facing against the aim from half a second into the emote to its end; the planted feet\'s '
            f'slide, mm a frame)')
    far = [r for r in res if abs(r['off_deg']) > 15.0]
    back = deg_off(heading_of_frame(frames[-1]), h)
    R['turned_back_off_my_heading_deg'] = round(back, 2)
    R.check('the turn first: an emote aimed 50 deg off turns to it, plays, and turns back',
            len(far) == 1 and far[0]['state'] == 'resolved' and far[0]['turns'] and far[0]['play']
            and far[0]['turns'][0][1] < far[0]['play'][0] and far[0]['facing_off_aim_deg'] is not None
            and far[0]['facing_off_aim_deg'] <= 2.0 and back <= 2.0,
            f'{far}; the last frame faces {back:.2f} deg off my heading before the emotes')
    R.check('each perform_action resolves', all(m['state'] == 'resolved' for m in marks) and len(marks) == 3,
            f'{[(m["clip"], m["state"]) for m in marks]}; the walk {out.get("walk")}')
    # the stills: a low side camera held over each emote, every two frames
    vbvh = S.solids_bvh(walls)
    shots, last = [], f0 + len(frames) - 1
    for k, r in enumerate(res):
        a_, b_ = max(f0, r['frames'][0] - 4), min(last, r['frames'][1] + (6 if abs(r['off_deg']) <= 15 else 40))
        shots += S.strip(f'{r["clip"]}{k + 1}', S.side_view(vbvh, frames, f0, a_, b_), a_, b_,
                         n=min(18, (b_ - a_) // 2 + 1))
    S.write_json('aimed_emote_shots.json', shots)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'aimed_emote.blend'), compress=True)
    if RENDER:
        R['renders'] = S.render_shots(sc, 'aimed_emote', shots)


try:
    main()
except Exception:  # noqa: BLE001
    R.finish(traceback.format_exc())
else:
    R.finish()
