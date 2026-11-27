"""eidoblend.props.carbine.cli: the carbine's Blender steps from the command line, each its own Blender run.

    bash run_blender.sh blender/eidoblend/props/carbine/cli.py high --out work/carbine/carbine_high.blend
    bash run_blender.sh blender/eidoblend/props/carbine/cli.py low --out work/carbine/carbine_low_raw.blend
    bash run_blender.sh blender/eidoblend/props/carbine/cli.py prep --high work/carbine/carbine_high.blend \
        --low work/carbine/carbine_low_raw.blend --bake work/carbine/bake --out work/carbine/carbine_low.blend \
        [--size 4096] [--cells 1024] [--high-only]
    python blender/tools/gpu_bake.py --bake work/carbine/bake --name carbine \
        --layers blender/eidoblend/props/carbine/layers.py --layers-dir work/carbine/decals
    bash run_blender.sh blender/eidoblend/props/carbine/cli.py look --low work/carbine/carbine_low.blend \
        --bake work/carbine/bake --out work/carbine/carbine.blend [--condition wear=1.2,dust=0.8]
    bash run_blender.sh blender/eidoblend/props/carbine/cli.py stills --blend work/carbine/carbine.blend \
        --out work/carbine/stills [--res 960x540] [--samples 16]

make.py runs them in order (with decals.py before them). prep finishes the low (lowpoly.prepare_low: its normals,
seams, one texel density, the pack: about 12 minutes at 1024 cells, its 1,009 islands on 58 % of the set; --cells 512
about 5 minutes and 30 %, for a preview; 256 cells cannot hold them) and writes the bake's inputs; --high-only rewrites
the high's inputs alone (a change to the high: the low and its pack stand). look writes the delivered file: the
collection 'carbine' (the low's 64 parts, every part at identity in the carbine's space, +X to the muzzle, the origin
on the bore at the receiver's rear face) with its material and every image packed. stills renders three views in
look.studio's room (EEVEE). Exit code 1 when a step fails.
"""

import os
import sys
import time
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
import bpy  # noqa: E402

from eidoblend import common  # noqa: E402
from eidoblend.props.carbine import high, look as LOOK  # noqa: E402
from eidoblend.props.hardsurface import bake_export, lowpoly, masses as hs  # noqa: E402

NAME = 'carbine'
VIEWS = {   # (centre, camera offset, lens): metres in the carbine's space
    'left_three_quarter': ((0.20, 0.0, -0.03), (0.35, 1.15, 0.45), 50),
    'receiver_left_close': ((0.10, 0.0, -0.03), (0.06, 0.40, 0.14), 60),
    'top_left_0p6m': ((0.10, 0.0, -0.03), (0.36, 0.176, 0.448), 45),
}


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def parts_of(col_name):
    c = bpy.data.collections.get(col_name)
    if c is None:
        raise RuntimeError(f'no collection {col_name!r} in {bpy.data.filepath}')
    return sorted((o for o in c.objects if o.type == 'MESH'), key=lambda o: o.name)


def save(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path))


def cmd_high(a, low=False):
    hs.new_file()
    high.build(low=low)
    save(opt(a, '--out'))
    print(f'[carbine] {"low" if low else "high"} saved: {opt(a, "--out")}')


def cmd_prep(a):
    bake = os.path.abspath(opt(a, '--bake'))
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(opt(a, '--high')))
    bake_export.write_high(parts_of('carbine_high'), bake, NAME)
    if '--high-only' in a:
        return
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(opt(a, '--low')))
    parts = parts_of('carbine_low')
    lowpoly.prepare_low(parts, sharp_deg=40.0, hide_dir=(0.0, -0.45, -0.89), hidden_scale=0.2, cells=int(opt(a, '--cells', 1024)))
    for o in parts:
        o['substrate'] = LOOK.substrate(o.name)
    bake_export.write_low(parts, bake, NAME, size=int(opt(a, '--size', 4096)), substrate=LOOK.substrate, ids=LOOK.IDS,
                          options={'ao_mm': 30.0, 'cav_mm': 2.0, 'edge_mm': 4.0, 'corner_mm': 8.0})
    for o in parts:
        o.data.materials.clear()
    save(opt(a, '--out'))


def cmd_look(a):
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(opt(a, '--low')))
    cond = {}
    for kv in (opt(a, '--condition', '') or '').split(','):
        if '=' in kv:
            k, v = kv.split('=')
            cond[k.strip()] = float(v)
    parts = parts_of('carbine_low')
    LOOK.apply(parts, os.path.abspath(opt(a, '--bake')), NAME, condition=cond or None)
    bpy.data.collections['carbine_low'].name = NAME
    out = os.path.abspath(opt(a, '--out'))
    save(out)
    bpy.ops.wm.open_mainfile(filepath=out)                     # (taken in fresh: every image packed, every part at identity)
    bad = [i.name for i in bpy.data.images if not i.packed_file and i.source != 'GENERATED']
    tris = sum(len(o.data.polygons) for o in parts_of(NAME))
    if bad:
        raise RuntimeError(f'images not packed: {bad}')
    print(f'[carbine] look saved: {out} ({len(parts_of(NAME))} parts, {tris:,} triangles, every image packed)')


def cmd_stills(a):
    from eidoblend.look import studio
    from eidoblend.props import carbine
    hs.new_file()
    sc = bpy.context.scene
    h = carbine.build(blend=os.path.abspath(opt(a, '--blend')))
    out = os.path.abspath(opt(a, '--out'))
    os.makedirs(out, exist_ok=True)
    rx, ry = (int(v) for v in (opt(a, '--res', '960x540')).split('x'))
    shoot = studio.studio(sc, balls_at=(0.30, 0.09, -0.16), ball_r=0.02, samples=int(opt(a, '--samples', 16)))
    for nm, (c, p, lens) in VIEWS.items():
        if opt(a, '--only') and opt(a, '--only') not in nm:
            continue
        shoot(os.path.join(out, f'{nm}.png'), c, p, lens=lens, res=(rx, ry))
        print(f'[carbine] still {nm}')
    h.dispose()


def main(a):
    t0 = time.time()
    cmd = a[0] if a else ''
    if cmd == 'high':
        cmd_high(a)
    elif cmd == 'low':
        cmd_high(a, low=True)
    elif cmd == 'prep':
        cmd_prep(a)
    elif cmd == 'look':
        cmd_look(a)
    elif cmd == 'stills':
        cmd_stills(a)
    else:
        raise SystemExit(__doc__)
    print(f'[carbine] {cmd}: {time.time() - t0:.1f} s')


if __name__ == '__main__':
    try:
        main(common.script_args())
        sys.stdout.flush()
        os._exit(0)
    except BaseException:                                       # noqa: BLE001
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
