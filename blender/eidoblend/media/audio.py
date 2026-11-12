"""The sound side of a Blender film: sound strips, markers, mixdown, and visemes keyed onto a VRM's face.

The audio tools themselves stay host-side Python, unchanged (generate_song.py, generate_sfx.py, align_lyrics.py,
lipsync.py, cyborg_voice.py, cyborg_stutter.py, merge_av.py, bake_weather_audio.py, voicebox, synthkit): Blender's
Python has no scipy, numba or soundfile. They write WAV and JSON; this module places them on the film's frames.

    from eidoblend.media import audio
    audio.add_sound(scene, 'work/<id>/mix.wav', t=0.0)               # a sound strip (does not replace the 3D render)
    audio.add_markers(scene, beat_times, prefix='kick')               # synthkit Track.hit_times() -> markers
    vis = audio.load_visemes('work/<id>/visemes.json')               # voicebox.visemes / lipsync.py output
    keys = audio.prepare_visemes(vis, scene, start_t=1.0, divide=1.0, windows=line_windows)
    audio.key_expressions(armature, keys)                             # shape keys + VRM previews, LINEAR

A render can carry the sound in one pass (``audio.mux_settings(scene)`` before rendering to video), or stay
video-only and be muxed with merge_av.py as before.
"""
import json
import math
from pathlib import Path

import bpy

from .screens import _abspath, set_interpolation
from .timebase import Timebase

VISEMES = ('aa', 'ih', 'ou', 'ee', 'oh')
VRM0_PRESET = {'a': 'aa', 'i': 'ih', 'u': 'ou', 'e': 'ee', 'o': 'oh'}


# ---------------------------------------------------------------------------------------------------- sound strips
def ensure_editor(scene):
    if scene.sequence_editor is None:
        scene.sequence_editor_create()
    return scene.sequence_editor


def _free_channel(scene, base=1):
    used = {s.channel for s in ensure_editor(scene).strips}
    c = base
    while c in used:
        c += 1
    return c


def add_sound(scene, path, t=None, frame=None, channel=None, volume=1.0, pan=0.0, offset=0.0, name=None):
    """A sound strip starting at film time ``t`` (or scene ``frame``). ``offset`` seconds trims the clip's head.
    A sequencer holding only sound strips leaves the 3D render in place (checked in tests/media/test_overlay.py)."""
    tb = Timebase.of(scene)
    f = int(frame) if frame is not None else tb.frame_round(t or 0.0)
    p = _abspath(path)
    ed = ensure_editor(scene)
    s = ed.strips.new_sound(name=name or p.stem, filepath=str(p), channel=channel or _free_channel(scene),
                            frame_start=f)
    s.volume = float(volume)
    s.pan = float(pan)
    if offset:
        s.sound_offset = float(offset)
    return s


def place_events(scene, events, gain=1.0):
    """[{t, clip, gain?, pan?, offset?}] (a mix's event list: book turns, foley hits) -> sound strips."""
    return [add_sound(scene, e['clip'], t=e['t'], volume=gain * e.get('gain', 1.0), pan=e.get('pan', 0.0),
                      offset=e.get('offset', 0.0)) for e in events]


def add_markers(scene, times, prefix='', names=None):
    """Timeline markers at film times (synthkit Track.hit_times(), lyric line starts, cue points)."""
    tb = Timebase.of(scene)
    out = []
    for i, t in enumerate(times):
        out.append(scene.timeline_markers.new(names[i] if names else f'{prefix}{i:03d}', frame=tb.frame_round(t)))
    return out


_SAMPLE_BYTES = {'U8': 1, 'S16': 2, 'S24': 3, 'S32': 4, 'F32': 4, 'F64': 8}


_CHILD = r'''
import ast, sys, time
from pathlib import Path
import bpy
a = sys.argv[sys.argv.index('--') + 1:]
name, out, want, timeout, settle = a[0], Path(a[1]), int(a[2]), float(a[3]), float(a[4])
kw = ast.literal_eval(a[5])
sc = bpy.data.scenes[name]
with bpy.context.temp_override(scene=sc):
    bpy.ops.sound.mixdown(filepath=str(out), **kw)
t0, last, still = time.time(), -1, time.time()
while time.time() - t0 < timeout:
    size = out.stat().st_size if out.exists() else -1
    if size != last:
        last, still = size, time.time()
    elif size > 0 and size >= want and time.time() - still >= (0.15 if want else settle):
        print(f'[mixdown] {out.name}: {size} bytes', flush=True)
        sys.exit(0)
    time.sleep(0.05)
print(f'[mixdown] {out.name}: not complete after {timeout:.0f} s ({last} bytes)', flush=True)
sys.exit(3)
'''


