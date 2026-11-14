"""The map sheets' two further readings (SURFACING_DESIGN.md 5.4, package 1, item 1), plain Python on the bakes
bake_cases.py cached:

    python blender/tests/terrain/surface_data/readings.py [--case toroweap ...] [--all]

Gentle ground: on ground under 15 degrees (the main level and the sheet's hero level), each map's 5-95 % spread.
The maps a gentle-ground rule reads (crest, valley, cavity, wetness) must vary there; settle's flat 0.5 is expected.
Parent and child: over the child's window, each map on the child and on the parent: the overlap over union of the
two past a threshold the palettes use for it (THRESHOLDS; a parent cell counts for the child when any child cell in
it is past), the same with the child box-averaged (iou_mean), and their correlation (child box-averaged), for every
parent and child pair from the main level down. An overlap under 0.6 is flagged, except on the texel-scale maps
(TEXEL), which each level makes at its own texel.
Writes out/surface_data/readings_<case>.json and prints a table per case.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
import _cases as C  # noqa: E402
import numpy as np  # noqa: E402
import sheets as SH  # noqa: E402

MAPS = ('crest', 'crest_fine', 'crease', 'cavity', 'settle', 'valley', 'fresh', 'spi', 'grain', 'streak', 'snowpack',
        'wetness', 'flow')
# (comparison, value): the side of the threshold the palettes' rules key on
THRESHOLDS = {'crest': ('>', 0.3), 'crest_fine': ('>', 0.3), 'crease': ('<', -0.3), 'cavity': ('<', 0.8),
              'settle': ('>', 0.6), 'valley': ('>', 0.5), 'fresh': ('>', 0.5), 'spi': ('>', 0.7),
              'grain': ('<', 0.5), 'streak': ('>', 0.2), 'snowpack': ('>', 0.2), 'wetness': ('>', 0.6),
              'flow': ('>', 0.6)}
# a level's own texel-scale relief (1-2 texels): each level has its own, so parent and child are not expected to agree
TEXEL = ('crest_fine', 'crease')


def _to(a, n):
    """A map (m, m) on a grid of n per side over the same window: box-averaged (m = k n) or as it is."""
    a = np.asarray(a, np.float64)
    m = a.shape[0]
    if m == n:
        return a
    k = m // n
    return a.reshape(n, k, n, k).mean(axis=(1, 3))


def gentle(sd, t, i):
    m = sd.maps(i)
    slope = np.asarray(m['slope'], np.float64)
    g = slope < 15.0
    out = {}
    for k in MAPS:
        if k not in m:
            continue
        a = _to(m[k], slope.shape[0])
        if not g.any():
            continue
        lo, hi = np.percentile(a[g], [5, 95])
        out[k] = round(float(hi - lo), 4)
    return dict(level=i, share_gentle=round(float(g.mean()), 3), spread_5_95=out)


def _iou(a, b):
    union = float((a | b).sum())
    return float((a & b).sum()) / union if union else None


def pair(sd, t, i):
    """Child level i against its parent i - 1 over the child's window, at the parent's cells. The overlap: the
    child's cells past the threshold, a parent cell counted when any child cell in it is (a channel 4 m wide on the
    child averaged into an 8 m parent cell falls under the threshold it passes on both levels); the correlation and
    the mean-pooled overlap (iou_mean) of the child box-averaged."""
    lv, plv = t.levels[i], t.levels[i - 1]
    mc, mp = sd.maps(i), sd.maps(i - 1)
    i0, j0, mcells = lv.in_parent(t.levels)
    rows = {}
    for k in MAPS:
        if k not in mc or k not in mp:
            continue
        cc = _to(mc[k], lv.n)                             # the child on its cells
        c = _to(cc, mcells)                               # ... box-averaged to the parent's cells
        p = np.asarray(mp[k], np.float64)
        if p.shape[0] != plv.n:
            p = _to(p, plv.n)
        p = p[j0:j0 + mcells, i0:i0 + mcells]
        op, v = THRESHOLDS[k]
        past = (lambda x: x > v) if op == '>' else (lambda x: x < v)
        f = cc.shape[0] // mcells
        a_any = past(cc).reshape(mcells, f, mcells, f).any(axis=(1, 3))
        a, b = past(c), past(p)
        iou, iou_mean = _iou(a_any, b), _iou(a, b)
        cs, ps = c.std(), p.std()
        corr = float(np.corrcoef(c.ravel(), p.ravel())[0, 1]) if cs > 1e-9 and ps > 1e-9 else None
        rows[k] = dict(iou=None if iou is None else round(iou, 3),
                       iou_mean=None if iou_mean is None else round(iou_mean, 3),
                       corr=None if corr is None else round(corr, 3),
                       share_child=round(float(past(cc).mean()), 4), share_parent=round(float(b.mean()), 4),
                       flag=bool(k not in TEXEL and iou is not None and iou < 0.6
                                 and max(a_any.mean(), b.mean()) > 0.002))
    return dict(child=i, parent=i - 1, cells=[lv.cell, plv.cell], maps=rows)


def readings(name):
    t = C.terrain(name)
    sd, key = SH.load_sd(name, t)
    roles = [lv.role for lv in t.levels]
    main = roles.index('main')
    heroes = [i for i, r in enumerate(roles) if r == 'hero']
    hi = heroes[min(1, len(heroes) - 1)] if heroes else None
    rep = dict(case=name, key=key, gentle=[gentle(sd, t, main)] + ([gentle(sd, t, hi)] if hi is not None else []),
               pairs=[pair(sd, t, i) for i in range(main + 1, len(t.levels))])
    with open(os.path.join(C.OUT, f'readings_{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=1)
    print(f'[readings] {name} ({key[:10]})')
    for gr in rep['gentle']:
        print(f"  gentle ground, level {gr['level']} ({gr['share_gentle'] * 100:.0f} % under 15 deg): "
              + ', '.join(f'{k} {v}' for k, v in gr['spread_5_95'].items()))
    for pr in rep['pairs']:
        flags = [k for k, r in pr['maps'].items() if r['flag']]
        print(f"  L{pr['child']} {pr['cells'][0]:g} m vs L{pr['parent']}: "
              + ', '.join(f"{k} {r['iou']}/{r['corr']}" for k, r in pr['maps'].items())
              + (f"   FLAG: {flags}" if flags else ''))
    return rep


def main():
    a = plain_import.script_args()
    names = [a[i + 1] for i, v in enumerate(a) if v == '--case' and i + 1 < len(a)]
    if '--all' in a or not names:
        names = list(C.SHEET_CASES)
    for nm in names:
        readings(nm)
    return 0


if __name__ == '__main__':
    sys.exit(main())
