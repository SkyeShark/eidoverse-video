"""Design probe (PORT_PLAN.md section 4.2): fixtures from the Blender edition's numpy twins, for the WGSL ports of the
same kernels to be checked against (kernel_parity.mjs). The inputs are the Blender fluvial package's own parity
inputs (blender/tests/terrain/fluvial/test_kernels.py fields96: a non-square 96 x 80 field with pins), so the WGSL
port is measured exactly as the GLSL kernels were.

    python eidoverse/terrain/tests/design_probes/make_twin_fixtures.py <out_dir>

The Blender edition is found at blender/ beside eidoverse/ in this checkout (a blender-branch checkout holds both
editions), else at $EIDO_BLENDER_EDITION (the root of a checkout of the blender branch). numpy only; no Blender.

Writes <out_dir>/manifest.json and one little-endian float32 (or uint32) .bin per array, row 0 = south, (H, W, C)
C-order: the case list (kernel, uniforms, inputs, expected outputs), the hashes, and the world-noise term table.
"""
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))


def blender_edition():
    cands = [os.path.normpath(os.path.join(HERE, '..', '..', '..', '..')), os.environ.get('EIDO_BLENDER_EDITION', '')]
    for root in cands:
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return root
    sys.exit('make_twin_fixtures: no Blender edition (blender/eidoblend/terrain) here or at $EIDO_BLENDER_EDITION')


ROOT = blender_edition()
BLENDER_DIR = os.path.join(ROOT, 'blender')
TERRAIN_DIR = os.path.join(BLENDER_DIR, 'eidoblend', 'terrain')
sys.path.insert(0, BLENDER_DIR)
import eidoblend  # noqa: E402  (imports nothing)

pkg = types.ModuleType('eidoblend.terrain')                  # plain_import.install's bare package, without its makedirs
pkg.__path__ = [TERRAIN_DIR]
pkg.__package__ = 'eidoblend.terrain'
sys.modules['eidoblend.terrain'] = pkg
eidoblend.terrain = pkg

import numpy as np  # noqa: E402

from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.core import world_noise as N  # noqa: E402
from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402
from eidoblend.terrain.solvers import hillslope as HS  # noqa: E402,F401  (registers creep / threshold twins)

F32 = np.float32
OUT = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: make_twin_fixtures.py <out_dir>')
os.makedirs(OUT, exist_ok=True)
manifest = {'source': 'blender edition numpy twins', 'cases': [], 'hashes': None, 'noise': None}
_n = [0]


def save(a, dtype=np.float32):
    a = np.ascontiguousarray(np.asarray(a, dtype))
    if a.ndim == 2:
        a = a[:, :, None]
    _n[0] += 1
    name = f'a{_n[0]:04d}.bin'
    a.tofile(os.path.join(OUT, name))
    return {'file': name, 'shape': list(a.shape), 'dtype': 'f32' if dtype == np.float32 else 'u32'}


def case(label, kernel, inputs, uniforms):
    """Run the registered twin on (inputs, uniforms) and record inputs, uniforms and the twin's outputs."""
    s = {k: T._prep_inputs({k: v})[k] for k, v in inputs.items()}
    out = T.get_twin(kernel)(s, {k: (int(v) if isinstance(v, int) else F32(v)) for k, v in uniforms.items()})
    manifest['cases'].append({'label': label, 'kernel': kernel, 'uniforms': uniforms,
                              'inputs': {k: save(v) for k, v in s.items()},
                              'outputs': {k: save(np.asarray(v, F32)) for k, v in out.items()}})
    return {k: np.asarray(v, F32) for k, v in out.items()}


