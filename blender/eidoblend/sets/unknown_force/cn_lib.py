"""eidoblend.sets.unknown_force.cn_lib: the shared helpers of the UNKNOWN FORCE corridor (verse 2) and news (verse 5)
sets, the Blender 5.2 edition of eidoverse/sets/unknown_force/cn_lib.js.

    from eidoblend.sets.unknown_force import cn_lib
    L = cn_lib.make_lib('corridor')                 # owns what it makes; L.dispose_all() removes it
    S = L.pbr('Marble016', res='2k')                # {'id', 'col', 'nrm', 'rgh'} bpy Images (ao / met / disp on request)
    cv = cn_lib.create_canvas(2048, 544); g = cv.get_context('2d')
    cn_lib.fit_text(g, 'SUPREME', x=1024, y=215, max_w=1380, max_h=175, family=cn_lib.fam['michroma'], track=0.16)
    img = L.canvas_tex(cv)                          # a packed bpy Image, rows as three's DataTexture (v = 0 at the bottom)
    B = L.bucket('corridor_gold').box(0.6, 0.3, 0.6, 0, 10, -23.7)      # three's metres, Y up
    ob = B.mesh(material, parent=root)              # one Blender mesh, converted to Blender's Z up

What the JS file holds, and where it went:
  fonts           FONTS / fam: the kit's bundled faces by key; a canvas font string names one ('bold 90px "UF_Exo2"').
  random          rng(seed) is mulberry32, bit for bit; clamp01, smooth.
  textures        tex(path, srgb), pbr(id, res, ao, met, disp) from the shared library (fetched once), build_mips,
                  data_tex / canvas_tex / dyn_canvas (canvas pixels -> packed bpy Images), height_field, box_blur,
                  normal_tex, pack_tex (relief: grey height -> tangent normal map, masks packed in RGBA).
                  ImageVariants: a canvas whose drawing changes over time (a new post, a recount, a new
                  chyron): every variant packed, a keyed property picks the one shown (the WebGPU redrew its
                  DataTexture).
  canvas          create_canvas: canvas-2D on numpy + FreeType (Pillow), drawn as @napi-rs/canvas (Skia) drew it:
                  shapes by a scanline fill (nonzero / evenodd, 4 x 4 samples at their centres) and outlined strokes
                  (joins, caps, the miter limit); text with Skia's layout (the faces' unhinted hmtx advances, their
                  GPOS pair kerning, fake bold for 'bold' on a face without one, the mask gamma), glyphs drawn 4 x 4
                  and box-filtered; gradients, shadows ((shadow alpha x paint alpha)^2, as napi-rs draws them),
                  destination-out, clips, drawImage. Every texture the sets draw matches the WebGPU canvases to about
                  1/255 (tests/sets_uf_corridor_news/test_parity.py). fit_text(g, text, ...) as the JS export;
                  register_font(path, name) as GlobalFonts.registerFromPath.
  geometry        three r184's Box / Cylinder / Cone / Sphere / Lathe / Torus / Circle / Plane / Tube geometries
                  (positions, normals, uvs, index), prep, box_uv (box-projected metre UVs), bucket (merge, then one
                  mesh), m4 (three's Matrix4.compose), all in three's axes; meshes are converted when they are made.
  environment     env_tex(fn, W, H): the procedural HDR environment as a float equirect bpy Image in Blender's
                  convention (fn is called with three-space directions, as the JS callback); make_world makes it the
                  set's World with three's hemisphere term, and EEVEE lights every material with it.
  TSL helpers     NB, an expression layer that writes shader (and Geometry Nodes) math as nodes, with hash21,
                  lum, hex, the MaterialX noises (Blender's Noise Texture computes them exactly), uniforms (a node
                  group of keyed values every material of a set reads), pixel footprints for fwidth.
  pbr_mat         a Principled BSDF material from a texture set with the JS options (tile, tint, recolor, macro,
                  rough, metal, nrm, post, physical sheen / clearcoat, side, transparent, alphaTest ...).
  dispose_all     removes every datablock the lib made.
  SetBase         what corridor.build / news.build return (read as a dict too, the sets' contract): update,
                  animate (the moving parts keyed on your own clock), camera(name), apply_look (exposure, EEVEE),
                  apply_post (the look's bloom and aeropittura, its focal projected), focal_world, set_u, dispose.

Coordinates: the sets are built in three's metres (Y up, the singer's mark the origin facing +Z) and converted once,
three (x, y, z) -> Blender (x, -z, y), when a mesh or an object is made. Shaders read positions back in three's axes
(NB.three(...)), so the WebGPU materials' math ports line for line.
"""

from __future__ import annotations

import json
import math
import os
import re
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ... import common

# ================================================================================================== fonts ===========

FONT_DIR = os.path.join(common.ASSETS_DIR, 'fonts')
FONTS = {
    'michroma': 'Michroma-Regular', 'blackops': 'BlackOpsOne-Regular', 'rajdhani': 'Rajdhani-Bold', 'exo': 'Exo2',
    'sedgwick': 'SedgwickAveDisplay-Regular', 'kalam': 'Kalam-Bold', 'caveat': 'CaveatBrush-Regular',
    'elite': 'SpecialElite-Regular', 'mono': 'ShareTechMono-Regular', 'audiowide': 'Audiowide-Regular',
}
# the CSS family names the JS registered (GlobalFonts.registerFromPath(file, 'UF_' + name)); a canvas font string
# carries one, and the canvas resolves it back to the file
fam = {k: f'"UF_{v}"' for k, v in FONTS.items()}


_REGISTERED = {}


def register_font(path, name):
    """GlobalFonts.registerFromPath(path, name): another face a canvas font string can name ('40px "name"')."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f'cn_lib: register_font: {path} not found')
    _REGISTERED[name.strip().strip('"').strip("'")] = os.path.abspath(path)
    return f'"{name}"'


def font_file(family: str) -> str:
    """'"UF_Exo2"' / 'UF_Exo2' / 'Exo2' / 'exo' (or a name given to register_font) -> its TTF."""
    f = family.strip().strip('"').strip("'")
    if f in _REGISTERED:
        return _REGISTERED[f]
    if f.startswith('UF_'):
        f = f[3:]
    f = FONTS.get(f, f)
    p = os.path.join(FONT_DIR, f + '.ttf')
    if not os.path.isfile(p):
        raise KeyError(f'cn_lib: font {family!r} is not one of the bundled faces ({", ".join(FONTS.values())}) '
                       f'nor registered ({", ".join(_REGISTERED) or "none"})')
    return p


def lum(c):
    """TSL lum(c) on numbers: Rec. 709 luminance of an (r, g, b) (NB.lum writes the same into a node graph)."""
    if hasattr(c, 'nb'):
        return c.nb.lum(c)
    return 0.2126 * float(c[0]) + 0.7152 * float(c[1]) + 0.0722 * float(c[2])


_FONT_CACHE = {}
_FACE_BOLD = {}
_BIG = {}
BIG_PX = 2048.0          # advances are measured at this size and scaled: FreeType hints them to whole pixels, Skia doesn't
TEXT_SS = 4              # glyphs are drawn at 4 x 4 and box-filtered: near-unhinted shapes, Skia's sub-pixel placement


def _pil_font(path, px, weight=''):
    """The face at px (its default instance: @napi-rs/canvas registers a variable face, Exo 2, as its default
    instance and does not pick its Bold; see fake_bold)."""
    k = (path, round(float(px), 3))
    f = _FONT_CACHE.get(k)
    if f is None:
        f = ImageFont.truetype(path, max(0.5, float(px)))
        if len(_FONT_CACHE) > 512:
            _FONT_CACHE.clear()
        _FONT_CACHE[k] = f
    return f


def _face_bold(path) -> bool:
    b = _FACE_BOLD.get(path)
    if b is None:
        style = ImageFont.truetype(path, 16).getname()[1] or ''
        b = _FACE_BOLD[path] = any(w in style for w in ('Bold', 'Black', 'Heavy'))
    return b


def fake_bold(path, weight) -> bool:
    """Skia emboldens a face that has no bold of its own when bold is asked (the post's 'bold <n>px "UF_Exo2"'): the
    face's own advances, its outline grown (measured on the WebGPU post: 21-22 px stems at 177 px, as here)."""
    return weight == 'bold' and not _face_bold(path)


def fake_bold_outset(px) -> float:
    """Skia's fake bold strokes the outline with width size x lerp(1/24 at 9 px, 1/32 at 36 px) (strokeAndFill):
    each side grows by half of that."""
    t = min(1.0, max(0.0, (float(px) - 9.0) / 27.0))
    return float(px) * ((1.0 / 24.0) + t * (1.0 / 32.0 - 1.0 / 24.0)) / 2.0


class _Kerning:
    """A face's pair kerning as HarfBuzz applies it for Skia: the GPOS 'kern' feature's PairPos lookups (formats 1 and
    2, also inside Extension lookups), else the legacy 'kern' table (format 0); glyph ids through the cmap (formats
    4 and 12). Pillow lays text out without HarfBuzz here, so the sets' lines would run up to 1.6% long without it."""

    def __init__(self, path):
        with open(path, 'rb') as f:
            self.b = b = f.read()
        n = struct.unpack_from('>H', b, 4)[0]
        self.t = {b[12 + 16 * i:16 + 16 * i].decode('latin-1'): struct.unpack_from('>I', b, 20 + 16 * i)[0]
                  for i in range(n)}
        self.upem = struct.unpack_from('>H', b, self.t['head'] + 18)[0] if 'head' in self.t else 1000
        self.cmap = self._cmap()
        # the unhinted advances (hmtx, font units): Skia lays text out with them (FreeType's hinted ones are whole
        # pixels; even measured at 2048 px they drift by a pixel along a 4096 px ticker)
        self.adv = None
        if 'hhea' in self.t and 'hmtx' in self.t:
            nm = struct.unpack_from('>H', b, self.t['hhea'] + 34)[0]
            self.adv = np.frombuffer(b, '>u2', count=2 * nm, offset=self.t['hmtx'])[0::2].astype(np.float64)
        self.subs = self._gpos() if 'GPOS' in self.t else []
        self.legacy = self._kern0() if not self.subs and 'kern' in self.t else {}
        self.cache = {}

    def _u16(self, o):
        return struct.unpack_from('>H', self.b, o)[0]

    def _cmap(self):
        b, base = self.b, self.t.get('cmap')
        if base is None:
            return {}
        best = None
        for i in range(self._u16(base + 2)):
            pid, eid, off = struct.unpack_from('>HHI', b, base + 4 + 8 * i)
            fmt = self._u16(base + off)
            rank = {(3, 10, 12): 0, (0, 4, 12): 1, (3, 1, 4): 2, (0, 3, 4): 3}.get((pid, eid, fmt))
            if rank is not None and (best is None or rank < best[0]):
                best = (rank, base + off, fmt)
        out = {}
        if best is None:
            return out
        _r, o, fmt = best
        if fmt == 4:
            segx2 = self._u16(o + 6)
            ends, starts = o + 14, o + 16 + segx2
            deltas, ranges = starts + segx2, starts + 2 * segx2
            for s in range(segx2 // 2):
                end, start = self._u16(ends + 2 * s), self._u16(starts + 2 * s)
                delta = struct.unpack_from('>h', b, deltas + 2 * s)[0]
                ro = self._u16(ranges + 2 * s)
                for c in range(start, min(end, 0xFFFE) + 1):
                    if ro == 0:
                        g = (c + delta) & 0xFFFF
                    else:
                        g = self._u16(ranges + 2 * s + ro + 2 * (c - start))
                        g = (g + delta) & 0xFFFF if g else 0
                    if g:
                        out[c] = g
        else:
            for k in range(struct.unpack_from('>I', b, o + 12)[0]):
                c0, c1, g0 = struct.unpack_from('>III', b, o + 16 + 12 * k)
                for c in range(c0, c1 + 1):
                    out[c] = g0 + c - c0
        return out

    def _coverage(self, o):
        fmt, n = self._u16(o), self._u16(o + 2)
        if fmt == 1:
            return {self._u16(o + 4 + 2 * i): i for i in range(n)}
        cov = {}
        for i in range(n):
            s, e, si = struct.unpack_from('>HHH', self.b, o + 4 + 6 * i)
            for g in range(s, e + 1):
                cov[g] = si + g - s
        return cov

    def _classdef(self, o):
        fmt = self._u16(o)
        if fmt == 1:
            start, n = self._u16(o + 2), self._u16(o + 4)
            return {start + i: self._u16(o + 6 + 2 * i) for i in range(n)}
        cd = {}
        for i in range(self._u16(o + 2)):
            s, e, c = struct.unpack_from('>HHH', self.b, o + 4 + 6 * i)
            for g in range(s, e + 1):
                cd[g] = c
        return cd

    @staticmethod
    def _vsize(fmt):
        return 2 * bin(fmt & 0xFF).count('1')

    def _xadv(self, o, fmt):
        """XAdvance of a ValueRecord at o (0 when the format has none)."""
        if not fmt & 4:
            return 0
        skip = 2 * bin(fmt & 3).count('1')
        return struct.unpack_from('>h', self.b, o + skip)[0]

    def _gpos(self):
        b, g = self.b, self.t['GPOS']
        sl, fl, ll = self._u16(g + 4), self._u16(g + 6), self._u16(g + 8)
        feats = set()
        for i in range(self._u16(g + sl)):                     # every script's default language system
            so = g + sl + self._u16(g + sl + 2 + 6 * i + 4)
            dl = self._u16(so)
            for lo in ([so + dl] if dl else []):
                feats.update(self._u16(lo + 6 + 2 * k) for k in range(self._u16(lo + 4)))
        lookups = []
        for fi in sorted(feats):
            rec = g + fl + 2 + 6 * fi
            if b[rec:rec + 4] != b'kern':
                continue
            fo = g + fl + self._u16(rec + 4)
            lookups += [self._u16(fo + 4 + 2 * k) for k in range(self._u16(fo + 2))]
        out = []
        for li in sorted(set(lookups)):
            lo = g + ll + self._u16(g + ll + 2 + 2 * li)
            ltype = self._u16(lo)
            subs = []
            out.append(subs)                                    # per lookup: its first matching subtable applies
            for k in range(self._u16(lo + 4)):
                so = lo + self._u16(lo + 6 + 2 * k)
                t_ = ltype
                if t_ == 9:
                    t_ = self._u16(so + 2)
                    so = so + struct.unpack_from('>I', b, so + 4)[0]
                if t_ != 2:
                    continue
                fmt, cov, vf1, vf2 = struct.unpack_from('>HHHH', b, so)
                rec = {'fmt': fmt, 'cov': self._coverage(so + cov), 'vf1': vf1, 'vf2': vf2, 'o': so}
                if fmt == 2:
                    cd1, cd2, n1, n2 = struct.unpack_from('>HHHH', b, so + 8)
                    rec.update(cd1=self._classdef(so + cd1), cd2=self._classdef(so + cd2), n2=n2)
                subs.append(rec)
        return [s for s in out if s]

    def _kern0(self):
        b, k = self.b, self.t['kern']
        out = {}
        if self._u16(k) != 0:
            return out
        o = k + 4
        for _ in range(self._u16(k + 2)):
            ln, cov = self._u16(o + 2), self._u16(o + 4)
            if cov >> 8 == 0 and cov & 1:                     # format 0, horizontal
                for i in range(self._u16(o + 6)):
                    l_, r_, v = struct.unpack_from('>HHh', b, o + 14 + 6 * i)
                    out[(l_, r_)] = v
            o += ln
        return out

    def pair(self, c1, c2):
        """The kerning between two characters, in font units (positive: further apart)."""
        key = (c1, c2)
        v = self.cache.get(key)
        if v is not None:
            return v
        g1, g2 = self.cmap.get(ord(c1)), self.cmap.get(ord(c2))
        v = 0
        if g1 is not None and g2 is not None:
            for lookup in self.subs:                            # every 'kern' lookup adds; in one, the first match
                for s in lookup:
                    ci = s['cov'].get(g1)
                    if ci is None:
                        continue
                    sz1, sz2 = self._vsize(s['vf1']), self._vsize(s['vf2'])
                    if s['fmt'] == 1:
                        ps = s['o'] + self._u16(s['o'] + 10 + 2 * ci)
                        rec = 2 + sz1 + sz2
                        hit = None
                        lo_, hi_ = 0, self._u16(ps) - 1
                        while lo_ <= hi_:                       # PairValueRecords are sorted by the second glyph
                            mid = (lo_ + hi_) // 2
                            gm = self._u16(ps + 2 + rec * mid)
                            if gm == g2:
                                hit = ps + 2 + rec * mid + 2
                                break
                            if gm < g2:
                                lo_ = mid + 1
                            else:
                                hi_ = mid - 1
                        if hit is None:
                            continue
                        v += self._xadv(hit, s['vf1'])
                        break
                    if s['fmt'] == 2:
                        c1i, c2i = s['cd1'].get(g1, 0), s['cd2'].get(g2, 0)
                        v += self._xadv(s['o'] + 16 + (c1i * s['n2'] + c2i) * (sz1 + sz2), s['vf1'])
                        break
            if not self.subs:
                v = self.legacy.get((g1, g2), 0)
        self.cache[key] = v
        return v


_KERN = {}
_ADV = {}


def kerning(path) -> _Kerning:
    k = _KERN.get(path)
    if k is None:
        k = _KERN[path] = _Kerning(path)
    return k


def glyph_pens(path, px, text):
    """Each character's pen x (from the run's start) and the run's advance, unhinted, with the face's pair kerning:
    the layout Skia's measureText / fillText make."""
    f = _BIG.get(path)
    if f is None:
        f = _BIG[path] = ImageFont.truetype(path, BIG_PX)
    k = kerning(path)
    ks = float(px) / k.upem
    pens, x = [], 0.0
    text = str(text)
    for i, ch in enumerate(text):
        pens.append(x)
        a = _ADV.get((path, ch))
        if a is None:
            gid = k.cmap.get(ord(ch))
            if k.adv is not None and gid is not None:
                a = k.adv[min(gid, len(k.adv) - 1)] / k.upem          # font units -> em
            else:
                a = f.getlength(ch) / BIG_PX                           # no hmtx / no glyph: FreeType's, per em
            a = _ADV[(path, ch)] = float(a)
        x += a * float(px)
        if i + 1 < len(text):
            x += k.pair(ch, text[i + 1]) * ks
    return pens, x


def text_advance(path, px, text) -> float:
    """The unhinted, kerned advance of a run (Skia's measureText)."""
    return glyph_pens(path, px, text)[1]


_FONT_RE = re.compile(r'^\s*(?:(bold|normal|\d{3})\s+)?([\d.]+)px\s+(.+?)\s*$')


def parse_font(s: str):
    """A canvas font string -> (file, px, weight)."""
    m = _FONT_RE.match(str(s))
    if not m:
        raise ValueError(f'cn_lib: font string {s!r} is not "[bold] <n>px <family>"')
    w = m.group(1) or ''
    weight = 'bold' if w == 'bold' or (w.isdigit() and int(w) >= 600) else ''
    return font_file(m.group(3)), float(m.group(2)), weight


# ================================================================================================= random ==========

M32 = 0xFFFFFFFF


def rng(seed=1):
    """mulberry32, bit for bit the JS rng(seed): a function returning floats in [0, 1)."""
    st = [int(seed) & M32]

    def r():
        a = (st[0] + 0x6D2B79F5) & M32
        st[0] = a
        t = ((a ^ (a >> 15)) * (1 | a)) & M32
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & M32)) & M32) ^ t
        return ((t ^ (t >> 14)) & M32) / 4294967296.0
    return r


def clamp01(x):
    return min(1.0, max(0.0, x))


def smooth(a, b, x):
    k = clamp01((x - a) / (b - a))
    return k * k * (3 - 2 * k)


def exists(p) -> bool:
    return os.path.exists(str(p))


# ================================================================================================= colour ==========

_NAMED = {'black': '#000000', 'white': '#ffffff', 'red': '#ff0000', 'transparent': 'rgba(0,0,0,0)'}


def parse_color(c):
    """A CSS colour (#rgb, #rrggbb, #rrggbbaa, rgb(), rgba(), a few names) or a tuple -> (r, g, b, a), r g b in 0..1
    (sRGB-encoded, as canvas-2D blends them), a in 0..1."""
    if isinstance(c, (tuple, list)):
        t = [float(v) for v in c]
        if max(t[:3]) > 1.0:
            t[:3] = [v / 255.0 for v in t[:3]]
        return tuple(t[:3]) + ((t[3],) if len(t) > 3 else (1.0,))
    s = str(c).strip().lower()
    s = _NAMED.get(s, s)
    if s.startswith('#'):
        h = s[1:]
        if len(h) in (3, 4):
            h = ''.join(ch * 2 for ch in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) / 255.0 if len(h) == 8 else 1.0
        return (r / 255.0, g / 255.0, b / 255.0, a)
    m = re.match(r'rgba?\(([^)]*)\)', s)
    if m:
        p = [x.strip() for x in m.group(1).split(',')]
        r, g, b = (float(x) / 255.0 for x in p[:3])
        return (r, g, b, float(p[3]) if len(p) > 3 else 1.0)
    raise ValueError(f'cn_lib: colour {c!r}')


