"""The plan's spots as plants in Blender (surfacing design section 4.6): flora-family plants and SeedThree species,
each individual grown once and instanced on its spots by Geometry Nodes, with the level of detail chosen by distance.

    from eidoblend.terrain.build import plants as PL, plant_instances as PI
    spots = PL.plan_plants(t, focus=(x, y))
    made = PI.instance_plants(spots, t)             # {species: [objects]}, in the collection '<terrain>_plants'
    # after the sky and its sun are final:
    from eidoblend.trees import make_seed_tree
    make_seed_tree.set_sun(sun_lamp)                # the leaves' backlight, and the sun the billboards cast from

SeedThree species (source ('seedthree', species, dials, seeds)):
  - one individual per seed, grown through eidoblend.trees.make_seed_tree with its full level (LOD0) and its card
    level (LOD2), and its billboard baked by seedthree.bl.cards.bake_impostor. SeedThree takes minutes for that, so a
    grown individual is kept as a small .blend library in eidoverse/assets/cache/terrain_plants/ (git-ignored, keyed
    by species, seed, dials, SeedThree's code and Blender's version) and appended from it afterwards in seconds;
  - per individual, a points mesh carrying SeedThree's own slot attributes (st_rot = yaw, st_scale, st_ground = the
    ground's height) under seedthree.bl.forest.forest_group, set up the way SeedThree's make_forest_ring sets up its
    grove: one object whose near spots (within billboard_m of the ACTIVE CAMERA, re-evaluated every frame) are the
    card level, realised so each sways, and a second object on the same points for the billboards beyond, which cast
    the sun's shadow and receive none (seedthree.bl.cast_only);
  - the spots within hero_m of the plan's focus are a third object carrying the full level, chosen at build.
  billboard_m shrinks with the stand's density so about NEAR_TREES plants are realised at once
  (min(the species' billboard_m, sqrt(NEAR_TREES / (pi x density)))), and hero_m so their full levels come to at
  most HERO_TRIANGLES triangles (memory: a full level is realised with SeedThree's wind attributes on every vertex).

Flora species (source ('flora', species, opts) or ('ph', asset, opts)):
  - per individual (opts seeds) one still create_flora stroke (instances, never realised: design 4.4) with explicit
    placements [[x, y, s]] and the spots' own ground heights; the plant is grown once per stroke and instanced by
    flora's Geometry Nodes. A stroke draws each plant's yaw and colour variation from its seed and the plant's place
    in the stroke (as the WebGPU edition's createFlora does), not from the spot's yaw: the spots' yaw turns the
    SeedThree plants. Flora's occupancy list is reset after the plan's strokes.

Scale: a spot's height is scale x size_m[1] metres. The individual grown for it is measured (how far its full level
reaches above its base: SeedThree's heightMeters also counts what hangs below the base, a fifth of a blackbrush; a
flora plant's own geometry) and scaled to that. Plants stand upright, their bases `sink` (x their scale) under the
ground, and deeper on a slope by the drop across their foot, so no base hangs over the downhill side.

instance_plants reads nothing but the spots (and the terrain's name): it instances what plan_plants planned.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path

import bpy
import numpy as np

from . import plants as PL

LIBRARY_VERSION = 2
NEAR_TREES = 300                    # SeedThree plants realised at their card level at once (design 4.4)
HERO_TRIANGLES = 1.5e6              # a species' full levels realised near the focus, in triangles: about 220 bytes
                                    # each once SeedThree's wind attributes ride on them (154 Douglas firs at 45 k
                                    # triangles took 1.5 GB), so hero_m shrinks in a dense stand to keep within it
BILLBOARD_RES = 1024
_F = {n: i for i, n in enumerate(PL.FIELDS)}
_FLORA_OPTS = ('height', 'color', 'blades', 'daisy', 'corn', 'sunflower', 'head_scale', 'normals', 'rough',
               'specular', 'lod', 'variants', 'wind', 'sss', 'translucency')


# -------------------------------------------------------------------------------------- grown individuals ---

def library_root():
    """eidoverse/assets/cache/terrain_plants/ of this checkout (git-ignored; beside the terrain cache, not in it:
    its prune takes every folder there for a terrain)."""
    return Path(__file__).resolve().parents[4] / 'eidoverse' / 'assets' / 'cache' / 'terrain_plants'


def _seedthree():
    """SeedThree's api module, with its package (seedthree.bl ...) importable: the trees family's bridge finds the
    add-on (SEEDTHREE_DIR or a SeedThree checkout beside this one) and puts it on the path."""
    from ...trees import seedthree_api as _st
    return _st.raw()


def _seedthree_code():
    """A hash of the SeedThree add-on's code and where it lives (its materials load their maps from its assets)."""
    api = _seedthree()
    pkg = Path(api.PACKAGE_DIR)
    h = hashlib.sha1(str(Path(api.ASSETS_DIR).resolve()).encode('utf-8'))
    for p in sorted(pkg.rglob('*.py')):
        h.update(p.relative_to(pkg).as_posix().encode('utf-8'))
        h.update(p.read_bytes())
    return h.hexdigest()


