"""eidoblend.props.carbine.decals: the carbine's drawn surface data, at real size (plain Python: numpy and Pillow).

    python blender/eidoblend/props/carbine/decals.py --out work/carbine/decals      # or decals.draw(out_dir)

What is too fine or too flat to be mesh, drawn in the carbine's own millimetres; the bake lays each into UV space
through its rectangle in decals.json (layers.py), on the faces that look its way:
    grip_panel                   the pistol grip's chequered panel: a 16-bit height picture (white = the surface, dark
                                 = the cut between the diamonds, 0.4 mm deep), diamonds 1.7 mm across and 2.9 mm long
                                 the long way down the panel, a fine groove round it; grip_panel_mask: where it is
    rail_right / _left / _top / _bottom   the fore-end's numbered lands (one number on every second land, the figures'
                                 tops toward the muzzle)
    upper_top                    the receiver rail's numbers
    lower_left / lower_right     the selector's three words: SAFE ahead of it, SEMI above, AUTO behind
Function markings only: no maker's marks, no serial. A picture for a LEFT or BOTTOM face is drawn for the eye on that
side: its rectangle runs mm1 -> mm0, so the same mapping shows it unmirrored. The letters are the repo's Space Mono
Bold (OFL), sized by their cap height.
"""

from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', 'eidoverse', 'assets', 'fonts', 'SpaceMono-Bold.ttf'))


