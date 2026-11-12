"""Every recipe's review sheet, end to end on the finished family (design section 11, row 13). System Python; it
starts Blender itself, through the GPU slot:

    python blender/tests/terrain/integration/recipe_sheets.py                    # every recipe
    python blender/tests/terrain/integration/recipe_sheets.py --recipes canyon,dunes
    python blender/tests/terrain/integration/recipe_sheets.py --compose-only      # the sheets again, no Blender

Per recipe, two steps:
1. the judge (judge/run.py, in this process): make_terrain at its real place's extent (seed 1, film quality), the
   numbers against the place's bands, the reference rig's three clay views of the place and of the recipe (top-down
   hillshade, 45-degree aerial, 1.7 m eye), the recipe rebuilt with its focus on the eye spot (the hero levels'
   eye view) and in its palette with rocks (the textured aerial and eye). The meadow has no elevation data at its
   scale: its views come from the fluvial package's meadow cameras (fluvial/render_eye.py: eye, over, ground, in
   its palette with the probe's test grass).
2. the sheet: photographs of the real place on top (CC0 / public domain fetched by fetch_photos.py, or the
   packages' own Commons photographs with their licences), then the package's renders from those photographs'
   cameras where it made them (the real DEM and the recipe, same camera, same light), then the judge's sheet:
   the place's views and numbers above the recipe's.

Writes blender/tests/terrain/out/integration/sheets/<recipe>.jpg, sheets/overview.jpg (every recipe in one row: a
photograph, the place at 1.7 m, the recipe at 1.7 m and from the air), the judge's files in sheets/judge/<recipe>/
and sheets/index.json (per recipe: bands passed, the failures, the seconds). GPU: the main checkout's slots
(heavy.sh, then heavy2.sh, then heavy3.sh; --slots heavy.sh keeps to one), retried every 60 s while all are busy.
"""
import argparse
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)

from PIL import Image, ImageDraw  # noqa: E402

from judge import refs  # noqa: E402
from judge import run as JR  # noqa: E402
from judge.sheet import BG, DIM, GOLD, GOOD, BAD, INK, font, wrap  # noqa: E402

OUT_ROOT = os.path.join(TN, 'out')
OUT = os.path.join(OUT_ROOT, 'integration', 'sheets')

# recipe: the place it is judged against (its first reference), the photographs (source, place or file prefix, which
# ones), the package's photo-matched sheets (newest first: the first that exists is used) and knobs for the judge
RECIPES = {
    'fluvial_range': dict(ref='san_gabriel_mountains', photos=('integration', 'san_gabriel_mountains', (2, 3, 1, 4))),
    'alpine_valley': dict(ref='lauterbrunnen', photos=('glacial', 'lauterbrunnen', (1, 13, 0, 5)),
                          matched=[['glacial/photo_views/sheet_final_lauterbrunnen.jpg'],
                                   ['glacial/photo_views/sheet_final_yosemite.jpg']]),
    'stratovolcano': dict(ref='mount_fuji', photos=('volcano', 'mount_fuji', None),
                          matched=[['volcanoes_craters/photo_views/mount_fuji_photo_sheet.png']]),
    'caldera': dict(ref='crater_lake', photos=('volcano', 'crater_lake', None),
                    matched=[['volcanoes_craters/photo_views/crater_lake_photo_sheet.png']]),
    'cinder_cones': dict(ref='sp_crater', photos=('volcano', 'sp_crater', None),
                         matched=[['volcanoes_craters/photo_views/sp_crater_photo_sheet.png']]),
    'impact_crater': dict(ref='meteor_crater', photos=('volcano', 'meteor_crater', None),
                          matched=[['volcanoes_craters/photo_views/meteor_crater_photo_sheet.png']]),
    'canyon': dict(ref='grand_canyon_toroweap', photos=('layered', 'tw_', (1, 3, 4, 7)),
                   matched=[['layered_rock/sheets/grand_canyon_toroweap_v3_views.png',
                             'layered_rock/sheets/grand_canyon_toroweap_v2_views.png',
                             'layered_rock/sheets/grand_canyon_toroweap_v1_views.png']]),
    'incised_meanders': dict(ref='goosenecks', photos=('layered', 'gn_', (1, 3, 4, 6)),
                             matched=[['layered_rock/sheets/goosenecks_v1_views.png']]),
    'mesas_buttes': dict(ref='monument_valley', photos=('layered', 'mv_', (1, 2, 3, 6)),
                         matched=[['layered_rock/sheets/monument_valley_v1_views.png']]),
    'badlands': dict(ref='badlands_sd', photos=('layered', 'bl_', (1, 2, 4, 5)),
                     matched=[['layered_rock/sheets/badlands_sd_v1_views.png']]),
    'dunes': dict(ref='namib_star_dunes', photos=('integration', 'namib_star_dunes', (1, 2, 3, 4)),
                  photos2=('integration', 'great_sand_dunes', (1, 2, 3))),
    'tower_karst': dict(ref='guilin_karst', photos=('integration', 'guilin_karst', (3, 2, 5, 6))),
    'sea_cliffs': dict(ref='seven_sisters', photos=('coast', 'ss_', None),
                       matched=[['coast/sheets/seven_sisters_photos_vs_sea_cliffs_chalk_seed1.png'],
                                ['coast/sheets/cliffs_of_moher_photos_vs_sea_cliffs_layered_seed1.png']]),
    'rolling_hills': dict(ref='palouse_hills', photos=('integration', 'palouse_hills', (1, 2, 3, 4))),
    'real_place': dict(ref='lauterbrunnen', photos=('glacial', 'lauterbrunnen', (1, 13, 0, 5))),
    'meadow': dict(ref=None),
}
W = 1950                    # the judge sheet's width: every block is scaled to it
PHOTO_H = 330


