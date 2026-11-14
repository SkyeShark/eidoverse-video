"""The lightning port against eidoverse/weather_system.js itself, frame for frame. No Blender needed.

    python -B blender/tests/weather/test_lightning_parity.py

lightning_parity.mjs runs the engine's own makeWeatherSystem under deno over a 150 s storm (overcast -> storm ->
darkstorm, a forced strike, cyclone, clear, darkstorm at k 0.8, then time runs backwards) with a moving camera and a
small target set (ground, a flat roof, foliage and glass that must be skipped, a ramp too steep to strike). This test
feeds the same live weather def, k, transition target and camera into eidoblend.weather.lightning.LightningScheduler,
with an exact ray cast of the same targets, and compares: the profile tables, every frame's flash, scene light,
bolt visibility and sky strike uniform, every strike record, every bolt ribbon (vertex for vertex), the impact
sparks, puffs and scorches, the local-impact counters, and rainLight / rainColor. Prints PASS/FAIL lines.
"""
import json
import math
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
import _where  # noqa: E402

MAIN = _where.main_checkout()             # deno's working folder, as lightning_parity.mjs asks: the main checkout
sys.path.insert(0, str(WORKTREE / 'blender'))
from eidoblend.weather import lightning as L  # noqa: E402
from eidoblend.weather.bolt import bolt_ribbon  # noqa: E402
from eidoblend.weather.frame import rain_light  # noqa: E402

OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
JS = OUT / 'lightning_js.json'
if '--reuse' not in sys.argv or not JS.exists():
    r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '--cached-only', '-A', str(HERE / 'lightning_parity.mjs'),
                        str(JS)], cwd=str(MAIN), capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        sys.exit(2)
data = json.loads(JS.read_text())
frames = data['frames']
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''))
    if not ok:
        fails.append(name)


def close(a, b, tol=1e-6):
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


# ---- the profile tables ----
P = data['profile']
mine = [[L.lightning_event_gap_at(i, 'standard', 0.3), L.lightning_event_gap_at(i, 'darkstorm', 0.5),
         L.lightning_initial_event_gap_at(i, 'darkstorm', 0.85)] for i in (1, 2, 3, 7, 11)]
check('profile eventGapAt / initialEventGapAt (gap scale 0.42)', close(mine, P['gaps'], 1e-9))
mp = [[L.lightning_stroke_plan_at(i, 'standard'), L.lightning_stroke_plan_at(i, 'darkstorm')] for i in range(1, 11)]
ok = all(a['count'] == b['count'] and close(a['offsets'], b['offsets'], 1e-9) and close(a['amplitudes'], b['amplitudes'], 1e-9)
         and close(a['durationSeconds'], b['durationSeconds'], 1e-9)
         for pa, pb in zip(mp, P['plans']) for a, b in zip(pa, pb))
check('profile strokePlanAt (counts, offsets, amplitudes)', ok)
check('profile styleKeyAt', [[L.lightning_style_key_at(i, 'standard'), L.lightning_style_key_at(i, 'darkstorm')]
                              for i in range(40)] == P['styles'])
plan3 = L.lightning_stroke_plan_at(3, 'standard')
check('profile flashAt', close([L.lightning_flash_at(e, plan3) for e in (0, 0.01, 0.05, 0.1, 0.2, 0.4)], P['flash'], 1e-9))
loc = [L.lightning_local_candidate_at(i, 0.16, palette_name='darkstorm' if i % 2 else 'standard',
                                      entry_event_count=i % 3, remote_events_since_local=i % 7,
                                      has_local_strike=i % 4 == 0) for i in range(30)]
check('profile localCandidateAt', loc == P['local'])
check('style colours (three Color.setHex, linear)',
      all(close(L.style_color(k), v, 1e-6) for k, v in P['colors'].items()))

# ---- the targets, ray cast exactly ----
S50, C50 = math.sin(math.radians(50)), math.cos(math.radians(50))


