"""eidoblend.props.helicopter.decals: the helicopter's drawn pictures (plain Python: Pillow).

    python blender/eidoblend/props/helicopter/decals.py --out work/props/helicopter/decals      # or decals.draw(out_dir)

What a riveted airframe's skin carries that no vertex can, drawn in the aircraft's own millimetres SIDE ON (x aft to the
right, z up), 2.5 mm a pixel over the rectangle x -4700 .. 9500, z -500 .. 3400; look.py lays them through the hull from
each side:
    skin_side.png    R rivet heads: rows along every frame (0.5 m apart) and along the stringers (which converge down the
                       boom as the real ones do), along the cowlings' seams and the fin's ribs
                     G seams: the production joints, the cockpit door's shut line, access panels, cowling doors
                     B flush fasteners round the panels, the cowling doors' latches
    marks_left.png / marks_right.png   the stencils, black, as they read from each side (the right one drawn mirrored
                     so that it reads true there). Function markings only: no service title, no serial, no unit's mark.
The stencils are the repo's Archivo Black (OFL), sized by their cap height.
"""

from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', 'eidoverse', 'assets', 'fonts', 'ArchivoBlack-Regular.ttf'))
X0, X1, Z0, Z1, S = -4700.0, 9500.0, -500.0, 3400.0, 0.4


