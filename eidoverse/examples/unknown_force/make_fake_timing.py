"""Fake (but near-real) lyric timing for the parole captions, until the real alignment arrives.

    python eidoverse/examples/unknown_force/make_fake_timing.py      # from the repo root, after transcribe_raw.py
    -> work/unknown_force/props/parole_timing_fake.json        (the film's final cut used this timing)

The LYRICS.md words are aligned (global DP, fuzzy word match) to the raw Whisper words of the vocal stem
(analysis/raw_transcript.json); a matched word takes Whisper's time, an unmatched one is spread between its
matched neighbours by letter count. Whisper's mishearings ("heart" for "odds", "this war" for "swore", "bend" for
"bin") still land on the right times because the alignment walks both sequences in order. The break-1 echo of
"Could you turn it down?" (109.2 s) is sung but is not in LYRICS.md; it is added as its own line.

Output: [{text, start, end, section, words:[{w, s, e}]}]  (the shape parole.js takes)
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'eido.py').exists())
WORK = ROOT / 'work' / 'unknown_force'            # the film's data and outputs (git-ignored)
LYR = (HERE / 'LYRICS.md').read_text(encoding='utf-8')
RAW = json.loads((WORK / 'analysis' / 'raw_transcript.json').read_text(encoding='utf-8'))


def norm(w):
    return re.sub(r"[^a-z0-9']", '', w.lower().replace('’', "'"))


# 1. lyric lines with sections
lines, section = [], None
for raw in LYR.splitlines():
    s = raw.strip()
    if not s or s.startswith('#'):
        continue
    m = re.match(r'\[(.+)\]', s)
    if m:
        section = m.group(1).lower().replace(' ', '_').replace('-', '')
        continue
    lines.append({'text': s.replace(' — ', ' — '), 'section': section})
# the chorus sections repeat: number them
counts = {}
for ln in lines:
    pass
sec_seen, last = {}, None
for ln in lines:
    if ln['section'] != last:
        sec_seen[ln['section']] = sec_seen.get(ln['section'], 0) + 1
        last = ln['section']
    k = sec_seen[ln['section']]
    ln['section'] = ln['section'] + (str(k) if ln['section'] in ('chorus', 'prechorus') else '')

# the break-1 echo, sung but not written: insert after chorus 1's last line
echo_at = next(i for i, l in enumerate(lines) if l['section'] == 'chorus1' and l['text'].lower().startswith('could you'))
lines.insert(echo_at + 1, {'text': 'Could you turn it down?', 'section': 'instrumental_break', 'echo': True})

# 2. token streams
lyr_tok = []                     # (line index, word as written)
for li, ln in enumerate(lines):
    for w in ln['text'].replace('—', ' ').split():
        if norm(w):
            lyr_tok.append((li, w))
wh = [w for seg in RAW for w in seg['words'] if norm(w['w'])]


def sim(a, b):
    a, b = norm(a), norm(b)
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# 3. global alignment (Needleman-Wunsch, similarity score, gaps cost)
n, m = len(lyr_tok), len(wh)
GAP = -0.45
S = [[0.0] * (m + 1) for _ in range(n + 1)]
P = [[0] * (m + 1) for _ in range(n + 1)]
for i in range(1, n + 1):
    S[i][0], P[i][0] = S[i - 1][0] + GAP, 1
for j in range(1, m + 1):
    S[0][j], P[0][j] = S[0][j - 1] + GAP * 0.6, 2
for i in range(1, n + 1):
    for j in range(1, m + 1):
        sc = sim(lyr_tok[i - 1][1], wh[j - 1]['w'])
        d = S[i - 1][j - 1] + (sc * 2.0 - 0.9)
        u = S[i - 1][j] + GAP
        l = S[i][j - 1] + GAP * 0.6      # Whisper's extra words (repeats, "toaster" twice) are cheap to skip
        best = max(d, u, l)
        S[i][j], P[i][j] = best, (0 if best == d else 1 if best == u else 2)
i, j, match = n, m, {}
while i > 0 and j > 0:
    p = P[i][j]
    if p == 0:
        if sim(lyr_tok[i - 1][1], wh[j - 1]['w']) >= 0.34:
            match[i - 1] = wh[j - 1]
        i, j = i - 1, j - 1
    elif p == 1:
        i -= 1
    else:
        j -= 1

# 4. times: matched words from Whisper, the rest spread by letters between matched neighbours (within the line)
times = [None] * n
for k, w in match.items():
    s, e = float(w['s']), float(w['e'])
    if e - s < 0.08:
        e = s + 0.18
    times[k] = [s, e]
for li in range(len(lines)):
    idx = [k for k in range(n) if lyr_tok[k][0] == li]
    if not idx:
        continue
    if all(times[k] is None for k in idx):
        raise SystemExit(f'line {li} "{lines[li]["text"]}" matched nothing')
    k = 0
    while k < len(idx):
        if times[idx[k]] is not None:
            k += 1
            continue
        a = k
        while k < len(idx) and times[idx[k]] is None:
            k += 1
        b = k
        t0 = times[idx[a - 1]][1] if a > 0 else times[idx[b]][0] - 0.28 * (b - a)
        t1 = times[idx[b]][0] if b < len(idx) else times[idx[a - 1]][1] + 0.3 * (b - a)
        if t1 < t0 + 0.12 * (b - a):
            t1 = t0 + 0.12 * (b - a)
        lens = [max(2, len(norm(lyr_tok[idx[q]][1]))) for q in range(a, b)]
        tot, acc = float(sum(lens)), t0
        for q, L in zip(range(a, b), lens):
            d = (t1 - t0) * L / tot
            times[idx[q]] = [acc, acc + d]
            acc += d
    # monotone + no overlap inside the line
    prev = -1.0
    for q in idx:
        s, e = times[q]
        s = max(s, prev)
        e = max(e, s + 0.1)
        times[q] = [s, e]
        prev = s + 0.04

out = []
for li, ln in enumerate(lines):
    idx = [k for k in range(n) if lyr_tok[k][0] == li]
    words = [{'w': lyr_tok[k][1], 's': round(times[k][0], 3), 'e': round(times[k][1], 3)} for k in idx]
    rec = {'text': ln['text'], 'start': words[0]['s'], 'end': words[-1]['e'], 'section': ln['section'], 'words': words}
    if ln.get('echo'):
        rec['echo'] = True
    out.append(rec)
# lines must not start before the previous ends minus a little (Whisper occasionally merges two)
for a, b in zip(out, out[1:]):
    if b['start'] < a['start']:
        raise SystemExit(f'order broken at "{b["text"]}"')

dst = WORK / 'props' / 'parole_timing_fake.json'
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps({'note': 'FAKE timing: LYRICS.md aligned to raw Whisper words (make_fake_timing.py). '
                                   'Replace with the real alignment.', 'lines': out}, indent=1), encoding='utf-8')
for i, l in enumerate(out):
    print(f"{i:2d} {l['start']:7.2f}-{l['end']:7.2f} {l['section']:20s} {l['text']}")
print(f'wrote {dst.name}: {len(out)} lines, {sum(len(l["words"]) for l in out)} words, matched {len(match)}/{n}')
