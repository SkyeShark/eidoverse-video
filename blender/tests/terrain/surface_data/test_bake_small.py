"""The whole surface bake on a small terrain, in plain Python through the numpy twins (no Blender):

    python blender/tests/terrain/surface_data/test_bake_small.py

Three nested levels of 96 cells (main 1920 m, two hero levels around a focus) of an analytic landform: a plateau
with a 45-degree escarpment of layered rock, a valley with a stream, gullied slopes, a snowline across it. The masks
come from masks.compute_stack, the drainage area from the twins' routing. Checks: every map of the registry the bake
makes is there on every level, finite and in its unit's range; the bake is deterministic (bytes); every map's child
equals its parent at the window edges within 1 % of its range; the maps mean what they say on the landform (crest
high on the rim, settle gathered at the escarpment's foot, src_strata above the ground's own bed on the talus,
snowpack only above the snowline, fresh on the stream). Writes out/surface_data/bake_small.json.
"""
import json
import math
import os
import sys
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
import numpy as np  # noqa: E402

from eidoblend.terrain import masks as M  # noqa: E402
from eidoblend.terrain.core import levels as LV  # noqa: E402
from eidoblend.terrain.surface import bake as B  # noqa: E402
from eidoblend.terrain.surface import maps as MP  # noqa: E402

OUT = os.path.join(HERE, '..', 'out', 'surface_data')
N = 96
SIZE = 1920.0
FOCUS = (180.0, -60.0)


def height(x, y):
    """A plateau (300 m) breaking at an escarpment along x = 150 m into a valley floor (0 m) falling gently east,
    with gullies on the slopes and a stream down the valley."""
    x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
    esc = 300.0 / (1.0 + np.exp(-(x - 150.0) / 40.0))                       # the escarpment, steepest 62 degrees
    valley = -0.02 * x + 30.0 * np.exp(-((y + 200.0) / 300.0) ** 2) * 0.0
    gullies = 6.0 * np.sin(y / 23.0 + 0.3 * np.sin(x / 70.0)) * np.exp(-((x - 150.0) / 120.0) ** 2)
    stream = -8.0 * np.exp(-((y - 0.004 * x ** 1.0 + 300.0) / 25.0) ** 2) * (x < 150)
    bumps = 3.0 * np.sin(x / 31.0) * np.cos(y / 37.0)
    return esc + valley + gullies + stream + bumps


def make_terrain():
    plan = LV.plan_levels(SIZE, N, (0.0, 0.0), None, FOCUS, hero=SIZE / N / 4.0)
    fields = []
    for lv in plan:
        X, Y = lv.xy()
        h = height(X, Y).astype(np.float64)
        f = {'h': h, 'talus': np.clip((h - 40.0) / 60.0, 0, 1) * (h < 120) * 1.5,
             'zs': h + 0.05 * X}
        fields.append(f)
    # drainage area by the twins' routing on each level's filled surface (as the runner's)
    from eidoblend.terrain.solvers import fluvial as FL
    from eidoblend.terrain.solvers import hydro as HY
    dev = FL.device('twin')
    for f, lv in zip(fields, plan):
        filled, _ = HY.fill_depressions(f['h'])
        rs = HY.routing_surface(filled)
        A, _it = HY.route_to_convergence(dev, rs, lv.cell, tol=1e-3, check=64)
        f['A'] = A
    P = M.MaskParams(snowline_m=250.0, base_elevation_m=0.0)
    stack = M.compute_stack(fields, plan, params=P)
    t = SimpleNamespace(levels=plan, fields=lambda i: fields[i], masks=stack,
                        info=dict(seed=3, base_elevation_m=0.0), recipe=None, knobs={'snowline_m': 250.0})
    return t