def draw(out_dir, font=FONT):
    """Draw skin_side.png, marks_left.png, marks_right.png and decals.json into out_dir; returns the spec."""
    from PIL import Image, ImageDraw, ImageFont
    if __package__:
        from . import datum as D
    else:                                                      # (run as a file)
        sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
        from eidoblend.props.helicopter import datum as D
    os.makedirs(out_dir, exist_ok=True)
    W, H = int((X1 - X0) * S), int((Z1 - Z0) * S)

    def P(x, z):
        return ((x - X0) * S, (Z1 - z) * S)

    def keel(x):
        return D.HULL.ctrl(x)[0][0][1]

    def crown(x):
        return D.HULL.ctrl(x)[0][6][1]

    riv, seam, fast = Image.new('L', (W, H), 0), Image.new('L', (W, H), 0), Image.new('L', (W, H), 0)
    dr, ds, df = ImageDraw.Draw(riv), ImageDraw.Draw(seam), ImageDraw.Draw(fast)

    def rivets(pts, pitch=25.0, r=1.5, d=dr):
        """heads every `pitch` mm along a polyline of (x, z)"""
        run, nxt = 0.0, pitch * 0.5
        for (xa, za), (xb, zb) in zip(pts, pts[1:]):
            seg = math.hypot(xb - xa, zb - za)
            while seg > 0 and run + seg >= nxt:
                f = (nxt - run) / seg
                px, py = P(xa + (xb - xa) * f, za + (zb - za) * f)
                d.ellipse([px - r, py - r, px + r, py + r], fill=255)
                nxt += pitch
            run += seg

    def line(pts, w=2, d=ds):
        d.line([P(x, z) for x, z in pts], fill=255, width=w, joint='curve')

    def rounded(x0, z0, x1, z1, r):
        out = []
        for cx, cz, a0 in ((x1 - r, z1 - r, 0), (x0 + r, z1 - r, 90), (x0 + r, z0 + r, 180), (x1 - r, z0 + r, 270)):
            out += [(cx + r * math.cos(math.radians(a0 + 90 * k / 6)), cz + r * math.sin(math.radians(a0 + 90 * k / 6))) for k in range(7)]
        return out + out[:1]

    def panel(x0, z0, x1, z1, r=40.0, pitch=60.0):
        line(rounded(x0, z0, x1, z1, r), 2)
        rivets(rounded(x0 + 14.0, z0 + 14.0, x1 - 14.0, z1 - 14.0, max(6.0, r - 14.0)), pitch, 1.6, df)

    # ---------------------------------------------------------------- the hull: frames, stringers, joints
    x = -3990.0
    k = 0
    while x < 8660.0:
        zk, zc = keel(x) + 30.0, crown(x) - 30.0
        for dx in (-11.0, 11.0):
            rivets([(x + dx, zk), (x + dx, zc)])
        if k % 3 == 0:
            line([(x, zk), (x, zc)], 1)
        x += 508.0
        k += 1
    xs = [-2400.0 + 100.0 * i for i in range(111)]               # the cabin and the boom: stringers at shares of the depth
    for f in (0.09, 0.24, 0.40, 0.56, 0.72, 0.88, 0.965):
        rivets([(x, keel(x) + f * (crown(x) - keel(x))) for x in xs])
    xs = [-4380.0 + 60.0 * i for i in range(31)]                 # the nose, below its windows
    for f in (0.14, 0.42):
        rivets([(x, keel(x) + f * (crown(x) - keel(x))) for x in xs])
    for xj in (-2585.0, 3650.0, 8120.0):                         # the production joints: a seam between two rows
        line([(xj, keel(xj) + 10.0), (xj, crown(xj) - 10.0)], 2)
        for dx in (-22.0, 22.0):
            rivets([(xj + dx, keel(xj) + 20.0), (xj + dx, crown(xj) - 20.0)], 20.0)
    line(D.COCKPIT_DOOR + D.COCKPIT_DOOR[:1], 2)                 # the cockpit door's shut line
    line([(-4470.0, 210.0), (-4300.0, 418.0), (-3990.0, 560.0), (-3870.0, 585.0)], 2)      # the avionics door on the nose
    line([(-4470.0, 210.0), (-4250.0, 150.0), (-4020.0, 120.0)], 2)
    for args in ((3760.0, 300.0, 4140.0, 700.0), (5260.0, 430.0, 5610.0, 770.0), (6900.0, 400.0, 7200.0, 650.0), (3340.0, 1090.0, 3700.0, 1320.0),
                 (1700.0, 140.0, 2200.0, 520.0), (-2500.0, -60.0, -2000.0, 260.0), (-1000.0, 60.0, -840.0, 420.0)):
        panel(*args)
    for cx, cz in ((2540.0, 1190.0), (2940.0, 1190.0)):           # the two filler caps
        line([(cx + 72.0 * math.cos(2 * math.pi * q / 40), cz + 72.0 * math.sin(2 * math.pi * q / 40)) for q in range(41)], 2)
        rivets([(cx + 58.0 * math.cos(2 * math.pi * q / 40), cz + 58.0 * math.sin(2 * math.pi * q / 40)) for q in range(41)], 46.0, 1.6, df)
    # ---------------------------------------------------------------- the cowlings (z above the roof), the exhausts, the fin
    for xj in (-150.0, 560.0, 1300.0, 1650.0):
        line([(xj, 1560.0), (xj, 2170.0)], 2)
        rivets([(xj + 16.0, 1570.0), (xj + 16.0, 2160.0)], 40.0, 1.6, df)
    line([(-430.0, 1870.0), (1650.0, 1870.0)], 2)
    for xl in (-20.0, 240.0, 760.0, 1060.0, 1480.0):              # the cowling doors' latches
        px, py = P(xl, 1870.0)
        df.rectangle([px - 14, py - 5, px + 14, py + 5], fill=255)
    for z in (1620.0, 2120.0):
        rivets([(-430.0, z), (1650.0, z)], 50.0, 1.6, df)
    for xj in (1950.0, 2300.0):
        rivets([(xj, 1600.0), (xj, 2120.0)], 30.0)
    for z in [1100.0 + 240.0 * i for i in range(8)]:              # the fin's ribs
        rivets([(8150.0 + (z - 1000.0) * 0.794 + 40.0, z), (9640.0 + (z - 1020.0) * 0.364 - 30.0 if z < 2080.0 else 10170.0 + (z - 2100.0) * 0.62 - 30.0, z)], 28.0)
    rivets([(8150.0 + (z - 1000.0) * 0.794 + 150.0, z) for z in (1000.0, 2950.0)], 28.0)
    Image.merge('RGB', (riv, seam, fast)).save(os.path.join(out_dir, 'skin_side.png'))

    # ---------------------------------------------------------------- the stencils
    bb = ImageFont.truetype(font, 1000).getbbox('H')
    cap_ratio = (bb[3] - bb[1]) / 1000.0

    def font_at(mm):
        return ImageFont.truetype(font, max(8, int(mm * S / cap_ratio)))

    def marks(mirror):
        im = Image.new('L', (W, H), 0)
        d = ImageDraw.Draw(im)

        def text(x, z, s, mm=46.0, anchor='lm'):
            px, py = P(x, z)
            f = font_at(mm)
            if not mirror:
                d.text((px, py), s, font=f, fill=255, anchor=anchor)
                return
            # this side is seen with the nose to the RIGHT: draw the word true on a tile, then flip the tile, so that the
            # whole picture, laid mirrored-in-x, shows it true
            bb_ = d.textbbox((0, 0), s, font=f)
            tile = Image.new('L', (bb_[2] - bb_[0] + 4, bb_[3] - bb_[1] + 4), 0)
            ImageDraw.Draw(tile).text((2 - bb_[0], 2 - bb_[1]), s, font=f, fill=255)
            tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
            ox = px - tile.width if anchor[0] == 'l' else px if anchor[0] == 'r' else px - tile.width // 2
            im.paste(tile, (int(ox), int(py - tile.height / 2)), tile)

        def arrow(xa, za, xb, zb, w=5):
            d.line([P(xa, za), P(xb, zb)], fill=255, width=w)
            a = math.atan2(zb - za, xb - xa)
            for da in (2.6, -2.6):
                d.line([P(xb, zb), P(xb + 70.0 * math.cos(a + da), zb + 70.0 * math.sin(a + da))], fill=255, width=w)
        text(8230.0, 760.0, 'DANGER', 62.0)                       # at the tail rotor: an arrow aft
        text(8230.0, 668.0, 'KEEP AWAY', 44.0)
        arrow(8250.0, 600.0, 8700.0, 600.0)
        for xs_, zs_ in ((3120.0, 290.0), (3210.0, 720.0), (3300.0, 1150.0)):   # over each kick step
            text(xs_ - 60.0, zs_, 'STEP', 34.0)
        text(-2520.0, 480.0, 'RESCUE', 46.0)                       # the cockpit door's outside release, an arrow to its handle
        arrow(-2540.0, 500.0, -2600.0, 500.0, 4)
        text(1040.0, 1080.0, 'RESCUE', 46.0)                       # the cabin door's handle
        text(1040.0, 1010.0, 'PULL AFT TO OPEN', 26.0)
        text(-3300.0, 20.0, 'JACK POINT', 30.0)
        text(2700.0, -30.0, 'JACK POINT', 30.0)
        text(2440.0, 1300.0, 'JP-8', 38.0)
        text(2840.0, 1300.0, 'JP-8', 38.0)
        text(3340.0, 1360.0, 'EXHAUST', 30.0)
        text(-2100.0, 330.0, 'NO STEP', 34.0)
        text(8900.0, 1080.0, 'NO HANDHOLD', 30.0)
        for i, s in enumerate(('SERVICING DATA: SEE OPERATORS MANUAL', 'TIE DOWN  /  HOIST  /  JACK AS MARKED', 'GROUND HERE BEFORE FUELLING')):
            text(-2540.0, 150.0 - 34.0 * i, s, 16.0)
        return im

    marks(False).save(os.path.join(out_dir, 'marks_left.png'))
    marks(True).save(os.path.join(out_dir, 'marks_right.png'))
    spec = {'rect': {'x': [X0, X1], 'z': [Z0, Z1]}, 'mm_per_px': 1.0 / S, 'size': [W, H]}
    with open(os.path.join(out_dir, 'decals.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(spec, f, indent=1)
    return spec


if __name__ == '__main__':
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else os.path.join(os.getcwd(), 'decals')
    draw(out)
    print(f'[helicopter decals] -> {out}')
