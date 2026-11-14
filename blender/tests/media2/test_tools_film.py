"""Probe: what the engine-agnostic audio tools wrote (tools_host.py), put into a Blender film. From the main checkout:

    bash run_blender.sh <worktree>/blender/tests/media2/test_tools_film.py [-- --only vrm,sound,captions]
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

vrm       claude.vrm sings DAISY's chorus 1 (69-84 s of the song, frame 1 = 69 s): lipsync.py's audio-derived
          visemes (0..0.35, so divide=0.35), gated to align_lyrics.py's lines (audio.viseme_windows), keyed onto its
          expressions; read back; face stills at the widest frame and at a rest between lines
          -> out/tools_vrm_f*.png
sound     the cyborg-toned lead (cyborg_voice.py), the synthkit loop (its kicks as markers) and the stuttered speech
          (cyborg_stutter.py) as sound strips; a one-pass H.264 + AAC render of 2 s; a mixdown of the strips
          -> out/tools_av_onepass.mp4, out/tools_work/tools_mixdown.wav
captions  DAISY's captions.py ASS (era styles, karaoke) burned onto test_era_screens.py's EEVEE film in the song's
          time (ffmpeg's ass filter with the bundled fonts), the song under it -> out/era_film_captions.mp4 and a
          frame grab out/era_film_captions_f*.png
Prints PASS/FAIL lines for what it measures.
"""
import json
import subprocess
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'media'))
import _stage as S  # noqa: E402
from eidoblend.media import audio, timebase  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else {'vrm', 'sound', 'captions'}
OUT = HERE / 'out'
WORK = OUT / 'tools_work'
WT = HERE.parents[2]
DAISY = OUT / 'daisy' / 'out'
X0 = 69.0                                     # the excerpt's start in the song (tools_host.py)
FPS = 24
FAILS = []


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def probe(path, entries):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', entries, '-of', 'json', str(path)],
                       capture_output=True, text=True)
    return json.loads(r.stdout or '{}')


def build_singer():
    sc = S.fresh_scene(frames=(1, 15 * FPS), fps=FPS)
    sc['eido_frame0'] = 1 - round(X0 * FPS)                  # frame 1 = 69 s of the song
    bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
    before = set(bpy.data.objects)
    bpy.ops.import_scene.vrm(filepath=str(S.ASSETS / 'vrms' / 'claude.vrm'))
    arm = next(o for o in bpy.data.objects if o not in before and o.type == 'ARMATURE')
    return sc, arm


def probe_vrm(sc, arm):
    vj = json.loads((WORK / 'lead_chorus1_lipsync.json').read_text(encoding='utf-8'))
    vis = audio.load_visemes(vj['frames'], fps=vj['fps'])               # lipsync.py's bare list + its fps
    aligned = json.loads((WORK / 'lead_chorus1_aligned.json').read_text(encoding='utf-8'))
    lines = timebase.load_lines([{**l, 'start': l['start'] + X0, 'end': l['end'] + X0} for l in aligned])
    wins = audio.viseme_windows(lines)
    keys = audio.prepare_visemes(vis, sc, start_t=X0, divide=0.35, windows=wins, pad=0.12)
    binds = audio.morph_binds(arm)
    counts = audio.key_expressions(arm, keys, binds)
    check(all(counts.get(e, 0) > 300 for e in audio.VISEMES), f'keyed every frame per expression: {counts}')
    worst = 0.0
    for e, ks in keys.items():
        for f, v in ks[::23]:
            sc.frame_set(f)
            for o, key, w in binds.get(e, []):
                worst = max(worst, abs(o.data.shape_keys.key_blocks[key].value - v * w))
    check(worst < 1e-4, f'shape keys read back the prepared lipsync.py values (worst {worst:.6f})')
    tb = timebase.Timebase.of(sc)
    per = {}
    for e, ks in keys.items():
        for f, v in ks:
            per.setdefault(f, {})[e] = v
    f_open = max(per, key=lambda f: sum(per[f].values()))
    gaps = [(a[1], b[0]) for a, b in zip(wins, wins[1:]) if b[0] - a[1] > 0.4]
    f_rest = int(round(tb.frame((gaps[0][0] + gaps[0][1]) / 2))) if gaps else 1
    check(sum(per[f_open].values()) > 0.6 and sum(per.get(f_rest, {}).values()) == 0.0,
          f'widest at frame {f_open} ({tb.t(f_open):.2f} s, sum {sum(per[f_open].values()):.2f}); shut between '
          f'lines at frame {f_rest} ({tb.t(f_rest):.2f} s); {len(wins)} sung windows from align_lyrics.py')
    mouth = binds['aa'][0][0]
    corners = [mouth.matrix_world @ Vector(c) for c in mouth.bound_box]
    mp = sum(corners, Vector()) / 8
    S.area_light(sc, mp + Vector((-0.9, -1.2, 0.6)), mp, 60.0, size=0.8, color=(1.0, 0.93, 0.85), name='key')
    S.area_light(sc, mp + Vector((1.0, -0.8, 0.1)), mp, 20.0, size=1.0, color=(0.8, 0.86, 1.0), name='fill')
    S.area_light(sc, mp + Vector((0.2, 1.0, 0.6)), mp, 30.0, size=0.6, name='rim')
    sc.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.055, 0.06, 1)
    S.camera(sc, mp + Vector((0.0, -1.1, 0.03)), mp + Vector((0, 0, 0.02)), lens=60)
    stills = [S.render_still(sc, f, OUT / f'tools_vrm_f{f:03d}.png') for f in (f_open, f_rest)]
    a, b = (np.asarray(Image.open(p).convert('L')).astype(float) for p in stills)
    check(np.abs(a - b).mean() > 0.3, f'the open and the shut mouth differ on screen (mean |diff| '
                                      f'{np.abs(a - b).mean():.2f})')
    return f_open


