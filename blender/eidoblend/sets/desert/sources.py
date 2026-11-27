"""eidoblend.sets.desert.sources: the simulated ground the desert is composed from, and the town it lies round. Blender
(the terrain family's GPU runner):

    from eidoblend.sets.desert import sources
    sources.simulate(work, quality='film')       # <work>/sources/{dunes,mesas,range}_L<i>.npz + SOURCES.json
    sources.town_mask(town_collection, work)     # <work>/sources/town_mask.npz: the town's footprint, its tracks' ends
    sources.plain_mask(work, extent=(840, 300))  # the same for a desert with no town in it: a rectangle, no tracks

simulate() runs three recipes of eidoblend.terrain (generate(): the levels' fields, no mesh), with the knobs the desert
was composed against, and keeps only what the land reads, each level with its window (x0, y0, side, cell, n):
  dunes  'dunes', kind 'star' (Werner transport with slip faces), seed 1, 8 km main tile: fields h, bed, sand
  mesas  'mesas_buttes' (caprock retreat over talus), seed 1, 8 km, hero levels to 1.95 m round the plateau edge the
         land turns toward the town: h, bed, deposit, wear, talus
  range  'fluvial_range' (stream power, threshold slopes, alluvial floors), seed 1, 12 km with context out to 192 km:
         h, bed, deposit, talus, A (drainage area)
quality 'film' runs them at 1024 cells a level (minutes each on a laptop GPU, cached by the terrain family in
eidoverse/assets/cache/terrain or EIDO_TERRAIN_CACHE); 'draft' at 512 and without hero levels (a test, a preview).
"""
import json
import os
import time

import numpy as np

RECIPES = {
    'dunes': dict(recipe='dunes', seed=1, params={'kind': 'star'}, fields=('h', 'bed', 'sand')),
    'mesas': dict(recipe='mesas_buttes', seed=1, focus=(-664.1, 1802.6), hero_cell=1.9,
                  params={'caprock_fraction': 0.08, 'relief_m': 320.0, 'floor_zs_m': 140.0, 'weathering_m_per_yr': 0.00022,
                          'fraying': 3.0, 'detail': True},
                  fields=('h', 'bed', 'deposit', 'wear', 'talus')),
    'range': dict(recipe='fluvial_range', seed=1,
                  params={'relief_m': 2000.0, 'valley_spacing_m': 320.0, 'threshold_deg': 29.0, 'age_myr': 2.0, 'roughness': 0.6,
                          'rock_contrast': 0.35, 'deposition': 0.5, 'floor_width_m': 170.0, 'trunk_faults': 3.5, 'rock': 1.0,
                          'gullies': True, 'uplift': 'ridge', 'azimuth_deg': 70.0, 'detail': True},
                  fields=('h', 'bed', 'deposit', 'talus', 'A')),
}


def src_dir(work):
    return os.path.join(os.path.abspath(work), 'sources')


def simulate(work, quality='film', cache=True, only=None, log=print):
    """the three recipes run (or read from the terrain cache) and their fields kept under <work>/sources/"""
    from ...terrain import generate
    out = src_dir(work)
    os.makedirs(out, exist_ok=True)
    rec = {'quality': quality, 'sources': {}}
    for name, spec in RECIPES.items():
        if only and name not in only:
            continue
        t0 = time.time()
        kw = dict(seed=spec['seed'], params=spec['params'], quality=quality, cache=cache, log=lambda *m: None)
        if quality != 'draft' and spec.get('focus'):
            kw.update(focus=spec['focus'], hero_cell=spec['hero_cell'])
        t = generate(spec['recipe'], **kw)
        levels = []
        for i, lv in enumerate(t.levels):
            f = t.fields(i)
            arrs = {k: np.asarray(f[k], np.float32) for k in spec['fields'] if k in f}
            np.savez_compressed(os.path.join(out, f'{name}_L{i}.npz'), x0=lv.x0, y0=lv.y0, side=lv.side, cell=lv.cell, n=lv.n, **arrs)
            levels.append(dict(role=lv.role, x0=lv.x0, y0=lv.y0, side=lv.side, cell=lv.cell, n=lv.n, fields=sorted(arrs)))
        for p in os.listdir(out):                                    # (a finer run's levels beyond this one's: gone)
            if p.startswith(f'{name}_L') and int(p[len(name) + 2:-4]) >= len(levels):
                os.remove(os.path.join(out, p))
        rec['sources'][name] = dict(recipe=spec['recipe'], seed=spec['seed'], params=spec['params'], levels=levels,
                                    cache_key=t.info.get('cache_key'), cache_hit=t.info.get('cache_hit'), seconds=round(time.time() - t0, 1))
        log(f'[desert] {name}: {spec["recipe"]} {len(levels)} levels, cache {"hit" if t.info.get("cache_hit") else "made"}, {time.time() - t0:.1f} s')
    old = {}
    p = os.path.join(out, 'SOURCES.json')
    if only and os.path.isfile(p):
        old = json.load(open(p, encoding='utf-8')).get('sources', {})
    rec['sources'] = dict(old, **rec['sources'])
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    return rec


