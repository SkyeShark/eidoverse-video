"""The detail package's own Blender runs with the parity hooks (PORT_PLAN.md 5.1, 5.2, 5.7): the stage dumps, dispatch
log, readbacks and step snapshots of runs the chaos floor does not make, because its draft runs have no hero levels
and no recipe calls the gully and planation ops. Made from outside with tests/parity/_hooks.py and
blender_stage_dump.py's StageDumper, as the floor's base runs are; nothing in the Blender branch changes.

    bash run_blender.sh eidoverse/terrain/tests/detail/blender_detail_runs.py -- --run <name> [--pattern 1..5]
                     the base run (no --pattern), or a perturbed one: the chaos floor's protocol (plan C1, 5.4: every
                     op's fields and each kernel's first outputs in a call moved by one ulp, tests/parity/_hooks.py),
                     its step snapshots compared with the base's: p<k>/sample.json, the snapshot floors
                     tests/parity/replay.mjs grades the base's snapshots by
    bash run_blender.sh eidoverse/terrain/tests/parity/blender_stage_dump.py -- --floor \\
        eidoverse/terrain/tests/out/detail/runs/<name>/base/stages --levels all --ops breakup,hydraulic,gully,planation
                     (the stage floors of the same calls, five patterns: tests/detail/replay_test.mjs grades by them)
    (GPU jobs: on a shared machine behind $EIDO_GPU_WRAP)

The runs (seed 1, cache off):
  lauterbrunnen_film   real_place Lauterbrunnen at film quality with the Blender detail package's focus (its
                       lauterbrunnen_truth.focus(): the reference's eye spot and the robot's spot 14 m along the view),
                       its 'detail' variant (blender/tests/terrain/detail/run_real_place.py: the stages dem, breakup and
                       hydraulic), so the hero levels at 4, 2, 1 and 0.5 m each run breakup and hydraulic on the DEM;
                       the port's whole run of the same variant is compared with it (tests/detail/real_place_test.mjs)
  gully_planation      real_place Lauterbrunnen at draft quality with the stages dem, planation and gully on the main
                       level: the two ops no recipe calls, on real ground
  lauterbrunnen_film_full
                       the registered recipe (dem, fluvial, talus, breakup, hydraulic) at film quality with the same
                       focus: the Blender run the port's full variant is judged beside (tests/detail/real_place_test.mjs
                       --variants full, tests/detail/views.mjs). A save only: no hooks, no dumps, no snapshots
Every level's op calls carry their in-call step snapshots (the floor's hooks take them on the main level only), and
the run's terrain is saved (Terrain.save). Writes eidoverse/terrain/tests/out/detail/runs/<name>/base/: run.json,
dispatch_log.jsonl.gz, readbacks.jsonl.gz, kernels.json, snap/, stages/, terrain.npz and terrain.json (a run without
hooks: run.json, terrain.npz and terrain.json).
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'detail', 'runs'))
RUNS = {
    'lauterbrunnen_film': dict(recipe='real_place', params={'dem': 'lauterbrunnen'}, quality='film', focus=True,
                               keep=('dem', 'breakup', 'hydraulic'), extra=(), snap_roles=('main', 'hero')),
    'gully_planation': dict(recipe='real_place', params={'dem': 'lauterbrunnen'}, quality='draft', focus=False,
                            keep=('dem',), extra=({'op': 'planation', 'params': {'tilt_deg': 0.8, 'azimuth_deg': 30.0},
                                                   'levels': 'main', 'where': None},
                                                  {'op': 'gully', 'params': {}, 'levels': 'main', 'where': None}),
                            snap_roles=('main',)),
    'lauterbrunnen_film_full': dict(recipe='real_place', params={'dem': 'lauterbrunnen'}, quality='film', focus=True,
                                    keep=None, extra=(), snap_roles=(), hooks=False),
}


def lauterbrunnen_focus(root):
    """blender/tests/terrain/detail/lauterbrunnen_truth.focus(), read the same way: the reference's eye spot and the
    robot's spot 14 m along the view (1.6 m to the side)."""
    with open(os.path.join(root, 'blender', 'tests', 'terrain', 'reference', 'renders', 'lauterbrunnen_views.json')) as f:
        eye = json.load(f)['eye']
    ex, ey = eye['camera'][:2]
    tx, ty = eye['target'][:2]
    L = math.hypot(tx - ex, ty - ey)
    ux, uy = (tx - ex) / L, (ty - ey) / L
    return [(ex, ey), (ex + 14.0 * ux + 1.6 * uy, ey + 14.0 * uy - 1.6 * ux)]


