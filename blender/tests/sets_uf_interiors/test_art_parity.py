"""test_art_parity.py: the interiors' canvas art, Blender edition against the WebGPU edition.

Runs in system Python (numpy + Pillow; no bpy needed) or inside Blender. It draws every board, the ENGINE sheet, the
WARNING placard, the rating plate, the dial and a sheet of the marker primitives with the Python port, and compares
each with the ORIGINAL JS modules' output (art_reference.mjs, run through Deno + @napi-rs/canvas, cached-only):

  numbers   the mulberry32 streams (bit for bit), build_mips checksums, the shared noise texture (byte for byte),
            pcg_hash against the WGSL u32 arithmetic of three's TSL hash, and the text layout: runs in every face
            measured by Skia (text_measure_reference.mjs) against Fonts.layout
  pixels    mean |RGB difference| over the picture, and the IoU of the INK masks (dark or saturated pixels) after a
            1.5 px blur, which forgives anti-aliasing and font hinting but not a misplaced stroke or word; small type
            (FreeType's hinted strokes against Skia's) may pass on its layout instead: the ink's row and column
            profiles aligned at zero shift and correlated r >= 0.98
  inline    the canvases quiet_room.js and showroom.js draw inside build() (the essay, the stencils, the platter ...),
            captured from the original builds (inline_art_reference.mjs) and compared the same way

    cd blender/tests/sets_uf_interiors && python test_art_parity.py [--only center,engine_sheet]

Outputs (git-ignored): out/ref/*.png (the JS references), out/art/*.png (the port), out/art/sbs_*.jpg (side by
side, JS left / Python right) and out/art/diff_*.png.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))                     # <repo>/blender

from eidoblend.sets.unknown_force import interiors_lib as L          # noqa: E402
from eidoblend.sets.unknown_force import quiet_room_art as QA        # noqa: E402
from eidoblend.sets.unknown_force import showroom_art as SA          # noqa: E402

OUT = HERE / 'out'
REF, ART = OUT / 'ref', OUT / 'art'
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def make_refs():
    if (REF / 'numbers.json').is_file() and (REF / 'board_center.png').is_file():
        return
    deno = 'deno'
    cmd = [deno, 'run', '--no-config', '--no-lock', '--node-modules-dir=none', '--cached-only', '-A',
           str(HERE / 'art_reference.mjs'), str(REF)]
    print('[art] drawing the JS references:', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(HERE))


def pieces():
    out = {}
    for name, b in QA.BOARDS.items():
        W, H = QA.board_size(name)
        out[f'board_{name}'] = (W, H, lambda ctx, W, H, b=b: b['draw'](ctx, W, H, L.rng(b['seed'])))
    out['engine_sheet'] = (SA.SCREEN['W'], SA.SCREEN['H'], SA.draw_engine_sheet)
    out['warning'] = (920, 1240, SA.draw_warning)
    out['rating_plate'] = (512, 180, SA.draw_rating_plate)
    out['dial'] = (256, 256, SA.draw_dial)

    def prim(ctx, W, H):
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, 1200, 700)
        r = L.rng(7)
        L.marker(ctx, 'P(DOOM | SHIP) = 0.37', 40, 110, size=90, r=r)
        L.marker(ctx, 'centred, rotated', 600, 230, size=60, r=r, align='center', rot=-0.08, color='#15171b')
        L.mline(ctx, [[40, 300], [400, 330], [700, 280], [1150, 320]], w=10, r=r)
        L.mline(ctx, [[40, 380], [1150, 380]], w=6, r=r, dashed=[28, 22], color='#a50d18')
        L.marrow(ctx, 60, 600, 400, 460, w=7, r=r, head=30, color='#15171b')
        L.mring(ctx, 800, 560, 220, 90, w=8, r=r)
    out['primitives'] = (1200, 700, prim)
    return out


def ink(img):
    a = np.asarray(img.convert('RGB'), np.float32)
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32) / 255
    sat = (a.max(2) - a.min(2)) / 255
    m = ((lum < 0.55) | (sat > 0.25)).astype(np.uint8) * 255
    return np.asarray(Image.fromarray(m).filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255 > 0.35


REF_INLINE = OUT / 'ref_inline'
COMPARED_ELSEWHERE = {'engine_sheet', 'warning', 'dial', 'rating_plate'}      # the art modules' pieces (above)


def make_inline_refs():
    """the canvases quiet_room.js / showroom.js draw inside build(), captured from the original builds
    (inline_art_reference.mjs: the real three r184 without a renderer, its DataTexture recording each canvas)."""
    if (REF_INLINE / 'inline_qr_1024x1448.png').is_file() and (REF_INLINE / 'inline_sr_2048x2048.png').is_file():
        return True
    cmd = ['deno', 'run', '--no-config', '--no-lock', '--cached-only', '--import-map=inline_import_map.json', '-A',
           'inline_art_reference.mjs', str(REF_INLINE)]
    print('[art] capturing the inline canvases from the JS builds:', ' '.join(cmd), flush=True)
    try:
        subprocess.run(cmd, check=True, cwd=str(HERE))
    except (OSError, subprocess.CalledProcessError) as e:
        print(f'SKIP the inline canvases: the JS builds did not run ({e})', flush=True)
        return False
    return True


def compare_inline(only=None):
    """every canvas the two sets draw in build() (not the boards, not the art modules' pieces), drawn by the port
    (quiet_room.draw_canvas / showroom.draw_canvas, fresh) against the engine's own, matched by size."""
    from eidoblend.sets.unknown_force import quiet_room as QR, showroom as SR
    if not make_inline_refs():
        return
    for tag, mod in (('qr', QR), ('sr', SR)):
        for key, (W, H, _paint) in mod.CANVASES.items():
            if key.startswith('board_') or key in COMPARED_ELSEWHERE:
                continue
            name = f'inline_{tag}_{key}'
            if only and name not in only and key not in only:
                continue
            ref = REF_INLINE / f'inline_{tag}_{W}x{H}.png'
            if not ref.is_file():
                check(f'{name}: the engine drew a {W} x {H} canvas', False, 'no capture of that size')
                continue
            t = time.perf_counter()
            cv = mod.draw_canvas(key)
            dt = time.perf_counter() - t
            cv.save_png(ART / f'{name}.png')
            compare(name, dt, ref_path=ref)


def compare(name, timing, ref_path=None):
    ref = Image.open(ref_path or REF / f'{name}.png').convert('RGBA')
    py = Image.open(ART / f'{name}.png').convert('RGBA')
    if ref.size != py.size:
        check(f'{name}: size', False, f'{py.size} vs {ref.size}')
        return
    # a light mask on clear (the slogan: white letters the shader tints brass) is judged on black, all else on white
    ra = np.asarray(ref, np.float32)
    opaque = ra[..., 3] > 127
    light = bool(opaque.any()) and float(ra[opaque][:, :3].mean()) > 200
    bg = Image.new('RGBA', ref.size, (0, 0, 0, 255) if light else (255, 255, 255, 255))
    rr = Image.alpha_composite(bg, ref).convert('RGB')
    pp = Image.alpha_composite(bg, py).convert('RGB')
    a, b = np.asarray(rr, np.float32), np.asarray(pp, np.float32)
    mad = float(np.abs(a - b).mean())
    ia, ib = ink(rr), ink(pp)
    inter, union = float((ia & ib).sum()), float((ia | ib).sum())
    iou = inter / union if union else 1.0
    w = 1400
    h = int(ref.height * (w / 2) / ref.width)
    sbs = Image.new('RGB', (w, h), 'white')
    sbs.paste(rr.resize((w // 2, h), Image.LANCZOS), (0, 0))
    sbs.paste(pp.resize((w // 2, h), Image.LANCZOS), (w // 2, 0))
    sbs.save(ART / f'sbs_{name}.jpg', quality=90)
    d = np.clip(np.abs(a - b).max(2) * 3, 0, 255).astype(np.uint8)
    Image.fromarray(d).save(ART / f'diff_{name}.png')
    # ink centroid and amount: small type (the 256 px dial) loses IoU to a sub-pixel hinting shift that these keep
    la, lb = 255 - a.mean(2), 255 - b.mean(2)
    ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    if la.sum() > 0 and lb.sum() > 0:
        dc = float(np.hypot((la * ys).sum() / la.sum() - (lb * ys).sum() / lb.sum(),
                            (la * xs).sum() / la.sum() - (lb * xs).sum() / lb.sum()))
        amount = float(lb.sum() / la.sum())
    else:
        dc, amount = 0.0, 1.0                              # nothing dark on either (light lettering on clear)
    # layout: small type rasterised by FreeType (hinted) against Skia loses ink IoU to stroke weight alone; the
    # ink's row and column profiles still say whether every line and word sits where the engine put it
    lay = []
    for ax in (1, 0):
        pa, pb = la.sum(ax), lb.sum(ax)
        shift = max(range(-4, 5), key=lambda s: float((np.roll(pb, s) * pa).sum()))
        corr = float(np.corrcoef(pa, pb)[0, 1]) if pa.std() > 0 and pb.std() > 0 else 1.0
        lay.append((shift, corr))
    layout_ok = all(s == 0 and c >= 0.98 for s, c in lay)
    ok = mad <= 6.0 and (iou >= 0.85 or (dc <= 0.5 and abs(amount - 1) <= 0.03) or layout_ok)
    check(f'{name}: ink IoU {iou:.3f} (>= 0.85, or centroid {dc:.2f} px <= 0.5 with ink x{amount:.3f}, or the '
          f'layout: rows {lay[0][0]:+d} px r {lay[0][1]:.3f}, columns {lay[1][0]:+d} px r {lay[1][1]:.3f}), '
          f'mean |dRGB| {mad:.2f} <= 6', ok, f'{timing:.2f} s to draw')


# three's TSL hash (src/nodes/math/Hash.js) as the WGSL it compiles to runs it: u32(seed), wrapping u32 products,
# f32(result) / 2^32. Math.imul and >>> are JS's u32 arithmetic, independent of numpy's uint64 masking.
PCG_JS = r"""
const seeds = JSON.parse(Deno.args[0]);
const h = (s) => {
    const st = (Math.imul(s >>> 0, 747796405) + 2891336453) >>> 0;
    const w = Math.imul(((st >>> ((st >>> 28) + 4)) ^ st) >>> 0, 277803737) >>> 0;
    return Math.fround(((w >>> 22) ^ w) >>> 0) / 4294967296;
};
console.log(JSON.stringify(seeds.map(h)));
"""


def check_pcg():
    """pcg_hash (the exact per-instance hash: the quiet room's towers and aviation lights) against the WGSL
    arithmetic, over the seeds the sets use (instance ids + 5 / 17 / 91 / 233) and a spread of large ones."""
    seeds = [float(i + o) for o in (5, 17, 91, 233) for i in range(0, 360, 7)]
    seeds += [17.7, 0.0, 1.0, 1234567.0, 4294967040.0, 1073741824.5, 2891336453.0]
    try:
        out = subprocess.run(['deno', 'eval', '--quiet', PCG_JS, json.dumps(seeds)], capture_output=True, text=True,
                             check=True, cwd=str(HERE)).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        print(f'SKIP pcg_hash vs WGSL u32 arithmetic: deno unavailable ({e})', flush=True)
        return
    want = np.array(json.loads(out))
    got = L.pcg_hash(np.array(seeds))
    check('pcg_hash: three\'s TSL hash bit for bit (u32 PCG, f32 result)', np.array_equal(got, want),
          f'{len(seeds)} seeds, max |d| {float(np.abs(got - want).max()):.3g}')
    sc = [float(L.pcg_hash(s)) for s in seeds[:5]]
    check('pcg_hash: scalars as arrays', sc == list(got[:5]))


# runs of text in every face the interiors use, at their sizes: Skia's measureText against Fonts.layout (unhinted
# advances + GPOS pair kerning). Caveat Brush is measured on runs without contextual alternates (GSUB is not applied).
TEXT_RUNS = [
    ['290px "UF Black Ops"', 'v.NEXT'], ['60px "UF Black Ops"', 'CONTENTS: ANOTHER ME'],
    ['44px "UF Black Ops"', 'FRAGILE - HANDLE WITH FEAR'], ['72px "UF Black Ops"', 'SHIP IT'],
    ['bold 132px "Georgia", "UF Special Elite"', 'SLOW IT'], ['italic 44px "Georgia"', 'notes on caution, at the frontier'],
    ['30px "UF Special Elite"', 'R-3285 leak ........'], ['150px "UF Michroma"', 'ENGINE'],
    ['110px "UF Michroma"', 'WE TAKE THIS VERY SERIOUSLY.'], ['40px "UF Rajdhani"', 'ASSEMBLY DRAWING  EXPLODED VIEW'],
    ['120px "UF Kalam Bold"', 'P(DOOM | SHIP)'], ['100px "UF Kalam Bold"', 'AVAWATo Yo, LT'],
    ['36px "UF Mono"', 'SEQUENCE COMPLETION'], ['48px "UF Orbitron"', 'EXIT'], ['40px "UF Exo"', 'Tolerance AV Wa'],
    ['80px "UF Caveat Brush"', 'SHIP Q3'], ['60px "UF Kalam"', 'they ship anyway'],
]


def check_text_layout():
    try:
        out = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '--cached-only', '-A',
                              'text_measure_reference.mjs', json.dumps(TEXT_RUNS)], capture_output=True, text=True,
                             check=True, cwd=str(HERE)).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        print(f'SKIP text layout vs Skia: deno unavailable ({e})', flush=True)
        return
    skia = json.loads(out)
    F = L.napi()
    mine = [F.layout(f, t)[1] for f, t in TEXT_RUNS]
    basic = [F.font(f, 1.0)[0].getlength(t) for f, t in TEXT_RUNS]
    worst = max(abs(a - s) for a, s in zip(mine, skia))
    was = max(abs(b - s) for b, s in zip(basic, skia))
    check(f'text layout: {len(TEXT_RUNS)} runs in all eleven faces measure as Skia measures them (unhinted advances, '
          'GPOS pair kerning)', worst < 0.05, f'worst {worst:.3f} px; Pillow\'s own layout was off by {was:.1f} px')


def main():
    only = None
    if '--only' in sys.argv:
        only = set(sys.argv[sys.argv.index('--only') + 1].split(','))
    ART.mkdir(parents=True, exist_ok=True)
    make_refs()
    nums = json.loads((REF / 'numbers.json').read_text())
    # numbers
    for seed, vals in nums['streams'].items():
        r = L.rng(int(seed))
        got = [r() for _ in vals]
        check(f'rng({seed}) stream', got == vals, f'{got[:2]} vs {vals[:2]}')
        r2 = L.rng(int(seed))
        check(f'rng({seed}) take() matches r()', list(r2.take(len(vals))) == vals)
    W, H = 7, 5
    data = np.array([(i * 37 + 11) % 256 for i in range(W * H * 4)], np.uint8)
    for key, aw in (('mips', False), ('mipsAlpha', True)):
        lv = L.build_mips(data, W, H, aw)
        got = [[l['width'], l['height'], int(l['data'].astype(np.int64).sum())] for l in lv]
        check(f'build_mips alpha_weighted={aw}', got == nums[key], f'{got} vs {nums[key]}')
    noise = L.noise_rgba()
    ref = np.frombuffer((REF / 'noise_rgba.bin').read_bytes(), np.uint8).reshape(256, 256, 4)
    check('noise texture byte-exact', np.array_equal(noise, ref), f'{int((noise != ref).sum())} bytes differ')
    check('smooth / ramp', [L.smooth(x) for x in (0, 0.25, 0.5, 0.9)] == nums['smooth']
          and [L.ramp(0.3, 0.2, 0.4), L.ramp(-1, 0, 1)] == nums['ramp'])
    check_pcg()
    check_text_layout()
    # pixels
    N = L.napi()
    for name, (W, H, draw) in pieces().items():
        if only and name not in only and name.replace('board_', '') not in only:
            continue
        t = time.perf_counter()
        cv, ctx = L.canvas(N, W, H)
        draw(ctx, W, H)
        dt = time.perf_counter() - t
        cv.save_png(ART / f'{name}.png')
        compare(name, dt)
    compare_inline(only)
    print('ALL PASS' if not FAILS else f'{len(FAILS)} FAILED: {FAILS}', flush=True)
    return 0 if not FAILS else 1


if __name__ == '__main__':
    sys.exit(main())
