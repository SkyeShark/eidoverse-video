"""voicebox — a singing and speaking formant synthesizer for eidoverse agents.

Build a voice from first principles (glottal source, vocal-tract resonances,
frication) and make it sing a score or speak a line, with a phoneme timeline
that drives VRM mouth shapes exactly. Era presets (see `eras.py`) reproduce the
characteristic sound of historical machine voices.

    from voicebox import Voice, Sung, speak, visemes, write_wav
    song = Sung(bpm=120)
    song.line("Dai sy Dai sy", ["G4", "E4", "C4", "G3"], [3, 3, 3, 3], start_beat=0)
    audio, segs, tracks = song.render(Voice(vtl=0.6))
    write_wav("daisy.wav", audio, 48000)
"""
from .articulate import CR, Syl, Voice, midi_to_hz, render_syllables, sung_f0
from .g2p import add_word, lookup, syllabify, text_to_syllables
from .score import Sung, note_midi, speak, speak_syllables, visemes
from .util import read_wav, write_wav

__all__ = ['CR', 'Syl', 'Voice', 'Sung', 'midi_to_hz', 'render_syllables', 'sung_f0', 'add_word', 'lookup',
           'syllabify', 'text_to_syllables', 'note_midi', 'speak', 'speak_syllables', 'visemes',
           'read_wav', 'write_wav']