def seedthree_key(species, seed, dials=None):
    blob = json.dumps([LIBRARY_VERSION, BILLBOARD_RES, list(bpy.app.version[:2]), species, int(seed), dials or {},
                       _seedthree_code()], sort_keys=True, default=str)
    return hashlib.sha1(blob.encode('utf-8')).hexdigest()[:16]


def _extent_z(objs):
    """(lowest, highest) z of the meshes' own vertices: a grown plant's parts are instanced from their mesh data,
    whose origin is the plant's base, so these are how far it reaches below and above the spot it stands on."""
    lo, hi = math.inf, -math.inf
    for o in objs:
        if o.type != 'MESH' or not len(o.data.vertices):
            continue
        co = np.empty(len(o.data.vertices) * 3, np.float32)
        o.data.vertices.foreach_get('co', co)
        lo, hi = min(lo, float(co[2::3].min())), max(hi, float(co[2::3].max()))
    return lo, hi


def _triangles(objs):
    """The triangles of the meshes' own data."""
    n = 0
    for o in objs:
        if o.type != 'MESH' or not len(o.data.polygons):
            continue
        tot = np.empty(len(o.data.polygons), np.int32)
        o.data.polygons.foreach_get('loop_total', tot)
        n += int((tot - 2).sum())
    return n


def _mesh_children(root):
    out = []

    def walk(ob):
        for ch in ob.children:
            out.append(ch)
            walk(ch)
    walk(root)
    return out


def _fold_duplicates(before):
    """After an append: datablocks the file already had come in again under a numbered name. Fold SeedThree's shared
    node groups (its sun and wind, found by name), its keyed materials and its file-backed images back onto the ones
    already here, so set_sun and set_wind reach every plant and no shader is compiled twice."""
    groups, mats, images = before
    for ng in [g for g in bpy.data.node_groups if g not in groups]:
        stem = ng.name.rsplit('.', 1)[0]
        base = bpy.data.node_groups.get(stem)
        if ng.name != stem and ng.name.rsplit('.', 1)[-1].isdigit() and stem.startswith('SeedThree') \
                and base is not None and base is not ng:
            ng.user_remap(base)
            bpy.data.node_groups.remove(ng)
    keyed = {}
    for m in mats:
        k = _mat_key(m)
        if k is not None:
            keyed.setdefault(k, m)
    for m in [m for m in bpy.data.materials if m not in mats]:
        k = _mat_key(m)
        if k is None:
            continue
        if k in keyed and keyed[k] is not m:
            m.user_remap(keyed[k])
            bpy.data.materials.remove(m)
        else:
            keyed[k] = m
    files = {bpy.path.abspath(i.filepath): i for i in images if i.filepath and i.packed_file is None}
    for i in [i for i in bpy.data.images if i not in images]:
        if i.filepath and i.packed_file is None:
            p = bpy.path.abspath(i.filepath)
            if p in files and files[p] is not i:
                i.user_remap(files[p])
                bpy.data.images.remove(i)
            else:
                files[p] = i
    for i in [i for i in bpy.data.images if i not in images and i.users == 0]:
        bpy.data.images.remove(i)


def _mat_key(m):
    if m.get('st_cards_key') is not None:
        return ('cards', m['st_cards_key'], int(m.get('st_variant', 0)), str(m.get('st_view', '')))
    if m.get('st_key') is not None:
        return ('st', m['st_key'], bool(m.get('st_billboard', False)))
    return None


