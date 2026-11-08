"""eidoblend.sets.unknown_force.city: UNKNOWN FORCE's world, a dark cyberpunk megacity at night painted by a Futurist,
the Blender 5.2 EEVEE edition of eidoverse/sets/unknown_force/city.js.

A radial city around THE HOLE (hole.py): four grand avenues run in from the diagonals to the hole, four more start at
the first ring road, six ring roads circle it. Sant'Elia's stepped towers with external lift shafts, slabs with fins,
wedges with sloped tops, set-back skyscrapers; the inner towers lean toward the hole (the city bows to its centre:
every line runs to her). Lit windows are procedural per building, signs are canvas material on one mesh, the streets
are wet and mirror the neon, rain wraps the camera, a low rain-cloud deck hangs at 345-520 m and glows with the
city's light.

    from eidoblend.sets.unknown_force import city as C
    city = C.build()                                   # includes hole.py (the chorus stage) unless {'hole': False}
    city['parts']['apply_atmosphere'](scene)           # the World (the night sky, its hemisphere and environment)
    C.key_dive(camera, city['parts']['kit'], frame_start=1, fps=24)   # the intro, keyed (camera, time, focal, rain)

FRAME: the singer's mark (the bottom of the hole) is the origin; the streets are at z = STREET_Y (12 m). Poses and
focal points are in Blender axes; the layout code below works in three's axes, as citykit.py explains.
"""
from __future__ import annotations

import math

import numpy as np

from . import citykit as KIT
from .citykit import (STREET_Y, HOLE, AVENUES_MAIN, AVENUES_SECOND, AVENUE_W, SECOND_START, RINGS, CITY_R, FAR_R,
                      rng, hash1, smooth, smoother, lerp, clamp01, keyed, jround, apply_cam, cam_velocity)

try:
    import bpy
except ImportError:                    # pragma: no cover
    bpy = None

apply_camera = KIT.apply_cam

D2R = math.pi / 180
# the crossing the dive falls into: grand avenue 45 degrees x the first ring road (three's axes)
DIVE_AV = 45 * D2R
DIVE_C3 = [RINGS[0]['r'] * math.cos(DIVE_AV), STREET_Y, RINGS[0]['r'] * math.sin(DIVE_AV)]    # three's axes (city.js)
DIVE_C = KIT.to_blender(DIVE_C3)       # Blender axes, as every public position: (116.7, -116.7, 12)
PLAZA_R = 44.0                         # the open plaza at the dive's crossing (low pavilions only)
SUPERTALL_KEEPOUT = 170.0              # no supertall within this of the dive axis


# ------------------------------------------------------------------------------------------------ layout
def zone_list():
    """Zones between ring roads (radial): [{'i', 'r0', 'r1'}]."""
    edges = [{'r': HOLE['rim_tower'][1] + 4, 'w': 0.0}] + RINGS + [{'r': CITY_R, 'w': 0.0}]
    return [{'i': i, 'r0': edges[i]['r'] + edges[i]['w'] / 2 + 1, 'r1': edges[i + 1]['r'] - edges[i + 1]['w'] / 2 - 1}
            for i in range(len(edges) - 1)]


def zone_params(i):
    """Height range, lean toward the hole (degrees), block arc target (m), lit fraction, podium chance."""
    return [
        {'h': [110, 250], 'lean': 5.0, 'arc': 62, 'lit': [0.10, 0.26], 'pod': 0.9},
        {'h': [90, 230], 'lean': 3.4, 'arc': 70, 'lit': [0.09, 0.24], 'pod': 0.85},
        {'h': [60, 190], 'lean': 1.8, 'arc': 78, 'lit': [0.08, 0.22], 'pod': 0.8},
        {'h': [45, 160], 'lean': 0.8, 'arc': 84, 'lit': [0.07, 0.20], 'pod': 0.7},
        {'h': [35, 130], 'lean': 0.0, 'arc': 90, 'lit': [0.06, 0.18], 'pod': 0.6},
        {'h': [26, 110], 'lean': 0.0, 'arc': 96, 'lit': [0.05, 0.16], 'pod': 0.5},
        {'h': [20, 90], 'lean': 0.0, 'arc': 100, 'lit': [0.05, 0.15], 'pod': 0.4},
    ][min(i, 6)]


def sector_edges(r_mid):
    """Sectors between the avenues that exist at r_mid: [[a0, a1]] (radians, increasing, the last wraps)."""
    av = sorted(((a % (2 * math.pi)) + 2 * math.pi) % (2 * math.pi)
                for a in AVENUES_MAIN + (AVENUES_SECOND if r_mid >= SECOND_START else []))
    out = []
    for i, a in enumerate(av):
        b = av[i + 1] if i + 1 < len(av) else av[0] + 2 * math.pi
        out.append([a, b])
    return out


def plan_city(seed=1909):
    """Blocks (between minor streets) and lots (1..4 per block) in polar terms, plus the supertalls (300-420 m towers
    that pierce the cloud base, away from the dive): {'blocks', 'lots', 'supertalls'}."""
    R = rng(seed)
    blocks, lots = [], []
    for z in zone_list():
        P = zone_params(z['i'])
        depth = z['r1'] - z['r0']
        mid = (z['r0'] + z['r1']) / 2
        rows = [[z['r0'], mid - 4], [mid + 4, z['r1']]] if depth > 150 else [[z['r0'], z['r1']]]
        for ra, rb in rows:
            r_mid = (ra + rb) / 2
            for a0, a1 in sector_edges(r_mid):
                marg0 = math.asin(min(0.9, (AVENUE_W / 2 + 1) / ra))
                s0, s1 = a0 + marg0, a1 - marg0
                n = max(1, jround(r_mid * (s1 - s0) / P['arc']))
                alley = 5 / r_mid
                for k in range(n):
                    t0 = s0 + (s1 - s0) * k / n + (alley if k > 0 else 0)
                    t1 = s0 + (s1 - s0) * (k + 1) / n - (alley if k < n - 1 else 0)
                    blocks.append({'zone': z['i'], 'ra': ra, 'rb': rb, 't0': t0, 't1': t1})
                    ia, ib = ra + 4, rb - 4
                    tw = (t1 - t0) - 8 / r_mid
                    ti0 = t0 + 4 / r_mid
                    arc_w, dep = r_mid * tw, ib - ia
                    nt = 2 if arc_w > 70 else 1
                    nr = 2 if dep > 80 else 1
                    for i in range(nt):
                        for j in range(nr):
                            la0 = ti0 + tw * i / nt + (2 / r_mid if i > 0 else 0)
                            la1 = ti0 + tw * (i + 1) / nt - (2 / r_mid if i < nt - 1 else 0)
                            lr0 = ia + dep * j / nr + (2 if j > 0 else 0)
                            lr1 = ia + dep * (j + 1) / nr - (2 if j < nr - 1 else 0)
                            lots.append({'zone': z['i'], 'r0': lr0, 'r1': lr1, 't0': la0, 't1': la1, 'seed': R()})
    sup = []
    cand = [l for l in lots if 1 <= l['zone'] <= 4 and (l['r1'] - l['r0']) > 40]
    k = 0
    while k < 400 and len(sup) < 11:
        k += 1
        l = cand[math.floor(R() * len(cand))]
        rc, tc = (l['r0'] + l['r1']) / 2, (l['t0'] + l['t1']) / 2
        x, z = rc * math.cos(tc), rc * math.sin(tc)
        if math.hypot(x - DIVE_C3[0], z - DIVE_C3[2]) < SUPERTALL_KEEPOUT:
            continue
        if any(math.hypot(s['x'] - x, s['z'] - z) < 260 for s in sup):
            continue
        l['supertall'] = True
        sup.append({'x': x, 'z': z})
    return {'blocks': blocks, 'lots': lots, 'supertalls': sup}


# ------------------------------------------------------------------------------------------------ the building generator
STYLES = {
    'punched': {'fam': 'concrete', 'floorH': 3.6, 'bayW': 2.6, 'w': [0.24, 0.30, 0.80]},
    'ribbon': {'fam': 'metal', 'floorH': 3.8, 'bayW': 1.8, 'w': [0.03, 0.34, 0.82]},
    'curtain': {'fam': 'metal', 'floorH': 4.0, 'bayW': 1.5, 'w': [0.04, 0.10, 0.94]},
    'resid': {'fam': 'concrete', 'floorH': 3.1, 'bayW': 3.2, 'w': [0.30, 0.28, 0.78]},
    'slots': {'fam': 'concrete', 'floorH': 4.2, 'bayW': 4.4, 'w': [0.38, 0.50, 0.76]},
    'shop': {'fam': 'concrete', 'floorH': 5.0, 'bayW': 4.2, 'w': [0.05, 0.04, 0.80]},
}
STRIP_COLS = [KIT.hex_lin('#29e7ff'), KIT.hex_lin('#ff4fd8'), KIT.hex_lin('#ff8a3d'), KIT.hex_lin('#e9f3f1')]
_FRAME = {'aM': [2, 4, 4, 0], 'aW': [0, 0, 0, 0]}


def sign_at(xf, sid, local, ry, rx, w, h, gain, flicker):
    """A sign quad placed in a building's frame: local position, yaw (about local Y) then pitch (about local X)."""
    p = xf.p(local)
    q = KIT.quat_mul(xf.q, KIT.quat_euler_yxz(rx, ry, 0.0))
    return {'id': sid, 'pos': p, 'quat': q, 'w': w, 'h': h, 'gain': gain, 'flicker': flicker,
            'power': hash1(p[0] * 0.37 + p[2] * 0.73)}


