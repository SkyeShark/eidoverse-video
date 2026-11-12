"""Package 9's recipe loop in one command (system Python; Blender runs through a GPU slot):

    python blender/tests/terrain/volcanoes_craters/vc.py gen --recipe stratovolcano --seeds 1,2 --tag r1 \\
           [--params '{"age_kyr": 200}'] [--stage-params '{"volcano_age": {"K": 3e-6}}'] [--focus x,y]
    python blender/tests/terrain/volcanoes_craters/vc.py judge <tag> [<tag> ...]

gen writes out/volcanoes_craters/gen/job_<tag>.json, runs gen.py in Blender (judge/run.py's slot runner: heavy.sh,
then heavy2.sh, heavy3.sh, retrying every 60 s while all are busy), then judges every item. judge measures a saved
field against its reference with the judge package (judge.judge: the generic numbers and bands, the family's),
writes <tag>_verdict.json, the level seams (<tag>_seams.json: |dh| at each child's edge, the slope jump) and
<tag>_sheet.png: the reference's hillshade beside the generated main level's at the reference pixel (north up), a
crop of each round the landform at full resolution, every level's hillshade, and the verdict's rows.
"""
import argparse
import json
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
from judge import judge, refs  # noqa: E402

OUT = os.path.normpath(os.path.join(TN, 'out', 'volcanoes_craters', 'gen'))
REF_OF = {'stratovolcano': 'mount_fuji', 'caldera': 'crater_lake', 'cinder_cones': 'sp_crater',
          'impact_crater': 'meteor_crater'}
# the crop round the landform on the sheet: (half-width m, centre in the reference's local metres)
CROP = {'mount_fuji': (6000.0, (300.0, 260.0)), 'crater_lake': (3500.0, (95.0, 9.0)),
        'meteor_crater': (900.0, (30.0, 0.0)), 'sp_crater': (1500.0, (-480.0, 1950.0))}


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def shade(h, cell, size=None, water=None):
    hs = IO.hillshade(np.asarray(h, np.float64), cell)
    rgb = np.repeat(IO.to_u8(hs)[..., None], 3, axis=2)
    if water is not None:
        w = np.asarray(water) > 0.01
        rgb[w] = (rgb[w] * np.array([0.35, 0.5, 0.75])).astype(np.uint8)
    img = Image.fromarray(np.ascontiguousarray(rgb[::-1]))                      # north up
    if size:
        img = img.resize((size, size), Image.LANCZOS)
    return img


def crop(a, cell, half_m, centre, extent):
    """The square of half-width half_m about a point (local metres of a tile centred on 0) of a row-0-south array."""
    n = a.shape[0]
    ci = int(round((centre[0] + extent / 2.0) / cell))
    cj = int(round((centre[1] + extent / 2.0) / cell))
    k = int(round(half_m / cell))
    return a[max(cj - k, 0):cj + k, max(ci - k, 0):ci + k]


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
    """Each child level against its parent: |dh| on the child's edge ring and the slope jump there (design 3's
    numbers: <= 0.05 m, <= 3 degrees)."""
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
        sc, sp = Gd.slope_deg(hc, c['cell']), Gd.slope_deg(up, c['cell'])
        ring2 = np.zeros(hc.shape, bool)
        ring2[1, 1:-1] = ring2[-2, 1:-1] = ring2[1:-1, 1] = ring2[1:-1, -2] = True
        jump = float(np.abs(sc - sp)[ring | ring2].max())
        rows.append(dict(child_cell_m=float(c['cell']), edge_max_dh_m=dh, edge_slope_jump_deg=jump,
                         ok=dh <= 0.05 and jump <= 3.0))
    return rows


def verdict_lines(v):
    lines = [f"verdict vs {v.reference}: {'PASS' if v.passed else 'FAIL'} ({len(v.failures)} failures)"]
    for r in v.rows:
        if r['passed'] is None:
            continue
        g, f = r['gen'], r['ref']
        if isinstance(g, (int, float)) and isinstance(f, (int, float)):
            lines.append(f"{'PASS' if r['passed'] else 'FAIL'}  {r['metric']}: gen {g:.4g}  ref {f:.4g}  band "
                         f"{r['band']}")
        else:
            lines.append(f"{'PASS' if r['passed'] else 'FAIL'}  {r['metric']}: gen {g}  ref {f}")
    info = [r for r in v.rows if r['kind'] == 'info' and isinstance(r['gen'], (int, float))
            and isinstance(r['ref'], (int, float))]
    if info:
        lines.append('also: ' + ', '.join(f"{r['metric']} {r['gen']:.3g} ({r['ref']:.3g})" for r in info[:8]))
    return lines


