"""vegetation_daisy_gen: the daisy (Leucanthemum: oxeye / Shasta) for create_flora, ported from
eidoverse/vegetation_daisy_gen.js with the same draw order, so a seed grows the same clump in both editions.

One CLUMP per instance: a basal rosette of spatulate lobed leaves on tube petioles, 1-4 ribbed flowering stems with
clasping toothed stem leaves, and on each stem a head (involucre cup, domed disc, a whorl of 24-30 fitted notched ray
florets; now and then a bud). One geometry on the ONE daisy_ trim sheet (eidoverse/assets/grass/daisy_*), whose
layout is owned by assets/grass/daisy_src/daisy_art.py.

The generator runs in three.js space (Y up) and returns a PlantGeo; plantgeo.to_blender_mesh converts it. Every
vertex carries its close record as ordinary attributes (the WebGPU edition packed them into a storage buffer read by
vertex index; Blender has no vertex-buffer ceiling): close_center_v, close_hinge_v, close_axis_v (vectors, converted
to Blender axes), close_angle, is_head, lod_class (0 plant, 1 near head detail, 2 far impostor card).
"""
import math

import numpy as np

from .jsmath import Rng, js_round
from .plantgeo import PlantGeo, vertex_normals

TAU = math.pi * 2
PX = 1 / 1024


def _tri(s):
    m = math.fmod(s, 2)
    return m if m <= 1 else 2 - m


DAISY_SHEET = {
    'disc': {'cu': 212 * PX, 'cv': 812 * PX, 'r': 207 * PX, 'mm': 9.54},
    'petals': {'x0': 428, 'y0': 605, 'cw': 74, 'ch': 207, 'mmPerPx': 0.09},
    'basal': [{'x0': 5, 'y0': 418, 'x1': 640, 'y1': 596, 'L': 64}, {'x0': 5, 'y0': 236, 'x1': 640, 'y1': 414, 'L': 60}],
    'stemLeaf': [{'x0': 5, 'y0': 124, 'x1': 640, 'y1': 230, 'L': 44}, {'x0': 5, 'y0': 12, 'x1': 640, 'y1': 118, 'L': 40}],
    'invol': {'cu': 832 * PX, 'cv': 400 * PX, 'r': 184 * PX, 'mm': 9.4},
    'stalk': {'u0': 652 * PX, 'u1': 1012 * PX, 'v0': 16 * PX, 'v1': 104 * PX},
    'imp': {'cu': 983 * PX, 'cv': 775 * PX, 'h': 35.5 * PX, 'discR': 14.1 * PX,
            'u0': 947 * PX, 'u1': 1019 * PX, 'v0': 739 * PX, 'v1': 811 * PX},
}

# petal colours (sRGB hex; base -> tip along the ray). 'white' keeps the modelled art; the rest recolor the ray
# region only (the disc stays gold).
DAISY_COLORS = {
    'white': None,
    'orange': {'base': 0xC75A36, 'tip': 0xE68B6B},     # Claude orange, #D97757 mid-ray
    'pink': {'base': 0xD24F87, 'tip': 0xF2A3C4},       # painted daisy
    'yellow': {'base': 0xE8A413, 'tip': 0xF7D24A},
    'cream': {'base': 0xE9DCB0, 'tip': 0xF8F1DC},
}

RD, DOME_H = 9.0, 2.2


def _domeZ(rho):
    r2 = min(1.0, rho) ** 2
    if rho > 1:
        return -3 * (rho - 1)
    return DOME_H * math.pow(1 - r2, 0.85) - 0.25 * math.exp(-((rho / 0.12) ** 2))


def _cupZ(r):
    return -0.8 - 4.6 * math.pow(max(0.0, 1 - (r / 8.7) ** 2), 1.35)


FIT_FALLBACK = {
    'petals': [[[0.5, 0.2], [0.5, 0.3], [0.5, 0.31], [0.5, 0.31], [0.5, 0.3]]] * 16,
    'petalV': [[0.02, 0.98]] * 16,
    'leaves': {
        'basalA': {'u': [0.013, 0.986], 'bands': [[0.5, 0.07], [0.5, 0.13], [0.5, 0.27], [0.5, 0.45], [0.5, 0.49], [0.5, 0.48], [0.5, 0.3]]},
        'basalB': {'u': [0.013, 0.986], 'bands': [[0.5, 0.07], [0.5, 0.13], [0.5, 0.27], [0.5, 0.45], [0.5, 0.49], [0.5, 0.48], [0.5, 0.3]]},
        'stemA': {'u': [0.013, 0.986], 'bands': [[0.5, 0.4], [0.5, 0.38], [0.5, 0.45], [0.5, 0.43], [0.5, 0.36], [0.5, 0.22], [0.5, 0.05]]},
        'stemB': {'u': [0.013, 0.986], 'bands': [[0.5, 0.4], [0.5, 0.38], [0.5, 0.45], [0.5, 0.43], [0.5, 0.36], [0.5, 0.22], [0.5, 0.05]]},
    },
}

