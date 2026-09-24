"""Phoneme inventory and acoustic targets for the voicebox formant synthesizer.

ARPAbet symbols (the CMU Pronouncing Dictionary's set). Vowel formant targets
are the Peterson & Barney (1952) averages for adult male and adult female
speakers; a voice's `vtl` (vocal-tract scale, 0 = male averages, 1 = female
averages, beyond 1 = smaller/brighter) interpolates and extrapolates between
them. Consonant targets follow the conventions of Klatt's (1980) cascade/
parallel synthesizer: formant loci for place of articulation, a nasal pole/zero
pair for nasals, and a separate frication spectrum for noise sources.

All frequencies in Hz, levels in dB relative to a full vowel.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- vowels ---------------------------------------------------------------
# (F1, F2, F3) — Peterson & Barney 1952 means.
VOWEL_MALE = {
    'IY': (270, 2290, 3010), 'IH': (390, 1990, 2550), 'EH': (530, 1840, 2480),
    'AE': (660, 1720, 2410), 'AA': (730, 1090, 2440), 'AO': (570, 840, 2410),
    'UH': (440, 1020, 2240), 'UW': (300, 870, 2240), 'AH': (640, 1190, 2390),
    'ER': (490, 1350, 1690), 'AX': (500, 1400, 2450), 'OH': (470, 900, 2400),
    'NM': (280, 1000, 2200),   # nasal murmur: a hummed 'mm' used as a syllable nucleus
}
VOWEL_FEMALE = {
    'IY': (310, 2790, 3310), 'IH': (430, 2480, 3070), 'EH': (610, 2330, 2990),
    'AE': (860, 2050, 2850), 'AA': (850, 1220, 2810), 'AO': (590, 920, 2710),
    'UH': (470, 1160, 2680), 'UW': (370, 950, 2670), 'AH': (760, 1400, 2780),
    'ER': (500, 1640, 1960), 'AX': (550, 1650, 2800), 'OH': (510, 1000, 2700),
    'NM': (300, 1150, 2500),
}
# diphthongs: (start vowel, end vowel, fraction of the vowel spent before gliding)
DIPHTHONGS = {
    'AY': ('AA', 'IH', 0.55), 'EY': ('EH', 'IY', 0.55), 'OW': ('OH', 'UH', 0.45),
    'AW': ('AA', 'UH', 0.55), 'OY': ('AO', 'IH', 0.55),
}
# higher formants (male, female) — F4, F5, F6
HIGH_FORMANTS = {'male': (3350, 3900, 4900), 'female': (4100, 4700, 5600)}

VOWELS = set(VOWEL_MALE) | set(DIPHTHONGS)


def lerp(a, b, t):
    return a + (b - a) * t


def vowel_formants(v: str, vtl: float):
    """(F1..F6) for monophthong v at vocal-tract scale vtl (0 male, 1 female)."""
    m, f = VOWEL_MALE[v], VOWEL_FEMALE[v]
    hm, hf = HIGH_FORMANTS['male'], HIGH_FORMANTS['female']
    return tuple(lerp(a, b, vtl) for a, b in zip(m + hm, f + hf))


# --- consonants -------------------------------------------------------------
@dataclass
class Consonant:
    kind: str                      # stop | fricative | affricate | nasal | liquid | glide | aspirate
    voiced: bool
    place: str                     # labial | labiodental | dental | alveolar | postalveolar | palatal | velar | glottal
    formants: tuple | None = None  # (F1, F2, F3) male targets during the constriction; None = follow neighbours
    dur: float = 0.07              # default duration in seconds (at speaking rate 1)
    nasal: tuple | None = None     # (FNP, FNZ) nasal pole / zero
    fric: list = field(default_factory=list)  # [(centre Hz, bandwidth Hz, level dB)] frication spectrum (male)
    fric_level: float = -60.0      # overall frication level dB re vowel (-60 = none)
    burst: list = field(default_factory=list) # stop release burst spectrum
    burst_level: float = -60.0
    vot: float = 0.0               # voice-onset time (aspiration after release), seconds
    av_level: float = 0.0          # voicing level during the consonant, dB re vowel (-60 = unvoiced)


# F2/F3 loci for stop and nasal places (male); velar is vowel-dependent (see velar_locus)
LOCI = {'labial': (800, 2200), 'labiodental': (1100, 2200), 'dental': (1400, 2600),
        'alveolar': (1700, 2650), 'postalveolar': (1900, 2600), 'palatal': (2100, 2800)}

S_SPEC = [(5300, 1300, 0.0), (7600, 2400, -4.0)]
SH_SPEC = [(2600, 500, 0.0), (3600, 1000, -3.0), (5600, 2600, -9.0)]
F_SPEC = [(1800, 3500, -6.0), (6500, 4000, -2.0)]
TH_SPEC = [(2400, 3500, -4.0), (6000, 4000, -3.0)]

CONSONANTS = {
    # stops: closure dur; burst + aspiration added at release
    'P': Consonant('stop', False, 'labial', dur=0.075, burst=[(900, 1400, 0.0), (3000, 4000, -8.0)], burst_level=-13, vot=0.055, av_level=-60),
    'B': Consonant('stop', True, 'labial', dur=0.06, burst=[(900, 1400, 0.0), (3000, 4000, -8.0)], burst_level=-24, vot=0.0, av_level=-22),
    'T': Consonant('stop', False, 'alveolar', dur=0.065, burst=[(4600, 2000, 0.0), (6800, 3000, -1.0)], burst_level=-6, vot=0.06, av_level=-60),
    'D': Consonant('stop', True, 'alveolar', dur=0.05, burst=[(4600, 2000, 0.0), (6800, 3000, -1.0)], burst_level=-13, vot=0.0, av_level=-22),
    'K': Consonant('stop', False, 'velar', dur=0.07, burst=[(2200, 700, 0.0), (3500, 1600, -8.0)], burst_level=-9, vot=0.07, av_level=-60),
    'G': Consonant('stop', True, 'velar', dur=0.055, burst=[(2200, 700, 0.0), (3500, 1600, -8.0)], burst_level=-15, vot=0.0, av_level=-22),
    # affricates = stop closure + postalveolar frication
    'CH': Consonant('affricate', False, 'postalveolar', dur=0.12, fric=SH_SPEC, fric_level=-6, burst=[(3000, 1500, 0.0)], burst_level=-14, av_level=-60),
    'JH': Consonant('affricate', True, 'postalveolar', dur=0.1, fric=SH_SPEC, fric_level=-11, burst=[(3000, 1500, 0.0)], burst_level=-20, av_level=-14),
    # fricatives
    'F': Consonant('fricative', False, 'labiodental', (400, 1100, 2080), dur=0.095, fric=F_SPEC, fric_level=-20, av_level=-60),
    'V': Consonant('fricative', True, 'labiodental', (380, 1100, 2080), dur=0.07, fric=F_SPEC, fric_level=-24, av_level=-8),
    'TH': Consonant('fricative', False, 'dental', (400, 1290, 2540), dur=0.095, fric=TH_SPEC, fric_level=-21, av_level=-60),
    'DH': Consonant('fricative', True, 'dental', (380, 1290, 2540), dur=0.055, fric=TH_SPEC, fric_level=-24, av_level=-8),
    'S': Consonant('fricative', False, 'alveolar', (420, 1390, 2530), dur=0.105, fric=S_SPEC, fric_level=-11, av_level=-60),
    'Z': Consonant('fricative', True, 'alveolar', (400, 1390, 2530), dur=0.08, fric=S_SPEC, fric_level=-12, av_level=-14),
    'SH': Consonant('fricative', False, 'postalveolar', (400, 1840, 2750), dur=0.105, fric=SH_SPEC, fric_level=-9, av_level=-60),
    'ZH': Consonant('fricative', True, 'postalveolar', (380, 1840, 2750), dur=0.08, fric=SH_SPEC, fric_level=-12, av_level=-14),
    'HH': Consonant('aspirate', False, 'glottal', None, dur=0.08, av_level=-60),
    # sonorants
    'M': Consonant('nasal', True, 'labial', (280, 1000, 2200), dur=0.075, nasal=(260, 950), av_level=-4),
    'N': Consonant('nasal', True, 'alveolar', (280, 1600, 2600), dur=0.07, nasal=(260, 1650), av_level=-4),
    'NG': Consonant('nasal', True, 'velar', (280, 2000, 2600), dur=0.075, nasal=(260, 2600), av_level=-4),
    'L': Consonant('liquid', True, 'alveolar', (330, 1150, 2800), dur=0.065, av_level=-4),
    'R': Consonant('liquid', True, 'postalveolar', (330, 1100, 1450), dur=0.065, av_level=-3),
    'W': Consonant('glide', True, 'labial', (300, 650, 2200), dur=0.06, av_level=-3),
    'Y': Consonant('glide', True, 'palatal', (270, 2150, 3000), dur=0.055, av_level=-3),
}


def velar_locus(next_vowel_f2: float):
    """Velar stops assimilate to the vowel: F2 and F3 pinch together near the vowel's F2."""
    f2 = min(2600.0, max(1650.0, next_vowel_f2 * 1.1 + 200.0))
    return f2, f2 + 350.0