class EveryLevel:
    """Compares equal to each of a run's chosen levels: the hooks take a call's in-call snapshots where
    `level == main_index`, so this makes them take them on every such level."""

    def __init__(self, levels):
        self.levels = set(int(i) for i in levels)

    def __eq__(self, other):
        return other in self.levels

    def __hash__(self):
        return 0

    def __repr__(self):
        return f'EveryLevel({sorted(self.levels)})'


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--run', required=True, choices=sorted(RUNS))
    ap.add_argument('--pattern', type=int, default=0)
    a = ap.parse_args(B.script_args())
    if a.pattern:
        return perturbed(a)
    spec = RUNS[a.run]
    if not spec.get('hooks', True):
        return plain(a, spec)
    root = B.import_blender_terrain()
    import _hooks as H
    from blender_stage_dump import StageDumper

    class Dumper(StageDumper):
        def start(self, h):
            super().start(h)
            levels = [lv.index for lv in h.run_args['plan'] if lv.role in spec['snap_roles']]
            self.header['snap_levels'] = levels
            self.flush()
            h.main_index = EveryLevel(levels)

    h = H.install()
    from eidoblend.terrain import api as A
    from eidoblend.terrain import recipes as RG
    gpu = h.G.init()
    d = RG.get(spec['recipe']).to_dict()
    d['stages'] = [s for s in d['stages'] if s['op'] in spec['keep']] + [dict(s) for s in spec['extra']]
    pts = lauterbrunnen_focus(root) if spec['focus'] else None
    base = os.path.join(OUT, a.run, 'base')
    os.makedirs(base, exist_ok=True)
    for f in ('done.json', 'failed.json'):
        if os.path.exists(os.path.join(base, f)):
            os.remove(os.path.join(base, f))
    snap = H.SnapStore(os.path.join(base, 'snap'))
    dumper = Dumper(os.path.join(base, 'stages'))
    lines = []
    print(f"[detail runs] {a.run}: {spec['recipe']} {spec['quality']}, stages {[s['op'] for s in d['stages']]}, focus {pts}",
          flush=True)
    h.start(pattern=None, log_dir=base, snap=snap, dumper=dumper, plans=None)
    t0 = time.perf_counter()
    try:
        t = A.generate(d, seed=1, params=dict(spec['params']), focus=pts, quality=spec['quality'], cache=False,
                       log=lambda m: lines.append(str(m)))
    finally:
        h.stop(log_dir=base)
    sec = time.perf_counter() - t0
    t.save(os.path.join(base, 'terrain'))
    rec = dict(run=a.run, recipe=d, params=spec['params'], quality=spec['quality'], focus=[list(p) for p in pts or []],
               seed=1, seconds=round(sec, 2), plan=[lv.to_dict() for lv in t.levels], main_index=t.main.index,
               summary=h.summary(), versions=B.versions(gpu), key=B.source_key(root), log=lines,
               stage_dump_bytes=dumper.bytes, snapshot_bytes=snap.bytes)
    B.write_json(os.path.join(base, 'run.json'), rec)
    B.write_json(os.path.join(base, 'done.json'), dict(seconds=round(sec, 2)))
    print(f'[detail runs] {a.run}: {sec:.1f} s, {h.summary()["dispatches"]} dispatches, stage dumps '
          f'{dumper.bytes / 1e6:.0f} MB, snapshots {snap.bytes / 1e6:.0f} MB -> {base}', flush=True)
    sys.stdout.flush()
    os._exit(0)                      # (sys.exit with GPU textures alive crashed Blender's teardown once: the Blender tests')