def fields96(seed=1, relief=400.0):
    """blender/tests/terrain/fluvial/test_kernels.py fields96, verbatim."""
    shape = (80, 96)
    h = T.random_field(shape, 0.0, relief, seed, smooth=1)
    A = T.random_field(shape, 100.0, 1e6, seed + 1)
    qs = T.random_field(shape, 0.0, 80.0, seed + 2)
    U = T.random_field(shape, 0.0, 3e-3, seed + 3, smooth=2)
    K = (1.5e-5 * (0.5 + T.random_field(shape, 0, 1, seed + 4, smooth=2))).astype(F32)
    Sc = (np.tan(np.radians(35.0)) * (0.85 + 0.3 * T.random_field(shape, 0, 1, seed + 5, smooth=2))).astype(F32)
    G = (0.5 * T.random_field(shape, 0, 1, seed + 6, smooth=2)).astype(F32)
    pw, ph = T.pin_pattern(shape, seed, band=4, value=(0.0, relief))
    rng = np.random.default_rng(seed + 9)
    Ain = np.where(rng.random(shape) > 0.97, rng.uniform(1e5, 1e7, shape), 0.0).astype(F32)
    qin = np.where(Ain > 0, rng.uniform(1.0, 50.0, shape), 0.0).astype(F32)
    loose = T.random_field(shape, 0.0, 6.0, seed + 10)
    mk = T.rgba(T.random_field(shape, 0, 5, seed + 11), T.random_field(shape, 0, 2, seed + 12),
                T.random_field(shape, 0, 2, seed + 13), loose)
    return dict(h=h, A=A, qs=qs, U=U, K=K, Sc=Sc, G=G, pw=pw, ph=ph, Ain=Ain, qin=qin, mk=mk)


f = fields96()
shape = f['h'].shape
st = T.rgba(f['h'], f['A'], f['qs'], T.random_field(shape, 0, 1, 77))
par = T.rgba(f['U'], f['K'], f['Sc'], f['G'])
pin = T.rgba(f['pw'], f['ph'], f['Ain'], f['qin'])
one = np.zeros((1, 1), F32)
col = (np.linspace(0.3, 3.0, 64) * (1.0 + 0.5 * np.sin(np.arange(64)))).astype(F32)
zoff = T.random_field(shape, -40.0, 40.0, 31, smooth=2)
hp = f['h'].copy()
hp[3::7, 3::7] -= 5.0
st_p = T.rgba(hp, f['A'], f['qs'], T.random_field(shape, 0, 1, 77))
for mode_name, mode in T.BOUNDARY_CASES:
    w = case(f'flow_weights {mode_name}', 'flow_weights', {'st': st}, {'uDx': 10.0, 'uP': 1.0, 'uBound': mode})
    case(f'flow_weights p=1.3 {mode_name}', 'flow_weights', {'st': st}, {'uDx': 10.0, 'uP': 1.3, 'uBound': mode})
    base = {'uDx': 10.0, 'uDt': 128.0, 'uM': 0.5, 'uN': 1.0, 'uP': 1.0, 'uColZ0': 0.0, 'uColDz': 1.0, 'uColN': 0,
            'uSlope': 1, 'uPitFill': 1, 'uPitEps': 1e-3, 'uBound': mode}
    ins = {'st': st, 'wsumT': w['outW'], 'par': par, 'pin': pin, 'mk': f['mk'], 'kcol': one, 'zoff': one}
    case(f'route_incise n=1 D-infinity {mode_name}', 'route_incise', ins, base)
    case(f'route_incise n=1 D8 {mode_name}', 'route_incise', ins, dict(base, uSlope=0))
    wp = T.get_twin('flow_weights')({'st': st_p}, {'uDx': F32(10.0), 'uP': F32(1.0), 'uBound': mode})['outW']
    for fillp in (1, 0):
        case(f'route_incise pits filled={fillp} {mode_name}', 'route_incise', dict(ins, st=st_p, wsumT=wp),
             dict(base, uPitFill=fillp))
    case(f'route_incise n=1.5 explicit {mode_name}', 'route_incise', ins, dict(base, uN=1.5))
    case(f'route_incise column {mode_name}', 'route_incise', dict(ins, kcol=col[None, :], zoff=zoff),
         dict(base, uColZ0=-50.0, uColDz=8.0, uColN=64))
    for cap in (5.0, 1.0):
        case(f'creep cap={cap:g} {mode_name}', 'creep', {'st': st, 'par': par, 'pin': pin},
             {'uDx': 10.0, 'uDtSub': 50.0, 'uD': 0.4, 'uCap': cap, 'uBound': mode})
    ex = case(f'threshold_excess {mode_name}', 'threshold_excess', {'st': st, 'par': par}, {'uDx': 10.0, 'uBound': mode})
    for loose in (0, 1):
        case(f'threshold isotropic loose={loose} {mode_name}', 'threshold',
             {'st': st, 'par': par, 'pin': pin, 'mk': f['mk'], 'phiT': ex['outP']},
             {'uDx': 10.0, 'uRate': 0.12, 'uLoose': loose, 'uIso': 1, 'uBound': mode})
        case(f'threshold pair loose={loose} {mode_name}', 'threshold',
             {'st': st, 'par': par, 'pin': pin, 'mk': f['mk'], 'phiT': one},
             {'uDx': 10.0, 'uRate': 0.06, 'uLoose': loose, 'uIso': 0, 'uBound': mode})
