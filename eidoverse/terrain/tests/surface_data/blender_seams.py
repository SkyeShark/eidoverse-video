"""Blender's own seams run on the surface data fixtures, for tests/surface_data/seams_test.mjs's comparison with it
(PORT_PLAN.md 8.2 row P14; SURFACING_DESIGN.md 5.4, package 1, item 3). blender/tests/terrain/surface_data/
test_seams.py's check() is used as it is, on the very bytes the port's tests read: each case's Blender bake and Blender
palette bake as tests/surface_data/blender_bakes.py copied and made them (tests/out/surface_data/fixtures/<key>/
bakes/<case>/, the palette bake its record names) and the case's snapshot (the fixtures' pinned copy, else the Blender
edition's). The Blender edition's own out/surface_data/seams_<case>.json reads whatever its cache holds when it ran
(the newest bake and the newest palette bake there), and its rounds re-make their snapshots and bakes. Plain Python
(Blender's, numpy), no Blender, no GPU:

    EIDO_BLENDER_EDITION=<a checkout or `git archive` export of the blender branch at the fixtures' commit> \
        [EIDO_SNAPSHOT_EDITION=<the Blender checkout holding out/surface_data/snap, when the code is an export>] \
        <Blender's python> -I eidoverse/terrain/tests/surface_data/blender_seams.py [--case toroweap ...]

Writes tests/out/surface_data/fixtures/<key>/seams/seams_<case>.json: test_seams.py's record, plus the palette tag
and the snapshot's terrain it read. $EIDO_SURFACE_FIXTURES names the fixtures (else the newest, as _surface.mjs
takes them). The Blender edition is only read (point it at an export: test_seams.py's plain_import makes its own
out/core folder).
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

CASES = ['toroweap', 'lauterbrunnen', 'meteor_crater', 'great_sand_dunes', 'badlands_sd', 'canyon', 'alpine_valley',
         'fluvial_range']


def fixture_root():
    """tests/out/surface_data/fixtures/<key>: $EIDO_SURFACE_FIXTURES, else the newest by its key.json."""
    root = os.path.join(B.TERRAIN, 'tests', 'out', 'surface_data', 'fixtures')
    want = os.environ.get('EIDO_SURFACE_FIXTURES')
    if want:
        return os.path.join(root, want) if os.path.exists(os.path.join(root, want, 'key.json')) else None
    keys = glob.glob(os.path.join(root, '*', 'key.json'))
    return os.path.dirname(max(keys, key=os.path.getmtime)) if keys else None


def main():
    a = B.script_args()
    names = [a[i + 1] for i, v in enumerate(a) if v == '--case' and i + 1 < len(a)] or CASES
    edition = B.bare_terrain_package()
    sys.path.insert(0, os.path.join(edition, 'blender', 'tests', 'terrain', 'surface_data'))
    import numpy as np
    import test_seams as TS                                  # Blender's test, used as it is
    from eidoblend.terrain import surface as S
    root = fixture_root()
    if root is None:
        print('blender_seams: no surface data fixtures (tests/surface_data/surface_fixtures.py, blender_bakes.py)')
        return 2
    with open(os.path.join(root, 'bakes', 'palette_bake.json'), encoding='utf-8') as f:
        recs = json.load(f)['cases']
    out = os.path.join(root, 'seams')
    os.makedirs(out, exist_ok=True)
    C = TS.C
    blender_snap = C.snap_path
    snaps = os.environ.get('EIDO_SNAPSHOT_EDITION')

    def snap_path(name):
        """The fixtures' pinned snapshot, else $EIDO_SNAPSHOT_EDITION's (the Blender checkout holding the snapshots,
        when the code comes from an export: tests/plants/plants_fixtures.py's convention), else the edition's own."""
        for p in (os.path.join(root, 'snap', name + '.npz'),
                  os.path.join(snaps, 'blender', 'tests', 'terrain', 'out', 'surface_data', 'snap', name + '.npz')
                  if snaps else None):
            if p and os.path.exists(p):
                return p
        return blender_snap(name)

    def load_sd(name, t):
        """sheets.load_sd's SurfaceData, on the fixtures' copy of Blender's bake and the palette bake its record
        names (sheets.load_sd takes the newest of each in the Blender package's cache)."""
        rec = recs[name]
        folder = os.path.join(root, 'bakes', name)
        baked, info = S.load_cached(folder, rec['key'], len(t.levels))
        pal = []
        for i in range(len(t.levels)):
            with np.load(os.path.join(folder, f"surface_{rec['key']}_{rec['tag']}_L{i}.npz")) as z:
                pal.append({k: np.asarray(z[k], np.float32) for k in z.files})
        return S.SurfaceData(t, baked, info, info.get('options') or {}, rec['key'], colour=pal, cache_dir=folder), rec['key']

    C.snap_path = snap_path
    C.OUT = out                                              # where check() writes seams_<case>.json
    TS.SH.load_sd = load_sd
    ok = True
    for nm in names:
        rec = recs.get(nm)
        if not rec or rec.get('error'):
            print(f'[blender_seams] {nm}: no Blender palette bake in {root}/bakes (blender_bakes.py)')
            ok = False
            continue
        ok = TS.check(nm) and ok
        p = os.path.join(out, f'seams_{nm}.json')
        with open(p, encoding='utf-8') as f:
            rep = json.load(f)
        with open(snap_path(nm).replace('.npz', '.json'), encoding='utf-8') as f:
            terrain = json.load(f).get('cache_key')
        rep.update(palette_tag=rec['tag'], terrain=terrain, edition_commit=os.environ.get('EIDO_SURFACE_COMMIT'))
        B.write_json(p, rep)
    print(f"[blender_seams] {len(names)} cases -> {out}: {'every case passes' if ok else 'not every case passes'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
