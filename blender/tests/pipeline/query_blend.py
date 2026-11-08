"""query_blend.py <file.blend> <spec.json>: what a SAVED build shows, for run_tests.py (no render).

    bash run_blender.sh blender/tests/pipeline/query_blend.py out/bake.blend out/_q.json

spec: {"frames": [250, 300], "objects": ["crate_0"], "lights": ["lamp"], "interp": ["cam", "lamp"]}
Prints one line `QUERY_JSON {...}`: at each frame, each object's evaluated world position and each light's
energy; and each named ID's F-curve interpolations ({data path[index]: [names]}), objects and lights alike.
"""
import json
import os
import sys

import bpy

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')))
from eidoblend import common  # noqa: E402
from eidoblend.harness import keying  # noqa: E402

blend, spec_path = common.script_args()[:2]
with open(spec_path, encoding='utf-8') as f:
    spec = json.load(f)
bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
scene = bpy.context.scene
out = {'frames': {}, 'interp': {}, 'range': [scene.frame_start, scene.frame_end]}
for fr in spec.get('frames', []):
    scene.frame_set(int(fr))
    dg = bpy.context.evaluated_depsgraph_get()
    row = {'objects': {}, 'lights': {}}
    for name in spec.get('objects', []):
        ob = bpy.data.objects.get(name)
        if ob is not None:
            row['objects'][name] = list(ob.evaluated_get(dg).matrix_world.translation)
    for name in spec.get('lights', []):
        li = bpy.data.lights.get(name)
        if li is not None:
            row['lights'][name] = li.energy
    out['frames'][str(fr)] = row
for name in spec.get('interp', []):
    for coll in (bpy.data.objects, bpy.data.lights, bpy.data.cameras):
        idb = coll.get(name)
        if idb is not None:
            out['interp'][f'{type(idb).__name__}:{name}'] = {k: sorted(v) for k, v in keying.interpolations(idb).items()}
print('QUERY_JSON ' + json.dumps(out), flush=True)
