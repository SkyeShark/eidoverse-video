"""era1_mainframe.py — an IBM 7090-era computer room at Bell Labs, 1961, as a hero asset.
blender --background --factory-startup --python era1_mainframe.py
-> work/daisy/props/assets/era1/mainframe.glb, mainframe_mask.png, mainframe_layout.json

Row of four 729-style tape drives (face-modelled cabinet masses: recessed reel deck
behind smoked glass, door-leaf seams, header control strip, blue vacuum columns
behind a glass door, side seams, back louvres) with reels (moving), head block,
capstans, guides and tape runs; two-tone grey/blue frame cabinets with door leaves,
louvre band, pulls and locks; a 7151-style operator console with a recessed lamp
field (brass bezels; the bulbs are GPU lamps added by the module), paddle keys,
emergency pull and nameplate; floor cables. No maker's marks.
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
N_DRIVES = int(os.environ.get('ERA1_DRIVES', '4'))
W, D, H = 0.74, 0.72, 1.80
ROW, REELS, DECALS, CONSOLE = [], [], [], []
LAYOUT = {'drives': [], 'cabinets': [], 'console': {}}


def T3(v):
    """Blender -> three.js coordinates."""
    return [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]


def obj_from_bm(name, bm, roles, bucket, bevel=0.003, seg=3, angle=35):
    ob = K.new_mesh_obj(name, bm, roles)
    if bevel:
        K.finish(ob, bevel, seg, angle)
    bucket.append(ob)
    return ob


def front_face_at(bm, x, z, y=0.0, tol=0.002):
    cands = [f for f in bm.faces if f.normal.y < -0.99 and abs(f.calc_center_median().y - y) < tol]
    for f in cands:
        xs = [v.co.x for v in f.verts]; zs = [v.co.z for v in f.verts]
        if min(xs) - 1e-6 <= x <= max(xs) + 1e-6 and min(zs) - 1e-6 <= z <= max(zs) + 1e-6:
            return f
    raise RuntimeError(f'no front face at {x},{z}')


def box_obj(name, w, d, h, c, roles, bucket, bevel=0.002, seg=2, rot=None):
    bm = bmesh.new()
    K.bm_box(bm, w, d, h, (0, 0, 0))
    ob = obj_from_bm(name, bm, roles, bucket, bevel, seg)
    if rot:
        ob.rotation_euler = rot
    ob.location = c
    return ob


# ═══ TAPE DRIVES ═════════════════════════════════════════════════════════════
DX = [(i - (N_DRIVES - 1) / 2) * W for i in range(N_DRIVES)]
PACK_FILE = [0.119, 0.097, 0.074, 0.110, 0.088, 0.103]
PACK_MACH = [0.071, 0.099, 0.116, 0.082, 0.107, 0.090]
RY, RXO, REEL_Y = 1.41, 0.162, 0.045                      # reel centre z, x offset, y (Blender)
DOOR = dict(x0=-0.13, x1=0.25, z0=0.075, z1=0.965)
WIN = dict(x0=-0.33, x1=0.33, z0=1.02, z1=1.585)
STRIP = dict(x0=-0.265, x1=0.235, z0=1.662, z1=1.748)


def reel(name, pack_r, clear):
    """A reel: hub along the local -Y axis (faces the front). Opaque parts one mesh; the
    file reel's clear flanges a second mesh (both children of the pivot empty)."""
    parts = []
    def flange(y, holes):
        s_bm = bmesh.new()
        segs = 96
        outer = [s_bm.verts.new((0.1335 * math.cos(2 * math.pi * k / segs), 0, 0.1335 * math.sin(2 * math.pi * k / segs))) for k in range(segs)]
        f = s_bm.faces.new(outer)
        ex = bmesh.ops.extrude_face_region(s_bm, geom=[f])
        top = [g for g in ex['geom'] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(s_bm, vec=(0, 0.0022, 0), verts=top)
        me = bpy.data.meshes.new('_fl'); s_bm.to_mesh(me); s_bm.free()
        o = bpy.data.objects.new('_fl', me); K.link(o)
        o.location = (0, y, 0)
        K.boolean(o, K.cutter_cyl(0.052, 0.02, (0, y, 0), rot=(math.radians(90), 0, 0), seg=64))
        if holes:
            for k in range(3):
                a0 = k * 2 * math.pi / 3 + 0.25
                cut = bpy.data.objects.new('_k', bpy.data.meshes.new('_k')); K.link(cut)
                cb = bmesh.new()
                pts_o = [(0.118 * math.cos(a0 + 1.35 * i / 16), 0.118 * math.sin(a0 + 1.35 * i / 16)) for i in range(17)]
                pts_i = [(0.066 * math.cos(a0 + 1.35 * i / 16), 0.066 * math.sin(a0 + 1.35 * i / 16)) for i in range(16, -1, -1)]
                vs = [cb.verts.new((x, -0.02, z)) for (x, z) in pts_o + pts_i]
                ff = cb.faces.new(vs)
                ex2 = bmesh.ops.extrude_face_region(cb, geom=[ff])
                tv = [g for g in ex2['geom'] if isinstance(g, bmesh.types.BMVert)]
                bmesh.ops.translate(cb, vec=(0, 0.04, 0), verts=tv)
                bmesh.ops.recalc_face_normals(cb, faces=cb.faces)
                cb.to_mesh(cut.data); cb.free()
                cut.location = (0, y, 0)
                K.boolean(o, cut)
        K.finish(o, 0.0006, 1, 30)
        K.apply_mods(o)
        return o
    pack = K.lathe('_pack', [(0.052, -0.00635), (pack_r, -0.00635), (pack_r, 0.00635), (0.052, 0.00635)], 'tape', seg=96)
    pack.rotation_euler = (math.radians(90), 0, 0)
    parts.append(pack)
    hub = K.lathe('_hub', [(0, -0.0135), (0.052, -0.0135), (0.052, 0.0135), (0, 0.0135)], 'reelhub', seg=64)
    hub.rotation_euler = (math.radians(90), 0, 0)
    parts.append(hub)
    # hub latch: a chamfered black cap with three raised locking tabs (lathe + boxes, clean topology)
    cap = K.lathe('_cap', [(0, 0), (0.034, 0), (0.035, 0.002), (0.035, 0.009), (0.032, 0.012), (0, 0.012)], 'blackplastic', seg=64)
    cap.rotation_euler = (math.radians(90), 0, 0)
    cap.location = (0, -0.0135, 0)
    parts.append(cap)
    for k in range(3):
        a_ = k * 2 * math.pi / 3 + math.pi / 2
        tb = bmesh.new()
        K.bm_box(tb, 0.010, 0.004, 0.016, (0, 0, 0))
        tab = K.new_mesh_obj('_tab', tb, ['blackplastic'])
        K.finish(tab, 0.0012, 2, 30)
        tab.rotation_euler = (0, a_, 0)
        tab.location = (math.cos(a_) * 0.024, -0.0275, -math.sin(a_) * 0.024) if False else (math.sin(a_) * 0.024, -0.0275, math.cos(a_) * 0.024)
        parts.append(tab)
    knob = K.lathe('_knob', [(0, 0), (0.011, 0), (0.011, 0.005), (0.009, 0.007), (0, 0.007)], 'reelhub', seg=32)
    knob.rotation_euler = (math.radians(90), 0, 0)
    knob.location = (0, -0.0255, 0)
    parts.append(knob)
    opaque_flanges = []
    if not clear:
        opaque_flanges = [flange(-0.0095, True), flange(0.0073, False)]
        for o in opaque_flanges:
            K.set_mats(o, ['reelwhite'])
    for o in parts:
        K.apply_mods(o)
        K.apply_xform(o)
    body = K.join(parts + opaque_flanges, name)
    out = [body]
    if clear:
        fa = flange(-0.0095, False)
        fb = flange(0.0073, False)
        for o in (fa, fb):
            K.set_mats(o, ['reelclear'])
            K.apply_xform(o)
        cf = K.join([fa, fb], name + '_clear')
        cf['no_ao'] = True
        out.append(cf)
    return out


for d, x in enumerate(DX):
    seed_name = f'mainframe_drive_{d + 1}'
    bm = bmesh.new()
    K.bm_box(bm, W, D, H - 0.06, (x, D / 2, 0.06 + (H - 0.06) / 2))
    front = front_face_at(bm, x, 0.9)
    # lower door leaf outline, then the glass-door recess inside it (field = column back)
    leaf = K.seam_rect(bm, front, 'x', 'z', x - 0.338, x + 0.338, 0.07, 1.005, gap=0.003, depth=0.004)
    dfield, dwalls, _ = K.recess(bm, K.cut_rect(bm, leaf[0], 'x', 'z', x + DOOR['x0'], x + DOOR['x1'], DOOR['z0'], DOOR['z1'])[0], 0.0, 0.09)
    for f in dwalls:
        f.material_index = 2
    for f in dfield:
        f.material_index = 2
    # blue band in the column field
    band, _ = K.cut_rect(bm, dfield[0], 'x', 'z', x - 0.045, x + 0.165, DOOR['z0'] + 0.04, DOOR['z1'] - 0.03)
    for f in band:
        f.material_index = 4
    # reel window recess (field = crinkle deck)
    wf = front_face_at(bm, x, 1.3)
    wfield, wwalls, _ = K.recess(bm, K.cut_rect(bm, wf, 'x', 'z', x + WIN['x0'], x + WIN['x1'], WIN['z0'], WIN['z1'])[0], 0.0, 0.09)
    for f in wfield:
        f.material_index = 1
    for f in wwalls:
        f.material_index = 2
    # header control strip recess
    hf = front_face_at(bm, x, 1.70)
    sfield, swalls, _ = K.recess(bm, K.cut_rect(bm, hf, 'x', 'z', x + STRIP['x0'], x + STRIP['x1'], STRIP['z0'], STRIP['z1'])[0], 0.0, 0.004)
    for f in sfield + swalls:
        f.material_index = 1
    # removable-cover seam wrapping the sides and top 5 cm behind the front
    K.groove_band(bm, 'y', 0.050, 0.053, 0.002)
    # back louvre pocket
    back = max([f for f in bm.faces if f.normal.y > 0.99], key=lambda f: f.calc_area())
    lin, _ = K.cut_rect(bm, back, 'x', 'z', x - 0.28, x + 0.28, 0.20, 0.55)
    K.recess(bm, lin, 0.0, 0.02)
    drive = obj_from_bm(seed_name, bm, ['enamel', 'crinkle', 'darkpaint', 'blue', 'columnblue'], ROW, bevel=0.0035)
    # plinth
    box_obj(f'{seed_name}_plinth', W - 0.03, D - 0.04, 0.062, (x, D / 2 + 0.01, 0.030), ['plinth'], ROW, 0.003)
    # aluminium corner trims with screws
    for sx in (-1, 1):
        box_obj(f'{seed_name}_trim', 0.012, 0.012, H - 0.07, (x + sx * (W / 2 - 0.006), -0.003, 0.06 + (H - 0.06) / 2), ['alu'], ROW, 0.0025)
        for zz in (0.10, H - 0.04):
            ROW.append(K.screw('_s', r=0.0028, h=0.0015, role='chrome', loc=(x + sx * (W / 2 - 0.006), -0.009, zz), normal=(0, -1, 0)))
    # window frame bars, smoked glass, chrome handle bar on standoffs
    for (w_, h_, cx, cz) in ((WIN['x1'] - WIN['x0'] + 0.03, 0.016, 0, WIN['z1'] + 0.004), (WIN['x1'] - WIN['x0'] + 0.03, 0.016, 0, WIN['z0'] - 0.004),
                             (0.016, WIN['z1'] - WIN['z0'], WIN['x0'] - 0.004, (WIN['z0'] + WIN['z1']) / 2),
                             (0.016, WIN['z1'] - WIN['z0'], WIN['x1'] + 0.004, (WIN['z0'] + WIN['z1']) / 2)):
        box_obj(f'{seed_name}_wframe', w_, 0.014, h_, (x + cx, -0.004, cz), ['alu'], ROW, 0.0022)
    g = box_obj(f'{seed_name}_smoked', WIN['x1'] - WIN['x0'], 0.004, WIN['z1'] - WIN['z0'], (x, 0.001, (WIN['z0'] + WIN['z1']) / 2), ['smoked'], DECALS, 0)
    g['no_ao'] = True
    hb = K.lathe(f'{seed_name}_handle', [(0, -0.15), (0.0075, -0.15), (0.0085, -0.145), (0.0085, 0.145), (0.0075, 0.15), (0, 0.15)], 'chrome', seg=24)
    hb.rotation_euler = (0, math.radians(90), 0)
    hb.location = (x, -0.024, WIN['z1'] - 0.036)
    ROW.append(hb)
    for sx in (-1, 1):
        post = K.lathe('_post', [(0, 0), (0.006, 0), (0.0055, 0.022), (0, 0.022)], 'chrome', seg=20)
        post.rotation_euler = (math.radians(90), 0, 0)
        post.location = (x + sx * 0.13, -0.002, WIN['z1'] - 0.036)
        ROW.append(post)
    # glass door: frame, pane, pull; label plate
    for (w_, h_, cx, cz) in ((DOOR['x1'] - DOOR['x0'] + 0.02, 0.014, (DOOR['x0'] + DOOR['x1']) / 2, DOOR['z0'] + 0.003),
                             (DOOR['x1'] - DOOR['x0'] + 0.02, 0.014, (DOOR['x0'] + DOOR['x1']) / 2, DOOR['z1'] - 0.003),
                             (0.014, DOOR['z1'] - DOOR['z0'], DOOR['x0'] + 0.003, (DOOR['z0'] + DOOR['z1']) / 2),
                             (0.014, DOOR['z1'] - DOOR['z0'], DOOR['x1'] - 0.003, (DOOR['z0'] + DOOR['z1']) / 2)):
        box_obj(f'{seed_name}_dframe', w_, 0.014, h_, (x + cx, -0.003, cz), ['alu'], ROW, 0.002)
    g = box_obj(f'{seed_name}_clearglass', DOOR['x1'] - DOOR['x0'] - 0.012, 0.003, DOOR['z1'] - DOOR['z0'] - 0.012,
                (x + (DOOR['x0'] + DOOR['x1']) / 2, 0.002, (DOOR['z0'] + DOOR['z1']) / 2), ['clearglass'], DECALS, 0)
    g['no_ao'] = True
    pull = K.curve_tube('_pull', [Vector((x + DOOR['x0'] + 0.03, -0.002, 0.50)), Vector((x + DOOR['x0'] + 0.03, -0.022, 0.52)),
                                   Vector((x + DOOR['x0'] + 0.03, -0.022, 0.72)), Vector((x + DOOR['x0'] + 0.03, -0.002, 0.74))], 0.006, 'chrome', res=8)
    ROW.append(pull)
    box_obj(f'{seed_name}_plate', 0.21, 0.004, 0.030, (x + (DOOR['x0'] + DOOR['x1']) / 2, -0.004, 0.935), ['blackplastic'], ROW, 0.001)
    DECALS.append(K.plane_decal(f'{seed_name}_platedecal', 0.20, 0.024, (x + (DOOR['x0'] + DOOR['x1']) / 2, -0.006, 0.935), (0, -1, 0), 'decal_plate'))
    # header strip: digit window + lamp/button bezels (lenses are GPU lamps in the module)
    lens_pos, btn_pos = [], []
    box_obj(f'{seed_name}_digitbez', 0.060, 0.008, 0.062, (x - 0.225, -0.001, 1.705), ['alu'], ROW, 0.002)
    for j in range(5):
        lx = x - 0.155 + j * 0.078
        box_obj(f'{seed_name}_lbez', 0.074, 0.006, 0.034, (lx, -0.0005, 1.726), ['blackplastic'], ROW, 0.0012)
        box_obj(f'{seed_name}_bbez', 0.074, 0.006, 0.032, (lx, -0.0005, 1.684), ['blackplastic'], ROW, 0.0012)
        lens_pos.append(T3((lx, -0.0035, 1.726)))
        btn_pos.append(T3((lx, -0.0035, 1.684)))
    for sx in (-1, 1):
        for zz in (1.668, 1.742):
            ROW.append(K.screw('_s', r=0.0022, h=0.0012, role='chrome', loc=(x + (STRIP['x0'] if sx < 0 else STRIP['x1']) - sx * 0.008, 0.0, zz), normal=(0, -1, 0)))
    # reel deck contents
    for sx in (-1, 1):
        sh = K.lathe('_shaft', [(0, 0), (0.014, 0), (0.014, 0.034), (0, 0.034)], 'reelhub', seg=24)
        sh.rotation_euler = (math.radians(90), 0, 0)
        sh.location = (x + sx * RXO, 0.090, RY)
        ROW.append(sh)
    hbk = bmesh.new()
    fs = K.bm_box(hbk, 0.13, 0.05, 0.075, (x, 0.065, 1.125))
    top = K.face_toward(fs, (0, -1, 0))
    K.recess(hbk, [top], 0.012, 0.006)
    obj_from_bm(f'{seed_name}_head', hbk, ['blackplastic'], ROW, 0.004)
    box_obj(f'{seed_name}_headcover', 0.085, 0.012, 0.030, (x, 0.036, 1.13), ['chrome'], ROW, 0.003)
    for sx in (-1, 1):
        ROW.append(K.screw('_s', r=0.002, h=0.0012, role='chrome', loc=(x + sx * 0.034, 0.030, 1.13), normal=(0, -1, 0)))
        cap_ = K.lathe('_capstan', [(0, 0), (0.018, 0), (0.018, 0.012), (0.014, 0.014), (0, 0.014)], 'chrome', seg=40)
        cap_.rotation_euler = (math.radians(90), 0, 0)
        cap_.location = (x + sx * 0.092, 0.058, 1.105)
        ROW.append(cap_)
        tire = K.lathe('_tire', [(0.0045, 0), (0.0085, 0), (0.0085, 0.016), (0.0045, 0.016)], 'rubber', seg=24)
        tire.rotation_euler = (math.radians(90), 0, 0)
        tire.location = (x + sx * 0.092, 0.058 - 0.014, 1.105)
        ROW.append(tire)
        gr = K.lathe('_guide', [(0, 0), (0.012, 0), (0.013, 0.003), (0.013, 0.015), (0.012, 0.018), (0, 0.018)], 'chrome', seg=32)
        gr.rotation_euler = (math.radians(90), 0, 0)
        gr.location = (x + sx * 0.135, 0.068, 1.215)
        ROW.append(gr)
        box_obj(f'{seed_name}_mouth', 0.024, 0.03, 0.07, (x + sx * 0.062, 0.070, 1.06), ['alu'], ROW, 0.003)
    # tape runs: tangent from each guide roller to its pack, and down to the mouths
    for sx, pr in ((-1, PACK_FILE[d % 6]), (1, PACK_MACH[d % 6])):
        cx, cz = sx * RXO, RY
        gx, gz = sx * 0.135 - sx * 0.012, 1.215
        ddx, ddz = gx - cx, gz - cz
        dd = math.hypot(ddx, ddz)
        al, be = math.atan2(ddz, ddx), math.acos(min(1, pr / dd))
        cands = [(cx + pr * math.cos(a), cz + pr * math.sin(a)) for a in (al + be, al - be)]
        tx, tz = max(cands, key=lambda p: -sx * p[0])
        L = math.hypot(gx - tx, gz - tz)
        ang = math.atan2(gx - tx, gz - tz)
        tb = bmesh.new(); K.bm_box(tb, 0.0016, 0.0127, L, (0, 0, -L / 2))
        tp = K.new_mesh_obj('_tape', tb, ['tape'])
        tp.rotation_euler = (0, ang + math.pi, 0)
        tp.location = (x + tx, REEL_Y, tz)
        ROW.append(tp)
        box_obj('_tape2', 0.0016, 0.0127, 0.15, (x + gx, 0.05, 1.14), ['tape'], ROW, 0)
    box_obj('_tape3', 0.17, 0.0127, 0.0016, (x, 0.040, 1.0885), ['tape'], ROW, 0)
    # vacuum column walls behind the door glass
    colx = [x + (DOOR['x0'] + DOOR['x1']) / 2 - 0.058, x + (DOOR['x0'] + DOOR['x1']) / 2 + 0.058]
    for cx in colx:
        for sx in (-1, 1):
            box_obj(f'{seed_name}_colwall', 0.006, 0.06, 0.78, (cx + sx * 0.038, 0.05, 0.53), ['alu'], ROW, 0.0015)
    # reels
    for side, sx, pr, clear in (('file', -1, PACK_FILE[d % 6], True), ('machine', 1, PACK_MACH[d % 6], False)):
        objs = reel(f'mainframe_reel_{d + 1}_{side}', pr, clear)
        piv = bpy.data.objects.new(f'mainframe_reel_{d + 1}_{side}_pivot', None)
        K.link(piv)
        piv.location = (x + sx * RXO, REEL_Y, RY)
        for o in objs:
            o.parent = piv
            o.location = (0, 0, 0)
        REELS.append((piv, objs, pr, side, d))
    LAYOUT['drives'].append({'x': round(x, 5), 'lens': lens_pos, 'buttons': btn_pos, 'digit': T3((x - 0.225, -0.0035, 1.705)),
                             'loops': [[round(c, 5), round(-0.05, 5)] for c in colx], 'packFile': PACK_FILE[d % 6],
                             'packMachine': PACK_MACH[d % 6]})

# ═══ FRAME CABINETS (two-tone grey / blue) ═══════════════════════════════════
CW, CD = 0.80, 0.76
ends = [DX[0] - W / 2 - CW / 2 - 0.004, DX[-1] + W / 2 + CW / 2 + 0.004]
for i, cx in enumerate(ends):
    nm = f'mainframe_cabinet_{i + 1}'
    bm = bmesh.new()
    K.bm_box(bm, CW, CD, H - 0.10, (cx, CD / 2, 0.06 + (H - 0.10) / 2))
    front = front_face_at(bm, cx, 0.9)
    left = K.seam_rect(bm, front, 'x', 'z', cx - 0.372, cx - 0.004, 0.25, 1.62, gap=0.003, depth=0.004)
    for f in left:
        f.material_index = 1
    right_face = front_face_at(bm, cx + 0.2, 0.9)
    right = K.seam_rect(bm, right_face, 'x', 'z', cx + 0.004, cx + 0.372, 0.25, 1.62, gap=0.003, depth=0.004)
    for f in right:
        f.material_index = 1
    lf = front_face_at(bm, cx, 0.16)
    lfield, lwalls, _ = K.recess(bm, K.cut_rect(bm, lf, 'x', 'z', cx - 0.34, cx + 0.34, 0.09, 0.225)[0], 0.0, 0.03)
    for f in lfield + lwalls:
        f.material_index = 2
    tf = front_face_at(bm, cx, 1.70)
    tfield, twalls, _ = K.recess(bm, K.cut_rect(bm, tf, 'x', 'z', cx - 0.30, cx + 0.30, 1.672, 1.728)[0], 0.0, 0.004)
    for f in tfield + twalls:
        f.material_index = 2
    K.groove_band(bm, 'y', 0.050, 0.053, 0.002)
    obj_from_bm(nm, bm, ['greyenamel', 'blue', 'crinkle'], ROW, bevel=0.004)
    box_obj(f'{nm}_cap', CW + 0.012, CD + 0.012, 0.042, (cx, CD / 2, H - 0.019), ['greyenamel'], ROW, 0.006)
    box_obj(f'{nm}_plinth', CW - 0.03, CD - 0.04, 0.062, (cx, CD / 2 + 0.01, 0.030), ['plinth'], ROW, 0.003)
    for k in range(6):
        fin = box_obj(f'{nm}_fin', CW - 0.10, 0.004, 0.022, (cx, 0.012, 0.105 + k * 0.021), ['crinkle'], ROW, 0.001, rot=(math.radians(-38), 0, 0))
    lamps = []
    for k in range(6):
        lx = cx - 0.25 + k * 0.1
        rb = K.lathe('_bez', [(0.0085, 0), (0.0125, 0), (0.0125, 0.003), (0.0095, 0.004), (0.0085, 0.002)], 'brass', seg=24)
        rb.rotation_euler = (math.radians(90), 0, 0)
        rb.location = (lx, 0.004, H - 0.10)
        ROW.append(rb)
        lamps.append(T3((lx, 0.003, H - 0.10)))
    for sx in (-1, 1):
        pull = K.curve_tube('_cpull', [Vector((cx + sx * 0.03, -0.004, 0.94)), Vector((cx + sx * 0.03, -0.026, 0.96)),
                                        Vector((cx + sx * 0.03, -0.026, 1.14)), Vector((cx + sx * 0.03, -0.004, 1.16))], 0.0065, 'chrome', res=8)
        ROW.append(pull)
        esc = K.lathe('_lock', [(0, 0), (0.011, 0), (0.011, 0.003), (0.008, 0.005), (0, 0.005)], 'chrome', seg=32)
        esc.rotation_euler = (math.radians(90), 0, 0)
        esc.location = (cx + sx * 0.03, -0.004, 1.25)
        ROW.append(esc)
    LAYOUT['cabinets'].append({'x': round(cx, 5), 'lamps': lamps})

# ═══ OPERATOR CONSOLE ════════════════════════════════════════════════════════
cX, cZ3, cYaw = [float(v) for v in os.environ.get('ERA1_CONSOLE', '0.95,1.35,-0.38').split(',')]
croot = bpy.data.objects.new('mainframe_console', None)
K.link(croot)
CWD, DESK = 1.70, 0.74
bm = bmesh.new()
K.bm_box(bm, CWD, 0.66, DESK - 0.035 - 0.10, (0, 0.05, 0.10 + (DESK - 0.035 - 0.10) / 2))
panel_face = front_face_at(bm, 0, 0.45, y=0.05 - 0.33)
K.seam_rect(bm, panel_face, 'x', 'z', -0.78, 0.78, 0.16, 0.66, gap=0.003, depth=0.004)
obj_from_bm('mainframe_console_desk', bm, ['blue'], CONSOLE, bevel=0.004)
box_obj('mainframe_console_plinth', CWD - 0.08, 0.58, 0.102, (0, 0.09, 0.050), ['plinth'], CONSOLE, 0.003)
bm = bmesh.new()
K.bm_box(bm, CWD + 0.04, 0.80, 0.035, (0, 0.0, DESK - 0.0175))
K.groove_band(bm, 'z', DESK - 0.024, DESK - 0.012, 0.003)
obj_from_bm('mainframe_console_top', bm, ['laminate'], CONSOLE, bevel=0.003)
box_obj('mainframe_console_edge', CWD + 0.037, 0.797, 0.0095, (0, 0.0, DESK - 0.018), ['alu'], CONSOLE, 0.0015)
# upright lamp-panel housing (tilted back), lamp field recessed into its face
TILT, PZ3, PH_ = 0.17, -0.22, 0.58
bm = bmesh.new()
K.bm_box(bm, 1.60, 0.22, PH_, (0, 0, 0))
pf = front_face_at(bm, 0, 0.0, y=-0.11)
field, walls, _ = K.recess(bm, K.cut_rect(bm, pf, 'x', 'z', -0.735, 0.735, -0.205, 0.205)[0], 0.0, 0.012)
for f in field:
    f.material_index = 1
for f in walls:
    f.material_index = 2
wing = front_face_at(bm, 0.77, 0.0, y=-0.11)
wf_, ww_, _ = K.recess(bm, K.cut_rect(bm, wing, 'x', 'z', 0.745, 0.79, -0.20, 0.205)[0], 0.0, 0.006)
for f in wf_ + ww_:
    f.material_index = 3
housing = obj_from_bm('mainframe_console_housing', bm, ['greyenamel', 'panelbase', 'alu', 'crinkle'], CONSOLE, bevel=0.005)
housing.rotation_euler = (-TILT, 0, 0)           # lean back (top toward +Y)
housing.location = (0, -PZ3 + 0.06, DESK + PH_ / 2)
bpy.context.view_layer.update()
HM = housing.matrix_world.copy()


def on_panel(x, z, h):
    """point on the recessed lamp field (housing-local x, z), h metres proud; console-local Blender."""
    return HM @ Vector((x, -0.11 + 0.012 - h, z))


PW, PHh = 1.46, 0.40
lamp_list = []                                    # (x, z, kind, a, b) in panel-local metres


def row(z, x0, n, dx, kind, rid):
    for c in range(n):
        lamp_list.append((x0 + c * dx, z, kind, rid, n - 1 - c))


row(0.155, -0.67, 15, 0.031, 0, 1); row(0.105, -0.67, 15, 0.031, 0, 2); row(0.055, -0.67, 15, 0.031, 0, 3)
row(0.160, -0.03, 10, 0.064, 2, 0)
row(0.108, -0.03, 18, 0.0355, 0, 4); row(0.055, 0.075, 15, 0.0355, 1, 5)
row(-0.045, -0.66, 38, 0.0355, 0, 6); row(-0.105, -0.66, 38, 0.0355, 0, 7); row(-0.165, -0.66, 36, 0.0355, 0, 8)
lamp_list = [(x, z, k, (1 if (k == 2 and b == 3) else 0) if k == 2 else a, 0 if k == 2 else b) for (x, z, k, a, b) in lamp_list]
bez_objs = []
tor = bmesh.new()
bmesh.ops.create_circle(tor, cap_ends=False, segments=20, radius=0.0078)
master = K.lathe('_lbez', [(0.0060, 0.0), (0.0098, 0.0), (0.0098, 0.0012), (0.0082, 0.0026), (0.0062, 0.0020)], 'brass', seg=20)
K.apply_xform(master)
for (x, z, k, a, b) in lamp_list:
    o = bpy.data.objects.new('_lb', master.data)
    K.link(o)
    o.matrix_world = Matrix.Translation(on_panel(x, z, 0.0)) @ (HM.to_quaternion() @ Quaternion((1, 0, 0), math.radians(90))).to_matrix().to_4x4()
    bez_objs.append(o)
for o in bez_objs:
    o.data = o.data.copy()
    K.apply_xform(o)
bez = K.join(bez_objs, 'mainframe_console_bezels')
bpy.data.objects.remove(master, do_unlink=True)
CONSOLE.append(bez)
# status squares' bezels + emergency pull + indicator column
STATUS = [(-0.143, 0.158), (-0.086, 0.158), (-0.143, 0.101), (-0.086, 0.101)]
for (sx_, sz_) in STATUS:
    o = box_obj('_sbez', 0.058, 0.006, 0.056, (0, 0, 0), ['alu'], CONSOLE, 0.0015)
    o.matrix_world = Matrix.Translation(on_panel(sx_, sz_, 0.003)) @ HM.to_quaternion().to_matrix().to_4x4()
em = K.lathe('_emerg', [(0, 0), (0.014, 0), (0.014, 0.020), (0.012, 0.026), (0, 0.027)], 'red', seg=32)
em.matrix_world = Matrix.Translation(on_panel(0.767, 0.17, 0.0)) @ (HM.to_quaternion() @ Quaternion((1, 0, 0), math.radians(90))).to_matrix().to_4x4()
CONSOLE.append(em)
col_pos = []
for i in range(4):
    o = box_obj('_cbez', 0.044, 0.006, 0.038, (0, 0, 0), ['alu'], CONSOLE, 0.0012)
    o.matrix_world = Matrix.Translation(on_panel(0.767, 0.08 - i * 0.055, 0.003)) @ HM.to_quaternion().to_matrix().to_4x4()
    col_pos.append((0.767, 0.08 - i * 0.055))
# nameplate on the housing top edge
top_pt = HM @ Vector((0.42, -0.05, PH_ / 2))
npl = box_obj('mainframe_console_nameplate', 0.36, 0.012, 0.046, top_pt + Vector((0, 0, 0.022)), ['alu'], CONSOLE, 0.003)
DECALS.append(K.plane_decal('mainframe_console_name', 0.34, 0.034, top_pt + Vector((0, -0.0065, 0.022)), (0, -1, 0), 'decal_name'))
# key shelf with 36 paddle entry keys + function buttons
bm = bmesh.new()
K.bm_profile_x(bm, [(-0.14, DESK - 0.001), (-0.14, DESK + 0.018), (0.02, DESK + 0.040), (0.02, DESK - 0.001)], -0.70, 0.70)
obj_from_bm('mainframe_console_shelf', bm, ['greyenamel'], CONSOLE, bevel=0.004)
for i in range(36):
    x = -0.63 + i * 0.034 + (i // 3) * 0.006
    role = 'keydark' if (i // 3) % 2 == 0 else 'keylight'
    k = box_obj('_key', 0.026, 0.05, 0.014, (x, -0.075, DESK + 0.032), [role], CONSOLE, 0.004, rot=(math.radians(8), 0, 0))
for i in range(10):
    box_obj('_fkey', 0.07, 0.03, 0.016, (-0.54 + i * 0.12, -0.012, DESK + 0.040), ['keylight' if i % 2 else 'keydark'], CONSOLE, 0.005,
            rot=(math.radians(8), 0, 0))
DECALS.append(K.plane_decal('mainframe_console_panel', PW, PHh, on_panel(0, 0, 0.0005), HM.to_quaternion() @ Vector((0, -1, 0)), 'decal_panel',
                            up=HM.to_quaternion() @ Vector((0, 0, 1))))
LAYOUT['console'] = {
    'pos': [cX, 0.0, cZ3], 'yaw': cYaw,
    'panel': {'center': T3(on_panel(0, 0, 0.0)), 'normal': T3(HM.to_quaternion() @ Vector((0, -1, 0))),
              'up': T3(HM.to_quaternion() @ Vector((0, 0, 1))), 'w': PW, 'h': PHh},
    'lamps': [[round(x, 5), round(z, 5), k, a, b] for (x, z, k, a, b) in lamp_list],
    'status': [[x, z] for (x, z) in STATUS], 'column': [[x, z] for (x, z) in col_pos],
}
# floor cables: from under the console back along the floor into a grommet in the floor
cab_objs = []
a_ = Matrix.Rotation(cYaw, 4, 'Z')
base = Vector((cX, -cZ3, 0))
grommet = base + a_ @ Vector((0.05, 0.72, 0.0))
gr = K.lathe('mainframe_grommet', [(0.045, 0.0), (0.065, 0.0), (0.065, 0.004), (0.058, 0.007), (0.045, 0.006)], 'blackplastic', seg=40)
gr.location = grommet
ROW.append(gr)
for k, xo in enumerate((-0.35, -0.05, 0.25)):
    start = base + a_ @ Vector((xo, 0.34, 0.0))
    pts = [start + Vector((0, 0, 0.11)), start + a_ @ Vector((0, 0.05, 0.013)), start.lerp(grommet, 0.55) + Vector((0, 0, 0.012)),
           grommet + a_ @ Vector(((k - 1) * 0.018, -0.03, 0.012)), grommet + a_ @ Vector(((k - 1) * 0.018, 0.0, -0.06))]
    cab_objs.append(K.curve_tube(f'mainframe_floorcable_{k}', pts, 0.011 - k * 0.0015, 'cable', res=10))
ROW = ROW + cab_objs

# ═══ FINISH ══════════════════════════════════════════════════════════════════
for o in ROW + CONSOLE + DECALS:
    if o.name in bpy.data.objects:
        K.apply_mods(o)
for o in ROW + CONSOLE:
    K.apply_xform(o)
row_obj = K.join([o for o in ROW if o.name in bpy.data.objects], 'mainframe_row')
con_obj = K.join([o for o in CONSOLE if o.name in bpy.data.objects], 'mainframe_console_body')
reel_meshes = []
for (piv, objs, pr, side, d) in REELS:
    for o in objs:
        K.apply_mods(o)
        reel_meshes.append(o)
for o in [row_obj, con_obj] + reel_meshes:
    K.clean_slots(o)
    K.uv_tile(o)
for o in DECALS:
    if o.get('no_ao'):
        K.uv_tile(o)
bake_set = [row_obj, con_obj] + [o for o in reel_meshes if not o.get('no_ao')]
K.uv_atlas(bake_set, margin=0.0015)
# console hierarchy: parent the console body + its decals to the console empty (console-local frame)
croot.location = (cX, -cZ3, 0)
croot.rotation_euler = (0, 0, cYaw)
bpy.context.view_layer.update()
for o in [con_obj] + [d for d in DECALS if d.name.startswith('mainframe_console')]:
    mw = o.matrix_world.copy()
    o.parent = croot
    o.matrix_world = croot.matrix_world @ mw
K.stats()
K.bake_masks(bake_set, 'mainframe', res=2048, samples=40)
pivots = [p for (p, _, _, _, _) in REELS]
LAYOUT['reels'] = [{'name': p.name, 'drive': d, 'side': side, 'packRadius': pr} for (p, _, pr, side, d) in REELS]
K.export_glb('mainframe', [row_obj, croot, con_obj] + pivots + reel_meshes + DECALS, extras=LAYOUT)
print('[mainframe] done')
