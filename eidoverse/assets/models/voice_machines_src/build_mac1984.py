"""build_mac1984.py — the beige 1984 all-in-one compact, its small keyboard and one-button mouse, for DAISY.
bash run_blender.sh work/daisy/props/blender/build_mac1984.py   (the isolated runner; never blender.exe directly)
Compact 344 × 246 × 276 mm. Front faces -Y, up +Z, bottom at z = 0."""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import era_bkit as B
from mathutils import Vector, Matrix
import bmesh

B.reset(ao_distance=0.015)
W, D, H, FOOT = 0.246, 0.276, 0.344, 0.036
MAC_Y = 0.060                        # the compact's centre (y); keyboard in front of it, mouse to the right
yF = -D / 2
FPD = 0.070                          # depth of the front bezel moulding
REC = dict(w=0.194, h=0.162, top=H - 0.037, r=0.016)
REC['cz'] = REC['top'] - REC['h'] / 2
BEIGE = B.lin('#bfae86'); AGED = B.lin('#bba26a')

# ══ front bezel moulding: one mass with the drafted screen recess, floppy slot, thumbwheel notch ══
front = B.rbox('mac_front', W, FPD, H - FOOT, 0.010, n=6, loc=(0, yF + FPD / 2, FOOT), zbase=True)
B.chamfer(front, width=0.005, segments=5, angle=40, profile=0.5)
def rr_y(w, h, r, y, cz):
    return [(x, y, cz + z) for (x, z) in B.rrect(w, h, r, 6)]
recess = B.loft('recess', [rr_y(REC['w'] + 0.006, REC['h'] + 0.006, REC['r'] + 0.003, yF - 0.006, REC['cz']),
                           rr_y(REC['w'], REC['h'], REC['r'], yF, REC['cz']),
                           rr_y(0.186, 0.136, 0.012, yF + 0.030, REC['cz'] - 0.002),
                           rr_y(0.186, 0.136, 0.012, yF + 0.064, REC['cz'] - 0.002)])
FL = dict(x0=0.017, x1=0.106, z=0.097)
surround = B.rbox('flsur', FL['x1'] - FL['x0'], 0.004, 0.014, 0.004, loc=((FL['x0'] + FL['x1']) / 2, yF, FL['z']))
slot = B.rbox('flslot', 0.077, 0.040, 0.0032, 0.0012, loc=(0.0595, yF + 0.018, FL['z'] + 0.0005))
eject = B.cyl('eject', 0.0011, 0.01, 12, loc=(0.1015, yF, FL['z']), rot=(math.pi / 2, 0, 0))
wheelnotch = B.rbox('wnotch', 0.030, 0.012, 0.008, 0.002, loc=(-0.080, yF + 0.004, FOOT))
APPLE = dict(x=-0.077, z=0.061, w=0.0185, h=0.0205)
badgepocket = B.rbox('bpocket', APPLE['w'], 0.0016, APPLE['h'], 0.0028, loc=(APPLE['x'], yF, APPLE['z']))
B.boolean(front, [recess, surround, slot, eject, wheelnotch, badgepocket])
B.chamfer(front, width=0.0005, segments=2, angle=40)
B.finish(front, 40)

# ══ rear housing: the main body with the carrying-handle groove, top + side vents, back port panel ══
RD = D - FPD + 0.006
rear = B.rbox('mac_rear', W, RD, H - FOOT, 0.010, n=6, loc=(0, D / 2 - RD / 2, FOOT), zbase=True)
B.chamfer(rear, width=0.005, segments=5, angle=40, profile=0.5)
groove = B.prism('groove', B.rrect(0.028, 0.034, 0.0139, 8, D / 2 - 0.062, H), 0.186, 'x')
B.chamfer(groove, width=0.012, segments=6, angle=40, profile=0.5)
cuts = [groove, B.slots('topvent', 16, 0.0095, 0.0032, 0.024, 0.014, axis_along='x', loc=(0, D / 2 - 0.022, H), rot=(math.pi / 2, 0, 0))]
for sx in (-1, 1):
    cuts.append(B.slots(f'sidevent{sx}', 13, 0.0068, 0.0028, 0.044, 0.012, axis_along='x', loc=(sx * W / 2, D / 2 - 0.085, FOOT + 0.052), rot=(0, 0, math.pi / 2)))
