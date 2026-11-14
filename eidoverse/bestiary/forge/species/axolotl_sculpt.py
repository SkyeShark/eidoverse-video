"""AX6 (work/bestiary/research/AXOLOTL_PLAN.md §5.9 and §11's row): THE AXOLOTL'S SCULPT PLAN (tier S: about 1 mm x4
and up, or outline-changing) on the accepted clay, and the GRIDS of its voxel high. The step script is
work/bestiary/tests/ax06_high.py; AX7's bake rebuilds the same grids through sculpt_grid().

Every stroke is placed on the CLAY (the analytic block-out: the program AX2-AX5 used) in x4 metres, planned before any
grid exists, so a grid's band can grow round a stroke that needs it (octopus_sculpt.Plan.bounds). The plan's container
is octopus_sculpt.Plan: each batch is unioned exactly within itself, then added or carved with its fillet; adds first,
carves after, the nares last; then Plan.apply's smooth (1, 0.5) and relevel. The RIGHT side is every left stroke
mirrored exactly (x -> -x), so the body (unique: both sides bake) is symmetric and the left limbs' bake is right for
their stacked right copies. The rami and the fins take no strokes: the rami's stalks are smooth (their filaments are
instances), and the fins' high is the clay's shell, whose root fillet and rounded margin are already the clay's.

THE BASE (high_clay, then sculpt_grid's order: the pillows, then the plan):
  THE SWEEPS SAMPLED DENSER (high_clay): a clay sweep's centreline is the polyline through its nodes (sdf.sd_sweep:
    C(s) piecewise linear, the radius linear between nodes), so a bent limb carries a facet at every node: AX6's first
    look in a wet light found BANDS 2 mm x4 apart round the knee and the elbow (CLAY node_mm 0.5 mm life). The high's
    clay is the same program with the limbs' and the rami's sweeps on the same Catmull-Rom curves sampled REFINE times
    denser (the polyline's sag 16 x smaller; the stacks' contract re-measured on it by ax06's gate). The body (a GRID of
    caudate's limit mesh), the eyes and the fins are the clay's own.
  THE COSTAL PILLOWS (pillows; plan §5.9's costal grooves): AX0b's reading of p23 and p19 is "narrow creases between
    rounded segments: each costal segment a convex pillow and the groove a narrow V-crease between two pillows" (the
    crease's dark band 0.05 of the spacing on p23). Round carve strokes cannot make that (a tube sunk past its radius
    undercuts: the first draft's keyhole slot), so the trunk's field is DISPLACED along its normal by an arch per
    segment between the spec's groove stations, sqrt(4u(1 - u)) - pi/4 (mean zero: the low, fitted to the clay, stays
    the mean surface; the crease, a cusp between two convex arcs, dips 0.785 h, the crowns rise 0.215 h), h
    GROOVE['h'] on the flank, fading to nothing under the dorsal fin's root, to GROOVE['floor'] on the belly (p16:
    "faint transverse costal lines on the belly"), near each limb's footprint ring, and over the outer segment past
    the first and the last groove. A pure function of position, so every grid applies the same field.
  THE LIP LOBES (lobes; LIP's note): p13's swollen mouth corners, a smooth bump displaced outward over the tangential
    distance from a centre just over each commissure (a ball, the third try, read as a ball glued on).

THE STROKES (plan §5.9's S tier; sizes in life mm, [E] where the plan or the photos give only a shape):
  GULAR FOLD (the AX4 gular loop at the gill line, s 0.176; p16: "a clear transverse gular fold ... level with the gill
    bases"): the throat skin in front overhanging the skin behind: a ridge just ahead of the loop, a crease just behind
    it, both fading where the loop meets the gill sockets.
  LIP CORNERS: p13's "smile", the upper lip a broad ledge over the set-back lower lip (the clay's creased mouth line
    and tucked lower lip), swelling at each corner into a rounded LOBE ~5-6 mm across: THE BASE's lip lobes (no
    stroke).
  THE EYE (p13 / p14 / p15 / p18: a lidless ball PROUD ALL ROUND in a soft, broad rim of skin, its outline round).
    AX6's first look found the clay's opening a D (a shelf of skin over the ball's lower part); then its eye sections
    found the ball in a SOCKET behind and below (the skin 1.3-1.6 mm life over the edge plane there), and check:ax5 found
    the high's skin climbing 0.13-0.18 mm up the ball in front of the low's edge ring all round (the lip torus crossed
    the ball at the ring and its fillets climbed it), a crisp narrow lip where the photos have a soft broad rim. AX7's eye
    round fixed the socket where it started: the SPEC's eye axis turned toward the head's local normal and caudate's
    edge plane moved out (rig.eye_axis, caudate FEATURES eye out), so the clay itself now carries an EVEN soft collar
    (+0.06..+0.24 mm life over the edge plane at 1.05-1.3 r_e all round). The high's eye (eye_strokes) keeps that collar
    as the rim and lands the skin ON the ring: a FUNNEL carve (a ROUND cone, apex on the axis behind the ball,
    EYE['alpha'], cut above the ball's pole) whose wall passes outside the edge ring by the reach of the ball's fillet
    (EYE['land'] x k_ball), its rim filleted into the collar (k_funnel), so that when the BALL is re-added from air
    (k_ball: the meniscus) its fillet ends at the ring itself; the low's edge ring is then exactly where the skin leaves
    the ball. No lip torus (it made the crisp ring). Their order in the plan: the funnel among the carves, then the
    ball. The funnel takes no activation spheres (sculpt_grid): its new surface lies within the band.
  NARES (caudate's dimpled vertex, found as the deepest point of the clay's dimple): round conical pits, p13's small
    round dark openings, carved last along the clay's normal.
  VENT (spec stations.vent 0.552 = the cloaca's posterior end; p01's male): the cloacal MOUND on the ventral midline
    ahead of the ventral fin's start (p01 at full size: ~8 mm long, ~2 mm below the belly line on that breeding male),
    its slit carved along the midline, small papillae along the slit's lips.
  AXILLA AND GROIN FOLDS: a broad low swelling on the body above each limb's footprint over its dorsal arc (the skin
    folding over the sprawled limb's top) and a shallow soft crease below it, OFF the footprint ring, which is the root
    band's UV seam (AX7b: FOLD's note).
  DIGIT TIPS (plan §5.9, S / T): AX7b, no stroke (TIP's note: the digits taper to a rounded tip in the clay; the
    round-6 ball read as balls on sticks).
GRIDS (plan §5.9, the wolf's §4.7 pattern: one SparseSDF per set with a keep region, every grid applies the whole plan,
so the relief agrees where two grids meet; the bake bakes each (texture set, grid) pair over its own triangles and
merges by coverage): FINE 0.25 mm x4 over the head, the neck and its gill sockets, the left limbs, r1's stalk and the
rami's caps, the fins (plan §15 item 5: the fin margins' 0.48 mm x4 half-thickness is 4 voxels across here, 3 on the
coarse grid) and the left eyeball (the EYE set); COARSE 0.30 mm x4 over the trunk and the tail. Only PRIMARIES are kept
(AX5: the stacked copies are never baked; their clay stays in the hybrid field, so their occlusion still reaches the
skin round them).
THE FILAMENT TEMPLATES (plan §5.7): each its own small grid, its high a sweep of the template's own curve and radius
(axolotl_gills.template's) built at D_REF (octopus_suckers' idea: the forge's constants hold at a creature's scale, and
the maps are scale-free).
"""
import time

import numpy as np
import warp as wp

from .. import voxel as VX
from ..voxel import STROKE_CONE
from .octopus_sculpt import Plan

wp.set_module_options({'enable_backward': False})    # forward-only kernels (render_wet's): no adjoint code to compile

