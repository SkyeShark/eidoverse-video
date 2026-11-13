"""Photo-beside-render sheets (plain Python, Pillow) from render_views.py's renders and the photographs
(fetch_photos.py), each photo credited with its author and licence on the sheet.

    python blender/tests/terrain/layered_rock/compose_sheets.py fan <reference>
        one row per photo position: the photo, then the real DEM's clay renders at every fan heading
    python blender/tests/terrain/layered_rock/compose_sheets.py views <reference> <tag> [--title "..."]
        one row per view: the photograph | the real DEM from the photo's camera (textured, clay) | the generated
        terrain from its matched camera (textured, clay)

Writes blender/tests/terrain/out/layered_rock/sheets/.
"""
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUTR = os.path.normpath(os.path.join(HERE, '..', 'out', 'layered_rock'))
VIEWS = os.path.join(OUTR, 'views')
PHOTOS = os.path.join(OUTR, 'photos')
SHEETS = os.path.join(OUTR, 'sheets')
PREFIX = {'grand_canyon_toroweap': 'tw', 'goosenecks': 'gn', 'monument_valley': 'mv', 'badlands_sd': 'bl'}


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def fit(path, W, H):
    """The image scaled to cover W x H and centre-cropped (photos are 4:3 or 3:2, renders 16:9)."""
    if not path or not os.path.exists(path):
        im = Image.new('RGB', (W, H), (40, 40, 40))
        ImageDraw.Draw(im).text((10, H // 2), 'not rendered', fill=(200, 200, 200), font=font(16))
        return im
    im = Image.open(path).convert('RGB')
    r = max(W / im.width, H / im.height)
    im = im.resize((max(W, int(im.width * r + 0.5)), max(H, int(im.height * r + 0.5))), Image.LANCZOS)
    x = (im.width - W) // 2
    y = (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def credit(src, key):
    s = src.get(key, {})
    return f"{key}: {s.get('artist', '?')[:48]}, {s.get('license', '?')} (Wikimedia Commons)"


def grid(rows, cols_titles, W, H, title, path):
    """rows: [(row label, [image paths or PIL images], [cell captions])]."""
    head = 34
    cap = 20
    img = Image.new('RGB', (len(cols_titles) * (W + 6) + 6, head + 22 + len(rows) * (H + cap + 26)), (22, 22, 22))
    d = ImageDraw.Draw(img)
    d.text((8, 6), title, fill=(255, 255, 255), font=font(20))
    for k, t in enumerate(cols_titles):
        d.text((6 + k * (W + 6), head), t, fill=(200, 200, 200), font=font(15))
    y = head + 22
    for label, cells, caps in rows:
        d.text((6, y), label, fill=(235, 235, 235), font=font(15))
        for k, c in enumerate(cells):
            im = c if isinstance(c, Image.Image) else fit(c, W, H)
            img.paste(im, (6 + k * (W + 6), y + 20))
            if caps and k < len(caps) and caps[k]:
                d.text((10 + k * (W + 6), y + 22 + H - 18), caps[k], fill=(255, 255, 160), font=font(13))
        y += H + cap + 26
    os.makedirs(SHEETS, exist_ok=True)
    img.save(path, quality=90)
    return path


def fan(reference):
    src = json.load(open(os.path.join(PHOTOS, 'sources.json'), encoding='utf-8'))
    rows = []
    for photo in sorted({os.path.basename(p).split('_')[1] + '_' + os.path.basename(p).split('_')[2]
                         for p in glob.glob(os.path.join(VIEWS, f'fan_{PREFIX[reference]}_*.png'))}):
        fans = sorted(glob.glob(os.path.join(VIEWS, f'fan_{photo}_*.png')))
        cells = [os.path.join(PHOTOS, photo + '.jpg')] + fans
        caps = [credit(src, photo)] + ['heading ' + os.path.splitext(f)[0].rsplit('_', 1)[1] for f in fans]
        rows.append((photo, cells, caps))
    if not rows:
        print('no fan renders for', reference)
        return None
    ncol = max(len(r[1]) for r in rows)
    # wrap long rows in two
    out = []
    for label, cells, caps in rows:
        half = (len(cells) + 1) // 2
        out.append((label, cells[:half], caps[:half]))
        out.append((label + ' (cont.)', [cells[0]] + cells[half:], [caps[0]] + caps[half:]))
    return grid(out, ['photo'] + [''] * (min(ncol, (ncol + 1) // 2 + 1) - 1), 380, 214,
                f'{reference}: camera fit, the real DEM in clay from the photo position', os.path.join(
                    SHEETS, f'{reference}_fan.png'))


def views(reference, tag, title=None):
    """The generated renders are read under <reference>_<tag> (render_views.py keys them so): with the tag alone the
    Monument Valley sheet was built from the Badlands' cameras, photographs and renders. A camera whose photograph
    is not this reference's (its prefix) stops the sheet."""
    src = json.load(open(os.path.join(PHOTOS, 'sources.json'), encoding='utf-8'))
    sys.path.insert(0, HERE)
    stem = f'{reference}_{tag}'
    vr = json.load(open(os.path.join(VIEWS, f'{stem}_views.json'), encoding='utf-8'))
    if vr.get('reference') not in (None, reference):
        raise ValueError(f"{stem}_views.json holds views of {vr.get('reference')}, not {reference}")
    rr = json.load(open(os.path.join(VIEWS, f'{reference}_views.json'), encoding='utf-8')) \
        if os.path.exists(os.path.join(VIEWS, f'{reference}_views.json')) else {}
    names = list((vr.get('cameras') or {}).keys()) or list((rr.get('cameras') or {}).keys())
    for nm in names:
        photo = ((vr.get('cameras') or {}).get(nm, {}).get('photo')
                 or (rr.get('cameras') or {}).get(nm, {}).get('photo'))
        if photo and not str(photo).startswith(PREFIX[reference] + '_'):
            raise ValueError(f'view {nm!r} of {stem} uses photograph {photo}, not one of {reference} '
                             f'({PREFIX[reference]}_*)')
    tag = stem
    rows = []
    for nm in names:
        cg = (vr.get('cameras') or {}).get(nm, {})
        photo = cg.get('photo') or (rr.get('cameras') or {}).get(nm, {}).get('photo')
        m = cg.get('match') or {}
        rel = cg.get('relation') or {}
        gen_cap = ''
        if m:
            gen_cap = (f"generated: {m.get('dist', 0):.0f} m from the {'river' if rel.get('kind') == 'river' else 'target'}"
                       + (f", {m.get('above', 0):.0f} m above it" if 'above' in m else
                          f", {m.get('above_floor', 0):.0f} m above the floor") + f", lens {m.get('lens', 0):.0f} mm")
        ref_cap = ''
        if rel:
            ref_cap = (f"real: {rel.get('dist', 0):.0f} m from the {'river' if rel.get('kind') == 'river' else 'target'}"
                       + (f", {rel.get('above', 0):.0f} m above it" if 'above' in rel else
                          f", {rel.get('above_floor', 0):.0f} m above the floor"))
        cells = [os.path.join(PHOTOS, f'{photo}.jpg'), os.path.join(VIEWS, f'{reference}_{nm}.png'),
                 os.path.join(VIEWS, f'{reference}_{nm}_clay.png'), os.path.join(VIEWS, f'{tag}_{nm}.png'),
                 os.path.join(VIEWS, f'{tag}_{nm}_clay.png')]
        rows.append((nm, cells, [credit(src, photo), ref_cap, '', gen_cap, '']))
    return grid(rows, ['photograph', 'real DEM, the photo\'s camera', 'real DEM, clay',
                       f'generated ({tag}), matched camera', 'generated, clay'], 420, 236,
                title or f'{reference} vs {tag}: photograph, real DEM and generated terrain under make_sky daylight',
                os.path.join(SHEETS, f'{tag}_views.png'))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'fan':
        print(fan(a[1]))
    else:
        t = a[a.index('--title') + 1] if '--title' in a else None
        print(views(a[1], a[2], t))
