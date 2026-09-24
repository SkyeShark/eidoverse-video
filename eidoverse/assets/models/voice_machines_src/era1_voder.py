"""era1_voder.py — the Bell Labs Voder (1939) as a hero asset.
blender --background --factory-startup --python era1_voder.py
-> work/daisy/props/assets/era1/voder.glb, voder_mask.png, voder_layout.json

Operator's console (Art Deco pedestals, lacquered desk, key bed with ten ivory
spectrum keys through real slots, right-thumb stop keys + quiet key, left-wrist
bar, sloped control box with meter, pilot jewel, knobs, whisper toggle, switch
bank) + pitch pedal + stepped loudspeaker tower + braided cable.
Blender frame: operator/camera side = -Y, up = +Z.
"""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(__file__))
import importlib
import era1_kit as K
importlib.reload(K)
import bpy, bmesh
from mathutils import Vector, Matrix, Euler, Quaternion


def P(x, y, z):
    """three.js (x, y-up, z-toward-camera) -> Blender (x, -z, y)."""
    return Vector((x, -z, y))


K.reset()
CONSOLE, SPEAKER, MOVING, DECALS = [], [], [], []
LAYOUT = {}
DESK = 0.745


def obj_from_bm(name, bm, roles, bucket, bevel=0.003, seg=3, angle=35, harden=True):
    ob = K.new_mesh_obj(name, bm, roles)
    if bevel:
        K.finish(ob, bevel, seg, angle, harden)
    bucket.append(ob)
    return ob


# ═══ PEDESTALS ═══════════════════════════════════════════════════════════
for side in (-1, 1):
    x0, x1 = (-0.60, -0.30) if side < 0 else (0.30, 0.60)
    rO, rI = 0.14, 0.022
    radii = [rO, rI, rI, rO] if side < 0 else [rI, rO, rO, rI]
    bm = bmesh.new()
    K.bm_prism(bm, K.rrect_pts(x0, x1, -0.28, 0.30, radii, seg=14), 0.07, 0.70)
    for zc in (0.506, 0.540, 0.574):                     # speed-line grooves (chrome inlays go in)
        K.groove_band(bm, 'z', zc - 0.0048, zc + 0.0048, 0.004)
    # inspection door on the knee-side face: seam groove cut into the mass
    xin = x1 if side < 0 else x0
    side_faces = [f for f in bm.faces if abs(f.normal.x) > 0.95 and abs(f.calc_center_median().x - xin) < 1e-3]
    inside, region = K.cut_rect(bm, side_faces[0] if len(side_faces) == 1 else max(side_faces, key=lambda f: f.calc_area()),
                                'y', 'z', -0.19, 0.17, 0.12, 0.44)
    r = bmesh.ops.inset_region(bm, faces=inside, thickness=0.003, depth=0.0, use_even_offset=True)
    bmesh.ops.inset_region(bm, faces=r['faces'], thickness=0.0003, depth=-0.0035, use_even_offset=True)
    # louvre pocket on the back (speaker side)
    back = max([f for f in bm.faces if f.normal.y > 0.95], key=lambda f: f.calc_area())
    lin, _ = K.cut_rect(bm, back, 'x', 'z', min(x0, x1) + 0.06, max(x0, x1) - 0.06, 0.16, 0.36)
    K.recess(bm, lin, 0.0, 0.018)
    ped = obj_from_bm(f'voder_pedestal_{"L" if side < 0 else "R"}', bm, ['cream'], CONSOLE, bevel=0.0035)
    # chrome inlays in the grooves: rings following the plan, 1 mm proud of the groove floor
    for zc in (0.506, 0.540, 0.574):
        bm = bmesh.new()
        e = -0.0015
        K.bm_prism(bm, K.rrect_pts(x0 - e, x1 + e, -0.28 - e, 0.30 + e, [max(0.005, q + e) for q in radii], seg=14),
                   zc - 0.0036, zc + 0.0036)
        obj_from_bm(f'voder_inlay_{side}_{zc}', bm, ['chrome'], CONSOLE, bevel=0.0012, seg=2)
    # louvre fins inside the back pocket
    for k in range(7):
        z = 0.175 + k * 0.026
        bm = bmesh.new()
        K.bm_box(bm, abs(x1 - x0) - 0.13, 0.004, 0.022, (0, 0, 0))
        fin = obj_from_bm(f'voder_fin_{side}_{k}', bm, ['cream'], CONSOLE, bevel=0.0012, seg=2)
        fin.rotation_euler = (math.radians(-35), 0, 0)
        fin.location = ((x0 + x1) / 2, 0.30 - 0.009, z)
    # door escutcheon with keyhole
    esc = K.lathe(f'voder_esc_{side}', [(0, 0), (0.012, 0), (0.012, 0.002), (0.010, 0.0035), (0, 0.004)], 'chrome', seg=32)
    esc.location = (xin + side * 0.0005 * -1, -0.12, 0.30)
    esc.rotation_euler = (0, math.radians(90) * (1 if side < 0 else -1), 0)
    K.apply_xform(esc)
    K.boolean(esc, K.cutter_box(0.02, 0.0028, 0.009, (xin, -0.12, 0.2985)))
    CONSOLE.append(esc)
    # dark plinth (kick), sunk 1 mm into the floor
    bm = bmesh.new()
    rr = [max(0.01, q - 0.018) for q in radii]
    K.bm_prism(bm, K.rrect_pts(x0 + 0.018, x1 - 0.018, -0.262, 0.282, rr, seg=12), -0.001, 0.075)
    obj_from_bm(f'voder_plinth_{side}', bm, ['lacquer'], CONSOLE, bevel=0.003)

