"""eidoblend.sets.same_seed.kitchen.prints: what is printed or written in the kitchen, drawn at real size (plain Python:
numpy and Pillow).

    python blender/eidoblend/sets/same_seed/kitchen/prints.py --out <out>/prints

Markings belong in the material at real size, unmirrored; each sheet here is its paper's own size at 8 px/mm (enough
for any of the room's lenses), laid on its geometry by a planar UV the look makes from the sheet's own rectangle. Ink
only: the paper's colour, grain and roughness come from the CC0 paper set in the material, this picture multiplies over
it. No people anywhere: the child's drawing is a house, a tree, the sun, a pot with a plant in it.
  worksheet.png      the homework being read: two-digit sums, some answered in pencil (letter, 216 x 279)
  spelling.png       the finished sheet under it: a spelling list on primary-ruled paper, in pencil
  notebook.png       the composition book's cover: black-and-white marbling (from the CC0 Marble016 photograph,
                     desaturated and pushed to the cover's contrast) and its white label
  drawing.png        on the fridge, crayon (landscape letter)
  letter.png         on the fridge, a school's printed letter (a made-up school; no badge or logo)
  list.png           on the fridge, a shopping list in ballpoint on a narrow pad sheet (105 x 190)
  dial.png           the clock's face (200 across): numerals, minute marks
The type is the repository's own OFL fonts (eidoverse/assets/fonts): Exo 2 for print, Old Standard for a serif, Kalam
for the hands. Marble016 is read from the shared library (eidoverse/assets/cache/, or EIDO_ASSET_CACHE), fetched once
by fetch_texture.py when it is not there.
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps  # noqa: F401
except ImportError:                                             # (Blender's Python has no Pillow: this runs in plain Python)
    Image = ImageDraw = ImageFilter = ImageFont = ImageOps = None

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '..'))
FONTS = os.path.join(REPO, 'eidoverse', 'assets', 'fonts')
# the faces the pictures use, by role -> the repository's OFL fonts (file, variable instance)
FACES = {'print': ('Exo2.ttf', b'Regular'), 'print_bold': ('Exo2.ttf', b'Bold'), 'serif': ('OldStandard-Regular.ttf', None),
         'hand': ('Kalam-Regular.ttf', None), 'hand_bold': ('Kalam-Bold.ttf', None)}
PX = 8                                                          # px per mm
OUT = None
R = random.Random(25)


def font(name, size_mm):
    path, inst = FACES[name]
    f = ImageFont.truetype(os.path.join(FONTS, path), int(size_mm * PX))
    if inst:
        f.set_variation_by_name(inst)
    return f


def texture(set_id, res, key='diff'):
    """a map of a CC0 set in the shared library, fetched once when it is not there"""
    base = os.environ.get('EIDO_ASSET_CACHE') or os.path.join(REPO, 'eidoverse', 'assets', 'cache')
    d = os.path.join(base, 'textures', f'{set_id}_{res}')
    js = os.path.join(d, 'tex_urls.json')
    if not os.path.isfile(js):
        if os.environ.get('EIDO_NO_FETCH') == '1':
            raise FileNotFoundError(f'{set_id} ({res}) is not in the library; fetch it with: python fetch_texture.py {set_id} {res} --cache')
        subprocess.run([sys.executable, os.path.join(REPO, 'fetch_texture.py'), set_id, res, '--cache'], cwd=REPO,
                       creationflags=0x08000000 if os.name == 'nt' else 0)
    with open(js, encoding='utf-8') as f:
        return os.path.join(d, os.path.basename(str(json.load(f)[key]).replace('\\', '/')))


def sheet(w_mm, h_mm):
    return Image.new('RGB', (int(w_mm * PX), int(h_mm * PX)), (255, 255, 255))


def hand(im, xy, text, size_mm, ink, jitter=0.35, fnt='hand', slant=0.0):
    """handwriting on the picture im: each letter its own size, place and lean (a child's or a hurried adult's hand)"""
    x, y = xy
    for ch in text:
        s = size_mm * (1.0 + R.uniform(-0.08, 0.1))
        f = font(fnt, s)
        g = Image.new('L', (int(s * PX * 1.6) + 8, int(s * PX * 1.6) + 8), 0)
        ImageDraw.Draw(g).text((4, 4), ch, font=f, fill=255)
        g = g.rotate(R.uniform(-6, 6) + slant, resample=Image.BICUBIC, expand=False)
        dy = R.uniform(-jitter, jitter) * PX
        im.paste(Image.new('RGB', g.size, ink), (int(x), int(y + dy)), g)
        x += f.getlength(ch) * (0.92 + R.uniform(-0.04, 0.06))
    return x


def pencil_grain(im, strength=0.18):
    """graphite lies on the paper's tooth: break the strokes up a little"""
    n = Image.effect_noise(im.size, 64).point(lambda v: 255 if v > 118 else int(255 * (1 - strength)))
    white = Image.new('RGB', im.size, (255, 255, 255))
    ink = ImageOps.invert(im.convert('L'))
    mask = Image.composite(ink, Image.new('L', im.size, 0), n)
    return Image.composite(im, white, mask)


