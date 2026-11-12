"""eidoblend.harness.output: what a run writes. EEVEE renders straight to H.264 (as my films' render_h264.py does),
or to PNG stills, and the files land under their names only when they are whole.

Output safety (as the WebGPU edition): an existing output is moved to <out>.prev first, the render goes to
<out>.part, and only a finished render is renamed into place; absence of the output means the render did not
finish. Never review a .prev as the new render.

The post chain's records of earlier frames (look.post.history: after_image's trail, the era looks' CRT persistence,
aeropittura's echoes) are written by compositor File Outputs as each frame composites and read back by the frames
after it. post_histories(scene) finds them and what each reads; history_lead_in(scene, frame) is the first frame a
still of `frame` must render before it, in order (a trail fed by its own last frame: from its shot's start; a fixed
number of frames back: that many); render_lead_in renders those frames keeping only the records; prune_histories
deletes the records no later frame reads (a film render prunes as it goes).
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
    hist = post_histories(scene)                       # the post chain's records, pruned below as the frames go by
    scene.frame_start, scene.frame_end = int(frame_start), int(frame_end)
    fps = scene.render.fps / scene.render.fps_base
    total = int(frame_end) - int(frame_start) + 1

    def _progress(sc, *_a):
        if sc == scene:
            i = sc.frame_current - int(frame_start)
            log_progress(progress, i, total, i / fps)
            prune_histories(hist, sc.frame_current)    # a frame's records go once no later frame reads them
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


# ------------------------------------------------------------------------------- the post chain's history ---
# The look family's frame-history effects (after_image's trail, the era looks' CRT persistence, aeropittura's echoes)
# read earlier frames back from the records their compositor File Outputs write as each frame composites
# (look/post/history.py). A frame rendered alone would read records that are missing or left by an older run, so a
# still renders the frames those records come from first, in order.

def _taps_upstream(sockets):
    """The histories whose taps (Image nodes reading earlier records) feed these input sockets, through reroutes,
    muted nodes and node groups (into a group through the output linked, out of it through the group's inputs)."""
    found, seen = set(), set()
    stack = [(s, ()) for s in sockets]
    while stack:
        sock, ctx = stack.pop()
        k = (sock.as_pointer(), tuple(g.as_pointer() for g in ctx))
        if k in seen:
            continue
        seen.add(k)
        for lk in sock.links:
            if getattr(lk, 'is_muted', False):
                continue
            n = lk.from_node
            if n.bl_idname == 'CompositorNodeImage' and n.get('eido_history') is not None:
                found.add(str(n['eido_history']))
            elif n.bl_idname == 'NodeGroupInput':
                if ctx:
                    outer = next((i for i in ctx[-1].inputs if i.identifier == lk.from_socket.identifier), None)
                    if outer is not None:
                        stack.append((outer, ctx[:-1]))
            elif getattr(n, 'node_tree', None) is not None and not n.mute and n.bl_idname.endswith('Group'):
                outs = [o for o in n.node_tree.nodes if o.bl_idname == 'NodeGroupOutput']
                outs = [o for o in outs if getattr(o, 'is_active_output', False)] or outs
                for o in outs:
                    stack.extend((i, ctx + (n,)) for i in o.inputs if i.identifier == lk.from_socket.identifier)
            else:
                stack.extend((i, ctx) for i in n.inputs)
    return found


def post_histories(scene) -> list:
    """The post chain's records of earlier frames in the scene's compositor that something reads back: one dict per
    history, {'key', 'dir' (the folder its File Output writes), 'depth' (the furthest frame back its taps read),
    'cuts' (the frames it restarts at: the scene's first frame and the cuts its taps were keyed to), 'feedback' (its
    record is computed from earlier records: after_image's trail is its own last trail, so a frame depends on every
    frame of its shot before it)}. [] when the compositor is off or holds none. Each folder is made if it was cleared
    (the records are rendered again, never kept as inputs)."""
    tree = getattr(scene, 'compositing_node_group', None)
    if tree is None or not scene.render.use_compositing:
        return []
    writers, taps = {}, {}
    for n in tree.nodes:
        key = n.get('eido_history')
        if key is None or n.mute:
            continue
        if n.bl_idname == 'CompositorNodeOutputFile':
            writers[str(key)] = n
        elif n.bl_idname == 'CompositorNodeImage' and 'eido_offset' in n:
            taps.setdefault(str(key), []).append(int(n['eido_offset']))
    out = []
    for key, fo in sorted(writers.items()):
        if key not in taps:
            continue                                                 # written, never read back
        cuts = {int(c) for c in tree.get('eido_cuts_' + key, [])} | {int(scene.frame_start)}
        d = os.path.normpath(bpy.path.abspath(fo.directory))
        os.makedirs(d, exist_ok=True)
        out.append({'key': key, 'dir': d, 'depth': max(taps[key]), 'cuts': sorted(cuts),
                    'feedback': bool(_taps_upstream(list(fo.inputs)))})
    return out


def history_lead_in(scene, frame: int, histories=None) -> int:
    """The first frame to render, in order, before a still of `frame`, so every history the frame reads holds what a
    film render gives it: a feedback history from its shot's first frame (its last cut at or before `frame`), a
    history of fixed depth that many frames back, never before its cut (on a cut frame the effect reads none).
    `frame` itself when nothing is read back."""
    hs = post_histories(scene) if histories is None else histories
    start = int(frame)
    for h in hs:
        cut = max([c for c in h['cuts'] if c <= frame] or [int(scene.frame_start)])
        start = min(start, cut if h['feedback'] else max(cut, int(frame) - h['depth']))
    return max(int(scene.frame_start), start)


def prune_histories(histories, frame: int):
    """Delete the records no frame after `frame` reads (older than frame + 1 - depth): look.post.history's
    History.prune, on each writer's own folder (a History made again would re-point its writer)."""
    if not histories:
        return
    from ..look.post import history as HI
    for h in histories:
        rec = HI.History.__new__(HI.History)
        rec.dir, rec.key = h['dir'], h['key']
        rec.prune(int(frame) + 1 - h['depth'])


def render_lead_in(scene, first: int, frame: int, histories=()) -> int:
    """Render frames first .. frame - 1 in order at the scene's settings, keeping nothing but what the compositor's
    File Outputs write (the records; no picture is saved), pruning records as they age. Returns the frames rendered."""
    for g in range(int(first), int(frame)):
        scene.frame_set(g)
        bpy.ops.render.render(write_still=False)
        prune_histories(histories, g)
    return max(0, int(frame) - int(first))


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
