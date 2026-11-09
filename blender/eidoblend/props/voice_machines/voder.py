"""The Bell Labs Voder, 1939 New York World's Fair (voder.js, ported), and the era-1 craft kit.

Homer Dudley's Voder: the vocoder's synthesis half, played by hand. Ten finger keys set the levels of ten band-pass
filters (0-7500 Hz); a left-wrist bar switches buzz (voiced, bar down) and hiss (unvoiced, bar up); three right-thumb
keys make the stop pairs t-d, p-b, k-g; a right-thumb "quiet" key drops about 20 dB; a right-foot pedal sets pitch.
The console plays itself: nobody is modelled at it.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props.voice_machines import voder

    vo = voder.build()                                   # -> Voder: group (root Empty), parts, update, animate
    vo.group.location = (0, 2, 0)
    vo.animate(lambda t: {'voice': 0.5 + 0.5 * math.sin(t * 3), 'power': 1}, frames=(1, 96))   # keys every frame
    # or per frame, in time order (a harness render_frame(ctx, t, i) passes ctx):
    vo.update(t, {'voice': v}, ctx=ctx)                  # sets and keys the frame of t
    vo.update(t, {'keys': [0.8] + [0] * 9, 'wrist': 1, 'stops': [0, 0, 0], 'quiet': 0, 'pedal': 0.5, 'level': 0.7})
    voder.pattern(t)                                     # the demo fingering: keys[10], stops[3], quiet, wrist, pedal, level

update(t, state): state['voice'] (0..1, this era's voice loudness) animates everything when 'keys' isn't given: the
demo fingering (pattern(t)) gated by the voice, the needle and the grille glow on the voice. 'keys' etc. override.
'power' (0..1) lights the pilot jewel, the dial and the grille. Deterministic in t. Every value the update sets is
KEYED at the frame of t (frame= wins; ctx.key in the harness; LINEAR), key=False only poses, and animate() keys a
range and drops the keys that change nothing, so a saved .blend plays and renders any frame on its own. The lamp and
glow levels are custom properties on the root ("power", "level") that the materials read through drivers.

parts: keys[0..9] (each with ['band'] = [lo, hi] Hz), stop_keys[3] (t-d, p-b, k-g), quiet_key, wrist_bar, pedal,
dial {needle, face, texture}, lamp (the pilot jewel), grille (the object carrying the backlit cloth), console, speaker,
uniforms {power, level} (Uniform: .value reads and writes the root's property).
Metres, Blender Z up, floor z = 0, facing -Y (three's +Z). About 1.3 m wide x 1.35 m deep, tower 1.70 m.

THE ERA-1 CRAFT KIT (the same block heads voder.js / mainframe.js / teletype.js; here it lives once, in this file,
and mainframe.py / teletype.py import it): the AmbientCG sets of the library pack (eidoverse/assets/models/
voice_machines/tex/), the GLB import with its role slots, the layered role material (a tiling set on UV0, recoloured
by luminance, the baked masks on UV1: R = AO over 0.30 m, G = edges, B = AO over 4 cm, curvature wear, grime, dust,
fingerprint and smear breakup), glass, canvas decals, a canvas-2D drawing surface on Pillow (the labels and logos are
drawn in code, as the engine drew them), small geometry builders (three's RoundedBox, Sphere, Cylinder, Box, Torus,
Lathe), and the keyer.

EEVEE translations of the engine's material terms (measured choices, see tools-guides/_drafts/voice-machines-b.md):
  aoNode            three applies AO to indirect light only. EEVEE's horizon scan already occludes the indirect light
                    at the 30 cm scale, so the R channel is not applied again; the 4 cm cavity term (B), which screen
                    space cannot resolve at a distance, darkens the base colour: albedo *= mix(1, 0.65 + 0.35 cav, ao).
  curvature()       a per-triangle attribute 'eido_curv' (1/m): the trace of the shape operator from the corner
                    normals, which is what dFdx/dFdy of the interpolated normal measured (constant per triangle).
  mx_fractal_noise  Blender's Noise Texture, fBm, Normalize off: the same lookup3 hash, gradients and fade as
                    MaterialX (fx/_noise.py), summed the same way.
  transparent/opacity   Principled Alpha with the BLENDED render method; castShadow false -> visible_shadow off.
  CPU mip chains    not needed: Blender builds the mips of every image itself.
"""

from __future__ import annotations

import json
import math
import os
import re

import numpy as np
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from ... import common

PACK = common.asset_path('models', 'voice_machines')
TEX_DIR = os.path.join(PACK, 'tex')
LUM = (0.2126, 0.7152, 0.0722)


# ===================================================================================================================
# ERA-1 CRAFT KIT
# ===================================================================================================================

# ------------------------------------------------------------------------------------------------- small maths ---
def clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


def sstep(a, b, x):
    """GLSL smoothstep(a, b, x) (voder.js sstep)."""
    t = clamp01((x - a) / (b - a)) if b != a else (1.0 if x >= b else 0.0)
    return t * t * (3 - 2 * t)


def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    """0xRRGGBB or '#rrggbb' -> sRGB-encoded (r, g, b) 0..1."""
    if isinstance(h, str):
        h = int(h.lstrip('#'), 16)
    return (((h >> 16) & 255) / 255.0, ((h >> 8) & 255) / 255.0, (h & 255) / 255.0)


def lin(h):
    """three's Color(hex) in the linear working space (the engine's rgb()/lin() helpers): a linear (r, g, b)."""
    return tuple(srgb_to_lin(c) for c in hex_rgb(h))


def v3(x, y, z):
    """A three.js (Y-up) point or direction in Blender axes."""
    return Vector((x, -z, y))


def axis_letter(axis3):
    """three local axis 'x' | 'y' | 'z' -> (Blender local axis index, sign): x -> +X, y -> +Z, z -> -Y."""
    return {'x': (0, 1.0), 'y': (2, 1.0), 'z': (1, -1.0)}[axis3]


# ------------------------------------------------------------------------------------------------ the keyer ---
class Uniform:
    """A uniform the engine's materials read (three's uniform().value): here a custom property on the machine's
    root, read by the materials through drivers, and keyed like everything else."""

    def __init__(self, owner, prop, value=0.0, lo=0.0, hi=1.0, description=''):
        self.owner, self.prop = owner, prop
        owner[prop] = float(value)
        try:
            ui = owner.id_properties_ui(prop)
            ui.update(min=lo, max=hi, soft_min=lo, soft_max=hi, description=description)
        except (AttributeError, TypeError):
            pass

    @property
    def value(self):
        return float(self.owner[self.prop])

    @value.setter
    def value(self, v):
        self.owner[self.prop] = float(v)

    @property
    def path(self):
        return f'["{self.prop}"]'


class Keyer:
    """Keys what a machine's update set, at a frame: through ctx.key in the harness (its runner sets the
    interpolation afterwards), else keyframe_insert with the interpolation set on the inserted points right away
    (Python's keyframe_insert ignores the preference and makes BEZIER keys)."""

    def __init__(self):
        self.ids = {}
        self._fc = {}

    def _fcurves(self, idb, full):
        k = (idb.as_pointer(), full)
        fcs = self._fc.get(k)
        if fcs is None or any(not _alive(fc) for fc in fcs):
            ad = getattr(idb, 'animation_data', None)
            fcs = [fc for fc in _action_fcurves(ad.action) if fc.data_path == full] if ad and ad.action else []
            self._fc[k] = fcs
        return fcs

    def key(self, target, path, index=-1, frame=None, ctx=None, interpolation='LINEAR'):
        if ctx is not None:
            return ctx.key(target, path, index=index, frame=frame, interpolation=interpolation)
        f = bpy.context.scene.frame_current if frame is None else frame
        ok = target.keyframe_insert(path, index=index, frame=f)
        idb = target.id_data
        self.ids[idb.as_pointer()] = idb
        try:
            full = target.path_from_id(path)
        except (ValueError, TypeError, AttributeError):
            full = path
        for fc in self._fcurves(idb, full):
            if index >= 0 and fc.array_index != index:
                continue
            kps = fc.keyframe_points
            hit = kps[-1] if len(kps) and abs(kps[-1].co.x - f) < 1e-3 else next(
                (p for p in kps if abs(p.co.x - f) < 1e-3), None)
            if hit is not None:
                hit.interpolation = interpolation
        return ok

    def finish(self, simplify=True):
        """With simplify, keys that change nothing are removed: a LINEAR key on the straight line between its
        neighbours, a CONSTANT key equal to the one before (to 1e-6), so a held value costs two keys, not one per
        frame. Returns the keys left on the F-curves keyed here."""
        n = 0
        for ptr, idb in list(self.ids.items()):
            ad = getattr(idb, 'animation_data', None)
            if ad is None or ad.action is None:
                continue
            for fc in _action_fcurves(ad.action):
                kps = fc.keyframe_points
                if simplify and len(kps) > 2:
                    co = np.empty(len(kps) * 2)
                    kps.foreach_get('co', co)
                    co = co.reshape(-1, 2)
                    ip = [k.interpolation for k in kps]
                    x, y = co[:, 0], co[:, 1]
                    keep = np.ones(len(x), bool)
                    tol = 1e-6 * np.maximum(1.0, np.abs(y[1:-1]))
                    mid = (x[2:] - x[:-2])
                    lerp = y[:-2] + (y[2:] - y[:-2]) * (x[1:-1] - x[:-2]) / np.where(mid == 0, 1, mid)
                    lin_ok = (np.abs(lerp - y[1:-1]) <= tol)
                    const_ok = (np.abs(y[1:-1] - y[:-2]) <= tol)
                    for j in range(1, len(x) - 1):
                        same = ip[j] == ip[j - 1]
                        if same and ((ip[j] == 'LINEAR' and lin_ok[j - 1]) or (ip[j] == 'CONSTANT' and const_ok[j - 1])):
                            keep[j] = False
                    if not keep.all():
                        new = co[keep]
                        nip = [ip[j] for j in range(len(ip)) if keep[j]]
                        while len(kps) > len(new):
                            kps.remove(kps[len(kps) - 1], fast=True)
                        kps.foreach_set('co', new.ravel())
                        for k, w in zip(kps, nip):
                            k.interpolation = w
                            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
                        fc.update()
                n += len(kps)
        self._fc.clear()
        return n


def _alive(rna):
    try:
        rna.data_path
        return True
    except ReferenceError:
        return False


def _alive_id(idb):
    try:
        idb.name
        return True
    except ReferenceError:
        return False


def _action_fcurves(action):
    out = []
    for ly in getattr(action, 'layers', ()):
        for st in ly.strips:
            for cb in st.channelbags:
                out.extend(cb.fcurves)
    if not out and hasattr(action, 'fcurves'):
        out = list(action.fcurves)
    return out


def frame_range(frames=None, scene=None):
    sc = scene or bpy.context.scene
    if frames is None:
        return sc.frame_start, sc.frame_end
    return int(frames[0]), int(frames[1])


def scene_fps(scene=None):
    sc = scene or bpy.context.scene
    return sc.render.fps / sc.render.fps_base


def set_turn(obj, axis3, angle, rest=None):
    """obj's local rotation = its rest rotation, then a turn about its own three-axis ('x' | 'y' | 'z') by angle
    (three's o.quaternion.copy(q0).multiply(axisAngle)). One Euler channel carries the turn: Euler order puts the
    turn first and the rest's single axis last, so a keyed angle interpolates exactly (motion blur included)."""
    i, sgn = axis_letter(axis3)
    rest = rest if rest is not None else obj.get('eido_rest_euler')
    a = sgn * angle
    if rest is None:
        obj.rotation_mode = 'XYZ'
        e = [0.0, 0.0, 0.0]
        e[i] = a
        obj.rotation_euler = e
        return (i,)
    ri, rv = int(rest[0]), float(rest[1])        # the rest is a pure turn about Blender axis ri
    letters = 'XYZ'
    other = [k for k in range(3) if k not in (i, ri)][0]
    obj.rotation_mode = letters[i] + letters[other] + letters[ri]
    e = [0.0, 0.0, 0.0]
    e[ri] = rv
    e[i] = a
    obj.rotation_euler = e
    return (i,)


def remember_rest(obj):
    """Record obj's imported rest rotation when it is a pure turn about one Blender axis (for set_turn)."""
    q = obj.rotation_quaternion if obj.rotation_mode == 'QUATERNION' else obj.rotation_euler.to_quaternion()
    q = q.normalized()
    comps = [q.x, q.y, q.z]
    nz = [k for k in range(3) if abs(comps[k]) > 1e-6]
    if not nz:
        return None
    if len(nz) > 1:
        raise ValueError(f'{obj.name}: rest rotation is not about one axis ({tuple(q)})')
    k = nz[0]
    ang = 2.0 * math.atan2(comps[k], q.w)
    obj['eido_rest_euler'] = [k, ang]
    return (k, ang)


# --------------------------------------------------------------------------------------------- canvas 2D ---
_WIN_FONTS = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
_FAMILY_FILES = {
    # family -> {weight class: file}; a variable face lists one file and the named instances it carries
    'bahnschrift': {'var': 'bahnschrift.ttf'},
    'segoe ui': {400: 'segoeui.ttf', 600: 'seguisb.ttf', 700: 'segoeuib.ttf'},
    'arial': {400: 'arial.ttf', 700: 'arialbd.ttf'},
    'lucida console': {400: 'lucon.ttf'},
    'consolas': {400: 'consola.ttf', 700: 'consolab.ttf'},
    'courier new': {400: 'cour.ttf', 700: 'courbd.ttf'},
}
_GENERIC = {'sans-serif': ('Rajdhani-Bold', 'Exo2'), 'monospace': ('SpaceMono-Regular', 'ShareTechMono-Regular'),
            'serif': ('OldStandard-Regular',)}
_VAR_NAMES = {300: b'Light', 350: b'SemiLight', 400: b'Regular', 500: b'Regular', 600: b'SemiBold', 700: b'Bold'}
_font_cache = {}


