"""create_flora: the VEGETATION BRUSH, Blender 5.2 EEVEE edition (port of eidoverse/vegetation.js).

One call paints one stand (a "stroke") of one species: the plant is grown ONCE per stroke by the species' generator
(seeded, so strokes differ by seed), placed by the same jittered-grid / row / explicit placement as the WebGPU
edition (same seed -> same stand), instanced by geometry nodes, and moved by the same 3-layer wind and character
pushers, evaluated in geometry nodes from Scene Time so the deformation is real geometry: EEVEE's Vector pass and
motion blur see it, and a saved .blend renders any frame in a fresh background Blender (no handlers, no drivers that
need Python).

    from eidoblend.flora import create_flora
    f = create_flora(species='grass', size=30, height=0.45, color='green', height_fn=terrain_z)
    d = create_flora(species='daisy', size=12, center=(2, 1), color={'white': 3, 'orange': 2}, seed=5)
    f.set_pushers([(walker_armature, 'foot.L'), (walker_armature, 'foot.R')], radius=0.5)

This module is the planning half (species, generators, placement) and runs without bpy, so parity_check.py can
compare it against the JS in a plain Python. Blender objects, geometry nodes and materials are built by
create_flora through nodes.py.

Coordinates: the API takes Blender coordinates (Z up, metres). Internally the generators and the placement run
verbatim in the WebGPU edition's three.js space (Y up) and convert once at the boundary: three (x, y, z) -> Blender
(x, -z, y).
"""
import json
import math
import os

import numpy as np

from .jsmath import lehmer, value_noise_2d, js_round, smoothstep, js_num
from .plantgeo import PlantGeo, vertex_normals, blend_normals_up, C3B

HERE = os.path.dirname(os.path.abspath(__file__))


def repo_root():
    """The eidoverse-video checkout this package lives in (the folder holding eido.py)."""
    d = HERE
    for _ in range(8):
        if os.path.exists(os.path.join(d, 'eido.py')):
            return d
        d = os.path.dirname(d)
    raise FileNotFoundError('[flora] no eido.py above ' + HERE)


def asset_dir():
    return os.path.join(repo_root(), 'eidoverse', 'assets', 'grass')


# grass colours, the seasonal palette, one word each. The green family are MULTIPLIERS over the blade atlas; the
# rest are luminance RECOLORS (hue from the target, detail from the atlas luminance). Normalized against the blade
# atlas's opaque mean (91/138/35 sRGB) so luminance stays in range.
GRASS_COLORS = {
    'lime': [1.15, 1.13, 0.48],
    'emerald': [0.56, 1.04, 0.61],
    'blue': [0.64, 1.05, 1.61],
    'blue-green': [0.6, 1.07, 1.18],
    'green': {'recolor': [0.755, 1.145, 0.29]},
    'gray-green': {'recolor': [0.92, 0.97, 0.83]},
    'burgundy': {'recolor': [1.95, 0.57, 0.81]},
    'rust': {'recolor': [1.93, 0.79, 0.32]},
    'copper': {'recolor': [1.72, 0.93, 0.3]},
    'orange': {'recolor': [1.83, 0.98, 0.19]},
    'straw': {'recolor': [1.35, 1.14, 0.64]},
    'brown': {'recolor': [1.24, 0.91, 0.52]},
}

