"""The weather-audio recorder over Blender frames (eidoverse/weather_audio.js, ported decision for decision).

It records what fires, when and where: the rain bed's envelope, the wind envelope and one thunder event per new
lightning strike (distance, the 343 m/s flash-to-clap delay, listener-relative pan, the compressed inverse
distance gain). bake_weather_audio.py, unchanged, renders that JSON to a WAV with the clips in
eidoverse/assets/sky/audio/.

    from eidoblend.media import weather_audio
    rec = weather_audio.WeatherAudioRecorder()
    rec.record_scene(scene, read=weather_audio.read_props)            # every frame of the scene's range
    rec.write('work/<id>/wx_audio.json')
    # python bake_weather_audio.py work/<id>/wx_audio.json --out wx.wav --duration <d>

``read(scene, frame)`` returns the weather state at a frame: {rainK, denseA, wind (the windVec length), strike:
{id, x, y, z, flash, local} or None}. ``read_props`` reads it from custom properties keyed on an object named
``eido_weather`` (the contract proposed to the sky-weather family: rainK, denseA, windK or wind_len, strike_id,
strike_x, strike_y, strike_z, strike_flash, strike_local; Blender world metres). The listener is the scene camera.
"""
import json
import math
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

A = 'eidoverse/assets/sky/audio/'
CLIPS = {
    'rain': A + 'rain_desert_loop.ogg',
    'thunderClose': [A + 'thunder_close_01.ogg', A + 'thunder_close_02.ogg', A + 'thunder_close_03.ogg'],
    'thunderDistant': [A + 'thunder_distant_01.ogg', A + 'thunder_distant_02.ogg', A + 'thunder_distant_03.ogg'],
    'thunderExplosive': [A + 'thunder_explosive_01.wav', A + 'thunder_explosive_02.wav',
                         A + 'thunder_explosive_03.wav'],
}
THUNDER_CLOSE_ONSETS = [0.156, 0.118, 0.274]
SPEED_OF_SOUND = 343.0
RAIN_BED_CEILING = 0.26
DIST_GAIN_FLOOR = 0.42


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def distance_gain(d, ref, mx, roll):
    """Web Audio's 'inverse' model in closed form, compressed into [DIST_GAIN_FLOOR, 1] (see the JS for why)."""
    c = _clamp(d, ref, mx)
    g = ref / (ref + roll * (c - ref))
    return DIST_GAIN_FLOOR + (1 - DIST_GAIN_FLOOR) * g


def rain_severity(rain_k, dense_a):
    return math.pow(_clamp(rain_k, 0, 1), 1.1) * (0.75 + 0.25 * _clamp(dense_a, 0, 2))


def _js_fixed(v, n):
    """Number(v.toFixed(n)) exactly as JS computes it: on the double's exact value, ties away from zero
    (Python's own formatting rounds ties to even: 0.03125 -> 0.0312 where JS gives 0.0313)."""
    if v != v or v in (math.inf, -math.inf):
        return v
    return float(Decimal(v).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP))