# --- visemes (VRM five-vowel mouth set) ---------------------------------------
VISEME_OF_VOWEL = {
    'IY': 'ih', 'IH': 'ih', 'EH': 'ee', 'AE': 'aa', 'AA': 'aa', 'AO': 'oh', 'UH': 'ou',
    'UW': 'ou', 'AH': 'aa', 'ER': 'ou', 'AX': 'aa', 'AY': 'aa', 'EY': 'ee', 'OW': 'oh',
    'AW': 'aa', 'OY': 'oh', 'NM': 'closed', 'OH': 'oh',
}
# consonant mouth shapes: (viseme, openness 0..1); None = keep neighbour vowel, reduced
VISEME_OF_CONSONANT = {
    'P': ('closed', 0.0), 'B': ('closed', 0.0), 'M': ('closed', 0.0),
    'F': ('ih', 0.15), 'V': ('ih', 0.15), 'W': ('ou', 0.35), 'R': ('ou', 0.3),
    'SH': ('ou', 0.3), 'ZH': ('ou', 0.3), 'CH': ('ou', 0.3), 'JH': ('ou', 0.3),
    'S': ('ih', 0.2), 'Z': ('ih', 0.2), 'TH': ('ee', 0.25), 'DH': ('ee', 0.25),
    'T': ('ee', 0.2), 'D': ('ee', 0.2), 'N': ('ee', 0.2), 'L': ('ee', 0.3),
    'K': ('aa', 0.25), 'G': ('aa', 0.25), 'NG': ('aa', 0.2), 'Y': ('ih', 0.3),
    'HH': (None, 0.5),
}


def is_vowel(p: str) -> bool:
    return p in VOWELS
