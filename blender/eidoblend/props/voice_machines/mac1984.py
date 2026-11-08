"""eidoblend.props.voice_machines.mac1984: the beige 1984 all-in-one compact (9" 1-bit screen, floppy slot,
carrying-handle groove on top), its small keyboard and one-button mouse, for DAISY's museum of voices. Port of
eidoverse/props/voice_machines/mac1984.js.

Era marks as homage, drawn by us: the six-band apple badge on the front (baked into the pack's maps) and a 1-bit
apple in the menu bar.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props.voice_machines import mac1984
    mac = mac1984.build(text='hello')               # options: title ('Note'), text ('hello')
    mac.group.location = (0.0, 0.0, 0.74)
    mac.parts['screen'].set_text('hello')            # crisp 1-bit pixel text in a window on the dithered desktop
    # per frame, in time order: keyed at the frame of t
    mac.update(t, {'power': 1.0, 'voice': loudness(t)})
    #   power = the raster (CRT switch-on); voice = its own voice: the raster brightens, the speaker vents glow

Screen: a 512 x 342 1-bit canvas at native resolution (72 dpi -> 180.6 x 120.7 mm), magnified with nearest
filtering and mipmapped when small (the 50 % desktop dither averages to grey instead of shimmering). Text is drawn
small with a hinted UI font, thresholded to 1 bit, and blown up by an integer factor.
Geometry + materials: the pack's mac1984.glb (models/voice_machines_src/build_mac1984.py): the front bezel moulding
(drafted screen recess, floppy slot, recessed badge, brightness thumbwheel), the rear housing (handle groove, vents,
port panel with D-sub shells), the inset foot with the keyboard jack; the small keyboard (58 dished keys with
legends, coiled cord); the mouse and its cord; AmbientCG scans, AO grime, edge wear, yellowing baked.
Real size: 344 x 246 x 276 mm. Metres, +Z up, on z = 0 of its root, the front toward -Y.
parts: computer (the body), keyboard, mouse, screen (mesh, set_text, text, power, screen), speaker (mesh, set(v)).
"""
from __future__ import annotations

import math

import numpy as np

from . import Lamp, Machine, font, glow_material, js_round, metal_material

TW, TH = 0.200, 0.152                 # the tube's glass (m): its UV square
RW, RH = 0.1806, 0.1207               # the 512 x 342 raster at 72 dpi
WP, HP = 512, 342
U0, V0 = (TW - RW) / 2 / TW, (TH - RH) / 2 / TH
WINDOW = (U0, V0 + 0.004, 1 - U0, 1 - V0 + 0.004)   # where the raster sits on the glass (UV), a hair high
UI = ('Tahoma, Verdana, Arial, sans-serif', 12)
ICON_FONT = ('Tahoma, Verdana, Arial, sans-serif', 10)
TEXT_FONT = ('Tahoma, Verdana, Arial, sans-serif', 13)
INK, PAPER = 18, 236                  # the 1-bit levels (sRGB 0..255)
APPLE = ['.......##....', '......##.....', '..####.####..', '.###########.', '###########..', '##########...',
         '##########...', '##########...', '###########..', '############.', '.###########.', '.###########.',
         '..#########..', '...###.###...']
ARROW = ['1', '11', '101', '1001', '10001', '100001', '1000001', '10000001', '100000001', '1000011111', '1001001',
         '101001', '11  1001', '1   1001', '     1001', '     111']
MENUS = ('File', 'Edit', 'View', 'Special')


class Bits:
    """The JS bits(s, font): the string drawn black on white in a canvas max(8, 16 n + 8) x 32 at the baseline
    y = 22 (x = 1), thresholded (R < 110 -> 1). w = ceil(the text's width) + 2."""

    def __init__(self, s, fam_px):
        from PIL import Image, ImageDraw
        fam, px = fam_px
        f = font(fam, px, bold=True)
        cw = max(8, len(s) * 16 + 8)
        img = Image.new('L', (cw, 32), 255)
        if s:
            ImageDraw.Draw(img).text((1, 22), s, font=f, fill=0, anchor='ls')
        self.w = int(math.ceil(f.getlength(s))) + 2 if s else 2
        a = np.asarray(img)
        rows = np.zeros((32, self.w), bool)
        n = min(self.w, cw)
        rows[:, :n] = a[:, :n] < 110
        self.rows = rows
        self.base = 22


