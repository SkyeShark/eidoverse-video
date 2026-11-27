"""eidoblend.sets.same_seed.kitchen.lows: the kitchen's close pieces as lows and their bake, in Blender (Cycles).

    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py kitchen lows --dir <out> [--size 4096] [--quick]
        -> <out>/kitchen_lows.blend, <out>/bake/{table,fronts,fridge}_{normal,ao,cavity,curv,cover,proof}.png

The table, the cupboards' fronts (every door and drawer front) and the refrigerator: each HIGH as built baked onto a
clean LOW DRAWN ON IT, never decimated or remeshed:
  * a part made as boxes and cuts has for its low its own construction without the bevels: the high's base mesh, the
    very planes it was cut from; judged flat-shaded;
  * the table's top is one slab over its boards and breadboard ends (their joints, eased arrises and pegs are baked);
  * a turned leg's low is its own lathe profile (Douglas-Peucker at 0.5 mm) at 16 sides, cut by its square block as the
    high is (16 sides on r 33 is a 0.6 mm sagitta).
UVs: each low unwrapped by planes (smart project), every island brought to its true size, then weighted by what the
lenses see (faces no lens sees at 3-15 %) and packed by the kit's raster packer (eidoblend.props.hardsurface.uv_pack)
with a 16 px gutter at 4096; triangulated before the bake and kept so.
THE BAKE, Blender's Cycles bake on the GPU (OptiX; the CPU without it), part by part, each low against ITS OWN highs
only, cage and ray reach per part: island and hit masks (the coverage proof), tangent normal (OpenGL, MikkTSpace both
ways), ambient occlusion to 80 mm (rigid neighbours in, what may move left out: chairs, homework) and cavity (AO to
4 mm); curvature from the baked normal's divergence, fine (R) and broad (G). Every map dilated 16 px from the nearest
texel a ray really hit. This room's look reads these maps (its curvature thresholds are set on them); the other rooms
bake on the GPU through blender/tools/gpu_bake.py. About 13 minutes at 4096 on a desktop GPU; --quick bakes with a
tenth of the samples (a preview).
"""
import math
import os
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from ....props.hardsurface import uv_pack as UP
from .. import look as L


