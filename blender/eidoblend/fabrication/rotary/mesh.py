"""Indexed XYZ rasters from actual source triangles, about the stock's X axis: the port of
eidoverse/robotics/rotary_mesh.js (meshEnvelope, rotaryMeshProgram). numpy planning; a Blender source is snapshot by
eidoblend.fabrication.source_geometry.

    from eidoblend.fabrication.rotary.mesh import rotary_mesh_program, mesh_envelope
    p = rotary_mesh_program(bpy.data.objects['bust'], material='wood', tool='flat', angles=12)
    p.report     # source triangles, reach-limited samples, the reach floor, retained end stock, limitations
    rotary_program(obj, ...) does the same: any source that is not a function is a mesh

The source is fitted into the cutting region (fit=False: used where it is, and refused if it does not fit). For each
of `angles` orientations the triangles are turned to face the cutter and their upper envelope is taken over a grid
(the maximum over every covered cell, so even a thin triangle between sampling rays is protected); each raster row's
samples then clear the cutter's whole swept footprint over that envelope. Rows are lateral rasters across the stock
(the stock's Y here; three's z). A shank-clearance floor keeps the non-cutting shank out of the original blank:
material beyond the flute's reach is left and reported, never silently pretended away.
"""

from __future__ import annotations

import math

import numpy as np

from ..cutting import stock_profile
from .._axes import Rec
from .path import CENTRE_SEAT, RotaryPath, TAU
from .setup import rotary_fixture_setup
from ..source_geometry import fit_source_geometry, source_geometry

SNAPSHOT_KEYS = ('matrix', 'space', 'visible_only', 'max_triangles')


def _turned(corners, angle):
    """(x, lateral, height) of every corner with the stock turned by `angle` about X: height is the turned Z, lateral
    the turned -Y (three's z, kept so the rows and their order are the WebGPU ones)."""
    c, s = math.cos(angle), math.sin(angle)
    y, z = corners[..., 1], corners[..., 2]
    return corners[..., 0], z * s - y * c, z * c + y * s


def mesh_envelope(geometry, angle, min_x, max_x, min_z, max_z, step):
    """meshEnvelope: the upper envelope (heights toward the cutter) of the source turned by `angle`, over a grid of
    cells min_x..max_x (along X) by min_z..max_z (lateral, three's z = the turned -Y) of about `step`. Each cell holds
    the highest point of any triangle clipped to it (-inf where none). geometry: what source_geometry returns (eidoblend.fabrication.source_geometry), or
    (N, 3, 3) corners. Returns a Rec: heights (nx * nz, x fastest), nx, nz, dx, dz, min_x, min_z."""
    corners = geometry.triangles if hasattr(geometry, 'triangles') else np.asarray(geometry, dtype=float)
    nx, nz = math.ceil((max_x - min_x) / step), math.ceil((max_z - min_z) / step)
    dx, dz = (max_x - min_x) / nx, (max_z - min_z) / nz
    heights = np.full(nx * nz, -np.inf)
    X, Z, Y = _turned(corners, angle)                                     # (T, 3) each
    ax = np.maximum(0, np.floor((X.min(1) - min_x) / dx).astype(np.int64) - 1)
    bx = np.minimum(nx - 1, np.floor((X.max(1) - min_x) / dx).astype(np.int64))
    az = np.maximum(0, np.floor((Z.min(1) - min_z) / dz).astype(np.int64) - 1)
    bz = np.minimum(nz - 1, np.floor((Z.max(1) - min_z) / dz).astype(np.int64))
    wx, wz = np.maximum(0, bx - ax + 1), np.maximum(0, bz - az + 1)
    count = wx * wz
    total = int(count.sum())
    if total == 0:
        return Rec(heights=heights, nx=nx, nz=nz, dx=dx, dz=dz, min_x=min_x, min_z=min_z)
    chunk = 2_000_000
    tri_of = np.repeat(np.arange(len(X)), count)
    starts = np.repeat(np.cumsum(count) - count, count)
    local = np.arange(total) - starts
    for c0 in range(0, total, chunk):
        sl = slice(c0, min(total, c0 + chunk))
        t, k = tri_of[sl], local[sl]
        ix = ax[t] + k % wx[t]
        iz = az[t] + k // wx[t]
        best = _cell_max(X[t], Z[t], Y[t], min_x + ix * dx, min_x + (ix + 1) * dx, min_z + iz * dz,
                         min_z + (iz + 1) * dz)
        np.maximum.at(heights, ix + nx * iz, best)
    return Rec(heights=heights, nx=nx, nz=nz, dx=dx, dz=dz, min_x=min_x, min_z=min_z)


