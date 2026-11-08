"""eidoblend.harness.html_mesh: the production engine's HTMLMesh (html_mesh.js) in Blender. A UI element tree styled
with CSS (titles, lower thirds, chyrons, HUD chips, lyric cards, a settings panel) painted to a transparent image on
a plane, 1 mm per pixel, unlit, as the engine's CanvasTexture-backed mesh was.

    from eidoblend.harness.html_mesh import El, html_mesh
    card = El('div', style='background: rgba(0,0,0,0.85); padding: 20px; color: orange; '
                           'font: 600 80px VT323; border-radius: 18px; border: 3px solid #ff9a3c',
              text='I am Claude, I am Claude')
    mesh = html_mesh(card)                         # a plane facing -Y, 1 mm per pixel, its own unlit material
    live = html_mesh(lambda t: El('div', style=..., text=f'{t:05.2f} s'), frames=(1, 120))   # redrawn every frame

The engine had a browser lay the DOM out (getBoundingClientRect) and html2canvas paint it. Blender has no browser, so
this module lays the tree out itself, in the CSS subset UI cards use, and paints it the way html2canvas did:

    layout   block flow (children stack, margins, padding), display: flex (flex-direction row / column, gap,
             align-items, justify-content), width / height in px or %, text wrapped at word boundaries within the
             content box, line-height, text-align, display: none
    paint    background colour (rgba) in the border-radius rounded rectangle; four matching borders stroked round the
             rounded rectangle, otherwise each side's line; text in its font, colour and text-transform (top
             baseline, + 0.1 em); overflow: hidden / auto clips the children; <img src=...> scaled into its box;
             a <canvas> (a PIL image) drawn at its place; inputs: radio, checkbox (a checked box gets the ✔), range
             (track, fill, thumb), and the value of color / text / number fields, in accent-color (else color) with
             white or #111 accent text by the accent's luminance
    fonts    font-family names are the bundled fonts (eidoverse/assets/fonts) by family or file stem; the generic
             families map to bundled faces (monospace -> Space Mono, sans-serif -> Exo 2, serif -> Old Standard);
             weight 600 and over picks a family's Bold face when it has one

Not carried over: the mouse-event dispatch (dispatchDOMEvent / htmlevent: a pointer clicking a panel in XR; a rendered
film has no pointer) and the MutationObserver (a static element is painted once; a function of t is painted every
frame, which is what update() was for). The engine's isUIOverlay routing is the harness overlay layer:
post.make_overlay_layer(scene).add(mesh).
"""

from __future__ import annotations

import math
import re

from PIL import Image, ImageDraw

PX = 0.001                      # metres per pixel (the engine's PlaneGeometry(w * 0.001, h * 0.001))
GENERIC = {'monospace': 'SpaceMono-Regular', 'sans-serif': 'Exo2', 'serif': 'OldStandard-Regular',
           'system-ui': 'Exo2', 'cursive': 'Kalam-Regular', 'fantasy': 'Bungee-Regular'}
INHERITED = ('color', 'font-family', 'font-size', 'font-weight', 'font-style', 'line-height', 'text-align',
             'text-transform', 'accent-color')


class El:
    """One element: a tag ('div', 'span', 'p', 'img', 'canvas', 'input', ...), its style (a CSS declaration string or
    a dict), its own text (painted before its children, as a leading text node) and its children (El or str).
    Attributes: src (img: an image path), image (canvas: a PIL image), type / checked / value / min / max (input)."""

    def __init__(self, tag='div', style='', text=None, children=(), **attrs):
        self.tag = tag.lower()
        self.style = parse_style(style) if isinstance(style, str) else {k.replace('_', '-'): str(v)
                                                                         for k, v in dict(style).items()}
        self.text = text
        self.children = list(children)
        self.attrs = attrs

    def __repr__(self):
        return f'El({self.tag!r}, {len(self.children)} children)'


# ------------------------------------------------------------------------------------------------- the CSS ---

def parse_style(s):
    out = {}
    for decl in str(s or '').split(';'):
        if ':' in decl:
            k, v = decl.split(':', 1)
            out[k.strip().lower()] = v.strip()
    return out


