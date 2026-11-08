"""The city's canvas art and its light map, drawn on the canvas port (no Blender, no GPU):

    python blender/tests/sets_uf_city/test_canvas_art.py

  camp screens   the twelve screens' default canvases (draw_camp_screen) -> out/canvas_camp_screens.png
  tickers        the four ticker rings (draw_ticker): each run stretched to fill its canvas exactly, so it wraps
                 seamlessly (both edges fall in a gap) -> out/canvas_tickers.png
  plaza sun      draw_plaza_sun at t = 3.7 s against the material's decomposition of it (the rays and the slogans
                 drawn once and turned, the rings and the core drawn analytically), emulated here in numpy: they
                 must agree -> out/canvas_plaza_sun.png (left the canvas, right the decomposition)
  light map      the street light map of the whole city (lamp pools, shop spill, the piazza, the hole) and its blurred
                 levels -> out/canvas_light_map.png
Prints PASS / FAIL.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from eidoblend.sets.unknown_force import citykit as KIT  # noqa: E402
from eidoblend.sets.unknown_force import city as C  # noqa: E402
from eidoblend.sets.unknown_force import hole as H  # noqa: E402

OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[uf-city-canvas] %s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


# ---- the twelve camp screens
tiles = []
for i, camp in enumerate(H.CAMPS):
    c = KIT.make_canvas(1024, 576)
    H.draw_camp_screen(c['ctx'], 1024, 576, camp)
    px = c['canvas'].rgba8()
    fg = np.array(KIT.hex_rgb(camp['fg']))
    word = (np.abs(px[150:380, :, :3].astype(int) - fg).sum(-1) < 40).mean()
    check(f'camp screen {i} {camp["word"]!r}: the word is drawn', 0.03 < word < 0.6, f'{word:.3f} of the word band')
    tiles.append(Image.fromarray(px, 'RGBA').convert('RGB').resize((512, 288)))
sheet = Image.new('RGB', (512 * 4, 288 * 3))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 4) * 512, (i // 4) * 288))
sheet.save(OUT / 'canvas_camp_screens.png')

# ---- the four tickers
rows = []
for s, items in enumerate(H.TICKERS):
    c = KIT.make_canvas(2048, 96)
    H.draw_ticker(c['ctx'], 2048, 96, items)
    px = c['canvas'].rgba8()
    # the run starts with text at x = 0 and ends in its last gap: the right edge is dark, so the band wraps seamlessly
    edge = px[:, -3:, :3].max()
    lit = (px[..., :3].max(-1) > 80).mean()
    check(f'ticker {s}: seamless (the run ends in its gap), text drawn', edge < 60 and lit > 0.05,
          f'right edge max {edge}, lit {lit:.3f}')
    rows.append(px)
Image.fromarray(np.concatenate(rows, 0), 'RGBA').convert('RGB').save(OUT / 'canvas_tickers.png')

# ---- the plaza sun: the canvas against the material's decomposition (numpy emulation of the shader)
PX = 1024
T = 3.7
tq = math.floor(T * 10) / 10                      # the engine redrew at 10 fps
full = KIT.make_canvas(PX, PX)
C.draw_plaza_sun(full['ctx'], PX, PX, tq)
ref = full['canvas'].rgba8()[..., :3].astype(np.float64) / 255
rays = KIT.make_canvas(PX, PX)
rays['ctx'].fillStyle = '#05040a'
rays['ctx'].fillRect(0, 0, PX, PX)
C._plaza_rays(rays['ctx'], PX, PX, 0.0)
text = KIT.make_canvas(PX, PX)
C._plaza_text(text['ctx'], PX, PX, 0.0)
A = rays['canvas'].rgba8()[..., :3].astype(np.float64) / 255
B = text['canvas'].rgba8().astype(np.float64) / 255
# the material samples with uv (v up); in canvas rows: u = (x + .5) / W, v = 1 - (y + .5) / H
ys, xs = np.mgrid[0:PX, 0:PX]
u, v = (xs + 0.5) / PX, 1 - (ys + 0.5) / PX
du, dv = u - 0.5, v - 0.5


def sample(img, uu, vv):
    x = np.clip(uu * PX - 0.5, 0, PX - 1)
    y = np.clip((1 - vv) * PX - 0.5, 0, PX - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, PX - 1), np.minimum(y0 + 1, PX - 1)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) + img[y1, x0] * (1 - fx) * fy +
            img[y1, x1] * fx * fy)


def rot(a):
    c, s = math.cos(a), math.sin(a)
    return du * c - dv * s + 0.5, du * s + dv * c + 0.5


col = sample(A, *rot(tq * 0.12))
r = np.hypot(du, dv)
srgb = lambda h: np.array(KIT.hex_rgb(h)) / 255  # noqa: E731  (canvas space: compare before decoding)
for k in range(1, 6):
    rk = (0.16 * k + math.sin(tq * 0.7 + k) * 0.04) * 0.5
    t_ = np.clip((np.abs(r - rk) - (0.003 - 0.0006)) / 0.0012, 0, 1)
    mask = (1 - t_ * t_ * (3 - 2 * t_))[..., None]
    col = col * (1 - mask) + srgb('#05040a' if k % 2 else '#ffcf8a') * mask
t_ = np.clip((r - (0.05 - 0.0006)) / 0.0012, 0, 1)
mask = (1 - t_ * t_ * (3 - 2 * t_))[..., None]
col = col * (1 - mask) + srgb('#fffaf0') * mask
tb = sample(B, *rot(tq * -0.05))
col = col * (1 - tb[..., 3:4]) + tb[..., :3] * tb[..., 3:4]
diff = np.abs(col - ref).mean(-1)
check('plaza sun: decomposition = the canvas (mean)', diff.mean() < 0.012, f'mean |diff| {diff.mean():.4f}')
check('plaza sun: decomposition = the canvas (99th percentile)', np.percentile(diff, 99) < 0.2,
      f'{np.percentile(diff, 99):.3f}')
Image.fromarray(np.concatenate([ref, np.clip(col, 0, 1)], 1).__mul__(255).astype(np.uint8)).resize((1024, 512)).save(
    OUT / 'canvas_plaza_sun.png')

# ---- the street light map of the whole city
plan = C.plan_city(1909)
bctx = {'buf': {k: KIT.GeoBuf() for k in ('concrete', 'metal', 'frame', 'strip')}, 'signs': [], 'lights': []}
for lot in sorted(plan['lots'], key=lambda l: l['r0']):
    C.emit_building(lot, bctx)
lamps = C.plan_lamps()
lm = KIT.paint_light_map(C.light_draws(lamps, bctx, True), 2048)
s = 2048 / (2 * KIT.LM_R)


def at(x, z):
    return lm[int((z + KIT.LM_R) * s), int((x + KIT.LM_R) * s), :3].astype(int)


piazza = at(C.DIVE_C3[0], C.DIVE_C3[2])          # the light map's plan is in three's xz
check('light map: the piazza at the dive\'s crossing is the brightest street', piazza.min() >= 250, str(piazza.tolist()))
l0 = lamps[200]
lamp = at(l0['x'] + math.sin(l0['yaw']) * -2.4, l0['z'] + math.cos(l0['yaw']) * -2.4)
check('light map: a sodium pool under a lamp head', lamp[0] > lamp[2] + 40 and lamp[0] > 120, str(lamp.tolist()))
ring = at(0, 0)
check('light map: the quiet ring lights her floor', ring.min() > 120, str(ring.tolist()))
dark = at(800, -1300)
check('light map: dark between the streets', dark.max() < 60, str(dark.tolist()))
vis = Image.fromarray(lm[..., :3]).resize((1024, 1024), Image.BOX)
vis.save(OUT / 'canvas_light_map.png')
fails = [n for n, ok in results if not ok]
print(f'[uf-city-canvas] {len(results) - len(fails)}/{len(results)} passed' + (f'; FAILED: {fails}' if fails else ''))
sys.exit(1 if fails else 0)
