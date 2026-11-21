"""Boards of the plants' views (tests/plants/views.mjs): per view, in a row, the photograph, the Blender edition's
render of the view with its plants (blender/tests/terrain/out/surfacing/review/<recipe>/<view>_<tag>.png, the review's
final renders) and the port's (tests/out/plants/views/<recipe>_<view>_<label>.png; one rendered at k times the review's
size, views.mjs --W --H, is averaged k x k first and kept as <...>_<label>_960.png); under them two places at 2x of
both renders (the view's crops in surfacing_judge/views.json, else the near ground and the middle distance, where
the cards hand over to the billboards and the billboards to the material's canopy), so the plants are judged beside
the place and beside Blender's, item by item. System Python with Pillow (no Blender, no numpy needed).

    EIDO_BLENDER_EDITION=<a Blender checkout> python eidoverse/terrain/tests/plants/board_views.py [--label port]
        [--tag final2] [--views real_place/floor_lischmaad,...]

Writes tests/out/plants/views/boards/<recipe>_<view>_<label>.jpg.
"""
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'plants', 'views'))
TILE = (640, 360)
VIEWS = ['real_place/floor_lischmaad', 'real_place/ridge_schynige', 'canyon/approach_walk', 'caldera/rim_east',
         'fluvial_range/canyon_road', 'dunes/interdune_floor']


def opt(name, default=None):
    a = sys.argv[1:]
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def fit(img, size):
    """The image cropped to the size's aspect about its centre, then resized."""
    w, h = img.size
    tw, th = size
    k = max(tw / w, th / h)
    nw, nh = round(w * k), round(h * k)
    im = img.convert('RGB').resize((nw, nh), Image.LANCZOS)
    x0, y0 = (nw - tw) // 2, (nh - th) // 2
    return im.crop((x0, y0, x0 + tw, y0 + th))


def crop2x(img, box, size):
    x0, y0, x1, y1 = box
    return img.convert('RGB').crop((x0, y0, x1, y1)).resize(size, Image.NEAREST)


def main():
    edition = os.environ.get('EIDO_BLENDER_EDITION')
    if not edition:
        print('[skip] boards: set EIDO_BLENDER_EDITION to a Blender checkout (its review renders and photographs)')
        return 0
    tests = os.path.join(edition, 'blender', 'tests', 'terrain')
    label, tag = opt('--label', 'port'), opt('--tag', 'final2')
    views = (opt('--views') or ','.join(VIEWS)).split(',')
    judge = json.load(open(os.path.join(tests, 'surfacing_judge', 'views.json'), encoding='utf-8'))
    os.makedirs(os.path.join(OUT, 'boards'), exist_ok=True)
    made = []
    for rv in views:
        recipe, name = rv.split('/')
        v = next((x for x in judge[recipe]['views'] if x['name'] == name), None)
        port = os.path.join(OUT, f'{recipe}_{name}_{label}.png')
        blender = os.path.join(tests, 'out', 'surfacing', 'review', recipe, f'{name}_{tag}.png')
        photo = os.path.join(tests, 'out', v['photo']) if v and v.get('photo') else None
        if not os.path.exists(port):
            print(f'[skip] {rv}: no port render {port}')
            continue
        pi = Image.open(port)
        bi = Image.open(blender) if os.path.exists(blender) else None
        ph = Image.open(photo) if photo and os.path.exists(photo) else None
        ss = ''
        if bi is not None and pi.size != bi.size and pi.size[0] % bi.size[0] == 0 and pi.size[0] // bi.size[0] == pi.size[1] // bi.size[1]:
            # a frame rendered at k x k the review's size (views.mjs --W, --H): its pixels averaged k x k, so the port's
            # frame takes k^2 samples a pixel (Blender's review renders take 16)
            k = pi.size[0] // bi.size[0]
            pi = pi.convert('RGB').reduce(k)
            ss = f' ({k}x{k} samples a pixel)'
        W, H = pi.size
        crops = (v or {}).get('crops') or [[W // 2 - 120, H - 135, W // 2 + 120, H], [W // 2 - 120, H // 2 - 68, W // 2 + 120, H // 2 + 67]]
        cs = (480, 270)
        board = Image.new('RGB', (3 * TILE[0], TILE[1] + 2 * cs[1] + 60), (24, 24, 24))
        d = ImageDraw.Draw(board)
        for k, (im, cap) in enumerate([(ph, 'photograph'), (bi, f'Blender {tag}'), (pi, f'port {label}{ss}')]):
            if im is not None:
                board.paste(fit(im, TILE), (k * TILE[0], 20))
            d.text((k * TILE[0] + 6, 4), cap + ('' if im is not None else ' (missing)'), fill=(230, 230, 230))
        y = TILE[1] + 40
        for j, box in enumerate(crops[:2]):
            for k, (im, cap) in enumerate([(bi, 'Blender'), (pi, 'port')]):
                if im is None:
                    continue
                board.paste(crop2x(im.resize((W, H)) if im.size != (W, H) else im, box, cs), (k * cs[0] + (TILE[0] // 2) * j * 0, y + j * cs[1]))
                d.text((k * cs[0] + 6, y + j * cs[1] + 4), f'{cap} 2x {box}', fill=(255, 255, 0))
        # the crops sit in the left two columns; the right column keeps the photograph's own 2x crops for reference
        if ph is not None:
            pf = fit(ph, (W, H))
            for j, box in enumerate(crops[:2]):
                board.paste(crop2x(pf, box, cs), (2 * cs[0], y + j * cs[1]))
                d.text((2 * cs[0] + 6, y + j * cs[1] + 4), f'photograph 2x {box}', fill=(255, 255, 0))
        dst = os.path.join(OUT, 'boards', f'{recipe}_{name}_{label}.jpg')
        board.save(dst, quality=90)
        made.append(dst)
        if ss:                                           # the averaged frame beside the others, for the eye and the measures
            pi.save(os.path.join(OUT, f'{recipe}_{name}_{label}_960.png'))
    print('\n'.join(made))
    return 0


if __name__ == '__main__':
    sys.exit(main())
