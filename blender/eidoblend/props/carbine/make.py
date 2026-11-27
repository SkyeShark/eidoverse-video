"""eidoblend.props.carbine.make: the carbine made from nothing, step by step (plain Python, stdlib only).

    python blender/eidoblend/props/carbine/make.py [--out work/props/carbine] [--size 4096] [--cells 1024] [--ss 2]
        [--from high] [--to look] [--stills] [--condition wear=1.2,dust=0.8] [--device auto|cuda|cpu]

STEPS, in order (--from / --to pick a run of them):
    decals  the drawn pictures at real size                <out>/decals/              (Pillow)
    high    the high, 64 parts, about 499 k triangles       <out>/carbine_high.blend   (Blender, ~10 s)
    low     the low from the same tables                    <out>/carbine_low_raw.blend
    prep    the low finished and packed, the bake's inputs  <out>/carbine_low.blend, <out>/bake/   (Blender; ~12 min
            at 1024 cells, ~5 at 512; 256 cells cannot hold its 1,009 islands)
    bake    every ray on the GPU                            <out>/bake/carbine_*.png   (warp-lang; ~45 s on a CUDA GPU)
    look    the layered material, every image packed        <out>/carbine.blend        (Blender; fetches its CC0 sets)
    stills  (--stills) three views in look.studio's room    <out>/stills/
Without warp-lang the chain stops before the bake and says so (exit 3); on a machine without CUDA, Warp bakes on the
CPU (--device cpu), more slowly. EIDO_GPU_WRAP queues every step (hardsurface.chain).
"""

from __future__ import annotations

import argparse
import os
import sys

if __package__ in (None, ''):                                  # run as a file: the package from its folder
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
    from eidoblend.props.hardsurface import chain
else:
    from ..hardsurface import chain

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = ('decals', 'high', 'low', 'prep', 'bake', 'look', 'stills')
DEFAULT_OUT = os.path.join(chain.REPO, 'work', 'props', 'carbine')


def make(out=DEFAULT_OUT, size=4096, cells=1024, ss=2, first='decals', last='look', stills=False, condition=None,
         device='auto', log=print) -> int:
    """Run the chain from `first` to `last` (and the stills); returns 0, a step's exit code, or 3 (no warp-lang)."""
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    cli = os.path.join(HERE, 'cli.py')
    p = {k: os.path.join(out, v) for k, v in (('high', 'carbine_high.blend'), ('raw', 'carbine_low_raw.blend'),
                                              ('low', 'carbine_low.blend'), ('bake', 'bake'), ('decals', 'decals'),
                                              ('look', 'carbine.blend'), ('stills', 'stills'))}
    todo = list(STEPS[STEPS.index(first):STEPS.index(last) + 1])
    if stills and 'stills' not in todo:
        todo.append('stills')
    for step in todo:
        if step == 'decals':
            rc = chain.python(os.path.join(HERE, 'decals.py'), '--out', p['decals'], log=log, wrap=False)
        elif step == 'high':
            rc = chain.blender(cli, 'high', '--out', p['high'], log=log)
        elif step == 'low':
            rc = chain.blender(cli, 'low', '--out', p['raw'], log=log)
        elif step == 'prep':
            rc = chain.blender(cli, 'prep', '--high', p['high'], '--low', p['raw'], '--bake', p['bake'], '--out', p['low'],
                               '--size', str(size), '--cells', str(cells), log=log)
        elif step == 'bake':
            if not chain.has_warp():
                log('[carbine make] SKIP the bake and the look: warp-lang is not installed (pip install warp-lang)')
                return 3
            rc = chain.python(os.path.join(chain.REPO, 'blender', 'tools', 'gpu_bake.py'), '--bake', p['bake'], '--name', 'carbine',
                              '--ss', str(ss), '--device', device, '--layers', os.path.join(HERE, 'layers.py'),
                              '--layers-dir', p['decals'], log=log)
        elif step == 'look':
            rc = chain.blender(cli, 'look', '--low', p['low'], '--bake', p['bake'], '--out', p['look'],
                               *(['--condition', condition] if condition else []), log=log)
        else:
            rc = chain.blender(cli, 'stills', '--blend', p['look'], '--out', p['stills'], log=log)
        if rc != 0:
            log(f'[carbine make] the step {step} exited {rc}')
            return rc
    log(f'[carbine make] done: {p["look"] if "look" in todo else out}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='make the carbine (see the module doc)')
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--size', type=int, default=4096)
    ap.add_argument('--cells', type=int, default=1024)
    ap.add_argument('--ss', type=int, default=2)
    ap.add_argument('--from', dest='first', default='decals', choices=STEPS[:-1])
    ap.add_argument('--to', dest='last', default='look', choices=STEPS[:-1])
    ap.add_argument('--stills', action='store_true')
    ap.add_argument('--condition', default=None)
    ap.add_argument('--device', default='auto')
    a = ap.parse_args(argv)
    return make(a.out, a.size, a.cells, a.ss, a.first, a.last, a.stills, a.condition, a.device)


if __name__ == '__main__':
    sys.exit(main())