# the species registry, verbatim from vegetation.js (field-approved values)
FLORA_SPECIES = {
    'grass': {
        'archetype': 'blades', 'maps': 'blades_meadow',
        'blades': {'perBunch': 8, 'bunchR': 0.5, 'h': 0.38, 'w': 0.042, 'lean': 0.42},
        'baseScale': [0.8, 1.3], 'density': 22.0, 'clump': 1.0,
        'wind': {'base': 0.35, 'gust': 0.7, 'gustFreq': 0.3, 'flutter': 0.5},
        'sss': 0.5, 'rough': 0.6, 'pushScale': 1.0,
    },
    'galleta_dry': {
        'archetype': 'blades', 'maps': 'blades_meadow',
        'leafRecolor': GRASS_COLORS['straw']['recolor'],
        'blades': {'perBunch': 34, 'bunchR': 0.26, 'h': 0.44, 'w': 0.036, 'lean': 0.75},
        'baseScale': [0.7, 1.25], 'density': 0.9, 'clump': 0.55,
        'wind': {'base': 0.28, 'gust': 0.5, 'gustFreq': 0.3, 'flutter': 0.7},
        'sss': 0.55, 'rough': 0.7, 'pushScale': 1.0,
    },
    'blackbrush': {
        'archetype': 'shrub', 'gen': 'blackbrush', 'maps': 'blackbrush',
        'stem': 'blackbrush_stem', 'stemColor': 0x6D5A46, 'stemTint': [1.7, 1.75, 1.6],
        'footRadius': 0.75, 'baseScale': [0.7, 1.25], 'density': 0.06, 'clump': 0.5,
        'wind': {'base': 0.06, 'gust': 0.14, 'gustFreq': 0.3, 'flutter': 1.1},
        'sss': 0.35, 'rough': 0.9, 'pushScale': 0.4,
    },
    'creosote': {
        'archetype': 'shrub', 'gen': 'creosote', 'maps': 'creosote',
        'stem': 'creosote_stem', 'stemColor': 0x8A7358, 'stemTint': [2.6, 2.7, 1.7],
        'footRadius': 1.1, 'baseScale': [0.7, 1.3], 'density': 0.035, 'clump': 0.3,
        'wind': {'base': 0.10, 'gust': 0.22, 'gustFreq': 0.3, 'flutter': 1.3},
        'sss': 0.45, 'rough': 0.85, 'pushScale': 0.7,
    },
    'sagebrush': {
        'archetype': 'shrub', 'gen': 'sagebrush', 'maps': 'sagebrush',
        'stem': 'blackbrush_stem', 'stemColor': 0x8B8378, 'stemTint': [3.2, 3.5, 3.3],
        'footRadius': 0.65, 'baseScale': [0.75, 1.3], 'density': 0.05, 'clump': 0.45,
        'wind': {'base': 0.08, 'gust': 0.18, 'gustFreq': 0.3, 'flutter': 1.0},
        'sss': 0.4, 'rough': 0.9, 'pushScale': 0.45,
    },
    'yucca': {
        'archetype': 'yucca', 'maps': 'yucca_kit',
        'rosette': {'r': 0.55, 'spikes': 64},
        'footRadius': 0.6, 'baseScale': [1.0, 1.6], 'density': 0.10, 'clump': 0.15,
        'wind': {'base': 0.03, 'gust': 0.06, 'gustFreq': 0.3, 'flutter': 0.5},
        'sss': 0.5, 'rough': 0.8, 'pushScale': 0.12,
    },
    'corn': {
        'archetype': 'corn', 'maps': 'corn',
        'corn': {'height': 2.3, 'leaves': 10, 'leafLen': 0.95, 'ears': 3, 'peel': False},
        'regionTint': {'u0': 0.5, 'u1': 1.0, 'v0': 0.7, 'v1': 1.0, 'mul': [1.9, 2.7, 2.2]},
        'footRadius': 0.32, 'baseScale': [0.88, 1.14], 'density': 1.4, 'clump': 0.85,
        'wind': {'base': 0.05, 'gust': 0.11, 'gustFreq': 0.3, 'flutter': 1.2},
        'sss': 0.55, 'rough': 0.75, 'pushScale': 0.55,
    },
    'sunflower': {
        'archetype': 'sunflower', 'maps': 'sunflower',
        'sunflower': {'height': 1.9, 'leaves': 11, 'leafLen': 0.62, 'headR': 0.20, 'petals': 26},
        'footRadius': 0.3, 'baseScale': [0.9, 1.12], 'density': 1.2, 'clump': 0.8,
        'wind': {'base': 0.04, 'gust': 0.09, 'gustFreq': 0.3, 'flutter': 0.8},
        'sss': 0.5, 'rough': 0.8, 'pushScale': 0.4,
    },
    'daisy': {
        'archetype': 'daisy', 'maps': 'daisy',
        'daisy': {'height': 0.45, 'headD': 0.05, 'headScale': 1},
        'baseScale': [0.85, 1.15], 'density': 12, 'clump': 0.42,
        'wind': {'base': 0.018, 'gust': 0.035, 'gustFreq': 0.3, 'flutter': 0.12},
        'sss': 0.6, 'rough': 1.0, 'pushScale': 0.8,
    },
}


# Scanned plants (CC0 Poly Haven .blend sets) for mixing with our own species: create_flora('ph:<asset>', ...) places
# them with the same brush (placement, wind, pushers), one variant mesh picked per plant. They keep their own
# scanned materials. Habit values are this edition's (real-size scans: no scale-up), by plant kind.
SCANNED_DIR_ENV = 'EIDOBLEND_PH_ASSETS'
SCANNED_SPECIES = {
    'grass_medium_01': {'kind': 'grass'}, 'grass_medium_02': {'kind': 'grass'},
    'celandine_01': {'kind': 'herb'}, 'dandelion_01': {'kind': 'herb'},
    'shrub_sorrel_01': {'kind': 'groundcover'}, 'weed_plant_02': {'kind': 'weed'},
}
SCANNED_KINDS = {
    'grass': {'baseScale': [0.85, 1.2], 'density': 28.0, 'clump': 0.8,
              'wind': {'base': 0.22, 'gust': 0.45, 'gustFreq': 0.3, 'flutter': 0.45}, 'pushScale': 1.0},
    'herb': {'baseScale': [0.85, 1.15], 'density': 3.0, 'clump': 0.45,
             'wind': {'base': 0.02, 'gust': 0.04, 'gustFreq': 0.3, 'flutter': 0.15}, 'pushScale': 0.8},
    'weed': {'baseScale': [0.85, 1.15], 'density': 1.5, 'clump': 0.45,
             'wind': {'base': 0.05, 'gust': 0.1, 'gustFreq': 0.3, 'flutter': 0.5}, 'pushScale': 0.7},
    # a carpet of small clover-like rosettes (shrub_sorrel_01: 2-6 cm tall, 3-7 cm across), patchy
    'groundcover': {'baseScale': [0.85, 1.2], 'density': 40.0, 'clump': 0.3,
                    'wind': {'base': 0.006, 'gust': 0.012, 'gustFreq': 0.3, 'flutter': 0.05}, 'pushScale': 0.25},
}


