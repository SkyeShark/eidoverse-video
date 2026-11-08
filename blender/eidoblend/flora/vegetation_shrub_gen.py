"""vegetation_shrub_gen: SeedThree's dichotomous plant math for the three Mojave shrubs (blackbrush, creosote,
sagebrush), ported line for line from eidoverse/vegetation_shrub_gen.js on three.js r184 semantics (three_math), so
a seed grows the same shrub in both editions.

Skeleton: a stochastic L-system (F -> F[+F][-F]) of short bent segments forking low from a multi-stem root crown,
with tropism, elbow bend, gnarliness, branch repel and crown clearance. Wood: ONE welded tube network (the parent's
last ring stitched to each child's first ring), parallel-transported rings, bark-grain UVs, cone caps, shading normals
welded over coincident positions. Foliage: base-anchored crossed spray cards on the terminal (and sub-terminal)
stems, with phyllotaxy, down-angle and droop, the sheet's measured art alignment baked in (shrub_anchors.json), and
spherical bent normals so the crown shades as one volume.
"""
import math

import numpy as np

from .jsmath import Rng, js_round
from .plantgeo import PlantGeo, vertex_normals
from .three_math import Vec3, Quat

UP = Vec3(0, 1, 0)
Y = Vec3(0, 1, 0)
X = Vec3(1, 0, 0)
DOWN = Vec3(0, -1, 0)
GOLDEN = (137.5 * math.pi) / 180

DEFAULTS = {
    'firstForkHeight': 1.6, 'armLength': 0.9, 'armFalloff': 0.86, 'forkGenerations': 6, 'branchiness': 0.62,
    'forkSpread': 32, 'forkTriChance': 0.15, 'curlUp': 0.35, 'armBend': 16, 'gnarliness': 12, 'continuationKink': 8,
    'forkRadiusKeep': 0.86, 'forkBaseScale': 1.0, 'trunkRadius': 0.16, 'trunkFlare': 1.7, 'trunkSegRes': 9,
    'branchRepel': 0.7, 'tipClearance': 0, 'minRadius': 0.02, 'radialSegs': 10, 'segCurveRes': 4, 'trunks': 1,
    'trunkSplayDeg': 14, 'tileWorldSize': 0.8,
}


def tropism(d, amount):
    if amount <= 0:
        return d
    dt = max(-1.0, min(1.0, d.dot(UP)))
    decl = math.acos(dt)
    if decl < 1e-4:
        return d
    axis = Vec3().crossVectors(d, UP)
    if axis.lengthSq() < 1e-8:
        return d
    axis.normalize()
    return d.clone().applyAxisAngle(axis, amount * decl).normalize()


def tropism_in_place(d, amount):
    d.copy(tropism(d, amount))


def perp(d):
    a = UP if abs(d.y) < 0.9 else X
    return Vec3().crossVectors(d, a).normalize()


def grow_segment(origin, dir0, length, radius0, radius1, p, rng, res_override=None):
    res = max(1, res_override if res_override is not None else p['segCurveRes'])
    points = [origin.clone()]
    radii = [radius0]
    d = dir0.clone().normalize()
    pos = origin.clone()
    bend_per = ((p['armBend'] + rng.vary(0, p['gnarliness'])) * math.pi) / 180 / res
    bend_axis = perp(d)
    for i in range(1, res + 1):
        d.applyAxisAngle(bend_axis, bend_per)
        if p['gnarliness'] > 0:
            d.applyAxisAngle(perp(d), (rng.vary(0, p['gnarliness']) * math.pi) / 180 / res)
        tropism_in_place(d, p['curlUp'] / res)
        pos.addScaledVector(d, length / res)
        points.append(pos.clone())
        radii.append(radius0 + (radius1 - radius0) * (i / res))
    return {'points': points, 'radii': radii, 'endDir': d.clone().normalize()}


def frames_for(points):
    orients, tangents = [], []
    n = len(points)
    for i in range(n):
        t = Vec3()
        if i == 0:
            t.subVectors(points[1], points[0])
        elif i == n - 1:
            t.subVectors(points[n - 1], points[n - 2])
        else:
            t.subVectors(points[i + 1], points[i - 1])
        t.normalize()
        tangents.append(t)
        orients.append(Quat().setFromUnitVectors(Y, t))
    return orients, tangents


