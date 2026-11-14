"""Fixtures made by the Blender edition's own code, for the port's packages to check their kernels, their GPU
replacements of numpy code, their plans and their recipes against (PORT_PLAN.md 5.1, 5.2). numpy only: no Blender,
no GPU.

    <Blender's python> -I eidoverse/terrain/tests/parity/fixtures.py [--kernels] [--functions] [--plans]
        [--recipes] [--only fluvial,hydro,...] [--out <dir>]            (no flag: all four)

Run it with Blender's own Python (tests/_where.mjs blenderPython(): Python 3.13, numpy 2.3.4, zlib 1.3.1), never the
system's (plan C6): every manifest records the versions. The Blender edition is found as _blender.py finds it
($EIDO_BLENDER_EDITION, or blender/ in this checkout). Outputs go under $EIDO_PARITY_OUT, else
eidoverse/terrain/tests/out/parity/, keyed by the Blender commit and code hash (5.1):
    blender_<commit>_<code hash>/fixtures/<kind>/manifest.json and one little-endian .bin per distinct array
    (kinds: kernels, functions/<group>, plans, twin_probe, np_random, core_inputs)

--kernels    Every Blender kernel's numpy twin on the Blender package tests' own inputs. The parity sections of the
             Blender tests (KERNEL_TESTS: each file's test_parity(), as it is) are executed here with the GPU
             replaced by the twins, and every dispatch they make is recorded once: the kernel, its uniforms, the
             input arrays and the twin's outputs. So the cases are the Blender tests' cases (the non-square 96 x 80
             field with pins, every boundary mode, every variant), not a copy of them that could drift. Where a
             Blender test feeds one kernel's GPU output into the next case, the twin's output feeds it here (the
             recorded input is what the recorded output was computed from). Also runs
             tests/design_probes/make_twin_fixtures.py as it is into fixtures/twin_probe/ (the 46 cases, hashes
             and world noise the runner package's tests read), with the versions added to its manifest.
--functions  The Blender numpy functions that become GPU code, on recorded inputs (FUNCTION_GROUPS; `hydro`: the
             fill, flats, receivers, routing surface, routing to convergence on the twin device, lakes, the
             parent's lakes, inflow). Each case: the function, its arguments, the input arrays, every output.
--plans      Every function of the Blender terrain package that draws from numpy's Generator, called again for
             seeds 1-8 with the arguments a real run gave it: the plan calls are recorded by the floor's base runs
             (blender_chaos_floor.py, <run>/base/plans/), so this needs those runs; it says which recipes have none.
             Numpy's own draws for every call form are the runner package's (tests/core_runner/
             np_random_expected.py), run as it is into fixtures/np_random/.
--recipes    to_dict(), resolve() for the defaults and two other knob sets, describe(), and plan_levels for 20
             focus cases at each quality: the core-inputs package's generator (tests/core_inputs/
             core_inputs_expected.py), run as it is into fixtures/core_inputs/, so there is one generator.

A kernel fixture's manifest: {source, versions, key, kinds, cases: [{label, kernel, test (the Blender test file),
inline (a kernel written inline in a solver module), source_sha1, defines, uniforms {name: number | [numbers]},
uniform_types {name: 'float' | 'int' | 'vec2' | 'ivec2' ...}, inputs {sampler: {file, shape [H, W, C], dtype}},
outputs {image: {file, shape, dtype}}, channels (when the Blender test compares only some)}]}: a superset of the
design probe's manifest, so tests/core_runner/_twins.mjs reads it. Arrays are (H, W, C), row 0 south, C order.
A function fixture's case: {label, function, args, inputs {name: array}, outputs {name: array}, values}, arrays in
their natural shape, dtype one of f32 f64 i32 i64 u32 u8 (bools are u8).
"""
from __future__ import annotations

import ast
import builtins
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _blender as B  # noqa: E402

import numpy as np  # noqa: E402

# The Blender tests whose test_parity() holds a package's kernel cases (blender/tests/terrain/<file>).
KERNEL_TESTS = (
    ('fluvial', 'fluvial/test_kernels.py'),             # flow_weights, route_incise, creep, threshold_excess,
                                                        # threshold, route_area, soil_jacobi, lock_restrict,
                                                        # lock_apply, h_keep, creep_layers
    ('detail', 'detail/test_detail_gpu.py'),            # pipes_flux, pipes_water, pipes_transport, pipes_thermal,
                                                        # breakup
    ('layered_rock', 'layered_rock/test_kernels.py'),   # strata_threshold, strata_cell, strata_creep,
                                                        # strata_weather (and route_incise with a rock column)
    ('wind_sand', 'wind_sand/test_gpu.py'),             # dune_shadow, dune_activate, dune_transport, dune_avalanche
    ('glacial', 'glacial/test_gpu.py'),                 # ice_flux, jump_flood, u_carve
    ('coast', 'coast/test_coast_gpu.py'),               # coast_fetch, coast_seed, coast_jfa
)
DT = {'float32': 'f32', 'float64': 'f64', 'int32': 'i32', 'int64': 'i64', 'uint32': 'u32', 'uint8': 'u8',
      'bool': 'u8', 'int8': 'i8', 'uint16': 'u16', 'float16': 'f16'}


