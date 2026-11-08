"""eidoblend.props.voice_machines.c64: a 1982 home computer (the brown/beige "breadbin" wedge) with its 13" colour
monitor behind it, for DAISY's museum of voices. Port of eidoverse/props/voice_machines/c64.js.

Era marks as homage, drawn by us and baked into the pack's maps: the commodore badge with the C= mark, rainbow
stripes and 64, the C= key, and the monitor's commodore plate.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props.voice_machines import c64
    c = c64.build()                                   # or voice_machines.build_machine('c64')
    c.group.location = (0.0, 0.0, 0.74)               # on a desk top
    c.parts['screen'].set_text(['READY.', 'SAY "I WAS A MOUTH"', 'I WAS A MOUTH', 'READY.'], True)
    # per frame, in time order: keyed at the frame of t
    c.update(t, {'power': 1.0, 'voice': loudness(t)})
    #   power = the monitor's raster (CRT switch-on) + its LED; voice = its own voice loudness: the raster brightens
    #   on each syllable and the monitor's power LED pulses with it, the side vents glow from inside

Screen: 40 x 25 characters in an 8 x 8 pixel font drawn for this prop (C64-style: 2-px verticals, 1-px
horizontals), light-blue text on a blue field inside a lighter border, a blinking block cursor. cursor_on: True =
blinks with t (period 2/3 s), 'solid' = always on, False = hidden. The raster sits under the bulged glass with the
CRT switch-on, 288 scanlines, pincushion, rounded tube mask, vignette and a slight phosphor bleed.

Geometry + materials: the pack's c64.glb (built by models/voice_machines_src/build_c64.py): the wedge case, the 70
dished keycaps with legends, the monitor; AmbientCG Plastic013B / 012B scans, AO grime, edge wear and yellowing
baked to 2048 maps. Real sizes: computer 404 x 216 x 75 mm; monitor about 368 x 342 x 400 mm. Metres, +Z up, on
z = 0 of its root, the front toward -Y.
parts: computer, keys, monitor, screen (mesh, set_text, lines, power, screen), leds {computer, monitor},
       speaker (mesh, set(v)): the monitor's side vents, lit from inside.
"""
from __future__ import annotations

import math

import numpy as np

from . import Lamp, Machine, glow_material, led_material, metal_material

TW, TH = 0.282, 0.218                      # the tube's glass (m): its UV square
CW, CH = 768, 576                          # 2 x (384 x 288): the frame at double pixels
S = 2                                      # canvas pixels per C64 pixel
BORDER, FIELD, INK = '#6c5eb5', '#352879', '#6c5eb5'
COLS, ROWS = 40, 24                        # characters per line; lines kept (the 25th row holds the cursor)
BOOT = ['', '    **** SPEECH BASIC V2 ****', '', ' 64K RAM SYSTEM  38911 BASIC BYTES FREE', '', 'READY.']
BLINK_HZ = 3.0                             # floor(t * 3) % 2: 1/3 s on, 1/3 s off