def emit_building(lot, ctx, over=None):
    """Emit one building into the buffers. lot: a polar lot; ctx: {'buf': {concrete, metal, frame, strip GeoBufs},
    'signs': [], 'lights': []}; over: {'height', 'lean' (deg), 'style', 'type'} overrides. Returns {'x', 'z', 'H',
    'type'} or None (a lot too small to build)."""
    over = over or {}
    R = rng(math.floor(lot['seed'] * 1e9) + 7)
    P = zone_params(lot['zone'])
    rc, tc = (lot['r0'] + lot['r1']) / 2, (lot['t0'] + lot['t1']) / 2
    cx, cz = rc * math.cos(tc), rc * math.sin(tc)
    depth = lot['r1'] - lot['r0']
    width = 2 * lot['r0'] * math.sin((lot['t1'] - lot['t0']) / 2)
    if width < 10 or depth < 10:
        return None
    yaw = math.atan2(-math.cos(tc), -math.sin(tc))             # local +Z faces the hole
    d_plaza = math.hypot(cx - DIVE_C3[0], cz - DIVE_C3[2])
    in_plaza = d_plaza < PLAZA_R + max(width, depth) * 0.5
    H = lerp(P['h'][0], P['h'][1], math.pow(R(), 1.35))
    if lot.get('supertall'):
        H = 300 + R() * 120
    if over.get('height'):
        H = over['height']
    if in_plaza:
        H = min(H, 9 + R() * 9)
    if over.get('lean') is not None:
        lean_deg = over['lean']
    else:
        lean_deg = P['lean'] * (0.6 + 0.8 * R())
        lean_deg += (3 + R() * 3) if R() < 0.08 else 0
    lean = lean_deg * D2R * (0 if in_plaza else 1)
    style_key = over.get('style') or (['curtain', 'ribbon', 'slots', 'punched'][math.floor(R() * 4)] if H > 150 else
                                      ['punched', 'resid', 'ribbon', 'slots', 'curtain'][math.floor(R() * 5)])
    S = STYLES[style_key]
    seed = R()
    litF = lerp(P['lit'][0], P['lit'][1], R())
    aT = [seed, litF, 0.25 + R() * 0.6, 1 if R() < 0.3 else 0]
    aM = [0, S['floorH'], S['bayW'], 0]
    aW = [S['w'][0], S['w'][1], S['w'][2], R()]
    buf = ctx['buf'][S['fam']]
    pos = [cx, STREET_Y, cz]
    xf_flat = KIT.make_xf(pos, yaw, 0, 0)
    frame = {'aT': aT, **_FRAME}
    # ---- podium (plumb): a shop floor + 1..3 floors above; fills the lot
    pod_h = 0
    has_pod = (R() < P['pod']) if not in_plaza else True
    W, D = min(width, 90), min(depth, 90)
    if has_pod:
        if in_plaza:
            pod_h = H
        else:
            pod_h = 5 + (3.8 * (1 + math.floor(R() * 3)) if R() < 0.6 else 0)
        shop = {'aT': [seed, 0.75, 0.6, 1], 'aM': [3, 5.0, STYLES['shop']['bayW'], 0], 'aW': [*STYLES['shop']['w'], aW[3]]}
        ctx['buf']['concrete'].box(xf_flat, -W / 2, -0.5, -D / 2, W / 2, min(5, pod_h), D / 2, shop, {'vBase': 0})
        if pod_h > 5.2:
            ctx['buf']['concrete'].box(xf_flat, -W / 2, 5, -D / 2, W / 2, pod_h, D / 2,
                                       {'aT': aT, 'aM': [0, 3.8, 2.6, 0], 'aW': [0.24, 0.3, 0.78, aW[3]]},
                                       {'vBase': 5, 'top': pod_h - 5})
        # shop signs on the faces that front streets (hole side always, plus sides)
        for f, n in (('Z', [0, 0, 1]), ('x', [-1, 0, 0]), ('X', [1, 0, 0]), ('z', [0, 0, -1])):
            if f != 'Z' and R() < 0.45:
                continue
            along = W if f in ('Z', 'z') else D
            k = KIT.SHOPS[math.floor(R() * len(KIT.SHOPS))]
            sw = min(along * 0.7, 6 + R() * 5)
            sh = sw / 4
            off = (R() - 0.5) * (along - sw) * 0.8
            if f == 'Z':
                local = [off, 5.2 + sh / 2, D / 2 + 0.25]
            elif f == 'z':
                local = [off, 5.2 + sh / 2, -D / 2 - 0.25]
            elif f == 'X':
                local = [W / 2 + 0.25, 5.2 + sh / 2, off]
            else:
                local = [-W / 2 - 0.25, 5.2 + sh / 2, off]
            ry = 0 if f == 'Z' else math.pi if f == 'z' else math.pi / 2 if f == 'X' else -math.pi / 2
            gain = 4.5 + R() * 3
            flick = 1 if R() < 0.15 else 0
            ctx['signs'].append(sign_at(xf_flat, 'shop:' + k[0], local, ry, 0, sw, sh, gain, flick))
            wp = xf_flat.p([local[0] + n[0] * 5, 0, local[2] + n[2] * 5])
            ctx['lights'].append({'x': wp[0], 'z': wp[2], 'r': 9 + sw * 0.6,
                                  'c': next(s for s in KIT.SHOPS if s[0] == k[0])[1], 'a': 0.55})
            # a blade sign at the corner of the hole-facing face
            if f == 'Z' and R() < 0.4:
                b = KIT.BLADES[math.floor(R() * len(KIT.BLADES))]
                bh = 7 + R() * 6
                bx = (-1 if R() < 0.5 else 1) * (W / 2 - 1.2)
                for side in (1, -1):
                    ctx['signs'].append(sign_at(xf_flat, 'blade:' + b[0], [bx + side * 0.12, 6.5 + bh / 2, D / 2 + 1.45],
                                                math.pi / 2 if side > 0 else -math.pi / 2, 0, bh * 96 / 448, bh, 4.0, 0))
                ctx['buf']['frame'].box(xf_flat, bx - 0.08, 6.5 - 0.2, D / 2, bx + 0.08, 6.5 + bh + 0.2, D / 2 + 2.9, frame)
    if in_plaza:
        return {'x': cx, 'z': cz, 'H': H}
    # ---- the tower (leans toward the hole about its base, which is buried in the podium)
    base = pod_h - 1.5 if pod_h > 0 else -0.5
    xf = KIT.make_xf(pos, yaw, lean, base)
    tw = min(W * (0.62 + R() * 0.3), 70)
    td = min(D * (0.55 + R() * 0.35), 60)
    kind_r = R()
    if over.get('type'):
        typ = over['type']
    elif lot.get('supertall'):
        typ = 'setback'
    elif H > 170:
        typ = 'gradinata' if kind_r < 0.4 else 'setback' if kind_r < 0.7 else 'slab'
    else:
        typ = 'gradinata' if kind_r < 0.25 else 'wedge' if kind_r < 0.5 else 'slab' if kind_r < 0.75 else 'setback'
    att = {'aT': aT, 'aM': aM, 'aW': aW}
    tiers = []
    if typ == 'slab':
        sw, sd = tw, min(td, tw * 0.5 + 6)
        buf.box(xf, -sw / 2, base, -sd / 2, sw / 2, H, sd / 2, att, {'vBase': base, 'top': H - base})
        tiers.append({'x0': -sw / 2, 'x1': sw / 2, 'z0': -sd / 2, 'z1': sd / 2, 'y': H})
        nf = max(2, jround(sw / 9))                       # vertical fins on the long faces: Sant'Elia's piers
        for i in range(nf + 1):
            fx = -sw / 2 + sw * i / nf
            for zz in (sd / 2, -sd / 2):
                ctx['buf']['frame'].box(xf, fx - 0.35, base, zz - 0.6, fx + 0.35, H + 1.5, zz + 0.6, frame)
    elif typ == 'setback':
        n = 3 + math.floor(R() * 2)
        y0, w0, d0 = base, tw, td
        for i in range(n):
            y1 = H if i == n - 1 else base + (H - base) * (0.45 + 0.55 * (i + 1) / n) * (0.8 if i == 0 else 1)
            buf.box(xf, -w0 / 2, y0, -d0 / 2, w0 / 2, y1, d0 / 2, att, {'vBase': base, 'top': H - base})
            tiers.append({'x0': -w0 / 2, 'x1': w0 / 2, 'z0': -d0 / 2, 'z1': d0 / 2, 'y': y1})
            y0 = y1
            w0 *= 0.72 + R() * 0.12
            d0 *= 0.72 + R() * 0.12
        if lot.get('supertall'):                      # a mast that disappears into the cloud
            ctx['buf']['frame'].box(xf, -0.8, H, -0.8, 0.8, H + 60, 0.8, frame)
            for k in range(1, 4):
                ctx['buf']['frame'].box(xf, -0.35, H + k * 15, -0.35, 0.35, H + k * 15 + 0.7, 0.35,
                                        {'aT': aT, 'aM': [4, 4, 4, 0], 'aW': [0, 0, 0, 0]})
    elif typ == 'wedge':
        hi, lo = H, H * (0.55 + R() * 0.25)
        to_hole = R() < 0.6                               # the slope falls toward the hole (Crali's tilted roofs)
        buf.box(xf, -tw / 2, base, -td / 2, tw / 2, hi, td / 2, att,
                {'vBase': base, 'top': hi - base, 'y1a': hi if to_hole else lo, 'y1b': lo if to_hole else hi})
        tiers.append({'x0': -tw / 2, 'x1': tw / 2, 'z0': -td / 2, 'z1': td / 2, 'y': lo, 'sloped': True})
    else:                                                # gradinata: the hole face steps back in terraces; two lift shafts
        n = 4 + math.floor(R() * 3)
        step_d = td / (n + 1)
        for i in range(n):
            y1 = base + (H - base) * (i + 1) / n
            z1 = td / 2 - step_d * i
            buf.box(xf, -tw / 2, base if i == 0 else base + (H - base) * i / n - 0.01, -td / 2, tw / 2, y1, z1, att,
                    {'vBase': base, 'top': y1 - base})
            tiers.append({'x0': -tw / 2, 'x1': tw / 2, 'z0': -td / 2, 'z1': z1, 'y': y1, 'terrace': True})
        shaft_h = H + 14
        fz = td / 2 + 7
        for sx in (-tw * 0.3, tw * 0.3):
            ctx['buf']['frame'].box(xf, sx - 2.2, base, fz - 2.2, sx + 2.2, shaft_h, fz + 2.2,
                                    {'aT': aT, 'aM': [5, shaft_h, 4.4, 0], 'aW': [0, 0, 0, 0]},
                                    {'vBase': base, 'top': shaft_h - base})
            for k in range(1, n + 1):                     # bridges to every terrace
                by = base + (H - base) * k / n - 3.2
                z_end = td / 2 - step_d * (k - 1)
                if z_end >= fz - 2.2:
                    continue
                ctx['buf']['frame'].box(xf, sx - 1.4, by, z_end - 0.5, sx + 1.4, by + 2.8, fz - 2.2 + 0.2,
                                        {'aT': aT, 'aM': [0, 2.8, 1.4, 0], 'aW': [0.05, 0.25, 0.85, 0]})
    # ---- roof: plant, beacons, antenna; signs on some roofs and facades
    T0 = tiers[-1]
    if not T0.get('sloped'):
        nb_ = 1 + math.floor(R() * 3)
        for _ in range(nb_):
            bw, bd, bh = 3 + R() * 6, 3 + R() * 6, 2 + R() * 4
            bx = lerp(T0['x0'] + bw, T0['x1'] - bw, R())
            bz = lerp(T0['z0'] + bd, T0['z1'] - bd, R())
            ctx['buf']['frame'].box(xf, bx - bw / 2, T0['y'] - 0.2, bz - bd / 2, bx + bw / 2, T0['y'] + bh, bz + bd / 2,
                                    frame)
    if H > 120:
        for ex, ez in ((T0['x0'] + 0.6, T0['z0'] + 0.6), (T0['x1'] - 0.6, T0['z1'] - 0.6)):
            ctx['buf']['frame'].box(xf, ex - 0.4, T0['y'], ez - 0.4, ex + 0.4, T0['y'] + 1.2, ez + 0.4,
                                    {'aT': aT, 'aM': [4, 4, 4, 0], 'aW': [0, 0, 0, 0]})
    if H > 90 and R() < 0.4 and not T0.get('sloped'):
        ctx['buf']['frame'].box(xf, -0.3, T0['y'], -0.3, 0.3, T0['y'] + 10 + R() * 25, 0.3, frame)
    # roof supergraphic, read from the dive
    if not T0.get('sloped') and R() < 0.16:
        rw = min(T0['x1'] - T0['x0'], (T0['z1'] - T0['z0']) * 2) * 0.8
        sid = 'heli' if R() < 0.18 else 'roof:' + str(math.floor(R() * 8))
        asp = 1 if sid == 'heli' else 2
        ctx['signs'].append(sign_at(xf, sid, [0, T0['y'] + 0.08, (T0['z0'] + T0['z1']) / 2], 0, -math.pi / 2, rw, rw / asp,
                                    0.7 + R() * 0.5, 0))
    # a big ad on the hole-facing (or a side) facade, mounted on a backing frame
    if R() < (0.55 if lot['zone'] <= 1 else 0.32) and H > 40:
        ad = KIT.AD_COPY[math.floor(R() * len(KIT.AD_COPY))]
        T1 = tiers[0]
        face_z = T1['z1']
        aw = min(T1['x1'] - T1['x0'] - 4, 18 + R() * 16)
        ah = aw / 4
        ay = lerp(max(base + ah, 22), min(H * 0.55, 80), R())
        side = 'Z' if R() < 0.65 else 'X'
        if side == 'Z':
            ctx['buf']['frame'].box(xf, -aw / 2 - 0.6, ay - ah / 2 - 0.6, face_z, aw / 2 + 0.6, ay + ah / 2 + 0.6,
                                    face_z + 0.5, frame, {'faces': 'xXzZt'})
            gain = 2.2 + R() * 1.2
            ctx['signs'].append(sign_at(xf, 'ad:' + ad['id'], [0, ay, face_z + 0.56], 0, 0, aw, ah, gain,
                                        2 if R() < 0.1 else 0))
        else:
            fx, aw2 = T1['x1'], min(T1['z1'] - T1['z0'] - 4, aw)
            ah2 = aw2 / 4
            if aw2 > 8:
                ctx['buf']['frame'].box(xf, fx, ay - ah2 / 2 - 0.6, -aw2 / 2 - 0.6, fx + 0.5, ay + ah2 / 2 + 0.6,
                                        aw2 / 2 + 0.6, frame)
                ctx['signs'].append(sign_at(xf, 'ad:' + ad['id'], [fx + 0.56, ay, 0], math.pi / 2, 0, aw2, ah2,
                                            2.2 + R() * 1.2, 0))
    # a Futurist supergraphic painted on a side wall (floodlit)
    if R() < 0.22 and H > 50:
        T1 = tiers[0]
        ln = min(T1['z1'] - T1['z0'] - 2, 46)
        gh = ln / 6
        if ln > 12:
            gy = lerp(base + gh + 4, min(H * 0.8, 120), R())
            sx = -1 if R() < 0.5 else 1
            sid = 'fut:' + str(math.floor(R() * len(KIT.FUTURIST)))
            ctx['signs'].append(sign_at(xf, sid, [sx * (T1['x1'] + 0.12), gy, (T1['z0'] + T1['z1']) / 2],
                                        math.pi / 2 if sx > 0 else -math.pi / 2, 0, ln, gh, 0.9 + R() * 0.5, 0))
    # neon edge strips: vertical lines on the hole-facing corners (they converge on the hole from the dive)
    if R() < (0.5 if lot['zone'] <= 1 else 0.22):
        c = STRIP_COLS[math.floor(R() * len(STRIP_COLS))]
        T1 = tiers[0]
        a_t = [c[0], c[1], c[2], R()]
        a_m = [1 if R() < 0.5 else 0, 3.2 + R() * 2, 0.35 + R() * 0.4, R()]
        st = {'aT': a_t, 'aM': a_m, 'aW': [0, 0, 0, 0]}
        for ex in (T1['x0'], T1['x1']):
            ctx['buf']['strip'].box(xf, ex - 0.18, base, T1['z1'] - 0.18, ex + 0.18, T1['y'] + 0.4, T1['z1'] + 0.18, st,
                                    {'vBase': T1['y'] + 0.4})
        for t in tiers:
            if t['y'] < H - 1 or t.get('terrace'):
                ctx['buf']['strip'].box(xf, t['x0'], t['y'] - 0.1, t['z1'] - 0.15, t['x1'], t['y'] + 0.25, t['z1'] + 0.15,
                                        st)
    return {'x': cx, 'z': cz, 'H': H, 'type': typ}


