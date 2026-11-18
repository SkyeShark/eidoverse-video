"""The plants seen from the judge's cameras (surfacing design 5.4, package 4, items 2 and 3): each view of
surfacing_judge/views.json rendered as the review renders it (the recipe's terrain at its reference's extent, seed 1,
film quality, hero levels around an eye-level camera, the rocks, make_sky daylight with the sun 70 degrees left of
the view, 960 x 540, 16 samples, exposure -0.5) through the per-texel material with the plants:

  1. the terrain built in clay (make_terrain), its rocks scattered as make_terrain scatters them;
  2. its surface data baked (surface.bake_surface, cached);
  3. the plants planned on it at the camera (plants.plan_plants(data=); an eye view's camera stands where a person
     can stand, no plant's crown within STAND_M of it), their cover rasters added to the data
     (SurfaceData.add_maps(spots.cover_extra()): canopy, canopy_expected, canopy_far, shrubs, shrubs_far), so the
     material's forest, scrub and crowns read the one rule the plants were placed by (design 4.7);
  4. the per-texel material (surfacing.apply_surface(data=, cameras=[camera])), which reads those rasters;
  5. the plants instanced for a still shot (plant_instances.instance_plants: levels picked per frame by the camera).
A fresh file per view: a finished view's memory stays with the process. An eye view plants around its camera, an
aerial around the ground it looks at. A plan and its cover rasters are kept in the terrain's cache entry
(plants.cache_base), so a view rendered again re-plans nothing. A view whose judge camera frames no plants, or sees
nothing but them where its photograph looks over them, is reframed (REFRAME: where its aim lands instead, or how far
its camera walks toward the aim, and why; the record says so).

    bash run_blender.sh blender/tests/terrain/plants/render_plants.py [--views a,b] [--set acceptance|recipes|far]
        [--tag t] [--once] [--samples 16] [--no-rocks] [--no-plants] [--seed 0] [--grow] [--cost] [--bare]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

  --views    view names (as views.json names them), from every set; --set picks a set: acceptance (design 5.4's
             six), recipes (an eye view of every other recipe with an ecotope), far (aerials over forests: the
             far canopy and the hand-off); default acceptance
  --no-plants  the same view without plants: the material's canopy from expected_cover alone (plants=None)
  --once     one frame per view (no second, timed frame)
  --grow     only grow the SeedThree individuals the views' ecotopes name into the plant library
  --cost     after the timed frame, the frame again with each group of plant objects hidden in turn
  --bare     also the frame with the plants hidden and the material as it is (the ground under the plants: litter
             where the instances stand, the material's crowns beyond them)

Writes out/plants/views/<recipe>_<view>[_<tag>].png (and _bare.png) and out/plants/views/record[_<tag>].json: per
view the camera, the plan (species, counts, stems per hectare at home, seconds), the instancing (objects, card
distances, seconds), the frame seconds (the second frame is the one item 3 holds to 8 s) and the memory after each
stage. board_plants.py lays each beside its photograph.
"""
import gc
import json
import math
import os
import shutil
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'plants', 'views')
sys.path.insert(0, TN)
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import render_references as RR  # noqa: E402
from surfacing_judge import views as V  # noqa: E402
from judge import refs  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain import surface as SU  # noqa: E402
from eidoblend.terrain.build import dressing as DR  # noqa: E402
from eidoblend.terrain.build import palettes as P  # noqa: E402
from eidoblend.terrain.build import plant_instances as PI  # noqa: E402
from eidoblend.terrain.build import plants as PL  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

