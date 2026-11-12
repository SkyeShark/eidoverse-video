"""One recipe's review videos, in Blender (review_videos.py runs it through the GPU slot, one recipe per process):

    bash run_blender.sh blender/tests/terrain/integration/video_job.py --recipe canyon \\
         --reference grand_canyon_toroweap --field <judge's recipe_seed1.npz> --judge <blender_job_result.json> \\
         --out <dir> [--seed 1] [--spec <json: params, eye, flatten>] [--no-clay] [--no-textured]

1. the clay videos of the main level and its surround (judge/video.py's render_videos: the reference rig's grey
   clay, make_sky daylight): an 8 s aerial orbit and a 6 s dolly at 1.7 m from the eye spot matched to the place's
   kind of view (the judge's spot when --judge gives it); without --field the recipe is generated here;
2. the textured dolly: make_terrain with its focus on that walk (the hero levels down to 0.5 m, the recipe's
   palette, rocks near the focus), the same walk 1.7 m over its own triangles, the same sky and sun.
960 x 540, 16 samples, 24 fps, H.264 High yuv420p (video only: review_videos.py adds the AAC track and checks
each file). Writes <out>/<recipe>_orbit.mp4, _dolly.mp4, _dolly_textured.mp4 and <recipe>_video_job.json.
"""
import argparse
import json
import math
import os
import shutil
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)
sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))

import numpy as np  # noqa: E402

from judge import refs, video  # noqa: E402
from judge.refs import REFERENCE_DIR  # noqa: E402

FPS = 24
DOLLY_S = 6.0
TEX_EXPOSURE = -0.5         # the textured views' exposure, as the surfacing package and the judge's textured row


def args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--recipe', required=True)
    ap.add_argument('--reference', required=True, help='the place (or, for the meadow, the rig) the views match')
    ap.add_argument('--field')
    ap.add_argument('--judge', help="the judge's blender_job_result.json: its eye spot")
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--spec', help='a JSON file of any of: params (the knobs), eye (x, y, look_x, look_y, look_dz, '
                                   'lens_mm in the main tile\'s local metres), flatten')
    ap.add_argument('--samples', type=int, default=16)
    ap.add_argument('--no-clay', action='store_true')
    ap.add_argument('--no-textured', action='store_true')
    return ap.parse_args(argv)


def field_from_generate(a, ref, params, flatten):
    from eidoblend.terrain import api as A
    t = A.generate(a.recipe, size=None if a.recipe == 'meadow' else ref.extent, seed=a.seed, params=params or None,
                   flatten=flatten, quality='film')
    h = np.asarray(t.fields('main')['h'], np.float64)
    ctx = [lv for lv in t.levels if lv.role == 'context']
    c = max(ctx, key=lambda v: v.side) if ctx else None
    return h, float(t.main.cell), ((np.asarray(t.fields(c.index)['h'], np.float64), float(c.cell)) if c else None)


