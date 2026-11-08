"""make_weather_system: the Blender makeWeatherSystem (eidoverse/weather_system.js), on top of the sky package.

    from eidoblend.sky import make_sky
    from eidoblend.weather import make_weather_system
    sky = make_sky(scene, camera=cam, hours=17.0, weather='overcast', cache_dir=cache)
    wx = make_weather_system(scene, sky, strike_targets=[street], occluders=street)
    wx.wrap_scene()                                  # eido_wet in front of every Principled BSDF
    wx.transition_to('darkstorm', 1.0, 12.0, at=3.0)   # direction calls go to the sky's recipe
    wx.bake()                                        # plan every frame, bake the sky with the flashes, key it all
    wx.write_audio('wx_audio.json'); wx.bake_audio('wx.wav')
    bpy.ops.render.render(animation=True)            # no Python in the loop: the .blend replays the weather

The sky owns the weather state machine (WEATHER, setWeather, transitionTo, the eased morph, greying, sun / hemi
dimming). This system reads it frame by frame, after the sky's update, exactly where the JS weather.update(t, camera)
runs, and writes what the WebGPU uniforms carried as keyed Blender data: the rain and splash generators' inputs, the
shader values (rainK, rainLight, rainColor, wetness, surface water, time, rain direction, moisture centre), the
strike light, one bolt per event, impact objects per local strike, the moisture sequence, and the eido_weather
object's custom properties (the weather-audio contract). The lightning flash goes into the sky's own bake through an
on_frame callback (zenith / horizon flash, sheet flash, the cloud glow at the strike).
"""
import json
import math
import os

import numpy as np

from . import lightning as L
from .frame import rain_light

_REGISTRY = {}
ASSET_DROP = ('sky', 'rain_streak.png')
ASSET_BOLT = ('particle_textures', 'trace_06.png')


def _t3(v):
    return (float(v[0]), float(v[2]), -float(v[1]))


def _b3(v):
    return (float(v[0]), -float(v[2]), float(v[1]))


