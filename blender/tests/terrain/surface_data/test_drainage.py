"""Hero drainage (SURFACING_DESIGN.md 5.4, package 1, item 4): the trunk's catchment stays within 15 % from the main
level to the finest hero level. Plain Python on the bakes bake_cases.py cached:

    python blender/tests/terrain/surface_data/test_drainage.py [--case fluvial_range] [--case lauterbrunnen]

The design's case is fluvial_range at its canyon_road focus; lauterbrunnen's valley trunk is the second (a river of
about 150 km2 crossing every hero window). The trunk: on the main level, the largest flux across a 10 m section
(trunk()) inside the finest hero window less its border band; on each finer level, the largest flux across a 10 m
section within NEAR_M of that point (a channel moves a little on a finer DEM), from the runner's drainage area and
from the bake's own routing ('area') on the levels the bake re-routed (option reroute_hero). What the maps read (the
bake's routing where it re-routed, else the runner's) is compared with the main level's. Also printed: the largest
flux within FOCUS_M of the focus on every level, which says whether a trunk passes the focus at all. Writes
out/surface_data/drainage_<case>.json; exit 0 when every hero level of every case is within 15 % of its main level.
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

TOL = 0.15
CROSS_M = 10.0          # the cross-section the trunk's flux is summed over
NEAR_M = 30.0           # how far a finer level's channel may lie from the main level's
FOCUS_M = 150.0         # the focus's own surroundings
CASES = ('fluvial_range', 'lauterbrunnen')


def trunk(A, lv, box):
    """The trunk crossing a world box (x0, y0, x1, y1) on a level: the largest flux across a CROSS_M section, the
    sum of the drainage area over a CROSS_M square divided by its length in cells (multiple-flow routing spreads a
    stream bed over several cells of a fine grid, so the largest single cell undercounts it there)."""
    A = np.asarray(A, np.float64)
    k = max(1, int(round(CROSS_M / float(lv.cell))))
    c = np.cumsum(np.cumsum(np.pad(A, ((1, 0), (1, 0))), 0), 1)
    S = (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / float(k)
    X, Y = lv.xy()
    Xc, Yc = X[:S.shape[0], :S.shape[1]] + 0.5 * (k - 1) * lv.cell, Y[:S.shape[0], :S.shape[1]] + 0.5 * (k - 1) * lv.cell
    near = (Xc >= box[0]) & (Xc <= box[2]) & (Yc >= box[1]) & (Yc <= box[3])
    if not near.any():
        return None
    j = np.argmax(np.where(near, S, -1.0))
    return float(S.ravel()[j]), float(Xc.ravel()[j]), float(Yc.ravel()[j])


def _km2(r):
    return None if r is None else round(r[0] / 1e6, 3)


def measure(name):
    t = C.terrain(name)
    sd, key = SH.load_sd(name, t)
    fx, fy = t.info['focus'][0]
    roles = [lv.role for lv in t.levels]
    main_i = roles.index('main')
    fin = t.levels[-1]
    b = fin.band * fin.cell                               # the finest window less its border band, on every level
    box = (fin.x0 + b, fin.y0 + b, fin.x1 - b, fin.y1 - b)
    focus = (fx - FOCUS_M, fy - FOCUS_M, fx + FOCUS_M, fy + FOCUS_M)
    rows = []
    near = box
    for i, lv in enumerate(t.levels):
        if i < main_i:
            continue
        A = np.asarray(t.fields(i)['A'], np.float64)
        runner = trunk(A, lv, near)
        baked = sd.maps(i).get('area')
        bake = trunk(np.asarray(baked, np.float64), lv, near) if baked is not None else None
        rows.append(dict(level=i, role=lv.role, cell=lv.cell, runner_km2=_km2(runner), bake_km2=_km2(bake),
                         at=bake[1:] if bake else runner[1:], focus_km2=_km2(trunk(A, lv, focus))))
        if i == main_i:                                   # the finer levels look near the main level's trunk
            ax, ay = runner[1], runner[2]
            near = (ax - NEAR_M, ay - NEAR_M, ax + NEAR_M, ay + NEAR_M)
    ref = rows[0]['runner_km2']
    ok = True
    for r in rows[1:]:
        # what the maps read: the bake's routing where it re-routed the level, else the runner's (the masks')
        used = r['bake_km2'] if r['bake_km2'] is not None else r['runner_km2']
        r['source'] = 'bake' if r['bake_km2'] is not None else 'runner'
        r['ratio'] = round(used / ref, 3) if used is not None else None
        r['ok'] = r['ratio'] is not None and abs(r['ratio'] - 1.0) <= TOL
        ok &= r['ok']
    ax, ay = rows[0]['at']
    rep = dict(case=name, key=key, focus=[fx, fy], box=box, near_m=NEAR_M, cross_m=CROSS_M, main_km2=ref,
               trunk_from_focus_m=round(float(np.hypot(ax - fx, ay - fy)), 1), levels=rows, ok=ok)
    with open(os.path.join(C.OUT, f'drainage_{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=1)
    print(f"[test_drainage] {name}: the main level's trunk {ref} km2, {rep['trunk_from_focus_m']} m from the focus")
    for r in rows:
        print(f"[test_drainage]   L{r['level']} {r['role']} {r['cell']:.3g} m: runner {r['runner_km2']} km2, bake "
              f"{r['bake_km2']} km2" + (f", {r['ratio']} x the main level's" if 'ratio' in r else '')
              + f"; within {FOCUS_M:g} m of the focus {r['focus_km2']} km2")
    print(f"[test_drainage] {name}: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    a = plain_import.script_args()
    names = [a[i + 1] for i, v in enumerate(a) if v == '--case' and i + 1 < len(a)] or list(CASES)
    ok = True
    for nm in names:
        ok &= measure(nm)
    print(f"[test_drainage] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
