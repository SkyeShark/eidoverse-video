"""build_c64.py — the 1982 home computer ("breadbin") and its 13" colour monitor, for DAISY (Blender 5.2 headless).
bash run_blender.sh work/daisy/props/blender/build_c64.py   (the isolated runner; never blender.exe directly)
Computer 404 × 216 × 75 mm; monitor ≈ 368 × 342 × 400 mm. Front faces -Y, up +Z, bottom at z = 0.
The computer sits in front (y < 0), the monitor behind it."""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import era_bkit as B
from mathutils import Vector, Matrix

B.reset(ao_distance=0.015)
rnd = random.Random(64)
COMP_Y = -0.150            # computer centre (y)
MON_Y = 0.130              # monitor front-section centre (y)

# ════════════════════════════════ computer ════════════════════════════════
W, D = 0.404, 0.216
prof = [(0.104, 0.004, 0.004), (0.108, 0.010, 0.0), (0.108, 0.066, 0.004), (0.104, 0.072, 0.006), (0.058, 0.072, 0.012),
        (-0.086, 0.050, 0.010), (-0.101, 0.045, 0.006), (-0.107, 0.035, 0.008), (-0.108, 0.022, 0.006), (-0.106, 0.008, 0.004), (-0.100, 0.004, 0.003)]
case = B.prism('c64_case', B.fillet_poly([(p[0], p[1], p[2]) for p in prof], 0.004, 5), W, 'x')
B.chamfer(case, width=0.006, segments=5, angle=40, profile=0.5)          # rounded side edges
alpha = math.atan2(0.072 - 0.050, 0.058 + 0.086)
P0 = Vector((0, -0.086, 0.050))
BK = Vector((0, math.cos(alpha), math.sin(alpha)))      # up the deck, toward the back
NN = Vector((0, -math.sin(alpha), math.cos(alpha)))     # deck normal
XX = Vector((1, 0, 0))
def deck(a, b, h=0.0):
    return P0 + XX * a + BK * b + NN * h
DECKM = Matrix((XX, BK, NN)).transposed().to_4x4()
def on_deck(ob, a, b, h=0.0):
    ob.data.transform(DECKM); ob.data.transform(Matrix.Translation(deck(a, b, h))); return ob

U1 = 0.01905
ROWB = [0.030 + r * U1 for r in range(5)]              # 0 = space row (front) … 4 = number row (back)
KB0 = -0.1767
rows = [   # back (numbers) → front
    [('←',), ('1', 1, '!'), ('2', 1, '"'), ('3', 1, '#'), ('4', 1, '$'), ('5', 1, '%'), ('6', 1, '&'), ('7', 1, "'"), ('8', 1, '('), ('9', 1, ')'), ('0',), ('+',), ('-',), ('£',), ('CLR|HOME',), ('INST|DEL',)],
    [('CTRL', 1.5), ('Q',), ('W',), ('E',), ('R',), ('T',), ('Y',), ('U',), ('I',), ('O',), ('P',), ('@',), ('*',), ('↑',), ('RESTORE', 1.5)],
    [('RUN|STOP',), ('SHIFT|LOCK',), ('A',), ('S',), ('D',), ('F',), ('G',), ('H',), ('J',), ('K',), ('L',), (':',), (';',), ('=',), ('RETURN', 2)],
    [('CBM',), ('SHIFT', 1.5), ('Z',), ('X',), ('C',), ('V',), ('B',), ('N',), ('M',), (',',), ('.',), ('/',), ('SHIFT', 1.5), ('CRSR|⇕',), ('CRSR|⇔',)],
]
keys = []
for r, row in enumerate(rows):
    a = KB0
    for k in row:
        lab, wu = k[0], (k[1] if len(k) > 1 else 1)
        keys.append(dict(a=a + wu * U1 / 2, b=ROWB[4 - r], wu=wu, lab=lab, alt=(k[2] if len(k) > 2 else None)))
        a += wu * U1
keys.append(dict(a=KB0 + 7.0 * U1, b=ROWB[0], wu=9, lab='', alt=None, space=True))
for i in range(4):
    keys.append(dict(a=0.1624, b=ROWB[4 - i], wu=1.5, lab=f'f{2 * i + 1}|f{2 * i + 2}', alt=None, fkey=True))

