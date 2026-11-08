"""2D drawing for screens and textures: Pillow canvases, the bundled fonts by name, and draw_text_fit.

No bpy needed. Blender 5.2's Python ships Pillow (without RAQM, so no complex-script shaping) and numpy.

The WebGPU engine drew screens with canvas-2D on Skia. Here a screen's draw callback gets a ``Canvas``:
``canvas.image`` is a PIL RGBA image, ``canvas.draw`` an ImageDraw on it, ``canvas.w`` / ``canvas.h`` its size.
Fonts are files, never generic families (Skia's 'monospace' on Windows fell back to Arial; here a name that
is not a bundled or given font raises):

    f = font('Share Tech Mono', 48)          # or 'ShareTechMono-Regular', or a path to any TTF/OTF
    draw_text_fit(canvas, 'SYSTEM READY', x=w / 2, y=h * 0.3, max_width=w * 0.8, max_height=h * 0.4,
                  font='Share Tech Mono', px=64, align='center', fill='#c6f4ef')
"""
import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(__file__).resolve().parents[3] / 'eidoverse' / 'assets' / 'fonts'


def _norm(s):
    return ''.join(ch for ch in str(s).lower() if ch.isalnum())


@lru_cache(maxsize=1)
def _font_index():
    idx = {}
    for p in sorted(FONT_DIR.glob('*.[ot]tf')):
        stem = _norm(p.stem)
        idx.setdefault(stem, p)
        if stem.endswith('regular'):
            idx.setdefault(stem[:-len('regular')], p)
    return idx


def fonts():
    """The bundled font files (eidoverse/assets/fonts), by normalised name."""
    return dict(_font_index())


def font_path(name):
    """A font file from a path, a file stem ('ShareTechMono-Regular') or a family-like name ('Share Tech Mono')."""
    p = Path(str(name))
    if p.suffix.lower() in ('.ttf', '.otf') and p.is_file():
        return p.resolve()
    hit = _font_index().get(_norm(p.stem if p.suffix.lower() in ('.ttf', '.otf') else name))
    if hit is None:
        raise KeyError(f'font {name!r}: not a file and not one of the bundled fonts '
                       f'({", ".join(sorted(x.stem for x in set(_font_index().values())))})')
    return hit


@lru_cache(maxsize=256)
def _font(path, px):
    return ImageFont.truetype(str(path), px)


def font(name, px):
    """A Pillow FreeType font at px pixels (em size, as canvas-2D's 'NNpx')."""
    return _font(str(font_path(name)), max(1, int(round(px))))


def color(c):
    """'#rgb' / '#rrggbb' / '#rrggbbaa' / CSS names / 0xRRGGBB / (r, g, b[, a]) 0..255 -> an RGBA tuple."""
    if isinstance(c, int):
        return ((c >> 16) & 255, (c >> 8) & 255, c & 255, 255)
    if isinstance(c, (tuple, list)):
        t = tuple(int(round(v)) for v in c)
        return t if len(t) == 4 else t + (255,)
    from PIL import ImageColor
    return ImageColor.getcolor(str(c), 'RGBA')


class Canvas:
    """A drawing surface for one frame. ``ss`` supersamples: draw at ss x the size, downsampled on output,
    so ImageDraw's aliased shapes come out smooth. Coordinates and font px are in the supersampled pixels
    (the callback gets w and h at that size)."""

    def __init__(self, w, h, ss=1, background=None):
        self.ss = max(1, int(ss))
        self.out_size = (int(w), int(h))
        self.w, self.h = int(w) * self.ss, int(h) * self.ss
        self.image = Image.new('RGBA', (self.w, self.h), color(background) if background is not None else (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)

    def clear(self, c=(0, 0, 0, 0)):
        """Replace every pixel (alpha included) with c."""
        self.image.paste(color(c), (0, 0, self.w, self.h))

    def font(self, name, px):
        return font(name, px)

    def text_fit(self, text, **kw):
        return draw_text_fit(self, text, **kw)

    def layer(self):
        """A transparent RGBA layer the canvas size, for alpha-blended shapes: draw on it, then canvas.over(layer)."""
        return Image.new('RGBA', (self.w, self.h), (0, 0, 0, 0))

    def over(self, layer, xy=(0, 0)):
        """Alpha-composite an RGBA image onto the canvas (source-over)."""
        self.image.alpha_composite(layer.convert('RGBA'), dest=tuple(int(v) for v in xy))
        self.draw = ImageDraw.Draw(self.image)

    def result(self):
        if self.ss == 1:
            return self.image
        return self.image.resize(self.out_size, Image.Resampling.LANCZOS)


def draw_text_fit(target, text, x=0, y=0, max_width=512, max_height=math.inf, font='Share Tech Mono', px=48,
                  min_px=10, line_height=1.25, align='center', fill='#ffffff', stroke_width=0, stroke_fill=None):
    """Word-wrap ``text`` (explicit newlines kept) and shrink it until the block fits max_width x max_height,
    then draw it. ``x`` is the box centre (align='center'), left edge ('left') or right edge ('right'); ``y`` is
    the block's top. Returns {'px': size used, 'lines': [...]}: px under the request means it had to shrink,
    and if it shrank a lot, shorten the copy or enlarge the canvas. (render_scene.mjs drawTextFit, ported.)"""
    img = target.image if hasattr(target, 'image') else target
    d = ImageDraw.Draw(img)
    fpath = str(font_path(font))
    p = float(px)
    lines = []
    f = None
    while True:
        f = _font(fpath, max(1, int(round(p))))
        lines, ok = [], True
        for para in str(text).split('\n'):
            cur = ''
            for word in para.split():
                test = cur + ' ' + word if cur else word
                if f.getlength(test) <= max_width:
                    cur = test
                    continue
                if not cur:
                    ok = False
                    break
                lines.append(cur)
                cur = word
            if not ok:
                break
            lines.append(cur)
        if ok and len(lines) * p * line_height <= max_height:
            break
        nxt = p - max(1, round(p * 0.08))
        if nxt < min_px:
            break
        p = nxt
    anchor = {'center': 'ma', 'left': 'la', 'right': 'ra'}[align]
    for i, ln in enumerate(lines):
        d.text((x, y + i * p * line_height), ln, font=f, fill=color(fill), anchor=anchor,
               stroke_width=int(stroke_width), stroke_fill=color(stroke_fill) if stroke_fill is not None else None)
    return {'px': p, 'lines': lines}


def srgb_to_linear(a):
    """sRGB-encoded values 0..1 -> linear (numpy)."""
    a = np.asarray(a, dtype=np.float64)
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def mean_linear(img, alpha_weighted=True):
    """The mean scene-linear RGB of an sRGB image (alpha-weighted), for a screen's spill light."""
    a = np.asarray(img.convert('RGBA'), dtype=np.float64) / 255.0
    rgb = srgb_to_linear(a[..., :3])
    if alpha_weighted:
        rgb = rgb * a[..., 3:4]
    return rgb.reshape(-1, 3).mean(axis=0)


def save_png(img, path, compress_level=1):
    """Write a PNG atomically (a .part file renamed into place), so a render never reads half a frame."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.part')
    img.save(tmp, format='PNG', compress_level=compress_level)
    os.replace(tmp, path)
    return path
