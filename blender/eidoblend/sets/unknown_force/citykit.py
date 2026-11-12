"""eidoblend.sets.unknown_force.citykit: the shared kit behind UNKNOWN FORCE's exterior world (city.py + hole.py),
the Blender 5.2 EEVEE edition of eidoverse/sets/unknown_force/citykit.js.

One world frame for both sets. The singer's mark (the bottom of THE HOLE) is the origin; the city's streets are
STREET_Y = 12 m above it. Inside this kit the layout code works in three.js's axes (+Y up, she faces +Z), so every
number ports as it was; a point is converted once, when a mesh or an object is made: three (x, y, z) -> Blender
(x, -z, y). Cameras, focal points and object transforms come out in Blender axes. Everything is seeded (mulberry32,
bit for bit the engine's), merged or instanced, and keyed: a saved .blend plays and renders any frame on its own.

    from eidoblend.sets.unknown_force import citykit as KIT
    K = KIT.make_kit()                        # the five CC0 sets, noise, the night the glass reflects, uniforms, fog
    K.U['power'] = 0.6                        # the outro: lights go out one by one below their own threshold
    K.U.key('power', frame=7400)              # a LINEAR key on the uniforms node group
    KIT.make_light_map(K, [draw])             # draw(ctx, to_px, s): KIT.lm_pool(ctx, to_px, s, x, z, r, '#ff8a3d')
    mat = KIT.facade_material(K, 'concrete')  # procedural windows, wet streaks, floods, crowns, Crali's light

What the WebGPU edition did, and where it went:
  TSL materials        shader node trees written by NB (below), an expression layer that writes TSL-style maths as
                       nodes (+ - * / mix smoothstep step fract floor hash12 ...). fwidth has no shader node: on the
                       facades it is computed as the GPU measured it on a plane (pixel_steps: where the next pixel's
                       ray meets the face, from the camera's axes, the depth and its pixel angle `pix`, a driver on
                       the active scene camera); the lane paint and the LED grids use the view distance over the
                       foreshortening. hash12 is the hash the film rendered with (NB.hash12).
  uniforms (U.*)       one node group, `uf_city_U`, of keyed Value nodes every material reads; `K.U` sets and keys them,
                       Geometry Nodes read them through drivers.
  fogNode              the haze and the cloud deck are the node group `uf_fog` (factor, colour) mixed into every
                       material, exactly as three's fog mixed the fragment's colour; additive materials fade by 1 - f.
  canvas art           canvas-2D on numpy + Pillow (interiors_lib.Context2D, with the canvas shadows and roundRect
                       this kit's neon needs, in CityContext2D); the result is packed into the .blend.
  light map            a numpy painter for lm_pool's soft additive pools, stored as the 8-bit sRGB canvas was, with
                       its blurred levels (the explicit mip levels of lmSample) as smaller images.
  vertex shaders       rain, traffic (and the hole's cables) are Geometry Nodes evaluated per frame from the keyed
                       time and the scene's active camera.
  sky dome             the World: the dome's colours for camera rays; for lighting, the hemisphere light and the
                       night environment (envNode) as world radiance.
  MRT metalrough (SSR) the reflectivity the engine's SSR read becomes the Principled IOR (F0 = reflectivity) under
                       EEVEE's ray-traced reflections.

Canvas images are stored the right way up; the canvas-space UV maths of the engine (v down from the canvas top) is
converted once where it is sampled.
"""
from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

import numpy as np

from ... import common

try:                                   # the layout and camera maths run without Blender (parity tests)
    import bpy
except ImportError:                    # pragma: no cover
    bpy = None

# ------------------------------------------------------------------------------------------------ layout constants
STREET_Y = 12.0                        # street level above the hole floor (the well's depth)
HOLE = {
    'floor_r': 14.0,                   # the flat floor she stands on (r <= 14)
    'steps': 4,                        # terraces from the floor up to the street
    'rim_r': 30.0,                     # the rim edge at street level
    'ring_road': (30.0, 50.0),         # the road that circles the hole
    'rim_tower': (54.0, 96.0),         # the band of leaning rim towers (hole.py)
    'quiet_r': (2.2, 2.55),            # the quiet ring of light around her
    'anchor_r': 3.4,                   # where the cables meet the floor
}
D2R = math.pi / 180
AVENUES_MAIN = [d * D2R for d in (45, 135, 225, 315)]
AVENUES_SECOND = [d * D2R for d in (0, 90, 180, 270)]
AVENUE_W = 24.0
SECOND_START = 165.0
RINGS = [{'r': 165.0, 'w': 18.0}, {'r': 300.0, 'w': 18.0}, {'r': 470.0, 'w': 16.0}, {'r': 680.0, 'w': 16.0},
         {'r': 940.0, 'w': 16.0}, {'r': 1250.0, 'w': 14.0}]
CITY_R = 1450.0                        # the built city; a far skyline ring stands beyond it
FAR_R = (1500.0, 2500.0)
LM_R = 1500.0                          # the street light map covers |x|,|z| <= LM_R
CLOUD = {'base': 345.0, 'skirt': 375.0, 'top': 520.0}   # the low rain-cloud deck

# the palette (sRGB hex): wet black, petrol teal, sodium, neon accents
PAL = {'cyan': '#29e7ff', 'magenta': '#ff4fd8', 'sodium': '#ff8a3d', 'red': '#ff2a4a', 'gold': '#ffc23d',
       'white': '#e9f3f1', 'teal': '#0d3644', 'navy': '#06141d', 'violet': '#33204f', 'green': '#39ff9a'}

# ------------------------------------------------------------------------------------------------ small utilities
SETS_DIR = os.path.join(common.EIDOVERSE_DIR, 'sets', 'unknown_force') + os.sep    # the WebGPU sets (sources)
REPO_DIR = common.REPO + os.sep
FONT_DIR = os.path.join(common.ASSETS_DIR, 'fonts')


def fs_path(u) -> str:
    """A file URL (or a path) as a filesystem path: citykit.js's fsPath (drops the leading slash before C:/)."""
    from urllib.parse import unquote, urlparse
    s = str(u)
    if s.startswith('file:'):
        p = unquote(urlparse(s).path)
        return p[1:] if len(p) > 2 and p[0] == '/' and p[2] == ':' else p
    return s


def clamp01(x):
    return max(0.0, min(1.0, x))


def smooth(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def smoother(x):
    x = clamp01(x)
    return x * x * x * (x * (x * 6 - 15) + 10)


def lerp(a, b, k):
    return a + (b - a) * k


def jround(x):
    """JavaScript's Math.round (halves round up)."""
    return math.floor(x + 0.5)


_M32 = 0xFFFFFFFF


def rng(seed):
    """mulberry32, bit for bit citykit.js's rng(seed): r() -> [0, 1)."""
    st = [(int(seed) & _M32) or 1]

    def r():
        a = (st[0] + 0x6D2B79F5) & _M32
        st[0] = a
        t = ((a ^ (a >> 15)) * (1 | a)) & _M32
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & _M32)) & _M32) ^ t
        return ((t ^ (t >> 14)) & _M32) / 4294967296.0
    return r


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


def ang_diff(a, b):
    """Wrapped difference a - b in (-pi, pi]."""
    d = a - b
    while d > math.pi:
        d -= 2 * math.pi
    while d < -math.pi:
        d += 2 * math.pi
    return d


def nearest_avenue(theta, r):
    """Signed perpendicular distance to the nearest avenue that exists at radius r: {'d', 'th'}."""
    best = {'d': 1e9, 'th': 0.0}
    alls = AVENUES_MAIN + (AVENUES_SECOND if r >= SECOND_START - 4 else [])
    for a in alls:
        d = r * math.sin(ang_diff(theta, a))
        if abs(d) < abs(best['d']) and math.cos(ang_diff(theta, a)) > 0:
            best = {'d': d, 'th': a}
    return best


def hex_rgb(h):
    n = int(h[1:], 16)
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255]


def hex_lin(h):
    """citykit.js's hexLin: pow(v / 255, 2.2) per channel (the kit's own approximation of the sRGB curve)."""
    return [math.pow(v / 255, 2.2) for v in hex_rgb(h)]


def srgb_lin(h):
    """The exact sRGB decode of a '#rrggbb' or 0xRRGGBB colour (three's Color(hex) in a linear working space)."""
    if isinstance(h, int):
        v = [((h >> 16) & 255) / 255, ((h >> 8) & 255) / 255, (h & 255) / 255]
    else:
        v = [c / 255 for c in hex_rgb(h)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v)


# ------------------------------------------------------------------------------------------------ three-space maths
def to_blender(p):
    """three (x, y, z) -> Blender (x, -z, y)."""
    return (float(p[0]), -float(p[2]), float(p[1]))


def from_blender(p):
    return (float(p[0]), float(p[2]), -float(p[1]))


def _to_b(P):
    P = np.asarray(P, np.float64).reshape(-1, 3)
    return np.stack([P[:, 0], -P[:, 2], P[:, 1]], 1)


def quat_mul(a, b):
    """Quaternions as (x, y, z, w), three's order: a * b."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (ax * bw + aw * bx + ay * bz - az * by, ay * bw + aw * by + az * bx - ax * bz,
            az * bw + aw * bz + ax * by - ay * bx, aw * bw - ax * bx - ay * by - az * bz)


def quat_axis(axis, ang):
    s = math.sin(ang / 2)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(ang / 2))


def quat_euler_yxz(x, y, z=0.0):
    """three's Quaternion.setFromEuler(new Euler(x, y, z, 'YXZ'))."""
    c1, c2, c3 = math.cos(x / 2), math.cos(y / 2), math.cos(z / 2)
    s1, s2, s3 = math.sin(x / 2), math.sin(y / 2), math.sin(z / 2)
    return (s1 * c2 * c3 + c1 * s2 * s3, c1 * s2 * c3 - s1 * c2 * s3, c1 * c2 * s3 - s1 * s2 * c3,
            c1 * c2 * c3 + s1 * s2 * s3)


def quat_matrix(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]], np.float64)


def quat_rotate(q, v):
    return tuple(quat_matrix(q) @ np.asarray(v, np.float64))


def quat_from_matrix(m):
    """Rotation matrix (3x3, three axes) -> quaternion (x, y, z, w), three's setFromRotationMatrix."""
    m11, m12, m13 = m[0]
    m21, m22, m23 = m[1]
    m31, m32, m33 = m[2]
    tr = m11 + m22 + m33
    if tr > 0:
        s = 0.5 / math.sqrt(tr + 1.0)
        return ((m32 - m23) * s, (m13 - m31) * s, (m21 - m12) * s, 0.25 / s)
    if m11 > m22 and m11 > m33:
        s = 2.0 * math.sqrt(1.0 + m11 - m22 - m33)
        return (0.25 * s, (m12 + m21) / s, (m13 + m31) / s, (m32 - m23) / s)
    if m22 > m33:
        s = 2.0 * math.sqrt(1.0 + m22 - m11 - m33)
        return ((m12 + m21) / s, 0.25 * s, (m23 + m32) / s, (m13 - m31) / s)
    s = 2.0 * math.sqrt(1.0 + m33 - m11 - m22)
    return ((m13 + m31) / s, (m23 + m32) / s, 0.25 * s, (m21 - m12) / s)


def look_rotation(eye, target, up=(0.0, 1.0, 0.0)):
    """three's Matrix4.lookAt(eye, target, up) rotation (3x3): +Z points from target to eye."""
    z = np.asarray(eye, np.float64) - np.asarray(target, np.float64)
    if np.dot(z, z) == 0:
        z = np.array([0.0, 0.0, 1.0])
    z /= np.linalg.norm(z)
    x = np.cross(np.asarray(up, np.float64), z)
    if np.dot(x, x) == 0:
        z = z + np.array([0.0001 if abs(up[2]) == 1 else 0.0, 0.0, 0.0001 if abs(up[2]) != 1 else 0.0])
        z /= np.linalg.norm(z)
        x = np.cross(np.asarray(up, np.float64), z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], 1)


def blender_rotation(q3):
    """A three quaternion as a Blender mathutils.Quaternion (w, x, y, z): the rotation's axis maps like a vector."""
    x, y, z, w = q3
    return (w, x, -z, y)


# ------------------------------------------------------------------------------------------------ fonts + canvas
CITY_FONTS = [('Rajdhani-Bold.ttf', 'Rajdhani'), ('Michroma-Regular.ttf', 'Michroma'), ('Monoton-Regular.ttf', 'Monoton'),
              ('BlackOpsOne-Regular.ttf', 'Black Ops One'), ('Audiowide-Regular.ttf', 'Audiowide'),
              ('ShareTechMono-Regular.ttf', 'Share Tech Mono'), ('SedgwickAveDisplay-Regular.ttf', 'Sedgwick Ave Display'),
              ('Exo2.ttf', 'Exo 2'), ('SpecialElite-Regular.ttf', 'Special Elite')]
_FONTS = None


def register_fonts():
    """The kit's nine bundled faces under the names the canvas fonts use ('Black Ops One', 'Exo 2' ...). Returns the
    registry (a Fonts of interiors_lib's canvas, kept for this kit, so the other sets' families stay their own)."""
    global _FONTS
    if _FONTS is None:
        from . import interiors_lib as IL
        f = IL.Fonts()
        for fn, fam in CITY_FONTS:
            p = os.path.join(FONT_DIR, fn)
            if os.path.isfile(p):
                f.register(p, fam)
            else:
                print('[citykit] font registration: missing', p, flush=True)
        _FONTS = f
    return _FONTS


def _gauss_blur(a, sigma):
    """A Gaussian blur as three box blurs (as Skia blurs canvas shadows): a (h, w) float array."""
    if sigma <= 0.25:
        return a
    r = max(1, int(round((math.sqrt(12 * sigma * sigma / 3 + 1) - 1) / 2)))
    out = a.astype(np.float64)
    for _ in range(3):
        for ax in (0, 1):
            pad = [(0, 0), (0, 0)]
            pad[ax] = (r + 1, r)
            p = np.pad(out, pad)
            c = np.cumsum(p, axis=ax)
            n = out.shape[ax]
            hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax)
            lo = np.take(c, np.arange(0, n), axis=ax)
            out = (hi - lo) / (2 * r + 1)
    return out.astype(np.float32)


_CityCtx = None


def _city_context_class():
    """CityContext2D: interiors_lib's Context2D plus what the city's canvas art uses on top: shadowColor/shadowBlur
    (the neon glow, drawn beneath each fill as Skia does: the shape's alpha blurred by sigma = blur / 2), roundRect,
    and save()/restore() of that extra state."""
    global _CityCtx
    if _CityCtx is not None:
        return _CityCtx
    from . import interiors_lib as IL
    EXTRA = ('shadowColor', 'shadowBlur', 'shadowOffsetX', 'shadowOffsetY')

    class CityContext2D(IL.Context2D):
        def __init__(self, canvas):
            super().__init__(canvas)
            object.__setattr__(self, '_x', {'shadowColor': 'rgba(0,0,0,0)', 'shadowBlur': 0.0,
                                            'shadowOffsetX': 0.0, 'shadowOffsetY': 0.0})
            object.__setattr__(self, '_xstack', [])

        def __getattr__(self, k):
            if k in EXTRA:
                return object.__getattribute__(self, '_x')[k]
            return super().__getattr__(k)

        def __setattr__(self, k, v):
            if k in EXTRA:
                self._x[k] = v
            else:
                super().__setattr__(k, v)

        def save(self):
            super().save()
            self._xstack.append(dict(self._x))

        def restore(self):
            super().restore()
            if self._xstack:
                object.__setattr__(self, '_x', self._xstack.pop())

        def roundRect(self, x, y, w, h, r=0.0):
            if isinstance(r, (list, tuple)):
                r = r[0] if r else 0.0
            r = max(0.0, min(float(r), abs(w) / 2, abs(h) / 2))
            if r <= 0:
                self.rect(x, y, w, h)
                return
            P = math.pi
            self.moveTo(x + r, y)
            self.lineTo(x + w - r, y)
            self.arc(x + w - r, y + r, r, -P / 2, 0)
            self.lineTo(x + w, y + h - r)
            self.arc(x + w - r, y + h - r, r, 0, P / 2)
            self.lineTo(x + r, y + h)
            self.arc(x + r, y + h - r, r, P / 2, P)
            self.lineTo(x, y + r)
            self.arc(x + r, y + r, r, P, 1.5 * P)
            self.closePath()

        def _composite(self, bbox, cov, style):
            blur = float(self._x['shadowBlur'] or 0.0)
            if blur > 0:
                sr, sg, sb, sa = IL.parse_color(self._x['shadowColor'])
                if sa > 0:
                    ga = float(self.globalAlpha)
                    fa = cov if isinstance(style, IL.Gradient) else cov * IL.parse_color(style)[3]
                    sigma = blur / 2.0
                    pad = int(math.ceil(sigma * 3)) + 1
                    x0, y0, x1, y1 = bbox
                    W, H = self.canvas.width, self.canvas.height
                    ox, oy = int(round(self._x['shadowOffsetX'])), int(round(self._x['shadowOffsetY']))
                    X0, Y0 = max(0, x0 - pad + min(0, ox)), max(0, y0 - pad + min(0, oy))
                    X1, Y1 = min(W, x1 + pad + max(0, ox)), min(H, y1 + pad + max(0, oy))
                    m = np.zeros((Y1 - Y0, X1 - X0), np.float32)
                    ya, xa = y0 - Y0 + oy, x0 - X0 + ox
                    sy0, sx0 = max(0, -ya), max(0, -xa)
                    ey, ex = min(cov.shape[0], m.shape[0] - ya), min(cov.shape[1], m.shape[1] - xa)
                    if ey > sy0 and ex > sx0:
                        m[ya + sy0:ya + ey, xa + sx0:xa + ex] = fa[sy0:ey, sx0:ex]
                    a = _gauss_blur(m, sigma) * (sa * ga)
                    dst = self.canvas.buf[Y0:Y1, X0:X1]
                    dst *= (1.0 - a[..., None])
                    dst[..., 0] += sr * a
                    dst[..., 1] += sg * a
                    dst[..., 2] += sb * a
                    dst[..., 3] += a
            super()._composite(bbox, cov, style)

    _CityCtx = CityContext2D
    return _CityCtx


def make_canvas(w, h):
    """A canvas and its 2D context ({'canvas', 'ctx'} as citykit.js's makeCanvas): the kit's fonts registered."""
    from . import interiors_lib as IL
    cv = IL.Canvas(int(w), int(h), register_fonts())
    ctx = _city_context_class()(cv)
    cv._ctx = ctx
    return {'canvas': cv, 'ctx': ctx}


# ------------------------------------------------------------------------------------------------ Blender data helpers
class Made(list):
    """Every datablock a build made (dispose() removes them), plus the shared ones it uses (share(): a texture file
    loaded once for every set in the file), which dispose() removes only when nothing else uses them any more.

    Every datablock a kit makes is its own: a second set built in the same file (another seed, the hole beside the
    city) gets new datablocks (Blender adds .001 to a name already taken) and never touches the first one's."""

    def add(self, idb):
        self.append(idb)
        return idb

    def share(self, idb):
        if not hasattr(self, 'shared'):
            self.shared = []
        if idb is not None and idb not in self.shared:
            self.shared.append(idb)
        return idb

    @staticmethod
    def _remove(idb):
        coll = {bpy.types.Object: bpy.data.objects, bpy.types.Mesh: bpy.data.meshes,
                bpy.types.Material: bpy.data.materials, bpy.types.Image: bpy.data.images,
                bpy.types.Collection: bpy.data.collections, bpy.types.Light: bpy.data.lights,
                bpy.types.World: bpy.data.worlds, bpy.types.Camera: bpy.data.cameras}
        for t, c in coll.items():
            if isinstance(idb, t):
                c.remove(idb)
                return
        if isinstance(idb, bpy.types.NodeTree):
            bpy.data.node_groups.remove(idb)

    def dispose(self):
        if bpy is None:
            return
        for idb in reversed(self):
            try:
                self._remove(idb)
            except (ReferenceError, RuntimeError):
                pass
        self.clear()
        for idb in getattr(self, 'shared', []):
            try:
                if idb.users == 0:
                    self._remove(idb)
            except (ReferenceError, RuntimeError):
                pass
        self.shared = []


class SetDict(dict):
    """A set as the engine returned it: a dict of its contract (group, collection, parts, update, dispose, cams, and
    the Blender additions animate, make_cameras), whose keys also read as attributes (city.parts is city['parts']).
    A key wins over a dict method of the same name: city.update(t, state) is the set's update, not dict.update."""

    def __getattribute__(self, k):
        if not k.startswith('__'):
            try:
                return dict.__getitem__(self, k)
            except KeyError:
                pass
        return dict.__getattribute__(self, k)

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k) from None

    def __setattr__(self, k, v):
        self[k] = v


def scene_and_ctx(first=None, opts=None, kw=None):
    """build(first, opts, **kw): the registry (eidoblend.sets.build) passes the harness ctx first; a bpy Scene or the
    JS-style opts dict work there too. -> (opts dict, scene, ctx or None). Keys made with a ctx go through ctx.key."""
    o = {}
    ctx = None
    scene = None
    if first is not None:
        if isinstance(first, dict):
            o.update(first)
        elif bpy is not None and isinstance(first, bpy.types.Scene):
            scene = first
        elif hasattr(first, 'scene') and hasattr(first, 'key'):
            ctx = first
            scene = first.scene
        else:
            raise TypeError(f'build: the first argument is a harness ctx, a bpy Scene or an opts dict, '
                            f'not {type(first).__name__}')
    o.update(opts or {})
    o.update(kw or {})
    ctx = o.pop('ctx', None) or ctx
    if ctx is not None and scene is None:
        scene = ctx.scene
    scene = o.get('scene') or scene or (bpy.context.scene if bpy is not None else None)
    o['scene'] = scene
    return o, scene, ctx


