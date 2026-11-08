"""Numeric acceptance of the port beyond parity: Ekigar's own field tests (test/field.test.js), the plan's validation
harness (section 14: tiling, derivatives, diagonal mirror, curvature, determinism, NaN sweep), and the generator's
interfaces (height_at, export round trips, project files, migration, the API).

    python blender/tests/terrain_ekigar/test_generator_properties.py
"""
import json
import math
import os
import sys
import tempfile

import numpy as np

import _ekigar_load

ek = _ekigar_load.load()
fc = ek.field_cpu if hasattr(ek, 'field_cpu') else __import__(f'{ek.__name__}.field_cpu', fromlist=['x'])
results = []


def check(name, ok, detail=''):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}", flush=True)


def lcg(seed):
    s = seed & 0xFFFFFFFF
    while True:
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        yield s / 4294967296


# ------------------------------------------------------------------------------- field.test.js, ported ---

check('wrap_cell is floor-based', [fc.wrap_cell(-1, 8), fc.wrap_cell(-9, 8), fc.wrap_cell(8, 8), fc.wrap_cell(3, 8),
                                   fc.wrap_cell(-1, 0)] == [7, 7, 0, 3, -1])

rng = lcg(7)
worst = 0.0
for _ in range(400):
    x, y = next(rng) * 40 - 20, next(rng) * 40 - 20
    v, dx, dy = fc.noised(x, y)
    e = 1e-6
    fdx = (fc.noised(x + e, y)[0] - fc.noised(x - e, y)[0]) / (2 * e)
    fdy = (fc.noised(x, y + e)[0] - fc.noised(x, y - e)[0]) / (2 * e)
    worst = max(worst, abs(fdx - dx) / max(1.0, abs(fdx)), abs(fdy - dy) / max(1.0, abs(fdy)))
check('noised derivatives are exact', worst < 1e-4, f'worst {worst:.2e}')

worst = 0.0
for _ in range(200):
    x, y = next(rng), next(rng)
    v, dx, dy = fc.fractal_noise(x, y, 3, 5, 2, 0.5, 1, 1)
    e = 1e-6
    fdx = (fc.fractal_noise(x + e, y, 3, 5, 2, 0.5, 1, 1)[0] - fc.fractal_noise(x - e, y, 3, 5, 2, 0.5, 1, 1)[0]) / (2 * e)
    worst = max(worst, abs(fdx - dx) / max(1.0, abs(fdx)))
check('fractal_noise derivatives are exact through the octave chain', worst < 1e-3, f'worst {worst:.2e}')

xs = np.linspace(-5, 5, 300)
a = fc.noised(xs, xs * 0.37 + 1.1, 8, 8)[0]
b = fc.noised(xs + 8, xs * 0.37 + 1.1 - 16, 8, 8)[0]
check('noised is periodic once the lattice is wrapped', np.abs(a - b).max() < 1e-9, f'{np.abs(a - b).max():.1e}')
u0 = fc.noised(xs, xs * 0.37 + 1.1)[0]
u8 = fc.noised(xs + 8, xs * 0.37 + 1.1)[0]
check('negative control: unwrapped noised does not repeat', np.abs(u0 - u8).max() > 0.05, f'{np.abs(u0 - u8).max():.3f}')

f = fc.make_field()
pts = np.array([[next(rng), next(rng)] for _ in range(300)])
r0 = f.evaluate(pts[:, 0], pts[:, 1])
r1 = f.evaluate(pts[:, 0] + 1, pts[:, 1] - 1)
check('the full eroded field tiles on both axes', np.abs(r0['height'] - r1['height']).max() < 1e-8
      and np.abs(r0['dx'] - r1['dx']).max() < 1e-6)

cfg = fc.default_config()
cfg['tile'] = {'x': 1, 'y': 0}
fx = fc.make_field(cfg)
wx = np.abs(fx.evaluate(pts[:, 0], pts[:, 1])['height'] - fx.evaluate(pts[:, 0] + 1, pts[:, 1])['height']).max()
wy = np.abs(fx.evaluate(pts[:, 0], pts[:, 1])['height'] - fx.evaluate(pts[:, 0], pts[:, 1] + 1)['height']).max()
check('x-only periodicity (the ring band) and y genuinely does not tile', wx < 1e-8 and wy > 0.005,
      f'x {wx:.1e}, y {wy:.3f}')

