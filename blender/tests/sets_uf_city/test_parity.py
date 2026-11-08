"""Parity: the Blender city kit's numbers against the WebGPU originals (no GPU, no Blender needed).

    cd blender/tests/sets_uf_city
    deno run --no-config --no-lock -A parity_dump.mjs <main checkout>/node_modules/three/build/three.module.js <worktree> out/parity_js.json
    python test_parity.py

Compares, number for number: mulberry32, hash1, nearestAvenue, keyed; the city plan (blocks, lots, seeds, the
supertalls); every building emitBuilding makes (count, types, signs, light spill, the four merged buffers' vertex
counts and coordinate / attribute sums, sampled signs with their quaternions); the far skyline; the lamps; the traffic
paths; a ring sector; the dive camera, its focal point and velocity at 14 times; the eight chorus cameras at five
points each; the twelve rim towers; the 24 cable ends; the noise and night-environment textures (sums and pixels); the
sign atlas's packing. Prints PASS / FAIL per check.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import numpy as np  # noqa: E402
from eidoblend.sets.unknown_force import citykit as KIT  # noqa: E402
from eidoblend.sets.unknown_force import city as C  # noqa: E402
from eidoblend.sets.unknown_force import hole as H  # noqa: E402

J = json.loads((HERE / 'out' / 'parity_js.json').read_text(encoding='utf-8'))
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[uf-city-parity] %s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def maxdiff(a, b):
    """Largest absolute difference between two nested structures of numbers (inf on a shape mismatch)."""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return math.inf
        return max([maxdiff(a[k], b[k]) for k in a] or [0.0])
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return math.inf
        return max([maxdiff(x, y) for x, y in zip(a, b)] or [0.0])
    if isinstance(a, bool) or isinstance(b, bool):
        return 0.0 if bool(a) == bool(b) else math.inf
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b))
    return 0.0 if a == b else math.inf


def close(name, a, b, tol=1e-9):
    d = maxdiff(a, b)
    check(name, d <= tol, f'max |diff| {d:.3g} (tol {tol:g})')


# ---- small maths
r = KIT.rng(1909)
close('rng mulberry32', [r() for _ in range(8)], J['rng1909'], 0.0)
close('hash1', [KIT.hash1(x) for x in (0, 1, 2.5, 7.13, 100.37)], J['hash1'], 1e-9)
close('nearest_avenue', [KIT.nearest_avenue(t, rr) for t, rr in ((0.1, 50), (0.8, 200), (2.0, 400), (-1.2, 170))],
      J['nearestAvenue'], 1e-9)
keys = [{'t': 0, 'v': [0, 1]}, {'t': 5, 'v': [10, 2]}, {'t': 10, 'v': [4, 8]}, {'t': 20, 'v': [7, 7]}]
close('keyed Catmull-Rom', [KIT.keyed(keys, t) for t in (0, 3, 7.5, 12, 33)], J['keyed'], 1e-12)

# ---- the plan
plan = C.plan_city(1909)
jp = J['plan']
check('plan blocks', len(plan['blocks']) == jp['blocks'], f"{len(plan['blocks'])} vs {jp['blocks']}")
check('plan lots', len(plan['lots']) == jp['lots'], f"{len(plan['lots'])} vs {jp['lots']}")
close('plan supertalls', plan['supertalls'], jp['supertalls'], 1e-9)
lot_keys = ('zone', 'r0', 'r1', 't0', 't1', 'seed')
close('plan first lots', [{k: l[k] for k in lot_keys} for l in plan['lots'][:6]],
      [{k: l[k] for k in lot_keys} for l in jp['firstLots']], 1e-9)
close('plan seed sum', sum(l['seed'] for l in plan['lots']), jp['seedSum'], 1e-7)
close('plan block sample', [plan['blocks'][i] for i in (0, 7, 50, len(plan['blocks']) - 1)], jp['blockSample'], 1e-9)

# ---- every building
buf = {k: KIT.GeoBuf() for k in ('concrete', 'metal', 'frame', 'strip')}
bctx = {'buf': buf, 'signs': [], 'lights': []}
built = [b for b in (C.emit_building(l, bctx) for l in sorted(plan['lots'], key=lambda l: l['r0'])) if b]
jb = J['buildings']
types = {}
for b in built:
    types[b.get('type') or 'plaza'] = types.get(b.get('type') or 'plaza', 0) + 1
check('buildings count', len(built) == jb['count'], f"{len(built)} vs {jb['count']}")
check('building types', types == jb['types'], f'{types} vs {jb["types"]}')
check('building signs', len(bctx['signs']) == jb['signs'], f"{len(bctx['signs'])} vs {jb['signs']}")
check('shop light spill', len(bctx['lights']) == jb['lights'], f"{len(bctx['lights'])} vs {jb['lights']}")
check('merged buffers (vertices)', {k: b.count for k, b in buf.items()} == jb['verts'],
      f"{ {k: b.count for k, b in buf.items()} } vs {jb['verts']}")
close('building heights (sum)', sum(b['H'] for b in built), jb['heightSum'], 1e-6)
close('first buildings', built[:5], jb['firstBuilt'], 1e-9)
sig = [bctx['signs'][i] for i in (0, 1, 17, 200, 999, len(bctx['signs']) - 1)]
close('sign sample (id, pos, quaternion, size, gain, flicker)',
      [{'id': s['id'], 'pos': s['pos'], 'quat': list(s['quat']), 'w': s['w'], 'h': s['h'], 'gain': s['gain'],
        'flicker': s['flicker']} for s in sig],
      [{k: v for k, v in s.items() if k != 'power'} for s in jb['signSample']], 1e-9)
# power = hash1(x 0.37 + z 0.73): the sine hash turns a last-bit difference in a position into ~1e-7
close('sign sample (power threshold)', [s['power'] for s in sig], [s['power'] for s in jb['signSample']], 1e-6)
close('light spill sample', [bctx['lights'][i] for i in (0, 5, len(bctx['lights']) - 1)], jb['lightSample'], 1e-9)
Pc = buf['concrete'].arrays()[0]
close('concrete positions (sum per axis)', Pc.sum(0).tolist(), jb['posSum'], 1e-3)
close('metal uv (sum)', buf['metal'].arrays()[1].sum(0).tolist(), jb['uvSum'], 1e-3)
close('frame aT (sum)', buf['frame'].arrays()[2].sum(0).tolist(), jb['aTSum'], 1e-4)
close('strip aM (sum)', buf['strip'].arrays()[3].sum(0).tolist(), jb['aMSum'], 1e-4)
far = KIT.GeoBuf()
C.emit_far_skyline(far)
check('far skyline vertices', far.count == J['far']['verts'], f"{far.count} vs {J['far']['verts']}")
close('far skyline positions (sum)', far.arrays()[0].sum(0).tolist(), J['far']['posSum'], 1e-3)

# ---- lamps, traffic, ground
lamps = C.plan_lamps()
check('lamps count', len(lamps) == J['lamps']['count'], f"{len(lamps)} vs {J['lamps']['count']}")
close('lamps sample', [lamps[i] for i in (0, 1, 100, len(lamps) - 1)], J['lamps']['sample'], 1e-9)
paths = C.plan_traffic()
check('traffic paths', len(paths) == J['traffic']['count'], f"{len(paths)} vs {J['traffic']['count']}")
close('traffic sample', [paths[i] for i in (0, 1, 500, len(paths) - 1)], J['traffic']['sample'], 1e-9)
close('traffic speed / phase sums', [sum(p['speed'] for p in paths), sum(p['phase'] for p in paths)],
      [J['traffic']['speedSum'], J['traffic']['phaseSum']], 1e-6)
P, Q = C.ring_sector(120, 160, 0.2, 0.6, 11.7, 12.16, 5)
check('ring sector vertices', len(P) == J['ringSector']['n'], f"{len(P)} vs {J['ringSector']['n']}")
close('ring sector (first quads, sum)', [np.asarray(P[:4]).ravel().tolist(), float(np.sum(P))],
      [J['ringSector']['p0'], J['ringSector']['sum']], 1e-9)

# ---- cameras
dmax = 0.0
for row in J['dive']:
    c = C.dive_cam_three(row['t'])
    f = C.dive_focal_three(row['t'])
    v = KIT.cam_velocity(C.dive_cam_three, row['t'])
    dmax = max(dmax, maxdiff([c['pos'], c['target'], c['fov'], c['roll'], c['up'], f, v],
                             [row['pos'], row['target'], row['fov'], row['roll'], row['up'], row['focal'], row['vel']]))
check('dive camera, focal, velocity (14 times)', dmax < 1e-7, f'max |diff| {dmax:.3g}')
close('DIVE_C3 (three axes)', C.DIVE_C3, J['DIVE_C'], 1e-12)
close('DIVE_C (Blender axes)', list(C.DIVE_C), list(KIT.to_blender(J['DIVE_C'])), 1e-12)
hmax = 0.0
for n, rows in J['holeCams'].items():
    for u, row in zip((0, 0.3, 0.5, 0.9, 1.0), rows):
        c = H.hole_cam_three(n, u * H.HOLE_CAM_DUR[n])
        hmax = max(hmax, maxdiff({k: c[k] for k in row}, row))
check('chorus cameras (8 x 5)', hmax < 1e-9, f'max |diff| {hmax:.3g}')
check('hole cam durations', H.HOLE_CAM_DUR == J['holeCamDur'])
ren = {'th': 'th', 'half': 'half', 'rIn': 'r_in', 'rOut': 'r_out', 'H': 'H', 'lean': 'lean', 'bbY': 'bb_y', 'seed': 'seed'}
close('RIM (12 towers)', [{k: r[ren[k]] for k in ren} for r in H.RIM], J['RIM'], 1e-9)
close('cable ends (24)', [H._cable_ends_three(i, k) for i in range(12) for k in (0, 1)], J['cables'], 1e-9)
# Blender-axis conversions of the public API
c3, cb = C.dive_cam_three(16.0), C.dive_cam(16.0)
check('dive_cam in Blender axes', maxdiff(list(cb['pos']), [c3['pos'][0], -c3['pos'][2], c3['pos'][1]]) < 1e-12)

# ---- textures
nz = KIT.noise_texture_rgba()
close('noise texture (channel sums)', nz.reshape(-1, 4).sum(0).astype(int).tolist(), J['noise']['sum'], 0)
close('noise texture (pixels)', [nz[y, x].tolist() for x, y in ((0, 0), (17, 3), (255, 400), (511, 511))], J['noise']['px'], 0)
ev = KIT.night_env_rgba()
close('night environment (channel sums)', ev[..., :3].reshape(-1, 3).sum(0).astype(int).tolist(), J['env']['sum'], 0)
close('night environment (pixels)', [ev[y, x].tolist() for x, y in ((0, 0), (100, 120), (300, 140), (511, 255))],
      J['env']['px'], 0)

# ---- the sign atlas's packing (drawn here on the canvas port; its PNG goes to out/ for a look)
atlas = KIT.make_sign_atlas(None)
close('sign atlas items (uv rects)', atlas['items'], J['atlas'], 1e-12)
from PIL import Image  # noqa: E402
Image.fromarray(atlas['rgba'], 'RGBA').save(HERE / 'out' / 'canvas_sign_atlas.png')

fails = [n for n, ok in results if not ok]
print(f'[uf-city-parity] {len(results) - len(fails)}/{len(results)} passed' + (f'; FAILED: {fails}' if fails else ''))
sys.exit(1 if fails else 0)
