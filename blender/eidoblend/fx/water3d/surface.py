"""fluid_water.js's render side, as a mesh: the phi = 0 isosurface each baked frame, with the engine's field ops.

The engine raymarched the level set per pixel. Here the same field becomes a closed mesh (OpenVDB volumeToMesh)
that EEVEE lights, shadows and refracts like any object, and the render-side options keep their meaning:

    the solid mask   phiAt = mix(phi, 4 DX, smoothstep(0.30, 0.62, solidSoft)): water is never drawn inside walls,
                     colliders or spheres, and the interpolated occupancy gives a smooth shoreline
    render_blur      1-2 separable [1 2 1]/4 passes of phi into a render-only field (rounds silhouettes)
    smooth_surface   the cubic B-spline reconstruction (Sigg & Hadwiger), evaluated on a 2x grid and meshed
    surface_bias     the phi = -bias contour (thin films under ~2 bias stop rendering)

and the engine's per-pixel shading inputs become per-vertex attributes the material reads:

    thick   water thickness along a ray (the engine's 24-step march to the box exit): along the inward normal by
            default (view independent, any camera), or along the scene camera's view ray ('view', the engine's own)
    ring    solid proximity: the max of the soft occupancy over the engine's 6 taps 1.6 cells around the point
    speed   flow speed (m/s) from the velocity field (the Blender edition's churn foam reads it)
    exit    the water path along the inward normal to where it leaves the water (m): EEVEE's refraction
            thickness, which the engine's raymarch never needed (left unlinked, the same settled pool rendered
            bright in one frame and dark in the next: measured on the dam break)
    bed     1 where that path ends on a solid or runs deeper than 24 cells (water over a floor), 0 where it
            leaves into air (a stream, a sheet, a drop)

All arrays are in three.js axes, [k][j][i] = [z][y][x] (y up), domain-local (the domain centred on 0).
"""

from __future__ import annotations

import numpy as np


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class Grid:
    """A cell-centred scalar field over the domain [-W/2, W/2] (three axes), sampled like a linear,
    clamp-to-edge texture."""

    def __init__(self, a, world3):
        self.a = np.ascontiguousarray(a, dtype=np.float32)
        self.nz, self.ny, self.nx = self.a.shape
        self.W = np.asarray(world3, dtype=np.float64)

    def sample_uvw(self, uvw):
        uvw = np.asarray(uvw, dtype=np.float64)
        n = np.array([self.nx, self.ny, self.nz], dtype=np.float64)
        t = uvw * n - 0.5
        i0 = np.floor(t)
        f = (t - i0).astype(np.float32)
        i0 = i0.astype(np.int64)
        lim = np.array([self.nx - 1, self.ny - 1, self.nz - 1])
        a0 = np.clip(i0, 0, lim)
        a1 = np.clip(i0 + 1, 0, lim)
        A = self.a
        x0, y0, z0 = a0[:, 0], a0[:, 1], a0[:, 2]
        x1, y1, z1 = a1[:, 0], a1[:, 1], a1[:, 2]
        fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]
        c00 = A[z0, y0, x0] * (1 - fx) + A[z0, y0, x1] * fx
        c10 = A[z0, y1, x0] * (1 - fx) + A[z0, y1, x1] * fx
        c01 = A[z1, y0, x0] * (1 - fx) + A[z1, y0, x1] * fx
        c11 = A[z1, y1, x0] * (1 - fx) + A[z1, y1, x1] * fx
        c0 = c00 * (1 - fy) + c10 * fy
        c1 = c01 * (1 - fy) + c11 * fy
        return c0 * (1 - fz) + c1 * fz

    def sample(self, p_local):
        return self.sample_uvw(np.asarray(p_local) / self.W + 0.5)


