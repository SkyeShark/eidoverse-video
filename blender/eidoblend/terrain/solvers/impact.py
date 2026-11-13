"""Impact craters for the new make_terrain (design section 4.8): the analytic crater stamp, wave 1.

    crater_dimensions(D, gravity)   Pike 1977's morphometry (as quoted by Holsapple 2022): simple craters depth 0.2 D
                                    and rim height 0.036 D; complex craters depth 1.044 D^0.301 km, rim 0.236 D^0.399
                                    km, floor 0.187 D^1.249 km, all on the Moon, with the simple-to-complex
                                    transition (10.6 km there, where the two depth fits meet) scaled by 1/g and every
                                    length scaled with it, so Earth's transition is about 1.75 km
    impact_crater(x, y, ...)        the crater as a height change over the pre-impact surface, in world metres:
                                    a parabolic bowl, flat where infilled, or (with cliffs) the infill a concave
                                    debris apron rising from the floor's near-level centre to the foot of the target's
                                    bedded face (Meteor Crater's: _apron_wall), its talus and fill recorded; the rim
                                    crest a rounded peak; ejecta thickness h_rim (r/R)^-3 out to 2-3 R with hummocks,
                                    blocks and faint rays; a polygonal planform (joint sets: Meteor Crater is nearly
                                    square); rim height varying with azimuth. Complex craters add a flat floor, slumped
                                    terraces as irregular arcs and a central peak cluster.
    boulders(x, y, ...)             blocks lying on the ground on a hashed lattice (a function of world position)

The structure (lobate rim, flat floor, central peak) is Ekigar's impactCrater's, rebuilt in metres with Pike's
numbers (design section 3). Reference preset: METEOR_CRATER, measured from the meteor_crater DEM.

Stage ops: OPS = {'impact_crater': op_impact_crater, 'crater_blocks': op_crater_blocks} (the op contract is
volcanic.py's). The aging (gullies, fans, the rim rounded) is volcanic.py's volcano_age with the crater a closed
basin; talus at repose and the fallen blocks run on the hero levels.

numpy only.
"""
import math

import numpy as np

from .volcanic import (AZ_TABLE_ANGLES, TAU, _layered_face, _prepass, _pull_band, _stamp_key, azimuth_noise,
                       azimuth_sampler, crest_union, fbm, gradient_noise, level_window, polar, smooth_max, smoothstep,
                       stamp_add, support_slices)

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
    keys = ('delta', 'ejecta', 'fill', 'talus') + (('strength',) if cliffs else ())
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
    # the debris apron's outline: the broad shape with a quarter of the polygon (talus and fans round the corners
    # inward; on the full square its smooth contours turned most of the crater's slopes to the four side normals, a
    # 4-fold aspect signal of 0.2 to the judge, the square reference's 0.12; at a half, once the aging left the lower
    # apron unchannelled, the apron alone carried a 4-fold signal of 0.19 against 0.07 when gullied)
    plan_low = 1.0 + 0.25 * (plan - 1.0)
    if radius_noise:
        rn_f = 1.0 + float(radius_noise) * azimuth_noise(az, seed, 61, 1, 6)
        plan = plan * rn_f
        plan_low = plan_low * rn_f
    if edge_noise:
        plan = plan * (1.0 + float(edge_noise) * azimuth_noise(az, seed, 64, 8, 40, decay=1.0))
    rho = r / (R * plan)
    hr = hm * (1.0 + float(rim_noise) * azimuth_noise(az, seed, 62, 1, 4)) if rim_noise else hm + 0.0 * r
    rim_ramp = hm + (hr - hm) * np.minimum(rho, 1.6) ** 2      # the rim height brought to its mean at the centre

    strength = None
    apron = None
    # the inside (bowl, apron, face) only where it can win the union with the blanket, inside 1.6 R: evaluated over
    # the whole square it cost 2-3 times as much on a main level (a 3 km tile round a 1.2 km crater)
    near = rho < 1.6
    every = bool(near.all())

    def pick(a):
        return a if every else a[near]

    def scatter(v, fill_value):
        if every:
            return np.asarray(v, np.float64)
        full = np.full(rho.shape, fill_value)
        full[near] = v
        return full
    inner = np.full(rho.shape, _BIG)
    if near.any():
        rho_n, rr_n = pick(rho), pick(rim_ramp)
        if dims['kind'] == 'simple':
            inn = rr_n - d * (1.0 - rho_n * rho_n)              # the parabolic bowl: rim crest at rho = 1
            if cliffs and fill_ratio is not None:
                ap = _apron_wall(pick(x), pick(y), rho_n, pick(az_rad), R * pick(plan), R * pick(plan_low), rr_n, hm,
                                 d, D, float(fill_ratio), dict(cliffs), seed)
                inn = ap['surface']
                apron = dict(strength=scatter(ap['strength'], np.nan), rock=scatter(ap['rock'], 0.0),
                             coarse=scatter(ap['coarse'], 0.0))
                strength = apron['strength']
        else:
            inn = _complex_interior(rho_n, pick(az_rad), rr_n, hm - d, dims['floor_diameter_m'] / D, terraces, seed)
        inner = scatter(inn, _BIG)

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
    talus = np.zeros_like(delta)
    if apron is not None:
        # the apron is the infill: what lies above the buried rock (the fresh bowl, the face continued down) is loose,
        # coarse talus under the face grading to the floor's fine sediment (lake beds and fan silts) further in
        inside = (rho < 1.0) & (delta <= inner + 1e-6)
        loose = np.where(inside, np.maximum(delta - apron['rock'], 0.0), 0.0)
        talus = loose * apron['coarse']
        fill = loose - talus
    elif fill_ratio is not None:
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
    out = dict(delta=delta, ejecta=ejecta, fill=fill, talus=talus, kind=dims['kind'], dims=dims)
    if cliffs:
        if apron is not None:
            out['strength'] = np.where(rho < 1.0, strength, np.nan)
        else:
            out['strength'] = (np.where((fill <= 0.0) & (rho < 1.0), strength, np.nan) if strength is not None
                               else np.full_like(delta, np.nan))
    return out


