"""Rocks and boulders on the terrain (design section 7, dressing): CC0 rock models scattered on the masks where fallen
rock gathers (talus, the foot of exposed rock, stream beds), as Geometry Nodes collection instances, so tens of
thousands of stones cost one mesh each in memory. Vegetation is not imported here: the scene script passes
terrain.mask('vegetation') to the flora family.

    from eidoblend.terrain.build import dressing as D
    rocks = D.scatter_rocks(spec=pal['dressing'], mask_at=lambda n, x, y: ..., height_at=t.height_at,
                            normal_at=t.normal_at, focus=(x, y), radius_m=150, seed=7)
    rocks['collection'], rocks['object'], rocks['count']

How a rock is placed, so the result can be trusted:
- density: the spec's mask expression (palettes.py language) gives the number of rocks per m^2 at least size_m[0]
  across, everywhere in the disc of radius_m around the focus. Candidates are a Poisson draw at the density's maximum
  over the disc, kept with probability density / maximum (rejection sampling: no grid pattern).
- size: a power law between size_m[0] and size_m[1], N(>s) ~ s^-alpha (talus and boulder fields measure alpha 2-3).
  The smallest size kept grows with distance from the focus (lod_m_per_m metres per metre), so far ground keeps
  only the rocks a camera could resolve, at the same density of big rocks as near ground.
- each rock stands on height_at, a `bury` fraction of its height under the ground, its up axis turned `align` of the
  way from world up to the surface normal, a random turn about it and a few degrees of random tilt; its proportions
  are jittered a little (no two stones alike).
- models: Poly Haven rock models (fetch_model.py <id> --cache --res 1k), each mesh centred on its bounding box and
  measured; `size` is a rock's longest horizontal side. With `colour`, each model's albedo is rescaled from its own
  mean to that colour (as the ground's layers are), so the rocks are the palette's stone.
"""
from __future__ import annotations

import math
import os
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

from . import palettes as P

DEFAULT_SPEC = dict(models=['boulder_01', 'rock_07', 'rock_09'], colour=None, density='0.0',
                    size_m=(0.12, 2.5), alpha=2.4, bury=0.35, align=0.6, tilt_deg=8.0, squash=(0.7, 1.05),
                    radius_m=150.0, lod_m_per_m=0.01, max_rocks=400000, model_res='1k')
# lod_m_per_m 0.01: a rock d metres off is kept only if it is at least 0.01 d across, about 7 pixels at 960 px over a
# 74-degree view (24 mm) and more at longer lenses: the scanned models are 12-110 k triangles each, so rocks a camera
# cannot resolve are not drawn. A model entry may be (id, min_size_m, max_size_m): the heavy boulder scans then stand
# only for big rocks and the light ones for stones.
SOURCE_COLLECTION = 'eido_rock_models'


# ------------------------------------------------------------------------------------------- the models ---

def model_roots():
    """Where cached models are looked for: this checkout's eidoverse/assets/cache/models/, $EIDO_ASSET_CACHE/models,
    then the main checkout's when this one is a git worktree (as _pbr finds textures)."""
    from .. import _pbr
    root = _pbr._checkout_root()
    roots = [root / 'eidoverse' / 'assets' / 'cache' / 'models']
    env = os.environ.get('EIDO_ASSET_CACHE')
    if env:
        roots.append(Path(env) / 'models')
    main = _pbr._main_checkout(root)
    if main:
        roots.append(main / 'eidoverse' / 'assets' / 'cache' / 'models')
    return [r for r in roots if r.is_dir()]


def find_model(model_id, res='1k'):
    """The cached glTF of a Poly Haven model id, or FileNotFoundError naming how to fetch it."""
    for r in model_roots():
        for d in (r / f'{model_id}_{res}', *sorted(r.glob(f'{model_id}_*'))):
            if d.is_dir():
                hit = sorted(d.glob('*.gltf')) + sorted(d.glob('*.glb'))
                if hit:
                    return hit[0]
    raise FileNotFoundError(f"rock model {model_id!r} is not in {[str(r) for r in model_roots()]}: "
                            f"python fetch_model.py {model_id} --cache --res {res}")