MIRROR = np.array([-1.0, 1.0, 1.0])
# the high's limb and ramus sweeps: the clay's curves sampled this much denser (THE BASE)
REFINE = 4
# the costal pillows (THE BASE): h the crown-to-crease height (life mm) on the flank (the spec's groove_depth 0.3-0.5
# [E]; p23 "shallow", p19's old male "deep": A1 is a young adult, so the range's lower part); the dorsal fade (deg off
# the dorsal midline: 0 under the fin's root .. 1), the ventral fade to `floor` at the ventral midline, the limb fade
# (life mm from the footprint ring: 0 .. 1), and the outer segment past the first and the last groove
GROOVE = dict(h=0.35, dorsal=(18.0, 40.0), ventral=(125.0, 180.0), floor=0.25, limb=(0.5, 2.5))
# the gular fold (life mm): the ridge's tube radius, its rise, how far ahead of the loop; the crease's radius (at least
# its depth: no undercut), its depth, how far behind; the fillet; the fade over each end's share of the loop
GULAR = dict(ridge_r=0.60, rise=0.22, ahead=0.25, crease_r=0.34, depth=0.30, behind=0.25, k=0.25, fade=0.25,
             step=0.25)
#   (AX6's first run: ridge_r 0.40, k 0.15 read as a thin welt from the side; p16's fold is a broad lip of throat skin)
# the lip corners (p13's pads): the tube's radius from the run's front end to the commissure, its rise over the clay at
# the commissure (life mm; 0 at the run's front end, full over its last 30 %, fading over `past` beyond the corner), its
# centre `up` x its radius above the mouth line (so its lowest side hangs (1 - up) r under the line, over the tucked
# lower lip)
LIP = dict(R=2.2, rise=0.0, up=0.30, ahead=0.9)
#   (AX7c, 10-30: rise 1.0 -> 0, OFF. The lobes are now the CLAY's (heads/caudate.py: on the lower lip's rows under the
#   ends of the smile, ~0.32 HW off the midline), so the low (AX4) carries them; this displacement lived only in the
#   high's normals, near the commissure on the side, and read as a dot in the engine beside p13 / p14 / p15's fleshy
#   lobes. With rise 0 no voxel moves and no probe is laid)
# THE LOBES' RIMS (AX7c): the clay's lobe reads as a pale patch in the engine, where p14 / p15's are blisters outlined by
# a dark line round their lower edge. A soft carve under each lobe, an arc half_w along the line either way of its
# centre and `drop` under the margin (measure_lobes.py: the lobe 5.2 mm wide, its lowest point 2.8 mm under the margin),
# fading into the margin at both ends over `fade` of sin(angle); radius and depth life mm, so the bake's normal, cavity
# and occlusion carry the outline the low's few rows cannot
LOBE = dict(half_w=3.0, drop=2.7, rim_r=0.34, depth=0.14, k=0.10, step=0.22, fade=0.22, bead_half_k=0.95, bead_drop=2.2,
            bead_rim=False)
#   (AX8, the BEADS (caudate's lobe record's beads, two a side): a rim under EACH bead, half_w its own half-length x
#   bead_half_k, its deepest bead_drop under the margin (ax8_notes/measure_beads.py: their lowest points 2.44 / 2.65 mm
#   under it at 0.2 mm of stand-off; the rim just inside), so the two arcs meet in a V between the beads at the margin:
#   p15 / p14's beads each outlined by a dark line, the crease between them included)
#   (the AX8 check, 11-01: bead_rim False, NO rim under the beads. The two arcs crumpled them: in the high (the plan
#   rebuilt stroke for stroke, ax8_check/bead_probe.py) looped grooves over draped folds where the clay has two round
#   bumps, and in the engine dark wire-loop creases through the first bead, read as crumpled foil beside p14 / p15's
#   round beads. Without the arcs the high hangs two round bulbs under the margin from 3/4 and the engine shows two
#   smooth lobes with a soft V between (ax8_check/out/trial_close.png, trial_mouth_*.png, r2_trial_leu_front.png);
#   the trial chain (ax8_check/fixrun.py) passed every gate, its seams and stacks equal to the line, the mouth's wrong
#   texels 511 -> 403, the audit 114 -> 112 clusters. A record without beads keeps AX7c's one rim under its lobe)
#   (AX7b, 10-30: `ahead` mm along the lip run before the commissure, where the lobes hang over the lower lip in front of
#   each corner; with the clay's smile the corner itself turns up behind the lobe. Round 6: R 2.8, rise 0.65, over the
#   commissure; AX7b's first build R 3.0, rise 0.75, 1.5 mm ahead did not read in the engine beside p14 / p15's round
#   fleshy lobes at the corners: smaller, taller, nearer the corner)
#   (AX6's runs 1-3: a tube along the run, however wide, read as a bar laid on the lip, and a ball as a ball glued on
#   (a 2.6 mm ball rising 0.45 meets the skin at ~34 deg, which no fillet hides; a wider ball's bounding sphere would
#   activate its whole interior). p13 at 2x: the upper lip is a broad ledge across the front (the clay has it: the
#   creased mouth line, the lower lip tucked) and at each corner it swells into a rounded LOBE ~5-6 mm across, bulging
#   forward and hanging over the set-back lower lip. So the lobe is a DISPLACEMENT, as the pillows: a bump
#   rise (1 - (d / R)^2)^2 over the tangential distance d from a centre `up` mm over the commissure)
# the eye (the module docstring's THE EYE): the funnel's half-angle (deg off the eye's axis), its fillet and how far
# above the higher of the skin round the eye and the ball's pole it reaches (life mm); the radius (over the visible
# eye's) where that skin is read
# (the AX4 cage's crest ring); the funnel wall's offset outside the edge ring in units of the ball fillet's reach
# (land); the ball's fillet when it is added back (life mm); the angles round the axis
EYE = dict(alpha=35.0, k_funnel=0.10, out=0.4, collar_at=1.30, land=0.45, k_ball=0.10, n=48)
#   (AX6, on the old clay: 45 deg cut a wide bowl with a hard rim where the cheek stood 1.3 mm over the edge plane, 20
#   deg kept the cheek as a steep wall; annulus smooths could not remove the dark crevice behind the eye, the socket
#   itself (the clay's placement). AX7's eye round, on the clay's even collar, the round cone measured on the eye-only
#   harness (work/bestiary/axolotl/ax7_notes/eye_high.py, on ax06's lattice and plan; NOTES.md has the sweeps): where
#   the skin first covers the ball, against the ring, moves 0.1 mm per unit of `land`, and k_funnel 0.25 bevelled the
#   cut's rim below the edge plane (a groove: the skin at 1.05 r_e -0.02..-0.08) where 0.10 keeps it on it. On caudate
#   ax2-g's clay (the eye's inner rings at even spokes: the clay's own D gone) land 0.45 lands the skin within -0.011..
#   +0.012 mm life of the ring at every 15 deg (0.55 -0.021..+0.006, 0.65 -0.025..-0.001), the skin at 1.05 r_e
#   0.00..+0.05, at 1.14 r_e +0.06..+0.18: the collar's soft rim is the clay's own)
NARES = dict(depth=0.40, r_open=0.28, r_bottom=0.05, k=0.06, search=1.2)
# the vent (p01 at full size, the male's mound: ~8 mm long, ~2 mm under the belly line on that breeding male; A1 takes
# about half the swelling): the mound's stations, its peak rise and half-width (life mm), the slit, the papillae
VENT = dict(s=(0.519, 0.549), rise=1.0, half_w=2.2, k=0.8, slit=(0.523, 0.546), slit_r=0.16, slit_depth=0.16,
            papillae=5, pap_r=0.10, pap_rise=0.06, pap_off=0.26, step=0.25)
