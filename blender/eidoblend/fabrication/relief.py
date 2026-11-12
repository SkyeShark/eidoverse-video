"""eidoblend.fabrication.relief: sampled 3-axis relief planning in stock coordinates (relief.js, MIT).

Stock coordinates: Blender's axes, metres, origin at the centre of the stock's footprint on the bed, Z up; the stock
spans x in [-width/2, width/2], y in [-depth/2, depth/2], height 0 .. stock_height.

    h = relief_from_mesh(source, width=.078, depth=.128, stock_height=.020, floor=.004, columns=129, rows=193)
        the upper visible envelope of a mesh / object / collection (placed in stock coordinates first) by downward
        rays: {width, depth, columns, rows, heights (float32, row j at y = (j / (rows - 1) - .5) * depth, column i
        at x = (i / (columns - 1) - .5) * width), floor, interpretation}
    p = relief_program(target, **options)
        target: a height function f(x, y) -> metres, a sampled heightfield like the one above, or a mesh source.
        Roughing rasters at successive levels (stepdown, rough_stepover, leaving rough_allowance), then a finer
        finishing raster (stepover, surface_tolerance); ball-footprint compensation lifts the tip over neighbouring
        high ground. Returns {points, stages [{name, start_distance, end_distance, start_index, end_index}], cutter,
        radius, width, depth, stock_width, stock_depth, stock_height, stepover, sample_step, surface_tolerance,
        rough_allowance, sampling, target}
    sample_relief(x, y)   the original Eidoverse relief: an asymmetric flowing crest on a recessed land

relief_program options (metres): stock_width .078, stock_depth .128, stock_height .020, radius .003, width (stock_width
- 4 radius), depth (stock_depth - 4 radius), stepdown .003, rough_stepover (.8 radius), stepover .0008, sample_step
.001, clearance .006, rough_allowance .0005, surface_tolerance .00005, floor (mesh sampling), flute_length .018,
plunge .003, feed (per cut move when given); and this edition's lift_over_steps (False: the WebGPU planner exactly).

The planner samples the ball-compensated tip every sample_step along each row and moves straight between samples.
That is right for a relief (sample_relief: the cutter never dips below the target), but beside a wall taller than the
leave the needed tip climbs within one step and the straight move cuts into the wall (4.2 mm into the 12.8 mm walls
of the fork bracket sample fitted as the inspector fits a supplied mesh). The eight-ring ball kernel adds to it: its
height steps grow toward the rim, so a wall between two outer rings is under-read by up to 0.48 radius. With
lift_over_steps=True every move is checked between its ends and the tool lifts over such steps, and a tip whose ball
rides a wall on its outer rings is read again with a fine rim (a sampled heightfield's in one numpy call, a height
function's point by point): 0.1 mm of cut is left on the bracket (from 4.2 mm), 0.05 mm on the ring, none on the
handle. A program whose moves all pass the check and whose ball never rides its outer rings, a smooth relief such as
sample_relief, comes out unchanged. A sampled heightfield's kernel runs as one numpy call per tip (the same float64
operations, the same values, about 9x faster).
"""

from __future__ import annotations

import math

import numpy as np

from ._axes import positive

INTERPRETATION = 'Upper visible envelope; vertical undercuts are not reachable by this 3-axis tool'
RIM_SPACING = .0001             # lift_over_steps: the fine rim's points, and a height function's move checks, 0.1 mm apart
SAMPLING = 'Ball footprint compensation on a finite sampled target; output stock is the actual swept cutter envelope'


def _clamp(v, a, b):
    return max(a, min(b, v))


def _is_mesh_source(source):
    try:
        import bpy
        if isinstance(source, (bpy.types.Object, bpy.types.Collection, bpy.types.Mesh)):
            return True
    except ImportError:
        pass
    from .three_geometry import Geom
    from .source_geometry import SourceGeometry
    return isinstance(source, (Geom, SourceGeometry))


