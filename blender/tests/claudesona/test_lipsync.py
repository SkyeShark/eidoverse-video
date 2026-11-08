"""A sung line with lipsync (characters/lipsync.py + claudesona/face.py): the claudesona's own handmade voicebox voice
sings "Daisy Daisy give me your answer do" (sung_line_host.py, system Python), the line placed at 0.5 s film time.

    aletheia        lipsync.py's timeline from the WAV (run inside Blender) keyed on her aa/ih/ou/ee/oh, raw (the
                    engine's way), gated to the sung line
    claude_suit A   the same timeline through the suit mouth (install_suit_mouth + make_suit_mouth, inputMax 0.35)
    claude_suit B   the viseme mouth from voicebox's own phones (events_from_phones -> make_viseme_track)
Checks:
    lipsync.py run in Blender's Python gives the very frames the system Python gives
    aletheia's keyed shape keys equal the timeline on every frame (x the bind weight), 0 outside the line +- 0.12 s
    the suit mouth opens through the sung phrases and is shut in the silences, never flickering frame to frame
    the viseme mouth shows each sung vowel's shape while it sounds (EY -> E, IY -> I, ...)
    everything is keyed: a frame evaluated cold gives the same face
Outputs: out/lipsync_sheet.png (the three faces at four sung moments, front), out/lipsync_side.png (the same at 40 deg),
out/lipsync_sung_line.mp4 (H.264 + AAC, the first 4.5 s, 960x400; --no-video skips it).

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/claudesona/test_lipsync.py [--no-render] [--no-video]
"""

import json
import math
import os
import subprocess
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import lipsync as L  # noqa: E402
from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.claudesona import face as F  # noqa: E402
from eidoblend.media import audio  # noqa: E402
from eidoblend.media.timebase import Timebase  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
VIDEO = RENDER and '--no-video' not in ARGS
FPS = 30
START = 0.5


def host_line():
    wav, js = os.path.join(S.OUT, 'sung_line.wav'), os.path.join(S.OUT, 'sung_line.json')
    if not (os.path.exists(wav) and os.path.exists(js)):
        r = subprocess.run(['python', os.path.join(S.HERE, 'sung_line_host.py'), S.OUT, str(FPS)], cwd=S.REPO,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f'sung_line_host.py failed: {r.stderr[-1500:]}')
    with open(js, encoding='utf-8') as f:
        return wav, json.load(f)