class Store:
    """A fixture folder: arrays written once per distinct content, the manifest at the end."""

    def __init__(self, dir, kind, key):
        self.dir = dir
        os.makedirs(dir, exist_ok=True)
        for f in os.listdir(dir):                                  # a fixture is made whole: no stale arrays
            if f.endswith('.bin') or f == 'manifest.json':
                os.remove(os.path.join(dir, f))
        self.files = {}
        self.bytes = 0
        self.manifest = dict(source='the Blender edition (blender/eidoblend/terrain), by tests/parity/fixtures.py',
                             kind=kind, key=key, versions=B.versions(), date=time.strftime('%Y-%m-%d %H:%M:%S'),
                             cases=[])

    def save(self, a, hwc=False):
        a = np.asarray(a)
        if a.dtype == np.bool_:
            a = a.astype(np.uint8)
        if hwc and a.ndim == 2:
            a = a[:, :, None]
        a = np.ascontiguousarray(a)
        dt = DT[str(a.dtype)]
        h = hashlib.sha1(a.tobytes() + repr((a.shape, dt)).encode()).hexdigest()
        name = self.files.get(h)
        if name is None:
            name = self.files[h] = f'a{len(self.files) + 1:05d}.bin'
            a.astype(a.dtype.newbyteorder('<'), copy=False).tofile(os.path.join(self.dir, name))
            self.bytes += a.nbytes
        return {'file': name, 'shape': list(a.shape), 'dtype': dt}

    def finish(self, **extra):
        self.manifest.update(extra, arrays=len(self.files), bytes=self.bytes)
        B.write_json(os.path.join(self.dir, 'manifest.json'), self.manifest)
        return self.manifest


def _num(v):
    """A uniform or argument as JSON: numbers as given (float64 repr), tuples and arrays as lists."""
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return float(v)
    if isinstance(v, (list, tuple, np.ndarray)):
        return [_num(x) for x in np.ravel(np.asarray(v)).tolist()]
    return v


# ---------------------------------------------------------------------------------------------------- kernels ---

class KernelRecorder:
    """Every twin dispatch the Blender tests make, once each."""

    def __init__(self, store):
        self.store = store
        self.seen = {}
        self.pending = []
        self.test = None
        self.counts = {}

    def case(self, name, spec, samplers, uniforms, outputs, inline_source=None, defines=None, channels=None):
        ins = {n: self.store.save(np.asarray(a, np.float32), hwc=True) for n, a in samplers.items()}
        outs = {n: self.store.save(np.asarray(a, np.float32), hwc=True) for n, a in outputs.items()}
        u = {n: _num(v) for n, v in sorted(uniforms.items())}
        sha = hashlib.sha1(inline_source.encode('utf-8')).hexdigest() if inline_source is not None else None
        ident = json.dumps([name, sha, sorted((str(k), str(v)) for k, v in (defines or {}).items()), u,
                            {n: v['file'] for n, v in sorted(ins.items())}], sort_keys=True)
        if ident in self.seen:
            c = self.seen[ident]
        else:
            n = self.counts[name] = self.counts.get(name, 0) + 1
            c = dict(label=f'{name} #{n}', kernel=name, test=self.test, inline=inline_source is not None,
                     source_sha1=sha, defines={str(k): str(v) for k, v in (defines or {}).items()} or None,
                     uniforms=u, uniform_types=dict(spec.uniforms), inputs=ins, outputs=outs,
                     images={n: fmt for n, fmt in spec.images.items()})
            self.seen[ident] = c
            self.store.manifest['cases'].append(c)
        if channels is not None:
            c['channels'] = {n: [int(x) for x in v] for n, v in channels.items()}
        self.pending.append(c)
        return c

    def label(self, text):
        """The Blender test's own name for the cases since its last check() (its first naming stays)."""
        for c in self.pending:
            if c['label'].startswith(c['kernel'] + ' #'):
                c['label'] = f'{text} [{c["kernel"]}]' if len(self.pending) > 1 else str(text)
        self.pending = []


