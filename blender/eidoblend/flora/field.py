"""The Blender half of create_flora: converts the API's Blender coordinates into the WebGPU edition's three space,
plans the stroke (vegetation.plan_flora), and builds it:

  <name>_proto   the plant, grown once per stroke (a hidden mesh, its sheet material; daisies carry the close group)
  <name>         a vertex-only mesh object, one vertex per plant (flora_xform 4x4, root, color_var, phase, head_fix),
                 with the shared 'EB Flora Field' geometry nodes modifier: instance the prototype, realize, wind +
                 pushers + the daisy head fix as real geometry. The object stays at the world origin (the wind and
                 the pushers are evaluated in world space; create_flora places it, do not move it).
"""
import json
import math
import hashlib
import os

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import nodes
from .plantgeo import to_blender_mesh, to_blender, C3B, PlantGeo, merge
from .vegetation import plan_flora, instance_matrices, asset_dir

PROTO_COLLECTION = 'flora_prototypes'
BLADE_CURL = 1.4         # blade cross-section curl in the shader (tan of the edge normal's bend, ~54 deg), t_sheen.py
# blade grasses' roughness x this by default (rough=None): the WebGPU edition's 0.6 x the map (~0.65) is ~0.39, glossy
# for a GGX blade; under a low sun the gust-bent blades of a wide meadow mirror it in crisp white lines that read as
# frost. x1.6 (~0.62, a grass blade's usual PBR roughness) keeps a soft sheen and leaves the look at
# the feet as it was (tests/flora/t_sheen.py --frost)
BLADE_ROUGH = 1.6
PUSHER_COLLECTION = 'flora_pushers'


def _child_collection(name, parent=None, hide=False):
    parent = parent or bpy.context.scene.collection
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if col.name not in parent.children.keys():
        parent.children.link(col)
    if hide:
        col.hide_render = True
    return col


def _surface_sampler(objs):
    """Raycast straight down onto the given objects' evaluated world meshes; returns hits in three space."""
    objs = objs if isinstance(objs, (list, tuple)) else [objs]
    dg = bpy.context.evaluated_depsgraph_get()
    trees = []
    for ob in objs:
        mw = ob.matrix_world.copy()
        # the evaluated mesh in object space (built in C), rays taken into it
        trees.append((BVHTree.FromObject(ob, dg), mw, mw.inverted(), mw.to_3x3().inverted().transposed()))

    def at(x3, z3):
        best = None
        for t, mw, mi, nm in trees:
            o = mi @ Vector((x3, -z3, 1.0e4))
            d = (mi.to_3x3() @ Vector((0, 0, -1))).normalized()
            loc, n, _, _ = t.ray_cast(o, d)
            if loc is not None:
                loc, n = mw @ loc, (nm @ n).normalized()
                if best is None or loc.z > best[0].z:
                    best = (loc, n)
        if best is None:
            return None
        loc, n = best
        n3 = [n.x, n.z, -n.y]
        if n3[1] < 0:
            n3 = [-c for c in n3]
        return {'y': loc.z, 'slope': math.acos(min(1.0, abs(n3[1]))), 'nx': n3[0], 'ny': n3[1], 'nz': n3[2]}
    return at


def _three_opts(kw):
    """The API's Blender-space options -> plan_flora's three-space ones."""
    o = {}
    for k in ('species', 'width', 'depth', 'size', 'seed', 'variant', 'density', 'footprint', 'align', 'max_slope',
              'avoid', 'heading_jitter', 'heading_elevation', 'height', 'head_scale', 'color', 'wind', 'sss', 'close',
              'corn', 'sunflower', 'daisy', 'blades', 'webgpu_heading'):
        if kw.get(k) is not None:
            o[k] = kw[k]
    cx, cy = kw.get('center') or (0.0, 0.0)
    o['center'] = [float(cx), -float(cy)]
    o['y'] = float(kw.get('z') or 0.0)
    hf, cf = kw.get('height_fn'), kw.get('clip_fn')
    if hf:
        o['height_fn'] = lambda x, z: hf(x, -z)
    if cf:
        o['clip_fn'] = lambda x, z: cf(x, -z)
    if kw.get('surface') is not None and not hf:
        o['_surface_at'] = _surface_sampler(kw['surface'])
    if kw.get('placements'):
        o['placements'] = [[p[0], -p[1]] + list(p[2:3]) for p in kw['placements']]
    if kw.get('rows'):
        r = kw['rows'] if isinstance(kw['rows'], dict) else {}
        r = dict(r)
        if 'angle' in r:
            r['angle'] = -r['angle']
        o['rows'] = r or True
    hd = kw.get('heading')
    if hd is not None:
        if isinstance(hd, dict) and 'toward' in hd:
            t = hd['toward']
            o['heading'] = {'toward': [t[0], t[2], -t[1]]}
        elif isinstance(hd, (list, tuple)):
            o['heading'] = [hd[0], hd[2], -hd[1]]
        else:
            o['heading'] = -float(hd)
    return o