# ═══ KNEE WELL: modesty panel (recessed field), apron with inlay ══════════════
bm = bmesh.new()
fs = K.bm_box(bm, 0.62, 0.03, 0.63, (0, 0.27, 0.385))
front = K.face_toward(fs, (0, -1, 0))
field, walls, frame = K.recess(bm, [front], 0.045, 0.008)
for f in field + walls:
    f.material_index = 1
obj_from_bm('voder_modesty', bm, ['lacquer', 'satin'], CONSOLE)
bm = bmesh.new()
K.bm_box(bm, 0.62, 0.07, 0.075, (0, -0.235, 0.655))
K.groove_band(bm, 'z', 0.6515, 0.6585, 0.003)
obj_from_bm('voder_apron', bm, ['cream'], CONSOLE)
bm = bmesh.new()
K.bm_box(bm, 0.598, 0.0065, 0.006, (0, -0.2705, 0.655))
obj_from_bm('voder_apron_inlay', bm, ['chrome'], CONSOLE, bevel=0.0015, seg=2)

# ═══ DESK TOP: lacquered slab, chrome lip inlay, bullnose front ══════════════
bm = bmesh.new()
K.bm_prism(bm, K.rrect_pts(-0.64, 0.64, -0.34, 0.34, 0.15, seg=16), 0.700, DESK)
K.groove_band(bm, 'z', 0.7075, 0.7185, 0.0035)
obj_from_bm('voder_desk', bm, ['lacquer'], CONSOLE, bevel=0.007, seg=4, angle=40)
bm = bmesh.new()
e = -0.0012
K.bm_prism(bm, K.rrect_pts(-0.64 - e, 0.64 + e, -0.34 - e, 0.34 + e, 0.15 + e, seg=16), 0.7085, 0.7175)
obj_from_bm('voder_desk_inlay', bm, ['chrome'], CONSOLE, bevel=0.0015, seg=2)

# ═══ KEY BED: slotted housing ═══════════════════════════════════════════════
BED_FRONT = 0.135
KEY_X = [-0.214, -0.187, -0.160, -0.133, -0.106, 0.106, 0.133, 0.160, 0.187, 0.214]
STOP_X, QUIET_X = [0.030, 0.052, 0.074], 0.004
TIP_Z = [0.205, 0.221, 0.232, 0.224, 0.211, 0.211, 0.224, 0.232, 0.221, 0.205]
KEY_PIV = (0.768, 0.070)                    # three (y, z)
bm = bmesh.new()
prof = [(-BED_FRONT, DESK - 0.002), (-BED_FRONT, 0.800), (-0.095, 0.818), (0.005, 0.824), (0.005, DESK - 0.002)]
K.bm_profile_x(bm, prof, -0.345, 0.345)
# legend strip recess on the front face
front = max([f for f in bm.faces if f.normal.y < -0.95], key=lambda f: f.calc_area())
sin_, _ = K.cut_rect(bm, front, 'x', 'z', -0.332, 0.332, 0.7785, 0.7945)
K.recess(bm, sin_, 0.0, 0.0012)
bed = obj_from_bm('voder_keybed', bm, ['satin'], CONSOLE, bevel=0)
# key slots: one boolean with all cutters
cut_objs = []
for x in KEY_X:
    cut_objs.append(K.cutter_box(0.0235, 0.10, 0.0175, P(x, 0.7675, 0.100)))
for x in STOP_X + [QUIET_X]:
    cut_objs.append(K.cutter_box(0.0195, 0.10, 0.0150, P(x, 0.7600, 0.100)))
