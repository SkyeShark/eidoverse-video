"""canvas_parity.py: every canvas the race and the bin draw, the Blender port's (eidoblend/sets/unknown_force: race.py,
bin.py, bin_pages.py on Pillow + numpy) against the WebGPU edition's own (napi canvas, dumped as PNGs by
race_parity_dump.mjs, bin_parity_dump.mjs and atlas_dump.mjs into out/parity/).

    cd <worktree> && deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_race_bin/atlas_dump.mjs 0.5
    python blender/tests/sets_uf_race_bin/canvas_parity.py

Two rasterizers and two font engines never agree pixel for pixel, and the pages' body text is laid out word by word
from a seeded stream, so a word that fits on one engine's line and not on the other's changes the words after it.
What must agree is the drawing: the layout, the shapes, the type sizes, the colours. So each canvas is compared
premultiplied, after a box filter of 8 px (the scale a sheet is seen at), by its mean absolute difference, and written
side by side (WebGPU left, Blender right) into out/parity/cmp_<name>.png to look at.

Runs in plain Python (no Blender). Prints PASS / FAIL per canvas; exit 1 on any FAIL.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sets.unknown_force import bin as B  # noqa: E402
from eidoblend.sets.unknown_force import bin_pages as PAGES  # noqa: E402
from eidoblend.sets.unknown_force import race as R  # noqa: E402

PAR = os.path.join(HERE, 'out', 'parity')
fails = []


def check(name, ok, info=''):
    print(('PASS' if ok else 'FAIL'), name, info, flush=True)
    if not ok:
        fails.append(name)


def load(name):
    return np.asarray(Image.open(os.path.join(PAR, name)).convert('RGBA'), np.float32) / 255.0


def premul(a):
    return np.concatenate([a[..., :3] * a[..., 3:4], a[..., 3:4]], -1)


def box(a, k):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    return a[:h, :w].reshape(h // k, k, w // k, k, -1).mean((1, 3))


def compare(name, js, mine, tol, k=8):
    if js.shape != mine.shape:
        check(f'{name}: size', False, f'{mine.shape} vs {js.shape}')
        return
    a, b = premul(js), premul(mine)
    mad = float(np.abs(box(a, k) - box(b, k)).mean())
    full = float(np.abs(a - b).mean())
    side = np.concatenate([js, np.ones((js.shape[0], 8, 4), np.float32), mine], 1)
    im = Image.fromarray((np.clip(side, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA')
    bg = Image.new('RGBA', im.size, (90, 90, 96, 255))
    bg.alpha_composite(im)
    s = min(1.0, 2000 / bg.size[0])
    bg.convert('RGB').resize((int(bg.size[0] * s), int(bg.size[1] * s)), Image.LANCZOS).save(os.path.join(PAR, f'cmp_{name}.png'))
    check(f'{name} {js.shape[1]}x{js.shape[0]}', mad < tol, f'mean abs diff {mad:.4f} at {k} px (per pixel {full:.4f}; tolerance {tol})')


race = R.Race.__new__(R.Race)                 # the canvas methods are pure: no scene needed
compare('race_billboard_a', load('race_billboard_a.png'), race.billboard_canvas('$100,000,000'), 0.02)
compare('race_billboard_b', load('race_billboard_b.png'), race.billboard_canvas('$20,000,000'), 0.02)
compare('race_march', load('race_march.png'), R.march_canvas(), 0.02)
compare('race_radiator_7', load('race_canvas_256x256_0.png'), R.radiator_number_canvas(), 0.03)
compare('race_manifesto', load('race_canvas_768x1086_1.png'), race.manifesto_canvas(), 0.03)
compare('bin_stickers', load('bin_canvas_2048x1024_0.png'), B.draw_stickers(), 0.03)
compare('bin_cut_shapes', load('bin_canvas_2048x1024_2.png'), B.draw_cut_shapes(), 0.02)
at = os.path.join(PAR, 'bin_atlas_341x512.png')
if os.path.isfile(at):
    mine = np.asarray(PAGES.draw_page_atlas(cw=341, ch=512), np.float32) / 255.0
    compare('bin_page_atlas', load('bin_atlas_341x512.png'), mine, 0.03)
else:
    check('bin_page_atlas (run atlas_dump.mjs first)', False)
print('canvas_parity:', 'ALL PASS' if not fails else f'{len(fails)} FAIL: {fails}')
sys.exit(1 if fails else 0)
