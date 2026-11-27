"""The carbine's bake: its decals drawn, the high baked onto the low on the GPU, its markings and grip relief laid in.

    python blender/tests/props_carbine/test_bake.py [--device cpu]          (after test_build.py; a GPU job, ~30 s)

decals.py into out/decals/, then blender/tools/gpu_bake.py on out/bake/ with the carbine's layers (layers.py). Checks
(PASS / FAIL): the decals (the grip panel 16-bit, the rail's and the selector's lettering); under 4 % of the samples
missed (the bores the carbine hides); the normal map, both mask sets, the ID map, the markings (ink on the rail's
lands and the receiver's flats) and the grip's relief (the chequering's cut share) written. Proofs stay in out/bake/
(carbine_coverage.png, carbine_layout.png). Without warp-lang, or without CUDA unless --device cpu, it prints SKIP.
"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import _where  # noqa: E402

OUT = os.path.join(HERE, 'out')
BAKE = os.path.join(OUT, 'bake')
CARBINE = _where.REPO / 'blender' / 'eidoblend' / 'props' / 'carbine'
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def main():
    device = sys.argv[sys.argv.index('--device') + 1] if '--device' in sys.argv else 'auto'
    rc = subprocess.run([sys.executable, str(CARBINE / 'decals.py'), '--out', os.path.join(OUT, 'decals')]).returncode
    check(rc == 0 and os.path.isfile(os.path.join(OUT, 'decals', 'decals.json')), 'decals.py drew the pictures')
    import numpy as np
    from PIL import Image
    gp = Image.open(os.path.join(OUT, 'decals', 'grip_panel.png'))
    check(gp.mode in ('I;16', 'I') and gp.size == (1525, 1700), f'the grip panel: a 16-bit height picture at 0.04 mm ({gp.mode} {gp.size})')
    ink = float((np.asarray(Image.open(os.path.join(OUT, 'decals', 'rail_left.png'))) > 128).mean())
    check(0.005 < ink < 0.08, f'the rail\'s numbers drawn ({ink * 100:.2f} % ink)')
    if importlib.util.find_spec('warp') is None:
        print('SKIP warp-lang is not installed (pip install warp-lang): no bake')
        return 1 if FAILS else 0
    if device == 'auto':
        r = subprocess.run([sys.executable, '-c', 'import warp as wp; wp.config.quiet = True; wp.init(); print(wp.get_cuda_device_count())'],
                           capture_output=True, text=True)
        if not r.stdout.strip().splitlines() or int(r.stdout.strip().splitlines()[-1]) == 0:
            print('SKIP no CUDA device (run with --device cpu to bake on the CPU)')
            return 1 if FAILS else 0
    if not os.path.isfile(os.path.join(BAKE, 'carbine.json')):
        print('FAIL out/bake/carbine.json is missing: run test_build.py first')
        return 1
    rc = subprocess.run([sys.executable, str(_where.REPO / 'blender' / 'tools' / 'gpu_bake.py'), '--bake', BAKE, '--name', 'carbine', '--device', device,
                         '--layers', str(CARBINE / 'layers.py'), '--layers-dir', os.path.join(OUT, 'decals')]).returncode
    check(rc == 0, f'gpu_bake.py exited {rc}')
    if rc:
        return 1
    rep = json.load(open(os.path.join(BAKE, 'carbine_report.json'), encoding='utf-8'))
    check(rep['miss_share'] < 0.04, f'{rep["miss_share"] * 100:.2f} % of the samples found no high (under 4 %: hidden bores)')
    for k in ('normal', 'masks_a', 'masks_b', 'id', 'marks', 'relief'):
        check(os.path.isfile(os.path.join(BAKE, f'carbine_{k}.png')), f'carbine_{k}.png written')
    marks = np.asarray(Image.open(os.path.join(BAKE, 'carbine_marks.png')))
    relief = np.asarray(Image.open(os.path.join(BAKE, 'carbine_relief.png')))
    # (0.12 % of a 4096 set packed at 1024 cells, 59 % fill; about half that at the test's 512-cell pack)
    check(0.0002 < (marks > 128).mean() < 0.05, f'the markings laid in ({(marks > 128).mean() * 100:.3f} % of the set)')
    check((relief > 64).mean() > 0.0005, f'the grip\'s relief laid in ({(relief > 64).mean() * 100:.3f} % of the set cut)')
    print(f'[carbine bake] {len(FAILS)} FAIL' if FAILS else f'[carbine bake] all checks passed ({rep["device"]}, {rep["bake_seconds"]} s)')
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