def install_twin_gpu(rec):
    """Replace the Blender package's GPU with its twins, recording every dispatch: core/gpu's texture, empty, like,
    read, sync, kernel, run and init; twins.parity; solvers/fluvial.device (both 'gpu' and 'twin'). Nothing of the
    Blender edition is changed on disk; the replacements live in this process."""
    from eidoblend.terrain.core import gpu as G
    from eidoblend.terrain.core import twins as T
    from eidoblend.terrain.solvers import fluvial as FL

    Tex = FL._Tex

    def texture(arr, fmt=None):
        a = G._as_hwc(arr)
        return Tex(a, fmt or G._CHANNEL_FMT[a.shape[2]])

    def empty(shape, channels=4, fmt=None):
        fmt = fmt or G._CHANNEL_FMT[channels]
        return Tex(np.zeros((int(shape[0]), int(shape[1]), G._FMT_CHANNELS[fmt]), np.float32), fmt)

    def like(tex):
        return empty((tex.height, tex.width), fmt=tex.format)

    def read(tex):
        return np.array(tex.a, dtype=np.float32, copy=True)

    kernels = {}

    def kernel(name=None, path=None, source=None, defines=None, common=True):
        kname, full, spec = G.load_source(name, path, source, common)
        defs = sorted((str(k), str(v)) for k, v in (defines or {}).items())
        key = hashlib.sha1((full + '\0' + repr(defs)).encode('utf-8')).hexdigest()
        if key not in kernels:
            k = G.Kernel(kname, spec, None, 0.0, key)
            k.parity_source = source
            k.parity_defines = dict(defines or {})
            kernels[key] = k
        return kernels[key]

    def run(kern, groups=None, samplers=None, images=None, uniforms=None):
        k = kernel(kern) if isinstance(kern, str) else kern
        spec = k.spec
        samplers, images, uniforms = samplers or {}, images or {}, uniforms or {}
        for given, declared, what in ((samplers, spec.samplers, 'sampler'), (images, spec.images, 'image'),
                                      (uniforms, spec.uniforms, 'uniform')):
            if set(given) != set(declared):
                raise KeyError(f'kernel {k.name!r}: {what}s given {sorted(given)}, declared {sorted(declared)}')
        s = {n: t.a for n, t in samplers.items()}
        out = T.get_twin(k.name)(s, T._prep_uniforms(uniforms, spec))
        res = {}
        for n, t in images.items():
            a = np.asarray(out[n], np.float32)
            a = a[:, :, None] if a.ndim == 2 else a
            if a.shape != t.a.shape:
                raise ValueError(f'twin of {k.name!r}: image {n!r} is {a.shape}, its texture {t.a.shape}')
            t.a = np.ascontiguousarray(a)
            res[n] = t.a
        rec.case(k.name, spec, s, uniforms, res, getattr(k, 'parity_source', None), getattr(k, 'parity_defines', None))

    def parity(kern, inputs, uniforms, twin=None, tol=1e-4, channels=None, defines=None):
        if isinstance(kern, G.Kernel):
            k = kern
        elif isinstance(kern, str) and kern.endswith('.glsl'):
            k = kernel(path=kern, defines=defines)
        else:
            k = kernel(kern, defines=defines)
        fn = twin or T.get_twin(k.name)
        s = T._prep_inputs(inputs, k.spec)
        u = T._prep_uniforms(uniforms, k.spec)
        want = T.run_twin(fn, s, u, spec=k.spec)
        rec.case(k.name, k.spec, s, uniforms, want, getattr(k, 'parity_source', None),
                 getattr(k, 'parity_defines', None) or defines, channels)
        shape = next(iter(s.values())).shape[:2]
        return {'ok': True, 'worst': 0.0, 'tol': tol, 'channels': [], 'kernel': k.name,
                'shape': [int(shape[0]), int(shape[1])], 'gpu_ms': 0.0, 'twin_only': True}

    class RecDevice(FL.TwinDevice):
        """solvers/fluvial's twin device, recording."""
        name = 'gpu'

        def kernel(self, kern):                                    # GPUDevice's, for callers that compile first
            return kern

        def run(self, kern, samplers, images, uniforms):
            spec = self._spec(kern)
            name = kern.name if isinstance(kern, FL.Inline) else kern
            s = {n: t.a for n, t in samplers.items()}
            FL.TwinDevice.run(self, kern, samplers, images, uniforms)
            rec.case(name, spec, s, uniforms, {n: t.a for n, t in images.items()},
                     kern.source if isinstance(kern, FL.Inline) else None)

    dev = RecDevice()
    G.init = lambda: {'backend': 'numpy twins (tests/parity/fixtures.py)', 'device': 'none', 'vendor': 'none'}
    G.texture, G.empty, G.like, G.read, G.kernel, G.run = texture, empty, like, read, kernel, run
    G.sync = lambda tex: None
    T.parity = parity
    FL.device = lambda kind=None: dev
    FL._DEVICES['gpu'] = FL._DEVICES['twin'] = dev
    return G, T, FL


def _definitions(path):
    """A Blender test file's code without the call that runs it (`main()` at module level, an `if __name__` block)."""
    with open(path, encoding='utf-8') as f:
        tree = ast.parse(f.read(), path)
    body = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and \
                getattr(node.value.func, 'id', None) == 'main':
            continue
        if isinstance(node, ast.If) and '__name__' in ast.dump(node.test):
            continue
        body.append(node)
    tree.body = body
    return compile(tree, path, 'exec')


