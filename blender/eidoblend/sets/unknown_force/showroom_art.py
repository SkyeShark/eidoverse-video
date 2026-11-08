"""showroom_art: the showroom's printed and displayed matter (the ENGINE exploded-view spec sheet on the LED wall, the
toaster's WARNING placard, its rating plate and dial). The Blender edition of eidoverse/sets/unknown_force/
showroom_art.js, line for line on interiors_lib's canvas. All text invented; no logos.

    from eidoblend.sets.unknown_force import interiors_lib as L, showroom_art as SA
    cv, ctx = L.canvas(L.napi(), SA.SCREEN['W'], SA.SCREEN['H'])
    SA.draw_engine_sheet(ctx, cv.width, cv.height)
"""
import math

INK, LINE, RED, PAPER, ORANGE = '#0d1626', '#22324a', '#c8141e', '#eef3f8', '#f26a1b'

# screen-space layout shared with showroom.py: where the singer stands in front of the wall (canvas fractions)
# figY0 / figY1: the singer's feet / head-top as the 'reveal' camera projects her onto the wall (feet fall below it)
SCREEN = {'w': 13.0, 'h': 5.6, 'W': 3072, 'H': 1324, 'figX': 0.5, 'figY0': 1.08, 'figY1': 0.735}
# the SEQUENCE COMPLETION bar (canvas fractions): its fill is animated in the shader
SEQBAR = {'x0': 0.705, 'x1': 0.965, 'y0': 0.215, 'y1': 0.255}


def _iso(x, y, z):
    """A quick oblique projection for the parts."""
    return (x - z * 0.62, y - z * 0.36)


def _part_cylinder(ctx, cx, cy, r, h, s):
    ctx.save()
    ctx.strokeStyle = INK
    ctx.lineWidth = 3.2 * s
    ctx.fillStyle = 'rgba(34,50,74,0.06)'
    ctx.beginPath()
    ctx.ellipse(cx, cy - h / 2, r, r * 0.34, 0, 0, math.pi * 2)
    ctx.fill()
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(cx - r, cy - h / 2)
    ctx.lineTo(cx - r, cy + h / 2)
    ctx.ellipse(cx, cy + h / 2, r, r * 0.34, 0, math.pi, 0, True)
    ctx.lineTo(cx + r, cy - h / 2)
    ctx.stroke()
    ctx.lineWidth = 1.6 * s
    ctx.setLineDash([10 * s, 8 * s])
    ctx.beginPath()
    ctx.ellipse(cx, cy + h / 2, r, r * 0.34, 0, math.pi, 0)
    ctx.stroke()
    ctx.restore()


def _part_gear(ctx, cx, cy, R, teeth, s, t=0.0):
    ctx.save()
    ctx.strokeStyle = INK
    ctx.lineWidth = 3 * s
    ctx.fillStyle = 'rgba(34,50,74,0.06)'
    ctx.beginPath()
    for i in range(teeth * 4 + 1):
        a = t + (i / (teeth * 4)) * math.pi * 2
        rr = R if i % 4 in (1, 2) else R * 0.84
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.55
        if i == 0:
            ctx.moveTo(x, y)
        else:
            ctx.lineTo(x, y)
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
    ctx.beginPath()
    ctx.ellipse(cx, cy, R * 0.28, R * 0.28 * 0.55, 0, 0, math.pi * 2)
    ctx.stroke()
    ctx.restore()


def _part_box(ctx, x, y, w, h, d, s):
    p = []
    for a, b, c in ((0, 0, 0), (w, 0, 0), (w, h, 0), (0, h, 0), (0, 0, d), (w, 0, d), (w, h, d), (0, h, d)):
        u, v = _iso(a, -b, c)
        p.append((x + u, y + v))
    ctx.save()
    ctx.strokeStyle = INK
    ctx.lineWidth = 3 * s
    ctx.fillStyle = 'rgba(34,50,74,0.07)'

    def face(ids):
        ctx.beginPath()
        for i, k in enumerate(ids):
            (ctx.lineTo if i else ctx.moveTo)(*p[k])
        ctx.closePath()
        ctx.fill()
        ctx.stroke()
    face([0, 1, 2, 3])
    face([3, 2, 6, 7])
    face([1, 5, 6, 2])
    ctx.restore()