def blur121(a, passes):
    """The engine's renderBlur: per pass, [1 2 1]/4 along x, then y, then z, edges clamped (a tap past the
    domain reads the edge cell, as the engine's clamp-to-edge sampler did)."""
    a = np.asarray(a, dtype=np.float32)
    for _ in range(int(passes)):
        for ax in (2, 1, 0):                                    # x, y, z in [z][y][x] order
            lo = np.take(a, np.r_[0, np.arange(a.shape[ax] - 1)], axis=ax)
            hi = np.take(a, np.r_[np.arange(1, a.shape[ax]), a.shape[ax] - 1], axis=ax)
            a = (2.0 * a + lo + hi) * 0.25
    return a


def _bspline_w(f):
    f2, f3 = f * f, f * f * f
    return ((-f3 + 3 * f2 - 3 * f + 1) / 6.0, (3 * f3 - 6 * f2 + 4) / 6.0,
            (-3 * f3 + 3 * f2 + 3 * f + 1) / 6.0, f3 / 6.0)


def bspline_upsample2(a):
    """The engine's phiCubeRaw (uniform cubic B-spline over the texels, clamp to edge) evaluated at the centres
    of a 2x finer cell-centred grid. Separable: a fine centre sits at texel coordinate i - 1/4 or i + 1/4, so two
    fixed 4-tap weight sets per axis."""
    a = np.asarray(a, dtype=np.float32)
    we = _bspline_w(0.75)                    # even fine index 2i: base b = i - 1, f = 0.75
    wo = _bspline_w(0.25)                    # odd fine index 2i+1: base b = i, f = 0.25
    for ax in (2, 1, 0):
        n = a.shape[ax]
        idx = np.arange(n)
        ev = np.zeros_like(a)
        od = np.zeros_like(a)
        for k in range(4):
            ev = ev + we[k] * np.take(a, np.clip(idx - 2 + k, 0, n - 1), axis=ax)
            od = od + wo[k] * np.take(a, np.clip(idx - 1 + k, 0, n - 1), axis=ax)
        shp = list(a.shape)
        shp[ax] = 2 * n
        out = np.empty(shp, dtype=np.float32)
        sl_e = [slice(None)] * 3
        sl_o = [slice(None)] * 3
        sl_e[ax] = slice(0, None, 2)
        sl_o[ax] = slice(1, None, 2)
        out[tuple(sl_e)] = ev
        out[tuple(sl_o)] = od
        a = out
    return a


