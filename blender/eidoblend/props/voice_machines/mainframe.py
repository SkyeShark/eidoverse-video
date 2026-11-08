"""An IBM 7090-era computer room at Bell Labs, 1961 (mainframe.js, ported): the room that sang "Daisy Bell".

Kelly, Lochbaum and Mathews made a mainframe sing "Daisy Bell" in 1961 (the LP credits a 7090). The pack's hero asset
(mainframe.glb): four 729-style tape drives (recessed reel deck behind smoked glass, door-leaf seams, header control
strip, blue vacuum columns behind a glass door, back louvres; reels, head block, capstans, guides, tape runs),
two-tone grey/blue frame cabinets, a 7151-style operator console (recessed lamp field with brass bezels, paddle keys,
emergency pull) and floor cables into a grommet. Layered materials (the era-1 kit in voder.py): AmbientCG sets on UV0
+ baked AO/edge/cavity masks on UV1 + curvature wear. Era logos are canvas homage: the striped IBM wordmark on the drive
plates and the console nameplate (the striped mark is 1972; a 1961 room wore the solid 1956 one).

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props.voice_machines import mainframe

    room = mainframe.build()                      # -> Mainframe: group (root Empty), parts, update, animate
    room.update(t, {'tape_speed': s, 'voice': v, 'power': 1}, ctx=ctx)     # per frame, IN TIME ORDER
    room.animate(lambda t: {'tapeSpeed': 1.0 if t < 4 else max(0, 1 - (t - 4) / 2) ** 1.6, 'voice': 0.4})

update(t, state):
  tape_speed  1 = nominal (about 1.1 m/s of tape). The reels follow it EXACTLY: speed is integrated frame to frame
              (trapezoid), so the film's curve (1, then (1-x)^1.6 to 0) is the reels' angular speed. Negative rewinds.
  tape_stop   {'at', 'duration', 'curve'} alternative: analytic in t (synthkit fx.tape_stop).
  tape_pos    metres of tape: overrides both.
  voice       0..1, this era's voice loudness: the register lamps sparkle and brighten with it (the machine visibly
              sings); the machine clock still freezes when the tape stops.
  power       0..1: every lamp, digit window and indicator (the lights dying).
Every value is keyed at the frame of t (see voder.Machine): the reels' angles, the vacuum-column loops, and the lamp
uniforms (root properties clock, t, power, voice), which the lamp shader reads through drivers, so the lamp logic runs
in the shader at any frame of the saved .blend, as it ran on the GPU.
parts: reels [{pivot, drive, side, pack_radius}], lamps {bulbs, lenses, status, cabinets, count, uniforms}, console
(node; re-place freely), row, loops [{runs, bend, index}], uniforms {clock, power, voice, loops (the 8 depths)}.
Metres, Blender Z up, floor z = 0, facing -Y. The row is about 4.6 m wide; the console stands front right.

Blender translations: the engine merged each reel body's primitives into one mesh (one draw call); Blender's importer
already makes one mesh per node, so each body takes the reel material whole. The vacuum-column loops were one mesh
deformed in the vertex stage from a uniform array; the deformation is affine per part (the two runs stretch from the
column mouth, the U-bend slides), so here each loop is two objects whose keyed scale and location are that same map.
"""

from __future__ import annotations

import math
import os
import re

import numpy as np
import bpy
from mathutils import Matrix, Quaternion, Vector

from . import voder as K
from ... import common

clamp01 = K.clamp01
v3 = K.v3
TAPE_MPS = 1.1
LOOP_BASE = 0.47
MOUTH = 0.95
SPEED_MULT = [1.0, 0.72, -1.35, 0.55, 0.9, -0.6]
SANS = '"Bahnschrift", "Segoe UI", Arial, sans-serif'

MACHINE = {'year': 1961, 'title': 'IBM 7090-era computer room (the Bell Labs "Daisy Bell")', 'era': 1,
           'footprint': (4.58, 2.81, 1.87), 'center': (0.0, -0.64)}

# lens atlas: 8 x 4 cells: lamp lenses (0-4), buttons (8-12), digits (16-25), console status (26-29), column (5-7, 13)
LENS = [('SELECT', '#e8d25a'), ('READY', '#f1eee4'), ('FILE\nPROTECT', '#d8472f'), ('HIGH\nDENSITY', '#f1eee4'),
        ('TAPE\nINDICATE', '#d8472f')]
BTN = ['LOAD\nREWIND', 'START', 'CHANGE\nDENSITY', 'UNLOAD', 'RESET']
STATUS = [('PROGRAM\nSTOP', '#b8352a'), ('I/O\nCHECK', '#d8d6cf'), ('READY', '#e9e6dc'), ('AUTO-\nMATIC', '#e6cf57')]
COLS = [('POWER\nON', '#b8352a'), ('COMP\nON', '#d8d6cf'), ('TEMP', '#d8d6cf'), ('CHECK', '#d8d6cf')]
ATL_COLS, ATL_ROWS = 8, 4


