"""The numpy originals of core/prims.js (PORT_PLAN.md 3.4 and 8.2, P1), run on recorded inputs, for
tests/core_runner/prims_test.mjs to check the GPU primitives against.

    <Blender's python> -I eidoverse/terrain/tests/core_runner/prims_expected.py [out_dir]

Run it with Blender's own Python (a Blender folder's <version>/python/bin/python), never another (PORT_PLAN.md 5.1):
the Blender edition computes with the numpy that Python carries (numpy 2.3.4 in Blender 5.2), and np.percentile's
arithmetic differs between numpy versions. numpy only; no Blender, no GPU. The default out_dir is
tests/out/core_runner/prims_<numpy version>/; the manifest records the Python, numpy and zlib versions.

The Blender edition is found at blender/ beside eidoverse/ in this checkout (a blender-branch checkout holds both
editions), else at $EIDO_BLENDER_EDITION (the root of a checkout of the blender branch). Its functions are the
oracles, called as they are: solvers/hydro.py fill_depressions, flat_distance, flow_receivers, path_steps,
_terminal_of and box_blur, core/metrics.py label, solvers/hillslope.py and masks.py gaussian_blur, volcanic.py
_gauss_fft and _dilate, hydraulic.py _box; numpy's own percentile, quantile and median (each call form: a number q
and a list, float32 and float64 data, with ties, at 512, 1024 and 2048 cells a side too), argsort, lexsort, cumsum,
bincount, flatnonzero and argmin; np.fft.rfft2 on what core/metrics.py radial_spectrum hands it, and fft2. The DEMs (palouse_hills, crater_lake) are read where real_place reads them
($EIDO_TERRAIN_DEMS, then the Blender edition's tests/terrain/reference/data); without them those cases are left out.

Writes manifest.json (numpy's version, the Blender commit, the cases) and one little-endian .bin per array, row 0 =
south, C order: f32, f64, u32 or i32 as the manifest says.
"""
import json
import math
import os
import subprocess
import sys
import types
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))


def blender_edition():
    cands = [os.path.normpath(os.path.join(HERE, '..', '..', '..', '..')), os.environ.get('EIDO_BLENDER_EDITION', '')]
    for root in cands:
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return root
    sys.exit('prims_expected: no Blender edition (blender/eidoblend/terrain) here or at $EIDO_BLENDER_EDITION')


ROOT = blender_edition()
BLENDER_DIR = os.path.join(ROOT, 'blender')
TERRAIN_DIR = os.path.join(BLENDER_DIR, 'eidoblend', 'terrain')
sys.path.insert(0, BLENDER_DIR)
import eidoblend  # noqa: E402  (imports nothing)

pkg = types.ModuleType('eidoblend.terrain')                  # the bare package, as make_twin_fixtures.py makes it
pkg.__path__ = [TERRAIN_DIR]
pkg.__package__ = 'eidoblend.terrain'
sys.modules['eidoblend.terrain'] = pkg
eidoblend.terrain = pkg

import numpy as np  # noqa: E402

from eidoblend.terrain.core import metrics as M  # noqa: E402
from eidoblend.terrain.core import io as IO  # noqa: E402
from eidoblend.terrain.solvers import hydro as HY  # noqa: E402
from eidoblend.terrain.solvers import hillslope as HS  # noqa: E402
from eidoblend.terrain.solvers import hydraulic as HD  # noqa: E402
from eidoblend.terrain.solvers import volcanic as VO  # noqa: E402
from eidoblend.terrain import masks as MK  # noqa: E402

F32 = np.float32
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'out', 'core_runner', 'prims_' + np.__version__)
os.makedirs(OUT, exist_ok=True)
_n = [0]
DT = {np.dtype(np.float32): 'f32', np.dtype(np.float64): 'f64', np.dtype(np.uint32): 'u32', np.dtype(np.int32): 'i32'}


