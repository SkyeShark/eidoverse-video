"""eidoblend.harness.output: what a run writes. EEVEE renders straight to H.264 (as my films' render_h264.py does),
or to PNG stills, and the files land under their names only when they are whole.

Output safety (as the WebGPU edition): an existing output is moved to <out>.prev first, the render goes to
<out>.part, and only a finished render is renamed into place; absence of the output means the render did not
finish. Never review a .prev as the new render.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import bpy


def set_h264(scene, path: str):
    """Blender's own ffmpeg writer: H.264 in MP4, near-lossless (CRF 'PERC_LOSSLESS'), GOP 24, no audio (sound is
    muxed afterwards with merge_av.py). use_file_extension off, so Blender writes exactly `path`."""
    r = scene.render
    im = r.image_settings
    if hasattr(im, 'media_type'):                       # Blender 5: video is a media type, then FFMPEG its format
        im.media_type = 'VIDEO'
    im.file_format = 'FFMPEG'
    im.color_mode = 'RGB'
    r.ffmpeg.format = 'MPEG4'
    r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'PERC_LOSSLESS'
    r.ffmpeg.ffmpeg_preset = 'GOOD'
    r.ffmpeg.gopsize = 24
    r.ffmpeg.audio_codec = 'NONE'
    r.use_file_extension = False
    r.filepath = path


def set_png(scene, path: str = ''):
    r = scene.render
    im = r.image_settings
    if hasattr(im, 'media_type'):
        im.media_type = 'IMAGE'
    im.file_format = 'PNG'
    im.color_mode = 'RGBA' if r.film_transparent else 'RGB'
    im.color_depth = '8'
    im.compression = 15
    r.use_file_extension = False
    if path:
        r.filepath = path


def displace(path: str) -> str | None:
    """Move an existing output to <path>.prev (replacing an older .prev). Returns the .prev path if it moved one."""
    if not os.path.exists(path):
        return None
    prev = path + '.prev'
    if os.path.exists(prev):
        os.remove(prev)
    os.replace(path, prev)
    return prev


def render_video(scene, out: str, frame_start: int, frame_end: int, progress: str = 'eido_blender') -> str:
    """Render frames frame_start..frame_end to H.264 at `out` (through out.part). Returns out. RENDER_CODEC /
    RENDER_CQ / RENDER_BITRATE apply as render_common.mjs's ffmpeg pipe applied them; a progress line is printed every
    15 frames and on the last (render_common.mjs logProgress)."""
    from .render_common import ffmpeg_rate_control, log_progress
    os.makedirs(os.path.dirname(out), exist_ok=True)
    part = out + '.part'
    if os.path.exists(part):
        os.remove(part)
    set_h264(scene, part)
    for n in ffmpeg_rate_control(scene):
        print(f'[{progress}] video: {n}', flush=True)
    keep = scene.frame_start, scene.frame_end
    scene.frame_start, scene.frame_end = int(frame_start), int(frame_end)
    fps = scene.render.fps / scene.render.fps_base
    total = int(frame_end) - int(frame_start) + 1

    def _progress(sc, *_a):
        if sc == scene:
            i = sc.frame_current - int(frame_start)
            log_progress(progress, i, total, i / fps)
    bpy.app.handlers.render_post.append(_progress)
    try:
        bpy.ops.render.render(animation=True)
    finally:
        scene.frame_start, scene.frame_end = keep
        if _progress in bpy.app.handlers.render_post:
            bpy.app.handlers.render_post.remove(_progress)
    if not os.path.exists(part) or os.path.getsize(part) == 0:
        raise RuntimeError(f'the render wrote no video ({part} missing or empty)')
    os.replace(part, out)
    return out


def render_still(scene, frame: int, png: str) -> str:
    """Render one frame to a PNG (through png.part), the scene evaluated at that frame first."""
    os.makedirs(os.path.dirname(png), exist_ok=True)
    scene.frame_set(int(frame))
    part = png + '.part'
    set_png(scene, part)
    bpy.ops.render.render(write_still=True)
    if not os.path.exists(part):
        raise RuntimeError(f'the render wrote no still for frame {frame} ({part} missing)')
    os.replace(part, png)
    return png


def ffmpeg_exe():
    return os.environ.get('FFMPEG_PATH') or shutil.which('ffmpeg')


def extract_probe_frames(video: str, n_frames: int) -> list:
    """Three stills from a rendered video at 15 / 50 / 85 % (<stem>_probe1..3.png), so looking at the render costs one
    file read. Returns the PNG paths written (empty if ffmpeg is missing)."""
    ff = ffmpeg_exe()
    if not ff:
        return []
    stem = os.path.splitext(video)[0]
    picks = sorted({max(0, min(n_frames - 1, int(n_frames * f))) for f in (0.15, 0.5, 0.85)})
    sel = '+'.join(f'eq(n\\,{n})' for n in picks)
    for i in range(1, 4):
        p = f'{stem}_probe{i}.png'
        if os.path.exists(p):
            os.remove(p)
    r = subprocess.run([ff, '-y', '-loglevel', 'error', '-i', video, '-vf', f'select={sel}', '-fps_mode', 'vfr',
                        f'{stem}_probe%d.png'], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'ffmpeg exit {r.returncode}: {r.stderr.strip()[-300:]}')
    return [f'{stem}_probe{i + 1}.png' for i in range(len(picks)) if os.path.exists(f'{stem}_probe{i + 1}.png')]


def probe_video(video: str) -> dict:
    """ffprobe's view of a written video: codec, pixel format, size, frame count (or {} without ffprobe)."""
    fp = shutil.which('ffprobe')
    if not fp or not os.path.exists(video):
        return {}
    r = subprocess.run([fp, '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries',
                        'stream=codec_name,profile,pix_fmt,width,height,nb_read_frames,r_frame_rate', '-of',
                        'default=nw=1', video], capture_output=True, text=True)
    info = {}
    for line in r.stdout.splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            info[k.strip()] = v.strip()
    return info