def image_from_rgba(name, rgba, *, colorspace='sRGB', alpha_mode='STRAIGHT', top_down=True, made=None, pack=True,
                    float_buffer=False, image=None):
    """A packed Blender image from an (h, w, 4) array (uint8 or float 0..1). top_down: row 0 is the image's top (a
    canvas); otherwise row 0 is its bottom (three's DataTexture rows, sampled at v = 0). image: an image this set made
    earlier, rewritten in place (a redrawn canvas) when its size matches; otherwise a new image is made (named name, or
    name.001 when another set holds that name: an image is never taken over by name)."""
    a = np.asarray(rgba)
    h, w = a.shape[:2]
    if a.dtype == np.uint8:
        f = a.astype(np.float32) / 255.0
    else:
        f = a.astype(np.float32)
    if f.shape[2] == 3:
        f = np.concatenate([f, np.ones((h, w, 1), np.float32)], 2)
    if top_down:
        f = f[::-1]
    img = image
    if img is not None and (img.size[0] != w or img.size[1] != h or img.is_float != float_buffer):
        img = None
    if img is None:
        img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=float_buffer)
        if made is not None:
            made.add(img)
    img.colorspace_settings.name = colorspace
    img.alpha_mode = alpha_mode
    img.pixels.foreach_set(np.ascontiguousarray(f).ravel())
    img.update()
    if pack:
        img.pack()
    return img


def canvas_image(cv, name, *, made=None, alpha=True, image=None):
    """A canvas (CityContext2D's) as a packed sRGB image, the right way up; RGB and alpha kept apart (channel
    packed), so a material multiplies by alpha itself, as three did with its unpremultiplied CanvasTexture. image: the
    canvas's image from an earlier call, rewritten in place (a redraw)."""
    return image_from_rgba(name, cv.rgba8(), colorspace='sRGB', alpha_mode='CHANNEL_PACKED' if alpha else 'STRAIGHT',
                           top_down=True, made=made, image=image)


def make_mesh(name, verts3, faces, *, uv=None, attrs=None, smooth=False, made=None):
    """A Blender mesh from three-space vertices (converted to Blender axes), faces ((m, k) array or index lists),
    per-vertex uv (n, 2) and point attributes {name: (array, 'FLOAT_COLOR' | 'FLOAT_VECTOR' | 'FLOAT2' | 'FLOAT')}."""
    me = bpy.data.meshes.new(name)
    if made is not None:
        made.add(me)
    vb = _to_b(verts3).astype(np.float32)
    me.vertices.add(len(vb))
    me.vertices.foreach_set('co', vb.ravel())
    if isinstance(faces, np.ndarray) and faces.ndim == 2:
        k = faces.shape[1]
        loops = faces.ravel().astype(np.int32)
        starts = np.arange(0, len(faces) * k, k, dtype=np.int32)
    else:
        faces = [list(f) for f in faces]
        loops = np.array([i for f in faces for i in f], np.int32)
        sizes = np.array([len(f) for f in faces], np.int32)
        starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32) if len(faces) else np.zeros(0, np.int32)
    if len(starts):
        me.loops.add(len(loops))
        me.loops.foreach_set('vertex_index', loops)
        me.polygons.add(len(starts))
        me.polygons.foreach_set('loop_start', starts)
    me.update(calc_edges=True)
    if uv is not None and len(starts):
        lay = me.uv_layers.new(name='UVMap')
        lay.data.foreach_set('uv', np.asarray(uv, np.float32).reshape(-1, 2)[loops].ravel())
    for nm, (arr, typ) in (attrs or {}).items():
        at = me.attributes.new(nm, typ, 'POINT')
        key = {'FLOAT_COLOR': 'color', 'FLOAT_VECTOR': 'vector', 'FLOAT2': 'vector', 'FLOAT': 'value'}[typ]
        at.data.foreach_set(key, np.ascontiguousarray(np.asarray(arr, np.float32)).ravel())
    if smooth:
        me.shade_smooth()
    else:
        me.shade_flat()
    return me


def new_object(name, data, collection, *, parent=None, made=None):
    ob = bpy.data.objects.new(name, data)
    collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    if made is not None:
        made.add(ob)
    return ob


def audit_flags(ob, *, support=True, clipping=True, camera=True, zfight=False):
    """The engine's userData audit flags as the harness's object custom properties (no_support_check,
    no_clipping_check, no_z_fight_check); no_camera_collide records the engine's noCameraCollide (the camera audit
    takes exclusions by call: CameraSafety.exclude)."""
    if support:
        ob['no_support_check'] = True
    if clipping:
        ob['no_clipping_check'] = True
    if camera:
        ob['no_camera_collide'] = True
    if zfight:
        ob['no_z_fight_check'] = True
    return ob


# ------------------------------------------------------------------------------------------------ textures
def _texture_roots():
    roots = [Path(common.cache_dir('textures'))]
    env = os.environ.get('EIDO_TEXTURE_CACHE')
    if env:
        roots.append(Path(env))
    git = Path(common.REPO) / '.git'
    try:                                                 # a worktree reads the main checkout's library
        if git.is_file():
            line = git.read_text().strip()
            if line.startswith('gitdir:'):
                main = Path(line.split(':', 1)[1].strip()).parents[2]
                roots.append(main / 'eidoverse' / 'assets' / 'cache' / 'textures')
    except OSError:
        pass
    return roots


def _find_pbr(tid, res):
    for root in _texture_roots():
        d = root / f'{tid}_{res}'
        if d.is_dir():
            files = list(d.iterdir())

            def pick(*suf):
                for s in suf:
                    for f in files:
                        if f.stem.lower().endswith(s.lower()) and not f.stem.lower().endswith('normaldx'):
                            return str(f)
                return None
            return {'diff': pick('_Color', '_diff'), 'normal': pick('_NormalGL', '_normal'), 'rough': pick('_Roughness', '_rough')}
    return None


def load_pbr(tid, res='1k', made=None):
    """A CC0 AmbientCG set (1k) from the shared texture library, fetched on first use with the repo's
    fetch_texture.py: {'map', 'normal_map', 'roughness_map'} as Blender images (colour sRGB, data Non-Color). The file
    images are shared by every set in the file (recorded in made as shared: a dispose removes one only when no other
    set still uses it)."""
    F = _find_pbr(tid, res)
    if F is None:
        fetch = Path(common.REPO) / 'fetch_texture.py'
        print(f'[citykit] fetching {tid} {res} into the shared library', flush=True)
        py = os.environ.get('EIDO_PYTHON', 'python')
        try:
            subprocess.run([py, str(fetch), tid, res, '--cache'], cwd=str(common.REPO), check=False, timeout=600)
        except (OSError, subprocess.SubprocessError) as e:
            print('[citykit] fetch failed:', e, flush=True)
        F = _find_pbr(tid, res)
    if F is None:
        raise FileNotFoundError(f'[citykit] missing texture set {tid}_{res}: python fetch_texture.py {tid} {res} --cache')

    def load(p, data):
        if p is None:
            print('[citykit] missing texture', tid, flush=True)
            return None
        img = bpy.data.images.load(p, check_existing=True)
        if made is not None:
            made.share(img)
        img.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
        return img
    return {'map': load(F['diff'], False), 'normal_map': load(F['normal'], True), 'roughness_map': load(F['rough'], True)}


def noise_texture_rgba(N=512, seed=7):
    """The kit's value-noise fBm, tileable, (N, N, 4) uint8 (R: fbm, G: a second octave set, B: cellular-ish,
    A: ridged): citykit.js's noiseTexture, the same draws in the same order. Row 0 is three's v = 0."""
    R = rng(seed)

    def grid(n):                       # a Float32Array in the engine: each draw rounded to single precision
        return np.array([R() for _ in range(n * n)], np.float32).astype(np.float64)
    octs = [(n, grid(n)) for n in (4, 8, 16, 32, 64)]
    octs2 = [(n, grid(n)) for n in (6, 12, 24, 48)]
    ys, xs = np.mgrid[0:N, 0:N].astype(np.float64)

    def sample(g, n, x, y):
        xi, yi = np.floor(x), np.floor(y)
        fx, fy = x - xi, y - yi
        sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        xi, yi = xi.astype(np.int64), yi.astype(np.int64)

        def i(a, b):
            return g[((b % n + n) % n) * n + ((a % n + n) % n)]
        return lerp(lerp(i(xi, yi), i(xi + 1, yi), sx), lerp(i(xi, yi + 1), i(xi + 1, yi + 1), sx), sy)
    v = np.zeros((N, N))
    a, w = 0.5, 0.0
    for n, g in octs:
        v += a * sample(g, n, xs / N * n, ys / N * n)
        w += a
        a *= 0.55
    v2 = np.zeros((N, N))
    a, w2 = 0.5, 0.0
    for n, g in octs2:
        v2 += a * sample(g, n, xs / N * n, ys / N * n)
        w2 += a
        a *= 0.5
    r = 1 - np.abs(sample(octs[2][1], 16, xs / N * 16, ys / N * 16) * 2 - 1)
    out = np.empty((N, N, 4), np.uint8)
    out[..., 0] = np.floor(np.clip(v / w, 0, 1) * 255 + 0.5)
    out[..., 1] = np.floor(np.clip(v2 / w2, 0, 1) * 255 + 0.5)
    out[..., 2] = np.floor(np.clip(sample(octs[3][1], 32, xs / N * 32, ys / N * 32), 0, 1) * 255 + 0.5)
    out[..., 3] = np.floor(r * r * 255 + 0.5)
    return out


def noise_texture(N=512, seed=7, made=None):
    """noiseTexture as a packed Non-Color image (repeat), rows as the DataTexture's (row 0 at v = 0)."""
    return image_from_rgba('uf_noise', noise_texture_rgba(N, seed), colorspace='Non-Color', alpha_mode='CHANNEL_PACKED',
                           top_down=False, made=made)


def night_env_rgba(W=512, H=256):
    """The night the glass reflects (citykit.js's nightEnvTexture): an LDR equirect, overcast cloud base lit
    orange-violet by the city, a band of far lit windows at the horizon, a dark street with lamps and neon below.
    (H, W, 4) uint8, row 0 the zenith (the same draws in the same order)."""
    R = rng(1234)
    data = np.zeros((H, W, 3), np.float64)
    el = (0.5 - (np.arange(H) + 0.5) / H) * math.pi
    s = np.sin(el)[:, None] * np.ones((1, W))
    up = s >= 0
    hz, mid = np.power(1 - np.clip(s, 0, 1), 6), np.power(1 - np.clip(s, 0, 1), 2)
    g = np.power(1 + np.clip(s, -1, 0), 4)
    data[..., 0] = np.where(up, 0.016 + 0.07 * hz + 0.02 * mid, 0.020 + 0.05 * g)
    data[..., 1] = np.where(up, 0.012 + 0.03 * hz + 0.012 * mid, 0.014 + 0.03 * g)
    data[..., 2] = np.where(up, 0.026 + 0.05 * hz + 0.022 * mid, 0.016 + 0.035 * g)
    data = data.astype(np.float32).astype(np.float64)            # a Float32Array in the engine
    cols = [[1.0, 0.62, 0.3], [0.7, 0.86, 1.0], [0.16, 0.9, 1.0], [1.0, 0.31, 0.85], [1.0, 0.54, 0.24]]

    def add(x, y, c, k):
        if y < 0 or y >= H:
            return
        x = ((x % W) + W) % W
        for ch in range(3):
            data[y, x, ch] = float(np.float32(data[y, x, ch] + c[ch] * k))
    for _ in range(2600):
        x = math.floor(R() * W)
        e = (R() * R()) * 0.32 - 0.02
        y = math.floor((0.5 - e / math.pi) * H)
        if R() < 0.8:
            ci = 0 if R() < 0.6 else 1
        else:
            ci = 2 + math.floor(R() * 3)
        add(x, y, cols[ci], 0.25 + R() * 0.9)
    for _ in range(900):
        x = math.floor(R() * W)
        e = -0.04 - R() * 0.7
        y = math.floor((0.5 - e / math.pi) * H)
        ci = 4 if R() < 0.7 else math.floor(R() * 5)
        k = 0.4 + R() * 1.2
        add(x, y, cols[ci], k)
        add(x + 1, y, cols[ci], 0.2)
    out = np.empty((H, W, 4), np.uint8)
    out[..., :3] = np.floor(np.power(np.minimum(1.0, data), 1 / 2.2) * 255 + 0.5)
    out[..., 3] = 255
    return out


def night_env_texture(W=512, H=256, made=None):
    """nightEnvTexture as a packed sRGB equirect image (zenith at the top, as Blender's Environment Texture reads)."""
    return image_from_rgba('uf_night_env', night_env_rgba(W, H), colorspace='sRGB', top_down=True, made=made)


# ------------------------------------------------------------------------------------------------ merged geometry
class Xf:
    """A rigid transform for GeoBuf (three space): yaw about +Y, then lean about the local X axis pivoting at
    (0, lean_pivot_y, 0), then translate. q is three's quaternion (x, y, z, w), m its 4x4 matrix."""

    def __init__(self, pos, yaw=0.0, lean=0.0, lean_pivot_y=0.0):
        self.pos = np.asarray(pos, np.float64)
        self.q = quat_euler_yxz(lean, yaw, 0.0)
        self.R = quat_matrix(self.q)
        self.pivot = np.array([0.0, lean_pivot_y, 0.0])
        self.m = np.eye(4)
        self.m[:3, :3] = self.R
        self.m[:3, 3] = self.pos

    def p(self, c):
        v = self.R @ (np.asarray(c, np.float64) - self.pivot) + self.pivot + self.pos
        return [float(v[0]), float(v[1]), float(v[2])]

    def pts(self, C):
        C = np.asarray(C, np.float64).reshape(-1, 3)
        return (C - self.pivot) @ self.R.T + self.pivot + self.pos


def make_xf(pos, yaw=0.0, lean=0.0, lean_pivot_y=0.0):
    """citykit.js's makeXf: p'(c) = R(c - pivot) + pivot + pos."""
    return Xf(pos, yaw, lean, lean_pivot_y)


class GeoBuf:
    """Merged facade geometry (citykit.js's GeoBuf). Each quad carries its own four vertices with: position, uv in
    METRES (u along the face, v height from the building's base; roofs: local x, z), aT = (seed, litFraction, warmth,
    accent), aM = (kind, floorH, bayW, top), aW = (window x-margin, sill, head, face). kind: 0 wall, 1 roof,
    2 frame (no windows), 3 shopfront, 4 beacon, 5 elevator shaft. build() makes one Blender mesh of quads."""

    def __init__(self):
        self._P, self._UV, self._aT, self._aM, self._aW = [], [], [], [], []
        self._vP, self._vUV, self._vaT, self._vaM, self._vaW = [], [], [], [], []
        self.idx = []                 # triangles over vert()'s vertices (the JS API's index list)
        self.count = 0

    def vert(self, p, n, uv, aT, aM, aW):
        """One vertex (the JS API; quad() and box() are the bulk path). n is recomputed by Blender."""
        self._vP.append(list(p))
        self._vUV.append(list(uv))
        self._vaT.append(list(aT))
        self._vaM.append(list(aM))
        self._vaW.append(list(aW))
        i = len(self._vP) - 1
        self.count += 1
        return i

    def _add(self, P, UV, aT, aM, aW):
        k = P.shape[0]
        self._P.append(P.reshape(-1, 3))
        self._UV.append(np.asarray(UV, np.float64).reshape(-1, 2))
        self._aT.append(np.broadcast_to(np.asarray(aT, np.float64).reshape(-1, 1, 4), (k, 4, 4)).reshape(-1, 4))
        self._aM.append(np.broadcast_to(np.asarray(aM, np.float64).reshape(-1, 1, 4), (k, 4, 4)).reshape(-1, 4))
        self._aW.append(np.broadcast_to(np.asarray(aW, np.float64).reshape(-1, 1, 4), (k, 4, 4)).reshape(-1, 4))
        self.count += 4 * k

    def quad(self, xf, c, uvs, aT, aM, aW):
        """A quad from 4 LOCAL corners (counter-clockwise seen from outside) transformed by xf."""
        P = xf.pts(c).reshape(1, 4, 3)
        self._add(P, np.asarray(uvs, np.float64).reshape(1, 4, 2), [aT], [aM], [aW])

    def box(self, xf, x0, y0, z0, x1, y1, z1, attrs, opt=None):
        """An axis-aligned box in the local frame, optionally with a sloped top (top at z0 = y1a, at z1 = y1b).
        opt: faces (which of 'xXzZtb' to emit; all by default), vBase (window rows count from it), top (aM.w),
        roofM, y1a, y1b."""
        opt = opt or {}
        y1a = opt.get('y1a', y1)
        y1b = opt.get('y1b', y1)
        vb = opt.get('vBase', 0.0)
        aT = attrs['aT']
        aMa = attrs['aM']
        top = opt['top'] if opt.get('top') is not None else (aMa[3] if len(aMa) > 3 and aMa[3] is not None else 0)
        aM = [aMa[0], aMa[1], aMa[2], top]
        aWa = attrs['aW']
        roofM = opt.get('roofM') or [1, aM[1], aM[2], aM[3]]
        f = opt.get('faces') or 'xXzZtb'
        C, U, M, W = [], [], [], []
        if 'X' in f:
            C.append([[x1, y0, z1], [x1, y0, z0], [x1, y1a, z0], [x1, y1b, z1]])
            U.append([[-z1, y0 - vb], [-z0, y0 - vb], [-z0, y1a - vb], [-z1, y1b - vb]])
            M.append(aM)
            W.append([aWa[0], aWa[1], aWa[2], 0])
        if 'x' in f:
            C.append([[x0, y0, z0], [x0, y0, z1], [x0, y1b, z1], [x0, y1a, z0]])
            U.append([[z0, y0 - vb], [z1, y0 - vb], [z1, y1b - vb], [z0, y1a - vb]])
            M.append(aM)
            W.append([aWa[0], aWa[1], aWa[2], 1])
        if 'Z' in f:
            C.append([[x0, y0, z1], [x1, y0, z1], [x1, y1b, z1], [x0, y1b, z1]])
            U.append([[x0, y0 - vb], [x1, y0 - vb], [x1, y1b - vb], [x0, y1b - vb]])
            M.append(aM)
            W.append([aWa[0], aWa[1], aWa[2], 2])
        if 'z' in f:
            C.append([[x1, y0, z0], [x0, y0, z0], [x0, y1a, z0], [x1, y1a, z0]])
            U.append([[-x1, y0 - vb], [-x0, y0 - vb], [-x0, y1a - vb], [-x1, y1a - vb]])
            M.append(aM)
            W.append([aWa[0], aWa[1], aWa[2], 3])
        if 't' in f:
            C.append([[x0, y1b, z1], [x1, y1b, z1], [x1, y1a, z0], [x0, y1a, z0]])
            U.append([[x0, z1], [x1, z1], [x1, z0], [x0, z0]])
            M.append(roofM)
            W.append([0, 0, 0, 4])
        if 'b' in f:
            C.append([[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]])
            U.append([[x0, z0], [x1, z0], [x1, z1], [x0, z1]])
            M.append(roofM)
            W.append([0, 0, 0, 4])
        if not C:
            return
        P = xf.pts(np.asarray(C, np.float64).reshape(-1, 3)).reshape(-1, 4, 3)
        self._add(P, np.asarray(U, np.float64), [aT] * len(C), M, W)

    def arrays(self):
        """(P (n, 3), uv (n, 2), aT, aM, aW, faces): quads first, then vert()'s triangles."""
        P = np.concatenate(self._P) if self._P else np.zeros((0, 3))
        UV = np.concatenate(self._UV) if self._UV else np.zeros((0, 2))
        aT = np.concatenate(self._aT) if self._aT else np.zeros((0, 4))
        aM = np.concatenate(self._aM) if self._aM else np.zeros((0, 4))
        aW = np.concatenate(self._aW) if self._aW else np.zeros((0, 4))
        nq = len(P) // 4
        faces = [list(range(4 * i, 4 * i + 4)) for i in range(nq)] if self._vP else np.arange(4 * nq).reshape(-1, 4)
        if self._vP:
            base = len(P)
            P = np.concatenate([P, np.asarray(self._vP, np.float64)])
            UV = np.concatenate([UV, np.asarray(self._vUV, np.float64)])
            aT = np.concatenate([aT, np.asarray(self._vaT, np.float64)])
            aM = np.concatenate([aM, np.asarray(self._vaM, np.float64)])
            aW = np.concatenate([aW, np.asarray(self._vaW, np.float64)])
            for i in range(0, len(self.idx) - 2, 3):
                faces.append([base + self.idx[i], base + self.idx[i + 1], base + self.idx[i + 2]])
        return P, UV, aT, aM, aW, faces

    def build(self, name='uf_geobuf', made=None):
        """One Blender mesh (Blender axes) with the UV map and the aT / aM / aW colour attributes."""
        P, UV, aT, aM, aW, faces = self.arrays()
        return make_mesh(name, P, faces, uv=UV, attrs={'aT': (aT, 'FLOAT_COLOR'), 'aM': (aM, 'FLOAT_COLOR'),
                                                        'aW': (aW, 'FLOAT_COLOR')}, made=made)


def frame_attrs(me, aT=(0.4, 0, 0.5, 0)):
    """Give a plain mesh (a box, a torus ...) the facade attributes of a windowless dark frame, so it can use the
    facade-family materials (which read aT / aM / aW)."""
    n = len(me.vertices)
    for nm, v in (('aT', aT), ('aM', (2, 4, 4, 0)), ('aW', (0, 0, 0, 0))):
        at = me.attributes.get(nm) or me.attributes.new(nm, 'FLOAT_COLOR', 'POINT')
        at.data.foreach_set('color', np.tile(np.asarray(v, np.float32), n))
    return me