def draw(out_dir, font=FONT):
    """Draw every picture into out_dir and write decals.json; returns the spec dict."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    os.makedirs(out_dir, exist_ok=True)
    spec = {}

    def save16(name, a):
        Image.fromarray((np.clip(a, 0, 1) * 65535).astype(np.uint16)).save(os.path.join(out_dir, name + '.png'))

    # ------------------------------------------------------------------ the grip's chequered panel
    px = 0.04                                                  # mm a pixel
    x0, x1, z0, z1 = -14.0, 47.0, -139.0, -71.0
    W, H = int(round((x1 - x0) / px)), int(round((z1 - z0) / px))
    poly = [(-10.2, -129.3), (18.4, -77.7), (23.5, -75.6), (28.6, -75.0), (37.4, -76.2), (43.2, -81.6), (39.1, -93.2), (31.4, -106.8),
            (27.2, -116.5), (22.3, -126.2), (18.9, -135.0)]
    im = Image.new('L', (W, H), 0)
    ImageDraw.Draw(im).polygon([((x - x0) / px, (z1 - z) / px) for x, z in poly], fill=255)
    # its corners rounded (about 3 mm): blur, then cut at half
    soft = np.asarray(im.filter(ImageFilter.GaussianBlur(2.2 / px)), np.float32) / 255.0
    inside = (soft > 0.5).astype(np.float32)
    edge = np.asarray(Image.fromarray((inside * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.12 / px)), np.float32) / 255.0
    zz, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    X, Z = x0 + (xx + 0.5) * px, z1 - (zz + 0.5) * px
    lean = math.radians(28.0)                                  # the panel's long way: 28 degrees off upright, down and back
    a = X * -math.sin(lean) + Z * -math.cos(lean)
    b = X * math.cos(lean) + Z * -math.sin(lean)
    wd, ld = 1.7, 2.9                                          # a diamond across and along
    phi = math.atan2(wd, ld)
    w = wd * math.cos(phi)
    c1, c2 = (a * math.sin(phi) + b * math.cos(phi)) / w, (-a * math.sin(phi) + b * math.cos(phi)) / w

    def tri(v):
        return 1.0 - np.abs(2.0 * (v - np.floor(v)) - 1.0)
    pyr = np.minimum(np.minimum(tri(c1), tri(c2)) * 1.35, 1.0)  # moulded diamonds: their tops a little flat
    height = 1.0 - edge * (1.0 - pyr)
    ring = np.clip(1.0 - np.abs(soft - 0.5) / 0.035, 0, 1)      # a fine groove round the panel
    height = np.minimum(height, 1.0 - 0.45 * ring)
    save16('grip_panel', height)
    Image.fromarray((edge * 255).astype(np.uint8)).save(os.path.join(out_dir, 'grip_panel_mask.png'))
    spec['grip_panel'] = {'file': 'grip_panel.png', 'mask': 'grip_panel_mask.png', 'u': ['x', x0, x1], 'v': ['z', z0, z1], 'depth_mm': 0.4}

    # ------------------------------------------------------------------ lettering
    ref = ImageFont.truetype(font, 1000)
    bb = ref.getbbox('H')
    cap_ratio = (bb[3] - bb[1]) / 1000.0                       # the font's cap height in ems

    def label(text, cap_px):
        f = ImageFont.truetype(font, max(4, int(round(cap_px / cap_ratio))))
        wl = int(ImageDraw.Draw(Image.new('L', (4, 4))).textlength(text, font=f)) + 8
        im_ = Image.new('L', (wl, int(cap_px / cap_ratio * 1.4) + 8), 0)
        ImageDraw.Draw(im_).text((4, im_.height // 2), text, font=f, fill=255, anchor='lm')
        return im_.crop(im_.getbbox())

    def sheet(name, u, v, labels, px_=0.04):
        """labels: [(text, cap height mm, centre along u (its own mm), centre along v, turn degrees counter-clockwise)]"""
        (ua, u0, u1), (va, v0, v1) = u, v
        W_, H_ = int(round(abs(u1 - u0) / px_)), int(round(abs(v1 - v0) / px_))
        im_ = Image.new('L', (W_, H_), 0)
        for text, cap, cu, cv, turn in labels:
            g = label(text, cap / px_).rotate(turn, expand=True, resample=Image.BICUBIC)
            x = (cu - u0) / (u1 - u0) * W_
            y = (1.0 - (cv - v0) / (v1 - v0)) * H_
            im_.paste(g, (int(round(x - g.width / 2)), int(round(y - g.height / 2))), g)
        im_.save(os.path.join(out_dir, name + '.png'))
        spec[name] = {'file': name + '.png', 'u': [ua, u0, u1], 'v': [va, v0, v1], 'labels': [lb[0] for lb in labels]}

    # the fore-end's lands (front.py: slots from x = 228, every 10.0076 mm, 5.29 wide): land k's middle
    lands = [228.0 + 5.29 + 2.359 + k * 10.0076 for k in range(14)]
    nums = [(k, 14 + k) for k in range(0, 13, 2)]              # on every second land: 14, 16, .. 26
    # RIGHT (the eye at -y: x to the right, z up): tops toward the muzzle = turned a quarter clockwise
    sheet('rail_right', ('x', 225.0, 375.0), ('z', -9.1, 12.1), [(f'R{n}', 3.0, lands[k], 1.5, -90) for k, n in nums])
    # LEFT (the eye at +y: x runs to the LEFT): the rectangle given x1 -> x0, the tops (muzzle) turn counter-clockwise
    sheet('rail_left', ('x', 375.0, 225.0), ('z', -9.1, 12.1), [(f'L{n}', 3.0, lands[k], 1.5, 90) for k, n in nums])
    # TOP (the eye above: x to the right, y up the picture); BOTTOM (the eye below: y DOWN the picture): y1 -> y0
    sheet('rail_top', ('x', 225.0, 375.0), ('y', -10.6, 10.6), [(f'T{n}', 3.0, lands[k], 0.0, -90) for k, n in nums])
    sheet('rail_bottom', ('x', 225.0, 375.0), ('y', 10.6, -10.6), [(f'B{n}', 3.0, lands[k], 0.0, -90) for k, n in nums])
    # the receiver's own rail (high.py: slots from x = 22, lands' middles from 29.65)
    ul = [22.0 + 5.29 + 2.359 + k * 10.0076 for k in range(17)]
    sheet('upper_top', ('x', 18.0, 205.0), ('y', -10.6, 10.6), [(f'T{2 + k}', 3.0, ul[k], 0.0, -90) for k in range(0, 17, 2)])
    words = [('SAFE', 2.5, 81.5, -33.0, 0), ('SEMI', 2.5, 56.0, -23.6, 0), ('AUTO', 2.5, 33.5, -33.0, 0)]
    sheet('lower_right', ('x', 20.0, 100.0), ('z', -45.0, -15.0), words)
    sheet('lower_left', ('x', 100.0, 20.0), ('z', -45.0, -15.0), words)
    with open(os.path.join(out_dir, 'decals.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(spec, f, indent=1)
    return spec


if __name__ == '__main__':
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else os.path.join(os.getcwd(), 'decals')
    s = draw(out)
    print(f'[carbine decals] {len(s)} pictures -> {out}')
