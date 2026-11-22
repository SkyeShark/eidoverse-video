"""The look package's boards (PORT_PLAN.md 8.2 row P18; SURFACING_DESIGN.md section 6): per view, the surfacing
judge's own board row with Blender's frame as 'before' and the port's as 'after' (surfacing_judge/board.view_row:
photograph | Blender | port | the port's layer map, two places enlarged 2x, Blender beside port, the judge's numbers
a line each), and under it a row of this package's: Blender's layer map | the port's | where the two frames differ
(dE per 32 px block, port against Blender) | the port's frame through this edition's own tone curve (three's AgX),
then the two places that differ most, enlarged 2x, Blender beside port.

    python -B eidoverse/terrain/tests/surface_look/boards.py --state <label> [--ref final2] [--recipes a,b]
           [--no-compare]
    (system Python: numpy and Pillow; the Blender edition at $EIDO_BLENDER_EDITION, only read)

--ref names any state of Blender's review: the crater's check is --ref v5 (SURFACING_DESIGN.md 3.8: the walls and
the rocks unchanged or better beside impact_crater_v5), with --no-compare (measures.py's lines are against final2).

Reads tests/out/surface_look/states/<label>/ (develop.py's pictures), baseline_<label>.json and compare_<label>.json
(measures.py), and Blender's out/surfacing/review/<recipe>/<view>_<ref>.png, _layers.png and baseline_<ref>.json.
Writes tests/out/surface_look/boards/<recipe>_<ref>_<label>.jpg.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import measures as MS  # noqa: E402

OUT = MS.OUT


def heat(de, shape, vmax=20.0):
    """A dE grid (rows, cols) as a picture of `shape` (H, W): black 0, red at vmax, grey where not measured."""
    H, W = shape
    rows, cols = de.shape
    img = np.full((H, W, 3), 60, np.uint8)
    for j in range(rows):
        for i in range(cols):
            x = de[j, i]
            if not np.isfinite(x):
                continue
            t = float(np.clip(x / vmax, 0.0, 1.0))
            img[j * 32:(j + 1) * 32, i * 32:(i + 1) * 32] = (int(255 * t), int(255 * max(0.0, t - 0.6) * 2.5), int(40 * (1 - t)))
    return img


def compare_line(c):
    if not c or 'error' in c:
        return None
    parts = []
    g = c.get('ground_lab')
    if g:
        parts.append(f"ground dE {g['delta_e']:.1f} (port L* {g['port'][0]:.1f} a* {g['port'][1]:.1f} b* {g['port'][2]:.1f}; "
                     f"Blender {g['blender'][0]:.1f} {g['blender'][1]:.1f} {g['blender'][2]:.1f})")
    b = c.get('block_delta_e')
    if b:
        parts.append(f"blocks dE median {b['median']:.1f}, p90 {b['p90']:.1f}")
    if c.get('dominant_layer_agreement') is not None:
        parts.append(f"same dominant layer on {100 * c['dominant_layer_agreement']:.0f} % of the ground")
    fl = c.get('frame_L')
    if fl:
        parts.append(f"frame L* {fl['port']:.1f} vs {fl['blender']:.1f}")
    lr = c.get('linear_ratio')
    if lr:
        parts.append(f"light x{lr['ground']:.2f} (sunlit x{lr['brightest_quarter']:.2f}, shade x{lr['darkest_quarter']:.2f})")
    lm = c.get('light_matched')
    if lm:
        parts.append(f"at Blender's light: ground dE {lm['ground_delta_e']:.1f}, blocks median {lm['block_median']:.1f}, "
                     f"p90 {lm['block_p90']:.1f}")
    return 'port vs Blender: ' + '; '.join(parts)


def extra_row(recipe, v, label, ref, S, LY, M, BD, cmp, n_layers):
    from PIL import Image, ImageDraw
    TW, TH, CW, CH = BD.TW, BD.TH, BD.CW, BD.CH
    tiles = []
    for st, name in ((ref, 'Blender'), (label, 'port')):
        lp = S.layers(recipe, v['name'], st)
        if lp:
            w, ground, _ws, _i = LY.decode_layer_map(M.load_rgba(lp), n_layers)
            tiles.append((Image.fromarray(BD.layer_picture(w, ground)).resize((TW, TH), Image.NEAREST),
                          f'layer map: {name}'))
        else:
            tiles.append((BD._blank(f'no layer map ({name})'), f'layer map: {name}'))
    pa, pb = S.render(recipe, v['name'], label), S.render(recipe, v['name'], ref)
    a, b = M.load_rgb(pa), M.load_rgb(pb)
    ground = np.ones(a.shape[:2], bool)
    la, lb = S.layers(recipe, v['name'], label), S.layers(recipe, v['name'], ref)
    if la and lb:
        _w, ga, _s, _i = LY.decode_layer_map(M.load_rgba(la), n_layers)
        _w, gb, _s, _i = LY.decode_layer_map(M.load_rgba(lb), n_layers)
        ground = ga & gb
    de = np.linalg.norm(MS.block_lab(a, ground) - MS.block_lab(b, ground), axis=-1)
    tiles.append((Image.fromarray(heat(de, a.shape[:2])).resize((TW, TH), Image.NEAREST),
                  'dE per 32 px block, port vs Blender (red 20)'))
    three = os.path.join(os.path.dirname(pa), v['name'] + '_agx3.png')
    tiles.append((Image.open(three).convert('RGB').resize((TW, TH), Image.LANCZOS) if os.path.exists(three)
                  else BD._blank('no three AgX frame'), "port through three's AgX (the edition's own curve)"))
    # the two most different places, each 240 x 135 render pixels round its worst block, away from each other
    ok = np.isfinite(de)
    boxes = []
    if ok.any():
        order = np.argsort(np.where(ok, de, -1).ravel())[::-1]
        for idx in order:
            j, i = np.unravel_index(idx, de.shape)
            if not ok[j, i]:
                break
            cx, cy = i * 32 + 16, j * 32 + 16
            x0 = int(min(max(cx - CW // 2, 0), 960 - CW))
            y0 = int(min(max(cy - CH // 2, 0), 540 - CH))
            if all(abs(x0 - q[0]) >= CW or abs(y0 - q[1]) >= CH for q in boxes):
                boxes.append((x0, y0, x0 + CW, y0 + CH, float(de[j, i])))
            if len(boxes) == 2:
                break
    font, small = BD._font(16), BD._font(13)
    head, gap = 44, 22
    row = Image.new('RGB', (4 * TW, head + TH + gap + 2 * CH), BD.BG)
    d = ImageDraw.Draw(row)
    line = compare_line((cmp.get(f"{recipe}/{v['name']}") or {}).get('compare'))
    if line:
        d.text((6, 4), line[:240], fill=(220, 200, 150), font=small)
    for k, (im, lab) in enumerate(tiles):
        row.paste(im, (k * TW, head))
        d.text((k * TW + 6, 24), lab, fill=(205, 205, 205), font=small)
    fa, fb = Image.open(pa).convert('RGB'), Image.open(pb).convert('RGB')
    for k, (x0, y0, x1, y1, e) in enumerate(boxes):
        for j, (full, who) in enumerate(((fb, 'Blender'), (fa, 'port'))):
            X, Y = (2 * k + j) * TW, head + TH + gap
            row.paste(full.crop((x0, y0, x1, y1)).resize((2 * CW, 2 * CH), Image.NEAREST), (X, Y))
            d.text((X + 6, Y - 18), f'{who}, 2x: pixels {x0}-{x1}, {y0}-{y1} (block dE {e:.0f})', fill=(190, 190, 190), font=small)
        d.rectangle([3 * TW + x0 // 2, head + y0 // 2, 3 * TW + x1 // 2, head + y1 // 2], outline=(255, 90, 90), width=2)
    return row, [b[:4] for b in boxes]


def main(argv):
    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    label = opt('--state', 'port')
    ref = opt('--ref', 'final2')
    only = set((opt('--recipes') or '').split(',')) - {''}
    MS.edition()
    BL, LY, M, S, V = MS.judge(os.path.join(OUT, 'states'))
    from surfacing_judge import board as BD
    from PIL import Image
    cmp_p = os.path.join(OUT, f'compare_{label}.json')
    # measures.py's port-vs-Blender lines are against its --ref (final2): left out for a board against another state
    cmp = json.load(open(cmp_p, encoding='utf-8')) if os.path.exists(cmp_p) and '--no-compare' not in argv else {}
    blender_out = BD.OUT
    os.makedirs(os.path.join(OUT, 'boards'), exist_ok=True)
    crops = {}
    plan = V.load()
    for recipe, rec in plan.items():
        if only and recipe not in only:
            continue
        pal = LY.palette(recipe)
        rows = []
        for v in rec['views']:
            if not S.render(recipe, v['name'], label) or not S.render(recipe, v['name'], ref):
                continue
            BD.OUT = blender_out
            nb = BD._numbers(ref, recipe, v['name'])
            BD.OUT = OUT
            npo = BD._numbers(label, recipe, v['name'])
            BD.OUT = blender_out
            rows.append(BD.view_row(recipe, v, ref, label, None, [x for x in (nb, npo) if x]))
            r2, boxes = extra_row(recipe, v, label, ref, S, LY, M, BD, cmp, len(pal['layers']))
            rows.append(r2)
            crops[f"{recipe}/{v['name']}"] = dict(judge=[list(b) for b in BD.pick_crops(v, None, None)] if v.get('crops') else None,
                                                   most_different=[list(b) for b in boxes])
        if not rows:
            continue
        sheet = Image.new('RGB', (rows[0].width, sum(im.height for im in rows)), BD.BG)
        y = 0
        for im in rows:
            sheet.paste(im, (0, y))
            y += im.height
        p = os.path.join(OUT, 'boards', f'{recipe}_{ref}_{label}.jpg')
        sheet.save(p, quality=88)
        print('[boards]', p.replace('\\', '/'), len(rows) // 2, 'views', flush=True)
    # one crop file a label, keyed by reference: a board against v5 keeps the final2 boards' crops
    cp = os.path.join(OUT, 'boards', f'crops_{label}.json')
    try:
        with open(cp, encoding='utf-8') as f:
            kept = json.load(f)
    except (OSError, ValueError):
        kept = {}
    if not all(isinstance(x, dict) and 'most_different' not in x for x in kept.values()):
        kept = {}                                      # the older layout (one reference): written again in full
    kept[ref] = {**kept.get(ref, {}), **crops}
    with open(cp, 'w', encoding='utf-8') as f:
        json.dump(kept, f, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
