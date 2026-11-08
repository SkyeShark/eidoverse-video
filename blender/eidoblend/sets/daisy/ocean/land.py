"""ocean/land.py: the shore of verse 3 (port of eidoverse/sets/ocean/land.js), in the DESIGN frame: her mark at the
origin, the open sea toward the moon, the cove and the house's spit behind her to the left.

    a small rise (her mark) at the tip of a low headland,
    a cove curling round to a sand spit where the house stands,
    beach -> dunes -> low dark hills inland.

Heights are analytic from a signed distance to the coast polyline (+ water, - land), so the sea's shore attribute,
the land mesh and the grass placement all agree.

    coast = make_coast()   -> Coast: sdist_3(x, z), height_3(x, z), markY, house {x, z, yaw, grade} (three's design
                              frame, as land.js); sdist(x, y), height(x, y), house_blender (Blender's design axes)
    land = build_land(coast, parent=layout_empty, design_to_world=f, world_to_design=g)
                           -> Land: group, land (the mesh), grass (the dune grass object: its clock is the custom
                              property 't'), mats, grass_count, daisies, update(t, key=None, frame=None)

A design-frame point (three x, z) is Blender's (x, -z) in the layout Empty. The maths runs in three's (x, z) exactly
as land.js does (the _3 functions), so the WebGPU edition's numbers carry over (tests: test_ocean_staging.py).
"""

from __future__ import annotations

import math

import numpy as np

from .util import rng, np_smoothstep

# the coastline (three x, z), land on the +z / inland side, walked from the far right to the far left
COAST = [
    [420, 48], [160, 22], [70, 10], [45, 6.2], [30, 4.4], [19, 2.5], [11.5, 1.0], [6.6, -0.7], [3.3, -2.5],
    [1.2, -4.0], [-0.9, -4.6], [-3.1, -4.0], [-5.6, -2.4], [-8.6, -1.4], [-12.2, -2.3], [-15.8, -5.2],
    [-18.3, -9.8], [-19.0, -15.0], [-17.8, -19.3], [-15.0, -21.7], [-11.6, -22.3], [-8.2, -22.6], [-5.6, -23.7],
    [-3.9, -26.2], [-4.4, -29.3], [-6.9, -31.8], [-11.4, -33.0], [-16.4, -32.7], [-22.5, -31.7], [-30, -33.2],
    [-46, -36.5], [-80, -41], [-200, -52], [-420, -66],
]
INLAND = [[-420, 600], [420, 600]]                      # closes the land polygon far inland
HOUSE_3 = (-10.9, -28.1)                                # the house on the spit (three x, z)


def _ss(a, b, x):
    """land.js smoothstep(a, b, x) = smooth((x - a) / (b - a)) (also for a > b), on arrays."""
    return np_smoothstep(a, b, x)