def host_lipsync(wav):
    """lipsync.py in the system Python, the reference for the in-Blender run"""
    code = ('import json,sys; sys.path.insert(0, r"%s"); from lipsync import get_viseme_timeline; '
            'print(json.dumps(get_viseme_timeline(r"%s", fps=%d)))' % (S.REPO, wav, FPS))
    r = subprocess.run(['python', '-c', code], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1500:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def main():
    R, C = {}, S.Checks('lipsync')
    try:
        wav, rec = host_line()
        windows = [(START + l['t0'], START + l['t1']) for l in rec['lines']]
        sc = S.clean_scene(FPS)
        tb = Timebase.of(sc)
        vis = L.visemes_from_audio(wav, fps=FPS)
        ref = host_lipsync(wav)
        same = len(vis[0]) == len(ref) and all(abs(a[k] - b[k]) < 1e-12 for a, b in zip(vis[0], ref) for k in a)
        R['timeline_frames'] = len(vis[0])
        C.check("lipsync.py in Blender's Python: the same frames as the system Python", same, f'{len(vis[0])} frames')
        hA = load_vrm('aletheia', location=(-0.62, 0.0, 0.0))
        hB = load_vrm('claude_suit', name='suit_mouth', location=(0.0, 0.0, 0.0))
        hC = load_vrm('claude_suit', name='viseme_mouth', location=(0.62, 0.0, 0.0))
        for h in (hB, hC):
            h.arm.scale = (0.87,) * 3
        bpy.context.view_layer.update()
        f_end = tb.frame_round(START + rec['duration']) + 2
        sc.frame_start, sc.frame_end = 1, f_end
        # aletheia: raw visemes on her expressions
        repA = L.key_lipsync(hA, vis, start_t=START, windows=windows)
        R['aletheia'] = repA
        binds = audio.morph_binds(hA.arm)
        worst, outside = 0.0, 0.0
        for f in range(1, f_end + 1):
            sc.frame_set(f)
            t = tb.t(f)
            i = round((t - START) * FPS)
            inside = any(a - 0.12 <= t <= b + 0.12 for a, b in windows)
            for e in L.VISEMES:
                for o, key, w in binds.get(e, []):
                    v = o.data.shape_keys.key_blocks[key].value
                    want = (vis[0][i].get(e, 0.0) if (0 <= i < len(vis[0]) and inside) else 0.0) * w
                    worst = max(worst, abs(v - want))
                    if not inside:
                        outside = max(outside, v)
        R['aletheia_value_max_err'] = round(worst, 6)
        C.check("aletheia: every keyed viseme equals the timeline's raw value on its frame", worst < 1e-4,
                f'max error {worst:.2e}; peak {repA["peak"]}')
        C.check('aletheia: the mouth is shut outside the sung line (+- 0.12 s)', outside < 1e-6, f'max {outside:.2e}')
        # claudesona A: the suit mouth from the same audio timeline
        repB = L.key_lipsync(hB, vis, start_t=START, windows=windows, f0=1, f1=f_end)
        R['suit'] = {k: v for k, v in repB.items() if k != 'face'}
        opens, flips, prev = [], 0, None
        plate = [o for o in hB.meshes if o.data.shape_keys and (F.KEY_PREFIX + 'mouth.seat') in o.data.shape_keys.key_blocks][0]
        for f in range(1, f_end + 1):
            sc.frame_set(f)
            on = plate.data.shape_keys.key_blocks[F.KEY_PREFIX + 'mouth.seat'].value > 0.5
            opens.append(on)
            if prev is not None and on != prev:
                flips += 1
            prev = on
        sung = [f for f in range(1, f_end + 1) if any(a <= tb.t(f) <= b for a, b in windows)]
        open_sung = sum(opens[f - 1] for f in sung) / max(1, len(sung))
        # silence: past the gate's 0.12 s pad plus the driver's release to closeAt (0.11 s x ln(1 / 0.08) = 0.28 s)
        open_silent = sum(opens[f - 1] for f in range(1, f_end + 1) if not any(a - 0.45 <= tb.t(f) <= b + 0.45 for a, b in windows))
        R['suit_open_share_sung'] = round(open_sung, 3)
        R['suit_open_frames_silent'] = open_silent
        R['suit_flips'] = flips
        C.check('the suit mouth: open through the sung phrases, shut in the silence', open_sung > 0.6 and open_silent == 0,
                f'open {100 * open_sung:.0f} % of sung frames, {open_silent} silent frames open')
        C.check('the suit mouth does not flicker (opens and closes at phrases, not consonants)', flips <= 14,
                f'{flips} open/close changes over a {rec["duration"]:.1f} s line')
        # claudesona B: the viseme mouth from voicebox's phones
        ev = F.events_from_phones([{'ph': s['ph'], 't0': s['t0'] + START, 't1': s['t1'] + START} for s in rec['segs']])
        repC = L.key_lipsync(hC, None, mode='viseme', events=ev, start_t=START, f0=1, f1=f_end)
        R['viseme'] = {k: v for k, v in repC.items() if k != 'face'}
        plateC = [o for o in hC.meshes if o.data.shape_keys and (F.KEY_PREFIX + 'viseme.seat') in o.data.shape_keys.key_blocks][0]
        hits, tests = 0, 0
        for e in ev:
            if not e['v'] or e['v'] == 'MBP' or e['t1'] - e['t0'] < 0.2:
                continue
            f = tb.frame_round((e['t0'] + e['t1']) / 2)
            sc.frame_set(f)
            kb = plateC.data.shape_keys.key_blocks
            vals = {v: kb[F.KEY_PREFIX + 'viseme.' + v].value for v in F.VISEMES}
            tests += 1
            hits += max(vals, key=vals.get) == e['v']
        R['viseme_vowel_hits'] = [hits, tests]
        C.check('the viseme mouth: each held vowel shows its own shape mid-vowel', tests > 0 and hits == tests, f'{hits}/{tests}')
        # keyed: a cold re-evaluation of one frame gives the same face
        f = sung[len(sung) // 2]
        sc.frame_set(1)
        sc.frame_set(f)
        a = [kb.value for kb in plate.data.shape_keys.key_blocks]
        sc.frame_set(f_end)
        sc.frame_set(f)
        b = [kb.value for kb in plate.data.shape_keys.key_blocks]
        C.check('keyed: a frame re-evaluated cold gives the same face', max(abs(x - y) for x, y in zip(a, b)) < 1e-9)
        audio.add_sound(sc, wav, t=START)
        if RENDER:
            render(sc, tb, rec, (hA, hB, hC), R)
    except Exception:
        traceback.print_exc()
        R['error'] = traceback.format_exc()
        C.check('ran without an exception', False)
    R['checks'] = C.rows
    R['all_pass'] = C.all_pass and 'error' not in R
    with open(os.path.join(S.OUT, 'lipsync.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    print('[lipsync] ALL PASS' if R['all_pass'] else '[lipsync] SOME FAILED', flush=True)


def render(sc, tb, rec, hs, R):
    S.probe_render(sc, res=(960, 400), samples=12)
    S.turntable_studio(sc, light=0.75)
    hz = [(h.arm.matrix_world @ h.arm.data.bones[h.humanoid['head']].head_local).z for h in hs]
    z = sum(hz) / 3 + 0.05
    cam = S.camera('lip_cam', lens=50)
    S.aim(cam, (0.0, -2.35, z), (0.0, 0.0, z - 0.02))
    sc.camera = cam
    moments = [START + 0.95, START + 2.9, START + 3.95, START + 6.0]          # "Dai-", "-sy" (2nd), "give", "an-"
    paths = []
    for t in moments:
        f = tb.frame_round(t)
        p = os.path.join(S.OUT, f'lipsync_front_f{f:03d}.png')
        S.still(sc, cam, f, p)
        paths.append(p)
    R['sheet'] = S.sheet(paths, os.path.join(S.OUT, 'lipsync_sheet.png'), cols=2)
    side = S.camera('lip_side', lens=50)
    a = math.radians(40)
    S.aim(side, (2.35 * math.sin(a), -2.35 * math.cos(a), z), (0.0, 0.0, z - 0.02))
    p2 = []
    for t in moments[:2]:
        f = tb.frame_round(t)
        p = os.path.join(S.OUT, f'lipsync_side_f{f:03d}.png')
        S.still(sc, side, f, p)
        p2.append(p)
    R['side'] = S.sheet(p2, os.path.join(S.OUT, 'lipsync_side.png'), cols=2)
    if VIDEO:
        out = os.path.join(S.OUT, 'lipsync_sung_line.mp4')
        r = sc.render
        sc.camera = cam
        sc.frame_start, sc.frame_end = 1, tb.frame_round(START + 4.5)
        r.image_settings.media_type = 'VIDEO'
        r.image_settings.file_format = 'FFMPEG'
        r.ffmpeg.format, r.ffmpeg.codec = 'MPEG4', 'H264'
        r.ffmpeg.constant_rate_factor = 'HIGH'
        audio.mux_settings(sc)
        sc.eevee.taa_render_samples = 8
        r.filepath = out
        bpy.ops.render.render(animation=True)
        R['video'] = out if os.path.exists(out) else None


main()