#   (the mound ends 0.003 TL ahead of the vent station: the ventral fin's membrane starts at 0.552, and a section ray
#   down the midline there would land on its margin)
FOLD = dict(arc=0.40, ridge_r=1.4, rise=0.12, offset=1.8, crease_r=0.60, depth=0.06, crease_at=0.80, k=0.20)
#   (AX7b's first build: ridge_r 1.0, rise 0.14, offset 1.6, crease_r 0.45, depth 0.10, crease_at 0.70, k 0.35: the blend
#   ate half the swelling's rise (the axilla built +0.278 mm x4 of +0.560, AX6 gate 5 over by 0.002); with k 0.20 the
#   groin still read as an arc ledge in ax06's close-up (a narrow crease under a convex swelling): broader and shallower)
#   (AX7b, 10-30: the round-6 look read the groin fold as a FLANGE RING (a 0.35 mm tube rising 0.18 mm, 0.45 mm off the
#   footprint ring) and its check found the crease, carved 0.05 mm off the footprint ring, ON the root band's UV seam:
#   the baked normals jumped 40-57 deg across it, a stepped crease at 2048. p01's groin is a smooth rounded junction
#   with a soft overhang: now a broad low swelling 1.6 mm up the body and a shallow soft crease `crease_at` 0.70 mm off
#   the ring (its flanks end ~0.4 mm off it: 4-5 texels at 2048, 9 at 4096, all on the body's island), filleted k 0.35)
# the digit tips: a ball `scale` x the digit's end radius, its front `rise` past the clay's round end (life mm),
# filleted. AX7b: OFF (scale 0): p23 / p04 / p05 show the digits tapering to a rounded tip about half their base with no
# bulb, the round-6 "balls on sticks"; the clay's own round end is the tip (sprawl's ax7b.digit_r taper). Before: 1.18
TIP = dict(scale=0.0, rise=0.05, k=0.15)
GRIDS = dict(fine=dict(voxel=0.00025, band=0.0025), coarse=dict(voxel=0.0003, band=0.0025))
FINE_REGIONS = ('root', 'arm', 'palm', 'digit', 'web', 'cap', 'ramus', 'body_head', 'body_neck', 'body_cap',
                'body_mouth', 'body_eye', 'body_socket', 'fin', 'eyeball')
COARSE_REGIONS = ('body_trunk', 'body_tail', 'body_port', 'body_tailcap')
D_REF = 0.054               # m: a filament template's high and bake at this ramus diameter (its width 0.074 D = 4 mm,
#                             16 voxels at 0.25 mm; at r1's own 13.6 mm it would be 4)
TPL_VOXEL = 0.00025
TPL_BAND = 0.0015


def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-20)


# ============================================================================================ the clay's surface
def onto(prg, P, iters=8):
    """points moved onto the clay's zero set (Newton steps along the gradient), with their outward normals"""
    P = np.asarray(P, np.float64).reshape(-1, 3).copy()
    for _ in range(iters):
        P = P - prg.eval(P).astype(np.float64)[:, None] * prg.normals(P).astype(np.float64)
    return P, unit(prg.normals(P).astype(np.float64))


def ray_surface(prg, O, D, reach, n=96):
    """from points O inside the clay along unit directions D: the first exit (a march then a bisection)"""
    O, D = np.asarray(O, np.float64).reshape(-1, 3), unit(np.asarray(D, np.float64).reshape(-1, 3))
    ts = np.linspace(0.0, reach, n)
    f = prg.eval((O[:, None] + ts[None, :, None] * D[:, None]).reshape(-1, 3)).reshape(len(O), n)
    k = np.argmax(f > 0.0, axis=1)
    assert np.all(f[np.arange(len(O)), k] > 0.0), 'a section ray found no surface'
    lo, hi = ts[np.maximum(k - 1, 0)], ts[k]
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        out = prg.eval(O + mid[:, None] * D) > 0.0
        hi, lo = np.where(out, mid, hi), np.where(out, lo, mid)
    return onto(prg, O + (0.5 * (lo + hi))[:, None] * D, iters=2)


def section(prg, body, km, s, thetas):
    """the clay's surface on the station plane of s at angles theta (deg from the dorsal midline toward +x, the
    creature's left), cast from the section's centre (the midline at mid-height): (points, normals) in x4 m"""
    top, bot = body.top_bot(s)
    c = np.array([0.0, 0.5 * (top + bot), body.z(s)]) * km
    th = np.radians(np.asarray(thetas, np.float64))
    D = np.column_stack([np.sin(th), np.cos(th), np.zeros_like(th)])
    return ray_surface(prg, np.broadcast_to(c, D.shape), D, (top - bot) * km * 1.5)


def chain(P, step):
    """the polyline P resampled every `step` (its own units) by arc"""
    L = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    t = np.linspace(0.0, L[-1], max(2, int(np.ceil(L[-1] / step)) + 1))
    return np.column_stack([np.interp(t, L, P[:, j]) for j in range(3)]), t / max(L[-1], 1e-20)


# ============================================================================================ the plan
def mirrored(plan_l):
    """each batch of a left-side plan with its exact mirror appended (x -> -x)"""
    for o in plan_l.ops:
        o['A'] = np.vstack([o['A'], o['A'] * MIRROR])
        o['B'] = np.vstack([o['B'], o['B'] * MIRROR])
        for key in ('kind', 'ra', 'rb', 'rc'):
            o[key] = np.concatenate([o[key], o[key]])
    return plan_l


def ring_samples(rings, step):
    """closed rings (each (n, 3)) resampled every `step` along their edges (their own units), stacked"""
    out = []
    for R in rings:
        R = np.asarray(R, np.float64)
        C = np.vstack([R, R[:1]])
        out.append(chain(C, step)[0][:-1])
    return np.vstack(out)


# ============================================================================================ THE BASE
def body_only(SDF, grid_body):
    """the clay's body member alone (the GRID of caudate's limit mesh), as its own program: x4 m"""
    vals, org, cell = grid_body
    pb = SDF.Program()
    pb.grid(org, np.eye(3), cell, vals, name='body')
    return pb


def pillow_stations(spec):
    """the groove stations with one spacing added past each end (the outer segments)"""
    st = np.asarray(spec['trunk']['groove_stations'], np.float64)
    return np.r_[2.0 * st[0] - st[1], st, 2.0 * st[-1] - st[-2]]


def pillows(P, spec, body, km, footprints, f_body, band):
    """THE BASE's costal pillows (module docstring): the displacement (x4 m, outward positive) at points P (x4 m).
    footprints: the LEFT limbs' footprint rings (x4 m; the right side by |x|); f_body: the body-only field at P (x4 m):
    points farther than `band` from the body's own surface (the limbs, the hands and feet over the flank's stations,
    the fins' blades) take none. Returns (displacement, amplitude (0..1, the fades' product))"""
    g = GROOVE
    ext = pillow_stations(spec)
    st = ext[1:-1]
    s = body.s_of(P[:, 2] / km)
    i = np.clip(np.searchsorted(ext, s) - 1, 0, len(ext) - 2)
    u = np.clip((s - ext[i]) / (ext[i + 1] - ext[i]), 0.0, 1.0)
    prof = np.sqrt(np.clip(4.0 * u * (1.0 - u), 0.0, 1.0)) - 0.25 * np.pi
    a = smooth01((s - ext[0]) / (st[0] - ext[0])) * smooth01((ext[-1] - s) / (ext[-1] - st[-1]))
    a[(s <= ext[0]) | (s >= ext[-1])] = 0.0
    # the section's angle off the dorsal midline (about its mid-height)
    ss = np.linspace(ext[0] - 0.01, ext[-1] + 0.01, 400)
    tb = np.array([body.top_bot(v) for v in ss])
    ymid = np.interp(s, ss, 0.5 * (tb[:, 0] + tb[:, 1]))
    th = np.degrees(np.arctan2(np.abs(P[:, 0]) / km, P[:, 1] / km - ymid))
    a *= smooth01((th - g['dorsal'][0]) / (g['dorsal'][1] - g['dorsal'][0]))
    a *= 1.0 - (1.0 - g['floor']) * smooth01((th - g['ventral'][0]) / (g['ventral'][1] - g['ventral'][0]))
    # off the limbs' roots
    from scipy.spatial import cKDTree
    fp = ring_samples(footprints, 0.1 * km)
    d, _ = cKDTree(fp).query(np.column_stack([np.abs(P[:, 0]), P[:, 1], P[:, 2]]))
    a *= smooth01((d / km - g['limb'][0]) / (g['limb'][1] - g['limb'][0]))
    # on the body's own skin only
    a *= smooth01((band - np.abs(f_body)) / (0.25 * band))
    return g['h'] * km * prof * a, a