# keyboard wells (5 mm deep, drafted), rear grooves, badge recess, LED hole, parting line
WELL_D = 0.005
def well_cutter(name, a0, a1, b0, b1):
    rings = []
    for h, grow in [(0.02, 0.0012), (0.0, 0.0), (-WELL_D, -0.0006)]:
        rings.append([tuple(deck(x, y, h)) for (x, y) in B.rrect(a1 - a0 + 2 * grow, b1 - b0 + 2 * grow, 0.003, 4, (a0 + a1) / 2, (b0 + b1) / 2)])
    return B.loft(name, rings)
cut_list = [well_cutter('wellA', KB0 - 0.003, KB0 + 16 * U1 + 0.003, ROWB[0] - U1 / 2 - 0.003, ROWB[4] + U1 / 2 + 0.003),
            well_cutter('wellB', 0.1624 - 0.75 * U1 - 0.003, 0.1624 + 0.75 * U1 + 0.003, ROWB[1] - U1 / 2 - 0.003, ROWB[4] + U1 / 2 + 0.003)]
for i in range(6):
    yv = 0.066 + i * 0.0056
    g = B.rbox(f'groove{i}', W - 0.024, 0.0011, 0.0016, 0.0005, loc=(0, yv, 0.072))
    cut_list.append(g)
cut_list.append(B.rbox('badgepocket', 0.104, 0.016, 0.0016, 0.002, loc=(-0.121, 0.080, 0.072)))
led_pos = Vector((0.170, 0.0475, 0.0))
led_pos.z = 0.050 + (led_pos.y + 0.086) * math.tan(alpha)
cut_list.append(B.cyl('ledhole', 0.0026, 0.01, 20, loc=tuple(led_pos)))
ring_o = B.rbox('seam_o', W + 0.01, D + 0.01, 0.0007, 0.0, loc=(0, 0, 0.030))
ring_i = B.rbox('seam_i', W - 0.0014, D - 0.0014, 0.002, 0.004, loc=(0, 0, 0.030))
B.boolean(ring_o, ring_i)
cut_list.append(ring_o)
# right side: two joystick ports + power switch + DIN power socket; back: cartridge, cassette, user port, AV
def side_port(name, y, z, w, h, depth=0.008):
    return B.rbox(name, depth, w, h, 0.0015, loc=(W / 2, y, z))
ports = [side_port('joy1', -0.048, 0.026, 0.032, 0.013), side_port('joy2', -0.004, 0.026, 0.032, 0.013),
         side_port('pwsw', 0.040, 0.030, 0.012, 0.012), B.cyl('pwin', 0.0075, 0.010, 24, loc=(W / 2, 0.070, 0.028), rot=(0, math.pi / 2, 0))]
def back_port(name, x, z, w, h):
    return B.rbox(name, w, 0.010, h, 0.0012, loc=(x, D / 2, z))
ports += [back_port('cart', -0.140, 0.030, 0.070, 0.010), back_port('cass', -0.060, 0.030, 0.026, 0.009), back_port('user', 0.080, 0.030, 0.052, 0.009),
          B.cyl('av', 0.0085, 0.012, 24, loc=(0.010, D / 2, 0.034), rot=(math.pi / 2, 0, 0)), B.cyl('rf', 0.0045, 0.012, 20, loc=(0.035, D / 2, 0.034), rot=(math.pi / 2, 0, 0))]
B.boolean(case, cut_list + ports)
B.chamfer(case, width=0.00045, segments=2, angle=40)
B.finish(case, 40)

# well floor plate (dark) sitting inside the wells
floor = B.prism('c64_floor', B.rrect(16 * U1 + 0.004, 5 * U1 + 0.004, 0.003, 4, KB0 + 8 * U1, (ROWB[0] + ROWB[4]) / 2), 0.002, 'z')
on_deck(floor, 0, 0, -WELL_D + 0.001)
floorB = B.prism('c64_floorB', B.rrect(1.5 * U1 + 0.004, 4 * U1 + 0.004, 0.003, 4, 0.1624, (ROWB[1] + ROWB[4]) / 2), 0.002, 'z')
on_deck(floorB, 0, 0, -WELL_D + 0.001)
floor = B.join([floor, floorB], 'c64_floor')
# connector inserts (dark) in the ports, DE-9 shells (metal)
inserts = []
for y in (-0.048, -0.004):
    inserts.append(B.rbox(f'ji{y}', 0.004, 0.028, 0.010, 0.001, loc=(W / 2 - 0.0045, y, 0.026)))