def _cell_max(X, Z, Y, x0, x1, z0, z1, tol=1e-12):
    """For triangle / cell pairs: the highest point of the triangle clipped to the cell (Sutherland-Hodgman's output
    vertices: corners inside, edge crossings of the cell's sides, cell corners inside the triangle), -inf if none."""
    best = np.full(len(X), -np.inf)
    xs, zs = x0[:, None], z0[:, None]
    inside = (X - xs >= -tol) & (x1[:, None] - X >= -tol) & (Z - zs >= -tol) & (z1[:, None] - Z >= -tol)
    best = np.maximum(best, np.where(inside, Y, -np.inf).max(1))
    with np.errstate(all='ignore'):
        for i, j in ((0, 1), (1, 2), (2, 0)):
            xa, xb, za, zb, ya, yb = X[:, i], X[:, j], Z[:, i], Z[:, j], Y[:, i], Y[:, j]
            for val, along, other_a, other_b, olo, ohi in ((x0, (xa, xb), za, zb, z0, z1), (x1, (xa, xb), za, zb, z0, z1),
                                                           (z0, (za, zb), xa, xb, x0, x1), (z1, (za, zb), xa, xb, x0, x1)):
                da, db = along[0] - val, along[1] - val
                cross = ((da > 0) & (db < 0)) | ((da < 0) & (db > 0))
                t = da / (da - db)
                o = other_a + (other_b - other_a) * t
                ok = cross & (o - olo >= -tol) & (ohi - o >= -tol)
                best = np.maximum(best, np.where(ok, ya + (yb - ya) * t, -np.inf))
        # cell corners inside the triangle (its plane's height there)
        e1x, e1z, e2x, e2z = X[:, 1] - X[:, 0], Z[:, 1] - Z[:, 0], X[:, 2] - X[:, 0], Z[:, 2] - Z[:, 0]
        det = e1x * e2z - e2x * e1z
        good = det != 0
        for cx, cz in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
            px, pz = cx - X[:, 0], cz - Z[:, 0]
            u = (px * e2z - e2x * pz) / det
            v = (e1x * pz - px * e1z) / det
            ins = good & (u >= 0) & (v >= 0) & (u + v <= 1)
            h = Y[:, 0] + u * (Y[:, 1] - Y[:, 0]) + v * (Y[:, 2] - Y[:, 0])
            best = np.maximum(best, np.where(ins, h, -np.inf))
    return best


def _footprints(grid, x0, x1, z, R, kind):
    """footprint for every sample of one raster row: the highest point the cutter's footprint (swept from x0 to x1 at
    lateral z) meets over the envelope, the ball's dome included; -inf where it meets nothing."""
    H = grid.heights.reshape(grid.nz, grid.nx)                            # [z][x]
    ax = np.maximum(0, np.floor((x0 - R - grid.min_x) / grid.dx).astype(np.int64))
    bx = np.minimum(grid.nx - 1, np.floor((x1 + R - grid.min_x) / grid.dx).astype(np.int64))
    az = max(0, math.floor((z - R - grid.min_z) / grid.dz))
    bz = min(grid.nz - 1, math.floor((z + R - grid.min_z) / grid.dz))
    out = np.full(len(x0), -np.inf)
    if az > bz:
        return out
    wmax = int((bx - ax).max()) + 1 if len(ax) else 0
    if wmax <= 0:
        return out
    off = np.arange(wmax)
    ii = ax[:, None] + off[None, :]                                       # (S, W)
    valid_i = ii <= bx[:, None]
    iic = np.minimum(ii, grid.nx - 1)
    cx = np.maximum(0.0, np.maximum(grid.min_x + iic * grid.dx - x1[:, None],
                                    x0[:, None] - grid.min_x - (iic + 1) * grid.dx))
    for j in range(az, bz + 1):
        cz = max(0.0, grid.min_z + j * grid.dz - z, z - grid.min_z - (j + 1) * grid.dz)
        h = H[j][iic]
        r2 = cx * cx + cz * cz
        ok = valid_i & np.isfinite(h) & (r2 <= R * R)
        val = h + (np.sqrt(np.maximum(0.0, R * R - r2)) - R if kind == 'ball' else 0.0)
        out = np.maximum(out, np.where(ok, val, -np.inf).max(1))
    return out