def mixdown(scene, path, codec='PCM', fmt='S24', mixrate=48000, bitrate=320, timeout=600.0):
    """Mix the scene's sound strips over its frame range down to a file (WAV/FLAC/MP3/AAC by extension); returns
    once the file is complete.

    Blender 5.2 runs a mixdown as a window-manager job on a thread of its own: the operator returns FINISHED before
    the file exists (in 8 ms; 0.4 s later 15 s of 48 kHz stereo is written), and without an event loop
    (a background run, or a script that keeps the UI busy) the job is never ended, so only a session's first mixdown
    writes anything: every later one wrote nothing at all. So the mixdown runs in a child Blender on a copy of this
    file: one mixdown each, waited for until the file is complete."""
    import subprocess
    import sys
    import tempfile
    p = _abspath(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    container = {'.wav': 'WAV', '.flac': 'FLAC', '.mp3': 'MP3', '.ogg': 'OGG', '.aac': 'AAC',
                 '.mka': 'MATROSKA'}.get(p.suffix.lower(), 'WAV')
    if container == 'FLAC':
        codec = 'FLAC'
    elif container == 'MP3':
        codec = 'MP3'
    elif container == 'AAC':
        codec = 'AAC'
    kw = dict(container=container, codec=codec, mixrate=mixrate, bitrate=bitrate)
    if codec in ('PCM', 'FLAC'):
        kw['format'] = fmt
    if p.exists():
        p.unlink()
    seconds = (scene.frame_end - scene.frame_start + 1) * scene.render.fps_base / scene.render.fps
    want = round(seconds * mixrate) * 2 * _SAMPLE_BYTES.get(fmt, 3) if (container, codec) == ('WAV', 'PCM') else 0
    tmp = Path(tempfile.mkdtemp(prefix='eido_mixdown_'))
    try:
        blend = tmp / 'mixdown.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(blend), copy=True, relative_remap=True, compress=False)
        (tmp / 'mixdown_child.py').write_text(_CHILD, encoding='utf-8')
        cmd = [bpy.app.binary_path, '-b']
        if '--factory-startup' in sys.argv:          # as this session was started (an isolated user folder)
            cmd.append('--factory-startup')
        cmd += [str(blend), '--python', str(tmp / 'mixdown_child.py'), '--', scene.name, str(p), str(want),
                str(timeout), '1.0', repr(kw)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=timeout + 60)
        if r.returncode != 0 or not p.exists():
            raise RuntimeError(f'mixdown {p}: the child Blender failed ({r.returncode}):\n{r.stdout[-1500:]}\n'
                               f'{r.stderr[-1500:]}')
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    return p


def mux_settings(scene, codec='AAC', bitrate=320, mixrate=48000):
    """Make a video render carry the scene's sound strips (AAC 320k at 48 kHz, as the cut does)."""
    f = scene.render.ffmpeg
    f.audio_codec = codec
    f.audio_bitrate = bitrate
    f.audio_mixrate = mixrate
    f.audio_channels = 'STEREO'
    return scene


# ---------------------------------------------------------------------------------------------------- visemes
def load_visemes(src, fps=None):
    """A viseme timeline: a list of {aa, ih, ou, ee, oh} per frame (voicebox.visemes, lipsync.get_viseme_timeline)
    or {'fps': n, 'frames': [...]} (what tests/media/audio_host.py writes). Returns (frames, fps)."""
    if isinstance(src, (str, Path)):
        src = json.loads(Path(src).read_text(encoding='utf-8'))
    if isinstance(src, dict):
        return src['frames'], float(src.get('fps', fps or 30))
    if fps is None:
        raise ValueError('a bare viseme list needs its fps')
    return src, float(fps)


def prepare_visemes(vis, scene, start_t=0.0, divide=1.0, windows=None, pad=0.12, cap_sum=1.0):
    """Viseme frames (``vis`` = (frames, fps) from load_visemes) -> {expression: [(scene frame, value)]}.

    - resampled linearly from the viseme rate to the scene's frames; source frame i sits at start_t + i / fps;
    - ``divide``: lipsync.py's audio-derived values cap at 0.35, so divide by 0.35 for them; voicebox's are 0..1
      already (divide=1);
    - ``windows``: [(t0, t1)] film seconds of the sung / spoken lines: outside them (+- ``pad``) the mouth is shut
      (demucs bleed otherwise sings along with the piano);
    - each frame's sum is scaled to at most ``cap_sum``; values are clamped to 0..1.
    WebGPU's "read at t + 1/FPS" offset does not apply: keys are evaluated on their own frame."""
    frames, fps = vis
    tb = Timebase.of(scene)
    n = len(frames)
    if not n:
        return {e: [] for e in VISEMES}
    f_first = int(math.floor(tb.frame(start_t)))
    f_last = int(math.ceil(tb.frame(start_t + (n - 1) / fps)))
    out = {e: [] for e in VISEMES}
    for f in range(f_first, f_last + 2):
        u = (tb.t(f) - start_t) * fps
        i0 = int(math.floor(u))
        a = u - i0
        vals = {}
        for e in VISEMES:
            v0 = frames[i0].get(e, 0.0) if 0 <= i0 < n else 0.0
            v1 = frames[i0 + 1].get(e, 0.0) if 0 <= i0 + 1 < n else 0.0
            vals[e] = max(0.0, (v0 * (1 - a) + v1 * a) / divide)
        t = tb.t(f)
        if windows is not None and not any(w0 - pad <= t <= w1 + pad for w0, w1 in windows):
            vals = {e: 0.0 for e in VISEMES}
        s = sum(vals.values())
        if s > cap_sum:
            vals = {e: v * cap_sum / s for e, v in vals.items()}
        for e in VISEMES:
            out[e].append((f, min(1.0, vals[e])))
    return out


def morph_binds(arm, exprs=VISEMES):
    """{expression: [(mesh object, shape key name, weight)]} from the VRM add-on's data (VRM 1.0 presets, or a
    VRM 0.x model's blend shape groups a / i / u / e / o)."""
    ext = arm.data.vrm_addon_extension
    out = {}
    try:
        pre = ext.vrm1.expressions.preset
        for e in exprs:
            lst = []
            for b in getattr(pre, e).morph_target_binds:
                o = bpy.data.objects.get(getattr(b.node, 'mesh_object_name', '') or '')
                if o is not None and o.data.shape_keys and b.index in o.data.shape_keys.key_blocks:
                    lst.append((o, b.index, float(b.weight)))
            if lst:
                out[e] = lst
    except AttributeError:
        pass
    if not out:
        try:
            for g in ext.vrm0.blend_shape_master.blend_shape_groups:
                e = VRM0_PRESET.get(g.preset_name)
                if e not in exprs:
                    continue
                lst = []
                for b in g.binds:
                    o = bpy.data.objects.get(getattr(b.mesh, 'mesh_object_name', '') or '')
                    if o is not None and o.data.shape_keys and b.index in o.data.shape_keys.key_blocks:
                        w = float(b.weight)
                        lst.append((o, b.index, w / 100.0 if w > 1.0 else w))
                if lst:
                    out[e] = lst
        except AttributeError:
            pass
    return out


def key_expressions(arm, keyed, binds=None):
    """Key each expression's shape keys (value x bind weight) and the add-on's expression preview, LINEAR,
    from prepare_visemes' {expression: [(frame, value)]}. Returns {expression: key count}."""
    binds = binds or morph_binds(arm, tuple(keyed))
    missing = [e for e in keyed if e not in binds and any(v for _f, v in keyed[e])]
    if missing:
        raise RuntimeError(f'{arm.name}: no shape-key binds for {missing} (is the VRM add-on enabled?)')
    counts = {}
    try:
        pre = arm.data.vrm_addon_extension.vrm1.expressions.preset
    except AttributeError:
        pre = None
    keys_ids = set()
    for e, ks in keyed.items():
        for o, key, w in binds.get(e, []):
            kb = o.data.shape_keys.key_blocks[key]
            for f, v in ks:
                kb.value = v * w
                kb.keyframe_insert('value', frame=f)
            keys_ids.add(o.data.shape_keys)
        if pre is not None and hasattr(pre, e):
            ex = getattr(pre, e)
            if hasattr(ex, 'preview'):
                for f, v in ks:
                    ex.preview = v
                    ex.keyframe_insert('preview', frame=f)
        counts[e] = len(ks)
    for k in keys_ids:
        set_interpolation(k, 'LINEAR', 'key_blocks')
    set_interpolation(arm.data, 'LINEAR', 'preview')
    return counts


def viseme_windows(lines, pad=0.0):
    """timebase.load_lines() lines (or voicebox Sung.lines) -> [(t0, t1)] windows for prepare_visemes."""
    out = []
    for l in lines:
        a = l.get('start', l.get('t0'))
        b = l.get('end', l.get('t1'))
        if a is not None and b is not None and str(l.get('text', 'x')).strip():
            out.append((float(a) - pad, float(b) + pad))
    return out
