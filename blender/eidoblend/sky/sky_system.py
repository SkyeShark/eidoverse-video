"""The sky's state machine: time of day, cloud presets and transitions, colour channels, lights.

A Python port of the JS side of Eanpa Engine engine/sky_system.js (makeSkySystem: setSun, setTime,
setColors, setClouds, transitionClouds, update, applyToLights, weatherAt). It owns the uniform set `U`,
named exactly as the TSL uniforms, which the GLSL baker reads every frame. No bpy here.
"""
import math

from . import palette as P


def _vec(v):
    return tuple(float(x) for x in v)


def _smooth01(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class CloudMotion:
    """Wind is a velocity, not a phase: integrate it so a wind change never jumps the clouds (cloud_motion.js)."""

    def __init__(self):
        self.offset = [0.0, 0.0, 0.0]
        self.previous = [0.0, 0.0, 0.0]
        self.last = None

    def update(self, time, wind):
        if self.last is not None and time >= self.last:
            dt = time - self.last
            for a in range(3):
                self.offset[a] += (self.previous[a] + wind[a]) * 0.5 * dt
        self.last = time
        self.previous = list(wind)
        return tuple(self.offset)


def default_uniforms(opts):
    return dict(
        time=0.0,
        sunDir=P.norm3((0, 0.3, 1)), cloudLightDir=P.norm3((0, 0.3, 1)), cloudLightColor=(1, 0.9, 0.8),
        cloudAmbSky=(0.2, 0.5, 1.0), cloudAmbGround=(0.8, 0.8, 0.8),
        zenith=(0.15, 0.38, 0.82), horizon=(0.62, 0.78, 0.92), sunColor=(1, 0.95, 0.9),
        sunDiscI=48.0, solarVisibility=1.0, solarSkyVisibility=1.0, sunGlowI=1.0, starFade=0.0,
        skyGlow=(0.0, 0.0, 0.0),
        moonDir=(0, -1, 0), moonRight=(1, 0, 0), moonUp=(0, 1, 0),
        moonCos=math.cos(opts.get('moonAngularDeg', 1.6) * math.pi / 360 * 2), moonLightK=0.0,
        largeT=0.18, largeA=3.0, weatherT=0.28, finalMul=0.40, wScale=1.0, dScale=1.0,
        cloudStart=700.0, cloudHeight=520.0, stretch=(1, 1, 1), lightK=1.0, lightCacheDirect=0.0,
        cloudTint=(1, 1, 1), cloudDim=1.0, cloudRadiance=1.0, cloudWeatherGrey=0.0, cloudRadianceScale=1.0,
        wispColor=(0.8, 0.8, 0.8), wispTint=(1, 1, 1), wispStretch=(1, 1, 1),
        wispOn=0.28, wispScale=0.00125, wispThreshold=0.48, wispStrength=0.7, wispOpacity=1.45,
        wispFloor=0.0, wispFilament=0.18, stormCanopy=0.0, celestialVisibility=1.0,
        lightningFlashColor=(1, 1, 1), lightningStrike=(0, 500, 0, 0),
        shaftK=float(opts.get('shafts', 0.0)), shaftDen=float(opts.get('shaftDensity', 3e-5)),
        precipK=0.0, precipLo=0.95, precipHi=1.55,
        cloudDisplacement=(0, 0, 0), skyWind=(0, 0, 10.3), wallCloud=(0, 0, 1, 0),
        fadeDist=float(opts.get('cloudFadeDist', 26000)), cloudShadowStrength=1.0,
    )


class SkySystem:
    def __init__(self, opts=None):
        opts = dict(opts or {})
        self.opts = opts
        self.U = default_uniforms(opts)
        self.src_r_deg = max(0.0, opts.get('sourceAngularRadiusDeg', 0.0))
        rgb = lambda k, d=(1, 1, 1): _vec(opts.get(k) or d)
        self.sky_color = dict(cloud=rgb('cloudColor'), sun=rgb('sunColor'), sky=rgb('skyColor'),
                              fog=rgb('fogColor'), shield=rgb('shieldColor'))
        self.palette_tint = opts.get('paletteTint')
        self.state = dict(hours=12.0, azBase=opts.get('azimuth', 1.9), elMax=opts.get('maxElevationDeg', 62.0),
                          azSpanK=opts.get('azSpanK', 0.9), preset='cumulus', palette=None)
        self.state['palette'] = self._tint_pal(P.tod_at(40))
        self.sun_dir = (0.0, 1.0, 0.0)
        self.moon_dir = (0.0, -1.0, 0.0)
        self.cloud_motion = CloudMotion()
        self.cloud_transition = None
        self.cloud_visible = True
        self.solar_occlusion = None
        self.celestial_module = None       # the sky's celestial body (the red giant): set_colors reaches it
        self.set_clouds(opts.get('clouds', 'cumulus'))
        self.set_time(opts.get('hours', 12.0))

    # ---- palette ----
    def _tint_pal(self, p):
        q = dict(p)
        pt = self.palette_tint
        if pt:
            for band in ('zen', 'hor', 'sun'):
                if pt.get(band):
                    q[band] = tuple(q[band][i] * pt[band][i] for i in range(3))
        s = self.sky_color['sky']
        if s != (1, 1, 1):
            q['zen'] = tuple(q['zen'][i] * s[i] for i in range(3))
            q['hor'] = tuple(q['hor'][i] * s[i] for i in range(3))
        return q

    def _update_wisp_color(self):
        pal = self.state['palette']
        pk = max(pal['sun'][0], pal['sun'][1], pal['sun'][2], 1e-4)
        neutral = tuple(c / pk for c in pal['sun'])
        k = 0.22 + pal['int'] * 0.34
        tint = self.U['wispTint']
        self.U['wispColor'] = tuple((pal['sun'][i] + (neutral[i] - pal['sun'][i]) * 0.62) * k * tint[i] for i in range(3))

    def _update_cloud_key(self):
        o = self.opts
        pal = self.state['palette']
        night_k = self.U['moonLightK']
        moon_up = max(0.0, min(1.0, self.moon_dir[1] / 0.12))
        moon_gain = 1.3 * night_k * moon_up * moon_up * (3 - 2 * moon_up)
        sun_gain = pal['int'] * 7 * o.get('cloudLightScale', 1.0)
        moon_tint = o.get('moonLightColor') or (0.45, 0.55, 0.85)
        tint = o.get('cloudLightTint') or (1, 1, 1)
        cc = self.sky_color['cloud']
        self.U['cloudLightColor'] = tuple(
            (pal['sun'][i] * sun_gain * tint[i] * (1 - night_k) + moon_tint[i] * moon_gain * night_k) * cc[i]
            for i in range(3))
        self.U['cloudLightDir'] = self.moon_dir if night_k > 0.5 else self.sun_dir

    # ---- time of day ----
    def set_sun(self, az, el):
        self.sun_dir = P.norm3((math.cos(el) * math.cos(az), math.sin(el), math.cos(el) * math.sin(az)))
        U = self.U
        U['sunDir'] = self.sun_dir
        el_deg = el * 180 / math.pi
        pal = self._tint_pal(P.tod_disc(el_deg, self.src_r_deg))
        self.state['palette'] = pal
        U['zenith'] = pal['zen']
        U['horizon'] = pal['hor']
        sc = self.sky_color['sun']
        U['sunColor'] = tuple(pal['sun'][i] * sc[i] for i in range(3))
        U['starFade'] = pal['star']
        night_k = max(0.0, min(1.0, (-el_deg - 2) / 8))
        U['moonLightK'] = night_k
        self._update_cloud_key()
        amb_scale = self.opts.get('cloudAmbScale', 1.0)
        amb_day = tuple(c * 0.34 * (0.25 + pal['int'] * 0.55) * amb_scale for c in pal['zen'])
        amb_night = (0.04 * 0.6, 0.055 * 0.6, 0.10 * 0.6)
        U['cloudAmbSky'] = tuple(amb_day[i] + (amb_night[i] - amb_day[i]) * night_k for i in range(3))
        g = max(0.008, pal['int'] * 0.027)
        U['cloudAmbGround'] = (0.8 * g, 0.8 * g, 0.8 * g)
        self._update_wisp_color()

    def set_moon_direction(self, d):
        self.moon_dir = P.norm3(d)
        self.U['moonDir'] = self.moon_dir
        right = P.norm3(P.cross3((0, 1, 0), self.moon_dir))
        self.U['moonRight'] = right
        self.U['moonUp'] = P.norm3(P.cross3(self.moon_dir, right))
        self._update_cloud_key()

    def set_time(self, hours):
        self.state['hours'] = hours
        sun, moon, az, el = P.sun_moon_at(hours, self.state['azBase'], self.state['elMax'], self.state['azSpanK'],
                                          self.opts.get('noonAzimuth'))
        self.moon_dir = moon
        self.U['moonDir'] = moon
        right = P.norm3(P.cross3((0, 1, 0), moon))
        self.U['moonRight'] = right
        self.U['moonUp'] = P.norm3(P.cross3(moon, right))
        self.set_sun(az, el)

    def set_colors(self, c=None):
        c = c or {}
        star = c.get('star', c.get('sun'))
        for key, val in (('cloud', c.get('cloud')), ('sun', star), ('sky', c.get('sky')),
                         ('fog', c.get('fog')), ('shield', c.get('shield'))):
            if val is not None:
                self.sky_color[key] = _vec(val)
        # a package with its own star shader (the red giant) gets the star and shield colours forwarded, where it
        # takes them (a custom celestial body may carry neither)
        cm = self.celestial_module
        if cm is not None:
            if c.get('shield') is not None and hasattr(cm, 'set_shield_color'):
                cm.set_shield_color(self.sky_color['shield'])
            if star is not None and hasattr(cm, 'set_star_color'):
                cm.set_star_color(self.sky_color['sun'])
        self.set_time(self.state['hours'])
        return dict(self.sky_color)

    def get_colors(self):
        return dict(self.sky_color)

    # ---- clouds ----
    def _capture_cloud_state(self):
        return dict(scalars=[float(self.U[k]) for k in P.CLOUD_SCALAR_KEYS],
                    vectors=[tuple(self.U[k]) for k in P.CLOUD_VECTOR_KEYS])

    def _apply_cloud_state(self, a, b, k):
        for i, key in enumerate(P.CLOUD_SCALAR_KEYS):
            self.U[key] = a['scalars'][i] + (b['scalars'][i] - a['scalars'][i]) * k
        for i, key in enumerate(P.CLOUD_VECTOR_KEYS):
            self.U[key] = tuple(a['vectors'][i][c] + (b['vectors'][i][c] - a['vectors'][i][c]) * k for c in range(3))

    def set_clouds(self, name, over=None):
        self.cloud_transition = None
        resolved = name if name in P.PRESETS else 'cumulus'
        self.state['preset'] = resolved
        p = dict(P.PRESETS[resolved])
        p.update(over or {})
        p.setdefault('stormCanopy', 0.0)
        for key, uni in P.PRESET_UNIFORM.items():
            if key in p:
                v = p[key]
                self.U[uni] = _vec(v) if isinstance(v, (tuple, list)) else float(v)
        self.cloud_visible = p['finalMul'] > 0 or p['wispOn'] > 0 or p.get('stormCanopy', 0) > 0
        self._update_wisp_color()
        return resolved

    def transition_clouds(self, name, duration=45.0, over=None):
        resolved = name if name in P.PRESETS else 'cumulus'
        from_preset = self.state['preset']
        from_visible = self.cloud_visible
        frm = self._capture_cloud_state()
        self.set_clouds(resolved, over)
        to = self._capture_cloud_state()
        to_visible = self.cloud_visible
        self._apply_cloud_state(frm, frm, 0)
        self._update_wisp_color()
        has = from_visible or to_visible
        self.cloud_visible = has
        self.state['preset'] = 'transition' if has else resolved
        self.cloud_transition = dict(fromPreset=from_preset, toPreset=resolved, frm=frm, to=to, toVisible=to_visible,
                                     t0=None, duration=max(0.001, float(duration)))
        return True

    # ---- per frame ----
    def update(self, t):
        U = self.U
        U['time'] = float(t)
        U['cloudDisplacement'] = self.cloud_motion.update(float(t), U['skyWind'])
        tr = self.cloud_transition
        if tr:
            if tr['t0'] is None:
                tr['t0'] = t
            raw = max(0.0, min(1.0, (t - tr['t0']) / tr['duration']))
            eased = raw * raw * (3 - 2 * raw)
            self._apply_cloud_state(tr['frm'], tr['to'], eased)
            self._update_wisp_color()
            if raw >= 1:
                self.state['preset'] = tr['toPreset']
                self.cloud_visible = tr['toVisible']
                self.cloud_transition = None

    def apply_to_lights(self):
        """The lamp/ambient/fog values the WebGPU applyToLights writes, as plain numbers (three.js space)."""
        o = self.opts
        pal = self.state['palette']
        U = self.U
        night_k = U['moonLightK']
        ml = o.get('moonLightColor') or (0.5, 0.6, 0.95)
        sc = self.sky_color['sun']
        sun_color = tuple((pal['sun'][i] * (1 - night_k) + ml[i] * night_k) * sc[i] for i in range(3))
        moon_up = max(0.0, min(1.0, self.moon_dir[1] / 0.12))
        solar_gain = 1.0 if self.solar_occlusion else U['solarVisibility']
        sun_intensity = (max(0.08, pal['int'] * 1.15) * (1 - night_k) * solar_gain
                         + o.get('moonLightIntensity', 0.35) * night_k * moon_up * moon_up * (3 - 2 * moon_up))
        key_dir = self.moon_dir if night_k > 0.5 else self.sun_dir
        zen, hor = U['zenith'], U['horizon']
        hemi_color = tuple(c * 2.2 for c in zen)
        hemi_ground = (hor[0] * 0.25, hor[1] * 0.2, hor[2] * 0.18)
        hemi_intensity = (0.25 + pal['int'] * 0.25 + night_k * 0.06) * U['solarSkyVisibility']
        F = self.sky_color['fog']
        fog = tuple(hor[i] * F[i] * (0.5 + pal['int'] * 0.12) * U['solarSkyVisibility'] for i in range(3))
        return dict(sun_color=sun_color, sun_intensity=sun_intensity, key_dir=key_dir, night_k=night_k,
                    hemi_color=hemi_color, hemi_ground=hemi_ground, hemi_intensity=hemi_intensity, fog_color=fog,
                    palette=pal)
