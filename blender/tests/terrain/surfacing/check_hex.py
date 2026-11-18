"""The material's check 3 (SURFACING_DESIGN.md 5.4, package 2): hex tiling against today's two-lattice de-tiling, read
on the same views rendered both ways (check_sectors.py writes them), with the judge's repetition measure
(surfacing_judge/measures.py) and the crop's high-pass energy beside it, so blur cannot pass for de-tiling.

    python blender/tests/terrain/surfacing/check_hex.py [--tag r5]     (plain Python: numpy and Pillow, no Blender)

Crops (pixels of the 960 x 540 renders): the canyon plateau near and in the middle distance (approach_walk, the
judge's two crops), the brink's diagonal wall (brink_down's second crop), the benches and talus aprons between the
cliff bands (low_oblique: the beds' bands correlate too, as they do in the photographs), and the Lauterbrunnen floor
at the walker's feet (floor_lischmaad's first crop) when its renders exist. Eye-level ground
is read in rows (a row lies at one depth, where a tile repeats at one period along it), aerial crops in 2-D. Per crop
and material: the autocorrelation's second peak (the photographs' 0.03-0.11, measures.PHOTO_REPETITION) and the
energy of the high-passed luma; and the per-texel material's energy over today's (flagged under 0.8). Writes
out/surfacing/material/hex_<tag>.json and a 2x board of the crops, today above the per-texel material.
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'surfacing_judge'))
import measures as M  # noqa: E402

OUT = os.path.join(TN, 'out', 'surfacing', 'material')
SECTORS = os.path.join(OUT, 'sectors')
# (case, view, crop box, mode, what it shows)
CROPS = [('canyon', 'approach_walk', (360, 405, 600, 540), 'rows', 'plateau at the feet'),
         ('canyon', 'approach_walk', (380, 250, 620, 385), 'rows', 'plateau, middle distance'),
         ('canyon', 'brink_down', (380, 300, 620, 435), '2d', "the brink's diagonal wall, near"),
         ('canyon', 'low_oblique', (330, 300, 570, 435), '2d', 'benches, talus aprons and cliff bands'),
         ('lauterbrunnen', 'floor_lischmaad', (0, 405, 240, 540), 'rows', 'valley floor at the feet')]


def main():
    a = sys.argv[1:]
    tag = a[a.index('--tag') + 1] if '--tag' in a else 'r5'
    rec = dict(tag=tag, photographs=list(M.PHOTO_REPETITION), crops=[])
    tiles = []
    for case, view, box, mode, what in CROPS:
        paths = {lab: os.path.join(SECTORS, f'{case}_{view}_{lab}_scan_{tag}.png') for lab in ('today', 'per_texel')}
        if not all(os.path.exists(p) for p in paths.values()):
            print(f'[hex] {case} {view}: no renders tagged {tag} (check_sectors.py --tag {tag})', flush=True)
            continue
        r = dict(case=case, view=view, box=list(box), mode=mode, what=what)
        crops = {}
        for lab, p in paths.items():
            rgb = M.load_rgb(p)
            rep = M.repetition(M.luma(rgb), box=box, mode=mode)
            r[lab] = dict(peak=None if rep['peak'] is None else round(rep['peak'], 3), lag=rep['lag'],
                          energy=round(rep['energy'], 4))
            crops[lab] = Image.open(p).convert('RGB').crop(box)
        r['energy_ratio'] = round(r['per_texel']['energy'] / max(r['today']['energy'], 1e-9), 2)
        r['energy_flag'] = bool(M.flag('repetition_energy', r['energy_ratio']))
        r['repetition_flag'] = bool(r['per_texel']['peak'] is not None and M.flag('repetition', r['per_texel']['peak']))
        rec['crops'].append(r)
        tiles.append(crops)
        print(f"[hex] {case} {view} ({what}): repetition today {r['today']['peak']} -> {r['per_texel']['peak']}, "
              f"energy {r['today']['energy']} -> {r['per_texel']['energy']} ({r['energy_ratio']}x)", flush=True)
    if tiles:
        w, h = tiles[0]['today'].size
        board = Image.new('RGB', (len(tiles) * (2 * w + 8), 2 * (2 * h) + 8), (20, 20, 20))
        for k, c in enumerate(tiles):
            for j, lab in enumerate(('today', 'per_texel')):
                board.paste(c[lab].resize((2 * w, 2 * h), Image.LANCZOS), (k * (2 * w + 8), j * (2 * h + 8)))
        board.save(os.path.join(OUT, f'hex_{tag}.png'))
    path = os.path.join(OUT, f'hex_{tag}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    print(f'[hex] done -> {path}', flush=True)


if __name__ == '__main__':
    main()