def _sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class WeatherFX:
    """The weather system of one scene (making a second one disposes the first, as the JS registry does)."""

    def __init__(self, scene, sky, rain_count=16000, rain_radius=45.0, rain_height=24.0, splash_count=1200,
                 ground_y=0.0, fall_speed=11.0, puddles=1.0, wet_tint=(1.0, 1.0, 1.0),
                 lightning_gap_scale=L.DEFAULT_GAP_SCALE, storm_center=None, storm_range=700.0,
                 strike_targets=None, strike_height_at=None, on_local_strike=None, occluders=None,
                 drop_texture='default', bolt_texture='default', moisture=True, moisture_radius=1024.0,
                 moisture_resolution=256, rain_color=None, cloud_color=None, sun_color=None, shield_color=None,
                 wet_model='moisture', wet_exposure=True, cache_dir=None, log=print):
        import bpy
        if sky is None:
            raise ValueError('make_weather_system: pass the scene\'s Sky (eidoblend.sky.make_sky): the weather reads '
                             'its state machine, palette and weather field')
        old = _REGISTRY.get(scene.name)
        if old is not None:
            old.dispose()
        self.scene, self.sky, self.log = scene, sky, log
        self.opts = dict(rain_count=int(rain_count), rain_radius=float(rain_radius), rain_height=float(rain_height),
                         splash_count=int(splash_count), ground_y=float(ground_y), fall_speed=float(fall_speed),
                         puddles=float(puddles), wet_tint=tuple(wet_tint), storm_range=float(storm_range),
                         moisture_radius=float(moisture_radius), moisture_resolution=int(moisture_resolution))
        self.storm_center3 = ((float(storm_center[0]), -float(storm_center[1])) if storm_center is not None
                              else (0.0, 0.0))
        self.strike_targets = strike_targets
        self.on_local_strike = on_local_strike
        self.occluders = occluders
        self.use_moisture = bool(moisture)
        from .wet import WET_MODELS
        if wet_model not in WET_MODELS:
            raise ValueError("make_weather_system: wet_model must be one of %s, not '%s'"
                             % (' | '.join(WET_MODELS), wet_model))
        self.wet_model = wet_model
        self.wet_exposure = bool(wet_exposure)
        self.cache_dir = cache_dir or os.path.join(sky.cache_dir, 'weather')
        os.makedirs(self.cache_dir, exist_ok=True)
        from .strike import make_strike_finder
        finder = make_strike_finder(strike_targets, strike_height_at) if (strike_targets or strike_height_at) else None
        self.sched = L.LightningScheduler(gap_scale=lightning_gap_scale, storm_center=self.storm_center3,
                                          storm_range=storm_range, rain_count=rain_count, find_local_strike=finder,
                                          on_local_strike=self._notify_local)
        self.lightning_profile = L.make_lightning_profile(self.sched.gap_scale)
        from ..sky.weather_system import WEATHER
        self.WEATHER = WEATHER
        self._force = []                  # media times of debug_force_local_strike calls
        self._rows = {}
        self._active = False              # the on_frame flash injection runs only for a planned bake
        self.wrapped = []
        self.receivers = []
        self.objects = {}
        self.state = dict(name='clear', k=1.0, def_=None, strike=None, lastImpact=None)
        self.color = dict(rain=(1.0, 1.0, 1.0), cloud=(1.0, 1.0, 1.0), sun=(1.0, 1.0, 1.0), shield=(1.0, 1.0, 1.0))
        self.uniforms = {}
        self.diagnostics = self._fresh_diagnostics()
        # ---- Blender objects ----
        coll = bpy.data.collections.get('eido_weather')
        if coll is None:
            coll = bpy.data.collections.new('eido_weather')
        if coll.name not in scene.collection.children:
            scene.collection.children.link(coll)
        self.collection = coll
        self.weather_map = self._weather_map_image()
        from ..common import asset_path
        drop = asset_path(*ASSET_DROP) if drop_texture == 'default' else drop_texture
        bolt = asset_path(*ASSET_BOLT) if bolt_texture == 'default' else bolt_texture
        self.drop_image = bpy.data.images.load(drop, check_existing=True) if drop else None
        self.bolt_image = bpy.data.images.load(bolt, check_existing=True) if bolt else None
        from . import rain as R
        self.objects.update(R.build_rain_objects(coll, self.weather_map, self.drop_image, occluders,
                                                 rain_count, rain_radius, rain_height, splash_count))
        from .strike import strike_light, bolt_material
        self.light = strike_light(coll)
        self.bolt_material = bolt_material(self.bolt_image)
        self.carrier = bpy.data.objects.get('eido_weather') or bpy.data.objects.new('eido_weather', None)
        if self.carrier.name not in coll.objects:
            coll.objects.link(self.carrier)
        self.rain = self.objects['eido_rain']['object']
        self.bolt = self.light
        colors = {k: v for k, v in (('rain', rain_color), ('cloud', cloud_color), ('sun', sun_color),
                                    ('shield', shield_color)) if v is not None}
        if colors:
            self.set_colors(colors)
        sky.on_frame(self._on_frame)
        sky.weather_fx = self                  # for the sky facade's audio_timeline (the WebGPU api.audioTimeline)
        _REGISTRY[scene.name] = self

    # ------------------------------------------------------------------ direction (through the sky's recipe) ---
    def set_weather(self, name, k=1.0, at=None):
        """setWeather through the sky's recipe; returns the state's WEATHER entry (legacy names resolved, an unknown
        name falls back to clear), as the JS returns w."""
        from ..sky.weather_system import LEGACY_STATES
        self.sky.set_weather(name, k, at=at)
        return self.WEATHER.get(LEGACY_STATES.get(name, name), self.WEATHER['clear'])

    def transition_to(self, name, k=1.0, dur=45.0, at=None):
        self.sky.transition_to(name, k, dur, at=at)
        return self

    def set_colors(self, c=None, at=None):
        """Per-channel multipliers over the active look: rain, cloud, sun, shield. Only the channels named are
        forwarded to the sky (as the JS does); shield reaches the shieldworld's red giant and is ignored, with the
        sky's warning, on a world without one. Returns the weather's colour record."""
        c = dict(c or {})
        fwd = {}
        for k in ('rain', 'cloud', 'sun', 'shield'):
            v = c.get(k)
            if v is not None and len(v) == 3:
                self.color[k] = tuple(float(x) for x in v)
                fwd[k] = self.color[k]
        if fwd:
            self.sky.set_colors(fwd, at=at)
        return self.get_colors()

    def get_colors(self):
        """The weather's colour record (COLOR in the JS): the per-channel multipliers last set, [1, 1, 1] if never."""
        return dict(self.color)

    def sun_dim(self):
        return self.sky.wx.sun_dim()

    def hemi_dim(self):
        return self.sky.wx.hemi_dim()

    def debug_force_local_strike(self, at=0.0):
        """The next lightning event after media time `at` becomes a close forward strike (34-58 m ahead), pulled to
        0.6 s after the call, bypassing chance and cooldown: to look at the impact puff and scorch."""
        self._force.append(float(at))
        self._force.sort()
        return True

    # ------------------------------------------------------------------------------------------- wetness ---
    def wrap_material(self, mat, receiver=None):
        from .wet import wrap_material
        if receiver is not None and receiver not in self.receivers:
            self.receivers.append(receiver)
        ok = wrap_material(mat, receiver, self._seq, model=self.wet_model)
        if ok:
            self.wrapped.append(mat)
        return ok

    def wrap_scene(self, budget=None):
        """eido_wet on every eligible material of the scene's meshes (budget: the WebGPU per-frame compile budget,
        which does not apply: EEVEE compiles at render). Returns how many materials were wrapped."""
        n = 0
        for ob in self.scene.objects:
            if ob.type != 'MESH' or ob.name.startswith('eido_') or ob.get('eido_dry'):
                continue
            for slot in ob.material_slots:
                if slot.material is not None and self.wrap_material(slot.material, ob):
                    n += 1
        self.diagnostics['wetness'].update(wrappedMaterials=len(self.wrapped), receiverMeshes=len(self.receivers),
                                           receiverNames=[o.name for o in self.receivers[:96]])
        self.log('[weather] wetness wrapped %d materials' % n)
        return n

    @property
    def _seq(self):
        return getattr(self, '_seq_range', None)

    # ------------------------------------------------------------------------------------------ per frame ---
    def _fresh_diagnostics(self):
        o = self.opts
        return dict(version='weather-acceptance-v3',
                    transition=dict(active=False, target=None, durationSeconds=0.0, rawProgress=1.0),
                    motion=dict(integration='positive-delta-time-velocity', verticalDirection='downward-only',
                                fallVelocity=0.0, lastDeltaSeconds=0.0, totalFallDistance=0.0,
                                totalWindDistance=[0.0, 0.0], fallPhase=0.0, windOffset=[0.0, 0.0]),
                    precipitation=dict(fieldShape='camera-centred-circular-feather',
                                       darkstormCoverage='sealed-canopy-independent', volumetricCurtains=True,
                                       featherInnerRadius=o['rain_radius'] * 0.70, featherOuterRadius=o['rain_radius'],
                                       opacityBaseRange=[0.075, 0.20], sceneLightResponsive=True,
                                       rainPopulation=o['rain_count'], splashPopulation=o['splash_count'],
                                       rainVisible=False, intensity=0.0, sceneLight=1.0,
                                       sceneColor=[0.72, 0.78, 0.86]),
                    lightning=self.sched.diag,
                    wetness=dict(projection='per-fragment-world-position-and-world-normal',
                                 supportsArbitraryUpwardGeometry=True, wrappedMaterials=0, receiverMeshes=0,
                                 receiverNames=[], wetness=0.0, surfaceWater=0.0, targetWetness=0.0,
                                 puddleStrength=o['puddles']))

    def _reset_run(self):
        self.sched.reset()
        self.diagnostics = self._fresh_diagnostics()
        self.diagnostics['wetness'].update(wrappedMaterials=len(self.wrapped), receiverMeshes=len(self.receivers))
        self._last_t = None
        self._total_fall = 0.0
        self._total_wind = [0.0, 0.0]
        self._force_queue = list(self._force)
        self._moist = None
        if self.use_moisture:
            from .moisture import RainAccumulationField
            self._moist = RainAccumulationField(self._cell_at, self.opts['moisture_radius'],
                                                self.opts['moisture_resolution'])
        self.diagnostics['wetness']['moisture'] = self._moist.stats if self._moist else None

    def _weather_map_image(self):
        import bpy
        from ..sky.bake.baker import weather_map, write_exr
        path = os.path.join(self.cache_dir, 'weather_map.exr')
        if not os.path.exists(path):
            write_exr(path, weather_map(), half=False)
        img = bpy.data.images.get('eido_weather_map')
        if img is None:
            img = bpy.data.images.load(path, check_existing=True)
            img.name = 'eido_weather_map'
        img.colorspace_settings.name = 'Non-Color'
        self._wmap_r = None
        return img

    def _wmap(self):
        if self._wmap_r is None:
            from ..sky.bake.baker import weather_map
            self._wmap_r = weather_map()[..., 0].astype(np.float64)
        return self._wmap_r

    def _coverage(self, x3, z3):
        """tslCoverage over numpy arrays (three x, z): GPU texel centres, bilinear, repeat-wrapped."""
        U = self.sky.sky.U
        r = self._wmap()
        n = r.shape[0]
        s = -0.00005 * float(U['wScale'])
        d = U['cloudDisplacement']
        pu = ((z3 - d[2]) * s) * n - 0.5
        pv = ((x3 - d[0]) * s) * n - 0.5
        iu, iv = np.floor(pu), np.floor(pv)
        fu, fv = pu - iu, pv - iv
        iu, iv = iu.astype(np.int64), iv.astype(np.int64)
        g = lambda a, b: r[(b % n), (a % n)]
        val = (g(iu, iv) * (1 - fu) + g(iu + 1, iv) * fu) * (1 - fv) + (g(iu, iv + 1) * (1 - fu) + g(iu + 1, iv + 1) * fu) * fv
        return np.clip((val - float(U['largeT'])) * float(U['largeA']), 0.0, 2.0)

    def _cell_at(self, x, y, height=0.0):
        """rainCellAt over Blender (x, y) arrays at a height (0: the moisture columns' reference)."""
        u = self.sky.wx.u
        U = self.sky.sky.U
        x3, z3 = np.asarray(x, np.float64), -np.asarray(y, np.float64)
        k = max(float(U['cloudStart']) - height, 0.0) / max(self.opts['fall_speed'] * float(u['fallMul']), 1.0)
        wv = u['windVec']
        cov = self._coverage(x3 - wv[0] * k, z3 - wv[2] * k)
        gate = _sstep(float(u['cellLo']), float(u['cellHi']), cov)
        c = max(0.0, min(1.0, float(U['stormCanopy'])))
        return gate + (1.0 - gate) * c

    def _notify_local(self, damage, hit_object):
        rec = dict(damage)
        rec['point'] = list(_b3(damage['point']))
        rec['normal'] = list(_b3(damage['normal']))
        self.state['lastImpact'] = rec
        if hit_object is not None:
            d = hit_object.get('eido_lightning_strikes', 0)
            hit_object['eido_lightning_strikes'] = int(d) + 1
            hit_object['eido_lightning_last'] = json.dumps(rec)
        if self.on_local_strike:
            self.on_local_strike(rec)

    def update(self, t, camera=None, frame=None):
        """One frame, with the sky already updated to t (inside sky.frame_states or an on_frame-driven loop): the
        WebGPU weather.update(t, camera). Returns the frame's record (what the bake keys)."""
        sky = self.sky
        wx, U, u = sky.wx, sky.sky.U, sky.wx.u
        cam = camera or self.scene.camera
        w, k, tr = wx.state['def_'], float(wx.state['k']), wx.trans
        if getattr(self, '_last_t', 'unset') == 'unset':
            self._reset_run()
        t = float(t) if math.isfinite(t) else 0.0
        while self._force_queue and self._force_queue[0] <= t + 1e-9:
            self._force_queue.pop(0)
            self.sched.force_local_strike(self._last_t if self._last_t is not None else 0.0, w, k)
        dt = 0.0 if self._last_t is None else max(0.0, min(t - self._last_t, 0.1))
        self._last_t = t
        fall_v = max(0.05, self.opts['fall_speed'] * max(0.05, float(u['fallMul'])))
        wv = u['windVec']
        self._total_fall += fall_v * dt
        self._total_wind[0] += wv[0] * dt
        self._total_wind[1] += wv[2] * dt
        H, P = self.opts['rain_height'], self.opts['rain_radius'] * 2
        mw = cam.matrix_world
        pos_b = tuple(mw.translation)
        right_b = tuple(mw.col[0][:3])
        up_b = tuple(mw.col[1][:3])
        back_b = tuple(mw.col[2][:3])

        def unit(v):
            n = math.sqrt(sum(c * c for c in v)) or 1.0
            return tuple(c / n for c in v)

        cam3 = dict(pos=_t3(pos_b), forward=_t3(unit(tuple(-c for c in back_b))))
        right3, up3 = _t3(unit(right_b)), _t3(unit(up_b))
        bk = sky.baker()
        sky_d = dict(cloudStart=float(U['cloudStart']), cloudHeight=float(U['cloudHeight']),
                     weather_at=lambda x, z: bk.weather_at(U, x, z))
        r = self.sched.step(t, w, k, tr['toName'] if tr else None, cam3, sky_d)
        pal = sky.sky.state['palette']
        light, lit, rcol = rain_light(pal, w, U['stormCanopy'], u['rainK'], r['flash'], r['flash_d'], r['color'],
                                      wx.color['rain'])
        rain_vis = float(u['rainK']) > 0.001
        if tr:
            rain_vis = rain_vis or tr['fromDef']['rain'] * tr['fromK'] > 0.001 or tr['toDef']['rain'] * tr['toK'] > 0.001
        fall = self.opts['fall_speed'] * float(u['fallMul'])
        sdir3 = unit((wv[0], -fall, wv[2]))
        src_b = tuple(-c for c in _b3(sdir3))
        moist = None
        moist_cam = (0.0, 0.0)
        if self._moist is not None:
            self._moist.prepare((pos_b[0], pos_b[1]), t, float(u['rainK']), float(u['wetTarget']))
            moist = (float(self._moist.center[0]), float(self._moist.center[1]), self._moist.span)
            mc = self._moist.sample(pos_b[0], pos_b[1])[0]
            moist_cam = (float(mc[0]), float(mc[1]))
        cell_cam = float(self._cell_at(np.array([pos_b[0]]), np.array([pos_b[1]]))[0])
        st = r['strike']
        strike_b = None
        if st:
            sb = _b3((st['x'], st['y'], st['z']))
            strike_b = dict(id=st['interval'], x=sb[0], y=sb[1], z=sb[2], flash=st['flash'], local=st['local'])
        row = dict(frame=frame if frame is not None else self.scene.frame_current, t=t,
                   weather=wx.state['name'], k=k, target=tr['toName'] if tr else None,
                   cam3=cam3['pos'], right3=right3, up3=up3, cam_matrix=[list(rw) for rw in mw],
                   fall_phase=self._total_fall % (H * 1000.0),
                   wind_offset=((self._total_wind[0] % (P * 100) + P * 100) % (P * 100), 0.0,
                                (self._total_wind[1] % (P * 100) + P * 100) % (P * 100)),
                   wind=tuple(wv), wind_len=math.sqrt(sum(c * c for c in wv)), fall=fall,
                   streak_len=float(u['streakLen']), rain_k=float(u['rainK']), dense_a=float(u['denseA']),
                   dash_k=float(u['dashK']), cell_lo=float(u['cellLo']), cell_hi=float(u['cellHi']),
                   storm_canopy=float(U['stormCanopy']), sun_dir=tuple(U['sunDir']),
                   cloud_start=float(U['cloudStart']), cloud_drift=tuple(U['cloudDisplacement']),
                   w_scale=float(U['wScale']), large_t=float(U['largeT']), large_a=float(U['largeA']),
                   rain_light=light, lit_rain=lit, rain_color=rcol, wetness=float(u['wetness']),
                   surface_water=float(u['surfaceWater']), wet_target=float(u['wetTarget']), rain_visible=rain_vis,
                   src=src_b, moist=moist, moisture_at_camera=moist_cam, cell_at_camera=cell_cam,
                   strike_blender=strike_b, **{'l_' + key: v for key, v in r.items() if key not in ('strike',)})
        row['l_strike'] = st
        self._update_state(row, r, w, k, tr)
        return row

    def _update_state(self, row, r, w, k, tr):
        self.state.update(name=self.sky.wx.state['name'], k=row['k'], def_=w, strike=r['strike'])
        D = self.diagnostics
        D['transition'].update(active=tr is not None, target=tr['toName'] if tr else None,
                               durationSeconds=tr['dur'] if tr else 0.0, rawProgress=self.sky.wx.trans_s if tr else 1.0)
        D['motion'].update(fallVelocity=row['fall'], totalFallDistance=self._total_fall,
                           totalWindDistance=list(self._total_wind), fallPhase=row['fall_phase'] % self.opts['rain_height'],
                           windOffset=[row['wind_offset'][0] % (self.opts['rain_radius'] * 2),
                                       row['wind_offset'][2] % (self.opts['rain_radius'] * 2)])
        D['precipitation'].update(rainVisible=row['rain_visible'], intensity=row['rain_k'], sceneLight=row['rain_light'],
                                  sceneColor=list(row['lit_rain']))
        D['wetness'].update(wetness=row['wetness'], surfaceWater=row['surface_water'], targetWetness=row['wet_target'])
        self.uniforms = dict(time=row['t'], rainK=row['rain_k'], fallPhase=row['fall_phase'] % self.opts['rain_height'],
                             windOffset=row['wind_offset'], windVec=row['wind'], streakLen=row['streak_len'],
                             fallMul=row['fall'] / self.opts['fall_speed'], dashK=row['dash_k'],
                             rainColor=row['rain_color'], rainLight=row['rain_light'], wetness=row['wetness'],
                             wetTint=self.opts['wet_tint'], puddleK=self.opts['puddles'], cellLo=row['cell_lo'],
                             cellHi=row['cell_hi'], denseA=row['dense_a'], camPos=row['cam3'],
                             camRight=row['right3'], camUp=row['up3'])

    def _generators_off(self):
        """A context in which the weather's Geometry Nodes objects (rain, splashes, impacts) skip the viewport
        depsgraph. The sky's replay steps every frame with frame_set while a callback is registered, and the rain's
        16000 ray casts per frame were most of a one-frame sky bake (70 s for a frame 45 s into a film). Renders use
        the render depsgraph (show_render), so a bake or render in between is unaffected."""
        import contextlib

        @contextlib.contextmanager
        def ctx():
            mods = [m for ob in self.collection.objects for m in ob.modifiers if m.type == 'NODES']
            was = [m.show_viewport for m in mods]
            for m in mods:
                m.show_viewport = False
            try:
                yield
            finally:
                for m, v in zip(mods, was):
                    m.show_viewport = v
        return ctx()

    # ---------------------------------------------------------------------------------- the sky's flash hook ---
    def _on_frame(self, sky, t):
        if not self._active:
            return
        row = self._rows.get(self.scene.frame_current)
        if row is None:
            return
        wx = sky.wx
        wx.flash = row['l_flash']
        wx.flash_d = row['l_flash_d']
        wx.strike_color = tuple(row['l_color'])
        sky.sky.U['lightningFlashColor'] = tuple(row['l_color'])
        sky.sky.U['lightningStrike'] = tuple(row['l_sky_strike'])

    # ----------------------------------------------------------------------------------------------- bake ---
    def plan(self, frame_end=None, write_from=None):
        """Every frame from the scene's first to frame_end, state only: the frame records the bake keys. The
        moisture images are written from `write_from` on (default: the scene's first frame); earlier frames are a
        pre-roll that only integrates (the wetness and puddles a shot opens on)."""
        sc = self.scene
        fe = sc.frame_end if frame_end is None else int(frame_end)
        write_from = sc.frame_start if write_from is None else int(write_from)
        self._last_t = 'unset'
        self._active = False
        rows = []
        moist_pat = os.path.join(self.cache_dir, 'moisture_%04d.exr')
        with self._generators_off():
            for f, t, _L in self.sky.frame_states(sc.frame_start, fe):
                row = self.update(t, frame=f)
                rows.append(row)
                if self._moist is not None and f >= write_from:
                    from .wet import write_moisture_frame
                    cx, cy = self._moist.center
                    n = self._moist.size
                    i = (np.arange(n) + 0.5) / n
                    gx, gy = np.meshgrid((i - 0.5) * self._moist.span + cx, (i - 0.5) * self._moist.span + cy)
                    write_moisture_frame(moist_pat, f, self._moist, self._cell_at(gx, gy).astype(np.float32))
        self._rows = {r['frame']: r for r in rows}
        self.rows = rows
        return rows

    def bake(self, frame_start=None, frame_end=None, bake_sky=True, keys=True):
        """Plan, bake the sky layers with the lightning in them (bake_sky=False when you bake the sky yourself after
        this), then key everything. Returns the frame records."""
        import time
        t0 = time.time()
        fs = self.scene.frame_start if frame_start is None else int(frame_start)
        rows = self.plan(frame_end, write_from=fs)
        self.log('[weather] planned %d frames in %.1fs: %d lightning events, %d local strikes'
                 % (len(rows), time.time() - t0, len(self.sched.events), len(self.sched.impacts)))
        self._active = True
        if bake_sky:
            with self._generators_off():
                self.sky.bake(frame_start, frame_end)
        if keys:
            self.key(rows, frame_start=fs)
        self._write_state(rows)
        return rows

    def shelter_map(self, rows, texel=0.15, max_texels=1600):
        """The rain-exposure map of the occluders along the bake's rain-weighted mean direction (shelter.py)."""
        from .shelter import capture, mean_rain_direction
        from .strike import resolve_targets
        from .wet import shelter_image
        from ..sky.bake.baker import write_exr
        objs = resolve_targets(self.occluders)
        if not objs:
            return None
        lo = [math.inf, math.inf]
        hi = [-math.inf, -math.inf]
        for ob in objs:
            for c in ob.bound_box:
                w = ob.matrix_world @ __import__('mathutils').Vector(c)
                lo = [min(lo[0], w.x), min(lo[1], w.y)]
                hi = [max(hi[0], w.x), max(hi[1], w.y)]
        span = max(hi[0] - lo[0], hi[1] - lo[1])
        texel = max(texel, span / max_texels)
        d = mean_rain_direction(rows)
        pad = 2.0
        rgba, meta, z_low = capture(objs, d, (lo[0] - pad, lo[1] - pad, hi[0] + pad, hi[1] + pad), texel,
                                    log=self.log, lowest=True)
        path = os.path.join(self.cache_dir, 'rain_exposure.exr')
        write_exr(path, rgba, half=False)
        shelter_image(path)
        from .shelter import soft_map
        soft = soft_map(rgba, z_low, meta)
        spath = os.path.join(self.cache_dir, 'rain_exposure_soft.exr')
        write_exr(spath, soft, half=False)
        from .wet import SHELTER_SOFT_IMAGE
        shelter_image(spath, SHELTER_SOFT_IMAGE)
        self.shelter = meta
        return meta

    def key(self, rows, frame_start=None):
        """Key the planned frames into the scene (rain, splashes, shader values, light, bolts, impacts, the
        eido_weather properties) and point every wrapped material at the moisture sequence (from frame_start)."""
        import bpy
        from ._graph import mod_path
        from .keys import key_series, changes_only
        from .values import key_values
        from . import strike as S
        frames = [r['frame'] for r in rows]
        seq_from = frames[0] if frame_start is None else int(frame_start)
        sc = self.scene
        fps = sc.render.fps / sc.render.fps_base
        rain = self.objects['eido_rain']
        splash = self.objects['eido_splashes']
        rk = dict(Camera='cam3', **{'Camera Right': 'right3', 'Fall Phase': 'fall_phase', 'Wind Offset': 'wind_offset',
                                    'Wind': 'wind', 'Fall': 'fall', 'Streak Length': 'streak_len', 'Rain K': 'rain_k',
                                    'Density': 'dense_a', 'Cell Lo': 'cell_lo', 'Cell Hi': 'cell_hi',
                                    'Storm Canopy': 'storm_canopy', 'Sun Dir': 'sun_dir', 'Cloud Start': 'cloud_start',
                                    'Cloud Drift': 'cloud_drift', 'Weather Scale': 'w_scale', 'Large T': 'large_t',
                                    'Large A': 'large_a'})
        sk = dict(Camera='cam3', Time='t', Wind='wind', Fall='fall', **{'Rain K': 'rain_k', 'Cell Lo': 'cell_lo',
                                                                        'Cell Hi': 'cell_hi',
                                                                        'Storm Canopy': 'storm_canopy',
                                                                        'Cloud Start': 'cloud_start',
                                                                        'Cloud Drift': 'cloud_drift',
                                                                        'Weather Scale': 'w_scale',
                                                                        'Large T': 'large_t', 'Large A': 'large_a'})
        for gen, table in ((rain, rk), (splash, sk)):
            ob, mod, ids = gen['object'], gen['modifier'], gen['ids']
            for name, field in table.items():
                key_series(ob, mod_path(mod, ids[name]), frames, [r[field] for r in rows], 'LINEAR')
            # the JS rainInst.visible and splashInst.visible (= rain visible && splashCount > 0)
            none = gen is splash and self.opts['splash_count'] <= 0
            hf, hv = changes_only(frames, [0.0 if (r['rain_visible'] and not none) else 1.0 for r in rows])
            key_series(ob, 'hide_render', hf, hv, 'CONSTANT')
            key_series(ob, 'hide_viewport', hf, hv, 'CONSTANT')
        from .rain import SPLASH_INPUTS  # noqa: F401  (Ground Y is a constant)
        from ._graph import set_input
        set_input(splash['modifier'], splash['ids']['Ground Y'], self.opts['ground_y'])
        vals = dict(time=[r['t'] for r in rows], rain_k=[r['rain_k'] for r in rows],
                    rain_light=[r['rain_light'] for r in rows], rain_r=[r['rain_color'][0] for r in rows],
                    rain_g=[r['rain_color'][1] for r in rows], rain_b=[r['rain_color'][2] for r in rows],
                    wetness=[r['wetness'] for r in rows], surface_water=[r['surface_water'] for r in rows],
                    wet_target=[r['wet_target'] for r in rows], puddle_k=[self.opts['puddles']] * len(rows),
                    wet_tint_r=[self.opts['wet_tint'][0]] * len(rows), wet_tint_g=[self.opts['wet_tint'][1]] * len(rows),
                    wet_tint_b=[self.opts['wet_tint'][2]] * len(rows), src_x=[r['src'][0] for r in rows],
                    src_y=[r['src'][1] for r in rows], src_z=[r['src'][2] for r in rows])
        if self._moist is not None:
            vals.update(moist_cx=[r['moist'][0] for r in rows], moist_cy=[r['moist'][1] for r in rows],
                        moist_span=[r['moist'][2] for r in rows])
        meta = (self.shelter_map(rows) if self.occluders is not None and self.wrapped and self.wet_exposure
                and self.wet_model == 'moisture' else None)
        n = len(rows)
        if meta is not None:
            from .wet import link_shelter
            for m in self.wrapped:
                link_shelter(m)
            vals.update(shelter_on=[1.0] * n, sh_x0=[meta['x0']] * n, sh_y0=[meta['y0']] * n, sh_sx=[meta['sx']] * n,
                        sh_sy=[meta['sy']] * n, sh_w=[float(meta['w'])] * n, sh_h=[float(meta['h'])] * n,
                        sh_dx=[meta['d'][0]] * n, sh_dy=[meta['d'][1]] * n, sh_dz=[meta['d'][2]] * n)
        else:
            vals.update(shelter_on=[0.0] * n)          # no rain shadow on wet ground (none captured, or turned off)
        key_values(frames, vals)
        if self._moist is not None:
            from .wet import moisture_sequence, set_sequence
            n_seq = frames[-1] - seq_from + 1
            moisture_sequence(os.path.join(self.cache_dir, 'moisture_%04d.exr'), seq_from, n_seq)
            self._seq_range = (seq_from, n_seq)
            for m in self.wrapped:
                set_sequence(m, seq_from, n_seq)
        lrecs = [dict(light_intensity=r['l_light_intensity'], color=r['l_color'], light_pos=r['l_light_pos'],
                      channel=r['l_channel'], bolt_seed=r['l_bolt_seed']) for r in rows]
        S.key_strike_light(self.light, frames, lrecs)
        for ob in [o for o in self.collection.objects if o.name.startswith(('eido_bolt_', 'eido_impact_'))]:
            bpy.data.objects.remove(ob, do_unlink=True)
        for ev in self.sched.events:
            S.make_bolt(ev, self.collection, self.bolt_material, frames, lrecs)
        times = [r['t'] for r in rows]
        cams = [(r['right3'], r['up3']) for r in rows]
        for imp in self.sched.impacts:
            S.make_impact(imp, self.collection, frames, times, cams, sc.frame_start / fps)
        # the weather-audio contract (eidoblend.media.weather_audio.read_props): keyed custom properties
        car = self.carrier
        for key, vals_, interp in (('rainK', [r['rain_k'] for r in rows], 'LINEAR'),
                                   ('denseA', [r['dense_a'] for r in rows], 'LINEAR'),
                                   ('wind_len', [r['wind_len'] for r in rows], 'LINEAR'),
                                   ('strike_flash', [(r['strike_blender'] or {}).get('flash', 0.0) for r in rows],
                                    'LINEAR')):
            car[key] = 0.0
            key_series(car, f'["{key}"]', frames, vals_, interp)
        sid = [float((r['strike_blender'] or {}).get('id', -1)) for r in rows]
        for key, vv in (('strike_id', sid),
                        ('strike_x', [(r['strike_blender'] or {}).get('x', 0.0) for r in rows]),
                        ('strike_y', [(r['strike_blender'] or {}).get('y', 0.0) for r in rows]),
                        ('strike_z', [(r['strike_blender'] or {}).get('z', 0.0) for r in rows]),
                        ('strike_local', [1.0 if (r['strike_blender'] or {}).get('local') else 0.0 for r in rows])):
            car[key] = 0.0
            f2, v2 = changes_only(frames, vv)
            key_series(car, f'["{key}"]', f2, v2, 'CONSTANT')
        self.log('[weather] keyed %d frames: %d bolts, %d impacts' % (len(frames), len(self.sched.events),
                                                                     len(self.sched.impacts)))

    def _write_state(self, rows):
        drop = ('cam_matrix', 'l_strike')
        out = []
        for r in rows:
            out.append({k: v for k, v in r.items() if k not in drop})
        with open(os.path.join(self.cache_dir, 'weather_state.json'), 'w', encoding='utf-8') as f:
            json.dump(dict(frames=out, events=[dict(interval=e['interval'], time=e['time'], strike=e['strike'],
                                                    color_key=e['color_key'], local=e['strike']['local'],
                                                    damage=e['damage']) for e in self.sched.events],
                           diagnostics=self.diagnostics), f, indent=1, default=str)

    # ----------------------------------------------------------------------------------------------- audio ---
    def _t0(self, frame_start):
        if frame_start is None:
            return 0.0
        sc = self.scene
        return (int(frame_start) - sc.frame_start) / (sc.render.fps / sc.render.fps_base)

    def audio_timeline(self, frame_start=None, **kw):
        """The weather_audio.js timeline of the planned frames (rain bed, wind bed, thunder events), as a dict;
        frame_start: the shot's first frame (the track's 0) when the bake had a pre-roll."""
        from .audio import record
        return record(self.rows, t0=self._t0(frame_start), **kw).timeline()

    @property
    def audio(self):
        """The weather-audio recorder fed with the planned frames (sky_worlds.js `audio`: stats, timeline()), or None
        before a plan."""
        if not getattr(self, 'rows', None):
            return None
        from .audio import record
        return record(self.rows)

    def audio_json(self, frame_start=None, **kw):
        """The timeline as weather_audio.js's toJSON() writes it (JSON, one-space indent): the string sky_worlds.js's
        audioTimeline() returns. None before a plan."""
        if not getattr(self, 'rows', None):
            return None
        return json.dumps(self.audio_timeline(frame_start, **kw), indent=1)

    def write_audio(self, path, frame_start=None, **kw):
        from .audio import record, write_timeline
        return write_timeline(record(self.rows, t0=self._t0(frame_start), **kw), path)

    def bake_audio(self, wav_path, timeline_path=None, duration=None, frame_start=None, **kw):
        """The timeline baked to a stereo WAV with the repo-root bake_weather_audio.py (sky audio assets)."""
        from .audio import bake_wav
        timeline_path = timeline_path or os.path.splitext(wav_path)[0] + '.json'
        self.write_audio(timeline_path, frame_start=frame_start, **kw)
        if duration is None:
            sc = self.scene
            duration = ((self.rows[-1]['t'] - self._t0(frame_start)) + 1.0 / (sc.render.fps / sc.render.fps_base)
                        if self.rows else None)
        return bake_wav(timeline_path, wav_path, duration)

    @staticmethod
    def merge_av(video, wav, out, **kw):
        from .audio import merge
        return merge(video, wav, out, **kw)

    # ------------------------------------------------------------------------------------------ inventory ---
    def pipeline_warmup_objects(self):
        """Every weather object (the WebGPU list existed to compile pipelines before a switch; EEVEE compiles at
        render, so this is an inventory)."""
        return [o for o in self.collection.objects]

    def dispose(self):
        """Restore wrapped materials, remove the weather's objects, materials and groups, unhook the sky."""
        import bpy
        from .wet import unwrap_material
        for m in list(self.wrapped):
            unwrap_material(m)
        self.wrapped.clear()
        if self._on_frame in self.sky.callbacks:
            self.sky.callbacks.remove(self._on_frame)
        if getattr(self.sky, 'weather_fx', None) is self:
            self.sky.weather_fx = None
        coll = bpy.data.collections.get('eido_weather')
        if coll is not None:
            for ob in list(coll.objects):
                data = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                if data is not None and data.users == 0:
                    if isinstance(data, bpy.types.Mesh):
                        bpy.data.meshes.remove(data)
                    elif isinstance(data, bpy.types.Light):
                        bpy.data.lights.remove(data)
            bpy.data.collections.remove(coll)
        for name in [m.name for m in bpy.data.materials if m.name.startswith('eido_') and m.name in (
                'eido_rain', 'eido_splash', 'eido_bolt', 'eido_spark', 'eido_puff', 'eido_scorch')]:
            bpy.data.materials.remove(bpy.data.materials[name])
        for name in [g.name for g in bpy.data.node_groups if g.name in (
                'eido_rain_streaks', 'eido_rain_splashes', 'eido_impact_sparks', 'eido_impact_puffs',
                'eido_impact_scorch', 'eido_wet', 'eido_wet_eidoverse', 'eido_moisture_uv', 'eido_shelter_uv',
                'eido_weather_values')]:
            bpy.data.node_groups.remove(bpy.data.node_groups[name])
        if _REGISTRY.get(self.scene.name) is self:
            del _REGISTRY[self.scene.name]
        self._active = False
        return True