def _protect_images(objs, key):
    """Give a grown plant's baked images names of their own: SeedThree names a bake's images by the species alone
    and removes any image of that name before a new bake, so a second design of the species in one file would take
    the first one's cards and billboard away."""
    tag = f' [{key[:8]}]'
    for ob in objs:
        if ob.type != 'MESH':
            continue
        for m in ob.data.materials:
            if m is None or not m.use_nodes:
                continue
            for n in m.node_tree.nodes:
                img = getattr(n, 'image', None)
                if img is not None and img.packed_file is not None and img.name.startswith('ST ') \
                        and not img.name.endswith(']'):
                    img.name = img.name + tag


def grow_seedthree(species, seed, dials=None, cache=True, log=print):
    """One SeedThree individual, ready to instance: its full level, its card level and its billboard. Appended from
    its library in the plant cache when it was grown before, else grown now (minutes: SeedThree builds every level
    and bakes its cards and its billboard) and written there. Returns dict(levels {'LOD0': [objects], 'LOD2':
    [objects]}, cards [the two billboard card objects], height_m and width_m (SeedThree's whole extent), top_m and
    bottom_m (how far its full level reaches above and below its base: the height it stands is top_m), half_h,
    half_w, centre_z (its billboard's), key, from_cache, seconds). The objects are in no collection: instance their
    meshes."""
    t0 = time.time()
    key = seedthree_key(species, seed, dials)
    path = library_root() / f'seedthree_{species}_{int(seed)}_{key}.blend'
    before = (set(bpy.data.node_groups), set(bpy.data.materials), set(bpy.data.images))
    if cache and path.is_file():
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.objects = list(src.objects)
        objs = [o for o in dst.objects if o is not None]
        _fold_duplicates(before)
        from_cache = True
    else:
        from ...trees import seedthree_api as _st
        _seedthree()
        from seedthree.bl import cards as _cards
        scene = bpy.context.scene
        tmp = bpy.data.collections.new(f'eido_plant_grow_{key[:8]}')
        scene.collection.children.link(tmp)
        tree = _st.make_seed_tree(species=species, seed=int(seed), dials=dict(dials or {}), level=['LOD0', 'LOD2'],
                                  billboard=False, wind=False, collection=tmp, name=f'{species} {int(seed)} {key[:8]}')
        _cards.bake_impostor(tree, size=BILLBOARD_RES, source_level='LOD0',
                             name=f'ST {species} {int(seed)} {key[:8]} billboard', collection=tmp)
        root = tree['object']
        objs = [root] + _mesh_children(root)
        _protect_images(objs, key)
        bb = tree['billboard']
        root['eido_plant'] = json.dumps(dict(
            species=species, seed=int(seed), dials=dials or {}, key=key,
            height_m=float(tree['stats']['summary']['heightMeters']),
            width_m=float(tree['stats']['summary']['widthMeters']), half_h=float(bb['halfH']),
            half_w=float(bb['halfW']), centre_z=float(bb['center'][1]), sink=float(tree['tree']['plantSink'])))
        if cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = str(path) + '.tmp.blend'
            bpy.data.libraries.write(tmp_path, set(objs), path_remap='ABSOLUTE', fake_user=True, compress=True)
            os.replace(tmp_path, str(path))
        for o in objs:
            for c in list(o.users_collection):
                c.objects.unlink(o)
        scene.collection.children.unlink(tmp)
        bpy.data.collections.remove(tmp)
        from_cache = False
    root = next(o for o in objs if o.get('eido_plant'))
    meta = json.loads(root['eido_plant'])
    levels, cards = {}, []
    for o in objs:
        if o.type != 'MESH':
            continue
        if o.get('seedthree_billboard_card'):
            cards.append(o)
        elif o.get('seedthree_lod'):
            levels.setdefault(o['seedthree_lod'], []).append(o)
    cards.sort(key=lambda o: o.name)
    bottom, top = _extent_z(levels.get('LOD0') or [])
    out = dict(meta, levels=levels, cards=cards, objects=objs, from_cache=from_cache, top_m=top, bottom_m=bottom,
               seconds=round(time.time() - t0, 1))
    if log:
        log(f"[plants] SeedThree {species} seed {int(seed)}: {meta['height_m']:.1f} m tall, {meta['width_m']:.1f} m "
            f"wide, {'from the plant cache' if from_cache else 'grown and baked'} in {out['seconds']} s")
    return out