def _image_mean_linear(img):
    """Mean linear colour of an image (its pixels as Blender holds them, sRGB byte images decoded)."""
    w, h = img.size
    if w * h == 0:
        return None
    px = np.empty(w * h * img.channels, np.float32)
    img.pixels.foreach_get(px)
    rgb = px.reshape(-1, img.channels)[:, :3].astype(np.float64)
    if not img.is_float and img.colorspace_settings.name.lower().startswith('srgb'):
        rgb = P.srgb_to_linear(rgb)
    return rgb.mean(0)


def _recolour(mat, target_linear, contrast=0.55):
    """Rescale a model material's base colour from its own mean to target_linear (channel by channel), on a copy:
    target * (1 + contrast (scan / mean - 1)), as the ground layers' colour rescale does. With contrast under 1 a dark
    scan with a few bright specks (rock_09: mean 0.09, most of it under half that) becomes the target's stone with its
    detail, not a near-black rock with clipped highlights (what a plain rescale made of it on the red desert soil)."""
    if mat is None or not mat.use_nodes:
        return mat
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
    if bsdf is None:
        return mat
    sock = bsdf.inputs['Base Color']
    if not sock.links:                                   # a flat colour: the target itself
        sock.default_value = (*(float(v) for v in np.clip(target_linear, 0, 0.95)), 1.0)
        return mat
    src = sock.links[0].from_socket
    node = src.node
    mean = None
    if node.bl_idname == 'ShaderNodeTexImage' and node.image is not None:
        mean = _image_mean_linear(node.image)
    if mean is None:
        return mat
    c = float(contrast)
    rel = nt.nodes.new('ShaderNodeVectorMath')           # scan / mean
    rel.operation = 'MULTIPLY'
    rel.inputs[1].default_value = tuple(float(v) for v in 1.0 / np.maximum(mean, 1e-4))
    mad = nt.nodes.new('ShaderNodeVectorMath')           # contrast (scan / mean) + (1 - contrast)
    mad.operation = 'MULTIPLY_ADD'
    mad.inputs[1].default_value = (c, c, c)
    mad.inputs[2].default_value = (1.0 - c, 1.0 - c, 1.0 - c)
    out = nt.nodes.new('ShaderNodeVectorMath')           # x target
    out.operation = 'MULTIPLY'
    out.inputs[1].default_value = tuple(float(v) for v in np.clip(target_linear, 0.0, 0.95))
    for k, n in enumerate((rel, mad, out)):
        n.location = (bsdf.location.x - 660 + 220 * k, bsdf.location.y)
    nt.links.new(src, rel.inputs[0])
    nt.links.new(rel.outputs[0], mad.inputs[0])
    nt.links.new(mad.outputs[0], out.inputs[0])
    nt.links.new(out.outputs[0], sock)
    return mat


def _matte(mat, rough_min=0.6):
    """Hold a model material's roughness at rough_min or more: the small rock scans pack a low roughness (rock_07's
    averages 0.30), so under make_sky they mirrored the blue sky and read as black glossy pebbles on dry ground."""
    if mat is None or not mat.use_nodes:
        return mat
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
    if bsdf is None:
        return mat
    sock = bsdf.inputs['Roughness']
    if not sock.links:
        sock.default_value = max(float(sock.default_value), float(rough_min))
        return mat
    src = sock.links[0].from_socket
    mx = nt.nodes.new('ShaderNodeMath')
    mx.operation = 'MAXIMUM'
    mx.inputs[1].default_value = float(rough_min)
    mx.location = (bsdf.location.x - 220, bsdf.location.y - 260)
    nt.links.new(src, mx.inputs[0])
    nt.links.new(mx.outputs[0], sock)
    return mat


def model_entries(models):
    """[(id, min_size_m, max_size_m)] from a spec's models: ids, or (id, min, max) tuples."""
    out = []
    for m in models:
        if isinstance(m, str):
            out.append((m, 0.0, float('inf')))
        else:
            out.append((str(m[0]), float(m[1]), float(m[2]) if len(m) > 2 else float('inf')))
    return out


