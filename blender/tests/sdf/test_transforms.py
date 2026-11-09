"""SDF solids placed as a film places them: rotated, scaled (also unevenly), seated on a glossy floor, half hidden by
an ordinary mesh, and an animated one rendered with motion blur from its baked frames.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sdf/test_transforms.py

Mr. Hege turned 35 degrees and scaled 0.55; the red shoggoth tilted 20 degrees forward, turned -50 degrees and
scaled (0.45, 0.6, 0.45); a grey box in front of Mr. Hege's legs. PASS lines: each mesh's silhouette from the
camera matches the engine's march of its field through the same object transform (the change of axes, the
rotation and the uneven scale agree between the mesh and the reference); place_on_ground seats each on z = 0 under
its rotation and scale; the shoggoth's baked frames play and its frame 2 renders with EEVEE motion blur as the same
frame (each frame mesh has its own topology, so EEVEE blurs only object motion, and nothing streaks).
out/transforms.png, top to bottom: the scene, the shoggoth's frame 2, the same frame with motion blur on.
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402

W, H = 960, 540
CACHE = os.path.join(C.OUT, 'cache_transforms')

sc = C.stage(W, H, 16, world_color=(0.42, 0.46, 0.52), world_strength=0.8, floor_color=(0.16, 0.16, 0.17),
             sun_energy=3.5, sun_rot=(48.0, 0.0, 30.0))
sc.frame_start, sc.frame_end = 1, 3
floor_bsdf = bpy.data.materials['floor_mat'].node_tree.nodes['Principled BSDF']
floor_bsdf.inputs['Roughness'].default_value = 0.12            # a glossy floor: the solids must show in it

hege = sdf.EXAMPLES['mr_hege'].make(name='tf_hege', cache_dir=CACHE, location=(-0.85, 0.35, 0.0),
                                    rotation=(0.0, 0.0, math.radians(35.0)), scale=0.55, log=None)
shog = sdf.EXAMPLES['red_shoggoth'].make(name='tf_shoggoth', cache_dir=CACHE, location=(1.05, 0.7, 0.0),
                                         rotation=(math.radians(20.0), 0.0, math.radians(-50.0)),
                                         scale=(0.45, 0.6, 0.45), log=None)
for o in (hege, shog):
    o.place_on_ground(0.0)
bpy.context.view_layer.update()
for o in (hege, shog):
    zmin = min((o.object.matrix_world @ v.co).z for v in o.object.data.vertices)
    C.check(f'{o.name}: seated under its rotation and scale', abs(zmin) < 1e-4,
            f'lowest point z = {zmin * 1000:.3f} mm')

# an ordinary mesh in front of Mr. Hege's legs: the SDF is in the depth buffer like any mesh
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-0.55, -0.35, 0.22))
box = bpy.context.active_object
box.scale = (0.28, 0.2, 0.22)
bm = bpy.data.materials.new('tf_box')
bm.use_nodes = True
bm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.5, 0.5, 0.52, 1.0)
box.data.materials.append(bm)

cam = C.camera((0.35, -4.4, 1.25), (0.1, 0.3, 0.62), lens=38)


def mesh_coverage(obj, w, h):
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(obj, dg)
    inv = obj.matrix_world.inverted()
    frame = cam.data.view_frame(scene=sc)
    tr, br, bl = frame[0], frame[1], frame[2]
    origin = inv @ cam.matrix_world.translation
    m = np.zeros((h, w), bool)
    for j in range(h):
        v = 1.0 - (j + 0.5) / h
        for i in range(w):
            u = (i + 0.5) / w
            d = (inv.to_3x3() @ (cam.matrix_world.to_3x3() @ (bl + (br - bl) * u + (tr - br) * v)))
            m[j, i] = bvh.ray_cast(origin, d.normalized())[0] is not None
    return m


# silhouettes at half size: the mesh through the object's transform against the engine's march through it
for o in (hege, shog):
    w2, h2 = W // 2, H // 2
    ref = o.raymarch_reference(cam, w2, h2, samples=1, t=0.0)
    m_ref = ref[::-1, :, 3] > 0.5
    m_mesh = mesh_coverage(o.object, w2, h2)
    iou = float((m_ref & m_mesh).sum()) / max(1.0, float((m_ref | m_mesh).sum()))
    C.check(f'{o.name}: rotated and scaled, the mesh matches the march', iou > 0.93,
            f'IoU {iou:.3f} (mesh {m_mesh.mean() * 100:.2f}%, march {m_ref.mean() * 100:.2f}% of the frame)')

eevee = os.path.join(C.OUT, 'tf_eevee.png')
C.check('scene renders', C.render(eevee), eevee)

# the shoggoth animated: three baked frames, frame 2 with and without motion blur
shog.bake(1, 3, log=None)
counts = []
for f in (1, 2, 3):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    counts.append(len(shog.object.evaluated_get(dg).data.vertices))
C.check('the shoggoth bakes and plays under its transform', min(counts) > 1000 and len(set(counts)) > 1,
        f'vertices per frame {counts}')
hege.object.hide_render = True
box.hide_render = True
cam2 = C.camera((1.05 + 1.9 * math.sin(math.radians(-20)), 0.7 - 1.9 * math.cos(math.radians(-20)), 0.95),
                (1.05, 0.7, 0.62), lens=45, name='cam_close')
sc.frame_set(2)
still = os.path.join(C.OUT, 'tf_shoggoth_f2.png')
C.render(still)
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.5
blur = os.path.join(C.OUT, 'tf_shoggoth_f2_blur.png')
C.check('frame 2 renders with motion blur', C.render(blur), blur)
sc.render.use_motion_blur = False
import OpenImageIO as oiio  # noqa: E402
a = np.asarray(oiio.ImageBuf(still).get_pixels(oiio.FLOAT))[..., :3]
b = np.asarray(oiio.ImageBuf(blur).get_pixels(oiio.FLOAT))[..., :3]
diff = np.abs(a - b).max(axis=-1)
# each baked frame is a mesh of its own topology, so EEVEE adds no deformation blur (only the object's own motion
# blurs): what must hold is that the blurred frame is the frame, with no streaks from mismatched frame meshes
C.check('motion blur on baked frames: the frame, no streaks', float(diff.mean()) < 0.02 and
        float((diff > 0.25).mean()) < 0.01,
        f'mean difference {diff.mean():.4f}, {(diff > 0.25).mean() * 100:.2f}% of pixels differ by more than 0.25 '
        f'(no deformation blur: each frame mesh has its own topology)')
C.sheet([eevee, still, blur], os.path.join(C.OUT, 'transforms.png'), cols=1)
C.summary()
