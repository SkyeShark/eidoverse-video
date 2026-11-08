"""eidoblend.characters.lipsync: a VRM's mouth keyed from audio (claudesona.md, "Lipsync").

    from eidoblend.characters import load_vrm
    from eidoblend.characters import lipsync as L
    me = load_vrm('aletheia')
    vis = L.visemes_from_audio('work/song/vocals.wav', fps=30)      # the repo's lipsync.py, run in Blender's Python
    vis = L.gate_visemes(vis, [(1.0, 4.2), (5.0, 8.8)])             # mouth shut outside the sung lines (+- 0.12 s)
    rep = L.key_lipsync(me, vis, start_t=1.0)                       # aa/ih/ou/ee/oh keyed on the VRM's expressions

The WebGPU path, and what each step becomes here:
    lipsync.py get_viseme_timeline(wav, fps)    the same module (repo root), imported by path: it needs only numpy
                                                (Blender has it) and ffmpeg/ffprobe on PATH. Values 0..0.35.
    voicebox.visemes(segs, tracks, dur, fps)    host-side (scipy/numba): hand Blender its JSON; values 0..1.
    gate to the aligned lyric windows           gate_visemes(vis, windows, pad=0.12) (audio.md's recipe)
    per frame: every viseme 0, then the frame's  key_lipsync -> media.audio.prepare_visemes (frame-exact at the same
    raw values on expressionManager             fps; raw values, no multiplier: divide=1) + media.audio.key_expressions
                                                (each expression's shape keys x bind weight and the add-on's preview,
                                                LINEAR), so every frame between keys is the engine's value
    claude_suit's mouth                         installSuitMouth + makeSuitMouth({inputMax: 0.35}): key_lipsync sees the
                                                claudesona's face plate and drives it through claudesona.face instead
                                                (or mode='viseme' with phone events: the viseme mouth)

get_mouth_openness(v) is lipsync.py's helper (one openness number per frame), ported line for line.
"""

import importlib.util
import json
import os

import bpy

VISEMES = ('aa', 'ih', 'ou', 'ee', 'oh')
LIPSYNC_CAP = 0.35                 # lipsync.py's ceiling (makeSuitMouth inputMax for its timelines)
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))


