"""Compare the Python port's plain maths with the WebGPU sources run under deno (js_parity.mjs writes the JSON).

    deno run --no-config --no-lock -A blender/tests/sky_worlds/js_parity.mjs <three build> <Eanpa engine dir> out.json
    python blender/tests/sky_worlds/js_parity.py out.json

Prints a PASS/FAIL line per system: the red giant's flare envelopes and shield impacts (redgiant.py), the ring's solar
visibility (ringworld.ring_solar_visibility), the shattered moon's fragment motion (asteroid_moon.FragmentMotion).
No Blender needed.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky.redgiant import make_red_giant, flare_env, FLARES  # noqa: E402
from eidoblend.sky.ringworld import ring_solar_visibility  # noqa: E402
from eidoblend.sky.asteroid_moon import FragmentMotion  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'out', 'parity', 'js_parity.json')
d = json.load(open(path))
ok_all = True


def report(name, err, tol):
    global ok_all
    ok = err <= tol
    ok_all &= ok
    print('%s %s  (max abs difference %.3g, tolerance %.3g)' % ('PASS' if ok else 'FAIL', name, err, tol))


# ---- red giant ----
err = 0.0
for row in d['redgiant']['flares']:
    for f, v in zip(FLARES, row['env']):
        err = max(err, abs(flare_env(f, row['t']) - v))
report('red giant flareEnv, %d slots x %d times' % (len(FLARES), len(d['redgiant']['flares'])), err, 1e-12)


class _Sky:
    def __init__(self):
        self.U = {}
        self.sun_dir = (0, 1, 0)
        self.celestial_module = None


rg = make_red_giant({'shield': True})
sky = _Sky()
rg.attach(sky)
err = err_b = 0.0
for row in d['redgiant']['impacts']:
    sky.sun_dir = tuple(row['sun'])
    rg.update(row['t'])
    for mine, js in zip(rg.impacts, row['imp']):
        err = max(err, max(abs(a - b) for a, b in zip(mine, js)))
    err_b = max(err_b, abs(rg.burst_k - row['burst']))
report('red giant shield impacts (plane xy, birth, amplitude) at 6 times', err, 1e-9)
report('red giant live flare envelope burstK', err_b, 1e-12)

# ---- ring eclipse ----
err = 0.0
for row in d['eclipse']:
    v = ring_solar_visibility(row['p'], row['sun'], center=(0.0, 4921.6, 0.45))
    err = max(err, abs(v - row['v']))
report('ring solar visibility over %d sun / receiver pairs' % len(d['eclipse']), err, 1e-9)

# ---- fragment motion ----
for key in ('frag', 'frag2'):
    fr = d.get(key)
    if fr is None:
        continue
    pos = [s[:3] for s in fr['spec']]
    radii = [s[3] for s in fr['spec']]
    fm = FragmentMotion(pos, radii, spread=1.75)
    err = max(abs(a - b) for mine, js in zip(fm.base_positions, fr['base']) for a, b in zip(mine, js))
    report('%s: separated base positions, %d separation passes (JS %d), hero %d (JS %d)'
           % (key, fm.stats['iterations'], fr['stats']['iterations'], fm.hero_index, fr['hero']), err, 1e-9)
    err = errq = 0.0
    for frame in fr['frames']:
        p, q = fm.update(frame['t'])
        for a, b in zip(p, frame['pos']):
            err = max(err, max(abs(x - y) for x, y in zip(a, b)))
        for a, b in zip(q, frame['quat']):          # three's quaternion is (x, y, z, w); ours (w, x, y, z)
            errq = max(errq, max(abs(x - y) for x, y in zip((a[1], a[2], a[3], a[0]), b)))
    report('%s: update(t) positions at %d times' % (key, len(fr['frames'])), err, 1e-9)
    report('%s: update(t) tumble quaternions' % key, errq, 1e-9)
print('PASS js parity all' if ok_all else 'FAIL js parity some')