cutter = K.join(cut_objs, '_slots')
K.boolean(bed, cutter)
K.finish(bed, 0.003, 3, 35)
K.apply_mods(bed)
for x in (-0.3475, 0.3475):                 # chrome end caps, same profile
    bm = bmesh.new()
    K.bm_profile_x(bm, [(y - 0.0015 if y < -0.1 else y, z + (0.0015 if z > 0.8 else 0)) for (y, z) in prof], x - 0.003, x + 0.003)
    obj_from_bm(f'voder_bedcap_{x}', bm, ['chrome'], CONSOLE, bevel=0.0015, seg=2)
DECALS.append(K.plane_decal('voder_keystrip', 0.66, 0.0155, P(0, 0.7865, BED_FRONT - 0.0012 + 0.0), (0, -1, 0), 'decal_keystrip'))
LAYOUT['keystrip'] = {'w': 0.66, 'h': 0.0155, 'keyX': KEY_X, 'stopX': STOP_X, 'quietX': QUIET_X}


# ═══ KEYS (moving; origin = pivot) ══════════════════════════════════════════
def key_obj(name, x, piv_y, piv_z, tip_z, w, h, body_role, cap_role=None, cap_len=0.028):
    L = tip_z - piv_z
    bm = bmesh.new()
    K.bm_prism(bm, K.rrect_pts(-w / 2, w / 2, -L, 0.0, [w * 0.28, w * 0.28, 0.001, 0.001], seg=6), -h / 2, h / 2)
    # a dished top: pull the top-centre verts down a hair (finger rest)
    for v in bm.verts:
        if v.co.z > h / 2 - 1e-6 and abs(v.co.x) < w * 0.35 and v.co.y < -L * 0.3:
            v.co.z -= 0.0006
    roles = [body_role]
    if cap_role:
        for f in bm.faces:
            if f.calc_center_median().y < -L + cap_len:
                f.material_index = 1
        roles.append(cap_role)
    ob = K.new_mesh_obj(name, bm, roles)
    K.finish(ob, 0.0018, 3, 35)
    ob.location = P(x, piv_y, piv_z)
    MOVING.append(ob)
    return ob


for i, x in enumerate(KEY_X):
    key_obj(f'voder_key_{i + 1:02d}', x, KEY_PIV[0], KEY_PIV[1], TIP_Z[i], 0.021, 0.013, 'ivory')
for i, x in enumerate(STOP_X):
    key_obj(f'voder_stop_{["td", "pb", "kg"][i]}', x, 0.760, KEY_PIV[1], KEY_PIV[1] + 0.172, 0.017, 0.011, 'bakelite', 'ivory')
key_obj('voder_quiet', QUIET_X, 0.760, KEY_PIV[1], KEY_PIV[1] + 0.160, 0.017, 0.011, 'bakelite', 'chrome')

# ═══ WRIST BAR (moving; origin = hinge) ═════════════════════════════════════
WB = P(-0.160, 0.770, BED_FRONT - 0.004)
parts = []
grip = K.lathe('_grip', [(0, -0.093), (0.0105, -0.093), (0.0115, -0.090), (0.0115, 0.090), (0.0105, 0.093), (0, 0.093)], 'bakelite', seg=32)
grip.rotation_euler = (0, math.radians(90), 0)
grip.location = (0, -0.128, 0.004)
parts.append(grip)
for sx in (-1, 1):
    fer = K.lathe('_fer', [(0, 0), (0.0125, 0), (0.0128, 0.002), (0.0128, 0.010), (0.0115, 0.012), (0, 0.012)], 'chrome', seg=32)
    fer.rotation_euler = (0, math.radians(90) * sx, 0)
    fer.location = (sx * 0.093, -0.128, 0.004)
    parts.append(fer)
    bm = bmesh.new()
    K.bm_box(bm, 0.007, 0.132, 0.005, (sx * 0.099, -0.066, 0.002))
    arm = K.new_mesh_obj('_arm', bm, ['chrome'])
    K.finish(arm, 0.0012, 2)
    parts.append(arm)
    hub = K.lathe('_hub', [(0, -0.006), (0.0065, -0.006), (0.0065, 0.006), (0, 0.006)], 'chrome', seg=20)
    hub.rotation_euler = (0, math.radians(90), 0)
    hub.location = (sx * 0.099, 0, 0.0)
    parts.append(hub)
for p_ in parts:
    K.apply_mods(p_)
    K.apply_xform(p_)
wrist = K.join(parts, 'voder_wristbar')
wrist.location = WB
MOVING.append(wrist)
for sx in (-1, 1):                           # static hinge brackets on the key-bed face
    bm = bmesh.new()
    K.bm_box(bm, 0.010, 0.012, 0.022, (WB.x + sx * 0.099, WB.y - 0.004, WB.z + 0.004))
    obj_from_bm(f'voder_wbhinge_{sx}', bm, ['chrome'], CONSOLE, bevel=0.0015, seg=2)