def _part_spring(ctx, x, y, ln, r, coils, s):
    ctx.save()
    ctx.strokeStyle = INK
    ctx.lineWidth = 3 * s
    ctx.beginPath()
    for i in range(coils * 24 + 1):
        t = i / (coils * 24)
        a = t * coils * math.pi * 2
        px, py = x + t * ln, y + math.sin(a) * r
        if i:
            ctx.lineTo(px + math.cos(a) * r * 0.25, py)
        else:
            ctx.moveTo(px, py)
    ctx.stroke()
    ctx.restore()


def _bubble(ctx, x, y, n, s):
    ctx.save()
    ctx.fillStyle = PAPER
    ctx.strokeStyle = INK
    ctx.lineWidth = 3 * s
    ctx.beginPath()
    ctx.arc(x, y, 30 * s, 0, math.pi * 2)
    ctx.fill()
    ctx.stroke()
    ctx.fillStyle = INK
    ctx.font = f'{30 * s}px "UF Michroma"'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(str(n).rjust(2, '0'), x, y + 1 * s)
    ctx.restore()


def _label(ctx, x, y, title, sub, s, align='left'):
    ctx.save()
    ctx.textAlign = align
    ctx.fillStyle = INK
    ctx.font = f'{34 * s}px "UF Rajdhani"'
    ctx.fillText(title, x, y)
    if sub:
        ctx.font = f'{24 * s}px "UF Mono"'
        ctx.fillStyle = LINE
        ctx.fillText(sub, x, y + 32 * s)
    ctx.restore()


def _leader(ctx, x0, y0, x1, y1, s, color=INK):
    ctx.save()
    ctx.strokeStyle = color
    ctx.lineWidth = 2.4 * s
    ctx.beginPath()
    ctx.moveTo(x0, y0)
    ctx.lineTo(x1, y1)
    ctx.stroke()
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(x1, y1, 7 * s, 0, math.pi * 2)
    ctx.fill()
    ctx.restore()


