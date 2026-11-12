"""RED GIANT + PLANETARY SHIELD: the shieldworld's sky-element system (Eanpa Engine engine/redgiant.js).

The star is a procedural animated red giant that rides the sky's sun through the day cycle; the shield is a
hex-cell radiation lattice above the clouds, where radiation hits arrive as expanding rings of whole-hexagon
activations, more and harder while a flare peaks. As in the JS, the system is three things:
  - the celestial body, shaded inside the sky shader (bake/celestial.py generates it from these flare slots), so
    the visible sky and the environment get the star from one function;
  - the shield layer, composited between the sky and the clouds (sky.glsl shieldLayer, HAS_SHIELD);
  - this JS-side state, updated per frame: the star's basis, the flare schedule and the impact slots.

    rg = make_red_giant(opts={'shield': True})      # before the sky: its palette tint goes into the sky's options
    rg.attach(sky)                                  # sky: a SkySystem; registers rg for set_colors(shield/star)
    rg.update(t)                                    # per frame, after sky.update(t)

make_sky(world='shieldworld') builds and drives its own; make_sky(celestial=make_red_giant({'shield': False})) puts
one in the Earth or ringworld sky, where it is the sun.

Options (the JS names): angularRadius (rad, 0.28 = a 32 deg disc), granScale (52), plasmaSpeed (0.5), shield (True),
hexScale (22), shieldRadius (21000), flares (slot list), flareBoost (0; 1 forces eruption 0 to its peak),
starColor ([1, 1, 1]), shieldColor ([0.38, 0.95, 1.3], linear HDR), paletteTint. No bpy here.
"""
import math

from . import palette as P

# Eanpa's slots: five limb prominences plus three slow front events (paired sunspots with surface anchors)
FLARES = (
    dict(th=0.7, rate=0.055, ph0=0.13),
    dict(th=2.3, rate=0.075, ph0=0.55),
    dict(th=3.5, rate=0.048, ph0=0.82),
    dict(th=4.6, rate=0.068, ph0=0.30),
    dict(th=5.7, rate=0.060, ph0=0.68),
    dict(th=1.0, rate=0.014, ph0=0.32, center=(0.31, 0.27)),
    dict(th=2.1, rate=0.019, ph0=0.66, center=(-0.38, 0.08)),
    dict(th=4.8, rate=0.012, ph0=0.10, center=(0.08, -0.47)),
)

# warm giant illumination (Eanpa): a cool photosphere keeps green/blue energy, so materials stay readable under
# the red-orange sky instead of collapsing into one red channel
PALETTE_TINT = dict(zen=(0.72, 0.32, 0.20), hor=(1.00, 0.42, 0.22), sun=(1.00, 0.62, 0.35))
SHIELD_COLOR = (0.38, 0.95, 1.3)


def _jsmod1(x):
    """JS (x % 1 + 1) % 1."""
    return math.fmod(math.fmod(x, 1.0) + 1.0, 1.0)


def flare_env(f, t):
    """The flare envelope of slot f at time t (0..1), the JS flareEnv: the same deterministic schedule the shader's
    prominences follow (the shader decides `act` in float32, as WebGPU's did)."""
    ph = math.fmod(t * f['rate'] + f['ph0'], 1.0)
    cyc = math.floor(t * f['rate'] + f['ph0'])
    act = 1.0 if _jsmod1(math.sin(cyc * 12.9898 + f['th'] * 78.233) * 43758.5453) > 0.45 else 0.0
    return math.sin(math.pi * min(ph * 1.3, 1.0)) ** 2 * act


