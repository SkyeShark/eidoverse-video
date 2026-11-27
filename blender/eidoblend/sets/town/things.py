"""eidoblend.sets.town.things: what a lived-in town leaves about, from CC0 models. Blender; the layout calls
place(collection, parent, rng, strikes, ystreets, mosque) after the masks.

Poly Haven's scanned and authored models, fetched by ID into the shared library on first use (eidoverse/assets/cache/
models/<id>_<res>, harness.assets.fetch_model_file; each keeps its .license.json beside it): the white monobloc chair
on the roofs and in the yards, the gas cylinder by the kitchen door, plastic and steel jerrycans, steel drums, an old
tyre on a roof, a car under its cover in a yard, a cardboard box, a bin; and, in a town built with damage, concrete
road barriers where the road was closed and burnt tyres in the street. Each is placed where such a thing is put: by
the dishes on the roofs people use, in the yards, by the shop fronts and the kerbs. Each model's parts are joined into
ONE mesh placed many times; its own Poly Haven material is kept, with the town's dust laid over what faces up and,
near a strike, more of it. Nothing is decimated: each kind is thinned to its share of the face budget instead (KEEP).
"""
import math

import bpy
from mathutils import Matrix, Vector

# key: (Poly Haven ID, resolution)
LIB = {
    'chair': ('plastic_monobloc_chair_01', '1k'), 'lpg': ('small_lpg_tank', '1k'), 'jerry_p': ('plastic_jerrycan', '1k'),
    'jerry_m': ('metal_jerrycan_green', '1k'), 'drum': ('Barrel_02', '1k'), 'barrel': ('barrel_03', '1k'),
    'tyre': ('old_tyre', '1k'), 'barrier': ('concrete_road_barrier', '1k'), 'covered_car': ('covered_car', '1k'),
    'box': ('cardboard_box_01', '1k'), 'bin': ('metal_trash_can', '2k'),
}
DUST = (0.37, 0.315, 0.23, 1.0)
# THE BUDGET: the full town (840 x 300 m) holds 8 to 10 M placed faces (SeedThree's yard trees the difference), about
# 3.7 M of them the buildings and streets. The gas tank, the box and the barrier are dense scans (15 k, 17 k and 61 k
# faces each), so each kind is kept at a share of its placings (KEEP: the chance a placing is kept): about 270 chairs,
# 45 gas cylinders, 100 cans, 110 tyres, 75 drums, 20 boxes, 20 bins and a few covered cars in the full town, about
# 4 M faces; with damage, barriers and burnt tyres where the roads were closed.
KEEP = {'chair': 0.40, 'lpg': 0.19, 'box': 0.10, 'jerry_p': 0.39, 'jerry_m': 0.44, 'tyre': 0.8, 'bin': 0.4, 'barrier': 0.5}


def _dust_over(m):
    """the town's dust over a Poly Haven material's own colour: on what faces up, broken by noise; thicker near a strike"""
    if m is None or not m.use_nodes or m.get('tl_dusted'):
        return
    nt = m.node_tree
    bs = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bs is None:
        return
    N, L = nt.nodes, nt.links
    src = bs.inputs['Base Color'].links[0].from_socket if bs.inputs['Base Color'].is_linked else None
    geo = N.new('ShaderNodeNewGeometry')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(geo.outputs['Normal'], sep.inputs[0])
    up = N.new('ShaderNodeMapRange')
    up.interpolation_type = 'SMOOTHSTEP'
    up.inputs[1].default_value, up.inputs[2].default_value = 0.45, 0.95
    L.new(sep.outputs[2], up.inputs[0])
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value, nz.inputs['Detail'].default_value = 6.0, 3.0
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    at = N.new('ShaderNodeAttribute')
    at.attribute_type, at.attribute_name = 'OBJECT', 'tn_dust'
    a1 = N.new('ShaderNodeMath')
    a1.operation = 'MULTIPLY_ADD'                                     # up * (0.45 + 0.4 near) ...
    L.new(at.outputs['Fac'], a1.inputs[0])
    a1.inputs[1].default_value, a1.inputs[2].default_value = 0.4, 0.45
    a2 = N.new('ShaderNodeMath')
    a2.operation = 'MULTIPLY'
    L.new(up.outputs[0], a2.inputs[0])
    L.new(a1.outputs[0], a2.inputs[1])
    a3 = N.new('ShaderNodeMath')
    a3.operation = 'MULTIPLY_ADD'                                     # ... + (noise - 0.5) * 0.5 + 0.08
    L.new(nz.outputs['Fac'], a3.inputs[0])
    a3.inputs[1].default_value, a3.inputs[2].default_value = 0.5, -0.17
    a4 = N.new('ShaderNodeMath')
    a4.operation, a4.use_clamp = 'ADD', True
    L.new(a2.outputs[0], a4.inputs[0])
    L.new(a3.outputs[0], a4.inputs[1])
    mx = N.new('ShaderNodeMix')
    mx.data_type = 'RGBA'
    L.new(a4.outputs[0], mx.inputs[0])
    if src is not None:
        L.new(src, mx.inputs[6])
    else:
        mx.inputs[6].default_value = bs.inputs['Base Color'].default_value
    mx.inputs[7].default_value = DUST
    L.new(mx.outputs[2], bs.inputs['Base Color'])
    m['tl_dusted'] = 1


