"""era1_teletype.py — a Teletype ASR-33 on its pedestal (1966) as a hero asset.
blender --background --factory-startup --python era1_teletype.py
-> work/daisy/props/assets/era1/teletype.glb, teletype_mask.png, teletype_layout.json

Moulded khaki lower housing (side-profile mass with the keyboard well pocket, band
recess, parting-line groove, back vents), cream typing-unit cover as a real shell
(window opening with a lip), platen + knob, ribbon spools, type-box rail, mechanism
block, paper-roll cradle, grey right plate with call-control bezels, brushed front
band + mode knob, paper-tape reader/punch with knobs, lid, lever and chad box,
sheet-metal pedestal with the arch cut through, sled feet, power cord.
The keyboard (legend atlas) and the printed paper are built by the module.
Blender frame: front = -Y, up = +Z. Layout JSON is in three.js coordinates.
"""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(__file__))
import importlib
import era1_kit as K
importlib.reload(K)
import bpy, bmesh
from mathutils import Vector, Matrix, Euler, Quaternion

K.reset()
PARTS, DECALS, MOVING = [], [], []
LAYOUT = {}


def P(x, y, z):
    """three.js (x, y-up, z-toward-camera) -> Blender (x, -z, y)."""
    return Vector((x, -z, y))


def T3(v):
    return [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]


def obj(name, bm, roles, bevel=0.003, seg=3, angle=35, bucket=None):
    ob = K.new_mesh_obj(name, bm, roles)
    if bevel:
        K.finish(ob, bevel, seg, angle)
    (bucket if bucket is not None else PARTS).append(ob)
    return ob


def box(name, w, d, h, c, roles, bevel=0.002, seg=2, rot=None, bucket=None):
    bm = bmesh.new()
    K.bm_box(bm, w, d, h, (0, 0, 0))
    ob = obj(name, bm, roles, bevel, seg, bucket=bucket)
    if rot:
        ob.rotation_euler = rot
    ob.location = c
    return ob


# ═══ PEDESTAL: front outline with the arch, extruded through the depth ══════
PX, PZ0, PZ1, PD = 0.20, 0.030, 0.655, 0.20
ax_, ay_, ar_ = 0.165, 0.215, 0.055
out = [(-PX, PZ0), (-ax_, PZ0)]
for k in range(9):
    a = math.pi - (math.pi / 2) * k / 8
    out.append((-ax_ + ar_ + ar_ * math.cos(a), ay_ - ar_ + ar_ * math.sin(a)))
for k in range(9):
    a = math.pi / 2 - (math.pi / 2) * k / 8
    out.append((ax_ - ar_ + ar_ * math.cos(a), ay_ - ar_ + ar_ * math.sin(a)))
out += [(ax_, PZ0), (PX, PZ0), (PX, PZ1), (-PX, PZ1)]
bm = bmesh.new()
vs = [bm.verts.new((x, -PD, z)) for (x, z) in out]
f = bm.faces.new(vs)
ex = bmesh.ops.extrude_face_region(bm, geom=[f])
tv = [g for g in ex['geom'] if isinstance(g, bmesh.types.BMVert)]
bmesh.ops.translate(bm, vec=(0, 2 * PD, 0), verts=tv)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
# folded-sheet seams: vertical seam 2.5 cm in from each front corner, and a top rim groove
K.groove_band(bm, 'z', PZ1 - 0.030, PZ1 - 0.027, 0.0015)
ped = obj('teletype_pedestal', bm, ['pedestal'], bevel=0.004)
# MIT Project MAC property tag on the pedestal front
DECALS.append(K.plane_decal('teletype_tag', 0.090, 0.038, (0.10, -PD - 0.0004, PZ1 - 0.07), (0, -1, 0), 'decal_tag'))
for sx in (-1, 1):
    for sz in (-1, 1):
        PARTS.append(K.screw('_ts', r=0.0016, h=0.0009, role='chrome', loc=(0.10 + sx * 0.040, -PD - 0.0003, PZ1 - 0.07 + sz * 0.014), normal=(0, -1, 0), slot=False))
