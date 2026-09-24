"""era_logos.py — stylized homage renditions of the era logos, drawn from scratch with PIL (no copied image files).
Each function draws into an RGBA PIL image inside a box (x0, y0, x1, y1) in pixels. Skye (09-23): era logos are
welcome as homages that tell the history."""
import math
from PIL import Image, ImageDraw, ImageFont

FONTS = 'C:/Windows/Fonts/'


def font(name, size):
    return ImageFont.truetype(FONTS + name, max(4, int(size)))


def _paste_mask(im, color_img, mask, x0, y0):
    im.alpha_composite(Image.composite(color_img, Image.new('RGBA', color_img.size, (0, 0, 0, 0)), mask), (int(x0), int(y0)))


# ── Texas Instruments: the state outline with a lowercase "ti" inside ─────────────────────────────────────────
TEXAS = [(0.33, 0.0), (0.51, 0.0), (0.51, 0.27), (0.60, 0.30), (0.70, 0.31), (0.80, 0.33), (0.90, 0.34), (0.97, 0.36),
         (0.96, 0.50), (0.97, 0.63), (0.93, 0.70), (0.86, 0.76), (0.78, 0.82), (0.73, 0.88), (0.70, 0.95), (0.67, 1.0),
         (0.60, 0.97), (0.54, 0.89), (0.48, 0.80), (0.42, 0.72), (0.36, 0.66), (0.30, 0.63), (0.24, 0.57), (0.18, 0.49),
         (0.12, 0.43), (0.06, 0.38), (0.0, 0.33), (0.02, 0.30), (0.33, 0.30)]


def ti_mark(im, box, color=(214, 58, 28, 255), outline=True):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    dr = ImageDraw.Draw(im)
    pts = [(x0 + u * w, y0 + v * h) for (u, v) in TEXAS]
    lw = max(2, int(w * 0.045))
    if outline:
        dr.line(pts + [pts[0]], fill=color, width=lw, joint='curve')
    # "ti": a t with a curved foot and an i whose dot is a ball, set in the middle of the state
    cx, cy, s = x0 + w * 0.56, y0 + h * 0.56, w * 0.26
    st = max(2, int(s * 0.22))
    dr.line([(cx - s * 0.45, cy - s * 0.55), (cx - s * 0.45, cy + s * 0.35)], fill=color, width=st)
    dr.arc([cx - s * 0.45 - st * 0.5, cy + s * 0.05, cx - s * 0.05, cy + s * 0.55], 90, 180, fill=color, width=st)
    dr.line([(cx - s * 0.75, cy - s * 0.25), (cx - s * 0.12, cy - s * 0.25)], fill=color, width=st)
    dr.line([(cx + s * 0.25, cy - s * 0.25), (cx + s * 0.25, cy + s * 0.55)], fill=color, width=st)
    r = st * 0.85
    dr.ellipse([cx + s * 0.25 - r, cy - s * 0.72 - r, cx + s * 0.25 + r, cy - s * 0.72 + r], fill=color)


def ti_wordmark(im, xy, size, color=(211, 58, 28, 255), anchor='rs'):
    """TEXAS INSTRUMENTS in flared small caps (Times-bold homage: big initials, small caps)"""
    dr = ImageDraw.Draw(im)
    big, small = font('timesbd.ttf', size), font('timesbd.ttf', size * 0.78)
    parts = [('T', big), ('EXAS ', small), ('I', big), ('NSTRUMENTS', small)]
    total = sum(dr.textlength(t, font=f) for t, f in parts)
    x, y = xy
    if anchor[0] == 'r': x -= total
    elif anchor[0] == 'm': x -= total / 2
    for t, f in parts:
        dr.text((x, y), t, font=f, fill=color, anchor='ls')
        x += dr.textlength(t, font=f)


