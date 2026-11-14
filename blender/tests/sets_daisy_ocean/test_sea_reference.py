"""The sea's fragment stage against an independent reference: the ocean of faces' unlit material rendered alone in
linear light (Standard view, 16-bit PNG, no dither) from four views, the water held flat (calm 0, relief 0: the swell
phases, the faces' surfacing and their light untouched, only the displacement goes) so the reference can intersect the
plane exactly; the camera, the uniforms and the layout's matrix are dumped beside each still; then sea_reference.py
(system Python) evaluates sea.js's colorNode in numpy for the same pixels and compares.

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy_ocean/test_sea_reference.py [--render-only]
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)
    python <worktree>/blender/tests/sets_daisy_ocean/sea_reference.py    (the compare alone, after --render-only)
"""
import json
import math
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sets.daisy import ocean  # noqa: E402
from eidoblend.sets.daisy.ocean.staging import D_MOON  # noqa: E402

OUT = os.path.join(C.OUT, 'sea_reference')
os.makedirs(OUT, exist_ok=True)
CS = C.characters_stage()
sc = CS.clean_scene(fps=24)
for w in list(bpy.data.worlds):
    bpy.data.worlds.remove(w)
RES = (480, 270)
CS.probe_render(sc, res=RES, samples=16)
sc.render.filter_size = 0.5
sc.render.dither_intensity = 0.0
vs = sc.view_settings
vs.view_transform = 'Standard'
vs.look = 'None'
vs.exposure, vs.gamma = 0.0, 1.0
im = sc.render.image_settings
im.media_type = 'IMAGE'
im.file_format = 'PNG'
im.color_mode = 'RGB'
im.color_depth = '16'
ocean.render_settings(sc)
cam = bpy.data.objects.new('vcam', bpy.data.cameras.new('vcam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.sensor_fit = 'VERTICAL'
cam.data.clip_start, cam.data.clip_end = 0.05, 3200.0
cam.rotation_mode = 'QUATERNION'
O = ocean.build({'scene': sc, 'parts': ('sea', 'world')})
sea = O.sea
MY = O.coast.markY
E = MY + 1.52
s, c = math.sin(D_MOON), math.cos(D_MOON)
OVER = (-s * 3.4 + c * 0.7, E + 0.9, -c * 3.4 - s * 0.7)               # over the mark's shoulder, out to sea
OUT_TO = (s * 26.0, E - 3.2, c * 26.0)
BEHIND = (-s * 4.2 + c * 1.5, E + 0.1, -c * 4.2 - s * 1.5)
FIG = (s * 22.0, E + 2.0, c * 22.0)
probes = [  # name, t, reveal, (camera, target, fov) in the design frame
    ('over_mark_reveal63', 105.6, 0.63, (OVER, OUT_TO, 39.0)),
    ('moon_path_full', 116.5, 1.0, (BEHIND, FIG, 38.0)),
    ('aerial', 112.0, 1.0, ((7.0, 16.0, 20.0), (-4.0, 0.0, -14.0), 50.0)),
    ('low_waterline', 109.0, 1.0, ((0.4, MY + 0.35, -3.6), (2.0, -0.2, -40.0), 40.0)),
]
for name, t, reveal, (p3, t3, fov) in probes:
    O.update(t, {'reveal': reveal, 'calm': 0.0, 'relief': 0.0})
    p, tg = Vector(O.to_world(p3)), Vector(O.to_world(t3))
    cam.location = p
    cam.rotation_quaternion = (tg - p).to_track_quat('-Z', 'Y')
    cam.data.angle_y = math.radians(fov)
    sea.mesh.update_tag()
    bpy.context.view_layer.update()
    path = os.path.join(OUT, f'blender_{name}.png')
    sc.render.filepath = path
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    U = {k: (list(sea.get(k)) if isinstance(sea.get(k), tuple) else sea.get(k)) for k in
         ('t', 'reveal', 'glow', 'relief', 'calm', 'moonW', 'moonCol', 'moonI', 'zen', 'hor', 'porchW', 'porch',
          'porchCol', 'winW', 'win', 'fog')}
    meta = {'name': name, 'u': t, 'res': RES, 'cam_matrix': [list(r) for r in cam.matrix_world],
            'angle_y': cam.data.angle_y, 'layout_matrix': [list(r) for r in O.layout.matrix_world], 'PSI': O.PSI,
            'uniforms': U}
    with open(os.path.join(OUT, f'blender_{name}.json'), 'w') as fh:
        json.dump(meta, fh, indent=1)
    print(f'[sea_ref] {name}: rendered {time.time() - t1:.1f}s', flush=True)
if '--render-only' not in C.argv():                  # (the compare is ~3 min of numpy: run it apart to free the GPU slot)
    r = subprocess.run(['python', os.path.join(C.HERE, 'sea_reference.py')], cwd=C.HERE)
    print(f'[sea_ref] reference compare exit {r.returncode}', flush=True)