inserts.append(B.rbox('swr', 0.006, 0.007, 0.009, 0.001, loc=(W / 2 - 0.0025, 0.040, 0.030)))
for (x, w) in ((-0.140, 0.066), (-0.060, 0.022), (0.080, 0.048)):
    inserts.append(B.rbox(f'pcb{x}', w, 0.004, 0.0016, 0.0003, loc=(x, D / 2 - 0.004, 0.030)))
inserts = B.join(inserts, 'c64_inserts')
# DE-9 male shells: D-shaped (trapezoid) metal skirts standing out of the insulator, pins inside
def dshape(wt, wb, h, r):
    return B.fillet_poly([(-wt / 2, h / 2), (-wb / 2, -h / 2), (wb / 2, -h / 2), (wt / 2, h / 2)], r, 4)
shells, pins_ = [], []
for y in (-0.048, -0.004):
    outer = B.prism(f'de9o{y}', dshape(0.0188, 0.0154, 0.0068, 0.0014), 0.0036, 'z')
    inner = B.prism(f'de9i{y}', dshape(0.0174, 0.0140, 0.0054, 0.0010), 0.006, 'z')
    B.xform(inner, (0, 0, 0.001))
    B.boolean(outer, inner)
    # the shell's axis → +X (out of the right side), its long axis along Y
    B.xform(outer, (W / 2 - 0.0026, y, 0.026), (0, math.pi / 2, 0))
    shells.append(outer)
    for i, (py, pz) in enumerate([(-0.0054 + k * 0.0027, 0.0014) for k in range(5)] + [(-0.0041 + k * 0.0027, -0.0014) for k in range(4)]):
        pins_.append(B.cyl(f'pin{y}{i}', 0.0005, 0.003, 8, loc=(W / 2 - 0.0026, y + py, 0.026 + pz), rot=(0, math.pi / 2, 0)))
metal_c = B.join(shells + pins_, 'metal_c64_ports')
# badge plate, rubber feet, LED lens
badge = B.rbox('c64_badge', 0.100, 0.0125, 0.0014, 0.0015, loc=(-0.121, 0.080, 0.0718))
B.chamfer(badge, 0.0003, 2, 30)
feet = B.join([B.cyl(f'f{i}', 0.008, 0.004, 20, loc=(x, y, 0.002)) for i, (x, y) in enumerate([(-0.18, -0.09), (0.18, -0.09), (-0.18, 0.09), (0.18, 0.09)])], 'c64_feet')
B.chamfer(feet, 0.001, 3, 30); B.finish(feet)
led = B.loft('led_c64_power', [[(led_pos.x + math.cos(t) * 0.0022, led_pos.y + math.sin(t) * 0.0022, led_pos.z - 0.003) for t in [i * math.pi / 8 for i in range(16)]],
                                [(led_pos.x + math.cos(t) * 0.0022, led_pos.y + math.sin(t) * 0.0022, led_pos.z + 0.0004) for t in [i * math.pi / 8 for i in range(16)]],
                                [(led_pos.x + math.cos(t) * 0.0012, led_pos.y + math.sin(t) * 0.0012, led_pos.z + 0.0012) for t in [i * math.pi / 8 for i in range(16)]]])
B.finish(led, 60, weighted=False)

# keycaps: dished, tapered; brown (F keys lighter)
caps, fcaps = [], []
for i, k in enumerate(keys):
    wB, dB = k['wu'] * U1 - 0.0012, U1 - 0.0012
    kc = B.keycap(f'k{i}', wB, dB, wB - 0.0055, dB - 0.006, 0.0118, r=0.0012, dish=0.0006, sculpt=0.0008)
    on_deck(kc, k['a'], k['b'], -WELL_D + 0.002)
    (fcaps if k.get('fkey') else caps).append(kc)
caps = B.join(caps, 'c64_keys'); B.chamfer(caps, 0.0004, 2, 35); B.finish(caps, 40)
fcaps = B.join(fcaps, 'c64_fkeys'); B.chamfer(fcaps, 0.0004, 2, 35); B.finish(fcaps, 40)