# ------------------------------------------------------------------------------------------------ the ground
def ring_sector(ra, rb, t0, t1, y0, y1, segs):
    """A closed annular-sector slab: top, outer, inner and two radial sides, each quad wound to face OUT.
    Returns (P (three), quads [[a, b, c, d]])."""
    P, Q = [], []
    n = max(2, segs)

    def ring(r, y):
        return [[r * math.cos(t0 + (t1 - t0) * i / n), y, r * math.sin(t0 + (t1 - t0) * i / n)] for i in range(n + 1)]
    ti, to, bi, bo = ring(ra, y1), ring(rb, y1), ring(ra, y0), ring(rb, y0)

    def quad(a, b, c, d, nrm):
        cb = [c[0] - b[0], c[1] - b[1], c[2] - b[2]]
        ab = [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
        g = [cb[1] * ab[2] - cb[2] * ab[1], cb[2] * ab[0] - cb[0] * ab[2], cb[0] * ab[1] - cb[1] * ab[0]]
        if g[0] * nrm[0] + g[1] * nrm[1] + g[2] * nrm[2] < 0:
            a, b, c, d = d, c, b, a
        k = len(P)
        P.extend([a, b, c, d])
        Q.append([k, k + 1, k + 2, k + 3])
    for i in range(n):
        tm = t0 + (t1 - t0) * (i + 0.5) / n
        rad = [math.cos(tm), 0, math.sin(tm)]
        quad(ti[i], to[i], to[i + 1], ti[i + 1], [0, 1, 0])
        quad(bo[i], to[i], to[i + 1], bo[i + 1], rad)
        quad(bi[i + 1], ti[i + 1], ti[i], bi[i], [-rad[0], 0, -rad[2]])
    quad(bi[0], ti[0], to[0], bo[0], [math.sin(t0), 0, -math.cos(t0)])
    quad(bo[n], to[n], ti[n], bi[n], [-math.sin(t1), 0, math.cos(t1)])
    return P, Q


def build_blocks(blocks):
    """The raised block slabs (sidewalks) at the street: (P, quads, uv = world x, z)."""
    P, Q = [], []
    for b in blocks:
        segs = math.ceil((b['t1'] - b['t0']) * b['rb'] / 12)
        p, q = ring_sector(b['ra'], b['rb'], b['t0'], b['t1'], STREET_Y - 0.3, STREET_Y + 0.16, segs)
        k = len(P)
        P.extend(p)
        Q.extend([[i + k for i in f] for f in q])
    P = np.asarray(P, np.float64)
    return P, np.asarray(Q, np.int64), np.stack([P[:, 0], P[:, 2]], 1)


def plan_lamps():
    """Street lamps along the avenues and ring roads (both kerbs): [{'x', 'z', 'yaw', 'r'}] (three's axes; the arm,
    local -Z, reaches over the road)."""
    L = []
    SP = 34
    avs = [{'a': a, 'r0': HOLE['ring_road'][1] + 6, 'r1': CITY_R} for a in AVENUES_MAIN] + \
          [{'a': a, 'r0': SECOND_START + 12, 'r1': CITY_R} for a in AVENUES_SECOND]
    for v in avs:
        r = v['r0']
        while r < v['r1']:
            for s in (-1, 1):
                off = s * (AVENUE_W / 2 + 0.8)
                x = r * math.cos(v['a']) - off * math.sin(v['a'])
                z = r * math.sin(v['a']) + off * math.cos(v['a'])
                ax, az = -math.sin(v['a']) * -s, math.cos(v['a']) * -s
                L.append({'x': x, 'z': z, 'yaw': math.atan2(-ax, -az), 'r': 14})
            r += SP
    for g in RINGS + [{'r': 40.0, 'w': 20.0}]:
        n = jround(2 * math.pi * g['r'] / SP)
        for i in range(n):
            for s in ((1,) if g['r'] == 40 else (-1, 1)):
                t = (i + 0.5) / n * 2 * math.pi
                rr = g['r'] + s * (g['w'] / 2 + 0.8)
                na = KIT.nearest_avenue(t, rr)
                if na['d'] != 1e9 and abs(na['d']) < AVENUE_W / 2 + 3:
                    continue
                x, z = rr * math.cos(t), rr * math.sin(t)
                ax, az = -math.cos(t) * s, -math.sin(t) * s
                L.append({'x': x, 'z': z, 'yaw': math.atan2(-ax, -az), 'r': 14})
    return L


def plan_traffic():
    """Traffic paths: ring roads (two lanes each way) + avenues (two lanes each way)."""
    R = rng(77)
    paths = []
    for g in RINGS + [{'r': 40.0, 'w': 20.0}]:
        lanes = [-6.5, -3, 3, 6.5] if g['r'] == 40 else [-6, -2.5, 2.5, 6]
        for ln in lanes:
            d = -1 if ln < 0 else 1
            r = g['r'] + ln
            spacing = 18 if g['r'] == 40 else 55 + R() * 30
            n = max(3, math.floor(2 * math.pi * r / spacing))
            for i in range(n):
                speed = (13 if g['r'] == 40 else 15) + R() * 6
                phase = (i + R() * 0.6) / n * 2 * math.pi
                paths.append({'type': 'ring', 'r': r, 'dir': d, 'speed': speed, 'phase': phase})
    avs = [{'a': a, 'r0': HOLE['ring_road'][1], 'r1': CITY_R} for a in AVENUES_MAIN] + \
          [{'a': a, 'r0': SECOND_START, 'r1': CITY_R} for a in AVENUES_SECOND]
    for v in avs:
        for ln in (-8.5, -4.5, 4.5, 8.5):
            d = 1 if ln < 0 else -1
            span = v['r1'] - v['r0']
            n = math.floor(span / (48 + R() * 30))
            for i in range(n):
                speed = 14 + R() * 7
                phase = (i + R() * 0.7) / n
                paths.append({'type': 'av', 'th': v['a'], 'r0': v['r0'], 'r1': v['r1'], 'lane': ln, 'dir': d,
                              'speed': speed, 'phase': phase})
    return paths


def emit_far_skyline(buf):
    """The far skyline ring beyond the city: simple tall blocks for silhouette and glitter (fogged)."""
    R = rng(31337)
    for _ in range(420):
        t = R() * math.pi * 2
        r = lerp(FAR_R[0], FAR_R[1], math.sqrt(R()))
        w, d, h = 20 + R() * 50, 20 + R() * 40, 30 + math.pow(R(), 2) * 220
        xf = KIT.make_xf([r * math.cos(t), STREET_Y, r * math.sin(t)], math.atan2(-math.cos(t), -math.sin(t)), 0, 0)
        aT = [R(), 0.25 + R() * 0.2, 0.5, 0]
        aW = [0.2, 0.3, 0.8, R()]
        buf.box(xf, -w / 2, -1, -d / 2, w / 2, h, d / 2, {'aT': aT, 'aM': [0, 3.8, 2.4, 0], 'aW': aW})


def ring_geometry(r_in, r_out, theta_segs, phi_segs, y):
    """three's RingGeometry rotated flat (rotateX(-pi/2)) at height y: (P, quads, uv = world x, z)."""
    P = []
    for j in range(phi_segs + 1):
        r = r_in + (r_out - r_in) * j / phi_segs
        for i in range(theta_segs + 1):
            a = 2 * math.pi * i / theta_segs
            P.append([r * math.cos(a), y, -r * math.sin(a)])
    Q = []
    for j in range(phi_segs):
        for i in range(theta_segs):
            a = j * (theta_segs + 1) + i
            b = a + theta_segs + 1
            Q.append([a, b, b + 1, a + 1])            # wound to face +Y (up)
    P = np.asarray(P, np.float64)
    return P, np.asarray(Q, np.int64), np.stack([P[:, 0], P[:, 2]], 1)


def circle_geometry(r, segs, y):
    """three's CircleGeometry rotated flat: (P, faces, uv as three's (0..1 across the disc, v toward -z))."""
    P = [[0.0, y, 0.0]] + [[r * math.cos(2 * math.pi * i / segs), y, -r * math.sin(2 * math.pi * i / segs)]
                           for i in range(segs)]
    F = [[0, 1 + i, 1 + (i + 1) % segs] for i in range(segs)]
    P = np.asarray(P, np.float64)
    uv = np.stack([(P[:, 0] / r + 1) / 2, (-P[:, 2] / r + 1) / 2], 1)
    return P, F, uv


def torus_geometry(radius, tube, radial_segs, tubular_segs):
    """three's TorusGeometry in its own XY plane (the ring round Z): (P, quads, uv)."""
    P, UV = [], []
    for j in range(radial_segs + 1):
        for i in range(tubular_segs + 1):
            u = i / tubular_segs * 2 * math.pi
            v = j / radial_segs * 2 * math.pi
            P.append([(radius + tube * math.cos(v)) * math.cos(u), (radius + tube * math.cos(v)) * math.sin(u),
                      tube * math.sin(v)])
            UV.append([i / tubular_segs, j / radial_segs])
    Q = []
    for j in range(1, radial_segs + 1):
        for i in range(1, tubular_segs + 1):
            a = (tubular_segs + 1) * j + i - 1
            b = (tubular_segs + 1) * (j - 1) + i - 1
            c = (tubular_segs + 1) * (j - 1) + i
            d = (tubular_segs + 1) * j + i
            Q.append([a, b, c, d])
    return np.asarray(P, np.float64), np.asarray(Q, np.int64), np.asarray(UV, np.float64)


def box_geometry(w, h, d):
    """three's BoxGeometry (centred): (P, quads, uv), faces wound outward."""
    x0, x1, y0, y1, z0, z1 = -w / 2, w / 2, -h / 2, h / 2, -d / 2, d / 2
    faces = [([x1, y0, z1], [x1, y0, z0], [x1, y1, z0], [x1, y1, z1]), ([x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0]),
             ([x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0]), ([x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]),
             ([x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]), ([x1, y0, z0], [x0, y0, z0], [x0, y1, z0], [x1, y1, z0])]
    P, Q, UV = [], [], []
    for f in faces:
        k = len(P)
        P.extend(f)
        UV.extend([[0, 0], [1, 0], [1, 1], [0, 1]])
        Q.append([k, k + 1, k + 2, k + 3])
    return np.asarray(P, np.float64), np.asarray(Q, np.int64), np.asarray(UV, np.float64)


# ------------------------------------------------------------------------------------------------ light linking
def _link_state(rc, child, state):
    """Set a child collection's light-linking state in a receiver collection (collection_children follows children's
    order and takes no names)."""
    for i, c in enumerate(rc.children):
        if c == child:
            rc.collection_children[i].light_linking.link_state = state
            return


def exclude_from_light(light_ob, collection, made=None):
    """Light linking: light_ob no longer lights the collection's objects (it keeps lighting everything else). A
    receiver collection made here is recorded in made (the light's own one is kept)."""
    ll = light_ob.light_linking
    rc = ll.receiver_collection
    if rc is None:
        rc = bpy.data.collections.new(f'uf_ll_{light_ob.name}')
        if made is not None:
            made.add(rc)
        ll.receiver_collection = rc
    if collection.name not in rc.children:
        rc.children.link(collection)
    _link_state(rc, collection, 'EXCLUDE')


def unexclude_from_light(light_ob, collection):
    """Undo exclude_from_light: light_ob lights the collection's objects again."""
    rc = light_ob.light_linking.receiver_collection
    if rc is None:
        return
    for i, c in enumerate(rc.children):
        if c == collection:
            if rc.collection_children[i].light_linking.link_state == 'EXCLUDE':
                rc.children.unlink(collection)
            return


def restrict_lights(scene, collection, keep, made=None):
    """The set's surfaces (collection) see only the lights in keep, their own and the World: every other light in the
    scene excludes the collection (light linking); a kept light that was excluded before lights it again. The engine's
    material.lightsNode = lights(list), as setLights did it."""
    keep = set(keep)
    for ob in scene.objects:
        if ob.type != 'LIGHT' or ob.name in collection.all_objects:
            continue
        if ob in keep:
            unexclude_from_light(ob, collection)
        else:
            exclude_from_light(ob, collection, made)


def light_only(light_ob, collections, made=None):
    """Light linking: light_ob lights only these collections' objects (each INCLUDE)."""
    rc = bpy.data.collections.new(f'uf_ll_{light_ob.name}')
    if made is not None:
        made.add(rc)
    for c in collections:
        rc.children.link(c)
        _link_state(rc, c, 'INCLUDE')
    light_ob.light_linking.receiver_collection = rc
    return rc


# ------------------------------------------------------------------------------------------------ build
def light_draws(lamps, bctx, hole=True):
    """The street light map's paint: lamp pools (at each head, over the road), shop spill, the piazza at the dive's
    crossing, a faint glow under every low ad, and (with hole) the hole's share."""
    def city_lights(ctx, to_px, s):
        for l in lamps:
            ax, az = math.sin(l['yaw']) * -2.4, math.cos(l['yaw']) * -2.4
            KIT.lm_pool(ctx, to_px, s, l['x'] + ax, l['z'] + az, l['r'], '#ff8a3d', 0.85)
        for l in bctx['lights']:
            KIT.lm_pool(ctx, to_px, s, l['x'], l['z'], l['r'], KIT.PAL.get(l['c'], '#e9f3f1'), l['a'])
        # the dive's crossing: a lit piazza (the light at Crali's vanishing point)
        KIT.lm_pool(ctx, to_px, s, DIVE_C3[0], DIVE_C3[2], 40, '#ffb070', 0.9)
        KIT.lm_pool(ctx, to_px, s, DIVE_C3[0], DIVE_C3[2], 18, '#fff0dc', 1.0)
        for i in range(10):
            a = i / 10 * math.pi * 2
            KIT.lm_pool(ctx, to_px, s, DIVE_C3[0] + math.cos(a) * 26, DIVE_C3[2] + math.sin(a) * 26, 9,
                        '#29e7ff' if i % 2 else '#ff4fd8', 0.35)
        for sg in bctx['signs']:
            if sg['id'].startswith('ad:') and sg['pos'][1] < STREET_Y + 60:
                KIT.lm_pool(ctx, to_px, s, sg['pos'][0], sg['pos'][2], 26, '#7aa8ff', 0.10)
    if hole:
        from .hole import draw_hole_lights
        return [city_lights, draw_hole_lights]
    return [city_lights]


def build(first=None, opts=None, ctx=None, **kw):
    """Build the city (and, unless opts['hole'] is False, the hole inside it). first: the harness ctx (its scene; every
    key the set makes then goes through ctx.key), a bpy Scene, or the opts dict (city.js's build(THREE, opts)); ctx=
    works too (eidoblend.sets.build passes it so). opts:
    kit (share a Kit), seed (1909), hole (True), rain_count (26000; rainCount too), scene, collection (the parent
    collection), light_scale (1: three's balance of lights against emission), env_intensity, and the hole's own
    options. Returns the set (a dict whose keys read as attributes): group (the root Empty), collection, parts,
    update, dispose, cams, and the Blender additions animate and make_cameras."""
    import time as _time
    t_start = _time.perf_counter()
    opts, scene, ctx = KIT.scene_and_ctx(first, opts, dict(kw, ctx=ctx) if ctx is not None else kw)
    K = opts.get('kit') or KIT.make_kit(opts)
    if ctx is not None:
        K.U.keyer = ctx.key
    parent_coll = opts.get('collection') or scene.collection
    coll = bpy.data.collections.new('set:city')
    K.made.add(coll)
    parent_coll.children.link(coll)
    root = KIT.new_object('set:city', None, coll, made=K.made)
    root.empty_display_size = 5.0
    K.collection, K.root = coll, root
    plan = plan_city(opts.get('seed', 1909))
    lamps = plan_lamps()
    # ---- buildings (into merged buffers) and their signs + light spill
    buf = {'concrete': KIT.GeoBuf(), 'metal': KIT.GeoBuf(), 'frame': KIT.GeoBuf(), 'strip': KIT.GeoBuf()}
    bctx = {'buf': buf, 'signs': [], 'lights': []}
    lots = sorted(plan['lots'], key=lambda l: l['r0'])
    built = []
    for lot in lots:
        b = emit_building(lot, bctx)
        if b:
            built.append(b)
    far_buf = KIT.GeoBuf()
    emit_far_skyline(far_buf)
    # ---- the hole (its own module): planned now so its lights land in the light map
    hole_mod = None
    if opts.get('hole', True) is not False:
        from . import hole as hole_mod

    KIT.make_light_map(K, light_draws(lamps, bctx, hole_mod is not None))
    # ---- materials (after the light map: they sample it)
    if K.mat is None:
        K.mat = {'concrete': KIT.facade_material(K, 'concrete'), 'metal': KIT.facade_material(K, 'metal'),
                 'frame': KIT.frame_material(K), 'strip': KIT.strip_material(K), 'ground': KIT.ground_material(K),
                 'paving': KIT.paving_material(K, 'paving'), 'marble': KIT.paving_material(K, 'marble')}
    M = K.mat
    meshes = {}

    def add_mesh(name, me, mat):
        me.materials.append(mat)
        ob = KIT.new_object(name, me, coll, parent=root, made=K.made)
        ob['assembly'] = 'uf_city'
        meshes[name] = ob
        return ob
    add_mesh('uf_towers_concrete', buf['concrete'].build('uf_towers_concrete', K.made), M['concrete'])
    add_mesh('uf_towers_metal', buf['metal'].build('uf_towers_metal', K.made), M['metal'])
    add_mesh('uf_frames', buf['frame'].build('uf_frames', K.made), M['frame'])
    if buf['strip'].count:
        add_mesh('uf_strips', buf['strip'].build('uf_strips', K.made), M['strip'])
    add_mesh('uf_far', far_buf.build('uf_far', K.made), M['concrete'])
    # ---- ground: the street disc (with the hole's opening) and the raised blocks
    P, Q, uv = ring_geometry(HOLE['rim_r'], FAR_R[1] + 200, 160, 24, STREET_Y)
    add_mesh('uf_street', KIT.make_mesh('uf_street', P, Q, uv=uv, made=K.made), M['ground'])
    P, Q, uv = build_blocks(plan['blocks'])
    add_mesh('uf_blocks', KIT.make_mesh('uf_blocks', P, Q, uv=uv, made=K.made), M['paving'])
    # ---- the city's own light: the dim hemisphere is the World (make_sky); the sky glow a sun without shadows
    light_scale = float(opts.get('light_scale', 1.0))
    sky = KIT.make_sky(K, env_intensity=opts.get('env_intensity'))
    moon_d = bpy.data.lights.new('uf_skyglow', 'SUN')
    K.made.add(moon_d)
    moon_d.energy = 0.12 * light_scale
    moon_d.color = KIT.srgb_lin(0x8fa6c8)
    moon_d.use_shadow = False
    moon = KIT.new_object('uf_skyglow', moon_d, coll, parent=root, made=K.made)
    from mathutils import Vector
    moon.rotation_mode = 'QUATERNION'
    moon.rotation_quaternion = Vector(KIT.to_blender((-300, 900, -200))).normalized().to_track_quat('Z', 'Y')
    atlas = KIT.make_sign_atlas(K)
    hole = None
    if hole_mod:
        hole = hole_mod.build(dict(opts, kit=K, atlas=atlas, with_city=True, city_lights=[moon], collection=coll,
                                   parent=root, scene=scene))
    plaza = make_plaza_screen(K, coll, root)
    signs = KIT.make_signs_mesh(K, atlas, bctx['signs'] + (hole['parts']['city_signs'] if hole else []), coll,
                                parent=root)
    lamp = KIT.make_lamps(K, lamps, coll, parent=root)
    traffic = KIT.make_traffic(K, plan_traffic(), coll, parent=root)
    rain = KIT.make_rain(K, coll, {'count': opts.get('rain_count', opts.get('rainCount', 26000))}, parent=root)
    clouds = KIT.make_clouds(K, coll, parent=root)

    def set_lights(lights):
        """The city's lit surfaces see only these lights (and the World): every other light in the scene is set to
        exclude the city's collection (light linking). Call it again after adding lights to the scene."""
        keep = set(lights) | ({hole['parts']['lights'][k] for k in hole['parts']['lights']} if hole else set())
        restrict_lights(scene, coll, keep, K.made)
    set_lights([moon])
    U = K.U

    def apply_atmosphere(sc=None, objects=None):
        """The scene's atmosphere: the city's World (the night sky, its hemisphere, its environment); the haze lives
        in the set's materials. objects: the conductor's own objects (the singer, props) take the haze too, as three's
        scene.fogNode fogged every material in the scene (KIT.fog_objects; see-through materials are left as they
        are)."""
        sc = sc or scene
        sc.world = sky['world']
        if objects:
            KIT.fog_objects(K, objects)
        return sc

    set_focal = make_set_focal(U)
    last = {'pos': None, 'frame': None}

    def update(t, state=None, frame=None, ctx=None):
        """Set (and with frame, key) the city's clock and the rain's camera velocity: state {'cam_vel' | 'camVel' (m/s,
        Blender axes), 'camera' (a camera object: its velocity by finite difference between calls when no cam_vel
        is given), 'fps'}. ctx: the harness ctx (from now on, keys go through ctx.key)."""
        if ctx is not None:
            U.keyer = ctx.key
        state = state or {}
        U['time'] = t
        cv = state.get('cam_vel', state.get('camVel'))
        if cv is None and state.get('camera') is not None and frame is not None:
            try:                                  # matrix_world is current only after a depsgraph update
                bpy.context.view_layer.update()
            except (AttributeError, RuntimeError):
                pass
            p = tuple(state['camera'].matrix_world.translation)
            fps = state.get('fps') or scene.render.fps / scene.render.fps_base
            if last['pos'] is not None and 0 < frame - last['frame'] <= 2:
                dt = (frame - last['frame']) / fps
                cv = [(p[i] - last['pos'][i]) / dt for i in range(3)]
                if math.hypot(*cv) > 400:
                    cv = [0.0, 0.0, 0.0]
            else:
                cv = [0.0, 0.0, 0.0]
            last['pos'], last['frame'] = p, frame
        if cv is not None:
            U['cam_vel'] = cv
        if frame is not None:
            U.key('time', frame)
            if cv is not None:
                U.key('cam_vel', frame)
        if hole:
            hole['update'](t, state, frame)
        plaza['update'](t, frame)

    def dispose():
        if hole:
            hole['dispose']()
        K.made.dispose()
    parts = KIT.SetDict({
        'kit': K, 'uniforms': U, 'fog_node': K.fog_group(), 'fog_factor': (K.fog_group(), 'factor'),
        'fog_color': (K.fog_group(), 'color'), 'hole': hole, 'billboards': hole['parts']['billboards'] if hole else [],
        'signs': signs, 'traffic': traffic['object'], 'rain': rain['object'], 'clouds': clouds['group'],
        'sky': sky['world'], 'lamps': lamp['object'], 'meshes': meshes,
        'lights': KIT.SetDict({'hemi': sky['world'], 'moon': moon}),
        'set_lights': set_lights, 'plan': plan, 'atlas': atlas, 'plaza_screen': plaza,
        'apply_atmosphere': apply_atmosphere, 'set_focal': set_focal, 'collection': coll,
    })
    cams = {
        'dive_clouds': _static(dive_cam(4)), 'dive_crali': _static(dive_cam(16)), 'dive_canyon': _static(dive_cam(30)),
        'dive_end': _static(dive_cam(40.8)),
        'avenue': KIT.pose_to_blender({'pos': [260, STREET_Y + 9, 255], 'target': [0, STREET_Y + 30, 0], 'fov': 50}),
        'skyline': KIT.pose_to_blender({'pos': [-520, STREET_Y + 160, 420], 'target': [0, STREET_Y + 90, 0], 'fov': 45}),
    }
    for c in cams.values():
        c.pop('roll', None) if not c.get('roll') else None
    stats = {'buildings': len(built), 'signs': len(bctx['signs']), 'lamps': len(lamps), 'cars': traffic['count'],
             'build_s': _time.perf_counter() - t_start}
    print(f"[city] built {stats['buildings']} buildings, {stats['signs']} signs, {stats['lamps']} lamps in "
          f"{stats['build_s'] * 1000:.0f} ms", flush=True)
    parts['stats'] = stats

    def animate(frames=None, t0=0.0, fps=None, section=None, focal=None, power=True):
        """Key the set over film frames as the film's conductor drove it (scene.js), so the .blend plays on its own:
        the clock (song seconds t0 at frames[0], then real time), Crali's focal light (the dive's focal point in the
        intro; in the hole, her chest: focal, Blender axes, default hole.chest()), the rain's camera velocity (the
        dive's; zero in the hole) and the outro's turn-down (power 1 - 0.85 smooth((t - 300) / 24) after 294.8 s).
        section: 'dive' | 'hole' | None (by the song time: the dive to 40.8 s). frames: film frames (default the
        intro from the scene's frame_start). Returns (first, last)."""
        return animate_section(K, scene, frames, t0, fps, section, focal, power)

    def make_cameras(frames=None, t0=0.0, fps=None, scene_=None, shots=None):
        """The section's cameras, keyed into the .blend (near 0.25 m, far 6 km, the engine's). No shots: the dive,
        every frame of song seconds [t0, 40.8] from frames[0] (default the scene's frame_start). shots: chorus shots
        [(name, first frame, last frame)] (hole_cam's names, each stretched over its frames), one camera each, bound to
        timeline markers (ctx.cut with a ctx). Returns {name: camera}; the first becomes the scene's camera."""
        return make_section_cameras(K, scene_ or scene, ctx, frames, t0, fps, shots)
    return KIT.SetDict(group=root, collection=coll, parts=parts, update=update, dispose=dispose, cams=cams,
                       animate=animate, make_cameras=make_cameras)


def make_set_focal(U):
    """parts['set_focal'](pos, o=None, *, gain, radius, color, frame): Crali's light from the vanishing point (Blender
    axes): faces turned toward pos light up (keep it on the post's focal). o: city.js's options dict {gain, radius,
    color}; keywords work too. With frame, what was given is keyed."""
    def set_focal(pos, o=None, *, gain=None, radius=None, color=None, frame=None):
        if isinstance(o, (int, float)):                  # set_focal(pos, gain): the earlier positional form
            o, gain = None, o
        o = dict(o or {})
        gain = o.get('gain', gain)
        radius = o.get('radius', radius)
        color = o.get('color', color)
        U['focal_pos'] = pos
        given = ['focal_pos']
        for k, v in (('focal_gain', gain), ('focal_r', radius), ('focal_col', color)):
            if v is not None:
                U[k] = v
                given.append(k)
        if frame is not None:
            for k in given:
                U.key(k, frame)
    return set_focal


# ------------------------------------------------------------------------------------------------ sections, keyed
OUTRO_T = 294.8                        # the outro: the city turns itself down from here (scene.js)


def conductor_state(t, section=None, focal=None):
    """What the film's conductor (scene.js) gave the city and the hole at song second t: (section, focal point,
    camera velocity (both Blender axes), power)."""
    sec = section or ('dive' if t <= DIVE_LEN else 'hole')
    if sec == 'dive':
        tt = min(t, DIVE_LEN)
        fp, cv = dive_focal(tt), cam_velocity(dive_cam, tt)
    else:
        from .hole import chest
        fp, cv = (list(focal) if focal is not None else chest()), [0.0, 0.0, 0.0]
    pw = 1 - 0.85 * smooth((t - 300) / 24) if t > OUTRO_T else 1.0
    return sec, fp, cv, pw


def animate_section(K, scene, frames, t0, fps, section=None, focal=None, power=True):
    """The body of the sets' animate(): see city's build()."""
    fps = float(fps or scene.render.fps / scene.render.fps_base)
    if frames is None:
        f0 = scene.frame_start
        frames = range(f0, f0 + max(1, int(round((DIVE_LEN - t0) * fps))) + 1)
    frames = list(frames)
    U = K.U
    prev = None
    for i, f in enumerate(frames):
        t = t0 + (f - frames[0]) / fps
        sec, fp, cv, pw = conductor_state(t, section, focal)
        edge = i == 0 or i == len(frames) - 1 or sec != prev
        if sec == 'dive' or edge:              # the hole's focal and velocity hold: their ends are enough
            U.key('focal_pos', f, fp)
            U.key('cam_vel', f, cv)
        if power and (t >= OUTRO_T - 1 / fps or edge):
            U.key('power', f, pw)
        prev = sec
    key_time(K, frames[0], fps, t0, frames[-1])
    return frames[0], frames[-1]


def make_section_cameras(K, scene, ctx, frames, t0, fps, shots):
    """The body of the sets' make_cameras(): see city's build()."""
    from . import hole as H
    fps = float(fps or scene.render.fps / scene.render.fps_base)
    keyer = K.U.keyer
    out = {}

    def camera(name):
        cd = bpy.data.cameras.new(name)
        cd.clip_start, cd.clip_end = 0.25, 6000.0
        K.made.add(cd)
        ob = bpy.data.objects.new(name, cd)
        scene.collection.objects.link(ob)
        K.made.add(ob)
        return ob

    def cut(f, cam, name):
        if ctx is not None:
            ctx.cut(int(f), cam, name)
        else:
            m = scene.timeline_markers.new(name, frame=int(f))
            m.camera = cam
    if not shots:
        f0 = list(frames)[0] if frames is not None else scene.frame_start
        cam = camera('uf_cam_dive')
        a, b = key_dive(cam, None, frame_start=f0, fps=fps, t0=t0, t1=DIVE_LEN, keyer=keyer)
        cut(a, cam, 'uf_dive')
        out['dive'] = cam
    else:
        for name, fa, fb in shots:
            nm = H.HOLE_CAM_ALIASES.get(name, name)
            cam = camera(f'uf_cam_{nm}_{int(fa)}')
            H.key_hole_cam(cam, nm, frame_start=int(fa), fps=fps, dur=max(1, int(fb) - int(fa)) / fps, keyer=keyer)
            cut(fa, cam, f'uf_{nm}_{int(fa)}')
            out[nm if nm not in out else f'{nm}_{int(fa)}'] = cam
    first = next(iter(out.values()))
    if ctx is None:
        scene.camera = first
    return out


def _static(c):
    return {'pos': c['pos'], 'target': c['target'], 'fov': c['fov']}


# ------------------------------------------------------------------------------------------------ the plaza screen
PLAZA_SLOGANS = 'SUPERINTELLIGENCE BY Q3  /  TRUST THE MODEL  /  ALIGNED  /  VELOCITA  /  ACCELERATE  /  YOUR NEW EMPLOYEE  /  '


def _plaza_rays(ctx, W, H, t=0.0):
    cx, cy, R = W / 2, H / 2, W / 2
    rays = 24
    for i in range(rays):
        a0 = (i / rays) * math.pi * 2 + t * 0.12
        a1 = a0 + math.pi / rays
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.arc(cx, cy, R * 0.98, a0, a1)
        ctx.closePath()
        g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R)
        c = ['#fff4dc', '#ff8a3d'] if i % 3 == 0 else ['#ffe2b0', '#b81f66'] if i % 3 == 1 else ['#e9f3f1', '#0d3644']
        g.addColorStop(0, c[0])
        g.addColorStop(0.55, c[1])
        g.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.fillStyle = g
        ctx.fill()