class SolidSoft:
    """The engine's render-side occupancy solidSoft(uvw): the baked field (linear), the analytic walls (hard), the
    dynamic spheres (a smooth falloff 1.8 cells wide outside each sphere)."""

    def __init__(self, world3, dx, wall_margin, walls, solid=None, spheres=None):
        self.W = np.asarray(world3, dtype=np.float64)
        self.dx = float(dx)
        self.m = float(wall_margin)
        self.walls = bool(walls)
        self.solid = Grid(solid, world3) if solid is not None else None
        sp = np.zeros((0, 4)) if spheres is None else np.asarray(spheres, dtype=np.float64).reshape(-1, 4)
        self.spheres = sp[sp[:, 3] > 0]

    def walls_at(self, uvw):
        m = self.m
        return ((uvw[:, 0] < m) | (uvw[:, 0] > 1 - m) | (uvw[:, 2] < m) | (uvw[:, 2] > 1 - m)
                | (uvw[:, 1] < m))

    def on_grid(self, shape):
        """The same occupancy at every cell centre of a [z][y][x] grid of `shape` (the sim grid or the 2x render
        grid), evaluated separably: the baked field by an exact per-axis linear resample (a GL linear sampler's
        taps at those centres), the walls by per-axis tests, each sphere only inside its own bounding box."""
        nz, ny, nx = shape
        xs = (np.arange(nx) + 0.5) / nx
        ys = (np.arange(ny) + 0.5) / ny
        zs = (np.arange(nz) + 0.5) / nz
        if self.solid is not None:
            v = linear_resample(self.solid.a, shape)
        else:
            v = np.zeros(shape, dtype=np.float32)
        if self.walls:
            m = self.m
            wx = (xs < m) | (xs > 1 - m)
            wz = (zs < m) | (zs > 1 - m)
            wy = ys < m
            wall = wz[:, None, None] | wy[None, :, None] | wx[None, None, :]
            v = np.maximum(v, wall.astype(np.float32))
        for s in self.spheres:
            reach = s[3] + self.dx * 1.8
            lo = (s[:3] - reach) / self.W + 0.5
            hi = (s[:3] + reach) / self.W + 0.5
            i0, i1 = np.searchsorted(xs, lo[0]), np.searchsorted(xs, hi[0], side='right')
            j0, j1 = np.searchsorted(ys, lo[1]), np.searchsorted(ys, hi[1], side='right')
            k0, k1 = np.searchsorted(zs, lo[2]), np.searchsorted(zs, hi[2], side='right')
            if i1 <= i0 or j1 <= j0 or k1 <= k0:
                continue
            px = (xs[i0:i1] - 0.5) * self.W[0] - s[0]
            py = (ys[j0:j1] - 0.5) * self.W[1] - s[1]
            pz = (zs[k0:k1] - 0.5) * self.W[2] - s[2]
            d = np.sqrt(pz[:, None, None] ** 2 + py[None, :, None] ** 2 + px[None, None, :] ** 2) - s[3]
            sub = (1.0 - smoothstep(0.0, self.dx * 1.8, d)).astype(np.float32)
            v[k0:k1, j0:j1, i0:i1] = np.maximum(v[k0:k1, j0:j1, i0:i1], sub)
        return v

    def __call__(self, uvw):
        uvw = np.asarray(uvw, dtype=np.float64).reshape(-1, 3)
        v = self.solid.sample_uvw(uvw).astype(np.float64) if self.solid is not None else np.zeros(len(uvw))
        if self.walls:
            v = np.maximum(v, self.walls_at(uvw).astype(np.float64))
        if len(self.spheres):
            pw = (uvw - 0.5) * self.W
            for s in self.spheres:
                d = np.linalg.norm(pw - s[:3], axis=1) - s[3]
                v = np.maximum(v, 1.0 - smoothstep(0.0, self.dx * 1.8, d))
        return v


def linear_resample(a, shape):
    """A cell-centred [z][y][x] field resampled at the cell centres of `shape` the way a linear, clamp-to-edge
    texture sampler reads it (separable, exact)."""
    a = np.asarray(a, dtype=np.float32)
    for ax in range(3):
        n_src, n_dst = a.shape[ax], shape[ax]
        if n_src == n_dst:
            continue
        t = (np.arange(n_dst) + 0.5) / n_dst * n_src - 0.5
        i0 = np.floor(t).astype(np.int64)
        f = (t - i0).astype(np.float32)
        lo = np.take(a, np.clip(i0, 0, n_src - 1), axis=ax)
        hi = np.take(a, np.clip(i0 + 1, 0, n_src - 1), axis=ax)
        sh = [1, 1, 1]
        sh[ax] = n_dst
        f = f.reshape(sh)
        a = lo + (hi - lo) * f
    return a


def cell_uvw(shape):
    """uvw of every cell centre of a [z][y][x] grid, flattened in that order, as (N, 3) (x, y, z)."""
    nz, ny, nx = shape
    k, j, i = np.meshgrid(np.arange(nz), np.arange(ny), np.arange(nx), indexing='ij')
    return np.stack([(i.ravel() + 0.5) / nx, (j.ravel() + 0.5) / ny, (k.ravel() + 0.5) / nz], axis=1)


