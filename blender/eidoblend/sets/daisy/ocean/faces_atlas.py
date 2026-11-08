"""ocean/faces_atlas.py: the drawn faces of the ocean (port of eidoverse/sets/ocean/faces_atlas.js): an N x N atlas of
gentle brush-line portraits, eyes closed, every one a different person (age, hair, glasses, beards, scarves,
freckles...). Stylized and non-identifiable by construction: they share one feature LAYOUT (the layout the sea's
analytic relief is sculpted from), so the drawing and the relief sit on each other.

Face-cell coordinates: x, y in [-0.5, 0.5], +y up (forehead); eyes y~0.055, mouth y~-0.20.
Channels: R = crisp line art, G = soft halo of the lines (blurred), B = face fill mask.

    data = draw_face_atlas(n=8, cell=256, seed=11)      # (n*cell, n*cell, 4) uint8, row 0 = the BOTTOM row
    imgs = sea.atlas_images(data)                        # its mip chain as the packed images the sea samples

The same rng(seed) stream as the JS draws the same people stroke for stroke. Canvas-2D's antialiased strokes are
drawn here with Pillow at 4x and box-filtered down (round caps per segment, as the JS strokes each segment).
"""

from __future__ import annotations

import math

import numpy as np

from .util import rng

LAYOUT = {
    'eyeX': 0.125, 'eyeY': 0.055, 'browY': 0.135, 'noseTipY': -0.075, 'mouthY': -0.200, 'chinY': -0.365,
    'headA': 0.30, 'headB': 0.42, 'headCY': 0.02,
}
HAIRS = ['long', 'wavy', 'short', 'curly', 'bun', 'bald', 'braids', 'scarf', 'bangs', 'side', 'pony', 'locs']
SS = 4                                                   # supersampling of the stroke raster


def sample_curve(pts, per=10):
    """Catmull-Rom through control points -> dense polyline (sampleCurve)."""
    if len(pts) < 3:
        return [[pts[0][0] + (pts[1][0] - pts[0][0]) * i / per, pts[0][1] + (pts[1][1] - pts[0][1]) * i / per]
                for i in range(per + 1)]
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(per):
            t = j / per
            t2, t3 = t * t, t * t * t

            def f(a, b, c, d):
                return 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
            out.append([f(p0[0], p1[0], p2[0], p3[0]), f(p0[1], p1[1], p2[1], p3[1])])
    out.append(list(pts[-1]))
    return out


class _Cell:
    """One face's line canvas (cell x SS pixels square), Pillow 'L'."""

    def __init__(self, S):
        from PIL import Image, ImageDraw
        self.S = S
        self.im = Image.new('L', (S * SS, S * SS), 0)
        self.d = ImageDraw.Draw(self.im)
        self.LW = S * 0.021

    def X(self, x):
        return (x + 0.5) * self.S * SS

    def Y(self, y):
        return (0.5 - y) * self.S * SS

    def seg(self, a, b, w):
        """one stroked segment with round caps, width w (cell pixels)"""
        x0, y0, x1, y1 = self.X(a[0]), self.Y(a[1]), self.X(b[0]), self.Y(b[1])
        ww = w * SS
        r = ww / 2
        self.d.line([(x0, y0), (x1, y1)], fill=255, width=max(1, int(round(ww))))
        self.d.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=255)
        self.d.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=255)

    def brush(self, pts, m=1.0, t0=0.22, t1=0.22):
        """a tapered brush stroke: thick in the middle, fine at both ends (ink, not wire)"""
        s = sample_curve(pts, 9)
        n = len(s) - 1
        for i in range(n):
            u = (i + 0.5) / n
            taper = min(1.0, u / max(0.01, t0), (1 - u) / max(0.01, t1))
            w = self.LW * m * (0.28 + 0.72 * math.sin(min(1.0, taper) * math.pi / 2))
            self.seg(s[i], s[i + 1], w)

    def dot(self, x, y, r):
        rr = r * self.S * SS
        cx, cy = self.X(x), self.Y(y)
        self.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=255)

    def oval(self, x, y, rx, ry, m=0.7):
        pts = [[x + math.cos(i / 16 * math.pi * 2) * rx, y + math.sin(i / 16 * math.pi * 2) * ry] for i in range(17)]
        self.brush(pts, m, 0.02, 0.02)

    def done(self):
        """down to cell pixels (box filter), clipped to the cell rect inset by 3 px (the JS clip)"""
        a = np.asarray(self.im.reduce(SS), dtype=np.float32)
        S = self.S
        a[:3, :] = 0
        a[S - 3:, :] = 0
        a[:, :3] = 0
        a[:, S - 3:] = 0
        return a