# ── prints
KA0, KA1, KB_0, KB_1 = -0.184, 0.184, 0.014, 0.126
def draw_legends(im, dr, font):
    Wp, Hp = im.size
    A = lambda a: (a - KA0) / (KA1 - KA0) * Wp
    Bv = lambda b: Hp - (b - KB_0) / (KB_1 - KB_0) * Hp        # image top = back
    import era_logos as LG
    for k in keys:
        if not k['lab']: continue
        w = k['wu'] * U1 - 0.0012 - 0.0055
        x0, x1 = A(k['a'] - w / 2), A(k['a'] + w / 2)
        yt, yb = Bv(k['b'] + (U1 - 0.0072) / 2), Bv(k['b'] - (U1 - 0.0072) / 2)
        kh = yb - yt
        col = (40, 34, 26, 255) if k.get('fkey') else (232, 225, 208, 255)
        cx = (x0 + x1) / 2
        parts = k['lab'].split('|')
        if k['lab'] == 'CBM':                         # the C= key
            LG.cbm_mark(im, cx - kh * 0.05, yt + kh * 0.42, kh * 0.22, c_color=col, blue=(150, 190, 240, 255), red=(236, 96, 84, 255))
        elif len(parts) == 2:
            f = font(kh * 0.24); dr.text((cx, yt + kh * 0.28), parts[0], font=f, fill=col, anchor='mm'); dr.text((cx, yt + kh * 0.58), parts[1], font=f, fill=col, anchor='mm')
        elif len(k['lab']) > 1:
            dr.text((cx, yt + kh * 0.40), k['lab'], font=font(kh * 0.24), fill=col, anchor='mm')
        else:
            if k['alt']:
                dr.text((cx, yt + kh * 0.24), k['alt'], font=font(kh * 0.28), fill=col, anchor='mm')
                dr.text((cx, yt + kh * 0.58), k['lab'], font=font(kh * 0.38), fill=col, anchor='mm')
            else:
                dr.text((cx, yt + kh * 0.42), k['lab'], font=font(kh * 0.44), fill=col, anchor='mm')
leg_png = B.decal_png('c64_legends', 4096, round(4096 * (KB_1 - KB_0) / (KA1 - KA0)), draw_legends)
leg_proj = B.projector('proj_leg', tuple(deck(0.0, (KB_0 + KB_1) / 2, 0.02)), (KA1 - KA0, KB_1 - KB_0), normal=tuple(NN), up=tuple(BK), depth=0.03)

def draw_top(im, dr, font):                        # the badge: C= mark, wordmark, rainbow, 64 (homage)
    import era_logos as LG
    Wp, Hp = im.size
    LG.commodore_badge(im, (2, 2, Wp - 2, Hp - 2), plate=(172, 168, 160, 255), ink=(56, 52, 46, 255))
badge_png = B.decal_png('c64_badge', 2048, round(2048 * 0.0125 / 0.100), draw_top)
badge_proj = B.projector('proj_badge', (-0.121, 0.080, 0.0735), (0.100, 0.0125), normal=(0, 0, 1), up=(0, 1, 0), depth=0.004)
def draw_power(im, dr, font):
    Wp, Hp = im.size
    dr.text((Wp / 2, Hp / 2), 'POWER', font=font(Hp * 0.62), fill=(54, 48, 40, 255), anchor='mm')
pw_png = B.decal_png('c64_power', 256, 64, draw_power)
lp = Vector((0.146, 0.0475, 0)); lp.z = 0.050 + (lp.y + 0.086) * math.tan(alpha) + 0.001
pw_proj = B.projector('proj_pw', tuple(lp), (0.026, 0.0065), normal=tuple(NN), up=tuple(BK), depth=0.004)

m_case = B.plastic('c64_beige', B.lin('#b3a98e'), aged=B.lin('#b8a370'), age=0.4, rough=(0.36, 0.62), grime=(0.21, 0.17, 0.11), grime_amt=0.7,
                   decals=[dict(img=pw_png, proj=pw_proj)])
