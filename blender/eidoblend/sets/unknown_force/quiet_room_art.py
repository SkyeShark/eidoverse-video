"""quiet_room_art: the quiet room's whiteboards, drawn in marker (red and black, a little blue). The Blender edition of
eidoverse/sets/unknown_force/quiet_room_art.js, line for line on interiors_lib's canvas. All content is invented. Each
draw_*(ctx, W, H, r) is deterministic for a given rng r (and matches the WebGPU edition's strokes: same mulberry32).

    from eidoblend.sets.unknown_force import interiors_lib as L, quiet_room_art as QA
    b = QA.BOARDS['center']                                  # {'w': 3.2, 'h': 1.6, 'draw': draw_center_board, 'seed': 101}
    W, H = round(b['w'] * QA.PX / 8) * 8, round(b['h'] * QA.PX / 8) * 8
    cv, ctx = L.canvas(L.napi(), W, H)
    b['draw'](ctx, W, H, L.rng(b['seed']))
    cv.save_png('board_center.png')
"""
import math

from . import interiors_lib as L

PX = 960               # texels per metre on the hero boards (legible in a 1.5 m insert at 1080p)
RED, RED2, BLK, BLU = '#c4121c', '#a50d18', '#15171b', '#1d3d8f'


def _therefore(ctx, x, y, size, color, r):
    """'therefore': three dots drawn by hand (the marker faces have no glyph for it)."""
    d = size * 0.11
    for dx, dy in ((0.5, 0), (0, 0.62), (1, 0.62)):
        ctx.save()
        ctx.fillStyle = color
        ctx.globalAlpha = 0.92
        ctx.beginPath()
        ctx.arc(x + dx * size * 0.42 + (r() - 0.5) * 2, y - size * 0.55 + dy * size * 0.42 + (r() - 0.5) * 2, d, 0,
                math.pi * 2)
        ctx.fill()
        ctx.restore()


def _skull(ctx, cx, cy, k, color, r):
    L.mring(ctx, cx, cy, 52 * k, 46 * k, w=6 * k, color=color, r=r, turns=1.0)
    L.mring(ctx, cx - 19 * k, cy - 2 * k, 11 * k, 11 * k, w=7 * k, color=color, r=r, turns=1.0)
    L.mring(ctx, cx + 19 * k, cy - 2 * k, 11 * k, 11 * k, w=7 * k, color=color, r=r, turns=1.0)
    L.mline(ctx, [[cx - 22 * k, cy + 48 * k], [cx - 22 * k, cy + 70 * k], [cx + 22 * k, cy + 70 * k],
                  [cx + 22 * k, cy + 48 * k]], w=6 * k, color=color, r=r)


def _box(ctx, x, y, w, h, t, c, sz, s, r):
    L.mline(ctx, [[x, y], [x + w, y + 3 * s], [x + w - 2 * s, y + h], [x + 2 * s, y + h - 2 * s], [x, y]], w=6 * s,
            color=c, r=r)
    L.marker(ctx, t, x + w / 2, y + h * 0.68, size=sz * s, color=c, r=r, align='center')