def srgb_to_linear(v):
    v = np.asarray(v, dtype=np.float64)
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def hex_linear(h, k=1.0):
    """three's new Color(0xRRGGBB): an sRGB hex as linear RGB (ColorManagement on), times k."""
    if isinstance(h, str):
        h = int(h.lstrip('#'), 16)
    c = [((h >> 16) & 255) / 255.0, ((h >> 8) & 255) / 255.0, (h & 255) / 255.0]
    return tuple(float(x) * k for x in srgb_to_linear(c))


# ================================================================================================= canvas ==========

class Gradient:
    """createLinearGradient / createRadialGradient: stops interpolated unpremultiplied (Skia's default), padded."""

    def __init__(self, kind, args):
        self.kind, self.args, self.stops = kind, [float(a) for a in args], []

    def add_color_stop(self, off, color):
        self.stops.append((float(off), parse_color(color)))
        self.stops.sort(key=lambda s: s[0])

    def _colors(self, t):
        offs = np.array([s[0] for s in self.stops])
        cols = np.array([s[1] for s in self.stops])
        t = np.clip(t, 0.0, 1.0)
        out = np.empty(t.shape + (4,), np.float32)
        for c in range(4):
            out[..., c] = np.interp(t, offs, cols[:, c])
        return out

    def eval(self, ctx, x0, y0, w, h):
        """(h, w, 4) straight RGBA for device pixels [x0, x0 + w) x [y0, y0 + h): user space through the CTM."""
        a, b, c, d, e, f = ctx.m
        det = a * d - b * c
        ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
        X, Y = np.meshgrid(np.arange(x0, x0 + w) + 0.5, np.arange(y0, y0 + h) + 0.5)
        X, Y = X - e, Y - f
        ux, uy = ia * X + ic * Y, ib * X + id_ * Y
        if self.kind == 'linear':
            x0g, y0g, x1g, y1g = self.args
            dx, dy = x1g - x0g, y1g - y0g
            L2 = dx * dx + dy * dy or 1e-12
            t = ((ux - x0g) * dx + (uy - y0g) * dy) / L2
        else:
            cx0, cy0, r0, cx1, cy1, r1 = self.args
            dcx, dcy, dr = cx1 - cx0, cy1 - cy0, r1 - r0
            px, py = ux - cx0, uy - cy0
            A = dcx * dcx + dcy * dcy - dr * dr
            B = px * dcx + py * dcy + r0 * dr
            C = px * px + py * py - r0 * r0
            if abs(A) < 1e-9:
                t = C / (2 * B + 1e-12)
            else:
                disc = np.maximum(B * B - A * C, 0.0)
                sq = np.sqrt(disc)
                t1, t2 = (B + sq) / A, (B - sq) / A
                t = np.where(r0 + np.maximum(t1, t2) * dr >= 0, np.maximum(t1, t2), np.minimum(t1, t2))
        return self._colors(t)


def _adjust_end_angle(a0, a1, ccw):
    """Chrome's canvas arc rule (adjustEndAngle): what Skia-backed canvases sweep for arc(..., a0, a1, ccw)."""
    tp = 2 * math.pi
    if not ccw and a1 - a0 >= tp:
        return a0 + tp
    if ccw and a0 - a1 >= tp:
        return a0 - tp
    if not ccw and a0 > a1:
        return a0 + (tp - math.fmod(a0 - a1, tp))
    if ccw and a0 < a1:
        return a0 - (tp - math.fmod(a1 - a0, tp))
    return a1


SHADOW_SIGMA = [0.5, 0.0]          # sigma = a x shadowBlur + b (the canvas spec's sigma = blur / 2)


def shadow_sigma(blur):
    return SHADOW_SIGMA[0] * float(blur) + SHADOW_SIGMA[1]


_GAMMA_LUTS = {}


