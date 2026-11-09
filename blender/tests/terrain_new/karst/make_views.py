"""Generate a tower-karst terrain at the Guilin reference's extent for the probe renders, in plain Python (numpy):
the main tile (8 km at 8 m, as guilin_karst), the context surround (32 km at 32 m, as guilin_karst_context), an
optional hero window around the eye (2 km at 2 m), and an eye viewpoint on the plain looking at a massif, like the
reference's (a plain 2.2 km from the nearest cluster, aimed 100 m above its target, 35 mm).

    python make_views.py --name fenglin_s7 --seed 7 [--kind fenglin] [--params '{"spacing_m": 220}'] [--hero]

writes out/karst/<name>_fields.npz (h_main, h_ctx, h_hero: float32, row 0 = NORTH, as render_probe takes them) and
<name>_eye.json (the eye dict in the main tile's local metres, the numbers, the timings).

The fields come straight from solvers/karst.py: the karst stage alone (the tower field, plain, river, cockpits,
fluting on the 2 m hero window). The whole recipe (with package 3's threshold, creep and talus stages, through
make_terrain) is judged by judge/run.py --recipe tower_karst.
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
OUT = os.path.join(HERE, '..', 'out', 'karst')
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
sys.path.insert(0, HERE)


def load_karst():
    from eidoblend.terrain.solvers import karst
    return karst


def field(K, plan, centre, side, cell):
    """(h south-up float64, the evaluate() dict) of a window `side` metres wide centred on `centre`."""
    n = int(round(side / cell))
    out = K.evaluate(plan, centre[0] - side / 2, centre[1] - side / 2, cell, n)
    return out['h'].astype(np.float64), out


def find_eye(h, cell, x0, y0, plain, seed, eye_h=1.7, near_m=350.0, far=(900.0, 3200.0), fallback=True):
    """A standing point on the plain with a clear foreground and a skyline of peaks 1-3 km away, like the
    reference's: candidates where nothing within near_m stands 4 m above the plain; for each, 32 headings, the
    largest elevation angle of the ground between far[0] and far[1]; the score is the summed angle over a +-20 degree
    fan, with views whose foreground rises over 1.2 degrees rejected. Fengcong has no plain: then the eye stands on a
    cockpit floor (flat ground, nothing within 90 m standing 4 m above it) looking at the cones around it, 200 m to
    1.5 km away. Returns the eye dict (south-up h, local metres with the tile centred on 0)."""
    try:
        return _find_eye(h, cell, x0, y0, plain, seed, eye_h, near_m, far, 1.2)
    except LookupError:
        if not fallback:
            raise
    gy, gx = np.gradient(h, cell)
    from numpy.lib.stride_tricks import sliding_window_view
    r = max(1, int(round(150.0 / cell)))
    p = np.pad(h, r, mode='edge')
    floor = sliding_window_view(sliding_window_view(p, 2 * r + 1, axis=0).min(-1), 2 * r + 1, axis=1).min(-1)
    floor = np.where(np.hypot(gx, gy) < 0.07, h, floor)
    return _find_eye(h, cell, x0, y0, floor, seed, eye_h, 90.0, (350.0, 2500.0), 6.0)


def _find_eye(h, cell, x0, y0, plain, seed, eye_h, near_m, far, near_max_deg):
    rng = np.random.default_rng(seed)
    n = h.shape[0]
    above = h - plain
    blk = max(1, int(round(40.0 / cell)))
    nb = n // blk
    coarse = above[:nb * blk, :nb * blk].reshape(nb, blk, nb, blk).max(axis=(1, 3))
    r = int(math.ceil(near_m / (blk * cell)))
    from numpy.lib.stride_tricks import sliding_window_view
    p = np.pad(coarse, r, mode='edge')
    clear = sliding_window_view(sliding_window_view(p, 2 * r + 1, axis=0).max(-1), 2 * r + 1, axis=1).max(-1) < 4.0
    margin = int(far[1] * 0.5 / (blk * cell))
    cj, ci = np.nonzero(clear[margin // 2:nb - margin // 2, margin // 2:nb - margin // 2])
    if cj.size == 0:
        cj, ci = np.nonzero(clear)
    else:
        cj, ci = cj + margin // 2, ci + margin // 2
    if cj.size == 0:
        raise LookupError('no standing point with a clear foreground')
    pick = rng.choice(cj.size, size=min(400, cj.size), replace=False)
    heads = np.radians(np.arange(32) * 360.0 / 32)
    dists = np.arange(far[0], far[1], 15.0)
    near_d = np.arange(30.0, far[0], 15.0)

    def sample(x, y):
        i = np.clip(((x - x0) / cell - 0.5).astype(int), 0, n - 1)
        j = np.clip(((y - y0) / cell - 0.5).astype(int), 0, n - 1)
        return h[j, i]
    best = None
    for k in pick:
        ex = x0 + (ci[k] + 0.5) * blk * cell
        ey = y0 + (cj[k] + 0.5) * blk * cell
        z0 = sample(np.array([ex]), np.array([ey]))[0] + eye_h
        ang = np.zeros(32)
        dist_at = np.zeros(32)
        near_ang = np.zeros(32)
        for a in range(32):
            cx, sy = math.cos(heads[a]), math.sin(heads[a])
            zz = sample(ex + cx * dists, ey + sy * dists)
            e = np.degrees(np.arctan2(zz - z0, dists))
            ang[a] = e.max()
            dist_at[a] = dists[int(np.argmax(e))]
            zn = sample(ex + cx * near_d, ey + sy * near_d)
            near_ang[a] = np.degrees(np.arctan2(zn - z0, near_d)).max()
        for a in range(32):
            fan = [(a + d) % 32 for d in (-2, -1, 0, 1, 2)]
            if near_ang[fan].max() > near_max_deg:
                continue
            score = float(np.clip(ang[fan], 0, 9 if near_max_deg < 3 else 14).sum() + 0.002 * dist_at[fan].mean())
            if best is None or score > best[0]:
                best = (score, ex, ey, heads[a], dist_at[a])
    if best is None:
        raise LookupError('no heading with a clear foreground')
    score, ex, ey, hd, d = best
    return dict(x=float(ex), y=float(ey), look_x=float(ex + math.cos(hd) * d), look_y=float(ey + math.sin(hd) * d),
                look_dz=100.0, lens_mm=35.0, score=score)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--kind', default='fenglin')
    ap.add_argument('--params', default='{}')
    ap.add_argument('--hero', action='store_true', help='also a 2 km window at 2 m around the eye')
    a = ap.parse_args(argv)
    K = load_karst()
    sys.path.insert(0, HERE)
    import karst_numbers as KN
    params = dict(json.loads(a.params))
    params['kind'] = a.kind
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    plan = K.plan_karst(a.seed, (-16000.0, -16000.0, 32000.0), params, via=(0.0, 0.0),
                        main=(-4000.0, -4000.0, 8000.0))       # as the op plans it: the main tile's cover
    t_plan = time.time() - t0
    t0 = time.time()
    h_main, out_main = field(K, plan, (0.0, 0.0), 8000.0, 8.0)
    t_main = time.time() - t0
    t0 = time.time()
    h_ctx, _ = field(K, plan, (0.0, 0.0), 32000.0, 32.0)
    t_ctx = time.time() - t0
    eye = find_eye(h_main, 8.0, -4000.0, -4000.0, out_main['plain'].astype(np.float64), a.seed)
    rec = dict(name=a.name, seed=a.seed, kind=a.kind, params=params, eye=eye, plan_stats=plan.stats,
               timings_s=dict(plan=round(t_plan, 2), main_1000sq_8m=round(t_main, 2), context_1000sq_32m=round(t_ctx, 2)))
    north = h_main[::-1]
    rec['numbers_raw'] = KN.numbers(north, 8.0)
    rec['numbers_instrument'] = KN.numbers(KN.as_copernicus(north, 8.0), 8.0)
    arrays = dict(h_main=north.astype(np.float32), h_ctx=h_ctx[::-1].astype(np.float32),
                  tower_id=out_main['tower_id'][::-1].copy(), plain=out_main['plain'][::-1].copy(),
                  deposit=out_main['deposit'][::-1].copy(), river=out_main['river'][::-1].copy())
    if a.hero:
        t0 = time.time()
        h_hero, _ = field(K, plan, (eye['x'], eye['y']), 2048.0, 2.0)
        rec['timings_s']['hero_1024sq_2m'] = round(time.time() - t0, 2)
        h_hctx, _ = field(K, plan, (eye['x'], eye['y']), 24000.0, 24.0)      # the hero view's horizon
        arrays['h_hero'] = h_hero[::-1].astype(np.float32)
        arrays['h_hero_ctx'] = h_hctx[::-1].astype(np.float32)
        rec['hero'] = dict(centre=[eye['x'], eye['y']], side_m=2048.0, cell_m=2.0, context_side_m=24000.0,
                           context_cell_m=24.0)
    np.savez_compressed(os.path.join(OUT, f'{a.name}_fields.npz'), **arrays)
    with open(os.path.join(OUT, f'{a.name}_eye.json'), 'w') as f:
        json.dump(rec, f, indent=1)
    print(json.dumps(dict(name=a.name, eye=eye, timings_s=rec['timings_s'], stats=plan.stats)))


if __name__ == '__main__':
    main()