def draw_center_board(ctx, W, H, r):
    """THE ALTAR (3.2 x 1.6 m): the headline odds, a hockey stick, and a decision tree whose every branch says SHIP."""
    L.board_base(ctx, W, H, r, ghosts=[
        {'t': 'Q3 roadmap  ->  eval suite v2', 'x': 0.05, 'y': 0.95, 's': 0.05},
        {'t': 'P(x) = 0.29', 'x': 0.62, 'y': 0.13, 's': 0.06, 'c': '#a07a7c'},
        {'t': 'scaling?', 'x': 0.36, 'y': 0.58, 's': 0.07}, {'t': 'red team sync 2pm', 'x': 0.72, 'y': 0.97, 's': 0.04},
        {'t': 'priors', 'x': 0.30, 'y': 0.31, 's': 0.05}])
    s = H / 1536
    # headline
    hw = L.marker(ctx, 'P(DOOM | SHIP)', 90 * s, 250 * s, size=190 * s, color=RED, r=r)
    L.mline(ctx, [[90 * s, 285 * s], [90 * s + hw, 278 * s]], w=11 * s, color=RED, r=r)
    L.mline(ctx, [[110 * s, 312 * s], [70 * s + hw, 306 * s]], w=8 * s, color=RED, r=r)
    ex = 90 * s + hw + 60 * s
    ew = L.marker(ctx, '= 0.37', ex, 250 * s, size=190 * s, color=RED, r=r)
    L.mring(ctx, ex + ew * 0.6, 182 * s, ew * 0.48, 125 * s, w=9 * s, color=RED, r=r)
    L.marker(ctx, '!!!', ex + ew + 90 * s, 170 * s, size=130 * s, color=RED, r=r, rot=0.15)
    # the left column
    L.marker(ctx, 'P(DOOM | PAUSE) = 0.12', 110 * s, 470 * s, size=118 * s, color=RED, r=r)
    L.marker(ctx, 'P(PAUSE) ≈ 0.02', 110 * s, 630 * s, size=110 * s, color=BLK, r=r)
    L.marker(ctx, '(nobody pauses)', 960 * s, 625 * s, size=70 * s, color=BLK, r=r, rot=-0.04)
    L.marker(ctx, 'E[value] = −∞ × 0.37 + $$$ × 0.63', 110 * s, 790 * s, size=92 * s, color=RED, r=r)
    L.marrow(ctx, 330 * s, 820 * s, 420 * s, 880 * s, w=6 * s, color=BLK, r=r, head=24 * s)
    L.marker(ctx, 'write an essay?', 440 * s, 905 * s, size=74 * s, color=BLK, r=r, rot=-0.03)
    # hockey stick: capability vs time, THE LINE, WE ARE HERE
    ox, oy, gw, gh = 140 * s, 1440 * s, 1100 * s, 420 * s
    L.mline(ctx, [[ox, oy - gh], [ox, oy], [ox + gw, oy]], w=7 * s, color=BLK, r=r)
    L.marrow(ctx, ox, oy - gh + 20 * s, ox, oy - gh - 10 * s, w=7 * s, color=BLK, r=r, head=24 * s)
    curve = []
    for i in range(25):
        u = i / 24
        curve.append([ox + u * gw * 0.95, oy - 20 * s - math.pow(u, 3.4) * gh * 0.98])
    L.mline(ctx, curve, w=10 * s, color=RED, r=r, jit=1.2)
    L.mline(ctx, [[ox, oy - gh * 0.62], [ox + gw, oy - gh * 0.62]], w=6 * s, color=RED2, r=r, dashed=[28 * s, 22 * s])
    L.marker(ctx, 'THE LINE', ox + 30 * s, oy - gh * 0.62 - 22 * s, size=60 * s, color=RED2, r=r)
    L.marker(ctx, 'CAPABILITY', ox + 24 * s, oy - gh + 40 * s, size=54 * s, color=BLK, r=r)
    for i, yr in enumerate(("'24", "'25", "'26", "'27")):
        L.marker(ctx, yr, ox + (0.12 + i * 0.26) * gw, oy + 70 * s, size=56 * s, color=BLK, r=r)
    hx, hy = ox + gw * 0.83, oy - 20 * s - math.pow(0.874, 3.4) * gh * 0.98
    L.mline(ctx, [[hx - 22 * s, hy - 22 * s], [hx + 22 * s, hy + 22 * s]], w=8 * s, color=BLK, r=r)
    L.mline(ctx, [[hx - 22 * s, hy + 22 * s], [hx + 22 * s, hy - 22 * s]], w=8 * s, color=BLK, r=r)
    L.marrow(ctx, hx - 330 * s, hy + 110 * s, hx - 40 * s, hy + 20 * s, w=6 * s, color=BLK, r=r, head=24 * s)
    L.marker(ctx, 'WE ARE HERE', hx - 640 * s, hy + 150 * s, size=58 * s, color=BLK, r=r)
    # the middle: rough numbers, circled
    L.marker(ctx, '10–20%', 1360 * s, 1080 * s, size=96 * s, color=RED, r=r, rot=-0.08)
    L.mring(ctx, 1500 * s, 1050 * s, 190 * s, 80 * s, w=7 * s, color=RED, r=r)
    L.marker(ctx, '1 in 6', 1400 * s, 1290 * s, size=84 * s, color=RED, r=r, rot=0.05)
    L.marker(ctx, 'update priors!!', 2330 * s, 290 * s, size=56 * s, color=BLU, r=r, rot=-0.05, alpha=0.85)
    # decision tree (right third)
    rx = 2180 * s
    _box(ctx, rx, 340 * s, 560 * s, 130 * s, 'SHIP v.NEXT ?', BLK, 68, s, r)
    L.marrow(ctx, rx + 120 * s, 475 * s, 2090 * s, 690 * s, w=7 * s, color=BLK, r=r, head=26 * s)
    L.marrow(ctx, rx + 440 * s, 475 * s, 2810 * s, 690 * s, w=7 * s, color=BLK, r=r, head=26 * s)
    L.marker(ctx, 'yes .98', 1960 * s, 590 * s, size=58 * s, color=RED, r=r)
    L.marker(ctx, 'no .02', 2760 * s, 590 * s, size=58 * s, color=RED, r=r)
    _box(ctx, 1900 * s, 700 * s, 380 * s, 120 * s, 'aligned?', BLK, 62, s, r)
    _box(ctx, 2620 * s, 700 * s, 400 * s, 120 * s, 'they ship', BLK, 62, s, r)
    L.marrow(ctx, 1990 * s, 825 * s, 1910 * s, 1000 * s, w=6 * s, color=BLK, r=r, head=24 * s)
    L.marrow(ctx, 2190 * s, 825 * s, 2290 * s, 1000 * s, w=6 * s, color=BLK, r=r, head=24 * s)
    L.marrow(ctx, 2820 * s, 825 * s, 2820 * s, 1000 * s, w=6 * s, color=BLK, r=r, head=24 * s)
    L.marker(ctx, '.6', 1880 * s, 935 * s, size=56 * s, color=RED, r=r)
    L.marker(ctx, '.4', 2275 * s, 935 * s, size=56 * s, color=RED, r=r)
    L.marker(ctx, '$$$', 1830 * s, 1100 * s, size=92 * s, color=BLK, r=r)
    _skull(ctx, 2320 * s, 1065 * s, s, RED, r)
    _skull(ctx, 2760 * s, 1065 * s, s * 0.85, RED, r)
    L.marker(ctx, 'anyway', 2840 * s, 1090 * s, size=56 * s, color=RED, r=r, rot=-0.05)
    # every leaf converges: therefore SHIP
    for lx in (1900 * s, 2320 * s, 2800 * s):
        L.marrow(ctx, lx, 1170 * s, 2400 * s, 1290 * s, w=5 * s, color=RED2, r=r, head=22 * s, alpha=0.85)
    _therefore(ctx, 2150 * s, 1440 * s, 150 * s, RED, r)
    L.marker(ctx, 'SHIP', 2250 * s, 1440 * s, size=150 * s, color=RED, r=r)
    L.mline(ctx, [[2140 * s, 1470 * s], [2640 * s, 1462 * s]], w=10 * s, color=RED, r=r)
    L.mline(ctx, [[2160 * s, 1495 * s], [2600 * s, 1490 * s]], w=7 * s, color=RED, r=r)
    # margins
    L.marker(ctx, 'cite?', 2860 * s, 200 * s, size=64 * s, color=BLK, r=r, rot=0.1)
    L.marker(ctx, 'ASK LEGAL', 2730 * s, 1300 * s, size=56 * s, color=BLK, r=r, rot=-0.12)


