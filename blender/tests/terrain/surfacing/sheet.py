"""Compare sheets for package 6 (system Python: numpy + Pillow): per place, the grey-clay reference views (the rig's
renders of the real DEM) above the textured views of the same DEM with its palette, at the same cameras, labelled
with the palette, the view and the render seconds per frame.

    python blender/tests/terrain/surfacing/sheet.py [--only toroweap,...] [--tag v1] [--out <png>]

Writes out/surfacing/sheet_<place>[_<tag>].png per place and out/surfacing/sheet_all[_<tag>].png (half size).
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
TN = HERE.parent
OUT = TN / 'out' / 'surfacing'
REFR = TN / 'reference' / 'renders'
SHORT = {'toroweap': 'grand_canyon_toroweap', 'lauterbrunnen': 'lauterbrunnen', 'sand_dunes': 'great_sand_dunes',
         'fuji': 'mount_fuji', 'badlands': 'badlands_sd', 'badlands_detail': 'badlands_sd_detail',
         'guilin': 'guilin_karst', 'seven_sisters': 'seven_sisters', 'palouse': 'palouse_hills'}
W, H = 960, 540


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf', 'segoeui.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def tile(path, label, sub=''):
    im = Image.open(path).convert('RGB') if path and Path(path).exists() else Image.new('RGB', (W, H), (40, 40, 40))
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 30 if not sub else 52], fill=(0, 0, 0))
    d.text((8, 4), label, fill=(255, 255, 255), font=font(20))
    if sub:
        d.text((8, 29), sub, fill=(210, 210, 210), font=font(16))
    if not (path and Path(path).exists()):
        d.text((W // 2 - 60, H // 2), 'missing', fill=(255, 120, 120), font=font(24))
    return im


def place_sheet(name, tag):
    t = f'_{tag}' if tag else ''
    rec_path = OUT / f'{name}{t}_record.json'
    rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
    tiles = []
    for v, ref in (('aerial', 'aerial_45deg'), ('eye', 'eye_1p7m')):
        tiles.append(tile(REFR / f'{name}_{ref}.png', f'{name}: {v}, reference DEM in grey clay'))
    for v in ('aerial', 'eye'):
        r = rec.get(v, {})
        png = r.get('png') or next(iter(sorted(OUT.glob(f'{name}_*_{v}{t}.png'))), None)
        sub = ''
        if r:
            sub = (f"palette {r['palette']}; render {r['second_render_s']:.1f} s/frame at {r['samples']} samples "
                   f"(first {r['first_render_s']:.0f} s with the material compile); {r['triangles'] / 1e6:.1f} M tris"
                   + (f"; {r['rocks']} rocks" if r.get('rocks') else ''))
        tiles.append(tile(png, f'{name}: {v}, textured' if png else f'{name}: {v}', sub))
    # photographs of the place, when someone drops them in surfacing/photos/<name>*.jpg|png (no fetch script brings
    # photographs, so they are added by hand): a third row
    photos = sorted(p for p in (HERE / 'photos').glob(f'{name}*') if p.suffix.lower() in ('.jpg', '.jpeg', '.png'))
    for p in photos[:2]:
        tiles.append(tile(p, f'{name}: photograph ({p.name})'))
    rows = (len(tiles) + 1) // 2
    sheet = Image.new('RGB', (2 * W, rows * H), (20, 20, 20))
    for k, im in enumerate(tiles):
        sheet.paste(im, ((k % 2) * W, (k // 2) * H))
    path = OUT / f'sheet_{name}{t}.png'
    sheet.save(path)
    return path, sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='toroweap,lauterbrunnen,sand_dunes,fuji,badlands',
                    help='places, each optionally place:tag (its own render tag)')
    ap.add_argument('--tag', default='')
    ap.add_argument('--name', default=None, help='the overview sheet: sheet_<name>.png')
    a = ap.parse_args()
    sheets = []
    for s in [x for x in a.only.split(',') if x]:
        place, _, tag = s.partition(':')
        p, im = place_sheet(SHORT.get(place, place), tag or a.tag)
        print('[sheet]', p)
        sheets.append(im.resize((W, im.size[1] // 2), Image.LANCZOS))
    if len(sheets) > 1:
        allim = Image.new('RGB', (W, sum(s.size[1] for s in sheets)), (20, 20, 20))
        y = 0
        for im in sheets:
            allim.paste(im, (0, y))
            y += im.size[1]
        p = OUT / (f'sheet_{a.name}.png' if a.name else f"sheet_all{'_' + a.tag if a.tag else ''}.png")
        allim.save(p)
        print('[sheet]', p)


if __name__ == '__main__':
    sys.exit(main())