cuts.append(B.rbox('portpanel', 0.200, 0.008, 0.030, 0.003, loc=(0, D / 2, FOOT + 0.034)))
B.boolean(rear, cuts)
B.chamfer(rear, width=0.0005, segments=2, angle=40)
B.finish(rear, 40)

# the speaker behind the side vents: planes at the slot floors that the voice lights (glow_vents)
glows = []
for sx in (-1, 1):
    g = B.rbox(f'gv{sx}', 0.0006, 13 * 0.0068 + 0.004, 0.048, 0.0, loc=(sx * (W / 2 - 0.0056), D / 2 - 0.085, FOOT + 0.052))
    glows.append(g)
glow = B.join(glows, 'glow_vents')
B.uv_planar(glow, D / 2 - 0.14, FOOT + 0.02, D / 2 - 0.03, FOOT + 0.08, 'yz')
B.assign(glow, B.simple_material('glowm', (0.01, 0.01, 0.01), 0.8))

# ══ the recessed foot (base) with the keyboard jack, rubber feet ══
base = B.rbox('mac_base', W - 0.014, D - 0.014, FOOT + 0.003, 0.006, n=5, loc=(0, 0.001, 0), zbase=True)
B.chamfer(base, width=0.0025, segments=3, angle=40)
B.boolean(base, [B.rbox('kjack', 0.013, 0.012, 0.010, 0.001, loc=(0.087, yF + 0.007, 0.019))])
B.chamfer(base, width=0.0004, segments=2, angle=40)
B.finish(base, 40)
dark = [B.rbox('kjin', 0.011, 0.004, 0.008, 0.0008, loc=(0.087, yF + 0.011, 0.019)),
        B.rbox('pp_back', 0.196, 0.003, 0.026, 0.002, loc=(0, D / 2 - 0.003, FOOT + 0.034))]
# back connectors: two DB-9, one DB-19, audio jack, IEC socket, rocker switch (metal shells + dark inserts)
def dsub(name, wt, wb, h, x, z, depth=0.004):
    o = B.prism(name, B.fillet_poly([(-wt / 2, h / 2), (-wb / 2, -h / 2), (wb / 2, -h / 2), (wt / 2, h / 2)], 0.0012, 4), depth, 'y')
    i = B.prism(name + 'i', B.fillet_poly([(-wt / 2 + 0.0008, h / 2 - 0.0008), (-wb / 2 + 0.0008, -h / 2 + 0.0008), (wb / 2 - 0.0008, -h / 2 + 0.0008), (wt / 2 - 0.0008, h / 2 - 0.0008)], 0.0008, 4), depth * 2, 'y')
    B.xform(i, (0, -0.0015, 0)); B.boolean(o, i)
    B.xform(o, (x, D / 2 - 0.002, z))
    return o
metal_parts = [dsub('db9a', 0.0188, 0.0154, 0.0068, -0.075, FOOT + 0.034), dsub('db9b', 0.0188, 0.0154, 0.0068, -0.045, FOOT + 0.034),
               dsub('db19', 0.0355, 0.0320, 0.0068, 0.000, FOOT + 0.034),
               B.cyl('aud', 0.0035, 0.004, 16, loc=(0.040, D / 2 - 0.002, FOOT + 0.034), rot=(math.pi / 2, 0, 0))]
