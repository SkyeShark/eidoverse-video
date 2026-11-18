"""How the judge builds a shot in Blender, shared by its renderers (surfacing/review_views.py, video.py): a view's
terrain (saved, or generated through the terrain cache), the recipe's palette as the code has it now, the view's
camera, its plants, and make_sky daylight with the sun 70 degrees left of the view. Needs bpy.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
JUDGE_TERRAINS = os.path.join(TN, 'out', 'surfacing_judge', 'terrains')
REFERENCE_DIR = os.path.join(TN, 'reference')
W, H = 960, 540
EXPOSURE = -0.5                             # the textured views' exposure (AgX)
VISTA_STEP_M, VISTA_HALF_M = 5.0, 2.0       # a view's vista_m: no crown within 2 m of its sight line, every 5 m
PARAMS = {'real_place': {'dem': 'lauterbrunnen'}}


def quiet(*_a, **_k):
    pass


def rr():
    """The reference rig (render_references: new_scene, place_camera, the sun's elevation and side)."""
    import sys
    if REFERENCE_DIR not in sys.path:
        sys.path.insert(0, REFERENCE_DIR)
    import render_references as RR
    return RR


def recipe_centre(recipe, params):
    from eidoblend.terrain import api as A
    R = A._registry.resolve(recipe)
    values, _ = R.resolve(params or None)
    dfl = dict(R.defaults)
    if getattr(R, 'defaults_for', None) is not None:
        dfl.update(R.defaults_for(values))
    c = dfl.get('centre', (0.0, 0.0))
    return float(c[0]), float(c[1])


def palette_now(recipe):
    """The recipe's palette from the code as it is now: 'auto' for a real place, else the registry recipe's 'auto'
    palette as a dict (a saved terrain carries its recipe as it was saved, with that day's palette copy)."""
    from eidoblend.terrain import api as A
    from eidoblend.terrain.build import palettes as P
    if recipe == 'real_place':
        return 'auto'
    return P.get('auto', recipe=A._registry.get(recipe))


def _saved_focus(npz):
    try:
        info = json.load(open(os.path.splitext(npz)[0] + '.json', encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return info.get('focus') if isinstance(info, dict) else None


def terrain_source(recipe, name, focus, snap=None):
    """(saved terrain to load or None, where to save a generated one or None): a view without a focus takes the
    judge's saved terrain; one with a focus a terrain saved in `snap` whose focus is that focus."""
    if not focus:
        p = os.path.join(JUDGE_TERRAINS, recipe + '.npz')
        if os.path.exists(p):
            return p, None
    if not snap:
        return None, None
    for suffix in ('', '_j'):
        p = os.path.join(snap, f'{recipe}_{name}{suffix}.npz')
        if not os.path.exists(p):
            continue
        sf = _saved_focus(p)
        if (not focus and not sf) or (focus and sf and len(sf) == len(focus)
                                      and all(math.dist(tuple(a[:2]), tuple(b)) < 1.0 for a, b in zip(sf, focus))):
            return p, None
    return None, os.path.join(snap, f'{recipe}_{name}_j.npz')


def terrain_for(recipe, name, size, params, focus, snap=None):
    """The view's terrain without its object (a saved one, else api.generate through the terrain cache), and where
    it came from."""
    from eidoblend.terrain import api as A
    path, save_to = terrain_source(recipe, name, focus, snap)
    if path:
        t = A.Terrain.load(path, build=False)
        t.info['cache_hit'] = 'snapshot'
        return t, os.path.basename(path)
    t = A.generate(recipe, size=size, seed=1, params=params, focus=focus, quality='film', log=quiet)
    if save_to:
        os.makedirs(os.path.dirname(save_to), exist_ok=True)
        t.save(save_to)
    return t, ('terrain cache hit' if t.info.get('cache_hit') else 'generated')


def aim_camera(cam, eye, target, frame, lens):
    """Point cam from eye so that target lands at frame (0..1 from the left, from the top): the review's rule.
    Returns (heading, pitch) in degrees."""
    RR = rr()
    cam.data.lens = lens
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36.0
    dx, dy, dz = target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]
    yaw_t = math.atan2(dy, dx)
    pitch_t = math.atan2(dz, math.hypot(dx, dy))
    hf, vf = 36.0, 36.0 * H / W
    u = (frame[0] - 0.5) * hf / lens
    v = (0.5 - frame[1]) * vf / lens
    yaw = yaw_t + math.atan(u)
    pitch = pitch_t - math.atan(v)
    d = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
    RR.place_camera(cam, eye, (eye[0] + 1000.0 * d[0], eye[1] + 1000.0 * d[1], eye[2] + 1000.0 * d[2]))
    return (90.0 - math.degrees(yaw)) % 360.0, math.degrees(pitch)


def is_eye(v):
    return v['cam_z'][0] == 'ground' and float(v['cam_z'][1]) <= 10.0


def plant_spec(v, eye, aim, path=None):
    """make_terrain's plants= for a view: around the camera (an eye view; a walk's whole path) or the ground it looks
    at (an aerial), with the view's vista kept clear of crowns."""
    if path is not None:
        spec = dict(focus=[(float(p[0]), float(p[1])) for p in path])
    else:
        spec = dict(focus=(eye[0], eye[1]) if is_eye(v) else (aim[0], aim[1]))
    if v.get('vista_m'):
        n = math.hypot(aim[0] - eye[0], aim[1] - eye[1])
        steps = [VISTA_STEP_M * k for k in range(1, int(float(v['vista_m']) / VISTA_STEP_M) + 1)]
        spec['exclude'] = [(eye[0] + s * (aim[0] - eye[0]) / n, eye[1] + s * (aim[1] - eye[1]) / n, VISTA_HALF_M,
                            'crown') for s in steps]
    return spec


def sun_xy(cam):
    """The sun's direction for a camera: RR.SUN_LEFT_DEG left of its view, as the review lights every view."""
    RR = rr()
    d = cam.matrix_world.col[2][:3]
    hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
    return math.cos(hd), math.sin(hd)
