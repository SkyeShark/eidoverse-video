"""The compare sheet (DESIGN.md section 10 item 5): the reference's row above the generated rows, each the three
probe views (top-down hillshade, 45-degree aerial, eye level at 1.7 m) with its numbers printed beside it, every
banded number green (in band) or red (out) with the band; the textured and hero eye views of a built terrain in a
row of their own under its clay row. System Python (Pillow).

    compose(out_png, reference, verdicts, render_dir, title=None)
        verdicts: [Verdict, ...] in row order (their labels name the renders: <render_dir>/<label>_<view>.png)
"""
import os
import site
import sys

sys.path.append(site.getusersitepackages())
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from .bands import _fmt  # noqa: E402
from .refs import REFERENCE_DIR  # noqa: E402

ROW_H = 270
GAP = 8
LABEL_W = 250
NUM_W = 430
BG = (24, 25, 27)
INK = (232, 232, 228)
DIM = (150, 152, 156)
GOOD = (120, 200, 120)
BAD = (240, 110, 100)
GOLD = (240, 200, 120)
VIEWS = (('top_hillshade', ROW_H), ('aerial_45deg', ROW_H * 16 // 9), ('eye_1p7m', ROW_H * 16 // 9))
EXTRA = (('hero_eye', 'hero levels, eye 1.7 m'), ('tex_aerial', 'textured aerial (with its context rings)'),
         ('tex_eye', 'textured eye'))


def font(size):
    for f in ('segoeui.ttf', 'arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap(d, text, f, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _paste(sheet, d, path, x, y, w, fs):
    if path and os.path.exists(path):
        sheet.paste(Image.open(path).convert('RGB').resize((w, ROW_H), Image.LANCZOS), (x, y))
    else:
        d.rectangle([x, y, x + w - 1, y + ROW_H - 1], outline=(70, 70, 70))
        d.text((x + 10, y + 10), 'not rendered', font=fs, fill=DIM)


def _numbers(d, v, x, y, fs, which):
    """The banded numbers of a verdict: which = 'ref' (the reference's) or 'gen' (generated, with verdicts)."""
    rows = [r for r in v.rows if r['kind'] != 'info']
    lh = fs.size + 3
    cols = 2 if len(rows) * lh > ROW_H - 6 else 1
    per = (len(rows) + cols - 1) // cols
    cw = NUM_W // cols
    for k, r in enumerate(rows):
        cx, cy = x + (k // per) * cw, y + 3 + (k % per) * lh
        if which == 'ref':
            d.text((cx, cy), f"{r['metric'][:20]}", font=fs, fill=DIM)
            d.text((cx + cw - 70, cy), _fmt(r['ref']), font=fs, fill=INK)
        else:
            col = GOOD if r['passed'] else (BAD if r['passed'] is False else DIM)
            d.text((cx, cy), f"{r['metric'][:20]}", font=fs, fill=col)
            d.text((cx + cw - 70, cy), _fmt(r['gen']), font=fs, fill=col)


def compose(out_png, reference, verdicts, render_dir, title=None, ref_render_dir=None):
    ref_render_dir = ref_render_dir or os.path.join(REFERENCE_DIR, 'renders')
    extra_rows = [v for v in verdicts if any(os.path.exists(os.path.join(render_dir, f'{v.label}_{e}.png'))
                                             for e, _ in EXTRA)]
    n_rows = 1 + len(verdicts) + len(extra_rows)
    W = LABEL_W + sum(w for _, w in VIEWS) + NUM_W + GAP * (len(VIEWS) + 2)
    head = 70
    foot_lines = []
    for v in verdicts:
        foot_lines += [f'{v.label}: ' + n for n in v.notes]
        foot_lines += [f'{v.label} FAIL ' + f for f in v.failures]
    fs = font(13)
    tmp = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    foot = []
    for ln in foot_lines:
        foot += wrap(tmp, ln, fs, W - 2 * GAP)
    H = head + n_rows * (ROW_H + GAP) + GAP + len(foot) * (fs.size + 4) + 10
    sheet = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(sheet)
    ft, fb = font(24), font(16)
    v0 = verdicts[0] if verdicts else None
    n_pass = sum(1 for v in verdicts if v.passed)
    d.text((GAP + 4, 10), title or f'{reference.title} ({reference.family}): {n_pass} of {len(verdicts)} pass',
           font=ft, fill=INK)
    if v0 is not None:
        d.text((GAP + 4, 42), f'numbers at {v0.pixel:g} m pixels over {v0.extent / 1000:g} km; grey clay (albedo '
                              f'0.18) under make_sky daylight, the references\' own rig; green in band, red out',
               font=fs, fill=DIM)
    x = LABEL_W + GAP
    for (kind, w), lab in zip(VIEWS, ('top-down hillshade, north up', '45-degree aerial', 'eye level 1.7 m')):
        d.text((x + 2, head - 18), lab, font=fs, fill=DIM)
        x += w + GAP
    d.text((x + 2, head - 18), 'numbers (band in the JSON)', font=fs, fill=DIM)

    def row_y(i):
        return head + i * (ROW_H + GAP)
    # the reference
    y = row_y(0)
    m = reference.meta
    lines = [(reference.title, fb, INK), (m.get('landform', ''), fb, GOLD),
             (f"REFERENCE: {reference.extent / 1000:g} km, {reference.pixel:g} m px", fs, DIM)]
    ty = y + 6
    for t, f, c in lines:
        for ln in wrap(d, t, f, LABEL_W - 16):
            d.text((GAP + 4, ty), ln, font=f, fill=c)
            ty += f.size + 5
    x = LABEL_W + GAP
    for kind, w in VIEWS:
        _paste(sheet, d, os.path.join(ref_render_dir, f'{reference.name}_{kind}.png'), x, y, w, fs)
        x += w + GAP
    if v0 is not None:
        _numbers(d, v0, x, y, fs, 'ref')
    # the generated rows
    i = 1
    for v in verdicts:
        y = row_y(i)
        ok = v.passed
        lines = [(v.label or 'generated', fb, INK),
                 ('PASS' if ok else 'FAIL', font(22), GOOD if ok else BAD),
                 (f'{sum(1 for r in v.judged if r["passed"])} of {len(v.judged)} bands', fs, DIM)]
        ty = y + 6
        for t, f, c in lines:
            for ln in wrap(d, t, f, LABEL_W - 16):
                d.text((GAP + 4, ty), ln, font=f, fill=c)
                ty += f.size + 5
        x = LABEL_W + GAP
        for kind, w in VIEWS:
            _paste(sheet, d, os.path.join(render_dir, f'{v.label}_{kind}.png'), x, y, w, fs)
            x += w + GAP
        _numbers(d, v, x, y, fs, 'gen')
        i += 1
        if v in extra_rows:
            y = row_y(i)
            d.text((GAP + 4, y + 6), f'{v.label}: built terrain', font=fb, fill=INK)
            x = LABEL_W + GAP
            for e, lab in EXTRA:                       # only the views that were rendered
                p = os.path.join(render_dir, f'{v.label}_{e}.png')
                if not os.path.exists(p):
                    continue
                ww = min(ROW_H * 16 // 9, W - x - GAP)
                _paste(sheet, d, p, x, y, ww, fs)
                d.text((x + 6, y + ROW_H - 20), lab, font=fs, fill=INK)
                x += ww + GAP
            i += 1
    ty = head + n_rows * (ROW_H + GAP) + GAP
    for ln in foot:
        d.text((GAP + 4, ty), ln, font=fs, fill=BAD if ' FAIL ' in ln else DIM)
        ty += fs.size + 4
    os.makedirs(os.path.dirname(os.path.abspath(out_png)) or '.', exist_ok=True)
    sheet.save(out_png)
    return out_png
