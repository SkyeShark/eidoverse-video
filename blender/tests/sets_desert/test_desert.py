"""The desert round a town (eidoblend.sets.desert): a small one made from nothing at draft quality, checked, and two
stills. Plain Python with numpy and Pillow (the chain's own Python), which runs the Blender steps itself:

    python blender/tests/sets_desert/test_desert.py [--reuse] [--no-render]

It runs make.py into out/desert (the terrain recipes at draft quality, a 260 x 160 m town's footprint and tracks, the
land on the draft grid, the mesh at 8 m, the collection saved), then checks (PASS / FAIL):
  1. the sources: three recipes' levels with the fields the land reads
  2. the land: three rasters, every height finite, the town's footprint under its plane (z < 0) and the floor rising
     through z 0 within 60 m of it; the tracks drawn from the town's own track ends
  3. the mesh: NO CRACKS (every open edge on the outer border or under the town's plane), no edge in three faces,
     nothing rising into the flight over the town (x +-1200, y +-900: under 30 m), the scrub placed
  4. two stills (out/stills/ring_c_pY.png: toward the escarpment over the town; close_dunes.png): written, neither
     black nor blown
--reuse skips the chain when out/desert is made. A PASS is not a look: open the stills.
"""
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))
import _where  # noqa: E402

OUT = os.path.join(HERE, 'out')
WORK = os.path.join(OUT, 'desert')
MAKE = os.path.join(_where.REPO, 'blender', 'eidoblend', 'sets', 'desert', 'make.py')
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def main(a):
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    if not ('--reuse' in a and os.path.isfile(os.path.join(WORK, 'build', 'desert_mesh.npz'))):
        r = subprocess.run([sys.executable, MAKE, '--work', WORK, '--quality', 'draft', '--town', '260x160'], cwd=str(_where.REPO))
        check(r.returncode == 0, f'make.py: the chain ran (exit {r.returncode}, {time.time() - t0:.0f} s)')
        if r.returncode:
            return
    # 1. the sources
    src = json.load(open(os.path.join(WORK, 'sources', 'SOURCES.json'), encoding='utf-8'))['sources']
    lv = {k: len(v['levels']) for k, v in src.items()}
    fl = {k: sorted(set().union(*[set(L['fields']) for L in v['levels']])) for k, v in src.items()}
    check(set(lv) == {'dunes', 'mesas', 'range'} and lv['range'] >= 2 and 'sand' in fl['dunes'] and 'A' in fl['range'],
          f'the sources: levels {lv}; fields {fl}')
    # 2. the land
    land = json.load(open(os.path.join(WORK, 'build', 'land.json'), encoding='utf-8'))
    A = np.load(os.path.join(WORK, 'build', 'land_A.npz'))
    h, town = A['h'], A['town']
    check(all(np.isfinite(np.load(os.path.join(WORK, 'build', f'land_{n}.npz'))['h']).all() for n in 'ABC'), 'the land: three rasters, every height finite')
    under = h[town < 0.5]
    ring = h[(town > 60.0) & (town < 80.0)]
    check(under.size > 0 and float(under.max()) < 0.0 and float(np.median(ring)) > 0.0,
          f'the town lies on its plane: under it the land is below z 0 (max {float(under.max()):.2f} m), 60-80 m out it is above (median {float(np.median(ring)):.2f} m)')
    check(land.get('tracks', '').startswith('drawn'), f"the tracks: {land.get('tracks')}")
    # 3. the mesh
    z = np.load(os.path.join(WORK, 'build', 'desert_mesh.npz'))
    co, quads, tris = z['co'], z['quads'], z['tris']
    e = np.concatenate([np.stack([quads[:, k], quads[:, (k + 1) % 4]], 1) for k in range(4)] + [np.stack([tris[:, k], tris[:, (k + 1) % 3]], 1) for k in range(3)])
    e.sort(1)
    _, cnt = np.unique(e, axis=0, return_counts=True)
    ue = np.unique(e, axis=0)
    open_e = ue[cnt == 1]
    mid = 0.5 * (co[open_e[:, 0]] + co[open_e[:, 1]])
    outer = (np.abs(mid[:, 0]) > 32760) | (np.abs(mid[:, 1]) > 32760)
    hidden = (mid[:, 2] < 0.0) & (np.abs(mid[:, 0]) < 1600) & (np.abs(mid[:, 1]) < 1600)
    bad = ~(outer | hidden)
    check(not bad.any(), f'no cracks: {len(open_e)} open edges, {int(outer.sum())} on the border, {int(hidden.sum())} under the town plane, {int(bad.sum())} elsewhere')
    check(int((cnt > 2).sum()) == 0, f'no edge in three faces or more ({int((cnt > 2).sum())})')
    near = (np.abs(co[:, 0]) < 1200) & (np.abs(co[:, 1]) < 900)
    check(float(co[near, 2].max()) < 30.0, f'nothing rises into the flight over the town: highest {float(co[near, 2].max()):.1f} m')
    sc = np.load(os.path.join(WORK, 'build', 'scrub.npz'))
    check(len(sc['pos']) > 1000 and float(sc['pos'][:, 2].min()) > 0.3, f"the scrub: {len(sc['pos'])} shrubs, all above the town's plane")
    print(f'[test] mesh: {len(co)} vertices, {len(quads) + len(tris)} faces', flush=True)
    if '--no-render' in a:
        print('[test] --no-render: no stills')
        return
    # 4. two stills
    stills = os.path.join(OUT, 'stills')
    cmd = _where.blender_cmd(os.path.join(_where.REPO, 'blender', 'eidoblend', 'sets', 'desert', 'cli.py'), 'look', '--work', WORK,
                             '--renders', stills, '--only', 'ring_c_pY,close_dunes', '--town', '260x160')
    r = subprocess.run(cmd, cwd=str(_where.REPO))
    check(r.returncode == 0, f'the stills ran (exit {r.returncode})')
    try:
        from PIL import Image
    except ImportError:
        print('[skip] the stills\' levels: no Pillow in this Python')
        return
    for nm in ('ring_c_pY', 'close_dunes'):
        p = os.path.join(stills, nm + '.png')
        if not os.path.isfile(p):
            check(False, f'still {nm} written')
            continue
        px = np.asarray(Image.open(p).convert('RGB'), np.float32) / 255.0
        m, hi = float(px.mean()), float((px > 0.98).mean())
        check(0.1 < m < 0.9 and hi < 0.05, f'still {nm}: mean {m:.3f}, {hi * 100:.2f} % blown')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception:
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
    print(f'[test] {"ALL PASS" if not FAILS else f"{len(FAILS)} FAIL"}', flush=True)
    sys.exit(1 if FAILS else 0)
