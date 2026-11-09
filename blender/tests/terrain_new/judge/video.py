"""The review videos (DESIGN.md section 10 item 8; integration renders them into out/videos/): per terrain an 8 s aerial
orbit and a 6 s eye-level dolly, 960 x 540, 16 samples, H.264 High yuv420p, checked with ffprobe. The scene is the
references' rig (grey clay, make_sky daylight at 15:30, the wider surround under the eye view); the sun stays where
it starts (70 degrees left of the first frame's view), so the orbit shows the form under a turning light.

    bash run_blender.sh blender/tests/terrain_new/judge/video.py --reference grand_canyon_toroweap \\
         [--field my.npz] [--out <dir>] [--orbit-deg 360] [--fps 24] [--dolly-m 0]
    (a reference alone renders the reference itself; --field renders that heightfield, its eye spot matched to the
    reference's kind of view)

From Python in Blender: render_videos(name, h, cell, ref, out_dir, cache_root, context=None, eye=None).
encode() and probe() also run in system Python.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))

import numpy as np  # noqa: E402

from judge import refs, views  # noqa: E402
from judge.refs import grid, REFERENCE_DIR  # noqa: E402

RES = (960, 540)


def encode(frames_dir, mp4, fps):
    ff = shutil.which('ffmpeg')
    if not ff:
        raise RuntimeError('ffmpeg is not on PATH')
    subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', os.path.join(frames_dir, 'f%04d.png'),
                    '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', '18',
                    '-movflags', '+faststart', mp4], check=True)
    return mp4


def probe(mp4):
    """ffprobe's view of the video: codec, profile, pix_fmt, width, height, frames, duration (s), and ok when it is
    H.264 High yuv420p at 960 x 540."""
    fp = shutil.which('ffprobe')
    if not fp:
        raise RuntimeError('ffprobe is not on PATH')
    out = subprocess.run([fp, '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries',
                          'stream=codec_name,profile,pix_fmt,width,height,nb_read_frames:format=duration',
                          '-of', 'json', mp4], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    s = j['streams'][0]
    r = dict(codec=s.get('codec_name'), profile=s.get('profile'), pix_fmt=s.get('pix_fmt'), width=s.get('width'),
             height=s.get('height'), frames=int(s.get('nb_read_frames', 0)),
             duration=float(j.get('format', {}).get('duration', 0.0)))
    r['ok'] = (r['codec'] == 'h264' and r['profile'] == 'High' and r['pix_fmt'] == 'yuv420p'
               and (r['width'], r['height']) == RES)
    return r


def _scene(RR, h, cell, ref, context, samples, exposure, curvature_at=None):
    """The clay tile (and the surround for the eye view) in a fresh scene; returns (scene, z0, xs, ys, z)."""
    import bpy
    rows, cols = h.shape
    sc = RR.new_scene(RES, samples, exposure)
    clay = RR.material('grey_clay', RR.CLAY, 0.9, specular=0.0)
    xs, ys = RR.axes(rows, cols, cell)
    hn = grid.to_north_up(np.asarray(h, np.float64))
    z0 = float(hn.min())
    z = hn - z0
    X, Y = np.meshgrid(xs, ys)
    if curvature_at is not None:
        z = z - ((X - curvature_at[0]) ** 2 + (Y - curvature_at[1]) ** 2) / (2 * RR.R_EFF)
    RR.grid_mesh('terrain', z, xs, ys, skirt_m=15.0 if curvature_at is not None else 0.0, mat=clay)
    if context is not None and curvature_at is not None:
        hc = grid.to_north_up(np.asarray(context[0], np.float64))
        pc = float(context[1])
        rc, cc = hc.shape
        xcs, ycs = RR.axes(rc, cc, pc)
        XC, YC = np.meshgrid(xcs, ycs)
        zc = hc - z0
        ext = cols * cell
        inside = (np.abs(XC) < ext / 2) & (np.abs(YC) < ext / 2)
        zc[inside] = RR.R.sample(z, dict(rows=rows, cols=cols, pixel_size_m=cell), XC[inside], YC[inside]) - 8.0
        zc = zc - ((XC - curvature_at[0]) ** 2 + (YC - curvature_at[1]) ** 2) / (2 * RR.R_EFF) * (~inside)
        shrink = (np.abs(XC) < ext / 2 - pc) & (np.abs(YC) < ext / 2 - pc)
        keep = ~(shrink[:-1, :-1] & shrink[1:, :-1] & shrink[1:, 1:] & shrink[:-1, 1:])
        RR.grid_mesh('context', zc, xcs, ycs, face_keep=keep, mat=clay)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam, z0, xs, ys, z


def _key(cam, frame):
    cam.keyframe_insert('location', frame=frame)
    cam.keyframe_insert('rotation_euler', frame=frame)


def _render(sc, cam, sun_xy, RR, cache_dir, frames_dir, n, fps, mp4, log):
    import bpy
    from eidoblend.sky import make_sky
    sc.frame_start, sc.frame_end = 1, n
    sc.render.fps = fps                         # every frame is keyed: the interpolation between keys never shows
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)
    t0 = time.time()
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache_dir,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option(sun_xy))
    sky.bake(frame_start=1, frame_end=n, log=lambda *a, **k: None)
    t_bake = time.time() - t0
    sc.render.filepath = os.path.join(frames_dir, 'f')
    bpy.ops.render.render(animation=True)
    t_render = time.time() - t0 - t_bake
    encode(frames_dir, mp4, fps)
    p = probe(mp4)
    log(f'[video] {os.path.basename(mp4)}: sky bake {t_bake:.0f}s, render {t_render:.0f}s ({t_render / n:.2f}s a '
        f'frame), {p}')
    return dict(mp4=mp4, bake_s=round(t_bake, 1), render_s=round(t_render, 1), probe=p)


def render_videos(name, h, cell, ref, out_dir, cache_root, context=None, eye=None, fps=24, orbit_s=8.0, dolly_s=6.0,
                  orbit_deg=360.0, dolly_m=0.0, samples=16, exposure=None, keep_frames=False, log=print):
    """The two review videos of a heightfield (row 0 = south, metres; context: (h, cell) centred alike) into
    out_dir/<name>_orbit.mp4 and <name>_dolly.mp4. eye: render_probe's dict (default: matched to the reference's
    kind of view); dolly_m: how far the dolly walks toward the target (default a tenth of the distance, 10-150 m)."""
    from mathutils import Vector
    if REFERENCE_DIR not in sys.path:
        sys.path.insert(0, REFERENCE_DIR)
    import render_references as RR
    exposure = RR.EXPOSURE if exposure is None else exposure
    os.makedirs(out_dir, exist_ok=True)
    res = {}
    # ---- the aerial orbit: the 45-degree aerial's camera, carried round the tile centre
    sc, cam, z0, xs, ys, z = _scene(RR, h, cell, ref, None, samples, exposure)
    az0 = ref.aerial_azimuth()
    zmid = float(np.median(z))
    pts = RR.frame_points(z, xs, ys)
    # the widest of the 45-degree aerials fitted at eight azimuths round the orbit, and 10 % more: one fit at the
    # first azimuth let the tile's corners touch the frame on the diagonals
    p0 = max((RR.fit_aerial(pts, zmid, az0 + k * 45.0)[0] for k in range(8)), key=lambda p: math.hypot(p[0], p[1]))
    rad = 1.1 * math.hypot(p0[0], p0[1])
    ht = zmid + 1.1 * (p0[2] - zmid)
    n = int(round(orbit_s * fps))
    cam.data.lens = 35.0
    cam.data.clip_start, cam.data.clip_end = rad * 0.02, rad * 8
    for f in range(1, n + 1):
        a = math.radians(az0 + orbit_deg * (f - 1) / n)
        RR.place_camera(cam, (math.sin(a) * rad, math.cos(a) * rad, ht), (0.0, 0.0, zmid))
        _key(cam, f)
    bx, by = RR.compass(az0)
    hd = math.atan2(-by, -bx) + math.radians(RR.SUN_LEFT_DEG)
    res['orbit'] = _render(sc, cam, (math.cos(hd), math.sin(hd)), RR, os.path.join(cache_root, name + '_orbit'),
                           os.path.join(out_dir, f'_{name}_orbit_frames'), n, fps,
                           os.path.join(out_dir, f'{name}_orbit.mp4'), log)
    # ---- the eye-level dolly: from the matched eye spot toward the target, 1.7 m over the ground every frame
    if eye is None:
        eye = views.eye_spot(h, cell, ref)
    sc, cam, z0, xs, ys, z = _scene(RR, h, cell, ref, context, samples, exposure, curvature_at=(eye['x'], eye['y']))
    meta_t = dict(rows=h.shape[0], cols=h.shape[1], pixel_size_m=cell)
    dx, dy = eye['look_x'] - eye['x'], eye['look_y'] - eye['y']
    dist = math.hypot(dx, dy)
    walk = dolly_m or min(max(0.1 * dist, 10.0), 150.0)
    ux, uy = dx / dist, dy / dist
    tz = float(RR.R.sample(z, meta_t, eye['look_x'], eye['look_y'])) + eye.get('look_dz', 0.0)
    n = int(round(dolly_s * fps))
    cam.data.lens = eye.get('lens_mm', 35.0)
    cam.data.clip_start, cam.data.clip_end = 0.5, 2.5 * max(h.shape) * cell * 4
    for f in range(1, n + 1):
        s = walk * (f - 1) / max(n - 1, 1)
        px, py = eye['x'] + ux * s, eye['y'] + uy * s
        gz = float(RR.R.sample(z, meta_t, px, py))
        RR.place_camera(cam, (px, py, gz + RR.EYE_HEIGHT), (eye['look_x'], eye['look_y'], tz))
        _key(cam, f)
    d = Vector((dx, dy, 0.0))
    hd = math.atan2(d.y, d.x) + math.radians(RR.SUN_LEFT_DEG)
    res['dolly'] = _render(sc, cam, (math.cos(hd), math.sin(hd)), RR, os.path.join(cache_root, name + '_dolly'),
                           os.path.join(out_dir, f'_{name}_dolly_frames'), n, fps,
                           os.path.join(out_dir, f'{name}_dolly.mp4'), log)
    res['dolly']['eye'] = {k: v for k, v in eye.items() if k != 'world'}
    res['dolly']['walk_m'] = walk
    if not keep_frames:
        for k in ('orbit', 'dolly'):
            shutil.rmtree(os.path.join(out_dir, f'_{name}_{k}_frames'), ignore_errors=True)
    return res


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--reference', required=True)
    ap.add_argument('--field')
    ap.add_argument('--name')
    ap.add_argument('--out', default=os.path.join(os.path.normpath(os.path.join(HERE, '..')), 'out', 'judge', 'videos'))
    ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--orbit-deg', type=float, default=360.0)
    ap.add_argument('--dolly-m', type=float, default=0.0)
    ap.add_argument('--samples', type=int, default=16)
    a = ap.parse_args(argv)
    ref = refs.load(a.reference)
    if a.field:
        d = np.load(a.field)
        h, cell = np.asarray(d['h'], np.float64), float(d['cell'])
        ctx = (np.asarray(d['context_h'], np.float64), float(d['context_cell'])) if 'context_h' in d.files else None
        eye = None
        name = a.name or os.path.splitext(os.path.basename(a.field))[0]
    else:
        h, cell = ref.h, ref.pixel
        c = refs.load_context(a.reference)
        ctx = (c[0], c[1]) if c else None
        eye = ref.eye()                                                # the reference's own view, as in its stills
        name = a.name or a.reference
    t0 = time.time()
    res = render_videos(name, h, cell, ref, a.out, os.path.join(a.out, '_sky_cache'), context=ctx, eye=eye,
                        fps=a.fps, orbit_deg=a.orbit_deg, dolly_m=a.dolly_m, samples=a.samples)
    shutil.rmtree(os.path.join(a.out, '_sky_cache'), ignore_errors=True)
    with open(os.path.join(a.out, f'{name}_videos.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1, default=str)
    ok = all(r['probe']['ok'] for r in res.values())
    print(f'[video] {name}: {"ok" if ok else "NOT OK"} in {time.time() - t0:.0f}s', flush=True)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