# ═══ CONTROL BOX: sloped desk, chrome frame, recessed black face plate ═══════
SL = dict(z0=-0.055, y0=0.802, z1=-0.300, y1=1.022)
cprof = [(-SL['z0'], DESK - 0.002), (-SL['z0'], SL['y0']), (-SL['z1'], SL['y1']),
         (-(SL['z1'] - 0.025), SL['y1']), (-(SL['z1'] - 0.025), DESK - 0.002)]
bm = bmesh.new()
K.bm_profile_x(bm, cprof, -0.425, 0.425)
slope = max([f for f in bm.faces if f.normal.z > 0.3 and f.normal.y < -0.3], key=lambda f: f.calc_area())
r = bmesh.ops.inset_region(bm, faces=[slope], thickness=0.022, depth=0.0, use_even_offset=True)
for f in r['faces']:
    f.material_index = 1                    # chrome frame band
r2 = bmesh.ops.inset_region(bm, faces=[slope], thickness=0.006, depth=0.0, use_even_offset=True)
for f in r2['faces']:
    f.material_index = 1
field, walls, _ = K.recess(bm, [slope], 0.0, 0.006)
for f in field:
    f.material_index = 2
for f in walls:
    f.material_index = 1
cbox = obj_from_bm('voder_controlbox', bm, ['cream', 'chrome', 'lacquer'], CONSOLE, bevel=0)
# slope frame: U up the face, N out of it (three coords); convert when placing
U3 = Vector((0, SL['y1'] - SL['y0'], SL['z1'] - SL['z0'])).normalized()
N3 = Vector((0, -U3.z, U3.y))
C3 = Vector((0, (SL['y0'] + SL['y1']) / 2, (SL['z0'] + SL['z1']) / 2))
FIELD_H = -0.006                            # the recessed field sits 6 mm below the slope plane


def S3(x, s, h):
    v = C3 + Vector((x, 0, 0)) + U3 * s + N3 * (h + FIELD_H)
    return P(v.x, v.y, v.z)


NB = P(0, N3.y, N3.z) - P(0, 0, 0)          # outward normal, Blender
UB = P(0, U3.y, U3.z) - P(0, 0, 0)
Q_FACE = NB.to_track_quat('Z', 'Y')
q_up = (Q_FACE @ Vector((0, 1, 0)))
Q_FACE = q_up.rotation_difference(UB) @ Q_FACE      # local +Y up the slope, +Z out


def on_face(ob, x, s, h):
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Q_FACE.copy()
    ob.location = S3(x, s, h)
    return ob


PANEL_W, PANEL_H = 0.772, 0.270
# meter: bore through the plate, case, bezel, card (decal), glass, needle
DIAL = dict(x=0.225, s=0.005, R=0.058)
bore = K.cutter_cyl(DIAL['R'] + 0.004, 0.05, (0, 0, 0))
on_face(bore, DIAL['x'], DIAL['s'], 0.0)
K.boolean(cbox, bore)
K.finish(cbox, 0.004, 3, 35)
K.apply_mods(cbox)
case = K.lathe('voder_meter_case', [(0, -0.030), (DIAL['R'] + 0.003, -0.030), (DIAL['R'] + 0.003, 0.0), (0, 0.0)], 'dark', seg=48)
on_face(case, DIAL['x'], DIAL['s'], -0.004)
CONSOLE.append(case)
bez = K.lathe('voder_meter_bezel', [(DIAL['R'] - 0.002, 0.0), (DIAL['R'] + 0.013, 0.0), (DIAL['R'] + 0.013, 0.003),
                                     (DIAL['R'] + 0.009, 0.008), (DIAL['R'] + 0.002, 0.009), (DIAL['R'] - 0.002, 0.004)],
               'chrome', seg=64)
on_face(bez, DIAL['x'], DIAL['s'], 0.0)
CONSOLE.append(bez)
dface = K.plane_decal('voder_dial_face', 2 * DIAL['R'] + 0.012, 2 * DIAL['R'] + 0.012, (0, 0, 0), (0, 0, 1), 'decal_dial')   # overfills the bore
on_face(dface, DIAL['x'], DIAL['s'], -0.0035)
DECALS.append(dface)
glass_ = K.lathe('voder_meter_glass', [(0, 0.0), (DIAL['R'] + 0.001, 0.0), (DIAL['R'] + 0.001, 0.0015), (0, 0.0022)], 'glass', seg=48)
on_face(glass_, DIAL['x'], DIAL['s'], 0.0045)
glass_['no_ao'] = True
DECALS.append(glass_)
bm = bmesh.new()
K.bm_box(bm, 0.0016, 0.0008, DIAL['R'] * 1.10, (0, 0.0, DIAL['R'] * 0.55))
nb = K.new_mesh_obj('_needle', bm, ['bakelite'])
nb.rotation_euler = (math.radians(-90), 0, 0)
hubn = K.lathe('_needlehub', [(0, 0), (0.0045, 0), (0.0045, 0.003), (0, 0.003)], 'bakelite', seg=20)
for o in (nb, hubn):
    K.apply_xform(o)