def kernel_fixtures(root_out, key, only=None):
    edition = B.bare_terrain_package()
    tests = os.path.join(edition, 'blender', 'tests', 'terrain')
    store = Store(os.path.join(root_out, 'kernels'), 'kernels', key)
    rec = KernelRecorder(store)
    install_twin_gpu(rec)
    real_makedirs, real_open = os.makedirs, builtins.open
    inside = os.path.normcase(os.path.abspath(edition)) + os.sep

    def makedirs(p, *a, **k):                    # the Blender edition is read-only to the port: its tests' output
        if os.path.normcase(os.path.abspath(p)).startswith(inside):       # folders are not made from here
            return None
        return real_makedirs(p, *a, **k)

    def guarded_open(file, mode='r', *a, **k):
        if isinstance(file, (str, os.PathLike)) and any(c in mode for c in 'wax+') and \
                os.path.normcase(os.path.abspath(file)).startswith(inside):
            raise PermissionError(f'parity fixtures: a Blender test tried to write {file} (the Blender edition is '
                                  f'read-only here)')
        return real_open(file, mode, *a, **k)

    sources = []
    for pkg, rel in KERNEL_TESTS:
        if only and pkg not in only:
            continue
        path = os.path.join(tests, *rel.split('/'))
        ent = dict(package=pkg, test=rel)
        n0 = len(store.manifest['cases'])
        rec.test, rec.pending = rel, []
        t0 = time.perf_counter()
        os.makedirs, builtins.open = makedirs, guarded_open
        try:
            ns = {'__name__': f'parity_fixture_{pkg}', '__file__': path}
            exec(_definitions(path), ns)
            ns['check'] = lambda name, cond=True, detail=None: rec.label(name)
            ns['test_parity']()
        except Exception as e:                                       # noqa: BLE001 - recorded; the others still run
            ent['error'] = f'{type(e).__name__}: {e}'
            ent['traceback'] = traceback.format_exc()[-1500:]
        finally:
            os.makedirs, builtins.open = real_makedirs, real_open
        rec.label(f'{pkg} (after its last check)')
        new = store.manifest['cases'][n0:]
        ent.update(cases=len(new), kernels=sorted({c['kernel'] for c in new}),
                   seconds=round(time.perf_counter() - t0, 2))
        sources.append(ent)
        print(f"[fixtures] kernels: {rel}: {len(new)} cases of {', '.join(ent['kernels']) or 'no kernel'}"
              + (f"  ERROR {ent['error']}" if 'error' in ent else ''), flush=True)
    kernels = {}
    for c in store.manifest['cases']:
        kernels[c['kernel']] = kernels.get(c['kernel'], 0) + 1
    man = store.finish(sources=sources, kernels=kernels)
    print(f"[fixtures] kernels: {len(man['cases'])} cases of {len(kernels)} kernels, {man['arrays']} arrays "
          f"({man['bytes'] / 1e6:.1f} MB) -> {store.dir}", flush=True)
    return man


def _run_script(script, out_dir, extra_manifest):
    """Another package's fixture maker, run as it is with this Python (-I) into out_dir; the versions and this
    tool's key go into its manifest."""
    os.makedirs(out_dir, exist_ok=True)
    env = dict(os.environ, EIDO_BLENDER_EDITION=B.blender_edition(), PYTHONDONTWRITEBYTECODE='1')
    r = subprocess.run([sys.executable, '-I', script, out_dir], env=env, capture_output=True, text=True,
                       creationflags=B.NO_WINDOW)
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    print(f"[fixtures] {os.path.relpath(script, B.TERRAIN)}: rc {r.returncode}: {' | '.join(tail)}", flush=True)
    mp = os.path.join(out_dir, 'manifest.json')
    man = B.read_json(mp)
    if r.returncode == 0 and isinstance(man, dict):
        man.update(extra_manifest, made_by=os.path.relpath(script, B.TERRAIN).replace('\\', '/'),
                   versions=B.versions())
        B.write_json(mp, man)
    return r.returncode == 0


# -------------------------------------------------------------------------------------------------- functions ---

class FunctionRecorder:
    def __init__(self, store, group):
        self.store, self.group = store, group

    def case(self, label, function, args, inputs, outputs, values=None):
        c = dict(label=label, group=self.group, function=function, args=B.jsonable(args),
                 inputs={n: self.store.save(a) for n, a in inputs.items() if a is not None},
                 outputs={n: self.store.save(a) for n, a in outputs.items() if a is not None},
                 values=B.jsonable(values) if values is not None else None)
        self.store.manifest['cases'].append(c)
        return c