# 8 x 8 glyphs drawn for this prop in the home-computer style (2-px verticals, 1-px horizontals). Not a ROM dump.
FONT8 = {
    ' ': '........ ........ ........ ........ ........ ........ ........ ........',
    'A': '...##... ..####.. .##..##. .######. .##..##. .##..##. .##..##. ........',
    'B': '.#####.. .##..##. .##..##. .#####.. .##..##. .##..##. .#####.. ........',
    'C': '..####.. .##..##. .##..... .##..... .##..... .##..##. ..####.. ........',
    'D': '.####... .##.##.. .##..##. .##..##. .##..##. .##.##.. .####... ........',
    'E': '.######. .##..... .##..... .####... .##..... .##..... .######. ........',
    'F': '.######. .##..... .##..... .####... .##..... .##..... .##..... ........',
    'G': '..####.. .##..##. .##..... .##.###. .##..##. .##..##. ..####.. ........',
    'H': '.##..##. .##..##. .##..##. .######. .##..##. .##..##. .##..##. ........',
    'I': '..####.. ...##... ...##... ...##... ...##... ...##... ..####.. ........',
    'J': '...####. ....##.. ....##.. ....##.. ....##.. .##.##.. ..###... ........',
    'K': '.##..##. .##.##.. .####... .###.... .####... .##.##.. .##..##. ........',
    'L': '.##..... .##..... .##..... .##..... .##..... .##..... .######. ........',
    'M': '.##...## .###.### .####### .##.#.## .##...## .##...## .##...## ........',
    'N': '.##..##. .###.##. .######. .######. .##.###. .##..##. .##..##. ........',
    'O': '..####.. .##..##. .##..##. .##..##. .##..##. .##..##. ..####.. ........',
    'P': '.#####.. .##..##. .##..##. .#####.. .##..... .##..... .##..... ........',
    'Q': '..####.. .##..##. .##..##. .##..##. .##..##. ..####.. ....###. ........',
    'R': '.#####.. .##..##. .##..##. .#####.. .####... .##.##.. .##..##. ........',
    'S': '..####.. .##..##. .##..... ..####.. .....##. .##..##. ..####.. ........',
    'T': '.######. ...##... ...##... ...##... ...##... ...##... ...##... ........',
    'U': '.##..##. .##..##. .##..##. .##..##. .##..##. .##..##. ..####.. ........',
    'V': '.##..##. .##..##. .##..##. .##..##. .##..##. ..####.. ...##... ........',
    'W': '.##...## .##...## .##...## .##.#.## .####### .###.### .##...## ........',
    'X': '.##..##. .##..##. ..####.. ...##... ..####.. .##..##. .##..##. ........',
    'Y': '.##..##. .##..##. .##..##. ..####.. ...##... ...##... ...##... ........',
    'Z': '.######. .....##. ....##.. ...##... ..##.... .##..... .######. ........',
    '0': '..####.. .##..##. .##.###. .###.##. .##..##. .##..##. ..####.. ........',
    '1': '...##... ...##... ..###... ...##... ...##... ...##... .######. ........',
    '2': '..####.. .##..##. .....##. ....##.. ..##.... .##..... .######. ........',
    '3': '..####.. .##..##. .....##. ...###.. .....##. .##..##. ..####.. ........',
    '4': '.....##. ....###. ...####. .##..##. .####### .....##. .....##. ........',
    '5': '.######. .##..... .#####.. .....##. .....##. .##..##. ..####.. ........',
    '6': '..####.. .##..##. .##..... .#####.. .##..##. .##..##. ..####.. ........',
    '7': '.######. .##..##. ....##.. ...##... ...##... ...##... ...##... ........',
    '8': '..####.. .##..##. .##..##. ..####.. .##..##. .##..##. ..####.. ........',
    '9': '..####.. .##..##. .##..##. ..#####. .....##. .##..##. ..####.. ........',
    '.': '........ ........ ........ ........ ........ ...##... ...##... ........',
    ',': '........ ........ ........ ........ ........ ...##... ...##... ..##....',
    ':': '........ ........ ...##... ........ ........ ...##... ........ ........',
    ';': '........ ........ ...##... ........ ........ ...##... ...##... ..##....',
    '"': '.##..##. .##..##. .##..##. ........ ........ ........ ........ ........',
    "'": '.....##. ....##.. ...##... ........ ........ ........ ........ ........',
    '!': '...##... ...##... ...##... ...##... ........ ........ ...##... ........',
    '?': '..####.. .##..##. .....##. ....##.. ...##... ........ ...##... ........',
    '*': '........ .##..##. ..####.. ######## ..####.. .##..##. ........ ........',
    '-': '........ ........ ........ .######. ........ ........ ........ ........',
    '+': '........ ...##... ...##... .######. ...##... ...##... ........ ........',
    '=': '........ ........ .######. ........ .######. ........ ........ ........',
    '/': '........ ......## .....##. ....##.. ...##... ..##.... .##..... ........',
    '(': '....##.. ...##... ..##.... ..##.... ..##.... ...##... ....##.. ........',
    ')': '..##.... ...##... ....##.. ....##.. ....##.. ...##... ..##.... ........',
    '#': '.##..##. .##..##. ######## .##..##. ######## .##..##. .##..##. ........',
    '$': '...##... ..#####. .##..... ..####.. .....##. .#####.. ...##... ........',
    '<': '....###. ...###.. ..###... .###.... ..###... ...###.. ....###. ........',
    '>': '.###.... ..###... ...###.. ....###. ...###.. ..###... .###.... ........',
    '%': '.##...## .##..##. ....##.. ...##... ..##.... .##..##. ##...##. ........',
}
_BITS = {ch: np.array([[c == '#' for c in row] for row in rows.split()], bool) for ch, rows in FONT8.items()}