def _parse_font(spec):
    """'600 70px "Bahnschrift", "Segoe UI", Arial, sans-serif' -> (weight, px, [families])."""
    m = re.match(r'\s*(?:(bold|normal|\d{3})\s+)?([\d.]+)px\s+(.*)$', spec)
    if not m:
        raise ValueError(f'font {spec!r}')
    w = m.group(1)
    weight = 700 if w == 'bold' else 400 if w in (None, 'normal') else int(w)
    fams = [f.strip().strip('"\'') for f in m.group(3).split(',')]
    return weight, float(m.group(2)), fams


def resolve_font(families, weight=400):
    """The first family with a font file on this machine (Windows faces first, as Skia's lookup did; the repo's
    bundled fonts for the generic fallbacks). Returns (path, variation name or None, synthetic bold)."""
    from ...media import raster
    for fam in families:
        f = _FAMILY_FILES.get(fam.lower())
        if f:
            if 'var' in f:
                p = os.path.join(_WIN_FONTS, f['var'])
                if os.path.exists(p):
                    w = min(_VAR_NAMES, key=lambda k: abs(k - weight))
                    return p, _VAR_NAMES[w], False
                continue
            best = min(f, key=lambda k: (abs(k - weight), -k))
            p = os.path.join(_WIN_FONTS, f[best])
            if os.path.exists(p):
                return p, None, weight >= 600 and best < 600
            continue
        for cand in _GENERIC.get(fam.lower(), ()):
            try:
                return str(raster.font_path(cand)), None, False
            except KeyError:
                pass
    return str(raster.font_path('Rajdhani-Bold')), None, False


def pil_font(families, weight, px):
    from PIL import ImageFont
    path, var, fake = resolve_font(families, weight)
    key = (path, var, int(round(px)))
    f = _font_cache.get(key)
    if f is None:
        f = ImageFont.truetype(path, max(1, int(round(px))))
        if var:
            try:
                f.set_variation_by_name(var)
            except (OSError, ValueError):
                pass
        _font_cache[key] = f
    return f, fake


def _css_color(c):
    """CSS colour -> (r, g, b, a) floats, sRGB-encoded as canvas works."""
    if isinstance(c, (tuple, list)):
        return tuple(float(v) for v in c) if len(c) == 4 else tuple(float(v) for v in c) + (1.0,)
    s = str(c).strip()
    m = re.match(r'rgba?\(([^)]*)\)', s)
    if m:
        p = [float(x) for x in m.group(1).split(',')]
        return (p[0] / 255, p[1] / 255, p[2] / 255, p[3] if len(p) > 3 else 1.0)
    if s.startswith('#'):
        h = s[1:]
        if len(h) == 3:
            h = ''.join(ch * 2 for ch in h)
        v = int(h[:6], 16)
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (((v >> 16) & 255) / 255, ((v >> 8) & 255) / 255, (v & 255) / 255, a)
    from PIL import ImageColor
    r, g, b, *a = ImageColor.getrgb(s)
    return (r / 255, g / 255, b / 255, (a[0] / 255) if a else 1.0)


def _stroke_polys(pts, closed, width, miter_limit=10.0):
    """A polyline's stroke as polygons whose union is canvas-2D's stroke (butt caps, miter joins falling back to
    bevel past the miter limit): one quad per segment and one join wedge per corner. (Pillow's own wide line leaves
    seams between short segments.)"""
    P = [p for i, p in enumerate(pts) if i == 0 or (abs(p[0] - pts[i - 1][0]) + abs(p[1] - pts[i - 1][1])) > 1e-9]
    if closed and len(P) > 2 and abs(P[0][0] - P[-1][0]) + abs(P[0][1] - P[-1][1]) < 1e-9:
        P = P[:-1]
    if len(P) < 2:
        return []
    hw = width / 2.0
    n = len(P)
    segs = [(P[i], P[(i + 1) % n]) for i in range(n if closed else n - 1)]
    out = []
    nrm = []
    ov = 0.5                                     # quads overlap half a pixel at inner joints: no seam between them
    for i, ((x0, y0), (x1, y1)) in enumerate(segs):
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        nrm.append((nx, ny, ux, uy))
        e0 = ov if (closed or i > 0) else 0.0
        e1 = ov if (closed or i < len(segs) - 1) else 0.0
        x0, y0, x1, y1 = x0 - ux * e0, y0 - uy * e0, x1 + ux * e1, y1 + uy * e1
        out.append([(x0 + nx * hw, y0 + ny * hw), (x1 + nx * hw, y1 + ny * hw),
                    (x1 - nx * hw, y1 - ny * hw), (x0 - nx * hw, y0 - ny * hw)])
    joints = range(len(segs)) if closed else range(1, len(segs))
    for j in joints:
        a, b = nrm[j - 1], nrm[j]
        px, py = segs[j][0]
        cross = a[2] * b[3] - a[3] * b[2]
        if abs(cross) < 1e-9 and a[2] * b[2] + a[3] * b[3] > 0:
            continue
        s = -1.0 if cross > 0 else 1.0                     # the outer side of the turn
        o0 = (px + a[0] * hw * s, py + a[1] * hw * s)
        o1 = (px + b[0] * hw * s, py + b[1] * hw * s)
        mx, my = a[0] + b[0], a[1] + b[1]
        ml = math.hypot(mx, my)
        cos_half = ml / 2.0
        if ml > 1e-9 and 1.0 / max(cos_half, 1e-9) <= miter_limit:
            k = hw / cos_half
            out.append([(px, py), o0, (px + mx / ml * k * s, py + my / ml * k * s), o1])
        else:
            out.append([(px, py), o0, o1])
    return out


class _Gradient:
    def __init__(self, kind, args):
        self.kind, self.args, self.stops = kind, args, []

    def addColorStop(self, t, c):
        self.stops.append((float(t), _css_color(c)))
        self.stops.sort(key=lambda s: s[0])

    def paint(self, xs, ys, M):
        """RGBA (premultiplied-ready, straight) at device pixel centres xs, ys (arrays): user space via M^-1."""
        Mi = np.linalg.inv(M)
        ux = Mi[0, 0] * xs + Mi[0, 1] * ys + Mi[0, 2]
        uy = Mi[1, 0] * xs + Mi[1, 1] * ys + Mi[1, 2]
        if self.kind == 'linear':
            x0, y0, x1, y1 = self.args
            dx, dy = x1 - x0, y1 - y0
            dd = dx * dx + dy * dy or 1.0
            t = ((ux - x0) * dx + (uy - y0) * dy) / dd
        else:
            x0, y0, r0, x1, y1, r1 = self.args
            cdx, cdy, dr = x1 - x0, y1 - y0, r1 - r0
            px, py = ux - x0, uy - y0
            a = cdx * cdx + cdy * cdy - dr * dr
            b = px * cdx + py * cdy + r0 * dr
            c = px * px + py * py - r0 * r0
            if abs(a) < 1e-9:
                t = c / (2 * b + 1e-12)
            else:
                disc = np.sqrt(np.maximum(b * b - a * c, 0.0))
                ta, tb = (b + disc) / a, (b - disc) / a
                hi, lo = np.maximum(ta, tb), np.minimum(ta, tb)
                t = np.where(r0 + hi * dr >= 0, hi, lo)      # the largest t whose circle has r >= 0
        t = np.clip(t, 0.0, 1.0)
        st = self.stops or [(0.0, (0, 0, 0, 0))]
        ts = np.array([s[0] for s in st])
        cs = np.array([s[1] for s in st])
        out = np.empty(t.shape + (4,), np.float32)
        for k in range(4):
            out[..., k] = np.interp(t, ts, cs[:, k])
        return out


