"""How sharp are the seams on real data? The crease across each ring border of real_place Lauterbrunnen (seven levels
around the reference's eye spot, the hero levels refined by the level runner) against the creases across ordinary
lattice lines. (test_mesh.py checks the seam rule alone, on a surface every level samples alike.)

For each seam, at 2,000 points along it, the angle between the triangle normals a quarter of a vertex spacing outside
and inside the border; the same across lattice lines three spacings inside the child ring and three outside in the
parent ring, which every ring has everywhere. A seam within 25 % + 0.1 degree of the ordinary lines at p50 and p99
reads like any other row of the mesh. The main tile's own border is also where the DEM meets its surround (real_place
blends them continuously in height, not in slope), so an excess there is the data's, not the stitching's.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain_new/mesh_api/test_seam_crease.py
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', '..')))
sys.path.insert(0, HERE)
from eidoblend.terrain.api import generate  # noqa: E402
from _common import EYE, lauterbrunnen  # noqa: E402
from test_mesh import crease_deg, border_points  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'mesh_api'))


def main():
    recipe, off = lauterbrunnen()
    t = generate(recipe, params={'dem': 'lauterbrunnen'}, focus=EYE, seed=1, cache=False, log=lambda *a: None)
    rm = t.ring
    rec, ok = {}, True
    p = lambda a, q: float(np.percentile(a, q))  # noqa: E731
    for k in range(1, len(rm.rings)):
        child, parent = rm.rings[k], rm.rings[k - 1]
        sc, sp = child.spec.sp * rm.unit, parent.spec.sp * rm.unit
        seam = crease_deg(rm, *border_points(child, 0.0), 0.25 * min(sc, sp))
        ref = np.concatenate([crease_deg(rm, *border_points(child, 3 * sc), 0.25 * sc),
                              crease_deg(rm, *border_points(child, -3 * sp), 0.25 * sp)])
        good = p(seam, 50) <= p(ref, 50) * 1.25 + 0.1 and p(seam, 99) <= p(ref, 99) * 1.25 + 0.1
        ok &= good
        rec[f'seam{k}'] = dict(spacing_m=[sp, sc], seam_p50_p90_p99_deg=[p(seam, 50), p(seam, 90), p(seam, 99)],
                               ordinary_p50_p90_p99_deg=[p(ref, 50), p(ref, 90), p(ref, 99)], pass_=good)
        print(f'[crease] seam {k} ({sp:g} -> {sc:g} m): seam p50/p90/p99 {p(seam, 50):.2f}/{p(seam, 90):.2f}/'
              f'{p(seam, 99):.2f} deg; ordinary lines {p(ref, 50):.2f}/{p(ref, 90):.2f}/{p(ref, 99):.2f} deg '
              f'{"PASS" if good else "OVER"}', flush=True)
    rec.update(pass_=bool(ok), stages_switched_off=off, skipped_stages=t.info['skipped_stages'],
               seconds=t.info['seconds'])
    with open(os.path.join(OUT, 'test_seam_crease.json'), 'w') as f:
        json.dump(rec, f, indent=1)
    print('[crease] ' + ('ALL WITHIN' if ok else 'SOME OVER'), flush=True)


main()
