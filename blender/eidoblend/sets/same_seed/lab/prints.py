"""eidoblend.sets.same_seed.lab.prints: the lab's pictures at their real size (plain Python: numpy and Pillow).

    python blender/eidoblend/sets/same_seed/lab/prints.py --out <out>/prints

Markings belong in the material, not in floating geometry: each picture is drawn at a known number of pixels per
millimetre of the thing it lies on, unmirrored, and the look lays it there through a UV of its own.
  screen_document.png      the screen's picture (598 x 348 mm at 2.6 px/mm): a document open in an editor, light theme
  whiteboard_ghosts.png    the board (1990 x 990 mm at 1 px/mm): what old marker leaves after wiping. R: dark (black and
                           blue) marker's ghost, G: red marker's ghost, B: the eraser's broad smear. Words as cursive
                           strokes, a diagram's boxes and arrows, all wiped many times (the board is in use, kept clean)
  clipboard_form.png       the sheet on the clipboard (210 x 297 mm at 4 px/mm): a printed form, answers in blue ink
  notice.png               the sheet under the magnets (210 x 297 mm at 3 px/mm): a printed notice
No real text: lines of words are drawn as strokes at the size of words.
"""
import argparse
import math
import os
import random

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:                                             # (Blender's Python has no Pillow: this runs in plain Python)
    Image = ImageDraw = ImageFilter = None


def scribble(d, x, y, w, h, rnd, width=3, fill=255, slant=0.25):
    """a handwritten word: a run of small loops and humps along a baseline (x, y), w long, h tall"""
    pts = []
    t = 0.0
    while t < w:
        k = rnd.random()
        amp = h * (0.45 + 0.55 * rnd.random()) * (1.6 if k > 0.88 else 1.0)
        step = h * (0.35 + 0.3 * rnd.random())
        for s in range(6):
            a = s / 5.0
            px = x + t + step * a + slant * amp * math.sin(math.pi * a)
            py = y - amp * math.sin(math.pi * a) ** 1.3
            pts.append((px, py))
        t += step
    d.line(pts, fill=fill, width=width, joint='curve')


def screen_document(out):
    W, H = 1556, 905                                            # 598 x 348 mm at 2.6 px/mm
    im = Image.new('RGB', (W, H), (236, 238, 241))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 34), fill=(222, 225, 229))           # the title bar
    for i in range(3):
        d.ellipse((14 + 22 * i, 11, 26 + 22 * i, 23), fill=(176, 181, 188))
    d.rectangle((0, 34, W, 74), fill=(246, 247, 249))           # the toolbar
    for i in range(14):
        d.rounded_rectangle((18 + 40 * i, 44, 44 + 40 * i, 64), 4, fill=(205, 209, 215))
    d.rectangle((0, 74, 250, H), fill=(243, 244, 246))          # the files down the side
    rnd = random.Random(7)
    for i in range(16):
        y = 96 + 34 * i
        d.rounded_rectangle((20, y, 20 + 18, y + 14), 3, fill=(190, 196, 204))
        d.rounded_rectangle((48, y + 2, 48 + rnd.randint(90, 180), y + 12), 4, fill=(150, 156, 164) if i != 3 else (66, 118, 196))
    px0, px1 = 420, 1240                                        # the page
    d.rectangle((px0, 92, px1, H), fill=(255, 255, 255))
    d.rounded_rectangle((px0 + 60, 140, px0 + 470, 166), 6, fill=(60, 64, 70))   # its heading
    y = 200
    for para in range(5):
        n = rnd.randint(3, 6)
        for li in range(n):
            x = px0 + 60
            end = px1 - 60 if li < n - 1 else px0 + 60 + rnd.randint(150, 600)
            while x < end - 30:
                wd = rnd.randint(28, 96)
                d.rounded_rectangle((x, y, min(x + wd, end), y + 9), 4, fill=(118, 123, 130))
                x += wd + 12
            y += 22
        y += 20
        if para == 1:                                            # a small figure in the text
            d.rectangle((px0 + 60, y, px0 + 420, y + 150), outline=(190, 194, 200), width=2)
            vals = [rnd.random() for _ in range(12)]
            for k, v in enumerate(vals):
                d.rectangle((px0 + 80 + 28 * k, y + 140 - int(110 * v), px0 + 96 + 28 * k, y + 140), fill=(102, 150, 214))
            y += 175
    d.line((px0 + 60, 232, px0 + 60, 252), fill=(30, 30, 30), width=2)          # the cursor
    im.save(os.path.join(out, 'screen_document.png'))


