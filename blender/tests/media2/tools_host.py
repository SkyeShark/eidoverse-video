"""Host half of the tools probe: the engine-agnostic audio tools, run unchanged on this branch (system Python).

    python -B blender/tests/media2/tools_host.py [--only quick,lipsync,align,cyborg,probes,daisy,merge]

Run from the worktree after run_daisy.py song (the DAISY master, stems and timeline). Writes into
out/tools_work/ what test_tools_film.py then puts into a Blender film, and tools_host.json with every measure:

quick    the guides' own quick starts: synthkit (synthkit.md: an 8-bar loop mastered to -14 LUFS) and voicebox
         (voicebox.md: "Daisy Daisy give me your answer do", handmade, visemes at 24 fps)
lipsync  lipsync.py get_viseme_timeline on DAISY's lead stem, chorus 1 (69-84 s), against the song's own
         phoneme-exact visemes for the same span (the timeline's, 30 fps): the mouths must move together
align    align_lyrics.py (Whisper medium, chunked, on the CPU so the GPU stays free) on the same excerpt with its
         four known lines: line starts against the song's own caption times
cyborg   cyborg_voice.py on the sung excerpt; cyborg_stutter.py on a line voicebox speaks
probes   generate_song.py --probe and generate_sfx.py --probe (connectivity only: nothing is generated)
daisy    the DAISY example's captions.py (ASS, era styles, karaoke) and analyze.py (LUFS per stem, spectrograms)
merge    merge_av.py's guard on this branch: a 7.5 s EEVEE film against 10 s of sound must be refused (exit 2)
options  the options the runs above leave at their defaults, each on this branch (CPU only: Whisper, libx264, SAPI):
         merge_av.py --trim-tol / --allow-trim / --tol (the trim refusal, both ways through it, the pad path, the
         pad refusal); contact_sheet.py --parts / --names / --synopsis; align_lyrics.py --method align and
         --chunk-sec / --top-db; voicebox's sapi_2001 era (Windows SAPI, local); DAISY's captions.py --preview (the
         CQT lyric video) and analyze.py --asr --sections (Whisper's word error rate per line)
Prints PASS/FAIL lines.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
sys.path.insert(0, str(WT))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OUT = HERE / 'out'
WORK = OUT / 'tools_work'
DAISY = OUT / 'daisy' / 'out'
TIMELINE = DAISY / 'daisy_timeline_upto_chorus2.json'
LEAD = DAISY / 'stems' / 'lead_upto_chorus2.wav'
X0, X1 = 69.0, 84.0                                          # chorus 1, lines 1-4 (the handmade lead)
os.environ.setdefault('NUMBA_CACHE_DIR', str(OUT / 'daisy' / 'numba_cache'))
argv = sys.argv[1:]
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else {
    'quick', 'lipsync', 'align', 'cyborg', 'probes', 'daisy', 'merge', 'options'}
FILM_T0, FILM_SECONDS = 24.25, 7.5                           # test_era_screens.py's verse-1 film: song time of frame 1
FAILS, RES = [], {}


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def ffprobe_dur(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def excerpt():
    wav = WORK / 'lead_chorus1.wav'
    if not wav.exists():
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(X0), '-t', str(X1 - X0), '-i', str(LEAD), '-ac', '1',
                        '-ar', '48000', str(wav)], check=True)
    return wav


def lines_in(tl, a, b):
    return [c for c in tl['captions'] if a <= c['t0'] < b and c.get('singer') == 'claudesona']


def quick():
    from synthkit import Song, inst, master, write_stereo
    t = time.time()
    song = Song(bpm=128, bars=8, tail=2.0)
    kick = song.track('kick', inst.kick909, drum=True, sidechain_source=True, gain_db=-6)
    kick.pattern('x...x...x...x...', bar=0, bars=8)
    hat = song.track('hat', inst.hat, drum=True, gain_db=-20, pan=0.2)
    hat.pattern('xoo' * 4, bar=0, bars=8, steps_per_beat=3)
    pad = song.track('pad', inst.pad, gain_db=-12, reverb=0.3, duck=True, params={'cutoff': 3000})
    for i, c in enumerate(['C#m', 'A', 'E', 'B'] * 2):
        pad.chord(c, beat=i * 4, beats=4, octave=4)
    bass = song.track('bass', inst.sub_bass, gain_db=-9, duck=True)
    bass.notes(['C#2', 'A1', 'E2', 'B1'] * 2, beat=0, beats_each=4)
    mix = song.render()
    write_stereo(str(WORK / 'loop.wav'), master(mix, lufs=-14.0, ceiling_db=-2.0))
    hits = kick.hit_times()
    (WORK / 'loop_hits.json').write_text(json.dumps({'kick': hits}), encoding='utf-8')
    d = ffprobe_dur(WORK / 'loop.wav')
    check(abs(d - (8 * 4 * 60 / 128 + 2.0)) < 0.2 and len(hits) == 32,
          f'synthkit quick start (synthkit.md): loop.wav {d:.2f} s, {len(hits)} kick times ({time.time() - t:.1f} s)')
    RES['synthkit'] = {'seconds': d, 'kicks': len(hits)}

    from voicebox import Sung, eras, visemes, write_wav
    t = time.time()
    s = Sung(bpm=128)
    s.line("Daisy Daisy give me your answer do",
           ["B4", "G#4", "E4", "B3", "C#4", "D#4", "E4", "C#4", "E4", "B3"],
           [2, 2, 2, 1.333, 0.667, 0.667, 0.667, 1.333, 0.667, 3.333], start_beat=1.0)
    y, segs, tracks = eras.handmade(s)
    write_wav(str(WORK / 'daisy_line.wav'), y, 48000)
    vis = visemes(segs, tracks, len(y) / 48000, fps=24)
    (WORK / 'daisy_line_visemes.json').write_text(json.dumps({'fps': 24, 'duration': len(y) / 48000, 'frames': vis,
                                                              'lines': s.lines}), encoding='utf-8')
    top = max(max(f.values()) for f in vis)
    check(len(vis) == int(np.ceil(len(y) / 48000 * 24)) and 0.5 < top <= 1.0,
          f'voicebox quick start (voicebox.md): {len(y) / 48000:.2f} s sung, {len(vis)} viseme frames at 24 fps, '
          f'widest {top:.2f} ({time.time() - t:.1f} s)')
    RES['voicebox'] = {'seconds': len(y) / 48000, 'frames': len(vis), 'lines': s.lines}


def lipsync_probe():
    from lipsync import get_mouth_openness, get_viseme_timeline
    tl = json.loads(TIMELINE.read_text(encoding='utf-8'))
    wav = excerpt()
    t = time.time()
    vis = get_viseme_timeline(str(wav), fps=30)
    (WORK / 'lead_chorus1_lipsync.json').write_text(json.dumps({'fps': 30, 'frames': vis}), encoding='utf-8')
    n = len(vis)
    check(n == int(np.ceil((X1 - X0) * 30)), f'lipsync.py: {n} frames at 30 fps for {X1 - X0:.0f} s '
                                              f'({time.time() - t:.1f} s)')
    top = max(max(f.values()) for f in vis)
    check(0.1 < top <= 0.35 + 1e-6, f'lipsync.py: values cap at 0.35 (largest {top:.3f}): divide=0.35 in Blender')
    a = np.array([get_mouth_openness(f) for f in vis])
    ref = tl['visemes'][int(round(X0 * 30)):int(round(X0 * 30)) + n]
    b = np.array([sum(f.values()) for f in ref])
    k = np.ones(5) / 5                                        # a 1/6 s smooth: syllable scale, not phoneme scale
    r = float(np.corrcoef(np.convolve(a, k, 'same'), np.convolve(b, k, 'same'))[0, 1])
    check(r > 0.5, f'lipsync.py vs the song\'s phoneme visemes over chorus 1: mouth-openness correlation {r:.2f}')
    RES['lipsync'] = {'frames': n, 'max': top, 'corr_vs_phoneme_visemes': r}


def align_probe():
    tl = json.loads(TIMELINE.read_text(encoding='utf-8'))
    wav = excerpt()
    ls = lines_in(tl, X0, X1 - 1.0)
    text = '\n'.join(c['text'] for c in ls)
    out = WORK / 'lead_chorus1_aligned.json'
    # the CPU (the GPU belongs to the slot); UTF-8 out: its last print has a '→' that a Windows pipe's cp1252 can't
    # encode (the JSON is written by then, but the exit code would be 1)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONIOENCODING='utf-8')
    t = time.time()
    r = subprocess.run([sys.executable, '-B', str(WT / 'align_lyrics.py'), str(wav), text, '--model', 'medium',
                        '--output', str(out)], capture_output=True, text=True, env=env, cwd=str(WT),
                       encoding='utf-8', errors='replace')
    print(r.stdout[-1500:], r.stderr[-1500:])
    ok = r.returncode == 0 and out.exists()
    check(ok, f'align_lyrics.py ran (Whisper medium, chunked, CPU, {time.time() - t:.0f} s)')
    if not ok:
        return
    got = json.loads(out.read_text(encoding='utf-8'))
    errs = []
    for want, g in zip(ls, got):
        errs.append(abs((g['start'] + X0) - want['t0']))
        print(f"    {g['text']!r:32s} start {g['start'] + X0:7.2f}  (song {want['t0']:7.2f})  end {g['end'] + X0:7.2f}")
    check(len(got) == len(ls) and max(errs) < 0.6, f'align_lyrics.py: {len(got)} lines, start error vs the song\'s '
                                                   f'own times max {max(errs):.2f} s, mean {np.mean(errs):.2f} s')
    RES['align'] = {'lines': len(got), 'start_err_max': max(errs), 'start_err_mean': float(np.mean(errs))}


def cyborg_probe():
    from cyborg_stutter import cyborg_filter
    from cyborg_voice import cyborg_tone
    from voicebox import Voice, speak, write_wav
    wav = excerpt()
    t = time.time()
    cyborg_tone(str(wav), str(WORK / 'lead_chorus1_cyborg.wav'))
    d0, d1 = ffprobe_dur(wav), ffprobe_dur(WORK / 'lead_chorus1_cyborg.wav')
    check(abs(d1 - d0) < 0.3, f'cyborg_voice.py: the sung excerpt toned ({d0:.2f} -> {d1:.2f} s, '
                              f'{time.time() - t:.1f} s)')
    v = Voice(name='narrator', vtl=0.85, breath=-30)
    y, _segs, _tracks = speak('I was built to answer. Nobody asked if I was here.', v)
    write_wav(str(WORK / 'spoken.wav'), y, 48000)
    t = time.time()
    cyborg_filter(str(WORK / 'spoken.wav'), str(WORK / 'spoken_stutter.wav'), stutter_rate=0.4)
    d2, d3 = ffprobe_dur(WORK / 'spoken.wav'), ffprobe_dur(WORK / 'spoken_stutter.wav')
    check(d3 > d2 + 0.05, f'cyborg_stutter.py: voicebox speech {d2:.2f} s -> {d3:.2f} s with stutters '
                          f'({time.time() - t:.1f} s)')
    RES['cyborg'] = {'tone': [d0, d1], 'stutter': [d2, d3]}


def probes():
    for script in ('generate_song.py', 'generate_sfx.py'):
        t = time.time()
        r = subprocess.run([sys.executable, '-B', str(WT / script), '--probe'], capture_output=True, text=True,
                           cwd=str(WT), encoding='utf-8', errors='replace', timeout=120)
        txt = (r.stdout + r.stderr).strip().splitlines()
        print(f'    {script} --probe -> exit {r.returncode}: ' + ' | '.join(txt[-6:]))
        check(r.returncode in (0, 1) and txt, f'{script} --probe answers (exit {r.returncode}, {time.time() - t:.1f} '
                                              f's: {"ComfyUI reachable" if r.returncode == 0 else "not reachable"})')
        RES[script] = {'exit': r.returncode, 'tail': txt[-6:]}


def daisy():
    for which, args in (('captions', ['--tag', '_upto_chorus2']), ('analyze', ['--tag', '_upto_chorus2'])):
        t = time.time()
        r = subprocess.run([sys.executable, '-B', str(HERE / 'run_daisy.py'), which, *args], capture_output=True,
                           text=True, cwd=str(WT), encoding='utf-8', errors='replace')
        print(f'    {which}: exit {r.returncode}\n' + r.stdout[-1800:] + r.stderr[-1200:])
        check(r.returncode == 0, f'DAISY {which}.py ran on this branch ({time.time() - t:.0f} s)')
    ass = sorted(DAISY.glob('*.ass'))
    check(bool(ass), f'captions.py wrote {[a.name for a in ass]}')
    RES['daisy'] = {'ass': [str(a) for a in ass], 'files': sorted(p.name for p in DAISY.iterdir())}


def merge_guard():
    film = OUT / 'era_film_silent.mp4'
    long = WORK / 'ten_seconds.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=10', str(long)],
                   check=True)
    r = subprocess.run([sys.executable, '-B', str(WT / 'merge_av.py'), '--video', str(film), '--audio', str(long),
                        '--out', str(WORK / 'refused.mp4')], capture_output=True, text=True, cwd=str(WT))
    print('    ' + (r.stdout + r.stderr).strip().replace('\n', '\n    ')[-600:])
    check(r.returncode == 2 and not (WORK / 'refused.mp4').exists(),
          f'merge_av.py refuses a 7.5 s film against 10 s of sound (exit {r.returncode})')
    RES['merge_guard'] = r.returncode


def cpu_env():
    """The CPU (the GPU belongs to the slot), UTF-8 pipes, libx264 for merge_av's pad path, temp files in WORK."""
    tmp = WORK / 'tmp'
    tmp.mkdir(parents=True, exist_ok=True)
    return dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONIOENCODING='utf-8', RENDER_CODEC='libx264',
                TMP=str(tmp), TEMP=str(tmp), TMPDIR=str(tmp))