def probe_sound(sc, f_open):
    lead = audio.add_sound(sc, WORK / 'lead_chorus1_cyborg.wav', t=X0, name='lead_cyborg')
    audio.add_sound(sc, WORK / 'loop.wav', t=X0, volume=0.5, name='synthkit_loop')
    talk = audio.add_sound(sc, WORK / 'spoken_stutter.wav', t=X0 + 9.5, volume=0.8, pan=-0.3, name='stutter')
    hits = json.loads((WORK / 'loop_hits.json').read_text(encoding='utf-8'))['kick']
    marks = audio.add_markers(sc, [X0 + h for h in hits], prefix='kick')
    tb = timebase.Timebase.of(sc)
    check(lead.frame_start == 1 and talk.frame_start == int(round(tb.frame(X0 + 9.5))),
          f'strips placed in the song\'s time: lead at frame {lead.frame_start}, stutter at {talk.frame_start}')
    check(len(marks) == len(hits), f'{len(marks)} kick markers from synthkit\'s hit_times()')
    r = sc.render
    keep = r.resolution_x, r.resolution_y, sc.eevee.taa_render_samples
    r.resolution_x, r.resolution_y = 480, 270
    sc.eevee.taa_render_samples = 4
    r.image_settings.media_type = 'VIDEO'
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format, r.ffmpeg.codec = 'MPEG4', 'H264'
    audio.mux_settings(sc)
    r.use_file_extension = False
    mp4 = OUT / 'tools_av_onepass.mp4'
    r.filepath = str(mp4)
    fs, fe = sc.frame_start, sc.frame_end
    sc.frame_start, sc.frame_end = max(1, f_open - 24), max(1, f_open - 24) + 47
    bpy.ops.render.render(animation=True, scene=sc.name)
    j = probe(mp4, 'stream=codec_type,codec_name,sample_rate,channels:format=duration')
    kinds = sorted((s['codec_type'], s['codec_name']) for s in j.get('streams', []))
    check(kinds == [('audio', 'aac'), ('video', 'h264')] and abs(float(j['format']['duration']) - 2.0) < 0.1,
          f'one-pass render: {kinds}, {j.get("format", {}).get("duration")} s')
    sc.frame_start, sc.frame_end = fs, fe
    r.resolution_x, r.resolution_y, sc.eevee.taa_render_samples = keep
    wav = audio.mixdown(sc, WORK / 'tools_mixdown.wav')
    j = probe(wav, 'format=duration:stream=sample_rate,channels')
    st = j['streams'][0]
    check(int(st['sample_rate']) == 48000 and int(st['channels']) == 2 and float(j['format']['duration']) > 14.5,
          f'mixdown: {st["sample_rate"]} Hz, {st["channels"]} ch, {float(j["format"]["duration"]):.2f} s')


def probe_captions():
    ass = DAISY / 'daisy_upto_chorus2.ass'
    film = OUT / 'era_film_silent.mp4'
    if not (ass.exists() and film.exists()):
        check(False, 'captions: run tools_host.py --only daisy and test_era_screens.py --only film first')
        return
    t_start = 24.25                                           # test_era_screens.py's film: frame 1 = 24.25 s
    shifted = WORK / 'daisy_era_film.ass'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-itsoffset', f'{-t_start:.4f}', '-i', str(ass), '-c', 'copy',
                    str(shifted)], check=True)
    song = WORK / 'era_film_song.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t_start:.4f}', '-t', '7.5', '-i',
                    str(DAISY / 'daisy_master_upto_chorus2.wav'), str(song)], check=True)
    out = OUT / 'era_film_captions.mp4'
    rel = shifted.relative_to(WT).as_posix()
    vf = f'scale=1280:720:flags=lanczos,ass={rel}:fontsdir=eidoverse/assets/fonts'
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(film), '-i', str(song), '-vf', vf, '-map', '0:v',
                        '-map', '1:a', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                        '-shortest', str(out)], capture_output=True, text=True, cwd=str(WT))
    print(r.stderr[-800:])
    check(r.returncode == 0 and out.exists(), 'captions.py\'s ASS burned onto the EEVEE film (ass filter, bundled '
                                              'fonts), the song under it')
    for t in (1.5, 5.5):                                      # 25.75 s: voder's line; 29.75 s: bell_1961's
        png = OUT / f'era_film_captions_t{t:.1f}.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', str(out), '-frames:v', '1', str(png)],
                       check=True)
        a = np.asarray(Image.open(png).convert('RGB')).astype(float)
        plain = np.asarray(Image.open(film_frame(film, t)).convert('RGB').resize((1280, 720))).astype(float)
        diff = np.abs(a - plain).mean(axis=-1)
        rows = np.where(diff.mean(axis=1) > 6)[0]
        check(rows.size > 10, f'caption visible at {t_start + t:.2f} s in the song (rows changed '
                              f'{rows.min() if rows.size else -1}..{rows.max() if rows.size else -1})')


def film_frame(film, t):
    p = WORK / f'_plain_{t:.1f}.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', str(film), '-frames:v', '1', str(p)],
                   check=True)
    return p


def main():
    if {'vrm', 'sound'} & ONLY:
        sc, arm = build_singer()
        f_open = probe_vrm(sc, arm) if 'vrm' in ONLY else 120
        if 'sound' in ONLY:
            probe_sound(sc, f_open)
    if 'captions' in ONLY:
        probe_captions()
    for p in WORK.glob('_plain_*.png'):
        p.unlink()
    print(f'[test_tools_film] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)


main()