def rotary_mesh_program(source, **options):
    """rotaryMeshProgram (see the module docstring). Options: the blank (stock_length, stock_width, stock_height,
    quill), material, radius (0.003), tool ('flat' | 'ball'), flute_length, angles (4..96, default 12), sample_step
    (0.001), grid_step (0.0005), stepover (0.55 radius), stepdown, rough_allowance (0.0005), tolerance (0.00005), feed,
    plunge, rpm, fit (True), require_reach (False), and the snapshot's matrix, space, visible_only, max_triangles."""
    def opt(key, default):
        v = options.get(key)
        return default if v is None else v
    setup = rotary_fixture_setup(**{k: options[k] for k in ('stock_length', 'stock_width', 'stock_height', 'quill')
                                    if options.get(k) is not None})
    profile = stock_profile(opt('material', 'wood'))
    L, W, Hs = setup['stock_length'], setup['stock_width'], setup['stock_height']
    axis_height, axis_x, start, end = setup['axis_height'], setup['axis_x'], setup['start'], setup['end']
    radius = opt('radius', .003)
    kind = opt('tool', 'flat')
    flute_length = opt('flute_length', .018 if kind == 'flat' else .017)
    angles = opt('angles', 12)
    sample_step, grid_step = opt('sample_step', .001), opt('grid_step', .0005)
    stepover, stepdown = opt('stepover', radius * .55), opt('stepdown', profile['stepdown'])
    allowance, tolerance = opt('rough_allowance', .0005), opt('tolerance', .00005)
    feed, plunge, rpm = opt('feed', profile['feed']), opt('plunge', profile['plunge']), opt('rpm', profile['rpm'])
    if kind not in ('flat', 'ball'):
        raise ValueError('Rotary tool must be flat or ball')
    if not (isinstance(angles, (int, float)) and not isinstance(angles, bool) and float(angles).is_integer()
            and 4 <= angles <= 96):
        raise ValueError('Mesh indexing requires 4–96 orientations')
    angles = int(angles)

    def fin(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if (not all(fin(v) and v > 0 for v in (radius, flute_length, sample_step, grid_step, stepover, stepdown, feed, plunge,
                                          rpm))
            or not all(fin(v) and v >= 0 for v in (allowance, tolerance))
            or grid_step < .0001 or sample_step < .0002 or stepover > radius * 1.5 or stepover < .0002):
        raise ValueError('Invalid mesh machining resolution, tool or feed')
    box = ((start, -W / 2 + .0005, -Hs / 2 + .0005), (end, W / 2 - .0005, Hs / 2 - .0005))
    snap = {k: options[k] for k in SNAPSHOT_KEYS if options.get(k) is not None}
    geometry = source_geometry(source, **snap) if options.get('fit') is False else \
        fit_source_geometry(source, bounds=box, **snap)
    gmin, gmax = geometry.bounding_box
    if any(gmin[k] < box[0][k] - 1e-8 or gmax[k] > box[1][k] + 1e-8 for k in range(3)):
        raise ValueError('Target does not fit the cutting region; enable fit or change stock size')
    stock_radius = math.hypot(W / 2, Hs / 2)
    safe = stock_radius + .0022
    # conservative shank clearance against the original blank: never cut with the non-cutting shank, and never
    # pretend that unreachable stock vanished
    reach_floor = stock_radius - flute_length + .0006
    nx = math.ceil((end - start) / sample_step)
    nz = math.ceil(2 * stock_radius / stepover)
    report = Rec(source=geometry.manufacturing_source, orientations=angles, tool=kind, grid_step=grid_step,
                    reach_limited_samples=0, minimum_requested_tip=math.inf, reach_floor=reach_floor,
                    retained_end_stock=[start + L / 2, L / 2 - end],
                    limitations=['Indexed machining about X preserves surfaces inaccessible to these directions and '
                                 'this cutter.', 'Sacrificial end stock and any material beyond cutting-length reach '
                                 'remain in the simulated result.'])
    xs = start + (end - start) * np.arange(nx + 1) / nx
    x0s, x1s = xs[:-1], xs[1:]
    rows = []
    for j in range(angles):
        angle = -j * math.pi * 2 / angles
        grid = mesh_envelope(geometry, angle, start - radius, end + radius, -stock_radius - radius,
                             stock_radius + radius, grid_step)
        station = []
        for k in range(nz + 1):
            z = -stock_radius + 2 * stock_radius * k / nz
            req = _footprints(grid, x0s, x1s, z, radius, kind)
            fin_ = np.isfinite(req)
            if fin_.any():
                report['minimum_requested_tip'] = min(report['minimum_requested_tip'], float(req[fin_].min()))
                report['reach_limited_samples'] += int((fin_ & (req + tolerance < reach_floor)).sum())
            seg = np.maximum(reach_floor, req + tolerance)
            left = seg[np.maximum(0, np.arange(nx + 1) - 1)]
            right = seg[np.minimum(nx - 1, np.arange(nx + 1))]
            ys = np.maximum(left, right)
            station.append([(float(xs[i]), float(ys[i]), z) for i in range(nx + 1)])    # (x, height, lateral)
        rows.append(station)
    if options.get('require_reach') and report['reach_limited_samples']:
        raise ValueError(f'Target exceeds cutter reach at {report["reach_limited_samples"]} sampled footprints; use '
                         'smaller stock, a longer tool, or another setup')
    minimum = min(p[1] for station in rows for row in station for p in row)
    floors = []
    y = stock_radius - stepdown
    while y > minimum + allowance:
        floors.append(y)
        y -= stepdown
    floors.append(minimum + allowance)
    floors.append(None)
    stages, moves = [], []
    cur = {'p': (start, safe, 0.0), 'a': 0.0}                            # (x, height, lateral) as the JS rows

    def push(p3, a, kind_, stage, rate=None):
        moves.append({'position': (p3[0], -p3[2], p3[1]), 'angle': a, 'type': kind_, 'stage': stage, 'feed': rate})
        cur['p'], cur['a'] = p3, a

    push(cur['p'], 0.0, 'rapid', 'setup')
    for pass_ in range(len(floors)):
        finish = floors[pass_] is None
        stage = 'finish' if finish else 'rough %d' % (pass_ + 1)
        stages.append({'name': stage, 'first_move': len(moves)})
        for j in range(angles):
            a = -(pass_ + j / angles) * TAU
            push((cur['p'][0], safe, cur['p'][2]), cur['a'], 'rapid', stage)
            push(cur['p'], a, 'index', stage)
            row_stride = 1 if finish else max(1, math.floor(radius * 1.25 / stepover))
            for k in range(0, len(rows[j]), row_stride):
                row = [(x, yy if finish else max(floors[pass_], yy + allowance), zz) for x, yy, zz in rows[j][k]]
                if not finish:
                    stride = max(1, math.floor(.003 / sample_step))
                    coarse = []
                    for i in range(0, len(row), stride):
                        e = min(len(row) - 1, i + stride)
                        s0 = max(0, i - stride)
                        coarse.append((row[i][0], max(p[1] for p in row[s0:e + 1]), row[i][2]))
                    if coarse[-1][0] != row[-1][0]:
                        coarse.append((row[-1][0], max(p[1] for p in row[-stride - 1:]), row[-1][2]))
                    row = coarse
                if k % 2:
                    row.reverse()
                push((cur['p'][0], safe, cur['p'][2]), a, 'rapid', stage)
                push((row[0][0], safe, row[0][2]), a, 'rapid', stage)
                push(row[0], a, 'cut', stage, plunge)
                for p in row[1:]:
                    push(p, a, 'cut', stage, feed)
    push((cur['p'][0], safe, cur['p'][2]), cur['a'], 'rapid', 'retract')
    if len(moves) > 400000:
        raise ValueError('Mesh toolpath exceeds 400,000 moves; increase sampling or stepover')
    path = RotaryPath(moves, feed=feed, rapid=opt('rapid', .08), acceleration=opt('acceleration', .3),
                      rotation_speed=opt('rotation_speed', .8))
    settings = Rec(stock_length=L, stock_width=W, stock_height=Hs, start=start, end=end, axis_x=axis_x,
                      axis_height=axis_height, radius=radius, flute_length=flute_length, tool=kind, angles=angles,
                      sample_step=sample_step, stepover=stepover, grid_step=grid_step, safe=safe,
                      material=opt('material', 'wood'), feed=feed, plunge=plunge, rpm=rpm, stepdown=stepdown,
                      centre_seat=dict(CENTRE_SEAT))
    return Rec(moves=moves, path=path, stages=stages, report=report, settings=settings, target=source,
                  geometry=geometry)