def _s2l(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _l2s(v):
    return v * 12.92 if v <= 0.0031308 else 1.055 * max(v, 0.0) ** (1 / 2.4) - 0.055


def skia_text_gamma(cov, style, contrast=0.0):
    """Skia's glyph-mask preblend (SkMaskGamma's correcting table, sRGB luminance, the paint's luminance in 3 bits):
    a glyph's coverage is bent so that a naive blend over the opposite luminance looks like a linear-light one, so
    light text on the canvas comes out a little heavier and dark text a little lighter, as the WebGPU canvases drew
    it (measured on the chyron ticker: Skia's light 40 px text carries 7% more ink than linear coverage)."""
    if isinstance(style, Gradient) or not style:
        return cov
    r, g, b, _a = parse_color(style)
    lum = (int(round(r * 255)) * 54 + int(round(g * 255)) * 183 + int(round(b * 255)) * 19) >> 8
    q = lum >> 5
    src_i = (q << 5) | (q << 2) | (q >> 1)
    T = _GAMMA_LUTS.get((src_i, contrast))
    if T is None:
        src = src_i / 255.0
        dst = 1.0 - src
        lin_src, lin_dst = _s2l(src), _s2l(dst)
        adj = contrast * lin_dst
        a = np.arange(256) / 255.0
        sa = a + (1.0 - a) * adj * a
        if abs(src - dst) < 1.0 / 256.0:
            T = sa
        else:
            out = np.array([_l2s(v) for v in lin_src * sa + (1.0 - sa) * lin_dst])
            T = (out - dst) / (src - dst)
        T = _GAMMA_LUTS[(src_i, contrast)] = np.clip(np.round(T * 255.0) / 255.0, 0.0, 1.0).astype(np.float32)
    # the table is indexed by 8-bit coverage; interpolate between entries so the 4 x 4 box filter's levels keep
    i = np.clip(cov, 0.0, 1.0) * 255.0
    i0 = np.floor(i).astype(np.int64)
    i1 = np.minimum(i0 + 1, 255)
    f = (i - i0).astype(np.float32)
    return T[i0] * (1.0 - f) + T[i1] * f


def scan_coverage(polys, x0, y0, w, h, S=4, rule='nonzero', rows_per_chunk=192):
    """The coverage of closed polygons (lists of device (x, y), y down) over the device box [x0, x0 + w) x
    [y0, y0 + h): S x S point samples per pixel at the sample centres, canvas-2D's fill rule ('nonzero' or 'evenodd').
    A scanline fill written out (each sample row crosses the edges it spans, half-open, sorted; the winding decides
    the spans), so a 14 px rect covers exactly 14 pixels and a ring cut by an opposite winding is a ring."""
    ax, ay, bx, by = [], [], [], []
    for p in polys:
        P = np.asarray(p, np.float64).reshape(-1, 2)
        if len(P) < 3:
            continue
        Q = np.roll(P, -1, axis=0)
        ax.append(P[:, 0]); ay.append(P[:, 1]); bx.append(Q[:, 0]); by.append(Q[:, 1])
    out = np.zeros((h * S, w), np.int32)                 # covered samples per (sample row, pixel)
    if not ax:
        return np.zeros((h, w), np.float32)
    ax, ay, bx, by = (np.concatenate(v) for v in (ax, ay, bx, by))
    keep = ay != by
    ax, ay, bx, by = ax[keep], ay[keep], bx[keep], by[keep]
    d = np.where(by > ay, 1, -1).astype(np.int32)
    ylo, yhi = np.minimum(ay, by), np.maximum(ay, by)
    slope = (bx - ax) / (by - ay)
    for r0 in range(0, h * S, rows_per_chunk):
        r1 = min(h * S, r0 + rows_per_chunk)
        ys = y0 + (np.arange(r0, r1) + 0.5) / S
        sel = (yhi > ys[0]) & (ylo <= ys[-1])
        if not sel.any():
            continue
        Y = ys[:, None]
        span = (Y >= ylo[sel][None, :]) & (Y < yhi[sel][None, :])
        X = np.where(span, ax[sel][None, :] + (Y - ay[sel][None, :]) * slope[sel][None, :], np.inf)
        D = np.where(span, d[sel][None, :], 0)
        o = np.argsort(X, axis=1, kind='stable')
        Xs = np.take_along_axis(X, o, 1)
        wind = np.cumsum(np.take_along_axis(D, o, 1), axis=1)
        ins = (wind != 0) if rule == 'nonzero' else (wind % 2 != 0)
        m = ins[:, :-1] & np.isfinite(Xs[:, 1:])
        if not m.any():
            continue
        rr, cc = np.nonzero(m)
        ka = np.clip(np.ceil((Xs[rr, cc] - x0) * S - 0.5), 0, w * S).astype(np.int64)        # first sample centre >= xa
        kb = np.clip(np.ceil((Xs[rr, cc + 1] - x0) * S - 0.5), 0, w * S).astype(np.int64)    # first one >= xb: excluded
        nz = kb > ka
        rr, ka, kb = rr[nz], ka[nz], kb[nz]
        # the samples [ka, kb) per pixel: whole pixels through a difference row, the two partial ends added
        pa, pb = ka // S, kb // S
        acc = np.zeros((r1 - r0, w + 2), np.int32)
        one = pa == pb
        np.add.at(acc, (rr[one], pa[one]), (kb - ka)[one])
        two = ~one
        r2, pa2, pb2, ka2, kb2 = rr[two], pa[two], pb[two], ka[two], kb[two]
        np.add.at(acc, (r2, pa2), (pa2 + 1) * S - ka2)
        np.add.at(acc, (r2, pb2), kb2 - pb2 * S)
        full = np.zeros((r1 - r0, w + 2), np.int32)
        np.add.at(full, (r2, pa2 + 1), S)
        np.add.at(full, (r2, pb2), -S)
        out[r0:r1] = (acc + np.cumsum(full, axis=1))[:, :w]
    return (out.reshape(h, S, w).sum(axis=1) / float(S * S)).astype(np.float32)


def _ccw(poly):
    """The polygon wound one way (positive area in y-down device space), so the pieces of a stroke union under the
    nonzero rule."""
    P = np.asarray(poly, np.float64)
    a = np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    return P if a >= 0 else P[::-1]


def _disc(c, r, tol=0.03):
    n = max(12, int(math.ceil(2 * math.pi / (2 * math.acos(max(-1.0, 1 - tol / max(r, 1e-6)))))))
    return [(c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def stroke_polygons(pts, closed, hw, join='miter', cap='butt', miter_limit=10.0):
    """canvas-2D's stroke of a flattened subpath as polygons whose union (nonzero) is the stroke: a quad per segment,
    the joins (miter with the canvas limit 10, else bevel; round; bevel) and the caps (butt, square, round)."""
    P = [tuple(p) for p in pts]
    clean = [P[0]]
    for p in P[1:]:
        if math.dist(p, clean[-1]) > 1e-9:
            clean.append(p)
    if closed and len(clean) > 2 and math.dist(clean[0], clean[-1]) <= 1e-9:
        clean.pop()
    P = clean
    out = []
    if len(P) < 2:
        if cap == 'round' and P:
            out.append(_disc(P[0], hw))
        return out
    segs = list(zip(P, P[1:])) + ([(P[-1], P[0])] if closed and len(P) > 2 else [])

    def nrm(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        return (dx / ln, dy / ln), (-dy / ln, dx / ln)
    dirs = [nrm(a, b) for a, b in segs]
    for k, (a, b) in enumerate(segs):
        (ux, uy), (nx, ny) = dirs[k]
        a2, b2 = a, b
        if not closed and cap == 'square':
            if k == 0:
                a2 = (a[0] - ux * hw, a[1] - uy * hw)
            if k == len(segs) - 1:
                b2 = (b[0] + ux * hw, b[1] + uy * hw)
        out.append(_ccw([(a2[0] + nx * hw, a2[1] + ny * hw), (b2[0] + nx * hw, b2[1] + ny * hw),
                         (b2[0] - nx * hw, b2[1] - ny * hw), (a2[0] - nx * hw, a2[1] - ny * hw)]))
    joins = range(len(segs)) if closed and len(P) > 2 else range(1, len(segs))
    for k in joins:
        p = segs[k][0]
        (u1x, u1y), (n1x, n1y) = dirs[k - 1]
        (u2x, u2y), (n2x, n2y) = dirs[k]
        if join == 'round':
            out.append(_ccw(_disc(p, hw)))
            continue
        turn = n1x * u2x + n1y * u2y                   # > 0: the path turns toward n1, so the outer corner is on -n1
        if abs(turn) < 1e-9:
            continue                                   # straight on: the two quads meet edge to edge
        s = -1.0 if turn > 0 else 1.0
        e1 = (p[0] + s * n1x * hw, p[1] + s * n1y * hw)
        e2 = (p[0] + s * n2x * hw, p[1] + s * n2y * hw)
        mx_, my_ = n1x + n2x, n1y + n2y
        ml = math.hypot(mx_, my_)
        cos_half = ml / 2.0
        if join == 'miter' and cos_half > 1e-6 and 1.0 / cos_half <= miter_limit:
            L = hw / cos_half
            out.append(_ccw([p, e1, (p[0] + s * mx_ / ml * L, p[1] + s * my_ / ml * L), e2]))
        else:
            out.append(_ccw([p, e1, e2]))
    if not closed and cap == 'round':
        out.append(_ccw(_disc(P[0], hw)))
        out.append(_ccw(_disc(P[-1], hw)))
    return out


class _TextMetrics:
    __slots__ = ('width',)

    def __init__(self, w):
        self.width = w


_H_ANCHOR = {'left': 'l', 'start': 'l', 'center': 'm', 'right': 'r', 'end': 'r'}
_V_ANCHOR = {'alphabetic': 's', 'middle': 'm', 'top': 'a', 'hanging': 'a', 'bottom': 'd', 'ideographic': 'd'}
_STATE = ('m', 'fill_style', 'stroke_style', 'line_width', 'line_cap', 'line_join', 'font', 'text_align',
          'text_baseline', 'global_composite_operation', 'global_alpha', 'shadow_color', 'shadow_blur', '_clip')


class Context2D:
    """The canvas-2D calls the sets use, in snake_case (fillRect -> fill_rect, globalCompositeOperation ->
    global_composite_operation ...). Shapes are rasterised at 4 x 4 samples per pixel and composited premultiplied
    on sRGB-encoded values, as Skia does; text is FreeType's anti-aliased glyphs (Pillow), placed through the
    current transform."""

    SS = 4

    def __init__(self, canvas):
        self.canvas = canvas
        self.m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        self.fill_style = '#000'
        self.stroke_style = '#000'
        self.line_width = 1.0
        self.line_cap = 'butt'
        self.line_join = 'miter'
        self.font = '10px "UF_Rajdhani-Bold"'
        self.text_align = 'start'
        self.text_baseline = 'alphabetic'
        self.global_composite_operation = 'source-over'
        self.global_alpha = 1.0
        self.shadow_color = 'rgba(0,0,0,0)'
        self.shadow_blur = 0.0
        self._clip = None
        self._stack = []
        self._path = []

    # ---------------------------------------------------------------------------------------------- state
    def save(self):
        self._stack.append({k: getattr(self, k) for k in _STATE})

    def restore(self):
        if self._stack:
            for k, v in self._stack.pop().items():
                setattr(self, k, v)

    def translate(self, tx, ty):
        a, b, c, d, e, f = self.m
        self.m = (a, b, c, d, a * tx + c * ty + e, b * tx + d * ty + f)

    def rotate(self, ang):
        cs, sn = math.cos(ang), math.sin(ang)
        a, b, c, d, e, f = self.m
        self.m = (a * cs + c * sn, b * cs + d * sn, -a * sn + c * cs, -b * sn + d * cs, e, f)

    def scale(self, sx, sy):
        a, b, c, d, e, f = self.m
        self.m = (a * sx, b * sx, c * sy, d * sy, e, f)

    def set_transform(self, a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0):
        self.m = (float(a), float(b), float(c), float(d), float(e), float(f))

    def reset_transform(self):
        self.m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    def _xf(self, x, y):
        a, b, c, d, e, f = self.m
        return (a * x + c * y + e, b * x + d * y + f)

    def _scale(self):
        a, b, c, d, _, _ = self.m
        return math.sqrt(abs(a * d - b * c)) or 1e-9

    # ----------------------------------------------------------------------------------------------- paths
    def begin_path(self):
        self._path = []

    def _cur(self):
        if not self._path or self._path[-1][1]:
            return None
        return self._path[-1][0]

    def move_to(self, x, y):
        self._path.append([[self._xf(x, y)], False])

    def line_to(self, x, y):
        cur = self._cur()
        if cur is None:
            self.move_to(x, y)
        else:
            cur.append(self._xf(x, y))

    def close_path(self):
        if self._path and not self._path[-1][1]:
            pts = self._path[-1][0]
            self._path[-1][1] = True
            self._path.append([[pts[0]], False])            # a new subpath at the closed one's start

    def _flatten(self, ctrl, n_hint):
        cur = self._cur()
        if cur is None:
            self._path.append([[ctrl[0]], False])
            cur = self._path[-1][0]
        p0 = cur[-1]
        pts = [p0] + list(ctrl)
        L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        n = max(8, int(math.ceil(L / 1.5)))                 # 1.5 px chords: smooth at the anti-aliased edge
        for i in range(1, n + 1):
            t = i / n
            if len(pts) == 3:
                u = 1 - t
                x = u * u * pts[0][0] + 2 * u * t * pts[1][0] + t * t * pts[2][0]
                y = u * u * pts[0][1] + 2 * u * t * pts[1][1] + t * t * pts[2][1]
            else:
                u = 1 - t
                x = (u ** 3 * pts[0][0] + 3 * u * u * t * pts[1][0] + 3 * u * t * t * pts[2][0] + t ** 3 * pts[3][0])
                y = (u ** 3 * pts[0][1] + 3 * u * u * t * pts[1][1] + 3 * u * t * t * pts[2][1] + t ** 3 * pts[3][1])
            cur.append((x, y))

    def quadratic_curve_to(self, cx, cy, x, y):
        self._flatten([self._xf(cx, cy), self._xf(x, y)], None)

    def bezier_curve_to(self, c1x, c1y, c2x, c2y, x, y):
        self._flatten([self._xf(c1x, c1y), self._xf(c2x, c2y), self._xf(x, y)], None)

    def arc(self, x, y, r, a0, a1, ccw=False):
        self.ellipse(x, y, r, r, 0.0, a0, a1, ccw)

    def ellipse(self, x, y, rx, ry, rot, a0, a1, ccw=False):
        a1 = _adjust_end_angle(a0, a1, ccw)
        sweep = a1 - a0
        rdev = max(rx, ry) * self._scale()
        step = 2 * math.acos(max(-1.0, 1.0 - 0.03 / max(rdev, 1e-6)))     # chords within 0.03 px of the true arc
        n = max(8, int(math.ceil(abs(sweep) / max(step, 1e-3))))
        cr, sr = math.cos(rot), math.sin(rot)
        pts = []
        for i in range(n + 1):
            th = a0 + sweep * i / n
            ex, ey = rx * math.cos(th), ry * math.sin(th)
            pts.append(self._xf(x + ex * cr - ey * sr, y + ex * sr + ey * cr))
        cur = self._cur()
        if cur is None:
            self._path.append([pts, False])
        else:
            cur.extend(pts)

    def rect(self, x, y, w, h):
        pts = [self._xf(x, y), self._xf(x + w, y), self._xf(x + w, y + h), self._xf(x, y + h)]
        self._path.append([pts, True])
        self._path.append([[self._xf(x, y)], False])

    # ------------------------------------------------------------------------------------------- raster
    def _bbox(self, polys, pad):
        xs = np.concatenate([np.asarray(p, np.float64)[:, 0] for p in polys])
        ys = np.concatenate([np.asarray(p, np.float64)[:, 1] for p in polys])
        W, H = self.canvas.width, self.canvas.height
        x0 = max(0, int(math.floor(xs.min() - pad)) - 1)
        y0 = max(0, int(math.floor(ys.min() - pad)) - 1)
        x1 = min(W, int(math.ceil(xs.max() + pad)) + 2)
        y1 = min(H, int(math.ceil(ys.max() + pad)) + 2)
        return x0, y0, x1, y1

    def _fill_cov(self, subpaths, rule='nonzero'):
        polys = [p for p, _c in subpaths if len(p) >= 3]
        if not polys:
            return None
        x0, y0, x1, y1 = self._bbox(polys, 0)
        if x1 <= x0 or y1 <= y0:
            return None
        return scan_coverage(polys, x0, y0, x1 - x0, y1 - y0, self.SS, rule), x0, y0

    def _stroke_cov(self, subpaths):
        lw = self.line_width * self._scale()
        polys = [(p, c) for p, c in subpaths if len(p) >= 2]
        if not polys or lw <= 0:
            return None
        x0, y0, x1, y1 = self._bbox([p for p, _ in polys], lw * 5.0)
        if x1 <= x0 or y1 <= y0:
            return None
        pieces = []
        for p, closed in polys:
            pieces += stroke_polygons(p, closed, lw / 2.0, self.line_join, self.line_cap)
        if not pieces:
            return None
        cov = scan_coverage(pieces, x0, y0, x1 - x0, y1 - y0, self.SS, 'nonzero')
        return cov, x0, y0

    def _paint(self, cov, x0, y0, style):
        """Composite a coverage mask at device (x0, y0) with a style, through the clip, shadow first."""
        H, W = self.canvas.height, self.canvas.width
        h, w = cov.shape
        if x0 >= W or y0 >= H or x0 + w <= 0 or y0 + h <= 0:
            return
        if self.shadow_blur > 0:
            sc = parse_color(self.shadow_color)
            if sc[3] > 0:
                sig = shadow_sigma(self.shadow_blur)
                pad = int(math.ceil(3 * sig)) + 1
                big = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
                big[pad:pad + h, pad:pad + w] = cov
                im = Image.fromarray(np.clip(big * 255.0 + 0.5, 0, 255).astype(np.uint8), 'L')
                sh = np.asarray(im.filter(ImageFilter.GaussianBlur(sig)), np.float32) / 255.0
                # the shadow's strength as @napi-rs/canvas draws it: (shadow alpha x paint alpha) squared (measured on
                # the graffiti's overspray, rgba(...,0.55) under 0.4 text: the spec's 0.22 would be 4.6 x too strong)
                pa = 1.0 if isinstance(style, Gradient) else parse_color(style)[3]
                self._composite(sh, x0 - pad, y0 - pad, tuple(sc[:3]) + ((sc[3] * pa) ** 2,), shadow=True)
        self._composite(cov, x0, y0, style)

    def _erase_bounds(self, cx0, cy0, cx1, cy1):
        """1 where a destination-out may erase in the device box [cx0, cx1) x [cy0, cy1): inside the bounding box of the
        canvas rect (0, 0, W, H) through the current transform, else 0."""
        Wc, Hc = self.canvas.width, self.canvas.height
        cs = np.array([self._xf(x, y) for x, y in ((0, 0), (Wc, 0), (Wc, Hc), (0, Hc))])
        bx0, by0 = int(math.floor(cs[:, 0].min() + 1e-6)), int(math.floor(cs[:, 1].min() + 1e-6))
        bx1, by1 = int(math.ceil(cs[:, 0].max() - 1e-6)), int(math.ceil(cs[:, 1].max() - 1e-6))
        xs = np.arange(cx0, cx1)
        ys = np.arange(cy0, cy1)
        return (((ys >= by0) & (ys < by1))[:, None] & ((xs >= bx0) & (xs < bx1))[None, :]).astype(np.float32)

    def _composite(self, cov, x0, y0, style, shadow=False):
        H, W = self.canvas.height, self.canvas.width
        h, w = cov.shape
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(W, x0 + w), min(H, y0 + h)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        cov = cov[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
        if self._clip is not None:
            cov = cov * self._clip[cy0:cy1, cx0:cx1]
        if isinstance(style, Gradient):
            col = style.eval(self, cx0, cy0, cx1 - cx0, cy1 - cy0)
            rgb, al = col[..., :3], col[..., 3]
        else:
            c = style if (shadow and isinstance(style, tuple)) else parse_color(style)
            rgb, al = np.array(c[:3], np.float32), c[3]
        a = (al * self.global_alpha) * cov
        dst = self.canvas.data[cy0:cy1, cx0:cx1]
        if self.global_composite_operation == 'destination-out':
            # as @napi-rs/canvas 0.1.69 erases: only inside the canvas rect carried through the current transform
            # (its layer's bounds; measured: under translate(100, 50) a hole at (0, 0) keeps only its quarter at
            # x >= 100, y >= 50), so the poll's LOSING BADLY stamp is distressed on its lower right only, as the WebGPU's
            a = a * self._erase_bounds(cx0, cy0, cx1, cy1)
            dst *= (1.0 - a)[..., None]
        else:
            dst[..., :3] = rgb * a[..., None] + dst[..., :3] * (1.0 - a)[..., None]
            dst[..., 3] = a + dst[..., 3] * (1.0 - a)

    def fill(self):
        r = self._fill_cov(self._path)
        if r:
            self._paint(r[0], r[1], r[2], self.fill_style)

    def stroke(self):
        r = self._stroke_cov(self._path)
        if r:
            self._paint(r[0], r[1], r[2], self.stroke_style)

    def clip(self):
        r = self._fill_cov(self._path)
        m = np.zeros((self.canvas.height, self.canvas.width), np.float32)
        if r:
            cov, x0, y0 = r
            h, w = cov.shape
            m[y0:y0 + h, x0:x0 + w] = cov
        self._clip = m if self._clip is None else self._clip * m

    def fill_rect(self, x, y, w, h):
        pts = [self._xf(x, y), self._xf(x + w, y), self._xf(x + w, y + h), self._xf(x, y + h)]
        r = self._fill_cov([[pts, True]])
        if r:
            self._paint(r[0], r[1], r[2], self.fill_style)

    def stroke_rect(self, x, y, w, h):
        """A miter-joined rectangle outline: the ring between the rect grown and shrunk by half the line width."""
        hw = self.line_width / 2.0
        outer = [self._xf(x - hw, y - hw), self._xf(x + w + hw, y - hw), self._xf(x + w + hw, y + h + hw),
                 self._xf(x - hw, y + h + hw)]
        sub = [[outer, True]]
        if w > 2 * hw and h > 2 * hw:
            sub.append([[self._xf(x + hw, y + hw), self._xf(x + w - hw, y + hw), self._xf(x + w - hw, y + h - hw),
                         self._xf(x + hw, y + h - hw)], True])
        r = self._fill_cov(sub, rule='evenodd')                  # the inner rect cuts the hole
        if r:
            self._paint(r[0], r[1], r[2], self.stroke_style)

    def clear_rect(self, x, y, w, h):
        (X0, Y0), (X1, Y1) = self._xf(x, y), self._xf(x + w, y + h)
        X0, X1 = sorted((X0, X1))
        Y0, Y1 = sorted((Y0, Y1))
        H, W = self.canvas.height, self.canvas.width
        self.canvas.data[max(0, int(round(Y0))):min(H, int(round(Y1))), max(0, int(round(X0))):min(W, int(round(X1)))] = 0

    # -------------------------------------------------------------------------------------------- text
    def measure_text(self, text):
        path, px, _weight = parse_font(self.font)
        return _TextMetrics(text_advance(path, px, text))

    def _text_cov(self, text, x, y, stroke):
        """A run's coverage in device pixels: the glyphs drawn TEXT_SS x larger (FreeType's hinting then moves
        nothing by more than a sub-pixel, as Skia leaves glyphs unhinted) and box-filtered down. stroke: the glyphs
        grown by half the line width; a face with no bold of its own grows by Skia's fake bold too."""
        text = str(text)
        if not text:
            return None
        path, px, weight = parse_font(self.font)
        s = self._scale()
        SS = TEXT_SS
        font = _pil_font(path, px * s * SS)
        vanchor = 'l' + _V_ANCHOR.get(self.text_baseline, 's')
        grow = (self.line_width * s / 2.0 if stroke else 0.0) + (fake_bold_outset(px) * s if fake_bold(path, weight) else 0.0)
        sw = grow * SS
        # the run laid out as Skia lays it: unhinted, kerned pens (device px at the device size), aligned by its advance
        pens, total = glyph_pens(path, px * s, text)
        h_ = _H_ANCHOR.get(self.text_align, 'l')
        off = 0.0 if h_ == 'l' else (-total / 2.0 if h_ == 'm' else -total)
        glyphs = [(ch, (off + p) * SS, font.getbbox(ch, anchor=vanchor, stroke_width=sw)) for ch, p in zip(text, pens)
                  if not ch.isspace()]
        if not glyphs:
            return None
        l = min(gx + bb[0] for _c, gx, bb in glyphs)               # the run's ink box, upright, TEXT_SS px from the anchor
        r = max(gx + bb[2] for _c, gx, bb in glyphs)
        t = min(bb[1] for _c, _g, bb in glyphs)
        b = max(bb[3] for _c, _g, bb in glyphs)
        pad = 2
        X, Y = self._xf(x, y)
        a_, b_, c_, d_, _, _ = self.m

        def down(im, w, h):
            a = np.asarray(im, np.float32).reshape(h, SS, w, SS).mean(axis=(1, 3))
            return a / 255.0

        def draw_run(im, ox, oy):
            dr = ImageDraw.Draw(im)
            for ch, gx, _bb in glyphs:
                dr.text((ox + gx, oy), ch, font=font, fill=255, anchor=vanchor, stroke_width=sw, stroke_fill=255)
        if abs(b_) < 1e-9 and abs(c_) < 1e-9 and a_ > 0 and abs(a_ - d_) < 1e-9:
            ix = int(math.floor((X * SS + l) / SS)) - pad
            iy = int(math.floor((Y * SS + t) / SS)) - pad
            w = int(math.ceil((X * SS + r) / SS)) + pad - ix
            h = int(math.ceil((Y * SS + b) / SS)) + pad - iy
            im = Image.new('L', (w * SS, h * SS), 0)
            draw_run(im, (X - ix) * SS, (Y - iy) * SS)
            return down(im, w, h), ix, iy
        # rotated or skewed: draw upright at TEXT_SS x the device scale, warp through the transform onto a TEXT_SS x
        # device grid, box-filter down. The upright image holds glyph offset (gx, gy) (user units from the anchor) at
        # (u0, v0) + s TEXT_SS (gx, gy); device offset D - (X, Y) = A (gx, gy).
        W, H = int(math.ceil(r - l)) + 2 * pad * SS, int(math.ceil(b - t)) + 2 * pad * SS
        u0, v0 = pad * SS - l, pad * SS - t
        im = Image.new('L', (W, H), 0)
        draw_run(im, u0, v0)
        det = a_ * d_ - b_ * c_
        i00, i01, i10, i11 = d_ / det, -c_ / det, -b_ / det, a_ / det
        corners = []
        for u, v in ((0, 0), (W, 0), (W, H), (0, H)):
            lx, ly = (u - u0) / (s * SS), (v - v0) / (s * SS)
            corners.append((X + a_ * lx + c_ * ly, Y + b_ * lx + d_ * ly))
        cs = np.array(corners)
        bx0, by0 = int(math.floor(cs[:, 0].min())) - 1, int(math.floor(cs[:, 1].min())) - 1
        bx1, by1 = int(math.ceil(cs[:, 0].max())) + 1, int(math.ceil(cs[:, 1].max())) + 1
        # output sub-pixel centre o -> device (bx0, by0) + o / SS -> upright (u0, v0) + s SS A^-1 (D - (X, Y))
        A, B = s * i00, s * i01
        C = s * SS * (i00 * (bx0 - X) + i01 * (by0 - Y)) + u0
        D, E = s * i10, s * i11
        F = s * SS * (i10 * (bx0 - X) + i11 * (by0 - Y)) + v0
        out = im.transform(((bx1 - bx0) * SS, (by1 - by0) * SS), Image.Transform.AFFINE, (A, B, C, D, E, F),
                           resample=Image.Resampling.BILINEAR)
        return down(out, bx1 - bx0, by1 - by0), bx0, by0

    def fill_text(self, text, x, y):
        r = self._text_cov(text, x, y, False)
        if r:
            self._paint(skia_text_gamma(r[0], self.fill_style), r[1], r[2], self.fill_style)

    def stroke_text(self, text, x, y):
        """The glyphs grown by half the line width (FreeType's round stroker): the outside half of canvas-2D's
        centred stroke plus the glyph (the inner half is covered by the fill wherever the sets stroke text)."""
        r = self._text_cov(text, x, y, True)
        if r:
            self._paint(skia_text_gamma(r[0], self.stroke_style), r[1], r[2], self.stroke_style)

    # ------------------------------------------------------------------------------------------ gradients
    def create_linear_gradient(self, x0, y0, x1, y1):
        return Gradient('linear', (x0, y0, x1, y1))

    def create_radial_gradient(self, x0, y0, r0, x1, y1, r1):
        return Gradient('radial', (x0, y0, r0, x1, y1, r1))

    # ---------------------------------------------------------------------------------------- draw image
    def draw_image(self, src, dx, dy):
        """Another canvas, at (dx, dy) through the current transform (premultiplied source-over or
        destination-out)."""
        sd = src.data if isinstance(src, Canvas) else src
        sh, sw = sd.shape[:2]
        a_, b_, c_, d_, e_, f_ = self.m
        H, W = self.canvas.height, self.canvas.width
        corners = [self._xf(dx + u, dy + v) for u, v in ((0, 0), (sw, 0), (sw, sh), (0, sh))]
        cs = np.array(corners)
        bx0, by0 = max(0, int(math.floor(cs[:, 0].min()))), max(0, int(math.floor(cs[:, 1].min())))
        bx1, by1 = min(W, int(math.ceil(cs[:, 0].max()))), min(H, int(math.ceil(cs[:, 1].max())))
        if bx1 <= bx0 or by1 <= by0:
            return
        det = a_ * d_ - b_ * c_
        i00, i01, i10, i11 = d_ / det, -c_ / det, -b_ / det, a_ / det
        X0, Y0 = bx0 - e_, by0 - f_
        A, B, C = i00, i01, i00 * X0 + i01 * Y0 - dx
        D, E, F = i10, i11, i10 * X0 + i11 * Y0 - dy
        chans = []
        for k in range(4):
            im = Image.fromarray(np.ascontiguousarray(sd[..., k]).astype(np.float32), 'F')
            o = im.transform((bx1 - bx0, by1 - by0), Image.Transform.AFFINE, (A, B, C, D, E, F),
                             resample=Image.Resampling.BILINEAR)
            chans.append(np.asarray(o, np.float32))
        s = np.stack(chans, -1)
        if self._clip is not None:
            s = s * self._clip[by0:by1, bx0:bx1, None]
        dst = self.canvas.data[by0:by1, bx0:bx1]
        if self.global_composite_operation == 'destination-out':
            dst *= (1.0 - s[..., 3:4] * self._erase_bounds(bx0, by0, bx1, by1)[..., None])
        else:
            dst[...] = s + dst * (1.0 - s[..., 3:4])

    def get_image_data(self, x=0, y=0, w=None, h=None):
        return self.canvas.pixels()


class Canvas:
    """createCanvas(W, H): float premultiplied RGBA (sRGB-encoded values), read back as RGBA8 like getImageData."""

    def __init__(self, width, height):
        self.width, self.height = int(width), int(height)
        self.data = np.zeros((self.height, self.width, 4), np.float32)
        self._ctx = None

    def get_context(self, kind='2d'):
        if self._ctx is None:
            self._ctx = Context2D(self)
        return self._ctx

    def pixels(self) -> np.ndarray:
        """(H, W, 4) uint8, straight alpha, rows top-down (canvas getImageData)."""
        d = self.data
        a = d[..., 3:4]
        rgb = np.where(a > 1e-6, d[..., :3] / np.maximum(a, 1e-6), 0.0)
        out = np.concatenate([np.clip(rgb, 0, 1), np.clip(a, 0, 1)], -1)
        return np.clip(np.round(out * 255.0), 0, 255).astype(np.uint8)

    def to_pil(self):
        return Image.fromarray(self.pixels(), 'RGBA')


def create_canvas(width, height) -> Canvas:
    return Canvas(width, height)


def canvas_pixels(cv) -> np.ndarray:
    """RGBA8 rows top-down, flattened like the JS Uint8Array view (H * W * 4)."""
    return cv.pixels().reshape(-1)


def fit_text(g, text, x, y, max_w, max_h, family, weight='', align='center', baseline='middle', track=0.0):
    """Fit a single line of text into a box (canvas units); returns the font size used. The JS export, line for
    line: shrink to max_w, then draw (tracked: glyph by glyph)."""
    size = max_h
    g.font = f'{weight} {size}px {family}'.strip()

    def w_of():
        return g.measure_text(text).width + track * size * max(0, len(text) - 1)
    w = w_of()
    if w > max_w:
        size = size * max_w / w
        g.font = f'{weight} {size}px {family}'.strip()
    g.text_align = 'left' if track else align
    g.text_baseline = baseline
    if not track:
        g.fill_text(text, x, y)
        return size
    total = w_of()
    cx = x - total / 2 if align == 'center' else x - total if align == 'right' else x
    for ch in text:
        g.fill_text(ch, cx, y)
        cx += g.measure_text(ch).width + track * size
    return size


# ============================================================================================ relief (numpy) =========

def build_mips(data, w, h):
    """The JS CPU mip chain (2x2 box, integer >> 2), for parity: Blender builds its own GPU mips, so the sets do not
    call it. data: (h * w * 4) uint8. Returns [{'data', 'width', 'height'}, ...]."""
    levels = [{'data': np.asarray(data, np.uint8).reshape(-1), 'width': w, 'height': h}]
    sw, sh = w, h
    src = np.asarray(data, np.uint8).reshape(h, w, 4).astype(np.int32)
    while sw > 1 or sh > 1:
        dw, dh = max(1, sw >> 1), max(1, sh >> 1)
        ys0 = np.minimum(sh - 1, 2 * np.arange(dh))
        ys1 = np.minimum(sh - 1, 2 * np.arange(dh) + 1)
        xs0 = np.minimum(sw - 1, 2 * np.arange(dw))
        xs1 = np.minimum(sw - 1, 2 * np.arange(dw) + 1)
        dst = (src[ys0][:, xs0] + src[ys0][:, xs1] + src[ys1][:, xs0] + src[ys1][:, xs1]) >> 2
        levels.append({'data': dst.astype(np.uint8).reshape(-1), 'width': dw, 'height': dh})
        sw, sh, src = dw, dh, dst
    return levels


def box_blur(src, W, H, r, passes=1):
    """The JS box blur (radius r, edge-clamped, horizontal then vertical, `passes` times) on a flat field."""
    a = np.asarray(src, np.float64).reshape(H, W)
    r = int(r)
    if r <= 0:
        return a.reshape(-1).astype(np.float32)
    k = 2 * r + 1
    for _ in range(passes):
        p = np.pad(a, ((0, 0), (r, r)), mode='edge')
        cs = np.concatenate([np.zeros((H, 1)), np.cumsum(p, axis=1)], axis=1)
        b = (cs[:, k:] - cs[:, :-k]) / k
        p = np.pad(b, ((r, r), (0, 0)), mode='edge')
        cs = np.concatenate([np.zeros((1, W)), np.cumsum(p, axis=0)], axis=0)
        a = (cs[k:, :] - cs[:-k, :]) / k
    return a.reshape(-1).astype(np.float32)


def height_field(cv, blur=2, channel='lum'):
    """A grey height canvas -> {'h': flat float32 heights 0..1 (white = high), 'W', 'H'}, box-blurred twice."""
    W, H = cv.width, cv.height
    p = cv.pixels().reshape(-1, 4).astype(np.float64)
    if channel == 'a':
        h = p[:, 3] / 255.0
    else:
        h = (p[:, 0] * 0.2126 + p[:, 1] * 0.7152 + p[:, 2] * 0.0722) / 255.0
    h = h.astype(np.float32)
    if blur > 0:
        h = box_blur(h, W, H, blur, 2)
    return {'h': h, 'W': W, 'H': H}


def _to_u8(x):
    """A JS Uint8Array store: ToUint8 truncates (the values here stay in 0..255)."""
    return np.floor(np.clip(x, 0.0, 255.0)).astype(np.uint8)


def normal_pixels(hf, strength=4.0) -> np.ndarray:
    """The JS normalTex's pixels: tangent-space normal map (OpenGL, +V up) from a top-down height field, RGBA8
    rows top-down."""
    h = np.asarray(hf['h'], np.float64).reshape(hf['H'], hf['W'])
    hp = np.pad(h, 1, mode='edge')
    dx = (hp[1:-1, 2:] - hp[1:-1, :-2]) * 0.5 * strength
    dyc = (hp[2:, 1:-1] - hp[:-2, 1:-1]) * 0.5 * strength
    nx, ny, nz = -dx, dyc, np.ones_like(dx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    out = np.empty(h.shape + (4,), np.uint8)
    out[..., 0] = _to_u8((nx / ln * 0.5 + 0.5) * 255)
    out[..., 1] = _to_u8((ny / ln * 0.5 + 0.5) * 255)
    out[..., 2] = _to_u8((nz / ln * 0.5 + 0.5) * 255)
    out[..., 3] = 255
    return out


def pack_pixels(chans, W, H) -> np.ndarray:
    """The JS packTex's pixels: up to four grey canvases / float fields in R, G, B, A (missing: 0, alpha 255)."""
    out = np.zeros((H, W, 4), np.uint8)
    for c in range(4):
        s = chans[c] if c < len(chans) else None
        if s is None:
            out[..., c] = 255 if c == 3 else 0
        elif isinstance(s, np.ndarray):
            out[..., c] = _to_u8(np.asarray(s, np.float64).reshape(H, W) * 255.0)
        else:
            out[..., c] = s.pixels()[..., 0]
    return out


# =============================================================================================== matrices ===========

def euler_xyz(rx=0.0, ry=0.0, rz=0.0) -> np.ndarray:
    """three's Matrix4.makeRotationFromEuler for order 'XYZ': Rx @ Ry @ Rz (3 x 3)."""
    a, b = math.cos(rx), math.sin(rx)
    c, d = math.cos(ry), math.sin(ry)
    e, f = math.cos(rz), math.sin(rz)
    ae, af, be, bf = a * e, a * f, b * e, b * f
    return np.array([[c * e, -c * f, d],
                     [af + be * d, ae - bf * d, -b * c],
                     [bf - ae * d, be + af * d, a * c]])


def m4(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0, s=1.0) -> np.ndarray:
    """The JS M4: Matrix4.compose(position, quaternion from Euler XYZ, scale) as a 4 x 4 numpy array (column
    vectors: p' = M @ p)."""
    sv = np.array(s if isinstance(s, (list, tuple, np.ndarray)) else (s, s, s), np.float64)
    M = np.eye(4)
    M[:3, :3] = euler_xyz(rx, ry, rz) * sv[None, :]
    M[:3, 3] = (x, y, z)
    return M


def translation(x, y, z):
    M = np.eye(4)
    M[:3, 3] = (x, y, z)
    return M


def quat_from_unit_vectors(vf, vt):
    """three's Quaternion.setFromUnitVectors -> a 3 x 3 rotation matrix."""
    vf, vt = np.asarray(vf, float), np.asarray(vt, float)
    r = float(np.dot(vf, vt)) + 1.0
    if r < 1e-8:
        r = 0.0
        if abs(vf[0]) > abs(vf[2]):
            q = np.array([-vf[1], vf[0], 0.0, r])
        else:
            q = np.array([0.0, -vf[2], vf[1], r])
    else:
        c = np.cross(vf, vt)
        q = np.array([c[0], c[1], c[2], r])
    q = q / np.linalg.norm(q)
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def look_at_matrix(eye, target, up=(0.0, 1.0, 0.0)):
    """three's Object3D.lookAt for a non-camera object: its +Z toward the target (3 x 3)."""
    eye, target, up = (np.asarray(v, float) for v in (eye, target, up))
    z = target - eye
    if np.linalg.norm(z) < 1e-12:
        z = np.array([0.0, 0.0, 1.0])
    z = z / np.linalg.norm(z)
    x = np.cross(up, z)
    if np.linalg.norm(x) < 1e-12:
        z = z + np.array([1e-4, 0, 0])
        x = np.cross(up, z)
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], 1)


C_THREE = np.array([[1.0, 0, 0, 0], [0, 0, -1.0, 0], [0, 1.0, 0, 0], [0, 0, 0, 1.0]])   # three -> Blender axes


def to_blender_matrix(M3) -> np.ndarray:
    """A three-space 4 x 4 (column vectors) -> the Blender-space matrix C M C^-1."""
    return C_THREE @ np.asarray(M3, float) @ C_THREE.T


def b3(p):
    """A three point / direction -> Blender (x, -z, y)."""
    return (float(p[0]), -float(p[2]), float(p[1]))


# =============================================================================================== geometry ===========

class Geo:
    """An indexed (or not) triangle geometry in three's axes: position (N, 3), normal (N, 3), uv (N, 2), index or
    None, plus optional extra per-vertex attributes {name: (N, k)}."""

    def __init__(self, pos, nrm=None, uv=None, index=None, attrs=None):
        self.pos = np.asarray(pos, np.float64).reshape(-1, 3)
        self.nrm = None if nrm is None else np.asarray(nrm, np.float64).reshape(-1, 3)
        self.uv = None if uv is None else np.asarray(uv, np.float64).reshape(-1, 2)
        self.index = None if index is None else np.asarray(index, np.int64).reshape(-1)
        self.attrs = dict(attrs or {})

    def copy(self):
        return Geo(self.pos.copy(), None if self.nrm is None else self.nrm.copy(),
                   None if self.uv is None else self.uv.copy(), None if self.index is None else self.index.copy(),
                   {k: v.copy() for k, v in self.attrs.items()})

    def apply(self, M):
        """applyMatrix4: positions by M, normals by its normal matrix (normalised)."""
        M = np.asarray(M, float)
        self.pos = self.pos @ M[:3, :3].T + M[:3, 3]
        if self.nrm is not None:
            Nm = np.linalg.inv(M[:3, :3]).T
            n = self.nrm @ Nm.T
            ln = np.linalg.norm(n, axis=1, keepdims=True)
            self.nrm = n / np.where(ln > 0, ln, 1.0)
        return self

    def translate(self, x, y, z):
        self.pos = self.pos + np.array([x, y, z])
        return self

    def scale(self, sx, sy, sz):
        return self.apply(np.diag([sx, sy, sz, 1.0]))

    def rotate3(self, R):
        M = np.eye(4)
        M[:3, :3] = R
        return self.apply(M)

    def non_indexed(self):
        if self.index is None:
            return self.copy()
        i = self.index
        return Geo(self.pos[i], None if self.nrm is None else self.nrm[i], None if self.uv is None else self.uv[i],
                   None, {k: v[i] for k, v in self.attrs.items()})

    def compute_vertex_normals(self):
        """three's computeVertexNormals: area-weighted face normals summed per vertex (indexed) or per face."""
        p = self.pos
        tri = self.index.reshape(-1, 3) if self.index is not None else np.arange(len(p)).reshape(-1, 3)
        fn = np.cross(p[tri[:, 2]] - p[tri[:, 1]], p[tri[:, 0]] - p[tri[:, 1]])
        n = np.zeros_like(p)
        for k in range(3):
            np.add.at(n, tri[:, k], fn)
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        self.nrm = n / np.where(ln > 0, ln, 1.0)
        return self


def box_geometry(w=1.0, h=1.0, d=1.0, ws=1, hs=1, ds=1) -> Geo:
    pos, nrm, uvs, idx = [], [], [], []
    count = [0]

    def plane(u, v, wax, udir, vdir, width, height, depth, gx, gy):
        sw_, sh_ = width / gx, height / gy
        wh, hh, dh = width / 2, height / 2, depth / 2
        gx1, gy1 = gx + 1, gy + 1
        start = count[0]
        for iy in range(gy1):
            y = iy * sh_ - hh
            for ix in range(gx1):
                x = ix * sw_ - wh
                vec = [0.0, 0.0, 0.0]
                vec[u], vec[v], vec[wax] = x * udir, y * vdir, dh
                pos.append(vec)
                n = [0.0, 0.0, 0.0]
                n[wax] = 1.0 if depth > 0 else -1.0
                nrm.append(n)
                uvs.append((ix / gx, 1 - iy / gy))
        for iy in range(gy):
            for ix in range(gx):
                a = start + ix + gx1 * iy
                b = start + ix + gx1 * (iy + 1)
                c = start + (ix + 1) + gx1 * (iy + 1)
                dd = start + (ix + 1) + gx1 * iy
                idx.extend((a, b, dd, b, c, dd))
        count[0] += gx1 * gy1
    X, Y, Z = 0, 1, 2
    plane(Z, Y, X, -1, -1, d, h, w, ds, hs)
    plane(Z, Y, X, 1, -1, d, h, -w, ds, hs)
    plane(X, Z, Y, 1, 1, w, d, h, ws, ds)
    plane(X, Z, Y, 1, -1, w, d, -h, ws, ds)
    plane(X, Y, Z, 1, -1, w, h, d, ws, hs)
    plane(X, Y, Z, -1, -1, w, h, -d, ws, hs)
    return Geo(pos, nrm, uvs, idx)


def cylinder_geometry(rt=1.0, rb=1.0, h=1.0, rs=32, hs=1, open_ended=False, th0=0.0, thl=2 * math.pi) -> Geo:
    rs, hs = int(rs), int(hs)
    pos, nrm, uvs, idx = [], [], [], []
    hh = h / 2
    slope = (rb - rt) / h
    grid = []
    for y in range(hs + 1):
        row = []
        v = y / hs
        r = v * (rb - rt) + rt
        for x in range(rs + 1):
            u = x / rs
            th = u * thl + th0
            s_, c_ = math.sin(th), math.cos(th)
            pos.append((r * s_, -v * h + hh, r * c_))
            n = np.array([s_, slope, c_])
            nrm.append(n / np.linalg.norm(n))
            uvs.append((u, 1 - v))
            row.append(len(pos) - 1)
        grid.append(row)
    for x in range(rs):
        for y in range(hs):
            a, b, c, d = grid[y][x], grid[y + 1][x], grid[y + 1][x + 1], grid[y][x + 1]
            if rt > 0 or y != 0:
                idx.extend((a, b, d))
            if rb > 0 or y != hs - 1:
                idx.extend((b, c, d))

    def cap(top):
        r = rt if top else rb
        sg = 1 if top else -1
        c0 = len(pos)
        for _ in range(rs):
            pos.append((0.0, hh * sg, 0.0))
            nrm.append((0.0, sg, 0.0))
            uvs.append((0.5, 0.5))
        c1 = len(pos)
        for x in range(rs + 1):
            u = x / rs
            th = u * thl + th0
            cs_, sn_ = math.cos(th), math.sin(th)
            pos.append((r * sn_, hh * sg, r * cs_))
            nrm.append((0.0, sg, 0.0))
            uvs.append((cs_ * 0.5 + 0.5, sn_ * 0.5 * sg + 0.5))
        for x in range(rs):
            c, i = c0 + x, c1 + x
            idx.extend((i, i + 1, c) if top else (i + 1, i, c))
    if not open_ended:
        if rt > 0:
            cap(True)
        if rb > 0:
            cap(False)
    return Geo(pos, nrm, uvs, idx)


def cone_geometry(r=1.0, h=1.0, rs=32, hs=1, open_ended=False, th0=0.0, thl=2 * math.pi) -> Geo:
    return cylinder_geometry(0.0, r, h, rs, hs, open_ended, th0, thl)


def sphere_geometry(r=1.0, ws=32, hs=16, phi0=0.0, phil=2 * math.pi, th0=0.0, thl=math.pi) -> Geo:
    ws, hs = max(3, int(ws)), max(2, int(hs))
    th_end = min(th0 + thl, math.pi)
    pos, nrm, uvs, idx = [], [], [], []
    grid = []
    for iy in range(hs + 1):
        row = []
        v = iy / hs
        uoff = 0.0
        if iy == 0 and th0 == 0:
            uoff = 0.5 / ws
        elif iy == hs and th_end == math.pi:
            uoff = -0.5 / ws
        for ix in range(ws + 1):
            u = ix / ws
            p = (-r * math.cos(phi0 + u * phil) * math.sin(th0 + v * thl), r * math.cos(th0 + v * thl),
                 r * math.sin(phi0 + u * phil) * math.sin(th0 + v * thl))
            pos.append(p)
            n = np.array(p)
            ln = np.linalg.norm(n)
            nrm.append(n / ln if ln > 0 else n)
            uvs.append((u + uoff, 1 - v))
            row.append(len(pos) - 1)
        grid.append(row)
    for iy in range(hs):
        for ix in range(ws):
            a, b, c, d = grid[iy][ix + 1], grid[iy][ix], grid[iy + 1][ix], grid[iy + 1][ix + 1]
            if iy != 0 or th0 > 0:
                idx.extend((a, b, d))
            if iy != hs - 1 or th_end < math.pi:
                idx.extend((b, c, d))
    return Geo(pos, nrm, uvs, idx)


def lathe_geometry(points, segments=12, phi0=0.0, phil=2 * math.pi) -> Geo:
    """three r184 LatheGeometry: the profile (r, y) turned about +Y, normals from the profile (averaged at
    corners)."""
    pts = [(float(a), float(b)) for a, b in points]
    segments = int(segments)
    phil = min(max(phil, 0.0), 2 * math.pi)
    init = []
    prev = None
    n_ = len(pts)
    for j in range(n_):
        if j == 0:
            dx, dy = pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1]
            nv = np.array([dy * 1.0, -dx, dy * 0.0])
            prev = nv.copy()
            ln = np.linalg.norm(nv)
            init.append(nv / ln if ln > 0 else nv)
        elif j == n_ - 1:
            init.append(prev.copy())
        else:
            dx, dy = pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1]
            nv = np.array([dy * 1.0, -dx, dy * 0.0])
            cur = nv.copy()
            nv = nv + prev
            ln = np.linalg.norm(nv)
            init.append(nv / ln if ln > 0 else nv)
            prev = cur
    pos, nrm, uvs, idx = [], [], [], []
    for i in range(segments + 1):
        phi = phi0 + i / segments * phil
        s_, c_ = math.sin(phi), math.cos(phi)
        for j in range(n_):
            pos.append((pts[j][0] * s_, pts[j][1], pts[j][0] * c_))
            uvs.append((i / segments, j / (n_ - 1)))
            nrm.append((init[j][0] * s_, init[j][1], init[j][0] * c_))
    for i in range(segments):
        for j in range(n_ - 1):
            base = j + i * n_
            a, b, c, d = base, base + n_, base + n_ + 1, base + 1
            idx.extend((a, b, d, c, d, b))
    return Geo(pos, nrm, uvs, idx)


def torus_geometry(radius=1.0, tube=0.4, rs=12, ts=48, arc=2 * math.pi, th0=0.0, thl=2 * math.pi) -> Geo:
    rs, ts = int(rs), int(ts)
    pos, nrm, uvs, idx = [], [], [], []
    for j in range(rs + 1):
        v = th0 + j / rs * thl
        for i in range(ts + 1):
            u = i / ts * arc
            p = ((radius + tube * math.cos(v)) * math.cos(u), (radius + tube * math.cos(v)) * math.sin(u),
                 tube * math.sin(v))
            pos.append(p)
            n = np.array(p) - np.array([radius * math.cos(u), radius * math.sin(u), 0.0])
            nrm.append(n / np.linalg.norm(n))
            uvs.append((i / ts, j / rs))
    for j in range(1, rs + 1):
        for i in range(1, ts + 1):
            a = (ts + 1) * j + i - 1
            b = (ts + 1) * (j - 1) + i - 1
            c = (ts + 1) * (j - 1) + i
            d = (ts + 1) * j + i
            idx.extend((a, b, d, b, c, d))
    return Geo(pos, nrm, uvs, idx)


def circle_geometry(r=1.0, segments=32, th0=0.0, thl=2 * math.pi) -> Geo:
    segments = max(3, int(segments))
    pos, nrm, uvs, idx = [(0.0, 0.0, 0.0)], [(0, 0, 1.0)], [(0.5, 0.5)], []
    for s in range(segments + 1):
        a = th0 + s / segments * thl
        x, y = r * math.cos(a), r * math.sin(a)
        pos.append((x, y, 0.0))
        nrm.append((0, 0, 1.0))
        uvs.append(((x / r + 1) / 2, (y / r + 1) / 2))
    for i in range(1, segments + 1):
        idx.extend((i, i + 1, 0))
    return Geo(pos, nrm, uvs, idx)


def plane_geometry(w=1.0, h=1.0, ws=1, hs=1) -> Geo:
    gx, gy = int(ws), int(hs)
    pos, nrm, uvs, idx = [], [], [], []
    for iy in range(gy + 1):
        y = iy * h / gy - h / 2
        for ix in range(gx + 1):
            x = ix * w / gx - w / 2
            pos.append((x, -y, 0.0))
            nrm.append((0, 0, 1.0))
            uvs.append((ix / gx, 1 - iy / gy))
    for iy in range(gy):
        for ix in range(gx):
            a = ix + (gx + 1) * iy
            b = ix + (gx + 1) * (iy + 1)
            c = ix + 1 + (gx + 1) * (iy + 1)
            d = ix + 1 + (gx + 1) * iy
            idx.extend((a, b, d, b, c, d))
    return Geo(pos, nrm, uvs, idx)


class QuadraticBezierCurve3:
    """three's QuadraticBezierCurve3 with the base Curve's arc-length tables (getPointAt / getTangentAt)."""

    arc_length_divisions = 200

    def __init__(self, v0, v1, v2):
        self.v = [tuple(float(c) for c in p) for p in (v0, v1, v2)]
        self._lengths = None

    def get_point(self, t):
        u = 1 - t
        return tuple(u * u * self.v[0][k] + 2 * u * t * self.v[1][k] + t * t * self.v[2][k] for k in range(3))

    def get_lengths(self, divisions=None):
        from ...placement._curves import CatmullRomCurve3
        return CatmullRomCurve3.get_lengths(self, divisions)

    def get_u_to_t_mapping(self, u, distance=None):
        from ...placement._curves import CatmullRomCurve3
        return CatmullRomCurve3.get_u_to_t_mapping(self, u, distance)

    def get_point_at(self, u):
        return self.get_point(self.get_u_to_t_mapping(u))

    def get_tangent(self, t):
        from ...placement._curves import CatmullRomCurve3
        return CatmullRomCurve3.get_tangent(self, t)

    def get_tangent_at(self, u):
        return self.get_tangent(self.get_u_to_t_mapping(u))


def catmull_rom(points, closed=False):
    """three's CatmullRomCurve3(points, closed) (centripetal, the default)."""
    from ...placement._curves import CatmullRomCurve3
    return CatmullRomCurve3([tuple(float(c) for c in p) for p in points], closed, 'centripetal')


def tube_geometry(path, tubular=64, radius=1.0, radial=8, closed=False) -> Geo:
    from ...placement._curves import frenet_frames
    _t, N, B = frenet_frames(path, tubular, closed)
    pos, nrm, uvs, idx = [], [], [], []

    def seg(i):
        P = path.get_point_at(i / tubular)
        n_, b_ = N[i], B[i]
        for j in range(radial + 1):
            v = j / radial * math.pi * 2
            sn, cs = math.sin(v), -math.cos(v)
            nv = np.array([cs * n_[0] + sn * b_[0], cs * n_[1] + sn * b_[1], cs * n_[2] + sn * b_[2]])
            nv = nv / (np.linalg.norm(nv) or 1.0)
            nrm.append(nv)
            pos.append((P[0] + radius * nv[0], P[1] + radius * nv[1], P[2] + radius * nv[2]))
    for i in range(tubular):
        seg(i)
    seg(tubular if not closed else 0)
    for i in range(tubular + 1):
        for j in range(radial + 1):
            uvs.append((i / tubular, j / radial))
    for j in range(1, tubular + 1):
        for i in range(1, radial + 1):
            a = (radial + 1) * (j - 1) + (i - 1)
            b = (radial + 1) * j + (i - 1)
            c = (radial + 1) * j + i
            d = (radial + 1) * (j - 1) + i
            idx.extend((a, b, d, b, c, d))
    return Geo(pos, nrm, uvs, idx)


def extrude_polygon(shape_pts, depth) -> Geo:
    """ExtrudeGeometry(shape, {depth, bevelEnabled: false}) for a convex closed shape (non-indexed, flat normals as
    three's computeVertexNormals on its non-indexed buffer). Caps at z = 0 (facing -Z) and z = depth (+Z)."""
    pts = [(float(x), float(y)) for x, y in shape_pts]
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    if area < 0:
        pts = pts[::-1]
    tris = []
    for i in range(1, len(pts) - 1):                                   # a fan (the shapes here are convex)
        a, b, c = pts[0], pts[i], pts[i + 1]
        tris.append(((a[0], a[1], depth), (b[0], b[1], depth), (c[0], c[1], depth)))
        tris.append(((a[0], a[1], 0.0), (c[0], c[1], 0.0), (b[0], b[1], 0.0)))
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        p0, p1, p2, p3 = (a[0], a[1], 0.0), (b[0], b[1], 0.0), (b[0], b[1], depth), (a[0], a[1], depth)
        tris.append((p0, p1, p2))
        tris.append((p0, p2, p3))
    pos = np.array(tris, float).reshape(-1, 3)
    g = Geo(pos, None, np.zeros((len(pos), 2)))
    return g.compute_vertex_normals()


def prep(g: Geo, M=None) -> Geo:
    """The JS prep: non-indexed, the matrix applied, only position / normal / uv kept (uv zeros if absent)."""
    q = g.non_indexed()
    if M is not None:
        q.apply(M)
    if q.nrm is None:
        q.compute_vertex_normals()
    if q.uv is None:
        q.uv = np.zeros((len(q.pos), 2))
    return q


def box_uv(g: Geo, scale=1.0, off=(0.0, 0.0, 0.0)) -> Geo:
    """Box-projected metre UVs from each triangle's face normal (axis-aligned faces get exact world-metre UVs)."""
    p = g.pos.reshape(-1, 3, 3)
    fn = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    ax, ay, az = np.abs(fn[:, 0]), np.abs(fn[:, 1]), np.abs(fn[:, 2])
    v = p + np.asarray(off, float)
    x, y, z = v[..., 0], v[..., 1], v[..., 2]
    use_x = ((ax >= ay) & (ax >= az))[:, None]
    use_y = (~use_x[:, 0] & (ay >= az))[:, None]
    sx, sy, sz = (fn[:, 0] > 0)[:, None], (fn[:, 1] > 0)[:, None], (fn[:, 2] > 0)[:, None]
    u = np.where(use_x, np.where(sx, -z, z), np.where(use_y, x, np.where(sz, x, -x)))
    w = np.where(use_x, y, np.where(use_y, np.where(sy, -z, z), y))
    g.uv = np.stack([u / scale, w / scale], -1).reshape(-1, 2)
    return g


class Bucket:
    """The JS bucket(name): add(geometry, matrix, {uv: 'box' | 'keep', scale, off, uv_scale}) ... then mesh(material)."""

    def __init__(self, lib, name):
        self.lib, self.name, self.list = lib, name, []

    def add(self, g: Geo, M=None, uv='box', scale=1.0, off=(0.0, 0.0, 0.0), uv_scale=None, attrs=None):
        q = prep(g, M)
        if uv == 'box':
            box_uv(q, scale, off)
        elif uv_scale is not None:
            q.uv = q.uv * np.asarray(uv_scale, float)[None, :]
        for k, v in (attrs or {}).items():
            q.attrs[k] = np.broadcast_to(np.asarray(v, float), (len(q.pos),) + np.shape(v)).copy()
        self.list.append(q)
        return self

    def box(self, w, h, d, x, y, z, rx=0.0, ry=0.0, rz=0.0, **o):
        M = np.eye(4)
        if rx or ry or rz:
            M[:3, :3] = euler_xyz(rx, ry, rz)
        M[:3, 3] = (x, y, z)
        return self.add(box_geometry(w, h, d), M, **o)

    def count(self):
        return len(self.list)

    def geometry(self) -> Geo | None:
        if not self.list:
            return None
        keys = set(self.list[0].attrs)
        for q in self.list[1:]:
            keys &= set(q.attrs)
        g = Geo(np.concatenate([q.pos for q in self.list]), np.concatenate([q.nrm for q in self.list]),
                np.concatenate([q.uv for q in self.list]), None,
                {k: np.concatenate([q.attrs[k] for q in self.list]) for k in keys})
        self.list = []
        return g

    def mesh(self, material, parent=None, name=None, **flags):
        g = self.geometry()
        if g is None:
            return None
        return self.lib.mesh_object(name or self.name, g, material, parent=parent, **flags)


def mesh_from_geo(name, g: Geo, weld=True):
    """A Blender mesh from a three-space triangle Geo: positions converted to Z up, three's normals as custom split
    normals (its exact shading), the uv as 'UVMap', extra attributes as point / corner float attributes."""
    import bpy
    q = g.non_indexed() if g.index is not None else g
    P = np.asarray(q.pos, np.float64)
    Pb = np.stack([P[:, 0], -P[:, 2], P[:, 1]], 1)
    n = len(Pb)
    if weld and n:
        key = np.round(Pb, 6)
        uniq, inv = np.unique(key, axis=0, return_inverse=True)
        verts = uniq
        loops_v = inv.reshape(-1)
        t = loops_v.reshape(-1, 3)
        keep = (t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])
        if not keep.all():                     # a triangle welded to a line or a point: drop it with its corners
            kc = np.repeat(keep, 3)
            loops_v = loops_v[kc]
            q = Geo(P[kc], None if q.nrm is None else q.nrm[kc], None if q.uv is None else q.uv[kc], None,
                    {k: v[kc] for k, v in q.attrs.items()})
            n = len(loops_v)
    else:
        verts = Pb
        loops_v = np.arange(n)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', verts.astype(np.float32).ravel())
    nt = n // 3
    me.loops.add(n)
    me.loops.foreach_set('vertex_index', loops_v.astype(np.int32))
    me.polygons.add(nt)
    me.polygons.foreach_set('loop_start', (np.arange(nt) * 3).astype(np.int32))
    me.polygons.foreach_set('loop_total', np.full(nt, 3, np.int32))
    if q.uv is not None:
        uvl = me.uv_layers.new(name='UVMap')
        uvl.data.foreach_set('uv', np.asarray(q.uv, np.float32).ravel())
    for k, v in q.attrs.items():
        v = np.asarray(v, np.float32)
        if v.ndim == 1 or v.shape[1] == 1:
            a = me.attributes.new(k, 'FLOAT', 'CORNER')
            a.data.foreach_set('value', v.ravel())
        elif v.shape[1] == 2:
            a = me.attributes.new(k, 'FLOAT2', 'CORNER')
            a.data.foreach_set('vector', v.ravel())
        else:
            a = me.attributes.new(k, 'FLOAT_VECTOR', 'CORNER')
            vv = v[:, :3]
            a.data.foreach_set('vector', vv.ravel())
    me.update(calc_edges=True)
    if q.nrm is not None and n:
        N = np.asarray(q.nrm, np.float64)
        Nb = np.stack([N[:, 0], -N[:, 2], N[:, 1]], 1)
        me.polygons.foreach_set('use_smooth', np.ones(nt, bool))
        try:
            me.normals_split_custom_set([tuple(x) for x in Nb.astype(np.float32)])
        except (RuntimeError, TypeError, ValueError):
            pass
    return me


# ================================================================================================= glb ===============

def read_glb_meshes(path) -> dict:
    """{mesh name: {'position', 'normal', 'color', 'index'}} from a .glb (float / normalised u16 / u8 accessors), in
    the file's own (three's) axes. Enough for the model library's plain meshes (the DAISY crowd figures)."""
    with open(path, 'rb') as f:
        b = f.read()
    jl = struct.unpack_from('<I', b, 12)[0]
    j = json.loads(b[20:20 + jl])
    off = 20 + jl
    bl = struct.unpack_from('<I', b, off)[0]
    bin_ = b[off + 8:off + 8 + bl]
    CT = {5126: (np.float32, 4), 5123: (np.uint16, 2), 5121: (np.uint8, 1), 5125: (np.uint32, 4)}
    NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}

    def acc(i):
        a = j['accessors'][i]
        bv = j['bufferViews'][a['bufferView']]
        dt, sz = CT[a['componentType']]
        nc = NC[a['type']]
        start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = bv.get('byteStride', 0) or sz * nc
        raw = np.frombuffer(bin_, np.uint8, count=stride * (a['count'] - 1) + sz * nc, offset=start)
        rows = np.lib.stride_tricks.as_strided(raw, (a['count'], sz * nc), (stride, 1))
        arr = np.frombuffer(rows.copy().tobytes(), dt).reshape(a['count'], nc).astype(np.float64)
        if a.get('normalized'):
            arr = arr / float(np.iinfo(dt).max)
        return arr
    out = {}
    for mi, m in enumerate(j['meshes']):
        p = m['primitives'][0]
        at = p['attributes']
        rec = {'position': acc(at['POSITION'])}
        if 'NORMAL' in at:
            rec['normal'] = acc(at['NORMAL'])
        if 'COLOR_0' in at:
            rec['color'] = acc(at['COLOR_0'])
        rec['index'] = acc(p['indices']).astype(np.int64).reshape(-1) if 'indices' in p else None
        out[m.get('name', f'mesh_{mi}')] = rec
    return out