DAISY_GEN = {
    'daisy': {
        'height': 0.45,        # flowering stem height (m) of the tallest stem
        'headD': 0.05,         # head diameter (m) before headScale
        'headScale': 1,        # stylized big heads: 2-4
        'stems': [1, 4],
        'petals': [24, 30],
        'rosette': [5, 8],
        'stemLeaves': [3, 5],
        'budChance': 0.12,
        'lod': [10, 18],       # the WebGPU far-LOD distances (not used in Blender, kept for parity of options)
        'facing': None,        # None = wild; {'el': e} = every head faces local +X at elevation e
    },
}


# ── small vector helpers (tuples, doubles, as the JS) ──────────────────────
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def hyp(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def norm(a):
    ln = hyp(a) or 1.0
    return (a[0] / ln, a[1] / ln, a[2] / ln)


def lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def bez3(p0, p1, p2, p3, t):
    s = 1 - t
    return tuple(s * s * s * p0[k] + 3 * s * s * t * p1[k] + 3 * s * t * t * p2[k] + t * t * t * p3[k] for k in range(3))


def rot_axis(v, k, ang):     # Rodrigues
    c, s = math.cos(ang), math.sin(ang)
    kv, kd = cross(k, v), dot(k, v) * (1 - c)
    return (v[0] * c + kv[0] * s + k[0] * kd, v[1] * c + kv[1] * s + k[1] * kd, v[2] * c + kv[2] * s + k[2] * kd)


UP = (0.0, 1.0, 0.0)
ZERO_REC = (0.0,) * 12


def build_daisy_geometry(name, seed, over=None):
    """One daisy clump. Returns {'geo': PlantGeo (three space), 'heads': [...], 'stats': {...}}."""
    cfg = dict(DAISY_GEN.get(name, DAISY_GEN['daisy']))
    cfg.update(over or {})
    fit = cfg.get('fit') or FIT_FALLBACK
    rng = Rng(seed)
    R = rng.next

    def irange(a, b):
        return math.floor(rng.range(a, b + 0.999))

    pos, uv, aH, idx, nrm, rec = [], [], [], [], [], []
    fold = {}
    st = {'vb': 0, 'rec': None}

    def V(p, u, v, a, n=(0.0, 1.0, 0.0)):
        pos.append(p)
        uv.append((u, v))
        aH.append(a)
        nrm.append(n)
        rec.append(st['rec'] if st['rec'] is not None else ZERO_REC)
        st['vb'] += 1
        return st['vb'] - 1

    def tri3(a, b, c):
        idx.extend((a, b, c))

    def quad(a, b, c, d):
        idx.extend((a, b, c, a, c, d))

    tube_ranges = []
    stalk = DAISY_SHEET['stalk']

    def sweep_tube(pts, radii, weights, RADS, vA, vB):
        n = len(pts)
        start = st['vb']
        tans = [norm(sub(pts[min(n - 1, i + 1)], pts[max(0, i - 1)])) for i in range(n)]
        s1 = (tans[0][2], 0.0, -tans[0][0]) if abs(tans[0][1]) < 0.95 else (1.0, 0.0, 0.0)
        s1 = norm(sub(s1, mul(tans[0], dot(s1, tans[0]))))
        arc_tot = 0.0
        for i in range(1, n):
            arc_tot += hyp(sub(pts[i], pts[i - 1]))
        rows = []
        arc = 0.0
        u0, u1 = stalk['u0'], stalk['u1']
        for i in range(n):
            if i > 0:
                arc += hyp(sub(pts[i], pts[i - 1]))
                s1 = norm(sub(s1, mul(tans[i], dot(s1, tans[i]))))
            t = tans[i]
            s2 = cross(t, s1)
            vv = vA + (vB - vA) * (arc / (arc_tot or 1))
            row = []
            for j in range(RADS + 1):
                an = (j / RADS) * TAU
                o = add(mul(s1, math.cos(an)), mul(s2, math.sin(an)))
                row.append(V(add(pts[i], mul(o, radii[i])), u0 + (u1 - u0) * _tri((j / RADS) * 2), vv, weights[i], o))
            rows.append(row)
        for i in range(n - 1):
            for j in range(RADS):
                quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])
        tube_ranges.append((start, st['vb']))

    def leaf_card(win, key, pts, side_dirs, sizeMM, a0, a1, t0=0.0, cols=2, upK=0.4):
        f = (fit.get('leaves') or {}).get(key) or FIT_FALLBACK['leaves'][key]
        bands = f['bands']
        NB = len(bands)
        winW, winH = (win['x1'] - win['x0']) * PX, (win['y1'] - win['y0']) * PX
        mmPerPx = win['L'] / (win['x1'] - win['x0'] - 16)
        acrossMM = (win['y1'] - win['y0']) * mmPerPx
        g0 = js_round(t0 * (NB - 1))
        sB = st['vb']
        nSt = NB - g0
        sc = (sizeMM * 0.001) / win['L']
        for g in range(g0, NB):
            tt = g / (NB - 1)
            k = (g - g0) / (nSt - 1)
            c, side = pts(k), side_dirs(k)
            cF, hwF = bands[g]
            hw = hwF * acrossMM * sc
            off = (cF - 0.5) * acrossMM * sc
            u = win['x0'] * PX + (f['u'][0] + tt * (f['u'][1] - f['u'][0])) * winW
            vC, vHw = win['y0'] * PX + cF * winH, hwF * winH
            a = a0 + (a1 - a0) * k
            nUp = norm(cross(sub(pts(min(1, k + 0.02)), pts(max(0, k - 0.02))), side))
            cc = add(c, mul(side, off))
            if cols == 2:
                V(sub(cc, mul(side, hw)), u, vC - vHw, a, nUp)
                V(add(cc, mul(side, hw)), u, vC + vHw, a, nUp)
            else:
                trough = mul(nUp, -hw * 0.22)
                V(sub(cc, mul(side, hw)), u, vC - vHw, a, nUp)
                V(add(cc, trough), u, vC, a, nUp)
                V(add(cc, mul(side, hw)), u, vC + vHw, a, nUp)
        for g in range(nSt - 1):
            A = sB + g * cols
            B = A + cols
            for q in range(cols - 1):
                quad(A + q, B + q, B + q + 1, A + q + 1)
        return (sB, st['vb'], upK)

    H0 = cfg['height']
    mm = 0.001
    leaf_blocks = []
    head_info = []

    # ── basal rosette ──
    nRos = irange(cfg['rosette'][0], cfg['rosette'][1])
    rosRot = R() * TAU
    for i in range(nRos):
        az = rosRot + i * 2.39996 + rng.vary(0, 0.25)
        d = (math.cos(az), 0.0, math.sin(az))
        sz = rng.range(0.75, 1.1) * (1 - 0.25 * (i / nRos))
        petL = rng.range(0.022, 0.034) * sz
        rise = rng.range(0.28, 0.5)
        p0 = (d[0] * 0.004, -0.012, d[2] * 0.004)
        p1 = add(p0, add(mul(d, petL * 0.55), (0, petL * rise * 0.9 + 0.01, 0)))
        p2 = add(p0, add(mul(d, petL), (0, petL * rise + 0.008, 0)))
        ptsP = []
        for t in (0, 0.4, 0.75, 1):
            s = 1 - t
            ptsP.append(tuple(s * s * p0[k] + 2 * s * t * p1[k] + t * t * p2[k] for k in range(3)))
        aL = 0.02 + 0.03 * sz
        sweep_tube(ptsP, [r * mm * math.sqrt(sz) for r in (1.15, 1.0, 0.85, 0.72)], [aL * k / 3 for k in range(4)],
                   4, stalk['v0'], stalk['v0'] + 0.04)
        win = DAISY_SHEET['basal'][i % 2]
        key = 'basalB' if i % 2 else 'basalA'
        bladeL = win['L'] * mm * sz * rng.range(0.9, 1.15)
        tan = norm(sub(p2, p1))
        b0 = sub(p2, mul(tan, 0.0015))
        b1 = add(b0, mul(tan, bladeL * 0.35))
        tipH = rng.range(-0.004, 0.012)
        b3 = (b0[0] + d[0] * bladeL * 0.92, max(0.004, tipH + 0.004), b0[2] + d[2] * bladeL * 0.92)
        b2 = (b0[0] + d[0] * bladeL * 0.62, b0[1] + 0.012 * sz, b0[2] + d[2] * bladeL * 0.62)
        twist = rng.vary(0, 0.35)
        side0 = norm(cross(UP, d))

        def pts(k, b0=b0, b1=b1, b2=b2, b3=b3):
            return bez3(b0, b1, b2, b3, k)

        def sides(k, pts=pts, side0=side0, twist=twist):
            tg = norm(sub(pts(min(1, k + 0.02)), pts(max(0, k - 0.02))))
            return norm(rot_axis(side0, tg, twist * k))
        leaf_blocks.append(leaf_card(win, key, pts, sides, bladeL / mm / 0.82, aL, aL + 0.03, 1 / 6, 3, 0.55))

    # ── one head: involucre cup, disc dome, ray whorl ──
    def build_head(C, a, s, aHead, bud):
        s1 = norm(cross(a, (0, 1, 0)))
        if not math.isfinite(s1[0]) or hyp(cross(a, (0, 1, 0))) < 1e-3:
            s1 = (1.0, 0.0, 0.0)
        s2 = cross(a, s1)

        def radial(th):
            return add(mul(s1, math.cos(th)), mul(s2, math.sin(th)))

        def P(r, x, th):
            return add(C, add(mul(a, x * mm * s), mul(radial(th), r * mm * s)))
        lodC = 0 if bud else 1
        st['rec'] = (C[0], C[1], C[2], 1, 0, 0, 0, 0, 0, 0, 0, lodC)
        # involucre cup (outer surface faces away from the head)
        RADS = 12
        prof = [[1.25, _cupZ(1.25) - 0.35], [2.6, _cupZ(2.6) - 0.32], [4.4, _cupZ(4.4) - 0.28],
                [6.2, _cupZ(6.2) - 0.22], [7.8, _cupZ(7.8) - 0.15], [9.05, -0.62]]
        I = DAISY_SHEET['invol']
        rings = []
        for r, x in prof:
            row = []
            for j in range(RADS + 1):
                th = (j / RADS) * TAU
                k = (r / I['mm']) * I['r']
                row.append(V(P(r, x, th), I['cu'] + k * math.cos(th), I['cv'] + k * math.sin(th), aHead))
            rings.append(row)
        for i in range(len(rings) - 1):
            for j in range(RADS):
                A, B = rings[i], rings[i + 1]
                idx.extend((A[j], A[j + 1], B[j + 1], A[j], B[j + 1], B[j]))
        # disc dome (front normal = a): planar uv, u along s1
        RADS = 16
        D = DAISY_SHEET['disc']
        prof = [[rho * RD, _domeZ(rho) + 0.55] for rho in (0.35, 0.65, 0.86, 1.0)]
        prof += [[RD * 1.06, 0.25], [RD * 1.0, -0.6]]
        c0 = V(P(0, _domeZ(0) + 0.55, 0), D['cu'], D['cv'], aHead)
        rings = []
        for r, x in prof:
            row = []
            for j in range(RADS + 1):
                th = (j / RADS) * TAU
                k = (min(r, D['mm']) / D['mm']) * D['r'] * 0.965
                row.append(V(P(r, x, th), D['cu'] + k * math.cos(th), D['cv'] + k * math.sin(th), aHead))
            rings.append(row)
        for j in range(RADS):
            tri3(c0, rings[0][j], rings[0][j + 1])
        for i in range(len(rings) - 1):
            for j in range(RADS):
                A, B = rings[i], rings[i + 1]
                idx.extend((A[j], B[j], B[j + 1], A[j], B[j + 1], A[j + 1]))
        # ray florets: fitted cards, bases tucked under the disc rim, two alternating layers; each petal hinges just
        # outside the rim
        petal_start = st['vb']
        N = 13 if bud else irange(cfg['petals'][0], cfg['petals'][1])
        PT = DAISY_SHEET['petals']
        ph0 = R() * TAU
        lenK = 0.42 if bud else 1
        for k in range(N):
            th = ph0 + (k / N) * TAU + rng.vary(0, 0.05)
            rh = radial(th)
            Kx = cross(rh, a)
            cell = math.floor(R() * 15)
            if cell >= 7:
                cell += 1
            cx, cy = cell % 8, cell // 8
            bands = fit['petals'][cell] if cell < len(fit['petals']) else FIT_FALLBACK['petals'][0]
            pvl = fit.get('petalV')
            pv = pvl[cell] if pvl and cell < len(pvl) else [0.02, 0.98]
            L = 16 * rng.range(0.86, 1.1) * lenK
            layer = -0.13 if k % 2 else 0.13
            pitch = rng.range(1.25, 1.45) if bud else rng.range(-0.1, 0.24) + (-0.05 if k % 2 else 0.05)
            droop = -0.1 if bud else rng.range(-0.62, 0.02)
            roll = rng.vary(0, 0.26)
            bowK = 0 if bud else rng.vary(0, 0.075)
            sideW = norm(rot_axis(Kx, rh, roll))
            hingeR, hingeX = 9.4, -0.5
            closeA = 0 if bud else 1.32 + (0.14 if k % 2 else -0.02) + rng.vary(0, 0.06)
            Hp = P(hingeR, hingeX, th)
            NBp = len(bands)
            sA = st['vb']
            clear = 3.2 / L
            px, pxx = 7.0, -0.6 + layer
            u0c, v0c = (PT['x0'] + PT['cw'] * cx) * PX, (PT['y0'] + PT['ch'] * cy) * PX
            cellW, cellH = PT['cw'] * PX, PT['ch'] * PX
            prevT = 0.0
            for g in range(NBp):
                t = g / (NBp - 1)
                steps = 6
                if g > 0:
                    for q in range(steps):
                        tm = prevT + (t - prevT) * (q + 0.5) / steps
                        phi = 0.02 if tm < clear else pitch + droop * ((tm - clear) / (1 - clear)) ** 1.6
                        ds = L * (t - prevT) / steps
                        px += math.cos(phi) * ds
                        pxx += math.sin(phi) * ds
                prevT = t
                ctr = P(px, pxx, th)
                cF, hwF = bands[g]
                hw = hwF * PT['cw'] * PT['mmPerPx'] * mm * s
                off = (cF - 0.5) * PT['cw'] * PT['mmPerPx'] * mm * s
                vv = v0c + (pv[0] + t * (pv[1] - pv[0])) * cellH
                uC, uHw = u0c + cF * cellW, hwF * cellW
                cc = add(ctr, mul(sideW, off + bowK * L * t * t * mm * s))
                tc = min(1.0, max(0.0, hyp(sub(cc, Hp)) / (L * mm * s)))
                st['rec'] = (C[0], C[1], C[2], 1, Hp[0], Hp[1], Hp[2], closeA * (1 + 0.3 * tc), Kx[0], Kx[1], Kx[2], lodC)
                fold[V(sub(cc, mul(sideW, hw)), uC - uHw, vv, aHead)] = sideW
                fold[V(add(cc, mul(sideW, hw)), uC + uHw, vv, aHead)] = mul(sideW, -1)
            for g in range(NBp - 1):
                A = sA + g * 2
                idx.extend((A, A + 1, A + 3, A, A + 3, A + 2))
        petal_end = st['vb']
        # far card (lod class 2): the WebGPU edition's impostor quad, kept so vertex counts match the JS; the Blender
        # edition drops it before meshing (EEVEE's many samples keep far heads' colour; see the guide)
        if not bud:
            IM = DAISY_SHEET['imp']
            half = 23 * mm * s * 0.75
            cc = add(C, mul(a, 0.8 * mm * s))
            q0 = st['vb']
            for cu, cv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                st['rec'] = (C[0], C[1], C[2], 1, cu, cv, half, 0, 0, 0, 0, 2)
                V(add(cc, add(mul(s1, cu * half), mul(s2, cv * half))), IM['cu'] + cu * IM['h'], IM['cv'] + cv * IM['h'], aHead, a)
            quad(q0, q0 + 1, q0 + 2, q0 + 3)
        st['rec'] = None
        return (petal_start, petal_end)

    # ── flowering stems + heads ──
    s0, s1_ = cfg['stems']
    nStems = max(s0, min(s1_, js_round((rng.range(s0, s1_) + rng.range(s0, s1_)) / 2)))
    leanRot = R() * TAU
    placed = []
    for si in range(nStems):
        hk = H0 * (rng.range(0.92, 1.05) if si == 0 else rng.range(0.62, 0.98))
        bud = si > 0 and R() < cfg['budChance']
        dHead = cfg['headD'] * (cfg.get('headScale') or 1) * rng.range(0.86, 1.14) * (0.5 if bud else 1)
        leanAz = leanRot + si * (TAU / nStems) + rng.vary(0, 0.35)
        leanAng = rng.range(0.02, 0.1) if nStems == 1 else rng.range(0.1, 0.22)
        if cfg.get('facing'):
            az = rng.vary(0, 0.32)
            el = max(0.35, min(1.5, cfg['facing']['el'] + rng.vary(0, 0.14)))
        else:
            az = R() * TAU
            el = rng.range(0.6, 1.45)
        ax = (math.cos(el) * math.cos(az), math.sin(el), math.cos(el) * math.sin(az))
        s = dHead / 0.05
        kk = 1 if si else 0.3
        base = (math.cos(leanAz) * 0.012 * kk, -0.02, math.sin(leanAz) * 0.012 * kk)
        C = None
        for _ in range(6):
            top = (base[0] + math.cos(leanAz) * math.sin(leanAng) * hk, hk * math.cos(leanAng * 0.8),
                   base[2] + math.sin(leanAz) * math.sin(leanAng) * hk)
            C = add(top, mul(ax, 5.6 * mm * s))
            if not any(hyp(sub(q[0], C)) < 0.55 * (q[1] + dHead) for q in placed):
                break
            leanAng += 0.07
            leanAz += 0.5
        placed.append((C, dHead))
        neck = sub(C, mul(ax, 5.6 * mm * s))
        stemLen = hyp(sub(neck, base))
        lean = norm((math.cos(leanAz) * math.sin(leanAng), math.cos(leanAng), math.sin(leanAz) * math.sin(leanAng)))
        q1 = add(base, mul(lean, stemLen * 0.45))
        q2 = sub(neck, mul(ax, stemLen * 0.16))
        aTop = min(1.1, 0.35 + 0.65 * (hk / H0))
        NS = 14
        spts, srad, swt = [], [], []
        rS = math.sqrt(max(1, s)) * mm
        for k in range(NS + 1):
            t = 1 - math.pow(1 - k / NS, 1.5)
            spts.append(bez3(base, q1, q2, neck, t))
            srad.append((1.55 - 0.45 * t + 0.35 * max(0.0, (t - 0.88) / 0.12) ** 2) * rS)
            swt.append(aTop * math.pow(t, 1.25))
        spts.append(add(neck, mul(ax, 1.4 * mm * s)))
        srad.append(1.3 * rS)
        swt.append(aTop)
        sweep_tube(spts, srad, swt, 5, stalk['v0'] + 0.01, stalk['v1'])

        def stem_at(t, base=base, q1=q1, q2=q2, neck=neck):
            return bez3(base, q1, q2, neck, t)
        nSL = 1 if bud else irange(cfg['stemLeaves'][0], cfg['stemLeaves'][1])
        for li in range(nSL):
            f = 0.08 + 0.6 * ((li + rng.range(0.1, 0.8)) / nSL)
            p = stem_at(f)
            tg = norm(sub(stem_at(f + 0.02), stem_at(f - 0.02)))
            azL = leanAz + math.pi * 0.5 + li * 2.4 + rng.vary(0, 0.4)
            out = (math.cos(azL), 0.0, math.sin(azL))
            out = norm(sub(out, mul(tg, dot(out, tg))))
            leafL = rng.range(0.032, 0.048) * (1.15 - 0.6 * f) * max(1, math.sqrt(s) * 0.8)
            ang = rng.range(0.5, 0.85)
            d0 = norm(add(mul(tg, math.cos(ang)), mul(out, math.sin(ang))))
            l0 = add(p, mul(out, 0.0009))
            l1 = add(l0, mul(d0, leafL * 0.45))
            l3 = add(add(l0, mul(d0, leafL * 0.95)), (0, -leafL * rng.range(0.12, 0.3), 0))
            l2 = add(lerp3(l1, l3, 0.5), (0, leafL * 0.05, 0))

            def pts(k, l0=l0, l1=l1, l2=l2, l3=l3):
                return bez3(l0, l1, l2, l3, k)
            side0 = norm(cross(tg, out))

            def sides(k, pts=pts, side0=side0):
                tgl = norm(sub(pts(min(1, k + 0.02)), pts(max(0, k - 0.02))))
                return norm(sub(side0, mul(tgl, dot(side0, tgl))))
            win = DAISY_SHEET['stemLeaf'][li % 2]
            key = 'stemB' if li % 2 else 'stemA'
            aAt = aTop * math.pow(f, 1.25)
            leaf_blocks.append(leaf_card(win, key, pts, sides, leafL / mm, aAt, aAt + 0.05, 0, 2, 0.3))
        petals = build_head(C, ax, s, aTop, bud)
        head_info.append({'c': C, 'a': ax, 'd': dHead, 'bud': bud, 'petals': petals, 'aH': aTop})

    # ── assemble, then the gen-owned normal treatment ──
    P = np.array(pos, dtype=np.float64)
    T = np.array(idx, dtype=np.int64).reshape(-1, 3)
    N = vertex_normals(P, T)
    for (a0, a1, k) in leaf_blocks:       # leaf cards lean toward up (the turf law) so rosettes light like ground
        m = N[a0:a1] * (1 - k)
        m[:, 1] += k
        ln = np.linalg.norm(m, axis=1, keepdims=True)
        ln[ln == 0] = 1
        N[a0:a1] = m / ln
    kb = cfg.get('petalBend', 0.5)
    for h in head_info:                   # ray cards: half geometric, half bent from a centre behind the disc
        back = np.array(sub(h['c'], mul(h['a'], h['d'] * 1.3)))
        ha = np.array(h['a'])
        for i in range(h['petals'][0], h['petals'][1]):
            bent = P[i] - back
            bent /= (np.linalg.norm(bent) or 1)
            n = N[i].copy()
            if n @ ha < 0:
                n = -n
            m = n * (1 - kb) + bent * kb
            m /= (np.linalg.norm(m) or 1)
            fd = fold.get(i)
            if fd is not None:
                m = m + np.array(fd) * 0.36
                m /= (np.linalg.norm(m) or 1)
            N[i] = m
    NR = np.array(nrm, dtype=np.float64)
    for (a0, a1) in tube_ranges:          # tubes: the analytic radial normals captured at emission
        N[a0:a1] = NR[a0:a1]
    REC = np.array(rec, dtype=np.float64)
    extra = {
        'close_center_v': REC[:, 0:3], 'is_head': REC[:, 3], 'close_hinge_v': REC[:, 4:7],
        'close_angle': REC[:, 7], 'close_axis_v': REC[:, 8:11], 'lod_class': REC[:, 11],
    }
    geo = PlantGeo(P, uv, aH, T, N, extra)
    heads = [h for h in head_info]
    geo.stats = {'verts': st['vb'], 'tris': len(T), 'heads': sum(1 for h in heads if not h['bud']),
                 'buds': sum(1 for h in heads if h['bud'])}
    lod = cfg.get('lod')
    return {'geo': geo, 'heads': heads, 'stats': geo.stats,
            'lod': None if lod is False else [d * (cfg.get('headScale') or 1) for d in lod]}


