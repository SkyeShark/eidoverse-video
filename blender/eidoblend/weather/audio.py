"""The weather audio timeline (eidoverse/weather_audio.js) for a baked weather, and the repo-root tools that render
and mux it: bake_weather_audio.py (the timeline -> a stereo WAV) and merge_av.py (the WAV onto the rendered video).

The recorder is eidoblend.media.weather_audio.WeatherAudioRecorder (the JS recorder ported decision for decision): a
rain bed envelope (rainK x curtain density, ceilinged under thunder), a synthesized wind bed envelope (the windVec
length), and one thunder event per new strike, delayed 1 s per 343 m, panned from the camera's view of the strike,
the compressed inverse-distance gain, the explosive / close / distant takes chosen by distance and locality. Here
it reads the weather's own per-frame records, so no frame is evaluated twice. make_weather_audio is the JS factory
itself, for a frame loop of your own.
"""
import json
import math
import os
import subprocess
import sys

from ..common import REPO


class WeatherAudio:
    """makeWeatherAudio's object: call update(t) once per frame, after the weather's update(t, camera), with the same
    t; it reads the weather's uniforms (rainK, denseA, windVec) and its strike record as the JS reads them, and the
    camera's world matrix as the listener. stats, timeline() and to_json() (the JS toJSON) as in weather_audio.js."""

    def __init__(self, weather, camera=None, rain_gain=1.0, thunder_gain=1.8, quiet=False, wind=True, wind_gain=1.0):
        from ..media.weather_audio import WeatherAudioRecorder
        self.weather, self.camera = weather, camera
        self.recorder = WeatherAudioRecorder(rain_gain=rain_gain, thunder_gain=thunder_gain, wind=wind,
                                             wind_gain=wind_gain, quiet=quiet)
        self.stats = self.recorder.stats

    def update(self, t):
        wx = self.weather
        if wx is None:                              # the JS falls back to globalThis._weather: the scene's own system
            import bpy
            from .system import _REGISTRY
            wx = _REGISTRY.get(bpy.context.scene.name)
        u = getattr(wx, 'uniforms', None) if wx is not None else None
        if not u:                                   # no weather, or no weather.update(t, camera) yet: the JS returns
            return
        cam = self.camera or getattr(getattr(wx, 'scene', None), 'camera', None)
        st = wx.state.get('strike')                 # Blender axes (WeatherFX.state)
        strike = (dict(id=st['id'], x=st['x'], y=st['y'], z=st['z'], flash=st['flash'], local=st['local'])
                  if st else None)
        wv = u.get('windVec', (0.0, 0.0, 0.0))
        self.recorder.update(float(t), dict(rainK=u.get('rainK', 0.0), denseA=u.get('denseA', 1.0),
                                            wind=math.sqrt(sum(float(c) * float(c) for c in wv)), strike=strike),
                             cam.matrix_world if cam is not None else None)

    def timeline(self):
        return self.recorder.timeline()

    def to_json(self):
        return json.dumps(self.timeline(), indent=1)


def make_weather_audio(weather=None, camera=None, rain_gain=1.0, thunder_gain=1.8, quiet=False, wind=True,
                       wind_gain=1.0):
    """makeWeatherAudio({weather, camera, rainGain, thunderGain, quiet, wind, windGain}), for a frame loop of your own
    (weather None: the scene's weather system, as the JS reads globalThis._weather; camera None: the scene camera):

        wx_audio = make_weather_audio(weather=wx, camera=cam)
        for f, t, _ in sky.frame_states(a, b):
            wx.update(t, cam)
            wx_audio.update(t)
        open('wx_audio.json', 'w').write(wx_audio.to_json())

    A baked weather records the same timeline from its planned frames: WeatherFX.audio_timeline()."""
    return WeatherAudio(weather, camera, rain_gain=rain_gain, thunder_gain=thunder_gain, quiet=quiet, wind=wind,
                        wind_gain=wind_gain)


def record(rows, t0=0.0, rain_gain=1.0, thunder_gain=1.8, wind=True, wind_gain=1.0, quiet=True):
    """A WeatherAudioRecorder fed with the weather's frame rows (rainK, denseA, wind length, strike, camera) from
    media time t0 on, re-timed so t0 is the track's 0 (a shot that opens after a pre-roll)."""
    from ..media.weather_audio import WeatherAudioRecorder
    rec = WeatherAudioRecorder(rain_gain=rain_gain, thunder_gain=thunder_gain, wind=wind, wind_gain=wind_gain,
                               quiet=quiet)
    for r in rows:
        if r['t'] < t0 - 1e-9:
            continue
        st = r['strike_blender']
        rec.update(r['t'] - t0, dict(rainK=r['rain_k'], denseA=r['dense_a'], wind=r['wind_len'], strike=st),
                   r['cam_matrix'])
    return rec


def _python():
    """A Python for the repo-root tools (stdlib only): this interpreter (Blender's bundled one inside Blender)."""
    exe = sys.executable or ''
    return exe if os.path.basename(exe).lower().startswith('python') else 'python'


def _run(cmd):
    """Run a repo-root tool from the repository root in Python's UTF-8 mode, and read its output as UTF-8 (the tools
    print em dashes; under Windows' cp1252 that byte stream is not UTF-8, and reading it raised). -X utf8 is a
    command-line option, so it holds under -I, which ignores PYTHONIOENCODING."""
    if len(cmd) > 1 and cmd[1] == '-I':
        cmd = [cmd[0], '-I', '-X', 'utf8'] + list(cmd[2:])
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding='utf-8', errors='replace')


def bake_wav(timeline_path, wav_path, duration=None):
    """python bake_weather_audio.py <timeline> --out <wav> [--duration d], run from the repository root (the
    timeline names its clips relative to it)."""
    cmd = [_python(), '-I', os.path.join(REPO, 'bake_weather_audio.py'), os.path.abspath(timeline_path), '--out',
           os.path.abspath(wav_path)]
    if duration:
        cmd += ['--duration', '%.3f' % float(duration)]
    r = _run(cmd)
    if r.returncode != 0 or not os.path.exists(wav_path):
        raise RuntimeError('bake_weather_audio.py failed: ' + ((r.stdout or '') + (r.stderr or ''))[-1500:])
    return (r.stdout or '').strip()


def merge(video, wav, out, tol=1.0, trim_tol=2.0, allow_trim=False):
    """python merge_av.py --video --audio --out: refuses a frozen-frame pad or a silent cut, as the tool does."""
    cmd = [_python(), '-I', os.path.join(REPO, 'merge_av.py'), '--video', os.path.abspath(video), '--audio',
           os.path.abspath(wav), '--out', os.path.abspath(out), '--tol', str(tol), '--trim-tol', str(trim_tol)]
    if allow_trim:
        cmd.append('--allow-trim')
    r = _run(cmd)
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError('merge_av.py failed (%d): %s' % (r.returncode, ((r.stdout or '') + (r.stderr or ''))[-1500:]))
    return (r.stdout or '').strip()


def write_timeline(rec, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec.timeline(), f, indent=1)
    return path