def render_field(phi, o, dx, soft):
    """The field the surface is the zero contour of: (array [z][y][x], cell size per axis (three)). Blur and the
    cubic reconstruction act on the raw phi (as the engine's march read phiReadNode); the solid mask and the
    bias come after (phiAt / phiRC)."""
    a = np.asarray(phi, dtype=np.float32)
    if int(o.get('render_blur') or 0) > 0:
        a = blur121(a, min(2, int(o['render_blur'])))
    if o.get('smooth_surface'):
        a = bspline_upsample2(a)
    occ = soft.on_grid(a.shape)
    air = np.float32(dx * 4.0)
    a = a + (air - a) * smoothstep(0.30, 0.62, occ).astype(np.float32)
    a = a + np.float32(o.get('surface_bias') or 0.0)
    return a


def mesh_field(field, world3, center3, adaptivity=0.0):
    """Mesh the zero contour of a [z][y][x] field over the domain. Returns (verts (N, 3) Blender world
    coordinates, tris (T, 3), quads (Q, 4)). A one-voxel AIR border closes the surface at the domain's bounds
    (where the engine's ray box cut it)."""
    import openvdb as vdb
    nz, ny, nx = field.shape
    W = np.asarray(world3, dtype=np.float64)
    h = W / np.array([nx, ny, nz], dtype=np.float64)                  # cell size per axis (three x, y, z)
    air = float(max(field.max(), 1e-3))
    pad = np.pad(field, 1, mode='constant', constant_values=air)
    # three [z][y][x] -> Blender [x][y_b][z_b] with y_b = -z3 (reversed k), z_b = y3
    b = np.ascontiguousarray(pad.transpose(2, 0, 1)[:, ::-1, :])
    g = vdb.FloatGrid(air)
    g.copyFromArray(b.astype(np.float32))
    c = np.asarray(center3, dtype=np.float64)
    hx, hy3, hz3 = h
    # index (a, b, c) -> Blender: x = (a - 1 + 0.5) hx - Wx/2 + cx3, y_b = (b - 1 + 0.5) hz3 - Wz/2 - cz3,
    # z_b = (c - 1 + 0.5) hy3 - Wy/2 + cy3
    ox = -W[0] / 2 + c[0] - 0.5 * hx
    oy = -W[2] / 2 - c[2] - 0.5 * hz3
    oz = -W[1] / 2 + c[1] - 0.5 * hy3
    g.transform = vdb.createLinearTransform([[hx, 0, 0, 0], [0, hz3, 0, 0], [0, 0, hy3, 0], [ox, oy, oz, 1]])
    pts, tris, quads = g.convertToPolygons(isovalue=0.0, adaptivity=float(adaptivity))
    return (np.asarray(pts, dtype=np.float32).reshape(-1, 3), np.asarray(tris, dtype=np.int32).reshape(-1, 3),
            np.asarray(quads, dtype=np.int32).reshape(-1, 4))


def blender_to_local3(v, center3):
    v = np.asarray(v, dtype=np.float64)
    return np.stack([v[:, 0], v[:, 2], -v[:, 1]], axis=1) - np.asarray(center3, dtype=np.float64)


def cell_velocity(velocity):
    """The cell-centred velocity: the mean of each cell's two MAC faces (the engine's cellVel). `velocity` is the
    solver's (NZ, NY, NX, 3) face field."""
    v = np.asarray(velocity, dtype=np.float32)
    c = v.copy()
    c[:, :, 1:, 0] = 0.5 * (v[:, :, 1:, 0] + v[:, :, :-1, 0])
    c[:, 1:, :, 1] = 0.5 * (v[:, 1:, :, 1] + v[:, :-1, :, 1])
    c[1:, :, :, 2] = 0.5 * (v[1:, :, :, 2] + v[:-1, :, :, 2])
    return c


def vertex_speed(verts_b, velocity, world3, center3):
    """Flow speed (m/s) at each vertex: the cell-centred velocity sampled trilinearly."""
    sp = Grid(np.linalg.norm(cell_velocity(velocity), axis=-1), world3)
    if len(verts_b) == 0:
        return np.zeros(0, dtype=np.float32)
    return sp.sample(blender_to_local3(verts_b, center3)).astype(np.float32)