def _px(v, ref=0.0, default=0.0):
    if v is None:
        return default
    v = str(v).strip()
    if v in ('', 'auto', 'none', 'normal'):
        return default
    if v.endswith('%'):
        return float(v[:-1]) * ref / 100.0
    m = re.match(r'^(-?[\d.]+)\s*(px|em|rem)?$', v)
    if not m:
        return default
    return float(m.group(1))


def _box4(st, prop, ref):
    """padding / margin shorthand (1-4 values) and its per-side longhands -> (top, right, bottom, left)."""
    vals = [0.0, 0.0, 0.0, 0.0]
    if prop in st:
        parts = st[prop].split()
        p = [_px(x, ref) for x in parts] or [0.0]
        if len(p) == 1:
            vals = p * 4
        elif len(p) == 2:
            vals = [p[0], p[1], p[0], p[1]]
        elif len(p) == 3:
            vals = [p[0], p[1], p[2], p[1]]
        else:
            vals = p[:4]
    for i, side in enumerate(('top', 'right', 'bottom', 'left')):
        if f'{prop}-{side}' in st:
            vals[i] = _px(st[f'{prop}-{side}'], ref)
    return vals


def css_color(c, default=None):
    """A CSS colour -> RGBA 0..255, or None for transparent / none."""
    if c is None:
        return default
    c = str(c).strip().lower()
    if c in ('transparent', 'none', ''):
        return None
    m = re.match(r'rgba?\(([^)]*)\)', c)
    if m:
        p = [x.strip() for x in m.group(1).replace('/', ',').split(',') if x.strip()]
        rgb = [float(x[:-1]) * 2.55 if x.endswith('%') else float(x) for x in p[:3]]
        a = p[3] if len(p) > 3 else '1'
        a = float(a[:-1]) / 100 if a.endswith('%') else float(a)
        return (int(round(rgb[0])), int(round(rgb[1])), int(round(rgb[2])), int(round(255 * a)))
    from PIL import ImageColor
    try:
        r = ImageColor.getcolor(c, 'RGBA')
    except ValueError:
        return default
    return tuple(r)


def _border(st, side):
    """(width, style, colour) of one side, from border / border-<side> / border-<side>-width|style|color."""
    w, s, c = 0.0, 'none', None
    for key in ('border', f'border-{side}'):
        if key in st:
            for tok in re.findall(r'rgba?\([^)]*\)|\S+', st[key]):
                if re.match(r'^[\d.]+(px)?$', tok):
                    w = _px(tok)
                elif tok in ('solid', 'dashed', 'dotted', 'double', 'none', 'hidden', 'groove', 'ridge', 'inset',
                             'outset'):
                    s = tok
                else:
                    c = css_color(tok, c)
    for key in ('border-width', f'border-{side}-width'):
        if key in st:
            w = _px(st[key].split()[0])
    for key in ('border-style', f'border-{side}-style'):
        if key in st:
            s = st[key].split()[0]
    for key in ('border-color', f'border-{side}-color'):
        if key in st:
            c = css_color(st[key])
    if s != 'none' and c is None:
        c = css_color(st.get('color', '#000000'))
    return w, s, c


def _font_parts(st):
    """(family list, size px, weight, line-height factor or px) from font / font-* (CSS shorthand order)."""
    fam, size, weight, lh = st.get('font-family'), st.get('font-size'), st.get('font-weight'), st.get('line-height')
    if 'font' in st:
        m = re.match(r'^(?:(italic|oblique|normal)\s+)?(?:(bold|bolder|lighter|normal|\d{3})\s+)?'
                     r'([\d.]+px)(?:\s*/\s*([\d.]+(?:px)?))?\s+(.+)$', st['font'].strip())
        if m:
            weight = m.group(2) or weight
            size = m.group(3)
            lh = m.group(4) or lh
            fam = m.group(5)
    fams = [f.strip().strip('"\'') for f in (fam or 'sans-serif').split(',')]
    w = {'bold': 700, 'bolder': 800, 'lighter': 300, 'normal': 400, None: 400}.get(weight, None)
    if w is None:
        try:
            w = int(weight)
        except (TypeError, ValueError):
            w = 400
    return fams, _px(size, default=16.0), w, lh