def scanned_dir():
    """Where the Poly Haven plant sets live: $EIDOBLEND_PH_ASSETS, else the fetch folder in the main checkout
    (work/claude_body/film/tools/dlss5nr/bmeadow/assets, fetched with its fetch_ph.py)."""
    d = os.environ.get(SCANNED_DIR_ENV)
    if d:
        return d
    main = os.path.join(os.path.dirname(repo_root()), 'eidoverse-video-prealpha-0.01')
    return os.path.join(main, 'work', 'claude_body', 'film', 'tools', 'dlss5nr', 'bmeadow', 'assets')


BLADE_HABITS = {
    # narrow meadow blades for close shots: a third of the card width, about three times the blades per plant
    'fine': {'w': 0.014, 'perBunch': 22, 'bunchR': 0.35},
}


def _camel(d):
    """Lookdev sub-dicts (corn={...}, sunflower={...}, daisy={...}) in snake_case -> the generators' camelCase."""
    out = {}
    for k, v in (d or {}).items():
        head, *rest = k.split('_')
        out[head + ''.join(w[:1].upper() + w[1:] for w in rest)] = v
    return out


def _load_json(name):
    try:
        with open(os.path.join(asset_dir(), name), encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ── blade cards (the Halo hybrid): segmented planes fitted to an individual-blade alpha atlas ─────────────────────
def bunch_geometry(spec, rng, fit):
    b = spec['blades']
    perBunch, bunchR, h, w, lean = b['perBunch'], b['bunchR'], b['h'], b['w'], b['lean']
    COLS = 8
    cardW = w * 2
    pos, aH, uv, idx = [], [], [], []
    vb = 0
    LOOPS = 4
    for _ in range(perBunch):
        ang, rad = rng() * math.pi * 2, math.sqrt(rng()) * bunchR
        bx, bz = math.cos(ang) * rad, math.sin(ang) * rad
        bh = h * (0.6 + rng() * 0.8)
        bw = cardW * (0.85 + rng() * 0.4)
        roll = rng() * math.pi * 2
        leanAmt = (0.25 + rng() * 0.75) * lean * bh
        cr, sr = math.cos(roll), math.sin(roll)
        c = math.floor(rng() * COLS)
        bands = fit[c] if fit else None
        s0 = vb
        for lp in range(LOOPS + 1):
            t = lp / LOOPS
            fcx, fhw = bands[lp] if bands else (0, 0.5)
            bend = leanAmt * t * t
            artC = fcx * bw
            px, pz = bx + cr * (bend + artC), bz + sr * (bend + artC)
            py = t * bh
            hwW = fhw * bw
            pos += [(px - sr * hwW, py, pz + cr * hwW), (px + sr * hwW, py, pz - cr * hwW)]
            uv += [((c + 0.5 + fcx - fhw) / COLS, t), ((c + 0.5 + fcx + fhw) / COLS, t)]
            aH += [t, t]
            vb += 2
        for lp in range(LOOPS):
            a = s0 + lp * 2
            idx += [a, a + 1, a + 2, a + 1, a + 3, a + 2]
    P = np.array(pos)
    T = np.array(idx).reshape(-1, 3)
    N = blend_normals_up(vertex_normals(P, T), 1.0)       # blades: normals straight up, lit like the ground plane
    # Blender edition: -1 / +1 at each loop's two edges (u runs across the blade), for the shader's blade curl
    across = np.tile([-1.0, 1.0], len(P) // 2)
    return PlantGeo(P, uv, aH, T, N, {'across': across})


# ── quaternion helpers with three.js semantics (the yucca uses setFromUnitVectors + applyQuaternion) ─────────────
def _q_from_unit_vectors(f, t):
    r = f[0] * t[0] + f[1] * t[1] + f[2] * t[2] + 1
    if r < 1e-8:                     # three r184's epsilon (#31286)
        r = 0
        if abs(f[0]) > abs(f[2]):
            q = [-f[1], f[0], 0.0, r]
        else:
            q = [0.0, -f[2], f[1], r]
    else:
        q = [f[1] * t[2] - f[2] * t[1], f[2] * t[0] - f[0] * t[2], f[0] * t[1] - f[1] * t[0], r]
    ln = math.sqrt(sum(x * x for x in q))
    return [x / ln for x in q] if ln else [0.0, 0.0, 0.0, 1.0]


def _q_apply(v, q):
    vx, vy, vz = v
    qx, qy, qz, qw = q
    tx, ty, tz = 2 * (qy * vz - qz * vy), 2 * (qz * vx - qx * vz), 2 * (qx * vy - qy * vx)
    return [vx + qw * tx + qy * tz - qz * ty, vy + qw * ty + qz * tx - qx * tz, vz + qw * tz + qx * ty - qy * tx]


def _v_norm(v):
    ln = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1
    return [v[0] / ln, v[1] / ln, v[2] / ln]


# ── Mojave yucca (Yucca schidigera): golden-spiral crown of V-folded bayonets, dried skirt, bendy thatched trunk ──
def yucca_geometry(spec, rng):
    r, spikes = spec['rosette']['r'], spec['rosette']['spikes']
    pos, uv, aH, idx = [], [], [], []
    st = {'vb': 0}
    YUP = [0.0, 1.0, 0.0]
    GA = 2.399963
    LIVE, DRY, BARK = (0.012, 0.32), (0.345, 0.655), (0.67, 0.996)
    trunkH = 0.22 + rng() * 0.28
    trunkR = 0.06 + rng() * 0.02
    bendA = rng() * math.pi * 2
    bendAmt = (0.1 + rng() * 0.55) * trunkH
    bcx, bcz = math.cos(bendA) * bendAmt, math.sin(bendA) * bendAmt

    def trunk_point(t):
        return [bcx * t * t, t * trunkH, bcz * t * t]

    def q_at(t):
        return _q_from_unit_vectors(YUP, _v_norm([2 * bcx * t, trunkH, 2 * bcz * t]))

    def spike(yaw, pitch, length, u0, u1, bx, by, bz, droopK, qRot):
        w0 = length * 0.145 * (0.9 + rng() * 0.3)
        A = [math.cos(yaw) * math.cos(pitch), math.sin(pitch), math.sin(yaw) * math.cos(pitch)]
        S = [-math.sin(yaw), 0.0, math.cos(yaw)]
        UPL = [0.0, 1.0, 0.0]
        if qRot:
            A, S, UPL = _q_apply(A, qRot), _q_apply(S, qRot), _q_apply(UPL, qRot)
        segs, s0 = 3, st['vb']
        for sg in range(segs + 1):
            t = sg / segs
            wHere = w0 * (1 - t * 0.94)
            droop = droopK * length * t * t
            cxp, cyp, czp = bx + A[0] * length * t, by + A[1] * length * t + droop, bz + A[2] * length * t
            foldUp = wHere * 0.55
            pos.append((cxp - S[0] * wHere, cyp - S[1] * wHere, czp - S[2] * wHere)); uv.append((u0, t)); aH.append(t * 0.3)
            pos.append((cxp + UPL[0] * foldUp, cyp + UPL[1] * foldUp, czp + UPL[2] * foldUp)); uv.append(((u0 + u1) / 2, t)); aH.append(t * 0.3)
            pos.append((cxp + S[0] * wHere, cyp + S[1] * wHere, czp + S[2] * wHere)); uv.append((u1, t)); aH.append(t * 0.3)
            st['vb'] += 3
        for sg in range(segs):
            a = s0 + sg * 3
            b = a + 3
            idx.extend((a, a + 1, b, a + 1, b + 1, b, a + 1, a + 2, b + 1, a + 2, b + 2, b + 1))

    # trunk: rings along the arc, base sunk below grade, real thatch skin
    n, rings, s0 = 10, 4, st['vb']
    for g in range(rings + 1):
        t = g / rings
        cx, cy, cz = trunk_point(t)
        rad = trunkR * (1.12 - 0.27 * t)
        y = -0.05 if g == 0 else cy
        for i in range(n + 1):
            a = (i / n) * math.pi * 2
            u = BARK[0] + (BARK[1] - BARK[0]) * (i / n)
            pos.append((cx + math.cos(a) * rad, y, cz + math.sin(a) * rad))
            uv.append((u, 0.02 + t * trunkH * 0.9))
            aH.append(0.0)
            st['vb'] += 1
    for g in range(rings):
        for i in range(n):
            a = s0 + g * (n + 1) + i
            b = a + n + 1
            idx.extend((a, b, a + 1, a + 1, b, b + 1))
    tx, ty, tz = trunk_point(1)
    cTop = st['vb']
    pos.append((tx, ty + 0.01, tz)); uv.append(((BARK[0] + BARK[1]) / 2, 0.6)); aH.append(0.0); st['vb'] += 1
    lastRing = s0 + rings * (n + 1)
    for i in range(n):
        idx.extend((lastRing + i, cTop, lastRing + i + 1))

    # dried skirt: dense, in a tight band just under the crown, downswept, following the arc's local frame
    nSkirt = js_round(spikes * 0.8)
    for i in range(nSkirt):
        tS = i / nSkirt
        yaw = i * GA + rng() * 0.3
        hFrac = min(1, 0.72 + 0.26 * tS + rng() * 0.04)
        cx, cy, cz = trunk_point(hFrac)
        qR = q_at(hFrac)
        pitch = -(0.35 + rng() * 0.8)
        length = r * (0.3 + 0.2 * tS + rng() * 0.14)
        col = BARK if tS < 0.35 else DRY
        RAD = _q_apply([math.cos(yaw) * trunkR * 0.9, 0.0, math.sin(yaw) * trunkR * 0.9], qR)
        spike(yaw, pitch, length, col[0], col[1], cx + RAD[0], cy + RAD[1], cz + RAD[2], -0.28, qR)

    # live crown: golden-spiral spherical burst riding the arc's end tangent
    qTop = q_at(1)
    tpx, tpy, tpz = trunk_point(1)
    for i in range(spikes):
        t = (i + 0.5) / spikes
        yaw = i * GA + rng() * 0.25
        pitch = 1.45 - t * 2.1 + rng() * 0.12
        baseR = trunkR * (0.15 + 0.8 * math.sqrt(t))
        hDome = 0.02 + 0.055 * (1 - t * t)
        length = r * (0.6 + 0.42 * math.sin(min(math.pi, (0.25 + t * 0.75) * math.pi)) + rng() * 0.12)
        RAD = _q_apply([math.cos(yaw) * baseR, hDome, math.sin(yaw) * baseR], qTop)
        spike(yaw, pitch, length, LIVE[0], LIVE[1], tpx + RAD[0], tpy + RAD[1], tpz + RAD[2], -0.04, qTop)
    P = np.array(pos)
    T = np.array(idx).reshape(-1, 3)
    return PlantGeo(P, uv, aH, T, blend_normals_up(vertex_normals(P, T), 0.35))


# ── cross-field occupancy: structural plants claim their canopy footprint ─────────────────────────────────────────
_placed_plants = []


def reset_flora_occupancy():
    _placed_plants.clear()


def _occupancy_conflict(x, z, r):
    for (px, pz, pr) in _placed_plants:
        rr = (r + pr) * 0.75
        dx, dz = x - px, z - pz
        if dx * dx + dz * dz < rr * rr:
            return True
    return False


# ── placement: jittered grid, feathered elliptical rim + stragglers, organic lobes, clump / bare-patch noise ──────
def place_instances(o, spec):
    seed = 7 if o.get('seed') is None else o['seed']
    rng = lehmer(seed * 2654435761, 16807)
    noise = value_noise_2d(seed)
    W, D, cx, cz = o['width'], o['depth'], o['center'][0], o['center'][1]
    organic = o.get('footprint') == 'organic'
    step = 1 / math.sqrt(spec['density'] * (1 if o.get('density') is None else o['density']) * (1.45 if organic else 1))
    out = []
    EXT = 1.25
    clip = o.get('clip_fn')
    gx = -W * EXT / 2
    while gx < W * EXT / 2:
        gz = -D * EXT / 2
        while gz < D * EXT / 2:
            x = cx + gx + (rng() - 0.5) * step
            z = cz + gz + (rng() - 0.5) * step
            gz += step
            if clip and clip(x, z):
                continue
            r = math.sqrt(((x - cx) / (W / 2)) ** 2 + ((z - cz) / (D / 2)) ** 2)
            if r > EXT:
                continue
            if r > 1:
                if rng() > 0.055 * (1 - (r - 1) / (EXT - 1)):
                    continue
            elif rng() < smoothstep(0.82, 1.04, r):
                continue
            if organic:
                f = 3.4 / max(W, D)
                m = noise(x * f + 31.7, z * f + 17.3)
                if m < 0.4 + 0.28 * min(1, r):
                    continue
            dN = noise(x * 0.05, z * 0.05)
            if dN < 0.5 - spec['clump'] and rng() < 0.85:
                continue
            p = finish_placement(x, z, o, spec, rng, step, True)
            if p:
                out.append(p)
        gx += step
    return out


def finish_placement(x, z, o, spec, rng, step, self_check):
    ntx = ntz = 0.0
    surf = o.get('_surface_at')
    if surf:
        hit = surf(x, z)
        if not hit:
            return None
        if o.get('max_slope') and hit['slope'] > o['max_slope']:
            return None
        y = hit['y']
        k = o['_align']
        if k > 0:
            ntx = math.atan2(hit['nz'], hit['ny']) * k
            ntz = -math.atan2(hit['nx'], hit['ny']) * k
    else:
        hf = o.get('height_fn')
        y = hf(x, z) if hf else o.get('y', 0.0)
        if hf and o.get('max_slope'):
            eps = step * 0.5
            sx, sz = (hf(x + eps, z) - y) / eps, (hf(x, z + eps) - y) / eps
            if math.atan(math.hypot(sx, sz)) > o['max_slope']:
                return None
    s0, s1 = spec['baseScale']
    scale = s0 + rng() * (s1 - s0)
    if spec.get('footRadius') and o.get('avoid') is not False:
        rr = spec['footRadius'] * scale
        if self_check and _occupancy_conflict(x, z, rr):
            return None
        _placed_plants.append((x, z, rr))
    leanAz, lean = rng() * math.pi * 2, (rng() - 0.5) * 0.16
    spin = rng()
    yaw = heading_yaw(o, x, z, spin)
    return {'x': x, 'y': y, 'z': z, 'yaw': yaw, 'scale': scale, 'tilt': 0.0,
            'tx': ntx + math.cos(leanAz) * lean, 'tz': ntz + math.sin(leanAz) * lean,
            'colorVar': rng(), 'phase': rng() * math.pi * 2}


def heading_yaw(o, x, z, spin):
    jit = (spin - 0.5) * 2 * (0.15 if o.get('heading_jitter') is None else o['heading_jitter'])
    if o.get('heading_target') is not None:
        t = o['heading_target']
        return math.atan2(t[2] - z, t[0] - x) + jit
    return o['heading'] + jit if o.get('heading') is not None else spin * math.pi * 2


def place_rows(o, spec):
    seed = 7 if o.get('seed') is None else o['seed']
    rng = lehmer((seed + 5) * 2654435761, 16807)
    r = o['rows'] if isinstance(o['rows'], dict) else {}
    k = 1 if o.get('density') is None else o['density']
    gap = r.get('spacing', 0.76)
    inRow = r.get('plant', 0.24) / max(1, k)
    ang, jit = r.get('angle', 0.0), r.get('jitter', 0.05)
    skip = min(0.95, r.get('skip', 0.03) + max(0, 1 - k))
    stride, phase = max(1, r.get('stride', 1)), r.get('phase', 0)
    ca, sa = math.cos(ang), math.sin(ang)
    W, D, cx, cz = o['width'], o['depth'], o['center'][0], o['center'][1]
    clip = o.get('clip_fn')
    out = []
    rowI = 0
    rz = -D / 2 + gap * 0.5
    while rz <= D / 2 - gap * 0.2:
        if math.fmod(rowI + phase, stride) == 0:
            end0, end1 = -W / 2 + rng() * inRow * 1.6, W / 2 - rng() * inRow * 1.6
            rx = end0 + inRow * 0.5
            while rx <= end1:
                cur = rx
                rx += inRow
                if rng() < skip:
                    continue
                lxx, lzz = cur + (rng() - 0.5) * jit * 2, rz + (rng() - 0.5) * jit * 2
                x, z = cx + lxx * ca - lzz * sa, cz + lxx * sa + lzz * ca
                if clip and clip(x, z):
                    continue
                p = finish_placement(x, z, o, spec, rng, inRow, False)
                if p:
                    out.append(p)
        rz += gap
        rowI += 1
    return out


def gust_pixels(n=256):
    """The shared gust-envelope texture (vegetation.js gustTex): 256^2, 4-octave value noise, seed 3, as the uint8
    values the WebGPU edition uploads (row 0 first, which is v = 0 in both editions)."""
    from .jsmath import value_noise_2d_np
    y, x = np.mgrid[0:n, 0:n].astype(np.float64)
    v = np.zeros_like(x)
    amp, f = 0.55, 0.035
    for _ in range(4):
        v += value_noise_2d_np(3, x * f, y * f) * amp
        amp *= 0.5
        f *= 2
    return np.clip(v * 255, 0, 255).astype(np.int32).astype(np.uint8)


# ── the plan: everything create_flora decides before Blender is touched ────────────────────────────────────────────
def plan_flora(opts):
    """opts in the WebGPU edition's own (three-space) terms, snake_case: species, width, depth, size, center [x, z],
    y, seed, variant, density, footprint, rows, placements [[x, z, s]], height_fn(x, z) -> y, clip_fn(x, z),
    _surface_at(x, z) -> hit, align, max_slope, avoid, heading (azimuth atan2(dz, dx) | [x, y, z] | {'toward': p}),
    heading_jitter, height, head_scale, color, wind, wind_dir [x, z], sss, close, corn/sunflower/daisy sub-dicts.
    Returns a dict with the resolved spec, the plant geometry (three space) and the per-instance arrays."""
    sp = 'grass' if opts.get('species') == 'meadow_blades' else opts.get('species')
    if isinstance(sp, str) and sp.startswith('ph:'):
        asset = sp[3:]
        if asset not in SCANNED_SPECIES:
            raise ValueError(f"[flora] unknown scanned plant '{asset}': have {', '.join(SCANNED_SPECIES)}")
        spec = dict(SCANNED_KINDS[SCANNED_SPECIES[asset]['kind']], archetype='scanned', asset=asset)
    else:
        spec = FLORA_SPECIES.get(sp)
        if spec is None:
            raise ValueError(f"[flora] unknown species '{opts.get('species')}': have {', '.join(FLORA_SPECIES)} "
                             f"(or 'ph:<asset>': {', '.join(SCANNED_SPECIES)})")
    spec = dict(spec)
    o = {'width': 24, 'depth': 24, 'center': [0.0, 0.0], 'y': 0.0, 'seed': 7, 'max_slope': 0.9, 'wind_dir': [1.0, 0.3]}
    o.update({k: v for k, v in opts.items() if v is not None})
    if opts.get('size'):
        if not opts.get('width'):
            o['width'] = opts['size']
        if not opts.get('depth'):
            o['depth'] = opts['size']
    o['_align'] = opts['align'] if opts.get('align') is not None else (0.75 if spec.get('blades') else 0.15)
    color = opts.get('color')
    daisy_palette = None
    if spec['archetype'] == 'daisy':
        from .vegetation_daisy_gen import resolve_daisy_palette
        daisy_palette = resolve_daisy_palette(color)
    elif color is not None:
        if not spec.get('blades'):
            raise ValueError(f"[flora] 'color' applies to blade grasses only: '{sp}' keeps its authored sheet colours")
        entry = list(color) if isinstance(color, (list, tuple)) else GRASS_COLORS.get(color)
        if entry is None:
            raise ValueError(f"[flora] unknown color '{color}': have {', '.join(GRASS_COLORS)} (or a custom [r,g,b])")
        if isinstance(entry, list):
            spec['leafTint'] = entry
        else:
            spec['leafRecolor'] = entry['recolor']
    if opts.get('blades') and spec.get('blades'):
        # Blender-edition override of the blade habit (perBunch, bunchR, h, w, lean) or a named habit; default =
        # parity. 'fine' = meadow grass for shots at a person's feet (narrow blades, three times as many)
        hab = BLADE_HABITS[opts['blades']] if isinstance(opts['blades'], str) else opts['blades']
        spec['blades'] = dict(spec['blades'], **hab)
    if opts.get('height') and spec.get('blades'):
        hK = min(2.2, max(0.25, (opts['height'] / spec['blades']['h']) ** 1.4))
        spec['blades'] = dict(spec['blades'], h=opts['height'])
        w = spec['wind']
        spec['wind'] = dict(w, base=w['base'] * hK, gust=w['gust'] * hK, flutter=w['flutter'] * math.sqrt(hK))

    seed = o['seed']
    variant = 0 if o.get('variant') is None else o['variant']
    g_rng = lehmer((seed + 13) * 48271, 48271)
    stem_geo, heads, stats = None, None, {}
    arch = spec['archetype']
    if arch == 'scanned':
        geo = None                          # the scanned variant meshes are the plants (field.py loads them)
    elif arch == 'blades':
        geo = bunch_geometry(spec, g_rng, _load_json(spec['maps'] + '_fit.json'))
    elif arch == 'yucca':
        geo = yucca_geometry(spec, g_rng)
    elif arch == 'daisy':
        from .vegetation_daisy_gen import build_daisy_geometry
        d_opt = dict(spec['daisy'])
        d_opt.update(_camel(opts.get('daisy')))
        if opts.get('height'):
            d_opt['height'] = opts['height']
        if opts.get('head_scale'):
            d_opt['headScale'] = opts['head_scale']
        hd = opts.get('heading')
        if hd is not None:
            el = 0.62 if opts.get('heading_elevation') is None else opts['heading_elevation']
            if isinstance(hd, (list, tuple)):
                o['heading'] = math.atan2(hd[2], hd[0])
                el = math.atan2(hd[1], math.hypot(hd[0], hd[2]))
            elif isinstance(hd, dict) and 'toward' in hd:
                t = hd['toward']
                hf = o.get('height_fn')
                cy = hf(o['center'][0], o['center'][1]) if hf else o.get('y', 0.0)
                o['heading'] = None
                o['heading_target'] = t
                el = math.atan2(t[1] - cy - d_opt['height'] * 0.8, math.hypot(t[0] - o['center'][0], t[2] - o['center'][1]))
            d_opt['facing'] = {'el': el}
        d_opt['fit'] = _load_json('daisy_fit.json')
        build = build_daisy_geometry('daisy', f'daisy:{js_num(seed)}:{js_num(variant)}', d_opt)
        geo, heads, stats = build['geo'], build['heads'], build['stats']
    elif arch == 'shrub':
        from .vegetation_shrub_gen import build_shrub_geometry
        anchors = _load_json('shrub_anchors.json') or {}
        build = build_shrub_geometry(spec['gen'], f"{spec['gen']}:{js_num(seed)}:{js_num(variant)}", anchors.get(spec['maps']))
        geo, stem_geo, stats = build['leaf'], build['stem'], build['stats']
    elif arch == 'corn':
        from .vegetation_corn_gen import build_corn_geometry
        c_opt = dict(spec['corn'])
        c_opt.update(_camel(opts.get('corn')))
        build = build_corn_geometry('corn', f'corn:{js_num(seed)}:{js_num(variant)}', c_opt)
        geo, stats = build['geo'], build['stats']
        geo.nrm = blend_normals_up(geo.nrm, 0.3)
    elif arch == 'sunflower':
        from .vegetation_sunflower_gen import build_sunflower_geometry
        s_opt = {'fit': _load_json('sunflower_fit.json')}
        s_opt.update(spec['sunflower'])
        s_opt.update(_camel(opts.get('sunflower')))
        build = build_sunflower_geometry('sunflower', f'sunflower:{js_num(seed)}:{js_num(variant)}', s_opt)
        geo, stats = build['geo'], build['stats']
        stats['headYaw'] = build['headYaw']
    else:
        raise ValueError(f'[flora] unknown archetype {arch}')

    if o.get('placements'):
        inst = []
        for pi, pl in enumerate(o['placements']):
            pr = lehmer(seed * 131 + pi * 37 + 5, 16807)
            scale = pl[2] if len(pl) > 2 and pl[2] is not None else 1
            if spec.get('footRadius'):
                _placed_plants.append((pl[0], pl[1], spec['footRadius'] * scale))
            sy = None
            if o.get('_surface_at'):
                hit = o['_surface_at'](pl[0], pl[1])
                sy = hit['y'] if hit else 0.0
            hf = o.get('height_fn')
            y = sy if sy is not None else (hf(pl[0], pl[1]) if hf else o.get('y', 0.0))
            yaw = heading_yaw(o, pl[0], pl[1], pr()) if arch == 'daisy' else pr() * math.pi * 2
            inst.append({'x': pl[0], 'y': y, 'z': pl[1], 'yaw': yaw, 'scale': scale, 'tilt': 0.0,
                         'colorVar': pr(), 'phase': pr() * math.pi * 2, 'tx': 0.0, 'tz': 0.0})
    elif o.get('rows'):
        inst = place_rows(o, spec)
    else:
        inst = place_instances(o, spec)
    n = len(inst)
    posRot = np.array([[p['x'], p['y'], p['z'], p['yaw']] for p in inst], dtype=np.float64).reshape(n, 4)
    if (arch == 'sunflower' and (o.get('heading') is not None or o.get('heading_target') is not None)
            and (opts.get('sunflower') or {}).get('head_yaw', (opts.get('sunflower') or {}).get('headYaw')) is None
            and not opts.get('webgpu_heading')):
        # the WebGPU edition's heads face `heading` PLUS the stroke's random head yaw (one plant geometry per stroke,
        # its head turned leanA +- 0.6): turning every instance back by that yaw makes the field face the asked way,
        # as the guide promises, without touching the plant (same draws, same geometry). webgpu_heading=True keeps
        # the old facing.
        posRot[:, 3] -= stats['headYaw']
    scaleVar = np.array([[p['scale'], p['scale'] * (0.85 + p['colorVar'] * 0.3), p['tilt'], p['colorVar']]
                         for p in inst], dtype=np.float64).reshape(n, 4)
    phase = np.array([[p['phase'], p.get('tx', 0.0), p.get('tz', 0.0)] for p in inst], dtype=np.float64).reshape(n, 3)
    return {'species': sp, 'spec': spec, 'o': o, 'geo': geo, 'stem_geo': stem_geo, 'heads': heads, 'stats': stats,
            'count': n, 'posRot': posRot, 'scaleVar': scaleVar, 'phase': phase, 'daisy_palette': daisy_palette}


def instance_matrices(posRot, scaleVar, phase):
    """The WebGPU positionNode's instance transform as Blender 4x4 matrices, (N, 4, 4): scale (s, s*(0.85+0.3cv), s)
    -> yaw about Y (x' = x c - z s, z' = x s + z c) -> world tilt about X then Z -> translate, built in three space
    and conjugated into Blender's basis (B = C M C^T)."""
    n = len(posRot)
    yaw, sx, sy = posRot[:, 3], scaleVar[:, 0], scaleVar[:, 1]
    tX, tZ = phase[:, 1], phase[:, 2]
    c, s = np.cos(yaw), np.sin(yaw)
    Ry = np.zeros((n, 3, 3)); Ry[:, 0, 0] = c; Ry[:, 0, 2] = -s; Ry[:, 1, 1] = 1; Ry[:, 2, 0] = s; Ry[:, 2, 2] = c
    cx, sx_ = np.cos(tX), np.sin(tX)
    Rx = np.zeros((n, 3, 3)); Rx[:, 0, 0] = 1; Rx[:, 1, 1] = cx; Rx[:, 1, 2] = -sx_; Rx[:, 2, 1] = sx_; Rx[:, 2, 2] = cx
    cz, sz = np.cos(tZ), np.sin(tZ)
    Rz = np.zeros((n, 3, 3)); Rz[:, 0, 0] = cz; Rz[:, 0, 1] = -sz; Rz[:, 1, 0] = sz; Rz[:, 1, 1] = cz; Rz[:, 2, 2] = 1
    S = np.zeros((n, 3, 3)); S[:, 0, 0] = sx; S[:, 1, 1] = sy; S[:, 2, 2] = sx
    M3 = Rz @ Rx @ Ry @ S
    MB = C3B @ M3 @ C3B.T
    out = np.zeros((n, 4, 4))
    out[:, :3, :3] = MB
    out[:, :3, 3] = posRot[:, :3] @ C3B.T
    out[:, 3, 3] = 1
    # the daisy head fix (vegetation_daisy_gen.js daisyLocalNodes): heads keep a round shape under the non-uniform
    # instance scale; per instance the offset direction is (sx - sy) * (Rz Rx) * up, in Blender axes
    up = (Rz @ Rx)[:, :, 1]
    head_fix = (up * (sx - sy)[:, None]) @ C3B.T
    return out, head_fix


# create_flora (the Blender half) lives in field.py and is re-exported here, so the guide's
# `from eidoblend.flora.vegetation import create_flora` reads like the WebGPU edition's import
def create_flora(species=None, **kw):
    from .field import create_flora as _cf
    return _cf(species if species is not None else kw.pop('species'), **kw)