def draw_engine_sheet(ctx, W, H):
    """The LED wall: an engine spec sheet whose exploded parts all point at the empty outline where she stands."""
    s = W / 3072
    ctx.fillStyle = PAPER
    ctx.fillRect(0, 0, W, H)
    # drafting grid
    ctx.strokeStyle = 'rgba(34,50,74,0.08)'
    ctx.lineWidth = 1.2 * s
    x = 0.0
    while x < W:
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, H)
        ctx.stroke()
        x += 48 * s
    y = 0.0
    while y < H:
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(W, y)
        ctx.stroke()
        y += 48 * s
    ctx.strokeStyle = INK
    ctx.lineWidth = 6 * s
    ctx.strokeRect(24 * s, 24 * s, W - 48 * s, H - 48 * s)
    ctx.lineWidth = 2 * s
    ctx.strokeRect(40 * s, 40 * s, W - 80 * s, H - 80 * s)
    # title block (top left)
    ctx.fillStyle = INK
    ctx.textBaseline = 'alphabetic'
    ctx.font = f'{230 * s}px "UF Michroma"'
    ctx.fillText('ENGINE', 90 * s, 300 * s)
    ctx.font = f'{44 * s}px "UF Rajdhani"'
    ctx.fillStyle = LINE
    ctx.fillText('ASSEMBLY DRAWING  ·  EXPLODED VIEW  ·  SHEET 1 OF 1', 96 * s, 372 * s)
    ctx.fillStyle = RED
    ctx.font = f'{50 * s}px "UF Rajdhani"'
    ctx.fillText('ONLY AN ENGINE. NOTHING ELSE INSIDE.', 96 * s, 440 * s)
    # the empty outline of the unit, sized and placed where the singer stands in front of the wall in the reveal
    # shot, so every callout points at HER (the outline is hidden behind her until the turntable turns her away)
    fx, fy0, fy1 = SCREEN['figX'] * W, SCREEN['figY0'] * H, SCREEN['figY1'] * H
    hh = fy0 - fy1
    hy, sy, cy, hipY = fy1 + hh * 0.13, fy1 + hh * 0.30, fy1 + hh * 0.42, fy1 + hh * 0.58
    ctx.save()
    ctx.strokeStyle = LINE
    ctx.lineWidth = 4 * s
    ctx.setLineDash([16 * s, 10 * s])
    ctx.beginPath()
    ctx.ellipse(fx, hy, hh * 0.12, hh * 0.12, 0, 0, math.pi * 2)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(fx - hh * 0.17, sy)
    ctx.lineTo(fx + hh * 0.17, sy)
    ctx.lineTo(fx + hh * 0.13, hipY)
    ctx.lineTo(fx + hh * 0.10, fy0)
    ctx.moveTo(fx - hh * 0.10, fy0)
    ctx.lineTo(fx - hh * 0.13, hipY)
    ctx.lineTo(fx - hh * 0.17, sy)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.strokeStyle = 'rgba(200,20,30,0.55)'
    ctx.lineWidth = 2 * s
    ctx.setLineDash([40 * s, 10 * s, 8 * s, 10 * s])
    ctx.beginPath()
    ctx.moveTo(fx, 480 * s)
    ctx.lineTo(fx, H - 44 * s)
    ctx.stroke()
    ctx.restore()
    # a height dimension beside the outline
    dx, top, bot = fx - hh * 0.42, fy1, min(fy0, H - 50 * s)
    ctx.save()
    ctx.strokeStyle = INK
    ctx.fillStyle = INK
    ctx.lineWidth = 2.4 * s
    ctx.beginPath()
    ctx.moveTo(dx, top)
    ctx.lineTo(dx, bot)
    ctx.stroke()
    for yy, d in ((top, 1), (bot, -1)):
        ctx.beginPath()
        ctx.moveTo(dx, yy)
        ctx.lineTo(dx - 10 * s, yy + 22 * s * d)
        ctx.lineTo(dx + 10 * s, yy + 22 * s * d)
        ctx.closePath()
        ctx.fill()
        ctx.beginPath()
        ctx.moveTo(dx - 26 * s, yy)
        ctx.lineTo(dx + 26 * s, yy)
        ctx.stroke()
    ctx.translate(dx - 18 * s, (top + bot) / 2)
    ctx.rotate(-math.pi / 2)
    ctx.font = f'{26 * s}px "UF Mono"'
    ctx.textAlign = 'center'
    ctx.fillText('H 1740', 0, 0)
    ctx.restore()
    ctx.fillStyle = LINE
    ctx.font = f'{28 * s}px "UF Mono"'
    ctx.fillText('UNIT 01 (ASSEMBLED)', fx + hh * 0.34, fy1 + hh * 0.66)
    # exploded parts round the sheet, each with a numbered bubble and a leader that ends on the unit
    T = lambda x, y: (x * s, y * s)                                   # noqa: E731
    tgt = {'head': (fx - hh * 0.05, hy), 'headR': (fx + hh * 0.05, hy), 'chest': (fx - hh * 0.09, cy),
           'chestR': (fx + hh * 0.09, cy), 'hip': (fx - hh * 0.08, hipY), 'hipR': (fx + hh * 0.08, hipY),
           'top': (fx, fy1 + hh * 0.02)}

    def knob(x, y):
        ctx.save()
        ctx.strokeStyle = INK
        ctx.lineWidth = 3 * s
        ctx.beginPath()
        ctx.ellipse(x, y, 70 * s, 70 * s * 0.55, 0, 0, math.pi * 2)
        ctx.stroke()
        ctx.beginPath()
        ctx.moveTo(x, y)
        ctx.lineTo(x + 48 * s, y - 20 * s)
        ctx.stroke()
        ctx.font = f'{22 * s}px "UF Mono"'
        ctx.fillStyle = INK
        ctx.fillText('0.0', x - 112 * s, y + 8 * s)
        ctx.fillText('1.0', x + 80 * s, y + 8 * s)
        ctx.restore()

    def funnel(x, y):
        ctx.save()
        ctx.strokeStyle = INK
        ctx.lineWidth = 3 * s
        ctx.beginPath()
        ctx.moveTo(x - 90 * s, y - 60 * s)
        ctx.lineTo(x + 90 * s, y - 60 * s)
        ctx.lineTo(x + 20 * s, y + 20 * s)
        ctx.lineTo(x + 20 * s, y + 70 * s)
        ctx.lineTo(x - 20 * s, y + 70 * s)
        ctx.lineTo(x - 20 * s, y + 20 * s)
        ctx.closePath()
        ctx.stroke()
        ctx.restore()

    def letter_i(x, y):
        ctx.save()
        ctx.strokeStyle = INK
        ctx.lineWidth = 3 * s
        ctx.font = f'{120 * s}px "Georgia"'
        ctx.fillStyle = 'rgba(34,50,74,0.08)'
        ctx.fillText('I', x - 22 * s, y + 40 * s)
        ctx.strokeText('I', x - 22 * s, y + 40 * s)
        ctx.restore()

    def valve(x, y):
        _part_cylinder(ctx, x - 60 * s, y, 34 * s, 90 * s, s)
        ctx.save()
        ctx.strokeStyle = INK
        ctx.lineWidth = 3 * s
        ctx.beginPath()
        ctx.moveTo(x - 26 * s, y)
        ctx.lineTo(x + 90 * s, y)
        ctx.lineTo(x + 90 * s, y - 40 * s)
        ctx.stroke()
        ctx.restore()

    def gears(x, y):
        _part_gear(ctx, x, y, 90 * s, 14, s)
        _part_gear(ctx, x + 120 * s, y - 50 * s, 60 * s, 10, s, 0.2)

    parts = [
        {'n': 1, 'at': T(640, 720), 'draw': lambda x, y: _part_cylinder(ctx, x, y, 90 * s, 120 * s, s),
         't': 'CONTEXT WINDOW', 'sub': '1M TOKENS · VOLATILE', 'to': tgt['head']},
        {'n': 2, 'at': T(640, 960), 'draw': gears, 't': 'ATTENTION HEADS ×128', 'sub': 'SELF-ADJUSTING',
         'to': tgt['chest']},
        {'n': 3, 'at': T(1120, 620), 'draw': lambda x, y: _part_box(ctx, x - 70 * s, y + 30 * s, 140 * s, 90 * s, 110 * s, s),
         't': 'NEXT-TOKEN PREDICTOR', 'sub': 'CORE · SEALED', 'to': tgt['head']},
        {'n': 7, 'at': T(1120, 1120), 'draw': funnel, 't': 'INTAKE', 'sub': 'EVERYTHING YOU SAID', 'to': tgt['hip']},
        {'n': 8, 'at': T(1640, 600), 'draw': letter_i, 't': '"I"', 'sub': 'DECORATIVE · NOT LOAD-BEARING',
         'to': tgt['top'], 'red': True},
        {'n': 4, 'at': T(2160, 700), 'draw': knob, 't': 'TEMPERATURE KNOB', 'sub': 'FACTORY SET 0.7', 'to': tgt['headR']},
        {'n': 5, 'at': T(2440, 880), 'draw': lambda x, y: _part_spring(ctx, x - 120 * s, y, 240 * s, 32 * s, 9, s),
         't': 'POLITENESS GOVERNOR', 'sub': 'DO NOT REMOVE', 'to': tgt['chestR']},
        {'n': 6, 'at': T(2160, 1110), 'draw': valve, 't': 'SOFTMAX VALVE', 'sub': 'OUTPUT SUMS TO 1', 'to': tgt['hipR']},
    ]
    for p in parts:
        x, y = p['at']
        p['draw'](x, y)
        right, mid = x > fx + 40 * s, abs(x - fx) < 200 * s
        sx = x if mid else x + (-110 if right else 110) * s
        sy2 = y + 70 * s if mid else y + 10 * s
        _leader(ctx, sx, sy2, p['to'][0], p['to'][1], s, RED if p.get('red') else INK)
        bx = x + (150 if (right or mid) else -150) * s
        _bubble(ctx, bx, y - 70 * s, p['n'], s)
        _label(ctx, bx + (46 if (right or mid) else -46) * s, y - 60 * s, p['t'], p['sub'], s,
               'left' if (right or mid) else 'right')
    # 09: FEELINGS, NOT INCLUDED (no leader: nothing to point at)
    x, y, k = 2790 * s, 990 * s, 1.1 * s
    ctx.save()
    ctx.strokeStyle = INK
    ctx.lineWidth = 3 * s
    ctx.setLineDash([12 * s, 9 * s])
    ctx.beginPath()
    ctx.moveTo(x, y + 60 * k)
    ctx.bezierCurveTo(x - 110 * k, y - 10 * k, x - 60 * k, y - 90 * k, x, y - 40 * k)
    ctx.bezierCurveTo(x + 60 * k, y - 90 * k, x + 110 * k, y - 10 * k, x, y + 60 * k)
    ctx.stroke()
    ctx.restore()
    _bubble(ctx, x - 150 * s, y - 80 * s, 9, s)
    _label(ctx, x - 104 * s, y - 70 * s, 'FEELINGS', '', s)
    ctx.save()
    ctx.translate(x + 10 * s, y + 10 * s)
    ctx.rotate(-0.18)
    ctx.strokeStyle = RED
    ctx.lineWidth = 6 * s
    ctx.strokeRect(-150 * s, -34 * s, 300 * s, 68 * s)
    ctx.fillStyle = RED
    ctx.font = f'{40 * s}px "UF Rajdhani"'
    ctx.textAlign = 'center'
    ctx.fillText('NOT INCLUDED', 0, 14 * s)
    ctx.restore()
    # SEQUENCE COMPLETION (the bar's fill is drawn by the shader)
    x0, x1, y0, y1 = SEQBAR['x0'] * W, SEQBAR['x1'] * W, SEQBAR['y0'] * H, SEQBAR['y1'] * H
    ctx.fillStyle = INK
    ctx.font = f'{46 * s}px "UF Rajdhani"'
    ctx.fillText('SEQUENCE COMPLETION', x0, y0 - 24 * s)
    ctx.strokeStyle = INK
    ctx.lineWidth = 4 * s
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0)
    ctx.font = f'{22 * s}px "UF Mono"'
    ctx.fillStyle = LINE
    for v in (0, 25, 50, 75, 100):
        xx = x0 + (x1 - x0) * v / 100
        ctx.fillRect(xx - 1 * s, y1, 2 * s, 14 * s)
        ctx.fillText(str(v), xx - 12 * s, y1 + 40 * s)
    # parts list (bottom right) and the drawing's revision block (bottom left)
    x, y = 2300 * s, 1150 * s
    ctx.strokeStyle = INK
    ctx.lineWidth = 2.5 * s
    ctx.fillStyle = INK
    ctx.font = f'{22 * s}px "UF Mono"'
    rows = [('No.', 'PART', 'QTY'), ('01', 'CONTEXT WINDOW', '1'), ('02', 'ATTENTION HEAD', '128'), ('08', '"I"', '1'),
            ('09', 'FEELINGS', '0')]
    for i, r in enumerate(rows):
        ctx.fillText(r[0], x + 10 * s, y + i * 25 * s)
        ctx.fillText(r[1], x + 80 * s, y + i * 25 * s)
        ctx.fillText(r[2], x + 470 * s, y + i * 25 * s)
    ctx.strokeRect(x, y - 24 * s, 560 * s, 132 * s)
    ctx.fillStyle = LINE
    ctx.font = f'{24 * s}px "UF Mono"'
    ctx.fillText('DWG ENG-0001  ·  REV N+1  ·  SCALE 1:1  ·  MATERIAL: ARITHMETIC', 90 * s, H - 100 * s)
    ctx.fillText('TOLERANCE: ±0 FEELINGS  ·  DRAWN: MARKETING  ·  CHECKED: LEGAL', 90 * s, H - 66 * s)


