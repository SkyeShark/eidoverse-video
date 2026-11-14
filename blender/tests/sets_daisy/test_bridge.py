"""tests/sets_daisy/test_bridge.py: the Golden Gate in fog (eidoverse/sets/funeral/bridge.js) on its own, in Blender.

Builds the vignette at the origin (bridge.build()), keys bars 0-1 (u 0-3.75 at 30 fps), its camera (the funeral's
first shot, bridge-local) and the claudesona on the walkway; renders the film's shot, a look up toward the sun (the
fog brightens and warms toward it; the pale disc), and the debug_ids build (each part a flat colour, its name printed).
Checks the sun direction, the drift, the set contract's update(t, st) and dispose() numerically.

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy/test_bridge.py [-- --no-render --no-her]
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

or in two steps: test_bridge.py --no-render (CPU), then render_saved.py bridge (the probe cameras are saved with it).
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _common as C                                        # noqa: E402

import bpy                                                  # noqa: E402
from mathutils import Vector                                # noqa: E402

from eidoblend.look import camera as LC                     # noqa: E402
from eidoblend.sets.daisy import bridge as BR               # noqa: E402
from eidoblend.sets.daisy import funeral as FU              # noqa: E402

A = C.args()
FPS = 30
F0, F1 = 1, 113
OUT = os.path.join(C.OUT, 'bridge')
os.makedirs(OUT, exist_ok=True)
sc = C.clean_scene(FPS, (F0, F1))
C.probe_look(sc, exposure=float(A.get('exposure', 0.0)))

Bv = BR.build()
nk = Bv.animate((F0, F1), 0.0)
cams = Bv.make_cameras((F0, F1), 0.0)
if 'no-her' not in A['flags']:
    try:
        C.claudesona(Bv.mark_at, (F0, F1), FPS, 0.0)
    except Exception as e:                                  # noqa: BLE001
        print(f'[bridge] claudesona not loaded: {e}')
# the debug_ids build, parked 2 km away, with its own camera on the same shot
Dv = BR.StandaloneBridge(location=(0.0, 2000.0, 0.0), debug_ids=True)
sc.world = Bv.world['world']                               # the debug build made a World of its own: keep the film's
C.check('debug_ids paints every part a flat colour', all(m.material.name.startswith('bridge:debug_') for o in Dv.nodes.values()
                                                         if o.type == 'MESH' for m in o.material_slots))

# ------------------------------------------------------------------------------------------------- the numbers
sd = Vector(FU.V(BR._norm(BR.SUN_DIR)))
C.check('the sun direction maps to Blender axes (up and ahead)', sd.z > 0.5 and sd.y > 0.7, f'{tuple(round(x, 3) for x in sd)}')
cam = Bv.camera(1.875)
d = (cam['target'] - cam['pos']).normalized()
ang = math.degrees(d.angle(sd))
C.check('the film shot looks past the sun (the disc just above the frame)', 20 < ang < 40, f'{ang:.1f} deg from the sun')
sc.frame_set(F1)
C.check('the fog drifts (keyed: drift = 0.35 t)', abs(Bv.U['drift'] - 0.35 * (F1 - F0) / FPS) < 1e-3, f"{Bv.U['drift']:.3f}")
C.check('the sun is on for the bridge (1.6 W/m2)', abs(Bv.sun_light.data.energy - 1.6) < 1e-6)
# the set contract on the standalone vignette: update(t, st) keys at a frame and returns its Keys; dispose() removes a
# build and leaves the others whole
k = Bv.update(2.0, {'u': 2.0}, frame=F1 + 10)
C.check('update(t, st) keys the drift and the clock at the frame', k.active and abs(Bv.U['drift'] - 0.7) < 1e-9
        and abs(Bv.U['u'] - 2.0) < 1e-9)
n0 = len(bpy.data.objects)
Ex = BR.build(location=(0.0, 4000.0, 0.0))
n1 = len(bpy.data.objects)
Ex.dispose()
C.check('dispose() removes a build (the others stay)', len(bpy.data.objects) == n0 and n1 > n0
        and all(o.name in bpy.data.objects for o in (Bv.group, Dv.group)), f'{n1 - n0} objects made and removed')
sc.world = Bv.world['world']
sc.frame_set(F1)
# the probe cameras, saved with the set: toward the sun (from the mark, up the sun's direction) and the debug_ids build
# seen through the film's shot 2 km away
sun_cam = LC.make_camera('bridge:sun_cam', fov=50)
m = Bv.mark_at(0.0)['pos'] + Vector((0, 0, 1.4))
sun_cam.matrix_world = LC.look_matrix(m, m + sd * 10.0)
dcam = LC.make_camera('bridge:debug_cam', fov=cam['fov'])
off = Vector((0.0, 2000.0, 0.0))
dcam.matrix_world = LC.look_matrix(cam['pos'] + off, cam['target'] + off)
f = 57
stills = [('film_shot', (f - F0) / FPS, f), ('toward_sun', (f - F0) / FPS, f, sun_cam.name),
          ('debug_ids', (f - F0) / FPS, f, dcam.name)]
C.write_stills(OUT, stills)
blend = os.path.join(OUT, 'bridge.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
C.check('saved .blend', os.path.isfile(blend), f'{os.path.getsize(blend) / 1e6:.1f} MB')

if 'no-render' not in A['flags']:
    path = os.path.join(OUT, 'bridge_film_shot.png')
    ok, dt = C.render_still(sc, f, path)
    st = C.image_stats(path)
    C.check('still: the film shot', ok and st['magenta'] < 0.001, f"mean {st['mean']:.3f} ({dt:.1f} s)")
    for mk in list(sc.timeline_markers):
        sc.timeline_markers.remove(mk)
    sc.camera = sun_cam
    path = os.path.join(OUT, 'bridge_toward_sun.png')
    ok, dt = C.render_still(sc, f, path)
    st = C.image_stats(path)
    C.check('still: toward the sun (a bright warm halo, the disc)', ok and st['max'] > 0.9, f"max {st['max']:.2f}")
    sc.camera = dcam
    path = os.path.join(OUT, 'bridge_debug_ids.png')
    ok, dt = C.render_still(sc, f, path)
    C.check('still: debug_ids', ok)


# the harness path (after the save: the saved file stays the set alone): sets.build hands the ctx's scene to the
# builder, and update(t, st, ctx=ctx) keys every value through ctx.key at the ctx's frame
class HarnessCtx:                                           # what the set reads of the harness ctx (context.Ctx)
    def __init__(self, scene):
        self.scene, self.calls = scene, 0

    def key(self, target, data_path, index=-1, frame=None, interpolation='LINEAR'):
        self.calls += 1
        f = self.scene.frame_current if frame is None else frame
        return target.keyframe_insert(data_path, index=index, frame=f)


from eidoblend import sets                                  # noqa: E402
hc = HarnessCtx(sc)
B2 = sets.build('daisy.bridge', hc, location=(0.0, 6000.0, 0.0))
sc.frame_set(30)
B2.update(29 / FPS, {'u': 29 / FPS}, ctx=hc)
fcs = [fc for fc in FU.action_fcurves(B2.U.root.animation_data.action) if fc.data_path == '["drift"]']
C.check('harness ctx: built in ctx.scene, keyed through ctx.key at its frame', B2.kit.scene == sc and hc.calls >= 6
        and fcs and any(abs(k.co.x - 30) < 1e-6 for k in fcs[0].keyframe_points), f'{hc.calls} keys through ctx.key')
B2.dispose()
sys.exit(1 if C.summary('test_bridge') else 0)
