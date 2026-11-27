"""eidoblend.sets.same_seed.make: a SAME SEED room made from nothing, step by step (plain Python, stdlib only).

    python blender/eidoblend/sets/same_seed/make.py <room> [--out work/sets/same_seed/<room>] [--from high] [--to look]
        [--stills] [--cams a,b] [--res 960x540] [--samples 16] [--ss 2] [--device auto|cuda|cpu] [--size 4096] [--quick]
        [--<look option> v]
    python blender/eidoblend/sets/same_seed/make.py --list          # the rooms and their steps

--size and --quick reach a lows step that bakes in Blender itself (the kitchen's: its atlases' size, a tenth of the
samples for a preview).

The rooms: sealed_room, kitchen, lab, desk. STEPS, in order (--from / --to pick a run of them):
    high    the parts as built                          <out>/<room>_high.blend     (Blender)
    lows    lows, UVs and the bake's inputs             <out>/<room>_lows.blend, <out>/bake/   (Blender)
    bake    every ray on the GPU, atlas by atlas        <out>/bake/<atlas>_*.png    (blender/tools/gpu_bake.py:
                                                        warp-lang; on the CPU without CUDA)
    prints  the room's drawn pictures                   <out>/prints/               (Pillow; the rooms that have them)
    look    CC0 sets and models, layered materials, the light, the probes   <out>/<room>.blend   (Blender; fetches its
                                                        CC0 IDs into the shared library on first use)
    stills  (--stills) the room's cameras               <out>/stills/<room>_<cam>.png
Without warp-lang the chain stops before the bake and says so (exit 3). EIDO_GPU_WRAP queues every step
(eidoblend.props.hardsurface.chain); exit 75 from it means "busy, try again later" and is handed back as it is.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

if __package__ in (None, ''):                                  # run as a file: the package from its folder
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
    from eidoblend.props.hardsurface import chain
    from eidoblend.sets.same_seed import ROOMS, info
else:
    from ...props.hardsurface import chain
    from . import ROOMS, info

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = ('high', 'lows', 'bake', 'prints', 'look', 'stills')


def default_out(room):
    return os.path.join(chain.REPO, 'work', 'sets', 'same_seed', room)


def make(room, out=None, first='high', last='look', stills=False, cams=None, res='960x540', samples=None, ss=2,
         device='auto', look=None, log=print, size=None, quick=False) -> int:
    """Run the room's chain from `first` to `last` (and the stills); returns 0, a step's exit code, or 3 (no
    warp-lang). look: {option: value} for the room's look (e.g. {'tube': 14}); size / quick: for a lows step that
    bakes in Blender (the kitchen's)."""
    out = os.path.abspath(out or default_out(room))
    os.makedirs(out, exist_ok=True)
    meta = info(room)
    cli = os.path.join(HERE, 'cli.py')
    todo = [s for s in STEPS[STEPS.index(first):STEPS.index(last) + 1] if s in meta['steps'] or s == 'stills']
    if stills and 'stills' not in todo:
        todo.append('stills')
    if not stills and last != 'stills':
        todo = [s for s in todo if s != 'stills']
    for step in todo:
        if step in ('high', 'lows'):
            extra = (['--size', str(size)] if size else []) + (['--quick'] if quick else []) if step == 'lows' else []
            rc = chain.blender(cli, room, step, '--dir', out, *extra, log=log)
        elif step == 'bake':
            if not chain.has_warp():
                log('[same_seed make] SKIP the bake and the look: warp-lang is not installed (pip install warp-lang)')
                return 3
            with open(os.path.join(out, 'bake', 'atlases.json'), encoding='utf-8') as f:
                atlases = json.load(f)
            rc = 0
            for a in atlases:
                rc = chain.python(os.path.join(chain.REPO, 'blender', 'tools', 'gpu_bake.py'), '--bake', os.path.join(out, 'bake'),
                                  '--name', a['name'], '--ss', str(ss), '--ao', str(a.get('ao', 96)), '--cav', str(a.get('cav', 48)),
                                  '--device', device, log=log)
                if rc != 0:
                    break
        elif step == 'prints':
            rc = chain.python(os.path.join(HERE, room, 'prints.py'), '--out', os.path.join(out, 'prints'), log=log, wrap=False)
        elif step == 'look':
            extra = []
            for k, v in (look or {}).items():
                extra += [f'--{k}', str(v)]
            rc = chain.blender(cli, room, 'look', '--dir', out, *extra, log=log)
        else:
            extra = ['--res', res] + (['--cams', cams] if cams else []) + (['--samples', str(samples)] if samples else [])
            rc = chain.blender(cli, room, 'stills', '--dir', out, *extra, log=log)
        if rc != 0:
            log(f'[same_seed make] {room}: the step {step} exited {rc}')
            return rc
    log(f'[same_seed make] {room}: done: {os.path.join(out, room + ".blend")}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='make a SAME SEED room (see the module doc)')
    ap.add_argument('room', nargs='?', choices=ROOMS)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--out', default=None)
    ap.add_argument('--from', dest='first', default='high', choices=STEPS)
    ap.add_argument('--to', dest='last', default='look', choices=STEPS)
    ap.add_argument('--stills', action='store_true')
    ap.add_argument('--cams', default=None)
    ap.add_argument('--res', default='960x540')
    ap.add_argument('--samples', type=int, default=None)
    ap.add_argument('--ss', type=int, default=2)
    ap.add_argument('--device', default='auto')
    ap.add_argument('--size', type=int, default=None)
    ap.add_argument('--quick', action='store_true')
    a, rest = ap.parse_known_args(argv)
    if a.list or not a.room:
        for r in ROOMS:
            m = info(r)
            print(f'{r:12s} {", ".join(m["steps"])}: {m["about"]}')
        return 0
    look = {}
    it = iter(rest)
    for k in it:
        if k.startswith('--'):
            look[k[2:]] = next(it, '')
    return make(a.room, a.out, a.first, a.last, a.stills, a.cams, a.res, a.samples, a.ss, a.device, look, size=a.size, quick=a.quick)


if __name__ == '__main__':
    sys.exit(main())
