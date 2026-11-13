"""Photo-matched views of the layered-rock landforms (Blender, through a GPU slot): the real DEM from each reference
photograph's own camera, and a generated terrain from the camera that stands in the same relation to its landform
(views_match.py), both under the reference rig's make_sky daylight (Earth 15:30, cumulus, AgX Medium High Contrast,
the sun 70 degrees left of the view), 960 x 540, 16 samples, textured (the palette and rocks near the camera) and in
the references' grey clay. compose_sheets.py sets them beside the photographs.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/terrain/layered_rock/render_views.py --real grand_canyon_toroweap [--fan]
    ... render_views.py --recipe canyon --seed 1 --tag v1 [--params '{...}'] [--stage-params '{op: {...}}']
                        [--views overlook,west_side] [--no-clay] [--no-textured]

--real <reference>   the real DEM (the real_place recipe) from the photos' cameras: <reference>_<view>.png (textured)
                     and _clay.png; with --fan, clay renders from every photo position at the FAN headings, to fit
                     each photo's heading, pitch and lens (fan_<photo>_<heading>.png)
--recipe <name>      generated at the reference's extent (the stage overrides merged into the recipe dict), the
                     cameras matched, then built with the hero levels around them: <reference>_<tag>_<view>.png
                     and _clay.png
Writes blender/tests/terrain/out/layered_rock/views/ and <reference>_<tag>_views.json (--real: <reference>_views.json;
cameras, relations, timings). (Keyed by the tag alone, the Badlands' v1 cameras overwrote Monument Valley's and its
sheet showed Badlands photographs and renders.)
"""
import json
import math
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, TN)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import landform_refs as LR  # noqa: E402
import render_references as RR  # noqa: E402
import views_match as VM  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain import recipes as RG  # noqa: E402
from judge import refs  # noqa: E402

OUT = os.path.normpath(os.path.join(TN, 'out', 'layered_rock', 'views'))

# Each photograph's camera on its reference DEM: the GPS position (sources.json), the heading, pitch and lens fitted
# by eye against the fan renders (--fan), and how the generated terrain's camera is matched (views_match kinds).
# edge: slide forward from the GPS point to the brink before rendering (a GPS fix a few tens of metres back from a
# rim sees nothing of the gorge below).
VIEWS = {
    # the canyon views: at the brink beside the gorge (the GPS fix slid to it), looking along the river (upstream or
    # downstream, turned toward_deg toward it) or across it at a loop, the view axis coming down within
    # hit_river_m of the river: the same rule on the real DEM and on the generated terrain, so the two compare
    'grand_canyon_toroweap': [
        dict(name='overlook_up', photo='tw_02', kind='river', at=(36.215306, -113.056386), look='upstream',
             toward_deg=25.0, az=50.0, pitch=-20.0, lens=24.0, edge=True, hit_river_m=250.0),
        dict(name='overlook_down', photo='tw_03', kind='river', at=(36.215306, -113.056386), look='downstream',
             toward_deg=20.0, az=225.0, pitch=-16.0, lens=24.0, edge=True, hit_river_m=300.0),
        dict(name='west_side', photo='tw_07', kind='river', at=(36.213722, -113.058049), look='downstream',
             toward_deg=15.0, az=235.0, pitch=-20.0, lens=24.0, edge=True, hit_river_m=250.0),
    ],
    'goosenecks': [
        dict(name='overlook', photo='gn_01', kind='river', at=(37.174205, -109.92751), look='across', toward_deg=0.0,
             az=240.0, pitch=-24.0, lens=24.0, edge=True, hit_river_m=200.0),
        dict(name='overlook_2', photo='gn_02', kind='river', at=(37.174722, -109.926944), look='across',
             toward_deg=10.0, az=250.0, pitch=-22.0, lens=24.0, edge=True, hit_river_m=200.0),
    ],
    'monument_valley': [
        dict(name='lookout', photo='mv_01', kind='target', at=(36.982667, -110.111667), az=76.0, pitch=-1.5,
             lens=35.0, target_xy=(309.0, 803.0)),
        dict(name='west_mitten', photo='mv_02', kind='target', at=(36.985427, -110.111482), az=72.0, pitch=2.0,
             lens=45.0, target_xy=(309.0, 803.0)),
    ],
    'badlands_sd': [
        dict(name='door_trail', photo='bl_01', kind='target', at=(43.759842, -101.927572), az=200.0, pitch=4.0,
             lens=28.0, target_xy=None),
        dict(name='wall', photo='bl_06', kind='target', at=(43.759411, -101.926986), az=200.0, pitch=4.0,
             lens=28.0, target_xy=None),
    ],
}
FAN = {'grand_canyon_toroweap': (range(0, 360, 30), -14.0, 24.0), 'goosenecks': (range(180, 330, 25), -22.0, 24.0),
       'monument_valley': (range(40, 120, 15), 0.0, 35.0), 'badlands_sd': (range(0, 360, 30), 4.0, 28.0)}
