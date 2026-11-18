"""No step at a window edge on real terrains (surfacing design 5.4, package 4, item 5): per species, stems per hectare
in 50 m strips either side of every hero window's edge, on Lauterbrunnen (real_place) and the canyon, each terrain
made around a judge view's camera (surfacing_judge/views.json) with its surface data baked, the plan's placement
itself (its view's thinning off). Each edge is set against the same strips of the same plan on the terrain's coarse
levels alone (test_plants.edge_steps): a hill or a forest's edge across those 100 m is in both, a step the window
makes only in the first. The gate is the step (10 %); the raw ratio, the design's literal measure, is recorded too.

    bash run_blender.sh blender/tests/terrain/plants/edges_real.py [--views floor_lischmaad,approach_walk]
    (a GPU job on a terrain or bake cache miss: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with
    EIDO_GPU_WRAP, blender/tests/_where.py)

Writes out/plants/edges.json: per view the terrain's levels and every edge's row.
"""
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, TN)
sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))

import test_plants as TP  # noqa: E402
from surfacing_judge import views as V  # noqa: E402
from judge import refs  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain import surface as SU  # noqa: E402
from eidoblend.terrain.build import plants as PL  # noqa: E402

VIEWS = [('real_place', 'floor_lischmaad'), ('real_place', 'ridge_schynige'), ('canyon', 'approach_walk')]
OUT = os.path.join(TN, 'out', 'plants', 'edges.json')
GATE = 0.10


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    only = a[a.index('--views') + 1].split(',') if '--views' in a else None
    return [(r, v) for r, v in VIEWS if not only or v in only]


def why(t, sd, eco, rows, strip_m=50.0):
    """For each edge over the gate: at the plan's candidates in either strip (the windowless plan's trees there),
    how many each of the finest level's exclusions keeps off on the terrain with its windows and on its coarse
    levels alone: what the window changed."""
    import numpy as np
    out = []
    for r in rows:
        if abs(r['step'] - 1.0) <= GATE:
            continue
        s = next(x for x in eco['species'] if x['name'] == r['species'])
        lv = [x for x in t.levels if getattr(x, 'role', '') == 'hero'][r['level'] - 1]
        x0, y0, x1, y1 = lv.x0, lv.y0, lv.x0 + lv.side, lv.y0 + lv.side
        g = np.linspace(0.5, strip_m - 0.5, 50)
        along = np.linspace(x0 + strip_m, x1 - strip_m, 400) if r['edge'] in ('south', 'north') else \
            np.linspace(y0 + strip_m, y1 - strip_m, 400)
        rows_out = {}
        for side, sgn in (('inner', 1.0), ('outer', -1.0)):
            if r['edge'] == 'west':
                X, Y = np.meshgrid(x0 + sgn * g, along)
            elif r['edge'] == 'east':
                X, Y = np.meshgrid(x1 - sgn * g, along)
            elif r['edge'] == 'south':
                X, Y = np.meshgrid(along, y0 + sgn * g)
            else:
                X, Y = np.meshgrid(along, y1 - sgn * g)
            x, y = X.ravel(), Y.ravel()
            for tag, terr in (('windows', t), ('coarse', TP.G.CoarseView(t))):
                ground = PL._Ground(terr, sd, PL._constants(terr, eco))
                pts = ground.locate(x, y)
                fine = {k: ground.at(pts, k) for k in ('water', 'snowpack', 'slope', 'talus', 'sand')}
                share = {}
                for k, v in fine.items():
                    if v is None:
                        continue
                    lim = {'water': 0.05, 'snowpack': 0.2, 'slope': PL.STEEP_DEG}.get(k, float(s['roots_m']))
                    share[k] = round(float((v > lim).mean()), 4)
                rows_out[f'{side} {tag}'] = share
        # the window's level against its parent over the same ground (inside the window): does the window change
        # what the finest level excludes, or does the windowless plan only lack a map the hero levels carry?
        hero_i = [i for i, x in enumerate(t.levels) if getattr(x, 'role', '') == 'hero'][r['level'] - 1]
        X, Y = np.meshgrid(np.linspace(x0 + 1, x1 - 1, 300), np.linspace(y0 + 1, y1 - 1, 300))
        ground = PL._Ground(t, sd, PL._constants(t, eco))
        same = {}
        for k in ('water', 'talus', 'slope', 'snowpack'):
            arrays = [m.get(k) for m in ground.stack]
            if arrays[hero_i] is None or arrays[hero_i - 1] is None:
                continue
            lim = {'water': 0.05, 'snowpack': 0.2, 'slope': PL.STEEP_DEG}.get(k, float(s['roots_m']))
            a = [float((PL._Points(ground.levels, X.ravel(), Y.ravel(), only={j}).sample(ground.levels, arrays)
                        > lim).mean()) for j in (hero_i, hero_i - 1)]
            same[k] = dict(window=round(a[0], 4), parent=round(a[1], 4))
        coarse_lacks = sorted(k for k, v in rows_out['outer windows'].items() if k not in rows_out['outer coarse']
                              and abs(v - rows_out['inner windows'].get(k, 0.0)) > 0.02)
        explained = bool(coarse_lacks) and all(abs(v['window'] - v['parent']) <= 0.02 for v in same.values())
        out.append(dict(species=r['species'], level=r['level'], edge=r['edge'], excluded_share=rows_out,
                        same_ground=same, coarse_lacks=coarse_lacks, explained=explained))
        print(f"[edges] why {r['species']} level {r['level']} {r['edge']}: {rows_out}; over the same ground, the "
              f"window's level against its parent: {same}; the windowless plan lacks {coarse_lacks}: "
              f"{'the terrain, not the window' if explained else 'NOT explained'}", flush=True)
    return out