# the views (recipe, name in views.json)
SETS = {
    # design 5.4, package 4, item 2
    'acceptance': [('real_place', 'floor_lischmaad'), ('real_place', 'ridge_schynige'), ('canyon', 'approach_walk'),
                   ('caldera', 'rim_east'), ('fluvial_range', 'canyon_road'), ('dunes', 'interdune_floor')],
    # an eye view of every other recipe with an ecotope, beside its photograph where it has one
    'recipes': [('alpine_valley', 'floor_axis'), ('stratovolcano', 'walk_upper_flank'), ('cinder_cones', 'ground_se'),
                ('impact_crater', 'plain_north'), ('incised_meanders', 'rim_walk'), ('mesas_buttes', 'valley_view'),
                ('badlands', 'prairie_walk'), ('tower_karst', 'plain_fields'), ('sea_cliffs', 'clifftop_along'),
                ('rolling_hills', 'hilltop_walk'), ('meadow', 'eye_swales')],
    # forests from the air: the far canopy and the hand-off from the instances to it
    'far': [('caldera', 'aerial_far'), ('alpine_valley', 'aerial_axis'), ('fluvial_range', 'aerial_range_front')],
}
# views whose judge camera frames no plants, or only plants: where their aim lands instead (frame: (x, y) from the
# left, from the top), how far the camera walks toward the aim along the ground (forward_m; the terrain's hero
# levels follow it), how far its line of sight is kept clear of crowns where its photograph stands at a built
# overlook (vista_m), and why
REFRAME = {
    ('dunes', 'interdune_floor'): dict(frame=(0.5, 0.15),
                                       why='the judge\'s camera aims 13.7 degrees up at the dune face, the floor and '
                                           'its grass below the frame; namib_star_dunes_02 looks along the floor with '
                                           'the dune behind: pitched to 4.7 degrees'),
    ('caldera', 'rim_east'): dict(forward_m=335.0, vista_m=30.0,
                                  why='the judge\'s camera stands on the bench inside the rim, 335 m back from where '
                                      'the caldera wall steepens past 25 degrees and its rock begins; the forest on '
                                      'the bench and the rounded shoulder hides the lake from there. crater_lake_01 '
                                      'stands at the overlook wall on the edge, its vista kept open: walked forward '
                                      'to it, and the first 30 m of its line of sight kept clear of crowns (a pine '
                                      '10 m in front filled the frame)'),
}
EXPOSURE = -0.5
W, H = 960, 540
STAND_M = 1.5        # an eye view's camera: no plant's crown within this of it (where its photographer stands)
VISTA_STEP_M, VISTA_HALF_M = 5.0, 2.0   # an overlook's vista (REFRAME vista_m): no crown within 2 m of its line of
#                                         sight, in discs every 5 m along it


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(views=[s for s in (opt('--views') or '').split(',') if s], set=opt('--set', 'acceptance'),
                tag=opt('--tag', ''), once='--once' in a, samples=int(opt('--samples', '16')),
                rocks='--no-rocks' not in a, plants='--no-plants' not in a, seed=int(opt('--seed', '0')),
                grow='--grow' in a, cost='--cost' in a, bare='--bare' in a)


def chosen(a):
    if a['views']:
        return [(r, v) for vs in SETS.values() for r, v in vs if v in a['views']]
    return list(SETS[a['set']])


def plant_groups(made):
    """The plant objects by what they draw: {group: [objects]}."""
    out = {'seedthree near (full and card levels)': [], 'seedthree billboards': [], 'seedthree grove (wind)': [],
           'flora strokes': []}
    for obs in made.values():
        for o in obs:
            info = json.loads(o['eido_plants'])
            if 'seedthree' in info['source']:
                key = ('seedthree billboards' if o.name.endswith('_billboards') else
                       'seedthree near (full and card levels)' if info.get('still') else 'seedthree grove (wind)')
            else:
                key = 'flora strokes'
            out[key].append(o)
    return out


def frame_costs(sc, made):
    """Seconds of a frame with each group of plant objects hidden in turn, and with every plant hidden."""
    groups = plant_groups(made)
    groups['every plant'] = [o for obs in groups.values() for o in obs]
    out = {}
    for name, obs in groups.items():
        if not obs:
            continue
        for o in obs:
            o.hide_render = True
        bpy.ops.render.render(write_still=False)             # the scene re-synced without them
        t0 = time.time()
        bpy.ops.render.render(write_still=False)
        out['without ' + name] = round(time.time() - t0, 2)
        for o in obs:
            o.hide_render = False
    return out