def make_weather_system(scene=None, sky=None, **opts):
    """The Blender makeWeatherSystem({scene, sky, opts}). Options, by their WebGPU names in snake_case:

    rain_count 16000, rain_radius 45 (world tile half-extent, m), rain_height 24 (vertical recycle, m),
    splash_count 1200, ground_y 0 (the splash plane's height when there are no occluders), fall_speed 11 (m/s),
    puddles 1, wet_tint (1, 1, 1), lightning_gap_scale 0.42 (eidoverse's offline cadence; 1 = the realtime one),
    storm_center (Blender x, y) and storm_range 700 (where distant strikes land), strike_targets (objects /
    collections / a callable: local strikes land on them), strike_height_at(x, y) -> z (heightfield fallback),
    on_local_strike(record), rain_color / cloud_color / sun_color (per-channel multipliers), drop_texture /
    bolt_texture (paths; default the repo's rain_streak.png and trace_06.png; None draws the procedural shapes).
    Blender additions: occluders (a collection: rain stops at roofs, splashes land on surfaces), moisture (the 2D
    history, default on), moisture_radius 1024 / moisture_resolution 256 (Eanpa's), wet_model 'moisture' (eido_wet:
    Eanpa's response over the moisture history) or 'eidoverse' (eido_wet_eidoverse: eidoverse's one global
    wetness), wet_exposure True (the occluders' rain shadow on wet ground; False keeps them for drops and splashes
    only), cache_dir.
    """
    import bpy
    scene = scene or bpy.context.scene
    return WeatherFX(scene, sky, **opts)