def font_for(fams, size, weight):
    """A PIL font for a CSS family list (the first that resolves among the bundled fonts)."""
    from ..media import raster
    tried = []
    for f in fams:
        f = GENERIC.get(f.lower(), f)
        cands = []
        if weight >= 600:
            base = re.sub(r'-?(regular|bold)$', '', f, flags=re.I)
            cands.append(base + '-Bold')
        cands.append(f)
        for c in cands:
            tried.append(c)
            try:
                return raster.font(c, max(1, int(round(size))))
            except KeyError:
                continue
    return raster.font(GENERIC['sans-serif'], max(1, int(round(size))))


# ---------------------------------------------------------------------------------------------- the layout ---

class _Box:
    def __init__(self, el, st):
        self.el, self.st = el, st
        self.x = self.y = self.w = self.h = 0.0
        self.pad = self.mar = (0.0, 0.0, 0.0, 0.0)
        self.lines = []              # [(text, x, y, font, colour)] in this element's own text
        self.kids = []


def _computed(el, parent_st):
    st = {k: parent_st[k] for k in INHERITED if k in parent_st}
    if 'font' in el.style:                                      # the shorthand resets the longhands it covers
        for k in ('font-family', 'font-size', 'font-weight', 'line-height'):
            st.pop(k, None)
    st.update(el.style)
    if 'font' in el.style:
        fams, size, w, lh = _font_parts(el.style)
        st['font-family'] = ','.join(fams)
        st['font-size'] = f'{size}px'
        st['font-weight'] = str(w)
        if lh:
            st['line-height'] = lh
    return st


def _line_height(st, size):
    lh = st.get('line-height')
    if lh is None or lh == 'normal':
        return size * 1.2
    if str(lh).endswith('px'):
        return _px(lh)
    try:
        return float(lh) * size
    except ValueError:
        return size * 1.2


def _wrap(text, font, max_w):
    lines = []
    for para in str(text).split('\n'):
        cur = ''
        for word in para.split():
            test = (cur + ' ' + word) if cur else word
            if max_w is None or font.getlength(test) <= max_w or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def _text_of(el):
    return el if isinstance(el, str) else None


