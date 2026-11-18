"""The material's checks 6 and 7 (SURFACING_DESIGN.md 5.4, package 2): the hand-off to the far colour, and views that
stand on context rings.

    bash run_blender.sh blender/tests/terrain/surfacing/check_far.py [--case canyon]
        [--views aerial_down_canyon,low_oblique] [--old]
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

Per view, under make_sky, the per-texel material three times with only its hand-off distance moved
(surfacing.set_far_distance: a node value, nothing recompiles): as built (D0), near only (D0 beyond everything: the
layers to the horizon) and far only (D0 at 1 cm: the baked far colour C wherever the hand-off allows it, which is
never inside the hero windows). The same pixels drawn by the near material and by C are the hand-off's two sides,
so their difference is what a ring would show:
  - over the ground the far colour may draw (more than 64 main cells outside the outermost hero window): the CIELAB
    difference of the two renders' mean colours, and per pixel its median and 90th percentile;
  - the same over the pixels whose view distance lies in the band D0..1.5 D0, where the hand-off happens as built;
  - the share of the frame the far colour takes as built.
Then the view once more with its camera passed to apply_surface, so the rings beyond 1.5 D0 of it take the far
material (slot 1: C, the macro normal, no layers; a cost saving only): against the near material as built, the
CIELAB difference of the mean colours over those rings' pixels, what the far material's ring boundary would show.
The region comes from an emission render of the level reader's Hero Outside and the view distance. --old adds
today's material (mesh attributes) on the same views, for the eye. --motion: each view also as a 24-frame sequence
in motion through the hand-off as built (an aerial view panned 20 degrees about the vertical through the camera, an
eye view dollied forward by a tenth of D0), encoded to H.264 (ffmpeg on the PATH), to watch for a ring. Writes
out/surfacing/material/far/<case>_<view>_<as_built|near|far|rings|old>.png, a 4x difference image, the motion
frames and videos (far/motion_<case>_<view>/, far/motion_<case>_<view>.mp4) and far_<case>.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _material_scene as MS  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

OUT = os.path.join(MS.OUT, 'far')


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(case=opt('--case', 'canyon'), views=opt('--views', 'aerial_down_canyon,low_oblique').split(','),
                old='--old' in a, motion='--motion' in a)


def motion(sc, t, cam, case, v, d0, frames=24):
    """The view in motion through the hand-off, as built (module doc): frames and an H.264 video; its record."""
    import math
    import shutil
    import subprocess
    from mathutils import Matrix
    folder = os.path.join(OUT, f'motion_{case}_{v}')
    os.makedirs(folder, exist_ok=True)
    bpy.context.view_layer.update()
    m0 = cam.matrix_world.copy()
    loc = m0.translation.copy()
    aerial = loc.z - float(t.height_at(loc.x, loc.y)) > 50.0
    fwd = -m0.col[2].xyz
    fwd.z = 0.0
    fwd = fwd.normalized() if fwd.length > 1e-6 else fwd
    for k in range(frames):
        s = k / max(frames - 1, 1)
        if aerial:
            mw = Matrix.Translation(loc) @ Matrix.Rotation(math.radians(-10.0 + 20.0 * s), 4, 'Z') \
                @ Matrix.Translation(-loc) @ m0
        else:
            p = loc + fwd * (0.1 * d0 * s)
            p.z = float(t.height_at(p.x, p.y)) + (loc.z - float(t.height_at(loc.x, loc.y)))
            mw = m0.copy()
            mw.translation = p
        cam.matrix_world = mw
        MS.frame(sc, os.path.join(folder, f'f_{k:03d}.png'))
    cam.matrix_world = m0
    rec = dict(frames=frames, kind='pan 20 degrees' if aerial else f'dolly {0.1 * d0:.0f} m',
               folder=os.path.relpath(folder, MS.OUT))
    exe = shutil.which('ffmpeg')
    if exe:
        mp4 = os.path.join(OUT, f'motion_{case}_{v}.mp4')
        cmd = [exe, '-y', '-loglevel', 'error', '-framerate', '12', '-i', os.path.join(folder, 'f_%03d.png'),
               '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', '16', mp4]
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000 if os.name == 'nt' else 0)
        rec['video'] = os.path.relpath(mp4, MS.OUT) if r.returncode == 0 else f'ffmpeg failed: {r.stderr[:200]}'
    return rec


def srgb_to_lab(rgb):
    """CIELAB (D65) of display sRGB values 0..1, (..., 3)."""
    c = np.asarray(rgb, np.float64)
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216.0 / 24389.0, np.cbrt(xyz), (24389.0 / 27.0 * xyz + 16.0) / 116.0)
    return np.stack([116.0 * f[..., 1] - 16.0, 500.0 * (f[..., 0] - f[..., 1]), 200.0 * (f[..., 1] - f[..., 2])], -1)


def compare(near, far, sel):
    if int(sel.sum()) < 50:
        return dict(pixels=int(sel.sum()))
    la, lb = srgb_to_lab(near[sel]), srgb_to_lab(far[sel])
    de = np.linalg.norm(la - lb, axis=-1)
    return dict(pixels=int(sel.sum()), mean_colour_dE=round(float(np.linalg.norm(la.mean(0) - lb.mean(0))), 2),
                pixel_dE_median=round(float(np.median(de)), 2), pixel_dE_p90=round(float(np.percentile(de, 90)), 2),
                near_mean_lab=[round(float(v), 1) for v in la.mean(0)],
                far_mean_lab=[round(float(v), 1) for v in lb.mean(0)])


def main():
    a = args()
    case = a['case']
    os.makedirs(OUT, exist_ok=True)
    sc = MS.scene(samples=16)
    t, obj = MS.terrain(case)
    sd = MS.surface(t)
    me = obj.data
    cams = {v: MS.camera(sc, t, case, v) for v in a['views']}
    mat = MS.apply(t, obj, sd)
    d0 = float(mat['eido_far_m'])
    cm = S._main_cell(sd)
    region = MS.region_material(sd)
    rec = dict(case=case, far_m=d0, main_cell=cm, views={})
    sky = os.path.join(OUT, '_sky')
    for v, cam in cams.items():
        sc.camera = cam
        if len(me.materials) > 1 or me.materials[0] is not mat:
            mat = MS.apply(t, obj, sd)                     # the near material alone again (the last view's rings)
        MS.light(sc, cam, sky)
        MS.frame(sc)
        imgs = {}
        for label, dist in (('as_built', d0), ('near', 1.0e7), ('far', 0.01)):
            S.set_far_distance(mat, dist)
            path = os.path.join(OUT, f'{case}_{v}_{label}.png')
            secs = MS.frame(sc, path)
            imgs[label] = MS.read_png(path)
            MS.log(f'[far] {case} {v} {label}: {secs:.2f} s')
        S.set_far_distance(mat, d0)
        if a['motion']:
            rmo = motion(sc, t, cam, case, v, d0)
            MS.log(f'[far] {case} {v} motion: {json.dumps(rmo)}')
        outside, dist, ground = MS.region_render(sc, me, region, os.path.join(OUT, f'{case}_{v}_region.exr'))
        allowed = ground & (outside > S.FAR_FADE_MAIN_CELLS * cm)
        band = allowed & (dist > d0) & (dist < 1.5 * d0)
        beyond = allowed & (dist >= 1.5 * d0)
        r = dict(ground_px=int(ground.sum()), far_allowed_share=round(float(allowed.sum() / max(ground.sum(), 1)), 3),
                 far_as_built_share=round(float(beyond.sum() / max(ground.sum(), 1)), 3),
                 where_far_may_draw=compare(imgs['near'], imgs['far'], allowed),
                 in_the_band=compare(imgs['near'], imgs['far'], band),
                 beyond_the_band=compare(imgs['near'], imgs['far'], beyond),
                 view_distance_m=[round(float(dist[ground].min()), 0), round(float(dist[ground].max()), 0)])
        diff = np.clip(np.abs(imgs['near'] - imgs['far']) * 4.0, 0.0, 1.0)
        dimg = bpy.data.images.new('far_diff', diff.shape[1], diff.shape[0], alpha=False)
        dimg.pixels.foreach_set(np.concatenate([diff[::-1], np.ones(diff.shape[:2] + (1,), np.float32)], -1)
                                .astype(np.float32).ravel())
        dimg.filepath_raw = os.path.join(OUT, f'{case}_{v}_near_minus_far_x4.png')
        dimg.file_format = 'PNG'
        dimg.save()
        bpy.data.images.remove(dimg)
        # the far material on the rings beyond 1.5 D0 of this camera, against the near material as built there
        MS.apply(t, obj, sd, cameras=[cam])
        far_px = np.zeros(ground.shape, bool)
        if len(me.materials) > 1:
            MS.frame(sc)
            path = os.path.join(OUT, f'{case}_{v}_rings.png')
            MS.frame(sc, path)
            rings = MS.read_png(path)
            far_px = ground & (np.abs(rings - imgs['as_built']).max(-1) > 0.0)
            # the far material's own pixels: those its ring draws (where the two renders differ at all, or the
            # rings' region by distance: beyond 1.5 D0 every pixel the far material can draw)
            sel = ground & (dist >= 1.5 * d0) & allowed
            r['far_material'] = dict(rings=S.far_rings(obj, sd, [cam], far_m=d0),
                                     differing_px=int(far_px.sum()),
                                     **compare(imgs['as_built'], rings, sel))
        else:
            r['far_material'] = 'no ring lies beyond 1.5 D0 of this camera'
        if a['motion']:
            r['motion'] = rmo
        rec['views'][v] = r
        MS.log(f'[far] {case} {v}: {json.dumps(r)}')
        MS.clean(sky)
    if a['old']:
        MS.apply(t, obj, None)
        for v, cam in cams.items():
            sc.camera = cam
            MS.light(sc, cam, sky)
            MS.frame(sc)
            secs = MS.frame(sc, os.path.join(OUT, f'{case}_{v}_old.png'))
            MS.log(f'[far] {case} {v} old: {secs:.2f} s')
            MS.clean(sky)
    path = os.path.join(MS.OUT, f'far_{case}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    MS.log(f'[far] done -> {path}')


try:
    main()
except Exception:                                           # noqa: BLE001
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)
sys.stdout.flush()
os._exit(0)