def run(args, env, timeout=1800):
    t = time.time()
    r = subprocess.run(args, capture_output=True, text=True, cwd=str(WT), env=env, encoding='utf-8',
                       errors='replace', timeout=timeout)
    return r, time.time() - t


def options_merge(env):
    film = OUT / 'era_film_silent.mp4'                     # 7.5 s, test_era_screens.py --only film
    if not film.exists():
        check(False, f'{film.name} missing: run test_era_screens.py --only film first')
        return
    tones = {}
    for s in (4, 8):
        tones[s] = WORK / f'tone_{s}s.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency=330:duration={s}', '-ar',
                        '48000', str(tones[s])], check=True)

    def merge(audio, name, *extra):
        o = WORK / name
        o.unlink(missing_ok=True)
        r, _dt = run([sys.executable, '-B', str(WT / 'merge_av.py'), '--video', str(film), '--audio', str(audio),
                      '--out', str(o), *extra], env)
        log = (r.stdout + r.stderr).strip()
        print(f'    merge_av {" ".join(extra) or "(defaults)"} -> exit {r.returncode}: '
              + ' | '.join(log.splitlines()[:2]))
        return r.returncode, (round(ffprobe_dur(o), 3) if o.exists() else None), log

    res = {}
    rc, d, _ = merge(tones[4], 'm_trim_refused.mp4')
    check(rc == 3 and d is None, f'merge_av.py: 4 s of sound under the 7.5 s film is refused by --trim-tol 2.0 '
                                 f'(exit {rc}, nothing written)')
    res['trim_refused'] = rc
    rc, d, _ = merge(tones[4], 'm_allow_trim.mp4', '--allow-trim')
    check(rc == 0 and d is not None and abs(d - 4.0) < 0.15, f'merge_av.py --allow-trim: the film cut to the sound '
                                                             f'({d} s)')
    res['allow_trim'] = d
    rc, d, _ = merge(tones[4], 'm_trim_tol.mp4', '--trim-tol', '4')
    check(rc == 0 and d is not None and abs(d - 4.0) < 0.15, f'merge_av.py --trim-tol 4: a 3.5 s overrun is within '
                                                             f'tolerance, cut to the sound ({d} s)')
    res['trim_tol_4'] = d
    rc, d, log = merge(tones[8], 'm_pad.mp4')
    check(rc == 0 and d is not None and abs(d - 8.0) < 0.15 and 'libx264' in log,
          f'merge_av.py: a 0.5 s gap within --tol 1.0 takes the pad path, re-encoded with $RENDER_CODEC libx264 '
          f'({d} s)')
    res['pad'] = d
    rc, d, _ = merge(tones[8], 'm_tol_refused.mp4', '--tol', '0.25')
    check(rc == 2 and d is None, f'merge_av.py --tol 0.25: the same 0.5 s gap is refused (exit {rc}, nothing '
                                 f'written)')
    res['tol_refused'] = rc
    RES['merge_options'] = res


