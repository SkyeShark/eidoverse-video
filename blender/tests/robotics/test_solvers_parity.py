"""The kit's pure kinematics against the WebGPU edition's own numbers (plain Python, no Blender).

js_parity_dump.mjs (run first; see its header) writes out/js_parity/_summary.json and the A650's IK cases; this
compares eidoblend.characters.robotics.solvers with them: scara forward / inverse / demo / limits / grip TCP, the
A650's SerialArm forward, Jacobian and inverse, articulatedDemo, gantryDemo, constrainGantryPose, graspValues and
rotaryFixtureSetup. Every value is used in the kit's native axes in both editions, so they must agree to float
precision.

    python C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/test_solvers_parity.py
"""

import json
import math
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))

# solvers.py is plain Python; load it by path so the package __init__ (which imports bpy) stays out of it
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    'robotics_solvers', os.path.join(REPO, 'blender', 'eidoblend', 'characters', 'robotics', 'solvers.py'))
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

DUMP = os.path.join(HERE, 'out', 'js_parity')
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def flat(x):
    if isinstance(x, dict):
        return [v for k in sorted(x) for v in flat(x[k])]
    if isinstance(x, (list, tuple)):
        return [v for e in x for v in flat(e)]
    return [float(x)] if isinstance(x, (int, float)) and not isinstance(x, bool) else []


def worst(a, b):
    fa, fb = flat(a), flat(b)
    if len(fa) != len(fb):
        return math.inf
    return max((abs(x - y) for x, y in zip(fa, fb)), default=0.0)


def main():
    summ = json.load(open(os.path.join(DUMP, '_summary.json'), encoding='utf-8'))['solvers']
    sc = S.scara
    w = max(worst(sc.forward(c['q']), c['tcp0']) for c in summ['scara_forward'])
    w = max(w, max(worst(sc.forward(c['q'], sc.GRIP_TCP), c['tcp']) for c in summ['scara_forward']))
    check('scara.forward matches scara.js (plain and grip TCP)', w < 1e-12, f'worst {w:.2e}')
    worst_inv, counts = 0.0, True
    for c in summ['scara_inverse']:
        x, y, z, yaw = c['args']
        for got, want in ((sc.inverse(x, y, z, yaw), c['plain']),
                          (sc.inverse(x, y, z, yaw, sc.GRIP_TCP, [0.1, 0.5, 0.05, 0]), c['tcp']),
                          (sc.inverse(x, y, z, yaw, sc.GRIP_TCP, None, 0.055), c['minZ'])):
            counts &= len(got) == len(want)
            worst_inv = max(worst_inv, worst(got, want))
    check('scara.inverse matches (solution count, order, values; seed and minZ)', counts and worst_inv < 1e-12,
          f'worst {worst_inv:.2e}')
    w = max(worst(sc.demo(c['t']), c['q']) for c in summ['scara_demo'])
    check('scara.demo matches', w < 1e-12, f'worst {w:.2e}')
    check('scara limits and gripTCP match', worst(sc.LIMITS, summ['scara_limits']) < 1e-15
          and worst(sc.GRIP_TCP, summ['scara_gripTCP']) == 0)
    w = max(worst(S.articulated_demo(c['t']), c['q']) for c in summ['articulatedDemo'])
    check('articulatedDemo matches', w < 1e-12, f'worst {w:.2e}')
    w = max(worst(S.gantry_demo(c['t'], c['tool'], c['tipRestZ']), c['xyz']) for c in summ['gantryDemo'])
    check('gantryDemo matches (bare, extruder, spindle, explicit tip rest)', w < 1e-12, f'worst {w:.2e}')
    mf = json.load(open(os.path.join(REPO, 'eidoverse', 'assets', 'robotics', 'metadata', 'manufacturing.json'),
                        encoding='utf-8'))
    w = 0.0
    for c in summ['constrainGantryPose']:
        w = max(w, worst(S.constrain_gantry_pose(mf, None, c['xyz']), c['plain']),
                worst(S.constrain_gantry_pose(mf, {'z_limits_m': [-0.02, 0.01]}, c['xyz']), c['assembly']))
    check('constrainGantryPose matches', w < 1e-12, f'worst {w:.2e}')
    inter = json.load(open(os.path.join(REPO, 'eidoverse', 'assets', 'robotics', 'metadata', 'interaction.json'),
                           encoding='utf-8'))
    g = inter['mobile']['hand']['grasp']
    w = max(worst(S.grasp_values(g, c['t']), c['q']) for c in summ['graspValues'])
    keys = all(set(S.grasp_values(g, c['t'])) == set(c['q']) for c in summ['graspValues'])
    check('graspValues matches (joints and approach keyframes)', keys and w < 1e-12, f'worst {w:.2e}')
    w = 0.0
    for c in summ['rotaryFixtureSetup']:
        o = c['o']
        r = S.rotary_fixture_setup(**{'stock_length': o.get('stockLength', 0.14), 'stock_width': o.get('stockWidth', 0.036),
                                      'stock_height': o.get('stockHeight', 0.036), 'quill': o.get('quill', 0.0)})
        want = c['r']
        w = max(w, worst(r['joints'], want['joints']), abs(r['axis_x'] - want['axisX']),
                abs(r['start'] - want['start']), abs(r['end'] - want['end']))
    check('rotaryFixtureSetup matches', w < 1e-12, f'worst {w:.2e}')
    for bad in ({'stock_length': 0.2}, {'stock_width': 0.06}, {'quill': 0.01}):
        try:
            S.rotary_fixture_setup(**bad)
            check(f'rotaryFixtureSetup rejects {bad}', False)
        except ValueError:
            check(f'rotaryFixtureSetup rejects {bad}', True)
    arm = json.load(open(os.path.join(DUMP, 'articulated__mechanisms.json'), encoding='utf-8'))
    rep = json.load(open(os.path.join(REPO, 'eidoverse', 'assets', 'robotics', 'metadata', 'articulated.json'),
                         encoding='utf-8'))
    ik = S.SerialArm(rep)
    wf, wj, wi = 0.0, 0.0, 0.0
    for c in arm['ik']:
        f = ik.forward(c['q'], True)
        wf = max(wf, worst(f['transform'], c['forward']))
        wj = max(wj, worst(f['jacobian'], c['jacobian']))
        inv = ik.inverse(c['forward'], [0, 0.3, -0.5, 0, 0.3, 0])
        wi = max(wi, worst(inv, c['inverse']) if inv and c['inverse'] else (0 if inv == c['inverse'] else math.inf))
        # and the solution actually reaches the target
        if inv:
            t = ik.forward(inv)
            wi = max(wi, 0 if worst(t, c['forward']) < 1e-4 else math.inf)
    check('SerialArm.forward matches serial_arm.js', wf < 1e-12, f'worst {wf:.2e}')
    check('SerialArm Jacobian matches', wj < 1e-12, f'worst {wj:.2e}')
    check('SerialArm.inverse matches (damped least squares, same iterate)', wi < 1e-9, f'worst {wi:.2e}')
    far = [[1, 0, 0, 3.0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    check('SerialArm.inverse returns None for an unreachable target', ik.inverse(far) is None)
    try:
        ik.inverse([[1, 0, 0, math.nan]] * 4)
        check('SerialArm.inverse rejects a non-finite target', False)
    except ValueError:
        check('SerialArm.inverse rejects a non-finite target', True)
    print(f'{len(FAILS)} failed' if FAILS else 'ALL PASS')
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
