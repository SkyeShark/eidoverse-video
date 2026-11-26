#!/usr/bin/env python3
"""film_print.py: a finished film printed as a period release print: the colour its dye process gives the picture,
and everything the strip of film carries when it is projected. It works on any rendered video, from either edition,
and it runs LAST: after the render, and after any neural pass over the frames (a denoiser or a neural renderer such
as DLSS 5 would smooth the grain and the dirt away).

    python film_print.py film.mp4 [--out film_print.mp4] [--era 1970s|1960s] [--set grain=0.02,dust=0]
        [--letters timeline.json [--inks '#12082e,#ffe9a8,#ff8a1e'] [--where bottom]] [--parts 4] [--seed 1970]
    python film_print.py film.mp4 --stills DIR --at 1.5,3.0          # a few frames to look at first
    python film_print.py --images a.png,b.png --stills DIR [--at 1.5,3.0] [--fps 24]   # rendered stills

ERAS (--era)
  1970s  a 1970s release print. THE NEGATIVE AND THE DYES: the dye records' cross-talk (deep, clean primaries,
         greens leaning to blue-green), the decade's print light (golden highlights, warm-neutral shadows, a faint
         warm veil in the blacks), red-orange halation round the highlights at two spreads, the soft bloom of a
         diffusion filter, the print's tone curve (dense blacks, a soft shoulder). THE PRINT AS PROJECTED: the three
         dye records a little off register, the gate's weave, the softness of a later-generation print, dust and
         dirt (white where it lay on the negative, dark where it lies on the print), fibres, a hair in the gate now
         and then, scratches that run for seconds, the lamp's flicker, uneven density, the projector's falloff to
         the corners and the stock's grain in three dye layers.
  1960s  a first-run three-strip dye-transfer print: the same cross-talk and print tone, red halation, fine grain,
         a little weave and flicker, soft corners; clean (no dirt, no scratches, no hairs).
Every value of a preset can be changed with --set name=value (the names: ERAS below).

Every frame's artefacts come from its frame number and --seed alone, so any range of frames prints the same pixels
on its own: --parts N prints N ranges side by side (one process each) and joins them without a re-encode. The sound
is copied as it is. Output: H.264 High, yuv420p (--crf, --preset).

LETTERING (--letters): the lines of a timeline lettered into the picture as heavy capitals swelled and bent to fill
a band (the way late-1960s concert posters were lettered), in two inks with a dark padded outline. Timelines:
{"captions": [{text, t0, t1}]} (song_clock.py's clock, voicebox/song timelines) or align_lyrics.py's list of
{text, start, end}. A caption may carry "where": "bottom" | "top" | "top-left", "style": "band" | "arch" (large,
arched across the top of the frame) and "inks": [outline, top, bottom]. The lettering goes into the graded picture
before the print's artefacts, as a title printed into the film: the weave, dirt and grain go over it too. It sits
on screen from 0.25 s before a line to 0.42 s after it, fading in and out. Font: Anton (OFL, in the repo).

Dependencies: numpy, Pillow, ffmpeg/ffprobe. Guide: tools-guides/postprocessing.md ("After the render: the
release print").
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = ROOT / 'eidoverse' / 'assets' / 'fonts' / 'Anton-Regular.ttf'
NOWIN = 0x08000000 if os.name == 'nt' else 0          # no console windows for the children on Windows
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)

# THE DYE RECORDS' CROSS-TALK: each record takes a share away from the others (what made the dye prints' primaries
# deep and clean). Rows: the print's R, G, B from the scene's R, G, B, in linear light.
CROSS_TALK = np.array([[1.38, -0.26, -0.12],
                       [-0.14, 1.30, -0.16],
                       [-0.06, -0.30, 1.36]], np.float32)

ERAS = {
    '1970s': dict(
        cross=1.0,                       # the cross-talk's strength (0: none, 1: the matrix above)
        richness=1.22,                   # the dyes' saturation about the grey
        exposure=1.0,                    # print light, in linear light (a colourist's trim)
        shadow_tint=(1.00, 0.985, 0.95),  # the print light in the shadows ...
        light_tint=(1.07, 1.02, 0.87),   # ... and in the light parts
        halation=0.55,                   # halation from this linear level up ...
        halation_spreads=((3.0, (0.30, 0.09, 0.02)), (14.0, (0.22, 0.07, 0.015))),  # (radius at 1080p / 4, RGB)
        bloom=(0.085, 0.072, 0.052),     # the diffusion filter's glow (RGB) from ...
        bloom_from=0.30,                 # ... this linear level
        veil=(0.0026, 0.0021, 0.0014),   # flashing: a warm veil in the blacks
        registration=1.0,                # the dye records off register (x 0.5 px at 1080p)
        weave=1.0,                       # the gate's weave (x 0.9 px at 1080p)
        softness=0.7,                    # the print's softness (0..1: a 1-2-1 blur mixed in)
        dust=4.0,                        # dust and dirt specks a frame (on average)
        fibre=0.05,                      # the chance of a fibre in a frame
        hairs=0.9,                       # hairs in the gate a minute (each for 1.5-2.5 s)
        scratch_every=13.0,              # seconds between scratches on average (each runs 1-3.5 s); 0: none
        flicker=1.0,                     # the lamp's flicker (x 1.6 %)
        density=1.0,                     # the print's uneven density (x 1.2 %)
        falloff=0.20,                    # the projector's falloff to the corners
        grain=0.026),                    # the grain's amplitude in the mid-tones
    '1960s': dict(
        cross=1.0, richness=1.22, exposure=1.0,
        shadow_tint=(1.0, 0.995, 0.98), light_tint=(1.04, 1.01, 0.93),
        halation=0.6, halation_spreads=((4.0, (0.26, 0.06, 0.02)),),
        bloom=(0.0, 0.0, 0.0), bloom_from=0.30, veil=(0.0, 0.0, 0.0),
        registration=0.0, weave=0.5, softness=0.35,
        dust=0.0, fibre=0.0, hairs=0.0, scratch_every=0.0,
        flicker=0.6, density=0.3, falloff=0.16, grain=0.016),
}


def srgb_to_lin(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(x):
    x = np.clip(x, 0.0, None)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def print_tone(x):
    """a print's characteristic curve on linear light: a dense toe (the blacks of a dye print), a middle steeper than
    the scene's, a soft shoulder (no hard clip)"""
    y = np.clip(x - 0.018, 0.0, None)
    y = np.power(y * 1.10, 1.12)
    return y / (1.0 + y * 0.58) * 1.58


