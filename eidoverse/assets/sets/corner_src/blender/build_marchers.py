"""Vibecamp march - four silhouette marchers, each holding a protest sign's stick in both raised hands.

Built as tagged source pieces (elliptical lofts through smooth joint curves: torso, legs, arms,
head, and clothes as thick shells), fused into ONE organic mass per person with a voxel remesh,
decimated to budget, then the animation weights are transferred back from the tagged pieces:

    _LEG   +1 left leg (Blender +X), -1 right leg; +/-0.35 max on skirt / coat hems (they follow
           the legs a little); 0 elsewhere.        (three.js GLTFLoader names it `_leg`)
    _SHIN  0 above the knee -> 1 below (a ~8 cm blend around the knee axis)
    _ARM   0 at the shoulder -> 1 at the fists (arc length along shoulder-elbow-fist)

Variants (meshes 'Marcher_A'..'Marcher_D', origin between the feet on the floor, facing -Y):
    A hoodie (hood up) + backpack + jeans     B long hair + long skirt + cardigan
    C cap + puffy jacket + trousers           D beanie + long coat
All four hold the stick at ONE grip: the stick axis is x = 0, y = -0.27 m; the lower (right) fist
wraps it at z = 1.40 m (the sign's origin), the upper (left) fist at z = 1.52 m.
One shared baked atlas (dark cloth, 2K) -> glb/camp_marchers.glb.
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix, kdtree
from clib import *

reset()
GRIP_Y = -0.27
FIST_R_Z, FIST_L_Z = 1.40, 1.52          # right (lower) fist = the sign's grip point
VOXEL = 0.0065
TARGET_TRIS = 12500


def sstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ geometry builders
def catmull(pts, spacing=0.012):
    P = [Vector(p) for p in pts]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(0, i - 1)], P[i], P[i + 1], P[min(len(P) - 1, i + 2)]
        n = max(2, int((p2 - p1).length / spacing))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((q, i + t))
    out.append((P[-1], len(P) - 1.0))
    return out


def loft(pts, radii, ref=(1, 0, 0), seg=28, caps=True, spacing=0.012, wobble=None):
    """Closed elliptical tube through pts; radii = [(rx, ry)] per control point, rx along the
    ref-projected axis. Hemispherical end caps. Returns a bmesh."""
    samples = catmull(pts, spacing)
    bm = bmesh.new()
    rings = []
    N_prev = None
    T_prev = None
    ref = Vector(ref)
    for idx, (p, u) in enumerate(samples):
        a = samples[max(0, idx - 1)][0]; b = samples[min(len(samples) - 1, idx + 1)][0]
        T = (b - a).normalized()
        if N_prev is None:
            r = ref if abs(ref.dot(T)) < 0.95 else Vector((0, 1, 0))
            N = (r - r.dot(T) * T).normalized()
        else:                                   # parallel transport: no frame flips
            q = T_prev.rotation_difference(T)
            N = (q @ N_prev)
            N = (N - N.dot(T) * T).normalized()
        B = T.cross(N)
        i0 = min(int(u), len(radii) - 2); f = u - i0
        rx = radii[i0][0] + (radii[i0 + 1][0] - radii[i0][0]) * f
        ry = radii[i0][1] + (radii[i0 + 1][1] - radii[i0][1]) * f
        ring = []
        for k in range(seg):
            th = k / seg * math.tau
            w = 1.0 + (wobble(th, u) if wobble else 0.0)
            ring.append(bm.verts.new(p + N * (rx * w * math.cos(th)) + B * (ry * w * math.sin(th))))
        rings.append((ring, p, T, N, B, rx, ry))
        N_prev, T_prev = N, T
    faces = []
    for i in range(len(rings) - 1):
        r0, r1 = rings[i][0], rings[i + 1][0]
        for k in range(seg):
            faces.append(bm.faces.new((r0[k], r0[(k + 1) % seg], r1[(k + 1) % seg], r1[k])))
    if caps:
        for end, sgn in ((rings[0], -1), (rings[-1], 1)):
            ring, p, T, N, B, rx, ry = end
            prev = ring
            steps = 5
            rmin = min(rx, ry)
            for s in range(1, steps + 1):
                ang = s / steps * math.pi / 2
                cr, sr = math.cos(ang), math.sin(ang)
                if s == steps:
                    tip = bm.verts.new(p + T * (sgn * rmin * sr))
                    for k in range(seg):
                        f = bm.faces.new((prev[k], prev[(k + 1) % seg], tip)) if sgn > 0 else bm.faces.new((prev[(k + 1) % seg], prev[k], tip))
                    break
                cur = []
                for k in range(seg):
                    th = k / seg * math.tau
                    cur.append(bm.verts.new(p + T * (sgn * rmin * sr) + N * (rx * cr * math.cos(th)) + B * (ry * cr * math.sin(th))))
                for k in range(seg):
                    if sgn > 0:
                        bm.faces.new((prev[k], prev[(k + 1) % seg], cur[(k + 1) % seg], cur[k]))
                    else:
                        bm.faces.new((prev[(k + 1) % seg], prev[k], cur[k], cur[(k + 1) % seg]))
                prev = cur
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def ellipsoid(center, radii, seg=32, rings=20):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in bm.verts:
        v.co = Vector((center[0] + v.co.x * radii[0], center[1] + v.co.y * radii[1], center[2] + v.co.z * radii[2]))
    return bm


def shell(bm, thickness, keep_fn=None):
    """Delete verts failing keep_fn(co) (an open shell), then give it thickness (closed volume)."""
    if keep_fn is not None:
        bad = [v for v in bm.verts if not keep_fn(v.co)]
        bmesh.ops.delete(bm, geom=bad, context='VERTS')
    return bm, thickness


PIECES = []                                # (name, bm, kind, side, color, solidify)


def piece(bm, kind, color, side=0, solid=0.0, fuse=True):
    PIECES.append(dict(bm=bm, kind=kind, color=color, side=side, solid=solid, fuse=fuse))


def arm_ik(S, F, ua, fa, pole):
    S, F = Vector(S), Vector(F)
    d = (F - S).length
    d_eff = min(d, ua + fa - 1e-4)
    u = (F - S).normalized()
    x = (ua * ua - fa * fa + d_eff * d_eff) / (2 * d_eff)
    h = math.sqrt(max(ua * ua - x * x, 0.0))
    p = Vector(pole)
    w = (p - p.dot(u) * u).normalized()
    return S + u * x + w * h


# ------------------------------------------------------------------ one person
def person(V):
    """V: dict of proportions + wardrobe. Returns (fused object, info)."""
    PIECES.clear()
    H = V['H']; s = H / 1.75; bw = V.get('bw', 1.0); g = V.get('girth', 1.0); fem = V.get('fem', False)
    z_hc = H - 0.115 * s
    z_nt, z_nb = H - 0.22 * s, H - 0.295 * s
    z_sh = H - 0.325 * s
    z_chest, z_waist, z_pel = H - 0.45 * s, H - 0.68 * s, H - 0.79 * s
    z_crotch = H - 0.915 * s
    z_hip = 0.518 * H
    z_knee = 0.284 * H
    z_ank = 0.045 * H
    x_sh, x_hip = 0.185 * s * bw, 0.088 * s * (1.06 if fem else 1.0)
    skin = V['skin']

    # ---- torso
    if fem:
        tr = [(0.125, 0.10), (0.175, 0.12), (0.128, 0.095), (0.150, 0.105), (0.160, 0.122), (0.140, 0.095), (0.052, 0.052), (0.046, 0.046)]
    else:
        tr = [(0.125, 0.095), (0.165, 0.115), (0.140, 0.100), (0.158, 0.110), (0.170, 0.118), (0.155, 0.098), (0.058, 0.056), (0.050, 0.050)]
    tz = [z_crotch + 0.01, z_pel, z_waist, (z_waist + z_chest) / 2, z_chest, z_sh - 0.03, z_nb, z_nt]
    ty = [0.005, 0.012, 0.0, -0.004, -0.008, 0.002, 0.022, 0.012]
    torso_pts = [(0, ty[i], tz[i]) for i in range(len(tz))]
    torso_r = [(r[0] * s * g * (bw if 3 <= i <= 5 else 1.0), r[1] * s * g) for i, r in enumerate(tr)]
    piece(loft(torso_pts, torso_r), 'torso', V['top'])

    # ---- head (egg: narrower jaw), no features
    hb = ellipsoid((0, 0.012, z_hc), (0.077 * s, 0.094 * s, 0.114 * s))
    for v in hb.verts:
        t = max(0.0, (z_hc - v.co.z) / (0.114 * s))
        v.co.x *= 1.0 - 0.22 * t * t
        v.co.y = 0.012 + (v.co.y - 0.012) * (1.0 - 0.10 * t * t)
    piece(hb, 'head', skin)

    # ---- legs + feet (per side)
    for side in (1, -1):
        x = side * x_hip
        lp = [(x, 0.0, z_hip), (x, -0.006, (z_hip + z_knee) / 2 + 0.03), (x * 0.97, -0.012, z_knee),
              (x * 0.95, 0.0, (z_knee + z_ank) / 2 + 0.03), (x * 0.92, 0.012, z_ank + 0.03)]
        lr = [(0.090, 0.092), (0.074, 0.078), (0.052, 0.056), (0.054, 0.060), (0.034, 0.038)]
        lr = [(a * s * g, b * s * g) for a, b in lr]
        if V.get('legwear'):
            extra = V['legwear']['pad']
            lr = [(a + extra, b + extra) for a, b in lr]
            lr[-1] = (lr[-1][0] + V['legwear'].get('hem', 0.004), lr[-1][1] + V['legwear'].get('hem', 0.004))
            col = V['legwear']['color']
        else:
            col = V.get('legs', skin)
        piece(loft(lp, lr, ref=(1, 0, 0)), 'leg', col, side=side)
        fx = x * 0.92
        sh = V.get('shoe', 0.010)
        fr = [(0.046 + sh, 0.040 + sh), (0.044 + sh, 0.046 + sh), (0.030 + sh * 0.6, 0.044 + sh)]
        fp = [(fx, 0.045 * s, fr[0][0] + 0.004), (fx + side * 0.004, -0.04 * s, fr[1][0] + 0.004), (fx + side * 0.012, -0.155 * s, fr[2][0] + 0.004)]
        piece(loft(fp, fr, ref=(0, 0, 1)), 'leg', V['shoes'], side=side)
        if V.get('boot'):
            piece(loft([(fx, 0.02, 0.058), (fx, 0.015, V['boot'])], [(0.050, 0.052), (0.046, 0.048)]), 'leg', V['shoes'], side=side)

    # ---- arms to the grip (IK), fists around the stick
    info = dict(H=H, z_hip=z_hip, z_knee=z_knee, knee_y=-0.012, grip=(0.0, GRIP_Y, FIST_R_Z))
    for side, fz in ((-1, FIST_R_Z), (1, FIST_L_Z)):
        S = Vector((side * x_sh, 0.0, z_sh))
        F = Vector((side * 0.012, GRIP_Y + 0.004, fz))
        E = arm_ik(S, F, 0.300 * s, 0.335 * s, (side * 1.0, 0.25, -0.85))
        W = F + (E - F).normalized() * 0.075
        ap = [S, S + (E - S) * 0.5, E, E + (W - E) * 0.55, W, F]
        ar = [(0.056, 0.056), (0.044, 0.044), (0.036, 0.036), (0.035, 0.033), (0.027, 0.025), (0.028, 0.026)]
        ar = [(a * s * g, b * s * g) for a, b in ar]
        piece(loft(ap, ar, ref=(0, 0, 1)), 'arm', skin, side=side)
        # the fist: knuckles around the stick (a squarish ellipsoid)
        piece(ellipsoid((F.x + side * 0.004, F.y + 0.004, F.z), (0.042 * s, 0.046 * s, 0.047 * s), 20, 14), 'arm', skin, side=side)
        info[f'arm{side}'] = (S, E, F)
        if V.get('sleeve'):
            sv = V['sleeve']
            sp = [S + Vector((side * 0.005, 0, 0.01)), S + (E - S) * 0.5, E, E + (W - E) * 0.6, W + (F - W) * 0.15]
            pad = sv['pad']
            sr = [(0.062 + pad, 0.062 + pad), (0.049 + pad, 0.049 + pad), (0.041 + pad, 0.041 + pad),
                  (0.040 + pad, 0.038 + pad), (0.037 + sv.get('cuff', 0.004), 0.035 + sv.get('cuff', 0.004))]
            wob = sv.get('baffle')
            wf = (lambda th, u, b=wob: 0.06 * math.sin(u * math.pi * b) ** 2) if wob else None
            piece(loft(sp, sr, ref=(0, 0, 1), wobble=wf), 'arm', sv['color'], side=side)

    # ---- the wardrobe
    top = V.get('topwear')
    if top:
        pad = top['pad']
        hem = top['hem']
        zs = [hem, z_pel, z_waist, (z_waist + z_chest) / 2, z_chest, z_sh - 0.02, z_nb + 0.01]
        rs = [(0.160, 0.122), (0.170, 0.122), (0.150, 0.110), (0.162, 0.117), (0.174, 0.123), (0.160, 0.104), (0.075, 0.072)]
        rs = [(a * s * g * (bw if 3 <= i <= 5 else 1.0) + pad, b * s * g + pad) for i, (a, b) in enumerate(rs)]
        rs[0] = (rs[0][0] + top.get('flare', 0.0), rs[0][1] + top.get('flare', 0.0) * 0.7)
        ys = [0.01, 0.012, 0.0, -0.004, -0.008, 0.004, 0.018]
        bf = top.get('baffle')
        wf = (lambda th, u, b=bf: 0.07 * math.sin(u * math.pi * b) ** 2) if bf else None
        piece(loft([(0, ys[i], zs[i]) for i in range(len(zs))], rs, wobble=wf), 'torso', top['color'])
        if top.get('collar'):
            c = top['collar']
            piece(loft([(0, 0.02, z_nb - 0.02), (0, 0.018, z_nb + c)], [(0.080, 0.078), (0.074, 0.070)], caps=True), 'torso', top['color'])
        if top.get('pocket'):
            piece(ellipsoid((0, -(0.100 * s * g + pad) + 0.004, z_waist - 0.03), (0.125, 0.014, 0.068)), 'torso', top['color'])
    skirt = V.get('skirt')
    if skirt:
        zt, zh = skirt['top'], skirt['hem']
        zz = [zt, zt - 0.10, (zt + zh) / 2, zh]
        rr = [(0.15, 0.115), (0.19, 0.15), (skirt['rmid'], skirt['rmid'] * 0.8), (skirt['rhem'], skirt['rhem'] * 0.8)]
        folds = skirt.get('folds', 7)
        wf = lambda th, u: 0.045 * max(0.0, u - 1.0) * math.sin(th * folds + u)
        bm = loft([(0, 0.01, z) for z in zz], rr, wobble=wf, caps=False)
        piece(bm, 'skirt', skirt['color'], solid=0.014)
    hood = V.get('hood')
    if hood:
        bm = ellipsoid((0, 0.028, z_hc + 0.012), (0.104 * s, 0.128 * s, 0.138 * s))
        cz = z_hc
        keep = lambda co: not (co.y < -0.035 and co.z < cz + 0.075 and abs(co.x) < 0.09)
        bm, t = shell(bm, 0.02, keep)
        piece(bm, 'head', hood, solid=0.02)
        piece(loft([(0, 0.07, z_hc - 0.06), (0, 0.075, z_nb)], [(0.10, 0.06), (0.09, 0.05)]), 'head', hood)   # the hood's fallen fold at the nape
    hair = V.get('hair')
    if hair:
        bm = ellipsoid((0, 0.018, z_hc + 0.012), (0.088 * s, 0.106 * s, 0.124 * s))
        cz = z_hc
        keep = lambda co: not (co.y < -0.03 and co.z < cz + 0.06)
        bm, t = shell(bm, 0.016, keep)
        piece(bm, 'head', hair, solid=0.016)
        cp = [(0, 0.075, z_hc), (0, 0.105, z_nb), (0, 0.125, z_sh - 0.10), (0, 0.13, z_sh - 0.22), (0, 0.124, z_sh - 0.30)]
        cr = [(0.085, 0.050), (0.110, 0.045), (0.128, 0.038), (0.136, 0.032), (0.118, 0.022)]
        piece(loft(cp, cr), 'head', hair)
        for sx in (-1, 1):
            piece(loft([(sx * 0.07, -0.005, z_hc - 0.02), (sx * 0.098, -0.020, z_nb - 0.01), (sx * 0.112, -0.036, z_sh - 0.12)],
                       [(0.030, 0.026), (0.030, 0.024), (0.020, 0.016)], ref=(0, 1, 0)), 'head', hair)
    cap = V.get('cap')
    if cap:
        bm = ellipsoid((0, 0.012, z_hc + 0.045), (0.091 * s, 0.103 * s, 0.078 * s))
        cz = z_hc + 0.035
        bm, t = shell(bm, 0.012, lambda co: co.z > cz)
        piece(bm, 'head', cap, solid=0.012)
        piece(ellipsoid((0, 0.012, z_hc + 0.045 + 0.078 * s), (0.012, 0.012, 0.008), 12, 8), 'head', cap)
        # the brim (thin: not voxel-remeshed)
        bm = bmesh.new()
        nu, nv = 12, 5
        grid = []
        for i in range(nv + 1):
            row = []
            for j in range(nu + 1):
                a = math.radians(-78 + 156 * j / nu)
                rad = 0.086 * s + 0.078 * i / nv
                x = math.sin(a) * rad * 1.02
                y = 0.012 - math.cos(a) * rad * 1.08
                z = z_hc + 0.036 - 0.018 * (abs(math.sin(a)) ** 2) * (i / nv) - 0.012 * (i / nv)
                row.append(bm.verts.new((x, y, z)))
            grid.append(row)
        for i in range(nv):
            for j in range(nu):
                bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
        piece(bm, 'head', cap, solid=0.006, fuse=False)
    beanie = V.get('beanie')
    if beanie:
        bm = ellipsoid((0, 0.016, z_hc + 0.03), (0.094 * s, 0.107 * s, 0.105 * s))
        cz = z_hc + 0.005
        bm, t = shell(bm, 0.014, lambda co: co.z > cz)
        piece(bm, 'head', beanie, solid=0.014)
        piece(loft([(0, 0.016, z_hc + 0.004), (0, 0.016, z_hc + 0.048)], [(0.100 * s, 0.113 * s), (0.099 * s, 0.112 * s)]), 'head', beanie)
        piece(ellipsoid((0, 0.07, z_hc + 0.10), (0.06, 0.05, 0.04)), 'head', beanie)              # the slouch
    pack = V.get('backpack')
    if pack:
        bm = bmesh.new()
        bm_box(bm, 0.30 * s, 0.13, 0.40 * s, 0, 0.125 * s + 0.065 + 0.02, z_chest - 0.08)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.045, segments=3, affect='EDGES', profile=0.5, clamp_overlap=True)
        piece(bm, 'torso', pack)
        piece(ellipsoid((0, 0.125 * s + 0.15, z_chest - 0.16), (0.11, 0.05, 0.09)), 'torso', pack)       # front pocket
        for sx in (-1, 1):
            piece(loft([(sx * 0.085, 0.16, z_chest + 0.10), (sx * 0.105, 0.03, z_sh + 0.035), (sx * 0.110, -0.105, z_sh - 0.07),
                        (sx * 0.125, -0.10, z_chest - 0.10), (sx * 0.145, 0.10, z_chest - 0.24)],
                       [(0.014, 0.014)] * 5, ref=(1, 0, 0), seg=10), 'torso', pack)
    return info


# ------------------------------------------------------------------ fuse + weights
def weights_for(kind, side, co, info):
    leg = shin = arm = 0.0
    if kind == 'leg':
        leg = side * sstep(info['z_hip'] + 0.03, info['z_hip'] - 0.09, co.z)
        shin = sstep(info['z_knee'] + 0.04, info['z_knee'] - 0.04, co.z)
    elif kind == 'skirt':
        leg = 0.35 * max(-1.0, min(1.0, co.x / 0.12)) * sstep(info['z_hip'] + 0.06, info['z_hip'] - 0.30, co.z)
    elif kind == 'arm':
        S, E, F = info[f'arm{side}']
        L1, L2 = (E - S).length, (F - E).length
        best, bt = 1e9, 0.0
        for a, b, t0, L in ((S, E, 0.0, L1), (E, F, L1, L2)):
            ab = b - a
            t = max(0.0, min(1.0, (co - a).dot(ab) / ab.length_squared))
            d = (a + ab * t - co).length
            if d < best:
                best, bt = d, (t0 + t * L) / (L1 + L2)
        arm = max(0.0, min(1.0, bt))
    return leg, shin, arm


def build_person(V, key, info):
    objs_fuse, objs_keep = [], []
    src_co, src_w, src_c = [], [], []
    for i, P in enumerate(PIECES):
        o = obj_from_bm(f'{key}_p{i}', P['bm'])
        if P['solid']:
            m = o.modifiers.new('sol', 'SOLIDIFY'); m.thickness = P['solid']; m.offset = -1.0; m.use_rim = True
            apply_mods(o)
        # densify for the weight transfer
        me = o.data
        for v in me.vertices:
            co = o.matrix_world @ v.co
            src_co.append(co.copy())
            src_w.append(weights_for(P['kind'], P['side'], co, info))
            src_c.append(P['color'])
        (objs_fuse if P['fuse'] else objs_keep).append(o)
    body = join(objs_fuse, f'{key}_body')
    rm = body.modifiers.new('rm', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = VOXEL; rm.adaptivity = 0.0
    apply_mods(body)
    ntri = sum(len(p.vertices) - 2 for p in body.data.polygons)
    keep_tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs_keep)
    dec = body.modifiers.new('dec', 'DECIMATE'); dec.ratio = max(0.02, (TARGET_TRIS - keep_tris) / max(1, ntri))
    apply_mods(body)
    sm = body.modifiers.new('sm', 'CORRECTIVE_SMOOTH'); sm.factor = 0.5; sm.iterations = 4; sm.use_only_smooth = True
    apply_mods(body)
    for o in objs_keep:
        smooth(o, 40)
    person_obj = join([body] + objs_keep, f'Marcher_{key}') if objs_keep else body
    person_obj.name = f'Marcher_{key}'
    smooth(person_obj, 180)
    # transfer: IDW over the 6 nearest source vertices
    kd = kdtree.KDTree(len(src_co))
    for i, c in enumerate(src_co):
        kd.insert(c, i)
    kd.balance()
    me = person_obj.data
    for nm in ('_LEG', '_SHIN', '_ARM'):
        if nm in me.attributes:
            me.attributes.remove(me.attributes[nm])
        me.attributes.new(nm, 'FLOAT', 'POINT')
    if 'Col' in me.attributes:
        me.attributes.remove(me.attributes['Col'])
    col_attr = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    A_leg, A_shin, A_arm = me.attributes['_LEG'].data, me.attributes['_SHIN'].data, me.attributes['_ARM'].data
    for v in me.vertices:
        co = person_obj.matrix_world @ v.co
        hits = kd.find_n(co, 6)
        ws = 0.0; acc = [0.0, 0.0, 0.0]; cacc = [0.0, 0.0, 0.0]
        dmin = hits[0][2]
        for (c, idx, d) in hits:
            if d > dmin + 0.012:                   # only the surface this vertex actually came from
                continue
            w = 1.0 / (d + 0.002)
            ws += w
            for k in range(3):
                acc[k] += src_w[idx][k] * w
                cacc[k] += src_c[idx][k] * w
        A_leg[v.index].value = acc[0] / ws
        A_shin[v.index].value = acc[1] / ws
        A_arm[v.index].value = acc[2] / ws
        col_attr.data[v.index].color = (cacc[0] / ws, cacc[1] / ws, cacc[2] / ws, 1.0)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    info['tris'] = tris
    print(f'[marchers] {key}: voxel tris {ntri} -> {tris}', flush=True)
    return person_obj


# ------------------------------------------------------------------ the four people (very dark, desaturated)
SKIN = [(0.050, 0.034, 0.028), (0.042, 0.030, 0.026), (0.034, 0.024, 0.020), (0.046, 0.032, 0.027)]
VARIANTS = {
    'A': dict(H=1.79, bw=1.07, girth=1.03, skin=SKIN[0], top=(0.030, 0.034, 0.042),
              topwear=dict(pad=0.022, hem=0.83, color=(0.030, 0.034, 0.042), pocket=True, flare=0.01),
              sleeve=dict(pad=0.012, cuff=0.010, color=(0.030, 0.034, 0.042)),
              hood=(0.030, 0.034, 0.042), backpack=(0.036, 0.031, 0.028),
              legwear=dict(pad=0.013, hem=0.006, color=(0.022, 0.028, 0.044)), shoes=(0.020, 0.020, 0.021), shoe=0.014),
    'B': dict(H=1.66, bw=0.93, girth=0.96, fem=True, skin=SKIN[1], top=(0.046, 0.034, 0.031),
              topwear=dict(pad=0.018, hem=0.80 * 1.66 / 1.75, color=(0.046, 0.034, 0.031), flare=0.02),
              sleeve=dict(pad=0.011, cuff=0.006, color=(0.046, 0.034, 0.031)),
              hair=(0.021, 0.016, 0.013), skirt=dict(top=1.00, hem=0.30, rmid=0.245, rhem=0.30, color=(0.031, 0.025, 0.037), folds=7),
              legs=(0.018, 0.018, 0.020), shoes=(0.020, 0.018, 0.017), shoe=0.008, boot=0.20),
    'C': dict(H=1.74, bw=1.02, girth=1.0, skin=SKIN[2], top=(0.036, 0.042, 0.034),
              topwear=dict(pad=0.040, hem=0.86, color=(0.036, 0.042, 0.034), baffle=7.0, collar=0.075),
              sleeve=dict(pad=0.026, cuff=0.004, color=(0.036, 0.042, 0.034), baffle=6.0),
              cap=(0.046, 0.021, 0.019),
              legwear=dict(pad=0.017, hem=0.008, color=(0.029, 0.029, 0.030)), shoes=(0.022, 0.021, 0.022), shoe=0.015),
    'D': dict(H=1.70, bw=0.98, girth=0.99, skin=SKIN[3], top=(0.041, 0.035, 0.030),
              topwear=dict(pad=0.028, hem=0.95, color=(0.041, 0.035, 0.030), collar=0.10),
              sleeve=dict(pad=0.018, cuff=0.008, color=(0.041, 0.035, 0.030)),
              skirt=dict(top=1.02, hem=0.44, rmid=0.225, rhem=0.265, color=(0.041, 0.035, 0.030), folds=5),
              beanie=(0.018, 0.028, 0.034),
              legwear=dict(pad=0.014, hem=0.005, color=(0.022, 0.022, 0.026)), shoes=(0.019, 0.018, 0.018), shoe=0.012, boot=0.17),
}

people = []
infos = {}
for vi, (key, V) in enumerate(VARIANTS.items()):
    info = person(V)
    o = build_person(V, key, info)
    me = o.data
    va = me.attributes.new('variant', 'INT', 'FACE')
    for p in me.polygons:
        va.data[p.index].value = vi
    people.append(o)
    infos[key] = info

# ------------------------------------------------------------------ one shared baked cloth atlas
def cloth_extra(nb, col, vec):
    # the garment colour (vertex attribute) x the weave, normalised to mean 1 and softened to +-35 %
    attr = nb.n('ShaderNodeAttribute'); attr.attribute_name = 'Col'
    ma = nb.n('ShaderNodeVectorMath', operation='MULTIPLY_ADD')
    nb.l(col, ma.inputs[0]); ma.inputs[1].default_value = (3.04, 3.04, 3.04); ma.inputs[2].default_value = (0.65, 0.65, 0.65)
    mu = nb.n('ShaderNodeVectorMath', operation='MULTIPLY')
    nb.l(ma.outputs[0], mu.inputs[0]); nb.l(attr.outputs['Color'], mu.inputs[1])
    return mu.outputs[0]


m_cloth = layered_mat('dark_cloth', 'Fabric030', scale=7.0, tint=None, sat=0.0, val=1.0, rough_mul=1.0, rough_add=0.08,
                      nstr=0.7, extra_color=cloth_extra,
                      wear=dict(color=(0.070, 0.066, 0.064), radius=0.004, amount=0.16, rough=0.95, noise=18, gain=6),
                      grime=dict(color=(0.006, 0.006, 0.006), dist=0.06, amount=0.7, gain=1.5, rough=0.05))
allp = []
for o in people:
    c = o.copy(); c.data = o.data.copy(); link(c)
    c.data.materials.clear(); c.data.materials.append(m_cloth)
    uv_tex(c, 1.0)
    allp.append(c)
merged = join(allp, 'Marchers_all')
uv_bake(merged, margin=0.002, angle=76)
bake_and_swap(merged, 'marchers', size=2048, samples=40, ao_dist=0.10)
mat = merged.data.materials[0]
mat.use_backface_culling = True
finals = []
for vi, key in enumerate(VARIANTS):
    o = merged.copy(); o.data = merged.data.copy(); link(o)
    bm = bmesh.new(); bm.from_mesh(o.data)
    va = bm.faces.layers.int.get('variant')
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[va] != vi], context='FACES')
    bm.to_mesh(o.data); bm.free()
    for nm in ('variant', 'Col'):
        if nm in o.data.attributes:
            o.data.attributes.remove(o.data.attributes[nm])
    finals.append(o)
for o in people + [merged]:
    bpy.data.objects.remove(o)
for o in list(bpy.data.objects):
    if o not in finals:
        bpy.data.objects.remove(o)
for m in list(bpy.data.meshes):
    if m.users == 0:
        bpy.data.meshes.remove(m)
for key, o in zip(VARIANTS, finals):                 # names are free now: no '.001'
    o.name = f'Marcher_{key}'; o.data.name = f'Marcher_{key}'
for key, o in zip(VARIANTS, finals):                 # soles exactly on the floor (remesh drifts a few mm)
    zmin = min(v.co.z for v in o.data.vertices)
    o.data.transform(Matrix.Translation((0, 0, -zmin)))
    infos[key]['z_hip'] -= zmin; infos[key]['z_knee'] -= zmin; infos[key]['sole_shift'] = -zmin
    infos[key]['grip'] = (0.0, GRIP_Y, FIST_R_Z - zmin)
    print(f'[marchers] {key}: soles shifted by {-zmin * 1000:.1f} mm', flush=True)
export_glb(finals, 'camp_marchers.glb')
for key, o in zip(VARIANTS, finals):
    i = infos[key]
    tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    print(f'[marchers] {o.name}: H {i["H"]:.2f} hip_z {i["z_hip"]:.3f} knee_z {i["z_knee"]:.3f} knee_y {i["knee_y"]:.3f} grip_z {i["grip"][2]:.3f} tris {tris}', flush=True)

# ------------------------------------------------------------------ previews: line-up + night rim-light read + grip check
for i, o in enumerate(finals):
    o.location.x = (i - 1.5) * 0.9
preview(finals, 'marchers', height=0.28, size=640, world=0.35)
# the sign in their hands: the stick must pass through both fists
with bpy.data.libraries.load(os.path.join(BAKED, 'camp_sign_lib.blend'), link=False) as (src, dst):
    dst.objects = ['Sign']
sg = dst.objects[0]
link(sg)
signs = []
for i, o in enumerate(finals):
    c = sg.copy(); c.data = sg.data; link(c)
    c.location = (o.location.x, GRIP_Y, FIST_R_Z)
    signs.append(c)
bpy.data.objects.remove(sg)
preview(finals + signs, 'marchers_signs', height=0.22, size=640, world=0.35)
# night: dark world, warm key from the fire side, cool rim from behind
sc = bpy.context.scene
sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.02
lights = []
for loc, en, col in (((1.5, -3.0, 0.6), 250.0, (1.0, 0.55, 0.25)), ((-1.0, 3.5, 3.0), 900.0, (0.55, 0.65, 1.0))):
    ld = bpy.data.lights.new('n', 'AREA'); ld.energy = en; ld.size = 1.0; ld.color = col
    lo = bpy.data.objects.new('n', ld); link(lo); lo.location = loc
    lo.rotation_euler = (Vector((0, 0, 1.2)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    lights.append(lo)
closeup('marchers_night', (0.6, -5.2, 1.5), (0.0, 0.0, 1.35), lens=40, size=900, samples=64)
closeup('marchers_grip', (0.9, -1.2, 1.75), (finals[1].location.x, GRIP_Y, 1.52), lens=50, size=768, samples=48)

# ------------------------------------------------------------------ weight debug: R = _LEG (0.5 = none), G = _SHIN, B = _ARM
dbg = bpy.data.materials.new('dbg'); dbg.use_nodes = True
nb = NB(dbg); bs = nb.N.get('Principled BSDF')
cmb = nb.n('ShaderNodeCombineColor')
for i, nm in enumerate(('_LEG', '_SHIN', '_ARM')):
    at = nb.n('ShaderNodeAttribute'); at.attribute_name = nm
    v = at.outputs['Fac']
    if nm == '_LEG':
        v = nb.math('ADD', nb.math('MULTIPLY', v, 0.5), 0.5)
    nb.l(v, cmb.inputs[i])
nb.l(cmb.outputs[0], bs.inputs['Base Color'])
nb.l(cmb.outputs[0], bs.inputs['Emission Color']); bs.inputs['Emission Strength'].default_value = 0.6
for o in signs:
    o.hide_render = True
for o in finals:
    o.data.materials[0] = dbg
closeup('marchers_weights_front', (0.0, -5.6, 1.1), (0.0, 0.0, 0.95), lens=35, size=900, samples=16)
closeup('marchers_weights_side', (5.6, -1.2, 1.1), (0.0, 0.0, 0.95), lens=35, size=900, samples=16)
