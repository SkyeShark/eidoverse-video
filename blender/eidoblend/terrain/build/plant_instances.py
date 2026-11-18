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
    by species, seed, dials, SeedThree's code and Blender's version) and appended from it afterwards in seconds.
  - A still shot (instance_plants(wind=False), the default; design 4.4): one points mesh per species carrying
    SeedThree's slot attributes (st_rot = yaw, st_scale, st_ground) and the individual (eido_variant), under two
    eidoverse-side Geometry Nodes groups that pick, every frame, by the distance to the ACTIVE CAMERA:
      '<species>'             the full level (LOD0) on the nearest plants within hero_m, at most hero_k of them
                              (HERO_MAX trees in all, shared over the tree species), and the card level (LOD2) on
                              the rest within the card distance: instances, never realised;
      '<species>_billboards'  the billboard beyond the card distance: realised into one mesh of two crossed cards
                              per plant, its material an eidoverse-side copy of SeedThree's (_still_billboard_material)
                              that reads each plant's card centre and yaw from the mesh (eido_bb_origin, eido_bb_yaw)
                              where SeedThree's reads the instance's Object Info, and takes the billboard's measured
                              colour gain against the card level (BILLBOARD_GAIN, match_billboards.py). Two hundred
                              thousand instanced billboards cost 25 s a frame and 3 GB; as one mesh they cost little.
                              It casts the sun's shadow and receives none (seedthree.bl.cast_only).
    The card distance is min(the species' billboard_m, sqrt(NEAR_TREES / (pi x density))) for trees; shrubs keep
    their card level while a plant spans 4 pixels (height / (4 PIXEL_ANGLE)), at most NEAR_SHRUBS plants.
  - A shot with wind (wind=True): trees take SeedThree's own grove (seedthree.bl.forest.forest_group), as its
    make_forest_ring sets it up, per individual: the card level realised near the camera so each tree sways, the
    billboards beyond on a second object, and the full level within hero_m of the plan's focus on a third object,
    chosen at build (hero_m shrinks in a dense stand to keep its full levels within HERO_TRIANGLES). Shrubs stay
    still instances: they barely sway.

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
NEAR_TREES = 300                    # trees at their card level at once (design 4.4: the swaying grove's 300)
HERO_MAX = 64                       # trees at their full level in any frame, over every species (design 4.4)
HERO_SHRUBS = 96                    # shrubs at their full level per species, the nearest the camera (instances)
NEAR_SHRUBS = 4000                  # shrubs at their card level at once (instances)
PIXEL_ANGLE = 1.0e-3                # radians a pixel spans (960 pixels over 55 degrees): a shrub keeps its card level
                                    # while it spans 4 pixels (design 4.4: 250 m for a 1 m shrub)
HERO_TRIANGLES = 1.5e6              # with wind: a species' full levels realised near the focus, in triangles: about
                                    # 220 bytes each once SeedThree's wind attributes ride on them (154 Douglas firs at
                                    # 45 k triangles took 1.5 GB), so hero_m shrinks in a dense stand to keep within it
BILLBOARD_RES = 1024
TINT_AMOUNT = 0.25                  # a still plant's albedo x (1 + TINT_AMOUNT (tint - 0.5)): each plant's own tone
# the billboard matched to its card level (design 4.4: before it is used), per individual: gain, the linear RGB
# gains on its baked albedo, and alpha, the threshold its cut-out keeps the baked alpha above (SeedThree's 0.35: a
# higher one thins a billboard baked from the full level down to the card level's silhouette). What
# match_billboards.py measured with both rendered at the card distance under make_sky. Keyed (SeedThree species,
# seed, dials as sorted JSON); an individual missing here keeps SeedThree's billboard as it is
BILLBOARD_GAIN = {}
ALPHA_CUT = 0.35                    # SeedThree's billboard cut-out threshold
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


# ---------------------------------------------------------------------------------- SeedThree, a still shot ---

def _gn(nt, kind, x=0.0, y=0.0, **props):
    n = nt.nodes.new(kind)
    n.location = (x, y)
    for k, v in props.items():
        setattr(n, k, v)
    return n


def _gn_attr(nt, name, kind, x, y):
    n = _gn(nt, 'GeometryNodeInputNamedAttribute', x, y, data_type=kind)
    n.inputs['Name'].default_value = name
    return n.outputs['Attribute']


def _gn_value(nt, name, value, x, y):
    n = _gn(nt, 'ShaderNodeValue', x, y, name=name, label=name)
    n.outputs[0].default_value = float(value)
    return n.outputs[0]


def _gn_camera_distance(nt, x, y):
    """Each point's distance to the active camera (re-evaluated every frame as the camera moves)."""
    cam = _gn(nt, 'GeometryNodeInputActiveCamera', x, y - 150)
    oi = _gn(nt, 'GeometryNodeObjectInfo', x + 200, y - 150, transform_space='ORIGINAL')
    nt.links.new(cam.outputs[0], oi.inputs['Object'])
    d = _gn(nt, 'ShaderNodeVectorMath', x + 400, y, operation='DISTANCE')
    nt.links.new(_gn(nt, 'GeometryNodeInputPosition', x + 200, y).outputs[0], d.inputs[0])
    nt.links.new(oi.outputs['Location'], d.inputs[1])
    return d.outputs['Value']


def _gn_instance(nt, points, selection, col, x, y):
    """The point's individual (eido_variant) of a collection holding one child collection per individual,
    instanced on the selected points, turned by st_rot and scaled by st_scale: instances, not realised."""
    ci = _gn(nt, 'GeometryNodeCollectionInfo', x, y + 150, transform_space='ORIGINAL')
    ci.inputs['Collection'].default_value = col
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = False
    rot = _gn(nt, 'ShaderNodeCombineXYZ', x, y - 150)
    nt.links.new(_gn_attr(nt, 'st_rot', 'FLOAT', x - 200, y - 150), rot.inputs[2])
    iop = _gn(nt, 'GeometryNodeInstanceOnPoints', x + 250, y)
    nt.links.new(points, iop.inputs['Points'])
    nt.links.new(selection, iop.inputs['Selection'])
    nt.links.new(ci.outputs[0], iop.inputs['Instance'])
    iop.inputs['Pick Instance'].default_value = True
    nt.links.new(_gn_attr(nt, 'eido_variant', 'INT', x - 200, y - 300), iop.inputs['Instance Index'])
    nt.links.new(rot.outputs[0], iop.inputs['Rotation'])
    nt.links.new(_gn_attr(nt, 'st_scale', 'FLOAT', x - 200, y - 400), iop.inputs['Scale'])
    return iop.outputs[0]


def _new_group(name):
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    return ng


def near_group(name, near_col, full_col, card_m, hero_m, hero_k):
    """The still grove's near object: the full level (LOD0) on the hero_k points nearest the active camera within
    hero_m, the card level (LOD2) on the other points within card_m. The hero radius is the hero_k-th nearest
    point's distance (the points sorted by it, read at index hero_k - 1), capped at hero_m: chosen per frame.
    Its 'Card Distance', 'Hero Distance' and 'Hero Count' values can be changed after."""
    ng = _new_group(name)
    nt = ng
    gin = _gn(nt, 'NodeGroupInput', -1400, 0)
    gout = _gn(nt, 'NodeGroupOutput', 1000, 0)
    card = _gn_value(nt, 'Card Distance', card_m, -1400, -500)
    hm = _gn_value(nt, 'Hero Distance', hero_m if full_col is not None else 0.0, -1400, -600)
    hk = _gn_value(nt, 'Hero Count', hero_k if full_col is not None else 0, -1400, -700)
    dist = _gn_camera_distance(nt, -1400, -250)
    srt = _gn(nt, 'GeometryNodeSortElements', -1000, 200, domain='POINT')
    nt.links.new(gin.outputs[0], srt.inputs['Geometry'])
    nt.links.new(dist, srt.inputs['Sort Weight'])
    si = _gn(nt, 'GeometryNodeSampleIndex', -800, 200, data_type='FLOAT', domain='POINT', clamp=True)
    nt.links.new(srt.outputs[0], si.inputs['Geometry'])
    nt.links.new(dist, si.inputs['Value'])
    idx = _gn(nt, 'ShaderNodeMath', -1000, -50, operation='SUBTRACT')
    nt.links.new(hk, idx.inputs[0])
    idx.inputs[1].default_value = 1.0
    nt.links.new(idx.outputs[0], si.inputs['Index'])
    rk = _gn(nt, 'ShaderNodeMath', -600, 200, operation='MINIMUM')
    nt.links.new(si.outputs[0], rk.inputs[0])
    nt.links.new(hm, rk.inputs[1])
    # hero: within the hero radius, and a hero count above 0 (index -1 would read the nearest point)
    within = _gn(nt, 'FunctionNodeCompare', -400, 200, data_type='FLOAT', operation='LESS_EQUAL')
    nt.links.new(dist, within.inputs[0])
    nt.links.new(rk.outputs[0], within.inputs[1])
    some = _gn(nt, 'FunctionNodeCompare', -400, 50, data_type='FLOAT', operation='GREATER_THAN')
    nt.links.new(hk, some.inputs[0])
    some.inputs[1].default_value = 0.5
    hero = _gn(nt, 'FunctionNodeBooleanMath', -200, 150, operation='AND')
    nt.links.new(within.outputs[0], hero.inputs[0])
    nt.links.new(some.outputs[0], hero.inputs[1])
    inside = _gn(nt, 'FunctionNodeCompare', -400, -150, data_type='FLOAT', operation='LESS_EQUAL')
    nt.links.new(dist, inside.inputs[0])
    nt.links.new(card, inside.inputs[1])
    near = _gn(nt, 'FunctionNodeBooleanMath', -200, -150, operation='NIMPLY')     # inside and not hero
    nt.links.new(inside.outputs[0], near.inputs[0])
    nt.links.new(hero.outputs[0], near.inputs[1])
    join = _gn(nt, 'GeometryNodeJoinGeometry', 800, 0)
    nt.links.new(_gn_instance(nt, gin.outputs[0], near.outputs[0], near_col, 200, -200), join.inputs[0])
    if full_col is not None:
        nt.links.new(_gn_instance(nt, gin.outputs[0], hero.outputs[0], full_col, 200, 400), join.inputs[0])
    nt.links.new(join.outputs[0], gout.inputs[0])
    return ng


def billboard_group(name, bb_col, card_m):
    """The still grove's billboards: beyond card_m of the active camera, each point's billboard pair, realised into
    one mesh. The points' eido_bb_origin and eido_bb_yaw ride along onto its vertices (point attributes go to the
    instances, and from them to the realised mesh), where _still_billboard_material reads them."""
    ng = _new_group(name)
    nt = ng
    gin = _gn(nt, 'NodeGroupInput', -1000, 0)
    gout = _gn(nt, 'NodeGroupOutput', 800, 0)
    card = _gn_value(nt, 'Card Distance', card_m, -1000, -400)
    dist = _gn_camera_distance(nt, -1000, -200)
    far = _gn(nt, 'FunctionNodeCompare', -400, -200, data_type='FLOAT', operation='GREATER_THAN')
    nt.links.new(dist, far.inputs[0])
    nt.links.new(card, far.inputs[1])
    inst = _gn_instance(nt, gin.outputs[0], far.outputs[0], bb_col, -200, 0)
    real = _gn(nt, 'GeometryNodeRealizeInstances', 400, 0)
    nt.links.new(inst, real.inputs[0])
    nt.links.new(real.outputs[0], gout.inputs[0])
    return ng


def _tone_base(nt, gain, attr_type):
    """Multiply the Principled BSDF's Base Color of a material's tree by gain (r, g, b) and by the plant's own tone,
    1 + TINT_AMOUNT (eido_tint - 0.5), eido_tint read from the mesh ('GEOMETRY': a realised billboard's vertices) or
    from the instance ('INSTANCER': a card or full level instanced on the spots)."""
    bsdf = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
    if bsdf is None:
        return
    sock = bsdf.inputs['Base Color']
    x, y = bsdf.location[0] - 260, bsdf.location[1] + 260
    t = nt.nodes.new('ShaderNodeAttribute')
    t.attribute_type = attr_type
    t.attribute_name = 'eido_tint'
    t.location = (x - 400, y + 150)
    k = nt.nodes.new('ShaderNodeMath')
    k.operation = 'MULTIPLY_ADD'
    k.inputs[1].default_value = TINT_AMOUNT
    k.inputs[2].default_value = 1.0 - 0.5 * TINT_AMOUNT
    k.location = (x - 200, y + 150)
    nt.links.new(t.outputs['Fac'], k.inputs[0])
    m = nt.nodes.new('ShaderNodeVectorMath')
    m.operation = 'MULTIPLY'
    m.inputs[1].default_value = tuple(float(v) for v in gain)
    m.location = (x, y)
    s = nt.nodes.new('ShaderNodeVectorMath')
    s.operation = 'SCALE'
    s.location = (x + 180, y)
    if sock.links:
        nt.links.new(sock.links[0].from_socket, m.inputs[0])
    else:
        m.inputs[0].default_value = tuple(sock.default_value)[:3]
    nt.links.new(m.outputs[0], s.inputs[0])
    nt.links.new(k.outputs[0], s.inputs['Scale'])
    nt.links.new(s.outputs[0], sock)


def _tinted_material(mat):
    """A copy of a SeedThree part's material whose albedo takes each instance's own tone (eido_tint, the spots' tint
    field, read from the instancer): the still grove's card and full levels. Shared per material."""
    name = f'{mat.name} [tint]'
    out = bpy.data.materials.get(name)
    if out is not None and out.get('eido_tint_of') == mat.name:
        return out
    out = mat.copy()
    out.name = name
    out['eido_tint_of'] = mat.name
    _tone_base(out.node_tree, (1.0, 1.0, 1.0), 'INSTANCER')
    return out


def _still_billboard_material(mat, gain=None, alpha=None):
    """An eidoverse-side copy of a SeedThree billboard material for realised billboards: where SeedThree's reads the
    instance's origin (Object Info) for the card's dome normal, this reads eido_bb_origin from the mesh, and where
    it turns the baked detail normal from the card's frame to the world (Vector Transform, object to world), this
    turns it by eido_bb_yaw about z (the realised mesh's object frame is the world's). gain: (r, g, b) on the baked
    albedo, alpha: the cut-out's threshold (BILLBOARD_GAIN); the albedo also takes each plant's own tone (eido_tint,
    from the mesh). Shared per (material, gain, alpha)."""
    g = tuple(round(float(v), 4) for v in (gain or (1.0, 1.0, 1.0)))
    cut = round(float(ALPHA_CUT if alpha is None else alpha), 3)
    name = f'{mat.name} [still {g[0]:g} {g[1]:g} {g[2]:g} a{cut:g}]'
    out = bpy.data.materials.get(name)
    if out is not None and out.get('eido_still_of') == mat.name:
        return out
    out = mat.copy()
    out.name = name
    out['eido_still_of'] = mat.name
    nt = out.node_tree
    for n in nt.nodes:                                   # the cut-out: alpha > threshold
        if n.bl_idname == 'ShaderNodeMath' and n.operation == 'GREATER_THAN' and n.inputs[0].links \
                and n.inputs[0].links[0].from_socket.name == 'Alpha':
            n.inputs[1].default_value = cut
    for n in list(nt.nodes):
        if n.bl_idname == 'ShaderNodeObjectInfo':
            a = nt.nodes.new('ShaderNodeAttribute')
            a.attribute_type = 'GEOMETRY'
            a.attribute_name = 'eido_bb_origin'
            a.location = n.location
            for link in list(n.outputs['Location'].links):
                nt.links.new(a.outputs['Vector'], link.to_socket)
            if any(o.links for o in n.outputs if o.name != 'Location'):
                raise RuntimeError(f'{mat.name}: the billboard reads Object Info beyond its location')
            nt.nodes.remove(n)
        elif n.bl_idname == 'ShaderNodeVectorTransform' and n.convert_from == 'OBJECT' and n.convert_to == 'WORLD':
            r = nt.nodes.new('ShaderNodeVectorRotate')
            r.rotation_type = 'Z_AXIS'
            r.location = n.location
            yaw = nt.nodes.new('ShaderNodeAttribute')
            yaw.attribute_type = 'GEOMETRY'
            yaw.attribute_name = 'eido_bb_yaw'
            yaw.location = (n.location[0] - 200, n.location[1] - 150)
            if n.inputs[0].links:
                nt.links.new(n.inputs[0].links[0].from_socket, r.inputs['Vector'])
            nt.links.new(yaw.outputs['Fac'], r.inputs['Angle'])
            for link in list(n.outputs[0].links):
                nt.links.new(r.outputs[0], link.to_socket)
            nt.nodes.remove(n)
    _tone_base(nt, g, 'GEOMETRY')
    return out


def billboard_gain(species, seed, dials):
    """BILLBOARD_GAIN's entry of an individual as dict(gain=(r, g, b), alpha=threshold), or None."""
    e = BILLBOARD_GAIN.get((species, int(seed), json.dumps(dials or {}, sort_keys=True)))
    if e is None:
        return None
    if not isinstance(e, dict):                          # a gain alone
        e = dict(gain=tuple(e))
    return dict(gain=tuple(e.get('gain') or (1.0, 1.0, 1.0)), alpha=float(e.get('alpha', ALPHA_CUT)))


def _variant_collection(name, per_variant, roles=None, offset=None, materials=None):
    """A collection (not in the scene) with one child collection per individual, in index order (the instancer
    picks a child by eido_variant, and Collection Info gives the children sorted by name), each holding copies of
    the individual's parts at its own origin. offset: per individual (x, y, z) the parts stand at (the billboard
    pair at its card centre); materials: per individual a function giving a part's material in its place (the
    parts then take mesh copies)."""
    from seedthree.bl.export import role_of
    col = bpy.data.collections.new(name)
    for v, objs in enumerate(per_variant):
        child = bpy.data.collections.new(f'{name} v{v:03d}')
        col.children.link(child)
        for ob in objs or []:
            if ob.type != 'MESH' or (roles and role_of(ob) not in roles):
                continue
            data = ob.data
            if materials is not None and materials[v] is not None:
                data = ob.data.copy()
                for i, m in enumerate(data.materials):
                    if m is not None:
                        data.materials[i] = materials[v](m)
            c = bpy.data.objects.new(ob.name + ' [plants]', data)
            child.objects.link(c)
            c.location = offset[v] if offset is not None else (0.0, 0.0, 0.0)
            c.visible_shadow = ob.visible_shadow
            if 'seedthree_cast_only' in ob:
                c['seedthree_cast_only'] = ob['seedthree_cast_only']
    return col


def _species_points(name, rec, scale, z_base, variant, origin=None):
    me = bpy.data.meshes.new(name)
    n = len(rec)
    me.vertices.add(n)
    if n:
        me.vertices.foreach_set('co', np.ascontiguousarray(
            np.stack([rec[:, 0], rec[:, 1], z_base], 1), np.float32).ravel())
    for nm, kind, vals in (('st_rot', 'FLOAT', rec[:, _F['yaw']]), ('st_scale', 'FLOAT', scale),
                           ('st_ground', 'FLOAT', rec[:, _F['z']]), ('eido_variant', 'INT', variant),
                           ('eido_bb_yaw', 'FLOAT', rec[:, _F['yaw']]), ('eido_tint', 'FLOAT', rec[:, _F['tint']])):
        at = me.attributes.new(nm, kind, 'POINT')
        if n:
            at.data.foreach_set('value', np.ascontiguousarray(vals, np.int32 if kind == 'INT' else np.float32))
    if origin is not None:
        at = me.attributes.new('eido_bb_origin', 'FLOAT_VECTOR', 'POINT')
        if n:
            at.data.foreach_set('vector', np.ascontiguousarray(origin, np.float32).ravel())
    me.update()
    return me


def card_distance(entry, rec, focus, lod):
    """How far from the camera a species keeps its card level: trees min(billboard_m, sqrt(NEAR_TREES / (pi x the
    stand's density around the focus))); shrubs min(billboard_m, the distance a plant of mean size spans 4 pixels
    at), at most NEAR_SHRUBS plants. Returns (metres, plants per m^2 there)."""
    near_r = max(2.0 * min(float(lod['billboard_m']), 150.0), 60.0)
    dist = PL.path_distance(focus, rec[:, 0], rec[:, 1])
    dens = float((dist <= near_r).sum()) / (math.pi * near_r * near_r)
    m = float(lod['billboard_m'])
    if entry['kind'] == 'tree':
        cap = NEAR_TREES
    else:
        mean_h = float(entry['size_m'][1]) * float(np.mean(rec[:, _F['scale']])) if len(rec) else 1.0
        m = min(m, mean_h / (4.0 * PIXEL_ANGLE))
        cap = NEAR_SHRUBS
    if dens > 0.0:
        m = min(m, math.sqrt(cap / (math.pi * dens)))
    return m, dens


def _instance_seedthree_still(entry, rec, focus, coll, lod, base, cache, log, hero_k):
    """A still shot's SeedThree species (module doc): (objects, card distance, hero distance)."""
    _seedthree()
    from seedthree.bl.materials import shadow_bias
    from seedthree.bl import cast_only
    from seedthree.bl.sun import bound_sun, find_sun
    src = entry['source']
    species, dials, seeds = src['seedthree'], src.get('dials') or {}, src.get('seeds') or [1]
    card_m, dens = card_distance(entry, rec, focus, lod)
    hero_m = float(lod['hero_m'])
    variants = np.clip(rec[:, _F['variant']].astype(np.int64), 0, len(seeds) - 1)
    plants = [grow_seedthree(species, seed, dials, cache=cache, log=log) if (variants == v).any() else None
              for v, seed in enumerate(seeds)]
    k = np.array([entry['size_m'][1] / p['top_m'] if p is not None else 1.0 for p in plants])
    centre = np.array([p['centre_z'] if p is not None else 0.0 for p in plants])
    s = rec[:, _F['scale']].astype(np.float64) * k[variants]
    z = _base_z(rec, entry['sink'], entry['foot_m'])
    origin = np.stack([rec[:, 0], rec[:, 1], z + s * centre[variants]], 1)
    tag = f"{base}_{PL._file_part(entry['name'])}"
    roles = ('bark', 'cards', 'foliage', 'fronds')
    tinted = [_tinted_material] * len(plants)             # each instance's own tone (the spots' tint field)
    near_col = _variant_collection(tag + '_near_source', [p['levels'].get('LOD2') or p['levels']['LOD0']
                                                         if p is not None else [] for p in plants], roles,
                                   materials=tinted)
    full_col = _variant_collection(tag + '_full_source', [p['levels']['LOD0'] if p is not None else []
                                                         for p in plants], materials=tinted) \
        if hero_m > 0 and hero_k > 0 else None
    gains = [billboard_gain(species, seed, dials) for seed in seeds]
    bb_col = _variant_collection(tag + '_billboard_source', [p['cards'] if p is not None else [] for p in plants],
                                 offset=[(0.0, 0.0, float(c)) for c in centre],
                                 materials=[(lambda m, e=e: _still_billboard_material(
                                     m, (e or {}).get('gain'), (e or {}).get('alpha'))) for e in gains])
    me = _species_points(tag + '_spots', rec, s, z, variants, origin)
    ob = bpy.data.objects.new(tag, me)
    coll.objects.link(ob)
    ob.modifiers.new('Eido Plants', 'NODES').node_group = near_group(tag + ' near', near_col, full_col, card_m,
                                                                     hero_m, hero_k)
    shadow_bias(ob)
    far = bpy.data.objects.new(tag + '_billboards', me)
    coll.objects.link(far)
    far.modifiers.new('Eido Plants', 'NODES').node_group = billboard_group(tag + ' billboards', bb_col, card_m)
    cast_only.link([far], bound_sun() or find_sun())
    for p in plants:                                     # the grown originals: their meshes live on in the sources
        for o in (p or {}).get('objects', []):
            if o.users == 0 or not o.users_collection:
                bpy.data.objects.remove(o)
    out = [ob, far]
    for o in out:
        o['allow_intersect'] = True
        o['eido_plants'] = json.dumps(dict(species=entry['name'], source=src, billboard_m=round(card_m, 1),
                                           hero_m=round(hero_m, 1), hero_k=int(hero_k), still=True,
                                           matched=[dict(gain=list(e['gain']), alpha=e['alpha']) if e else None
                                                    for e in gains]))
    if log:
        log(f"[plants] {entry['name']}: {len(rec):,} spots of SeedThree {species} x{len(seeds)}, still: full level on "
            f"the nearest {hero_k} within {hero_m:.0f} m of the camera, cards within {card_m:.0f} m "
            f"({dens * 1e4:.0f} per ha there), billboards beyond as one mesh"
            + ('' if all(gains) else f" ({sum(1 for g in gains if not g)} of {len(gains)} without a measured gain)"))
    return out


# --------------------------------------------------------------------------------- SeedThree, with wind ---

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


def _gained_material(mat, gain):
    """A copy of a plant material whose colour is multiplied by gain (r, g, b) where it reaches the diffuse (the
    Principled BSDF's Base Color) and the translucent lobe (a Translucent BSDF's Color): the eidoverse side's
    calibration of a flora plant's tone against the photographs, flora's own material untouched. Shared per
    (material, gain)."""
    g = tuple(round(float(v), 4) for v in gain)
    name = f'{mat.name} [gain {g[0]:g} {g[1]:g} {g[2]:g}]'
    out = bpy.data.materials.get(name)
    if out is not None and out.get('eido_gain_of') == mat.name:
        return out
    out = mat.copy()
    out.name = name
    out['eido_gain_of'] = mat.name
    nt = out.node_tree
    for n in list(nt.nodes):
        sock = (n.inputs.get('Base Color') if n.bl_idname == 'ShaderNodeBsdfPrincipled' else
                n.inputs.get('Color') if n.bl_idname == 'ShaderNodeBsdfTranslucent' else None)
        if sock is None:
            continue
        m = nt.nodes.new('ShaderNodeVectorMath')
        m.operation = 'MULTIPLY'
        m.inputs[1].default_value = g
        m.location = (n.location[0] - 200, n.location[1] + 150)
        if sock.links:
            nt.links.new(sock.links[0].from_socket, m.inputs[0])
        else:
            m.inputs[0].default_value = tuple(sock.default_value)[:3]
        nt.links.new(m.outputs[0], sock)
    return out


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
        gain = opts.get('gain')
        proto = getattr(field, 'prototype', None)
        if gain and proto is not None:                   # the source's tone against the photographs (ecotopes.py)
            for i, m in enumerate(proto.data.materials):
                if m is not None:
                    proto.data.materials[i] = _gained_material(m, gain)
        field.object['eido_plants'] = json.dumps(dict(species=entry['name'], source=src, motion=False))
        out.append(field.object)
    if log:
        log(f"[plants] {entry['name']}: {len(rec):,} spots of flora {ident} x{len(seeds)}, still strokes"
            + (f", gain {tuple(opts['gain'])}" if opts.get('gain') else ''))
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


def instance_plants(spots, terrain=None, collection=None, lod=None, cache=True, wind=False, log=print):
    """Instance a plan's spots (plants.PlantSpots) in the open scene.

    terrain     the Terrain the spots were planned on (its object's name names the plants' collection), or None
    collection  where the plants' collection is linked (default the scene's)
    lod         overrides of the species' lod settings: {'hero_m': .., 'billboard_m': .., 'near_m': ..} for every
                species, or {species name: {...}}
    cache       keep grown SeedThree individuals in the plant cache, and take them from it
    wind        False (a still shot): every SeedThree plant an instance, its level picked per frame by the active
                camera, the full level on at most HERO_MAX trees; True: trees in SeedThree's swaying grove (module
                doc), shrubs still
    Returns {species name: [objects]}. A scene with SeedThree plants binds its sun once the sky is final:
    bind_sun(sun_lamp)."""
    t0 = time.time()
    obj = getattr(terrain, 'obj', None)
    base = (obj.name if obj is not None else 'terrain') + '_plants'
    coll = bpy.data.collections.new(base)
    (collection or bpy.context.scene.collection).children.link(coll)
    focus = np.asarray(spots.meta['focus'], np.float64).reshape(-1, 2)
    trees = [e['name'] for e in spots.species
             if e['kind'] == 'tree' and 'seedthree' in e['source'] and len(spots.array(e['name']))]
    tree_k = max(1, HERO_MAX // max(len(trees), 1))
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
            if wind and entry['kind'] == 'tree':
                made[entry['name']] = _instance_seedthree(entry, rec, focus, coll, L, base, cache, log)
            else:
                k = tree_k if entry['kind'] == 'tree' else HERO_SHRUBS
                made[entry['name']] = _instance_seedthree_still(entry, rec, focus, coll, L, base, cache, log, k)
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
           'near_group', 'billboard_group', 'card_distance', 'billboard_gain', 'NEAR_TREES', 'NEAR_SHRUBS',
           'HERO_MAX', 'HERO_SHRUBS', 'HERO_TRIANGLES', 'BILLBOARD_GAIN', 'PIXEL_ANGLE']