def save(a, dtype=None):
    a = np.ascontiguousarray(np.asarray(a, dtype) if dtype is not None else np.asarray(a))
    if a.dtype not in DT:
        raise TypeError(f'save: {a.dtype}')
    _n[0] += 1
    name = f'p{_n[0]:04d}.bin'
    a.astype(a.dtype.newbyteorder('<')).tofile(os.path.join(OUT, name))
    return {'file': name, 'shape': list(a.shape), 'dtype': DT[a.dtype]}


def git(*args):
    try:
        return subprocess.run(['git', '-C', ROOT, *args], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


# ------------------------------------------------------------------------------------------------- inputs ---

def noise(shape, seed, octaves=5, amp=400.0):
    """A float32 field of value noise: hills, pits and passes at several scales (any shape)."""
    rng = np.random.default_rng(seed)
    h, w = shape
    out = np.zeros(shape)
    for o in range(octaves):
        cells = 2 ** (o + 2)
        g = rng.random((cells + 3, cells + 3))
        yy = np.linspace(0, cells, h, endpoint=False)
        xx = np.linspace(0, cells, w, endpoint=False)
        y0, x0 = np.floor(yy).astype(int), np.floor(xx).astype(int)
        ty, tx = (yy - y0)[:, None], (xx - x0)[None, :]
        ty, tx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)
        a = g[y0][:, x0] * (1 - tx) + g[y0][:, x0 + 1] * tx
        b = g[y0 + 1][:, x0] * (1 - tx) + g[y0 + 1][:, x0 + 1] * tx
        out += (a * (1 - ty) + b * ty) * amp / 2 ** o
    return (out + 1200.0).astype(F32)


def dem(name):
    """(heights in metres, row 0 south) of a reference DEM, as real_place reads it (core/io.py read_png), or None."""
    dirs = [d for d in os.environ.get('EIDO_TERRAIN_DEMS', '').split(os.pathsep) if d]
    dirs.append(os.path.join(BLENDER_DIR, 'tests', 'terrain', 'reference', 'data'))
    for d in dirs:
        p = os.path.join(d, name + '.json')
        if os.path.isfile(p):
            with open(p, encoding='utf-8') as f:
                meta = json.load(f)
            v = IO.read_png(os.path.join(d, meta['height_png']))
            lo, hi = float(meta['height_min_m']), float(meta['height_max_m'])
            return np.ascontiguousarray((lo + v.astype(np.float64) * ((hi - lo) / 65535.0))[::-1]).astype(F32)
    return None


cases = []


def case(kind, label, inputs, outputs, **params):
    cases.append({'kind': kind, 'label': label, 'inputs': inputs, 'outputs': outputs, 'params': params})


fields = {
    'noise96x80': noise((80, 96), 1),
    'noise257x300': noise((257, 300), 2, octaves=6),
    'terraced': (np.round(noise((120, 136), 3) / 25.0) * 25.0).astype(F32),        # flats and ties everywhere
}
for nm in ('palouse_hills', 'crater_lake'):
    d = dem(nm)
    if d is not None:
        fields[nm] = d
print('[prims_expected] fields:', {k: v.shape for k, v in fields.items()})
saved = {k: save(v) for k, v in fields.items()}

# ------------------------------------------------------------------------------------------- the fill ---
for nm, wrap, sea in [('noise96x80', (False, False), None), ('noise96x80', (False, False), 1450.0),
                      ('noise96x80', (True, False), None), ('noise96x80', (False, True), None),
                      ('noise96x80', (True, True), None), ('noise96x80', (True, True), 1400.0),
                      ('noise257x300', (False, False), None), ('terraced', (False, False), None),
                      ('terraced', (True, True), None), ('palouse_hills', (False, False), None),
                      ('crater_lake', (False, False), None), ('crater_lake', (False, False), 1900.0)]:
    if nm not in fields:
        continue
    filled, info = HY.fill_depressions(fields[nm], wrap=wrap, sea_level=sea)
    if not np.array_equal(filled, filled.astype(F32).astype(np.float64)):
        sys.exit(f'prims_expected: the fill of {nm} is not float32-exact (the GPU result is float32)')
    case('fill', f'fill {nm} wrap={wrap} sea={sea}', {'h': saved[nm]}, {'filled': save(filled, F32)},
         wrap=list(wrap), sea_level=sea, outlet=info['outlet'], basins=info['basins'],
         filled_cells=int(np.count_nonzero(filled > fields[nm])))

