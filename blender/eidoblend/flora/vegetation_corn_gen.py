"""vegetation_corn_gen: the corn plant (Zea mays) for create_flora, ported line for line from
eidoverse/vegetation_corn_gen.js (same draw order, so a seed grows the same plant in both editions): a leaning
6-sided cane, distichous arching leaves collision-tested against the ears and each other, 1-3 ears (husked, or
peeled with the baked cob standing bare), silk, and a sparse strand tassel, all on the ONE corn_ trim sheet.

corn_ sheet regions (UV, v up): COB u 0-.5, v .701-1 (the baked highpoly); PLUME u .5-1, v .701-1; HUSK v .499-.700;
LEAF u .004-.998, v .2139-.4922 (midrib at .3496); STALK v .005-.195. Wrapped surfaces ping-pong their UVs (the
sheet clamps), so fibre stays continuous with no wrap seam.
"""
import math

import numpy as np

from .jsmath import Rng, js_round
from .plantgeo import PlantGeo, vertex_normals

TAU = math.pi * 2
COB_PROF = [
    [0.000, 0.051], [0.025, 0.0856], [0.050, 0.1069], [0.100, 0.1241],
    [0.150, 0.1317], [0.225, 0.1345], [0.300, 0.1337], [0.400, 0.1304],
    [0.500, 0.1269], [0.600, 0.1221], [0.700, 0.1149], [0.800, 0.1028],
    [0.875, 0.0857], [0.9440, 0.0452], [0.9470, 0.0375], [0.965, 0.032],
    [0.985, 0.0240],
]
COB_STA = [0, 1, 2, 3, 5, 7, 9, 11, 12, 13, 14, 16]


def _tri(s):
    m = math.fmod(s, 2)
    return m if m <= 1 else 2 - m


def _hyp(*a):
    return math.sqrt(sum(x * x for x in a))


CORN_GEN = {'corn': {'height': 2.15, 'leaves': 10, 'leafLen': 0.85, 'ears': 1, 'peel': False}}