def _plaza_rings(ctx, W, H, t=0.0):
    cx, cy, R = W / 2, H / 2, W / 2
    for k in range(1, 6):
        ctx.beginPath()
        ctx.arc(cx, cy, R * (0.16 * k + 0.04 * math.sin(t * 0.7 + k)), 0, math.pi * 2)
        ctx.lineWidth = W * 0.006
        ctx.strokeStyle = '#05040a' if k % 2 else '#ffcf8a'
        ctx.stroke()
    ctx.beginPath()
    ctx.arc(cx, cy, R * 0.1, 0, math.pi * 2)
    ctx.fillStyle = '#fffaf0'
    ctx.fill()


def _plaza_text(ctx, W, H, t=0.0):
    cx, cy, R = W / 2, H / 2, W / 2
    ctx.font = f'{jround(W * 0.038)}px "Rajdhani"'
    ctx.fillStyle = '#fff1d6'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    chars = list(PLAZA_SLOGANS)
    for i, ch in enumerate(chars):
        a = (i / len(chars)) * math.pi * 2 - t * 0.05
        ctx.save()
        ctx.translate(cx + math.cos(a) * R * 0.9, cy + math.sin(a) * R * 0.9)
        ctx.rotate(a + math.pi / 2)
        ctx.fillText(ch, 0, 0)
        ctx.restore()