def _lipsync_module():
    p = os.path.join(_REPO, 'lipsync.py')
    spec = importlib.util.spec_from_file_location('eido_lipsync', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def visemes_from_audio(path, fps=None, fft_size=1024, scene=None):
    """lipsync.py's get_viseme_timeline on an audio file -> (frames [{aa, ih, ou, ee, oh}], fps); fps defaults to the
    scene's"""
    if fps is None:
        r = (scene or bpy.context.scene).render
        fps = r.fps / r.fps_base
    frames = _lipsync_module().get_viseme_timeline(str(path), fps=int(round(fps)), fft_size=fft_size)
    return frames, float(fps)


def load(src, fps=None):
    """a viseme timeline from JSON (a list per frame, or {'fps', 'frames'}) or (frames, fps) -> (frames, fps)"""
    if isinstance(src, tuple):
        return src
    from ..media.audio import load_visemes
    return load_visemes(src, fps)


def get_mouth_openness(v):
    """lipsync.py's helper: one 0..1 openness from a viseme frame (aa/oh wide, ee/ih slight, ou pursed)"""
    return min(1.0, v.get('aa', 0) * 2.5 + v.get('oh', 0) * 2.0 + v.get('ee', 0) * 1.5 + v.get('ih', 0) * 1.5
               + v.get('ou', 0) * 1.0)


def gate_visemes(vis, windows, pad=0.12, start_t=0.0):
    """every frame outside the sung/spoken windows [(t0, t1)] (+- pad, film seconds; frame i at start_t + i / fps)
    set to 0: demucs bleed otherwise sings along with the piano. Returns a new (frames, fps)."""
    frames, fps = vis
    out = []
    for i, f in enumerate(frames):
        t = start_t + i / fps
        out.append(dict(f) if any(a - pad <= t <= b + pad for a, b in windows) else {k: 0.0 for k in f})
    return out, fps


def is_claudesona(h):
    from .claudesona import _mesh as M
    o, _ = M.find(h, 'Material', need_keys=True)
    f, _ = M.find(h, 'face')
    return o is not None and f is not None and o.data.shape_keys is not None and \
        'show MMD mouth' in o.data.shape_keys.key_blocks


def key_lipsync(h, vis, start_t=0.0, divide=1.0, windows=None, mode='auto', input_max=None, events=None,
                emotions=None, face=None, scene=None, f0=None, f1=None):
    """key a viseme timeline on h's face; returns a report.
    vis: (frames, fps) (visemes_from_audio / load) or a path to an audio file or a JSON timeline.
    mode 'auto': the claudesona -> 'suit' (its own mouth: install_suit_mouth + make_suit_mouth), any other VRM ->
    'expressions' (aa/ih/ou/ee/oh: raw values, the engine's way). 'viseme': the claudesona's full viseme mouth from
    `events` ([{t0, t1, v}], e.g. face.events_from_phones(voicebox segs)). input_max: the suit driver's inputMax
    (default 0.35 for lipsync.py timelines; pass 1 for voicebox visemes). emotions: a function t -> weights
    merged by maximum (face.make_face_track(...).at). windows: [(t0, t1)] film seconds to keep (gate_visemes)."""
    scene = scene or bpy.context.scene
    from ..media.timebase import Timebase
    tb = Timebase.of(scene)
    from_audio = False
    if isinstance(vis, (str, os.PathLike)) and os.path.splitext(str(vis))[1].lower() in ('.wav', '.mp3', '.flac', '.ogg', '.m4a'):
        vis = visemes_from_audio(vis, scene=scene)
        from_audio = True
    elif vis is not None:
        vis = load(vis)
    if mode == 'auto':
        mode = 'suit' if is_claudesona(h) else 'expressions'
    if vis is not None and windows:
        vis = gate_visemes(vis, windows, start_t=start_t)
    if mode == 'expressions':
        from ..media import audio
        keyed = audio.prepare_visemes(vis, scene, start_t=start_t, divide=divide)
        counts = audio.key_expressions(h.arm, keyed)
        frames = sorted({f for ks in keyed.values() for f, _v in ks})
        peak = max((v for ks in keyed.values() for _f, v in ks), default=0.0)
        return {'mode': mode, 'keys': counts, 'frames': [frames[0], frames[-1]] if frames else [], 'peak': round(peak, 4)}
    from .claudesona import face as F
    frames_, fps = vis if vis is not None else ([], tb.fps)
    n = len(frames_)
    if f0 is None:
        f0 = int(tb.frame_round(start_t))
    if f1 is None:
        f1 = int(tb.frame_round(start_t + max(n - 1, 0) / fps)) if n else int(tb.frame_round(max(e['t1'] for e in events) + 0.5))

    def frame_at(t):
        i = int((t - start_t) * fps + 1e-6)          # the engine reads visemes[floor(t * fps)]
        return frames_[i] if 0 <= i < n else {}
    feel = emotions or (lambda t: {})
    if mode == 'suit':
        face = face or F.install_suit_mouth(h)
        mouth = F.make_suit_mouth(input_max=LIPSYNC_CAP if input_max is None else input_max)
        opened = [0]

        def fn(t):
            w = mouth.update(t, {k: v / divide for k, v in frame_at(t).items()})
            if w.get(F.MOUTH_OPEN, 0) > 0.04:
                opened[0] += 1
            return F.merge_max(w, feel(t))
        keys = face.bake(fn, f0, f1, scene=scene)
        return {'mode': mode, 'keys': keys, 'frames': [f0, f1], 'open_frames': opened[0], 'face': face.report}
    if mode == 'viseme':
        if events is None:
            raise ValueError("key_lipsync mode='viseme' needs events [{t0, t1, v}] (face.events_from_phones)")
        face = face or F.install_viseme_mouth(h)
        track = F.make_viseme_track(events)
        opened = [0]

        def fn(t):
            s = track.at(t)
            if s['mouth'] > 0.02:
                opened[0] += 1
            return F.merge_max({'viseme': s['viseme'], 'mouth': s['mouth']}, feel(t))
        keys = face.bake(fn, f0, f1, scene=scene)
        return {'mode': mode, 'keys': keys, 'frames': [f0, f1], 'open_frames': opened[0], 'face': face.report}
    raise ValueError(f"key_lipsync mode={mode!r}: 'auto', 'expressions', 'suit' or 'viseme'")


def save(vis, path):
    """(frames, fps) -> {'fps', 'frames'} JSON (what load reads back)"""
    frames, fps = vis
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'fps': fps, 'frames': frames}, f)
    return path
