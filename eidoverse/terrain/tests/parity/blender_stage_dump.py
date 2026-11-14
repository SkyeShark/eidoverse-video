"""Stage dumps of the Blender edition (PORT_PLAN.md 5.1, 5.2): every op's level fields before and after it, with
its context, so a port's op can be replayed from Blender's own input; and the stage floors (5.3, 5.4 item 7): each
op replayed from its dumped input with the revised protocol's perturbation, five patterns, the largest difference
recorded. Made from outside, with no change to the Blender branch (tests/parity/_hooks.py wraps the level runner).

The dumps are made by the floor runs' base run (blender_chaos_floor.py, which also logs the dispatches and keeps the
step snapshots of the same run); this file owns their format and the replay:

    bash run_blender.sh eidoverse/terrain/tests/parity/blender_stage_dump.py -- --floor <run>/base/stages \
        [--patterns 5] [--levels main|all|0,2] [--ops fluvial,talus]
                         replays each op of the chosen levels from its 'before' dump: once as it is (it must give
                         the 'after' dump bit for bit, or the dump does not hold all of the op's input), then once per
                         pattern with both perturbation points of 5.4 (every float field of the level at the op's
                         entry, and each kernel's images after its first dispatch in the call); writes
                         <run>/base/stage_floors.json

The format (5.2), in <recipe>_s<seed>_<quality>/base/stages/:
    stages.json                       the run (plan, recipe to_dict, knob values, resolved stages, seed, flatten,
                                      sea_level, base_elevation_m, the recipe's defaults) and per op call: level,
                                      pass (the coarse-to-fine pass of the coarsest level, 0 when there is one), n (its
                                      number on that level and pass), op, label, where, params, seed, the window, the
                                      context (index, prepass, fresh, role, sea_level, base_elevation_m, flatten,
                                      grow_levels, values, the pins' names, the JSON form of `shared`), seconds,
                                      whether it evolved, and the files below; the end stages likewise
    L{i}_p{k}_{n:02d}_{op}_before.npz every array of the level's Fields, the pins as pin__<name>, the arrays inside
                                      `shared` as shared__<path> (the JSON names the path)
    L{i}_p{k}_{n:02d}_{op}_after.npz  every array of the Fields after the op (before run.py's `where` blend and, for an
                                      op without ctx on a child level, its band pull: the op's own output); shared
                                      arrays after it as shared__<path>
    L{i}_p{k}_{n:02d}_{op}_where.npz  the stage's `where` mask (0..1, float64), when it has one
    L{i}_p{k}_{n:02d}_{op}_before.pkl the op's params and `shared`, flatten and values as Python objects (for the
                                      Blender replay; the JSON carries what a port reads)
    L{i}_end_lakes_{before|after}.npz the runner's end stages: the lakes (fields, no_lake; after: fields, filled) and
    L{i}_end_route_{before|after}.npz the drainage area routed to convergence (surf, A0, A_in; after: A)
Arrays are numpy's, row 0 south, as the Blender fields hold them; the npz files are np.savez_compressed (core/io.js
reads both kinds).
"""
from __future__ import annotations

import copy
import os
import pickle
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _blender as B  # noqa: E402

SHARED_ARRAY_MIN = 64          # arrays in `shared` above this many values go to the npz, smaller ones into the JSON