LUT_IN = srgb_to_lin(np.arange(256, dtype=np.float64) / 255.0).astype(np.float32)   # the 8-bit sRGB decode, exact


def hexrgb(h):
    h = h.strip().lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def shift(a, dx, dy):
    """a (H x W) moved (dx, dy) pixels (x right, y down), bilinear, its edges held"""
    ix, iy = math.floor(dx), math.floor(dy)
    fx, fy = dx - ix, dy - iy

    def sh(sx, sy):
        o = np.roll(a, (sy, sx), axis=(0, 1))
        if sy > 0:
            o[:sy] = o[sy:sy + 1]
        elif sy < 0:
            o[sy:] = o[sy - 1:sy]
        if sx > 0:
            o[:, :sx] = o[:, sx:sx + 1]
        elif sx < 0:
            o[:, sx:] = o[:, sx - 1:sx]
        return o
    return ((sh(ix, iy) * (1.0 - fx) + sh(ix + 1, iy) * fx) * (1.0 - fy)
            + (sh(ix, iy + 1) * (1.0 - fx) + sh(ix + 1, iy + 1) * fx) * fy)


def blurred(field, size, radius, out_size):
    """a 0..1 field reduced to `size`, Gaussian-blurred by `radius` px there, and brought back to `out_size`"""
    q = Image.fromarray(np.clip(field * 255.0, 0, 255).astype(np.uint8)).resize(size, Image.BILINEAR)
    return np.asarray(q.filter(ImageFilter.GaussianBlur(radius)).resize(out_size, Image.BILINEAR), np.float32) / 255.0


# ------------------------------------------------------------------------------------------------------ the lettering
def lettering(text, width, height, bulge=0.38, wave=0.0, arch=0.0):
    """heavy capitals swelled to fill a band: an alpha image (H x W float 0..1). Each column is stretched so the line
    is tall in its middle and short at its ends (bulge), rides a wave, or arches"""
    f = ImageFont.truetype(str(FONT), 300)
    tw = int(ImageDraw.Draw(Image.new('L', (8, 8))).textlength(text, font=f))
    src = Image.new('L', (tw + 40, 420), 0)
    ImageDraw.Draw(src).text((20, 210), text, font=f, fill=255, anchor='lm')
    src = src.crop(src.getbbox()).resize((width, height), Image.LANCZOS)
    a = np.asarray(src, np.float32) / 255.0
    oh = int(height * 1.6)
    xs = np.arange(width) / max(1, width - 1)
    scale = (1.0 - bulge) + bulge * np.sin(np.pi * xs) ** 0.8                      # the column's height, 0..1
    centre = oh / 2 + wave * height * np.sin(2 * np.pi * xs * 1.5) - arch * height * (np.sin(np.pi * xs) - 0.6)
    ys = np.arange(oh)[:, None]
    sy = (ys - centre[None, :]) / (scale[None, :] * height) + 0.5                  # 0..1 in the source
    ok = (sy >= 0) & (sy < 1)
    iy = np.clip((sy * height).astype(np.int32), 0, height - 1)
    return np.where(ok, a[iy, np.arange(width)[None, :]], 0.0).astype(np.float32)


