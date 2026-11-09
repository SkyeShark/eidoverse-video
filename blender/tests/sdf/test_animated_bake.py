"""Animated SDFs as keyed Blender data: Mr. Hege (uTime: head sway, six wiggling tentacles) re-meshed per frame into a
PLY sequence played by Geometry Nodes ('vertex' carrier), the blob as a per-frame atlas sequence ('atlas'), the
.blend saved, reopened and rendered again: the saved file plays on its own.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sdf/test_animated_bake.py

out/anim_hege_f0001.png, anim_hege_f0005.png (this session), anim_hege_f0005_reopened.png (from the saved file),
anim_sheet.png.
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402

CACHE = os.path.join(C.OUT, 'cache_anim')
BLEND = os.path.join(C.OUT, 'anim_hege.blend')
A = C.args()
if A.get('phase', '1') == '1':
    sc = C.stage(960, 540, 16, world_color=(0.2, 0.2, 0.2), world_strength=1.0, sun=False,
                 floor_color=(0.18, 0.18, 0.18))
    for i, (d3, col, k) in enumerate([((5.0, 8.0, 5.0), (1.0, 0.94, 0.85), 1.1), ((-4.0, 3.0, -6.0), (0.35, 0.5, 0.85), 0.32)]):
        from mathutils import Vector
        ld = bpy.data.lights.new(f'key{i}', 'SUN')
        ld.energy, ld.color, ld.angle = math.pi * k, col, math.radians(1.5)
        ob = bpy.data.objects.new(f'key{i}', ld)
        sc.collection.objects.link(ob)
        ob.rotation_euler = Vector((d3[0], -d3[2], d3[1])).normalized().to_track_quat('Z', 'Y').to_euler()
    sc.frame_start, sc.frame_end = 1, 5
    hege = sdf.EXAMPLES['mr_hege'].make(name='hege_anim', cache_dir=CACHE, cells=320)
    hege.place_on_ground(0.0)
    hege.bake(1, 5, time_scale=10.0, step=2)                  # frames 2 and 4 hold 1 and 3
    plys = [os.path.join(CACHE, f'hege_anim_{f:04d}.ply') for f in range(1, 6)]
    C.check('one PLY per frame', all(os.path.exists(p) for p in plys), f'{len(plys)} files')
    s1, s2, s3 = (os.path.getsize(p) for p in plys[:3])
    C.check('held frames copy the frame before', s1 == s2 and s3 != s1, f'sizes {s1} {s2} {s3}')
    blob = sdf.EXAMPLES['stylized_blob'].make(name='blob_anim', cache_dir=CACHE, cells=128, location=(1.6, 0.8, 0.0),
                                              scale=0.5, carrier='atlas_sequence')
    blob.place_on_ground(0.0)
    blob.bake(1, 5, time_scale=20.0)
    exr0 = os.path.join(CACHE, 'blob_anim_0000_base.exr')
    C.check('atlas sequence with its hold copy', os.path.exists(exr0) and
            os.path.exists(os.path.join(CACHE, 'blob_anim_0005_normal.exr')), 'blob_anim_0000..0005 *.exr')
    # Mr. Hege stands 3 m tall and his head sway is the motion to see: this frame holds z = -0.2 .. 3.3 m
    cam = C.camera((0.9, -7.2, 1.6), (0.45, 0.0, 1.45), lens=40)

    def verts_at(obj, f):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get('co', co)
        ev.to_mesh_clear()
        return co.reshape(-1, 3)
    v1, v5 = verts_at(hege.object, 1), verts_at(hege.object, 5)
    C.check('the player shows each frame', len(v1) > 1000 and (len(v1) != len(v5) or float(np.abs(v1 - v5).max()) > 0.01),
            f'{len(v1)} vs {len(v5)} vertices')
    for f in (1, 5):
        sc.frame_set(f)
        p = os.path.join(C.OUT, f'anim_hege_f{f:04d}.png')
        C.check(f'render frame {f}', C.render(p), p)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    C.check('saved', os.path.exists(BLEND), BLEND)
    # phase 2: the saved file, opened fresh, renders frame 5 by itself
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.frame_set(5)
    p2 = os.path.join(C.OUT, 'anim_hege_f0005_reopened.png')
    C.check('the reopened .blend renders frame 5', C.render(p2), p2)
    import OpenImageIO as oiio
    a = np.asarray(oiio.ImageBuf(os.path.join(C.OUT, 'anim_hege_f0005.png')).get_pixels(oiio.FLOAT))
    b = np.asarray(oiio.ImageBuf(p2).get_pixels(oiio.FLOAT))
    d = float(np.abs(a - b).mean())
    C.check('the reopened file shows the same frame', d < 0.01, f'mean difference {d:.4f}')
    C.sheet([os.path.join(C.OUT, 'anim_hege_f0001.png'), os.path.join(C.OUT, 'anim_hege_f0005.png')],
            os.path.join(C.OUT, 'anim_sheet.png'), cols=2)
C.summary()
