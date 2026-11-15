"""The hooks a parity run installs in Blender from outside (PORT_PLAN.md 5.1, 5.4, 5.7; no change to the Blender
branch): the reference implementation is design_probes/blender_floor_patterns.py, whose hooks these are, grown into
the dispatch log, the readbacks, the step snapshots and the stage dumps of the plan's formats (5.2).

    import _hooks as H
    hooks = H.install()                 # after the Blender package and the GPU are up (G.init(): the self test's
                                        # dispatch is never logged)
    hooks.start(pattern=None, log_dir=..., snap=H.SnapStore(...), dumper=..., plans=H.PlanRecorder(...))
                                        # then api.generate(...)
    hooks.stop()

What is wrapped (module attributes, so every caller's lookup finds the wrapper):
  run.get_op                 each op call: its name and index (the op of every dispatch inside it); in a perturbed
                             run (pattern p) every float32 2-D field of the level moved by one ulp on half the cells
                             (+1 on a quarter, -1 on a quarter; numpy's default_rng([p, op call])) before the op runs,
                             which reaches the ops that run in numpy too; with a dumper, the stage dumps
  solvers/fluvial.StageContext.__init__   the level and the pass (a pre-pass of the coarsest level, or its own cells)
                             every later dispatch belongs to (contexts made outside op calls only: run.py's)
  run.run_levels, masks.compute_stack     the runner's own work and the masks after it: op '<runner>' / '<masks>'
  core/gpu.run               every dispatch: the log line; in a perturbed run, inside an op call, the images a kernel
                             wrote moved by one ulp right after its first dispatch in that call (default_rng([p, op
                             call, kernel, 1])) and copied back by a copy kernel: this reaches GPU state an op makes for
                             itself (the dune field grows on a tile from its own start fields); the step snapshots
  core/gpu.read              every readback: its line in readbacks.jsonl.gz
  solvers/hydro.lakes, solvers/hydro.route_to_convergence, run.where_mask
                             the runner's end stages and a stage's `where` mask: their dumps (run.py's own calls only)
  every function that draws from numpy's Generator (discover_plan_functions)
                             the plans: each outermost call's arguments and result (PlanRecorder), in a base run

The dispatch log (5.2): <dir>/dispatch_log.jsonl.gz, one JSON array per dispatch,
    [op, kernel, [[uniform, value or [values]], ...] by name, [[image, height, width, format], ...] by name,
     [sampler names] sorted, meta]
values as the caller gave them (float64; integers for int uniforms: the kernel's //! types are in kernels.json), and
meta {g: work groups, call: the op call (null outside ops), level, pass, s: [[height, width, format] per sampler],
end: 'lakes' | 'route' for the runner's end stages}. Readbacks: <dir>/readbacks.jsonl.gz, one
    [index of the last dispatch before it, op, image or field name, height, width, channels, [min, max, sum], meta]
per G.read. The device's self test (_self_test, once per process) is never in a log.

Step snapshots (5.7): each kernel's bound images after its 1st, 10th, 100th, 1,000th and 10,000th dispatch of the
run (key '<kernel>#<count>'), and on the main level's own cells after its 1st, 10th and 100th dispatch within each
op call (key 'L<level>_c<call>_<op>_<kernel>#<count>'). The base run keeps the arrays (snap/d<dispatch>.npz and
snap/index.json); a perturbed run compares its own with the base's at the same key and keeps only the differences.
A snapshot also holds the dispatch's inputs, each sampler's texture as 'in__<sampler>': the forcing a solver hands
its kernels in textures (the fluvial run's `par` = U, K, Sc, G and `pin`: the relief controller's factors live there,
not in uniforms, so the dispatch log alone would not see a wrong K; measured on rolling_hills: five perturbed runs
moved the main level by 9-16 % of relief and not one uniform by more than 4 float32 steps).
"""
from __future__ import annotations

import functools
import gzip
import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _blender as B  # noqa: E402

SNAP_AT = (1, 10, 100, 1000, 10000)
CALL_SNAP_AT = (1, 10, 100)
# the solvers' per-process memos of results (5.4 item 1): a run that follows another in one process would get the
# first one's result back (a dune tile is grown once per process)
MEMOS = ('_TILES', '_AGED_PATCHES', '_PLANS', '_DOMAINS', '_COLUMN_CACHE', '_CACHE')
OUTSIDE = ('<prepare>', '<runner>', '<masks>', '<after>')     # the op names of work done outside op calls


