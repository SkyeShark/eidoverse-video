"""build_speakspell.py — the 1978/80 speaking toy for DAISY (Blender 5.2, headless).
bash run_blender.sh work/daisy/props/blender/build_speakspell.py   (the isolated runner; never blender.exe directly)
Real size (V&A, Henry Ford): 254 × 177 × 38 mm. Front faces -Y, up +Z, bottom at z = 0. The toy is modelled upright;
the wire stand is built in place for a lean of LEAN, and the JS module leans the toy back onto it by the same LEAN."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import era_bkit as B
from mathutils import Vector

B.reset(ao_distance=0.012, samples=24)
W, H, T = 0.177, 0.254, 0.038
Y0 = -T / 2                       # front face
HOLE = dict(w=0.124, h=0.025, cz=0.2260, r=0.012)
BAND = dict(z0=0.1671, z1=0.2101)
CARD = dict(x0=-0.080, z0=0.034, w=0.160, h=0.118, r=0.012)
VFD = dict(x0=0.006, x1=0.074, z0=0.1813, z1=0.1959)
GRILLE = dict(x0=-0.0795, x1=-0.0300, z0=0.1712, z1=0.2060)
SEAM_Y = 0.004                    # front/back shell parting line (y)

RED = B.lin('#c42a1a'); RED_AGED = B.lin('#c9543a')
BLACK = B.lin('#0d0d10')

# ══ outer mass (shared by the red shell and the band) ══
def outer_profile(grow=0.0):
    return B.rrect(W + 2 * grow, H + 2 * grow, 0.024 + grow, 8, 0, H / 2)

def hole_profile(grow=0.0):
    return B.rrect(HOLE['w'] + 2 * grow, HOLE['h'] + 2 * grow, HOLE['r'] + grow, 8, 0, HOLE['cz'])

def mass(name, grow=0.0):
    ob = B.prism(name, outer_profile(grow), T, 'y')
    hc = B.prism(name + '_h', hole_profile(-grow), T + 0.02, 'y')
    B.boolean(ob, hc)
    return ob

# ── red shell: round the perimeter first (4.5 mm), then cut, then a fine chamfer on the new edges
shell = mass('ss_shell')
B.chamfer(shell, width=0.0045, segments=5, angle=40, profile=0.5)
# band pocket: the black middle section replaces the front half across the full width (+ wraps the sides)
B.boolean(shell, B.rbox('bandcut', W + 0.02, T / 2 + SEAM_Y + 0.001, BAND['z1'] - BAND['z0'], 0, loc=(0, Y0 - 0.001 + (T / 2 + SEAM_Y + 0.001) / 2 - 0.0005, (BAND['z0'] + BAND['z1']) / 2)))
# membrane-card pocket, 1.0 mm deep
card_pocket = B.prism('cardpocket', B.rrect(CARD['w'] + 0.0012, CARD['h'] + 0.0012, CARD['r'] + 0.0006, 8, CARD['x0'] + CARD['w'] / 2, CARD['z0'] + CARD['h'] / 2), 0.004, 'y')
B.xform(card_pocket, (0, Y0 - 0.001, 0))
B.boolean(shell, card_pocket)
# back: battery door seam (a 0.7 mm groove rectangle) + finger notch, screw pockets
door_outer = B.prism('door_o', B.rrect(0.112, 0.074, 0.006, 6, 0, 0.078), 0.004, 'y'); B.xform(door_outer, (0, T / 2, 0))
door_inner = B.prism('door_i', B.rrect(0.1106, 0.0726, 0.0053, 6, 0, 0.078), 0.006, 'y'); B.xform(door_inner, (0, T / 2, 0))
B.boolean(door_outer, door_inner)
notch = B.prism('notch', B.rrect(0.022, 0.008, 0.004, 5, 0, 0.1125), 0.004, 'y'); B.xform(notch, (0, T / 2 + 0.0005, 0))
screws_at = [(-0.066, 0.030), (0.066, 0.030), (-0.050, 0.186), (0.050, 0.186)]   # clear of the handle hole
pockets = [B.cyl(f'sp{i}', 0.0042, 0.006, 24, loc=(x, T / 2, z), rot=(math.pi / 2, 0, 0)) for i, (x, z) in enumerate(screws_at)]
B.boolean(shell, [door_outer, notch] + pockets)
# parting-line groove round the perimeter (and inside the handle hole)
ring_o = B.prism('seam_o', outer_profile(0.002), 0.0007, 'y'); B.xform(ring_o, (0, SEAM_Y, 0))
ring_i = B.prism('seam_i', outer_profile(-0.0005), 0.002, 'y'); B.xform(ring_i, (0, SEAM_Y, 0))
B.boolean(ring_o, ring_i)
hr_o = B.prism('hseam_o', hole_profile(0.0005), 0.0007, 'y'); B.xform(hr_o, (0, SEAM_Y, 0))
hr_i = B.prism('hseam_i', hole_profile(-0.002), 0.002, 'y'); B.xform(hr_i, (0, SEAM_Y, 0))
B.boolean(hr_o, hr_i)
B.boolean(shell, [ring_o, hr_o])
B.chamfer(shell, width=0.00035, segments=2, angle=40)
B.finish(shell, angle=40)

# ── the black band: the case slice between handle and keyboard, front half, wrapping the sides
band = mass('ss_band', grow=0.0003)
B.chamfer(band, width=0.0048, segments=5, angle=40, profile=0.5)
keep = B.rbox('bandkeep', W + 0.02, T / 2 + SEAM_Y + 0.0003, BAND['z1'] - BAND['z0'] - 0.0004, 0,
              loc=(0, Y0 - 0.0003 + (T / 2 + SEAM_Y + 0.0003) / 2, (BAND['z0'] + BAND['z1']) / 2))
B.boolean(band, keep, op='INTERSECT')
# speaker cavity behind the grille, the slots through the 2 mm front wall
cav = B.rbox('cav', GRILLE['x1'] - GRILLE['x0'] + 0.004, 0.012, GRILLE['z1'] - GRILLE['z0'] + 0.004, 0.002,
             loc=(0.5 * (GRILLE['x0'] + GRILLE['x1']), Y0 + 0.0022 + 0.006, 0.5 * (GRILLE['z0'] + GRILLE['z1'])))
nsl = 9
pitch = (GRILLE['z1'] - GRILLE['z0']) / nsl
sl = B.slots('grille', nsl, pitch, GRILLE['x1'] - GRILLE['x0'], pitch * 0.46, 0.008, axis_along='z',
             loc=(0.5 * (GRILLE['x0'] + GRILLE['x1']), Y0 + 0.0012, 0.5 * (GRILLE['z0'] + GRILLE['z1'])))
# the display window: an opening into the tube cavity
vcav = B.rbox('vcav', VFD['x1'] - VFD['x0'] + 0.006, 0.010, VFD['z1'] - VFD['z0'] + 0.006, 0.002,
              loc=(0.5 * (VFD['x0'] + VFD['x1']), Y0 + 0.0020 + 0.005, 0.5 * (VFD['z0'] + VFD['z1'])))
vwin = B.rbox('vwin', VFD['x1'] - VFD['x0'], 0.006, VFD['z1'] - VFD['z0'], 0.0015,
              loc=(0.5 * (VFD['x0'] + VFD['x1']), Y0, 0.5 * (VFD['z0'] + VFD['z1'])))
B.boolean(band, [cav, sl, vcav, vwin])
B.chamfer(band, width=0.0005, segments=2, angle=40)
B.finish(band, angle=40)

# ── the membrane card: printed sheet with 40 embossed key domes (one piece)
card = B.prism('ss_card', B.rrect(CARD['w'], CARD['h'], CARD['r'], 8, CARD['x0'] + CARD['w'] / 2, CARD['z0'] + CARD['h'] / 2), 0.0011, 'y')
B.xform(card, (0, Y0 + 0.00095 - 0.00055, 0))       # front face ~0.4 mm proud of the shell face
rows = [0.0935, 0.0813, 0.0691, 0.0569]
key_centres = [(0.0198 + c * 0.01338, rows[r]) for r in range(4) for c in range(10)]
domes = []
for i, (kx, kz) in enumerate(key_centres):
    d = B.prism(f'dome{i}', B.rrect(0.0118, 0.0100, 0.0024, 5, CARD['x0'] + kx, CARD['z0'] + kz), 0.0014, 'y')
    B.xform(d, (0, Y0 - 0.0006 - 0.0007 + 0.0002, 0))
    domes.append(d)
B.boolean(card, domes, op='UNION')
B.chamfer(card, width=0.0006, segments=4, angle=25, profile=0.6)
B.finish(card, angle=35)

# ── feet, screws (metal), wire stand
feet = [B.cyl(f'foot{i}', 0.0055, 0.0022, 24, loc=(x, T / 2 + 0.0011, z), rot=(math.pi / 2, 0, 0)) for i, (x, z) in enumerate([(-0.064, 0.012), (0.064, 0.012), (-0.072, 0.192), (0.072, 0.192)])]
feet = B.join(feet, 'ss_feet'); B.chamfer(feet, 0.0007, 3, 30); B.finish(feet)
scr = [B.screw(f'scr{i}', 0.0026, loc=(x, T / 2 - 0.0028, z), rot=(-math.pi / 2, 0, 0)) for i, (x, z) in enumerate(screws_at)]
screws = B.join(scr, 'metal_screws'); B.finish(screws, 30)

# ══ materials ══
from PIL import Image

def draw_card(im, dr, font):
    Wp, Hp = im.size
    sx, sy = Wp / CARD['w'], Hp / CARD['h']
    X = lambda x: x * sx
    Y = lambda y: Hp - y * sy
    dr.rectangle([0, 0, Wp, Hp], fill=(230, 192, 0, 255))        # flat printed golden yellow (both references)
    dr.rounded_rectangle([X(0.005), Y(0.113), X(0.155), Y(0.032)], radius=0.008 * sx, fill=(212, 56, 27, 255))
    dr.rounded_rectangle([X(0.009), Y(0.101), X(0.151), Y(0.046)], radius=0.006 * sx, fill=(20, 128, 207, 255))
    R1 = ['OFF', 'GO', 'replay', 'repeat', 'clue', '?', 'key', 'letter', 'face', 'ON']
    R4 = ['U', 'V', 'W', 'X', 'Y', 'Z', "'", '#', '\\', 'up']
    L = list('ABCDEFGHIJKLMNOPQRST')
    layout = [R1, L[:10], L[10:20], R4]
    vow = set('AEIOU')
    ink = (23, 17, 12, 255)
    for r in range(4):
        for c in range(10):
            k = layout[r][c]
            cx, cz = key_centres[r * 10 + c]
            fn = r == 0 or (r == 3 and c >= 6)
            base = (214, 44, 28) if fn else ((246, 211, 18) if k in vow else (239, 108, 24))
            rim = (150, 30, 20) if fn else ((188, 150, 12) if k in vow else (180, 76, 16))
            x0, y0, x1, y1 = X(cx - 0.0059), Y(cz + 0.0050), X(cx + 0.0059), Y(cz - 0.0050)
            dr.rounded_rectangle([x0 - 6, y0 - 4, x1 + 6, y1 + 8], radius=0.0028 * sx, fill=(12, 84, 142, 255))
            dr.rounded_rectangle([x0, y0, x1, y1], radius=0.0024 * sx, fill=(*rim, 255))
            dr.rounded_rectangle([x0 + 5, y0 + 5, x1 - 5, y1 - 5], radius=0.0020 * sx, fill=(*base, 255))
            mx, my, kh, kw = (x0 + x1) / 2, (y0 + y1) / 2, (y1 - y0), (x1 - x0)
            if len(k) == 1 and k.isalpha():
                dr.text((mx, my + 2), k, font=font(kh * 0.74), fill=ink, anchor='mm')
            elif k in ('OFF', 'GO', 'ON'):
                dr.text((mx, my + 2), k, font=font(kh * 0.42), fill=ink, anchor='mm')
            elif k == 'replay':
                dr.arc([mx - kh * 0.1, my - kh * 0.2, mx + kh * 0.3, my + kh * 0.2], -90, 90, fill=ink, width=int(kh * 0.1))
                dr.line([mx + kh * 0.1, my + kh * 0.2, mx - kw * 0.2, my + kh * 0.2], fill=ink, width=int(kh * 0.1))
                dr.polygon([(mx - kw * 0.28, my + kh * 0.2), (mx - kw * 0.14, my + kh * 0.07), (mx - kw * 0.14, my + kh * 0.33)], fill=ink)
            elif k == 'repeat':
                dr.text((mx, my + 2), '//', font=font(kh * 0.5), fill=ink, anchor='mm')
            elif k == 'clue':
                dr.rectangle([mx - kw * 0.25, my - kh * 0.05, mx + kw * 0.25, my + kh * 0.06], fill=ink)
            elif k == '?':
                dr.text((mx, my + 2), '?', font=font(kh * 0.6), fill=ink, anchor='mm')
            elif k == 'key':
                dr.ellipse([mx - kh * 0.14, my - kh * 0.26, mx + kh * 0.14, my + kh * 0.02], fill=ink)
                dr.polygon([(mx - kh * 0.08, my - kh * 0.08), (mx + kh * 0.08, my - kh * 0.08), (mx + kh * 0.12, my + kh * 0.28), (mx - kh * 0.12, my + kh * 0.28)], fill=ink)
            elif k == 'letter':
                f = font(kh * 0.34)
                dr.text((mx - kw * 0.2, my + kh * 0.1), '?', font=f, fill=ink, anchor='mm'); dr.text((mx, my - kh * 0.12), '?', font=f, fill=ink, anchor='mm'); dr.text((mx + kw * 0.2, my + kh * 0.1), '?', font=f, fill=ink, anchor='mm')
            elif k == 'face':
                dr.ellipse([mx - kh * 0.3, my - kh * 0.3, mx + kh * 0.3, my + kh * 0.3], fill=ink)
                dr.ellipse([mx - kh * 0.15, my - kh * 0.13, mx - kh * 0.05, my - kh * 0.03], fill=(*base, 255))
                dr.ellipse([mx + kh * 0.05, my - kh * 0.13, mx + kh * 0.15, my - kh * 0.03], fill=(*base, 255))
                dr.arc([mx - kh * 0.16, my - kh * 0.12, mx + kh * 0.16, my + kh * 0.18], 25, 155, fill=(*base, 255), width=int(kh * 0.06))
            elif k == "'":
                dr.rectangle([mx - kw * 0.04, my - kh * 0.25, mx + kw * 0.04, my], fill=ink)
            elif k == '#':
                dr.text((mx, my + 2), '#', font=font(kh * 0.55), fill=ink, anchor='mm')
            elif k == '\\':
                dr.line([mx - kw * 0.15, my - kh * 0.25, mx + kw * 0.15, my + kh * 0.25], fill=ink, width=int(kh * 0.1))
            elif k == 'up':
                dr.polygon([(mx, my - kh * 0.3), (mx + kw * 0.2, my), (mx + kw * 0.07, my), (mx + kw * 0.07, my + kh * 0.28), (mx - kw * 0.07, my + kh * 0.28), (mx - kw * 0.07, my), (mx - kw * 0.2, my)], fill=ink)
    G1, O1 = (182, 224, 74, 255), (255, 178, 28, 255)
    kx = lambda c: 0.0198 + c * 0.01338
    def lab(s, cx, cy, col, size=0.0027):
        dr.text((X(cx), Y(cy)), s, font=font(size * sy), fill=col, anchor='mm')
    lab('REPLAY', kx(2), 0.1035, G1); lab('REPEAT', kx(3), 0.1035, G1); lab('CLUE', kx(4), 0.1035, G1)
    lab('MYSTERY', kx(5), 0.1082, O1); lab('WORD', kx(5), 0.1035, G1); lab('SECRET', kx(6), 0.1082, O1); lab('CODE', kx(6), 0.1035, G1)
    lab('LETTER', kx(7), 0.1035, G1); lab('SAY', kx(8), 0.1082, O1); lab('IT', kx(8), 0.1035, G1); lab('SPELL', kx(9), 0.1035, G1)
    lab('MODULE', kx(7), 0.0438, G1); lab('SELECT', kx(7), 0.0392, O1); lab('ERASE', kx(8), 0.0438, G1); lab('ENTER', kx(9), 0.0438, G1)
    # lower panel (Skye 09-23: era logos welcome, drawn as homage): the product wordmark, TI's small-caps name and
    # the Texas-outline mark, the copyright line above the wordmark
    import era_logos as LG
    LG.speak_spell(im, (X(0.009), Y(0.0305), X(0.092), Y(0.0015)))
    LG.ti_wordmark(im, (X(0.151), Y(0.0175)), 0.0047 * sy)
    LG.ti_mark(im, (X(0.1365), Y(0.0150), X(0.1510), Y(0.0020)))
    dr.text((X(0.011), Y(0.0305)), '© TI 1978', font=font(0.0021 * sy, bold=False), fill=(184, 64, 30, 255), anchor='ls')

def B_font_black(size):
    from PIL import ImageFont
    for f in ('ariblk.ttf', 'arialbd.ttf'):
        try: return ImageFont.truetype(B.FONTS + f, int(size))
        except Exception: pass

card_png = B.decal_png('ss_card', 2048, round(2048 * CARD['h'] / CARD['w']), draw_card)
card_proj = B.projector('proj_card', (CARD['x0'] + CARD['w'] / 2, Y0 - 0.002, CARD['z0'] + CARD['h'] / 2), (CARD['w'], CARD['h']), normal=(0, -1, 0), depth=0.01)

# back label (a small paper sticker, generic)
def draw_back(im, dr, font):
    Wp, Hp = im.size
    dr.rounded_rectangle([0, 0, Wp - 1, Hp - 1], radius=18, fill=(226, 220, 205, 255), outline=(120, 110, 95, 255), width=3)
    lines = ['TEXAS INSTRUMENTS', 'SPEAK & SPELL  ·  9V', 'MADE IN U.S.A.  © 1978', 'SERIAL 0781235']
    for i, s in enumerate(lines):
        dr.text((Wp / 2, 34 + i * 34), s, font=font(24 if i == 0 else 19, bold=i == 0), fill=(40, 34, 28, 255), anchor='mm')
back_png = B.decal_png('ss_back', 512, 170, draw_back)
back_proj = B.projector('proj_back', (0, T / 2 + 0.002, 0.155), (0.070, 0.023), normal=(0, 1, 0), depth=0.01)

m_red = B.plastic('ss_red', RED, aged=RED_AGED, age=0.35, rough=(0.28, 0.55), grime=(0.14, 0.05, 0.03), grime_amt=0.6, edge=0.25,
                  decals=[dict(img=back_png, proj=back_proj, rough=0.6)])
m_black = B.plastic('ss_black', BLACK, pbrname='Plastic012B', tile=5, texmix=0.05, rough=(0.17, 0.23), grime=(0.02, 0.02, 0.02),
                    grime_amt=0.3, edge=0.3, dust=(0.35, 0.35, 0.36), dust_amt=0.06, bump=0.02)   # smoked gloss: no glitter
m_card = B.plastic('ss_card', (1, 1, 1), tile=7, texmix=0.15, rough=(0.22, 0.42), grime=(0.12, 0.09, 0.05), grime_amt=0.5, edge=0.18,
                   dust_amt=0.06, decals=[dict(img=card_png, proj=card_proj, face0=-0.6, face1=-0.4, mode='mul')])  # print × wear
m_rubber = B.rubber('ss_rubber')
B.assign(shell, m_red); B.assign(band, m_black); B.assign(card, m_card); B.assign(feet, m_rubber)

# ══ stand: a black-coated wire plate stand; the toy leans back LEAN on it (module applies the lean to the toy) ══
LEAN = 0.12
WR = 0.0016
cl, sl_ = math.cos(LEAN), math.sin(LEAN)
def toy_to_world(zl, yl):      # the toy leans back about the x axis through its bottom (z = 0, y = 0): returns (y, z)
    return (yl * cl + zl * sl_, -yl * sl_ + zl * cl)
lift = 2 * WR + (T / 2) * sl_ + 0.0005
def W_(zl, yl):
    y, z = toy_to_world(zl, yl)
    return (y, z + lift)
fy, fz = W_(0.006, Y0)
cy, cz = W_(0.105, T / 2)
xs, yBack = 0.052, 0.078
wire_objs = []
for sx in (-1, 1):
    pts = [(sx * xs, fy - WR * 1.2, fz + 0.010), (sx * xs, fy - WR * 1.2, WR), (sx * xs, yBack, WR), (sx * xs * 0.82, cy + WR * 1.05, cz)]
    wire_objs.append(B.cable(f'wire{sx}', B.fillet_path(pts, 0.005, 6), WR))
wire_objs.append(B.cable('wbar0', [(-xs, yBack, WR), (xs, yBack, WR)], WR))
wire_objs.append(B.cable('wbar1', [(-xs * 0.82, cy + WR * 1.05, cz), (xs * 0.82, cy + WR * 1.05, cz)], WR))
stand = B.join(wire_objs, 'part_stand')
B.finish(stand, 60, weighted=False)
m_coat = B.plastic('ss_coat', B.lin('#141416'), pbrname='Plastic012B', tile=20, texmix=0.3, rough=(0.3, 0.55), grime_amt=0.2, edge=0.4, dust_amt=0.2, bump=0.2)
B.assign(stand, m_coat)

# ══ display glass + grille glow (runtime materials) ══
vx0, vx1, vz0, vz1 = VFD['x0'] + 0.0004, VFD['x1'] - 0.0004, VFD['z0'] + 0.0004, VFD['z1'] - 0.0004
glass = B.rbox('screen_vfd', vx1 - vx0, 0.0015, vz1 - vz0, 0.0012, loc=((vx0 + vx1) / 2, Y0 + 0.0009, (vz0 + vz1) / 2))
B.chamfer(glass, 0.0003, 2, 30); B.finish(glass, 30, weighted=False)
B.uv_planar(glass, vx0, vz0, vx1, vz1, 'xz')
B.assign(glass, B.simple_material('vfd_glass', (0.02, 0.03, 0.03), 0.1))
glow = B.rbox('glow_grille', GRILLE['x1'] - GRILLE['x0'], 0.0005, GRILLE['z1'] - GRILLE['z0'], 0.001,
              loc=(0.5 * (GRILLE['x0'] + GRILLE['x1']), Y0 + 0.0022 + 0.0115, 0.5 * (GRILLE['z0'] + GRILLE['z1'])))
B.uv_planar(glow, GRILLE['x0'], GRILLE['z0'], GRILLE['x1'], GRILLE['z1'], 'xz')
B.assign(glow, B.simple_material('glow', (0.01, 0.01, 0.01), 0.8))

# ══ bake: body (shell + band + feet) and the printed card each get a 2048 atlas; the stand a small one ══
B.delete_faces(card, lambda c, n: n.y > 0.8)                        # the card's back sits in its pocket
B.delete_faces(band, lambda c, n: n.y > 0.8 and c.y > SEAM_Y - 0.001)  # the band's back face against the shell
toy = B.join([shell, band, feet], 'ss_body')
B.uv_atlas(toy, angle=60, margin=0.003)
maps = B.bake(toy, 'ss_body', size=2048)
toy.data.materials.clear(); toy.data.materials.append(B.export_material('ss_body_baked', maps))
B.uv_atlas(card, angle=60, margin=0.003)
cmaps = B.bake(card, 'ss_card', size=2048)
card.data.materials.clear(); card.data.materials.append(B.export_material('ss_card_baked', cmaps))
card.name = 'ss_card'
B.uv_atlas(stand, angle=60, margin=0.01)
smaps = B.bake(stand, 'ss_stand', size=256, passes=('color', 'rough', 'normal'))
stand.data.materials.clear(); stand.data.materials.append(B.export_material('ss_stand_baked', smaps))
screws.data.materials.clear(); screws.data.materials.append(B.simple_material('metal_screw', (0.55, 0.55, 0.56), 0.35, 1.0))
for o in (toy, card, stand, screws, glass, glow): B.triangulate(o)
B.log('tris', B.stats([toy, card, stand, screws, glass, glow]))
B.export_glb([toy, card, stand, screws, glass, glow], 'speakspell')