def main(out_dir, size=4096, quick=False, only=()):
    SIZE, QUICK, ONLY = int(size), bool(quick), [s for s in only if s]
    BAKE = os.path.join(out_dir, 'bake')
    os.makedirs(BAKE, exist_ok=True)
    MM = 1e-3

    def log(*a):
        L.log('kitchen lows', *a)

    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, 'kitchen_high.blend'))
    sc = bpy.context.scene
    ROOM = bpy.data.collections['kitchen_room']
    LOWS = bpy.data.collections.new('kitchen_lows')
    sc.collection.children.link(LOWS)
    OB = bpy.data.objects

    # ============================================================================================ THE LOWS
    # (the table's leg profile, table.py's own: the low is drawn from the same profile)
    LEG = [(0.0, 0.0), (17.0, 0.0), (20.0, 4.0), (22.0, 30.0), (21.0, 44.0), (17.5, 52.0), (16.0, 58.0), (18.5, 64.0), (24.0, 70.0), (26.0, 78.0), (24.5, 86.0), (20.5, 92.0), (19.5, 98.0),
           (20.5, 120.0), (25.0, 240.0), (29.5, 380.0), (32.5, 450.0), (33.0, 480.0), (31.5, 502.0), (27.0, 516.0), (24.0, 524.0), (26.5, 531.0), (31.0, 535.5), (33.5, 541.0), (32.0, 547.0),
           (28.0, 551.5), (27.0, 556.0), (29.0, 560.5), (36.0, 566.0), (60.0, 574.0), (60.0, 712.0), (0.0, 712.0)]
    TABLE_Z0 = 710.0                                              # the legs' blocks end under the top


    def new_obj(name, bm):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(name, me)
        LOWS.objects.link(o)
        return o


    def base_low(hname):
        """the high's own construction without its bevel (its base mesh: the planes it was cut from)"""
        h = OB[hname]
        me = h.data.copy()
        me.name = hname + '_low'
        me.materials.clear()
        o = bpy.data.objects.new(hname + '_low', me)
        o.matrix_world = h.matrix_world.copy()
        LOWS.objects.link(o)
        o['bake_from'] = [hname]
        return o


    def box_low(name, lo, hi, frm):
        bm = bmesh.new()
        x0, y0, z0 = [v * MM for v in lo]
        x1, y1, z1 = [v * MM for v in hi]
        v = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            bm.faces.new([v[i] for i in f])
        o = new_obj(name, bm)
        o['bake_from'] = frm
        return o


    def dp(pts, tol):
        """Douglas-Peucker: the profile's points that matter at tol (mm)"""
        if len(pts) < 3:
            return list(pts)
        a, b = Vector(pts[0]), Vector(pts[-1])
        ab = b - a
        best, bi = -1.0, 0
        for i in range(1, len(pts) - 1):
            p = Vector(pts[i])
            d = abs(ab.x * (p.y - a.y) - ab.y * (p.x - a.x)) / max(ab.length, 1e-9)
            if d > best:
                best, bi = d, i
        if best <= tol:
            return [pts[0], pts[-1]]
        return dp(pts[:bi + 1], tol)[:-1] + dp(pts[bi:], tol)


    def leg_low(hname, cx, cy, seg=16):
        prof = dp(LEG[1:-1], 0.5)                                 # (the two points on the axis are the caps)
        bm = bmesh.new()
        rings = []
        for r, z in prof:
            rings.append([bm.verts.new(((cx + r * math.cos(2 * math.pi * k / seg)) * MM, (cy + r * math.sin(2 * math.pi * k / seg)) * MM, z * MM)) for k in range(seg)])
        for ra, rb in zip(rings, rings[1:]):
            for k in range(seg):
                bm.faces.new((ra[k], ra[(k + 1) % seg], rb[(k + 1) % seg], rb[k]))
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
        lathe = new_obj(hname + '_lathe', bm)
        blk = box_low(hname + '_low', (cx - 35.0, cy - 35.0, 0.0), (cx + 35.0, cy + 35.0, TABLE_Z0), [hname])
        m = blk.modifiers.new('cut', 'BOOLEAN')
        m.operation, m.object, m.solver = 'INTERSECT', lathe, 'EXACT'
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(blk.evaluated_get(dg))
        blk.modifiers.remove(m)
        old = blk.data
        blk.data = me
        me.name = hname + '_low'
        bpy.data.meshes.remove(old)
        bpy.data.objects.remove(lathe, do_unlink=True)
        log(f'{hname}: profile {len(LEG)} -> {len(prof)} stations at 0.5 mm, {seg} sides; low {len(me.polygons)} faces')
        return blk


    ATLAS = {}                                                     # low name -> atlas
    CAGE = {}                                                      # low name -> (cage mm, ray mm)


    def add(o, atlas, cage, ray):
        ATLAS[o.name], CAGE[o.name] = atlas, (cage, ray)


    if not ONLY or 'table' in ONLY:
        add(box_low('table_top_low', (150.0, -901.0, 710.0), (1650.0, 1.0, 740.0), ['table_top_boards', 'table_top_breadboard_0', 'table_top_breadboard_1', 'table_pegs']), 'table', 4.0, 9.0)
        for n in ('00', '01', '10', '11'):
            cx_ = 900.0 + (640.0 if n[0] == '1' else -640.0)
            cy_ = -450.0 + (370.0 if n[1] == '1' else -370.0)
            add(leg_low(f'table_leg_{n}', cx_, cy_), 'table', 2.0, 4.0)
        for n in ('table_apron_long_0', 'table_apron_long_1', 'table_apron_short_0', 'table_apron_short_1'):
            add(base_low(n), 'table', 2.5, 5.0)
    FRONTS = sorted(o.name for o in ROOM.objects if o.name.endswith('_fronts'))
    if not ONLY or 'fronts' in ONLY:
        for n in FRONTS:
            add(base_low(n), 'fronts', 1.5, 3.5)
    if not ONLY or 'fridge' in ONLY:
        add(base_low('fridge_case'), 'fridge', 2.5, 6.0)
        add(base_low('fridge_door_lower'), 'fridge', 3.0, 13.0)
        add(base_low('fridge_door_upper'), 'fridge', 3.0, 13.0)
    lows = [OB[n] for n in ATLAS]

    # shading: a hard-surface low reads clean flat-shaded; a turned leg is smooth round its axis and hard where the profile
    # turns sharply or meets its block (hard edges by role)
    for o in lows:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        turned = o.name.startswith('table_leg')
        for f in bm.faces:
            f.smooth = turned
        for e in bm.edges:
            e.smooth = not (len(e.link_faces) != 2 or e.calc_face_angle(0.0) > math.radians(40.0 if turned else 1.0))
        bm.to_mesh(o.data)
        bm.free()

    # ============================================================================================ UVs
    def weight(name, c, n):
        """texels where the lens looks: c the face's centre (mm), n its normal"""
        if name == 'table_top_low':
            return 1.0 if n.z > 0.9 else (0.12 if n.z < -0.9 else 0.7)
        if name.startswith('table_leg'):
            return 0.05 if abs(n.z) > 0.9 and (c.z > TABLE_Z0 - 1.0 or c.z < 1.0) else 0.55
        if name.startswith('table_apron'):
            if n.z > 0.9:
                return 0.05                                        # under the top
            inner = (Vector((900.0, -450.0, 0.0)) - Vector((c.x, c.y, 0.0))).dot(Vector((n.x, n.y, 0.0))) > 0.0
            return 0.25 if inner or n.z < -0.9 else 0.6
        if name.endswith('_fronts_low'):
            return 0.05 if n.y > 0.9 else 1.0                      # (the backs face into the cupboards)
        if name == 'fridge_case_low':
            if n.y > 0.9 or n.z < -0.9:
                return 0.03
            if n.x > 0.9:
                return 0.08                                        # 66 mm from the right wall
            if n.z > 0.9:
                return 0.15                                        # above every lens (1.4-1.55 m)
            if n.y < -0.9:
                return 0.25                                        # behind the doors but for their gaps
            return 1.0                                             # its left side faces the room
        if name.startswith('fridge_door'):
            return 0.05 if n.y > 0.9 else (1.0 if n.y < -0.9 else 0.8)
        return 1.0


    def edit(objs, fn):
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        fn()
        bpy.ops.object.mode_set(mode='OBJECT')


    def true_size(o):
        """every island's UVs at its own size in metres (smart project scales each object's islands to its own square)"""
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        uv = bm.loops.layers.uv.active
        for faces in UP.islands_of(bm, uv):
            a3 = sum(bm.faces[i].calc_area() for i in faces)
            a2 = 0.0
            for i in faces:
                ls = [lp[uv].uv for lp in bm.faces[i].loops]
                for j in range(1, len(ls) - 1):
                    a2 += abs((ls[j].x - ls[0].x) * (ls[j + 1].y - ls[0].y) - (ls[j].y - ls[0].y) * (ls[j + 1].x - ls[0].x)) * 0.5
            s = math.sqrt(a3 / max(a2, 1e-12))
            for i in faces:
                for lp in bm.faces[i].loops:
                    lp[uv].uv = lp[uv].uv * s
        bm.to_mesh(o.data)
        bm.free()


    by_atlas = {}
    for o in lows:
        by_atlas.setdefault(ATLAS[o.name], []).append(o)
    for atlas, objs in by_atlas.items():
        for o in objs:
            if 'atlas' not in o.data.uv_layers:
                o.data.uv_layers.new(name='atlas')
            o.data.uv_layers.active = o.data.uv_layers['atlas']
            edit([o], lambda: bpy.ops.uv.smart_project(angle_limit=math.radians(60.0), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False))
            true_size(o)
        fw = {}
        for o in objs:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            fw[o.name] = [weight(o.name, f.calc_center_median() / MM, f.normal) for f in bm.faces]
            bm.free()
        t1 = time.time()
        cov = UP.pack(objs, fw, N=1024, gutter=4, log=log)
        log(f'{atlas}: {len(objs)} lows packed in {time.time() - t1:.1f} s, {cov * 100:.1f} % of the square')
        # (00.31: triangulate once, bake on those triangles and ship them)
        for o in objs:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
            bm.to_mesh(o.data)
            bm.free()
        # texel density on the faces the lens sees most (px per m), measured
        for o in objs:
            me = o.data
            uvd = me.uv_layers['atlas'].data
            best = 0.0
            for p in me.polygons:
                if p.area < 1e-6:
                    continue
                l = list(p.loop_indices)
                a, b, c = (Vector(uvd[i].uv) for i in l[:3])
                a2 = abs((b - a).cross(c - a)) * 0.5 * SIZE * SIZE
                best = max(best, math.sqrt(a2 / p.area))
            o['px_per_m'] = round(best)
        log(f'{atlas}: densest face per low (px/m at {SIZE}): ' + ', '.join(f'{o.name}={o["px_per_m"]}' for o in objs))

    # ============================================================================================ THE BAKE (GPU)
    sc.render.engine = 'CYCLES'
    pr = bpy.context.preferences.addons['cycles'].preferences
    pr.compute_device_type = 'OPTIX'
    pr.get_devices()
    for d in pr.devices:
        d.use = d.type == 'OPTIX'
    log('devices:', [(d.name, d.type, d.use) for d in pr.devices])
    sc.cycles.device = 'GPU'
    sc.cycles.use_denoising = False
    sc.cycles.use_auto_tile = False                                # (one buffer: no tile files written)
    sc.render.bake.margin = 0                                      # (never per batch: dilated once, below)
    sc.world = sc.world or bpy.data.worlds.new('bake')
    for o in lows:
        for attr in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter', 'visible_shadow'):
            setattr(o, attr, False)                                # (a low must never shade its own high's AO)
    white = bpy.data.materials.new('bake_white')
    white.use_nodes = True
    _n = white.node_tree.nodes
    for n in list(_n):
        if n.type != 'OUTPUT_MATERIAL':
            _n.remove(n)
    _em = _n.new('ShaderNodeEmission')
    _em.inputs['Color'].default_value, _em.inputs['Strength'].default_value = (1, 1, 1, 1), 1.0
    white.node_tree.links.new(_em.outputs[0], next(n for n in _n if n.type == 'OUTPUT_MATERIAL').inputs[0])

    # what shades each atlas's AO: its highs and their rigid neighbours; everything else is off for those passes
    NEIGH = {
        'table': ['table_'],
        'fronts': ['base_', 'wall_a', 'wall_b', 'wall_c', 'wall_d', 'wall_over', 'worktop', 'cupboard_', 'sink', 'dishwasher', 'cooker', 'hood', 'toe_kick', 'soffit', 'wall_back',
                   'room_floor', 'fridge_case', 'fridge_door', 'wall_filler', 'base_filler', 'base_end_foot'],
        'fridge': ['fridge_case', 'fridge_door', 'fridge_handle', 'fridge_hinge', 'fridge_gasket', 'fridge_grille', 'fridge_feet', 'wall_right', 'wall_back', 'room_floor', 'base_c_',
                   'wall_over_fridge', 'worktop_right', 'wall_filler_right', 'base_end_foot'],
    }
    HIGHS_ALL = [o for o in ROOM.objects if o.type == 'MESH']
    PASSES = [('island', 'EMIT', 1, None), ('hit', 'EMIT', 4, None), ('normal', 'NORMAL', 4 if QUICK else 16, None),
              ('ao', 'AO', 16 if QUICK else 160, 0.08), ('cavity', 'AO', 16 if QUICK else 96, 0.004)]


    def pixels(img):
        a = np.empty(SIZE * SIZE * 4, np.float32)
        img.pixels.foreach_get(a)
        return a.reshape(SIZE, SIZE, 4)


    def save_png(arr, path, srgb=False):
        H_, W_ = arr.shape[:2]
        out = bpy.data.images.new(os.path.basename(path), W_, H_, alpha=False)
        out.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
        rgba = np.ones((H_, W_, 4), np.float32)
        rgba[..., :arr.shape[2]] = arr
        out.pixels.foreach_set(rgba.ravel())
        out.filepath_raw, out.file_format = path + '.tmp.png', 'PNG'
        out.save()
        os.replace(path + '.tmp.png', path)
        bpy.data.images.remove(out)


    def dilate(a, v, n):
        """fill texels no ray hit from their hit neighbours, n rings out (the gutter and any miss inside an island)"""
        a, v = a.copy(), v.copy()
        for _ in range(n):
            acc = np.zeros_like(a)
            cnt = np.zeros(v.shape, np.float32)
            for sh in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                vs = np.roll(v, sh, (0, 1))
                acc += np.roll(a, sh, (0, 1)) * vs[..., None]
                cnt += vs
            new = (~v) & (cnt > 0)
            a[new] = acc[new] / cnt[new][:, None]
            v |= new
        return a, v


    def blur(x, r):
        """separable box blur of radius r (texels)"""
        if r <= 0:
            return x
        for ax in (0, 1):
            c = np.cumsum(np.pad(x, [(r + 1, r) if i == ax else (0, 0) for i in range(x.ndim)], mode='edge'), axis=ax)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[ax]), axis=ax)
            lo = np.take(c, np.arange(0, c.shape[ax] - 2 * r - 1), axis=ax)
            x = (hi - lo) / (2 * r + 1)
        return x


    for atlas, objs in by_atlas.items():
        ta = time.time()
        names = {o.name for o in objs}
        srcs = {o.name: [OB[h] for h in o['bake_from']] for o in objs}
        neigh = [h for h in HIGHS_ALL if any(h.name.startswith(p) for p in NEIGH[atlas])]
        imgs = {}
        for pname, *_ in PASSES:
            img = bpy.data.images.new(f'{atlas}_{pname}', SIZE, SIZE, alpha=True, float_buffer=True)
            img.colorspace_settings.name = 'Non-Color'
            img.generated_color = (0.0, 0.0, 0.0, 0.0)
            imgs[pname] = img
        mat = bpy.data.materials.new(f'bake_{atlas}')
        mat.use_nodes = True
        N_ = mat.node_tree.nodes
        for n in list(N_):
            if n.type != 'OUTPUT_MATERIAL':
                N_.remove(n)
        em = N_.new('ShaderNodeEmission')
        em.inputs['Color'].default_value, em.inputs['Strength'].default_value = (1, 1, 1, 1), 1.0
        mat.node_tree.links.new(em.outputs[0], next(n for n in N_ if n.type == 'OUTPUT_MATERIAL').inputs[0])
        tgt = N_.new('ShaderNodeTexImage')
        N_.active = tgt
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(mat)
        # ONE bake object per cage group: every bake call re-syncs the scene, so the group's lows are duplicated and joined
        # by Blender's own join (UVs and sharp edges kept); their highs stay the originals (their custom normals intact),
        # selected together. No high of one member lies within another member's cage and ray reach.
        groups = {}
        for o in objs:
            groups.setdefault(CAGE[o.name], []).append(o)
        batches = []
        for (cage, ray), members in groups.items():
            dup = []
            for o in members:
                c = o.copy()
                c.data = o.data.copy()
                LOWS.objects.link(c)
                dup.append(c)
            bpy.ops.object.select_all(action='DESELECT')
            for c in dup:
                c.select_set(True)
            bpy.context.view_layer.objects.active = dup[0]
            bpy.ops.object.join()
            j = bpy.context.view_layer.objects.active
            j.name = f'BAKELOW_{atlas}_{len(batches)}'
            batches.append((j, [h for o in members for h in srcs[o.name]], cage, ray))
        names = {b[0].name for b in batches}
        log(f'{atlas}: {len(objs)} lows in {len(batches)} bake batches')
        for pname, btype, samples, dist in PASSES:
            tgt.image = imgs[pname]
            sc.cycles.samples = samples
            if dist:
                sc.world.light_settings.distance = dist
            # who is in the scene's rays for this pass: the highs of this atlas always; for AO also their neighbours
            keep = {h.name for hs_ in srcs.values() for h in hs_}
            if btype == 'AO':
                keep |= {h.name for h in neigh}
            for h in HIGHS_ALL:
                h.hide_render = h.name not in keep
            for o in list(LOWS.objects):
                o.hide_render = o.name not in names
            if pname == 'hit':
                for h in HIGHS_ALL:
                    if h.name in keep and h.material_slots:
                        h.material_slots[0].link = 'OBJECT'
                        h.material_slots[0].material = white
            tp = time.time()
            for o, hs_, cage, ray in batches:
                bpy.ops.object.select_all(action='DESELECT')
                kw = dict(type=btype, margin=0, use_clear=False, target='IMAGE_TEXTURES')
                if pname != 'island':
                    for h in hs_:
                        h.select_set(True)
                    kw.update(use_selected_to_active=True, cage_extrusion=cage * MM, max_ray_distance=ray * MM)
                else:
                    kw.update(use_selected_to_active=False)
                if btype == 'NORMAL':
                    kw.update(normal_space='TANGENT', normal_r='POS_X', normal_g='POS_Y', normal_b='POS_Z')
                o.select_set(True)
                bpy.context.view_layer.objects.active = o
                bpy.ops.object.bake(**kw)
            if pname == 'hit':
                for h in HIGHS_ALL:
                    if h.material_slots and h.material_slots[0].link == 'OBJECT':
                        h.material_slots[0].material = None
                        h.material_slots[0].link = 'DATA'
            log(f'{atlas} {pname:7s} {len(objs)} lows, {samples} samples: {time.time() - tp:5.1f} s')
        # ---------------------------------------------------------------- the proof and the maps
        I = pixels(imgs['island'])[..., 0] > 0.5
        Hm = (pixels(imgs['hit'])[..., 0] > 0.5) & I
        miss = I & ~Hm
        log(f'{atlas}: islands {I.mean() * 100:.1f} % of the square; rays hit their high on {Hm.sum() / max(I.sum(), 1) * 100:.2f} % of island texels; '
            f'missed {miss.sum()} texels ({miss.sum() / max(I.sum(), 1) * 100:.3f} %)')
        nrm = pixels(imgs['normal'])[..., :3]
        n3 = nrm * 2.0 - 1.0
        back = (n3[..., 2] < 0.0) & Hm
        log(f'{atlas}: normal texels facing away from their face {back.sum()} ({back.sum() / max(Hm.sum(), 1) * 100:.3f} %)')
        nrm, _ = dilate(nrm, Hm, 16)
        n3 = nrm * 2.0 - 1.0
        n3 /= np.maximum(np.linalg.norm(n3, axis=-1, keepdims=True), 1e-6)          # (00.32: renormalise what was blended)
        nrm = n3 * 0.5 + 0.5
        save_png(nrm, os.path.join(BAKE, f'{atlas}_normal.png'))
        ao, _ = dilate(pixels(imgs['ao'])[..., :1], Hm, 16)
        cav, _ = dilate(pixels(imgs['cavity'])[..., :1], Hm, 16)
        # curvature: the divergence of the baked normal in the island's own UV frame (MikkTSpace: x along u, y along v);
        # zero where a neighbour lies off the island (a seam is not an edge)
        inner = I & np.roll(I, 1, 0) & np.roll(I, -1, 0) & np.roll(I, 1, 1) & np.roll(I, -1, 1)
        div = 0.5 * (np.roll(n3[..., 0], -1, 1) - np.roll(n3[..., 0], 1, 1)) + 0.5 * (np.roll(n3[..., 1], -1, 0) - np.roll(n3[..., 1], 1, 0))
        div[~inner] = 0.0
        fine = np.clip(blur(div, 1) * 2.5, -1.0, 1.0)
        broad = np.clip(blur(div, 6) * 12.0, -1.0, 1.0)
        curv = np.stack([0.5 + 0.5 * fine, 0.5 + 0.5 * broad, np.zeros_like(fine)], -1)
        curv, _ = dilate(curv, inner, 16)
        save_png(np.concatenate([ao, ao, ao], -1), os.path.join(BAKE, f'{atlas}_ao.png'))
        save_png(np.concatenate([cav, cav, cav], -1), os.path.join(BAKE, f'{atlas}_cavity.png'))
        save_png(curv, os.path.join(BAKE, f'{atlas}_curv.png'))
        cover = np.stack([miss.astype(np.float32), Hm.astype(np.float32), np.zeros(I.shape, np.float32)], -1)
        save_png(cover, os.path.join(BAKE, f'{atlas}_cover.png'))
        k = SIZE // 1024
        tiles = [nrm, np.concatenate([ao] * 3, -1), np.concatenate([cav] * 3, -1), curv, cover]
        proof = np.concatenate([t.reshape(1024, k, 1024, k, 3).mean((1, 3)) for t in tiles], 1)
        save_png(proof, os.path.join(BAKE, f'{atlas}_proof.png'))
        for img in imgs.values():
            bpy.data.images.remove(img)
        for b in batches:
            bpy.data.objects.remove(b[0], do_unlink=True)
        for o in objs:
            o.data.materials.clear()
        log(f'{atlas}: maps written in {time.time() - ta:.1f} s')

    # ------------------------------------------------------------------------------------------------- the file
    # the lows stand in the room; the highs they were baked from leave (the maps hold what they gave)
    gone = {h for o in lows for h in o['bake_from']}
    for o in lows:
        for attr in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter', 'visible_shadow'):
            setattr(o, attr, True)
        o.hide_render = False
        o['atlas'] = ATLAS[o.name]
        del o['bake_from']
        LOWS.objects.unlink(o)
        ROOM.objects.link(o)
    for n in gone:
        bpy.data.objects.remove(OB[n], do_unlink=True)
    for h in ROOM.objects:
        h.hide_render = False
    bpy.data.collections.remove(LOWS)
    for m in [m for m in bpy.data.materials if m.name.startswith('bake_')]:
        bpy.data.materials.remove(m)
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)
    sc.render.engine = 'BLENDER_EEVEE'
    log(f'{len(lows)} lows: ' + ', '.join(f'{o.name} {len(o.data.polygons)} tris' for o in lows))
    return L.save(os.path.join(out_dir, 'kitchen_lows.blend'))