def _maps(base):
    d = asset_dir()
    out = {'albedo': nodes.load_map(os.path.join(d, base + '_albedo.png'), True)}
    for key, suffix, color in (('normal', '_normal.png', False), ('rough', '_roughness.png', False),
                               ('transl', '_translucency.png', False)):
        p = os.path.join(d, base + suffix)
        out[key] = nodes.load_map(p, color) if os.path.exists(p) else None
    return out


def _scanned_names(asset, names, lod):
    """A Poly Haven plant set's variant objects at one LOD -> ([(object name, variant name)], the LOD used).
    Sets with LOD objects ('<asset>_<variant>_LOD<n>': grass_medium_01, dandelion_01, ...) give the asked LOD, or the
    nearest one they have (grass_medium_01 stops at LOD2). Single-LOD sets ('<asset>_<variant>': grass_medium_02,
    shrub_sorrel_01) give their one mesh per variant, LOD None. Both skip a set's own geometry-nodes scatter rig and
    its copies of the variants ('<asset>_geonodes_*', '<asset>_geometry_nodes', '<asset>_<variant>_geo')."""
    import re
    a = re.escape(asset)
    lod_pat = re.compile(rf'{a}_(?!geonodes_|geometry_nodes)(.+)_LOD(\d+)$')
    by_lod = {}
    for n in names:
        m = lod_pat.match(n)
        if m:
            by_lod.setdefault(int(m.group(2)), []).append((n, m.group(1)))
    if by_lod:
        use = min(by_lod, key=lambda l: (abs(l - lod), l))
        return by_lod[use], use
    plain = re.compile(rf'{a}_(?!geonodes_|geometry_nodes$)(.+)$')
    out = []
    for n in names:
        m = plain.match(n)
        if m and not m.group(1).endswith('_geo'):
            out.append((n, m.group(1)))
    return out, None


def _scanned_variants(asset, lod=1, which=None):
    """A Poly Haven plant set's variant meshes at one LOD (see _scanned_names) in a hidden collection per asset, LOD
    and filter (shared by every stroke asking the same). Each variant object is appended from the set once per
    .blend (tagged eb_ph_src, so another LOD or filter reuses it instead of appending the meshes, materials and 2k
    maps again), set at the origin with an 'aH' wind weight (height above its base over its height, 0 root -> 1
    top). which: variant name prefixes to keep (e.g. ['mid', 'tall'] on grass_medium_01, ['a', 'b'] on a set whose
    variants are lettered); None = all."""
    from .vegetation import scanned_dir
    path = os.path.join(scanned_dir(), asset, f'{asset}_2k.blend')
    if not os.path.exists(path):
        raise FileNotFoundError(f'[flora] {path}: fetch it with bmeadow/fetch_ph.py (model {asset} 2k), '
                                f'or point ${"EIDOBLEND_PH_ASSETS"} at a folder of Poly Haven plant sets')
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        names = list(src.objects)
    picked, used = _scanned_names(asset, names, lod)
    if which:
        picked = [(n, v) for n, v in picked if any(v.startswith(w) for w in which)]
    if not picked:
        raise ValueError(f'[flora] {asset}: no variant meshes' + (f' matching {which}' if which else '') +
                         f' among {len(names)} objects')
    if used is None and lod not in (None, 0, 1):
        print(f'[flora] {asset}: a single-LOD set, lod={lod} ignored')
    elif used is not None and used != lod:
        print(f'[flora] {asset}: no LOD{lod}, using LOD{used}')
    key = f'flora_ph_{asset}' + (f'_lod{used}' if used is not None else '') + ('_' + '_'.join(which) if which else '')
    col = bpy.data.collections.get(key)
    if col is not None and len(col.objects):
        return col
    have ={ob.get('eb_ph_src'): ob for ob in bpy.data.objects if ob.get('eb_ph_src')}
    need = [n for n, _ in picked if f'{asset}/{n}' not in have]
    if need:
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = list(need)        # a copy: the loader swaps the names in its list for the loaded objects
        for n, ob in zip(need, dst.objects):
            ob['eb_ph_src'] = f'{asset}/{n}'
            have[f'{asset}/{n}'] = ob
            ob.location = (0.0, 0.0, 0.0)
            ob.rotation_euler = (0.0, 0.0, 0.0)
            ob.hide_render = True
            me = ob.data
            z = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get('co', z)
            z = z.reshape(-1, 3)[:, 2]
            zmin, zmax = float(z.min()), float(z.max())
            a = me.attributes.get('aH') or me.attributes.new('aH', 'FLOAT', 'POINT')
            a.data.foreach_set('value', np.clip((z - max(zmin, 0.0)) / max(zmax - max(zmin, 0.0), 1e-3), 0, 1)
                               .astype(np.float32))
    col = bpy.data.collections.new(key)
    _child_collection(PROTO_COLLECTION, hide=True).children.link(col)
    for n, _ in picked:
        col.objects.link(have[f'{asset}/{n}'])
    return col