def lobes(P, lob):
    """THE BASE's lip lobes (LIP's note): the displacement (x4 m, outward) at points P (x4 m): for each centre c (normal
    n), rise (1 - (d / R)^2)^2 over the tangential distance d = |(p - c) - n ((p - c) . n)| (so every voxel through the
    band at a surface point takes the same), within R along n too. lob: plan info's 'lobes'"""
    P = np.asarray(P, np.float64).reshape(-1, 3)
    out = np.zeros(len(P))
    R, h = float(lob['R']), float(lob['rise'])
    for c, n in zip(np.asarray(lob['centres']), np.asarray(lob['normals'])):
        q = P - c
        a = q @ n
        d = np.linalg.norm(q - a[:, None] * n, axis=1)
        w = np.clip(1.0 - (d / R) ** 2, 0.0, 1.0) ** 2
        out += h * w * (np.abs(a) < R)
    return out


def relief(field, P0, N0, reach, step, iters=24):
    """a field's surface (anything with .eval: a SparseSDF, a Program) along each line P0 + t N0 (t in [-reach, reach],
    x4 m): the outward crossing (inside -> outside) nearest t = 0, bisected; nan where the line has none"""
    P0, N0 = np.asarray(P0, np.float64).reshape(-1, 3), unit(np.asarray(N0, np.float64).reshape(-1, 3))
    ts = np.arange(-reach, reach + 0.5 * step, step)
    f = field.eval((P0[:, None] + ts[None, :, None] * N0[:, None]).reshape(-1, 3)).reshape(len(P0), len(ts))
    cross = (f[:, :-1] < 0.0) & (f[:, 1:] >= 0.0)
    cost = np.where(cross, np.abs(0.5 * (ts[:-1] + ts[1:]))[None], np.inf)
    k = np.argmin(cost, axis=1)
    ok = np.isfinite(cost[np.arange(len(P0)), k])
    lo, hi = ts[k].copy(), ts[k + 1].copy()
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        inside = field.eval(P0 + mid[:, None] * N0) < 0.0
        lo, hi = np.where(inside, mid, lo), np.where(inside, hi, mid)
    return np.where(ok, 0.5 * (lo + hi), np.nan)


def high_clay(spec, SDF, chain, sk, grid, eyes, fins_m):
    """THE BASE's high clay (module docstring): sprawl.clay_program with the limbs' and the rami's sweeps on the same
    curves sampled REFINE times denser. grid: the body GRID (values, origin, cell) x4 m; eyes: (centres, radius) x4 m;
    fins_m: {name: (V, F, half thickness)} x4 m. Returns (program, limbs, rami)"""
    from ..families import sprawl as SP
    node = SP.CLAY['node_mm'] / REFINE
    limbs = SP.limb_sweeps(spec, chain, sk, sk.world, node_mm=node)
    rami = SP.gill_rami(spec, chain, sk, sk.world, node_mm=node)
    return SP.clay_program(spec, SDF, grid, limbs, rami, eyes, fins_m), limbs, rami


def sculpt_grid(name, prg, plan_, base, samples, lo, hi, log=print, chunk=8_000_000, on_built=None, relevel_order=2):
    """one grid of the high (module docstring's GRIDS): a SparseSDF at GRIDS[name] over the coarse cells within reach of
    `samples` (x4 m points on the triangles this grid bakes), the plan's tall strokes' spheres activated; THE BASE's
    pillows and lip lobes, then the plan (Plan.apply: the batches in order, smooth (1, 0.5), relevel). base: dict(spec,
    body, km, footprints (the LEFT rings, x4 m), body_prg (body_only's program), lobes (plan info's)). on_built(G):
    called on the built grid before
    any sculpting (ax06's views of the high clay). The grid keeps its keep filter (G.keep) and its name. AX7's bake
    calls this with AX6's inputs. relevel_order: 2, the house's relevel (Plan.apply's: voxel.redistance over the whole
    band, second-order upwind data); 1, the same relevel with first-order data (AX7's bake inputs, where the check found
    the second-order Jacobi sweeps leaving isolated voxels 1-4 rings off the surface 0.2-1 mm wrong for the bake's
    curvature, AO and thickness to read: the first-order update is monotone; both hold the interface layer, so the
    surface is the same). Returns (G, info)"""
    gp = GRIDS[name]
    reach = 64 * gp['voxel'] * 0.8661 + gp['band'] + 0.003
    keep = keep_fn(samples, reach)
    # the strokes' activation spheres, the eye funnel's left out: Plan.bounds gives a round cone one sphere round its
    # whole length, ~25 mm x4 about a centre inside the ball (some 4 M voxels per eye), yet the funnel makes new surface
    # only where it cuts the collar by the edge ring, within the band, and the ball it removes is added back
    pb = Plan()
    pb.ops = [o for o in plan_.ops if o['tag'] != 'eye funnel']
    extra = pb.bounds(prg, gp['band'])
    # a displacement as tall as the band's reach needs voxels as a tall stroke does (run 5: the lip lobes at 0.65 mm
    # life, 2.6 mm x4, printed a patch of pits where the displaced skin left the band): a sphere round each lobe
    lob = base['lobes']
    if lob['rise'] > 0.5 * gp['band']:
        Cl = np.asarray(lob['centres']) + np.asarray(lob['normals']) * 0.5 * lob['rise']
        extra = (np.vstack([extra[0], Cl]), np.r_[extra[1], np.full(len(Cl), lob['R'] + gp['band'])])
    t0 = time.time()
    G = VX.SparseSDF(prg, lo, hi, voxel=gp['voxel'], band=gp['band'], keep=keep, extra=extra, log=log)
    G.keep, G.name = keep, name
    if on_built is not None:
        on_built(G)
    t1 = time.time()
    # the displacements: the pillows (only voxels on the trunk's stations can take any: pillows' outer segments bound
    # them) and the lip lobes (only voxels within R of a lobe's centre)
    spec, body, km = base['spec'], base['body'], base['km']
    ext = pillow_stations(spec)
    Cl = np.asarray(lob['centres'])
    ijk = G.ijk.numpy()
    disp = np.zeros(G.n, np.float32)
    n_on, amp_max, n_lobe = 0, 0.0, 0
    for s0 in range(0, G.n, chunk):
        P = G.origin + ijk[s0:s0 + chunk].astype(np.float64) * G.vs
        s = body.s_of(P[:, 2] / km)
        on = np.nonzero((s > ext[0]) & (s < ext[-1]))[0]
        if len(on):
            f_body = base['body_prg'].eval(P[on]).astype(np.float64)
            d, a = pillows(P[on], spec, body, km, base['footprints'], f_body, gp['band'])
            disp[s0 + on] = d.astype(np.float32)
            n_on += int((a > 0).sum())
            amp_max = max(amp_max, float(a.max()))
        near = np.nonzero(np.min(np.linalg.norm(P[:, None, :] - Cl[None], axis=2), axis=1) < 1.5 * lob['R'])[0]
        if len(near):
            dl = lobes(P[near], lob)
            disp[s0 + near] += dl.astype(np.float32)
            n_lobe += int((dl > 0).sum())
    del ijk
    G.offset(1.0, weight=disp)
    t2 = time.time()
    if relevel_order == 2:
        plan_.apply(G, log=log)
    else:
        plan_.apply(G, log=log, relevel=0)            # the strokes and the smooth; then the relevel at this order
        G.redistance(None, order=int(relevel_order))
        log(f'[sculpt] the {name} grid relevelled with order-{int(relevel_order)} data')
    info = dict(voxels=int(G.n), voxel=gp['voxel'], band=gp['band'], extra=int(len(extra[0])),
                keep_samples=int(len(samples)), pillow_voxels=n_on, pillow_amp_max=amp_max, lobe_voxels=n_lobe,
                disp_mm=(float(disp.min() * 1000), float(disp.max() * 1000)), t_build=t1 - t0, t_pillows=t2 - t1,
                t_plan=time.time() - t2)
    log(f'[sculpt] the {name} grid: {G.n:,} voxels ({info["extra"]} stroke spheres activated); the pillows on '
        f'{n_on:,} voxels, the lip lobes on {n_lobe:,} (displacement {info["disp_mm"][0]:+.3f} .. '
        f'{info["disp_mm"][1]:+.3f} mm x4); build {info["t_build"]:.1f}s, displacements {info["t_pillows"]:.1f}s, the '
        f'plan {info["t_plan"]:.1f}s')
    return G, info


