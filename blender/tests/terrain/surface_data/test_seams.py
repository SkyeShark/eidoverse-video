"""Seams and gutters of the surface data (SURFACING_DESIGN.md 5.4, package 1, item 3), plain Python on the bakes
bake_cases.py cached:

    python blender/tests/terrain/surface_data/test_seams.py [--case toroweap ...] [--all]

1. At every window edge, every map's child equals its parent within 1 % of the map's range, plus the rounding of the
   8-bit encodings the cache keeps E and M in (half a step at each level): the child's outermost texel centres (its
   pinned border) against the parent bilinear at the same points.
2. Every atlas tile's gutter holds the parent's maps at the gutter's own positions, encoded as the tile is (the
   gutter is what Linear filtering and the mips read past a window edge): the D, E and M tiles' outer gutter ring
   against the parent's encoded values there, within one 8-bit step (RGBA8) or 1e-3 (16F).
Writes out/surface_data/seams_<case>.json; exit 0 when every case passes.
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

from eidoblend.terrain.surface import atlas as AT  # noqa: E402
from eidoblend.terrain.surface import maps as MP  # noqa: E402

SKIP = ('aspect', 'height', 'strata', 'insolation',     # aspect tears at north; height and strata are not pinned
        'area',                                         # the routed drainage area (m^2, accumulated): not a map
        'slope_20m')                                    # the reader's slope of the interpolated n20: n20's seam
TOL = 0.01


def enc_step(nm, cell):
    """One step of a map's 8-bit encoding in its own units on a level of `cell` metres (0 for a 16F map): the cache
    and the atlases hold E and M maps in 8 bits, so a child's border and its parent each round by half a step."""
    try:
        s = MP.spec(nm)
    except KeyError:
        return 0.0
    if s.family in ('C', 'P'):
        return 1.0 / 255.0                                 # the palette's images are 8-bit (kept in float16)
    if s.family not in ('E', 'M'):
        return 0.0
    if s.encoding == 'unit':
        return 1.0 / 255.0
    if s.encoding == 'signed':
        return 2.0 / 255.0
    if s.encoding == 'bend':
        return 2.0 / (255.0 * MP.bend_scale(s, cell))
    if s.encoding == 'thick':
        return 2.0 * float(s.t_max) / 255.0                # the largest step, at t_max (v^2 t_max: 2 v t_max dv)
    return 0.0


def edge_points(lv, m):
    """World (x, y) of the outermost texel centres of a level's grid of m texels."""
    t = lv.side / m
    k = (np.arange(m) + 0.5) * t
    xs = np.concatenate([lv.x0 + k, lv.x0 + k, np.full(m, lv.x0 + 0.5 * t), np.full(m, lv.x1 - 0.5 * t)])
    ys = np.concatenate([np.full(m, lv.y0 + 0.5 * t), np.full(m, lv.y1 - 0.5 * t), lv.y0 + k, lv.y0 + k])
    return xs, ys


def edge_values(a):
    return np.concatenate([a[0, :], a[-1, :], a[:, 0], a[:, -1]])


def check(name):
    t = C.terrain(name)
    sd, key = SH.load_sd(name, t)
    rows = []
    for i in range(1, len(t.levels)):
        lv, plv = t.levels[i], t.levels[i - 1]
        mc, mp = sd.maps(i), sd.maps(i - 1)
        for nm in sorted(mc):
            if nm in SKIP or nm not in mp:
                continue
            a, b = np.asarray(mc[nm], np.float64), np.asarray(mp[nm], np.float64)
            if a.ndim != 2:
                continue
            xs, ys = edge_points(lv, a.shape[0])
            child = edge_values(a)
            parent = AT.sample_bilinear(b, plv.x0, plv.y0, plv.side / b.shape[0], xs, ys)
            # the map's range on both levels (a map that is 0 nearly everywhere, lake depth, has no percentile range)
            rng = max(float(np.ptp(b)), float(np.ptp(a)), 1e-6)
            d = float(np.max(np.abs(child - parent)))
            err = d / rng
            rounding = 0.5 * (enc_step(nm, lv.side / a.shape[0]) + enc_step(nm, plv.side / b.shape[0]))
            rows.append(dict(level=i, map=nm, err=round(err, 5), rounding=round(rounding / rng, 5),
                             ok=d <= TOL * rng + rounding + 1e-9))
    bad = [r for r in rows if not r['ok']]
    # the gutters
    grows = []
    for fam in [f for f in sd.families() if f in ('D', 'E') or f.startswith('M')]:
        lay = sd.layouts[fam]
        base = 'M' if fam.startswith('M') else fam
        step = 1e-3 if MP.FAMILIES[base]['is_float'] else 1.0 / 255.0 + 1e-6
        for i in range(1, len(t.levels)):
            tl = lay.tiles[i]
            tile = sd.tile(fam, i)
            xs, ys = tl.centres()
            outer = np.concatenate([tile[0, :], tile[-1, :], tile[:, 0], tile[:, -1]])
            px = np.concatenate([xs, xs, np.full(tl.size, xs[0]), np.full(tl.size, xs[-1])])
            py = np.concatenate([np.full(tl.size, ys[0]), np.full(tl.size, ys[-1]), ys, ys])
            worst = 0.0
            for c, nm in enumerate(sd.family_maps(fam)):
                if nm is None:
                    continue
                src = sd._array(i - 1, nm)
                if src is None:                           # the parent lacks the map: its gutter holds the neutral value
                    grows.append(dict(family=fam, level=i, map=nm, note='parent lacks the map', ok=True))
                    continue
                plv = t.levels[i - 1]
                want = AT.sample_bilinear(src, plv.x0, plv.y0, plv.side / src.shape[0], px, py)
                enc = sd._encode(fam, nm, want, i)
                worst = max(worst, float(np.max(np.abs(outer[:, c] - enc))))
            grows.append(dict(family=fam, level=i, worst=worst, ok=worst <= step))
    gbad = [r for r in grows if not r['ok']]
    rep = dict(case=name, key=key, tol=TOL, seams=rows, gutters=grows, ok=not bad and not gbad)
    with open(os.path.join(C.OUT, f'seams_{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=1)
    worst = max(rows, key=lambda r: r['err']) if rows else None
    print(f"[test_seams] {name}: {len(rows)} map edges, worst {worst['map']} L{worst['level']} {worst['err']:.4f} "
          f"of the range; {len(grows)} gutters" + (f'; FAIL: {[(r["map"], r["level"], r["err"]) for r in bad]}'
                                                    if bad else '')
          + (f'; gutter FAIL: {[(r["family"], r["level"], r["worst"]) for r in gbad]}' if gbad else ''), flush=True)
    return rep['ok']


def main():
    a = plain_import.script_args()
    names = [a[i + 1] for i, v in enumerate(a) if v == '--case' and i + 1 < len(a)]
    if '--all' in a or not names:
        names = [n for n in C.CASES if os.path.isdir(os.path.join(C.OUT, 'cache', n))]
    ok = all([check(n) for n in names])
    print(f"[test_seams] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
