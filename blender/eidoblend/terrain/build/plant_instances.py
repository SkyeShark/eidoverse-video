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
                              colour gain against the card level (BILLBOARD_GAIN, match_billboards.py; a tree's on its
                              foliage) and the source's tone (bark and foliage alike). Its cut-out keeps a small
                              plant's coverage (_soft_cut: a hard edge while the plant stands large on screen, the
                              alpha's share of the pixel when it is a few pixels tall). Two hundred
                              thousand instanced billboards cost 25 s a frame and 3 GB; as one mesh they cost little.
                              It casts the sun's shadow and receives none (seedthree.bl.cast_only), so bind_sun gives
                              each plant the terrain's shadow under the sun (eido_shade, sun_shade over the terrain's
                              coarse heightfields), which its material takes as SHADE_ALBEDO of the light, and the
                              shadow line the crowns toward the sun cast on it (eido_canopy_z, canopy_line), under
                              which each fragment takes CANOPY_SHADE of that.
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
# seed, dials as sorted JSON); an individual missing here keeps SeedThree's billboard as it is. Measured 11-18 (the
# comments: the mean colour's distance from the level it takes over from before and after, in CIELAB, and the
# billboard's silhouette area over that level's)
BILLBOARD_GAIN = {
    # shrubs: against their card level (it covers 0.97-0.99 of their full level's area)
    ('sagebrush', 3, '{}'): dict(gain=(0.764, 0.796, 0.872), alpha=0.35),           # dE 6.3 -> 1.5, area 1.01
    ('blackbrush', 7, '{"barkTint": 11847908}'): dict(gain=(1.304, 1.283, 1.293), alpha=0.35),    # 5.8 -> 0.9, 1.06
    ('blackbrush', 19, '{"barkTint": 11847908}'): dict(gain=(1.311, 1.288, 1.298), alpha=0.35),   # 5.9 -> 0.8, 1.07
    ('creosote', 3, '{}'): dict(gain=(0.872, 0.917, 1.28), alpha=0.35),             # 9.8 -> 1.9, 0.97
    ('creosote', 3, '{"leafColorize": 5069356, "leafTintAmount": 0.55}'):
        dict(gain=(0.851, 0.881, 1.287), alpha=0.35),                               # 10.6 -> 2.1, 0.97
    ('blackbrush', 7, '{"barkTint": 11847908, "leafColorize": 5660719, "leafTintAmount": 0.45}'):
        dict(gain=(1.321, 1.278, 1.42), alpha=0.35),                                # 6.6 -> 1.2, 1.06
    # trees, their gain on the foliage only: the Douglas fir against its card level (it covers 0.75-0.77 of its full
    # level's area), the broadleaves and the pine against their full level (their card levels cover 0.44-0.76 and
    # are set aside: ecotopes._BROADLEAF_LOD). The spruce stand-in of 11-20 (ecotopes._NARROW_CONIFER, a cone): its
    # billboard, baked from the full level, stays 13-14 % larger than the card level even cut at 0.7, and 15 %
    # smaller than the full level
    ('douglasFir', 11, '{"branchDensity": 78, "height": 30, "leafSize": 0.9, "leavesPerBranch": 16, "paramOverrides": '
                       '{"branches": {"2": 24}, "curve": {"1": -18}, "downAngle": {"1": 106}, "length": {"1": 0.22, '
                       '"2": 0.42}}}'): dict(gain=(0.728, 0.811, 1.044), alpha=0.698),  # 9.02 -> 2.04, 1.14
    ('douglasFir', 23, '{"branchDensity": 78, "height": 30, "leafSize": 0.9, "leavesPerBranch": 16, "paramOverrides": '
                       '{"branches": {"2": 24}, "curve": {"1": -18}, "downAngle": {"1": 106}, "length": {"1": 0.22, '
                       '"2": 0.42}}}'): dict(gain=(0.731, 0.813, 1.05), alpha=0.698),   # 9.01 -> 2.17, 1.13
    ('douglasFir', 37, '{"branchDensity": 78, "height": 30, "leafSize": 0.9, "leavesPerBranch": 16, "paramOverrides": '
                       '{"branches": {"2": 24}, "curve": {"1": -18}, "downAngle": {"1": 106}, "length": {"1": 0.22, '
                       '"2": 0.42}}}'): dict(gain=(0.734, 0.809, 1.04), alpha=0.698),   # 8.97 -> 1.79, 1.14
    ('redMaple', 5, '{}'): dict(gain=(0.72, 0.705, 1.518), alpha=0.35),             # 22.5 -> 3.5, 0.98
    ('redMaple', 17, '{}'): dict(gain=(0.738, 0.723, 1.527), alpha=0.35),           # 21.7 -> 3.5, 1.00
    ('redMaple', 29, '{}'): dict(gain=(0.743, 0.73, 1.511), alpha=0.35),            # 21.1 -> 3.6, 0.99
    ('redMaple', 41, '{}'): dict(gain=(0.717, 0.704, 1.505), alpha=0.35),           # 22.4 -> 3.3, 0.97
    ('pine', 9, '{"height": 20}'): dict(gain=(0.971, 1.006, 1.346), alpha=0.35),   # 6.1 -> 3.5, 0.95
    ('whiteOak', 1737, '{"height": 9}'): dict(gain=(0.788, 0.72, 1.735), alpha=0.2),  # 21.2 -> 1.8, 0.90
    # (11-20) the dunes' camelthorn, the white oak low and wide
    ('whiteOak', 1737, '{"branchAngle": 82, "crownShape": 2, "height": 7, "leafSize": 0.35}'):
        dict(gain=(0.764, 0.731, 1.648), alpha=0.35),                               # 19.75 -> 2.86, 0.92
    ('americanSycamore', 5, '{"height": 16}'): dict(gain=(0.722, 0.679, 1.167), alpha=0.35),   # 16.6 -> 3.2, 1.02
    # the karst's broadleaf with a rounded crown (11-20: SeedThree's sweetgum is a cone, and a stand of it read as
    # conifers on Guilin's towers)
    ('sweetgum', 5, '{"crownShape": 1, "height": 14}'): dict(gain=(1.004, 0.873, 1.961), alpha=0.35),  # 19.2 -> 2.9, 0.98
    ('sweetgum', 17, '{"crownShape": 1, "height": 14}'): dict(gain=(1.026, 0.886, 2.0), alpha=0.35),   # 19.3 -> 2.6, 0.99
}
ALPHA_CUT = 0.35                    # SeedThree's billboard cut-out threshold
ALPHA_SOFT_PX = (24.0, 4.0)         # a billboard's cut-out is hard while its plant stands this many pixels tall
                                    # (PIXEL_ANGLE) and widens to its whole alpha by the second (_soft_cut): a small
                                    # plant keeps the share of a pixel its crown covers, a large one its silhouette
