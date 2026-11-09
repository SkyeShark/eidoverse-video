"""Package 9's render compare sheets: each reference's three probe views above the analytic shape's three.

    python blender/tests/terrain_new/volcanoes_craters/compare_sheets.py

Reads reference/renders/<name>_* (the real DEMs; SP Crater's from out/volcanoes_craters/renders/sp_crater_real_*,
rendered by render_views.py with the same rig) and out/volcanoes_craters/renders/gen_<name>_*, and writes
out/volcanoes_craters/<name>_compare_sheet.png (top hillshade, 45-degree aerial, 1.7 m eye view; grey clay under
make_sky daylight), plus cinder_field_preview_sheet.png. Plain Python (Pillow).
"""
import os

from PIL import Image, ImageDraw, ImageFont

import _common as C

RENDERS = os.path.join(C.OUT, 'renders')
REF_RENDERS = os.path.join(C.REFERENCE_DIR, 'renders')
VIEWS = ('top_hillshade', 'aerial_45deg', 'eye_1p7m')
H = 300                                                   # each panel's height on the sheet
BG, INK, INK2 = (24, 24, 23), (240, 239, 236), (195, 194, 183)

ROWS = {
    'mount_fuji': ('REAL  Mount Fuji, GSI DEM10B at 40 m', 'ANALYTIC  FUJI preset: exponential cone (H 2983 m on a 755 m '
                   'foot, lambda 4215 m), crater, Hoei crater, 18 rift cones; placeholder plain'),
    'crater_lake': ('REAL  Crater Lake, 3DEP at 14 m', 'ANALYTIC  CRATER_LAKE preset: Mazama edifice, scalloped ring '
                    'collapse, rock walls 38 deg over talus 33 deg, floor 1300 m, lake 1880.5 m, Wizard Island'),
    'meteor_crater': ('REAL  Meteor Crater, 3DEP at 3 m', 'ANALYTIC  METEOR_CRATER preset: Pike bowl 0.2 D, infill to '
                      '0.143 D, rim 0.044 D, square planform, (r/R)^-3 ejecta with hummocks; placeholder plain'),
    'sp_crater': ('REAL  SP Crater, Terrain Tiles (3DEP 10 m) at 7.8 m', 'ANALYTIC  SP_CRATER preset: Wood cone, H/W '
                  '0.18, crater 0.28 W, 32 deg flank with concave toe, 30 deg crater walls; placeholder plain'),
}


def font(size):
    for f in ('consola.ttf', 'DejaVuSansMono.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def row_image(paths, label):
    ims = []
    for p in paths:
        if os.path.exists(p):
            im = Image.open(p).convert('RGB')
            ims.append(im.resize((int(im.width * H / im.height), H)))
        else:
            im = Image.new('RGB', (H * 16 // 9, H), (60, 20, 20))
            ImageDraw.Draw(im).text((12, H // 2), 'missing: ' + os.path.basename(p), fill=INK, font=font(14))
            ims.append(im)
    w = sum(i.width for i in ims) + 6 * (len(ims) - 1)
    out = Image.new('RGB', (w, H + 30), BG)
    ImageDraw.Draw(out).text((8, 6), label, fill=INK, font=font(15))
    x = 0
    for i in ims:
        out.paste(i, (x, 30))
        x += i.width + 6
    return out


def sheet(name, ref_paths, gen_paths, ref_label, gen_label, note):
    a, b = row_image(ref_paths, ref_label), row_image(gen_paths, gen_label)
    w = max(a.width, b.width)
    out = Image.new('RGB', (w, a.height + b.height + 34), BG)
    out.paste(a, (0, 0))
    out.paste(b, (0, a.height + 4))
    ImageDraw.Draw(out).text((8, a.height + b.height + 10), note, fill=INK2, font=font(13))
    path = os.path.join(C.OUT, f'{name}.png')
    out.save(path)
    print('wrote', path)


def main():
    note = ('grey clay, make_sky daylight (15:30), top / 45-degree aerial / 1.7 m eye; the analytic row is the '
            'constructional start: gullies, talus, aprons, lava flows and aging come with the second half')
    for name, (ref_label, gen_label) in ROWS.items():
        if name == 'sp_crater':
            ref = [os.path.join(RENDERS, f'sp_crater_real_{v}.png') for v in VIEWS]
        else:
            ref = [os.path.join(REF_RENDERS, f'{name}_{v}.png') for v in VIEWS]
        gen = [os.path.join(RENDERS, f'gen_{name}_{v}.png') for v in VIEWS]
        sheet(f'{name}_compare_sheet', ref, gen, ref_label, gen_label, note)
    gen = [os.path.join(RENDERS, f'gen_cinder_field_{v}.png') for v in VIEWS]
    a = row_image(gen, 'PREVIEW  cinder field: 12 fresh cones along 2 vent lines, some breached, lobate footprints '
                       '(aging and lava flows come later); placeholder lava plateau')
    path = os.path.join(C.OUT, 'cinder_field_preview_sheet.png')
    a.save(path)
    print('wrote', path)


if __name__ == '__main__':
    main()