m_floor = B.plastic('c64_well', B.lin('#231e18'), texmix=0.08, rough=(0.55, 0.7), grime=(0.05, 0.04, 0.03), grime_amt=0.3, dust_amt=0.03, edge=0.05)
m_keys = B.plastic('c64_brown', B.lin('#4a3f33'), rough=(0.30, 0.52), grime=(0.08, 0.06, 0.04), grime_amt=0.5, edge=0.35, dust_amt=0.12,
                   decals=[dict(img=leg_png, proj=leg_proj, face0=0.55, face1=0.8, rough=0.35)])
m_fkeys = B.plastic('c64_fk', B.lin('#8a8170'), rough=(0.32, 0.55), grime=(0.12, 0.10, 0.07), grime_amt=0.5, edge=0.3,
                    decals=[dict(img=leg_png, proj=leg_proj, face0=0.55, face1=0.8, rough=0.35)])
m_dark = B.plastic('c64_dark', B.lin('#1c1a17'), pbrname='Plastic012B', rough=(0.4, 0.7), grime_amt=0.3, edge=0.3)
m_badge = B.plastic('c64_badgeplate', B.lin('#b7b2a8'), rough=(0.25, 0.45), grime_amt=0.4, edge=0.4, decals=[dict(img=badge_png, proj=badge_proj)])
m_rubber = B.rubber('c64_rubber')
B.assign(case, m_case); B.assign(floor, m_floor); B.assign(caps, m_keys); B.assign(fcaps, m_fkeys); B.assign(inserts, m_dark)
B.assign(badge, m_badge); B.assign(feet, m_rubber)

# ════════════════════════════════ monitor ════════════════════════════════
MW, MH, MD, FEET = 0.368, 0.337, 0.200, 0.005
BZ = dict(w=0.326, h=0.254, cz=FEET + MH - 0.017 - 0.127)
cab = B.rbox('mon_cab', MW, MD, MH, 0.012, n=6, loc=(0, 0, FEET), zbase=True)
B.chamfer(cab, width=0.005, segments=4, angle=40, profile=0.5)
B.sanity([cab], limit=1.0)
yF = -MD / 2
mcuts = [B.prism('bzopen', B.rrect(BZ['w'], BZ['h'], 0.012, 6, 0, BZ['cz']), 0.12, 'y')]
B.xform(mcuts[0], (0, yF, 0))
# lower panel: flap seam, finger notch, label plate pockets, button hole, LED hole, jack pocket
mcuts.append(B.rbox('flapseam', MW - 0.014, 0.004, 0.0008, 0.0003, loc=(0, yF, FEET + 0.030)))
mcuts.append(B.rbox('flapnotch', 0.070, 0.006, 0.010, 0.003, loc=(0.137, yF, FEET + 0.018)))
mcuts.append(B.rbox('plateL', 0.088, 0.003, 0.0165, 0.0015, loc=(-0.0325, yF, FEET + 0.048)))
mcuts.append(B.rbox('plateR', 0.088, 0.003, 0.0185, 0.0015, loc=(0.0825, yF, FEET + 0.048)))
mcuts.append(B.rbox('btnhole', 0.0215, 0.012, 0.0135, 0.002, loc=(0.143, yF, FEET + 0.047)))
mcuts.append(B.rbox('ledwin', 0.017, 0.004, 0.013, 0.0015, loc=(0.022, yF, FEET + 0.048)))
# top + side vents (slots into the cabinet)
mcuts.append(B.slots('topvent', 24, 0.0105, 0.0035, 0.080, 0.012, axis_along='x', loc=(0, 0.035, FEET + MH), rot=(math.pi / 2, 0, 0)))
for sx in (-1, 1):
    mcuts.append(B.slots(f'sidevent{sx}', 14, 0.0060, 0.0026, 0.042, 0.010, axis_along='x', loc=(sx * MW / 2, 0.040, FEET + MH - 0.050), rot=(0, 0, math.pi / 2)))
B.boolean(cab, mcuts)
B.sanity([cab], limit=1.0)
B.chamfer(cab, width=0.0005, segments=2, angle=40)
B.sanity([cab], limit=1.0)
B.finish(cab, 40)
# the dark bezel: sloping frame to the curved tube (solidified), and the tube
TW, TH, R = 0.282, 0.218, 0.60
TCZ = BZ['cz'] + 0.002
TY0 = yF + 0.040          # tube corner plane (y)
tedge = math.sqrt(R * R - (TW / 2) ** 2 - (TH / 2) ** 2)
def ty(x, z):             # tube surface y at (x, z-TCZ): bulges toward -y
    return TY0 - (math.sqrt(R * R - x * x - z * z) - tedge)