# ------------------------------------------------------------------------------------------- labels ---
def spiral(n):
    m = np.zeros((n, n), bool)
    lo, hi, k = 0, n - 1, 0
    while lo < hi:
        if k % 2 == 0:
            m[lo, lo:hi + 1] = m[lo:hi + 1, hi] = m[hi, lo:hi + 1] = True
            m[lo + 2:hi + 1, lo] = True
        lo += 2
        hi -= 2
        k += 1
    return m


rng = np.random.default_rng(7)
masks = {
    'random30_257x300': rng.random((257, 300)) < 0.30,
    'random59_257x300': rng.random((257, 300)) < 0.59,             # near 8-connected site percolation
    'spiral_128': spiral(128),
    'full_40x33': np.ones((40, 33), bool),
    'empty_17x21': np.zeros((17, 21), bool),
}
for nm in ('palouse_hills', 'crater_lake', 'noise257x300'):
    if nm in fields:
        filled, _ = HY.fill_depressions(fields[nm])
        masks[f'depressions_{nm}'] = (filled - fields[nm]) > 0
for nm, m in masks.items():
    lab, n = M.label(m)
    case('label', f'label {nm}', {'mask': save(m.astype(np.uint32))}, {'labels': save(lab.astype(np.uint32))}, count=n)

# ------------------------------------------------------------------------------- percentiles and medians ---
pcases = [('noise257x300', None), ('terraced', None)]
if 'palouse_hills' in fields:
    pcases.append(('palouse_hills', None))
for nm, _ in pcases:
    a = fields[nm]
    mask = rng.random(a.shape) < 0.37
    for qs in ([10, 50, 90, 99], 50, [0, 100], [0.5, 99.5], 37.3, [25.0], 99.9, 0.1):
        for masked in (False, True):
            v = np.percentile(a[mask] if masked else a, qs)
            case('percentile', f'percentile {nm} q={qs} masked={masked}', {'a': saved[nm]} | ({'mask': save(mask.astype(F32))} if masked else {}),
                 {}, q=qs, expected=np.asarray(v, np.float64).ravel().tolist(), scalar=not isinstance(qs, list), masked=masked)
    for sub in (a, a[:-1, :], a[mask]):
        v = np.median(sub)
        case('median', f'median {nm} n={sub.size}', {'a': save(np.ascontiguousarray(sub).ravel())}, {},
             expected=float(v), dtype=str(np.asarray(v).dtype), data_dtype='float32')
    # the same float32 values held in float64, as numpy code that converts first holds them
    a64 = a.astype(np.float64)
    for qs in ([10, 50, 90, 99], 37.3, 99.9):
        v = np.percentile(a64, qs)
        case('percentile', f'percentile {nm} (as float64) q={qs}', {'a': saved[nm]}, {}, q=qs,
             expected=np.asarray(v, np.float64).ravel().tolist(), scalar=not isinstance(qs, list), masked=False, data_dtype='float64')
    v = np.median(a64[:-1, :])
    case('median', f'median {nm} (as float64) n={a64[:-1, :].size}', {'a': save(np.ascontiguousarray(a[:-1, :]).ravel())}, {},
         expected=float(v), dtype=str(np.asarray(v).dtype), data_dtype='float64')
    for qs in (0.373, [0.1, 0.5, 0.9], 0.995):
        for data, dd in ((a, 'float32'), (a64, 'float64')):
            v = np.quantile(data, qs)
            case('quantile', f'quantile {nm} ({dd}) q={qs}', {'a': saved[nm]}, {}, q=qs,
                 expected=np.asarray(v, np.float64).ravel().tolist(), scalar=not isinstance(qs, list), data_dtype=dd)