# ======================================================================================= seam-free texture uvs =========

def hash21_np(x, y):
    """The TSL hash21 (Hoskins, hash without sine) in float32, as the GPU computes it: vec2 -> [0, 1)."""
    f = np.float32
    x, y = np.asarray(x, f), np.asarray(y, f)

    def fr(v):
        return (v - np.floor(v)).astype(f)
    p3 = [fr(x * f(0.1031)), fr(y * f(0.1031)), fr(x * f(0.1031))]
    d = p3[0] * (p3[1] + f(33.33)) + p3[1] * (p3[2] + f(33.33)) + p3[2] * (p3[0] + f(33.33))
    p4 = [p3[0] + d, p3[1] + d, p3[2] + d]
    return fr((p4[0] + p4[1]) * p4[2])


def slice_tris(g: Geo, s_of, cuts, eps=1e-7) -> Geo:
    """Split the triangles of a non-indexed Geo along the level lines s = c, c in cuts, where s_of(g) gives each
    corner's s (an affine function of the corner's position or uv, so it interpolates exactly along an edge).

    The point: a texture uv that jumps (a hashed offset per slab or tile) jumps on a mesh edge, never inside a
    triangle. EEVEE samples mipmaps from screen derivatives, and a jump inside a triangle draws a line of the
    smallest mip there; the WebGPU edition sampled those materials with explicit gradients (.grad) instead."""
    q = g.non_indexed()
    P = q.pos.reshape(-1, 3, 3)
    N = (q.nrm if q.nrm is not None else np.zeros_like(q.pos)).reshape(-1, 3, 3)
    UV = (q.uv if q.uv is not None else np.zeros((len(q.pos), 2))).reshape(-1, 3, 2)
    A = {k: v.reshape(len(P), 3, -1) for k, v in q.attrs.items()}
    S = np.asarray(s_of(q), np.float64).reshape(-1, 3)
    for c in sorted(cuts):
        d = S - c
        lo, hi = d.min(1), d.max(1)
        cross = (lo < -eps) & (hi > eps)
        if not cross.any():
            continue
        keep = ~cross
        side = d[cross] >= 0
        cnt = side.sum(1)
        lone = np.where(cnt == 1, np.argmax(side, 1), np.argmin(side, 1))
        order = (lone[:, None] + np.arange(3)[None, :]) % 3            # cyclic: the lone corner first, winding kept
        ti = np.nonzero(cross)[0]

        def rot(arr):
            a = arr[ti]
            return np.take_along_axis(a, order.reshape(len(ti), 3, *([1] * (a.ndim - 2))), axis=1)
        dd = rot(d)
        t1 = (dd[:, 0] / (dd[:, 0] - dd[:, 1]))[:, None]
        t2 = (dd[:, 0] / (dd[:, 0] - dd[:, 2]))[:, None]

        def split(arr):
            a = rot(arr)
            A0, B0, C0 = a[:, 0], a[:, 1], a[:, 2]
            sh = (-1,) + (1,) * (A0.ndim - 1)
            X_ = A0 + (B0 - A0) * t1.reshape(sh)
            Y_ = A0 + (C0 - A0) * t2.reshape(sh)
            return np.concatenate([np.stack([A0, X_, Y_], 1), np.stack([X_, B0, C0], 1), np.stack([X_, C0, Y_], 1)])

        def cat(arr):
            return np.concatenate([arr[keep], split(arr)])
        P, N, UV, S = cat(P), cat(N), cat(UV), cat(S)
        A = {k: cat(v) for k, v in A.items()}
    ln = np.linalg.norm(N, axis=2, keepdims=True)
    N = N / np.where(ln > 0, ln, 1.0)
    out = Geo(P.reshape(-1, 3), N.reshape(-1, 3), UV.reshape(-1, 2), None,
              {k: v.reshape(len(P) * 3, -1) for k, v in A.items()})
    return out