RECIPE_REF = {'canyon': 'grand_canyon_toroweap', 'incised_meanders': 'goosenecks', 'mesas_buttes': 'monument_valley',
              'badlands': 'badlands_sd'}
# the real DEMs' palette where build/palettes.PLACES has no entry ('auto' then gave the Goosenecks the alpine one)
REAL_PALETTE = {'goosenecks': 'desert_sandstone'}


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(real=opt('--real'), recipe=opt('--recipe'), fan='--fan' in a, seed=int(opt('--seed', '1')),
                params=json.loads(opt('--params', '{}')), stage_params=json.loads(opt('--stage-params', '{}')),
                tag=opt('--tag', 'v'), views=[v for v in (opt('--views', '') or '').split(',') if v],
                clay='--no-clay' not in a, textured='--no-textured' not in a, quality=opt('--quality', 'film'))


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = RR.new_scene((960, 540), 16, RR.EXPOSURE)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start, cam.data.clip_end = 0.05, 120000.0
    return sc, cam


def render(sc, cam, name, sky_root, rec):
    from mathutils import Vector
    d = Vector(cam.matrix_world.col[2][:3]) * -1.0
    hd = math.atan2(d.y, d.x) + math.radians(RR.SUN_LEFT_DEG)
    cache = os.path.join(sky_root, name)
    os.makedirs(cache, exist_ok=True)
    t0 = time.time()
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    shutil.rmtree(cache, ignore_errors=True)
    rec[name] = dict(camera=[round(v, 2) for v in cam.location], lens_mm=cam.data.lens,
                     seconds=round(time.time() - t0, 1))
    print(f'[layered.views] {name}.png {rec[name]["seconds"]} s', flush=True)


def aim(cam, x, y, z, az, pitch, lens):
    a = math.radians(az)
    c = math.cos(math.radians(pitch))
    tgt = (x + 100.0 * c * math.sin(a), y + 100.0 * c * math.cos(a), z + 100.0 * math.sin(math.radians(pitch)))
    RR.place_camera(cam, (x, y, z), tgt)
    cam.data.lens = lens


def slide_to_edge(height_at, x, y, az, max_m=160.0, drop=20.0):
    """Forward from (x, y) along az in 3 m steps while the ground 25 m ahead is no more than `drop` below here."""
    a = math.radians(az)
    ux, uy = math.sin(a), math.cos(a)
    for s in np.arange(0.0, max_m, 3.0):
        px, py = x + s * ux, y + s * uy
        z = float(height_at(px, py))
        ahead = min(float(height_at(px + k * ux, py + k * uy)) for k in (10.0, 18.0, 25.0))
        if ahead < z - drop:
            return px, py
    return x, y


def _clear(height_at, x, y, z, az, pitch, dist=60.0):
    """The view axis stays above the ground for its first `dist` metres."""
    a = math.radians(az)
    for s in np.linspace(2.0, dist, 30):
        if z + s * math.tan(math.radians(pitch)) < float(height_at(x + s * math.sin(a), y + s * math.cos(a))):
            return False
    return True


def ahead_point(x, y, az, d=120.0):
    a = math.radians(az)
    return (x + d * math.sin(a), y + d * math.cos(a))


def dem_cams(ref, views):
    """Each view's camera on the reference DEM: the GPS position, and for the canyon views (look=...) the brink
    beside the river and the heading along it (views_match.relation's rule, the one the generated terrain gets)."""
    out = []
    half = ref.extent / 2.0
    for v in views:
        x, y = LR.latlon_to_xy(ref.meta, *v['at'])
        c = dict(v, x=float(x), y=float(y))
        if v.get('kind') == 'river' and v.get('look'):
            rel = VM.relation(ref.h, ref.pixel, -half, -half, dict(x=c['x'], y=c['y'], az=v['az'], pitch=v['pitch'],
                                                                   lens=v['lens']), v)
            c.update(x=rel['x'], y=rel['y'], az=rel['az'], edge=False)
        out.append(c)
    return out