# ------------------------------------------------------------------------------------------------- the art ---
def draw_ibm(ctx, x, y, h, ink, bg, stripes=8):
    """mainframe.js drawIBM: the striped homage of the IBM wordmark, from rectangles and arcs (no font).
    Returns its width."""
    u = h / 10
    serif, stem = u * 2.0, u * 3.0

    def slab(x0, w):
        ctx.fillRect(x0, y, w, serif)
        ctx.fillRect(x0, y + h - serif, w, serif)
    ctx.fillStyle = ink
    Iw = u * 5.6                                                      # I
    slab(x, Iw)
    ctx.fillRect(x + (Iw - stem) / 2, y, stem, h)
    Bx, Bw = x + Iw + u * 1.2, u * 8.4                                # B
    ctx.fillRect(Bx, y, Bw - u * 2.4, serif)
    ctx.fillRect(Bx, y + h - serif, Bw - u * 2.4, serif)
    ctx.fillRect(Bx + u * 1.3, y, stem, h)
    ctx.fillRect(Bx, y + h / 2 - u * 0.9, Bw - u * 2.6, u * 1.8)
    for cy, r in ((y + h * 0.26, h * 0.26), (y + h * 0.735, h * 0.265)):
        ctx.beginPath()
        ctx.arc(Bx + Bw - u * 2.4 - r * 0.05, cy, r, -math.pi / 2, math.pi / 2)
        ctx.closePath()
        ctx.fill()
        ctx.fillStyle = bg
        ctx.beginPath()
        ctx.arc(Bx + Bw - u * 2.4 - r * 0.05, cy, r - stem * 0.95, -math.pi / 2, math.pi / 2)
        ctx.closePath()
        ctx.fill()
        ctx.fillRect(Bx + u * 1.3 + stem, cy - (r - stem * 0.95), Bw - u * 2.4 - u * 1.3 - stem - r * 0.05,
                     2 * (r - stem * 0.95))
        ctx.fillStyle = ink
    Mx, Mw = Bx + Bw + u * 1.2, u * 11.5                              # M
    ctx.fillRect(Mx, y, u * 3.4, serif)
    ctx.fillRect(Mx + Mw - u * 3.4, y, u * 3.4, serif)
    ctx.fillRect(Mx, y + h - serif, u * 4.2, serif)
    ctx.fillRect(Mx + Mw - u * 4.2, y + h - serif, u * 4.2, serif)
    ctx.fillRect(Mx + u * 0.9, y, u * 2.1, h)
    ctx.fillRect(Mx + Mw - u * 3.2, y, stem, h)
    ctx.beginPath()
    ctx.moveTo(Mx + u * 0.9, y)
    ctx.lineTo(Mx + u * 3.4, y)
    ctx.lineTo(Mx + Mw / 2 + u * 0.8, y + h * 0.78)
    ctx.lineTo(Mx + Mw - u * 3.4, y)
    ctx.lineTo(Mx + Mw - u * 3.2 + stem, y)
    ctx.lineTo(Mx + Mw - u * 3.2 + stem, y + u * 0.1)
    ctx.lineTo(Mx + Mw / 2 + u * 0.8, y + h)
    ctx.lineTo(Mx + Mw / 2 - u * 0.6, y + h)
    ctx.closePath()
    ctx.fill()
    w_all = Mx + Mw - x
    g = h / (stripes * 1.7 - 0.7)                                     # stripes: background gaps across the mark
    s = g * 1.7
    ctx.fillStyle = bg
    for k in range(1, stripes):
        ctx.fillRect(x - 1, y + k * s - g, w_all + 2, g * 0.7)
    return w_all


def _draw_plate(ctx, w, h):
    ctx.fillStyle = '#0f1011'
    ctx.fillRect(0, 0, w, h)
    wI = draw_ibm(ctx, 40, 22, 84, '#e9e6de', '#0f1011')
    ctx.fillStyle = '#e9e6de'
    ctx.textBaseline = 'middle'
    ctx.font = f'600 70px {SANS}'
    ctx.fillText('729', 40 + wI + 34, 62)
    w729 = ctx.measureText('729').width
    ctx.font = f'600 34px {SANS}'
    ctx.fillText('II', 40 + wI + 34 + w729 + 8, 44)
    ctx.font = f'600 30px {SANS}'
    K.spaced_text(ctx, 'MAGNETIC TAPE UNIT', w - 300, 64, 3)


def _draw_name(ctx, w, h):
    ctx.fillStyle = '#f1efe9'
    ctx.fillRect(0, 0, w, h)
    ctx.fillStyle = '#0d1015'
    ctx.fillRect(0, 0, 390, h)
    wI = draw_ibm(ctx, 26, 18, 68, '#f1efe9', '#0d1015')
    ctx.fillStyle = '#f1efe9'
    ctx.textBaseline = 'middle'
    ctx.font = f'700 64px {SANS}'
    ctx.fillText('7090', 26 + wI + 28, 54)
    ctx.fillStyle = '#2a2d33'
    ctx.font = f'600 34px {SANS}'
    K.spaced_text(ctx, 'DATA PROCESSING SYSTEM', 700, 54, 4)