dark.append(B.rbox('iec', 0.024, 0.006, 0.016, 0.002, loc=(0.075, D / 2 - 0.002, FOOT + 0.034)))
rocker = B.rbox('rocker', 0.012, 0.006, 0.016, 0.0015, loc=(-0.100, D / 2 - 0.0005, FOOT + 0.034), )
dark.append(rocker)
dark = B.join(dark, 'mac_dark'); B.chamfer(dark, 0.0004, 2, 40); B.finish(dark, 40)
metal = B.join(metal_parts, 'metal_mac'); B.finish(metal, 40)
feet = B.join([B.cyl(f'ft{i}', 0.009, 0.003, 20, loc=(x, y, 0.0015)) for i, (x, y) in enumerate([(-0.10, -0.11), (0.10, -0.11), (-0.10, 0.11), (0.10, 0.11)])], 'mac_feet')
B.chamfer(feet, 0.0008, 2, 30); B.finish(feet)
# brightness thumbwheel under the front-left, in the foot recess
wheel = B.cyl('wheel', 0.0105, 0.006, 40, loc=(-0.080, yF + 0.006, FOOT - 0.001), rot=(0, math.pi / 2, 0))
ridges = [B.rbox(f'rg{i}', 0.0064, 0.0012, 0.0012, 0.0, loc=(-0.080, yF + 0.006 + math.cos(i * math.pi / 12) * 0.0106, FOOT - 0.001 + math.sin(i * math.pi / 12) * 0.0106)) for i in range(24)]
B.boolean(wheel, ridges, op='UNION'); B.finish(wheel, 40)
B.boolean(base, [B.cyl('wheelcut', 0.0125, 0.009, 32, loc=(-0.080, yF + 0.006, FOOT - 0.001), rot=(0, math.pi / 2, 0))])

# ══ the tube: bulged black glass behind the recess (screen_crt) ══
TW, TH, R = 0.200, 0.152, 0.55
TCZ = REC['cz'] - 0.002
TY0 = yF + 0.042
tedge = math.sqrt(R * R - (TW / 2) ** 2 - (TH / 2) ** 2)
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=26, y_segments=20, size=0.5)
for v in bm.verts:
    x, z = v.co.x * TW, v.co.y * TH
    v.co = (x, TY0 - (math.sqrt(R * R - x * x - z * z) - tedge), TCZ + z)
bm.normal_update(); bm.faces.ensure_lookup_table()
if bm.faces[0].normal.y > 0: bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
tube = B.mesh_obj('screen_crt', bm)
B.finish(tube, 80, weighted=False)
B.uv_planar(tube, -TW / 2, TCZ - TH / 2, TW / 2, TCZ + TH / 2, 'xz')

# ══ prints on the compact: floppy surround shading is geometry; a small rear label (generic) ══
def draw_rear(im, dr, font):
    Wp, Hp = im.size
    dr.rounded_rectangle([3, 3, Wp - 3, Hp - 3], radius=10, fill=(218, 210, 188, 255), outline=(150, 140, 118, 255), width=3)
    for i, s_ in enumerate(['Macintosh', 'Apple Computer, Inc.  Cupertino, CA', 'MODEL M0001   128K', '120V ~ 60Hz  60W   1984']):
        dr.text((Wp / 2, 26 + i * 27), s_, font=font(20 if i == 0 else 17, bold=i == 0), fill=(52, 46, 36, 255), anchor='mm')
rear_png = B.decal_png('mac_rear', 512, 128, draw_rear)
rear_proj = B.projector('proj_mrear', (0, D / 2 + 0.002, FOOT + 0.085), (0.090, 0.0225), normal=(0, 1, 0), depth=0.01)
def draw_apple(im, dr, font):                     # the six-band apple, homage
    import era_logos as LG
    Wp, Hp = im.size
    LG.rainbow_apple(im, (Wp * 0.12, Hp * 0.08, Wp * 0.88, Hp * 0.92))
apple_png = B.decal_png('mac_apple', 512, round(512 * APPLE['h'] / APPLE['w']), draw_apple)
apple_proj = B.projector('proj_apple', (APPLE['x'], yF - 0.001, APPLE['z']), (APPLE['w'], APPLE['h']), normal=(0, -1, 0), depth=0.004)
m_beige = B.plastic('mac_beige', BEIGE, aged=AGED, age=0.4, rough=(0.36, 0.6), grime=(0.2, 0.16, 0.1), grime_amt=0.65, edge=0.28,
                    decals=[dict(img=rear_png, proj=rear_proj), dict(img=apple_png, proj=apple_proj, rough=0.22)])
