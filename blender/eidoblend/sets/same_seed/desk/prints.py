"""eidoblend.sets.same_seed.desk.prints: what is printed, written or shown in the room at 2 a.m. (plain Python: numpy and
Pillow).

    python blender/eidoblend/sets/same_seed/desk/prints.py --out <out>/prints

Each picture is made at its real size (markings at real size, unmirrored; a screen is a designed product showing a
believable picture):
  screen_recording.png  2560 x 1440, the 27-inch screen's own pixels (QHD): somebody's song being recorded at 2 a.m. in
                        a plain multitrack recorder (no maker's name anywhere): the take's vocal lane armed and red, the
                        guitar's lane under it, a click lane; the waveforms; the playhead; and the words being written
                        beside the recording in a plain text window (the light it gives the room is mostly that white).
  lyrics_page.png       1240 x 1754 (A4 at 150 dpi), the page on the desk: a song being written by hand in blue
                        ballpoint, chords over the lines, words struck out and written again, a margin note.
  poster.png            1414 x 2000 (A1's 1 : 1.414), the print in the frame on the back wall: a gig poster in the manner
                        of the late-1960s dance-hall posters (a radiating ground, flat colours, lettering that swells to
                        fill its shape), for an invented band at an invented room.
Nothing here names a real person, band, venue or product. The type is the repository's own OFL fonts
(eidoverse/assets/fonts): Exo 2 for the recorder's interface, Space Mono for its clock, Kalam for the hand, Anton for
the poster's lettering.
"""
import argparse
import math
import os
import random

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: F401
except ImportError:                                             # (Blender's Python has no Pillow: this runs in plain Python)
    np = Image = ImageDraw = ImageFilter = ImageFont = None

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '..'))
FONTS = os.path.join(REPO, 'eidoverse', 'assets', 'fonts')
# the faces the pictures use, by role -> the repository's OFL fonts (file, variable instance)
FACES = {'ui': ('Exo2.ttf', b'Regular'), 'ui_bold': ('Exo2.ttf', b'Bold'), 'mono': ('SpaceMono-Regular.ttf', None),
         'hand': ('Kalam-Regular.ttf', None), 'hand_bold': ('Kalam-Bold.ttf', None), 'poster': ('Anton-Regular.ttf', None)}
OUT = None


def font(name, size):
    path, inst = FACES[name]
    f = ImageFont.truetype(os.path.join(FONTS, path), size)
    if inst:
        f.set_variation_by_name(inst)
    return f


