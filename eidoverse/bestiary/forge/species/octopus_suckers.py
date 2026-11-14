"""The octopus's GEOMETRIC SUCKERS (PLAN round 6: "Low: the proximal suckers as geometry"). The v4 sculpt's sessile
suckers stand up to 0.40 d off the arm's skin (7 mm on the 17.8 mm ones); baked into the maps of a smooth arm tube they
read as pale rings with jagged rims from below and as a sawtooth line edge-on (t10_low_arm, t11_arm030): a normal map
cannot carry relief that tall. So the large suckers become real geometry, as ONE design:

  * a TEMPLATE at unit diameter d (every length below is in d): its high an SDF program (the body revolved from a
    meridian profile, sdf.REVOLVE: a thick rounded rim, a shallow infundibular cone, the orifice's lip, the slot round
    the acetabular roof's protuberance; smooth-unioned into a slab of arm skin so the base flares into it), voxelised
    and sculpted (the infundibulum's CUSHIONS, whose creases are the radial grooves, 20 at the orifice forking to 32
    at the rim: Tramacere 2014, Gleadall 2016), then a TEXTURE tier for what is under a millimetre at the largest
    suckers (the grooves' hairlines, the concentric grooves, the rim's denticles and folds, the protuberance's grain,
    the wall's grain); its low a REVOLVED profile in LODs by size class, one polar UV island (seamless: the island's
    rim is the buried base ring), baked once (normal, AO, cavity, height) at D_REF and painted, so every sucker
    stacks the same texels;
  * PLACEMENT from the sculpt plan's own instances (t10's instances.npz: the reference arm's suckers, the other seven
    arms its rotation, octopus_sculpt.arm_rotations): geometry along each arm out to where the suckers fall under GEO_D
    (geo_mask: a clean cut, never interleaved with painted ones), the rest stays baked. Each sucker turned
    a random azimuth about its axis, squashed radially where the plan's size jitter overlaps two rims (squash), its
    base kept inside its own cell between neighbours (confine_base) and CONFORMED to the arm's low: the base ring sunk
    under the skin beneath it by max(0.07 d, 0.6 mm) + K_LIFT x the length of the low's triangle there (what a bent
    arm lifts a base off its skin), the fillet ring the template's height over it, so no gap shows where the skin
    falls away across a curved arm (3.1 mm under the largest) or when the arm bends; the conformed base rings then
    kept on their own side of every neighbour's separating plane (separate_bases), so no two suckers CROSS in any pose
    the gates run (Crossings: t26 X);
  * SKINNING: every sucker vertex takes the arm skin's weights where its axis meets the skin (octopus_rig's field,
    interpolated on the low's triangle), so the suckers bend with the arm;
  * the arm's BAKE keeps the large suckers as AO / cavity OCCLUDERS only (occluder_values: the same voxel topology, a
    second value array min(skin, suckers) that bake.py's AO and cavity rays read; patches/sucker_geometry.md), so their
    contact shadow lands on the skin while the skin's normal and height carry no doubled relief;
  * EXPORT as its own primitive and material (add_to_glb): the masks pack in the skin's channel order (R thin, G
    ventral, B sucker parts: rim 1, disc .66, cup .33, A the wall: the arm's skin carried up the cup) and COLOR_0 per
    sucker (the arm's skin colour round its base, its dark band display in alpha) for bestiary.js's suckerMaterial.

Live references (work/bestiary/research/BODY_PLAN_PHOTOS.md; refs/body/14, 15; refs/colour/04, 09): a low soft cup on a
broad base, no neck (the round rim overhangs a slightly waisted wall that flares into the arm: c04's side views, c09's
oblique row); a thick rounded rim whose outer margin is a beaded, folded fringe ("a rim covered with a deeply
folded, loose epithelium": Kier & Smith 1990, Tramacere 2013); the infundibulum a shallow cone ("cone-shaped at rest")
with ~20 fine radial grooves at the orifice that branch toward the rim; the orifice ~0.2 d across, filled almost to its
lip by the acetabular roof's granular protuberance (O. vulgaris: Tramacere 2013).
"""
import numpy as np
import warp as wp

from .. import sdf as S_

wp.set_module_options({'enable_backward': False})    # forward-only kernels: no adjoint code to compile

D_REF = 0.016           # the template's high is built and baked at this diameter (m): the forge's metric constants
                        # (the bake's reach, the AO radius, the voxel kernels' least steps) hold at a creature's scale;
                        # the maps are scale-free (the normal exactly, AO and cavity at the template's own radii in d)
GEO_D = 0.006           # suckers about this large and up are geometry, cut cleanly along each arm (geo_mask) (by eye: at
                        # 7.4 mm, t11_arm070's edge-on row is still a painted sawtooth; at 0.40 d a 6 mm sucker stands
                        # 2.4 mm off a 12-13 mm arm)
# the LOD by size class: (smallest d, lod); the low's rings per LOD and its segments round the axis (M). Every ring the
# outline or the arm's skin can cut takes M (ring_count), the buried base ring too; the dish's edge I takes I_SEG and
# the orifice's rings O_SEG. The rings are zipped by angle (template_lod). (Review 10-21: the first LODs' 13 / 10 /
# 8-gons read as nuts edge-on at 0.03-0.05 m frames; I at 6 showed as a hexagon inside the lip at oblique views. Stage
# 4, the close-up pass: at her frame's x4 (~43 px per mm on the nearest cups) stage 3's 15 / 12 / 10-gons turned 24 deg
# at every corner, the base ring at M / 2 drew a 7-gon crown where the skin cuts the base strip, the wall was one
# straight strip and the orifice a painted black dot. Now 24 / 18 / 14-gons, the waist WA and the rim's underside U
# bend the wall under the overhanging rim, and on LOD0 the orifice is an OPENING, its lip O over the protuberance's
# edge P (c09, b15): 191,584 triangles in all, against 79,624; the budget is the lead's call, patches/sucker_closeup.md)
LOD_TIERS = ((0.013, 0), (0.009, 1), (GEO_D, 2))
LODS = {0: (('B', 'W', 'WA', 'U', 'S', 'SC', 'C', 'I', 'O', 'P', 'X'), 24),
        1: (('B', 'W', 'WA', 'S', 'C', 'I', 'X'), 18),
        2: (('B', 'WA', 'S', 'C', 'I', 'X'), 14)}
I_SEG = 12              # the dish's edge ring's segments at every LOD (the same ring, so the dish maps alike: an
                        # 8-gon showed inside the lip at oblique views)
O_SEG = 16              # the orifice's rings (LOD0): the opening is 0.21 d across, ~150 px at her frame's x4
TRI_BUDGET = 192_000    # t26 B's bar for all eight arms. (80,000 through stage 3, the round-6 build's own limit: it
                        # held 15 / 12 / 10-gons with no waist and no opening. The close-up template is 191,584, one
                        # draw call as before, +61,032 skinned vertices: the lead's call, patches/sucker_closeup.md)
TEX = 1024              # the template's texture set (one island, stacked by every sucker)
BURY = (0.07, 0.0006)   # the base ring sunk under the skin beneath it: max(0.07 d, 0.6 mm) + K_LIFT L for the low's
K_LIFT = 0.11           # triangle under it, L long: a sucker vertex's blended weights bend it smoothly while the skin
BEND_C = 4.0            # there stays the interpolation of that triangle's corners, so a bent arm moves the base off its
                        # skin along the normal, measured up to 0.105 L at a curl of BEND_C local arm radii and 0.115 L
                        # at 2.5 (the first two-row suckers past the crown, on 22-29 mm quads: t26 D, patches/
                        # scratch_suckers/probe_gap2; L^2 / 8 rho, the chord sag, under-read it near the crown)

# ---------------------------------------------------------------------------------------------- the meridian profile
# (review 10-21: the first profile read as a machined can beside the photos: a vertical wall, a thick round torus
# 0.17 d across with a furrow inside it, and a pale disc only 0.58 d across, so from below a sucker read as a hubcap: a
# small disc, a dark groove ring, a broad pale tyre. Photo 15 has the pale infundibulum out to ~0.42 d, a narrow pale
# band and the beaded fringe from ~0.45 d; colour 04 a short wall under a soft lip that is TALLER than it is wide, the
# base flaring into the arm. So: a narrower, taller elliptical lip, a broad infundibulum rising into it with no furrow,
# a broader fillet)
RIM_C = np.array([0.445, 0.335])   # the rim's lip: the centre (r, y) of its ELLIPTICAL round, the semi-axes radial
RIM_A = (0.055, 0.065)             # and axial (a soft lip 0.11 d across, taller than wide: c04); its outer side the
RIM_R = RIM_A[0]                   # sucker's widest (r 0.50: the rim's diameter is d; same-row neighbours sit 0.97-1.05
                                   # d apart, so nothing may bulge past it), its crest the top (y 0.40:
                                   # octopus.arm_rest_height stands the arm on 0.40 d rims)
K_FILLET = 0.12                    # the base's fillet into the skin (the smooth union's k): the broad base of c04
# (stage 4, the close-up pass: at her frame's x4 the cups read as DRUMS, a straight wall under a flat face. The photos
# beside them (c04's side views, c09's oblique row): the thick round rim OVERHANGS a short waisted wall that flares into
# the arm, and the infundibulum is a shallow FUNNEL falling to a soft-lipped orifice. So the lip's round continues under
# its outer side to A_UNDER, the wall narrows to a waist under it and flares out to its foot, the dish falls further)
LIP_Y = 0.262                      # the orifice's lip and the roof protuberance's top (0.013 d under it: it nearly
PROT_Y = LIP_Y - 0.013             # fills the orifice, b15). (0.283 made a dish falling 0.035 d over 0.25 d, 8 deg: a
                                   # flat plate at oblique views; c09's funnel falls ~0.06 d, 13 deg)
ORI_R = 0.097                      # the orifice's wall, its lip's round (radius LIP_RND) above it, the protuberance's
LIP_RND = 0.012                    # radius PROT_R inside it: a slot 0.008 d wide (stage 3: 0.015 d round, 0.084 d
PROT_R = 0.089                     # protuberance, a 0.013 d slot)
DISH_R = 0.37                      # the infundibulum's outer edge, where it turns up into the lip's inner side (b15:
DISH_Y = 0.318                     # the pale dish to ~0.42 d with the lip's inner slope), and its height there
A_UNDER = -35.0                    # the lip's round runs on under its outer side to here (degrees) before the wall
WAIST = (0.225, 0.4595)            # the wall's waist (y, r): 0.04 d inside the rim's outer side (c04's overhang)
FOOT_R = 0.505                     # the wall's foot (r at the skin, before the fillet flares it: c04's trumpet base);
                                   # from it to the waist the wall runs nearly straight (the low's one strip W-WA)


def rim_point(a_deg):
    """the lip's round at angle a (degrees: 0 its outer side, 90 the crest, 180 its inner side): (r, y) in d"""
    a = np.radians(np.asarray(a_deg, np.float64))
    return np.stack([RIM_C[0] + RIM_A[0] * np.cos(a), RIM_C[1] + RIM_A[1] * np.sin(a)], -1)


def rim_angle(r, y):
    """the lip's angle (degrees) of points (r, y) in d about its centre, in the round's own (elliptical) measure"""
    return np.degrees(np.arctan2((np.asarray(y) - RIM_C[1]) / RIM_A[1], (np.asarray(r) - RIM_C[0]) / RIM_A[0]))


def rim_dist(r, y):
    """the elliptical 'radius' share of points about the lip's centre (1 on the round)"""
    return np.hypot((np.asarray(r) - RIM_C[0]) / RIM_A[0], (np.asarray(y) - RIM_C[1]) / RIM_A[1])


def rim_normal(a_deg):
    """the lip's outward profile normal (nr, ny) at angle a"""
    a = np.radians(a_deg)
    n = np.array([np.cos(a) / RIM_A[0], np.sin(a) / RIM_A[1]])
    return n / np.linalg.norm(n)


def _arc(c, rad, a0, a1, step):
    n = max(int(np.ceil(abs(a1 - a0) * rad / step)), 2)
    a = np.linspace(a0, a1, n)
    return np.column_stack([c[0] + rad * np.cos(a), c[1] + rad * np.sin(a)])


def _bezier(p0, p1, p2, p3, n):
    t = np.linspace(0.0, 1.0, n)[:, None]
    return (1 - t) ** 3 * p0 + 3 * t * (1 - t) ** 2 * p1 + 3 * t * t * (1 - t) * p2 + t ** 3 * p3


def dish_y(r):
    """the infundibulum's height at radius r (d): a shallow cone falling to the orifice, its slope easing toward it
    (at rest the infundibulum is cone-shaped, its centre drawn in: Kier & Smith 1990)"""
    x = np.clip((np.asarray(r, np.float64) - 0.118) / (DISH_R - 0.118), 0.0, None)
    return LIP_Y + (DISH_Y - LIP_Y) * x ** 1.25


def dish_slope(r):
    x = np.clip((np.asarray(r, np.float64) - 0.118) / (DISH_R - 0.118), 1e-6, None)
    return (DISH_Y - LIP_Y) * 1.25 * x ** 0.25 / (DISH_R - 0.118)


A_IN = 160.0                       # where the lip's round hands over to the blend down into the dish (degrees)


