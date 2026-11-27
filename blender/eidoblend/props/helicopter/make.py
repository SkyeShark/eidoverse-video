"""eidoblend.props.helicopter.make: the helicopter made from nothing, step by step (plain Python, stdlib only).

    python blender/eidoblend/props/helicopter/make.py [--out work/props/helicopter] [--from high] [--to look] [--stills]
        [--views left_front_above,left_front_below,nose_left] [--res 960x540] [--samples 16]

STEPS, in order (--from / --to pick a run of them):
    decals  rivets, seams, fasteners and stencils    <out>/decals/                 (Pillow)
    high    the measured high                         <out>/helicopter_high.blend  (Blender)
    look    the vertex masks and every material       <out>/helicopter.blend       (Blender; the masks' rays take minutes)
    stills  (--stills) views in daylight              <out>/stills/
EIDO_GPU_WRAP queues every Blender step (hardsurface.chain).
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
STEPS = ('decals', 'high', 'look', 'stills')
DEFAULT_OUT = os.path.join(chain.REPO, 'work', 'props', 'helicopter')


def make(out=DEFAULT_OUT, first='decals', last='look', stills=False, views=None, res='960x540', samples=16, log=print) -> int:
    """Run the chain from `first` to `last` (and the stills); returns 0 or the failing step's exit code."""
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    cli = os.path.join(HERE, 'cli.py')
    p = {'decals': os.path.join(out, 'decals'), 'high': os.path.join(out, 'helicopter_high.blend'),
         'look': os.path.join(out, 'helicopter.blend'), 'stills': os.path.join(out, 'stills')}
    todo = list(STEPS[STEPS.index(first):STEPS.index(last) + 1])
    if stills and 'stills' not in todo:
        todo.append('stills')
    for step in todo:
        if step == 'decals':
            rc = chain.python(os.path.join(HERE, 'decals.py'), '--out', p['decals'], log=log, wrap=False)
        elif step == 'high':
            rc = chain.blender(cli, 'high', '--out', p['high'], log=log)
        elif step == 'look':
            rc = chain.blender(cli, 'look', '--high', p['high'], '--decals', p['decals'], '--out', p['look'], log=log)
        else:
            rc = chain.blender(cli, 'stills', '--blend', p['look'], '--out', p['stills'], '--res', res, '--samples', str(samples),
                               *(['--views', views] if views else []), log=log)
        if rc != 0:
            log(f'[helicopter make] the step {step} exited {rc}')
            return rc
    log(f'[helicopter make] done: {p["look"]}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='make the helicopter (see the module doc)')
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--from', dest='first', default='decals', choices=STEPS[:-1])
    ap.add_argument('--to', dest='last', default='look', choices=STEPS[:-1])
    ap.add_argument('--stills', action='store_true')
    ap.add_argument('--views', default=None)
    ap.add_argument('--res', default='960x540')
    ap.add_argument('--samples', type=int, default=16)
    a = ap.parse_args(argv)
    return make(a.out, a.first, a.last, a.stills, a.views, a.res, a.samples)


if __name__ == '__main__':
    sys.exit(main())