def build_corn_geometry(name, seed, over=None):
    cfg = dict(CORN_GEN.get(name, CORN_GEN['corn']))
    cfg.update(over or {})
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

    def g(k, default=None):
        v = cfg.get(k)
        return default if v is None else v

    # ── stalk: a leaning cane ──
    H = cfg['height'] * (cfg['heightJitter'] if cfg.get('heightJitter') is not None else rng.range(0.92, 1.08))
    leanA = R() * TAU
    leanAmt = (cfg['stalkLean'] if cfg.get('stalkLean') is not None else rng.range(0.04, 0.13)) * H
    lx, lz = math.cos(leanA) * leanAmt, math.sin(leanA) * leanAmt

    def P(t):
        return (lx * t * t, t * H, lz * t * t)

    def stalkR(t):
        return 0.023 * (1 - t) + 0.010 * t
    STA, RADS = [0, 0.12, 0.25, 0.4, 0.55, 0.7, 0.85, 1], 6
    rows = []
    for t in STA:
        cx, cy, cz = P(t)
        r, row = stalkR(t), []
        vband = 0.012 + 0.176 * _tri(t * 2.2)
        for j in range(RADS + 1):
            a = (j / RADS) * TAU
            u = 0.03 + 0.94 * _tri((j / RADS) * 2)
            row.append(V(cx + math.cos(a) * r, -0.04 if t == 0 else cy, cz + math.sin(a) * r, u, vband, t * 0.8))
        rows.append(row)
    for i in range(len(rows) - 1):
        for j in range(RADS):
            quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])

    # ── leaves: distichous ranks, arching blades on the leaf band ──
    LEAF = {'v0': 0.2139, 'vm': 0.3496, 'v1': 0.4922, 'u0': 0.004, 'u1': 0.998}
    nL = js_round(cfg['leaves'] * rng.range(0.9, 1.1))
    rank = cfg['rank'] if cfg.get('rank') is not None else R() * TAU

    def B(p0, p1, p2, t):
        s = 1 - t
        return tuple(s * s * p0[k] + 2 * s * t * p1[k] + t * t * p2[k] for k in range(3))

    def leaf(f, yaw, L, wHalf, up, reach, tipY):
        sx, sy, sz = P(f)
        dirX, dirZ = math.cos(yaw), math.sin(yaw)
        sideX, sideZ = -math.sin(yaw), math.cos(yaw)
        r = stalkR(f)
        p0 = (sx + dirX * r * 0.6, sy, sz + dirZ * r * 0.6)
        p1 = (p0[0] + dirX * L * 0.45, p0[1] + L * up, p0[2] + dirZ * L * 0.45)
        p2 = (p0[0] + dirX * L * reach, p0[1] + L * tipY, p0[2] + dirZ * L * reach)
        rollK = rng.vary(0, 0.7)
        aH0 = f * 0.8
        SEG, s0 = 8, st['vb']
        for sg in range(SEG + 1):
            t = sg / SEG
            c = B(p0, p1, p2, t)
            d = B(p0, p1, p2, min(1, t + 0.01))
            tx, ty, tz = d[0] - c[0], d[1] - c[1], d[2] - c[2]
            tl = _hyp(tx, ty, tz) or 1
            ux = (ty / tl) * sideZ
            uy = (tz / tl) * sideX - (tx / tl) * sideZ
            uz = -(ty / tl) * sideX
            ul = _hyp(ux, uy, uz) or 1
            ux, uy, uz = ux / ul, uy / ul, uz / ul
            if uy < 0:
                ux, uy, uz = -ux, -uy, -uz
            rA = rollK * t
            cr, sr = math.cos(rA), math.sin(rA)
            csx, csy, csz = sideX * cr + ux * sr, uy * sr, sideZ * cr + uz * sr
            hw = wHalf * (0.30 + 1.15 * math.pow(math.sin(min(math.pi, t * math.pi * 1.05)), 0.65))
            fold = hw * (0.55 * (1 - t) - 0.25 * t)
            a = min(1, aH0 + t * t * (1 - aH0) * 0.85)
            u = LEAF['u0'] + t * (LEAF['u1'] - LEAF['u0'])
            V(c[0] - csx * hw + ux * fold, c[1] - csy * hw + uy * fold, c[2] - csz * hw + uz * fold, u, LEAF['v0'], a)
            V(c[0], c[1], c[2], u, LEAF['vm'], a)
            V(c[0] + csx * hw + ux * fold, c[1] + csy * hw + uy * fold, c[2] + csz * hw + uz * fold, u, LEAF['v1'], a)
        for sg in range(SEG):
            a = s0 + sg * 3
            b = a + 3
            quad(a, a + 1, b + 1, b)
            quad(a + 1, a + 2, b + 2, b + 1)

    # ears drawn first (geometry params included) so leaves get exact collision capsules
    ear_specs = []
    maxE = g('ears', 1)
    nE = 1 + (1 if maxE >= 2 and R() < 0.4 else 0) + (1 if maxE >= 3 and R() < 0.22 else 0)
    pc = g('peelChance', 0.5 if cfg.get('peel') else 0)
    for k in range(nE):
        f = (cfg['earF'] if cfg.get('earF') is not None else rng.range(0.33, 0.4)) + k * rng.range(0.12, 0.16)
        yaw = cfg['earYaw'] + math.pi * k if cfg.get('earYaw') is not None else rank + math.pi * k + rng.vary(0.8, 0.5)
        lean = rng.range(0.4, 0.58)
        ln = rng.range(0.24, 0.29) * (1 - k * 0.12)
        peel = bool((cfg.get('peel') and k == 0) or R() < pc)
        ear_specs.append({'f': f, 'yaw': yaw, 'lean': lean, 'len': ln, 'peel': peel})
    caps = []
    for e in ear_specs:
        sx, sy, sz = P(e['f'])
        dirX, dirZ = math.cos(e['yaw']), math.sin(e['yaw'])
        ax, ay, az = dirX * math.sin(e['lean']), math.cos(e['lean']), dirZ * math.sin(e['lean'])
        r = stalkR(e['f'])
        bx, by, bz = sx + dirX * r * 0.35, sy - 0.02, sz + dirZ * r * 0.35
        cobLen = e['len'] * 0.95
        caps.append({'ax': ax, 'ay': ay, 'az': az, 'bx': bx, 'by': by, 'bz': bz,
                     'segL': cobLen * (1.0 if e['peel'] else 1.25), 'r': cobLen * 0.135 + 0.025,
                     'cx': bx + ax * cobLen * 0.45, 'cy': by + ay * cobLen * 0.45, 'cz': bz + az * cobLen * 0.45,
                     'cr': e['len'] * 0.5 if e['peel'] else 0})

    def dist_pt_seg(px, py, pz, c):
        dx, dy, dz = px - c['bx'], py - c['by'], pz - c['bz']
        t = max(0, min(c['segL'], dx * c['ax'] + dy * c['ay'] + dz * c['az']))
        return _hyp(px - (c['bx'] + c['ax'] * t), py - (c['by'] + c['ay'] * t), pz - (c['bz'] + c['az'] * t))
    placed = []
    for i in range(nL):
        f = 0.14 + 0.74 * ((i + R() * 0.5) / nL)
        L0 = cfg['leafLen'] * (0.62 + 0.55 * math.sin(math.pi * min(1, f * 1.4))) * rng.range(0.85, 1.15)
        if f > 0.7:
            L0 *= 1 - (f - 0.7) * 1.6
        best = None
        tries = 0
        while tries < 8 and not best:
            yaw = rank + i * math.pi + i * 0.55 + rng.vary(0, 0.85)
            up = rng.range(0.5, 0.64)
            reach = rng.range(1.0, 1.18)
            tipY = rng.range(-0.26, 0.0) if tries < 6 else rng.range(0.0, 0.12)
            L = L0 if tries < 6 else L0 * 0.6
            sx, sy, sz = P(f)
            dirX, dirZ = math.cos(yaw), math.sin(yaw)
            r0 = stalkR(f)
            q0 = (sx + dirX * r0 * 0.6, sy, sz + dirZ * r0 * 0.6)
            q1 = (q0[0] + dirX * L * 0.45, q0[1] + L * up, q0[2] + dirZ * L * 0.45)
            q2 = (q0[0] + dirX * L * reach, q0[1] + L * tipY, q0[2] + dirZ * L * reach)
            pts = []
            ok = True
            for sg in range(1, 9):
                if not ok:                     # the JS loop condition: sg <= 8 && ok
                    break
                t, s2 = sg / 8, 1 - sg / 8
                px = s2 * s2 * q0[0] + 2 * s2 * t * q1[0] + t * t * q2[0]
                py = s2 * s2 * q0[1] + 2 * s2 * t * q1[1] + t * t * q2[1]
                pz = s2 * s2 * q0[2] + 2 * s2 * t * q1[2] + t * t * q2[2]
                hw = (L * 0.092) * (0.30 + 1.15 * math.pow(math.sin(min(math.pi, t * math.pi * 1.05)), 0.65))
                for c in caps:
                    if dist_pt_seg(px, py, pz, c) < c['r'] + hw * 0.5:
                        ok = False
                        break
                    if c['cr'] and _hyp(px - c['cx'], py - c['cy'], pz - c['cz']) < c['cr'] + hw * 0.4:
                        ok = False
                        break
                if not ok:
                    break
                for pl in placed:
                    for q in pl:
                        dy = py - q[1]
                        if dy > 0.28 or dy < -0.28:
                            continue
                        if _hyp(px - q[0], dy, pz - q[2]) < (hw + q[3]) * 0.55:
                            ok = False
                            break
                    if not ok:
                        break
                pts.append((px, py, pz, hw))   # (pushed even when a placed blade failed it, as the JS does)
            if ok or tries == 7:
                best = {'yaw': yaw, 'up': up, 'reach': reach, 'tipY': tipY, 'L': L, 'pts': pts}
            tries += 1
        placed.append(best['pts'])
        leaf(f, best['yaw'], best['L'], best['L'] * 0.092 * rng.range(0.9, 1.1), best['up'], best['reach'], best['tipY'])

    # ── ear(s): husked spindle at a mid node; peel stands the cob up bare ──
    HUSK = {'v0': 0.505, 'v1': 0.693, 'u0': 0.03, 'u1': 0.97}

    def basis_from(ax, ay, az):
        s1x, s1y, s1z = -az, 0.0, ax
        ln = _hyp(s1x, s1y, s1z) or 1
        s1x, s1z = s1x / ln, s1z / ln
        return (s1x, s1y, s1z, ay * s1z - az * s1y, az * s1x - ax * s1z, ax * s1y - ay * s1x)

    def cob(bx, by, bz, ax, ay, az, ln, aE):
        s1x, s1y, s1z, s2x, s2y, s2z = basis_from(ax, ay, az)
        RADC, t1 = 10, 0.985
        rows = []
        for si in COB_STA:
            t, r0 = COB_PROF[si]
            r, row = r0 * ln, []
            cx, cy, cz = bx + ax * t * ln, by + ay * t * ln, bz + az * t * ln
            u = 0.015 + (t / t1) * (0.46 - 0.015)
            for j in range(RADC + 1):
                a = (j / RADC) * TAU
                ox, oy, oz = (s1x * math.cos(a) + s2x * math.sin(a), s1y * math.cos(a) + s2y * math.sin(a),
                              s1z * math.cos(a) + s2z * math.sin(a))
                row.append(V(cx + ox * r, cy + oy * r, cz + oz * r, u, 0.710 + (j / RADC) * (0.990 - 0.710), aE))
            rows.append(row)
        for i in range(len(rows) - 1):
            for j in range(RADC):
                quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])
        for si, cu, cv, _cr, flip in ((0, 0.478, 0.93, 0.017, True), (len(COB_STA) - 1, 0.478, 0.97, 0.010, False)):
            row = rows[0 if si == 0 else len(rows) - 1]
            t = COB_PROF[COB_STA[0 if si == 0 else len(COB_STA) - 1]][0]
            c = V(bx + ax * t * ln, by + ay * t * ln, bz + az * t * ln, cu, cv, aE)
            for j in range(10):
                idx.extend((row[j + 1], row[j], c) if flip else (row[j], row[j + 1], c))

    def ear(e):
        f, yaw, peel = e['f'], e['yaw'], e['peel']
        sx, sy, sz = P(f)
        dirX, dirZ = math.cos(yaw), math.sin(yaw)
        lean = e['lean']
        ax, ay, az = dirX * math.sin(lean), math.cos(lean), dirZ * math.sin(lean)
        r = stalkR(f)
        bx, by, bz = sx + dirX * r * 0.35, sy - 0.02, sz + dirZ * r * 0.35
        ln = e['len']
        s1x, s1y, s1z, s2x, s2y, s2z = basis_from(ax, ay, az)
        aE = f * 0.8
        cobLen = ln * 0.95

        def cobR(t):
            tc = min(0.985, max(0, t))
            for i in range(1, len(COB_PROF)):
                if COB_PROF[i][0] >= tc:
                    ta, ra = COB_PROF[i - 1]
                    tb, rb = COB_PROF[i]
                    return (ra + (rb - ra) * ((tc - ta) / ((tb - ta) or 1))) * cobLen
            return COB_PROF[-1][1] * cobLen

        def radial(th):
            return (s1x * math.cos(th) + s2x * math.sin(th), s1y * math.cos(th) + s2y * math.sin(th),
                    s1z * math.cos(th) + s2z * math.sin(th))
        nH = 3 if peel else 5
        th0s = []
        if peel:
            acc = R() * TAU
            for _ in range(nH):
                th0s.append(acc)
                acc += rng.range(1.6, 2.6)
        else:
            for k2 in range(nH):
                th0s.append((k2 / nH) * TAU + R() * 0.5)

        def nrm(a):
            return math.fmod(math.fmod(a, TAU) + TAU, TAU)
        srt = sorted(nrm(a) for a in th0s)

        def arc_for(th):
            i = srt.index(nrm(th))
            nxt, prv = srt[(i + 1) % len(srt)], srt[(i - 1 + len(srt)) % len(srt)]
            gN = nrm(nxt - srt[i]) or TAU
            gP = nrm(srt[i] - prv) or TAU
            return min(1.95, max(0.9, 0.65 * max(gN, gP)))
        for k in range(nH):
            th0 = th0s[k]
            twist = rng.vary(0.35, 0.1)
            halfArc = arc_for(th0)
            wrapTop = rng.range(0.4, 0.5) if peel else rng.range(0.98, 1.04)
            lift = 0.004 + k * 0.0016
            sA = st['vb']
            rows2 = 0
            vMidH, vSpanH = (HUSK['v0'] + HUSK['v1']) / 2, (HUSK['v1'] - HUSK['v0']) / 2 - 0.02
            COLS = [(-1, -vSpanH), (-0.5, -vSpanH * 0.5), (0, 0), (0.5, vSpanH * 0.5), (1, vSpanH)]

            def emit_wrap_row(t, uFrac, pad=0.0):
                th = th0 + twist * max(0, t)
                u = HUSK['u0'] + uFrac * (HUSK['u1'] - HUSK['u0'])
                for kk, dv in COLS:
                    ox, oy, oz = radial(th + kk * halfArc)
                    rr = max(0.004, cobR(t)) + lift + pad + (1 - abs(kk)) * 0.003
                    V(bx + ax * t * cobLen + ox * rr, by + ay * t * cobLen + oy * rr, bz + az * t * cobLen + oz * rr,
                      u, vMidH + dv, aE)
            wrapSegs = 5
            rowTs = [-0.03 + (wrapTop + 0.03) * (sg / wrapSegs) for sg in range(wrapSegs + 1)]

            def seg_pad(ta, tb):
                d = 0.0
                for m in range(1, 5):
                    tm = ta + (tb - ta) * (m / 5)
                    d = max(d, cobR(tm) - (cobR(ta) + (cobR(tb) - cobR(ta)) * (m / 5)))
                return d
            for sg in range(wrapSegs + 1):
                t = rowTs[sg]
                padA = seg_pad(rowTs[sg - 1], t) if sg > 0 else 0
                padB = seg_pad(t, rowTs[sg + 1]) if sg < wrapSegs else 0
                emit_wrap_row(t, 0.05 + 0.5 * (sg / wrapSegs), max(padA, padB))
                rows2 += 1
            if peel:
                thR = th0 + twist * wrapTop
                ox, oy, oz = radial(thR)
                rimR = cobR(wrapTop) + lift
                px, py, pz = (bx + ax * wrapTop * cobLen + ox * rimR, by + ay * wrapTop * cobLen + oy * rimR,
                              bz + az * wrapTop * cobLen + oz * rimR)
                cL = ln * rng.range(0.38, 0.55)
                c1 = (px + ax * cL * 0.38 + ox * cL * 0.06, py + ay * cL * 0.38 + oy * cL * 0.06, pz + az * cL * 0.38 + oz * cL * 0.06)
                c2 = (px + ox * cL * 0.62 + ax * cL * 0.1, py + oy * cL * 0.62 + ay * cL * 0.1, pz + oz * cL * 0.62 + az * cL * 0.1)
                ce = (px + ox * cL * 0.6 - ax * cL * 0.55, py + oy * cL * 0.6 - ay * cL * 0.55 - cL * rng.range(0.1, 0.3),
                      pz + oz * cL * 0.6 - az * cL * 0.55)
                tx2 = s2x * math.cos(thR) - s1x * math.sin(thR)
                ty2 = s2y * math.cos(thR) - s1y * math.sin(thR)
                tz2 = s2z * math.cos(thR) - s1z * math.sin(thR)
                w0 = halfArc * rimR
                for sg2 in range(1, 8):
                    t2 = sg2 / 7
                    s0b = 1 - t2
                    c = tuple(s0b ** 3 * pp + 3 * s0b * s0b * t2 * a1 + 3 * s0b * t2 * t2 * a2 + t2 ** 3 * a3
                              for pp, a1, a2, a3 in zip((px, py, pz), c1, c2, ce))
                    w = w0 * (1 - t2 * 0.55) * (1 + 0.1 * math.sin(t2 * 7.0 + k * 2.1)) * (1 - math.pow(t2, 5) * 0.85)
                    cup = w * 0.55 * (0.3 + t2 * 0.7)
                    u = HUSK['u0'] + (0.55 + 0.42 * t2) * (HUSK['u1'] - HUSK['u0'])
                    for kk, dv in COLS:
                        bend = (1 - kk * kk) * cup
                        V(c[0] + tx2 * w * kk + ox * bend, c[1] + ty2 * w * kk + oy * bend, c[2] + tz2 * w * kk + oz * bend,
                          u, vMidH + dv, aE)
                    rows2 += 1
            for sg in range(rows2 - 1):
                a2 = sA + sg * 5
                b2 = a2 + 5
                for cq in range(4):
                    quad(a2 + cq, a2 + cq + 1, b2 + cq + 1, b2 + cq)
            if not peel:
                tipT = 1.08 + R() * 0.12
                th = th0 + twist * tipT
                ox, oy, oz = radial(th)
                apex = V(bx + ax * tipT * cobLen + ox * 0.004, by + ay * tipT * cobLen + oy * 0.004,
                         bz + az * tipT * cobLen + oz * 0.004, HUSK['u0'] + 0.97 * (HUSK['u1'] - HUSK['u0']),
                         (HUSK['v0'] + HUSK['v1']) / 2, aE)
                last_row = sA + (rows2 - 1) * 5
                for cq in range(4):
                    idx.extend((last_row + cq, last_row + cq + 1, apex))
        if peel:
            cob(bx, by, bz, ax, ay, az, cobLen, aE)
        stt = 1.02 if peel else 1.16
        stx, sty, stz = bx + ax * stt * cobLen, by + ay * stt * cobLen, bz + az * stt * cobLen
        for _ in range(4):
            a0 = R() * TAU
            hw2 = rng.range(0.004, 0.007)
            bX, bZ = math.cos(a0), math.sin(a0)
            sL = rng.range(0.05, 0.085)
            vMid = 0.875 + R() * 0.1
            for wx, wy, wz in ((-math.sin(a0) * hw2, 0, math.cos(a0) * hw2),
                               (math.cos(a0) * hw2 * 0.5, hw2 * 0.85, math.sin(a0) * hw2 * 0.5)):
                sA = st['vb']
                for sg in range(4):
                    t = sg / 3
                    rise, out, drop = sL * 0.6 * t, sL * 0.95 * t * t, sL * 0.7 * t * t * t
                    cx2, cy2, cz2 = stx + ax * rise + bX * out, sty + ay * rise - drop, stz + az * rise + bZ * out
                    u = 0.72 + t * 0.275
                    V(cx2 - wx, cy2 - wy, cz2 - wz, u, vMid - 0.025, aE)
                    V(cx2 + wx, cy2 + wy, cz2 + wz, u, vMid + 0.025, aE)
                for sg in range(3):
                    a2 = sA + sg * 2
                    quad(a2, a2 + 1, a2 + 3, a2 + 2)
    for e in ear_specs:
        ear(e)

    # ── tassel: sparse strand-branch crown over a short spike ──
    tx, ty, tz = P(1)
    spikeH = rng.range(0.09, 0.13)
    s0, RADS = st['vb'], 4
    for gg in range(3):
        t = gg / 2
        r = 0.006 * (1 - t * 0.7)
        for j in range(RADS + 1):
            a = (j / RADS) * TAU
            V(tx + math.cos(a) * r, ty + spikeH * t, tz + math.sin(a) * r, 0.03 + 0.94 * _tri((j / RADS) * 2),
              0.19 - t * 0.05, 0.82 + t * 0.1)
    for gg in range(2):
        for j in range(RADS):
            quad(s0 + gg * (RADS + 1) + j, s0 + gg * (RADS + 1) + j + 1, s0 + (gg + 1) * (RADS + 1) + j + 1,
                 s0 + (gg + 1) * (RADS + 1) + j)
    nB = 6
    for k in range(nB):
        t01 = k / (nB - 1)
        yaw = k * 2.4 + R() * 0.5
        pitch = 0.12 + t01 * 0.75 + R() * 0.1
        bl = rng.range(0.16, 0.26) * (1 - t01 * 0.25)
        hw = rng.range(0.011, 0.02)
        dx, dyy, dz = math.cos(yaw) * math.sin(pitch), math.cos(pitch), math.sin(yaw) * math.sin(pitch)
        px2, pz2 = -math.sin(yaw), math.cos(yaw)
        hF = rng.range(0.35, 0.95)
        by2 = ty + spikeH * hF
        aB = 0.82 + hF * 0.1
        vMid = 0.725 + R() * 0.22
        for wxx, wyy, wzz in ((px2 * hw, 0, pz2 * hw), (dx * 0, hw * 0.9, dz * 0)):
            sA = st['vb']
            for sg in range(4):
                t = sg / 3
                arc = t * t * bl * 0.55
                cx2, cy2, cz2 = tx + dx * bl * t + dx * arc * 0.4, by2 + dyy * bl * t - arc, tz + dz * bl * t + dz * arc * 0.4
                u = 0.7 + t * 0.295
                a = min(1, aB + t * 0.1)
                V(cx2 - wxx, cy2 - wyy, cz2 - wzz, u, vMid - 0.025, a)
                V(cx2 + wxx, cy2 + wyy, cz2 + wzz, u, vMid + 0.025, a)
            for sg in range(3):
                a = sA + sg * 2
                quad(a, a + 1, a + 3, a + 2)

    Pp = np.array(pos)
    T = np.array(idx).reshape(-1, 3)
    geo = PlantGeo(Pp, uv, aH, T, vertex_normals(Pp, T))
    geo.stats = {'verts': st['vb'], 'tris': len(T)}
    return {'geo': geo, 'stats': geo.stats}