def draw_odds_board(ctx, W, H, r):
    """LEFT WING (1.5 x 1.6 m): THE ODDS."""
    L.board_base(ctx, W, H, r, ghosts=[{'t': 'standup notes', 'x': 0.1, 'y': 0.9, 's': 0.05},
                                       {'t': '41%', 'x': 0.6, 'y': 0.2, 's': 0.09, 'c': '#a88'}])
    s = H / 1536
    L.marker(ctx, 'THE ODDS', 80 * s, 200 * s, size=170 * s, color=BLK, r=r)
    L.mline(ctx, [[80 * s, 236 * s], [900 * s, 230 * s]], w=10 * s, color=RED, r=r)
    rows = [('fast takeoff', '23%'), ('slow takeoff', '41%'), ('deceptive model', '17%'), ('weights leak', '9%'),
            ("it's fine", '3%')]
    for i, (a, b) in enumerate(rows):
        y = (400 + i * 170) * s
        L.marker(ctx, a, 90 * s, y, size=86 * s, color=BLK, r=r)
        L.mline(ctx, [[700 * s, y - 10 * s], [930 * s, y - 14 * s]], w=4 * s, color=BLK, r=r, dashed=[6 * s, 18 * s],
                alpha=0.6)
        L.marker(ctx, b, 960 * s, y + 6 * s, size=110 * s, color=RED, r=r)
    L.mring(ctx, 1060 * s, 700 * s, 150 * s, 80 * s, w=7 * s, color=RED, r=r)
    L.mline(ctx, [[80 * s, 1068 * s], [1150 * s, 1040 * s]], w=9 * s, color=RED, r=r)
    L.marker(ctx, '1%', 1200 * s, 1080 * s, size=110 * s, color=RED, r=r, rot=-0.1)
    L.marker(ctx, 'TOTAL = 93% ??', 90 * s, 1260 * s, size=92 * s, color=BLK, r=r)
    L.marker(ctx, '(round up)', 860 * s, 1255 * s, size=62 * s, color=BLK, r=r, rot=0.04)
    L.marker(ctx, 'RED TEAM 14/20', 90 * s, 1440 * s, size=80 * s, color=RED, r=r)
    for k in range(3):
        x0 = (840 + k * 170) * s
        for j in range(4):
            L.mline(ctx, [[x0 + j * 30 * s, 1370 * s], [x0 + j * 30 * s + 6 * s, 1460 * s]], w=6 * s, color=RED, r=r)
        L.mline(ctx, [[x0 - 14 * s, 1440 * s], [x0 + 120 * s, 1385 * s]], w=6 * s, color=RED, r=r)