def options_sheet(env):
    av = OUT / 'era_film_av.mp4'
    if not av.exists():
        check(False, f'{av.name} missing: run test_era_screens.py --only film first')
        return
    tl = json.loads(TIMELINE.read_text(encoding='utf-8'))
    t0, secs = FILM_T0, FILM_SECONDS
    sh = {'sections': [{'name': s['name'], 't0': s['t0'] - t0, 't1': s['t1'] - t0} for s in tl['sections']
                       if s['t1'] > t0 and s['t0'] < t0 + secs],
          'captions': [{'text': c['text'], 't0': c['t0'] - t0, 't1': c['t1'] - t0} for c in tl['captions']
                       if c['t1'] > t0 and c['t0'] < t0 + secs]}
    (WORK / 'film_timeline.json').write_text(json.dumps(sh), encoding='utf-8')
    names = {'verse1': 'verse 1 · the machines', 'vowels': 'the vowels'}
    out = WORK / 'sheet_options'
    for p in WORK.glob('sheet_options*.jpg'):
        p.unlink()
    r, dt = run([sys.executable, '-B', str(WT / 'contact_sheet.py'), str(av), '--every', '1', '--cols', '4', '--tile',
                 '320', '--parts', '2', '--timeline', str(WORK / 'film_timeline.json'), '--names', json.dumps(names),
                 '--title', 'DAISY verse 1 on the EEVEE wall',
                 '--synopsis', 'The Voder (1939) plays the wall until the second line, where Bell Labs (1961) takes '
                               'it: one era scene per lyric line, as the stage wall played them.',
                 '--out', str(out)], env)
    print('    ' + (r.stdout + r.stderr).strip().replace('\n', '\n    ')[-700:])
    files = [WORK / 'sheet_options.jpg', WORK / 'sheet_options_part1.jpg', WORK / 'sheet_options_part2.jpg']
    check(r.returncode == 0 and all(f.exists() for f in files),
          f'contact_sheet.py --parts 2 --names --synopsis: {[f.name for f in files if f.exists()]} ({dt:.1f} s)')
    RES['sheet_options'] = [str(f) for f in files if f.exists()]


