"""eidoblend.props.voice_machines.desktop2001: a 2001 desktop PC (beige mid-tower, 17" CRT, powered speakers,
104-key keyboard, wheel mouse) for DAISY's museum of voices. Port of eidoverse/props/voice_machines/desktop2001.js.

The CRT shows an early-2000s desktop: a generic green hill under a blue sky (drawn here, not the real wallpaper), a
Luna-blue taskbar whose Start button carries our homage of the four-tile flag, and a small Narrator dialog the film
fills with text. The XP sticker on the tower and the flag keys are baked homages.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props.voice_machines import desktop2001
    pc = desktop2001.build()                          # options: title ('Narrator'), clock ('10:23 PM'), text
    pc.group.location = (0.0, 0.0, 0.74)
    pc.parts['screen'].set_text('reading screens')    # the dialog's message (\\n for a second line)
    # per frame, in time order: keyed at the frame of t
    pc.update(t, {'power': 1.0, 'voice': loudness(t)})
    #   power = the CRT raster (switch-on) + the power LEDs; voice = its own voice: the screen brightens, the
    #   speaker cloth glows from within, the tower's drive light flickers with the speech

Geometry + materials: the pack's desktop2001.glb (models/voice_machines_src/build_desktop2001.py): the tower with
cover seams, PSU and slot covers, its front bezel (bays, floppy, CD-ROM, power + reset, LED windows, intake slots,
sticker pocket); the CRT with a drafted opening, control strip, tapered vented hood and swivel foot; speakers with
fabric grilles (AmbientCG Fabric082A), knob and LED; the keyboard (three drafted wells, 104 dished keys, legends,
lock LEDs); the mouse; cables. AmbientCG scans, AO grime, edge wear baked. Metres, +Z up, on z = 0 of its root, the
front toward -Y.
parts: monitor, tower, keyboard, speakers, screen (mesh, set_text, text, power, screen), leds {mon, tw_power, tw_hdd,
       tw_cd, spk, kb0, kb1, kb2} (Lamp: mesh, level, set(v)), speaker (mesh, set(v)): the cloth's glow.
"""
from __future__ import annotations

import math
import re

import numpy as np

from . import Canvas2D, Gradient, Lamp, Machine, Nodes, baked_material, led_material, lin, quad, rng, rr

TW, TH = 0.345, 0.262                 # the tube's glass (m): its UV square
PX = 1024                             # the canvas: 1024 x 778 (makeScreen's height by the glass's aspect)
W, H, TB = 1024, 768, 30              # the drawing: a 1024 x 768 desktop, the taskbar 30 px
SS = 3                                # supersampling of the drawing (canvas-2D antialiases its shapes and text)
# name, colour, lens colour
LEDS = (('led_mon', '#46ff5a', '#1a5a24'), ('led_tw_power', '#46ff5a', '#1a5a24'),
        ('led_tw_hdd', '#ffb020', '#6a4a10'), ('led_tw_cd', '#46ff5a', '#1a5a24'), ('led_spk', '#46ff5a', '#1a5a24'),
        ('led_kb0', '#46ff5a', '#1a5a24'), ('led_kb1', '#46ff5a', '#1a5a24'), ('led_kb2', '#46ff5a', '#1a5a24'))


# ------------------------------------------------------------------------------------------------- the desktop ---
TAHOMA = 'Tahoma, Verdana, sans-serif'


def draw_flag(g, x, y, w, h):
    """The four waving tiles, homage."""
    cols = ('#f25022', '#7fba00', '#00a4ef', '#ffb900')

    def wave(u):
        return math.sin(u * math.pi * 1.1 + 0.3) * 0.07
    for k, (i, j) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
        u0, u1 = i * 0.5 + (0.03 if i else 0), (i + 1) * 0.5 - (0 if i else 0.03)
        v0, v1 = j * 0.5 + (0.03 if j else 0), (j + 1) * 0.5 - (0 if j else 0.03)
        pts = []
        for s in range(9):
            u = u0 + (u1 - u0) * s / 8
            pts.append((x + u * w - (v0 + wave(u)) * w * 0.06, y + (v0 + wave(u)) * h))
        for s in range(8, -1, -1):
            u = u0 + (u1 - u0) * s / 8
            pts.append((x + u * w - (v1 + wave(u)) * w * 0.06, y + (v1 + wave(u)) * h))
        g.fill_poly(pts, cols[k])