# every call form at the level sizes (the float32 index can pick another order statistic at 2048 cells a side),
# on terraced ground (ties) and smooth ground
for side in (512, 1024, 2048):
    for kind in ('terraced', 'smooth'):
        g = noise((side, side), 100 + side, octaves=7)
        if kind == 'terraced':
            g = (np.round(g / 2.0) * 2.0).astype(F32)
        ref = save(g)
        g64 = g.astype(np.float64)
        for fn, qs in (('percentile', 37.3), ('percentile', 99.5), ('percentile', [0.5, 10, 50, 90, 99.5]),
                       ('quantile', 0.373), ('quantile', [0.25, 0.75])):
            for data, dd in ((g, 'float32'), (g64, 'float64')):
                v = getattr(np, fn)(data, qs)
                case(fn, f'{fn} {kind} {side}x{side} ({dd}) q={qs}', {'a': ref}, {}, q=qs,
                     expected=np.asarray(v, np.float64).ravel().tolist(), scalar=not isinstance(qs, list), masked=False,
                     data_dtype=dd)
        for data, dd in ((g, 'float32'), (g64, 'float64')):
            v = np.median(data)
            case('median', f'median {kind} {side}x{side} ({dd})', {'a': ref}, {}, expected=float(v),
                 dtype=str(np.asarray(v).dtype), data_dtype=dd)

# ------------------------------------------------------------------------------ sorts, scans, histograms ---
keys_t = fields['terraced'].ravel()                                        # float keys with many ties
case('argsort', 'argsort terraced (float ties)', {'a': saved['terraced']},
     {'perm': save(np.argsort(keys_t, kind='stable').astype(np.uint32))}, descending=False)
case('argsort', 'argsort -terraced (descending)', {'a': saved['terraced']},
     {'perm': save(np.argsort(-keys_t, kind='stable').astype(np.uint32))}, descending=True)
ku = rng.integers(0, 2 ** 32, 70001, dtype=np.uint64).astype(np.uint32)
case('argsort', 'argsort u32 random (70001)', {'a': save(ku)}, {'perm': save(np.argsort(ku, kind='stable').astype(np.uint32))},
     descending=False)
ki = rng.integers(-50, 50, 9000).astype(np.int32)
case('argsort', 'argsort i32 with negatives and ties', {'a': save(ki)},
     {'perm': save(np.argsort(ki, kind='stable').astype(np.uint32))}, descending=False)
# the fill's own lexsort pattern: np.lexsort((ep, key)), key = lo * B + hi
ep = (np.round(rng.random(50000) * 300) / 3).astype(F32)
key = rng.integers(0, 4000, 50000).astype(np.uint32)
case('lexsort', 'lexsort (float ep, int key)', {'k0': save(ep), 'k1': save(key)},
     {'perm': save(np.lexsort((ep, key)).astype(np.uint32))})
skey = np.sort(key)
first = np.ones(skey.size, bool)
first[1:] = skey[1:] != skey[:-1]
case('segments', 'segment heads of sorted keys', {'keys': save(skey)}, {'first': save(first.astype(np.uint32))})
for n in (1, 255, 256, 257, 65539, 1000003):
    v = rng.integers(0, 9, n).astype(np.uint32)
    case('cumsum', f'cumsum {n}', {'a': save(v)}, {'inclusive': save(np.cumsum(v).astype(np.uint32))})
fl = (rng.random(300007) < 0.1).astype(np.uint32) * rng.integers(1, 5, 300007).astype(np.uint32)
case('nonzero', 'flatnonzero (300007)', {'flags': save(fl)}, {'index': save(np.flatnonzero(fl).astype(np.uint32))})
bk = rng.integers(0, 1100, 200003).astype(np.uint32)
case('bincount', 'bincount (200003 into 1000; keys past the bins ignored)', {'keys': save(bk)},
     {'counts': save(np.bincount(bk[bk < 1000], minlength=1000).astype(np.uint32))}, bins=1000)