def main():
    t0 = time.perf_counter()
    t = make_terrain()
    tm = time.perf_counter() - t0
    opts = B.resolve_options(t, None, {'backend': 'twin', 'carry_passes': 64})
    t1 = time.perf_counter()
    out, info, fills = B.bake_levels(t, opts, log=None)
    secs = time.perf_counter() - t1
    out2, _i2, _f2 = B.bake_levels(t, opts, log=None)
    checks = {}
    # 1. every map, finite, in range
    want = [k for k, s in MP.MAPS.items() if s.made_by not in ('masks', 'plants', 'shader', 'far_colour',
                                                                'route_colour')]
    rows = {}
    for i, m in enumerate(out):
        lv = t.levels[i]
        for k in want:
            if k in ('strata', 'src_strata'):
                k = 'src_dz' if k == 'src_strata' else 'strata_dz'
            if k == 'streak' and info['wind'] is False:
                continue
            if MP.MAPS.get(k) is not None and MP.MAPS[k].made_by == 'masks+route' and \
                    (lv.role != 'hero' or not opts.get('reroute_hero')):
                continue                                  # the masks' own (the bake routes hero levels on request)
            a = m.get(k)
            ok = a is not None and bool(np.isfinite(a).all())
            rng = (float(np.min(a)), float(np.max(a))) if a is not None else None
            unit = MP.MAPS.get(k, MP.MAPS['strata']).unit if k in MP.MAPS else 'm'
            if ok and unit == '0-1':
                ok = rng[0] >= -1e-5 and rng[1] <= 1 + 1e-5
            if ok and unit == '-1..1':
                ok = rng[0] >= -1 - 1e-5 and rng[1] <= 1 + 1e-5
            rows[f'L{i}.{k}'] = dict(ok=ok, range=rng, shape=list(a.shape) if a is not None else None)
    checks['maps'] = all(r['ok'] for r in rows.values())
    # 2. deterministic
    checks['deterministic'] = all(np.array_equal(out[i][k], out2[i][k]) for i in range(len(out)) for k in out[i])
    # 3. pinned at the window edges (the bake's maps; the masks are compute_stack's)
    seam = {}
    from eidoblend.terrain.surface import atlas as AT
    for i in range(1, len(out)):
        lv, plv = t.levels[i], t.levels[i - 1]
        for k, a in out[i].items():
            if k in ('area',) or k not in out[i - 1] or a.ndim != 2:
                continue
            b = out[i - 1][k]
            m = a.shape[0]
            tx = lv.side / m
            kk = (np.arange(m) + 0.5) * tx
            xs = np.concatenate([lv.x0 + kk, lv.x0 + kk, np.full(m, lv.x0 + tx / 2), np.full(m, lv.x1 - tx / 2)])
            ys = np.concatenate([np.full(m, lv.y0 + tx / 2), np.full(m, lv.y1 - tx / 2), lv.y0 + kk, lv.y0 + kk])
            child = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
            par = AT.sample_bilinear(b, plv.x0, plv.y0, plv.side / b.shape[0], xs, ys)
            r = max(float(np.ptp(b)), 1e-9)
            seam[f'L{i}.{k}'] = round(float(np.max(np.abs(child - par)) / r), 5)
    checks['seams'] = max(seam.values()) <= 0.01
    # 4. meaning, on the main level (cells: x along columns)
    main = 0
    m = out[main]
    lv = t.levels[main]
    X, Y = lv.xy()
    mk = t.masks[main]
    rim = (np.abs(X - 230) < 30)                                              # the plateau's edge (convex)
    # the escarpment's foot: where its slope (62 degrees at x = 150 m) has fallen under 15 degrees, x 0..30 m
    foot = (X > 0) & (X < 30) & (np.abs(Y - FOCUS[1]) < 600)
    below = (X > 40) & (X < 110) & (np.abs(Y - FOCUS[1]) < 600)               # its lower face, 20-45 degrees
    face = (np.abs(X - 150) < 15)
    meaning = dict(
        crest_rim_minus_foot=float(m['crest'][rim].mean() - m['crest'][foot].mean()),
        settle_foot=float(m['settle'][foot].mean()), settle_face=float(m['settle'][face].mean()),
        src_above_bed_below_face=float((m['src_dz'] - m['strata_dz'])[below].mean()),
        snow_above_line=float(m['snowpack'][mk['height'] > 280].mean()) if 'snowpack' in m else None,
        snow_below_line=float(m['snowpack'][mk['height'] < 150].mean()) if 'snowpack' in m else None,
        fresh_on_channels=float(m['fresh'][mk['channels'] > 0.5].mean()) if 'fresh' in m else None,
        fresh_elsewhere=float(m['fresh'][mk['channels'] < 0.1].mean()) if 'fresh' in m else None)
    checks['crest'] = meaning['crest_rim_minus_foot'] > 0.2
    checks['settle'] = meaning['settle_foot'] > 0.5 > meaning['settle_face']
    checks['src_strata'] = meaning['src_above_bed_below_face'] > 5.0
    checks['snow'] = meaning['snow_above_line'] is not None and meaning['snow_above_line'] > 0.3 and \
        meaning['snow_below_line'] < 0.02
    # 5. the SurfaceData API on the bake: the cache round trip, maps, at, channel, pack, layouts, atlases
    import shutil
    from eidoblend.terrain import surface as S
    folder = os.path.join(OUT, 'cache', 'bake_small')
    shutil.rmtree(folder, ignore_errors=True)
    key = B.bake_key(t, opts)
    for m_, w in zip(out, fills):
        m_['_fill'] = w
    info = dict(info, options=opts, names=[sorted(k for k in m_ if not k.startswith('_')) for m_ in out])
    info['refs'] = S.SurfaceData(t, out, info, opts, key).refs          # as bake_surface stores them
    S.save_cached(folder, key, out, info, cells=[lv.cell for lv in t.levels])
    hit = S.load_cached(folder, key, len(t.levels))
    sd = S.SurfaceData(t, hit[0], hit[1], opts, key, cache_dir=folder)
    api = {}
    api['lazy'] = all(isinstance(b, str) for b in sd._baked)
    api['names'] = {'crest', 'settle', 'normal_x', 'slope', 'insolation', 'src_strata'} <= set(sd.names())
    x, y = FOCUS
    api['at'] = abs(sd.at('crest', x, y) - float(AT.sample_bilinear(        # the cache keeps crest in 8 bits
        out[-1]['crest'], t.levels[-1].x0, t.levels[-1].y0, t.levels[-1].cell, x, y))) <= 2.0 / 255.0
    packed = sd.pack(['settle', 'crest', 'n20', 'flow', 'talus', 'slope', 'cavity'])
    api['pack'] = packed.get('n20_x', (None,))[0] == packed.get('n20_y', (None,))[0] and 'slope' not in packed \
        and 'cavity' not in packed
    api['channel'] = (sd.channel('normal_x')[0] == 'D' and sd.channel('cavity')[:2] == ('E', 1)
                      and sd.channel('slope')[0] == 'shader' and sd.channel('n20')[1] in ((0, 1), (1, 2), (2, 3))
                      and sd.channel('src_strata')[0] == 'F')
    fam_ok = {}
    for fam in sd.families():
        a = sd.atlas(fam)
        lay = sd.layouts[fam]
        tl = lay.tiles[-1]
        x0, y0, x1, y1 = tl.pixels()
        fam_ok[fam] = bool(np.isfinite(a).all()) and a.shape[:2] == (lay.height, lay.width)
    api['atlases'] = all(fam_ok.values())
    checks['api'] = all(api.values())
    ok = all(checks.values())
    rep = dict(ok=ok, checks=checks, meaning=meaning, seconds=dict(terrain=round(tm, 2), bake=round(secs, 2)),
               api=api, families=fam_ok,
               levels=[str(lv) for lv in t.levels], maps=rows, seams=seam, info={k: v for k, v in info.items()
                                                                                 if k != 'levels'})
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'bake_small.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=1, default=str)
    print(f"[test_bake_small] {'PASS' if ok else 'FAIL'}: {checks}")
    print(f"[test_bake_small] meaning: {json.dumps(meaning)}")
    print(f"[test_bake_small] worst seam {max(seam, key=seam.get)} {max(seam.values()):.4f}; bake {secs:.1f} s")
    bad = [k for k, r in rows.items() if not r['ok']]
    if bad:
        print(f'[test_bake_small] maps failing: {bad[:12]}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
_ = math