SHADE_ALBEDO = 0.3                  # a billboard in the terrain's shadow (eido_shade 1) takes this share of its
                                    # light: the sky's alone, the sun's twin lights every billboard (cast-only)
CANOPY_SHADE = 0.85                 # a billboard below its neighbours' shadow line (eido_canopy_z) takes this share
                                    # of the terrain's shade: the lit crowns around it light it a little
CANOPY_REACH_M = 40.0               # how far toward the sun a neighbour's crown is looked for
CANOPY_NONE = -1.0e4                # eido_canopy_z where no crown shades the card (and before bind_sun)
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


TONE_DIAL = 'eidoGain'              # a SeedThree source's eidoverse-side tone, (r, g, b) on its albedo (ecotopes.py)


def grown_dials(dials):
    """A SeedThree source's dials as SeedThree grows them: the eidoverse side's tone (TONE_DIAL) left out."""
    return {k: v for k, v in (dials or {}).items() if k != TONE_DIAL}


def seedthree_key(species, seed, dials=None):
    blob = json.dumps([LIBRARY_VERSION, BILLBOARD_RES, list(bpy.app.version[:2]), species, int(seed),
                       grown_dials(dials), _seedthree_code()], sort_keys=True, default=str)
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
    meshes. The dials' eidoverse-side tone (TONE_DIAL) is not SeedThree's: it is left out here."""
    t0 = time.time()
    dials = grown_dials(dials)
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


FOLIAGE_EDGE = 0.04                 # albedo green over its red and blue that counts as foliage (foliage-only gains)


def _tone_base(nt, gain, attr_type, foliage=False, tone=None, shade=False):
    """Multiply the Principled BSDF's Base Color of a material's tree by gain (r, g, b) and by the plant's own tone,
    1 + TINT_AMOUNT (eido_tint - 0.5), eido_tint read from the mesh ('GEOMETRY': a realised billboard's vertices) or
    from the instance ('INSTANCER': a card or full level instanced on the spots), and the leaves' backlight (a
    Translucent BSDF's Color) by gain. foliage: the albedo's gain only where it is green (its green over its red and
    blue by FOLIAGE_EDGE, faded in from 0), the bark kept as it is. tone: (r, g, b) on the whole albedo and the
    backlight, bark and foliage alike (the source's tone, TONE_DIAL: a toned tree's billboard keeps its toned bark,
    where a foliage-only tone left the broadleaves' trunks white on their billboards, an orchard of white-trunk
    clones, 11-20). shade: also the terrain's shadow from the mesh's eido_shade (bind_sun: 0 in the sun, 1 in a
    ridge's or a slope's shadow), which a billboard lit by the shadowless twin sun cannot receive (SHADE_ALBEDO),
    and its neighbours' below the shadow line their crowns cast on it (eido_canopy_z, CANOPY_SHADE)."""
    bsdf = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
    if bsdf is None:
        return
    tone = tuple(float(v) for v in (tone or (1.0, 1.0, 1.0)))
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
    m.location = (x, y)
    s = nt.nodes.new('ShaderNodeVectorMath')
    s.operation = 'SCALE'
    s.location = (x + 180, y)
    src = sock.links[0].from_socket if sock.links else None
    if src is not None:
        nt.links.new(src, m.inputs[0])
    else:
        m.inputs[0].default_value = tuple(sock.default_value)[:3]
    g = tuple(float(v) for v in gain)
    if foliage and src is not None and g != (1.0, 1.0, 1.0):
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        sep.location = (x - 600, y - 150)
        nt.links.new(src, sep.inputs[0])
        rb = nt.nodes.new('ShaderNodeMath')
        rb.operation = 'MAXIMUM'
        rb.location = (x - 420, y - 200)
        nt.links.new(sep.outputs[0], rb.inputs[0])
        nt.links.new(sep.outputs[2], rb.inputs[1])
        d = nt.nodes.new('ShaderNodeMath')
        d.operation = 'SUBTRACT'
        d.location = (x - 280, y - 200)
        nt.links.new(sep.outputs[1], d.inputs[0])
        nt.links.new(rb.outputs[0], d.inputs[1])
        f = nt.nodes.new('ShaderNodeMapRange')         # 0 at no green excess, 1 at FOLIAGE_EDGE (clamped)
        f.location = (x - 140, y - 200)
        f.inputs['From Min'].default_value = 0.0
        f.inputs['From Max'].default_value = FOLIAGE_EDGE
        nt.links.new(d.outputs[0], f.inputs['Value'])
        mix = nt.nodes.new('ShaderNodeVectorMath')     # 1 + f (gain - 1)
        mix.operation = 'MULTIPLY_ADD'
        mix.location = (x - 10, y - 200)
        mix.inputs[0].default_value = tuple(v - 1.0 for v in g)
        nt.links.new(f.outputs['Result'], mix.inputs[1])
        mix.inputs[2].default_value = (1.0, 1.0, 1.0)
        nt.links.new(mix.outputs[0], m.inputs[1])
    else:
        m.inputs[1].default_value = tuple(a * b for a, b in zip(g, tone))
    out = m.outputs[0]
    if foliage and src is not None and g != (1.0, 1.0, 1.0) and tone != (1.0, 1.0, 1.0):
        tn = nt.nodes.new('ShaderNodeVectorMath')        # the tone over bark and foliage alike
        tn.operation = 'MULTIPLY'
        tn.location = (x + 90, y - 120)
        tn.inputs[1].default_value = tone
        nt.links.new(out, tn.inputs[0])
        out = tn.outputs[0]
    nt.links.new(out, s.inputs[0])
    sk = k.outputs[0]
    lit = None
    if shade:
        # in the terrain's shadow: SHADE_ALBEDO of the light (the sky's share of it), on the albedo and the backlight;
        # below the shadow line of the crowns toward the sun (eido_canopy_z, over the card's centre: the fragment's
        # own height decides, so a crown's top is lit over the shade of its foot) CANOPY_SHADE of that shade; the
        # deeper of the two, not both (in a ridge's shadow the crowns take no sun to shade it from)
        a = nt.nodes.new('ShaderNodeAttribute')
        a.attribute_type = attr_type
        a.attribute_name = 'eido_shade'
        a.location = (x - 400, y + 320)
        c = nt.nodes.new('ShaderNodeAttribute')
        c.attribute_type = attr_type
        c.attribute_name = 'eido_canopy_z'
        c.location = (x - 900, y + 470)
        o = nt.nodes.new('ShaderNodeAttribute')
        o.attribute_type = attr_type
        o.attribute_name = 'eido_bb_origin'
        o.location = (x - 900, y + 620)
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        geo.location = (x - 900, y + 780)
        pz = nt.nodes.new('ShaderNodeSeparateXYZ')
        pz.location = (x - 720, y + 780)
        nt.links.new(geo.outputs['Position'], pz.inputs[0])
        oz = nt.nodes.new('ShaderNodeSeparateXYZ')
        oz.location = (x - 720, y + 620)
        nt.links.new(o.outputs['Vector'], oz.inputs[0])
        up = nt.nodes.new('ShaderNodeMath')              # the fragment's height over the card's centre
        up.operation = 'SUBTRACT'
        up.location = (x - 560, y + 700)
        nt.links.new(pz.outputs['Z'], up.inputs[0])
        nt.links.new(oz.outputs['Z'], up.inputs[1])
        ex = nt.nodes.new('ShaderNodeMath')              # how far under the crowns' shadow line it lies
        ex.operation = 'SUBTRACT'
        ex.location = (x - 420, y + 560)
        nt.links.new(c.outputs['Fac'], ex.inputs[0])
        nt.links.new(up.outputs[0], ex.inputs[1])
        f = nt.nodes.new('ShaderNodeMapRange')
        f.interpolation_type = 'SMOOTHSTEP'
        f.inputs['From Min'].default_value = -1.0
        f.inputs['From Max'].default_value = 1.5
        f.location = (x - 300, y + 520)
        nt.links.new(ex.outputs[0], f.inputs['Value'])
        sc = nt.nodes.new('ShaderNodeMath')
        sc.operation = 'MULTIPLY'
        sc.inputs[1].default_value = CANOPY_SHADE
        sc.location = (x - 200, y + 470)
        nt.links.new(f.outputs['Result'], sc.inputs[0])
        deep = nt.nodes.new('ShaderNodeMath')
        deep.operation = 'MAXIMUM'
        deep.location = (x - 200, y + 340)
        nt.links.new(a.outputs['Fac'], deep.inputs[0])
        nt.links.new(sc.outputs[0], deep.inputs[1])
        lit = nt.nodes.new('ShaderNodeMath')
        lit.operation = 'MULTIPLY_ADD'
        lit.inputs[1].default_value = SHADE_ALBEDO - 1.0
        lit.inputs[2].default_value = 1.0
        lit.location = (x - 120, y + 400)
        nt.links.new(deep.outputs[0], lit.inputs[0])
        both = nt.nodes.new('ShaderNodeMath')
        both.operation = 'MULTIPLY'
        both.location = (x - 40, y + 260)
        nt.links.new(sk, both.inputs[0])
        nt.links.new(lit.outputs[0], both.inputs[1])
        sk = both.outputs[0]
    nt.links.new(sk, s.inputs['Scale'])
    nt.links.new(s.outputs[0], sock)
    gt = tuple(a * b for a, b in zip(g, tone))
    if gt != (1.0, 1.0, 1.0) or lit is not None:
        # the leaves' backlight (SeedThree's Translucent lobe, coloured by the species' transmit, not the albedo)
        # takes the same gain and tone, and the shade, or a darkened plant keeps its glow
        for n in [n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfTranslucent']:
            c = n.inputs['Color']
            tm = nt.nodes.new('ShaderNodeVectorMath')
            tm.operation = 'MULTIPLY'
            tm.inputs[1].default_value = gt
            tm.location = (n.location[0] - 200, n.location[1] + 120)
            if c.links:
                nt.links.new(c.links[0].from_socket, tm.inputs[0])
            else:
                tm.inputs[0].default_value = tuple(c.default_value)[:3]
            res = tm.outputs[0]
            if lit is not None:
                sc = nt.nodes.new('ShaderNodeVectorMath')
                sc.operation = 'SCALE'
                sc.location = (n.location[0] - 60, n.location[1] + 120)
                nt.links.new(res, sc.inputs[0])
                nt.links.new(lit.outputs[0], sc.inputs['Scale'])
                res = sc.outputs[0]
            nt.links.new(res, c)


def _tinted_material(mat, tone=None):
    """A copy of a SeedThree part's material whose albedo takes the source's tone (its dials' TONE_DIAL, (r, g, b))
    and each instance's own tone (eido_tint, the spots' tint field, read from the instancer): the still grove's card
    and full levels. Shared per (material, tone)."""
    g = tuple(round(float(v), 4) for v in (tone or (1.0, 1.0, 1.0)))
    name = f'{mat.name} [tint {g[0]:g} {g[1]:g} {g[2]:g}]'
    out = bpy.data.materials.get(name)
    if out is not None and out.get('eido_tint_of') == mat.name:
        return out
    out = mat.copy()
    out.name = name
    out['eido_tint_of'] = mat.name
    _tone_base(out.node_tree, g, 'INSTANCER')
    return out


def _soft_cut(nt, node, cut):
    """Replace a billboard's cut-out (alpha > cut, a Math node) by one that keeps a small plant's coverage: while
    the plant stands ALPHA_SOFT_PX[0] pixels tall or more the same hard edge, down to [1] pixels a ramp that widens
    to the whole alpha range, so the texture's mip, where a texel averages crown and gaps, leaves the plant the share
    of the pixel its crown covers (the material is dithered: a fraction is drawn as that share of the samples). The
    plant's size on screen is its height (eido_bb_h, from the mesh) over the camera's distance. A hard cut-out on
    mipped alpha erased the stand-in spruce past a few hundred metres, a cut of 0.69 the sooner, and the slopes its
    instances stood on read as bare, smooth felt (11-20, Schynige); a ramp by distance alone (150-1500 m) softened
    20 m spruces that still stood 20 pixels tall at a kilometre into a felt of overlapping fringes (11-20,
    Lauterbrunnen). (alpha - cut) / w + cut, clamped, w from 0.02 to 1: the hard edge at the cut, the alpha itself
    at the softest (with + 0.5 a card's empty corners kept 0.5 - cut of cover there, a faint box of foliage colour
    round every small plant, 11-20)."""
    x, y = node.location
    cam = nt.nodes.new('ShaderNodeCameraData')
    cam.location = (x - 800, y - 200)
    hh = nt.nodes.new('ShaderNodeAttribute')
    hh.attribute_type = 'GEOMETRY'
    hh.attribute_name = 'eido_bb_h'
    hh.location = (x - 800, y - 360)
    per = nt.nodes.new('ShaderNodeMath')                 # metres of distance per metre of plant (0 without a height:
    per.operation = 'DIVIDE'                             # the hard edge)
    per.location = (x - 600, y - 260)
    nt.links.new(cam.outputs['View Distance'], per.inputs[0])
    nt.links.new(hh.outputs['Fac'], per.inputs[1])
    w = nt.nodes.new('ShaderNodeMapRange')
    w.location = (x - 400, y - 200)
    w.interpolation_type = 'SMOOTHSTEP'
    w.inputs['From Min'].default_value = 1.0 / (ALPHA_SOFT_PX[0] * PIXEL_ANGLE)
    w.inputs['From Max'].default_value = 1.0 / (ALPHA_SOFT_PX[1] * PIXEL_ANGLE)
    w.inputs['To Min'].default_value = 0.02
    w.inputs['To Max'].default_value = 1.0
    nt.links.new(per.outputs[0], w.inputs['Value'])
    a = node.inputs[0].links[0].from_socket
    sub = nt.nodes.new('ShaderNodeMath')
    sub.operation = 'SUBTRACT'
    sub.location = (x - 200, y)
    nt.links.new(a, sub.inputs[0])
    sub.inputs[1].default_value = float(cut)
    div = nt.nodes.new('ShaderNodeMath')
    div.operation = 'DIVIDE'
    div.location = (x - 50, y)
    nt.links.new(sub.outputs[0], div.inputs[0])
    nt.links.new(w.outputs['Result'], div.inputs[1])
    add = nt.nodes.new('ShaderNodeMath')
    add.operation = 'ADD'
    add.use_clamp = True
    add.location = (x + 100, y)
    nt.links.new(div.outputs[0], add.inputs[0])
    add.inputs[1].default_value = float(cut)
    for link in list(node.outputs[0].links):
        nt.links.new(add.outputs[0], link.to_socket)
    nt.nodes.remove(node)


def _still_billboard_material(mat, gain=None, alpha=None, foliage=False, tone=None):
    """An eidoverse-side copy of a SeedThree billboard material for realised billboards: where SeedThree's reads the
    instance's origin (Object Info) for the card's dome normal, this reads eido_bb_origin from the mesh, and where
    it turns the baked detail normal from the card's frame to the world (Vector Transform, object to world), this
    turns it by eido_bb_yaw about z (the realised mesh's object frame is the world's). gain: (r, g, b) on the baked
    albedo, alpha: the cut-out's threshold (BILLBOARD_GAIN), kept by a small plant's coverage (_soft_cut); foliage: the
    gain on the green of the bake only (a tree's: its bark stays as baked); tone: the source's tone (TONE_DIAL) on
    bark and foliage alike; the albedo also takes each plant's own tone (eido_tint, from the mesh), the terrain's
    shadow and its neighbours' (eido_shade, eido_canopy_z: bind_sun). Shared per (material, gain, alpha, foliage,
    tone)."""
    g = tuple(round(float(v), 4) for v in (gain or (1.0, 1.0, 1.0)))
    tn = tuple(round(float(v), 4) for v in (tone or (1.0, 1.0, 1.0)))
    cut = round(float(ALPHA_CUT if alpha is None else alpha), 3)
    name = (f'{mat.name} [still {g[0]:g} {g[1]:g} {g[2]:g} a{cut:g}{" leaves" if foliage else ""}'
            + ('' if tn == (1.0, 1.0, 1.0) else f' tone {tn[0]:g} {tn[1]:g} {tn[2]:g}') + ']')
    out = bpy.data.materials.get(name)
    if out is not None and out.get('eido_still_of') == mat.name:
        return out
    out = mat.copy()
    out.name = name
    out['eido_still_of'] = mat.name
    nt = out.node_tree
    for n in list(nt.nodes):                             # the cut-out: alpha > threshold, kept by far coverage
        if n.bl_idname == 'ShaderNodeMath' and n.operation == 'GREATER_THAN' and n.inputs[0].links \
                and n.inputs[0].links[0].from_socket.name == 'Alpha':
            _soft_cut(nt, n, cut)
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
    _tone_base(nt, g, 'GEOMETRY', foliage=foliage, tone=tn, shade=True)
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


def _species_points(name, rec, scale, z_base, variant, origin=None, height=None):
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
        at = me.attributes.new('eido_canopy_z', 'FLOAT', 'POINT')       # no crown's shadow until bind_sun
        if n:
            at.data.foreach_set('value', np.full(n, CANOPY_NONE, np.float32))
    if height is not None:                               # each plant's height, metres (the billboard's soft cut)
        at = me.attributes.new('eido_bb_h', 'FLOAT', 'POINT')
        if n:
            at.data.foreach_set('value', np.ascontiguousarray(height, np.float32))
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
    tone = tuple(float(v) for v in (dials.get(TONE_DIAL) or (1.0, 1.0, 1.0)))
    dials = grown_dials(dials)
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
    tinted = [lambda m: _tinted_material(m, tone)] * len(plants)    # the source's tone and each instance's own
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
                                     m, (e or {}).get('gain') or (1.0, 1.0, 1.0), (e or {}).get('alpha'),
                                     foliage=entry['kind'] == 'tree', tone=tone)) for e in gains])
    me = _species_points(tag + '_spots', rec, s, z, variants, origin,
                         height=rec[:, _F['scale']].astype(np.float64) * float(entry['size_m'][1]))
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


