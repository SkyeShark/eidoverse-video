"""The port's masks drawn by the Blender masks package's own sheet painter (blender/tests/terrain/masks/sheets.py,
used as it is: the same panels over the same hillshade, the same false-colour composite), beside masks.py's masks of
the same inputs, for an environment artist to read the two against the landform and against each other.

    <Blender's python> -I eidoverse/terrain/tests/masks/sheets_port.py [--only lauterbrunnen,mount_fuji]

Reads the port's main-tile masks (tests/out/masks/sheets/<name>_port_masks.npz, written by masks_test.mjs --only
refs --sheets) and the fixture of the same stack (tests/out/masks/fixtures/ref_<name>.npz: its float32 inputs and
masks.py's masks). Writes into tests/out/masks/sheets/:
    <name>_tile_compare.png     the whole main tile: masks.py's sheet above, the port's below
    <name>_detail_compare.png   the same on the Blender sheets' detail crop (2 km; Fuji 10 km)
    <name>_diff.png             per mask |port - masks.py| over its range, x 1000 (white: 1e-3 of the range)
With --aerials, after tests/masks/render_masks.mjs: masks_aerials_compare.png, per reference the clay reference's
45-degree aerial (the Blender edition's reference/renders), the Blender masks package's render of the masks as a
material (its out/masks/renders), the port's render of the same view (tests/out/masks/renders), and a photograph of
the place from the Blender packages' photo folders (their sources.json: title, author, licence).
Runs numpy and Pillow only; nothing is written into the Blender edition.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

sys.dont_write_bytecode = True
ROOT = B.bare_terrain_package()
sys.path.insert(0, os.path.join(ROOT, 'blender', 'tests', 'terrain', 'masks'))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

FIX = os.path.join(HERE, '..', 'out', 'masks', 'fixtures')
OUT = os.path.join(HERE, '..', 'out', 'masks', 'sheets')


class Masks(dict):
    """A mask dict with the .skipped the painter reads."""
    skipped = {}


def stack_images(top, bottom, labels):
    w = max(top.width, bottom.width)
    lab = 34
    img = Image.new('RGB', (w, top.height + bottom.height + 2 * lab), (14, 15, 18))
    d = ImageDraw.Draw(img)
    f = S.font(20)
    d.text((10, 6), labels[0], font=f, fill=(150, 210, 255))
    img.paste(top, (0, lab))
    d.text((10, top.height + lab + 6), labels[1], font=f, fill=(255, 200, 120))
    img.paste(bottom, (0, top.height + 2 * lab))
    return img


def diff_sheet(name, blender, port, h, cell, px=300, cols=7):
    keys = [k for k in blender if k in port]
    rows = -(-len(keys) // cols)
    head, lab = 40, 40
    img = Image.new('RGB', (cols * (px + 6) + 6, head + rows * (px + lab + 6)), (14, 15, 18))
    d = ImageDraw.Draw(img)
    d.text((10, 8), f'{name}: |port - masks.py| / range x 1000 per mask (white = 1e-3 of the range), north up',
           font=S.font(18), fill=(240, 220, 150))
    for k, nm in enumerate(keys):
        a, b = np.asarray(blender[nm], np.float64), np.asarray(port[nm], np.float64)
        rng = max(float(np.ptp(a)), 1e-20)
        e = np.abs(a - b)
        if nm == 'aspect':
            e = np.minimum(e % 360.0, 360.0 - e % 360.0)
        v = np.clip(np.flipud(e / rng) * 1000.0, 0.0, 1.0)
        r, c = divmod(k, cols)
        x, y = 6 + c * (px + 6), head + r * (px + lab + 6)
        rgb = np.repeat(v[..., None], 3, -1)
        img.paste(S.to_img(rgb, px), (x, y + lab))
        d.text((x + 2, y + 2), nm, font=S.font(15), fill=(240, 220, 150))
        d.text((x + 2, y + 20), f'max {e.max() / rng:.1e}  p99 {np.percentile(e, 99) / rng:.1e}', font=S.font(12),
               fill=(185, 190, 200))
    return img


# a photograph of each sheet reference: (the Blender package's photo folder under out/, the file, its sources.json)
PHOTOS = {
    'lauterbrunnen': ('glacial/photos/raw', 'lauterbrunnen_00.jpg', 'glacial/photos/sources.json'),
    'grand_canyon_toroweap': ('layered_rock/photos', 'tw_01.jpg', 'layered_rock/photos/sources.json'),
    'mount_fuji': ('volcanoes_craters/photos/mount_fuji', 'mount_fuji_04_aerial_north.jpg',
                   'volcanoes_craters/photos/mount_fuji/sources.json'),
    'badlands_sd': ('layered_rock/photos', 'bl_01.jpg', 'layered_rock/photos/sources.json'),
    'great_sand_dunes': ('integration/photos/great_sand_dunes', 'great_sand_dunes_01.jpg',
                         'integration/photos/great_sand_dunes/sources.json'),
}


def _credit(src, file):
    """'title, author, licence' of a photo from its sources.json, whatever its layout (a dict of records, or
    {'photos': [records]})."""
    s = B.read_json(src, {}) or {}
    recs = []
    if isinstance(s, dict):
        if isinstance(s.get('photos'), list):
            recs = s['photos']
        elif isinstance(s.get('photos'), dict):
            recs = list(s['photos'].values())
        else:
            recs = [dict(v, key=k) for k, v in s.items() if isinstance(v, dict)]
    stem = os.path.splitext(file)[0]
    for r in recs:
        if not isinstance(r, dict):
            continue
        if stem in (str(r.get('key', '')), str(r.get('file', '')), os.path.splitext(str(r.get('file', '')))[0],
                    os.path.splitext(os.path.basename(str(r.get('path', ''))))[0]):
            return ', '.join(str(r[k]) for k in ('title', 'artist', 'author', 'license', 'licence') if r.get(k))[:120]
    return 'see sources.json beside the photograph'


def aerials(names, w=480):
    tests = os.path.join(ROOT, 'blender', 'tests', 'terrain')
    rows = []
    for name in names:
        ref = os.path.join(tests, 'reference', 'renders', f'{name}_aerial_45deg.png')
        bl = os.path.join(tests, 'out', 'masks', 'renders', f'{name}_masks_aerial_45deg.png')
        port = os.path.join(HERE, '..', 'out', 'masks', 'renders', f'{name}_masks_port_aerial_45deg.png')
        ph = PHOTOS.get(name)
        photo = os.path.join(tests, 'out', ph[0], ph[1]) if ph else None
        panels = []
        for label, p in ((f'{name}: clay (reference rig)', ref), ('masks as a material: Blender (masks.py, EEVEE)', bl),
                         ('masks as a material: the port (masks.js, WebGPU)', port), ('a photograph of the place', photo)):
            im = Image.open(p).convert('RGB') if p and os.path.isfile(p) else None
            panels.append((label, im))
        credit = _credit(os.path.join(tests, 'out', ph[2]), ph[1]) if ph else ''
        rows.append((name, panels, credit))
    hgt = int(w * 540 / 960)
    lab, foot = 26, 18
    img = Image.new('RGB', (4 * (w + 6) + 6, 44 + len(rows) * (hgt + lab + foot + 8)), (14, 15, 18))
    d = ImageDraw.Draw(img)
    d.text((10, 10), 'The masks as a material (render_masks.py\'s rules): the clay reference, Blender\'s render, the '
                     'port\'s render of the same view, and a photograph of the place', font=S.font(17), fill=(240, 220, 150))
    for k, (name, panels, credit) in enumerate(rows):
        y = 44 + k * (hgt + lab + foot + 8)
        for c, (label, im) in enumerate(panels):
            x = 6 + c * (w + 6)
            d.text((x + 2, y + 4), label, font=S.font(14), fill=(190, 195, 205))
            if im is None:
                d.text((x + 10, y + lab + hgt // 2), 'missing', font=S.font(16), fill=(255, 90, 90))
                continue
            if c == 3:                                               # the photograph: centre-cropped to the frame
                sw, sh = im.size
                sc = max(w / sw, hgt / sh)
                im = im.resize((max(w, int(sw * sc)), max(hgt, int(sh * sc))), Image.LANCZOS)
                ox, oy = (im.width - w) // 2, (im.height - hgt) // 2
                im = im.crop((ox, oy, ox + w, oy + hgt))
            else:
                im = im.resize((w, hgt), Image.LANCZOS)
            img.paste(im, (x, y + lab))
        d.text((6 + 3 * (w + 6) + 2, y + lab + hgt + 2), credit, font=S.font(11), fill=(150, 155, 165))
    path = os.path.join(HERE, '..', 'out', 'masks', 'renders', 'masks_aerials_compare.png')
    img.save(path)
    return os.path.normpath(path)


def main():
    global S
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--only', default='')
    ap.add_argument('--aerials', action='store_true', help='the aerial compare sheet (after render_masks.mjs)')
    a = ap.parse_args()
    import sheets as _S                                              # the Blender masks package's painter, as it is
    S = _S
    os.makedirs(OUT, exist_ok=True)
    names = [n for n in (a.only.split(',') if a.only else S.F.SHEET_REFS) if n]
    if a.aerials:
        print(f'[sheets] {aerials(names)}', flush=True)
        return
    made = []
    for name in names:
        pf = os.path.join(OUT, f'{name}_port_masks.npz')
        ff = os.path.join(FIX, f'ref_{name}.npz')
        if not (os.path.isfile(pf) and os.path.isfile(ff)):
            print(f'[sheets] {name}: no port masks or fixture (run masks_test.mjs --only refs --sheets)', flush=True)
            continue
        with open(os.path.join(OUT, f'{name}_port_masks.json'), encoding='utf-8') as f:
            pmeta = json.load(f)
        fz, pz = np.load(ff), np.load(pf)
        h = fz['L1__in__h'].astype(np.float64)
        cell = float(pmeta['level']['cell'])
        blender = Masks({k[len('L1__out__'):]: fz[k] for k in fz.files if k.startswith('L1__out__')})
        port = Masks({k: pz[k] for k in pz.files})
        port.skipped = dict(pmeta.get('skipped') or {})
        man = B.read_json(os.path.join(FIX, 'manifest.json'), {})
        case = next((c for c in man.get('cases', []) if c['name'] == f'ref_{name}'), {})
        blender.skipped = dict((case.get('masks') or [{}, {}])[1].get('skipped') or {})
        pal = S.F.PREVIEW_PALETTE_OF.get(name, 'alpine')
        km = h.shape[1] * cell / 1000.0
        title = lambda who: (f'{name}: the main tile\'s masks, {who}',                          # noqa: E731
                             f'{km:g} km at {cell:g} m  |  relief {h.max() - h.min():.0f} m  |  stacked on its context, border pinned')
        tb = S.sheet(name, blender, h, cell, title('masks.py (Blender edition)'), palette=pal)
        tp = S.sheet(name, port, h, cell, title('masks.js (three.js edition, the port)'), palette=pal)
        stack_images(tb, tp, ('masks.py, Blender 5.2 numpy 2.3.4', 'masks.js, WebGPU kernels (the port)')).save(
            os.path.join(OUT, f'{name}_tile_compare.png'))
        det = S.DETAIL.get(name, dict(at=(0.0, 0.0), side=2048.0))
        lv = pmeta['level']
        half = int(round(det['side'] / cell / 2))
        ci = min(max(int(round((det['at'][0] - lv['x0']) / cell)), half), h.shape[1] - half)
        cj = min(max(int(round((det['at'][1] - lv['y0']) / cell)), half), h.shape[0] - half)
        crop = (cj - half, cj + half, ci - half, ci + half)
        dtitle = lambda who: (f'{name}: detail, {2 * half * cell / 1000:g} km wide, {who}', 'north up')   # noqa: E731
        db = S.sheet(name, blender, h, cell, dtitle('masks.py'), crop=crop, palette=pal)
        dp = S.sheet(name, port, h, cell, dtitle('masks.js (the port)'), crop=crop, palette=pal)
        stack_images(db, dp, ('masks.py', 'masks.js (the port)')).save(os.path.join(OUT, f'{name}_detail_compare.png'))
        diff_sheet(name, blender, port, h, cell).save(os.path.join(OUT, f'{name}_diff.png'))
        made.append(name)
        print(f'[sheets] {name}: tile, detail and difference sheets', flush=True)
    print(f'[sheets] {len(made)} references -> {OUT}', flush=True)


S = None

if __name__ == '__main__':
    main()