# ---------------------------------------------------------------------------------------------- SeedThree ---

def _source_collection(name, objs, roles=None):
    """A collection outside the scene holding copies of plant parts (sharing their meshes) at the plant's own origin:
    what forest_group instances. roles: keep only these part roles (the grove takes bark and foliage, not fruit)."""
    from seedthree.bl.export import role_of
    col = bpy.data.collections.new(name)
    for ob in objs:
        if ob.type != 'MESH' or (roles and role_of(ob) not in roles):
            continue
        c = bpy.data.objects.new(ob.name + ' [plants]', ob.data)
        col.objects.link(c)
        c.location = (0.0, 0.0, 0.0)
        c.visible_shadow = ob.visible_shadow
        if 'seedthree_cast_only' in ob:
            c['seedthree_cast_only'] = ob['seedthree_cast_only']
    return col


def _points(name, xyz, yaw, scale, ground):
    me = bpy.data.meshes.new(name)
    n = len(xyz)
    me.vertices.add(n)
    if n:
        me.vertices.foreach_set('co', np.ascontiguousarray(xyz, np.float32).ravel())
    for nm, vals in (('st_rot', yaw), ('st_scale', scale), ('st_ground', ground)):
        at = me.attributes.new(nm, 'FLOAT', 'POINT')
        if n:
            at.data.foreach_set('value', np.ascontiguousarray(vals, np.float32))
    me.update()
    return me


def _base_z(rec, sink, foot):
    """Where a plant's base goes: `sink` x its scale under the ground, and on a slope deeper by the drop across
    its foot (so the foot's downhill edge is in the ground too)."""
    s = rec[:, _F['scale']].astype(np.float64)
    nz = np.maximum(rec[:, _F['nz']].astype(np.float64), 0.2)
    tan = np.hypot(rec[:, _F['nx']], rec[:, _F['ny']]) / nz
    return rec[:, _F['z']].astype(np.float64) - s * (float(sink) + float(foot) * np.minimum(tan, 2.0))


