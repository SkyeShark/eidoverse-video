"""Rain exposure for wet surfaces: Eanpa's rain surface field (engine/rain_surface_field.js) as a world-space map.

The WebGPU field renders the first surface seen along the incoming rain into a depth / normal target around the
camera, and wet receivers compare their position with that captured surface: under a roof or an awning a surface is
sheltered (no wetness, no puddles), in the open it is exposed. Here the same first-surface capture is ray cast once
per bake over the set's extent along one rain direction (the rain-weighted mean of the bake: Blender renders offline,
and a set's geometry does not walk with the camera), and written as an EXR: RGB = the hit normal, A = the hit
height, per line of rain through each texel of the z = 0 plane. eido_wet compares a fragment with the plane of its
line's captured surface (not the texel centre's depth, which would draw the texel grid on sloped surfaces), with
Eanpa's bias: 0.06 m plus 0.28 m on surfaces the rain grazes.

The gusts (soft_map). That exact test draws a rain shadow as the projected roof line, hard to the centimetre, and a
lightning flash glares on the wet side of it as a sharp polygon. Real rain swings with the gusts (+-8 degrees moves
the shadow of a 15 m building about 2.4 m), so the capture also finds the lowest surface along each line (cast up
from below), marks a line blocked when its first surface stands well above its lowest (a roof or an awning over the
ground), and blurs that mask along the wind with a triangle whose width follows the occluder's height (GUST_SPREAD):
a second EXR, R = the blurred mask, G = the lowest surface's height. Ground-level fragments read it with linear
filtering (a smooth ramp a few metres wide, no bands); raised surfaces keep the exact test.
"""
import math

import numpy as np

NO_HIT = -1.0e4
BLOCK_ABOVE = 0.6           # metres a line's first surface must stand above its lowest to shelter the ground
GROUND_LEVEL = 0.6          # metres above a line's lowest surface a fragment still counts as ground


def mean_rain_direction(rows):
    """The rain-weighted mean falling direction (Blender, unit, z < 0) of planned frames."""
    acc = np.zeros(3)
    for r in rows:
        w = max(0.0, r['rain_k'])
        s = r['src']                       # the source direction (up the rain)
        acc -= np.array(s) * w
    if np.linalg.norm(acc) < 1e-9:
        return (0.0, 0.0, -1.0)
    acc /= np.linalg.norm(acc)
    return tuple(float(c) for c in acc)


GUST_SPREAD = 0.15          # metres the rain shadow's edge swings per metre of occluder height (about +-8.5 degrees)
GUST_MAX = 2.5              # the widest half-penumbra, metres


def gust_scale(direction):
    """1 for rain tilted by tan 0.2 (about 11 degrees) or more, falling to 0 as the rain turns vertical (a drip line
    under an awning stays sharp in still air)."""
    dx, dy, dz = direction
    h = math.hypot(dx, dy)
    return min(1.0, max(0.0, h / max(abs(dz), 1e-6) / 0.2))


def capture(objects, direction, bounds, texel=0.15, top=None, log=print, lowest=False):
    """(map RGBA float32 [rows = y, cols = x], meta) of the first surface along `direction` over bounds
    (x0, y0, x1, y1) on the z = 0 plane. objects: mesh objects (evaluated, world space). lowest=True also returns
    the lowest surface along each line (z, NO_HIT where none): (map, meta, z_low)."""
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys, zmax, zmin = [], [], 0.0, 0.0
    for ob in objects:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        base = len(verts)
        for v in me.vertices:
            w = mw @ v.co
            verts.append(w)
            zmax = max(zmax, w.z)
            zmin = min(zmin, w.z)
        polys.extend(tuple(base + i for i in p.vertices) for p in me.polygons)
        ev.to_mesh_clear()
    d = Vector(direction).normalized()
    if d.z > -0.05:
        raise ValueError('shelter.capture: the rain direction must fall (z < 0)')
    x0, y0, x1, y1 = bounds
    W = max(8, int(math.ceil((x1 - x0) / texel)))
    H = max(8, int(math.ceil((y1 - y0) / texel)))
    out = np.zeros((H, W, 4), np.float32)
    out[..., 2] = 1.0
    out[..., 3] = NO_HIT
    z_low = np.full((H, W), NO_HIT, np.float32)
    meta = dict(x0=x0, y0=y0, sx=W * texel, sy=H * texel, w=W, h=H, d=tuple(d), texel=texel)
    if not polys:
        return (out, meta, z_low) if lowest else (out, meta)
    bvh = BVHTree.FromPolygons(verts, polys)
    ztop = (top if top is not None else zmax) + 5.0
    zbot = zmin - 5.0
    k = ztop / -d.z                         # along -d from the z = 0 line point up to ztop
    kb = zbot / d.z                         # along +d from the z = 0 line point down to zbot
    far = (ztop - zbot + 50.0) / -d.z
    up = -d
    cast = bvh.ray_cast
    for j in range(H):
        yc = y0 + (j + 0.5) * texel
        for i in range(W):
            xc = x0 + (i + 0.5) * texel
            o = Vector((xc - d.x * k, yc - d.y * k, ztop))
            loc, nrm, _idx, _dist = cast(o, d, far)
            if loc is not None:
                n = nrm.normalized()
                if n.dot(d) > 0:            # a back face: the surface faces away from the rain, still a roof
                    n = -n
                out[j, i] = (n.x, n.y, n.z, loc.z)
                if lowest:
                    lo, _n, _i, _d = cast(Vector((xc + d.x * kb, yc + d.y * kb, zbot)), up, far)
                    z_low[j, i] = lo.z if lo is not None else loc.z
    log('[weather] rain exposure %dx%d (%.2f m texels) along (%.3f, %.3f, %.3f)' % (W, H, texel, d.x, d.y, d.z))
    return (out, meta, z_low) if lowest else (out, meta)


