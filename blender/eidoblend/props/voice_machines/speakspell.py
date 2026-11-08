"""The 1978 educational speaking toy (speakspell.js, ported): a red-orange handheld speller with an 8-character
vacuum-fluorescent display, for DAISY's museum of voices. Era marks as homage, drawn by us and baked into the card
(the bouncy wordmark, TEXAS INSTRUMENTS in small caps, the Texas-outline "ti" mark).

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props.voice_machines import speakspell

    ss = speakspell.build(text='LOVE')            # -> SpeakSpell: group (root Empty), parts, update, dispose
    ss.parts['display'].set_text('LOVE')          # 8 characters at most, 14-segment VFD, unlit segments ghosted ~8 %
    ss.update(t, {'power': 1.0, 'voice': v}, ctx=ctx)   # per frame: power = VFD lit; voice = the toy's own loudness:
                                                        # the VFD flares and the grille glows

Geometry and materials come from the pack's speakspell.glb (built and baked in Blender by the pack's
build_speakspell.py: one-mass shell with the handle hole, parting line, card pocket, battery door and screw pockets;
the black band as its own moulding with real grille slots into a speaker cavity and a display window; a printed
membrane card with 40 embossed domes; a wire plate stand), imported once per blend by the voice-machine kit (the
registry module's era-2 kit). Real size (V&A): 254 x 177 x 38 mm. Metres, Blender Z up, resting on z = 0 of its root,
facing -Y; it leans back 0.12 rad on its stand (stand=False: upright, no stand, standing on its edge).
parts: toy (the leaning Empty), body, card, stand (or None), display {mesh, set_text, text, power, screen},
speaker {mesh, set(v)}.

How it plays as Blender data (the era-2 kit's Machine): power, gain (the tube's flare: 1 + 0.55 voice) and the
speaker glow are keyed custom properties on the root that the materials read through drivers; the display is a PNG
sequence (EraScreen): a new drawing only on the frames whose text changes, held between them.
"""

from __future__ import annotations

import math
import re

import bpy

from . import Machine, glow_material, metal_material, screen_material, baked_material
from .voder import Ctx2D

T_THICK, WIRE_R = 0.038, 0.0016
VFD_W, VFD_H = 0.0676, 0.0138
VFD_PX = 1024

SEG = {
    'a': ((0.14, 0.07), (0.86, 0.07)), 'd': ((0.14, 0.93), (0.86, 0.93)),
    'g1': ((0.14, 0.5), (0.5, 0.5)), 'g2': ((0.5, 0.5), (0.86, 0.5)),
    'f': ((0.12, 0.07), (0.12, 0.5)), 'e': ((0.12, 0.5), (0.12, 0.93)),
    'b': ((0.88, 0.07), (0.88, 0.5)), 'c': ((0.88, 0.5), (0.88, 0.93)),
    'i': ((0.5, 0.07), (0.5, 0.5)), 'l': ((0.5, 0.5), (0.5, 0.93)),
    'h': ((0.12, 0.07), (0.5, 0.5)), 'j': ((0.88, 0.07), (0.5, 0.5)),
    'k': ((0.12, 0.93), (0.5, 0.5)), 'm': ((0.88, 0.93), (0.5, 0.5)),
}
GLYPH = {
    'A': 'abcefg1g2', 'B': 'abcdilg2', 'C': 'adef', 'D': 'abcdil', 'E': 'adefg1g2', 'F': 'aefg1', 'G': 'acdefg2',
    'H': 'bcefg1g2', 'I': 'adil', 'J': 'bcde', 'K': 'efg1jm', 'L': 'def', 'M': 'bcefhj', 'N': 'bcefhm', 'O': 'abcdef',
    'P': 'abefg1g2', 'Q': 'abcdefm', 'R': 'abefg1g2m', 'S': 'acdfg1g2', 'T': 'ail', 'U': 'bcdef', 'V': 'efjk',
    'W': 'bcefkm', 'X': 'hjkm', 'Y': 'hjl', 'Z': 'adjk', '0': 'abcdefjk', '1': 'bcj', '2': 'abdeg1g2', '3': 'abcdg2',
    '4': 'bcfg1g2', '5': 'acdfg1g2', '6': 'acdefg1g2', '7': 'abc', '8': 'abcdefg1g2', '9': 'abcdfg1g2', '-': 'g1g2',
    "'": 'j', '?': 'abg2l', '!': 'il', '*': 'g1g2hijklm', '+': 'g1g2il', '/': 'jk', '_': 'd', ' ': '', '=': 'dg1g2',
    '<': 'jm', '>': 'hk',
}


