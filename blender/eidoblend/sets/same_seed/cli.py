"""eidoblend.sets.same_seed.cli: a SAME SEED room's Blender steps from the command line, each its own Blender run.

    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py <room> high  --dir <out>
    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py <room> lows  --dir <out> [--size 4096] [--quick]
    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py <room> look  --dir <out> [--<option> value ...]
    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py <room> stills --dir <out> [--cams a,b] [--res 960x540]
        [--samples 16] [--clay]

make.py runs them in order, with the GPU bake (blender/tools/gpu_bake.py) after lows and the room's pictures
(<room>/prints.py) before look. The files, in <out>:
    high    <room>_high.blend    the room's parts as built (highs), the bench's drawn lows beside their highs
    lows    <room>_lows.blend    the parts a lens comes close to as LOWS (UV 'atlas'), the rest as built;
            bake/<atlas>_low.npz, _high.npz, .json and bake/atlases.json: what the GPU baker reads
    look    <room>.blend         the delivered room: collection <room> (parts, lights, probes), its world, its render
                                 settings; its pictures read by path from the shared library and <out>
    stills  stills/<room>_<cam>.png from the delivered file (EEVEE; the room's own settings at --samples)
A look option (--tube 14, --watts 150 ...) is passed to the room's look.apply() as a number. Exit code 1 when a step
fails.
"""

import importlib
import inspect
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
import bpy  # noqa: E402

from eidoblend.sets.same_seed import look as L  # noqa: E402


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def open_file(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f'{path} is not made yet (run the step before it)')
    bpy.ops.wm.open_mainfile(filepath=path)
    return bpy.context.scene


def step_look(mod, d, a):
    look = importlib.import_module(f'{mod.__name__}.look')
    sc = open_file(os.path.join(d, f'{mod.NAME}_lows.blend'))
    room = bpy.data.collections[mod.COLLECTION]
    lib = L.Library(os.path.join(os.path.dirname(mod.__file__), 'cc0.json'))
    opts = dict(getattr(mod, 'LOOK', {}))
    opts.update({k[2:].replace('-', '_'): num(v) for k, v in a.items() if k.startswith('--') and k not in ('--dir',)})
    if 'prints' in mod.STEPS:
        opts['prints_dir'] = os.path.join(d, 'prints')
    res = look.apply(room, os.path.join(d, 'bake'), lib, **opts)
    sc.world = res['world']
    L.eevee(sc, **mod.RENDER)
    if hasattr(look, 'finish'):
        look.finish(room, sc, res)                           # the room's probes, baked over the finished room
    for o in list(sc.objects):
        if o.type == 'CAMERA':
            bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        if c.name.endswith('_tmp') and not c.objects:
            bpy.data.collections.remove(c)
    path = L.save(os.path.join(d, f'{mod.NAME}.blend'))
    parts = [o for o in room.all_objects if o.type == 'MESH']
    L.log('look', f'{mod.NAME}: {len(parts)} meshes, {len([o for o in room.all_objects if o.type == "LIGHT"])} lights, '
                  f'{len(res["materials"])} of its own materials -> {path}')


def step_stills(mod, d, a):
    sc = open_file(os.path.join(d, f'{mod.NAME}.blend'))
    names = [c for c in str(a.get('--cams', ','.join(mod.CAMS))).split(',') if c]
    res = tuple(int(v) for v in str(a.get('--res', '960x540')).lower().split('x'))
    samples = int(a.get('--samples', mod.RENDER.get('samples', 16)))
    L.eevee(sc, **dict(mod.RENDER, samples=samples, resolution=res))
    out = os.path.join(d, 'stills')
    os.makedirs(out, exist_ok=True)
    tmp = bpy.data.collections.new('stills_cams')
    sc.collection.children.link(tmp)
    if '--clay' in a:                                        # the forms alone: every part one grey
        clay = bpy.data.materials.new('clay_still')
        clay.use_nodes = True
        clay.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.36, 0.36, 0.36, 1)
        for o in bpy.data.collections[mod.COLLECTION].all_objects:
            if o.type == 'MESH' and not o.get('eido_loaded_asset'):
                L.assign(o, clay)
    for n in names:
        pos, aim, lens = mod.CAMS[n]
        cam = L.camera(f'still_{n}', pos, aim, lens, tmp)
        L.shoot(sc, cam, os.path.join(out, f'{mod.NAME}_{n}{"_clay" if "--clay" in a else ""}.png'))


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if len(a) < 2:
        print(__doc__)
        return 2
    name, step = a[0], a[1]
    opts = L.args(['--'] + a[2:])
    d = os.path.abspath(opts.get('--dir') or os.path.join(os.getcwd(), 'work', 'sets', 'same_seed', name))
    os.makedirs(d, exist_ok=True)
    mod = importlib.import_module(f'eidoblend.sets.same_seed.{name}')
    t0 = time.time()
    if step == 'high':
        importlib.import_module(f'eidoblend.sets.same_seed.{name}.high').main(d)
    elif step == 'lows':
        lows = importlib.import_module(f'eidoblend.sets.same_seed.{name}.lows')
        params = inspect.signature(lows.main).parameters             # (a lows step that bakes in Blender takes these)
        kw = {}
        if '--size' in opts and 'size' in params:
            kw['size'] = int(opts['--size'])
        if '--quick' in opts and 'quick' in params:
            kw['quick'] = True
        lows.main(d, **kw)
    elif step == 'look':
        step_look(mod, d, opts)
    elif step == 'stills':
        step_stills(mod, d, opts)
    else:
        print(f'[same_seed cli] unknown step {step!r} (high, lows, look, stills)')
        return 2
    L.log('cli', f'{name} {step}: done in {time.time() - t0:.0f} s')
    return 0


if __name__ == '__main__':
    try:
        rc = main()
    except Exception:                                          # noqa: BLE001
        traceback.print_exc()
        rc = 1
    sys.stdout.flush()
    os._exit(rc)
