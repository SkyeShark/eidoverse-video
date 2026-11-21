"""The plant layer's oracles from the Blender edition (PORT_PLAN.md 5.1, 8.2 row P15): its own ecotopes and its own
plans, made by its own Python (numpy only: build/plants.py and ecotopes.py need no bpy), for tests/plants/*.

    EIDO_BLENDER_EDITION=<a checkout or a `git archive` export of the blender branch> \\
        <Blender's python> -I eidoverse/terrain/tests/plants/plants_fixtures.py --ecotopes
    ... plants_fixtures.py --spots [--case lauterbrunnen ...] [--debug]

--ecotopes  every ecotope, and the 'auto' ecotope of every recipe and every place, as ecotopes.get() gives it: its
            JSON, Python's canonical text of it (json.dumps(sort_keys=True), what ecotope_hash hashes) and the hash,
            check(), describe(), masks_used(), resolve_name(), and every species' source_dict()
--spots     per case (CASES: a snapshot of the Blender surface-data package, its Blender surface bake, and the plan's
            arguments), plan_plants on the bake's SurfaceData, as make_terrain plans with a bake: the spots files
            (PlantSpots.save), the cover rasters of every level (cover_extra) and expected_cover, with the plan's
            seconds and notes. --debug also keeps, per species, what _candidates, _thin and _hard_core returned (the
            candidates' ids as two uint32), so a difference can be traced to the step that makes it.

Inputs, read only: the snapshots (<Blender tests>/out/surface_data/snap/<case>.npz, in the Blender checkout that made
them: $EIDO_SNAPSHOT_EDITION when the code comes from an export, or --snaps <folder>) and the Blender bakes of the
surface data package's cases as tests/surface_data/blender_bakes.py copied them
(tests/out/surface_data/fixtures/blender_<commit>/bakes/<case>/; $EIDO_SURFACE_FIXTURES names the folder, else the
newest), or --bakes <a folder holding <case>/surface_<key>.json>. Outputs: tests/out/plants/fixtures/
blender_<commit>/ (git-ignored), its key.json naming the commit, the code hashes and the versions.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

TERRAIN = B.TERRAIN
OUT = os.path.join(TERRAIN, 'tests', 'out', 'plants', 'fixtures')

# the plan per case: the terrain's own focus (its info), seed 0, every species' own radius capped at radius_m (None:
# each species' own); exclude: discs kept clear ([x, y, r] or [x, y, r, 'crown'] in metres from the focus' first
# point, so a case reads the same wherever its terrain lies)
CASES = {
    'lauterbrunnen_r250': dict(snap='lauterbrunnen', radius_m=250.0, seed=0),       # small: the --debug case
    'lauterbrunnen': dict(radius_m=None, seed=0),
    'alpine_valley': dict(radius_m=700.0, seed=3),
    'canyon': dict(radius_m=None, seed=0),
    'toroweap': dict(radius_m=500.0, seed=1),
    'fluvial_range': dict(radius_m=None, seed=0),
    'great_sand_dunes': dict(radius_m=None, seed=0, exclude=[[0.0, 0.0, 6.0, 'crown']]),
    'badlands_sd': dict(radius_m=None, seed=2),
    'meteor_crater': dict(radius_m=None, seed=0),
}


def commit_of(edition):
    return (B.git(edition, 'rev-parse', '--short', 'HEAD') or os.environ.get('EIDO_PLANTS_COMMIT') or 'unknown')[:7]


def code_hash(edition, names):
    h = hashlib.sha1()
    for n in names:
        p = os.path.join(edition, 'blender', 'eidoblend', 'terrain', 'build', n)
        with open(p, 'rb') as f:
            h.update(f.read())
    return h.hexdigest()


def write_key(root, edition, commit):
    key = dict(commit=commit, plants_code=code_hash(edition, ['plants.py', 'ecotopes.py', 'palettes.py']),
               versions=B.versions(), date=time.strftime('%Y-%m-%d %H:%M:%S'))
    B.write_json(os.path.join(root, 'key.json'), key)
    return key


# ------------------------------------------------------------------------------------------------- ecotopes ---

def canonical(eco):
    from eidoblend.terrain.build import ecotopes as E
    return json.dumps(E._jsonable({k: v for k, v in eco.items() if k not in ('title',)}), sort_keys=True, default=str)


def ecotope_record(eco):
    from eidoblend.terrain.build import ecotopes as E
    return dict(name=eco['name'], json=B.jsonable(eco), canonical=canonical(eco), hash=E.ecotope_hash(eco),
                check=E.check(eco), masks_used=sorted(E.masks_used(eco)),
                sources=[E.source_dict(s['source']) for s in eco['species']])


def ecotopes(root):
    from eidoblend.terrain.build import ecotopes as E
    from eidoblend.terrain.build import palettes as P
    from eidoblend.terrain import recipes as RG
    out = dict(names=E.names(), by_name={}, by_recipe={}, by_recipe_name={}, by_place={}, resolve={})
    for n in E.names():
        eco = E.get(n)
        rec = ecotope_record(eco)
        rec['describe'] = E.describe(n)
        out['by_name'][n] = rec
    for rn in RG.names():
        R = RG.get(rn)
        out['by_recipe'][rn] = ecotope_record(E.get('auto', recipe=R))
        out['by_recipe_name'][rn] = ecotope_record(E.get('auto', recipe=rn))
        base, over = E.resolve_name('auto', recipe=R)
        out['resolve'][f'recipe:{rn}'] = [base, B.jsonable(over)]
    places = sorted(set(P.PLACES) | set(E.PLACE_ECOTOPES))
    R = RG.get('real_place')
    for pl in places:
        pal = P.PLACES[pl]['palette'] if pl in P.PLACES else None
        out['by_place'][pl] = dict(palette=pal, with_palette=ecotope_record(E.get('auto', recipe=R, place=pl, palette=pal)),
                                   without=ecotope_record(E.get('auto', recipe=R, place=pl)))
        out['resolve'][f'place:{pl}'] = [E.resolve_name('auto', recipe=R, place=pl, palette=pal)[0],
                                         E.resolve_name('auto', recipe=R, place=pl)[0]]
    out['describe_auto_fluvial'] = E.describe('auto', recipe='fluvial_range')
    # the Poisson tables the candidates invert (plants._poisson's cdf, float64), for every species' cell and cluster
    import math
    import numpy as np
    from eidoblend.terrain.build import plants as PL
    pois = {}
    for rn in RG.names():
        for s in E.get('auto', recipe=RG.get(rn))['species']:
            c = PL._cell_m(s)
            for what, mean in (('parents', s['cluster']['parents_per_ha'] * 1.0e-4 * c * c), ('mu', s['cluster']['mu'])):
                mean = float(mean)
                kmax = int(mean + 12.0 * math.sqrt(mean) + 24.0)
                k = np.arange(kmax + 1, dtype=np.float64)
                logp = -mean + k * math.log(mean) - np.concatenate([[0.0], np.cumsum(np.log(np.arange(1, kmax + 1)))])
                pois[f'{rn}/{s["name"]}/{what}'] = dict(mean=mean, cell_m=c, cdf=[float(v) for v in np.cumsum(np.exp(logp))])
    out['poisson'] = pois
    path = os.path.join(root, 'ecotopes', 'ecotopes.json')
    B.write_json(path, out)
    B.write_json(os.path.join(root, 'ecotopes', 'manifest.json'), dict(kind='ecotopes', file='ecotopes.json',
                                                                      count=len(out['by_name']) + len(out['by_recipe']) + len(out['by_place'])))
    print(f'[plants_fixtures] ecotopes: {len(out["by_name"])} ecotopes, {len(out["by_recipe"])} recipes, '
          f'{len(out["by_place"])} places -> {path}', flush=True)


# ---------------------------------------------------------------------------------------------------- spots ---

def bakes_root(a):
    if '--bakes' in a:
        return a[a.index('--bakes') + 1]
    base = os.path.join(TERRAIN, 'tests', 'out', 'surface_data', 'fixtures')
    want = os.environ.get('EIDO_SURFACE_FIXTURES')
    if want:
        return os.path.join(base, want, 'bakes')
    best, t = None, -1
    for nm in os.listdir(base) if os.path.isdir(base) else []:
        k = os.path.join(base, nm, 'key.json')
        if os.path.exists(k) and os.path.getmtime(k) > t:
            best, t = os.path.join(base, nm, 'bakes'), os.path.getmtime(k)
    return best


def bake_key(folder):
    for nm in sorted(os.listdir(folder)):
        if nm.startswith('surface_') and nm.endswith('.json') and '_pal' not in nm:
            return nm[len('surface_'):-len('.json')]
    return None


def load_case(name, snaps, bakes):
    from eidoblend.terrain import api as A
    from eidoblend.terrain import surface as S
    t = A.Terrain.load(os.path.join(snaps, name + '.npz'), build=False)
    folder = os.path.join(bakes, name)
    key = bake_key(folder)
    if key is None:
        raise FileNotFoundError(f'{name}: no surface bake in {folder}')
    with open(os.path.join(folder, f'surface_{key}.json'), encoding='utf-8') as f:
        info = json.load(f)
    hit = S.load_cached(folder, key, len(t.levels))
    if hit is None:
        raise FileNotFoundError(f'{name}: the bake in {folder} does not load')
    baked, binfo = hit
    sd = S.SurfaceData(t, baked, dict(binfo, cache_hit=True), info['options'], key, palette=None, cache_dir=folder)
    return t, sd, key


class Recorder:
    """Wraps plants.py's steps from outside (nothing in the Blender edition changes) and keeps what they return."""

    def __init__(self, PL):
        import numpy as np
        self.np = np
        self.PL = PL
        self.rec = {}
        self.order = []
        self._orig = (PL._candidates, PL._thin, PL._hard_core)
        self._group = 0

        def cands(s, keys, focus, reach, bounds):
            c = self._orig[0](s, keys, focus, reach, bounds)
            self._keep(s['name'], 'cand', c, dict(reach=float(reach)))
            return c

        def thin(s, c, ground, f, gi, exclude, feet, casters, st):
            out = self._orig[1](s, c, ground, f, gi, exclude, feet, casters, st)
            self._keep(s['name'], 'thin', out, dict(exact=float(gi['exact']), pad=float(gi['pad']),
                                                     spill=float(gi['spill']), core=float(gi['core'])))
            return out

        def hard(x, y, r, rank, tainted):
            acc, certain = self._orig[2](x, y, r, rank, tainted)
            g = f'group{self._group}'
            self._group += 1
            self.rec[g] = dict(x=x, y=y, r=r, rank=rank, tainted=tainted, acc=acc, certain=certain)
            self.order.append(g)
            return acc, certain
        PL._candidates, PL._thin, PL._hard_core = cands, thin, hard

    def _keep(self, name, step, c, extra):
        np = self.np
        k = f'{name}|{step}|{len([o for o in self.order if o.startswith(name + "|" + step)])}'
        d = {}
        for kk, v in (c or {}).items():
            v = np.asarray(v)
            if v.dtype == np.uint64:
                d[kk + '_lo'] = (v & np.uint64(0xFFFFFFFF)).astype(np.uint32)
                d[kk + '_hi'] = (v >> np.uint64(32)).astype(np.uint32)
            else:
                d[kk] = v
        self.rec[k] = d
        self.order.append(k)
        self.rec[k + '|meta'] = extra

    def restore(self):
        self.PL._candidates, self.PL._thin, self.PL._hard_core = self._orig

    def save(self, path):
        arrays, meta = {}, {}
        for k in self.order:
            for kk, v in self.rec[k].items():
                arrays[f'{k}|{kk}'] = v
            if k + '|meta' in self.rec:
                meta[k] = self.rec[k + '|meta']
        B.save_npz(path, arrays)
        return dict(steps=self.order, meta=meta)