def glyph(ch: str):
    """The 8 x 8 bit array of a character (rows top to bottom), or None for one the font does not draw."""
    return _BITS.get(ch)


def flatten_lines(lines) -> list:
    """setText's layout: a list of lines or one string with newlines, upper-cased, each wrapped at 40 columns (an
    empty line stays a line), and only the last 24 kept (the screen scrolls)."""
    arr = list(lines) if isinstance(lines, (list, tuple)) else str('' if lines is None else lines).split('\n')
    flat = []
    for ln in arr:
        s = str(ln).upper()
        if not s:
            flat.append('')
        for i in range(0, len(s), COLS):
            flat.append(s[i:i + COLS])
    return flat[-ROWS:]


def _rgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.uint8)


def draw_c64(lines, cursor=True, blink_phase=1, w=CW, h=None):
    """drawC64: the raster as an RGBA PIL image w x h (the canvas makeScreen made: 768 x 594 for the tube). The frame
    fills the top 768 x 576 (border, field, 40 x 25 text, block cursor); canvas rows below it stay transparent
    black, as on the engine's canvas. lines: already flattened (flatten_lines)."""
    from PIL import Image
    h = h or CH
    a = np.zeros((h, w, 4), np.uint8)
    a[:CH, :CW, :3] = _rgb(BORDER)
    a[:CH, :CW, 3] = 255
    x0, y0 = (CW - 320 * S) // 2, (CH - 200 * S) // 2
    a[y0:y0 + 200 * S, x0:x0 + 320 * S, :3] = _rgb(FIELD)
    ink = _rgb(INK)
    row = 0
    for line in lines:
        for c, ch in enumerate(line[:COLS]):
            g = _BITS.get(ch)
            if g is None:
                continue
            big = np.kron(g, np.ones((S, S), bool))
            ys, xs = y0 + row * 8 * S, x0 + c * 8 * S
            a[ys:ys + 8 * S, xs:xs + 8 * S, :3][big] = ink
        row += 1
    if blink_phase and cursor:
        ys = y0 + min(24, row) * 8 * S
        a[ys:ys + 8 * S, x0:x0 + 8 * S, :3] = ink
    return Image.fromarray(a[:h, :w], 'RGBA')


def blink_phase_at(t, cursor):
    """The cursor's phase at t: True blinks (on for floor(3t) even), a truthy non-True value ('solid') is always on,
    a falsy one is off."""
    if cursor is True:
        return 1 if math.floor(t * BLINK_HZ) % 2 == 0 else 0
    return 1 if cursor else 0


class C64Screen:
    """parts['screen']: mesh (the tube), set_text(lines, cursor_on=True), lines (what is on it), power (the
    raster's channel: update keys it), screen (the EraScreen: its image sequence)."""

    def __init__(self, machine, mesh, screen, power):
        self.machine, self.mesh, self.screen, self.power = machine, mesh, screen, power

    def set_text(self, lines, cursor_on=True):
        """The screen's text (a list of lines or one string with newlines; upper-cased, wrapped at 40 columns, the
        last 24 lines kept) and its cursor: True blinks, 'solid' stays on, False hides it. Like the engine, the
        drawing changes at the next update(t)."""
        st = self.machine._st
        nxt = flatten_lines(lines)
        same_cursor = type(cursor_on) is type(st['cursor']) and cursor_on == st['cursor']      # JS's ===
        if '\n'.join(nxt) != '\n'.join(st['lines']) or not same_cursor:
            st['lines'], st['cursor'], st['dirty'] = nxt, cursor_on, True

    @property
    def lines(self):
        return list(self.machine._st['lines'])

    def __repr__(self):
        return f'<C64Screen {len(self.lines)} lines, cursor {self.machine._st["cursor"]!r}>'


