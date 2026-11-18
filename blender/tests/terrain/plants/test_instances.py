"""The plant instancer's checks in Blender (surfacing design 5.4, package 4, items 1 and 3 on the instanced geometry):
a sparse stand planned on the synthetic valley (_ground.py) and instanced for a still shot
(plant_instances.instance_plants) with a camera at the focus, then read back from the evaluated scene, plant by plant:

  library     a SeedThree individual comes back from the plant library with its full level, its card level and
              its two billboard cards
  objects     each species' objects carry every spot once (SeedThree: the near and the billboard object on one points
              mesh; flora: one still stroke per individual)
  realised    nothing is realised but the billboards: the near object's evaluated geometry is instances only, and no
              grass stroke is realised (design 4.4)
  lod         the full level on the plants nearest the camera within hero_m (at most the hero count: set to 3, the
              3 nearest), the card level on the rest within the card distance, the billboard beyond it, picked from
              the camera
  billboards  the realised billboard mesh carries each plant's card centre and yaw (eido_bb_origin, eido_bb_yaw),
              and its material reads them instead of Object Info
  tint        each plant's own tone: the billboards read it from the mesh, the card and full levels from the instance
  match       a tree's billboard takes its measured gain on its foliage only, and its cut-out threshold
              (BILLBOARD_GAIN); a shrub without a match keeps SeedThree's billboard
  ground      no plant floats or is buried: each plant's lowest point lies where its base (the ground less its sink)
              puts it (a SeedThree plant reaches below its base by its own grown amount, scaled)
  height      each plant stands scale x size_m[1] tall above its base (a flora plant within its stroke's own height
              variation)

    bash run_blender.sh blender/tests/terrain/plants/test_instances.py
    (a GPU job when an individual must still be grown: queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

The SeedThree individual is the desert ecotope's blackbrush (seed 7), grown into the plant library on its first use.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import _ground as G  # noqa: E402
from eidoblend.terrain.build import plant_instances as PI  # noqa: E402
from eidoblend.terrain.build import plants as PL  # noqa: E402

RESULTS = []
F = {n: i for i, n in enumerate(PL.FIELDS)}
EVERYWHERE = ('water', 'snow', 'rock', 'talus', 'sand')
SHRUB_LOD = dict(hero_m=40.0, billboard_m=45.0, near_m=0.0)
GRASS_LOD = dict(hero_m=0.0, billboard_m=0.0, near_m=12.0)


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print(('PASS ' if ok else 'FAIL ') + name + (': ' + detail if detail else ''), flush=True)
    return ok


FIR = ('douglasFir', 11, {'height': 30, 'paramOverrides': {'length': {1: 0.14}, 'downAngle': {1: 98}}})


def ecotope():
    """A sparse stand: SeedThree shrubs at least 6 m apart, flora grass tufts at least 1.1 m apart (so each
    plant's geometry is its own), a few firs (the alpine spruce's individual) far apart, everywhere on the valley."""
    return dict(title='instancer test', species=[
        dict(name='fir', kind='tree', source=('seedthree', FIR[0], FIR[2], [FIR[1]]), size_m=(20.0, 30.0),
             core_m=25.0, max_cell_m=None, max_radius_m=200.0, lod_m_per_m=0.0, fade=(1.0, 1.0),
             cluster=dict(parents_per_ha=4.0, mu=2.0, sigma_m=20.0), density='0.0008', on=EVERYWHERE,
             lod=dict(hero_m=30.0, billboard_m=60.0, near_m=0.0)),
        dict(name='shrub', kind='shrub', source=('seedthree', 'blackbrush', {}, [7]), size_m=(0.9, 1.5),
             core_m=7.0, foot_m=1.0, max_cell_m=None, max_radius_m=110.0, lod_m_per_m=0.0, fade=(1.0, 1.0),
             cluster=dict(parents_per_ha=40.0, mu=3.0, sigma_m=10.0), density='0.012', on=EVERYWHERE,
             lod=SHRUB_LOD),
        dict(name='grass', kind='grass', source=('flora', 'galleta_dry', dict(seeds=[7, 13])), size_m=(0.3, 0.6),
             core_m=1.5, max_radius_m=30.0, lod_m_per_m=0.0, fade=(1.0, 1.0),
             cluster=dict(parents_per_ha=600.0, mu=4.0, sigma_m=2.0), density='0.2', on=EVERYWHERE, lod=GRASS_LOD),
    ])


def level_of(inst_object):
    """'hero', 'card' or 'billboard' of an instanced part, by the source collection it was copied into."""
    names = ' '.join(c.name for c in inst_object.original.users_collection)
    return 'hero' if '_full_source' in names else ('card' if '_near_source' in names else 'other')


def world_points(ob, dg):
    """(realized vertices (n, 3), [(level, instance bounding-box corners (8, 3))]) of an object as evaluated."""
    ev = ob.evaluated_get(dg)
    verts = np.zeros((0, 3))
    if ev.type == 'MESH':
        me = ev.to_mesh()
        if len(me.vertices):
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get('co', co)
            M = np.array(ev.matrix_world)
            co = co.reshape(-1, 3).astype(np.float64)
            verts = co @ M[:3, :3].T + M[:3, 3]
        ev.to_mesh_clear()
    boxes = []
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None or inst.parent.original != ob:
            continue
        o = inst.object
        bb = np.array([list(c) for c in o.bound_box], np.float64)
        M = np.array(inst.matrix_world)
        boxes.append((level_of(o), bb @ M[:3, :3].T + M[:3, 3]))
    return verts, boxes


def assign(xy, p):
    d = np.hypot(xy[:, 0][None, :] - p[:, 0][:, None], xy[:, 1][None, :] - p[:, 1][:, None])
    k = np.argmin(d, axis=1)
    return k, d[np.arange(len(p)), k]


def per_spot(rec, verts, boxes, reach, verts_level='billboard'):
    """Per spot and level, the lowest and highest z of the geometry nearest it (within reach metres across):
    {spot index: {level: (lo, hi)}}."""
    out = {}
    xy = rec[:, :2].astype(np.float64)
    if len(verts):
        for s0 in range(0, len(verts), 200000):
            v = verts[s0:s0 + 200000]
            k, d = assign(xy, v)
            ok = d <= reach
            for i in np.unique(k[ok]):
                z = v[ok & (k == i), 2]
                lo, hi = out.setdefault(int(i), {}).get(verts_level, (np.inf, -np.inf))
                out[int(i)][verts_level] = (min(lo, float(z.min())), max(hi, float(z.max())))
    for lvl, b in boxes:
        c = b.mean(0)
        k, d = assign(xy, c[None, :2])
        if d[0] <= reach:
            lo, hi = out.setdefault(int(k[0]), {}).get(lvl, (np.inf, -np.inf))
            out[int(k[0])][lvl] = (min(lo, float(b[:, 2].min())), max(hi, float(b[:, 2].max())))
    return out


def set_value(ob, name, value):
    ob.modifiers['Eido Plants'].node_group.nodes[name].outputs[0].default_value = float(value)
    ob.update_tag()


def main():
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    t = G.valley()
    f = t.info['focus'][0]
    spots = PL.plan_plants(t, ecotope(), log=None)
    shrubs, grass = spots.array('shrub'), spots.array('grass')
    print(f'[instances-test] {len(shrubs)} shrubs, {len(grass)} grass tufts planned in {time.time() - t0:.1f} s',
          flush=True)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (f[0], f[1], float(t.height_at(f[0], f[1])) + 1.7)

    plant = PI.grow_seedthree('blackbrush', 7, {})
    check('library: the SeedThree individual comes back with its full level, its card level and its billboard',
          bool(plant['levels'].get('LOD0')) and bool(plant['levels'].get('LOD2')) and len(plant['cards']) == 2,
          f"{plant['height_m']:.2f} m tall, {'from the library' if plant['from_cache'] else 'grown now'} in "
          f"{plant['seconds']} s")
    # how far each level reaches below and above the plant's base, as grown (before its objects go)
    extents = {'hero': (plant['bottom_m'], plant['top_m']),
               'card': PI._extent_z(plant['levels']['LOD2']),
               'billboard': (plant['centre_z'] - plant['half_h'], plant['centre_z'] + plant['half_h'])}
    for o in plant['objects']:
        bpy.data.objects.remove(o, do_unlink=True)

    # a measured billboard match for the fir, and none for the shrub: the fir's gain on its foliage only
    PI.BILLBOARD_GAIN[(FIR[0], FIR[1], json.dumps(PI.grown_dials(json.loads(json.dumps(FIR[2]))),
                                                  sort_keys=True))] = dict(gain=(0.8, 0.9, 1.1), alpha=0.6)
    ti = time.time()
    made = PI.instance_plants(spots, None, log=None)
    secs = time.time() - ti
    dg = bpy.context.evaluated_depsgraph_get()
    entry = {s['name']: s for s in spots.species}
    near_ob = next(o for o in made['shrub'] if not o.name.endswith('_billboards'))
    far_ob = next(o for o in made['shrub'] if o.name.endswith('_billboards'))

    # objects: every spot once
    n_shrub = len(near_ob.data.vertices)
    n_grass = sum(len(o.data.vertices) for o in made['grass'])
    check('objects: each species\' objects carry every spot once', n_shrub == len(shrubs) and n_grass == len(grass)
          and far_ob.data == near_ob.data,
          f"shrub {n_shrub} of {len(shrubs)} on {', '.join(o.name for o in made['shrub'])} (one points mesh); grass "
          f"{n_grass} of {len(grass)} on {', '.join(o.name for o in made['grass'])}; instanced in {secs:.1f} s")

    # realised: only the billboards
    ev = near_ob.evaluated_get(dg)
    me = ev.to_mesh()
    near_verts = len(me.vertices)
    ev.to_mesh_clear()
    realised = [o.name for o in made['grass'] if json.loads(o['eido_plants']).get('motion')
                or len(o.evaluated_get(dg).data.vertices) > len(o.data.vertices)]
    check('realised: nothing but the billboards (the shrubs\' full and card levels are instances, the grass still '
          'strokes)', near_verts == 0 and not realised,
          f'{near_verts} realised vertices on {near_ob.name}; ' + (', '.join(realised) or
                                                                   f"{len(made['grass'])} still strokes"))

    # lod: which level stands where, chosen by the camera
    info = json.loads(near_ob['eido_plants'])
    bb_m, hero_m = info['billboard_m'], info['hero_m']
    camd = np.hypot(shrubs[:, 0] - cam.location.x, shrubs[:, 1] - cam.location.y)
    cam3 = np.sqrt(camd ** 2 + (shrubs[:, F['z']] - cam.location.z) ** 2)

    def lods_now():
        dg2 = bpy.context.evaluated_depsgraph_get()
        out = {}
        for o in made['shrub']:
            verts, boxes = world_points(o, dg2)
            for i, lv in per_spot(shrubs, verts, boxes, 2.5).items():
                out.setdefault(i, set()).update(lv)
        return out

    def want(k):
        order = np.argsort(cam3, kind='stable')
        hero = np.zeros(len(shrubs), bool)
        within = order[cam3[order] <= hero_m][:k]
        hero[within] = True
        return {i: ({'hero'} if hero[i] else ({'card'} if cam3[i] <= bb_m else {'billboard'}))
                for i in range(len(shrubs))}, int(hero.sum())
    got = lods_now()
    w, nh = want(PI.HERO_SHRUBS)
    wrong = [i for i in range(len(shrubs)) if got.get(i) != w[i]]
    check('lod: the full level on the nearest within hero_m of the camera, the card level within the card distance, '
          'billboards beyond', not wrong and len(shrubs) > 20 and nh > 3,
          f"{nh} hero (within {hero_m:g} m), {sum(1 for v in w.values() if v == {'card'})} card, "
          f"{sum(1 for v in w.values() if v == {'billboard'})} billboard shrubs (cards within {bb_m:.0f} m)"
          + (f'; wrong: {[(i, got.get(i), w[i]) for i in wrong[:5]]}' if wrong else ''))
    set_value(near_ob, 'Hero Count', 3)
    got3 = lods_now()
    w3, nh3 = want(3)
    wrong = [i for i in range(len(shrubs)) if got3.get(i) != w3[i]]
    check('lod: the hero count caps the full level, the nearest first (Hero Count 3)', not wrong and nh3 == 3,
          f'{sum(1 for v in got3.values() if "hero" in v)} at the full level'
          + (f'; wrong: {[(i, got3.get(i), w3[i]) for i in wrong[:5]]}' if wrong else ''))
    set_value(near_ob, 'Hero Count', PI.HERO_SHRUBS)

    # billboards: the realised mesh carries the card centre and the yaw of its plant
    dg = bpy.context.evaluated_depsgraph_get()
    ev = far_ob.evaluated_get(dg)
    me = ev.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    has = 'eido_bb_origin' in me.attributes and 'eido_bb_yaw' in me.attributes
    ok_attr, detail = False, f'{n} vertices; attributes {sorted(a.name for a in me.attributes if a.name.startswith("eido"))}'
    if has and n:
        org = np.empty(n * 3, np.float32)
        me.attributes['eido_bb_origin'].data.foreach_get('vector', org)
        org = org.reshape(-1, 3)
        yaw = np.empty(n, np.float32)
        me.attributes['eido_bb_yaw'].data.foreach_get('value', yaw)
        k, d = assign(shrubs[:, :2].astype(np.float64), co[:, :2].astype(np.float64))
        rec = shrubs[k]
        s = rec[:, F['scale']].astype(np.float64) * entry['shrub']['size_m'][1] / plant['top_m']
        base = PI._base_z(rec, entry['shrub']['sink'], entry['shrub']['foot_m'])
        want_o = np.stack([rec[:, 0], rec[:, 1], base + s * plant['centre_z']], 1)
        e_org = float(np.abs(org - want_o).max())
        e_yaw = float(np.abs(yaw - rec[:, F['yaw']]).max())
        ok_attr = e_org < 2e-3 and e_yaw < 1e-5
        detail += f'; card centre off by at most {e_org * 1000:.2f} mm, yaw {e_yaw:.1e} rad'
    ev.to_mesh_clear()
    mats = [m for m in far_ob.evaluated_get(dg).data.materials if m is not None] if n else []
    reads = all(not any(nd.bl_idname == 'ShaderNodeObjectInfo' for nd in m.node_tree.nodes)
                and any(nd.bl_idname == 'ShaderNodeAttribute' and nd.attribute_name == 'eido_bb_origin'
                        for nd in m.node_tree.nodes) for m in mats)
    check('billboards: one realised mesh carrying each plant\'s card centre and yaw, its material reading them',
          ok_attr and bool(mats) and reads, detail + f"; materials {', '.join(m.name for m in mats)}")

    # tint: each plant's own tone, the spots' tint field, read from the realised mesh and from the instances
    def reads_tint(m, kind):
        return any(nd.bl_idname == 'ShaderNodeAttribute' and nd.attribute_name == 'eido_tint'
                   and nd.attribute_type == kind for nd in m.node_tree.nodes)
    near_mats = {m for inst in dg.object_instances if inst.is_instance and inst.parent is not None
                 and inst.parent.original == near_ob for m in inst.object.original.data.materials if m}
    check('tint: the billboards read each plant\'s tint from the mesh, the card and full levels from the instance',
          bool(mats) and all(reads_tint(m, 'GEOMETRY') for m in mats) and bool(near_mats)
          and all(reads_tint(m, 'INSTANCER') for m in near_mats),
          f"{len(mats)} billboard and {len(near_mats)} near materials: "
          + ', '.join(sorted(m.name for m in near_mats))[:300])

    # the match: a tree's billboard takes its measured gain on its foliage only and its cut-out threshold; a shrub
    # without a measured match keeps SeedThree's billboard (no gain, the 0.35 cut-out)
    def bb_mats(species):
        col = next(c for c in bpy.data.collections if c.name.endswith(f'_{species}_billboard_source'))
        return [m for ch in col.children for o in ch.objects for m in o.data.materials if m]

    def cut_of(m):
        return [round(n.inputs[1].default_value, 3) for n in m.node_tree.nodes
                if n.bl_idname == 'ShaderNodeMath' and n.operation == 'GREATER_THAN' and n.inputs[0].links
                and n.inputs[0].links[0].from_socket.name == 'Alpha']
    fir_m, shrub_m = bb_mats('fir'), bb_mats('shrub')

    def foliage_mask(m):
        return any(n.bl_idname == 'ShaderNodeMapRange' and abs(n.inputs['From Max'].default_value
                                                                - PI.FOLIAGE_EDGE) < 1e-6 for n in m.node_tree.nodes)
    masked = all(foliage_mask(m) for m in fir_m)
    plain = not any(foliage_mask(m) for m in shrub_m)
    check('match: the tree\'s billboard takes its gain on its foliage only and its cut-out, the unmatched shrub\'s '
          'stays as SeedThree baked it', bool(fir_m) and masked and plain
          and all(cut_of(m) == [0.6] for m in fir_m) and all(cut_of(m) == [PI.ALPHA_CUT] for m in shrub_m),
          f"fir {[m.name for m in fir_m]} cut-outs {[cut_of(m) for m in fir_m]}; shrub cut-outs "
          f"{[cut_of(m) for m in shrub_m]}")

    # ground and height, plant by plant and level by level: each level's geometry stands where that level's own
    # extent, scaled to the spot, puts it over the spot's base (the ground less its sink). SeedThree's levels reach
    # below the base as grown (roots, flare, low twigs) and its billboard is the full level's box padded 3 %; a flora
    # tuft roots at its base and stands its stroke's height (0.85-1.15 of the spot's, per plant)
    dg = bpy.context.evaluated_depsgraph_get()
    k0 = plant['top_m']
    for name, rec, objs, reach in (('shrub', shrubs, made['shrub'], 2.5), ('grass', grass, made['grass'], 0.5)):
        e = entry[name]
        scale = rec[:, F['scale']].astype(np.float64)
        base = PI._base_z(rec, e['sink'], e['foot_m'] if name == 'shrub' else 0.5 * e['foot_m'])
        tall = scale * e['size_m'][1]
        found = {}
        for o in objs:
            verts, boxes = world_points(o, dg)
            vlevel = 'billboard' if name == 'shrub' else 'still'
            boxes = boxes if name == 'shrub' else [('still', b) for _l, b in boxes]
            for i, lv in per_spot(rec, verts, boxes, reach, vlevel).items():
                found.setdefault(i, {}).update(lv)
        rows = []
        ok_ground = ok_height = True
        for kind in sorted({k for v in found.values() for k in v}):
            idx = np.array(sorted(i for i, v in found.items() if kind in v), np.int64)
            lo = np.array([found[i][kind][0] for i in idx])
            hi = np.array([found[i][kind][1] for i in idx])
            if name == 'shrub':
                b, tp = extents[kind]
                s = tall[idx] / k0
                off_lo = lo - (base[idx] + s * b)
                off_hi = hi - (base[idx] + s * tp)
                ok_ground &= float(np.abs(off_lo).max()) <= 0.01
                ok_height &= float(np.abs(off_hi).max()) <= 0.01
                rows.append(f'{kind} x{len(idx)}: lowest {off_lo.min() * 100:+.1f}..{off_lo.max() * 100:+.1f} cm, '
                            f'top {off_hi.min() * 100:+.1f}..{off_hi.max() * 100:+.1f} cm from its own extent')
            else:
                off_lo = lo - base[idx]
                h = (hi - base[idx]) / tall[idx]
                ok_ground &= float(np.abs(off_lo).max()) <= 0.005
                ok_height &= float(h.max()) <= 1.16 and float(h.min()) >= 0.84
                rows.append(f'{kind} x{len(idx)}: lowest {off_lo.min() * 100:+.2f}..{off_lo.max() * 100:+.2f} cm '
                            f'from the base, height {h.min():.3f}-{h.max():.3f} of the spot\'s')
        check(f'ground: {name}: every plant\'s lowest point lies where its base puts it (none floats, none is buried)',
              ok_ground and len(found) == len(rec), f'{len(found)} of {len(rec)}; ' + '; '.join(rows))
        check(f'height: {name}: each plant stands scale x size_m[1] tall above its base', ok_height, '; '.join(rows))
    bad = [n for n, ok in RESULTS if not ok]
    print(f'[instances-test] {len(RESULTS) - len(bad)}/{len(RESULTS)} PASS in {time.time() - t0:.0f} s'
          + ('; FAIL: ' + '; '.join(bad) if bad else ''), flush=True)
    os._exit(1 if bad else 0)


main()