def load_models(model_ids, colour=None, res='1k', log=print):
    """Import (once per id and colour) the rock models into the unlinked source collection, each mesh baked to world
    space and centred on its bounding box. model_ids: ids or (id, min_size_m, max_size_m). Returns (collection,
    [dict(object, dims (dx, dy, dz), id, sizes (min, max))])."""
    entries = model_entries(model_ids)
    rng_of = {e[0]: (e[1], e[2]) for e in entries}
    ids = [e[0] for e in entries]
    key = (colour or 'scan').lstrip('#')
    cname = f'{SOURCE_COLLECTION}_{key}'
    coll = bpy.data.collections.get(cname)
    if coll is not None and set(coll.get('eido_ids', [])) >= set(ids):
        return coll, [dict(object=o, dims=tuple(o['eido_dims']), id=o['eido_model'],
                           sizes=rng_of.get(o['eido_model'], (0.0, float('inf'))))
                      for o in coll.objects if o['eido_model'] in rng_of]
    if coll is None:
        coll = bpy.data.collections.new(cname)          # not linked to the scene: only the instances show
    have = {o['eido_model'] for o in coll.objects}
    target = np.array(P.hex_linear(colour)) if colour else None
    out = [dict(object=o, dims=tuple(o['eido_dims']), id=o['eido_model'], sizes=rng_of[o['eido_model']])
           for o in coll.objects if o['eido_model'] in rng_of]
    t0 = time.time()
    for mid in ids:
        if mid in have:
            continue
        path = find_model(mid, res)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path))
        new = [o for o in bpy.data.objects if o not in before]
        meshes = [o for o in new if o.type == 'MESH']
        for o in meshes:
            mw = o.matrix_world.copy()
            o.parent = None
            o.data = o.data.copy() if o.data.users > 1 else o.data
            o.data.transform(mw)
            o.matrix_world.identity()
            co = np.empty(len(o.data.vertices) * 3, np.float32)
            o.data.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3)
            lo, hi = co.min(0), co.max(0)
            c = 0.5 * (lo + hi)
            o.data.transform(Matrix.Translation((-float(c[0]), -float(c[1]), -float(c[2]))))
            dims = tuple(float(v) for v in (hi - lo))
            if target is not None:
                for slot in o.material_slots:
                    if slot.material is not None:
                        m = slot.material.copy()
                        m.name = f'{slot.material.name}_{key}'
                        slot.material = _matte(_recolour(m, target))
            for uc in list(o.users_collection):
                uc.objects.unlink(o)
            coll.objects.link(o)
            o['eido_dims'] = list(dims)
            o['eido_model'] = mid
            o.name = f'rock_{mid}_{len(out)}'
            out.append(dict(object=o, dims=dims, id=mid, sizes=rng_of[mid]))
        for o in new:
            if o.type != 'MESH' and o.name in bpy.data.objects:
                bpy.data.objects.remove(o, do_unlink=True)
    coll['eido_ids'] = sorted(set(coll.get('eido_ids', [])) | set(ids))
    if log:
        log(f'[dressing] {len(out)} rock meshes from {len(ids)} models ({key}) in {time.time() - t0:.1f} s')
    return coll, out


# --------------------------------------------------------------------------------------------- placement ---

def _rotations(up, yaw, tilt_axis_angle, rng_tilt):
    """Euler XYZ (n, 3) of: random yaw about Z, then a small random tilt, then Z turned onto `up`."""
    n = len(up)
    z = np.array([0.0, 0.0, 1.0])
    # Rz(yaw)
    cy, sy = np.cos(yaw), np.sin(yaw)
    Rz = np.zeros((n, 3, 3))
    Rz[:, 0, 0], Rz[:, 0, 1], Rz[:, 1, 0], Rz[:, 1, 1], Rz[:, 2, 2] = cy, -sy, sy, cy, 1.0

    def rodrigues(axis, ang):
        ax = axis / np.maximum(np.linalg.norm(axis, axis=1, keepdims=True), 1e-12)
        K = np.zeros((n, 3, 3))
        K[:, 0, 1], K[:, 0, 2] = -ax[:, 2], ax[:, 1]
        K[:, 1, 0], K[:, 1, 2] = ax[:, 2], -ax[:, 0]
        K[:, 2, 0], K[:, 2, 1] = -ax[:, 1], ax[:, 0]
        s, c = np.sin(ang)[:, None, None], np.cos(ang)[:, None, None]
        return np.eye(3)[None] + s * K + (1 - c) * (K @ K)
    tilt = rodrigues(np.stack([np.cos(tilt_axis_angle), np.sin(tilt_axis_angle), np.zeros(n)], 1), rng_tilt)
    axis = np.cross(np.broadcast_to(z, up.shape), up)
    ang = np.arccos(np.clip(up[:, 2], -1.0, 1.0))
    small = np.linalg.norm(axis, axis=1) < 1e-9
    axis[small] = (1.0, 0.0, 0.0)
    A = rodrigues(axis, ang)
    R = A @ tilt @ Rz
    # Blender 'XYZ' euler: R = Rz(g) Ry(b) Rx(a)
    b = np.arcsin(np.clip(-R[:, 2, 0], -1.0, 1.0))
    a = np.arctan2(R[:, 2, 1], R[:, 2, 2])
    gm = np.arctan2(R[:, 1, 0], R[:, 0, 0])
    return np.stack([a, b, gm], 1)