def clear_memos():
    """Empty every per-process memo of the Blender terrain modules; the number of entries removed."""
    n = 0
    for name, mod in list(sys.modules.items()):
        if name.startswith('eidoblend.terrain') and mod is not None:
            for m in MEMOS:
                d = getattr(mod, m, None)
                if isinstance(d, dict):
                    n += len(d)
                    d.clear()
    return n


def nudge(a, rng):
    """One float32 ulp up on a quarter of the cells and down on another quarter (blender_floor_patterns.py _nudge)."""
    r = rng.random(a.shape)
    up, dn = r < 0.25, r >= 0.75
    return np.where(up, np.nextafter(a, np.float32(np.inf)),
                    np.where(dn, np.nextafter(a, np.float32(-np.inf)), a)).astype(np.float32)


def channel_diffs(got, base):
    """Per channel of two (H, W, C) arrays: [max |d| / range, RMS / range, range], the range that of the base's
    channel (its largest |value| when it is flat, 1 when that is 0)."""
    out = []
    g = np.asarray(got, np.float64)
    b = np.asarray(base, np.float64)
    if g.ndim == 2:
        g, b = g[:, :, None], b[:, :, None]
    for c in range(b.shape[2]):
        bc, gc = b[:, :, c], g[:, :, c]
        fin = np.isfinite(bc) & np.isfinite(gc)
        same_nan = bool(np.array_equal(np.isnan(bc), np.isnan(gc)))
        if not fin.any():
            out.append([0.0 if same_nan else None, 0.0 if same_nan else None, 0.0])
            continue
        rng_ = float(np.ptp(bc[fin])) or float(np.max(np.abs(bc[fin]))) or 1.0
        d = (gc - bc)[fin]
        out.append([float(np.max(np.abs(d))) / rng_ if same_nan else None,
                    float(np.sqrt(np.mean(d * d))) / rng_ if same_nan else None, rng_])
    return out


class SnapStore:
    """The step snapshots of one run: the base run writes them (dir), a perturbed run compares (base_dir)."""

    def __init__(self, dir, base_dir=None):
        self.dir, self.base = dir, base_dir
        self.index, self.diffs = {}, {}
        self.bytes = 0
        if base_dir is None:
            os.makedirs(dir, exist_ok=True)
            self.base_index = None
        else:
            self.base_index = (B.read_json(os.path.join(base_dir, 'index.json')) or {}).get('snapshots', {})

    def take(self, keys, d, kernel, arrays, meta):
        if self.base is None:
            fname = f'd{d:07d}.npz'
            p = B.save_npz(os.path.join(self.dir, fname), arrays)
            self.bytes += os.path.getsize(p)
            for key in keys:
                self.index[key] = dict(d=d, file=fname, kernel=kernel, op=meta.get('op'), call=meta.get('call'),
                                       level=meta.get('level'), images={n: list(a.shape) for n, a in arrays.items()})
            return
        loaded = {}
        for key in keys:
            ent = self.base_index.get(key)
            if ent is None:
                self.diffs[key] = {'missing_in_base': True, 'd': d}
                continue
            if ent['file'] not in loaded:
                with np.load(os.path.join(self.base, ent['file'])) as z:
                    loaded[ent['file']] = {n: z[n] for n in z.files}
            base = loaded[ent['file']]
            rec = {'d': d, 'base_d': ent['d']}
            for n, a in arrays.items():
                b = base.get(n)
                rec[n] = None if b is None or b.shape != a.shape else channel_diffs(a, b)
            self.diffs[key] = rec

    def finish(self):
        if self.base is None:
            B.write_json(os.path.join(self.dir, 'index.json'), {'snap_at': SNAP_AT, 'call_snap_at': CALL_SNAP_AT,
                                                               'bytes': self.bytes, 'snapshots': self.index})
        return self.diffs


