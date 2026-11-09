"""eidoblend.sky -- the eidoverse sky worlds and weather in Blender 5.2 EEVEE.

    from eidoblend.sky import make_sky
    sky = make_sky(scene, camera=cam, world='ringworld', hours=16.5, clouds='cumulus', cache_dir=...)
    sky.transition_to('storm', 1.0, 45, at=8.0)        # direction calls take an optional media time `at`
    sky.bake()                                          # frames -> sky layers, world, lamps, sky-element keys
    bpy.ops.render.render(animation=True)

One call selects a whole world (eidoverse/sky_worlds.js): 'earth', 'ringworld' (the Orbital / Halo band overhead,
its rock-giant companion and ring-native cloud deck) or 'shieldworld' (Earth 5129323011 CE: the red giant, the
planetary hex shield and the shattered moon). The sky is ours: the WebGPU cloud and celestial shaders run as GLSL in
Blender's GPU module (bake/), once per film frame, from the same Python state machine (sky_system.py,
weather_system.py, redgiant.py). The world's geometry (the ringworld band, the shattered moon) is real EEVEE geometry
(ringworld.py, asteroid_moon.py) whose materials composite the sky's shield and clouds over themselves, so the local
clouds always draw in front of them, as the WebGPU draw order had it. EEVEE uses the rest natively: the world shows
the sky and lights with it, the sun lamp is keyed from the palette, a hidden caster plane carries the cloud shadows.
See tools-guides/sky-weather.md.
"""
import json
import math
import os

import numpy as np

from . import palette as P
from .sky_system import SkySystem
from .weather_system import WeatherSystem, WEATHER
from .worlds import WORLDS, SKY_WORLDS, ring_constants

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
ASSETS = os.path.join(REPO, 'eidoverse', 'assets', 'sky')

QUALITY = {
    'film': dict(m_pass=8, n_march=60, n_light=20, env=(1024, 512), shadow=512),
    'draft': dict(m_pass=3, n_march=60, n_light=20, env=(512, 256), shadow=256),
}

# three.js directional light: radiance out = albedo * E / pi, the same as a Blender sun's W/m^2, so the
# palette's sun intensity is the lamp's strength unchanged. `ambient` scales the world's DIFFUSE light only:
# EEVEE's world lighting tells diffuse from glossy rays (probe_world_api.py P5), so camera and glossy rays
# always see the sky at the radiance the camera sees, and a mirror reflects the sky it stands under at any
# ambient. 1.0 lights diffuse surfaces with the sky as it is; WebGPU fills diffuse with a hemisphere light worth
# ~0.4 of its environment (with its cloud-reflect hook on), which ambient=0.4 reproduces.
DEFAULT_AMBIENT = 1.0

# the shieldworld's night (Eanpa src/shieldworld.js): three colours, linear
HEMI_CYAN = (0.29, 0.73, 1.0)                  # new Color(0.29, 0.73, 1.0): linear as given
NIGHT_AMBIENT = (0.0685, 0.4910, 1.0)          # 0x4abaff (sRGB) in linear
MOON_AMBIENT = (0.6308, 0.1441, 0.0452)        # 0xd06a3c (sRGB) in linear
MOON_KEY = (1.0, 0.62, 0.35)                   # the moon's key: the red giant's spectrum
CLIP_FOR = dict(ringworld=16000.0, shieldworld=60000.0)


def _cam_window(cam_obj, scene):
    """Half-angle tangents (x, y) of a symmetric window that covers the camera frame.

    Read from Blender's own frame (Camera.view_frame: the sensor fit, AUTO included, which fits sensor_width
    to the LARGER side, so a portrait frame's height; lens shift; pixel aspect), so the window is the render's.
    """
    cd = cam_obj.data
    if cd.type != 'PERSP':
        raise ValueError('make_sky: the sky camera must be a perspective camera')
    corners = cd.view_frame(scene=scene)            # camera space, all at one depth z < 0
    return max(abs(v.x / v.z) for v in corners), max(abs(v.y / v.z) for v in corners)


def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _read_exr(path):
    """An EXR as a float (H, W, 4) array, row 0 at the bottom (Blender's order, as write_exr takes it)."""
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        return px.reshape(h, w, 4)
    finally:
        bpy.data.images.remove(img)


def _resize_bilinear(img, h, w):
    """Resample an (H, W, C) image to (h, w) over the same window: pixel centres to pixel centres, edges held."""
    H, W = img.shape[:2]
    if (H, W) == (h, w):
        return img
    ys = (np.arange(h) + 0.5) * H / h - 0.5
    xs = (np.arange(w) + 0.5) * W / w - 0.5
    y0 = np.floor(ys).astype(np.int64)
    x0 = np.floor(xs).astype(np.int64)
    fy = (ys - y0)[:, None, None].astype(np.float32)
    fx = (xs - x0)[None, :, None].astype(np.float32)
    ya, yb = np.clip(y0, 0, H - 1), np.clip(y0 + 1, 0, H - 1)
    xa, xb = np.clip(x0, 0, W - 1), np.clip(x0 + 1, 0, W - 1)
    top = img[ya][:, xa] * (1 - fx) + img[ya][:, xb] * fx
    bot = img[yb][:, xa] * (1 - fx) + img[yb][:, xb] * fx
    return top * (1 - fy) + bot * fy


