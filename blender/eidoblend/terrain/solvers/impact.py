"""Impact craters for the new make_terrain (design section 4.8): the analytic crater stamp, wave 1.

    crater_dimensions(D, gravity)   Pike 1977's morphometry (as quoted by Holsapple 2022): simple craters depth 0.2 D
                                    and rim height 0.036 D; complex craters depth 1.044 D^0.301 km, rim 0.236 D^0.399
                                    km, floor 0.187 D^1.249 km, all on the Moon, with the simple-to-complex
                                    transition (10.6 km there, where the two depth fits meet) scaled by 1/g and every
                                    length scaled with it, so Earth's transition is about 1.75 km
    impact_crater(x, y, ...)        the crater as a height change over the pre-impact surface, in world metres:
                                    a parabolic bowl, flat where infilled; the rim crest a rounded peak; ejecta
                                    thickness h_rim (r/R)^-3 out to 2-3 R with hummocks, blocks and faint rays; a
                                    polygonal planform (joint sets: Meteor Crater is nearly square); rim height varying
                                    with azimuth. Complex craters add a flat floor, slumped terraces as irregular arcs
                                    and a central peak cluster.

The structure (lobate rim, flat floor, central peak) is Ekigar's impactCrater's, rebuilt in metres with Pike's
numbers (design section 3). Reference preset: METEOR_CRATER, measured from the meteor_crater DEM.

Stage op: OPS = {'impact_crater': op_impact_crater} (the op contract is volcanic.py's).

Later (second half): aging by creep (kappa t), wall gullies by the fluvial stage with the crater as a closed basin,
the floor filled flat by the hydro stage; talus on the hero levels.

numpy only.
"""
import math

import numpy as np

from .volcanic import (AZ_TABLE_ANGLES, TAU, _layered_face, _prepass, _pull_band, _stamp_key, azimuth_noise,
                       azimuth_sampler, crest_union, fbm, gradient_noise, polar, smooth_max, smoothstep, stamp_add,
                       support_slices)

G_EARTH = 9.81
G_MOON = 1.62
MOON_TRANSITION_M = 10600.0        # Pike 1977: where the simple (0.2 D) and complex (1.044 D^0.301) depth fits meet
_BIG = 1.0e9


def crater_dimensions(diameter_m, gravity=G_EARTH, depth_ratio=0.2, rim_ratio=0.036):
    """Pike's numbers for a fresh crater of diameter D (rim crest to rim crest), metres:
    dict(kind 'simple' | 'complex', depth_m (rim crest to floor), rim_m (rim crest above the surroundings),
    floor_diameter_m (0 for a simple bowl), transition_m (the simple-to-complex diameter at this gravity)).

    Complex craters use the lunar fits at the lunar-equivalent diameter D g / g_moon, scaled back by g_moon / g, so
    the depth is continuous at the transition and the Moon gets Pike's fits exactly."""
    D = float(diameter_m)
    s = G_MOON / float(gravity)
    Dt = MOON_TRANSITION_M * s
    if D < Dt:
        return dict(kind='simple', depth_m=float(depth_ratio) * D, rim_m=float(rim_ratio) * D, floor_diameter_m=0.0,
                    transition_m=Dt)
    Dm = D / s / 1000.0                                   # the lunar-equivalent diameter, km
    return dict(kind='complex', depth_m=1044.0 * Dm ** 0.301 * s, rim_m=236.0 * Dm ** 0.399 * s,
                floor_diameter_m=187.0 * Dm ** 1.249 * s, transition_m=Dt)


def polygon_factor(az, sides, strength, azimuth_deg=0.0, roundness=0.08):
    """A rounded regular polygon's radius as a factor of azimuth (radians, or an AzimuthSampler), mean 1: `sides`
    straight sides (joint sets), the first side's outward normal at azimuth_deg, corners rounded by a soft maximum
    (roundness, in units of the side normals' cosine), blended with the circle by strength (0 a circle, 1 the full
    polygon)."""
    sampler = azimuth_sampler(az)
    if sides < 3 or strength <= 0.0:
        return np.ones_like(sampler.f)
    t = AZ_TABLE_ANGLES
    normals = math.radians(azimuth_deg) + TAU * np.arange(int(sides)) / int(sides)
    c = np.cos(t[:, None] - normals[None, :])
    beta = 1.0 / max(float(roundness), 1e-3)
    m = c.max(axis=1) + np.log(np.sum(np.exp(beta * (c - c.max(axis=1, keepdims=True))), axis=1)) / beta
    p = 1.0 / m                                           # the polygon's radius (side normals at distance 1)
    p /= p[:-1].mean()
    return sampler(1.0 + float(strength) * (p - 1.0))