def add_c(P, N, h, r):
    """an ADD stroke's centre: radius r, its top h above the surface point P (normal N)"""
    return P + N * np.asarray(h - r, np.float64).reshape(-1, 1)


def carve_c(P, N, d, r):
    """a CARVE stroke's centre: radius r, cutting d below the surface point P (normal N); d <= r (no undercut)"""
    d = np.asarray(d, np.float64)
    assert np.all(d <= np.asarray(r) + 1e-12), 'a carve deeper than its radius undercuts its own lips'
    return P + N * np.asarray(r - d, np.float64).reshape(-1, 1)


def probe(info, name, P, N, expect, tol, absolute=False):
    """a feature's design relief: the high's surface along N at P should lie `expect` off the clay (x4 m, outward
    positive) within tol (ax06's gate 5); absolute: `expect` off P itself (where the clay is not the reference: the
    eye's opening, which the clay's cheek covers on one side)"""
    info.setdefault('probes', []).append(dict(name=name, P=np.asarray(P, np.float64).reshape(-1, 3),
                                              N=unit(np.asarray(N, np.float64).reshape(-1, 3)),
                                              expect=np.broadcast_to(np.asarray(expect, np.float64),
                                                                     (len(np.asarray(P).reshape(-1, 3)),)).copy(),
                                              tol=float(tol), absolute=bool(absolute)))


def surface_from_inside(prg, O, D, reach):
    """ray_surface for one direction shared by every start (a convenience); every start must lie inside the clay"""
    O = np.asarray(O, np.float64).reshape(-1, 3)
    assert np.all(prg.eval(O) < 0.0), 'a ray starts outside the clay (ray_surface would return the start itself)'
    return ray_surface(prg, O, np.broadcast_to(unit(D), O.shape), reach)


def find_naris(prg, guess, km, half=1.2, step=0.04):
    """the clay's naris: the deepest point of caudate's dimple below the plane of its surroundings, near guess (x4 m).
    Returns (point, the surroundings' outward normal, the dimple's depth below them), x4 m"""
    p0, n0 = onto(prg, np.asarray(guess, np.float64).reshape(1, 3))
    p0, n0 = p0[0], n0[0]
    t1 = unit(np.cross(n0, [0.0, 1.0, 0.0]))
    t2 = np.cross(n0, t1)
    g = np.arange(-half, half + 1e-9, step) * km
    X, Y = np.meshgrid(g, g, indexing='ij')
    X, Y = X.ravel(), Y.ravel()
    O = p0[None] + X[:, None] * t1 + Y[:, None] * t2 - n0 * 1.0 * km
    Q, _ = surface_from_inside(prg, O, n0, 2.5 * km)
    h = (Q - p0) @ n0
    rim = np.hypot(X, Y) > 0.75 * half * km
    A = np.column_stack([X[rim], Y[rim], np.ones(int(rim.sum()))])
    cx, cy, c0 = np.linalg.lstsq(A, h[rim], rcond=None)[0]
    depth = (cx * X + cy * Y + c0) - h
    k = int(np.argmax(np.where(np.hypot(X, Y) < 0.6 * half * km, depth, -np.inf)))
    n_plane = unit(n0 - cx * t1 - cy * t2)
    return Q[k], n_plane, float(depth[k])