def load(key, log=print):
    """one model's parts joined into one mesh, its feet at the origin -> the mesh (made once in a file); None when the
    model is not in the library and cannot be fetched"""
    me = bpy.data.meshes.get('cc0_' + key)
    if me is not None:
        return me
    from ...harness import assets
    try:
        path = assets.fetch_model_file(*LIB[key])
    except FileNotFoundError as e:
        log(f'[town] CC0 {key}: {e}')
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    parts = [o for o in new if o.type == 'MESH']
    if not parts:
        return None
    import bmesh
    bm = bmesh.new()
    mats = []
    for o in parts:
        tmp = o.data.copy()
        tmp.transform(o.matrix_world)
        slot = {}
        for k, m in enumerate(tmp.materials):
            if m not in mats:
                mats.append(m)
            slot[k] = mats.index(m)
        n0 = len(bm.faces)
        bm.from_mesh(tmp)
        bm.faces.ensure_lookup_table()
        for i in range(n0, len(bm.faces)):
            bm.faces[i].material_index = slot.get(bm.faces[i].material_index, 0)
        bpy.data.meshes.remove(tmp)
    me = bpy.data.meshes.new('cc0_' + key)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
        _dust_over(m)
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    me.transform(Matrix.Translation((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, -min(zs))))
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    me['cc0_size'] = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    log(f'[town] CC0 {key}: {len(me.polygons)} faces, {me["cc0_size"][0]:.2f} x {me["cc0_size"][1]:.2f} x {me["cc0_size"][2]:.2f} m, '
        f'{len(mats)} materials')
    return me