def plain(a, spec):
    """A run without the parity hooks: generated as the hooked runs are (api.generate, seed 1, cache off), then saved."""
    root = B.import_blender_terrain()
    from eidoblend.terrain import api as A
    from eidoblend.terrain import recipes as RG
    from eidoblend.terrain.core import gpu as G
    gpu = G.init()
    d = RG.get(spec['recipe']).to_dict()
    if spec['keep'] is not None:
        d['stages'] = [s for s in d['stages'] if s['op'] in spec['keep']]
    d['stages'] += [dict(s) for s in spec['extra']]
    pts = lauterbrunnen_focus(root) if spec['focus'] else None
    base = os.path.join(OUT, a.run, 'base')
    os.makedirs(base, exist_ok=True)
    for f in ('done.json', 'failed.json'):
        if os.path.exists(os.path.join(base, f)):
            os.remove(os.path.join(base, f))
    lines = []
    print(f"[detail runs] {a.run}: {spec['recipe']} {spec['quality']}, stages {[s['op'] for s in d['stages']]}, focus {pts}",
          flush=True)
    t0 = time.perf_counter()
    t = A.generate(d, seed=1, params=dict(spec['params']), focus=pts, quality=spec['quality'], cache=False,
                   log=lambda m: (lines.append(str(m)), print(m, flush=True)))
    sec = time.perf_counter() - t0
    t.save(os.path.join(base, 'terrain'))
    rec = dict(run=a.run, recipe=d, params=spec['params'], quality=spec['quality'], focus=[list(p) for p in pts or []],
               seed=1, seconds=round(sec, 2), plan=[lv.to_dict() for lv in t.levels], main_index=t.main.index,
               versions=B.versions(gpu), key=B.source_key(root), log=lines, hooks=False)
    B.write_json(os.path.join(base, 'run.json'), rec)
    B.write_json(os.path.join(base, 'done.json'), dict(seconds=round(sec, 2)))
    print(f'[detail runs] {a.run}: {sec:.1f} s -> {base}', flush=True)
    sys.stdout.flush()
    os._exit(0)                      # (as main(): Blender's teardown with GPU textures alive)


def perturbed(a):
    """One perturbed run of a base run (blender_chaos_floor.py run_one's perturbed branch, for these runs): the same
    call, the hooks' perturbation of pattern a.pattern, its step snapshots against the base's (every level the base
    snapshotted), and each level's h against the base's save: p<k>/sample.json."""
    import numpy as np
    spec = RUNS[a.run]
    root = B.import_blender_terrain()
    import _hooks as H
    h = H.install()
    from eidoblend.terrain import api as A
    from eidoblend.terrain import recipes as RG
    gpu = h.G.init()
    base = os.path.join(OUT, a.run, 'base')
    if not os.path.exists(os.path.join(base, 'done.json')):
        sys.exit(f'[detail runs] {a.run}: make the base run first')
    brec = B.read_json(os.path.join(base, 'run.json'))
    d = brec['recipe']
    pts = [tuple(p) for p in brec['focus']] or None
    pdir = os.path.join(OUT, a.run, f'p{a.pattern}')
    os.makedirs(pdir, exist_ok=True)
    snap_levels = B.read_json(os.path.join(base, 'stages', 'stages.json'))['snap_levels']

    class NoDump:
        """No stage dumps; its start(), which the hooks call once they have set main_index, takes the snapshots on
        the levels the base took them on."""

        def start(self, hk):
            hk.main_index = EveryLevel(snap_levels)

        def before(self, *x, **k):
            return None

        def where(self, *x, **k):
            pass

        def end_before(self, *x, **k):
            return None

        def flush(self):
            pass
    snap = H.SnapStore(None, base_dir=os.path.join(base, 'snap'))
    t0 = time.perf_counter()
    h.start(pattern=a.pattern, log_dir=pdir, snap=snap, dumper=NoDump(), plans=None)
    try:
        t = A.generate(d, seed=1, params=dict(spec['params']), focus=pts, quality=spec['quality'], cache=False,
                       log=lambda m: None)
    finally:
        snapdiffs = h.stop(log_dir=pdir)
    sec = time.perf_counter() - t0
    sample = dict(pattern=a.pattern, levels=[], snapshots=snapdiffs, seconds=round(sec, 2))
    with np.load(os.path.join(base, 'terrain.npz')) as z:
        for i, lv in enumerate(t.levels):
            hb = np.asarray(z[f'L{i}__f__h'], np.float64)
            hp = np.asarray(t.fields(i)['h'], np.float64)
            r = float(np.ptp(hb)) or 1.0
            dd = hp - hb
            sample['levels'].append(dict(index=i, role=lv.role, cell=lv.cell, rms_over_relief=float(np.sqrt(np.mean(dd * dd)) / r),
                                         p99_abs_over_relief=float(np.percentile(np.abs(dd), 99) / r),
                                         max_abs_m=float(np.abs(dd).max()), bit_identical=bool(np.array_equal(hb, hp))))
    B.write_json(os.path.join(pdir, 'sample.json'), sample)
    B.write_json(os.path.join(pdir, 'done.json'), dict(seconds=round(sec, 2)))
    print(f'[detail runs] {a.run} p{a.pattern}: {sec:.1f} s; ' + ', '.join(
        f"L{x['index']} {x['rms_over_relief']:.2e}" for x in sample['levels']), flush=True)
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main()