m_foot = B.plastic('mac_footp', B.lin('#ad9c76'), aged=B.lin('#a8915f'), age=0.3, rough=(0.42, 0.66), grime_amt=0.8, edge=0.2)
m_dark = B.plastic('mac_darkp', B.lin('#1d1a16'), pbrname='Plastic012B', rough=(0.4, 0.65), grime_amt=0.3, edge=0.3)
m_rub = B.rubber('mac_rub')
for o in (front, rear): B.assign(o, m_beige)
B.assign(base, m_foot); B.assign(dark, m_dark); B.assign(feet, m_rub); B.assign(wheel, m_dark)
B.assign(tube, B.simple_material('crt', (0.01, 0.012, 0.012), 0.2)); B.assign(metal, B.simple_material('metal', (0.6, 0.6, 0.6), 0.35, 1.0))

# ══ keyboard: wedge case with a drafted key well, 58 dished keys, legends, coiled cord ══
KW, KD, KH0, KH1 = 0.332, 0.146, 0.024, 0.036
KB_Y = -0.225                                   # keyboard centre (y), in front of the compact
kprof = [(KD / 2, 0.002, 0.002), (KD / 2 + 0.0005, KH0 - 0.004, 0.004), (KD / 2 - 0.004, KH0, 0.004), (-KD / 2 + 0.006, KH1, 0.005), (-KD / 2, KH1 - 0.006, 0.004), (-KD / 2, 0.002, 0.002)]
kcase = B.prism('mac_kbcase', B.fillet_poly([(-p[0], p[1], p[2]) for p in kprof], 0.003, 4), KW, 'x')
B.chamfer(kcase, width=0.004, segments=4, angle=40)
kal = math.atan2(KH1 - KH0, KD - 0.010)
KP0 = Vector((0, -KD / 2 + 0.004, KH0))            # deck front edge (y = front)
KBK = Vector((0, math.cos(kal), math.sin(kal))); KN = Vector((0, -math.sin(kal), math.cos(kal)))
KDM = Matrix((Vector((1, 0, 0)), KBK, KN)).transposed().to_4x4()
def kdeck(a, b, h=0.0): return KP0 + Vector((a, 0, 0)) + KBK * b + KN * h
U = 0.019
krows = [   # back → front
    [('`',), ('1',), ('2',), ('3',), ('4',), ('5',), ('6',), ('7',), ('8',), ('9',), ('0',), ('-',), ('=',), ('Backspace', 2)],
    [('Tab', 1.5), ('Q',), ('W',), ('E',), ('R',), ('T',), ('Y',), ('U',), ('I',), ('O',), ('P',), ('[',), (']',), ('\\', 1.5)],
    [('Caps Lock', 1.75), ('A',), ('S',), ('D',), ('F',), ('G',), ('H',), ('J',), ('K',), ('L',), (';',), ("'",), ('Return', 2.25)],
    [('Shift', 2.25), ('Z',), ('X',), ('C',), ('V',), ('B',), ('N',), ('M',), (',',), ('.',), ('/',), ('Shift', 2.75)],
    [('Option', 1.5), ('⌘', 1.5), ('', 9), ('Enter', 1.5), ('Option', 1.5)],
]
KROW_B = [0.105 - r * U for r in range(5)]      # b of each row (0 = back)
kkeys = []
for r, row in enumerate(krows):
    a = -7.5 * U
    for k in row:
        wu = k[1] if len(k) > 1 else 1
        kkeys.append(dict(a=a + wu * U / 2, b=KROW_B[r], wu=wu, lab=k[0])); a += wu * U