class OneBit:
    """The 512 x 342 bit plane drawMac paints (1 = black), with its rect / frame / blit."""

    def __init__(self):
        y, x = np.mgrid[0:HP, 0:WP]
        self.px = ((x + y) & 1).astype(np.uint8)            # the 50 % desktop

    def rect(self, x0, y0, w, h, v):
        xa, xb, ya, yb = max(0, x0), min(WP, x0 + w), max(0, y0), min(HP, y0 + h)
        if xb > xa and yb > ya:
            self.px[ya:yb, xa:xb] = v

    def frame(self, x0, y0, w, h):
        self.rect(x0, y0, w, 1, 1)
        self.rect(x0, y0 + h - 1, w, 1, 1)
        self.rect(x0, y0, 1, h, 1)
        self.rect(x0 + w - 1, y0, 1, h, 1)

    def blit(self, b, x0, y_base, scale, v=1):
        ys, xs = np.nonzero(b.rows)
        for y, x in zip(ys.tolist(), xs.tolist()):
            self.rect(x0 + x * scale, y_base + (y - b.base) * scale, scale, scale, v)

    def image(self, w=WP, h=HP):
        from PIL import Image
        g = np.where(self.px == 1, INK, PAPER).astype(np.uint8)
        a = np.zeros((h, w, 4), np.uint8)
        hh, ww = min(h, HP), min(w, WP)
        a[:hh, :ww, :3] = g[:hh, :ww, None]
        a[:hh, :ww, 3] = 255
        return Image.fromarray(a, 'RGBA')


def draw_mac(text='hello', title='Note', w=WP, h=HP):
    """drawMac: the 1-bit screen (the 50 % desktop, the menu bar with the apple, disk + trash icons, a window with
    the text, up to 3 lines, blown up by the largest integer factor that fits) as an RGBA PIL image."""
    P = OneBit()
    P.rect(0, 0, WP, 19, 0)
    P.rect(0, 19, WP, 1, 1)                                      # the menu bar
    for y, row in enumerate(APPLE):
        for x, c in enumerate(row):
            if c == '#':
                P.rect(11 + x, 3 + y, 1, 1, 1)
    mx = 38
    for m in MENUS:
        b = Bits(m, UI)
        P.blit(b, mx, 15, 1)
        mx += b.w + 14

    def icon(x0, y0, kind, label):
        P.rect(x0, y0, 32, 32, 0)
        if kind == 'disk':
            P.frame(x0 + 3, y0 + 3, 26, 26)
            P.rect(x0 + 8, y0 + 3, 16, 10, 1)
            P.rect(x0 + 18, y0 + 5, 4, 6, 0)
            P.frame(x0 + 7, y0 + 17, 18, 12)
        else:
            P.frame(x0 + 7, y0 + 8, 18, 22)
            P.rect(x0 + 5, y0 + 6, 22, 2, 1)
            P.rect(x0 + 13, y0 + 3, 6, 3, 1)
            for i in range(3):
                P.rect(x0 + 11 + i * 4, y0 + 12, 1, 14, 1)
        b = Bits(label, ICON_FONT)
        P.rect(x0 + 16 - (b.w >> 1) - 2, y0 + 34, b.w + 4, 13, 0)
        P.blit(b, x0 + 16 - (b.w >> 1), y0 + 44, 1)
    icon(WP - 52, 26, 'disk', 'System Disk')
    icon(WP - 52, HP - 58, 'trash', 'Trash')
    lines = (text or '').split('\n')[:3]
    bl = [Bits(ln, TEXT_FONT) for ln in lines]
    max_w = max([8] + [b.w for b in bl])
    win_w, win_h = 330, 170
    wx, wy = js_round((WP - win_w) / 2) - 18, 64
    scale = 1
    for s in range(6, 0, -1):
        if max_w * s <= win_w - 36 and len(lines) * 16 * s <= win_h - 40:
            scale = s
            break
    P.rect(wx + 2, wy + 2, win_w, win_h, 1)                      # the window's shadow
    P.rect(wx, wy, win_w, win_h, 0)
    P.frame(wx, wy, win_w, win_h)
    for i in range(6):
        P.rect(wx + 2, wy + 3 + i * 2, win_w - 4, 1, 1)          # the title bar's stripes
    P.rect(wx, wy + 18, win_w, 1, 1)
    P.rect(wx + 8, wy + 4, 11, 11, 0)
    P.frame(wx + 8, wy + 4, 11, 11)                              # the close box
    tb = Bits(title, UI)
    P.rect(wx + (win_w >> 1) - (tb.w >> 1) - 6, wy + 2, tb.w + 12, 15, 0)
    P.blit(tb, wx + (win_w >> 1) - (tb.w >> 1), wy + 14, 1)
    line_h = 16 * scale
    total_h = len(lines) * line_h
    for i, b in enumerate(bl):
        bx = wx + js_round((win_w - b.w * scale) / 2)
        by = wy + 19 + js_round((win_h - 19 - total_h) / 2) + i * line_h + js_round(12 * scale)
        P.blit(b, bx, by, scale)
    P.rect(wx + win_w - 16, wy + 18, 1, win_h - 18, 1)           # the scroll bar
    P.rect(wx + win_w - 16, wy + win_h - 16, 16, 1, 1)
    ax, ay = wx + win_w - 60, wy + win_h - 30                    # the pointer
    for y, row in enumerate(ARROW):
        for x, c in enumerate(row):
            if c == '1':
                P.rect(ax + x, ay + y, 1, 1, 1)
            elif c == '0':
                P.rect(ax + x, ay + y, 1, 1, 0)
    return P.image(w, h)