needle = K.join([nb, hubn], 'voder_needle')
needle['pivot'] = True
on_face(needle, DIAL['x'], DIAL['s'] - DIAL['R'] * 0.40, -0.0022)
MOVING.append(needle)
# pilot jewel lamp: knurled bezel + faceted jewel (emissive)
PIL = dict(x=0.112, s=0.0)
pb = K.lathe('voder_pilot_bezel', [(0, 0), (0.021, 0), (0.021, 0.004), (0.017, 0.012), (0.012, 0.013), (0, 0.013)], 'chrome',
             seg=40, flutes=24, flute_depth=0.06, flute_z=(0.0, 0.0045))
on_face(pb, PIL['x'], PIL['s'], 0.0)
CONSOLE.append(pb)
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.0115)
bmesh.ops.scale(bm, vec=(1, 1, 0.78), verts=bm.verts)
jewel = K.new_mesh_obj('voder_pilot', bm, ['lamp_pilot'], smooth=False)
on_face(jewel, PIL['x'], PIL['s'], 0.015)
MOVING.append(jewel)
# knobs: fluted bakelite over a chrome skirt dial plate
for nm, x in (('pitch', -0.330), ('gain', 0.335)):
    plate = K.lathe(f'voder_knobplate_{nm}', [(0, 0), (0.034, 0), (0.034, 0.0012), (0.032, 0.0022), (0, 0.0022)], 'chrome', seg=48)
    on_face(plate, x, 0.0, 0.0)
    CONSOLE.append(plate)
    kn = K.lathe(f'voder_knob_{nm}', [(0, 0), (0.024, 0), (0.024, 0.004), (0.0205, 0.006), (0.0195, 0.024), (0.0165, 0.029),
                                      (0.009, 0.031), (0, 0.031)], 'bakelite', seg=48, flutes=16, flute_depth=0.07,
                 flute_z=(0.006, 0.024))
    on_face(kn, x, 0.0, 0.0022)
    CONSOLE.append(kn)
    cap = K.lathe(f'voder_knobcap_{nm}', [(0, 0), (0.0085, 0), (0.0085, 0.0012), (0, 0.0016)], 'chrome', seg=32)
    on_face(cap, x, 0.0, 0.0332)
    CONSOLE.append(cap)
# whisper toggle + a five-switch bank: hex nut, bat handle, escutcheon
def toggle(nm, x, s, tilt, scale=1.0):
    esc_ = K.lathe(f'voder_tesc_{nm}', [(0, 0), (0.014 * scale, 0), (0.014 * scale, 0.0012), (0, 0.0014)], 'chrome', seg=32)
    on_face(esc_, x, s, 0.0)
    nut = K.lathe(f'voder_tnut_{nm}', [(0, 0), (0.0072 * scale, 0), (0.0072 * scale, 0.0045 * scale), (0, 0.0045 * scale)], 'chrome', seg=6)
    on_face(nut, x, s, 0.0014)
    bat = K.lathe(f'voder_tbat_{nm}', [(0, 0), (0.0032 * scale, 0), (0.0021 * scale, 0.026 * scale), (0.0033 * scale, 0.029 * scale),
                                       (0.0028 * scale, 0.0318 * scale), (0, 0.0322 * scale)], 'chrome', seg=16)
    on_face(bat, x, s, 0.0055)
    bat.rotation_quaternion = bat.rotation_quaternion @ Quaternion((1, 0, 0), math.radians(tilt))
    CONSOLE.extend([esc_, nut, bat])


toggle('whisper', 0.030, 0.0, -24)
bank = dict(x0=-0.330, s=0.090)
bm = bmesh.new()
K.bm_box(bm, 0.155, 0.040, 0.0018, (0, 0, 0.0009))
bankplate = K.new_mesh_obj('voder_bankplate', bm, ['chrome'])
K.finish(bankplate, 0.0007, 2)
on_face(bankplate, bank['x0'] + 0.062, bank['s'], 0.0)
CONSOLE.append(bankplate)
for k in range(5):
    toggle(f'bank{k}', bank['x0'] + k * 0.031, bank['s'], -24 if k % 2 else 22, 0.62)