def _pick(size, ranges, rng):
    """For each rock size, a uniformly random model among those whose (min, max) size range holds it; where none
    does, the model whose range is nearest."""
    lo = np.array([r[0] for r in ranges])
    hi = np.array([r[1] for r in ranges])
    ok = (size[:, None] >= lo[None]) & (size[:, None] <= hi[None])
    gap = np.maximum(lo[None] - size[:, None], 0.0) + np.maximum(size[:, None] - hi[None], 0.0)
    gap = np.where(np.isfinite(lo)[None], gap, np.inf)           # a range of (inf, inf): never this model
    none = ~ok.any(1)
    if none.any():
        ok[none] = gap[none] == gap[none].min(1, keepdims=True)
    u = rng.random(len(size))[:, None] * ok.sum(1, keepdims=True)
    return np.minimum((np.cumsum(ok, 1) <= u).sum(1), len(ranges) - 1).astype(np.int32)


def place_rocks(spec, mask_at, height_at, normal_at=None, focus=(0.0, 0.0), radius_m=None, seed=0, n_models=1,
                model_dims=None, exclude=None, model_sizes=None):
    """The rock instances as arrays (no bpy): dict(xyz (n, 3), euler (n, 3), scale (n, 3), pick (n,), size (n,)).
    model_dims: per model (dx, dy, dz) of its mesh; a rock's size is its longest horizontal side. model_sizes: per
    model the (min, max) rock size it stands for ((inf, inf): never), default all sizes."""
    sp = dict(DEFAULT_SPEC)
    sp.update(spec or {})
    R = float(radius_m if radius_m is not None else sp['radius_m'])
    fx, fy = float(focus[0]), float(focus[1])
    rng = np.random.default_rng(seed)
    tree = P.parse(sp['density'])
    names = P.names_in(tree)

    def dens(x, y):
        ms = {n: mask_at(n, x, y) for n in names}
        d = np.maximum(np.asarray(P.evaluate(tree, ms, x, y), np.float64), 0.0)
        if np.ndim(d) == 0:
            d = np.full(np.shape(x), float(d))
        w = mask_at('water', x, y)
        if w is not None:
            d = d * (np.asarray(w) <= 0.05)
        return d
    # the density's maximum over the disc (a 96 x 96 probe grid), for the Poisson draw
    gx, gy = np.meshgrid(np.linspace(fx - R, fx + R, 96), np.linspace(fy - R, fy + R, 96))
    ins = (gx - fx) ** 2 + (gy - fy) ** 2 <= R * R
    dmax = float(dens(gx[ins], gy[ins]).max()) if ins.any() else 0.0
    if dmax <= 0.0:
        return dict(xyz=np.zeros((0, 3)), euler=np.zeros((0, 3)), scale=np.zeros((0, 3)), pick=np.zeros(0, np.int32),
                    size=np.zeros(0))
    dmax *= 1.25                                         # the probe grid can miss a narrow peak
    n_cand = int(min(rng.poisson(math.pi * R * R * dmax), 40 * sp['max_rocks']))
    r = R * np.sqrt(rng.random(n_cand))
    th = 2 * math.pi * rng.random(n_cand)
    x, y = fx + r * np.cos(th), fy + r * np.sin(th)
    keep = rng.random(n_cand) * dmax < dens(x, y)
    x, y = x[keep], y[keep]
    if exclude:
        ok = np.ones(len(x), bool)
        for ex, ey, er in exclude:
            ok &= (x - ex) ** 2 + (y - ey) ** 2 > er * er
        x, y = x[ok], y[ok]
    # sizes: N(>s) ~ s^-alpha between s0 and s1; thin the small ones with distance
    s0, s1 = (float(v) for v in sp['size_m'])
    al = float(sp['alpha'])
    u = rng.random(len(x))
    size = s0 * (1.0 - u * (1.0 - (s0 / s1) ** al)) ** (-1.0 / al)
    dist = np.hypot(x - fx, y - fy)
    keep = size >= np.maximum(s0, float(sp['lod_m_per_m']) * dist)
    x, y, size = x[keep], y[keep], size[keep]
    if len(x) > sp['max_rocks']:
        sel = rng.choice(len(x), int(sp['max_rocks']), replace=False)
        x, y, size = x[sel], y[sel], size[sel]
    n = len(x)
    if model_sizes is not None:
        pick = _pick(size, model_sizes, rng)
    else:
        pick = rng.integers(0, max(n_models, 1), n).astype(np.int32)
    dims = np.array(model_dims if model_dims is not None else [(1.0, 1.0, 0.6)] * max(n_models, 1), np.float64)
    longest = np.maximum(dims[pick, 0], dims[pick, 1])
    k = size / np.maximum(longest, 1e-6)
    lo, hi = sp['squash']
    sc = np.stack([k * rng.uniform(0.9, 1.1, n), k * rng.uniform(0.9, 1.1, n), k * rng.uniform(lo, hi, n)], 1)
    hgt = dims[pick, 2] * sc[:, 2]
    z = np.asarray(height_at(x, y), np.float64)
    if normal_at is not None:
        nrm = np.asarray(normal_at(x, y), np.float64).reshape(-1, 3)
    else:
        e = 0.5
        dzx = (np.asarray(height_at(x + e, y)) - np.asarray(height_at(x - e, y))) / (2 * e)
        dzy = (np.asarray(height_at(x, y + e)) - np.asarray(height_at(x, y - e))) / (2 * e)
        nrm = np.stack([-dzx, -dzy, np.ones(n)], 1)
    nrm = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    a = float(sp['align'])
    up = (1 - a) * np.array([0.0, 0.0, 1.0]) + a * nrm
    up = up / np.maximum(np.linalg.norm(up, axis=1, keepdims=True), 1e-12)
    eul = _rotations(up, 2 * math.pi * rng.random(n), 2 * math.pi * rng.random(n),
                     np.radians(float(sp['tilt_deg'])) * rng.standard_normal(n))
    zc = z + (0.5 - float(sp['bury'])) * hgt * up[:, 2]
    return dict(xyz=np.stack([x, y, zc], 1), euler=eul, scale=sc, pick=pick, size=size)