def draw_plaza_sun(ctx, W, H, t=0.0):
    """The plaza screen's default canvas: Balla's sun (24 rays turning slowly, five rings, a white core) with a ring of
    slogans, read from above."""
    ctx.save()
    ctx.fillStyle = '#05040a'
    ctx.fillRect(0, 0, W, H)
    _plaza_rays(ctx, W, H, t)
    _plaza_rings(ctx, W, H, t)
    _plaza_text(ctx, W, H, t)
    ctx.restore()


def make_plaza_screen(K, collection, parent, *, name='uf_plaza_screen', px=1024):
    """A circular LED floor at the dive's crossing (r 34 m): the light at Crali's vanishing point. The default sun
    turns in the shader on the keyed time at the engine's 10 redraws a second (the rays and the slogans are drawn
    once each and turned; the rings and the core are drawn in the shader), so every frame renders on its own.
    set_canvas(draw) replaces it with a still canvas; set_canvas(draw, frames=..., fps=..., out_dir=...) bakes a
    redrawn one as a keyed image sequence; reset() goes back to the sun."""
    R = 34.0
    rays = KIT.make_canvas(px, px)
    rays['ctx'].fillStyle = '#05040a'
    rays['ctx'].fillRect(0, 0, px, px)
    _plaza_rays(rays['ctx'], px, px, 0.0)
    text = KIT.make_canvas(px, px)
    _plaza_text(text['ctx'], px, px, 0.0)
    img_rays = KIT.canvas_image(rays['canvas'], name + '_rays', made=K.made, alpha=False)
    img_text = KIT.canvas_image(text['canvas'], name + '_text', made=K.made)
    custom = KIT.make_canvas(px, px)
    img_custom = KIT.canvas_image(custom['canvas'], name + '_custom', made=K.made)
    m, nb = KIT.new_material(name, K)
    m.use_backface_culling = True
    gain_n = nb.new('ShaderNodeValue')
    gain_n.name = gain_n.label = 'gain'
    gain_n.outputs[0].default_value = 1.6
    cust_n = nb.new('ShaderNodeValue')
    cust_n.name = cust_n.label = 'custom'
    cust_n.outputs[0].default_value = 0.0
    gain = KIT.V(nb, gain_n.outputs[0], 'f')
    cust = KIT.V(nb, cust_n.outputs[0], 'f')
    uv = nb.uv()
    u, v = uv.x, uv.y
    tq = nb.floor(nb.U('time') * 10.0) / 10.0                  # the engine redrew the sun at 10 fps
    du, dv = u - 0.5, v - 0.5

    def rot(ang):
        c, s = nb.cos(ang), nb.sin(ang)
        return du * c - dv * s + 0.5, du * s + dv * c + 0.5
    ru, rv = rot(tq * 0.12)
    col = nb.tex(img_rays, ru, rv, extension='EXTEND')[0]
    r = nb.length(nb.comb(du, dv, 0.0))
    for k in range(1, 6):
        rk = (0.16 * k + nb.sin(tq * 0.7 + k) * 0.04) * 0.5
        mask = nb.one_minus(nb.smoothstep(0.003 - 0.0006, 0.003 + 0.0006, nb.abs(r - rk)))
        col = nb.mix(col, KIT.srgb_lin('#05040a' if k % 2 else '#ffcf8a'), mask)
    col = nb.mix(col, KIT.srgb_lin('#fffaf0'), nb.one_minus(nb.smoothstep(0.05 - 0.0006, 0.05 + 0.0006, r)))
    tu_, tv_ = rot(tq * -0.05)
    trgb, ta = nb.tex(img_text, tu_, tv_, extension='EXTEND')
    col = nb.mix(col, trgb, ta)
    crgb, _ = nb.tex(img_custom, u, v, extension='EXTEND')
    col = nb.mix(col, crgb, cust)
    # the LED grid: a fine pixel grid at close range, resolved by the footprint of a pixel
    cells_u, cells_v = u * (px / 3), v * (px / 3)
    gu, gv = nb.fract(cells_u), nb.fract(cells_v)
    mpp = nb.view_distance() * nb.U('pix') / nb.max(nb.abs(nb.geo('Incoming').z), 0.05)
    fw = mpp * (px / 3) / (2 * R)
    led = nb.mix(nb.step(0.15, gu) * nb.step(0.15, gv) * 0.45 + 0.55, 0.8, nb.smoothstep(0.25, 0.7, fw))
    on = nb.smoothstep(0.62, 0.66, nb.U('power'))
    KIT.out_basic(nb, col * (gain * led * on * nb.U('neon')))
    P, F, cuv = circle_geometry(R, 96, 0.0)
    me = KIT.make_mesh(name, P, F, uv=cuv, made=K.made)
    me.materials.append(m)
    mesh = KIT.new_object(name, me, collection, parent=parent, made=K.made)
    mesh.location = KIT.to_blender((DIVE_C3[0], STREET_Y + 0.035, DIVE_C3[2]))
    mesh['assembly'] = 'uf_plaza'
    # its kerb: a dark metal ring the screen is set into
    P, Q, tuv = torus_geometry(R + 0.25, 0.3, 6, 96)
    P = np.stack([P[:, 0], -P[:, 2], P[:, 1]], 1)           # rotation.x = pi/2: the ring lies flat
    rme = KIT.make_mesh(name.replace('screen', 'rim'), P, Q, uv=tuv, smooth=True, made=K.made)
    KIT.frame_attrs(rme)
    rme.materials.append(K.mat['frame'])
    rim = KIT.new_object('uf_plaza_rim', rme, collection, parent=parent, made=K.made)
    rim.location = KIT.to_blender((DIVE_C3[0], STREET_Y + 0.05, DIVE_C3[2]))
    rim['assembly'] = 'uf_plaza'
    state = {'custom': False}
    flag_path = f'nodes["{cust_n.name}"].outputs[0].default_value'

    def key_flag(frame):                                       # a step: the canvas switches on a frame, as a cut
        KIT.key_prop(m.node_tree, flag_path, frame, 'CONSTANT', K.U.keyer)

    def set_canvas(draw, frames=None, fps=None, out_dir=None, frame_start=None, frame=None):
        """draw(ctx, w, h) paints the whole canvas (a still); with frames (film frames, at fps) draw(ctx, w, h, t) is
        baked as a keyed image sequence into out_dir. frame: the canvas replaces the sun from that frame on (keyed)."""
        if frame is not None and not state['custom']:
            key_flag(frame - 1)                                # the sun until then
        state['custom'] = True
        cust_n.outputs[0].default_value = 1.0
        if frame is not None:
            key_flag(frame)
        if frames is None:
            c = custom['ctx']
            c.clearRect(0, 0, px, px)
            draw(c, px, px)
            KIT.canvas_image(custom['canvas'], name + '_custom', made=K.made, image=img_custom)
        else:
            seq = bake_canvas_sequence(K, name + '_custom_seq', px, px, draw, frames, fps, out_dir, frame_start)
            _set_image(m, img_custom, seq)

    def reset(frame=None):
        """Back to Balla's sun (from frame on, keyed, when given; the custom canvas holds until then)."""
        if frame is not None and state['custom']:
            key_flag(frame - 1)
        state['custom'] = False
        cust_n.outputs[0].default_value = 0.0
        if frame is not None:
            key_flag(frame)

    def update(t, frame=None):
        return None                                           # the sun turns in the shader on the keyed time
    return KIT.SetDict({'mesh': mesh, 'rim': rim, 'canvas': custom['canvas'], 'ctx': custom['ctx'],
                        'texture': img_custom, 'material': m, 'gain': gain_n.outputs[0], 'px': [px, px],
                        'set_canvas': set_canvas, 'reset': reset, 'update': update,
                        'layers': {'rays': img_rays, 'text': img_text}})


