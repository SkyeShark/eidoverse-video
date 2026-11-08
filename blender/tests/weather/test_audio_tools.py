"""The repo-root weather-audio tools, unchanged, run the way the Blender port runs them. No Blender needed.

    python -B blender/tests/weather/test_audio_tools.py

bake_weather_audio.py bakes the timeline weather_audio.js recorded on the engine's own storm (lightning_parity.mjs,
via test_lightning_parity.py's out/lightning_js.json) into a stereo WAV: its length, the rain bed under the first
strike, and every thunder event's onset where the timeline puts it. Then its default duration (last event + 12 s),
a timeline with nothing to bake (exit 1), and the recorder options of the port (eidoblend.weather.audio.record:
rain_gain, thunder_gain, wind, wind_gain) against the same rows. merge_av.py on synthetic clips: a stream-copy mux,
the short-render refusal (exit 2), the silent-cut refusal (exit 3), --allow-trim, and the small pad within --tol.
Prints PASS/FAIL lines; writes into out/audio/.
"""
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'blender'))
OUT = HERE / 'out' / 'audio'
OUT.mkdir(parents=True, exist_ok=True)
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(detail)) if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


def run(args):
    return subprocess.run([sys.executable, '-I'] + [str(a) for a in args], cwd=str(REPO), capture_output=True,
                          text=True)


def read_wav(p):
    with wave.open(str(p)) as wf:
        n, sr, ch = wf.getnframes(), wf.getframerate(), wf.getnchannels()
        d = np.frombuffer(wf.readframes(n), np.int16).reshape(-1, ch).astype(np.float64) / 32768.0
    return d, sr


def envelope(d, sr, win=0.01):
    k = max(1, int(sr * win))
    return np.sqrt(np.convolve((d ** 2).mean(axis=1), np.ones(k) / k, 'same'))


# ---- bake_weather_audio.py on weather_audio.js's own timeline ----
js = HERE / 'out' / 'lightning_js.json'
if not js.exists():
    r = subprocess.run([sys.executable, '-B', str(HERE / 'test_lightning_parity.py')], capture_output=True, text=True)
tl = json.loads(js.read_text())['audio']
tl_path = OUT / 'engine_timeline.json'
tl_path.write_text(json.dumps(tl, indent=1))
wav = OUT / 'engine_timeline.wav'
DUR = 80.0
r = run(['bake_weather_audio.py', tl_path, '--out', wav, '--duration', DUR])
check('bake_weather_audio.py bakes the engine timeline', r.returncode == 0 and wav.exists(), (r.stdout + r.stderr)[-400:])
d, sr = read_wav(wav)
check('the track is stereo 48 kHz and as long as asked', d.shape[1] == 2 and sr == 48000 and abs(len(d) / sr - DUR) < 0.05,
      '%d ch %d Hz %.2f s' % (d.shape[1], sr, len(d) / sr))
env = envelope(d, sr)
ev = [e for e in tl['events'] if e['t'] < DUR - 2]
first = min(e['t'] for e in ev)
bed = env[int((first - 3.0) * sr):int((first - 0.5) * sr)].mean()
check('the rain and wind beds run under the storm before the first clap', bed > 0.005, '%.4f rms' % bed)
groups = []                      # one strike's layers (clap, tail, crack) start within 0.5 s of each other
for e in sorted(ev, key=lambda e: e['t']):
    if groups and e['t'] - groups[-1][0]['t'] < 0.5:
        groups[-1].append(e)
    else:
        groups.append([e])
bad = []
for g in groups:                          # measured against the beds alone (before the first strike): an earlier
    t = g[0]['t']                         # strike's tail must not count as this one's background
    if 'distant' in g[0]['clip']:            # a far rumble swells: its energy, not a transient
        post = env[int(t * sr):int((t + 2.0) * sr)].mean()
        if post < bed * 1.3:
            bad.append(('distant', t, round(bed, 4), round(post, 4)))
        continue
    lo, hi = int(max(0, t - 0.4) * sr), int((t + 0.6) * sr)
    onset = (lo + int(np.argmax(np.diff(env[lo:hi])))) / sr
    peak = env[int(t * sr):int((t + 0.5) * sr)].max()
    if abs(onset - t) > 0.25 or peak < bed * 2.0:
        bad.append((g[0]['clip'].split('/')[-1], t, round(onset, 3), round(bed, 4), round(peak, 4)))
check('every strike sounds at its timeline time over the beds (%d strikes: claps at their onsets, far rumbles '
      'swelling)' % len(groups), not bad, bad)
L, R = d[:, 0], d[:, 1]
pans = [(e['t'], e['pan']) for e in ev if abs(e['pan']) > 0.5 and 'distant' not in e['clip']]
if pans:
    t, p = pans[0]
    s = slice(int(t * sr), int((t + 0.4) * sr))
    lr = np.sqrt((L[s] ** 2).mean()) / max(1e-9, np.sqrt((R[s] ** 2).mean()))
    check('a strike panned %s lands on that side (pan %.2f, L/R %.2f)' % ('right' if p > 0 else 'left', p, lr),
          (lr < 1) if p > 0 else (lr > 1))