def _layout(el, parent_st, avail_w, x, y):
    """Lay el out at (x, y) (its margin box's top-left) with avail_w for its margin box. Returns the box."""
    if isinstance(el, str):
        el = El('span', text=el)
    st = _computed(el, parent_st)
    b = _Box(el, st)
    if st.get('display') == 'none':
        b.hidden = True
        return b
    b.hidden = False
    b.mar = _box4(st, 'margin', avail_w or 0.0)
    b.pad = _box4(st, 'padding', avail_w or 0.0)
    bw = [_border(st, s)[0] for s in ('top', 'right', 'bottom', 'left')]
    fams, size, weight, _lh = _font_parts(st)
    font = font_for(fams, size, weight)
    lh = _line_height(st, size)
    tt = st.get('text-transform', 'none')
    tag = el.tag
    explicit_w = 'width' in st and st['width'] != 'auto'
    inner_avail = None if avail_w is None else max(0.0, avail_w - b.mar[1] - b.mar[3] - b.pad[1] - b.pad[3]
                                                   - bw[1] - bw[3])
    cw = _px(st['width'], avail_w or 0.0) if explicit_w else inner_avail
    if 'max-width' in st and cw is not None:
        cw = min(cw, _px(st['max-width'], avail_w or 0.0))
    elif 'max-width' in st and cw is None:
        cw = _px(st['max-width'])
    text = el.text
    if tag == 'input' and el.attrs.get('type', 'text') in ('color', 'text', 'number'):
        text = None
    raw_lines = []
    if text not in (None, ''):
        t = str(text)
        t = t.upper() if tt == 'uppercase' else t.lower() if tt == 'lowercase' else t
        raw_lines = _wrap(t, font, cw)
    text_w = max([font.getlength(l) for l in raw_lines] or [0.0])
    cx = x + b.mar[3] + bw[3] + b.pad[3]
    cy = y + b.mar[0] + bw[0] + b.pad[0]
    flex = st.get('display') == 'flex'
    direction = st.get('flex-direction', 'row') if flex else 'column'
    gap = _px(st.get('gap')) if flex else 0.0
    ty = cy
    content_w = text_w
    if raw_lines:
        ty += lh * len(raw_lines)
    kids = [k for k in el.children]
    if flex and direction == 'row':
        kx = cx
        row_h = 0.0
        for k in kids:
            kb = _layout(k, st, None, kx, ty)
            if getattr(kb, 'hidden', False):
                continue
            b.kids.append(kb)
            kx += kb.mw + gap
            row_h = max(row_h, kb.mh)
        used = (kx - gap - cx) if b.kids else 0.0
        content_w = max(content_w, used)
        kids_h = row_h
    else:
        kids_h = 0.0
        ky = ty
        for k in kids:
            kb = _layout(k, st, cw if cw is not None else None, cx, ky)
            if getattr(kb, 'hidden', False):
                continue
            b.kids.append(kb)
            ky += kb.mh + (gap if flex else 0.0)
            content_w = max(content_w, kb.mw)
        kids_h = (ky - ty - (gap if flex and b.kids else 0.0)) if b.kids else 0.0
    if tag == 'img':
        src = el.attrs.get('src')
        b.image = Image.open(src).convert('RGBA') if src else None
        iw, ih = (b.image.size if b.image else (0, 0))
        w = _px(st.get('width'), avail_w or 0.0, iw)
        h = _px(st.get('height'), 0.0, ih * (w / iw) if iw else ih)
        content_w, kids_h = w, h
    elif tag == 'canvas':
        b.image = el.attrs.get('image')
        content_w, kids_h = (b.image.size if b.image is not None else (0, 0))
    elif tag == 'input':
        kind = el.attrs.get('type', 'text')
        default = {'checkbox': (size, size), 'radio': (size, size), 'range': (size * 8, size)}.get(kind, (size * 10, lh))
        content_w = _px(st.get('width'), avail_w or 0.0, default[0])
        kids_h = _px(st.get('height'), 0.0, default[1])
    width = cw if (explicit_w or (cw is not None and st.get('display', 'block') == 'block' and tag not in
                                  ('span', 'img', 'canvas', 'input', 'b', 'i', 'em', 'strong'))) else content_w
    if width is None:
        width = content_w
    height = _px(st['height'], 0.0) if 'height' in st and st['height'] != 'auto' else \
        (ty - cy) + kids_h
    if 'min-height' in st:
        height = max(height, _px(st['min-height']))
    b.cw, b.ch = width, height
    b.w = width + b.pad[1] + b.pad[3] + bw[1] + bw[3]
    b.h = height + b.pad[0] + b.pad[2] + bw[0] + bw[2]
    b.x, b.y = x + b.mar[3], y + b.mar[0]
    b.mw = b.w + b.mar[1] + b.mar[3]
    b.mh = b.h + b.mar[0] + b.mar[2]
    align = st.get('text-align', 'left')
    col = css_color(st.get('color', '#000000'), (0, 0, 0, 255))
    for i, line in enumerate(raw_lines):
        lw = font.getlength(line)
        lx = cx + (width - lw) / 2 if align == 'center' else cx + width - lw if align == 'right' else cx
        b.lines.append((line, lx, cy + i * lh + (lh - size) / 2, font, col, size))
    if flex:
        _flex_align(b, st, cx, ty, width, kids_h, direction, gap)
    return b


def _shift(b, dx, dy):
    b.x += dx
    b.y += dy
    b.lines = [(t, x + dx, y + dy, f, c, s) for t, x, y, f, c, s in b.lines]
    for k in b.kids:
        _shift(k, dx, dy)


def _flex_align(b, st, cx, cy, width, height, direction, gap):
    ai, jc = st.get('align-items', 'stretch'), st.get('justify-content', 'flex-start')
    if not b.kids:
        return
    if direction == 'row':
        used = sum(k.mw for k in b.kids) + gap * (len(b.kids) - 1)
        free = width - used
        off = free / 2 if jc == 'center' else free if jc == 'flex-end' else 0.0
        step = free / max(1, len(b.kids) - 1) if jc == 'space-between' and len(b.kids) > 1 else 0.0
        for i, k in enumerate(b.kids):
            dy = (height - k.mh) / 2 if ai == 'center' else (height - k.mh) if ai == 'flex-end' else 0.0
            _shift(k, off + step * i, dy)
    else:
        for k in b.kids:
            dx = (width - k.mw) / 2 if ai == 'center' else (width - k.mw) if ai == 'flex-end' else 0.0
            _shift(k, dx, 0.0)


def layout(el, max_width=None):
    """Lay out a tree; returns the root box (its .w x .h is the element's border-box size in px)."""
    return _layout(el, {'color': '#000000', 'font-size': '16px', 'font-family': 'sans-serif'}, max_width, 0.0, 0.0)


