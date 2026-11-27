"""The carbine's high and low built from their tables, and the low prepared for its bake (Blender on the CPU).

    bash run_blender.sh blender/tests/props_carbine/test_build.py [--size 2048] [--cells 512]       (~5 min)

Builds out/carbine_high.blend and out/carbine_low_raw.blend (eidoblend.props.carbine.cli high / low) and runs the prep
into out/carbine_low.blend and out/bake/ at a test's size (a 2048 set, a 512-cell pack: the full make uses 4096 and 1024).
Checks (PASS / FAIL): 64 parts in each, the same names; every high part closed; the high's evaluated triangles near
499 k, the low's near 21 k once finished; the carbine's own space (x from the butt at -178.5 mm to the flash hider at
582); the receivers' edge groups (several bevel widths); the finished low all triangles, its UVs inside the square,
the pack's fill, the bake's inputs written with the 13 substrates.
"""
import json
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.props.carbine import cli  # noqa: E402
from eidoblend.props.hardsurface import masses as hs  # noqa: E402

OUT = os.path.join(HERE, 'out')
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SIZE = ARGS[ARGS.index('--size') + 1] if '--size' in ARGS else '2048'
CELLS = ARGS[ARGS.index('--cells') + 1] if '--cells' in ARGS else '512'
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def main():
    os.makedirs(OUT, exist_ok=True)
    high, raw, low, bake = (os.path.join(OUT, n) for n in ('carbine_high.blend', 'carbine_low_raw.blend', 'carbine_low.blend', 'bake'))
    cli.cmd_high(['high', '--out', high])
    rep = list(hs.REPORT)
    parts = cli.parts_of('carbine_high')
    check(len(parts) == 64, f'the high: {len(parts)} parts (64)')
    check(all(r[1] == 0 for r in rep), f'every high part closed (open: {[r[0] for r in rep if r[1]]})')
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for o in parts:
        em = o.evaluated_get(dg).to_mesh()
        em.calc_loop_triangles()
        tris += len(em.loop_triangles)
        o.evaluated_get(dg).to_mesh_clear()
    check(480_000 < tris < 520_000, f'the high: {tris:,} triangles evaluated (about 499 k)')
    xs = np.concatenate([np.array([v.co.x for v in o.data.vertices]) for o in parts]) * 1000.0
    check(abs(xs.min() + 178.5) < 0.6 and abs(xs.max() - 582.0) < 0.6, f'its space: x {xs.min():.1f} .. {xs.max():.1f} mm (butt -178.5, muzzle 582)')
    up = next(o for o in parts if o.name == 'upper_receiver')
    w = np.zeros(len(up.data.edges), np.float32)
    up.data.attributes['bevel_weight_edge'].data.foreach_get('value', w)
    check(len(np.unique(np.round(w[w > 0], 2))) > 5, 'the upper receiver\'s edges rounded by group (machined, forged, fillets)')
    names = [o.name for o in parts]
    cli.cmd_high(['low', '--out', raw], low=True)
    lparts = cli.parts_of('carbine_low')
    check([o.name for o in lparts] == names, 'the low holds the high\'s 64 parts by name')
    check(all(not o.modifiers for o in lparts), 'the low has no bevels (its bake carries them)')
    cli.cmd_prep(['prep', '--high', high, '--low', raw, '--bake', bake, '--out', low, '--size', SIZE, '--cells', CELLS])
    lparts = cli.parts_of('carbine_low')
    ltris = sum(len(o.data.polygons) for o in lparts)
    check(all(len(p.vertices) == 3 for o in lparts for p in o.data.polygons) and 18_000 < ltris < 24_000,
          f'the finished low: {ltris:,} triangles, triangles only (about 21 k)')
    uv = np.concatenate([np.array([d.uv[:] for d in o.data.uv_layers['UVMap'].data]) for o in lparts])
    check(uv.min() >= -1e-6 and uv.max() <= 1 + 1e-6, 'every UV inside the square')
    meta = json.load(open(os.path.join(bake, 'carbine.json'), encoding='utf-8'))
    least = 0.5 if int(CELLS) >= 1024 else 0.25                # (58 % at 1024 cells; the 512 cells' coarser grid ~30 %)
    check(meta['uv_fill'] > least, f'the pack fills {meta["uv_fill"] * 100:.1f} % of the square at {CELLS} cells (over {least * 100:.0f} %)')
    check(sorted(set(meta['substrate'].values())) == list(range(1, 14)), 'the bake\'s inputs carry the 13 substrates')
    print(f'[carbine build] {len(FAILS)} FAIL' if FAILS else '[carbine build] all checks passed')


if __name__ == '__main__':
    try:
        main()
    except Exception:                                           # noqa: BLE001
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)