def body_profile(step=0.0025):
    """the sucker body's meridian profile (r, y) in d, a closed polygon for sdf.revolve (its closing segment runs down
    the axis): the buried bottom, the outer wall (a short soft cup: a slight flare toward its foot, a slight waist under
    the lip, as c04's lip overhangs its wall), the lip's elliptical round over the crest and down its inner side, a
    smooth concave turn into the infundibulum's broad shallow cone (no furrow: b15's dish rises straight into the lip),
    the orifice's rounded lip and wall, the slot round the roof's protuberance, the protuberance's granular dome nearly
    filling the orifice (b15)"""
    from scipy.interpolate import CubicSpline
    parts = [np.array([[0.0, -0.25], [FOOT_R, -0.25]])]
    # the wall: a clamped cubic r(y) from its foot (FOOT_R, vertical) narrowing to the WAIST and out again into the lip's
    # round, which it meets at A_UNDER with the round's own slope, so the rim overhangs it (c04, c09); the fillet into
    # the skin (high_program) flares its foot. (Stage 3's wall, a convex dome from 0.545 d narrowing to the lip, read as
    # a drum at her frame's x4; neighbours' walls may lean into each other's space below the lips: confine_base keeps
    # the low's base rings on their own side)
    pu = rim_point(A_UNDER)
    au = np.radians(A_UNDER)
    slope_u = (-RIM_A[0] * np.sin(au)) / (RIM_A[1] * np.cos(au))          # dr / dy of the round at A_UNDER
    yk = np.array([-0.25, 0.0, 0.08, 0.15, 0.20, WAIST[0], pu[1]])
    rk = np.array([FOOT_R + 0.02, FOOT_R, FOOT_R - 0.0165, FOOT_R - 0.0325, WAIST[1] + 0.0025, WAIST[1], pu[0]])
    wall = CubicSpline(yk, rk, bc_type=((1, -0.08), (1, slope_u)))
    y = np.linspace(-0.25, pu[1], int(np.ceil((pu[1] + 0.25) / step)) + 1)
    parts.append(np.column_stack([wall(y), y])[1:])
    n_rim = max(int(np.ceil(np.radians(A_IN - A_UNDER) * RIM_A[1] / step)), 8)
    rim = rim_point(np.linspace(A_UNDER, A_IN, n_rim))
    parts.append(rim[1:])
    # the lip's inner side into the dish: a cubic from the round's end (heading down, a little in) to the dish's edge
    p0 = rim[-1]
    a = np.radians(A_IN)
    t0 = np.array([-RIM_A[0] * np.sin(a), RIM_A[1] * np.cos(a)])
    t0 /= np.linalg.norm(t0)
    q = np.array([DISH_R, dish_y(DISH_R)])
    tq = np.array([-1.0, -dish_slope(DISH_R)])
    tq /= np.linalg.norm(tq)
    parts.append(_bezier(p0, p0 + 0.018 * t0, q - 0.014 * tq, q, 14)[1:])
    r = np.linspace(DISH_R, 0.118, int(np.ceil((DISH_R - 0.118) / step)) + 1)[1:]
    parts.append(np.column_stack([r, dish_y(r)]))
    # the orifice, its depths below its lip (LIP_Y) as stage 3's; the protuberance nearly fills it (b15): the slot
    # round it a thin line (stage 3's 0.013 d slot under a 0.015 d lip round read as a black ring round a white button)
    parts.append(_arc(np.array([ORI_R + LIP_RND, LIP_Y - LIP_RND]), LIP_RND, 0.5 * np.pi, np.pi, step))   # the lip
    parts.append(np.array([[ORI_R, LIP_Y - 0.043], [ORI_R, LIP_Y - 0.068]]))                   # the orifice's wall
    sr = 0.5 * (ORI_R - PROT_R)
    parts.append(_arc(np.array([PROT_R + sr, LIP_Y - 0.068]), sr, 0.0, -np.pi, step)[1:])      # the slot's floor
    parts.append(np.array([[PROT_R, LIP_Y - 0.057], [PROT_R, LIP_Y - 0.047]]))                 # the protuberance
    a = np.linspace(0.0, 0.5 * np.pi, 16)
    parts.append(np.column_stack([PROT_R * np.cos(a), LIP_Y - 0.047 + (PROT_Y - LIP_Y + 0.047) * np.sin(a)]))
    P = np.concatenate(parts)
    keep = np.concatenate([[True], np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-6])
    return P[keep]


def high_program(dref=D_REF):
    """the template's high as an SDF program at diameter dref: the revolved body smooth-unioned into a slab of arm skin
    (its top at y = 0, 1.25 d round), so the base flares into the skin with the fillet K_FILLET"""
    prog = S_.Program()
    prog.revolve(body_profile() * dref, [0.0, 0.0, 0.0], [0.0, 1.0, 0.0], name='sucker body')
    slab = np.array([[0.0, -0.40], [1.25, -0.40], [1.25, 0.0], [0.0, 0.0]]) * dref
    prog.revolve(slab, [0.0, 0.0, 0.0], [0.0, 1.0, 0.0], k=K_FILLET * dref, name='arm skin')
    return prog


def body_occluder_program():
    """the body alone at UNIT diameter (no skin slab): the arm bake's occluder shape (occluder_values)"""
    prog = S_.Program()
    prog.revolve(body_profile(0.004), [0.0, 0.0, 0.0], [0.0, 1.0, 0.0], name='sucker occluder')
    return prog


# ---------------------------------------------------------------------------------------------- the radial grooves
def groove_paths(seed=26):
    """the infundibulum's radial grooves as azimuth functions phi(r) over a radial span, in d: 20 at the orifice at
    18 deg +- 3 (Tramacere et al. 2014, O. vulgaris), 12 of them forking between r 0.20 and 0.26 so 32 reach the rim
    ("about 32 well-developed cushions, coalescing to around 20 centrally", Gleadall). Returns a list of (r0, r1,
    phi(r) callable). The sculpt carves them as soft valleys, the texture tier draws their hairlines in the same
    places"""
    rng = np.random.default_rng(seed)
    out = []
    n = 20
    forks = set(rng.choice(n, 12, replace=False).tolist())
    for k in range(n):
        # (the jitter clipped at 3 deg: two neighbours 8 deg apart, both forked, bunched five creases together, probe 3)
        ph0 = 2.0 * np.pi * k / n + np.radians(np.clip(rng.normal(0.0, 2.0), -3.0, 3.0))
        amp, om, ps = np.radians(rng.uniform(0.6, 1.8)), rng.uniform(0.6, 1.4), rng.uniform(0.0, 2.0 * np.pi)
        base = (lambda r, ph0=ph0, amp=amp, om=om, ps=ps:
                ph0 + amp * np.sin(np.pi * om * (np.asarray(r) - 0.10) / 0.33 + ps))
        if k in forks:
            # (review 10-21: forks split over 0.05 d read as Y-shaped cracks on the hubcap; b15's grooves part
            # gradually, so the split runs over 0.10 d and opens at most ~3.5 deg)
            rf = rng.uniform(0.19, 0.25)
            out.append((0.094, rf, base))
            dmax = np.radians(3.6) * rng.uniform(0.8, 1.2)
            for sgn in (-1.0, 1.0):
                def br(r, base=base, rf=rf, dmax=dmax, sgn=sgn):
                    x = np.clip((np.asarray(r) - rf) / 0.10, 0.0, 1.0)
                    return base(r) + sgn * dmax * x * x * (3.0 - 2.0 * x)
                out.append((rf, GROOVE_R1, br))
        else:
            out.append((0.094, GROOVE_R1, base))
    return out


GROOVE_R1 = 0.36                   # the grooves reach the dish's edge (DISH_R), where it turns up into the lip


def groove_sides(r, th, paths, chunk=250_000):
    """per point (r, th) on the dish (d, radians): the arc distances (d) to the nearest groove centreline on either
    side (left: th increasing, right) among the grooves whose span covers r (1e9 where none)"""
    r = np.asarray(r, np.float64).ravel()
    th = np.asarray(th, np.float64).ravel()
    left = np.full(len(r), 1e9)
    right = np.full(len(r), 1e9)
    for s in range(0, len(r), chunk):
        rr, tt = r[s:s + chunk], th[s:s + chunk]
        lo, hi = left[s:s + chunk], right[s:s + chunk]
        for r0, r1, ph in paths:
            on = (rr >= r0) & (rr <= r1)
            dth = (ph(rr) - tt + np.pi) % (2.0 * np.pi) - np.pi          # > 0: the groove lies at a larger angle
            arc = np.abs(dth) * np.maximum(rr, 1e-6)
            lo[:] = np.where(on & (dth >= 0.0) & (arc < lo), arc, lo)
            hi[:] = np.where(on & (dth < 0.0) & (arc < hi), arc, hi)
    return left, right


CUSHION_H = 0.0009                 # the cushions' crown over the grooves' creases (d; 0.0032 shaded each cushion as a
                                   # facet ~10 deg off its neighbour, 0.0024 and 0.0015 still a fan's blades at an
                                   # oblique view beside b14 / b15's soft dish, review 10-21)


def cushion_height(r, th, paths):
    """the infundibulum's CUSHIONS (Gleadall's "about 32 well-developed cushions, coalescing to around 20 centrally"):
    per point (r, th) in d, the height (d) over the dish: a soft dome across each cushion (the sine of the share
    across it), zero ON the grooves (the creases between cushions), lower where a cushion is narrow (just past a
    fork), fading out at the orifice's lip and at the rim's foot. The grooves' hairlines are the texture tier's"""
    r = np.asarray(r, np.float64).ravel()
    lt, rt = groove_sides(r, th, paths)
    w = lt + rt
    t = np.clip(lt / np.maximum(w, 1e-9), 0.0, 1.0)
    c = np.sin(np.pi * t) * np.clip(w / 0.028, 0.0, 1.0)
    fade = np.clip((r - 0.108) / 0.03, 0.0, 1.0) * np.clip((GROOVE_R1 - 0.005 - r) / 0.03, 0.0, 1.0)
    return np.where(w < 1e8, CUSHION_H * c * fade, 0.0)


# ---------------------------------------------------------------------------------------------- the voxel high
def build_high(dref=D_REF, voxel=None, log=print, seed=26):
    """the template's voxel high: a voxel.SparseSDF over the program (kept where the sucker is: r < 0.80 d), the
    infundibulum's CUSHIONS raised (the dish's voxels offset by cushion_height: the zero set moves out by it, the
    grooves are the creases where neighbouring cushions meet; carved valleys read as engraved spokes, probes 1-2),
    then a light smooth and the relevel (the sculpt brief's every-pass finish). Returns the SparseSDF"""
    from .. import voxel as VX
    vs = float(voxel or dref / 400.0)
    prog = high_program(dref)

    def keep(p):
        return (np.hypot(p[:, 0], p[:, 2]) < 0.80 * dref) & (p[:, 1] > -0.30 * dref)
    G = VX.SparseSDF(prog, np.array([-0.82, -0.30, -0.82]) * dref, np.array([0.82, 0.46, 0.82]) * dref, voxel=vs,
                     band=0.045 * dref, keep=keep, log=log)
    P = G.positions() / dref
    r = np.hypot(P[:, 0], P[:, 2])
    val = G.val.numpy()
    dish = (r > 0.10) & (r < GROOVE_R1) & (np.abs(P[:, 1] - dish_y(np.minimum(r, DISH_R))) < 0.045)
    h = cushion_height(r[dish], np.arctan2(P[dish, 2], P[dish, 0]), groove_paths(seed))
    val[dish] -= (h * dref).astype(np.float32)
    G.val = wp.array(val, dtype=wp.float32, device=G.val.device)
    log(f'[suckers] high: cushions on {int(dish.sum()):,} dish voxels (crown {CUSHION_H:.4f} d over the creases)')
    G.smooth(1, 0.5)
    G.redistance()
    return G


# ---------------------------------------------------------------------------------------------- the low template
W_Y = 0.035                        # the fillet ring's height over the skin (d): low on the fillet, so the low's own
                                   # base flares into the arm (at 0.07 d, the fillet's top, the low met the skin in a
                                   # near-vertical crease: the base strip B-W drops into the skin)
I_R = 0.30                         # the low's inner ring lies IN the flat dish, inside its edge (0.37): at the edge its
                                   # I_SEG-gon crease showed as an octagon round the dish at oblique views; the strip
                                   # C-I bridges the dish's concave turn (0.033 d over the high at most) and the normal
                                   # map carries the turn, round


O_A = 120.0                        # the orifice's lip ring O on the lip's round (its arc from 90, the dish's side, to 180,
P_A = 30.0                         # the orifice's wall); the protuberance's ring P on its dome (from 0, its edge, to 90)


def named_rings(prog=None, dref=D_REF):
    """the low's named rings (r, y) in d on the high's surface, outermost first: B the base ring (buried: conformed
    under the skin per sucker), W the fillet ring (low on the fillet, the base's flare into the arm), WA the wall's
    waist under the overhanging rim, S the lip's outer side (the widest), SC the lip's round at 50 deg, C the crest, I
    the dish's edge (where the lip's inner side turns into the infundibulum), O the orifice's lip, P the protuberance's
    dome near its edge (the slot between them the maps'), X the centre (the protuberance's top). W is measured on the
    high (its fillet at W_Y) when its program is given"""
    pt = lambda a: tuple(float(x) for x in rim_point(a))
    oa, pa = np.radians(O_A), np.radians(P_A)
    R = dict(B=(0.615, -0.060), W=(0.585, W_Y), WA=(WAIST[1], WAIST[0]), U=pt(A_UNDER), S=pt(0.0), SC=pt(50.0),
             C=pt(90.0), I=(I_R, float(dish_y(I_R))),
             O=(ORI_R + LIP_RND + LIP_RND * np.cos(oa), LIP_Y - LIP_RND + LIP_RND * np.sin(oa)),
             P=(PROT_R * np.cos(pa), LIP_Y - 0.047 + (PROT_Y - LIP_Y + 0.047) * np.sin(pa)), X=(0.0, PROT_Y))
    R = {k: (float(v[0]), float(v[1])) for k, v in R.items()}
    if prog is not None:
        # W on the fillet: march in from outside at its height to the high's surface (the fillet sets it, ~0.58 d); B
        # 0.03 d further out, under the skin
        for nm in ('W',):
            yy = R[nm][1]
            rs = np.linspace(0.75, 0.40, 701)
            f = prog.eval(np.column_stack([rs, np.full_like(rs, yy), np.zeros_like(rs)]) * dref)
            i = int(np.argmax(f < 0.0))
            R[nm] = (float(rs[i - 1] + (rs[i] - rs[i - 1]) * f[i - 1] / (f[i - 1] - f[i])), yy)
        R['B'] = (R['W'][0] + 0.03, R['B'][1])
    return R


