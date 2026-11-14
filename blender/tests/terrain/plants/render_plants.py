"""The plants seen from the review's cameras (surfacing design 5.4, package 4, items 2 and 3): each acceptance view
rendered as the review renders it (surfacing/review_views.py: make_terrain at the judge's settings, the recipe's
palette, its rocks, make_sky daylight with the sun 70 degrees left of the view, 960 x 540, 16 samples, exposure
-0.5), with the terrain's plants planned at the camera (plants.plan_plants) and instanced
(plant_instances.instance_plants). A fresh file per view; give a run one view when the terrains are big, since a
finished view's memory stays with the process (the caldera, after the canyon in the same process, rendered over a
12 GB cap that it fits alone).

    bash run_blender.sh blender/tests/terrain/plants/render_plants.py [--views a,b] [--tag t] [--clay] [--once]
        [--samples 16] [--no-rocks] [--no-plants] [--seed 0] [--grow]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

  --views    view names of VIEWS (default all six), as out/review/views_plan.json names them
  --clay     the ground in grey clay (no palette: no material compile), for looking at the plants alone
  --no-plants  the same frame without plants (the board's 'before' from the same session)
  --once     one frame per view (no second, timed frame)
  --grow     only grow the SeedThree individuals the views' ecotopes name into the plant library
             (plant_instances.grow_seedthree; about a minute each, once), so the view runs take them from it
  --cost     after the timed frame, the frame again with each group of plant objects hidden in turn (SeedThree's
             card level, its billboards, its full level, flora's near and still strokes, every plant): what each
             costs, recorded with the scene's statistics
  --surface  bake the terrain's surface data first (surface.bake_surface), plan on it (plan_plants(data=)) and hand
             the plan's cover rasters back to it (SurfaceData.add_maps(spots.cover_extra())): the design's 5.3
             interface on a real terrain, timed (the material does not read the rasters yet)
  --frame-y  where the aim point lands, from the top (default the plan's): the same camera pitched to show the
             ground in front of it (the dunes view's plan aims 12 degrees up, its floor below the frame)

Writes out/plants/views/<recipe>_<view>[_<tag>].png and out/plants/views/record[_<tag>].json: per view the camera,
the plan (species, counts, stems per hectare at home, seconds), the instancing (objects, SeedThree's card distance,
seconds) and the frame seconds (the second frame is the one item 3 holds to 8 s). board_plants.py lays each beside
the photograph and the review's render of the same camera.
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
REVIEW = os.path.join(TN, 'out', 'review')
OUT = os.path.join(TN, 'out', 'plants', 'views')
sys.path.insert(0, TN)
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))

import bpy  # noqa: E402

import render_references as RR  # noqa: E402
from judge import refs  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain.build import plant_instances as PI  # noqa: E402
from eidoblend.terrain.build import plants as PL  # noqa: E402

# the acceptance views (design 5.4, package 4, item 2): (recipe, view name in views_plan.json)
VIEWS = [('real_place', 'floor_lischmaad'), ('real_place', 'ridge_schynige'), ('canyon', 'approach_walk'),
         ('caldera', 'rim_east'), ('fluvial_range', 'canyon_road'), ('dunes', 'interdune_floor')]
REF = {'fluvial_range': 'san_gabriel_mountains', 'alpine_valley': 'lauterbrunnen', 'caldera': 'crater_lake',
       'canyon': 'grand_canyon_toroweap', 'dunes': 'namib_star_dunes', 'real_place': 'lauterbrunnen'}
PARAMS = {'real_place': {'dem': 'lauterbrunnen'}}
TEX_EXPOSURE = -0.5
W, H = 960, 540


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(views=[s for s in (opt('--views') or '').split(',') if s], tag=opt('--tag', ''),
                clay='--clay' in a, once='--once' in a, samples=int(opt('--samples', '16')),
                rocks='--no-rocks' not in a, plants='--no-plants' not in a, seed=int(opt('--seed', '0')),
                grow='--grow' in a, cost='--cost' in a, surface='--surface' in a,
                frame_y=None if opt('--frame-y') is None else float(opt('--frame-y')),
                plan=opt('--plan', os.path.join(REVIEW, 'views_plan.json')))


def plant_groups(made):
    """The plant objects by what they draw: {group: [objects]}."""
    out = {'seedthree cards': [], 'seedthree billboards': [], 'seedthree full level': [], 'flora near': [],
           'flora still': []}
    for obs in made.values():
        for o in obs:
            info = json.loads(o['eido_plants'])
            if 'seedthree' in info['source']:
                key = ('seedthree billboards' if o.name.endswith('_billboards') else
                       'seedthree full level' if o.name.endswith('_hero') else 'seedthree cards')
            else:
                key = 'flora near' if info.get('motion') else 'flora still'
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
        from ctypes import wintypes as W

        class Counters(ctypes.Structure):
            _fields_ = [('cb', W.DWORD), ('PageFaultCount', W.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t)]
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = ctypes.c_void_p           # a pseudo-handle, pointer-sized
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), W.DWORD]
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


def recipe_centre(recipe, params):
    c = recipe_defaults(recipe, params)[1].get('centre', (0.0, 0.0))
    return float(c[0]), float(c[1])


def grow(views):
    """Every SeedThree individual the views' ecotopes name, grown into the plant library (or found there)."""
    from eidoblend.terrain.build import ecotopes as E
    seen, out = set(), []
    for recipe, _v in views:
        R, dfl = recipe_defaults(recipe, PARAMS.get(recipe))
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
    """make_sky as the review sets it (the sun 70 degrees left of the view), baked; then SeedThree's plants bound
    to its sun (their backlight, and the billboards' cast-only shadow)."""
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