# ------------------------------------------------------------------------------------- the terrain's shade ---
# A still billboard is lit by SeedThree's shadowless twin of the sun (cast_only: it casts the sun's shadow and
# receives none, so its crossed cards never band each other), so in the shadow of a ridge or of its own slope it
# glowed as if in full sun: a stand on a shaded tower flank read as a block of pale cut-outs (11-20, Guilin). Every
# instanced plants collection keeps the terrain's coarse heightfields (the context and main levels' h), and
# bind_sun marches each billboard's card centre toward the sun over them: eido_shade on its points (0 in the sun,
# 1 in the terrain's shadow), which the billboard material reads (_tone_base, SHADE_ALBEDO). For the same reason a
# stand of billboards was lit crown by crown as if each stood alone: a felt of even green on Lauterbrunnen's wooded
# sides at 0.5-1.6 km, where the photographs show lit crowns over the shade between them (11-20). The collection
# also keeps its plants' crowns (_crowns), and bind_sun gives each billboard the shadow line the crowns toward the
# sun cast on it (canopy_line), over its card's centre: eido_canopy_z on its points, which the material compares
# with each fragment's own height, so a crown's top stands lit over the shade of its foot and of the stand.
_SHADE_GROUND = {}


def _crowns(spots):
    """[x, y, top, radius] of a plan's SeedThree plants (trees and shrubs, every level of detail): the crowns that
    shade each other; a plant's height is its scale x size_m[1] over its spot, its crown radius crown_m x scale."""
    parts = []
    for e in spots.species:
        if 'seedthree' not in e['source']:
            continue
        rec = spots.array(e['name'])
        if not len(rec):
            continue
        sc = rec[:, _F['scale']].astype(np.float64)
        top = rec[:, _F['z']].astype(np.float64) + sc * float(e['size_m'][1])
        r = sc * float(e.get('crown_m', e['core_m']))
        parts.append(np.stack([rec[:, _F['x']].astype(np.float64), rec[:, _F['y']].astype(np.float64), top, r], 1))
    return np.concatenate(parts) if parts else np.zeros((0, 4))


