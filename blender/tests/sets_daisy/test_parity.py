"""tests/sets_daisy/test_parity.py: the DAISY sets' Blender ports against their WebGPU source, number for number.

parity_dump.mjs evaluates blocks cut from eidoverse/sets/funeral.js and corner.js themselves (deno, three's
CatmullRomCurve3); this compares the Python ports: the crowd (mulberry32 placements, facing, phone and arm timings),
the candles, the ERUPT motes, the festoon bulbs (centripetal Catmull-Rom + arc length), the 13 shots, the power curve
and the phones; the march (Lehmer rows), the chant accents, the string-light bulbs, the spark (path, easing, trail
births) and the corner's 11 shots. No render, no GPU:

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy/test_parity.py
"""

import json
import math
import os
import subprocess
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _common as C                                        # noqa: E402
import _where                                               # noqa: E402  (blender/tests/_where.py, on _common's path)

from mathutils import Vector                                # noqa: E402

from eidoblend.sets.daisy import corner as CO               # noqa: E402
from eidoblend.sets.daisy import funeral as FU              # noqa: E402

THREE = os.environ.get('THREE_MODULE', (_where.main_checkout() / 'node_modules/three/build/three.module.js').as_posix())
DENO = os.environ.get('DENO', 'deno')
BULB_B = Vector((-1.930, 1.760, 1.149))           # the lamp bulb's centre, room-local Blender (from the GLB, as built)
BULB3 = (BULB_B.x, BULB_B.z, -BULB_B.y)
r = subprocess.run([DENO, 'run', '--no-config', '--no-lock', '-A', os.path.join(HERE, 'parity_dump.mjs'),
                    os.path.join(C.WORKTREE, 'eidoverse'), THREE, ','.join(f'{x:.6f}' for x in BULB3)],
                   capture_output=True, text=True, encoding='utf-8')
if r.returncode != 0:
    print(r.stderr[-2000:])
    C.check('deno dump', False, f'exit {r.returncode}')
    sys.exit(1)
J = json.loads(r.stdout)


def maxdiff(a, b):
    return max((abs(x - y) for x, y in zip(a, b)), default=0.0)


# ------------------------------------------------------------------------------------------------ the funeral
jf = J['funeral']
with open(os.path.join(FU.PACK, 'funeral_layout.json'), encoding='utf-8') as f:
    layout = json.load(f)
fake = SimpleNamespace(layout=layout, beats=json.loads(json.dumps(FU.BEATS)))
C.check('BEATS', all(abs(jf['beats'][k] - FU.BEATS[s]) < 1e-12 for k, s in
                     (('bridgeEnd', 'bridge_end'), ('fail', 'fail'), ('breaker', 'breaker'), ('hum', 'hum'),
                      ('erupt', 'erupt'), ('lightsOn', 'lights_on'), ('end', 'end')))
        and maxdiff(sum(jf['beats']['lines'], []), sum(FU.BEATS['lines'], [])) < 1e-12)
lr = [math.hypot(p[0], (p[2] - 7.5) * 0.8) * 0.028 for p in layout['lamps']]
C.check('lamp relight stagger', maxdiff(lr, jf['lampRelight']) < 1e-12)
cand = FU.Funeral.candle_placements(fake)
C.check('candles (mulberry 31): 73, every number', len(cand) == len(jf['candles']) and
        maxdiff(sum(cand, []), sum(jf['candles'], [])) < 1e-12, f'{len(cand)} vs {len(jf["candles"])}')
ppl = FU.Funeral.crowd_placements(fake)
keys = ('x', 'y', 'z', 'variant', 'yaw', 'scale', 'tOn', 'hold', 'tUp', 'up', 'seed', 'bowK')
py = [[float(p[k]) for k in keys] + [1.0 if p.get('mezz') else 0.0] for p in ppl]
C.check('crowd (mulberry 1234): 200 people, every number', len(py) == len(jf['people']) and
        maxdiff(sum(py, []), sum(jf['people'], [])) < 1e-9, f'{len(py)} vs {len(jf["people"])}, '
        f'max diff {maxdiff(sum(py, []), sum(jf["people"], [])):.2e}')
# the motes (mulberry 77) from the same people
rr = FU.mulberry(77)
P0, V0 = [], []
for i in range(520):
    p = ppl[int(math.floor(rr() * len(ppl)))]
    P0 += [p['x'] + (rr() - 0.5) * 0.5, p['y'] + 1.6 + rr() * 0.8, p['z'] + (rr() - 0.5) * 0.5, FU.BEATS['erupt'] + rr() * 1.6]
    V0 += [(rr() - 0.5) * 0.35, 0.45 + rr() * 0.9, (rr() - 0.5) * 0.35, 3.0 + rr() * 3.5]
C.check('ERUPT motes (mulberry 77)', maxdiff(P0, jf['motesP']) < 1e-5 and maxdiff(V0, jf['motesV']) < 1e-5,
        f'{maxdiff(P0, jf["motesP"]):.1e}')