_RINGS = {}


def rings():
    """the named rings measured on the template's own high (cached): every low (the bake's, the placed suckers', the
    budget's) takes the SAME rings, so the stacked maps land where they were baked"""
    if 'R' not in _RINGS:
        _RINGS['R'] = named_rings(high_program())
    return _RINGS['R']


SHARED_RINGS = ('B', 'WA', 'S', 'C', 'I', 'X')     # the rings every LOD carries


def ring_normals(R):
    """each named ring's outward normal in the meridian plane (nr, ny). The rings EVERY LOD carries (SHARED_RINGS) take
    the high's profile normal there (the wall's at the waist, horizontal; the lip's from its round; the buried base ring
    tipped up toward the skin's normal, so the strip's sliver above the skin shades into the arm instead of creasing;
    the dish's edge the DISH's normal, so the dish fan shades as the dish with no large correction in the normal map).
    A ring only the finer LODs carry (W, U, SC, O, P) takes the normal the coarser LODs interpolate at its UV radius: the
    normal map is baked once on LOD0 and stacked by every LOD, so its tangent-space corrections must decode alike on all
    of them (stage 4: LOD0's orifice rings at their true normals, 30 deg off the fan's, would have drawn a ring round
    every LOD1 / LOD2 orifice); LOD0's own shading there is the normal map's, from the high"""
    sl = float(dish_slope(R['I'][0]))
    n_i = np.array([-sl, 1.0]) / np.hypot(sl, 1.0)
    out = dict(B=(0.45, 0.89), WA=(1.0, 0.0), S=tuple(rim_normal(0.0)), C=(0.0, 1.0), I=tuple(n_i), X=(0.0, 1.0))
    rp = ring_params(R)
    shared = sorted(SHARED_RINGS, key=lambda n: rp[n])
    for nm in UV_ORDER:
        if nm in out:
            continue
        lo = max((n for n in shared if rp[n] <= rp[nm]), key=lambda n: rp[n])
        hi = min((n for n in shared if rp[n] >= rp[nm]), key=lambda n: rp[n])
        t = (rp[nm] - rp[lo]) / max(rp[hi] - rp[lo], 1e-12)
        v = (1.0 - t) * np.asarray(out[lo]) + t * np.asarray(out[hi])
        out[nm] = tuple(float(x) for x in v / np.linalg.norm(v))
    return out


# the UV island: each ring's arc parameter along the full low profile (X outward), its strips weighted (keyed by the
# strip's inner ring). A polar island stretches its outer strips round the axis (UV radius over r grows outward), so
# the wall's strips are weighted UP until a texel there is about as long as it is wide: 1.10-1.20 (at weight 1 the
# wall ran 1.40-1.64, the dish 1.08). (Stage 3 weighted the mostly buried base strip W-B up, 1.6: its M / 2 base ring's
# UV chords folded over the fillet ring at 0.5, review 10-21. The base ring has M vertices now, so that strip is a
# plain quad strip that cannot fold, and its buried texels go to the visible strips at 0.5)
UV_WEIGHT = dict(W=0.5, WA=1.5, U=1.3, S=1.1)


UV_ORDER = ['X', 'P', 'O', 'I', 'C', 'SC', 'S', 'U', 'WA', 'W', 'B']   # the island's rings from its centre out
                                                                       # (every LOD's dish is a fan from I)


def ring_params(R):
    """per named ring, its UV radius share (0 at the centre X .. 1 at the base ring B): the arc length along the
    LOD0 profile X-P-O-I-C-SC-S-U-WA-W-B, each strip weighted (UV_WEIGHT keys the strip by its inner ring: 'W' is W-B);
    every LOD shares these at its named rings, and every LOD's dish fans from the same ring I, so the texels map alike"""
    order = UV_ORDER
    s = {'X': 0.0}
    acc = 0.0
    for a, b in zip(order[:-1], order[1:]):
        acc += UV_WEIGHT.get(a, 1.0) * float(np.linalg.norm(np.asarray(R[b]) - np.asarray(R[a])))
        s[b] = acc
    return {k: v / acc for k, v in s.items()}


def ring_count(nm, M):
    """a named ring's vertices at an LOD of M outline segments: the centre one, the dish's edge I_SEG, the orifice's
    rings O_SEG, every other ring M (the buried base ring too: where the skin cuts the base strip it draws the strip's
    polygon, and at M / 2 that was a 7-gon crown on every cup at her frame's x4)"""
    return 1 if nm == 'X' else I_SEG if nm == 'I' else O_SEG if nm in ('O', 'P') else M


def _zip(a0, ma, b0, mb, UV):
    """the triangles between two closed rings of ma and mb vertices (both from angle 0, counter-clockwise): ma + mb
    triangles, each step closing the SHORTER new diagonal in UV (a quad strip when ma == mb). (Zipped by angle share
    alone, a 7-gon round a 15-gon at 0.85 of its radius fanned one base vertex over two fillet vertices and folded a
    sliver, t26 uv_fold)"""
    F = []
    i = j = 0
    P = np.asarray(UV, np.float64)
    while i < ma or j < mb:
        if j >= mb:
            adv_a = True
        elif i >= ma:
            adv_a = False
        else:
            da = np.linalg.norm(P[a0 + (i + 1) % ma] - P[b0 + j % mb])     # advance on a: the edge a_{i+1} - b_j
            db = np.linalg.norm(P[a0 + i % ma] - P[b0 + (j + 1) % mb])     # advance on b: the edge a_i - b_{j+1}
            adv_a = da <= db
        if adv_a:
            F.append((a0 + i % ma, a0 + (i + 1) % ma, b0 + j % mb))
            i += 1
        else:
            F.append((a0 + i % ma, b0 + (j + 1) % mb, b0 + j % mb))
            j += 1
    return F


def template_lod(lod, R=None, size=TEX, pad=6):
    """one LOD of the low template at UNIT diameter: its named rings (LODS[lod]) revolved, each at ring_count's
    segments (the outline, wall and base rings at M, the dish's edge at I_SEG, the orifice's rings at O_SEG, the
    centre one vertex), the outline and base rings' radii set so their polygon's mean radius is the high's (2 r / (1 +
    cos(pi / m))), the dish's and orifice's rings on their circles; neighbouring rings zipped on their shorter
    diagonals; the UVs polar on one seamless island (u, v = 0.5 + rho (cos th, sin th), rho by ring_params: identical
    for every LOD at the named rings); the normals ring_normals' revolved. Returns dict(V, F, UV, N, ring (per vertex,
    its name's index in LODS[lod][0]), th,
    names, strips (per triangle, the strip's outer ring index))"""
    R = R or rings()
    names, M = LODS[lod]
    rp = ring_params(R)
    rn = ring_normals(R)
    rho_max = 0.5 - pad / float(size)
    V, UV, N, ring, TH = [], [], [], [], []
    counts, starts = [], []
    for k, nm in enumerate(names):
        r, y = R[nm]
        m = ring_count(nm, M)
        th = (np.arange(m) * 2.0 * np.pi / m) if m > 1 else np.zeros(1)
        rr = 0.0 if m == 1 else r if nm in ('I', 'O', 'P') else r * 2.0 / (1.0 + np.cos(np.pi / m))
        nr, ny = rn[nm]
        starts.append(len(V))
        counts.append(m)
        for t in th:
            V.append((rr * np.cos(t), y, rr * np.sin(t)))
            rho = rho_max * rp[nm]
            UV.append((0.5 + rho * np.cos(t), 0.5 + rho * np.sin(t)))
            N.append((nr * np.cos(t), ny, nr * np.sin(t)))
            ring.append(k)
            TH.append(t)
    F, strip = [], []
    for k in range(len(names) - 1):
        a0, ma, b0, mb = starts[k], counts[k], starts[k + 1], counts[k + 1]
        if mb == 1:                                    # the fan to the centre
            for j in range(ma):
                F.append((a0 + j, a0 + (j + 1) % ma, b0))
                strip.append(k)
        else:                                          # a strip, zipped on the shorter diagonals
            Fz = _zip(a0, ma, b0, mb, UV)
            F += Fz
            strip += [k] * len(Fz)
    V = np.asarray(V, np.float64)
    F = np.asarray(F, np.int64)
    N = np.asarray(N, np.float64)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    # winding: the face normals out (along the profile normals)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if np.sum(fn * N[F].mean(1)) < 0.0:
        F = F[:, [0, 2, 1]]
    return dict(V=V, F=F, UV=np.asarray(UV, np.float64), N=N, ring=np.asarray(ring, np.int64),
                th=np.asarray(TH, np.float64), names=names, strips=np.asarray(strip, np.int64), lod=lod, M=M)


def uv_flips(T):
    """a template's UV triangles wound against the island's majority (a fold-over: a coarse ring's chords crossing a
    finer ring), and the least |UV area| share of the mean (slivers): (flips, min area / mean area)"""
    e1 = T['UV'][T['F'][:, 1]] - T['UV'][T['F'][:, 0]]
    e2 = T['UV'][T['F'][:, 2]] - T['UV'][T['F'][:, 0]]
    a = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    s = np.sign(np.sum(np.sign(a)))
    return int((np.sign(a) != s).sum()), float(np.abs(a).min() / np.abs(a).mean())


def geo_mask(d, s, geo_d=GEO_D, band=0.05):
    """which of the plan's suckers are GEOMETRY (the rest stay baked): along the arm (s >= 0) every sucker proximal to
    the last one at least geo_d x (1 + band) across, a clean cut; off the arm (the oral disc's four, s < 0) by size. The
    plan jitters sizes +-5 %, so a size threshold alone interleaved geometric and painted suckers along each row near it
    (s 0.74-0.77: tall cups beside flat painted discs, t26 F at s 0.75, review 10-21). With 6 mm: 98 per arm as before,
    the 5.96 mm one at s 0.738 geometric and the 6.1 mm one at s 0.762 baked"""
    d, s = np.asarray(d, np.float64), np.asarray(s, np.float64)
    arm = s >= 0.0
    big = arm & (d >= geo_d * (1.0 + band))
    s_cut = s[big].max() if big.any() else -np.inf
    return np.where(arm, s <= s_cut, d >= geo_d)


def lod_of(d):
    """each diameter's LOD (-1 below GEO_D: baked)"""
    d = np.asarray(d, np.float64)
    out = np.full(d.shape, -1, np.int64)
    for dmin, lod in sorted(LOD_TIERS, key=lambda t: t[0]):
        out[d >= dmin] = lod
    return out


def lod_cost(lod):
    """(triangles, vertices) of one sucker at a LOD"""
    T = template_lod(lod)
    return len(T['F']), len(T['V'])


STRIP_NAMES = {'B': 'base', 'W': 'wall foot', 'WA': 'wall', 'U': 'rim under', 'S': 'rim outer', 'SC': 'rim top',
               'C': 'rim inner', 'I': 'dish', 'O': 'orifice', 'P': 'protuberance'}


def uv_radius_y(uv, R=None, lod=0, size=TEX, pad=6):
    """the low's height (d) under template UVs (n, 2): the polar island's radius share, between its named rings
    (the buried texels are those under y 0)"""
    R = R or rings()
    rp = ring_params(R)
    names = UV_ORDER
    rho = np.linalg.norm(np.asarray(uv, np.float64) - 0.5, axis=-1) / (0.5 - pad / float(size))
    return np.interp(rho, [rp[n] for n in names], [R[n][1] for n in names])


# ---------------------------------------------------------------------------------------------- the template bake
def bake_template(G, lod=0, size=TEX, ss=2, dref=D_REF, log=print, n_ao=32):
    """the template's LOD0 low baked against its voxel high (bake.bake at D_REF: the search reach and the AO radius
    in d, AO 0.30 d so the skin slab gives the base its contact shade). Returns (template, TAN, res, gate) where gate
    holds the VISIBLE texels' numbers (the buried base, under y 0, is hidden by the arm)"""
    from .. import bake as BK
    R = named_rings(G.prog, dref)
    T = template_lod(lod, R, size)
    V = T['V'] * dref
    _, TAN = BK.low_frames(V, T['F'], T['UV'], T['N'])
    names = {k: STRIP_NAMES.get(n, n) for k, n in enumerate(T['names'][:-1])}
    res = BK.bake(G, V, T['F'], T['UV'], T['N'], TAN, T['strips'], size=size, ss=ss, cage=0.12 * dref,
                  ao_r=0.30 * dref, cav_r=0.035 * dref, n_ao=n_ao, n_cav=16, n_thk=4, thk_max=0.5 * dref,
                  cage_min=0.002 * dref, reach_margin=0.02 * dref, far_max=0.05 * dref, region_names=names, log=log)
    # the visible texels' gate (the bake's own counts the buried base too)
    yy, xx = np.mgrid[0:size, 0:size]
    uv = np.column_stack([(xx.ravel() + 0.5) / size, 1.0 - (yy.ravel() + 0.5) / size])
    vis = (uv_radius_y(uv, R, lod, size) > 0.0).reshape(size, size)
    cov = res['normal'][..., 3] > 0
    inside = cov | (res['miss'] > 0)
    full = (res['miss'] > 0) & ~cov
    part = (res['miss'] > 0) & cov
    hgt = np.abs(res['height'][cov & vis])
    gate = dict(texels=int((inside & vis).sum()), full=int((full & vis).sum()), part=int((part & vis).sum()),
                full_pct=100.0 * (full & vis).sum() / max((inside & vis).sum(), 1),
                part_pct=100.0 * (part & vis).sum() / max((inside & vis).sum(), 1),
                d_p95=float(np.percentile(hgt, 95) / dref), d_max=float(hgt.max() / dref),
                bake_gate=bool(res['gate'][0]))
    gate['ok'] = gate['full_pct'] <= 0.5 and gate['d_p95'] <= 0.05
    log(f'[suckers] template bake {size}^2 x ss {ss}: visible texels {gate["texels"]:,}, fully missed '
        f'{gate["full_pct"]:.3f} % (bar 0.5 %), partly {gate["part_pct"]:.2f} %; low-to-high |d| p95 '
        f'{gate["d_p95"]:.4f} d ({gate["d_p95"] * 17.8:.2f} mm on the largest), max {gate["d_max"]:.3f} d: '
        f'{"PASS" if gate["ok"] else "FAIL"}')
    return T, TAN, res, gate


