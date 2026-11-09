"""race_parity.py: the Blender race's pure half (eidoblend/sets/unknown_force/race.py: the moving parts' time controls,
the car path, the crash, the debris, the boot, update()'s state, camAt, focal, the lamp heads, the noise atlas and the
night environment) against what the WebGPU race.js computes (race_parity_dump.mjs writes out/parity/race.json first).
race.js's suggest(t), its cut on the music video's clock, is not ported; it serves here as the test vector for the
time controls that replace it (sequence() at the same event times must give the same car, screens, gaze, march and
boot).

    cd <worktree> && deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_race_bin/race_parity_dump.mjs
    python blender/tests/sets_uf_race_bin/race_parity.py

Runs in plain Python (no Blender). Prints PASS / FAIL per check; exit 1 on any FAIL.
"""
import base64
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sets.unknown_force import race as R  # noqa: E402

J = json.load(open(os.path.join(HERE, 'out', 'parity', 'race.json')))
fails = []


def check(name, ok, info=''):
    print(('PASS' if ok else 'FAIL'), name, info, flush=True)
    if not ok:
        fails.append(name)


def close(a, b, tol=1e-6):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return a.shape == b.shape and np.allclose(a, b, atol=tol, rtol=0), float(np.max(np.abs(a - b))) if a.shape == b.shape else -1


path = R.car_path()
check('car path length', abs(path.length() - J['CAR_LEN']) < 1e-9, f"{path.length():.9f} vs {J['CAR_LEN']:.9f}")
check('CAR_LEN constant', abs(R.CAR_LEN - J['CAR_LEN']) < 0.01)
worst = 0.0
for s in J['path']:
    ok1, e1 = close(path.point_at(s['u']), s['p'], 1e-9)
    ok2, e2 = close(path.tangent_at(s['u']), s['t'], 1e-7)
    worst = max(worst, e1, e2)
check('path points and tangents (41 samples)', worst < 1e-7, f'max err {worst:.2e}')
start, tg = path.point_at(1), path.tangent_at(1)
worst = 0.0
for c in J['crash']:
    p = R.crash_pose(c['tc'], start, math.atan2(tg[0], tg[2]))
    for k in ('pitch', 'roll', 'yaw', 'spin'):
        worst = max(worst, abs(p[k] - c[k]))
    worst = max(worst, float(np.max(np.abs(np.array(p['com']) - c['com']))))
check('crash poses (10 times)', worst < 1e-9, f'max err {worst:.2e}')
deb = R.debris_specs(path)
ok = len(deb) == len(J['debris'])
worst = 0.0
for d, e in zip(deb, J['debris']):
    worst = max(worst, abs(d['s0'] - e['s0']), max(abs(a - b) for a, b in zip(d['home'], e['home'])),
                max(abs(a - b) for a, b in zip(d['v'], e['v'])), abs(d['r'] - e['r']))
check('debris specs', ok and worst < 1e-9, f'{len(deb)} pieces, max err {worst:.2e}')
heads = [h[:3] for h in R.lamp_heads()]
check('lamp heads', len(heads) == len(J['heads']) and close(heads, J['heads'], 1e-9)[0], f'{len(heads)} heads')
C = J['CUES']                    # race.js's event times on the video's clock: test vectors, not part of the port
EVENTS = dict(bill_a_on=(C['v3'] - 0.4, C['v3'] + 0.5), bill_b_on=(C['prevent'] - 2.4, C['prevent'] - 1.6),
              glance_from=C['machineGod'], car_edge=C['bow'] - 0.12,
              march_on=(C['lastTime'] + 0.5, C['blackShirts'] - 0.1),
              heel_strike=C['heel'] - 1.5 + R.HEEL['strike'] * R.HEEL['dur'])
worst_s, n_s = 0.0, 0
keymap = {'carT': 'car_t', 'billA': 'bill_a', 'billB': 'bill_b'}
for s in J['suggest']:
    m = R.sequence(s['t'], **EVENTS)
    for k, v in s['state'].items():
        kk = keymap.get(k, k)
        if kk in ('rain', 'billboards', 'lamps'):            # constants of suggest's, update()'s defaults
            continue
        if kk == 'heel' and s['cam'] != 'heel':              # suggest hid the boot outside its own shot (the cut)
            continue
        worst_s = max(worst_s, abs(m.get(kk, 0.0) - v))
        n_s += 1
check("the time controls (sequence: ease_in, glance, car_drive, heel_stamp) are race.js's suggest at its event times",
      worst_s < 1e-9, f'{n_s} values over {len(J["suggest"])} times, max err {worst_s:.1e}')
check('no music-video clock in the module (CUES, suggest, film_state, film_cut, FILM_SPANS left out)',
      not any(hasattr(R, k) for k in ('CUES', 'suggest', 'film_state', 'film_cut', 'FILM_SPANS')))
d = R.car_drive(10.0, 12.0, 30.0)
check('car_drive: another speed reaches the edge on time and carries its own car_v; heel_stamp strikes on time',
      abs(d['car_t'] - (R.CAR_LEN - 60.0) / R.CAR_LEN) < 1e-12 and d['car_v'] == 30.0 and d['crash'] == 0.0
      and R.car_drive(13.5, 12.0)['crash'] == 0.5 and R.heel_stamp(5.0, 5.0) == R.HEEL['strike'])