def make_stem(seg, level, wind_base, flex_gain):
    orients, _ = frames_for(seg['points'])
    n = len(seg['points'])
    winds = [min(1, wind_base + flex_gain * math.pow(i / (n - 1) if n > 1 else 0, 1.15)) for i in range(n)]
    return {'points': seg['points'], 'radii': seg['radii'], 'orients': orients, 'winds': winds,
            'level': level, 'terminal': False, 'children': []}


def generate_shrub_skeleton(user_params, rng):
    p = dict(DEFAULTS)
    p.update(user_params)
    stems, terminal_stems = [], []
    all_pts, tips = [], []

    def repel_dir(pos, d, length):
        strength = p.get('branchRepel') or 0
        if strength <= 0:
            return d
        clr = p.get('tipClearance') or 0
        probe = pos.clone().addScaledVector(d, length * 0.8)
        reach = length * 0.6 + clr
        R2, near2 = reach ** 2, (length * 0.5) ** 2
        rep = Vec3()
        for pt in all_pts:
            if pt.distanceToSquared(pos) < near2:
                continue
            dsq = probe.distanceToSquared(pt)
            if R2 > dsq > 1e-4:
                rep.add(Vec3().subVectors(probe, pt).multiplyScalar(1 / dsq))
        crown_gap2 = (clr * 1.7) ** 2
        for t in tips:
            if t.distanceToSquared(pos) < near2:
                continue
            dsq = probe.distanceToSquared(t)
            if crown_gap2 > dsq > 1e-4:
                rep.add(Vec3().subVectors(probe, t).multiplyScalar(crown_gap2 / dsq))
        if rep.lengthSq() < 1e-8:
            return d
        return d.clone().addScaledVector(rep.normalize(), strength).normalize()

    def grow(origin, d, radius, length, depth, level, wind_base, flare_base, base_is_fork=False, is_ground_base=False):
        flex_gain = [0.3, 0.4, 0.5, 0.55][min(level, 3)]
        r1 = max(p['minRadius'], radius * 0.96)
        seg = grow_segment(origin, d, length, radius, r1, p, rng, (p.get('trunkSegRes') or 9) if level == 0 else None)
        if flare_base:
            nr = len(seg['radii'])
            for i in range(nr):
                z = i / (nr - 1)
                if z < 0.4:
                    seg['radii'][i] = flare_base * (1 - z / 0.4) + seg['radii'][i] * (z / 0.4)
        if level == 0 and is_ground_base and (p.get('trunkFlare') or 0) > 0:
            nr = len(seg['radii'])
            for i in range(nr):
                z = i / (nr - 1)
                flare = 1 + p['trunkFlare'] * (1 - z / 0.35) if z < 0.35 else 1
                amp = 0.10 + 0.16 * (1 - z)
                und = 1 + amp * (math.sin(z * 8.3) * 0.6 + math.sin(z * 21.7 + 1.9) * 0.4)
                seg['radii'][i] *= flare * und
        stem = make_stem(seg, level, wind_base, flex_gain)
        stem['baseIsFork'] = base_is_fork
        stems.append(stem)
        all_pts.extend(seg['points'])
        end_pos = seg['points'][-1]
        end_dir = seg['endDir']
        end_radius = seg['radii'][-1]
        wind_tip = min(1, wind_base + flex_gain)
        if depth <= 1:
            stem['terminal'] = True
            terminal_stems.append(stem)
            tips.append(end_pos.clone())
            return stem
        if rng.next() < p['branchiness']:
            nc = 3 if rng.next() < p['forkTriChance'] else 2
            plane_az = rng.range(0, math.pi * 2)
            axis = perp(end_dir)
            child_r = max(p['minRadius'], end_radius * p['forkRadiusKeep'])
            child_len = p['armLength'] if level == 0 else length * p['armFalloff']
            for k in range(nc):
                az = plane_az + (k * math.pi * 2) / nc
                spin = Quat().setFromAxisAngle(end_dir, az)
                tilt_axis = axis.clone().applyQuaternion(spin)
                spread = ((p['forkSpread'] + rng.vary(0, 6)) * math.pi) / 180
                cdir = end_dir.clone().applyAxisAngle(tilt_axis, spread).normalize()
                cdir = repel_dir(end_pos, cdir, child_len)
                stem['children'].append(grow(end_pos, cdir, child_r, child_len, depth - 1, level + 1, wind_tip,
                                             end_radius * (p.get('forkBaseScale') if p.get('forkBaseScale') is not None else 1), nc >= 2))
        else:
            cdir = end_dir.clone()
            kink = p.get('continuationKink') if p.get('continuationKink') is not None else 8
            cdir.applyAxisAngle(perp(cdir), (rng.vary(0, kink) * math.pi) / 180).normalize()
            cdir = repel_dir(end_pos, tropism(cdir, p['curlUp'] * 0.4), length)
            stem['children'].append(grow(end_pos, cdir, end_radius * 0.98, length, depth - 1, level, wind_tip, end_radius, False))
        return stem

    trunk_len = p['firstForkHeight']
    n_trunks = max(1, int(p['trunks']))
    for t in range(n_trunks):
        d = UP.clone()
        if n_trunks > 1:
            az = (math.pi * 2 * t) / n_trunks
            d.applyAxisAngle(X, (p['trunkSplayDeg'] * math.pi) / 180).applyAxisAngle(UP, az).normalize()
        grow(Vec3(0, 0, 0), d, p['trunkRadius'], trunk_len, p['forkGenerations'], 0, 0.05, 0, False, True)
    return stems, terminal_stems, p


