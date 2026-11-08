"""The machines' screen drawings, Python port vs the WebGPU originals run in Deno with Skia. No Blender needed:

    python -B blender/tests/voice_machines_a/test_screens_parity.py

parity_draw.mjs cuts drawC64 / drawMac / drawDesktop out of the JS modules and draws six cases on @napi-rs/canvas
(the engine's canvas) into out/parity_js/; this draws the same cases with c64.draw_c64, mac1984.draw_mac and
desktop2001.draw_desktop into out/parity_py/, compares them pixel by pixel (PASS / FAIL lines) and writes
out/parity_sheet.png: JS | Python | |difference| x 4, one row per case. Also checks the kit's rng and tiling noise
bit for bit against the JS (rng(seed) sequences, noiseTexture()), and the kit's other pure helpers against the JS
kit's own code (parity_kit.mjs): buildMips (plain and alpha-weighted, bit for bit), rrPoints, roundedRectShape and
roundedPolyline (points and length) and speckle (drawn on @napi-rs/canvas vs Canvas2D). parity_kit.mjs also dumps
the keycap / rbox / loftRings / planarUVFacing numbers that test_machines.py's kit probe checks in Blender.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'blender'))
from eidoblend.media.canvas_scenes import deno_exe  # noqa: E402
from eidoblend.props import voice_machines as VM  # noqa: E402
from eidoblend.props.voice_machines import c64, desktop2001, mac1984, noise_data, rng  # noqa: E402

OUT = HERE / 'out'
JS_DIR, PY_DIR = OUT / 'parity_js', OUT / 'parity_py'
FAILS = []


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


CASES = [
    {'machine': 'c64', 'name': 'c64_boot', 'lines': c64.BOOT, 'cursor': True, 'blink': 1},
    {'machine': 'c64', 'name': 'c64_say', 'lines': ['READY.', 'SAY "I WAS A MOUTH"', 'I WAS A MOUTH', 'READY.'],
     'cursor': True, 'blink': 0},
    {'machine': 'c64', 'name': 'c64_scroll', 'lines': [f'LINE {i} OF THE LONG LISTING, WRAPPED AT FORTY COLUMNS!'
                                                       for i in range(30)], 'cursor': 'solid', 'blink': 1},
    {'machine': 'mac1984', 'name': 'mac_hello', 'text': 'hello', 'title': 'Note'},
    {'machine': 'mac1984', 'name': 'mac_two', 'text': 'I was a mouth\nand a voice', 'title': 'MacinTalk'},
    {'machine': 'mac1984', 'name': 'mac_empty', 'text': '', 'title': 'Note'},
    {'machine': 'mac1984', 'name': 'mac_four_lines', 'text': 'one\ntwo lines here\nthree\nfour is cut', 'title': 'Note'},
    {'machine': 'mac1984', 'name': 'mac_long', 'text': 'Hello, I am Macintosh. Never trust a computer', 'title': 'x'},
    {'machine': 'c64', 'name': 'c64_unknown_chars', 'lines': ['lower case @ _ [ ] ~ & are skipped', '', 'OK'],
     'cursor': False, 'blink': 1},
    {'machine': 'desktop2001', 'name': 'desktop_long_word',
     'text': 'Supercalifragilisticexpialidocious and more words after it\nline two\nline three\nline four',
     'title': 'A much longer Narrator title', 'clock': '9:05 AM'},
    {'machine': 'desktop2001', 'name': 'desktop_empty', 'text': '', 'title': 'Narrator', 'clock': '10:23 PM'},
    {'machine': 'desktop2001', 'name': 'desktop_reading', 'text': 'reading screens', 'title': 'Narrator',
     'clock': '10:23 PM'},
    {'machine': 'desktop2001', 'name': 'desktop_wrap', 'text': 'I read every screen to you aloud\nthen I sang',
     'title': 'Narrator', 'clock': '11:59 PM'},
]
# what each case may differ by (0..255 per channel): the C64 is rect fills (exact); the Mac thresholds the same
# UI font rasterised by FreeType instead of Skia; the desktop antialiases shapes and text by supersampling
LIMITS = {'c64': (0.0, 0.0), 'mac1984': (6.0, 0.03), 'desktop2001': (3.0, 0.03)}


def js_drawings():
    cases = OUT / 'parity_cases.json'
    js_cases = []
    for c in CASES:
        d = dict(c)
        if c['machine'] == 'c64':
            d['lines'] = c64.flatten_lines(c['lines'])        # the JS draw gets setText's flattened lines
        js_cases.append(d)
    cases.write_text(json.dumps(js_cases), encoding='utf-8')
    r = subprocess.run([deno_exe(), 'run', '--no-config', '--no-lock', '--node-modules-dir=none', '--cached-only',
                        '-A', str(HERE / 'parity_draw.mjs'), str(JS_DIR), str(cases)], cwd=str(ROOT),
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode:
        print(r.stderr[-3000:])
    check(r.returncode == 0, 'parity_draw.mjs drew the JS originals')


def py_drawing(c):
    if c['machine'] == 'c64':
        return c64.draw_c64(c64.flatten_lines(c['lines']), c['cursor'], c['blink'], 768, 594)
    if c['machine'] == 'mac1984':
        return mac1984.draw_mac(c['text'], c['title'])
    return desktop2001.draw_desktop(c['text'], c['title'], c['clock'], 1024, 778)


def rng_and_noise():
    """rng(seed) and the tiling noise against the JS (Deno runs the kit's own rng and noiseTexture loops)."""
    js = r"""
const rng = (seed) => { let s = ((seed | 0) * 2654435761) >>> 0; return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s;
  t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; };
const out = { rng: {} };
for (const seed of [0, 1, 7, 2001, 123456789, -5]) { const r = rng(seed); out.rng[seed] = Array.from({ length: 64 }, () => r()); }
const N = 256, data = new Uint8Array(N * N * 4), chans = [[4, 5, 11], [8, 4, 23], [32, 3, 37], [64, 2, 53]];
for (let ch = 0; ch < 4; ch++) { const [P, oct, seed] = chans[ch], r = rng(seed), lats = [];
  for (let o = 0; o < oct; o++) { const p = P << o, L = new Float32Array(p * p); for (let i = 0; i < L.length; i++) L[i] = r(); lats.push([p, L]); }
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) { let v = 0, amp = 0.5, tot = 0;
    for (let o = 0; o < oct; o++) { const [p, L] = lats[o], fx = x / N * p, fy = y / N * p; const xi = Math.floor(fx), yi = Math.floor(fy), xf = fx - xi, yf = fy - yi;
      const X0 = xi % p, X1 = (xi + 1) % p, Y0 = (yi % p) * p, Y1 = ((yi + 1) % p) * p; const u = xf * xf * (3 - 2 * xf), w = yf * yf * (3 - 2 * yf);
      const a = L[Y0 + X0], b = L[Y0 + X1], c = L[Y1 + X0], d = L[Y1 + X1]; v += amp * (a + (b - a) * u + (c - a) * w + (a - b - c + d) * u * w); tot += amp; amp *= 0.5; }
    data[(y * N + x) * 4 + ch] = Math.round(255 * v / tot); } }
out.noise = Array.from(data);
console.log(JSON.stringify(out));
"""
    f = OUT / 'parity_rng_noise.mjs'
    f.write_text(js, encoding='utf-8')
    r = subprocess.run([deno_exe(), 'run', '--no-config', '--no-lock', '-A', str(f)], capture_output=True, text=True)
    data = json.loads(r.stdout)
    for seed, seq in data['rng'].items():
        g = rng(int(seed))
        mine = [g() for _ in range(64)]
        check(mine == seq, f'rng({seed}) matches the JS for 64 draws, bit for bit')
    jsn = np.array(data['noise'], np.uint8).reshape(256, 256, 4)
    py = noise_data()
    diff = np.abs(jsn.astype(int) - py.astype(int))
    print(f'  noise: max |diff| {diff.max()}, differing texels {(diff > 0).mean() * 100:.4f} %')
    # the JS fills its lattices through a Float32Array (rng values rounded to float32); the port keeps float64, so a
    # value on a rounding boundary may land one step off
    check(diff.max() <= 1 and (diff > 0).mean() < 0.002, 'noiseTexture(): every texel within 1 step of the JS')


def main():
    JS_DIR.mkdir(parents=True, exist_ok=True)
    PY_DIR.mkdir(parents=True, exist_ok=True)
    js_drawings()
    rows = []
    for c in CASES:
        js = np.asarray(Image.open(JS_DIR / f'{c["name"]}.png').convert('RGBA')).astype(np.float64)
        im = py_drawing(c)
        im.save(PY_DIR / f'{c["name"]}.png')
        py = np.asarray(im.convert('RGBA')).astype(np.float64)
        same_size = js.shape == py.shape
        check(same_size, f'{c["name"]}: the canvas is {js.shape[1]} x {js.shape[0]} as makeScreen made it')
        if not same_size:
            continue
        # compare premultiplied colour (the screen material samples rgb; transparent canvas rows are black)
        jp, pp = js[..., :3] * js[..., 3:] / 255.0, py[..., :3] * py[..., 3:] / 255.0
        d = np.abs(jp - pp)
        mean, frac = d.mean(), (d.max(axis=2) > 48).mean()
        lim_mean, lim_frac = LIMITS[c['machine']]
        check(mean <= lim_mean + 1e-9 and frac <= lim_frac + 1e-9,
              f'{c["name"]}: mean |diff| {mean:.3f} (<= {lim_mean}), pixels off by > 48: {frac * 100:.3f} % '
              f'(<= {lim_frac * 100:.1f} %)')
        rows.append((c['name'], jp, pp, d))
    # the contact sheet: JS | Python | |difference| x 4
    tw = 384
    sheet_rows = []
    for name, jp, pp, d in rows:
        h = int(round(jp.shape[0] * tw / jp.shape[1]))
        tiles = [Image.fromarray(np.clip(x, 0, 255).astype(np.uint8)).resize((tw, h), Image.Resampling.LANCZOS)
                 for x in (jp, pp, d * 4)]
        row = Image.new('RGB', (tw * 3 + 16, h + 18), (24, 24, 26))
        for i, t in enumerate(tiles):
            row.paste(t, (i * (tw + 8), 18))
        ImageDraw.Draw(row).text((4, 3), f'{name}: JS (Skia) | Python | |diff| x 4', fill=(220, 220, 220))
        sheet_rows.append(row)
    if sheet_rows:
        W = max(r.width for r in sheet_rows)
        sheet = Image.new('RGB', (W, sum(r.height for r in sheet_rows)), (24, 24, 26))
        y = 0
        for r in sheet_rows:
            sheet.paste(r, (0, y))
            y += r.height
        sheet.save(OUT / 'parity_sheet.png')
        print(f'[parity] sheet -> {OUT / "parity_sheet.png"}')
    rng_and_noise()
    kit_parity()
    print(f'[test_screens_parity] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
    return 1 if FAILS else 0


def three_build_dir():
    """A node_modules/three/build folder: this worktree's, else the main checkout's (read only)."""
    for root in (ROOT, ROOT.parent / 'eidoverse-video-prealpha-0.01'):
        d = root / 'node_modules' / 'three' / 'build'
        if (d / 'three.module.js').is_file():
            return d
    git = ROOT / '.git'
    if git.is_file() and git.read_text().startswith('gitdir:'):
        main = Path(git.read_text().split(':', 1)[1].strip()).parents[2]
        d = main / 'node_modules' / 'three' / 'build'
        if (d / 'three.module.js').is_file():
            return d
    return None


def kit_parity():
    """The kit's pure helpers against the JS kit's own code (parity_kit.mjs)."""
    tdir = three_build_dir()
    if tdir is None:
        check(False, 'kit parity: a node_modules/three/build folder (this worktree or the main checkout)')
        return
    r = subprocess.run([deno_exe(), 'run', '--no-config', '--no-lock', '--node-modules-dir=none', '--cached-only',
                        '-A', str(HERE / 'parity_kit.mjs'), str(tdir), str(OUT)], cwd=str(ROOT), capture_output=True,
                       text=True)
    print(r.stdout.strip())
    if r.returncode:
        print(r.stderr[-3000:])
    check(r.returncode == 0, 'parity_kit.mjs ran the JS kit')
    if r.returncode:
        return
    js = json.loads((OUT / 'parity_kit_js.json').read_text(encoding='utf-8'))
    # buildMips: bit for bit, every level, both modes (the input made by the JS with the kit's rng)
    src = np.array(js['mips_input'], np.uint8).reshape(23, 37, 4)
    for mode, weighted in (('mips_plain', False), ('mips_weighted', True)):
        mine = VM.build_mips(src, alpha_weighted=weighted)
        theirs = js[mode]
        same = len(mine) == len(theirs) and all(
            (m['width'], m['height']) == (t['w'], t['h']) and
            np.array_equal(m['data'].reshape(-1), np.array(t['data'], np.uint8)) for m, t in zip(mine, theirs))
        check(same, f'build_mips(alpha_weighted={weighted}): {len(mine)} levels 37 x 23 -> 1 x 1, bit for bit')
    b = VM.bleed_alpha(src)
    check(np.array_equal(b[..., 3], src[..., 3]) and np.array_equal(b[src[..., 3] > 0], src[src[..., 3] > 0]) and
          (b[src[..., 3] == 0][:, :3] > 0).any(),
          'bleed_alpha: alpha and every visible texel kept, the empty texels take colour from their neighbours')
    for case in js['rr_points']:
        w, h, rad, n, cx, cy = case['args']
        mine = np.array(VM.rr_points(w, h, rad, n, cx, cy))
        theirs = np.array(case['pts'])
        check(mine.shape == theirs.shape and np.abs(mine - theirs).max() < 1e-12,
              f'rr_points{tuple(case["args"])}: {len(mine)} points as rrPoints (max |diff| '
              f'{np.abs(mine - theirs).max() if mine.shape == theirs.shape else "shape"})')
    for case in js['rounded_rect_shape']:
        w, h, rad, cx, cy, hole = case['args']
        mine = np.array(VM.rounded_rect_shape(w, h, rad, cx, cy, hole))
        theirs = np.array(case['pts'])
        if len(theirs) > 1 and np.abs(theirs[0] - theirs[-1]).max() < 1e-12:
            theirs = theirs[:-1]                                  # three's getPoints closes the loop
        ok = mine.shape == theirs.shape and np.abs(mine - theirs).max() < 1e-12
        check(ok, f'rounded_rect_shape{tuple(case["args"])}: {len(mine)} points as roundedRectShape().getPoints(12)')
    rp = js['rounded_polyline']
    path = VM.rounded_polyline(rp['pts'], rp['radius'])
    mine, theirs = np.array(path.points(12)), np.array(rp['points'])
    check(mine.shape == theirs.shape and np.abs(mine - theirs).max() < 1e-12 and len(path.segments) == rp['n_curves'],
          f'rounded_polyline: {len(path.segments)} pieces, {len(mine)} points as getPoints(12)')
    check(abs(path.length - rp['length']) < 1e-9, f'rounded_polyline: length {path.length:.9f} m as getLength() '
                                                  f'({rp["length"]:.9f})')
    sp = js['speckle']
    g = VM.make_canvas(sp['w'], sp['h'])
    g.fill_rect(0, 0, sp['w'], sp['h'], '#ffffff')
    VM.speckle(g, sp['w'], sp['h'], sp['n'], sp['seed'], sp['colors'], sp['r_max'], sp['alpha'])
    im = g.image()
    im.save(OUT / 'parity_kit_speckle_py.png')
    a = np.asarray(im.convert('RGB'), np.float64)
    b = np.asarray(Image.open(OUT / 'parity_kit_speckle_js.png').convert('RGB'), np.float64)
    d = np.abs(a - b)
    dots_js, dots_py = (b.mean(axis=2) < 200).sum(), (a.mean(axis=2) < 200).sum()
    ink_js, ink_py = (255 - b).mean(), (255 - a).mean()
    # the dots' places, sizes and colours match; what differs is their antialiased rim (Skia's analytic coverage vs
    # 3 x 3 samples: the residue falls as the samples grow, mean 1.68 at 3 x, 0.82 at 8 x)
    check(abs(ink_py - ink_js) <= 0.02 * ink_js and abs(dots_py - dots_js) <= 0.05 * max(dots_js, 1) and
          d.mean() < 2.0, f'speckle: the same dots as the JS on Skia (ink {ink_py:.3f} vs {ink_js:.3f}, dark pixels '
                          f'{dots_py} vs {dots_js}, mean |diff| {d.mean():.3f} at their antialiased rims)')


if __name__ == '__main__':
    sys.exit(main())