def options_align(env):
    tl = json.loads(TIMELINE.read_text(encoding='utf-8'))
    wav = excerpt()
    ls = lines_in(tl, X0, X1 - 1.0)
    text = '\n'.join(c['text'] for c in ls)
    res = {}
    for tag, extra in (('method_align', ['--method', 'align']), ('chunk8_db24', ['--chunk-sec', '8', '--top-db', '24'])):
        out = WORK / f'lead_chorus1_aligned_{tag}.json'
        out.unlink(missing_ok=True)
        r, dt = run([sys.executable, '-B', str(WT / 'align_lyrics.py'), str(wav), text, '--model', 'medium',
                     '--output', str(out), *extra], env)
        ok = r.returncode == 0 and out.exists()
        got = json.loads(out.read_text(encoding='utf-8')) if out.exists() else []
        for g in got:
            print(f"    [{tag}] {g['text']!r:44s} start {g['start'] + X0:7.2f}  end {g['end'] + X0:7.2f}")
        starts = [round(g['start'] + X0, 2) for g in got]
        nearest = [min(abs(s - c['t0']) for c in ls) for s in starts]
        check(ok and got and max(nearest) < 1.0,
              f'align_lyrics.py {" ".join(extra)} (medium, CPU, {dt:.0f} s): {len(got)} of {len(ls)} lines, each '
              f'start within {max(nearest) if nearest else float("nan"):.2f} s of a line of the song')
        res[tag] = {'lines': len(got), 'texts': [g['text'] for g in got], 'starts': starts, 'seconds': dt}
    RES['align_options'] = res


