"""ocean/sea.py: THE OCEAN OF FACES (port of eidoverse/sets/ocean/sea.js).

A night sea whose swells are made of faces. The long swell rolls in every 3.75 s (MAIN_T); three shorter swells and
six glitter ripples ride on it. As a crest passes, the faces in it SURFACE: a sculpted relief rises out of
the water (brow, closed lids, nose, lips, chin: the analytic LAYOUT shared with faces_atlas.py) and its drawn lines
glow warm from under the surface; as the crest moves on, each face sinks back and dims. Faces are laid out
anamorphically around the claudesona's eye point (log-polar rows, constant lateral width), so from the rise every face
reads upright and in proportion instead of foreshortened to a sliver: the ocean faces her.

    sea = build_sea(shore_fn=coast.sdist_3, radius=1500, parent=layout_empty)
    sea.U['reveal'] = 0.4          # the uniforms are custom properties on sea.mesh (key them; see Sea.set)
    sea.set('t', 12.0, key=True)

How the WebGPU edition maps here:
    vertex stage (positionNode)      Geometry Nodes 'ocean_sea_displace': the Gerstner swells + the faces' relief as
                                     real geometry (EEVEE's motion blur and velocity see it); the rest position is kept
                                     as the 'rest' attribute for the shader
    fragment stage (colorNode)       an unlit material (MeshBasicNodeMaterial -> Emission), the same formula node for
                                     node: Fresnel night sky, the moon's glint, the faces' light, the deep faces, the
                                     porch and window glints, the waterline foam, the haze
    uniforms U.*                     custom properties on the sea object, keyed by the set's update; the material's
                                     Value nodes and the modifier's inputs follow them through drivers (a material
                                     reads only a few Attribute (Object) values, GPU_MAX_UNIFORM_ATTR; the sea has 16)
    three's TSL hash() (PCG, uint)   exact per-cell lookup tables (float images, Closest): shader nodes have no integer
                                     maths, so the per-face draws (which face, scale, tilt, presence, hue) are computed in
                                     numpy with the same PCG and fetched texel for texel: the same crowd as WebGPU
    texture(atlas).grad(gx, gy)      the atlas's mip chain as separate images sampled with Cubic (Blender's cubic is 4
                                     textureLod(0) taps: no screen derivatives, so no seams at the fract()'d cell
                                     borders) and blended at an LOD computed from the same analytic gradients, with
                                     the screen footprint from the camera (a driver reads its vertical angle)

U: t (the swells' clock, s), reveal (0..1 sweep), glow, relief, calm, moonW (world dir), moonCol, moonI, zen / hor (sky palette,
linear), porchW / porch / porchCol (world pos / intensity / colour), winW / win, fog.
"""

from __future__ import annotations

import math

import numpy as np

from .faces_atlas import LAYOUT

