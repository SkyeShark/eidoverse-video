"""The weather-audio recorder's Python port against the engine's weather_audio.js, event for event.

    python -B blender/tests/media/test_weather_audio_parity.py

No Blender needed (eidoblend.media.weather_audio's recorder is plain Python). A synthetic storm: rain and wind ramps,
a turning, travelling camera, strikes far (distant takes), mid (close + crack) and near / local (explosive), one
strike repeated over frames (must record once) and one under the flash gate. Both recorders get the same frames;
the timelines must match exactly (the JSON the baker reads). Then bake_weather_audio.py, unchanged, renders the
port's timeline to a WAV (ffprobe: duration). Exit 0 = parity.
"""
import json
import math
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
sys.path.insert(0, str(WORKTREE / 'blender'))
from eidoblend.media.weather_audio import WeatherAudioRecorder  # noqa: E402

OUT = HERE / 'out' / 'weather_work'
OUT.mkdir(parents=True, exist_ok=True)
FPS = 24
states = []
strikes = {30: (0, 120, -900, 'a'), 31: (0, 120, -900, 'a'), 70: (200, 80, -120, 'b'), 110: (-40, 30, -60, 'c'),
           150: (500, 200, 300, 'd'), 190: (10, 5, -20, 'e')}
for f in range(240):
    t = f / FPS
    yaw = 0.4 * math.sin(t * 0.3)
    px, py, pz = 3 * math.sin(t * 0.1), 1.6, -t * 0.5
    # three's camera matrixWorld, column-major: right = (cos yaw, 0, -sin yaw), up = y, back (+Z) = (sin yaw, 0, cos yaw)
    c, s = math.cos(yaw), math.sin(yaw)
    cam = [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, px, py, pz, 1]
    st = None
    if f in strikes:
        x, y, z, sid = strikes[f]
        st = {'id': sid, 'x': x, 'y': y, 'z': z, 'flash': 0.9 if sid != 'e' else 0.02, 'local': sid == 'c'}
    states.append({'t': t, 'rainK': min(1.0, t / 6), 'denseA': 1.0 + 0.75 * min(1.0, max(0.0, (t - 4) / 4)),
                   'wind': 3.2 * 5 * min(1.0, t / 8), 'strike': st, 'cam': cam, 'pos': [px, py, pz]})
(OUT / 'states.json').write_text(json.dumps(states))

deno = 'deno'
r = subprocess.run([deno, 'run', '-A', '--no-config', '--node-modules-dir=none', '--cached-only',
                    str(HERE / 'weather_audio_parity.mjs'), str(OUT / 'states.json')], capture_output=True, text=True,
                   cwd=str(WORKTREE))
if r.returncode != 0:
    print(r.stderr[-2000:])
    sys.exit(2)
js = json.loads(r.stdout)

rec = WeatherAudioRecorder(quiet=True)
for s in states:
    e = s['cam']
    m = [[e[0], e[4], e[8], e[12]], [e[1], e[5], e[9], e[13]], [e[2], e[6], e[10], e[14]], [0, 0, 0, 1]]
    rec.update(s['t'], s, m)
py = json.loads(json.dumps(rec.timeline()))
(OUT / 'wx_audio_py.json').write_text(json.dumps(py, indent=1))
(OUT / 'wx_audio_js.json').write_text(json.dumps(js, indent=1))

bad = []
for k in ('rainClip', 'rain', 'wind', 'windGain', 'events', 'stats'):
    if js.get(k) != py.get(k):
        bad.append(k)
        print(f'[parity] {k} differs:\n  js {json.dumps(js.get(k))[:600]}\n  py {json.dumps(py.get(k))[:600]}')
print(f'[parity] rain points {len(py["rain"])}, wind points {len(py["wind"])}, events {len(py["events"])}, '
      f'stats {py["stats"]} -> {"OK" if not bad else "MISMATCH in " + ", ".join(bad)}')

wav = OUT / 'wx.wav'
env = {k: v for k, v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH')}
b = subprocess.run([sys.executable, '-B', str(WORKTREE / 'bake_weather_audio.py'), str(OUT / 'wx_audio_py.json'),
                    '--out', str(wav), '--duration', '12'], capture_output=True, text=True, cwd=str(WORKTREE), env=env)
pr = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=sample_rate,channels', '-of',
                     'json', str(wav)], capture_output=True, text=True)
print('[bake] bake_weather_audio.py exit', b.returncode, b.stderr[-400:] if b.returncode else '', '|', pr.stdout.strip().replace('\n', ' '))
sys.exit(1 if bad or b.returncode else 0)
