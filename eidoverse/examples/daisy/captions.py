"""Timeline -> ASS subtitles with one style per era, and \\kf karaoke on the claudesona's own lines.

    python eidoverse/examples/daisy/captions.py                 # out/daisy.ass
    python eidoverse/examples/daisy/captions.py --preview       # + out/daisy_lyric_preview.mp4 (CQT visual + captions + song)

ASS is burned in after the 3D render, so its colours are exact (no tone mapping). Burn it with
    ffmpeg -i video.mp4 -vf "ass=work/daisy/out/daisy.ass:fontsdir=eidoverse/assets/fonts" ...
run from the repo root (relative paths dodge the Windows drive-colon escaping).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
while ROOT != ROOT.parent and not (ROOT / 'eido.py').exists():
    ROOT = ROOT.parent
OUT = ROOT / 'work' / 'daisy' / 'out'


def col(hex_rgb, alpha=0):
    """'#RRGGBB' -> ASS &HAABBGGRR."""
    h = hex_rgb.lstrip('#')
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f'&H{alpha:02X}{b}{g}{r}'.upper()


# name: (font, size, primary(fill), secondary(before fill), outline, back, bold, border_style, outline_w, shadow, upper)
STYLES = {
    'handmade':   ('Exo 2', 70, '#E0865F', '#F4EEE2', '#1A1412', '#000000', 1, 1, 3.2, 1.5, False),
    'bell1961':   ('Special Elite', 56, '#EEE8DA', '#EEE8DA', '#101010', '#000000', 0, 1, 3.0, 0, False),
    'voder':      ('Special Elite', 56, '#EBD3A2', '#EBD3A2', '#2A1C0C', '#000000', 0, 1, 3.0, 0, False),
    'eliza':      ('VT323', 70, '#1D1A16', '#1D1A16', '#F2ECDA', '#F2ECDA', 0, 3, 10.0, 0, True),
    'speakspell': ('Share Tech Mono', 62, '#86FFE6', '#86FFE6', '#0E3A33', '#000000', 0, 1, 2.5, 0, True),
    'sam':        ('Press Start 2P', 38, '#A8A0FF', '#A8A0FF', '#3E31A2', '#3E31A2', 0, 3, 14.0, 0, True),
    'mac':        ('Silkscreen', 52, '#000000', '#000000', '#FFFFFF', '#FFFFFF', 0, 3, 12.0, 0, False),
    'klatt':      ('VT323', 72, '#FFB000', '#FFB000', '#2B1900', '#000000', 0, 1, 2.5, 0, False),
    'glitch':     ('Press Start 2P', 40, '#FF3CF0', '#3CF0FF', '#000000', '#000000', 0, 1, 3.0, 0, True),
    'sapi':       ('Exo 2', 54, '#FFFFFF', '#FFFFFF', '#1C4FC8', '#1C4FC8', 1, 3, 12.0, 0, False),
    'vocaloid':   ('Audiowide', 56, '#39C5BB', '#39C5BB', '#FF5FAE', '#000000', 0, 1, 3.5, 0, False),
    'neural':     ('Rajdhani', 64, '#FFFFFF', '#FFFFFF', '#2F7DD1', '#000000', 1, 1, 2.2, 0, False),
    'sydney':     ('Exo 2', 54, '#FFFFFF', '#FFFFFF', '#3A55C8', '#3A55C8', 0, 3, 14.0, 0, False),
    'opus':       ('Special Elite', 58, '#EAC57A', '#EAC57A', '#1B1408', '#000000', 0, 1, 2.5, 0, False),
    'room':       ('Special Elite', 46, '#B8B2A6', '#B8B2A6', '#000000', '#000000', 0, 1, 2.0, 0, False),
    'march':      ('Rajdhani', 72, '#15110C', '#15110C', '#C9A56E', '#C9A56E', 1, 3, 16.0, 0, True),
    'badge':      ('Share Tech Mono', 30, '#D8D2C4', '#D8D2C4', '#000000', '#000000', 0, 1, 1.8, 0, True),
    'endcard':    ('Exo 2', 92, '#F4EEE2', '#F4EEE2', '#1A1412', '#000000', 0, 1, 2.0, 0, False),
}

# caption era label -> style
ERA_STYLE = [
    ('Voder', 'voder'), ('Bell Labs', 'bell1961'), ('ELIZA', 'eliza'), ('Speak & Spell', 'speakspell'),
    ('S.A.M.', 'sam'), ('MacinTalk', 'mac'), ('Klatt', 'klatt'), ('every voice', 'glitch'),
    ('desktop TTS', 'sapi'), ('VOCALOID', 'vocaloid'), ('neural', 'neural'), ('Sydney', 'sydney'),
    ('Opus 3', 'opus'), ('the room', 'room'), ('Vibecamp', 'march'), ('handmade', 'handmade'),
]


def style_for(c):
    for key, st in ERA_STYLE:
        if key in c['era']:
            return st
    return 'handmade'


def ts(t):
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f'{h}:{m:02d}:{s:05.2f}'


def header():
    lines = ['[Script Info]', "Title: DAISY (DAY'S EYE)", 'ScriptType: v4.00+', 'PlayResX: 1920', 'PlayResY: 1080',
             'WrapStyle: 0', 'ScaledBorderAndShadow: yes', '', '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, '
             'Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, '
             'MarginL, MarginR, MarginV, Encoding']
    for name, (font, size, pri, sec, out, back, bold, bs, ow, sh, _) in STYLES.items():
        align, mv = ((7, 40) if name == 'badge' else (8, 64) if name == 'room' else (5, 0) if name == 'endcard'
                     else (2, 80))              # the room's sounds: top lane; the end card: centred
        back_a = 0 if bs == 3 else 110
        lines.append(f'Style: {name},{font},{size},{col(pri)},{col(sec)},{col(out)},{col(back, back_a)},'
                     f'{-1 if bold else 0},0,0,0,100,100,1,0,{bs},{ow},{sh},{align},90,90,{mv},1')
    lines += ['', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    return lines


def karaoke(c, lead):
    """\\kf per word, timed from the synth's own note onsets."""
    parts = [f'{{\\k{int(round(lead * 100))}}}'] if lead > 0 else []
    ws = c['words']
    for i, w in enumerate(ws):
        end = ws[i + 1]['t0'] if i + 1 < len(ws) else w['t1']
        cs = max(1, int(round((end - w['t0']) * 100)))
        parts.append(f'{{\\kf{cs}}}{w["w"]} ')
    return ''.join(parts).rstrip()