# ---------------------------------------------------------------------------------------------- the texture tier
def _hash2(i, j, seed):
    """a per-cell random in [0, 1) (integer hash, vectorised)"""
    x = (np.asarray(i, np.int64) * 73856093) ^ (np.asarray(j, np.int64) * 19349663) ^ (seed * 83492791)
    x = (x ^ (x >> 13)) * 1274126177
    return ((x ^ (x >> 16)) & 0xFFFFFF) / float(0x1000000)


def _worley(u, v, cell, seed, jit=0.8):
    """F1 and F2 distances (in u, v units) to jittered feature points on a cell-sized grid, and the nearest's random"""
    gu, gv = np.floor(u / cell).astype(np.int64), np.floor(v / cell).astype(np.int64)
    f1 = np.full(u.shape, 1e9)
    f2 = np.full(u.shape, 1e9)
    rid = np.zeros(u.shape)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            ci, cj = gu + di, gv + dj
            pu = (ci + 0.5 + jit * (_hash2(ci, cj, seed) - 0.5)) * cell
            pv = (cj + 0.5 + jit * (_hash2(ci, cj, seed + 1) - 0.5)) * cell
            dd = np.hypot(u - pu, v - pv)
            m1 = dd < f1
            f2 = np.where(m1, f1, np.minimum(f2, dd))
            rid = np.where(m1, _hash2(ci, cj, seed + 2), rid)
            f1 = np.where(m1, dd, f1)
    return f1, f2, rid


def _hash3(i, j, k, seed):
    """a per-cell random in [0, 1) on a 3D lattice (integer hash, vectorised)"""
    x = ((np.asarray(i, np.int64) * 73856093) ^ (np.asarray(j, np.int64) * 19349663)
         ^ (np.asarray(k, np.int64) * 83492791) ^ (seed * 2654435761))
    x = (x ^ (x >> 13)) * 1274126177
    return ((x ^ (x >> 16)) & 0xFFFFFF) / float(0x1000000)


def _worley3(p, cell, seed, jit=0.8):
    """F1 distance to jittered feature points on a 3D cell grid and the nearest's random, for points p (n, 3): a SOLID
    texture, so its cells keep their shape on whatever surface samples it (stage 4: the specks, the disc's mottle and
    the roughness jitter were cells on the polar island's chart, which the wall stretches 1.35-1.64x along the profile:
    the wall's specks read as vertical dashes at her frame's x4, live and copy alike)"""
    g = np.floor(p / cell).astype(np.int64)
    f1 = np.full(len(p), 1e9)
    rid = np.zeros(len(p))
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for dk in (-1, 0, 1):
                c0, c1, c2 = g[:, 0] + di, g[:, 1] + dj, g[:, 2] + dk
                fp = np.stack([(c + 0.5 + jit * (_hash3(c0, c1, c2, seed + s) - 0.5)) * cell
                               for s, c in ((0, c0), (1, c1), (2, c2))], -1)
                dd = np.linalg.norm(p - fp, axis=1)
                m1 = dd < f1
                rid = np.where(m1, _hash3(c0, c1, c2, seed + 3), rid)
                f1 = np.where(m1, dd, f1)
    return f1, rid


def _vnoise3(p, cell, seed):
    """smooth value noise in [0, 1] on a 3D lattice (the corners' randoms, smoothstep-interpolated): a solid texture"""
    s = p / cell
    g = np.floor(s).astype(np.int64)
    f = s - g
    w = f * f * (3.0 - 2.0 * f)
    out = np.zeros(len(p))
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                wt = ((w[:, 0] if di else 1.0 - w[:, 0]) * (w[:, 1] if dj else 1.0 - w[:, 1])
                      * (w[:, 2] if dk else 1.0 - w[:, 2]))
                out += wt * _hash3(g[:, 0] + di, g[:, 1] + dj, g[:, 2] + dk, seed)
    return out


def _sstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def texture_tier(q, seed=26):
    """the features under a millimetre at the largest suckers, as a HEIGHT (d) over the high, per point q (n, 3) on it
    in template units (d): the grooves' hairlines in the cushions' creases and the infundibulum's concentric grooves
    (Tramacere 2014: 280 um apart on ~13 mm suckers, 0.02 d), the rim's beaded fringe (b15: ~110 denticles round the
    outer margin) and its fine folds ("deeply folded, loose epithelium"), the roof protuberance's grain (b15), the
    wall's skin tiles (the arm's patch network carried up the cup, ~0.09 d). Returns (h, parts) with parts the masks
    the paint reads (groove, bead, fold, grain, tile groove)"""
    q = np.asarray(q, np.float64)
    r = np.hypot(q[:, 0], q[:, 2])
    th = np.arctan2(q[:, 2], q[:, 0])
    y = q[:, 1]
    h = np.zeros(len(q))
    face = (y > LIP_Y - 0.043) & (r < 0.40)                  # (the orifice's levels below its lip, as body_profile's)
    # the hairlines, in the creases (the cushions' grooves): fine and shallow (b15: thin lines, a hair's width at its
    # scale; 0.0022 d deep and 0.0048 d wide they drew dark spokes on the first template's dish)
    dish = face & (r > 0.095) & (r < GROOVE_R1)
    groove = np.zeros(len(q))
    if dish.any():
        lt, rt = groove_sides(r[dish], th[dish], groove_paths(seed))
        dist = np.minimum(lt, rt)
        fade = _sstep(0.095, 0.110, r[dish]) * (1.0 - _sstep(GROOVE_R1 - 0.02, GROOVE_R1, r[dish]))
        groove[dish] = np.exp(-(dist / 0.0018) ** 2) * fade
        conc = (0.5 + 0.5 * np.cos(2.0 * np.pi * (r[dish] - 0.10) / 0.021)) ** 6 * fade
        h[dish] += -0.0006 * groove[dish] - 0.0003 * conc
    # the lip: its round's angle a (0 outer side, 90 the crest, elliptical measure), the beads round the outer margin,
    # fine irregular wrinkles over the crest and down the inner side
    a = rim_angle(r, y)
    on_rim = (rim_dist(r, y) < 1.55) & (a > -40.0) & (a < 178.0)
    bead = np.zeros(len(q))
    fold = np.zeros(len(q))
    if on_rim.any():
        ar = np.radians(a[on_rim])
        u = th[on_rim] * 0.5                     # arc length round the lip's outer side (d)
        v = ar * 0.06                            # arc length over the round (d, its mean semi-axis)
        f1, f2, rid = _worley(u, v, 0.022, seed + 11)
        wv = _sstep(-12.0, 5.0, a[on_rim]) * (1.0 - _sstep(55.0, 72.0, a[on_rim]))
        rb = 0.0095 * (0.75 + 0.5 * rid)
        bead[on_rim] = np.clip(1.0 - (f1 / rb) ** 2, 0.0, 1.0) ** 1.5 * wv
        # (a regular 150-fold ripple over the crest read as a tyre's tread, review 10-21: the epithelium's folds are
        # irregular, running across the lip; cells drawn out 3x across it)
        f1w, f2w, _ = _worley(u * 1.4, v * 0.45, 0.012, seed + 13)
        wr = 1.0 - _sstep(0.0, 0.22, (f2w - f1w) / 0.012)
        fw = _sstep(45.0, 65.0, a[on_rim]) * (1.0 - _sstep(150.0, 176.0, a[on_rim]))
        fold[on_rim] = wr * fw
        h[on_rim] += 0.0025 * bead[on_rim] - 0.0005 * fold[on_rim]
    # the protuberance's grain
    prot = (r < PROT_R + 0.004) & (y > LIP_Y - 0.068)
    grain = np.zeros(len(q))
    if prot.any():
        f1, f2, rid = _worley(q[prot, 0], q[prot, 2], 0.011, seed + 21)
        grain[prot] = np.clip(1.0 - (f1 / 0.0065) ** 2, 0.0, 1.0) * (1.0 - _sstep(PROT_R - 0.019, PROT_R + 0.002,
                                                                                    r[prot]))
        h[prot] += 0.0022 * grain[prot]
    # the wall's skin: a fine GRAIN (b15's wall is finely granular under its chromatophores; tiles 0.085 d and then
    # 0.055 d across read as cobblestones and crazy paving on the arm, probes 4-5)
    wall = (r > 0.43) & (y < RIM_C[1] + 0.01) & (y > -0.02)
    tile = np.zeros(len(q))
    if wall.any():
        u = th[wall] * 0.5
        f1, f2, rid = _worley(u, y[wall], 0.026, seed + 31)
        e = (f2 - f1) / 0.026
        tg = 1.0 - _sstep(0.0, 0.15, e)
        dome = _sstep(0.0, 0.5, e)
        fw = 1.0 - _sstep(RIM_C[1] - 0.06, RIM_C[1], y[wall])
        tile[wall] = tg * fw
        h[wall] += (0.0005 * dome - 0.0002 * tg) * fw
    return h, dict(groove=groove, bead=bead, fold=fold, grain=grain, tile=tile)


def compose_normal(n_b, h, pos, dref=D_REF):
    """the baked tangent normals (H, W, 3) with the texture tier's height h (H, W, metres) composed in: the height's
    surface gradient from its texel differences and the surface's own (the position map's: metres per texel along
    u and v), in the bake's tangent frame (T along +u, B along +v: up the image), blended whiteout-style"""
    def du(a):
        out = np.zeros_like(a)
        out[:, 1:-1] = 0.5 * (a[:, 2:] - a[:, :-2])
        return out

    def dv(a):                                   # +v is up the image (row 0 is v = 1)
        out = np.zeros_like(a)
        out[1:-1] = 0.5 * (a[:-2] - a[2:])
        return out
    Pu = np.stack([du(pos[..., k]) for k in range(3)], -1)
    Pv = np.stack([dv(pos[..., k]) for k in range(3)], -1)
    hu, hv = du(h), dv(h)
    # the surface gradient g with g . Pu = hu, g . Pv = hv (g in the tangent plane spanned by Pu, Pv)
    a, b, c = (Pu * Pu).sum(-1), (Pu * Pv).sum(-1), (Pv * Pv).sum(-1)
    det = np.maximum(a * c - b * b, 1e-30)
    ca = (hu * c - hv * b) / det
    cb = (hv * a - hu * b) / det
    g = Pu * ca[..., None] + Pv * cb[..., None]
    T = Pu / np.maximum(np.linalg.norm(Pu, axis=-1, keepdims=True), 1e-20)
    B = Pv / np.maximum(np.linalg.norm(Pv, axis=-1, keepdims=True), 1e-20)
    gx, gy = (g * T).sum(-1), (g * B).sum(-1)
    nd = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    nd /= np.linalg.norm(nd, axis=-1, keepdims=True)
    n = np.stack([n_b[..., 0] + nd[..., 0], n_b[..., 1] + nd[..., 1], n_b[..., 2] * nd[..., 2]], -1)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-20)


# ---------------------------------------------------------------------------------------------- the paint
def srgb_lin(c):
    from ..material import srgb_eotf                   # the house helper (exact)
    return srgb_eotf(c)


def lin_srgb(L):
    from ..material import srgb_oetf                   # the house helper (exact)
    return srgb_oetf(L)


def lum(c):
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def at_lum(c_srgb, L):
    """an sRGB hue (its chroma ratios) at linear luminance L"""
    c = srgb_lin(c_srgb)
    return c * (L / max(float(lum(c)), 1e-9))


# the colour bars (forge/calib.py OCTOPUS_BARS, research/REAL_OCTOPUS_COLOUR.md §1, §3e): the disc near-neutral at
# x2.1-3.5 the arms' aboral L (t11 read x3.55-3.65: too bright), S 0.04-0.09; the rim band x0.33-0.44 the disc, S
# 0.20-0.40; the cup (the orifice's floor) x0.4-0.5 the disc in ambient light (here the albedo x0.8, the AO the rest);
# outside the rim band the arm's oral skin (S 0.45-0.54).
# (Stage 4: the disc back inside its bar, S 0.04-0.09, and read as tissue another way than M2b's S 0.20 hue
# (octopus_sucker_discs_m2b.md: a flat, uniform, near-neutral disc in a dark ring read as a washer). The photos' disc is
# a WARM off-white, photo 05's own hue (210, 200, 195), and it is never uniform: §3e's radial profiles put a pinker
# EDGE (205, 178, 176), S 0.15, between it and the rim band, c09's funnel darkens and warms toward the orifice, the
# cushions' crowns are paler than their creases (b15's fine radial lines), and the tissue is softly mottled. The
# orifice is no grey button: 07's is warm, S 0.18-0.38)
PAINT = dict(disc_ratio=2.8, disc_srgb=(0.824, 0.784, 0.765), edge_srgb=(0.804, 0.698, 0.690),
             centre_srgb=(0.800, 0.722, 0.686), rim_ratio=0.385, rim_srgb=(0.400, 0.310, 0.255), prot_ratio=0.68,
             prot_srgb=(0.640, 0.560, 0.505), speck_srgb=(0.300, 0.180, 0.130))
# (the rim's hue: REAL_OCTOPUS_COLOUR §3e's measured band, S 0.36; centre_srgb the funnel's floor toward the orifice,
# S 0.14, blended in over the inner half of the dish)
DISC_VAR = dict(radial=0.10, cushion=0.03, crease_pink=0.20, mottle=0.05)   # the disc's structure (L shares; the
                                                                          # creases' share of the edge's pink: at
                                                                          # 0.06 / 0.35 the sunlit disc read as a
                                                                          # fluted bowl's rays, b15's are faint lines)
