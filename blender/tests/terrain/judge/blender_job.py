"""The Blender side of judge/run.py (it writes the job file and runs this through a GPU slot):

    bash run_blender.sh blender/tests/terrain/judge/blender_job.py --job <job.json>

The job: {reference, out_dir, cache_root, samples, items: [...]}, each item
    {label, field: <path.npz>}                       a heightfield (h, cell, row 0 = south; optional context_h,
                                                     context_cell centred on the same point; water; sea_level)
    {label, recipe, seed, quality, params, textured, save_terrain}
                                                     generated here at the reference's extent: generate() for the
                                                     main level and its context (saved as <label>.npz for the
                                                     numbers; with save_terrain also every level, Terrain.save as
                                                     <label>_terrain.*, ~200 MB at film quality), the clay probes of
                                                     the main level, then make_terrain() with the focus on the eye
                                                     spot for the hero-level eye view (and with the recipe's palette
                                                     when textured: the textured aerial and eye of item 6)
Each item gets <label>_top_hillshade.png, _aerial_45deg.png, _eye_1p7m.png (the reference rig, grey clay) and
<label>_views.json; a built terrain also <label>_hero_eye.png and, textured, <label>_tex_aerial.png and
<label>_tex_eye.png. Progress and errors go to stdout; a failed item is recorded and the job goes on.
"""
import gc
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))

import numpy as np  # noqa: E402

from judge import refs, views  # noqa: E402
from judge.refs import grid  # noqa: E402

TEX_EXPOSURE = -0.5         # the surfacing package's exposure for textured views (its render_places.py default)


def argv():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return a[a.index('--job') + 1]


def field_item(job, ref, item, log):
    d = np.load(item['field'])
    h = np.asarray(d['h'], np.float64)
    cell = float(d['cell'])
    ctx = (np.asarray(d['context_h'], np.float64), float(d['context_cell'])) if 'context_h' in d.files else None
    eye = views.eye_spot(h, cell, ref)
    recs, eye = views.render_field(item['label'], h, cell, ref, job['out_dir'], job['cache_root'], context=ctx,
                                   eye=eye, samples=job.get('samples', 16))
    return dict(eye={k: v for k, v in eye.items() if k != 'world'}, views=recs)


def recipe_item(job, ref, item, log):
    import bpy
    from eidoblend.terrain import api as A
    label, out = item['label'], job['out_dir']
    kw = dict(size=ref.extent, seed=int(item.get('seed', 1)), params=item.get('params') or None,
              quality=item.get('quality', 'film'), palette=None)
    t0 = time.time()
    t = A.generate(item['recipe'], **{k: v for k, v in kw.items() if k != 'palette'}, log=log)
    secs = dict(generate=round(time.time() - t0, 1))
    lv = t.main
    h = np.asarray(t.fields('main')['h'], np.float64)
    ctx = None
    ctx_lv = [lv_ for lv_ in t.levels if lv_.role == 'context']
    if ctx_lv:
        c = max(ctx_lv, key=lambda v: v.side)
        ctx = (np.asarray(t.fields(c.index)['h'], np.float64), float(c.cell))
    fields = t.fields('main')
    extra = {}
    if 'water' in fields:
        extra['water'] = np.asarray(fields['water'], np.float32)
    sea = t.info.get('sea_level') if isinstance(t.info, dict) else None
    np.savez(os.path.join(out, label + '.npz'), h=h.astype(np.float32), cell=lv.cell, frame='south_up',
             sea_level=np.nan if sea is None else float(sea),
             **({'context_h': ctx[0].astype(np.float32), 'context_cell': ctx[1]} if ctx else {}), **extra)
    if item.get('save_terrain'):                # every level's fields: ~200 MB for a film terrain
        t.save(os.path.join(out, label + '_terrain'))
    eye = views.terrain_eye(t, ref)
    recs, eye = views.render_field(label, h, lv.cell, ref, out, job['cache_root'], context=ctx, eye=eye,
                                   samples=job.get('samples', 16))
    secs['probes'] = round(time.time() - t0 - secs['generate'], 1)
    # the hero-level eye view (and the textured row): the ring mesh built with the focus on the eye spot
    wx, wy = eye['world'].eye[0], eye['world'].eye[1]
    centre = (lv.x0 + lv.side / 2.0, lv.y0 + lv.side / 2.0)
    levels = [dict(role=v.role, cell=v.cell, side=v.side) for v in t.levels]
    del t, fields                               # a film terrain's levels and masks hold gigabytes: one at a time
    errors = {}
    # the textured views at the palettes' own exposure (surfacing/render_places.py: -0.5; the clay keeps the rig's).
    # Each view in a scene of its own: make_sky keys its sun, moon and layers to the one camera it is made for
    passes = [(None, 'hero', 'eye', None)]
    if item.get('textured'):
        passes += [('auto', 'tex', 'aerial', TEX_EXPOSURE), ('auto', 'tex', 'eye', TEX_EXPOSURE)]
    tb = None
    for palette, tag, vw, exposure in passes:
        try:                                    # the field and the clay probes stand even when a build fails
            tb = None                           # the last build's arrays go before the next one is made
            gc.collect()
            bpy.ops.wm.read_factory_settings(use_empty=True)
            tb = A.make_terrain(item['recipe'], focus=(wx, wy), name=f'{label}_{tag}', **dict(kw, palette=palette))
            r = views.render_object_views(tb.height_at, lv.side, centre, ref, eye, out, job['cache_root'],
                                          f'{label}_{tag}', views=(vw,), samples=job.get('samples', 16),
                                          exposure=exposure)
            recs.update({f'{tag}_{k}': v for k, v in r.items()})
        except Exception as e:                  # noqa: BLE001 - recorded in the result, the job goes on
            traceback.print_exc()
            errors[f'{tag}_{vw}'] = f'{type(e).__name__}: {e}'
        secs[f'{tag}_{vw}'] = round(time.time() - t0 - sum(secs.values()), 1)
    return dict(eye={k: v for k, v in eye.items() if k != 'world'}, views=recs, seconds=secs, errors=errors,
                levels=levels)


def main():
    with open(argv(), encoding='utf-8') as f:
        job = json.load(f)
    ref = refs.load(job['reference'])
    os.makedirs(job['out_dir'], exist_ok=True)
    results = {}
    for item in job['items']:
        t0 = time.time()
        try:
            r = (recipe_item if item.get('recipe') else field_item)(job, ref, item, lambda *a, **k: print(*a, flush=True))
            r['ok'] = True
        except Exception as e:                                          # noqa: BLE001 - recorded, the job goes on
            traceback.print_exc()
            r = dict(ok=False, error=f'{type(e).__name__}: {e}')
        r['seconds_total'] = round(time.time() - t0, 1)
        results[item['label']] = r
        print(f"[judge-blender] {item['label']}: {'ok' if r['ok'] else r['error']} ({r['seconds_total']}s)", flush=True)
    with open(os.path.join(job['out_dir'], 'blender_job_result.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))
    print('[judge-blender] done', flush=True)


if __name__ == '__main__':
    main()