# ------------------------------------------------------------------------------------------------- photographs ---

def _glacial_records():
    p = os.path.join(OUT_ROOT, 'glacial', 'photos', 'candidates.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def photos_for(spec):
    """[(path, caption, credit)] for a (source, place-or-prefix, picks) spec; picks are 1-based numbers in the
    source's order (glacial: the file numbers), None = all."""
    if not spec:
        return []
    src, key, picks = spec
    out = []
    if src in ('integration', 'volcano'):
        d = os.path.join(OUT_ROOT, 'integration' if src == 'integration' else 'volcanoes_craters', 'photos', key)
        p = os.path.join(d, 'sources.json')
        if not os.path.exists(p):
            return []
        recs = json.load(open(p, encoding='utf-8'))['photos']
        order = [recs[i - 1] for i in picks if i - 1 < len(recs)] if picks else recs
        for r in order[:4]:
            out.append((os.path.join(d, r['file']), r.get('note', ''), f"{r.get('licence', '')} · {r.get('author', '')}"))
    elif src == 'layered':
        d = os.path.join(OUT_ROOT, 'layered_rock', 'photos')
        recs = json.load(open(os.path.join(d, 'sources.json'), encoding='utf-8'))
        keys = [f'{key}{i:02d}' for i in picks] if picks else sorted(k for k in recs if k.startswith(key))
        for k in keys[:4]:
            r = recs.get(k, {})
            out.append((os.path.join(d, k + '.jpg'), r.get('title', '').replace('File:', '').rsplit('.', 1)[0],
                        f"{r.get('license', '')} · Wikimedia Commons"))
    elif src == 'coast':
        d = os.path.join(OUT_ROOT, 'coast', 'photos')
        recs = json.load(open(os.path.join(d, 'sources.json'), encoding='utf-8'))
        for k, r in sorted(recs.items()):
            if k.startswith(key) or r.get('file', '').startswith(key):
                out.append((os.path.join(d, r.get('file', k + '.jpg')), r.get('title', r.get('file', k)),
                            f"{r.get('licence', '')} · {r.get('author', '')}"))
        out = out[:4]
    elif src == 'glacial':
        d = os.path.join(OUT_ROOT, 'glacial', 'photos', 'raw')
        recs = _glacial_records()
        names = [f'{key}_{i:02d}.jpg' for i in picks] if picks else sorted(f for f in recs if f.startswith(key))
        for n in names[:4]:
            r = recs.get(n, {})
            out.append((os.path.join(d, n), r.get('desc', r.get('title', n)),
                        f"{r.get('licence', '')} · {r.get('author', '')}"))
    return [o for o in out if os.path.exists(o[0])]


# ----------------------------------------------------------------------------------------------------- blocks ---

def text_block(lines, width=W):
    """lines: [(text, size, colour)] -> an image."""
    probe = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    rows = []
    for text, size, colour in lines:
        f = font(size)
        for ln in wrap(probe, text, f, width - 24) or ['']:
            rows.append((ln, f, colour, size))
    h = sum(int(s * 1.35) for _, _, _, s in rows) + 16
    im = Image.new('RGB', (width, h), BG)
    d = ImageDraw.Draw(im)
    y = 8
    for ln, f, colour, size in rows:
        d.text((12, y), ln, font=f, fill=colour)
        y += int(size * 1.35)
    return im


def photo_row(photos, title):
    if not photos:
        return None
    n = len(photos)
    gap = 8
    cell_w = (W - 24 - gap * (n - 1)) // n
    head = text_block([(title, 22, GOLD)])
    im = Image.new('RGB', (W, PHOTO_H + 70), BG)
    d = ImageDraw.Draw(im)
    fs = font(15)
    for i, (path, caption, credit) in enumerate(photos):
        p = Image.open(path).convert('RGB')
        p.thumbnail((cell_w, PHOTO_H), Image.LANCZOS)
        x = 12 + i * (cell_w + gap)
        im.paste(p, (x + (cell_w - p.width) // 2, (PHOTO_H - p.height) // 2))
        lines = wrap(d, caption, fs, cell_w)[:2] + [credit[:90]]
        for k, ln in enumerate(lines):
            d.text((x, PHOTO_H + 6 + 19 * k), ln, font=fs, fill=INK if k < len(lines) - 1 else DIM)
    return stack([head, im])


def scaled(path, label):
    im = Image.open(path).convert('RGB')
    if im.width != W:
        im = im.resize((W, int(im.height * W / im.width)), Image.LANCZOS)
    return stack([text_block([(label, 20, GOLD)]), im])


def stack(blocks):
    blocks = [b for b in blocks if b is not None]
    h = sum(b.height for b in blocks)
    out = Image.new('RGB', (W, h), BG)
    y = 0
    for b in blocks:
        out.paste(b, (0, y))
        y += b.height
    return out


# ------------------------------------------------------------------------------------------------- the judge ---

def run_judge(recipe, spec, seed, samples):
    out = os.path.join(OUT, 'judge', recipe)
    os.makedirs(out, exist_ok=True)
    # a Blender job that dies leaves the last run's renders and result behind: clear them, so a sheet never shows them
    for f in glob.glob(os.path.join(out, f'{recipe}_seed*')) + [os.path.join(out, 'blender_job_result.json'),
                                                                os.path.join(out, 'verdicts.json')]:
        if os.path.isfile(f):
            os.remove(f)
    argv = ['run.py', '--recipe', recipe, '--reference', spec['ref'], '--seeds', str(seed), '--textured',
            '--samples', str(samples), '--out', out]
    for k, v in (spec.get('params') or {}).items():
        argv += ['--param', f'{k}={json.dumps(v)}']
    saved = sys.argv
    sys.argv = argv
    t0 = time.time()
    try:
        JR.main()
        rc = 0
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
    finally:
        sys.argv = saved
    return dict(rc=rc, seconds=round(time.time() - t0))


def run_meadow(seed):
    """The meadow's views: fluvial/render_eye.py's meadow cameras, textured, through the slot."""
    out = os.path.join(OUT, 'judge', 'meadow')
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    rc, slot = JR.run_blender(os.path.join(TN, 'fluvial', 'render_eye.py'),
                              ['--recipe', 'meadow', '--seed', str(seed), '--tag', 'integration_meadow', '--textured'],
                              os.path.join(out, 'blender.log'))
    return dict(rc=rc, seconds=round(time.time() - t0), slot=slot)


def meadow_views():
    """The meadow's textured views (render_eye.py names them <tag>_<view>_tex.png): eye, over, ground."""
    r = os.path.join(TN, 'out', 'fluvial', 'renders')
    out = []
    for v in ('eye', 'over', 'ground'):
        p = next((os.path.join(r, f'{tag}_{v}_tex.png') for tag in ('integration_meadow', 'integration')
                  if os.path.exists(os.path.join(r, f'{tag}_{v}_tex.png'))), None)
        out.append(p)
    return out


# ------------------------------------------------------------------------------------------------- the sheet ---

def verdict_lines(recipe, spec):
    vp = os.path.join(OUT, 'judge', recipe, 'verdicts.json')
    if not os.path.exists(vp):
        return [('no verdict (the judge did not finish: see sheets/judge/%s/blender.log)' % recipe, 18, BAD)], None
    v = json.load(open(vp, encoding='utf-8'))
    if not v:
        return [('no verdict', 18, BAD)], None
    v = v[0]
    rows = [r for r in v['rows'] if r.get('passed') is not None]
    npass = sum(bool(r['passed']) for r in rows)
    lines = [(f"{v['label']}: {npass} of {len(rows)} bands {'PASS' if v['passed'] else 'out'}"
              + (f" (out: {'; '.join(v['failures'])})" if v['failures'] else ''), 18, GOOD if v['passed'] else BAD)]
    return lines, dict(passed=bool(v['passed']), bands=f'{npass}/{len(rows)}', failures=v['failures'],
                       notes=v.get('notes', []))


def compose(recipe, spec, title):
    blocks = []
    ref = refs.load(spec['ref']) if spec.get('ref') else None
    head = [(f'{recipe}: {title}', 30, INK)]
    if ref is not None:
        head.append((f'judged against {ref.title} ({ref.extent / 1000:g} km at {ref.pixel:g} m pixels), seed 1, '
                     f'film quality; photographs of the place first, then views from their cameras, then the judge',
                     17, DIM))
    vl, summary = verdict_lines(recipe, spec) if ref is not None else ([], None)
    blocks.append(text_block(head + vl))
    matched = []
    for alts in spec.get('matched', []):
        p = next((os.path.join(OUT_ROOT, a) for a in alts if os.path.exists(os.path.join(OUT_ROOT, a))), None)
        if p:
            matched.append(p)
    if not matched:                     # a photo-matched sheet carries its photographs beside the renders already
        blocks.append(photo_row(photos_for(spec.get('photos')), 'photographs of the place'))
    if spec.get('photos2'):
        blocks.append(photo_row(photos_for(spec['photos2']), 'photographs of the second place it is judged against'))
    for p in matched:
        when = time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(p)))
        blocks.append(scaled(p, f'photographs of the place, and from their cameras the real DEM and the recipe under '
                                f'the same sky (the package\'s renders, {os.path.relpath(p, OUT_ROOT)}, {when})'))
    if recipe == 'meadow':
        views = [v for v in meadow_views() if v]
        if views:
            ims = [Image.open(v).convert('RGB') for v in views]
            cw = (W - 24 - 8 * (len(ims) - 1)) // len(ims)
            row = Image.new('RGB', (W, int(cw * 9 / 16) + 8), BG)
            for i, im in enumerate(ims):
                row.paste(im.resize((cw, int(cw * 9 / 16)), Image.LANCZOS), (12 + i * (cw + 8), 4))
            blocks.append(stack([text_block([('the meadow in its palette (eye 1.6 m, over the shoulder, the ground at '
                                              'the feet) with the probe\'s test grass: no elevation data exists at '
                                              'this scale, so its read is the look', 20, GOLD)]), row]))
        else:
            blocks.append(text_block([('meadow renders missing: see sheets/judge/meadow/blender.log', 18, BAD)]))
    else:
        js = glob.glob(os.path.join(OUT, 'judge', recipe, 'compare_*.png'))
        if js:
            blocks.append(scaled(js[0], 'the judge: the place\'s clay views and numbers above the recipe\'s (green in '
                                        'band, red out), then the recipe built with its hero levels and palette'))
        else:
            blocks.append(text_block([('judge sheet missing: see sheets/judge/%s/blender.log' % recipe, 18, BAD)]))
    sheet = stack(blocks)
    path = os.path.join(OUT, f'{recipe}.jpg')
    sheet.save(path, quality=88)
    return path, summary


def overview(names):
    """One page for all recipes: per row a photograph of the place, the place's own 1.7 m eye view (the reference
    rig's clay), the recipe's textured eye (hero levels, palette, rocks) and its textured aerial."""
    cw, ch, lw = 400, 225, 330
    rows = []
    fs, fb = font(15), font(20)
    for r in names:
        spec = RECIPES[r]
        jd = os.path.join(OUT, 'judge', r)
        photos = photos_for(spec.get('photos'))
        if r == 'meadow':
            eye, over, ground = meadow_views()
            cells = [None, ground, eye, over]
        else:
            cells = [photos[0][0] if photos else None,
                     os.path.join(refs.REFERENCE_DIR, 'renders', f"{spec['ref']}_eye_1p7m.png"),
                     os.path.join(jd, f'{r}_seed1_tex_eye.png'), os.path.join(jd, f'{r}_seed1_tex_aerial.png')]
        row = Image.new('RGB', (W, ch + 10), BG)
        d = ImageDraw.Draw(row)
        d.text((12, 8), r, font=fb, fill=INK)
        vl, summary = verdict_lines(r, spec) if spec.get('ref') else ([('judged by its look', 15, DIM)], None)
        y = 40
        for ln in wrap(d, vl[0][0], fs, lw - 24)[:6]:
            d.text((12, y), ln, font=fs, fill=vl[0][2])
            y += 19
        for i, p in enumerate(cells):
            x = lw + i * (cw + 5)
            if p and os.path.exists(p):
                im = Image.open(p).convert('RGB')
                im = im.resize((cw, int(im.height * cw / im.width)), Image.LANCZOS)
                if im.height > ch:                                   # a tall photograph: its middle band
                    top = (im.height - ch) // 2
                    im = im.crop((0, top, cw, top + ch))
                row.paste(im, (x, 5))
            else:
                d.rectangle((x, 5, x + cw, 5 + ch), outline=(60, 60, 64))
        rows.append(row)
    head = text_block([('the recipes at a glance: a photograph of the place, the place at 1.7 m (its real elevation '
                        'data in the reference rig\'s clay), the recipe at 1.7 m and from the air (hero levels, '
                        'palette, rocks); each recipe\'s sheet has the rest', 20, GOLD)])
    sheet = stack([head] + rows)
    path = os.path.join(OUT, 'overview.jpg')
    sheet.save(path, quality=88)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--recipes', default='')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--samples', type=int, default=16)
    ap.add_argument('--compose-only', action='store_true')
    ap.add_argument('--slots', default='heavy.sh,heavy2.sh,heavy3.sh')
    ap.add_argument('--slot-wait', type=float, default=600.0, help='minutes to wait for a free GPU slot per job')
    a = ap.parse_args()
    JR.SLOTS = tuple(s for s in a.slots.split(',') if s) or ('heavy.sh',)
    run_blender = JR.run_blender
    JR.run_blender = lambda script, args, log_path: run_blender(script, args, log_path, timeout_min=a.slot_wait)
    names = [r for r in a.recipes.split(',') if r] or list(RECIPES)
    os.makedirs(OUT, exist_ok=True)
    idx_path = os.path.join(OUT, 'index.json')
    index = json.load(open(idx_path, encoding='utf-8')) if os.path.exists(idx_path) else {}
    sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))
    from eidoblend.terrain import recipes as REG
    for r in names:
        spec = RECIPES[r]
        entry = index.get(r, {})
        if not a.compose_only:
            print(f'[sheets] {r}: judging against {spec.get("ref") or "its look"}', flush=True)
            entry['run'] = run_meadow(a.seed) if r == 'meadow' else run_judge(r, spec, a.seed, a.samples)
            entry['when'] = time.strftime('%Y-%m-%d %H:%M')
        path, summary = compose(r, spec, REG.get(r).title)
        entry.update(sheet=os.path.relpath(path, TN).replace(os.sep, '/'), verdict=summary)
        index[r] = entry
        with open(idx_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=1)
        print(f"[sheets] {r}: {path}" + (f" ({summary['bands']} bands)" if summary else ''), flush=True)
    print(f'[sheets] overview: {overview(list(RECIPES))}', flush=True)


if __name__ == '__main__':
    main()
