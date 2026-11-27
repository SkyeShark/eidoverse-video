"""The kit's sample pair under its layered material, in the studio: three stills (a GPU job, EEVEE, 960 x 540, 16 samples).

    bash run_blender.sh blender/tests/props_hardsurface/test_stills.py        (after test_kit.py and test_bake.py)

The finished low (out/kit_low.blend) takes materials.layered.baked_material on its bake (out/kit_bake/): the block hard-
anodised aluminium, the pin phosphated steel, worn where knocks go, dusty in the channel; the CC0 photographs it reads are
fetched into the shared library on first use. look.studio's room with its grey and mirror balls; three views into
out/stills/ (three_quarter, channel_close, boss_side). Checks (PASS / FAIL): the material's tables read back, every map
packed, each still written and the asset neither black nor blown (the frame's middle and its highlights). A PASS is not
a look: open the stills. Without the bake it prints SKIP.
"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.look import studio  # noqa: E402
from eidoblend.materials import layered as LY  # noqa: E402

OUT = os.path.join(HERE, 'out')
BAKE = os.path.join(OUT, 'kit_bake')
FAILS = []
SUBS = {1: LY.Substrate((0.026, 0.031, 0.033), (0.70, 0.71, 0.73), 0.46, 0.0, 1.0, 0.30, 1.0, 0.6, 0.8, 0.8, 0, 0.05, 1.3, 0.6),
        5: LY.Substrate((0.048, 0.046, 0.041), (0.50, 0.50, 0.52), 0.66, 0.0, 1.0, 0.36, 0.9, 0.5, 0.6, 0.8, 1, 0.09, 0.8, 0.2)}
VIEWS = {'three_quarter': ((0.06, 0.0, 0.03), (0.16, -0.22, 0.14), 50), 'channel_close': ((0.055, 0.0, 0.058), (0.03, -0.09, 0.08), 60),
         'boss_side': ((0.04, -0.02, 0.03), (-0.03, -0.12, 0.03), 60)}


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def main():
    if not os.path.isfile(os.path.join(BAKE, 'kit_normal.png')):
        print('SKIP no bake in out/kit_bake (run test_kit.py, then test_bake.py)')
        return
    bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, 'kit_low.blend'))
    sc = bpy.context.scene
    parts = [o for o in bpy.data.collections['kit_low'].objects if o.type == 'MESH']
    mat = LY.baked_material('kit.layered', LY.load_bake(BAKE, 'kit'), SUBS, knocks=[('x', 100.0, 120.0)],
                            hands=[((0, -25, 0), (60, 25, 65), 6.0)], stains=[([('x', 110.0, 120.0)], 0.5)])
    for o in parts:
        o.data.materials.clear()
        o.data.materials.append(mat)
    t0 = bpy.data.images['kit.layered_table_0']
    px = np.empty(64, np.float32)
    t0.pixels.foreach_get(px)
    check(abs(px[4] - SUBS[1].base[0]) < 3e-3 and abs(px[20] - SUBS[5].base[0]) < 3e-3, 'the substrate tables read back (rows 1 and 5)')
    check(all(i.packed_file for i in bpy.data.images if i.name.startswith('kit_')), 'every bake map packed into the file')
    shoot = studio.studio(sc, balls_at=(0.135, -0.02, 0.02), ball_r=0.012, samples=16)
    os.makedirs(os.path.join(OUT, 'stills'), exist_ok=True)
    for nm, (c, p, lens) in VIEWS.items():
        path = shoot(os.path.join(OUT, 'stills', f'{nm}.png'), c, p, lens=lens, res=(960, 540), reach=0.4)
        ok = os.path.isfile(path)
        if ok:
            im = bpy.data.images.load(path)
            a = np.empty(len(im.pixels), np.float32)
            im.pixels.foreach_get(a)
            a = a.reshape(im.size[1], im.size[0], 4)[..., :3]
            mid = a[im.size[1] // 4: 3 * im.size[1] // 4, im.size[0] // 4: 3 * im.size[0] // 4]
            hot = float((a.max(axis=2) >= 250 / 255).mean())
            check(0.03 < float(mid.mean()) < 0.85 and hot < 0.02, f'{nm}: written; the middle\'s mean {mid.mean():.3f}, highlights {hot * 100:.2f} %')
            bpy.data.images.remove(im)
        else:
            check(False, f'{nm}: not written')
    print(f'[stills] {len(FAILS)} FAIL' if FAILS else '[stills] all checks passed')


if __name__ == '__main__':
    try:
        main()
    except Exception:                                           # noqa: BLE001
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)