def plan(spec, prg, body, km, cage, log=print):
    """the tier-S strokes (module docstring) in x4 m, the right side every left stroke mirrored. cage (x4 m):
    gular: the gular loop's vertices in order across the throat; lip: the upper lip's creased run on the LEFT side, in
    order toward the commissure; eye: dict(centre, axis, r_e, r_ball) of the left eye (the ball's centre, the eye's
    axis, the visible eye's radius = the edge ring's, the ball's); footprints: {fore, hind} the left limbs' footprint
    rings; tips: [(end node, unit tangent, end radius)] of the left digits' sweeps (the high's); naris: caudate's left
    naris (its dimple's neighbourhood); frontal (optional): caudate's record (its mouth line and lobes: the lobes' rims).
    Returns (Plan, info: per feature its design numbers and the probes ax06's gate 5 measures)"""
    mm = km
    left, mid = Plan(), Plan()
    info = {}
    # ---- the gular fold (the midline batch: the loop crosses it); the ridge just ahead, the crease just behind
    g = GULAR
    G = np.asarray(cage['gular'], np.float64)
    Gp, gu = chain(G, g['step'] * mm)
    Gp, Gn = onto(prg, Gp)
    # exactly symmetric (the clay is float32: its two sides agree to ~1e-7 m): sample i is sample n-1-i mirrored
    Gp = 0.5 * (Gp + Gp[::-1] * MIRROR)
    Gn = unit(0.5 * (Gn + Gn[::-1] * MIRROR))
    gu = 0.5 * (gu + 1.0 - gu[::-1])
    fwd = np.array([0.0, 0.0, 1.0])
    tf = unit(fwd - Gn * (Gn @ fwd)[:, None])
    fade = smooth01(gu / g['fade']) * smooth01((1.0 - gu) / g['fade'])
    ridge = add_c(Gp + tf * g['ahead'] * mm, Gn, g['rise'] * fade * mm, g['ridge_r'] * mm)
    mid.add(STROKE_CONE, ridge[:-1], ridge[1:], g['ridge_r'] * mm, g['ridge_r'] * mm, 'add', g['k'] * mm, 'gular ridge')
    crease = carve_c(Gp - tf * g['behind'] * mm, Gn, g['depth'] * fade * mm, g['crease_r'] * mm)
    i0 = int(np.argmin(np.abs(Gp[:, 0])))
    probe(info, 'gular ridge', Gp[i0] + tf[i0] * g['ahead'] * mm, Gn[i0], g['rise'] * mm, 0.45 * g['rise'] * mm)
    probe(info, 'gular crease', Gp[i0] - tf[i0] * g['behind'] * mm, Gn[i0], -g['depth'] * mm, 0.45 * g['depth'] * mm)
    # ---- the lip lobes (a displacement, sculpt_grid applies it: lobes()): centred `up` over each commissure
    lp = LIP
    L = np.asarray(cage['lip'], np.float64)
    # AX7b: the lobe's foot `ahead` mm before the commissure along the lip run (LIP's note)
    Lc, lu = chain(L, 0.1 * mm)
    arc_l = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Lc, axis=0), axis=1))])
    a_foot = max(0.0, arc_l[-1] - lp.get('ahead', 0.0) * mm)
    foot = np.array([np.interp(a_foot, arc_l, Lc[:, k]) for k in range(3)])
    corner, cn = onto(prg, foot[None])
    yh = np.array([0.0, 1.0, 0.0])
    up_c = unit(yh - cn[0] * (cn[0] @ yh))
    Pl, Nl = onto(prg, corner + up_c * lp['up'] * mm)
    Pl, Nl = np.vstack([Pl, Pl * MIRROR]), np.vstack([Nl, Nl * MIRROR])      # both sides, exact mirrors
    info['lobes'] = dict(centres=Pl, normals=Nl, R=lp['R'] * mm, rise=lp['rise'] * mm)
    if lp['rise'] > 0.0:                         # (AX7c: off, the clay's lobes: LIP's note)
        probe(info, 'lip lobes', Pl[:1], Nl[:1], lp['rise'] * mm, 0.3 * lp['rise'] * mm)
    # ---- the lobes' rims (LOBE's note; cage['frontal']: caudate's record, with its mouth line and lobes)
    rim = None
    fr = cage.get('frontal')
    # (the AX8 check: no rim under the beads unless LOBE['bead_rim']; LOBE's note)
    if fr is not None and fr.get('lobe') is not None and (LOBE['bead_rim'] or len(fr['lobe'].get('beads') or []) < 2):
        from ..heads import caudate as CD
        lb, lob = LOBE, fr['lobe']
        # AX8: one arc per bead (LOBE's AX8 note); AX7c's one lobe without the record's beads
        arcs = ([(lc, lb['bead_half_k'] * w_, lb['bead_drop']) for lc, w_ in lob['beads']] if lob.get('beads') and
                len(lob['beads']) > 1 else [(lob['lam_L'], lb['half_w'], lb['drop'])])
        rim = []
        for k_, (lc, hw_, dr_) in enumerate(arcs):
            phi = np.linspace(0.0, np.pi, int(np.ceil(np.pi * hw_ / lb['step'])) + 1)
            s_rim = np.interp(lc + hw_ * np.cos(phi), lob['lam_s'], lob['s_tab'])
            M_rim = np.array([[*CD.mouth_point(body, fr, float(s_))[1:], float(body.z(s_))] for s_ in s_rim])
            Pb, Nb = onto(prg, (M_rim - np.outer(dr_ * np.sin(phi), [0.0, 1.0, 0.0])) * mm)
            rim.append(carve_c(Pb, Nb, lb['depth'] * smooth01(np.sin(phi) / lb['fade']) * mm, lb['rim_r'] * mm))
            if k_ == 0:
                i_b = len(phi) // 2
                probe(info, 'lobe rim', Pb[i_b], Nb[i_b], -lb['depth'] * mm, 0.45 * lb['depth'] * mm)
    # ---- the axilla and groin folds: a ridge just above each footprint's dorsal arc, on the body; a crease at it
    crease_A, crease_B, crease_r = [], [], []
    for kind, ring in cage['footprints'].items():
        ring = np.asarray(ring, np.float64)
        k_top = np.argsort(-ring[:, 1])[:max(3, int(round(FOLD['arc'] * len(ring))))]
        idx = np.arange(len(ring))
        sel = np.isin(idx, k_top)
        start = int(np.nonzero(sel & ~np.roll(sel, 1))[0][0])
        order = [(start + j) % len(ring) for j in range(len(ring)) if sel[(start + j) % len(ring)]]
        arc = ring[order]
        Pa, au = chain(arc, 0.25 * mm)
        Pa, Na = onto(prg, Pa)
        # away from the limb along the body: from the ring's centre outward, in the surface's tangent plane
        out = Pa - ring.mean(0)
        out = unit(out - Na * (out * Na).sum(1)[:, None])
        f = smooth01(au / 0.3) * smooth01((1.0 - au) / 0.3)
        Pr, Nr = onto(prg, Pa + out * FOLD['offset'] * mm)
        ridge_f = add_c(Pr, Nr, FOLD['rise'] * f * mm, FOLD['ridge_r'] * mm)
        name = f'{"axilla" if kind == "fore" else "groin"} fold'
        left.add(STROKE_CONE, ridge_f[:-1], ridge_f[1:], FOLD['ridge_r'] * mm, FOLD['ridge_r'] * mm, 'add',
                 FOLD['k'] * mm, name)
        Pc, Nc = onto(prg, Pa + out * FOLD['crease_at'] * mm)          # AX7b: off the footprint ring (the seam)
        cr = carve_c(Pc, Nc, FOLD['depth'] * f * mm, FOLD['crease_r'] * mm)
        crease_A.append(cr[:-1])
        crease_B.append(cr[1:])
        crease_r.append(np.full(len(cr) - 1, FOLD['crease_r'] * mm))
        im = len(Pr) // 2
        probe(info, name, Pr[im], Nr[im], FOLD['rise'] * mm, 0.5 * FOLD['rise'] * mm)
    # ---- the digit tips: a ball a little wider than the digit's round end, its front a little past it (AX7b: off,
    # TIP's note: the clay's tapered round end is the tip)
    if TIP['scale'] > 1.0:
        E_ = np.array([t[0] for t in cage['tips']], np.float64)
        T_ = unit(np.array([t[1] for t in cage['tips']], np.float64))
        r_end = np.array([t[2] for t in cage['tips']], np.float64)
        r_b = TIP['scale'] * r_end
        ctr = E_ + T_ * (r_end + TIP['rise'] * mm - r_b)[:, None]
        left.add(STROKE_CONE, ctr, ctr, r_b, r_b, 'add', TIP['k'] * mm, 'digit tips')
        probe(info, 'digit tips', E_ + T_ * r_end[:, None], T_, TIP['rise'] * mm, 0.6 * TIP['rise'] * mm + 0.0001)
        side_n = unit(np.cross(T_, [0.0, 1.0, 0.0]))
        probe(info, 'digit tips, the bulb\'s side', ctr + side_n * r_end[:, None], side_n, r_b - r_end,
              0.5 * float(np.mean(r_b - r_end)) + 0.0001)
    # ---- the vent: the mound on the ventral midline, its slit, the papillae on the slit's lips
    v = VENT
    s0, s1 = v['s']
    sv = np.arange(s0, s1 + 1e-9, v['step'] / spec['a1']['TL'])
    Pv, Nv = section_midline(prg, body, km, sv)
    t_v = (sv - s0) / (s1 - s0)
    w = np.sin(np.pi * t_v) ** 0.7
    rise_v = v['rise'] * w
    r_v = (v['half_w'] ** 2 + v['rise'] ** 2 * w) / (2.0 * v['rise'])
    cv = add_c(Pv, Nv, rise_v * mm, r_v * mm)
    mid.add(STROKE_CONE, cv[:-1], cv[1:], r_v[:-1] * mm, r_v[1:] * mm, 'add', v['k'] * mm, 'vent mound')
    a0, a1 = v['slit']
    sp_ = np.linspace(a0 + 0.12 * (a1 - a0), a1 - 0.12 * (a1 - a0), v['papillae'])
    Pp, Np_ = section_midline(prg, body, km, sp_)
    top_p = v['rise'] * np.sin(np.pi * (sp_ - s0) / (s1 - s0)) ** 0.7
    xh = np.array([1.0, 0.0, 0.0])
    pc = add_c(Pp + xh * v['pap_off'] * mm, Np_, (top_p + v['pap_rise']) * mm, v['pap_r'] * mm)
    left.add(STROKE_CONE, pc, pc, v['pap_r'] * mm, v['pap_r'] * mm, 'add', 0.04 * mm, 'vent papillae')
    sl = np.arange(a0, a1 + 1e-9, v['step'] / spec['a1']['TL'])
    Ps, Ns = section_midline(prg, body, km, sl)
    top_s = v['rise'] * np.sin(np.pi * (sl - s0) / (s1 - s0)) ** 0.7
    ws = np.sin(np.pi * (sl - a0) / (a1 - a0)) ** 0.5
    slit = carve_c(Ps + Ns * (top_s * mm)[:, None], Ns, v['slit_depth'] * ws * mm, v['slit_r'] * mm)
    ip = int(np.argmax(w))
    Pq, Nq = onto(prg, Pv[ip] + xh * 0.6 * mm)
    probe(info, 'vent mound', Pq, Nq, (v['rise'] - 0.36 / (2 * r_v[ip])) * mm, 0.35 * v['rise'] * mm)
    # ---- the eye (eye_strokes: the funnel landing the skin on the edge ring, the ball added back)
    eye_ops, info['eye'] = eye_strokes(prg, cage['eye'], km, info)
    # ---- the nares (caudate's dimple, its deepest point): round conical pits along the surroundings' normal
    pn, nn, dimple = find_naris(prg, np.asarray(cage['naris'], np.float64), km, NARES['search'])
    na = NARES
    A_n = pn - nn * na['depth'] * mm
    B_n = pn + nn * 0.3 * mm
    rb_n = na['r_bottom'] + (na['r_open'] - na['r_bottom']) * (na['depth'] + 0.3) / na['depth']
    probe(info, 'nares', pn, nn, -(na['depth'] + na['r_bottom']) * mm, 0.35 * na['depth'] * mm)
    info['nares'] = dict(point_life_mm=(pn / km).round(3).tolist(), normal=nn.round(4).tolist(),
                         dimple_depth_mm=dimple / mm)
    # ---- the batches: the side ones mirrored, then everything in its order
    mid.add(STROKE_CONE, crease[:-1], crease[1:], g['crease_r'] * mm, g['crease_r'] * mm, 'carve', g['k'] * mm,
            'gular crease')
    left.add(STROKE_CONE, np.vstack(crease_A), np.vstack(crease_B), np.concatenate(crease_r),
             np.concatenate(crease_r), 'carve', FOLD['k'] * mm, 'axilla / groin creases')
    if rim is not None:
        # (each arc its own polyline: a segment from one bead's arc to the next would carve across the lip)
        left.add(STROKE_CONE, np.vstack([r_[:-1] for r_ in rim]), np.vstack([r_[1:] for r_ in rim]), LOBE['rim_r'] * mm,
                 LOBE['rim_r'] * mm, 'carve', LOBE['k'] * mm, 'lobe rim')
    mid.add(STROKE_CONE, slit[:-1], slit[1:], v['slit_r'] * mm, v['slit_r'] * mm, 'carve', 0.05 * mm, 'vent slit')
    for op in eye_ops:
        left.add(*op)
    left.add(STROKE_CONE, A_n, B_n, na['r_bottom'] * mm, rb_n * mm, 'carve', na['k'] * mm, 'nares')
    left = mirrored(left)
    order = ['gular ridge', 'axilla fold', 'groin fold'] + (['digit tips'] if TIP['scale'] > 1.0 else []) + \
        ['vent mound', 'vent papillae', 'gular crease', 'axilla / groin creases'] + \
        (['lobe rim'] if rim is not None else []) + ['vent slit'] + [op[-1] for op in eye_ops] + ['nares']
    by = {o['tag']: o for o in left.ops + mid.ops}
    P = Plan()
    P.ops = [by[t] for t in order if t in by]
    assert len(P.ops) == len(order), sorted(set(order) - set(by))
    log('[sculpt] the plan: ' + ', '.join(f'{o["tag"]} {len(o["A"])}' for o in P.ops))
    return P, info