def relief_from_mesh(source, width=.078, depth=.128, stock_height=.020, floor=.004, columns=129, rows=193):
    for v in (width, depth, stock_height):
        positive(v, 'Relief bounds')
    if not all(isinstance(n, int) and 2 <= n <= 513 for n in (columns, rows)):
        raise ValueError('Relief sampling dimensions must be 2..513')
    if not (floor >= 0 and floor < stock_height):
        raise ValueError('Invalid relief floor')
    if not _is_mesh_source(source):
        raise TypeError('Expected a Mesh, Object, Collection or geometry')
    from .source_geometry import source_geometry
    g = source_geometry(source)
    lo, hi = g.bounding_box
    if lo[2] < floor - 1e-6 or hi[2] > stock_height + 1e-6:
        raise ValueError('Relief source must fit above its floor and below the stock top; place it in metres first')
    if lo[0] < -width / 2 or hi[0] > width / 2 or lo[1] < -depth / 2 or hi[1] > depth / 2:
        raise ValueError('Relief source extends outside stock')
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    verts = g.triangles.reshape(-1, 3)
    tree = BVHTree.FromPolygons([tuple(p) for p in verts.tolist()], [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(g.triangles))],
                                all_triangles=True, epsilon=0.0)
    heights = np.empty(columns * rows, dtype=np.float32)
    down = Vector((0.0, 0.0, -1.0))
    top = stock_height + .01
    for j in range(rows):
        y = (j / (rows - 1) - .5) * depth
        for i in range(columns):
            x = (i / (columns - 1) - .5) * width
            hit = tree.ray_cast(Vector((x, y, top)), down)
            heights[j * columns + i] = max(floor, hit[0].z) if hit[0] is not None else floor
    return {'width': width, 'depth': depth, 'columns': columns, 'rows': rows, 'heights': heights, 'floor': floor,
            'interpretation': INTERPRETATION}


def _sampler(source, width, depth, stock_height, floor=None):
    if callable(source):
        return source
    if _is_mesh_source(source):
        kw = dict(width=width, depth=depth, stock_height=stock_height)
        if floor is not None:
            kw['floor'] = floor
        source = relief_from_mesh(source, **kw)
    src = source or {}
    heights, columns, rows = src.get('heights'), src.get('columns'), src.get('rows')
    w, d = src.get('width'), src.get('depth')
    if heights is None or columns is None or rows is None or len(heights) != columns * rows or columns < 2 or rows < 2 \
            or not (w and d and w > 0 and d > 0):
        raise ValueError('Relief needs a height function, sampled heightfield, or mesh')
    hs = np.asarray(heights, dtype=np.float64)

    def target(x, y):
        u = _clamp((x / w + .5) * (columns - 1), 0, columns - 1)
        v = _clamp((y / d + .5) * (rows - 1), 0, rows - 1)
        i = min(columns - 2, math.floor(u))
        j = min(rows - 2, math.floor(v))
        a, b = hs[j * columns + i], hs[j * columns + i + 1]
        c, e = hs[(j + 1) * columns + i], hs[(j + 1) * columns + i + 1]
        return (a + (b - a) * (u - i)) * (1 - (v - j)) + (c + (e - c) * (u - i)) * (v - j)

    def many(xs, ys):
        """target over numpy arrays: the same float64 operations in the same order, so the same values"""
        u = np.clip((xs / w + .5) * (columns - 1), 0, columns - 1)
        v = np.clip((ys / d + .5) * (rows - 1), 0, rows - 1)
        i = np.minimum(columns - 2, np.floor(u)).astype(np.int64)
        j = np.minimum(rows - 2, np.floor(v)).astype(np.int64)
        a, b = hs[j * columns + i], hs[j * columns + i + 1]
        c, e = hs[(j + 1) * columns + i], hs[(j + 1) * columns + i + 1]
        return (a + (b - a) * (u - i)) * (1 - (v - j)) + (c + (e - c) * (u - i)) * (v - j)
    target.many = many
    target.cell = min(w / (columns - 1), d / (rows - 1))
    return target


