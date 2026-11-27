"""The helicopter built, given its masks and materials, and its rotors keyed (Blender on the CPU, ~3 min).

    bash run_blender.sh blender/tests/props_helicopter/test_build.py           (after test_decals.py)

eidoblend.props.helicopter.cli high into out/helicopter_high.blend, then look (the vertex masks' rays, then every
material, the pictures of out/decals/ packed) into out/helicopter.blend; then the made file appended as a scene takes it
(props.build('helicopter', blend=...)) and its rotors keyed over two seconds. Checks (PASS / FAIL): 290 parts, none open;
the Empties main_rotor and tail_rotor carry the turning parts (the hub, the four blades each); the blades carry their
'blade' chord and span; every part's vertices carry 'masks'; every slot has a material of the look, the exhaust ducts and
shields the airframe's paint; every picture packed; spin keys LINEAR rotations of 258 and 1190 rpm.
"""
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend import props  # noqa: E402
from eidoblend.props.hardsurface import masses as hs  # noqa: E402
from eidoblend.props.helicopter import cli  # noqa: E402

OUT = os.path.join(HERE, 'out')
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def main():
    decals = os.path.join(OUT, 'decals')
    if not os.path.isfile(os.path.join(decals, 'skin_side.png')):
        print('FAIL out/decals is missing: run test_decals.py first')
        FAILS.append('decals')
        return
    high, look = os.path.join(OUT, 'helicopter_high.blend'), os.path.join(OUT, 'helicopter.blend')
    cli.cmd_high(['high', '--out', high])
    col = bpy.data.collections['helicopter_high']
    parts = [o for o in col.objects if o.type == 'MESH']
    check(len(parts) == 290 and not [r for r in hs.REPORT if r[1]], f'{len(parts)} parts (290), none open-edged')
    mr, tr = col.objects.get('main_rotor'), col.objects.get('tail_rotor')
    kids = lambda e: [o.name for o in col.objects if o.parent is e]       # noqa: E731
    check(mr is not None and {'hub_barrel', 'main_blade_0', 'main_blade_3'} <= set(kids(mr)), 'main_rotor carries the hub and the four blades')
    check(tr is not None and {'tail_rotor_hub', 'tail_blade_0', 'tail_blade_3'} <= set(kids(tr)), 'tail_rotor carries its hub and blades')
    bl = col.objects['main_blade_0'].data.color_attributes.get('blade')
    check(bl is not None, 'the blades carry their chord and span (\'blade\')')
    cli.cmd_look(['look', '--high', high, '--decals', decals, '--out', look])
    c = bpy.data.collections['helicopter']
    parts = [o for o in c.objects if o.type == 'MESH']
    check(all(o.data.color_attributes.get('masks') is not None for o in parts), 'every part carries its masks')
    check(all(m is not None and m.name.startswith('helicopter.') for o in parts for m in o.data.materials), 'every slot has a material of the look')
    check(all(m.name == 'helicopter.paint' for nm in ('exhaust_duct_l', 'exhaust_shield_r') for m in c.objects[nm].data.materials),
          'the exhaust ducts and shields wear the airframe\'s paint')
    check(all(i.packed_file or i.source == 'GENERATED' for i in bpy.data.images), 'every picture packed')
    hs.new_file()
    heli = props.build('helicopter', blend=look)
    turns = heli.spin(1, 49, fps=24.0)
    sc = bpy.context.scene
    sc.frame_set(49)
    a = heli.main_rotor.rotation_euler[2]
    check(abs(a - 2 * math.pi * 258.0 / 60.0 * 2.0) < 1e-3, f'spin: the main rotor turns {turns[0][1]} times in 2 s (258 rpm)')
    fc = heli.main_rotor.animation_data.action
    from bpy_extras.anim_utils import action_get_channelbag_for_slot
    cb = action_get_channelbag_for_slot(fc, heli.main_rotor.animation_data.action_slot)
    check(all(k.interpolation == 'LINEAR' for f in cb.fcurves for k in f.keyframe_points), 'spin: LINEAR keys')
    check(heli.tail_rotor is not None and abs(heli.tail_rotor.rotation_euler[1] - 2 * math.pi * 1190.0 / 60.0 * 2.0) < 1e-3, 'spin: the tail rotor at 1190 rpm')
    heli.dispose()
    print(f'[helicopter build] {len(FAILS)} FAIL' if FAILS else '[helicopter build] all checks passed')


if __name__ == '__main__':
    try:
        main()
    except Exception:                                           # noqa: BLE001
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)