def place(c, parent, rng, strikes, ystreets, mosque, log=print):
    """the things, where such things are put (the town must be linked into the scene: they are set down by ray casts
    on what it built). rng: the town's own stream for them; strikes: [] for an intact town -> {kind: count}"""
    lib = {k: load(k, log) for k in LIB if strikes or k != 'barrier'}
    lib = {k: v for k, v in lib.items() if v is not None}
    Mw = parent.matrix_world.copy() if parent is not None else Matrix.Identity(4)
    Mi = Mw.inverted()
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    counts = {}

    def cast(x, y, z0=40.0):
        """the town's surface under (x, y): (z, its normal, the object hit) in the town's own metres"""
        o_ = Mw @ Vector((x, y, z0))
        hit, loc, nrm, _, ob, _ = sc.ray_cast(dg, o_, (Mw.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized(), distance=z0 + 5.0)
        if not hit:
            return None
        lo = Mi @ loc
        return lo.z, (Mi.to_3x3() @ nrm).normalized(), ob

    def struck(x, y):
        return min((math.hypot(x - sx, y - sy) / sr for sx, sy, sr in strikes), default=1e9)

    def put(key, x, y, z, rot, lie=False, tilt=0.0):
        me = lib.get(key)
        if me is None or rng.random() > KEEP.get(key, 1.0):
            return None
        k = counts.get(key, 0)
        counts[key] = k + 1
        o = bpy.data.objects.new(f'cc0_{key}.{k:04d}', me)
        c.objects.link(o)
        # laid on its side: turned about x, then lifted by half its depth so it rests on the surface, not in it
        o.location = (x, y, z + (me['cc0_size'][1] / 2.0 if lie else 0.0))
        o.rotation_euler = (math.radians(90.0) if lie else tilt, 0.0, rot)
        if parent is not None:
            o.parent = parent
        o['tn_dust'] = max(0.0, min(1.0, 1.15 - struck(x, y) / 1.2))
        return o

    def flat_at(x, y, want_z=None, tol=0.2, names=('bld.', 'town_streets')):
        h = cast(x, y)
        if h is None:
            return None
        z, n, ob = h
        if n.z < 0.92 or not ob.name.startswith(names):
            return None
        if want_z is not None and abs(z - want_z) > tol:
            return None
        return z

    def group(cx, cy, z, kinds, spread, want_z=None, names=('bld.', 'town_streets')):
        """a few things set down together, each checked on the surface it stands on"""
        for kind in kinds:
            for _ in range(6):
                x, y = cx + rng.uniform(-spread, spread), cy + rng.uniform(-spread, spread)
                zz = flat_at(x, y, want_z if want_z is not None else z, 0.12, names)
                if zz is None:
                    continue
                if kind == 'tyre_flat':                              # (the model stands on its tread: 0.6 x 0.16 x 0.6 m)
                    put('tyre', x, y, zz, rng.uniform(0, 6.28), lie=True)
                elif kind == 'tyre_lean':
                    put('tyre', x, y, zz, rng.uniform(0, 6.28), lie=False)
                else:
                    put(kind, x, y, zz, rng.uniform(0, 6.28))
                break
    # ROOFS: by the dishes (they stand on the roofs people use): chairs in twos, a gas cylinder, cans, a drum, a tyre
    dishes = [o for o in c.objects if o.name.startswith('dish.')]
    for d in dishes:
        if rng.random() > 0.42:
            continue
        x0, y0, z0 = d.location.x, d.location.y, d.location.z
        if struck(x0, y0) < 0.7 and rng.random() < 0.7:
            continue
        pick = rng.random()
        if pick < 0.40:
            kinds = ['chair', 'chair'] + (['chair'] if rng.random() < 0.3 else [])
        elif pick < 0.58:
            kinds = ['lpg'] + (['jerry_p'] if rng.random() < 0.5 else [])
        elif pick < 0.74:
            kinds = ['tyre_flat'] + (['tyre_flat'] if rng.random() < 0.4 else [])
        elif pick < 0.88:
            kinds = ['drum'] if rng.random() < 0.5 else ['barrel']
        else:
            kinds = ['box', 'jerry_p']
        a = rng.uniform(0, 6.28)
        r = rng.uniform(1.6, 3.2)
        group(x0 + r * math.cos(a), y0 + r * math.sin(a), z0, kinds, 0.9, want_z=z0, names=('bld.',))
    # YARDS and PAVEMENTS: the street mesh's own faces of each kind
    st = next((o for o in c.objects if o.name == 'town_streets'), None)
    if st is not None:
        me = st.data
        names = [m.name if m else '' for m in me.materials]
        yard = [p for p in me.polygons if names[p.material_index] == 'town.yard' and p.area > 6.0]
        walk = [p for p in me.polygons if names[p.material_index] == 'town.walk' and p.area > 3.0 and p.normal.z > 0.9]
        rng.shuffle(yard)
        rng.shuffle(walk)
        for p in yard[:int(len(yard) * 0.55)]:
            xs = [me.vertices[v].co.x for v in p.vertices]
            ys = [me.vertices[v].co.y for v in p.vertices]
            x0, x1, y0, y1 = min(xs) + 0.6, max(xs) - 0.6, min(ys) + 0.6, max(ys) - 0.6
            if x1 <= x0 or y1 <= y0:
                continue
            cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1)
            pick = rng.random()
            if pick < 0.07 and (x1 - x0) > 5.0 and (y1 - y0) > 2.6 and struck(cx, cy) > 1.0:
                xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
                if all(flat_at(xc + dx, yc + dy, 0.012, 0.08, ('town_streets',)) is not None for dx in (-2.0, 0.0, 2.0) for dy in (-0.7, 0.7)):
                    # (the model is long along y: 1.79 x 4.38 m; a quarter turn lays it along its yard)
                    put('covered_car', xc, yc, 0.012, math.pi / 2 + rng.choice((0.0, math.pi)) + rng.uniform(-0.06, 0.06))
            elif pick < 0.42:
                group(cx, cy, 0.012, ['chair', 'chair'] + (['chair', 'chair'] if rng.random() < 0.25 else []), 0.9, names=('town_streets',))
            elif pick < 0.58:
                group(cx, cy, 0.012, ['lpg', 'lpg'] if rng.random() < 0.3 else ['lpg'], 0.5, names=('town_streets',))
            elif pick < 0.74:
                group(cx, cy, 0.012, ['drum', 'barrel', 'jerry_m'], 0.8, names=('town_streets',))
            elif pick < 0.86:
                group(cx, cy, 0.012, ['tyre_lean', 'tyre_flat'], 0.8, names=('town_streets',))
            else:
                group(cx, cy, 0.012, ['box', 'box', 'jerry_p'], 0.7, names=('town_streets',))
        # by the shop fronts and the kerbs: gas sellers' cylinders, fuel sellers' cans and drums, chairs, boxes, bins
        for p in walk[:int(len(walk) * 0.5)]:
            xs = [me.vertices[v].co.x for v in p.vertices]
            ys = [me.vertices[v].co.y for v in p.vertices]
            z = max(me.vertices[v].co.z for v in p.vertices)
            x0, x1, y0, y1 = min(xs) + 0.4, max(xs) - 0.4, min(ys) + 0.35, max(ys) - 0.35
            if x1 <= x0 or y1 <= y0:
                continue
            for _ in range(1 + int((x1 - x0) * (y1 - y0) / 60.0)):
                cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1)
                pick = rng.random()
                if pick < 0.22:
                    group(cx, cy, z, ['lpg'] * rng.randrange(2, 6), 0.5, names=('town_streets',))
                elif pick < 0.40:
                    group(cx, cy, z, ['jerry_p', 'jerry_p', 'jerry_m', 'drum'][:rng.randrange(2, 5)], 0.6, names=('town_streets',))
                elif pick < 0.62:
                    group(cx, cy, z, ['chair', 'chair'], 0.6, names=('town_streets',))
                elif pick < 0.80:
                    group(cx, cy, z, ['box', 'box', 'box'][:rng.randrange(1, 4)], 0.5, names=('town_streets',))
                else:
                    group(cx, cy, z, ['bin'], 0.3, names=('town_streets',))
    # WHERE THE ROAD WAS CLOSED: barriers across the street near each strike, staggered; burnt tyres in the road
    for sx, sy, sr in strikes:
        yc, wd = min(ystreets, key=lambda s: abs(s[0] - sy))
        bx = sx + rng.choice((-1, 1)) * sr * rng.uniform(0.9, 1.3)
        n_b = int(wd / 1.9)
        for k in range(n_b):
            if rng.random() < 0.2:
                continue
            y = yc - wd / 2 + 1.0 + k * (wd - 2.0) / max(1, n_b - 1)
            z = flat_at(bx, y, None, 0.2, ('town_ground', 'town_streets'))
            if z is not None:
                put('barrier', bx + rng.uniform(-0.15, 0.15), y, z, math.pi / 2 + rng.uniform(-0.12, 0.12))
        for k in range(rng.randrange(2, 6)):
            x, y = sx + rng.uniform(-0.6, 0.6) * sr, yc + rng.uniform(-0.35, 0.35) * wd
            z = flat_at(x, y, None, 0.3, ('town_ground', 'town_streets'))
            if z is not None:
                o = put('tyre', x, y, z, rng.uniform(0, 6.28), lie=True)
                if o is not None:
                    o['tn_dust'] = 1.0
    total = sum(len(lib[k].polygons) * n for k, n in counts.items())
    log(f'CC0 placed {counts}: {total} faces')
    return counts