def impact_crater(x, y, centre=(0.0, 0.0), diameter_m=1200.0, gravity=G_EARTH, depth_ratio=0.2, rim_ratio=0.036,
                  fill_ratio=None, fill_round=0.25, sides=4, polygon=0.45, polygon_azimuth_deg=0.0, radius_noise=0.02,
                  edge_noise=0.01, rim_noise=0.2, crest_round=0.35, ejecta_reach=2.4, ejecta_exponent=3.0,
                  hummocks=0.05, hummock_scale=0.10, blocks=0.02, rays=0.04, peak_height_frac=0.4,
                  peak_width_frac=0.2, terraces=4, cliffs=None, seed=0):
    """An impact crater as a height change (metres) over the pre-impact surface at world points (x, y).

    cliffs           an infilled simple crater only: None keeps the parabolic wall; a dict makes the wall above the
                     fill the layered face of the target's beds (volcanic.wall_column: strong_deg, strong_frac,
                     layer_m, sectors; talus_frac of the wall height a talus apron at talus_deg at its foot), its
                     mean slope the parabola's from the floor's edge to the rim: Meteor Crater's Kaibab and Coconino
                     cliffs over its talus. The result then carries `strength` (the threshold tangent the wall was
                     built at; NaN off it).

    diameter_m       D, rim crest to rim crest (the polygon's mean); gravity sets the simple/complex transition
    depth_ratio      a simple crater's fresh depth, rim crest to the bowl's bottom (Pike: 0.2 D)
    rim_ratio        a simple crater's rim crest above the surroundings (Pike: 0.036 D fresh)
    fill_ratio       rim crest to an infilled flat floor, as a fraction of D (Meteor Crater 0.14); None: no fill
    fill_round       the floor's fillet into the walls (the fans at the wall foot), as a fraction of the bowl
                     depth below the fill
    sides, polygon   the planform: a rounded `sides`-gon (4-6 from joint sets), blended in by polygon (0 a circle);
                     polygon_azimuth_deg the first side's outward normal; radius_noise outline noise (unit RMS x,
                     harmonics 1-6), edge_noise the small bends and spurs of the rim (harmonics 8-40)
    rim_noise        the rim height varying with azimuth (unit-RMS harmonics 1-4, times this)
    crest_round      the rim crest's rounding, as a fraction of the rim height
    ejecta_reach     the blanket's edge in crater radii (2-3), thickness h_rim (r/R)^-ejecta_exponent tapering to 0
    hummocks         hummock relief as a fraction of the local ejecta thickness, at hummock_scale D (0.05 at 0.1 D
                     puts Meteor Crater's blanket at its real slope p90, 9 degrees; the smooth blanket gives 7)
    blocks           sparse blocks as a fraction of the rim height, densest at the rim, thinning as the ejecta does
    rays             faint rays: the ejecta thickness modulated by a narrow-streak azimuth pattern; a fresh crater on
                     an airless body (0.05-0.15); Earth's weather removes them, so Meteor Crater has none
    peak_*, terraces complex craters only: the central peak's height (fraction of the depth) and base width
                     (fraction of D); the number of slumped terrace arcs on the wall

    Returns dict(delta, ejecta (the loose blanket's thickness), fill (the floor infill's thickness), kind, dims).
    Everything is zero beyond the ejecta's reach, so only the square covering it is evaluated."""
    args = dict(centre=centre, diameter_m=diameter_m, gravity=gravity, depth_ratio=depth_ratio, rim_ratio=rim_ratio,
                fill_ratio=fill_ratio, fill_round=fill_round, sides=sides, polygon=polygon,
                polygon_azimuth_deg=polygon_azimuth_deg, radius_noise=radius_noise, edge_noise=edge_noise,
                rim_noise=rim_noise, crest_round=crest_round, ejecta_reach=ejecta_reach,
                ejecta_exponent=ejecta_exponent, hummocks=hummocks, hummock_scale=hummock_scale, blocks=blocks,
                rays=rays, peak_height_frac=peak_height_frac, peak_width_frac=peak_width_frac, terraces=terraces,
                cliffs=cliffs, seed=seed)
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    shape = np.broadcast(x, y).shape
    xb, yb = np.broadcast_to(x, shape), np.broadcast_to(y, shape)
    reach = 0.5 * float(diameter_m) * max(float(ejecta_reach), 1.6) * (1.0 + float(polygon) * 0.6
                                                                         + 4.0 * float(radius_noise)
                                                                         + 4.0 * float(edge_noise)) * 1.05
    keys = ('delta', 'ejecta', 'fill') + (('strength',) if cliffs else ())
    out = {k: np.zeros(shape) for k in keys}
    if cliffs:
        out['strength'][:] = np.nan
    meta = {}

    def core(xs, ys):
        res = _impact_crater_core(xs, ys, **args)
        meta.update(kind=res['kind'], dims=res['dims'])
        return res

    sl = support_slices(xb, yb, centre, reach)
    if sl is not None:
        if sl[0].stop > sl[0].start and sl[1].stop > sl[1].start:
            res = core(xb[sl], yb[sl])
            for k in out:
                out[k][sl] = res[k]
    else:
        near = (np.abs(xb - centre[0]) < reach) & (np.abs(yb - centre[1]) < reach)
        if near.any():
            res = core(xb[near], yb[near])
            for k in out:
                out[k][near] = res[k]
    if not meta:
        meta.update(kind=crater_dimensions(diameter_m, gravity, depth_ratio, rim_ratio)['kind'],
                    dims=crater_dimensions(diameter_m, gravity, depth_ratio, rim_ratio))
    out.update(meta)
    return out