class RedGiant:
    def __init__(self, opts=None):
        o = dict(opts or {})
        self.opts = o
        self.angular_radius = float(o.get('angularRadius', 0.28))
        self.gran_scale = float(o.get('granScale', 52))
        self.plasma_speed = float(o.get('plasmaSpeed', 0.5))
        # opts.flares ?? FLARES: an explicit empty list is honoured (no prominences, no sunspot events), as in the JS
        self.flares = FLARES if o.get('flares') is None else tuple(o['flares'])
        self.hex_scale = float(o.get('hexScale', 22))
        self.shield_radius = float(o.get('shieldRadius', 21000))
        self.has_shield = o.get('shield', True) is not False
        self.palette_tint = o.get('paletteTint') or PALETTE_TINT
        self.star_tint = tuple(float(c) for c in (o.get('starColor') or (1, 1, 1)))
        self.shield_color = tuple(float(c) for c in (o.get('shieldColor') or SHIELD_COLOR))
        self.flare_boost = float(o.get('flareBoost', 0))
        self.sky = None
        self.star_dir = P.norm3((0, 0.42, -0.86))
        self.star_right = (1.0, 0.0, 0.0)
        self.star_up = (0.0, 1.0, 0.0)
        self.burst_k = 0.0
        self.impacts = [(0.0, 0.0, -99.0, 0.0)] * 5      # (plane x, plane y, birth time, amplitude)
        self.t = 0.0

    # ---- what the sky shader compiles (bake/celestial.py) ----
    def celestial_glsl(self):
        from .bake.celestial import red_giant_glsl
        return red_giant_glsl(self.flares, self.angular_radius, self.gran_scale, self.plasma_speed)

    def shader_defines(self):
        d = dict(HAS_CELESTIAL=1)
        if self.has_shield:
            d.update(HAS_SHIELD=1, HEXSCALE=float(self.hex_scale), SHIELD_R=float(self.shield_radius))
        return d

    def flare_env(self, f, t):
        return flare_env(f, t)

    # ---- live recolours ----
    def set_shield_color(self, rgb):
        """Recolour the hex lattice: [r, g, b] in linear HDR (above 1 is intentional, it is emissive)."""
        if self.has_shield and rgb is not None and len(rgb) == 3:
            self.shield_color = tuple(float(c) for c in rgb)
            self._write()
        return self

    def set_star_color(self, rgb):
        """Recolour the star: a multiplier over the authored ember ramp ([1, 1, 1] is the dialled-in giant)."""
        if rgb is not None and len(rgb) == 3:
            self.star_tint = tuple(float(c) for c in rgb)
            self._write()
        return self

    def attach(self, sky):
        """Register with the sky (its set_colors reaches the shield and the star through this)."""
        self.sky = sky
        sky.celestial_module = self
        self._write()
        return self

    # ---- per frame ----
    def update(self, t):
        self.t = float(t)
        sky = self.sky
        if sky is not None:
            # the giant IS the sun: ride the sky's sun, and keep the default disc and glow lobes off
            sd = P.norm3(sky.sun_dir)
            self.star_dir = sd
            up0 = (1.0, 0.0, 0.0) if abs(sd[1]) > 0.93 else (0.0, 1.0, 0.0)
            self.star_right = P.norm3(P.cross3(up0, sd))
            self.star_up = P.norm3(P.cross3(sd, self.star_right))
            sky.U['sunDiscI'] = 0.0
            sky.U['sunGlowI'] = 0.0
        env = 0.0
        for f in self.flares:
            env = max(env, flare_env(f, t))
        self.burst_k = env
        # radiation hits: 5 deterministic slots clustered toward the star's gnomonic projection on the shield plane
        sdd = self.star_dir
        hs = self.hex_scale
        gy = max(sdd[1], 0.15)
        sx, sz = sdd[0] / gy * hs, sdd[2] / gy * hs
        day_k = 0.1 + 0.9 * min(1.0, max(0.0, (sdd[1] + 0.05) / 0.25))

        def h1(a, b):
            v = math.sin(a * 127.1 + b * 311.7) * 43758.5453
            return v - math.floor(v)

        imp = []
        for i in range(5):
            per = 2.8 + i * 1.2
            tin = t / per + i * 0.37
            cyc = math.floor(tin)
            birth = (cyc - i * 0.37) * per
            env_b = max((flare_env(f, birth) for f in self.flares), default=0.0)
            ang = h1(cyc, i * 7 + 1) * math.pi * 2
            rad = (0.12 + h1(cyc, i * 7 + 2) * 0.55) * hs
            on = 1.0 if h1(cyc, i * 7 + 3) > (0.45 - env_b * 0.35) else 0.0
            near_k = 1 - 0.45 * (rad / (0.67 * hs))
            amp = on * (0.35 + 0.65 * h1(cyc, i * 7 + 4)) * (0.55 + 1.6 * env_b) * near_k * day_k
            imp.append((sx + math.cos(ang) * rad, sz + math.sin(ang) * rad, birth, amp))
        self.impacts = imp
        self._write()
        return self

    def _write(self):
        sky = self.sky
        if sky is None:
            return
        U = sky.U
        U['starDir'] = tuple(self.star_dir)
        U['starRight'] = tuple(self.star_right)
        U['starUp'] = tuple(self.star_up)
        U['starT'] = self.t
        U['flareBoost'] = self.flare_boost
        U['starTint'] = tuple(self.star_tint)
        U['shieldColorU'] = tuple(self.shield_color)
        U['impacts'] = [tuple(v) for v in self.impacts]

    @property
    def uniforms(self):
        return dict(starDir=self.star_dir, starT=self.t, burstK=self.burst_k, impacts=list(self.impacts))


def make_red_giant(opts=None):
    """makeRedGiant({opts}): the system; pass .palette_tint into the sky's options, then attach(sky)."""
    return RedGiant(opts)