def sheet(tag, ref, levels, lines, out_dir):
    d = np.load(os.path.join(out_dir, tag + '.npz'))
    h = np.asarray(d['h'], np.float64)
    cell = float(d['cell'])
    water = np.asarray(d['water']) if 'water' in d.files else None
    W = 520
    rw = ref.water if ref.water is not None else None
    rmask = ((rw >= 128) & (rw < 255)) if rw is not None else None
    gen_px = Gd.resample_box(h, cell, ref.pixel) if ref.pixel > cell * 1.0001 else h
    gw = Gd.resample_box(water, cell, ref.pixel) if (water is not None and ref.pixel > cell * 1.0001) else water
    tiles = [(f'reference: {ref.title} ({ref.pixel:g} m)', shade(ref.h, ref.pixel, W, rmask)),
             (f'generated main level at {ref.pixel:g} m', shade(gen_px, ref.pixel, W, gw))]
    half, c = CROP.get(ref.name, (0.15 * ref.extent, (0.0, 0.0)))
    tiles += [(f'reference, {2 * half / 1000:g} km round the landform',
               shade(crop(ref.h, ref.pixel, half, c, ref.extent), ref.pixel, W)),
              (f'generated, {2 * half / 1000:g} km round the vent at {cell:.3g} m',
               shade(crop(h, cell, half, (0.0, 0.0), h.shape[0] * cell), cell, W))]
    for i, lv in enumerate(levels):
        tiles.append((f"level {i}: {lv['side'] / 1000:g} km at {lv['cell']:.3g} m",
                      shade(lv['fields']['h'], lv['cell'], W, lv['fields'].get('water'))))
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    head = 28 + 17 * len(lines)
    img = Image.new('RGB', (cols * (W + 8) + 8, head + rows * (W + 30) + 8), (24, 24, 24))
    dr = ImageDraw.Draw(img)
    f = font(14)
    dr.text((8, 6), tag, fill=(255, 255, 255), font=font(18))
    y = 30
    for ln in lines:
        dr.text((8, y), ln, fill=(220, 220, 220), font=f)
        y += 17
    for k, (label, t) in enumerate(tiles):
        x = 8 + (k % cols) * (W + 8)
        yy = head + (k // cols) * (W + 30)
        dr.text((x, yy), label, fill=(230, 230, 230), font=f)
        img.paste(t, (x, yy + 22))
    path = os.path.join(out_dir, tag + '_sheet.png')
    img.save(path)
    return path


def judge_tag(tag, out_dir=OUT):
    rec = json.load(open(os.path.join(out_dir, tag + '_record.json'), encoding='utf-8'))
    recipe = rec['item']['recipe']
    ref = refs.load(rec['item'].get('reference') or REF_OF[recipe])
    v = judge(os.path.join(out_dir, tag + '.npz'), ref, label=tag)
    v.save(os.path.join(out_dir, tag + '_verdict.json'))
    print(v.table(), flush=True)
    levels = levels_of(os.path.join(out_dir, tag + '_levels.npz'))
    sm = seams(levels)
    json.dump(sm, open(os.path.join(out_dir, tag + '_seams.json'), 'w'), indent=1)
    lines = verdict_lines(v)
    if sm:
        lines.append('seams: ' + ', '.join(f"{r['child_cell_m']:.3g} m |dh| {r['edge_max_dh_m']:.3f} jump "
                                          f"{r['edge_slope_jump_deg']:.2f}" for r in sm))
    lines.append(f"run {rec['seconds']} s: " + ', '.join(f"L{i} {lv.get('seconds')}" for i, lv in
                                                         enumerate(rec['run'].get('levels', []))))
    print(sheet(tag, ref, levels, lines, out_dir), flush=True)
    return v


def gen(a):
    from judge.run import run_blender
    os.makedirs(OUT, exist_ok=True)
    items = []
    for s in [int(v) for v in a.seeds.split(',') if v]:
        it = dict(tag=f'{a.tag}_{a.recipe}_s{s}', recipe=a.recipe, seed=s, params=json.loads(a.params or '{}'),
                  stage_params=json.loads(a.stage_params or '{}'), resolution=a.resolution)
        if a.focus:
            it['focus'] = [float(v) for v in a.focus.split(',')]
        if a.size:
            it['size'] = float(a.size)
        items.append(it)
    job = dict(out_dir=OUT, items=items)
    path = os.path.join(OUT, f'job_{a.tag}_{a.recipe}.json')
    json.dump(job, open(path, 'w', encoding='utf-8'), indent=1)
    log = os.path.join(OUT, f'job_{a.tag}_{a.recipe}.log')
    rc, slot = run_blender(os.path.join(HERE, 'gen.py'), ['--job', path], log)
    print(f'[vc] Blender rc={rc} ({slot}); log {log}', flush=True)
    tail = open(log, encoding='utf-8', errors='replace').read().splitlines()
    print('\n'.join(ln for ln in tail if 'terrain.' in ln or 'volc.gen' in ln or 'Error' in ln or 'error' in ln)[-6000:])
    for it in items:
        if os.path.exists(os.path.join(OUT, it['tag'] + '_record.json')):
            judge_tag(it['tag'])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    g = sub.add_parser('gen')
    g.add_argument('--recipe', required=True)
    g.add_argument('--seeds', default='1')
    g.add_argument('--tag', default='r')
    g.add_argument('--params')
    g.add_argument('--stage-params')
    g.add_argument('--focus')
    g.add_argument('--size')
    g.add_argument('--resolution', type=int, default=1024)
    j = sub.add_parser('judge')
    j.add_argument('tags', nargs='+')
    a = ap.parse_args()
    if a.cmd == 'gen':
        gen(a)
    elif a.cmd == 'judge':
        for t in a.tags:
            judge_tag(t)
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