def vertex_shear(verts_b, velocity, soft, world3, center3, dx, reach_cells=2.0):
    """The flow's shear at each vertex (m/s): the largest speed difference between the water at the point and the
    water reach_cells away along +-x, +-y, +-z (taps in solids skipped). Water moving as one body (a stream in free
    fall, a falling slug, a still pool) reads near 0; fast water meeting slow water (a jet plunging into a pool, a slug
    landing, a crown leaving the impact) reads its speed difference: where real water entrains air and turns white."""
    n = len(verts_b)
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    W = np.asarray(world3, dtype=np.float64)
    c = cell_velocity(velocity)
    comps = [Grid(c[..., k], world3) for k in range(3)]
    P = blender_to_local3(verts_b, center3)

    def vel(q):
        return np.stack([g.sample(q) for g in comps], axis=1)

    u0 = vel(P)
    r = float(dx) * reach_cells
    best = np.zeros(n)
    for ax in range(3):
        for sgn in (-1.0, 1.0):
            e = np.zeros(3)
            e[ax] = sgn * r
            q = P + e
            uvw = q / W + 0.5
            usable = np.all((uvw >= 0.0) & (uvw <= 1.0), axis=1) & (soft(uvw) < 0.30)
            d = np.linalg.norm(vel(q) - u0, axis=1)
            best = np.where(usable, np.maximum(best, d), best)
    return best.astype(np.float32)


def vertex_attributes(verts_b, field_grid, soft, o, dx, world3, center3, camera_b=None):
    """thick and ring per vertex (the engine's per-pixel shading inputs), the normal from grad phi, and exit and
    bed (the refraction thickness EEVEE needs): (thick, ring, normal, exit, bed)."""
    W = np.asarray(world3, dtype=np.float64)
    P = blender_to_local3(verts_b, center3)
    n = len(P)
    if n == 0:                                   # no water this frame (an empty tank before a pour): an empty surface
        z = np.zeros(0, dtype=np.float32)
        return z, z, np.zeros((0, 3), dtype=np.float32), z, z
    # normal: central differences of the rendered field one sim cell either side (the engine's n)
    d = np.array([dx, dx, dx])
    g = np.zeros((n, 3))
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = d[ax]
        g[:, ax] = field_grid.sample(P + e) - field_grid.sample(P - e)
    nrm = g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)
    # thickness: 24 steps from the point to the domain box exit, counting the samples inside the water
    if o.get('thickness_mode', 'normal') == 'view' and camera_b is not None:
        cam = blender_to_local3(np.asarray(camera_b, dtype=np.float64).reshape(1, 3), center3)[0]
        dirs = P - cam
        dirs /= np.maximum(np.linalg.norm(dirs, axis=1, keepdims=True), 1e-12)
    else:
        dirs = -nrm
    h = W / 2
    with np.errstate(divide='ignore', invalid='ignore'):
        inv = 1.0 / np.where(np.abs(dirs) < 1e-9, 1e-9, dirs)
    ta = (-h - P) * inv
    tb = (h - P) * inv
    t_far = np.minimum.reduce(np.maximum(ta, tb), axis=1)
    t_far = np.maximum(t_far, 0.0)
    STEPS = 24
    step = t_far / STEPS
    thick = np.zeros(n)
    for k in range(STEPS):
        q = P + dirs * (step * (k + 0.5))[:, None]
        thick += np.where(field_grid.sample(q) < 0.0, step, 0.0)
    # the refraction thickness EEVEE needs (the material output's Thickness): the water path along the inward
    # normal to where it leaves the water, and whether it ends on a solid (or runs deep) instead of in air
    exit_len, bed = first_segment(P, -nrm, field_grid, soft, W, dx)
    # contact ring: max soft occupancy over the point and 1.6 cells along +-x, +-z and -y
    uvw = P / W + 0.5
    Wc = 1.6 / np.array([field_grid.nx, field_grid.ny, field_grid.nz], dtype=np.float64)
    if o.get('smooth_surface'):
        Wc = Wc * 2.0                                            # 1.6 SIM cells, not 1.6 fine cells
    ring = np.zeros(n)
    for off in ((0, 0, 0), (Wc[0], 0, 0), (-Wc[0], 0, 0), (0, 0, Wc[2]), (0, 0, -Wc[2]), (0, -Wc[1], 0)):
        ring = np.maximum(ring, soft(uvw + np.array(off)))
    # the normal in Blender axes for the PLY
    nb = np.stack([nrm[:, 0], -nrm[:, 2], nrm[:, 1]], axis=1)
    return (thick.astype(np.float32), ring.astype(np.float32), nb.astype(np.float32), exit_len.astype(np.float32),
            bed.astype(np.float32))


