"""eidoblend.props.voice_machines.dectalk: the 1984 desktop speech synthesizer (the DTC01 form: a flat putty-beige
box, 18 x 12 x 4 in, the top edge slanted back, horizontal grooves across the front, a grey stripe, a rocker switch),
for DAISY's museum of voices. Port of eidoverse/props/voice_machines/dectalk.js.

Era mark as homage, drawn by us and baked: DEC's seven-block "digital" and a red DECtalk on the slant.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props.voice_machines import dectalk
    dt = dectalk.build()
    dt.group.location = (0.0, 0.0, 0.74)
    # per frame, in time order: keyed at the frame of t
    dt.update(t, {'power': 1.0, 'voice': loudness(t)})
    #   power -> the POWER LED (and the READY LED on the back); voice -> the SPEECH LED pulses with the loudness and
    #   the speaker cavity behind the grille glows
    dt.update(t, {'leds': [1.0, 0.4, 1.0]})            # or drive the three LEDs directly (power, speech, back)
    dt.parts['leds'][1].set(0.8, t)                    # one LED, keyed at the frame of t

The real DTC01 front carries only the rocker (its green LED is on the back panel, audio leaves by jacks); the two
front LEDs and the speaker grille are the brief's additions, drawn in the same groove language.
Geometry + materials: the pack's dectalk.glb (models/voice_machines_src/build_dectalk.py): the case with the slanted
top-front, perimeter parting line, grooves cut across the front, the recessed grey stripe, a rocker in a pocketed
bezel, LED lenses, grille slots into a speaker cavity, side vents, a recessed back panel with DB-25 shells, RJ11s,
audio jacks, volume wheel and power inlet; AmbientCG scans, AO grime, edge wear and yellowing baked to 2048 maps.
Metres, +Z up, on z = 0 of its root, the front toward -Y.
parts: box, leds [Lamp power, speech, back] (name, mesh, level, set(v)), speaker (mesh, set(v)).
"""
from __future__ import annotations

from . import Lamp, Machine, glow_material, led_material, metal_material

# name, colour, lens colour (index order: the update state's leds list)
LEDS = (('power', '#36ff6a', '#1a6a2a'), ('speech', '#ffae1a', '#7a4a10'), ('back', '#36ff6a', '#1a6a2a'))


class DECtalk(Machine):
    """The built DECtalk (see the module doc). update(t, state): power, voice, or leds [power, speech, back]."""

    def __init__(self, **kw):
        super().__init__('dectalk', **kw)
        g = self.group
        box = self.part('dt_body')
        metal = self.material(metal_material(f'{g.name}.metal', '#c2c2c6', 0.3))
        for o in [self.part(n, runtime=True) for n in sorted(self.src) if n.startswith('metal_')]:
            self.assign(o, metal)
        glow_mesh = self.part('glow_grille', runtime=True)
        spk = self.channel('speaker', 0.0, 'the glow of the speaker cavity behind the grille (0.9 voice when on)')
        self.assign(glow_mesh, self.material(glow_material(f'{g.name}.glow', '#ffb24a', g, 'speaker')))
        leds = []
        for name, col, lens in LEDS:
            ch = self.channel(f'led_{name}', 0.0, f'the {name} LED level')
            m = self.part(f'led_{name}', runtime=True)
            self.assign(m, self.material(led_material(f'{g.name}.led_{name}', col, g, f'led_{name}', lens)))
            leds.append(Lamp(name, m, ch))
        self.parts = {'box': box, 'leds': leds, 'speaker': Lamp('speaker', glow_mesh, spk)}

    def _update(self, t, st, f, ctx):
        p = max(0.0, float(st['power'] if st.get('power') is not None else 1.0))
        v = max(0.0, min(1.0, float(st.get('voice') or 0.0)))
        leds, speaker = self.parts['leds'], self.parts['speaker']
        if isinstance(st.get('leds'), (list, tuple)):                 # drive them directly
            for i, x in enumerate(st['leds']):
                if i < len(leds):
                    leds[i].set(x, ctx=ctx, frame=f)
            return
        on = p > 0.02
        leds[0].set(1.0 if on else 0.0, ctx=ctx, frame=f)
        leds[2].set(1.0 if on else 0.0, ctx=ctx, frame=f)
        leds[1].set((0.55 + 0.9 * v if v > 0.3 else v * 0.4) if on else 0.0, ctx=ctx, frame=f)   # SPEECH pulses
        speaker.set(v * 0.9 if on else 0.0, ctx=ctx, frame=f)


def build(opts=None, **kw):
    """build(THREE, opts) -> the DECtalk: group (its root Empty), parts, update(t, state), dispose(). Options (the
    Blender edition's plumbing; the JS build takes none): name, scene, collection, ctx, interpolation."""
    o = dict(opts or {})
    o.update(kw)
    return DECtalk(**o)


__all__ = ['build', 'DECtalk', 'LEDS']