def terrain_at(recipe, vname):
    """The terrain the judge's view is rendered on, its hero levels around the camera, and the camera (x, y); None
    for a view without hero levels (a camera on a context ring: no window edges to measure)."""
    plan = V.load()[recipe]
    v = next(x for x in plan['views'] if x['name'] == vname)
    if not v.get('focus'):
        return None, None
    R = A._registry.resolve(recipe)
    vals, _ = R.resolve(plan.get('params'))
    dfl = dict(R.defaults)
    if getattr(R, 'defaults_for', None) is not None:
        dfl.update(R.defaults_for(vals))
    c0 = dfl.get('centre', (0.0, 0.0))
    focus = (c0[0] + v['cam'][0], c0[1] + v['cam'][1])
    t = A.generate(recipe, size=refs.load(plan['reference']).extent, seed=1, params=plan.get('params'),
                   focus=[focus], quality='film', cache=True, log=lambda *a, **k: None)
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
    return t, (v['cam'][0] + cx, v['cam'][1] + cy)


def main():
    rec = {}
    if os.path.exists(OUT):
        with open(OUT, encoding='utf-8') as fh:
            rec = json.load(fh)
    tmp = tempfile.mkdtemp(prefix='plants_edges_')
    worst_all = 0.0
    try:
        for recipe, vname in args():
            t0 = time.time()
            t, cam = terrain_at(recipe, vname)
            if t is None:
                print(f'[edges] {recipe}/{vname}: its camera stands where no hero window is (a context ring)',
                      flush=True)
                continue
            sd = SU.bake_surface(t, palette='auto', log=None)
            eco = TP.unthinned(PL._resolve(t, 'auto'))
            rows = TP.edge_steps(t, eco, cam, tmp, data=sd, min_count=200)
            worst = max((abs(r['step'] - 1.0) for r in rows), default=0.0)
            reasons = why(t, sd, eco, rows)
            unexplained = [r for r in rows if abs(r['step'] - 1.0) > GATE and not any(
                w['explained'] for w in reasons if (w['species'], w['level'], w['edge']) ==
                (r['species'], r['level'], r['edge']))]
            worst_all = max(worst_all, max((abs(r['step'] - 1.0) for r in unexplained), default=0.0))
            rec[f'{recipe}_{vname}'] = dict(
                camera=[round(cam[0], 1), round(cam[1], 1)], ecotope=eco['name'], seconds=round(time.time() - t0, 1),
                levels=[[lv.role, round(lv.x0, 1), round(lv.y0, 1), round(lv.side, 1), lv.cell] for lv in t.levels],
                worst_step=round(worst, 4), passed=bool(rows) and not unexplained,
                edges=[{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in rows],
                why=reasons)
            for r in rows:
                print(f"[edges] {recipe}/{vname} {r['species']} level {r['level']} {r['edge']}: "
                      f"{r['inner']:.0f}/{r['outer']:.0f} per ha ({100 * (r['ratio'] - 1):+.0f} %), without the window "
                      f"{100 * (r['ratio_coarse'] - 1):+.0f} %: step {100 * (r['step'] - 1):+.1f} %", flush=True)
            print(f'[edges] {recipe}/{vname}: {len(rows)} edges, worst step {100 * worst:.1f} % '
                  f'({time.time() - t0:.0f} s)', flush=True)
            with open(OUT, 'w', encoding='utf-8') as fh:
                json.dump(rec, fh, indent=1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(('PASS' if worst_all <= GATE else 'FAIL') + f' edges on real terrains: worst step the window makes '
          f'{100 * worst_all:.1f} % (edges over {100 * GATE:g} % whose difference is a map only the hero levels carry, '
          f'the same on the window\'s level and its parent, are the terrain)', flush=True)
    os._exit(0)


main()