def _js_num(v):
    """String(v) of a JSON number as JavaScript prints it (integers without '.0')."""
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def _draw_panel(L):
    P = L['console']['panel']

    def draw(ctx, w, h):
        def px(x):
            return (x / P['w'] + 0.5) * w

        def py(z):
            return (0.5 - z / P['h']) * h
        ctx.fillStyle = '#d4d0c6'
        ctx.fillRect(0, 0, w, h)
        ctx.fillStyle = '#6d6f6f'
        ctx.fillRect(px(-0.705), py(0.205), px(-0.19) - px(-0.705), py(0.02) - py(0.205))
        ctx.fillStyle = '#4c4e50'
        ctx.fillRect(px(-0.19), py(0.205), px(0.70) - px(-0.19), py(0.02) - py(0.205))
        ctx.fillStyle = '#5a5b58'
        ctx.fillRect(px(-0.705), py(-0.005), px(0.70) - px(-0.705), py(-0.195) - py(-0.005))
        tones = ['#8b8d8c', '#3e3f41', '#8a8674']
        rows = {}
        for lamp in L['console']['lamps']:
            x, z, k = lamp[0], lamp[1], lamp[2]
            if k == 2:
                continue
            rows.setdefault(f'{z:.3f}', []).append(x)
        for zk, xs in rows.items():
            xs.sort()
            z = float(zk)
            dx = xs[1] - xs[0] if len(xs) > 1 else 0.03
            g = 0
            while g * 3 < len(xs):
                x0 = xs[g * 3] - dx / 2
                x1 = xs[min(len(xs) - 1, g * 3 + 2)] + dx / 2
                ctx.fillStyle = tones[g % 3]
                ctx.fillRect(px(x0), py(z + 0.022), px(x1) - px(x0), py(z - 0.028) - py(z + 0.022))
                g += 1
        ctx.fillStyle = '#e9e6dd'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'

        def lab(t, x, z, s=11):
            ctx.font = f'600 {s}px {SANS}'
            ctx.fillText(t, px(x), py(z))
        lab('I N D E X   A', -0.45, 0.181)
        lab('I N D E X   B', -0.45, 0.131)
        lab('I N D E X   C', -0.45, 0.081)
        lab('I N S T R U C T I O N', 0.27, 0.134)
        lab('I N S T R U C T I O N   C O U N T E R', 0.32, 0.081)
        lab('S T O R A G E', 0.0, -0.019)
        lab('A C C U M U L A T O R', 0.0, -0.079)
        lab('M - Q', 0.0, -0.139)
        for i, t in enumerate(['TRAP', 'SIMULATE', 'AC OVFL', 'MQ OVFL', 'R/W SEL', 'DIV CHK', 'SENSE 1', 'SENSE 2',
                               'SENSE 3', 'SENSE 4']):
            lab(t, -0.03 + i * 0.064, 0.19, 9)
        ctx.font = f'600 8px {SANS}'
        for lamp in L['console']['lamps']:
            x, z, k, a, b = lamp[:5]
            if k != 2:
                ctx.fillText(_js_num(math.fmod(b, 36)), px(x), py(z + 0.015))
        ctx.fillStyle = '#e1ded6'
        ctx.fillRect(px(-0.172), py(0.19), px(-0.058) - px(-0.172), py(0.07) - py(0.19))
        ctx.strokeStyle = '#2b2b2c'
        ctx.lineWidth = 3
        ctx.strokeRect(px(-0.705), py(0.205), px(0.70) - px(-0.705), py(-0.195) - py(0.205))
    return draw


