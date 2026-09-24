"""build_dectalk.py — the 1984 desktop speech synthesizer (DTC01 form), for DAISY (Blender 5.2 headless).
bash run_blender.sh work/daisy/props/blender/build_dectalk.py   (the isolated runner; never blender.exe directly)
457 × 305 × 102 mm (18 × 12 × 4 in). Front faces -Y, up +Z, bottom at z = 0.
The real front carries only the rocker; the brief adds two LEDs and a speaker grille, drawn in the rib language."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import era_bkit as B
import era_logos as LG
from mathutils import Vector

B.reset(ao_distance=0.015)
W, D, H, FOOT = 0.457, 0.305, 0.102, 0.006
yF = -D / 2
CH, CZ = 0.030, 0.026                # the slanted top-front: 30 mm drop over 26 mm
PART_Z = 0.034                       # parting line between the top cover and the base
prof = [(D / 2, FOOT, 0.004), (D / 2, H, 0.006), (yF + CZ, H, 0.008), (yF, H - CH, 0.006), (yF, FOOT, 0.004)]
case = B.prism('dt_case', B.fillet_poly([(p[0], p[1], p[2]) for p in prof], 0.004, 5), W, 'x')
B.chamfer(case, width=0.005, segments=5, angle=40, profile=0.5)

RIB0, RIBP, NRIB = 0.040, 0.0062, 6
GR = dict(x0=0.090, x1=0.205)
cuts = []
# horizontal grooves across the front (between the ribs)
for i in range(NRIB - 1):
    z = RIB0 + (i + 0.5) * RIBP
    cuts.append(B.rbox(f'grv{i}', W - 0.022, 0.0026, 0.0019, 0.0006, loc=(0, yF, z)))           # full width, as on the unit
# the stripe pocket (grey insert sits in it), the parting line round the case
cuts.append(B.rbox('stripe', W - 0.030, 0.0016, 0.0078, 0.0015, loc=(0, yF, 0.0255)))
ring_o = B.rbox('pl_o', W + 0.02, D + 0.02, 0.0007, 0.0, loc=(0, 0, PART_Z))
ring_i = B.rbox('pl_i', W - 0.0014, D - 0.0014, 0.002, 0.004, loc=(0, 0, PART_Z))
B.boolean(ring_o, ring_i)
cuts.append(ring_o)
# controls: rocker pocket, two LED holes
ROCK = dict(x=-W / 2 + 0.030, z=0.052)
cuts.append(B.rbox('rockpocket', 0.0215, 0.012, 0.0215, 0.002, loc=(ROCK['x'], yF, ROCK['z'])))
LEDS = [dict(name='power', x=-W / 2 + 0.056, z=0.0615), dict(name='speech', x=-W / 2 + 0.056, z=0.0455)]
for L in LEDS:
    cuts.append(B.cyl(f'lh{L["name"]}', 0.0027, 0.012, 20, loc=(L['x'], yF, L['z']), rot=(math.pi / 2, 0, 0)))
# speaker grille: a cavity behind the front wall and slots through it (between the grooves' rhythm)
cav = B.rbox('spkcav', GR['x1'] - GR['x0'] + 0.006, 0.020, NRIB * RIBP + 0.004, 0.003, loc=((GR['x0'] + GR['x1']) / 2, yF + 0.0025 + 0.010, RIB0 + (NRIB - 1) * RIBP / 2))
cuts.append(cav)
for i in range(NRIB):
    z = RIB0 + i * RIBP
    cuts.append(B.rbox(f'gs{i}', GR['x1'] - GR['x0'], 0.008, 0.0024, 0.0011, loc=((GR['x0'] + GR['x1']) / 2, yF, z)))
# side vents (rear half), back port panel recess in the base
for sx in (-1, 1):
    cuts.append(B.slots(f'sv{sx}', 20, 0.0072, 0.0026, 0.034, 0.012, axis_along='x', loc=(sx * W / 2, 0.050, 0.064), rot=(0, 0, math.pi / 2)))
cuts.append(B.rbox('backpanel', W - 0.060, 0.010, 0.026, 0.003, loc=(-0.005, D / 2, 0.020)))
B.boolean(case, cuts)
B.chamfer(case, width=0.0004, segments=2, angle=40)
B.finish(case, 40)

# the grey stripe insert, the rocker (bezel + paddle), back-panel inserts, feet
stripe = B.rbox('dt_stripe', W - 0.031, 0.0014, 0.0072, 0.0012, loc=(0, yF + 0.0004, 0.0255))
B.chamfer(stripe, 0.0003, 2, 40); B.finish(stripe, 40)
bez = B.rbox('bez', 0.0205, 0.006, 0.0205, 0.0018, loc=(ROCK['x'], yF + 0.0022, ROCK['z']))
B.boolean(bez, [B.rbox('bezin', 0.0150, 0.02, 0.0150, 0.0012, loc=(ROCK['x'], yF, ROCK['z']))])
paddle = B.rbox('paddle', 0.0144, 0.006, 0.0144, 0.0014)
B.boolean(paddle, [B.rbox('pdent', 0.010, 0.004, 0.004, 0.0015, loc=(0, -0.0027, 0.004))])     # the 'I' side dip
B.xform(paddle, (ROCK['x'], yF + 0.0015, ROCK['z']), (0.18, 0, 0))                               # rocked over
darks = [bez, paddle]
darks.append(B.rbox('bp_in', W - 0.064, 0.003, 0.022, 0.002, loc=(-0.005, D / 2 - 0.004, 0.020)))
def dsub(name, wt, wb, h, x, z, depth=0.005):
    o = B.prism(name, B.fillet_poly([(-wt / 2, h / 2), (-wb / 2, -h / 2), (wb / 2, -h / 2), (wt / 2, h / 2)], 0.0012, 4), depth, 'y')
    i = B.prism(name + 'i', B.fillet_poly([(-wt / 2 + 0.0008, h / 2 - 0.0008), (-wb / 2 + 0.0008, -h / 2 + 0.0008), (wb / 2 - 0.0008, -h / 2 + 0.0008), (wt / 2 - 0.0008, h / 2 - 0.0008)], 0.0008, 4), depth * 2, 'y')
    B.xform(i, (0, 0.002, 0)); B.boolean(o, i)
    B.xform(o, (x, D / 2 - 0.0035, z))
    return o
metals = [dsub('db25a', 0.0415, 0.0380, 0.0082, -0.165, 0.020), dsub('db25b', 0.0415, 0.0380, 0.0082, -0.110, 0.020)]
for i, x in enumerate((-0.068, -0.050)):
    darks.append(B.rbox(f'rj{i}', 0.010, 0.006, 0.009, 0.0008, loc=(x, D / 2 - 0.004, 0.021)))
for i, x in enumerate((-0.028, -0.015)):
    metals.append(B.cyl(f'aj{i}', 0.0036, 0.005, 16, loc=(x, D / 2 - 0.0035, 0.021), rot=(math.pi / 2, 0, 0)))
darks.append(B.cyl('thumb', 0.0075, 0.005, 28, loc=(0.075, D / 2 - 0.002, 0.021), rot=(0, math.pi / 2, 0)))
darks.append(B.rbox('iec', 0.028, 0.006, 0.020, 0.002, loc=(0.140, D / 2 - 0.004, 0.020)))
dark = B.join(darks, 'dt_dark'); B.chamfer(dark, 0.0003, 2, 40); B.finish(dark, 40)
metal = B.join(metals, 'metal_dt'); B.finish(metal, 40)
feet = B.join([B.cyl(f'ft{i}', 0.011, FOOT + 0.001, 24, loc=(x, y, (FOOT + 0.001) / 2)) for i, (x, y) in enumerate([(-0.19, -0.12), (0.19, -0.12), (-0.19, 0.12), (0.19, 0.12)])], 'dt_feet')
B.chamfer(feet, 0.0012, 3, 30); B.finish(feet)
# LED lenses + back green LED
leds = []
for L in LEDS:
    o = B.loft('led_' + L['name'], [[(L['x'] + math.cos(t) * 0.0026, yF + 0.004, L['z'] + math.sin(t) * 0.0026) for t in [i * math.pi / 10 for i in range(20)]],
                                     [(L['x'] + math.cos(t) * 0.0026, yF - 0.0004, L['z'] + math.sin(t) * 0.0026) for t in [i * math.pi / 10 for i in range(20)]],
                                     [(L['x'] + math.cos(t) * 0.0015, yF - 0.0016, L['z'] + math.sin(t) * 0.0015) for t in [i * math.pi / 10 for i in range(20)]]])
    B.finish(o, 60, weighted=False); leds.append(o)
bl = B.loft('led_back', [[(0.105 + math.cos(t) * 0.002, D / 2 - 0.004, 0.021 + math.sin(t) * 0.002) for t in [i * math.pi / 8 for i in range(16)]],
                         [(0.105 + math.cos(t) * 0.0012, D / 2 - 0.0015, 0.021 + math.sin(t) * 0.0012) for t in [i * math.pi / 8 for i in range(16)]]])
leds.append(bl)
# the speaker cavity wall, lit by the voice
glow = B.rbox('glow_grille', GR['x1'] - GR['x0'] + 0.004, 0.0006, NRIB * RIBP + 0.002, 0.0, loc=((GR['x0'] + GR['x1']) / 2, yF + 0.0025 + 0.0195, RIB0 + (NRIB - 1) * RIBP / 2))
B.uv_planar(glow, GR['x0'], RIB0 - 0.004, GR['x1'], RIB0 + NRIB * RIBP, 'xz')

# ══ prints: badge on the slant (DEC blocks + DECtalk), control labels, the back panel legends ══
def draw_front(im, dr, font):
    Wp, Hp = im.size
    s = Wp / W
    X = lambda x: (x + W / 2) * s
    Z = lambda z: Hp - (z - 0.0) * s
    f = font(0.0042 * s)
    dr.text((X(-W / 2 + 0.061), Z(0.0615)), 'POWER', font=f, fill=(76, 66, 50, 255), anchor='lm')
    dr.text((X(-W / 2 + 0.061), Z(0.0455)), 'SPEECH', font=f, fill=(76, 66, 50, 255), anchor='lm')
    dr.text((X(ROCK['x']), Z(ROCK['z'] - 0.0145)), 'O   I', font=font(0.0034 * s), fill=(76, 66, 50, 255), anchor='mm')
    dr.text((X((GR['x0'] + GR['x1']) / 2), Z(RIB0 - 0.0085)), 'VOICE', font=font(0.0030 * s), fill=(96, 84, 64, 255), anchor='mm')
front_png = B.decal_png('dt_front', 4096, round(4096 * 0.075 / W), draw_front)
front_proj = B.projector('proj_front', (0, yF - 0.002, 0.0375), (W, 0.075), normal=(0, -1, 0), depth=0.01)
slant_n = Vector((0, -CH, CZ)).normalized()               # the slant faces up-and-forward
slant_c = Vector((0.152, yF + CZ * 0.5, H - CH * 0.5))
def draw_badge(im, dr, font):
    Wp, Hp = im.size
    LG.dec_logo(im, (Wp * 0.02, Hp * 0.22, Wp * 0.50, Hp * 0.78))
    dr.text((Wp * 0.56, Hp * 0.80), 'DECtalk', font=LG.font('arialbd.ttf', Hp * 0.62), fill=(196, 32, 36, 255), anchor='ls')
badge_png = B.decal_png('dt_badge', 2048, 360, draw_badge)
badge_proj = B.projector('proj_badge', tuple(slant_c + slant_n * 0.002), (0.110, 0.0193), normal=tuple(slant_n), up=(0, 1, 0.8), depth=0.006)
def draw_back(im, dr, font):
    Wp, Hp = im.size
    s = Wp / (W - 0.064)
    X = lambda x: (x + (W - 0.064) / 2 + 0.005) * s
    for x, t in ((-0.165, 'COMM'), (-0.110, 'LOCAL'), (-0.059, 'LINE'), (-0.0215, 'AUDIO'), (0.075, 'VOLUME'), (0.140, '120V ~')):
        dr.text((X(x), Hp * 0.12), t, font=font(0.0030 * s), fill=(210, 204, 190, 255), anchor='mt')
    dr.text((X(0.105), Hp * 0.12), 'READY', font=font(0.0026 * s), fill=(210, 204, 190, 255), anchor='mt')
back_png = B.decal_png('dt_back', 2048, round(2048 * 0.022 / (W - 0.064)), draw_back)
back_proj = B.projector('proj_back', (-0.005, D / 2 - 0.001, 0.020), (W - 0.064, 0.022), normal=(0, 1, 0), depth=0.006)
def draw_label(im, dr, font):
    Wp, Hp = im.size
    dr.rounded_rectangle([3, 3, Wp - 3, Hp - 3], radius=10, fill=(222, 216, 200, 255), outline=(140, 130, 110, 255), width=3)
    LG.dec_logo(im, (14, 14, 14 + Wp * 0.30, 14 + Wp * 0.30 * 0.16))
    for i, t in enumerate(['DECtalk DTC01  SPEECH SYNTHESIZER', 'DIGITAL EQUIPMENT CORPORATION', 'MAYNARD, MASSACHUSETTS   1984']):
        dr.text((14, 56 + i * 28), t, font=font(19, bold=i == 0), fill=(44, 38, 30, 255), anchor='lm')
label_png = B.decal_png('dt_label', 640, 150, draw_label)
label_proj = B.projector('proj_label', (0.030, D / 2 + 0.002, 0.070), (0.085, 0.020), normal=(0, 1, 0), depth=0.01)

PUTTY = B.lin('#c7b48c')
m_case = B.plastic('dt_putty', PUTTY, aged=B.lin('#c4a86f'), age=0.45, rough=(0.36, 0.62), grime=(0.22, 0.18, 0.12), grime_amt=0.7, edge=0.28,
                   decals=[dict(img=front_png, proj=front_proj), dict(img=badge_png, proj=badge_proj, rough=0.3, face0=0.2, face1=0.5),
                           dict(img=label_png, proj=label_proj)])
m_stripe = B.plastic('dt_grey', B.lin('#857a64'), aged=B.lin('#86775a'), age=0.3, rough=(0.36, 0.55), grime_amt=0.5, edge=0.35)
m_dark = B.plastic('dt_darkp', B.lin('#1c1a17'), texmix=0.1, rough=(0.42, 0.62), grime_amt=0.3, dust_amt=0.05, edge=0.3,
                   decals=[dict(img=back_png, proj=back_proj)])
B.assign(case, m_case); B.assign(stripe, m_stripe); B.assign(dark, m_dark); B.assign(feet, B.rubber('dt_rub'))
B.assign(metal, B.simple_material('metal', (0.6, 0.6, 0.6), 0.35, 1.0)); B.assign(glow, B.simple_material('glowm', (0.01, 0.01, 0.01), 0.8))
for o in leds: B.assign(o, B.simple_material('ledm_' + o.name, (0.1, 0.1, 0.1), 0.3))

B.sanity([case, stripe, dark, metal, feet, glow] + leds)
body = B.join([case, stripe, dark, feet], 'dt_body')
B.uv_atlas(body); bm_ = B.bake(body, 'dt_body', 2048)
body.data.materials.clear(); body.data.materials.append(B.export_material('dt_body_baked', bm_))
out = [body, metal, glow] + leds
for o in out: B.triangulate(o)
B.log('tris', B.stats(out))
B.export_glb(out, 'dectalk')