def _apron_wall(x, y, rho, az, Rp, Rp_low, rim_ramp, hm, d, D, fill_ratio, spec, seed):
    """An infilled simple crater's inside (impact_crater's cliffs), as Meteor Crater's: a concave debris apron from
    the floor's centre (fill_ratio D under the mean rim crest) rising as a power law (r / r_t)^p to meet, at the
    talus angle, the foot of the rock face; the face the target's beds (volcanic.wall_column: strong ledges standing
    as cliffs over weaker beds) at face_deg mean up to the rim crest. The exponent p = tan(talus) r_t / (apron
    height), so the apron is talus at repose under the face, fans further out and near-level lake beds at the
    centre (the reference's ring medians: 2 m up at 120 m out, 17 m at 310 m, 50 m at 410 m, the face's foot about
    65 m under the crest). The apron's top rises and falls round the ring (debris cones under the chutes, the beds
    exposed further down between them, azimuth noise harmonics 5-40 of apron_vary), and the floor carries low mounds
    (mounds_m of world noise at 0.08 D, fading out up the apron). Rp is the planform's radius at each point (R x the
    polygon and noise factors), which the face follows; Rp_low its broad shape (the polygon and the low harmonics),
    which the apron follows (a debris apron smooths the rim's small points and coves: following them, its contours
    swung round every one of them and the bowl read as a sunburst of radial ribs).

    Returns dict(surface, strength (the threshold tangent: the face's beds, 1.1 tan(talus) on the apron), rock (the
    buried rock under the apron: the fresh bowl, or the face continued down where that is higher), coarse (0..1:
    the share of the loose apron that is talus, under the face, rather than the floor's fine sediment))."""
    from .volcanic import smooth_max as _smax
    t_deg = float(spec.pop('talus_deg', 33.0))
    tf = float(spec.pop('talus_frac', 0.6))
    face_deg = float(spec.pop('face_deg', 52.0))
    vary = float(spec.pop('apron_vary', 0.12))
    mounds = float(spec.pop('mounds_m', 0.0))
    z_c = hm - fill_ratio * D                             # the floor's centre, the lowest lake beds
    Hw = hm - z_c                                         # floor centre to the mean crest
    if not (0.05 < tf < 0.95):
        raise ValueError(f'impact crater: talus_frac {tf} must lie between 0.05 and 0.95 of the wall')
    z_t = z_c + tf * Hw                                   # the apron's mean top, the face's foot
    tt = math.tan(math.radians(t_deg))
    tw = math.tan(math.radians(face_deg))
    Hf = hm - z_t                                         # the face's height
    r = rho * Rp                                          # metres from the centre
    u_t = np.maximum(Rp - Hf / tw, 0.2 * Rp)              # the face's foot, metres from the centre
    u_a = np.maximum(Rp_low - Hf / tw, 0.2 * Rp_low)      # the apron's top on the broad outline
    p = np.maximum(tt * u_a / (z_t - z_c), 1.0)
    q = r / u_a
    apron = np.where(q < 1.0, z_c + (z_t - z_c) * np.power(np.clip(q, 0.0, 1.0), p), z_t + tt * (r - u_a))
    if vary:
        # debris cones under the chutes bury the face's foot higher, the beds run further down between them: only
        # the apron's top moves (varied all the way in, the apron's top printed radial ribs to the centre; from
        # halfway up, in harmonics 5-40, the cones stood round the bowl as broad regular flutes)
        dz = vary * tf * Hw * azimuth_noise(az, seed, 66, 8, 90, decay=0.4)
        apron = apron + dz * smoothstep(0.7, 1.0, q)
    if mounds:
        apron = apron + mounds * fbm(x, y, 0.08 * D, seed + 83, octaves=2) * (1.0 - smoothstep(0.3, 0.6, q))
    face, s = _layered_face(r - u_t, az, Hf, face_deg, spec, seed)
    rock_face = z_t + face
    wall = _smax(apron, rock_face, 0.012 * Hw)
    ramp = np.clip((r - u_t) * (tw / Hf), 0.0, 1.0)
    wall = wall + (rim_ramp - hm) * ramp                  # the rim's height round the ring
    bowl = rim_ramp - d * (1.0 - rho * rho)               # the fresh bowl under the fill (Pike's 0.2 D)
    rock = np.maximum(bowl, rock_face + (rim_ramp - hm) * ramp)
    strength = np.where(rock_face >= apron, s, 1.1 * tt)
    coarse = smoothstep(0.55, 0.85, q)
    return dict(surface=wall, strength=strength, rock=np.minimum(rock, wall), coarse=coarse)


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
    """Stage op 'impact_crater': params are impact_crater's (plus supersample, applied on the main level and any other
    level with cells of a metre or coarser that is not a context level: finer cells sample the shape's kinks exactly,
    and a context level is seen from afar). Adds the crater to h once
    (volcanic.stamp_add: whole on the first level, only the finer detail below, so it can run on every level from the
    one that resolves D); bed takes the excavation and the rim's uplift (all but the loose ejecta, the floor's
    fill and the talus under the walls); the fill is recorded as deposit and the talus apron as talus. With cliffs,
    Sc takes the strength the wall was built at (tan 38 degrees off the wall) for the threshold, talus and aging
    stages. Skips the coarsest level's pre-passes (the ground grows first) and pins a child level's border band."""
    if _prepass(ctx):
        return fields
    p = dict(params)
    s = int(p.pop('supersample', 1))
    if getattr(level, 'role', 'main') != 'main':
        # the main level's box filter is the judge's; a hero level's cells sample the kinks (its finer children
        # resolve them; supersampled, the first hero window of a floor camera, 1.5 km at 1.46 m, evaluated the
        # crater at 5.3 M points), and a context level is seen from afar
        s = 1
    p.setdefault('seed', seed)
    for k in ('talus', 'deposit'):
        if k not in fields:
            fields[k] = np.zeros(fields['h'].shape, np.float32)

    def evaluate(x, y):
        out = impact_crater(x, y, **p)
        res = {'h': out['delta'], 'bed': out['delta'] - out['ejecta'] - out['fill'] - out['talus'],
               'deposit': out['fill'], 'talus': out['talus']}
        if out.get('strength') is not None:
            res['strength'] = out['strength']          # evaluated and returned, not a field (the threshold below)
        return res
    here = stamp_add(fields, level, _stamp_key('impact_crater', dict(params, seed=p['seed'])), evaluate, s, ctx=ctx,
                     reduce={'strength': 'nanmax'})
    if here.get('strength') is not None:
        st = here['strength']
        fields['Sc'] = np.where(np.isfinite(st), np.maximum(st, math.tan(math.radians(30.0))),
                                math.tan(math.radians(38.0))).astype(np.float32)
    _pull_band(fields, ctx)
    return fields