AO_THIN = 0.30          # the translucent parts' AO depth cut by this share (the disc, its edge, the orifice): the light
                        # that scatters through thin tissue fills their creases, which an opaque bake shades as rings
                        # (the deeper orifice's slot baked to AO 0.38 and read as a black ring round a white button,
                        # where b15's protuberance sits in a soft thin line; the dish's edge as a dark ring b15 lacks)


def paint(res, dref=D_REF, aboral_L=0.108, wall_lin=None, seed=26, size=None, log=print):
    """the template's maps from its bake (image order): albedo (sRGB), normal (GL: the bake's with the texture tier
    composed in), ORM (AO, roughness, 0), masks (R thin, G ventral, B sucker parts: rim 1, disc .66, cup .33, A the
    wall). aboral_L: the arms set's aboral L p50 (the disc's bar is a ratio of it); wall_lin: the arm's oral skin
    round the suckers' bases (linear RGB; t26 measures it). Returns (maps uint8, info: zone colours for the bars)"""
    from scipy import ndimage
    from .. import bake as BK
    dil, grown = BK.dilate_all(res, 24)
    H, W_ = res['normal'].shape[:2]
    pos = dil['position'][..., :3]
    q = pos.reshape(-1, 3) / dref
    h, parts = texture_tier(q, seed)
    h = h.reshape(H, W_)
    parts = {k: v.reshape(H, W_) for k, v in parts.items()}
    nb = dil['normal'][..., :3]
    nb = nb / np.maximum(np.linalg.norm(nb, axis=-1, keepdims=True), 1e-9)
    nrm = compose_normal(nb, h * dref, pos, dref)
    r = np.hypot(q[:, 0], q[:, 2]).reshape(H, W_)
    y = q[:, 1].reshape(H, W_)
    # zones (the high's point; a = the angle round the lip's round, rim_angle: 0 its outer side, 90 the crest): the
    # orifice inside the lip, the disc (the infundibulum, to the dish's edge at 0.37 d), its pale pinker edge from there
    # over the lip's inner side and crest (b15's narrow white band), the pigmented rim BAND over the lip's outer
    # shoulder and the beaded margin (b15's purple fringe ~0.46-0.50, REAL_OCTOPUS_COLOUR §3e's darker band to rho 1.35
    # on its photos 05 / 07; a band to a 110 painted the whole round brown, t26 A beside b15), the wall below it (the
    # arm's skin carried up the cup: c04's orange wall)
    a = rim_angle(r, y)
    round_ = (rim_dist(r, y) < 1.6) & (r > 0.36)
    inner = 1.0 - _sstep(0.100, 0.113, r)
    face = _sstep(LIP_Y - 0.048, LIP_Y - 0.023, y)          # (the orifice's levels below its lip, as body_profile's)
    orifice = inner * face
    # (the band over the lip's outer shoulder to just outside the crest, a -12..80: face-on r 0.455-0.50, b15's beaded
    # fringe and b14's dark rim line; the pale edge a narrow band over the crest, a 80..125, b15's white band; the
    # disc's colour carried up the lip's inner side: a pale edge from the dish's edge over the whole inner side read as
    # a broad pale tyre round a small disc beside b14)
    rim = round_ * _sstep(-28.0, -12.0, a) * (1.0 - _sstep(72.0, 86.0, a))
    # (the wall from the waist down: stage 3's r 0.44-0.47 ramp would have half-masked the waist at 0.46)
    wall = _sstep(0.40, 0.43, r) * (1.0 - _sstep(-28.0, -12.0, a)) * (a < 60.0)
    edge = np.clip(round_ * _sstep(72.0, 86.0, a) * (1.0 - _sstep(116.0, 132.0, a)) * face - rim - wall, 0.0, 1.0)
    disc = np.clip(face * (1.0 - inner) - rim - wall - edge, 0.0, 1.0)
    slot = orifice * (1.0 - _sstep(LIP_Y - 0.078, LIP_Y - 0.048, y)) * _sstep(PROT_R - 0.004, PROT_R + 0.004, r)
    L_disc = PAINT['disc_ratio'] * aboral_L
    c_disc = at_lum(PAINT['disc_srgb'], L_disc)
    c_edge = at_lum(PAINT['edge_srgb'], 0.93 * L_disc)
    c_rim = at_lum(PAINT['rim_srgb'], PAINT['rim_ratio'] * L_disc)
    c_prot = at_lum(PAINT['prot_srgb'], PAINT['prot_ratio'] * L_disc)
    c_wall = np.asarray(wall_lin if wall_lin is not None else at_lum((0.56, 0.40, 0.28), 1.5 * aboral_L))
    c_speck = srgb_lin(PAINT['speck_srgb'])
    # the disc's own structure (the photos' disc is never one flat colour): the funnel's floor warmer and darker toward
    # the orifice, its outer part paler (c09); the cushions' crowns paler than their creases, the creases a touch of the
    # edge's pink (b15's radial lines); a soft mottle, a solid noise of the surface point (cells 0.09 d)
    dv = DISC_VAR
    tr = _sstep(0.12, 0.36, r)
    c_cen = at_lum(PAINT['centre_srgb'], L_disc)
    c_d = (c_cen + (c_disc - c_cen) * np.clip(0.5 + tr, 0.0, 1.0)[..., None]) \
        * (1.0 - dv['radial'] * (1.0 - tr))[..., None] * (1.0 + 0.4 * dv['radial'] * tr)[..., None]
    th = np.arctan2(q[:, 2], q[:, 0]).reshape(H, W_)
    dsk = (disc > 1e-3) & (r > 0.10) & (r < GROOVE_R1)
    ch = np.zeros((H, W_))
    if dsk.any():
        ch[dsk] = cushion_height(r[dsk], th[dsk], groove_paths(seed)) / CUSHION_H
    c_d = c_d * (1.0 + dv['cushion'] * (ch - 0.5))[..., None]
    c_d = c_d + (c_edge - c_d) * (dv['crease_pink'] * parts['groove'])[..., None]
    mott = _vnoise3(q, 0.09, seed + 61).reshape(H, W_) - 0.5
    mott = mott / max(float(mott[disc > 0.5].std()) if (disc > 0.5).any() else 1.0, 1e-9)   # (unit sd on the disc)
    c_d = c_d * (1.0 + 0.5 * dv['mottle'] * np.clip(mott, -2.0, 2.0))[..., None]
    col = (disc[..., None] * c_d + edge[..., None] * c_edge + rim[..., None] * c_rim
           + orifice[..., None] * c_prot + wall[..., None] * c_wall)
    wsum = disc + edge + rim + orifice + wall
    col = col / np.maximum(wsum, 1e-6)[..., None]
    col = np.where((wsum < 1e-3)[..., None], c_wall, col)
    # chromatophore specks on the rim band and the wall (the arm's pigment), none on the disc: a SOLID cell texture of
    # the surface point, so they keep their shape over the rim's crest and down the wall (stage 3 drew them on the polar
    # island's chart, ~0.53 UV units per d radially but 0.65-0.89 round the wall: dashes along the profile). A surface
    # cuts a 3D cell's feature at its own depth, so the cells are finer (0.034 d) and the specks a little larger than
    # stage 3's 0.045 d / 0.006-0.015 d, for the same density and sizes on the skin
    f1, rid = _worley3(q, 0.034, seed + 41)
    f1, rid = f1.reshape(H, W_), rid.reshape(H, W_)
    rs = 0.0065 + 0.0100 * rid
    speck = np.clip(1.0 - f1 / rs, 0.0, 1.0) ** 0.7 * (rid > 0.35) * np.clip(rim + wall, 0.0, 1.0)
    col = col + (c_speck - col) * (0.55 * speck)[..., None]
    # the denticles' tips a little paler, the wall's tile grooves pale (the skin's reticulation), the slot dark
    col = col * (1.0 + 0.10 * parts['bead'])[..., None]
    col = col + (np.clip(col * 1.25, 0.0, 1.0) - col) * (0.06 * parts['tile'])[..., None]
    col = col * (1.0 - 0.15 * slot)[..., None]
    # relief: crevices darker (cavity, the hairlines), richer (REF R4: cavities a little more saturated); gentler than
    # the first template's (x0.78 at a full cavity inked every crease: b15's dish is soft and pale)
    hp = h - ndimage.gaussian_filter(h, 3.0)
    cav_t = np.clip(1.0 + hp / 0.004, 0.0, 1.0)
    cavity = np.clip(dil['cavity'], 0.0, 1.0) * cav_t
    col = col * (0.85 + 0.15 * cavity)[..., None]
    alb = lin_srgb(col)
    # roughness: the disc's denticulate cuticle 0.26 (M2b), the rim's folded epithelium soft 0.24, the wall the skin's
    # 0.16, the orifice's granular protuberance 0.18 and its slot wet 0.14 (at 0.07 the protuberance caught a sharp
    # highlight: a white button); the hairlines a touch glossier
    rough = (0.26 * disc + 0.26 * edge + 0.24 * rim + 0.16 * wall + 0.18 * orifice) / np.maximum(wsum, 1e-6)
    rough = np.where(wsum < 1e-3, 0.16, rough)
    rough = rough - 0.02 * parts['groove'] - 0.04 * slot + 0.015 * (_worley3(q, 0.03, seed + 51)[1].reshape(H, W_)
                                                                       - 0.5)
    ao = np.clip(dil['ao'], 0.0, 1.0) * (0.75 + 0.25 * cav_t)
    ao = 1.0 - (1.0 - ao) * (1.0 - AO_THIN * np.clip(disc + edge + orifice, 0.0, 1.0))
    thin = 0.45 * rim * _sstep(-5.0, 20.0, a) + 0.25 * disc + 0.10 * orifice + 0.05 * wall
    sucker = np.clip(1.0 * rim + 0.66 * (disc + edge) + 0.33 * orifice, 0.0, 1.0)
    masks = np.stack([np.clip(thin, 0, 1), np.ones_like(thin), sucker, np.clip(wall, 0, 1)], -1)
    u8 = lambda a: np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8)
    maps = dict(albedo=u8(alb), normal=u8(nrm * 0.5 + 0.5), orm=u8(np.stack([ao, np.clip(rough, 0.04, 1.0),
                                                                            np.zeros_like(ao)], -1)),
                masks=u8(masks))
    maps = {k: np.where(grown[..., None], v, np.array([128, 128, 255] if k == 'normal' else
                                                     ([255, 128, 0] if k == 'orm' else [0] * v.shape[-1]),
                                                     np.uint8)[:v.shape[-1]]) for k, v in maps.items()}
    info = dict(c_disc=c_disc, c_rim=c_rim, c_wall=c_wall, c_prot=c_prot, L_disc=L_disc, aboral_L=aboral_L,
                wall_ref=c_wall)
    log(f'[suckers] paint: disc L {L_disc:.3f} (x{PAINT["disc_ratio"]} the aboral {aboral_L:.3f}), rim L '
        f'{float(lum(c_rim)):.3f}, wall {np.round(c_wall, 3)} (linear)')
    return maps, info


def calib_zones(maps, aboral_L, log=print):
    """the template set's colour bars (forge/calib.py OCTOPUS_BARS): per zone (masks B: rim 1, disc .66; A the wall)
    the albedo's linear L p50 and sRGB S p50, the disc's L as a ratio of the arms' aboral L, the rim's of the disc's.
    Returns dict"""
    from .. import calib
    alb = maps['albedo'].astype(np.float64) / 255.0
    L = lum(srgb_lin(alb))
    mx, mn = alb.max(-1), alb.min(-1)
    S = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    m = maps['masks'].astype(np.float64) / 255.0
    zones = dict(disc=(m[..., 2] > 0.60) & (m[..., 2] < 0.72), rim=m[..., 2] > 0.92, wall=m[..., 3] > 0.9)
    out = {k: dict(L=float(np.median(L[z])), S=float(np.median(S[z])), n=int(z.sum())) for k, z in zones.items()}
    b = calib.OCTOPUS_BARS
    rd = out['disc']['L'] / aboral_L
    rr = out['rim']['L'] / max(out['disc']['L'], 1e-9)
    out['disc_ratio'], out['rim_ratio'] = rd, rr
    flag = lambda v, lo, hi: 'ok' if lo <= v <= hi else ('LOW' if v < lo else 'HIGH')
    out['ok'] = all(flag(v, *bb) == 'ok' for v, bb in ((rd, b['disc_ratio']), (out['disc']['S'], b['disc_S']),
                                                       (rr, b['rim_ratio']), (out['rim']['S'], b['rim_S'])))
    log(f'[suckers] calib: disc L {out["disc"]["L"]:.3f} = x{rd:.2f} the arms\' aboral {aboral_L:.3f} '
        f'{flag(rd, *b["disc_ratio"])} (bar x{b["disc_ratio"][0]}-{b["disc_ratio"][1]}), S {out["disc"]["S"]:.2f} '
        f'{flag(out["disc"]["S"], *b["disc_S"])} (bar {b["disc_S"][0]}-{b["disc_S"][1]}); rim L x{rr:.2f} the disc '
        f'{flag(rr, *b["rim_ratio"])} (bar x{b["rim_ratio"][0]}-{b["rim_ratio"][1]}), S {out["rim"]["S"]:.2f} '
        f'{flag(out["rim"]["S"], *b["rim_S"])} (bar {b["rim_S"][0]}-{b["rim_S"][1]}); wall L {out["wall"]["L"]:.3f} '
        f'(x{out["wall"]["L"] / aboral_L:.2f} the aboral; the arms\' oral faces x1.3-1.65), S {out["wall"]["S"]:.2f}')
    return out