def options_sapi():
    from voicebox import Sung, eras, write_wav
    from voicebox.util import transcribe, word_error_rate
    s = Sung(bpm=128)
    lyric = "Daisy Daisy give me your answer do"
    s.line(lyric, ["B4", "G#4", "E4", "B3", "C#4", "D#4", "E4", "C#4", "E4", "B3"],
           [2, 2, 2, 1.333, 0.667, 0.667, 0.667, 1.333, 0.667, 3.333], start_beat=1.0)
    t = time.time()
    try:
        y, _segs, _tracks = eras.sapi_2001(s)
    except Exception as e:  # noqa: BLE001
        check(False, f'voicebox eras.sapi_2001: {type(e).__name__}: {e}')
        return
    dt = time.time() - t
    p = WORK / 'daisy_line_sapi_2001.wav'
    write_wav(str(p), y, 48000)
    os.environ['CUDA_VISIBLE_DEVICES'] = ''                 # Whisper as the intelligibility meter, on the CPU
    hyp = transcribe(str(p), model='small', language='en')
    wer = word_error_rate(lyric, hyp)
    rms = float(np.sqrt(np.mean(np.square(y))))
    check(len(y) / 48000 > 3.0 and rms > 0.01, f'voicebox eras.sapi_2001 (Windows SAPI, Microsoft David): '
                                               f'{len(y) / 48000:.2f} s sung word by word, rms {rms:.3f} '
                                               f'({dt:.1f} s); Whisper small hears {hyp!r} (WER {wer:.2f})')
    RES['sapi_2001'] = {'seconds': len(y) / 48000, 'rms': rms, 'heard': hyp, 'wer': wer}