G = 9.81
MAIN_T = 3.75                                                     # the long swell's period (s)
# swells in the DESIGN frame (three x, z); +z is landward. [dirX, dirZ, wavelength or None (= main), amplitude,
# steepness, phase]
SWELLS = [
    [-0.40, 1.0, None, 0.30, 0.55, 0.0],                          # the long swell (wavelength ~21.9 m)
    [-0.05, 1.0, 9.2, 0.10, 0.45, 1.7],
    [-0.80, 1.0, 5.49, 0.055, 0.40, 4.2],                         # half the long swell's period
    [0.35, 1.0, 3.3, 0.030, 0.35, 2.9],
]
RIPPLES = [                                                       # fragment-only glitter ripples
    [0.9, 1.0, 1.55, 0.012], [-0.6, 1.0, 1.02, 0.009], [0.2, -1.0, 0.71, 0.006],
    [-1.0, 0.3, 0.53, 0.005], [0.7, 0.4, 0.38, 0.0035], [-0.3, 0.9, 0.29, 0.0025],
]
FACE = {'W': 1.7, 'hV': 3.0, 'r0': 3.0}                           # lateral width (m), eye height, first row radius
N_ATLAS = 8                                                       # faces per atlas side
L = LAYOUT
# the relief's Gaussians, face units: [cx, cy, sx, sy, amplitude, smileShifted]
GAUSS = [
    [0, 0.13, 0.19, 0.035, 0.035, 0], [L['eyeX'], L['eyeY'], 0.06, 0.04, -0.045, 0], [-L['eyeX'], L['eyeY'], 0.06, 0.04, -0.045, 0],
    [L['eyeX'], L['eyeY'] - 0.004, 0.048, 0.026, 0.03, 0], [-L['eyeX'], L['eyeY'] - 0.004, 0.048, 0.026, 0.03, 0],
    [0, 0.01, 0.026, 0.085, 0.05, 0], [0, L['noseTipY'], 0.04, 0.03, 0.075, 0],
    [0.036, -0.093, 0.02, 0.016, 0.022, 0], [-0.036, -0.093, 0.02, 0.016, 0.022, 0],
    [0.15, -0.055, 0.075, 0.065, 0.03, 0], [-0.15, -0.055, 0.075, 0.065, 0.03, 0],
    [0, L['mouthY'] + 0.022, 0.062, 0.016, 0.028, 1], [0, L['mouthY'], 0.068, 0.007, -0.018, 1],
    [0, L['mouthY'] - 0.022, 0.055, 0.02, 0.03, 1],
    [0, L['chinY'] + 0.06, 0.055, 0.04, 0.03, 0],
]
GOLD, AMBER, ROSE, AQUA = (1.0, 0.62, 0.26), (1.0, 0.5, 0.2), (1.0, 0.46, 0.4), (0.3, 0.72, 0.95)

# the uniforms (custom properties on the sea object) and their defaults (sea.js U)
UNIFORMS = {
    't': 0.0, 'reveal': 0.0, 'glow': 1.0, 'relief': 1.0, 'calm': 1.0,
    'moonW': (0.0, 0.98058, 0.19612), 'moonCol': (0.75, 0.82, 1.0), 'moonI': 1.0,
    'zen': (0.012, 0.02, 0.06), 'hor': (0.05, 0.055, 0.11),
    'porchW': (0.0, 0.0, 0.0), 'porch': 0.0, 'porchCol': (1.0, 0.62, 0.3),
    'winW': (0.0, 0.0, 0.0), 'win': 0.0,
    'fog': 0.0011,
}
VECTOR_UNIFORMS = ('moonW', 'moonCol', 'zen', 'hor', 'porchW', 'porchCol', 'winW')


def wave_set():
    """SWELLS -> [{dx, dz, k, omega, A, Q, ph}] (deep-water dispersion; the main swell's period is MAIN_T)."""
    out = []
    for dx, dz, Lw, A, Q, ph in SWELLS:
        n = math.hypot(dx, dz)
        omega = 2 * math.pi / MAIN_T if Lw is None else math.sqrt(G * 2 * math.pi / Lw)
        k = omega * omega / G if Lw is None else 2 * math.pi / Lw
        out.append({'dx': dx / n, 'dz': dz / n, 'k': k, 'omega': omega, 'A': A, 'Q': Q, 'ph': ph})
    return out


# ================================================================================================ the PCG hash
M32 = 0xFFFFFFFF


def pcg_hash(seed):
    """three's TSL hash(seed) (nodes/math/Hash.js, pcg-random): uint(seed) -> PCG -> [0, 1). Exact for the float32
    seeds the sea makes (integers below 2^24). Negative seeds convert to 0, as WGSL's saturating u32() does."""
    s = np.asarray(seed, dtype=np.float32).astype(np.float64)
    u = np.where(s > 0, np.trunc(s), 0.0).astype(np.uint64) & M32
    state = (u * np.uint64(747796405) + np.uint64(2891336453)) & M32
    word = (((state >> ((state >> np.uint64(28)) + np.uint64(4))) ^ state) * np.uint64(277803737)) & M32
    res = ((word >> np.uint64(22)) ^ word) & M32
    return res.astype(np.float64) / 4294967296.0


# the lookup tables: rows ROW_MIN..ROW_MIN+ROWS-1 of each layer (main, then deep), columns -COL0..W_T-COL0-1
ROW_MIN, ROWS = -8, 24
COL0, W_T = 2304, 4608
LAYERS = {'main': (1.0, 0), 'deep': (2.4, 509)}                  # (width factor, seed offset so)