class Sky:
    def __init__(self, scene, camera, world, hours, clouds, weather, weather_k, sun, cache_dir, quality, ambient,
                 shadows, opts, shadow_height=None, shadow_ground=0.0, cloud_dome=None):
        import bpy
        if world not in WORLDS:
            raise ValueError("make_sky: unknown world '%s'. Pick one of: %s" % (world, ' | '.join(WORLDS)))
        self.scene = scene
        self.camera = camera or scene.camera
        if self.camera is None:
            raise ValueError('make_sky: pass camera= or set scene.camera')
        self.W = WORLDS[world]
        self.world_key = world
        opts = dict(opts or {})
        self.audio_on = bool(opts.pop('audio', True))   # makeSky's audio flag: the weather-audio timeline on or off
        o = dict(self.W['sky'])
        # the sky's own options; the world modules' option dicts (ring=, redGiant=) and the atlas path stay out of it
        o.update({k: v for k, v in opts.items() if k not in ('cirrus_atlas', 'ring', 'redGiant')})
        o.update(hours=hours, clouds=clouds)
        if self.W.get('planetShine') and 'moonLightColor' not in opts:
            o['moonLightColor'] = tuple(self.W['planetShine'])
        # the world's celestial module FIRST: the red giant's palette goes into the sky it rides
        self.red_giant = None
        if world == 'shieldworld':
            from .redgiant import make_red_giant
            self.red_giant = make_red_giant(dict(opts.get('redGiant') or {}, shield=True))
            o.setdefault('paletteTint', self.red_giant.palette_tint)
        self._opts0 = o                       # the starting point every bake replays from
        self._weather0 = (weather, weather_k)
        self.q = dict(QUALITY[quality]) if isinstance(quality, str) else dict(quality)
        self.ambient = ambient
        self.use_shadows = shadows
        self.shadow_height = shadow_height    # None: just under the lowest cloud base of the bake
        self.shadow_ground = shadow_ground
        if cache_dir is None and bpy.data.filepath:
            cache_dir = bpy.path.abspath('//sky_cache')
        self.cache_dir = cache_dir
        if not self.cache_dir:
            raise ValueError('make_sky: pass cache_dir= (the .blend is unsaved, so there is no // to bake beside)')
        self.sun = sun or self._make_sun_lamp()
        self.weather_fx = None              # set by eidoblend.weather.make_weather_system
        self.fog = None
        self.dome_radius = None
        self.layer_scale = 1.0
        self.recipe = []            # every direction call in call order: (at or None, seq, fn)
        self._seq = 0
        self._replaying = False
        self.callbacks = []
        self._baker = None
        self.cirrus_atlas = opts.get('cirrus_atlas')
        # the world's own geometry
        self.ring = None
        self.moon = None
        need = CLIP_FOR.get(world)
        if need and self.camera.data.clip_end < need:
            self.camera.data.clip_end = need
        if self.W.get('band'):
            self._build_ring(opts)
        if self.W.get('moon'):
            self._build_moon()
        if cloud_dome:
            self.use_cloud_dome(3072.0 if cloud_dome is True else float(cloud_dome))
        self._reset_state()

    # ---- the world's geometry ----
    def _build_ring(self, opts):
        from .ringworld import make_ringworld
        b = self.W['band']
        assets = {k: os.path.join(ASSETS, v) for k, v in b.items() if isinstance(v, str)}
        ro = dict(opts.get('ring') or {})
        ro.setdefault('planetShineColor', tuple(self.W['planetShine']))
        ro.setdefault('centerY', b['centerY'])
        # Eanpa's newest band (the eroded v4 relief and its albedo) whenever the repo carries the set beside the
        # band's other maps; reliefDir=False keeps the v1 maps, a folder points at another copy of the set
        cel = os.path.join(ASSETS, 'celestial')
        if os.path.exists(os.path.join(cel, 'ring_relief_v4.bin.gz')):
            ro.setdefault('reliefDir', cel)
        self.ring = make_ringworld(self.scene, assets, ro, cache_dir=os.path.join(self.cache_dir, 'ringworld'))
        self.ring.unlink_scene_sun(self.sun)
        # the band behind every local object (WebGPU's depthless band): its own scene, a plate in the camera layer
        self.ring.make_plate()
        self._plate_job = None
        self.ring_k = ring_constants(self.W['sky']['ringCurve'])

    def _build_moon(self):
        from .asteroid_moon import make_shattered_moon
        m = self.W['moon']
        self.moon = make_shattered_moon(self.scene, os.path.join(ASSETS, m['glb']), spread=m['spread'],
                                        scale=m['scale'])
        self.moon.world_owned = True          # the world's own moon: its orbit, fade and light are the sky's

    def _reset_state(self):
        """The state machine at its starting point: the options, then every immediate call in call order.

        A bake starts here, so the same calls always give the same sky: a second bake does not carry on from
        the first one's end state, and a partial bake replays the frames before it (state only, no layers).
        """
        self.sky = SkySystem(self._opts0)
        if self.ring is not None:
            self.sky.U['ringDeckBase'] = self.ring_k['RING_BASE']
            # Eanpa ringsky.js sky.setSolarOcclusion: the eclipse proxy shadows every receiver of the sun lamp, so
            # the lamp is not also dimmed by the camera's visibility (that one still dims the sky)
            self.sky.solar_occlusion = 'ring_eclipse_proxy'
        self.wx = WeatherSystem(self.sky)
        if self.red_giant is not None:
            self.red_giant.attach(self.sky)
        if self.ring is not None:
            self.ring.bind_weather(self.wx, self.sky)
        if self._weather0[0]:
            self.wx.set_weather(*self._weather0)
        self.cyc = None
        self.lights = None
        self.world_extra = None
        was, self._replaying = self._replaying, True
        try:
            for at, _seq, fn in self.recipe:
                if at is None:
                    fn()
        finally:
            self._replaying = was
        self.schedule = sorted((e for e in self.recipe if e[0] is not None), key=lambda e: (e[0], e[1]))

    # ---- objects ----
    def _make_sun_lamp(self):
        import bpy
        ld = bpy.data.lights.new('eido_sky_sun', 'SUN')
        ld.angle = math.radians(0.53)          # the real sun's diameter: shadow softness
        ob = bpy.data.objects.new('eido_sky_sun', ld)
        self.scene.collection.objects.link(ob)
        return ob

    # ---- the scene-facing surface ----
    @property
    def world(self):
        return self.world_key

    @property
    def label(self):
        return self.W['label']

    @property
    def planet_shine(self):
        return list(self.W['planetShine']) if self.W.get('planetShine') else None

    @property
    def internals(self):
        """Escape hatch for engine work only (sky_worlds.js _internals {sky, wx, band, celestialMod, wxAudio, moon}):
        sky, wx, band, celestial_mod (also as celestial), wx_audio (the attached weather system), moon."""
        return dict(sky=self.sky, wx=self.wx, band=self.ring, celestial_mod=self.red_giant, celestial=self.red_giant,
                    wx_audio=self.weather_fx, moon=self.moon)

    # ---- direction calls (immediate, or at media time `at` seconds) ----
    def _at(self, at, fn):
        self._seq += 1
        entry = (None if at is None else float(at), self._seq, fn)
        if not self._replaying:     # a call made by the script: part of the sky's direction, replayed by every bake
            self.recipe.append(entry)
        # (a call an on_frame callback makes while frames run belongs to that run only: never recorded)
        if at is None:
            fn()
        else:
            self.schedule.append(entry)
            self.schedule.sort(key=lambda e: (e[0], e[1]))
        return self

    def set_time(self, hours, at=None):
        def fn():
            self.cyc = None
            self.sky.set_time(((hours % 24) + 24) % 24)
        return self._at(at, fn)

    def day_cycle(self, start_hour=6.0, seconds=60.0, at=None):
        def fn():
            self.cyc = dict(start=start_hour, seconds=seconds, t0=None)
        return self._at(at, fn)

    def set_clouds(self, kind, shape=None, at=None):
        return self._at(at, lambda: self.sky.set_clouds(kind, shape))

    def transition_clouds(self, kind, seconds=2.5, at=None):
        return self._at(at, lambda: self.sky.transition_clouds(kind, seconds))

    def set_weather(self, name, k=1.0, at=None):
        return self._at(at, lambda: self.wx.set_weather(name, k))

    def transition_to(self, name, k=1.0, seconds=45.0, at=None):
        return self._at(at, lambda: self.wx.transition_to(name, k, seconds))

    def set_colors(self, colors, at=None):
        """Per-channel retints over the package's authored look: cloud, star (or sun), sky, fog, rain, and shield
        (the red giant only: a world without a shield ignores it, with a warning, as sky_worlds.js does)."""
        if colors.get('shield') is not None and not self.W.get('shield'):
            print("[sky_worlds] set_colors: '%s' has no shield, so a shield colour has nothing to apply to; ignored. "
                  'The shield belongs to the red giant package.' % self.world_key)

        def fn():
            self.sky.set_colors(dict(cloud=colors.get('cloud'), star=colors.get('star', colors.get('sun')),
                                     sky=colors.get('sky'), fog=colors.get('fog'),
                                     shield=colors.get('shield') if self.W.get('shield') else None))
            if colors.get('rain'):
                self.wx.set_colors(dict(rain=colors['rain']))
        return self._at(at, fn)

    def on_frame(self, fn):
        """fn(sky, t) runs every frame before the update: the WebGPU renderFrame(t) escape hatch."""
        self.callbacks.append(fn)
        return self

    def use_fog(self, density=0.0004, kind='exp2', near=1.0, far=1000.0):
        """Distance fog in the sky's keyed fog colour (three's FogExp2 or Fog); the scene owns the density."""
        self.fog = dict(density=density, kind=kind, near=near, far=far)
        return self

    def use_cloud_dome(self, radius=3072.0):
        """Clouds over distant geometry: WebGPU's cloud dome (3200 * 0.96 m), see cloud_dome.py. None turns it off."""
        self.dome_radius = None if radius is None else float(radius)
        return self

    def attach_cluster(self, cluster):
        """A CUSTOM celestial cluster (asteroid_moon.make_shattered_moon) in this sky: the scene places, scales and
        animates cluster.group; every bake lights it with the sky's true sun (its own uniforms keep sun_col, gain,
        fade), marches its accretion dust in the sky shader behind the fragments and composites the sky's clouds over
        it, as the shieldworld does for its own moon. The shieldworld already owns its cluster. Returns the sky."""
        if self.world_key == 'shieldworld':
            raise ValueError('attach_cluster: the shieldworld already owns its shattered moon; do not add a duplicate')
        cluster.placed = True
        self.moon = cluster
        self.moon_vals = None
        self._baker = None                   # the sky shader now compiles the cluster's dust (HAS_DUST)
        return self

    def wrap_scene(self):
        """The weather wraps the scene's materials for wetness and puddles: delegated to the weather system attached
        to this sky (eidoblend.weather.make_weather_system sets sky.weather_fx); without one there is nothing to
        wrap. Call it again after adding geometry. Returns the sky."""
        fx = getattr(self, 'weather_fx', None)
        if fx is not None:
            fx.wrap_scene()
        return self

    def enable_reflections(self, *_args, **_kw):
        """WebGPU's cloud-reflect hook: EEVEE ray-traces reflections of the world and the sky elements natively, so
        there is nothing to enable. Returns the sky."""
        return self

    def audio_timeline(self, **kw):
        """The weather audio timeline (rain bed, wind bed, thunder events) of the attached weather system, or None
        without one or with make_sky(audio=False), as the JS returns null without an audio system."""
        fx = getattr(self, 'weather_fx', None)
        if fx is None or not self.audio_on:
            return None
        return fx.audio_timeline(**kw)

    @property
    def audio(self):
        """The weather-audio carrier (the attached weather system, which records the timeline), or None."""
        return getattr(self, 'weather_fx', None) if self.audio_on else None

    # ---- the true sun / moon directions (Blender world space) ----
    @property
    def sun_dir(self):
        return P.three_to_blender(self.sky.sun_dir)

    @property
    def moon_dir(self):
        return P.three_to_blender(self.sky.moon_dir)

    # ---- one frame of state, in the JS facade's order ----
    def update(self, t):
        while self.schedule and self.schedule[0][0] <= t + 1e-9:
            _at, _seq, fn = self.schedule.pop(0)
            fn()
        was, self._replaying = self._replaying, True
        try:
            for cb in self.callbacks:
                cb(self, t)
        finally:
            self._replaying = was
        if self.cyc:
            c = self.cyc
            if c['t0'] is None:
                c['t0'] = t
            self.sky.set_time((c['start'] + (t - c['t0']) * (24 / c['seconds'])) % 24)
        hours = self.sky.state['hours']
        U = self.sky.U
        # the shattered moon rides its own orbit on the sky's clock; the sky's moon follows it (Eanpa)
        if self.moon is not None:
            th = (((hours - 22.3) + 24) % 24) / 6.2 * math.pi
            p3 = (math.cos(th) * 34000.0, math.sin(th) * 22000.0 + 2000.0, -12000.0)
            self.sky.set_moon_direction(p3)
        # the band eclipses the sun (Eanpa ringsky.js: the visibility at the camera dims the sun and the sky)
        if self.ring is not None:
            cam = self.camera.matrix_world.translation
            solar = self.ring.eclipse_k(self.sky.sun_dir, P.blender_to_three((cam.x, cam.y, cam.z)))
            U['solarVisibility'] = solar
            U['solarSkyVisibility'] = 0.16 + 0.84 * solar
        self.sky.update(t)
        self.wx.update(t)
        if self.ring is not None:
            self.ring_vals = self.ring.update(t)
        if self.red_giant is not None:
            self.red_giant.update(t)
        L = self.sky.apply_to_lights()
        L['sun_intensity'] *= self.wx.sun_dim()
        L['hemi_dim'] = self.wx.hemi_dim()
        # Eanpa applyLightDim: fog is scattered skylight, so the weather's skylight dim greys it too (a sealed storm
        # otherwise leaves the bright daytime horizon in the fog, a glowing band on distant terrain)
        L['fog_color'] = tuple(c * L['hemi_dim'] for c in L['fog_color'])
        self.world_extra = None
        if self.world_key == 'shieldworld':
            self._shieldworld_night(t, hours, L)
        elif self.moon is not None:
            # a custom cluster (attach_cluster): placed by the scene, lit by the true sun, its dust in the sky shader
            mv = self.moon.update(t, sky_sun_dir=self.sky.sun_dir)
            U.update(mv['U'])
            self.moon_vals = mv
        self.lights = L
        return L

    def _shieldworld_night(self, t, hours, L):
        """Eanpa src/shieldworld.js's frame block: the night is lit by the shield's cyan glow and, when the cluster is
        up, the moon's amber; the lattice's glow washes the milky way and lifts the sky floor."""
        U = self.sky.U
        sun_y = self.sky.sun_dir[1]
        night_k = max(0.0, min(1.0, (0.06 - sun_y) / 0.24))
        pal = self.sky.state['palette']
        U['starFade'] = pal.get('star', 0.0) * (1 - 0.85 * night_k)
        U['skyGlow'] = tuple(c * 0.014 * night_k for c in (0.29, 0.73, 1.0))
        mv = self.moon.update(t, hours, self.sky.sun_dir, night_k, MOON_KEY) if self.moon is not None else None
        if mv is not None:
            U.update(mv['U'])
        moon_up_k = max(0.0, min(1.0, (mv['moon_up'] if mv else 0.0) / 16000.0)) * night_k
        # the hemisphere light: its colour lerps toward cyan, its strength floors at 0.2 at night (then hemiDim)
        hemi_i = max((0.25 + pal['int'] * 0.25 + night_k * 0.06) * U['solarSkyVisibility'], 0.20 * night_k)
        hemi_i *= L['hemi_dim']
        lerp = night_k * 0.8
        # a three.js ambient / hemisphere light of colour c and intensity I lights like a sky of radiance c I / pi
        add = [HEMI_CYAN[i] * lerp * hemi_i / math.pi
               + NIGHT_AMBIENT[i] * 0.16 * night_k / math.pi
               + MOON_AMBIENT[i] * 0.22 * moon_up_k / math.pi for i in range(3)]
        tint = (1.0 - lerp,) * 3
        self.moon_vals = mv
        self.world_extra = dict(tint=tint, add=tuple(add), night_k=night_k, moon_up_k=moon_up_k)

    def apply_to_lights(self):
        """The frame's lamp values (update() computes them every frame: lighting is not opt-in)."""
        return self.lights

    # ---- baking ----
    def baker(self):
        if self._baker is None:
            from .bake.baker import SkyBaker
            o = self.sky.opts
            # Eanpa's ice-trail atlas when the repo carries it, else the in-repo analytic mares'-tail plumes
            cirrus = self.cirrus_atlas or os.path.join(ASSETS, 'cirrus_ice_trails.png')
            defines, celestial, dust, ring_map, ring_mask = {}, '', '', None, None
            if self.ring is not None:
                defines.update(self.ring_k)
                c = self.ring.ring_center_three()
                defines.update(HAS_RING_ENV=1, RING_CENTER_Y=float(c[1]), RING_BAND_R=5000.0,
                               RING_HALF_W=483.0, RING_REPEAT=float(self.ring.info['repeat']),
                               RING_PHASE=float(self.ring.info['phase']))
                ring_map, ring_mask = self.ring.map_path, self.ring.info['mask_path']
            if self.red_giant is not None:
                defines.update(self.red_giant.shader_defines())
                celestial = self.red_giant.celestial_glsl()
            if self.moon is not None:
                defines['HAS_DUST'] = 1
                dust = self.moon.dust_glsl()
            moonmap = self.W.get('moonmap')
            self._baker = SkyBaker(stars=os.path.join(ASSETS, self.W['starmap']),
                                   moon=os.path.join(ASSETS, moonmap) if moonmap else None,
                                   cirrus=cirrus,
                                   n_march=self.q['n_march'], n_light=self.q['n_light'], m_pass=self.q['m_pass'],
                                   phase_soften=o.get('cloudPhaseSoften', 0.0),
                                   ms_floor=o.get('cloudMultiScatterFloor', 0.008), defines=defines,
                                   celestial=celestial, dust=dust, ring_map=ring_map, ring_mask=ring_mask)
        return self._baker

    def frame_states(self, frame_start=None, frame_end=None):
        """Yield (frame, t, lights) for each frame of the range, with the scene on that frame: what a bake renders.

        Every call starts from the same state (_reset_state) and replays the direction calls from the scene's
        first frame, so a re-bake, or a bake of part of the range, gives exactly the frames of a full bake.
        Frames before frame_start run as state only (the scene is moved there only when on_frame callbacks
        might read it). Leaves the sky in the state of the last frame yielded.
        """
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = sc.render.fps / sc.render.fps_base
        self._reset_state()
        before = (sc.frame_current, sc.frame_subframe)
        try:
            for f in range(min(fs, sc.frame_start), fe + 1):
                t = (f - sc.frame_start) / fps
                if f >= fs or self.callbacks:
                    sc.frame_set(f)
                L = self.update(t)
                if f >= fs:
                    yield f, t, L
        finally:
            sc.frame_set(before[0], subframe=before[1])

    def _layered(self):
        """Whether the bake splits the camera rays into layers (sky elements composite them; a dome draws them)."""
        return self.ring is not None or self.moon is not None or self.dome_radius is not None

    def bake(self, frame_start=None, frame_end=None, overscan=0.08, layer_scale=None, plate_scale=1.0, log=print):
        """Replay the direction calls frame by frame, render the sky layers, key the world, the lamps and the
        world's geometry. On the ringworld, render the band's plate per frame into the camera layer: plate_scale is
        its pixel density against the frame's (1: the frame's own, so the band's textures take the mip levels a
        direct render gives them; above 1 is crisper, but sharpens the night water's glints)."""
        import time
        import bpy
        from mathutils import Vector
        from . import world_nodes as WN
        from .bake.baker import write_exr
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        ls = self.layer_scale if layer_scale is None else float(layer_scale)
        pct = sc.render.resolution_percentage / 100.0
        rw, rh = int(sc.render.resolution_x * pct), int(sc.render.resolution_y * pct)
        lw = int(math.ceil(rw * (1 + 2 * overscan) * ls))
        lh = int(math.ceil(rh * (1 + 2 * overscan) * ls))
        ew, eh = self.q['env']
        bk = self.baker()
        os.makedirs(self.cache_dir, exist_ok=True)
        pat = {k: os.path.join(self.cache_dir, 'sky_%s_%%04d.exr' % k)
               for k in ('cam', 'back', 'cloud', 'shield', 'env', 'base')}
        pat['plate'] = os.path.join(self.cache_dir, 'ring_plate_%04d.exr')
        layered = self._layered()
        dome = self.dome_radius is not None
        want = ['back' if dome else 'cam']
        if layered:
            want.append('cloud')
            if self.red_giant is not None and self.red_giant.has_shield:
                want.append('shield')
        plate = self._plate_ready()
        if plate:
            want.append('base')          # the sky with no band: the ring's plate composites over it
        frames = []
        t_start = time.time()
        for f, t, L in self.frame_states(fs, fe):
            mw = self.camera.matrix_world
            right = Vector(mw.col[0][:3]).normalized()
            up = Vector(mw.col[1][:3]).normalized()
            back = Vector(mw.col[2][:3]).normalized()
            tx, ty = _cam_window(self.camera, sc)
            tx, ty = tx * (1 + 2 * overscan), ty * (1 + 2 * overscan)
            loc = mw.translation
            org = P.blender_to_three((loc.x, loc.y, loc.z))
            t0 = time.time()
            basis = (tuple(right), tuple(up), tuple(back))
            if layered:
                layers = bk.camera_layers(self.sky.U, basis, (tx, ty), org, lw, lh)
            else:
                layers = dict(cam=bk.camera_layer(self.sky.U, basis, (tx, ty), org, lw, lh))
            t1 = time.time()
            env_img = bk.environment(self.sky.U, ew, eh, origin_three=(org[0], max(2.0, org[1]), org[2]))
            t2 = time.time()
            for k in want:
                write_exr(pat[k] % f, layers['back' if k == 'base' else k])
            write_exr(pat['env'] % f, env_img)
            fr = dict(frame=f, t=t, basis=(tuple(right), tuple(up), tuple(-back)), tan=(tx, ty), lights=L,
                      U={k: v for k, v in self.sky.U.items()}, shadow_org=org, weather=self.wx.state['name'],
                      extra=self.world_extra, cam_matrix=[list(row) for row in mw])
            if self.ring is not None:
                fr['ring'] = dict(self.ring_vals)
            if self.moon is not None:
                fr['moon'] = self.moon_vals
            frames.append(fr)
            log('[sky] frame %d t=%.2fs  camera layer%s %dx%d %.2fs  environment %dx%d %.2fs'
                % (f, t, 's ' + '+'.join(want) if layered else '', lw, lh, t1 - t0, ew, eh, t2 - t1))
        # (frame_states has put the scene back on the frame it was on)
        for k in want + ['env']:
            WN.hold_before_first(pat[k], fs)
        world = sc.world or bpy.data.worlds.new('eido_sky_world')
        sc.world = world
        if world.animation_data:
            world.animation_data_clear()
        if world.node_tree and world.node_tree.animation_data:
            world.node_tree.animation_data_clear()
        from .sky_view import view_group, overlay_group
        vg = view_group()
        if vg.animation_data:
            vg.animation_data_clear()
        n = fe - fs + 1
        handles = WN.build_world(world, pat[want[0]] % fs, pat['env'] % fs, fs, n)
        self._key_sun(frames)
        for fr in frames:
            fill = self.ambient * fr['lights']['hemi_dim']        # diffuse only: glossy rays keep the sky
            ex = fr.get('extra') or {}
            WN.key_world(handles, fr['frame'], fr['basis'], fr['tan'], fill, tint=ex.get('tint'),
                         ambient_add=ex.get('add'))
        WN.constant_interpolation(world.node_tree)
        WN.constant_interpolation(vg)
        if layered:
            cloud_img = WN._seq_image(pat['cloud'] % fs, fs, n, 'eido_sky_cloud_layer')
            shield_img = (WN._seq_image(pat['shield'] % fs, fs, n, 'eido_sky_shield_layer')
                          if 'shield' in want else None)
            overlay_group(cloud_img, shield_img, fs, n, dome_radius=self.dome_radius)
            if self.ring is not None:
                self._key_ring(frames)
            if self.moon is not None:
                self._key_moon(frames)
            if dome:
                from .cloud_dome import build_cloud_dome
                build_cloud_dome(sc, self.camera, cloud_img, fs, n, radius=self.dome_radius)
        if self.use_shadows:
            from . import cloud_shadows
            cloud_shadows.bake_and_key(self, frames, ground_z=self.shadow_ground, caster_height=self.shadow_height,
                                       log=log)
        if plate:
            # every key the band reads is in place (the world, the ring's values and lamps, the band sun's cloud-shadow
            # twin): render its plate per frame and composite it into the layer the world shows
            ps = max(1.0, float(plate_scale))       # against the frame (with the overscan), whatever the layer scale
            self._plate_job = dict(size=(int(math.ceil(rw * (1 + 2 * overscan) * ps)),
                                         int(math.ceil(rh * (1 + 2 * overscan) * ps))),
                                   pat=pat, target=want[0],
                                   frames=[(fr['frame'], fr['cam_matrix'], fr['tan']) for fr in frames])
            self._render_plates(log=log)
        if self.fog:
            from . import fog as FOG
            FOG.key_fog(FOG.setup_fog(sc, **self.fog), frames)
        self._write_state(frames)
        log('[sky] baked %d frames in %.1fs' % (len(frames), time.time() - t_start))
        return frames

    def _key_ring(self, frames):
        r = self.ring
        for tree in (r.keys_tree,):
            if tree.animation_data:
                tree.animation_data_clear()
        for lamp in (r.band_sun, r.band_shine):
            if lamp is not None:
                for idd in (lamp, lamp.data):
                    if idd.animation_data:
                        idd.animation_data_clear()
        for fr in frames:
            r.key(fr['frame'], fr['ring'])
        r.finish_keys()

    def _key_moon(self, frames):
        m = self.moon
        m.clear_keys()                       # a placed cluster's group keeps the scene's own animation
        for fr in frames:
            m.key(fr['frame'], fr['moon'])
        m.finish_keys()

    # ---- the ringworld's plate: the band behind every local object ----
    def _plate_ready(self):
        return self.ring is not None and getattr(self.ring, 'plate_scene', None) is not None

    def _plate_settings(self, plate, w, h):
        """The plate renders as the main scene does (samples, shadows, ray tracing, filter), at (w, h), with a
        transparent film and the main scene's world, which lights the band."""
        sc = self.scene
        plate.world = sc.world
        plate.render.fps, plate.render.fps_base = sc.render.fps, sc.render.fps_base
        plate.frame_start, plate.frame_end = sc.frame_start, sc.frame_end
        plate.render.resolution_x, plate.render.resolution_y = w, h
        # the main render filters the band again when it samples the world, so the plate keeps a one-pixel filter of
        # its own (filtered twice at full width, the sun's glints on the night water spread over more pixels and read
        # brighter through the view transform)
        plate.render.filter_size = min(sc.render.filter_size, 1.0)
        for attr in ('taa_render_samples', 'use_shadows', 'shadow_ray_count', 'shadow_step_count', 'use_raytracing',
                     'use_fast_gi', 'fast_gi_method', 'fast_gi_resolution', 'fast_gi_step_count', 'fast_gi_distance',
                     'horizon_quality', 'horizon_thickness', 'horizon_bias', 'horizon_resolution',
                     'clamp_surface_direct', 'clamp_surface_indirect', 'light_threshold', 'shadow_resolution_scale'):
            if hasattr(sc.eevee, attr) and hasattr(plate.eevee, attr):
                try:
                    setattr(plate.eevee, attr, getattr(sc.eevee, attr))
                except (AttributeError, TypeError, ValueError):
                    pass
        src, dst = getattr(sc.eevee, 'ray_tracing_options', None), getattr(plate.eevee, 'ray_tracing_options', None)
        if src is not None and dst is not None:
            for p in src.bl_rna.properties:
                if not p.is_readonly and p.identifier != 'rna_type':
                    try:
                        setattr(dst, p.identifier, getattr(src, p.identifier))
                    except (AttributeError, TypeError, ValueError):
                        pass
        # the band sun's kilometre-scale shadows need the pool the ring asked of the main scene
        plate.eevee.shadow_pool_size = max(plate.eevee.shadow_pool_size, sc.eevee.shadow_pool_size, '1024', key=int)

    def _render_plates(self, log=print):
        """Render the ring's plate for every frame of the last bake and composite it into the layer the world shows:
        the clouds over the band over the sky, C + (1 - a)(P + (1 - Pa) B), from the bake's own cloud layer and the
        sky it keeps without the band (sky_base). Under a cloud dome the world shows the sky behind the clouds, so the
        plate goes into that layer, P + (1 - Pa) B, and the dome draws the clouds over it. The plate covers the camera
        layer's window at bake(plate_scale=) times the frame's pixel density; the cloud and sky layers, soft by
        nature, are resampled to it when it is finer."""
        import time
        import bpy
        from mathutils import Matrix
        from . import world_nodes as WN
        from .bake.baker import write_exr
        job = self._plate_job
        r = self.ring
        plate, pcam = r.plate_scene, r.plate_camera
        pw, ph = job['size']
        self._plate_settings(plate, pw, ph)
        pat, target = job['pat'], job['target']
        sc = self.scene
        before = (sc.frame_current, sc.frame_subframe)
        t0 = time.time()
        for f, mw, tan in job['frames']:
            tx, ty = tan
            pcam.matrix_world = Matrix(mw).normalized()
            pcam.data.angle = 2.0 * math.atan(tx)
            # the layer's grid spans [-tx, tx] x [-ty, ty]: the pixel aspect gives the plate exactly that window
            ratio = (ty * pw) / (tx * ph)
            plate.render.pixel_aspect_x, plate.render.pixel_aspect_y = (1.0, ratio) if ratio >= 1.0 else (1.0 / ratio,
                                                                                                        1.0)
            # both scenes on the frame: the image sequences the band reads through the shared world (the sky's
            # environment) and the band sun's cloud-shadow twin follow the main scene's frame, not the plate's
            sc.frame_set(f)
            plate.frame_set(f)
            plate.render.filepath = pat['plate'] % f
            bpy.ops.render.render(write_still=True, scene=plate.name)
            pl = _read_exr(pat['plate'] % f)
            base = _resize_bilinear(_read_exr(pat['base'] % f), ph, pw)
            behind = pl[..., :3] + (1.0 - pl[..., 3:4]) * base[..., :3]
            out = np.empty((ph, pw, 4), np.float32)
            if target == 'back':
                out[..., :3] = behind
                out[..., 3] = 1.0
            else:
                cl = _resize_bilinear(_read_exr(pat['cloud'] % f), ph, pw)
                out[..., :3] = cl[..., :3] + (1.0 - cl[..., 3:4]) * behind
                out[..., 3] = cl[..., 3]
            write_exr(pat[target] % f, out)
            os.remove(pat['plate'] % f)
        sc.frame_set(before[0], subframe=before[1])
        WN.hold_before_first(pat[target], job['frames'][0][0])
        img = bpy.data.images.get('eido_sky_camera_layer')
        if img is not None:
            img.reload()
        log('[sky] ring plates: %d frames at %dx%d in %.1fs' % (len(job['frames']), pw, ph, time.time() - t0))

    def bake_plates(self, log=print):
        """Render the ringworld's plates again for the frames of the last bake, without baking the sky again: after
        changing the band's materials or the ring's options, which reach the frame only through the plate. Returns
        the sky."""
        if not self._plate_ready() or not getattr(self, '_plate_job', None):
            raise ValueError('bake_plates: bake() the ringworld first')
        self._render_plates(log=log)
        return self

    def bake_env(self, width=None, height=None):
        """bakeEnv: the environment of the sky's current state (the band traced in, on the ringworld) as a float
        image; bake() writes one per frame for the world, so a scene rarely needs this."""
        ew, eh = self.q['env']
        cam = self.camera.matrix_world.translation
        org = P.blender_to_three((cam.x, cam.y, cam.z))
        return self.baker().environment(self.sky.U, width or ew, height or eh,
                                        origin_three=(org[0], max(2.0, org[1]), org[2]))

    def _key_sun(self, frames):
        from mathutils import Vector
        ob = self.sun
        ob.rotation_mode = 'QUATERNION'
        ld = ob.data
        for fr in frames:
            L = fr['lights']
            d = Vector(P.three_to_blender(L['key_dir'])).normalized()
            ob.rotation_quaternion = d.to_track_quat('Z', 'Y')
            ob.keyframe_insert('rotation_quaternion', frame=fr['frame'])
            ld.energy = L['sun_intensity']
            ld.color = L['sun_color']
            ld.keyframe_insert('energy', frame=fr['frame'])
            ld.keyframe_insert('color', frame=fr['frame'])
        for idd in (ob, ld):
            ad = idd.animation_data
            if ad and ad.action:
                from .world_nodes import _fcurves
                for fc in _fcurves(ad):
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'

    def _write_state(self, frames):
        rows = []
        for fr in frames:
            L = fr['lights']
            row = dict(frame=fr['frame'], t=fr['t'], sun_color=L['sun_color'], sun_intensity=L['sun_intensity'],
                       key_dir_blender=P.three_to_blender(L['key_dir']), hemi_dim=L['hemi_dim'],
                       fog_color=L['fog_color'], weather=fr['weather'],
                       uniforms={k: v for k, v in fr['U'].items()})
            if fr.get('extra'):
                row['world_extra'] = fr['extra']
            if fr.get('ring'):
                row['ring'] = fr['ring']
            if fr.get('moon'):
                mv = fr['moon']
                row['moon'] = dict(position3=mv['position3'], visibility=mv['visibility'], gain=mv['gain'])
            rows.append(row)
        with open(os.path.join(self.cache_dir, 'sky_state.json'), 'w', encoding='utf-8') as f:
            json.dump(rows, f, indent=1, default=lambda o: list(o) if hasattr(o, '__iter__') else str(o))