# ------------------------------------------------------------------ the worksheet (the one he reads)
def worksheet():
    im = sheet(216, 279)
    d = ImageDraw.Draw(im)
    k = (40, 40, 44)
    d.text((22 * PX, 16 * PX), 'Name', font=font('print', 4.2), fill=k)
    d.line([(36 * PX, 21 * PX), (110 * PX, 21 * PX)], fill=k, width=3)
    d.text((122 * PX, 16 * PX), 'Date', font=font('print', 4.2), fill=k)
    d.line([(135 * PX, 21 * PX), (192 * PX, 21 * PX)], fill=k, width=3)
    d.text((22 * PX, 30 * PX), 'Adding Two-Digit Numbers', font=font('print_bold', 7.5), fill=k)
    d.text((22 * PX, 42 * PX), 'Add. Show your work. Remember to carry!', font=font('print', 4.0), fill=k)
    pairs = [(R.randint(12, 69), R.randint(11, 29)) for _ in range(16)]
    gx, gy = (30, 76, 122, 168), (62, 110, 158, 206)
    answered = 11                                                # the child stopped at the twelfth
    for i, (a, b) in enumerate(pairs):
        cx, cy = gx[i % 4], gy[i // 4]
        f = font('print', 7.0)
        d.text((cx * PX - 2, cy * PX), f'{a:>2}', font=f, fill=k, anchor='la')
        d.text(((cx - 9) * PX, (cy + 9) * PX), '+', font=f, fill=k)
        d.text((cx * PX - 2, (cy + 9) * PX), f'{b:>2}', font=f, fill=k)
        d.line([((cx - 10) * PX, (cy + 19.5) * PX), ((cx + 13) * PX, (cy + 19.5) * PX)], fill=k, width=4)
        d.text(((cx - 13) * PX, (cy - 6) * PX), f'{i + 1}.', font=font('print', 3.6), fill=k)
    import numpy as np
    pen = Image.new('RGB', im.size, (255, 255, 255))
    dp = ImageDraw.Draw(pen)
    hand(pen, (38 * PX, 13 * PX), 'Sam', 6.5, (70, 70, 74))
    hand(pen, (139 * PX, 13.5 * PX), 'Nov 25', 5.0, (70, 70, 74))
    for i, (a, b) in enumerate(pairs[:answered]):
        cx, cy = gx[i % 4], gy[i // 4]
        s = a + b if i != 6 else a + b - 10                     # one sum got wrong (the carried one forgotten)
        hand(pen, ((cx - 3) * PX, (cy + 21) * PX), str(s), 7.0, (62, 62, 68))
        if (a % 10) + (b % 10) >= 10 and i != 6:
            hand(pen, ((cx - 4) * PX, (cy - 5.5) * PX), '1', 3.6, (80, 80, 86))
    dp.ellipse([((gx[2] - 14) * PX, (gy[1] + 18) * PX), ((gx[2] + 18) * PX, (gy[1] + 33) * PX)], outline=(96, 96, 104), width=3)   # (circled, rubbed half out)
    pen = pencil_grain(pen)
    im = Image.fromarray(np.minimum(np.asarray(im), np.asarray(pen)))   # (graphite over the print: the darker wins)
    im.save(os.path.join(OUT, 'worksheet.png'))


# ------------------------------------------------------------------ the spelling sheet (done, under it)
def spelling():
    im = sheet(216, 279)
    d = ImageDraw.Draw(im)
    d.line([(30 * PX, 0), (30 * PX, 279 * PX)], fill=(232, 150, 150), width=4)
    for r in range(11):
        y0 = 40 + r * 21.0
        d.line([(0, y0 * PX), (216 * PX, y0 * PX)], fill=(150, 175, 220), width=4)
        for x in range(0, 216, 6):
            d.line([(x * PX, (y0 + 7) * PX), ((x + 3) * PX, (y0 + 7) * PX)], fill=(170, 190, 225), width=3)
        d.line([(0, (y0 + 14) * PX), (216 * PX, (y0 + 14) * PX)], fill=(150, 175, 220), width=4)
    d.text((34 * PX, 18 * PX), 'Spelling - Week 12', font=font('print_bold', 5.5), fill=(40, 40, 44))
    pen = Image.new('RGB', im.size, (255, 255, 255))
    for r, w in enumerate(('seed', 'sun', 'rain', 'grow', 'leaf', 'plant', 'water', 'root', 'light')):
        hand(pen, (36 * PX, (39 + r * 21.0) * PX), f'{r + 1}. {w}', 11.0, (66, 66, 72), jitter=0.6)
    pen = pencil_grain(pen)
    import numpy as np
    im = Image.fromarray(np.minimum(np.asarray(im), np.asarray(pen)))
    im.save(os.path.join(OUT, 'spelling.png'))


# ------------------------------------------------------------------ the composition book's cover
def notebook():
    import numpy as np
    src = Image.open(texture('Marble016', '2k')).convert('L')
    src = src.resize((190 * PX, 247 * PX), Image.BICUBIC)
    a = np.asarray(src, np.float32) / 255.0
    a = (a - a.mean()) / (a.std() + 1e-6)
    a = 1.0 / (1.0 + np.exp(-2.6 * (a - 0.15)))                 # the cover's black-and-white marbling
    im = Image.fromarray((a * 235 + 8).astype(np.uint8)).convert('RGB')
    d = ImageDraw.Draw(im)
    lx0, ly0, lx1, ly1 = 52 * PX, 30 * PX, 160 * PX, 92 * PX
    d.rounded_rectangle([lx0, ly0, lx1, ly1], radius=6 * PX, fill=(250, 250, 246), outline=(20, 20, 20), width=6)
    d.text(((lx0 + lx1) // 2, ly0 + 7 * PX), 'COMPOSITION', font=font('print_bold', 8.0), fill=(20, 20, 20), anchor='ma')
    for i, lab in enumerate(('NAME', 'SUBJECT')):
        y = ly0 + (30 + 15 * i) * PX
        d.text((lx0 + 6 * PX, y - 4 * PX), lab, font=font('print', 3.2), fill=(30, 30, 30))
        d.line([(lx0 + 24 * PX, y), (lx1 - 6 * PX, y)], fill=(30, 30, 30), width=3)
    hand(im, (lx0 + 26 * PX, ly0 + 22 * PX), 'Sam B.', 7.0, (40, 40, 110))
    hand(im, (lx0 + 30 * PX, ly0 + 37 * PX), 'Math', 7.0, (40, 40, 110))
    im.save(os.path.join(OUT, 'notebook.png'))


# ------------------------------------------------------------------ on the fridge: a crayon drawing
def crayon(d, pts, col, width_mm=2.6, passes=3):
    for _ in range(passes):
        q = [(x * PX + R.uniform(-0.6, 0.6) * PX, y * PX + R.uniform(-0.6, 0.6) * PX) for x, y in pts]
        d.line(q, fill=col, width=int(width_mm * PX * R.uniform(0.7, 1.0)), joint='curve')


def fill_scribble(d, x0, y0, x1, y1, col, step=2.2, ang=0.5):
    """a crayon fill: back-and-forth strokes, not reaching the edges everywhere"""
    t = y0
    while t < y1:
        crayon(d, [(x0 + R.uniform(0, 3), t), (x1 - R.uniform(0, 3), t + ang * (x1 - x0) * 0.05)], col, 2.2, 1)
        t += step + R.uniform(-0.5, 0.5)


def drawing():
    im = sheet(279, 216)
    d = ImageDraw.Draw(im, 'RGBA')
    fill_scribble(d, 8, 170, 271, 206, (70, 160, 60, 200), 2.6)                     # grass
    for x in range(10, 270, 9):
        crayon(d, [(x, 172), (x + 2, 160 + R.uniform(-4, 3))], (60, 140, 50, 230), 1.6, 1)
    crayon(d, [(30 + 22 * math.cos(a / 12 * 2 * math.pi), 36 + 22 * math.sin(a / 12 * 2 * math.pi)) for a in range(13)], (240, 190, 30, 255), 3.0)
    fill_scribble(d, 14, 20, 46, 52, (250, 205, 40, 150), 2.4)
    for a in range(10):                                                              # the sun's rays
        t = a / 10 * 2 * math.pi + 0.3
        crayon(d, [(30 + 28 * math.cos(t), 36 + 28 * math.sin(t)), (30 + 40 * math.cos(t), 36 + 40 * math.sin(t))], (240, 180, 30, 255), 2.2, 2)
    hx0, hy0, hx1, hy1 = 92, 96, 176, 172                                            # the house
    fill_scribble(d, hx0, hy0, hx1, hy1, (230, 120, 60, 150), 2.8)
    crayon(d, [(hx0, hy0), (hx1, hy0), (hx1, hy1), (hx0, hy1), (hx0, hy0)], (180, 60, 40, 255), 2.4)
    crayon(d, [(hx0 - 8, hy0 + 2), ((hx0 + hx1) / 2, 52), (hx1 + 8, hy0 + 2), (hx0 - 8, hy0 + 2)], (200, 40, 40, 255), 2.8)
    fill_scribble(d, hx0 + 4, 62, hx1 - 4, hy0 - 2, (210, 50, 50, 140), 2.6)
    crayon(d, [(124, 172), (124, 136), (144, 136), (144, 172)], (110, 70, 40, 255), 2.4)
    crayon(d, [(100, 108), (118, 108), (118, 124), (100, 124), (100, 108)], (50, 110, 200, 255), 2.0)
    crayon(d, [(150, 108), (168, 108), (168, 124), (150, 124), (150, 108)], (50, 110, 200, 255), 2.0)
    crayon(d, [(220, 172), (222, 120)], (120, 75, 40, 255), 4.0)                     # the tree
    for k in range(7):
        a = k / 7 * 2 * math.pi
        crayon(d, [(221 + 20 * math.cos(a), 104 + 16 * math.sin(a)), (221 + 24 * math.cos(a + 0.9), 104 + 19 * math.sin(a + 0.9))], (40, 130, 50, 255), 3.0, 2)
    fill_scribble(d, 203, 90, 241, 118, (50, 150, 60, 140), 2.4)
    crayon(d, [(56, 160), (74, 160), (70, 174), (60, 174), (56, 160)], (190, 100, 60, 255), 2.2)   # a pot with a plant
    for k in range(5):
        crayon(d, [(65, 160), (58 + k * 4, 144 - (k % 2) * 4)], (50, 150, 60, 255), 1.6, 1)
        crayon(d, [(58 + k * 4, 144 - (k % 2) * 4), (55 + k * 4, 140 - (k % 2) * 4)], (60, 170, 70, 255), 3.0, 1)
    for x in range(70, 260, 34):                                                     # sky strokes
        crayon(d, [(x, 14 + R.uniform(-3, 3)), (x + 22, 12 + R.uniform(-3, 3))], (80, 150, 230, 200), 2.0, 2)
    hand(im, (196 * PX, 186 * PX), 'SAM', 9.0, (40, 60, 160), fnt='hand_bold')
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im.save(os.path.join(OUT, 'drawing.png'))


# ------------------------------------------------------------------ on the fridge: a school letter
def letter():
    im = sheet(216, 279)
    d = ImageDraw.Draw(im)
    k = (30, 30, 34)
    d.text((108 * PX, 18 * PX), 'Hillside Elementary School', font=font('print_bold', 6.0), fill=k, anchor='ma')
    d.text((108 * PX, 27 * PX), 'Family Newsletter  -  November', font=font('print', 4.0), fill=k, anchor='ma')
    d.line([(20 * PX, 35 * PX), (196 * PX, 35 * PX)], fill=k, width=3)
    words = ('our class the children have been learning about seeds and how plants grow we planted beans in cups '
             'by the window please send an empty jar on Monday thank you for reading with your child every night '
             'the winter concert is on December twelfth at six in the gym all families are welcome').split()
    y = 44.0
    for para in range(5):
        d.text((20 * PX, y * PX), ('Dear Families,', 'Reading', 'Science Corner', 'Reminders', 'Winter Concert')[para], font=font('print_bold', 4.2), fill=k)
        y += 7.0
        for line in range(R.randint(3, 5)):
            txt = ' '.join(R.choice(words) for _ in range(R.randint(9, 12))).capitalize()
            d.text((20 * PX, y * PX), txt, font=font('serif', 4.0), fill=k)
            y += 5.6
        y += 4.0
    d.line([(20 * PX, 250 * PX), (110 * PX, 250 * PX)], fill=k, width=3)
    d.text((20 * PX, 252 * PX), 'Parent signature', font=font('print', 3.4), fill=k)
    im.save(os.path.join(OUT, 'letter.png'))


# ------------------------------------------------------------------ on the fridge: the shopping list
def shopping():
    im = sheet(105, 190)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 105 * PX, 14 * PX], fill=(250, 236, 150))
    for r in range(13):
        y = (24 + r * 12.5) * PX
        d.line([(4 * PX, y), (101 * PX, y)], fill=(170, 200, 225), width=2)
    for r, w in enumerate(('milk', 'bread', 'eggs', 'apples', 'rice', 'dish soap', 'basil?', 'pencils')):
        hand(im, (8 * PX, (13.5 + r * 12.5) * PX), w, 8.0, (30, 50, 140), jitter=0.4, slant=-4)
    d.line([(8 * PX, 37.0 * PX), (40 * PX, 36.0 * PX)], fill=(30, 50, 140), width=4)    # (milk: got)
    im.save(os.path.join(OUT, 'list.png'))


# ------------------------------------------------------------------ the clock's face
def dial():
    S = 200
    im = sheet(S, S)
    d = ImageDraw.Draw(im)
    c = S * PX / 2
    for m in range(60):
        a = math.radians(m * 6.0)
        r0 = (S / 2 - 6.0) * PX
        r1 = r0 - (7.0 if m % 5 == 0 else 3.0) * PX
        d.line([(c + r0 * math.sin(a), c - r0 * math.cos(a)), (c + r1 * math.sin(a), c - r1 * math.cos(a))], fill=(18, 18, 18), width=int((1.6 if m % 5 == 0 else 0.7) * PX))
    for h in range(1, 13):
        a = math.radians(h * 30.0)
        r = (S / 2 - 21.0) * PX
        d.text((c + r * math.sin(a), c - r * math.cos(a)), str(h), font=font('print', 15.0), fill=(18, 18, 18), anchor='mm')
    im.save(os.path.join(OUT, 'dial.png'))


def main(argv=None):
    global OUT
    ap = argparse.ArgumentParser(description="the kitchen's pictures (see the module doc)")
    ap.add_argument('--out', required=True)
    OUT = os.path.abspath(ap.parse_args(argv).out)
    os.makedirs(OUT, exist_ok=True)
    for fn in (worksheet, spelling, notebook, drawing, letter, shopping, dial):
        fn()
    print('[kitchen prints]', OUT, sorted(os.listdir(OUT)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