# ----------------------------------------------------------------------------------------------- the paint ---

def _rr(d, x, y, w, h, r, fill=None, outline=None, width=0):
    """html2canvas's buildRectPath (a radius clamped to half the side) filled and / or stroked."""
    r = max(0.0, min(r, w / 2, h / 2))
    box = [x, y, x + max(0.0, w), y + max(0.0, h)]
    if r > 0:
        d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=int(round(width)) if outline else 0)
    else:
        d.rectangle(box, fill=fill, outline=outline, width=int(round(width)) if outline else 0)


def _luma(rgba):
    def lin(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgba[:3])
    return math.sqrt(0.299 * r * r + 0.587 * g * g + 0.114 * b * b)


def _paint(img, b, ox=0.0, oy=0.0, ss=1.0):
    if getattr(b, 'hidden', False):
        return
    d = ImageDraw.Draw(img, 'RGBA')
    S = lambda v: v * ss                                           # noqa: E731
    st = b.st
    x, y, w, h = S(b.x - ox), S(b.y - oy), S(b.w), S(b.h)
    rad = S(_px(st.get('border-radius', '0').split()[0], b.w))
    bg = css_color(st.get('background-color') or st.get('background'))
    if bg is not None and bg[3] > 0:
        _rr(d, x, y, w, h, rad, fill=bg)
    sides = {s: _border(st, s) for s in ('top', 'left', 'bottom', 'right')}
    same = len({(round(v[0], 3), v[1], v[2]) for v in sides.values()}) == 1
    if same:
        bw_, bs, bc = sides['top']
        if bw_ > 0 and bs != 'none' and bc is not None and bc[3] > 0:
            k = S(bw_)
            _rr(d, x + k / 2, y + k / 2, w - k, h - k, max(0.0, rad - k / 2), outline=bc, width=k)
    else:
        for side, (a, z) in {'top': ((x, y), (x + w, y)), 'left': ((x, y), (x, y + h)),
                             'bottom': ((x, y + h), (x + w, y + h)), 'right': ((x + w, y), (x + w, y + h))}.items():
            bw_, bs, bc = sides[side]
            if bw_ > 0 and bs != 'none' and bc is not None and bc[3] > 0:
                d.line([a, z], fill=bc, width=max(1, int(round(S(bw_)))))
    el = b.el
    if el.tag == 'input':
        _paint_input(img, d, b, x, y, w, h, ss)
    if el.tag in ('img', 'canvas') and getattr(b, 'image', None) is not None:
        im = b.image.convert('RGBA').resize((max(1, int(round(S(b.cw)))), max(1, int(round(S(b.ch))))),
                                            Image.Resampling.LANCZOS)
        img.alpha_composite(im, (int(round(x + S(b.pad[3]))), int(round(y + S(b.pad[0])))))
        d = ImageDraw.Draw(img, 'RGBA')
    clip = st.get('overflow') in ('hidden', 'auto')                # html2canvas's Clipper: the element's text
    target = Image.new('RGBA', img.size, (0, 0, 0, 0)) if clip else img   # nodes and children cut to its box
    dt = ImageDraw.Draw(target, 'RGBA')
    for text, lx, ly, font, col, size in b.lines:
        f = font.font_variant(size=max(1, int(round(font.size * ss))))
        dt.text((S(lx - ox), S(ly - oy) + S(size) * 0.1), text, font=f, fill=col)
    for k in b.kids:
        _paint(target, k, ox, oy, ss)
    if clip:
        _composite_clipped(img, target, (x, y, x + w, y + h))


def _composite_clipped(img, layer, rect):
    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).rectangle(list(rect), fill=255)
    clipped = Image.new('RGBA', img.size, (0, 0, 0, 0))
    clipped.paste(layer, (0, 0), mask)
    img.alpha_composite(clipped)