def ring_xz(w, h, r, fy, cz, grow=0.0):
    return [(x, fy(x, zz) if callable(fy) else fy, cz + zz) for (x, zz) in B.rrect(w + 2 * grow, h + 2 * grow, r + grow, 6)]
bz_rings = [ring_xz(BZ['w'] + 0.004, BZ['h'] + 0.004, 0.013, yF + 0.003, BZ['cz']),
            ring_xz(BZ['w'] - 0.010, BZ['h'] - 0.010, 0.013, yF + 0.007, BZ['cz']),
            ring_xz(0.270, 0.208, 0.022, lambda x, z: ty(x * 0.97, z * 0.97) - 0.005, TCZ),
            ring_xz(0.262, 0.200, 0.020, lambda x, z: ty(x, z) - 0.0012, TCZ)]
bezel = B.loft('mon_bezel', bz_rings, cap0=False, cap1=False)
sol = bezel.modifiers.new('sol', 'SOLIDIFY'); sol.thickness = 0.002; sol.offset = -1.0
B.apply_mods(bezel)
B.chamfer(bezel, 0.0006, 2, 40); B.finish(bezel, 40)
import bmesh
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=28, y_segments=22, size=0.5)
for v in bm.verts:
    x, z = v.co.x * TW, v.co.y * TH
    v.co = (x, ty(x, z), TCZ + z)
bm.normal_update()
bm.faces.ensure_lookup_table()
if bm.faces[0].normal.y > 0: bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
tube = B.mesh_obj('screen_crt', bm)
B.finish(tube, 80, weighted=False)
B.uv_planar(tube, -TW / 2, TCZ - TH / 2, TW / 2, TCZ + TH / 2, 'xz')
# rear housing (dark brown), with vent slots; feet; power button; RCA jacks (colour rings + metal)
def rr_xyz(w, h, r, y, cz):
    return [(x, y, cz + zz) for (x, zz) in B.rrect(w, h, r, 6)]
hcz = FEET + MH / 2 + 0.005
housing = B.loft('mon_rear', [rr_xyz(0.336, 0.310, 0.03, MD / 2 - 0.004, hcz), rr_xyz(0.322, 0.294, 0.035, MD / 2 + 0.06, hcz),
                              rr_xyz(0.215, 0.195, 0.045, MD / 2 + 0.19, hcz + 0.01), rr_xyz(0.150, 0.130, 0.040, MD / 2 + 0.20, hcz + 0.01)], cap0=True, cap1=True)
B.boolean(housing, [B.slots('rearvent', 12, 0.012, 0.004, 0.060, 0.03, axis_along='x', loc=(0, MD / 2 + 0.125, hcz + 0.105), rot=(math.pi / 2 - 0.55, 0, 0))])
B.chamfer(housing, 0.0008, 2, 40); B.finish(housing, 40)
button = B.rbox('mon_button', 0.0195, 0.008, 0.0118, 0.002, loc=(0.143, yF + 0.001, FEET + 0.047))
B.chamfer(button, 0.0007, 3, 30); B.finish(button)
mfeet = B.join([B.cyl(f'mf{i}', 0.011, FEET + 0.001, 24, loc=(x, y, (FEET + 0.001) / 2)) for i, (x, y) in enumerate([(-0.15, -0.07), (0.15, -0.07), (-0.15, 0.07), (0.15, 0.07)])], 'mon_feet')
B.chamfer(mfeet, 0.0012, 3, 30); B.finish(mfeet)
jack_rings, jack_metal = [], []
for jx, col in ((0.117, 'y'), (0.152, 'w')):
    jr = B.cyl(f'jr{col}', 0.0055, 0.004, 24, loc=(jx, yF + 0.0015, FEET + 0.017), rot=(math.pi / 2, 0, 0))
    B.boolean(jr, [B.cyl('jh', 0.0022, 0.02, 16, loc=(jx, yF, FEET + 0.017), rot=(math.pi / 2, 0, 0))])
    (jack_rings if col == 'w' else jack_metal).append(jr)
    jm = B.cyl(f'jm{col}', 0.0034, 0.009, 20, loc=(jx, yF + 0.004, FEET + 0.017), rot=(math.pi / 2, 0, 0))
    B.boolean(jm, [B.cyl('jmh', 0.0017, 0.03, 16, loc=(jx, yF, FEET + 0.017), rot=(math.pi / 2, 0, 0))])
    jack_metal.append(jm)