def draw_speaker_glyph(g, x, y, s):
    """Narrator's speaker-and-waves glyph."""
    body = [(x, y + s * 0.35), (x + s * 0.22, y + s * 0.35), (x + s * 0.5, y + s * 0.1), (x + s * 0.5, y + s * 0.9),
            (x + s * 0.22, y + s * 0.65), (x, y + s * 0.65)]
    g.fill_poly(body, '#e8e8e8')
    g.stroke_poly(body, '#3a3a3a', max(1.0, s * 0.05), closed=True)
    for k in (1, 2, 3):
        g.stroke_arc(x + s * 0.5, y + s * 0.5, s * 0.14 * k + s * 0.04, -0.7, 0.7, '#2a6fd6', max(1.2, s * 0.07))


def draw_desktop(text='reading screens', title='Narrator', clock='10:23 PM', w=PX, h=None, ss=SS):
    """drawDesktop: sky, clouds, the hill, icons, the taskbar with Start + tray, the Narrator dialog with the text,
    a pointer, as an RGBA PIL image w x h (the 1024 x 768 drawing at the top of the 1024 x 778 canvas)."""
    h = h or H
    g = Canvas2D(W, H, ss)
    # sky
    g.fill_rect(0, 0, W, H, Gradient(0, H * 0.7, [(0, '#1f5fd6'), (0.55, '#4d93ec'), (1, '#a9d2fa')]))
    # soft clouds (seeded, deterministic), each ellipse blurred by the canvas filter blur(10px)
    r = rng(2001)
    for _ in range(14):
        cx, cy, rw = r() * W, 60 + r() * 260, 60 + r() * 150
        a = 0.25 + r() * 0.35
        for k in range(5):
            g.fill_ellipse(cx + (k - 2) * rw * 0.35, cy + (r() - 0.5) * 18, rw * 0.45, rw * 0.22,
                           (255, 255, 255, a), blur=10.0)

    # a far hill and the near green hill (our own gentle rise, left to right)
    def hill(y0, amp, ph, c0, c1):
        pts = [(0, H)]
        for x in range(0, W + 1, 8):
            pts.append((x, y0 - amp * math.sin((x / W) * math.pi * 0.9 + ph)
                        - amp * 0.25 * math.sin((x / W) * 5.1 + ph * 3)))
        pts.append((W, H))
        g.fill_poly(pts, Gradient(y0 - amp, H, [(0, c0), (1, c1)]))
    hill(H * 0.66, 38, 1.9, '#5f9b3a', '#2f6a1e')
    hill(H * 0.78, 120, 0.55, '#7fcf3f', '#2e7d18')
    # light on the grass: a few streaks
    for _ in range(60):
        x, y = r() * W, H * 0.62 + r() * H * 0.3
        g.stroke_poly([(x, y), (x + 3, y - 7)], '#eaffc0', 2, alpha=0.12)

    # desktop icons
    def icon(x, y, kind, label):
        if kind == 'pc':
            g.fill_rect(x + 6, y + 4, 36, 26, '#dfe6ee')
            g.fill_rect(x + 9, y + 7, 30, 20, '#3b82d8')
            g.fill_rect(x + 16, y + 31, 16, 5, '#c9d2dc')
            g.fill_rect(x + 10, y + 36, 28, 4, '#c9d2dc')
        elif kind == 'docs':
            g.fill_poly([(x + 4, y + 10), (x + 18, y + 10), (x + 22, y + 6), (x + 44, y + 6), (x + 44, y + 38),
                         (x + 4, y + 38)], '#f4d56b')
            g.fill_rect(x + 12, y + 12, 24, 20, '#ffffff')
        else:
            g.fill_poly([(x + 10, y + 10), (x + 38, y + 10), (x + 34, y + 40), (x + 14, y + 40)], '#e8eef4')
            for k in range(3):
                g.stroke_poly([(x + 17 + k * 7, y + 14), (x + 18 + k * 6, y + 37)], '#88aaaa', 2)
        g.text(label, x + 25, y + 57, TAHOMA, 13, '#000000', 'center')
        g.text(label, x + 24, y + 56, TAHOMA, 13, '#ffffff', 'center')
    icon(18, 18, 'pc', 'My Computer')
    icon(18, 98, 'docs', 'My Documents')
    icon(18, H - TB - 90, 'bin', 'Recycle Bin')
    # taskbar
    g.fill_rect(0, H - TB, W, TB, Gradient(H - TB, H, [(0, '#3f8cf3'), (0.12, '#2463da'), (0.9, '#1c4fc4'),
                                                         (1, '#163e9e')]))
    # start button: green pill with the flag and an italic "start"
    pill = [(0, H - TB), (88, H - TB)] + quad((88, H - TB), (106, H - TB), (106, H - TB / 2)) \
        + quad((106, H - TB / 2), (106, H), (88, H)) + [(0, H)]
    g.fill_poly(pill, Gradient(H - TB, H, [(0, '#5eb95e'), (0.2, '#3c9a3c'), (1, '#2d7d2d')]))
    draw_flag(g, 10, H - TB + 5, 22, 20)
    g.text('start', 38, H - 9, '"Franklin Gothic Medium", Trebuchet MS, Tahoma, sans-serif', 21, '#ffffff', 'left',
           bold=True, italic=True, shadow=('rgba(0,0,0,0.45)', 1, 1))
    # the running task + tray + clock
    g.fill_poly(rr(118, H - TB + 3, 160, TB - 6, 3), '#3c80ef')
    g.text(title, 142, H - 11, 'Tahoma, sans-serif', 12, '#ffffff', 'left')
    g.fill_ellipse(130, H - TB / 2, 5, 5, '#e8eaf0')
    g.fill_rect(W - 118, H - TB, 118, TB, Gradient(H - TB, H, [(0, '#16a7f4'), (1, '#0d7fd8')]))
    g.text(clock, W - 10, H - 10, 'Tahoma, sans-serif', 12, '#ffffff', 'right')
    g.fill_ellipse(W - 96, H - TB / 2, 5, 5, '#ffd24a')
    g.fill_rect(W - 82, H - TB / 2 - 5, 9, 10, '#e6e6e6')
    # the dialog (big enough to read on film)
    dw, dh = 600, 250
    dx, dy = int(round((W - dw) / 2)) + 40, 188
    frame = rr(dx, dy, dw, dh, 8)
    g.fill_poly(frame, '#0831d9', shadow=('rgba(0,0,0,0.35)', 16, 5, 6))
    g.fill_poly(rr(dx, dy, dw, 40, 8), Gradient(dy, dy + 34, [(0, '#3a8cf6'), (0.15, '#0a5ee4'),
                                                                    (0.85, '#0550d6'), (1, '#0342b8')]))
    g.fill_rect(dx, dy + 20, dw, 20, Gradient(dy, dy + 34, [(0, '#3a8cf6'), (0.15, '#0a5ee4'), (0.85, '#0550d6'),
                                                            (1, '#0342b8')]))
    g.fill_rect(dx + 4, dy + 38, dw - 8, dh - 42, '#ece9d8')
    g.text(title, dx + 34, dy + 27, 'Tahoma, Trebuchet MS, sans-serif', 17, '#ffffff', 'left', bold=True,
           shadow=('rgba(0,0,0,0.5)', 1, 1))
    draw_speaker_glyph(g, dx + 10, dy + 11, 18)
    g.fill_poly(rr(dx + dw - 32, dy + 7, 25, 25, 4), '#e04a2a')
    g.stroke_poly([(dx + dw - 26, dy + 13), (dx + dw - 13, dy + 26)], '#ffffff', 3)
    g.stroke_poly([(dx + dw - 13, dy + 13), (dx + dw - 26, dy + 26)], '#ffffff', 3)
    draw_speaker_glyph(g, dx + 34, dy + 78, 64)
    # the message: large Tahoma, wrapped to the panel
    lines = []
    for para in (text or '').split('\n'):
        cur = ''
        for wd in re.split(r'\s+', para):
            tst = f'{cur} {wd}' if cur else wd
            if g.measure(tst, TAHOMA, 44, bold=True) > dw - 170 and cur:
                lines.append(cur)
                cur = wd
            else:
                cur = tst
        lines.append(cur)
    n = min(3, len(lines))
    for i, ln in enumerate(lines[:3]):
        g.text(ln, dx + 128, dy + 108 + i * 52 - (n - 1) * 18, TAHOMA, 44, '#111111', 'left', bold=True)
    # OK button
    ok = rr(dx + dw - 132, dy + dh - 52, 110, 34, 4)
    g.fill_poly(ok, '#f4f3ee')
    g.stroke_poly(ok, '#003c74', 1.5, closed=True)
    g.text('OK', dx + dw - 77, dy + dh - 29, 'Tahoma, sans-serif', 17, '#000000', 'center')
    # pointer
    px, py = dx + dw - 70, dy + dh - 20
    arrow = [(px, py), (px, py + 22), (px + 5, py + 17), (px + 9, py + 26), (px + 12, py + 25), (px + 8, py + 16),
             (px + 15, py + 16)]
    g.fill_poly(arrow, '#ffffff')
    g.stroke_poly(arrow, '#000000', 1.2, closed=True)
    return g.image(w, h)