def first_segment(P, dirs, field_grid, soft, W, dx, max_cells=24.0, step_cells=0.75):
    """The water path from each surface point along dirs to where it leaves the water: (length in metres, bed).

    bed is 1 where the path ends on a solid (water over a basin's floor, against a wall or a body) or is still in
    water after max_cells (deep water), 0 where it leaves into air (a stream, a sheet, a drop). The render field
    blends solids to air, so the occupancy is tested first, at the mask's own onset (0.30). An air exit is placed
    at the linear zero crossing between the last two samples."""
    n = len(P)
    h = float(dx) * step_cells
    steps = int(np.ceil(max_cells / step_cells))
    length = np.full(n, steps * h)
    bed = np.ones(n, dtype=bool)
    alive = np.ones(n, dtype=bool)
    prev = np.full(n, -1e-6)
    for k in range(1, steps + 1):
        idx = np.nonzero(alive)[0]
        if len(idx) == 0:
            break
        t = k * h
        q = P[idx] + dirs[idx] * t
        uvw = q / W + 0.5
        out = np.any((uvw < 0.0) | (uvw > 1.0), axis=1)            # past the open domain: air
        solid = (soft(uvw) >= 0.30) & ~out
        f = field_grid.sample(q)
        air = ((f >= 0.0) | out) & ~solid
        hit_s = idx[solid]
        length[hit_s] = t
        alive[hit_s] = False
        hit_a = idx[air]
        fp, fc = prev[hit_a], f[air]
        frac = np.clip(fp / np.minimum(fp - fc, -1e-9), 0.0, 1.0)  # fp < 0 <= fc: where the line crosses zero
        length[hit_a] = t - h + frac * h
        bed[hit_a] = False
        alive[hit_a] = False
        prev[idx] = np.minimum(f, -1e-9)
    return length, bed


def write_ply(path, verts, tris, quads, attrs):
    """A binary PLY: positions + named float vertex properties (Blender's PLY import makes them point
    attributes) + triangles and quads."""
    import os
    n = len(verts)
    fields = [('x', '<f4'), ('y', '<f4'), ('z', '<f4')] + [(k, '<f4') for k in attrs]
    rec = np.zeros(n, dtype=fields)
    rec['x'], rec['y'], rec['z'] = verts[:, 0], verts[:, 1], verts[:, 2]
    for k, v in attrs.items():
        rec[k] = v
    hdr = ['ply', 'format binary_little_endian 1.0', f'element vertex {n}']
    hdr += [f'property float {k}' for k, _ in fields]
    hdr += [f'element face {len(tris) + len(quads)}', 'property list uchar int vertex_indices', 'end_header']
    t = np.zeros(len(tris), dtype=[('n', 'u1'), ('v', '<i4', 3)])
    t['n'] = 3
    t['v'] = tris
    q = np.zeros(len(quads), dtype=[('n', 'u1'), ('v', '<i4', 4)])
    q['n'] = 4
    q['v'] = quads
    tmp = path + '.tmp'
    with open(tmp, 'wb') as fh:
        fh.write(('\n'.join(hdr) + '\n').encode('ascii'))
        fh.write(rec.tobytes())
        fh.write(t.tobytes())
        fh.write(q.tobytes())
    os.replace(tmp, path)