def memory_gb():
    """This process's memory in GB, [now, the peak so far]: the working set on Windows; elsewhere the peak resident
    size for both; None when the platform tells neither."""
    try:
        import ctypes
        from ctypes import wintypes as WT

        class Counters(ctypes.Structure):
            _fields_ = [('cb', WT.DWORD), ('PageFaultCount', WT.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t)]
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = ctypes.c_void_p           # a pseudo-handle, pointer-sized
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), WT.DWORD]
        c = Counters()
        c.cb = ctypes.sizeof(Counters)
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return None
        return [round(c.WorkingSetSize / 2 ** 30, 2), round(c.PeakWorkingSetSize / 2 ** 30, 2)]
    except (AttributeError, OSError):
        try:
            import resource
            peak = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20, 2)
            return [peak, peak]
        except ImportError:
            return None


def save_record(path, key, entry):
    """Write one view's entry into the record, over what the file holds now: runs of other views may write the same
    record meanwhile (each process keeps its own views, never another's)."""
    try:
        with open(path, encoding='utf-8') as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        rec = {}
    rec[key] = entry
    tmp = f'{path}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, indent=1, default=str)
    os.replace(tmp, path)


def recipe_defaults(recipe, params):
    """(Recipe, its defaults with the knobs' own: palette, place, centre ...)."""
    R = A._registry.resolve(recipe)
    values, _ = R.resolve(params or None)
    dfl = dict(R.defaults)
    if getattr(R, 'defaults_for', None) is not None:
        dfl.update(R.defaults_for(values))
    return R, dfl


def grow(views):
    """Every SeedThree individual the views' ecotopes name, grown into the plant library (or found there)."""
    from eidoblend.terrain.build import ecotopes as E
    plan = V.load()
    seen, out = set(), []
    for recipe, _v in views:
        R, dfl = recipe_defaults(recipe, plan[recipe].get('params'))
        eco = E.get('auto', recipe=R, place=dfl.get('place'), palette=dfl.get('palette'))
        for s in eco['species']:
            src = E.source_dict(s['source'])
            if 'seedthree' not in src:
                continue
            for seed in src['seeds']:
                key = (src['seedthree'], int(seed), json.dumps(src['dials'], sort_keys=True))
                if key in seen:
                    continue
                seen.add(key)
                p = PI.grow_seedthree(src['seedthree'], seed, src['dials'])
                out.append(dict(ecotope=eco['name'], species=s['name'], seedthree=src['seedthree'], seed=int(seed),
                                height_m=round(p['height_m'], 2), width_m=round(p['width_m'], 2),
                                from_cache=p['from_cache'], seconds=p['seconds']))
                for o in p['objects']:
                    bpy.data.objects.remove(o, do_unlink=True)
                bpy.data.orphans_purge(do_recursive=True)       # its meshes and bakes live on in the library
    return out


def aim_camera(cam, eye, target, frame, lens):
    """The review's rule (review_views.aim_camera): cam at eye, `target` landing at `frame` (0..1 from the left,
    from the top) of a 36 mm horizontal sensor."""
    cam.data.lens = lens
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36.0
    dx, dy, dz = target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]
    yaw_t = math.atan2(dy, dx)
    pitch_t = math.atan2(dz, math.hypot(dx, dy))
    u = (frame[0] - 0.5) * 36.0 / lens
    v = (0.5 - frame[1]) * (36.0 * H / W) / lens
    yaw = yaw_t + math.atan(u)
    pitch = pitch_t - math.atan(v)
    d = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
    RR.place_camera(cam, eye, (eye[0] + 1000.0 * d[0], eye[1] + 1000.0 * d[1], eye[2] + 1000.0 * d[2]))
    return (90.0 - math.degrees(yaw)) % 360.0, math.degrees(pitch)


