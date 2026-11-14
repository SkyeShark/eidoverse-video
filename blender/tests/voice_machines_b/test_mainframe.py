"""The 1961 computer room (props/voice_machines/mainframe.py): build, the tape integrator and the analytic stop against
mainframe.js, the keyed reels and vacuum-column loops, the lamp logic, and probe renders at true scale.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/voice_machines_b/test_mainframe.py          # checks
    bash run_blender.sh <this> --render                                                                        # + stills
    (--render: a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402

import bpy  # noqa: E402


def film_speed(t):
    """the DAISY intro's curve: nominal, then (1 - x)^1.6 to a stop"""
    x = max(0.0, (t - 2.0) / 2.0)
    return 1.0 if t < 2.0 else max(0.0, 1.0 - x) ** 1.6


def run(render=False):
    sc = S.fresh_scene(frames=(1, 120))
    from eidoblend.props.voice_machines import mainframe as MF
    mf = MF.build()
    P = mf.parts
    S.check('mainframe: every GLB role has a material', not mf.missing_roles, ', '.join(sorted(mf.missing_roles)))
    S.decals_drawn('mainframe', mf.made['images'])
    S.decals_on_panels('mainframe', mf, 6, not mf.seated_decals)
    S.check('mainframe: 8 reels with their pack radii', len(P['reels']) == 8 and all(r['pack_radius'] > 0.05 for r in P['reels']))
    S.check('mainframe: lamps and loops', P['lamps']['count'] == 200 + 4 * 11 + 12 and len(P['loops']) == 8,
            f"{P['lamps']['count']} lamps, {len(P['loops'])} loops")

    dump = S.OUT / 'parity_js.json'
    J = json.loads(dump.read_text()) if dump.exists() else {}
    if 'tape_speed' in J:
        mem = {'last_t': None, 'last_speed': 0.0, 'pos': 0.0}
        worst = max(abs(MF.tape_position({'tape_speed': s}, t, mem) - p) for t, s, p in J['tape_speed'])
        S.check('mainframe: integrated tape speed equals mainframe.js (trapezoid, 120 frames)', worst < 1e-12, f'{worst:.1e}')
        mem = {'last_t': None, 'last_speed': 0.0, 'pos': 0.0}
        worst = max(abs(MF.tape_position({'tape_stop': {'at': 2.0, 'duration': 1.5, 'curve': 2}}, t, mem) - p)
                    for t, p in J['tape_stop'])
        S.check('mainframe: analytic tape stop equals mainframe.js', worst < 1e-12, f'{worst:.1e}')
    else:
        S.check('mainframe: parity dump present', False)
    mem = {'last_t': None, 'last_speed': 0.0, 'pos': 0.0}
    S.check('mainframe: tape_pos (metres) overrides speed and stop',
            MF.tape_position({'tape_pos': 3.2, 'tape_speed': 5.0, 'tape_stop': {'at': 0.1}}, 9.0, mem) == 3.2)

    # the film: tape at speed, then the stop; the voice sings over it
    n = mf.animate(lambda t: {'tapeSpeed': film_speed(t), 'voice': 0.6 if 1.0 < t < 3.5 else 0.0, 'power': 1.0},
                   frames=(1, 120))
    S.check('mainframe: animate keyed the film', n > 100, f'{n} keys')
    mem = {'last_t': None, 'last_speed': 0.0, 'pos': 0.0}
    xs = [MF.tape_position({'tape_speed': film_speed(mf.time_at(f))}, mf.time_at(f), mem) for f in range(1, 121)]
    for f in (30, 70, 120):
        sc.frame_set(f)
        r = P['reels'][2]
        m = MF.SPEED_MULT[r['drive'] % 6]
        want = (xs[f - 1] * m) / r['pack_radius']
        got = r['pivot'].rotation_euler[1]
        S.check(f'mainframe: reel 3 angle keyed at frame {f}', abs(got - want) < 1e-4 * max(1, abs(want)),
                f'{got:.4f} vs {want:.4f} rad')
    sc.frame_set(110)
    a110 = P['reels'][0]['pivot'].rotation_euler[1]
    sc.frame_set(120)
    a120 = P['reels'][0]['pivot'].rotation_euler[1]
    S.check('mainframe: the reels stop with the tape', abs(a120 - a110) < 1e-3, f'{a110:.4f} -> {a120:.4f}')
    sc.frame_set(40)
    X = xs[39]
    lp = P['loops'][3]
    m = MF.SPEED_MULT[(3 // 2) % 6]
    d = MF.LOOP_BASE + 0.09 * math.sin(X * abs(m) * 2.3 + 3 * 1.7) * min(1, abs(m)) + 0.05
    S.check('mainframe: a vacuum-column loop follows the tape (keyed)',
            abs(lp['runs'].scale.z - (MF.MOUTH - d) / (MF.MOUTH - 0.05)) < 1e-5 and abs(lp['bend'].location.z - (d - 0.05)) < 1e-5)
    S.check('mainframe: the clock is the tape (keyed)', abs(mf.group['clock'] - X / MF.TAPE_MPS) < 1e-5)
    # the lamp logic: register bits change with the clock, the voice adds sparkle (register and counter lamps only)
    import numpy as np
    lamps = MF.K.json_load('mainframe_layout.json')['console']['lamps']
    on = lambda clock, t, v: np.array([MF.lamp_on_cpu(l[2], l[3], l[4], clock, t, v) for l in lamps])  # noqa: E731
    a, b = on(1.0, 1.0, 0.0), on(1.4, 1.4, 0.0)
    S.check('mainframe: register lamps change with the clock', 10 < int((np.abs(a - b) > 0.5).sum()) < 190,
            f'{int((np.abs(a - b) > 0.5).sum())} of {len(lamps)} changed in 0.4 s')
    lit0, lit1 = (on(2.0, 2.0, 0.0) > 0.5).sum(), (on(2.0, 2.0, 1.0) > 0.5).sum()
    S.check('mainframe: the voice lights more lamps', lit1 > lit0, f'{lit0} -> {lit1} lit')
    lo, hi = S.bounds([mf.group] + list(mf.group.children_recursive))
    size = hi - lo
    S.check('mainframe: footprint about index.js (4.58 x 2.81 x 1.87 m)',
            all(abs(x - y) < 0.06 for x, y in zip(size, MF.MACHINE['footprint'])), f'{size.x:.3f} x {size.y:.3f} x {size.z:.3f}')
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
    feet = S.rest_height(mf)
    S.check("mainframe: centre matches index.js's (0.0, -0.64 in Blender axes); the room stands on z = 0 (its floor "
            'cables run into the grommet)', abs(cx - MF.MACHINE['center'][0]) < 0.02
            and abs(cy - MF.MACHINE['center'][1]) < 0.02 and abs(feet) < 0.002,
            f'({cx:.3f}, {cy:.3f}), feet {feet * 1000:.1f} mm, cables {lo.z * 1000:.1f} mm')
    S.dispose_leaves_nothing('mainframe', lambda: MF.build(name='mainframe_2', power=0.5,
                                                           glb=str(Path(MF.K.PACK) / 'mainframe.glb')))

    if render:
        from PIL import Image as PI
        from eidoblend.props.voice_machines import voder as K
        L = K.json_load('mainframe_layout.json')
        for nm, w, h, fn in (('plate', 1024, 128, MF._draw_plate), ('name', 1024, 104, MF._draw_name),
                             ('panel', 1024, 280, MF._draw_panel(L)), ('atlas', 1024, 256, MF._draw_atlas)):
            c = K.Ctx2D(w, h, ss=3)
            fn(c, w, h)
            bg = PI.new('RGBA', (w, h), (90, 90, 90, 255))
            bg.alpha_composite(c.image())
            bg.save(S.OUT / f'mainframe_art_{nm}.png')
        S.floor(sc, size=16)
        S.wall(sc, y=0.9, color=(0.36, 0.35, 0.33))
        S.studio(sc, (0, -0.4, 1.0), dist=5.5, key=220, scale=1.5)
        cam = S.camera(sc, (1.9, -5.2, 1.75), (-0.3, -0.3, 1.0), lens=28)
        S.render(S.OUT / 'mainframe_room_wide_f040.png', frame=40)
        S.look_from(cam, (-0.65, -1.25, 1.45), (-0.3, 0.0, 1.25), lens=35)
        S.render(S.OUT / 'mainframe_tape_drive_f040.png', frame=40)
        S.look_from(cam, (1.25, -2.35, 1.55), (0.95, -1.35, 1.05), lens=40)
        S.render(S.OUT / 'mainframe_console_lamps_f040.png', frame=40)
        # the lights dying (power 0.12) after the tape has stopped: the same console framing
        mf.update(mf.time_at(121), {'tape_speed': 0.0, 'voice': 0.0, 'power': 0.12}, frame=121)
        S.render(S.OUT / 'mainframe_console_lights_dying_f121.png', frame=121)
    return S.summary('mainframe')


if __name__ == '__main__':
    sys.exit(1 if run(render='--render' in sys.argv) else 0)