# ------------------------------------------------------------------------------------------------ the plans ---
# Every function of the Blender terrain package that draws from numpy's Generator is a plan (PORT_PLAN.md 2.4,
# 5.1): found by reading the modules' syntax trees (a function whose body calls default_rng, or calls a function that
# only returns one, such as solvers/volcanic._rng), never by a list that could miss one. A base run records each
# outermost call: the function, the op and level it ran in, its arguments (pickled, when they are small: plans over
# objects, not field evaluations) and its result as JSON and arrays. fixtures.py --plans then makes the same calls
# again for seeds 1-8 in plain Python.

PLAN_PACKAGES = ('solvers', 'recipes', 'core')
PLAN_SKIP_MODULES = ('core.twins',)                 # the twins' test inputs draw too; they are not plans
PLAN_ARGS_MAX_BYTES = 4 << 20                       # larger arguments are whole-level fields: recorded by shape only
PLAN_CALLS_PER_FUNCTION = 48


def _calls_in(node, names):
    import ast
    found = set()
    for c in ast.walk(node):
        if isinstance(c, ast.Call):
            nm = c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, 'id', None)
            if nm in names:
                found.add(nm)
    return found


def discover_plan_functions(terrain_dir, ops=False):
    """[(module 'solvers.karst', qualname 'plan_karst' | 'Column.__init__')] of every module-level function and
    method that draws from numpy's Generator (see above); ops (op_*) are left out: their calls are the stage dumps.
    With ops=True, the ops that draw in their own body instead (their draws have no plan fixture: the stage replay of
    that op is what checks them)."""
    import ast
    trees = {}
    for pkg in PLAN_PACKAGES:
        d = os.path.join(terrain_dir, pkg)
        for f in sorted(os.listdir(d)):
            if f.endswith('.py') and f != '__init__.py' and f'{pkg}.{f[:-3]}' not in PLAN_SKIP_MODULES:
                with open(os.path.join(d, f), encoding='utf-8') as fh:
                    trees[f'{pkg}.{f[:-3]}'] = ast.parse(fh.read())
    funcs = {}
    for mod, tree in trees.items():
        out = funcs[mod] = []
        for n in tree.body:
            if isinstance(n, ast.FunctionDef):
                out.append((n.name, n))
            elif isinstance(n, ast.ClassDef):
                out += [(f'{n.name}.{m.name}', m) for m in n.body if isinstance(m, ast.FunctionDef)]
    factories = set()
    for mod, fl in funcs.items():
        for q, n in fl:
            if any(isinstance(s, ast.Return) and isinstance(s.value, ast.Call)
                   and getattr(s.value.func, 'attr', None) == 'default_rng' for s in n.body):
                factories.add(q.split('.')[-1])
    found = []
    for mod, fl in funcs.items():
        for q, n in fl:
            name = q.split('.')[-1]
            if name in factories or name.startswith('op_') != bool(ops):
                continue
            if _calls_in(n, {'default_rng'} | factories):
                found.append((mod, q))
    return found


def resolve_plan_function(module, qualname):
    """(function, owner): the function `qualname` of eidoblend.terrain.<module> as the module has it now, and the
    object it is an attribute of (the module, or its class); (None, None) when it is gone."""
    import importlib
    try:
        owner = importlib.import_module(f'eidoblend.terrain.{module}')
        parts = qualname.split('.')
        for p in parts[:-1]:
            owner = getattr(owner, p)
        return getattr(owner, parts[-1]), owner
    except (ImportError, AttributeError):
        return None, None


def _bind(fn, args, kwargs):
    import inspect
    try:
        return inspect.signature(fn).bind_partial(*args, **kwargs)
    except (TypeError, ValueError):
        return None


def plan_call_args(call, seed=None):
    """(args, kwargs) of a recorded plan call (its pickled arguments), with `seed` in place of its seed argument."""
    import pickle
    args, kwargs = pickle.loads(call['pickle'])
    if seed is not None and call.get('seed_arg'):
        fn, _owner = resolve_plan_function(call['module'], call['qualname'])
        b = _bind(fn, args, kwargs)
        if b is not None:
            b.arguments['seed'] = seed
            return list(b.args), dict(b.kwargs)
    return list(args), dict(kwargs)


def _arg_bytes(v, depth=0):
    if isinstance(v, np.ndarray):
        return v.nbytes
    if depth > 3:
        return 0
    if isinstance(v, dict):
        return sum(_arg_bytes(x, depth + 1) for x in v.values())
    if isinstance(v, (list, tuple)):
        return sum(_arg_bytes(x, depth + 1) for x in v)
    d = getattr(v, '__dict__', None)
    return sum(_arg_bytes(x, depth + 1) for x in d.values()) if isinstance(d, dict) else 0