# nameplate (brass) + screws; face-plate corner screws
bm = bmesh.new()
K.bm_box(bm, 0.20, 0.0625, 0.004, (0, 0, 0.002))
nplate = K.new_mesh_obj('voder_nameplate', bm, ['lacquer'])
K.finish(nplate, 0.0012, 2)
on_face(nplate, -0.13, 0.03, 0.0)
CONSOLE.append(nplate)
nd = K.plane_decal('voder_name', 0.19, 0.056, (0, 0, 0), (0, 0, 1), 'decal_name')
on_face(nd, -0.13, 0.03, 0.0044)
DECALS.append(nd)
for (sx, ss) in ((-0.092, 0.025), (0.092, 0.025), (-0.092, -0.025), (0.092, -0.025)):
    sc_ = K.screw('voder_nscrew', r=0.0028, h=0.0018, role='chrome')
    on_face(sc_, -0.13 + sx, 0.03 + ss, 0.004)
    CONSOLE.append(sc_)
for (sx, ss) in ((-1, 1), (1, 1), (-1, -1), (1, -1)):
    sc_ = K.screw('voder_pscrew', r=0.0034, h=0.002, role='chrome')
    on_face(sc_, sx * (PANEL_W / 2 - 0.012), ss * (PANEL_H / 2 - 0.012), 0.0)
    CONSOLE.append(sc_)
pdec = K.plane_decal('voder_panel_labels', PANEL_W, PANEL_H, (0, 0, 0), (0, 0, 1), 'decal_panel')
on_face(pdec, 0, 0, 0.0004)
DECALS.append(pdec)
LAYOUT['panel'] = {'w': PANEL_W, 'h': PANEL_H, 'dial': DIAL, 'pilot': PIL, 'knobs': {'pitch': -0.330, 'gain': 0.335},
                   'whisper': [0.030, 0.0], 'bank': bank, 'name': [-0.13, 0.03]}

# ═══ PITCH PEDAL: cast base with hinge lugs + spring; ribbed treadle (moving) ═
bm = bmesh.new()
fs = K.bm_box(bm, 0.13, 0.33, 0.016, P(0.13, 0.008, 0.035))
top = K.face_toward(fs, (0, 0, 1))
K.recess(bm, [top], 0.012, 0.004)
obj_from_bm('voder_pedal_base', bm, ['crinkle'], CONSOLE, bevel=0.0025)
for sx in (-1, 1):
    bm = bmesh.new()
    K.bm_box(bm, 0.012, 0.030, 0.034, P(0.13 + sx * 0.052, 0.024, 0.172))
    lug = obj_from_bm(f'voder_pedal_lug_{sx}', bm, ['crinkle'], CONSOLE, bevel=0.002)
pin = K.lathe('voder_pedal_pin', [(0, -0.062), (0.0045, -0.062), (0.0045, 0.062), (0, 0.062)], 'chrome', seg=20)
pin.rotation_euler = (0, math.radians(90), 0)
pin.location = P(0.13, 0.030, 0.172)
CONSOLE.append(pin)
spring = K.curve_tube('voder_pedal_spring', [P(0.13 + 0.008 * math.cos(a), 0.010 + a * 0.0011, 0.055 + 0.008 * math.sin(a))
                                              for a in [k * math.pi / 3 for k in range(0, 25)]], 0.0012, 'chrome', res=4, bevel_res=2)
CONSOLE.append(spring)
PED_PIV = P(0.13, 0.030, 0.172)
parts = []
bm = bmesh.new()
K.bm_prism(bm, K.rrect_pts(-0.049, 0.049, 0.0, 0.285, [0.004, 0.004, 0.025, 0.025], seg=8), -0.006, 0.006)
plate = K.new_mesh_obj('_pplate', bm, ['chrome'])
K.finish(plate, 0.0018, 2)
parts.append(plate)
for k in range(11):
    bm = bmesh.new()
    K.bm_box(bm, 0.082, 0.012, 0.006, (0, 0.030 + k * 0.022, 0.009))
    rib = K.new_mesh_obj('_rib', bm, ['rubber'])
    K.finish(rib, 0.0022, 3)
    parts.append(rib)
for p_ in parts:
    K.apply_mods(p_)
treadle = K.join(parts, 'voder_pedal')
treadle.location = PED_PIV + Vector((0, 0.002, 0.0))
MOVING.append(treadle)

