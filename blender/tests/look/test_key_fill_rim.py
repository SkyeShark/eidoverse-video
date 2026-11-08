"""tests/look/test_key_fill_rim.py: the studio three-point rig (lighting.key_fill_rim) on claude_robot.vrm, standing in
the stock idle on a grey floor under a near-black world: the key to the camera's side and above, the fill on the other
side at a quarter of the key, the rim behind. Rendered with the key alone, the key + fill, and all three, so each
light's job shows. Judge: the key models the shells (a lit side and a shadow side), the fill opens the shadow side
without flattening it, the rim separates the silhouette from the background.
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh blender/tests/look/test_key_fill_rim.py
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as FX                                       # noqa: E402

from eidoblend.look import camera as C                       # noqa: E402
from eidoblend.look import exposure as EX                    # noqa: E402
from eidoblend.look import frame_stats as FS                 # noqa: E402
from eidoblend.look import lighting as L                     # noqa: E402
from eidoblend.look import probe as P                        # noqa: E402
from eidoblend.look import render_settings as RS             # noqa: E402

OUT = os.path.join(FX.OUT, 'key_fill_rim')
os.makedirs(OUT, exist_ok=True)
sc = FX.new_scene(frames=(1, 24))
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
floor = bpy.context.object
m = bpy.data.materials.new('floor_grey')
m.use_nodes = True
m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.18, 0.18, 0.18, 1)
m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.6
floor.data.materials.append(m)
w = bpy.data.worlds.new('dark')
sc.world = w
if w.node_tree is None:
    w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.022, 0.025, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
arm, _m = FX.robot(sc, walk=False, start=(0, 0, 0), clip='idle')
arm.rotation_euler = (0, 0, 0)                       # facing -Y, toward the camera
cam = C.make_camera('cam', lens=50, fstop=4.0, scene=sc)
C.hold(sc, cam, (1, 24), (0.6, -4.2, 1.25), C.bone_target(arm, 'chest'))
C.focus_on(sc, cam, (1, 24), C.bone_target(arm, 'chest'))
sc.camera = cam
sc.frame_set(12)
bpy.context.view_layer.update()
rig = L.key_fill_rim(sc, subject=arm, camera=cam, key_w=250, fill_ratio=0.25, rim_w=300, distance=2.5)
L.log_lights(sc)
RS.apply_auto_enhance(sc, 'probe', ao={'distance': 0.4})
paths = []
for name, on in (('key', ('key',)), ('key_fill', ('key', 'fill')), ('key_fill_rim', ('key', 'fill', 'rim'))):
    for k, o in rig.items():
        o.hide_render = k not in on
    if name == 'key':
        ae = EX.auto_expose(sc, os.path.join(OUT, 'sweep'), log=False)
        print(f"[kfr] exposure {ae['exposure']:+.2f}: {ae['pick']['reason']}", flush=True)
    p = os.path.join(OUT, f'{name}.png')
    P.render_still(sc, p, 12)
    st = FS.frame_stats(FS.read_rgb(p))
    print(f"[kfr] {name}: {FS.check_highlights(st)[1]}", flush=True)
    paths.append(p)
FS.sheet(paths, os.path.join(OUT, 'kfr_sheet.jpg'), cols=3, tile=480, labels=['key alone', 'key + fill', 'key + fill + rim'])
print('[kfr] done', flush=True)