op_impact_crater.evolves = True          # called on every pass of the coarsest level; the stamp skips the pre-passes


# ====================================================================== fallen blocks (the hero levels)

def _unit(h, k):
    """The k-th uniform number in [0, 1) from uint32 hashes h."""
    from .volcanic import _pcg
    return _pcg(h ^ np.uint32((0x9E3779B9 * (k + 1)) & 0xFFFFFFFF)).astype(np.float64) * (1.0 / 4294967296.0)


def boulders(x, y, density, spacing_m, size_m, seed, salt=0, exponent=2.5, height_frac=(0.3, 0.6), profile='slab'):
    """Blocks lying on the ground, as the height to add at world points (x, y): at most one per cell of a square
    lattice spacing_m apart, present with probability density(cx, cy) (0..1, a function of world position) at its
    jittered centre; its size (the long side) from a power law of that exponent between size_m (many small, few
    large); its plan a rounded rectangle (aspect 0.55-1) at a random angle; its profile a rounded slab height_frac
    of its size above the ground, its sides steep (profile 'mound': a soft Gaussian mound instead, the hummocks of
    sediment round desert shrubs). A function of world position and seed alone, so every level samples the same
    blocks. Returns metres (>= 0), shaped like x."""
    from .volcanic import _meshgrid_axes, lattice_hash
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    shape = np.broadcast(x, y).shape
    xb, yb = np.broadcast_to(x, shape), np.broadcast_to(y, shape)
    out = np.zeros(shape)
    if xb.size == 0:
        return out
    L = float(spacing_m)
    s0, s1 = (float(v) for v in size_m)
    a = float(exponent)
    tail = 1.0 - (s1 / s0) ** -a
    # every lattice cell whose block could reach the points: its parameters once per cell (not once per point and
    # neighbour), then each block present stamped over its own footprint only
    reach = 0.75 * s1
    IX, IY = np.meshgrid(np.arange(int(np.floor((xb.min() - reach) / L)), int(np.floor((xb.max() + reach) / L)) + 1),
                         np.arange(int(np.floor((yb.min() - reach) / L)), int(np.floor((yb.max() + reach) / L)) + 1))
    h = lattice_hash(IX.ravel(), IY.ravel(), int(seed) * 131 + int(salt))
    cx = (IX.ravel() + 0.1 + 0.8 * _unit(h, 0)) * L
    cy = (IY.ravel() + 0.1 + 0.8 * _unit(h, 1)) * L
    keep = _unit(h, 2) < density(cx, cy)
    if not keep.any():
        return out
    h, cx, cy = h[keep], cx[keep], cy[keep]
    size = s0 * (1.0 - _unit(h, 3) * tail) ** (-1.0 / a)
    th = _unit(h, 4) * math.pi
    asp = 0.55 + 0.45 * _unit(h, 5)
    top = size * (height_frac[0] + (height_frac[1] - height_frac[0]) * _unit(h, 6))
    axes = _meshgrid_axes(xb, yb) if xb.ndim == 2 else None
    if axes is not None and not (axes[0][1] > axes[0][0] and axes[1][1] > axes[1][0]):
        axes = None
    for k in range(cx.size):
        rad = (1.1 if profile == 'mound' else 0.72) * size[k]
        if axes is not None:
            xr, yc = axes
            i0, i1 = np.searchsorted(xr, cx[k] - rad), np.searchsorted(xr, cx[k] + rad, 'right')
            j0, j1 = np.searchsorted(yc, cy[k] - rad), np.searchsorted(yc, cy[k] + rad, 'right')
            if i1 <= i0 or j1 <= j0:
                continue
            dx, dy = (xr[i0:i1] - cx[k])[None, :], (yc[j0:j1] - cy[k])[:, None]
            win = (slice(j0, j1), slice(i0, i1))
        else:
            win = (np.abs(xb - cx[k]) < rad) & (np.abs(yb - cy[k]) < rad)
            if not win.any():
                continue
            dx, dy = xb[win] - cx[k], yb[win] - cy[k]
        c, s = math.cos(th[k]), math.sin(th[k])
        du = (dx * c + dy * s) / (0.5 * size[k])
        dv = (dy * c - dx * s) / (0.5 * size[k] * asp[k])
        if profile == 'mound':
            # a soft mound (sediment held round a shrub's roots): a Gaussian of half its size, cut off at its edge
            d2 = du * du + dv * dv
            z = top[k] * np.clip(np.exp(-2.5 * d2) - 0.02, 0.0, None) / 0.98
        else:
            d4 = du * du * du * du + dv * dv * dv * dv
            z = top[k] * np.sqrt(np.clip(1.0 - d4 ** 0.6, 0.0, None))     # a rounded top, steep sides
        out[win] = np.maximum(out[win], z)
    return out