class StageDumper:
    """Writes the stage dumps of one run (the hooks call it)."""

    def __init__(self, dir):
        self.dir = dir
        os.makedirs(dir, exist_ok=True)
        self.header = None
        self.records, self.end_records = [], []
        self.last = None
        self.bytes = 0

    def _save(self, name, arrays):
        p = B.save_npz(os.path.join(self.dir, name), arrays)
        self.bytes += os.path.getsize(p)
        return name

    def start(self, h):
        ra = h.run_args
        kw = ra['kwargs']
        recipe = ra['recipe']
        self.header = dict(plan=[lv.to_dict() for lv in ra['plan']], recipe=recipe.to_dict(),
                           values=B.jsonable(ra['values']), stages=[st.to_dict() for st in ra['stages']],
                           seed=int(kw.get('seed', 0)), flatten=B.jsonable(kw.get('flatten')),
                           sea_level=kw.get('sea_level'), base_elevation_m=kw.get('base_elevation_m', 0.0),
                           defaults=B.jsonable(dict(getattr(recipe, 'defaults', {}) or {})),
                           main_index=h.main_index)
        self.flush()

    def before(self, h, call, lvl, k, n, op, fields, level, params, seed, ctx):
        stem = f'L{lvl}_p{k}_{n:02d}_{op}'
        arrays = {name: np.asarray(v) for name, v in fields.items()}
        pins = getattr(ctx, 'pins', None) if ctx is not None else None
        if pins:
            for p, v in pins.items():
                if v is not None:
                    arrays['pin__' + p] = np.asarray(v)
        shared = ctx.shared if ctx is not None else None
        sh = {}
        shared_json = B.jsonable(shared, sh, 'shared', SHARED_ARRAY_MIN) if shared is not None else None
        for p, v in sh.items():
            arrays['shared__' + p] = np.asarray(v)
        self._save(stem + '_before.npz', arrays)
        pk, pk_err = stem + '_before.pkl', None
        try:
            with open(os.path.join(self.dir, pk), 'wb') as f:
                pickle.dump(dict(params=params, shared=shared, flatten=getattr(ctx, 'flatten', None),
                                 values=getattr(ctx, 'values', None)), f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:                                          # noqa: BLE001 - recorded: no Blender replay
            pk, pk_err = None, f'{type(e).__name__}: {e}'
            try:
                os.remove(os.path.join(self.dir, stem + '_before.pkl'))
            except OSError:
                pass
        st = h.stage_for(params)
        rec = dict(call=call, level=lvl, pass_index=k, n=n, op=op, label=getattr(st, 'label', None),
                   where=(str(st.where_expr) if st is not None and getattr(st, 'where_expr', None) is not None
                          else None),
                   params=B.jsonable(params), seed=int(seed), takes_ctx=ctx is not None, window=level.to_dict(),
                   before=stem + '_before.npz', pickle=pk, pickle_error=pk_err, fields_before=sorted(fields.keys()),
                   t_start=round(time.time(), 3))
        if ctx is not None:
            rec['context'] = dict(index=ctx.index, prepass=ctx.prepass, fresh=bool(ctx.fresh), role=ctx.role,
                                  sea_level=ctx.sea_level, base_elevation_m=ctx.base_elevation_m,
                                  flatten=B.jsonable(ctx.flatten), grow_levels=ctx.grow_levels,
                                  values=B.jsonable(ctx.values), pins=sorted(pins) if pins else None,
                                  shared=shared_json)
        else:
            rec['context'] = None                   # an op without ctx: on a child level run.py band-pulls it after
        self.last = rec
        return rec

    def after(self, rec, fields, ctx, seconds):
        stem = rec['before'][:-len('_before.npz')]
        arrays = {name: np.asarray(v) for name, v in fields.items()}
        if ctx is not None:
            sh = {}
            rec['shared_after'] = B.jsonable(ctx.shared, sh, 'shared', SHARED_ARRAY_MIN)
            for p, v in sh.items():
                arrays['shared__' + p] = np.asarray(v)
            rec['evolved'] = bool(ctx.evolved)
        rec['after'] = self._save(stem + '_after.npz', arrays)
        rec['fields_after'] = sorted(fields.keys())
        rec['seconds'] = round(seconds, 3)
        self.records.append(rec)
        self.flush()

    def where(self, m):
        if self.last is not None:
            stem = self.last['before'][:-len('_before.npz')]
            self.last['where_mask'] = self._save(stem + '_where.npz', {'where': np.asarray(m)})
            self.flush()

    def end_before(self, h, stage, a, k):
        lvl = h.level
        rec = dict(level=lvl, stage=stage)
        if stage == 'lakes':
            fields, lv, thr, mode = a[0], a[1], a[2], a[3]
            parent = k.get('parent')
            arrays = {name: np.asarray(v) for name, v in fields.items()}
            if k.get('no_lake') is not None:
                arrays['no_lake'] = np.asarray(k['no_lake'])
            rec.update(window=lv.to_dict(), thr=float(thr), mode=mode, sea_level=k.get('sea_level'),
                       band=k.get('band'), parent=(parent[0].index if parent is not None else None))
        else:
            dev, surf, cell = a[0], a[1], a[2]
            arrays = {'surf': np.asarray(surf)}
            for nm in ('A0', 'A_in'):
                if k.get(nm) is not None:
                    arrays[nm] = np.asarray(k[nm])
            rec.update(cell=float(cell), device=getattr(dev, 'name', str(dev)))
        rec['before'] = self._save(f'L{lvl}_end_{stage}_before.npz', arrays)
        return rec

    def end_after(self, rec, a, k, r):
        if rec['stage'] == 'lakes':
            filled, nlakes = r
            arrays = {name: np.asarray(v) for name, v in a[0].items()}
            arrays['filled'] = np.asarray(filled)
            rec['nlakes'] = int(nlakes)
        else:
            A, iters = r
            arrays = {'A': np.asarray(A)}
            rec['iterations'] = int(iters)
        rec['after'] = self._save(f"L{rec['level']}_end_{rec['stage']}_after.npz", arrays)
        self.end_records.append(rec)
        self.flush()

    def flush(self):
        B.write_json(os.path.join(self.dir, 'stages.json'),
                     dict(self.header or {}, stages=self.records, end_stages=self.end_records, bytes=self.bytes))


# ---------------------------------------------------------------------------------------------- the replay ---

def _diffs(got, want):
    """Per field: [max |d| / range, RMS / range, p99 |d| / range, bit-identical] (range: the want's)."""
    out = {}
    for name in sorted(set(want) | set(got)):
        a, b = got.get(name), want.get(name)
        if a is None or b is None or np.shape(a) != np.shape(b):
            out[name] = {'missing': a is None, 'extra': b is None}
            continue
        a64, b64 = np.asarray(a, np.float64), np.asarray(b, np.float64)
        same = bool(np.array_equal(np.asarray(a).view(np.uint8), np.asarray(b).view(np.uint8))) \
            if np.asarray(a).dtype == np.asarray(b).dtype else False
        fin = np.isfinite(b64) & np.isfinite(a64)
        if not fin.any():
            out[name] = [0.0, 0.0, 0.0, same]
            continue
        r = float(np.ptp(b64[fin])) or float(np.max(np.abs(b64[fin]))) or 1.0
        d = np.abs(a64 - b64)[fin]
        out[name] = [float(d.max()) / r, float(np.sqrt(np.mean(d * d))) / r, float(np.percentile(d, 99)) / r, same]
    return out


def replay_one(h, header, rec, dir, pattern):
    """Run rec's op once from its 'before' dump (pattern None: as it is; else the 5.4 perturbation). The fields after
    it, {name: float32 array}."""
    from eidoblend.terrain.core.fields import Fields
    from eidoblend.terrain.core.levels import Level
    FL = h.FL
    plan = [Level.from_dict(d) for d in header['plan']]
    level = Level.from_dict(rec['window'])
    with np.load(os.path.join(dir, rec['before'])) as z:
        arrays = {k: z[k] for k in z.files}
    with open(os.path.join(dir, rec['pickle']), 'rb') as f:
        pk = pickle.load(f)
    fields = Fields(level, {k: v for k, v in arrays.items() if not k.startswith(('pin__', 'shared__'))})
    params = copy.deepcopy(pk['params'])
    ctx = None
    if rec['takes_ctx']:
        c = rec['context']
        pins = {k[5:]: v for k, v in arrays.items() if k.startswith('pin__')} or None
        was = h.active
        h.active = False                                   # a replay's own context: not one the run made
        ctx = FL.StageContext(plan=plan, index=c['index'], level=level, prepass=c['prepass'], fresh=c['fresh'],
                              role=c['role'], pins=pins, shared=copy.deepcopy(pk['shared']), seed=rec['seed'],
                              sea_level=c['sea_level'], base_elevation_m=c['base_elevation_m'],
                              flatten=copy.deepcopy(pk.get('flatten')), device=FL.device(None),
                              log=lambda m: None, values=copy.deepcopy(pk.get('values')),
                              grow_levels=c['grow_levels'])
        h.active = was
    fn = h._orig_get_op(rec['op'])
    h.start(pattern=pattern)                               # memos cleared; the dispatch and nudge hooks on
    h.main_index = header.get('main_index')
    h.call, h.level, h.pass_, h.ctx = rec['call'] - 1, rec['level'], rec['pass_index'], ctx
    r = h.enter_op(rec['op'], fields, level, params, rec['seed'], ctx)
    try:
        if ctx is not None:
            fn(fields, level, params, rec['seed'], ctx=ctx)
        else:
            fn(fields, level, params, rec['seed'])
    finally:
        h.leave_op(r, fields, ctx, 0.0)
        h.stop()
    return {k: np.asarray(v) for k, v in fields.items()}


def stage_floors(stages_dir, patterns=5, levels='main', ops=None, log=print):
    """The stage floors of one dump folder (module doc): {'stages': [...], 'patterns': n}, also written to
    <stages_dir>/../stage_floors.json."""
    import _hooks as H
    B.import_blender_terrain()
    h = H.install()
    header = B.read_json(os.path.join(stages_dir, 'stages.json'))
    main = header.get('main_index')
    if levels == 'main':
        want = {main}
    elif levels == 'all':
        want = None
    else:
        want = {int(x) for x in str(levels).split(',') if x != ''}
    out = dict(source=os.path.abspath(stages_dir), patterns=patterns, levels=levels,
               protocol='5.4: every float32 field of the level +-1 ulp on half the cells at the op entry, and each '
                        'kernel\'s images after its first dispatch in the call; default_rng([pattern, op call]) and '
                        '([pattern, op call, kernel, 1])', stages=[], versions=B.versions(h.G.init()))
    path = os.path.join(os.path.dirname(os.path.abspath(stages_dir)), 'stage_floors.json')
    for rec in header['stages']:
        if want is not None and rec['level'] not in want:
            continue
        if ops and rec['op'] not in ops:
            continue
        ent = dict(call=rec['call'], level=rec['level'], pass_index=rec['pass_index'], n=rec['n'], op=rec['op'],
                   label=rec.get('label'), seconds_in_run=rec.get('seconds'))
        if not rec.get('pickle'):
            ent['skipped'] = f"no pickle of its params and shared ({rec.get('pickle_error')})"
            out['stages'].append(ent)
            continue
        with np.load(os.path.join(stages_dir, rec['after'])) as z:
            want_after = {k: z[k] for k in z.files if not k.startswith('shared__')}
        t0 = time.perf_counter()
        base = replay_one(h, header, rec, stages_dir, None)
        ent['replay_seconds'] = round(time.perf_counter() - t0, 2)
        rd = _diffs(base, want_after)
        ent['replay_bit_identical'] = all(isinstance(v, list) and v[3] for v in rd.values())
        if not ent['replay_bit_identical']:
            ent['replay_vs_dump'] = rd
        samples = []
        for p in range(1, patterns + 1):
            got = replay_one(h, header, rec, stages_dir, p)
            samples.append(_diffs(got, base))
        fl = {}
        for name in base:
            vals = [s.get(name) for s in samples if isinstance(s.get(name), list)]
            if vals:
                fl[name] = dict(max_over_range=max(v[0] for v in vals), rms_over_range=max(v[1] for v in vals),
                                p99_over_range=max(v[2] for v in vals),
                                samples=[[v[0], v[1], v[2]] for v in vals])
        ent['floor'] = fl
        out['stages'].append(ent)
        log(f"[stage-floor] L{rec['level']} {rec['op']} (call {rec['call']}): replay "
            f"{'bit-identical' if ent['replay_bit_identical'] else 'DIFFERS'}, h floor "
            f"{fl.get('h', {}).get('rms_over_range', float('nan')):.3g} RMS / range ({ent['replay_seconds']} s a replay)")
        B.write_json(path, out)
    B.write_json(path, out)
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--floor', required=True, help='a stages/ folder of a base run')
    ap.add_argument('--patterns', type=int, default=5)
    ap.add_argument('--levels', default='main')
    ap.add_argument('--ops', default='')
    a = ap.parse_args(B.script_args())
    stage_floors(a.floor, a.patterns, a.levels, [o for o in a.ops.split(',') if o] or None)


if __name__ == '__main__':
    main()