def two_rows(text, row_w, row_h, centre=True, **kw):
    """a long line lettered as two rows, the second tucked under the first"""
    words, k = text.split(' '), 1
    while k < len(words) - 1 and len(' '.join(words[:k])) < len(text) / 2 - 2:
        k += 1
    rows = [lettering(' '.join(r), row_w(' '.join(r)), row_h, **kw) for r in (words[:k], words[k:])]
    ww = max(r.shape[1] for r in rows)
    hh = int(rows[0].shape[0] * 0.72)
    a = np.zeros((hh + rows[1].shape[0], ww), np.float32)
    for j, r in enumerate(rows):
        x0 = (ww - r.shape[1]) // 2 if centre else 0
        a[j * hh:j * hh + r.shape[0], x0:x0 + r.shape[1]] = np.maximum(a[j * hh:j * hh + r.shape[0], x0:x0 + r.shape[1]], r)
    return a


def load_captions(path):
    tl = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(tl, list):                                  # align_lyrics.py's list
        caps = [{'text': c['text'], 't0': c['start'], 't1': c['end']} for c in tl]
    else:
        caps = tl.get('captions', [])
    return sorted((c for c in caps if c.get('text', '').strip() and float(c['t1']) > float(c['t0'])),
                  key=lambda c: float(c['t0']))


