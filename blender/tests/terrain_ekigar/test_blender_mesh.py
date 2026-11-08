"""Blender checks of the mesh side (no render): build_mesh puts every texel centre at its true height, carries every
mask as a point attribute, and hf.height_at() lands exactly on the surface Blender renders (ray casts at random
points, including inside quads, where the triangle split decides the answer).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/terrain_ekigar/test_blender_mesh.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.terrain import ekigar  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}", flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

hf = ekigar.generate('volcano', resolution=128, world_size=400, z_base='min')
obj = ekigar.build_mesh(hf, name='Volcano')
me = obj.data
nx, ny = hf.resolution
check('one vertex per texel centre', len(me.vertices) == nx * ny and len(me.polygons) == (nx - 1) * (ny - 1),
      f'{len(me.vertices)} vertices, {len(me.polygons)} quads')
co = np.zeros(len(me.vertices) * 3, dtype=np.float32)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
xs, ys = hf.grid_xy()
check('vertices sit on the texel centres at their true height',
      np.abs(co[:, 0] - xs.ravel()).max() < 1e-3 and np.abs(co[:, 2] - hf.heights_m.ravel()).max() < 1e-3)
names = {a.name for a in me.attributes}
want = {'ekigar_' + k for k in hf.masks()} | {'ekigar_height', 'ekigar_hnorm'}
check('every mask is a point attribute', want <= names, f'{len(want)} attributes')
val = np.zeros(len(me.vertices), dtype=np.float32)
me.attributes['ekigar_slope'].data.foreach_get('value', val)
check('attribute values are the masks', np.abs(val - hf.mask('slope').ravel()).max() < 1e-6)

dg = bpy.context.evaluated_depsgraph_get()
rng = np.random.default_rng(3)
pts = rng.uniform(-190, 190, size=(400, 2))
worst = 0.0
misses = 0
for x, y in pts:
    hit, loc, nrm, idx, ob, mat = scene.ray_cast(dg, Vector((x, y, 1000.0)), Vector((0, 0, -1)))
    if not hit:
        misses += 1
        continue
    worst = max(worst, abs(loc.z - float(hf.height_at(x, y))))
check('height_at lands on the rendered surface (ray casts at 400 random points)', misses == 0 and worst < 2e-3,
      f'worst {worst:.2e} m, {misses} misses')



def ray_worst(points, sample, z0=5000.0):
    """Worst |ray-cast surface z - sample(x, y)| over points, and the misses."""
    dg = bpy.context.evaluated_depsgraph_get()
    w, miss = 0.0, 0
    for x, y in points:
        hit, loc, nrm, idx, ob, mat = scene.ray_cast(dg, Vector((x, y, z0)), Vector((0, 0, -1)))
        if not hit:
            miss += 1
            continue
        w = max(w, abs(loc.z - float(sample(x, y))))
    return w, miss


# Ekigar's display grid: side='auto' (terrainVertexSide) and an explicit coarser side, sampled by height_at(side=)
hf2 = ekigar.generate('mountainRange', resolution=96, world_size=1000)
for side, off in ((48, 2000), (37, 4000)):
    o2 = ekigar.build_mesh(hf2, name=f'Range{side}', side=side, location=(0, 0, 0))
    o2.location = (off, 0, 0)
    bpy.context.view_layer.update()
    check(f'a side={side} display grid builds {side}x{side} vertices', len(o2.data.vertices) == side * side)
    pts = rng.uniform(-480, 480, size=(200, 2))
    o2.location = (0, 0, 0)
    obj.hide_viewport = True
    obj.hide_set(True)
    bpy.context.view_layer.update()
    w2, m2 = ray_worst(pts, lambda x, y: hf2.height_at(x, y, side=side))
    check(f'height_at(side={side}) lands on that mesh', m2 == 0 and w2 < 2e-3, f'worst {w2:.2e} m')
    bpy.data.objects.remove(o2, do_unlink=True)
o3 = ekigar.build_mesh(hf2, name='RangeAuto', side='auto', attributes=False)
check("side='auto' follows terrainVertexSide (a 96-texel field gets the 256 floor)",
      len(o3.data.vertices) == ekigar.terrain_vertex_side(96) ** 2, f'{len(o3.data.vertices)} vertices')
bpy.data.objects.remove(o3, do_unlink=True)

# the local area: a crop window across the periodic seam, at full resolution, sampled with wrap=True
cut = ekigar.cut_for(hf2, (480.0, 300.0), radius_m=150.0, fade_m=40.0)
oc = ekigar.build_mesh(hf2, name='Local', crop=cut)
c = cut['crop']
check('a crop mesh has the crop window of vertices', len(oc.data.vertices) == c['w'] * c['h'],
      f"{c['w']}x{c['h']} from texel ({c['x0']}, {c['y0']})")
check('the crop carries its local weight', 'ekigar_local_weight' in oc.data.attributes)
co = np.zeros(len(oc.data.vertices) * 3, dtype=np.float32)
oc.data.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
check('the crop runs past the tile edge (it wraps on a periodic tile)', co[:, 0].max() > 500.0,
      f'x up to {co[:, 0].max():.1f} m on a 1000 m tile')
pts = np.stack([rng.uniform(co[:, 0].min() + 1, co[:, 0].max() - 1, 200),
                rng.uniform(co[:, 1].min() + 1, co[:, 1].max() - 1, 200)], axis=1)
w3, m3 = ray_worst(pts, lambda x, y: hf2.height_at(x, y, wrap=True))
check('height_at(wrap=True) lands on the crop mesh, across the seam', m3 == 0 and w3 < 2e-3, f'worst {w3:.2e} m')
bpy.data.objects.remove(oc, do_unlink=True)


def verts(o):
    c = np.zeros(len(o.data.vertices) * 3, dtype=np.float32)
    o.data.vertices.foreach_get('co', c)
    return c.reshape(-1, 3) + np.array(o.location, dtype=np.float32)


# tiled copies of a periodic tile: wrap=True adds the seam row and column, so copies at multiples of world_size meet
W2 = hf2.world_size
texel2 = W2 / hf2.resolution[0]
for side in (None, 48):
    label = 'full field' if side is None else f'side={side} display grid'
    a = ekigar.build_mesh(hf2, name='TileA', side=side, attributes=False, wrap=True)
    b = ekigar.build_mesh(hf2, name='TileB', side=side, attributes=False, wrap=True, location=(W2, 0, 0))
    n_side = hf2.resolution[0] if side is None else side
    va, vb = verts(a), verts(b)
    check(f'wrap=True ({label}) adds the seam row and column', len(a.data.vertices) == (n_side + 1) ** 2,
          f'{len(a.data.vertices)} vertices')
    ga, gb = va.reshape(n_side + 1, n_side + 1, 3), vb.reshape(n_side + 1, n_side + 1, 3)
    gap = float(np.abs(ga[:, -1, :] - gb[:, 0, :]).max())
    span = float(va[:, 0].max() - va[:, 0].min())
    check(f'wrap=True ({label}): the copies share their seam vertices exactly, and one copy spans world_size',
          gap < 1e-3 and abs(span - W2) < 1e-3, f'seam mismatch {gap:.1e} m, span {span:.4f} m of {W2:.0f}')
    # the wrapped mesh covers [-W/2 + h, W/2 + h] on each axis (h = half a vertex spacing): rays inside it, across
    # the x seam between the copies and along the added row at +y
    h_ = 0.5 * W2 / n_side
    seam_pts = np.stack([rng.uniform(W2 / 2 - 3 * texel2, W2 / 2 + 3 * texel2, 150),
                         rng.uniform(-W2 / 2 + h_ + 0.05, W2 / 2 + h_ - 0.05, 150)], axis=1)
    edge_pts = np.stack([rng.uniform(-W2 / 2 + h_ + 0.05, W2 / 2 + h_ - 0.05, 60),
                         rng.uniform(W2 / 2 - 2 * texel2, W2 / 2 + h_ - 0.05, 60)], axis=1)
    if side is None:
        ws, ms = ray_worst(np.concatenate([seam_pts, edge_pts]), lambda x, y: hf2.height_at(x, y, wrap=True))
    else:
        ws, ms = ray_worst(np.concatenate([seam_pts, edge_pts]),
                           lambda x, y: hf2.height_at(x, y, side=side, wrap=True))
    check(f'wrap=True ({label}): height_at(wrap=True) lands on both copies across the seam, no hole',
          ms == 0 and ws < 2e-3, f'worst {ws:.2e} m, {ms} misses in 210 rays')
    for o in (a, b):
        bpy.data.objects.remove(o, do_unlink=True)
a = ekigar.build_mesh(hf2, name='TileA', attributes=False)
b = ekigar.build_mesh(hf2, name='TileB', attributes=False, location=(W2, 0, 0))
slit = float(verts(b)[:, 0].min() - verts(a)[:, 0].max())
check('without wrap, copies leave a one-texel slit (why wrap exists)', abs(slit - texel2) < 1e-3,
      f'{slit:.4f} m, texel {texel2:.4f} m')
for o in (a, b):
    bpy.data.objects.remove(o, do_unlink=True)

# hydrology masks become attributes once computed; Ekigar's diagnostic preview of one mask
hf2.hydrology()
oh = ekigar.build_mesh(hf2, name='Hydro')
names = {a.name for a in oh.data.attributes}
check('computed hydrology masks are point attributes',
      {'ekigar_' + k for k in ekigar.HYDROLOGY_MASKS} <= names)
bpy.data.objects.remove(oh, do_unlink=True)
mats = [ekigar.preview_material(m) for m in ('grey', 'shaded', 'height', 'slope', 'aspect', 'curvProfile',
                                               'curvPlan', 'ridge', 'mask:channels')]
check('every preview mode (and a mask diagnostic) builds a material', all(m and m.node_tree for m in mats),
      f'{len(mats)} materials')

# lakes: a flat water mesh at each filled depression's spill level, over the ground, grown under the shore
hv = ekigar.generate('volcano', resolution=128, world_size=3000, z_base='min')
H = hv.hydrology()
lk = ekigar.build_lake_mesh(hv, min_depth_m=0.5)
ok = lk is not None
if ok:
    lco = np.zeros(len(lk.data.vertices) * 3, dtype=np.float32)
    lk.data.vertices.foreach_get('co', lco)
    lco = lco.reshape(-1, 3)
    ground = hv.height_at(lco[:, 0], lco[:, 1])
    level = (H['filled'] - hv.z_base) * hv.metres_per_unit
    # every lake vertex is at a lake's level: some filled texel's water surface, to float32
    lv = np.unique(np.round(level[H['lakeDepth_m'] > 1e-9], 2))
    on_level = np.isin(np.round(lco[:, 2].astype(np.float64), 2), lv).mean()
    under = float((lco[:, 2] < ground - 1e-3).mean())
    check('build_lake_mesh lays flat water at the spill levels, running under the shore by one texel',
          on_level > 0.99 and 0 < under < 0.5, f'{len(lk.data.polygons)} quads, {on_level:.1%} on a lake level, '
          f'{under:.1%} of vertices under the ground (the shore ring)')
else:
    check('build_lake_mesh finds the crater lake', False)

# exportGLB: the display grid through Blender's glTF exporter, read back by its importer
out = os.path.join(HERE, 'out', 'glb')
os.makedirs(out, exist_ok=True)
path = ekigar.export_glb(hf2, os.path.join(out, 'mountainRange_96.glb'), side=64)
size = os.path.getsize(path) if os.path.exists(path) else 0
check('export_glb writes a binary glTF', size > 64 * 64 * 12, f'{size} bytes')
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=path)
imported = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
ok = len(imported) == 1
if ok:
    g = imported[0]
    bpy.context.view_layer.update()
    gco = np.array([g.matrix_world @ v.co for v in g.data.vertices])
    xs, ys = hf2.grid_xy(side=64)
    z = hf2.display_z(64)
    want = np.stack([xs.ravel(), ys.ravel(), z.ravel()], axis=1)
    # the importer may reorder vertices: compare as sorted point sets
    a = gco[np.lexsort((gco[:, 2], gco[:, 1], gco[:, 0]))]
    b = want[np.lexsort((want[:, 2], want[:, 1], want[:, 0]))]
    err = float(np.abs(a - b).max()) if a.shape == b.shape else float('inf')
    ok = err < 1e-3
    check('the GLB reads back as the same surface (Z-up restored by the importer)', ok, f'max {err:.2e} m')
else:
    check('the GLB reads back as one mesh', False, f'{len(imported)} meshes')

print(f'blender mesh: {sum(results)}/{len(results)} pass')