def real(a, rec):
    name = a['real']
    ref = refs.load(name)
    views = [v for v in VIEWS[name] if not a['views'] or v['name'] in a['views']]
    cams = dem_cams(ref, views)
    focus = [(c['x'], c['y']) for c in cams] + [ahead_point(c['x'], c['y'], c['az']) for c in cams]
    sky_root = tempfile.mkdtemp(prefix='layered_sky_')
    jobs = [(None, '_clay', a['clay'] or a['fan']), (REAL_PALETTE.get(name, 'auto'), '', a['textured'] and not a['fan'])]
    for palette, suffix, on in jobs:
        if not on:
            continue
        sc, cam = scene()
        t0 = time.time()
        t = A.make_terrain('real_place', params={'dem': name}, focus=focus, palette=palette,
                           dress=palette is not None, name='terrain')
        rec['make_terrain' + suffix] = dict(seconds=round(time.time() - t0, 1), levels=[str(lv) for lv in t.levels])
        if a['fan']:
            heads, pitch, lens = FAN[name]
            seen = set()
            for c in cams:
                key = (round(c['x']), round(c['y']))
                if key in seen:
                    continue
                seen.add(key)
                for az in heads:
                    x, y = (slide_to_edge(t.height_at, c['x'], c['y'], az) if c.get('edge') else (c['x'], c['y']))
                    z = float(t.height_at(x, y)) + VM.EYE
                    aim(cam, x, y, z, az, pitch, lens)
                    render(sc, cam, f"fan_{c['photo']}_{az:03d}", sky_root, rec)
            continue
        for c in cams:
            x, y = (slide_to_edge(t.height_at, c['x'], c['y'], c['az']) if c.get('edge') else (c['x'], c['y']))
            z = float(t.height_at(x, y)) + VM.EYE
            raised = 0.0
            if c.get('kind') == 'river':
                # the DEM rounds a rim into a shoulder the photographer's brink is not: raise the camera until its
                # view axis clears the shoulder (recorded; 30 m at most)
                for dz in (0.0, 3.0, 6.0, 10.0, 15.0, 20.0, 30.0):
                    if _clear(t.height_at, x, y, z + dz, c['az'], c['pitch']):
                        raised = dz
                        break
                z += raised
            aim(cam, x, y, z, c['az'], c['pitch'], c['lens'])
            rec.setdefault('cameras', {})[c['name']] = dict(x=x, y=y, z=z, az=c['az'], pitch=c['pitch'],
                                                            lens=c['lens'], photo=c['photo'], raised_m=raised)
            render(sc, cam, f"{name}_{c['name']}{suffix}", sky_root, rec)
    shutil.rmtree(sky_root, ignore_errors=True)


def recipe_dict(a):
    R = RG.get(a['recipe'])
    d = R.to_dict()
    for st in d['stages']:
        extra = a['stage_params'].get(st['op']) or a['stage_params'].get(st.get('name') or '')
        if extra:
            st['params'].update(extra)
    return d


def targets_for(kind, h, cell, x0, y0, rel):
    """The generated terrain's candidate targets: buttes for Monument Valley's views, high points of the wall for
    the Badlands' (x, y, relief above the floor), most like the photo's first."""
    if kind == 'mesas_buttes':
        bs = VM.buttes(h, cell, x0, y0, min_rel=max(60.0, 0.4 * rel['target_top']))
        bs = sorted(bs, key=lambda b: abs((b[3] - b[4]) - rel['target_top']))
        return [(b[1], b[2], b[3] - b[4]) for b in bs[:8]]
    # badlands: the highest ground of 60 m blocks, at least 20 m above the floor
    n = h.shape[0]
    b = max(4, int(60.0 / cell))
    out = []
    fl = np.percentile(h, 10)
    for j in range(0, n - b, b):
        for i in range(0, n - b, b):
            w = h[j:j + b, i:i + b]
            k = int(np.argmax(w))
            jj, ii = divmod(k, b)
            z = float(w[jj, ii])
            if z - fl > 20.0:
                out.append((x0 + (i + ii + 0.5) * cell, y0 + (j + jj + 0.5) * cell, z - fl))
    out.sort(key=lambda t: abs(t[2] - rel['target_top']))
    return out[:40]