def _draw_atlas(ctx, w, h):
    cw, ch = w / ATL_COLS, h / ATL_ROWS
    ctx.fillStyle = '#111'
    ctx.fillRect(0, 0, w, h)
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'

    def cell(i, bg, txt, fg, px):
        x, y = (i % ATL_COLS) * cw, (i // ATL_COLS) * ch
        ctx.fillStyle = bg
        ctx.fillRect(x + 2, y + 2, cw - 4, ch - 4)
        g = ctx.createLinearGradient(x, y, x, y + ch)
        g.addColorStop(0, 'rgba(255,255,255,0.12)')
        g.addColorStop(1, 'rgba(0,0,0,0.14)')
        ctx.fillStyle = g
        ctx.fillRect(x + 2, y + 2, cw - 4, ch - 4)
        ctx.fillStyle = fg
        ctx.font = f'600 {px}px {SANS}'
        lines = txt.split('\n')
        for k, ln in enumerate(lines):
            ctx.fillText(ln, x + cw / 2, y + ch / 2 + (k - (len(lines) - 1) / 2) * px * 1.05)
    for i, (t, c) in enumerate(LENS):
        cell(i, c, t, '#1a1712', 17)
    for i, t in enumerate(BTN):
        cell(8 + i, '#ecebe6', t, '#23211d', 16)
    for d in range(10):
        cell(16 + d, '#0b0b0b', str(d), '#f4f1e8', 50)
    for i, (t, c) in enumerate(STATUS):
        cell(26 + i, c, t, '#1b1814', 17)
    for i, (t, c) in enumerate(COLS):
        cell([5, 6, 7, 13][i], c, t, '#1b1814', 16)


# ------------------------------------------------------------------------------------- the lamp logic (shader) ---
def lamp_on_cpu(kind, a, b, clock, t, voice):
    """mainframe.js lampOn, evaluated on the CPU (float64) for checks: register bits, counter bits, steady/blink,
    and the voice's sparkle."""
    def fract(x):
        return x - math.floor(x)

    def hash11(x):
        p = fract(x * 0.1031)
        p = p * (p + 33.33)
        p = p * (p + p)
        return fract(p)

    def step(e, x):
        return 1.0 if x >= e else 0.0
    rate = 2.2 + (9.0 - 2.2) * hash11(a * 7.13 + 1.7)
    tr = clock * rate + hash11(a * 3.7 + 0.3) * 17.0
    k = math.floor(tr)

    def bit_at(kk):
        return step(0.5, hash11(kk * 1.37 + a * 57.1 + b * 13.97))
    reg = bit_at(k - 1) + (bit_at(k) - bit_at(k - 1)) * K.sstep(0.0, 0.22, fract(tr))
    n = math.floor(clock * 6.0 + a * 29.0)
    cnt = math.floor(n / 2 ** b) % 2.0
    blink = step(0.5, fract(t * b)) if b > 0.001 else 1.0
    steady = a * blink
    base = reg if kind < 0.5 else (cnt if kind < 1.5 else steady)
    sp = step(hash11(math.floor(t * 12.0) * 0.91 + a * 17.3 + b * 5.1), voice * 0.55) * step(kind, 1.5)
    return max(base, sp)


def _hash11(nb, x):
    p = nb.fract(nb.mul(x, 0.1031))
    p = nb.mul(p, nb.add(p, 33.33))
    p = nb.mul(p, nb.add(p, p))
    return nb.fract(p)


def lamp_on_nodes(nb, root):
    """mainframe.js lampOn as shader nodes: aLamp = (kind, a, b) from the mesh, clock / t / voice from the root's
    keyed properties. Returns the lamp's on level (0..1) socket."""
    kind, a, b = nb.sep(nb.attr('aLamp', 'Vector'))
    clock = nb.driven(root, 'clock', 0.0)
    T = nb.driven(root, 't', 0.0)
    voice = nb.driven(root, 'voice', 0.0)
    rate = nb.mix(2.2, 9.0, _hash11(nb, nb.madd(a, 7.13, 1.7)))
    tr = nb.add(nb.mul(clock, rate), nb.mul(_hash11(nb, nb.madd(a, 3.7, 0.3)), 17.0))
    k = nb.floor(tr)

    def bit_at(kk):
        return nb.step(0.5, _hash11(nb, nb.add(nb.add(nb.mul(kk, 1.37), nb.mul(a, 57.1)), nb.mul(b, 13.97))))
    b0, b1 = bit_at(nb.sub(k, 1.0)), bit_at(k)
    reg = nb.mix(b0, b1, nb.smoothstep(0.0, 0.22, nb.fract(tr)))
    n = nb.floor(nb.add(nb.mul(clock, 6.0), nb.mul(a, 29.0)))
    cnt = nb.mod(nb.floor(nb.div(n, nb.math('POWER', 2.0, b))), 2.0)
    blink = nb.select(nb.math('GREATER_THAN', b, 0.001), nb.step(0.5, nb.fract(nb.mul(T, b))), 1.0)
    steady = nb.mul(a, blink)
    base = nb.select(nb.math('LESS_THAN', kind, 0.5), reg, nb.select(nb.math('LESS_THAN', kind, 1.5), cnt, steady))
    hs = _hash11(nb, nb.add(nb.add(nb.mul(nb.floor(nb.mul(T, 12.0)), 0.91), nb.mul(a, 17.3)), nb.mul(b, 5.1)))
    sp = nb.mul(nb.step(hs, nb.mul(voice, 0.55)), nb.step(kind, 1.5))
    return nb.mx(base, sp)


def _glow(nb, root, power):
    """uPower x (uVoice x 0.6 + 0.85)"""
    return nb.mul(nb.driven(root, 'power', power), nb.madd(nb.driven(root, 'voice', 0.0), 0.6, 0.85))


def _reel_material(name):
    """mainframe.js reelMat: one material per reel, the sub-material picked by position in the reel's own frame
    (three's +Z toward the viewer, Blender's -Y): hub cap, knob, hub, flanges, tape pack."""
    m = K.new_material(name)
    t = m.node_tree
    t.nodes.clear()
    nb = K.NB(t)
    b = K.principled(nb)
    bx, by, bz = nb.sep(nb.texcoord('Object'))
    plz = nb.mul(by, -1.0)                            # three's local z
    r = nb.vmath('LENGTH', nb.comb(bx, bz, 0.0))       # length(three's local xy)
    az = nb.abs(by)
    knob = nb.mul(nb.step(0.0253, plz), nb.step(r, 0.0118))
    cap = nb.mul(nb.mul(nb.step(0.0132, plz), nb.step(r, 0.0357)), nb.sub(1.0, knob))
    hub = nb.mul(nb.mul(nb.mul(nb.step(r, 0.0527), nb.step(az, 0.0137)), nb.sub(1.0, cap)), nb.sub(1.0, knob))
    flange = nb.mul(nb.mul(nb.mul(nb.step(0.0068, az), nb.step(0.0527, r)), nb.sub(1.0, cap)), nb.sub(1.0, knob))
    pack = nb.clamp(nb.sub(nb.sub(nb.sub(nb.sub(1.0, cap), knob), hub), flange))
    band = nb.add(nb.mul(nb.madd(nb.sin(nb.mul(r, 2400.0)), 0.5, 0.5), 0.06), nb.mul(nb.sin(nb.mul(r, 310.0)), 0.03))
    p3 = nb.comb(bx, bz, plz)                            # three's local position (x, y, z)
    n = nb.noise(nb.vscale(p3, 60.0), 1.0, detail=0.0, normalize=True)
    c_white = nb.vscale((0.80, 0.79, 0.75), nb.madd(n, 0.06, 0.97))
    c_tape = nb.vscale((0.028, 0.018, 0.012), nb.add(band, 0.94))
    hk = nb.add(hub, knob)
    col = nb.vadd(nb.vadd(nb.vscale(c_white, flange), nb.vscale(c_tape, pack)),
                  nb.vadd(nb.vscale((0.62, 0.64, 0.66), hk), nb.vscale((0.02, 0.02, 0.021), cap)))
    rough = nb.add(nb.add(nb.mul(flange, 0.34), nb.mul(nb.add(band, 0.22), pack)),
                   nb.add(nb.mul(hk, 0.24), nb.mul(cap, 0.4)))
    nb.put(b.inputs['Base Color'], col)
    nb.put(b.inputs['Roughness'], rough)
    nb.put(b.inputs['Metallic'], hk)
    m.use_backface_culling = False
    m['eido_role'] = name
    return m


def _reel_clear_material(name):
    """mainframe.js reelClear: the clear reel flanges' rings and rim (transparent, double-sided, half specular)."""
    m = K.new_material(name)
    t = m.node_tree
    t.nodes.clear()
    nb = K.NB(t)
    b = K.principled(nb)
    bx, by, bz = nb.sep(nb.texcoord('Object'))
    r = nb.vmath('LENGTH', nb.comb(bx, bz, 0.0))
    rings = nb.smoothstep(0.40, 0.5, nb.abs(nb.sub(nb.fract(nb.mul(r, 38.0)), 0.5)))
    rim = nb.smoothstep(0.125, 0.1332, r)
    nb.put(b.inputs['Base Color'], (0.30, 0.34, 0.38))
    nb.put(b.inputs['Alpha'], nb.add(nb.add(0.035, nb.mul(rings, 0.05)), nb.mul(rim, 0.6)))
    nb.put(b.inputs['Roughness'], nb.madd(rings, 0.1, 0.04))
    nb.put(b.inputs['Metallic'], 0.0)
    nb.put(b.inputs['Specular IOR Level'], 0.25)          # three's specularIntensity 0.5
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    m.use_transparency_overlap = True
    m['eido_role'] = name
    return m


# ------------------------------------------------------------------------------------------- geometry ---
def cell_uv(g, i):
    """mainframe.js cellUV: squeeze a geometry's 0..1 UVs into atlas cell i."""
    c, r = i % ATL_COLS, i // ATL_COLS
    u0, u1 = c / ATL_COLS, (c + 1) / ATL_COLS
    v1, v0 = 1 - r / ATL_ROWS, 1 - (r + 1) / ATL_ROWS
    g.uv[:, 0] = u0 + g.uv[:, 0] * (u1 - u0)
    g.uv[:, 1] = v0 + g.uv[:, 1] * (v1 - v0)
    return g


def bulb_geo():
    """SphereGeometry(0.0062, 14, 8, 0, 2 pi, 0, pi / 2).rotateX(pi / 2): a dome facing +Z"""
    return K.sphere_geo(0.0062, 14, 8, 0.0, 2 * math.pi, 0.0, math.pi / 2).rotate_x(math.pi / 2)


def _panel_frame(P):
    N, U, C = np.array(P['normal'], float), np.array(P['up'], float), np.array(P['center'], float)
    R = np.cross(U, N)
    R /= np.linalg.norm(R)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2] = R, U, N
    return M, R, U, N, C


