"""vegetation_sunflower_gen: the sunflower (Helianthus annuus) for create_flora, ported line for line from
eidoverse/vegetation_sunflower_gen.js (same draw order): one continuous parallel-transported cane (base -> neck arc
-> head), spiral petioled heart leaves with cup, ruffle and a decurving tip fitted to sunflower_fit.json, and a
nodding head (thin-plate seed disc lathe, two fitted ray whorls, a 10-wedge bract cup), on the ONE sunflower_ sheet.
The generator owns its normals: head cards spherical-bent from a centre behind the disc, leaf blades up-blended,
tubes geometric. The whole head shares one aH (0.82): one rigid assembly in wind.

sunflower_ sheet (UV, v up): DISC circle (.2405, .780) r .2053; PETALS u .5-1, v .586-1 (4 x 2 fitted cells);
BRACT circle (.826, .3793) r .1701; LEAF u .004-.6305, v .2102-.5396 (midrib .3743); STALK v .005-.195.
"""
import math

import numpy as np

from .jsmath import Rng, js_round
from .plantgeo import PlantGeo, vertex_normals

TAU = math.pi * 2


def _tri(s):
    m = math.fmod(s, 2)
    return m if m <= 1 else 2 - m


def _hyp(*a):
    return math.sqrt(sum(x * x for x in a))


DISC_R, DISC_K, DISC_X = 0.30, 0.90, -0.012
DISC_FRONT = [[r * DISC_K, DISC_X + 0.012 + 0.052 * math.pow(1 - math.pow(r / 0.302, 2.2), 0.8)]
              for r in (0, 0.09, 0.16, 0.22, 0.265, 0.29, 0.300)]
DISC_RIM_BACK = [[0.302 * DISC_K, DISC_X + 0.002], [0.290 * DISC_K, DISC_X - 0.014],
                 [0.170 * DISC_K, DISC_X - 0.036], [0.000, DISC_X - 0.046]]
FIT_FALLBACK = {
    'petals': [[[0.5, 0.20], [0.5, 0.31], [0.5, 0.34], [0.5, 0.34], [0.5, 0.32], [0.5, 0.19]]] * 8,
    'leaf': [[0.5, 0.47], [0.5, 0.5], [0.5, 0.5], [0.5, 0.5], [0.5, 0.39], [0.5, 0.22]],
    'bractR': 1.0,
}
SUNFLOWER_GEN = {'sunflower': {'height': 1.9, 'leaves': 11, 'leafLen': 0.62, 'headR': 0.20, 'petals': 34}}


