"""bin_pages.py: the paper of THE BIN (bin.py), an atlas of invented pages the whole discourse was printed on:
newspapers, forum printouts, sermons, manifestos, an open letter, a memo, a chat log, a chart, ads, notes, classifieds
and Futurist papier-colle cut papers. bin_pages.js ported line for line. Every word is invented generic text: no real
logos, names or mastheads. Deterministic (seeded, the same mulberry32 stream as the JS).

    from eidoblend.sets.unknown_force import bin_pages as P
    img = P.draw_page_atlas(cols=6, rows=4, cw=682, ch=1024)     # a PIL RGBA image, 4092 x 4096
    P.PAGE_KINDS[18]                                               # 'cut'

Cell k sits at column k % cols, row k // cols, top-left origin. Alpha is 0 outside a page's (sometimes torn) outline;
the bin's sheet material cuts it at 0.5.

The drawing runs on Canvas2D, a canvas-2D context (the subset the UNKNOWN FORCE sets draw with) on Pillow + numpy:
paths, fills, round-capped strokes, arcs, clip, save / restore, translate / rotate, globalAlpha, the 'lighter'
composite, shadowBlur glows, radial gradients and text in the kit's bundled fonts (the 'UF ...' families parole.js
registers) or the Windows faces the race asks for. It supersamples (ss) and box-filters down, so shapes come out
antialiased. The race's billboards, march atlas, radiator number and manifesto page are drawn on it as well.
Pure Python: no bpy (runs in Blender's Python and the system Python alike).
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.normpath(os.path.join(_HERE, '..', '..', '..', '..', 'eidoverse', 'assets', 'fonts'))
SYSTEM_FONT_DIR = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')


# ============================================================================================ js number helpers ====

def js_round(x: float) -> int:
    """JavaScript Math.round (halves round up, toward +infinity)."""
    return int(math.floor(x + 0.5))


def _u32(x: int) -> int:
    return x & 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def rng(seed):
    """mulberry32, exactly as bin.js / bin_pages.js: a function returning floats in [0, 1)."""
    a = [_u32(int(seed))]

    def r():
        a[0] = _u32(a[0] + 0x6D2B79F5)
        t = a[0]
        t = _imul(t ^ (t >> 15), t | 1)
        t = _u32(t ^ _u32(t + _imul(t ^ (t >> 7), t | 61)))
        return _u32(t ^ (t >> 14)) / 4294967296.0
    return r


# ==================================================================================================== fonts ====

# the families parole.js registers (registerFonts) and race.js's Rajdhani: weight and style ignored, as Skia does
# with a face registered under its own family name
UF_FONTS = {
    'uf anton': 'Anton-Regular.ttf', 'uf archivo black': 'ArchivoBlack-Regular.ttf',
    'uf alfa slab': 'AlfaSlabOne-Regular.ttf', 'uf old standard bold': 'OldStandard-Bold.ttf',
    'uf old standard': 'OldStandard-Regular.ttf', 'uf old standard italic': 'OldStandard-Italic.ttf',
    'uf space mono bold': 'SpaceMono-Bold.ttf', 'uf space mono': 'SpaceMono-Regular.ttf',
    'uf bungee': 'Bungee-Regular.ttf', 'uf sedgwick': 'SedgwickAveDisplay-Regular.ttf',
    'uf black ops': 'BlackOpsOne-Regular.ttf', 'uf caveat brush': 'CaveatBrush-Regular.ttf',
    'uf press start': 'PressStart2P-Regular.ttf', 'rajdhani': 'Rajdhani-Bold.ttf',
    'special elite': 'SpecialElite-Regular.ttf',
}
# Windows system faces (used at render time when present, never redistributed): (family, bold, italic) -> file
SYSTEM_FONTS = {
    'georgia': {(0, 0): 'georgia.ttf', (1, 0): 'georgiab.ttf', (0, 1): 'georgiai.ttf', (1, 1): 'georgiaz.ttf'},
    'times new roman': {(0, 0): 'times.ttf', (1, 0): 'timesbd.ttf', (0, 1): 'timesi.ttf', (1, 1): 'timesbi.ttf'},
    'impact': {(0, 0): 'impact.ttf'},
    'arial black': {(0, 0): 'ariblk.ttf'},
    'arial': {(0, 0): 'arial.ttf', (1, 0): 'arialbd.ttf', (0, 1): 'ariali.ttf', (1, 1): 'arialbi.ttf'},
}
GENERIC_FONTS = {   # CSS generic families -> bundled faces (Skia's own fallbacks differ by machine)
    'serif': {(0, 0): 'OldStandard-Regular.ttf', (1, 0): 'OldStandard-Bold.ttf', (0, 1): 'OldStandard-Italic.ttf',
              (1, 1): 'OldStandard-Bold.ttf'},
    'sans-serif': {(0, 0): 'Rajdhani-Bold.ttf'},
    'monospace': {(0, 0): 'SpaceMono-Regular.ttf', (1, 0): 'SpaceMono-Bold.ttf'},
}

_FONT_RE = re.compile(r'^\s*((?:[a-zA-Z0-9-]+\s+)*?)(\d+(?:\.\d+)?)px(?:/\S+)?\s+(.+)$')


@lru_cache(maxsize=512)
def parse_font(css: str):
    """A CSS font shorthand ('bold 26px Georgia, "Times New Roman", serif') -> (file path, px)."""
    m = _FONT_RE.match(css)
    if not m:
        raise ValueError(f'font {css!r}: not a CSS font shorthand with a px size')
    pre = m.group(1).lower().split()
    px = float(m.group(2))
    bold = int(any(w in ('bold', 'bolder', '700', '800', '900') for w in pre))
    italic = int(any(w in ('italic', 'oblique') for w in pre))
    fams = [f.strip().strip('"\'') for f in m.group(3).split(',')]
    for f in fams:
        key = f.lower()
        if key in UF_FONTS:
            p = os.path.join(FONT_DIR, UF_FONTS[key])
            if os.path.isfile(p):
                return p, px
        if key in SYSTEM_FONTS:
            tab = SYSTEM_FONTS[key]
            name = tab.get((bold, italic)) or tab.get((bold, 0)) or tab.get((0, italic)) or tab[(0, 0)]
            p = os.path.join(SYSTEM_FONT_DIR, name)
            if os.path.isfile(p):
                return p, px
        if key in GENERIC_FONTS:
            tab = GENERIC_FONTS[key]
            name = tab.get((bold, italic)) or tab.get((bold, 0)) or tab[(0, 0)]
            return os.path.join(FONT_DIR, name), px
    # nothing matched: the generic serif / sans of the last family's kind, as a browser would
    return os.path.join(FONT_DIR, GENERIC_FONTS['sans-serif'][(0, 0)]), px


@lru_cache(maxsize=1024)
def _pil_font(path: str, size: int):
    return ImageFont.truetype(path, max(1, int(size)))


_MEASURE_PX = 1024


def measure_text(css_font: str, text: str) -> float:
    """canvas measureText(text).width for a CSS font string (in that font's px, untransformed). Measured at 1024 px
    and scaled, so the advances are as good as unhinted (Skia measures unhinted; at 7 px a hinted advance per glyph
    adds up to whole words over a line and changes where body copy breaks)."""
    path, px = parse_font(css_font)
    return _pil_font(path, _MEASURE_PX).getlength(text) * px / _MEASURE_PX


# =================================================================================================== colour ====

_NAMED = {'white': (255, 255, 255), 'black': (0, 0, 0), 'red': (255, 0, 0), 'transparent': (0, 0, 0)}


@lru_cache(maxsize=2048)
def css_color(c) -> tuple:
    """'#rgb' / '#rrggbb' / 'rgb(r,g,b)' / 'rgba(r,g,b,a)' / a few names -> straight (r, g, b, a), sRGB 0..1."""
    if isinstance(c, tuple):
        return c
    s = str(c).strip().lower()
    if s.startswith('#'):
        h = s[1:]
        if len(h) in (3, 4):
            h = ''.join(ch * 2 for ch in h)
        v = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
        a = v[3] / 255.0 if len(v) > 3 else 1.0
        return (v[0] / 255.0, v[1] / 255.0, v[2] / 255.0, a)
    m = re.match(r'rgba?\(([^)]*)\)', s)
    if m:
        parts = [p.strip() for p in m.group(1).split(',')]
        r, g, b = (float(p) / 255.0 for p in parts[:3])
        a = float(parts[3]) if len(parts) > 3 else 1.0
        return (r, g, b, a)
    if s in _NAMED:
        r, g, b = _NAMED[s]
        return (r / 255.0, g / 255.0, b / 255.0, 0.0 if s == 'transparent' else 1.0)
    raise ValueError(f'colour {c!r}')


class _Gradient:
    """canvas createRadialGradient (concentric circles, the form the sets use)."""

    def __init__(self, x0, y0, r0, x1, y1, r1):
        self.c = (x0, y0, r0, x1, y1, r1)
        self.stops = []

    def addColorStop(self, offset, color):
        self.stops.append((float(offset), css_color(color)))
        self.stops.sort(key=lambda s: s[0])


class _TextMetrics:
    def __init__(self, width):
        self.width = width


# ================================================================================================ Canvas2D ====

class Canvas2D:
    """A canvas-2D context on a numpy buffer (premultiplied sRGB floats, row 0 at the top), supersampled ss times.

    The canvas API by its JS names (fillStyle, lineWidth, beginPath, arc, fillText, ...), so the sets' drawing code
    ports line for line. getContext('2d') returns the canvas itself. to_rgba8() / to_image() give the result at the
    canvas size (straight alpha), as getImageData would."""

    def __init__(self, width, height, ss=2):
        self.width, self.height, self.ss = int(width), int(height), int(max(1, ss))
        self.W, self.H = self.width * self.ss, self.height * self.ss
        self.buf = np.zeros((self.H, self.W, 4), np.float32)
        self.fillStyle = '#000'
        self.strokeStyle = '#000'
        self.lineWidth = 1.0
        self.lineCap = 'butt'
        self.lineJoin = 'miter'
        self.globalAlpha = 1.0
        self.globalCompositeOperation = 'source-over'
        self.shadowColor = 'rgba(0,0,0,0)'
        self.shadowBlur = 0.0
        self.font = '10px sans-serif'
        self.textAlign = 'start'
        self.textBaseline = 'alphabetic'
        self._tf = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)     # a b c d e f: x' = a x + c y + e, y' = b x + d y + f
        self._clip = None                             # coverage (H, W) float32, or None
        self._stack = []
        self._paths = []                              # [[points (buffer px)], closed]

    # ------------------------------------------------------------------------------------------- state
    _STATE = ('fillStyle', 'strokeStyle', 'lineWidth', 'lineCap', 'lineJoin', 'globalAlpha',
              'globalCompositeOperation', 'shadowColor', 'shadowBlur', 'font', 'textAlign', 'textBaseline', '_tf',
              '_clip')

    def getContext(self, kind='2d'):
        return self

    @property
    def canvas(self):
        return self

    def save(self):
        self._stack.append(tuple(getattr(self, k) for k in self._STATE))

    def restore(self):
        if self._stack:
            for k, v in zip(self._STATE, self._stack.pop()):
                setattr(self, k, v)

    def _mul(self, a2, b2, c2, d2, e2, f2):
        a, b, c, d, e, f = self._tf
        self._tf = (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2, a * e2 + c * f2 + e,
                    b * e2 + d * f2 + f)

    def translate(self, x, y):
        self._mul(1.0, 0.0, 0.0, 1.0, float(x), float(y))

    def rotate(self, ang):
        c, s = math.cos(ang), math.sin(ang)
        self._mul(c, s, -s, c, 0.0, 0.0)

    def scale(self, sx, sy):
        self._mul(float(sx), 0.0, 0.0, float(sy), 0.0, 0.0)

    def setTransform(self, a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0):
        self._tf = (float(a), float(b), float(c), float(d), float(e), float(f))

    def resetTransform(self):
        self.setTransform()

    def _pt(self, x, y):
        a, b, c, d, e, f = self._tf
        s = self.ss
        return ((a * x + c * y + e) * s, (b * x + d * y + f) * s)

    def _scale(self):
        a, b, c, d = self._tf[:4]
        return math.sqrt(abs(a * d - b * c))

    # -------------------------------------------------------------------------------------------- path
    def beginPath(self):
        self._paths = []

    def _sub(self):
        if not self._paths or self._paths[-1][1]:
            start = self._paths[-1][0][0] if self._paths and self._paths[-1][0] else None
            self._paths.append([[start] if start is not None else [], False])
        return self._paths[-1][0]

    def moveTo(self, x, y):
        self._paths.append([[self._pt(x, y)], False])

    def lineTo(self, x, y):
        if not self._paths or (self._paths[-1][1] is False and not self._paths[-1][0]):
            self.moveTo(x, y)
            return
        self._sub().append(self._pt(x, y))

    def _last_user(self):
        """The current point in user space (inverse transform of the last buffer point)."""
        p = self._paths[-1][0][-1]
        a, b, c, d, e, f = self._tf
        det = a * d - b * c
        X, Y = p[0] / self.ss - e, p[1] / self.ss - f
        return ((d * X - c * Y) / det, (-b * X + a * Y) / det)

    def _nseg(self, pts_user):
        L = 0.0
        for i in range(1, len(pts_user)):
            L += math.hypot(pts_user[i][0] - pts_user[i - 1][0], pts_user[i][1] - pts_user[i - 1][1])
        return int(min(96, max(6, L * self._scale() * self.ss / 3.0)))

    def quadraticCurveTo(self, cx, cy, x, y):
        if not self._paths or not self._paths[-1][0]:
            self.moveTo(cx, cy)
        x0, y0 = self._last_user()
        n = self._nseg([(x0, y0), (cx, cy), (x, y)])
        sub = self._sub()
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            sub.append(self._pt(u * u * x0 + 2 * u * t * cx + t * t * x, u * u * y0 + 2 * u * t * cy + t * t * y))

    def bezierCurveTo(self, c1x, c1y, c2x, c2y, x, y):
        if not self._paths or not self._paths[-1][0]:
            self.moveTo(c1x, c1y)
        x0, y0 = self._last_user()
        n = self._nseg([(x0, y0), (c1x, c1y), (c2x, c2y), (x, y)])
        sub = self._sub()
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            sub.append(self._pt(u ** 3 * x0 + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t ** 3 * x,
                                u ** 3 * y0 + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t ** 3 * y))

    def arc(self, x, y, r, a0, a1, ccw=False):
        tau = 2 * math.pi
        if not ccw:
            sweep = a1 - a0
            sweep = tau if sweep >= tau else sweep % tau
        else:
            sweep = a0 - a1
            sweep = -(tau if sweep >= tau else sweep % tau)
        n = int(min(256, max(8, abs(sweep) * max(r, 0.0) * self._scale() * self.ss / 2.5)))
        pts = [self._pt(x + r * math.cos(a0 + sweep * i / n), y + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]
        if self._paths and self._paths[-1][0] and not self._paths[-1][1]:
            self._paths[-1][0].extend(pts)
        else:
            self._paths.append([pts, False])

    def rect(self, x, y, w, h):
        self._paths.append([[self._pt(x, y), self._pt(x + w, y), self._pt(x + w, y + h), self._pt(x, y + h)], True])
        self._paths.append([[self._pt(x, y)], False])

    def closePath(self):
        if self._paths and self._paths[-1][0]:
            self._paths[-1][1] = True

    # ---------------------------------------------------------------------------------------- coverage
    def _bbox(self, pts, pad):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0 = max(0, int(math.floor(min(xs) - pad)))
        y0 = max(0, int(math.floor(min(ys) - pad)))
        x1 = min(self.W, int(math.ceil(max(xs) + pad)) + 1)
        y1 = min(self.H, int(math.ceil(max(ys) + pad)) + 1)
        return x0, y0, x1, y1

    def _fill_mask(self, polys, pad=0.0):
        polys = [p for p in polys if len(p) >= 3]
        if not polys:
            return None
        x0, y0, x1, y1 = self._bbox([q for p in polys for q in p], pad + 1)
        if x1 <= x0 or y1 <= y0:
            return None
        im = Image.new('L', (x1 - x0, y1 - y0), 0)
        dr = ImageDraw.Draw(im)
        for p in polys:
            dr.polygon([(q[0] - x0, q[1] - y0) for q in p], fill=255)
        return im, x0, y0

    def _stroke_mask(self, pad=0.0):
        lw = max(0.5, self.lineWidth * self._scale() * self.ss)
        lines = []
        for pts, closed in self._paths:
            if len(pts) < 2 and not (len(pts) == 1 and self.lineCap == 'round'):
                continue
            q = list(pts)
            if closed and len(q) > 2:
                q.append(q[0])
            lines.append((q, closed))
        if not lines:
            return None
        x0, y0, x1, y1 = self._bbox([p for q, _ in lines for p in q], lw + pad + 2)
        if x1 <= x0 or y1 <= y0:
            return None
        im = Image.new('L', (x1 - x0, y1 - y0), 0)
        dr = ImageDraw.Draw(im)
        w = max(1, int(round(lw)))
        rr = lw / 2.0
        for q, closed in lines:
            pts = [(p[0] - x0, p[1] - y0) for p in q]
            if len(pts) >= 2:
                dr.line(pts, fill=255, width=w, joint='curve' if self.lineJoin == 'round' or len(pts) > 2 else None)
            if self.lineJoin == 'round' or self.lineCap == 'round':
                ends = pts if self.lineJoin == 'round' else ([] if closed else [pts[0], pts[-1]])
                if self.lineCap == 'round' and not closed:
                    ends = ends + [pts[0], pts[-1]]
                for (px, py) in ends:
                    dr.ellipse((px - rr, py - rr, px + rr, py + rr), fill=255)
            elif self.lineCap == 'square' and not closed and len(pts) >= 2:
                for (ax, ay), (bx, by) in ((pts[0], pts[1]), (pts[-1], pts[-2])):
                    dx, dy = ax - bx, ay - by
                    L = math.hypot(dx, dy) or 1.0
                    dr.line([(ax, ay), (ax + dx / L * rr, ay + dy / L * rr)], fill=255, width=w)
        return im, x0, y0

    # ------------------------------------------------------------------------------------------ compositing
    def _paint(self, style, x0, y0, w, h):
        """The style's straight colour: a 4-tuple, or per-pixel (h, w, 4) for a gradient."""
        if isinstance(style, _Gradient):
            gx0, gy0, r0, gx1, gy1, r1 = style.c
            a, b, c, d, e, f = self._tf
            det = a * d - b * c
            ys, xs = np.mgrid[y0:y0 + h, x0:x0 + w].astype(np.float32)
            X = (xs + 0.5) / self.ss - e
            Y = (ys + 0.5) / self.ss - f
            ux = (d * X - c * Y) / det
            uy = (-b * X + a * Y) / det
            dist = np.hypot(ux - gx1, uy - gy1)
            t = np.clip((dist - r0) / max(1e-9, (r1 - r0)), 0.0, 1.0)
            offs = [s[0] for s in style.stops]
            out = np.empty((h, w, 4), np.float32)
            for k in range(4):
                out[..., k] = np.interp(t, offs, [s[1][k] for s in style.stops])
            return out
        return css_color(style)

    def _composite(self, mask_img, x0, y0, style, alpha=1.0):
        cov = np.asarray(mask_img, dtype=np.float32) / 255.0
        h, w = cov.shape
        x1, y1 = min(self.W, x0 + w), min(self.H, y0 + h)
        cov = cov[:y1 - y0, :x1 - x0]
        h, w = cov.shape
        if h <= 0 or w <= 0:
            return
        if self._clip is not None:
            cov = cov * self._clip[y0:y1, x0:x1]
        col = self._paint(style, x0, y0, w, h)
        ga = float(self.globalAlpha) * alpha
        dst = self.buf[y0:y1, x0:x1]
        if isinstance(col, tuple):
            a = col[3] * ga * cov
            src = np.stack([col[0] * a, col[1] * a, col[2] * a, a], axis=-1)
        else:
            a = col[..., 3] * ga * cov
            src = np.concatenate([col[..., :3] * a[..., None], a[..., None]], axis=-1)
        if self.globalCompositeOperation == 'lighter':
            np.minimum(dst + src, 1.0, out=dst)
        else:
            dst *= (1.0 - a)[..., None]
            dst += src

    def _with_shadow(self, mask):
        if mask is None:
            return
        im, x0, y0 = mask
        sc = css_color(self.shadowColor)
        if self.shadowBlur > 0 and sc[3] > 0:
            sig = self.shadowBlur / 2.0 * self.ss
            pad = int(math.ceil(sig * 3)) + 1
            big = Image.new('L', (im.width + 2 * pad, im.height + 2 * pad), 0)
            big.paste(im, (pad, pad))
            big = big.filter(ImageFilter.GaussianBlur(sig))
            bx, by = x0 - pad, y0 - pad
            if bx < 0 or by < 0:
                big = big.crop((max(0, -bx), max(0, -by), big.width, big.height))
                bx, by = max(0, bx), max(0, by)
            self._composite(big, bx, by, sc)

    # ------------------------------------------------------------------------------------------- drawing
    def fill(self):
        polys = [p for p, _ in self._paths]
        m = self._fill_mask(polys)
        if m is None:
            return
        self._with_shadow(m)
        self._composite(m[0], m[1], m[2], self.fillStyle)

    def stroke(self):
        m = self._stroke_mask()
        if m is None:
            return
        self._with_shadow(m)
        self._composite(m[0], m[1], m[2], self.strokeStyle)

    def clip(self):
        polys = [p for p, _ in self._paths]
        new = np.zeros((self.H, self.W), np.float32)
        m = self._fill_mask(polys)
        if m is not None:
            im, x0, y0 = m
            a = np.asarray(im, dtype=np.float32) / 255.0
            h, w = a.shape
            x1, y1 = min(self.W, x0 + w), min(self.H, y0 + h)
            new[y0:y1, x0:x1] = a[:y1 - y0, :x1 - x0]
        self._clip = new if self._clip is None else self._clip * new

    def fillRect(self, x, y, w, h):
        a, b, c, d, e, f = self._tf
        if b == 0.0 and c == 0.0 and not isinstance(self.fillStyle, _Gradient) and not (
                self.shadowBlur > 0 and css_color(self.shadowColor)[3] > 0):
            X0, Y0 = self._pt(x, y)
            X1, Y1 = self._pt(x + w, y + h)
            X0, X1 = sorted((X0, X1))
            Y0, Y1 = sorted((Y0, Y1))
            ix0, iy0 = max(0, int(round(X0))), max(0, int(round(Y0)))
            ix1, iy1 = min(self.W, max(ix0 + 1, int(round(X1)))), min(self.H, max(iy0 + 1, int(round(Y1))))
            if ix1 <= ix0 or iy1 <= iy0:
                return
            self._composite(Image.new('L', (ix1 - ix0, iy1 - iy0), 255), ix0, iy0, self.fillStyle)
            return
        saved = self._paths
        self._paths = [[[self._pt(x, y), self._pt(x + w, y), self._pt(x + w, y + h), self._pt(x, y + h)], True]]
        self.fill()
        self._paths = saved

    def strokeRect(self, x, y, w, h):
        saved = self._paths
        self._paths = [[[self._pt(x, y), self._pt(x + w, y), self._pt(x + w, y + h), self._pt(x, y + h)], True]]
        self.stroke()
        self._paths = saved

    def clearRect(self, x, y, w, h):
        X0, Y0 = self._pt(x, y)
        X1, Y1 = self._pt(x + w, y + h)
        X0, X1 = sorted((X0, X1))
        Y0, Y1 = sorted((Y0, Y1))
        self.buf[max(0, int(Y0)):max(0, int(math.ceil(Y1))), max(0, int(X0)):max(0, int(math.ceil(X1)))] = 0.0

    def createRadialGradient(self, x0, y0, r0, x1, y1, r1):
        return _Gradient(x0, y0, r0, x1, y1, r1)

    def measureText(self, text):
        return _TextMetrics(measure_text(self.font, str(text)))

    def _text_anchor(self):
        h = {'left': 'l', 'start': 'l', 'center': 'm', 'right': 'r', 'end': 'r'}.get(self.textAlign, 'l')
        v = {'alphabetic': 's', 'middle': 'm', 'top': 'a', 'hanging': 'a', 'bottom': 'd', 'ideographic': 'd'
             }.get(self.textBaseline, 's')
        return h + v

    def _text_mask(self, text, x, y):
        path, px = parse_font(self.font)
        k = self._scale() * self.ss
        size = max(1, int(round(px * k)))
        font = _pil_font(path, size)
        anchor = self._text_anchor()
        l, t, r, b = font.getbbox(text, anchor=anchor)
        pad = 4
        a, bb, c, d, e, f = self._tf
        if abs(bb) < 1e-9 and abs(c) < 1e-9 and a > 0 and d > 0:
            X, Y = self._pt(x, y)
            ox, oy = int(math.floor(X + l)) - pad, int(math.floor(Y + t)) - pad
            im = Image.new('L', (int(r - l) + 2 * pad + 2, int(b - t) + 2 * pad + 2), 0)
            ImageDraw.Draw(im).text((X - ox, Y - oy), text, font=font, fill=255, anchor=anchor)
            if ox < 0 or oy < 0:
                im = im.crop((max(0, -ox), max(0, -oy), im.width, im.height))
                ox, oy = max(0, ox), max(0, oy)
            return im, ox, oy
        # rotated / sheared: draw in text space at the device scale, then map it with the inverse affine
        lw, lh = int(r - l) + 2 * pad, int(b - t) + 2 * pad
        ax, ay = -l + pad, -t + pad                           # the anchor's place in the local image
        loc = Image.new('L', (max(1, lw), max(1, lh)), 0)
        ImageDraw.Draw(loc).text((ax, ay), text, font=font, fill=255, anchor=anchor)
        corners = [(-ax, -ay), (lw - ax, -ay), (lw - ax, lh - ay), (-ax, lh - ay)]
        dev = [self._pt(x + cx / k, y + cy / k) for cx, cy in corners]
        X0, Y0, X1, Y1 = self._bbox(dev, 2)
        if X1 <= X0 or Y1 <= Y0:
            return None
        det = a * d - bb * c
        ia, ib, ic, id_ = d / det, -bb / det, -c / det, a / det        # inverse of [[a c] [b d]]
        s, kk = self.ss, k / self.ss
        # local u = kk*(ia*(Xd/s - e) + ic*(Yd/s - f) - x)*s/s ... with Xd = X + X0
        cu = kk * s
        A = cu * ia / s
        B = cu * ic / s
        C = cu * (ia * (X0 / s - e) + ic * (Y0 / s - f) - x) + ax
        D = cu * ib / s
        E = cu * id_ / s
        F_ = cu * (ib * (X0 / s - e) + id_ * (Y0 / s - f) - y) + ay
        im = loc.transform((X1 - X0, Y1 - Y0), Image.AFFINE, (A, B, C, D, E, F_), resample=Image.BILINEAR)
        return im, X0, Y0

    def fillText(self, text, x, y):
        text = str(text)
        if not text:
            return
        m = self._text_mask(text, x, y)
        if m is None:
            return
        self._with_shadow(m)
        self._composite(m[0], m[1], m[2], self.fillStyle)

    def strokeText(self, text, x, y):
        self.fillText(text, x, y)

    # ------------------------------------------------------------------------------------------- output
    def to_float(self):
        """(height, width, 4) straight-alpha sRGB floats at the canvas size (box-filtered from the supersample)."""
        s = self.ss
        b = self.buf.reshape(self.height, s, self.width, s, 4).mean(axis=(1, 3)) if s > 1 else self.buf.copy()
        a = b[..., 3:4]
        rgb = np.where(a > 1e-6, b[..., :3] / np.maximum(a, 1e-6), 0.0)
        return np.concatenate([np.clip(rgb, 0, 1), np.clip(a, 0, 1)], axis=-1).astype(np.float32)

    def to_rgba8(self):
        return (self.to_float() * 255.0 + 0.5).astype(np.uint8)

    def to_image(self):
        return Image.fromarray(self.to_rgba8(), 'RGBA')


def make_canvas(w, h, ss=2):
    """The canvas factory the drawing functions take (drawPageAtlas's makeCanvas)."""
    return Canvas2D(w, h, ss)


# ================================================================================================ the pages ====

VOCAB = ('future machine risk progress freedom speed steel safety order power mind engine model answer question '
         'voice screen static sermon forum thread manifesto letter people market race god fear hope signal noise truth '
         'value control alignment threat promise history tomorrow nation capital labour dream warning silence argument '
         'everyone nobody must will never always only every each now soon again before after because therefore unless '
         'we they you it the a of and to in for with on by from is are was be not no yes more less than all some '
         'new old last first great small deep fast slow open closed public private true false clear unknown force').split(' ')
HEAD = ['THE FUTURE', 'MACHINE GOD?', 'WHO DECIDES', 'SLOW IT DOWN', 'SPEED UP', 'NOT YET', 'THE LAST INVENTION',
        'ARE WE READY', 'A RACE TO WIN', 'THE ENGINE', 'IT SPEAKS', 'TURN IT DOWN', 'WHAT IT WANTS', 'BEFORE IT SPEAKS']
MASTS = ['THE MORNING CERTAINTY', 'THE EVENING ARGUMENT', 'THE DAILY DISCOURSE', 'THE WEEKLY CONSENSUS']


def pick(r, a):
    return a[min(len(a) - 1, int(math.floor(r() * len(a))))]


def words(r, n):
    return [pick(r, VOCAB) for _ in range(n)]


def sentence(r, n):
    w = words(r, n)
    w[0] = w[0][0].upper() + w[0][1:]
    return ' '.join(w) + pick(r, ['.', '.', '.', '?', ',', ':'])


def F(px, fam, wt=''):
    return f'{wt + " " if wt else ""}{max(1, js_round(px))}px "{fam}"'


FAM = {'grot': 'UF Anton', 'wide': 'UF Archivo Black', 'slab': 'UF Alfa Slab', 'serif': 'UF Old Standard',
       'serifB': 'UF Old Standard Bold', 'ital': 'UF Old Standard Italic', 'mono': 'UF Space Mono',
       'monoB': 'UF Space Mono Bold', 'disp': 'UF Bungee', 'hand': 'UF Caveat Brush', 'sten': 'UF Black Ops'}


def body(g, r, x, y, w, h, px, fam, color, lead=1.32):
    """Body copy: justified-looking lines of invented words inside a column."""
    g.font = F(px, fam)
    g.fillStyle = color
    lh = px * lead
    yy = y + px
    while yy < y + h:
        line = ''
        lw = 0.0
        while True:
            wd = pick(r, VOCAB)
            ww = g.measureText((' ' if line else '') + wd).width
            if lw + ww > w:
                break
            line += (' ' if line else '') + wd
            lw += ww
        if r() < 0.06:                                  # paragraph break
            yy += lh * 0.5
            yy += lh
            continue
        g.fillText(line, x, yy)
        yy += lh


def rule(g, x, y, w, t, color):
    g.fillStyle = color
    g.fillRect(x, y, w, t)


def halftone(g, r, x, y, w, h, color):
    """A photo block printed in dots: a dark diagonal composition (no faces, no real photos)."""
    step = 7
    a = r() * math.pi
    cx = x + w * (0.3 + r() * 0.4)
    cy = y + h * (0.3 + r() * 0.4)
    g.fillStyle = color
    yy = y
    while yy < y + h:
        xx = x
        while xx < x + w:
            d = ((xx - cx) * math.cos(a) + (yy - cy) * math.sin(a)) / w
            v = max(0.0, min(1.0, 0.5 + 0.9 * math.sin(d * 7) * 0.5 + (r() - 0.5) * 0.15 + ((yy - y) / h) * 0.25))
            rad = step * 0.5 * math.sqrt(v)
            if rad > 0.4:
                g.beginPath()
                g.arc(xx + step / 2, yy + step / 2, rad, 0, 6.283)
                g.fill()
            xx += step
        yy += step


def scribble(g, r, x, y, w, h, color, lw=2):
    g.strokeStyle = color
    g.lineWidth = lw
    g.lineCap = 'round'
    g.beginPath()
    px, py = x, y + h / 2
    g.moveTo(px, py)
    for _ in range(18):
        px += w / 18
        cy = py + (r() - 0.5) * h * 1.6
        g.quadraticCurveTo(px - w / 36, cy, px, y + h * (0.3 + r() * 0.4))
    g.stroke()


def stain(g, r, w, h):
    """A coffee ring, a crease, grime toward the edges."""
    if r() < 0.35:
        cx = w * (0.2 + r() * 0.6)
        cy = h * (0.2 + r() * 0.6)
        rad = w * (0.08 + r() * 0.06)
        g.strokeStyle = 'rgba(120,80,30,0.22)'
        g.lineWidth = 5 + r() * 6
        g.beginPath()
        g.arc(cx, cy, rad, 0.3, 6.0)
        g.stroke()
    g.strokeStyle = 'rgba(0,0,0,0.10)'
    g.lineWidth = 2
    for _ in range(2):
        yy = h * (0.25 + r() * 0.5)
        g.beginPath()
        g.moveTo(0, yy)
        g.lineTo(w, yy + (r() - 0.5) * 30)
        g.stroke()
    gr = g.createRadialGradient(w / 2, h / 2, min(w, h) * 0.35, w / 2, h / 2, max(w, h) * 0.75)
    gr.addColorStop(0, 'rgba(60,45,20,0)')
    gr.addColorStop(1, 'rgba(60,45,20,0.28)')
    g.fillStyle = gr
    g.fillRect(0, 0, w, h)


def outline(g, r, w, h, torn):
    """The page outline: mostly a clean rectangle, sometimes torn along one side (alpha cut)."""
    g.beginPath()
    if not torn:
        g.rect(0, 0, w, h)
        return
    side, N = int(math.floor(r() * 4)), 40
    pts = [(0, 0), (w, 0), (w, h), (0, h)]
    for s in range(4):
        (x0, y0), (x1, y1) = pts[s], pts[(s + 1) % 4]
        if s != side:
            if s == 0:
                g.moveTo(x0, y0)
            g.lineTo(x1, y1)
            continue
        if s == 0:
            g.moveTo(x0, y0)
        for i in range(1, N + 1):
            u, nx, ny = i / N, -(y1 - y0), x1 - x0
            L = math.hypot(nx, ny)
            d = (r() * 0.9 + 0.1) * min(w, h) * 0.07
            k = 1 if i < N else 0
            g.lineTo(x0 + (x1 - x0) * u + nx / L * d * k, y0 + (y1 - y0) * u + ny / L * d * k)
    g.closePath()


PAPER = {'white': '#f2f0ea', 'news': '#e7dcc2', 'yellow': '#eadaa6', 'grey': '#d9d9d4', 'pink': '#efd6d2',
         'blue': '#d6e2ea', 'green': '#e3eedd'}
INK, RED = '#1b1917', '#b3232b'


# ------------------------------------------------------------------------------------- one page per kind
def _newspaper(g, w, h, r, k):
    m = MASTS[k % len(MASTS)]
    g.fillStyle = INK
    g.textAlign = 'center'
    g.font = F(w * 0.075, FAM['serifB'])
    mw = g.measureText(m).width
    if mw > w * 0.9:
        g.font = F(w * 0.075 * (w * 0.9) / mw, FAM['serifB'])
    g.fillText(m, w / 2, h * 0.075)
    rule(g, w * 0.05, h * 0.09, w * 0.9, 3, INK)
    rule(g, w * 0.05, h * 0.097, w * 0.9, 1, INK)
    g.font = F(w * 0.022, FAM['mono'])
    vol = 10 + int(math.floor(r() * 90))
    no = 100 + int(math.floor(r() * 900))
    g.fillText(f'VOL. {vol}  \u00b7  No. {no}  \u00b7  ONE EDITION ONLY', w / 2, h * 0.115)
    head = pick(r, HEAD)
    g.font = F(w * (0.12 if len(head) > 10 else 0.16), FAM['grot'])
    g.fillStyle = RED if r() < 0.4 else INK
    g.fillText(head, w / 2, h * 0.24)
    g.fillStyle = INK
    g.font = F(w * 0.03, FAM['ital'])
    g.fillText(sentence(r, 9), w / 2, h * 0.285)
    g.textAlign = 'left'
    cols = 3 + int(math.floor(r() * 2))
    gx = w * 0.05
    cw = (w * 0.9 - (cols - 1) * 10) / cols
    photo = r() < 0.7
    for c in range(cols):
        x = gx + c * (cw + 10)
        y0 = h * 0.31
        if photo and c < 2:
            if c == 0:
                halftone(g, r, x, y0, cw * 2 + 10, h * 0.2, INK)
            y0 += h * 0.22
        if r() < 0.5:
            hd = pick(r, HEAD).lower()
            g.font = F(w * 0.032, FAM['serifB'])
            hw = g.measureText(hd).width
            if hw > cw:
                g.font = F(w * 0.032 * cw / hw, FAM['serifB'])
            g.fillStyle = INK
            g.fillText(hd, x, y0 + w * 0.03)
            y0 += w * 0.05
        body(g, r, x, y0, cw, h * 0.95 - y0, w * 0.018, FAM['serif'], '#2a2622')
        if c < cols - 1:
            rule(g, x + cw + 4, h * 0.31, 1, h * 0.64, 'rgba(0,0,0,0.45)')


def _forum(g, w, h, r, k):
    g.fillStyle = INK
    g.font = F(w * 0.04, FAM['monoB'])
    n = 1 if k % 2 else 23 + int(math.floor(r() * 20))
    g.fillText(f'THREAD {n}/47', w * 0.06, h * 0.06)
    g.font = F(w * 0.024, FAM['mono'])
    hd = pick(r, HEAD).lower()
    g.fillText(f're: {hd} ({200 + int(math.floor(r() * 4000))} replies)', w * 0.06, h * 0.09)
    rule(g, w * 0.05, h * 0.105, w * 0.9, 2, INK)
    y = h * 0.14
    while y < h * 0.93:
        opts = ['anon', f'user_{1000 + int(math.floor(r() * 8999))}', f'throwaway_{int(math.floor(r() * 99))}',
                'lurker', 'op', 'mod', f'nobody_{int(math.floor(r() * 9))}']
        user = pick(r, opts)
        g.font = F(w * 0.024, FAM['monoB'])
        g.fillStyle = INK
        up = int(math.floor(r() * 999))
        num = int(math.floor(r() * 9999))
        g.fillText(f'{user}  \u25b2 {up}  #{num}', w * 0.06, y)
        y += w * 0.03
        if r() < 0.3:
            g.fillStyle = 'rgba(0,0,0,0.08)'
            g.fillRect(w * 0.08, y - w * 0.018, w * 0.84, w * 0.07)
            g.fillStyle = '#555'
            g.font = F(w * 0.02, FAM['ital'])
            g.fillText('> ' + sentence(r, 8), w * 0.1, y + w * 0.012)
            y += w * 0.08
        n = 2 + int(math.floor(r() * 4))
        body(g, r, w * 0.06, y - w * 0.02, w * 0.88, n * w * 0.028, w * 0.021, FAM['mono'], '#262321', 1.3)
        y += n * w * 0.028 + w * 0.035
        if r() < 0.12:
            g.font = F(w * 0.022, FAM['mono'])
            g.fillStyle = '#777'
            g.fillText('[deleted]', w * 0.06, y)
            y += w * 0.04


def _greenbar(g, w, h, r, k):
    y, i = 0.0, 0
    while y < h:
        g.fillStyle = 'rgba(120,180,120,0.28)' if i % 2 else 'rgba(255,255,255,0)'
        g.fillRect(w * 0.06, y, w * 0.88, h / 22)
        y += h / 22
        i += 1
    g.fillStyle = 'rgba(0,0,0,0.25)'
    y = 12
    while y < h:
        g.beginPath()
        g.arc(w * 0.025, y, 5, 0, 6.283)
        g.fill()
        g.beginPath()
        g.arc(w * 0.975, y, 5, 0, 6.283)
        g.fill()
        y += 26
    g.fillStyle = '#2b2b2b'
    g.font = F(w * 0.024, FAM['mono'])
    y = h * 0.05
    while y < h * 0.96:
        pre = 're: re: ' if r() < 0.5 else '> '
        g.fillText(pre + ' '.join(words(r, 5 + int(math.floor(r() * 4)))).upper(), w * 0.08, y)
        y += w * 0.036


def _sermon(g, w, h, r, k):
    g.fillStyle = INK
    g.textAlign = 'center'
    g.font = F(w * 0.07, FAM['serifB'])
    g.fillText('SERMON' if r() < 0.5 else 'ON THE LAST DAYS', w / 2, h * 0.08)
    g.font = F(w * 0.028, FAM['ital'])
    g.fillText('the ' + pick(r, ['seventh', 'last', 'first', 'eleventh']) + ' reading', w / 2, h * 0.115)
    g.strokeStyle = INK
    g.lineWidth = 1.5
    g.beginPath()
    g.moveTo(w * 0.3, h * 0.13)
    g.lineTo(w * 0.7, h * 0.13)
    g.stroke()
    g.textAlign = 'left'
    cw = w * 0.42
    for c in range(2):
        x = w * 0.06 + c * (cw + w * 0.04)
        y = h * 0.16
        if c == 0:
            g.font = F(w * 0.16, FAM['serifB'])
            g.fillStyle = RED
            g.fillText(pick(r, ['A', 'T', 'W', 'I', 'O']), x, y + w * 0.13)
        v = 1
        while y < h * 0.94:
            g.font = F(w * 0.02, FAM['serifB'])
            g.fillStyle = RED
            g.fillText(str(v), x + (w * 0.13 if c == 0 and v < 3 else 0), y + w * 0.022)
            n = 2 + int(math.floor(r() * 4))
            ind = w * 0.16 if c == 0 and v < 3 else w * 0.03
            body(g, r, x + ind, y, cw - ind, n * w * 0.03, w * 0.021, FAM['serif'], '#2b2724', 1.35)
            y += n * w * 0.03 + w * 0.012
            v += 1


def _manifesto(g, w, h, r, k):
    g.fillStyle = INK
    g.font = F(w * 0.15, FAM['slab'])
    g.fillText('MANIFESTO', w * 0.05, h * 0.12)
    g.font = F(w * 0.03, FAM['ital'])
    a_ = pick(r, VOCAB)
    b_ = pick(r, VOCAB)
    g.fillText(f'of the {a_} and the {b_}', w * 0.06, h * 0.155)
    rule(g, w * 0.05, h * 0.17, w * 0.9, 4, RED)
    y = h * 0.21
    i = 1
    while y < h * 0.94:
        g.font = F(w * 0.04, FAM['grot'])
        g.fillStyle = RED
        g.fillText(f'{i}.', w * 0.05, y + w * 0.035)
        g.font = F(w * 0.03, FAM['wide'])
        g.fillStyle = INK
        g.fillText(' '.join(words(r, 3)).upper(), w * 0.14, y + w * 0.033)
        n = 1 + int(math.floor(r() * 3))
        body(g, r, w * 0.14, y + w * 0.04, w * 0.8, n * w * 0.03, w * 0.022, FAM['serif'], '#2b2724')
        y += w * 0.05 + n * w * 0.03 + w * 0.02
        i += 1


def _futurist(g, w, h, r, k):
    """Our own words-in-freedom page: diagonal words, signs, sizes."""
    items = ['SPEED', '+', 'STEEL', '=', 'TUMB', 'zang', 'VELOCIT\u00c0', 'trrrr', 'FUTURE', '\u00d7', '!!!']
    for i in range(9):
        g.save()
        tx = w * (0.1 + r() * 0.8)
        g.translate(tx, h * (0.08 + i * 0.1))
        g.rotate((r() - 0.5) * 1.1)
        t = pick(r, items)
        big = r() < 0.4
        g.font = F(w * (0.16 if big else 0.07), pick(r, [FAM['grot'], FAM['slab'], FAM['serifB'], FAM['disp']]))
        g.fillStyle = RED if r() < 0.35 else INK
        g.fillText(t, -g.measureText(t).width / 2, 0)
        g.restore()
    g.strokeStyle = INK
    g.lineWidth = 6
    g.beginPath()
    g.moveTo(w * 0.05, h * 0.95)
    g.lineTo(w * 0.95, h * 0.1)
    g.stroke()


def _letter(g, w, h, r, k):
    g.fillStyle = INK
    g.font = F(w * 0.09, FAM['serifB'])
    g.fillText('OPEN LETTER', w * 0.07, h * 0.1)
    g.font = F(w * 0.026, FAM['ital'])
    g.fillText('to whoever is listening', w * 0.07, h * 0.135)
    body(g, r, w * 0.07, h * 0.17, w * 0.86, h * 0.45, w * 0.023, FAM['serif'], '#2b2724', 1.45)
    g.font = F(w * 0.024, FAM['serif'])
    g.fillStyle = INK
    g.fillText('signed,', w * 0.07, h * 0.66)
    for i in range(18):
        scribble(g, r, w * (0.07 + (i % 3) * 0.3), h * (0.69 + (i // 3) * 0.045), w * 0.22, w * 0.03, '#203060', 1.6)


def _memo(g, w, h, r, k):
    g.fillStyle = INK
    g.font = F(w * 0.07, FAM['monoB'])
    g.fillText('MEMORANDUM', w * 0.07, h * 0.08)
    g.font = F(w * 0.026, FAM['monoB'])
    for i, f in enumerate(['TO:', 'FROM:', 'RE:', 'CLASS:']):
        g.fillStyle = INK
        g.fillText(f, w * 0.07, h * (0.13 + i * 0.035))
        g.fillStyle = '#111'
        g.fillRect(w * 0.25, h * (0.13 + i * 0.035) - w * 0.022, w * (0.25 + r() * 0.4), w * 0.026)
    rule(g, w * 0.07, h * 0.28, w * 0.86, 2, INK)
    y = h * 0.31
    while y < h * 0.93:
        n = 2 + int(math.floor(r() * 4))
        body(g, r, w * 0.07, y, w * 0.86, n * w * 0.032, w * 0.022, FAM['mono'], '#262321', 1.4)
        for kk in range(n):
            if r() < 0.35:
                g.fillStyle = '#111'
                x0 = w * (0.07 + r() * 0.5)
                g.fillRect(x0, y + kk * w * 0.032 + w * 0.006, w * (0.1 + r() * 0.25), w * 0.024)
        y += n * w * 0.032 + w * 0.03
    g.save()
    g.translate(w * 0.62, h * 0.2)
    g.rotate(-0.25)
    g.strokeStyle = RED
    g.lineWidth = 5
    g.strokeRect(-w * 0.16, -w * 0.05, w * 0.32, w * 0.1)
    g.font = F(w * 0.06, FAM['sten'])
    g.fillStyle = RED
    g.fillText('URGENT', -w * 0.14, w * 0.025)
    g.restore()


def _chat(g, w, h, r, k):
    g.fillStyle = '#222'
    g.font = F(w * 0.024, FAM['mono'])
    y = h * 0.05
    while y < h * 0.95:
        who = '> user:' if r() < 0.5 else '> model:'
        g.font = F(w * 0.024, FAM['monoB'])
        g.fillText(who, w * 0.06, y)
        n = 1 + int(math.floor(r() * 4))
        body(g, r, w * 0.24, y - w * 0.024, w * 0.7, n * w * 0.03, w * 0.022, FAM['mono'], '#333', 1.32)
        y += n * w * 0.03 + w * 0.03


def _chart(g, w, h, r, k):
    g.strokeStyle = 'rgba(40,90,140,0.35)'
    g.lineWidth = 1
    x = 0.0
    while x < w:
        g.beginPath()
        g.moveTo(x, 0)
        g.lineTo(x, h)
        g.stroke()
        x += w / 20
    y = 0.0
    while y < h:
        g.beginPath()
        g.moveTo(0, y)
        g.lineTo(w, y)
        g.stroke()
        y += w / 20
    x0, y0, x1, y1 = w * 0.12, h * 0.82, w * 0.9, h * 0.2
    g.strokeStyle = INK
    g.lineWidth = 3
    g.beginPath()
    g.moveTo(x0, y1)
    g.lineTo(x0, y0)
    g.lineTo(x1, y0)
    g.stroke()
    g.strokeStyle = RED
    g.lineWidth = 5
    g.beginPath()
    for i in range(61):
        u = i / 60
        v = (math.exp(u * 4.2) - 1) / (math.exp(4.2) - 1)
        if i:
            g.lineTo(x0 + u * (x1 - x0), y0 - v * (y0 - y1))
        else:
            g.moveTo(x0, y0)
    g.stroke()
    g.fillStyle = INK
    g.font = F(w * 0.05, FAM['hand'])
    g.fillText(pick(r, ['p = 0.1?', 'odds', 'when?', 'too fast']), w * 0.5, h * 0.3)
    g.font = F(w * 0.03, FAM['mono'])
    g.fillText('t \u2192', x1 - w * 0.08, y0 + w * 0.05)
    g.fillText('?', x0 - w * 0.06, y1 + w * 0.02)


def _ad(g, w, h, r, k):
    g.fillStyle = '#e7d23a' if r() < 0.5 else '#f2f0ea'
    g.fillRect(0, 0, w, h)
    g.fillStyle = INK
    g.textAlign = 'center'
    g.font = F(w * 0.2, FAM['grot'])
    g.fillText(pick(r, ['BUY NOW', 'NEW!', 'UPGRADE', 'SALE']), w / 2, h * 0.25)
    g.font = F(w * 0.12, FAM['disp'])
    g.fillStyle = RED
    g.fillText(pick(r, ['$100,000,000', '$20,000,000', '99.9%', 'v.NEXT']), w / 2, h * 0.45)
    g.save()                                            # a starburst
    g.translate(w * 0.5, h * 0.7)
    g.fillStyle = RED
    g.beginPath()
    for i in range(32):
        a = i / 32 * 6.283
        rr = w * 0.18 if i % 2 else w * 0.3
        g.lineTo(math.cos(a) * rr, math.sin(a) * rr)
    g.fill()
    g.fillStyle = '#fff'
    g.font = F(w * 0.07, FAM['wide'])
    g.fillText('ONLY', 0, w * 0.02)
    g.restore()
    g.textAlign = 'left'


def _notebook(g, w, h, r, k):
    g.strokeStyle = 'rgba(60,110,190,0.45)'
    g.lineWidth = 1.5
    y = h * 0.1
    while y < h:
        g.beginPath()
        g.moveTo(0, y)
        g.lineTo(w, y)
        g.stroke()
        y += h / 30
    g.strokeStyle = 'rgba(200,40,40,0.5)'
    g.beginPath()
    g.moveTo(w * 0.12, 0)
    g.lineTo(w * 0.12, h)
    g.stroke()
    g.fillStyle = '#1d2a6a'
    g.font = F(w * 0.06, FAM['hand'])
    notes = ['slow it down', 'ship it anyway', 'who is it for?', 'ask it?', 'not a toaster', 'the fear sells',
             'it answered', 'turn it down']
    y = h * 0.1 + h / 30
    while y < h * 0.9:
        t = pick(r, notes)
        g.fillText(t, w * 0.15 + r() * w * 0.2, y - 4)
        y += h / 30 * (2 + int(math.floor(r() * 2)))


def _classifieds(g, w, h, r, k):
    g.fillStyle = INK
    g.font = F(w * 0.06, FAM['grot'])
    g.fillText('CLASSIFIED', w * 0.05, h * 0.06)
    cols = 4
    cw = w * 0.9 / cols
    for c in range(cols):
        y = h * 0.09
        while y < h * 0.95:
            bh = w * (0.06 + r() * 0.12)
            g.strokeStyle = '#333'
            g.lineWidth = 1
            g.strokeRect(w * 0.05 + c * cw + 3, y, cw - 6, bh)
            g.font = F(w * 0.02, FAM['monoB'])
            g.fillStyle = INK
            g.fillText(pick(r, VOCAB).upper(), w * 0.05 + c * cw + 7, y + w * 0.022)
            body(g, r, w * 0.05 + c * cw + 7, y + w * 0.022, cw - 14, bh - w * 0.03, w * 0.014, FAM['mono'], '#333', 1.25)
            y += bh + 6


def _poster(g, w, h, r, k):
    g.fillStyle = INK
    g.textAlign = 'center'
    g.font = F(w * 0.26, FAM['grot'])
    g.fillText('THE', w / 2, h * 0.27)
    g.fillText('FUTURE', w / 2, h * 0.52)
    g.font = F(w * 0.12, FAM['slab'])
    g.fillStyle = RED
    g.fillText('IS', w / 2, h * 0.68)
    g.font = F(w * 0.05, FAM['ital'])
    g.fillStyle = INK
    g.fillText('(the rest is torn off)', w / 2, h * 0.78)
    g.textAlign = 'left'


def _cut(g, w, h, r, k):
    """Futurist papier colle: coloured paper with a big type fragment or a cut shape."""
    pal = [('#141414', '#f2efe6'), ('#b81f2a', '#141414'), ('#d6a034', '#141414'), ('#2a4a8a', '#f2efe6'),
           ('#141414', '#c8262c'), ('#e9e2cf', '#141414')]
    bg, fg = pal[k % len(pal)]
    g.fillStyle = bg
    g.fillRect(0, 0, w, h)
    g.fillStyle = fg
    g.textAlign = 'center'
    t = ['ZANG', 'TUMB', '!!!', '+', '\u25cf', 'M'][k % 6]
    if t == '\u25cf':
        g.beginPath()
        g.arc(w / 2, h / 2, w * 0.35, 0, 6.283)
        g.fill()
    else:
        g.save()
        g.translate(w / 2, h * 0.6)
        g.rotate(-0.5 + r())
        g.font = F(w * (0.34 if len(t) > 2 else 0.6), FAM['grot'])
        g.fillText(t, 0, 0)
        g.restore()
    g.textAlign = 'left'


KINDS = {'newspaper': _newspaper, 'forum': _forum, 'greenbar': _greenbar, 'sermon': _sermon, 'manifesto': _manifesto,
         'futurist': _futurist, 'letter': _letter, 'memo': _memo, 'chat': _chat, 'chart': _chart, 'ad': _ad,
         'notebook': _notebook, 'classifieds': _classifieds, 'poster': _poster, 'cut': _cut}
PAGE_KINDS = ['newspaper', 'newspaper', 'newspaper', 'forum', 'forum', 'greenbar', 'sermon', 'sermon', 'manifesto',
              'futurist', 'letter', 'memo', 'chat', 'chart', 'ad', 'notebook', 'classifieds', 'poster',
              'cut', 'cut', 'cut', 'cut', 'cut', 'cut']
PAPER_OF = {'newspaper': ['news', 'news', 'yellow'], 'forum': ['white', 'grey'], 'greenbar': ['white'],
            'sermon': ['news', 'yellow'], 'manifesto': ['white', 'news'], 'futurist': ['news'], 'letter': ['white', 'blue'],
            'memo': ['white', 'pink'], 'chat': ['white', 'grey'], 'chart': ['white'], 'ad': ['white'],
            'notebook': ['white'], 'classifieds': ['news'], 'poster': ['white', 'yellow'], 'cut': ['white']}


def draw_page(kind, k, cw=682, ch=1024, seed=222, ss=2, make_canvas=make_canvas):
    """One cell of the atlas (kind PAGE_KINDS[k] at index k), drawn on its own cw x ch canvas exactly as
    drawPageAtlas draws it in place (the same seeded stream: rng(seed * 7919 + k * 104729))."""
    cv = make_canvas(cw, ch, ss)
    g = cv.getContext('2d')
    r = rng(seed * 7919 + k * 104729)
    m = 3                                                # a transparent margin: no bleeding between cells
    w, h = cw - 2 * m, ch - 2 * m
    g.save()
    g.translate(m, m)
    torn = kind != 'cut' and r() < 0.35
    outline(g, r, w, h, torn)
    g.save()
    g.clip()
    g.fillStyle = PAPER[pick(r, PAPER_OF.get(kind) or ['white'])]
    g.fillRect(0, 0, w, h)
    for _ in range(1400):                                # paper fibre
        g.fillStyle = 'rgba(0,0,0,0.035)' if r() < 0.5 else 'rgba(255,255,255,0.05)'
        fx, fy = r() * w, r() * h
        g.fillRect(fx, fy, 1 + r() * 3, 1)
    g.textBaseline = 'alphabetic'
    KINDS[kind](g, w, h, r, k)
    stain(g, r, w, h)
    g.restore()
    g.restore()
    return cv


ATLAS_VERSION = 1


def draw_page_atlas(make_canvas=make_canvas, cols=6, rows=4, cw=682, ch=1024, seed=222, ss=2, cache_dir=None):
    """The whole atlas as a PIL RGBA image (cols*cw x rows*ch, row 0 at the top), cell by cell.

    cache_dir: a folder for a PNG of the result, keyed by every argument (a rebuild reads it instead of drawing)."""
    key = hashlib.md5(repr((ATLAS_VERSION, cols, rows, cw, ch, seed, ss)).encode()).hexdigest()[:12]
    path = os.path.join(cache_dir, f'bin_page_atlas_{cols}x{rows}_{cw}x{ch}_{key}.png') if cache_dir else None
    if path and os.path.isfile(path):
        return Image.open(path).convert('RGBA')
    atlas = Image.new('RGBA', (cols * cw, rows * ch), (0, 0, 0, 0))
    for k, kind in enumerate(PAGE_KINDS[:cols * rows]):
        cell = draw_page(kind, k, cw, ch, seed, ss, make_canvas).to_image()
        atlas.paste(cell, ((k % cols) * cw, (k // cols) * ch))
    if path:
        os.makedirs(cache_dir, exist_ok=True)
        tmp = path + '.part'
        atlas.save(tmp, format='PNG', compress_level=1)
        os.replace(tmp, path)
    return atlas
