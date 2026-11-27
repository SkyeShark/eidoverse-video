#!/usr/bin/env python3
"""blender/tools/grid_crop.py: a crop of a reference photograph, enlarged, under a MILLIMETRE GRID in the part's own
coordinates, so an outline is traced by reading numbers instead of by eye (plain Python with Pillow).

    python blender/tools/grid_crop.py PHOTO OUT.png --scale MM_PER_PX --origin X,Y --box X0,Y0,X1,Y1 [--zoom 4] [--step 5]

--scale     millimetres a photo pixel (from a known length in the photo, square on)
--origin    the photo pixel that is the part's (0, 0): x is measured toward the photo's right from it, z UP from it
--box       the crop, in photo pixels
--zoom      the enlargement (each photo pixel becomes zoom x zoom)
--step      the grid's spacing in mm; every fifth line is heavier and numbered (x along the top, z down the left)

The tables a hard-surface builder reads (eidoblend.props.hardsurface.masses: prism_side outlines in (x, z) mm) are
read off such crops. The photograph is a reference only: keep it, and the crops, out of the repository.
"""

import argparse
import os

from PIL import Image, ImageDraw, ImageFont

FONT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'eidoverse', 'assets', 'fonts', 'SpaceMono-Regular.ttf'))


def grid_crop(src, out, mm, origin, box, zoom=4, step=5.0):
    """Write the gridded crop; returns its size."""
    ox, oy = origin
    x0, y0, x1, y1 = box
    im = Image.open(src).convert('RGB').crop((x0, y0, x1, y1))
    im = im.resize((im.width * zoom, im.height * zoom), Image.LANCZOS)
    d = ImageDraw.Draw(im, 'RGBA')
    try:
        f = ImageFont.truetype(FONT, 15)
    except OSError:
        f = ImageFont.load_default()
    k = int((x0 - ox) * mm // step) - 1
    while True:
        k += 1
        px = (ox + k * step / mm - x0) * zoom
        if px > im.width:
            break
        if px < 0:
            continue
        major = k % 5 == 0
        d.line([(px, 0), (px, im.height)], fill=(0, 200, 255, 150 if major else 60), width=1)
        if major:
            d.text((px + 2, 2), f'{k * step:g}', font=f, fill=(0, 255, 255, 255))
    k = int((oy - y1) * mm // step) - 1
    while True:
        k += 1
        py = (oy - k * step / mm - y0) * zoom
        if py < 0:
            break
        if py > im.height:
            continue
        major = k % 5 == 0
        d.line([(0, py), (im.width, py)], fill=(255, 220, 0, 150 if major else 60), width=1)
        if major:
            d.text((2, py + 2), f'z {k * step:g}', font=f, fill=(255, 255, 0, 255))
    im.save(out)
    return im.size


def main(argv=None):
    ap = argparse.ArgumentParser(description='a photo crop under a millimetre grid (see the module doc)')
    ap.add_argument('photo')
    ap.add_argument('out')
    ap.add_argument('--scale', type=float, required=True, help='mm a photo pixel')
    ap.add_argument('--origin', required=True, help='X,Y: the photo pixel at the part\'s (0, 0)')
    ap.add_argument('--box', required=True, help='X0,Y0,X1,Y1: the crop in photo pixels')
    ap.add_argument('--zoom', type=int, default=4)
    ap.add_argument('--step', type=float, default=5.0)
    a = ap.parse_args(argv)
    size = grid_crop(a.photo, a.out, a.scale, tuple(float(v) for v in a.origin.split(',')),
                     tuple(int(v) for v in a.box.split(',')), a.zoom, a.step)
    print(a.out, size)


if __name__ == '__main__':
    main()
