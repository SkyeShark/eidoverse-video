"""Weather states and their coupling to the sky, ported from Eanpa Engine engine/weather_system.js.

What is here: the WEATHER table (every state carries its cloud preset), setWeather / transitionTo with
the same eased lerp of every uniform they touch, the per-frame sky greying (mixG, horMul, greyTint),
wetness / surface-water time constants, the integrated wind, sunDim / hemiDim. Rain streaks, splashes, puddles
and lightning are eidoblend.weather's, which make_sky builds when its weather rains, strikes or wets.
"""
import math

LEGACY_STATES = {'noreaster': 'cyclone', 'hurricane': 'cyclone', 'drizzle': 'rain'}

WEATHER = {
    'clear': dict(clouds='clear', over={}, sunDim=1.00, grey=0.00, dark=1.00, greyTint=(1, 1, 1), rain=0.00, wet=0.00,
                  windK=0.0, len=0.30, fall=1.0, dash=0.0, lightning=0.00),
    'sunshower': dict(clouds='cumulus', over=dict(largeT=0.50, weatherT=0.34, wispOn=0.16, wispThreshold=0.58,
                                                  wispStrength=0.42, wispOpacity=1.10, wispFilament=0.20,
                                                  wispStretch=(0.70, 0.32, 1.72), wispTint=(1.04, 0.99, 0.91)),
                      sunDim=0.92, grey=0.05, dark=1.00, greyTint=(1, 1, 1), rain=0.45, wet=0.55, windK=0.5, len=0.2,
                      fall=0.9, dash=0.0, lightning=0.00, cellLo=0.85, cellHi=1.25),
    'fair': dict(clouds='cumulus', over=dict(largeT=0.58, largeA=3.2, weatherT=0.26, finalMul=0.24, wispOn=0.13,
                                             wispThreshold=0.62, wispStrength=0.38, wispOpacity=1.06, wispFilament=0.18,
                                             wispStretch=(0.72, 0.33, 1.66), wispTint=(1.02, 0.99, 0.94)),
                 sunDim=0.88, grey=0.15, dark=1.00, greyTint=(1, 1, 1), rain=0.00, wet=0.00, windK=0.5, len=0.3,
                 fall=1.0, dash=0.0, lightning=0.00),
    'overcast': dict(clouds='stratus', over=dict(largeT=0.05, finalMul=0.20, wispOn=0.90, wispThreshold=0.30,
                                                 wispStrength=0.90, wispOpacity=0.96, wispFilament=0.05,
                                                 wispStretch=(0.92, 0.24, 1.18), wispTint=(0.66, 0.74, 0.84)),
                     sunDim=0.45, cloudRadiance=0.80, grey=0.60, dark=0.75, greyTint=(1, 1, 1), rain=0.00, wet=0.15,
                     windK=0.4, len=0.3, fall=1.0, dash=0.0, lightning=0.00, horMul=0.85, cellLo=0.5, cellHi=0.9,
                     celestialVisibility=0.30),
    'rain': dict(clouds='stratus', over=dict(largeT=0.02, finalMul=0.26, height=320, wispOn=0.94, wispScale=0.00092,
                                             wispThreshold=0.27, wispStrength=0.96, wispOpacity=1.00, wispFilament=0.12,
                                             wispStretch=(0.66, 0.22, 1.65), wispTint=(0.57, 0.66, 0.78)),
                 sunDim=0.30, cloudRadiance=0.65, grey=0.75, dark=0.55, greyTint=(1, 1, 1), rain=0.70, wet=0.85,
                 windK=1.0, len=0.22, fall=1.0, dash=0.0, lightning=0.00, horMul=0.75, cellLo=0.5, cellHi=0.85,
                 celestialVisibility=0.15),
    'storm': dict(clouds='cumulus', over=dict(largeT=0.12, largeA=4.0, finalMul=0.34, start=550, height=950, wispOn=0.52,
                                              wispScale=0.00096, wispThreshold=0.36, wispStrength=0.88, wispOpacity=1.05,
                                              wispFilament=0.32, wispStretch=(0.40, 0.20, 2.18),
                                              wispTint=(0.53, 0.60, 0.70)),
                  sunDim=0.18, cloudRadiance=0.45, grey=0.80, dark=0.42, greyTint=(1, 1, 1), rain=1.00, wet=1.00,
                  windK=2.2, len=0.3, fall=1.2, dash=0.0, lightning=0.30, lightningPalette='standard',
                  localStrikeChance=0.018, horMul=0.6, cellLo=1.0, cellHi=1.45, distant=0.5, celestialVisibility=0.10),
    'cyclone': dict(clouds='stratus', over=dict(largeT=0.00, largeA=2.2, finalMul=0.50, start=240, height=400, wispOn=1.00,
                                                wispScale=0.00100, wispThreshold=0.22, wispStrength=1.00,
                                                wispOpacity=1.12, wispFilament=0.22, wispStretch=(0.46, 0.24, 1.95),
                                                wispTint=(0.45, 0.56, 0.72)),
                    sunDim=0.10, cloudRadiance=0.32, grey=0.95, dark=0.26, greyTint=(0.92, 0.97, 1.06), rain=1.00,
                    wet=1.00, windK=6.5, len=0.60, fall=1.6, dash=0.0, lightning=0.05, lightningPalette='standard',
                    localStrikeChance=0.010, horMul=0.5, cellLo=0.10, cellHi=0.35, dense=1.9, distant=0.15,
                    celestialVisibility=0.06),
    'darkstorm': dict(clouds='cumulus', over=dict(largeT=0.00, largeA=2.2, weatherT=0.00, finalMul=0.34, start=500,
                                                  height=650, lightCacheDirect=0, wispOn=1.00, wispScale=0.00085,
                                                  wispThreshold=0.16, wispStrength=0.95, wispOpacity=1.05, wispFloor=0.55,
                                                  wispFilament=0.14, wispStretch=(0.42, 0.26, 1.60),
                                                  wispTint=(0.30, 0.33, 0.38), stormCanopy=1.00),
                      stormTopMeters=19300, sunDim=0.00, hemiDim=0.12, celestialVisibility=0.00, cloudRadiance=0.14,
                      grey=0.97, dark=0.14, greyTint=(0.90, 0.95, 1.00), rain=1.00, wet=1.00, windK=1.6, len=0.40,
                      fall=1.25, dash=0.0, lightning=0.85, lightningPalette='darkstorm', localStrikeChance=0.16,
                      horMul=0.22, cellLo=0.9, cellHi=1.4, dense=1.75, distant=0.8),
}