# --------------------------------------------------------------------------------------- the instancer ---

def _instancer(name, source):
    """The Geometry Nodes tree: the points object's vertices -> instances of the source collection's children,
    picked by eido_pick, turned by eido_rot (Euler XYZ) and scaled by eido_scale."""
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    ci = N.new('GeometryNodeCollectionInfo')
    ci.transform_space = 'ORIGINAL'
    ci.inputs['Collection'].default_value = source
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True

    def named(attr, dtype):
        n = N.new('GeometryNodeInputNamedAttribute')
        n.data_type = dtype
        n.inputs['Name'].default_value = attr
        return n.outputs['Attribute']
    e2r = N.new('FunctionNodeEulerToRotation')
    L.new(named('eido_rot', 'FLOAT_VECTOR'), e2r.inputs['Euler'])
    iop = N.new('GeometryNodeInstanceOnPoints')
    L.new(gi.outputs['Geometry'], iop.inputs['Points'])
    L.new(ci.outputs['Instances'], iop.inputs['Instance'])
    iop.inputs['Pick Instance'].default_value = True
    L.new(named('eido_pick', 'INT'), iop.inputs['Instance Index'])
    L.new(e2r.outputs['Rotation'], iop.inputs['Rotation'])
    L.new(named('eido_scale', 'FLOAT_VECTOR'), iop.inputs['Scale'])
    L.new(iop.outputs['Instances'], go.inputs['Geometry'])
    return ng


