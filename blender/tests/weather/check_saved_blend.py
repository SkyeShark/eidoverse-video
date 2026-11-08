"""Run inside a fresh Blender on a saved weather .blend (no eidoblend import, no Python weather code): print, as JSON,
what the file evaluates on its own at the frames asked for. test_blender_build.py compares it with the live session.

    blender --background <file.blend> --python check_saved_blend.py -- <frame> [<frame> ...]
"""
import hashlib
import json
import sys

import bpy
import numpy as np

frames = [int(a) for a in sys.argv[sys.argv.index('--') + 1:]]
sc = bpy.context.scene
out = {}
for f in frames:
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    rec = {}
    me = bpy.data.objects['eido_rain'].evaluated_get(dg).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    rec['rain_vertices'] = len(me.vertices)
    rec['rain_sum'] = float(np.round(co.astype(np.float64).sum(), 2))
    rec['rain_md5'] = hashlib.md5(np.round(co, 3).tobytes()).hexdigest()
    rec['light_energy'] = float(bpy.data.objects['eido_lightning_light'].data.energy)
    vg = bpy.data.node_groups['eido_weather_values']
    rec['rain_light'] = float(vg.nodes['rain_light'].outputs[0].default_value)
    rec['wetness'] = float(vg.nodes['wetness'].outputs[0].default_value)
    bolts = [o for o in bpy.data.objects if o.name.startswith('eido_bolt_')]
    rec['bolts_drawn'] = sorted(o.name for o in bolts if not o.hide_render)
    sp = [o for o in bpy.data.objects if o.name.startswith('eido_impact_sparks_')]
    rec['spark_vertices'] = sum(len(o.evaluated_get(dg).data.vertices) for o in sp)
    img = bpy.data.images.get('eido_moisture')
    rec['moisture_image'] = bool(img) and img.source == 'SEQUENCE'
    out[str(f)] = rec
print('SAVED_BLEND_JSON ' + json.dumps(out), flush=True)
