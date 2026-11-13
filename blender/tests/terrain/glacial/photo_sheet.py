"""The photo-matched compare sheet: per photograph a row of the photo (cropped to 16:9 about its middle, the lens's
horizontal field kept), the real place's elevation data rendered from the photo's camera, and each generated
terrain from the same camera in the valley's frame (photo_views.py; render_views.py in clay, render_textured.py
with the palettes).

    python blender/tests/terrain/glacial/photo_sheet.py <job.json>[,<job2.json> ...] <sheet.png> [--title text]
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
PHOTOS = os.path.join(TN, 'out', 'glacial', 'photos')
W, H = 640, 360


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def photo_16x9(path):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    hh = int(round(w * 9 / 16))
    if hh <= h:
        top = (h - hh) // 2
        im = im.crop((0, top, w, top + hh))
    return im.resize((W, H), Image.LANCZOS)


def main():
    job_path, out = sys.argv[1], sys.argv[2]
    title = sys.argv[sys.argv.index('--title') + 1] if '--title' in sys.argv else os.path.basename(job_path)
    meta = json.load(open(os.path.join(PHOTOS, 'sources.json'), encoding='utf-8'))['photos']
    rows = {}
    for jp in job_path.split(','):                       # several jobs (clay, textured): one row per photograph
        job = json.load(open(jp, encoding='utf-8'))
        for v in job['views']:
            rows.setdefault(v['photo'], []).append(dict(v, out_dir=job['out_dir']))
    ncols = 1 + max(len(r) for r in rows.values())
    head = 40
    sheet = Image.new('RGB', (ncols * (W + 8) + 8, head + len(rows) * (H + 46)), (22, 22, 22))
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), title, fill=(255, 255, 255), font=font(20))
    f = font(14)
    for r, (photo, views) in enumerate(rows.items()):
        y = head + r * (H + 46)
        ph = next((m for m in meta.values() if m['file'] == photo), None)
        if ph is None:                                   # a view placed in the valley frame (photo_views --axis): the
            cand = json.load(open(os.path.join(PHOTOS, 'candidates.json'), encoding='utf-8'))   # photograph's credit
            c = cand.get(os.path.basename(photo), {})
            ph = dict(title=c.get('title', os.path.basename(photo)).replace('File:', ''), author=c.get('author', '?'),
                      licence=c.get('licence', '?'), lens_mm_36=float('nan'))
        sheet.paste(photo_16x9(os.path.join(PHOTOS, photo)), (8, y + 40))
        d.text((8, y + 2), f"photo: {ph['title'][:70]}", fill=(230, 230, 230), font=f)
        lens = ph['lens_mm_36']
        d.text((8, y + 20), f"{ph['author']}, {ph['licence']} (Wikimedia Commons)" +
               (f"; lens {lens:.0f} mm (36 mm frame)" if lens == lens else '; the same kind of view, not its camera'),
               fill=(170, 170, 170), font=f)
        for k, v in enumerate(views):
            x = 8 + (k + 1) * (W + 8)
            p = os.path.join(v['out_dir'], v['name'] + '.png')
            if 'source' in v:                                # render_views.py: grey clay meshes of the fields
                src = v['source'].get('reference') or os.path.splitext(os.path.basename(v['source']['npz']))[0]
                label = ('the real place: ' if v['source'].get('reference') else 'generated: ') + src
            else:                                            # render_textured.py: make_terrain with its palette
                label = (f"the real place, textured: {(v.get('params') or {}).get('dem')}"
                         if v.get('recipe') == 'real_place' else
                         f"generated, textured: {v.get('recipe')} seed {v.get('seed')}")
            c = v['camera']
            d.text((x, y + 2), label, fill=(230, 230, 230), font=f)
            d.text((x, y + 20), f"camera ({c['x']:.0f}, {c['y']:.0f}) m, heading {c['heading_deg']:.0f}, pitch "
                                f"{c['pitch_deg']:.0f}", fill=(170, 170, 170), font=f)
            if os.path.exists(p):
                sheet.paste(Image.open(p).convert('RGB').resize((W, H), Image.LANCZOS), (x, y + 40))
            else:
                d.text((x + 10, y + 120), 'not rendered', fill=(255, 80, 80), font=f)
    sheet.save(out, quality=90)
    print(out)


main()
