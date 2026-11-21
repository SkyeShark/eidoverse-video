"""Boards of the material's views (SURFACING_DESIGN.md 5.4, package 2): the matched photograph, today's material and
the per-texel material side by side, with a 2x crop of each render where a defect would show, from the renders
check_sectors.py writes (out/surfacing/material/sectors/<case>_<view>_<today|per_texel>_scan_<tag>.png).

    python blender/tests/terrain/surfacing/material_boards.py --tag r5 [--views canyon/brink_down,sea_cliffs/from_the_sea]
        [--crop canyon/brink_down=380,300,620,435]           (plain Python: Pillow)
    python blender/tests/terrain/surfacing/material_boards.py --sheen rolling_hills/f76 [--variants before,new]
        [--photo rolling_hills/aerial] [--crop 300,200,700,420]

A view's photograph is the judge's (surfacing_judge/views.json, under blender/tests/terrain/out/); its 2x crop is the
--crop given, else the judge's first crop of the view, else the frame's lower middle. Writes
out/surfacing/material/boards/<case>_<view>_<tag>.jpg. --sheen: a board of check_sheen.py's shot (an orbit frame fNN
or a view) in its variants side by side (out/surfacing/material/sheen/), the light the ground mirrors 4x under each,
then the 2x crop; the photograph is the shot's view's (--photo for an orbit frame: the orbit's view). Writes
out/surfacing/material/boards/sheen_<case>_<shot>.jpg.
"""
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'surfacing', 'material')
VIEWS = os.path.join(TN, 'surfacing_judge', 'views.json')
PLAN_OF = {'canyon': 'canyon', 'alpine_valley': 'alpine_valley', 'lauterbrunnen': 'real_place',
           'meteor_crater': 'impact_crater', 'toroweap': 'canyon', 'fluvial_range': 'fluvial_range'}
W, H = 960, 540


def view_of(case, name):
    plan = json.load(open(VIEWS, encoding='utf-8'))[PLAN_OF.get(case, case)]
    return next(v for v in plan['views'] if v['name'] == name)


def fit(img, w, h):
    """img scaled to cover w x h and centre-cropped."""
    s = max(w / img.width, h / img.height)
    im = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    x0, y0 = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x0, y0, x0 + w, y0 + h))


def board(case, name, tag, crop=None):
    v = view_of(case, name)
    src = {lab: os.path.join(OUT, 'sectors', f'{case}_{name}_{lab}_scan_{tag}.png') for lab in ('today', 'per_texel')}
    if not all(os.path.exists(p) for p in src.values()):
        print(f'[boards] {case}/{name}: no renders tagged {tag}', flush=True)
        return None
    renders = {lab: Image.open(p).convert('RGB') for lab, p in src.items()}
    photo = None
    if v.get('photo'):
        p = os.path.join(TN, 'out', v['photo'])
        if os.path.exists(p):
            photo = fit(Image.open(p).convert('RGB'), W, H)
    box = tuple(crop or (v.get('crops') or [[360, 270, 600, 405]])[0])
    cw, ch = box[2] - box[0], box[3] - box[1]
    cap = 22
    top = [('photograph' + (f" ({os.path.basename(v['photo'])})" if v.get('photo') else ': none'), photo),
           ("today's material", renders['today']), ('per-texel material', renders['per_texel'])]
    out = Image.new('RGB', (3 * W + 20, cap + H + 10 + cap + 2 * ch), (18, 18, 18))
    d = ImageDraw.Draw(out)
    for k, (label, im) in enumerate(top):
        x = k * (W + 10)
        d.text((x + 4, 4), label, fill=(235, 220, 160))
        if im is not None:
            out.paste(im, (x, cap))
    y = cap + H + 10
    d.text((4, y + 4), f'{case} / {name}: 2x crop {box}, today | per-texel', fill=(235, 220, 160))
    for k, lab in enumerate(('today', 'per_texel')):
        out.paste(renders[lab].crop(box).resize((2 * cw, 2 * ch), Image.LANCZOS), (k * (2 * cw + 10), y + cap))
    os.makedirs(os.path.join(OUT, 'boards'), exist_ok=True)
    path = os.path.join(OUT, 'boards', f'{case}_{name}_{tag}.jpg')
    out.save(path, quality=90)
    print(f'[boards] {path}', flush=True)
    return path