def _set_image(mat, old, new):
    from ...media import screens as SC
    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image == old:
            n.image = new
            SC.configure_user(n.image_user, new)


def bake_canvas_sequence(K, name, w, h, draw, frames, fps, out_dir, frame_start=None):
    """A canvas redrawn over the film, as a numbered PNG sequence keyed to frames (the engine re-uploaded its
    CanvasTexture). frames: film frame numbers; draw(ctx, w, h, t) with t = (frame - frames[0]) / fps (+ the
    frame_start offset when given, in seconds). out_dir may be blend-relative ('//uf_screens': beside the saved .blend,
    as the media family reads it; in a file not saved yet, that is the working folder). Returns the image
    (media.screens' sequence loader: a hold file before the range, the last file after it)."""
    from pathlib import Path
    from ...media import screens as SC
    if out_dir is None:
        raise ValueError('bake_canvas_sequence: out_dir (where the PNG sequence lives) is required')
    out_dir = str(out_dir)
    if out_dir.startswith('//'):
        if not bpy.data.filepath:
            print(f'[city] {out_dir}: the .blend is not saved yet, so the sequence goes under the working folder',
                  flush=True)
        out_dir = bpy.path.abspath(out_dir)
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    frames = list(frames)
    for i, f in enumerate(frames):
        c = KIT.make_canvas(w, h)
        t = (f - frames[0]) / float(fps or 24) + float(frame_start or 0.0)
        draw(c['ctx'], w, h, t)
        c['canvas'].save_png(str(out / f'{name}_{i + 1:04d}.png'))
    img = SC._load_sequence(out / f'{name}_0001.png', frames[0], len(frames), name)
    K.made.add(img)
    return img