def canopy_line(x, y, crowns, to_sun, chunk=20000):
    """Per card (at x, y) the height of the shadow line the crowns toward the sun cast on it: a crown [x, y, top, r]
    nearer the sun on the card's line of light, within its radius r of it across the light and at most
    CANOPY_REACH_M along it, shades it below top - d tan(el), d its distance along the light; the highest such line,
    or -1e9 where none. Its own crown (d 0) does not count."""
    x, y = (np.asarray(v, np.float64).ravel() for v in (x, y))
    n = len(x)
    line = np.full(n, -1.0e9)
    d = np.asarray(to_sun, np.float64)
    d = d / max(float(np.linalg.norm(d)), 1e-9)
    hz = math.hypot(d[0], d[1])
    if not n or not len(crowns) or hz < 1e-6 or d[2] <= 0.0:
        return line
    ux, uy, tan_el = d[0] / hz, d[1] / hz, d[2] / hz
    cx, cy, ct, cr = (np.asarray(crowns[:, k], np.float64) for k in range(4))
    for s0 in range(0, n, chunk):
        s1 = min(n, s0 + chunk)
        i, j, _d = PL._pairs(x[s0:s1], y[s0:s1], cx, cy, CANOPY_REACH_M)
        if not len(i):
            continue
        dx, dy = cx[j] - x[s0:s1][i], cy[j] - y[s0:s1][i]
        along = dx * ux + dy * uy
        k = (along > 0.5) & (np.abs(dy * ux - dx * uy) < cr[j])
        if k.any():
            part = np.full(s1 - s0, -1.0e9)
            np.maximum.at(part, i[k], ct[j[k]] - along[k] * tan_el)
            line[s0:s1] = part
    return line