def cell_tables():
    """The per-cell draws of both layers as two float32 RGBA tables (H = 2 * ROWS, W = W_T), row 0 = v 0:
         A: h1, h2, h3, h4          (hash(seed), hash(seed + 17), hash(seed + 41), hash(seed + 73))
         B: present, off(row), 0, 1 (step(0.16, hash(seed + 97)); the row's lateral offset hash((row + 64 + so) * 37) * 9)
    seed = (col + 4096 + so) * 131 + (row + 64) * 7919, in float32 as the shader computes it."""
    A = np.zeros((2 * ROWS, W_T, 4), np.float32)
    B = np.zeros((2 * ROWS, W_T, 4), np.float32)
    col = np.arange(W_T, dtype=np.float32) - np.float32(COL0)
    for li, (_name, (_wf, so)) in enumerate(LAYERS.items()):
        for ri in range(ROWS):
            row = np.float32(ROW_MIN + ri)
            seed = (col + np.float32(4096 + so)) * np.float32(131.0) + (row + np.float32(64)) * np.float32(7919.0)
            k = li * ROWS + ri
            A[k, :, 0] = pcg_hash(seed)
            A[k, :, 1] = pcg_hash(seed + np.float32(17.0))
            A[k, :, 2] = pcg_hash(seed + np.float32(41.0))
            A[k, :, 3] = pcg_hash(seed + np.float32(73.0))
            B[k, :, 0] = (pcg_hash(seed + np.float32(97.0)) >= 0.16).astype(np.float32)
            B[k, :, 1] = np.float32(pcg_hash((row + np.float32(64 + so)) * np.float32(37.0)) * 9.0)
            B[k, :, 3] = 1.0
    return A, B


# ================================================================================================ numpy reference
def swell_np(x, z, t, damp=1.0):
    """The swells at rest positions (three x, z): disp (dx, dy, dz), the GPU Gems normal, and the main swell's sin/cos
    and the second swell's sin (sea.js swell())."""
    x, z = np.asarray(x, np.float64), np.asarray(z, np.float64)
    dx = dy = dz = nx = ny = nz = 0.0
    s0 = c0 = s1 = None
    for i, w in enumerate(wave_set()):
        th = (x * w['dx'] + z * w['dz']) * w['k'] - t * w['omega'] + w['ph']
        c, s = np.cos(th), np.sin(th)
        if i == 0:
            s0, c0 = s, c
        if i == 1:
            s1 = s
        A = damp * w['A']
        dx = dx + A * w['Q'] * w['dx'] * c
        dz = dz + A * w['Q'] * w['dz'] * c
        dy = dy + A * s
        nx = nx + A * w['dx'] * w['k'] * c
        nz = nz + A * w['dz'] * w['k'] * c
        ny = ny + A * w['Q'] * w['k'] * s
    return {'disp': (dx, dy, dz), 'n': (-nx, 1 - ny, -nz), 's0': s0, 'c0': c0, 's1': s1}


def cell_np(x, z, wf=1.0, so=0):
    """cellOf(p, W * wf, so) with the exact PCG draws (sea.js), on arrays of three (x, z)."""
    W, hV, r0 = FACE['W'] * wf, FACE['hV'], FACE['r0']
    DL = W / hV
    x, z = np.asarray(x, np.float64), np.asarray(z, np.float64)
    r2 = np.maximum(x * x + z * z, 0.25)
    r = np.sqrt(r2)
    vR = (np.log(r) - math.log(r0)) / DL
    row = np.floor(vR)
    rRow = np.exp((row + 0.5) * DL + math.log(r0))
    th = np.arctan2(x, -z)
    off = pcg_hash((row + 64 + so) * 37.0) * 9.0
    sC = th * rRow / W + off
    col = np.floor(sC)
    seed = (col + 4096 + so) * 131.0 + (row + 64) * 7919.0
    h1, h2, h3, h4 = (pcg_hash(seed + d) for d in (0.0, 17.0, 41.0, 73.0))
    present = (pcg_hash(seed + 97.0) >= 0.16).astype(np.float64)
    scl = h2 * 0.26 + 0.74
    tilt = (h3 - 0.5) * 0.4
    ct, st = np.cos(tilt), np.sin(tilt)
    lu = sC - np.floor(sC) - 0.5
    lv = vR - row - 0.5 - (h4 - 0.5) * (1 - scl) * 0.9
    fx = (lu * ct - lv * st) / scl
    fy = (lu * st + lv * ct) / scl
    thC = (col + 0.5 - off) * W / rRow
    pc = (np.sin(thC) * rRow, -np.cos(thC) * rRow)
    return dict(r=r, vR=vR, row=row, rRow=rRow, sC=sC, col=col, h1=h1, h2=h2, h3=h3, h4=h4, scl=scl, ct=ct, st=st,
                x=fx, y=fy, pc=pc, present=present)


