"""Judge what gen.py made, in plain Python (numpy + Pillow): the judge package's verdict beside each reference, the
level seams, and a sheet: hillshades (reference and generated at the reference pixel, north up, central 2 km crops,
every level) and wall cross-sections (benches and cliffs read there, not in a hillshade).

    python blender/tests/terrain/layered_rock/judge_fields.py <out_dir> <tag> [<tag> ...]

Per tag: <tag>_verdict_<reference>.json, <tag>_seams.json and <tag>_sheet.png.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from eidoblend.terrain.core import grid as Gd  # noqa: E402
from eidoblend.terrain.core import io as IO  # noqa: E402
from judge import family as F  # noqa: E402
from judge import judge, refs  # noqa: E402


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def shade(h, cell, size=None):
    hs = IO.hillshade(np.asarray(h, np.float64), cell)
    img = Image.fromarray(np.ascontiguousarray(IO.to_u8(hs)[::-1]))          # north up
    if size:
        img = img.resize((size, size), Image.LANCZOS)
    return img.convert('RGB')


def levels_of(path):
    d = np.load(path)
    out = []
    i = 0
    while f'L{i}_window' in d.files:
        w = d[f'L{i}_window']
        f = {k[len(f'L{i}_'):]: d[k] for k in d.files if k.startswith(f'L{i}_') and not k.endswith('_window')}
        out.append(dict(x0=w[0], y0=w[1], side=w[2], cell=w[3], n=int(w[4]), fields=f))
        i += 1
    return out


def seams(levels):
    """Each child level against its parent (the design's seam numbers)."""
    rows = []
    for c, p in zip(levels[1:], levels[:-1]):
        i0 = int(round((c['x0'] - p['x0']) / p['cell']))
        j0 = int(round((c['y0'] - p['y0']) / p['cell']))
        m = int(round(c['side'] / p['cell']))
        up = Gd.crop_upsample2(p['fields']['h'], i0, j0, m, 'catmull').astype(np.float64)
        hc = np.asarray(c['fields']['h'], np.float64)
        ring = np.zeros(hc.shape, bool)
        ring[0, :] = ring[-1, :] = ring[:, 0] = ring[:, -1] = True
        dh = float(np.abs(hc - up)[ring].max())
        sc = Gd.slope_deg(hc, c['cell'])
        sp = Gd.slope_deg(up, c['cell'])
        ring2 = np.zeros(hc.shape, bool)
        ring2[1, 1:-1] = ring2[-2, 1:-1] = ring2[1:-1, 1] = ring2[1:-1, -2] = True
        jump = float(np.abs(sc - sp)[ring | ring2].max())
        rows.append(dict(child_cell_m=float(c['cell']), edge_max_dh_m=dh, edge_slope_jump_deg=jump,
                         ok=dh <= 0.05 and jump <= 3.0))
    return rows


def sections(h, cell, n=4):
    """Wall cross-sections across the trunk (the judge's trunk and stations): [(offsets m, heights m)]."""
    area, recv, _ = F.drainage(h, cell)
    path = F.trunk(h, cell, area, recv)
    out = []
    if not path:
        return out
    hs = F.blur(h, 0.7)
    for c, d in F.stations(path, n, 0.2, 0.8, half_window=max(3, int(100 / cell))):
        t, z = F.section(hs, cell, c, d, 0.45 * h.shape[0] * cell)
        out.append((t, z))
    return out


def profile_panel(secs_ref, secs_gen, W, H, title):
    """Cross-sections drawn at true scale (1:1, metres), reference in white, generated in orange."""
    img = Image.new('RGB', (W, H), (16, 16, 16))
    dr = ImageDraw.Draw(img)
    dr.text((6, 4), title, fill=(230, 230, 230), font=font(14))
    allz = [z for _t, z in secs_ref + secs_gen if len(z)]
    if not allz:
        return img
    rows = max(len(secs_ref), len(secs_gen), 1)
    band = (H - 24) / rows
    span_t = max(float(np.ptp(t)) for t, _z in secs_ref + secs_gen)
    for k in range(rows):
        y0 = 24 + k * band
        zr = [z for z in ([secs_ref[k][1]] if k < len(secs_ref) else []) + ([secs_gen[k][1]] if k < len(secs_gen)
                                                                               else [])]
        lo = min(float(np.nanmin(z)) for z in zr)
        hi = max(float(np.nanmax(z)) for z in zr)
        sx = (W - 12) / span_t
        sz = min(sx, (band - 8) / max(hi - lo, 1.0))        # true scale when it fits
        for secs, colr in ((secs_ref, (235, 235, 235)), (secs_gen, (255, 150, 40))):
            if k >= len(secs):
                continue
            t, z = secs[k]
            pts = [(6 + (tt - t.min()) * sx, y0 + band - 4 - (zz - lo) * sz) for tt, zz in zip(t, z) if np.isfinite(zz)]
            if len(pts) > 1:
                dr.line(pts, fill=colr, width=2)
        dr.text((8, y0 + 2), f'{hi - lo:.0f} m relief, {span_t / 1000:.1f} km wide, '
                             f'vertical x{sx / sz if sz else 1:.1f}', fill=(160, 160, 160), font=font(11))
    return img


def sheet(tag, out_dir, ref_names, levels, verdict_lines):
    d = np.load(os.path.join(out_dir, tag + '.npz'))
    h = np.asarray(d['h'], np.float64)
    cell = float(d['cell'])
    W = 520
    tiles = []
    ref = refs.load(ref_names[0]) if ref_names else None
    if ref is not None:
        gen_px = Gd.resample_box(h, cell, ref.pixel) if ref.pixel > cell * 1.0001 else h
        tiles += [(f'reference: {ref.title} ({ref.pixel:g} m)', shade(ref.h, ref.pixel, W)),
                  (f'generated main level at {ref.pixel:g} m', shade(gen_px, ref.pixel, W))]
        n_r = int(round(2000.0 / ref.pixel))
        n_g = int(round(2000.0 / cell))
        cr = ref.h[ref.h.shape[0] // 2 - n_r // 2:ref.h.shape[0] // 2 + n_r // 2,
                   ref.h.shape[1] // 2 - n_r // 2:ref.h.shape[1] // 2 + n_r // 2]
        cg = h[h.shape[0] // 2 - n_g // 2:h.shape[0] // 2 + n_g // 2, h.shape[1] // 2 - n_g // 2:h.shape[1] // 2 + n_g // 2]
        tiles += [('reference, central 2 km', shade(cr, ref.pixel, W)),
                  (f'generated, central 2 km at {cell:.3g} m', shade(cg, cell, W))]
        try:
            pr = profile_panel(sections(ref.h, ref.pixel), sections(gen_px, ref.pixel), 2 * W + 8, W,
                               'cross-sections across the trunk at 20/40/60/80 % of its length: reference white, '
                               'generated orange')
            tiles.append(('', pr))
        except Exception as e:                                         # noqa: BLE001 - the sheet goes on
            print('[layered.judge] sections:', e)
    for i, lv in enumerate(levels):
        tiles.append((f"level {i}: {lv['side']:g} m at {lv['cell']:.3g} m", shade(lv['fields']['h'], lv['cell'], W)))
    cols = 4
    head = 26 + 18 * len(verdict_lines)
    # lay out: wide tiles take two columns
    pos, x, y, rowh = [], 0, 0, 0
    for label, t in tiles:
        span = 2 if t.size[0] > W + 4 else 1
        if x + span > cols:
            x, y = 0, y + 1
        pos.append((x, y))
        x += span
    rows = y + 1
    img = Image.new('RGB', (cols * (W + 8) + 8, head + rows * (W + 30) + 8), (24, 24, 24))
    dr = ImageDraw.Draw(img)
    f = font(15)
    yy = 6
    dr.text((8, yy), tag, fill=(255, 255, 255), font=font(18))
    yy += 24
    for ln in verdict_lines:
        dr.text((8, yy), ln, fill=(220, 220, 220), font=f)
        yy += 18
    for (label, t), (cx, cy) in zip(tiles, pos):
        x = 8 + cx * (W + 8)
        y = head + cy * (W + 30)
        dr.text((x, y), label, fill=(230, 230, 230), font=f)
        img.paste(t, (x, y + 22))
    path = os.path.join(out_dir, tag + '_sheet.png')
    img.save(path)
    return path


def verdict_lines(v, ref_name):
    lines = [f"verdict vs {ref_name}: {'PASS' if v.passed else 'FAIL'}  ({len(v.failures)} failures)"]
    row = []
    for r in v.rows:
        if r['passed'] is None:
            continue
        g, rf = r['gen'], r['ref']
        txt = (f"{'ok' if r['passed'] else 'FAIL'} {r['metric']} {g:.3g}/{rf:.3g}" if isinstance(g, (int, float))
               and isinstance(rf, (int, float)) else f"{'ok' if r['passed'] else 'FAIL'} {r['metric']}")
        row.append(txt)
        if len(row) == 5:
            lines.append('   '.join(row))
            row = []
    if row:
        lines.append('   '.join(row))
    return lines


def main():
    out_dir, tags = sys.argv[1], sys.argv[2:]
    for tag in tags:
        rec = json.load(open(os.path.join(out_dir, tag + '_record.json'), encoding='utf-8'))
        recipe = rec['item']['recipe']
        ref_names = rec['item'].get('references') or refs.RECIPE_REFERENCES.get(recipe, [])
        field = os.path.join(out_dir, tag + '.npz')
        lines = []
        for rn in ref_names:
            v = judge(field, rn, label=tag)
            v.save(os.path.join(out_dir, f'{tag}_verdict_{rn}.json'))
            print(v.table(), flush=True)
            lines += verdict_lines(v, rn)
        crop = os.path.join(out_dir, tag + '_crop.npz')
        for rn in (rec['item'].get('crop_references') or []):
            if os.path.exists(crop):
                v = judge(crop, rn, label=tag + '_crop')
                v.save(os.path.join(out_dir, f'{tag}_crop_verdict_{rn}.json'))
                print(v.table(), flush=True)
                lines += [ln.replace('verdict vs', 'crop verdict vs') for ln in verdict_lines(v, rn)]
        levels = levels_of(os.path.join(out_dir, tag + '_levels.npz'))
        sm = seams(levels)
        json.dump(sm, open(os.path.join(out_dir, tag + '_seams.json'), 'w'), indent=1)
        lines.append('seams: ' + ', '.join(f"{r['child_cell_m']:.3g} m |dh| {r['edge_max_dh_m']:.3f} jump "
                                          f"{r['edge_slope_jump_deg']:.2f}" for r in sm))
        flog = [x for x in (rec['run'].get('shared') or {}).get('fluvial_log', [])]
        lines.append(f"run {rec['seconds']} s: " + ', '.join(f"L{i} {lv.get('seconds')}" for i, lv in
                                                             enumerate(rec['run'].get('levels', [])))
                     + '; passes: ' + ', '.join(f"{x.get('role')} {x.get('steps')}x{x.get('dt_yr')}yr"
                                                for x in flog))
        print(sheet(tag, out_dir, ref_names, levels, lines))


main()
