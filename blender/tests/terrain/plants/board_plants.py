"""Boards of the plants' views (system Python: numpy and Pillow; no Blender): per view, in a row, the photograph,
render_plants.py's render with the plants (out/plants/views/<recipe>_<view>[_<tag>].png) and the same view without
them (its --no-plants render, <view>_noplants[_<tag>].png, the material's canopy from expected_cover alone; else
its --bare frame, the plants hidden; else the review's newest render, out/surfacing/review/<recipe>/<view>*.png);
under them two crops at 2x of both where a defect would show (the near ground, and the band where SeedThree's cards
hand over to their billboards), so the plants are judged beside the place, item by item.

    python blender/tests/terrain/plants/board_plants.py [--tag t] [--views a,b]

Writes out/plants/boards/<recipe>_<view>[_<tag>].jpg.
"""
import glob
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
VIEWS_OUT = os.path.join(TN, 'out', 'plants', 'views')
BOARDS = os.path.join(TN, 'out', 'plants', 'boards')
REVIEW = os.path.join(TN, 'out', 'surfacing', 'review')
TILE = (960, 540)


def newest_before(recipe, view):
    """The review's newest textured render of a view: <view>.png or <view>_v<N>.png with the largest N."""
    best, best_n = None, -1
    for p in glob.glob(os.path.join(REVIEW, recipe, view + '*.png')):
        stem = os.path.splitext(os.path.basename(p))[0]
        if stem == view:
            n = 0
        else:
            m = re.fullmatch(re.escape(view) + r'_v(\d+)', stem)
            if not m:
                continue
            n = int(m.group(1))
        if n > best_n:
            best, best_n = p, n
    return best


def photo_path(rec):
    """The record's photograph: views.json gives it relative to blender/tests/terrain/out/ (older plans gave a path
    under this checkout's test folder)."""
    p = rec.get('photo')
    if not p:
        return None
    for cand in (os.path.join(TN, 'out', p), p):
        if os.path.exists(cand):
            return cand
    tail = p.replace('\\', '/').split('blender/tests/terrain/', 1)
    if len(tail) == 2 and os.path.exists(os.path.join(TN, tail[1])):
        return os.path.join(TN, tail[1])
    return None


def without_plants(recipe, view, tag):
    """(path, label) of the same view without plants: its --no-plants render, its bare frame, or the review's."""
    t = f'_{tag}' if tag else ''
    for name, label in ((f'{recipe}_{view}_noplants{t}.png', 'no plants (expected_cover)'),
                        (f'{recipe}_{view}_bare{t}.png', 'plants hidden')):
        p = os.path.join(VIEWS_OUT, name)
        if os.path.exists(p):
            return p, label
    p = newest_before(recipe, view)
    return p, 'review, no plants'


def fit(im, size=TILE):
    """The image scaled to fit the tile, centred on black."""
    w, h = im.size
    k = min(size[0] / w, size[1] / h)
    im = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
    out = Image.new('RGB', size)
    out.paste(im, ((size[0] - im.size[0]) // 2, (size[1] - im.size[1]) // 2))
    return out


def crop2x(im, cx, cy):
    """A crop of half the frame around (cx, cy) (fractions of the frame), shown at 2x, nearest-neighbour, and its
    box (x0, y0, w, h) in the frame."""
    w, h = im.size
    cw, ch = w // 2, h // 2
    x0 = int(min(max(cx * w - cw / 2, 0), w - cw))
    y0 = int(min(max(cy * h - ch / 2, 0), h - ch))
    return im.crop((x0, y0, x0 + cw, y0 + ch)).resize((cw * 2, ch * 2), Image.NEAREST), (x0, y0, cw, ch)


def handoff_row(rec, h=TILE[1]):
    """The frame row (fraction from the top) where the ground lies at SeedThree's card distance from the camera, for
    the first SeedThree species the record names; None when it cannot be told (no cards, the ground never there)."""
    lod = rec.get('lod') or {}
    bb = next((v[0].get('billboard_m') for v in lod.values() if v and v[0].get('billboard_m')), None)
    if not bb:
        return None
    pitch = math.radians(rec.get('pitch_deg') or 0.0)
    eye_h = 1.7
    # the angle below the horizon of ground bb metres off, against the frame's vertical field
    below = math.atan2(eye_h, bb)
    vfov = 2 * math.atan(18.0 * TILE[1] / TILE[0] / float(rec['lens']))
    frac = 0.5 + (pitch + below) / vfov
    return frac if 0.05 < frac < 0.95 else None


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 8 + 7 * len(text), 18], fill=(0, 0, 0))
    d.text((4, 3), text, fill=(255, 255, 255))
    return im