def tape_position(state, t, mem):
    """mainframe.js tapePosition: metres of tape at t. mem holds the integrator ({last_t, last_speed, pos}); call in
    time order (an earlier t restarts the integral from 0)."""
    s = state
    if isinstance(s.get('tape_pos'), (int, float)):
        return float(s['tape_pos'])
    base = s.get('tape_speed')
    base = 1.0 if base is None else float(base)
    stop = s.get('tape_stop')
    if isinstance(stop, dict) and isinstance(stop.get('at'), (int, float)):
        at = float(stop['at'])
        dur = float(stop.get('duration', 1.0))
        curve = float(stop.get('curve', 2.0))
        if t <= at:
            return base * TAPE_MPS * t
        u = min(1.0, (t - at) / dur)
        return base * TAPE_MPS * (at + dur * (1 - (1 - u) ** (curve + 1)) / (curve + 1))
    if mem['last_t'] is None or t < mem['last_t']:
        mem['pos'] = base * TAPE_MPS * t
    else:
        mem['pos'] += 0.5 * (mem['last_speed'] + base) * TAPE_MPS * (t - mem['last_t'])     # trapezoid
    mem['last_t'], mem['last_speed'] = t, base
    return mem['pos']


class Mainframe(K.Machine):
    name = 'mainframe'

    def _update(self, t, s):
        X = tape_position(s, t, self._tape)
        for r in self.parts['reels']:
            m = SPEED_MULT[r['drive'] % 6]
            K.set_turn(r['pivot'], 'z', -(X * m) / r['pack_radius'])
            self.touch(r['pivot'], 'rotation_euler')
        self.clock.value = X / TAPE_MPS
        self.t.value = t
        self.power.value = clamp01(s['power'] if s.get('power') is not None else 1.0)
        self.voice.value = clamp01(s['voice'] if s.get('voice') is not None else 0.0)
        for u in (self.clock, self.t, self.power, self.voice):
            self.touch(self.group, u.path)
        depths = self.loop_depths
        for i in range(len(depths)):
            m = SPEED_MULT[(i // 2) % 6]
            depths[i] = LOOP_BASE + 0.09 * math.sin(X * abs(m) * 2.3 + i * 1.7) * min(1.0, abs(m)) + (
                0.05 if i % 2 else -0.03)
        for lp in self.parts['loops']:
            d = depths[lp['index']]
            lp['runs'].scale = (1.0, 1.0, (MOUTH - d) / (MOUTH - 0.05))
            lp['bend'].location = (0.0, 0.0, d - 0.05)
            self.touch(lp['runs'], 'scale')
            self.touch(lp['bend'], 'location')
        return X


def build(glb=None, power=1.0, name='mainframe_room', collection=None, scene=None, location=(0.0, 0.0, 0.0), ctx=None):
    """mainframe.js build(THREE, opts): opts.glb (another GLB path), opts.power. ctx: a scene's ctx (its scene, and the
    default route of every update's keys). Returns a Mainframe."""
    scene = scene or (ctx.scene if ctx is not None else bpy.context.scene)
    path = glb or os.path.join(K.PACK, 'mainframe.glb')
    root, nodes, col = K.import_glb(path, name, collection, scene)
    root.location = location
    L = K.json_load('mainframe_layout.json')
    mf = Mainframe(root, col, scene, ctx=ctx)
    mf._tape = {'last_t': None, 'last_speed': 0.0, 'pos': 0.0}
    mf.clock = K.Uniform(root, 'clock', 0.0, lo=-1e9, hi=1e9, description='the machine clock (seconds of tape)')
    mf.t = K.Uniform(root, 't', 0.0, lo=-1e9, hi=1e9, description='film time (s): the blink and sparkle clock')
    mf.power = K.Uniform(root, 'power', power, description='0..1: every lamp, digit window and indicator')
    mf.voice = K.Uniform(root, 'voice', 0.0, description='0..1: the register lamps sparkle with the voice')
    mask = K.load_image(os.path.join(K.PACK, 'mainframe_mask.png'), srgb=False)
    T = {
        'enamel': K.pbr('PaintedMetal002'), 'plastic': K.pbr('Plastic013B_1k'), 'grey': K.pbr('Plastic018B_1k'),
        'gloss': K.pbr('Plastic003_1k'), 'satin': K.pbr('Plastic006_1k'), 'chrome': K.pbr('Metal049A'),
        'alu': K.pbr('Metal041A'), 'crinkle': K.pbr('Metal046A'), 'rubber': K.pbr('Rubber004_1k'),
        'prints': K.pbr('Fingerprints002_1k', normal=False, rough=False),
        'smear': K.pbr('Smear004_1k', normal=False, rough=False),
    }
    n = name

    def rm(role, **o):
        m, _nb, _b = K.role_mat(f'{n}_{role}', mask=o.pop('mask', mask), **o)
        mf.made['materials'].append(m)
        return m
    enamel = dict(set=T['enamel'], lum=0.181, lum_contrast=0.07, mottle=0.045, repeat=1.4, rough_mul=1.3,
                  rough_add=0.12, normal_scale=0.55, grime=0.6, edge=0.8, edge_rough=0.55, dust=0.3, imperf=T['smear'],
                  imperf_amt=0.12)
    R = {
        'enamel': rm('enamel', **{**enamel, 'tint': 0xdcd5c2, 'grime_color': 0x4d463a, 'edge_color': 0x8a8577}),
        'greyenamel': rm('greyenamel', **{**enamel, 'tint': 0xb3b0a6, 'grime_color': 0x49443a, 'edge_color': 0x6e6b63}),
        'blue': rm('blue', **{**enamel, 'tint': 0x3a5573, 'grime_color': 0x1f252a, 'edge_color': 0x8f949a,
                              'dust_color': 0x7d8189}),
        'darkpaint': rm('darkpaint', **{**enamel, 'tint': 0x2a2b2d, 'grime_color': 0x141414, 'edge_color': 0x5a5b5d,
                                        'dust': 0.1}),
        'columnblue': rm('columnblue', **{**enamel, 'tint': 0x3f86d8, 'grime': 0.25, 'grime_color': 0x1b2b3d,
                                          'edge': 0.2, 'edge_color': 0x8fb3dc, 'dust': 0.1, 'ao': 0.35}),
        'laminate': rm('laminate', set=T['grey'], lum=0.187, lum_contrast=0.25, tint=0xd2cec3, repeat=1.2, rough_mul=0.8,
                       normal_scale=0.3, grime=0.3, edge=0.4, edge_color=0x8b877c, dust=0.25, imperf=T['prints'],
                       imperf_repeat=1.6, imperf_amt=0.25),
        'panelbase': rm('panelbase', set=T['grey'], lum=0.187, lum_contrast=0.2, tint=0x5b5c5a, repeat=2.0,
                        normal_scale=0.3),
        'plinth': rm('plinth', set=T['satin'], lum=0.002, lum_contrast=0.2, tint=0x242425, repeat=2.0, rough_mul=1.8,
                     grime=0.6, dust=0.4),
        'crinkle': rm('crinkle', set=T['crinkle'], lum=0.108, lum_contrast=0.8, tint=0x232323, repeat=3.0, metal=0.3,
                      rough_mul=3.0, normal_scale=1.4, grime=0.35, edge=0.4, edge_color=0x6f6a62, edge_metal=1),
        'alu': rm('alu', set=T['alu'], tint=0xe6e8ea, repeat=3.0, metal=1, rough_mul=1.5, normal_scale=0.5, grime=0.4,
                  grime_color=0x46423a, imperf=T['prints'], imperf_repeat=3.0, imperf_amt=0.2),
        'chrome': rm('chrome', set=T['chrome'], repeat=2.5, metal=1, rough_add=0.05, normal_scale=0.4, grime=0.3,
                     imperf=T['prints'], imperf_repeat=3.5, imperf_amt=0.25),
        'brass': rm('brass', set=T['alu'], lum=0.488, lum_contrast=1.2, tint=0xcfa45a, repeat=6.0, metal=1,
                    rough_mul=1.8, normal_scale=0.5, grime=0.5, grime_color=0x3b2a14),
        'blackplastic': rm('blackplastic', set=T['gloss'], lum=0.006, lum_contrast=0.3, tint=0x141414, repeat=3.0,
                           rough_mul=1.2, normal_scale=0.4, grime=0.2, edge=0.4, edge_color=0x3c3c3c),
        'keydark': rm('keydark', set=T['plastic'], lum=0.807, lum_contrast=0.6, tint=0x55575a, repeat=6.0,
                      rough_mul=0.7, normal_scale=0.3, grime=0.3, edge=0.5, edge_color=0x9a9da0),
        'keylight': rm('keylight', set=T['plastic'], lum=0.807, lum_contrast=0.6, tint=0xe4e1d8, repeat=6.0,
                       rough_mul=0.7, normal_scale=0.3, grime=0.45, grime_color=0x7d776a, edge=0.3,
                       edge_color=0xb8b3a6),
        'red': rm('red', set=T['gloss'], lum=0.006, lum_contrast=0.2, tint=0xa3261d, repeat=4.0, clearcoat=0.4),
        'rubber': rm('rubber', set=T['rubber'], lum=0.025, lum_contrast=0.6, tint=0x161616, repeat=6.0),
        'cable': rm('cable', set=T['rubber'], lum=0.025, lum_contrast=0.8, tint=0x1c1c1d, repeat=8.0, normal_scale=0.6,
                    rough_mul=0.9, grime=0.3, dust=0.5),
        'tape': rm('tape', flat=0x21150d, rough=0.28),
        'reelhub': rm('reelhub', set=T['alu'], tint=0xd6d9dc, repeat=8.0, metal=1, rough_mul=1.4, normal_scale=0.4,
                      grime=0.3),
    }
    R['smoked'] = K.glass_mat(f'{n}_smoked', color=0x07090c, opacity=0.30, rough=0.02, smudge=0.25, imperf=T['smear'])
    R['clearglass'] = K.glass_mat(f'{n}_clearglass', color=0x141b24, opacity=0.14, rough=0.02, smudge=0.2,
                                  imperf=T['prints'])
    reel_mat = _reel_material(f'{n}_reel')
    reel_clear = _reel_clear_material(f'{n}_reelclear')
    mf.made['materials'] += [R['smoked'], R['clearglass'], reel_mat, reel_clear]

    imgs = {
        'plate': K.canvas_image(f'{n}_plate_art', 1024, 128, _draw_plate, alpha=False),
        'name': K.canvas_image(f'{n}_name_art', 1024, 104, _draw_name, alpha=False),
        'panel': K.canvas_image(f'{n}_panel_art', 1024, 280, _draw_panel(L), alpha=False),
        'atlas': K.canvas_image(f'{n}_lens_atlas', 1024, 256, _draw_atlas, alpha=False),
    }
    mf.made['images'] += list(imgs.values())
    R['decal_plate'] = K.decal_mat(f'{n}_decal_plate', imgs['plate'], rough=0.3, alpha=False)
    R['decal_name'] = K.decal_mat(f'{n}_decal_name', imgs['name'], rough=0.3, alpha=False)
    R['decal_panel'] = K.decal_mat(f'{n}_decal_panel', imgs['panel'], rough=0.45, alpha=False)
    mf.made['materials'] += [R['decal_plate'], R['decal_name'], R['decal_panel']]

    reel_body = re.compile(r'^mainframe_reel_\d+_(file|machine)$')

    def special(o, role):
        if role == 'reelclear':
            return reel_clear
        if reel_body.match(K.base_name(o.name)) or (o.parent is not None and reel_body.match(K.base_name(o.parent.name))):
            return reel_mat
        return None
    missing = K.apply_roles(nodes, R, R['darkpaint'], special=special,
                            no_shadow=r'decal|glass|smoked|reelclear')
    missing.discard('reelwhite')            # a slot of the reel bodies, which take the reel material whole
    mf.seated_decals = K.seat_decals(nodes)  # (the room's quads all sit 0.4-0.9 mm off: none moves)
    mf.missing_roles = missing
    if missing:
        common.log('mainframe', 'no material for roles:', ', '.join(sorted(missing)))
    for o in nodes.values():
        if o.type == 'MESH' and any(not r.startswith('decal') and r not in ('smoked', 'clearglass', 'reelclear')
                                    for r in K.roles_of(o)) and not reel_body.match(K.base_name(o.name)):
            K.write_curvature(o)

    reels = []
    for r in L['reels']:
        pivot = nodes.get(r['name'])
        if pivot is None:
            continue
        K.remember_rest(pivot)
        reels.append({'pivot': pivot, 'drive': r['drive'], 'side': r['side'], 'pack_radius': r['packRadius']})
    console = nodes.get('mainframe_console')
    row = nodes.get('mainframe_row')

    # ── the lamps from the layout: aLamp = (kind, a, b) per vertex, the logic in the shader ──
    P = L['console']['panel']
    PM, PR, PU, PN, PC = _panel_frame(P)

    def on_panel(x, z, h):
        return PC + PR * x + PU * z + PN * h

    def lamp_attr(g, a):
        return g.set_attr('aLamp', np.array(a, float))
    bulb_geos = []
    for lamp in L['console']['lamps']:
        x, z, k, a, b = lamp[:5]
        g = bulb_geo().apply(PM)
        p = on_panel(x, z, 0.0012)
        bulb_geos.append(lamp_attr(g.translate(*p), [k, a, b]))
    bulb_mat, _nb, _b = K.role_mat(
        f'{n}_lamp_bulbs', flat=0x4a3d2a, rough=0.18,
        emissive=lambda nb: nb.vscale((1.0, 0.80, 0.48), nb.mul(nb.mul(lamp_on_nodes(nb, root), _glow(nb, root, power)), 4.2)))

    def lens_color(nb, col):
        return nb.tex(imgs['atlas'], nb.uv('UVMap'), extension='EXTEND').outputs['Color']

    def lens_emit(nb):
        c = nb.tex(imgs['atlas'], nb.uv('UVMap'), extension='EXTEND').outputs['Color']
        return nb.vscale(c, nb.mul(nb.mul(lamp_on_nodes(nb, root), _glow(nb, root, power)), 1.9))
    lens_mat, _nb, _b = K.role_mat(f'{n}_lenses', flat=0xffffff, rough=0.22, color_fn=lens_color, emissive=lens_emit)
    mf.made['materials'] += [bulb_mat, lens_mat]
    bulbs = K.mesh_object(f'{n}_console_bulbs', K.merge(bulb_geos), [bulb_mat], col, parent=console)
    lens_geos = []
    for d, dv in enumerate(L['drives']):
        def add(pos, cell, w, h, dep, a):
            g = cell_uv(K.rbox(w, h, dep, 0.002), cell).translate(*pos)
            lens_geos.append(lamp_attr(g, a))
        add(dv['digit'], 16 + ((d + 1) % 10), 0.050, 0.052, 0.004, [2, 1, 0])
        state = [[1 if d != 3 else 0, 1.5 if d == 0 else 0], [1, 0], [d % 2, 0], [1, 0], [1 if d == 2 else 0, 0]]
        for j, p in enumerate(dv['lens']):
            add(p, j, 0.066, 0.028, 0.006, [2, state[j][0], state[j][1]])
        for j, p in enumerate(dv['buttons']):
            add([p[0], p[1], p[2] + 0.002], 8 + j, 0.066, 0.026, 0.010, [2, 0, 0])
    lenses = K.mesh_object(f'{n}_lenses', K.merge(lens_geos), [lens_mat], col, parent=root)
    cl = []
    for i, (x, z) in enumerate(L['console']['status']):
        g = cell_uv(K.rbox(0.050, 0.048, 0.006, 0.002), 26 + i).apply(PM)
        cl.append(lamp_attr(g.translate(*on_panel(x, z, 0.004)), [2, 1 if i >= 2 else 0, 0]))
    for i, (x, z) in enumerate(L['console']['column']):
        g = cell_uv(K.rbox(0.040, 0.034, 0.006, 0.002), [5, 6, 7, 13][i]).apply(PM)
        cl.append(lamp_attr(g.translate(*on_panel(x, z, 0.004)), [2, 1 if i == 0 else 0, 0]))
    status = K.mesh_object(f'{n}_console_status', K.merge(cl), [lens_mat], col, parent=console)
    cab = []
    for i, c in enumerate(L['cabinets']):
        for k, p in enumerate(c['lamps']):
            cab.append(lamp_attr(bulb_geo().translate(*p), [0, 60 + i * 6 + k, k]))
    cabinets = K.mesh_object(f'{n}_cabinet_bulbs', K.merge(cab), [bulb_mat], col, parent=root)
    for o in (bulbs, lenses, status, cabinets):
        o.visible_shadow = True

    # ── the vacuum-column tape loops: per loop the two runs (stretched from the mouth) and the U-bend (slid) ──
    loop_mat = K.new_material(f'{n}_tape_loops')
    lt = loop_mat.node_tree
    lt.nodes.clear()
    lnb = K.NB(lt)
    lb = K.principled(lnb)
    lnb.put(lb.inputs['Base Color'], (0.028, 0.019, 0.013))
    lnb.put(lb.inputs['Roughness'], 0.3)
    lnb.put(lb.inputs['Metallic'], 0.0)
    loop_mat.use_backface_culling = False
    mf.made['materials'].append(loop_mat)
    loops_root = bpy.data.objects.new(f'{n}_tape_loops', None)
    loops_root.empty_display_size = 0.1
    col.objects.link(loops_root)
    loops_root.parent = root
    loops = []
    for d, dv in enumerate(L['drives']):
        for k, (cx, cz) in enumerate(dv['loops']):
            li = d * 2 + k
            runs = K.merge([K.box_geo(0.0016, 0.9, 0.0127, 1, 8, 1).translate(cx + sx * 0.031, 0.5 - MOUTH, cz)
                            for sx in (-1, 1)])
            ro = K.mesh_object(f'{n}_loop_{li}_runs', runs, [loop_mat], col, parent=loops_root)
            ro.location = (0.0, 0.0, MOUTH)
            u = K.torus_geo(0.031, 0.0008, 6, 24, math.pi).rotate_z(math.pi).apply(np.diag([1.0, 1.0, 8.0, 1.0]))
            bo = K.mesh_object(f'{n}_loop_{li}_bend', u.translate(cx, 0.05, cz), [loop_mat], col, parent=loops_root)
            loops.append({'runs': ro, 'bend': bo, 'index': li})
    mf.loop_depths = [LOOP_BASE] * (len(L['drives']) * 2)

    count = len(L['console']['lamps']) + len(L['drives']) * 11 + 12
    mf.parts = {
        'reels': reels,
        'lamps': {'bulbs': bulbs, 'lenses': lenses, 'status': status, 'cabinets': cabinets, 'count': count,
                  'uniforms': {'clock': mf.clock, 'power': mf.power, 'voice': mf.voice}},
        'console': console, 'row': row, 'loops': loops,
        'uniforms': {'clock': mf.clock, 'power': mf.power, 'voice': mf.voice, 'loops': mf.loop_depths, 't': mf.t},
        'materials': R,
    }
    mf.update(0.0, {'power': power}, key=False)        # the engine's update(0, {}): the rest pose, nothing keyed
    mf._tape = {'last_t': None, 'last_speed': 0.0, 'pos': 0.0}
    return mf