def column_hits(x, z):
    hits = []
    if abs(x) < 2000 and abs(z) < 2000:
        hits.append((0.0, (0.0, 1.0, 0.0), 'ground', False))
    if abs(x - 40) <= 15 and abs(z + 80) <= 15:
        hits.append((20.0, (0.0, 1.0, 0.0), 'building', False))
    if abs(x + 50) <= 10 and abs(z + 60) <= 10:
        hits.append((8.0, (0.0, 1.0, 0.0), 'foliage_clump', True))
    if abs(x) <= 10 and abs(z + 150) <= 10:
        hits.append((6.1, (0.0, 1.0, 0.0), 'canopy', True))
    u = (x - 100) / C50
    if abs(u) <= 10 and abs(z + 200) <= 10:
        hits.append((5 + u * S50, (-S50, C50, 0.0), 'ramp', False))
    return sorted(hits, key=lambda h: -h[0])


def find_local_strike(interval, cam, sky, prefer_forward):
    for x, z in L.strike_candidates(interval, cam['pos'], cam['forward'], prefer_forward):
        for y, n, name, blocked in column_hits(x, z):
            if blocked or n[1] < L.UPWARD_NORMAL_MIN:
                continue
            if math.hypot(x - cam['pos'][0], z - cam['pos'][2]) < L.LOCAL_STRIKE_PLAYER_GUARD:
                continue
            return dict(point=(x, y, z), normal=n, kind=name, object=name)
    return None


def weather_at(x, z):
    return 1.0 + 0.5 * math.sin(x * 0.01) * math.cos(z * 0.013)


sch = L.LightningScheduler(storm_center=(0, -300), storm_range=400, find_local_strike=find_local_strike)
FPS = data['fps']
mism = dict(flash=0, light=0, lightpos=0, bolt=0, sky=0, counters=0, rain=0, next=0)
first_bad = {}
strikes_js = [f for f in frames if 'strike' in f]
strikes_py = []
fx_checked = dict(spark=0, puff=0, scorch=0)
fx_bad = []
prev = None
last_light = None


def note(key, i, detail):
    mism[key] += 1
    first_bad.setdefault(key, (i, detail))


def qmul(a, b):          # three quaternions (x, y, z, w)
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def quat_from_units(a, b):      # three Quaternion.setFromUnitVectors
    r = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + 1
    if r < 1e-8:
        q = (-a[1], a[0], 0.0, 0.0) if abs(a[0]) > abs(a[2]) else (0.0, -a[2], a[1], 0.0)
        r = 0.0
    else:
        q = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    q = (q[0], q[1], q[2], r)
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)


def same_quat(a, b, tol=1e-5):
    return close(a, b, tol) or close(a, [-c for c in b], tol)


def _qrot(q, v):
    x, y, z, w = q
    t = [2 * c for c in (y * v[2] - z * v[1], z * v[0] - x * v[2], x * v[1] - y * v[0])]
    return (v[0] + w * t[0] + (y * t[2] - z * t[1]), v[1] + w * t[1] + (z * t[0] - x * t[2]),
            v[2] + w * t[2] + (x * t[1] - y * t[0]))


audio_rows = []