def speak_spell(im, box, red=(226, 52, 30, 255), blue=(28, 132, 214, 255), rim=(255, 248, 214, 255)):
    """the product wordmark: a bouncy 'Speak' over '& Spell', each letter nudged off the baseline"""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    dr = ImageDraw.Draw(im)
    f1 = font('georgiaz.ttf', h * 0.50)
    f2 = font('georgiaz.ttf', h * 0.46)
    bounce = [0.0, -0.05, 0.03, -0.04, 0.05]
    def word(text, x, y, f, col):
        for i, ch in enumerate(text):
            dy = bounce[i % len(bounce)] * h
            dr.text((x, y + dy), ch, font=f, fill=col, anchor='ls', stroke_width=max(2, int(h * 0.035)), stroke_fill=rim)
            x += dr.textlength(ch, font=f) * 0.93
        return x
    word('Speak', x0 + w * 0.02, y0 + h * 0.48, f1, red)
    xa = word('&', x0 + w * 0.10, y0 + h * 0.95, f2, blue)
    xe = word('Spell', xa + w * 0.02, y0 + h * 0.95, f2, blue)
    dr.text((xe + w * 0.01, y0 + h * 0.60), 'TM', font=font('arial.ttf', h * 0.09), fill=blue, anchor='ls')


# ── Commodore: the C= mark, the badge, the rainbow stripes ─────────────────────────────────────────────────────
def cbm_mark(im, cx, cy, r, c_color=(24, 28, 70, 255), blue=(28, 70, 160, 255), red=(206, 38, 36, 255)):
    """the C with a blue flag above and a red flag below, pointing right"""
    S = 4
    size = int(r * 2.9) * S
    lay = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    c = size / 2 - r * 0.45 * S
    R, ri = r * S, r * 0.56 * S
    d.pieslice([c - R, size / 2 - R, c + R, size / 2 + R], 40, 320, fill=c_color)
    d.ellipse([c - ri, size / 2 - ri, c + ri, size / 2 + ri], fill=(0, 0, 0, 0))
    fx0, fx1 = c + r * 0.05 * S, c + r * 1.15 * S
    g = r * 0.07 * S
    d.polygon([(fx0, size / 2 - g), (fx1, size / 2 - g), (fx1 - r * 0.35 * S, size / 2 - r * 0.45 * S), (fx0, size / 2 - r * 0.45 * S)], fill=blue)
    d.polygon([(fx0, size / 2 + g), (fx1, size / 2 + g), (fx1 - r * 0.35 * S, size / 2 + r * 0.45 * S), (fx0, size / 2 + r * 0.45 * S)], fill=red)
    lay = lay.resize((size // S, size // S), Image.LANCZOS)
    im.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))


def rainbow_stripes(im, box, n=5):
    x0, y0, x1, y1 = box
    dr = ImageDraw.Draw(im)
    cols = [(226, 44, 40), (242, 140, 32), (246, 214, 40), (64, 170, 70), (40, 104, 196)][:n]
    h = (y1 - y0) / n
    sl = (y1 - y0) * 0.55
    for i, c in enumerate(cols):
        ya, yb = y0 + i * h, y0 + (i + 1) * h - max(1, h * 0.12)
        dr.polygon([(x0 + sl * (1 - i / n), ya), (x1, ya), (x1 - sl * (1 / n), yb), (x0 + sl * (1 - (i + 1) / n) - sl * (1 / n) * 0, yb)], fill=(*c, 255))


def commodore_badge(im, box, plate=(52, 50, 48, 255), ink=(222, 218, 208, 255), with64=True):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle(box, radius=h * 0.18, fill=plate)
    cbm_mark(im, x0 + h * 0.62, y0 + h * 0.5, h * 0.32, c_color=ink, blue=(120, 170, 235, 255), red=(236, 80, 70, 255))
    f = font('segoeui.ttf', h * 0.58)
    dr.text((x0 + h * 1.12, y0 + h * 0.72), 'commodore', font=f, fill=ink, anchor='ls')
    tx = x0 + h * 1.12 + dr.textlength('commodore', font=f) + h * 0.35
    rainbow_stripes(im, (tx, y0 + h * 0.2, tx + h * 1.5, y0 + h * 0.8))
    if with64:
        dr.text((tx + h * 1.65, y0 + h * 0.78), '64', font=font('ariblk.ttf', h * 0.62), fill=ink, anchor='ls')