# ---------------------------------------------------------------------------------------------- Warp queries
@wp.kernel
def k_rays(mesh: wp.uint64, org: wp.array(dtype=wp.vec3), dirs: wp.array(dtype=wp.vec3), tmax: float,
           o_face: wp.array(dtype=wp.int32), o_bary: wp.array(dtype=wp.vec3)):
    """the first hit of each ray on the mesh: its face and (u, v, t) (-1 where none within tmax)"""
    i = wp.tid()
    q = wp.mesh_query_ray(mesh, org[i], dirs[i], tmax)
    if q.result:
        o_face[i] = q.face
        o_bary[i] = wp.vec3(q.u, q.v, q.t)
    else:
        o_face[i] = -1


@wp.kernel
def k_closest(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, o_face: wp.array(dtype=wp.int32),
              o_bary: wp.array(dtype=wp.vec3)):
    """the closest point of the mesh to each point: its face and (u, v, 0) (-1 beyond maxd)"""
    i = wp.tid()
    q = wp.mesh_query_point_no_sign(mesh, pts[i], maxd)
    if q.result:
        o_face[i] = q.face
        o_bary[i] = wp.vec3(q.u, q.v, 0.0)
    else:
        o_face[i] = -1


def mesh_rays(mesh, org, dirs, tmax):
    """(face, u, v, t) per ray against a wp.Mesh (face -1: no hit)"""
    n = len(org)
    f = wp.zeros(n, dtype=wp.int32)
    b = wp.zeros(n, dtype=wp.vec3)
    wp.launch(k_rays, dim=n, inputs=[mesh.id, wp.array(np.asarray(org, np.float32), dtype=wp.vec3),
                                     wp.array(np.asarray(dirs, np.float32), dtype=wp.vec3), float(tmax), f, b])
    bb = b.numpy().astype(np.float64)
    return f.numpy(), bb[:, 0], bb[:, 1], bb[:, 2]


def mesh_closest(mesh, pts, maxd):
    n = len(pts)
    f = wp.zeros(n, dtype=wp.int32)
    b = wp.zeros(n, dtype=wp.vec3)
    wp.launch(k_closest, dim=n, inputs=[mesh.id, wp.array(np.asarray(pts, np.float32), dtype=wp.vec3), float(maxd),
                                        f, b])
    bb = b.numpy().astype(np.float64)
    return f.numpy(), bb[:, 0], bb[:, 1]


def bary_eval(X, F, face, u, v):
    """a per-vertex quantity X (n, k) at hits (face, u, v): Warp's barycentrics (u on corner 0, v on corner 1)"""
    c = np.asarray(F, np.int64)[np.maximum(face, 0)]
    w = 1.0 - u - v
    return X[c[:, 0]] * u[:, None] + X[c[:, 1]] * v[:, None] + X[c[:, 2]] * w[:, None]


# ---------------------------------------------------------------------------------------------- crossings (stage 4)
@wp.func
def seg_tri(p0: wp.vec3, p1: wp.vec3, a: wp.vec3, b: wp.vec3, c: wp.vec3) -> int:
    """1 where the segment p0-p1 passes through the triangle's interior (Moller-Trumbore, ends excluded)"""
    d = p1 - p0
    e1 = b - a
    e2 = c - a
    h = wp.cross(d, e2)
    det = wp.dot(e1, h)
    if wp.abs(det) < 1.0e-20:
        return 0
    inv = 1.0 / det
    s = p0 - a
    u = inv * wp.dot(s, h)
    if u <= 0.0 or u >= 1.0:
        return 0
    q = wp.cross(s, e1)
    v = inv * wp.dot(d, q)
    if v <= 0.0 or u + v >= 1.0:
        return 0
    t = inv * wp.dot(e2, q)
    if t <= 1.0e-5 or t >= 1.0 - 1.0e-5:
        return 0
    return 1


@wp.kernel
def k_pair_cross(V: wp.array(dtype=wp.vec3), off: wp.array(dtype=int), lod: wp.array(dtype=int),
                 E: wp.array(dtype=wp.vec2i), e0: wp.array(dtype=int), ne: wp.array(dtype=int),
                 F: wp.array(dtype=wp.vec3i), f0: wp.array(dtype=int), nf: wp.array(dtype=int),
                 pa: wp.array(dtype=int), pb: wp.array(dtype=int), out: wp.array(dtype=int)):
    """per pair (a, b) and edge k of a: how many of b's triangles that edge passes through (summed into out[pair])"""
    p, k = wp.tid()
    a = pa[p]
    b = pb[p]
    la = lod[a]
    lb = lod[b]
    if k >= ne[la]:
        return
    e = E[e0[la] + k]
    P0 = V[off[a] + e[0]]
    P1 = V[off[a] + e[1]]
    n = int(0)
    for t in range(nf[lb]):
        f = F[f0[lb] + t]
        n += seg_tri(P0, P1, V[off[b] + f[0]], V[off[b] + f[1]], V[off[b] + f[2]])
    if n > 0:
        wp.atomic_add(out, p, n)


class Crossings:
    """two suckers CROSS in a pose when an edge of one passes through a triangle of the other (stage 3's probe measure,
    scratch_landing3/probe/sucker_cross_all.py, here exact over every candidate pair: centres closer than 0.66 x the
    summed d, any arms). S: build_mesh's mesh (V, J, W, inst; every sucker its template's topology), I its instances.
    skin(M) poses its vertices on skin matrices M (J, 4, 4) as three does (linear blend, float64); count(V) gives the
    pairs and the edges crossed per pair"""

    def __init__(self, S, I, device=None):
        self.I = I
        self.device = device or ('cuda:0' if wp.is_cuda_available() else 'cpu')
        inst = np.asarray(S['inst'])
        first = np.r_[True, inst[1:] != inst[:-1]]
        starts = np.nonzero(first)[0]
        self.ids = inst[starts]
        self.off = np.zeros(len(I['d']), np.int64)
        self.off[self.ids] = starts
        Es, Fs, e0, ne, f0, nf, ctr = [], [], [], [], [], [], {}
        for lod in range(max(LODS) + 1):
            T = template_lod(lod)
            El = np.unique(np.sort(np.concatenate([T['F'][:, [0, 1]], T['F'][:, [1, 2]], T['F'][:, [2, 0]]]), axis=1),
                           axis=0)
            e0.append(sum(len(x) for x in Es))
            f0.append(sum(len(x) for x in Fs))
            Es.append(El)
            Fs.append(T['F'])
            ne.append(len(El))
            nf.append(len(T['F']))
            ctr[lod] = int(np.nonzero(np.asarray(T['names'])[T['ring']] == 'X')[0][0])
        self.max_e = max(ne)
        self.ctr = self.off + np.array([ctr[int(l)] for l in I['lod']])
        dv = self.device
        arr = lambda x, t=int: wp.array(np.asarray(x, np.int32), dtype=t, device=dv)
        self.d = dict(off=arr(self.off), lod=arr(I['lod']), E=arr(np.concatenate(Es), wp.vec2i), e0=arr(e0),
                      ne=arr(ne), F=arr(np.concatenate(Fs), wp.vec3i), f0=arr(f0), nf=arr(nf))
        self.V0 = np.asarray(S['V'], np.float64)
        self.J = np.asarray(S['J'], np.int64)
        self.W = np.asarray(S['W'], np.float64)

    def skin(self, M):
        Vh = np.concatenate([self.V0, np.ones((len(self.V0), 1))], 1)
        out = np.zeros((len(Vh), 3))
        for c in range(self.J.shape[1]):
            w = self.W[:, c]
            m = w > 0.0
            out[m] += w[m, None] * np.einsum('nij,nj->ni', M[self.J[m, c]], Vh[m])[:, :3]
        return out

    def count(self, V, same_arm=False):
        """the pairs that cross in pose V: (pairs (k, 2) instance indices, edges crossed per pair, both ways);
        same_arm: only pairs on one arm (t26 D curls every arm at once, so its arms pass through each other)"""
        from scipy.spatial import cKDTree
        ids = self.ids
        C = V[self.ctr[ids]]
        D = self.I['d'][ids]
        pr = cKDTree(C).query_pairs(1.32 * float(D.max()), output_type='ndarray')
        if len(pr):
            a, b = ids[pr[:, 0]], ids[pr[:, 1]]
            keep = np.linalg.norm(C[pr[:, 0]] - C[pr[:, 1]], axis=1) < 0.66 * (self.I['d'][a] + self.I['d'][b])
            if same_arm:
                keep &= self.I['arm'][a] == self.I['arm'][b]
            P = np.column_stack([a[keep], b[keep]])
        else:
            P = np.zeros((0, 2), np.int64)
        if not len(P):
            return P, np.zeros(0, np.int64)
        dv, d = self.device, self.d
        dV = wp.array(V.astype(np.float32), dtype=wp.vec3, device=dv)
        tot = np.zeros(len(P), np.int64)
        for A, B in ((P[:, 0], P[:, 1]), (P[:, 1], P[:, 0])):
            o = wp.zeros(len(P), dtype=int, device=dv)
            wp.launch(k_pair_cross, dim=(len(P), self.max_e), device=dv,
                      inputs=[dV, d['off'], d['lod'], d['E'], d['e0'], d['ne'], d['F'], d['f0'], d['nf'],
                              wp.array(A.astype(np.int32), dtype=int, device=dv),
                              wp.array(B.astype(np.int32), dtype=int, device=dv), o])
            tot += o.numpy()
        hit = tot > 0
        return P[hit], tot[hit]


# ---------------------------------------------------------------------------------------------- placement
def arm_instances(inst, order, spec, geo_d=GEO_D, seed=26):
    """the GEOMETRIC suckers on all eight arms: the reference arm's plan instances (t10's instances.npz: suckers_p, n,
    d, s; suckers_geo when the sculpt plan marked them) rotated onto every arm by octopus_sculpt.arm_rotations (the
    arms identical: one plan rotated), those geo_mask picks. Each gets a frame (t1, n, t2: right-handed, t1 x n = t2)
    turned a seeded random azimuth about its axis (no two neighbours show the template's details in step), its LOD
    by size class, its arm's cage column (region 3 + column). Returns a dict of arrays"""
    from .octopus_sculpt import arm_rotations
    p, n, d, s = (np.asarray(inst[f'suckers_{k}'], np.float64) for k in ('p', 'n', 'd', 's'))
    geo = np.asarray(inst['suckers_geo'], bool) if 'suckers_geo' in inst else geo_mask(d, s, geo_d)
    rots = arm_rotations(order, spec)
    rng = np.random.default_rng(seed)
    P, N, T1, D, S_, ARM, IDX = [], [], [], [], [], [], []
    n = n / np.linalg.norm(n, axis=1, keepdims=True)
    for j, R in enumerate(rots):
        pj, nj = p[geo] @ R.T, n[geo] @ R.T
        radial = np.column_stack([pj[:, 0], np.zeros(len(pj)), pj[:, 2]])
        radial /= np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-12)
        t1 = radial - nj * (radial * nj).sum(1, keepdims=True)
        t1 /= np.linalg.norm(t1, axis=1, keepdims=True)
        t2 = np.cross(t1, nj)
        ph = rng.uniform(0.0, 2.0 * np.pi, len(pj))
        t1 = np.cos(ph)[:, None] * t1 + np.sin(ph)[:, None] * t2
        P.append(pj)
        N.append(nj)
        T1.append(t1)
        D.append(d[geo])
        S_.append(s[geo])
        ARM.append(np.full(len(pj), j))
        IDX.append(np.nonzero(geo)[0])
    P, N, T1 = np.concatenate(P), np.concatenate(N), np.concatenate(T1)
    T2 = np.cross(T1, N)
    D = np.concatenate(D)
    # (a geometric sucker just under geo_d, geo_mask's clean cut, takes the smallest class's LOD)
    return dict(p=P, n=N, t1=T1, t2=T2, d=D, s=np.concatenate(S_), arm=np.concatenate(ARM),
                idx=np.concatenate(IDX), lod=lod_of(np.maximum(D, geo_d)), scale=np.ones(len(D)))


def rim_clearance(I, scale=None):
    """per pair of suckers on one arm closer than 1.3 x their mean d: the clearance (m) between their rims' outer
    circles (radius 0.5 d x scale at the rim's outer side, RIM_C's height), measured across their mean axis. Returns
    (pairs (k, 2), clearance (k,))"""
    from scipy.spatial import cKDTree
    sc = I['scale'] if scale is None else scale
    c = I['p'] + I['n'] * (RIM_C[1] * I['d'])[:, None]
    pairs = cKDTree(c).query_pairs(1.3 * float(I['d'].max()), output_type='ndarray')
    if not len(pairs):
        return np.zeros((0, 2), np.int64), np.zeros(0)
    i, j = pairs[:, 0], pairs[:, 1]
    keep = (I['arm'][i] == I['arm'][j]) & (np.linalg.norm(c[i] - c[j], axis=1) < 1.3 * 0.5 * (I['d'][i] + I['d'][j]))
    i, j = i[keep], j[keep]
    ax = I['n'][i] + I['n'][j]
    ax /= np.linalg.norm(ax, axis=1, keepdims=True)
    v = c[j] - c[i]
    across = np.linalg.norm(v - ax * (v * ax).sum(1, keepdims=True), axis=1)
    return np.column_stack([i, j]), across - 0.5 * (I['d'][i] * sc[i] + I['d'][j] * sc[j])


def squash(I, margin=0.015, log=print):
    """per sucker a radial scale <= 1 so that no two rims on an arm come closer than margin x their mean d: the plan
    spaces a row at ~1.04 d and jitters sizes +-5 %, so a few neighbours' rims overlapped by up to 0.33 mm (they would
    interpenetrate as geometry); each pair too close shrinks both by the same factor, a sucker taking its worst pair's.
    Writes I['scale']"""
    pairs, clr = rim_clearance(I, np.ones(len(I['d'])))
    sc = np.ones(len(I['d']))
    if len(pairs):
        i, j = pairs[:, 0], pairs[:, 1]
        md = 0.5 * (I['d'][i] + I['d'][j])
        f = np.clip((clr + md - margin * md) / md, 0.5, 1.0)
        np.minimum.at(sc, i, f)
        np.minimum.at(sc, j, f)
    I['scale'] = sc
    _, clr2 = rim_clearance(I)
    log(f'[suckers] rims: {int((sc < 1).sum())} of {len(sc)} squashed (smallest x{sc.min():.3f}); rim clearance min '
        f'{clr.min() * 1e3:+.2f} mm before, {clr2.min() * 1e3:+.2f} mm after (bar >= {margin:.3f} d)')
    return clr, clr2