def _shade_ground(terrain):
    """[(x0, y0, side, h float32), ...] the terrain's context and main levels, finest first; [] without fields."""
    levels = getattr(terrain, 'levels', None)
    fields = getattr(terrain, 'fields', None)
    out = []
    if not levels or fields is None:
        return out
    for i, lv in enumerate(levels):
        if str(getattr(lv, 'role', 'main')) == 'hero':
            continue
        try:
            h = np.asarray(fields(i)['h'], np.float32)
        except (KeyError, IndexError, TypeError, AttributeError):
            continue
        out.append((float(lv.x0), float(lv.y0), float(lv.side), h))
    return out[::-1]


def _bilinear(a, fi, fj, outside=None):
    """a[j, i] at fractional indices (fi along columns, fj along rows), clamped; `outside`: the value where a point
    lies off the array by more than half a cell (None: clamp to the edge)."""
    nj, ni = a.shape
    ci = np.clip(fi, 0.0, ni - 1.001)
    cj = np.clip(fj, 0.0, nj - 1.001)
    i0, j0 = ci.astype(np.int64), cj.astype(np.int64)
    ti, tj = ci - i0, cj - j0
    v = ((a[j0, i0] * (1 - ti) + a[j0, i0 + 1] * ti) * (1 - tj) + (a[j0 + 1, i0] * (1 - ti) + a[j0 + 1, i0 + 1] * ti) * tj)
    if outside is not None:
        off = (fi < -0.5) | (fi > ni - 0.5) | (fj < -0.5) | (fj > nj - 0.5)
        v = np.where(off, outside, v)
    return v