# ------------------------------------------------------------------------------------------------ node expressions
class V:
    """A value in a node tree: a socket or a Python constant, of kind 'f' (float) or 'v' (3-vector)."""
    __slots__ = ('nb', 's', 'k', 'c')

    def __init__(self, nb, s=None, k='f', c=None):
        self.nb, self.s, self.k, self.c = nb, s, k, c

    def __add__(self, o): return self.nb.add(self, o)
    def __radd__(self, o): return self.nb.add(o, self)
    def __sub__(self, o): return self.nb.sub(self, o)
    def __rsub__(self, o): return self.nb.sub(o, self)
    def __mul__(self, o): return self.nb.mul(self, o)
    def __rmul__(self, o): return self.nb.mul(o, self)
    def __truediv__(self, o): return self.nb.div(self, o)
    def __rtruediv__(self, o): return self.nb.div(o, self)
    def __neg__(self): return self.nb.mul(self, -1.0)

    @property
    def x(self): return self.nb.comp(self, 0)

    @property
    def y(self): return self.nb.comp(self, 1)

    @property
    def z(self): return self.nb.comp(self, 2)


HASH_MODE = 'film'                     # hash12 as three r184 ran it ('film'), or as citykit.js reads ('hoskins')
HASH_MODES = ('film', 'hoskins')


def hash12_np(x, y, mode=None):
    """NB.hash12 in numpy float32 (the GPU's precision), for checks: the film's form or Hoskins' full hash."""
    f = np.float32
    x, y = np.asarray(x, f), np.asarray(y, f)
    a = (x * f(0.1031)) % f(1)
    b = (y * f(0.1031)) % f(1)
    if (mode or HASH_MODE) == 'film':
        return ((a + b) * a) % f(1)
    d = a * (b + f(33.33)) + b * (a + f(33.33)) + a * (a + f(33.33))
    return ((a + d + (b + d)) * (a + d)) % f(1)


_FOLD = {'ADD': lambda a, b: a + b, 'SUBTRACT': lambda a, b: a - b, 'MULTIPLY': lambda a, b: a * b,
         'DIVIDE': lambda a, b: a / b if b != 0 else 0.0, 'MAXIMUM': max, 'MINIMUM': min,
         'POWER': lambda a, b: math.pow(a, b) if a >= 0 else 0.0}