def seg_list(code):
    """'abcefg1g2' -> ['a', 'b', 'c', 'e', 'f', 'g1', 'g2'] (speakspell.js segList)"""
    return re.findall(r'g1|g2|[a-fh-m]', code or '')


def draw_vfd(ctx, w, h, text, align='left'):
    """speakspell.js drawVFD: the 14-segment tube on a canvas (black glass, ghosted segments, the lit characters in
    three glowing passes, the control grid and the filaments)."""
    ctx.save()
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, w, h)
    N, cell_w, cell_h, top = 8, w / 8, h * 0.8, h * 0.1
    chars = list(str(text or ''))
    off = N - len(chars) if align == 'right' else (N - len(chars)) // 2 if align == 'center' else 0

    def draw_seg(x0, y0, x1, y1, hw, gap):
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        ax, ay, bx, by = x0 + ux * gap, y0 + uy * gap, x1 - ux * gap, y1 - uy * gap
        ctx.beginPath()
        ctx.moveTo(ax, ay)
        ctx.lineTo(ax + ux * hw + nx * hw, ay + uy * hw + ny * hw)
        ctx.lineTo(bx - ux * hw + nx * hw, by - uy * hw + ny * hw)
        ctx.lineTo(bx, by)
        ctx.lineTo(bx - ux * hw - nx * hw, by - uy * hw - ny * hw)
        ctx.lineTo(ax + ux * hw - nx * hw, ay + uy * hw - ny * hw)
        ctx.closePath()
        ctx.fill()

    def cell_segs(ci, segs, dp, ghost):
        cx, cwid, hw = ci * cell_w + cell_w * 0.1, cell_w * 0.8, cell_h * 0.052
        for s in segs:
            (a0, b0), (a1, b1) = SEG[s]
            diag = s in ('h', 'j', 'k', 'm')
            draw_seg(cx + a0 * cwid, top + b0 * cell_h, cx + a1 * cwid, top + b1 * cell_h,
                     hw * 0.75 if diag else hw, cell_h * 0.07 if diag else cell_h * 0.028)
        if ghost or dp:
            ctx.beginPath()
            ctx.arc(cx + cwid * 1.03, top + cell_h * 0.95, hw * 0.9, 0, math.pi * 2)
            ctx.fill()
    ctx.fillStyle = 'rgba(62,242,228,0.08)'
    for ci in range(N):
        cell_segs(ci, list(SEG), False, True)
    lit = []
    for i, ch in enumerate(chars):
        lit.append((off + i, seg_list(GLYPH.get(ch, '')), ch in ('.', ',', '!')))
    ctx.shadowColor = 'rgba(16,214,204,0.9)'
    ctx.shadowBlur = cell_h * 0.2
    ctx.fillStyle = '#22d8cc'
    for ci, segs, dp in lit:
        cell_segs(ci, segs, dp, False)
    ctx.shadowBlur = cell_h * 0.06
    ctx.fillStyle = '#4cf2e2'
    for ci, segs, dp in lit:
        cell_segs(ci, segs, dp, False)
    ctx.shadowBlur = 0
    ctx.globalAlpha = 0.28
    ctx.fillStyle = '#b4fff6'
    for ci, segs, dp in lit:
        cell_segs(ci, segs, dp, False)
    ctx.globalAlpha = 1
    ctx.strokeStyle = 'rgba(0,0,0,0.30)'                      # control grid
    ctx.lineWidth = 1
    pitch = max(3, int(math.floor(cell_h * 0.045 + 0.5)))
    ctx.beginPath()
    x = -h
    while x < w + h:
        ctx.moveTo(x, 0)
        ctx.lineTo(x + h, h)
        ctx.moveTo(x + h, 0)
        ctx.lineTo(x, h)
        x += pitch
    ctx.stroke()
    ctx.strokeStyle = 'rgba(0,0,0,0.55)'                      # filaments
    ctx.lineWidth = 1.5
    for fy in (0.22, 0.5, 0.78):
        ctx.beginPath()
        ctx.moveTo(0, h * fy)
        ctx.lineTo(w, h * fy + 1)
        ctx.stroke()
    ctx.restore()


class Display:
    """parts['display']: the VFD behind its glass. set_text(s, align='left', t=None, frame=None) shows up to 8
    characters (redrawn and keyed at the frame of t, or `frame`, or the next update)."""

    def __init__(self, machine, mesh, screen):
        self.machine, self.mesh, self.screen = machine, mesh, screen
        self.power = machine.channels['power']
        self._text, self._align, self.dirty = '', 'left', True
        self.draws = 0

    @property
    def text(self):
        return self._text

    def set_text(self, s, align=None, t=None, frame=None, **opts):
        txt = str('' if s is None else s).upper()[:8]
        a = align or opts.get('align') or 'left'
        if txt != self._text or a != self._align:
            self._text, self._align, self.dirty = txt, a, True
        if self.dirty and (t is not None or frame is not None):
            f = frame if frame is not None else self.machine.frame_at(t)
            self.redraw(f)

    def draw(self, w, h):
        c = Ctx2D(w, h, ss=2)
        draw_vfd(c, w, h, self._text, self._align)
        self.draws += 1
        return c.image()

    def redraw(self, frame):
        self.screen.put(frame, self.draw(self.screen.pw, self.screen.ph))
        self.dirty = False