DEF_DEFAULTS = dict(horMul=1, dense=1, distant=0, localStrikeChance=0, cellLo=0.9, cellHi=1.45)

# sky uniforms a weather morph lerps (JS _transScalars / _transVecs, sky side)
SKY_TRANS_SCALARS = ('cloudDim', 'cloudRadiance', 'sunDiscI', 'precipK', 'precipLo', 'precipHi', 'largeT', 'largeA',
                     'weatherT', 'finalMul', 'wScale', 'dScale', 'cloudStart', 'cloudHeight', 'lightK', 'wispOn',
                     'wispScale', 'wispThreshold', 'wispStrength', 'wispOpacity', 'wispFloor', 'wispFilament',
                     'lightCacheDirect', 'stormCanopy', 'celestialVisibility', 'cloudWeatherGrey')
SKY_TRANS_VECS = ('skyWind', 'stretch', 'wispStretch', 'wispTint', 'wispColor')
OWN_TRANS_SCALARS = ('rainK', 'wetTarget', 'denseA', 'streakLen', 'fallMul', 'dashK', 'cellLo', 'cellHi')


def _lerp_def(a, b, k):
    out = {}
    for key in set(a) | set(b):
        av, bv = a.get(key), b.get(key)
        if isinstance(av, (int, float)) and not isinstance(av, bool) or isinstance(bv, (int, float)) and not isinstance(bv, bool):
            fb = DEF_DEFAULTS.get(key)
            if isinstance(av, (int, float)):
                aa = av
            elif key == 'hemiDim':
                aa = 0.5 + a.get('sunDim', 1) * 0.5
            else:
                aa = fb if fb is not None else bv
            if isinstance(bv, (int, float)):
                bb = bv
            elif key == 'hemiDim':
                bb = 0.5 + b.get('sunDim', 1) * 0.5
            else:
                bb = fb if fb is not None else av
            out[key] = aa + (bb - aa) * k
        elif isinstance(av, (tuple, list)) or isinstance(bv, (tuple, list)):
            aa = av if isinstance(av, (tuple, list)) else bv
            bb = bv if isinstance(bv, (tuple, list)) else av
            out[key] = tuple(aa[i] + (bb[i] - aa[i]) * k for i in range(len(bb)))
        else:
            out[key] = (av if av is not None else bv) if k < 0.5 else (bv if bv is not None else av)
    return out


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