class Ctx2D:
    """The subset of canvas-2D the era-1 and era-2 drawing code uses, on numpy + Pillow, supersampled ``ss`` times
    (canvas draws anti-aliased; ImageDraw does not). Colours blend in sRGB-encoded premultiplied space as canvas
    does. Transforms, paths (arc, arcTo, quadratic, bezier), fills and strokes with linear/radial gradients, text with
    textAlign/textBaseline and synthetic bold, globalAlpha, shadowBlur glow, save/restore. ``image()`` returns the
    canvas as a Pillow RGBA image at its own size."""

    def __init__(self, w, h, ss=3):
        self.width, self.height, self.ss = int(w), int(h), int(ss)
        self.W, self.H = self.width * self.ss, self.height * self.ss
        self.buf = np.zeros((self.H, self.W, 4), np.float32)
        self.fillStyle = '#000'
        self.strokeStyle = '#000'
        self.lineWidth = 1.0
        self.font = '10px sans-serif'
        self.textAlign = 'start'
        self.textBaseline = 'alphabetic'
        self.globalAlpha = 1.0
        self.shadowBlur = 0.0
        self.shadowColor = 'rgba(0,0,0,0)'
        self.M = np.diag([float(self.ss), float(self.ss), 1.0])
        self._stack = []
        self._paths = []
        self._cur = None

    # --- state ---
    _STATE = ('fillStyle', 'strokeStyle', 'lineWidth', 'font', 'textAlign', 'textBaseline', 'globalAlpha',
              'shadowBlur', 'shadowColor')

    def save(self):
        self._stack.append({k: getattr(self, k) for k in self._STATE} | {'M': self.M.copy()})

    def restore(self):
        if self._stack:
            s = self._stack.pop()
            for k in self._STATE:
                setattr(self, k, s[k])
            self.M = s['M']

    def translate(self, x, y):
        self.M = self.M @ np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], float)

    def scale(self, sx, sy):
        self.M = self.M @ np.diag([sx, sy, 1.0])

    def rotate(self, a):
        c, s = math.cos(a), math.sin(a)
        self.M = self.M @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)

    def _tp(self, x, y):
        M = self.M
        return (M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2])

    def _scale(self):
        return math.sqrt(abs(np.linalg.det(self.M[:2, :2])))

    # --- gradients ---
    def createLinearGradient(self, x0, y0, x1, y1):
        return _Gradient('linear', (x0, y0, x1, y1))

    def createRadialGradient(self, x0, y0, r0, x1, y1, r1):
        return _Gradient('radial', (x0, y0, r0, x1, y1, r1))

    # --- paths ---
    def beginPath(self):
        self._paths, self._cur = [], None

    def moveTo(self, x, y):
        self._cur = [[self._tp(x, y)], False, (x, y)]
        self._paths.append(self._cur)

    def _line_user(self, x, y):
        if self._cur is None:
            self.moveTo(x, y)
            return
        self._cur[0].append(self._tp(x, y))
        self._cur[2] = (x, y)

    def lineTo(self, x, y):
        self._line_user(x, y)

    def closePath(self):
        if self._cur is not None:
            self._cur[1] = True
            first = self._cur[0][0]
            self._cur = [[first], False, self._cur[2]]
            self._paths.append(self._cur)

    def _nseg(self, r, sweep):
        return max(4, int(abs(sweep) * max(r, 1e-3) * self._scale() / 2.5) + 4)

    def arc(self, cx, cy, r, a0, a1, ccw=False):
        sweep = a1 - a0
        if not ccw:
            if sweep < 0:
                sweep = sweep % (2 * math.pi) if abs(sweep) < 2 * math.pi else -sweep
            sweep = min(sweep, 2 * math.pi)
        else:
            if sweep > 0:
                sweep = -(((-sweep) % (2 * math.pi)) or 2 * math.pi) if sweep < 2 * math.pi else -2 * math.pi
            sweep = max(sweep, -2 * math.pi)
        n = self._nseg(r, sweep)
        for k in range(n + 1):
            a = a0 + sweep * k / n
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if k == 0 and self._cur is None:
                self.moveTo(x, y)
            else:
                self._line_user(x, y)

    def arcTo(self, x1, y1, x2, y2, r):
        if self._cur is None:
            self.moveTo(x1, y1)
        x0, y0 = self._cur[2]
        v1 = np.array([x0 - x1, y0 - y1], float)
        v2 = np.array([x2 - x1, y2 - y1], float)
        l1, l2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if l1 < 1e-9 or l2 < 1e-9 or r <= 0:
            self._line_user(x1, y1)
            return
        u1, u2 = v1 / l1, v2 / l2
        cosang = float(np.clip(u1 @ u2, -1, 1))
        ang = math.acos(cosang)
        if abs(math.sin(ang)) < 1e-9:
            self._line_user(x1, y1)
            return
        d = r / math.tan(ang / 2)
        p1 = np.array([x1, y1]) + u1 * d
        p2 = np.array([x1, y1]) + u2 * d
        bis = (u1 + u2) / np.linalg.norm(u1 + u2)
        c = np.array([x1, y1]) + bis * (r / math.sin(ang / 2))
        a0 = math.atan2(p1[1] - c[1], p1[0] - c[0])
        a1 = math.atan2(p2[1] - c[1], p2[0] - c[0])
        cross = u1[0] * u2[1] - u1[1] * u2[0]
        self._line_user(*p1)
        sweep = a1 - a0
        sweep = (sweep + math.pi) % (2 * math.pi) - math.pi
        n = self._nseg(r, sweep)
        for k in range(1, n + 1):
            a = a0 + sweep * k / n
            self._line_user(c[0] + r * math.cos(a), c[1] + r * math.sin(a))
        del cross

    def quadraticCurveTo(self, cx, cy, x, y):
        x0, y0 = self._cur[2] if self._cur else (cx, cy)
        n = 12
        for k in range(1, n + 1):
            t = k / n
            self._line_user((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x,
                            (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y)

    def bezierCurveTo(self, c1x, c1y, c2x, c2y, x, y):
        x0, y0 = self._cur[2] if self._cur else (c1x, c1y)
        n = 24
        for k in range(1, n + 1):
            t = k / n
            a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
            self._line_user(a * x0 + b * c1x + c * c2x + d * x, a * y0 + b * c1y + c * c2y + d * y)

    def rect(self, x, y, w, h):
        self.moveTo(x, y)
        self._line_user(x + w, y)
        self._line_user(x + w, y + h)
        self._line_user(x, y + h)
        self.closePath()

    # --- rasterising ---
    def _mask_from_polys(self, polys, stroke_w=None, closed=None):
        from PIL import Image, ImageDraw
        im = Image.new('L', (self.W, self.H), 0)
        d = ImageDraw.Draw(im)
        for k, pts in enumerate(polys):
            if len(pts) < 2:
                continue
            fp = [(float(x), float(y)) for x, y in pts]
            if stroke_w is None:
                if len(fp) >= 3:
                    d.polygon(fp, fill=255)
            else:
                for poly in _stroke_polys(fp, bool(closed and closed[k]), max(stroke_w, 0.5)):
                    d.polygon(poly, fill=255)
        return np.asarray(im, np.float32) / 255.0

    def _composite(self, mask, style):
        if mask is None or not mask.any():
            return
        ys, xs = np.nonzero(mask > 0)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        mk = mask[y0:y1, x0:x1]
        if self.shadowBlur > 0:
            sc = _css_color(self.shadowColor)
            if sc[3] > 0:
                from PIL import Image, ImageFilter
                pad = int(self.shadowBlur * self.ss * 1.5) + 2
                Y0, Y1 = max(0, y0 - pad), min(self.H, y1 + pad)
                X0, X1 = max(0, x0 - pad), min(self.W, x1 + pad)
                sm = np.zeros((Y1 - Y0, X1 - X0), np.float32)
                sm[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = mk
                im = Image.fromarray((sm * 255).astype(np.uint8), 'L').filter(
                    ImageFilter.GaussianBlur(self.shadowBlur * self.ss / 2.0))
                sb = np.asarray(im, np.float32) / 255.0
                a = sb * sc[3] * self.globalAlpha
                dst = self.buf[Y0:Y1, X0:X1]
                for k in range(3):
                    dst[..., k] = sc[k] * a + dst[..., k] * (1 - a)
                dst[..., 3] = a + dst[..., 3] * (1 - a)
        if isinstance(style, _Gradient):
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32) + 0.5
            paint = style.paint(xx, yy, self.M)
        else:
            c = _css_color(style)
            paint = np.broadcast_to(np.array(c, np.float32), mk.shape + (4,))
        a = mk * paint[..., 3] * self.globalAlpha
        dst = self.buf[y0:y1, x0:x1]
        for k in range(3):
            dst[..., k] = paint[..., k] * a + dst[..., k] * (1 - a)
        dst[..., 3] = a + dst[..., 3] * (1 - a)

    def fill(self):
        polys = [p[0] for p in self._paths if len(p[0]) >= 3]
        if polys:
            self._composite(self._mask_from_polys(polys), self.fillStyle)

    def stroke(self):
        polys = [p[0] for p in self._paths if len(p[0]) >= 2]
        if polys:
            closed = [p[1] for p in self._paths if len(p[0]) >= 2]
            self._composite(self._mask_from_polys(polys, self.lineWidth * self._scale(), closed), self.strokeStyle)

    def fillRect(self, x, y, w, h):
        saved = self._paths, self._cur
        self.beginPath()
        self.rect(x, y, w, h)
        self.fill()
        self._paths, self._cur = saved

    def strokeRect(self, x, y, w, h):
        saved = self._paths, self._cur
        self.beginPath()
        self.rect(x, y, w, h)
        self._paths[0][1] = True
        self.stroke()
        self._paths, self._cur = saved

    def clearRect(self, x, y, w, h):
        pts = [self._tp(x, y), self._tp(x + w, y + h)]
        xa, xb = sorted(int(round(p[0])) for p in pts)
        ya, yb = sorted(int(round(p[1])) for p in pts)
        self.buf[max(0, ya):max(0, yb), max(0, xa):max(0, xb)] = 0

    # --- text ---
    def _font(self, scale=1.0):
        weight, px, fams = _parse_font(self.font)
        return pil_font(fams, weight, px * scale), weight, px

    def measureText(self, text):
        (f, _fake), _w, _px = self._font(self.ss)

        class _M:
            pass
        m = _M()
        m.width = f.getlength(str(text)) / self.ss
        return m

    def fillText(self, text, x, y):
        from PIL import Image, ImageDraw
        text = str(text)
        if not text:
            return
        s = self._scale()
        (f, fake), weight, px = self._font(s)
        h = {'left': 'l', 'start': 'l', 'center': 'm', 'right': 'r', 'end': 'r'}[self.textAlign]
        v = {'alphabetic': 's', 'middle': 'm', 'top': 'a', 'hanging': 'a', 'bottom': 'd', 'ideographic': 'd'}[
            self.textBaseline]
        sw = max(1, int(round(px * s * 0.03))) if fake else 0
        M = self.M
        rot = abs(M[0, 1]) > 1e-9 or abs(M[1, 0]) > 1e-9
        if not rot:
            tx, ty = self._tp(x, y)
            im = Image.new('L', (self.W, self.H), 0)
            ImageDraw.Draw(im).text((tx, ty), text, font=f, fill=255, anchor=h + v, stroke_width=sw, stroke_fill=255)
            self._composite(np.asarray(im, np.float32) / 255.0, self.fillStyle)
            return
        # rotated text: draw it upright in its own image about the anchor, rotate, paste at the transformed anchor
        L = int(f.getlength(text) + 4 * px * s) + 8
        im = Image.new('L', (2 * L, 2 * L), 0)
        ImageDraw.Draw(im).text((L, L), text, font=f, fill=255, anchor=h + v, stroke_width=sw, stroke_fill=255)
        ang = math.degrees(math.atan2(M[1, 0], M[0, 0]))
        im = im.rotate(-ang, resample=Image.BICUBIC, center=(L, L))
        tx, ty = self._tp(x, y)
        full = Image.new('L', (self.W, self.H), 0)
        full.paste(im, (int(round(tx - L)), int(round(ty - L))))
        self._composite(np.asarray(full, np.float32) / 255.0, self.fillStyle)

    # --- out ---
    def image(self):
        from PIL import Image
        ss = self.ss
        b = self.buf.reshape(self.height, ss, self.width, ss, 4).mean(axis=(1, 3))
        a = b[..., 3:4]
        rgb = np.where(a > 1e-6, b[..., :3] / np.maximum(a, 1e-6), 0.0)
        out = np.concatenate([rgb, a], axis=-1)
        return Image.fromarray(np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8), 'RGBA')


def spaced_text(ctx, s, x, y, spacing, align='center'):
    """voder.js K.spacedText: letters drawn one by one with extra spacing (the period plates' tracking)."""
    widths = [ctx.measureText(ch).width for ch in s]
    total = sum(widths) + spacing * max(0, len(s) - 1)
    cx = x - total / 2 if align == 'center' else x - total if align == 'right' else x
    prev = ctx.textAlign
    ctx.textAlign = 'left'
    for ch, w in zip(s, widths):
        ctx.fillText(ch, cx, y)
        cx += w + spacing
    ctx.textAlign = prev


def bleed_alpha(img, rounds=6):
    """Fill the colour under fully transparent pixels from their opaque neighbours (alpha kept), so filtering and
    mips never pull black into a decal's edge (the engine's alpha-weighted CPU mips did the same job)."""
    from PIL import Image, ImageFilter
    a = np.asarray(img, np.float32) / 255.0
    rgb, al = a[..., :3], a[..., 3:4]
    if al.min() > 0.999:
        return img
    acc_rgb, acc_a = rgb * al, al.copy()
    out = rgb.copy()
    filled = al[..., 0] > 0.0
    for k in range(rounds):
        r = 2 ** k
        cim = Image.fromarray(np.clip(acc_rgb * 255, 0, 255).astype(np.uint8), 'RGB').filter(ImageFilter.BoxBlur(r))
        aim = Image.fromarray(np.clip(acc_a[..., 0] * 255, 0, 255).astype(np.uint8), 'L').filter(ImageFilter.BoxBlur(r))
        cs = np.asarray(cim, np.float32) / 255.0
        as_ = np.asarray(aim, np.float32)[..., None] / 255.0
        ok = (as_[..., 0] > 1e-3) & ~filled
        out[ok] = (cs[ok] / as_[ok])
        filled |= ok
        if filled.all():
            break
    res = np.concatenate([np.clip(out, 0, 1), al], axis=-1)
    return Image.fromarray((res * 255 + 0.5).astype(np.uint8), 'RGBA')


def _put_pixels(img, pil, alpha=True, pack=True, bleed=True):
    """Write a Pillow image into a Blender image of its size (canvas rows top-down -> Blender rows bottom-up, so the
    canvas top lands at v = 1) and pack it."""
    pil = pil.convert('RGBA')
    if bleed and alpha:
        pil = bleed_alpha(pil)
    px = np.asarray(pil, np.float32)[::-1] / 255.0
    img.pixels.foreach_set(px.ravel())
    img.update()
    if pack:
        img.pack()
    return img


def image_from_pil(pil, name, srgb=True, alpha=True, pack=True, bleed=True):
    """A Blender image holding a Pillow image (packed into the .blend: the saved file needs nothing beside it)."""
    w, h = pil.size
    img = bpy.data.images.new(name, w, h, alpha=alpha)
    # colour space and alpha mode BEFORE the pixels: changing them on a generated image regenerates its buffer
    # (blank), and the pack below would then store the blank
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    img.alpha_mode = 'STRAIGHT' if alpha else 'NONE'
    return _put_pixels(img, pil, alpha=alpha, pack=pack, bleed=bleed)


class CanvasTex:
    """voder.js K.canvasTex(w, h, draw, opts) -> {tex, ctx, canvas, redraw(fn)}: tex is the packed Blender image, ctx
    its canvas-2D surface (kept, as the engine kept its canvas), redraw(fn) draws fn(ctx, w, h) on top of what is there
    (or nothing) and repacks the image. The engine's options: srgb; repeat and gltf need nothing here (the extension
    is the texture node's, and Blender's images and the importer's flipped glTF UVs put the canvas top at v = 1 for
    both UV conventions); mips: Blender builds its own."""

    def __init__(self, name, w, h, draw, srgb=True, ss=3, alpha=True):
        self.width, self.height, self.alpha = int(w), int(h), alpha
        self.ctx = Ctx2D(w, h, ss=ss)
        self.canvas = self.ctx
        draw(self.ctx, w, h)
        self.tex = image_from_pil(self.ctx.image(), name, srgb=srgb, alpha=alpha)
        self.redraws = 0

    def redraw(self, fn=None):
        if fn is not None:
            fn(self.ctx, self.width, self.height)
        _put_pixels(self.tex, self.ctx.image(), alpha=self.alpha)
        self.redraws += 1
        return self.tex


def canvas_tex(name, w, h, draw, srgb=True, ss=3, alpha=True):
    """voder.js K.canvasTex: the drawing, its image and its redraw (CanvasTex)."""
    return CanvasTex(name, w, h, draw, srgb=srgb, ss=ss, alpha=alpha)


def canvas_image(name, w, h, draw, srgb=True, ss=3, alpha=True):
    """voder.js K.canvasTex(...).tex: draw(ctx, w, h) on a canvas-2D surface -> a packed Blender image."""
    return CanvasTex(name, w, h, draw, srgb=srgb, ss=ss, alpha=alpha).tex


# ---------------------------------------------------------------------------------------------- geometry ---
class Geo:
    """Indexed triangles in THREE's axes (Y up), as the engine built them: pos (N, 3), nrm (N, 3), uv (N, 2),
    tris (M, 3), attrs {name: (N, k)}. to_mesh() turns them into Blender's axes."""

    def __init__(self, pos, nrm, uv, tris, attrs=None):
        self.pos = np.asarray(pos, np.float64).reshape(-1, 3)
        self.nrm = np.asarray(nrm, np.float64).reshape(-1, 3)
        self.uv = np.asarray(uv, np.float64).reshape(-1, 2)
        self.tris = np.asarray(tris, np.int64).reshape(-1, 3)
        self.attrs = dict(attrs or {})

    def copy(self):
        return Geo(self.pos.copy(), self.nrm.copy(), self.uv.copy(), self.tris.copy(),
                   {k: v.copy() for k, v in self.attrs.items()})

    def apply(self, M):
        """Apply a 4x4 (numpy or mathutils) matrix: positions affine, normals by the inverse transpose."""
        M = np.array(M, float)
        self.pos = self.pos @ M[:3, :3].T + M[:3, 3]
        N = np.linalg.inv(M[:3, :3]).T
        n = self.nrm @ N.T
        self.nrm = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        if np.linalg.det(M[:3, :3]) < 0:
            self.tris = self.tris[:, ::-1]
        return self

    def translate(self, x, y, z):
        self.pos = self.pos + np.array([x, y, z])
        return self

    def rotate_x(self, a):
        return self.apply(_mat4(rx=a))

    def rotate_y(self, a):
        return self.apply(_mat4(ry=a))

    def rotate_z(self, a):
        return self.apply(_mat4(rz=a))

    def scale(self, sx, sy, sz):
        return self.apply(np.diag([sx, sy, sz, 1.0]))

    def set_attr(self, name, value):
        v = np.asarray(value, np.float64)
        self.attrs[name] = np.broadcast_to(v, (len(self.pos),) + v.shape).copy() if v.ndim <= 1 else v
        return self


def _mat4(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0, sx=1.0, sy=1.0, sz=1.0):
    """three's Matrix4.compose(position, Quaternion.setFromEuler(Euler(rx, ry, rz) 'XYZ'), scale)."""
    cx, sxn = math.cos(rx), math.sin(rx)
    cy, syn = math.cos(ry), math.sin(ry)
    cz, szn = math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sxn], [0, sxn, cx]])
    Ry = np.array([[cy, 0, syn], [0, 1, 0], [-syn, 0, cy]])
    Rz = np.array([[cz, -szn, 0], [szn, cz, 0], [0, 0, 1]])
    R = Rx @ Ry @ Rz
    M = np.eye(4)
    M[:3, :3] = R @ np.diag([sx, sy, sz])
    M[:3, 3] = (x, y, z)
    return M