cfg = fc.default_config()
cfg['tile'] = {'x': 0, 'y': 0}
fm = fc.make_field(cfg)
g = np.linspace(0, 64, 220, endpoint=False)
X, Y = np.meshgrid(g, g)
A = fm.evaluate(X, Y)['height'].ravel()
B = fm.evaluate(Y, X)['height'].ravel()
rr = float(np.corrcoef(A, B)[0, 1])
check('no 45-degree mirror symmetry', abs(rr) < 0.05, f'r = {rr:.4f}')

check('field is finite everywhere, including lattice corners', all(np.isfinite(f.evaluate(np.array([0.0, 1 / 3, 0.5]),
                                                                                          np.array([0.0, 2 / 3, 0.5]))['height'])))
ra = f.evaluate(pts[:, 0], pts[:, 1])['height']
check('evaluation is deterministic', np.array_equal(ra, f.evaluate(pts[:, 0], pts[:, 1])['height']))


def gradient_agreement(strength, samples=1500):
    cfg = fc.default_config()
    cfg['erosion']['strength'] = strength
    ff = fc.make_field(cfg)
    r = lcg(53)
    P = np.array([[next(r), next(r)] for _ in range(samples)])
    at = ff.evaluate(P[:, 0], P[:, 1])
    fd = fc.gradient_fd(ff, P[:, 0], P[:, 1], 1e-5)
    la = np.hypot(at['dx'], at['dy'])
    ok = (la > 1e-9) & (fd['slope'] > 1e-9)
    cos = np.clip((at['dx'] * fd['dx'] + at['dy'] * fd['dy'])[ok] / (la[ok] * fd['slope'][ok]), -1, 1)
    ang = np.sort(np.degrees(np.arccos(cos)))
    mag = np.sort(la[ok] / fd['slope'][ok])
    med = lambda v: v[(len(v) - 1) // 2]  # noqa: E731
    return med(ang), med(mag), float((ang < 60).mean())


a0, m0, _ = gradient_agreement(0.0)
check('with erosion off the carried gradient is exact', a0 < 1e-3 and abs(m0 - 1) < 1e-4, f'{a0:.1e} deg, x{m0:.6f}')
a1, m1, w60 = gradient_agreement(0.22)
check('the eroded gradient is approximate as characterised (~29 deg, ~0.42x)', 5 < a1 < 45 and 0.30 < m1 < 0.60
      and w60 > 0.75, f'{a1:.1f} deg, x{m1:.3f}, {w60 * 100:.0f}% within 60 deg')
rep = fc.tiling_report(fc.default_config())
check('tiling_report flags a non-integral period', rep['tiling'] and any('erosion scale' in n for n in rep['notes']))
clean = fc.default_config()
clean['erosion']['scale'] = 1 / (10 * 0.7)
check('a tiling-compatible config reports nothing', len(fc.tiling_report(clean)['notes']) == 0)
check('make_field snaps and reports', f.report['notes'] and f.config['erosion']['scale'] != f.requested['erosion']['scale'])
ug = (np.arange(128) + 0.5) / 128
TX, TY = np.meshgrid(ug, ug)
tr_ = fc.reference_trees(f, TX, TY)
cover = float((tr_['trees'] > 0).mean())
check("the reference demo's tree mask (GetTreesAmount) is finite with partial forest cover",
      np.isfinite(tr_['trees']).all() and 0.05 < cover < 0.9
      and np.allclose(tr_['height'], f.evaluate(TX, TY)['height'], atol=1e-12), f'{cover * 100:.0f}% forest')

# --------------------------------------------------------------------------- plan section 14, graph level ---

NAN_RES = 48
bad = []
for op, graph, target, fixture in ek.gallery():
    r = ek.evaluate_graph(graph, target, resolution=NAN_RES, workers=1)
    if not np.isfinite(r['field']).all() or any(not np.isfinite(v).all() for v in r['outs'].values()):
        bad.append(op)
check(f'NaN sweep: every gallery scene ({len(ek.gallery_ids())}) evaluates finite', not bad, ', '.join(bad))

g, t, _ = ek.operator_example('cinderConeField')
r1 = ek.evaluate_graph(g, t, resolution=64)
r2 = ek.evaluate_graph(g, t, resolution=64, workers=1)
check('determinism: two runs (threaded and serial) are byte-identical', np.array_equal(r1['field'], r2['field']))
# a screen derivative of a value built from one (patternedGround), under erosion: the case where a one-texel band pad
# made 'central' depend on the core count. Both modes, thin bands against one band.
g, ids = ek.chain_graph([('fbm', {}), ('patternedGround', {}), ('phacelle', {})])
same = []
for mode in ('coarse', 'central'):
    r1 = ek.evaluate_graph(g, ids[-1], resolution=80, derivatives=mode, workers=5, chunk_rows=4)
    r2 = ek.evaluate_graph(g, ids[-1], resolution=80, derivatives=mode, workers=1, chunk_rows=80)
    same.append(np.array_equal(r1['field'], r2['field']))
check('determinism: nested screen derivatives under erosion, thin bands vs one band, coarse and central',
      all(same), f'coarse {same[0]}, central {same[1]}; central pad {r1["derivative_pad"]}')

Vec = __import__(f'{ek.__name__}._tsl', fromlist=['Vec']).Vec


def at_points(graph, target, x, y, res=256):
    """Evaluate a graph at scattered points (the field is a pointwise function of p)."""
    return ek.compile_graph(graph, target, ek.Ctx(Vec(np.asarray(x), np.asarray(y)), (1, 1), resolution=res))['field']


# tiling, the exact way: the whole field shifted by one tile on either axis is the same field
TILED = [op for op in ek.gallery_ids()
         if op not in ('slopeMask', 'angleMask', 'terraceStair', 'waveCutPlatform', 'playa', 'planationSurface',
                       'towerKarst', 'cockpitKarst', 'limestonePavement', 'bornhardt', 'badlands', 'patternedGround')]
# Not periodic, and the same in Ekigar (the parity tests prove the port matches): the gradient ramp by definition, and
# the two landforms judged on a ramp fixture (beach cusps on the coast ramp, the lava field on the slope ramp); the
# eroded volcano (its built-in erosion pass uses scale 0.12, i.e. 11.9 cells per tile, which nothing snaps), and the
# rock glacier (its lobe phase runs along a direction mixed toward the local downhill, off the lattice).
KNOWN = {'gradient': 'a ramp', 'beachCusps': 'coast ramp fixture', 'lavaField': 'slope ramp fixture',
         'volcano': "Ekigar: built-in erosion scale 0.12 is not snapped", 'rockGlacier': 'Ekigar: lobe phase off-lattice'}
TILED = [op for op in TILED if op not in KNOWN]
print('     not periodic, as in Ekigar: ' + '; '.join(f'{k} ({v})' for k, v in KNOWN.items()))
rng2 = np.random.default_rng(11)
px_, py_ = rng2.random(600), rng2.random(600)
seams = []
for op in TILED:
    g, t, _ = ek.operator_example(op)
    with np.errstate(all='ignore'):
        a = at_points(g, t, px_, py_).x
        dx_ = np.abs(at_points(g, t, px_ + 1, py_).x - a).max()
        dy_ = np.abs(at_points(g, t, px_, py_ + 1).x - a).max()
    if dx_ > 1e-6 or dy_ > 1e-6:
        seams.append(f'{op} (x {dx_:.1e}, y {dy_:.1e})')
check(f'tiling: {len(TILED)} pointwise operators are exactly tile-periodic on both axes', not seams, '; '.join(seams))
print('     (the 12 screen-derivative operators need a grid; their periodicity rides on the grid evaluation)')

# derivatives: the carried gradient against central differences at scattered points (h = 1e-6), so the reference is
# not limited by the texel spacing. Exact by construction for these; mountain/crater/sandstone/swiss-based operators
# treat a warp as locally constant by design and are characterised, not asserted.
EXACT = ('fbm', 'ridged', 'perlin', 'gradient', 'radialGradient', 'island', 'curves', 'gamma', 'stratify', 'roughen',
         'terrace', 'invert', 'clip', 'threshold', 'softClip', 'fold', 'sand', 'shape', 'cone', 'hemisphere')
rng3 = np.random.default_rng(5)
qx, qy = rng3.random(2000), rng3.random(2000)
hh = 1e-6
worst = []
report = []
for op in EXACT + ('mountain', 'crater', 'phacelle', 'canyon', 'volcano'):
    g, t, _ = ek.operator_example(op)
    with np.errstate(all='ignore'):
        c = at_points(g, t, qx, qy)
        fx_ = (at_points(g, t, qx + hh, qy).x - at_points(g, t, qx - hh, qy).x) / (2 * hh)
        fy_ = (at_points(g, t, qx, qy + hh).x - at_points(g, t, qx, qy - hh).x) / (2 * hh)
    err = np.hypot(c.y - fx_, c.z - fy_) / np.maximum(np.hypot(fx_, fy_), 1e-3)
    med = float(np.median(err))
    if op in EXACT and med > 0.01:
        worst.append(f'{op} {med:.3f}')
    if op not in EXACT:
        report.append(f'{op} {med:.2f}')
check(f'derivatives: {len(EXACT)} exactly-differentiated operators carry the true gradient (median < 1%)',
      not worst, '; '.join(worst))
print('     characterised (approximate by design, median relative error): ' + ', '.join(report))

# curvature: closed forms on a paraboloid and a saddle (masks.js formulas, worldSize/verticalScale units)
n = 129
u = (np.arange(n) + 0.5) / n
U, V = np.meshgrid(u - 0.5, u - 0.5)
W, VS = 400.0, 0.3
for name, h, k in (('paraboloid', 0.5 * (U ** 2 + V ** 2), 1.0), ('saddle', 0.5 * (U ** 2 - V ** 2), 0.0)):
    m = ek.build_masks(h, texel=1 / n, world_size=W, vertical_scale=VS, wrap=(False, False))
    c = n // 2
    r_exact = VS * W / (W * W)          # d2h/dx2 in metres: h'' = 1 (field units per tile^2) -> vs*W / W^2
    mean_exact = -(r_exact + (r_exact if k else -r_exact)) * 0.5
    got = (m['curvMean'][c, c] - 0.5) / 6 / 0.5
    check(f'curvature: {name} mean curvature matches its closed form', abs(got - mean_exact) < 1e-3 * max(1, abs(mean_exact))
          + 1e-9, f'{got:.3e} vs {mean_exact:.3e}')

# ------------------------------------------------------------------------------------------- interfaces ---

hf = ek.generate('volcano', resolution=96, world_size=400)
zg = hf.heights_m
xs, ys = hf.grid_xy()
check('height_at equals the grid at texel centres', np.abs(hf.height_at(xs, ys) - zg).max() < 1e-9)
mid = hf.height_at((xs[10, 10] + xs[10, 11]) / 2, ys[10, 10])
check('height_at interpolates linearly along a mesh edge', abs(mid - (zg[10, 10] + zg[10, 11]) / 2) < 1e-9)
check('mask set present (masks.js + named outputs)', {'slope', 'curvProfile', 'concave', 'crater', 'rim', 'breach'}
      <= set(hf.masks()))

with tempfile.TemporaryDirectory() as td:
    sc = ek.export_heightmap(hf.height, td, formats=('png16', 'r32', 'r16'), world_size=400)
    png = ek.decode_png16_gray(open(os.path.join(td, 'ekigar_height.png'), 'rb').read())
    nrm = ek.normalise_heights(hf.height)['data']
    r32 = ek.decode_r32(open(os.path.join(td, 'ekigar_height.r32'), 'rb').read()).reshape(nrm.shape)
    r16 = ek.decode_r16(open(os.path.join(td, 'ekigar_height.r16'), 'rb').read()).reshape(nrm.shape)
    check('heightmap png16 round trip within one step', np.abs(png['data'] - nrm).max() <= 0.5 / 65535 + 1e-12)
    check('heightmap r32 round trip exact to float32', np.abs(r32 - nrm).max() < 1e-7)
    check('heightmap r16 round trip within one step', np.abs(r16 - nrm).max() <= 0.5 / 65535 + 1e-12)
    check('sidecar carries the elevation range', abs(sc['elevation']['heightRangeMetres']
                                                    - (hf.height.max() - hf.height.min()) * 400 * 0.3) < 1e-9)
    side = ek.export_maps(hf.height, hf.aux, td, world_size=400)
    imgs = [ek.decode_png(open(os.path.join(td, f), 'rb').read()) for f in
            ('ekigar_height16.png', 'ekigar_normal.png', 'ekigar_slope.png', 'ekigar_ridge.png')]
    check('map set: height16 / normal / slope / ridge decode at the field size',
          all(i['width'] == 96 and i['height'] == 96 for i in imgs) and imgs[1]['channels'] == 3)
    pth = os.path.join(td, 'p.json')
    doc = ek.save_project(pth, *ek.single_operator_graph('mesa', {'count': 4})[:1],
                          target=None, res=64)
    a = ek.generate(pth)
    b = ek.generate(json.load(open(pth)))
    check('ekigar-project/3 round trip: saved, reloaded, same terrain', np.array_equal(a.field, b.field)
          and doc['format'] == 'ekigar-project/3')
    hf.save(os.path.join(td, 'hf.npz'))
    hl = ek.Heightfield.load(os.path.join(td, 'hf.npz'))
    check('Heightfield save/load', np.allclose(hl.height, hf.height, atol=1e-6) and set(hl.outs) == set(hf.outs))

legacy = {'graph': {'nodes': [{'id': 'n1', 'op': 'fbm', 'params': {}}, {'id': 'n2', 'op': 'surface', 'params': {},
                                                                        'layer': {'name': 'grass', 'rules': [1]}},
                              {'id': 'n3', 'op': 'heightMask', 'params': {}}],
                    'edges': [{'from': {'node': 'n1', 'port': 'out'}, 'to': {'node': 'n2', 'port': 'in'}},
                              {'from': {'node': 'n3', 'port': 'out'}, 'to': {'node': 'n2', 'port': 'mask2'}}]},
          'target': 'n2'}
mig, warns = ek.migrate_project(legacy)
mm = [n for n in mig['graph']['nodes'] if n['id'] == 'n2'][0]
check('migrate_project: legacy Surface becomes a one-driver Material Map', mm['op'] == 'materialMap'
      and mig['target'] == 'n1' and any(e['to'].get('port') == 'mask' for e in mig['graph']['edges'])
      and len(warns) >= 2 and mm['layers'][0]['bandMax'] == 1.0)

# a project evaluated on a finer grid than it was authored at is the same terrain with more texels: texel radii stay
# in the authored resolution, and screen-derivative slopes keep their scale
gs, ids_s = ek.chain_graph([('fbm', {'frequency': 3, 'amplitude': 0.9}), ('blur', {'radius': 3}), ('slopeMask', {})])
# measured with per-texel ('central') derivatives, so the comparison sees the scaling and not the discretisation: the
# GPU's 2x2 quads ('coarse', Ekigar's and the default) are a different pattern of blocks at each resolution
lo = ek.evaluate_graph(gs, ids_s[-1], resolution=64, derivatives='central')['height']
hi = ek.evaluate_graph(gs, ids_s[-1], resolution=128, field_resolution=64, derivatives='central')['height']
hi_ds = hi.reshape(64, 2, 64, 2).mean(axis=(1, 3))
corr = float(np.corrcoef(lo.ravel(), hi_ds.ravel())[0, 1])
check('a 64-texel graph evaluated at 128 keeps its look (blur radius and slope scale)',
      corr > 0.95 and abs(hi.mean() - lo.mean()) < 0.05 * max(lo.mean(), 1e-3), f'r = {corr:.3f}, mean '
      f'{lo.mean():.3f} vs {hi.mean():.3f}')
# and in the default quad mode the slope keeps its scale (the same mean coverage), though the 2x2 blocks differ
lo_c = ek.evaluate_graph(gs, ids_s[-1], resolution=64)['height']
hi_c = ek.evaluate_graph(gs, ids_s[-1], resolution=128, field_resolution=64)['height']
check('the same with quad (coarse) derivatives keeps the slope scale (mean mask)',
      abs(hi_c.mean() - lo_c.mean()) < 0.05 * max(lo_c.mean(), 1e-3), f'mean {lo_c.mean():.3f} vs {hi_c.mean():.3f}')

mdl = __import__(f'{ek.__name__}.model', fromlist=['x'])
pp = ek.ports_of('phacelle')
gw, idw = ek.chain_graph([('fbm', {}), ('phacelle', {}), ('terrace', {})])
check('wire heuristics: a field lands on in, a mask on the mask port, a chain previews its end',
      mdl.choose_input_port(pp, [], 'field') == 'in' and mdl.choose_input_port(pp, ['in'], 'mask') == 'mask'
      and mdl.downstream_terminal(gw, idw[0]) == idw[-1]
      and mdl.target_after_add(gw, idw[1], ek.graph_ports.required_inputs) == idw[-1]
      and mdl.connection_target_rank('mask', 'field') == 3 and mdl.connection_target_rank('field', 'mask') == 2)

bad_proj = ek.make_project(*ek.single_operator_graph('terraceStair')[:1])
v = ek.api.validate(bad_proj)
check('api.validate names an unwired required input', not v['ok'] and any("'in'" in n for n in v['notes']))
check('api.describe covers every listed operator', all(ek.api.describe(o['id']) for o in ek.list_operators()))
tr = ek.api.tiling_report(ek.api.default_project())
check('api.tiling_report reports the erosion snap', tr['tiling'] and any('snapped' in n for n in tr['notes']))

print(f'properties: {sum(results)}/{len(results)} pass')
sys.exit(0 if all(results) else 1)
