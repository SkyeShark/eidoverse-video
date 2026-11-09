"""Render a generated tower-karst terrain exactly as the references are rendered (reference/render_references.py's
render_probe: grey clay, make_sky daylight at 15:30, the same three views and lens), from make_views.py's fields.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain_new/karst/render_karst.py --name fenglin_s7 [--views top,aerial,eye] [--hero]

Writes out/karst/<name>_top_hillshade.png, _aerial_45deg.png, _eye_1p7m.png and _views.json; with --hero also
<name>_hero_eye_1p7m.png: the same eye, standing in a 2 km window at 2 m inside a 24 km surround.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.normpath(os.path.join(HERE, '..', 'reference'))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'karst'))
sys.path.insert(0, REF)
from render_references import render_probe  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--views', default='top,aerial,eye')
    ap.add_argument('--hero', action='store_true')
    a = ap.parse_args(argv)
    f = np.load(os.path.join(OUT, f'{a.name}_fields.npz'))
    with open(os.path.join(OUT, f'{a.name}_eye.json')) as fh:
        rec = json.load(fh)
    eye = {k: rec['eye'][k] for k in ('x', 'y', 'look_x', 'look_y', 'look_dz', 'lens_mm')}
    cache = tempfile.mkdtemp(prefix='karst_sky_')
    try:
        views = [v for v in a.views.split(',') if v]
        if views:
            render_probe(a.name, f['h_main'].astype(np.float64), 8.0, OUT, cache, views=views,
                         context=(f['h_ctx'].astype(np.float64), 32.0), eye=eye, aerial_azimuth=200.0)
        if a.hero and 'h_hero' in f.files:
            cx, cy = rec['hero']['centre']
            he = dict(eye, x=eye['x'] - cx, y=eye['y'] - cy, look_x=eye['look_x'] - cx, look_y=eye['look_y'] - cy)
            render_probe(a.name + '_hero', f['h_hero'].astype(np.float64), 2.0, OUT, cache, views=('eye',),
                         context=(f['h_hero_ctx'].astype(np.float64), 24.0), eye=he)
    finally:
        shutil.rmtree(cache, ignore_errors=True)
    print('[karst] rendered', a.name, flush=True)


if __name__ == '__main__':
    main()