# update(): every case
UK = {'time': 'time', 'rain': 'rain', 'wet': 'wet', 'lamps': 'lamps', 'billA': 'bill_a', 'billB': 'bill_b', 'gaze': 'gaze',
      'march': 'march', 'marchT': 'march_t', 'crashAge': 'crash_age', 'crashP': 'crash_p', 'flipAge': 'flip_age',
      'flipP': 'flip_p', 'heelAge': 'heel_age', 'works': 'works', 'smear': 'smear', 'chainRun': 'chain_run',
      'scarfSpeed': 'scarf_speed', 'carShadow': 'car_shadow', 'steam': 'steam', 'steamP': 'steam_p',
      'headlamps': 'headlamps', 'heelKey': 'heel_key'}
SK = {'carT': 'car_t', 'carS': 'car_s', 'carV': 'car_v', 'billA': 'bill_a', 'billB': 'bill_b', 'marchT': 'march_t',
      'backRim': 'back_rim'}
worst = {}


def upd(k, e):
    worst[k] = max(worst.get(k, 0.0), e)


for c in J['update']:
    state = {SK.get(k, k): v for k, v in c['state'].items()}
    rs = R.race_state(c['t'], state, path, deb)
    car = rs['car']
    upd('car.visible', 0 if car['visible'] == c['car']['visible'] else 1)
    if c['car']['visible'] or True:
        upd('car.pos', float(np.max(np.abs(np.array(car['pos']) - c['car']['pos']))))
        q = np.array(car['q'])
        qe = np.array(c['car']['q'])
        upd('car.q', float(min(np.max(np.abs(q - qe)), np.max(np.abs(q + qe)))))
        upd('body', float(np.max(np.abs(np.array(car['body_pos']) - c['car']['body_pos']))))
        upd('body', float(np.max(np.abs(np.array(car['body_rot']) - c['car']['body_rot']))))
    upd('wheel_ang', abs(rs['wheel_ang'] - c['wheel_ang']))
    for (p, r), e in zip(rs['debris'], c['debris']):
        upd('debris', float(np.max(np.abs(np.array(p) - e['pos']))))
        upd('debris', float(np.max(np.abs(np.array(r) - e['rot']))))
    # race.js leaves the boot's pose, and the impact points, as they were while they do not show (hidden boot,
    # ages at -10, no steam); the port resets them so update() stays a pure function of (t, state)
    upd('heel', (0 if rs['heel']['visible'] == c['heel']['visible'] else 1)
        + ((abs(rs['heel']['y'] - c['heel']['y']) + abs(rs['heel']['pitch'] - c['heel']['pitch'])) if c['heel']['visible'] else 0))
    if c['U']['crashAge'] < -9:
        for k in ('crashP', 'flipP', 'steamP'):
            c['U'].pop(k)
    upd('shadow', float(np.max(np.abs(np.array(rs['shadow']['pos']) - c['shadow']['pos']))))
    upd('beam', float(np.max(np.abs(np.array(rs['beam']['pos']) - c['beam']['pos']))))
    upd('beam', float(np.max(np.abs(np.array(rs['beam']['target']) - c['beam']['target']))))
    upd('beam', abs(rs['beam']['i'] - c['beam']['i']))
    LK = {'key': 'key', 'glowA': 'glow_a', 'glowB': 'glow_b', 'rim': 'rim', 'backRim': 'back_rim', 'neonFill': 'neon_fill',
          'hemi': 'hemi'}
    for k, v in c['lights'].items():
        upd('lights', abs(rs['lights'][LK[k]] - v))
    for k, v in c['U'].items():
        mine = rs['U'][UK[k]]
        upd('U.' + UK[k], float(np.max(np.abs(np.asarray(mine, float) - np.asarray(v, float)))))
    for n, cam in c['cams'].items():
        mine = R.cam_at_three(n, c['t'], state, rs, path)
        if cam is None or mine is None:
            upd('camAt', 0 if (cam is None) == (mine is None) else 1)
            continue
        upd('camAt', float(np.max(np.abs(np.array(mine['pos']) - cam['pos']))))
        upd('camAt', float(np.max(np.abs(np.array(mine['target']) - cam['target']))))
        upd('camAt', abs(mine['fov'] - cam['fov']) + abs(mine.get('roll', 0) - cam.get('roll', 0)))
for k, e in sorted(worst.items()):
    check(f'update(): {k}', e < 1e-6, f'max err {e:.2e} over {len(J["update"])} cases')

ok = all(R.FOCAL.get(n, R.FOCAL['singer']) == list(v) for n, v in J['focal'].items())
check('focal(name)', ok)
ok = all(R.CAMS[n]['pos'] == c['pos'] and R.CAMS[n]['target'] == c['target'] and R.CAMS[n]['fov'] == c['fov']
         and R.CAMS[n].get('roll', 0) == c.get('roll', 0) for n, c in J['cams'].items()) and len(R.CAMS) == len(J['cams'])
check('cams', ok, f'{len(J["cams"])} cameras')

na = R.noise_atlas()
js = np.frombuffer(base64.b64decode(J['tex_256x256']), np.uint8).reshape(256, 256, 4)
d = np.abs(na.astype(int) - js.astype(int))
check('noise atlas 256^2', d.max() <= 1 and (d > 0).mean() < 1e-3, f'max diff {d.max()}, differing {(d > 0).mean() * 100:.4f}%')
env = R.night_env()
je = np.frombuffer(base64.b64decode(J['tex_512x256']), np.uint8).reshape(256, 512, 4)
d = np.abs(env.astype(int) - je.astype(int))
check('night environment 512x256', d.max() <= 1 and (d > 0).mean() < 1e-3, f'max diff {d.max()}, differing {(d > 0).mean() * 100:.4f}%')

print('race_parity:', 'ALL PASS' if not fails else f'{len(fails)} FAIL: {fails}')
sys.exit(1 if fails else 0)
