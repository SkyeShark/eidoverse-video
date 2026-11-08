"""A Teletype ASR-33 on its pedestal, 1966 (teletype.js, ported): ELIZA's terminal at MIT's Project MAC.

ELIZA ran on MIT's Project MAC time-sharing system through a typewriter terminal; the machine lines came back in
CAPITALS and the transcripts carry no question marks, because "?" was the line-delete character.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props.voice_machines import teletype

    tty = teletype.build()                        # -> Teletype: group (root Empty), parts, update, animate
    tty.update(t, {'text': 'I WAS A MIRROR NAMED ELIZA\\n', 'n_chars': n, 'voice': v, 'power': 1}, ctx=ctx)
    tty.parts['paper'].set_text(full_text, n_chars)          # or directly (keyed at the current frame)

set_text(full_text, n_chars): prints the first n_chars characters, UPPERCASE, every "?" stripped, 72 columns (wraps),
"\\n" = carriage return + line feed. The most recent line sits at the platen; older lines ride up the paper.
Fractional n_chars animates: the type box travels to the next column; on "\\n" the paper advances one line (the
platen and roll turn, the type box returns). The text is drawn in the paper's shader from a glyph atlas and a 128 x 64
character buffer (one RGBA texel per character: glyph, jitter, weight, ink), as the engine drew it: sharp in extreme
close-ups. The buffer is a PNG sequence (eidoblend.media.screens through the voice-machine kit's EraScreen): a new
128 x 64 file only on the frames whose printed text changes, held between them.
update(t, state): state['voice'] (0..1): the call-control lamps flare with it and the keyboard dances with the
printing (each printed character's key goes down). Every value is keyed at the frame of t (see voder.Machine).
parts: paper {mesh, set_text, lines(), uniforms {line}, texture (the buffer's EraScreen), glyphs (image)}, printhead,
platen, roll, keyboard (the keys' parent Empty), keys [53 key objects], lamps (the call-control buttons), body,
uniforms {power, voice, line, keys (.array: the 64 key depths, 0..1)}.
Metres, Blender Z up, floor z = 0, facing -Y (the keyboard toward the camera). About 0.50 m wide x 0.50 m deep,
0.89 m to the top of the cover; the paper rises to about 1.06 m.

Blender translations: the engine's keyboard was one mesh whose keys moved in the vertex stage from a uniform array;
here each key is its own object with its press keyed on its location (the same offset along the deck). The paper's
glyph lookup had explicit gradients (no mip seams between cells); EEVEE has no gradient sampling, so the atlas is
read with four nearest taps blended by hand (a bilinear filter without mips): smooth when magnified, no seams, and
EEVEE's sample accumulation antialiases it when it is small.
"""

from __future__ import annotations

import math
import os

import numpy as np
import bpy

from . import voder as K
from ... import common

clamp01 = K.clamp01
v3 = K.v3

COLS, BUF_W, ROWS = 72, 128, 64
LINE, CHAR, PAPER_W = 0.0254 / 6, 0.0254 / 10, 0.2159
MARGIN = (PAPER_W - COLS * CHAR) / 2
MONO = '"Lucida Console", Consolas, "Courier New", monospace'
SANS = '"Bahnschrift", "Segoe UI", Arial, sans-serif'

MACHINE = {'year': 1966, 'title': 'Teletype ASR-33 on its pedestal (ELIZA)', 'era': 1,
           'footprint': (0.60, 0.76, 1.07), 'center': (0.0, 0.12)}

ROWS_KEYS = [
    [['!', '1'], ['"', '2'], ['#', '3'], ['$', '4'], ['%', '5'], ['&', '6'], ["'", '7'], ['(', '8'], [')', '9'],
     ['', '0'], ['*', ':'], ['=', '-'], ['', 'HERE\nIS']],
    [['', 'ESC'], ['', 'Q'], ['', 'W'], ['', 'E'], ['', 'R'], ['', 'T'], ['', 'Y'], ['', 'U'], ['', 'I'], ['', 'O'],
     ['', 'P'], ['', 'LINE\nFEED'], ['', 'RE-\nTURN']],
    [['', 'CTRL'], ['', 'A'], ['', 'S'], ['', 'D'], ['', 'F'], ['', 'G'], ['', 'H'], ['', 'J'], ['', 'K'], ['', 'L'],
     ['+', ';'], ['', 'RUB\nOUT'], ['', 'REPT']],
    [['', 'SHIFT'], ['', 'Z'], ['', 'X'], ['', 'C'], ['', 'V'], ['', 'B'], ['', 'N'], ['', 'M'], ['<', ','], ['>', '.'],
     ['?', '/'], ['', 'SHIFT'], ['', 'BREAK']],
]
LEGENDS = [k for row in ROWS_KEYS for k in row]
SPACE_KEY = len(LEGENDS)                        # the space bar's index
KEY_OF = {}                                     # printed character -> key index
for _i, (_up, _main) in enumerate(LEGENDS):
    if len(_main) == 1:
        KEY_OF[_main] = _i
    if len(_up) == 1:
        KEY_OF[_up] = _i
KEY_OF[' '] = SPACE_KEY
KEY_OF['\n'] = next(i for i, (_u, m) in enumerate(LEGENDS) if m == 'RE-\nTURN')
KA_COLS, KA_ROWS = 8, 8
CALL_BUTTONS = [0xc0392b, 0x1c1c1c, 0x2f63b5, 0xd9861c]     # ORIG red, CLR black, BUZ-RLS blue, BRK-RLS amber


def sstep01(x):
    """teletype.js sstep(x): smoothstep over 0..1."""
    t = clamp01(x)
    return t * t * (3 - 2 * t)


def js_hash(n):
    """teletype.js hash(n) = fract(sin(n * 12.9898) * 43758.5453), in doubles as the engine computed it."""
    x = math.sin(n * 12.9898) * 43758.5453
    return x - math.floor(x)


def clean(s):
    """What the ASR-33 prints: upper case, no '?', no CR, tabs as spaces."""
    return str('' if s is None else s).upper().replace('?', '').replace('\r', '').replace('\t', ' ')


