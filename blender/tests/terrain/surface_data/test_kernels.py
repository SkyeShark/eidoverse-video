"""Every surface-bake kernel against its numpy twin (SURFACING_DESIGN.md 5.4, package 1, item 2): one dispatch on a
96 x 80 field, within 1e-4 of each output channel's range (core/twins.parity).

    bash run_blender.sh blender/tests/terrain/surface_data/test_kernels.py [--kernel crest ...]
    (queue it with EIDO_GPU_WRAP on a shared machine: blender/tests/_where.py)

Writes blender/tests/terrain/out/surface_data/kernels.json (one report per kernel). Exit 0 when every kernel passes.
The inputs are terrain-like: a smoothed random height with a cliff band and a valley, a loose cover in the valley,
so every branch of every kernel runs (bare rock and soil, sources and carriers, lakes and divides).
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()

import numpy as np  # noqa: E402

from eidoblend.terrain.core import gpu as G  # noqa: E402
from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.surface import twins as TW  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402,F401 - registers route_area's twin and wpow

OUT = os.path.join(HERE, '..', 'out', 'surface_data')
F = np.float32
H, W = 80, 96
CELL = 4.0


def terrain(seed=1):
    """A height (m) with relief at several scales, a cliff band (40-70 degrees) and a valley; float32 (H, W)."""
    jj, ii = np.mgrid[0:H, 0:W].astype(np.float64)
    h = 60.0 * T.random_field((H, W), seed=seed, smooth=6).astype(np.float64)
    h += 8.0 * T.random_field((H, W), seed=seed + 1, smooth=2)
    h += 140.0 / (1.0 + np.exp(-(ii - 48.0) / 2.5))                    # a cliff band across x = 48
    h -= 30.0 * np.exp(-((jj - 40.0) / 9.0) ** 2) * (ii < 48)           # a valley on the low side
    return (h - h.mean()).astype(F)


def cover(h):
    low = h < np.percentile(h, 30)
    return (np.where(low, 1.5, 0.0) * T.random_field((H, W), seed=9, smooth=3)).astype(F)


def octave_table(n=6, lam0=40.0, x0=-5123.7, y0=2077.1, seed=7):
    """bake._gully_octaves' table: the first three octaves read geometry gates (channels 2, 1, 0), the rest none."""
    from eidoblend.terrain.core import world_noise as N
    rows = []
    lam, amp = lam0, 0.05 * lam0
    for o in range(n):
        ox, oy = N.lattice_offset(seed + 4242, o)
        bx, by = math.floor(x0 / lam), math.floor(y0 / lam)
        rows.append([(bx + ox, by + oy, x0 / lam - bx, y0 / lam - by),
                     (1.0 / lam, amp, 1.0, float(2 - o) if o < 3 else -1.0)])
        lam *= 0.5
        amp *= 0.5
    t = np.zeros((1, 2 * n, 4), F)
    for k, (a, b) in enumerate(rows):
        t[0, 2 * k], t[0, 2 * k + 1] = a, b
    return t


