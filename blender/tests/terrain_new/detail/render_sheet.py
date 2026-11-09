"""Compare sheets of the detail renders (plain Python, Pillow): one per view, the variants as rows and grey clay /
the alpine palette as columns, each panel labelled.

    python -I blender/tests/terrain_new/detail/render_sheet.py --tag r1 [--variants upsampled,detail,full]
        [--views eye,wall,slope,ground]

Writes out/detail/renders/<tag>_<view>_sheet.png (each panel at half size).
"""
import os
import site
import sys

sys.path.append(site.getusersitepackages())
from PIL import Image, ImageDraw  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REN = os.path.normpath(os.path.join(HERE, '..', 'out', 'detail', 'renders'))
LABEL = {'upsampled': 'the DEM upsampled (no detail)', 'detail': 'rock breakup + hydraulic (this package)',
         'full': 'fluvial refine + talus (package 3) + breakup + hydraulic', 'nodetail': 'fluvial_range, no detail',
         'clay': 'grey clay', 'alpine': 'alpine palette + rocks'}


def main():
    a = sys.argv[1:]
    get = (lambda k, d: a[a.index(k) + 1] if k in a else d)
    tag = get('--tag', 'r1')
    variants = get('--variants', 'upsampled,detail,full').split(',')
    views = get('--views', 'eye,wall,slope,ground').split(',')
    for view in views:
        rows = []
        for v in variants:
            row = []
            for look in ('clay', 'alpine'):
                p = os.path.join(REN, f'{tag}_{v}_{view}_{look}.png')
                if not os.path.exists(p):
                    continue
                im = Image.open(p).convert('RGB')
                im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
                d = ImageDraw.Draw(im)
                txt = f'{v}: {LABEL.get(v, v)} | {LABEL[look]}'
                d.rectangle([0, 0, 8 + 6 * len(txt), 16], fill=(0, 0, 0))
                d.text((4, 2), txt, fill=(255, 255, 255))
                row.append(im)
            if row:
                rows.append(row)
        if not rows:
            continue
        w, h = rows[0][0].size
        sheet = Image.new('RGB', (2 * w + 4, len(rows) * (h + 4) - 4), (255, 255, 255))
        for r, row in enumerate(rows):
            for c, im in enumerate(row):
                sheet.paste(im, (c * (w + 4), r * (h + 4)))
        out = os.path.join(REN, f'{tag}_{view}_sheet.png')
        sheet.save(out)
        print('[render_sheet]', out, flush=True)


if __name__ == '__main__':
    main()