def glyph_of(ch):
    c = ord(ch)
    return c - 32 if 32 <= c <= 95 else 0


def layout(text, n):
    """The printed lines of the first n characters (72 columns, '\\n' ends a line)."""
    out = ['']
    for i in range(min(n, len(text))):
        ch = text[i]
        if ch == '\n':
            out.append('')
            continue
        if len(out[-1]) >= COLS:
            out.append('')
        out[-1] += ch
    return out


def buffer_bytes(lines):
    """teletype.js writeBuffer: the 128 x 64 RGBA character buffer (uint8, row = line % 64, row 0 first) of the last
    64 lines: R glyph, G jitter, B weight, A ink."""
    buf = np.zeros((ROWS, BUF_W, 4), np.uint8)
    Lc = len(lines) - 1
    for Ln in range(max(0, Lc - ROWS + 1), Lc + 1):
        row, s = Ln % ROWS, lines[Ln]
        for c in range(min(len(s), COLS)):
            g = glyph_of(s[c])
            if g == 0:
                continue
            heavy = 1 if js_hash(Ln * 17.1 + c * 3.9 + 5) > 0.93 else 0
            buf[row, c] = (g, math.floor(js_hash(Ln * 131.7 + c * 7.3 + 1) * 255),
                           math.floor((0.55 + 0.45 * js_hash(Ln * 57.3 + c * 11.1 + 9)) * 255 * (1 if heavy else 0.85)),
                           255)
    return buf


def col_x(c):
    return -PAPER_W / 2 + MARGIN + (c + 0.5) * CHAR


def deck_y(z):
    return 0.720 + (0.22 - min(0.22, z)) * (0.045 / 0.20) if z >= 0.02 else 0.765 + (0.02 - z) * (0.09 / 0.12)


# ------------------------------------------------------------------------------------------------- the art ---
def _draw_band(ctx, w, h):
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = 'rgba(38,36,33,0.92)'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = f'500 26px {SANS}'
    K.spaced_text(ctx, 'TELETYPE', w * 0.36, h / 2 + 1, 58)
    ctx.font = f'600 13px {SANS}'
    kx = w * 0.9345
    ctx.fillText('OFF', kx, 11)
    ctx.fillText('LINE', kx - 44, h / 2 + 8)
    ctx.fillText('LOCAL', kx + 48, h / 2 + 8)


def _draw_logo(ctx, w, h):
    ctx.clearRect(0, 0, w, h)
    ink = 'rgba(28,26,22,0.95)'
    ctx.fillStyle = ink
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = f'600 17px {SANS}'
    K.spaced_text(ctx, 'TELETYPE', w / 2, 20, 4)
    cx, cy = w / 2, 76                            # the TT monogram: two T's over a curl, in a bracket
    ctx.fillRect(cx - 50, cy - 26, 100, 11)
    ctx.fillRect(cx - 33, cy - 26, 13, 52)
    ctx.fillRect(cx + 20, cy - 26, 13, 52)
    ctx.lineWidth = 7
    ctx.strokeStyle = ink
    ctx.beginPath()
    ctx.arc(cx, cy + 6, 14, math.pi * 0.1, math.pi * 0.9)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(cx - 56, cy - 34)
    ctx.lineTo(cx - 56, cy + 30)
    ctx.lineTo(cx - 44, cy + 30)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(cx + 56, cy - 34)
    ctx.lineTo(cx + 56, cy + 30)
    ctx.lineTo(cx + 44, cy + 30)
    ctx.stroke()


def _draw_tag(ctx, w, h):
    g = ctx.createLinearGradient(0, 0, w, h)
    g.addColorStop(0, '#c9ccce')
    g.addColorStop(0.5, '#e4e6e7')
    g.addColorStop(1, '#b8bbbd')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, w, h)
    for x in range(0, w, 2):
        ctx.fillStyle = f'rgba(255,255,255,{0.03 + 0.05 * ((x * 7919) % 17) / 17})'
        ctx.fillRect(x, 0, 1, h)
    ctx.strokeStyle = '#2d3034'
    ctx.lineWidth = 5
    ctx.strokeRect(10, 10, w - 20, h - 20)
    ctx.fillStyle = '#23262a'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = f'600 22px {SANS}'
    K.spaced_text(ctx, 'PROPERTY OF', w / 2, 42, 3)
    ctx.font = f'700 25px {SANS}'
    K.spaced_text(ctx, 'MASSACHUSETTS INSTITUTE', w / 2, 80, 1)
    K.spaced_text(ctx, 'OF TECHNOLOGY', w / 2, 110, 2)
    ctx.fillRect(40, 132, w - 80, 3)
    ctx.font = f'700 30px {SANS}'
    K.spaced_text(ctx, 'PROJECT MAC', w / 2, 160, 6)
    ctx.font = f'600 18px {MONO}'
    ctx.fillText('No. 33-0417', w / 2, 192)