for nm in ('terraced', 'noise257x300'):
    a = fields[nm]
    st = {'min': float(a.min()), 'max': float(a.max()), 'sum': float(a.astype(np.float64).sum()),
          'nonzero': int(np.count_nonzero(a)), 'argmin': int(np.argmin(a))}
    case('stats', f'stats {nm}', {'a': saved[nm]}, {}, **st)

# ------------------------------------------------------------------- pointer jumping and flat distance ---
for nm in ('noise257x300', 'palouse_hills'):
    if nm not in fields:
        continue
    filled, _ = HY.fill_depressions(fields[nm])
    rec = HY.flow_receivers(filled)
    steps = HY.path_steps(rec)
    term = HY._terminal_of(rec)
    # path maxima along the receivers, the other way: terminals first, each cell from its receiver's value
    val = fields[nm].ravel().astype(np.float64)
    pm = val.copy()
    order = np.argsort(steps, kind='stable')
    bounds = np.searchsorted(steps[order], np.arange(int(steps.max()) + 2))
    for k in range(1, int(steps.max()) + 1):
        idx = order[bounds[k]:bounds[k + 1]]
        pm[idx] = np.maximum(val[idx], pm[rec[idx]])
    sh = fields[nm].shape
    case('paths', f'path_steps / _terminal_of / path maxima {nm}', {'rec': save(rec.reshape(sh).astype(np.int32)), 'val': saved[nm]},
         {'steps': save(steps.reshape(sh).astype(np.uint32)), 'terminal': save(term.reshape(sh).astype(np.uint32)),
          'pathmax': save(pm.reshape(sh).astype(F32))}, longest=int(steps.max()))
    fs = save(filled, F32)
    for wrap, sea in [((False, False), None), ((False, False), 1300.0 if nm == 'noise257x300' else None)]:
        d = HY.flat_distance(filled, wrap, sea)
        case('flat', f'flat_distance filled {nm} wrap={wrap} sea={sea}', {'surface': fs},
             {'dist': save(d.astype(np.uint32))}, wrap=list(wrap), sea_level=sea, longest=int(d.max()))
for wrap in [(False, False), (True, False), (True, True)]:
    d = HY.flat_distance(fields['terraced'], wrap, None)
    case('flat', f'flat_distance terraced wrap={wrap}', {'surface': saved['terraced']}, {'dist': save(d.astype(np.uint32))},
         wrap=list(wrap), sea_level=None, longest=int(d.max()))

# --------------------------------------------------------------------------------------------- filters ---
g257 = fields['noise257x300']
for s in (0.5, 1.0, 1.7, 3.2, 12.5, 40.0):
    case('gauss', f'hillslope.gaussian_blur sigma={s}', {'a': saved['noise257x300']}, {'out': save(HS.gaussian_blur(g257, s))},
         mode='reflect', sigma=s)
if 'palouse_hills' in fields:
    case('gauss', 'hillslope.gaussian_blur palouse sigma=6', {'a': saved['palouse_hills']},
         {'out': save(HS.gaussian_blur(fields['palouse_hills'], 6.0))}, mode='reflect', sigma=6.0)
win = (fields['noise96x80'] - F32(1500.0)).astype(F32)                   # masks' callers subtract a centre first
for s in (0.8, 2.0, 5.5):
    out = MK.gaussian_blur(win, s)
    case('gauss', f'masks.gaussian_blur sigma={s} (good size {MK._good_size(win.shape[0])}x{MK._good_size(win.shape[1])})',
         {'a': save(win)}, {'out': save(out.astype(np.float64))}, mode='periodic', size='good', sigma=s)
patch = np.zeros((90, 70), F32)
patch[20:70, 15:55] = noise((50, 40), 5, amp=50.0) - F32(1200.0)
for s in (1.5, 4.0):
    case('gauss', f'volcanic._gauss_fft sigma={s}', {'a': save(patch)}, {'out': save(VO._gauss_fft(patch, s))},
         mode='periodic', size=None, sigma=s)