def _drop_vertices(geo, keep):
    """A PlantGeo without the vertices where keep is False (and every triangle touching them)."""
    keep = np.asarray(keep, bool)
    remap = -np.ones(geo.nverts, np.int64)
    remap[keep] = np.arange(int(keep.sum()))
    tk = keep[geo.tris].all(axis=1)
    return PlantGeo(geo.pos[keep], geo.uv[keep], geo.aH[keep], remap[geo.tris[tk]],
                    None if geo.nrm is None else geo.nrm[keep], {k: np.asarray(v)[keep] for k, v in geo.extra.items()},
                    None if geo.mat is None else geo.mat[tk], geo.stats)


class FloraField:
    """What create_flora returns: the stroke's objects and its controls."""

    def __init__(self, plan, obj, proto, materials, pushers, heads, proto_verts):
        self.plan = plan
        self.object = obj
        self.prototype = proto
        self.materials = materials
        self.pushers = pushers
        self.count = plan['count']
        self.heads = heads
        self.species = plan['species']
        g = plan['geo']
        self.stats = dict(plan.get('stats') or {}, instances=self.count, proto_verts=proto_verts,
                          verts_total=self.count * proto_verts if proto is not None else None,
                          js_verts=g.nverts if g is not None else None, js_tris=g.ntris if g is not None else None)

    @property
    def modifier(self):
        return self.object.modifiers['flora']

    @staticmethod
    def _set_input(mod, name, value, frame=None):
        """Blender 5.2 keeps a nodes modifier's inputs at mod.properties.inputs.<socket identifier>.value (no longer
        ID properties); they keyframe like any property."""
        for item in mod.node_group.interface.items_tree:
            if getattr(item, 'in_out', None) == 'INPUT' and item.name == name:
                slot = getattr(mod.properties.inputs, item.identifier)
                slot.value = value
                if frame is not None:
                    slot.keyframe_insert(data_path='value', frame=frame)
                return
        raise KeyError(name)

    def set_wind(self, *, strength=None, sway=None, gust=None, flutter=None, direction=None, frame=None):
        """strength scales sway and gust together (the WebGPU edition's `wind` option); direction = (x, y)."""
        if not getattr(self, 'motion', True):
            print(f'[flora] {self.species}: a still stroke (motion=False) has no wind to set')
            return
        m = self.modifier
        w = self.plan['spec']['wind']
        if strength is not None:
            sway = w['base'] * strength if sway is None else sway
            gust = w['gust'] * strength if gust is None else gust
        for name, v in (('Sway', sway), ('Gust', gust), ('Flutter', flutter)):
            if v is not None:
                self._set_input(m, name, float(v), frame)
        if direction is not None:
            self._set_input(m, 'Wind Dir', (float(direction[0]), float(direction[1]), 0.0), frame)
        self.object.update_tag()

    def set_close(self, v, frame=None):
        """Daisies: 0 open .. 1 shut (the rays fold up about their hinges and curl in over the disc). With frame,
        a keyframe, so the dusk close plays from the saved .blend."""
        mod = self.prototype.modifiers.get('close') if self.prototype is not None else None
        if mod is None:
            return
        self._set_input(mod, 'Close', float(v), frame)
        self.prototype.update_tag()

    def set_pushers(self, items, radius=1.2):
        """Characters part the plants. items: objects, (armature, bone) pairs, (armature, bone, radius), points
        (x, y, z[, r]) or dicts {'object', 'bone', 'radius', 'offset'}. Each becomes an empty in this field's
        pusher collection, parented to what it follows; its world X scale is its radius. The collection is shared
        by every stroke made with the same `pushers` collection (by default all of them), so one walker parts
        every stroke. Replaces the collection's previous pushers."""
        col = self.pushers
        for ob in list(col.objects):
            if ob.get('eb_flora_pusher'):
                bpy.data.objects.remove(ob)
        made = []
        for i, it in enumerate(items):
            spec = {}
            if isinstance(it, bpy.types.Object):
                spec = {'object': it}
            elif isinstance(it, dict):
                spec = dict(it)
            elif isinstance(it, (list, tuple)) and it and isinstance(it[0], bpy.types.Object):
                spec = {'object': it[0], 'bone': it[1] if len(it) > 1 else None, 'radius': it[2] if len(it) > 2 else None}
            else:
                spec = {'point': it[:3], 'radius': it[3] if len(it) > 3 else None}
            r = float(spec.get('radius') or radius)
            e = bpy.data.objects.new(f'flora_pusher_{i}', None)
            e['eb_flora_pusher'] = True
            e.empty_display_type = 'SPHERE'
            e.empty_display_size = 1.0
            col.objects.link(e)
            if spec.get('object') is not None:
                e.parent = spec['object']
                if spec.get('bone'):
                    e.parent_type = 'BONE'
                    e.parent_bone = spec['bone']
                    bone = spec['object'].data.bones[spec['bone']]
                    e.location = (0.0, -bone.length, 0.0)          # bone parenting sits at the tail: back to the head
                off = spec.get('offset')
                if off:
                    e.location = Vector(e.location) + Vector(off)
            else:
                e.location = spec['point']
            e['eb_radius'] = r
            made.append(e)
        bpy.context.view_layer.update()
        for e in made:                                              # world X scale = the radius
            ws = e.matrix_world.to_scale().x or 1.0
            e.scale = (e.scale[0] * e['eb_radius'] / ws,) * 3
        bpy.context.view_layer.update()
        return made

    def remove(self):
        """Delete the stroke's objects and meshes (shared node groups, images and materials stay for other strokes)."""
        for ob in (self.object, self.prototype):
            if ob is not None:
                me = ob.data
                bpy.data.objects.remove(ob)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
        self.object = self.prototype = None