# =================================================================================================== Blender =========
# Everything below needs bpy. Light units: three r155+ shades a punctual light of I candela as irradiance I / d^2
# with no 683 lm/W factor, so the sets' levels carry over as radiometric numbers: a point or spot lamp is
# W = 4 pi cd (cd_watts), and everything that is light without a lamp (emissive paint, unlit glass and screens, the
# environment, the hemisphere light, fog) is three's number as it is (SPEC = 1). The view exposure that shows it as
# three's renderer did is log2 of the look's exposure (0 stops at 1.0). This is the convention of the other round-two
# sets (the race, the interiors, the funeral), so the conductor cuts between them without touching the exposure, and
# a character dropped in (the VRM add-on's MToon, which emits its lit colour) renders as it does there. The glTF
# importer's / 683 (look/lighting.candela_to_watts) is photometric: lamps and paint at / 683 need a +9.42-stop view
# exposure, and that exposure blows a VRM's MToon out to white.

SPEC = 1.0


def cd_watts(cd) -> float:
    """three's PointLight / SpotLight intensity (candela) -> Blender point / spot power, W = 4 pi cd (irradiance
    cd / d^2 as three shades it)."""
    return float(cd) * 4.0 * math.pi


def view_exposure(three_exposure=1.0) -> float:
    """The scene view exposure (stops) that shows a set lit in three's numbers the way three's renderer did at its
    toneMappingExposure (0 at 1.0)."""
    return math.log2(float(three_exposure))


def eevee_gi(scene, traced=False, max_roughness=0.5):
    """The sets' EEVEE lighting: global illumination (fast GI, which runs inside EEVEE's ray tracing, so the ray
    tracing is on), shadows on, and the reflections: from the light probes ('PROBE', the WebGPU editions' SSR-off
    picture: painted mirrors and env reflections) or screen-traced (traced=True). Returns scene.eevee."""
    ee = scene.eevee
    ee.use_shadows = True
    ee.use_raytracing = True
    ee.ray_tracing_method = 'SCREEN' if traced else 'PROBE'
    ee.ray_tracing_options.trace_max_roughness = float(max_roughness)
    ee.use_fast_gi = True
    ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
    return ee


# The AgX look nearest three's ACESFilmicToneMapping (its x exposure / 0.6 included), the WebGPU frames' tone. Measured
# in Blender 5.2 (sRGB 8-bit for scene-linear grey 0.01 / 0.05 / 0.18 / 1 / 5): three's ACES 8 / 50 / 127 / 226 / 251,
# this look 10 / 49 / 118 / 208 / 248, plain AgX 18 / 58 / 118 / 197 / 237 (twice as light in the deep darks, which is
# why the marble's veins, the pickets' coats and the patch read lighter than the WebGPU frames under it).
ACES_LIKE_LOOK = 'AgX - Medium High Contrast'


def hex_srgb(h):
    """0xRRGGBB -> sRGB-encoded (r, g, b) in 0..1 (a canvas or a light's displayed colour)."""
    if isinstance(h, str):
        h = int(h.lstrip('#'), 16)
    return (((h >> 16) & 255) / 255.0, ((h >> 8) & 255) / 255.0, (h & 255) / 255.0)


def image_from_rgba(name, rgba, srgb=True, alpha_mode='CHANNEL_PACKED', pack=True, top_down=True, interpolation=None,
                    extension=None):
    """(H, W, 4) uint8 (or float) pixels -> a packed bpy Image. top_down: row 0 is the canvas's top (three's dataTex
    flipped the rows so v = 0 is the bottom; Blender's pixel rows start at the bottom, the same flip). The image
    remembers how a set samples it (interpolation, extension) for NB.tex."""
    import bpy
    a = np.asarray(rgba)
    if a.ndim == 2:
        a = a[..., None]
    H, W, C = a.shape
    if C < 4:
        one = 255 if a.dtype == np.uint8 else 1.0
        if C == 1:
            a = np.concatenate([a, a, a, np.full((H, W, 1), one, a.dtype)], 2)
        else:
            a = np.concatenate([a, np.full((H, W, 4 - C), one, a.dtype)], 2)
    if top_down:
        a = a[::-1]
    fb = a.dtype != np.uint8
    img = bpy.data.images.new(name, W, H, alpha=True, float_buffer=fb)
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    if fb and hasattr(img, 'use_half_precision'):
        img.use_half_precision = False
    px = (a.astype(np.float32) / 255.0) if a.dtype == np.uint8 else a.astype(np.float32)
    img.pixels.foreach_set(np.ascontiguousarray(px).ravel())
    img.alpha_mode = alpha_mode
    if pack:
        img.pack()
    if interpolation:
        img['uf_interp'] = interpolation
    if extension:
        img['uf_ext'] = extension
    return img


def _wrap_ext(wrap):
    """three's wrap -> an Image Texture extension: 'repeat' / 'clamp' (ClampToEdge = EXTEND) / 'mirror'."""
    w = str(wrap).lower()
    return 'REPEAT' if 'repeat' in w else 'MIRROR' if 'mirror' in w else 'EXTEND'


REPEAT, CLAMP = 'repeat', 'clamp'


# ------------------------------------------------------------------------------------------- the node graph ---

def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _sock(coll, identifier):
    """A node socket by its identifier (names repeat on the Mix node: 'Factor' is both its float and vector input)."""
    for s in coll:
        if s.identifier == identifier:
            return s
    raise KeyError(identifier)


class X:
    """A value in a node graph being written: a Python constant (a float, or a 3-tuple) or an output socket, with its
    kind ('f' a float, 'v' a vector or colour). Arithmetic makes Math / Vector Math nodes; constants fold in Python, so
    a ported TSL expression reads like the JS and costs only the nodes it needs. A float meets a vector by broadcast
    (Blender splats a float socket linked into a vector input)."""
    __slots__ = ('nb', 'v', 'k', '_sep')

    def __init__(self, nb, v, k):
        self.nb, self.v, self.k, self._sep = nb, v, k, None

    @property
    def is_const(self):
        return not hasattr(self.v, 'node')

    def __add__(self, o): return self.nb.op('ADD', self, o)
    def __radd__(self, o): return self.nb.op('ADD', o, self)
    def __sub__(self, o): return self.nb.op('SUBTRACT', self, o)
    def __rsub__(self, o): return self.nb.op('SUBTRACT', o, self)
    def __mul__(self, o): return self.nb.op('MULTIPLY', self, o)
    def __rmul__(self, o): return self.nb.op('MULTIPLY', o, self)
    def __truediv__(self, o): return self.nb.op('DIVIDE', self, o)
    def __rtruediv__(self, o): return self.nb.op('DIVIDE', o, self)
    def __neg__(self): return self.nb.op('MULTIPLY', self, -1.0)

    # TSL spellings, so a ported line can stay close to the JS
    def add(self, o): return self + o
    def sub(self, o): return self - o
    def mul(self, o): return self * o
    def div(self, o): return self / o
    def negate(self): return -self
    def one_minus(self): return 1.0 - self

    def comp(self, i):
        return self.nb.comp(self, i)

    x = property(lambda s: s.comp(0))
    y = property(lambda s: s.comp(1))
    z = property(lambda s: s.comp(2))
    r, g, b = x, y, z


def _fold(op, a, b):
    va, vb = isinstance(a, tuple), isinstance(b, tuple)
    if va or vb:
        A = a if va else (a, a, a)
        Bv = b if vb else (b, b, b)
        return tuple(_fold(op, p, q) for p, q in zip(A, Bv))
    if op == 'ADD':
        return a + b
    if op == 'SUBTRACT':
        return a - b
    if op == 'MULTIPLY':
        return a * b
    if op == 'DIVIDE':
        return a / b if b != 0 else 0.0
    if op == 'MINIMUM':
        return min(a, b)
    if op == 'MAXIMUM':
        return max(a, b)
    if op == 'POWER':
        return math.pow(a, b) if a > 0 or float(b).is_integer() else 0.0
    if op == 'LESS_THAN':
        return 1.0 if a < b else 0.0
    if op == 'GREATER_THAN':
        return 1.0 if a > b else 0.0
    if op == 'ARCTAN2':
        return math.atan2(a, b)
    if op == 'FLOORED_MODULO':
        return a - b * math.floor(a / b) if b != 0 else 0.0
    raise ValueError(op)


_UNARY_PY = {
    'ABSOLUTE': abs, 'FLOOR': math.floor, 'FRACT': lambda v: v - math.floor(v), 'SINE': math.sin, 'COSINE': math.cos,
    'EXPONENT': math.exp, 'SQRT': lambda v: math.sqrt(max(v, 0.0)), 'SIGN': lambda v: (v > 0) - (v < 0),
    'ROUND': lambda v: math.floor(v + 0.5),
}
_UNARY_VEC = {'ABSOLUTE': 'ABSOLUTE', 'FLOOR': 'FLOOR', 'FRACT': 'FRACTION', 'SINE': 'SINE', 'COSINE': 'COSINE',
              'SIGN': 'SIGN', 'ROUND': 'ROUND'}