def relief_program(source, **options):
    o = options
    stock_width = o.get('stock_width', .078)
    stock_depth = o.get('stock_depth', .128)
    stock_height = o.get('stock_height', .020)
    radius = o.get('radius', .003)
    width = o.get('width') if o.get('width') is not None else stock_width - radius * 4
    depth = o.get('depth') if o.get('depth') is not None else stock_depth - radius * 4
    stepdown = o.get('stepdown') if o.get('stepdown') is not None else .003
    rough_stepover = o.get('rough_stepover') if o.get('rough_stepover') is not None else radius * .8
    stepover = o.get('stepover') if o.get('stepover') is not None else .0008
    sample_step = o.get('sample_step') if o.get('sample_step') is not None else .001
    clearance = o.get('clearance') if o.get('clearance') is not None else .006
    allowance = o.get('rough_allowance') if o.get('rough_allowance') is not None else .0005
    tolerance = o.get('surface_tolerance') if o.get('surface_tolerance') is not None else .00005
    for name, v in dict(stock_width=stock_width, stock_depth=stock_depth, stock_height=stock_height, radius=radius,
                        width=width, depth=depth, stepdown=stepdown, rough_stepover=rough_stepover, stepover=stepover,
                        sample_step=sample_step, clearance=clearance, allowance=allowance, tolerance=tolerance).items():
        positive(v, name)
    if width + 2 * radius > stock_width or depth + 2 * radius > stock_depth:
        raise ValueError('Relief footprint and ball radius must stay inside the stock')
    if stepover > radius or rough_stepover > radius * 1.5:
        raise ValueError('Relief stepover would leave unsupported strips between passes')
    if sample_step > radius or tolerance > allowance:
        raise ValueError('Use a sample step no larger than the tool radius and tolerance below rough allowance')
    target = _sampler(source, stock_width, stock_depth, stock_height, o.get('floor'))
    # the ball's lower surface as rings of offsets (dx, dy) and its height above the tip; the rows run toward -y as
    # three's ran toward +z, so a raster visits the same world points in the same order as the WebGPU planner
    kernel = [(0.0, 0.0, 0.0)]
    for ring in range(1, 9):
        r = radius * ring / 8
        n = max(12, ring * 8)
        for i in range(n):
            a = i / n * math.pi * 2
            kernel.append((math.cos(a) * r, -math.sin(a) * r, radius - math.sqrt(radius * radius - r * r)))
    cache = {}
    many = getattr(target, 'many', None)                # a sampled heightfield: the kernel in one numpy call
    kx, ky, kb = (np.array(c) for c in zip(*kernel))
    ring_of = np.array([0] + [ring for ring in range(1, 9) for _ in range(max(12, ring * 8))])
    lift = bool(o.get('lift_over_steps', False))
    rim = None
    if lift:
        # the ball's rim, finely (lift_over_steps only): rings from half the radius outward (the kernel's fourth ring),
        # each 1/64 of the radius higher on the ball than the last, points 0.1 mm apart around them. The eight-ring
        # kernel's height steps grow toward the rim (its last rises 0.48 radius), so a wall between two of its outer
        # rings is under-read by up to that step; the rim reads it again wherever the kernel's highest point lies on
        # its fifth ring or beyond.
        pts = []
        h0 = radius - math.sqrt(radius * radius - (.5 * radius) ** 2)
        steps = math.ceil((radius - h0) / (radius / 64))
        for k in range(steps + 1):
            h = h0 + (radius - h0) * k / steps
            rho = math.sqrt(max(0.0, radius * radius - (radius - h) ** 2))
            n = max(24, math.ceil(2 * math.pi * rho / RIM_SPACING))
            for i in range(n):
                a = i / n * math.pi * 2
                pts.append((math.cos(a) * rho, -math.sin(a) * rho, h))
        rim = tuple(np.array(c) for c in zip(*pts))

    def tip(x, y):
        k = f'{x:.8f},{y:.8f}'
        hit = cache.get(k)
        if hit is not None:
            return hit
        if many is not None:
            values = many(x + kx, y + ky)
            if not np.isfinite(values).all() or values.min() < .001 or values.max() > stock_height + 1e-7:
                raise ValueError('Relief heights must be finite and lie 1 mm or more above the bed, within stock height')
            best = float((values - kb).max())
        else:
            best, at = -math.inf, 0
            for i, (dx, dy, ball) in enumerate(kernel):
                value = height(x + dx, y + dy)
                if value - ball > best:
                    best, at = value - ball, i
            ring_at[k] = int(ring_of[at])            # where the highest point lies (lift_over_steps reads its rim)
        cache[k] = best
        return best

    def height(x, y):
        """a height function's value, checked as the planner checks every reading"""
        value = target(x, y)
        if not (isinstance(value, (int, float, np.floating)) and math.isfinite(value)) or value < .001 \
                or value > stock_height + 1e-7:
            raise ValueError('Relief heights must be finite and lie 1 mm or more above the bed, within stock height')
        return value

    def checked(values):
        if not np.isfinite(values).all() or values.min() < .001 or values.max() > stock_height + 1e-7:
            raise ValueError('Relief heights must be finite and lie 1 mm or more above the bed, within stock height')
        return values

    ring_at, rim_cache = {}, {}

    def rim_reading(x, y):
        """a height function read again over the fine rim (lift_over_steps), point by point"""
        k = f'{x:.8f},{y:.8f}'
        hit = rim_cache.get(k)
        if hit is None:
            hit = max(height(x + dx, y + dy) - h for dx, dy, h in zip(*rim))
            rim_cache[k] = hit
        return hit

    def on_outer_rings(x, y):
        """a height function's tip at (x, y) has its highest kernel point on the ball's outer rings"""
        tip(x, y)
        return ring_at[f'{x:.8f},{y:.8f}'] >= 5

    def tips_at(xs, y, near=()):
        """tip at several x on one row (lift_over_steps): for a sampled heightfield one numpy call over every kernel
        point, the same values as tip(); where a tip's highest kernel point lies on the ball's outer rings (a steep
        wall within reach), the fine rim's reading too. A height function's rim is read point by point, and also
        where a neighbouring sample's highest point (the x in `near`) lies on its outer rings: a function's wall can
        have no width, so a corner can reach into the ball between the kernel's points with no point of it reading
        the wall, where the sample beside it does"""
        if many is None:
            out = []
            for x in xs:
                best = tip(x, y)
                if rim is not None and (on_outer_rings(x, y) or any(on_outer_rings(n, y) for n in near)):
                    best = max(best, rim_reading(x, y))
                out.append(best)
            return out
        xs = np.asarray(xs, dtype=np.float64)
        X = xs[:, None] + kx[None, :]
        d = checked(many(X, y + ky[None, :] + 0.0 * X)) - kb[None, :]
        best = d.max(axis=1)
        if rim is not None:
            outer = ring_of[d.argmax(axis=1)] >= 5
            if outer.any():
                Xr = xs[outer][:, None] + rim[0][None, :]
                fine = checked(many(Xr, y + rim[1][None, :] + 0.0 * Xr)) - rim[2][None, :]
                best[outer] = np.maximum(best[outer], fine.max(axis=1))
        return best.tolist()

    # lift_over_steps (this edition's option; off = the WebGPU planner exactly): the planner moves straight between
    # tips sampled sample_step apart, and beside a wall taller than the leave the needed tip climbs steeply between two
    # samples, so the straight move cuts into the wall (up to the wall's height). With the option on, every move is
    # checked between its ends (a quarter of a heightfield cell apart, or RIM_SPACING apart for a height function);
    # where the needed height rises more than the pass's leave above the straight move, the tool lifts to the highest
    # of them before the move and stays there across it, leaving material at the wall's foot instead of a gouge in
    # it; and a tip whose ball rides a wall on its outer rings is read again with the fine rim. A program whose moves
    # all pass the check and whose ball never rides its outer rings (a smooth relief, sample_relief) is unchanged.
    cell = getattr(target, 'cell', None)
    n_sub = max(4, math.ceil(sample_step / (cell / 4) if (many is not None and cell) else sample_step / RIM_SPACING))
    subs = [k / n_sub for k in range(1, n_sub)]

    nx = math.ceil(width / sample_step)

    def x_at(i):
        return -width / 2 + width * i / nx

    minimum = stock_height
    nz_probe = math.ceil(depth / sample_step)
    for j in range(nz_probe + 1):
        for i in range(nx + 1):
            minimum = min(minimum, tip(x_at(i), depth / 2 - depth * j / nz_probe))
    flute = o.get('flute_length') if o.get('flute_length') is not None else .018
    if stock_height - minimum > flute:
        raise ValueError("Relief depth exceeds the visible tool's flute length")
    points = [{'position': (0.0, 0.0, stock_height + clearance), 'type': 'rapid'}]
    stages = []
    dist = [0.0]

    def add(position, typ='cut', feed=None):
        last = points[-1]['position']
        dist[0] += math.sqrt(sum((position[i] - last[i]) ** 2 for i in range(3)))
        p = {'position': position, 'type': typ}
        if feed:
            p['feed'] = feed
        points.append(p)

    def raster(name, level, spacing, leave):
        start_distance, start_index = dist[0], len(points)
        nz = math.ceil(depth / spacing)
        for j in range(nz + 1):
            y = depth / 2 - depth * j / nz
            reverse = j % 2 == 1
            first_x = x_at(nx if reverse else 0)
            prev = points[-1]['position']
            add((prev[0], prev[1], stock_height + clearance), 'rapid')
            add((first_x, y, stock_height + clearance), 'rapid')
            for k in range(nx + 1):
                i = nx - k if reverse else k
                x = x_at(i)
                z = max(level, tip(x, y) + leave)
                if rim is not None:                     # the rim's reading where the ball rides a wall:
                    near = [x_at(c) for c in (i - 1, i + 1) if 0 <= c <= nx]
                    fine = tips_at([x], y, near)[0]     # only past the leave does the coarse reading gouge
                    if fine > z:
                        z = max(level, fine + leave)
                if lift and k > 0:
                    px, _, pz = points[-1]['position']
                    need = [max(level, t + leave) for t in tips_at([px + (x - px) * f for f in subs], y, (px, x))]
                    if max(nd - (pz + (z - pz) * f) for nd, f in zip(need, subs)) > leave:
                        m = max(pz, z, *need)
                        if pz < m:
                            add((px, y, m), 'cut', o.get('feed'))
                        if z < m:
                            add((x, y, m), 'cut', o.get('feed'))
                add((x, y, z), 'cut', (o.get('plunge') if o.get('plunge') is not None else .003) if k == 0 else o.get('feed'))
        stages.append({'name': name, 'start_distance': start_distance, 'end_distance': dist[0],
                       'start_index': start_index, 'end_index': len(points) - 1})

    level, npass = stock_height, 0
    while level > minimum + allowance + 1e-7:
        level = max(minimum + allowance, level - stepdown)
        npass += 1
        raster(f'rough {npass}', level, rough_stepover, allowance)
        if npass > 100:
            raise ValueError('Relief roughing exceeds 100 passes; check units and stepdown')
    raster('finish', -math.inf, stepover, tolerance)
    last = points[-1]['position']
    add((last[0], last[1], stock_height + clearance), 'rapid')
    return {'points': points, 'stages': stages, 'cutter': 'ball', 'radius': radius, 'width': width, 'depth': depth,
            'stock_width': stock_width, 'stock_depth': stock_depth, 'stock_height': stock_height, 'stepover': stepover,
            'sample_step': sample_step, 'surface_tolerance': tolerance, 'rough_allowance': allowance,
            'sampling': SAMPLING, 'target': target}


def sample_relief(x, y):
    """The original Eidoverse relief (three's sampleRelief(x, z) with z = -y): an asymmetric flowing crest on a
    recessed land."""
    u, v = x / .03, -y / .05
    crest = math.exp(-((u + .26 * math.sin(v * 4)) ** 2 * 4 + v * v * 1.5))
    pool = math.exp(-((u - .45) ** 2 * 14 + (v + .38) ** 2 * 18))
    return .006 + .010 * crest - .0013 * pool