def _impact_crater_core(x, y, centre, diameter_m, gravity, depth_ratio, rim_ratio, fill_ratio, fill_round, sides,
                        polygon, polygon_azimuth_deg, radius_noise, edge_noise, rim_noise, crest_round, ejecta_reach,
                        ejecta_exponent, hummocks, hummock_scale, blocks, rays, peak_height_frac, peak_width_frac,
                        terraces, cliffs, seed):
    dims = crater_dimensions(diameter_m, gravity, depth_ratio, rim_ratio)
    D = float(diameter_m)
    R = 0.5 * D
    d, hm = dims['depth_m'], dims['rim_m']
    r, az_rad = polar(x, y, centre)
    az = azimuth_sampler(az_rad)                               # one table index for every azimuth table below
    plan = polygon_factor(az, sides, polygon, polygon_azimuth_deg)
    if radius_noise:
        plan = plan * (1.0 + float(radius_noise) * azimuth_noise(az, seed, 61, 1, 6))
    if edge_noise:
        plan = plan * (1.0 + float(edge_noise) * azimuth_noise(az, seed, 64, 8, 40, decay=1.0))
    rho = r / (R * plan)
    hr = hm * (1.0 + float(rim_noise) * azimuth_noise(az, seed, 62, 1, 4)) if rim_noise else hm + 0.0 * r
    rim_ramp = hm + (hr - hm) * np.minimum(rho, 1.6) ** 2      # the rim height brought to its mean at the centre

    strength = None
    if dims['kind'] == 'simple':
        inner = rim_ramp - d * (1.0 - rho * rho)              # the parabolic bowl: rim crest at rho = 1
        if cliffs and fill_ratio is not None:
            inner, strength = _layered_wall(rho, az_rad, R * plan, rim_ramp, hm, d, D, float(fill_ratio),
                                            dict(cliffs), seed)
    else:
        inner = _complex_interior(rho, az_rad, rim_ramp, hm - d, dims['floor_diameter_m'] / D, terraces, seed)
    inner = np.where(rho < 1.6, inner, _BIG)

    n = float(ejecta_exponent)
    taper = 1.0 - smoothstep(0.62 * ejecta_reach, ejecta_reach, rho)
    rc = np.maximum(rho, 0.35)
    fall = 1.0 / (rc * rc * rc) if n == 3.0 else rc ** -n
    blanket = hr * fall * taper                               # rises steeply inside the rim (the union's other side)
    if rays:
        streak = np.maximum(azimuth_noise(az, seed, 63, 12, 56, decay=0.6), 0.0) ** 2
        blanket = blanket * (1.0 + float(rays) * (streak - 0.5) * smoothstep(1.05, 1.7, rho))
    delta = crest_union(inner, blanket, float(crest_round) * hm)

    fill = np.zeros_like(delta)
    if fill_ratio is not None:
        z_fill = hm - float(fill_ratio) * D
        if z_fill <= hm - d:
            raise ValueError(f'impact crater: fill_ratio {fill_ratio} puts the fill below the bowl ({d / D:.3f} D)')
        filled = smooth_max(delta, z_fill, max(float(fill_round), 1e-3) * (z_fill - (hm - d)))
        fill = np.where(rho < 1.0, np.maximum(filled - delta, 0.0), 0.0)
        delta = np.where(rho < 1.0, filled, delta)

    # the ejecta blanket's own relief: hummocks scaled by the local thickness, blocks densest at the rim
    outside = smoothstep(0.92, 1.02, rho)
    thick = np.where(rho > 0.9, np.minimum(blanket, 1.2 * hr), 0.0) * outside
    if hummocks:
        delta = delta + float(hummocks) * thick * fbm(x, y, float(hummock_scale) * D, seed + 71, octaves=2)
    if blocks:                                   # sparse: only the gradient noise's top few percent rise as lumps
        lump = smoothstep(0.36, 0.6, gradient_noise(x, y, 0.012 * D, seed + 73))
        lump = lump + 0.6 * smoothstep(0.4, 0.62, gradient_noise(x, y, 0.006 * D, seed + 79))
        ro = np.maximum(rho, 1.0)
        delta = delta + float(blocks) * hm * lump * smoothstep(0.85, 0.98, rho) * taper / (ro * ro * ro)
    if dims['kind'] == 'complex':
        delta = delta + _central_peak(x, y, centre, D, d, peak_height_frac, peak_width_frac, seed)
    # about half the rim's height is the uplifted target rock, the rest ejecta; beyond 1.3 R it is all ejecta
    ejecta = np.clip(thick * (0.5 + 0.5 * smoothstep(1.0, 1.3, rho)), 0.0, None)
    out = dict(delta=delta, ejecta=ejecta, fill=fill, kind=dims['kind'], dims=dims)
    if cliffs:
        out['strength'] = (np.where((fill <= 0.0) & (rho < 1.0), strength, np.nan) if strength is not None
                           else np.full_like(delta, np.nan))
    return out