def textured_dolly(a, ref, params, flatten, eye, out_dir, cache_root, log):
    """make_terrain focused on the walk, in its palette with rocks; the dolly 1.7 m over its own triangles."""
    import bpy
    from eidoblend.terrain import api as A
    if REFERENCE_DIR not in sys.path:
        sys.path.insert(0, REFERENCE_DIR)
    import render_references as RR
    sc = RR.new_scene(video.RES, a.samples, TEX_EXPOSURE)
    # the walk is given in the main tile's local metres: its centre is the recipe's (the focus never moves it)
    R = A._registry.resolve(a.recipe)
    values, _ = R.resolve(params or None)
    dfl = dict(R.defaults)
    if getattr(R, 'defaults_for', None) is not None:
        dfl.update(R.defaults_for(values))
    c0 = tuple(float(v) for v in dfl.get('centre', (0.0, 0.0)))
    ex0, ey0 = eye['x'] + c0[0], eye['y'] + c0[1]
    dist = math.hypot(eye['look_x'] - eye['x'], eye['look_y'] - eye['y'])
    walk = min(max(0.1 * dist, 10.0), 150.0)
    ux, uy = (eye['look_x'] - eye['x']) / dist, (eye['look_y'] - eye['y']) / dist
    t0 = time.time()
    t = A.make_terrain(a.recipe, size=None if a.recipe == 'meadow' else ref.extent, seed=a.seed,
                       params=params or None, flatten=flatten, quality='film', palette='auto', dress=True,
                       focus=[(ex0, ey0), (ex0 + ux * walk, ey0 + uy * walk)], name=f'{a.recipe}_terrain')
    built_s = time.time() - t0
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0      # exact
    ex, ey = eye['x'] + cx, eye['y'] + cy
    lx, ly = eye['look_x'] + cx, eye['look_y'] + cy
    n = int(round(DOLLY_S * FPS))
    cam = bpy.data.objects.new('dolly_cam', bpy.data.cameras.new('dolly_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = eye.get('lens_mm', 35.0)
    cam.data.clip_start, cam.data.clip_end = 0.1, 10.0 * t.main.side          # the judge's eye view's clip
    tz = float(t.height_at(lx, ly)) + eye.get('look_dz', 0.0)
    from mathutils import Vector
    for f in range(1, n + 1):
        s = walk * (f - 1) / max(n - 1, 1)
        px, py = ex + ux * s, ey + uy * s
        RR.place_camera(cam, (px, py, float(t.height_at(px, py)) + RR.EYE_HEIGHT), (lx, ly, tz))
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_euler', frame=f)
    d = Vector((lx - ex, ly - ey, 0.0))
    hd = math.atan2(d.y, d.x) + math.radians(RR.SUN_LEFT_DEG)
    name = f'{a.recipe}_dolly_textured'
    r = video._render(sc, cam, (math.cos(hd), math.sin(hd)), RR, os.path.join(cache_root, name),
                      os.path.join(out_dir, f'_{name}_frames'), n, FPS, os.path.join(out_dir, name + '.mp4'), log)
    shutil.rmtree(os.path.join(out_dir, f'_{name}_frames'), ignore_errors=True)
    r.update(build_s=round(built_s, 1), walk_m=round(walk, 1), levels=[str(lv) for lv in t.levels],
             triangles=t.ring.triangle_count, rocks=(t.rocks or {}).get('count') if isinstance(t.rocks, dict) else None,
             eye_world=[ex, ey], look_world=[lx, ly])
    return r


def main():
    a = args()
    log = lambda *x, **k: print(*x, flush=True)               # noqa: E731
    os.makedirs(a.out, exist_ok=True)
    cache_root = os.path.join(a.out, '_sky_cache', a.recipe)
    ref = refs.load(a.reference)
    spec = json.load(open(a.spec, encoding='utf-8')) if a.spec else {}
    params = spec.get('params') or {}
    flatten = spec.get('flatten')
    res = dict(recipe=a.recipe, reference=a.reference, seed=a.seed, errors={})
    t0 = time.time()
    if a.field:
        d = np.load(a.field)
        h, cell = np.asarray(d['h'], np.float64), float(d['cell'])
        ctx = (np.asarray(d['context_h'], np.float64), float(d['context_cell'])) if 'context_h' in d.files else None
    else:
        h, cell, ctx = field_from_generate(a, ref, params, flatten)
    eye = spec.get('eye')
    if eye is None and a.judge and os.path.exists(a.judge):
        j = json.load(open(a.judge, encoding='utf-8'))
        rec = next(iter(j.values()), {})
        eye = rec.get('eye')
    if eye is None:
        from judge import views
        eye = views.eye_spot(h, cell, ref)
    res['eye'] = eye
    if not a.no_clay:
        try:
            res['clay'] = video.render_videos(a.recipe, h, cell, ref, a.out, cache_root, context=ctx, eye=dict(eye),
                                              samples=a.samples, log=log)
        except Exception as e:                                         # noqa: BLE001 - recorded, the job goes on
            traceback.print_exc()
            res['errors']['clay'] = f'{type(e).__name__}: {e}'
    if not a.no_textured:
        try:
            res['textured'] = textured_dolly(a, ref, params, flatten, eye, a.out, cache_root, log)
        except Exception as e:                                         # noqa: BLE001
            traceback.print_exc()
            res['errors']['textured'] = f'{type(e).__name__}: {e}'
    shutil.rmtree(os.path.join(a.out, '_sky_cache', a.recipe), ignore_errors=True)
    res['seconds'] = round(time.time() - t0, 1)
    with open(os.path.join(a.out, f'{a.recipe}_video_job.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))
    print(f"[video_job] {a.recipe}: {'ok' if not res['errors'] else res['errors']} in {res['seconds']:.0f} s",
          flush=True)


main()
