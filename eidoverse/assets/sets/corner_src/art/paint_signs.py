"""paint_signs.py - the hand-painted protest signs of the Vibecamp "Free Fable" march (June 2026).

Claude's orange flower (a radial burst of rounded petals around a small cream face) drawn the way
the real signs were: poster paint and markers on cardboard or white poster board (research/
fable_ban.md sec. 3: gagged with tape, behind prison bars, "FREE FABLE", "FREE MYTHOS",
"DON'T MUZZLE MAH' MYTHOS!", "#NoExportLabel", "FABLE FABLE FABLE / NOW NOW NOW").

The layered bake happens here, in numpy: card (AmbientCG Cardboard002 / poster board) -> poster
paint (directional brush strokes, uneven cover, pooled rims, relief) -> marker (multiply ink,
wobbly SDF outlines, streaks) -> duct tape (weave, sheen, torn ends, drop shadow) -> lettering.

Outputs (atlas 4 cols x 2 rows, cell = 512x384, index = row*4 + col, row 0 at the TOP):
    art/sign_art_color.jpg   2048x768 sRGB
    art/sign_art_normal.jpg  2048x768 tangent normal, OpenGL (+Y up)
    art/sign_art_orm.jpg     2048x768 R=1 (no AO), G=roughness, B=0 metal
    art/sign_art_*_hi.jpg    4096x1536 (the painting resolution) for close-ups
    previews/signs_art_sheet.png  labelled contact sheet
"""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(ROOT, '..', '..', '..', '..'))
FONTS = os.path.join(REPO, 'eidoverse', 'assets', 'fonts')
TEX = os.path.join(ROOT, 'tex')
PREV = os.path.join(ROOT, 'previews')
CW, CH = 1024, 768                      # painting resolution of one cell (2x the atlas cell)
YY, XX = np.mgrid[0:CH, 0:CW].astype(np.float32)

INK = np.array([0.075, 0.068, 0.066], np.float32)


# ------------------------------------------------------------------------------------ noise
def vnoise(rng, scale, octaves=4, persistence=0.5, h=CH, w=CW):
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gh = max(2, int(h / scale * 2 ** o)) + 1
        gw = max(2, int(w / scale * 2 ** o)) + 1
        g = rng.random((gh, gw)).astype(np.float32)
        out += np.asarray(Image.fromarray(g, 'F').resize((w, h), Image.BICUBIC)) * amp
        tot += amp
        amp *= persistence
    return np.clip(out / tot, 0, 1)


def warp(field, rng, amp, scale):
    dx = (vnoise(rng, scale, 3) - 0.5) * 2 * amp
    dy = (vnoise(rng, scale, 3) - 0.5) * 2 * amp
    return ndi.map_coordinates(field, [YY + dy, XX + dx], order=1, mode='nearest')


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------------------ shapes & SDF
def shape_mask(draw_fn, ss=2):
    im = Image.new('L', (CW * ss, CH * ss), 0)
    draw_fn(ImageDraw.Draw(im), ss)
    return np.asarray(im.resize((CW, CH), Image.BOX), np.float32) / 255.0


def sdf(mask):
    b = mask > 0.5
    return (ndi.distance_transform_edt(~b) - ndi.distance_transform_edt(b)).astype(np.float32)