RECIPES = ('real_place', 'fluvial_range', 'alpine_valley', 'impact_crater', 'incised_meanders', 'mesas_buttes',
           'tower_karst', 'sea_cliffs', 'rolling_hills', 'cinder_cones')


def board(key, rec, tag, out_dir):
    recipe, view = key.split('_', 1) if '_' in key else (key, key)
    for r in RECIPES:
        if key.startswith(r + '_'):
            recipe, view = r, key[len(r) + 1:]
    view = view[:-len('_' + tag)] if tag and view.endswith('_' + tag) else view
    after_p = os.path.join(TN, rec['image']) if rec.get('image') else None
    if not after_p or not os.path.exists(after_p):
        print(f'[board_plants] {key}: no render')
        return None
    after = Image.open(after_p).convert('RGB')
    before_p, before_what = without_plants(recipe, view, tag)
    before = Image.open(before_p).convert('RGB').resize(after.size) if before_p else Image.new('RGB', after.size)
    ph = photo_path(rec)
    photo = Image.open(ph).convert('RGB') if ph else Image.new('RGB', TILE)
    row1 = [label(fit(photo), 'photograph' if ph else 'no photograph'),
            label(fit(before), f'{before_what}: ' + (os.path.basename(before_p) if before_p else 'none')),
            label(fit(after), 'with plants: ' + os.path.basename(after_p))]
    near = (0.5, 0.82)
    hy = handoff_row(rec)
    mid = (0.5, hy) if hy is not None else (0.5, 0.6)
    row2 = []
    for (cx, cy), what in ((near, 'near ground 2x'), (mid, 'card-billboard hand-off 2x' if hy else 'mid ground 2x')):
        a, _ = crop2x(after, cx, cy)
        b, _ = crop2x(before, cx, cy)
        row2.append(label(fit(b), f'without {what}'))
        row2.append(label(fit(a), f'plants {what}'))
    W = TILE[0] * 3
    out = Image.new('RGB', (W, TILE[1] * 3), (20, 20, 20))
    for k, im in enumerate(row1):
        out.paste(im, (k * TILE[0], 0))
    for k, im in enumerate(row2[:2]):
        out.paste(im, (k * TILE[0], TILE[1]))
    for k, im in enumerate(row2[2:]):
        out.paste(im, (k * TILE[0], 2 * TILE[1]))
    d = ImageDraw.Draw(out)
    sp = rec.get('species') or {}
    lines = [f"{key}: {rec.get('caption', '')}",
             f"ecotope {rec.get('ecotope')}; plan {rec.get('plan_s')} s, instancing {rec.get('instance_s')} s, "
             f"frames {rec.get('first_render_s')} s / {rec.get('second_render_s')} s",
             ] + [f"  {n}: {v['count']:,} spots, {v.get('per_ha_home')} per ha at home (range {v.get('range_per_ha')})"
                  for n, v in sp.items()]
    y = TILE[1] + 10
    for ln in lines:
        d.text((2 * TILE[0] + 12, y), ln[:150], fill=(230, 230, 230))
        y += 16
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f'{recipe}_{view}' + (f'_{tag}' if tag else '') + '.jpg')
    out.save(p, quality=90)
    print('[board_plants] wrote', p)
    return p


def main():
    a = sys.argv[1:]
    tag = a[a.index('--tag') + 1] if '--tag' in a else ''
    only = set(a[a.index('--views') + 1].split(',')) if '--views' in a else None
    rec = json.load(open(os.path.join(VIEWS_OUT, f"record{'_' + tag if tag else ''}.json"), encoding='utf-8'))
    for key, r in rec.items():
        if 'error' in r:
            print(f'[board_plants] {key}: {r["error"]}')
            continue
        if not r.get('plants', True) or '_noplants' in key:
            continue                                     # a view without plants: the board's other half
        if only and not any(key.endswith(v) or key.endswith(v + '_' + tag) for v in only):
            continue
        board(key, r, tag, BOARDS)


if __name__ == '__main__':
    main()