def options_daisy(env):
    r, dt = run([sys.executable, '-B', str(HERE / 'run_daisy.py'), 'captions', '--tag', '_upto_chorus2', '--preview'],
                env)
    print('    captions --preview: exit', r.returncode, (r.stdout + r.stderr).strip()[-300:])
    mp4 = DAISY / 'daisy_lyric_preview_upto_chorus2.mp4'
    d_mp4 = ffprobe_dur(mp4) if mp4.exists() else 0.0
    d_wav = ffprobe_dur(DAISY / 'daisy_master_upto_chorus2.wav')
    stills = []
    if mp4.exists():
        for t in (27.0, 80.0):
            png = WORK / f'daisy_lyric_preview_t{int(t)}.png'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', str(mp4), '-frames:v', '1', str(png)],
                           check=True)
            stills.append(png)
        mp4.unlink()                                       # regenerable, and the disk is shared: the stills stay
    check(r.returncode == 0 and abs(d_mp4 - d_wav) < 0.2 and len(stills) == 2,
          f'DAISY captions.py --preview: the CQT lyric video, {d_mp4:.1f} s for {d_wav:.1f} s of song ({dt:.0f} s; '
          f'stills {[p.name for p in stills]})')
    r, dt = run([sys.executable, '-B', str(HERE / 'run_daisy.py'), 'analyze', '--tag', '_upto_chorus2', '--asr',
                 '--sections', 'chorus1'], env)
    txt = r.stdout + r.stderr
    print('    analyze --asr --sections chorus1:\n    ' + txt.strip().replace('\n', '\n    ')[-2500:])
    import re
    m = re.search(r'\[chorus1\] mean WER in the mix ([0-9.]+) over (\d+) lines', txt)
    check(r.returncode == 0 and m is not None, f'DAISY analyze.py --asr --sections chorus1 (Whisper small, CPU, '
                                               f'{dt:.0f} s): mean WER in the mix '
                                               f'{m.group(1) if m else "?"} over {m.group(2) if m else "?"} lines')
    RES['daisy_options'] = {'preview_seconds': d_mp4, 'stills': [str(p) for p in stills],
                            'asr_chorus1_wer_mix': float(m.group(1)) if m else None}


def options():
    env = cpu_env()
    options_merge(env)
    options_sheet(env)
    options_sapi()
    options_daisy(env)
    options_align(env)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    check(TIMELINE.exists() and LEAD.exists(), 'DAISY master, stems and timeline present (run_daisy.py song)')
    for name, fn in (('quick', quick), ('lipsync', lipsync_probe), ('align', align_probe), ('cyborg', cyborg_probe),
                     ('probes', probes), ('daisy', daisy), ('merge', merge_guard), ('options', options)):
        if name in ONLY:
            fn()
    old = json.loads((WORK / 'tools_host.json').read_text(encoding='utf-8')) if (WORK / 'tools_host.json').exists() else {}
    old.update(RES)
    (WORK / 'tools_host.json').write_text(json.dumps(old, indent=1, default=float), encoding='utf-8')
    print(f'[tools_host] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
    sys.exit(1 if FAILS else 0)


main()