# ------------------------------------------------------------------------------------------------- the machine ---
class DesktopScreen:
    """parts['screen']: mesh (the tube), set_text(s), text, power (the raster's channel), screen (the EraScreen)."""

    def __init__(self, machine, mesh, screen, power):
        self.machine, self.mesh, self.screen, self.power = machine, mesh, screen, power

    def set_text(self, s):
        """The dialog's message (\\n for a second line, 3 lines at most after wrapping). Like the engine, the drawing
        changes at the next update(t)."""
        t = '' if s is None else str(s)
        st = self.machine._st
        if t != st['text']:
            st['text'], st['dirty'] = t, True

    @property
    def text(self):
        return self.machine._st['text']

    def __repr__(self):
        return f'<DesktopScreen {self.text!r}>'


def cloth_material(name, src_mat, cloth_obj, root, prop='speaker'):
    """The speaker cloth: its baked weave (a copy of the glTF material), lit from within by root[prop]: warm light
    behind the weave, brightest over each driver (a cone 5 to 75 mm round the two drivers' centres, 12 mm above
    the cloth's centroid on each side) and falling off to the panel edges; the open threads (dark in the scan) let
    more of it through. emission = lin('#ffae5c') x clamp(1 - 2.2 R, 0.25, 1) x (0.85 cone + 0.15) x level x 1.25."""
    m = baked_material(src_mat, copy=True)
    m.name = name
    t = m.node_tree
    b = next(n for n in t.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    # the baked colour map (three's material.map): the image feeding Base Color, else the one named *_color
    col_tex = None
    lk = next((x for x in t.links if x.to_socket == b.inputs['Base Color']), None)
    while lk is not None and col_tex is None:
        n = lk.from_node
        if n.bl_idname == 'ShaderNodeTexImage':
            col_tex = n
        else:
            lk = next((x for s in n.inputs for x in s.links), None)
    if col_tex is None:
        col_tex = next((n for n in t.nodes if n.bl_idname == 'ShaderNodeTexImage' and n.image
                        and 'color' in n.image.name.lower()), None)
    for x in list(b.inputs['Emission Color'].links) + list(b.inputs['Emission Strength'].links):
        t.links.remove(x)
    nb = Nodes(t, x=-1600, y=-600)
    co = np.empty(len(cloth_obj.data.vertices) * 3)
    cloth_obj.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    mid = (co[:, 0].min() + co[:, 0].max()) / 2
    centres = [co[co[:, 0] < mid].mean(axis=0), co[co[:, 0] >= mid].mean(axis=0)]
    tc = nb.node('ShaderNodeTexCoord')
    dists = []
    for c in centres:
        dists.append(nb.vmath('DISTANCE', tc.outputs['Object'], (float(c[0]), float(c[1]), float(c[2]) + 0.012)))
    cone = nb.smoothstep(0.075, 0.005, nb.min(dists[0], dists[1]))
    if col_tex is not None:                    # the colour map's R, linear (three decodes the sRGB map too)
        sep = nb.node('ShaderNodeSeparateColor')
        t.links.new(col_tex.outputs['Color'], sep.inputs[0])
        red = sep.outputs['Red']
    else:
        red = 0.0
    weave = nb.max(nb.min(nb.sub(1.0, nb.mul(red, 2.2)), 1.0), 0.25)
    level = nb.driven(root, prop, 0.0, 'level')
    k = nb.mul(nb.mul(nb.mul(weave, nb.add(nb.mul(cone, 0.85), 0.15)), level), 1.25)
    b.inputs['Emission Color'].default_value = (*lin('#ffae5c'), 1.0)
    nb.link(k, b.inputs['Emission Strength'])
    return m


class Desktop2001(Machine):
    """The built 2001 desktop (see the module doc). update(t, state): power, voice, text."""

    def __init__(self, *, title='Narrator', clock='10:23 PM', text=None, **kw):
        super().__init__('desktop2001', **kw)
        g = self.group
        self.title, self.clock = title, clock
        mon, tower, kb, spk = (self.part(n) for n in ('pc_mon', 'pc_tower', 'pc_kb', 'pc_spk'))
        # speaker cloth: its baked weave, lit from within by the voice
        cloth = self.part('glowcloth_spk', runtime=True)
        ch_spk = self.channel('speaker', 0.0, 'the light behind the speaker cloth (0.8 voice when on)')
        src_mat = self.src['glowcloth_spk'].data.materials[0]
        self.assign(cloth, self.material(cloth_material(f'{g.name}.cloth', src_mat, cloth, g)))
        leds = {}
        for name, col, lens in LEDS:
            key = name[4:]
            ch = self.channel(name, 0.0, f'the {key} LED level')
            m = self.part(name, runtime=True)
            self.assign(m, self.material(led_material(f'{g.name}.{name}', col, g, name, lens)))
            leds[key] = Lamp(key, m, ch)
        # the CRT: the desktop canvas (1024 x 778) under the glass
        power = self.channel('power', 1.0, 'the raster (CRT switch-on as it rises)')
        self.channel('gain', 1.0, 'the raster brightness (1 + 0.25 voice)')
        self._st = {'text': 'reading screens' if text is None else str(text), 'dirty': False}
        scr = self.era_screen(TW, TH, PX, self._draw)
        tube = self.make_tube(scr, gain_k=0.95, glass='#0c0e0e', rough=0.3, coat_rough=0.03, barrel=0.012, scan=0,
                              corner=0.02, vignette=0.08, crt_on=True, tube_height=TH)
        self.parts = {'monitor': mon, 'tower': tower, 'keyboard': kb, 'speakers': spk,
                      'screen': DesktopScreen(self, tube, scr, power), 'leds': leds,
                      'speaker': Lamp('speaker', cloth, ch_spk)}

    def _draw(self, w, h):
        return draw_desktop(self._st['text'], self.title, self.clock, w, h)

    @staticmethod
    def drive_flicker(t):
        """The drive light's flicker while it speaks (deterministic in t): 1 or 0.1."""
        return 1.0 if (math.sin(t * 61.0) + math.sin(t * 37.3 + 1.7)) > 0.6 else 0.1

    def _update(self, t, st, f, ctx):
        p = max(0.0, float(st['power'] if st.get('power') is not None else 1.0))
        v = max(0.0, min(1.0, float(st.get('voice') or 0.0)))
        on = p > 0.02
        leds, kw = self.parts['leds'], {'ctx': ctx, 'frame': f}
        self.key('power', p, frame=f, ctx=ctx)
        self.key('gain', 1.0 + 0.25 * v, frame=f, ctx=ctx)
        self.parts['speaker'].set(v * 0.8 if on else 0.0, **kw)
        leds['mon'].set(1.0 if on else 0.15, **kw)            # amber-ish standby is out of scope: dim green
        leds['tw_power'].set(1.0, **kw)
        leds['spk'].set(1.0, **kw)
        leds['kb0'].set(1.0, **kw)
        leds['kb1'].set(0.0, **kw)
        leds['kb2'].set(0.0, **kw)
        leds['tw_hdd'].set(self.drive_flicker(t) if on and v > 0.15 else 0.02, **kw)
        leds['tw_cd'].set(0.0, **kw)
        if 'text' in st:                                              # JS: state.text !== undefined
            self.parts['screen'].set_text(st['text'])
        if self._st['dirty']:
            self.screens[0].redraw(f)
            self._st['dirty'] = False


def build(opts=None, **kw):
    """build(THREE, opts) -> the desktop: group (its root Empty), parts, update(t, state), dispose(). Options:
    title (the dialog's and the task's title, 'Narrator'), clock ('10:23 PM'), text (the first message, 'reading
    screens'); and the Blender edition's plumbing: name, scene, collection, screen_dir, ctx, interpolation."""
    o = dict(opts or {})
    o.update(kw)
    return Desktop2001(**o)


__all__ = ['build', 'Desktop2001', 'DesktopScreen', 'draw_desktop', 'draw_flag', 'draw_speaker_glyph',
           'cloth_material', 'TW', 'TH', 'LEDS']