# ── the 1984 rainbow apple ─────────────────────────────────────────────────────────────────────────────────────
def apple_mask(W, H):
    """1-channel mask of a bitten apple with a leaf, filling (W, H)"""
    S = 4
    m = Image.new('L', (W * S, H * S), 0)
    d = ImageDraw.Draw(m)
    cx, cy = W * S * 0.5, H * S * 0.60
    rx, ry = W * S * 0.47, H * S * 0.40
    pts = []
    for i in range(240):
        t = i / 240 * 2 * math.pi
        rr = 1.0 - 0.13 * math.exp(-((t - math.pi / 2) / 0.33) ** 2) - 0.06 * math.exp(-((t - 3 * math.pi / 2) / 0.25) ** 2)
        sx = 1.0 - 0.12 * (1 - math.sin(t)) / 2
        pts.append((cx + math.cos(t) * rx * rr * sx, cy - math.sin(t) * ry * rr))
    d.polygon(pts, fill=255)
    br = W * S * 0.17
    d.ellipse([cx + rx * 0.98 - br, cy - ry * 0.12 - br, cx + rx * 0.98 + br, cy - ry * 0.12 + br], fill=0)
    # leaf: a lens tilted 45°
    lx, ly, ll, lw = cx + W * S * 0.05, cy - ry * 1.28, W * S * 0.17, W * S * 0.085
    leaf = []
    for i in range(60):
        t = i / 60 * 2 * math.pi
        x, y = math.cos(t) * ll, math.sin(t) * lw * abs(math.sin(t)) ** 0.2
        a = -0.8
        leaf.append((lx + x * math.cos(a) - y * math.sin(a), ly + x * math.sin(a) + y * math.cos(a)))
    d.polygon(leaf, fill=255)
    return m.resize((W, H), Image.LANCZOS)


def rainbow_apple(im, box):
    x0, y0, x1, y1 = [int(v) for v in box]
    W, H = x1 - x0, y1 - y0
    cols = [(97, 187, 70), (253, 184, 39), (245, 130, 31), (224, 58, 62), (150, 61, 151), (0, 157, 220)]
    stripes = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(stripes)
    top = int(H * 0.08)
    band = (H - top) / 6
    d.rectangle([0, 0, W, top + band], fill=(*cols[0], 255))
    for i, c in enumerate(cols):
        d.rectangle([0, top + i * band, W, top + (i + 1) * band + 1], fill=(*c, 255))
    _paste_mask(im, stripes, apple_mask(W, H), x0, y0)


# ── DEC: seven blocks, "digital" ───────────────────────────────────────────────────────────────────────────────
def dec_logo(im, box, block=(122, 28, 44, 255), ink=(250, 246, 240, 255)):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    dr = ImageDraw.Draw(im)
    n = 7
    gap = w * 0.012
    bw = (w - gap * (n - 1)) / n
    f = font('arialbd.ttf', h * 0.78)
    for i, ch in enumerate('digital'):
        bx = x0 + i * (bw + gap)
        dr.rectangle([bx, y0, bx + bw, y1], fill=block)
        dr.text((bx + bw / 2, y1 - h * 0.14), ch, font=f, fill=ink, anchor='ms')


# ── the XP-era four-tile waving flag ───────────────────────────────────────────────────────────────────────────
def xp_flag(im, box, gap=0.06):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    S = 4
    lay = Image.new('RGBA', (int(w * S), int(h * S)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    W_, H_ = lay.size
    cols = [((242, 80, 34), 0, 0), ((127, 186, 0), 1, 0), ((0, 164, 239), 0, 1), ((255, 185, 0), 1, 1)]
    def wave(u): return math.sin(u * math.pi * 1.1 + 0.3) * 0.07
    for c, i, j in cols:
        u0, u1 = i * 0.5 + (gap / 2 if i else 0), (i + 1) * 0.5 - (0 if i else gap / 2)
        v0, v1 = j * 0.5 + (gap / 2 if j else 0), (j + 1) * 0.5 - (0 if j else gap / 2)
        pts = []
        for k in range(21):
            u = u0 + (u1 - u0) * k / 20; pts.append((u * W_, (v0 + wave(u)) * H_ * 0.86 + H_ * 0.07))
        for k in range(21):
            u = u1 - (u1 - u0) * k / 20; pts.append((u * W_, (v1 + wave(u)) * H_ * 0.86 + H_ * 0.07))
        skew = [(x + (y / H_) * W_ * -0.06, y) for (x, y) in pts]
        d.polygon(skew, fill=(*c, 255))
    lay = lay.resize((int(w), int(h)), Image.LANCZOS)
    im.alpha_composite(lay, (int(x0), int(y0)))
