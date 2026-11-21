"""The hex grid (blender/eidoblend/terrain/build/surfacing.py hex_grid_group, the Blender edition as it is) rendered by
EEVEE as the oracle of build/surfacing.js hexGrid (PORT_PLAN.md 8.2 row P17): a 40 m plane seen top-down, its object
coordinates into eido_hex_grid (inverse size 1 / 10 m, seed 7.1, turned), each slot's weight, offset, turn and
turned position as an unlit emission, one sample, no film filter, into a 32-bit EXR.

    bash run_blender.sh eidoverse/terrain/tests/surfacing/blender_probe_hex.py <out dir>
    (from a checkout of the blender branch: EIDO_BLENDER_EDITION's run_blender.sh; a GPU job)

Writes <out dir>/hex_<pass>.npy ((H, W, 4) float32, row 0 the bottom) and hex.json.
"""
import json
import os
import sys

import bpy
import numpy as np

_ARGS = [a for a in sys.argv[sys.argv.index('--') + 1:] if a != '--'] if '--' in sys.argv else []
OUT = os.path.abspath(_ARGS[0]) if _ARGS else os.path.join(os.getcwd(), 'probe_hex')
os.makedirs(OUT, exist_ok=True)
EDITION = os.environ.get('EIDO_BLENDER_EDITION')
if EDITION:
    sys.path.insert(0, os.path.join(EDITION, 'blender'))
from eidoblend.terrain.build import surfacing as S  # noqa: E402

SIDE, PX, INV, SEED = 40.0, 256, 0.1, 7.1
sc = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc.render.resolution_x = sc.render.resolution_y = PX
sc.render.resolution_percentage = 100
sc.world = bpy.data.worlds.new('black')
sc.world.color = (0.0, 0.0, 0.0)
sc.render.film_transparent = True
vs = sc.view_settings
vs.view_transform = 'Standard'
vs.look = 'None'
sc.eevee.taa_render_samples = 1
try:
    sc.render.filter_size = 0.0
except (AttributeError, TypeError):
    pass
sc.render.use_compositing = False
im = sc.render.image_settings
im.file_format = 'OPEN_EXR'
im.color_depth = '32'
im.color_mode = 'RGBA'
me = bpy.data.meshes.new('hex_plane')
me.from_pydata([(0, 0, 0), (SIDE, 0, 0), (SIDE, SIDE, 0), (0, SIDE, 0)], [], [(0, 1, 2, 3)])
ob = bpy.data.objects.new('hex_plane', me)
sc.collection.objects.link(ob)
cam = bpy.data.objects.new('hex_cam', bpy.data.cameras.new('hex_cam'))
sc.collection.objects.link(cam)
cam.data.type = 'ORTHO'
cam.data.ortho_scale = SIDE
cam.data.clip_start, cam.data.clip_end = 0.1, 100.0
cam.location = (SIDE / 2, SIDE / 2, 10.0)
sc.camera = cam

PASSES = {
    'w': [('W0', None), ('W1', None), ('W2', None)],
    'o': [('O0', 0), ('O0', 1), ('O1', 0)],
    'cs': [('CS0', 0), ('CS0', 1), ('CS2', 0)],
    'rd': [('RD0', 0), ('RD0', 1), ('RD1', 0)],
}
for name, outs in PASSES.items():
    mat = bpy.data.materials.new('hex_' + name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord')
    grp = nt.nodes.new('ShaderNodeGroup')
    grp.node_tree = S.hex_grid_group(True)
    nt.links.new(tc.outputs['Object'], grp.inputs['Position'])
    grp.inputs['Inverse Size'].default_value = INV
    grp.inputs['Seed'].default_value = SEED
    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    for k, (sock, ch) in enumerate(outs):
        src = grp.outputs[sock]
        if ch is not None:
            sp = nt.nodes.new('ShaderNodeSeparateXYZ')
            nt.links.new(src, sp.inputs[0])
            src = sp.outputs[ch]
        nt.links.new(src, comb.inputs[k])
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(comb.outputs[0], em.inputs['Color'])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    me.materials.clear()
    me.materials.append(mat)
    path = os.path.join(OUT, f'hex_{name}.exr')
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    np.save(os.path.join(OUT, f'hex_{name}.npy'), px.reshape(h, w, 4))
    os.remove(path)
with open(os.path.join(OUT, 'hex.json'), 'w') as f:
    json.dump(dict(blender=bpy.app.version_string, side_m=SIDE, px=PX, inverse_size=INV, seed=SEED,
                   passes={k: [list(map(str, o)) for o in v] for k, v in PASSES.items()}), f, indent=1)
print(f'[probe_hex] wrote {len(PASSES)} passes to {OUT}')