def _instance_seedthree(entry, rec, focus, coll, lod, base, cache, log):
    _seedthree()
    from seedthree.bl.forest import forest_group
    from seedthree.bl.materials import shadow_bias
    from seedthree.bl import cast_only
    from seedthree.bl.sun import bound_sun, find_sun
    src = entry['source']
    species, dials, seeds = src['seedthree'], src.get('dials') or {}, src.get('seeds') or [1]
    dist = PL.path_distance(focus, rec[:, 0], rec[:, 1])
    # the stand's density around the focus sets how far the card level reaches, and the full level
    near_r = max(2.0 * float(lod['billboard_m']), 60.0)
    dens = float((dist <= near_r).sum()) / (math.pi * near_r * near_r)
    bb_m = float(lod['billboard_m']) if dens <= 0.0 else min(float(lod['billboard_m']),
                                                            math.sqrt(NEAR_TREES / (math.pi * dens)))
    plants = [grow_seedthree(species, seed, dials, cache=cache, log=log) if (rec[:, _F['variant']] == v).any()
              else None for v, seed in enumerate(seeds)]
    tris = max((_triangles(p['levels'].get('LOD0') or []) for p in plants if p is not None), default=0)
    hero_m = float(lod['hero_m'])
    if dens > 0.0 and tris > 0:
        hero_m = min(hero_m, math.sqrt(HERO_TRIANGLES / tris / (math.pi * dens)))
    out = []
    sun = bound_sun() or find_sun()
    for v, seed in enumerate(seeds):
        sel = rec[:, _F['variant']] == v
        if not sel.any():
            continue
        plant = plants[v]
        r = rec[sel]
        k = entry['size_m'][1] / plant['top_m']          # a spot's height is what stands above its base
        s = r[:, _F['scale']].astype(np.float64) * k
        z = _base_z(r, entry['sink'], entry['foot_m'])
        xyz = np.stack([r[:, 0], r[:, 1], z], 1)
        hero = dist[sel] <= hero_m
        tag = f"{base}_{PL._file_part(entry['name'])}_{v}"
        roles = ('bark', 'cards', 'foliage', 'fronds')
        if (~hero).any():
            me = _points(tag + '_spots', xyz[~hero], r[~hero, _F['yaw']], s[~hero], r[~hero, _F['z']])
            near_col = _source_collection(tag + '_near_source', plant['levels'].get('LOD2') or plant['levels']['LOD0'],
                                          roles)
            bb_col = _source_collection(tag + '_billboard_source', plant['cards'])
            # forest_group lifts a billboard by scale x (half_h - 0.1) over its point: with the bake's own centre
            # the card stands exactly where the plant it was baked from stands
            lift = plant['centre_z'] + 0.1
            ob = bpy.data.objects.new(tag, me)
            coll.objects.link(ob)
            ob.modifiers.new('SeedThree Forest', 'NODES').node_group = forest_group(
                tag + ' grove', near_col, bb_col, bb_m, lift, True, part='near')
            shadow_bias(ob)
            far = bpy.data.objects.new(tag + '_billboards', me)
            coll.objects.link(far)
            far.modifiers.new('SeedThree Forest', 'NODES').node_group = forest_group(
                tag + ' grove billboards', near_col, bb_col, bb_m, lift, False, part='far')
            cast_only.link([far] + list(bb_col.objects), sun)
            for o in (ob, far):
                o['seedthree_forest'] = True
                o['allow_intersect'] = True
            out += [ob, far]
        if hero.any():
            me = _points(tag + '_hero_spots', xyz[hero], r[hero, _F['yaw']], s[hero], r[hero, _F['z']])
            full_col = _source_collection(tag + '_full_source', plant['levels']['LOD0'])
            ob = bpy.data.objects.new(tag + '_hero', me)
            coll.objects.link(ob)
            ob.modifiers.new('SeedThree Forest', 'NODES').node_group = forest_group(
                tag + ' hero', full_col, None, 1.0e9, 1.0, True, part='near')
            shadow_bias(ob)
            ob['seedthree_forest'] = True
            ob['allow_intersect'] = True
            out.append(ob)
        for o in plant['objects']:                       # the grown originals: their meshes live on in the sources
            if o.users == 0 or not o.users_collection:
                bpy.data.objects.remove(o)
    for o in out:
        o['eido_plants'] = json.dumps(dict(species=entry['name'], source=src, billboard_m=round(bb_m, 1),
                                           hero_m=round(hero_m, 1)))
    if log:
        log(f"[plants] {entry['name']}: {len(rec):,} spots of SeedThree {species} x{len(seeds)}; full level within "
            f"{hero_m:.0f} m of the focus, cards within {bb_m:.0f} m of the camera "
            f"({dens * 1e4:.0f} per ha there), billboards beyond")
    return out


# -------------------------------------------------------------------------------------------------- flora ---

_FLORA_HEIGHTS = {}


def flora_height(species, seed, opts=None):
    """The height in metres of the plant a create_flora stroke grows for a species, seed and options, at scale 1
    (flora's planning half grows it, without placing anything)."""
    key = json.dumps([species, int(seed), opts or {}], sort_keys=True, default=str)
    if key not in _FLORA_HEIGHTS:
        from ...flora.vegetation import plan_flora
        kw = {k: v for k, v in (opts or {}).items() if k in ('height', 'blades', 'daisy', 'corn', 'sunflower',
                                                               'head_scale')}
        if species.startswith('ph:'):
            _FLORA_HEIGHTS[key] = None
        else:
            plan = plan_flora(dict(kw, species=species, seed=int(seed), width=1e-3, depth=1e-3, avoid=False))
            top = float(np.asarray(plan['geo'].pos)[:, 1].max())
            if plan.get('stem_geo') is not None:
                top = max(top, float(np.asarray(plan['stem_geo'].pos)[:, 1].max()))
            _FLORA_HEIGHTS[key] = top
    return _FLORA_HEIGHTS[key]