def create_flora(species, *, size=None, width=None, depth=None, center=(0.0, 0.0), z=0.0, seed=7, variant=0,
                 density=None, footprint=None, rows=None, placements=None, height_fn=None, clip_fn=None,
                 surface=None, align=None, max_slope=0.9, avoid=None, heading=None, heading_jitter=None,
                 heading_elevation=None, height=None, head_scale=None, color=None, wind=1.0, wind_dir=(1.0, -0.3),
                 sss=1.0, translucency=1.0, close=0.0, corn=None, sunflower=None, daisy=None, blades=None,
                 normals=None, rough=None, specular=0.5, grazing_damp=None, curl=None, keep_length=True, motion=True,
                 lod=1, variants=None, sun_dir=None, pushers=None, collection=None, name=None, webgpu_heading=False):
    """Paint one stand of `species` (Blender coordinates, Z up, metres). See tools-guides/vegetation.md.
    sun_dir is accepted for parity and ignored: EEVEE lights the plants from the scene's real lights.
    webgpu_heading=True (sunflower): the WebGPU edition's facing, `heading` plus the stroke's random head yaw."""
    kw = dict(locals())
    opts = _three_opts(kw)
    plan = plan_flora(opts)
    spec, sp = plan['spec'], plan['species']
    scene = bpy.context.scene
    collection = collection or scene.collection
    base = name or f"flora_{sp.replace(':', '_')}_s{seed}" + (f'v{variant}' if variant else '')

    if spec['archetype'] == 'scanned':
        vcol = _scanned_variants(spec['asset'], lod, variants)
        proto, mats = None, sorted({m for ob in vcol.objects for m in ob.data.materials if m}, key=lambda m: m.name)
        nvar, proto_verts = len(vcol.objects), max(len(ob.data.vertices) for ob in vcol.objects)
    else:
        proto, mats, vcol = _grow_prototype(plan, base, normals, sss, translucency, rough, specular, grazing_damp, curl)
        nvar, proto_verts = 0, len(proto.data.vertices)
    field = _build_field(plan, base, collection, proto, mats, vcol, nvar, proto_verts, seed, variant, pushers,
                         wind, wind_dir, close, motion)
    if motion:
        field._set_input(field.modifier, 'Keep Length', bool(keep_length))
    return field