def xf(g, x=0, y=0, z=0, rx=0, ry=0, rz=0, sx=1, sy=1, sz=1):
    """voder.js K.xf: bake a three-style transform into the geometry."""
    return g.apply(_mat4(x, y, z, rx, ry, rz, sx, sy, sz))


def merge(geos):
    pos, nrm, uv, tris, attrs = [], [], [], [], {}
    off = 0
    names = set().union(*(g.attrs.keys() for g in geos)) if geos else set()
    for g in geos:
        pos.append(g.pos)
        nrm.append(g.nrm)
        uv.append(g.uv)
        tris.append(g.tris + off)
        for k in names:
            v = g.attrs.get(k)
            if v is None:
                w = next(h.attrs[k].shape[1:] for h in geos if k in h.attrs)
                v = np.zeros((len(g.pos),) + w)
            attrs.setdefault(k, []).append(v)
        off += len(g.pos)
    return Geo(np.concatenate(pos), np.concatenate(nrm), np.concatenate(uv), np.concatenate(tris),
               {k: np.concatenate(v) for k, v in attrs.items()})


def box_geo(w, h, d, ws=1, hs=1, ds=1):
    """three's BoxGeometry (faces +x, -x, +y, -y, +z, -z; three's UV layout per face)."""
    pos, nrm, uv, tris = [], [], [], []

    def plane(u, v, wdir, udir, vdir, width, height, depth, gx, gy):
        base = len(pos)
        for iy in range(gy + 1):
            yv = iy * height / gy - height / 2
            for ix in range(gx + 1):
                xv = ix * width / gx - width / 2
                p = [0.0, 0.0, 0.0]
                p[u] = xv * udir
                p[v] = yv * vdir
                p[wdir] = depth / 2
                n = [0.0, 0.0, 0.0]
                n[wdir] = 1.0 if depth > 0 else -1.0
                pos.append(p)
                nrm.append(n)
                uv.append((ix / gx, 1 - iy / gy))
        for iy in range(gy):
            for ix in range(gx):
                a = base + ix + (gx + 1) * iy
                b = base + ix + (gx + 1) * (iy + 1)
                c = base + (ix + 1) + (gx + 1) * (iy + 1)
                dd = base + (ix + 1) + (gx + 1) * iy
                tris.append((a, b, dd))
                tris.append((b, c, dd))
    plane(2, 1, 0, -1, -1, d, h, w, ds, hs)
    plane(2, 1, 0, 1, -1, d, h, -w, ds, hs)
    plane(0, 2, 1, 1, 1, w, d, h, ws, ds)
    plane(0, 2, 1, 1, -1, w, d, -h, ws, ds)
    plane(0, 1, 2, 1, -1, w, h, d, ws, hs)
    plane(0, 1, 2, -1, -1, w, h, -d, ws, hs)
    return Geo(pos, nrm, uv, tris)


def rbox(w, h, d, r=0.004, seg=2):
    """three's RoundedBoxGeometry(w, h, d, seg, r) (the kit's rbox clamps r below the half sizes): a box whose edges
    and corners are rounded; each face's UV runs 0..1 over the face and its rounded margins up to the 45-degree
    seams, linear in arc length (what RoundedBoxGeometry.getUv intends)."""
    r = max(1e-4, min(r, w / 2 - 1e-4, h / 2 - 1e-4, d / 2 - 1e-4))
    total = seg * 2 + 1
    g = box_geo(1, 1, 1, total, total, total)
    half_seg = 0.5 / total
    p = g.pos
    n = p - np.sign(p) * half_seg
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    box = np.array([w, h, d]) / 2 - r
    pos = box * np.sign(p) + n * r
    # arc-length UVs per face
    per = len(p) // 6
    sizes = np.array([w, h, d])
    uv = np.zeros((len(p), 2))

    def coord(ax, face_ax, k):
        """signed arc-length position along axis ax on the face whose outward axis is face_ax, normalised 0..1"""
        L = sizes[ax]
        center = max(L - 2 * r, 0.0)
        arc = math.pi * r / 2
        q = pos[k, ax]
        tot = center + arc
        flat = np.clip(q, -center / 2, center / 2)
        extra = np.abs(q) - center / 2
        # angle of the normal away from the face, in the (ax, face_ax) plane
        ang = np.arctan2(np.abs(n[k, ax]), np.maximum(np.abs(n[k, face_ax]), 1e-12))
        s = np.where(extra > 0, np.sign(q) * (center / 2 + r * ang), flat)
        return (s + tot / 2) / tot
    faces = [(0, 2, 1, -1, 1), (0, 2, 1, 1, 1), (1, 0, 2, 1, -1), (1, 0, 2, 1, 1), (2, 0, 1, 1, 1), (2, 0, 1, -1, 1)]
    for f, (face_ax, uax, vax, us, vs) in enumerate(faces):
        k = np.arange(f * per, (f + 1) * per)
        u = coord(uax, face_ax, k)
        v = coord(vax, face_ax, k)
        uv[k, 0] = u if us > 0 else 1 - u
        uv[k, 1] = v if vs > 0 else 1 - v
    return Geo(pos, n, uv, g.tris)


def sphere_geo(radius=1, ws=32, hs=16, phi0=0.0, phil=2 * math.pi, th0=0.0, thl=math.pi):
    """three's SphereGeometry (UV: u along phi, v = 1 - theta / pi)."""
    pos, nrm, uv, grid = [], [], [], []
    th_end = min(th0 + thl, math.pi)
    idx = 0
    for iy in range(hs + 1):
        row = []
        v = iy / hs
        u_off = 0.5 / ws if (iy == 0 and th0 == 0) else (-0.5 / ws if (iy == hs and th_end == math.pi) else 0)
        for ix in range(ws + 1):
            u = ix / ws
            x = -radius * math.cos(phi0 + u * phil) * math.sin(th0 + v * thl)
            y = radius * math.cos(th0 + v * thl)
            z = radius * math.sin(phi0 + u * phil) * math.sin(th0 + v * thl)
            pos.append((x, y, z))
            nn = np.array([x, y, z]) / max(radius, 1e-12)
            nrm.append(tuple(nn))
            uv.append((u + u_off, 1 - v))
            row.append(idx)
            idx += 1
        grid.append(row)
    tris = []
    for iy in range(hs):
        for ix in range(ws):
            a, b = grid[iy][ix + 1], grid[iy][ix]
            c, d = grid[iy + 1][ix], grid[iy + 1][ix + 1]
            if iy != 0 or th0 > 0:
                tris.append((a, b, d))
            if iy != hs - 1 or th_end < math.pi:
                tris.append((b, c, d))
    return Geo(pos, nrm, uv, tris)


def cylinder_geo(rt=1, rb=1, h=1, rs=32, hs=1, open_ended=False, groups=False):
    """three's CylinderGeometry: torso, then the top cap, then the bottom cap. groups=True also returns the index
    ranges (start, count) of the three groups in triangle-corner units, as three's geometry.groups."""
    pos, nrm, uv, tris = [], [], [], []
    half = h / 2
    slope = (rb - rt) / h
    grid = []
    for y in range(hs + 1):
        row = []
        v = y / hs
        radius = v * (rb - rt) + rt
        for x in range(rs + 1):
            u = x / rs
            theta = u * 2 * math.pi
            s, c = math.sin(theta), math.cos(theta)
            pos.append((radius * s, -v * h + half, radius * c))
            n = np.array([s, slope, c])
            nrm.append(tuple(n / np.linalg.norm(n)))
            uv.append((u, 1 - v))
            row.append(len(pos) - 1)
        grid.append(row)
    for x in range(rs):
        for y in range(hs):
            a, b = grid[y][x], grid[y + 1][x]
            c, d = grid[y + 1][x + 1], grid[y][x + 1]
            if rt > 0 or y != 0:
                tris.append((a, b, d))
            if rb > 0 or y != hs - 1:
                tris.append((b, c, d))
    ranges = [(0, len(tris) * 3)]

    def cap(top):
        start = len(tris)
        radius = rt if top else rb
        sign = 1 if top else -1
        c0 = len(pos)
        for x in range(1, rs + 1):
            pos.append((0.0, half * sign, 0.0))
            nrm.append((0.0, sign, 0.0))
            uv.append((x / rs, 0.5))  # three's cap centre uv is (0.5, 0.5); overwritten below
            uv[-1] = (0.5, 0.5)
        ce = len(pos)
        for x in range(rs + 1):
            u = x / rs
            theta = u * 2 * math.pi
            cs, sn = math.cos(theta), math.sin(theta)
            pos.append((radius * sn, half * sign, radius * cs))
            nrm.append((0.0, sign, 0.0))
            uv.append(((cs * 0.5) + 0.5, (sn * 0.5 * sign) + 0.5))
        for x in range(rs):
            cidx, i = c0 + x, ce + x
            if top:
                tris.append((i, i + 1, cidx))
            else:
                tris.append((i + 1, i, cidx))
        ranges.append((start * 3, (len(tris) - start) * 3))
    if not open_ended:
        if rt > 0:
            cap(True)
        if rb > 0:
            cap(False)
    g = Geo(pos, nrm, uv, tris)
    return (g, ranges) if groups else g


def torus_geo(radius=1, tube=0.4, rs=12, ts=48, arc=2 * math.pi):
    pos, nrm, uv, tris = [], [], [], []
    for j in range(rs + 1):
        for i in range(ts + 1):
            u = i / ts * arc
            v = j / rs * math.pi * 2
            x = (radius + tube * math.cos(v)) * math.cos(u)
            y = (radius + tube * math.cos(v)) * math.sin(u)
            z = tube * math.sin(v)
            pos.append((x, y, z))
            cx, cy = radius * math.cos(u), radius * math.sin(u)
            n = np.array([x - cx, y - cy, z])
            nrm.append(tuple(n / max(np.linalg.norm(n), 1e-12)))
            uv.append((i / ts, j / rs))
    for j in range(1, rs + 1):
        for i in range(1, ts + 1):
            a = (ts + 1) * j + i - 1
            b = (ts + 1) * (j - 1) + i - 1
            c = (ts + 1) * (j - 1) + i
            d = (ts + 1) * j + i
            tris.append((a, b, d))
            tris.append((b, c, d))
    return Geo(pos, nrm, uv, tris)


def lathe_geo(points, segments=12, phi0=0.0, phil=2 * math.pi):
    """three's LatheGeometry (points: [(r, y)] in the XY plane, swept about Y), its normals as three r184 makes them:
    the first point takes its segment's normal (unit), a middle point the sum of its two segments' raw normals
    (normalized, so the longer segment leads), and the last point the last segment's raw normal, not normalized
    (Blender normalizes it when it becomes a custom normal)."""
    pos, uv, tris = [], [], []
    P = np.asarray(points, float)
    n_pts = len(P)
    prof_n = []
    prev = None
    for j in range(n_pts):
        if j == n_pts - 1:
            prof_n.append(prev.copy())
            continue
        dx, dy = P[j + 1] - P[j]
        raw = np.array([dy, -dx])
        nn = raw if j == 0 else raw + prev
        prof_n.append(nn / max(np.linalg.norm(nn), 1e-12))
        prev = raw
    nrm = []
    for i in range(segments + 1):
        phi = phi0 + i / segments * phil
        s, c = math.sin(phi), math.cos(phi)
        for j in range(n_pts):
            pos.append((P[j, 0] * s, P[j, 1], P[j, 0] * c))
            uv.append((i / segments, j / (n_pts - 1)))
            nx, ny = prof_n[j]
            nrm.append((nx * s, ny, nx * c))
    for i in range(segments):
        for j in range(n_pts - 1):
            base = j + i * n_pts
            a, b, c, d = base, base + n_pts, base + n_pts + 1, base + 1
            tris.append((a, b, d))
            tris.append((c, d, b))
    return Geo(pos, nrm, uv, tris)


