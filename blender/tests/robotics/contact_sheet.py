"""A labelled contact sheet of a folder of PNG stills (system Python with Pillow; tests only).

    python contact_sheet.py <folder> <out.png> [--cols 8] [--label-map labels.json]
"""

import json
import os
import sys

from PIL import Image, ImageDraw


def main():
    a = sys.argv[1:]
    folder, out = a[0], a[1]
    cols = int(a[a.index('--cols') + 1]) if '--cols' in a else 8
    labels = {}
    if '--label-map' in a:
        labels = json.load(open(a[a.index('--label-map') + 1], encoding='utf-8'))
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith('.png'))
    if not files:
        raise SystemExit('no stills in ' + folder)
    ims = [Image.open(os.path.join(folder, f)).convert('RGB') for f in files]
    w, h = ims[0].size
    lab = 16
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * w, rows * (h + lab)), (24, 26, 28))
    d = ImageDraw.Draw(sheet)
    for i, (f, im) in enumerate(zip(files, ims)):
        x, y = (i % cols) * w, (i // cols) * (h + lab)
        sheet.paste(im.resize((w, h)), (x, y))
        name = labels.get(f, f[:-4].replace('__', '/'))
        d.text((x + 3, y + h + 2), name[:int(w / 6.2)], fill=(220, 224, 226))
    sheet.save(out)
    print(out, sheet.size, len(ims))


if __name__ == '__main__':
    main()