def _ss(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def face_h_np(x, y, smile):
    qx, qy = x / L['headA'], (y - L['headCY']) / L['headB']
    sd = np.clip(1 - qx * qx - qy * qy, 0, 1)
    h = sd * sd * 0.16
    ys = y - x * x * (smile * 2.4)
    for cx, cy, sx, sy, a, sm in GAUSS:
        yy = ys if sm else y
        u, v = (x - cx) / sx, (yy - cy) / sy
        h = h + np.exp(-(u * u + v * v)) * a
    return h


def relief_np(x, z, t, reveal=1.0, relief=1.0, fdamp=1.0, radius=1500.0):
    """The faces' world-height relief (m) at rest positions, as the vertex stage adds it."""
    W, r0 = FACE['W'], FACE['r0']
    c = cell_np(x, z)
    sw = swell_np(x, z, t)
    main = wave_set()[0]
    inside = _ss(0.5, 0.44, np.maximum(np.abs(c['x']), np.abs(c['y'])))
    f = face_h_np(c['x'], c['y'], c['h1'] * 0.5 + 0.15)
    pix = _ss(-0.35, 0.8, sw['s0'] * math.cos(0.35) - sw['c0'] * math.sin(0.35))
    near = pix * (sw['s1'] * 0.25 + 0.75)
    ph = (c['pc'][0] * main['dx'] + c['pc'][1] * main['dz']) * main['k'] - t * main['omega'] + main['ph']
    emerge = _ss(-0.15, 0.85, np.sin(ph + c['h4'] * 1.4 - 0.7))
    crest = (near + (emerge - near) * _ss(45.0, 160.0, c['r'])) * c['present']
    rf = (radius / r0) ** reveal * r0
    revealK = _ss(rf, rf * 0.82, c['r']) * (1.0 if reveal >= 0.001 else 0.0)
    A = inside * crest * revealK * (c['h3'] * 0.5 + 0.7) * relief * fdamp * (c['scl'] * W)
    return f * A


def sea_point_np(x, z, t, shore=50.0, reveal=1.0, relief=1.0, calm=1.0, radius=1500.0):
    """Where the vertex stage puts a rest point (three x, z) of the water: (x, y, z) three, design frame."""
    damp = _ss(0.0, 9.0, shore) * calm
    sw = swell_np(x, z, t, damp)
    fh = relief_np(x, z, t, reveal, relief, _ss(0.5, 6.0, shore), radius)
    return (np.asarray(x) + sw['disp'][0], sw['disp'][1] + fh, np.asarray(z) + sw['disp'][2])


# ================================================================================================ the node maths
class SeaMath:
    """sea.js's TSL as node expressions over an NB (ocean/_nodes.py): the same functions build the Geometry Nodes
    displacement and the material. `U` maps a uniform name to an E scalar (or a tuple of 3 for vectors)."""

    def __init__(self, nb, U, tables, radius=1500.0):
        self.nb, self.U, self.radius = nb, U, radius
        self.tA, self.tB = tables
        self.waves = wave_set()

    # ---- swells
    def swell(self, px, pz, t, damp):
        nb = self.nb
        dx = dy = dz = nx = ny = nz = 0.0
        s0 = c0 = s1 = None
        for i, w in enumerate(self.waves):
            th = (nb.s(px) * w['dx'] + pz * w['dz']) * w['k'] - t * w['omega'] + w['ph']
            c, s = nb.cos(th), nb.sin(th)
            if i == 0:
                s0, c0 = s, c
            if i == 1:
                s1 = s
            A = damp * w['A']
            dx = dx + A * (w['Q'] * w['dx']) * c
            dz = dz + A * (w['Q'] * w['dz']) * c
            dy = dy + A * s
            nx = nx + A * (w['dx'] * w['k']) * c
            nz = nz + A * (w['dz'] * w['k']) * c
            ny = ny + A * (w['Q'] * w['k']) * s
        return {'disp': (nb.s(dx), nb.s(dy), nb.s(dz)), 'n': (-nb.s(nx), 1.0 - nb.s(ny), -nb.s(nz)),
                's0': s0, 'c0': c0, 's1': s1}

    def main_phase(self, pcx, pcz, t):
        w = self.waves[0]
        return (self.nb.s(pcx) * w['dx'] + pcz * w['dz']) * w['k'] - t * w['omega'] + w['ph']

    # ---- the anamorphic cell around her eye point, with the exact per-cell draws
    def _table(self, img, ci, ri):
        nb = self.nb
        u = (ci + (COL0 + 0.5)) * (1.0 / W_T)
        v = (ri + 0.5) * (1.0 / (2 * ROWS))
        return nb.image(img, u, v, interpolation='Closest', extension='EXTEND')

    def cell_of(self, px, pz, layer='main'):
        nb = self.nb
        wf, so = LAYERS[layer]
        W, hV, r0 = FACE['W'] * wf, FACE['hV'], FACE['r0']
        DL = W / hV
        LR0 = math.log(r0)
        r2 = nb.max(nb.s(px) * px + nb.s(pz) * pz, 0.25)
        r = nb.sqrt(r2)
        vR = (nb.log(r) - LR0) * (1.0 / DL)
        row = nb.floor(vR)
        rRow = nb.exp((row + 0.5) * DL + LR0)
        th = nb.atan2(px, -nb.s(pz))
        ri = row + (-ROW_MIN + (ROWS if layer == 'deep' else 0))
        off = self._table(self.tB, 0.0 - COL0 + 1.0, ri)[1]          # any column: the row's offset is replicated
        sC = th * rRow * (1.0 / W) + off
        col = nb.floor(sC)
        h1, h2, h3, h4 = self._table(self.tA, col, ri)
        present = self._table(self.tB, col, ri)[0]
        scl = h2 * 0.26 + 0.74
        tilt = (h3 - 0.5) * 0.4
        ct, st = nb.cos(tilt), nb.sin(tilt)
        lu = nb.fract(sC) - 0.5
        lv = vR - row - 0.5 - (h4 - 0.5) * (1.0 - scl) * 0.9
        isc = 1.0 / scl
        x = (lu * ct - lv * st) * isc
        y = (lu * st + lv * ct) * isc
        thC = (col + 0.5 - off) * W / rRow
        pc = (nb.sin(thC) * rRow, -nb.cos(thC) * rRow)
        return dict(r=r, r2=r2, vR=vR, row=row, rRow=rRow, sC=sC, col=col, h1=h1, h2=h2, h3=h3, h4=h4, scl=scl, isc=isc,
                    ct=ct, st=st, x=x, y=y, pc=pc, present=present, lu=lu, W=W, DL=DL, px=px, pz=pz)

    def cell_jacobian(self, c):
        """d(face x, y)/d(design x, z): dX, dY (sea.js cellOf's dLu / dLv chain)."""
        nb = self.nb
        k = c['rRow'] * (1.0 / c['W'])
        ir2 = 1.0 / c['r2']
        dLu = (-nb.s(c['pz']) * ir2 * k, nb.s(c['px']) * ir2 * k)
        dLv = (nb.s(c['px']) * ir2 * (1.0 / c['DL']), nb.s(c['pz']) * ir2 * (1.0 / c['DL']))
        ct, st, isc = c['ct'], c['st'], c['isc']
        dX = tuple((dLu[i] * ct - dLv[i] * st) * isc for i in range(2))
        dY = tuple((dLu[i] * st + dLv[i] * ct) * isc for i in range(2))
        return dX, dY

    # ---- the relief
    def face_hg(self, x, y, smile, with_grad=True):
        nb = self.nb
        qx = x * (1.0 / L['headA'])
        qy = (y - L['headCY']) * (1.0 / L['headB'])
        sd = nb.clamp(1.0 - qx * qx - qy * qy, 0.0, 1.0)
        h = sd * sd * 0.16
        hx = sd * 0.32 * (x * (-2.0 / (L['headA'] ** 2))) if with_grad else None
        hy = sd * 0.32 * ((y - L['headCY']) * (-2.0 / (L['headB'] ** 2))) if with_grad else None
        k = smile * 2.4
        ys = y - x * x * k
        for cx, cy, sx, sy, a, sm in GAUSS:
            yy = ys if sm else y
            u = (x - cx) * (1.0 / sx)
            v = (yy - cy) * (1.0 / sy)
            g = nb.exp(-(u * u + v * v)) * a
            h = h + g
            if with_grad:
                gv = g * (v * (-2.0 / sy))
                hx = hx + g * (u * (-2.0 / sx))
                if sm:
                    hx = hx + gv * (x * k * -2.0)
                hy = hy + gv
        return h, hx, hy

    def reveal_k(self, r):
        nb, R = self.nb, self.U['reveal']
        rf = nb.exp(R * math.log(self.radius / FACE['r0'])) * FACE['r0']
        return nb.smoothstep(rf, rf * 0.82, r) * nb.step(0.001, R)

    def reveal_wave(self, r):
        nb, R = self.nb, self.U['reveal']
        rf = nb.exp(R * math.log(self.radius / FACE['r0'])) * FACE['r0']
        x = (r - rf * 0.9) / (rf * 0.13 + 0.6)
        return nb.exp(-(x * x)) * nb.step(0.001, R) * (1.0 - nb.smoothstep(0.93, 1.0, R))

    def emerge_k(self, c, t):
        return self.nb.smoothstep(-0.15, 0.85, self.nb.sin(self.main_phase(c['pc'][0], c['pc'][1], t) + c['h4'] * 1.4 - 0.7))

    def crest_k(self, sw, c, t):
        nb = self.nb
        pix = nb.smoothstep(-0.35, 0.8, sw['s0'] * math.cos(0.35) - sw['c0'] * math.sin(0.35))
        near = pix * (sw['s1'] * 0.25 + 0.75)
        return nb.mix(near, self.emerge_k(c, t), nb.smoothstep(45.0, 160.0, c['r'])) * c['present']

    def relief(self, c, sw, t, damp, with_grad):
        nb = self.nb
        inside = nb.smoothstep(0.5, 0.44, nb.max(nb.abs(c['x']), nb.abs(c['y'])))
        h, hx, hy = self.face_hg(c['x'], c['y'], c['h1'] * 0.5 + 0.15, with_grad)
        A = inside * self.crest_k(sw, c, t) * self.reveal_k(c['r']) * (c['h3'] * 0.5 + 0.7) * self.U['relief'] * damp \
            * (c['scl'] * FACE['W'])
        if not with_grad:
            return h * A, None
        dX, dY = self.cell_jacobian(c)
        g = tuple((dX[i] * hx + dY[i] * hy) * A for i in range(2))
        return h * A, g


# ================================================================================================ Blender
def _np_atlas_mips(data, levels):
    """The atlas (uint8, row 0 = bottom) -> [uint8 (H, W, 4)] mip levels 0..levels-1: util.build_mips, the WebGPU
    edition's chain byte for byte (each level the integer 2x2 box filter of the one above)."""
    from .util import build_mips
    return [m['data'] for m in build_mips(data)[:levels]]


ATLAS_LEVELS = 7                                                  # 2048 .. 32 px


def atlas_images(data=None, name='ocean_faces_atlas'):
    """The face atlas's mip chain as packed 8-bit images (levels 0..ATLAS_LEVELS-1), for Cubic sampling."""
    from .faces_atlas import draw_face_atlas
    from .util import image_from_array
    if data is None:
        data = draw_face_atlas(n=N_ATLAS, cell=256, seed=11)
    return [image_from_array(f'{name}_L{i}', m, colorspace='Non-Color', float_buffer=False)
            for i, m in enumerate(_np_atlas_mips(data, ATLAS_LEVELS))]


def table_images():
    from .util import image_from_array
    A, B = cell_tables()
    return (image_from_array('ocean_cells_A', A, colorspace='Non-Color', float_buffer=True),
            image_from_array('ocean_cells_B', B, colorspace='Non-Color', float_buffer=True))


def sea_mesh_arrays(shore_fn=None, radius=1500.0, NR=250, NS=768, R0=2.0):
    """The polar water mesh of sea.js (dense near her): positions (three x, z), triangles, the shore attribute.
    shore_fn(x, z) takes three's (x, z) (Coast.sdist_3)."""
    gro = (radius / R0) ** (1.0 / NR)
    r = R0 * gro ** np.arange(NR + 1)
    a = np.arange(NS) / NS * math.pi * 2
    X = (np.sin(a)[None, :] * r[:, None]).reshape(-1)
    Z = (-np.cos(a)[None, :] * r[:, None]).reshape(-1)
    S = np.asarray(shore_fn(X, Z), np.float64) if shore_fn else np.full(X.shape, 50.0)
    i = np.arange(NR)
    j = np.arange(NS)
    I, J = np.meshgrid(i, j, indexing='ij')
    A = I * NS + J
    Bq = I * NS + (J + 1) % NS
    C = (I + 1) * NS + J
    D = (I + 1) * NS + (J + 1) % NS
    keep = (np.maximum.reduce([S[A], S[Bq], S[C], S[D]]) >= -4).reshape(-1)     # quads buried in the land dropped
    A, Bq, C, D = (q.reshape(-1)[keep] for q in (A, Bq, C, D))
    tris = np.concatenate([np.stack([A, Bq, C], 1), np.stack([Bq, D, C], 1)], axis=0)
    return X, Z, tris, S


class Sea:
    """build_sea's result: mesh (the object), U (its uniforms: the object's custom properties), atlas (the mip
    images), tables, face_cell_info; set(name, value, key=..., frame=...) writes (and keys) a uniform."""

    def __init__(self, mesh, atlas, tables, face_cell_info):
        self.mesh, self.atlas, self.tables, self.face_cell_info = mesh, atlas, tables, face_cell_info

    @property
    def U(self):
        return self.mesh

    def set(self, name, value, key=None, frame=None):
        from . import _bl
        if name not in UNIFORMS:
            raise KeyError(f'[ocean] sea uniform {name!r}: one of {", ".join(UNIFORMS)}')
        v = tuple(float(x) for x in value) if name in VECTOR_UNIFORMS else float(value)
        _bl.set_prop(self.mesh, name, v, key=key, frame=frame)

    def get(self, name):
        v = self.mesh[name]
        return tuple(v) if name in VECTOR_UNIFORMS else float(v)


def build_sea(shore_fn=None, radius=1500.0, parent=None, collection=None, name='ocean_of_faces', atlas_data=None):
    """buildSea(THREE, { shoreFn, radius }) -> Sea. shore_fn takes three's design (x, z) (Coast.sdist_3); the mesh is
    built in the design frame (parent it under the layout Empty)."""
    import bpy
    from . import _bl, _sea_nodes
    col = collection or bpy.context.scene.collection
    X, Z, tris, S = sea_mesh_arrays(shore_fn, radius)
    pos = np.stack([X, -Z, np.zeros_like(X)], axis=1)
    me = _bl.mesh_from_arrays(name, pos, tris, smooth=True)
    _bl.add_point_attr(me, 'shore', S)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    for k, v in UNIFORMS.items():
        ob[k] = v
    atlas = atlas_images(atlas_data)
    tables = table_images()
    mod = ob.modifiers.new('sea_displace', 'NODES')
    mod.node_group = _sea_nodes.displace_group(tables, radius)
    for sock, prop in (('Time', 't'), ('Reveal', 'reveal'), ('Relief', 'relief'), ('Calm', 'calm')):
        _bl.drive_modifier_input(ob, mod, sock, ob, prop)
    mat = _sea_nodes.sea_material(atlas, tables, radius, owner=ob)
    me.materials.append(mat)
    # the water's surface is never a shadow caster or a light-probe occluder for the set's lights
    ob.visible_shadow = False
    W, hV, r0 = FACE['W'], FACE['hV'], FACE['r0']
    return Sea(ob, atlas, tables, {'W': W, 'hV': hV, 'r0': r0, 'DL': W / hV})