ELLIPSE_MAX = 0.045    # per sucker: an oval squeeze of up to 4.5 % across a random axis (shrink only, so the rims'
WOBBLE_MAX = 0.012     # clearance holds) and the lip's height wobbling up to +-0.012 d round it in three lobes: no two
                       # suckers the same turned copy (review 10-21: every sucker one stamped template read as a row of
                       # identical caps; live suckers are squeezed by their neighbours, their lips uneven)


def build_mesh(I, low, R=None, bury=BURY, log=print, seed=26):
    """the suckers in the BIND pose, one primitive: each sucker's LOD template scaled by d (its rim squash radial, its
    own oval squeeze and lip wobble: ELLIPSE_MAX, WOBBLE_MAX), framed, turned; its BASE CONFORMED to the arm's low: the
    base ring (B) sunk max(bury) under the skin beneath it and the fillet ring (W) the template's height over it (rays
    along -n onto the low), so the base follows the skin where it falls away across a curved arm; every vertex SKINNED
    as the skin is where its axis meets it (the low's weights interpolated on that triangle; low: dict(V, F, J, W) with
    the low's joints and weights, None for no skinning). Returns dict(V, N, TAN, UV, F, J, W, inst (per vertex), ring
    (per vertex: its name), lod_tris, burial (per B vertex, m), miss (rays that found no skin))"""
    from .. import bake as BK
    R = R or rings()
    mesh = wp.Mesh(points=wp.array(np.asarray(low['V'], np.float32), dtype=wp.vec3),
                   indices=wp.array(np.asarray(low['F'], np.int32).ravel(), dtype=wp.int32))
    out = {k: [] for k in ('V', 'N', 'TAN', 'UV', 'F', 'inst', 'ring')}
    off = 0
    lod_tris = {}
    tmpl = {}
    for lod in sorted(LODS):
        T = template_lod(lod, R)
        _, TAN = BK.low_frames(T['V'] * D_REF, T['F'], T['UV'], T['N'])
        tmpl[lod] = (T, TAN)
    rng = np.random.default_rng(seed + 1)
    n_s = len(I['d'])
    ell, phi = rng.uniform(0.3 * ELLIPSE_MAX, ELLIPSE_MAX, n_s), rng.uniform(0.0, np.pi, n_s)
    wob, psi = rng.uniform(0.0, WOBBLE_MAX, n_s), rng.uniform(0.0, 2.0 * np.pi, n_s)
    # the oval's short axis toward the nearest neighbour on the same arm (live cups are pressed along their row)
    from scipy.spatial import cKDTree
    dist, nb = cKDTree(I['p']).query(I['p'], k=min(4, n_s))
    for c in range(nb.shape[1] - 1, 0, -1):          # the nearest same-arm neighbour wins (written last)
        j = nb[:, c]
        on = I['arm'][j] == I['arm']
        v = I['p'][j] - I['p']
        phi = np.where(on, np.arctan2((v * I['t2']).sum(1), (v * I['t1']).sum(1)), phi)
    for i in np.argsort(I['lod'], kind='stable'):
        lod = int(I['lod'][i])
        if lod < 0:
            continue
        T, TAN = tmpl[lod]
        d, f = I['d'][i], I['scale'][i]
        M = np.column_stack([I['t1'][i], I['n'][i], I['t2'][i]])     # template x, y, z -> world
        rad = f * (1.0 - ell[i] * (0.5 + 0.5 * np.cos(2.0 * (T['th'] - phi[i]))))
        lip = np.isin(np.asarray(T['names'])[T['ring']], ['U', 'S', 'SC', 'C', 'I'])
        x, y, z = T['V'][:, 0] * rad, T['V'][:, 1] + wob[i] * np.sin(3.0 * T['th'] + psi[i]) * lip, T['V'][:, 2] * rad
        out['V'].append(I['p'][i] + d * (np.column_stack([x, y, z]) @ M.T))
        out['N'].append(T['N'] @ M.T)
        out['TAN'].append(np.column_stack([TAN[:, :3] @ M.T, TAN[:, 3]]))
        out['UV'].append(T['UV'])
        out['F'].append(T['F'] + off)
        out['inst'].append(np.full(len(T['V']), i))
        out['ring'].append(np.asarray(T['names'], object)[T['ring']])
        lod_tris[lod] = lod_tris.get(lod, 0) + len(T['F'])
        off += len(T['V'])
    S = {k: np.concatenate(v) for k, v in out.items()}
    inst = S['inst']
    n = I['n'][inst]
    d = I['d'][inst]
    # the conform: the skin under each base and fillet vertex, along the sucker's axis
    up = 0.6 * d + 0.005
    base = np.isin(S['ring'], ['B', 'W'])
    p0 = I['p'][inst]
    planar = S['V'] - n * ((S['V'] - p0) * n).sum(1, keepdims=True)
    planar[base] = confine_base(I, inst[base], planar[base])
    fc, u, v, t = mesh_rays(mesh, planar[base] + n[base] * up[base, None], -n[base], 0.05)
    hit = fc >= 0
    h = up[base] - t                                  # the skin's height over the tangent plane at the sucker's centre
    # the burial per sucker: the floor, plus the lift a bent arm gives a base on the low's triangles under it
    Fl, Vl = np.asarray(low['F'], np.int64), np.asarray(low['V'], np.float64)
    tri = Fl[np.maximum(fc, 0)]
    edge = np.max([np.linalg.norm(Vl[tri[:, a]] - Vl[tri[:, b]], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], 0)
    L_i = np.zeros(len(I['d']))
    np.maximum.at(L_i, inst[base][hit], edge[hit])
    bury_i = np.maximum(bury[0] * I['d'], bury[1]) + K_LIFT * L_i
    yb = np.where(S['ring'][base] == 'B', h - bury_i[inst[base]], h + R['W'][1] * d[base])
    yb = np.where(hit, yb, ((S['V'][base] - p0[base]) * n[base]).sum(1))
    S['V'][base] = planar[base] + n[base] * yb[:, None]
    burial = np.where(hit, h - yb, np.nan)[S['ring'][base] == 'B']
    # (stage 4) the conform moves each base vertex along its OWN sucker's axis, up to ~5 mm where the skin falls away,
    # and neighbouring axes splay: the planar confinement above no longer held, and same-row neighbours' buried base
    # strips crossed (plan suckers 14-16 at bind on four arms, 12-14 / 14-16 in the rest frames: the stage 3 probe's
    # "arm 0's (4,6)" and "arm 2's (2,4)"). So the conformed base rings are kept on their own side of each neighbour's
    # separating plane, in 3D
    S['V'][base], moved = separate_bases(I, inst[base], S['V'][base])
    log(f'[suckers] mesh: {len(I["d"])} suckers, {len(S["V"]):,} vertices, {len(S["F"]):,} triangles '
        f'({", ".join(f"LOD{k} {v:,}" for k, v in sorted(lod_tris.items()))}); base conformed on '
        f'{int(hit.sum()):,} of {int(base.sum()):,} vertices (skin under the base ring falls up to '
        f'{-np.nanmin(np.where(hit, h, np.nan)[S["ring"][base] == "B"]) * 1e3:.2f} mm below the tangent plane); the '
        f'low\'s triangles under the bases {L_i.min() * 1e3:.1f}-{L_i.max() * 1e3:.1f} mm long, burial '
        f'{bury_i.min() * 1e3:.2f}-{bury_i.max() * 1e3:.2f} mm; {int((moved > 0).sum()):,} base vertices pulled back '
        f'to their own side of a neighbour (up to {moved.max() * 1e3:.2f} mm)')
    S.update(lod_tris=lod_tris, burial=burial, miss=int((~hit).sum()), bury_i=bury_i, tri_len=L_i)
    if low.get('J') is not None:
        S['J'], S['W'], S['skin_miss'] = skin_weights(S, I, low, mesh)
    return S


def confine_base(I, inst, planar, margin=0.004, k=8):
    """the base rings (B, W) of each sucker kept inside its own cell: per vertex, its radial reach toward every
    neighbour on the arm (within 1.4 x their mean d) cut at their size-weighted bisector less margin x d, never inside
    the rim's outer radius (no undercut). Same-row neighbours sit 0.97-1.05 d apart, inside two base radii (~1.1 d):
    their base strips crossed above the skin as small wedges at each pair's junction (t26 F, s 0.45 from below).
    planar: the vertices projected on their sucker's tangent plane (the conform's starting points)"""
    from scipy.spatial import cKDTree
    P, Nn, D, sc = I['p'], I['n'], I['d'], I['scale']
    nk = min(k, len(P))
    dist, nbr = cKDTree(P).query(P, k=nk)
    p0 = P[inst]
    n = Nn[inst]
    rv = planar - p0
    t = np.linalg.norm(rv, axis=1)
    e = rv / np.maximum(t, 1e-12)[:, None]
    floor = 0.985 * 0.5 * D[inst] * sc[inst]
    for c in range(1, nk):
        j = nbr[inst, c]
        ok = (I['arm'][j] == I['arm'][inst]) & (dist[inst, c] < 0.7 * (D[inst] + D[j]))
        uvec = P[j] - p0
        uvec = uvec - n * (uvec * n).sum(1, keepdims=True)
        L = np.linalg.norm(uvec, axis=1)
        uvec = uvec / np.maximum(L, 1e-12)[:, None]
        cos = (e * uvec).sum(1)
        lim = (L * D[inst] / (D[inst] + D[j]) - margin * D[inst]) / np.maximum(cos, 1e-6)
        t = np.where(ok & (cos > 0.05), np.minimum(t, lim), t)
    t = np.maximum(t, floor)
    return p0 + e * t[:, None]


SEP_MARGIN = 0.02      # the conformed base rings stay this share of d (each sucker's own) behind the plane separating
                       # them from a neighbour: the slack the poses take (the rest frames squeeze the root suckers'
                       # bases together under the skin)


def separate_bases(I, inst, V, margin=SEP_MARGIN, k=8):
    """the CONFORMED base vertices V (B and W rings: inst their suckers) kept on their own side of the plane separating
    each sucker from every neighbour (any arm, centres closer than 0.7 x the summed d): through the size-weighted point
    between the two centres, normal to the line joining them across their mean axis; a vertex past it less margin x d
    is moved back along the plane's normal (under the skin for B; along it for W). Returns (V, the distance each moved)"""
    from scipy.spatial import cKDTree
    P, Nn, D = I['p'], I['n'], I['d']
    nk = min(k, len(P))
    dist, nbr = cKDTree(P).query(P, k=nk)
    V = np.array(V, np.float64)
    moved = np.zeros(len(V))
    p0, ni, di = P[inst], Nn[inst], D[inst]
    for c in range(1, nk):
        j = nbr[inst, c]
        ok = dist[inst, c] < 0.7 * (di + D[j])
        ax = ni + Nn[j]
        ax /= np.linalg.norm(ax, axis=1, keepdims=True)
        u = P[j] - p0
        u = u - ax * (u * ax).sum(1, keepdims=True)
        u /= np.maximum(np.linalg.norm(u, axis=1, keepdims=True), 1e-12)
        m = p0 + (P[j] - p0) * (di / (di + D[j]))[:, None]
        over = ((V - m) * u).sum(1) + margin * di
        fix = ok & (over > 0.0)
        V[fix] -= u[fix] * over[fix, None]
        moved[fix] += over[fix]
    return V, moved


def skin_weights(S, I, low, mesh=None, k=4):
    """each sucker vertex weighted as the arm's skin is where the sucker's axis through the vertex meets it (the low's
    four influences interpolated on that triangle, the top k cut continuously, rig.limit_influences), the closest
    skin point where that ray misses. Returns (J, W, misses)"""
    from .. import rig as RG
    if mesh is None:
        mesh = wp.Mesh(points=wp.array(np.asarray(low['V'], np.float32), dtype=wp.vec3),
                       indices=wp.array(np.asarray(low['F'], np.int32).ravel(), dtype=wp.int32))
    inst = S['inst']
    n = I['n'][inst]
    up = 0.6 * I['d'][inst] + 0.005
    fc, u, v, t = mesh_rays(mesh, S['V'] + n * up[:, None], -n, 0.06)
    miss = fc < 0
    if miss.any():
        fc2, u2, v2 = mesh_closest(mesh, S['V'][miss], 0.05)
        fc[miss], u[miss], v[miss] = fc2, u2, v2
    Jl, Wl = np.asarray(low['J'], np.int64), np.asarray(low['W'], np.float64)
    nJ = int(Jl.max()) + 1
    Wd = np.zeros((len(fc), nJ))
    c = np.asarray(low['F'], np.int64)[np.maximum(fc, 0)]
    for corner, b in ((0, u), (1, v), (2, 1.0 - u - v)):
        for slot in range(Jl.shape[1]):
            np.add.at(Wd, (np.arange(len(fc)), Jl[c[:, corner], slot]), b * Wl[c[:, corner], slot])
    J, W = RG.limit_influences(Wd, k)
    return J, W, int(miss.sum())


def budget(I, log=print):
    """triangles and vertices per LOD and in all, for every sucker placed (all eight arms)"""
    rows = {}
    for lod in sorted(LODS):
        m = I['lod'] == lod
        tr, vx = lod_cost(lod)
        rows[lod] = dict(count=int(m.sum()), tris_each=tr, verts_each=vx, tris=int(m.sum()) * tr,
                         verts=int(m.sum()) * vx,
                         d_mm=(float(I['d'][m].min() * 1e3), float(I['d'][m].max() * 1e3)) if m.any() else (0, 0))
    tot = sum(r['tris'] for r in rows.values())
    verts = sum(r['verts'] for r in rows.values())
    for lod, r in rows.items():
        log(f'[suckers] LOD{lod}: {r["count"]} suckers d {r["d_mm"][0]:.1f}-{r["d_mm"][1]:.1f} mm x {r["tris_each"]} '
            f'tris ({r["verts_each"]} verts) = {r["tris"]:,} tris')
    log(f'[suckers] all eight arms: {tot:,} triangles, {verts:,} vertices (budget 80,000 triangles)')
    return rows, tot, verts


# ---------------------------------------------------------------------------------------------- the arm bake's occluders
def occluder_bounds(I, pad=0.0015):
    """the voxel grid's extra activation round every geometric sucker (voxel.SparseSDF extra=): a sphere over its body
    (centre 0.15 d up its axis, radius 0.62 d), so its occluder values (occluder_values) exist above the band"""
    return I['p'] + I['n'] * (0.15 * I['d'])[:, None], 0.62 * I['d'] * I['scale'] + pad


@wp.kernel
def k_occ(ijk: wp.array(dtype=wp.vec3i), origin: wp.vec3, vs: float, val: wp.array(dtype=wp.float32),
          grid: wp.uint64, C: wp.array(dtype=wp.vec3), RX: wp.array(dtype=wp.vec3), RY: wp.array(dtype=wp.vec3),
          RZ: wp.array(dtype=wp.vec3), D: wp.array(dtype=wp.float32), SC: wp.array(dtype=wp.float32), reach: float,
          count: int, node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
          node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), out: wp.array(dtype=wp.float32)):
    """per voxel: min(the skin's value, the nearest suckers' bodies): each sucker's distance as the template body's
    exact revolve distance in its frame at unit diameter (a radial squash read as a smaller radius: conservative),
    times its d"""
    t = wp.tid()
    c = ijk[t]
    p = origin + wp.vec3(float(c[0]), float(c[1]), float(c[2])) * vs
    best = val[t]
    q = wp.hash_grid_query(grid, p, reach)
    k = int(0)
    while wp.hash_grid_query_next(q, k):
        w = p - C[k]
        dk = D[k]
        sk = SC[k]
        loc = wp.vec3(wp.dot(w, RX[k]) / sk, wp.dot(w, RY[k]), wp.dot(w, RZ[k]) / sk) / dk
        f = S_.sd_revolve(loc, 0, count, wp.vec3(0.0, 0.0, 0.0), wp.vec3(0.0, 1.0, 0.0), node_p, node_n, node_r,
                          node_h) * dk * sk
        best = wp.min(best, f)
    out[t] = best