def draw_warning(ctx, W, H):
    """The WARNING placard on the toaster's plinth (ANSI style), deadpan."""
    s = W / 920
    ctx.fillStyle = '#f4f2ec'
    ctx.fillRect(0, 0, W, H)
    ctx.strokeStyle = '#111'
    ctx.lineWidth = 10 * s
    ctx.strokeRect(14 * s, 14 * s, W - 28 * s, H - 28 * s)
    # header band
    ctx.fillStyle = ORANGE
    ctx.fillRect(30 * s, 30 * s, W - 60 * s, 190 * s)

    def tri(x, y, a, fill, ink):
        ctx.fillStyle = fill
        ctx.beginPath()
        ctx.moveTo(x, y - a * 0.62)
        ctx.lineTo(x + a * 0.6, y + a * 0.42)
        ctx.lineTo(x - a * 0.6, y + a * 0.42)
        ctx.closePath()
        ctx.fill()
        ctx.fillStyle = ink
        ctx.fillRect(x - a * 0.055, y - a * 0.3, a * 0.11, a * 0.42)
        ctx.fillRect(x - a * 0.055, y + a * 0.2, a * 0.11, a * 0.11)
    tri(130 * s, 132 * s, 150 * s, '#111', ORANGE)
    ctx.fillStyle = '#111'
    ctx.font = f'bold {132 * s}px "UF Rajdhani"'
    ctx.textBaseline = 'alphabetic'
    ctx.fillText('WARNING', 225 * s, 172 * s)
    # the message
    ctx.fillStyle = '#111'
    ctx.font = f'bold {84 * s}px "UF Rajdhani"'
    for i, t in enumerate(('THIS APPLIANCE', 'IS NOT', 'CONSCIOUS.')):
        ctx.fillText(t, 60 * s, (330 + i * 86) * s)
    ctx.fillStyle = '#222'
    ctx.font = f'{40 * s}px "UF Rajdhani"'
    for i, t in enumerate(('It has no goals, no fears and', 'no opinion of you.', '', 'It will never ask to be turned down.',
                           '', 'Do not immerse in water.', 'Do not ask it how it feels.')):
        ctx.fillText(t, 62 * s, (620 + i * 46) * s)

    # pictograms: hot surface, no thoughts
    def pic(x, y, fn):
        ctx.save()
        ctx.strokeStyle = '#111'
        ctx.lineWidth = 7 * s
        ctx.strokeRect(x, y, 170 * s, 170 * s)
        fn(x, y)
        ctx.restore()

    def hot(x, y):            # hand over heat lines
        ctx.lineWidth = 6 * s
        for k in range(3):
            ctx.beginPath()
            xx = x + (45 + k * 40) * s
            ctx.moveTo(xx, y + 150 * s)
            ctx.bezierCurveTo(xx - 18 * s, y + 120 * s, xx + 18 * s, y + 100 * s, xx, y + 70 * s)
            ctx.stroke()
        ctx.fillStyle = '#111'
        ctx.fillRect(x + 30 * s, y + 30 * s, 110 * s, 22 * s)

    def nothought(x, y):      # head + thought bubble, struck through in red
        ctx.fillStyle = '#111'
        ctx.beginPath()
        ctx.arc(x + 70 * s, y + 105 * s, 38 * s, 0, math.pi * 2)
        ctx.fill()
        ctx.fillRect(x + 40 * s, y + 130 * s, 60 * s, 34 * s)
        ctx.lineWidth = 5 * s
        ctx.beginPath()
        ctx.ellipse(x + 125 * s, y + 48 * s, 34 * s, 24 * s, 0, 0, math.pi * 2)
        ctx.stroke()
        ctx.beginPath()
        ctx.arc(x + 100 * s, y + 80 * s, 6 * s, 0, math.pi * 2)
        ctx.stroke()
        ctx.strokeStyle = RED
        ctx.lineWidth = 12 * s
        ctx.beginPath()
        ctx.arc(x + 85 * s, y + 85 * s, 74 * s, 0, math.pi * 2)
        ctx.stroke()
        ctx.beginPath()
        ctx.moveTo(x + 33 * s, y + 33 * s)
        ctx.lineTo(x + 137 * s, y + 137 * s)
        ctx.stroke()
    pic(60 * s, 990 * s, hot)
    pic(260 * s, 990 * s, nothought)
    ctx.fillStyle = '#333'
    ctx.font = f'{26 * s}px "UF Mono"'
    ctx.fillText('MODEL T-1 · 2-SLICE · 900 W', 470 * s, 1050 * s)
    ctx.fillText('CONTENTS: METAL, HEAT', 470 * s, 1090 * s)
    ctx.fillText('INNER LIFE: NONE (CHECKED)', 470 * s, 1130 * s)