def _paint_input(img, d, b, x, y, w, h, ss):
    el, st = b.el, b.st
    kind = el.attrs.get('type', 'text')
    acc = css_color(st.get('accent-color')) if st.get('accent-color', 'auto') != 'auto' else None
    acc = acc or css_color(st.get('color', '#000000'), (0, 0, 0, 255))
    acc_text = (255, 255, 255, 255) if _luma(acc) < 0.5 else (0x11, 0x11, 0x11, 255)
    if kind == 'radio':
        _rr(d, x, y, w, h, h, fill=(255, 255, 255, 255), outline=acc, width=max(1, ss))
        if el.attrs.get('checked'):
            _rr(d, x + 2 * ss, y + 2 * ss, w - 4 * ss, h - 4 * ss, h, fill=acc, outline=acc_text, width=2 * ss)
    elif kind == 'checkbox':
        checked = el.attrs.get('checked')
        _rr(d, x, y, w, h, 2 * ss, fill=acc if checked else (255, 255, 255, 255),
            outline=acc_text if checked else acc, width=max(1, ss))
        if checked:                                                # the engine's bold '✔', drawn as strokes (no
            d.line([(x + w * 0.22, y + h * 0.52), (x + w * 0.42, y + h * 0.74), (x + w * 0.8, y + h * 0.26)],
                   fill=acc_text, width=max(1, int(round(h * 0.14))), joint='curve')   # bundled font has the glyph)
    elif kind == 'range':
        lo, hi = float(el.attrs.get('min', 0)), float(el.attrs.get('max', 100))
        v = float(el.attrs.get('value', (lo + hi) / 2))
        pos = (v - lo) / ((hi - lo) or 1) * (w - h)
        _rr(d, x, y + h / 4, w, h / 2, h / 4, fill=acc_text, outline=acc, width=max(1, ss))
        _rr(d, x, y + h / 4, pos + h / 2, h / 2, h / 4, fill=acc)
        _rr(d, x + pos, y, h, h, h / 2, fill=acc)
    elif kind in ('color', 'text', 'number'):                      # the value, clipped to the field
        fams, size, weight, _lh = _font_parts(st)
        f = font_for(fams, size * ss, weight)
        col = css_color(st.get('color', '#000000'), (0, 0, 0, 255))
        layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((x + b.pad[3] * ss, y + b.pad[0] * ss), str(el.attrs.get('value', '')), font=f,
                                   fill=col)
        _composite_clipped(img, layer, (x, y, x + w, y + h))


def html_to_image(el, max_width=None, supersample=2):
    """html2canvas: the element painted to a transparent RGBA image the size of its border box (px)."""
    b = layout(el, max_width)
    W, H = max(1, int(math.ceil(b.w))), max(1, int(math.ceil(b.h)))
    ss = max(1, int(supersample))
    img = Image.new('RGBA', (W * ss, H * ss), (0, 0, 0, 0))
    _paint(img, b, 0.0, 0.0, float(ss))
    return img.resize((W, H), Image.Resampling.LANCZOS) if ss > 1 else img


def html_mesh(el, frames=None, px_size=PX, name='html_mesh', scene=None, max_width=None, supersample=2, fps=0,
              out_dir=None, double_sided=False):
    """The engine's `new HTMLMesh(element)`: a plane px_size metres per pixel (1 mm), standing up and facing -Y, with
    the painted element as an unlit, transparent image. el: an El, or a function of t (seconds) returning one, which
    is painted on every frame of `frames` (default the scene's range) as the engine's update() repainted it; its
    size is the first frame's. Returns the media family's Screen (its .obj is the plane)."""
    import bpy
    from ..media import screens
    scene = scene or bpy.context.scene
    fn = el if callable(el) else (lambda t, _e=el: _e)
    first = html_to_image(fn(0.0), max_width, supersample)
    W, H = first.size
    if frames is None and not callable(el):
        frames = (scene.frame_start, scene.frame_start)

    def draw(c, t, w, h):
        im = html_to_image(fn(t), max_width, supersample)
        if im.size != (w, h):
            im = im.resize((w, h), Image.Resampling.LANCZOS)
        c.image.paste((0, 0, 0, 0), (0, 0, c.w, c.h))
        c.image.alpha_composite(im)
    scr = screens.make_screen(width=W * px_size, height=H * px_size, px=W, draw=draw, frames=frames, fps=fps,
                              transparent=True, lit=False, double_sided=double_sided, name=name, scene=scene,
                              out_dir=out_dir, strength=1.0)
    scr.obj['eido_html_mesh'] = True
    scr.obj['eido_html_px'] = (W, H)
    return scr


def help():                                                          # noqa: A001 - the engine's HTMLMesh.help()
    """Print (and return) this module's API reference, as HTMLMesh.help() did."""
    msg = __doc__
    print(msg)
    return msg