# --------------------------------------------------------------------------------- the card
class Card:
    def __init__(self, kind, rng):
        self.rng = rng
        self.kind = kind
        if kind == 'cardboard':
            src = Image.open(os.path.join(TEX, 'Cardboard002', 'Cardboard002_2K-JPG_Color.jpg')).convert('RGB')
            nrm = Image.open(os.path.join(TEX, 'Cardboard002', 'Cardboard002_2K-JPG_NormalGL.jpg')).convert('RGB')
            rgh = Image.open(os.path.join(TEX, 'Cardboard002', 'Cardboard002_2K-JPG_Roughness.jpg')).convert('L')
            # the texture is ~0.5 m across; the board is 0.60 x 0.45 m -> crop ~2048*0.6/0.5 would overrun;
            # a 1536x1152 window keeps the flutes a believable ~8 mm apart
            x0 = int(rng.integers(0, 2048 - 1536)); y0 = int(rng.integers(0, 2048 - 1152))
            box = (x0, y0, x0 + 1536, y0 + 1152)
            c = np.asarray(src.crop(box).resize((CW, CH), Image.LANCZOS), np.float32) / 255
            c = c * np.array([0.88, 0.80, 0.74], np.float32)       # kraft: less yellow, more brown
            lum_ = c.mean(2, keepdims=True)
            c = lum_ + (c - lum_) * 0.78
            low = vnoise(rng, 260, 3)
            c = c * (0.92 + 0.16 * low[..., None])
            # handling grime toward the board edges + a couple of water rings / scuffs
            ex = np.minimum(XX, CW - 1 - XX) / CW
            ey = np.minimum(YY, CH - 1 - YY) / CH
            edge = 1 - smoothstep(0.0, 0.09, np.minimum(ex, ey * 0.75))
            c = c * (1 - 0.22 * edge[..., None] * (0.5 + 0.5 * vnoise(rng, 40, 3))[..., None])
            for _ in range(int(rng.integers(1, 3))):
                cx, cy, r = rng.uniform(80, CW - 80), rng.uniform(80, CH - 80), rng.uniform(40, 110)
                d = np.hypot(XX - cx, YY - cy) + (vnoise(rng, 30, 2) - 0.5) * 18
                ring = np.exp(-((d - r) / 3.5) ** 2) * 0.22 + (d < r) * 0.04
                c = c * (1 - ring[..., None] * np.array([0.35, 0.45, 0.6]))
            self.C = np.clip(c, 0, 1)
            self.Nb = (np.asarray(nrm.crop(box).resize((CW, CH), Image.LANCZOS), np.float32) / 255) * 2 - 1
            self.R = np.asarray(rgh.crop(box).resize((CW, CH), Image.LANCZOS), np.float32) / 255 * 0.25 + 0.68
        else:
            base = np.array([0.935, 0.925, 0.895], np.float32)
            n1 = vnoise(rng, 300, 3); n2 = vnoise(rng, 6, 2)
            c = base[None, None, :] * (0.975 + 0.035 * n1[..., None] + 0.02 * (n2[..., None] - 0.5))
            for _ in range(int(rng.integers(3, 6))):               # grey thumb smudges
                cx, cy = rng.uniform(0, CW), rng.uniform(0, CH)
                r = rng.uniform(18, 45)
                s = np.exp(-(((XX - cx) ** 2 + (YY - cy) ** 2) / (2 * r * r))) * rng.uniform(0.04, 0.09)
                c = c * (1 - s[..., None])
            ex = np.minimum(XX, CW - 1 - XX) / CW
            ey = np.minimum(YY, CH - 1 - YY) / CH
            edge = 1 - smoothstep(0.0, 0.05, np.minimum(ex, ey * 0.75))
            c = c * (1 - 0.10 * edge[..., None] * vnoise(rng, 30, 3)[..., None])
            self.C = np.clip(c, 0, 1)
            grain = vnoise(rng, 3, 2)
            self.Nb = np.zeros((CH, CW, 3), np.float32); self.Nb[..., 2] = 1
            self.Hg = (grain - 0.5) * 0.06
            self.R = 0.80 + (vnoise(rng, 50, 2) - 0.5) * 0.06
        self.H = np.zeros((CH, CW), np.float32)
        self.cover = np.zeros((CH, CW), np.float32)            # how much is painted over the card

    # ---- poster paint
    def paint(self, sd, color, *, dirfield=None, stroke_w=(7, 16), stroke_len=(30, 100), cover=0.96,
              rough=0.58, thick=0.45, edge_noise=1.5, pool=0.28, var=0.07, density=330, dry=0.10):
        rng = self.rng
        sdw = warp(sd, rng, 1.6, 55) + (vnoise(rng, 14, 2) - 0.5) * edge_noise * 2
        m = np.clip(0.5 - sdw * 0.7, 0, 1)                         # anti-aliased, uneven fill edge
        col = np.array(color, np.float32)
        layer = Image.new('RGB', (CW, CH), tuple(int(v * 255) for v in col))
        d = ImageDraw.Draw(layer)
        ys, xs = np.nonzero(m > 0.3)
        if len(xs):
            count = max(12, int(len(xs) / density))
            ks = rng.integers(0, len(xs), count)
            for k in ks:
                x, y = float(xs[k]), float(ys[k])
                ang = (dirfield(x, y) if dirfield else rng.uniform(0, math.pi)) + rng.normal(0, 0.12)
                L = rng.uniform(*stroke_len); w = rng.uniform(*stroke_w)
                dv = 1 + rng.normal(0, var)
                c2 = np.clip(col * dv + rng.normal(0, 0.015, 3), 0, 1)
                x1, y1 = x - math.cos(ang) * L * 0.5, y - math.sin(ang) * L * 0.5
                x2, y2 = x + math.cos(ang) * L * 0.5, y + math.sin(ang) * L * 0.5
                d.line([(x1, y1), (x2, y2)], fill=tuple(int(v * 255) for v in c2), width=max(2, int(w)))
        P = np.asarray(layer, np.float32) / 255
        P = ndi.gaussian_filter(P, (0.9, 0.9, 0))
        rim = np.clip(m - ndi.gaussian_filter(m, 5.0), 0, 1) * 2.4
        P = P * (1 - pool * rim[..., None])
        # dry-brush: streaks where the card shows through, stretched along the strokes
        dryn = vnoise(rng, 9, 2)
        cov = cover * (1 - dry * smoothstep(0.62, 0.9, dryn)) * (0.94 + 0.06 * vnoise(rng, 30, 2))
        a = m * cov
        if self.kind == 'cardboard':                               # paint over kraft reads a touch darker
            P = P * (0.93 + 0.07 * (1 - a[..., None]))
        self.C = self.C * (1 - a[..., None]) + P * a[..., None]
        lum = P.mean(2)
        ridges = (lum - ndi.gaussian_filter(lum, 2.5)) * 5
        self.H += a * (thick + ridges * 0.35 + rim * 0.35)
        self.R = self.R * (1 - a) + a * (rough + (vnoise(rng, 20, 2) - 0.5) * 0.12)
        self.cover = np.maximum(self.cover, a)
        return m

    # ---- marker ink (multiplies into what is under it)
    def ink(self, alpha, color=INK, rough=0.42, relief=0.07):
        rng = self.rng
        streak = 0.86 + 0.14 * vnoise(rng, 5, 2)
        a = np.clip(alpha, 0, 1) * streak
        col = np.array(color, np.float32)
        self.C = self.C * (1 - a[..., None] * (1 - col))
        self.H += a * relief
        self.R = self.R * (1 - a) + a * rough

    def outline(self, sd, width, color=INK, wob=2.4, wscale=60, var=0.35, alpha=0.95):
        rng = self.rng
        sdw = warp(sd, rng, wob, wscale)
        w = width * (1 - var / 2 + var * vnoise(rng, 90, 2))
        a = np.clip(w / 2 - np.abs(sdw) + 0.5, 0, 1) * alpha
        # a darker overlap where the pen went round twice
        a = np.clip(a * (1 + 0.25 * smoothstep(0.7, 0.9, vnoise(rng, 120, 2))), 0, 1)
        self.ink(a, color)

    def stroke(self, pts, width, color=INK, alpha=0.95, taper=True, wob=1.2):
        """A free marker stroke through pts (list of (x, y) in cell pixels)."""
        rng = self.rng
        ss = 2
        im = Image.new('L', (CW * ss, CH * ss), 0)
        d = ImageDraw.Draw(im)
        P = []
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 6))
            for k in range(n):
                t = k / n
                P.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        P.append(pts[-1])
        nz = rng.normal(0, 1, (len(P), 2))
        nz = ndi.gaussian_filter1d(nz, 4, axis=0) * wob * 3
        P = [(p[0] + nz[i, 0], p[1] + nz[i, 1]) for i, p in enumerate(P)]
        for i in range(len(P) - 1):
            t = i / max(1, len(P) - 2)
            wt = width * (0.75 + 0.25 * math.sin(math.pi * t) if taper else 1.0) * (0.9 + 0.2 * rng.random())
            r = wt * ss / 2
            d.line([(P[i][0] * ss, P[i][1] * ss), (P[i + 1][0] * ss, P[i + 1][1] * ss)], fill=255,
                   width=max(1, int(wt * ss)))
            d.ellipse([P[i][0] * ss - r, P[i][1] * ss - r, P[i][0] * ss + r, P[i][1] * ss + r], fill=255)
        a = np.asarray(im.resize((CW, CH), Image.BOX), np.float32) / 255 * alpha
        self.ink(a, color)

    # ---- lettering
    def text(self, s, font, size, cx, base_y, color=INK, rot=4.0, size_j=0.05, base_j=0.028, track=0.02,
             bold=1, alpha=0.95, max_w=None):
        rng = self.rng
        ss = 2
        fpath = os.path.join(FONTS, font)
        sizes = [size * (1 + rng.normal(0, size_j)) for _ in s]
        fonts = [ImageFont.truetype(fpath, int(z * ss)) for z in sizes]
        def advances(fonts, sizes):
            out = []
            for f, ch, z in zip(fonts, s, sizes):
                if ch == ' ':
                    out.append(z * 0.34)
                else:
                    bb = f.getbbox(ch)
                    out.append((bb[2] - bb[0]) / ss + z * (0.06 + track))    # ink width + a hand's gap
            return out
        adv = advances(fonts, sizes)
        total = sum(adv)
        if max_w and total > max_w:
            k = max_w / total
            sizes = [z * k for z in sizes]
            fonts = [ImageFont.truetype(fpath, int(z * ss)) for z in sizes]
            adv = advances(fonts, sizes)
            total = sum(adv)
        layer = Image.new('L', (CW * ss, CH * ss), 0)
        x = cx - total / 2
        drift = rng.normal(0, 0.012) * size                      # the whole line wanders a little
        for i, (ch, f, a) in enumerate(zip(s, fonts, adv)):
            if ch != ' ':
                asc, desc = f.getmetrics()
                bb = f.getbbox(ch)
                g = Image.new('L', (int(a * ss * 2.2) + 40, (asc + desc) + 20), 0)
                ImageDraw.Draw(g).text((10 - bb[0], 10), ch, font=f, fill=255)
                g = g.rotate(rng.normal(0, rot), resample=Image.BICUBIC, expand=True)
                by = base_y + drift * (i - len(s) / 2) / max(1, len(s)) + rng.normal(0, base_j) * size
                px = int(x * ss) - 10
                py = int(by * ss - asc) - 10
                layer.paste(Image.fromarray(np.maximum(np.asarray(layer.crop((px, py, px + g.size[0], py + g.size[1]))),
                                                       np.asarray(g))), (px, py))
            x += a
        if bold:
            layer = layer.filter(ImageFilter.MaxFilter(1 + 2 * bold))
        A = np.asarray(layer.resize((CW, CH), Image.BOX), np.float32) / 255 * alpha
        self.ink(A, color)
        return total

    def pencil_guides(self, ys, x0, x1):
        rng = self.rng
        for y in ys:
            a = np.zeros((CH, CW), np.float32)
            yy = y + rng.normal(0, 1.2)
            band = np.exp(-((YY - yy - (XX - x0) * rng.normal(0, 0.004)) / 0.9) ** 2)
            band *= (XX > x0) * (XX < x1) * (0.35 + 0.65 * smoothstep(0.35, 0.7, vnoise(rng, 20, 2)))
            self.ink(band * 0.22, (0.45, 0.45, 0.47), rough=0.5, relief=0.0)

    # ---- duct tape
    def tape(self, cx, cy, length, width, ang):
        rng = self.rng
        ca, sa = math.cos(ang), math.sin(ang)
        u = (XX - cx) * ca + (YY - cy) * sa                    # along the strip
        v = -(XX - cx) * sa + (YY - cy) * ca                   # across
        half = length / 2
        # torn ends: jagged, fibrous
        tear1 = half + (vnoise(rng, 4, 3) - 0.5) * 14 + np.abs(v) * 0.05
        tear0 = -half + (vnoise(rng, 4, 3) - 0.5) * 14
        inside = (u < tear1) & (u > tear0) & (np.abs(v) < width / 2 + (vnoise(rng, 40, 2) - 0.5) * 2)
        m = ndi.gaussian_filter(inside.astype(np.float32), 0.8)
        # drop shadow under the tape (it stands off the paint a hair)
        sh = ndi.shift(ndi.gaussian_filter(m, 6), (6, 4), order=1)
        self.C = self.C * (1 - 0.35 * sh[..., None] * (1 - m[..., None]))
        weave = 0.5 + 0.5 * np.sin(u * 1.9) * np.sin(v * 1.9)
        wrink = np.exp(-((u - rng.uniform(-half * 0.5, half * 0.5) + v * 0.4) / 2.2) ** 2) * 0.25
        sheen = 0.5 + 0.5 * np.cos(v / (width / 2) * 1.2 + 0.4)
        base = np.array([0.60, 0.61, 0.60], np.float32)
        col = base[None, None, :] * (0.88 + 0.08 * weave[..., None] + 0.12 * sheen[..., None] - wrink[..., None]
                                     + 0.05 * (vnoise(rng, 25, 2)[..., None] - 0.5))
        self.C = self.C * (1 - m[..., None]) + np.clip(col, 0, 1) * m[..., None]
        self.H += m * (0.55 + weave * 0.06 - wrink * 0.6)
        self.R = self.R * (1 - m) + m * (0.34 + 0.08 * (1 - sheen))

    # ---- export helpers
    def normal(self, strength=1.3):
        H = self.H + (self.Hg if hasattr(self, 'Hg') else 0)
        H = ndi.gaussian_filter(H, 0.7)
        gx = ndi.sobel(H, axis=1) / 8.0
        gy = ndi.sobel(H, axis=0) / 8.0
        n2 = np.stack([-gx * strength * 10, gy * strength * 10, np.ones_like(H)], -1)
        nb = self.Nb.copy()
        k = 1 - 0.45 * self.cover                               # paint fills the flutes a little
        nb[..., 0] *= k; nb[..., 1] *= k
        n = np.stack([nb[..., 0] + n2[..., 0], nb[..., 1] + n2[..., 1], nb[..., 2] * n2[..., 2]], -1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        return n


# ------------------------------------------------------------------------------ the flower
ORANGE = (0.905, 0.455, 0.205)
CREAM = (0.965, 0.915, 0.80)


def flower(card, cx, cy, R, *, n=None, mood='smile', tilt=0.0):
    """Paint Claude's flower: orange rounded rays around a small cream face. Returns face info."""
    rng = card.rng
    n = n or int(rng.integers(11, 14))
    a0 = rng.uniform(0, math.tau)
    r_face = R * rng.uniform(0.30, 0.34)
    petals = []
    for k in range(n):
        a = a0 + k * math.tau / n + rng.normal(0, 0.035)
        L = R * rng.uniform(0.84, 1.0)
        w = R * rng.uniform(0.19, 0.235) * (12.0 / n) ** 0.5
        bend = rng.normal(0, 0.025)
        petals.append((a, L, w, bend))

    def draw(d, ss):
        for a, L, w, bend in petals:
            ca, sa = math.cos(a), math.sin(a)
            px, py = -sa, ca
            pts_l, pts_r = [], []
            steps = 20
            hw_tip = w * 0.5
            tipr = L - hw_tip
            r_base = r_face * 0.55
            for i in range(steps + 1):
                t = i / steps
                r = r_base + (tipr - r_base) * t
                hw = w * 0.5 * (0.50 + 0.50 * float(smoothstep(0.0, 0.85, t)))   # narrow root, widest at the tip
                off = bend * R * math.sin(math.pi * t * 0.5)
                x = cx + ca * r + px * off
                y = cy + sa * r + py * off
                pts_l.append(((x + px * hw) * ss, (y + py * hw) * ss))
                pts_r.append(((x - px * hw) * ss, (y - py * hw) * ss))
            d.polygon(pts_l + pts_r[::-1], fill=255)
            off = bend * R * math.sin(math.pi * 0.5)
            ex = cx + ca * tipr + px * off
            ey = cy + sa * tipr + py * off
            d.ellipse([(ex - hw_tip) * ss, (ey - hw_tip) * ss, (ex + hw_tip) * ss, (ey + hw_tip) * ss], fill=255)

    pm = shape_mask(draw)
    psd = sdf(pm)
    radial = lambda x, y: math.atan2(y - cy, x - cx)
    card.paint(psd, ORANGE, dirfield=radial, stroke_w=(8, 18), stroke_len=(40, 120), var=0.08)
    # a second, thinner coat of a warmer orange on some petals: hand-painted unevenness
    card.paint(psd + 5 + (vnoise(rng, 35, 2) - 0.5) * 14, (0.95, 0.52, 0.22), dirfield=radial, cover=0.55,
               stroke_w=(5, 11), stroke_len=(25, 80), thick=0.15, pool=0.1, dry=0.35)
    card.outline(psd, width=R * 0.045 + 3, wob=1.6)
    # the face
    fm = shape_mask(lambda d, ss: d.ellipse([(cx - r_face) * ss, (cy - r_face * 0.97) * ss, (cx + r_face) * ss,
                                               (cy + r_face * 0.97) * ss], fill=255))
    fsd = sdf(fm)
    circ = lambda x, y: math.atan2(y - cy, x - cx) + math.pi / 2
    card.paint(fsd, CREAM, dirfield=circ, stroke_w=(6, 13), stroke_len=(20, 60), var=0.03, rough=0.62)
    card.outline(fsd, width=R * 0.04 + 3, wob=1.8)
    ey = cy - r_face * 0.18
    ex = r_face * 0.36
    er = r_face * 0.12
    for sx in (-1, 1):
        em = shape_mask(lambda d, ss, sx=sx: d.ellipse([(cx + sx * ex - er) * ss, (ey - er * 1.25) * ss,
                                                         (cx + sx * ex + er) * ss, (ey + er * 1.25) * ss], fill=255))
        card.ink(ndi.gaussian_filter(em, 0.6) * 0.97)
    mouth_y = cy + r_face * 0.36
    if mood == 'smile':
        pts = [(cx + r_face * 0.42 * math.cos(t), mouth_y - r_face * 0.14 + r_face * 0.24 * math.sin(t))
               for t in np.linspace(0.25, math.pi - 0.25, 9)]
        card.stroke(pts, R * 0.035 + 2)
    elif mood == 'sad':
        pts = [(cx + r_face * 0.36 * math.cos(t), mouth_y + r_face * 0.10 - r_face * 0.16 * math.sin(t))
               for t in np.linspace(0.35, math.pi - 0.35, 9)]
        card.stroke(pts, R * 0.033 + 2)
        for sx in (-1, 1):                                          # worried brows
            card.stroke([(cx + sx * ex * 1.45, ey - er * 2.1), (cx + sx * ex * 0.55, ey - er * 2.9)], R * 0.022 + 2)
    return dict(cx=cx, cy=cy, R=R, r_face=r_face, eye_y=ey, eye_x=ex, eye_r=er, mouth_y=mouth_y)


def gag(card, f, big=1.0):
    """An X of silver duct tape over the flower's mouth."""
    rng = card.rng
    L = f['r_face'] * 1.75 * big
    W = f['r_face'] * 0.36 * big
    card.tape(f['cx'] + rng.normal(0, 2), f['mouth_y'], L, W, math.radians(28 + rng.normal(0, 4)))
    card.tape(f['cx'] + rng.normal(0, 2), f['mouth_y'] + rng.normal(0, 2), L, W, math.radians(-26 + rng.normal(0, 4)))


def bars(card, f, n=5, pad=1.05):
    """Prison bars painted in black over the flower: verticals + top and bottom rails."""
    rng = card.rng
    R = f['R'] * pad
    cx, cy = f['cx'], f['cy']
    x0, x1 = cx - R, cx + R
    y0, y1 = cy - R * 0.98, cy + R * 0.98
    bw = R * 0.075

    def draw(d, ss):
        for i in range(n):
            x = x0 + (x1 - x0) * (i + 0.5) / n + rng.normal(0, 3)
            d.polygon([((x - bw / 2 + rng.normal(0, 1.5)) * ss, (y0 + 4) * ss),
                       ((x + bw / 2 + rng.normal(0, 1.5)) * ss, (y0 + 4) * ss),
                       ((x + bw / 2 + rng.normal(0, 2.5)) * ss, (y1 - 4) * ss),
                       ((x - bw / 2 + rng.normal(0, 2.5)) * ss, (y1 - 4) * ss)], fill=255)
        for y in (y0, y1):
            d.polygon([((x0 - bw * 0.3) * ss, (y - bw * 0.55 + rng.normal(0, 1.5)) * ss),
                       ((x1 + bw * 0.3) * ss, (y - bw * 0.55 + rng.normal(0, 1.5)) * ss),
                       ((x1 + bw * 0.3) * ss, (y + bw * 0.55 + rng.normal(0, 1.5)) * ss),
                       ((x0 - bw * 0.3) * ss, (y + bw * 0.55 + rng.normal(0, 1.5)) * ss)], fill=255)

    bm = shape_mask(draw)
    vert = lambda x, y: math.pi / 2
    card.paint(sdf(bm), (0.055, 0.052, 0.058), dirfield=vert, stroke_w=(5, 10), stroke_len=(40, 140), var=0.2,
               rough=0.5, thick=0.5, pool=0.15, dry=0.12)
    return (x0, y0, x1, y1)


def tear(card, f):
    ex = f['cx'] - f['eye_x'] - f['eye_r'] * 0.2
    ey = f['eye_y'] + f['eye_r'] * 2.4
    r = f['eye_r'] * 0.9

    def draw(d, ss):
        d.ellipse([(ex - r) * ss, (ey - r) * ss, (ex + r) * ss, (ey + r) * ss], fill=255)
        d.polygon([((ex - r * 0.8) * ss, (ey - r * 0.45) * ss), ((ex + r * 0.8) * ss, (ey - r * 0.45) * ss),
                   (ex * ss, (ey - r * 2.6) * ss)], fill=255)
    m = shape_mask(draw)
    s = sdf(m)
    card.paint(s, (0.20, 0.47, 0.86), stroke_w=(3, 6), stroke_len=(8, 20), thick=0.35, rough=0.45, pool=0.4)
    card.outline(s, width=3.5, color=(0.08, 0.16, 0.42), wob=0.6)


def padlock(card, cx, cy, s):
    rng = card.rng
    # shackle: a thick marker arch
    pts = [(cx + s * 0.34 * math.cos(t), cy - s * 0.22 - s * 0.42 * math.sin(t)) for t in np.linspace(0, math.pi, 14)]
    card.stroke([(cx + s * 0.34, cy - s * 0.05)] + pts + [(cx - s * 0.34, cy - s * 0.05)], s * 0.11)

    def body(d, ss):
        d.rounded_rectangle([(cx - s * 0.52) * ss, (cy - s * 0.18) * ss, (cx + s * 0.52) * ss, (cy + s * 0.55) * ss],
                            radius=s * 0.12 * ss, fill=255)
    m = shape_mask(body)
    sd_ = sdf(m)
    card.paint(sd_, (0.86, 0.66, 0.20), dirfield=lambda x, y: 0.0, stroke_w=(5, 10), stroke_len=(20, 60),
               rough=0.5, var=0.06)
    card.outline(sd_, width=6, wob=1.2)
    km = shape_mask(lambda d, ss: (d.ellipse([(cx - s * 0.08) * ss, (cy + s * 0.05) * ss, (cx + s * 0.08) * ss,
                                             (cy + s * 0.21) * ss], fill=255),
                                  d.polygon([((cx - s * 0.04) * ss, (cy + s * 0.15) * ss),
                                             ((cx + s * 0.04) * ss, (cy + s * 0.15) * ss),
                                             ((cx + s * 0.06) * ss, (cy + s * 0.36) * ss),
                                             ((cx - s * 0.06) * ss, (cy + s * 0.36) * ss)], fill=255)))
    card.ink(km * 0.97)


def check(card, x, y, s, color=(0.12, 0.55, 0.22)):
    card.stroke([(x - s * 0.45, y), (x - s * 0.12, y + s * 0.38), (x + s * 0.55, y - s * 0.52)], s * 0.16,
                color=color, taper=False)
    card.stroke([(x - s * 0.40, y + s * 0.03), (x - s * 0.10, y + s * 0.33), (x + s * 0.50, y - s * 0.47)], s * 0.12,
                color=color, taper=False, alpha=0.6)


# ------------------------------------------------------------------------------ the 8 signs
CAVEAT, KALAM, SEDG = 'CaveatBrush-Regular.ttf', 'Kalam-Bold.ttf', 'SedgwickAveDisplay-Regular.ttf'
RED = (0.78, 0.12, 0.10)
BLUE = (0.12, 0.26, 0.62)


def sign0(rng):                      # FREE FABLE + flower behind bars (white)
    c = Card('poster', rng)
    c.pencil_guides([172, 176], 120, 900)
    f = flower(c, CW * 0.5 + rng.normal(0, 8), CH * 0.60, CH * 0.285, mood='sad')
    bars(c, f, n=5)
    c.text('FREE', SEDG, 136, CW * 0.235, 170, rot=4, max_w=300)
    c.text('FABLE', SEDG, 142, CW * 0.70, 174, color=RED, rot=4, max_w=400)
    return c


def sign1(rng):                      # gagged flower + FREE FABLE (cardboard)
    c = Card('cardboard', rng)
    f = flower(c, CW * 0.5, CH * 0.42, CH * 0.33, mood='smile')
    gag(c, f)
    c.text('FREE FABLE', SEDG, 128, CW * 0.5, CH * 0.93, rot=3, max_w=CW * 0.82)
    return c


def sign2(rng):                      # FREE MYTHOS + barred flower with a tear (white)
    c = Card('poster', rng)
    c.pencil_guides([168], 90, 930)
    f = flower(c, CW * 0.5, CH * 0.61, CH * 0.28, mood='sad')
    tear(c, f)
    bars(c, f, n=6)
    c.text('FREE MYTHOS', KALAM, 118, CW * 0.5, 170, color=BLUE, rot=3, max_w=CW * 0.84)
    return c


def sign3(rng):                      # big gagged flower, no text (cardboard)
    c = Card('cardboard', rng)
    f = flower(c, CW * 0.5 + rng.normal(0, 10), CH * 0.5, CH * 0.43, n=13, mood='smile')
    gag(c, f, big=1.1)
    return c


def sign4(rng):                      # DON'T MUZZLE MAH' MYTHOS! + gagged flower (white)
    c = Card('poster', rng)
    c.pencil_guides([140, 285], 70, 950)
    c.text("DON'T MUZZLE", CAVEAT, 132, CW * 0.5, 140, rot=4, max_w=CW * 0.88)
    c.text("MAH' MYTHOS!", CAVEAT, 132, CW * 0.5, 285, color=RED, rot=4, max_w=CW * 0.88)
    f = flower(c, CW * 0.5, CH * 0.72, CH * 0.22, mood='smile')
    gag(c, f)
    return c


def sign5(rng):                      # #NoExportLabel + barred flower (cardboard)
    c = Card('cardboard', rng)
    c.text('#NoExportLabel', KALAM, 104, CW * 0.5, 150, color=BLUE, rot=3, max_w=CW * 0.88)
    f = flower(c, CW * 0.5, CH * 0.62, CH * 0.27, mood='sad')
    bars(c, f, n=5)
    return c


def sign6(rng):                      # FABLE FABLE FABLE / NOW NOW NOW + flower with a check (white)
    c = Card('poster', rng)
    c.pencil_guides([140, 268], 60, 960)
    c.text('FABLE FABLE FABLE', SEDG, 104, CW * 0.5, 140, rot=3, max_w=CW * 0.9)
    c.text('NOW NOW NOW', SEDG, 112, CW * 0.5, 268, color=RED, rot=4, max_w=CW * 0.8)
    f = flower(c, CW * 0.40, CH * 0.73, CH * 0.20, mood='smile')
    check(c, CW * 0.70, CH * 0.73, CH * 0.26)
    return c


def sign7(rng):                      # big flower behind bars with a padlock, no text (cardboard)
    c = Card('cardboard', rng)
    f = flower(c, CW * 0.5, CH * 0.47, CH * 0.40, n=12, mood='sad')
    x0, y0, x1, y1 = bars(c, f, n=6, pad=1.03)
    padlock(c, CW * 0.5 + rng.normal(0, 6), y1 - CH * 0.02, CH * 0.21)
    return c


SIGNS = [sign0, sign1, sign2, sign3, sign4, sign5, sign6, sign7]
LABELS = ['0 FREE FABLE + bars (white)', '1 gagged + FREE FABLE (card)', '2 FREE MYTHOS + bars, tear (white)',
          '3 big gagged (card)', "4 DON'T MUZZLE MAH' MYTHOS! (white)", '5 #NoExportLabel + bars (card)',
          '6 FABLE x3 / NOW x3 + check (white)', '7 bars + padlock (card)']


def main():
    col_hi = np.zeros((2 * CH, 4 * CW, 3), np.float32)
    nrm_hi = np.zeros((2 * CH, 4 * CW, 3), np.float32)
    rgh_hi = np.zeros((2 * CH, 4 * CW), np.float32)
    for i, fn in enumerate(SIGNS):
        rng = np.random.default_rng(1000 + i * 17)
        c = fn(rng)
        r, q = divmod(i, 4)
        col_hi[r * CH:(r + 1) * CH, q * CW:(q + 1) * CW] = np.clip(c.C, 0, 1)
        nrm_hi[r * CH:(r + 1) * CH, q * CW:(q + 1) * CW] = c.normal()
        rgh_hi[r * CH:(r + 1) * CH, q * CW:(q + 1) * CW] = np.clip(c.R, 0.05, 1)
        print('painted', LABELS[i], flush=True)
    out = HERE
    to8 = lambda a: Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))
    ci = to8(col_hi)
    ni = to8(nrm_hi * 0.5 + 0.5)
    oi = to8(np.stack([np.ones_like(rgh_hi), rgh_hi, np.zeros_like(rgh_hi)], -1))
    for im, name in ((ci, 'color'), (ni, 'normal'), (oi, 'orm')):
        im.save(os.path.join(out, f'sign_art_{name}_hi.jpg'), quality=94, subsampling=0)
        im.resize((2048, 768), Image.LANCZOS).save(os.path.join(out, f'sign_art_{name}.jpg'), quality=94,
                                                  subsampling=0)
    # labelled contact sheet
    sheet = ci.resize((2048, 768), Image.LANCZOS).convert('RGB')
    d = ImageDraw.Draw(sheet)
    for i, lab in enumerate(LABELS):
        r, q = divmod(i, 4)
        d.rectangle([q * 512 + 4, r * 384 + 4, q * 512 + 14 + 7 * len(lab), r * 384 + 20], fill=(0, 0, 0))
        d.text((q * 512 + 9, r * 384 + 6), lab, fill=(255, 255, 0))
    sheet.save(os.path.join(PREV, 'signs_art_sheet.png'))
    print('done', flush=True)


if __name__ == '__main__':
    main()