def whiteboard_ghosts(out):
    W, H = 1990, 990                                            # 1 px a millimetre
    rnd = random.Random(11)
    dark = Image.new('L', (W, H), 0)
    red = Image.new('L', (W, H), 0)
    for layer in range(5):                                      # five old sessions, each wiped
        lay = Image.new('L', (W, H), 0)
        dl = ImageDraw.Draw(lay)
        tgt = rnd.choice(('dark', 'dark', 'dark', 'red'))
        x0, y0 = rnd.randint(60, 900), rnd.randint(80, 420)
        for line in range(rnd.randint(3, 8)):                   # lines of words, 30-45 mm tall
            x, y = x0, y0 + line * rnd.randint(70, 95)
            if y > H - 60:
                break
            for word in range(rnd.randint(2, 7)):
                wl = rnd.randint(60, 230)
                if x + wl > W - 40:
                    break
                scribble(dl, x, y, wl, rnd.randint(22, 38), rnd, width=rnd.choice((3, 4)), fill=255)
                x += wl + rnd.randint(25, 50)
        if rnd.random() < 0.7:                                  # a diagram: boxes and arrows
            bx, by = rnd.randint(900, 1600), rnd.randint(120, 600)
            for b in range(rnd.randint(2, 4)):
                cx, cy = bx + rnd.randint(-250, 250), by + rnd.randint(-120, 260)
                w_, h_ = rnd.randint(140, 260), rnd.randint(70, 120)
                dl.rounded_rectangle((cx, cy, cx + w_, cy + h_), 12, outline=255, width=4)
                dl.line((cx + w_, cy + h_ // 2, cx + w_ + rnd.randint(60, 160), cy + h_ // 2 + rnd.randint(-80, 80)), fill=255, width=4)
        # the wiping: broad passes of the eraser leave a little of the ink, more at the passes' edges
        keep = np.full((H, W), 0.0, np.float32)
        yy = np.arange(H)[:, None].astype(np.float32)
        for p in range(rnd.randint(6, 12)):
            c = rnd.uniform(0, H)
            hw = rnd.uniform(40, 70)
            tilt = rnd.uniform(-0.08, 0.08)
            xs = np.arange(W)[None, :].astype(np.float32)
            dy = np.abs(yy - (c + tilt * (xs - W / 2)))
            band = np.clip(1.0 - dy / hw, 0.0, 1.0)
            keep = np.maximum(keep, band)
        resid = 0.05 + 0.25 * (1.0 - keep) + 0.05 * np.random.default_rng(layer).random((H, W)).astype(np.float32)
        lay = np.asarray(lay.filter(ImageFilter.GaussianBlur(1.6)), np.float32) / 255.0 * resid * rnd.uniform(0.5, 1.0)
        tgt_im = dark if tgt == 'dark' else red
        a = np.maximum(np.asarray(tgt_im, np.float32) / 255.0, lay)
        (dark if tgt == 'dark' else red).paste(Image.fromarray((a * 255).astype(np.uint8)))
    smear = np.zeros((H, W), np.float32)                        # the eraser's grey film, broad and soft
    for p in range(26):
        c, hw = rnd.uniform(0, H), rnd.uniform(50, 80)
        x0, x1 = sorted((rnd.uniform(0, W), rnd.uniform(0, W)))
        xs = np.arange(W)[None, :].astype(np.float32)
        yy = np.arange(H)[:, None].astype(np.float32)
        band = np.clip(1.0 - np.abs(yy - c) / hw, 0, 1) * ((xs > x0) & (xs < x1))
        smear = np.maximum(smear, band * rnd.uniform(0.2, 0.6))
    smear = np.asarray(Image.fromarray((smear * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(12)), np.float32) / 255.0
    rgb = np.stack([np.asarray(dark, np.float32) / 255.0, np.asarray(red, np.float32) / 255.0, smear], -1)
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8), 'RGB').save(os.path.join(out, 'whiteboard_ghosts.png'))


def clipboard_form(out):
    W, H = 840, 1188                                            # 210 x 297 mm at 4 px/mm
    im = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    rnd = random.Random(23)
    d.rectangle((60, 60, W - 60, 110), fill=(70, 74, 82))       # the form's head
    y = 160
    for q in range(9):
        x = 60
        for w in range(rnd.randint(3, 7)):                      # a question, printed
            wd = rnd.randint(30, 90)
            d.rounded_rectangle((x, y, x + wd, y + 10), 3, fill=(110, 112, 118))
            x += wd + 12
        y += 30
        for k in range(2):                                      # the ruled answer lines
            d.line((60, y + 26 * (k + 1), W - 60, y + 26 * (k + 1)), fill=(190, 192, 198), width=2)
        if q < 5:                                               # answered so far, in blue ink
            for k in range(2 if q < 4 else 1):
                x = 70
                for w in range(rnd.randint(2, 6)):
                    wl = rnd.randint(40, 120)
                    if x + wl > W - 80:
                        break
                    scribble(d, x, y + 26 * (k + 1) - 3, wl, rnd.randint(9, 14), rnd, width=2, fill=(30, 52, 140))
                    x += wl + rnd.randint(10, 20)
        y += 80
    im.save(os.path.join(out, 'clipboard_form.png'))


def notice(out):
    W, H = 630, 891                                             # 210 x 297 mm at 3 px/mm
    im = Image.new('RGB', (W, H), (252, 252, 250))
    d = ImageDraw.Draw(im)
    rnd = random.Random(31)
    d.rectangle((0, 0, W, 90), fill=(46, 112, 82))
    d.rounded_rectangle((40, 30, 360, 60), 6, fill=(240, 244, 240))
    y = 130
    for row in range(14):
        d.rounded_rectangle((40, y, 40 + rnd.randint(80, 160), y + 12), 4, fill=(80, 84, 90))
        d.rounded_rectangle((260, y, 260 + rnd.randint(120, 300), y + 12), 4, fill=(140, 144, 150))
        d.line((40, y + 30, W - 40, y + 30), fill=(215, 217, 220), width=1)
        y += 48
    im.save(os.path.join(out, 'notice.png'))


def main(argv=None):
    ap = argparse.ArgumentParser(description="the lab's pictures (see the module doc)")
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    screen_document(a.out)
    whiteboard_ghosts(a.out)
    clipboard_form(a.out)
    notice(a.out)
    print('[lab prints]', a.out, sorted(os.listdir(a.out)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
