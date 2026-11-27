"""eidoblend.props.helicopter.cli: the helicopter's Blender steps from the command line, each its own Blender run.

    bash run_blender.sh blender/eidoblend/props/helicopter/cli.py high --out work/props/helicopter/helicopter_high.blend
        [--parts hull,top,tail,rotor,gear,cabin,doors,fit]
    bash run_blender.sh blender/eidoblend/props/helicopter/cli.py look --high work/props/helicopter/helicopter_high.blend \
        --decals work/props/helicopter/decals --out work/props/helicopter/helicopter.blend
    bash run_blender.sh blender/eidoblend/props/helicopter/cli.py stills --blend work/props/helicopter/helicopter.blend \
        --out work/props/helicopter/stills [--views left_front_above,left_front_below,nose_left] [--res 960x540] [--samples 16]

make.py runs them in order (with decals.py first). look writes the delivered file: the collection 'helicopter' (the
high's parts with their masks and materials, every picture packed; the Empties 'main_rotor' and 'tail_rotor' turn the
rotors) in the aircraft's space (metres: x aft of the mast, y right, z up from the cabin floor; the origin on the mast's
line at the floor). stills renders the named views (VIEWS: camera position and aim in the aircraft's space, metres) in a
daylight of a sun and a pale sky, EEVEE. Exit code 1 when a step fails.
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import common  # noqa: E402
from eidoblend.props.hardsurface import masses as hs  # noqa: E402
from eidoblend.props.helicopter import high, look as LOOK  # noqa: E402

NAME = 'helicopter'
# camera position, aim (metres, the aircraft's space), lens (mm), the sun's direction (toward the sun)
VIEWS = {
    'left_front_above': ((3.997, -6.600, 1.859), (0.189, -0.800, 0.787), 30, (-0.4, -0.7, 0.6)),    # the door from above and behind it
    'left_front_below': ((7.161, -9.100, -2.132), (0.181, -0.700, 0.687), 55, (-0.4, -0.7, 0.6)),   # the side and the nose from below
    'nose_left': ((-10.5, -4.4, 1.0), (-2.9, 0.0, 0.75), 38, (-0.4, -0.7, 0.6)),
    'left_rear': ((10.7, -9.2, 1.4), (1.2, 0.0, 0.85), 48, (0.3, -0.7, 0.65)),
    'open_door': ((-0.5, -5.6, 1.6), (0.1, 0.0, 0.7), 35, (-0.4, -0.7, 0.6)),
}


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def save(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path))


def cmd_high(a):
    hs.new_file()
    parts = tuple((opt(a, '--parts') or ','.join(high.PARTS)).split(','))
    high.build(parts)
    save(opt(a, '--out'))
    print(f'[helicopter] high saved: {opt(a, "--out")}')


def cmd_look(a):
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(opt(a, '--high')))
    col = bpy.data.collections['helicopter_high']
    LOOK.apply(col, os.path.abspath(opt(a, '--decals')))
    col.name = NAME
    out = os.path.abspath(opt(a, '--out'))
    save(out)
    bpy.ops.wm.open_mainfile(filepath=out)                     # (taken in fresh: every picture packed)
    bad = [i.name for i in bpy.data.images if not i.packed_file and i.source != 'GENERATED']
    if bad:
        raise RuntimeError(f'pictures not packed: {bad}')
    c = bpy.data.collections[NAME]
    print(f'[helicopter] look saved: {out} ({sum(1 for o in c.objects if o.type == "MESH")} parts, '
          f'{sum(len(o.data.polygons) for o in c.objects if o.type == "MESH"):,} faces)')


def daylight(sc, samples):
    from eidoblend.look import studio
    studio.eevee(sc, samples)
    w = bpy.data.worlds.new('daylight')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.62, 0.66, 0.72, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
    sc.world = w
    sun = bpy.data.objects.new('daylight_sun', bpy.data.lights.new('daylight_sun', 'SUN'))
    sun.data.energy, sun.data.color, sun.data.angle = 4.0, (1.0, 0.93, 0.8), math.radians(1.5)
    sc.collection.objects.link(sun)
    cd = bpy.data.cameras.new('daylight_camera')
    cd.clip_start, cd.clip_end = 0.05, 500
    cam = bpy.data.objects.new('daylight_camera', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sun, cam


def cmd_stills(a):
    from eidoblend.props import helicopter
    hs.new_file()
    sc = bpy.context.scene
    helicopter.build(blend=os.path.abspath(opt(a, '--blend')))
    sun, cam = daylight(sc, int(opt(a, '--samples', 16)))
    out = os.path.abspath(opt(a, '--out'))
    os.makedirs(out, exist_ok=True)
    rx, ry = (int(v) for v in opt(a, '--res', '960x540').split('x'))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
    for nm in (opt(a, '--views') or 'left_front_above,left_front_below,nose_left').split(','):
        pos, aim, lens, light = VIEWS[nm]
        cam.location = Vector(pos)
        cam.rotation_euler = (Vector(aim) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        sun.rotation_euler = Vector(light).to_track_quat('Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, f'{nm}.png')
        bpy.ops.render.render(write_still=True)
        print(f'[helicopter] still {nm}')


def main(a):
    t0 = time.time()
    cmd = a[0] if a else ''
    if cmd == 'high':
        cmd_high(a)
    elif cmd == 'look':
        cmd_look(a)
    elif cmd == 'stills':
        cmd_stills(a)
    else:
        raise SystemExit(__doc__)
    print(f'[helicopter] {cmd}: {time.time() - t0:.1f} s')


if __name__ == '__main__':
    try:
        main(common.script_args())
        sys.stdout.flush()
        os._exit(0)
    except BaseException:                                       # noqa: BLE001
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
