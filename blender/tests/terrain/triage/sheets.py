"""Contact sheets of the triage renders: one row per subject (top | 45-degree aerial | 1.7 m eye level), four rows a
sheet, labelled with the subject, what its name promises, the tile size, the relief and the texel size; plus
comparison sheets that put each real-elevation reference beside the Ekigar subjects that claim to be that landform.

    python sheets.py            # sheets/<group>_<k>.png and sheets/compare_<k>.png
"""
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scenes  # noqa: E402

TOP, WIDE, H, LABEL = 300, 533, 300, 30
ROW_W = TOP + 2 * WIDE + 8
GROUP_SHEETS = [('landform', 'landforms'), ('operator', 'operators'), ('mask', 'mask_operators'),
                ('erosion', 'erosion'), ('maskstudy', 'mask_study'), ('graph', 'graphs'), ('reference', 'real')]
COMPARE = [('real_fuji', ['volcano', 'volcano_smooth', 'graph_fbm_then_volcano']),
           ('real_goosenecks', ['canyon', 'canyon_narrow', 'graph_range_then_canyon']),
           ('real_great_sand_dunes', ['duneField_star', 'duneField_star_f9', 'duneField_transverse']),
           ('real_yosemite', ['glacialTrough', 'graph_range_then_trough', 'graph_alpine_valley']),
           ('real_alps', ['mountainRange_alpine', 'mountain_alpine', 'ero_mountainRange_phacelle']),
           ('real_sp_crater', ['cinderConeField', 'lavaField', 'volcano_cone']),
           ('real_meteor_crater', ['crater', 'impactCrater', 'maar']),
           ('real_monument_valley', ['mesa', 'volcanicPlug', 'bornhardt']),
           ('real_badlands', ['badlands', 'default_project', 'op_phacelle'])]


def font(size):
    for f in ('C:/Windows/Fonts/consola.ttf', 'C:/Windows/Fonts/arial.ttf'):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


F1, F2 = font(15), font(13)


def tile(path, w, h):
    if os.path.exists(path):
        return Image.open(path).convert('RGB').resize((w, h), Image.LANCZOS)
    im = Image.new('RGB', (w, h), (40, 20, 20))
    ImageDraw.Draw(im).text((8, 8), 'missing', fill=(255, 120, 120), font=F2)
    return im


def row(name, index, metrics=None):
    s = scenes.BY_NAME[name]
    r = index.get(name, {})
    a = (metrics or {}).get(name)
    im = Image.new('RGB', (ROW_W, H + LABEL), (14, 16, 20))
    d = ImageDraw.Draw(im)
    W = r.get('W', s['W'])
    rel = r.get('relief_m')
    tex = r.get('texel_m')
    info = f"tile {W / 1000:g} km" + (f"  relief {rel:,.0f} m" if rel is not None else '') + \
           (f"  texel {tex:.2f} m" if tex is not None else '')
    if r.get('ov_range'):
        info += f"  mask {r['ov_range'][0]:.2f}..{r['ov_range'][1]:.2f}"
    if a:
        info += (f"  |  slope p50 {a['slope_p50']:.0f} p99 {a['slope_p99']:.0f} deg, >60 deg {a['cliff_pct']:.1f}%, "
                 f"untouched plane {a['base_pct']:.0f}%")
        if 'lake_pct' in a:
            info += f", would fill as lakes {a['lake_pct']:.0f}%"
    d.text((6, 2), name, fill=(255, 220, 140), font=F1)
    d.text((6 + 9 * len(name) + 14, 3), s['promise'][:110], fill=(200, 205, 215), font=F2)
    d.text((6, 16), info, fill=(150, 160, 175), font=F2)
    base = os.path.join(scenes.RENDERS, name)
    im.paste(tile(base + '__top.png', TOP, TOP), (0, LABEL))
    im.paste(tile(base + '__aerial.png', WIDE, H), (TOP + 4, LABEL))
    im.paste(tile(base + '__eye.png', WIDE, H), (TOP + WIDE + 8, LABEL))
    return im


def sheet(names, path, index, per=4, metrics=None):
    out = []
    for k in range(0, len(names), per):
        chunk = names[k:k + per]
        im = Image.new('RGB', (ROW_W, len(chunk) * (H + LABEL + 6)), (6, 8, 10))
        for i, n in enumerate(chunk):
            im.paste(row(n, index, metrics), (0, i * (H + LABEL + 6)))
        p = f'{path}_{k // per:02d}.png'
        im.save(p)
        out.append(p)
    return out


if __name__ == '__main__':
    os.makedirs(scenes.SHEETS, exist_ok=True)
    for f in glob.glob(os.path.join(scenes.SHEETS, '*.png')):
        os.remove(f)
    ip = os.path.join(scenes.RENDERS, 'index.json')
    index = json.load(open(ip)) if os.path.exists(ip) else {}
    ap = os.path.join(scenes.RENDERS, 'analysis.json')
    metrics = json.load(open(ap)) if os.path.exists(ap) else {}
    for g, label in GROUP_SHEETS:
        names = [s['name'] for s in scenes.SUBJECTS if s['group'] == g]
        for p in sheet(names, os.path.join(scenes.SHEETS, label), index, metrics=metrics):
            print(p)
    for k, (ref, gens) in enumerate(COMPARE):
        for p in sheet([ref] + gens, os.path.join(scenes.SHEETS, f'compare_{k}_{ref[5:]}'), index, metrics=metrics):
            print(p)