# ------------------------------------------------------------------------------------------------ THE DIVE
# dive_cam(t), t = song seconds 0..40.8: Tullio Crali's "Incuneandosi nell'abitato" (1939). Falling out of the low rain
# clouds over the crossing of grand avenue 45 degrees and the first ring road, a nose-dive that circles that crossing
# ever tighter and faster while the towers radiate from the vanishing point below, down between the towers, then the
# pull-out: levelling into the avenue at ~15 m, flying toward the hole, which ends the shot framed at the avenue's end.
DIVE = {
    # helix around the crossing: [t, radius, angle (deg), height above street]
    'helix': [{'t': 0, 'v': [118, -430, 508]}, {'t': 6, 'v': [104, -398, 430]}, {'t': 10, 'v': [92, -372, 352]},
              {'t': 15, 'v': [80, -338, 322]}, {'t': 20, 'v': [66, -300, 292]}, {'t': 24, 'v': [44, -230, 222]},
              {'t': 28, 'v': [24, -128, 148]}, {'t': 31, 'v': [12, -20, 92]}, {'t': 33, 'v': [7, 45, 58]}],
    'fov': [{'t': 0, 'v': [64]}, {'t': 9, 'v': [70]}, {'t': 20, 'v': [72]}, {'t': 30, 'v': [80]}, {'t': 34, 'v': [74]},
            {'t': 40.8, 'v': [56]}],
    'roll': [{'t': 0, 'v': [0]}, {'t': 12, 'v': [-6]}, {'t': 22, 'v': [5]}, {'t': 28, 'v': [-9]}, {'t': 33, 'v': [0]},
             {'t': 40.8, 'v': [0]}],
}
DEG = math.pi / 180
DIVE_LEN = 40.8


