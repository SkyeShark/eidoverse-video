"""Boards for the look package: per view, the photograph of the place | the render before | the render after | the
layer map after (render_look.py's frames), and 2x crops of where a defect would show, so a palette edit is judged
beside the photograph and beside what it replaces. Plain Python (numpy, Pillow).

    python blender/tests/terrain/surface_look/board.py --recipe canyon --before base --after new
        [--views a,b] [--crops "view:x0,y0,x1,y1;view:..."] [--tile 800]

--crops: rectangles as fractions of the 960 x 540 frame (from the left, from the top), cut from before and after at
the same place and shown at 2x. Writes out/surface_look/boards/<recipe>_<before>_<after>_<view>.jpg (one board per
view, the 2x2 grid with the view's caption, its crops under it).
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'surface_look')
REVIEW = os.path.join(TN, 'out', 'review')


def font(size=15):
    try:
        return ImageFont.truetype('arial.ttf', size)
    except OSError:
        return ImageFont.load_default()


def photo_path(p):
    """The review plan's photograph path, found again under this checkout's out/ (the plan was written on another
    checkout): the part after 'terrain/out/' (or 'terrain\\out\\') joined to this checkout's out/."""
    if not p:
        return None
    s = str(p).replace('\\', '/')
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


def board(recipe, view, before, after, tile=800, crops=None, caption=''):
    d = os.path.join(OUT, recipe)
    plan = json.load(open(os.path.join(REVIEW, 'views_plan.json'), encoding='utf-8')).get(recipe, {})
    v = next((x for x in plan.get('views', []) if x['name'] == view), {})
    th = tile * 9 // 16
    cells = [(load(photo_path(v.get('photo')), tile, th, 'photograph'), 'photograph'),
             (load(os.path.join(d, f'{view}_{before}.png'), tile, th, before), f'before [{before}]'),
             (load(os.path.join(d, f'{view}_{after}.png'), tile, th, after), f'after [{after}]'),
             (load(os.path.join(d, f'{view}_{after}_layers.png'), tile, th, 'layers'), f'layer map [{after}]')]
    crops = crops or []
    ch = 0
    crop_ims = []
    for (x0, y0, x1, y1) in crops:
        pair = []
        for tag in (before, after):
            p = os.path.join(d, f'{view}_{tag}.png')
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
    path = os.path.join(OUT, 'boards', f'{recipe}_{before}_{after}_{view}.jpg')
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
    a = ap.parse_args()
    plan = json.load(open(os.path.join(REVIEW, 'views_plan.json'), encoding='utf-8')).get(a.recipe, {})
    views = [s for s in a.views.split(',') if s] or [v['name'] for v in plan.get('views', [])]
    crops = {}
    for part in a.crops.split(';'):
        if ':' in part:
            vn, box = part.split(':', 1)
            crops.setdefault(vn.strip(), []).append(tuple(float(t) for t in box.split(',')))
    for vn in views:
        if not os.path.exists(os.path.join(OUT, a.recipe, f'{vn}_{a.after}.png')) and \
                not os.path.exists(os.path.join(OUT, a.recipe, f'{vn}_{a.before}.png')):
            continue
        print('[board]', board(a.recipe, vn, a.before, a.after, a.tile, crops.get(vn)))


if __name__ == '__main__':
    main()