def _grow_prototype(plan, base, normals, sss, translucency, rough=None, specular=0.5, grazing_damp=None, curl=None):
    """The plant: grown once per stroke, hidden, with its sheet material(s)."""
    spec = plan['spec']
    geo = plan['geo']
    if spec['archetype'] == 'daisy':
        geo = _drop_vertices(geo, np.asarray(geo.extra['lod_class']) < 1.5)    # no far-LOD impostor in EEVEE
    maps = _maps(spec['maps'])
    # shading normals: 'gather' (default) = the WebGPU edition's light-gather normals (blades straight up, the
    # generators' own bent / up-blended normals the same from both sides, daisy heads two-sided); 'true' = the
    # cards' own normals, two-sided; a number t = that share of world-up over the true two-sided normal
    # Blender default: blades shade 'true' (gather's up normals turn fine blades into grazing mirrors under a low
    # sun: white specular streaks, a sky-coloured haze from a low camera; t_lookdev.py E vs C); every other species
    # keeps its generator's light-gather normals
    if normals is None and spec['archetype'] == 'blades':
        normals = 'true'
    if normals in (None, 'gather'):
        normal_mode = 'up' if spec['archetype'] == 'blades' else ('mesh' if spec['archetype'] == 'daisy' else 'mesh_unflip')
    elif normals == 'true':
        normal_mode = 'mesh'
    else:
        normal_mode = float(normals)
    pal = plan['daisy_palette']
    r_eff = spec['rough'] * (rough if rough is not None else (BLADE_ROUGH if spec['archetype'] == 'blades' else 1.0))
    damp = spec['archetype'] == 'blades' if grazing_damp is None else bool(grazing_damp)
    crl = (BLADE_CURL if spec['archetype'] == 'blades' else 0.0) if curl is None else float(curl)
    key = json.dumps([spec['maps'], spec.get('leafTint'), spec.get('leafRecolor'), spec.get('regionTint'), pal,
                      spec['sss'] * sss, translucency, r_eff, specular, normal_mode, damp, crl, nodes.TRANSL_ENERGY,
                      nodes.SPEC_FACING],
                     sort_keys=True, default=str)
    mname = f"flora_{spec['maps']}_{hashlib.md5(key.encode()).hexdigest()[:6]}"
    leaf = nodes.leaf_material(mname, maps, rough=r_eff, sss=spec['sss'] * sss, translucency=translucency,
                               normal_mode=normal_mode, tint=spec.get('leafTint'), recolor=spec.get('leafRecolor'),
                               region_tint=spec.get('regionTint'), palette=pal, specular=specular, grazing_damp=damp,
                               curl=crl)
    mats = [leaf]
    if plan['stem_geo'] is not None:
        # shrubs: leaf cards (slot 0) + the welded wood network (slot 1) in ONE prototype, so one instancer
        stem = plan['stem_geo']
        geo = PlantGeo(geo.pos, geo.uv, geo.aH, geo.tris, geo.nrm, mat=np.zeros(geo.ntris, np.int64))
        stem = PlantGeo(stem.pos, stem.uv, stem.aH, stem.tris, stem.nrm, mat=np.ones(stem.ntris, np.int64))
        geo = merge([geo, stem])
        d = asset_dir()
        bmaps = {}
        for key, suffix, color in (('albedo', '_albedo.png', True), ('rough', '_roughness.png', False),
                                   ('normal', '_normal.png', False)):
            p = os.path.join(d, spec['stem'] + suffix)
            bmaps[key] = nodes.load_map(p, color, alpha_mode='STRAIGHT') if os.path.exists(p) else None
        mats.append(nodes.bark_material(f"flora_{spec['stem']}_{spec['gen']}", bmaps, tint=spec.get('stemTint', (1, 1, 1))))
    # blades keep Blender's own smooth card normals (the translucent lobe and 'true' shading use them; 'gather'
    # replaces them with world up in the shader); every other species carries its generator's normals
    me = to_blender_mesh(geo, base + '_proto', mats, custom_normals=(spec['archetype'] != 'blades'))
    proto = bpy.data.objects.new(base + '_proto', me)
    _child_collection(PROTO_COLLECTION, hide=True).objects.link(proto)
    proto.hide_render = True
    proto.hide_set(True) if proto.name in bpy.context.view_layer.objects else None
    if spec['archetype'] == 'daisy':
        cm = proto.modifiers.new('close', 'NODES')
        cm.node_group = nodes.close_group()
    return proto, mats, None