def sun_shade(ground, x, y, z, to_sun):
    """0..1 shade of points (x, y, z) from the terrain (ground: _shade_ground's levels) under the sun at to_sun (a
    unit vector toward it); 1 where the ground toward the sun rises 3 m over the ray from the point, 0 where it
    stays 0.5 m under it, soft between (the sun's disc and a crown's own height). A sweep per level, not a march
    per point: along the light's direction s (away from the sun) a point is shaded when some ground q nearer the sun
    on its line has h(q) + s_q tan(el) over z + s tan(el), so the running maximum of h + s tan(el) along each line of
    a grid laid along the light gives every point its shade at once (a few seconds for 10^5 billboards, where a march
    took twenty). The levels each sweep their own window (the main level's ridges, the context's mountains), and
    the shade is the largest."""
    x, y, z = (np.asarray(v, np.float64).ravel() for v in (x, y, z))
    d = np.asarray(to_sun, np.float64)
    d = d / max(float(np.linalg.norm(d)), 1e-9)
    hz = math.hypot(d[0], d[1])
    if not len(x) or not ground or hz < 1e-6 or d[2] <= 0.0:
        return np.zeros(len(x)) if d[2] > 0.0 else np.ones(len(x))
    ux, uy, tan_el = d[0] / hz, d[1] / hz, d[2] / hz
    excess = np.full(len(x), -1.0e9)
    for x0, y0, side, h in ground:
        n = h.shape[0]
        c = side / n
        # the window's corners in (s, w): s = -(p . u) along the light, w across it
        cx = np.array([x0, x0 + side, x0, x0 + side])
        cy = np.array([y0, y0, y0 + side, y0 + side])
        s_c, w_c = -(cx * ux + cy * uy), -cx * uy + cy * ux
        s0, w0 = float(s_c.min()), float(w_c.min())
        ns = int(math.ceil((float(s_c.max()) - s0) / c)) + 1
        nw = int(math.ceil((float(w_c.max()) - w0) / c)) + 1
        S, Wg = np.meshgrid(s0 + np.arange(ns) * c, w0 + np.arange(nw) * c)        # rows along w, columns along s
        gx, gy = -S * ux - Wg * uy, -S * uy + Wg * ux
        H = _bilinear(h, (gx - x0) / c - 0.5, (gy - y0) / c - 0.5, outside=-1.0e9).reshape(S.shape)
        B = H + S * tan_el
        pm = np.maximum.accumulate(B, axis=1)
        pm = np.concatenate([np.full((nw, 1), -1.0e9), pm[:, :-1]], axis=1)      # the ground before each cell
        sp, wp = -(x * ux + y * uy), -x * uy + y * ux
        v = _bilinear(pm, (sp - s0) / c, (wp - w0) / c)
        excess = np.maximum(excess, v - (z + sp * tan_el))
    e = np.clip((excess + 0.5) / 3.5, 0.0, 1.0)
    return e * e * (3.0 - 2.0 * e)