def _ring_vertices(center, tangent, ref_dir, radius, seg, uv_y, u_scale, out, prev_tangent=None):
    n = Vec3().copy(ref_dir)
    if prev_tangent is not None:
        dt = max(-1.0, min(1.0, prev_tangent.dot(tangent)))
        if dt < 0.999999:
            ax = Vec3().crossVectors(prev_tangent, tangent)
            if ax.lengthSq() > 1e-12:
                n.applyAxisAngle(ax.normalize(), math.acos(dt))
    n.addScaledVector(tangent, -n.dot(tangent))
    if n.lengthSq() < 1e-8:
        n.copy(perp(tangent))
    n.normalize()
    b = Vec3().crossVectors(n, tangent).normalize()
    for j in range(seg + 1):
        a = (j / seg) * math.pi * 2
        d = Vec3().copy(n).multiplyScalar(math.cos(a)).addScaledVector(b, math.sin(a))
        out['pos'].append((center.x + d.x * radius, center.y + d.y * radius, center.z + d.z * radius))
        out['nrm'].append((d.x, d.y, d.z))
        out['uv'].append((uv_y, (j / seg) * u_scale) if out['grainU'] else ((j / seg) * u_scale, uv_y))
        out['wind'].append(0.0)
    return n


def build_wood_mesh(stems, params):
    p = dict(DEFAULTS)
    p.update(params)
    rs = p.get('radialSegs')
    p['radialSegs'] = max(3, js_round(rs if isinstance(rs, (int, float)) and math.isfinite(rs) else 3))
    seg = p['radialSegs']
    ring_len = seg + 1
    out = {'pos': [], 'nrm': [], 'uv': [], 'wind': [], 'idx': [], 'grainU': p.get('barkGrainU') is not False}
    P = out['pos']

    def dsq(i, k):
        a, b = P[i], P[k]
        dx, dy, dz = a[0] - b[0], a[1] - b[1], a[2] - b[2]
        return dx * dx + dy * dy + dz * dz

    def stitch(a, b):
        for j in range(seg):
            a0, a1, b0, b1 = a + j, a + j + 1, b + j, b + j + 1
            if dsq(a1, b0) <= dsq(a0, b1):
                out['idx'].extend((a0, b0, a1, a1, b0, b1))
            else:
                out['idx'].extend((a0, b0, b1, a0, b1, a1))

    def emit_stem(stem, ref_dir0, vY0, tan0=None):
        _, tangents = frames_for(stem['points'])
        if tan0 is not None:
            tangents[0] = tan0.clone()
        ref = ref_dir0.clone()
        vY = vY0
        rings = []
        radii = stem['radii']
        ref_idx = min(len(radii) - 1, math.floor(len(radii) * 0.5))
        circ_ref = 2 * math.pi * radii[ref_idx]
        wraps = circ_ref / p['tileWorldSize']
        u_scale = max(1, js_round(wraps)) if wraps >= 0.75 else wraps
        tile_v = max(0.02, circ_ref / max(u_scale, 1e-4))
        pts = stem['points']
        for i in range(len(pts)):
            base = len(out['pos'])
            if i > 0:
                vY += pts[i].distanceTo(pts[i - 1]) / tile_v
            ref = _ring_vertices(pts[i], tangents[i], ref, radii[i], seg, vY, u_scale, out, tangents[i - 1] if i > 0 else None)
            for j in range(ring_len):
                out['wind'][len(out['wind']) - ring_len + j] = stem['winds'][i]
            rings.append(base)
            if i > 0:
                stitch(rings[i - 1], base)
        last_base = rings[-1]
        last_tan = tangents[-1]
        for child in stem['children']:
            is_cont = child['level'] == stem['level']
            first = emit_stem(child, ref, vY, last_tan if is_cont else None)
            stitch(last_base, first)
        if not stem['children']:
            cap_r = radii[-1]
            cap_c = pts[-1]
            cap_wind = stem['winds'][-1]
            aC = cap_c.clone().addScaledVector(last_tan, cap_r * 1.2)
            apex_base = len(out['pos'])
            apex_vy = vY + (cap_r * 1.2) / tile_v
            for j in range(seg + 1):
                out['pos'].append((aC.x, aC.y, aC.z))
                out['nrm'].append((last_tan.x, last_tan.y, last_tan.z))
                out['uv'].append((apex_vy, (j / seg) * u_scale) if out['grainU'] else ((j / seg) * u_scale, apex_vy))
                out['wind'].append(cap_wind)
            stitch(last_base, apex_base)
        return rings[0]

    child_ids = {id(c) for s in stems for c in s['children']}
    for s in stems:
        if id(s) in child_ids:
            continue
        t0 = Vec3().subVectors(s['points'][1], s['points'][0]).normalize()
        emit_stem(s, perp(t0), 0)

    pos = np.array(out['pos'], dtype=np.float64)
    tris = np.array(out['idx'], dtype=np.int64).reshape(-1, 3)
    aH = np.array(out['wind']) * 0.3
    p32 = pos.astype(np.float32).astype(np.float64)        # the JS reads its Float32Array back
    nrm = vertex_normals(p32, tris)
    # weld shading normals across coincident positions (fork joints, U-wrap seam)
    keys = np.floor(p32 * 1e4 + 0.5).astype(np.int64)
    _, inv = np.unique(keys, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    acc = np.zeros((inv.max() + 1, 3))
    np.add.at(acc, inv, nrm)
    cnt = np.bincount(inv)
    ln = np.linalg.norm(acc, axis=1, keepdims=True)
    ln[ln == 0] = 1
    welded = (acc / ln)[inv]
    nrm = np.where((cnt[inv] >= 2)[:, None], welded, nrm)
    return PlantGeo(pos, out['uv'], aH, tris, nrm)


CARD_DEFAULTS = {
    'sizeVar': 0.3, 'taper': 0.25, 'startFrac': 0.35, 'downAngle': 52, 'downAngleV': 18, 'droop': 22, 'droopV': 12,
    'clustersPerBranch': 3, 'clusterSize': 1.3, 'clusterSizeVar': 0.3, 'clusterQuads': 2,
}


def _card_template(quads, anchor):
    base = [(-0.5, 0), (0.5, 0), (0.5, 1), (-0.5, 1)]
    uvb = [(0, 0), (1, 0), (1, 1), (0, 1)]
    roll = (anchor['rollDeg'] * math.pi) / 180 if anchor else 0
    du = -(anchor['u'] - 0.5) if anchor else 0
    cr, sr = math.cos(roll), math.sin(roll)
    pos, nrm, uv, idx = [], [], [], []
    b = 0
    for q in range(quads):
        a = (q * math.pi) / quads
        ca, sa = math.cos(a), math.sin(a)
        for i in range(4):
            x, y = base[i]
            x += du
            xr, yr = x * cr - y * sr, x * sr + y * cr
            pos.append((xr * ca, yr, xr * sa))
            nrm.append((-sa, 0.0, ca))
            uv.append(uvb[i])
        idx.extend((b, b + 1, b + 2, b, b + 2, b + 3))
        b += 4
    return pos, nrm, uv, idx


def bake_spray_cards(terminal_stems, parent_stems, cfg_in, rng, anchor):
    c_in = dict(CARD_DEFAULTS)
    c_in.update(cfg_in)
    c = dict(c_in, perBranch=c_in['clustersPerBranch'], size=c_in['clusterSize'], sizeVar=c_in['clusterSizeVar'],
             quads=c_in['clusterQuads'], startFrac=cfg_in.get('startFrac', 0.35))
    if not terminal_stems or c['perBranch'] <= 0:
        return None
    tpos, tnrm, tuv, tidx = _card_template(c['quads'], anchor)
    vmin = anchor['vmin'] if anchor and anchor.get('vmin') is not None else 0.05
    pos, uv, aH, idx = [], [], [], []
    vb = 0
    min_y, max_y = math.inf, -math.inf
    jobs = [(terminal_stems, c['perBranch'], 1)]
    parent_per = js_round(c['perBranch'] * (c_in.get('parentSprays') or 0))
    if parent_stems and parent_per > 0:
        jobs.append((parent_stems, parent_per, 0.85))
    q, q_frame, q1, q2, qb = Quat(), Quat(), Quat(), Quat(), Quat()
    for (lst, per, size_mul) in jobs:
        for stem in lst:
            pts, oris = stem['points'], stem['orients']
            seg_n = len(pts) - 1
            phyllo = rng.range(0, math.pi * 2)
            for i in range(per):
                frac = c['startFrac'] + (1 - c['startFrac']) * ((i + rng.next()) / per)
                fseg = min(seg_n - 1, math.floor(frac * seg_n))
                ft = frac * seg_n - fseg
                pA = pts[fseg].clone().lerp(pts[fseg + 1], ft)
                q_frame.copy(oris[fseg]).slerp(oris[fseg + 1], ft)
                w_anchor = stem['winds'][fseg] * (1 - ft) + stem['winds'][fseg + 1] * ft if stem.get('winds') else 0.9
                phyllo += GOLDEN + rng.vary(0, 0.3)
                q2.setFromAxisAngle(Y, phyllo)
                down = ((c['downAngle'] + rng.vary(0, c['downAngleV'])) * math.pi) / 180
                q1.setFromAxisAngle(X, down)
                q.copy(q_frame).multiply(q2).multiply(q1)
                if c['droop'] > 0:
                    n = Vec3(0, 1, 0).applyQuaternion(q)
                    droop_axis = Vec3().crossVectors(n, DOWN)
                    if droop_axis.lengthSq() > 1e-6:
                        droop_axis.normalize()
                        qb.setFromAxisAngle(droop_axis, ((c['droop'] + rng.vary(0, c['droopV'])) * math.pi) / 180)
                        q.premultiply(qb)
                s = c['size'] * size_mul * (1 - c['taper'] * frac) * (1 + rng.vary(0, c['sizeVar']))
                card_y = Vec3(0, 1, 0).applyQuaternion(q)
                org = pA.clone().addScaledVector(card_y, -(vmin * s + 0.015))
                s0 = vb
                for v in range(len(tpos)):
                    tp = tpos[v]
                    vtx = Vec3(tp[0] * s, tp[1] * s, tp[2] * s).applyQuaternion(q).add(org)
                    pos.append((vtx.x, vtx.y, vtx.z))
                    uv.append(tuv[v])
                    t_local = max(0.0, min(1.0, tp[1]))
                    aH.append(w_anchor * 0.3 + t_local * 0.45)
                    min_y, max_y = min(min_y, vtx.y), max(max_y, vtx.y)
                    vb += 1
                idx.extend(s0 + ix for ix in tidx)
    if not pos:
        return None
    P = np.array(pos)
    cy = min_y + (max_y - min_y) * 0.45
    bent = P - np.array([0.0, cy, 0.0])
    ln = np.linalg.norm(bent, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return PlantGeo(P, uv, aH, np.array(idx).reshape(-1, 3), bent / ln)


SHRUB_GEN = {
    'creosote': {
        'params': {'trunks': 5, 'trunkSplayDeg': 38, 'firstForkHeight': 0.12, 'armLength': 0.55, 'armFalloff': 0.85,
                   'forkGenerations': 4, 'branchiness': 0.78, 'forkSpread': 30, 'forkTriChance': 0.1, 'curlUp': 0.15,
                   'armBend': 12, 'gnarliness': 14, 'continuationKink': 10, 'forkRadiusKeep': 0.78,
                   'trunkRadius': 0.022, 'trunkFlare': 1.2, 'branchRepel': 0.6, 'minRadius': 0.004, 'radialSegs': 4,
                   'segCurveRes': 2, 'trunkSegRes': 3, 'tileWorldSize': 0.5, 'barkGrainU': True},
        'foliage': {'clustersPerBranch': 8, 'clusterSize': 0.58, 'clusterSizeVar': 0.35, 'clusterQuads': 2,
                    'downAngle': 24, 'downAngleV': 12, 'droop': 14, 'startFrac': 0.22, 'parentSprays': 0.5},
    },
    'blackbrush': {
        'params': {'trunks': 6, 'trunkSplayDeg': 42, 'firstForkHeight': 0.08, 'armLength': 0.32, 'armFalloff': 0.82,
                   'forkGenerations': 4, 'branchiness': 0.85, 'forkSpread': 34, 'forkTriChance': 0.12, 'curlUp': 0.1,
                   'armBend': 14, 'gnarliness': 22, 'continuationKink': 14, 'forkRadiusKeep': 0.76,
                   'trunkRadius': 0.015, 'trunkFlare': 1.15, 'branchRepel': 0.5, 'minRadius': 0.0035, 'radialSegs': 4,
                   'segCurveRes': 2, 'trunkSegRes': 3, 'tileWorldSize': 0.4, 'barkGrainU': False},
        'foliage': {'clustersPerBranch': 3, 'clusterSize': 0.5, 'clusterSizeVar': 0.3, 'clusterQuads': 2,
                    'downAngle': 32, 'downAngleV': 14, 'droop': 16, 'startFrac': 0.2, 'parentSprays': 0.6},
    },
    'sagebrush': {
        'params': {'trunks': 3, 'trunkSplayDeg': 26, 'firstForkHeight': 0.15, 'armLength': 0.36, 'armFalloff': 0.86,
                   'forkGenerations': 4, 'branchiness': 0.8, 'forkSpread': 24, 'forkTriChance': 0.08, 'curlUp': 0.28,
                   'armBend': 10, 'gnarliness': 10, 'continuationKink': 8, 'forkRadiusKeep': 0.78,
                   'trunkRadius': 0.02, 'trunkFlare': 1.15, 'branchRepel': 0.55, 'minRadius': 0.004, 'radialSegs': 5,
                   'segCurveRes': 2, 'trunkSegRes': 3, 'tileWorldSize': 0.45, 'barkGrainU': False},
        'foliage': {'clustersPerBranch': 3, 'clusterSize': 0.48, 'clusterSizeVar': 0.3, 'clusterQuads': 2,
                    'downAngle': 30, 'downAngleV': 12, 'droop': 10, 'startFrac': 0.15, 'parentSprays': 0.6},
    },
}


def build_shrub_geometry(name, seed, anchor):
    """One shrub -> {'leaf': PlantGeo, 'stem': PlantGeo, 'stats'} (three space)."""
    preset = SHRUB_GEN.get(name)
    if preset is None:
        raise ValueError(f"[shrub_gen] unknown shrub '{name}': have {', '.join(SHRUB_GEN)}")
    rng = Rng(f'{name}:{seed}')
    params = dict(preset['params'], tipClearance=(preset['foliage'].get('clusterSize') or 0.5) * 0.9)
    stems, terminal_stems, _ = generate_shrub_skeleton(params, rng)
    stem = build_wood_mesh(stems, params)
    term_ids = {id(s) for s in terminal_stems}
    parents = [s for s in stems if not s['terminal'] and any(id(ch) in term_ids for ch in s['children'])]
    leaf = bake_spray_cards(terminal_stems, parents, preset['foliage'], rng, anchor)
    return {'leaf': leaf, 'stem': stem, 'stats': {'stems': len(stems), 'terminals': len(terminal_stems),
                                                  'woodVerts': stem.nverts, 'leafVerts': leaf.nverts if leaf else 0}}