yellow_ring = jack_metal.pop(0)
metal_m = B.join(jack_metal, 'metal_mon_jacks')
mled = B.loft('led_mon_power', [rr_xyz(0.013, 0.009, 0.0012, yF + 0.003, FEET + 0.048), rr_xyz(0.013, 0.009, 0.0012, yF + 0.0012, FEET + 0.048)], cap0=False, cap1=True)
# ── monitor prints
def draw_panel(im, dr, font):
    Wp, Hp = im.size
    s = Wp / MW
    X = lambda x: (x + MW / 2) * s
    Z = lambda z: Hp - (z - FEET) * s
    import era_logos as LG
    dr.rounded_rectangle([X(-0.0765), Z(FEET + 0.0565), X(0.0115), Z(FEET + 0.0395)], radius=0.0015 * s, fill=(104, 98, 88, 255))
    LG.cbm_mark(im, X(-0.0690), Z(FEET + 0.048), 0.0040 * s, c_color=(230, 224, 210, 255), blue=(130, 176, 236, 255), red=(236, 90, 80, 255))
    dr.text((X(-0.0625), Z(FEET + 0.0440)), 'commodore', font=LG.font('segoeui.ttf', 0.0075 * s), fill=(230, 224, 210, 255), anchor='ls')
    LG.rainbow_stripes(im, (X(-0.0205), Z(FEET + 0.0525), X(-0.0045), Z(FEET + 0.0435)))
    dr.rounded_rectangle([X(0.0385), Z(FEET + 0.0575), X(0.1265), Z(FEET + 0.0385)], radius=0.0015 * s, fill=(214, 208, 196, 255), outline=(120, 110, 96, 255), width=3)
    dr.text((X(0.0825), Z(FEET + 0.052)), 'VIDEO MONITOR', font=font(0.0048 * s), fill=(58, 52, 44, 255), anchor='mm')
    dr.text((X(0.0825), Z(FEET + 0.0445)), 'MODEL 1702', font=font(0.0048 * s), fill=(58, 52, 44, 255), anchor='mm')
    dr.text((X(0.143), Z(FEET + 0.036)), 'POWER', font=font(0.0036 * s), fill=(58, 52, 44, 255), anchor='mm')
    dr.text((X(0.117), Z(FEET + 0.0075)), 'VIDEO', font=font(0.0028 * s), fill=(58, 52, 44, 255), anchor='mm')
    dr.text((X(0.152), Z(FEET + 0.0075)), 'AUDIO', font=font(0.0028 * s), fill=(58, 52, 44, 255), anchor='mm')
panel_png = B.decal_png('mon_panel', 2048, round(2048 * 0.07 / MW), draw_panel)
panel_proj = B.projector('proj_panel', (0, yF - 0.003, FEET + 0.035), (MW, 0.07), normal=(0, -1, 0), depth=0.01)
def draw_rear(im, dr, font):
    Wp, Hp = im.size
    dr.rounded_rectangle([4, 4, Wp - 4, Hp - 4], radius=12, fill=(206, 200, 186, 255))
    for i, s_ in enumerate(['COMMODORE VIDEO MONITOR 1702', '120V ~ 60Hz  80W', 'CAUTION: RISK OF ELECTRIC SHOCK', 'DO NOT OPEN']):
        dr.text((Wp / 2, 30 + i * 30), s_, font=font(20, bold=i != 1), fill=(36, 32, 26, 255), anchor='mm')
rear_png = B.decal_png('mon_rear', 512, 150, draw_rear)
rear_proj = B.projector('proj_rear', (0, MD / 2 + 0.203, hcz), (0.10, 0.03), normal=(0, 1, 0), depth=0.02)
m_cab = B.plastic('mon_beige', B.lin('#aba597'), aged=B.lin('#b2a582'), age=0.35, rough=(0.34, 0.6), grime=(0.2, 0.17, 0.12), grime_amt=0.7,
                  decals=[dict(img=panel_png, proj=panel_proj)])