def one_case(name, root, snaps, bakes, debug=False):
    import numpy as np
    from eidoblend.terrain.build import plants as PL
    from eidoblend.terrain.build import ecotopes as E
    args = dict(CASES[name])
    t, sd, key = load_case(args.get('snap', name), snaps, bakes)
    f = PL._focus_points(t.info.get('focus'))
    exclude = None
    if args.get('exclude'):
        exclude = [tuple([float(f[0, 0] + d[0]), float(f[0, 1] + d[1])] + list(d[2:])) for d in args['exclude']]
    out = os.path.join(root, 'spots', name)
    os.makedirs(out, exist_ok=True)
    rec = Recorder(PL) if debug else None
    t0 = time.perf_counter()
    try:
        spots = PL.plan_plants(t, 'auto', focus=None, radius_m=args.get('radius_m'), seed=int(args.get('seed', 0)),
                               data=sd, exclude=exclude, log=print)
    finally:
        if rec:
            rec.restore()
    plan_s = time.perf_counter() - t0
    paths = spots.save(os.path.join(out, name))
    t1 = time.perf_counter()
    cover = spots.cover_extra()
    cover_s = time.perf_counter() - t1
    B.save_npz(os.path.join(out, 'cover.npz'), {f'{k}_L{i}': np.asarray(v, np.float32)
                                                for k, per in cover.items() for i, v in enumerate(per)})
    t2 = time.perf_counter()
    exp_ = PL.expected_cover(t, data=sd)
    exp_s = time.perf_counter() - t2
    B.save_npz(os.path.join(out, 'expected.npz'), {f'{k}_L{i}': np.asarray(v, np.float32)
                                                   for k, per in exp_.items() for i, v in enumerate(per)})
    # the ground's derived rasters the densities read (per coarse level), for the port's derived-name checks
    g = spots._ground
    derived = {}
    for nm, per in (('dist_channel', g.dist_channel()), ('dist_water', g.dist_water()), ('fall_streak', g.fall_streak())):
        for i, a in enumerate(per):
            if a is not None:
                derived[f'{nm}_L{i}'] = np.asarray(a, np.float32)
    for i, a in enumerate(g.n20()):
        if a is not None:
            derived[f'n20x_L{i}'] = np.asarray(a[0], np.float32)
            derived[f'n20y_L{i}'] = np.asarray(a[1], np.float32)
    B.save_npz(os.path.join(out, 'derived.npz'), derived)
    eco = E.get('auto', recipe=t.recipe, place=t.info.get('place'), palette=t.info.get('palette'))
    info = dict(case=name, bake_key=key, args=args, exclude=[list(d) for d in (exclude or [])],
                focus=[[float(a), float(b)] for a, b in f], ecotope=eco['name'], ecotope_hash=E.ecotope_hash(eco),
                files=[os.path.basename(p) for p in paths], seconds=dict(plan=round(plan_s, 2), cover=round(cover_s, 2),
                                                                           expected=round(exp_s, 2)),
                notes=list(spots.notes), counts={s['name']: int(s['count']) for s in spots.species},
                constants={k: v for k, v in spots.meta['constants'].items()},
                levels=[dict(index=lv.index, role=lv.role, n=int(lv.n), cell=float(lv.cell), x0=float(lv.x0),
                             y0=float(lv.y0), side=float(lv.side)) for lv in t.levels])
    if rec:
        info['debug'] = rec.save(os.path.join(out, 'debug.npz'))
    B.write_json(os.path.join(out, 'info.json'), info)
    print(f'[plants_fixtures] {name}: {len(spots):,} plants of {len(spots.species)} species in {plan_s:.1f} s, cover '
          f'{cover_s:.1f} s, expected {exp_s:.1f} s -> {out}', flush=True)
    return info