kwell = B.loft('kwell', [[tuple(kdeck(x, y, h)) for (x, y) in B.rrect(15 * U + 0.006 + 2 * g, 5 * U + 0.006 + 2 * g, 0.003, 4, 0, (KROW_B[0] + KROW_B[4]) / 2)] for (h, g) in [(0.02, 0.001), (0.0, 0.0), (-0.004, -0.0005)]])
B.boolean(kcase, [kwell])
B.chamfer(kcase, width=0.0004, segments=2, angle=40)
B.finish(kcase, 40)
kfloor = B.prism('kfloor', B.rrect(15 * U + 0.006, 5 * U + 0.006, 0.003, 4, 0, (KROW_B[0] + KROW_B[4]) / 2), 0.002, 'z')
kfloor.data.transform(KDM); kfloor.data.transform(Matrix.Translation(kdeck(0, 0, -0.004 + 0.001)))
kcaps = []
for i, k in enumerate(kkeys):
    wB, dB = k['wu'] * U - 0.0012, U - 0.0012
    kc = B.keycap(f'mk{i}', wB, dB, wB - 0.0048, dB - 0.005, 0.0100, r=0.0011, dish=0.0005, sculpt=0.0005)
    kc.data.transform(KDM); kc.data.transform(Matrix.Translation(kdeck(k['a'], k['b'], -0.004 + 0.002)))
    kcaps.append(kc)
kcaps = B.join(kcaps, 'mac_keys'); B.chamfer(kcaps, 0.0004, 2, 35); B.finish(kcaps, 40)
KA0, KA1, KB0_, KB1_ = -0.150, 0.150, KROW_B[4] - 0.012, KROW_B[0] + 0.012
def draw_klegend(im, dr, font):
    Wp, Hp = im.size
    A = lambda a: (a - KA0) / (KA1 - KA0) * Wp
    Bv = lambda b: Hp - (b - KB0_) / (KB1_ - KB0_) * Hp
    for k in kkeys:
        if not k['lab']: continue
        w = k['wu'] * U - 0.0012 - 0.0048
        x0 = A(k['a'] - w / 2); yt = Bv(k['b'] + (U - 0.0062) / 2); kh = Bv(k['b'] - (U - 0.0062) / 2) - yt
        col = (70, 64, 52, 255)
        if len(k['lab']) == 1:
            dr.text((x0 + kh * 0.16, yt + kh * 0.12), k['lab'], font=font(kh * 0.34, bold=False), fill=col, anchor='lt')
        else:
            dr.text((x0 + kh * 0.14, yt + kh * 0.78), k['lab'], font=font(kh * 0.2, bold=False), fill=col, anchor='ls')
kleg_png = B.decal_png('mac_legends', 4096, round(4096 * (KB1_ - KB0_) / (KA1 - KA0)), draw_klegend)
kleg_proj = B.projector('proj_kleg', tuple(kdeck(0.0, (KB0_ + KB1_) / 2, 0.02)), (KA1 - KA0, KB1_ - KB0_), normal=tuple(KN), up=tuple(KBK), depth=0.03)
m_keys = B.plastic('mac_keysp', B.lin('#cdc2a2'), aged=B.lin('#c9b88d'), age=0.25, rough=(0.34, 0.55), grime=(0.18, 0.15, 0.1), grime_amt=0.6, edge=0.3,
                   decals=[dict(img=kleg_png, proj=kleg_proj, face0=0.55, face1=0.8)])
B.assign(kcase, m_beige); B.assign(kfloor, m_dark); B.assign(kcaps, m_keys)
kfeet = B.join([B.cyl(f'kf{i}', 0.006, 0.002, 16, loc=(x, y, 0.001)) for i, (x, y) in enumerate([(-0.15, -0.06), (0.15, -0.06), (-0.15, 0.06), (0.15, 0.06)])], 'mac_kfeet')
B.finish(kfeet); B.assign(kfeet, m_rub)

# ══ mouse: body with a pocket for its one button (a separate part), cords ══
MS_X, MS_Y, MROT = 0.245, -0.210, -0.12
mbody = B.rbox('mac_mouse', 0.058, 0.108, 0.030, 0.011, n=6, zbase=True)
B.chamfer(mbody, width=0.007, segments=5, angle=40)
B.boolean(mbody, [B.rbox('btnpocket', 0.0505, 0.0345, 0.010, 0.0015, loc=(0, 0.033, 0.030))])
B.chamfer(mbody, width=0.0004, segments=2, angle=40); B.finish(mbody, 40)
btn = B.rbox('mac_mbutton', 0.0495, 0.0335, 0.0034, 0.0012, loc=(0, 0.033, 0.0276))
B.chamfer(btn, 0.0008, 3, 30); B.finish(btn, 40)
for o in (mbody, btn):
    B.xform(o, (MS_X, MS_Y, 0), (0, 0, MROT))