class WeatherAudioRecorder:
    def __init__(self, rain_gain=1.0, thunder_gain=1.8, wind=True, wind_gain=1.0, quiet=False):
        self.rain_gain, self.thunder_gain, self.wind, self.wind_gain, self.quiet = (
            rain_gain, thunder_gain, wind, wind_gain, quiet)
        self.events, self.rain_curve, self.wind_curve = [], [], []
        self.previous_strike = None
        self.variation = 0
        self.last_rain = -1.0
        self.last_wind = -1.0
        self.stats = {'strikes': 0, 'explosive': 0, 'close': 0, 'distant': 0, 'cracks': 0, 'maxRain': 0,
                      'maxWind': 0, 'nearestMeters': None, 'farthestMeters': None}

    @staticmethod
    def azimuth(cam_matrix, sx, sy, sz):
        """0 = dead ahead, +pi/2 = hard right; the camera's right is its local +X, forward its local -Z."""
        if cam_matrix is None:
            return 0.0
        m = cam_matrix
        rx, ry, rz = m[0][0], m[1][0], m[2][0]
        fx, fy, fz = -m[0][2], -m[1][2], -m[2][2]
        px, py, pz = m[0][3], m[1][3], m[2][3]
        dx, dy, dz = sx - px, sy - py, sz - pz
        ln = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        dx, dy, dz = dx / ln, dy / ln, dz / ln
        return math.atan2(dx * rx + dy * ry + dz * rz, dx * fx + dy * fy + dz * fz)

    def _emit(self, clip, t, distance, azimuth, gain=1.0, rate=1.0, offset=0.0, spatial=None, lowpass=None,
              highpass=None, stop_after=None):
        dg = distance_gain(distance, *spatial) if spatial else 1.0
        e = {'clip': clip, 't': max(0.0, _js_fixed(t, 4)), 'gain': _js_fixed(gain * self.thunder_gain * dg, 5),
             'rate': _js_fixed(rate, 4), 'offset': _js_fixed(offset, 4), 'pan': _js_fixed(math.sin(azimuth), 4),
             'distance': int(round(distance))}
        if lowpass:
            e['lowpassHz'] = lowpass
        if highpass:
            e['highpassHz'] = highpass
        if stop_after:
            e['stopAfter'] = stop_after
        self.events.append(e)

    def _thunder(self, t, distant, local, distance, delay, azimuth):
        i = self.variation
        self.variation += 1
        rate = 0.93 + ((i * 11) % 11) * 0.014
        at = t + delay
        s = self.stats
        s['strikes'] += 1
        rd = int(round(distance))
        s['nearestMeters'] = rd if s['nearestMeters'] is None or distance < s['nearestMeters'] else s['nearestMeters']
        s['farthestMeters'] = rd if s['farthestMeters'] is None or distance > s['farthestMeters'] else s['farthestMeters']
        if distant:
            s['distant'] += 1
            self._emit(CLIPS['thunderDistant'][i % 3], at, distance, azimuth, gain=0.64, rate=rate,
                       spatial=(100, 2600, 0.38))
            return
        if local or distance <= 150:
            s['explosive'] += 1
            s['cracks'] += 1
            self._emit(CLIPS['thunderExplosive'][i % 3], at, distance, azimuth, gain=1.9, rate=rate,
                       spatial=(80, 1600, 0.4))
            self._emit(CLIPS['thunderClose'][i % 3], at + 0.35, distance, azimuth, gain=0.62, rate=rate,
                       lowpass=5200, offset=max(0.0, THUNDER_CLOSE_ONSETS[i % 3] - 0.035), spatial=(90, 2200, 0.34))
            return
        s['close'] += 1
        onset = THUNDER_CLOSE_ONSETS[i % 3]
        self._emit(CLIPS['thunderClose'][i % 3], at, distance, azimuth, gain=0.90, rate=rate, lowpass=8200,
                   offset=max(0.0, onset - 0.035), spatial=(90, 2200, 0.34))
        if distance <= 180:
            s['cracks'] += 1
            self._emit(CLIPS['thunderClose'][i % 3], at, distance, azimuth, gain=0.92, rate=rate, highpass=1150,
                       stop_after=0.72, offset=onset, spatial=(55, 1400, 0.44))

    def update(self, t, state, cam_matrix=None):
        """One frame: ``state`` {rainK, denseA, wind (windVec length), strike}; cam_matrix the camera's 4x4 world
        matrix (row-major nested sequence, e.g. a mathutils Matrix)."""
        rain = _clamp(float(state.get('rainK', 0) or 0), 0, 1)
        dense = float(state.get('denseA', 1) if state.get('denseA') is not None else 1)
        g = RAIN_BED_CEILING * rain_severity(rain, dense) * self.rain_gain
        if abs(g - self.last_rain) > 0.005:
            self.rain_curve.append({'t': _js_fixed(t, 3), 'gain': _js_fixed(g, 4)})
            self.last_rain = g
        self.stats['maxRain'] = max(self.stats['maxRain'], rain)
        if self.wind:
            wk = float(state.get('wind', 0) or 0) / 3.2
            w = _clamp(wk / 5, 0, 1.2)
            if abs(w - self.last_wind) > 0.015:
                self.wind_curve.append({'t': _js_fixed(t, 3), 'w': _js_fixed(w, 4)})
                self.last_wind = w
            self.stats['maxWind'] = max(self.stats['maxWind'], w)
        st = state.get('strike')
        if not st:
            return
        key = st.get('id')
        if key is None:
            key = f"{float(st['x']):.2f},{st.get('y', 0)},{float(st['z']):.2f}"
        if key == self.previous_strike or not (float(st.get('flash', 0) or 0) > 0.03):
            return
        self.previous_strike = key
        sx, sy, sz = float(st['x']), float(st.get('y', 0) or 0), float(st['z'])
        if cam_matrix is not None:
            px, py, pz = cam_matrix[0][3], cam_matrix[1][3], cam_matrix[2][3]
        else:
            px = py = pz = 0.0
        d = math.sqrt((sx - px) ** 2 + (sy - py) ** 2 + (sz - pz) ** 2)
        self._thunder(t, distant=d > 360, local=st.get('local') is True, distance=d, delay=d / SPEED_OF_SOUND,
                      azimuth=self.azimuth(cam_matrix, sx, sy, sz))
        if not self.quiet:
            print(f'[weather_audio] strike t={t:.2f}s d={d:.0f}m delay={d / SPEED_OF_SOUND:.2f}s')

    def timeline(self):
        return {'rainClip': CLIPS['rain'], 'rain': self.rain_curve, 'wind': self.wind_curve if self.wind else [],
                'windGain': self.wind_gain, 'events': self.events, 'stats': self.stats}

    def write(self, path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.timeline(), indent=1), encoding='utf-8')
        return p

    def record_scene(self, scene, read=None, frames=None, camera=None):
        """Step the scene frame by frame (frame_set, so keyed weather and camera evaluate) and record."""
        from .timebase import Timebase
        tb = Timebase.of(scene)
        read = read or read_props
        a, b = frames or (scene.frame_start, scene.frame_end)
        keep = scene.frame_current
        for f in range(a, b + 1):
            scene.frame_set(f)
            cam = camera or scene.camera
            self.update(tb.t(f), read(scene, f), cam.matrix_world if cam else None)
        scene.frame_set(keep)
        return self


def read_props(scene, frame, name='eido_weather'):
    """The proposed contract: custom properties (keyable) on an object named ``eido_weather``."""
    import bpy
    o = bpy.data.objects.get(name)
    if o is None:
        return {}
    g = o.get
    wind = g('wind_len')
    if wind is None and g('windK') is not None:
        wind = float(g('windK')) * 3.2
    st = None
    if g('strike_id') is not None and g('strike_flash', 0) > 0:
        st = {'id': g('strike_id'), 'x': g('strike_x', 0.0), 'y': g('strike_y', 0.0), 'z': g('strike_z', 0.0),
              'flash': g('strike_flash', 0.0), 'local': bool(g('strike_local', False))}
    return {'rainK': g('rainK', 0.0), 'denseA': g('denseA', 1.0), 'wind': wind or 0.0, 'strike': st}
