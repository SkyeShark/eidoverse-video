"""Design probe (PORT_PLAN.md 5.4 and 5.7, the revision): the chaos floor under the revised protocol, and the
dispatch log a port is compared by.

    bash run_blender.sh eidoverse/terrain/tests/design_probes/blender_floor_patterns.py -- <out.json> <patterns> <recipe> [...]

Per recipe (draft quality, seed 1): a base run, then <patterns> perturbed runs, every run after the solvers'
per-process memos are cleared (aeolian._TILES, volcanic._AGED_PATCHES, karst._PLANS and _DOMAINS,
strata._COLUMN_CACHE, real_place._CACHE: a dune tile, for one, is grown once per process and returned again). A
perturbed run moves values by one float32 ulp (+1 ulp on a quarter of the cells, -1 ulp on another quarter) at two
points, from outside, with no change to the Blender edition:
- at each op's entry, every float field of its level (numpy's default_rng([pattern, op call])), through the level
  runner's get_op: every op, evolving or not, including those that run in numpy;
- inside each op call, the images each kernel writes, right after that kernel's first dispatch in the call
  (default_rng([pattern, op call, kernel, 1])), read back, moved and copied back by a copy kernel: this reaches GPU
  state an op makes itself rather than reads from the level (the dune field is grown on a tile from its own start
  fields, so the op-entry perturbation alone never reaches it).
That reaches the ops the first protocol never touched (it moved only FluvialRun's start): the slab model of the dunes,
karst, the relaxations, the pipes, glacial, coast.

Per perturbed run, against the base:
- every level's height: RMS / relief, p99 |dh| / relief, and the main level's channel overlap;
- the judge's generic numbers of the main level;
- the growth of the difference step by step: every kernel's bound images read back after its 1st, 10th, 100th,
  1,000th and 10,000th dispatch, compared with the base run's at the same dispatch;
- the dispatch log: every core/gpu.run (the op, the kernel, its uniforms, the bound images' names and sizes), and
  whether the perturbed run issues the same kernel sequence with the same uniforms as the base, and where it first
  differs.

The Blender edition is found at blender/ beside eidoverse/ in this checkout, else at $EIDO_BLENDER_EDITION.
"""
import functools
import gzip
import hashlib
import json
import os
import struct
import sys
import time
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))


def blender_edition():
    for root in (os.path.normpath(os.path.join(HERE, '..', '..', '..', '..')), os.environ.get('EIDO_BLENDER_EDITION', '')):
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return root
    sys.exit('blender_floor_patterns: no Blender edition here or at $EIDO_BLENDER_EDITION')


sys.path.insert(0, os.path.join(blender_edition(), 'blender'))
import numpy as np  # noqa: E402

from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain import run as RUN  # noqa: E402
from eidoblend.terrain.core import gpu as G  # noqa: E402
from eidoblend.terrain.core import metrics as M  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
while args and args[0] == '--':                  # run_blender.sh passes its own '--' before the script's arguments
    args = args[1:]
OUT, NPAT = args[0], int(args[1])
RECIPES = args[2:] or ['dunes']
SNAP_AT = (1, 10, 100, 1000, 10000)
KEYS = ('relief_m', 'hypsometric_integral', 'slope_p10', 'slope_p50', 'slope_p90', 'slope_p99', 'frac_slope_lt5',
        'spectrum_knee_m')

S = {'pattern': None, 'op': None, 'op_calls': 0, 'kernels': None, 'uhash': None, 'names': None, 'counts': None,
     'snaps': None, 'base_snaps': None, 'growth': None, 'reads': 0, 'in_snap': False, 'gz': None, 'nudged': set(),
     'in_nudges': 0}
MEMOS = ('_TILES', '_AGED_PATCHES', '_PLANS', '_DOMAINS', '_COLUMN_CACHE', '_CACHE')


def clear_memos():
    n = 0
    for name, mod in list(sys.modules.items()):
        if name.startswith('eidoblend.terrain'):
            for m in MEMOS:
                d = getattr(mod, m, None)
                if isinstance(d, dict):
                    n += len(d)
                    d.clear()
    return n


_COPY = {}


def _copy_kernel(fmt):
    if fmt not in _COPY:
        _COPY[fmt] = G.kernel(source='//! sampler src\n//! image dst ' + fmt.lower() + '\nvoid main() {\n'
                              '  ivec2 p = ivec2(gl_GlobalInvocationID.xy);\n  ivec2 n = textureSize(src, 0);\n'
                              '  if (!inside(p, n)) return;\n  imageStore(dst, p, texelFetch(src, p, 0));\n}\n',
                              name=f'probe_copy_{fmt.lower()}')
    return _COPY[fmt]

