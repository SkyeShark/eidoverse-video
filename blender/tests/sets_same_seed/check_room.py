"""check_room.py: a made SAME SEED room's delivered file, checked through the public API (Blender, renders nothing).
test_rooms.py runs it after make.py; on its own:

    bash run_blender.sh blender/tests/sets_same_seed/check_room.py <room> <out folder>

It appends the room into an empty scene with sets.build('same_seed.<room>', blend=..., render=True) and checks: the
room's collection, world and render settings arrive; it has lights, a volume probe and a sphere probe; every mesh has a
material and none is still a build clay; every low has its 'atlas' UV and its baked maps are on disk; every picture
the file reads exists; the marks and the cameras' aims lie inside the room; the root carries everything (moving it
moves the parts, mark() follows); dispose() removes it all. PASS / FAIL lines.
"""
import importlib
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))       # <repo>/blender
from eidoblend import sets  # noqa: E402

FAILS = []
CLAYS = ('clay', 'clay_dark', 'clay_glass', 'houseplant_clay')


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    room, out = a[0], os.path.abspath(a[1])
    mod = sets.get(f'same_seed.{room}')
    blend = os.path.join(out, f'{room}.blend')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    r = sets.build(f'same_seed.{room}', blend=blend, render=True)
    check(f'{room}: appended', r.group is not None and len(r.parts) > 20, f'{len(r.parts)} meshes, {len(r.lights)} lights, {len(r.probes)} probes')
    check(f'{room}: its world is the scene\'s', sc.world is not None and sc.world.name == mod.WORLD, sc.world.name if sc.world else 'none')
    check(f'{room}: its render settings', sc.eevee.taa_render_samples == mod.RENDER.get('samples', 16)
          and all(getattr(sc.eevee, k) == v for k, v in mod.RENDER.items() if hasattr(sc.eevee, k) and not isinstance(v, dict)),
          f'{sc.eevee.taa_render_samples} samples, Fast GI {sc.eevee.fast_gi_method}, exposure {sc.view_settings.exposure:.2f}')
    kinds = {p.data.type for p in r.probes}
    probed = hasattr(importlib.import_module(f'eidoblend.sets.same_seed.{room}.look'), 'finish')   # (the sealed room's bounce is lamps)
    check(f'{room}: lights' + (' and probes' if probed else ''), len(r.lights) >= 1 and (not probed or {'VOLUME', 'SPHERE'} <= kinds),
          f'{len(r.lights)} lights, probes {sorted(kinds)}')
    # every mesh dressed: a material in every slot, none a build clay (the desk's night backdrop keeps its own 'desk.' one)
    bare, clay = [], []
    for o in r.parts:
        mats = [s.material for s in o.material_slots]
        if not mats or any(m is None for m in mats):
            bare.append(o.name)
        for m in mats:
            if m is not None and (m.name.split('.')[0] in CLAYS or (m.name.startswith('desk.') and 'night_outside' not in m.name)):
                clay.append(f'{o.name}:{m.name}')
    check(f'{room}: every mesh has its material', not bare, ', '.join(bare[:6]))
    check(f'{room}: no build clay left', not clay, ', '.join(clay[:6]))
    # the lows: their atlas UV and their baked maps
    lows = [o for o in r.parts if o.name.split('.')[0].endswith('_low')]
    no_uv = [o.name for o in lows if 'atlas' not in o.data.uv_layers]
    atlases = sorted({o.get('atlas') for o in lows if o.get('atlas')})
    maps = ('normal', 'masks_a', 'masks_b') if 'bake' in mod.STEPS else ('normal', 'ao', 'cavity', 'curv')
    missing = [f'{at}_{k}.png' for at in atlases for k in maps if not os.path.isfile(os.path.join(out, 'bake', f'{at}_{k}.png'))]
    check(f'{room}: lows and their bakes', lows and not no_uv and atlases and not missing,
          f'{len(lows)} lows in atlases {atlases}' + (f'; no atlas UV: {no_uv[:4]}' if no_uv else '') + (f'; missing {missing[:4]}' if missing else ''))
    # every picture the file reads is on disk (the shared library's sets, the bake, the prints, the HDRIs)
    gone = []
    for im in bpy.data.images:
        if im.source == 'FILE' and im.packed_file is None and im.filepath:
            if not os.path.isfile(bpy.path.abspath(im.filepath, library=im.library)):
                gone.append(im.filepath)
    check(f'{room}: every picture it reads exists', not gone, ', '.join(gone[:4]))
    # the marks and the cameras' aims inside the room (its floor's plan, from its parts' bounds)
    floor = next((o for o in r.parts if o.name.split('.')[0] == 'room_floor'), None)
    if floor is not None:
        bpy.context.view_layer.update()
        pts = [floor.matrix_world @ Vector(c) for c in floor.bound_box]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        inside = lambda p: lo.x <= p[0] <= hi.x and lo.y <= p[1] <= hi.y and -0.01 <= p[2] <= 3.2      # noqa: E731
        bad_marks = [k for k, m in mod.MARKS.items() if not inside(m['pos'])]
        bad_aims = [k for k, (pos, aim, lens) in mod.CAMS.items() if not inside(aim)]
        check(f'{room}: marks and camera aims inside the room', not bad_marks and not bad_aims,
              f'{len(mod.MARKS)} marks, {len(mod.CAMS)} cameras' + (f'; outside: {bad_marks + bad_aims}' if bad_marks or bad_aims else ''))
    # the root carries the room
    part = r.parts[0]
    before = part.matrix_world.translation.copy()
    mark0 = r.mark('stand').copy()
    r.group.location = (10.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    moved = (part.matrix_world.translation - before).length
    check(f'{room}: the root carries it', abs(moved - 10.0) < 1e-4 and abs((r.mark('stand') - mark0).x - 10.0) < 1e-4, f'a part moved {moved:.4f} m')
    cam = r.make_camera(next(iter(mod.CAMS)))
    check(f'{room}: make_camera', cam.type == 'CAMERA' and cam.parent is r.group)
    r.dispose()
    left = [o.name for o in bpy.data.objects if o.users_collection]
    check(f'{room}: dispose', mod.COLLECTION not in bpy.data.collections and not left, ', '.join(left[:4]))
    print(f'[check_room] {room}: {len(FAILS)} FAIL', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)