class NB:
    """Writes math into a shader node tree (or a Geometry Nodes tree, geo=True) through X values.

    Inputs are given in three's axes where the WebGPU material read them (positionLocal, normalLocal, positionWorld,
    cameraPosition ...): three (x, y, z) = Blender (x, z, -y), so ported math runs on the same numbers."""

    def __init__(self, tree, lib=None, geo=False, x0=-3000, y0=1200):
        self.t, self.lib, self.geo = tree, lib, geo
        self.k, self.x0, self.y0 = 0, x0, y0
        self._cache = {}

    # ------------------------------------------------------------------------------------------------ nodes
    def node(self, idname, **props):
        n = self.t.nodes.new(idname)
        col, row = divmod(self.k, 24)
        n.location = (self.x0 + col * 190, self.y0 - row * 48)
        n.hide = True
        self.k += 1
        for key, val in props.items():
            setattr(n, key, val)
        return n

    def w(self, v):
        """Anything -> X: X stays, numbers and tuples become constants, a list / tuple holding X builds a vector, a
        socket becomes an X of its kind."""
        if isinstance(v, X):
            return v
        if _is_num(v):
            return X(self, float(v), 'f')
        if isinstance(v, (tuple, list)):
            vals = list(v)
            if len(vals) == 2:
                vals.append(0.0)
            if all(_is_num(c) for c in vals):
                return X(self, tuple(float(c) for c in vals[:3]), 'v')
            return self.vec3(*vals[:3])
        if hasattr(v, 'node'):                                   # a socket
            return X(self, v, 'f' if v.type in ('VALUE', 'INT', 'BOOLEAN') else 'v')
        raise TypeError(f'NB: cannot use {v!r} in a graph')

    def put(self, sock, v):
        x = self.w(v)
        if x.is_const:
            dv = sock.default_value
            if hasattr(dv, '__len__'):
                n = len(dv)
                vals = list(x.v) if isinstance(x.v, tuple) else [x.v] * 3
                vals = vals[:n] + [1.0] * (n - len(vals))
                sock.default_value = vals
            else:
                c = x.v
                sock.default_value = (sum(c) / 3.0) if isinstance(c, tuple) else c
        else:
            self.t.links.new(x.v, sock)
        return sock

    def const(self, v):
        return self.w(v)

    # ------------------------------------------------------------------------------------------- arithmetic
    def op(self, op, a, b):
        a, b = self.w(a), self.w(b)
        vec = a.k == 'v' or b.k == 'v'
        if a.is_const and b.is_const:
            return X(self, _fold(op, a.v, b.v), 'v' if vec else 'f')
        zero = (0.0, 0.0, 0.0) if vec else 0.0
        if op == 'MULTIPLY':
            for p, q in ((a, b), (b, a)):
                if p.is_const and p.v in (1.0, (1.0, 1.0, 1.0)) and (q.k == 'v' or p.k == 'f'):
                    return q
                if p.is_const and p.v in (0.0, (0.0, 0.0, 0.0)):
                    return X(self, zero, 'v' if vec else 'f')
        if op == 'ADD':
            for p, q in ((a, b), (b, a)):
                if p.is_const and p.v in (0.0, (0.0, 0.0, 0.0)) and (q.k == 'v' or p.k == 'f'):
                    return q
        if op in ('SUBTRACT', 'DIVIDE') and b.is_const and b.v in ((0.0, (0.0, 0.0, 0.0)) if op == 'SUBTRACT' else
                                                                    (1.0, (1.0, 1.0, 1.0))) and (a.k == 'v' or b.k == 'f'):
            return a
        if vec:
            if op in ('LESS_THAN', 'GREATER_THAN', 'ARCTAN2', 'FLOORED_MODULO'):
                ax, bx = [self.w(t) for t in (a, b)]
                return self.vec3(*[self.op(op, ax.comp(i), bx.comp(i)) for i in range(3)])
            n = self.node('ShaderNodeVectorMath', operation=op)
            self.put(n.inputs[0], a)
            self.put(n.inputs[1], b)
            return X(self, n.outputs['Vector'], 'v')
        n = self.node('ShaderNodeMath', operation=op)
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        return X(self, n.outputs[0], 'f')

    def u(self, op, a):
        a = self.w(a)
        if a.is_const:
            f = _UNARY_PY[op]
            return X(self, tuple(float(f(c)) for c in a.v) if a.k == 'v' else float(f(a.v)), a.k)
        if a.k == 'v':
            vop = _UNARY_VEC.get(op)
            if vop is None:
                return self.vec3(*[self.u(op, a.comp(i)) for i in range(3)])
            n = self.node('ShaderNodeVectorMath', operation=vop)
            self.put(n.inputs[0], a)
            return X(self, n.outputs['Vector'], 'v')
        n = self.node('ShaderNodeMath', operation=op)
        self.put(n.inputs[0], a)
        return X(self, n.outputs[0], 'f')

    def abs(self, a): return self.u('ABSOLUTE', a)
    def floor(self, a): return self.u('FLOOR', a)
    def fract(self, a): return self.u('FRACT', a)
    def sin(self, a): return self.u('SINE', a)
    def cos(self, a): return self.u('COSINE', a)
    def exp(self, a): return self.u('EXPONENT', a)
    def sqrt(self, a): return self.u('SQRT', a)
    def sign(self, a): return self.u('SIGN', a)
    def round(self, a): return self.u('ROUND', a)
    def min(self, a, b): return self.op('MINIMUM', a, b)
    def max(self, a, b): return self.op('MAXIMUM', a, b)
    def pow(self, a, b): return self.op('POWER', a, b)
    def atan2(self, y, x): return self.op('ARCTAN2', y, x)
    def mod(self, a, b): return self.op('FLOORED_MODULO', a, b)
    def lt(self, a, b): return self.op('LESS_THAN', a, b)
    def gt(self, a, b): return self.op('GREATER_THAN', a, b)

    def step(self, edge, x):
        """GLSL step: 1 where x >= edge."""
        return 1.0 - self.lt(x, edge)

    def clamp(self, x, lo=0.0, hi=1.0):
        return self.max(self.min(x, hi), lo)

    def smoothstep(self, a, b, x):
        """GLSL smoothstep, also with a > b (= 1 - smoothstep(b, a, x), the sets' ss helper): a Map Range."""
        a, b, x = self.w(a), self.w(b), self.w(x)
        if a.is_const and b.is_const and x.is_const:
            if a.v == b.v:
                return X(self, 0.0 if x.v < a.v else 1.0, 'f')
            k = clamp01((x.v - a.v) / (b.v - a.v))
            return X(self, k * k * (3 - 2 * k), 'f')
        n = self.node('ShaderNodeMapRange', data_type='FLOAT', interpolation_type='SMOOTHSTEP', clamp=True)
        self.put(n.inputs['Value'], x)
        self.put(n.inputs['From Min'], a)
        self.put(n.inputs['From Max'], b)
        self.put(n.inputs['To Min'], 0.0)
        self.put(n.inputs['To Max'], 1.0)
        return X(self, n.outputs['Result'], 'f')

    ss = smoothstep

    def mix(self, a, b, t):
        """GLSL mix (unclamped)."""
        a, b, t = self.w(a), self.w(b), self.w(t)
        if t.is_const and t.k == 'f':
            if t.v == 0.0:
                return a if (a.k == 'v' or b.k == 'f') else self.vec3(a, a, a)
            if t.v == 1.0:
                return b if (b.k == 'v' or a.k == 'f') else self.vec3(b, b, b)
        if a.is_const and b.is_const and t.is_const:
            return a + (b - a) * t
        if a.k == 'f' and b.k == 'f' and t.k == 'f':
            n = self.node('ShaderNodeMix', data_type='FLOAT', clamp_factor=False)
            self.put(_sock(n.inputs, 'Factor_Float'), t)
            self.put(_sock(n.inputs, 'A_Float'), a)
            self.put(_sock(n.inputs, 'B_Float'), b)
            return X(self, _sock(n.outputs, 'Result_Float'), 'f')
        n = self.node('ShaderNodeMix', data_type='VECTOR', clamp_factor=False,
                      factor_mode='UNIFORM' if t.k == 'f' else 'NON_UNIFORM')
        self.put(_sock(n.inputs, 'Factor_Float' if t.k == 'f' else 'Factor_Vector'), t)
        self.put(_sock(n.inputs, 'A_Vector'), a)
        self.put(_sock(n.inputs, 'B_Vector'), b)
        return X(self, _sock(n.outputs, 'Result_Vector'), 'v')

    def select(self, c, a, b):
        """TSL select(cond, a, b) with cond a 0 / 1 float."""
        return self.mix(b, a, c)

    # ------------------------------------------------------------------------------------------------ vectors
    def vec3(self, x, y, z=0.0):
        xs = [self.w(c) for c in (x, y, z)]
        if all(c.is_const for c in xs):
            return X(self, tuple(float(c.v) for c in xs), 'v')
        n = self.node('ShaderNodeCombineXYZ')
        for i, c in enumerate(xs):
            self.put(n.inputs[i], c)
        return X(self, n.outputs[0], 'v')

    def vec2(self, x, y):
        return self.vec3(x, y, 0.0)

    def comp(self, a, i):
        a = self.w(a)
        if a.k == 'f':
            return a
        if a.is_const:
            return X(self, a.v[i], 'f')
        if a._sep is None:
            n = self.node('ShaderNodeSeparateXYZ')
            self.put(n.inputs[0], a)
            a._sep = n
        return X(self, a._sep.outputs[i], 'f')

    def dot(self, a, b):
        a, b = self.w(a), self.w(b)
        if a.is_const and b.is_const:
            return X(self, sum(p * q for p, q in zip(a.v, b.v)), 'f')
        n = self.node('ShaderNodeVectorMath', operation='DOT_PRODUCT')
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        return X(self, n.outputs['Value'], 'f')

    def length(self, a):
        a = self.w(a)
        if a.is_const:
            return X(self, math.sqrt(sum(c * c for c in a.v)), 'f')
        n = self.node('ShaderNodeVectorMath', operation='LENGTH')
        self.put(n.inputs[0], a)
        return X(self, n.outputs['Value'], 'f')

    def normalize(self, a):
        a = self.w(a)
        if a.is_const:
            ln = math.sqrt(sum(c * c for c in a.v)) or 1.0
            return X(self, tuple(c / ln for c in a.v), 'v')
        n = self.node('ShaderNodeVectorMath', operation='NORMALIZE')
        self.put(n.inputs[0], a)
        return X(self, n.outputs['Vector'], 'v')

    def cross(self, a, b):
        n = self.node('ShaderNodeVectorMath', operation='CROSS_PRODUCT')
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        return X(self, n.outputs['Vector'], 'v')

    def lum(self, c):
        return self.dot(c, (0.2126, 0.7152, 0.0722))

    def hex(self, h, k=1.0):
        return X(self, hex_linear(h, k), 'v')

    def hash21(self, p):
        """TSL hash21 (Hoskins): vec2 -> [0, 1), written out exactly."""
        p = self.w(p)
        px, py = p.x, p.y
        p3 = self.fract(self.vec3(px, py, px) * 0.1031)
        p4 = p3 + self.dot(p3, self.vec3(p3.y, p3.z, p3.x) + 33.33)
        return self.fract((p4.x + p4.y) * p4.z)

    # ------------------------------------------------------------------------------------------------- noise
    def mx_noise(self, p):
        """three's mx_noise_float(p): Blender's Noise Texture, detail 0, not normalized (eidoblend.fx._noise)."""
        n = self.node('ShaderNodeTexNoise', noise_dimensions='3D', noise_type='FBM', normalize=False)
        self.put(n.inputs['Vector'], p)
        for k, v in (('Scale', 1.0), ('Detail', 0.0), ('Roughness', 0.5), ('Lacunarity', 2.0), ('Distortion', 0.0)):
            self.put(n.inputs[k], v)
        return X(self, n.outputs['Fac'], 'f')

    def mx_fbm(self, p, octaves=3, lacunarity=2.0, diminish=0.5):
        """three's mx_fractal_noise_float(p, octaves, lacunarity, diminish): the Noise Texture's fBm, not normalized."""
        n = self.node('ShaderNodeTexNoise', noise_dimensions='3D', noise_type='FBM', normalize=False)
        self.put(n.inputs['Vector'], p)
        for k, v in (('Scale', 1.0), ('Detail', float(octaves) - 1.0), ('Roughness', diminish),
                     ('Lacunarity', lacunarity), ('Distortion', 0.0)):
            self.put(n.inputs[k], v)
        return X(self, n.outputs['Fac'], 'f')

    # ------------------------------------------------------------------------------------------------ inputs
    def _once(self, key, idname, **props):
        n = self._cache.get(key)
        if n is None:
            n = self._cache[key] = self.node(idname, **props)
        return n

    def three(self, v):
        """A Blender-axes vector -> three's axes (x, z, -y)."""
        v = self.w(v)
        return self.vec3(v.x, v.z, -v.y)

    def blender(self, v):
        """A three-axes vector -> Blender's (x, -z, y)."""
        v = self.w(v)
        return self.vec3(v.x, -v.z, v.y)

    def P(self):
        """positionLocal (three axes): the object-space position."""
        if 'P' not in self._cache:
            self._cache['P'] = self.three(self._once('tc', 'ShaderNodeTexCoord').outputs['Object'])
        return self._cache['P']

    def N_local(self):
        """normalLocal (three axes): the object-space normal."""
        if 'Nl' not in self._cache:
            self._cache['Nl'] = self.three(self._once('tc', 'ShaderNodeTexCoord').outputs['Normal'])
        return self._cache['Nl']

    def P_world(self):
        if 'Pw' not in self._cache:
            self._cache['Pw'] = self.three(self._once('geo', 'ShaderNodeNewGeometry').outputs['Position'])
        return self._cache['Pw']

    def N_world(self):
        if 'Nw' not in self._cache:
            self._cache['Nw'] = self.three(self._once('geo', 'ShaderNodeNewGeometry').outputs['Normal'])
        return self._cache['Nw']

    def incoming(self):
        """Toward the camera, world (three axes), unit."""
        if 'I' not in self._cache:
            self._cache['I'] = self.three(self._once('geo', 'ShaderNodeNewGeometry').outputs['Incoming'])
        return self._cache['I']

    def view_dist(self):
        return X(self, self._once('cam', 'ShaderNodeCameraData').outputs['View Distance'], 'f')

    def view_z(self):
        return X(self, self._once('cam', 'ShaderNodeCameraData').outputs['View Z Depth'], 'f')

    def cam_world(self):
        """cameraPosition (world, three axes)."""
        if 'Cw' not in self._cache:
            self._cache['Cw'] = self.P_world() + self.incoming() * self.view_dist()
        return self._cache['Cw']

    def cam_local(self):
        """modelWorldMatrixInverse * cameraPosition (three axes): the camera in the object's own space."""
        if 'Cl' not in self._cache:
            n = self.node('ShaderNodeVectorTransform', vector_type='POINT', convert_from='WORLD', convert_to='OBJECT')
            self.put(n.inputs[0], self.blender(self.cam_world()))
            self._cache['Cl'] = self.three(X(self, n.outputs[0], 'v'))
        return self._cache['Cl']

    def uv(self, name='UVMap'):
        key = 'uv:' + name
        if key not in self._cache:
            n = self.node('ShaderNodeUVMap', uv_map=name)
            self._cache[key] = X(self, n.outputs['UV'], 'v')
        return self._cache[key]

    def attr(self, name, kind='f'):
        key = 'attr:' + name
        if key not in self._cache:
            self._cache[key] = self.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name=name)
        n = self._cache[key]
        return X(self, n.outputs['Fac'] if kind == 'f' else n.outputs['Vector'], kind)

    def U(self, name):
        """A set uniform: a Value node driven by the set root's custom property (keyed by update())."""
        key = 'U:' + name
        if key not in self._cache:
            owner = self.lib.owner if self.lib is not None else None
            n = self.node('ShaderNodeValue', label=name)
            n.outputs[0].default_value = float(owner.get(name, 0.0)) if owner is not None else 0.0
            if owner is not None:
                drive_socket(n.outputs[0], owner, name)
            self._cache[key] = X(self, n.outputs[0], 'f')
        return self._cache[key]

    def facing(self):
        """|N . V| at the shading point (the view-angle cosine)."""
        return self.abs(self.dot(self.N_world(), self.incoming()))

    def fwidth_est(self, per_metre):
        """fwidth of a quantity that changes `per_metre` along the surface: one pixel's footprint there (the 'pix'
        uniform x view depth), stretched by the view angle. Blender's shader nodes have no screen derivatives."""
        return self.view_z() * self.U('pix') * per_metre / self.max(self.facing(), 0.08)

    # ------------------------------------------------------------------------------------------------ textures
    def tex(self, img, uv, interpolation=None, extension=None):
        """texture(img, uv) -> (rgb, alpha). uv: an X (only x, y count)."""
        interp = interpolation or (img.get('uf_interp') if img is not None else None) or 'Linear'
        ext = extension or (img.get('uf_ext') if img is not None else None) or 'REPEAT'
        n = self.node('ShaderNodeTexImage', image=img, interpolation=interp, extension=ext)
        self.put(n.inputs['Vector'], uv)
        return X(self, n.outputs['Color'], 'v'), X(self, n.outputs['Alpha'], 'f')

    def normal_map(self, rgb, strength=1.0, flip_x=False, uv_map='UVMap'):
        """TSL normalMap(texture, vec2(s, s)) -> a Normal Map node (tangent space of the mesh's uv, OpenGL maps).
        flip_x: the map's X reversed (a mirrored sample)."""
        c = self.w(rgb)
        if flip_x:
            c = self.vec3(1.0 - c.x, c.y, c.z)
        n = self.node('ShaderNodeNormalMap', space='TANGENT', uv_map=uv_map)
        self.put(n.inputs['Strength'], strength)
        self.put(n.inputs['Color'], c)
        return X(self, n.outputs['Normal'], 'v')

    def bump(self, height, strength=1.0, distance=0.01, normal=None):
        n = self.node('ShaderNodeBump')
        self.put(n.inputs['Height'], height)
        self.put(n.inputs['Strength'], strength)
        self.put(n.inputs['Distance'], distance)
        if normal is not None:
            self.put(n.inputs['Normal'], normal)
        return X(self, n.outputs['Normal'], 'v')

    def fog_factor(self, density):
        """FogExp2: 1 - exp(-(density z)^2), z the view depth."""
        d = self.view_z() * float(density)
        return 1.0 - self.exp(-(d * d))


def drive_socket(sock, owner, prop, path='default_value'):
    """sock.<path> follows owner[prop] through a one-variable AVERAGE driver (no Python runs: it evaluates in a blend
    opened with auto-run off)."""
    fc = sock.driver_add(path)
    d = fc.driver
    d.type = 'AVERAGE'
    for v in list(d.variables):
        d.variables.remove(v)
    v = d.variables.new()
    v.name = 'v'
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'
    v.targets[0].id = owner
    v.targets[0].data_path = f'["{prop}"]'
    return fc


# --------------------------------------------------------------------------------------------- materials ---