def _layered_wall(rho, az, Rp, rim_ramp, hm, d, D, fill_ratio, spec, seed):
    """An infilled simple crater's wall as the layered face of its target (impact_crater's cliffs): from the floor's
    edge (where the parabolic bowl meets the fill) to the rim crest, a talus apron (talus_frac of the height at
    talus_deg) under the beds of volcanic.wall_column, whose mean slope is the rest of the parabola's rise. Rp is
    the planform's radius at each point (R x the polygon and noise factors). Returns (inner surface, threshold
    tangent of the face)."""
    from .volcanic import smooth_max as _smax
    z_fill = hm - fill_ratio * D
    rf = math.sqrt(max(1.0 - fill_ratio * D / d, 0.05))
    Hw = hm - z_fill
    run = (1.0 - rf) * 0.5 * D
    t_deg = float(spec.pop('talus_deg', 32.0))
    th = float(spec.pop('talus_frac', 0.3)) * Hw
    run_t = th / math.tan(math.radians(t_deg))
    rock_deg = math.degrees(math.atan((Hw - th) / max(run - run_t, 1e-6)))
    u = (rho - rf) * Rp                                       # metres outward from the floor's edge
    face, s = _layered_face(u - run_t, az, Hw - th, rock_deg, spec, seed)
    rock = z_fill + th + face
    talus = z_fill + math.tan(math.radians(t_deg)) * u
    wall = _smax(talus, rock, 0.02 * Hw)
    wall = wall + (rim_ramp - hm) * np.clip((rho - rf) / (1.0 - rf), 0.0, 1.0)     # the rim's height round the ring
    return wall, np.where(u > run_t, s, np.tan(math.radians(t_deg)) * 1.1)


def _complex_interior(rho, az, rim_ramp, floor_z, floor_frac, terraces, seed):
    """A complex crater's inside: a flat floor out to floor_frac (of the radius), then a concave wall rising to the
    rim, with `terraces` slumped benches, each an arc of its own span and radius (not a ring)."""
    rf = float(np.clip(floor_frac, 0.05, 0.85))
    s = np.clip((rho - rf) / (1.0 - rf), 0.0, None)
    wall = lambda q: floor_z + (rim_ramp - floor_z) * np.minimum(q, 1.6) ** 1.8   # noqa: E731
    z = wall(s)
    rng = np.random.default_rng([abs(int(seed)), 65])
    for _ in range(int(terraces)):
        q0 = rng.uniform(0.3, 0.85)                  # the bench's place on the wall, 0 floor .. 1 rim
        half = rng.uniform(0.07, 0.12)               # its radial half-width, wall fractions
        a0, span = rng.uniform(0.0, TAU), math.radians(rng.uniform(50.0, 140.0))
        off = np.mod(az - a0 + math.pi, TAU) - math.pi
        arc = smoothstep(0.5 * span, 0.35 * span, np.abs(off))           # the arc's angular window, soft ends
        band = 0.5 * (1.0 + np.cos(np.clip((s - q0) / half, -1.0, 1.0) * math.pi))
        z = z + arc * band * (wall(np.full_like(s, q0)) - z)            # pull the wall toward the bench level
    return np.where(rho < rf, floor_z, z)