def _build_field(plan, base, collection, proto, mats, vcol, nvar, proto_verts, seed, variant, pushers, wind, wind_dir,
                 close, motion=True):
    """The plants: one vertex each (the instance data as attributes) under the shared field geometry nodes."""
    spec, sp = plan['spec'], plan['species']
    n = plan['count']
    M, head_fix = instance_matrices(plan['posRot'], plan['scaleVar'], plan['phase'])
    pts = bpy.data.meshes.new(base + '_points')
    roots = M[:, :3, 3].astype(np.float32)
    pts.vertices.add(n)
    pts.vertices.foreach_set('co', roots.ravel())
    a = pts.attributes.new('flora_xform', 'FLOAT4X4', 'POINT')
    a.data.foreach_set('value', np.transpose(M, (0, 2, 1)).astype(np.float32).ravel())   # column-major
    a = pts.attributes.new('root', 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set('vector', roots.ravel())
    a = pts.attributes.new('color_var', 'FLOAT', 'POINT')
    a.data.foreach_set('value', plan['scaleVar'][:, 3].astype(np.float32))
    a = pts.attributes.new('phase', 'FLOAT', 'POINT')
    a.data.foreach_set('value', plan['phase'][:, 0].astype(np.float32))
    if spec['archetype'] == 'daisy':
        a = pts.attributes.new('head_fix', 'FLOAT_VECTOR', 'POINT')
        a.data.foreach_set('vector', head_fix.astype(np.float32).ravel())
    if nvar:
        # one scanned variant per plant, a seeded stream of its own (the placement draws stay the brush's)
        from .jsmath import lehmer
        vr = lehmer(float(seed) * 7919 + 17, 16807)
        a = pts.attributes.new('variant', 'INT', 'POINT')
        a.data.foreach_set('value', np.array([int(vr() * nvar) for _ in range(n)], np.int32))
    pts.update()
    obj = bpy.data.objects.new(base, pts)
    collection.objects.link(obj)
    obj['eb_flora'] = json.dumps({'species': sp, 'seed': seed, 'variant': variant, 'count': n})
    mod = obj.modifiers.new('flora', 'NODES')
    mod.node_group = nodes.field_group() if motion else nodes.static_group()
    pcol = pushers if isinstance(pushers, bpy.types.Collection) else _child_collection(PUSHER_COLLECTION)
    w = spec['wind']
    field = FloraField(plan, obj, proto, mats, pcol, None, proto_verts)
    field.motion = motion
    if proto is not None:
        field._set_input(mod, 'Prototype', proto)
    if vcol is not None:
        field._set_input(mod, 'Variants', vcol)
        field._set_input(mod, 'Pick Variant', True)
    if motion:
        field._set_input(mod, 'Pushers', pcol)
        field._set_input(mod, 'Wind Dir', (float(wind_dir[0]), float(wind_dir[1]), 0.0))
        field._set_input(mod, 'Sway', w['base'] * wind)
        field._set_input(mod, 'Gust', w['gust'] * wind)
        field._set_input(mod, 'Gust Freq', w['gustFreq'])
        field._set_input(mod, 'Flutter', w['flutter'])
        field._set_input(mod, 'Push Scale', spec.get('pushScale', 1.0))
    if spec['archetype'] == 'daisy':
        field.set_close(close)
        field.heads = [{'c': tuple(C3B @ np.array(h['c'])), 'a': tuple(C3B @ np.array(h['a'])), 'd': h['d'],
                        'bud': h['bud'], 'aH': h['aH']} for h in plan['heads']]
    if n == 0:
        print(f'[flora] {sp}: zero instances placed')
    print(f"[flora] {sp}: {n} plants x {proto_verts} verts ({spec['archetype']}{f', {nvar} variants' if nvar else ''}), seed {seed}")
    return field