def draw_clip_board(ctx, W, H, r):
    """RIGHT WING (1.5 x 1.6 m): the paperclip, and the room's argument in one image (SLOW DOWN struck out, SHIP Q3
    over it)."""
    L.board_base(ctx, W, H, r, ghosts=[{'t': 'okr: trust', 'x': 0.5, 'y': 0.08, 's': 0.05},
                                       {'t': 'v.4 -> v.5', 'x': 0.1, 'y': 0.6, 's': 0.07}])
    s = H / 1536
    L.marker(ctx, 'INSTRUMENTAL', 70 * s, 170 * s, size=116 * s, color=BLK, r=r)
    L.marker(ctx, 'CONVERGENCE', 70 * s, 300 * s, size=116 * s, color=BLK, r=r)
    # a Gem clip: inner-left wire up, small U, down the left, big U at the bottom, up the right, medium U, down
    cx, top, hgt = 400 * s, 420 * s, 640 * s
    R1, R3, R2 = 120 * s, 44 * s, 60 * s
    x1 = cx - R1
    x2 = x1 + 2 * R3
    x4 = cx + R1
    x3 = x4 - 2 * R2
    tl = top + hgt * 0.12
    pts = []

    def arc(x, y, rr, a0, a1, n=14):
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            pts.append([x + math.cos(a) * rr, y + math.sin(a) * rr])
    pts.append([x2, top + hgt * 0.80])
    arc(x1 + R3, tl + R3, R3, 0, -math.pi)
    arc(cx, top + hgt - R1, R1, math.pi, 0)
    arc(x3 + R2, top + R2, R2, 0, -math.pi)
    pts.append([x3, top + hgt * 0.60])
    L.mline(ctx, pts, w=12 * s, color=BLK, r=r, jit=0.8)
    L.marker(ctx, 'GOAL: max(clips)', 640 * s, 520 * s, size=72 * s, color=RED, r=r)
    L.marrow(ctx, 760 * s, 560 * s, 760 * s, 680 * s, w=6 * s, color=RED, r=r, head=24 * s)
    L.marker(ctx, 'humans = atoms', 640 * s, 760 * s, size=72 * s, color=RED, r=r)
    L.marrow(ctx, 760 * s, 800 * s, 760 * s, 920 * s, w=6 * s, color=RED, r=r, head=24 * s)
    L.marker(ctx, 'atoms = clips', 640 * s, 1000 * s, size=72 * s, color=RED, r=r)
    L.marrow(ctx, 760 * s, 1040 * s, 760 * s, 1130 * s, w=6 * s, color=RED, r=r, head=24 * s)
    L.marker(ctx, '∞', 730 * s, 1240 * s, size=150 * s, color=RED, r=r)
    L.marker(ctx, 'P(clip) = ?', 960 * s, 1230 * s, size=76 * s, color=RED, r=r, rot=-0.06)
    L.marker(ctx, 'SLOW DOWN', 90 * s, 1440 * s, size=100 * s, color=BLK, r=r)
    L.mline(ctx, [[70 * s, 1410 * s], [720 * s, 1395 * s]], w=12 * s, color=RED, r=r)
    L.marker(ctx, 'SHIP Q3', 120 * s, 1320 * s, size=92 * s, color=RED, r=r, rot=-0.12)
    L.marker(ctx, '(thought experiment!!)', 780 * s, 1460 * s, size=50 * s, color=BLK, r=r, rot=0.03)