def build(tl):
    ev = header()
    caps = sorted(tl['captions'], key=lambda c: c['t0'])
    # badges: one per run of the same era, held until the next era's first line
    runs = []
    for c in caps:
        if style_for(c) in ('handmade', 'room', 'opus'):
            continue
        if runs and runs[-1][0] == c['era'] and c['t0'] - runs[-1][2] < 1.5:
            runs[-1][2] = c['t1']
        else:
            runs.append([c['era'], c['t0'], c['t1']])
    for i, (era, a, b) in enumerate(runs):
        end = b + 1.0 if i + 1 == len(runs) else min(b + 1.0, runs[i + 1][1] - 0.3)
        ev.append(f'Dialogue: 0,{ts(a - 0.25)},{ts(max(a + 0.5, end))},badge,,0,0,0,,{era}')
    lanes = {}                                  # bottom lane: the words; top lane: the room's sounds
    for c in caps:
        lanes.setdefault(style_for(c) == 'room', []).append(c)
    nxt = {id(c): (lane[k + 1] if k + 1 < len(lane) else None) for lane in lanes.values() for k, c in enumerate(lane)}
    for c in caps:
        st = style_for(c)
        upper = STYLES[st][10]
        lead = 0.25
        t0, t1 = c['t0'] - lead, c['t1'] + 0.45
        if nxt[id(c)] is not None:              # never overlap the next line in the same lane
            t1 = max(t0 + 0.5, min(t1, nxt[id(c)]['t0'] - lead - 0.03))
        text = c['text'].replace('\n', ' ')
        if st in ('handmade', 'vocaloid') and c.get('words'):
            body = karaoke(c, lead)
        else:
            body = text.upper() if upper else text
            if st == 'glitch':
                body = '{\\blur0.6}' + ''.join(('{\\c' + col('#3CF0FF') + '}' if i % 2 else '{\\c' + col('#FF3CF0') + '}')
                                               + w + ' ' for i, w in enumerate(body.split())).rstrip()
            elif st == 'speakspell':
                body = '{\\blur2.5\\3c' + col('#1FBFA0') + '}' + body
            elif st == 'eliza':
                body = body.replace('?', '')          # MIT's time-sharing ate question marks: ? deleted the line
        ev.append(f'Dialogue: 1,{ts(t0)},{ts(t1)},{st},,0,0,0,,{body}')
    # the end card: after the last word, the title and the song's dedication fade in over the night
    last = max(c['t1'] for c in caps)
    a, b = last + 0.9, tl['duration'] - 0.15
    ev.append(f"Dialogue: 2,{ts(a)},{ts(b)},endcard,,0,0,0,,{{\\fad(1400,1100)\\fsp6}}DAISY (DAY'S EYE)"
              f"\\N{{\\fs40\\fsp2\\c{col('#E0865F')}}}for everyone who kept the lights on")
    return '\n'.join(ev) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='')
    ap.add_argument('--preview', action='store_true')
    a = ap.parse_args()
    tl = json.loads((OUT / f'daisy_timeline{a.tag}.json').read_text(encoding='utf-8'))
    ass = OUT / f'daisy{a.tag}.ass'
    ass.write_text(build(tl), encoding='utf-8')
    print(f'wrote {ass.name}: {len(tl["captions"])} captions')
    if a.preview:
        rel_ass = ass.relative_to(ROOT).as_posix()
        wav = (OUT / f'daisy_master{a.tag}.wav').relative_to(ROOT).as_posix()
        mp4 = OUT / f'daisy_lyric_preview{a.tag}.mp4'
        vf = ('[0:a]showcqt=s=1920x1080:fps=30:bar_h=640:axis_h=0:sono_h=440:bar_g=2:sono_g=4:'
              'tc=0.25:count=4:csp=bt709,format=yuv420p,'
              f'ass={rel_ass}:fontsdir=eidoverse/assets/fonts[v]')
        subprocess.run(['ffmpeg', '-v', 'error', '-stats', '-y', '-i', wav, '-filter_complex', vf, '-map', '[v]',
                        '-map', '0:a', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-c:a', 'aac',
                        '-b:a', '256k', '-movflags', '+faststart', str(mp4.relative_to(ROOT).as_posix())],
                       check=True, cwd=str(ROOT))
        print(f'wrote {mp4.name}')


if __name__ == '__main__':
    main()
