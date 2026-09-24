"""The campfire: a ring of 12 field stones (inner radius 0.42, soot on the fire side), a teepee of
five logs (two split) charred into alligator plates, and a bed of ash and coal with charcoal lumps.
EMISSIVE: the glowing crack/coal mask is baked (<key>_glow) and exported as the glTF emissiveTexture
with emissiveFactor (1, 0.35, 0.08) on FireLogs and FireAsh. The engine flickers emissiveIntensity.
Origin: ground centre of the ring.  -> glb/camp_fire.glb ('FireStones', 'FireLogs', 'FireAsh')
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix, noise
from clib import *
from camp_lib import *
from camp_logs import *

reset()
R_IN = 0.42
EMBER = (1.0, 0.35, 0.08)
rnd = rng(7)


# ======================================================================================= stones
def stone(seed, sx, sy, sz):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
    off = Vector((seed * 3.1, seed * 1.7, seed * 2.3))
    for v in bm.verts:
        p = v.co.copy()
        d = 0.20 * noise.noise(p * 1.25 + off) + 0.07 * noise.noise(p * 3.4 + off * 2) + 0.022 * noise.noise(p * 9 + off)
        v.co = p * (1 + d)
        if v.co.z < -0.42:                       # a flat-ish bedding face
            v.co.z = -0.42 - (v.co.z + 0.42) * 0.12
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= zmin + 0.016                  # bedded 1.6 cm into the soil
    return bm


def stone_extra(nb, col, vec):
    oc = obj_coord(nb)
    x, y, z = sep_xyz(nb, oc)
    geo = nb.n('ShaderNodeNewGeometry')
    # per-stone hue: some browner, some bluer
    hue = ramp_s(nb, nb.noise(oc, 2.2, 1.0, 0.4), 0.35, 0.65)
    col = nb.mix(nb.math('MULTIPLY', hue, 0.45), col, (0.20, 0.16, 0.12))
    # inward-facing (toward the fire): soot + fire-reddening at its edge
    inward = nb.n('ShaderNodeVectorMath', operation='NORMALIZE')
    cxy = nb.n('ShaderNodeCombineXYZ'); nb.l(nb.math('MULTIPLY', x, -1.0), cxy.inputs[0]); nb.l(nb.math('MULTIPLY', y, -1.0), cxy.inputs[1])
    nb.l(cxy.outputs[0], inward.inputs[0])
    dp = nb.n('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    nb.l(geo.outputs['Normal'], dp.inputs[0]); nb.l(inward.outputs[0], dp.inputs[1])
    face_in = dp.outputs['Value']
    up = sep_xyz(nb, geo.outputs['Normal'])[2]
    top_in = nb.math('MULTIPLY', ramp_s(nb, up, 0.2, 0.9), ramp_s(nb, face_in, -0.5, 0.2))
    s = nb.math('MAXIMUM', ramp_s(nb, face_in, -0.15, 0.55), nb.math('MULTIPLY', top_in, 0.7))
    s = nb.math('ADD', s, nb.math('MULTIPLY', nb.math('SUBTRACT', nb.noise(oc, 9.0, 5.0, 0.65), 0.5), 0.9))
    soot = ramp_s(nb, s, 0.25, 0.75)
    redden = nb.math('MULTIPLY', ramp_s(nb, s, 0.05, 0.3), ramp_s(nb, s, 0.55, 0.3))
    col = nb.mix(nb.math('MULTIPLY', redden, 0.3), col, (0.22, 0.10, 0.05))
    col = nb.mix(nb.math('MULTIPLY', soot, 0.95), col, (0.018, 0.016, 0.015))
    # ash dust settled on the tops, moss low on the outside
    dust = nb.math('MULTIPLY', ramp_s(nb, up, 0.55, 0.95), ramp_s(nb, nb.noise(oc, 14.0, 3.0, 0.6), 0.45, 0.7))
    col = nb.mix(nb.math('MULTIPLY', dust, 0.45), col, (0.42, 0.41, 0.39))
    out_low = nb.math('MULTIPLY', ramp_s(nb, z, 0.06, 0.0), ramp_s(nb, face_in, 0.1, -0.5))
    moss = nb.math('MULTIPLY', out_low, ramp_s(nb, nb.noise(oc, 11.0, 4.0, 0.6), 0.5, 0.66))
    return nb.mix(nb.math('MULTIPLY', moss, 0.7), col, (0.10, 0.14, 0.05))


m_stone = layered_mat('stone', 'Rock058', scale=3.5, tint=(1.05, 1.0, 0.95), sat=0.7, val=0.78, rough_add=0.05,
                      nstr=1.3, extra_color=stone_extra,
                      wear=dict(color=(0.30, 0.29, 0.28), radius=0.006, amount=0.5, rough=0.5, gain=10, noise=20),
                      grime=dict(color=(0.03, 0.028, 0.026), dist=0.04, amount=0.8, gain=2.0))
set_glow(m_stone, lambda nb: (0.0, 0.0, 0.0))

stones = []
N = 12
ang = 0.0
for i in range(N):
    a = i / N * math.tau + rnd.uniform(-0.09, 0.09)
    w = rnd.uniform(0.075, 0.125)            # half tangential width
    d = rnd.uniform(0.06, 0.10)              # half radial depth
    h = rnd.uniform(0.055, 0.085)            # half height
    bm = stone(i + 1, w, d, h)
    s = obj_from_bm(f'stone{i}', bm, m_stone)
    rho = R_IN + d * 0.92 + rnd.uniform(0.0, 0.025)
    s.rotation_euler = (rnd.uniform(-0.12, 0.12), rnd.uniform(-0.18, 0.05), a + math.pi / 2 + rnd.uniform(-0.2, 0.2))
    s.location = (rho * math.cos(a), rho * math.sin(a), 0.0)
    select_only(s); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # re-bed after the tilt: lowest point 1.6 cm under the ground
    zmin = min((s.matrix_world @ v.co).z for v in s.data.vertices)
    s.location.z -= zmin + 0.016
    select_only(s); bpy.ops.object.transform_apply(location=True)
    smooth(s, 60)
    uv_tex(s, 0.35)
    stones.append(s)
ST = join(stones, 'FireStones')

# ========================================================================================= logs
def heat_mask(nb):
    """Heat of the flame column: high near the fire axis at every height up to ~0.5 m, high in
    the coal bed, boosted on faces turned toward the axis; noisy edges."""
    oc = obj_coord(nb)
    x, y, z = sep_xyz(nb, oc)
    geo = nb.n('ShaderNodeNewGeometry')
    r = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', x, x), nb.math('MULTIPLY', y, y)))
    inward = nb.n('ShaderNodeVectorMath', operation='NORMALIZE')
    cxy = nb.n('ShaderNodeCombineXYZ'); nb.l(nb.math('MULTIPLY', x, -1.0), cxy.inputs[0]); nb.l(nb.math('MULTIPLY', y, -1.0), cxy.inputs[1])
    nb.l(cxy.outputs[0], inward.inputs[0])
    dp = nb.n('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    nb.l(geo.outputs['Normal'], dp.inputs[0]); nb.l(inward.outputs[0], dp.inputs[1])
    down = ramp_s(nb, sep_xyz(nb, geo.outputs['Normal'])[2], 0.2, -0.6)
    column = nb.math('MULTIPLY', ramp_s(nb, r, 0.26, 0.08), ramp_s(nb, z, 0.66, 0.44))
    bed = ramp_s(nb, z, 0.16, 0.04)
    face = nb.math('MULTIPLY', ramp_s(nb, dp.outputs['Value'], -0.35, 0.45), ramp_s(nb, r, 0.36, 0.12))
    heat = nb.math('MAXIMUM', column, bed)
    heat = nb.math('MAXIMUM', heat, nb.math('MULTIPLY', face, 0.9))
    heat = nb.math('MAXIMUM', heat, nb.math('MULTIPLY', nb.math('MULTIPLY', down, ramp_s(nb, r, 0.3, 0.1)), 0.9))
    heat = nb.math('ADD', heat, nb.math('MULTIPLY', nb.math('SUBTRACT', nb.noise(oc, 6.0, 5.0, 0.65), 0.5), 0.55))
    return heat, oc


def char_cells(nb, oc, scale=48.0, along=0.62, use_uv=True):
    if use_uv:
        uvn = nb.n('ShaderNodeUVMap', uv_map='TexUV')
        mp = nb.n('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, along, 1.0)
        nb.l(uvn.outputs['UV'], mp.inputs['Vector'])
        base = mp.outputs[0]
    else:
        base = oc
    wob = nb.n('ShaderNodeTexNoise'); wob.inputs['Scale'].default_value = 22.0; wob.inputs['Detail'].default_value = 3.0
    nb.l(base, wob.inputs['Vector'])
    sc = nb.n('ShaderNodeVectorMath', operation='SCALE'); nb.l(wob.outputs['Color'], sc.inputs[0]); sc.inputs['Scale'].default_value = 0.03
    dist = nb.n('ShaderNodeVectorMath', operation='ADD')
    nb.l(base, dist.inputs[0]); nb.l(sc.outputs[0], dist.inputs[1])
    cells = nb.n('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE')
    cells.inputs['Scale'].default_value = scale
    cells.inputs['Randomness'].default_value = 1.0
    nb.l(dist.outputs[0], cells.inputs['Vector'])
    return cells.outputs['Distance']


def char_layer(nb, col):
    heat, oc = heat_mask(nb)
    char = ramp_s(nb, heat, 0.30, 0.52)
    cd = char_cells(nb, oc)
    crack = ramp_s(nb, cd, 0.0, 0.08, (1, 1, 1, 1), (0, 0, 0, 1))
    gate = ramp_s(nb, nb.noise(oc, 5.0, 4.0, 0.6), 0.36, 0.6)            # smooth-black vs cracked areas
    crack = nb.math('MULTIPLY', crack, gate)
    tone = ramp_s(nb, nb.noise(oc, 30.0, 3.0, 0.6), 0.3, 0.7)
    plate = nb.mix(tone, (0.012, 0.011, 0.010), (0.045, 0.042, 0.040))
    plate = nb.mix(nb.math('MULTIPLY', crack, 0.9), plate, (0.003, 0.002, 0.002))
    ash_f = nb.math('MULTIPLY', ramp_s(nb, heat, 0.85, 1.2), ramp_s(nb, nb.noise(oc, 24.0, 3.0, 0.6), 0.55, 0.68))
    plate = nb.mix(nb.math('MULTIPLY', ash_f, 0.5), plate, (0.28, 0.27, 0.26))
    scorch = nb.math('MULTIPLY', ramp_s(nb, heat, 0.12, 0.30), ramp_s(nb, heat, 0.55, 0.30))
    col = nb.mix(nb.math('MULTIPLY', scorch, 0.85), col, (0.07, 0.035, 0.018))
    return nb.mix(char, col, plate)


def char_glow(nb):
    heat, oc = heat_mask(nb)
    x, y, z = sep_xyz(nb, oc)
    geo = nb.n('ShaderNodeNewGeometry')
    low = ramp_s(nb, z, 0.34, 0.12)                                    # embers live low in the fire
    under = ramp_s(nb, sep_xyz(nb, geo.outputs['Normal'])[2], 0.35, -0.4)
    zone = nb.math('MAXIMUM', low, nb.math('MULTIPLY', under, ramp_s(nb, z, 0.45, 0.25)))
    cd = char_cells(nb, oc)
    crack = ramp_s(nb, cd, 0.0, 0.07, (1, 1, 1, 1), (0, 0, 0, 1))
    gate = ramp_s(nb, nb.noise(oc, 5.0, 4.0, 0.6), 0.36, 0.6)
    hot = ramp_s(nb, heat, 0.66, 1.05)
    patch = ramp_s(nb, nb.noise(oc, 4.5, 4.0, 0.6), 0.44, 0.64)
    g = nb.math('MULTIPLY', nb.math('MULTIPLY', hot, patch),
                nb.math('ADD', nb.math('MULTIPLY', nb.math('MULTIPLY', crack, gate), 0.85), 0.10))
    g = nb.math('MULTIPLY', g, zone)
    tips = nb.math('MULTIPLY', ramp_s(nb, z, 0.075, 0.03), ramp_s(nb, nb.noise(oc, 13.0, 4.0, 0.6), 0.35, 0.6))
    inward = nb.n('ShaderNodeVectorMath', operation='NORMALIZE')
    cxy = nb.n('ShaderNodeCombineXYZ'); nb.l(nb.math('MULTIPLY', x, -1.0), cxy.inputs[0]); nb.l(nb.math('MULTIPLY', y, -1.0), cxy.inputs[1])
    nb.l(cxy.outputs[0], inward.inputs[0])
    dp = nb.n('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    nb.l(geo.outputs['Normal'], dp.inputs[0]); nb.l(inward.outputs[0], dp.inputs[1])
    facing = nb.math('MAXIMUM', ramp_s(nb, dp.outputs['Value'], -0.15, 0.45), under)
    tips = nb.math('MULTIPLY', tips, facing)
    return nb.math('MAXIMUM', g, nb.math('MULTIPLY', tips, 0.9))


bark = layered_mat('fbark', 'Bark012', scale=3.2, tint=(0.80, 0.66, 0.52), sat=0.75, val=0.66, rough_add=0.18, nstr=1.6,
                   grime=dict(color=(0.035, 0.03, 0.025), dist=0.03, amount=0.8, gain=1.9))
endg = endgrain_clamp(layered_mat('fend', 'TreeEnd004', scale=1.0, tint=(0.95, 0.86, 0.74), sat=0.8, val=0.7,
                                  rough_add=0.2, nstr=1.0,
                                  grime=dict(color=(0.05, 0.04, 0.03), dist=0.02, amount=0.6)))
split = layered_mat('fsplit', 'Wood049', scale=2.2, tint=(1.0, 0.86, 0.70), sat=0.9, val=0.7, rough_add=0.15, nstr=1.2,
                    wear=dict(color=(0.55, 0.45, 0.33), radius=0.004, amount=0.6, rough=0.8, gain=12),
                    grime=dict(color=(0.05, 0.04, 0.03), dist=0.02, amount=0.6))
for m in (bark, endg, split):
    wrap_color(m, char_layer)
    set_glow(m, char_glow)


def seg_dist(p1, q1, p2, q2):
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1.dot(d1), d2.dot(d2), d2.dot(r)
    c, b = d1.dot(r), d1.dot(d2)
    den = a * e - b * b
    s = max(0.0, min(1.0, (b * f - c * e) / den)) if den > 1e-9 else 0.0
    t = (b * s + f) / e
    if t < 0: t, s = 0.0, max(0.0, min(1.0, -c / a))
    elif t > 1: t, s = 1.0, max(0.0, min(1.0, (b - c) / a))
    return ((p1 + d1 * s) - (p2 + d2 * t)).length


# cone teepee by random search: 5 logs whose tips lean onto a small ring above the coals, adjacent
# logs resting against each other (axes >= 0.97 x radius sum), none passing through another
best, best_score = None, -1e9
tr = rng(1234)
for trial in range(8000):
    cfg = []
    base = tr.uniform(0, math.tau)
    twist = tr.uniform(0.15, 0.45)
    rho_t = tr.uniform(0.065, 0.095)
    for k in range(5):
        th = base + k / 5 * math.tau + tr.uniform(-0.16, 0.16)
        b = tr.uniform(0.27, 0.31)
        rad_ = tr.uniform(0.036, 0.054)
        B = Vector((b * math.cos(th), b * math.sin(th), 0.022 + rad_ * 0.55))
        T = Vector((rho_t * math.cos(th + twist), rho_t * math.sin(th + twist), tr.uniform(0.44, 0.52)))
        L = (T - B).length + tr.uniform(0.0, 0.02)
        cfg.append([B, (T - B).normalized(), L, rad_])
    if not all(0.45 <= c[2] <= 0.60 for c in cfg):
        continue
    score = 1e9
    for i in range(5):
        for j in range(i + 1, 5):
            dd = seg_dist(cfg[i][0], cfg[i][0] + cfg[i][1] * cfg[i][2], cfg[j][0], cfg[j][0] + cfg[j][1] * cfg[j][2])
            score = min(score, dd - 0.97 * (cfg[i][3] + cfg[j][3]))
    # prefer RESTING (score just above 0) over floating (large positive)
    val = score if score < 0 else -score * 0.25
    if val > best_score:
        best, best_score = cfg, val
print('[fire] teepee contact score %.4f (0 = resting)  lengths %s' % (best_score, [round(c[2], 3) for c in best]))
logs = []
for k, (B, d, L, rad_) in enumerate(best):
    is_split = k in (1, 3)
    lg = log_mesh(f'log{k}', L, rad_, seed=40 + k, bend=0.006, na=26, nl=22,
                  split={'z': rad_ * 0.12} if is_split else None, mats=[bark, endg, split], bark_amp=0.05)
    if is_split:
        lg.rotation_euler = (math.radians(160 + 70 * k), 0, 0)
        select_only(lg); bpy.ops.object.transform_apply(rotation=True)
    place_log(lg, B, B + d * L)
    smooth(lg, 50)
    logs.append(lg)
kind_specs = []
kr = rng(77)
for k in range(5):
    Bk, dk, Lk, rk = best[k]
    Bn = best[(k + 1) % 5][0]
    mid_th = math.atan2((Bk.y + Bn.y) / 2, (Bk.x + Bn.x) / 2)
    if k % 2:
        continue
    rs = kr.uniform(0.011, 0.018)
    B = Vector((0.24 * math.cos(mid_th), 0.24 * math.sin(mid_th), 0.02 + rs))
    T = Vector((0.10 * math.cos(mid_th + 0.3), 0.10 * math.sin(mid_th + 0.3), kr.uniform(0.30, 0.40)))
    kind_specs.append([B, (T - B).normalized(), (T - B).length, rs])
kind_final = []
for (B, d, L, rs) in kind_specs:
    # pull the stick back until it clears every log
    for it in range(40):
        clear = all(seg_dist(B, B + d * L, c[0], c[0] + c[1] * c[2]) >= 0.98 * (rs + c[3]) for c in best)
        if clear:
            break
        L -= 0.01
    st = log_mesh('kindling', L, rs, seed=90 + int(B.x * 100), bend=0.01, na=12, nl=14, mats=[bark, endg, split],
                  bark_amp=0.08)
    place_log(st, B, B + d * L)
    smooth(st, 50)
    logs.append(st)
    kind_final.append([B, d, L, rs])
LG = join(logs, 'FireLogs')

# ========================================================================================== ash
bm = bmesh.new()
NR, NS, RA = 26, 96, 0.412
ctr = bm.verts.new((0, 0, 0))
arings = []
for i in range(1, NR + 1):
    rr = RA * (i / NR) ** 0.9
    arings.append([bm.verts.new((rr * math.cos(j / NS * math.tau), rr * math.sin(j / NS * math.tau), 0)) for j in range(NS)])
for j in range(NS):
    bm.faces.new((ctr, arings[0][j], arings[0][(j + 1) % NS]))
for i in range(NR - 1):
    for j in range(NS):
        bm.faces.new((arings[i][j], arings[i + 1][j], arings[i + 1][(j + 1) % NS], arings[i][(j + 1) % NS]))
for v in bm.verts:
    rr = v.co.xy.length
    mound = 0.045 * max(0.0, 1 - (rr / 0.40) ** 2) ** 1.4
    v.co.z = mound + 0.008 * noise.noise(Vector((v.co.x * 22, v.co.y * 22, 3.3)))         + 0.004 * noise.noise(Vector((v.co.x * 60, v.co.y * 60, 7.1))) - 0.004 - 0.006 * max(0.0, rr - 0.36) / 0.05
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def ash_extra(nb, col, vec):
    oc = obj_coord(nb)
    x, y, z = sep_xyz(nb, oc)
    r = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', x, x), nb.math('MULTIPLY', y, y)))
    ash = nb.mix(ramp_s(nb, nb.noise(oc, 26.0, 5.0, 0.62), 0.32, 0.72), (0.085, 0.082, 0.078), (0.24, 0.235, 0.228))
    flecks = ramp_s(nb, nb.noise(oc, 95.0, 2.0, 0.5), 0.60, 0.66)
    ash = nb.mix(nb.math('MULTIPLY', flecks, 0.7), ash, (0.46, 0.45, 0.43))
    ch = ramp_s(nb, nb.noise(oc, 11.0, 5.0, 0.62), 0.50, 0.58)
    ch = nb.math('MAXIMUM', ch, nb.math('MULTIPLY', ramp_s(nb, r, 0.24, 0.06), 0.85))
    base = nb.mix(ch, ash, (0.018, 0.016, 0.015))
    edge = ramp_s(nb, r, 0.30, 0.405)
    soil = nb.mix(ramp_s(nb, nb.noise(oc, 15.0, 4.0, 0.6), 0.4, 0.7), (0.07, 0.05, 0.035), (0.12, 0.09, 0.06))
    return nb.mix(nb.math('MULTIPLY', edge, 0.85), base, soil)


def ash_glow(nb):
    oc = obj_coord(nb)
    x, y, z = sep_xyz(nb, oc)
    r = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', x, x), nb.math('MULTIPLY', y, y)))
    core = ramp_s(nb, r, 0.25, 0.05)
    coals = ramp_s(nb, nb.noise(oc, 16.0, 6.0, 0.7), 0.5, 0.68)
    pin = ramp_s(nb, nb.noise(oc, 70.0, 3.0, 0.6), 0.62, 0.7)
    g = nb.math('MULTIPLY', core, nb.math('MAXIMUM', nb.math('MULTIPLY', coals, 0.85), nb.math('MULTIPLY', pin, 0.6)))
    return g


m_ash = layered_mat('ash', 'Ground106', scale=4.0, tint=(0.5, 0.5, 0.5), sat=0.2, val=0.75, rough_add=0.35, nstr=0.8,
                    extra_color=ash_extra, grime=dict(color=(0.02, 0.02, 0.02), dist=0.02, amount=0.6))
set_glow(m_ash, ash_glow)
ashbed = obj_from_bm('ashbed', bm, m_ash)
smooth(ashbed, 60)
uv_tex(ashbed, 0.5)
parts = [ashbed]
# charcoal lumps, clustered in the middle, some glowing
m_coal = layered_mat('coal', 'Asphalt033', scale=12.0, tint=(0.16, 0.155, 0.15), sat=0.3, val=0.6, rough_add=-0.15, nstr=1.5,
                     wear=dict(color=(0.35, 0.34, 0.33), radius=0.003, amount=0.7, rough=0.8, gain=14),
                     grime=dict(color=(0.01, 0.01, 0.01), dist=0.01, amount=0.7))
def coal_glow(nb):
    oc = obj_coord(nb)
    x, y, z = sep_xyz(nb, oc)
    r = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', x, x), nb.math('MULTIPLY', y, y)))
    pat = ramp_s(nb, nb.noise(oc, 38.0, 5.0, 0.68), 0.46, 0.66)
    return nb.math('MULTIPLY', ramp_s(nb, r, 0.27, 0.06), nb.math('MULTIPLY', pat, 0.95))
set_glow(m_coal, coal_glow)
for i in range(70):
    rr = 0.32 * math.sqrt(rnd.random()) ** 1.2
    a = rnd.uniform(0, math.tau)
    sz = rnd.uniform(0.008, 0.022)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    off = Vector((i * 1.3, i * 0.7, i * 2.1))
    for v in bm.verts:
        p = v.co.copy()
        v.co = p * (1 + 0.28 * noise.noise(p * 1.7 + off))
        v.co = Vector((v.co.x * sz * rnd.uniform(1.0, 1.7), v.co.y * sz * rnd.uniform(0.7, 1.1), v.co.z * sz * rnd.uniform(0.5, 0.8)))
    c = obj_from_bm(f'coal{i}', bm, m_coal)
    zbed = 0.045 * max(0.0, 1 - (rr / 0.40) ** 2) ** 1.4
    c.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(0, math.tau))
    c.location = (rr * math.cos(a), rr * math.sin(a), zbed - 0.004)
    select_only(c); bpy.ops.object.transform_apply(location=True, rotation=True)
    finish(c, bevel=0.0012, segments=1, angle=30)
    uv_tex(c, 0.1)
    parts.append(c)
AS = join(parts, 'FireAsh')

# ============================================================================= bake + export
out = []
for obj, key, size, aod in ((ST, 'fire_stones', 2048, 0.06), (LG, 'fire_logs', 2048, 0.06), (AS, 'fire_ash', 1024, 0.04)):
    uv_bake(obj, margin=0.004, angle=58)
    imgs, em = bake_all(obj, key, size=size, samples=40, ao_dist=aod)
    if key != 'fire_stones':
        gp = bake_glow(obj, key, size=size, samples=8)
        add_emissive(em, gp, factor=EMBER, strength=1.0)
    finalize_export_material(em)
    swap_to(obj, em)
    out.append(obj)
root = bpy.data.objects.new('CampFire', None)
link(root)
for o in out:
    o.parent = root
export_glb([root], 'camp_fire.glb')

g = ground_plane(4.0)
preview(out, 'fire', height=0.55)
lit_shot('fire_close', (0.75, -0.95, 0.62), (0.0, 0.0, 0.14), lens=45, size=768)
lit_shot('fire_night', (0.75, -0.95, 0.62), (0.0, 0.0, 0.14), lens=45, size=768, night=True,
         extra_lights=[((0.0, 0.0, 0.35), 6.0, (1.0, 0.55, 0.22), 0.12)])
lit_shot('fire_top', (0.35, -0.42, 0.95), (0.0, 0.0, 0.40), lens=50, size=768)