class Letters:
    """the timeline's lines, lettered at frame size (w, h)"""
    LEAD, TAIL, FADE_IN, FADE_OUT = 0.25, 0.42, 0.25, 0.33     # seconds on screen round a line, and its fades

    def __init__(self, captions, w, h, inks, where='bottom'):
        self.caps, self.w, self.h, self.where = captions, w, h, where
        self.inks = [hexrgb(c) for c in inks]
        self.k = w / 1920.0                                     # (the sizes below are for a 1920-wide frame)
        self.cache = {}

    def at(self, t):
        for i, c in enumerate(self.caps):
            a, b = float(c['t0']) - self.LEAD, float(c['t1']) + self.TAIL
            if a <= t < b:
                return i, max(0.0, min(1.0, (t - a) / self.FADE_IN, (b - t) / self.FADE_OUT))
        return None, 0.0

    def shape(self, i):
        if i in self.cache:
            return self.cache[i]
        c, k, W, H = self.caps[i], self.k, self.w, self.h
        txt = c['text'].replace('\\N', ' ').replace('\n', ' ').upper().replace('"', '').strip().rstrip(',.')
        where, style = c.get('where', self.where), c.get('style', 'band')
        r = max(1, int(round(6 * k)))                          # the outline's reach
        fit = lambda wpx: max(8, min(int(wpx), W - int(32 * k) - 2 * r))  # noqa: E731
        if style == 'arch':
            a = lettering(txt, fit(1120 * k), max(8, int(172 * k)), bulge=0.3, arch=0.55)
            where = 'top'
        elif where == 'top-left':
            a = two_rows(txt, lambda s: fit(min(640, 90 + 29 * len(s)) * k), max(8, int(70 * k)), centre=False,
                         bulge=0.4, wave=0.05)
        elif len(txt) > 26:                                    # a long line in one row would be too small to read
            a = two_rows(txt, lambda s: fit(min(1120, 112 + 35 * len(s)) * k), max(8, int(81 * k)), bulge=0.4, wave=0.05)
        else:
            a = lettering(txt, fit(min(1170, 128 + 40 * len(txt)) * k), max(8, int(105 * k)), bulge=0.42, wave=0.06)
        pad = r + 3                                            # room for the outline round every letter
        a = np.pad(a, ((pad, pad), (pad, pad)))
        o = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * r + 1)),
                       np.float32) / 255.0
        hh, ww = a.shape
        if where == 'top-left':
            x0, y0 = int(30 * k), int(14 * k)
        elif where == 'top':
            x0, y0 = max(0, (W - ww) // 2), int((26 if style == 'arch' else 20) * k)
        else:
            x0, y0 = max(0, (W - ww) // 2), max(0, H - hh - int(22 * k))
        inks = [hexrgb(x) for x in c['inks']] if c.get('inks') else self.inks
        self.cache[i] = (a, o, x0, y0, inks)
        return self.cache[i]

    def draw(self, out, t):
        """letter the line showing at time t into out (H x W x 3 float, in place)"""
        i, fade = self.at(t)
        if i is None or fade <= 0:
            return out
        a, o, x0, y0, (outline, top, bottom) = self.shape(i)
        hh, ww = a.shape
        ya, yb, xa, xb = max(0, y0), min(self.h, y0 + hh), max(0, x0), min(self.w, x0 + ww)
        if yb <= ya or xb <= xa:
            return out
        a, o = a[ya - y0:yb - y0, xa - x0:xb - x0], o[ya - y0:yb - y0, xa - x0:xb - x0]
        reg = out[ya:yb, xa:xb]
        oo = (o * fade)[..., None]
        reg[:] = reg * (1 - oo) + outline * oo
        aa = (a * fade)[..., None]
        grad = np.linspace(0, 1, hh, dtype=np.float32)[ya - y0:yb - y0, None, None]
        reg[:] = reg * (1 - aa) + (top * (1 - grad) + bottom * grad) * aa
        return out


# ------------------------------------------------------------------------------------------------------- the print
class Printer:
    """one era's print at one frame size: frame(rgb uint8 H x W x 3, frame number 1-based) -> uint8"""

    def __init__(self, w, h, fps=24.0, era='1970s', seed=1970, overrides=None, letters=None):
        self.p = dict(ERAS[era])
        self.p.update(overrides or {})
        self.w, self.h, self.fps, self.seed, self.letters = w, h, float(fps), int(seed), letters
        self.s = h / 1080.0                                    # (sizes in pixels are given for 1080 lines)
        p = self.p
        m = np.eye(3, dtype=np.float32) + float(p['cross']) * (CROSS_TALK - np.eye(3, dtype=np.float32))
        self.matrix_t = m.T.copy()
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r2 = ((xx - w * 0.5) / (w * 0.5)) ** 2 + ((yy - h * 0.5) / (h * 0.5)) ** 2
        f = float(p['falloff'])
        self.vig = ((1.0 - f * np.clip(r2 - 0.22, 0.0, None) ** 1.1) * (1.0 + 0.15 * f * np.exp(-r2 * 1.6))).astype(np.float32)
        self.gx, self.gy = (xx / w - 0.5) * 2.0, (yy / h - 0.5) * 2.0
        s_ = np.linspace(0.0, 1.0, 4096, dtype=np.float64)
        self.tone = lin_to_srgb(print_tone(8.0 * s_ * s_)).astype(np.float32)
        # the grain is drawn on about 540 lines whatever the frame's size (grain belongs to the film, not to pixels)
        self.gh = min(h, 540)
        self.gw = max(1, round(w * self.gh / h))
        n = np.random.default_rng(1).standard_normal((self.gh, self.gw), dtype=np.float32)
        self.grain_sd = float(self.grow(n).std()) or 1.0
        # where a scratch breaks along its run: smooth noise down the frame, a bank of 64
        rng = np.random.default_rng([self.seed, 5])
        q = rng.standard_normal((64, h // 24 + 2)).astype(np.float32)
        q = np.stack([np.interp(np.arange(h) / 24.0, np.arange(q.shape[1]), row) for row in q])
        self.scr_prof = np.clip((q + 0.9) / 1.4, 0.0, 1.0).astype(np.float32)
        self.blocks = {}

    def grow(self, n):
        if n.shape == (self.h, self.w):
            return n
        return np.asarray(Image.fromarray(n, 'F').resize((self.w, self.h), Image.BILINEAR), np.float32)

    # ---------------------------------------------------------------------- the schedule: scratches and hairs
    def events(self, fr):
        """the scratches and hairs alive at frame fr. They are drawn per two-minute block of frames from the seed and
        the block's number alone, so every range of the film sees the same ones"""
        block = max(1, int(round(self.fps * 120)))
        b = (fr - 1) // block
        scr, hairs = [], []
        for bb in (b - 1, b):
            if bb < 0:
                continue
            if bb not in self.blocks:
                rng = np.random.default_rng([self.seed, 3, bb])
                s_list, h_list = [], []
                every = float(self.p['scratch_every'])
                for _ in range(rng.poisson(block / (self.fps * every)) if every > 0 else 0):
                    s_list.append((1 + bb * block + int(rng.integers(0, block)), int(round(rng.uniform(1.0, 3.5) * self.fps)),
                                   float(rng.uniform(0.07, 0.93)), float(rng.uniform(1.5, 9.0)), float(rng.uniform(0, 6.28)),
                                   bool(rng.random() < 0.5), float(rng.uniform(0.28, 0.55))))
                for _ in range(rng.poisson(2.0 * float(self.p['hairs']))):
                    f0 = 1 + bb * block + int(rng.integers(0, block))
                    side = int(rng.integers(0, 3))
                    x, y = ((0.0, rng.uniform(0.2, 0.8)), (1.0, rng.uniform(0.2, 0.8)), (rng.uniform(0.2, 0.8), 0.0))[side]
                    ang = (0.0, math.pi, math.pi / 2)[side] + rng.uniform(-0.5, 0.5)
                    pts, px, py = [], x * (self.w - 1), y * (self.h - 1)
                    pts.append((px, py))
                    for _ in range(int(rng.integers(14, 26))):
                        ang += rng.uniform(-0.35, 0.35)
                        px, py = px + 7.0 * self.s * math.cos(ang), py + 7.0 * self.s * math.sin(ang)
                        pts.append((px, py))
                    h_list.append((f0, int(round(rng.uniform(1.5, 2.5) * self.fps)), pts))
                self.blocks[bb] = (s_list, h_list)
            scr += [e for e in self.blocks[bb][0] if e[0] <= fr < e[0] + e[1]]
            hairs += [e for e in self.blocks[bb][1] if e[0] <= fr < e[0] + e[1]]
        return scr, hairs

    # ---------------------------------------------------------------------- THE NEGATIVE AND THE DYES
    def grade(self, rgb):
        """uint8 sRGB -> float 0..1 sRGB: the cross-talk, the dyes' richness, the print light, halation, the diffusion
        filter's bloom, the veil, the print's tone (the decode: a 256-entry table; the tone and the encode: one 4096-entry
        table read on sqrt(y / 8), fine in the shadows)"""
        p, W, H, s = self.p, self.w, self.h, self.s
        x = LUT_IN[rgb]
        if float(p['exposure']) != 1.0:
            x = x * np.float32(p['exposure'])
        y = np.clip(x @ self.matrix_t, 0.0, None)
        lum = y @ LUMA
        y = lum[..., None] + (y - lum[..., None]) * np.float32(p['richness'])
        k = np.clip(lum / 0.5, 0.0, 1.0)[..., None]
        y = y * (np.array(p['shadow_tint'], np.float32) * (1.0 - k) + np.array(p['light_tint'], np.float32) * k)
        hi = np.clip(lum - float(p['halation']), 0.0, None)
        if p['halation_spreads'] and hi.max() > 0:              # the red record lay deepest: halation is red-orange
            for radius, rgb_amt in p['halation_spreads']:
                y = y + blurred(hi, (max(1, W // 4), max(1, H // 4)), radius * s, (W, H))[..., None] * np.array(rgb_amt, np.float32)
        if any(p['bloom']):                                     # the light parts glow a little into what is round them
            glow = blurred(np.clip(lum - float(p['bloom_from']), 0.0, None) * 1.5, (max(1, W // 8), max(1, H // 8)), 5 * s, (W, H))
            y = y + glow[..., None] / 1.5 * np.array(p['bloom'], np.float32)
        y = y + np.array(p['veil'], np.float32)
        idx = (np.sqrt(np.clip(y, 0.0, 8.0) * 0.125) * 4095.0 + 0.5).astype(np.int32)
        return self.tone[idx]

    # ---------------------------------------------------------------------- THE PRINT AS PROJECTED
    def projected(self, out, fr):
        """over the whole composed frame (float 0..1): registration and weave, softness, dirt, fibres, hairs, scratches,
        flicker, density, falloff, grain -> float 0..1"""
        p, s = self.p, self.s
        u = fr * 24.0 / self.fps                                # (the slow wanderings run in seconds, as at 24 fps)
        j = np.random.default_rng([self.seed, 1, fr]).standard_normal(6)
        wv, rg = float(p['weave']) * s, float(p['registration']) * s
        if wv or rg:
            wx = wv * (0.55 * math.sin(u * 0.21 + 0.4) + 0.30 * math.sin(u * 0.83 + 2.0) + 0.16 * j[0])
            wy = wv * (0.85 * math.sin(u * 0.17 + 1.1) + 0.40 * math.sin(u * 0.67 + 0.3) + 0.22 * j[1])
            rx, ry = rg * 0.55 * math.sin(u * 0.011 + 0.7), rg * 0.35 * math.sin(u * 0.017 + 2.1)
            bx, by = rg * -0.45 * math.sin(u * 0.013 + 1.9), rg * 0.40 * math.sin(u * 0.009 + 0.2)
            out = np.stack([shift(out[..., 0], wx + rx, wy + ry), shift(out[..., 1], wx, wy),
                            shift(out[..., 2], wx + bx, wy + by)], axis=2)
        soft = float(p['softness'])
        if soft:
            b = out * 0.5 + (np.roll(out, 1, 1) + np.roll(out, -1, 1)) * 0.25
            b = b * 0.5 + (np.roll(b, 1, 0) + np.roll(b, -1, 0)) * 0.25
            out = out * (1.0 - soft) + b * soft
        out = self.dirt(out, fr, j)
        flick = 1.0 + float(p['flicker']) * (0.016 * math.sin(u * 1.9 + 2.0 * math.sin(u * 0.31)) + 0.009 * j[2])
        dens = 1.0 + float(p['density']) * (0.012 * math.sin(u * 0.53) * self.gx + 0.010 * math.sin(u * 0.41 + 1.0) * self.gy)
        out = out * (self.vig * flick * dens)[..., None]
        g_amp = float(p['grain'])
        if g_amp:                                                # three dye layers, mostly shared
            rng = np.random.default_rng([self.seed, 2, fr])
            shared = rng.standard_normal((self.gh, self.gw), dtype=np.float32)
            lum = out @ LUMA
            amp = (g_amp * (0.40 + 0.60 * 4.0 * lum * (1.0 - lum))).astype(np.float32)
            for c in range(3):
                n = 0.78 * shared + 0.63 * rng.standard_normal((self.gh, self.gw), dtype=np.float32)
                out[..., c] += self.grow(n) / self.grain_sd * amp
        return np.clip(out, 0.0, 1.0)

    def dirt(self, out, fr, j):
        """dust, dirt and fibres new every frame; the scheduled hairs and scratches that stay"""
        p, W, H, s = self.p, self.w, self.h, self.s
        rng = np.random.default_rng([self.seed, 6, fr])
        mw, mb = Image.new('L', (W, H), 0), Image.new('L', (W, H), 0)
        dw, db = ImageDraw.Draw(mw), ImageDraw.Draw(mb)
        drawn = False
        for _ in range(rng.poisson(float(p['dust'])) if float(p['dust']) > 0 else 0):
            x, y = rng.uniform(0, W), rng.uniform(0, H)
            d = dw if rng.random() < 0.62 else db                  # white: on the negative when printed; dark: on the print
            kind = rng.random()
            r_ = (rng.uniform(0.6, 1.5) if kind < 0.70 else rng.uniform(1.5, 3.2) if kind < 0.95 else rng.uniform(3.2, 7.0)) * s
            op = int(rng.uniform(150, 255))
            for b_ in range(1 if kind < 0.95 else int(rng.integers(2, 5))):     # a big one is a clump: irregular
                ox, oy = (rng.uniform(-r_, r_), rng.uniform(-r_, r_)) if b_ else (0.0, 0.0)
                sx, sy = r_ * rng.uniform(0.6, 1.3), r_ * rng.uniform(0.6, 1.3)
                d.ellipse((x + ox - sx, y + oy - sy, x + ox + sx, y + oy + sy), fill=op)
            drawn = True
        if float(p['fibre']) > 0 and rng.random() < float(p['fibre']):
            d = db if rng.random() < 0.6 else dw
            x, y, a_ = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0, 6.28)
            pts = [(x, y)]
            for _ in range(int(rng.integers(5, 11))):
                a_ += rng.uniform(-0.7, 0.7)
                x, y = x + 6.0 * s * math.cos(a_), y + 6.0 * s * math.sin(a_)
                pts.append((x, y))
            d.line(pts, fill=int(rng.uniform(140, 230)), width=max(1, int(round(s))))
            drawn = True
        scratches, hairs = self.events(fr)
        for (_f0, _n, pts) in hairs:                               # a hair in the gate, for a second or two
            ox, oy = 2.0 * s * math.sin(fr * 0.9), 1.5 * s * math.cos(fr * 0.7)
            db.line([(px + ox, py + oy) for px, py in pts], fill=215, width=max(1, int(round(2 * s))))
            drawn = True
        if drawn:
            w_ = np.asarray(mw.filter(ImageFilter.GaussianBlur(0.7 * s)), np.float32)[..., None] / 255.0
            b_ = np.asarray(mb.filter(ImageFilter.GaussianBlur(0.7 * s)), np.float32)[..., None] / 255.0
            out = out * (1.0 - 0.88 * b_)
            out = out + (np.array([0.97, 1.0, 0.95], np.float32) - out) * (0.90 * w_)
        for (_f0, _n, x0, amp, ph, light, k) in scratches:        # down the strip, for seconds
            x = x0 * W + amp * s * math.sin(fr * 0.05 + ph) + 0.35 * s * j[3]
            xi, fx = int(x), x - int(x)
            if xi < 1 or xi >= W - 2:
                continue
            along = self.scr_prof[(fr * 37 + int(x0 * 1000)) % self.scr_prof.shape[0]]
            vis = (k * (0.65 + 0.35 * abs(j[4])) * along)[:, None]
            for c_, wgt in ((xi, 1.0 - fx), (xi + 1, fx)):
                col = out[:, c_, :]
                if light:
                    out[:, c_, :] = col + (np.array([0.80, 0.98, 0.84], np.float32) - col) * (vis * wgt)
                else:
                    out[:, c_, :] = col * (1.0 - vis * wgt * np.array([0.62, 0.55, 0.62], np.float32))
        return out

    def frame(self, rgb, fr):
        """rgb: H x W x 3 uint8, fr: its frame number in the film (1-based) -> the printed frame, uint8"""
        out = self.grade(rgb)
        if self.letters is not None:
            out = self.letters.draw(out, (fr - 1) / self.fps)
        return (self.projected(out, fr) * 255.0 + 0.5).astype(np.uint8)


# ---------------------------------------------------------------------------------------------------- the film
def probe(path):
    r = json.loads(subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
         'stream=width,height,avg_frame_rate,r_frame_rate,start_time,nb_frames:format=duration', '-of', 'json', str(path)],
        capture_output=True, text=True, check=True, creationflags=NOWIN).stdout)
    st = r['streams'][0]
    rate = st.get('avg_frame_rate') if st.get('avg_frame_rate', '0/0') != '0/0' else st['r_frame_rate']
    num, den = (int(x) for x in rate.split('/'))
    fps = num / den
    n = int(st.get('nb_frames') or 0)
    if not n:
        n = count_frames(path)
    return dict(w=int(st['width']), h=int(st['height']), fps=fps, rate=rate, n=n,
                start=float(st.get('start_time') or 0.0))


def count_frames(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries',
                        'stream=nb_read_packets', '-of', 'csv=p=0', str(path)], capture_output=True, text=True,
                       creationflags=NOWIN)
    return int(r.stdout.strip() or 0)


def encoder(path, v, a, with_sound_from=None):
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f"{v['w']}x{v['h']}", '-r', v['rate'],
           '-i', '-']
    if with_sound_from:
        cmd += ['-i', str(with_sound_from), '-map', '0:v', '-map', '1:a?', '-c:a', 'copy']
    cmd += ['-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', str(a.crf), '-preset', a.preset]
    if with_sound_from:
        cmd += ['-movflags', '+faststart']
    return subprocess.Popen(cmd + [str(path)], stdin=subprocess.PIPE, creationflags=NOWIN)


def make_printer(a, w, h, fps):
    letters = None
    if a.letters:
        letters = Letters(load_captions(a.letters), w, h, a.inks.split(','), where=a.where)
    return Printer(w, h, fps=fps, era=a.era, seed=a.seed, overrides=a.overrides, letters=letters)


def print_range(a, src, v, first, last, out, sound):
    """frames first..last of src printed into out (with src's sound when `sound`)"""
    P = make_printer(a, v['w'], v['h'], v['fps'])
    size = v['w'] * v['h'] * 3
    # (seek half a frame early: frame `first` is the first whose time is at or after it, whatever the rounding;
    #  ffmpeg offsets an input -ss by the file's start time itself)
    ss = max(0.0, (first - 1.5) / v['fps']) if first > 1 else 0.0
    rd = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', f'{ss:.6f}', '-i', str(src), '-frames:v', str(last - first + 1),
                           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE, creationflags=NOWIN)
    wr = encoder(out, v, a, with_sound_from=src if sound else None)
    fr, t0, total = first - 1, time.time(), last - first + 1
    while fr < last:
        raw = rd.stdout.read(size)
        if len(raw) < size:
            break
        fr += 1
        wr.stdin.write(P.frame(np.frombuffer(raw, np.uint8).reshape(v['h'], v['w'], 3), fr).tobytes())
        done = fr - first + 1
        if done % max(1, total // 10) == 0:
            print(f'[print] frames {first}..{last}: {done} of {total} ({done / max(1e-6, time.time() - t0):.1f} a second)',
                  flush=True)
    rd.kill()
    rd.wait()
    wr.stdin.close()
    wr.wait()
    return fr - first + 1


def ranges(n, parts):
    edges = [1 + round(k * n / parts) for k in range(parts)] + [n + 1]
    return [(a, b - 1) for a, b in zip(edges[:-1], edges[1:]) if b - 1 >= a]


def print_in_parts(a, src, v, out):
    """the film in N ranges side by side, each its own process; the segments joined as they are, with the sound"""
    rs = ranges(v['n'], a.parts)
    tmp = tempfile.mkdtemp(prefix='film_print_')
    print(f"[print] {v['n']} frames in {len(rs)} ranges: {rs}", flush=True)
    t0 = time.time()
    procs = []
    for k, (A, B) in enumerate(rs):
        seg = os.path.join(tmp, f'part_{k:02d}.mp4')
        cmd = [sys.executable, os.path.abspath(__file__), str(src), '--range', str(A), str(B), '--segment', seg,
               '--era', a.era, '--seed', str(a.seed), '--crf', str(a.crf), '--preset', a.preset]
        for kv in a.set or []:
            cmd += ['--set', kv]
        if a.letters:
            cmd += ['--letters', os.path.abspath(a.letters), '--inks', a.inks, '--where', a.where]
        log = open(os.path.join(tmp, f'part_{k:02d}.log'), 'w')
        procs.append((k, A, B, seg, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, creationflags=NOWIN), log))
    bad = []
    for k, A, B, seg, p, log in procs:
        code = p.wait()
        log.close()
        got = count_frames(seg) if os.path.exists(seg) else 0
        print(f'[print] range {k} ({A}..{B}): exit {code}, {got} of {B - A + 1} frames', flush=True)
        if code != 0 or got != B - A + 1:
            bad.append(k)
    if bad:
        raise SystemExit(f'[print] ranges {bad} failed: their logs are in {tmp}')
    lst = os.path.join(tmp, 'parts.txt')
    with open(lst, 'w', encoding='utf-8') as fh:
        for _k, _A, _B, seg, _p, _l in procs:
            fh.write("file '" + seg.replace('\\', '/').replace("'", "'\\''") + "'\n")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-i', str(src), '-map', '0:v',
                    '-map', '1:a?', '-c', 'copy', '-movflags', '+faststart', str(out)], check=True, creationflags=NOWIN)
    got = count_frames(out)
    print(f"[print] {out}: {got} frames (the source has {v['n']}), {time.time() - t0:.0f} s", flush=True)
    if got != v['n']:
        raise SystemExit('[print] the joined film has the wrong number of frames')
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


def stills(a):
    """single frames printed to look at: <dir>/<name>_f<frame>_<era>.png and a before | after picture beside it"""
    os.makedirs(a.stills, exist_ok=True)
    ats = [float(x) for x in a.at.split(',') if x.strip()] if a.at else []
    jobs = []
    if a.images:
        for i, path in enumerate(a.images.split(',')):
            t = ats[i] if i < len(ats) else i / a.fps
            jobs.append((Path(path).stem, np.asarray(Image.open(path).convert('RGB')), a.fps, t))
    else:
        v = probe(a.video)
        for t in ats:
            fr = int(round(t * v['fps'])) + 1
            ss = max(0.0, (fr - 1.5) / v['fps'])
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{ss:.6f}', '-i', str(a.video), '-frames:v', '1', '-f', 'rawvideo',
                                  '-pix_fmt', 'rgb24', '-'], capture_output=True, creationflags=NOWIN).stdout
            jobs.append((Path(a.video).stem, np.frombuffer(raw, np.uint8).reshape(v['h'], v['w'], 3), v['fps'], t))
    printers = {}
    for name, img, fps, t in jobs:
        h, w = img.shape[:2]
        if (w, h, fps) not in printers:
            printers[(w, h, fps)] = make_printer(a, w, h, fps)
        fr = int(round(t * fps)) + 1
        out = printers[(w, h, fps)].frame(img, fr)
        base = os.path.join(a.stills, f'{name}_f{fr:05d}_{a.era}')
        Image.fromarray(out).save(base + '.png')
        pair = np.concatenate([img, out], axis=1)
        Image.fromarray(pair).resize((w, h // 2) if w > 960 else (2 * w, h), Image.LANCZOS).save(base + '_before_after.jpg', quality=92)
        print(f'[print] {base}.png (frame {fr}, {t:.2f} s) and {base}_before_after.jpg', flush=True)


def split_top(s):
    """'a=1,b=[1,2]' -> ['a=1', 'b=[1,2]']: commas inside brackets stay"""
    out, depth, cur = [], 0, ''
    for ch in s:
        depth += ch == '['
        depth -= ch == ']'
        if ch == ',' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    return out + [cur] if cur else out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('video', nargs='?')
    ap.add_argument('--out', default=None, help='default: <video>_print.mp4 beside the video')
    ap.add_argument('--era', default='1970s', choices=sorted(ERAS))
    ap.add_argument('--set', action='append', default=[], help="a preset's values: name=value[,name=value] (see ERAS)")
    ap.add_argument('--seed', type=int, default=1970, help='another seed, another strip of film')
    ap.add_argument('--letters', default=None, help='a timeline whose captions are lettered into the picture')
    ap.add_argument('--inks', default='#12082e,#ffe9a8,#ff8a1e', help='the lettering: outline, top, bottom')
    ap.add_argument('--where', default='bottom', choices=['bottom', 'top', 'top-left'], help='where captions go by default')
    ap.add_argument('--parts', type=int, default=1, help='print N ranges side by side and join them')
    ap.add_argument('--crf', type=int, default=16)
    ap.add_argument('--preset', default='medium')
    ap.add_argument('--stills', default=None, help='write single printed frames into this folder instead of a film')
    ap.add_argument('--at', default='', help='--stills: times in seconds, comma-separated')
    ap.add_argument('--images', default='', help='--stills: rendered pictures instead of a video, comma-separated')
    ap.add_argument('--fps', type=float, default=24.0, help='--images: the film rate their --at times are in')
    ap.add_argument('--range', nargs=2, type=int, metavar=('FIRST', 'LAST'), help='frames FIRST..LAST only (1-based)')
    ap.add_argument('--segment', default=None, help='--range: write the frames alone (no sound) to this file')
    a = ap.parse_args()
    a.overrides = {}
    for item in a.set:
        for kv in split_top(item):
            if '=' in kv:
                name, val = kv.split('=', 1)
                name = name.strip()
                if name not in ERAS[a.era]:
                    raise SystemExit(f'--set {name}: not a print value ({", ".join(ERAS[a.era])})')
                a.overrides[name] = json.loads(val) if val.strip()[:1] == '[' else float(val)
    if a.stills:
        if not (a.images or (a.video and a.at)):
            raise SystemExit('--stills needs a video and --at times, or --images')
        return stills(a)
    if not a.video:
        raise SystemExit('film_print.py needs a video (or --images with --stills)')
    v = probe(a.video)
    if a.range:
        first, last = max(1, a.range[0]), min(v['n'], a.range[1])
        out = a.segment or a.out or str(Path(a.video).with_name(f'{Path(a.video).stem}_print_{first}_{last}.mp4'))
        done = print_range(a, a.video, v, first, last, out, sound=False)
        print(f'[print] frames {first}..{last}: {done} -> {out}', flush=True)
        return 0 if done == last - first + 1 else 1
    out = a.out or str(Path(a.video).with_name(Path(a.video).stem + '_print.mp4'))
    print(f"[print] {a.video}: {v['w']}x{v['h']}, {v['n']} frames at {v['fps']:g} fps; the {a.era} print"
          + (f', lettered from {a.letters}' if a.letters else ''), flush=True)
    if a.parts > 1 and v['n'] >= 2 * a.parts:
        print_in_parts(a, a.video, v, out)
    else:
        t0 = time.time()
        done = print_range(a, a.video, v, 1, v['n'], out, sound=True)
        print(f'[print] {out}: {done} frames, {time.time() - t0:.0f} s', flush=True)


if __name__ == '__main__':
    sys.exit(main())
