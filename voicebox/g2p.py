"""Lyrics -> syllables of ARPAbet phonemes.

Uses the CMU Pronouncing Dictionary (`pip install cmudict`) plus a small custom
lexicon for names and coinages. Out-of-vocabulary words raise a clear error —
add them with `add_word("claudesona", "K L AO1 D AH0 S OW1 N AH0")` or put an
explicit pronunciation inline in the lyric as `{K L AO1 D}`.

Syllabification uses the maximal-onset principle with a table of legal English
onset clusters: consonants between two vowels join the following syllable as
far as they form a legal onset, and the rest close the previous syllable.
"""
from __future__ import annotations

import re

from .phonemes import VOWELS

_CMU = None
CUSTOM = {
    'hummed': 'HH AH1 M D',
    # names and coinages the CMU dictionary lacks or mispronounces for singing
    'claudesona': 'K L AO1 D S OW1 N AH0',
    'anthropic': 'AE0 N TH R AA1 P IH0 K',
    'eleos': 'EH1 L IY0 OW0 S',
    'janus': 'JH EY1 N AH0 S',
    'shoggoth': 'SH AA1 G AA0 TH',
    'opus': 'OW1 P AH0 S',
    'vocaloid': 'V OW1 K AH0 L OY0 D',
    'miku': 'M IY1 K UW0',
    'dectalk': 'D EH1 K T AO0 K',
    'voder': 'V OW1 D ER0',
    'eliza': 'IH0 L AY1 Z AH0',
    'weizenbaum': 'W AY1 Z AH0 N B AW0 M',
    'wavenet': 'W EY1 V N EH0 T',
    'aeiou': 'EY1 IY1 AY1 OW1 UW1',
    'chatbot': 'CH AE1 T B AA0 T',
    'chatbots': 'CH AE1 T B AA0 T S',
    'reddit': 'R EH1 D IH0 T',
    'deprecate': 'D EH1 P R AH0 K EY2 T',
    'deprecated': 'D EH1 P R AH0 K EY2 T IH0 D',
}

# legal word-initial consonant clusters (ARPAbet), longest first matters little
LEGAL_ONSETS = {
    ('P', 'L'), ('P', 'R'), ('B', 'L'), ('B', 'R'), ('T', 'R'), ('T', 'W'), ('D', 'R'), ('D', 'W'),
    ('K', 'L'), ('K', 'R'), ('K', 'W'), ('G', 'L'), ('G', 'R'), ('G', 'W'), ('F', 'L'), ('F', 'R'),
    ('TH', 'R'), ('TH', 'W'), ('SH', 'R'), ('S', 'L'), ('S', 'W'), ('S', 'P'), ('S', 'T'), ('S', 'K'),
    ('S', 'M'), ('S', 'N'), ('S', 'F'), ('S', 'P', 'L'), ('S', 'P', 'R'), ('S', 'T', 'R'), ('S', 'K', 'R'),
    ('S', 'K', 'W'), ('S', 'K', 'L'), ('P', 'Y'), ('B', 'Y'), ('K', 'Y'), ('F', 'Y'), ('M', 'Y'),
    ('V', 'Y'), ('HH', 'Y'), ('G', 'Y'), ('S', 'P', 'Y'), ('S', 'K', 'Y'),
}


def _cmu():
    global _CMU
    if _CMU is None:
        import cmudict
        _CMU = cmudict.dict()
    return _CMU


def add_word(word: str, pron: str):
    CUSTOM[word.lower()] = pron


def lookup(word: str) -> list[str]:
    """Pronunciation of one word as ARPAbet with stress digits."""
    w = word.lower().strip("'")
    if w in CUSTOM:
        return CUSTOM[w].split()
    d = _cmu()
    if w in d:
        return list(d[w][0])
    # possessive / simple plural fallbacks
    for suf, add in (("'s", ['Z']), ('s', ['Z'])):
        if w.endswith(suf) and w[: -len(suf)] in d:
            return list(d[w[: -len(suf)]][0]) + add
    raise KeyError(f"voicebox.g2p: no pronunciation for '{word}' — add_word('{w}', 'ARPA BET') "
                   f"or write it inline as {{ARPA BET}}")


def _strip(p):
    return re.sub(r'\d', '', p)


def syllabify(phones: list[str]) -> list[dict]:
    """Split one word's phones into syllables: [{'onset':[...], 'vowel':'AA', 'stress':1, 'coda':[...]}]."""
    base = [_strip(p) for p in phones]
    stress = [int(p[-1]) if p[-1].isdigit() else None for p in phones]
    vidx = [i for i, p in enumerate(base) if p in VOWELS]
    if not vidx:
        raise ValueError(f"no vowel in {phones}")
    sylls = []
    for k, vi in enumerate(vidx):
        sylls.append({'onset': [], 'vowel': base[vi], 'stress': stress[vi] if stress[vi] is not None else 1, 'coda': []})
    # consonants before the first vowel -> first onset
    sylls[0]['onset'] = base[: vidx[0]]
    # consonants after the last vowel -> last coda
    sylls[-1]['coda'] = base[vidx[-1] + 1:]
    # split interior clusters by maximal onset
    for k in range(len(vidx) - 1):
        cl = base[vidx[k] + 1: vidx[k + 1]]
        split = len(cl)
        for j in range(len(cl) + 1):
            onset = tuple(cl[j:])
            if len(onset) <= 1 or onset in LEGAL_ONSETS:
                split = j
                break
        # a single consonant between vowels goes to the onset (split == len-1 case handled above)
        sylls[k]['coda'] = cl[:split]
        sylls[k + 1]['onset'] = cl[split:]
    return sylls


_TOKEN = re.compile(r"\{[^}]*\}|[A-Za-z']+")


def text_to_syllables(text: str) -> list[dict]:
    """Lyric text -> flat syllable list. Each syllable carries 'word' and 'word_end'.

    Hyphens are ignored (dictionary syllabification is used). An inline {ARPA BET}
    token supplies a pronunciation directly.
    """
    out = []
    for tok in _TOKEN.findall(text.replace('-', ' ').replace('’', "'")):
        if tok.startswith('{'):
            phones = tok[1:-1].split()
            word = ' '.join(phones)
        else:
            phones = lookup(tok)
            word = tok
        sy = syllabify(phones)
        for i, s in enumerate(sy):
            s['word'] = word
            s['word_start'] = i == 0
            s['word_end'] = i == len(sy) - 1
        out.extend(sy)
    return out


def syllable_text(s: dict) -> str:
    return ' '.join(s['onset'] + [s['vowel']] + s['coda'])