# ----------------------------------------------------------------------------------------------------- the screen
def screen():
    W, H = 2560, 1440
    rnd = random.Random(7)
    im = Image.new('RGB', (W, H), (58, 62, 70))
    d = ImageDraw.Draw(im)
    ui = font('ui', 22)
    uib = font('ui_bold', 24)
    small = font('ui', 18)
    # the title bar and the transport (a recorder's: rewind, play, record, the time, the tempo)
    d.rectangle((0, 0, W, 44), fill=(36, 38, 44))
    d.text((18, 9), 'untitled song 7  -  recording', fill=(200, 204, 210), font=ui)
    d.rectangle((0, 44, W, 128), fill=(48, 51, 58))
    for k, x in enumerate((40, 110, 180, 250)):
        d.rounded_rectangle((x, 62, x + 56, 112), 8, fill=(70, 74, 84))
    d.polygon([(132, 72), (132, 102), (156, 87)], fill=(210, 214, 220))          # play
    d.ellipse((262, 70, 294, 102), fill=(220, 52, 48))                          # record, lit
    d.rectangle((54, 74, 60, 100), fill=(210, 214, 220))
    d.polygon([(62, 87), (88, 72), (88, 102)], fill=(210, 214, 220))            # back to start
    d.rounded_rectangle((340, 60, 700, 114), 6, fill=(22, 24, 28))
    d.text((360, 64), '00:01:47.380', fill=(120, 230, 160), font=font('mono', 40))
    d.text((740, 74), '82 bpm   4/4   key of G', fill=(190, 194, 200), font=ui)
    # the track headers and lanes
    LX, LY = 360, 170
    lanes = [('vocal take 3', (220, 70, 64), True, 0.9), ('vocal take 2', (150, 112, 190), False, 0.7),
             ('acoustic gtr', (70, 160, 200), False, 0.8), ('acoustic gtr DI', (70, 160, 200), False, 0.55), ('click', (120, 126, 136), False, 0.3)]
    LH = 150
    ARR_X1 = 1720
    d.rectangle((0, 128, ARR_X1, H), fill=(44, 47, 54))
    d.rectangle((LX, 128, ARR_X1, 166), fill=(52, 55, 63))
    for b in range(0, 40):
        x = LX + b * 34
        if x > ARR_X1:
            break
        d.line((x, 140 if b % 4 == 0 else 154, x, 166), fill=(140, 144, 152), width=2)
        if b % 4 == 0:
            d.text((x + 4, 134), str(b // 4 + 1), fill=(170, 174, 180), font=small)
    for i, (name, col, armed, amp) in enumerate(lanes):
        y0 = LY + i * (LH + 8)
        d.rectangle((0, y0, LX - 6, y0 + LH), fill=(60, 64, 73))
        d.rectangle((0, y0, 10, y0 + LH), fill=col)
        d.text((24, y0 + 12), name, fill=(220, 222, 226), font=uib)
        for k, lab in enumerate(('M', 'S', 'R')):
            on = (lab == 'R' and armed)
            d.rounded_rectangle((24 + k * 52, y0 + 56, 66 + k * 52, y0 + 92), 5, fill=(220, 52, 48) if on else (80, 84, 94))
            d.text((38 + k * 52, y0 + 60), lab, fill=(240, 240, 240), font=ui)
        d.rounded_rectangle((24, y0 + 110, 330, y0 + 122), 5, fill=(36, 38, 44))
        d.rounded_rectangle((24, y0 + 110, 24 + int(306 * (0.55 + 0.3 * amp)), y0 + 122), 5, fill=(110, 200, 120))
        d.rectangle((LX, y0, ARR_X1, y0 + LH), fill=(50, 53, 61))
        # the clips with their waveforms (the take being recorded runs up to the playhead)
        x = LX + 6
        while x < ARR_X1 - 40:
            w = rnd.randint(260, 620)
            x1 = min(x + w, ARR_X1 - 4)
            if name == 'click':
                x1 = ARR_X1 - 4
            if armed and x1 > 1520:
                x1 = 1520
            cc = tuple(int(c * 0.55 + 30) for c in col)
            d.rounded_rectangle((x, y0 + 6, x1, y0 + LH - 6), 6, fill=cc)
            mid = y0 + LH // 2
            for px in range(x + 2, x1 - 2, 2):
                t = px * 0.013
                env = 0.25 + 0.75 * abs(math.sin(t * 0.9)) * (0.6 + 0.4 * math.sin(t * 0.21))
                a = (LH * 0.42) * amp * env * (0.5 + 0.5 * rnd.random())
                if name == 'click':
                    a = (LH * 0.35) if (px - LX) % 34 < 3 else 2
                d.line((px, mid - a, px, mid + a), fill=tuple(min(255, int(c * 1.25 + 40)) for c in col), width=2)
            if armed and x1 >= 1520:
                break
            x = x1 + rnd.randint(10, 80)
    d.line((1520, 128, 1520, H), fill=(240, 240, 240), width=3)                  # the playhead
    d.polygon([(1508, 128), (1532, 128), (1520, 146)], fill=(240, 240, 240))
    # the words, being written beside the take: a plain text window, white
    TX0 = ARR_X1 + 24
    d.rectangle((ARR_X1, 128, W, H), fill=(36, 38, 44))
    d.rectangle((TX0, 150, W - 24, H - 24), fill=(246, 246, 243))
    d.rectangle((TX0, 150, W - 24, 196), fill=(226, 227, 230))
    d.text((TX0 + 16, 158), 'words.txt', fill=(60, 62, 68), font=ui)
    body = font('ui', 30)
    lines = ['kettle song (2 a.m.)', '', 'the kettle\'s cold, the street is still', 'I count the windows on the hill',
             'one more light and then I\'ll sleep', 'one more line I mean to keep', '', 'chorus:', 'stay up, stay up with me',
             'the night is long and the coffee\'s free', 'sing it once and sing it true', 'nobody\'s up but me and you', '',
             'verse 2 ?', 'the radiator ticks in time', '...']
    y = 222
    for ln in lines:
        d.text((TX0 + 24, y), ln, fill=(30, 32, 36) if ln else (0, 0, 0), font=body)
        y += 44
    d.rectangle((TX0 + 24 + 6, y - 40, TX0 + 27 + 6, y - 6), fill=(30, 32, 36))     # the caret
    # a level meter on the master, at the bottom right of the arrangement
    d.rectangle((0, H - 60, ARR_X1, H), fill=(40, 42, 48))
    d.text((24, H - 46), 'input 1  mic  -12 dB', fill=(190, 194, 200), font=ui)
    d.rounded_rectangle((300, H - 40, 1100, H - 24), 4, fill=(26, 28, 32))
    d.rounded_rectangle((300, H - 40, 820, H - 24), 4, fill=(110, 200, 120))
    d.rounded_rectangle((820, H - 40, 930, H - 24), 4, fill=(220, 200, 80))
    im.save(os.path.join(OUT, 'screen_recording.png'))
    a = np.asarray(im, np.float32) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    print('screen: mean linear', lin.reshape(-1, 3).mean(0).round(4))
    return lin.reshape(-1, 3).mean(0)


# ------------------------------------------------------------------------------------------------------- the page
def page():
    W, H = 1240, 1754
    rnd = random.Random(3)
    im = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    hand = font('hand', 46)
    handb = font('hand', 58)
    chord = font('hand_bold', 32)
    ink = (28, 44, 120)
    # faint rules of a pad's page (the page was torn from a ruled pad: its blue lines, the red margin)
    for k in range(0, 31):
        y = 170 + k * 52
        d.line((0, y, W, y), fill=(196, 214, 236), width=2)
    d.line((150, 0, 150, H), fill=(236, 170, 170), width=2)
    lines = [('kettle song', None, True), ('', None, False),
             ('the kettle\'s cold, the street is still', 'G              Em', False),
             ('I count the windows on the hill', 'C                D', False),
             ('one more light and then I\'ll sleep', 'G              Em', False),
             ('one more line I mean to keep', 'C        D        G', False), ('', None, False),
             ('stay up, stay up with me', 'C           G', False),
             ("the night is long and the ~~tea's~~ coffee's free", 'D              Em', False),
             ('sing it once and sing it true', 'C           G', False),
             ('nobody\'s up but me and you', 'D                G', False), ('', None, False),
             ('the radiator ticks in time', 'G              Em', False),
             ('~~my head is~~ the clock says two', None, False)]
    y = 140
    for text, ch, title in lines:
        if title:
            d.text((190, y - 20), text, fill=ink, font=handb)
            d.line((190, y + 50, 560, y + 46), fill=ink, width=3)
            y += 104
            continue
        if not text:
            y += 52
            continue
        if ch:
            d.text((200 + rnd.randint(-4, 4), y - 4), ch, fill=(150, 40, 40), font=chord)
            y += 52
        x = 190 + rnd.randint(-6, 6)
        parts = text.split('~~')
        for k, part in enumerate(parts):
            if not part:
                continue
            w = d.textlength(part, font=hand)
            d.text((x, y - 14 + rnd.randint(-3, 3)), part, fill=ink, font=hand)
            if k % 2 == 1:                                     # struck out
                d.line((x - 4, y + 14, x + w + 4, y + 8), fill=ink, width=4)
            x += w + 12
        y += 52
    d.text((860, 1520), 'capo 2?', fill=ink, font=hand)
    d.ellipse((840, 1500, 1060, 1590), outline=ink, width=3)
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im.save(os.path.join(OUT, 'lyrics_page.png'))
    print('page written')


# ----------------------------------------------------------------------------------------------------- the poster
def poster():
    W, H = 1414, 2000
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W * 0.5, H * 0.42
    r = np.hypot(xx - cx, yy - cy)
    th = np.arctan2(yy - cy, xx - cx)
    # the ground: rays and ripples, four flat inks (the posters were printed in a few flat colours)
    f = np.sin(th * 18.0 + np.sin(r * 0.012) * 2.2) + 0.8 * np.sin(r * 0.045 - th * 2.0)
    inks = np.array([(232, 92, 34), (196, 28, 108), (78, 30, 120), (246, 190, 40)], np.float32)
    band = np.digitize(f, [-0.9, 0.1, 1.0])
    img = inks[band]
    sun = r < 230
    img[sun] = (250, 226, 120)
    img[(r > 230) & (r < 252)] = (78, 30, 120)
    # the lettering, swelling to fill its band (drawn flat, then bent by a wave along its length)

    def lettering(text, size, h_box, col, y0, wave=0.18):
        fnt = font('poster', size)
        m = Image.new('L', (W, h_box), 0)
        dm = ImageDraw.Draw(m)
        tw = dm.textlength(text, font=fnt)
        dm.text(((W - tw) / 2, h_box * 0.08), text, fill=255, font=fnt)
        a = np.asarray(m, np.float32) / 255.0
        ys, xs = np.mgrid[0:h_box, 0:W].astype(np.float32)
        u = (xs - W / 2) / (W / 2)
        sw = 1.0 + wave * np.cos(u * math.pi)                    # taller in the middle: the letters swell
        src_y = (ys - h_box / 2) / sw + h_box / 2 + 18.0 * np.sin(u * math.pi * 1.5)
        src_y = np.clip(src_y, 0, h_box - 1).astype(np.int32)
        b = a[src_y, xs.astype(np.int32)]
        reg = img[y0:y0 + h_box]
        mask = b[..., None] > 0.5
        edge = (b[..., None] > 0.15) & ~mask
        reg[:] = np.where(mask, np.array(col, np.float32), np.where(edge, np.array((30, 12, 40), np.float32), reg))

    lettering('THE KETTLE', 230, 300, (250, 240, 210), 60)
    lettering('ORCHARD', 300, 380, (250, 240, 210), 1250, 0.22)
    out = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(out)
    small = font('poster', 64)
    for k, ln in enumerate(('FRIDAY & SATURDAY', 'THE LANTERN ROOM  -  DOORS 8')):
        tw = d.textlength(ln, font=small)
        d.text(((W - tw) / 2, 1690 + k * 90), ln, fill=(30, 12, 40), font=small)
    out.save(os.path.join(OUT, 'poster.png'))
    print('poster written')


def main(argv=None):
    global OUT
    ap = argparse.ArgumentParser(description="the desk room's pictures (see the module doc)")
    ap.add_argument('--out', required=True)
    OUT = os.path.abspath(ap.parse_args(argv).out)
    os.makedirs(OUT, exist_ok=True)
    screen()
    page()
    poster()
    print('[desk prints]', OUT, sorted(os.listdir(OUT)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
