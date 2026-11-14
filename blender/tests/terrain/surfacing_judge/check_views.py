"""Does every judge view see its subject? (system Python: numpy, Pillow; no render)

    python blender/tests/terrain/surfacing_judge/check_views.py [recipe ...] [--terrains <json>] [--plan <views.json>]
           [--sheet] [--state latest]

For each view of views.json, on the recipe's saved terrain (its main and context levels): the camera is placed as
review_views.py places it, the ray at its aim is followed, and a 160 x 90 grid of rays is cast at the ground
(views.check: its rules and why). A terrain is generated for one code state: a camera that saw its subject on
yesterday's field can face a wall on today's, which is how the review's cameras came to fail.

--terrains: {recipe: source} (default out/surfacing_judge/terrains.json), a source being a terrain cache key, a
Terrain.save() snapshot or a generator's levels file, relative to blender/tests/terrain/out/ (terrain_data.load).
Writes out/surfacing_judge/views_check.json; with --sheet, views_check.jpg: per view the photograph, the camera as
grey clay ray-cast on the saved terrain (views.preview; the aim a red cross) and the state's render of it when one
exists (--state, default 'latest': states.py), so a camera is judged by its picture beside the photograph.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))

from surfacing_judge import OUT, OUT_ROOT  # noqa: E402
from surfacing_judge import states as S  # noqa: E402
from surfacing_judge import terrain_data as TD  # noqa: E402
from surfacing_judge import views as V  # noqa: E402

TILE = (288, 162)


def terrain_sources(path=None):
    path = path or os.path.join(OUT, 'terrains.json')
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    return {k: v for k, v in d.items() if k != 'note'}


def load_terrain(recipe, source):
    """A terrain list's source as a Stack. A levels file that also holds hero levels names its main level's side:
    '<file>.npz#main=3000'."""
    main_side = None
    if '#main=' in source:
        source, main_side = source.split('#main=', 1)
        main_side = float(main_side)
    p = os.path.join(OUT_ROOT, source.replace('/', os.sep)) if source.endswith('.npz') and not os.path.isabs(source) \
        else source
    return TD.load(p, recipe=recipe, main_side=main_side)


def _tile(path, label):
    from PIL import Image, ImageDraw
    if path and os.path.exists(path):
        im = Image.open(path).convert('RGB')
        x0, y0, x1, y1 = V.fit_box(im.width, im.height)
        return im.crop((x0, y0, x1, y1)).resize(TILE, Image.LANCZOS)
    im = Image.new('RGB', TILE, (34, 34, 34))
    ImageDraw.Draw(im).text((8, TILE[1] // 2 - 6), label, fill=(170, 170, 170))
    return im


def main(argv):
    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    plan = V.load(opt('--plan'))
    src = terrain_sources(opt('--terrains'))
    state = opt('--state', 'latest')
    names = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] not in
                                                                         ('--terrains', '--plan', '--state'))]
    out, rows = {}, []
    bad = 0
    for recipe, rec in plan.items():
        if names and recipe not in names:
            continue
        if recipe not in src:
            print(f'{recipe}: no saved terrain listed (--terrains): not checked')
            continue
        st = load_terrain(recipe, src[recipe])
        for v in rec['views']:
            c = V.check(st, v)
            c.pop('hit')
            out[f"{recipe}/{v['name']}"] = c
            bad += bool(c['fails'])
            print(f"{recipe:17s} {v['name']:20s} {V.kind_of(v):6s} on {c['stands']:7s} eye +{c['height_m']:7.1f} m  "
                  f"heading {c['heading_deg']:5.1f} pitch {c['pitch_deg']:6.1f}  aim {c['aim_m']:7.0f} m "
                  f"({c['aim_above_m']:+.0f} m over the ground, ray {100 * c['aim_seen']:3.0f} %)  ground "
                  f"{100 * c['ground']:3.0f} %  blocked {100 * c['blocked']:3.0f} %  "
                  + ('ok' if not c['fails'] else 'FAILS: ' + '; '.join(c['fails']))
                  + (f"  [{'; '.join(c['warns'])}]" if c['warns'] else ''), flush=True)
            if '--sheet' in argv:
                from PIL import Image
                clay = Image.fromarray(V.preview(st, v, size=(192, 108))).resize(TILE, Image.BILINEAR)
                rows.append((f"{recipe}/{v['name']}", c, [_tile(V.photo_path(v), 'no photograph'), clay,
                                                          _tile(S.render(recipe, v['name'], state),
                                                                f'no render ({state})')]))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'views_check.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    if rows:
        from PIL import Image, ImageDraw
        cols = 2
        cw, ch = 3 * TILE[0] + 8, TILE[1] + 30
        n = (len(rows) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * cw, n * ch), (16, 16, 16))
        d = ImageDraw.Draw(sheet)
        for k, (label, c, tiles) in enumerate(rows):
            x, y = (k % cols) * cw, (k // cols) * ch
            for j, im in enumerate(tiles):
                sheet.paste(im, (x + j * TILE[0], y + 28))
            head = f"{label}  " + ('FAILS: ' + '; '.join(c['fails']) if c['fails'] else 'sees its subject')
            d.text((x + 4, y + 2), head[:150], fill=(255, 120, 120) if c['fails'] else (220, 220, 200))
            d.text((x + 4, y + 14), f"photograph | clay on today's terrain (ray-cast) | {state} render   "
                                    f"blocked {100 * c['blocked']:.0f} %, ground {100 * c['ground']:.0f} %, aim ray "
                                    f"{100 * c['aim_seen']:.0f} %", fill=(160, 160, 160))
        sheet.save(os.path.join(OUT, 'views_check.jpg'), quality=88)
    print(f'{len(out)} views checked, {bad} fail')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