class Mat:
    """A material written with NB: standard (Principled, three's MeshStandard / MeshPhysical NodeMaterial) or unlit
    (three's MeshBasicNodeMaterial: an Emission, alpha-blended or additive)."""

    def __init__(self, lib, name):
        import bpy
        m = bpy.data.materials.new(name)
        if lib is not None:
            lib.own(m)
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        self.m, self.lib = m, lib
        self.nb = NB(nt, lib)
        self.out = nt.nodes.new('ShaderNodeOutputMaterial')
        self.out.location = (400, 0)

    def _finish(self, shader, side, method, fog, alpha=None):
        """The output: `shader` fogged by three's FogExp2 when fog is given, then side and render method. A surface
        with an alpha fogs only what it covers, Mix(f, S, Mix(alpha, Transparent, Emission(fog colour))): three fogged
        a fragment's colour and kept its alpha, so the chain link's open diamonds show the yard behind them unveiled."""
        nb, m = self.nb, self.m
        if fog:
            f = nb.fog_factor(fog['density'])
            em = nb.node('ShaderNodeEmission')
            nb.put(em.inputs['Color'], hex_linear(fog['color'], SPEC))
            nb.put(em.inputs['Strength'], 1.0)
            haze = em.outputs[0]
            a = None if alpha is None else nb.w(alpha)
            if a is not None and not (a.is_const and a.v >= 1.0):
                tr = nb.node('ShaderNodeBsdfTransparent')
                cov = nb.node('ShaderNodeMixShader')
                nb.put(cov.inputs[0], nb.clamp(a, 0.0, 1.0))
                nb.t.links.new(tr.outputs[0], cov.inputs[1])
                nb.t.links.new(em.outputs[0], cov.inputs[2])
                haze = cov.outputs[0]
            mx = nb.node('ShaderNodeMixShader')
            nb.put(mx.inputs[0], f)
            nb.t.links.new(shader, mx.inputs[1])
            nb.t.links.new(haze, mx.inputs[2])
            shader = mx.outputs[0]
        nb.t.links.new(shader, self.out.inputs['Surface'])
        if side == 'back':
            raise ValueError('Mat: BackSide meshes are built with their winding reversed (side="front")')
        m.use_backface_culling = side == 'front'
        if method:
            m.surface_render_method = method
        return m

    def standard(self, color, rough=1.0, metal=0.0, normal=None, emissive=None, alpha=None, sheen=None,
                 sheen_rough=0.3, sheen_color=(1.0, 1.0, 1.0), coat=None, coat_rough=0.03, side='double',
                 method=None, fog=None, emissive_scale=SPEC):
        """emissive in three's numbers (x SPEC here). side: 'front' culls back faces (three's FrontSide on an open
        surface), 'double' draws both. The set's environment lights the material through the World (make_world)."""
        nb = self.nb
        b = nb.node('ShaderNodeBsdfPrincipled')
        b.hide = False
        b.location = (100, 0)
        nb.put(b.inputs['Base Color'], color)
        rough_c = nb.clamp(rough, 0.0, 1.0) if not nb.w(rough).is_const else rough
        nb.put(b.inputs['Roughness'], rough_c)
        nb.put(b.inputs['Metallic'], metal)
        if normal is not None:
            nb.put(b.inputs['Normal'], normal)
        if emissive is not None:
            nb.put(b.inputs['Emission Color'], nb.w(emissive) * emissive_scale)
            nb.put(b.inputs['Emission Strength'], 1.0)
        else:
            nb.put(b.inputs['Emission Strength'], 0.0)
        if alpha is not None:
            nb.put(b.inputs['Alpha'], alpha)
        if sheen is not None:
            nb.put(b.inputs['Sheen Weight'], sheen)
            nb.put(b.inputs['Sheen Roughness'], sheen_rough)
            nb.put(b.inputs['Sheen Tint'], sheen_color)
        if coat is not None:
            nb.put(b.inputs['Coat Weight'], coat)
            nb.put(b.inputs['Coat Roughness'], coat_rough)
        return self._finish(b.outputs[0], side, method, fog, alpha)

    def unlit(self, color, alpha=None, additive=False, side='double', fog=None, scale=SPEC, method=None,
              depth_write=None):
        """MeshBasicNodeMaterial: colour in three's numbers (x scale). additive: AdditiveBlending (emission over a
        fully transparent surface, BLENDED); alpha: normal blending (BLENDED unless method says otherwise).
        depth_write: three's depthWrite. False (the default for additive: every additive material of the sets has
        it) blends every layer of the object, as three drew an instanced cloud of puffs or a double-sided cone in one
        call (EEVEE's Transparency Overlap); True keeps the front-most layer of the object only (EEVEE's depth
        prepass), which hid the steam behind its own front puffs and halved the beams and the door's shafts."""
        nb = self.nb
        c = nb.w(color)
        if fog:
            c = nb.mix(c, hex_linear(fog['color']), nb.fog_factor(fog['density']))
        em = nb.node('ShaderNodeEmission')
        nb.put(em.inputs['Color'], c * scale)
        nb.put(em.inputs['Strength'], 1.0)
        shader = em.outputs[0]
        if additive or alpha is not None:
            tr = nb.node('ShaderNodeBsdfTransparent')
            if additive:
                ad = nb.node('ShaderNodeAddShader')
                nb.t.links.new(em.outputs[0], ad.inputs[0])
                nb.t.links.new(tr.outputs[0], ad.inputs[1])
                shader = ad.outputs[0]
            else:
                mx = nb.node('ShaderNodeMixShader')
                nb.put(mx.inputs[0], alpha)
                nb.t.links.new(tr.outputs[0], mx.inputs[1])
                nb.t.links.new(em.outputs[0], mx.inputs[2])
                shader = mx.outputs[0]
            method = method or 'BLENDED'
        m = self._finish(shader, side, method, None)
        if method == 'BLENDED':
            m.use_transparency_overlap = bool(additive) if depth_write is None else not depth_write
        return m


# --------------------------------------------------------------------------------------- textures that change ---

class ImageVariants:
    """A texture the WebGPU edition redrew while it ran (a new post, a recount, a new chyron) becomes a list of
    packed images; every material that reads it samples them all and keeps the one the set root's `prop` names (a
    keyed property, CONSTANT keys). Each image key gets a node group (Vector -> Color, Alpha), rebuilt as variants are
    added, so a material made earlier picks up a later variant."""

    def __init__(self, lib, prefix, prop):
        self.lib, self.prefix, self.prop = lib, prefix, prop
        self.items = []
        self.groups = {}

    def add(self, images: dict, sig=None):
        for i, it in enumerate(self.items):
            if sig is not None and it.get('_sig') == sig:
                return i
        it = dict(images)
        it['_sig'] = sig
        self.items.append(it)
        self._rebuild()
        return len(self.items) - 1

    def _group(self, key):
        import bpy
        g = self.groups.get(key)
        if g is None:
            g = bpy.data.node_groups.new(f'{self.prefix}_{key}', 'ShaderNodeTree')
            g.interface.new_socket('Vector', in_out='INPUT', socket_type='NodeSocketVector')
            g.interface.new_socket('Color', in_out='OUTPUT', socket_type='NodeSocketColor')
            g.interface.new_socket('Alpha', in_out='OUTPUT', socket_type='NodeSocketFloat')
            self.lib.own(g)
            self.groups[key] = g
        return g

    def _rebuild(self):
        keys = [k for k in self.items[0] if not k.startswith('_')]
        for key in keys:
            g = self._group(key)
            for n in list(g.nodes):
                g.nodes.remove(n)
            nb = NB(g, self.lib)
            gi = nb.node('NodeGroupInput')
            go = nb.node('NodeGroupOutput')
            uvx = X(nb, gi.outputs['Vector'], 'v')
            idx = nb.U(self.prop)
            col = alpha = None
            for i, it in enumerate(self.items):
                c, a = nb.tex(it[key], uvx)
                if col is None:
                    col, alpha = c, a
                else:
                    on = nb.step(i - 0.5, idx)
                    col, alpha = nb.mix(col, c, on), nb.mix(alpha, a, on)
            nb.put(go.inputs['Color'], col)
            nb.put(go.inputs['Alpha'], alpha)

    def sample(self, nb, key, uv):
        g = self._group(key)
        n = nb.node('ShaderNodeGroup')
        n.node_tree = g
        nb.put(n.inputs['Vector'], uv)
        return X(nb, n.outputs['Color'], 'v'), X(nb, n.outputs['Alpha'], 'f')


# ------------------------------------------------------------------------------------------ geometry nodes ---

class GN:
    """A Geometry Nodes modifier written with NB (the vertex-stage TSL of the instanced crowd, signs, steam and hand
    lights: positionNode math, CPU-placed billboards). Positions here are Blender's axes."""

    def __init__(self, lib, ob, name):
        import bpy
        t = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        t.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        t.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        lib.own(t)
        self.tree = t
        self.nb = NB(t, lib, geo=True)
        self.gin = self.nb.node('NodeGroupInput')
        self.gout = self.nb.node('NodeGroupOutput')
        self.geom = self.gin.outputs[0]
        mod = ob.modifiers.new(name, 'NODES')
        mod.node_group = t
        self.mod = mod

    def attr(self, name, kind='f'):
        nb = self.nb
        n = nb.node('GeometryNodeInputNamedAttribute', data_type='FLOAT' if kind == 'f' else 'FLOAT_VECTOR')
        n.inputs['Name'].default_value = name
        return X(nb, n.outputs['Attribute'], kind)

    def position(self):
        n = self.nb._once('pos', 'GeometryNodeInputPosition')
        return X(self.nb, n.outputs[0], 'v')

    def set_position(self, pos):
        n = self.nb.node('GeometryNodeSetPosition')
        self.tree.links.new(self.geom, n.inputs['Geometry'])
        self.nb.put(n.inputs['Position'], pos)
        self.geom = n.outputs['Geometry']
        return self

    def store(self, name, value, kind='f', domain='POINT'):
        n = self.nb.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT' if kind == 'f' else 'FLOAT_VECTOR',
                         domain=domain)
        self.tree.links.new(self.geom, n.inputs['Geometry'])
        n.inputs['Name'].default_value = name
        self.nb.put(n.inputs['Value'], value)
        self.geom = n.outputs['Geometry']
        return self

    def rotate(self, v, center, angle, axis='X'):
        """Vector Rotate about an axis through `center` (right-handed, angle in radians)."""
        n = self.nb.node('ShaderNodeVectorRotate', rotation_type=f'{axis}_AXIS')
        self.nb.put(n.inputs['Vector'], v)
        self.nb.put(n.inputs['Center'], center)
        self.nb.put(n.inputs['Angle'], angle)
        return X(self.nb, n.outputs['Vector'], 'v')

    def camera_rotation(self):
        """The active camera's rotation in this object's frame (three's camera quaternion premultiplied by the set
        group's inverse): Object Info, Relative."""
        nb = self.nb
        ac = nb._once('acam', 'GeometryNodeInputActiveCamera')
        oi = nb._once('acam_info', 'GeometryNodeObjectInfo', transform_space='RELATIVE')
        self.tree.links.new(ac.outputs[0], oi.inputs['Object'])
        r = oi.outputs['Rotation']
        if r.type != 'ROTATION':
            e2r = nb.node('FunctionNodeEulerToRotation')
            self.tree.links.new(r, e2r.inputs[0])
            r = e2r.outputs[0]
        return r

    def billboards(self, quad_ob, scale, spin=None):
        """Instance quad_ob's mesh on every point, facing the active camera (its rotation, then spun about the view
        axis by `spin`), scaled; realized so the points' attributes reach the material."""
        nb, t = self.nb, self.tree
        oi = nb.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
        oi.inputs['Object'].default_value = quad_ob
        rot = self.camera_rotation()
        if spin is not None:
            aa = nb.node('FunctionNodeAxisAngleToRotation')
            nb.put(aa.inputs['Axis'], (0.0, 0.0, 1.0))
            nb.put(aa.inputs['Angle'], spin)
            rr = nb.node('FunctionNodeRotateRotation', rotation_space='LOCAL')
            t.links.new(rot, rr.inputs['Rotation'])
            t.links.new(aa.outputs[0], rr.inputs['Rotate By'])
            rot = rr.outputs[0]
        ip = nb.node('GeometryNodeInstanceOnPoints')
        t.links.new(self.geom, ip.inputs['Points'])
        t.links.new(oi.outputs['Geometry'], ip.inputs['Instance'])
        t.links.new(rot, ip.inputs['Rotation'])
        nb.put(ip.inputs['Scale'], scale)
        rz = nb.node('GeometryNodeRealizeInstances')
        t.links.new(ip.outputs[0], rz.inputs['Geometry'])
        self.geom = rz.outputs[0]
        return self

    def set_material(self, mat):
        n = self.nb.node('GeometryNodeSetMaterial')
        self.tree.links.new(self.geom, n.inputs['Geometry'])
        n.inputs['Material'].default_value = mat
        self.geom = n.outputs['Geometry']
        return self

    def done(self):
        self.tree.links.new(self.geom, self.gout.inputs[0])
        return self.mod


def points_object(lib, name, positions_b, attrs=None, parent=None, collection=None):
    """A mesh of loose vertices (Blender axes) carrying point attributes {name: (N,) or (N, 3)}: the per-instance data
    a GN modifier reads."""
    import bpy
    P = np.asarray(positions_b, np.float32).reshape(-1, 3)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(P))
    me.vertices.foreach_set('co', P.ravel())
    for k, v in (attrs or {}).items():
        v = np.asarray(v, np.float32)
        if v.ndim == 1:
            a = me.attributes.new(k, 'FLOAT', 'POINT')
            a.data.foreach_set('value', v)
        else:
            a = me.attributes.new(k, 'FLOAT_VECTOR', 'POINT')
            a.data.foreach_set('vector', v[:, :3].ravel())
    me.update()
    lib.own(me)
    ob = bpy.data.objects.new(name, me)
    (collection or lib.collection).objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return lib.own(ob)


def quad_object(lib, name, collection=None):
    """A unit quad in its local XY plane facing +Z with a UVMap (three's PlaneGeometry(1, 1)), hidden: the billboard
    instances' source."""
    import bpy
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name='UVMap')
    uvl.data.foreach_set('uv', [0, 0, 1, 0, 1, 1, 0, 1])
    lib.own(me)
    ob = bpy.data.objects.new(name, me)
    (collection or lib.collection).objects.link(ob)
    ob.hide_render = True
    ob.hide_viewport = True
    return lib.own(ob)


# ------------------------------------------------------------------------------------------------- keys ---

class Keyer:
    """Keys what a set's update() sets: through the harness's ctx.key (its runner makes them LINEAR or CONSTANT), or,
    with a frame and no ctx, keyframe_insert at that frame, given its interpolation by finish()."""

    def __init__(self):
        from ...harness.keying import KeyLog
        self.log = KeyLog()

    def __call__(self, target, path, index=-1, frame=None, ctx=None, interpolation='LINEAR'):
        if ctx is not None:
            return ctx.key(target, path, index=index, frame=frame, interpolation=interpolation)
        if frame is None:
            return False
        ok = target.keyframe_insert(path, index=index, frame=frame)
        if ok:
            self.log.add(target, path, index, frame, interpolation)
        return ok

    def finish(self):
        """LINEAR / CONSTANT on every key made without ctx (Python's keyframe_insert makes BEZIER)."""
        from ...harness.keying import make_linear
        n = make_linear(self.log)
        return n


# ------------------------------------------------------------------------------------------- the lib proper ---

class Lib:
    """make_lib(): what a set builds with, owning every datablock it makes (dispose_all removes them).

    owner: the set's root object, whose custom properties are the set's uniforms (NB.U reads them through drivers)."""

    def __init__(self, name='uf', owner=None, collection=None):
        self.name = name
        self.owner = owner
        self.collection = collection
        self.owned = []
        self._tex = {}
        self.fam = fam
        self.create_canvas = create_canvas
        self.rng, self.clamp01, self.smooth, self.exists = rng, clamp01, smooth, exists
        self.build_mips, self.canvas_pixels, self.height_field, self.box_blur = build_mips, canvas_pixels, height_field, box_blur
        self.prep, self.box_uv, self.m4 = prep, box_uv, m4
        self.hash21, self.lum, self.hex = hash21_np, lum, hex_linear
        self.register_font, self.fit_text = register_font, fit_text

    # ownership
    def own(self, x):
        self.owned.append(x)
        return x

    # images
    def tex(self, path, srgb=True):
        """An image file (cached per path and colour space); data images are Non-Color."""
        import bpy
        k = (os.path.abspath(str(path)), bool(srgb))
        im = self._tex.get(k)
        if im is None or im.name not in bpy.data.images:
            im = bpy.data.images.load(k[0], check_existing=False)
            im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
            if not srgb:
                im.alpha_mode = 'CHANNEL_PACKED'
            self._tex[k] = self.own(im)
        return im

    def pbr(self, id, res='1k', ao=False, met=False, disp=False):
        """A CC0 texture set from the shared library (fetched once): {'id', 'col', 'nrm', 'rgh'} + ao / met / disp when
        asked (an unasked map is not loaded)."""
        from ...harness import assets
        s = assets.fetch_pbr(id, res)
        F = s['files']
        out = {'id': id, 'col': self.tex(F['diff'], True), 'nrm': self.tex(F['normal'], False),
               'rgh': self.tex(F['rough'], False)}
        if ao and F.get('ao') and os.path.isfile(F['ao']):
            out['ao'] = self.tex(F['ao'], False)
        if met and F.get('metal') and os.path.isfile(F['metal']):
            out['met'] = self.tex(F['metal'], False)
        if disp and F.get('displacement') and os.path.isfile(F['displacement']):
            out['disp'] = self.tex(F['displacement'], False)
        return out

    def data_tex(self, rgba_top_down, W=None, H=None, srgb=True, mips=True, wrap=CLAMP, tx=None, name=None):
        """RGBA8 rows in canvas order -> a packed image (tx: an image made before, its pixels replaced)."""
        a = np.asarray(rgba_top_down, np.uint8)
        if a.ndim == 1:
            a = a.reshape(H, W, 4)
        interp = 'Linear' if mips else 'Cubic'
        if tx is not None:
            px = (a[::-1].astype(np.float32) / 255.0)
            tx.scale(a.shape[1], a.shape[0])
            tx.pixels.foreach_set(px.ravel())
            tx.pack()
            tx['uf_interp'], tx['uf_ext'] = interp, _wrap_ext(wrap)
            return tx
        img = image_from_rgba(name or f'{self.name}_tex', a, srgb=srgb, interpolation=interp, extension=_wrap_ext(wrap))
        return self.own(img)

    def canvas_tex(self, cv, srgb=True, mips=True, wrap=CLAMP, tx=None, name=None):
        return self.data_tex(cv.pixels(), srgb=srgb, mips=mips, wrap=wrap, tx=tx, name=name)

    def dyn_canvas(self, W, H, draw, srgb=True, mips=True, wrap=CLAMP, name=None):
        """A canvas whose image is rebuilt only when redraw(*args) is called (a build-time change; a change over
        time, keyed, is an ImageVariants)."""
        lib = self
        cv = create_canvas(W, H)

        class _Dyn:
            def __init__(self):
                self.canvas, self.ctx, self.W, self.H, self.texture = cv, cv.get_context('2d'), W, H, None

            def redraw(self, *args):
                self.canvas.data[...] = 0.0
                draw(self.ctx, W, H, *args)
                self.texture = lib.canvas_tex(cv, srgb=srgb, mips=mips, wrap=wrap, tx=self.texture, name=name)
                return self.texture
        return _Dyn()

    def normal_tex(self, hf, strength=4.0, wrap=CLAMP, name=None, mips=True):
        return self.data_tex(normal_pixels(hf, strength), srgb=False, mips=mips, wrap=wrap, name=name or f'{self.name}_nrm')

    def pack_tex(self, chans, W, H, wrap=CLAMP, name=None, mips=True):
        return self.data_tex(pack_pixels(chans, W, H), srgb=False, mips=mips, wrap=wrap, name=name or f'{self.name}_mask')

    # geometry
    def bucket(self, name):
        return Bucket(self, name)

    def empty(self, name, parent=None, M3=None, collection=None):
        """A Group: an Empty with three's local matrix (converted)."""
        import bpy
        from mathutils import Matrix
        e = bpy.data.objects.new(name, None)
        e.empty_display_size = 0.25
        (collection or self.collection).objects.link(e)
        if parent is not None:
            e.parent = parent
        if M3 is not None:
            e.matrix_basis = Matrix(to_blender_matrix(M3).tolist())
        return self.own(e)

    def mesh_object(self, name, g, material=None, parent=None, M3=None, shadow=True, collection=None, flags=None,
                    weld=True):
        """A mesh object from a three-space Geo (converted), its three-space local matrix M3 converted too."""
        import bpy
        from mathutils import Matrix
        me = mesh_from_geo(name, g, weld=weld)
        if material is not None:
            me.materials.append(material)
        self.own(me)
        ob = bpy.data.objects.new(name, me)
        (collection or self.collection).objects.link(ob)
        if parent is not None:
            ob.parent = parent
        if M3 is not None:
            ob.matrix_basis = Matrix(to_blender_matrix(M3).tolist())
        ob.visible_shadow = bool(shadow)
        set_flags(ob, flags)
        return self.own(ob)

    # environment
    def env_tex(self, fn, W=256, H=128, name=None):
        """The procedural HDR environment: fn(three-space direction) -> (r, g, b), as a float equirect image in
        Blender's world convention (an Environment Texture reads it with its default direction)."""
        u = (np.arange(W) + 0.5) / W
        v = (np.arange(H) + 0.5) / H
        lat = (v - 0.5) * math.pi
        phi = (0.5 - u) * 2 * math.pi
        out = np.zeros((H, W, 4), np.float32)
        out[..., 3] = 1.0
        for j in range(H):
            cl, sl = math.cos(lat[j]), math.sin(lat[j])
            for i in range(W):
                bx, by, bz = math.cos(phi[i]) * cl, math.sin(phi[i]) * cl, sl
                out[j, i, :3] = fn((bx, bz, -by))
        img = image_from_rgba(name or f'{self.name}_env', out, srgb=False, top_down=False, alpha_mode='STRAIGHT')
        img.colorspace_settings.name = 'Linear Rec.709' if 'Linear Rec.709' in _colorspaces() else 'Non-Color'
        return self.own(img)

    # materials
    def mat(self, name):
        return Mat(self, name)

    def pbr_mat(self, S, name=None, tile=1.0, uv=None, offset=(0.0, 0.0), P=None, tint=None, recolor=None, macro=None,
                macro_scale=0.35, rough=None, metal=0.0, nrm=1.0, post=None, physical=False,
                sheen=None, sheen_roughness=None, sheen_color=None, clearcoat=None, clearcoat_roughness=None,
                side='double', transparent=False, opacity=None, alpha_test=None, fog=None,
                method=None, depth_write=None):
        """The JS pbrMat: a textured material from a set S. tile (metres per tile, number | (u, v)); uv: an X (default
        the mesh uv); tint (hex | rgb); recolor(col, nb) -> col; macro: 0..1 large albedo variation (fBm of P at
        macro_scale); rough: (mul, add); metal: number | 'map'; nrm: the normal strength;
        post(dict(col, rough, metal, uvN, P, nb)) -> dict(col?, rough?, metal?, emissive?, normal?, opacity?).
        The set's environment (three's envMap) lights it through the World, and EEVEE's AO and probes occlude it
        (three's aoNode, the set's AO map, has no part here). side: 'double' (the default here; three's was
        FrontSide: a closed mesh looks the same, an open one keeps its inside) or 'front'. depth_write: three's
        depthWrite on a blended material (False: every layer of the object blends, EEVEE's Transparency Overlap)."""
        M = Mat(self, name or S['id'])
        nb = M.nb
        tu, tv = tile if isinstance(tile, (tuple, list)) else (tile, tile)
        base = uv if uv is not None else nb.uv()
        uvN = nb.vec2(base.x * (1.0 / tu) + offset[0], base.y * (1.0 / tv) + offset[1])
        Pn = P if P is not None else nb.P()
        col, _a = nb.tex(S['col'], uvN)
        if recolor is not None:
            col = nb.w(recolor(col, nb))
        if tint is not None:
            col = col * (hex_linear(tint) if not isinstance(tint, (tuple, list)) else tuple(tint))
        if macro:
            mac = nb.mx_fbm(Pn * macro_scale, 3, 2.0, 0.5)
            col = col * (mac * macro + 1.0)
        rgh, _ = nb.tex(S['rgh'], uvN)
        r_ = rgh.x
        if rough is not None:
            r_ = r_ * rough[0] + rough[1]
        if metal == 'map' and S.get('met') is not None:
            mt, _ = nb.tex(S['met'], uvN)
            met_ = mt.x
        else:
            met_ = nb.w(float(metal) if _is_num(metal) else 0.0)
        emissive = normal = op = None
        if post is not None:
            r = post({'col': col, 'rough': r_, 'metal': met_, 'uvN': uvN, 'P': Pn, 'nb': nb})
            col = r.get('col', col)
            r_ = r.get('rough', r_)
            met_ = r.get('metal', met_)
            emissive = r.get('emissive')
            normal = r.get('normal')
            op = r.get('opacity')
        if normal is None:
            nt, _ = nb.tex(S['nrm'], uvN)
            normal = nb.normal_map(nt, nrm)
        alpha = op if op is not None else opacity
        if alpha_test is not None and alpha is not None:
            alpha = nb.step(alpha_test, alpha)
        m = M.standard(col, rough=nb.clamp(r_, 0.03, 1.0), metal=met_, normal=normal, emissive=emissive, alpha=alpha,
                       sheen=sheen if physical else None, sheen_rough=sheen_roughness if sheen_roughness is not None else 0.3,
                       sheen_color=hex_linear(sheen_color) if sheen_color is not None else (1.0, 1.0, 1.0),
                       coat=clearcoat if physical else None,
                       coat_rough=clearcoat_roughness if clearcoat_roughness is not None else 0.03,
                       side=side, method=method or ('BLENDED' if transparent and alpha_test is None else None), fog=fog)
        if depth_write is not None and m.surface_render_method == 'BLENDED':
            m.use_transparency_overlap = not depth_write
        return m

    def dispose_all(self):
        """Remove every datablock this lib made."""
        import bpy
        colls = {
            'Object': bpy.data.objects, 'Mesh': bpy.data.meshes, 'Material': bpy.data.materials,
            'Image': bpy.data.images, 'Light': bpy.data.lights, 'Camera': bpy.data.cameras,
            'World': bpy.data.worlds, 'Collection': bpy.data.collections,
            'GeometryNodeTree': bpy.data.node_groups, 'ShaderNodeTree': bpy.data.node_groups,
            'LightProbe': bpy.data.lightprobes, 'LightProbeVolume': bpy.data.lightprobes,
            'LightProbePlane': bpy.data.lightprobes, 'LightProbeSphere': bpy.data.lightprobes,
        }
        for x in reversed(self.owned):
            try:
                kind = type(x).__name__
                c = colls.get(kind)
                if c is not None and x.name in c and c[x.name] == x:
                    c.remove(x, do_unlink=True) if kind in ('Object', 'Collection') else c.remove(x)
            except (ReferenceError, RuntimeError):
                pass
        self.owned.clear()
        self._tex.clear()