r = run(['bake_weather_audio.py', tl_path, '--out', OUT / 'engine_timeline_default.wav'])
d2, _ = read_wav(OUT / 'engine_timeline_default.wav')
want = max(e['t'] for e in tl['events']) + 12
check('without --duration the track runs to the last event + 12 s', abs(len(d2) / sr - want) < 0.05,
      '%.2f s, want %.2f' % (len(d2) / sr, want))
empty = OUT / 'empty_timeline.json'
empty.write_text(json.dumps(dict(rainClip=tl['rainClip'], rain=[], wind=[], windGain=1, events=[], stats={})))
r = run(['bake_weather_audio.py', empty, '--out', OUT / 'empty.wav'])
check('a timeline with nothing in it bakes nothing (exit 1)', r.returncode == 1 and 'Nothing to bake' in r.stdout,
      r.stdout.strip())

# ---- the port's recorder options, over rows that mirror the engine's storm ----
from eidoblend.weather.audio import record  # noqa: E402
rows = []
for i, e in enumerate(tl['events'][:4]):
    rows.append(dict(t=e['t'] - 0.5, rain_k=1.0, dense_a=1.75, wind_len=5.12, strike_blender=None,
                     cam_matrix=[[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 1.7], [0, 0, 0, 1]]))
    rows.append(dict(t=e['t'], rain_k=1.0, dense_a=1.75, wind_len=5.12, cam_matrix=rows[-1]['cam_matrix'],
                     strike_blender=dict(id=1000 + i, x=200.0 * (i + 1), y=50.0, z=0.0, flash=0.9, local=False)))
base = record(rows).timeline()
loud = record(rows, thunder_gain=3.6, rain_gain=0.5, wind=False).timeline()
check('record(): thunder_gain scales every thunder event (x2)', all(abs(b['gain'] * 2 - a['gain']) < 2e-4
                                                                   for a, b in zip(loud['events'], base['events'])))
check('record(): rain_gain scales the rain bed (x0.5)', abs(loud['rain'][0]['gain'] * 2 - base['rain'][0]['gain']) < 2e-4)
check('record(wind=False): no wind bed', loud['wind'] == [] and base['wind'] != [])
check('record(): wind_gain reaches the baker', record(rows, wind_gain=0.3).timeline()['windGain'] == 0.3)

# ---- merge_av.py ----
def clip(path, seconds, kind):
    if kind == 'video':
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=s=160x90:r=24:d=%g' % seconds,
               '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)]
    else:
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=f=440:d=%g' % seconds, '-ac', '2',
               str(path)]
    subprocess.run(cmd, check=True)
    return path


def dur(p):
    o = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)],
                       capture_output=True, text=True)
    return float(o.stdout.strip())


v5 = clip(OUT / 'v5.mp4', 5.0, 'video')
cases = [('a stream-copy mux of a 5 s render and 5 s of audio', 5.0, [], 0, 'copy'),
         ('refuses to clone-pad a render 3 s short of its audio (exit 2)', 8.0, [], 2, None),
         ('refuses to cut 3 s off the film silently (exit 3)', 2.0, [], 3, None),
         ('--allow-trim cuts the film to its audio', 2.0, ['--allow-trim'], 0, 'copy'),
         ('pads a 0.6 s rounding gap within --tol (re-encodes)', 5.6, [], 0, 'pad')]
from eidoblend.weather.system import WeatherFX  # noqa: E402
for i, (name, secs, extra, code, path) in enumerate(cases):
    a = clip(OUT / ('a%d.wav' % i), secs, 'audio')
    out = OUT / ('merged_%d.mp4' % i)
    if out.exists():
        out.unlink()
    r = run(['merge_av.py', '--video', v5, '--audio', a, '--out', out] + extra)
    ok = r.returncode == code
    if ok and code == 0:
        ok = out.exists() and abs(dur(out) - min(secs, 5.0 + (1.0 if path == 'pad' else 0))) < 0.15
        if path == 'pad':
            ok = ok and 'pad path re-encodes' in r.stdout
    check('merge_av.py: ' + name, ok, '' if ok else (r.stdout + r.stderr)[-300:])
try:
    WeatherFX.merge_av(v5, OUT / 'a1.wav', OUT / 'merged_refused.mp4')
    check('WeatherFX.merge_av raises when merge_av.py refuses', False)
except RuntimeError as e:
    check('WeatherFX.merge_av raises when merge_av.py refuses', 'REFUSING' in str(e), str(e)[:120])
for f in OUT.glob('a*.wav'):
    f.unlink()
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails))
sys.exit(0 if not fails else 1)