# sled feet: steel bars on edge with chamfered ends, bolted to the pedestal sides
for sx in (-1, 1):
    bm = bmesh.new()
    prof = [(-0.25, 0.0), (0.25, 0.0), (0.235, 0.032), (-0.235, 0.032)]
    vs = [bm.verts.new((0, y, z)) for (y, z) in prof]
    ff = bm.faces.new(vs)
    ex = bmesh.ops.extrude_face_region(bm, geom=[ff])
    tv = [g for g in ex['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.036, 0, 0), verts=tv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    foot = obj(f'teletype_foot_{sx}', bm, ['steel'], bevel=0.0025)
    foot.location = (sx * 0.178 - 0.018, 0, -0.001)
    for yy in (-0.12, 0.12):
        PARTS.append(K.screw('_fs', r=0.0045, h=0.003, role='steel', loc=(sx * 0.198 + (0.0 if sx > 0 else 0.0), yy, 0.045), normal=(sx, 0, 0), slot=False))
# base plate the machine sits on
box('teletype_baseplate', 0.50, 0.45, 0.012, (0.0, 0.0, PZ1 + 0.004), ['alu'], 0.003)
# power cord from the pedestal back to the floor
PARTS.append(K.curve_tube('teletype_cord', [Vector((0.12, PD + 0.001, 0.30)), Vector((0.13, PD + 0.05, 0.22)), Vector((0.16, PD + 0.12, 0.012)),
                                           Vector((0.30, PD + 0.30, 0.008))], 0.0045, 'cable', res=10))

# ═══ LOWER HOUSING: side-profile mass ═════════════════════════════════════════
BX0, BX1, FZ, BZ = -0.205, 0.25, 0.236, -0.236
prof3 = [(FZ, 0.658), (FZ, 0.700), (0.222, 0.720), (0.02, 0.765), (-0.10, 0.855), (-0.13, 0.867)]
cx_, cy_, r_ = -0.13, 0.77, 0.097
for k in range(1, 13):
    a = math.pi / 2 + (k / 12) * (math.pi / 2)
    prof3.append((cx_ + r_ * math.cos(a) * 1.09, cy_ + r_ * math.sin(a)))
prof3 += [(BZ, 0.735), (BZ, 0.658)]
bm = bmesh.new()
K.bm_profile_x(bm, [(-z, y) for (z, y) in prof3], BX0, BX1)
# front band recess
front = max([f for f in bm.faces if f.normal.y < -0.99], key=lambda f: f.calc_area())
bf, bw, _ = K.recess(bm, K.cut_rect(bm, front, 'x', 'z', BX0 + 0.004, BX1 - 0.004, 0.663, 0.697)[0], 0.0, 0.002)
# parting line of the moulding
K.groove_band(bm, 'z', 0.7045, 0.7075, 0.0015)
# back vents (a louvred pocket)
back = max([f for f in bm.faces if f.normal.y > 0.99], key=lambda f: f.calc_area())
vf, vw, _ = K.recess(bm, K.cut_rect(bm, back, 'x', 'z', -0.12, 0.17, 0.668, 0.72)[0], 0.0, 0.012)
for f in vf + vw:
    f.material_index = 1
body = obj('teletype_body', bm, ['khaki', 'blackplastic'], bevel=0)
# keyboard well: a 5 mm pocket in the sloped deck (boolean with a slope-aligned box)
KB = dict(x0=-0.148, x1=0.148, z0=0.036, z1=0.214)          # three z range
deck_ang = math.atan2(0.045, 0.20)
zc = (KB['z0'] + KB['z1']) / 2
yc = 0.720 + (0.22 - zc) * (0.045 / 0.20)
cut = K.cutter_box(KB['x1'] - KB['x0'], (KB['z1'] - KB['z0']) / math.cos(deck_ang), 0.03, P(0, yc, zc), rot=(deck_ang, 0, 0))
cut.location = P(0, yc, zc) + Vector((0, 0, 0.015 - 0.005))
bpy.context.view_layer.update()
K.boolean(body, cut)
K.finish(body, 0.006, 3, 35)
LAYOUT['well'] = {'center': T3(P(0, yc - 0.005 * math.cos(deck_ang), zc)), 'angle': deck_ang,
                  'x0': KB['x0'], 'x1': KB['x1'], 'z0': KB['z0'], 'z1': KB['z1']}
for sx in (-1, 1):
    for zz in (0.10, -0.12):
        PARTS.append(K.screw('_bs', r=0.003, h=0.0015, role='chrome', loc=((BX1 if sx > 0 else BX0) + sx * 0.0005, -zz, 0.685), normal=(sx, 0, 0)))
# brushed front band + mode knob
box('teletype_band', BX1 - BX0 - 0.010, 0.004, 0.032, P((BX0 + BX1) / 2, 0.680, FZ - 0.001), ['alu'], 0.0012)
DECALS.append(K.plane_decal('teletype_bandprint', BX1 - BX0 - 0.012, 0.030, P((BX0 + BX1) / 2, 0.680, FZ + 0.0012), (0, -1, 0), 'decal_band'))
kn = K.lathe('teletype_modeknob', [(0, 0), (0.0125, 0), (0.0125, 0.003), (0.0115, 0.004), (0.0112, 0.014), (0.0095, 0.016), (0, 0.016)],
             'chrome', seg=40, flutes=20, flute_depth=0.05, flute_z=(0.004, 0.015))
kn.rotation_euler = (math.radians(90), 0, 0)
kn.location = P(0.215, 0.679, FZ + 0.002)
PARTS.append(kn)
box('teletype_knobmark', 0.0025, 0.002, 0.012, P(0.215, 0.683, FZ + 0.0185), ['blackplastic'], 0.0006)
# right-hand grey plate along the rising deck + call-control bezels
pts = [(0.214, 0.724), (0.02, 0.767), (-0.10, 0.857), (-0.125, 0.866)]
sheet = [(z, y + 0.004) for (z, y) in pts] + [(z, y - 0.002) for (z, y) in reversed(pts)]
bm = bmesh.new()
K.bm_profile_x(bm, [(-z, y) for (z, y) in sheet], 0.158, 0.244)
obj('teletype_rightplate', bm, ['plategrey'], bevel=0.0015, seg=2)
BTN = []
for i in range(4):
    z = 0.165; x = 0.172 + i * 0.019
    y = 0.720 + (0.22 - z) * (0.045 / 0.20)
    box('_btnbez', 0.018, 0.018, 0.004, P(x, y + 0.006, z), ['blackplastic'], 0.001, rot=(deck_ang, 0, 0))
    BTN.append(T3(P(x, y + 0.0105, z)))
LAYOUT['buttons'] = BTN
LAYOUT['deckAngle'] = deck_ang

# ═══ TYPING-UNIT COVER: a moulded hood (tapered front, big radii) with a window ═══
# ASR-33: the cream hood covers the whole typing unit; the platen knob comes out of
# its left side; the print line is seen through a smoked window; paper exits behind it.
CV = dict(x0=-0.195, x1=0.150, z0=-0.185, z1=0.044, y0=0.758, y1=0.882, r=0.040)
PLATEN = dict(y=0.860, z=-0.100, r=0.021)
PRINT_Z = PLATEN['z'] + PLATEN['r']
bm = bmesh.new()
K.bm_prism(bm, K.rrect_pts(CV['x0'], CV['x1'], -CV['z1'], -CV['z0'], CV['r'], seg=12), CV['y0'], CV['y1'])
bot = [f for f in bm.faces if f.normal.z < -0.99][0]
bmesh.ops.delete(bm, geom=[bot], context='FACES')
top = [f for f in bm.faces if f.normal.z > 0.99][0]
for v in top.verts:                       # taper: the top's front edge sits 28 mm behind the base
    if v.co.y < -0.0:                     # (Blender -Y = front) — scale the front half back
        v.co.y = v.co.y + 0.028 * (min(1.0, -v.co.y / CV['z1']))
bm.normal_update()
# window: cut the opening rectangle into the top, a 4 mm lip step, then open it
WIN = dict(x0=-0.168, x1=0.123, z0=PRINT_Z - 0.010, z1=-0.004)
inside, _ = K.cut_rect(bm, top, 'x', 'y', WIN['x0'], WIN['x1'], -WIN['z1'], -WIN['z0'])
r = bmesh.ops.inset_region(bm, faces=inside, thickness=0.0001, depth=-0.004, use_even_offset=True)
bmesh.ops.delete(bm, geom=inside, context='FACES')
# paper-feed slot through the back wall (the paper comes in from the roll behind the hood)
backf = max([f for f in bm.faces if f.normal.y > 0.99], key=lambda f: f.calc_area())
slot, _ = K.cut_rect(bm, backf, 'x', 'z', -0.118, 0.118, 0.838, 0.866)
bmesh.ops.delete(bm, geom=slot, context='FACES')
cover = K.new_mesh_obj('teletype_cover', bm, ['cream'])
sol = cover.modifiers.new('shell', 'SOLIDIFY')
sol.thickness = 0.004
sol.offset = -1.0
sol.use_even_offset = True
K.finish(cover, 0.010, 4, 30)
PARTS.append(cover)
# smoked window over the platen (front part of the opening); the paper leaves through the slot behind it
gz0, gz1 = PRINT_Z + 0.003, WIN['z1'] + 0.004
gw = box('teletype_window', (WIN['x1'] - WIN['x0']) + 0.006, gz1 - gz0, 0.003,
         P((WIN['x0'] + WIN['x1']) / 2, CV['y1'] - 0.0055, (gz0 + gz1) / 2), ['acrylic'], 0, bucket=DECALS)
gw['no_ao'] = True
DECALS.append(K.plane_decal('teletype_logo', 0.062, 0.030, P(CV['x0'] + 0.085, 0.810, CV['z1'] + 0.0004), (0, -1, 0), 'decal_logo'))
# platen, shaft, knob, paper bail, ribbon spools, type-box rail, mechanism block
pl = K.lathe('_platen', [(0, -0.131), (PLATEN['r'], -0.131), (PLATEN['r'], 0.131), (0, 0.131)], 'rubber', seg=48)
pl.rotation_euler = (0, math.radians(90), 0)
sh = K.lathe('_pshaft', [(0, -0.17), (0.005, -0.17), (0.005, 0.17), (0, 0.17)], 'steel', seg=16)
sh.rotation_euler = (0, math.radians(90), 0)
pk = K.lathe('_platenknob', [(0, 0), (0.017, 0), (0.018, 0.004), (0.018, 0.022), (0.016, 0.026), (0, 0.026)], 'creamknob',
             seg=40, flutes=14, flute_depth=0.07, flute_z=(0.004, 0.022))
pk.rotation_euler = (0, math.radians(-90), 0)
pk.location = (CV['x0'] - 0.004, 0, 0)
for o in (pl, sh, pk):
    K.apply_mods(o); K.apply_xform(o)
platen = K.join([pl, sh, pk], 'teletype_platen')
platen.location = P(0, PLATEN['y'], PLATEN['z'])
MOVING.append(platen)
bail = K.lathe('_bail', [(0, -0.12), (0.0022, -0.12), (0.0022, 0.12), (0, 0.12)], 'chrome', seg=12)
bail.rotation_euler = (0, math.radians(90), 0)
bail.location = P(0, PLATEN['y'] + 0.019, PLATEN['z'] + 0.006)
PARTS.append(bail)
for sx in (-1, 1):
    sp = K.lathe('_spool', [(0, 0), (0.026, 0), (0.026, 0.002), (0.020, 0.003), (0.020, 0.006), (0.026, 0.007), (0.026, 0.009), (0, 0.009)],
                 'blackplastic', seg=40)
    sp.location = P(sx * 0.098 - 0.02, CV['y1'] - 0.036, -0.030)
    PARTS.append(sp)
    rb = K.lathe('_ribbon', [(0.008, 0.0021), (0.019, 0.0021), (0.019, 0.0069), (0.008, 0.0069)], 'ribbon', seg=40)
    rb.location = P(sx * 0.098 - 0.02, CV['y1'] - 0.036, -0.030)
    PARTS.append(rb)
box('_ribbonrun', 0.19, 0.0006, 0.0125, P(0, PLATEN['y'] - 0.0125, PRINT_Z + 0.0085), ['ribbon'], 0)   # rests below the print line
rail = K.lathe('_rail', [(0, -0.115), (0.003, -0.115), (0.003, 0.115), (0, 0.115)], 'steel', seg=12)
rail.rotation_euler = (0, math.radians(90), 0)
rail.location = P(0, PLATEN['y'] - 0.022, PRINT_Z + 0.02)
PARTS.append(rail)
bm = bmesh.new()
fs = K.bm_box(bm, 0.27, 0.05, 0.06, P(0, 0.795, -0.02))
tf = K.face_toward(fs, (0, 0, 1))
K.recess(bm, [tf], 0.015, 0.01)
obj('_mech', bm, ['mech'], bevel=0.003)
for k in range(5):                                           # code bars / levers glimpsed through the window
    box('_lever', 0.004, 0.06, 0.012, P(-0.10 + k * 0.05, 0.842, -0.02), ['steel'], 0.001)
# paper roll cradle + axle (the roll itself is paper, made by the module)
ROLL = dict(y=0.905, z=-0.245, r=0.052)
for sx in (-1, 1):
    bm = bmesh.new()
    K.bm_box(bm, 0.008, 0.05, 0.06, (0, 0, 0))
    cr = obj('_cradle', bm, ['plategrey'], bevel=0.002)
    cr.location = P(sx * 0.118, ROLL['y'] - 0.035, ROLL['z'])
ax2 = K.lathe('_axle', [(0, -0.125), (0.006, -0.125), (0.006, 0.125), (0, 0.125)], 'steel', seg=16)
ax2.rotation_euler = (0, math.radians(90), 0)
ax2.location = P(0, ROLL['y'], ROLL['z'])
PARTS.append(ax2)
LAYOUT['paper'] = {'platenY': PLATEN['y'], 'platenZ': PLATEN['z'], 'platenR': PLATEN['r'], 'printZ': PRINT_Z,
                   'coverTop': CV['y1'], 'roll': ROLL}

# ═══ PAPER-TAPE READER / PUNCH (left) ═══════════════════════════════════════
TX0, TX1 = -0.300, -0.209
tprof = [(0.215, 0.658), (0.215, 0.722), (0.196, 0.738), (0.10, 0.742), (0.09, 0.800), (0.07, 0.812), (-0.21, 0.812), (-0.21, 0.658)]
bm = bmesh.new()
K.bm_profile_x(bm, [(-z, y) for (z, y) in tprof], TX0, TX1)
K.groove_band(bm, 'z', 0.7045, 0.7075, 0.0015)
obj('teletype_tapeunit', bm, ['khaki'], bevel=0.005)
for i in range(4):
    x = TX0 + 0.018 + (i % 2) * 0.052
    z = 0.080 - (i // 2) * 0.034
    st = K.lathe('_kstem', [(0, 0), (0.0055, 0), (0.0045, 0.018), (0, 0.018)], 'chrome', seg=16)
    st.location = P(x, 0.812, z)
    PARTS.append(st)
    cap = K.lathe('_kcap', [(0, 0), (0.0062, 0.0), (0.0066, 0.004), (0.005, 0.009), (0, 0.010)], 'creamknob', seg=20)
    cap.location = P(x, 0.829, z)
    PARTS.append(cap)
lid = box('teletype_readerlid', 0.050, 0.060, 0.010, P((TX0 + TX1) / 2, 0.748, 0.160), ['acrylic'], 0.003, bucket=DECALS)
lid['no_ao'] = True
box('_lever2', 0.006, 0.008, 0.022, P(TX0 + 0.012, 0.712, 0.219), ['chrome'], 0.0015)
box('_tapeflat', 0.0254, 0.12, 0.0006, P((TX0 + TX1) / 2 + 0.006, 0.7436, 0.160), ['tapepink'], 0)
cb = box('teletype_chadbox', 0.07, 0.12, 0.10, P((TX0 + TX1) / 2, 0.596, -0.02), ['chad'], 0.006, bucket=DECALS)
cb['no_ao'] = True
# the hanging tape: a thin curved strip
bm = bmesh.new()
hang = [P(0, 0.7435, 0.219), P(0, 0.735, 0.232), P(0, 0.700, 0.238), P(0, 0.620, 0.240)]
curve_pts = []
for i in range(len(hang) - 1):
    for k in range(6):
        curve_pts.append(hang[i].lerp(hang[i + 1], k / 6))
curve_pts.append(hang[-1])
rows = []
for p in curve_pts:
    rows.append((bm.verts.new((-0.0127, p.y, p.z)), bm.verts.new((0.0127, p.y, p.z))))
for i in range(len(rows) - 1):
    bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]))
tape = K.new_mesh_obj('teletype_papertape', bm, ['tapepink'])
tape.location = ((TX0 + TX1) / 2 + 0.006, 0, 0)
sol = tape.modifiers.new('t', 'SOLIDIFY'); sol.thickness = 0.0004
PARTS.append(tape)
LAYOUT['tapeUnit'] = {'x0': TX0, 'x1': TX1}

# ═══ FINISH ══════════════════════════════════════════════════════════════════
for o in PARTS + DECALS:
    if o.name in bpy.data.objects:
        K.apply_mods(o)
for o in PARTS:
    K.apply_xform(o)
static = K.join([o for o in PARTS if o.name in bpy.data.objects], 'teletype_machine')
K.clean_slots(static)
K.uv_tile(static)
for o in MOVING:
    K.clean_slots(o)
    K.uv_tile(o)
for o in DECALS:
    if o.get('no_ao'):
        K.uv_tile(o)
K.uv_atlas([static] + MOVING, margin=0.002)
K.stats()
K.bake_masks([static] + MOVING, 'teletype', res=2048, samples=48)
K.export_glb('teletype', [static] + MOVING + DECALS, extras=LAYOUT)
print('[teletype] done')