def scatter_rocks(spec=None, *, mask_at, height_at, normal_at=None, focus=(0.0, 0.0), radius_m=None, seed=0,
                  name='terrain_rocks', collection=None, exclude=None, log=print):
    """Scatter a palette's rocks (its 'dressing' spec, DEFAULT_SPEC filled in) around a focus.

    mask_at     callable (name, x, y) -> array of that mask at world points, or None when the terrain lacks it (it
                then reads 0, as the material's Attribute node does)
    height_at   callable (x, y) -> ground metres (Terrain.height_at); normal_at (x, y) -> (n, 3), optional
    focus       (x, y): the centre of the scatter (the camera's ground point, a character's walk)
    radius_m    the disc scattered (default the spec's radius_m)
    exclude     [(x, y, r), ...] discs kept clear (flatten areas, paths)
    Returns dict(collection, object (the points mesh with the instancer), count, sizes (min, max), seconds); the
    collection is linked under `collection` (default the scene's)."""
    t0 = time.time()
    sp = dict(DEFAULT_SPEC)
    sp.update(spec or {})
    coll_src, models = load_models(sp['models'], sp.get('colour'), sp.get('model_res', '1k'), log=log)
    if not models:
        raise RuntimeError(f"no meshes in the rock models {sp['models']}")
    # every child of the source collection in the order Collection Info separates them (alphabetical), so eido_pick
    # indexes them; children this spec does not name are never picked
    mine = {m['object'].name: m for m in models}
    order = sorted(coll_src.objects, key=lambda o: o.name)
    res = place_rocks(sp, mask_at, height_at, normal_at, focus, radius_m, seed, n_models=len(order),
                      model_dims=[tuple(o['eido_dims']) for o in order], exclude=exclude,
                      model_sizes=[mine[o.name]['sizes'] if o.name in mine else (math.inf, math.inf) for o in order])
    n = len(res['pick'])
    out = bpy.data.collections.new(name)
    (collection or bpy.context.scene.collection).children.link(out)
    me = bpy.data.meshes.new(name + '_points')
    me.vertices.add(n)
    if n:
        me.vertices.foreach_set('co', res['xyz'].astype(np.float32).ravel())
    for attr, arr, dtype in (('eido_rot', res['euler'], 'FLOAT_VECTOR'), ('eido_scale', res['scale'], 'FLOAT_VECTOR'),
                             ('eido_pick', res['pick'], 'INT')):
        a = me.attributes.new(attr, dtype, 'POINT')
        if n:
            a.data.foreach_set('vector' if dtype == 'FLOAT_VECTOR' else 'value',
                               np.asarray(arr, np.float32 if dtype != 'INT' else np.int32).ravel())
    me.update()
    obj = bpy.data.objects.new(name, me)
    out.objects.link(obj)
    mod = obj.modifiers.new('rocks', 'NODES')
    mod.node_group = _instancer(name + '_instancer', coll_src)
    obj['eido_rocks'] = dict(count=n, models=[e[0] for e in model_entries(sp['models'])],
                             colour=sp.get('colour') or 'scan',
                             focus=[float(focus[0]), float(focus[1])], seed=int(seed))
    dt = time.time() - t0
    if log:
        sz = (float(res['size'].min()), float(res['size'].max())) if n else (0.0, 0.0)
        log(f'[dressing] {n} rocks ({sz[0]:.2f}-{sz[1]:.2f} m) within {radius_m or sp["radius_m"]:.0f} m of '
            f'({focus[0]:.0f}, {focus[1]:.0f}) in {dt:.1f} s')
    return dict(collection=out, object=obj, count=n,
                sizes=(float(res['size'].min()), float(res['size'].max())) if n else (0.0, 0.0), seconds=dt)


__all__ = ['scatter_rocks', 'place_rocks', 'load_models', 'find_model', 'model_roots', 'DEFAULT_SPEC']