m_bezel = B.plastic('mon_bezel', B.lin('#1b1916'), texmix=0.03, rough=(0.47, 0.53), grime=(0.03, 0.03, 0.025), grime_amt=0.2, dust_amt=0.0, edge=0.2, bump=0.03)
m_rear = B.plastic('mon_brown', B.lin('#3b342b'), texmix=0.2, rough=(0.42, 0.64), grime=(0.12, 0.10, 0.08), grime_amt=0.35, dust_amt=0.08, edge=0.25, decals=[dict(img=rear_png, proj=rear_proj)])
m_yellow = B.plastic('jack_y', B.lin('#d8b82a'), rough=(0.3, 0.5), grime_amt=0.3)
m_white = B.plastic('jack_w', B.lin('#e4e0d6'), rough=(0.3, 0.5), grime_amt=0.3)
B.assign(cab, m_cab); B.assign(bezel, m_bezel); B.assign(housing, m_rear); B.assign(button, m_cab); B.assign(mfeet, B.rubber('mon_rubber'))
B.assign(yellow_ring, m_yellow)
for o in jack_rings: B.assign(o, m_white)
B.assign(tube, B.simple_material('crt_glass', (0.02, 0.025, 0.022), 0.2))
B.assign(led, B.simple_material('led_red', (0.3, 0.02, 0.01), 0.3)); B.assign(mled, B.simple_material('led_red2', (0.3, 0.02, 0.01), 0.3))
B.assign(metal_c, B.simple_material('metal', (0.6, 0.6, 0.6), 0.35, 1.0)); B.assign(metal_m, B.simple_material('metal2', (0.6, 0.6, 0.6), 0.35, 1.0))

# the monitor's speaker sits behind its side vents: planes at the slot floors that the voice lights
gvs = [B.rbox(f'gv{sx}', 0.0006, 14 * 0.0060 + 0.004, 0.046, 0.0, loc=(sx * (MW / 2 - 0.0046), 0.040, FEET + MH - 0.050)) for sx in (-1, 1)]
glow = B.join(gvs, 'glow_vents')
B.uv_planar(glow, -0.01, FEET + MH - 0.08, 0.09, FEET + MH - 0.02, 'yz')
B.assign(glow, B.simple_material('glowm', (0.01, 0.01, 0.01), 0.8))

# ════════════════════════════════ place, bake, export ════════════════════════════════
for o in (case, floor, inserts, badge, feet, caps, fcaps, led, metal_c):
    B.xform(o, (0, COMP_Y, 0))
for o in (cab, bezel, housing, button, mfeet, yellow_ring, *jack_rings, tube, metal_m, mled, glow):
    B.xform(o, (0, MON_Y, 0))
for pj in (leg_proj, badge_proj, pw_proj): pj.location.y += COMP_Y
for pj in (panel_proj, rear_proj): pj.location.y += MON_Y
__import__('bpy').context.view_layer.update()
B.sanity([case, floor, inserts, badge, feet, caps, fcaps, cab, bezel, housing, button, mfeet, yellow_ring, *jack_rings, tube, metal_m, mled, metal_c, led])
comp = B.join([case, floor, inserts, badge, feet], 'c64_comp')
B.uv_atlas(comp); cm = B.bake(comp, 'c64_comp', 2048)
comp.data.materials.clear(); comp.data.materials.append(B.export_material('c64_comp_baked', cm))
keyset = B.join([caps, fcaps], 'c64_keys')
B.uv_atlas(keyset, angle=50, margin=0.002); km = B.bake(keyset, 'c64_keys', 2048)
keyset.data.materials.clear(); keyset.data.materials.append(B.export_material('c64_keys_baked', km))
mon = B.join([cab, bezel, housing, button, mfeet, yellow_ring] + jack_rings, 'c64_mon')
B.uv_atlas(mon); mm = B.bake(mon, 'c64_mon', 2048)
mon.data.materials.clear(); mon.data.materials.append(B.export_material('c64_mon_baked', mm))
metal = B.join([metal_c, metal_m], 'metal_c64')
out = [comp, keyset, mon, tube, led, mled, metal, glow]
for o in out: B.triangulate(o)
B.log('tris', B.stats(out))
B.export_glb(out, 'c64')
