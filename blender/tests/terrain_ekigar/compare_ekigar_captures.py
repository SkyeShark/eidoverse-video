"""Like-for-like look comparison: Ekigar's own visual-regression captures beside the port's gallery renders of the same
operator, same fixture, same camera (out/gallery/_compare_ekigar_<k>.png, then the index of what each pair can show).

Ekigar's captures are WebGPU readbacks written top row first, so they are stored upside down: they are flipped here.
Each pair is labelled with the capture's date and the modification date of the Ekigar source that defines the operator:
a capture older than its source shows an earlier version of that operator, so a difference in form there is Ekigar's
own later edit, not a port defect (the field parity tests run the CURRENT source). Only pairs whose capture is newer
than their source can support a look-match claim.

    python blender/tests/terrain_ekigar/compare_ekigar_captures.py [grey|shaded]
"""
import datetime
import glob
import os
import re
import sys

from PIL import Image, ImageDraw

import _ekigar_load

OUT = os.path.join(_ekigar_load.OUT, 'gallery')
EK = _ekigar_load.EKIGAR_ROOT
mode = sys.argv[1] if len(sys.argv) > 1 else 'shaded'
SETS = ['current', 'landform-detail-final', 'wave1-review2', 'wave2-review', 'wave3-review3', 'wave4-final',
        'wave4-tuned2']
SOURCES = {'wave1': 'src/core/landforms_wave1.js', 'wave2': 'src/core/landforms_wave2.js',
           'wave3': 'src/core/landforms_wave3.js', 'wave4': 'src/core/landforms_wave4.js'}


def source_of(op):
    """The Ekigar file that defines an operator: a landform wave file when it is a landform there, else registry.js."""
    for key, rel in SOURCES.items():
        with open(os.path.join(EK, rel), encoding='utf-8') as f:
            if re.search(rf'\b{re.escape(op)}\s*:\s*(\{{|landform\(|op\()', f.read()):
                return rel
    return 'src/core/registry.js'


def mtime(path):
    return datetime.datetime.fromtimestamp(os.path.getmtime(path))


captures = {}                                  # op -> newest capture path
for s in SETS:
    for p in glob.glob(os.path.join(EK, 'output', 'visual-regression', s, '*.png')):
        m = re.match(r'\d+-[a-z]+-(.+)\.png$', os.path.basename(p))
        if not m or m.group(1).startswith('fixture'):
            continue
        op = m.group(1)
        if op not in captures or mtime(p) > mtime(captures[op]):
            captures[op] = p
port = {}
for p in glob.glob(os.path.join(OUT, mode, '*.png')):
    op = os.path.splitext(os.path.basename(p))[0].split('_', 1)[1]
    port[op] = p
pairs = [op for op in sorted(captures, key=lambda o: os.path.basename(port.get(o, 'zz'))) if op in port]
W, H, LAB = 320, 240, 26
rows = []
for op in pairs:
    src = source_of(op)
    cap_t, src_t = mtime(captures[op]), mtime(os.path.join(EK, src))
    newer = cap_t >= src_t
    rows.append((op, src, cap_t, src_t, newer))
per = 12
for k in range(0, len(rows), per):
    chunk = rows[k:k + per]
    sheet = Image.new('RGB', (2 * W * 2, (H + LAB) * -(-len(chunk) // 2)), (11, 15, 20))
    for i, (op, src, cap_t, src_t, newer) in enumerate(chunk):
        ek_im = Image.open(captures[op]).convert('RGB').transpose(Image.FLIP_TOP_BOTTOM).resize((W, H))
        pt_im = Image.open(port[op]).convert('RGB').resize((W, H))
        x0 = (i % 2) * 2 * W
        y0 = (i // 2) * (H + LAB)
        sheet.paste(ek_im, (x0, y0 + LAB))
        sheet.paste(pt_im, (x0 + W, y0 + LAB))
        d = ImageDraw.Draw(sheet)
        colour = (160, 230, 160) if newer else (255, 170, 120)
        d.text((x0 + 4, y0 + 2), f'{op}: Ekigar capture {cap_t:%m-%d %H:%M} (flipped) | port, EEVEE {mode}',
               fill=(255, 230, 160))
        d.text((x0 + 4, y0 + 13), f'{src} edited {src_t:%m-%d %H:%M}: '
               + ('capture is current' if newer else 'capture predates the source'), fill=colour)
    path = os.path.join(OUT, f'_compare_ekigar_{k // per}.png')
    sheet.save(path)
    print(path)
cur = [r[0] for r in rows if r[4]]
old = [r[0] for r in rows if not r[4]]
print(f'{len(rows)} pairs; capture newer than its source (a look comparison can stand): {", ".join(cur) or "none"}')
print(f'capture older than its source (Ekigar edited the operator later): {", ".join(old) or "none"}')