def mesh_object(name, geo, materials=(), collection=None, parent=None, smooth=True, uv_name='UVMap'):
    """A Blender mesh object from a Geo (three axes -> Blender axes), its normals kept as custom normals, its
    attributes as POINT attributes (FLOAT, FLOAT_VECTOR, or FLOAT_COLOR for 'aTint')."""
    P = geo.pos
    N = geo.nrm
    pb = np.stack([P[:, 0], -P[:, 2], P[:, 1]], axis=1)
    nb = np.stack([N[:, 0], -N[:, 2], N[:, 1]], axis=1)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(pb))
    me.vertices.foreach_set('co', pb.astype(np.float32).ravel())
    T = geo.tris
    me.loops.add(len(T) * 3)
    me.loops.foreach_set('vertex_index', T.astype(np.int32).ravel())
    me.polygons.add(len(T))
    me.polygons.foreach_set('loop_start', np.arange(0, len(T) * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    uvl = me.uv_layers.new(name=uv_name)
    uvl.data.foreach_set('uv', geo.uv[T.ravel()].astype(np.float32).ravel())
    if smooth:
        me.polygons.foreach_set('use_smooth', np.ones(len(T), bool))
    me.normals_split_custom_set_from_vertices([tuple(v) for v in nb])
    for k, v in geo.attrs.items():
        v = np.asarray(v, np.float32)
        if v.ndim == 1 or v.shape[1] == 1:
            a = me.attributes.new(k, 'FLOAT', 'POINT')
            a.data.foreach_set('value', v.ravel())
        elif v.shape[1] == 2:
            a = me.attributes.new(k, 'FLOAT2', 'POINT')
            a.data.foreach_set('vector', v.ravel())
        else:
            a = me.attributes.new(k, 'FLOAT_VECTOR', 'POINT')
            a.data.foreach_set('vector', v[:, :3].ravel())
    for m in materials:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def mesh(geo, mat, seed=0, name='', collection=None, parent=None, smooth=True):
    """voder.js K.mesh(g, mat, seed, name): a runtime part with its own mesh and the material, the per-part seed on
    every vertex (attribute 'aSeed', the kit's seedN; no role material of the three machines reads it), casting and
    taking shadows."""
    return mesh_object(name, geo.copy().set_attr('aSeed', float(seed)), [mat], collection, parent, smooth=smooth)


# -------------------------------------------------------------------------------------------- node builder ---
def new_material(name):
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    return m


class NB:
    """Shader-graph builder for the TSL ports: float/vector/colour arithmetic where an argument is a socket, a number
    or a tuple. Every call returns an output socket."""

    def __init__(self, tree):
        self.t = tree
        self.k = 0

    def new(self, idname, **props):
        n = self.t.nodes.new(idname)
        n.location = (-1800 + (self.k // 24) * 230, 600 - (self.k % 24) * 150)
        self.k += 1
        for a, v in props.items():
            setattr(n, a, v)
        return n

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.t.links.new(v, sock)
        elif v is not None:
            if sock.type in ('VECTOR', 'RGBA') and isinstance(v, (int, float)):
                v = (v, v, v) if sock.type == 'VECTOR' else (v, v, v, 1.0)
            if sock.type == 'RGBA' and isinstance(v, (tuple, list)) and len(v) == 3:
                v = tuple(v) + (1.0,)
            sock.default_value = v

    @staticmethod
    def sock(coll, ident):
        return next(s for s in coll if s.identifier == ident)

    # floats
    def math(self, op, a, b=0.0, c=0.0, clamp=False):
        n = self.new('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.put(n.inputs[0], a)
        if len(n.inputs) > 1:
            self.put(n.inputs[1], b)
        if len(n.inputs) > 2:
            self.put(n.inputs[2], c)
        return n.outputs[0]

    def add(self, a, b):
        return self.math('ADD', a, b)

    def sub(self, a, b):
        return self.math('SUBTRACT', a, b)

    def mul(self, a, b):
        return self.math('MULTIPLY', a, b)

    def div(self, a, b):
        return self.math('DIVIDE', a, b)

    def madd(self, a, b, c):
        return self.math('MULTIPLY_ADD', a, b, c)

    def mn(self, a, b):
        return self.math('MINIMUM', a, b)

    def mx(self, a, b):
        return self.math('MAXIMUM', a, b)

    def clamp(self, x, lo=0.0, hi=1.0):
        n = self.new('ShaderNodeClamp')
        self.put(n.inputs['Value'], x)
        self.put(n.inputs['Min'], lo)
        self.put(n.inputs['Max'], hi)
        return n.outputs[0]

    def mix(self, a, b, t):
        """GLSL mix for floats: a + (b - a) t."""
        return self.madd(self.sub(b, a), t, a)

    def smoothstep(self, e0, e1, x):
        n = self.new('ShaderNodeMapRange', data_type='FLOAT', interpolation_type='SMOOTHSTEP', clamp=True)
        self.put(n.inputs['Value'], x)
        self.put(n.inputs['From Min'], e0)
        self.put(n.inputs['From Max'], e1)
        self.put(n.inputs['To Min'], 0.0)
        self.put(n.inputs['To Max'], 1.0)
        return n.outputs['Result']

    def step(self, edge, x):
        """GLSL step(edge, x) = x >= edge."""
        return self.math('SUBTRACT', 1.0, self.math('LESS_THAN', x, edge))

    def fract(self, x):
        return self.math('FRACT', x)

    def floor(self, x):
        return self.math('FLOOR', x)

    def mod(self, x, y):
        return self.math('FLOORED_MODULO', x, y)

    def sin(self, x):
        return self.math('SINE', x)

    def abs(self, x):
        return self.math('ABSOLUTE', x)

    def select(self, cond, a, b):
        """cond (0/1 float) ? a : b"""
        return self.mix(b, a, cond)

    # vectors / colours
    def vmath(self, op, a, b=None, scale=None):
        n = self.new('ShaderNodeVectorMath', operation=op)
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        if scale is not None:
            self.put(n.inputs['Scale'], scale)
        return n.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs['Vector']

    def vscale(self, v, s):
        return self.vmath('SCALE', v, scale=s)

    def vmul(self, a, b):
        return self.vmath('MULTIPLY', a, b)

    def vadd(self, a, b):
        return self.vmath('ADD', a, b)

    def vdot(self, a, b):
        return self.vmath('DOT_PRODUCT', a, b)

    def vmix(self, a, b, t):
        n = self.new('ShaderNodeMix', data_type='VECTOR', clamp_factor=False)
        self.put(self.sock(n.inputs, 'Factor_Float'), t)
        self.put(self.sock(n.inputs, 'A_Vector'), a)
        self.put(self.sock(n.inputs, 'B_Vector'), b)
        return self.sock(n.outputs, 'Result_Vector')

    def sep(self, v):
        n = self.new('ShaderNodeSeparateXYZ')
        self.put(n.inputs[0], v)
        return n.outputs['X'], n.outputs['Y'], n.outputs['Z']

    def comb(self, x, y, z):
        n = self.new('ShaderNodeCombineXYZ')
        self.put(n.inputs['X'], x)
        self.put(n.inputs['Y'], y)
        self.put(n.inputs['Z'], z)
        return n.outputs[0]

    def lum(self, c):
        return self.vdot(c, LUM)

    # sources
    def uv(self, layer='UVMap'):
        return self.new('ShaderNodeUVMap', uv_map=layer).outputs['UV']

    def texcoord(self, out='Object'):
        return self.new('ShaderNodeTexCoord').outputs[out]

    def geometry(self, out):
        return self.new('ShaderNodeNewGeometry').outputs[out]

    def attr(self, name, out='Fac'):
        return self.new('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name=name).outputs[out]

    def tex(self, image, vector, interpolation='Linear', extension='REPEAT'):
        n = self.new('ShaderNodeTexImage', image=image, interpolation=interpolation, extension=extension)
        self.put(n.inputs['Vector'], vector)
        return n

    def noise(self, vector, scale=1.0, detail=0.0, roughness=0.5, lacunarity=2.0, normalize=False, dims='3D'):
        """MaterialX noise in Blender's Noise Texture (fx/_noise.py: the same hash, gradients and fade):
        normalize=False sums octaves like mx_fractal_noise_float (signed); detail 0 + normalize = 0.5 mx_noise + 0.5."""
        n = self.new('ShaderNodeTexNoise', noise_dimensions=dims, noise_type='FBM', normalize=normalize)
        self.put(n.inputs['Vector'], vector)
        self.put(n.inputs['Scale'], scale)
        self.put(n.inputs['Detail'], detail)
        self.put(n.inputs['Roughness'], roughness)
        self.put(n.inputs['Lacunarity'], lacunarity)
        self.put(n.inputs['Distortion'], 0.0)
        return n.outputs['Fac']

    def fbm01(self, p, scale, octaves):
        """mx_fractal_noise_float(p * scale, octaves, 2.0, 0.5) * 0.5 + 0.5"""
        return self.madd(self.noise(p, scale, detail=octaves - 1, roughness=0.5, lacunarity=2.0), 0.5, 0.5)

    def driven(self, owner, prop, default=0.0, label=None):
        """A Value node that reads owner[prop] through a driver (the engine's uniform)."""
        n = self.new('ShaderNodeValue')
        n.label = label or prop
        n.outputs[0].default_value = default
        fc = n.outputs[0].driver_add('default_value')
        d = fc.driver
        d.type = 'AVERAGE'
        var = d.variables[0] if len(d.variables) else d.variables.new()
        var.name = 'v'
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'OBJECT'
        var.targets[0].id = owner
        var.targets[0].data_path = f'["{prop}"]'
        return n.outputs[0]


def principled(nb):
    out = nb.new('ShaderNodeOutputMaterial')
    b = nb.new('ShaderNodeBsdfPrincipled')
    nb.t.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    return b


# --------------------------------------------------------------------------------------------- materials ---
_IMG_CACHE = {}


def load_image(path, srgb=True):
    """An image file, loaded once per (path, colour space)."""
    key = (os.path.abspath(path), srgb)
    img = _IMG_CACHE.get(key)
    if img is not None:
        try:
            img.name
            return img
        except ReferenceError:
            pass
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    _IMG_CACHE[key] = img
    return img


def pbr(set_id, metal=False, rough=True, normal=True):
    """An AmbientCG set of the pack's tex/ folder: {'id', 'map', 'normal', 'rough', 'metal'} (images or None)."""
    base = os.path.join(TEX_DIR, set_id, set_id + '_')
    s = {'id': set_id, 'map': load_image(base + 'Color.jpg', srgb=True), 'normal': None, 'rough': None, 'metal': None}
    if normal and os.path.exists(base + 'NormalGL.jpg'):
        s['normal'] = load_image(base + 'NormalGL.jpg', srgb=False)
    if rough and os.path.exists(base + 'Roughness.jpg'):
        s['rough'] = load_image(base + 'Roughness.jpg', srgb=False)
    if metal and os.path.exists(base + 'Metalness.jpg'):
        s['metal'] = load_image(base + 'Metalness.jpg', srgb=False)
    return s


def role_mat(name, set=None, flat=0x808080, repeat=2.0, tint=0xffffff, lum=None, lum_contrast=1.0,
             rough_mul=1.0, rough_add=0.0, rough_min=0.03, rough_max=1.0, rough=0.5, metal=0.0, metal_map=False,
             normal_scale=1.0, clearcoat=0.0, coat_rough=0.08, mask=None, ao=1.0, grime=0.0, grime_color=0x2a241c,
             edge=0.0, edge_color=0x888888, edge_rough=0.35, edge_metal=None, edge_r=0.005, dust=0.0,
             dust_color=0x8e877a, imperf=None, imperf_repeat=1.5, imperf_amt=0.15, emissive=None, mottle=0.0,
             transparent=False, opacity=1.0, side='front', local=True, color_fn=None):
    """voder.js K.roleMat, as an EEVEE node material (see the module docstring for the AO and curvature terms).
    emissive: fn(nb) -> colour socket (the engine's emissive node). color_fn: fn(nb, col) -> col, a last colour
    override (the engine's own colorNode replacements). side ('front' | 'double', three's FrontSide / DoubleSide):
    EEVEE draws both faces of every role material (no backface culling); the pack's shells are closed, so 'front'
    looks the same, and a single-sided panel seen from behind shows its back instead of vanishing."""
    m = new_material(name)
    t = m.node_tree
    t.nodes.clear()
    nb = NB(t)
    b = principled(nb)
    uvT = nb.vscale(nb.uv('UVMap'), repeat)
    if set is not None:
        c = nb.tex(set['map'], uvT).outputs['Color']
        if lum:
            L = nb.lum(c)
            k = nb.madd(nb.sub(nb.div(L, lum), 1.0), lum_contrast, 1.0)
            col = nb.vscale(lin(tint), k)
        else:
            col = nb.vmul(c, lin(tint))
        if set['rough'] is not None:
            rg = nb.sep(nb.tex(set['rough'], uvT).outputs['Color'])[1]
            r = nb.madd(rg, rough_mul, rough_add)
        else:
            r = rough
    else:
        col = lin(flat)
        r = rough
    if set is not None and set.get('metal') is not None and metal_map:
        mt = nb.mul(nb.sep(nb.tex(set['metal'], uvT).outputs['Color'])[0], metal)
    else:
        mt = metal
    p = nb.texcoord('Object') if local else nb.geometry('Position')
    need_noise = mottle > 0 or grime > 0 or edge > 0 or dust > 0
    broad = nb.fbm01(p, 2.3, 3) if need_noise else None
    fine = nb.fbm01(p, 38.0, 2) if (mottle > 0 or edge > 0) else None
    if mottle > 0:
        col = nb.vscale(col, nb.madd(nb.sub(broad, 0.5), 2 * mottle, 1.0))
        col = nb.vscale(col, nb.madd(nb.sub(fine, 0.5), mottle, 1.0))
    if imperf is not None:
        im = nb.sep(nb.tex(imperf['map'], nb.vscale(nb.uv('UVMap'), imperf_repeat)).outputs['Color'])[0]
        r = nb.madd(im, imperf_amt, r)
    aoN, edgeM, cav = 1.0, 0.0, 1.0
    if mask is not None:
        mk = nb.tex(mask, nb.uv('UVMap.001'), extension='EXTEND').outputs['Color']
        aoN, edgeM, cav = nb.sep(mk)
    if grime > 0:
        g = nb.add(nb.mul(nb.sub(1.0, cav), 0.85), nb.mul(nb.sub(1.0, aoN), 0.45))
        g = nb.mul(nb.mul(g, nb.madd(broad, 0.8, 0.4)), grime)
        g = nb.clamp(g)
        col = nb.vmix(col, lin(grime_color), nb.mul(g, 0.7))
        r = nb.madd(g, 0.18, r)
    if edge > 0:
        curv = nb.attr('eido_curv')
        cv = nb.smoothstep(0.3, 0.85, nb.clamp(nb.mul(curv, edge_r)))
        if mask is not None:
            convex = nb.mx(cv, nb.mul(nb.mul(edgeM, nb.smoothstep(0.78, 0.97, cav)), 0.9))
        else:
            convex = cv
        chip = nb.mul(nb.mul(convex, nb.smoothstep(0.42, 0.62, fine)), nb.smoothstep(0.25, 0.6, broad))
        chip = nb.clamp(nb.mul(chip, edge))
        col = nb.vmix(col, lin(edge_color), chip)
        r = nb.mix(r, edge_rough, chip)
        if edge_metal is not None:
            mt = nb.mix(mt, edge_metal, chip)
    if dust > 0:
        nz = nb.sep(nb.geometry('Normal'))[2]
        up = nb.mul(nb.mul(nb.smoothstep(0.75, 0.98, nz), nb.madd(broad, 0.7, 0.3)), dust)
        if mask is not None:
            up = nb.mul(up, nb.madd(aoN, 0.5, 0.5))
        col = nb.vmix(col, lin(dust_color), nb.mul(up, 0.5))
        r = nb.mix(r, 0.85, up)
    if mask is not None and ao > 0:
        col = nb.vscale(col, nb.mix(1.0, nb.madd(cav, 0.35, 0.65), ao))
    if color_fn is not None:
        col = color_fn(nb, col)
    nb.put(b.inputs['Base Color'], col)
    nb.put(b.inputs['Roughness'], nb.clamp(r, rough_min, rough_max))
    nb.put(b.inputs['Metallic'], mt)
    if set is not None and set['normal'] is not None and normal_scale > 0:
        nm = nb.new('ShaderNodeNormalMap', space='TANGENT', uv_map='UVMap')
        nb.put(nm.inputs['Strength'], normal_scale)
        nb.put(nm.inputs['Color'], nb.tex(set['normal'], uvT).outputs['Color'])
        nb.put(b.inputs['Normal'], nm.outputs['Normal'])
    if clearcoat > 0:
        nb.put(b.inputs['Coat Weight'], clearcoat)
        nb.put(b.inputs['Coat Roughness'], coat_rough)
    if emissive is not None:
        nb.put(b.inputs['Emission Color'], emissive(nb))
        nb.put(b.inputs['Emission Strength'], 1.0)
    if transparent or opacity < 1:
        nb.put(b.inputs['Alpha'], opacity)
        m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    m['eido_role'] = name
    return m, nb, b


def glass_mat(name, color=0x0c0e11, opacity=0.3, rough=0.035, smudge=0.1, side='front', imperf=None):
    """voder.js K.glass: a thin dielectric pane at `opacity` (three: transparent, no depth write), its roughness
    broken by fingerprints / smears or a noise."""
    m = new_material(name)
    t = m.node_tree
    t.nodes.clear()
    nb = NB(t)
    b = principled(nb)
    if imperf is not None:
        im = nb.sep(nb.tex(imperf['map'], nb.vscale(nb.uv('UVMap'), 3.0)).outputs['Color'])[0]
        r = nb.madd(im, smudge, rough)
    else:
        n = nb.fbm01(nb.texcoord('Object'), 7.0, 3)
        r = nb.madd(nb.smoothstep(0.55, 0.85, n), smudge, rough)
    nb.put(b.inputs['Base Color'], lin(color))
    nb.put(b.inputs['Roughness'], r)
    nb.put(b.inputs['Metallic'], 0.0)
    nb.put(b.inputs['Alpha'], opacity)
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    m.use_transparency_overlap = side == 'double'
    m['eido_role'] = name
    return m


def decal_mat(name, image, rough=0.4, metal=0.0, emissive=None, alpha=True):
    """voder.js K.decalMat: canvas art on a GLB quad (lit, alpha-blended paint or print). The engine's polygonOffset
    (-2, -2) has no EEVEE counterpart and needs none: the pack's decal quads sit just off their panels, and the
    probes' close-ups show them without z-fighting."""
    m = new_material(name)
    t = m.node_tree
    t.nodes.clear()
    nb = NB(t)
    b = principled(nb)
    tx = nb.tex(image, nb.uv('UVMap'), extension='EXTEND')
    nb.put(b.inputs['Base Color'], tx.outputs['Color'])
    nb.put(b.inputs['Roughness'], rough)
    nb.put(b.inputs['Metallic'], metal)
    if alpha:
        nb.put(b.inputs['Alpha'], tx.outputs['Alpha'])
        m.surface_render_method = 'BLENDED'
    if emissive is not None:
        nb.put(b.inputs['Emission Color'], emissive(nb, tx))
        nb.put(b.inputs['Emission Strength'], 1.0)
    m.use_backface_culling = False
    m['eido_role'] = name
    return m


# ------------------------------------------------------------------------------------------ curvature ---
def write_curvature(ob, name='eido_curv'):
    """The engine's curvature() (dFdx/dFdy of the interpolated normal against position, 1/m, + convex) as a
    per-triangle FACE_CORNER attribute: the trace of the shape operator from the corner normals, in object space
    scaled to world metres by the object's scale."""
    me = ob.data
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    if nt == 0:
        return None
    tl = np.empty(nt * 3, np.int32)
    me.loop_triangles.foreach_get('loops', tl)
    tl = tl.reshape(-1, 3)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', lv)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    cn = np.empty(len(me.loops) * 3)
    me.corner_normals.foreach_get('vector', cn)
    cn = cn.reshape(-1, 3)
    P = co[lv[tl]]
    N = cn[tl]
    e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    n1, n2 = N[:, 1] - N[:, 0], N[:, 2] - N[:, 0]
    g11 = (e1 * e1).sum(1)
    g12 = (e1 * e2).sum(1)
    g22 = (e2 * e2).sum(1)
    det = g11 * g22 - g12 * g12
    b11 = (e1 * n1).sum(1)
    b12 = (e1 * n2).sum(1)
    b21 = (e2 * n1).sum(1)
    b22 = (e2 * n2).sum(1)
    # trace(G^-1 B) with G the Gram matrix of (e1, e2) and B_ij = e_i . n_j
    tr = np.where(det > 1e-20, (g22 * b11 - g12 * b21 - g12 * b12 + g11 * b22) / np.maximum(det, 1e-20), 0.0)
    s = max(ob.matrix_world.to_scale()) or 1.0
    tr = tr / s
    vals = np.zeros(len(me.loops), np.float32)
    vals[tl.ravel()] = np.repeat(tr, 3)
    a = me.attributes.get(name) or me.attributes.new(name, 'FLOAT', 'CORNER')
    a.data.foreach_set('value', vals)
    return tr


# --------------------------------------------------------------------------------------------- GLB import ---
_SUFFIX = re.compile(r'\.\d{3}$')


def base_name(n):
    return _SUFFIX.sub('', n)


def import_glb(path, name, collection=None, scene=None):
    """Import a pack GLB into its own collection under one root Empty (the machine's group). Returns
    (root, nodes {original node name: object}). Imported objects keep their glTF names when free; a second
    machine's '.001' suffixes are looked through."""
    scene = scene or bpy.context.scene
    col = collection or bpy.data.collections.new(name)
    if col.name not in scene.collection.children and col is not scene.collection:
        scene.collection.children.link(col)
    before = set(bpy.data.objects)
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    res = bpy.ops.import_scene.gltf(filepath=str(path))
    if 'FINISHED' not in res:
        raise RuntimeError(f'{path}: the glTF importer refused it ({res})')
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.25
    col.objects.link(root)
    for o in new:
        if o.parent is None:
            o.parent = root
    root['eido_src_asset'] = os.path.abspath(path)
    root['eido_loaded_asset'] = True
    nodes = {}
    for o in new:
        o['eido_loaded_asset'] = True
        nodes.setdefault(base_name(o.name), o)
    return root, nodes, col


def role_of(mat):
    return base_name(mat.name).replace('era1_', '', 1) if mat else ''


def apply_roles(nodes, R, fallback, special=None, no_shadow=r'decal|glass|smoked|reelclear|acrylic|chad'):
    """Swap each slot's placeholder 'era1_<role>' material for the role material R[role] (voder.js's traverse);
    special(obj, role) may pick another. Returns the roles that had no material (the engine's warning)."""
    missing = set()
    pat = re.compile(no_shadow)
    old = set()
    for o in nodes.values():
        if o.type != 'MESH':
            continue
        roles = []
        for s in o.material_slots:
            role = role_of(s.material)
            roles.append(role)
            mat = special(o, role) if special else None
            if mat is None:
                mat = R.get(role)
            if mat is None:
                missing.add(role)
                mat = fallback
            if s.material is not None:
                old.add(s.material)
            s.link = 'DATA'
            s.material = mat
        o['eido_roles'] = ','.join(roles)
        if roles and all(pat.search(r) for r in roles):
            o.visible_shadow = False
    for m in old:
        if m.users == 0:
            bpy.data.materials.remove(m)
    return missing


def roles_of(o):
    return [r for r in str(o.get('eido_roles', '')).split(',') if r]


def seat_decals(nodes, max_gap=0.002, standoff=0.0006, min_gap=0.0002):
    """Lay a decal quad that floats off its panel back onto it, and lift one that grazes it. The pack's decal quads
    stand 0.1 to 0.9 mm off their panels, and the engine's polygonOffset (-2, -2) drew them in front whatever the
    depth said; EEVEE has no depth bias, so a corner closer than min_gap (the Voder's panel labels touch the panel
    at 0.01 mm) moves out to min_gap. The teletype's TT monogram stands vertical 9 to 16 mm in front of the cover's
    12.7-degree face, in the GLB and so in the engine (from the side, a plate in mid-air): when any corner is further
    than max_gap, every corner moves onto the surface behind it, `standoff` in front. Distances run along the quad's
    normal; the UVs, so the art, stay. Returns {object name: (largest gap before, smallest gap before)} in metres for
    the quads it moved."""
    decals = [o for o in nodes.values() if o.type == 'MESH' and roles_of(o)
              and all(r.startswith('decal') for r in roles_of(o))]
    moved = {}
    if not decals:
        return moved
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    for o in decals:
        me = o.data
        if not len(me.polygons):
            continue
        mw = o.matrix_world.copy()
        n = (mw.to_3x3().inverted().transposed() @ me.polygons[0].normal).normalized()
        o.hide_set(True)                                 # the rays must not stop on the quad itself
        dg = bpy.context.evaluated_depsgraph_get()
        gaps, hits = [], []
        for v in me.vertices:
            p = mw @ v.co
            ok, loc, _nn, _i, _ob, _m = scene.ray_cast(dg, p + n * 0.002, -n, distance=0.05)
            gap = (p - loc).dot(n) if ok else None
            gaps.append(gap)
            hits.append(loc if ok else None)
        o.hide_set(False)
        if any(g is None for g in gaps) or (max(gaps) <= max_gap and min(gaps) >= min_gap):
            continue
        inv = mw.inverted()
        seat = max(gaps) > max_gap
        for v, loc, g in zip(me.vertices, hits, gaps):
            if seat:
                v.co = inv @ (loc + n * standoff)
            elif g < min_gap:
                v.co = inv @ (loc + n * min_gap)
        me.update()
        fn = me.polygons[0].normal.copy()
        me.normals_split_custom_set_from_vertices([tuple(fn)] * len(me.vertices))
        moved[o.name] = (max(gaps), min(gaps))
    return moved


def json_load(rel):
    with open(os.path.join(PACK, rel), encoding='utf-8') as f:
        return json.load(f)


# ------------------------------------------------------------------------------------------- the machine ---
def _snake(k):
    return re.sub(r'(?<=[a-z0-9])([A-Z])', lambda m: '_' + m.group(1).lower(), k)


class Machine:
    """What every ported era-1 machine returns (the JS build() result): group (the root Empty), parts,
    update(t, state, ctx=None, frame=None, key=True), animate(state, frames), dispose().

    update(t, state) is the engine's update: it sets the machine at film time t (seconds from the scene's first
    frame) and KEYS everything it set at the frame of t (frame= wins; ctx routes the keys through ctx.key, whose
    runner sets their interpolation), LINEAR unless a channel asks for CONSTANT, so a saved .blend plays and renders
    any frame on its own. key=False only poses (a still). State keys may be the JS's camelCase (tapeSpeed) or
    snake_case (tape_speed). Call it in time order, as the engine did (the mainframe integrates its tape speed)."""

    name = 'machine'

    def __init__(self, root, collection, scene=None, interpolation='LINEAR', ctx=None):
        self.group = root
        self.collection = collection
        self.ctx = ctx                                  # a scene's ctx: the default for every update's keys
        self.scene = scene or (ctx.scene if ctx is not None else bpy.context.scene)
        self.interpolation = interpolation
        self.parts = {}
        self.keyer = Keyer()
        self.made = {'materials': [], 'images': [], 'meshes': [], 'node_groups': []}
        self._touched = []
        self.updates = 0

    # ---- time and keys
    def frame_at(self, t, ctx=None):
        ctx = ctx or self.ctx
        if ctx is not None:
            return int(ctx.frame_at(t))
        sc = self.scene
        return common.frame_at(t, scene_fps(sc), sc.frame_start)

    def time_at(self, frame):
        sc = self.scene
        return common.time_at(frame, scene_fps(sc), sc.frame_start)

    def touch(self, target, path, interpolation=None):
        """Record that update() set target.path (keyed at the update's frame unless key=False)."""
        self._touched.append((target, path, interpolation))

    @staticmethod
    def normalize_state(state=None, kw=None):
        """The update state as one dict with snake_case keys (tapeSpeed -> tape_speed, nChars -> n_chars)."""
        st = {}
        for src in (state or {}), (kw or {}):
            for k, v in src.items():
                st[_snake(k)] = v
        return st

    def update(self, t, state=None, ctx=None, frame=None, key=True, **kw):
        st = self.normalize_state(state, kw)
        ctx = ctx or self.ctx
        self._touched = []
        f = frame if frame is not None else self.frame_at(t, ctx)
        self._frame = f
        out = self._update(float(t), st)
        if key:
            seen = set()
            for target, path, interp in self._touched:
                k = (target.as_pointer(), path)
                if k in seen:
                    continue
                seen.add(k)
                self.keyer.key(target, path, frame=f, ctx=ctx, interpolation=interp or self.interpolation)
        self._touched = []
        self.updates += 1
        return out

    def _update(self, t, st):
        raise NotImplementedError

    def animate(self, state=None, frames=None, simplify=True):
        """Key update(t, state(t)) on every frame of `frames` (default the scene's range), in time order, then drop
        the keys that change nothing. state: a dict or fn(t) -> dict. Returns the keys left."""
        sc = self.scene
        f0, f1 = frame_range(frames, sc)
        for f in range(f0, f1 + 1):
            t = self.time_at(f)
            st = state(t) if callable(state) else (state or {})
            self.update(t, st, frame=f)
        return self.keyer.finish(simplify=simplify)

    def dispose(self):
        """Remove the machine (the JS dispose): its objects and collection, the meshes, the materials on them and the
        ones it made, and every image those materials read (the pack's sets too), each once nothing else uses it."""
        objs = [self.group] + list(self.group.children_recursive)
        meshes = {o.data for o in objs if o.type == 'MESH'}
        actions = {o.animation_data.action for o in objs if o.animation_data and o.animation_data.action}
        mats = {m.as_pointer(): m for o in objs if o.type == 'MESH' for m in o.data.materials if m}
        mats.update({m.as_pointer(): m for m in self.made['materials'] if _alive_id(m)})
        imgs = {i.as_pointer(): i for i in self.made['images'] if _alive_id(i)}
        for m in mats.values():
            for n in (m.node_tree.nodes if m.node_tree else ()):
                if getattr(n, 'image', None) is not None:
                    imgs[n.image.as_pointer()] = n.image
        self.made['materials'] = list(mats.values())
        self.made['images'] = list(imgs.values())
        for o in objs:
            bpy.data.objects.remove(o, do_unlink=True)
        for me in meshes:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        for a in actions:                                # the keys update() made
            if a.users == 0:
                bpy.data.actions.remove(a)
        for kind, coll in (('materials', bpy.data.materials), ('images', bpy.data.images),
                           ('node_groups', bpy.data.node_groups)):
            for d in {d.as_pointer(): d for d in self.made[kind] if _alive_id(d)}.values():
                if d.users == 0:
                    coll.remove(d)
            self.made[kind] = []
        if self.collection is not None and not self.collection.all_objects and self.collection.users <= 1:
            bpy.data.collections.remove(self.collection)


# ===================================================================================================================
# THE VODER
# ===================================================================================================================

# Dudley's ten filter bands (Hz), keys 1-10 left to right.
BANDS = [[0, 225], [225, 450], [450, 700], [700, 1000], [1000, 1400],
         [1400, 2000], [2000, 2700], [2700, 3800], [3800, 5400], [5400, 7500]]

# Demo phrase: illustrative fingerings in the spirit of the Voder charts, not a transcription. k: 1-based band ->
# depth; w = wrist bar (1 buzz, 0 hiss); q = quiet key; st = stop key index.
PH = {
    'sh': {'k': {7: 0.55, 8: 0.9, 9: 0.7}, 'w': 0},
    'ee': {'k': {1: 0.45, 2: 0.35, 7: 0.85, 8: 0.45}, 'w': 1},
    's': {'k': {9: 0.75, 10: 1.0}, 'w': 0},
    'aw': {'k': {1: 0.55, 3: 0.95, 4: 0.7}, 'w': 1},
    'm': {'k': {1: 0.9}, 'w': 1, 'q': 1},
    'k': {'k': {5: 0.5}, 'w': 0, 'st': 2},
    'a': {'k': {2: 0.4, 4: 0.9, 6: 0.55}, 'w': 1},
    't': {'k': {9: 0.4}, 'w': 0, 'st': 0},
    '_': {'k': {}, 'w': 0},
}
SEQ = [('sh', 0.17), ('ee', 0.27), ('_', 0.07), ('s', 0.15), ('aw', 0.30), ('_', 0.05), ('m', 0.12),
       ('ee', 0.32), ('_', 0.30), ('k', 0.08), ('a', 0.26), ('t', 0.09), ('_', 0.40)]
SEQ_T = []
_acc = 0.0
for _p, _d in SEQ:
    SEQ_T.append((_p, _acc, _acc + _d))
    _acc += _d
SEQ_LEN = SEQ_T[-1][2]

# the registry's record (index.js MACHINES.voder) in Blender axes: footprint (x width, y depth, z height), centre (x, y)
MACHINE = {'year': 1939, 'title': "Bell Labs Voder (New York World's Fair)", 'era': 1,
           'footprint': (1.28, 1.32, 1.70), 'center': (0.0, 0.32)}


def pattern(t):
    """voder.js pattern(t): the demo fingering at t (loops every SEQ_LEN s) -> {keys[10], stops[3], quiet, wrist,
    pedal, level}."""
    tt = ((t % SEQ_LEN) + SEQ_LEN) % SEQ_LEN
    keys = [0.0] * 10
    stops = [0.0, 0.0, 0.0]
    wrist = quiet = voiced = loud = 0.0
    for ph, a, b in SEQ_T:
        env = sstep(a - 0.03, a + 0.03, tt) * (1 - sstep(b - 0.04, b + 0.04, tt))
        if env <= 0:
            continue
        P = PH[ph]
        for k, v in P['k'].items():
            keys[k - 1] = max(keys[k - 1], v * env)
        if 'st' in P:
            stops[P['st']] = max(stops[P['st']], env)
        if P.get('q'):
            quiet = max(quiet, env)
        wrist = max(wrist, P['w'] * env)
        if ph != '_':
            loud = max(loud, env)
            if P['w']:
                voiced = max(voiced, env)
    pedal = clamp01(0.42 + 0.18 * math.sin(tt * 3.1) + 0.22 * sstep(0.62, 0.72, tt) * (1 - sstep(0.9, 1.2, tt)))
    level = clamp01(loud * (0.55 + 0.4 * voiced) * (1 - 0.45 * quiet))
    return {'keys': keys, 'stops': stops, 'quiet': quiet, 'wrist': wrist, 'pedal': pedal, 'level': level}


DECO = '"Bahnschrift", "Segoe UI", Arial, sans-serif'
KEY_MAX, STOP_MAX, WRIST_MAX = 0.10, 0.12, 0.12


def _draw_panel(L):
    def draw(ctx, w, h):
        P = L['panel']

        def px(x):
            return (x / P['w'] + 0.5) * w

        def py(s):
            return (0.5 - s / P['h']) * h
        ctx.clearRect(0, 0, w, h)
        ctx.strokeStyle = 'rgba(214,202,172,0.92)'
        ctx.lineWidth = 2.5
        ctx.strokeRect(22, 22, w - 44, h - 44)
        ctx.lineWidth = 1.2
        ctx.strokeRect(31, 31, w - 62, h - 62)
        ctx.fillStyle = 'rgba(214,202,172,0.92)'
        for i in range(3):
            ctx.fillRect(44, 46 + i * 9, 110 - i * 28, 3)
            ctx.fillRect(w - 154 + i * 28, h - 52 - i * 9, 110 - i * 28, 3)
        ctx.textBaseline = 'middle'

        def lab(txt, x, s, size=20, sp=5):
            ctx.font = f'600 {size}px {DECO}'
            spaced_text(ctx, txt, px(x), py(s), sp)
        kn = P['knobs']
        lab('PITCH', kn['pitch'], -0.058)
        lab('GAIN', kn['gain'], -0.058)
        lab('LOW', kn['pitch'] - 0.05, -0.030, 13, 2)
        lab('HIGH', kn['pitch'] + 0.05, -0.030, 13, 2)
        lab('0', kn['gain'] - 0.046, -0.030, 13, 2)
        lab('10', kn['gain'] + 0.046, -0.030, 13, 2)
        lab('NORMAL', P['whisper'][0], 0.040, 15, 3)
        lab('WHISPER', P['whisper'][0], -0.040, 15, 3)
        lab('PILOT', P['pilot']['x'], 0.040, 15, 3)
        lab('LEVEL', P['dial']['x'], -0.082, 18, 5)
        b = P['bank']
        for i, t in enumerate(['ON', 'VIB', 'HISS', 'BUZZ', 'LINE']):
            lab(t, b['x0'] + i * 0.031, b['s'] + 0.031, 11, 1)
        ctx.strokeStyle = 'rgba(214,202,172,0.92)'
        for k in range(11):
            for kx in (kn['pitch'], kn['gain']):
                a = math.pi * (0.75 + 1.5 * k / 10)
                cx, cy = px(kx), py(0)
                r0, r1 = 0.037 / P['w'] * w, 0.042 / P['w'] * w
                ctx.lineWidth = 2.2 if k % 5 == 0 else 1.2
                ctx.beginPath()
                ctx.moveTo(cx + math.cos(a) * r0, cy + math.sin(a) * r0)
                ctx.lineTo(cx + math.cos(a) * r1, cy + math.sin(a) * r1)
                ctx.stroke()
    return draw


def _draw_strip(L):
    def draw(ctx, w, h):
        S = L['keystrip']
        ctx.fillStyle = '#e8dbba'
        ctx.fillRect(0, 0, w, h)
        g = ctx.createLinearGradient(0, 0, 0, h)
        g.addColorStop(0, 'rgba(255,255,255,0.18)')
        g.addColorStop(1, 'rgba(0,0,0,0.12)')
        ctx.fillStyle = g
        ctx.fillRect(0, 0, w, h)
        ctx.fillStyle = '#1b1612'
        ctx.textBaseline = 'middle'
        ctx.textAlign = 'center'

        def px(x):
            return (x / S['w'] + 0.5) * w
        ctx.font = f'600 19px {DECO}'
        for i, x in enumerate(S['keyX']):
            ctx.fillText(str(i + 1), px(x), h / 2 + 1)
        ctx.font = f'600 12px {DECO}'
        for i, s in enumerate(['T-D', 'P-B', 'K-G']):
            ctx.fillText(s, px(S['stopX'][i]), h / 2 + 1)
        ctx.fillText('Q', px(S['quietX']), h / 2 + 1)
        ctx.fillRect(4, 3, w - 8, 1.4)
        ctx.fillRect(4, h - 4.4, w - 8, 1.4)
    return draw


def _draw_name(ctx, w, h):
    ctx.clearRect(0, 0, w, h)
    gold = ctx.createLinearGradient(0, 0, w, h)
    gold.addColorStop(0, '#caa05a')
    gold.addColorStop(0.45, '#f1d692')
    gold.addColorStop(1, '#b8904c')
    ctx.fillStyle = gold
    ctx.textBaseline = 'middle'
    ctx.font = f'700 76px {DECO}'
    spaced_text(ctx, 'VODER', w / 2, h / 2 - 8, 22)
    ctx.font = f'600 17px {DECO}'
    spaced_text(ctx, 'BELL TELEPHONE LABORATORIES', w / 2, h - 30, 3)
    ctx.font = f'700 76px {DECO}'
    for i in range(3):
        ctx.fillRect(20, 42 + i * 13, 56 - i * 14, 5)
        ctx.fillRect(w - 76 + i * 14, h - 47 - i * 13, 56 - i * 14, 5)
    ctx.strokeStyle = gold
    ctx.lineWidth = 4
    ctx.strokeRect(8, 8, w - 16, h - 16)


def _draw_dial(ctx, w, h):
    # the card quad is 0.128 m (it overfills the 0.124 m bore); the needle pivot is 0.0232 m below centre
    k = 0.116 / 0.128
    cx, cy = w / 2, h * 0.70
    g = ctx.createRadialGradient(cx, h * 0.45, 20, cx, h * 0.5, w * 0.55)
    g.addColorStop(0, '#f6ead0')
    g.addColorStop(1, '#d9c59e')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, w, h)
    ctx.save()
    ctx.translate(cx, h / 2)
    ctx.scale(k, k)
    ctx.translate(-cx, -h / 2)
    Rr, a0, a1 = w * 0.36, -math.pi / 2 - 0.87, -math.pi / 2 + 0.87
    ctx.strokeStyle = '#1c1611'
    ctx.lineWidth = 4
    ctx.beginPath()
    ctx.arc(cx, cy, Rr, a0, a1)
    ctx.stroke()
    ctx.strokeStyle = '#a3261c'
    ctx.lineWidth = 14
    ctx.beginPath()
    ctx.arc(cx, cy, Rr + 9, a0 + (a1 - a0) * 0.78, a1)
    ctx.stroke()
    ctx.fillStyle = '#1c1611'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = f'600 26px {DECO}'
    for i in range(21):                         # the ticks keep the red arc's stroke, as voder.js draws them
        a = a0 + (a1 - a0) * i / 20
        big = i % 4 == 0
        ctx.lineWidth = 4 if big else 2
        ctx.beginPath()
        ctx.moveTo(cx + math.cos(a) * (Rr - (30 if big else 16)), cy + math.sin(a) * (Rr - (30 if big else 16)))
        ctx.lineTo(cx + math.cos(a) * Rr, cy + math.sin(a) * Rr)
        ctx.stroke()
        if big:
            v = i / 2
            ctx.fillText(str(int(v)) if v == int(v) else str(v), cx + math.cos(a) * (Rr - 56), cy + math.sin(a) * (Rr - 56))
    ctx.font = f'700 34px {DECO}'
    spaced_text(ctx, 'LEVEL', cx, h * 0.83, 10)
    ctx.font = f'600 16px {DECO}'
    spaced_text(ctx, 'SPEECH  OUTPUT', cx, h * 0.91, 5)
    ctx.restore()


def _draw_bell(ctx, w, h):
    """The Bell System roundel, 1939 style (homage): a bell in a double ring, BELL SYSTEM lettered round the top."""
    cx, cy, blue, cream = w / 2, h / 2, '#1d3f73', '#efe6cf'
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = cream
    ctx.beginPath()
    ctx.arc(cx, cy, 236, 0, math.pi * 2)
    ctx.fill()
    ctx.strokeStyle = blue
    ctx.lineWidth = 16
    ctx.beginPath()
    ctx.arc(cx, cy, 226, 0, math.pi * 2)
    ctx.stroke()
    ctx.lineWidth = 6
    ctx.beginPath()
    ctx.arc(cx, cy, 160, 0, math.pi * 2)
    ctx.stroke()
    ctx.fillStyle = blue
    ctx.font = f'700 46px {DECO}'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'

    def arc_text(txt, r, a0, a1, flip):
        n = len(txt)
        for i in range(n):
            a = a0 + (a1 - a0) * (0.5 if n == 1 else i / (n - 1))
            ctx.save()
            ctx.translate(cx + math.cos(a) * r, cy + math.sin(a) * r)
            ctx.rotate(a + (-math.pi / 2 if flip else math.pi / 2))
            ctx.fillText(txt[i], 0, 0)
            ctx.restore()
    arc_text('BELL SYSTEM', 193, -math.pi * 0.85, -math.pi * 0.15, False)
    ctx.font = f'600 26px {DECO}'
    arc_text('LABORATORIES', 196, math.pi * 0.78, math.pi * 0.22, True)
    ctx.beginPath()
    ctx.moveTo(cx - 92, cy + 76)
    ctx.bezierCurveTo(cx - 92, cy + 56, cx - 66, cy + 44, cx - 64, cy + 6)
    ctx.bezierCurveTo(cx - 62, cy - 58, cx - 40, cy - 96, cx, cy - 98)
    ctx.bezierCurveTo(cx + 40, cy - 96, cx + 62, cy - 58, cx + 64, cy + 6)
    ctx.bezierCurveTo(cx + 66, cy + 44, cx + 92, cy + 56, cx + 92, cy + 76)
    ctx.closePath()
    ctx.fill()
    ctx.fillRect(cx - 12, cy - 118, 24, 24)
    ctx.beginPath()
    ctx.arc(cx, cy + 96, 16, 0, math.pi * 2)
    ctx.fill()
    ctx.fillStyle = cream
    ctx.fillRect(cx - 96, cy + 70, 192, 4)


class Voder(Machine):
    """voder.build()'s result. update(t, state): see the module docstring; returns the level it set."""
    name = 'voder'

    def _update(self, t, s):
        P = self.parts
        self.power.value = clamp01(s['power'] if s.get('power') is not None else 1.0)
        voice = clamp01(s['voice']) if s.get('voice') is not None else None
        src = s
        if s.get('keys') is None and voice is not None:  # it sings: its own fingering, gated by the voice (as the
            #                                              JS's !s.keys: an empty list given is played, all keys up)
            p = pattern(t)
            g = sstep(0.02, 0.35, voice)
            src = {'keys': [k * g for k in p['keys']], 'stops': [k * g for k in p['stops']], 'quiet': p['quiet'] * g,
                   'wrist': p['wrist'] * g, 'pedal': 0.3 + (p['pedal'] - 0.3) * g, 'level': voice}
        kv = src.get('keys') or []
        total = 0.0
        for i in range(10):
            v = clamp01(kv[i] if i < len(kv) and kv[i] is not None else 0.0)
            set_turn(P['keys'][i], 'x', KEY_MAX * v)
            total += v
        st = src.get('stops') or []
        for i in range(3):
            set_turn(P['stop_keys'][i], 'x', STOP_MAX * clamp01(st[i] if i < len(st) and st[i] is not None else 0.0))
        quiet = clamp01(src.get('quiet') or 0.0)
        set_turn(P['quiet_key'], 'x', STOP_MAX * quiet)
        set_turn(P['wrist_bar'], 'x', WRIST_MAX * clamp01(src.get('wrist') or 0.0))
        set_turn(P['pedal'], 'x', 0.22 - 0.19 * clamp01(src['pedal'] if src.get('pedal') is not None else 0.3))
        level = clamp01(src['level']) if src.get('level') is not None else clamp01(total * 0.3 * (1 - 0.45 * quiet))
        self.level.value = level
        # needle: 0 -> left stop, 1 -> right, a deterministic flutter while it speaks
        set_turn(P['dial']['needle'], 'y', 0.87 - 1.74 * clamp01(level * 0.92 + 0.02 * math.sin(t * 23.0) * level))
        for o in self._movers:
            self.touch(o, 'rotation_euler')
        self.touch(self.group, self.power.path)
        self.touch(self.group, self.level.path)
        return level

    pattern = staticmethod(pattern)


def build(glb=None, power=1.0, name='voder', collection=None, scene=None, location=(0.0, 0.0, 0.0), ctx=None):
    """voder.js build(THREE, opts): opts.glb (another GLB path), opts.power. ctx: a scene's ctx (its scene, and the
    default route of every update's keys). Returns a Voder. `power` holds until the first update sets one (voder.js's
    own build-time update(0, {}) put its uniform back to 1 at once)."""
    scene = scene or (ctx.scene if ctx is not None else bpy.context.scene)
    path = glb or os.path.join(PACK, 'voder.glb')
    root, nodes, col = import_glb(path, name, collection, scene)
    root.location = location
    L = json_load('voder_layout.json')
    vm = Voder(root, col, scene, ctx=ctx)
    vm.power = Uniform(root, 'power', power, description='0..1: the pilot jewel, the dial and the grille light')
    vm.level = Uniform(root, 'level', 0.0, description='0..1: the speech level (needle, dial and grille glow)')
    mask = load_image(os.path.join(PACK, 'voder_mask.png'), srgb=False)
    T = {
        'enamel': pbr('PaintedMetal002'), 'gloss': pbr('Plastic003_1k'), 'satin': pbr('Plastic006_1k'),
        'plastic': pbr('Plastic013B_1k'), 'chrome': pbr('Metal049A'), 'metal': pbr('Metal041A'),
        'crinkle': pbr('Metal046A'), 'rubber': pbr('Rubber004_1k'), 'fabric': pbr('Fabric030'),
        'prints': pbr('Fingerprints002_1k', normal=False, rough=False),
        'smear': pbr('Smear004_1k', normal=False, rough=False),
    }
    n = name

    def rm(role, **o):
        m, nb, b = role_mat(f'{n}_{role}', mask=o.pop('mask', mask), **o)
        vm.made['materials'].append(m)
        return m

    def pw(nb):
        return nb.driven(root, 'power', power)

    def lv(nb):
        return nb.driven(root, 'level', 0.0)
    R = {
        'cream': rm('cream', set=T['enamel'], lum=0.181, lum_contrast=0.07, mottle=0.05, tint=0xe4d6b6, repeat=1.6,
                    rough_mul=1.1, rough_add=0.08, normal_scale=0.6, clearcoat=0.35, coat_rough=0.12, grime=0.65,
                    grime_color=0x4a3c2a, edge=0.9, edge_color=0x6d6150, edge_rough=0.6, dust=0.3,
                    imperf=T['smear'], imperf_amt=0.12),
        'lacquer': rm('lacquer', set=T['gloss'], lum=0.006, lum_contrast=0.25, tint=0x100d0d, repeat=1.4,
                      rough_mul=0.6, rough_add=0.02, normal_scale=0.35, clearcoat=0.9, coat_rough=0.04, grime=0.25,
                      edge=0.7, edge_color=0x4a3a2b, edge_rough=0.5, dust=0.25, dust_color=0x5e574d,
                      imperf=T['prints'], imperf_repeat=2.2, imperf_amt=0.35),
        'satin': rm('satin', set=T['satin'], lum=0.002, lum_contrast=0.2, tint=0x141112, repeat=2.0, rough_mul=1.2,
                    rough_add=0.08, normal_scale=0.5, clearcoat=0.3, coat_rough=0.3, grime=0.3, edge=0.6,
                    edge_color=0x4d3f31, dust=0.2, imperf=T['prints'], imperf_repeat=3.0, imperf_amt=0.25),
        'chrome': rm('chrome', set=T['chrome'], tint=0xffffff, repeat=2.5, metal=1, rough_mul=1.0, rough_add=0.05,
                     normal_scale=0.4, grime=0.35, grime_color=0x3a342a, imperf=T['prints'], imperf_repeat=3.5,
                     imperf_amt=0.25),
        'ivory': rm('ivory', set=T['plastic'], lum=0.807, lum_contrast=1.5, tint=0xeee0bf, repeat=6.0, rough_mul=0.45,
                    normal_scale=0.4, clearcoat=0.6, coat_rough=0.06, grime=0.35, grime_color=0x8a7550, edge=0.4,
                    edge_color=0xcfb88a, edge_rough=0.25),
        'bakelite': rm('bakelite', set=T['gloss'], lum=0.006, lum_contrast=0.5, tint=0x2b1a10, repeat=4.0,
                       rough_mul=0.8, normal_scale=0.5, clearcoat=0.5, coat_rough=0.1, grime=0.3, edge=0.5,
                       edge_color=0x6a4428, edge_rough=0.3),
        'rubber': rm('rubber', set=T['rubber'], lum=0.025, lum_contrast=0.6, tint=0x1a1918, repeat=5.0,
                     normal_scale=1.0, grime=0.3, dust=0.4),
        'crinkle': rm('crinkle', set=T['crinkle'], lum=0.108, lum_contrast=0.8, tint=0x2a2826, repeat=3.0, metal=0.3,
                      rough_mul=3.0, normal_scale=1.4, grime=0.4, edge=0.5, edge_color=0x6f6a62, edge_metal=1,
                      dust=0.3),
        'brass': rm('brass', set=T['metal'], lum=0.488, lum_contrast=1.2, tint=0xd8ae62, repeat=4.0, metal=1,
                    rough_mul=1.6, normal_scale=0.5, grime=0.5, grime_color=0x3b2a14, edge=0.6, edge_color=0xf2d9a0,
                    edge_rough=0.15),
        'cable': rm('cable', set=T['fabric'], lum=0.105, lum_contrast=1.6, tint=0x241f1a, repeat=14.0,
                    normal_scale=1.2, grime=0.3),
        'dark': rm('dark', flat=0x0a0a0a, rough=0.7),
        'lamp_pilot': rm('lamp_pilot', flat=0x6e3208, rough=0.12, clearcoat=0.8, mask=None,
                         emissive=lambda nb: nb.vscale((1.0, 0.5, 0.11), nb.mul(pw(nb), 6.0))),
    }
    R['glass'] = glass_mat(f'{n}_glass', color=0x15171a, opacity=0.16, rough=0.02, smudge=0.2, imperf=T['smear'])
    vm.made['materials'].append(R['glass'])

    def cloth_emit(nb):
        # grille cloth: woven fabric, lamp light through the gaps (glows with the voice)
        weave = nb.div(nb.lum(nb.tex(T['fabric']['map'], nb.vscale(nb.uv('UVMap'), 22.0)).outputs['Color']), 0.105)
        gap = nb.smoothstep(1.05, 0.6, weave)
        k = nb.mul(nb.mul(pw(nb), nb.madd(lv(nb), 0.9, 0.1)), 2.6)
        return nb.vscale(nb.vscale((1.0, 0.6, 0.28), nb.madd(gap, 0.8, 0.08)), k)
    R['cloth'] = rm('cloth', set=T['fabric'], lum=0.105, lum_contrast=1.8, tint=0x5a4731, repeat=22.0,
                    normal_scale=1.4, emissive=cloth_emit)
    # decals: canvas art on the GLB quads
    imgs = {
        'panel': canvas_image(f'{n}_panel_art', 1024, 358, _draw_panel(L)),
        'strip': canvas_image(f'{n}_keystrip_art', 1024, 32, _draw_strip(L), ss=4, alpha=False),
        'name': canvas_image(f'{n}_name_art', 512, 152, _draw_name),
        'dial': canvas_image(f'{n}_dial_art', 512, 512, _draw_dial, alpha=False),
        'bell': canvas_image(f'{n}_bell_art', 512, 512, _draw_bell),
    }
    vm.made['images'] += list(imgs.values())
    R['decal_bell'] = decal_mat(f'{n}_decal_bell', imgs['bell'], rough=0.35)
    R['decal_panel'] = decal_mat(f'{n}_decal_panel', imgs['panel'], rough=0.3)
    R['decal_keystrip'] = decal_mat(f'{n}_decal_keystrip', imgs['strip'], rough=0.25, alpha=False)
    R['decal_name'] = decal_mat(f'{n}_decal_name', imgs['name'], rough=0.22, metal=0.85)

    def dial_emit(nb, tx):
        k = nb.mul(nb.mul(pw(nb), nb.madd(lv(nb), 0.45, 0.75)), 1.1)
        return nb.vscale(nb.vmul(tx.outputs['Color'], (1.0, 0.8, 0.52)), k)
    R['decal_dial'] = decal_mat(f'{n}_decal_dial', imgs['dial'], rough=0.6, alpha=False, emissive=dial_emit)
    vm.made['materials'] += [R[k] for k in R if k.startswith('decal_')]
    missing = apply_roles(nodes, R, R['dark'], no_shadow=r'decal|glass')
    vm.seated_decals = seat_decals(nodes)              # (the Voder's quads all sit 0.4-0.5 mm off: none moves)
    vm.missing_roles = missing
    if missing:
        common.log('voder', 'no material for roles:', ', '.join(sorted(missing)))
    for o in nodes.values():
        if o.type == 'MESH' and any(not role.startswith('decal') and role != 'glass' for role in roles_of(o)):
            write_curvature(o)

    def node(nm):
        o = nodes.get(nm)
        if o is None:
            raise KeyError(f'[voder] missing node {nm}')
        return o
    keys = []
    for i in range(10):
        k = node(f'voder_key_{i + 1:02d}')
        k['band'] = BANDS[i]
        keys.append(k)
    stop_keys = [node(f'voder_stop_{s}') for s in ('td', 'pb', 'kg')]
    quiet, wrist, pedal = node('voder_quiet'), node('voder_wristbar'), node('voder_pedal')
    needle, jewel = node('voder_needle'), node('voder_pilot')
    movers = keys + stop_keys + [quiet, wrist, pedal, needle]
    for o in movers:
        remember_rest(o)
    vm._movers = movers
    vm.parts = {
        'keys': keys, 'stop_keys': stop_keys, 'quiet_key': quiet, 'wrist_bar': wrist, 'pedal': pedal,
        'dial': {'needle': needle, 'face': nodes.get('voder_dial_face'), 'texture': imgs['dial']},
        # the backlit cloth: voder.js looks up a 'voder_grille_cloth' node, which the pack's GLB does not have (it
        # found null); the cloth is the 'cloth' slot of the speaker tower, so the object that carries it stands in
        'lamp': jewel, 'grille': nodes.get('voder_grille_cloth') or next(
            (o for o in nodes.values() if 'cloth' in roles_of(o)), None), 'console': node('voder_console'),
        'speaker': node('voder_speaker'), 'uniforms': {'power': vm.power, 'level': vm.level},
        'materials': R,
    }
    vm.update(0.0, {'power': power}, key=False)        # the engine's update(0, {}): the rest pose, nothing keyed
    return vm