def main():
    a = args()
    plan = json.load(open(a['plan'], encoding='utf-8'))
    views = [(r, v) for r, v in VIEWS if not a['views'] or v in a['views']]
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
    rec = json.load(open(rec_path, encoding='utf-8')) if os.path.exists(rec_path) else {}
    sky_root = os.path.join(OUT, '_sky')
    for recipe, vname in views:
        t0 = time.time()
        key = f'{recipe}_{vname}'
        try:
            v = next(x for x in plan[recipe]['views'] if x['name'] == vname)
            sc = RR.new_scene((W, H), a['samples'], TEX_EXPOSURE)
            bpy.context.preferences.system.anisotropic_filter = 'FILTER_16'
            size = refs.load(REF[recipe]).extent
            params = PARAMS.get(recipe)
            c0 = recipe_centre(recipe, params)
            focus = [(c0[0] + v['cam'][0], c0[1] + v['cam'][1])] if v['focus'] else None
            t = A.make_terrain(recipe, size=size, seed=1, params=params, quality='film',
                               palette=None if a['clay'] else 'auto', dress=a['rocks'], focus=focus,
                               name=f'{recipe}_plants')
            tb = time.time() - t0
            cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
            ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
            kind, dz = v['cam_z']
            ground = float(t.height_at(ex, ey))
            ez = ground + float(dz) if kind == 'ground' else float(dz)
            tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
            cam = bpy.data.objects.new('plants_cam', bpy.data.cameras.new('plants_cam'))
            sc.collection.objects.link(cam)
            sc.camera = cam
            dist = math.dist((ex, ey, ez), (tx, ty, tz))
            if kind == 'ground':
                cam.data.clip_start, cam.data.clip_end = 0.1, 4.0 * t.main.side + 40000.0
            else:
                cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), 30.0 * dist
            frame = v['frame'] if a['frame_y'] is None else (v['frame'][0], a['frame_y'])
            heading, pitch = aim_camera(cam, (ex, ey, ez), (tx, ty, tz), frame, v['lens'])
            r = dict(camera=[round(ex, 1), round(ey, 1), round(ez, 1)], aim=[round(tx, 1), round(ty, 1), round(tz, 1)],
                     heading_deg=round(heading, 1), pitch_deg=round(pitch, 2), lens=v['lens'], focus=focus,
                     levels=[str(lv) for lv in t.levels], cache_hit=t.info.get('cache_hit'), build_s=round(tb, 1),
                     clay=a['clay'], caption=v['caption'], photo=v.get('photo'), memory_gb={})
            rec[key + tag] = r

            def stage(name):                             # the process's memory after each stage, kept on disk so a
                r['memory_gb'][name] = memory_gb()       # run that dies still says where its memory went
                save_record(rec_path, key + tag, r)
            stage('terrain')
            if a['plants']:
                data = None
                if a['surface']:
                    from eidoblend.terrain.surface import bake_surface
                    ts = time.time()
                    data = bake_surface(t, palette='auto')
                    r['surface_s'] = round(time.time() - ts, 1)
                tp = time.time()
                spots = PL.plan_plants(t, 'auto', focus=(ex, ey), seed=a['seed'], data=data)
                r['plan_s'] = round(time.time() - tp, 2)
                if data is not None:
                    tc = time.time()
                    extra = spots.cover_extra()
                    data.add_maps(extra)
                    r['cover_s'] = round(time.time() - tc, 1)
                    r['cover_means'] = {k: [round(float(v.mean()), 4) for v in per] for k, per in extra.items()}
                    r['surface_maps'] = data.names()
                r['ecotope'] = spots.meta['ecotope']
                r['species'] = {n: dict(count=spots.count(n), per_ha_home=spots.stats[n].get('per_ha_home'),
                                        range_per_ha=spots.entry(n)['rule'].get('range_per_ha'))
                                for n in spots.names()}
                r['notes'] = list(spots.notes)
                stage('plan')
                ti = time.time()
                made = PI.instance_plants(spots, t)
                r['instance_s'] = round(time.time() - ti, 1)
                r['objects'] = {n: [o.name for o in obs] for n, obs in made.items()}
                r['lod'] = {n: [json.loads(o['eido_plants']) for o in obs[:1]] for n, obs in made.items() if obs}
                bpy.context.view_layer.update()
                stage('instances')
            sky_and_sun(sc, cam, os.path.join(sky_root, key))
            if a['plants']:
                r['sun'] = getattr(PI.bind_sun(), 'name', None)
            stage('sky')
            path = os.path.join(OUT, key + tag + '.png')
            first, second = frame_seconds(sc, path, a['once'])
            r.update(first_render_s=round(first, 1), second_render_s=None if second is None else round(second, 2),
                     total_s=round(time.time() - t0, 1), image=os.path.relpath(path, TN).replace(os.sep, '/'),
                     statistics=sc.statistics(bpy.context.view_layer))
            stage('frames')
            if a['cost'] and a['plants']:
                r['frame_costs_s'] = frame_costs(sc, made)
                print(f"[render_plants] {key}{tag}: frame costs {r['frame_costs_s']}", flush=True)
            rec[key + tag] = r
            print(f"[render_plants] {key}{tag}: build {tb:.0f} s, plan {r.get('plan_s')} s, instance "
                  f"{r.get('instance_s')} s, first frame {first:.1f} s"
                  + ('' if second is None else f', second {second:.2f} s'), flush=True)
            del t
        except Exception as e:                                   # noqa: BLE001 - recorded, the run goes on
            traceback.print_exc()
            rec[key + tag] = dict(error=f'{type(e).__name__}: {e}')
        gc.collect()
        save_record(rec_path, key + tag, rec[key + tag])
    shutil.rmtree(sky_root, ignore_errors=True)
    print('[render_plants] done', flush=True)
    os._exit(0)


main()
