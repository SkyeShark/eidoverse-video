"""The carbine's look on its bakes, delivered and seen: three stills (a GPU job, EEVEE, 960 x 540, 16 samples).

    bash run_blender.sh blender/tests/props_carbine/test_look.py            (after test_build.py and test_bake.py)

eidoblend.props.carbine.cli look on out/carbine_low.blend and out/bake/ writes out/carbine.blend (its CC0 grain
photographs fetched into the shared library on first use), then the made file is appended the way a scene takes it
(props.build('carbine', blend=...)) and shot in look.studio's room into out/stills/: left_three_quarter,
receiver_left_close, top_left_0p6m (the receiver's top and left side from 0.6 m, the closest a film is likely to hold it).
Checks (PASS / FAIL): the delivered file has the collection 'carbine', 64 parts at identity, every one triangulated with
its UVMap and a material, every image packed; the registry's build appends it under carbine_root; each still written and
neither black nor blown. A PASS is not a look: open the stills. They carry the test's bake (1.8 px/mm against make.py's
4.9), so the selector's lettering reads soft here; judge the lettering on make.py's file. Without the bake it prints SKIP.
"""
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend import props  # noqa: E402
from eidoblend.look import studio  # noqa: E402
from eidoblend.props.carbine import cli  # noqa: E402
from eidoblend.props.hardsurface import masses as hs  # noqa: E402

OUT = os.path.join(HERE, 'out')
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def main():
    bake = os.path.join(OUT, 'bake')
    if not os.path.isfile(os.path.join(bake, 'carbine_normal.png')):
        print('SKIP no bake in out/bake (run test_build.py, then test_bake.py)')
        return
    look = os.path.join(OUT, 'carbine.blend')
    cli.cmd_look(['look', '--low', os.path.join(OUT, 'carbine_low.blend'), '--bake', bake, '--out', look])
    parts = cli.parts_of('carbine')
    check(len(parts) == 64 and all(o.matrix_world == Matrix.Identity(4) for o in parts), f'the delivered collection: {len(parts)} parts at identity')
    check(all('UVMap' in o.data.uv_layers and o.data.materials and o.data.materials[0] for o in parts), 'every part has its UVMap and a material')
    check(all(len(p.vertices) == 3 for o in parts for p in o.data.polygons), 'every part triangulated (the bake\'s tangents hold)')
    check(all(i.packed_file or i.source == 'GENERATED' for i in bpy.data.images), 'every image packed (the file renders on its own)')
    hs.new_file()
    rifle = props.build('carbine', blend=look)
    check(rifle.group.name == 'carbine_root' and len(rifle.parts) == 64, 'props.build(\'carbine\') appends it under carbine_root')
    shoot = studio.studio(bpy.context.scene, balls_at=(0.30, 0.09, -0.16), ball_r=0.02, samples=16)
    os.makedirs(os.path.join(OUT, 'stills'), exist_ok=True)
    for nm, (c, p, lens) in cli.VIEWS.items():
        path = shoot(os.path.join(OUT, 'stills', f'{nm}.png'), c, p, lens=lens, res=(960, 540))
        im = bpy.data.images.load(path)
        a = np.empty(len(im.pixels), np.float32)
        im.pixels.foreach_get(a)
        a = a.reshape(im.size[1], im.size[0], 4)[..., :3]
        hot = float((a.max(axis=2) >= 250 / 255).mean())
        check(0.02 < float(a.mean()) < 0.8 and hot < 0.02, f'{nm}: written; mean {a.mean():.3f}, highlights {hot * 100:.2f} %')
        bpy.data.images.remove(im)
    rifle.dispose()
    check(not [o for o in bpy.data.objects if o.name.startswith(('upper_receiver', 'carbine_root'))], 'dispose() removes what build() appended')
    print(f'[carbine look] {len(FAILS)} FAIL' if FAILS else '[carbine look] all checks passed')


if __name__ == '__main__':
    try:
        main()
    except Exception:                                           # noqa: BLE001
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)