def make_sky(scene=None, camera=None, world='earth', hours=12.0, clouds='cumulus', weather=None, weather_k=1.0,
             sun=None, cache_dir=None, quality='film', ambient=DEFAULT_AMBIENT, shadows=True, shadow_height=None,
             shadow_ground=0.0, cloud_dome=None, audio=True, **opts):
    """Select a whole sky world: 'earth' | 'ringworld' | 'shieldworld' (SKY_WORLDS). `weather` (a WEATHER state)
    overrides `clouds`; None keeps the cloud preset.

    hours 0-24, clouds clear|cumulus|stratus|cirrus, weather clear|fair|sunshower|overcast|rain|storm|cyclone|
    darkstorm. `sun` reuses a sun lamp object (else one is created). `cache_dir` holds the per-frame sky
    layers (default //sky_cache beside the saved .blend; an unsaved .blend must pass one). `quality` 'film'
    (8 march passes) or 'draft' (3). `ambient` scales the world's diffuse light against the visible sky (see
    DEFAULT_AMBIENT). `shadow_height` puts the cloud-shadow caster that many metres above `shadow_ground`
    (None: just under the lowest cloud base of the bake, so everything below the clouds receives). `cloud_dome`
    True (3072 m, WebGPU's) or a radius in metres draws the clouds over geometry beyond it (cloud_dome.py).
    `audio` (makeSky's flag) keeps the weather-audio timeline on: audio_timeline() and `audio` read the weather
    system attached to this sky (eidoblend.weather), and return None with audio=False.
    The world's look-dev (assets, bodies, band placement) is not a parameter: it belongs to the world. Engine
    options pass through: the SkySystem names, `ring={...}` (make_ringworld options), `redGiant={...}`.
    makeSky's `renderer` and `hemi` have no counterpart: the bake renders in Blender's own GPU module, and the EEVEE
    world is the hemisphere light (bake() keys its diffuse fill).
    """
    import bpy
    scene = scene or bpy.context.scene
    opts['audio'] = audio
    return Sky(scene, camera, world, hours, clouds, weather, weather_k, sun, cache_dir, quality, ambient, shadows,
               opts, shadow_height=shadow_height, shadow_ground=shadow_ground, cloud_dome=cloud_dome)


__all__ = ['make_sky', 'SKY_WORLDS', 'WORLDS', 'WEATHER', 'Sky']