def eye_strokes(prg, e, km, info=None):
    """THE EYE's strokes (the module docstring), the left eye's, x4 m: (ops, the eye's design numbers). e: dict(centre
    (the ball's), axis, r_e (the edge ring's radius = the visible eye's), r_ball). ops: Plan.add argument tuples in their
    plan order (the funnel, a carve; the ball, an add). info: the plan's dict, which takes the eye's probes when given
    (the step script's harness calls this alone)"""
    mm = km
    c_b, a_e = np.asarray(e['centre'], np.float64), unit(e['axis'])
    r_e, r_ball = float(e['r_e']), float(e['r_ball'])
    h_e = float(np.sqrt(r_ball ** 2 - r_e ** 2))                 # the edge plane off the ball's centre
    Ec = c_b + a_e * h_e
    u_ax = unit(np.cross(a_e, [0.0, 1.0, 0.0]))
    v_ax = np.cross(a_e, u_ax)
    ang = np.linspace(0.0, 2.0 * np.pi, EYE['n'], endpoint=False)
    rad = np.cos(ang)[:, None] * u_ax + np.sin(ang)[:, None] * v_ax
    # the skin round the eye (at the AX4 cage's crest radius): how far it stands over the edge plane, by angle
    R_c = EYE['collar_at'] * r_e
    Pk, _ = surface_from_inside(prg, c_b - a_e * r_ball + rad * R_c, a_e, 4.0 * r_ball)
    h_skin = (Pk - Ec) @ a_e
    # the funnel: a ROUND cone, its apex on the axis behind the ball, half-angle EYE['alpha']: STROKE_CONE, iq's exact
    # round cone, between two balls inscribed in the cone (radius z sin alpha at z along the axis from the apex: the side
    # is the true cone between their tangent circles, at z cos^2 alpha, and the balls' caps beyond lie inside it too).
    # (AX7's eye harness, 10-29: STROKE_ECONE, the octopus's elliptic aperture, is not round at equal half-angles: its
    # metric combines the two axes' angles, so at 45 deg between them the wall stands at 33.1 deg for 35, and the skin
    # landed 0.05-0.1 mm farther out at 12, 3, 6 and 9 o'clock than between them.) The near ball's tangent circle sits
    # EYE['out'] under the edge plane (below the moat the wall leaves by the ring, the near ball's cap lies inside the
    # eyeball, which is added back; its centre is where the stroke makes surface, so ax06's gate 2 finds voxels there: a
    # cone from the apex itself put its end deep in the ball, 5.4 mm x4 under the band), the far one's EYE['out'] above
    # the higher of the skin round the eye and the ball's pole: cut below the pole, the ball's top stayed in the field and
    # the ball added back over its own surface took smin(f, f) there, swelling the front cap by up to k_ball / 4 (0.024 mm
    # life at the pole); cut above it, the whole visible ball is re-added from air, exact but for its fillet. The wall
    # crosses the edge plane `land` x the ball fillet's reach outside the ring (the re-added ball covers its surface where
    # the carved field is under k_ball; the round cone's field is a true distance), so the ball's fillet ends AT the ring
    al = np.radians(EYE['alpha'])
    reach = EYE['land'] * EYE['k_ball'] * mm
    R_w = r_e + reach / np.cos(al)
    b_ap = R_w / np.tan(al)
    apex = Ec - a_e * b_ap
    h_cap = max(float(h_skin.max()), r_ball - h_e) + EYE['out'] * mm
    z_a = (b_ap - EYE['out'] * mm) / np.cos(al) ** 2
    z_b = (b_ap + h_cap) / np.cos(al) ** 2
    ops = [(STROKE_CONE, apex + a_e * z_a, apex + a_e * z_b, z_a * np.sin(al), z_b * np.sin(al), 'carve',
            EYE['k_funnel'] * mm, 'eye funnel'),
           (STROKE_CONE, c_b, c_b, r_ball, r_ball, 'add', EYE['k_ball'] * mm, 'eyeball')]
    if info is not None:
        # the probes: the ball is the surface inside the edge ring up to it (no skin over it), at three radii
        for f in (0.85, 0.93, 0.97):
            th = np.arcsin(f * r_e / r_ball)
            pts = c_b + r_ball * (np.cos(th) * a_e[None] + np.sin(th) * rad)
            probe(info, f'eye opening (the ball at {f:.2f} r_e, inside the edge ring)', pts, pts - c_b, 0.0, 0.0001,
                  absolute=True)
    return ops, dict(r_e_mm=r_e / mm, r_ball_mm=r_ball / mm, h_edge_mm=h_e / mm, alpha=float(np.degrees(al)),
                     apex_behind_ball_mm=(b_ap - h_e) / mm, wall_off_mm=(R_w - r_e) / mm, land=EYE['land'],
                     k_ball_mm=EYE['k_ball'], collar_R_mm=R_c / mm,
                     skin_over_edge_plane_mm=(h_skin / mm).round(3).tolist()[::6])


def section_midline(prg, body, km, ss):
    """the ventral midline's surface points and normals at stations ss (the section ray straight down); each must lie on
    the body's own belly line (within 1.5 mm life: a ray that met a fin's membrane instead fails here)"""
    out_p, out_n = [], []
    for s in ss:
        p, n = section(prg, body, km, s, [180.0])
        assert abs(p[0][1] / km - body.top_bot(s)[1]) < 1.5, f'the midline ray at s {s:.4f} missed the belly'
        out_p.append(p[0])
        out_n.append(n[0])
    P, N = np.array(out_p), np.array(out_n)
    P[:, 0], N[:, 0] = 0.0, 0.0                  # ON the midline exactly (the float32 clay's sides agree to ~1e-7 m)
    return P, unit(N)