# the festoon bulbs: three's CatmullRomCurve3.getPointAt vs the port
tz = layout['truss_z']
bp = []
for x in (-6.75, -2.25, 2.25, 6.75):
    pts = []
    for k in range(len(tz) - 1):
        for j in range(8):
            f = j / 8
            pts.append([x, 5.62 - 0.42 * 4 * f * (1 - f), FU.lerp(tz[k], tz[k + 1], f)])
    pts.append([x, 5.62, tz[-1]])
    cv = FU.CatmullRom(pts)
    Lc = cv.length()
    d = 0.2
    while d < Lc:
        p = cv.point_at(d / Lc)
        bp.append([p[0], p[1] - 0.055, p[2]])
        d += 0.48
C.check('festoon bulbs (centripetal Catmull-Rom, arc length)', len(bp) == len(jf['festoon']) and
        maxdiff(sum(bp, []), sum(jf['festoon'], [])) < 1e-6, f'{len(bp)} bulbs, max diff {maxdiff(sum(bp, []), sum(jf["festoon"], [])):.1e}')
shots = []
for u in jf['us']:
    s = FU.Funeral.shot_at(fake, u)
    shots.append([s['pos'].x, s['pos'].z, -s['pos'].y, s['target'].x, s['target'].z, -s['target'].y, s['fov']])
C.check('the 13 shots (positions, aims, fov) at 92 times (mathutils floats are 32-bit: 6e-5 m at the bridge, 700 m out)',
        maxdiff(sum(shots, []), sum(jf['shots'], [])) < 1e-4, f'max diff {maxdiff(sum(shots, []), sum(jf["shots"], [])):.1e}')
C.check('the power curve (sag, mains hum, clicks, breaker)',
        maxdiff([FU.Funeral.power(fake, u) for u in jf['us']], jf['power']) < 1e-9)
C.check('the phones waking', maxdiff([FU.Funeral.phone_frac(fake, u) for u in jf['us']], jf['phone']) < 1e-9)

# ------------------------------------------------------------------------------------------------- the corner
jc = J['corner']
cf = SimpleNamespace(room={'bulb_pos': BULB_B}, spark={}, to_set=CO.Corner.to_set)
pts, dest, fwd = CO.spark_path(BULB3)
cf.spark.update({'curve': FU.CatmullRom(pts), 'dest': dest, 'fwd': fwd, 't0': CO.B(26) + 1.17, 't1': CO.B(28) - 0.2, 'N': 56})
cf._bulb3 = lambda: CO.Corner._bulb3(cf)
rows = CO.Corner.march_rows(cf)
rk = ('x', 'z', 'sx', 'sz', 'tStart', 'tArr', 'yaw', 'scale', 'phase', 'delay', 'amp', 'sign', 'variant')
pyr = [[float(r_[k]) for k in rk] + [1.0 if r_['hasSign'] else 0.0] for r_ in rows]
C.check('the march (Lehmer 909): 34 rows, every number', len(pyr) == len(jc['rows']) and
        maxdiff(sum(pyr, []), sum(jc['rows'], [])) < 1e-9, f'max diff {maxdiff(sum(pyr, []), sum(jc["rows"], [])):.1e}')
C.check('the chant accents', maxdiff(CO.CHANT_ACCENTS, jc['chant']) < 1e-12)
yaw, wires, bulbs = CO.string_light_points()
C.check('the string lights: pole yaws and 131 bulbs on the catenaries', maxdiff(yaw, jc['poleYaw']) < 1e-12 and
        len(bulbs) == len(jc['bulbPts']) and maxdiff(sum(bulbs, []), sum(jc['bulbPts'], [])) < 1e-9,
        f'{len(bulbs)} vs {len(jc["bulbPts"])}')
C.check('the spark lands where the JS lands it', maxdiff(list(dest), jc['dest']) < 1e-12)
cvp = [list(cf.spark['curve'].point_at(s)) for s in (0, 0.1, 0.25, 0.5, 0.75, 0.9, 1)]
C.check('the spark path (three CatmullRomCurve3.getPointAt)', maxdiff(sum(cvp, []), sum(jc['curve'], [])) < 1e-6,
        f'{maxdiff(sum(cvp, []), sum(jc["curve"], [])):.1e}')
C.check('the spark easing', maxdiff([CO.spark_progress(u, cf.spark['t0'], cf.spark['t1']) for u in jc['us']], jc['progress']) < 1e-12)
C.check('the trail births (bisection)', maxdiff(CO.Corner._trail_births(cf), jc['births']) < 1e-5)
cams = []
for u in jc['us']:
    c = CO.Corner.camera(cf, u)
    # set-local Blender -> three set-local
    cams.append([c['pos'].x, c['pos'].z, -c['pos'].y, c['target'].x, c['target'].z, -c['target'].y, c['fov']])
C.check("the corner's 11 shots at 78 times (the spark's follow included)", maxdiff(sum(cams, []), sum(jc['cams'], [])) < 1e-5,
        f'max diff {maxdiff(sum(cams, []), sum(jc["cams"], [])):.1e}')
C.check('areas and moods', [CO.area_at(u) for u in jc['us']] == jc['areas'] and [CO.mood_at(u) for u in jc['us']] == jc['moods'])
sys.exit(1 if C.summary('test_parity') else 0)
