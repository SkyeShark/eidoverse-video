"""eidoblend.sets.desert.make: the desert made from nothing, step by step (stdlib; run it with the Python that has numpy,
scipy and Pillow, which the plain-Python steps need):

    python blender/eidoblend/sets/desert/make.py --work work/desert [--quality film|draft] [--town 840x300 | --plain 840x300]
        [--from sources|mask|land|mesh|look] [--to ...] [--renders DIR] [--res 960x540] [--samples 16]

  sources  Blender  cli.py sources: the three terrain recipes (film: about 2 minutes on a laptop GPU and 2.5 GB of
                    terrain cache; draft: seconds)
  mask     Blender  cli.py mask: the town's footprint and track ends (the town built at --town, default 840x300), or a
                    plain rectangle (--plain)
  land     Python   land.py: the composed rasters (film grid: 1, 4 and 16 m; draft: 4, 16 and 64 m)
  mesh     Python   mesh.py: the quadtree mesh (film: 2 m cells round the town, about 2.6 M faces; draft: 8 m)
  look     Blender  cli.py look: <work>/desert.blend (a build output: never commit it), and the views with --renders
Blender steps run through run_blender.sh, after $EIDO_GPU_WRAP's words when it is set. Exit code 1 when a step fails.
"""
import os
import shlex
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
STEPS = ('sources', 'mask', 'land', 'mesh', 'look')


def run(cmd):
    print('[desert make]', ' '.join(cmd), flush=True)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=REPO)
    print(f'[desert make] exit {r.returncode} in {time.time() - t0:.1f} s', flush=True)
    return r.returncode


def blender(script, *args):
    return shlex.split(os.environ.get('EIDO_GPU_WRAP', '')) + ['bash', os.path.join(REPO, 'run_blender.sh'), script] + list(args)


def main(a):
    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    work = os.path.abspath(opt('--work', os.path.join(REPO, 'work', 'desert')))
    q = opt('--quality', 'film')
    first, last = STEPS.index(opt('--from', 'sources')), STEPS.index(opt('--to', 'look'))
    cli = os.path.join(HERE, 'cli.py')
    py = os.environ.get('PYTHON') or sys.executable
    plan = {
        'sources': blender(cli, 'sources', '--work', work, '--quality', q),
        'mask': blender(cli, 'mask', '--work', work, *(('--plain', opt('--plain')) if opt('--plain') else ('--town', opt('--town', '840x300')))),
        'land': [py, os.path.join(HERE, 'land.py'), '--work', work, '--grid', 'film' if q == 'film' else 'draft'],
        'mesh': [py, os.path.join(HERE, 'mesh.py'), '--work', work] + (['--k', '0.0016', '--max-level', '10'] if q == 'film' else ['--k', '0.004', '--max-level', '8']),
        'look': blender(cli, 'look', '--work', work, '--out', os.path.join(work, 'desert.blend'),
                        *(('--renders', opt('--renders'), '--res', opt('--res', '960x540'), '--samples', opt('--samples', '16'))
                          if opt('--renders') else ()),
                        *(('--town', opt('--town', '840x300')) if opt('--renders') and not opt('--plain') else ())),
    }
    for s in STEPS[first:last + 1]:
        if run(plan[s]) != 0:
            print(f'[desert make] the {s} step failed', flush=True)
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