def sky_and_sun(sc, cam, cache):
    """make_sky as the review sets it (the sun 70 degrees left of the view), baked."""
    bpy.context.view_layer.update()
    d = cam.matrix_world.col[2][:3]
    hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
    os.makedirs(cache, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    return sky


def frame_seconds(sc, path, once):
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    first = time.time() - t0
    if once:
        return first, None
    t0 = time.time()
    bpy.ops.render.render(write_still=False)            # the second frame: shaders compiled, instances evaluated
    return first, time.time() - t0


def palette_of(t):
    """(palette, strata) as make_terrain passes them for this terrain (a real place: its own palette and strata)."""
    place = t.info.get('place')
    if place and place in P.PLACES:
        return P.PLACES[place].get('palette') or 'auto', P.PLACES[place].get('strata')
    return 'auto', None


def rocks(t, pal, name):
    """The palette's rocks around the focus, as make_terrain scatters them (api._build_blender)."""
    spec = P.get(pal, t.recipe).get('dressing')
    if not spec or not t.info.get('focus'):
        return None
    fx, fy = np.mean(np.asarray(t.info['focus'], np.float64), axis=0)

    def mask_at(nm, x, y):
        return t.masks[nm].at(x, y) if nm in t.masks else None
    exclude = [(f['at'][0], f['at'][1], float(f.get('radius', 0.0))) for f in t.flats if f.get('radius')]
    return DR.scatter_rocks(spec, mask_at=mask_at, height_at=t.height_at, normal_at=t.normal_at,
                            focus=(float(fx), float(fy)), seed=t.info['seed'], name=name + '_rocks', log=print)


def main():
    a = args()
    plan = V.load()
    views = chosen(a)
    os.makedirs(OUT, exist_ok=True)
    if a['grow']:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        grown = grow(views)
        with open(os.path.join(OUT, 'grown.json'), 'w', encoding='utf-8') as fh:
            json.dump(grown, fh, indent=1)
        print(f'[render_plants] {len(grown)} SeedThree individuals in the plant library', flush=True)
        os._exit(0)
    tag = f"_{a['tag']}" if a['tag'] else ''
    rec_path = os.path.join(OUT, f'record{tag}.json')
    sky_root = os.path.join(OUT, '_sky')
    for recipe, vname in views:
        t0 = time.time()
        key = f'{recipe}_{vname}' + ('' if a['plants'] else '_noplants')
        r = {}
        try:
            v = next(x for x in plan[recipe]['views'] if x['name'] == vname)
            sc = RR.new_scene((W, H), a['samples'], EXPOSURE)
            bpy.context.preferences.system.anisotropic_filter = 'FILTER_16'
            ref = plan[recipe].get('reference')
            size = refs.load(ref).extent if ref else None
            params = plan[recipe].get('params')
            _R, dfl = recipe_defaults(recipe, params)
            c0 = dfl.get('centre', (0.0, 0.0))
            rf = REFRAME.get((recipe, vname)) or {}
            vc = v['cam']
            if rf.get('forward_m'):                      # the camera walks toward the aim; the hero levels with it
                ux, uy = v['aim'][0] - vc[0], v['aim'][1] - vc[1]
                n = math.hypot(ux, uy)
                vc = [vc[0] + float(rf['forward_m']) * ux / n, vc[1] + float(rf['forward_m']) * uy / n]
            focus = [(c0[0] + vc[0], c0[1] + vc[1])] if v.get('focus') else None
            t = A.make_terrain(recipe, size=size, seed=1, params=params, quality='film', palette=None, dress=False,
                               focus=focus, name=f'{recipe}_plants')
            tb = time.time() - t0
            pal, strata = palette_of(t)
            t.info['palette'] = pal
            if a['rocks']:
                rocks(t, pal, f'{recipe}_plants')
            cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
            ex, ey = vc[0] + cx, vc[1] + cy
            kind, dz = v['cam_z']
            ground = float(t.height_at(ex, ey))
            ez = ground + float(dz) if kind == 'ground' else float(dz)
            tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
            cam = bpy.data.objects.new('plants_cam', bpy.data.cameras.new('plants_cam'))
            sc.collection.objects.link(cam)
            sc.camera = cam
            dist = math.dist((ex, ey, ez), (tx, ty, tz))
            if ez - ground < 50.0:
                cam.data.clip_start, cam.data.clip_end = 0.1, 4.0 * t.levels[0].side + 40000.0
            else:
                cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), 4.0 * t.levels[0].side + 40000.0
            frame, why_reframed = rf.get('frame', v.get('frame', (0.5, 0.5))), rf.get('why')
            heading, pitch = aim_camera(cam, (ex, ey, ez), (tx, ty, tz), frame, v['lens'])
            r = dict(camera=[round(ex, 1), round(ey, 1), round(ez, 1)], aim=[round(tx, 1), round(ty, 1), round(tz, 1)],
                     heading_deg=round(heading, 1), pitch_deg=round(pitch, 2), lens=v['lens'], kind=v.get('kind'),
                     focus=focus, levels=[str(lv) for lv in t.levels], cache_hit=t.info.get('cache_hit'),
                     build_s=round(tb, 1), caption=v.get('caption'), photo=v.get('photo'), palette=pal,
                     plants=a['plants'], reframed=why_reframed, memory_gb={})

            def stage(name):                             # the process's memory after each stage, kept on disk so a
                r['memory_gb'][name] = memory_gb()       # run that dies still says where its memory went
                save_record(rec_path, key + tag, r)
            stage('terrain')
            ts = time.time()
            try:
                sd = SU.bake_surface(t, palette=pal)
            except (ValueError, KeyError) as e:          # the palette's colours could not be baked: the maps alone
                print(f'[render_plants] {key}: the palette bake failed ({type(e).__name__}: {e}); the maps without '
                      f'the far colour', flush=True)
                r['palette_bake_failed'] = f'{type(e).__name__}: {e}'
                sd = SU.bake_surface(t, palette=None)
            r['surface_s'] = round(time.time() - ts, 1)
            made = {}
            tp = time.time()
            # an eye view plants around its camera; an aerial around the ground it looks at. An eye view's camera
            # is where its photographer stands, on ground a person can stand on: no plant's crown within STAND_M of
            # it (the camera stood inside a chaparral bush at the San Gabriel road, its flowers filling the frame,
            # under a pine on the cinder plain, and half a metre from a pine's crown at the caldera's rim, 11-18),
            # with the terrain's flats kept clear as plan_plants keeps them
            eye = ez - ground < 50.0
            pf = (ex, ey) if eye else (tx, ty)
            r['plant_focus'] = [round(pf[0], 1), round(pf[1], 1)]
            clear = None
            if eye:
                clear = [(fl['at'][0], fl['at'][1], float(fl.get('radius', 0.0)))
                         for fl in (getattr(t, 'flats', None) or []) if fl.get('radius')] + [(ex, ey, STAND_M, 'crown')]
                r['stand_m'] = STAND_M
                if rf.get('vista_m'):                    # an overlook: its line of sight kept open (REFRAME)
                    n = math.hypot(tx - ex, ty - ey)
                    clear += [(ex + s * (tx - ex) / n, ey + s * (ty - ey) / n, VISTA_HALF_M, 'crown')
                              for s in np.arange(VISTA_STEP_M, float(rf['vista_m']) + 1e-6, VISTA_STEP_M)]
                    r['vista_m'] = float(rf['vista_m'])
            if a['plants']:
                # the plan and its cover rasters are kept in the terrain's cache entry (plants.cache_base: keyed by
                # the ecotope, the seed, the focus, the clear discs, the bake and the plant code), so a view
                # rendered again re-plans nothing
                base = PL.cache_base(t, 'auto', focus=pf, seed=a['seed'], data=sd, exclude=clear)
                spots = None
                if base and os.path.exists(base + '.plants.json'):
                    try:
                        spots = PL.PlantSpots.load(base, terrain=t, data=sd)
                        r['plan_cached'] = True
                    except (OSError, ValueError, KeyError) as e:
                        print(f'[render_plants] the cached plan does not load ({e}): planning again', flush=True)
                if spots is None:
                    spots = PL.plan_plants(t, 'auto', focus=pf, seed=a['seed'], data=sd, exclude=clear)
                    if base:
                        spots.save(base)
                r['plan_s'] = round(time.time() - tp, 2)
                tc = time.time()
                extra = None
                if base and os.path.exists(base + '.cover.npz'):
                    with np.load(base + '.cover.npz') as z:
                        names = sorted({k.rsplit('_L', 1)[0] for k in z.files})
                        extra = {k: [np.asarray(z[f'{k}_L{i}']) for i in range(len(t.levels))] for k in names}
                if extra is None:
                    extra = spots.cover_extra()
                    if base:
                        np.savez_compressed(base + '.cover.npz', **{f'{k}_L{i}': v for k, per in extra.items()
                                                                    for i, v in enumerate(per)})
                r['ecotope'] = spots.meta['ecotope']
                r['species'] = {n: dict(count=spots.count(n), per_ha_home=spots.stats[n].get('per_ha_home'),
                                        range_per_ha=spots.entry(n)['rule'].get('range_per_ha'))
                                for n in spots.names()}
                r['notes'] = list(spots.notes)
            else:
                extra = PL.expected_cover(t, data=sd)
                tc = time.time()
            sd.add_maps(extra)
            r['cover_s'] = round(time.time() - tc, 1)
            r['cover_means'] = {k: [round(float(x.mean()), 4) for x in per] for k, per in extra.items()}
            stage('plan')
            tm = time.time()
            S.apply_surface(t.obj, palette=pal, recipe=t.recipe, strata=strata, data=sd, cameras=[cam], log=print)
            r['material_s'] = round(time.time() - tm, 1)
            # the per-texel material reads no mask attribute: the rings' eido_<mask> attributes go, as
            # mesh.make_object(mask_attributes=False) leaves them out (thirty floats a vertex on 2-3 million
            # vertices), eido_level kept
            me = t.obj.data
            for nm in [at.name for at in me.attributes if at.name.startswith('eido_') and at.name != 'eido_level']:
                me.attributes.remove(me.attributes[nm])
            stage('material')
            if a['plants']:
                ti = time.time()
                made = PI.instance_plants(spots, t)
                r['instance_s'] = round(time.time() - ti, 1)
                r['objects'] = {n: [o.name for o in obs] for n, obs in made.items()}
                r['lod'] = {n: [json.loads(o['eido_plants']) for o in obs[:1]] for n, obs in made.items() if obs}
                bpy.context.view_layer.update()
                stage('instances')
            # nothing after this needs the plan's working arrays, the surface data's numpy maps or the terrain's
            # fields (the object, its images and the instances live in Blender): the caldera's first frame ran
            # past the 12 GB cap with them held (7.5 GB before the sky, 11-18)
            if a['plants']:
                spots._ground = None
                del spots
            del extra, sd, t
            gc.collect()
            stage('freed')
            sky_and_sun(sc, cam, os.path.join(sky_root, key))
            r['sun'] = getattr(PI.bind_sun(), 'name', None) if a['plants'] else None
            stage('sky')
            path = os.path.join(OUT, key + tag + '.png')
            first, second = frame_seconds(sc, path, a['once'])
            r.update(first_render_s=round(first, 1), second_render_s=None if second is None else round(second, 2),
                     total_s=round(time.time() - t0, 1), image=os.path.relpath(path, TN).replace(os.sep, '/'),
                     statistics=sc.statistics(bpy.context.view_layer))
            stage('frames')
            if a['bare'] and made:
                for obs in made.values():
                    for o in obs:
                        o.hide_render = True
                bare = os.path.join(OUT, key + '_bare' + tag + '.png')
                sc.render.filepath = bare
                bpy.ops.render.render(write_still=True)
                r['bare_image'] = os.path.relpath(bare, TN).replace(os.sep, '/')
                for obs in made.values():
                    for o in obs:
                        o.hide_render = False
            if a['cost'] and made:
                r['frame_costs_s'] = frame_costs(sc, made)
                print(f"[render_plants] {key}{tag}: frame costs {r['frame_costs_s']}", flush=True)
            print(f"[render_plants] {key}{tag}: build {tb:.0f} s, surface {r['surface_s']} s, plan {r.get('plan_s')} s, "
                  f"material {r['material_s']} s, instance {r.get('instance_s')} s, first frame {first:.1f} s"
                  + ('' if second is None else f', second {second:.2f} s'), flush=True)
        except Exception as e:                                   # noqa: BLE001 - recorded, the run goes on
            traceback.print_exc()
            r = dict(r, error=f'{type(e).__name__}: {e}')
        gc.collect()
        save_record(rec_path, key + tag, r)
    shutil.rmtree(sky_root, ignore_errors=True)
    print('[render_plants] done', flush=True)
    os._exit(0)


main()
