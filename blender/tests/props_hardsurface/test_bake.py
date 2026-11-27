"""The GPU baker on the kit's sample pair (system Python with numpy, scipy, Pillow and warp-lang; a GPU job).

    python blender/tests/props_hardsurface/test_bake.py [--device cpu]        (after test_kit.py; ~30 s with CUDA)

Bakes out/kit_bake/ (test_kit.py's inputs: the block and its pin, high onto low, 1024 px) with blender/tools/gpu_bake.py
and checks (PASS / FAIL): the ray conventions proved, nearly every sample found its high, the flats bake flat (the
normal map's blue near 1 where the low and the high agree), the bevelled arrises bake tilted, the channel's floor and the
boss's root darker in the AO than the open top, the edge map bright along the arrises only, the corner map in the inside
corners, the ID map holds the two substrates. The maps and proofs stay in out/kit_bake/ (kit_coverage.png,
kit_layout.png): look at them. Without warp-lang, or without CUDA unless --device cpu, it prints SKIP.
"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import _where  # noqa: E402

BAKE = os.path.join(HERE, 'out', 'kit_bake')
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def main():
    device = sys.argv[sys.argv.index('--device') + 1] if '--device' in sys.argv else 'auto'
    if importlib.util.find_spec('warp') is None:
        print('SKIP warp-lang is not installed (pip install warp-lang): no bake')
        return 0
    if device == 'auto':
        r = subprocess.run([sys.executable, '-c', 'import warp as wp; wp.config.quiet = True; wp.init(); print(wp.get_cuda_device_count())'],
                           capture_output=True, text=True)
        if not r.stdout.strip().splitlines() or int(r.stdout.strip().splitlines()[-1]) == 0:
            print('SKIP no CUDA device (run with --device cpu to bake on the CPU)')
            return 0
    if not os.path.isfile(os.path.join(BAKE, 'kit.json')):
        print('FAIL out/kit_bake/kit.json is missing: run test_kit.py first')
        return 1
    rc = subprocess.run([sys.executable, str(_where.REPO / 'blender' / 'tools' / 'gpu_bake.py'), '--bake', BAKE, '--name', 'kit',
                         '--device', device]).returncode
    check(rc == 0, f'gpu_bake.py exited {rc}')
    if rc:
        return 1
    import numpy as np
    from PIL import Image
    rep = json.load(open(os.path.join(BAKE, 'kit_report.json'), encoding='utf-8'))
    check(rep['miss_share'] < 0.01, f'{rep["miss_share"] * 100:.3f} % of the samples found no high (under 1 %)')
    check(rep['normal_z_below_0.1'] < 0.001 * rep['texels'], f'normals facing away: {rep["normal_z_below_0.1"]} texels')

    def img(k):
        a = np.asarray(Image.open(os.path.join(BAKE, f'kit_{k}.png'))).astype(np.float64)
        return a / (65535.0 if a.max() > 255 else 255.0)
    nm, ma, mb, idm = img('normal'), img('masks_a'), img('masks_b'), np.asarray(Image.open(os.path.join(BAKE, 'kit_id.png')))
    cover = np.asarray(Image.open(os.path.join(BAKE, 'kit_coverage.png')).resize((nm.shape[1], nm.shape[0]), Image.NEAREST))
    on = (cover[..., 1] > 150) & (cover[..., 0] < 100)              # the proof's green: baked
    flat = on & (nm[..., 2] > 0.99)
    check(flat.mean() / max(on.mean(), 1e-9) > 0.5, f'the flats bake flat: {flat.sum() / max(on.sum(), 1) * 100:.1f} % of the baked texels at blue > 0.99')
    tilt = on & (nm[..., 2] < 0.9)
    check(0.002 < tilt.sum() / max(on.sum(), 1) < 0.3, f'the bevels bake tilted: {tilt.sum() / max(on.sum(), 1) * 100:.1f} % of the texels lean over 25 degrees')
    ao = ma[..., 0][on]
    check(ao.max() > 0.95 and np.percentile(ao, 2) < 0.75, f'AO: open places near 1 (max {ao.max():.2f}), the channel and the boss\'s root darker (p2 {np.percentile(ao, 2):.2f})')
    edge = mb[..., 0][on]
    check(edge.max() > 0.9 and np.median(edge) < 0.3, f'the edge map bright on the arrises only (max {edge.max():.2f}, median {np.median(edge):.2f})')
    corner = mb[..., 2][on]
    check(corner.max() > 0.8, f'the corner map finds the inside corners (max {corner.max():.2f})')
    ids = sorted(set(np.unique(idm[on[:idm.shape[0], :idm.shape[1]]]).tolist()))
    check(ids == [16, 80], f'the ID map holds the two substrates (block 1, pin 5): {ids}')
    print(f'[bake] {len(FAILS)} FAIL' if FAILS else f'[bake] all checks passed ({rep["device"]}, {rep["bake_seconds"]} s)')
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
