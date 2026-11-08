"""The 2D moisture history against Eanpa's own contract (qa/rain-accumulation-contract.js), check for check.

    python -B blender/tests/weather/test_moisture_contract.py

No Blender needed. The same synthetic weather as the GPU contract: rain 0.7, wet target 0.85, a cloud cell over x < 0
only, radius 256 m at 128 texels, samples at (-80, 48) and (80, 48), an upper surface over the first column, and a
point outside the field. Then the extra numbers a film needs: the time constants, and a frame-rate-independent
result (refreshing at 4 Hz under 24 and 60 fps gives the same water). Prints PASS/FAIL lines.
"""
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from eidoblend.weather.moisture import RainAccumulationField  # noqa: E402

fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''))
    if not ok:
        fails.append(name)


supply = {'v': 0.0}
field = RainAccumulationField(lambda x, y: np.where(x < 0, supply['v'], 0.0), radius=256, resolution=128)
# three points [-80,0,-48] [80,0,-48] [-80,40,-48] [270,0,-48] -> Blender (x, 48), heights do not matter (columns)
PX = np.array([-80.0, 80.0, -80.0, 270.0])
PY = np.array([48.0, 48.0, 48.0, 48.0])
RAIN, TARGET = 0.7, 0.85
cam = [0.0, 0.0]


def sample():
    return field.sample(PX, PY)


field.prepare(cam, 0, RAIN, TARGET)
field.prepare(cam, 30, RAIN, TARGET)
dry = sample()
check('dry cells do not accumulate water', np.all(dry == 0))
supply['v'] = 1.0
field.prepare(cam, 30, RAIN, TARGET, force=True)
arrival = sample()
check('rain arrives before water accumulates', np.all(arrival[0] == 0))
start = field.stats['captures']
sub = []
for dt in (0.05, 0.1, 0.15):
    field.prepare(cam, 30 + dt, RAIN, TARGET)
    sub.append(sample()[0])
check('wetness evolves between captures', field.stats['captures'] == start and 0 < sub[0][0] < sub[1][0] < sub[2][0],
      str([round(float(s[0]), 5) for s in sub]))
check('thin wetness precedes pooled water', all(s[0] > s[1] * 3 for s in sub))
field.prepare(cam, 60, RAIN, TARGET)
soaked = sample()
check('rain fills exposed columns', soaked[0][0] > 0.8 and soaked[0][1] > 0.4, str(soaked[0]))
check('nearby dry column stays dry', np.all(soaked[1] == 0))
check('upper surfaces share local rainfall', np.all(soaked[0] == soaked[2]))
check('outside the tracked footprint remains dry', np.all(soaked[3] == 0))
supply['v'] = 0.0
field.prepare(cam, 60, RAIN, TARGET, force=True)
stopped = sample()
check('same-time refresh does not add or remove water', np.all(np.abs(stopped[0] - soaked[0]) < 0.001))
field.prepare(cam, 65, RAIN, TARGET)
drying = sample()
check('puddles persist and dry gradually', 0.7 < drying[0][0] < soaked[0][0] and 0.35 < drying[0][1] < soaked[0][1],
      str(drying[0]))
cam = [100.0, 0.0]
field.prepare(cam, 65, RAIN, TARGET)
moved = sample()
check('camera recentre preserves overlapping water history', np.all(np.abs(moved[0] - drying[0]) < 0.001))
check('newly tracked dry columns start dry', np.all(moved[3] == 0))
field.prepare(cam, 10, RAIN, TARGET)
check('time rewind clears future water history', np.all(sample() == 0))

# ---- time constants a film depends on: 7 s to wet, 32 s to pool, 70 s / 150 s to dry ----
f2 = RainAccumulationField(lambda x, y: np.ones_like(x), radius=256, resolution=64)
f2.prepare([0, 0], 0, 1.0, 1.0)
f2.prepare([0, 0], 0.0, 1.0, 1.0, force=True)
for s in range(1, 7 * 24 + 1):
    f2.prepare([0, 0], s / 24, 1.0, 1.0)
w7, p7 = f2.sample(0.0, 0.0)[0]
check('after 7 s of full rain: wet = 1 - 1/e, water just starting', abs(w7 - (1 - math.exp(-1))) < 0.002 and p7 < 0.25,
      f'wet {w7:.4f} water {p7:.4f}')
for s in range(7 * 24 + 1, 32 * 24 + 1):
    f2.prepare([0, 0], s / 24, 1.0, 1.0)
w32, p32 = f2.sample(0.0, 0.0)[0]
check('after 32 s: water = 1 - 1/e', abs(p32 - (1 - math.exp(-1))) < 0.002, f'water {p32:.4f}')


def run(fps, seconds=20.0):
    f = RainAccumulationField(lambda x, y: np.ones_like(x), radius=256, resolution=64)
    for s in range(int(seconds * fps) + 1):
        f.prepare([0, 0], s / fps, 1.0, 1.0)
    return f.sample(0.0, 0.0)[0]


a, b = run(24), run(60)
check('24 fps and 60 fps give the same moisture at 20 s (4 Hz history, analytic in between)',
      np.all(np.abs(a - b) < 1e-9), f'{a} vs {b}')
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails))
sys.exit(0 if not fails else 1)