def sheen_board(case, shot, variants, photo_view=None, crop=None):
    """check_sheen.py's shot in its variants (module doc): photograph | each variant, the specular 4x under each, and
    a 2x crop of each."""
    src = os.path.join(OUT, 'sheen')
    renders = {v: os.path.join(src, f'{case}_{shot}_{v}.png') for v in variants}
    spec = {v: os.path.join(src, f'{case}_{shot}_{v}_specular_x4.png') for v in variants}
    have = [v for v in variants if os.path.exists(renders[v])]
    if not have:
        print(f'[boards] {case}/{shot}: no check_sheen renders ({", ".join(variants)})', flush=True)
        return None
    photo = None
    try:
        v = view_of(case, photo_view or shot)
        if v.get('photo') and os.path.exists(os.path.join(TN, 'out', v['photo'])):
            photo = fit(Image.open(os.path.join(TN, 'out', v['photo'])).convert('RGB'), W, H)
    except (StopIteration, KeyError):
        v = None
    box = tuple(crop or (((v or {}).get('crops') or [[360, 270, 600, 405]])[0]))
    cw, ch = box[2] - box[0], box[3] - box[1]
    cap = 22
    cols = [('photograph' + (f" ({os.path.basename(v['photo'])})" if v and v.get('photo') else ': none'), photo,
             None)]
    for var in have:
        im = Image.open(renders[var]).convert('RGB')
        sp = Image.open(spec[var]).convert('RGB') if os.path.exists(spec[var]) else None
        cols.append((var, im, sp))
    n = len(cols)
    out = Image.new('RGB', (n * W + (n - 1) * 10, 2 * (cap + H) + 10 + cap + 2 * ch), (18, 18, 18))
    d = ImageDraw.Draw(out)
    for k, (label, im, sp) in enumerate(cols):
        x = k * (W + 10)
        d.text((x + 4, 4), label, fill=(235, 220, 160))
        if im is not None:
            out.paste(im, (x, cap))
        if sp is not None:
            d.text((x + 4, cap + H + 4), f'{label}: the light the ground mirrors, x4', fill=(235, 220, 160))
            out.paste(sp, (x, 2 * cap + H))
    y = 2 * (cap + H) + 10
    d.text((4, y + 4), f'{case} / {shot}: 2x crop {box}, ' + ' | '.join(lab for lab, _i, _s in cols[1:]),
           fill=(235, 220, 160))
    for k, (_lab, im, _sp) in enumerate(cols[1:]):
        out.paste(im.crop(box).resize((2 * cw, 2 * ch), Image.LANCZOS), (k * (2 * cw + 10), y + cap))
    os.makedirs(os.path.join(OUT, 'boards'), exist_ok=True)
    path = os.path.join(OUT, 'boards', f'sheen_{case}_{shot}.jpg')
    out.save(path, quality=90)
    print(f'[boards] {path}', flush=True)
    return path


def main():
    a = sys.argv[1:]

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    if opt('--sheen'):
        case, shot = opt('--sheen').split('/')
        crop = [int(c) for c in opt('--crop').split(',')] if opt('--crop') else None
        ph = opt('--photo')
        sheen_board(case, shot, opt('--variants', 'before,new').split(','),
                    photo_view=ph.split('/')[1] if ph else None, crop=crop)
        return
    tag = opt('--tag', 'r5')
    crops = {}
    for kv in (opt('--crop') or '').split(';'):
        if '=' in kv:
            k, v = kv.split('=', 1)
            crops[k] = [int(c) for c in v.split(',')]
    views = (opt('--views') or '').split(',') if opt('--views') else []
    if not views:
        seen = set()
        for f in sorted(os.listdir(os.path.join(OUT, 'sectors'))):
            if f.endswith(f'_per_texel_scan_{tag}.png'):
                stem = f[:-len(f'_per_texel_scan_{tag}.png')]
                for case in sorted(set(PLAN_OF) | set(json.load(open(VIEWS, encoding='utf-8'))), key=len,
                                   reverse=True):
                    if stem.startswith(case + '_'):
                        seen.add(f'{case}/{stem[len(case) + 1:]}')
                        break
        views = sorted(seen)
    for cv in views:
        case, name = cv.split('/')
        try:
            board(case, name, tag, crops.get(cv))
        except StopIteration:
            print(f'[boards] {cv}: not a judge view', flush=True)


if __name__ == '__main__':
    main()