st2 = T.rgba(f['h'] + T.random_field(shape, -3, 3, 5), f['A'], f['qs'], f['h'])
case('creep_layers', 'creep_layers', {'st': st2, 'h0': f['h'], 'mk': f['mk']}, {})

# the hashes: common.glsl's PCG chain and u01 on every cell of a grid, Ekigar's lattice hash on signed cells
H, W = 80, 96
jj, ii = np.mgrid[0:H, 0:W]
hs = {'pcg': T.pcg(ii * 7919 + jj * 104729 + 12345), 'pcg2': T.pcg2(ii, jj), 'pcg3': T.pcg3(ii, jj, 77),
      'cell_hash_it3_seed11': T.cell_hash((H, W), 3, 11), 'u01_of_pcg': T.u01(T.pcg2(ii, jj))}
gx, gy = N.hash2(ii - 48 - 8388608 // 4, jj - 40 + 1000003)
manifest['hashes'] = {k: save(v, np.uint32 if v.dtype == np.uint32 else np.float32) for k, v in hs.items()}
manifest['hashes']['ekigar_hash2_gx'] = save(gx)       # world_noise.hash2's gradient: float64 arithmetic
manifest['hashes']['ekigar_hash2_gy'] = save(gy)
# the integer hash itself (world_noise.hash2's integer steps, verbatim) and the gradient in float32 arithmetic, as
# the GLSL kernel (and the WGSL port) compute it
wx = ((np.asarray(ii - 48 - 8388608 // 4, np.int64) + N.HASH_BIAS) & 0xFFFFFFFF).astype(np.uint32)
wy = ((np.asarray(jj - 40 + 1000003, np.int64) + N.HASH_BIAS) & 0xFFFFFFFF).astype(np.uint32)
with np.errstate(over='ignore'):
    hh = (wx * N._M1) ^ (wy * N._M2)
    hh ^= hh >> N._S15
    hh *= N._M3
    hh ^= hh >> N._S13
    hh *= N._M4
    hh ^= hh >> N._S16
manifest['hashes']['ekigar_hash2_u32'] = save(hh, np.uint32)
inv = np.float32(1.0 / 32767.5)
manifest['hashes']['ekigar_hash2_gx_f32'] = save((hh & np.uint32(0xFFFF)).astype(np.float32) * inv - np.float32(1))
manifest['hashes']['ekigar_hash2_gy_f32'] = save((hh >> N._S16).astype(np.float32) * inv - np.float32(1))

# world noise: core/world_noise.field (float64) at a level's cells, and the term table field_gpu dispatches with
lv = L.Level(0, 'main', 40000.0, -12000.0, 96 * 7.5, 7.5, 96)
spec = {'kind': 'sum', 'terms': [{'kind': 'fbm', 'wavelength_m': 2000, 'octaves': 5, 'amp': 0.6},
                                 {'kind': 'ridged', 'wavelength_m': 300, 'octaves': 3, 'amp': 0.6, 'seed': 1},
                                 {'kind': 'gradient', 'wavelength_m': 50, 'amp': 0.3, 'seed': 2}]}
x, y = lv.xy()
want = N.field(spec, x, y, seed=7)
terms, const = [], float(spec.get('offset', 0.0))
for t in spec['terms']:
    tt, c = N._leaf_terms(t, 7, lv.x0, lv.y0)
    terms += tt
    const += c
tab = np.zeros((1, 2 * len(terms), 4), np.float32)
for k, (mode, iw, c, pc, bx, by, fx, fy) in enumerate(terms):
    tab[0, 2 * k] = (mode, iw, c, pc)
    tab[0, 2 * k + 1] = (bx, by, fx, fy)
manifest['noise'] = {'terms': save(tab), 'n_terms': len(terms), 'const': const, 'cell': lv.cell,
                     'expected_float64_as_f32': save(want.astype(np.float32)), 'shape': [lv.n, lv.n]}

with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as fh:
    json.dump(manifest, fh, indent=1)
print(f'[fixtures] {len(manifest["cases"])} kernel cases, {len(manifest["hashes"])} hash arrays, '
      f'{manifest["noise"]["n_terms"]} noise terms -> {OUT}')