# ═══ SPEAKER TOWER: stepped mass built by extrude/inset from the plinth up ════
SY0, SY1, TW = 0.62, 0.98, 0.31
bm = bmesh.new()
K.bm_prism(bm, K.rrect_pts(-TW, TW, SY0, SY1, 0.06, seg=12), 0.06, 1.46)
topf = [f for f in bm.faces if f.normal.z > 0.99][0]
for (ins, sx_target, h) in ((0.03, 0.235, 0.125), (0.03, 0.16, 0.10)):
    bmesh.ops.inset_region(bm, faces=[topf], thickness=ins, depth=0.0, use_even_offset=True)
    vs = topf.verts
    cx = sum(v.co.x for v in vs) / len(vs)
    half = max(abs(v.co.x - cx) for v in vs)
    dx = half - sx_target                      # slide the straight sides in; the corner arcs keep their shape
    for v in vs:
        v.co.x -= dx if v.co.x > cx else -dx
    ex = bmesh.ops.extrude_face_region(bm, geom=[topf])
    vs2 = [g for g in ex['geom'] if isinstance(g, bmesh.types.BMVert)]
    nf = [g for g in ex['geom'] if isinstance(g, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, vec=(0, 0, h), verts=vs2)
    bmesh.ops.delete(bm, geom=[topf], context='FACES')
    topf = [f for f in nf if f.normal.z > 0.99][0]
# grille bore + back louvre pocket
back = max([f for f in bm.faces if f.normal.y > 0.95], key=lambda f: f.calc_area())
lin, _ = K.cut_rect(bm, back, 'x', 'z', -0.20, 0.20, 0.30, 0.62)
K.recess(bm, lin, 0.0, 0.02)
tower = obj_from_bm('voder_tower', bm, ['cream'], SPEAKER, bevel=0)
bm = bmesh.new()
K.bm_prism(bm, K.rrect_pts(-0.150, 0.150, SY0 + 0.07, SY1 - 0.07, 0.028, seg=10), 1.683, 1.693)
obj_from_bm('voder_tower_cap', bm, ['chrome'], SPEAKER, bevel=0.002, seg=2)
# Bell System roundel above the grille (era homage decal) on a chrome ring
DECALS.append(K.plane_decal('voder_bell', 0.130, 0.130, (0, SY0, 1.345), (0, -1, 0), 'decal_bell'))
bring = K.lathe('voder_bellring', [(0.066, 0.0), (0.072, 0.0), (0.072, 0.0025), (0.069, 0.0045), (0.066, 0.003)], 'chrome', seg=96)
bring.rotation_euler = (math.radians(90), 0, 0)
bring.location = (0, SY0, 1.345)
SPEAKER.append(bring)
GY, GR = 1.06, 0.175
bore = K.cutter_cyl(GR + 0.008, 0.05, (0, SY0, GY), rot=(math.radians(90), 0, 0), seg=96)
K.boolean(tower, bore)
K.finish(tower, 0.005, 3, 35)
K.apply_mods(tower)
bm = bmesh.new()
K.bm_prism(bm, K.rrect_pts(-TW + 0.016, TW - 0.016, SY0 + 0.016, SY1 - 0.016, 0.045, seg=10), -0.001, 0.065)
obj_from_bm('voder_tower_plinth', bm, ['lacquer'], SPEAKER, bevel=0.003)
for (z, inset_, r_) in ((1.4585, 0.0, 0.06), (1.5835, 0.075, 0.05)):
    bm = bmesh.new()
    e = -0.004
    x_half = TW - inset_ if inset_ else TW
    K.bm_prism(bm, K.rrect_pts(-x_half - (0.004 if not inset_ else -0.0), x_half + (0.004 if not inset_ else 0.0),
                               SY0 - 0.004 + (0.03 if inset_ else 0), SY1 + 0.004 - (0.03 if inset_ else 0), r_, seg=12), z - 0.004, z + 0.004)
    obj_from_bm(f'voder_band_{z}', bm, ['chrome'], SPEAKER, bevel=0.0015, seg=2)
# grille: cloth disc deep in the bore, chrome bars, bezel ring, sunburst, fins with screws
cloth = K.lathe('voder_grille_cloth', [(0, 0), (GR + 0.008, 0), (GR + 0.008, 0.001), (0, 0.001)], 'cloth', seg=96)
cloth.rotation_euler = (math.radians(90), 0, 0)
cloth.location = (0, SY0 + 0.022, GY)
SPEAKER.append(cloth)
for i in range(-3, 4):
    y = i * 0.045
    L = 2 * math.sqrt(max(0.0, (GR + 0.004) ** 2 - y * y))
    bar = K.lathe(f'voder_gbar_{i}', [(0, -L / 2), (0.0055, -L / 2), (0.0055, L / 2), (0, L / 2)], 'chrome', seg=20)
    bar.rotation_euler = (0, math.radians(90), 0)
    bar.location = (0, SY0 + 0.012, GY + y)
    SPEAKER.append(bar)
ring = K.lathe('voder_gbezel', [(GR + 0.004, -0.004), (GR + 0.022, -0.004), (GR + 0.022, 0.0), (GR + 0.016, 0.006),
                                  (GR + 0.008, 0.007), (GR + 0.004, 0.002)], 'chrome', seg=128)
ring.rotation_euler = (math.radians(90), 0, 0)
ring.location = (0, SY0, GY)
SPEAKER.append(ring)
for i in range(7):
    a = (i - 3) * 0.26
    bm = bmesh.new()
    K.bm_box(bm, 0.0065, 0.004, 0.078, (0, 0, 0.039))
    ray = K.new_mesh_obj(f'voder_ray_{i}', bm, ['chrome'])
    K.finish(ray, 0.0012, 2)
    ray.rotation_euler = (0, a, 0)
    ray.location = (math.sin(a) * 0.022, SY0 - 0.002, 0.78 + math.cos(a) * 0.022)
    SPEAKER.append(ray)
hubs = K.lathe('voder_ray_hub', [(0, 0), (0.019, 0), (0.019, 0.004), (0.015, 0.007), (0, 0.007)], 'chrome', seg=40)
hubs.rotation_euler = (math.radians(90), 0, 0)
hubs.location = (0, SY0 - 0.0005, 0.78)
SPEAKER.append(hubs)
for sx in (-1, 1):
    for i in range(3):
        x = sx * (0.218 + i * 0.0155)
        h = 1.02 - i * 0.12
        bm = bmesh.new()
        K.bm_box(bm, 0.0085, 0.010, h, (x, SY0 - 0.004, 0.36 + h / 2))
        obj_from_bm(f'voder_finv_{sx}_{i}', bm, ['chrome'], SPEAKER, bevel=0.0028, seg=3)
        for zz in (0.36 + 0.02, 0.36 + h - 0.02):
            s_ = K.screw('voder_fscrew', r=0.0026, h=0.0015, role='chrome', loc=(x, SY0 - 0.009, zz), normal=(0, -1, 0))
            SPEAKER.append(s_)
# back louvres + back-panel screws
for k in range(10):
    bm = bmesh.new()
    K.bm_box(bm, 0.39, 0.004, 0.026, (0, 0, 0))
    f_ = obj_from_bm(f'voder_tfin_{k}', bm, ['cream'], SPEAKER, bevel=0.0012, seg=2)
    f_.rotation_euler = (math.radians(35), 0, 0)
    f_.location = (0, SY1 - 0.010, 0.315 + k * 0.03)
# cable gland on the tower side, and the braided cable to the right pedestal
gl = K.lathe('voder_gland', [(0, 0), (0.016, 0), (0.016, 0.006), (0.012, 0.008), (0.012, 0.020), (0, 0.020)], 'chrome', seg=6)
gl.rotation_euler = (0, math.radians(90), 0)
gl.location = (TW - 0.001, 0.80, 0.12)
SPEAKER.append(gl)
cab = K.curve_tube('voder_cable', [P(0.44, 0.10, -0.300), P(0.46, 0.012, -0.42), P(0.43, 0.011, -0.60), P(0.38, 0.011, -0.74),
                                    Vector((TW + 0.08, 0.80, 0.012)), Vector((TW + 0.04, 0.80, 0.05)), Vector((TW + 0.018, 0.80, 0.12))],
                   0.0095, 'cable', res=12, bevel_res=4)
CONSOLE.append(cab)
gl2 = K.lathe('voder_gland2', [(0, 0), (0.016, 0), (0.016, 0.006), (0.012, 0.008), (0.012, 0.018), (0, 0.018)], 'chrome', seg=6)
gl2.rotation_euler = (math.radians(90), 0, 0)
gl2.location = P(0.44, 0.10, -0.300) + Vector((0, 0.0, 0.0))
CONSOLE.append(gl2)

# ═══ FINISH: apply, join statics per assembly, UVs, masks, export ═══════════
for o in CONSOLE + SPEAKER + MOVING + DECALS:
    if o.name in bpy.data.objects:
        K.apply_mods(o)
for o in CONSOLE + SPEAKER:
    K.apply_xform(o)
console = K.join([o for o in CONSOLE if o.name in bpy.data.objects], 'voder_console')
speaker = K.join([o for o in SPEAKER if o.name in bpy.data.objects], 'voder_speaker')
for o in [console, speaker] + MOVING:
    K.clean_slots(o)
    K.uv_tile(o)
for o in DECALS:
    if o.get('no_ao'):
        K.uv_tile(o)
bake_set = [console, speaker] + MOVING
K.uv_atlas(bake_set, margin=0.002)
K.stats()
K.bake_masks(bake_set, 'voder', res=2048, samples=48)
# moving parts: record pivots (glTF keeps them as node transforms)
LAYOUT['moving'] = [o.name for o in MOVING]
K.export_glb('voder', [console, speaker] + MOVING + DECALS, extras=LAYOUT)
print('[voder] done')