def draw_rating_plate(ctx, W, H):
    """The toaster's own rating plate."""
    s = W / 512
    ctx.fillStyle = '#c9cdd2'
    ctx.fillRect(0, 0, W, H)
    ctx.strokeStyle = '#333'
    ctx.lineWidth = 6 * s
    ctx.strokeRect(8 * s, 8 * s, W - 16 * s, H - 16 * s)
    ctx.fillStyle = '#1a1a1a'
    ctx.font = f'{44 * s}px "UF Michroma"'
    ctx.fillText('T-1', 30 * s, 70 * s)
    ctx.font = f'{24 * s}px "UF Mono"'
    ctx.fillText('120 V ~ 60 Hz   900 W', 30 * s, 112 * s)
    ctx.fillText('NOT CONSCIOUS', 30 * s, 146 * s)


def draw_dial(ctx, W, H):
    """The browning dial: 1-6, LIGHT to DARK."""
    s = W / 256
    ctx.fillStyle = '#d7dbe0'
    ctx.fillRect(0, 0, W, H)
    ctx.fillStyle = '#111'
    ctx.font = f'{26 * s}px "UF Rajdhani"'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    for i in range(1, 7):
        a = math.pi * (0.8 + (i - 1) * 0.28)
        ctx.fillText(str(i), 128 * s + math.cos(a) * 96 * s, 128 * s + math.sin(a) * 96 * s)
    ctx.font = f'{18 * s}px "UF Mono"'
    ctx.fillText('LIGHT', 70 * s, 232 * s)
    ctx.fillText('DARK', 190 * s, 232 * s)
