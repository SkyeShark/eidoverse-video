"""The glacial carve's stage floor with the jump flood's candidates left whole (PORT_PLAN.md 5.3, 5.4): the floor of
the coarsest level's carve call of each alpine_valley floor run, measured as tests/parity/blender_stage_dump.py
--floor measures every stage floor (its own replay_one and _diffs, the five patterns, both perturbation points of
5.4), except that the jump flood's images are not moved by the in-op nudge. Run in Blender (GPU):

    bash run_blender.sh eidoverse/terrain/tests/glacial/carve_floor.py -- [--runs alpine_valley_s1,alpine_valley_s2]
        [--patterns 5] [--calls 5]          (a GPU job: on a shared machine behind $EIDO_GPU_WRAP)

Why: jump_flood.glsl's images (candT / outC) hold the four best seeds' packed cell indices i + j n as floats (-1
none), exact integers that the kernels read back with int(). The in-op nudge moves a value one float32 ulp up or down,
and int(122.99999) is 122: the neighbouring cell's index, another seed or a cell that is no seed, not a rounding of
the same one. On the small V valley's carve (tests/glacial/glacial_expected.py, numpy's twin device), the floor of h
with every nudge of 5.4 is 32 % of its range; with the same nudges but the jump flood's images left whole, 3.8e-7.
The stage floor tests/parity's tool records for this call (stage_floors.json) keeps that nudge, so it measures the
corruption, not the carve's rounding: the replay (tests/glacial/replay_test.mjs) grades the carve calls by this
floor, and names both.

Writes tests/out/glacial/carve_floors.json: {format, protocol, exempt, runs: {run: {call: entry}}}, each entry as a
stage_floors.json entry (call, level, pass_index, n, op, replay_bit_identical, floor: per field max_over_range,
rms_over_range, p99_over_range and the samples).
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', 'parity')))
import _blender as B  # noqa: E402
import _hooks as H  # noqa: E402
import blender_stage_dump as SD  # noqa: E402

EXEMPT = {'jump_flood': "its images (candT, outC) hold packed cell indices as floats, read back with int(): a one-ulp "
                        "nudge makes another seed's index, not a rounding of the same one"}


def exempt_nudges():
    """Hooks.on_dispatch with the in-op nudge of the EXEMPT kernels' images left out (their draws still taken, so
    nothing else moves)."""
    on0 = H.Hooks.on_dispatch

    def on_dispatch(self, k, *a, **kw):
        if getattr(k, 'name', None) not in EXEMPT:
            return on0(self, k, *a, **kw)
        nudge0 = H.nudge

        def keep(arr, rng):
            rng.random(np.shape(arr))
            return np.asarray(arr, np.float32)
        H.nudge = keep
        try:
            return on0(self, k, *a, **kw)
        finally:
            H.nudge = nudge0
    H.Hooks.on_dispatch = on_dispatch


def main():
    args = B.script_args()
    opt = lambda n, d: args[args.index(n) + 1] if n in args else d  # noqa: E731
    runs = opt('--runs', 'alpine_valley_s1,alpine_valley_s2').split(',')
    patterns = int(opt('--patterns', '5'))
    calls = {int(c) for c in opt('--calls', '').split(',') if c}
    key = os.environ.get('EIDO_PARITY_KEY') or 'blender_f90c6fc_11d0dd93fa'
    out_path = os.path.normpath(os.path.join(HERE, '..', 'out', 'glacial', 'carve_floors.json'))
    out = B.read_json(out_path) or {}
    out.update(format=1, key=key, protocol='5.4 as tests/parity/blender_stage_dump.py --floor, the in-op nudge '
                                           'leaving the EXEMPT kernels\' images whole', exempt=EXEMPT)
    out.setdefault('runs', {})
    B.import_blender_terrain()
    h = H.install()
    exempt_nudges()
    out['versions'] = B.versions(h.G.init())
    for run in runs:
        stages_dir = os.path.join(B.parity_root(), key, f'{run}_draft', 'base', 'stages')
        header = B.read_json(os.path.join(stages_dir, 'stages.json'))
        if header is None:
            print(f'[carve-floor] {run}: no stage dumps under {key}', flush=True)
            continue
        ent_run = out['runs'].setdefault(run, {})
        for rec in header['stages']:
            c = rec.get('context') or {}
            carve = rec['op'] == 'glacial' and c.get('role') == 'grow' and c.get('prepass') is None
            if (calls and rec['call'] not in calls) or (not calls and not carve):
                continue
            with np.load(os.path.join(stages_dir, rec['after'])) as z:
                want_after = {k: z[k] for k in z.files if not k.startswith('shared__')}
            t0 = time.perf_counter()
            base = SD.replay_one(h, header, rec, stages_dir, None)
            secs = round(time.perf_counter() - t0, 2)
            rd = SD._diffs(base, want_after)
            same = all(isinstance(v, list) and v[3] for v in rd.values())
            samples = [SD._diffs(SD.replay_one(h, header, rec, stages_dir, p), base) for p in range(1, patterns + 1)]
            fl = {}
            for name in base:
                vals = [s.get(name) for s in samples if isinstance(s.get(name), list)]
                if vals:
                    fl[name] = dict(max_over_range=max(v[0] for v in vals), rms_over_range=max(v[1] for v in vals),
                                    p99_over_range=max(v[2] for v in vals), samples=[[v[0], v[1], v[2]] for v in vals])
            ent_run[str(rec['call'])] = dict(call=rec['call'], level=rec['level'], pass_index=rec['pass_index'],
                                             n=rec['n'], op=rec['op'], replay_seconds=secs, replay_bit_identical=same,
                                             patterns=patterns, floor=fl)
            B.write_json(out_path, out)
            print(f"[carve-floor] {run} L{rec['level']} {rec['op']} (call {rec['call']}): replay "
                  f"{'bit-identical' if same else 'DIFFERS'}, h floor {fl.get('h', {}).get('max_over_range', float('nan')):.3g} "
                  f"max / range, {fl.get('h', {}).get('rms_over_range', float('nan')):.3g} RMS ({secs} s a replay)", flush=True)
    B.write_json(out_path, out)
    print(f'[carve-floor] {out_path}', flush=True)


if __name__ == '__main__':
    main()