class MacScreen:
    """parts['screen']: mesh (the tube), set_text(s), text, power (the raster's channel), screen (the EraScreen)."""

    def __init__(self, machine, mesh, screen, power):
        self.machine, self.mesh, self.screen, self.power = machine, mesh, screen, power

    def set_text(self, s):
        """The window's text (\\n between lines, 3 at most). Like the engine, the drawing changes at the next
        update(t)."""
        t = '' if s is None else str(s)
        st = self.machine._st
        if t != st['text']:
            st['text'], st['dirty'] = t, True

    @property
    def text(self):
        return self.machine._st['text']

    def __repr__(self):
        return f'<MacScreen {self.text!r}>'


class Mac1984(Machine):
    """The built Macintosh (see the module doc). update(t, state): power, voice, text."""

    def __init__(self, *, title='Note', text=None, **kw):
        super().__init__('mac1984', **kw)
        g = self.group
        self.title = title
        body, kb, mouse = self.part('mac_body'), self.part('mac_kb'), self.part('mac_mouse')
        metal = self.material(metal_material(f'{g.name}.metal', '#bdbdc2', 0.32))
        for o in [self.part(n, runtime=True) for n in sorted(self.src) if n.startswith('metal_')]:
            self.assign(o, metal)
        glow_mesh = self.part('glow_vents', runtime=True)
        spk = self.channel('speaker', 0.0, 'the glow behind the vents (0.8 voice when on)')
        self.assign(glow_mesh, self.material(glow_material(f'{g.name}.glow', '#ffe2b0', g, 'speaker')))

        # the tube: black glass, the 512 x 342 raster in its middle
        power = self.channel('power', 1.0, 'the raster (CRT switch-on as it rises)')
        self.channel('gain', 1.0, 'the raster brightness (1 + 0.3 voice)')
        self._st = {'text': 'hello' if text is None else str(text), 'dirty': False}
        scr = self.era_screen(RW, RH, WP, self._draw, nearest=True)
        tube = self.make_tube(scr, gain_k=0.82, window=WINDOW, glass='#0b0c0c', rough=0.36, coat_rough=0.04,
                              barrel=0.025, scan=342, scan_amt=0.16, corner=0.035, vignette=0.12, tint='#eef3ff',
                              crt_on=True, tube_height=TH)
        self.parts = {'computer': body, 'keyboard': kb, 'mouse': mouse, 'screen': MacScreen(self, tube, scr, power),
                      'speaker': Lamp('speaker', glow_mesh, spk)}

    def _draw(self, w, h):
        return draw_mac(self._st['text'], self.title, w, h)

    def _update(self, t, st, f, ctx):
        p = max(0.0, float(st['power'] if st.get('power') is not None else 1.0))
        v = max(0.0, min(1.0, float(st.get('voice') or 0.0)))
        self.key('power', p, frame=f, ctx=ctx)
        self.key('gain', 1.0 + 0.3 * v, frame=f, ctx=ctx)
        self.parts['speaker'].set(v * 0.8 if p > 0.01 else 0.0, ctx=ctx, frame=f)
        if 'text' in st:                                              # JS: state.text !== undefined
            self.parts['screen'].set_text(st['text'])
        if self._st['dirty']:
            self.screens[0].redraw(f)
            self._st['dirty'] = False


def build(opts=None, **kw):
    """build(THREE, opts) -> the Macintosh: group (its root Empty), parts, update(t, state), dispose(). Options:
    title (the window's title, 'Note'), text (the first text, 'hello'); and the Blender edition's plumbing: name,
    scene, collection, screen_dir, ctx, interpolation."""
    o = dict(opts or {})
    o.update(kw)
    return Mac1984(**o)


__all__ = ['build', 'Mac1984', 'MacScreen', 'draw_mac', 'Bits', 'OneBit', 'TW', 'TH', 'RW', 'RH', 'WINDOW']
