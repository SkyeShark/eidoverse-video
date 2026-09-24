"""synthkit — hand-built music for eidoverse agents: oscillators, instruments, drums,
a beat sequencer with sidechain and send effects, and a loudness-targeted master bus.

    from synthkit import Song, inst, master, write_stereo
"""
from . import instruments as inst
from .dsp import SR, adsr, midi_hz, pan_stereo, pulse, saw, sine, supersaw, svf, tri
from .seq import Song, Track, chord, master, nm, place, write_stereo

__all__ = ['SR', 'Song', 'Track', 'chord', 'inst', 'master', 'midi_hz', 'nm', 'place', 'write_stereo',
           'adsr', 'pan_stereo', 'pulse', 'saw', 'sine', 'supersaw', 'svf', 'tri']
