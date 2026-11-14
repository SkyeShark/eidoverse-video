"""The plant instancer's checks in Blender (surfacing design 5.4, package 4, item 1 on the instanced geometry): a
sparse stand planned on the synthetic valley (_ground.py) and instanced (plant_instances.instance_plants) with a
camera at the focus, then read back from the evaluated scene, plant by plant:

  library     a SeedThree individual comes back from the plant library with its full level, its card level and
              its two billboard cards
  objects     each species' objects carry every spot once (SeedThree: near and billboard objects on one points mesh,
              a hero object; flora: one still stroke per individual, never realised)
  lod         SeedThree's card level stands only within the card distance of the camera, its billboards only beyond,
              its full level only within hero_m of the focus
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
SHRUB_LOD = dict(hero_m=18.0, billboard_m=45.0, near_m=0.0)
GRASS_LOD = dict(hero_m=0.0, billboard_m=0.0, near_m=12.0)


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print(('PASS ' if ok else 'FAIL ') + name + (': ' + detail if detail else ''), flush=True)
    return ok


def ecotope():
    """A sparse stand: SeedThree shrubs at least 6 m apart, flora grass tufts at least 1.1 m apart (so each
    plant's geometry is its own), everywhere on the valley."""
    return dict(title='instancer test', species=[
        dict(name='shrub', kind='shrub', source=('seedthree', 'blackbrush', {}, [7]), size_m=(0.9, 1.5),
             core_m=7.0, foot_m=1.0, max_cell_m=None, max_radius_m=110.0, lod_m_per_m=0.0, fade=(1.0, 1.0),
             cluster=dict(parents_per_ha=40.0, mu=3.0, sigma_m=10.0), density='0.012', on=EVERYWHERE,
             lod=SHRUB_LOD),
        dict(name='grass', kind='grass', source=('flora', 'galleta_dry', dict(seeds=[7, 13])), size_m=(0.3, 0.6),
             core_m=1.5, max_radius_m=30.0, lod_m_per_m=0.0, fade=(1.0, 1.0),
             cluster=dict(parents_per_ha=600.0, mu=4.0, sigma_m=2.0), density='0.2', on=EVERYWHERE, lod=GRASS_LOD),
    ])


def world_points(ob, dg):
    """(realized vertices (n, 3), [(instance bounding-box corners (8, 3))]) of an object as evaluated."""
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
        boxes.append(bb @ M[:3, :3].T + M[:3, 3])
    return verts, boxes


def per_spot(rec, verts, boxes, reach):
    """Lowest and highest z of the geometry nearest each spot (within reach metres across): {spot index: (lo, hi)}."""
    out = {}
    xy = rec[:, :2].astype(np.float64)

    def assign(p):
        d = np.hypot(xy[:, 0][None, :] - p[:, 0][:, None], xy[:, 1][None, :] - p[:, 1][:, None])
        k = np.argmin(d, axis=1)
        return k, d[np.arange(len(p)), k]
    if len(verts):
        for s0 in range(0, len(verts), 200000):
            v = verts[s0:s0 + 200000]
            k, d = assign(v)
            ok = d <= reach
            for i in np.unique(k[ok]):
                z = v[ok & (k == i), 2]
                lo, hi = out.get(int(i), (np.inf, -np.inf))
                out[int(i)] = (min(lo, float(z.min())), max(hi, float(z.max())))
    for b in boxes:
        c = b.mean(0)
        k, d = assign(c[None, :2])
        if d[0] <= reach:
            lo, hi = out.get(int(k[0]), (np.inf, -np.inf))
            out[int(k[0])] = (min(lo, float(b[:, 2].min())), max(hi, float(b[:, 2].max())))
    return out


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

    made = PI.instance_plants(spots, None, log=None)
    dg = bpy.context.evaluated_depsgraph_get()
    entry = {s['name']: s for s in spots.species}

    # objects: every spot once
    n_shrub = sum(len(o.data.vertices) for o in made['shrub'] if not o.name.endswith('_billboards'))
    n_grass = sum(len(o.data.vertices) for o in made['grass'])
    check('objects: each species\' objects carry every spot once', n_shrub == len(shrubs) and n_grass == len(grass),
          f"shrub {n_shrub} of {len(shrubs)} on {', '.join(o.name for o in made['shrub'])}; grass {n_grass} of "
          f"{len(grass)} on {', '.join(o.name for o in made['grass'])}")
    # a grass stroke is instances of its one plant, never a realised field (design 4.4)
    realised = [o.name for o in made['grass'] if json.loads(o['eido_plants']).get('motion')
                or len(o.evaluated_get(dg).data.vertices) > len(o.data.vertices)]
    check('objects: no grass is realised (still strokes: instances of one grown plant)', not realised,
          ', '.join(realised) or f"{len(made['grass'])} still strokes")

    # lod: which level stands where
    bb_m = max(json.loads(o['eido_plants'])['billboard_m'] for o in made['shrub'])
    hero_m = max(json.loads(o['eido_plants'])['hero_m'] for o in made['shrub'])
    camd = np.hypot(shrubs[:, 0] - cam.location.x, shrubs[:, 1] - cam.location.y)
    focd = np.hypot(shrubs[:, 0] - f[0], shrubs[:, 1] - f[1])
    lods = {}
    for o in made['shrub']:
        kind = 'hero' if o.name.endswith('_hero') else ('billboard' if o.name.endswith('_billboards') else 'card')
        verts, boxes = world_points(o, dg)
        for i in per_spot(shrubs, verts, boxes, 2.5):
            lods.setdefault(i, set()).add(kind)
    hero = focd <= hero_m
    want = {i: ({'hero'} if hero[i] else ({'card'} if camd[i] <= bb_m else {'billboard'})) for i in range(len(shrubs))}
    wrong = [i for i in range(len(shrubs)) if lods.get(i) != want[i]]
    check('lod: the full level within hero_m of the focus, the card level within the card distance of the camera, '
          'billboards beyond', not wrong and len(shrubs) > 20,
          f"{int(hero.sum())} hero (within {hero_m:g} m), {int(((~hero) & (camd <= bb_m)).sum())} card, "
          f"{int(((~hero) & (camd > bb_m)).sum())} billboard shrubs (cards within {bb_m:.0f} m)"
          + (f"; wrong: {[(i, lods.get(i), want[i]) for i in wrong[:5]]}"
                                                             if wrong else ''))

    # ground and height, plant by plant and level by level: each level's geometry stands where that level's own
    # extent, scaled to the spot, puts it over the spot's base (the ground less its sink). SeedThree's levels reach
    # below the base as grown (roots, flare, low twigs) and its billboard is the full level's box padded 3 %; a flora
    # tuft roots at its base and stands its stroke's height (0.85-1.15 of the spot's, per plant), less where flora's
    # wind bends the near strokes' blades
    k0 = plant['top_m']
    for name, rec, objs, reach in (('shrub', shrubs, made['shrub'], 2.5), ('grass', grass, made['grass'], 0.5)):
        e = entry[name]
        scale = rec[:, F['scale']].astype(np.float64)
        base = PI._base_z(rec, e['sink'], e['foot_m'] if name == 'shrub' else 0.5 * e['foot_m'])
        tall = scale * e['size_m'][1]
        rows, n_found = [], 0
        ok_ground = ok_height = True
        for o in objs:
            if name == 'shrub':
                kind = 'hero' if o.name.endswith('_hero') else ('billboard' if o.name.endswith('_billboards')
                                                                else 'card')
            else:
                kind = 'near' if o.name.endswith('_near') else 'still'
            verts, boxes = world_points(o, dg)
            got = per_spot(rec, verts, boxes, reach)
            if not got:
                continue
            idx = np.array(sorted(got), np.int64)
            n_found += len(idx)
            lo = np.array([got[i][0] for i in idx])
            hi = np.array([got[i][1] for i in idx])
            if name == 'shrub':
                b, t = extents[kind]
                s = tall[idx] / k0
                off_lo = lo - (base[idx] + s * b)
                off_hi = hi - (base[idx] + s * t)
                ok_ground &= float(np.abs(off_lo).max()) <= 0.01
                ok_height &= float(np.abs(off_hi).max()) <= 0.01
                rows.append(f'{kind} x{len(idx)}: lowest {off_lo.min() * 100:+.1f}..{off_lo.max() * 100:+.1f} cm, '
                            f'top {off_hi.min() * 100:+.1f}..{off_hi.max() * 100:+.1f} cm from its own extent')
            else:
                off_lo = lo - base[idx]
                h = (hi - base[idx]) / tall[idx]
                ok_ground &= float(np.abs(off_lo).max()) <= 0.005
                ok_height &= float(h.max()) <= 1.16 and (kind == 'near' or float(h.min()) >= 0.84)
                rows.append(f'{kind} x{len(idx)}: lowest {off_lo.min() * 100:+.2f}..{off_lo.max() * 100:+.2f} cm '
                            f'from the base, height {h.min():.3f}-{h.max():.3f} of the spot\'s')
        check(f'ground: {name}: every plant\'s lowest point lies where its base puts it (none floats, none is buried)',
              ok_ground and n_found == len(rec), f'{n_found} of {len(rec)}; '
              + '; '.join(rows))
        check(f'height: {name}: each plant stands scale x size_m[1] tall above its base', ok_height, '; '.join(rows))
    bad = [n for n, ok in RESULTS if not ok]
    print(f'[instances-test] {len(RESULTS) - len(bad)}/{len(RESULTS)} PASS in {time.time() - t0:.0f} s'
          + ('; FAIL: ' + '; '.join(bad) if bad else ''), flush=True)
    os._exit(1 if bad else 0)


main()