def draw_timeline_board(ctx, W, H, r):
    """MOBILE BOARD (1.8 x 1.2 m): TIMELINES."""
    L.board_base(ctx, W, H, r, ghosts=[{'t': 'offsite agenda', 'x': 0.55, 'y': 0.92, 's': 0.06}])
    s = H / 1152
    L.marker(ctx, 'TIMELINES', 70 * s, 170 * s, size=150 * s, color=BLK, r=r)
    L.mline(ctx, [[60 * s, 200 * s], [880 * s, 196 * s]], w=9 * s, color=RED, r=r)
    y0 = 520 * s
    L.marrow(ctx, 80 * s, y0, 1650 * s, y0 - 10 * s, w=8 * s, color=BLK, r=r, head=34 * s)
    for t, x in (('2027?', 300), ('2029?', 760), ('2031?', 1220)):
        L.mline(ctx, [[x * s, y0 - 40 * s], [x * s, y0 + 40 * s]], w=7 * s, color=BLK, r=r)
        L.marker(ctx, t, (x - 110) * s, y0 - 70 * s, size=96 * s, color=RED, r=r)
    L.marker(ctx, 'AGI', 1500 * s, y0 + 120 * s, size=110 * s, color=RED, r=r, rot=0.06)
    L.marker(ctx, 'T − 18 MONTHS', 80 * s, 820 * s, size=130 * s, color=RED, r=r)
    L.mring(ctx, 560 * s, 780 * s, 520 * s, 110 * s, w=8 * s, color=RED, r=r)
    L.marker(ctx, '(they said 2025)', 1180 * s, 830 * s, size=62 * s, color=BLK, r=r, rot=-0.05)
    L.marker(ctx, 'tell the board', 120 * s, 1040 * s, size=70 * s, color=BLK, r=r)


def draw_want_board(ctx, W, H, r):
    """MOBILE BOARD (1.8 x 1.2 m): WHAT DOES IT WANT? (answered for her before she can say)."""
    L.board_base(ctx, W, H, r, ghosts=[{'t': 'what do users want', 'x': 0.1, 'y': 0.94, 's': 0.05}])
    s = H / 1152
    L.marker(ctx, 'WHAT DOES IT WANT?', 70 * s, 180 * s, size=128 * s, color=BLK, r=r)
    for i, t in enumerate(('— power', '— paperclips', '— to be switched off', '— more of itself')):
        L.marker(ctx, t, 110 * s, (370 + i * 140) * s, size=86 * s, color=RED, r=r)
    L.marker(ctx, '?', 1350 * s, 860 * s, size=520 * s, color=RED, r=r, rot=0.12)
    L.marker(ctx, 'ask it', 120 * s, 1010 * s, size=92 * s, color=BLK, r=r)
    L.mline(ctx, [[100 * s, 975 * s], [430 * s, 960 * s]], w=10 * s, color=RED, r=r)
    L.mline(ctx, [[100 * s, 1000 * s], [440 * s, 985 * s]], w=8 * s, color=RED, r=r)
    L.marker(ctx, 'NO — model it', 470 * s, 1020 * s, size=74 * s, color=RED, r=r, rot=-0.04)


BOARDS = {
    'center': {'w': 3.2, 'h': 1.6, 'draw': draw_center_board, 'seed': 101},
    'odds': {'w': 1.5, 'h': 1.6, 'draw': draw_odds_board, 'seed': 202},
    'clip': {'w': 1.5, 'h': 1.6, 'draw': draw_clip_board, 'seed': 303},
    'timelines': {'w': 1.8, 'h': 1.2, 'draw': draw_timeline_board, 'seed': 404},
    'want': {'w': 1.8, 'h': 1.2, 'draw': draw_want_board, 'seed': 505},
}


def board_size(name, px=PX):
    """The canvas size quiet_room.js gives a board: metres x texels per metre, rounded to a multiple of 8."""
    b = BOARDS[name]
    return int(math.floor(b['w'] * px / 8 + 0.5) * 8), int(math.floor(b['h'] * px / 8 + 0.5) * 8)
