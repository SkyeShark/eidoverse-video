"""A look at core/compose.py's uplift shapes before the fluvial package erodes them: each shape's uplift field (top
row, as a hillshade of 3000 m x the field) and its rough 600 m start surface (bottom row), on a 20 km window at
78 m cells. System Python (cv2 for the labels):

    python blender/tests/terrain/core/sheet_shapes.py      -> out/core/sheet_uplift_shapes.png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plain_import  # noqa: E402

OUT = plain_import.install()

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.terrain.core import compose as C, grid as G, io as IO  # noqa: E402

SHAPES = [('dome', {'kind': 'dome', 'radius_m': 7000}),
          ('ridge + 6 spurs', {'kind': 'ridge', 'azimuth_deg': 30, 'length_m': 14000, 'width_m': 6000, 'spurs': 6}),
          ('plateau', {'kind': 'plateau', 'radius_m': 6500, 'edge_m': 2000}),
          ('massif, 5 peaks', {'kind': 'massif', 'radius_m': 7500, 'peaks': 5})]


def tile(h, cell, label, z=1.0):
    img = IO.to_u8(IO.hillshade(h, cell, z=z)[::-1])
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.putText(img, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 40, 220), 2, cv2.LINE_AA)
    return img


def main():
    n, cell = 256, 78.125
    x, y = G.cell_centres(-10000, -10000, cell, n)
    top, bottom = [], []
    for label, sp in SHAPES:
        u = C.uplift(sp, x, y, seed=3)
        h0 = C.start_surface(sp, x, y, seed=3, height_m=600.0)
        top.append(tile(3000.0 * u, cell, f'{label}: uplift x 3000 m'))
        bottom.append(tile(h0, cell, f'start 600 m ({h0.max():.0f} m peak)', z=3.0))
    sheet = np.vstack([np.hstack(top), np.hstack(bottom)])
    path = os.path.join(OUT, 'sheet_uplift_shapes.png')
    cv2.imwrite(path, sheet)
    print(path)


main()