for r, wrap in [(1, (False, False)), (3, (True, False)), (10, (True, True)), (4, (False, True))]:
    case('box', f'hydro.box_blur radius={r} wrap={wrap}', {'a': saved['noise257x300']},
         {'out': save(HY.box_blur(g257, r, wrap))}, r=int(max(1, r)), wrap=list(wrap), passes=3, axes='xy')
for r in (2, 7):
    case('box', f'hydraulic._box r={r}', {'a': saved['noise257x300']}, {'out': save(HD._box(g257, r))},
         r=r, wrap=[False, False], passes=1, axes='yx')
for r in (1, 4):
    case('dilate', f'volcanic._dilate r={r}', {'a': saved['terraced']}, {'out': save(VO._dilate(fields['terraced'], r).astype(F32))}, r=r)

# ------------------------------------------------------------------------------------------------- FFT ---
def spectrum_input(h):
    """What core/metrics.py radial_spectrum hands np.fft.rfft2: the field less its least-squares plane, Hann-windowed
    (its own lines), as float32: the GPU's input, so only the transform is compared."""
    z = np.asarray(h, dtype=np.float64)
    ny, nx = z.shape
    jj, ii = np.mgrid[0:ny, 0:nx]
    A = np.stack([ii.ravel(), jj.ravel(), np.ones(z.size)], axis=1)
    coef, *_ = np.linalg.lstsq(A, z.ravel(), rcond=None)
    z = z - (A @ coef).reshape(z.shape)
    w = np.outer(np.hanning(ny), np.hanning(nx))
    return (z * w).astype(F32)


def spectrum_bins(shape, nbins=48):
    """radial_spectrum's band of every rfft2 coefficient (nbins where it is outside every band), cell 1."""
    ny, nx = shape
    k = np.hypot(np.fft.fftfreq(ny)[:, None], np.fft.rfftfreq(nx)[None, :])
    edges = np.logspace(math.log10(1.0 / max(nx, ny)), math.log10(0.5), nbins + 1)
    b = np.digitize(k.ravel(), edges) - 1
    return np.where((b >= 0) & (b < nbins), b, nbins).reshape(k.shape).astype(np.uint32)


ffts = [('noise 64x128 (powers of two)', noise((64, 128), 11)), ('noise 80x96 (Bluestein on both axes)', fields['noise96x80'])]
for nm in ('palouse_hills', 'crater_lake'):
    if nm in fields:
        ffts.append((f'{nm} as radial_spectrum takes it', spectrum_input(fields[nm])))
for label, a in ffts:
    a = np.ascontiguousarray(a, F32)
    F = np.fft.rfft2(a.astype(np.float64))
    P = np.abs(F) ** 2
    b = spectrum_bins(a.shape)
    cnt = np.bincount(b.ravel(), minlength=49)[:48]
    tot = np.bincount(b.ravel(), weights=P.ravel(), minlength=49)[:48]
    case('rfft2', f'rfft2 {label}', {'a': save(a)}, {'F': save(np.stack([F.real, F.imag], -1)), 'bins': save(b)},
         band_power=np.where(cnt > 0, tot / np.maximum(cnt, 1), 0.0).tolist())
zc = np.stack([noise((50, 70), 12), noise((50, 70), 13)], -1).astype(F32) - F32(1300.0)
Fc = np.fft.fft2(zc[..., 0].astype(np.float64) + 1j * zc[..., 1].astype(np.float64))
case('fft2', 'fft2 complex 50x70', {'a': save(zc)}, {'F': save(np.stack([Fc.real, Fc.imag], -1))})

with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump({'numpy': np.__version__, 'python': sys.version.split()[0], 'zlib': zlib.ZLIB_RUNTIME_VERSION,
               'python_executable': os.path.basename(sys.executable), 'blender_commit': git('rev-parse', 'HEAD'),
               'blender_package_changes': git('status', '--short', '--', 'blender/eidoblend/terrain/core',
                                              'blender/eidoblend/terrain/solvers', 'blender/eidoblend/terrain/masks.py'),
               'cases': cases}, f, indent=1)
print(f'[prims_expected] numpy {np.__version__}: {len(cases)} cases -> {OUT}')