def _instance_flora(entry, rec, focus, coll, lod, base, log):
    from ...flora import create_flora
    src = entry['source']
    ident = src.get('flora') or ('ph:' + src['ph'])
    opts = dict(src.get('options') or {})
    seeds = src.get('seeds') or [7]
    kw = {k: v for k, v in opts.items() if k in _FLORA_OPTS}
    natural = opts.get('natural_m')
    out = []
    for v, seed in enumerate(seeds):
        sel = rec[:, _F['variant']] == v
        if not sel.any():
            continue
        r = rec[sel]
        h0 = flora_height(ident, seed, opts) or float(natural or entry['size_m'][1])
        s = r[:, _F['scale']].astype(np.float64) * entry['size_m'][1] / h0
        z = _base_z(r, entry['sink'], 0.5 * entry['foot_m'])
        xs, ys, zs = r[:, 0].astype(np.float64).tolist(), r[:, 1].astype(np.float64).tolist(), z.tolist()
        ground = dict(zip(zip(xs, ys), zs))
        mean_z = float(np.mean(zs))

        def height_fn(px, py, ground=ground, mean_z=mean_z):     # each spot's own base height
            return ground.get((px, py), mean_z)
        # a still stroke: instances of the one grown plant, never realised (design 4.4: a realised field of tufts
        # is what costs a frame its memory and time)
        field = create_flora(ident, placements=[[a, b, c] for a, b, c in zip(xs, ys, s.tolist())],
                             height_fn=height_fn, seed=int(seed), motion=False, collection=coll,
                             name=f"{base}_{PL._file_part(entry['name'])}_{v}", **kw)
        field.object['eido_plants'] = json.dumps(dict(species=entry['name'], source=src, motion=False))
        out.append(field.object)
    if log:
        log(f"[plants] {entry['name']}: {len(rec):,} spots of flora {ident} x{len(seeds)}, still strokes")
    return out


# ------------------------------------------------------------------------------------------------ the call ---

def bind_sun(sun=None):
    """Bind SeedThree's plants to the scene's sun (the leaves' backlight, and the lamp the billboards cast from
    without receiving): `sun` a sun lamp object, default the scene's strongest. Call it once the sky and its sun are
    final; it is eidoblend.trees.make_seed_tree.set_sun. Returns the lamp, or None when the scene has none."""
    _seedthree()
    from seedthree.bl.sun import find_sun, set_sun
    sun = sun or find_sun()
    return set_sun(sun) if sun is not None else None


def instance_plants(spots, terrain=None, collection=None, lod=None, cache=True, log=print):
    """Instance a plan's spots (plants.PlantSpots) in the open scene.

    terrain     the Terrain the spots were planned on (its object's name names the plants' collection), or None
    collection  where the plants' collection is linked (default the scene's)
    lod         overrides of the species' lod settings: {'hero_m': .., 'billboard_m': .., 'near_m': ..} for every
                species, or {species name: {...}}
    cache       keep grown SeedThree individuals in the plant cache, and take them from it
    Returns {species name: [objects]}. A scene with SeedThree plants binds its sun once the sky is final:
    bind_sun(sun_lamp)."""
    t0 = time.time()
    obj = getattr(terrain, 'obj', None)
    base = (obj.name if obj is not None else 'terrain') + '_plants'
    coll = bpy.data.collections.new(base)
    (collection or bpy.context.scene.collection).children.link(coll)
    focus = np.asarray(spots.meta['focus'], np.float64).reshape(-1, 2)
    made = {}
    for entry in spots.species:
        rec = spots.array(entry['name'])
        if not len(rec):
            made[entry['name']] = []
            continue
        L = dict(entry['lod'])
        over = lod or {}
        L.update({k: v for k, v in over.items() if not isinstance(v, dict)})
        L.update(over.get(entry['name']) or {})
        src = entry['source']
        if 'seedthree' in src:
            made[entry['name']] = _instance_seedthree(entry, rec, focus, coll, L, base, cache, log)
        else:
            made[entry['name']] = _instance_flora(entry, rec, focus, coll, L, base, log)
    # flora keeps the footprints of the structural plants its strokes placed and scans them for every later jittered
    # stroke: the plan's strokes are explicit placements, so they leave nothing for a later stroke to avoid
    from ...flora.vegetation import reset_flora_occupancy
    reset_flora_occupancy()
    if log:
        log(f"[plants] {sum(len(spots.array(n)) for n in spots.names()):,} plants of {len(spots.species)} species "
            f"instanced in {time.time() - t0:.1f} s")
    return made


__all__ = ['instance_plants', 'bind_sun', 'grow_seedthree', 'flora_height', 'library_root', 'seedthree_key',
           'NEAR_TREES', 'HERO_TRIANGLES']