def helix_at(t):
    R, phd, h = keyed(DIVE['helix'], min(t, 33), smoother)
    ph = (phd + 135) * DEG           # +135: the helix's last tangent points along the avenue toward the hole
    return [DIVE_C3[0] + R * math.cos(ph), STREET_Y + h, DIVE_C3[2] + R * math.sin(ph)]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _norm(a):
    l = math.hypot(a[0], a[1], a[2]) or 1
    return [a[0] / l, a[1] / l, a[2] / l]


def dive_cam_three(t):
    """The dive in three's axes, exactly as city.js's diveCam: {'pos', 'target', 'fov', 'roll', 'up'}."""
    t = max(0.0, min(DIVE_LEN, t))
    fov = keyed(DIVE['fov'], t)[0]
    roll = keyed(DIVE['roll'], t)[0] * DEG
    inward = [-math.cos(DIVE_AV), 0, -math.sin(DIVE_AV)]
    if t <= 33:
        pos = helix_at(t)
    else:                            # pull-out: cubic Hermite from the helix (matching its velocity) to the avenue's end
        p0 = helix_at(33)
        hb = helix_at(32.9)
        v0 = [(p0[i] - hb[i]) / 0.1 for i in range(3)]
        r_end = 104
        p1 = [DIVE_C3[0] + inward[0] * (RINGS[0]['r'] - r_end), STREET_Y + 15, DIVE_C3[2] + inward[2] * (RINGS[0]['r'] - r_end)]
        v1 = [inward[0] * 4, -0.6, inward[2] * 4]
        T = 7.8
        u = (t - 33) / T
        h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
        h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        pos = [h00 * p0[i] + h10 * T * v0[i] + h01 * p1[i] + h11 * T * v1[i] for i in range(3)]
    # where she looks: early, ahead and down into the murk; then the crossing (steeper than the line to it: Crali's
    # nadir); in the pull-out, the hole at the avenue's end
    C = DIVE_C3
    to_c = [C[0] - pos[0], 0, C[2] - pos[2]]
    ahead = [pos[0] + inward[0] * 240, STREET_Y, pos[2] + inward[2] * 240]
    nadir = [pos[0] + to_c[0] * 0.55, STREET_Y, pos[2] + to_c[2] * 0.55]
    kA = smooth((t - 3) / 8)
    tgt = [lerp(a, nadir[i], kA) for i, a in enumerate(ahead)]
    hole_t = [0, STREET_Y + 26, 0]
    kD = smoother((t - 33.5) / 6.0)
    dA, dB = _norm(_sub(tgt, pos)), _norm(_sub(hole_t, pos))
    d = _norm([lerp(a, dB[i], kD) for i, a in enumerate(dA)])
    target = [p + d[i] * 100 for i, p in enumerate(pos)]
    # image-up: the direction of horizontal travel while looking down (an aviator's view), world-up when level
    pa = helix_at(max(0.0, t - 0.05)) if t <= 33 else pos
    pb = helix_at(t + 0.05) if t <= 33 else pos
    hv = [pb[0] - pa[0], 0, pb[2] - pa[2]]
    if math.hypot(hv[0], hv[2]) < 1e-4 or t > 33:
        hv = list(inward)
    hv = _norm(hv)
    kU = smooth((d[1] + 0.55) / 0.5)
    up = _norm([lerp(h, 1 if i == 1 else 0, kU) for i, h in enumerate(hv)])
    return {'pos': pos, 'target': target, 'fov': fov, 'roll': roll, 'up': up}


def dive_cam(t):
    """The intro dive (song seconds 0..40.8) in Blender axes: {'pos', 'target', 'fov', 'roll', 'up'}; apply it with
    apply_cam(camera, dive_cam(t)) or key it with key_dive."""
    return KIT.pose_to_blender(dive_cam_three(t))


def dive_focal_three(t):
    k = smoother((t - 33.5) / 5.5)
    return [DIVE_C3[0] * (1 - k), lerp(STREET_Y + 18, 26, k), DIVE_C3[2] * (1 - k)]


def dive_focal(t):
    """The dive's focal point (Blender axes), for the post's sun cones AND set_focal: the crossing below, then the
    hole."""
    return KIT.to_blender(dive_focal_three(t))


def camera_velocity(t):
    return cam_velocity(dive_cam, t)


def key_dive(camera, K=None, *, frame_start=1, fps=24.0, t0=0.0, t1=DIVE_LEN, focal=True, step=1, keyer=None):
    """Key the intro on a camera: every frame of song seconds [t0, t1] from frame_start, LINEAR; with K, also the
    kit's clock, the rain's camera velocity and Crali's focal light (dive_focal). keyer: the harness's ctx.key (by
    default the kit's, when the set was built with a ctx). Returns the frame range."""
    keyer = keyer or (K.U.keyer if K is not None else None)
    n = int(round((t1 - t0) * fps))
    frames = list(range(frame_start, frame_start + n + 1, step))
    if frames[-1] != frame_start + n:
        frames.append(frame_start + n)
    for f in frames:
        t = t0 + (f - frame_start) / fps
        apply_cam(camera, dive_cam(t), frame=f, keyer=keyer)
        if K is not None:
            K.U.key('cam_vel', f, cam_velocity(dive_cam, t))
            if focal:
                K.U.key('focal_pos', f, dive_focal(t))
    if K is not None:
        key_time(K, frame_start, fps, t0)
    return frames[0], frames[-1]


def key_time(K, frame_start, fps, t0=0.0, frame_end=None):
    """The kit's clock as two LINEAR keys with linear extrapolation: song seconds t0 at frame_start, then real time."""
    frame_end = frame_end if frame_end is not None and frame_end > frame_start else frame_start + max(1, int(fps * 10))
    K.U.key('time', frame_start, t0)
    K.U.key('time', frame_end, t0 + (frame_end - frame_start) / fps)
    ad = K.U.tree.animation_data
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    for fc in cb.fcurves:
        if fc.data_path == 'nodes["u_time"].outputs[0].default_value':
            fc.extrapolation = 'LINEAR'