class WeatherSystem:
    def __init__(self, sky, opts=None):
        self.sky = sky
        self.opts = dict(opts or {})
        self.state = dict(name='clear', k=1.0, def_=WEATHER['clear'])
        self.u = dict(rainK=0.0, wetTarget=0.0, wetness=0.0, surfaceWater=0.0, denseA=1.0, streakLen=0.3,
                      fallMul=1.0, dashK=0.0, cellLo=0.9, cellHi=1.45, windVec=(0.0, 0.0, 0.0),
                      fallSpeed=float(self.opts.get('fallSpeed', 9)))
        self.color = dict(rain=(1, 1, 1), cloud=(1, 1, 1), sun=(1, 1, 1), shield=(1, 1, 1))
        self.trans = None
        self.trans_s = 0.0
        self.last_motion_t = None
        self.total_fall = 0.0
        self.total_wind = [0.0, 0.0]
        self.flash = 0.0
        self.flash_d = 0.0
        self.strike_color = (1.0, 1.0, 1.0)

    # ---- state ----
    def set_weather(self, name, k=1.0):
        name = LEGACY_STATES.get(name, name)
        self.trans = None
        resolved = name if name in WEATHER else 'clear'
        w = WEATHER[resolved]
        self.state.update(name=resolved, k=float(k), def_=w)
        U = self.sky.U
        self.sky.set_clouds(w['clouds'], w['over'])
        U['cloudDim'] = max(0.1, 1 - (1 - w['sunDim']) * k)
        U['cloudRadiance'] = max(0.1, 1 - (1 - w.get('cloudRadiance', w['sunDim'])) * k)
        U['cloudWeatherGrey'] = w['grey'] * k
        U['sunDiscI'] = 48 * max(0.02, 1 - w['grey'] * k * 0.98)
        U['celestialVisibility'] = 1 - (1 - w.get('celestialVisibility', 1)) * k
        U['precipK'] = w['rain'] * k * w.get('dense', 1)
        u = self.u
        u['rainK'] = w['rain'] * k
        u['wetTarget'] = w['wet'] * k
        u['windVec'] = tuple(c * w['windK'] * 3.2 for c in _norm((1.0, 0.0, 0.22)))
        u['denseA'] = w.get('dense', 1)
        U['skyWind'] = (u['windVec'][0] * 1.6 + 2, 0.0, u['windVec'][2] * 1.6 + 6)
        u['streakLen'] = w['len']
        u['fallMul'] = w['fall']
        u['dashK'] = w['dash']
        u['cellLo'] = w.get('cellLo', 0.9)
        u['cellHi'] = w.get('cellHi', 1.45)
        U['precipLo'] = w.get('cellLo', 0.9) + 0.05
        U['precipHi'] = w.get('cellHi', 1.45) + 0.1
        if w['lightning'] * k <= 0.0001:
            self.flash = 0.0
            U['lightningStrike'] = tuple(U['lightningStrike'][:3]) + (0.0,)
        return w

    def _capture(self):
        U = self.sky.U
        return dict(s=[float(U[k]) for k in SKY_TRANS_SCALARS] + [float(self.u[k]) for k in OWN_TRANS_SCALARS],
                    v=[tuple(self.u['windVec'])] + [tuple(U[k]) for k in SKY_TRANS_VECS])

    def _apply(self, a, b, k):
        U = self.sky.U
        n = len(SKY_TRANS_SCALARS)
        for i, key in enumerate(SKY_TRANS_SCALARS):
            U[key] = a['s'][i] + (b['s'][i] - a['s'][i]) * k
        for i, key in enumerate(OWN_TRANS_SCALARS):
            self.u[key] = a['s'][n + i] + (b['s'][n + i] - a['s'][n + i]) * k
        lerp = lambda x, y: tuple(x[c] + (y[c] - x[c]) * k for c in range(len(x)))
        self.u['windVec'] = lerp(a['v'][0], b['v'][0])
        for i, key in enumerate(SKY_TRANS_VECS):
            U[key] = lerp(a['v'][1 + i], b['v'][1 + i])

    def transition_to(self, name, k=1.0, dur=45.0):
        from_def, from_k, from_name = dict(self.state['def_']), self.state['k'], self.state['name']
        from_preset = self.sky.state['preset']
        from_visible = self.sky.cloud_visible
        snap = self._capture()
        self.set_weather(name, k)
        target = self._capture()
        to_def, to_name = dict(self.state['def_']), self.state['name']
        to_preset = self.sky.state['preset']
        to_visible = self.sky.cloud_visible
        self._apply(snap, snap, 0)
        has = from_visible or to_visible
        self.sky.cloud_visible = has
        self.sky.state['preset'] = 'transition' if has else to_preset
        self.trans = dict(fromDef=from_def, fromK=from_k, fromName=from_name, fromPreset=from_preset, toDef=to_def,
                          toK=float(k), toName=to_name, toPreset=to_preset, toVisible=to_visible, snap=snap,
                          target=target, t0=None, dur=max(0.001, float(dur)))
        self.trans_s = 0.0

    def set_colors(self, c=None):
        """Forwards to the sky ONLY the channels named, so set_colors({'rain': ...}) leaves cloud/sun alone."""
        c = c or {}
        for key in ('rain', 'cloud', 'sun', 'shield'):
            if c.get(key) is not None:
                self.color[key] = tuple(c[key])
        fwd = {k: self.color[k] for k in ('cloud', 'sun', 'shield') if c.get(k) is not None}
        if fwd:
            self.sky.set_colors(fwd)
        return dict(self.color)

    # ---- dimming of the scene's lights ----
    def sun_dim(self):
        d = self.state['def_']
        target = max(0.0, min(1.0, d.get('sunDim', 1)))
        amount = max(0.0, min(1.0, self.state['k']))
        return max(0.0, min(1.0, 1 - (1 - target) * amount))

    def hemi_dim(self):
        d = self.state['def_']
        ordinary = 0.5 + d.get('sunDim', 1) * 0.5
        target = d.get('hemiDim', ordinary)
        return max(0.08, 1 - (1 - target) * self.state['k'])

    # ---- per frame ----
    def update(self, t):
        U = self.sky.U
        if self.trans:
            tr = self.trans
            if tr['t0'] is None:
                tr['t0'] = t
            raw = max(0.0, min(1.0, (t - tr['t0']) / tr['dur']))
            s = raw * raw * (3 - 2 * raw)
            self._apply(tr['snap'], tr['target'], s)
            self.state['def_'] = _lerp_def(tr['fromDef'], tr['toDef'], s)
            self.state['k'] = tr['fromK'] + (tr['toK'] - tr['fromK']) * s
            self.trans_s = s
            if s >= 1:
                self.state.update(name=tr['toName'], def_=tr['toDef'], k=tr['toK'])
                self.sky.state['preset'] = tr['toPreset']
                self.sky.cloud_visible = tr['toVisible']
                self.trans = None
        dt = 0.0 if self.last_motion_t is None else max(0.0, min(t - self.last_motion_t, 0.1))
        self.last_motion_t = t
        u = self.u
        wet_tau = 7 if u['wetTarget'] > u['wetness'] else 70
        u['wetness'] += (u['wetTarget'] - u['wetness']) * -math.expm1(-dt / wet_tau)
        water_target = max(0.0, u['wetTarget']) ** 1.8
        water_tau = 32 if water_target > u['surfaceWater'] else 150
        u['surfaceWater'] += (water_target - u['surfaceWater']) * -math.expm1(-dt / water_tau)
        fall_v = max(0.05, u['fallSpeed'] * max(0.05, u['fallMul']))
        self.total_fall += fall_v * dt
        self.total_wind[0] += u['windVec'][0] * dt
        self.total_wind[1] += u['windVec'][2] * dt
        # sky greying under weather (mixG), with the lightning flash folded into zenith and horizon
        w, k = self.state['def_'], self.state['k']
        pal = self.sky.state['palette']
        flash, flash_d, sc = self.flash, self.flash_d, self.strike_color
        g = w['grey'] * k
        d = 1 - (1 - w['dark']) * k
        U['cloudWeatherGrey'] = g
        skyc = self.sky.sky_color['sky']
        gt = tuple(w['greyTint'][i] * skyc[i] for i in range(3))
        hor_mul = 1 - (1 - w.get('horMul', 1)) * k

        def mix_g(rgb, s):
            lum = (rgb[0] * 0.35 + rgb[1] * 0.5 + rgb[2] * 0.15) * s
            return tuple((rgb[i] + (lum * gt[i] - rgb[i]) * g) * d * s + flash * sc[i] * 0.44 for i in range(3))

        U['zenith'] = mix_g(pal['zen'], 1.0)
        hz = mix_g(pal['hor'], hor_mul)
        U['horizon'] = (hz[0] + flash_d * 0.55, hz[1] + flash_d * 0.60, hz[2] + flash_d * 0.78)
        return True