# ------------------------------------------------------------------------------------- op-entry perturbation ---
_orig_get_op = RUN.get_op


def _nudge(a, rng):
    r = rng.random(a.shape)
    up, dn = r < 0.25, r >= 0.75
    return np.where(up, np.nextafter(a, np.float32(np.inf)),
                    np.where(dn, np.nextafter(a, np.float32(-np.inf)), a)).astype(np.float32)


def _get_op(name):
    fn = _orig_get_op(name)

    @functools.wraps(fn)
    def wrapped(fields, level, params, seed, *a, **k):
        S['op'] = name
        if S['pattern'] is not None:
            rng = np.random.default_rng([S['pattern'], S['op_calls']])
            for key in sorted(fields.keys()):
                v = fields[key]
                if isinstance(v, np.ndarray) and v.dtype == np.float32 and v.ndim == 2:
                    fields[key] = _nudge(v, rng)
        S['op_calls'] += 1
        try:
            return fn(fields, level, params, seed, *a, **k)
        finally:
            S['op'] = '<runner>'
    return wrapped


RUN.get_op = _get_op

# ------------------------------------------------------------------------------------------- dispatch log ---
_orig_run, _orig_read = G.run, G.read


def _read(tex):
    if not S['in_snap']:
        S['reads'] += 1
    return _orig_read(tex)


def _plain(v):
    if isinstance(v, (list, tuple, np.ndarray)):
        return [float(x) for x in np.ravel(v)]
    return float(v)


def _run(kernel, groups=None, samplers=None, images=None, uniforms=None):
    _orig_run(kernel, groups, samplers, images, uniforms)
    if S['kernels'] is None:
        return
    name = kernel if isinstance(kernel, str) else kernel.name
    if name == '_self_test':                         # the device's check at first use: once per process, not the run's
        return
    call = S['op_calls'] - 1
    if S['pattern'] is not None and S['op'] not in (None, '<runner>') and (call, name) not in S['nudged'] and images:
        S['nudged'].add((call, name))               # inside an op call: this kernel's outputs, once, after its first run
        if name not in S['names']:
            S['names'].append(name)
        rng = np.random.default_rng([S['pattern'], call, S['names'].index(name), 1])
        S['in_snap'] = True
        for n in sorted(images):
            t = images[n]
            a = _nudge(_orig_read(t), rng)
            _orig_run(_copy_kernel(str(t.format)), None, samplers={'src': G.texture(a)}, images={'dst': t},
                      uniforms={})
            S['in_nudges'] += 1
        S['in_snap'] = False
    u = sorted((k, _plain(v)) for k, v in (uniforms or {}).items())
    ims = sorted((n, int(t.height), int(t.width), str(t.format)) for n, t in (images or {}).items())
    if name not in S['names']:
        S['names'].append(name)
    S['kernels'].append(S['names'].index(name))
    S['uhash'].append(struct.unpack('<Q', hashlib.sha1(json.dumps([name, u]).encode()).digest()[:8])[0])
    if S['gz'] is not None:
        S['gz'].write((json.dumps([S['op'], name, u, ims, sorted((samplers or {}).keys())]) + '\n').encode())
    c = S['counts'][name] = S['counts'].get(name, 0) + 1
    if c in SNAP_AT and images:
        S['in_snap'] = True
        snap = {n: _orig_read(t) for n, t in images.items()}
        S['in_snap'] = False
        key = f'{name}#{c}'
        if S['pattern'] is None:                       # the base run records; a perturbed run only compares
            S['base_snaps'][key] = snap
        elif key in S['base_snaps']:
            worst = 0.0
            for n, a in snap.items():
                b = S['base_snaps'][key].get(n)
                if b is None or b.shape != a.shape:
                    continue
                for ch in range(b.shape[2]):
                    rng_ = float(np.ptp(b[:, :, ch])) or 1.0
                    d = a[:, :, ch].astype(np.float64) - b[:, :, ch]
                    worst = max(worst, float(np.sqrt(np.mean(d * d))) / rng_)
            S['growth'].setdefault(name, {})[str(c)] = worst


G.run, G.read = _run, _read


def gen(recipe, log_path=None):
    S['memos_cleared'] = clear_memos()
    S.update(op=None, op_calls=0, kernels=array('H'), uhash=array('Q'), names=S['names'] or [], counts={}, reads=0,
             nudged=set(), in_nudges=0)
    S['gz'] = gzip.open(log_path, 'wb') if log_path else None
    t0 = time.perf_counter()
    t = A.generate(recipe, seed=1, quality='draft', cache=False, log=lambda m: None)
    s = time.perf_counter() - t0
    if S['gz'] is not None:
        S['gz'].close()
        S['gz'] = None
    return t, s


