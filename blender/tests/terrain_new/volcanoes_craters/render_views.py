"""Render package 9's analytic shapes through the reference rig, like for like with the references (Blender 5.2).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain_new/volcanoes_craters/render_views.py \\
        [--only fuji,lake,meteor,sp,sp_real,field] [--views top,aerial,eye] [--dry]

Each shape is evaluated on its reference's tile (volcanic / impact presets, the placeholder base of _common) and
rendered by reference/render_references.render_probe: the same grey clay, make_sky daylight, AgX look and three views
as the references, into out/volcanoes_craters/renders/<name>_{top_hillshade,aerial_45deg,eye_1p7m}.png with
<name>_views.json. The eye view stands where the reference's does: on the open plain at the same spot (Fuji), or on
this shape's own rim crest along the same bearing from the centre (Crater Lake, Meteor Crater), looking at the same
point. The real SP Crater (the triage's Terrain Tiles cache; not yet a reference) is rendered here too, from the
same spot as the analytic cone, as the reference row for the cinder cone. `field` is a cinder field preview with no
reference.
"""
import argparse
import math
import os
import shutil
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _common as C  # noqa: E402

sys.path.insert(0, C.REFERENCE_DIR)
import landform_refs as R  # noqa: E402
from render_references import reference_inputs, render_probe  # noqa: E402

OUT = os.path.join(C.OUT, 'renders')
NAMES = dict(fuji='mount_fuji', lake='crater_lake', meteor='meteor_crater', sp='sp_crater', field='cinder_field')
# SP Crater's eye: on the plain 2 km south-south-east of the cone, the ground falling gently toward it (the triage's
# spot at (-1600, -1600) faces rising ground 18 m ahead), aimed at the cone 60 m below its crater floor
SP_EYE = dict(x=600.0, y=-1900.0, look_x=0.0, look_y=0.0, look_dz=-60.0, lens_mm=35.0)
FIELD_EYE = dict(x=-2600.0, y=-3000.0, look_x=600.0, look_y=900.0, look_dz=0.0, lens_mm=35.0)


def north_up(a):
    return None if a is None else np.ascontiguousarray(a[::-1])


def crest_eye(g, ref_eye):
    """The reference's eye moved onto this shape's rim crest along the same bearing from the centre: the highest
    point on the ray between 0.5 and 1.6 times the reference eye's distance; the look point unchanged."""
    cx, cy = g['centre']
    dx, dy = ref_eye['x'] - cx, ref_eye['y'] - cy
    dist = math.hypot(dx, dy)
    ex, ey = dx / dist, dy / dist
    s = np.linspace(0.5 * dist, 1.6 * dist, 2000)
    meta = dict(rows=g['h'].shape[0], cols=g['h'].shape[1], pixel_size_m=g['pixel_m'])
    z = R.sample(north_up(g['h']), meta, cx + s * ex, cy + s * ey)
    k = int(np.argmax(z))
    eye = dict(ref_eye)
    eye.update(x=float(cx + s[k] * ex), y=float(cy + s[k] * ey))
    return eye


def render_name(key, views, cache_root, dry):
    t0 = time.time()
    if key == 'sp_real':
        h, p, _X, _Y = C.load_sp_crater()
        recs = render_probe('sp_crater_real', north_up(h), p, OUT, cache_root, views=views, eye=SP_EYE, dry=dry)
        print(f'[volc] sp_crater_real {time.time() - t0:.0f}s', flush=True)
        return recs
    name = NAMES[key]
    g = C.generated(name)
    water = None
    if g['water'] is not None:
        water = (north_up(g['water'][0]), g['water'][1])
    context = None
    if name in C.CONTEXTS:
        nc, pc = C.CONTEXTS[name]
        context = (north_up(C.generated(name, supersample=1, n=nc, pixel_m=pc)['h']), pc)
    if name == 'mount_fuji':
        eye = reference_inputs(name)[4]
    elif name in ('crater_lake', 'meteor_crater'):
        eye = crest_eye(g, reference_inputs(name)[4])
    elif name == 'sp_crater':
        eye = SP_EYE
    else:
        eye = FIELD_EYE
    recs = render_probe('gen_' + name, north_up(g['h']), g['pixel_m'], OUT, cache_root, views=views, water=water,
                        context=context, eye=eye, dry=dry)
    print(f'[volc] gen_{name} eye at ({eye["x"]:.0f}, {eye["y"]:.0f}) {time.time() - t0:.0f}s', flush=True)
    return recs


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='fuji,lake,meteor,sp_real,sp,field')
    ap.add_argument('--views', default='top,aerial,eye')
    ap.add_argument('--sky-cache', default=None)
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    cache_root = a.sky_cache or tempfile.mkdtemp(prefix='volc_sky_')
    os.makedirs(cache_root, exist_ok=True)
    for key in [k for k in a.only.split(',') if k]:
        render_name(key, a.views.split(','), cache_root, a.dry)
        for d in os.listdir(cache_root):
            shutil.rmtree(os.path.join(cache_root, d), ignore_errors=True)
    print('[volc] done', flush=True)


if __name__ == '__main__':
    main()