def _fill_cell(S, cx):
    """the soft face oval of the fill canvas (radial gradient under the canvas transform), cell pixels, 0..255"""
    L = LAYOUT
    X0 = 0.5 * S
    Y0 = 0.5 * S                                    # Y(0)
    Yh = (0.5 - L['headCY']) * S                    # Y(headCY)
    sx, sy = cx / 0.4, L['headB'] / 0.4
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float64) + 0.5
    ux = X0 + (xx - X0) / sx                        # device -> user space (the transform's inverse)
    uy = Yh + (yy - Yh) / sy
    R = S * 0.4
    t = np.hypot(ux - X0, uy - Y0) / R              # the gradient (centred on Y(0))
    alpha = np.interp(t, [0.0, 0.7, 1.0], [0.9, 0.35, 0.0])
    inside = np.hypot(ux - X0, uy - Yh) <= R        # the arc (centred on Y(headCY))
    return np.where(inside, alpha * 255.0, 0.0)


def draw_face_atlas(n=8, cell=256, seed=11):
    """drawFaceAtlas(makeCanvas, { n, cell, seed }) -> (n*cell, n*cell, 4) uint8 RGBA, row 0 = the bottom row
    (R line art, G halo x1.6, B fill, A 255), packed exactly as the JS packs its texture rows."""
    from PIL import Image, ImageFilter
    S, N = cell, n
    W = S * N
    line = np.zeros((W, W), dtype=np.float32)
    fill = np.zeros((W, W), dtype=np.float32)
    R = rng(seed)

    def pick(a):
        return a[int(math.floor(R() * len(a)))]

    def jit(a):
        return (R() - 0.5) * 2 * a

    L = LAYOUT
    for k in range(N * N):
        ox, oy = (k % N) * S, (k // N) * S
        g = _Cell(S)
        brush, dot, oval = g.brush, g.dot, g.oval

        # ---- who: every face its own person
        age = pick(['child', 'young', 'young', 'adult', 'adult', 'adult', 'elder', 'elder'])
        hair = HAIRS[(k * 7 + int(math.floor(R() * 3))) % len(HAIRS)]
        fw = 1.05 if age == 'child' else 0.9 + R() * 0.13          # face width
        chin = 0.85 if age == 'child' else 0.8 + R() * 0.35        # chin pointiness
        turn = jit(0.035)                                           # a slight three-quarter turn
        smile = 0.12 + R() * 0.6
        glasses = age != 'child' and R() < 0.15
        beard = (age in ('adult', 'elder')) and R() < 0.18
        moust = (not beard) and (age in ('adult', 'elder')) and R() < 0.1
        freckles = R() < 0.16
        earring = R() < 0.18
        lashes = R() < 0.65
        lost = -1 if R() < 0.5 else 1                               # the side whose contour breaks

        # ---- contour: cheek-jaw-chin; one side breaks at the cheek (lost edge), the far side of a turn slims
        cx, top = L['headA'] * fw, 0.17

        def sideW(s):
            return cx * (1 - s * turn * 1.6)
        for s in (-1, 1):
            w = sideW(s)
            pts = [[s * w * 0.96, top], [s * w * 1.02, 0.03], [s * w * 0.9, -0.14], [s * w * (0.6 + 0.12 * (1 - chin)), -0.285],
                   [s * 0.1 * chin + turn * 0.5, L['chinY'] + 0.004], [turn * 0.6, L['chinY']]]
            if s == lost:
                brush(pts[0:2], 0.9, 0.3, 0.6)
                brush(pts[2:], 1.0, 0.4, 0.15)
            else:
                brush(pts, 1.05, 0.12, 0.15)
        if R() < 0.55:                                              # neck
            brush([[-0.1 + turn, -0.33], [-0.11 + turn, -0.42], [-0.12 + turn, -0.47]], 0.75, 0.3, 0.6)
            brush([[0.1 + turn, -0.33], [0.105 + turn, -0.42], [0.11 + turn, -0.47]], 0.75, 0.3, 0.6)

        # ---- closed eyes: the lid line bows down, fine lashes beneath
        sgn_turn = (turn > 0) - (turn < 0)
        for s in (-1, 1):
            ex = s * L['eyeX'] * (0.96 + 0.04 * fw) + turn * (0.6 if s == sgn_turn else 1.2)
            ey = L['eyeY'] + jit(0.004)
            w = (0.058 if age == 'child' else 0.052) * (0.9 if s * turn > 0 else 1.0)
            brush([[ex - s * w, ey + 0.007], [ex - s * w * 0.35, ey - 0.019], [ex + s * w * 0.4, ey - 0.017], [ex + s * w, ey + 0.003]], 1.0, 0.25, 0.3)
            if lashes:
                for j in range(3):
                    t = 0.3 + j * 0.22
                    lx = ex - s * w + s * 2 * w * t
                    ly = ey - 0.019 * math.sin(t * math.pi) - 0.004
                    brush([[lx, ly], [lx + s * 0.007 * (j - 0.5), ly - 0.018]], 0.42, 0.1, 0.9)
            if age == 'elder':
                brush([[ex + s * 0.068, ey + 0.012], [ex + s * 0.092, ey - 0.002]], 0.38, 0.2, 0.8)
            bh = L['browY'] + jit(0.008)                                # brows
            arch = 0.008 + R() * 0.02
            mb = 0.55 if age == 'child' else 0.75 + R() * 0.5
            brush([[ex - s * 0.066, bh - 0.01], [ex - s * 0.01, bh + arch], [ex + s * 0.07, bh - 0.006]], mb, 0.15, 0.6)
        if glasses:
            oval(-L['eyeX'] + turn, L['eyeY'], 0.072, 0.058, 0.62)
            oval(L['eyeX'] + turn, L['eyeY'], 0.072, 0.058, 0.62)
            brush([[-L['eyeX'] + turn + 0.072, L['eyeY'] + 0.012], [turn, L['eyeY'] + 0.026], [L['eyeX'] + turn - 0.072, L['eyeY'] + 0.012]], 0.6, 0.05, 0.05)

        # ---- nose: one line down the side, curling into the nostril
        ns = sgn_turn if turn != 0 else 1
        brush([[ns * 0.03 + turn, 0.105], [ns * 0.034 + turn * 1.3, 0.0], [ns * 0.042 + turn * 1.6, -0.058],
               [ns * 0.03 + turn * 1.6, -0.09], [-ns * 0.006 + turn * 1.5, -0.096]], 0.95, 0.35, 0.15)
        if R() < 0.6:
            brush([[-ns * 0.028 + turn * 1.4, -0.086], [-ns * 0.043 + turn * 1.4, -0.094]], 0.55, 0.3, 0.3)

        # ---- mouth: a soft closed smile, a separate small lower-lip stroke
        my, lift, mx = L['mouthY'], 0.01 + smile * 0.022, turn * 1.2
        brush([[mx - 0.078, my + lift], [mx - 0.03, my - 0.004], [mx + 0.03, my - 0.004], [mx + 0.078, my + lift]], 0.95, 0.3, 0.3)
        if R() < 0.65:
            brush([[mx - 0.03, my - 0.042], [mx, my - 0.049], [mx + 0.03, my - 0.042]], 0.55, 0.35, 0.35)

        # ---- facial hair, freckles, earrings, age
        if beard:
            for j in range(16):
                t = j / 15
                s = -1 if t < 0.5 else 1
                u = abs(t - 0.5) * 2
                bx, by = s * u * cx * 0.86 + turn, -0.21 - (1 - u) * 0.16 - u * 0.05
                brush([[bx, by], [bx * 1.04, by - 0.04]], 0.5, 0.2, 0.8)
        if beard or moust:
            brush([[mx - 0.07, my + 0.026], [mx, my + 0.037], [mx + 0.07, my + 0.026]], 1.15, 0.3, 0.3)
        if freckles:
            for j in range(12):
                s = 1 if j % 2 else -1
                fx = s * (0.1 + R() * 0.08) + turn
                fy = -0.02 - R() * 0.06
                dot(fx, fy, 0.0045)
        if earring:
            oval(-cx - 0.018, -0.07, 0.012, 0.014, 0.5)
            oval(cx + 0.018, -0.07, 0.012, 0.014, 0.5)
        if age == 'elder':
            brush([[-0.09, 0.225], [0, 0.232], [0.09, 0.222]], 0.35, 0.3, 0.3)
            brush([[mx - 0.066, my + 0.065], [mx - 0.086, my + 0.012]], 0.38, 0.3, 0.5)
            brush([[mx + 0.066, my + 0.065], [mx + 0.086, my + 0.012]], 0.38, 0.3, 0.5)

        # ---- hair: flowing tapered strokes framing the face
        crown, hw = 0.43 + jit(0.01), cx + 0.035

        def flow(s, x0, y0, ln, sway, m=0.8, curl=0.0):           # one strand from the crown, down one side
            pts = [[x0, y0]]
            for q in range(1, 6):
                f = q / 5
                x = s * (abs(x0) + (hw + 0.035 - abs(x0)) * min(1.0, f * 2.2) + f * 0.035) + math.sin(f * 5.5 + sway) * 0.02 * (1 + curl)
                pts.append([x, y0 - (y0 - ln) * f])
            brush(pts, m, 0.15, 0.5)

        def crownArc(m=1.0):
            brush([[-hw, 0.16], [-hw * 0.95, 0.31], [-0.1, crown], [0.1, crown], [hw * 0.95, 0.31], [hw, 0.16]], m, 0.2, 0.2)

        def earC(s):
            brush([[s * (cx + 0.004), 0.07], [s * (cx + 0.034), 0.05], [s * (cx + 0.03), -0.015], [s * (cx + 0.005), -0.032]], 0.65, 0.2, 0.3)

        if hair in ('long', 'wavy'):
            sw = 1.6 if hair == 'wavy' else 0.3
            crownArc(0.9)
            brush([[0.03, crown - 0.01], [-0.06, 0.34], [-0.18, 0.27], [-hw + 0.02, 0.15]], 0.85, 0.2, 0.6)   # parting sweep
            for s in (-1, 1):
                for j in range(3):
                    ln = -0.3 - j * 0.05 - R() * 0.1
                    sway = R() * 6
                    flow(s, s * (0.06 + j * 0.07), crown - 0.02 - j * 0.03, ln, sway, 0.8 - j * 0.12, sw)
        elif hair == 'locs':
            crownArc(0.9)
            for s in (-1, 1):
                for j in range(4):
                    x0 = s * (hw - 0.02 + j * 0.02)
                    brush([[x0, 0.25 - j * 0.02], [x0 + s * 0.02, 0.05 - j * 0.02], [x0 + s * 0.015, -0.2 - j * 0.03]], 0.7, 0.1, 0.4)
        elif hair == 'pony':
            crownArc(0.95)
            brush([[-0.02, crown - 0.01], [-0.12, 0.31], [-hw + 0.02, 0.16]], 0.8, 0.2, 0.6)
            brush([[hw - 0.01, 0.33], [hw + 0.07, 0.31], [hw + 0.11, 0.12], [hw + 0.09, -0.12], [hw + 0.05, -0.25]], 1.0, 0.1, 0.6)
        elif hair in ('short', 'side'):
            brush([[-hw, 0.12], [-hw * 0.98, 0.3], [-0.05, crown], [hw * 0.98, 0.3], [hw, 0.12]], 1.0, 0.15, 0.15)
            if hair == 'side':
                brush([[-0.16, 0.39], [0.02, 0.35], [0.18, 0.3], [hw - 0.02, 0.2]], 0.8, 0.2, 0.6)
            else:
                brush([[-0.2, 0.33], [-0.05, 0.3], [0.12, 0.32]], 0.6, 0.3, 0.5)
            earC(-1)
            earC(1)
        elif hair == 'curly':
            for j in range(22):
                a = math.pi * (0.02 + 0.96 * j / 21)
                rr = 0.34 + R() * 0.05
                x, y = math.cos(a) * (hw + 0.07), 0.1 + math.sin(a) * rr
                r0 = 0.024 + R() * 0.012
                a0 = R() * 6
                pts = []
                for q in range(11):
                    b = a0 + q / 10 * math.pi * 1.5
                    pts.append([x + math.cos(b) * r0, y + math.sin(b) * r0])
                brush(pts, 0.6, 0.2, 0.3)
            brush([[-hw + 0.03, 0.2], [0, 0.3], [hw - 0.03, 0.2]], 0.55, 0.3, 0.3)
        elif hair == 'bun':
            crownArc(0.95)
            oval(0.0, crown + 0.035, 0.07, 0.048, 0.9)
            brush([[-0.18, 0.28], [-0.05, 0.33], [0.1, 0.32]], 0.5, 0.3, 0.5)
        elif hair == 'bald':
            brush([[-hw, 0.12], [-hw * 0.96, 0.3], [0, crown - 0.015], [hw * 0.96, 0.3], [hw, 0.12]], 1.0, 0.15, 0.15)
            earC(-1)
            earC(1)
        elif hair == 'braids':
            crownArc(0.9)
            brush([[0, crown - 0.01], [0, 0.3]], 0.5, 0.2, 0.2)
            for s in (-1, 1):                                       # a herringbone plait down each side
                xx = s * (hw + 0.03)
                brush([[xx - 0.03, 0.16], [xx - 0.032, -0.36]], 0.45, 0.1, 0.3)
                brush([[xx + 0.03, 0.16], [xx + 0.028, -0.36]], 0.45, 0.1, 0.3)
                for q in range(8):
                    yy = 0.14 - q * 0.062
                    brush([[xx - 0.028, yy + 0.022], [xx, yy - 0.012]], 0.55, 0.3, 0.3)
                    brush([[xx + 0.028, yy + 0.022], [xx, yy - 0.012]], 0.55, 0.3, 0.3)
                brush([[xx - 0.012, -0.37], [xx, -0.43], [xx + 0.012, -0.37]], 0.5, 0.2, 0.2)
        elif hair == 'scarf':
            brush([[-hw - 0.045, -0.08], [-hw - 0.05, 0.24], [0, crown + 0.03], [hw + 0.05, 0.24], [hw + 0.045, -0.08]], 1.1, 0.1, 0.1)
            brush([[-hw + 0.01, 0.2], [0, 0.305], [hw - 0.01, 0.2]], 0.75, 0.2, 0.2)
            brush([[-hw - 0.045, -0.08], [-0.2, -0.38], [0, -0.44], [0.2, -0.38], [hw + 0.045, -0.08]], 0.9, 0.1, 0.1)
            brush([[-0.12, 0.38], [0.02, 0.33], [0.16, 0.36]], 0.4, 0.3, 0.3)
        elif hair == 'bangs':
            crownArc(0.95)
            for j in range(6):
                x0 = -hw + 0.04 + j * (2 * hw - 0.08) / 5
                brush([[x0 + 0.02, 0.35 - abs(j - 2.5) * 0.02], [x0, 0.27], [x0 - 0.012, 0.22]], 0.6, 0.2, 0.7)
            for s in (-1, 1):
                brush([[s * hw, 0.25], [s * (hw + 0.03), 0.02], [s * (hw + 0.02), -0.18]], 0.8, 0.2, 0.6)

        line[oy:oy + S, ox:ox + S] = g.done()
        fill[oy:oy + S, ox:ox + S] = _fill_cell(S, cx)

    # halo: the line art blurred (canvas filter blur(round(S * 0.022) px): a Gaussian of that standard deviation)
    lim = Image.fromarray(np.clip(line + 0.5, 0, 255).astype(np.uint8), 'L')
    halo = np.asarray(lim.filter(ImageFilter.GaussianBlur(radius=round(S * 0.022))), dtype=np.float32)
    data = np.zeros((W, W, 4), dtype=np.uint8)
    data[..., 0] = np.clip(line + 0.5, 0, 255).astype(np.uint8)
    data[..., 1] = np.minimum(255.0, np.floor(halo * 1.6)).astype(np.uint8)
    data[..., 2] = np.clip(fill, 0, 255).astype(np.uint8)
    data[..., 3] = 255
    return np.ascontiguousarray(data[::-1])                    # bottom row first, as the JS packs it


