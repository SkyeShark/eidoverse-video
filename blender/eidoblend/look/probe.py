"""look/probe.py: probe stills from a Blender scene at given times, each one measured. eido.py render --at for Blender.

    from eidoblend.look import probe
    rows = probe.render_stills(scene, at=[1.5, 4.0], out_dir='out', name='meadow')          # jump: each frame alone
    rows = probe.render_stills(scene, at=[4.0], mode='preroll', preroll_s=1.0, ...)        # 1 s of frames evaluated first
    rows = probe.render_stills(scene, at=[4.0], mode='replay', ...)                        # every frame from the start

Files: <out_dir>/<name>_probe_at<sec>s.png, <sec> the still's FRAME time to two decimals as JS toFixed(2) writes it
(render_scene.mjs: `${probeBase}_at${(fr * dt).toFixed(2)}s.png`; the pipeline family's harness names its captures the
same way): at=2.5 at 24 fps is frame 61, 'meadow_probe_at2.50s.png'. Each still is written to a .part file and renamed
when complete, its existence checked, its wall time logged, and its highlights measured (frame_stats: the share of
pixels with any channel >= 250 and the worst grid cell).

Jump is right for anything keyed or driven: keys and drivers are pure functions of the frame. Preroll (or replay) is
needed when the frame depends on the frames before it: unbaked simulations, spring bones, frame-change handlers that
keep state. probe_cli.py --compare renders a frame both ways and reports how far they differ.
"""
import json
import os
import time

import bpy

from . import camera as C
from . import frame_stats as fs


def _png(scene):
    im = scene.render.image_settings
    if hasattr(im, 'media_type'):
        im.media_type = 'IMAGE'
    im.file_format = 'PNG'
    im.color_mode = 'RGB'
    im.color_depth = '8'
    im.compression = 15
    scene.render.use_file_extension = False


def to_fixed(x, digits=2):
    """JavaScript's Number.prototype.toFixed: the exact binary value rounded half up (Python's format rounds a tie
    such as 6.625 to even, toFixed away from zero)."""
    from decimal import ROUND_HALF_UP, Decimal
    return str(Decimal(float(x)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def still_name(name, t):
    """<name>_probe_at<t>s.png with t to two decimals, as the WebGPU harness names its captures (t: the frame's time)."""
    return f'{name}_probe_at{to_fixed(t)}s.png'


def evaluate_to(scene, frame, mode='jump', preroll_s=1.0):
    """Bring the scene to `frame` the way `mode` says (jump / preroll / replay)."""
    if mode == 'preroll':
        n = int(round(preroll_s * C.fps_of(scene)))
        for f in range(frame - n, frame):
            scene.frame_set(f)
    elif mode == 'replay':
        for f in range(scene.frame_start, frame):
            scene.frame_set(f)
    elif mode != 'jump':
        raise ValueError(f'mode {mode!r}')
    scene.frame_set(frame)


def render_still(scene, path, frame=None, mode='jump', preroll_s=1.0):
    """Render one still to `path` through a .part file. Returns wall seconds. Raises if no file came out."""
    _png(scene)
    if frame is not None:
        evaluate_to(scene, int(frame), mode, preroll_s)
    part = path + '.part'
    scene.render.filepath = part
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    dt = time.perf_counter() - t
    if not os.path.exists(part):
        raise RuntimeError(f'render wrote nothing for {path} (frame {scene.frame_current})')
    os.replace(part, path)
    return dt


def render_stills(scene, at=(), frames=(), out_dir='.', name='probe', mode='jump', preroll_s=1.0, samples=None,
                  resolution=None, percentage=None, stats=True, region_fn=None, log=True, report=True):
    """Render probe stills at times `at` (seconds from frame_start) and/or `frames`. samples / resolution /
    percentage override the scene's for these stills only. region_fn(frame) -> a normalised box (x0, y0, x1, y1,
    origin top left) adds that region's numbers (e.g. the subject's projected box). Returns rows
    {t, frame, camera, path, seconds, stats, highlights_ok, highlights}; writes <name>_probes.json beside them."""
    os.makedirs(out_dir, exist_ok=True)
    r, ee = scene.render, scene.eevee
    saved = (r.resolution_x, r.resolution_y, r.resolution_percentage, ee.taa_render_samples, r.filepath,
             r.use_file_extension)
    if samples:
        ee.taa_render_samples = int(samples)
    if resolution:
        r.resolution_x, r.resolution_y = int(resolution[0]), int(resolution[1])
    if percentage:
        r.resolution_percentage = int(percentage)
    fps = C.fps_of(scene)
    jobs = [(float(t), C.frame_at(scene, t)) for t in at] + [((f - scene.frame_start) / fps, int(f)) for f in frames]
    rows = []
    used = set()
    try:
        for t, f in jobs:
            nm = still_name(name, (f - scene.frame_start) / fps)          # the frame's own time, as WebGPU names it
            if nm in used:                                                 # two frames that round to one name
                nm = f'{name}_probe_f{f}.png'
            used.add(nm)
            p = os.path.join(out_dir, nm)
            dt = render_still(scene, p, f, mode, preroll_s)
            cam = C.camera_at(scene, f)
            row = {'t': round(t, 3), 'frame': f, 'camera': cam.name if cam else None, 'path': p, 'seconds': round(dt, 2),
                   'mode': mode}
            if stats:
                reg = region_fn(f) if region_fn else None
                st = fs.frame_stats(fs.read_rgb(p), region=reg)
                ok, msg = fs.check_highlights(st)
                row.update(stats=st, highlights_ok=ok, highlights=msg)
            rows.append(row)
            if log:
                extra = f"; {row['highlights']}" if stats else ''
                print(f"[probe] t={t:g}s frame {f} ({row['camera']}): {p} in {dt:.1f} s{extra}", flush=True)
    finally:
        r.resolution_x, r.resolution_y, r.resolution_percentage, ee.taa_render_samples, r.filepath, \
            r.use_file_extension = saved
    if report:
        with open(os.path.join(out_dir, f'{name}_probes.json'), 'w', encoding='utf-8') as fh:
            json.dump(rows, fh, indent=1)
    return rows