def _central_peak(x, y, centre, D, depth, height_frac, width_frac, seed):
    """A central peak cluster: a main summit and 2-4 lesser ones within its base, each a rounded cone whose radius
    wanders with azimuth, combined by maximum."""
    rng = np.random.default_rng([abs(int(seed)), 67])
    base = 0.5 * float(width_frac) * D
    top = float(height_frac) * depth
    out = 0.0
    for k in range(1 + int(rng.integers(2, 5))):
        if k == 0:
            cx, cy, h, rad = centre[0], centre[1], top, base
        else:
            a, dist = rng.uniform(0.0, TAU), rng.uniform(0.25, 0.6) * base
            cx, cy = centre[0] + dist * math.sin(a), centre[1] + dist * math.cos(a)
            h, rad = top * rng.uniform(0.45, 0.8), base * rng.uniform(0.4, 0.65)
        rr, aa = polar(x, y, (cx, cy))
        wob = 1.0 + 0.18 * azimuth_noise(aa, seed + k, 68, 2, 7)
        q = np.clip(1.0 - rr / (rad * wob), 0.0, 1.0)
        out = np.maximum(out, h * q ** 1.6 * (3.0 - 2.0 * q))      # 1 at the summit, a soft toe at the base
    return out


# ====================================================================== reference preset (measured)

METEOR_CRATER = dict(
    # meteor_crater (3DEP at 3 m): the rim crest 1194 m across on average (517-662 m in radius), 52 m above the
    # plain on average (0.0437 D; 36-68 m), the rim to the infilled floor 170 m (0.1426 D); the median profile along
    # radius normalised by the rim follows the 0.2 D parabola from rho 0.6 to 0.8 and the ejecta (r/R)^-3 to 1.4 R,
    # thinning to nothing by about 2.3 R; the outline's 4-fold harmonic is 5.3 % of the radius, its corners near
    # compass 30/120/210/300 degrees (sides facing 75/165/255/345).
    centre=(30.0, 0.0), diameter_m=1194.0, depth_ratio=0.2, rim_ratio=0.0437, fill_ratio=0.1426, sides=4,
    polygon=0.42, polygon_azimuth_deg=75.0, radius_noise=0.035, rim_noise=0.2, crest_round=0.35, ejecta_reach=2.3,
    rays=0.0, seed=11,
)


# ====================================================================== stage op

def op_impact_crater(fields, level, params, seed, ctx=None):
    """Stage op 'impact_crater': params are impact_crater's (plus supersample). Adds the crater to h once
    (volcanic.stamp_add: whole on the first level, only the finer detail below, so it can run on every level from the
    one that resolves D); bed takes the excavation and the rim's uplift (all but the loose ejecta and the floor's
    fill); the fill is recorded as deposit. With cliffs, Sc takes the strength the wall was built at (tan 38
    degrees off the wall) for the threshold, talus and aging stages. Skips the coarsest level's pre-passes (the
    ground grows first) and pins a child level's border band."""
    if _prepass(ctx):
        return fields
    p = dict(params)
    s = int(p.pop('supersample', 1))
    p.setdefault('seed', seed)
    here = []

    def evaluate(x, y):
        out = impact_crater(x, y, **p)
        if not here:
            here.append(out.get('strength'))
        return {'h': out['delta'], 'bed': out['delta'] - out['ejecta'] - out['fill'], 'deposit': out['fill']}
    stamp_add(fields, level, _stamp_key('impact_crater', dict(params, seed=p['seed'])), evaluate, s)
    if here and here[0] is not None:
        st = here[0]
        if s > 1:
            n = st.shape[0] // s
            st = np.nanmax(st.reshape(n, s, n, s), axis=(1, 3)) if np.isfinite(st).any() else st[::s, ::s]
        fields['Sc'] = np.where(np.isfinite(st), np.maximum(st, math.tan(math.radians(30.0))),
                                math.tan(math.radians(38.0))).astype(np.float32)
    _pull_band(fields, ctx)
    return fields


op_impact_crater.evolves = True          # called on every pass of the coarsest level; the stamp skips the pre-passes
OPS = {'impact_crater': op_impact_crater}