def occluder_values(G, I, log=print):
    """the arm bake's OCCLUDER field on the same voxel topology: min(G's skin value, the geometric suckers' bodies)
    per voxel (bake.py's AO and cavity rays read it as field.val_occ; its surface search keeps G.val, so the skin's
    normal and height carry no sucker relief while its AO and cavity take their contact shade). Returns a wp.array"""
    import time
    t0 = time.time()
    prog = body_occluder_program()
    dev = prog.device()
    count = int(prog.par[0][1])
    Mx = np.ascontiguousarray(I['t1'], np.float32)
    My = np.ascontiguousarray(I['n'], np.float32)
    Mz = np.ascontiguousarray(I['t2'], np.float32)
    C = np.ascontiguousarray(I['p'], np.float32)
    reach = float(0.72 * I['d'].max() + 2.0 * G.vs)
    grid = wp.HashGrid(128, 128, 128)
    Cd = wp.array(C, dtype=wp.vec3)
    grid.build(Cd, reach)
    out = wp.zeros(G.n, dtype=wp.float32)
    wp.launch(k_occ, dim=G.n, inputs=[G.ijk, wp.vec3(*np.asarray(G.origin, np.float32)), float(G.vs), G.val, grid.id,
                                      Cd, wp.array(Mx, dtype=wp.vec3), wp.array(My, dtype=wp.vec3),
                                      wp.array(Mz, dtype=wp.vec3), wp.array(I['d'].astype(np.float32), dtype=float),
                                      wp.array(I['scale'].astype(np.float32), dtype=float), reach, count,
                                      dev['node_p'], dev['node_n'], dev['node_r'], dev['node_h'], out])
    wp.synchronize()
    a, b = G.val.numpy(), out.numpy()
    log(f'[suckers] occluder field: {int((b < a - 1e-7).sum()):,} of {G.n:,} voxels take a sucker '
        f'({len(C)} suckers) in {time.time() - t0:.1f}s')
    return out


# ---------------------------------------------------------------------------------------------- export
def skin_colours(I, low, albedo, display=None, n=12, log=print):
    """per sucker its COLOR_0: rgb the arm's skin colour round its base (the low's albedo sampled at n points on the
    skin 0.62 d out round its axis, linear, averaged), alpha the display's dark bands and blotches there (B of the
    display pack). low: dict(V, F, UV (forge v-up), face_set per triangle); albedo / display: {set name: image}"""
    mesh = wp.Mesh(points=wp.array(np.asarray(low['V'], np.float32), dtype=wp.vec3),
                   indices=wp.array(np.asarray(low['F'], np.int32).ravel(), dtype=wp.int32))
    a = np.arange(n) * 2.0 * np.pi / n
    m = len(I['d'])
    rad = 0.62 * I['d'] * I['scale']
    pts = (I['p'][:, None] + rad[:, None, None] * (np.cos(a)[None, :, None] * I['t1'][:, None]
                                                   + np.sin(a)[None, :, None] * I['t2'][:, None])).reshape(-1, 3)
    nn = np.repeat(I['n'], n, axis=0)
    up = np.repeat(0.6 * I['d'] + 0.005, n)
    fc, u, v, t = mesh_rays(mesh, pts + nn * up[:, None], -nn, 0.05)
    ok = fc >= 0
    uv = bary_eval(np.asarray(low['UV'], np.float64), low['F'], fc, u, v)
    fs = np.asarray(low['face_set'])[np.maximum(fc, 0)]
    rgb = np.zeros((len(fc), 3))
    dk = np.zeros(len(fc))

    def sample(img, uv_):
        hh, ww = img.shape[:2]
        x = np.clip(uv_[:, 0] * ww - 0.5, 0, ww - 1)
        y = np.clip((1.0 - uv_[:, 1]) * hh - 0.5, 0, hh - 1)
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        x1, y1 = np.minimum(x0 + 1, ww - 1), np.minimum(y0 + 1, hh - 1)
        fx, fy = (x - x0)[:, None], (y - y0)[:, None]
        im = img.astype(np.float64).reshape(hh, ww, -1)
        return ((im[y0, x0] * (1 - fx) + im[y0, x1] * fx) * (1 - fy) + (im[y1, x0] * (1 - fx) + im[y1, x1] * fx) * fy)
    for name, img in albedo.items():
        s = ok & (fs == name)
        if s.any():
            rgb[s] = srgb_lin(sample(img, uv[s])[:, :3] / 255.0)
            if display is not None and name in display:
                dk[s] = sample(display[name], uv[s])[:, 2] / 255.0
    w = ok.reshape(m, n).astype(np.float64)
    col = (rgb.reshape(m, n, 3) * w[..., None]).sum(1) / np.maximum(w.sum(1), 1)[:, None]
    alpha = (dk.reshape(m, n) * w).sum(1) / np.maximum(w.sum(1), 1)
    log(f'[suckers] skin colours: {int(ok.sum())} of {len(ok)} samples on the skin; median rgb '
        f'{np.round(np.median(col, axis=0), 3)} (linear), dark band p50 {np.median(alpha):.2f}')
    return np.column_stack([col, alpha]).astype(np.float32)


def add_to_glb(g, mesh_index, S, colours, maps, tx, wall_ref, name='octopus_suckers'):
    """the suckers as their OWN PRIMITIVE of the creature's skinned mesh (gltf.GLB g, mesh mesh_index: the same skin,
    its own vertex set: POSITION, NORMAL, TANGENT, TEXCOORD_0 (glTF v down), COLOR_0 per sucker, JOINTS_0, WEIGHTS_0)
    with its own material: the template's maps (tx(img, kind) -> texture index: t13's writer, PNG for data, JPEG for
    colour), the masks in KHR_materials_volume's thickness slot as the skin's. Returns (primitive index, material)"""
    f32 = lambda a: np.ascontiguousarray(a, np.float32)
    col = f32(colours[S['inst']])
    attrs = {'POSITION': g.accessor(f32(S['V']), 'VEC3', 34962, minmax=True),
             'NORMAL': g.accessor(f32(S['N']), 'VEC3', 34962),
             'TANGENT': g.accessor(f32(S['TAN']), 'VEC4', 34962),
             'TEXCOORD_0': g.accessor(f32(np.column_stack([S['UV'][:, 0], 1.0 - S['UV'][:, 1]])), 'VEC2', 34962),
             'COLOR_0': g.accessor(col, 'VEC4', 34962),
             'JOINTS_0': g.accessor(np.ascontiguousarray(S['J'], np.uint16), 'VEC4', 34962),
             'WEIGHTS_0': g.accessor(f32(S['W']), 'VEC4', 34962)}
    mat = g.material(name, base=tx(maps['albedo'], 'colour'), normal=tx(maps['normal'], 'data'),
                     orm=tx(maps['orm'], 'colour'), volume_tex=tx(maps['masks'], 'data'), extras=dict(
        bestiary='sucker', recipe='octopus', part='geometric suckers, one stacked template (octopus_suckers.py)',
        slots='masks ride KHR_materials_volume thicknessTexture',
        masks_channels='R thin, G ventral, B sucker parts (rim 1, disc .66, cup .33), A the wall (the arm skin)',
        color0='rgb the arm skin colour round the base (linear), a its dark band display',
        wall_ref=[round(float(x), 5) for x in wall_ref]))
    prims = g.j['meshes'][mesh_index]['primitives']
    prims.append({'attributes': attrs, 'indices': g.accessor(np.ascontiguousarray(S['F'], np.uint32).reshape(-1),
                                                             'SCALAR', 34963), 'material': mat, 'mode': 4})
    return len(prims) - 1, mat


# ---------------------------------------------------------------------------------------------- the pipeline's hooks
def part_dir(oct_dir):
    """the template's outputs beside the creature's (work/bestiary/octopus -> work/bestiary/octopus_suckers)"""
    import os
    return os.path.join(os.path.dirname(os.path.abspath(oct_dir)), 'octopus_suckers')


def plan_occluders(plan, order, spec, log=print):
    """t10's hook: the geometric suckers of a plan made with sucker_geo_d (its inst['suckers'] carries 'geo'), on all
    eight arms, their rims squashed apart: the instances occluder_bounds and occluder_values read"""
    I = arm_instances({f'suckers_{k}': v for k, v in plan.inst['suckers'].items()}, order, spec)
    squash(I, log=log)
    return I


def baked_only(inst):
    """t11's hook: the instances with the geometric suckers left out of the sucker arrays (their own mesh carries their
    colour: the skin under them is hidden, round them it is the arm's oral skin)"""
    geo = np.asarray(inst['suckers_geo'], bool) if 'suckers_geo' in inst else geo_mask(inst['suckers_d'],
                                                                                         inst['suckers_s'])
    return {k: (np.asarray(v)[~geo] if k.startswith('suckers_') else v) for k, v in inst.items()}


def part_mesh(low, order, spec, oct_dir, log=print):
    """the suckers in the bind pose from t10's instances on a creature's low (dict V, F; with J and W they are
    skinned): returns (instances, mesh)"""
    import os
    inst = dict(np.load(os.path.join(oct_dir, 'instances.npz')))
    I = arm_instances(inst, order, spec)
    squash(I, log=log)
    return I, build_mesh(I, low, log=log)


def part_maps(oct_dir):
    """the template's texture set (t26 A writes it) and its mean wall colour"""
    import os
    from PIL import Image
    d = part_dir(oct_dir)
    maps = {k: np.asarray(Image.open(os.path.join(d, f'T_suckers_{k}.png'))) for k in ('albedo', 'normal', 'orm',
                                                                                         'masks')}
    return maps, np.load(os.path.join(d, 'wall_ref.npy'))


def lookdev_part(low, order, spec, oct_dir, log=print):
    """t11's hook: the suckers as a lookdev part: (mesh dict V, F, UV (the forge's v up, as t11's own lists), N, TAN;
    the lookdev material)"""
    I, S = part_mesh(dict(V=low['V'], F=low['F']), order, spec, oct_dir, log=log)
    maps, _ = part_maps(oct_dir)
    mat = dict(albedo=maps['albedo'], normal=maps['normal'], ao=maps['orm'][..., 0], rough=maps['orm'][..., 1],
               metal=maps['orm'][..., 2], ior=1.33)
    return dict(V=S['V'], F=S['F'], UV=S['UV'], N=S['N'], TAN=S['TAN']), mat


def export_part(g, mesh_index, low, order, spec, oct_dir, tx, log=print):
    """t13's hook: the suckers' primitive added to the creature's glb (low: dict V, F, UV, face_set, J, W: the
    creature's low with the joints and weights it ships), coloured from the creature's own maps. Returns its index"""
    import os
    from PIL import Image
    I, S = part_mesh(low, order, spec, oct_dir, log=log)
    maps, wall_ref = part_maps(oct_dir)
    img = lambda n: np.asarray(Image.open(os.path.join(oct_dir, n)))
    colours = skin_colours(I, low, {'head': img('T_head_albedo.png'), 'arms': img('T_arms_albedo.png')},
                           {'head': img('T_head_display.png'), 'arms': img('T_arms_display.png')}, log=log)
    pi, _ = add_to_glb(g, mesh_index, S, colours, maps, tx, wall_ref)
    log(f'[suckers] exported: primitive {pi}, {len(S["V"]):,} vertices, {len(S["F"]):,} triangles')
    return pi