class C64(Machine):
    """The built C64 (see the module doc). update(t, state): power, voice, lines, cursor_on."""

    def __init__(self, *, lines=None, cursor_on=True, **kw):
        super().__init__('c64', **kw)
        g = self.group
        comp, keys, mon = self.part('c64_comp'), self.part('c64_keys'), self.part('c64_mon')
        metal = self.material(metal_material(f'{g.name}.metal', '#c4c4c8', 0.3))
        for o in [self.part(n, runtime=True) for n in sorted(self.src) if n.startswith('metal_')]:
            self.assign(o, metal)
        ch_comp = self.channel('led_computer', 0.0, 'the computer power LED level (update keys 1)')
        ch_mon = self.channel('led_monitor', 0.0, "the monitor power LED level (0.75 + 0.6 voice when on)")
        led_a = self.material(led_material(f'{g.name}.led_computer', '#ff2a14', g, 'led_computer'))
        led_b = self.material(led_material(f'{g.name}.led_monitor', '#ff3018', g, 'led_monitor'))
        comp_led, mon_led = self.part('led_c64_power', runtime=True), self.part('led_mon_power', runtime=True)
        self.assign(comp_led, led_a)
        self.assign(mon_led, led_b)
        # the monitor's speaker lives behind its side vents: the voice lights them from inside
        ch_spk = self.channel('speaker', 0.0, 'the glow behind the monitor vents (0.8 voice when on)')
        glow = None
        if 'glow_vents' in self.src:
            glow = self.part('glow_vents', runtime=True)
            self.assign(glow, self.material(glow_material(f'{g.name}.glow', '#a79bff', g, 'speaker')))

        # the tube: the C64 raster under the glass, CRT switch-on, scanlines, pincushion
        power = self.channel('power', 1.0, 'the raster (CRT switch-on as it rises)')
        self.channel('gain', 1.0, 'the raster brightness (1 + 0.4 voice)')
        self._st = {'lines': flatten_lines(BOOT if lines is None else lines), 'cursor': cursor_on, 'blink': 1,
                    'dirty': False}
        scr = self.era_screen(TW, TH, CW, self._draw)
        tube = self.make_tube(scr, gain_k=0.72, glass='#0f1110', rough=0.34, coat_rough=0.04, barrel=0.05, scan=288,
                              scan_amt=0.32, corner=0.09, vignette=0.35, bleed=0.0009, crt_on=True, tube_height=TH)
        self.parts = {
            'computer': comp, 'keys': keys, 'monitor': mon,
            'screen': C64Screen(self, tube, scr, power),
            'leds': {'computer': Lamp('computer', comp_led, ch_comp), 'monitor': Lamp('monitor', mon_led, ch_mon)},
            'speaker': Lamp('speaker', glow, ch_spk),
        }

    def _draw(self, w, h):
        st = self._st
        return draw_c64(st['lines'], st['cursor'], st['blink'], w, h)

    def _update(self, t, st, f, ctx):
        p = max(0.0, float(st.get('power') if st.get('power') is not None else 1.0))
        v = max(0.0, min(1.0, float(st.get('voice') or 0.0)))
        self.key('power', p, frame=f, ctx=ctx)
        self.key('gain', 1.0 + 0.4 * v, frame=f, ctx=ctx)            # the raster flares with each syllable
        self.key('led_computer', 1.0, frame=f, ctx=ctx)              # the computer is on the whole scene
        self.key('led_monitor', 0.75 + 0.6 * v if p > 0.02 else 0.0, frame=f, ctx=ctx)
        self.key('speaker', max(0.0, v * 0.8 if p > 0.02 else 0.0), frame=f, ctx=ctx)
        if 'lines' in st:                                             # JS: state.lines !== undefined
            cur = st.get('cursor_on')
            self.parts['screen'].set_text(st['lines'], True if cur is None else cur)
        s = self._st
        ph = blink_phase_at(t, s['cursor'])
        if ph != s['blink']:
            s['blink'], s['dirty'] = ph, True
        if s['dirty']:
            self.screens[0].redraw(f)
            s['dirty'] = False


def build(opts=None, **kw):
    """build(THREE, opts) -> the C64: group (its root Empty), parts, update(t, state), dispose(). Options (all the
    Blender edition's plumbing; the JS build takes none): name, scene, collection, screen_dir (where the screen's
    frames go), ctx (a scene's ctx: keys through ctx.key, frames from ctx.frame_at), interpolation ('CONSTANT'),
    lines / cursor_on (the first drawing; default the SPEECH BASIC boot screen)."""
    o = dict(opts or {})
    o.update(kw)
    return C64(**o)


__all__ = ['build', 'C64', 'C64Screen', 'FONT8', 'glyph', 'flatten_lines', 'draw_c64', 'blink_phase_at', 'BOOT',
           'TW', 'TH', 'CW', 'CH']