def main():
    a = B.script_args()
    edition = B.bare_terrain_package()
    commit = a[a.index('--commit') + 1] if '--commit' in a else commit_of(edition)
    root = os.path.join(OUT, f'blender_{commit}')
    os.makedirs(root, exist_ok=True)
    key = write_key(root, edition, commit)
    print(f'[plants_fixtures] Blender edition at {commit} ({key["versions"]["python"]}, numpy '
          f'{key["versions"]["numpy"]}) -> {root}', flush=True)
    rc = 0
    if '--ecotopes' in a:
        ecotopes(root)
    if '--spots' in a:
        # the snapshots are outputs of the Blender surface-data package (git-ignored): in the Blender checkout that
        # ran it, $EIDO_SNAPSHOT_EDITION, when the code is read from an export of the commit
        snaps = os.path.join(os.environ.get('EIDO_SNAPSHOT_EDITION') or B.blender_edition(), 'blender', 'tests',
                             'terrain', 'out', 'surface_data', 'snap')
        if '--snaps' in a:
            snaps = a[a.index('--snaps') + 1]
        bakes = bakes_root(a)
        names = [a[i + 1] for i, v in enumerate(a) if v == '--case' and i + 1 < len(a)] or list(CASES)
        done = {}
        for nm in names:
            try:
                done[nm] = one_case(nm, root, snaps, bakes, debug='--debug' in a)
            except Exception as e:                       # noqa: BLE001 - reported; the other cases go on
                import traceback
                traceback.print_exc()
                done[nm] = dict(case=nm, error=repr(e))
                rc = 1
        path = os.path.join(root, 'spots', 'manifest.json')
        old = B.read_json(path, {}).get('cases', {})
        old.update(done)
        B.write_json(path, dict(kind='spots', commit=commit, snaps=snaps, bakes=bakes, cases=old))
    return rc


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    os._exit(code)
