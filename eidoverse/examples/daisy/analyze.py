"""Measure a render of the song, section by section (we can't listen, so we look).

    python eidoverse/examples/daisy/analyze.py [--tag _upto_chorus1] [--asr] [--sections verse1,chorus1]

Per section: loudness (LUFS) of each stem and of the mix, the lead-over-backing margin,
the spectral balance of the mix (low / mid / presence / air), peaks; with --asr, what
Whisper hears in the vocals alone and in the full mix (no prompt: a lyric prompt makes it
echo). Writes a spectrogram PNG per section into work/daisy/out/analysis/.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent
while ROOT != ROOT.parent and not (ROOT / 'eido.py').exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'work' / 'daisy' / 'out'


def lufs(x, sr, meter):
    if x.shape[0] < sr * 0.5 or np.max(np.abs(x)) < 1e-6:
        return -99.0
    v = meter.integrated_loudness(x)
    return -99.0 if not np.isfinite(v) else v


def bands(x, sr):
    m = x.mean(axis=1)
    S = np.abs(np.fft.rfft(m * np.hanning(len(m)))) ** 2
    f = np.fft.rfftfreq(len(m), 1 / sr)
    tot = S.sum() + 1e-20
    out = {}
    for name, a, b in [('sub', 20, 60), ('low', 60, 250), ('mid', 250, 2000), ('pres', 2000, 6000), ('air', 6000, 16000)]:
        out[name] = 10 * np.log10(S[(f >= a) & (f < b)].sum() / tot + 1e-12)
    return out


def main():
    import pyloudnorm as pyln
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='')
    ap.add_argument('--asr', action='store_true')
    ap.add_argument('--sections', default='')
    a = ap.parse_args()
    tl = json.loads((OUT / f'daisy_timeline{a.tag}.json').read_text(encoding='utf-8'))
    mix, sr = sf.read(OUT / f'daisy_master{a.tag}.wav')
    stems = {k: sf.read(OUT / 'stems' / f'{k}{a.tag}.wav')[0] for k in ('backing', 'lead', 'eras', 'choir', 'fx')}
    meter = pyln.Meter(sr)
    (OUT / 'analysis').mkdir(exist_ok=True)
    want = set(a.sections.split(',')) if a.sections else None
    print(f"mix: {mix.shape[0] / sr:.1f}s  integrated {lufs(mix, sr, meter):.1f} LUFS  peak {20 * np.log10(np.abs(mix).max()):.2f} dBFS")
    print(f"{'section':10s} {'mix':>6s} {'back':>6s} {'lead':>6s} {'eras':>6s} {'choir':>6s} {'fx':>6s}  voc-back  | sub   low   mid  pres  air")
    from voicebox.util import spectrogram_png
    for sec in tl['sections']:
        if want and sec['name'] not in want:
            continue
        i0, i1 = int(sec['t0'] * sr), int(sec['t1'] * sr)
        row = {k: lufs(v[i0:i1], sr, meter) for k, v in stems.items()}
        m = lufs(mix[i0:i1], sr, meter)
        voc = stems['lead'][i0:i1] + stems['eras'][i0:i1]
        vl = lufs(voc, sr, meter)
        bb = bands(mix[i0:i1], sr)
        print(f"{sec['name']:10s} {m:6.1f} {row['backing']:6.1f} {row['lead']:6.1f} {row['eras']:6.1f} {row['choir']:6.1f} "
              f"{row['fx']:6.1f}  {vl - row['backing']:+6.1f}   | {bb['sub']:5.1f} {bb['low']:5.1f} {bb['mid']:5.1f} "
              f"{bb['pres']:5.1f} {bb['air']:5.1f}")
        spectrogram_png(mix[i0:i1].mean(axis=1), sr, OUT / 'analysis' / f"{sec['name']}{a.tag}.png",
                        title=f"{sec['name']} ({sec['t0']:.1f}–{sec['t1']:.1f}s)", fmax=8000)
    if a.asr:
        # one caption line at a time (whole sections make Whisper loop): WER in the MIX, and of the vocals alone
        import re
        import tempfile
        from voicebox.util import transcribe, word_error_rate
        tmp = Path(tempfile.gettempdir())
        voc_all = stems['lead'] + stems['eras'] + stems['choir']
        per = {}
        for c in tl['captions']:
            sec = next((x['name'] for x in tl['sections'] if x['t0'] - 0.5 <= c['t0'] < x['t1']), '?')
            if want and sec not in want:
                continue
            ref = re.sub(r'\{[^}]*\}', '', c['text']).replace('—', ' ').strip()
            if not ref or ref.startswith('('):
                continue
            i0, i1 = int(max(0, c['t0'] - 0.25) * sr), int((c['t1'] + 0.35) * sr)
            res = []
            for label, x in (('mix', mix[i0:i1]), ('voc', voc_all[i0:i1])):
                pth = tmp / f'daisy_asr_{label}.wav'
                y = np.concatenate([np.zeros(sr // 4), x.mean(axis=1), np.zeros(sr // 2)])
                sf.write(pth, y / (np.abs(y).max() + 1e-9) * 0.9, sr)
                hyp = transcribe(str(pth), model='small', language='en')
                res.append((min(1.5, word_error_rate(ref, hyp)), hyp))
            per.setdefault(sec, []).append(res[0][0])
            print(f"{sec:9s} mix {res[0][0]:.2f} voc {res[1][0]:.2f} | {ref}  ->  {res[0][1]}", flush=True)
        for sec, ws in per.items():
            print(f"[{sec}] mean WER in the mix {np.mean(ws):.2f} over {len(ws)} lines")


if __name__ == '__main__':
    main()