class PlanRecorder:
    """The plan calls of one base run: <dir>/calls.pkl (the replayable calls, for fixtures.py --plans),
    <dir>/plans.json (every call: where it ran, its arguments' JSON form, its result) and r<k>.npz (result arrays)."""

    def __init__(self, dir):
        self.dir = dir
        os.makedirs(dir, exist_ok=True)
        self.depth = 0
        self.calls, self.records, self.counts = [], [], {}

    def before(self, fn, args, kwargs):
        """The call's arguments pickled before it runs (it may change them), or None when they are too large or do
        not pickle."""
        import pickle
        if _arg_bytes(args) + _arg_bytes(kwargs) > PLAN_ARGS_MAX_BYTES:
            return None
        try:
            return pickle.dumps((args, kwargs), protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:                                            # noqa: BLE001 - a context, a device, a closure
            return None

    def add(self, h, module, qualname, fn, blob, args, kwargs, out):
        key = f'{module}.{qualname}'
        n = self.counts[key] = self.counts.get(key, 0) + 1
        if n > PLAN_CALLS_PER_FUNCTION:
            return
        b = _bind(fn, args, kwargs)
        is_init = qualname.endswith('.__init__')
        arrays = {}
        k = len(self.records)
        try:
            result = B.jsonable(args[0] if is_init else out, arrays, 'result', 256)
        except Exception as e:                                       # noqa: BLE001 - recorded
            result = {'__error__': f'{type(e).__name__}: {e}'}
        shapes = {}
        try:
            arg_json = B.jsonable(dict(b.arguments) if b is not None else dict(args=list(args), kwargs=kwargs),
                                  shapes, 'args', 256)
        except Exception as e:                                       # noqa: BLE001 - recorded
            arg_json = {'__error__': f'{type(e).__name__}: {e}'}
        rec = dict(index=k, module=module, qualname=qualname, op=h.op, call=h.call if h.op not in OUTSIDE else None,
                   level=h.level, pass_index=h.pass_, seed_arg=bool(b is not None and 'seed' in b.arguments),
                   replayable=blob is not None, init=is_init, args=arg_json,
                   arg_arrays={p: [list(a.shape), str(a.dtype)] for p, a in shapes.items()}, result=result,
                   result_arrays=None)
        if arrays:
            rec['result_arrays'] = f'r{k:04d}.npz'
            B.save_npz(os.path.join(self.dir, rec['result_arrays']), arrays)
        self.records.append(rec)
        if blob is not None:
            self.calls.append(dict(index=k, module=module, qualname=qualname, op=rec['op'], level=rec['level'],
                                   seed_arg=rec['seed_arg'], init=is_init, pickle=blob))

    def finish(self):
        import pickle
        with open(os.path.join(self.dir, 'calls.pkl'), 'wb') as f:
            pickle.dump(self.calls, f, protocol=pickle.HIGHEST_PROTOCOL)
        B.write_json(os.path.join(self.dir, 'plans.json'),
                     dict(calls=self.records, counts=self.counts, per_function_limit=PLAN_CALLS_PER_FUNCTION,
                          args_max_bytes=PLAN_ARGS_MAX_BYTES))
        return dict(recorded=len(self.records), replayable=len(self.calls), functions=len(self.counts))


def install_plan_hooks(h):
    """Wrap every plan function (discover_plan_functions) so a run with a PlanRecorder records its outermost calls."""
    import eidoblend.terrain as pkg
    wrapped = []
    for module, qualname in discover_plan_functions(pkg.__path__[0]):
        fn, owner = resolve_plan_function(module, qualname)
        if fn is None or getattr(fn, '_parity_plan', False):
            continue

        def make(fn=fn, module=module, qualname=qualname):
            @functools.wraps(fn)
            def w(*a, **k):
                rec = h.plans
                if not h.active or rec is None or rec.depth > 0:
                    return fn(*a, **k)
                blob = rec.before(fn, a, k)
                rec.depth += 1
                try:
                    out = fn(*a, **k)
                finally:
                    rec.depth -= 1
                rec.add(h, module, qualname, fn, blob, a, k, out)
                return out
            w._parity_plan = True
            return w
        setattr(owner, qualname.split('.')[-1], make())
        wrapped.append(f'{module}.{qualname}')
    return wrapped


def _copy_kernel(G, fmt, cache={}):
    if fmt not in cache:
        cache[fmt] = G.kernel(source='//! sampler src\n//! image dst ' + fmt.lower() + '\nvoid main() {\n'
                              '  ivec2 p = ivec2(gl_GlobalInvocationID.xy);\n  ivec2 n = textureSize(src, 0);\n'
                              '  if (!inside(p, n)) return;\n  imageStore(dst, p, texelFetch(src, p, 0));\n}\n',
                              name=f'parity_copy_{fmt.lower()}')
    return cache[fmt]


def _spec(k):
    s = k.spec
    return dict(samplers=list(s.samplers), images=dict(s.images), uniforms=dict(s.uniforms), local=list(s.local))


def _typed(v, ty):
    """A uniform's value as the log records it: floats as given (float64), integers for int / ivec uniforms."""
    integer = ty == 'int' or (ty or '').startswith('ivec')
    if isinstance(v, (list, tuple, np.ndarray)):
        return [int(x) if integer else float(x) for x in np.ravel(v)]
    return int(v) if integer else float(v)


def _num(x):
    x = float(x)
    return x if math.isfinite(x) else None


class Hooks:
    def __init__(self, A, RUN, G, FL, HY, MS):
        self.A, self.RUN, self.G, self.FL, self.HY, self.MS = A, RUN, G, FL, HY, MS
        self.active = False
        self._reset()

    def _reset(self):
        self.pattern = None
        self.op, self.call, self.end = '<prepare>', -1, None
        self.level, self.pass_, self.ctx = None, None, None
        self.ctx_count, self.stage_n, self.call_counts = {}, {}, {}
        self.names, self.counts, self.kernels = [], {}, {}
        self.dispatches = self.readbacks = 0
        self.op_nudges = self.in_nudges = 0
        self.log = self.rlog = None
        self.snap = self.dumper = self.plans = None
        self.run_args, self.main_index = None, None
        self.in_hook = False
        self.names_by_id = {}
        self.op_calls = []                       # [op, level, pass] per op call

    # ---------------------------------------------------------------------------------------------- control ---
    def start(self, pattern=None, log_dir=None, snap=None, dumper=None, plans=None):
        self._reset()
        self.pattern = pattern
        self.plans = plans
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            self.log = gzip.open(os.path.join(log_dir, 'dispatch_log.jsonl.gz'), 'wb')
            self.rlog = gzip.open(os.path.join(log_dir, 'readbacks.jsonl.gz'), 'wb')
        self.snap, self.dumper = snap, dumper
        self.memos_cleared = clear_memos()
        self.active = True

    def stop(self, log_dir=None):
        self.active = False
        for f in (self.log, self.rlog):
            if f is not None:
                f.close()
        self.log = self.rlog = None
        if log_dir:
            B.write_json(os.path.join(log_dir, 'kernels.json'), self.kernels)
        if self.dumper is not None:
            self.dumper.flush()
        self.plan_summary = self.plans.finish() if self.plans is not None else None
        return self.snap.finish() if self.snap is not None else None

    def summary(self):
        return dict(dispatches=self.dispatches, readbacks=self.readbacks, op_calls=self.call + 1,
                    kernels={k: self.counts[k] for k in sorted(self.counts, key=lambda k: -self.counts[k])},
                    op_entry_nudges=self.op_nudges, in_op_nudges=self.in_nudges, memos_cleared=self.memos_cleared,
                    calls=self.op_calls, plans=getattr(self, 'plan_summary', None))

    def stage_for(self, params):
        """The recipe Stage whose params dict this is (run.py passes st.params itself), or None."""
        for st in (self.run_args or {}).get('stages') or []:
            if st.params is params:
                return st
        return None

    # -------------------------------------------------------------------------------------- op-entry hooks ---
    def enter_op(self, name, fields, level, params, seed, ctx):
        """What happens as an op starts: the call index, the op-entry nudge (perturbed runs), the dump. Returns
        the dump record (or None)."""
        self.call += 1
        self.op, self.end = name, None
        lvl = self.level if self.level is not None else getattr(level, 'index', None)
        n = self.stage_n.get((lvl, self.pass_), 0)
        self.stage_n[(lvl, self.pass_)] = n + 1
        self.op_calls.append([name, lvl, self.pass_])
        if self.pattern is not None:
            rng = np.random.default_rng([self.pattern, self.call])
            for key in sorted(fields.keys()):
                v = fields[key]
                if isinstance(v, np.ndarray) and v.dtype == np.float32 and v.ndim == 2:
                    fields[key] = nudge(v, rng)
            self.op_nudges += 1
        if self.dumper is not None:
            return self.dumper.before(self, self.call, lvl, self.pass_, n, name, fields, level, params, seed, ctx)
        return None

    def leave_op(self, rec, fields, ctx, seconds):
        if rec is not None:
            self.dumper.after(rec, fields, ctx, seconds)
        self.op, self.end = '<runner>', None

    # ------------------------------------------------------------------------------------------ dispatches ---
    def on_dispatch(self, k, groups, samplers, images, uniforms):
        G = self.G
        name = k.name
        d = self.dispatches
        self.dispatches += 1
        if name not in self.kernels:
            self.names.append(name)
            self.kernels[name] = _spec(k)
        c = self.counts[name] = self.counts.get(name, 0) + 1
        in_op = self.op not in OUTSIDE
        cc = None
        if in_op:
            cc = self.call_counts[(self.call, name)] = self.call_counts.get((self.call, name), 0) + 1
        for n, t in samplers.items():
            self.names_by_id[id(t)] = n
        for n, t in images.items():
            self.names_by_id[id(t)] = n
        if self.pattern is not None and in_op and cc == 1 and images:
            rng = np.random.default_rng([self.pattern, self.call, self.names.index(name), 1])
            for n in sorted(images):
                t = images[n]
                a = nudge(self._orig_read(t), rng)
                self._orig_run(_copy_kernel(G, str(t.format)), None, samplers={'src': G.texture(a)},
                               images={'dst': t}, uniforms={})
                self.in_nudges += 1
        sn = sorted(samplers)
        if groups is None:
            first = next(iter(images.values()))
            g = list(k.groups_for((first.height, first.width)))
        else:
            g = [int(x) for x in groups]
        meta = {'g': g, 'call': self.call if in_op else None, 'level': self.level, 'pass': self.pass_,
                's': [[int(samplers[s].height), int(samplers[s].width), str(samplers[s].format)] for s in sn]}
        if self.end:
            meta['end'] = self.end
        if self.log is not None:
            u = sorted([un, _typed(v, k.spec.uniforms.get(un))] for un, v in uniforms.items())
            ims = sorted([n, int(t.height), int(t.width), str(t.format)] for n, t in images.items())
            self.log.write((json.dumps([self.op, name, u, ims, sn, meta]) + '\n').encode())
        if images and self.snap is not None:
            keys = []
            if c in SNAP_AT:
                keys.append(f'{name}#{c}')
            if (in_op and cc in CALL_SNAP_AT and self.level == self.main_index and self.ctx is not None
                    and self.ctx.prepass is None):
                keys.append(f'L{self.level}_c{self.call}_{self.op}_{name}#{cc}')
            if keys:
                arrays = {n: self._orig_read(t) for n, t in images.items()}
                arrays.update({'in__' + n: self._orig_read(t) for n, t in samplers.items()})
                self.snap.take(keys, d, name, arrays, dict(meta, op=self.op))

    def on_read(self, tex, a):
        self.readbacks += 1
        if self.rlog is None:
            return
        name = self.names_by_id.get(id(tex), '?')
        f = np.asarray(a, np.float64)
        line = [self.dispatches - 1, self.op, name, int(a.shape[0]), int(a.shape[1]),
                int(a.shape[2]) if a.ndim == 3 else 1,
                [_num(np.min(f)), _num(np.max(f)), _num(np.sum(f))] if f.size else [None, None, 0.0],
                {'call': self.call if self.op not in OUTSIDE else None, 'level': self.level, 'pass': self.pass_,
                 **({'end': self.end} if self.end else {})}]
        self.rlog.write((json.dumps(line) + '\n').encode())


def install():
    """Wrap the Blender modules (once per process) and return the Hooks. Call after the GPU is initialised."""
    from eidoblend.terrain import api as A
    from eidoblend.terrain import masks as MS
    from eidoblend.terrain import run as RUN
    from eidoblend.terrain.core import gpu as G
    from eidoblend.terrain.solvers import fluvial as FL
    from eidoblend.terrain.solvers import hydro as HY
    if getattr(RUN, '_parity_hooks', None) is not None:
        return RUN._parity_hooks
    G.init()                                            # the self test runs here, before anything is logged
    h = Hooks(A, RUN, G, FL, HY, MS)
    h._orig_run, h._orig_read, h._orig_get_op = G.run, G.read, RUN.get_op

    def _get_op(name):
        fn = h._orig_get_op(name)
        if not h.active:
            return fn

        @functools.wraps(fn)                            # keeps evolves / post and the signature (ctx) run.py reads
        def wrapped(fields, level, params, seed, *a, **k):
            rec = h.enter_op(name, fields, level, params, seed, k.get('ctx'))
            t0 = time.perf_counter()
            try:
                return fn(fields, level, params, seed, *a, **k)
            finally:
                h.leave_op(rec, fields, k.get('ctx'), time.perf_counter() - t0)
        return wrapped

    def _run(kernel, groups=None, samplers=None, images=None, uniforms=None):
        h._orig_run(kernel, groups, samplers, images, uniforms)
        if not h.active or h.in_hook:
            return
        k = G.kernel(kernel) if isinstance(kernel, str) else kernel
        if k.name == '_self_test':
            return
        h.in_hook = True
        try:
            h.on_dispatch(k, groups, samplers or {}, images or {}, uniforms or {})
        finally:
            h.in_hook = False

    def _read(tex):
        a = h._orig_read(tex)
        if h.active and not h.in_hook:
            h.on_read(tex, a)
        return a

    orig_init = FL.StageContext.__init__

    def _ctx_init(self, *a, **k):
        orig_init(self, *a, **k)
        if h.active and h.op in OUTSIDE:                # run.py's contexts, one per level and pass
            i = self.index
            kk = h.ctx_count.get(i, 0)
            h.ctx_count[i] = kk + 1
            h.ctx, h.level, h.pass_ = self, i, kk

    orig_run_levels = RUN.run_levels

    @functools.wraps(orig_run_levels)
    def _run_levels(plan, recipe, values, stages, *a, **k):
        if h.active:
            h.run_args = dict(plan=plan, recipe=recipe, values=values, stages=stages, args=a, kwargs=k)
            h.main_index = next((lv.index for lv in plan if lv.role == 'main'), len(plan) - 1)
            h.op = '<runner>'
            if h.dumper is not None:
                h.dumper.start(h)
        try:
            return orig_run_levels(plan, recipe, values, stages, *a, **k)
        finally:
            if h.active:
                h.op = '<after>'

    orig_masks = MS.compute_stack

    @functools.wraps(orig_masks)
    def _compute_stack(*a, **k):
        prev = h.op
        if h.active:
            h.op = '<masks>'
        try:
            return orig_masks(*a, **k)
        finally:
            h.op = prev

    def _end(fn, stage):
        @functools.wraps(fn)
        def w(*a, **k):
            if not h.active or h.op != '<runner>':
                return fn(*a, **k)
            h.end = stage
            rec = h.dumper.end_before(h, stage, a, k) if h.dumper is not None else None
            try:
                r = fn(*a, **k)
            finally:
                h.end = None
            if rec is not None:
                h.dumper.end_after(rec, a, k, r)
            return r
        return w

    orig_where = RUN.where_mask

    @functools.wraps(orig_where)
    def _where(expr, fields, level, mask_params=None):
        m = orig_where(expr, fields, level, mask_params)
        if h.active and h.dumper is not None:
            h.dumper.where(m)
        return m

    G.run, G.read, RUN.get_op = _run, _read, _get_op
    FL.StageContext.__init__ = _ctx_init
    RUN.run_levels, MS.compute_stack, RUN.where_mask = _run_levels, _compute_stack, _where
    HY.lakes = _end(HY.lakes, 'lakes')
    HY.route_to_convergence = _end(HY.route_to_convergence, 'route')
    h.plan_functions = install_plan_hooks(h)
    RUN._parity_hooks = h
    return h