def build_sunflower_geometry(name, seed, over=None):
    cfg = dict(SUNFLOWER_GEN.get(name, SUNFLOWER_GEN['sunflower']))
    cfg.update(over or {})
    fit = cfg.get('fit') or FIT_FALLBACK
    rng = Rng(seed)
    R = rng.next
    pos, uv, aH, idx = [], [], [], []
    st = {'vb': 0}

    def V(x, y, z, u, vv, a):
        pos.append((x, y, z)); uv.append((u, vv)); aH.append(a)
        st['vb'] += 1
        return st['vb'] - 1

    def quad(a, b, c, d):
        idx.extend((a, b, c, a, c, d))

    def B(p0, p1, p2, t):
        s = 1 - t
        return [s * s * p0[k] + 2 * s * t * p1[k] + t * t * p2[k] for k in range(3)]

    def sweep_tube(pts, radii, weights, RADS, vStart=0.012):
        n = len(pts)
        tans = []
        for i in range(n):
            a, b = pts[max(0, i - 1)], pts[min(n - 1, i + 1)]
            t = [b[0] - a[0], b[1] - a[1], b[2] - a[2]]
            ln = _hyp(*t) or 1
            tans.append([t[0] / ln, t[1] / ln, t[2] / ln])
        t0 = tans[0]
        s1 = [t0[2], 0, -t0[0]] if abs(t0[1]) < 0.95 else [1, 0, 0]
        d = s1[0] * t0[0] + s1[1] * t0[1] + s1[2] * t0[2]
        s1 = [s1[0] - t0[0] * d, s1[1] - t0[1] * d, s1[2] - t0[2] * d]
        ln = _hyp(*s1) or 1
        s1 = [s1[0] / ln, s1[1] / ln, s1[2] / ln]
        rows = []
        arc = 0.0
        for i in range(n):
            if i > 0:
                arc += _hyp(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2])
                t = tans[i]
                d = s1[0] * t[0] + s1[1] * t[1] + s1[2] * t[2]
                s1 = [s1[0] - t[0] * d, s1[1] - t[1] * d, s1[2] - t[2] * d]
                ln = _hyp(*s1) or 1
                s1 = [s1[0] / ln, s1[1] / ln, s1[2] / ln]
            t = tans[i]
            s2 = [t[1] * s1[2] - t[2] * s1[1], t[2] * s1[0] - t[0] * s1[2], t[0] * s1[1] - t[1] * s1[0]]
            r, row = radii[i], []
            vband = vStart + 0.176 * _tri(vStart / 0.18 + arc * 1.15)
            for j in range(RADS + 1):
                an = (j / RADS) * TAU
                ox = s1[0] * math.cos(an) + s2[0] * math.sin(an)
                oy = s1[1] * math.cos(an) + s2[1] * math.sin(an)
                oz = s1[2] * math.cos(an) + s2[2] * math.sin(an)
                row.append(V(pts[i][0] + ox * r, pts[i][1] + oy * r, pts[i][2] + oz * r,
                             0.03 + 0.94 * _tri((j / RADS) * 2), vband, weights[i]))
            rows.append(row)
        for i in range(len(rows) - 1):
            for j in range(RADS):
                quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])

    # ── head placement first (the cane sweeps INTO it) ──
    H = cfg['height'] * (cfg['heightJitter'] if cfg.get('heightJitter') is not None else rng.range(0.9, 1.1))
    leanA = R() * TAU
    leanAmt = (cfg['stalkLean'] if cfg.get('stalkLean') is not None else rng.range(0.02, 0.08)) * H
    lx, lz = math.cos(leanA) * leanAmt, math.sin(leanA) * leanAmt

    def P(t):
        return [lx * t * t, t * H, lz * t * t]

    def stalkR(t):
        return 0.019 * (1 - t) + 0.008 * t
    aHead = 0.82
    s = (cfg['headR'] if cfg.get('headR') is not None else 0.20) / 0.50
    pitch = cfg['pitch'] if cfg.get('pitch') is not None else rng.range(0.6, 1.05)
    headYaw = cfg['headYaw'] if cfg.get('headYaw') is not None else (leanA + rng.vary(0, 0.6))
    ax, ay, az = math.cos(headYaw) * math.sin(pitch), math.cos(pitch), math.sin(headYaw) * math.sin(pitch)
    s1x, s1y, s1z = -az, 0.0, ax
    ln = _hyp(s1x, s1y, s1z) or 1
    s1x, s1z = s1x / ln, s1z / ln
    s2x, s2y, s2z = ay * s1z - az * s1y, az * s1x - ax * s1z, ax * s1y - ay * s1x
    neckL = 0.10 * s
    tx, ty, tz = P(1)
    hx, hy, hz = tx + ax * neckL * 0.85, ty + ay * neckL * 0.85 + neckL * 0.25, tz + az * neckL * 0.85

    def radial(th):
        return (s1x * math.cos(th) + s2x * math.sin(th), s1y * math.cos(th) + s2y * math.sin(th),
                s1z * math.cos(th) + s2z * math.sin(th))

    # ── the cane: ONE sweep, base -> stalk -> neck arc -> buried in the head ──
    pts, radii, weights = [], [], []
    for t in (0, 0.12, 0.25, 0.4, 0.55, 0.7, 0.85, 1):
        p = P(t)
        pts.append([p[0], -0.04 if t == 0 else p[1], p[2]])
        radii.append(stalkR(t))
        weights.append(t * 0.8)
    n0, n1 = [tx, ty, tz], [tx, ty + neckL * 0.55, tz]
    n2 = [hx - ax * 0.040 * s, hy - ay * 0.040 * s, hz - az * 0.040 * s]
    for t in (0.35, 0.7, 1):
        pts.append(B(n0, n1, n2, t))
        radii.append(stalkR(1) * (1 - t * 0.2))
        weights.append(0.8 + t * (aHead - 0.8))
    sweep_tube(pts, radii, weights, 6)

    # ── leaves: petiole tubes + fitted drooping heart blades ──
    LEAF = {'u0': 0.004, 'u1': 0.6305, 'v0': 0.2102, 'vm': 0.3743, 'v1': 0.5396}
    LEAF_ACROSS = (LEAF['v1'] - LEAF['v0']) / (LEAF['u1'] - LEAF['u0'])
    nL = js_round(cfg['leaves'] * rng.range(0.9, 1.15))
    rank = cfg['rank'] if cfg.get('rank') is not None else R() * TAU
    leaf_blade_start = []
    for i in range(nL):
        f = 0.14 + 0.63 * ((i + R() * 0.4) / nL)
        yaw = rank + i * 2.3998 + rng.vary(0, 0.3)
        size = (0.6 + 0.45 * math.sin(math.pi * min(1, 0.2 + f * 0.9))) * (1 - max(0, f - 0.6) * 0.9) * rng.range(0.85, 1.15)
        petL = cfg['leafLen'] * 0.34 * size
        bladeL = cfg['leafLen'] * 0.66 * size
        sx, sy, sz = P(f)
        dirX, dirZ = math.cos(yaw), math.sin(yaw)
        sideX, sideZ = -math.sin(yaw), math.cos(yaw)
        aL = f * 0.8
        r0 = stalkR(f)
        q0 = [sx + dirX * r0 * 0.2, sy, sz + dirZ * r0 * 0.2]
        q1 = [q0[0] + dirX * petL * 0.55, q0[1] + petL * 0.38, q0[2] + dirZ * petL * 0.55]
        q2 = [q0[0] + dirX * petL * 1.02, q0[1] + petL * rng.range(0.32, 0.5), q0[2] + dirZ * petL * 1.02]
        tp, tr, tw = [], [], []
        for t in (0, 0.34, 0.67, 1):
            tp.append(B(q0, q1, q2, t))
            tr.append((0.0062 - 0.0024 * t) * size)
            tw.append(aL + t * 0.05)
        sweep_tube(tp, tr, tw, 4, 0.03)
        petT = [q2[0] - q1[0], q2[1] - q1[1], q2[2] - q1[2]]
        ptl = _hyp(*petT) or 1
        b0 = q2
        b1 = [b0[k] + (petT[k] / ptl) * bladeL * 0.42 for k in range(3)]
        b2 = [b0[0] + dirX * bladeL * 0.82, b0[1] - bladeL * rng.range(0.3, 0.55), b0[2] + dirZ * bladeL * 0.82]
        bands = fit['leaf']
        NB = len(bands)
        rufPhase = R() * TAU
        rufFreq = rng.range(5.5, 7.5)
        COLS = [-1, -0.5, 0, 0.5, 1]
        sB = st['vb']
        leaf_blade_start.append(sB)
        for gg in range(NB):
            t = gg / (NB - 1)
            c = B(b0, b1, b2, t)
            cFrac, hwFrac = bands[gg]
            hw = hwFrac * LEAF_ACROSS * bladeL / 0.5
            a = min(1, aL + t * t * 0.16)
            u = LEAF['u0'] + t * (LEAF['u1'] - LEAF['u0'])
            vC = LEAF['v0'] + cFrac * (LEAF['v1'] - LEAF['v0'])
            vHw = hwFrac * (LEAF['v1'] - LEAF['v0'])
            sink = -0.006 if gg == 0 else 0
            tipDrop = max(0, t - 0.72) * bladeL * 0.35
            for k in COLS:
                cup = hw * 0.34 * k * k
                ruffle = hw * 0.09 * abs(k) * math.sin(rufPhase + t * rufFreq + k * 2.4)
                V(c[0] + sideX * hw * k + dirX * sink, c[1] - cup + ruffle - tipDrop, c[2] + sideZ * hw * k + dirZ * sink,
                  u, vC + vHw * k, a)
        for gg in range(NB - 1):
            a2 = sB + gg * 5
            b3 = a2 + 5
            for cq in range(4):
                quad(a2 + cq, a2 + cq + 1, b3 + cq + 1, b3 + cq)
    head_start = st['vb']

    # ── disc plate ──
    def disc_uv(rr, th):
        return (0.2405 + 0.2053 * (rr / DISC_R) * math.cos(th), 0.780 + 0.2053 * (rr / DISC_R) * math.sin(th))

    def back_uv(rr, th):
        return (0.826 + 0.16 * (rr / DISC_R) * math.cos(th), 0.3793 + 0.16 * (rr / DISC_R) * math.sin(th))
    RADD = 16
    prof = [p + [disc_uv] for p in DISC_FRONT] + [p + [disc_uv if i == 0 else back_uv] for i, p in enumerate(DISC_RIM_BACK)]
    rings = []
    for r, x, uvfn in prof:
        if r < 1e-6:
            uu2, vv2 = uvfn(0, 0)
            rings.append([V(hx + ax * x * s, hy + ay * x * s, hz + az * x * s, uu2, vv2, aHead)])
            continue
        row = []
        for j in range(RADD):
            th = (j / RADD) * TAU
            ox, oy, oz = radial(th)
            uu2, vv2 = uvfn(r, th)
            row.append(V(hx + ax * x * s + ox * r * s, hy + ay * x * s + oy * r * s, hz + az * x * s + oz * r * s, uu2, vv2, aHead))
        rings.append(row)
    for i in range(len(rings) - 1):
        A, Bb = rings[i], rings[i + 1]
        if len(A) == 1:
            for j in range(RADD):
                idx.extend((A[0], Bb[(j + 1) % RADD], Bb[j]))
        elif len(Bb) == 1:
            for j in range(RADD):
                idx.extend((A[j], A[(j + 1) % RADD], Bb[0]))
        else:
            for j in range(RADD):
                quad(A[j], A[(j + 1) % RADD], Bb[(j + 1) % RADD], Bb[j])
    petal_start = st['vb']

    # ── ray petals: dense layered whorl, per-band envelope in geometry AND uv ──
    N = cfg['petals'] if cfg.get('petals') is not None else 34
    cells = []
    for cx2 in range(4):
        for ry in range(2):
            cells.append({'u0': 0.5 + 0.125 * cx2 + 0.006, 'u1': 0.5 + 0.125 * (cx2 + 1) - 0.006,
                          'v0': 0.7937 if ry == 0 else 0.5879, 'v1': 0.9995 if ry == 0 else 0.7927,
                          'fit': fit['petals'][cx2 * 2 + ry]})
    rimR = 0.262
    needHW = (TAU * rimR / N) * 0.5 * 1.25
    layers = [{'n': N, 'rIn': 0.020, 'lenK': 1.0, 'phase': 0, 'droopLo': -0.15, 'droopHi': 0.18},
              {'n': js_round(N * 0.7), 'rIn': 0.042, 'lenK': 0.55, 'phase': math.pi / N, 'droopLo': 0.05, 'droopHi': 0.35}]
    for LY in layers:
        for k in range(LY['n']):
            th = (k / LY['n']) * TAU + LY['phase'] + rng.vary(0, 0.04)
            cell = cells[math.floor(R() * len(cells))]
            maxEnv = max(b[1] for b in cell['fit'])
            cardHW = needHW / maxEnv
            L = cardHW * 2 * (0.207 / 0.125) * LY['lenK'] * rng.range(0.94, 1.06)
            ox, oy, oz = radial(th)
            txp = s2x * math.cos(th) - s1x * math.sin(th)
            typ = s2y * math.cos(th) - s1y * math.sin(th)
            tzp = s2z * math.cos(th) - s1z * math.sin(th)
            droop = rng.range(LY['droopLo'], LY['droopHi']) - (0.18 if LY['lenK'] == 1 and k % 5 == 0 else 0)
            roll = rng.vary(0, 0.35)
            wx = txp * math.cos(roll) + ax * math.sin(roll)
            wy = typ * math.cos(roll) + ay * math.sin(roll)
            wz = tzp * math.cos(roll) + az * math.sin(roll)
            bxp = hx + ox * (rimR - LY['rIn']) * s - ax * 0.008 * s
            byp = hy + oy * (rimR - LY['rIn']) * s - ay * 0.008 * s
            bzp = hz + oz * (rimR - LY['rIn']) * s - az * 0.008 * s
            bands = cell['fit']
            NBp = len(bands)
            uSpan = cell['u1'] - cell['u0']
            sA = st['vb']
            for gg in range(NBp):
                t = gg / (NBp - 1)
                cFrac, hwFrac = bands[gg]
                hw = hwFrac * cardHW * 2
                dk = droop * min(1, max(0, (t - 0.12) / 0.38))
                cd, sd = math.cos(dk), math.sin(dk)
                dx, dy, dz = ox * cd + ax * sd, oy * cd + ay * sd, oz * cd + az * sd
                cup = math.sin(t * math.pi) * L * 0.05
                cx3, cy3, cz3 = bxp + dx * L * t * s + ax * cup * s, byp + dy * L * t * s + ay * cup * s, bzp + dz * L * t * s + az * cup * s
                vv2 = cell['v0'] + (cell['v1'] - cell['v0']) * t
                uC, uHw = cell['u0'] + cFrac * uSpan, hwFrac * uSpan
                V(cx3 - wx * hw * s, cy3 - wy * hw * s, cz3 - wz * hw * s, uC - uHw, vv2, aHead)
                V(cx3 + wx * hw * s, cy3 + wy * hw * s, cz3 + wz * hw * s, uC + uHw, vv2, aHead)
            for gg in range(NBp - 1):
                a2 = sA + gg * 2
                quad(a2, a2 + 1, a2 + 3, a2 + 2)

    # ── bract cup: tilted wedge cards sampling radial slices of the rosette ──
    BR = {'cu': 0.826, 'cv': 0.3793, 'r': 0.1701}
    bR = min(fit.get('bractR') if fit.get('bractR') is not None else 1.0, 1.05)
    uvR = BR['r'] * bR * 0.97
    NB2 = 10
    for k in range(NB2):
        phi = (k / NB2) * TAU + rng.vary(0, 0.12)
        deep = k % 2 == 0
        ox, oy, oz = radial(phi)
        txp = s2x * math.cos(phi) - s1x * math.sin(phi)
        typ = s2y * math.cos(phi) - s1y * math.sin(phi)
        tzp = s2z * math.cos(phi) - s1z * math.sin(phi)
        xBase, rBase = (-0.040 if deep else -0.030) * s, 0.06 * s
        xTip = (-0.012 if deep else -0.004) * s
        rTip = (0.315 + rng.vary(0.02, 0.015)) * s * (0.94 if deep else 1)
        halfWedge = (TAU / NB2) * 0.5 * 1.3
        sA = st['vb']
        for gg in range(3):
            t = gg / 2
            rr = rBase + (rTip - rBase) * t
            xx2 = xBase + (xTip - xBase) * (t * t * 0.4 + t * 0.6)
            hwW = rr * math.sin(halfWedge)
            cup = hwW * 0.3 * (1 - t * 0.5)
            uvr = (0.2 + 0.8 * t) * uvR
            uvHw = uvr * math.tan(halfWedge) * 0.92
            cx3, cy3, cz3 = hx + ax * xx2 + ox * rr, hy + ay * xx2 + oy * rr, hz + az * xx2 + oz * rr
            cU, cV = BR['cu'] + uvr * math.cos(phi), BR['cv'] + uvr * math.sin(phi)
            pU, pV = -math.sin(phi) * uvHw, math.cos(phi) * uvHw
            V(cx3 - txp * hwW - ax * cup, cy3 - typ * hwW - ay * cup, cz3 - tzp * hwW - az * cup, cU - pU, cV - pV, aHead)
            V(cx3, cy3, cz3, cU, cV, aHead)
            V(cx3 + txp * hwW - ax * cup, cy3 + typ * hwW - ay * cup, cz3 + tzp * hwW - az * cup, cU + pU, cV + pV, aHead)
        for gg in range(2):
            a2 = sA + gg * 3
            b3 = a2 + 3
            quad(a2, a2 + 1, b3 + 1, b3)
            quad(a2 + 1, a2 + 2, b3 + 2, b3 + 1)

    Pp = np.array(pos)
    T = np.array(idx).reshape(-1, 3)
    p32 = Pp.astype(np.float32).astype(np.float64)
    Nn = vertex_normals(p32, T)
    nc = np.array([hx - ax * 0.05 * s, hy - ay * 0.05 * s, hz - az * 0.05 * s])
    d = p32[petal_start:] - nc
    ln = np.linalg.norm(d, axis=1, keepdims=True)
    ln[ln == 0] = 1
    Nn[petal_start:] = d / ln
    UPK = 0.65
    for sB in leaf_blade_start:
        e = min(sB + 30, head_start)
        m = Nn[sB:e] * (1 - UPK)
        m[:, 1] += UPK
        ln = np.linalg.norm(m, axis=1, keepdims=True)
        ln[ln == 0] = 1
        Nn[sB:e] = m / ln
    geo = PlantGeo(Pp, uv, aH, T, Nn)
    geo.stats = {'verts': st['vb'], 'tris': len(T)}
    return {'geo': geo, 'stats': geo.stats, 'headYaw': headYaw,
            'head': {'c': (hx, hy, hz), 'a': (ax, ay, az)}}