def _hydro_fields():
    """The fields the hydrology cases run on: the fluvial tests' own 96 x 80 field with its sunk pits (every 7th cell
    5 m lower: closed basins), the same terraced to 8 m steps (flats and ties everywhere), a basin field (two bowls
    deeper than any lake threshold, one reaching the border band), and, when the reference DEMs are fetched, a
    192 x 160 window of Crater Lake's rim and lake (a real closed basin with a dead-flat floor)."""
    from eidoblend.terrain.core import twins as T
    shape = (80, 96)
    h = T.random_field(shape, 0.0, 400.0, 1, smooth=1)
    pits = h.copy()
    pits[3::7, 3::7] -= 5.0
    terr = (np.round(pits.astype(np.float64) / 8.0) * 8.0).astype(np.float32)
    jj, ii = np.mgrid[0:shape[0], 0:shape[1]]
    bowls = (0.35 * h + 120.0
             - 90.0 * np.exp(-(((ii - 30) / 11.0) ** 2 + ((jj - 44) / 9.0) ** 2))
             - 60.0 * np.exp(-(((ii - 84) / 9.0) ** 2 + ((jj - 20) / 8.0) ** 2))).astype(np.float32)
    fields = [('pits', pits, 10.0), ('terraces', terr, 10.0), ('bowls', bowls, 10.0)]
    try:
        from judge import refs
        r = refs.load('crater_lake')
        n = r.h.shape[0]
        st = max(1, n // 192)                        # every st-th pixel: the whole tile's width, 160 rows about its
        j0 = (n - 160 * st) // 2                     # middle (the rim, the lake and the flanks)
        win = np.asarray(r.h, np.float64)[j0:j0 + 160 * st:st, 0:192 * st:st]
        if win.shape == (160, 192):
            fields.append(('crater_lake', win.astype(np.float32), float(r.pixel) * st))
    except Exception as e:                                           # noqa: BLE001 - the DEMs are optional data
        print(f'[fixtures] functions: no reference DEM window ({type(e).__name__}: {e}): synthetic fields only',
              flush=True)
    return fields


def hydro_functions(rec):
    """solvers/hydro.py and the receivers it reads from solvers/fluvial.py (module doc)."""
    from eidoblend.terrain.core import levels as L
    from eidoblend.terrain.core import twins as T
    from eidoblend.terrain.solvers import fluvial as FL
    from eidoblend.terrain.solvers import hydro as HY
    dev = FL.TwinDevice()
    for fname, h, cell in _hydro_fields():
        ny, nx = h.shape
        seas = [None, float(np.percentile(h, 12))]
        wraps = [(False, False)] + ([(True, True), (True, False)] if fname != 'crater_lake' else [])
        for wrap in wraps:
            for sea in seas:
                tag = f"{fname} wrap={int(wrap[0])}{int(wrap[1])} sea={'none' if sea is None else f'{sea:.3f}'}"
                a = dict(wrap=list(wrap), sea_level=sea)
                filled, info = HY.fill_depressions(h, wrap, sea)
                rec.case(f'fill_depressions {tag}', 'solvers.hydro.fill_depressions', a, {'height': h},
                         {'filled': filled, 'filled_f32': filled.astype(np.float32)}, info)
                dist = HY.flat_distance(filled, wrap, sea)
                rec.case(f'flat_distance {tag}', 'solvers.hydro.flat_distance', a, {'surface': filled},
                         {'dist': dist})
                recv = HY.flow_receivers(filled, wrap, sea)
                rec.case(f'flow_receivers {tag}', 'solvers.hydro.flow_receivers', a, {'filled': filled},
                         {'rec': recv, 'd8': FL.d8_receivers(filled)})
                steps = HY.path_steps(recv)
                rec.case(f'path_steps {tag}', 'solvers.hydro.path_steps', {}, {'rec': recv}, {'steps': steps})
                top = float(np.max(np.abs(filled)))
                eps = max(2e-3, 4.0 * float(np.spacing(np.float32(max(top, 1.0)))))
                rs64 = HY._descend(filled, recv, eps)
                rec.case(f'_descend {tag}', 'solvers.hydro._descend', dict(eps=eps), {'filled': filled, 'rec': recv},
                         {'rs': rs64})
                rs = HY.routing_surface(filled, wrap, sea)
                rec.case(f'routing_surface {tag}', 'solvers.hydro.routing_surface', a, {'filled': filled},
                         {'surface': rs, 'surface_f64': rs64}, dict(eps=eps))
                if wrap == (False, False) or sea is None:
                    for method in ('d8', 'dinf', 'mfd'):
                        r8, wgt, term = HY.route(filled, wrap, sea, method)
                        acc = HY.accumulate(r8, wgt, term)
                        rec.case(f'route {method} {tag}', 'solvers.hydro.route', dict(a, method=method, exponent=1.1),
                                 {'filled': filled}, {'recv': r8, 'wgt': wgt, 'terminal': term})
                        rec.case(f'accumulate {method} {tag}', 'solvers.hydro.accumulate', {},
                                 {'recv': r8, 'wgt': wgt, 'terminal': term}, {'acc': acc})
                if wrap == (False, False):
                    bound = T.BOUND_OPEN
                    for label, A0, A_in in (('from one cell', None, None),
                                            ('from A0 with inflow', T.random_field((ny, nx), cell * cell, 4e4, 5),
                                             np.where(T.random_field((ny, nx), 0, 1, 6) > 0.985, 3e5, 0.0)
                                             .astype(np.float32) * T.on_edge((ny, nx)))):
                        A, iters = HY.route_to_convergence(dev, rs, cell, A0=A0, A_in=A_in, bound=bound)
                        rec.case(f'route_to_convergence {label} {tag}', 'solvers.hydro.route_to_convergence',
                                 dict(cell=cell, bound=bound, p=1.0, tol=1e-4, check=128, max_iter=None),
                                 {'surface': rs, 'A0': A0, 'A_in': A_in}, {'A': A}, dict(iterations=int(iters)))
        # the masks' helpers that stay in this module
        rec.case(f'box_blur {fname}', 'solvers.hydro.box_blur', dict(radius=3, wrap=[False, False], passes=3),
                 {'a': h}, {'out': HY.box_blur(h, 3)})
        flat_w = (HY.flat_distance(HY.fill_depressions(h)[0]) > 0).astype(np.float64)
        rec.case(f'flat_average {fname}', 'solvers.hydro.flat_average', dict(radius=4, wrap=[False, False]),
                 {'values': h, 'flat_w': flat_w}, {'out': HY.flat_average(h, flat_w, 4)})
        rec.case(f'horizon_occlusion {fname}', 'solvers.hydro.horizon_occlusion',
                 dict(texel_m=cell, radius_m=12 * cell, wrap=[False, False], directions=16, steps=20),
                 {'heights_m': h}, {'out': HY.horizon_occlusion(h, cell, 12 * cell)})
        # lakes: every mode, the border band, a no-lake mask, the sea
        relief = float(np.ptp(h))
        thr = HY.depression_threshold(relief)
        lv = L.Level(1, 'main', -0.5 * nx * cell, -0.5 * ny * cell, nx * cell, cell, nx)
        dep0 = T.random_field((ny, nx), 0.0, 0.5, 21)
        no_lake = np.zeros((ny, nx), bool)
        no_lake[ny // 2 - 6:ny // 2 + 6, nx // 3 - 6:nx // 3 + 6] = True
        for label, kw in (('lake', dict(mode='lake')), ('sediment', dict(mode='sediment')),
                          ('lake band 16', dict(mode='lake', band=16)),
                          ('lake no_lake', dict(mode='lake', no_lake=no_lake)),
                          ('lake sea', dict(mode='lake', sea_level=float(np.percentile(h, 12)))),
                          ('lake low threshold', dict(mode='lake', threshold=0.05))):
            kw = dict(kw)
            t_m = kw.pop('threshold', thr)
            f = {'h': h.copy(), 'deposit': dep0.copy()}       # a plain dict: lakes() reads keys only, and
                                                                # a Fields refuses a non-square array
            filled, nl = HY.lakes(f, lv, t_m, **kw)
            rec.case(f'lakes {label} {fname}', 'solvers.hydro.lakes',
                     dict(threshold_m=t_m, **{k: v for k, v in kw.items() if k != 'no_lake'}),
                     {'h': h, 'deposit': dep0, 'no_lake': kw.get('no_lake')},
                     {'h': f['h'], 'deposit': f['deposit'], 'water': f['water'], 'filled': filled},
                     dict(nlakes=int(nl), relief=relief))
    # a parent and its child: the parent's lakes kept on the child, and the inflow across the child's window edge
    from eidoblend.terrain.core import grid
    hp = dict((n, f) for n, f, _c in _hydro_fields())['bowls']
    ph = np.zeros((96, 96), np.float32)
    ph[8:88, :] = hp
    ph[:8, :] = hp[:1, :] + 3.0
    ph[88:, :] = hp[-1:, :] + 3.0
    pcell = 20.0
    plv = L.Level(0, 'context', -960.0, -960.0, 96 * pcell, pcell, 96)
    pf = {'h': ph.copy()}
    HY.lakes(pf, plv, HY.depression_threshold(float(np.ptp(ph))), 'lake')
    pfilled = HY.fill_depressions(pf['h'])[0]
    prs = HY.routing_surface(pfilled)
    pA, _it = HY.route_to_convergence(dev, prs, pcell)
    pf['A'] = pA
    pf['qs'] = (pA * 1e-4).astype(np.float32)
    for label, (i0, j0, m) in (('centred', (24, 24, 48)), ('at the lake', (14, 28, 40)), ('corner', (2, 2, 32))):
        clv = L.Level(1, 'main', plv.x0 + i0 * pcell, plv.y0 + j0 * pcell, m * pcell, pcell / 2, 2 * m, parent=0)
        ch = grid.crop_upsample2(pf['h'], i0, j0, m) if hasattr(grid, 'crop_upsample2') else None
        if ch is None:
            continue
        ch = np.asarray(ch, np.float32)
        water = HY._parent_lake_water(clv, np.asarray(ch, np.float64), plv, pf)
        win = dict(i0=i0, j0=j0, m=m, parent=plv.to_dict(), child=clv.to_dict())
        rec.case(f'_parent_lake_water {label}', 'solvers.hydro._parent_lake_water', win,
                 {'h': ch, 'parent_h': pf['h'], 'parent_water': pf['water']}, {'water': water})
        for p in (1.0, 1.3):
            A_in, qs_in = HY.inflow(plv, pf, clv, p=p, surface=prs)
            rec.case(f'inflow p={p:g} {label}', 'solvers.hydro.inflow', dict(win, p=p),
                     {'parent_surface': prs, 'parent_A': pf['A'], 'parent_qs': pf['qs']},
                     {'A_in': A_in, 'qs_in': qs_in})
        A_in, qs_in = HY.inflow(plv, pf, clv)
        rec.case(f'inflow default surface {label}', 'solvers.hydro.inflow', dict(win, p=1.0, surface=None),
                 {'parent_h': pf['h'], 'parent_A': pf['A'], 'parent_qs': pf['qs']},
                 {'A_in': A_in, 'qs_in': qs_in})
        f = {'h': ch.copy()}
        filled, nl = HY.lakes(f, clv, HY.depression_threshold(float(np.ptp(ph))), 'lake', parent=(plv, pf), band=16)
        rec.case(f'lakes with parent {label}', 'solvers.hydro.lakes',
                 dict(win, threshold_m=HY.depression_threshold(float(np.ptp(ph))), mode='lake', band=16),
                 {'h': ch, 'parent_h': pf['h'], 'parent_water': pf['water']},
                 {'h': f['h'], 'water': f['water'], 'deposit': f['deposit'] if 'deposit' in f else None,
                  'filled': filled}, dict(nlakes=int(nl)))


METRIC_DEMS = ('lauterbrunnen', 'mount_fuji', 'crater_lake', 'namib_star_dunes', 'palouse_hills')
ULPS = 16          # the float32 rounding a slope can carry (differences, a division, a square root, an arctangent)


def _near(a, limit, ulps=ULPS):
    """How many values of `a` lie within `ulps` float32 steps of `limit`: the cells a float32 evaluation may count on
    the other side of it (the count's tolerance, measured, never guessed)."""
    band = ulps * float(np.spacing(np.float32(abs(limit) if limit else 1e-30)))
    return int(np.count_nonzero(np.abs(np.asarray(a, np.float64) - limit) <= band))


def metrics_functions(rec):
    """core/metrics.py on reference DEMs, as float32 fields (what the port holds): every number of metrics(),
    slope_stats, depressions, radial_spectrum, spectrum_summary, aspect_harmonics, cliff_pairs, and for every count
    against a limit the number of cells within a float32 rounding of that limit."""
    import math
    from judge import refs
    from eidoblend.terrain.core import grid
    from eidoblend.terrain.core import metrics as M
    from eidoblend.terrain.core import twins as T
    fields = []
    for name in METRIC_DEMS:
        r = refs.load(name)
        fields.append((name, np.asarray(r.h, np.float64).astype(np.float32), float(r.pixel)))
    fields.append(('synthetic_96x80', T.random_field((80, 96), 0.0, 400.0, 1, smooth=1), 10.0))   # not square
    for name, h32, cell in fields:
        h = h32.astype(np.float64)
        m = M.metrics(h, cell)
        s = grid.slope_deg(h, cell)
        gx, gy = grid.gradient(h, cell)
        g = np.hypot(gx, gy)
        relief = float(h.max() - h.min())
        frac, count, thr, depth = M.depressions(h, cell, relief)
        lab, nlab = M.label(depth > 1e-6)
        maxd = np.zeros(nlab + 1)
        if nlab:
            np.maximum.at(maxd, lab.ravel(), depth.ravel())
        at_thr = np.abs(maxd[1:] - thr) <= ULPS * float(np.spacing(np.float32(thr)))
        sizes = np.bincount(lab.ravel(), minlength=nlab + 1)
        wl, P = M.radial_spectrum(h, cell)
        summ = M.spectrum_summary(wl, P, cell, min(h.shape) * cell)
        harm = M.aspect_harmonics(h, cell)
        t80 = math.tan(math.radians(80.0))
        pair_near = 0
        for dj, di in M.PAIR_DIRS:
            sa, sb = M.pair_slices(dj, di, h.shape)
            pair_near += _near(np.abs(h[sa] - h[sb]) / (math.hypot(dj, di) * cell), t80)
        t10 = math.tan(math.radians(10.0))
        sel = g > t10
        values = dict(
            cell=cell, metrics=m, slope_stats=M.slope_stats(h, cell),
            depressions=dict(frac=frac, count=count, thr=thr, labels=nlab,
                             labels_within_rounding_of_threshold=int(at_thr.sum()),
                             their_cells=int(sizes[1:][at_thr].sum()),
                             depth_cells_within_rounding_of_1e_6=_near(depth, 1e-6)),
            spectrum_summary=list(summ), aspect_harmonics={str(k): v for k, v in harm.items()},
            aspect=dict(selected=int(sel.sum()), sum_w=float(g[sel].sum()),
                        cells_within_rounding_of_min_slope=_near(g, t10)),
            cliff_pairs=dict(frac=M.cliff_pairs(h, cell), pairs_within_rounding_of_limit=pair_near),
            slope_cells_within_rounding={str(k): _near(s, k) for k in (5, 30, 40, 50)},
            slope_percentiles_of_float32_slopes=[float(v) for v in np.percentile(
                s.astype(np.float32).astype(np.float64), [10, 50, 90, 99])],
            ulps=ULPS)
        rec.case(f'metrics {name}', 'core.metrics.metrics', dict(cell=cell), {'h': h32},
                 {'spectrum_wavelength_m': wl, 'spectrum_power': P, 'slope_deg': s.astype(np.float32),
                  'depth': depth.astype(np.float32)}, values)


FUNCTION_GROUPS = {'hydro': hydro_functions, 'metrics': metrics_functions}


def function_fixtures(root_out, key, only=None):
    """One folder per group (functions/<group>/), so a package makes its own group again without the others'."""
    B.bare_terrain_package()
    groups = []
    for name, fn in FUNCTION_GROUPS.items():
        if only and name not in only:
            continue
        store = Store(os.path.join(root_out, 'functions', name), 'functions', key)
        ent = dict(group=name)
        t0 = time.perf_counter()
        try:
            fn(FunctionRecorder(store, name))
        except Exception as e:                                       # noqa: BLE001 - recorded; the others still run
            ent['error'] = f'{type(e).__name__}: {e}'
            ent['traceback'] = traceback.format_exc()[-1500:]
        ent.update(cases=len(store.manifest['cases']),
                   functions=sorted({c['function'] for c in store.manifest['cases']}),
                   seconds=round(time.perf_counter() - t0, 2))
        man = store.finish(group=ent)
        groups.append(ent)
        print(f"[fixtures] functions: {name}: {ent['cases']} cases of {len(ent['functions'])} functions, "
              f"{man['arrays']} arrays ({man['bytes'] / 1e6:.1f} MB) -> {store.dir}"
              + (f"  ERROR {ent['error']}" if 'error' in ent else ''), flush=True)
    return dict(groups=groups)


# ------------------------------------------------------------------------------------------------------ plans ---

PLAN_SEEDS = (1, 2, 3, 4, 5, 6, 7, 8)


def plan_fixtures(root_out, key, only=None):
    """Every recorded plan call (the floor's base runs: <recipe>_s<seed>_draft/base/plans/calls.pkl) made again for
    seeds 1-8 (module doc). The seed is the call's `seed` argument; a call without one is recorded as it was."""
    import pickle
    import _hooks as H
    B.bare_terrain_package()
    store = Store(os.path.join(root_out, 'plans'), 'plans', key)
    root = os.path.dirname(root_out)
    have, missing = [], []
    for name in sorted(os.listdir(root)):
        pk = os.path.join(root, name, 'base', 'plans', 'calls.pkl')
        if '_s1_' not in name:
            continue
        recipe = name.rsplit('_s', 1)[0]
        if only and recipe not in only:
            continue
        if not os.path.exists(pk):
            missing.append(recipe)
            continue
        with open(pk, 'rb') as f:
            calls = pickle.load(f)
        n0 = len(store.manifest['cases'])
        for i, c in enumerate(calls):
            fn, owner = H.resolve_plan_function(c['module'], c['qualname'])
            if fn is None:
                store.manifest['cases'].append(dict(recipe=recipe, function=f"{c['module']}.{c['qualname']}",
                                                    error='the function is gone from the module'))
                continue
            seeds = PLAN_SEEDS if c.get('seed_arg') else (None,)
            for s in seeds:
                args, kwargs = H.plan_call_args(c, s)
                in_arrays, arrays = {}, {}
                call_json = B.jsonable(dict(args=list(args[1:] if c.get('init') else args), kwargs=kwargs),
                                       in_arrays, 'call', 256)
                try:
                    H.clear_memos()
                    out = owner(*args[1:], **kwargs) if c.get('init') else fn(*args, **kwargs)
                    result = B.jsonable(out, arrays, 'result', 256)
                    err = None
                except Exception as e:                               # noqa: BLE001 - recorded
                    result, err = None, f'{type(e).__name__}: {e}'
                store.manifest['cases'].append(dict(
                    label=f"{recipe} {c['qualname']} #{i} seed {s if s is not None else 'as run'}", recipe=recipe,
                    function=f"{c['module']}.{c['qualname']}", op=c.get('op'), level=c.get('level'), seed=s,
                    call=call_json, inputs={n: store.save(a) for n, a in in_arrays.items()}, result=result,
                    outputs={n: store.save(a) for n, a in arrays.items()}, error=err))
        have.append(dict(recipe=recipe, calls=len(calls), cases=len(store.manifest['cases']) - n0))
        print(f'[fixtures] plans: {recipe}: {len(calls)} recorded calls -> {have[-1]["cases"]} cases', flush=True)
    man = store.finish(recipes=have, recipes_without_recorded_plans=missing, seeds=list(PLAN_SEEDS))
    print(f"[fixtures] plans: {len(man['cases'])} cases from {len(have)} recipes"
          + (f"; no recorded plan calls yet for {', '.join(missing)} (their base runs came before the plan hook, or "
             f"have not run)" if missing else '') + f' -> {store.dir}', flush=True)
    return man


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    for flag in ('--kernels', '--functions', '--plans', '--recipes'):
        ap.add_argument(flag, action='store_true')
    ap.add_argument('--only', default='')
    ap.add_argument('--out', default='')
    a = ap.parse_args(B.script_args())
    every = not (a.kernels or a.functions or a.plans or a.recipes)
    only = {x for x in a.only.split(',') if x} or None
    edition = B.bare_terrain_package()
    key = B.source_key(edition)
    out = os.path.abspath(a.out) if a.out else os.path.join(B.parity_root(), key['folder'], 'fixtures')
    os.makedirs(out, exist_ok=True)
    v = B.versions()
    print(f"[fixtures] Blender edition {key['commit'][:7]} (field hash {key['field_hash'][:10]}), Python "
          f"{v['python']}, numpy {v['numpy']}, zlib {v['zlib']} -> {out}", flush=True)
    if v['numpy'] != '2.3.4':
        print(f"[fixtures] WARNING: numpy {v['numpy']} is not Blender 5.2's 2.3.4: run this with Blender's own Python "
              f"(plan C6); the manifests record the version", flush=True)
    ok = True
    extra = dict(key=key)
    if a.kernels or every:
        man = kernel_fixtures(out, key, only)
        ok &= not any('error' in s for s in man['sources'])
        ok &= _run_script(os.path.join(HERE, '..', 'design_probes', 'make_twin_fixtures.py'),
                          os.path.join(out, 'twin_probe'), extra)
    if a.functions or every:
        man = function_fixtures(out, key, only)
        ok &= not any('error' in g for g in man['groups'])
    if a.plans or every:
        plan_fixtures(out, key, only)
        ok &= _run_script(os.path.join(HERE, '..', 'core_runner', 'np_random_expected.py'),
                          os.path.join(out, 'np_random'), extra)
    if a.recipes or every:
        ok &= _run_script(os.path.join(HERE, '..', 'core_inputs', 'core_inputs_expected.py'),
                          os.path.join(out, 'core_inputs'), extra)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