def symmetric(P, tags_mid=('gular ridge', 'vent mound', 'gular crease', 'vent slit')):
    """the plan's mirror test: every side batch's second half the exact mirror of its first; every midline batch's
    strokes mapped onto the batch by the mirror, as a set of UNDIRECTED round cones (a loop across the midline runs from
    -x to +x, so the mirror maps each segment onto its partner reversed: (a, b, ra, rb) is the solid (b, a, rb, ra)).
    Returns the worst distance (m)"""
    worst = 0.0
    for o in P.ops:
        n = len(o['A'])
        if o['tag'] in tags_mid:
            A, B, ra, rb = o['A'], o['B'], o['ra'][:, None], o['rb'][:, None]
            seg = np.hstack([A, B, ra, rb])
            rev = np.hstack([B, A, rb, ra])
            for row in np.hstack([A * MIRROR, B * MIRROR, ra, rb]):
                worst = max(worst, float(min(np.min(np.linalg.norm(seg - row, axis=1)),
                                             np.min(np.linalg.norm(rev - row, axis=1)))))
        else:
            h = n // 2
            worst = max(worst, float(np.abs(o['A'][h:] - o['A'][:h] * MIRROR).max()),
                        float(np.abs(o['B'][h:] - o['B'][:h] * MIRROR).max()))
    return worst


# ============================================================================================ the grids
def keep_fn(samples, reach):
    """a SparseSDF keep filter: a coarse cell is kept when its centre lies within reach of any sample point"""
    from scipy.spatial import cKDTree
    tree = cKDTree(np.asarray(samples, np.float64))

    def keep(pts):
        d, _ = tree.query(np.asarray(pts, np.float64))
        return d < reach
    return keep


def tri_samples(V, F, n=4):
    """points on each triangle on an n-step barycentric grid (its corners included)"""
    out = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            a, b = i / n, j / n
            out.append(V[F[:, 0]] * (1 - a - b) + V[F[:, 1]] * a + V[F[:, 2]] * b)
    return np.vstack(out)


# ============================================================================================ the filament templates
def template_program(SDF, spec, shape, D=D_REF, n=320):
    """a filament template's high (the sweep of axolotl_gills.template's own curve and radius) at ramus diameter D (m),
    in its own frame (x root -> tip, bending toward +y): (program, V low (the LOD0's, same scale), F). n sweep nodes:
    0.25 mm x4 apart at D_REF, a voxel (the sweep's centreline is the polyline through them: THE BASE's bands)"""
    from . import axolotl_gills as GL
    # AX7b: the template's own curve and radius (axolotl_gills.centreline / radius), not a copy of them: the copy kept
    # the round-6 bends and width when the templates changed (AX6 gate 4: the lows 2.3-3.3 mm off their highs)
    _, w = GL._dims(spec)
    t = np.linspace(0.0, 1.0, n)
    C = GL.centreline(shape, spec, t) * D
    r = GL.radius(spec, t) * D
    T = unit(np.gradient(C, axis=0))
    N = unit(np.cross(T, [0.0, 0.0, 1.0]))
    # the root runs on 0.3 D into where the stalk would be, so the template's own root is buried (its instances' are)
    root = C[0] - T[0] * 0.3 * w * D
    prg = SDF.Program()
    prg.sweep(np.vstack([root, C]), np.vstack([N[0], N]), np.r_[r[0], r], name=f'filament_{shape}')
    Vt, Ft = GL.template_low(shape, spec)
    return prg, Vt * D, Ft


# ============================================================================================ the look (wet light)
@wp.kernel
def k_wet(origin0: wp.vec3, du: wp.vec3, dv: wp.vec3, dirv: wp.vec3, size: int, tmax: float, min_step: float,
          grad_h: float, ao_h0: float, ao_dh: float,
          pos: wp.array(dtype=wp.vec3), nrm: wp.array(dtype=wp.vec3), occ_o: wp.array(dtype=float),
          vol: wp.uint64, val: wp.array(dtype=wp.float32),
          n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32),
          kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3),
          node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4),
          shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """voxel.k_trace's sphere tracing of the hybrid field, returning the hit, its B-spline normal (voxel.hnormal: the
    normal the high's maps are built from) and its SDF occlusion, so the shading (render_wet) can carry a wet specular
    lobe: a diffuse key hides the facets and bands a glossy skin shows"""
    tid = wp.tid()
    px = tid % size
    py = tid // size
    o = origin0 + du * (float(px) + 0.5) + dv * (float(py) + 0.5)
    t = float(0.0)
    t_prev = float(0.0)
    f = VX.hybrid(o, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    hit = int(0)
    for it in range(1024):
        if f < 0.0:
            hit = 1
            break
        step = wp.max(f * 0.8, min_step)
        t_prev = t
        t = t + step
        if t > tmax:
            break
        f = VX.hybrid(o + dirv * t, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                      tri)
    if hit == 0:
        nrm[tid] = wp.vec3(0.0, 0.0, 0.0)
        return
    lo = t_prev
    hi = t
    for it in range(24):
        mid = 0.5 * (lo + hi)
        fm = VX.hybrid(o + dirv * mid, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                       thick, tri)
        if fm > 0.0:
            lo = mid
        else:
            hi = mid
    p = o + dirv * hi
    n = VX.hnormal(p, grad_h, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    occ = float(0.0)
    sca = float(1.0)
    for a in range(6):
        hs = ao_h0 + ao_dh * float(a)
        dd = VX.hybrid(p + n * hs, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                       tri)
        occ = occ + (hs - dd) * sca
        sca = sca * 0.75
    pos[tid] = p
    nrm[tid] = n
    occ_o[tid] = occ


def render_wet(G, fwd, up, centre, span, size=640, label='', key=(0.45, 0.75, 0.45), ao=True, hits=False):
    """an orthographic view of G's hybrid field (a voxel.SparseSDF; centre and span in x4 m) in a wet light: a key
    (key = its weights on (toward the camera, up, right)), a fill from the camera, a tight specular lobe on the key,
    SDF occlusion (ao False: none; the SDF AO reads the field's values up to ~13 voxels off the surface, so it also
    shows where a partial relevel hands back the clay's values, which the bake's ray-traced AO does not read). hits:
    also return the hit points (n, 3) x4 m and the hit mask. Returns a PIL image (or (image, points, mask))"""
    from PIL import Image, ImageDraw
    f_ = unit(fwd)
    r_ = unit(np.cross(f_, up))
    u_ = np.cross(r_, f_)
    c = np.asarray(centre, np.float64)
    pix = span / size
    far = 2.0 * span + 0.02
    o0 = c - r_ * span / 2 + u_ * span / 2 - f_ * far
    n = size * size
    pos, nrm, occ = wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=float)
    ao_h0, ao_dh = max(1.5 * G.vs, 0.02 * span), max(2.0 * G.vs, 0.03 * span)
    wp.launch(k_wet, dim=n, inputs=[wp.vec3(*o0), wp.vec3(*(r_ * pix)), wp.vec3(*(-u_ * pix)), wp.vec3(*f_), size,
                                    2.0 * far, float(max(pix * 0.25, G.vs * 0.2)), float(G.vs * 0.9), float(ao_h0),
                                    float(ao_dh), pos, nrm, occ] + G._args())
    N = nrm.numpy().astype(np.float64)
    hit = np.linalg.norm(N, axis=1) > 0.5
    k_ = unit(-f_ * key[0] + u_ * key[1] + r_ * key[2])
    h = unit(k_ - f_)
    dif = np.clip(N @ k_, 0, 1)
    fill = np.clip(N @ -f_, 0, 1)
    spec = np.clip(N @ h, 0, 1) ** 90 * 0.9
    ao_ = np.clip(1.0 - 9.0 * occ.numpy() / (3.0 * (ao_h0 + 2.5 * ao_dh)), 0, 1) if ao else np.ones(n)
    cc = (0.12 + 0.55 * dif + 0.25 * fill) * (0.35 + 0.65 * ao_)
    col = np.stack([cc * 0.86, cc * 0.80, cc * 0.78], 1) + spec[:, None]
    col[~hit] = (0.10, 0.10, 0.12)
    im = Image.fromarray((np.clip(col.reshape(size, size, 3), 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))
    if label:
        ImageDraw.Draw(im).text((6, 6), label, fill=(240, 240, 240))
    if hits:
        return im, pos.numpy().astype(np.float64), hit
    return im