def op_crater_blocks(fields, level, params, seed, ctx=None):
    """Stage op 'crater_blocks': the blocks fallen from a crater's face, lying where rockfall comes to rest - over the
    debris apron's upper part and at its foot, thinning out onto the floor (Meteor Crater's walls shed broad talus and
    boulder slopes). Put it on the hero levels ('cell<=1.5'), after the aging and talus stages. params: crater (the
    impact_crater stage's params: centre, diameter_m and the planform), sets ([dict(spacing_m, size_m (lo, hi),
    density (the most per lattice cell), rho (four radii over the crater's broad outline: the density rises from 0
    at the first to full at the second and falls back to 0 between the third and the fourth), height_frac, profile
    ('slab': blocks of rock; 'mound': hummocks of sediment round the floor's shrubs))]). Added once per terrain
    (stamp_add) to h, and to bed for the blocks (rock) or to deposit for the mounds (sediment)."""
    if _prepass(ctx):
        return fields
    c = dict(params['crater'])
    sd = int(c.get('seed', seed))
    centre = c.get('centre', (0.0, 0.0))
    R = 0.5 * float(c['diameter_m'])
    sides, polygon = int(c.get('sides', 0)), float(c.get('polygon', 0.0))
    paz, rn = float(c.get('polygon_azimuth_deg', 0.0)), float(c.get('radius_noise', 0.0))
    sets = [dict(s) for s in params.get('sets', ())]
    reach = R * max(float(s['rho'][3]) for s in sets) * 1.3 + max(float(s['size_m'][1]) for s in sets)

    def rho_low(xq, yq):
        r, az = polar(xq, yq, centre)
        az = azimuth_sampler(az)
        plan = polygon_factor(az, sides, polygon, paz)
        if rn:
            plan = plan * (1.0 + rn * azimuth_noise(az, sd, 61, 1, 6))
        return r / (R * plan)

    def evaluate(x, y):
        rock = np.zeros(np.broadcast(x, y).shape)
        soft = np.zeros_like(rock)
        if float(np.min(np.hypot(x - centre[0], y - centre[1]))) > reach:
            return {'h': rock, 'bed': rock, 'deposit': soft}
        for i, s in enumerate(sets):
            r0, r1, r2, r3 = (float(v) for v in s['rho'])
            dmax = float(s['density'])
            prof = s.get('profile', 'slab')

            def dens(cx, cy, r0=r0, r1=r1, r2=r2, r3=r3, dmax=dmax):
                q = rho_low(cx, cy)
                return dmax * smoothstep(r0, r1, q) * (1.0 - smoothstep(r2, r3, q))
            b = boulders(x, y, dens, s['spacing_m'], s['size_m'], sd, 7919 + i,
                         height_frac=tuple(s.get('height_frac', (0.3, 0.6))), profile=prof)
            if prof == 'mound':
                soft = np.maximum(soft, b)
            else:
                rock = np.maximum(rock, b)
        return {'h': np.maximum(rock, soft), 'bed': rock, 'deposit': np.maximum(soft - rock, 0.0)}
    # one pass (block False): boulders loops over the blocks themselves, each stamped over its own footprint
    stamp_add(fields, level, _stamp_key('crater_blocks', dict(params, seed=sd)), evaluate, 1, ctx=ctx, block=False)
    _pull_band(fields, ctx)
    return fields


op_crater_blocks.evolves = True
OPS = {'impact_crater': op_impact_crater, 'crater_blocks': op_crater_blocks}