def _save_mask(work, occ, x0, y0, cell, tracks):
    out = src_dir(work)
    os.makedirs(out, exist_ok=True)
    np.savez_compressed(os.path.join(out, 'town_mask.npz'), occ=occ, x0=x0, y0=y0, cell=cell, tracks=np.array(tracks, np.float32).reshape(-1, 5))


def town_mask(col, work, half=(1000.0, 700.0), cell=2.0, log=print):
    """the town's footprint as a raster of `cell` m over +-half (x, y), from a built town's collection (eidoblend.sets.
    town): everything standing on the ground (wires and what hangs high left out), and its ground's own quads that
    are not the plain (roads, yards, fields, tracks); and every track quad's (axis, x0, x1, y0, y1): the desert's
    tracks go on from their ends. The desert keeps its ground under the town's plane wherever the town has anything."""
    from mathutils import Vector
    X0, Y0 = -half[0], -half[1]
    NX, NY = int(round(2 * half[0] / cell)), int(round(2 * half[1] / cell))
    occ = np.zeros((NY, NX), np.uint8)

    def paint(x0, x1, y0, y1):
        i0, i1 = int(np.floor((x0 - X0) / cell)), int(np.ceil((x1 - X0) / cell))
        j0, j1 = int(np.floor((y0 - Y0) / cell)), int(np.ceil((y1 - Y0) / cell))
        occ[max(0, j0):max(0, min(NY, j1)), max(0, i0):max(0, min(NX, i1))] = 1
    n = 0
    for o in col.all_objects:
        if o.type != 'MESH' or o.name in ('town_ground', 'town_air'):
            continue
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        if min(v.z for v in bb) > 3.0:
            continue
        paint(min(v.x for v in bb), max(v.x for v in bb), min(v.y for v in bb), max(v.y for v in bb))
        n += 1
    g = col.all_objects.get('town_ground')
    tracks = []
    if g is not None:
        me = g.data
        names = [m.name if m else '' for m in me.materials]
        for p in me.polygons:
            nm = names[p.material_index]
            if nm == 'town.ground':
                continue
            vs = [g.matrix_world @ me.vertices[i].co for i in p.vertices]
            x0, x1, y0, y1 = min(v.x for v in vs), max(v.x for v in vs), min(v.y for v in vs), max(v.y for v in vs)
            paint(x0, x1, y0, y1)
            if nm in ('town.track', 'town.track_y'):
                tracks.append((0 if nm == 'town.track' else 1, x0, x1, y0, y1))
    _save_mask(work, occ, X0, Y0, cell, tracks)
    log(f'[desert] town mask: {n} objects, {int(occ.sum())} of {occ.size} cells; {len(tracks)} track quads')
    return len(tracks)


def plain_mask(work, extent=(840.0, 300.0), half=(1000.0, 700.0), cell=2.0):
    """a footprint for a desert round no town: the rectangle `extent` (centred), and no tracks"""
    NX, NY = int(round(2 * half[0] / cell)), int(round(2 * half[1] / cell))
    occ = np.zeros((NY, NX), np.uint8)
    i0, i1 = int((half[0] - extent[0] / 2) / cell), int((half[0] + extent[0] / 2) / cell)
    j0, j1 = int((half[1] - extent[1] / 2) / cell), int((half[1] + extent[1] / 2) / cell)
    occ[j0:j1, i0:i1] = 1
    _save_mask(work, occ, -half[0], -half[1], cell, [])