def soft_map(rgba, z_low, meta):
    """The gust-softened ground mask (H, W, 4) float32: R = the blocked-line mask blurred along the wind with a
    triangle kernel whose half-width follows the local occluder height (GUST_SPREAD per metre, at most GUST_MAX, x
    gust_scale), G = the lowest surface's height (0 on a line that meets nothing), B = the unblurred mask, A = 1."""
    zh = rgba[..., 3]
    hit = (zh > NO_HIT / 2) & (z_low > NO_HIT / 2)
    blocked = (hit & (zh - z_low > BLOCK_ABOVE)).astype(np.float64)
    occ_h = np.where(blocked > 0, zh - z_low, 0.0)
    texel = meta['texel']
    g = gust_scale(meta['d'])
    dx, dy, _dz = meta['d']
    h = math.hypot(dx, dy)
    acc = blocked.copy()
    reach = GUST_MAX * g
    if reach > texel and h > 1e-6:
        wx, wy = dx / h, dy / h
        H, W = blocked.shape
        jj, ii = np.mgrid[0:H, 0:W].astype(np.float64)
        offs = np.linspace(-reach, reach, 2 * int(math.ceil(reach / (texel * 0.5))) + 1)

        def shifted(a, s, linear):
            pi = np.clip(ii + s * wx / texel, 0, W - 1)
            pj = np.clip(jj + s * wy / texel, 0, H - 1)
            if not linear:
                return a[np.rint(pj).astype(int), np.rint(pi).astype(int)]
            i0, j0 = np.floor(pi).astype(int), np.floor(pj).astype(int)
            i1, j1 = np.minimum(i0 + 1, W - 1), np.minimum(j0 + 1, H - 1)
            fi, fj = pi - i0, pj - j0
            return ((a[j0, i0] * (1 - fi) + a[j0, i1] * fi) * (1 - fj)
                    + (a[j1, i0] * (1 - fi) + a[j1, i1] * fi) * fj)
        # the half-width at each texel: the tallest occluder within reach along the wind sets how far its edge swings
        hmax = np.zeros_like(occ_h)
        for s in offs:
            hmax = np.maximum(hmax, shifted(occ_h, s, False))
        half = np.clip(hmax * GUST_SPREAD * g, texel, reach)
        acc = np.zeros_like(blocked)
        wsum = np.zeros_like(blocked)
        for s in offs:
            wgt = np.maximum(0.0, 1.0 - abs(s) / (half + texel))   # a triangle of that width: smooth shoulders
            acc += shifted(blocked, s, True) * wgt
            wsum += wgt
        acc /= np.maximum(wsum, 1e-9)
    out = np.zeros(blocked.shape + (4,), np.float32)
    out[..., 0] = acc
    out[..., 1] = np.where(z_low > NO_HIT / 2, z_low, 0.0)      # no surface on the line: ground at 0 (it filters)
    out[..., 2] = blocked
    out[..., 3] = 1.0
    return out


def exposure_at(px, py, pz, nz_incidence, rgba, meta, soft=None):
    """The shader's exposure in numpy, for tests: 1 exposed, 0 sheltered. The exact test on the fragment's line of
    rain (Eanpa's), and for a ground-level fragment (within GROUND_LEVEL of its line's lowest surface) the gust-soft
    mask instead, read bilinearly, as eido_wet does. soft: the soft_map array (None: the exact test only)."""
    dx, dy, dz = meta['d']
    x0 = px - dx * (pz / dz)
    y0 = py - dy * (pz / dz)
    u = (x0 - meta['x0']) / meta['sx']
    v = (y0 - meta['y0']) / meta['sy']
    if not (0 <= u < 1 and 0 <= v < 1):
        return 1.0
    exact = 1.0
    i, j = int(u * meta['w']), int(v * meta['h'])
    nx, ny, nz, zh = rgba[j, i]
    if zh > NO_HIT / 2:
        xc = meta['x0'] + (i + 0.5) / meta['w'] * meta['sx']
        yc = meta['y0'] + (j + 0.5) / meta['h'] * meta['sy']
        hx, hy = xc + dx * (zh / dz), yc + dy * (zh / dz)
        sep = (px - hx) * nx + (py - hy) * ny + (pz - zh) * nz
        bias = 0.06 + (1 - nz_incidence) * 0.28
        t = min(1.0, max(0.0, (sep - (-bias - 0.025)) / 0.05))
        exact = t * t * (3 - 2 * t)
    if soft is None:
        return exact
    fu, fv = u * meta['w'] - 0.5, v * meta['h'] - 0.5          # bilinear on texel centres, clamped at the edges
    i0, j0 = int(math.floor(fu)), int(math.floor(fv))
    a, b = fu - i0, fv - j0

    def at(jj, ii):
        return soft[min(max(jj, 0), meta['h'] - 1), min(max(ii, 0), meta['w'] - 1)]
    s = ((at(j0, i0) * (1 - a) + at(j0, i0 + 1) * a) * (1 - b) + (at(j0 + 1, i0) * (1 - a) + at(j0 + 1, i0 + 1) * a) * b)
    ground = (pz - s[1]) < GROUND_LEVEL
    return float(1.0 - s[0]) if ground else exact