def _shade_billboards(sun, log=None):
    """eido_shade and eido_canopy_z on every still billboard's points under this sun (the module note above)."""
    if sun is None or not _SHADE_GROUND:
        return 0
    to_sun = np.asarray(sun.matrix_world.to_3x3().col[2], np.float64)
    done = 0
    for name, kept in list(_SHADE_GROUND.items()):
        coll = bpy.data.collections.get(name)
        if coll is None:
            _SHADE_GROUND.pop(name, None)
            continue
        ground, crowns = kept['ground'], kept['crowns']
        meshes = {}
        for ob in coll.objects:
            if ob.type == 'MESH' and ob.name.endswith('_billboards') and ob.get('eido_plants') \
                    and json.loads(ob['eido_plants']).get('still'):
                meshes.setdefault(ob.data.name, ob.data)
        for me in meshes.values():
            n = len(me.vertices)
            org = me.attributes.get('eido_bb_origin')
            if not n or org is None:
                continue
            p = np.empty(n * 3, np.float32)
            org.data.foreach_get('vector', p)
            p = p.reshape(-1, 3)
            s = sun_shade(ground, p[:, 0], p[:, 1], p[:, 2], to_sun)
            at = me.attributes.get('eido_shade') or me.attributes.new('eido_shade', 'FLOAT', 'POINT')
            at.data.foreach_set('value', np.ascontiguousarray(s, np.float32))
            # the crowns' shadow line on each card (its points share its centre), over the card's centre
            cards, inv = np.unique(p, axis=0, return_inverse=True)
            line = canopy_line(cards[:, 0], cards[:, 1], crowns, to_sun)[inv.ravel()]
            c = np.clip(line - p[:, 2], CANOPY_NONE, -CANOPY_NONE)
            at = me.attributes.get('eido_canopy_z') or me.attributes.new('eido_canopy_z', 'FLOAT', 'POINT')
            at.data.foreach_set('value', np.ascontiguousarray(c, np.float32))
            me.update()
            done += n
    if log:
        log(f'[plants] the terrain\'s and the crowns\' shade on {done:,} billboard points')
    return done


# ------------------------------------------------------------------------------------------------ the call ---

def bind_sun(sun=None):
    """Bind SeedThree's plants to the scene's sun (the leaves' backlight, and the lamp the billboards cast from
    without receiving), and give every still billboard the terrain's shadow under it (eido_shade) and the shadow
    line its neighbours' crowns cast on it (eido_canopy_z): `sun` a sun lamp
    object, default the scene's strongest. Call it once the sky and its sun are final (again when the sun moves); it
    is eidoblend.trees.make_seed_tree.set_sun. Returns the lamp, or None when the scene has none."""
    _seedthree()
    from seedthree.bl.sun import find_sun, set_sun
    sun = sun or find_sun()
    if sun is None:
        return None
    lamp = set_sun(sun)
    _shade_billboards(sun)
    return lamp


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
    _SHADE_GROUND[coll.name] = dict(ground=_shade_ground(terrain),      # the billboards' shade, once the sun is
                                    crowns=_crowns(spots))              # known (bind_sun)
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