class Coast:
    """makeCoast(): the analytic shore. Public methods take Blender ground coordinates (x, y); the *_3 methods take
    three's (x, z) like land.js. All accept scalars or numpy arrays."""

    def __init__(self):
        poly = np.array(COAST + INLAND, dtype=np.float64)
        self._poly = poly
        c = np.array(COAST, dtype=np.float64)
        self._a, self._b = c[:-1], c[1:]
        hx, hz = HOUSE_3
        yaw = math.atan2(-hx, -hz)                                  # +z of the house points at her
        self._house3 = {'x': hx, 'z': hz, 'yaw': yaw}
        self.mark_z = float(self._raw_3(0.0, 0.0, self.sdist_3(0.0, 0.0)))
        hs = self.sdist_3(hx, hz)
        self.house_grade = float(max(0.42, float(self._raw_3(hx, hz, hs)))) + 0.02
        self._house3['grade'] = self.house_grade
        # makeCoast's house (three's design x, z; its grade; yaw about +Y, which is +Z in Blender)
        self.house = dict(self._house3)
        # the same in Blender's axes: (x, y) on the ground, z its grade
        self.house_blender = {'x': hx, 'y': -hz, 'z': self.house_grade, 'yaw': yaw}

    # ------------------------------------------------------------------------------------------- three (x, z)
    def inside_3(self, x, z):
        x = np.asarray(x, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        c = np.zeros(np.broadcast(x, z).shape, dtype=bool)
        poly = self._poly
        n = len(poly)
        j = n - 1
        for i in range(n):
            xi, zi = poly[i]
            xj, zj = poly[j]
            with np.errstate(divide='ignore', invalid='ignore'):
                cross = x < (xj - xi) * (z - zi) / (zj - zi) + xi
            c ^= ((zi > z) != (zj > z)) & cross
            j = i
        return c

    def sdist_3(self, x, z):
        """Signed distance to the coast polyline: + over the water, - over the land."""
        x = np.asarray(x, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        best = np.full(np.broadcast(x, z).shape, 1e18)
        for (ax, az), (bx, bz) in zip(self._a, self._b):
            vx, vz = bx - ax, bz - az
            wx, wz = x - ax, z - az
            t = np.clip((wx * vx + wz * vz) / (vx * vx + vz * vz), 0.0, 1.0)
            dx, dz = wx - vx * t, wz - vz * t
            best = np.minimum(best, dx * dx + dz * dz)
        d = np.sqrt(best)
        out = np.where(self.inside_3(x, z), -d, d)
        return float(out) if out.ndim == 0 else out

    def _raw_3(self, x, z, s):
        x = np.asarray(x, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        s = np.asarray(s, dtype=np.float64)
        sea = -np.minimum(4.5, 0.2 * s + 0.004 * s * s)                        # the shelving sea floor
        d = -s
        h = 0.58 * _ss(0, 7.5, d)                                              # the beach
        dune = 0.5 + 0.5 * np.sin(x * 0.105 + np.sin(z * 0.071) * 2.1) * np.cos(z * 0.087 + 0.7)
        h = h + _ss(4.5, 17, d) * (0.45 + 0.75 * dune)                         # dune field
        h = h + _ss(30, 240, d) * (4.5 + 2.5 * np.sin(x * 0.011 + 1.3) * np.cos(z * 0.008))   # hills inland
        h = np.where(s > 0, sea, h)
        r2 = (x - 0.2) ** 2 + (z - 0.45) ** 2
        h = h + 0.98 * np.exp(-r2 / (2 * 2.35 * 2.35)) * _ss(-1.2, 3.0, -s)  # HER RISE
        h = h + 0.035 * np.sin(x * 1.31 + z * 0.73) * np.sin(z * 1.07 - x * 0.41) * _ss(0, 2, -s)
        return h

    def height_3(self, x, z):
        x = np.asarray(x, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        s = self.sdist_3(x, z)
        h = self._raw_3(x, z, s)
        rm = np.hypot(x, z)                                                    # level ground under her feet
        h = h + (self.mark_z - h) * _ss(1.0, 0.45, rm)
        H = self._house3
        c, sn = math.cos(H['yaw']), math.sin(H['yaw'])                        # house pad (house-local axes)
        lx = (x - H['x']) * c - (z - H['z']) * sn
        lz = (x - H['x']) * sn + (z - H['z']) * c
        pad = np.maximum(np.abs(lx) / 3.6, np.abs(lz - 0.6) / 3.9)
        h = h + (self.house_grade - h) * _ss(1.45, 1.0, pad)
        return float(h) if np.ndim(h) == 0 else h

    # ------------------------------------------------------------------------------------------- Blender (x, y)
    def sdist(self, x, y):
        return self.sdist_3(x, -np.asarray(y, dtype=np.float64))

    def height(self, x, y):
        return self.height_3(x, -np.asarray(y, dtype=np.float64))

    @property
    def markY(self):                                                           # the WebGPU name
        return self.mark_z


def make_coast():
    """makeCoast() -> Coast (sdist, height, mark_z (markY), house {x, y, z, yaw, grade})."""
    return Coast()


# ================================================================================================ the land (Blender)

NR, NS, R0, RMAX = 300, 720, 0.04, 1500.0


def land_mesh_arrays(coast):
    """The polar land mesh of land.js (fine at her feet): vertices (three xyz), triangles, the shore attribute."""
    gro = (RMAX / R0) ** (1.0 / NR)
    r = R0 * gro ** np.arange(NR + 1)
    a = np.arange(NS) / NS * math.pi * 2
    X = (np.sin(a)[None, :] * r[:, None]).reshape(-1)
    Z = (-np.cos(a)[None, :] * r[:, None]).reshape(-1)
    X = np.concatenate([[0.0], X])
    Z = np.concatenate([[0.0], Z])
    S = coast.sdist_3(X, Z)
    Hh = coast.height_3(X, Z)
    j = np.arange(NS)
    fan = np.stack([np.zeros(NS, np.int64), 1 + (j + 1) % NS, 1 + j], axis=1)
    i = np.arange(NR)
    I, J = np.meshgrid(i, j, indexing='ij')
    A = 1 + I * NS + J
    Bq = 1 + I * NS + (J + 1) % NS
    C = 1 + (I + 1) * NS + J
    D = 1 + (I + 1) * NS + (J + 1) % NS
    lo = np.maximum.reduce([Hh[A], Hh[Bq], Hh[C], Hh[D]])
    keep = (lo >= -1.6).reshape(-1)                                            # deep sea floor: hidden by the water
    A, Bq, C, D = (q.reshape(-1)[keep] for q in (A, Bq, C, D))
    tris = np.concatenate([fan, np.stack([A, Bq, C], 1), np.stack([Bq, D, C], 1)], axis=0)
    pos3 = np.stack([X, Hh, Z], axis=1)
    return pos3, tris, S


def _tuft_geometry(R):
    """The dune-grass tuft: 13 tapered blades of 5 segments (positions three-local, uvs, triangles)."""
    P, I, UV = [], [], []
    nb, segs = 13, 5
    for _b in range(nb):
        az, lean, H, w0 = R() * math.pi * 2, 0.15 + R() * 0.55, 0.32 + R() * 0.48, 0.006 + R() * 0.006
        ox, oz = (R() - 0.5) * 0.09, (R() - 0.5) * 0.09
        base = len(P)
        for s in range(segs + 1):
            t = s / segs
            y, off = H * t, math.sin(lean) * H * t * t
            cx, cz = ox + math.sin(az) * off, oz + math.cos(az) * off
            w = w0 * (1 - t * 0.92)
            px, pz = math.cos(az) * w, -math.sin(az) * w
            yy = y * math.cos(lean * t * 0.6)
            P.append((cx - px, yy, cz - pz))
            P.append((cx + px, yy, cz + pz))
            UV.append((0.0, t))
            UV.append((1.0, t))
            if s < segs:
                q = base + s * 2
                I.append((q, q + 1, q + 2))
                I.append((q + 1, q + 3, q + 2))
    return np.array(P), np.array(I, dtype=np.int64), np.array(UV)


def plan_dune_grass(coast, seed=29):
    """land.js's dune-grass plan: the tuft (drawn first from the stream) and up to 2600 placements
    [x, y, z, yaw, s] in three's design frame, from the same rng(29) stream."""
    R = rng(seed)
    tuft = _tuft_geometry(R)
    blades = []
    tries = 0
    while tries < 60000 and len(blades) < 2600:
        tries += 1
        x, z = (R() - 0.5) * 110, -34 + R() * 80
        hh, s = coast.height_3(x, z), coast.sdist_3(x, z)
        if s > -2.5 or hh < 0.7:
            continue
        rm = math.hypot(x, z)
        if rm < 0.95:                                                          # her feet stay clear
            continue
        if math.hypot(x - coast._house3['x'], z - coast._house3['z']) < 4.6:  # the house pad
            continue
        gN = 0.5 + 0.5 * math.sin(x * 0.61 + math.cos(z * 0.43) * 2.0) * math.sin(z * 0.53 - x * 0.21)
        want = (0.55 if hh > 1.0 else 0.2) * (0.3 + gN) + (0.5 if rm < 4 else 0)
        if R() > want:
            continue
        blades.append([x, hh - 0.02, z, R() * math.pi * 2, 0.7 + R() * 0.7])
    return tuft, blades


# the dune grass's blade gradient, sRGB stops bottom -> top (land.js canvas: #5a5436 .35 #8f8458 .8 #c9b98a 1 #e2d5ad)
GRASS_STOPS = [(0.0, (0x5a, 0x54, 0x36)), (0.35, (0x8f, 0x84, 0x58)), (0.8, (0xc9, 0xb9, 0x8a)), (1.0, (0xe2, 0xd5, 0xad))]


def grass_gradient(n=256):
    """The canvas gradient, interpolated in sRGB as canvas does: (n, 3) uint8, row 0 = the blade's base."""
    v = (np.arange(n) + 0.5) / n
    out = np.zeros((n, 3))
    for (a, ca), (b, cb) in zip(GRASS_STOPS[:-1], GRASS_STOPS[1:]):
        m = (v >= a) & (v <= b)
        k = ((v[m] - a) / (b - a))[:, None]
        out[m] = np.array(ca) * (1 - k) + np.array(cb) * k
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


class Land:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def update(self, t, key=None, frame=None):
        """land.update(t): the dune grass's wind clock (the daisies keep close 1, wind 0.35, pulse 0: set at build)."""
        from . import _bl
        if self.grass is not None:
            _bl.set_prop(self.grass, 't', float(t), key=key, frame=frame)


def build_land(coast, parent=None, collection=None, mesh=True, grass=True, daisies=True, design_to_world=None,
               world_to_design=None, name='ocean_land', webgpu_sway=False):
    """buildLand(THREE, coast): the land mesh with its blended Poly Haven sand / wet sand / withered grass, the dune grass
    (2600 tufts of geometry blades swaying from a keyed clock: custom property 't' on the grass object), and her
    flowers (the flora family's daisy, shut for the night). parent: the layout Empty (design frame).
    design_to_world(x3, z3, y3=0) / world_to_design(x, y): the flora field lives in world space at the world origin,
    so it is planted through these. webgpu_sway: the film's grass sway arithmetic (see _land_nodes._sway_group)."""
    import bpy
    from . import _bl, _land_nodes
    col = collection or bpy.context.scene.collection
    group = _bl.empty('ocean:land', parent=parent, collection=col, size=0.5)

    # ---------------------------------------------------------------- mesh (polar, fine at her feet)
    land = mat = None
    if mesh:
        pos3, tris, S = land_mesh_arrays(coast)
        pos = np.stack([pos3[:, 0], -pos3[:, 2], pos3[:, 1]], axis=1)
        me = _bl.mesh_from_arrays(name, pos, tris)
        _bl.add_point_attr(me, 'shore', S)
        uv = np.stack([pos3[:, 0] / 3.1, pos3[:, 2] / 3.1], axis=1)           # world-planar uvs (normal-map frame)
        _bl.add_uv_from_points(me, 'uv', uv)
        land = bpy.data.objects.new(name, me)
        col.objects.link(land)
        land.parent = group
        mat = _land_nodes.land_material('ocean_land')
        me.materials.append(mat)

    # ---------------------------------------------------------------- dune grass: geometry blades
    tuft, blades = plan_dune_grass(coast)
    grass_ob = gmat = None
    if grass and blades:
        gmat = _land_nodes.dune_grass_material('ocean_dunegrass', grass_gradient())
        grass_ob = _land_nodes.dune_grass_object('ocean_dunegrass', tuft, blades, gmat, group, col)
        if webgpu_sway:
            _bl.set_modifier_input(grass_ob.modifiers['sway'], 'WebGPU', 1.0)

    # ---------------------------------------------------------------- her flowers, closed for the night
    flowers = None
    if daisies:
        from .daisies import build as build_daisies
        flowers = build_daisies(count=420, width=5.2, depth=4.6, center=(0.25, 0.5), seed=5,
                                height_fn=coast.height_3, face_dir=(0.1, 0.6, 1.0),
                                clear=[{'a': (-0.25, 0.0), 'b': (0.25, 0.0), 'w': 1.25}], close=1.0,
                                stem_height=(0.16, 0.28), head_scale=1.2, wind=0.35,
                                design_to_world=design_to_world, world_to_design=world_to_design, collection=col)
    return Land(group=group, land=land, grass=grass_ob, mats=[m for m in (mat, gmat) if m], grass_count=len(blades),
                daisies=flowers, tuft=tuft, blades=blades)
