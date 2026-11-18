"""Boards for the look package: per view, the photograph of the place | the render before | the render after | the
layer map after (render_look.py's frames), and 2x crops of where a defect would show, so a palette edit is judged
beside the photograph and beside what it replaces. Plain Python (numpy, Pillow).

    python blender/tests/terrain/surface_look/board.py --recipe canyon --before base --after new
        [--views a,b] [--crops "view:x0,y0,x1,y1;view:..."] [--tile 800] [--plan <views.json>]

--before and --after: a render_look.py tag (out/surface_look/<recipe>/<view>_<tag>.png), or state:<name> (a state of
the surfacing judge, out/surfacing_judge/states/<name>/<recipe>/<view>.png: state:before is the 11-13 review's look
from the judge's cameras), or mat:<tag> (the material package's per-texel renders, out/surfacing/material/sectors/
<recipe>_<view>_per_texel_scan_<tag>.png). The views are the judge's (surfacing_judge/views.json), and so are the
photographs. --crops: rectangles as fractions of the 960 x 540 frame (from the left, from the top), cut from before
and after at the same place and shown at 2x. Writes out/surface_look/boards/<recipe>_<before>_<after>_<view>.jpg (one
board per view, the 2x2 grid with the view's caption, its crops under it; ':' in a tag becomes '-').
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'surface_look')
REVIEW = os.path.join(TN, 'out', 'review')
VIEWS = os.path.join(TN, 'surfacing_judge', 'views.json')


def render_path(recipe, view, tag, layers=False):
    """Where a tag's frame of a view is (module doc)."""
    suffix = '_layers' if layers else ''
    if tag.startswith('state:'):
        return os.path.join(TN, 'out', 'surfacing_judge', 'states', tag[6:], recipe, f'{view}{suffix}.png')
    if tag.startswith('mat:'):
        return os.path.join(TN, 'out', 'surfacing', 'material', 'sectors',
                            f"{recipe}_{view}_per_texel_scan_{tag[4:]}{suffix}.png")
    return os.path.join(OUT, recipe, f'{view}_{tag}{suffix}.png')


def plan_views(recipe, plan=None):
    """The judge's views of a recipe (views.json; the review's plan as a fallback)."""
    for p in ([plan] if plan else []) + [VIEWS, os.path.join(REVIEW, 'views_plan.json')]:
        if p and os.path.exists(p):
            got = json.load(open(p, encoding='utf-8')).get(recipe)
            if got:
                return got.get('views', [])
    return []


def font(size=15):
    try:
        return ImageFont.truetype('arial.ttf', size)
    except OSError:
        return ImageFont.load_default()


def photo_path(p):
    """A view's photograph: the judge's views give it relative to this checkout's blender/tests/terrain/out/; the
    review plan's absolute path is found again under out/ (the part after 'terrain/out/')."""
    if not p:
        return None
    s = str(p).replace('\\', '/')
    cand = os.path.join(TN, 'out', s)
    if os.path.exists(cand):
        return cand
    key = 'terrain/out/'
    if key in s:
        cand = os.path.join(TN, 'out', s.split(key, 1)[1])
        if os.path.exists(cand):
            return cand
    return p if os.path.exists(p) else None


def fit(im, w, h):
    """im scaled to cover w x h and centre-cropped (a photograph's aspect differs from the frame's)."""
    s = max(w / im.width, h / im.height)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    x0, y0 = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x0, y0, x0 + w, y0 + h))


def blank(w, h, text):
    im = Image.new('RGB', (w, h), (40, 40, 40))
    ImageDraw.Draw(im).text((10, 10), text, fill=(200, 200, 200), font=font())
    return im


def load(path, w, h, label):
    if path and os.path.exists(path):
        im = Image.open(path)
        if im.mode == 'RGBA':                              # a layer map: its transparent sky on mid grey
            bg = Image.new('RGBA', im.size, (60, 60, 60, 255))
            bg.alpha_composite(im)
            im = bg
        return fit(im.convert('RGB'), w, h)
    return blank(w, h, f'{label}: none')


def board(recipe, view, before, after, tile=800, crops=None, caption='', plan=None):
    v = next((x for x in plan_views(recipe, plan) if x['name'] == view), {})
    th = tile * 9 // 16
    cells = [(load(photo_path(v.get('photo')), tile, th, 'photograph'), 'photograph'),
             (load(render_path(recipe, view, before), tile, th, before), f'before [{before}]'),
             (load(render_path(recipe, view, after), tile, th, after), f'after [{after}]'),
             (load(render_path(recipe, view, after, layers=True), tile, th, 'layers'), f'layer map [{after}]')]
    crops = crops or []
    ch = 0
    crop_ims = []
    for (x0, y0, x1, y1) in crops:
        pair = []
        for tag in (before, after):
            p = render_path(recipe, view, tag)
            if os.path.exists(p):
                im = Image.open(p).convert('RGB')
                W, H = im.size
                c = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
                c = c.resize((c.width * 2, c.height * 2), Image.LANCZOS)
                s = min(1.0, tile / c.width)
                pair.append(c.resize((max(1, int(c.width * s)), max(1, int(c.height * s))), Image.LANCZOS))
            else:
                pair.append(blank(tile, th // 2, tag))
        crop_ims.append(pair)
        ch += max(p.height for p in pair) + 26
    head = 30
    B = Image.new('RGB', (2 * tile, head + 2 * (th + 22) + ch), (18, 18, 18))
    dr = ImageDraw.Draw(B)
    dr.text((8, 7), f"{recipe} / {view}: {caption or v.get('caption', '')}"[:230], fill=(255, 220, 120), font=font())
    for k, (im, lb) in enumerate(cells):
        x, y = (k % 2) * tile, head + (k // 2) * (th + 22)
        B.paste(im, (x, y + 20))
        dr.text((x + 6, y + 2), lb, fill=(230, 230, 230), font=font())
    y = head + 2 * (th + 22)
    for k, ((x0, y0, x1, y1), pair) in enumerate(zip(crops, crop_ims)):
        dr.text((6, y + 4), f'2x crop {k} ({x0:.2f},{y0:.2f})-({x1:.2f},{y1:.2f}): before | after', fill=(230, 230, 230),
                font=font())
        B.paste(pair[0], (0, y + 24))
        B.paste(pair[1], (tile, y + 24))
        y += max(p.height for p in pair) + 26
    os.makedirs(os.path.join(OUT, 'boards'), exist_ok=True)
    path = os.path.join(OUT, 'boards', f"{recipe}_{before.replace(':', '-')}_{after.replace(':', '-')}_{view}.jpg")
    B.save(path, quality=92)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--recipe', required=True)
    ap.add_argument('--before', default='base')
    ap.add_argument('--after', default='new')
    ap.add_argument('--views', default='')
    ap.add_argument('--crops', default='')
    ap.add_argument('--tile', type=int, default=800)
    ap.add_argument('--plan')
    a = ap.parse_args()
    views = [s for s in a.views.split(',') if s] or [v['name'] for v in plan_views(a.recipe, a.plan)]
    crops = {}
    for part in a.crops.split(';'):
        if ':' in part:
            vn, box = part.split(':', 1)
            crops.setdefault(vn.strip(), []).append(tuple(float(t) for t in box.split(',')))
    for vn in views:
        if not os.path.exists(render_path(a.recipe, vn, a.after)) and \
                not os.path.exists(render_path(a.recipe, vn, a.before)):
            continue
        print('[board]', board(a.recipe, vn, a.before, a.after, a.tile, crops.get(vn), plan=a.plan))


if __name__ == '__main__':
    main()
