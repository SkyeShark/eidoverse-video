"""make_fire_glow: the burning mesh glows with the fire around it. The engine composited its volume pass with no depth
test, so its fire showed through the burning mesh; in EEVEE the mesh hides the gas behind it, and the glow puts the
fire's light on the mesh itself.

Checks (no render, no bake: a synthetic frame written through the fire's own .vdb writer and attached as its sequence):
    the burning mesh gets the 'fire_glow' Geometry Nodes modifier, and its vertices carry 'fire_temperature' and
        'fire_density' sampled from the grids in the mesh's own frame (the mesh moved and turned in the domain):
        against the synthetic fields (temperature rising with world height, density with world x)
    the material's Emission Color adds the glow to what fed it before (the lava cracks), through the flame's own
        display table (one image for both)
    bake() mutes the modifier while the solver reads the mesh and shows it again after, even when the bake fails
Render: test_fire_teapot.py (the glow on by default, glow=0 without it).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fx/test_fire_glow.py
"""

import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fx import fire as fxfire          # noqa: E402

OUT = os.path.join(HERE, 'out', 'fire_glow')
os.makedirs(OUT, exist_ok=True)
FAILS = []


def check(ok, what):
    print(f"[test_fire_glow] {'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def upstream(sock):
    seen, todo = {}, [lk.from_node for lk in sock.links]
    while todo:
        n = todo.pop()
        if n.name in seen:
            continue
        seen[n.name] = n
        for s in n.inputs:
            todo += [lk.from_node for lk in s.links]
    return list(seen.values())


for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.view_settings.view_transform = 'AgX'
sc.frame_start, sc.frame_end = 1, 1
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45, location=(0.3, 0.2, 1.0), segments=24, ring_count=12)
burner = bpy.context.active_object
burner.rotation_euler = (0.0, 0.0, math.radians(35.0))
mat = bpy.data.materials.new('burner')
mat.use_nodes = True
burner.data.materials.append(mat)
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')

fire = fxfire.create_volume_fire(burner, grid_size=(32, 32, 32), world_size=(4.0, 4.0, 4.0), name='glowfire',
                                 cache_dir=os.path.join(OUT, 'cache'))
fire.make_lava_emissive(mat)
lava_nodes = {n.name for n in upstream(bsdf.inputs['Emission Color'])}
fire.make_fire_glow(mat)
md = burner.modifiers.get(fxfire.GLOW_MODIFIER)
check(md is not None and md.type == 'NODES' and md.node_group is not None, "the burning mesh has the 'fire_glow' modifier")
n_nodes = len(mat.node_tree.nodes)
fire.make_fire_glow(mat, strength=0.5)
gain = mat.node_tree.nodes.get('fire_glow_strength')
check(len([m for m in burner.modifiers if m.name.startswith(fxfire.GLOW_MODIFIER)]) == 1
      and len(mat.node_tree.nodes) == n_nodes and gain is not None and abs(gain.outputs[0].default_value - 0.5) < 1e-6,
      f"a second call sets the strength ('fire_glow_strength' {gain.outputs[0].default_value if gain else None}) "
      f"and adds nothing ({len(mat.node_tree.nodes)} nodes)")

# ---- the material ------------------------------------------------------------------------------------------------
up = upstream(bsdf.inputs['Emission Color'])
names = {n.attribute_name for n in up if n.type == 'ATTRIBUTE'}
check({'fire_temperature', 'fire_density'} <= names and lava_nodes <= {n.name for n in up},
      f"Emission Color = the lava + the glow from {sorted(names)} ({len(up)} nodes)")
glow_imgs = {n.image.name for n in up if n.type == 'TEX_IMAGE' and n.image is not None}
vol_imgs = {n.image.name for n in fire.material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image is not None}
check(bool(glow_imgs & vol_imgs), f"the glow reads the flame's own display table: {sorted(glow_imgs & vol_imgs)}")
check(all(n.image is not None for n in fire.material.node_tree.nodes if n.type == 'TEX_IMAGE'),
      "the volume material keeps its table image")

# ---- a synthetic frame: temperature rising with world height, density with world x --------------------------------
import openvdb as vdb  # noqa: E402
GX, GY, GZ = fire.G3
WX, WY, WZ = fire.W3
dx = WX / GX
x_w = fire.origin[0] - WX / 2 + (np.arange(GX) + 0.5) * dx         # x3 index -> Blender world x
z_w = fire.origin[2] + (np.arange(GY) + 0.5) * dx                  # y3 index -> Blender world z


def t_of(z):
    return (z - 0.5) / 1.5


def rho_of(x):
    return 2.0 + 0.5 * x


arr = np.zeros((GZ, GY, GX, 4), np.float32)
arr[..., 1] = t_of(z_w)[None, :, None]
arr[..., 0] = rho_of(x_w)[None, None, :]
fire._write_vdb(vdb, 1, arr)
fire._attach_sequence(1, 1)
sc.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
ev = burner.evaluated_get(dg)
me = ev.to_mesh()
n = len(me.vertices)
co = np.empty(n * 3, np.float64)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
vals = {}
for nm in ('fire_temperature', 'fire_density'):
    a = me.attributes.get(nm)
    v = np.zeros(n, np.float32)
    if a is not None and a.domain == 'POINT':
        a.data.foreach_get('value', v)
    vals[nm] = v.astype(np.float64)
ev.to_mesh_clear()
M = np.array(burner.matrix_world)
W_ = co @ M[:3, :3].T + M[:3, 3]
eT = np.abs(vals['fire_temperature'] - t_of(W_[:, 2])).max()
eR = np.abs(vals['fire_density'] - rho_of(W_[:, 0])).max()
check(eT < 0.01 and eR < 0.01,
      f'{n} vertices sample the grids in the mesh\'s frame: max |error| temperature {eT:.4f} (range '
      f'{vals["fire_temperature"].min():.2f}..{vals["fire_temperature"].max():.2f}), density {eR:.4f}')

# ---- bake() mutes the modifier while the solver reads the mesh ---------------------------------------------------
seen = {}


def failing_bake(*_a, **_k):
    seen['shown'] = md.show_viewport
    raise RuntimeError('stopped here')


fire._bake = failing_bake
try:
    fire.bake(1, 1)
except RuntimeError:
    pass
check(seen.get('shown') is False and md.show_viewport, 'bake() mutes the glow while it runs and shows it again after')
print(f'[test_fire_glow] {"FAIL" if FAILS else "PASS"}: {len(FAILS)} failed check(s)')
