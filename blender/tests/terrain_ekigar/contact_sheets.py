"""Labelled contact sheets of the gallery, hero, variant and probe renders, for looking at them
(out/gallery/_sheet_<mode>_<k>.png, out/heroes/_sheet.png, out/variants/_sheet_<k>.png, out/probes/_sheet.png).

    python blender/tests/terrain_ekigar/contact_sheets.py
"""
import glob
import os

from PIL import Image, ImageDraw

import _ekigar_load

OUT = _ekigar_load.OUT


def sheet(files, path, cols=5, w=320, h=240):
    rows = -(-len(files) // cols)
    s = Image.new('RGB', (cols * w, rows * h), (11, 15, 20))
    for i, f in enumerate(files):
        im = Image.open(f).convert('RGB').resize((w, h), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, w, 12], fill=(0, 0, 0))
        d.text((3, 0), os.path.splitext(os.path.basename(f))[0], fill=(255, 230, 160))
        s.paste(im, ((i % cols) * w, (i // cols) * h))
    s.save(path)
    return path


for mode in ('grey', 'shaded'):
    fs = sorted(glob.glob(os.path.join(OUT, 'gallery', mode, '*.png')))
    for k in range(0, len(fs), 20):
        print(sheet(fs[k:k + 20], os.path.join(OUT, 'gallery', f'_sheet_{mode}_{k // 20}.png')))
hs = sorted(glob.glob(os.path.join(OUT, 'heroes', '*.png')))
hs = [f for f in hs if not os.path.basename(f).startswith('_')]
if hs:
    print(sheet(hs, os.path.join(OUT, 'heroes', '_sheet.png'), cols=3, w=480, h=270))
vs = [f for f in sorted(glob.glob(os.path.join(OUT, 'variants', '*.png'))) if not os.path.basename(f).startswith('_')]
for k in range(0, len(vs), 20):
    print(sheet(vs[k:k + 20], os.path.join(OUT, 'variants', f'_sheet_{k // 20}.png')))
ps = [f for f in sorted(glob.glob(os.path.join(OUT, 'probes', '*.png'))) if not os.path.basename(f).startswith('_')]
if ps:
    print(sheet(ps, os.path.join(OUT, 'probes', '_sheet.png'), cols=2, w=960, h=540))
