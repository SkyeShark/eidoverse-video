"""t_scanned.py: every scanned CC0 Poly Haven set through the brush, on bare ground where nothing hides them: a 3 x 2
lineup (grass_medium_01, grass_medium_02, celandine_01 / dandelion_01, shrub_sorrel_01, weed_plant_02), each patch
labelled on the ground, plus a low close look at the two single-LOD sets (grass_medium_02, shrub_sorrel_01).
API checks without a render: each set builds at its default LOD, the LOD fallback (grass_medium_01 has no LOD3),
a lettered variant filter on a single-LOD set, and per-plant variant picks. Writes out/scanned_<shot>.png.
    bash run_blender.sh blender/tests/flora/t_scanned.py [--no-render]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402
from eidoblend.flora.vegetation import SCANNED_SPECIES  # noqa: E402

S.new_scene()
S.lights(sun_elev_deg=40, sun_az_deg=-50, strength=4.0, sky_strength=0.7, gradient=True)
S.ground()
reset_flora_occupancy()


def label(text, x, y):
    cu = bpy.data.curves.new('lbl_' + text, 'FONT')
    cu.body = text
    cu.size = 0.09
    cu.align_x = 'CENTER'
    ob = bpy.data.objects.new('lbl_' + text, cu)
    ob.location = (x, y, 0.002)
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.get('lbl') or bpy.data.materials.new('lbl')
    m.diffuse_color = (0.9, 0.9, 0.9, 1)
    cu.materials.append(m)


# patch centres (x, y) and a density multiplier so each patch holds a handful to a few dozen plants
LINEUP = [('grass_medium_01', (-1.25, 1.9), 1.0), ('grass_medium_02', (0.0, 1.9), 1.0), ('celandine_01', (1.25, 1.9), 4.0),
          ('dandelion_01', (-1.25, 0.75), 4.0), ('shrub_sorrel_01', (0.0, 0.75), 1.0), ('weed_plant_02', (1.25, 0.75), 6.0)]
fields = {}
for asset, (x, y), dens in LINEUP:
    f = create_flora('ph:' + asset, size=0.95, center=(x, y), seed=11, density=dens)
    fields[asset] = f
    label(asset, x, y - 0.56)
    print(f'[scanned] {asset}: {f.count} plants, {f.stats["proto_verts"]} verts max per variant')
assert set(fields) == set(SCANNED_SPECIES), 'the lineup must cover every scanned set'

# API checks (no render)
dg = bpy.context.evaluated_depsgraph_get()
for asset, f in fields.items():
    me = f.object.evaluated_get(dg).to_mesh()
    var = np.empty(f.count, np.int32)
    f.object.data.attributes['variant'].data.foreach_get('value', var)
    sock = next(i for i in f.modifier.node_group.interface.items_tree
                if getattr(i, 'in_out', None) == 'INPUT' and i.name == 'Variants')
    vcol = getattr(f.modifier.properties.inputs, sock.identifier).value
    print(f'[scanned] {asset}: evaluated {len(me.vertices)} verts, {len(set(var.tolist()))} of {len(vcol.objects)} '
          f'variants used ({sorted(o.name for o in vcol.objects)[:3]}...), materials {[m.name for m in me.materials]}')
    assert len(me.vertices) > 0, asset
    f.object.evaluated_get(dg).to_mesh_clear()
lod3 = create_flora('ph:grass_medium_01', placements=[(5.0, 5.0, 1.0)], lod=3, name='chk_lod3')
names = sorted(o.name for o in bpy.data.collections['flora_ph_grass_medium_01_lod2'].objects)
assert all(n.endswith('_LOD2') for n in names), names
lett = create_flora('ph:shrub_sorrel_01', placements=[(5.0, 5.5, 1.0), (5.1, 5.5, 1.0)], variants=['a', 'b'],
                    name='chk_letters')
names = sorted(o.name for o in bpy.data.collections['flora_ph_shrub_sorrel_01_a_b'].objects)
assert names == ['shrub_sorrel_01_a', 'shrub_sorrel_01_b'], names
for f in (lod3, lett):
    f.remove()
print('[scanned] API checks passed: every set builds; lod=3 on grass_medium_01 -> LOD2; variants=[a, b] on a '
      'single-LOD set keeps exactly those two', flush=True)

SHOTS = {
    # the lineup from a crouch in front, every patch in view
    'lineup': ((0.0, -2.3, 1.3), (0.0, 1.25, 0.0), 28),
    # low and close on the two single-LOD sets (grass_medium_02 behind, shrub_sorrel_01 in front)
    'close': ((0.55, -0.15, 0.32), (0.0, 1.2, 0.04), 40),
}
for name, (loc, tgt, lens) in SHOTS.items():
    S.camera(loc, tgt, lens, name='cam_' + name)
    S.render(os.path.join(S.OUT, f'scanned_{name}.png'), 1)
print('[scanned] done')