def cases():
    h = terrain()
    gy, gx = np.gradient(h.astype(np.float64), CELL)
    tan_s = np.hypot(gx, gy).astype(F)
    cov = cover(h)
    zs = (h + 0.3 * (np.arange(W)[None, :] - W / 2)).astype(F)
    out = {}
    out['blur_fan'] = ({'src': T.rgba(h)}, {'uSigma': (1.0, 2.0, 4.0, 8.0), 'uDir': (1, 0), 'uFan': 1})
    pyr = np.stack([T.random_field((H, W), seed=s, smooth=2) * 50 for s in (3, 4, 5, 6)], 2).astype(F)
    out['blur_y'] = ({'src': pyr}, {'uSigma': (16.0, 2.5, 0.0, 1.0), 'uDir': (0, 1), 'uFan': 0})
    out['upsample2_catmull'] = ({'src': np.stack([h, zs, cov, tan_s], 2)},
                                {'uOrigin': (20, 17), 'uSize': (W, H), 'uKind': 0})
    out['upsample2_bilinear'] = ({'src': np.stack([h, zs, cov, tan_s], 2)},
                                 {'uOrigin': (3, 30), 'uSize': (W, H), 'uKind': 1})
    out['upsample2_nearest'] = ({'src': np.stack([h, zs, cov, tan_s], 2)},
                                {'uOrigin': (40, 0), 'uSize': (W, H), 'uKind': 2})
    out['field_normal'] = ({'hT': T.rgba(h)}, {'uTexel': CELL})
    # crest: a pyramid made by the twin of blur (its parity is checked above)
    from eidoblend.terrain.core import twins as _T  # noqa: F401
    pyrA = blur_twin(h, (1.0, 2.0, 4.0, 8.0))
    pyrB = blur_twin(h, (16.0, 5.0, 0.0, 0.0))
    par = np.stack([0.3 * T.random_field((H, W), seed=11, smooth=3) - 0.15,
                    T.random_field((H, W), seed=12, smooth=3) * 0.6,
                    0.2 * T.random_field((H, W), seed=13, smooth=3) - 0.1,
                    0.2 * T.random_field((H, W), seed=14, smooth=3) - 0.1], 2).astype(F)
    for tag, has_par, own in (('crest', 1, 0), ('crest_noparent', 0, 1)):
        out[tag] = ({'hT': T.rgba(h), 'pyrA': pyrA, 'pyrB': pyrB, 'parT': par},
                    {'uCell': CELL, 'uTau': 0.25, 'uTerms': 5.0 + 2 * has_par, 'uSmin': 6.0, 'uValley': (0.16, 25.0),
                     'uHasParent': has_par,
                     'uN20Own': own, 'uWind': (0.6, 0.8)})
    # phacelle on a detail grid of two texels per cell: the cell grid inputs are (40, 48)
    hD = T.rgba(h)
    hgD = T.run_twin(TW.field_normal, {'hT': hD}, {'uTexel': CELL / 2}, spec=spec('field_normal'))['outG']
    steer = np.zeros((H // 2, W // 2, 4), F)
    a = 2 * math.pi * T.random_field((H // 2, W // 2), seed=21, smooth=2)
    steer[..., 2], steer[..., 3] = np.cos(a), np.sin(a)
    rock = np.zeros((H, W, 4), F)
    rock[..., 3] = 0.6 * T.random_field((H, W), seed=22, smooth=1) - 0.3
    # the cover on the cell grid: loose debris (the valley's), sand on part of it, a snowpack on another part, and a
    # specific catchment from 2 m to 2 km, so every gate of every octave runs from 0 to 1
    hc, wc = H // 2, W // 2
    covC = np.zeros((hc, wc, 4), F)
    covC[..., 1] = np.maximum(1.2 * T.random_field((hc, wc), seed=23, smooth=2) - 0.4, 0.0)
    covC[..., 0] = np.ascontiguousarray(cov[::2, ::2]) + covC[..., 1]
    covC[..., 2] = np.maximum(4.0 * T.random_field((hc, wc), seed=24, smooth=2) - 1.5, 0.0)
    covC[..., 3] = 10.0 ** (0.3 + 3.0 * T.random_field((hc, wc), seed=25, smooth=2))
    gate = np.stack([T.random_field((hc, wc), seed=s, smooth=2) for s in (26, 27, 28, 29)], 2).astype(F)
    for tag, rock_on in (('phacelle', 1), ('phacelle_norock', 0)):
        out[tag] = ({'hgT': hgD, 'steerT': steer, 'octT': octave_table(), 'rockT': rock, 'coverT': covC,
                     'gateT': gate},
                    {'uOct': 6, 'uTexel': CELL / 2, 'uF': 2, 'uSteer': 0.35, 'uNorm': 0.5,
                     'uSlope': (10.0, 18.0, 30.0, 38.0), 'uRockDeg': (38.0, 52.0), 'uCover': (0.1, 1.0),
                     'uNormalCap': 4.0, 'uRockRef': 0.4, 'uRockOn': rock_on, 'uStrength': 0.5,
                     'uSpec': (0.3, 1.3, 3.0, 0.0), 'uInit': (1.0, 4.0, 0.1, 0.6), 'uLoose': (0.3, 2.0),
                     'uBury': (0.5, 2.0)})
    zR = np.stack([0.5 * T.random_field((H, W), seed=31, smooth=1) - 0.25,
                   T.random_field((H, W), seed=32) * 2 - 1, h, np.zeros((H, W))], 2).astype(F)
    zB = np.stack([blur_twin(zR[..., c], (1.0, 0, 0, 0))[..., 0] for c in range(4)], 2).astype(F)
    zB2 = np.stack([blur_twin(zR[..., c], (2.0, 0, 0, 0))[..., 0] for c in range(4)], 2).astype(F)
    out['cavity'] = ({'zT': zR, 'blurT': zB, 'blur2T': zB2}, {'uTexel': CELL / 2, 'uTau': 0.25})
    st = np.zeros((H, W, 4), F)
    st[..., 0], st[..., 1] = zs, 1.0e9
    st[::3, ::5, 0], st[::3, ::5, 1], st[::3, ::5, 2] = zs[::3, ::5] + 7.0, 33.0, 1.0
    aux = np.stack([cov, zs, np.zeros((H, W)), np.zeros((H, W))], 2).astype(F)
    aux[:4, :, 2] = 1.0
    out['carry_src'] = ({'hT': T.rgba(h), 'auxT': aux, 'stT': st},
                        {'uCell': CELL, 'uRockDeg': (34.0, 46.0), 'uCover': (0.1, 1.0), 'uSalt': 3})
    ex = np.stack([np.maximum(T.random_field((H, W), seed=41, smooth=1) - 0.5, 0)] + [np.zeros((H, W))] * 3, 2)
    out['streak'] = ({'exT': ex.astype(F)}, {'uWind': (0.6, -0.8), 'uLength': 6.0})
    z = np.stack([h, T.on_edge((H, W)).astype(F), np.zeros((H, W)), np.zeros((H, W))], 2).astype(F)
    Wf = np.where(T.on_edge((H, W)), h, h + 25.0 * T.random_field((H, W), seed=51)).astype(F)
    out['fill'] = ({'wT': T.rgba(Wf), 'zT': z}, {'uEps': 0.002, 'uCap': 3.0})
    # routing: a tilted, filled surface
    surf = (h + 0.05 * np.arange(W)[None, :] * CELL).astype(F)
    ws = T.run_twin('flow_weights', {'st': T.rgba(surf)}, {'uDx': CELL, 'uP': 1.0, 'uBound': T.BOUND_OPEN})['outW']
    tgt = np.zeros((H, W, 4), F)
    tgt[..., 0] = 50.0 + 2000.0 * T.random_field((H, W), seed=61, smooth=2)
    tgt[:6, :, 1] = tgt[-6:, :, 1] = tgt[:, :6, 1] = tgt[:, -6:, 1] = 1.0
    out['pin_inflow'] = ({'st': T.rgba(surf), 'wsumT': ws, 'tgtT': tgt}, {'uDx': CELL, 'uP': 1.0, 'uBound': 0})
    q = np.stack([T.random_field((H, W), seed=s, smooth=1) * 3 for s in (71, 72, 73, 74)], 2).astype(F)
    src = np.stack([T.random_field((H, W), seed=s) for s in (75, 76, 77, 78)], 2).astype(F)
    pin = np.zeros((H, W, 4), F)
    pin[:3, :, 1] = 1.0
    out['route_colour'] = ({'st': T.rgba(surf), 'wsumT': ws, 'qT': q, 'srcT': src, 'pinT': pin},
                           {'uDx': CELL, 'uP': 1.0, 'uBound': 0})
    return out


_SPECS = {}


def spec(name):
    if name not in _SPECS:
        _SPECS[name] = G.parse_spec(TW.source(name), TW.PREFIX + name)
    return _SPECS[name]


def blur_twin(h, sig):
    a = T.run_twin(TW.blur, {'src': T.rgba(h)}, {'uSigma': sig, 'uDir': (1, 0), 'uFan': 1}, spec=spec('blur'))
    return T.run_twin(TW.blur, {'src': a['outB']}, {'uSigma': sig, 'uDir': (0, 1), 'uFan': 0},
                      spec=spec('blur'))['outB']


def main():
    a = plain_import.script_args()
    only = [a[i + 1] for i, v in enumerate(a) if v == '--kernel' and i + 1 < len(a)]
    G.init()
    os.makedirs(OUT, exist_ok=True)
    reports = []
    ok = True
    for tag, (inputs, uniforms) in cases().items():
        name = next(k for k in sorted(TW.KERNELS, key=len, reverse=True) if tag.startswith(k))
        if only and name not in only and tag not in only:
            continue
        t0 = time.perf_counter()
        k = G.kernel(source=TW.source(name), name=TW.PREFIX + name)
        rep = T.parity(k, inputs, uniforms, twin=T.get_twin(TW.PREFIX + name), tol=1e-4)
        rep['case'] = tag
        rep['seconds'] = round(time.perf_counter() - t0, 3)
        reports.append(rep)
        ok &= rep['ok']
        print(f'[{tag}] ' + T.report_text(rep), flush=True)
    with open(os.path.join(OUT, 'kernels.json'), 'w', encoding='utf-8') as f:
        json.dump(reports, f, indent=1)
    print(f"[test_kernels] {'PASS' if ok else 'FAIL'}: {sum(r['ok'] for r in reports)} / {len(reports)} cases",
          flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    os._exit(code)
