"""Assemble the sky_matrix.py cells into one labelled sheet (system Python + Pillow).

    python blender/tests/sky/contact_sheet_matrix.py [out/matrix] [--cols 4]
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith('--')]
cols = int(sys.argv[sys.argv.index('--cols') + 1]) if '--cols' in sys.argv else 4
d = args[0] if args else os.path.join(HERE, 'out', 'matrix')
order = []
for clouds in ('cumulus', 'stratus', 'cirrus', 'clear'):
    order += ['%s_%s' % (clouds, t) for t in ('1200', '1630', '1809', '2200')]
order += ['%s_1500' % w for w in ('fair', 'sunshower', 'overcast', 'rain', 'storm', 'cyclone', 'darkstorm')]
cells = [(n, os.path.join(d, n + '.png')) for n in order if os.path.exists(os.path.join(d, n + '.png'))]
if not cells:
    sys.exit('no cells in ' + d)
w, h = Image.open(cells[0][1]).size
rows = (len(cells) + cols - 1) // cols
sheet = Image.new('RGB', (cols * w, rows * (h + 18)), (20, 20, 20))
draw = ImageDraw.Draw(sheet)
for i, (name, path) in enumerate(cells):
    x, y = (i % cols) * w, (i // cols) * (h + 18)
    sheet.paste(Image.open(path).convert('RGB'), (x, y + 18))
    draw.text((x + 4, y + 3), name, fill=(230, 230, 230))
out = os.path.join(d, 'matrix_sheet.png')
sheet.save(out)
print(out, sheet.size)
