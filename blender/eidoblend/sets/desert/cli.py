"""eidoblend.sets.desert.cli: the desert's Blender steps from the command line, each its own Blender run.

    bash run_blender.sh blender/eidoblend/sets/desert/cli.py sources --work work/desert [--quality film|draft] [--no-cache]
    bash run_blender.sh blender/eidoblend/sets/desert/cli.py mask --work work/desert [--town 840x300 | --plain 840x300]
    bash run_blender.sh blender/eidoblend/sets/desert/cli.py look --work work/desert [--out work/desert/desert.blend]
        [--renders DIR] [--town 840x300] [--res 960x540] [--samples 16] [--only NAME,NAME]

sources runs the terrain recipes (sources.simulate); mask writes the town's footprint (sources.town_mask: the town
built with eidoblend.sets.town at that extent, seed 7, no CC0 things) or a plain rectangle (--plain); look builds the
collection 'desert' from <work>/build (look.build) and saves it (a build output: never commit it), and with --renders
shoots look.views() into DIR, the town built beside it at its extent when --town is given, under the town's light.
make.py runs the whole chain with the plain-Python steps (land.py, mesh.py) between. Exit code 1 when a step fails.
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
import bpy  # noqa: E402

from eidoblend import common  # noqa: E402


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def extent(s):
    return tuple(float(v) for v in s.split('x'))


def main():
    a = common.script_args()
    cmd = a[0] if a else ''
    work = os.path.abspath(opt(a, '--work', os.path.join(common.REPO, 'work', 'desert')))
    t0 = time.time()
    if cmd == 'sources':
        from eidoblend.sets.desert import sources
        q = opt(a, '--quality', 'film')
        only = opt(a, '--only')
        sources.simulate(work, quality=q, cache='--no-cache' not in a, only=only.split(',') if only else None)
    elif cmd == 'mask':
        from eidoblend.sets.desert import sources
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if '--plain' in a:
            sources.plain_mask(work, extent(opt(a, '--plain')))
        else:
            from eidoblend.sets import town
            T = town.build(extent=extent(opt(a, '--town', '840x300')), things=False, masks=False, air=False, yard_trees='built')
            sources.town_mask(T.collection, work)
    elif cmd == 'look':
        from eidoblend.sets.desert import look
        bpy.ops.wm.read_factory_settings(use_empty=True)
        D = look.build(work)
        out = opt(a, '--out')
        if out:
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True)
            print(f'[desert] saved {out}: {os.path.getsize(os.path.abspath(out)) // 1024} KB', flush=True)
        if opt(a, '--renders'):
            look.shoot(D, opt(a, '--renders'), town=extent(opt(a, '--town')) if opt(a, '--town') else None,
                       res=tuple(int(v) for v in opt(a, '--res', '960x540').split('x')), samples=int(opt(a, '--samples', '16')),
                       only=opt(a, '--only'))
    else:
        print(__doc__)
        raise SystemExit(2)
    print(f'[desert] {cmd} done in {time.time() - t0:.1f} s', flush=True)


if __name__ == '__main__':
    code = 0
    try:
        main()
    except SystemExit as e:
        code = int(e.code or 0)
    except Exception:
        import traceback
        traceback.print_exc()
        code = 1
    sys.stdout.flush()
    os._exit(code)                       # (no Python teardown after the GPU module's work)