for i, f in enumerate(frames):
    t = f['t']
    if f['t'] == 60.0 and prev is not None:        # debugForceLocalStrike(), called before update(60)
        wp = dict(lightning=prev['wl'])
        sch.force_local_strike(prev['t'], wp, prev['k'])
    w = dict(lightning=f['wl'], lightningPalette=f['wp'], distant=f['wd'], localStrikeChance=f['wlc'], sunDim=f['wsd'])
    w = {k: v for k, v in w.items() if v is not None}
    cam = dict(pos=f['cam'], forward=f['fwd'])
    sky = dict(cloudStart=f['cs'], cloudHeight=f['ch'], weather_at=weather_at)
    r = sch.step(t, w, f['k'], f['tgt'], cam, sky)
    if i < len(frames) - 6 * FPS:                    # the forward timeline the JS recorder heard
        q = f['quat']
        axes = [L._norm(_qrot(q, e)) for e in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
        pb = (f['cam'][0], -f['cam'][2], f['cam'][1])
        ab = [(a[0], -a[2], a[1]) for a in axes]
        cam_m = [[ab[0][k], ab[1][k], ab[2][k], pb[k]] for k in range(3)] + [[0, 0, 0, 1]]
        st = r['strike']
        sb = None if not st else dict(id=st['interval'], x=st['x'], y=-st['z'], z=st['y'], flash=st['flash'],
                                      local=st['local'])
        audio_rows.append(dict(t=t, rain_k=f['rainK'], dense_a=f['denseA'], wind_len=f['windLen'], strike_blender=sb,
                               cam_matrix=cam_m))
    if r['began'] and r['strike']:
        strikes_py.append((i, dict(r['strike']), sch.events[-1]))
    if not close(r['flash'], f['flash'], 1e-7):
        note('flash', i, (r['flash'], f['flash']))
    if not close(r['light_intensity'], f['lightI'], 1e-6):
        note('light', i, (r['light_intensity'], f['lightI']))
    if r['light_pos'] is not None:
        last_light = r['light_pos']
    if last_light is not None and not close(last_light, f['lightPos'], 1e-6):
        note('lightpos', i, (last_light, f['lightPos']))
    if r['bolt_visible'] != f['boltVis']:
        note('bolt', i, (r['bolt_visible'], f['boltVis']))
    if not close(list(r['sky_strike']), f['sky'], 1e-6):
        note('sky', i, (r['sky_strike'], f['sky']))
    li = sch.diag['localImpact']
    keys = ('strikes', 'candidateAttempts', 'forcedCandidates', 'raycastMisses', 'remoteEventsSinceStrike')
    if any(li[k] != f['li'][k] for k in keys) or sch.diag['eventCount'] != f['events']:
        note('counters', i, ({k: li[k] for k in keys}, {k: f['li'][k] for k in keys}))
    if not close(sch.diag['nextEventAtSeconds'], f['next'], 1e-9):
        note('next', i, (sch.diag['nextEventAtSeconds'], f['next']))
    pal = dict(zen=(0.16, 0.36, 0.78), hor=(0.66, 0.74, 0.86))
    rl, _lit, rc = rain_light(pal, w, f['canopy'], f['rainK'], r['flash'], r['flash_d'], r['color'])
    if not (close(rl, f['rainLight'], 1e-6) and close(list(rc), f['rainColor'], 1e-6)):
        note('rain', i, ((rl, rc), (f['rainLight'], f['rainColor'])))
    # the impact pool: sparks, puffs and scorches the JS drew this frame
    for imp in sch.impacts:
        age = t - imp['birth']
        if age <= 0:
            continue
        n3 = imp['data']['normal']
        slot = imp['slot']
        js_sp, js_pf = f['fx'][slot * 2], f['fx'][slot * 2 + 1]
        if age < imp['fx_end'] - imp['birth'] and age < L.SPARK_LIFE:
            if js_sp is None:
                fx_bad.append((i, 'spark hidden in JS'))
            else:
                for j, mj in zip((0, 1, 7), js_sp['m']):
                    pos, d, scl = L.spark_at(imp['point'], n3, imp['data']['sparks'][j], age)
                    q = quat_from_units((0, 1, 0), d)
                    if not (close(pos, mj['p'], 1e-5) and close(scl, mj['s'], 1e-5) and same_quat(q, mj['q'])):
                        fx_bad.append((i, 'spark', j, pos, mj['p']))
                fx_checked['spark'] += 1
        if age < imp['fx_end'] - imp['birth'] and age < L.PUFF_LIFE:
            if js_pf is None:
                fx_bad.append((i, 'puff hidden in JS'))
            else:
                for j, mj in zip((0, 1, 7), js_pf['m']):
                    pos, size, roll = L.puff_at(imp['point'], n3, imp['data']['puffs'][j], age)
                    q = qmul(tuple(f['quat']), (0.0, 0.0, math.sin(roll / 2), math.cos(roll / 2)))
                    if not (close(pos, mj['p'], 1e-5) and close([size] * 3, mj['s'], 1e-5) and same_quat(q, mj['q'])):
                        fx_bad.append((i, 'puff', j, pos, mj['p'], size, mj['s']))
                fx_checked['puff'] += 1
        if age < imp['scorch_end'] - imp['birth']:
            js_sc = f['fx'][4 + imp['scorch_slot']]
            if js_sc is None:
                fx_bad.append((i, 'scorch hidden in JS'))
            else:
                p = tuple(imp['point'][k] + n3[k] * 0.018 for k in range(3))
                s = imp['data']['scorch_size']
                q = quat_from_units((0, 0, 1), n3)
                if not (close(p, js_sc['p'], 1e-6) and close([s] * 3, js_sc['s'], 1e-6) and same_quat(q, js_sc['q'])):
                    fx_bad.append((i, 'scorch', p, js_sc['p']))
                fx_checked['scorch'] += 1
    prev = f

for key, n in mism.items():
    check(f'per-frame {key} over {len(frames)} frames', n == 0, '' if n == 0 else f'{n} differ, first {first_bad[key]}')
check(f'strike count ({len(strikes_js)} in JS)', len(strikes_py) == len(strikes_js), f'{len(strikes_py)} here')
bolt_ok = True
for (i, sp, ev), fj in zip(strikes_py, strikes_js):
    sj = fj['strike']
    same = (sp['id'] == sj['id'] and sp['interval'] == sj['interval'] and sp['local'] == sj['local']
            and sp['kind'] == sj['kind'] and sp['colorKey'] == sj['colorKey'] and close(sp['x'], sj['x'], 1e-9)
            and close(sp['z'], sj['z'], 1e-9) and close(sp['y'], sj['y'], 1e-9) and close(sp['normal'], sj['normal'], 1e-9))
    check(f"strike {sj['interval']} at t={sj['time']:.3f} ({'local ' + sj['kind'] if sj['local'] else 'distant'}, "
          f"{sj['colorKey']})", same, '' if same else f'{sp} vs {sj}')
    pos, uvs, tris = bolt_ribbon(ev['interval'], ev['cam']['pos'], sp['x'], sp['z'], sp['y'], ev['cloud_start'])
    jp = fj['bolt']['pos']
    ok = (len(pos) * 3 == len(jp) and close([c for p in pos for c in p], jp, 1e-4)
          and close([c for u in uvs for c in u], fj['bolt']['uv'], 1e-6)
          and [c for tr in tris for c in tr] == fj['bolt']['idx'])
    bolt_ok = bolt_ok and ok
    if not ok:
        print('   bolt', sj['interval'], len(pos), len(jp) // 3)
check(f'bolt ribbons vertex for vertex ({len(strikes_js)} events)', bolt_ok)
dam_js = [f['damage'] for f in strikes_js if f.get('damage')]
dam_py = [ev['damage'] for _i, _s, ev in strikes_py if ev['damage']]
check(f'surface-damage records ({len(dam_js)})', len(dam_js) == len(dam_py) and all(
    a['id'] == b['id'] and close(a['point'], b['point'], 1e-9) and a['kind'] == b['kind'] for a, b in zip(dam_py, dam_js)))
check(f"impact sparks / puffs / scorches drawn as the JS draws them ({fx_checked})", not fx_bad and min(fx_checked.values()) > 0,
      str(fx_bad[:3]))
# ---- the weather-audio timeline: weather_audio.js on the JS weather vs the port's frame records (Blender axes) ----
from eidoblend.weather.audio import record  # noqa: E402
mine = record(audio_rows).timeline()
ja = data['audio']
ev_ok = len(mine['events']) == len(ja['events']) and all(
    a['clip'] == b['clip'] and close(a['t'], b['t'], 1e-6) and close(a['gain'], b['gain'], 1e-4)
    and close(a['rate'], b['rate'], 1e-6) and close(a['offset'], b['offset'], 1e-6) and close(a['pan'], b['pan'], 2e-4)
    and a['distance'] == b['distance'] and a.get('lowpassHz') == b.get('lowpassHz')
    and a.get('highpassHz') == b.get('highpassHz') and a.get('stopAfter') == b.get('stopAfter')
    for a, b in zip(mine['events'], ja['events']))
check(f"audio: thunder events = weather_audio.js on the engine's weather ({len(ja['events'])} events, "
      f"{ja['stats']['explosive']} explosive / {ja['stats']['close']} close / {ja['stats']['distant']} distant)", ev_ok,
      '' if ev_ok else str(list(zip(mine['events'], ja['events']))[:2]))
check(f"audio: rain bed ({len(ja['rain'])} points) and wind bed ({len(ja['wind'])} points) envelopes",
      mine['rain'] == ja['rain'] and mine['wind'] == ja['wind'],
      '' if mine['rain'] == ja['rain'] else str((mine['rain'][:3], ja['rain'][:3])))
kinds = sorted({s['strike']['kind'] for s in strikes_js})
check('targets: foliage, glass and the steep ramp are never struck', not ({'foliage_clump', 'canopy', 'ramp'} & set(kinds)),
      str(kinds))
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails))
sys.exit(0 if not fails else 1)