def set_flags(ob, flags):
    """The JS userData audit flags (noSupportCheck, allowIntersect, assembly ...) under the harness's names."""
    from ...harness.ledger import canonical_flag, OBJECT_FLAG_ALIASES
    for k, v in (flags or {}).items():
        ob[canonical_flag(k, OBJECT_FLAG_ALIASES)] = v
    return ob


def _colorspaces():
    import bpy
    try:
        return {e.identifier for e in bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties['name'].enum_items}
    except (KeyError, AttributeError):
        return set()


def make_lib(name='uf', owner=None, collection=None) -> Lib:
    """cn_lib's makeLib: the set builds with what it returns."""
    return Lib(name, owner, collection)


# ------------------------------------------------------------------------------------- lights, cameras, world ---

def spot(lib, name, color, cd, pos3, tgt3, angle, penumbra, parent=None, shadow=True, radius=0.02, cutoff=1000.0):
    """three's SpotLight(color, intensity cd, distance 0, angle, penumbra, decay 2) at pos3 aimed at tgt3 (three
    space): W = 4 pi cd (cd_watts), spot_size = 2 x angle, blend = penumbra, a custom cutoff (three's distance 0 is
    endless; Blender's light threshold would cull a weak far light)."""
    import bpy
    from mathutils import Vector
    from ...look import lighting as LL
    ld = bpy.data.lights.new(name, 'SPOT')
    ld.energy = cd_watts(cd)
    ld.color = hex_linear(color) if not isinstance(color, (tuple, list)) else tuple(color)
    ld.spot_size, ld.spot_blend = LL.three_spot(angle, penumbra)
    ld.spot_size = min(ld.spot_size, math.pi)
    ld.use_custom_distance = True
    ld.cutoff_distance = cutoff
    ld.use_shadow = bool(shadow)
    ld.shadow_soft_size = radius
    lib.own(ld)
    ob = bpy.data.objects.new(name, ld)
    lib.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    p, t = Vector(b3(pos3)), Vector(b3(tgt3))
    ob.location = p
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = (t - p).to_track_quat('-Z', 'Y')
    ob['base'] = float(ld.energy)
    ob['three_cd'] = float(cd)
    return lib.own(ob)


def point(lib, name, color, cd, pos3, parent=None, shadow=True, radius=0.05, cutoff=1000.0):
    """three's PointLight(color, intensity cd, distance 0, decay 2): W = 4 pi cd (cd_watts)."""
    import bpy
    from mathutils import Vector
    ld = bpy.data.lights.new(name, 'POINT')
    ld.energy = cd_watts(cd)
    ld.color = hex_linear(color) if not isinstance(color, (tuple, list)) else tuple(color)
    ld.use_custom_distance = True
    ld.cutoff_distance = cutoff
    ld.use_shadow = bool(shadow)
    ld.shadow_soft_size = radius
    lib.own(ld)
    ob = bpy.data.objects.new(name, ld)
    lib.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    ob.location = Vector(b3(pos3))
    ob['base'] = float(ld.energy)
    ob['three_cd'] = float(cd)
    return lib.own(ob)


def make_world(lib, name, env_img=None, env_i=1.0, hemi=None, scene=None):
    """The set's world: its environment (three's envMap, at envMapIntensity env_i) plus three's HemisphereLight
    (sky / ground colours x intensity / pi as radiance gives three's irradiance exactly), all x SPEC. EEVEE lights
    every material in the scene with it: a room through its volume probe, the reflections through the probes."""
    import bpy
    w = bpy.data.worlds.new(name)
    lib.own(w)
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    nb = NB(nt, lib)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    out.location = (400, 0)
    col = nb.w((0.0, 0.0, 0.0))
    if env_img is not None:
        n = nb.node('ShaderNodeTexEnvironment', image=env_img, interpolation='Linear', projection='EQUIRECTANGULAR')
        col = col + X(nb, n.outputs['Color'], 'v') * float(env_i)
    if hemi is not None:
        sky_c, ground_c, inten = hemi
        tc = nb.node('ShaderNodeTexCoord')
        dz = nb.comp(X(nb, tc.outputs['Generated'], 'v'), 2)
        up = nb.step(0.0, dz)
        col = col + nb.mix(hex_linear(ground_c), hex_linear(sky_c), up) * (float(inten) / math.pi)
    bg = nb.node('ShaderNodeBackground')
    nb.put(bg.inputs['Color'], col * SPEC)
    nb.put(bg.inputs['Strength'], 1.0)
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    if scene is not None:
        scene.world = w
    return w


def fog_group(lib, fog, name):
    """A set's fog, three's FogExp2(color, density), as a shader node group with the outputs the city kit's haze has
    (factor: 1 - exp(-(density z)^2) of the view depth z; color: the fog's colour), the same numbers the set's own
    materials mix in (Mat(fog=)). SetBase.fog_objects wraps your own objects' materials in it."""
    import bpy
    tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    lib.own(tree)
    tree.interface.new_socket('factor', in_out='OUTPUT', socket_type='NodeSocketFloat')
    tree.interface.new_socket('color', in_out='OUTPUT', socket_type='NodeSocketVector')
    nb = NB(tree, lib)
    out = nb.node('NodeGroupOutput')
    out.hide = False
    nb.put(out.inputs['factor'], nb.fog_factor(fog['density']))
    c = nb.node('ShaderNodeCombineXYZ')                       # the fog's colour, linear
    for s, v in zip(c.inputs, hex_linear(fog['color'], SPEC)):
        s.default_value = v
    tree.links.new(c.outputs[0], out.inputs['color'])
    return tree


def make_camera(lib, name, cam, parent=None, clip=(0.05, 2000.0)):
    """A Blender camera from a set's {pos, target, fov} (three space, set-local; fov vertical degrees)."""
    import bpy
    from mathutils import Vector
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = 'VERTICAL'
    cd.angle_y = math.radians(float(cam['fov']))
    cd.clip_start, cd.clip_end = clip
    lib.own(cd)
    ob = bpy.data.objects.new(name, cd)
    lib.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    p, t = Vector(b3(cam['pos'])), Vector(b3(cam['target']))
    ob.location = p
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = (t - p).to_track_quat('-Z', 'Y')
    return lib.own(ob)


def pix_of(scene, camera=None) -> float:
    """2 tan(fov_y / 2) / height: one pixel's size per metre of view depth (the 'pix' uniform behind fwidth_est)."""
    cam = camera or scene.camera
    if cam is None:
        return 2 * math.tan(math.radians(40.0) / 2) / max(1, scene.render.resolution_y)
    cd = cam.data
    r = scene.render
    W = r.resolution_x * r.resolution_percentage / 100.0
    H = r.resolution_y * r.resolution_percentage / 100.0
    if cd.sensor_fit == 'VERTICAL' or (cd.sensor_fit == 'AUTO' and H > W):
        return 2 * math.tan(cd.angle_y / 2) / max(1.0, H)
    return 2 * math.tan(cd.angle_x / 2) / max(1.0, W)


def normalized_bone_matrix(arm, bone_name):
    """three-vrm's normalized bone, in Blender: the bone's posed world position with the rotation it has made away
    from its rest (identity in the rest pose) and the character's own scale (a normalized bone's matrixWorld carries
    the VRM scene's scale: a claudesona at 0.87 wears the cap at 0.87, its fit offset scaled with her), as a
    4 x 4 mathutils Matrix."""
    from mathutils import Matrix
    pb = arm.pose.bones[bone_name]
    pose_w = arm.matrix_world @ pb.matrix
    rest_w = arm.matrix_world @ pb.bone.matrix_local
    R = pose_w.to_3x3() @ rest_w.to_3x3().inverted()
    M = (R @ Matrix.Diagonal(arm.matrix_world.to_scale())).to_4x4()
    M.translation = pose_w.translation
    return M


# ------------------------------------------------------------------------------------------ the set's shape ---

class SetBase:
    """What corridor.build / news.build return, the sets' contract in Blender terms (eidoblend.sets.unknown_force):
    group (the root Empty, set-local metres, Z up), parts, update(t, state, ctx=None, frame=None), animate(state_fn),
    dispose(), cams (set-local {pos, target, fov}, Blender axes; cams_three: the WebGPU's numbers), camera(name),
    focal (set-local, Blender axes; focal_three), look, uniforms (the root's custom properties the materials read),
    materials."""

    def __init__(self, lib, group, collection):
        self.lib, self.group, self.collection = lib, group, collection
        self.keyer = Keyer()
        self.parts, self.cams, self.cams_three, self.materials = {}, {}, {}, {}
        self.focal = self.focal_three = None
        self.look = {}
        self.fog = None                  # the FogExp2 the set's materials carry ({'color', 'density'}), when they do
        self._fog_group = None

    def set_cams(self, cams_three, focal_three):
        """The cameras and the focal point from the WebGPU's numbers (three axes): cams / focal in Blender's axes,
        cams_three / focal_three as given."""
        self.cams_three = {k: dict(v) for k, v in cams_three.items()}
        self.cams = {k: dict(v, pos=list(b3(v['pos'])), target=list(b3(v['target']))) for k, v in cams_three.items()}
        self.focal_three = tuple(float(c) for c in focal_three)
        self.focal = b3(self.focal_three)
        self.focal_blender = self.focal

    # uniforms
    def set_u(self, name, value, ctx=None, frame=None, interpolation='LINEAR'):
        self.group[name] = float(value)
        self.keyer(self.group, f'["{name}"]', frame=frame, ctx=ctx, interpolation=interpolation)
        if ctx is None and frame is None:
            # a live (unkeyed) update: a custom property set from Python tags nothing, so the drivers that read it
            # (every material uniform, the Geometry Nodes' t) would keep their old value until something else did
            self.group.update_tag()

    @property
    def uniforms(self):
        return {k: self.group[k] for k in self.group.keys() if not k.startswith('_') and _is_num(self.group[k])}

    def key_light(self, ob, energy, ctx=None, frame=None):
        ob.data.energy = float(energy)
        self.keyer(ob.data, 'energy', frame=frame, ctx=ctx)

    def key_transform(self, ob, ctx=None, frame=None):
        for p in ('location', 'rotation_quaternion' if ob.rotation_mode == 'QUATERNION' else 'rotation_euler', 'scale'):
            self.keyer(ob, p, frame=frame, ctx=ctx)

    def camera(self, name, scene=None, set_active=True):
        """The Blender camera of cams[name] (made once), parented to the set's root."""
        ob = self.parts.setdefault('_cameras', {}).get(name)
        if ob is None:
            ob = make_camera(self.lib, f'{self.group.name}_cam_{name}', self.cams_three[name], parent=self.group)
            self.parts['_cameras'][name] = ob
        if scene is not None and set_active:
            scene.camera = ob
        return ob

    def focal_world(self):
        """The focal point (the aeropittura's sun cones come from here) in world space, Blender axes."""
        from mathutils import Vector
        return self.group.matrix_world @ Vector(self.focal)

    def apply_post(self, scene, camera=None, aeropittura=True, bloom=True, force=1.0, layer='under', frame=None,
                   frames=None):
        """The look the set suggests, on the post chain (look/post): three's bloom at look['bloom'] (its threshold in
        the sets' light units, x SPEC) and the aeropittura pass at LOOKS[look['name']] ('argue'), its focal projected
        from focal_world() through the camera (left where it was when the point is behind it). frames=(first, last):
        the focal keyed on every frame through the scene's camera there (cuts by markers, the cameras' moves).
        Returns the aeropittura's FX handle (None without it). The look is a suggestion: a piece of your own may
        grade it any way; the probes use it to look at a frame with the look off and on, as the WebGPU doc asks."""
        from ...look.post import chain
        b = self.look.get('bloom') if bloom else None
        if b:
            chain.set_bloom(scene, strength=float(b['strength']), size=float(b['radius']),
                            threshold=float(b['threshold']) * SPEC)
        if not aeropittura:
            return None
        from ...look.post import aeropittura as AP, custom_effects as fx
        e = fx.apply_to(scene, 'aeropittura', {'aeropittura': {'layer': layer}})
        U = e.uniforms['aeropittura']
        AP.apply_look(U, AP.LOOKS[self.look.get('name', 'argue')], force, frame=frame)
        if frames:
            for f_ in range(int(frames[0]), int(frames[1]) + 1):
                scene.frame_set(f_)
                f = AP.project_focal(scene, self.focal_world(), scene.camera)
                if f is not None:
                    AP.set_focal(U, f[0], f[1], frame=f_)
            return e
        f = AP.project_focal(scene, self.focal_world(), camera or scene.camera)
        if f is not None:
            AP.set_focal(U, f[0], f[1], frame=frame)
        return e

    def animate(self, state=None, frames=None, scene=None, ctx=None, t0=None):
        """The set's moving parts on your own clock: key update(t, state(t)) on every frame of `frames` (default: the
        scene's range), then give the keys their interpolation. state: a function of t (or one dict for every
        frame). t: seconds from the scene's first frame, or t0 + (f - frames[0]) / fps when t0 is given."""
        import bpy
        sc = scene or bpy.context.scene
        f0, f1 = frames or (sc.frame_start, sc.frame_end)
        fps = sc.render.fps / sc.render.fps_base
        for f in range(int(f0), int(f1) + 1):
            t = (f - sc.frame_start) / fps if t0 is None else t0 + (f - f0) / fps
            st = state(t) if callable(state) else dict(state or {})
            sc.frame_set(f)
            self.update(t, st, ctx=ctx, frame=f)
        if ctx is None:
            self.keyer.finish()

    def update(self, t, state=None, ctx=None, frame=None):
        raise NotImplementedError

    def bake_probes(self, scene=None):
        """Bake the set's volume probe (parts['probe'], when it has one: a GPU job, run it through heavy.sh) at the
        set's current state. Returns {probe: seconds}."""
        import bpy
        from ...look import lighting as LL
        pr = self.parts.get('probe')
        if pr is None:
            return {}
        return LL.bake_light_probes(scene or bpy.context.scene, probes=[pr])

    def fog_group(self):
        """The set's fog as a shader node group (outputs factor, color: cn_lib.fog_group), made once; None when the
        set's materials carry no fog."""
        if self.fog and self._fog_group is None:
            self._fog_group = fog_group(self.lib, self.fog, f'{self.group.name}:fog')
        return self._fog_group

    def fog_objects(self, objects):
        """Your own objects in the set (a performer, a crowd, props) take the set's haze, as three's scene.fog fogged
        every material in the scene: each of their materials is wrapped once in the set's FogExp2 (fog_group), the
        wrap the city kit gives its own (citykit.fog_material), so a see-through material (a hair card, a decal, a
        blended veil) keeps its alpha and fogs only what it covers. Call it after loading them; citykit's
        unfog_material(mat) takes one out, and dispose() takes them all out. Returns (wrapped, left); a set built
        without fog wraps nothing."""
        g = self.fog_group()
        if g is None:
            return 0, 0
        from . import citykit as KIT
        return KIT.fog_objects(None, objects, group=g)

    def dispose(self):
        if self._fog_group is not None:
            from . import citykit as KIT
            KIT.unfog_group(self._fog_group)          # your objects' materials, before their haze group goes
            self._fog_group = None
        self.lib.dispose_all()

    # the sets' contract reads build()'s result as a dict too (eidoblend.sets.unknown_force: group, parts, update,
    # dispose, cams ...): S['parts'] is S.parts
    _KEYS = ('group', 'parts', 'update', 'dispose', 'cams', 'cams_three', 'focal', 'focal_three', 'look', 'uniforms',
             'materials', 'camera', 'animate', 'apply_look', 'apply_post', 'focal_world', 'bake_probes', 'fog_objects')

    def keys(self):
        return [k for k in self._KEYS if hasattr(self, k)]

    def __getitem__(self, k):
        if k not in self._KEYS or not hasattr(self, k):
            raise KeyError(k)
        return getattr(self, k)

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    def __contains__(self, k):
        return k in self.keys()