def _draw_keys(ctx, w, h):
    cw, ch = w / KA_COLS, h / KA_ROWS
    ctx.fillStyle = '#9da09f'
    ctx.fillRect(0, 0, w, h)
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    for i, (up, main) in enumerate(LEGENDS):
        cx, cy = (i % KA_COLS) * cw + cw / 2, (i // KA_COLS) * ch + ch / 2
        g = ctx.createRadialGradient(cx - 10, cy - 12, 4, cx, cy, cw * 0.5)
        g.addColorStop(0, '#b3b6b5')
        g.addColorStop(1, '#8e9190')
        ctx.fillStyle = g
        ctx.fillRect(cx - cw / 2, cy - ch / 2, cw, ch)
        ctx.fillStyle = '#f2f2ee'
        lines = main.split('\n')
        big = len(lines) == 1 and len(main) <= 1
        ctx.font = f'600 {46 if big else 21 if len(lines) > 1 else 24}px {SANS}'
        for k, ln in enumerate(lines):
            ctx.fillText(ln, cx, cy + (12 if up else 0) + (k - (len(lines) - 1) / 2) * 23)
        if up:
            ctx.font = f'600 26px {SANS}'
            ctx.fillText(up, cx, cy - 26)


def _draw_glyphs(ctx, w, h):
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, w, h)
    ctx.fillStyle = '#fff'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = f'bold 74px {MONO}'
    for i in range(64):
        ctx.fillText(chr(32 + i), (i % 16) * 64 + 32, (i // 16) * 96 + 50)


# ------------------------------------------------------------------------------------------- the materials ---
def _bilinear_nearest(nb, image, uv_x, uv_y, size):
    """A bilinear filter made of four nearest taps (no mip level, so no seams where the atlas UV jumps between
    cells): returns the R channel."""
    W, H = size
    tx = nb.sub(nb.mul(uv_x, W), 0.5)
    ty = nb.sub(nb.mul(uv_y, H), 0.5)
    fx, fy = nb.fract(tx), nb.fract(ty)
    x0, y0 = nb.floor(tx), nb.floor(ty)
    taps = []
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        u = nb.div(nb.add(x0, dx + 0.5), W)
        v = nb.div(nb.add(y0, dy + 0.5), H)
        n = nb.tex(image, nb.comb(u, v, 0.0), interpolation='Closest', extension='EXTEND')
        taps.append(nb.sep(n.outputs['Color'])[0])
    top = nb.mix(taps[0], taps[1], fx)
    bot = nb.mix(taps[2], taps[3], fx)
    return nb.mix(top, bot, fy)


def _paper_material(name, root, T, glyph_img, buffer, paper_tint, ink_color):
    """teletype.js paperMat: paper fibre, edge shade and the struck text from the glyph atlas + character buffer."""
    m = K.new_material(name)
    t = m.node_tree
    t.nodes.clear()
    nb = K.NB(t)
    b = K.principled(nb)
    uvx, uvy, _ = nb.sep(nb.uv('UVMap'))
    vM, xM = uvy, nb.mul(uvx, PAPER_W)
    line = nb.driven(root, 'line', 0.0)
    Lf = nb.sub(line, nb.div(vM, LINE))
    Ln = nb.floor(nb.add(Lf, 0.5))
    yIn = nb.sub(nb.add(Lf, 0.5), Ln)
    colF = nb.div(nb.sub(xM, MARGIN), CHAR)
    col = nb.floor(colF)
    gx = nb.fract(colF)
    gy = nb.sub(1.0, yIn)
    fl = nb.floor(line)
    valid = nb.mul(nb.mul(nb.mul(nb.step(0.0, col), nb.step(col, float(COLS - 1))),
                          nb.mul(nb.step(0.0, Ln), nb.step(Ln, fl))),
                   nb.step(nb.sub(fl, float(ROWS - 1)), Ln))
    cu = nb.div(nb.add(col, 0.5), BUF_W)
    cv = nb.div(nb.add(nb.mod(Ln, float(ROWS)), 0.5), ROWS)
    cell_node = buffer.texture_node(t)
    nb.put(cell_node.inputs['Vector'], nb.comb(cu, cv, 0.0))
    cr, cg, cb = nb.sep(cell_node.outputs['Color'])
    ca = cell_node.outputs['Alpha']
    gIdx = nb.floor(nb.madd(cr, 255.0, 0.5))
    jx = nb.mul(nb.sub(cg, 0.5), 0.07)
    jy = nb.mul(nb.sub(nb.fract(nb.mul(cg, 7.13)), 0.5), 0.10)
    ax = nb.mod(gIdx, 16.0)
    ay = nb.floor(nb.div(gIdx, 16.0))
    gxx = nb.clamp(nb.add(gx, jx), 0.02, 0.98)
    gyy = nb.clamp(nb.madd(nb.add(gy, jy), 0.92, 0.04), 0.02, 0.98)
    au = nb.div(nb.add(ax, gxx), 16.0)
    av = nb.sub(1.0, nb.div(nb.add(ay, nb.sub(1.0, gyy)), 4.0))
    cov = _bilinear_nearest(nb, glyph_img, au, av, glyph_img.size[:])
    weave = nb.noise(nb.comb(nb.mul(xM, 2600.0), nb.mul(vM, 2600.0), 0.0), 1.0, detail=0.0, normalize=True)
    front = nb.sub(1.0, nb.geometry('Backfacing'))
    ink = nb.mul(nb.mul(cov, nb.madd(cb, 0.35, 0.65)), nb.madd(weave, 0.3, 0.7))
    ink = nb.clamp(nb.mul(nb.mul(nb.mul(ink, ca), valid), front))
    pUV = nb.vscale(nb.comb(xM, vM, 0.0), 3.2)
    pap = nb.tex(T['paper']['map'], pUV).outputs['Color']
    fibre = nb.div(nb.lum(pap), 0.32)
    edge = nb.mul(nb.smoothstep(0.0, 0.004, xM), nb.smoothstep(PAPER_W, PAPER_W - 0.004, xM))
    paper = nb.vscale(nb.vscale(paper_tint, nb.madd(nb.sub(fibre, 1.0), 0.35, 1.0)), nb.madd(edge, 0.1, 0.9))
    nb.put(b.inputs['Base Color'], nb.vmix(paper, ink_color, nb.mul(ink, 0.92)))
    rg = nb.sep(nb.tex(T['paper']['rough'], pUV).outputs['Color'])[1]
    nb.put(b.inputs['Roughness'], nb.clamp(nb.sub(nb.mul(rg, 1.2), nb.mul(ink, 0.2)), 0.3, 1.0))
    nm = nb.new('ShaderNodeNormalMap', space='TANGENT', uv_map='UVMap')
    nb.put(nm.inputs['Strength'], 0.22)
    nb.put(nm.inputs['Color'], nb.tex(T['paper']['normal'], pUV).outputs['Color'])
    nb.put(b.inputs['Normal'], nm.outputs['Normal'])
    nb.put(b.inputs['Metallic'], 0.0)
    m.use_backface_culling = False
    m['eido_role'] = name
    return m


def _roll_material(name, T, paper_tint):
    """teletype.js rollMat: paper wound on a card core, end faces ringed by the winding."""
    m = K.new_material(name)
    t = m.node_tree
    t.nodes.clear()
    nb = K.NB(t)
    b = K.principled(nb)
    px, py, pz = nb.sep(nb.texcoord('Object'))
    r = nb.vmath('LENGTH', nb.comb(0.0, py, pz))
    wound = nb.madd(nb.sin(nb.mul(r, 3400.0)), 0.5, 0.5)
    end_face = nb.step(0.9, nb.div(nb.abs(px), PAPER_W / 2))
    core = nb.smoothstep(0.019, 0.017, r)
    u, v, _ = nb.sep(nb.uv('UVMap'))
    pap = nb.tex(T['paper']['map'], nb.comb(u, nb.mul(v, 4.0), 0.0)).outputs['Color']
    fibre = nb.div(nb.lum(pap), 0.32)
    side = nb.vscale(nb.vscale(paper_tint, nb.madd(nb.sub(fibre, 1.0), 0.3, 1.0)), 0.97)
    ends = nb.vscale(paper_tint, nb.madd(wound, 0.12, 0.84))
    base = nb.vmix(side, ends, end_face)
    nb.put(b.inputs['Base Color'], nb.vmix(base, (0.42, 0.33, 0.22), nb.mul(core, end_face)))
    nb.put(b.inputs['Roughness'], 0.8)
    nb.put(b.inputs['Metallic'], 0.0)
    m.use_backface_culling = False
    m['eido_role'] = name
    return m


def _button_material(name, root, power):
    """teletype.js btnMat: the call-control buttons' own colour (aTint), lit with power, flaring with the voice."""
    m = K.new_material(name)
    t = m.node_tree
    t.nodes.clear()
    nb = K.NB(t)
    b = K.principled(nb)
    c = nb.attr('aTint', 'Vector')
    nb.put(b.inputs['Base Color'], nb.vscale(c, 0.85))
    nb.put(b.inputs['Roughness'], 0.25)
    nb.put(b.inputs['Metallic'], 0.0)
    k = nb.mul(nb.mul(nb.driven(root, 'power', power), nb.madd(nb.driven(root, 'voice', 0.0), 2.4, 0.9)), 1.8)
    nb.put(b.inputs['Emission Color'], nb.vscale(c, k))
    nb.put(b.inputs['Emission Strength'], 1.0)
    m.use_backface_culling = False
    m['eido_role'] = name
    return m


# ------------------------------------------------------------------------------------------- the geometry ---
def vertex_normals(pos, tris):
    """three's computeVertexNormals: area-weighted face normals summed per vertex."""
    P = np.asarray(pos, float)
    T = np.asarray(tris, np.int64)
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    n = np.zeros_like(P)
    for k in range(3):
        np.add.at(n, T[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def _catmull_rom_centripetal(pts, n_out):
    """three's CatmullRomCurve3 (centripetal, open) sampled at n_out + 1 points equally spaced in arc length
    (getSpacedPoints): the curve is sampled finely, then resampled by its arc length."""
    P = [np.array(p, float) for p in pts]
    m = len(P)

    def point(t):
        p = (m - 1) * t
        i = int(math.floor(p))
        w = p - i
        if i >= m - 1:
            i, w = m - 2, 1.0
        p0 = P[i - 1] if i > 0 else 2 * P[0] - P[1]
        p1, p2 = P[i], P[i + 1]
        p3 = P[i + 2] if i + 2 < m else 2 * P[m - 1] - P[m - 2]
        d01 = max(np.sum((p1 - p0) ** 2) ** 0.25, 1e-4)
        d12 = max(np.sum((p2 - p1) ** 2) ** 0.25, 1e-4)
        d23 = max(np.sum((p3 - p2) ** 2) ** 0.25, 1e-4)
        if d12 < 1e-4:
            d12 = 1.0
        if d01 < 1e-4:
            d01 = d12
        if d23 < 1e-4:
            d23 = d12
        t1 = (p1 - p0) / d01 - (p2 - p0) / (d01 + d12) + (p2 - p1) / d12
        t2 = (p2 - p1) / d12 - (p3 - p1) / (d12 + d23) + (p3 - p2) / d23
        t1 *= d12
        t2 *= d12
        c0, c1 = p1, t1
        c2 = -3 * p1 + 3 * p2 - 2 * t1 - t2
        c3 = 2 * p1 - 2 * p2 + t1 + t2
        return c0 + c1 * w + c2 * w * w + c3 * w * w * w
    # three's getLengths uses 200 divisions; getSpacedPoints maps u to t through them
    div = 200
    samples = np.array([point(i / div) for i in range(div + 1)])
    seg = np.linalg.norm(np.diff(samples, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for j in range(n_out + 1):
        target = cum[-1] * j / n_out
        i = int(np.clip(np.searchsorted(cum, target) - 1, 0, div - 1))
        frac = (target - cum[i]) / max(cum[i + 1] - cum[i], 1e-12)
        out.append(point((i + frac) / div))
    return out


def paper_path(Pp):
    """The strip path in (z, y), three axes: from the roll, under the platen, up past the print point, curling back
    and draping down the back. Returns (path, index of the print point)."""
    PRINT_Z = Pp['printZ']
    roll = Pp['roll']
    back = [[roll['z'] + 0.006, roll['y'] - roll['r'] - 0.0005], [roll['z'] + 0.045, roll['y'] - roll['r'] - 0.002],
            [Pp['platenZ'] - 0.045, Pp['platenY'] - Pp['platenR'] - 0.006],
            [Pp['platenZ'] - 0.022, Pp['platenY'] - Pp['platenR'] - 0.0012]]
    below = []
    for k in range(9):
        a = -math.pi / 2 + (k / 8) * (math.pi / 2)
        below.append([Pp['platenZ'] + (Pp['platenR'] + 0.0006) * math.cos(a),
                      Pp['platenY'] + (Pp['platenR'] + 0.0006) * math.sin(a)])
    up = [[PRINT_Z + 0.0006, Pp['platenY'] + 0.03], [PRINT_Z - 0.002, Pp['coverTop'] + 0.02], [PRINT_Z - 0.010, 0.955],
          [PRINT_Z - 0.030, 1.005], [PRINT_Z - 0.070, 1.040], [PRINT_Z - 0.120, 1.056], [PRINT_Z - 0.170, 1.052],
          [PRINT_Z - 0.215, 1.036], [PRINT_Z - 0.250, 1.004], [PRINT_Z - 0.268, 0.950], [PRINT_Z - 0.273, 0.880],
          [PRINT_Z - 0.271, 0.800]]
    pts = _catmull_rom_centripetal([(0.0, y, z) for z, y in up], 72)
    above = [[p[2], p[1]] for p in pts]
    path = back + below + above[1:]
    return path, len(back) + len(below) - 1


def paper_geo(Pp):
    path, i_print = paper_path(Pp)
    s = [0.0]
    for i in range(1, len(path)):
        s.append(s[-1] + math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]))
    s0 = s[i_print]
    pos, uv, tris = [], [], []
    for i, (z, y) in enumerate(path):
        pos += [(-PAPER_W / 2, y, z), (PAPER_W / 2, y, z)]
        uv += [(0.0, s[i] - s0), (1.0, s[i] - s0)]
        if i > 0:
            a = (i - 1) * 2
            tris += [(a, a + 1, a + 2), (a + 1, a + 3, a + 2)]          # front face toward the reader (three's +Z)
    return K.Geo(pos, vertex_normals(pos, tris), uv, tris)


# ------------------------------------------------------------------------------------------- the machine ---
class Paper:
    """parts['paper']: the printed sheet. set_text(full_text, n_chars, t=None, frame=None) prints and keys (at the
    frame of t, or `frame`, or the current frame); lines() the printed lines."""

    def __init__(self, machine, mesh, glyphs, buffer):
        self.machine = machine
        self.mesh = mesh
        self.glyphs = glyphs
        self.texture = buffer
        self.uniforms = {'line': machine.line}
        self._text, self._n = None, -1
        self._lines = ['']
        self.printed = {'key': -1, 'env': 0.0}

    def lines(self):
        return list(self._lines)

    def _apply(self, full_text, n_chars, f):
        """set the printed state (no keys): returns {line, col, lines}."""
        M = self.machine
        text = clean(full_text)
        n_total = min(len(text), max(0.0, float(n_chars)))
        n = int(math.floor(n_total))
        frac = n_total - n
        if text != self._text or n != self._n:
            self._lines = layout(text, n)
            self._text, self._n = text, n
            M._buffer_put(f, buffer_bytes(self._lines))
        Lc = len(self._lines) - 1
        col = len(self._lines[Lc])
        nxt = text[n] if n < len(text) else None
        feed, head_col = 0.0, float(col)
        if nxt == '\n' and frac > 0:
            feed = sstep01(frac / 0.7)
            head_col = col * (1 - sstep01(frac))
        elif nxt and frac > 0:
            head_col = col + sstep01(frac)
        M.line.value = Lc + feed
        ph = M.parts['printhead']
        ph.location = M._printhead_rest + v3(col_x(min(COLS - 1, head_col)) - CHAR * 0.5, 0.0, 0.0)
        last = text[n - 1] if n > 0 else None
        self.printed['key'] = KEY_OF.get(last, -1) if last is not None else -1
        raw = max(0.0, float(n_chars))
        self.printed['env'] = 1 - sstep01((raw - n) * 1.6) if (n > 0 and raw < len(text) + 1) else 0.0
        M.touch(M.group, M.line.path)
        M.touch(ph, 'location')
        return {'line': Lc, 'col': col, 'lines': len(self._lines)}

    def set_text(self, full_text, n_chars=math.inf, t=None, frame=None, ctx=None, key=True):
        """Print the first n_chars characters of full_text (teletype.js parts.paper.setText) and key the paper, the
        type box, platen and roll at the frame of t (or `frame`, or the current frame)."""
        M = self.machine
        ctx = ctx or M.ctx
        f = frame if frame is not None else (M.frame_at(t, ctx) if t is not None else M.scene.frame_current)
        M._touched = []
        out = self._apply(full_text, n_chars, f)
        M._turn_paper()
        if key:
            for target, path, interp in M._touched:
                M.keyer.key(target, path, frame=f, ctx=ctx, interpolation=interp or M.interpolation)
        M._touched = []
        return out


class KeyDepths:
    """uniforms['keys']: the 64 key depths (0..1) the last update set (teletype.js uKeys.array)."""

    def __init__(self):
        self.array = [0.0] * 64


class Teletype(K.Machine):
    name = 'teletype'

    def dispose(self, files=False):
        """voder.Machine.dispose, and with files=True the character buffer's PNG folder too (as the era-2 machines'
        dispose(files=True) removes their screens' folders)."""
        d = getattr(getattr(self, 'buffer', None), 'dir', None)
        super().dispose()
        if files and d is not None and os.path.isdir(d):
            import shutil
            shutil.rmtree(d, ignore_errors=True)

    def _buffer_put(self, f, buf):
        """The buffer from frame f on (the frames since the last drawing hold it; see EraScreen.put)."""
        self.buffer.put(max(int(f), self.scene.frame_start), _pil(buf))
        self.buffer_writes += 1

    def _turn_paper(self):
        """platen and roll turn with the paper (one line = LINE of paper travel)"""
        Pp = self._Pp
        line = self.line.value
        K.set_turn(self.parts['platen'], 'x', -line * LINE / Pp['platenR'])
        self.parts['roll'].rotation_euler[0] = line * LINE / Pp['roll']['r']
        self.touch(self.parts['platen'], 'rotation_euler')
        self.touch(self.parts['roll'], 'rotation_euler')

    def _update(self, t, s):
        self.power.value = clamp01(s['power'] if s.get('power') is not None else 1.0)
        voice = clamp01(s['voice'] if s.get('voice') is not None else 0.0)
        self.voice.value = voice
        self.touch(self.group, self.power.path)
        self.touch(self.group, self.voice.path)
        paper = self.parts['paper']
        if 'text' in s:
            n = s.get('n_chars')
            paper._apply(s['text'], math.inf if n is None else n, self._frame)
        self._turn_paper()
        # the keyboard sings along: the struck key + a light voiced flutter across the home row
        arr = self.key_depths.array
        for i in range(len(arr)):
            arr[i] = 0.0
        pk = paper.printed
        if pk['key'] >= 0:
            arr[pk['key']] = pk['env']
        if voice > 0.05:
            step8 = math.floor(t * 9.0)
            for j in range(2):
                k = 13 + math.floor(js_hash(step8 * 3.1 + j * 17.7) * 38)
                arr[k] = max(arr[k], voice * 0.8 * (1 - sstep01((t * 9.0 - step8) * 1.3)))
        for i, ob in enumerate(self.parts['keys']):
            ob.location = self._press_dir * (-arr[i] * 0.0042)
            self.touch(ob, 'location')
        return None


def build(glb=None, power=1.0, paper_color=0xf0dfa4, name='teletype', collection=None, scene=None,
          location=(0.0, 0.0, 0.0), buffer_dir=None, ctx=None):
    """teletype.js build(THREE, opts): opts.glb (another GLB path), opts.power, opts.paperColor (paper_color).
    buffer_dir: where the character buffer's PNG frames go (default: <ctx.out_dir>/screens/<name> with a scene's ctx,
    else beside the saved blend, else a temp folder). ctx: a scene's ctx (its scene, and the default route of every
    update's keys)."""
    scene = scene or (ctx.scene if ctx is not None else bpy.context.scene)
    if buffer_dir is None and ctx is not None:
        buffer_dir = os.path.join(ctx.out_dir, 'screens', name)
    path = glb or os.path.join(K.PACK, 'teletype.glb')
    root, nodes, col = K.import_glb(path, name, collection, scene)
    root.location = location
    L = K.json_load('teletype_layout.json')
    tt = Teletype(root, col, scene, ctx=ctx)
    tt.power = K.Uniform(root, 'power', power, description='0..1: the call-control lamps')
    tt.voice = K.Uniform(root, 'voice', 0.0, description='0..1: the voice loudness (lamps flare, keys dance)')
    tt.line = K.Uniform(root, 'line', 0.0, lo=0.0, hi=1e6, description='the paper feed in lines (the newest line)')
    tt.key_depths = KeyDepths()
    tt._Pp = Pp = L['paper']
    mask = K.load_image(os.path.join(K.PACK, 'teletype_mask.png'), srgb=False)
    T = {
        'enamel': K.pbr('PaintedMetal002'), 'moulded': K.pbr('Plastic004'), 'plastic': K.pbr('Plastic013B_1k'),
        'grey': K.pbr('Plastic018B_1k'), 'gloss': K.pbr('Plastic003_1k'), 'alu': K.pbr('Metal041A'),
        'chrome': K.pbr('Metal049A'), 'crinkle': K.pbr('Metal046A'), 'rubber': K.pbr('Rubber004_1k'),
        'paper': K.pbr('Paper004'), 'prints': K.pbr('Fingerprints002_1k', normal=False, rough=False),
        'smear': K.pbr('Smear004_1k', normal=False, rough=False),
    }
    n = name

    def rm(role, **o):
        m, _nb, _b = K.role_mat(f'{n}_{role}', mask=o.pop('mask', mask), **o)
        tt.made['materials'].append(m)
        return m
    R = {
        'khaki': rm('khaki', set=T['moulded'], lum=0.131, lum_contrast=0.5, mottle=0.04, tint=0xc2b78d, repeat=3.0,
                    rough_mul=0.9, normal_scale=0.45, clearcoat=0.25, coat_rough=0.2, grime=0.5, grime_color=0x5a4f34,
                    edge=0.55, edge_color=0xdcd2ad, edge_rough=0.2, dust=0.3, dust_color=0x9e9679, imperf=T['prints'],
                    imperf_repeat=2.5, imperf_amt=0.18),
        'cream': rm('cream', set=T['plastic'], lum=0.807, lum_contrast=0.8, mottle=0.04, tint=0xe3d7b1, repeat=3.0,
                    rough_mul=0.6, normal_scale=0.35, clearcoat=0.35, coat_rough=0.14, grime=0.4, grime_color=0x7d6e4c,
                    edge=0.45, edge_color=0xf1e8c9, edge_rough=0.18, dust=0.25, imperf=T['prints'], imperf_repeat=2.5,
                    imperf_amt=0.2),
        'pedestal': rm('pedestal', set=T['enamel'], lum=0.181, lum_contrast=0.04, mottle=0.02, tint=0xb8b093,
                       repeat=1.6, rough_mul=1.4, rough_add=0.12, normal_scale=0.45, grime=0.45, grime_color=0x4a4230,
                       edge=0.85, edge_color=0x5a5549, edge_rough=0.6, edge_metal=0.6, dust=0.2, imperf=T['smear'],
                       imperf_amt=0.08),
        'plategrey': rm('plategrey', set=T['grey'], lum=0.187, lum_contrast=0.3, tint=0xa7a9a2, repeat=3.0,
                        rough_mul=0.9, normal_scale=0.4, grime=0.4, edge=0.5, edge_color=0x6d6f6a, dust=0.25,
                        imperf=T['prints'], imperf_repeat=3.0, imperf_amt=0.2),
        'steel': rm('steel', set=T['alu'], lum=0.488, lum_contrast=1.0, tint=0xbdbfc2, repeat=4.0, metal=1,
                    rough_mul=1.8, normal_scale=0.6, grime=0.5, grime_color=0x3b362d),
        'alu': rm('alu', set=T['alu'], tint=0xe6e7e8, repeat=3.0, metal=1, rough_mul=2.6, normal_scale=0.5, grime=0.3),
        'chrome': rm('chrome', set=T['chrome'], repeat=3.0, metal=1, rough_add=0.05, normal_scale=0.4, grime=0.3,
                     imperf=T['prints'], imperf_repeat=3.5, imperf_amt=0.25),
        'rubber': rm('rubber', set=T['rubber'], lum=0.025, lum_contrast=0.6, tint=0x131313, repeat=8.0, rough_mul=0.8),
        'blackplastic': rm('blackplastic', set=T['gloss'], lum=0.006, lum_contrast=0.3, tint=0x141414, repeat=4.0,
                           rough_mul=1.1, normal_scale=0.4, grime=0.2),
        'mech': rm('mech', set=T['crinkle'], lum=0.108, lum_contrast=0.8, tint=0x2a2a2a, repeat=5.0, metal=0.6,
                   rough_mul=2.0, normal_scale=0.8, grime=0.5),
        'ribbon': rm('ribbon', flat=0x0c0b0e, rough=0.55),
        'creamknob': rm('creamknob', set=T['plastic'], lum=0.807, lum_contrast=0.6, tint=0xe8dcbc, repeat=8.0,
                        rough_mul=0.6, clearcoat=0.3, grime=0.4),
        'tapepink': rm('tapepink', set=T['paper'], lum=0.32, lum_contrast=0.6, tint=0xe9bfb4, repeat=12.0,
                       normal_scale=0.5, side='double'),
        'cable': rm('cable', set=T['rubber'], lum=0.025, lum_contrast=0.8, tint=0x1c1b1a, repeat=10.0,
                    normal_scale=0.6, grime=0.3, dust=0.5),
    }
    R['acrylic'] = K.glass_mat(f'{n}_acrylic', color=0x1b1d1c, opacity=0.13, rough=0.03, smudge=0.25, side='double',
                               imperf=T['prints'])
    R['chad'] = K.glass_mat(f'{n}_chad', color=0xc9c2a0, opacity=0.22, rough=0.12, smudge=0.15, side='double',
                            imperf=T['smear'])
    tt.made['materials'] += [R['acrylic'], R['chad']]
    imgs = {
        'band': K.canvas_image(f'{n}_band_art', 1024, 72, _draw_band),
        'logo': K.canvas_image(f'{n}_logo_art', 256, 128, _draw_logo),
        'tag': K.canvas_image(f'{n}_tag_art', 512, 216, _draw_tag, alpha=False),
        'keys': K.canvas_image(f'{n}_key_legends', 1024, 1024, _draw_keys, alpha=False),
        'glyphs': K.canvas_image(f'{n}_glyph_atlas', 1024, 384, _draw_glyphs, srgb=False, alpha=False),
    }
    tt.made['images'] += list(imgs.values())
    R['decal_band'] = K.decal_mat(f'{n}_decal_band', imgs['band'], rough=0.35)
    R['decal_logo'] = K.decal_mat(f'{n}_decal_logo', imgs['logo'], rough=0.3)
    R['decal_tag'] = K.decal_mat(f'{n}_decal_tag', imgs['tag'], rough=0.35, metal=0.8, alpha=False)
    tt.made['materials'] += [R['decal_band'], R['decal_logo'], R['decal_tag']]
    missing = K.apply_roles(nodes, R, R['blackplastic'], no_shadow=r'decal|acrylic|chad')
    tt.seated_decals = K.seat_decals(nodes)            # the TT monogram onto the cover's sloped face (see seat_decals)
    tt.missing_roles = missing
    if missing:
        common.log('teletype', 'no material for roles:', ', '.join(sorted(missing)))
    for o in nodes.values():
        if o.type == 'MESH' and any(not r.startswith('decal') and r not in ('acrylic', 'chad') for r in K.roles_of(o)):
            K.write_curvature(o)
    platen = nodes['teletype_platen']
    K.remember_rest(platen)

    # ═══ KEYBOARD (legend atlas; each key its own object, pressed along the deck) ═══
    ANG = L['deckAngle']
    keyboard = bpy.data.objects.new(f'{n}_keyboard', None)
    keyboard.empty_display_size = 0.05
    col.objects.link(keyboard)
    keyboard.parent = root
    key_mat, _nb, _b = K.role_mat(f'{n}_keys', set=T['plastic'], lum=0.807, lum_contrast=0.2, tint=0xffffff, repeat=20.0,
                                  rough_mul=0.9, normal_scale=0.25, edge=0.6, edge_color=0xc9ccca, edge_r=0.003,
                                  edge_rough=0.25,
                                  color_fn=lambda nb, c: nb.vmul(nb.tex(imgs['keys'], nb.uv('UVMap'),
                                                                        extension='EXTEND').outputs['Color'],
                                                                 (1.0, 1.0, 0.98)))
    tt.made['materials'].append(key_mat)
    blank_uv = ((7 + 0.5) / KA_COLS, 1 - (7 + 0.5) / KA_ROWS)
    PITCH = 0.019
    keys = []
    idx = 0
    for r, row_keys in enumerate(ROWS_KEYS):
        zz = 0.064 + r * 0.030
        x0 = -0.121 + r * 0.25 * PITCH
        for k in range(len(row_keys)):
            h = 0.017 - r * 0.0012
            g, ranges = K.cylinder_geo(0.0072, 0.0077, h, 24, 1, groups=True)
            g.uv[:] = blank_uv
            c, rr = idx % KA_COLS, idx // KA_COLS
            t0, tc = ranges[1]
            top_v = np.unique(g.tris[t0 // 3:(t0 + tc) // 3].ravel())
            px = g.pos[top_v, 0] / 0.0072 * 0.5 + 0.5
            pz = g.pos[top_v, 2] / 0.0072 * 0.5 + 0.5
            g.uv[top_v, 0] = (c + px * 0.94 + 0.03) / KA_COLS
            g.uv[top_v, 1] = 1 - (rr + pz * 0.94 + 0.03) / KA_ROWS
            yb = deck_y(zz) - 0.005 + 0.002
            K.xf(g, x0 + k * PITCH, yb + h / 2, zz, ANG * 0.6)
            ob = K.mesh_object(f'{n}_key_{idx:02d}', g, [key_mat], col, parent=keyboard)
            ob['key_index'] = idx
            ob['legend'] = '/'.join(x for x in LEGENDS[idx] if x).replace('\n', ' ')
            keys.append(ob)
            idx += 1
    sb = K.rbox(0.13, 0.012, 0.016, 0.006)
    sb.uv[:] = blank_uv
    K.xf(sb, 0.004, deck_y(0.19) - 0.003 + 0.008, 0.19, ANG * 0.6)
    ob = K.mesh_object(f'{n}_key_space', sb, [key_mat], col, parent=keyboard)
    ob['key_index'] = SPACE_KEY
    ob['legend'] = 'SPACE'
    keys.append(ob)
    for ob in keys:
        K.write_curvature(ob)
    tt._press_dir = v3(0.0, math.cos(ANG), math.sin(ANG))

    # call-control buttons: ORIG red, CLR black, BUZ-RLS blue, BRK-RLS amber, lit with power, flaring with the voice
    geos = []
    for i, p in enumerate(L['buttons']):
        g = K.xf(K.rbox(0.0145, 0.010, 0.0145, 0.0025), p[0], p[1], p[2], ANG)
        g.set_attr('aTint', K.lin(CALL_BUTTONS[i]))
        geos.append(g)
    btn_mat = _button_material(f'{n}_callcontrol', root, power)
    tt.made['materials'].append(btn_mat)
    buttons = K.mesh_object(f'{n}_callcontrol', K.merge(geos), [btn_mat], col, parent=root)

    # ═══ TYPE BOX (moves along the platen) ═══
    PRINT_Z = Pp['printZ']
    printhead = bpy.data.objects.new(f'{n}_typebox', None)
    printhead.empty_display_size = 0.02
    col.objects.link(printhead)
    printhead.parent = root
    head_black, _nb, _b = K.role_mat(f'{n}_head_black', set=T['gloss'], lum=0.006, lum_contrast=0.3, tint=0x141414,
                                     repeat=20.0, rough_mul=1.1, normal_scale=0.4, edge=0.4, edge_color=0x4a4a4a,
                                     edge_r=0.002)
    head_alu, _nb, _b = K.role_mat(f'{n}_head_alu', set=T['alu'], tint=0xe6e7e8, repeat=20.0, metal=1, rough_mul=1.5,
                                   normal_scale=0.5)
    tt.made['materials'] += [head_black, head_alu]
    for seed, gname, g, mat in (
            (40, 'type_cylinder', K.cylinder_geo(0.0085, 0.0085, 0.017, 28).translate(0, -0.0105, 0.0105), head_black),
            (41, 'ribbon_guide', K.xf(K.rbox(0.020, 0.0035, 0.004, 0.001), 0, -0.0015, 0.0035), head_alu),
            (42, 'carriage_shoe', K.xf(K.rbox(0.024, 0.008, 0.024, 0.002), 0, -0.024, 0.014), head_alu)):
        ob = K.mesh(g, mat, seed, f'{n}_typebox_{gname}', col, parent=printhead)
        K.write_curvature(ob)
    tt._printhead_rest = v3(0.0, Pp['platenY'], PRINT_Z)
    printhead.location = tt._printhead_rest

    # ═══ PAPER: glyph atlas + character buffer, drawn in the shader ═══
    from . import EraScreen
    tt.buffer_writes = 0
    blank = np.zeros((ROWS, BUF_W, 4), np.uint8)
    tt.buffer = EraScreen(tt, f'{n}_paper_buffer', 2.0, 1.0, BUF_W, lambda w, h: _pil(blank), nearest=True,
                          out_dir=buffer_dir)
    tt.buffer.image.colorspace_settings.name = 'Non-Color'
    tt.buffer.image.alpha_mode = 'CHANNEL_PACKED'
    tt.made['images'].append(tt.buffer.image)
    paper_mat = _paper_material(f'{n}_paper', root, T, imgs['glyphs'], tt.buffer, K.lin(paper_color), K.lin(0x1d1a24))
    roll_mat = _roll_material(f'{n}_roll_paper', T, K.lin(paper_color))
    tt.made['materials'] += [paper_mat, roll_mat]
    paper_mesh = K.mesh_object(f'{n}_paper', paper_geo(Pp), [paper_mat], col, parent=root)
    roll = bpy.data.objects.new(f'{n}_roll', None)
    roll.empty_display_size = 0.06
    col.objects.link(roll)
    roll.parent = root
    roll.location = v3(0.0, Pp['roll']['y'], Pp['roll']['z'])
    roll.rotation_mode = 'XYZ'
    lathe = K.lathe_geo([(0.012, -PAPER_W / 2), (Pp['roll']['r'], -PAPER_W / 2), (Pp['roll']['r'], PAPER_W / 2),
                         (0.012, PAPER_W / 2)], 64).rotate_z(math.pi / 2)
    K.mesh(lathe, roll_mat, 43, f'{n}_roll_paper', col, parent=roll)        # three's lathe normals, smooth

    paper = Paper(tt, paper_mesh, imgs['glyphs'], tt.buffer)
    tt.parts = {
        'paper': paper, 'printhead': printhead, 'platen': platen, 'roll': roll, 'keyboard': keyboard, 'keys': keys,
        'lamps': buttons, 'body': nodes.get('teletype_machine'),
        'uniforms': {'power': tt.power, 'voice': tt.voice, 'line': tt.line, 'keys': tt.key_depths},
        'materials': R,
    }
    paper._apply('', 0, scene.frame_start)
    tt.update(0.0, {'power': power}, key=False)        # the engine's update(0, {}): the rest pose, nothing keyed
    return tt


def _pil(buf):
    """The buffer as a PNG-ready image: PNG rows run top-down and Blender puts the file's top row at v = 1, so the
    rows are flipped to land buffer row r at v = (r + 0.5) / 64, where the paper shader reads it."""
    from PIL import Image
    return Image.fromarray(buf[::-1].copy(), 'RGBA')