def channels(f, cell):
    if 'A' not in f:
        return None
    return np.asarray(f['A'], np.float64) > max(1e6, 400 * cell * cell)


def level_fields(t):
    out = []
    for i, lv in enumerate(t.levels):
        try:
            f = t.fields(i)
        except Exception:  # noqa: BLE001 - an older Terrain.fields takes a role only
            f = t.fields(lv.role) if hasattr(lv, 'role') else None
        out.append((str(lv), lv.cell, f))
    return out


res = {'protocol': 'every op: every float field +-1 ulp on half the cells at op entry; draft, seed 1',
       'snap_at': SNAP_AT, 'numpy': np.__version__, 'recipes': {}}
outdir = os.path.dirname(os.path.abspath(OUT))
for recipe in RECIPES:
    S['names'] = []
    S['pattern'], S['base_snaps'], S['growth'] = None, {}, None
    log_path = os.path.join(outdir, f'dispatch_log_{recipe}.jsonl.gz')
    t0, s0 = gen(recipe, log_path)
    base_k, base_u, base_counts, base_reads = S['kernels'], S['uhash'], dict(S['counts']), S['reads']
    lv0 = level_fields(t0)
    main = t0.main
    h0 = np.asarray(t0.fields('main')['h'], np.float64)
    rel = float(np.ptp(h0))
    m0 = M.metrics(h0, main.cell)
    c0 = channels(t0.fields('main'), main.cell)
    rr = res['recipes'][recipe] = {
        'main': str(main), 'relief_m': rel, 'base_seconds': round(s0, 1), 'dispatches': len(base_k),
        'kernels': {k: base_counts[k] for k in sorted(base_counts, key=lambda k: -base_counts[k])},
        'readbacks': base_reads, 'op_calls': S['op_calls'],
        'dispatch_log_gz_bytes': os.path.getsize(log_path), 'patterns': {}}
    print(recipe, 'base', json.dumps({k: rr[k] for k in ('base_seconds', 'dispatches', 'readbacks', 'op_calls',
                                                          'dispatch_log_gz_bytes')}), flush=True)
    for p in range(1, NPAT + 1):
        S['pattern'], S['growth'] = p, {}
        t, s = gen(recipe)
        S['pattern'] = None
        k, u = S['kernels'], S['uhash']
        n = min(len(k), len(base_k))
        first_k = next((i for i in range(n) if k[i] != base_k[i]), None if len(k) == len(base_k) else n)
        ud = [i for i in range(n) if u[i] != base_u[i]]
        levels = []
        for (name, cell, fb), (_, _, fp) in zip(lv0, level_fields(t)):
            if fb is None or fp is None or 'h' not in fb:
                continue
            hb, hp = np.asarray(fb['h'], np.float64), np.asarray(fp['h'], np.float64)
            r = float(np.ptp(hb)) or 1.0
            d = hp - hb
            levels.append({'level': name, 'rms_over_relief': float(np.sqrt(np.mean(d * d)) / r),
                           'p99_abs_over_relief': float(np.percentile(np.abs(d), 99) / r)})
        h = np.asarray(t.fields('main')['h'], np.float64)
        d = h - h0
        c = channels(t.fields('main'), main.cell)
        ov = None
        if c is not None and c0 is not None:
            inter, union = int((c0 & c).sum()), int((c0 | c).sum())
            ov = inter / union if union else 1.0
        m = M.metrics(h, main.cell)
        pr = rr['patterns'][str(p)] = {
            'seconds': round(s, 1), 'perturbed_op_calls': S['op_calls'], 'in_op_nudges': S['in_nudges'],
            'memo_entries_cleared_before': S['memos_cleared'],
            'rms_over_relief': float(np.sqrt(np.mean(d * d)) / rel),
            'p99_abs_over_relief': float(np.percentile(np.abs(d), 99) / rel), 'channel_overlap': ov,
            'levels': levels, 'metrics': {kk: [m0.get(kk), m.get(kk)] for kk in KEYS},
            'dispatches': len(k), 'same_kernel_sequence': first_k is None, 'first_kernel_difference': first_k,
            'dispatches_with_other_uniforms': len(ud),
            'first_uniform_difference': ({'index': ud[0], 'kernel': S['names'][base_k[ud[0]]]} if ud else None),
            'growth_rms_over_range': S['growth']}
        print(recipe, 'pattern', p, json.dumps({kk: pr[kk] for kk in ('seconds', 'rms_over_relief', 'p99_abs_over_relief',
              'channel_overlap', 'same_kernel_sequence', 'dispatches_with_other_uniforms')}), flush=True)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=1, default=float)
    S['base_snaps'] = None
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(res, f, indent=1, default=float)
print('RESULT', json.dumps(res, default=float)[:4000], flush=True)