# ── petal palette ─────────────────────────────────────────────────────────
LUM_WHITE = 0.74          # measured mean luminance of the white ray art (linear)
PET = {'u0': 428 * PX, 'v0': 605 * PX, 'rowH': 207 * PX}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    return [srgb_to_linear(((h >> s) & 255) / 255) for s in (16, 8, 0)]


def resolve_daisy_palette(color):
    """None (white art) or a list of {'cum': c | None, 'base': lin rgb, 'tip': lin rgb, 'white': bool}."""
    if color is None:
        return None

    def one(c):
        if isinstance(c, (list, tuple)):
            k = 1 / 255 if any(x > 1 for x in c) else 1
            col = [srgb_to_linear(x * k) for x in c[:3]]
            return {'base': [x * 0.85 for x in col], 'tip': col, 'white': False}
        if c not in DAISY_COLORS:
            raise ValueError(f"[daisy] unknown color '{c}': have {', '.join(DAISY_COLORS)} (or [r,g,b], or a {{name: weight}} mix)")
        e = DAISY_COLORS[c]
        return {'base': hex_lin(e['base']), 'tip': hex_lin(e['tip']), 'white': False} if e else {'white': True}
    if isinstance(color, (str, list, tuple)):
        e = one(color)
        return None if e['white'] else [dict(e, cum=None)]
    entries = [(k, w) for k, w in color.items() if w > 0]
    tot = sum(w for _, w in entries) or 1
    acc = 0.0
    out = []
    for k, w in entries:
        acc += w / tot
        out.append(dict(one(k), cum=acc))
    return out