class Speaker:
    """parts['speaker']: the cavity behind the grille slots, lit by the voice. set(v, t=None) keys the level."""

    def __init__(self, machine, mesh):
        self.machine, self.mesh = machine, mesh
        self.level = machine.channels['speaker']

    def set(self, v, t=None, ctx=None, frame=None):
        self.machine.key('speaker', max(0.0, float(v)), t, ctx, frame)


class SpeakSpell(Machine):
    def __init__(self, text='SPELL', stand=True, **kw):
        super().__init__('speakspell', **kw)
        g = self.group
        lean = 0.12 if stand else 0.0
        toy = bpy.data.objects.new(f'{g.name}_toy', None)
        toy.empty_display_size = 0.05
        self.collection.objects.link(toy)
        toy.parent = g
        self.objects.append(toy)
        self.channel('power', 1.0, '0..1: the VFD lit')
        self.channel('gain', 1.0, 'the tube flare on each syllable (1 + 0.55 voice)')
        self.channel('speaker', 0.0, 'the grille glow (the voice, while powered)')
        body = self.part('ss_body')
        card = self.part('ss_card')
        stand_ob = self.part('part_stand') if stand else None
        screws = self.part('metal_screws', runtime=True)
        glass = self.part('screen_vfd', runtime=True)
        glow = self.part('glow_grille', runtime=True)
        for o in (body, card, stand_ob):
            if o is not None:
                for s in o.material_slots:
                    s.material = baked_material(s.material)
        self.assign(screws, self.material(metal_material(f'{g.name}_screws', '#a9a9ad', 0.34)))
        self.display = Display(self, glass, None)
        self.display.set_text(text)
        self.screen = self.era_screen(VFD_W, VFD_H, VFD_PX, self.display.draw, suffix='vfd')   # draws the text once
        self.display.screen = self.screen
        self.display.dirty = False
        self.assign(glass, self.material(screen_material(
            f'{g.name}_vfd', self.screen, g, power='power', gain='gain', gain_k=1.2, glass='#07090a', rough=0.3,
            coat_rough=0.025, parallax=0.0032, face_size=(VFD_W, VFD_H), scene=self.scene)))
        self.assign(glow, self.material(glow_material(f'{g.name}_grille_glow', '#7ff6ff', g, 'speaker')))
        for o in (body, card, screws, glass, glow):
            o.parent = toy
        # lean back onto the stand exactly as the pack's Blender build placed it (same lean, same lift)
        toy.rotation_euler = (-lean, 0.0, 0.0)
        toy.location = (0.0, 0.0, 2 * WIRE_R + (T_THICK / 2) * math.sin(lean) + 0.0005 if stand else 0.0)
        if not stand:          # upright on its own edge: lift the toy until its lowest point rests on z = 0
            bpy.context.view_layer.update()
            zmin = min((o.matrix_world @ v.co).z for o in (body, card, screws, glass, glow) for v in o.data.vertices)
            toy.location.z = g.matrix_world.translation.z - zmin
        self.speaker = Speaker(self, glow)
        self.parts = {'toy': toy, 'body': body, 'card': card, 'stand': stand_ob,
                      'display': self.display, 'speaker': self.speaker}

    def _update(self, t, st, f, ctx):
        p = max(0.0, float(st['power'] if st.get('power') is not None else 1.0))
        v = max(0.0, min(1.0, float(st['voice'] if st.get('voice') is not None else 0.0)))
        self.key('power', p, frame=f, ctx=ctx)
        self.key('gain', 1 + 0.55 * v, frame=f, ctx=ctx)       # the tube flares a little on each syllable
        self.speaker.set(v if p > 0.01 else 0.0, frame=f, ctx=ctx)
        if 'text' in st:
            self.display.set_text(st['text'], st.get('align'))
        if self.display.dirty:
            self.display.redraw(f)


def build(text='SPELL', stand=True, **opts):
    """speakspell.js build(THREE, { text, stand }) -> a SpeakSpell. opts: name, scene, collection, interpolation
    ('CONSTANT' keys by default), screen_dir (the VFD's PNG frames), ctx (a scene's ctx: keys through ctx.key)."""
    return SpeakSpell(text=text, stand=stand, **opts)
