"""Contact sheet of the prototype hillshades with their slope statistics: python sheet.py -> out/_sheet_spl.png"""
import json
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
PANELS = [   # (file tag, label)
    ('spl_gather_256', 'A  gather, min-plus clip Sc 36deg (D8 facets)'),
    ('spl_gather_256_diffusion', 'B  gather, creep D=0.02 (corduroy)'),
    ('spl_gather_256_diffusion_D0.5', 'C  gather, creep D=0.5 (mush)'),
    ('spl_implicit_256_D0.5', 'D  implicit D8, D=0.5 (straight valleys)'),
    ('spl_gather_256_diffusion_D0.1', 'E  gather, D=0.1, flat start, 5 Myr'),
    ('spl_implicit_256_D0.1', 'F  implicit D8, D=0.1, flat start, 5 Myr'),
    ('spl_gather_256_diffusion_D0.1_K2e-05_U0.002_dt1000_dome', 'G  gather, D=0.1, K x5, U x2, dome start'),
    ('spl_gather_256_diffusion_D0.04_K2e-05_U0.002_dt1000_dome', 'H  gather, D=0.04, K x5, U x2, dome start'),
    ('spl_gather_256_diffusion_D0.04_K1e-05_U0.003_dt1000_dome', 'I  gather, D=0.04, K x2.5, U x3, dome start'),
]
S = 384
COLS = 4
rows = (len(PANELS) + COLS - 1) // COLS
sheet = Image.new('RGB', (COLS * S, rows * (S + 34)), (20, 20, 24))
d = ImageDraw.Draw(sheet)
for i, (tag, label) in enumerate(PANELS):
    x, y = (i % COLS) * S, (i // COLS) * (S + 34)
    img = Image.open(os.path.join(OUT, f'hillshade_{tag}.png')).convert('RGB').resize((S, S), Image.NEAREST)
    sheet.paste(img, (x, y + 34))
    m = json.load(open(os.path.join(OUT, tag + '.json')))
    d.text((x + 4, y + 2), label, fill=(255, 220, 140))
    d.text((x + 4, y + 17), f"relief {m['relief_m']:.0f} m  slope p50 {m['slope_p50']:.0f} p90 {m['slope_p90']:.0f}"
           f"  >40: {100 * m['frac_slope_gt40']:.1f}%  <5: {100 * m['frac_slope_lt5']:.0f}%  pits {m['depression_area_frac']:.3f}",
           fill=(200, 200, 200))
sheet.save(os.path.join(OUT, '_sheet_spl.png'))
print('ok')
