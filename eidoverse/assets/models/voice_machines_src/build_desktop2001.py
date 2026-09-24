"""build_desktop2001.py — a 2001 desktop PC for DAISY: beige mid-tower, 17" CRT, powered speakers, 104-key keyboard,
wheel mouse (Blender 5.2 headless).
bash run_blender.sh work/daisy/props/blender/build_desktop2001.py   (the isolated runner; never blender.exe directly)
Front faces -Y, up +Z, bottom at z = 0. Era mark as homage, drawn by us: the XP-era four-tile flag (sticker, keys)."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import era_bkit as B
import era_logos as LG
from mathutils import Vector, Matrix
import bmesh

B.reset(ao_distance=0.02)
PUTTY = B.lin('#d4cdbb'); PUTTY_AGED = B.lin('#d0c49f'); GREYK = B.lin('#a9a597')

def place(objs, loc, rz=0.0):
    for o in objs:
        B.xform(o, loc, (0, 0, rz))

def rr_y(w, h, r, y, cz, cx=0.0):
    return [(cx + x, y, cz + z) for (x, z) in B.rrect(w, h, r, 6)]

# ═════════════════════════════ 17" CRT monitor ═════════════════════════════
MW, MH = 0.412, 0.392
MZ0 = 0.058                                       # body bottom (on its stand)
OPEN = dict(w=0.352, h=0.270, top=0.030)
OPEN['cz'] = MZ0 + MH - OPEN['top'] - OPEN['h'] / 2
front = B.rbox('mon_front', MW, 0.060, MH, 0.022, n=6, loc=(0, 0.030, MZ0), zbase=True)
B.chamfer(front, width=0.008, segments=5, angle=40, profile=0.5)
cut = [B.loft('mopen', [rr_y(OPEN['w'] + 0.008, OPEN['h'] + 0.008, 0.016, -0.004, OPEN['cz']), rr_y(OPEN['w'], OPEN['h'], 0.012, 0.0, OPEN['cz']),
                        rr_y(OPEN['w'] - 0.012, OPEN['h'] - 0.012, 0.010, 0.012, OPEN['cz']), rr_y(OPEN['w'] - 0.012, OPEN['h'] - 0.012, 0.010, 0.070, OPEN['cz'])])]
CTRL_Z = MZ0 + 0.038
cut.append(B.rbox('ctrlslot', 0.200, 0.004, 0.018, 0.009, loc=(-0.020, 0.0, CTRL_Z)))
cut.append(B.cyl('pwhole', 0.0078, 0.012, 32, loc=(0.150, 0.0, CTRL_Z), rot=(math.pi / 2, 0, 0)))
cut.append(B.cyl('ledhole', 0.0022, 0.012, 16, loc=(0.126, 0.0, CTRL_Z), rot=(math.pi / 2, 0, 0)))
B.boolean(front, cut)
B.chamfer(front, width=0.0005, segments=2, angle=40)
B.finish(front, 40)
# the hood: a smooth taper from the bezel back to the neck (14 rings, eased), no faceting
hood = []
for i in range(14):
    t = i / 13
    e = t * t * (3 - 2 * t)
    hood.append(rr_y(0.400 - 0.180 * e, 0.380 - 0.190 * e, 0.030 + 0.025 * math.sin(math.pi * min(1, t * 1.2)), 0.058 + 0.342 * t,
                     MZ0 + MH / 2 + 0.030 * e))
rear = B.loft('mon_rear', hood)
B.boolean(rear, [B.slots('rvent', 16, 0.014, 0.004, 0.090, 0.03, axis_along='x', loc=(0, 0.25, MZ0 + MH / 2 + 0.16), rot=(math.pi / 2 - 0.25, 0, 0)),
                 B.slots('bvent', 12, 0.014, 0.004, 0.050, 0.03, axis_along='x', loc=(0, 0.40, MZ0 + MH / 2 + 0.03), rot=(0, 0, 0))])
B.chamfer(rear, 0.0012, 2, 40); B.finish(rear, 40)
# stand: swivel foot + neck
foot = B.loft('mon_foot', [[(math.cos(t) * 0.125, 0.12 + math.sin(t) * 0.110, 0.0) for t in [i * math.pi / 24 for i in range(48)]],
                           [(math.cos(t) * 0.123, 0.12 + math.sin(t) * 0.108, 0.012) for t in [i * math.pi / 24 for i in range(48)]],
                           [(math.cos(t) * 0.095, 0.12 + math.sin(t) * 0.085, 0.020) for t in [i * math.pi / 24 for i in range(48)]]])
neck = B.rbox('neck', 0.090, 0.080, MZ0 - 0.015, 0.012, loc=(0, 0.14, 0.017), zbase=True)
B.boolean(foot, [neck], op='UNION'); B.chamfer(foot, 0.0015, 3, 40); B.finish(foot, 40)
# control buttons, power button, LED, tube
btns = [B.rbox(f'mb{i}', 0.020, 0.004, 0.010, 0.0035, loc=(-0.095 + i * 0.037, 0.0003, CTRL_Z)) for i in range(5)]
btns.append(B.cyl('pwbtn', 0.0068, 0.004, 32, loc=(0.150, 0.0003, CTRL_Z), rot=(math.pi / 2, 0, 0)))
btns = B.join(btns, 'mon_btns'); B.chamfer(btns, 0.0008, 3, 30); B.finish(btns, 40)
mled = B.loft('led_mon', [rr_y(0.0042, 0.0042, 0.0021, 0.004, CTRL_Z, 0.126), rr_y(0.0040, 0.0040, 0.0020, -0.0002, CTRL_Z, 0.126)], cap0=False, cap1=True)
TW, TH, R = 0.345, 0.262, 1.6
TCZ = OPEN['cz']
TY0 = 0.020
tedge = math.sqrt(R * R - (TW / 2) ** 2 - (TH / 2) ** 2)
bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=30, y_segments=24, size=0.5)
for v in bm.verts:
    x, z = v.co.x * TW, v.co.y * TH
    v.co = (x, TY0 - (math.sqrt(R * R - x * x - z * z) - tedge), TCZ + z)
bm.normal_update(); bm.faces.ensure_lookup_table()
if bm.faces[0].normal.y > 0: bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
tube = B.mesh_obj('screen_crt', bm); B.finish(tube, 80, weighted=False)
B.uv_planar(tube, -TW / 2, TCZ - TH / 2, TW / 2, TCZ + TH / 2, 'xz')
def draw_mon(im, dr, font):
    Wp, Hp = im.size
    s = Wp / MW
    X = lambda x: (x + MW / 2) * s
    Z = lambda z: Hp - (z - MZ0) * s
    dr.text((X(-0.172), Z(CTRL_Z)), '17" COLOR', font=font(0.0060 * s), fill=(120, 114, 100, 255), anchor='lm')
    for i, t in enumerate(['MENU', '◄', '►', '▲', 'EXIT']):
        dr.text((X(-0.095 + i * 0.037), Z(CTRL_Z - 0.0125)), t, font=LG.font('segoeui.ttf', 0.0034 * s), fill=(110, 104, 92, 255), anchor='mm')
mon_png = B.decal_png('pc_monpanel', 2048, round(2048 * 0.075 / MW), draw_mon)
mon_proj = B.projector('proj_mon', (0, -0.003, MZ0 + 0.0375), (MW, 0.075), normal=(0, -1, 0), depth=0.01)
m_mon = B.plastic('pc_monp', PUTTY, aged=PUTTY_AGED, age=0.25, rough=(0.34, 0.58), grime=(0.2, 0.18, 0.14), grime_amt=0.55, edge=0.25,
                  decals=[dict(img=mon_png, proj=mon_proj)])
m_btn = B.plastic('pc_btnp', B.lin('#bdb6a4'), rough=(0.3, 0.5), grime_amt=0.5, edge=0.3)
for o in (front, rear, foot): B.assign(o, m_mon)
B.assign(btns, m_btn)
mon_objs = [front, rear, foot, btns, mled, tube]
MON = (-0.02, -0.14)
place(mon_objs, (MON[0], MON[1], 0)); mon_proj.location.x += MON[0]; mon_proj.location.y += MON[1]

# ═════════════════════════════ tower ═════════════════════════════
TWd, TD, TH_ = 0.190, 0.440, 0.425
body = B.rbox('tw_body', TWd, TD - 0.022, TH_, 0.004, n=3, loc=(0, 0.022 + (TD - 0.022) / 2, 0.012), zbase=True)
B.chamfer(body, 0.003, 3, 40)
tcut = []
for sx in (-1, 1):                                             # side-cover seams (the cover meets the chassis)
    tcut.append(B.rbox(f'sseam{sx}', 0.002, TD, 0.0008, 0.0, loc=(sx * TWd / 2, 0.24, 0.012 + TH_ - 0.012)))
    tcut.append(B.rbox(f'sseamb{sx}', 0.002, TD, 0.0008, 0.0, loc=(sx * TWd / 2, 0.24, 0.030)))
tcut.append(B.rbox('psu', 0.150, 0.010, 0.086, 0.002, loc=(0, TD, 0.012 + TH_ - 0.055)))
tcut.append(B.rbox('io', 0.045, 0.010, 0.160, 0.002, loc=(-0.045, TD, 0.012 + TH_ - 0.19)))
for i in range(7):                                             # expansion-slot covers (horizontal in a tower)
    tcut.append(B.rbox(f'slot{i}', 0.100, 0.010, 0.012, 0.001, loc=(0.030, TD, 0.012 + 0.035 + i * 0.0205)))
B.boolean(body, tcut); B.chamfer(body, 0.0004, 2, 40); B.finish(body, 40)
# the front bezel: one moulding with the bay openings, button holes, LED holes, intake slots
bez = B.rbox('tw_bezel', TWd + 0.004, 0.030, TH_ + 0.002, 0.008, n=5, loc=(0, 0.012, 0.011), zbase=True)
B.chamfer(bez, 0.006, 5, 40, 0.5)
BAYZ = [0.012 + TH_ - 0.045, 0.012 + TH_ - 0.090]
FLZ = 0.012 + TH_ - 0.145
bcut = [B.rbox(f'bay{i}', 0.150, 0.03, 0.0435, 0.0015, loc=(0, 0.0, z)) for i, z in enumerate(BAYZ)]
bcut.append(B.rbox('flbay', 0.104, 0.03, 0.0265, 0.0015, loc=(0, 0.0, FLZ)))
PWZ = 0.012 + 0.170
bcut.append(B.cyl('pwrecess', 0.0135, 0.010, 40, loc=(0, -0.003, PWZ), rot=(math.pi / 2, 0, 0)))
bcut.append(B.rbox('rstrec', 0.010, 0.010, 0.0045, 0.0015, loc=(0, -0.003, PWZ - 0.030)))
for i, x in enumerate((-0.022, 0.022)):
    bcut.append(B.cyl(f'tled{i}', 0.0021, 0.012, 16, loc=(x, 0.0, PWZ - 0.030), rot=(math.pi / 2, 0, 0)))
bcut.append(B.slots('intake', 14, 0.0085, 0.0036, 0.040, 0.012, axis_along='x', loc=(0, -0.003, 0.012 + 0.052)))
bcut.append(B.rbox('stkpocket', 0.052, 0.004, 0.034, 0.002, loc=(0.0, -0.003, 0.012 + 0.108)))
B.boolean(bez, bcut); B.chamfer(bez, 0.0005, 2, 40); B.finish(bez, 40)
# drive fronts (separate parts), buttons, blank covers
cd = B.rbox('cdrom', 0.146, 0.006, 0.0415, 0.0012, loc=(0, 0.004, BAYZ[0]))
B.boolean(cd, [B.rbox('tray', 0.130, 0.004, 0.0006, 0.0, loc=(0, -0.0005, BAYZ[0] + 0.004)),
               B.rbox('trayv1', 0.0006, 0.004, 0.016, 0.0, loc=(-0.065, -0.0005, BAYZ[0] + 0.012)),
               B.rbox('trayv2', 0.0006, 0.004, 0.016, 0.0, loc=(0.065, -0.0005, BAYZ[0] + 0.012)),
               B.cyl('hp', 0.0019, 0.01, 16, loc=(-0.058, 0.0, BAYZ[0] - 0.012), rot=(math.pi / 2, 0, 0))])
cdparts = [cd, B.rbox('ejct', 0.014, 0.004, 0.0045, 0.0015, loc=(0.052, 0.0008, BAYZ[0] - 0.012)),
           B.cyl('volw', 0.0055, 0.004, 28, loc=(-0.042, 0.0012, BAYZ[0] - 0.012), rot=(0, math.pi / 2, 0))]
blank = B.rbox('blank', 0.146, 0.006, 0.0415, 0.0012, loc=(0, 0.004, BAYZ[1]))
B.boolean(blank, [B.rbox('bgrip', 0.040, 0.004, 0.003, 0.0012, loc=(0, 0.0, BAYZ[1] - 0.010))])
fl = B.rbox('floppy', 0.101, 0.006, 0.0245, 0.0010, loc=(0, 0.004, FLZ))
B.boolean(fl, [B.rbox('flslot', 0.090, 0.012, 0.0032, 0.0012, loc=(-0.004, 0.0, FLZ + 0.004))])
flparts = [fl, B.rbox('flej', 0.013, 0.004, 0.0055, 0.0015, loc=(0.035, 0.0006, FLZ - 0.006)),
           B.rbox('fldoor', 0.086, 0.002, 0.0034, 0.0008, loc=(-0.004, 0.0035, FLZ + 0.004))]
pwb = B.cyl('pwbtn', 0.0115, 0.006, 40, loc=(0, 0.0, PWZ), rot=(math.pi / 2, 0, 0))
rsb = B.rbox('rstbtn', 0.0085, 0.006, 0.0033, 0.0012, loc=(0, 0.0, PWZ - 0.030))
tparts = B.join(cdparts + [blank] + flparts + [pwb, rsb], 'tw_parts'); B.chamfer(tparts, 0.0006, 2, 35); B.finish(tparts, 40)
tleds = []
for nm, x in (('power', -0.022), ('hdd', 0.022)):
    o = B.loft('led_tw_' + nm, [rr_y(0.0040, 0.0040, 0.0020, 0.004, PWZ - 0.030, x), rr_y(0.0038, 0.0038, 0.0019, -0.0002, PWZ - 0.030, x)], cap0=False, cap1=True)
    tleds.append(o)
cdled = B.loft('led_tw_cd', [rr_y(0.004, 0.0016, 0.0008, 0.004, BAYZ[0] - 0.012, 0.030), rr_y(0.004, 0.0016, 0.0008, 0.0008, BAYZ[0] - 0.012, 0.030)], cap0=False, cap1=True)
tleds.append(cdled)
tfeet = B.join([B.cyl(f'tf{i}', 0.010, 0.012, 20, loc=(x, y, 0.006)) for i, (x, y) in enumerate([(-0.07, 0.05), (0.07, 0.05), (-0.07, 0.41), (0.07, 0.41)])], 'tw_feet')
B.chamfer(tfeet, 0.0012, 3, 30); B.finish(tfeet)
# prints: XP sticker, drive legends, side perforation, back panel
def draw_sticker(im, dr, font):
    Wp, Hp = im.size
    dr.rounded_rectangle([2, 2, Wp - 2, Hp - 2], radius=14, fill=(250, 250, 248, 255), outline=(200, 200, 196, 255), width=3)
    dr.text((Wp * 0.5, Hp * 0.17), 'Designed for', font=LG.font('segoeui.ttf', Hp * 0.10), fill=(60, 60, 60, 255), anchor='mm')
    LG.xp_flag(im, (Wp * 0.18, Hp * 0.28, Wp * 0.62, Hp * 0.66))
    dr.text((Wp * 0.64, Hp * 0.60), 'XP', font=LG.font('framdit.ttf', Hp * 0.22), fill=(234, 106, 20, 255), anchor='ls')
    dr.text((Wp * 0.5, Hp * 0.84), 'Microsoft® Windows®', font=LG.font('framd.ttf', Hp * 0.105), fill=(40, 40, 40, 255), anchor='mm')
stk_png = B.decal_png('pc_xpsticker', 512, 335, draw_sticker)
stk_proj = B.projector('proj_stk', (0.0, -0.006, 0.012 + 0.108), (0.050, 0.0327), normal=(0, -1, 0), depth=0.006)
def draw_drives(im, dr, font):
    Wp, Hp = im.size
    s = Wp / 0.150
    X = lambda x: (x + 0.075) * s
    Z = lambda z: Hp - (z - (FLZ - 0.02)) * s
    dr.text((X(-0.060), Z(BAYZ[0] + 0.012)), 'COMPACT DISC  52X', font=LG.font('arialbd.ttf', 0.0034 * s), fill=(96, 92, 84, 255), anchor='lm')
    dr.text((X(0.052), Z(BAYZ[0] - 0.0175)), '▲', font=font(0.0030 * s), fill=(96, 92, 84, 255), anchor='mm')
    dr.text((X(-0.042), Z(FLZ - 0.0065)), '1.44MB', font=font(0.0028 * s), fill=(96, 92, 84, 255), anchor='mm')
drv_png = B.decal_png('pc_drives', 2048, round(2048 * 0.125 / 0.150), draw_drives)
drv_proj = B.projector('proj_drv', (0, -0.004, FLZ - 0.02 + 0.0625), (0.150, 0.125), normal=(0, -1, 0), depth=0.008)
def draw_side(im, dr, font):
    Wp, Hp = im.size
    for j in range(14):
        for i in range(14):
            if (i - 6.5) ** 2 + (j - 6.5) ** 2 > 52: continue
            x, y = Wp * (i + 0.5) / 14, Hp * (j + 0.5) / 14
            dr.ellipse([x - Wp * 0.022, y - Hp * 0.022, x + Wp * 0.022, y + Hp * 0.022], fill=(24, 22, 20, 255))
side_png = B.decal_png('pc_sidevent', 512, 512, draw_side)
side_proj = B.projector('proj_side', (-TWd / 2 - 0.002, 0.30, 0.20), (0.090, 0.090), normal=(-1, 0, 0), depth=0.006)
def draw_back(im, dr, font):
    Wp, Hp = im.size
    s = Wp / 0.160
    cx, cy, r = Wp * 0.5, Hp * 0.24, Wp * 0.26
    for k in range(6): dr.ellipse([cx - r * (1 - k * 0.16), cy - r * (1 - k * 0.16), cx + r * (1 - k * 0.16), cy + r * (1 - k * 0.16)], outline=(40, 38, 34, 255), width=6)
    dr.line([cx - r, cy, cx + r, cy], fill=(40, 38, 34, 255), width=6); dr.line([cx, cy - r, cx, cy + r], fill=(40, 38, 34, 255), width=6)
    y0 = Hp * 0.46
    for i, (col, lab) in enumerate([((150, 90, 200), 'KB'), ((70, 170, 90), 'MOUSE'), ((60, 60, 60), 'USB'), ((60, 60, 60), 'USB'), ((40, 80, 180), 'VGA'), ((200, 60, 150), 'LPT'), ((60, 60, 60), 'COM'), ((130, 200, 90), 'AUDIO')]):
        yy = y0 + i * Hp * 0.055
        dr.rounded_rectangle([Wp * 0.12, yy, Wp * 0.36, yy + Hp * 0.04], radius=6, fill=(*col, 255))
        dr.text((Wp * 0.40, yy + Hp * 0.02), lab, font=font(Hp * 0.028), fill=(210, 206, 196, 255), anchor='lm')
back_png = B.decal_png('pc_back', 1024, 1024, draw_back)
back_proj = B.projector('proj_back', (-0.025, TD + 0.003, 0.012 + TH_ - 0.14), (0.160, 0.260), normal=(0, 1, 0), depth=0.008)
m_tw = B.plastic('pc_towerp', PUTTY, aged=PUTTY_AGED, age=0.25, rough=(0.36, 0.6), grime=(0.2, 0.18, 0.14), grime_amt=0.55, edge=0.25,
                 decals=[dict(img=side_png, proj=side_proj, rough=0.9), dict(img=back_png, proj=back_proj)])
m_bez = B.plastic('pc_bezelp', PUTTY, aged=PUTTY_AGED, age=0.2, rough=(0.32, 0.55), grime=(0.2, 0.18, 0.14), grime_amt=0.6, edge=0.3,
                  decals=[dict(img=stk_png, proj=stk_proj, rough=0.3)])
m_drv = B.plastic('pc_drivep', B.lin('#cfc8b6'), rough=(0.3, 0.52), grime_amt=0.55, edge=0.3, decals=[dict(img=drv_png, proj=drv_proj)])
B.assign(body, m_tw); B.assign(bez, m_bez); B.assign(tparts, m_drv); B.assign(tfeet, B.rubber('pc_rub'))
tower_objs = [body, bez, tparts, tfeet] + tleds
TWR = (0.56, -0.02, -0.30)
place(tower_objs, (TWR[0], TWR[1], 0), TWR[2])
for pj in (stk_proj, drv_proj, side_proj, back_proj):
    pj.matrix_world = Matrix.LocRotScale(Vector((TWR[0], TWR[1], 0)), Matrix.Rotation(TWR[2], 3, 'Z').to_quaternion(), Vector((1, 1, 1))) @ pj.matrix_world

# ═════════════════════════════ speakers ═════════════════════════════
SW, SD, SH = 0.086, 0.110, 0.198
spk_objs, cloths, knobs, sleds = [], [], [], []
for side, (sx, rz) in (('L', (-0.315, 0.22)), ('R', (0.275, -0.22))):
    box = B.rbox(f'spk{side}', SW, SD, SH, 0.014, n=6, zbase=True)
    B.chamfer(box, 0.004, 4, 40, 0.5)
    B.boolean(box, [B.rbox('clothpocket', SW - 0.014, 0.006, SH - 0.050, 0.010, loc=(0, -SD / 2, 0.036 + (SH - 0.050) / 2))])
    B.chamfer(box, 0.0005, 2, 40); B.finish(box, 40)
    cloth = B.rbox(f'glowcloth_{side}', SW - 0.016, 0.003, SH - 0.052, 0.009, loc=(0, -SD / 2 + 0.0035, 0.036 + (SH - 0.052) / 2))
    B.chamfer(cloth, 0.0012, 3, 30); B.finish(cloth, 40)
    extra = []
    if side == 'R':
        knob = B.cyl('knob', 0.0085, 0.010, 40, loc=(-0.018, -SD / 2 - 0.004, 0.018), rot=(math.pi / 2, 0, 0))
        for i in range(24):
            a = i * math.pi / 12
            extra.append(B.rbox(f'kn{i}', 0.0011, 0.0095, 0.0011, 0.0, loc=(-0.018 + math.cos(a) * 0.0086, -SD / 2 - 0.004, 0.018 + math.sin(a) * 0.0086)))
        B.boolean(knob, extra, op='UNION'); B.chamfer(knob, 0.0006, 2, 35); B.finish(knob, 40)
        knobs.append(knob)
        sl = B.loft('led_spk', [rr_y(0.0038, 0.0038, 0.0019, -SD / 2 + 0.003, 0.018, 0.020), rr_y(0.0036, 0.0036, 0.0018, -SD / 2 - 0.0005, 0.018, 0.020)], cap0=False, cap1=True)
        B.boolean(box, [B.cyl('sledhole', 0.0021, 0.01, 16, loc=(0.020, -SD / 2, 0.018), rot=(math.pi / 2, 0, 0))])
        B.finish(box, 40)
        sleds.append(sl)
        group = [box, cloth, knob, sl]
    else:
        group = [box, cloth]
    place(group, (sx, -0.07, 0), rz)
    spk_objs.append(box); cloths.append(cloth)
def draw_spk(im, dr, font):
    Wp, Hp = im.size
    dr.text((Wp * 0.5, Hp * 0.5), 'MULTIMEDIA SPEAKER', font=LG.font('arialbd.ttf', Hp * 0.36), fill=(118, 112, 100, 255), anchor='mm')
spk_png = B.decal_png('pc_spk', 512, 60, draw_spk)
m_spk = B.plastic('pc_spkp', PUTTY, aged=PUTTY_AGED, age=0.25, rough=(0.34, 0.56), grime=(0.2, 0.18, 0.14), grime_amt=0.55, edge=0.25)
for b in spk_objs: B.assign(b, m_spk)
m_cloth = B.plastic('pc_clothp', B.lin('#6f6e6a'), pbrname='Fabric082A', tile=30, texmix=0.5, rough=(0.8, 0.95), grime_amt=0.3, edge=0.05, dust_amt=0.15, bump=0.5)
for c in cloths: B.assign(c, m_cloth)
for k in knobs: B.assign(k, m_btn)

# ═════════════════════════════ keyboard (104) + mouse ═════════════════════════════
KW, KD, KH0, KH1 = 0.455, 0.172, 0.022, 0.034
kprof = [(KD / 2, 0.003, 0.002), (KD / 2 + 0.0006, KH0 - 0.004, 0.004), (KD / 2 - 0.005, KH0, 0.004), (-KD / 2 + 0.007, KH1, 0.006), (-KD / 2, KH1 - 0.007, 0.004), (-KD / 2, 0.003, 0.002)]
kcase = B.prism('kb_case', B.fillet_poly([(-p[0], p[1], p[2]) for p in kprof], 0.003, 4), KW, 'x')
B.chamfer(kcase, width=0.004, segments=4, angle=40)
kal = math.atan2(KH1 - KH0, KD - 0.012)
KP0 = Vector((0, -KD / 2 + 0.005, KH0))
KBK = Vector((0, math.cos(kal), math.sin(kal))); KN = Vector((0, -math.sin(kal), math.cos(kal)))
KDM = Matrix((Vector((1, 0, 0)), KBK, KN)).transposed().to_4x4()
def kdeck(a, b, h=0.0): return KP0 + Vector((a, 0, 0)) + KBK * b + KN * h
U = 0.0190
A0 = -0.212
# rows (back → front) as (label, width, gap_before) in key units, three blocks
main = [
    [('Esc', 1, 0), ('F1', 1, 1), ('F2', 1, 0), ('F3', 1, 0), ('F4', 1, 0), ('F5', 1, 0.5), ('F6', 1, 0), ('F7', 1, 0), ('F8', 1, 0), ('F9', 1, 0.5), ('F10', 1, 0), ('F11', 1, 0), ('F12', 1, 0)],
    [('`', 1, 0), ('1', 1, 0), ('2', 1, 0), ('3', 1, 0), ('4', 1, 0), ('5', 1, 0), ('6', 1, 0), ('7', 1, 0), ('8', 1, 0), ('9', 1, 0), ('0', 1, 0), ('-', 1, 0), ('=', 1, 0), ('Backspace', 2, 0)],
    [('Tab', 1.5, 0), ('Q', 1, 0), ('W', 1, 0), ('E', 1, 0), ('R', 1, 0), ('T', 1, 0), ('Y', 1, 0), ('U', 1, 0), ('I', 1, 0), ('O', 1, 0), ('P', 1, 0), ('[', 1, 0), (']', 1, 0), ('\\', 1.5, 0)],
    [('Caps Lock', 1.75, 0), ('A', 1, 0), ('S', 1, 0), ('D', 1, 0), ('F', 1, 0), ('G', 1, 0), ('H', 1, 0), ('J', 1, 0), ('K', 1, 0), ('L', 1, 0), (';', 1, 0), ("'", 1, 0), ('Enter', 2.25, 0)],
    [('Shift', 2.25, 0), ('Z', 1, 0), ('X', 1, 0), ('C', 1, 0), ('V', 1, 0), ('B', 1, 0), ('N', 1, 0), ('M', 1, 0), (',', 1, 0), ('.', 1, 0), ('/', 1, 0), ('Shift', 2.75, 0)],
    [('Ctrl', 1.5, 0), ('WIN', 1.25, 0), ('Alt', 1.25, 0), ('', 5.75, 0), ('Alt', 1.25, 0), ('WIN', 1.25, 0), ('Menu', 1.25, 0), ('Ctrl', 1.5, 0)],
]
nav = [[('PrtSc', 1, 0), ('ScrLk', 1, 0), ('Pause', 1, 0)], [('Ins', 1, 0), ('Home', 1, 0), ('PgUp', 1, 0)], [('Del', 1, 0), ('End', 1, 0), ('PgDn', 1, 0)], [], [('', 1, 1), ('↑', 1, 0)], [('←', 1, 0), ('↓', 1, 0), ('→', 1, 0)]]
pad = [[], [('Num', 1, 0), ('/', 1, 0), ('*', 1, 0), ('-', 1, 0)], [('7', 1, 0), ('8', 1, 0), ('9', 1, 0), ('+', 1, 0, 2)], [('4', 1, 0), ('5', 1, 0), ('6', 1, 0)], [('1', 1, 0), ('2', 1, 0), ('3', 1, 0), ('Enter', 1, 0, 2)], [('0', 2, 0), ('.', 1, 0)]]
ROWB = [0.128 - (r * U + (0.35 * U if r > 0 else 0)) for r in range(6)]
kk = []
def lay(rows_, a_start):
    for r, row in enumerate(rows_):
        a = a_start
        for k in row:
            lab, wu, gap = k[0], k[1], k[2]
            tall = k[3] if len(k) > 3 else 1
            a += gap * U
            if lab == '' and wu == 1 and gap == 1:
                continue
            bcen = ROWB[r] - (tall - 1) * U / 2
            kk.append(dict(a=a + wu * U / 2, b=bcen, wu=wu, hu=tall, lab=lab)); a += wu * U
lay(main, A0); lay(nav, A0 + 15.25 * U); lay(pad, A0 + 18.5 * U)
kwells = []
for (a0, a1) in ((A0, A0 + 15 * U), (A0 + 15.25 * U, A0 + 18.25 * U), (A0 + 18.5 * U, A0 + 22.5 * U)):
    kwells.append(B.loft(f'kw{a0}', [[tuple(kdeck(x, y, h)) for (x, y) in B.rrect(a1 - a0 + 0.004 + 2 * g, 6.35 * U + 0.004 + 2 * g, 0.003, 4, (a0 + a1) / 2, (ROWB[0] + ROWB[5]) / 2)] for (h, g) in [(0.02, 0.001), (0.0, 0.0), (-0.004, -0.0005)]]))
ledwin = B.loft('ledwin', [[tuple(kdeck(x, y, h)) for (x, y) in B.rrect(0.056, 0.012, 0.003, 4, A0 + 20.5 * U, ROWB[0] + 0.001)] for h in (0.01, -0.0015)])
B.boolean(kcase, kwells + [ledwin])
B.chamfer(kcase, 0.0004, 2, 40); B.finish(kcase, 40)
kfloor = B.join([B.prism(f'kf{i}', B.rrect(a1 - a0 + 0.004, 6.35 * U + 0.004, 0.003, 4, (a0 + a1) / 2, (ROWB[0] + ROWB[5]) / 2), 0.002, 'z')
                 for i, (a0, a1) in enumerate(((A0, A0 + 15 * U), (A0 + 15.25 * U, A0 + 18.25 * U), (A0 + 18.5 * U, A0 + 22.5 * U)))], 'kb_floor')
kfloor.data.transform(KDM); kfloor.data.transform(Matrix.Translation(kdeck(0, 0, -0.003)))
caps_light, caps_grey = [], []
GREY = {'Esc', 'Tab', 'Caps Lock', 'Shift', 'Ctrl', 'WIN', 'Alt', 'Menu', 'Enter', 'Backspace', 'PrtSc', 'ScrLk', 'Pause', 'Ins', 'Home', 'PgUp', 'Del', 'End', 'PgDn', '↑', '←', '↓', '→', 'Num', '/', '*', '-', '+', ''}
for i, k in enumerate(kk):
    wB, dB = k['wu'] * U - 0.0012, k['hu'] * U - 0.0012
    kc = B.keycap(f'pk{i}', wB, dB, wB - 0.0048, dB - 0.005, 0.0095, r=0.0011, dish=0.0004, sculpt=0.0004)
    kc.data.transform(KDM); kc.data.transform(Matrix.Translation(kdeck(k['a'], k['b'], -0.003 + 0.001)))
    fkey = len(k['lab']) > 1 and k['lab'][0] == 'F' and k['lab'][1:].isdigit()
    grey = (k['lab'] in GREY and k['lab'] not in ('/', '*', '-', '+') or fkey) and k['lab'] != ''
    (caps_grey if grey else caps_light).append(kc)
caps_light = B.join(caps_light, 'kb_keys'); caps_grey = B.join(caps_grey, 'kb_keysg')
for o in (caps_light, caps_grey): B.chamfer(o, 0.0004, 2, 35); B.finish(o, 40)
KA0, KA1, KB0_, KB1_ = A0 - 0.006, A0 + 22.5 * U + 0.006, ROWB[5] - 0.012, ROWB[0] + 0.022
def draw_kleg(im, dr, font):
    Wp, Hp = im.size
    A = lambda a: (a - KA0) / (KA1 - KA0) * Wp
    Bv = lambda b: Hp - (b - KB0_) / (KB1_ - KB0_) * Hp
    for k in kk:
        if not k['lab']: continue
        w = k['wu'] * U - 0.006
        x0 = A(k['a'] - w / 2); yt = Bv(k['b'] + (k['hu'] * U - 0.0062) / 2); kh = Bv(k['b'] + (k['hu'] * U - 0.0062) / 2 - (U - 0.0062)) - yt
        col = (58, 56, 52, 255)
        if k['lab'] == 'WIN':
            LG.xp_flag(im, (x0 + kh * 0.14, yt + kh * 0.14, x0 + kh * 0.68, yt + kh * 0.62))
        elif len(k['lab']) <= 2:
            dr.text((x0 + kh * 0.14, yt + kh * 0.08), k['lab'], font=font(kh * 0.36, bold=False), fill=col, anchor='lt')
        else:
            dr.text((x0 + kh * 0.12, yt + kh * 0.72), k['lab'], font=font(kh * 0.2, bold=False), fill=col, anchor='ls')
    for i, t in enumerate(['Num Lock', 'Caps Lock', 'Scroll Lock']):
        dr.text((A(A0 + 19.2 * U + i * 0.0185), Bv(ROWB[0] + 0.012)), t, font=font(Hp * 0.022, bold=False), fill=(80, 78, 72, 255), anchor='mm')
kleg_png = B.decal_png('pc_klegend', 4096, round(4096 * (KB1_ - KB0_) / (KA1 - KA0)), draw_kleg)
kleg_proj = B.projector('proj_kleg', tuple(kdeck((KA0 + KA1) / 2, (KB0_ + KB1_) / 2, 0.02)), (KA1 - KA0, KB1_ - KB0_), normal=tuple(KN), up=tuple(KBK), depth=0.03)
kbleds = []
for i in range(3):
    c = kdeck(A0 + 19.2 * U + i * 0.0185, ROWB[0] + 0.001, -0.001)
    o = B.loft(f'led_kb{i}', [[(c.x + x, c.y + y * math.cos(kal), c.z + y * math.sin(kal)) for (x, y) in B.rrect(0.0035, 0.0035, 0.0017, 4)],
                              [(c.x + x, c.y + y * math.cos(kal), c.z + 0.0012 + y * math.sin(kal)) for (x, y) in B.rrect(0.0033, 0.0033, 0.0016, 4)]], cap0=False, cap1=True)
    kbleds.append(o)
m_keys = B.plastic('pc_keysp', B.lin('#ddd7c8'), aged=B.lin('#d8cca8'), age=0.2, rough=(0.36, 0.55), grime=(0.18, 0.16, 0.12), grime_amt=0.6, edge=0.3,
                   decals=[dict(img=kleg_png, proj=kleg_proj, face0=0.55, face1=0.8)])
m_keysg = B.plastic('pc_keysgp', GREYK, rough=(0.36, 0.55), grime_amt=0.6, edge=0.3, decals=[dict(img=kleg_png, proj=kleg_proj, face0=0.55, face1=0.8)])
m_kfloor = B.plastic('pc_kfloorp', B.lin('#8e897d'), texmix=0.1, rough=(0.5, 0.7), grime_amt=0.5, edge=0.1)
B.assign(kcase, m_tw); B.assign(caps_light, m_keys); B.assign(caps_grey, m_keysg); B.assign(kfloor, m_kfloor)
kbfeet = B.join([B.cyl(f'kbf{i}', 0.006, 0.003, 16, loc=(x, y, 0.0015)) for i, (x, y) in enumerate([(-0.20, -0.07), (0.20, -0.07), (-0.20, 0.07), (0.20, 0.07)])], 'kb_feet')
B.finish(kbfeet); B.assign(kbfeet, B.rubber('pc_rub2'))
# mouse: a smooth shell (scaled sphere, flat bottom), two buttons split by a groove, the wheel
bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=0.5)
for v in bm.verts:
    x, y, z = v.co
    z = max(z, -0.25)
    taper = 1.0 - 0.18 * (y + 0.5)                       # narrower toward the buttons (+y)
    v.co = (x * 0.062 * taper, y * 0.112, (z + 0.25) * 0.052 * (1.0 - 0.3 * (y + 0.5) ** 2))
mouse = B.mesh_obj('mouse', bm)
# buttons + wheel at the far end (+y, toward the monitor); the palm (highest) toward the user
B.boolean(mouse, [B.rbox('msplit', 0.0012, 0.050, 0.03, 0.0, loc=(0, 0.030, 0.035)), B.rbox('mbtn', 0.064, 0.0012, 0.03, 0.0, loc=(0, 0.006, 0.035)),
                  B.rbox('mwheelslot', 0.0085, 0.020, 0.03, 0.002, loc=(0, 0.030, 0.035))])
B.finish(mouse, 35)
wheel = B.cyl('mwheel', 0.0085, 0.0065, 32, loc=(0, 0.030, 0.0215), rot=(0, math.pi / 2, 0))
B.finish(wheel, 40)
B.assign(mouse, m_btn); B.assign(wheel, B.rubber('pc_rub3'))
KBP = (-0.03, -0.40); MSP = (0.30, -0.40, -0.1)
place([kcase, caps_light, caps_grey, kfloor, kbfeet] + kbleds, (KBP[0], KBP[1], 0))
kleg_proj.location.x += KBP[0]; kleg_proj.location.y += KBP[1]
place([mouse, wheel], (MSP[0], MSP[1], 0), MSP[2])
# cables: keyboard + mouse back to the tower, speaker link behind the monitor, monitor cable
def cab(name, pts, r=0.0022):
    return B.cable(name, B.fillet_path(pts, 0.03, 6), r)
cbl = [cab('c_kb', [(KBP[0] + 0.19, KBP[1] + KD / 2, 0.012), (KBP[0] + 0.21, KBP[1] + 0.13, 0.0022), (0.40, -0.12, 0.0022), (0.48, 0.10, 0.0022), (0.52, 0.30, 0.0022), (0.57, 0.40, 0.020)]),
       cab('c_ms', [(MSP[0], MSP[1] + 0.058, 0.012), (MSP[0] + 0.01, MSP[1] + 0.09, 0.0022), (0.42, -0.10, 0.0022), (0.50, 0.12, 0.0022), (0.55, 0.30, 0.0022), (0.60, 0.40, 0.020)]),
       cab('c_spk', [(-0.30, -0.04, 0.020), (-0.26, 0.05, 0.0022), (0.0, 0.26, 0.0022), (0.24, 0.05, 0.0022), (0.26, -0.02, 0.020)], 0.0016),
       cab('c_mon', [(0.0, 0.26, 0.20), (0.05, 0.36, 0.08), (0.20, 0.38, 0.0022), (0.45, 0.40, 0.0022), (0.54, 0.40, 0.06)], 0.0035)]
cables = B.join(cbl, 'pc_cables'); B.finish(cables, 60, weighted=False)
B.assign(cables, B.plastic('pc_cablep', B.lin('#c9c3b2'), rough=(0.4, 0.55), grime_amt=0.3, edge=0.1, dust_amt=0.05))

# ═════════════════════════════ bake + export ═════════════════════════════
__import__('bpy').context.view_layer.update()
B.sanity([front, rear, foot, btns, tube, body, bez, tparts, tfeet, kcase, caps_light, caps_grey, kfloor, mouse, wheel, cables] + spk_objs + cloths + knobs)
mon = B.join([front, rear, foot, btns], 'pc_mon')
B.uv_atlas(mon); mm = B.bake(mon, 'pc_mon', 2048); mon.data.materials.clear(); mon.data.materials.append(B.export_material('pc_mon_baked', mm))
tw = B.join([body, bez, tparts, tfeet], 'pc_tower')
B.uv_atlas(tw); tm = B.bake(tw, 'pc_tower', 2048); tw.data.materials.clear(); tw.data.materials.append(B.export_material('pc_tower_baked', tm))
kb = B.join([kcase, caps_light, caps_grey, kfloor, kbfeet, mouse, wheel], 'pc_kb')
B.uv_atlas(kb, angle=50, margin=0.002); km = B.bake(kb, 'pc_kb', 2048); kb.data.materials.clear(); kb.data.materials.append(B.export_material('pc_kb_baked', km))
spk = B.join(spk_objs + knobs + [cables], 'pc_spk')
B.uv_atlas(spk); sm = B.bake(spk, 'pc_spk', 1024); spk.data.materials.clear(); spk.data.materials.append(B.export_material('pc_spk_baked', sm))
glowcloth = B.join(cloths, 'glowcloth_spk')
B.uv_atlas(glowcloth); gm = B.bake(glowcloth, 'pc_cloth', 1024); glowcloth.data.materials.clear(); glowcloth.data.materials.append(B.export_material('pc_cloth_baked', gm))
leds = [mled] + tleds + kbleds + sleds
for o in leds: B.assign(o, B.simple_material('ledm_' + o.name, (0.1, 0.1, 0.1), 0.3))
B.assign(tube, B.simple_material('crt', (0.02, 0.02, 0.02), 0.2))
out = [mon, tw, kb, spk, glowcloth, tube] + leds
# centre the arrangement on x (the tower sits to the right of the monitor)
xs = [(o.matrix_world @ v.co).x for o in out for v in o.data.vertices]
cx = 0.5 * (min(xs) + max(xs))
for o in out: B.xform(o, (-cx, 0, 0))
B.log(f'centred by {-cx:.3f} m in x')
for o in out: B.triangulate(o)
B.log('tris', B.stats(out))
B.export_glb(out, 'desktop2001')