def generated(a, rec):
    name = RECIPE_REF[a['recipe']]
    ref = refs.load(name)
    views = [v for v in VIEWS[name] if not a['views'] or v['name'] in a['views']]
    d = recipe_dict(a)
    kw = dict(size=ref.extent, seed=a['seed'], params=a['params'] or None, quality=a['quality'])
    t0 = time.time()
    tg = A.generate(d, **kw)
    lv = tg.main
    h = np.asarray(tg.fields('main')['h'], np.float64)
    rec['generate'] = round(time.time() - t0, 1)
    half = ref.extent / 2.0
    cams = []
    for c in dem_cams(ref, views):
        x, y = c['x'], c['y']
        if c.get('kind') == 'target' and c.get('target_xy') is None:
            # the target is the highest ground within 600 m along the photo's heading
            s = np.linspace(40.0, 600.0, 60)
            px = x + s * math.sin(math.radians(c['az']))
            py = y + s * math.cos(math.radians(c['az']))
            hz = VM.sample(ref.h, ref.pixel, -half, -half, px, py)
            k = int(np.argmax(hz))
            c['target_xy'] = (float(px[k]), float(py[k]))
        cam_dem = dict(x=x, y=y, az=c['az'], pitch=c['pitch'], lens=c['lens'])
        rel = VM.relation(ref.h, ref.pixel, -half, -half, cam_dem, c)
        try:
            if c['kind'] == 'river':
                m = VM.match_river(h, lv.cell, lv.x0, lv.y0, rel)
            else:
                m = VM.match_target(h, lv.cell, lv.x0, lv.y0, rel, targets_for(a['recipe'], h, lv.cell, lv.x0,
                                                                                 lv.y0, rel))
        except ValueError as e:
            print(f"[layered.views] {c['name']}: {e}", flush=True)
            rec.setdefault('unmatched', {})[c['name']] = str(e)
            continue
        cams.append(dict(c, match=m, rel=rel))
        print(f"[layered.views] {c['name']}: relation {json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in rel.items()})} "
              f"-> camera {json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items() if k != 'target'})}",
              flush=True)
    rec['cameras'] = {c['name']: dict(match=c['match'], relation=c['rel'], photo=c['photo']) for c in cams}
    focus = [(c['match']['x'], c['match']['y']) for c in cams] + [ahead_point(c['match']['x'], c['match']['y'],
                                                                               c['match']['az']) for c in cams]
    sky_root = tempfile.mkdtemp(prefix='layered_sky_')
    for palette, suffix, on in (('auto', '', a['textured']), (None, '_clay', a['clay'])):
        if not on or not cams:
            continue
        sc, cam = scene()
        t1 = time.time()
        t = A.make_terrain(d, focus=focus, palette=palette, dress=palette is not None, name='terrain', **kw)
        rec['make_terrain' + suffix] = dict(seconds=round(time.time() - t1, 1), levels=[str(v) for v in t.levels],
                                            triangles=t.ring.triangle_count)
        for c in cams:
            m = c['match']
            x, y = (slide_to_edge(t.height_at, m['x'], m['y'], m['az']) if c.get('edge') else (m['x'], m['y']))
            z = float(t.height_at(x, y)) + VM.EYE
            aim(cam, x, y, z, m['az'], m['pitch'], m['lens'])
            render(sc, cam, f"{name}_{a['tag']}_{c['name']}{suffix}", sky_root, rec)
    shutil.rmtree(sky_root, ignore_errors=True)


def main():
    a = args()
    os.makedirs(OUT, exist_ok=True)
    rec = dict(args=a)
    t0 = time.time()
    try:
        if a['real']:
            real(a, rec)
        else:
            generated(a, rec)
    except Exception:                                                   # noqa: BLE001 - recorded
        import traceback
        traceback.print_exc()
        rec['error'] = traceback.format_exc()
    rec['seconds'] = round(time.time() - t0, 1)
    rec['reference'] = a['real'] or RECIPE_REF[a['recipe']]
    tag = a['real'] + ('_fan' if a['fan'] else '') if a['real'] else f"{RECIPE_REF[a['recipe']]}_{a['tag']}"
    with open(os.path.join(OUT, f'{tag}_views.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, default=str)
    print('[layered.views] done', rec['seconds'], 's', flush=True)
    os._exit(0)


main()