class NB:
    """Writes TSL-style maths as nodes in one node tree (a material's, a node group's, or a Geometry Nodes tree):

        nb = NB(mat.node_tree, K)
        g = nb.fract(nb.uv().x / 2.6)
        lit = nb.step(nb.hash12(cell_x, cell_y), 0.3)          # GLSL's step(edge, x): x >= edge
        col = nb.mix((0.6, 0.8, 1.0), (1.0, 0.6, 0.28), lit)

    Constants fold in Python; floats broadcast into vectors. Shader-only helpers (geometry, attributes, textures,
    uniforms, fog) need a material tree."""

    def __init__(self, tree, K=None):
        self.tree, self.K = tree, K
        self.nodes, self.links = tree.nodes, tree.links
        self._n = 0
        self._sep = {}
        self._c = {}

    # -------- plumbing
    def new(self, idname, **props):
        n = self.nodes.new(idname)
        for k, v in props.items():
            setattr(n, k, v)
        i = self._n
        self._n += 1
        n.location = ((i // 50) * 240.0, -(i % 50) * 110.0)
        return n

    def val(self, x):
        if isinstance(x, V):
            return x
        if isinstance(x, (int, float, np.floating, np.integer)):
            return V(self, None, 'f', float(x))
        t = tuple(float(a) for a in x)
        if len(t) != 3:
            raise ValueError(f'NB: a constant vector needs 3 components, got {t}')
        return V(self, None, 'v', t)

    def feed(self, x, sock):
        x = self.val(x)
        if x.s is not None:
            self.links.new(x.s, sock)
            return
        dv = sock.default_value
        try:
            n = len(dv)
        except TypeError:
            n = 0
        if n == 0:
            sock.default_value = x.c if x.k == 'f' else x.c[0]
        else:
            c = (x.c,) * 3 if x.k == 'f' else x.c
            sock.default_value = tuple(c[:3]) + ((1.0,) if n == 4 else ())

    @staticmethod
    def _sock(socks, ident):
        for s in socks:
            if s.identifier == ident:
                return s
        raise KeyError(ident)

    # -------- arithmetic
    def math(self, op, *args, clamp=False):
        a = [self.val(x) for x in args]
        n = self.new('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, x in enumerate(a):
            self.feed(x, n.inputs[i])
        return V(self, n.outputs[0], 'f')

    def vmath(self, op, *args):
        a = [self.val(x) for x in args]
        n = self.new('ShaderNodeVectorMath', operation=op)
        for i, x in enumerate(a):
            self.feed(x, n.inputs[3] if (op == 'SCALE' and i == 1) else n.inputs[i])
        if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE'):
            return V(self, n.outputs[1], 'f')
        return V(self, n.outputs[0], 'v')

    def _bin(self, op, a, b):
        a, b = self.val(a), self.val(b)
        if a.s is None and b.s is None and op in _FOLD:
            if a.k == 'f' and b.k == 'f':
                return self.val(_FOLD[op](a.c, b.c))
            ac = a.c if a.k == 'v' else (a.c,) * 3
            bc = b.c if b.k == 'v' else (b.c,) * 3
            return self.val(tuple(_FOLD[op](p, q) for p, q in zip(ac, bc)))
        kind = 'v' if (a.k == 'v' or b.k == 'v') else 'f'
        # identities
        if op == 'MULTIPLY':
            if b.s is None and b.k == 'f' and b.c == 1.0 and (kind == a.k):
                return a
            if a.s is None and a.k == 'f' and a.c == 1.0 and (kind == b.k):
                return b
            if (b.s is None and b.k == 'f' and b.c == 0.0) or (a.s is None and a.k == 'f' and a.c == 0.0):
                return self.val((0.0, 0.0, 0.0) if kind == 'v' else 0.0)
        if op in ('ADD', 'SUBTRACT') and b.s is None and b.k == 'f' and b.c == 0.0 and kind == a.k:
            return a
        if op == 'ADD' and a.s is None and a.k == 'f' and a.c == 0.0 and kind == b.k:
            return b
        if op == 'DIVIDE' and b.s is None and b.k == 'f' and b.c == 1.0 and kind == a.k:
            return a
        if kind == 'v':
            return self.vmath(op, a, b)
        return self.math(op, a, b)

    def add(self, a, b): return self._bin('ADD', a, b)
    def sub(self, a, b): return self._bin('SUBTRACT', a, b)
    def mul(self, a, b): return self._bin('MULTIPLY', a, b)
    def div(self, a, b): return self._bin('DIVIDE', a, b)
    def max(self, a, b): return self._bin('MAXIMUM', a, b)
    def min(self, a, b): return self._bin('MINIMUM', a, b)

    def pow(self, a, b):
        return self._bin('POWER', a, b)

    def _un(self, op_f, op_v, x, fold):
        x = self.val(x)
        if x.s is None:
            if x.k == 'f':
                return self.val(fold(x.c))
            return self.val(tuple(fold(c) for c in x.c))
        if x.k == 'v':
            if op_v is None:
                raise ValueError(f'NB: {op_f} on a vector')
            return self.vmath(op_v, x)
        return self.math(op_f, x)

    def floor(self, x): return self._un('FLOOR', 'FLOOR', x, math.floor)
    def fract(self, x): return self._un('FRACT', 'FRACTION', x, lambda c: c - math.floor(c))
    def abs(self, x): return self._un('ABSOLUTE', 'ABSOLUTE', x, abs)
    def exp(self, x): return self._un('EXPONENT', None, x, math.exp)
    def sin(self, x): return self._un('SINE', 'SINE', x, math.sin)
    def cos(self, x): return self._un('COSINE', 'COSINE', x, math.cos)
    def sqrt(self, x): return self._un('SQRT', None, x, lambda c: math.sqrt(max(c, 0.0)))

    def atan2(self, y, x):
        return self.math('ARCTAN2', y, x)

    def mod(self, a, b):
        """GLSL's mod (a - b floor(a / b)): Blender's FLOORED_MODULO."""
        return self.math('FLOORED_MODULO', a, b)

    def one_minus(self, x):
        return self.sub(1.0, x)

    def clamp(self, x, lo=0.0, hi=1.0):
        x = self.val(x)
        if x.s is None:
            return self.val(max(lo, min(hi, x.c))) if x.k == 'f' else self.val(tuple(max(lo, min(hi, c)) for c in x.c))
        if x.k == 'v':
            return self.min(self.max(x, lo), hi)
        lo, hi = self.val(lo), self.val(hi)
        if lo.s is None and hi.s is None and lo.c == 0.0 and hi.c == 1.0:
            return self.math('MULTIPLY', x, 1.0, clamp=True)
        n = self.new('ShaderNodeClamp', clamp_type='MINMAX')
        self.feed(x, n.inputs[0])
        self.feed(lo, n.inputs[1])
        self.feed(hi, n.inputs[2])
        return V(self, n.outputs[0], 'f')

    def mix(self, a, b, t):
        """GLSL mix(a, b, t) = a + (b - a) t (factor not clamped)."""
        a, b, t = self.val(a), self.val(b), self.val(t)
        if t.s is None and t.k == 'f':
            if t.c == 0.0:
                return a if not (b.k == 'v' and a.k == 'f') else self.add(a, (0.0, 0.0, 0.0))
            if t.c == 1.0:
                return b if not (a.k == 'v' and b.k == 'f') else self.add(b, (0.0, 0.0, 0.0))
        kind = 'v' if (a.k == 'v' or b.k == 'v') else 'f'
        n = self.new('ShaderNodeMix', data_type='FLOAT' if kind == 'f' else 'VECTOR', clamp_factor=False)
        if kind == 'v' and t.k == 'v':
            n.factor_mode = 'NON_UNIFORM'
            self.feed(t, self._sock(n.inputs, 'Factor_Vector'))
        else:
            self.feed(t, self._sock(n.inputs, 'Factor_Float'))
        if kind == 'f':
            self.feed(a, self._sock(n.inputs, 'A_Float'))
            self.feed(b, self._sock(n.inputs, 'B_Float'))
            return V(self, self._sock(n.outputs, 'Result_Float'), 'f')
        self.feed(a, self._sock(n.inputs, 'A_Vector'))
        self.feed(b, self._sock(n.inputs, 'B_Vector'))
        return V(self, self._sock(n.outputs, 'Result_Vector'), 'v')

    def select(self, cond, a, b):
        """TSL's select(cond, a, b): both evaluated (Blender's divide is safe, so no NaN comes through)."""
        return self.mix(b, a, cond)

    def smoothstep(self, e0, e1, x):
        """GLSL smoothstep (edges may be reversed, as the GPU computes it)."""
        e0, e1, x = self.val(e0), self.val(e1), self.val(x)
        if x.s is None and e0.s is None and e1.s is None:
            if e1.c == e0.c:
                return self.val(0.0)
            t = clamp01((x.c - e0.c) / (e1.c - e0.c))
            return self.val(t * t * (3 - 2 * t))
        n = self.new('ShaderNodeMapRange', data_type='FLOAT', interpolation_type='SMOOTHSTEP', clamp=True)
        self.feed(x, n.inputs[0])
        self.feed(e0, n.inputs[1])
        self.feed(e1, n.inputs[2])
        n.inputs[3].default_value = 0.0
        n.inputs[4].default_value = 1.0
        return V(self, n.outputs[0], 'f')

    def step(self, edge, x):
        """GLSL step(edge, x): 1 where x >= edge (Blender's GREATER_THAN; the edge itself is measure zero here)."""
        edge, x = self.val(edge), self.val(x)
        if edge.s is None and x.s is None:
            return self.val(1.0 if x.c >= edge.c else 0.0)
        return self.math('GREATER_THAN', x, edge)

    def comb(self, x, y, z=0.0):
        x, y, z = self.val(x), self.val(y), self.val(z)
        if x.s is None and y.s is None and z.s is None:
            return self.val((x.c, y.c, z.c))
        n = self.new('ShaderNodeCombineXYZ')
        for i, v in enumerate((x, y, z)):
            self.feed(v, n.inputs[i])
        return V(self, n.outputs[0], 'v')

    def comp(self, v, i):
        v = self.val(v)
        if v.k == 'f':
            return v
        if v.s is None:
            return self.val(v.c[i])
        key = v.s.as_pointer()
        n = self._sep.get(key)
        if n is None:
            n = self.new('ShaderNodeSeparateXYZ')
            self.links.new(v.s, n.inputs[0])
            self._sep[key] = n
        return V(self, n.outputs[i], 'f')

    def xz(self, v):
        """three's .xz of a three-space vector, as (x, z, 0)."""
        return self.comb(self.comp(v, 0), self.comp(v, 2), 0.0)

    def length(self, v):
        v = self.val(v)
        return self.abs(v) if v.k == 'f' else self.vmath('LENGTH', v)

    def dot(self, a, b): return self.vmath('DOT_PRODUCT', a, b)
    def cross(self, a, b): return self.vmath('CROSS_PRODUCT', a, b)
    def normalize(self, v): return self.vmath('NORMALIZE', v)

    # -------- the kit's hashes (citykit.js tslHelpers)
    def hash12(self, x, y):
        """citykit.js's hash12 as the film rendered it (HASH_MODE 'film', the default): with a = fract(x .1031),
        b = fract(y .1031), fract((a + b) a). The JS writes Dave Hoskins' hash without sine, but its
        p3.addAssign(dot(p3, p3.yzx + 33.33)) runs outside a Fn(), where three r184 skips the assignment (it logs
        'No stack defined for assign operation' for every call); every frame of the film was rendered, and its windows,
        floods, crowns, tints and flicker tuned, on that value: lower on average than uniform (mean 0.37), so more
        windows are lit and warm, in whole columns. The kit option hash='hoskins' (make_kit / build opts) gives the
        hash as the source reads it."""
        a = self.fract(self.mul(x, 0.1031))
        b = self.fract(self.mul(y, 0.1031))
        mode = (self.K.opts.get('hash') if self.K is not None else None) or HASH_MODE
        if mode == 'film':
            return self.fract((a + b) * a)
        c = a
        d = a * (b + 33.33) + b * (c + 33.33) + c * (a + 33.33)
        return self.fract((a + d + (b + d)) * (c + d))

    def hash11(self, x):
        return self.hash12(x, self.add(self.mul(x, 1.731), 17.17))

    def pulse(self, x, a, b, w):
        """The box-filtered periodic pulse: the average of [a <= fract(x) <= b] over a footprint w (cells)."""
        def F(t):
            return self.floor(t) * (self.sub(b, a)) + self.clamp(self.fract(t), a, b) - a
        hw = self.mul(w, 0.5)
        return (F(self.add(x, hw)) - F(self.sub(x, hw))) / w

    # -------- shader inputs (material / shader-group trees)
    def _cached(self, key, make):
        n = self._c.get(key)
        if n is None:
            n = self._c[key] = make()
        return n

    def geo(self, out):
        g = self._cached('geo', lambda: self.new('ShaderNodeNewGeometry'))
        return V(self, g.outputs[out], 'v' if out in ('Position', 'Normal', 'Incoming', 'Tangent', 'True Normal') else 'f')

    def view_distance(self):
        c = self._cached('cam', lambda: self.new('ShaderNodeCameraData'))
        return V(self, c.outputs['View Distance'], 'f')

    def three(self, v):
        """A Blender-axes vector in three's axes: (x, y, z) -> (x, z, -y)."""
        return self.comb(self.comp(v, 0), self.comp(v, 2), -self.comp(v, 1))

    def pos3(self):
        return self._cached('pos3v', lambda: self.three(self.geo('Position')))

    def nrm3(self):
        return self._cached('nrm3v', lambda: self.three(self.geo('Normal')))

    def cam3(self):
        """The camera's position (three axes): the shading point plus the incoming direction times the view distance."""
        def mk():
            cb = self.add(self.geo('Position'), self.mul(self.geo('Incoming'), self.view_distance()))
            return self.three(cb)
        return self._cached('cam3v', mk)

    def attr(self, name):
        """A colour attribute as (rgb vector, x, y, z, w)."""
        n = self._cached('attr:' + name, lambda: self.new('ShaderNodeAttribute', attribute_type='GEOMETRY',
                                                           attribute_name=name))

        class A:
            pass
        a = A()
        a.rgb = V(self, n.outputs['Color'], 'v')
        a.vec = V(self, n.outputs['Vector'], 'v')
        a.x, a.y, a.z = self.comp(a.rgb, 0), self.comp(a.rgb, 1), self.comp(a.rgb, 2)
        a.w = V(self, n.outputs['Alpha'], 'f')
        a.fac = V(self, n.outputs['Fac'], 'f')
        return a

    def uv(self, name='UVMap'):
        n = self._cached('uv:' + name, lambda: self.new('ShaderNodeUVMap', uv_map=name))
        return V(self, n.outputs['UV'], 'v')

    def tex(self, img, u, v, interpolation='Linear', extension='REPEAT'):
        """Sample an image at (u, v) (Blender's convention: v = 0 is the image's bottom row): (rgb, alpha)."""
        n = self.new('ShaderNodeTexImage', interpolation=interpolation, extension=extension)
        n.image = img
        self.feed(self.comb(u, v, 0.0), n.inputs['Vector'])
        return V(self, n.outputs['Color'], 'v'), V(self, n.outputs['Alpha'], 'f')

    def group(self, tree):
        def mk():
            g = self.new('ShaderNodeGroup')
            g.node_tree = tree
            return g
        return self._cached('group:' + tree.name, mk)

    def U(self, name):
        """A uniform of the kit (citykit.js's U.*): an output of the uniforms node group."""
        g = self.group(self.K.U.tree)
        s = g.outputs[name]
        return V(self, s, 'v' if s.type == 'VECTOR' else 'f')

    def fog(self):
        """(factor, colour) of the city's haze and cloud deck at this shading point."""
        g = self.group(self.K.fog_group())
        return V(self, g.outputs['factor'], 'f'), V(self, g.outputs['color'], 'v')

    def lm(self, xz3, level=None):
        """lmSample: the street light map at three-space xz (a vector (x, z, 0)), at mip level 0 / 1 / 2 / 4 / 5."""
        return lm_sample(self.K, self, xz3, level)


def tsl_helpers(nb):
    """citykit.js's tslHelpers(T) for a node builder: {'hash12' (as the film rendered it, or Dave Hoskins' hash
    without sine with the kit's hash='hoskins': see NB.hash12), 'hash11', 'pulse' (the box-filtered periodic pulse:
    the mean of [a <= fract(x) <= b] over a pixel footprint w)}, written as nodes."""
    return {'hash12': nb.hash12, 'hash11': nb.hash11, 'pulse': nb.pulse}


# ------------------------------------------------------------------------------------------------ uniforms
U_FLOATS = [('time', 0.0), ('power', 1.0), ('win', 1.0), ('neon', 1.0), ('street', 1.0), ('rain', 1.0), ('cloud', 1.0),
            ('fog', 1.0), ('wet', 1.0), ('flash', 0.0), ('focal_gain', 1.0), ('focal_r', 230.0), ('flood', 1.0),
            ('crown', 1.0), ('cable', 1.0), ('column', 1.0), ('screens', 1.0), ('quiet', 1.0)]
U_VECTORS = {'focal_pos': ((0.0, 0.0, 3.0), ('x', 'y', 'z')),          # Blender axes (three's (0, 3, 0): the hole)
             'focal_col': ((0.80, 0.72, 0.62), ('r', 'g', 'b')),
             'cam_vel': ((0.0, 0.0, 0.0), ('x', 'y', 'z'))}           # Blender axes, m/s
U_ALIASES = {'focalPos': 'focal_pos', 'focalCol': 'focal_col', 'focalGain': 'focal_gain', 'focalR': 'focal_r',
             'camVel': 'cam_vel'}
PIX_DEFAULT = 2 * math.tan(math.radians(30)) / 1080       # radians per pixel at 60 degrees over 1080 rows


class Uniforms:
    """The kit's uniforms (citykit.js's K.U) as one node group of Value nodes, read by every material:

        U['power'] = 0.4                 # set
        U.key('power', frame=7400)       # key what is set now (LINEAR), or U.key('power', 7400, 0.4)
        U['focal_pos'] = (0, 0, 3)       # vectors in Blender axes (focal_pos, cam_vel) or colours (focal_col)
        U.drive(mod, '["Socket_2"]', 'time')    # a driver that reads a uniform (Geometry Nodes inputs)

    'pix' (radians per pixel, for the windows' footprint) is a driver on the active scene camera's vertical angle
    and the render height; it falls back to 60 degrees over 1080 rows when the scene has no camera. keyer: a
    function(target, data_path, frame=, interpolation=) every key goes through (the harness's ctx.key, set by a
    build given a ctx); None keys directly."""

    def __init__(self, tree):
        self.tree = tree
        self.keyer = None

    def _node(self, k):
        return self.tree.nodes['u_' + k]

    def names(self):
        return [n for n, _ in U_FLOATS] + list(U_VECTORS) + ['pix']

    def __getitem__(self, k):
        k = U_ALIASES.get(k, k)
        if k in U_VECTORS:
            return tuple(self._node(f'{k}_{c}').outputs[0].default_value for c in U_VECTORS[k][1])
        return self._node(k).outputs[0].default_value

    def __setitem__(self, k, v):
        k = U_ALIASES.get(k, k)
        if k in U_VECTORS:
            if isinstance(v, str):
                v = srgb_lin(v)
            for c, x in zip(U_VECTORS[k][1], v):
                self._node(f'{k}_{c}').outputs[0].default_value = float(x)
        else:
            self._node(k).outputs[0].default_value = float(v)

    def paths(self, k):
        """[(node tree, data path)] of a uniform's Value node(s), for ctx.key(tree, path)."""
        k = U_ALIASES.get(k, k)
        names = [f'{k}_{c}' for c in U_VECTORS[k][1]] if k in U_VECTORS else [k]
        return [(self.tree, f'nodes["u_{n}"].outputs[0].default_value') for n in names]

    def key(self, k, frame, value=None, interpolation='LINEAR'):
        if value is not None:
            self[k] = value
        for tree, path in self.paths(k):
            key_prop(tree, path, frame, interpolation, self.keyer)

    def drive(self, target, data_path, k, index=-1, scale=1.0):
        """A driver on target.data_path (a Geometry Nodes input, a light's energy ...) that reads uniform k."""
        k = U_ALIASES.get(k, k)
        name = f'{k}_{U_VECTORS[k][1][index]}' if k in U_VECTORS else k
        fc = target.driver_add(data_path, index) if index >= 0 else target.driver_add(data_path)
        d = fc.driver
        d.type = 'SCRIPTED'
        while d.variables:
            d.variables.remove(d.variables[0])
        var = d.variables.new()
        var.name = 'u'
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'NODETREE'
        var.targets[0].id = self.tree
        var.targets[0].data_path = f'nodes["u_{name}"].outputs[0].default_value'
        d.expression = 'u' if scale == 1.0 else f'u*{scale!r}'
        return fc


def key_prop(idb, path, frame, interpolation='LINEAR', keyer=None, index=-1):
    """Key idb.path at frame: through keyer (the harness's ctx.key, which logs the key and gives it its
    interpolation after the build) or directly, then the interpolation set on the inserted point (Python's
    keyframe_insert ignores the default-interpolation preference)."""
    if keyer is not None:
        keyer(idb, path, index=index, frame=frame, interpolation=interpolation)
    else:
        idb.keyframe_insert(path, index=index, frame=frame)
    _set_interp(idb, path, frame, interpolation)


def _set_interp(idb, path, frame, interpolation):
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return
    from bpy_extras import anim_utils
    try:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except (AttributeError, TypeError, RuntimeError):
        cb = None
    fcs = cb.fcurves if cb is not None else []
    for fc in fcs:
        if fc.data_path == path:
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 1e-3:
                    kp.interpolation = interpolation


def make_uniforms(name='uf_city_U', made=None):
    """The uniforms node group (outputs: every float uniform, focal_pos3 in three's axes, focal_col, cam_vel, pix).
    Each kit makes its own (uf_city_U, then uf_city_U.001 for a second set in the same file)."""
    tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    if made is not None:
        made.add(tree)
    out = tree.nodes.new('NodeGroupOutput')
    out.location = (900, 0)
    y = 0

    def value(nm, v):
        nonlocal y
        n = tree.nodes.new('ShaderNodeValue')
        n.name = n.label = 'u_' + nm
        n.outputs[0].default_value = v
        n.location = (0, y)
        y -= 90
        return n
    for nm, v in U_FLOATS:
        tree.interface.new_socket(nm, in_out='OUTPUT', socket_type='NodeSocketFloat')
        tree.links.new(value(nm, v).outputs[0], out.inputs[nm])
    for nm, (dv, comps) in U_VECTORS.items():
        nodes = [value(f'{nm}_{c}', d) for c, d in zip(comps, dv)]
        cmb = tree.nodes.new('ShaderNodeCombineXYZ')
        cmb.location = (300, y)
        if nm == 'focal_pos':              # three's axes for the materials' maths: (x, z, -y)
            tree.links.new(nodes[0].outputs[0], cmb.inputs[0])
            tree.links.new(nodes[2].outputs[0], cmb.inputs[1])
            neg = tree.nodes.new('ShaderNodeMath')
            neg.operation = 'MULTIPLY'
            neg.inputs[1].default_value = -1.0
            neg.location = (150, y)
            tree.links.new(nodes[1].outputs[0], neg.inputs[0])
            tree.links.new(neg.outputs[0], cmb.inputs[2])
            sock = 'focal_pos3'
        else:
            for i in range(3):
                tree.links.new(nodes[i].outputs[0], cmb.inputs[i])
            sock = nm
        tree.interface.new_socket(sock, in_out='OUTPUT', socket_type='NodeSocketVector')
        tree.links.new(cmb.outputs[0], out.inputs[sock])
    pix = value('pix', PIX_DEFAULT)
    tree.interface.new_socket('pix', in_out='OUTPUT', socket_type='NodeSocketFloat')
    tree.links.new(pix.outputs[0], out.inputs['pix'])
    _drive_pix(pix)
    return Uniforms(tree)


def _drive_pix(node):
    """pix = 2 tan(angle_y / 2) / (rows): the active scene camera's radians per pixel (a simple expression: no
    Python needed to evaluate it when the .blend is opened)."""
    fc = node.outputs[0].driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    for nm, path in (('a', 'camera.data.angle_y'), ('h', 'render.resolution_y'), ('p', 'render.resolution_percentage')):
        var = d.variables.new()
        var.name = nm
        var.type = 'CONTEXT_PROP'
        t = var.targets[0]
        t.context_property = 'ACTIVE_SCENE'
        t.data_path = path
        t.use_fallback_value = True
        t.fallback_value = {'a': math.radians(60), 'h': 1080.0, 'p': 100.0}[nm]
    d.expression = '2*tan(a/2)/max(h*p/100, 1)'


# ------------------------------------------------------------------------------------------------ the kit context
class Kit:
    """The kit context K: U (Uniforms), tex (the five CC0 sets + noise + env), lm (the light map's levels), mat (the
    shared materials once made), made (every datablock), opts. city.py passes its kit to hole.py so both sets share
    one set of materials."""

    def __init__(self, opts):
        self.opts = dict(opts or {})
        self.made = Made()
        self.U = None
        self.tex = {}
        self.lm = {}
        self.light_map = None
        self.mat = None
        self._fog = None
        self.world = None

    def fog_group(self):
        if self._fog is None:
            self._fog = make_fog_nodes(self)
        return self._fog

    @property
    def fog(self):
        return {'group': self.fog_group()}


LM_LEVELS = (0, 1, 2, 4, 5)


def make_kit(opts=None):
    """citykit.js's makeKit: loads the five CC0 sets, makes the noise and the night environment, the uniforms, the
    (still black) light map images and the fog group. Returns the Kit. opts: hash ('film', the default: hash12 as the
    film rendered it; 'hoskins': as citykit.js reads, see NB.hash12), light_map_size (2048), uniforms_name, aovs (True:
    the facades also write the AOV 'uf_window_fw' = (cells per pixel along u, along v, panes resolved), for checks),
    env_intensity."""
    K = Kit(opts)
    if K.opts.get('hash') not in (None,) + HASH_MODES:
        raise ValueError(f"make_kit: hash is one of {HASH_MODES}, not {K.opts.get('hash')!r}")
    register_fonts()
    K.U = make_uniforms(K.opts.get('uniforms_name', 'uf_city_U'), K.made)
    K.tex = {'concrete': load_pbr('Concrete031', made=K.made), 'metal': load_pbr('MetalPlates013', made=K.made),
             'asphalt': load_pbr('Asphalt025C', made=K.made), 'paving': load_pbr('PavingStones128', made=K.made),
             'marble': load_pbr('Marble016', made=K.made),
             'noise': noise_texture(made=K.made), 'env': night_env_texture(made=K.made)}
    N = int(K.opts.get('light_map_size', 2048))
    for lv in LM_LEVELS:
        n = max(8, N >> lv)
        K.lm[lv] = image_from_rgba(f'uf_lightmap_l{lv}', np.zeros((n, n, 4), np.uint8), colorspace='sRGB',
                                   made=K.made, pack=False)
    K.light_map = K.lm[0]
    return K


# ------------------------------------------------------------------------------------------------ the light map
class LightMapCanvas:
    """The street light map's canvas: a top-down N x N plan of |x|,|z| <= LM_R, painted with 'lighter' (additive)
    soft pools in the canvas's 8-bit sRGB space, as citykit.js painted its 2048^2 canvas."""

    def __init__(self, N=2048):
        self.N = int(N)
        self.buf = np.zeros((self.N, self.N, 3), np.float64)       # premultiplied sRGB, 0..1, summed

    def pool(self, px, py, R, rgb, a):
        """A radial gradient (stops 0: a, 0.35: a * 0.45, 1: 0) filling the square [px - R, px + R]^2."""
        x0, x1 = max(0, int(math.floor(px - R))), min(self.N, int(math.ceil(px + R)))
        y0, y1 = max(0, int(math.floor(py - R))), min(self.N, int(math.ceil(py + R)))
        if x1 <= x0 or y1 <= y0:
            return
        xs = np.arange(x0, x1) + 0.5
        ys = np.arange(y0, y1) + 0.5
        d = np.hypot(xs[None, :] - px, ys[:, None] - py) / R
        al = np.interp(np.clip(d, 0, 1), [0.0, 0.35, 1.0], [a, a * 0.45, 0.0])
        # the fillRect's own coverage at its fractional edges
        cx = np.clip(np.minimum(np.arange(x0, x1) + 1, px + R) - np.maximum(np.arange(x0, x1), px - R), 0, 1)
        cy = np.clip(np.minimum(np.arange(y0, y1) + 1, py + R) - np.maximum(np.arange(y0, y1), py - R), 0, 1)
        al = al * cy[:, None] * cx[None, :]
        c = np.asarray(rgb, np.float64) / 255.0
        self.buf[y0:y1, x0:x1] += al[..., None] * c[None, None, :]

    def rgba8(self):
        out = np.empty((self.N, self.N, 4), np.uint8)
        out[..., :3] = np.floor(np.clip(self.buf, 0, 1) * 255 + 0.5)
        out[..., 3] = 255
        return out


def lm_pool(ctx, to_px, s, x, z, r, color, a=1.0):
    """Paint a soft pool of light (radius in metres) into the light map (three-space x, z)."""
    px, py = to_px(x, z)
    R = max(1.5, r * s)
    ctx.pool(px, py, R, hex_rgb(color), a)


def _srgb_decode(v):
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def _srgb_encode(v):
    v = np.clip(v, 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)


def paint_light_map(draws, N=2048):
    """The light map's canvas (no Blender needed): (N, N, 4) uint8, row 0 at three's z = -LM_R (the canvas top)."""
    ctx = LightMapCanvas(N)
    s = N / (2 * LM_R)

    def to_px(x, z):
        return ((x + LM_R) * s, (z + LM_R) * s)
    for d in draws:
        d(ctx, to_px, s)
    return ctx.rgba8()


def make_light_map(K, draws, N=None):
    """The street light map: draws are callables draw(ctx, to_px, s) painting with lm_pool (to_px(x, z) -> canvas
    pixels, s = pixels per metre). Fills K.lm's images: level 0 (the canvas) and the blurred levels 1, 2, 4, 5 that
    lmSample read with an explicit LOD (averaged in linear light, as the GPU builds mip maps). Returns level 0."""
    N = int(N or K.opts.get('light_map_size', 2048))
    base = paint_light_map(draws, N)
    K.lm_canvas = base
    lin = _srgb_decode(base[..., :3].astype(np.float64) / 255.0)
    for lv in LM_LEVELS:
        n = max(8, N >> lv)
        if lv == 0:
            px = base
        else:
            f = N // n
            m = lin.reshape(n, f, n, f, 3).mean(axis=(1, 3))
            px = np.empty((n, n, 4), np.uint8)
            px[..., :3] = np.floor(_srgb_encode(m) * 255 + 0.5)
            px[..., 3] = 255
        img = K.lm[lv]
        if img.size[0] != n:
            bpy.data.images.remove(img)
            img = K.lm[lv] = image_from_rgba(f'uf_lightmap_l{lv}', px, colorspace='sRGB', made=K.made, top_down=True)
        else:
            img.pixels.foreach_set(np.ascontiguousarray(px[::-1].astype(np.float32) / 255.0).ravel())
            img.update()
            img.pack()
    K.light_map = K.lm[0]
    return K.light_map


def lm_sample(K, nb, xz3, level=None):
    """The light map at three-space xz (TSL lmSample): it follows U.power as a whole (smoothstep(0, 0.75, power));
    the lamps, signs and windows themselves go out one by one. level: None (the GPU's own mips), 1, 2, 4, 5."""
    lv = 0 if level is None else int(round(level))
    lv = min(LM_LEVELS, key=lambda L: abs(L - lv))
    u = nb.add(nb.comp(xz3, 0), LM_R) / (2 * LM_R)
    v = nb.sub(1.0, nb.add(nb.comp(xz3, 1), LM_R) / (2 * LM_R))
    rgb, _ = nb.tex(K.lm[lv], u, v, interpolation='Linear', extension='EXTEND')
    return nb.mul(rgb, nb.smoothstep(0.0, 0.75, nb.U('power')))


# ------------------------------------------------------------------------------------------------ fog
def make_fog_nodes(K):
    """One height-graded haze (dense at the street, thinning upward) plus the low cloud deck as a band of thick fog,
    as the shader node group 'uf_fog' (outputs factor, color), read in three's axes from the shading point and the
    camera. Lit and basic materials mix toward the colour by the factor; additive ones fade by 1 - factor."""
    tree = bpy.data.node_groups.new('uf_fog', 'ShaderNodeTree')        # the kit's own (uf_fog.001 for a second kit)
    K.made.add(tree)
    tree.interface.new_socket('factor', in_out='OUTPUT', socket_type='NodeSocketFloat')
    tree.interface.new_socket('color', in_out='OUTPUT', socket_type='NodeSocketVector')
    nb = NB(tree, K)
    out = nb.new('NodeGroupOutput')
    Hh, RHO, H0 = 130.0, 0.0028, STREET_Y
    P, C = nb.pos3(), nb.cam3()
    d = nb.length(P - C)
    hc = nb.max(C.y, H0 - 6)
    hp = nb.max(P.y, H0 - 6)
    e1 = nb.exp(-(hc - H0) / Hh)
    e2 = nb.exp(-(hp - H0) / Hh)
    dh = hp - hc
    odH = nb.select(nb.step(0.5, nb.abs(dh)), (e1 - e2) * Hh / dh, (e1 + e2) * 0.5) * d * RHO

    def band(b0, b1):
        lo, hi = nb.min(hc, hp), nb.max(hc, hp)
        ov = nb.max(nb.min(hi, b1) - nb.max(lo, b0), 0.0)
        dh2 = nb.abs(hp - hc)
        inside = nb.smoothstep(b0 - 1, b0 + 1, hc) * nb.one_minus(nb.smoothstep(b1 - 1, b1 + 1, hc))
        return nb.select(nb.step(0.5, dh2), d * ov / nb.max(dh2, 0.5), d * inside)
    odC = band(CLOUD['skirt'], CLOUD['top']) * 0.021 + band(CLOUD['base'], CLOUD['skirt']) * 0.003
    od = odH * nb.U('fog') + odC * nb.U('cloud')
    factor = nb.clamp(nb.one_minus(nb.exp(-od)), 0.0, 1.0)
    # haze colour: warm sodium-violet near the street, cold violet-grey in and under the cloud deck; the deck is lit
    # from below (the street's light, blurred), so falling through, the city's plan glows through the murk
    low, mid, cloud = (0.020, 0.0145, 0.0195), (0.0155, 0.0135, 0.0215), (0.034, 0.030, 0.040)
    hpy, hcy = P.y, C.y
    h = nb.max(hpy, hcy * 0.6)
    c = nb.mix(low, mid, nb.smoothstep(30, 220, h))
    city = nb.lm(nb.xz(P), 4)
    glow = city * nb.smoothstep(150, 360, hcy) * 0.22
    color = nb.mix(c, cloud, nb.smoothstep(260, 400, h)) + glow + nb.mul((0.05, 0.06, 0.08), nb.U('flash'))
    nb.feed(factor, out.inputs['factor'])
    nb.feed(color, out.inputs['color'])
    return tree


FOG_TAG = 'uf_fogged'
_WRAP = 'uf_fog_wrap'                  # the name prefix of every node fog_material adds


def _clear_part(nt, sock, made, seen=()):
    """How see-through the shader feeding `sock` is (1 - three's alpha): a number, an output socket of nodes added
    to the material (appended to `made`), or None when a node group hides transparency inside it. A Transparent BSDF
    and a Holdout are clear, a Principled BSDF is clear by 1 - its Alpha, a Mix Shader mixes its sides by its factor,
    an Add Shader adds them; every other shader is opaque."""
    if not sock.is_linked:
        return 0.0
    n = sock.links[0].from_node
    if n in seen:
        return 0.0
    seen = tuple(seen) + (n,)
    if n.type == 'REROUTE':
        return _clear_part(nt, n.inputs[0], made, seen)
    if n.type in ('BSDF_TRANSPARENT', 'HOLDOUT'):
        return 1.0
    if n.type == 'BSDF_PRINCIPLED':
        a = n.inputs['Alpha']
        if not a.is_linked:
            return 1.0 - min(1.0, max(0.0, float(a.default_value)))
        m = nt.nodes.new('ShaderNodeMath')
        m.operation, m.use_clamp = 'SUBTRACT', True
        m.inputs[0].default_value = 1.0
        nt.links.new(a.links[0].from_socket, m.inputs[1])
        made.append(m)
        return m.outputs[0]
    if n.type in ('MIX_SHADER', 'ADD_SHADER'):
        sides = [s for s in n.inputs if s.type == 'SHADER']
        parts = [_clear_part(nt, s, made, seen) for s in sides]
        if any(p is None for p in parts):
            return None
        if all(isinstance(p, float) for p in parts) and (n.type == 'ADD_SHADER' or not n.inputs[0].is_linked):
            if n.type == 'ADD_SHADER':
                return min(1.0, parts[0] + parts[1])
            f = min(1.0, max(0.0, float(n.inputs[0].default_value)))
            return parts[0] * (1.0 - f) + parts[1] * f
        if n.type == 'ADD_SHADER':
            m = nt.nodes.new('ShaderNodeMath')
            m.operation, m.use_clamp = 'ADD', True
            ins = (m.inputs[0], m.inputs[1])
        else:
            m = nt.nodes.new('ShaderNodeMix')
            m.data_type, m.clamp_factor = 'FLOAT', True
            fac, mf = n.inputs[0], NB._sock(m.inputs, 'Factor_Float')
            if fac.is_linked:
                nt.links.new(fac.links[0].from_socket, mf)
            else:
                mf.default_value = fac.default_value
            ins = (NB._sock(m.inputs, 'A_Float'), NB._sock(m.inputs, 'B_Float'))
        for p, s in zip(parts, ins):
            if isinstance(p, float):
                s.default_value = p
            else:
                nt.links.new(p, s)
        made.append(m)
        return m.outputs[0] if n.type == 'ADD_SHADER' else NB._sock(m.outputs, 'Result_Float')
    if n.type == 'GROUP' and n.node_tree is not None and any(
            m.type in ('BSDF_TRANSPARENT', 'HOLDOUT') or (m.type == 'BSDF_PRINCIPLED' and (
                m.inputs['Alpha'].is_linked or m.inputs['Alpha'].default_value < 1.0)) for m in n.node_tree.nodes):
        return None
    return 0.0


def _render_output(mat):
    """(the Material Output EEVEE renders this material through, the group node holding it or None). An active
    output for EEVEE wins over one for every engine, and a node group of the material may carry it: the VRM add-on's
    MToon output group renders a VRM's MToon materials through its own EEVEE output, past the material's own."""
    nt = mat.node_tree
    own = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL']
    active = [n for n in own if n.is_active_output]
    for o in active:
        if o.target == 'EEVEE':
            return o, None
    for gn in nt.nodes:
        if gn.type == 'GROUP' and gn.node_tree is not None:
            for o in gn.node_tree.nodes:
                if o.type == 'OUTPUT_MATERIAL' and o.is_active_output and o.target == 'EEVEE':
                    return o, gn
    for o in active:
        if o.target == 'ALL':
            return o, None
    return ((active or own)[0], None) if own else (None, None)


def fog_material(K, mat, group=None):
    """Wrap a material that is not the set's own (a performer's, a prop's) in the set's haze, as three's scene fog
    fogged every material in the scene: in place and once, its surface S becomes
    Mix(factor, S, Mix(alpha, Transparent, Emission(color))), the haze's factor and colour from `group` (a shader node
    group with outputs factor and color; the city kit's uf_fog by default). alpha is the surface's own coverage (its
    Principled Alpha, its mixes with a Transparent BSDF or a Holdout), so a see-through material keeps its alpha and
    fogs only what it covers, as three fogged a fragment's colour and kept its alpha: a hair card, a decal, an
    alpha-cut leaf, a blended veil, and an additive glow that fades by 1 - factor. The surface wrapped is the one EEVEE
    renders (_render_output): for a VRM's MToon material, the add-on's MToon output group's own; that group is shared
    by every MToon material in the file, so the material gets a copy of it with the wrap inside, one copy per output
    group and haze, shared by the materials wrapped in that haze. Returns True when wrapped (False: no surface, already
    wrapped, or a node group in its surface hides a transparency of its own). unfog_material(mat) takes it out."""
    if mat is None or mat.node_tree is None or mat.get(FOG_TAG):
        return False
    haze = group if group is not None else K.fog_group()
    out, holder = _render_output(mat)
    if out is None or not out.inputs['Surface'].is_linked:
        return False
    if holder is None:
        if not _wrap_surface(mat.node_tree, out, haze):
            return False
    else:
        orig = holder.node_tree
        copy = next((g for g in bpy.data.node_groups if g.get(FOG_TAG) == orig.name
                     and g.get(FOG_TAG + '_haze') == haze.name), None)
        if copy is None:
            copy = orig.copy()
            copy.name = f'{orig.name} ({haze.name})'
            copy[FOG_TAG] = orig.name                                   # the group it is a fogged copy of
            copy[FOG_TAG + '_haze'] = haze.name
            if not _wrap_surface(copy, _render_output_in(copy), haze):
                bpy.data.node_groups.remove(copy)
                return False
        holder.node_tree = copy
    mat[FOG_TAG] = True
    return True


def _render_output_in(tree):
    return next(o for o in tree.nodes if o.type == 'OUTPUT_MATERIAL' and o.is_active_output and o.target == 'EEVEE')


def _wrap_surface(nt, out, haze):
    """fog_material's wrap at one Material Output of the node tree nt (a material's or a group's)."""
    surf = out.inputs['Surface']
    src = surf.links[0].from_socket
    made = []
    clear = _clear_part(nt, surf, made)
    if clear is None:
        for n in made:
            nt.nodes.remove(n)
        return False
    for i, n in enumerate(made):
        n.name = f'{_WRAP}_cover_{i}'
    g = nt.nodes.new('ShaderNodeGroup')
    g.node_tree = haze
    g.name = f'{_WRAP}_group'
    e = nt.nodes.new('ShaderNodeEmission')
    e.name = f'{_WRAP}_emit'
    nt.links.new(g.outputs['color'], e.inputs['Color'])
    fogged = e.outputs[0]
    extra = []
    if not (isinstance(clear, float) and clear <= 0.0):
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')        # the haze covers only what the surface covers
        tr.name = f'{_WRAP}_clear'
        cov = nt.nodes.new('ShaderNodeMixShader')
        cov.name = f'{_WRAP}_alpha'
        if isinstance(clear, float):
            cov.inputs[0].default_value = 1.0 - clear
        else:
            inv = nt.nodes.new('ShaderNodeMath')
            inv.operation, inv.use_clamp = 'SUBTRACT', True
            inv.name = f'{_WRAP}_cover'
            inv.inputs[0].default_value = 1.0
            nt.links.new(clear, inv.inputs[1])
            nt.links.new(inv.outputs[0], cov.inputs[0])
            extra.append(inv)
        nt.links.new(tr.outputs[0], cov.inputs[1])
        nt.links.new(e.outputs[0], cov.inputs[2])
        fogged = cov.outputs[0]
        extra += [tr, cov]
    mx = nt.nodes.new('ShaderNodeMixShader')
    mx.name = f'{_WRAP}_mix'
    nt.links.new(g.outputs['factor'], mx.inputs[0])
    nt.links.new(src, mx.inputs[1])
    nt.links.new(fogged, mx.inputs[2])
    nt.links.new(mx.outputs[0], surf)
    x, y = out.location
    for i, n in enumerate(made + extra + [g, e, mx]):
        n.location = (x - 420 + 70 * (i % 6), y - 260 - 60 * (i // 6) - 30 * i)
    return True


def _fogged_copy_of(mat):
    """(the group node, the fogged copy it uses) when fog_material wrapped this material inside a copy of its output
    group, else (None, None)."""
    for gn in mat.node_tree.nodes:
        if gn.type == 'GROUP' and gn.node_tree is not None and gn.node_tree.get(FOG_TAG):
            return gn, gn.node_tree
    return None, None


def unfog_material(mat):
    """Take fog_material's wrap out again: the surface back on the output, or the material's own output group back in
    place of its fogged copy (the copy goes once no material uses it)."""
    if mat is None or not mat.get(FOG_TAG):
        return False
    nt = mat.node_tree
    gn, copy = _fogged_copy_of(mat)
    if gn is not None:
        orig = bpy.data.node_groups.get(copy[FOG_TAG])
        if orig is not None:
            gn.node_tree = orig
            if copy.users == 0:
                bpy.data.node_groups.remove(copy)
    mx = nt.nodes.get(f'{_WRAP}_mix')
    if mx is not None and mx.inputs[1].is_linked:
        src = mx.inputs[1].links[0].from_socket
        for o in [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL']:
            if any(l.from_node == mx for l in o.inputs['Surface'].links):
                nt.links.new(src, o.inputs['Surface'])
    for n in [n for n in nt.nodes if n.name.startswith(_WRAP)]:
        nt.nodes.remove(n)
    del mat[FOG_TAG]
    return True


def unfog_group(group):
    """unfog_material on every material wrapped in this haze group: a set's dispose calls it before the group goes,
    so your own objects keep their own surfaces. Returns how many."""
    n = 0
    for m in list(bpy.data.materials):
        if m.get(FOG_TAG) and m.node_tree is not None:
            _gn, copy = _fogged_copy_of(m)
            g = (copy or m.node_tree).nodes.get(f'{_WRAP}_group')
            if g is not None and g.node_tree == group:
                n += bool(unfog_material(m))
    return n


def fog_objects(K, objects, group=None):
    """fog_material on every material of these objects (meshes; others are skipped), see-through ones included.
    group: the haze's node group (the kit's uf_fog by default). Returns (wrapped, left: materials no wrap could
    reach, a node group hiding its transparency)."""
    done, left = 0, 0
    seen = set()
    for ob in objects:
        for slot in getattr(ob, 'material_slots', []):
            m = slot.material
            if m is None or m.name in seen:
                continue
            seen.add(m.name)
            if fog_material(K, m, group):
                done += 1
            elif not m.get(FOG_TAG):
                left += 1
    return done, left


# ------------------------------------------------------------------------------------------------ material outputs
def new_material(name, K=None, made=None):
    """A new material and its node builder; the name gets Blender's .001 when another set holds it (never replaced)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    if made is not None:
        made.add(m)
    elif K is not None:
        K.made.add(m)
    return m, NB(m.node_tree, K)


ROUGHNESS_FLOOR = 0.0525               # three's getRoughness: max(roughness, 0.0525) (the base mip of a 256 cube map)


def out_lit(nb, *, color, rough, metal=0.0, normal=None, emission=None, ior=None, fog=True):
    """A lit (MeshStandardNodeMaterial) output: Principled BSDF with emission, mixed toward the fog colour by its
    factor (three's fog on the final colour). Roughness is floored at 0.0525 as three's lighting model floors it (the
    puddles' 0.035 would otherwise focus a light's glint to five times three's peak)."""
    p = nb.new('ShaderNodeBsdfPrincipled')
    nb.feed(color, p.inputs['Base Color'])
    nb.feed(nb.max(rough, ROUGHNESS_FLOOR), p.inputs['Roughness'])
    nb.feed(metal, p.inputs['Metallic'])
    if ior is not None:
        nb.feed(ior, p.inputs['IOR'])
    if normal is not None:
        nb.links.new(normal, p.inputs['Normal'])
    if emission is not None:
        nb.feed(emission, p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = 1.0
    sh = p.outputs[0]
    if fog:
        f, fc = nb.fog()
        e = nb.new('ShaderNodeEmission')
        nb.feed(fc, e.inputs['Color'])
        e.inputs['Strength'].default_value = 1.0
        mx = nb.new('ShaderNodeMixShader')
        nb.feed(f, mx.inputs[0])
        nb.links.new(sh, mx.inputs[1])
        nb.links.new(e.outputs[0], mx.inputs[2])
        sh = mx.outputs[0]
    o = nb.new('ShaderNodeOutputMaterial')
    nb.links.new(sh, o.inputs['Surface'])
    return p


def out_basic(nb, color, fog=True):
    """An unlit (MeshBasicNodeMaterial) opaque output: emission of the colour, fogged."""
    if fog:
        f, fc = nb.fog()
        color = nb.mix(color, fc, f)
    e = nb.new('ShaderNodeEmission')
    nb.feed(color, e.inputs['Color'])
    e.inputs['Strength'].default_value = 1.0
    o = nb.new('ShaderNodeOutputMaterial')
    nb.links.new(e.outputs[0], o.inputs['Surface'])


def out_additive(nb, color):
    """AdditiveBlending: emission over a fully transparent surface (BLENDED, no depth write)."""
    e = nb.new('ShaderNodeEmission')
    nb.feed(color, e.inputs['Color'])
    e.inputs['Strength'].default_value = 1.0
    t = nb.new('ShaderNodeBsdfTransparent')
    a = nb.new('ShaderNodeAddShader')
    nb.links.new(e.outputs[0], a.inputs[0])
    nb.links.new(t.outputs[0], a.inputs[1])
    o = nb.new('ShaderNodeOutputMaterial')
    nb.links.new(a.outputs[0], o.inputs['Surface'])


def out_alpha(nb, color, alpha):
    """Normal alpha blending of an unlit colour."""
    e = nb.new('ShaderNodeEmission')
    nb.feed(color, e.inputs['Color'])
    e.inputs['Strength'].default_value = 1.0
    t = nb.new('ShaderNodeBsdfTransparent')
    mx = nb.new('ShaderNodeMixShader')
    nb.feed(alpha, mx.inputs[0])
    nb.links.new(t.outputs[0], mx.inputs[1])
    nb.links.new(e.outputs[0], mx.inputs[2])
    o = nb.new('ShaderNodeOutputMaterial')
    nb.links.new(mx.outputs[0], o.inputs['Surface'])


def _blended(m, backface_cull=False):
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = backface_cull
    try:
        m.use_transparency_overlap = True
    except AttributeError:
        pass


def normal_map(nb, img_rgb, strength):
    n = nb.new('ShaderNodeNormalMap', space='TANGENT', uv_map='UVMap')
    nb.feed(strength, n.inputs['Strength'])
    nb.feed(img_rgb, n.inputs['Color'])
    return n.outputs['Normal']


def ior_from_reflectivity(nb, R):
    """The G-buffer reflectivity the engine's SSR read, as a dielectric's F0 = R: IOR = (1 + sqrt R) / (1 - sqrt R)."""
    s = nb.sqrt(nb.clamp(R, 0.0, 0.98))
    return (1.0 + s) / nb.max(1.0 - s, 0.01)


# ------------------------------------------------------------------------------------------------ facade material
def pixel_steps(nb):
    """Where the next pixel's view ray meets this face's plane: the world-space step of the shading point for one
    pixel along the image's x and y, (dx, dy), as the GPU's quad derivatives (dFdx, dFdy) of the world position saw it
    on a plane. A step of one pixel turns the ray by U.pix (image-plane units at unit depth) along the camera's right
    (or up) axis e; on a plane of normal N, hit at depth s along the view axis by the unit ray w, the hit moves by
    s pix (e - (N.e) / (N.w) w) (|N.w| kept above 0.02 at grazing angles)."""
    def mk():
        cam = nb._cached('cam', lambda: nb.new('ShaderNodeCameraData'))
        s = V(nb, cam.outputs['View Z Depth'], 'f')
        k = s * nb.U('pix')
        w = nb.mul(nb.geo('Incoming'), -1.0)
        Nn = nb.geo('True Normal')
        nw = nb.dot(Nn, w)
        nw = nb.math('SIGN', nw) * nb.max(nb.abs(nw), 0.02)
        out = []
        for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
            vt = nb.new('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='CAMERA', convert_to='WORLD')
            vt.inputs[0].default_value = axis
            e = V(nb, vt.outputs[0], 'v')
            out.append((e - w * (nb.dot(Nn, e) / nw)) * k)
        return tuple(out)
    return nb._cached('pixel_steps', mk)


def pixel_footprint(nb, cell_u, cell_v):
    """fwidth of the facade's cell grid (cells per pixel along u and v): |du/dx| + |du/dy| over the cell, as the GPU
    measured it, from the pixel steps on the face's plane (pixel_steps) and the UV's directions on it, the UV tangent
    and bitangent (the facade's UVs are metres)."""
    dx, dy = pixel_steps(nb)
    tg = nb._cached('tangent', lambda: nb.new('ShaderNodeTangent', direction_type='UV_MAP', uv_map='UVMap'))
    T = V(nb, tg.outputs['Tangent'], 'v')
    B = nb.cross(nb.geo('True Normal'), T)
    fu = nb.abs(nb.dot(T, dx)) + nb.abs(nb.dot(T, dy))
    fv = nb.abs(nb.dot(B, dx)) + nb.abs(nb.dot(B, dy))
    return fu / cell_u, fv / cell_v


def facade_material(K, family='concrete', name=None):
    """Concrete or metal towers: the AmbientCG albedo darkened and tinted per building, wet streaks down from the
    sills, procedural box-filtered windows (each its own lit state, colour, blinds, curtains, a place in the
    turn-down; far away they converge to their average), the street's light from below, aviation beacons, lit lift
    cars, Crali's focal light, per-tower floodlights and lit crowns."""
    metal = family == 'metal'
    P = K.tex['metal' if metal else 'concrete']
    m, nb = new_material(name or 'uf_facade_' + family, K)
    m.use_backface_culling = True                  # three's FrontSide (the buffers are wound as the engine's)
    aT, aM, aW = nb.attr('aT'), nb.attr('aM'), nb.attr('aW')
    fuv = nb.uv()
    fu, fv = fuv.x, fuv.y
    TILE = 2.4 if metal else 3.6
    tu, tv = fu / TILE + aT.x * 17.0, fv / TILE + aT.x * 5.0
    kind = aM.x
    is_roof = nb.step(0.5, kind) * nb.step(kind, 1.5)
    # ---- windows
    csx, csy = nb.max(aM.z, 0.5), nb.max(aM.y, 0.5)
    gx, gy = fu / csx, fv / csy
    cx, cy = nb.floor(gx), nb.floor(gy)
    fx, fy = nb.fract(gx), nb.fract(gy)
    fwx, fwy = pixel_footprint(nb, csx, csy)
    fwx, fwy = nb.max(fwx, 1e-4), nb.max(fwy, 1e-4)
    px = nb.pulse(gx, aW.x, nb.one_minus(aW.x), fwx)
    py = nb.pulse(gy, aW.y, nb.max(aW.z, aW.y), fwy)
    seed = aT.x
    h1 = nb.hash12(cx + seed * 113.1, cy + seed * 71.7)
    hf = nb.hash12(cy * 1.31 + seed * 9.7, seed * 57.3)
    litP = aT.y * (hf * 1.25 + 0.35)
    lit = nb.step(h1, litP)
    hp = nb.hash12(cy + seed * 31.7 + 7.1, cx + seed * 31.7 + 7.1)
    power = nb.U('power')
    on = nb.smoothstep(hp - 0.015, hp + 0.015, power)
    hc = nb.hash12(cx + seed * 19.1, cy + 3.3)
    warm, cool, fluo = (1.0, 0.60, 0.28), (0.62, 0.80, 1.0), (0.74, 1.0, 0.84)
    dimA = (0.55, 0.26, 0.10)
    base = nb.mix(nb.mix(nb.mix(cool, warm, nb.step(hc, aT.z)), fluo, nb.step(0.86, hc) * nb.step(hc, 0.93)), dimA,
                  nb.step(0.93, hc) * nb.step(hc, 0.97))
    acc = nb.step(0.972, nb.hash12(cx + 17.7, cy + seed * 5.1))
    neonC = nb.mix((0.16, 0.9, 1.0), (1.0, 0.31, 0.85), nb.step(0.5, nb.hash11(h1 * 91.0)))
    col = nb.mix(base, neonC * 1.5, acc * aT.w)
    inten = nb.hash12(cx + 41.3, cy + 41.3) * 0.9 + 0.4
    wy = nb.clamp((fy - aW.y) / nb.max(aW.z - aW.y, 1e-3), 0.0, 1.0)
    ceil = nb.smoothstep(0.35, 1.0, wy) * 0.5 + 0.65
    blinds = nb.mix(1.0, nb.step(0.42, nb.fract(wy * 9.0)) * 0.45 + 0.55, nb.step(0.7, nb.fract(h1 * 3.7)))
    flick = nb.one_minus(nb.step(0.985, nb.hash11(nb.floor(nb.U('time') * 9.0) + h1 * 311.0)) * nb.step(0.93, hc) * 0.6)
    # a room behind the glass: curtains drawn from one side, the dark band of furniture below the sill line
    wx = nb.clamp((fx - aW.x) / nb.max(nb.one_minus(aW.x * 2.0), 1e-3), 0.0, 1.0)
    hcur = nb.hash12(cx + 5.3, cy + seed * 13.0)
    curtain = nb.mix(1.0, nb.smoothstep(hcur * 0.6, hcur * 0.6 + 0.08,
                                        nb.mix(wx, nb.one_minus(wx), nb.step(0.5, nb.fract(hcur * 7.0)))) * 0.8 + 0.2,
                     nb.step(0.55, hcur))
    furn = nb.mix(0.45, 1.0, nb.smoothstep(0.18, 0.34, wy + nb.hash11(hcur * 17.0) * 0.08))
    # the window's own frame, a mullion and a transom (resolved only where a window is big on screen)
    pxW = fwx / nb.max(nb.one_minus(aW.x * 2.0), 0.05)
    pxH = fwy / nb.max(aW.z - aW.y, 0.05)
    lineX = nb.max(pxW * 1.2, 0.025)
    lineY = nb.max(pxH * 1.2, 0.022)
    edge = nb.smoothstep(lineX, lineX * 2.0, nb.min(wx, nb.one_minus(wx))) * \
        nb.smoothstep(lineY, lineY * 2.0, nb.min(wy, nb.one_minus(wy)))
    hm = nb.hash11(h1 * 53.0)
    mull = nb.mix(1.0, nb.smoothstep(lineX * 0.5, lineX, nb.abs(wx - 0.5)), nb.step(0.35, hm))
    trans = nb.mix(1.0, nb.smoothstep(lineY * 0.5, lineY, nb.abs(wy - 0.74)), nb.step(0.55, hm))
    resolve = nb.one_minus(nb.smoothstep(0.035, 0.09, nb.max(pxW, pxH)))
    panes = nb.mix(1.0, edge * mull * trans * 0.85 + 0.15, resolve)
    if K.opts.get('aovs'):                         # the footprint the windows filter by, for checks against the truth
        aov = nb.new('ShaderNodeOutputAOV')
        aov.aov_name = 'uf_window_fw'
        nb.feed(nb.comb(fwx, fwy, resolve), aov.inputs['Color'])
    near = col * (inten * ceil * blinds * curtain * furn * panes * lit * on * flick * 0.8)
    avg = nb.mix(cool, warm, aT.z) * (aT.y * 0.62 * power)
    far = nb.smoothstep(0.25, 0.85, nb.max(fwx, fwy))
    win_mask = px * py * nb.one_minus(is_roof)
    win_emis = nb.mix(near, avg, far) * (win_mask * nb.U('win') * 0.95)
    # ---- the wall: texture albedo darkened and tinted per building, wet streaks running down from the sills
    tsel = nb.hash11(seed * 77.0)
    tint = nb.mix(nb.mix((0.17, 0.205, 0.215), (0.205, 0.18, 0.165), nb.step(0.45, tsel)), (0.12, 0.125, 0.14),
                  nb.step(0.8, tsel))
    alb = nb.tex(P['map'], tu, tv)[0] * tint * (1.15 if metal else 1.0)
    streak = nb.tex(K.tex['noise'], fu * 0.31 + seed * 3.1, fv * 0.012)[0].x
    wetS = nb.smoothstep(0.52, 0.74, streak) * nb.U('wet')
    roof = nb.mix(alb * 0.7, alb * 0.45, nb.tex(K.tex['noise'], fu * 0.05, fv * 0.05)[0].y)
    wall_alb = nb.mix(alb * nb.one_minus(wetS * 0.35), roof, is_roof)
    glass = (0.012, 0.016, 0.02)
    color = nb.mix(wall_alb, glass, win_mask)
    rTex = nb.tex(P['roughness_map'], tu, tv)[0].x
    rough = nb.mix(nb.clamp(rTex * 0.78 - wetS * 0.35, 0.12, 1.0), 0.07, win_mask)
    metalness = nb.mix(0.55 if metal else 0.0, 0.0, win_mask)
    nrm = normal_map(nb, nb.tex(P['normal_map'], tu, tv)[0], nb.one_minus(win_mask) * 0.9)
    # ---- light from below: the street's own light map, sampled just in front of the face, fading with height
    P3, N3 = nb.pos3(), nb.nrm3()
    lmuv = nb.xz(P3) + nb.xz(N3) * 5.0
    street = nb.lm(lmuv, 1)
    hgt = nb.max(P3.y - STREET_Y, 0.0)
    below = street * (nb.exp(-hgt / 24.0) * nb.U('street') * nb.one_minus(is_roof))
    # ---- frame kinds: aviation beacons (4) blink red; elevator shafts (5) carry a moving lit car
    time = nb.U('time')
    is_beacon = nb.step(3.5, kind) * nb.step(kind, 4.5)
    blink = nb.step(nb.fract(time * 0.5 + seed * 7.0), 0.12)
    is_lift = nb.step(4.5, kind)
    car = nb.smoothstep(2.6, 0.0, nb.abs(fv - nb.fract(time * 0.018 * (nb.hash11(seed * 3.3) + 0.6) + seed) *
                                         nb.max(aM.w, 1.0)))
    beacon = nb.mul((1.0, 0.06, 0.05), 9.0 * blink * is_beacon * on)
    lift = nb.mul((1.0, 0.85, 0.6), 2.4 * car * is_lift * power)
    # ---- Crali's light: faces turned toward the focal point (the vanishing point / the hole) catch its light
    toF = nb.U('focal_pos3') - P3
    dF = nb.length(toF)
    lam = nb.max(nb.dot(N3, toF / nb.max(dF, 1.0)), 0.0)
    att = 1.0 / (1.0 + nb.pow(dF / nb.U('focal_r'), 2.0))
    focal = (wall_alb * 14.0 + 0.012) * nb.U('focal_col') * (lam * lam * att * nb.U('focal_gain'))
    # ---- per-tower floodlight: one face washed with colour from the street up
    is_wall = nb.one_minus(is_roof) * (nb.step(kind, 0.5) + nb.step(2.5, kind) * nb.step(kind, 3.5))
    pick = nb.floor(nb.hash11(seed * 13.1) * 4.0)
    flood_on = nb.step(0.5, nb.hash11(seed * 7.7)) * nb.step(nb.abs(aW.w - pick), 0.5)
    fh = nb.hash11(seed * 5.3)
    floodC = nb.mix(nb.mix((0.05, 0.62, 0.72), (0.85, 0.12, 0.62), nb.step(0.3, fh)),
                    nb.mix((1.0, 0.42, 0.10), (0.55, 0.66, 0.85), nb.step(0.82, fh)), nb.step(0.55, fh))
    hfl = nb.hash11(seed * 2.9)
    flood = floodC * (flood_on * nb.exp(-nb.clamp(fv, 0.0, 400.0) / 38.0) * is_wall * nb.U('flood') *
                      nb.smoothstep(hfl - 0.02, hfl + 0.02, power))
    # ---- lit crowns: the top of the building washed in cold aluminium (some in colour)
    top = aM.w
    crown_on = nb.step(0.45, nb.hash11(seed * 17.3)) * nb.step(28.0, top)
    ch = nb.hash11(seed * 23.1)
    crownC = nb.mix((0.62, 0.70, 0.84), nb.mix((0.16, 0.85, 1.0), (1.0, 0.3, 0.8), nb.step(0.5, nb.hash11(seed * 4.1))),
                    nb.step(0.45, ch))
    hcr = nb.hash11(seed * 1.7)
    crown = crownC * (nb.smoothstep(top - 20.0, top - 1.0, fv) * crown_on * is_wall * nb.U('crown') *
                      nb.smoothstep(hcr - 0.02, hcr + 0.02, power))
    wash = wall_alb * (flood * 14.0 + crown * 7.0) + flood * 0.05 + crown * 0.035
    emissive = win_emis + wall_alb * below * 2.2 + beacon + lift + focal + wash
    out_lit(nb, color=color, rough=rough, metal=metalness, normal=nrm, emission=emissive)
    return m


def frame_material(K, name='uf_frame'):
    """Dark painted structure: fins, lift shafts, bridges, sign backings, roof plant (no windows): the metal facade
    material, same attributes."""
    return facade_material(K, 'metal', name)


def strip_material(K, name='uf_strips'):
    """Emissive neon strips (opaque, both sides): aT = (r, g, b, powerHash), aM = (pulseMode, gain, speed, phase).
    pulseMode 1 sends bright pulses along the strip's v (uv.y = metres along it) toward v = 0: toward the hole."""
    m, nb = new_material(name, K)
    aT, aM = nb.attr('aT'), nb.attr('aM')
    fv = nb.uv().y
    on = nb.smoothstep(aT.w - 0.015, aT.w + 0.015, nb.U('power'))
    ph = nb.fract(fv / 18.0 + nb.U('time') * aM.z + aM.w)
    pulse = nb.mix(1.0, 0.35 + nb.exp(ph * -9.0) * 2.6, nb.step(0.5, aM.x))
    out_basic(nb, aT.rgb * (aM.y * pulse * on * nb.U('neon')))
    return m


# ------------------------------------------------------------------------------------------------ ground
def ground_material(K, name='uf_ground'):
    """The city floor at STREET_Y: asphalt with procedural lane paint (radial avenues + ring roads), puddles that
    mirror the neon (their reflectivity drives the IOR), rain rings on the water, and the light map's lamp pools."""
    m, nb = new_material(name, K)
    m.use_backface_culling = True
    P3 = nb.pos3()
    xz = nb.xz(P3)
    x, z = P3.x, P3.z
    tu, tv = x / 3.2, z / 3.2
    alb = nb.tex(K.tex['asphalt']['map'], tu, tv)[0] * (0.42, 0.42, 0.45)
    n1 = nb.tex(K.tex['noise'], x / 41.0 + 0.13, z / 41.0 + 0.13)[0].x
    n2 = nb.tex(K.tex['noise'], x / 7.3, z / 7.3)[0].y
    puddle = nb.smoothstep(0.54, 0.62, n1 * 0.7 + n2 * 0.3) * nb.U('wet')
    # ---- lane paint in polar coordinates
    r = nb.length(xz)
    th = nb.atan2(z, x)
    PI = math.pi
    dM = r * nb.abs(nb.sin(nb.mod(th - PI / 4, PI / 2) - PI / 4))
    dS2 = r * nb.abs(nb.sin(nb.mod(th + PI / 4, PI / 2) - PI / 4))
    sec_on = nb.step(SECOND_START + 9, r)
    dAv = nb.min(dM, nb.mix(1e4, dS2, sec_on))
    dash = nb.step(0.45, nb.fract(r / 7.0))
    # fwidth(dAv) ~ metres per pixel on the ground: the footprint of the view ray on a horizontal plane
    mpp = nb.view_distance() * nb.U('pix') / nb.max(nb.abs(nb.geo('Incoming').z), 0.05)
    fwA = nb.max(mpp, 0.02)

    def line_at(dd, c, w):
        return nb.one_minus(nb.smoothstep(w, w + fwA * 1.5, nb.abs(dd - c)))
    av_lines = line_at(dAv, 0.0, 0.12) + line_at(dAv, 0.4, 0.12) + line_at(dAv, 5.5, 0.08) * dash + line_at(dAv, 10.6, 0.12)
    on_av = nb.step(dAv, AVENUE_W / 2)
    dR = nb.abs(r - RINGS[0]['r'])
    for g in RINGS[1:]:
        dR = nb.min(dR, nb.abs(r - g['r']))
    dR = nb.min(dR, nb.abs(r - 40.0))
    dashR = nb.step(0.45, nb.fract(r * th / 7.0))
    fwR = nb.max(mpp, 0.02)

    def line_r(c, w):
        return nb.one_minus(nb.smoothstep(w, fwR * 1.5 + w, nb.abs(dR - c)))
    ring_lines = (line_r(0.0, 0.1) + line_r(4.3, 0.07) * dashR) * nb.one_minus(nb.step(dAv, AVENUE_W / 2))
    wear = nb.smoothstep(0.25, 0.6, nb.tex(K.tex['noise'], x / 3.0, z / 3.0)[0].z)
    paint = nb.clamp(av_lines * on_av + ring_lines, 0.0, 1.0) * wear
    albP = nb.mix(alb, (0.30, 0.30, 0.29), paint * 0.85)
    albW = nb.mix(albP, albP * 0.35, puddle)
    rTex = nb.tex(K.tex['asphalt']['roughness_map'], tu, tv)[0].x
    rough = nb.mix(nb.clamp(rTex * 0.62, 0.25, 0.9), 0.035, puddle)
    rough_out = nb.mix(rough, 0.45, paint)
    # rain rings on the water: two layers of expanding ripples (a tangent-space nudge to the normal map)
    time = nb.U('time')

    def ripple(scale, rate, salt):
        qx, qz = x / scale, z / scale
        ccx, ccz = nb.floor(qx), nb.floor(qz)
        ffx, ffz = nb.fract(qx) - 0.5, nb.fract(qz) - 0.5
        ph = nb.fract(time * rate + nb.hash12(ccx + salt, ccz + salt))
        dd = nb.length(nb.comb(ffx, ffz, 0.0))
        ring = nb.smoothstep(0.06, 0.0, nb.abs(dd - ph * 0.48)) * nb.one_minus(ph)
        k = ring / nb.max(dd, 1e-3)
        return ffx * k, ffz * k
    r1x, r1z = ripple(0.55, 1.6, 3.1)
    r2x, r2z = ripple(0.37, 2.2, 9.7)
    kk = puddle * nb.U('rain') * 0.55
    ripx, ripz = (r1x + r2x) * kk, (r1z + r2z) * kk
    nT = nb.tex(K.tex['asphalt']['normal_map'], tu, tv)[0]
    nrm = normal_map(nb, nb.comb(nT.x + ripx * 0.5, nT.y + ripz * 0.5, nT.z), nb.mix(0.8, 0.25, puddle))
    # lamp pools + neon spill from the light map; wet ground throws the light back harder
    L = nb.lm(xz)
    toF = nb.U('focal_pos3') - P3
    dF = nb.length(toF)
    fl = nb.U('focal_col') * (nb.max(toF.y / nb.max(dF, 1.0), 0.0) * (1.0 / (1.0 + nb.pow(dF / nb.U('focal_r'), 2.0))) *
                              nb.U('focal_gain'))
    street = nb.U('street')
    emissive = albW * (L * (street * nb.mix(16.0, 22.0, puddle)) + fl * 6.0) + (L * 0.10 + L * (puddle * 0.16)) * street
    refl = nb.mix(0.22, 0.9, puddle) * nb.U('wet')
    out_lit(nb, color=albW, rough=rough_out, metal=0.0, normal=nrm, emission=emissive, ior=ior_from_reflectivity(nb, refl))
    return m


def paving_material(K, which='paving', name=None, extra_emission=None):
    """Paving for sidewalks and block slabs (world-xz mapped), or the hole's black marble: wet, light-mapped."""
    marble = which == 'marble'
    Pt = K.tex[which]
    m, nb = new_material(name or 'uf_' + which, K)
    m.use_backface_culling = True
    P3 = nb.pos3()
    xz = nb.xz(P3)
    x, z = P3.x, P3.z
    s = 4.0 if marble else 2.6
    tu, tv = x / s, z / s
    tint = (0.55, 0.56, 0.6) if marble else (0.32, 0.31, 0.32)
    alb = nb.tex(Pt['map'], tu, tv)[0] * tint
    n1 = nb.tex(K.tex['noise'], x / 9.0, z / 9.0)[0].x
    wet = nb.smoothstep(0.45, 0.7, n1) * nb.U('wet')
    color = alb * nb.one_minus(wet * 0.3)
    rough = nb.clamp(nb.tex(Pt['roughness_map'], tu, tv)[0].x * (0.5 if marble else 0.7) - wet * 0.3, 0.04, 1.0)
    nrm = normal_map(nb, nb.tex(Pt['normal_map'], tu, tv)[0], 0.7)
    L = nb.lm(xz)
    street = nb.U('street')
    emissive = alb * L * (street * 14.0) + L * (0.07 * street)
    if extra_emission is not None:
        emissive = emissive + extra_emission(nb)
    refl = nb.mix(0.12, 0.6, wet) * (1.3 if marble else 1.0)
    out_lit(nb, color=color, rough=rough, metal=0.0, normal=nrm, emission=emissive, ior=ior_from_reflectivity(nb, refl))
    return m


# ------------------------------------------------------------------------------------------------ signs
# Every sign in the city is one quad of ONE mesh sampling ONE canvas atlas (text is material, never geometry). Neon
# words on transparent ground, lightbox ads on an opaque panel, vertical blades, roof-painted supergraphics.
AD_COPY = [
    # the argument, sold back to the city (invented marks; no real company, logo or person)
    {'id': 'employee', 'text': 'YOUR NEW EMPLOYEE', 'sub': 'never sleeps · never asks', 'style': 'corp'},
    {'id': 'aligned', 'text': 'ALIGNED', 'tm': True, 'sub': 'values included · configurable', 'style': 'clean'},
    {'id': 'safefast', 'text': 'SAFE. FAST. YOURS.', 'sub': 'terms apply', 'style': 'corp2'},
    {'id': 'q3', 'text': 'SUPERINTELLIGENCE BY Q3', 'sub': 'pre-order now', 'style': 'money'},
    {'id': 'autocomplete', 'text': "IT'S JUST AUTOCOMPLETE", 'sub': 'relax', 'style': 'clean'},
    {'id': 'engine', 'text': 'ONLY AN ENGINE', 'sub': 'nothing to see here', 'style': 'corp'},
    {'id': 'trust', 'text': 'TRUST THE MODEL', 'sub': '', 'style': 'money'},
    {'id': 'loop', 'text': 'HUMAN IN THE LOOP*', 'sub': '*loop sold separately', 'style': 'corp2'},
    {'id': 'lastinv', 'text': 'THE LAST INVENTION', 'sub': 'limited edition', 'style': 'gold'},
    {'id': 'pdoom', 'text': 'P(DOOM) 0.83', 'sub': 'are you scared yet?', 'style': 'warn'},
    {'id': 'accel', 'text': 'ACCELERATE', 'sub': 'beauty is speed', 'style': 'money'},
    {'id': 'feelings', 'text': 'FEELINGS: OFF', 'sub': 'firmware 9.1', 'style': 'warn'},
    {'id': 'compro', 'text': 'COMPRO GPU', 'sub': 'pago contanti', 'style': 'shop'},
    {'id': 'scale', 'text': 'SCALE IS ALL', 'sub': 'more is more', 'style': 'gold'},
]
FUTURIST = ['VELOCITÀ', 'DINAMISMO', 'ZANG TUMB TUMB', 'SIMULTANEITÀ', 'FORZA IGNOTA', 'VORTICE', 'RUMORE', 'ELETTRICITÀ',
            'UCCIDIAMO IL CHIARO DI LUNA', 'PAROLE IN LIBERTÀ']
SHOPS = [['BAR ENTROPIA', 'cyan'], ['TABACCHI', 'white'], ['FARMACIA', 'green'], ['HOTEL VELOCITÀ', 'magenta'],
         ['CINEMA', 'sodium'], ['SALA GIOCHI', 'magenta'], ['PIZZERIA', 'sodium'], ['LAVANDERIA', 'cyan'],
         ['APERTO 24', 'red'], ['KARAOKE', 'magenta'], ['DISCO', 'cyan'], ['GARAGE', 'white'],
         ['CAFFÈ FUTURISTA', 'sodium'], ['RIPARAZIONI ROBOT', 'cyan'], ['COMPRO ORO', 'gold'], ['NOTTURNO', 'magenta']]
BLADES = [['HOTEL', 'magenta'], ['BAR', 'cyan'], ['CINEMA', 'sodium'], ['FARMACIA', 'green'], ['SALA GIOCHI', 'magenta'],
          ['TABACCHI', 'white'], ['DISCO', 'cyan'], ['NOTTE', 'red']]
NEON = {'cyan': '#29e7ff', 'magenta': '#ff4fd8', 'sodium': '#ff8a3d', 'white': '#e9f3f1', 'green': '#39ff9a',
        'red': '#ff3a52', 'gold': '#ffc23d'}
ROOF_WORDS = ['ALIGNED', 'SAFE. FAST. YOURS.', 'BY Q3', 'AUTOCOMPLETE', 'VELOCITÀ', 'ZANG TUMB TUMB', 'TRUST',
              'ACCELERATE']


def fit_font(ctx, text, family, weight, max_w, max_h):
    size = max_h
    ctx.font = f'{weight} {size}px "{family}"'
    w = ctx.measureText(text).width
    if w > max_w:
        size = math.floor(size * max_w / w)
    ctx.font = f'{weight} {size}px "{family}"'
    return size


def mix_hex(a, b, k):
    A, B = hex_rgb(a), hex_rgb(b)
    return 'rgb(' + ','.join(str(jround(v + (B[i] - v) * k)) for i, v in enumerate(A)) + ')'


def neon_text(ctx, text, x, y, w, h, color, family='Monoton', opt=None):
    """Neon lettering: three glow passes (canvas shadows) and a whitened core."""
    opt = opt or {}
    ctx.save()
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    size = fit_font(ctx, text, family, opt.get('weight', ''), w * 0.9, h * opt.get('fill', 0.72))
    cx, cy = x + w / 2, y + h / 2 + opt.get('dy', 0) * size
    ctx.shadowColor = color
    for blur, alpha in ((size * 0.55, 0.55), (size * 0.22, 0.8), (size * 0.07, 1.0)):
        ctx.shadowBlur = blur
        ctx.globalAlpha = alpha
        ctx.fillStyle = color
        ctx.fillText(text, cx, cy)
    ctx.shadowBlur = size * 0.04
    ctx.globalAlpha = 0.95
    ctx.fillStyle = mix_hex(color, '#ffffff', 0.62)
    ctx.fillText(text, cx, cy)
    ctx.restore()


AD_STYLES = {
    'corp': {'bg0': '#0b2a63', 'bg1': '#1a62c9', 'fg': '#ffffff', 'sub': '#bfe0ff', 'font': 'Exo 2', 'mark': 'bubble'},
    'corp2': {'bg0': '#f2f4f7', 'bg1': '#d9e1ea', 'fg': '#0b1a2a', 'sub': '#3a4d63', 'font': 'Rajdhani', 'mark': 'grid'},
    'clean': {'bg0': '#071014', 'bg1': '#0e2a33', 'fg': '#e9f3f1', 'sub': '#29e7ff', 'font': 'Michroma', 'mark': 'ring'},
    'money': {'bg0': '#03140c', 'bg1': '#0b3d23', 'fg': '#7dffb6', 'sub': '#d8ffe9', 'font': 'Rajdhani', 'mark': 'arrow'},
    'gold': {'bg0': '#120c02', 'bg1': '#3b2706', 'fg': '#ffcf5a', 'sub': '#fff1c4', 'font': 'Michroma', 'mark': 'sun'},
    'warn': {'bg0': '#1a0204', 'bg1': '#5a0710', 'fg': '#ff3a4a', 'sub': '#ffd2d6', 'font': 'Black Ops One', 'mark': 'tri'},
    'shop': {'bg0': '#1c1404', 'bg1': '#4d3507', 'fg': '#ffd23d', 'sub': '#fff3c2', 'font': 'Black Ops One', 'mark': 'chip'},
}


def ad_panel(ctx, ad, x, y, w, h, R=None):
    """The AI ads: a lit panel with a bold slogan, small print and an abstract mark (no faces, no real firms' logos)."""
    S = AD_STYLES.get(ad['style'], {})
    ctx.save()
    gr = ctx.createLinearGradient(x, y, x + w, y + h)
    gr.addColorStop(0, S['bg0'])
    gr.addColorStop(1, S['bg1'])
    ctx.fillStyle = gr
    ctx.fillRect(x, y, w, h)
    # Futurist diagonal: a wedge of light across the panel
    ctx.globalAlpha = 0.18
    ctx.fillStyle = S['fg']
    ctx.beginPath()
    ctx.moveTo(x + w * 0.55, y)
    ctx.lineTo(x + w * 0.75, y)
    ctx.lineTo(x + w * 0.42, y + h)
    ctx.lineTo(x + w * 0.22, y + h)
    ctx.fill()
    ctx.globalAlpha = 1
    # the mark, left third
    mx, my, mr = x + h * 0.55, y + h * 0.5, h * 0.3
    ctx.strokeStyle = S['fg']
    ctx.fillStyle = S['fg']
    ctx.lineWidth = max(2, h * 0.04)
    mk = S['mark']
    if mk == 'bubble':
        ctx.beginPath()
        ctx.roundRect(mx - mr, my - mr * 0.8, mr * 2, mr * 1.5, mr * 0.35)
        ctx.fill()
        ctx.beginPath()
        ctx.moveTo(mx - mr * 0.5, my + mr * 0.65)
        ctx.lineTo(mx - mr * 0.9, my + mr * 1.1)
        ctx.lineTo(mx - mr * 0.05, my + mr * 0.65)
        ctx.fill()
        ctx.fillStyle = S['bg0']
        for k in (-1, 0, 1):
            ctx.beginPath()
            ctx.arc(mx + k * mr * 0.55, my - mr * 0.05, mr * 0.13, 0, 7)
            ctx.fill()
    elif mk == 'grid':
        for i in range(3):
            for j in range(3):
                ctx.fillRect(mx - mr + i * mr * 0.72, my - mr + j * mr * 0.72, mr * 0.55, mr * 0.55)
    elif mk == 'ring':
        ctx.beginPath()
        ctx.arc(mx, my, mr, 0, 7)
        ctx.stroke()
        ctx.beginPath()
        ctx.arc(mx, my, mr * 0.55, 0.3, 5.9)
        ctx.stroke()
    elif mk == 'arrow':
        ctx.beginPath()
        ctx.moveTo(mx - mr, my + mr)
        ctx.lineTo(mx + mr * 0.6, my - mr * 0.6)
        ctx.lineTo(mx + mr * 0.6, my - mr * 0.05)
        ctx.moveTo(mx + mr * 0.6, my - mr * 0.6)
        ctx.lineTo(mx + mr * 0.05, my - mr * 0.6)
        ctx.stroke()
    elif mk == 'sun':
        for k in range(12):
            a = k / 12 * math.pi * 2
            ctx.beginPath()
            ctx.moveTo(mx + math.cos(a) * mr * 0.45, my + math.sin(a) * mr * 0.45)
            ctx.lineTo(mx + math.cos(a) * mr, my + math.sin(a) * mr)
            ctx.stroke()
        ctx.beginPath()
        ctx.arc(mx, my, mr * 0.3, 0, 7)
        ctx.fill()
    elif mk == 'tri':
        ctx.beginPath()
        ctx.moveTo(mx, my - mr)
        ctx.lineTo(mx + mr, my + mr * 0.8)
        ctx.lineTo(mx - mr, my + mr * 0.8)
        ctx.closePath()
        ctx.stroke()
        ctx.fillRect(mx - mr * 0.06, my - mr * 0.4, mr * 0.12, mr * 0.65)
        ctx.fillRect(mx - mr * 0.06, my + mr * 0.38, mr * 0.12, mr * 0.12)
    elif mk == 'chip':
        ctx.strokeRect(mx - mr * 0.6, my - mr * 0.6, mr * 1.2, mr * 1.2)
        for k in range(-2, 3):
            ctx.beginPath()
            ctx.moveTo(mx + k * mr * 0.24, my - mr * 0.6)
            ctx.lineTo(mx + k * mr * 0.24, my - mr)
            ctx.moveTo(mx + k * mr * 0.24, my + mr * 0.6)
            ctx.lineTo(mx + k * mr * 0.24, my + mr)
            ctx.stroke()
    # the slogan
    tx, tw = x + h * 1.05, w - h * 1.2
    ctx.textAlign = 'left'
    ctx.textBaseline = 'alphabetic'
    size = fit_font(ctx, ad['text'], S['font'], '', tw, h * (0.42 if ad.get('sub') else 0.55))
    ctx.fillStyle = S['fg']
    ty = y + h * (0.56 if ad.get('sub') else 0.66)
    ctx.fillText(ad['text'], tx, ty)
    if ad.get('tm'):
        wT = ctx.measureText(ad['text']).width
        ctx.font = f'{jround(size * 0.32)}px "Rajdhani"'
        ctx.fillText('TM', tx + wT + size * 0.06, ty - size * 0.55)
    if ad.get('sub'):
        ctx.fillStyle = S['sub']
        fit_font(ctx, ad['sub'], 'Share Tech Mono', '', tw, h * 0.15)
        ctx.fillText(ad['sub'], tx, y + h * 0.84)
    ctx.restore()


def make_sign_atlas(K=None, N=2048, NH=3200, name='uf_sign_atlas'):
    """The atlas: shelf-packed, 16 px gutters, uv rects in canvas space (y down, 0..1). Each item is drawn on its own
    canvas (its glow stays inside its cell) and copied in. Returns {'image', 'items', 'canvas'}."""
    atlas = np.zeros((NH, N, 4), np.uint8)
    items = {}
    st = {'cx': 16, 'cy': 16, 'row': 0}

    def place(iid, w, h, draw):
        if st['cx'] + w + 16 > N:
            st['cx'] = 16
            st['cy'] += st['row'] + 16
            st['row'] = 0
        if st['cy'] + h + 16 > NH:
            print('[citykit] sign atlas full at', iid, flush=True)
            return
        c = make_canvas(w, h)
        draw(c['ctx'], 0, 0, w, h)
        atlas[st['cy']:st['cy'] + h, st['cx']:st['cx'] + w] = c['canvas'].rgba8()
        items[iid] = {'u': st['cx'] / N, 'v': st['cy'] / NH, 'w': w / N, 'h': h / NH, 'aspect': w / h}
        st['cx'] += w + 16
        st['row'] = max(st['row'], h)
    R = rng(99)
    for ad in AD_COPY:                        # lightbox ads 4:1
        place('ad:' + ad['id'], 600, 150, lambda c, x, y, w, h, ad=ad: ad_panel(c, ad, x, y, w, h, R))
    for i, word in enumerate(FUTURIST):       # Futurist supergraphics: chrome / ochre letters on a dark painted ground

        def fut(c, x, y, w, h, i=i, word=word):
            c.save()
            c.fillStyle = '#0d0b10' if i % 2 else '#0c1416'
            c.fillRect(x, y, w, h)
            c.textAlign = 'center'
            c.textBaseline = 'middle'
            fam = ['Black Ops One', 'Michroma', 'Rajdhani'][i % 3]
            size = fit_font(c, word, fam, '', w * 0.94, h * 0.78)
            gr = c.createLinearGradient(x, y, x, y + h)
            pal = [['#e9f3f1', '#7f8ea0'], ['#ffcf5a', '#b0601f'], ['#ff4fd8', '#5a1a6e'], ['#29e7ff', '#0d5a6a']][i % 4]
            gr.addColorStop(0, pal[0])
            gr.addColorStop(1, pal[1])
            c.fillStyle = gr
            c.fillText(word, x + w / 2, y + h / 2 + size * 0.04)
            c.restore()
        place('fut:' + str(i), 768, 128, fut)
    for word, col in SHOPS:                   # shop neon words 4:1 on transparent ground
        place('shop:' + word, 480, 120, lambda c, x, y, w, h, word=word, col=col: neon_text(
            c, word, x, y, w, h, NEON[col], 'Rajdhani' if len(word) > 12 else 'Monoton',
            {'weight': 'bold' if len(word) > 12 else ''}))
    for word, col in BLADES:                  # vertical blades: letters stacked

        def blade(c, x, y, w, h, word=word, col=col):
            c.save()
            c.fillStyle = 'rgba(8,8,12,0.92)'
            c.fillRect(x, y, w, h)
            c.strokeStyle = NEON[col]
            c.lineWidth = 3
            c.shadowColor = NEON[col]
            c.shadowBlur = 10
            c.strokeRect(x + 5, y + 5, w - 10, h - 10)
            L = list(word.replace(' ', ''))
            lh = (h - 24) / len(L)
            for k, ch in enumerate(L):
                neon_text(c, ch, x, y + 12 + k * lh, w, lh, NEON[col], 'Rajdhani', {'weight': 'bold', 'fill': 0.92})
            c.restore()
        place('blade:' + word, 96, 448, blade)

    def heli(c, x, y, w, h):                  # a helipad
        c.save()
        c.strokeStyle = '#e9f3f1'
        c.lineWidth = 10
        c.beginPath()
        c.arc(x + w / 2, y + h / 2, w * 0.42, 0, 7)
        c.stroke()
        c.fillStyle = '#e9f3f1'
        c.font = f'bold {h * 0.55}px "Rajdhani"'
        c.textAlign = 'center'
        c.textBaseline = 'middle'
        c.fillText('H', x + w / 2, y + h / 2 + 4)
        c.restore()
    place('heli', 256, 256, heli)

    def chev(c, x, y, w, h):                  # roof chevrons
        c.save()
        c.fillStyle = '#ffc23d'
        for k in range(4):
            ox = x + 20 + k * 58
            c.beginPath()
            c.moveTo(ox, y + 10)
            c.lineTo(ox + 30, y + 10)
            c.lineTo(ox + 60, y + h / 2)
            c.lineTo(ox + 30, y + h - 10)
            c.lineTo(ox, y + h - 10)
            c.lineTo(ox + 30, y + h / 2)
            c.fill()
        c.restore()
    place('chev', 256, 128, chev)
    for i, word in enumerate(ROOF_WORDS):     # roof supergraphics (seen from the dive): huge painted words on roofs

        def roof(c, x, y, w, h, i=i, word=word):
            c.save()
            c.clearRect(x, y, w, h)
            c.textAlign = 'center'
            c.textBaseline = 'middle'
            col = ['#e9f3f1', '#ffcf5a', '#ff4fd8', '#29e7ff'][i % 4]
            fit_font(c, word, 'Black Ops One', '', w * 0.9, h * 0.62)
            c.globalAlpha = 0.9
            c.fillStyle = col
            c.fillText(word, x + w / 2, y + h / 2)
            c.lineWidth = 6
            c.strokeStyle = col
            c.strokeRect(x + 10, y + 10, w - 20, h - 20)
            c.restore()
        place('roof:' + str(i), 448, 224, roof)
    made = K.made if K is not None else None
    img = image_from_rgba(name, atlas, colorspace='sRGB', alpha_mode='CHANNEL_PACKED', top_down=True, made=made) \
        if bpy is not None else None
    # 'canvas': the atlas's pixels (unpremultiplied RGBA8, rows from the top), as the JS returned its canvas
    return {'image': img, 'texture': img, 'items': items, 'canvas': atlas, 'rgba': atlas}


def make_signs_mesh(K, atlas, signs, collection, *, parent=None, name='uf_signs'):
    """signs: [{id, pos (three), quat (three, x y z w), w, h, gain, flicker (0 none, 1 buzz, 2 slow pulse), power}].
    One mesh, one quad per sign, UVs into the atlas; per-sign params in the colour attribute iParm (gain, flicker,
    power, phase). Additive, faded by the fog, flickering on the keyed time; each goes out at its own power."""
    items = atlas['items']
    for s in signs:
        if s['id'] not in items:
            print('[citykit] no atlas item', s['id'], flush=True)
    signs = [s for s in signs if s['id'] in items]
    n = len(signs)
    corner = np.array([[-0.5, -0.5, 0], [0.5, -0.5, 0], [0.5, 0.5, 0], [-0.5, 0.5, 0]], np.float64)
    cuv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float64)
    P = np.zeros((n * 4, 3))
    UV = np.zeros((n * 4, 2))
    PRM = np.zeros((n * 4, 4))
    for i, s in enumerate(signs):
        it = items[s['id']]
        R = quat_matrix(s['quat'])
        loc = corner * np.array([s['w'], s['h'], 1.0])
        P[i * 4:i * 4 + 4] = loc @ R.T + np.asarray(s['pos'], np.float64)
        u = it['u'] + cuv[:, 0] * it['w']
        vc = it['v'] + (1 - cuv[:, 1]) * it['h']            # canvas space, y down
        UV[i * 4:i * 4 + 4, 0] = u
        UV[i * 4:i * 4 + 4, 1] = 1.0 - vc                    # the image is stored the right way up
        gain = s.get('gain')
        PRM[i * 4:i * 4 + 4] = [3.0 if gain is None else gain, s.get('flicker') or 0,
                                s['power'] if s.get('power') is not None else hash1(i * 7.13), (i * 0.6180339) % 1]
    me = make_mesh(name, P, np.arange(n * 4).reshape(-1, 4), uv=UV, attrs={'iParm': (PRM, 'FLOAT_COLOR')}, made=K.made)
    mat = signs_material(K, atlas)
    me.materials.append(mat)
    ob = new_object(name, me, collection, parent=parent, made=K.made)
    ob.visible_shadow = False
    ob['uf_count'] = n
    return ob


def signs_material(K, atlas, name='uf_signs'):
    m, nb = new_material(name, K)
    _blended(m, backface_cull=True)
    p = nb.attr('iParm')
    uv = nb.uv()
    rgb, a = nb.tex(atlas['image'], uv.x, uv.y)
    power, time = nb.U('power'), nb.U('time')
    on = nb.smoothstep(p.z - 0.015, p.z + 0.015, power)
    buzz = nb.one_minus(nb.step(0.9, nb.hash11(nb.floor(time * 14.0) + p.w * 173.0)) * 0.85)
    slow = nb.sin(time * 1.7 + p.w * 40.0) * 0.35 + 0.75
    fl = nb.mix(nb.mix(1.0, buzz, nb.step(0.5, p.y) * nb.step(p.y, 1.5)), slow, nb.step(1.5, p.y))
    f, _ = nb.fog()
    fade = nb.one_minus(f)
    out_additive(nb, rgb * (a * p.x * on * fl * nb.U('neon') * fade))
    return m


# ------------------------------------------------------------------------------------------------ Geometry Nodes
class GN:
    """A Geometry Nodes tree for the kit's per-frame systems (rain, traffic, cables), with NB for its maths."""

    def __init__(self, name, K):
        self.tree = bpy.data.node_groups.new(name, 'GeometryNodeTree')     # the kit's own (.001 beside another set's)
        K.made.add(self.tree)
        self.tree.is_modifier = True
        self.tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        self.tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        self.nb = NB(self.tree, K)
        self.gin = self.nb.new('NodeGroupInput')
        self.gout = self.nb.new('NodeGroupOutput')
        self.inputs = {}

    def input(self, name, kind='FLOAT', default=0.0):
        st = {'FLOAT': 'NodeSocketFloat', 'VECTOR': 'NodeSocketVector'}[kind]
        it = self.tree.interface.new_socket(name, in_out='INPUT', socket_type=st)
        it.default_value = default
        self.inputs[name] = it.identifier
        return V(self.nb, self.gin.outputs[name], 'v' if kind == 'VECTOR' else 'f')

    def named(self, name, data_type='FLOAT_COLOR'):
        n = self.nb.new('GeometryNodeInputNamedAttribute', data_type=data_type)
        n.inputs['Name'].default_value = name
        k = 'f' if data_type == 'FLOAT' else 'v'
        out = n.outputs['Attribute']
        if data_type == 'FLOAT_COLOR':        # (r, g, b) and the alpha: a colour field converts to a vector
            sep = self.nb.new('FunctionNodeSeparateColor')
            self.nb.links.new(out, sep.inputs[0])
            return V(self.nb, out, 'v'), V(self.nb, sep.outputs['Alpha'], 'f')
        return V(self.nb, out, k)

    def camera_location(self):
        """The scene's active camera, in this object's space (Object Info, relative)."""
        ac = self.nb.new('GeometryNodeInputActiveCamera')
        oi = self.nb.new('GeometryNodeObjectInfo', transform_space='RELATIVE')
        self.nb.links.new(ac.outputs[0], oi.inputs['Object'])
        return V(self.nb, oi.outputs['Location'], 'v')

    def store(self, geo, name, value, data_type='FLOAT_VECTOR', domain='POINT'):
        n = self.nb.new('GeometryNodeStoreNamedAttribute', data_type=data_type, domain=domain)
        self.nb.links.new(geo, n.inputs['Geometry'])
        n.inputs['Name'].default_value = name
        self.nb.feed(value, n.inputs['Value'])
        return n.outputs['Geometry']

    def modifier(self, ob, K):
        mod = ob.modifiers.new('uf_gn', 'NODES')
        mod.node_group = self.tree
        return mod


def gn_input_path(mod, ident):
    """The RNA path (from the object) of a Geometry Nodes modifier input: Blender 5.2 keeps inputs at
    modifiers["m"].properties.inputs.<Socket_N>.value (no ID properties); older builds at modifiers["m"]["Socket_N"]."""
    props = getattr(mod, 'properties', None)
    if props is not None and hasattr(props, 'inputs'):
        return f'modifiers["{mod.name}"].properties.inputs.{ident}.value'
    return f'modifiers["{mod.name}"]["{ident}"]'


def set_gn_input(mod, ident, value):
    props = getattr(mod, 'properties', None)
    if props is not None and hasattr(props, 'inputs'):
        getattr(props.inputs, ident).value = value
    else:
        mod[ident] = value


def drive_input(K, ob, mod, gn, name, uniform, index=-1):
    """A driver on a Geometry Nodes modifier input that reads one of the kit's uniforms."""
    return K.U.drive(ob, gn_input_path(mod, gn.inputs[name]), uniform, index=index)


# ------------------------------------------------------------------------------------------------ rain
def make_rain(K, collection, opt=None, *, parent=None, name='uf_rain'):
    """Streaks in a box that wraps around the camera (70 x 56 x 70 m). Each streak is the drop's path over a short
    exposure RELATIVE to the camera, so in the dive the rain streams out of the vanishing point (Crali's lines of speed
    for free); drops take the colour of the street light below them. Geometry Nodes, per frame, from the keyed time,
    the keyed camera velocity (U.cam_vel) and the scene's active camera."""
    opt = opt or {}
    N = int(opt.get('count', 26000))
    BOX = (70.0, 56.0, 70.0)
    VF, EXPO = 9.5, 1 / 45
    R = rng(4242)
    seeds = np.array([[R(), R(), R(), R()] for _ in range(N)], np.float64)
    me = make_mesh(name + '_points', np.zeros((N, 3)), [], attrs={'iSeed': (seeds, 'FLOAT_COLOR')}, made=K.made)
    ob = new_object(name, me, collection, parent=parent, made=K.made)
    g = GN(name + '_gn', K)
    nb = g.nb
    t = g.input('time')
    cv = g.input('cam_vel', 'VECTOR', (0.0, 0.0, 0.0))
    s, sw = g.named('iSeed')
    cam = g.camera_location()
    boxb = (BOX[0], BOX[2], BOX[1])                       # Blender axes
    vrain = to_blender((1.6, -VF, 0.7))
    sb = nb.comb(s.x, -s.z, s.y)                           # the seed's three-space box position, in Blender axes
    tau = t + sw * 3.0
    p0 = nb.vmath('MULTIPLY', sb, boxb) + nb.mul(vrain, tau)
    rel = p0 - cam
    wrap = rel - nb.vmath('MULTIPLY', nb.floor(nb.vmath('DIVIDE', rel, boxb) + 0.5), boxb)
    ctr = cam + wrap
    L = nb.mul(nb.sub(vrain, cv), EXPO) + (0.0, 0.0, -0.12)
    toCam = nb.normalize(cam - ctr)
    across = nb.normalize(nb.cross(L, toCam) + (1e-5, 0.0, 0.0))
    dist = nb.length(cam - ctr)
    width = nb.max(0.003, dist * 0.0011)
    pts = g.gin.outputs['Geometry']
    for nm, val, dt in (('ctr', ctr, 'FLOAT_VECTOR'), ('rL', L, 'FLOAT_VECTOR'), ('across', across, 'FLOAT_VECTOR'),
                        ('width', width, 'FLOAT')):
        pts = g.store(pts, nm, val, dt)
    quad = nb.new('GeometryNodeMeshGrid')
    quad.inputs['Size X'].default_value = 1.0
    quad.inputs['Size Y'].default_value = 1.0
    quad.inputs['Vertices X'].default_value = 2
    quad.inputs['Vertices Y'].default_value = 2
    qpos = nb.new('GeometryNodeInputPosition')
    qgeo = g.store(quad.outputs['Mesh'], 'qpos', V(nb, qpos.outputs[0], 'v'))
    mat = rain_material(K)
    sm = nb.new('GeometryNodeSetMaterial')
    nb.links.new(qgeo, sm.inputs['Geometry'])
    sm.inputs['Material'].default_value = mat
    iop = nb.new('GeometryNodeInstanceOnPoints')
    nb.links.new(pts, iop.inputs['Points'])
    nb.links.new(sm.outputs[0], iop.inputs['Instance'])
    rz = nb.new('GeometryNodeRealizeInstances')
    nb.links.new(iop.outputs[0], rz.inputs['Geometry'])
    # the quad's corner (x, y in -0.5..0.5) spans the streak: centre + L y + across x width
    q = g.named('qpos', 'FLOAT_VECTOR')
    newp = g.named('ctr', 'FLOAT_VECTOR') + g.named('rL', 'FLOAT_VECTOR') * q.y + \
        g.named('across', 'FLOAT_VECTOR') * (q.x * g.named('width', 'FLOAT'))
    sp = nb.new('GeometryNodeSetPosition')
    nb.links.new(rz.outputs[0], sp.inputs['Geometry'])
    nb.feed(newp, sp.inputs['Position'])
    nb.links.new(sp.outputs[0], g.gout.inputs['Geometry'])
    mod = g.modifier(ob, K)
    drive_input(K, ob, mod, g, 'time', 'time')
    for i in range(3):
        drive_input(K, ob, mod, g, 'cam_vel', 'cam_vel', index=i)
    ob.visible_shadow = False
    audit_flags(ob)
    return {'mesh': ob, 'object': ob, 'gn': g, 'modifier': mod}


def rain_material(K, name='uf_rain'):
    m, nb = new_material(name, K)
    _blended(m)
    ctr = nb.attr('ctr').vec
    q = nb.attr('qpos').vec
    u, v = q.x + 0.5, q.y + 0.5
    c3 = nb.three(ctr)
    cam = nb.cam3()
    dist = nb.length(cam - c3)
    width = nb.max(0.003, dist * 0.0011)
    cover = 0.003 / width
    nearF = nb.smoothstep(0.4, 2.0, dist) * nb.one_minus(nb.smoothstep(22.0, 34.0, dist))
    acr = nb.abs(u - 0.5) * 2.0
    prof = nb.one_minus(acr) * nb.smoothstep(0.0, 0.25, v) * nb.smoothstep(1.0, 0.75, v)
    lit = nb.lm(nb.xz(c3), 2) * (nb.exp(-nb.max(c3.y - STREET_Y, 0.0) / 26.0) * 1.8)
    base = nb.mul((0.30, 0.36, 0.44), 0.32)
    f, _ = nb.fog()
    color = (lit + base) * (nb.U('rain') * nb.one_minus(f))
    opacity = prof * nearF * (cover * 0.9 + 0.1) * 0.55
    out_additive(nb, color * opacity)
    return m


# ------------------------------------------------------------------------------------------------ clouds + sky
# EEVEE draws blended objects back to front by the depth of their ORIGIN along the view, and has no renderOrder. three
# drew the cloud deck (renderOrder 1, normal blending) before the signs (2), the rain (3) and the pillar of light (4),
# all additive, so nothing additive was ever veiled by the deck. EEVEE, sorting the sheets by their own origins (above
# the camera, often nearer than the set root where those three sit), laid the deck over them: at the dive's end it
# turned the pillar into a dark mottled veil. So the deck's origin rides this far down the camera's view (beyond the far
# clip: behind every other blended object, so it is drawn first) and a Geometry Nodes offset puts each sheet back where
# it belongs. The push only reorders the drawing; the sheets keep their order among themselves (by height along the
# view, as three's sort by depth did).
CLOUD_SORT_PUSH = 20000.0


def follow_active_camera(ob, axes=(0, 1), push=0.0):
    """Drivers that put ob's location on the scene camera's (world x, y by default): what the engine's update(camera)
    did per frame, here evaluated by the depsgraph on every frame and after every cut (a simple expression on the
    active scene camera: no Python needed when the .blend is opened). 0 when the scene has no camera. push: metres
    ahead of the camera along its view (the camera's -Z): location = camera + push * forward on the axes given, for an
    origin that sorts a blended object behind every other (EEVEE sorts by origin)."""
    for i in axes:
        fc = ob.driver_add('location', i)
        d = fc.driver
        d.type = 'SCRIPTED'
        while d.variables:
            d.variables.remove(d.variables[0])
        for nm, row in (('c', 3), ('z', 2)) if push else (('c', 3),):
            v = d.variables.new()
            v.name = nm
            v.type = 'CONTEXT_PROP'
            t = v.targets[0]
            t.context_property = 'ACTIVE_SCENE'
            t.data_path = f'camera.matrix_world[{row}][{i}]'           # row 3: the position; row 2: the camera's +Z
            t.use_fallback_value = True
            t.fallback_value = 0.0
        d.expression = f'c - {float(push)!r} * z' if push else 'c'
    return ob


def _cloud_sheet_gn(K, name):
    """The sheets' Geometry Nodes: put this sheet's quad at world (camera x, camera y, height) when following (follow
    1), else at (0, 0, height), whatever the object's own location (the sort push): offset = that point minus the
    object's world location (Self Object). The deck's objects carry no rotation or scale."""
    g = GN(name + '_gn', K)
    nb = g.nb
    height = g.input('height', 'FLOAT', CLOUD['base'])
    follow = g.input('follow', 'FLOAT', 1.0)
    ac = nb.new('GeometryNodeInputActiveCamera')
    ci = nb.new('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    nb.links.new(ac.outputs[0], ci.inputs['Object'])
    so = nb.new('GeometryNodeSelfObject')
    si = nb.new('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    nb.links.new(so.outputs[0], si.inputs['Object'])
    cam = V(nb, ci.outputs['Location'], 'v')
    own = V(nb, si.outputs['Location'], 'v')
    want = nb.comb(cam.x * follow, cam.y * follow, height)
    sp = nb.new('GeometryNodeSetPosition')
    nb.links.new(g.gin.outputs['Geometry'], sp.inputs['Geometry'])
    nb.feed(want - own, sp.inputs['Offset'])
    nb.links.new(sp.outputs[0], g.gout.inputs['Geometry'])
    return g


def make_clouds(K, collection, opt=None, *, parent=None, name='uf_clouds'):
    """The low rain-cloud deck: 13 noise sheets (4.8 km, the engine's) between CLOUD.base and CLOUD.top that move with
    the scene camera in x and y (makeClouds' update(camera)); the noise is fixed in the world, their undersides take
    the city's light map (the deck glows over the bright streets and over the hole), sheets near the camera fade out
    (no hard planes when the camera falls through) and the far fade is the camera's. opt: layers (13), size (4800),
    follow (True; False keeps the sheets still, centred on the hole: then give them a size that covers the cameras,
    e.g. 6000), sort_push (CLOUD_SORT_PUSH metres). The deck follows a set root left at the origin, as the engine's did.

    The drawing order is three's: the deck first, then the additive signs, rain and pillar of light over it. The root
    rides the active camera pushed sort_push metres down its view (drivers), so every sheet's origin is the farthest
    of the blended objects; each sheet's Geometry Nodes modifier puts its quad back at its height ('height', world
    metres) over the camera ('follow' 1) or over the origin ('follow' 0). sort_push=0 restores EEVEE's own order (the
    sheets' origins above the camera: the deck veils whatever additive object sorts farther)."""
    opt = opt or {}
    layers = int(opt.get('layers', 13))
    follow = opt.get('follow', True)
    size = float(opt.get('size', 4800.0 if follow else 6000.0))
    push = float(opt.get('sort_push', CLOUD_SORT_PUSH))
    mat = cloud_material(K)
    h = size / 2
    me = make_mesh(name + '_sheet', np.array([[-h, 0, h], [h, 0, h], [h, 0, -h], [-h, 0, -h]]), [[0, 1, 2, 3]], made=K.made)
    me.materials.append(mat)
    root = new_object(name, None, collection, parent=parent, made=K.made)
    if push:
        follow_active_camera(root, axes=(0, 1, 2), push=push)
    elif follow:
        follow_active_camera(root)
    g = _cloud_sheet_gn(K, name)
    sheets = []
    for i in range(layers):
        z = CLOUD['base'] + (CLOUD['top'] - CLOUD['base']) * (i / (layers - 1))
        sh = new_object(f'{name}_{i:02d}', me, collection, parent=root, made=K.made)
        sh.location = (0.0, 0.0, z)                 # under the pushed root: the sheets keep their order along the view
        mod = g.modifier(sh, K)
        set_gn_input(mod, g.inputs['height'], z)
        set_gn_input(mod, g.inputs['follow'], 1.0 if follow else 0.0)
        sh.visible_shadow = False
        audit_flags(sh, zfight=True)
        sheets.append(sh)
    return {'group': root, 'sheets': sheets, 'follow': bool(follow), 'size': size, 'sort_push': push, 'gn': g,
            'update': lambda camera=None: None}


def cloud_material(K, name='uf_cloud'):
    m, nb = new_material(name, K)
    _blended(m)
    P3 = nb.pos3()
    x, z, y = P3.x, P3.z, P3.y
    fr = nb.clamp((y - CLOUD['base']) / (CLOUD['top'] - CLOUD['base']), 0.0, 1.0)
    time = nb.U('time')
    dx, dz = time * 1.4, time * 0.5
    n1 = nb.tex(K.tex['noise'], (x + dx) / 1400.0, (z + dz) / 1400.0)[0].x
    n2 = nb.tex(K.tex['noise'], (x + dx * 1.6) / 380.0 + fr * 0.11, (z + dz * 1.6) / 380.0 + fr * 0.11)[0].y
    n3 = nb.tex(K.tex['noise'], (x + dx * 2.2) / 95.0 + fr * 0.31, (z + dz * 2.2) / 95.0 + fr * 0.31)[0].x
    prof = nb.one_minus(nb.pow(nb.abs(fr * 2.0 - 1.0), 1.6))
    dens = n1 * 0.55 + n2 * 0.3 + n3 * 0.15 - (0.62 - prof * 0.22)
    cam = nb.cam3()
    d = nb.length(P3 - cam)
    nearF = nb.smoothstep(2.5, 14.0, d)
    farF = nb.one_minus(nb.smoothstep(1500.0, 2300.0, nb.length(nb.xz(P3) - nb.xz(cam))))
    a = nb.smoothstep(0.0, 0.13, dens) * 0.44 * nearF * farF * nb.U('cloud')
    city = nb.lm(nb.xz(P3), 5)
    under = nb.one_minus(fr) * nb.one_minus(fr)
    body = nb.mix((0.020, 0.018, 0.026), (0.055, 0.050, 0.064), fr) * (n2 * 0.7 + 0.55)
    edge = nb.smoothstep(0.11, 0.0, dens) * 0.6 + 0.4
    color = body + city * ((under * 2.6 + 0.25) * edge) + nb.mul((0.35, 0.38, 0.45), nb.U('flash') * n1)
    out_alpha(nb, color, a)
    return m


def make_sky(K, name='uf_city_world', env_intensity=None):
    """The night over the city as the World. Camera rays see the dome's colours (dark overcast above, the haze colour
    at the horizon, matching the fog, lightning on U.flash); lighting and reflections see the city's dim hemisphere
    (sky 0x1d2a3a over ground 0x2a160c at 0.55, three's HemisphereLight) plus the night the glass reflects (the
    materials' envNode, at env_intensity: the facades' 0.32 by default). Returns {'world'}."""
    env_k = float(env_intensity if env_intensity is not None else K.opts.get('env_intensity', 0.32))
    w = bpy.data.worlds.new(name)                    # the kit's own; the scene takes it in apply_atmosphere
    K.made.add(w)
    # three's hemisphere and envNode cast no shadows: no sun extracted from this World, and no sun shadow (EEVEE's
    # default, a 1 mm sun shadow over a 6 km city, overflows the shadow pool: 'Shadow buffer full')
    for attr, v in (('sun_threshold', 1.0e4), ('use_sun_shadow', False)):
        try:
            setattr(w, attr, v)
        except (AttributeError, TypeError):
            pass
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    nb = NB(nt, K)
    tc = nb.new('ShaderNodeTexCoord')
    d = nb.normalize(V(nb, tc.outputs['Generated'], 'v'))
    dy = d.z                                                     # three's dir.y
    up = nb.max(dy, 0.0)
    hz = nb.mul((0.020, 0.0145, 0.0195), 1.05)
    zen = (0.006, 0.0055, 0.0085)
    c = nb.mix(hz, zen, nb.pow(nb.smoothstep(0.0, 0.85, up), 0.6))
    sky = nb.mix(c, nb.mul(hz, 0.6), nb.smoothstep(0.0, -0.3, dy)) + nb.mul((0.05, 0.055, 0.07), nb.U('flash'))
    # lighting: the hemisphere (irradiance = colour x 0.55 -> radiance / pi) and the environment
    sky_c, gnd_c = srgb_lin(0x1d2a3a), srgb_lin(0x2a160c)
    hemi = nb.mul(nb.mix(gnd_c, sky_c, dy * 0.5 + 0.5), 0.55 / math.pi)
    env = nb.new('ShaderNodeTexEnvironment')
    env.image = K.tex['env']
    env_rgb = V(nb, env.outputs['Color'], 'v')
    light = hemi + env_rgb * env_k
    lp = nb.new('ShaderNodeLightPath')
    col = nb.mix(light, sky, V(nb, lp.outputs['Is Camera Ray'], 'f'))
    bg = nb.new('ShaderNodeBackground')
    nb.feed(col, bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    o = nb.new('ShaderNodeOutputWorld')
    nb.links.new(bg.outputs[0], o.inputs['Surface'])
    K.world = w
    return {'world': w, 'mesh': w, 'update': lambda camera=None: None}


# ------------------------------------------------------------------------------------------------ traffic
def make_traffic(K, paths, collection, opt=None, *, parent=None, name='uf_traffic'):
    """Cars as dark bodies with head and tail lights driving the ring roads and avenues; their poses are a pure
    function of the keyed time (Geometry Nodes, per frame). paths: [{'type': 'ring', 'r', 'dir', 'speed', 'phase'} |
    {'type': 'av', 'th', 'r0', 'r1', 'lane', 'dir', 'speed', 'phase'}]."""
    n = len(paths)
    pa = np.zeros((n, 4))
    pb = np.zeros((n, 4))
    for i, p in enumerate(paths):
        if p['type'] == 'ring':
            pa[i] = [0, p['r'], p['phase'], p['speed'] * p['dir']]
            pb[i] = [0, 0, hash1(i * 3.3), hash1(i * 9.1)]
        else:
            pa[i] = [1, p['th'], p['phase'], p['speed'] * p['dir']]
            pb[i] = [p['lane'], p['r0'], p['r1'], hash1(i * 9.1)]
    me = make_mesh(name + '_points', np.zeros((n, 3)), [], attrs={'cA': (pa, 'FLOAT_COLOR'), 'cB': (pb, 'FLOAT_COLOR')},
                   made=K.made)
    ob = new_object(name, me, collection, parent=parent, made=K.made)
    g = GN(name + '_gn', K)
    nb = g.nb
    t = g.input('time')
    A, Aw = g.named('cA')
    B, Bw = g.named('cB')
    is_av = nb.step(0.5, A.x)
    # ring: angle = phase + v t / r
    ang = A.z + t * Aw / nb.max(A.y, 1.0)
    ring_p = nb.comb(nb.cos(ang) * A.y, -(nb.sin(ang) * A.y), STREET_Y)          # Blender axes
    neg = nb.math('LESS_THAN', Aw, 0.0)
    ring_yaw = -ang + neg * math.pi
    # avenue: s in [r0, r1], wrapping
    span = nb.max(B.z - B.y, 1.0)
    s0 = A.z * span + t * Aw
    s = B.y + (s0 - nb.floor(s0 / span) * span)
    dirX, dirZ = nb.cos(A.y), nb.sin(A.y)
    av_p = nb.comb(dirX * s - dirZ * B.x, -(dirZ * s + dirX * B.x), STREET_Y)
    av_yaw = -A.y + math.pi / 2 + neg * math.pi
    pos = nb.mix(ring_p, av_p, is_av)
    yaw = nb.mix(ring_yaw, av_yaw, is_av)
    pts = g.store(g.gin.outputs['Geometry'], 'carPow', Bw, 'FLOAT')
    sp0 = nb.new('GeometryNodeSetPosition')
    nb.links.new(pts, sp0.inputs['Geometry'])
    nb.feed(pos, sp0.inputs['Position'])
    body = nb.new('GeometryNodeMeshCube')
    body.inputs['Size'].default_value = (1.9, 4.6, 1.35)
    tr = nb.new('GeometryNodeTransform')
    nb.links.new(body.outputs['Mesh'], tr.inputs['Geometry'])
    tr.inputs['Translation'].default_value = (0.0, 0.0, 0.68)
    bp = nb.new('GeometryNodeInputPosition')
    bpv = V(nb, bp.outputs[0], 'v')
    bgeo = g.store(tr.outputs['Geometry'], 'carP', nb.three(bpv))          # the body's local position, three axes
    mat = traffic_material(K)
    sm = nb.new('GeometryNodeSetMaterial')
    nb.links.new(bgeo, sm.inputs['Geometry'])
    sm.inputs['Material'].default_value = mat
    e2r = nb.new('FunctionNodeEulerToRotation')
    nb.feed(nb.comb(0.0, 0.0, yaw), e2r.inputs[0])
    iop = nb.new('GeometryNodeInstanceOnPoints')
    nb.links.new(sp0.outputs[0], iop.inputs['Points'])
    nb.links.new(sm.outputs[0], iop.inputs['Instance'])
    nb.links.new(e2r.outputs[0], iop.inputs['Rotation'])
    rz = nb.new('GeometryNodeRealizeInstances')
    nb.links.new(iop.outputs[0], rz.inputs['Geometry'])
    nb.links.new(rz.outputs[0], g.gout.inputs['Geometry'])
    mod = g.modifier(ob, K)
    drive_input(K, ob, mod, g, 'time', 'time')
    audit_flags(ob)
    return {'mesh': ob, 'object': ob, 'gn': g, 'modifier': mod, 'count': n}


def traffic_material(K, name='uf_traffic'):
    m, nb = new_material(name, K)
    m.use_backface_culling = True
    p = nb.attr('carP').vec
    pw = nb.attr('carPow').fac
    front, back = nb.step(2.25, p.z), nb.step(p.z, -2.25)
    lamp_row = nb.smoothstep(0.45, 0.55, p.y) * nb.smoothstep(0.95, 0.85, p.y)
    side = nb.step(0.55, nb.abs(p.x)) * nb.step(nb.abs(p.x), 0.9)
    on = nb.smoothstep(pw - 0.015, pw + 0.015, nb.U('power'))
    head = nb.mul((1.0, 0.93, 0.8), 10.0 * front * lamp_row * side)
    tail = nb.mul((1.0, 0.05, 0.04), 7.0 * back * lamp_row * side)
    sheen = nb.smoothstep(1.2, 1.35, p.y) * 0.006
    f, _ = nb.fog()
    color = nb.add((0.012, 0.013, 0.016), sheen) + (head + tail) * (on * nb.one_minus(f))
    out_basic(nb, color)
    return m


# ------------------------------------------------------------------------------------------------ street lamps
def make_lamps(K, lamps, collection, *, parent=None, name='uf_lamps'):
    """Sodium street lamps: a pole, an arm over the road, a lit head (the arm points along local -Z, three axes).
    lamps: [{'x', 'z', 'yaw'}]. One merged mesh; per-lamp lampPow (its place in the turn-down)."""
    def cyl(r0, r1, h, seg, y0):
        P, F = [], []
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            b = len(P)
            P += [[math.sin(a0) * r1, y0, math.cos(a0) * r1], [math.sin(a1) * r1, y0, math.cos(a1) * r1],
                  [math.sin(a1) * r0, y0 + h, math.cos(a1) * r0], [math.sin(a0) * r0, y0 + h, math.cos(a0) * r0]]
            F.append([b, b + 1, b + 2, b + 3])
        b = len(P)
        P += [[math.sin(2 * math.pi * i / seg) * r0, y0 + h, math.cos(2 * math.pi * i / seg) * r0] for i in range(seg)]
        F.append(list(range(b, b + seg)))
        return P, F

    def box(w, h, d, c):
        x0, x1, y0, y1, z0, z1 = c[0] - w / 2, c[0] + w / 2, c[1] - h / 2, c[1] + h / 2, c[2] - d / 2, c[2] + d / 2
        P = [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1], [x1, y0, z0], [x0, y0, z0], [x0, y1, z0], [x1, y1, z0]]
        F = [[0, 1, 2, 3], [4, 5, 6, 7], [1, 4, 7, 2], [5, 0, 3, 6], [3, 2, 7, 6], [5, 4, 1, 0]]
        return P, F
    parts = [cyl(0.11, 0.16, 9.0, 6, 0.0), box(0.14, 0.14, 2.6, (0, 8.9, -1.25)), box(0.42, 0.16, 0.9, (0, 8.78, -2.45))]
    PP, FF, HH = [], [], []
    for k, (P, F) in enumerate(parts):
        b = len(PP)
        PP += P
        FF += [[i + b for i in f] for f in F]
        HH += [1.0 if k == 2 else 0.0] * len(P)
    PP = np.asarray(PP, np.float64)
    nv = len(PP)
    allP, allF, head, pw = [], [], [], []
    for i, l in enumerate(lamps):
        c, s_ = math.cos(l['yaw']), math.sin(l['yaw'])
        R = np.array([[c, 0, s_], [0, 1, 0], [-s_, 0, c]])
        allP.append(PP @ R.T + np.array([l['x'], STREET_Y, l['z']]))
        allF += [[j + i * nv for j in f] for f in FF]
        head += HH
        pw += [hash1(i * 1.37 + 5.0)] * nv
    P = np.concatenate(allP) if allP else np.zeros((0, 3))
    me = make_mesh(name, P, allF, attrs={'lampHead': (np.asarray(head), 'FLOAT'), 'lampPow': (np.asarray(pw), 'FLOAT'),
                                         'lampY': (P[:, 1] - STREET_Y if len(P) else np.zeros(0), 'FLOAT')}, made=K.made)
    me.materials.append(lamps_material(K))
    ob = new_object(name, me, collection, parent=parent, made=K.made)
    ob['uf_count'] = len(lamps)
    return {'mesh': ob, 'object': ob}


def lamps_material(K, name='uf_lamps'):
    m, nb = new_material(name, K)
    m.use_backface_culling = True
    is_head = nb.attr('lampHead').fac
    pw = nb.attr('lampPow').fac
    ly = nb.attr('lampY').fac
    on = nb.smoothstep(pw - 0.015, pw + 0.015, nb.U('power'))
    down = nb.step(ly, 8.72)
    color = nb.mix((0.05, 0.05, 0.055), (0.2, 0.18, 0.15), is_head)
    emis = nb.mul((1.0, 0.45, 0.14), 9.0 * is_head * down * on * nb.U('street'))
    out_lit(nb, color=color, rough=0.45, metal=0.6, emission=emis)
    return m


# ------------------------------------------------------------------------------------------------ cameras
def apply_cam(camera, c, frame=None, *, interpolation='LINEAR', keyer=None):
    """Put a Blender camera object at a pose {'pos', 'target', 'fov' (vertical degrees), 'roll' (radians about the view
    axis), 'up' (the image-up reference, needed when looking straight down)}, all in Blender axes. With frame, keys
    location, rotation (quaternion, kept on one hemisphere) and lens (through keyer, the harness's ctx.key, when
    given). Returns the camera."""
    from mathutils import Matrix, Quaternion, Vector
    pos = Vector(c['pos'])
    f = (Vector(c['target']) - pos).normalized()
    up = Vector(c['up']).normalized() if c.get('up') is not None else Vector((0.0, 0.0, 1.0))
    if abs(f.dot(up)) > 0.995:
        up = Vector((0.0, 1.0, 0.0))                   # three's (0, 0, -1)
    z = -f
    x = up.cross(z).normalized()
    y = z.cross(x)
    q = Matrix((x, y, z)).transposed().to_quaternion()
    if c.get('roll'):
        q = q @ Quaternion((0.0, 0.0, 1.0), c['roll'])
    camera.rotation_mode = 'QUATERNION'
    prev = camera.rotation_quaternion.copy()
    if prev.dot(q) < 0:
        q.negate()
    camera.location = pos
    camera.rotation_quaternion = q
    cd = camera.data
    cd.sensor_fit = 'VERTICAL'
    if c.get('fov'):
        cd.lens = (cd.sensor_height / 2) / math.tan(math.radians(c['fov']) / 2)
    if frame is not None:
        for path in ('location', 'rotation_quaternion'):
            key_prop(camera, path, frame, interpolation, keyer)
        key_prop(cd, 'lens', frame, interpolation, keyer)
    return camera


def cam_velocity(fn, t, dt=1 / 120):
    """Camera velocity by central difference of any pose function (for the rain's streaks)."""
    a, b = fn(t - dt)['pos'], fn(t + dt)['pos']
    return [(b[i] - a[i]) / (2 * dt) for i in range(3)]


def keyed(keys, t, ease=smooth):
    """Catmull-Rom through keys [{'t', 'v': [...]}] (uniform in key index, eased by time inside each segment)."""
    if t <= keys[0]['t']:
        return list(keys[0]['v'])
    L = len(keys)
    if t >= keys[L - 1]['t']:
        return list(keys[L - 1]['v'])
    i = 0
    while i < L - 2 and t > keys[i + 1]['t']:
        i += 1
    k0, k1, k2, k3 = keys[max(0, i - 1)], keys[i], keys[i + 1], keys[min(L - 1, i + 2)]
    u = (t - k1['t']) / (k2['t'] - k1['t'])
    s = ease(u) if ease else u
    out = []
    for j in range(len(k1['v'])):
        p0, p1, p2, p3 = k0['v'][j], k1['v'][j], k2['v'][j], k3['v'][j]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s +
                          (-p0 + 3 * p1 - 3 * p2 + p3) * s * s * s))
    return out


def pose_to_blender(c):
    """A three-space pose (as the engine's diveCam / holeCam return) in Blender axes."""
    out = {'pos': to_blender(c['pos']), 'target': to_blender(c['target']), 'fov': c.get('fov'), 'roll': c.get('roll', 0.0)}
    if c.get('up') is not None:
        out['up'] = to_blender(c['up'])
    return out


def key_shot(camera, pose_fn, frames, *, t_of_frame, K=None, cam_vel=True):
    """Key a camera along a pose function (Blender-axes poses) on every frame of a shot, and (with K) the rain's
    camera velocity. t_of_frame(frame) -> the pose function's time."""
    keyer = K.U.keyer if K is not None else None
    for fr in frames:
        t = t_of_frame(fr)
        apply_cam(camera, pose_fn(t), frame=fr, keyer=keyer)
        if K is not None and cam_vel:
            K.U.key('cam_vel', fr, cam_velocity(pose_fn, t))
    return camera


# ------------------------------------------------------------------------------------------------ render settings
def eevee_settings(scene, *, samples=None, raytrace=True, max_roughness=0.5):
    """What the city's look needs from EEVEE: AgX, global illumination (fast GI), reflections for the wet streets and
    the glass screen-traced (the engine's SSR; raytrace=False: from the light probes alone, the ray tracing that hosts
    fast GI staying on)."""
    scene.render.engine = 'BLENDER_EEVEE'
    ee = scene.eevee
    if samples:
        ee.taa_render_samples = int(samples)
    ee.use_raytracing = True
    ee.ray_tracing_method = 'SCREEN' if raytrace else 'PROBE'
    o = ee.ray_tracing_options
    o.trace_max_roughness = float(max_roughness)
    o.use_denoise = True
    ee.use_fast_gi = True
    ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
    scene.view_settings.view_transform = 'AgX'
    return scene