m_mouse = B.plastic('mac_mousep', BEIGE, aged=AGED, age=0.3, rough=(0.32, 0.55), grime_amt=0.7, edge=0.35)
B.assign(mbody, m_mouse); B.assign(btn, m_mouse)
ca, sa = math.cos(MROT), math.sin(MROT)
def mw(x, y, z): return (MS_X + x * ca - y * sa, MS_Y + x * sa + y * ca, z)
mcord = B.cable('mac_mcord', B.fillet_path([mw(0, 0.054, 0.012), mw(0, 0.075, 0.0016), (0.205, -0.10, 0.0016), (0.150, -0.02, 0.0016), (0.142, 0.08, 0.0016),
                                             (0.128, D / 2 + 0.030, 0.004), (0.080, D / 2 + 0.018, 0.030), (0.070, D / 2 + 0.002, FOOT + 0.034)], 0.02, 6), 0.0016)
# coiled keyboard cord: from the keyboard's back-right to the foot's jack
pA = Vector((0.12, KB_Y + KD / 2 + 0.004, 0.012)); pB = Vector((0.087, yF + 0.007 + MAC_Y, 0.019))
coil = []
for i in range(0, 481):
    t = i / 480; a = t * 11 * 2 * math.pi
    c = pA.lerp(pB, t)
    coil.append((c.x + math.cos(a) * 0.0045, c.y, c.z + math.sin(a) * 0.0045 + math.sin(t * math.pi) * 0.004))
kcord = B.cable('mac_kcord', coil, 0.0011)
cords = B.join([mcord, kcord], 'mac_cords'); B.finish(cords, 60, weighted=False)
B.assign(cords, B.plastic('mac_cordp', B.lin('#b3a684'), rough=(0.38, 0.55), grime_amt=0.4, edge=0.1, dust_amt=0.05))

# ══ place the keyboard, then bake + export ══
for o in (kcase, kfloor, kcaps, kfeet):
    B.xform(o, (0, KB_Y, 0))
kleg_proj.location.y += KB_Y
for o in (front, rear, base, dark, metal, feet, wheel, tube, glow):
    B.xform(o, (0, MAC_Y, 0))
rear_proj.location.y += MAC_Y; apple_proj.location.y += MAC_Y
__import__('bpy').context.view_layer.update()
B.sanity([front, rear, base, dark, metal, feet, wheel, tube, kcase, kfloor, kcaps, kfeet, mbody, btn, cords])
B.delete_faces(front, lambda c, n: n.y > 0.9 and c.y > yF + FPD - 0.004 + MAC_Y)     # the moulding's back, inside the housing
body = B.join([front, rear, base, dark, feet, wheel], 'mac_body')
B.uv_atlas(body); bm_ = B.bake(body, 'mac_body', 2048)
body.data.materials.clear(); body.data.materials.append(B.export_material('mac_body_baked', bm_))
kb = B.join([kcase, kfloor, kcaps, kfeet], 'mac_kb')
B.uv_atlas(kb, angle=50, margin=0.002); km = B.bake(kb, 'mac_kb', 2048)
kb.data.materials.clear(); kb.data.materials.append(B.export_material('mac_kb_baked', km))
ms = B.join([mbody, btn, cords], 'mac_mouse')
B.uv_atlas(ms, margin=0.006); mm = B.bake(ms, 'mac_mouse', 1024)
ms.data.materials.clear(); ms.data.materials.append(B.export_material('mac_mouse_baked', mm))
out = [body, kb, ms, tube, metal, glow]
for o in out: B.triangulate(o)
B.log('tris', B.stats(out))
B.export_glb(out, 'mac1984')
