"""AX2 (10-28, the lead's call): THE AXOLOTL'S BODY AS ONE SUBDIVISION SURFACE, the head first (work/bestiary/research/
AXOLOTL_PLAN.md §5.4's fallback taken from the start: the wolf's W2j and the beetle's B3g printed a lump for every
analytic piece they composed, so the axolotl's head is never composed). ONE closed quad cage runs from the snout to the
tail tip: its rings are the body's cross-sections, measured; its edge loops sit on the head's features: the MOUTH LINE
(a creased loop round the snout and back along each side to the commissure, the lower lip tucked under the upper),
the LIDLESS EYES (a tube of rings inserted in a square ring of the grid: the skin's collar, its edge on the eyeball,
the tuck under the ball), the GILL BASES (columns through the three bases on the gill line's ring, which is also the
GULAR loop across the throat) and the NARES (pinned, dimpled vertices). Catmull-Clark with semi-sharp creases
(forge/subdiv_sharp.py, DeRose, Kass & Truong 1998) where the face has them, smooth everywhere else by construction.
Its limit mesh becomes the body's signed-distance GRID (the exact distance to its triangles, the winding number's
sign, on Warp's device: heads/insect_cage.py's route), so the clay's program (families/sprawl.clay_program) unions
the limbs, the gill rami, the eyes and the fins on it. The trunk and the tail are the same surface: there is no head
to neck seam to blend.

THE FRAME AND UNITS: LIFE millimetres in the plan frame of the bind (x lateral, + the creature's left; y up; z forward,
z = (s_hip - s) TL), s the station (TL fraction from the snout tip). families/sprawl.py scales to metres at x4.

THE SECTIONS (Body): at station s, a closed curve symmetric about x = 0, made of two superellipse halves meeting at the
widest level yw(s): the upper half from the dorsal midline (0, top) to (hw, yw) with exponent n_top, the lower half to
the ventral midline (0, bot) with n_bot, their exponents and half heights eased into each other across the junction
(no curvature jump: AX2's first look printed one as a crease along the cheeks). Their measures, from the SPEC
(species/axolotl.py):
  top, bot    the head (s <= 0.18): p01's dorsal and ventral lines rotated level about the snout tip
              (profile.head_side_x2, AX2's reading: the head axis pitched 17.9 deg in p01), the snout tip at the AO's
              height (families/sprawl.section); the trunk (0.20 .. the vent): the belly line and the core depth (§2.2);
              the tail: the core about the column's line falling to rest.tail_tip_h (sprawl.section), AX0b's shared core;
              blended (smoothstep) over 0.18-0.20
  hw          widths.profile_x2: p09's plan widths over its head maximum (my edge trace, AX2), x HW; the snout's last
              0.025 TL an elliptic arc round at the tip and tangent to the trace there (Body.width_frac); behind p09's
              visible tail, half the core depth x a falling aspect
  yw, n       SECTION's tables [E]: the cheeks' widest level and the head's rounded box (p13's frontal outline), the
              trunk's flatter belly, the tail's lens
THE CAGE (Topo): rings at STATIONS (dense on the head, the named stations snapped), J + 1 columns a half ring (0 the
dorsal midline, J the ventral), the SNOUT CAP a (hx x ny) grid whose row b_mouth is the mouth line across the front,
the TAIL CAP a thin grid; the half cage is mirrored and welded on the midline. Each ring's columns sit at arc-length
fractions of its half section with ANCHORS (column 0, the mouth / flank column j_mouth, column J; on the gill ring the
three gill bases' columns), evenly between anchors.
THE FIT (fit_cage): least squares, the limit surface at the cage's vertices against the targets (features weighted
FIT w_feat, the rest w_free) plus FIT lam times the squared umbrella Laplacian of (controls - targets) (fairness that
keeps the controls' offsets smooth); then the cage is subdivided to the limit (LEVELS).
"""
import hashlib
import json
import math
import os
import time

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from ..mesh import QuadMesh
from .. import subdiv_sharp as SS

VERSION = 'ax13-a'         # (the cache key: bumped with every change to the construction's code; f: AX7's eye out;
#                            g: the eye's inner rings at even spoke angles; h: AX7b's smile, mouth_height; i: AX7c's
#                            smile across the front (smile_y / mouth_point), the deeper snout cap, the lip lobes;
#                            j: the U ends at the lobes, the lobes under the margin, on the lower lip's rows; k: AX8's
#                            beads (two a side, lobe_weight sums them), their rings, the snout's widest-level floor;
#                            ax10-a: the beads as pearls, the lower lip's dense rows and the beads' finer rings, the
#                            corner's fold; b: the fold starts at the U's end; ax13-a: the beads off the skin when the
#                            pearls are parts (pearls_are_parts))

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
CACHE = os.path.join(REPO, 'work', 'bestiary', 'axolotl', 'cache')


def pearls_are_parts(spec):
    """AX13: the pearls are separate glass droplets (species/axolotl_pearls.py; SPEC ax13 pearls 'parts'): the clay
    carries no bead (no pearl domes, no margin dip, no dense rows under them), its lower lip runs smooth under where the
    droplets rest. The lobe record keeps the beads' places along the line (the droplets' chart) at zero bulge and drop"""
    return (spec.get('ax13') or {}).get('pearls') == 'parts'

# ============================================================================================ the layout
LAYOUT = dict(
    J=24,                      # half-ring edges: K = 48 round the body
    cap=(6, 12),               # the snout cap (hx, ny): 2 hx + ny = J; its row b_mouth meets column hx + b_mouth
    tail_cap=(2, 20),          # the tail cap: the tail's last section is a tall thin lens
    b_mouth=8,                 # so j_mouth = 6 + 8 = 14
    s0=0.012,                  # the first ring (the snout cap spans 0 .. s0: 2.9 mm of dome). AX7c: was 0.008 (1.9 mm),
    #                            whose bottom (12.75 mm) bounded the mouth's front 1.4 mm under the corner, so AX7b's
    #                            smile could only dip 0.35 mm at the front (its 1.8 mm folded the cap); at 0.012 ring 0's
    #                            bottom is 11.54 and the front takes the U the photos show (smile_y)
    s_end=0.986,               # the last ring (the tail cap spans s_end .. 1)
    # ring spacing (life mm) up to each station: dense over the snout, the eye and the mouth, then the head, the neck.
    # AX8: THE LIP'S BEADS' RINGS, a third of 1.25 mm to s 0.0224 and half of it to 0.0275: the lobe's resolution along
    # the line is the rings' (the AX7c check: a lobe asked a third as wide still measured 0.109 HW), and two beads ~3 mm
    # long, touching, need 4-5 vertices each where 1.25 mm rings put 1.6-2.6 mm of line between vertices. Both segments
    # end on the old stations (s0 + k 1.25 mm), so the eye block's rings (from 0.0275) and every ring behind it stay put
    # AX10: a fifth of 1.25 mm over both bead segments (0.42 / 0.625 mm rings along a line that runs diagonally there put
    # 0.6-1.0 mm of line between vertices, 3-4 per bead: a round pearl needs ~6); the segments' ends stay put
    spacing=((0.02236, 1.25 / 5.0), (0.02755, 1.25 / 5.0), (0.065, 1.25), (0.135, 1.5), (0.215, 1.8), (0.56, 2.6),
             (0.93, 3.0), (1.0, 2.0)),
    # AX10: THE LOWER LIP'S ROWS UNDER THE BEADS: on the beads' rings the first n rows under the margin `step` mm of arc
    # apart (the natural even columns put them ~1.0-1.2 mm apart there, two rows per bead: a bump of controls that coarse
    # subdivides to a flat lobe), easing back to the even columns over `ease` TL outside the span s (with SPEC ax10's
    # beads only)
    lip_rows=dict(n=6, step=0.50, s=(0.0125, 0.0270), ease=0.004),
    eye_half=2,                # the eye's square ring: rings i_e +- 2, columns j_e +- 2 (16 spokes)
    eye_j=6,
    gill_j=(9, 11, 13),        # the three gill bases' columns on the gill ring (r1, r2, r3)
    gill_blend=3,              # rings over which the gill anchors ease into the default columns
    gular_cols=7,              # the gular loop: the gill ring's ventral 7 edges each side
)

# the section's shape [E] (p13's frontal outline, the eye and the nares on the surface; tuned at AX2): tables over s
SECTION = dict(
    # the widest level: on the head an absolute height (the cheeks, p13: 0.566 of the frontal height below the top), on
    # the trunk and tail a share of the section's depth above its bottom; the head value eases into the trunk's
    yw_head=15.0, yw_front=((0.0, 13.0), (0.02, 13.6), (0.05, 14.6), (0.09, 15.0)), yw_share_trunk=0.46,
    yw_share_tail=0.5,
    # the widest level's floor over the section's bottom, a share of its height (yw never lower). AX8, 10-31: 0.15 all
    # along held the snout's first sections at it (the bottom line rises to the tip faster than yw_front), so their lower
    # halves were slabs 7.7 x 1.1 mm (s 0.008): the natural front turned 18-19 deg within 0.5 mm along the locus of their
    # widest points, a crease from (x 5.5, y 15) down across the mouth line at x 8.3 (ax8_notes/front_table.py): the
    # AX7c check's nick on the line and its soft shading edge from the nostril to the lip. So the floor rises toward the
    # tip, 0.42 of the height there, and comes down gently to meet yw_front at s 0.04 (14.25 mm there: share 0.32): every
    # row of the front then turns at most 6-8 deg per 0.5 mm, the mouth line's plan at most 12 deg at a cage vertex (30 at
    # the cap's last); a floor dropping to 0.15 by s 0.03 moved the crease onto the jaw (15-23 deg at x 10-12.5)
    yw_floor=((0.0, 0.42), (0.012, 0.40), (0.02, 0.37), (0.03, 0.34), (0.04, 0.32), (0.05, 0.15), (1.0, 0.15)),
    # the exponents (2 = an ellipse, larger = boxier): p13's frontal outline reads n ~2.2-2.6 above the cheeks and an
    # ellipse below them (AX2's first look: 2.9 / 2.5 made square top corners and a hard lower edge along the head)
    n_top=((0.0, 2.0), (0.03, 2.0), (0.07, 2.2), (0.12, 2.4), (0.18, 2.4), (0.23, 2.35), (0.55, 2.3), (0.65, 2.1),
           (1.0, 2.0)),
    n_bot=((0.0, 2.0), (0.10, 2.05), (0.18, 2.15), (0.23, 2.5), (0.50, 2.6), (0.58, 2.2), (1.0, 2.0)),
    snout_apex=0.040,          # the snout's elliptic arc over its last 0.040 TL, tangent to p09's trace there (AX7c: was
    #                            0.025, an arc 13.3 mm across by 8.5 mm along: at the mouth's height the front ran flat
    #                            across +-8-10 mm and turned back hard at ~0.28 HW, the "bathtub" smile's hooks; p11's
    #                            dorsal view is rounder, 0.41 / 0.59 HW wide 2 / 4.8 mm behind the tip against 0.49 /
    #                            0.67; at 0.040 the arc gives 0.42 / 0.62, tangent to the trace at the eyes' station)
    neck_blend=(0.16, 0.23),   # the head's side profile eases into the trunk's (smoothstep)
    width_smooth=(0.004, 0.014),   # p09's widths smoothed (Gaussian sigma, TL) on the head and on the trunk
    junction=0.45,             # rad: the section's upper and lower halves ease into each other about the widest point
    # behind p09's visible tail: the half width = the aspect x half the core depth
    tail_aspect=((0.62, 0.76), (0.75, 0.60), (0.90, 0.45), (1.0, 0.35)),
)

# the features
FEATURES = dict(
    # the mouth line: proud of the natural surface (the upper lip), the lower lip's column tucked under it (the smile:
    # most at the corners), both fading over `fade` TL behind the commissure; the line itself at p13's 0.613 of the
    # frontal height below the top [P p13]
    mouth=dict(proud=0.10, tuck_front=0.10, tuck_corner=0.50, ease=(0.006, 0.010), lobe_tuck=0.0, lobe_soft=0.15,
               lobe_q=3.0, lobe_rows=((-1, 0.10), (1, 0.5), (2, 0.9), (3, 0.55), (4, 0.18)),
               tuck_s=((0.0, 0.10), (0.008, 0.10), (0.016, 0.40), (0.035, 0.45), (0.08, 0.50)), bead_post=True),
    # (AX8, bead_post: the beads displace the FITTED controls of their rows (fit_cage), every target staying on the smooth
    # lip. As displaced targets on the beads' dense rings they printed ripples up the snout's side, a band at each ring:
    # the face's rows answered the bead rows' oscillating controls, the next rows answered theirs (probe/ripple_test*.png:
    # gone with the beads flat, kept with AX7c's tuck, a fit weight of 0.2 or a rounder bump). On the controls a bead is
    # the subdivision's own smooth bump, and the margin's crease keeps it off the face)
    # (AX8, tuck_s: the lower lip's tuck under the upper by station, in place of tuck_front + (corner - front) (s / s_c)^2,
    # which held it to 0.10-0.14 mm over the snout's sides: there the lips met flush (the AX7c low's lower lip 0.0-0.2 mm
    # under the upper from x 10 to 12.5, ax8_notes/lip_loop.py) between the front, where the face's own slope set it 0.68
    # mm back, and the corner's 0.4-0.47; the groove's facing turned within two vertices at the snout's corner (the AX7c
    # check's nick) and the corner's fold had no overhang to come from. Now the upper lip folds over the lower all round
    # the U as p13 / p15 show, the front's pale band (0.10, AX7c's) kept)
    # (AX7c's lobes, build_cage: lobe_rows ((rows under the margin, share of the bulge), ...): THE LOBES HANG UNDER THE
    # MARGIN, on the lower lip's rows, as p14 / p15's do: the first build put them on the margin itself (it hung the
    # margin 0.9 mm and stood it 1 mm out), and the eye read a flat-bottomed trapezoid with fangs (0.9 mm on top of the
    # U's 0.68 mm there nearly reaches its 1.7 at the midline) and, on the far side from three quarters, the lobe's point
    # in silhouette as a beak; the row above the margin keeps a tenth of the swell, p13's fuller lip. The rows fall off
    # over two past the lobe's fullest (0.30 then nothing printed a corner on the jaw's 3/4 outline: AX2's views, probe
    # y012.png). The lobe's sizes are SPEC ax7c's. lobe_q: the bump's flatness (bump), a rounded lobe; lobe_tuck: how much
    # more the lower lip's row tucks under the lobe, lobe_soft: how much the margin's crease softens through it (both
    # small now the margin stays a line). tuck_front 0.18 -> 0.10: p13 / p15 show the lower lip as a pale band under the
    # upper's middle, where 0.18 hid it under the ledge)
    # the eye (lidless, the octopus eye port without its lid): the rim on the face, the crest (the skin's collar,
    # raised), the edge on the ball, the tuck under it; radii over the visible eye's radius, heights in mm along the
    # eye's axis from the edge plane; the ball (sprawl's member) of radius ball x r_eye
    # (AX2's first look: the joint sat 1.2 mm under the natural surface and a 0.3 mm collar at 1.28 r made a socket, a
    # doll's eye in a ring: the edge's centre now moves out `out` of the way to the natural surface, and the collar hugs
    # the ball. AX7's eye round, 10-29: with out 0.35 the edge plane still sat 0.65 mm under the natural surface and
    # the skin stood 1.3-1.6 mm over it behind and below (the axis 21 deg off the head's normal); with the SPEC's axis
    # turned toward that normal (rig.eye_axis) and out 0.80, the skin over the edge plane is +0.06..+0.24 mm at
    # 1.05-1.3 r_e all round on the fitted cage: an even soft collar, the ball's pole 0.86 mm over it)
    eye=dict(rim=1.70, crest=1.14, crest_h=0.12, edge=1.0, tuck=0.80, tuck_h=-0.55, core=0.42, core_h=-1.3, ball=1.18,
             rim_pull=0.6, out=0.80),
    nares=dict(dimple=0.25),
    gular=dict(tuck=0.30),
)
SMILE_KEYS = ('corner_up', 'smile_U', 'smile_c', 'smile_xU', 'lobe_x', 'lobe_w', 'lobe_bulge', 'lobe_drop')   # SPEC ax7c's
BEAD_KEYS = ('beads_x', 'bead_w', 'bead_bulge', 'bead_drop')                                                 # SPEC ax8's
BEAD10_KEYS = ('beads_x', 'bead_ra', 'bead_rb', 'bead_dc', 'bead_h', 'bead_p', 'bead_hang', 'bead_up', 'bead_out',
               'bead_drop', 'fold_s', 'fold_drop', 'fold_corner', 'fold_out', 'fold_tuck', 'fold_end')     # SPEC ax10's
SHARP = dict(mouth=1.5, mouth_front=1.0, mouth_end=(1.0, 0.4), gular=0.7)
LEVELS = dict(fit=3, out=3)
FIT = dict(w_feat=30.0, w_free=1.0, w_inner=0.2, lam=0.25)
# THE BODY'S FIELD (body_field): the exact signed distance to the limit mesh within `band` of the surface, a coarse
# pass (coarse x h, trilinear) beyond, clamped (the clay's largest blend is the limbs' 2.5 mm: the clamp keeps the
# GRID's divisor near 1, sdf_grid.md), the far field blurred s_far
BODY_FIELD = dict(h=0.25, pad=3.0, coarse=4, band=1.2, s_far=0.4, clamp=(-5.0, 5.0), s_near=0.18)
#   (s_near: a last blur of the whole field: the thin tail tip, the eye's tube and the lip's groove put medial creases
#   inside the exact band, whose cells' steepest edges set the GRID's proved divisor (1.52 at AX2's first run: the whole
#   field read 0.66 of the distance); a 0.18 mm blur rounds them)


def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mouth_height(frontal, s):
    """THE SMILE (AX7b, 10-30): the mouth line's height (life mm) at station s. The round-6 line ran level at p13's
    0.613 of the frontal height below the top all the way round, and read straight with its corners turning down; p15
    (frontal: a U, the corners 0.05-0.06 HW over the front), p18 (lateral) and p13 show it rising toward each corner. The
    line runs from `down` under p13's height at the front to `up` over it at the corner: y_c - down + (down + up) (s /
    s_c)^p, flat across the front and rising toward the corner (SPEC ax7b.smile_down_built / smile_up_built /
    smile_power: the front is bounded by the snout's section, the corners by AX2's gate 5); level behind the commissure.
    frontal: build_cage's record (its 'smile': (up, down, p, s_c); without it the old level line)"""
    y_c = frontal['mouth']
    up, down, p, s_c = frontal.get('smile', (0.0, 0.0, 1.0, 1.0))
    u = np.clip(np.asarray(s, np.float64) / s_c, 0.0, 1.0)
    return y_c - down + (down + up) * u ** p


def bump(t, q=2.0):
    """a smooth bump of half-width 1: (1 - |t|^q)^2 inside, 0 outside (C1 at its ends); q over 2 is flatter across the
    middle"""
    t = np.clip(np.abs(np.asarray(t, np.float64)), 0.0, 1.0)
    return (1.0 - t ** q) ** 2


def smile_y(frontal, x, s=None):
    """AX7c, 10-30: THE SMILE ACROSS THE FRONT: the mouth line's height (life mm) at the lateral offset x. AX7b's line
    rose with the station (mouth_height): level along the snout cap's row and across the snout's truncate front (at the
    mouth's height the front surface is flat across +-8-10 mm: ax7c_notes/snout_table.py), then up where the line turns
    back along the side, so from the front it read as one flat line hooking up at the outline (a bathtub from a raised
    camera: ax7c_notes/probe/base.png), where p15 curves all the way across and p13 / p14 turn up behind their lobes.
    Now the height is a law of x (frontal['smile_x'] = (y_corner, D, c, x_c, x_U), x_c the commissure's offset), so the
    U shows from the front at every x, and it ENDS AT x_U: p15's line has done its whole rise by 0.37 HW, at the lobes,
    where its dark slit ends; beyond them the mouth is a faint fold to the true corner at 0.45 HW, so a U spread to the
    corner reads wide and flat. u = |x| / x_U:
      inside x_U: y_U - D (1 - h(u)), h(u) = (1 + c) u^2 / (u^2 + c): round at the midline (a power under 2 has a soft V
        there, ax7c_notes/probe/x1z_row.png) and rising early: c 1.2 gives p15's shares of the rise, 0.26 / 0.61 at
        0.15 / 0.25 HW against its 0.25 / 0.58;
      past x_U: a shoulder to the commissure, its slope falling to 0: y_U + m t (1 - t / (2 T)), t = |x| - x_U, T = x_c -
        x_U, m the U's slope at x_U, so the line has no kink and y_U = y_corner - m T / 2.
    The margin hangs `drop` lower at the lobes (a touch: the lobes themselves hang under it, build_cage). Without
    'smile_x' it is AX7b's mouth_height at s"""
    sm = frontal.get('smile_x')
    if sm is None:
        return float(mouth_height(frontal, 0.0 if s is None else s))
    y_corner, D, c, x_c, x_U = sm
    m, T = D * 2.0 * c / ((1.0 + c) * x_U), x_c - x_U
    y_U = y_corner - 0.5 * m * T
    ax = abs(float(x))
    if ax <= x_U:
        u2 = (ax / x_U) ** 2
        y = y_U - D * (1.0 - (1.0 + c) * u2 / (u2 + c))
    else:
        t = min(ax - x_U, T)
        y = y_U + m * t * (1.0 - t / (2.0 * T))
    lob = frontal.get('lobe')
    if lob is not None:
        y -= lob['drop'] * lobe_weight(frontal, s, x)
    if frontal.get('fold') is not None and s is not None:
        y -= frontal['fold']['drop'] * fold_weight(frontal, s)          # AX10: the corner's fold (fold_weight)
    return float(y)


def fold_weight(frontal, s):
    """AX10: THE CORNER'S FLESHY FOLD (p14's near end: past the beads the upper lip's margin sags into a rounded fleshy
    lobe over the lower lip and rolls back up into the cheek at the corner; p15's line hooks down at its ends): its
    weight at station s (0 .. 1), rising from fold s[0] (where the U ends) to s[1], full to s[2], down to `corner` of
    it at the commissure; past the commissure (the roll only: the line is no longer the mouth) it fades over `end` TL.
    The sag is smile_y's (the line's height: the low's lip column follows it through mouth_point), the roll and the
    tuck build_cage's"""
    fd = frontal.get('fold')
    if fd is None:
        return 0.0
    sa, sp, sq = fd['s']
    s_c = fd['s_c']
    if s <= sa:
        return 0.0
    if s < sp:
        return float(smooth01((s - sa) / (sp - sa)))
    if s <= sq:
        return 1.0
    if s <= s_c:
        return float(1.0 - (1.0 - fd['corner']) * smooth01((s - sq) / max(s_c - sq, 1e-9)))
    return float(fd['corner'] * (1.0 - smooth01((s - s_c) / fd['end'])))


def lobe_weight(frontal, s=None, x=None):
    """AX7c: the lobes' bump weight at a mouth-line point, by the line's ARC LENGTH from the midline (build_cage's
    tables, the line without its lobes), so a lobe may straddle the snout cap's row and the rings: a ring vertex reads it
    by its station, a cap vertex (s None or under the cap's ring 0) by its offset x. AX8: the record's beads (each
    (arc length, half-length)), their bumps summed and capped at 1 (AX7c's one lobe without them)"""
    lob = frontal.get('lobe')
    if lob is None:
        return 0.0
    if s is not None and s >= lob['s0'] - 1e-12:
        lam = float(np.interp(s, lob['s_tab'], lob['lam_s']))
    else:
        lam = float(np.interp(abs(float(x)), lob['x_tab'], lob['lam_x']))
    q = FEATURES['mouth']['lobe_q']
    beads = lob.get('beads') or [(lob['lam_L'], lob['w'])]
    return float(min(1.0, sum(bump((lam - lc) / w, q) for lc, w in beads)))


def frac_at_y(body, s, y):
    """the half section's arc fraction at height y, on its lower half below the widest level and its upper half above
    it (frac_at_height(lower=True) clamps at the widest level: AX7b's corners, asked 1.2 mm up, sat there at 14.90)"""
    return body.frac_at_height(s, y, lower=bool(y <= body.yw(s)))


def mouth_point(body, frontal, s, it=16):
    """AX7c: the mouth line's point at station s on the natural half section: (arc fraction, x, y) with y = smile_y(x,
    s), a fixed point (x moves little with y there: the section's side near its widest level is steep). Without
    'smile_x' AX7b's station law"""
    if frontal.get('smile_x') is None:
        y = float(mouth_height(frontal, s))
        f = body.frac_at_height(s, y, lower=True)
        return f, float(body.at_frac(s, [f])[0, 0]), y
    y = float(frontal['smile_x'][0])
    for _ in range(it):
        f = frac_at_y(body, s, y)
        x = float(body.at_frac(s, [f])[0, 0])
        y_new = smile_y(frontal, x, s)
        if abs(y_new - y) < 1e-6:
            y = y_new
            break
        y = y_new
    f = frac_at_y(body, s, y)
    return f, float(body.at_frac(s, [f])[0, 0]), float(y)


def tab(table, s):
    """a (s, value) table at s, linear, clamped at its ends"""
    t = np.asarray(table, np.float64)
    return float(np.interp(s, t[:, 0], t[:, 1]))


# ============================================================================================ the sections
class Body:
    """the bind's body sections from the SPEC (module docstring), life mm"""

    def __init__(self, spec):
        from ..families import sprawl as SPR
        self.spec = spec
        a1, st, rs, rg, pr = spec['a1'], spec['stations'], spec['rest'], spec['rig'], spec['profile']
        self.TL, self.HW = a1['TL'], a1['HW']
        self.s_hip, self.s_vent = st['hip'], st['vent']
        sec = SPR.section(spec)
        self.sec = sec
        self.y_tip = sec['y_ao']                              # the snout tip level with the AO (the level head)
        self.belly = rs['belly']
        self.spine_frac = rg['spine_frac']
        self.head_side = np.asarray(pr['head_side_x2'], np.float64)      # (s, top, bot) TL about the snout's level
        self.wprof = self._smooth_widths(np.asarray(spec['widths']['profile_x2'], np.float64))
        self.core = lambda s: SPR.core_depth(spec, s) * self.TL      # noqa: E731
        self.col = sec['col']
        from scipy.interpolate import PchipInterpolator
        self._nt = PchipInterpolator(*np.asarray(SECTION['n_top'], np.float64).T, extrapolate=True)
        self._nb = PchipInterpolator(*np.asarray(SECTION['n_bot'], np.float64).T, extrapolate=True)

    @staticmethod
    def _smooth_widths(wp):
        """p09's width rows on a fine station grid (PCHIP), smoothed by a Gaussian whose width grows from the head's
        WIDTH_SMOOTH[0] to the trunk's [1] TL (the trace's row noise and the masked limb spans printed soft lumps on the
        flank, AX2's first look): the head keeps its shape, the trunk its measured swell"""
        from scipy.interpolate import PchipInterpolator
        s = np.arange(wp[0, 0], wp[-1, 0] + 1e-9, 0.001)
        v = PchipInterpolator(wp[:, 0], wp[:, 1])(s)
        sig = np.interp(s, [0.0, 0.17, 0.23, 1.0], [SECTION['width_smooth'][0]] * 2 + [SECTION['width_smooth'][1]] * 2)
        out = np.empty_like(v)
        for i, (si, gi) in enumerate(zip(s, sig)):
            w = np.exp(-0.5 * ((s - si) / gi) ** 2)
            out[i] = (w * v).sum() / w.sum()
        # the head's widest stays at its measured 1.0 (the smoothing must not shave HW)
        head = s <= 0.2
        out[head] *= v[head].max() / out[head].max()
        return np.column_stack([s, out])

    def z(self, s):
        return (self.s_hip - np.asarray(s, np.float64)) * self.TL

    def s_of(self, z):
        return self.s_hip - np.asarray(z, np.float64) / self.TL

    # ---- the side profile (bind)
    def head_tb(self, s):
        hs = self.head_side
        return (self.y_tip + np.interp(s, hs[:, 0], hs[:, 1]) * self.TL,
                self.y_tip + np.interp(s, hs[:, 0], hs[:, 2]) * self.TL)

    def trunk_tb(self, s):
        """the trunk on the belly line; behind the vent the tail's ventral line rises straight from the belly line to
        rest.tail_tip_h at the tip (the tail trailing low, v01: AX1's column runs 0.08 of the depth above this core's
        mid-depth, its spine_frac), the core's depth on it"""
        D = self.core(s)
        if s <= self.s_vent:
            return self.belly + D, self.belly
        b = self.belly + (self.spec['rest']['tail_tip_h'] - self.belly) * (s - self.s_vent) / (1.0 - self.s_vent)
        return b + D, b

    def top_bot(self, s):
        s = float(np.clip(s, 0.0, 1.0))
        a, e = SECTION['neck_blend']
        if s <= a:
            return self.head_tb(s)
        if s >= e:
            return self.trunk_tb(s)
        w = smooth01((s - a) / (e - a))
        th, bh = self.head_tb(min(s, 0.18))           # (the head table ends at 0.18: its last row held)
        tt, bt = self.trunk_tb(s)
        return (1 - w) * th + w * tt, (1 - w) * bh + w * bt

    # ---- the plan width
    def width_frac(self, s):
        """the plan width over HW. Ahead of SECTION snout_apex the snout is an ELLIPTIC ARC round at the tip and
        TANGENT to p09's trace at the apex station (its width and slope there): the AX2 restart's look found the plan's
        quarter-ellipse (flat where it meets a trace still widening at ~4 HW per TL) printing shoulders on the snout's
        corners in the top view. The arc: w(s) = B sqrt(s (2A - s)) / A, its semi-axes from w(a) = w0, w'(a) = m:
        A = a (1 - k) / (1 - 2k) with k = a m / w0 (k = 0 gives back the quarter-ellipse)"""
        wp = self.wprof
        a = SECTION['snout_apex']
        if s < a:
            w0 = float(np.interp(a, wp[:, 0], wp[:, 1]))
            m = (float(np.interp(a + 0.002, wp[:, 0], wp[:, 1])) - w0) / 0.002
            k = float(np.clip(a * m / w0, 0.0, 0.45))
            A = a * (1.0 - k) / (1.0 - 2.0 * k)
            B = w0 * A / np.sqrt(a * (2.0 * A - a))
            return float(B * np.sqrt(max(s * (2.0 * A - s), 0.0)) / A)
        return float(np.interp(s, wp[:, 0], wp[:, 1]))

    def hw(self, s):
        """the half width (mm)"""
        s = float(np.clip(s, 0.0, 1.0))
        end = float(self.wprof[-1, 0])
        h_p = 0.5 * self.width_frac(min(s, end)) * self.HW
        if s <= end:
            return h_p
        t, b = self.top_bot(s)
        h_a = 0.5 * tab(SECTION['tail_aspect'], s) * (t - b)
        w = smooth01((s - end) / 0.03)
        return (1 - w) * h_p + w * h_a if s < end + 0.03 else h_a

    # ---- the widest level and the exponents
    def yw(self, s):
        t, b = self.top_bot(s)
        if s <= 0.09:
            y = tab(SECTION['yw_front'], s)
        elif s <= 0.18:
            y = SECTION['yw_head']
        else:
            share = SECTION['yw_share_trunk'] if s <= self.s_vent else SECTION['yw_share_tail']
            y_t = b + share * (t - b)
            y = SECTION['yw_head'] + (y_t - SECTION['yw_head']) * smooth01((s - 0.18) / 0.05) if s < 0.23 else y_t
        return float(np.clip(y, b + tab(SECTION['yw_floor'], s) * (t - b), t - 0.15 * (t - b)))

    def half_section(self, s, m=720):
        """(m, 2) points (x >= 0, y) from the dorsal midline to the ventral midline, and their cumulative arc lengths.
        The exponent and the half height ease from the upper half's to the lower half's over +-SECTION junction rad
        about the widest point (AX2's first look: two halves meeting with different half heights jump in curvature
        there, a soft crease along the head at the cheeks' level)"""
        t, b = self.top_bot(s)
        hw = max(self.hw(s), 0.05)
        yw = self.yw(s)
        nt, nb = float(self._nt(s)), float(self._nb(s))
        ph = np.linspace(0.0, np.pi, m)
        dl = SECTION['junction']
        wj = smooth01((ph - (0.5 * np.pi - dl)) / (2.0 * dl))
        n = nt + (nb - nt) * wj
        hh = (t - yw) + ((yw - b) - (t - yw)) * wj
        sn, cs = np.sin(ph), np.cos(ph)
        x = hw * np.abs(sn) ** (2.0 / n)
        # both ends EXACTLY on the midline (sin(pi) is 1.2e-16, not 0): the polygon's closing edge then lies on x = 0,
        # and inside() no longer counts it as a crossing for a point on the midline (it read every midline point as
        # outside, so the snout and tail caps' midline columns stayed at their rings' stations: the AX2 restart's look
        # found a 1.7 mm notch down the snout's front and a forked tail tip)
        x[0] = x[-1] = 0.0
        y = yw + hh * np.sign(cs) * np.abs(cs) ** (2.0 / n)
        P = np.column_stack([x, y])
        L = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        return P, L

    def at_frac(self, s, fracs):
        P, L = self.half_section(s)
        f = np.asarray(fracs, np.float64) * L[-1]
        return np.column_stack([np.interp(f, L, P[:, 0]), np.interp(f, L, P[:, 1])])

    def frac_of_point(self, s, x, y):
        """the arc fraction of the half section's point nearest (x, y)"""
        P, L = self.half_section(s)
        i = int(np.argmin((P[:, 0] - x) ** 2 + (P[:, 1] - y) ** 2))
        return float(L[i] / L[-1])

    def frac_at_height(self, s, y, lower=True):
        """the arc fraction where the half section crosses height y on its lower (below yw) or upper half"""
        P, L = self.half_section(s)
        yw = self.yw(s)
        idx = np.nonzero(P[:, 1] <= yw)[0] if lower else np.nonzero(P[:, 1] >= yw)[0]
        Q, Lq = P[idx], L[idx]
        o = np.argsort(Q[:, 1])
        return float(np.interp(y, Q[o, 1], Lq[o]) / L[-1])

    def inside(self, x, y, s):
        """is the point (x, y) inside the section at station s: the crossing number of the half section's polygon (the
        curve closed by the midline) along +x from (|x|, y)"""
        P, _ = self.half_section(s, m=360)
        X, Y = P[:, 0], P[:, 1]
        X2, Y2 = np.roll(X, -1), np.roll(Y, -1)
        cond = (Y > y) != (Y2 > y)
        with np.errstate(divide='ignore', invalid='ignore'):
            xi = X + (y - Y) * (X2 - X) / np.where(cond, Y2 - Y, 1.0)
        return bool(np.count_nonzero(cond & (xi > abs(x))) % 2 == 1)

    def front_station(self, x, y, s_hi, s_lo=0.0, it=40):
        """the snout's natural front surface at (x, y): the least station in [s_lo, s_hi] whose section holds the
        point (bisection; the sections grow away from the tip); s_hi when even its section does not"""
        if not self.inside(x, y, s_hi):
            return s_hi
        lo, hi = s_lo, s_hi
        for _ in range(it):
            mid = 0.5 * (lo + hi)
            if self.inside(x, y, mid):
                hi = mid
            else:
                lo = mid
        return hi

    def back_station(self, x, y, s_lo, s_hi=1.0, it=40):
        """the tail tip's natural surface at (x, y): the largest station in [s_lo, s_hi] whose section holds the point"""
        if not self.inside(x, y, s_lo):
            return s_lo
        lo, hi = s_lo, s_hi
        for _ in range(it):
            mid = 0.5 * (lo + hi)
            if self.inside(x, y, mid):
                lo = mid
            else:
                hi = mid
        return lo

    def surface_along(self, p, d, reach=8.0):
        """the natural surface's point on the line p + t d (plan frame mm), the crossing nearest p (bisection)"""
        d = np.asarray(d, np.float64) / np.linalg.norm(d)

        def ins(t):
            q = p + t * d
            return self.inside(q[0], q[1], float(self.s_of(q[2])))
        a0 = ins(0.0)
        ts = np.linspace(0.0, reach, 161)
        tsn = -ts
        for seq in (ts, tsn):
            prev = 0.0
            for t in seq[1:]:
                if ins(t) != a0:
                    lo, hi = prev, t
                    for _ in range(40):
                        mid = 0.5 * (lo + hi)
                        if ins(mid) == a0:
                            lo = mid
                        else:
                            hi = mid
                    return p + 0.5 * (lo + hi) * d, 0.5 * (lo + hi)
                prev = t
        return None, None


# ============================================================================================ the stations
def make_stations(spec):
    """the rings' stations: the spacing table's steps, the named stations snapped to their nearest ring"""
    TL = spec['a1']['TL']
    st = spec['stations']
    L = LAYOUT
    s, out = L['s0'], [L['s0']]
    for upto, mm in L['spacing']:
        while s + mm / TL <= min(upto, L['s_end']) + 1e-9:
            s += mm / TL
            out.append(s)
    if out[-1] < L['s_end'] - 0.5 / TL:
        out.append(L['s_end'])
    else:
        out[-1] = L['s_end']
    out = np.array(out)
    named = dict(eye=st['eye_c_x0b'], commissure=st['commissure'], gill=st['gill_base'], shoulder=st['shoulder_joint'],
                 hip=st['hip'], vent=st['vent'])
    idx = {}
    for nm, v in named.items():
        i = int(np.argmin(np.abs(out - v)))
        out[i] = v
        idx[nm] = i
    assert np.all(np.diff(out) > 0), 'stations must increase'
    return out, idx


# ============================================================================================ the topology
class Topo:
    """the half cage (x >= 0): rings R[i, j], the snout cap C[a, b], the tail cap T[a, b], the eye's inserted tube"""

    def __init__(self, n_rings, idx):
        L = LAYOUT
        J = L['J']
        self.J, self.N = J, n_rings
        hx, ny = L['cap']
        tx, ty = L['tail_cap']
        assert 2 * hx + ny == J and 2 * tx + ty == J
        self.R = np.arange(n_rings * (J + 1)).reshape(n_rings, J + 1)
        cnt = self.R.size
        # the snout cap: boundary ids from ring 0, interior new
        self.C = np.full((hx + 1, ny + 1), -1, int)
        for a in range(hx + 1):
            self.C[a, 0] = self.R[0, a]
            self.C[a, ny] = self.R[0, J - a]
        for b in range(ny + 1):
            self.C[hx, b] = self.R[0, hx + b]
        for a in range(hx):
            for b in range(1, ny):
                self.C[a, b] = cnt
                cnt += 1
        self.T = np.full((tx + 1, ty + 1), -1, int)
        last = n_rings - 1
        for a in range(tx + 1):
            self.T[a, 0] = self.R[last, a]
            self.T[a, ty] = self.R[last, J - a]
        for b in range(ty + 1):
            self.T[tx, b] = self.R[last, tx + b]
        for a in range(tx):
            for b in range(1, ty):
                self.T[a, b] = cnt
                cnt += 1
        self.n_half = cnt
        Q = []
        for i in range(n_rings - 1):
            for j in range(J):
                Q.append((self.R[i, j], self.R[i, j + 1], self.R[i + 1, j + 1], self.R[i + 1, j]))
        self.q_body = len(Q)
        for a in range(hx):
            for b in range(ny):
                Q.append((self.C[a, b], self.C[a, b + 1], self.C[a + 1, b + 1], self.C[a + 1, b]))
        for a in range(tx):
            for b in range(ty):
                Q.append((self.T[a, b], self.T[a + 1, b], self.T[a + 1, b + 1], self.T[a, b + 1]))
        self.Qh = np.array(Q, int)
        self.sharp_h = {}
        # the eye's tube in its square ring
        e, h = idx['eye'], L['eye_half']
        je = L['eye_j']
        self.eye_block = (e - h, e + h, je - h, je + h)
        i0, i1, j0, j1 = self.eye_block
        cells = ([(i0, j) for j in range(j0, j1)] + [(i, j1) for i in range(i0, i1)] +
                 [(i1, j) for j in range(j1, j0, -1)] + [(i, j0) for i in range(i1, i0, -1)])
        self.eye_rim_cells = cells
        self.eye_rim = [int(self.R[i, j]) for (i, j) in cells]
        inner_q = [i * J + j for i in range(i0, i1) for j in range(j0, j1)]
        self.eye_inner = [int(self.R[i, j]) for i in range(i0 + 1, i1) for j in range(j0 + 1, j1)]
        self.eye_rings = self.insert_tube(self.eye_rim, inner_q, 3)      # crest, edge, tuck

    def insert_tube(self, rim, inner_quads, n):
        """n new rings between the closed loop `rim` and the quads `inner_quads` it encloses (their rim vertices moved
        to the innermost ring), quad strips between, each strip's winding the inner quads' (canid_cage's rule)"""
        m = len(rim)
        rings = []
        for _ in range(n):
            rings.append(list(range(self.n_half, self.n_half + m)))
            self.n_half += m
        pos = {v: j for j, v in enumerate(rim)}
        Qh = self.Qh.copy()
        dirs = {}
        for qi in inner_quads:
            q = Qh[qi]
            for c in range(4):
                a, b = int(q[c]), int(q[(c + 1) % 4])
                if a in pos and b in pos:
                    ja, jb = pos[a], pos[b]
                    if (jb - ja) % m == 1:
                        dirs[ja] = True
                    elif (ja - jb) % m == 1:
                        dirs[jb] = False
        assert len(dirs) == m, f'the rim\'s edges in the inner quads: {len(dirs)} of {m}'
        last = rings[-1]
        for qi in inner_quads:
            Qh[qi] = [last[pos[int(v)]] if int(v) in pos else int(v) for v in Qh[qi]]
        new = []
        chain = [list(rim)] + rings
        for A, B in zip(chain[:-1], chain[1:]):
            for j in range(m):
                j1 = (j + 1) % m
                if dirs[j]:
                    new.append((A[j], A[j1], B[j1], B[j]))
                else:
                    new.append((A[j1], A[j], B[j], B[j1]))
        self.Qh = np.vstack([Qh, np.array(new, int)])
        return rings

    def midline(self):
        ids = set(self.R[:, 0].tolist()) | set(self.R[:, self.J].tolist()) | set(self.C[0, :].tolist()) | \
            set(self.T[0, :].tolist())
        return np.array(sorted(ids), int)

    def crease(self, pairs, s):
        for (a, b), v in zip(pairs, np.broadcast_to(np.asarray(s, np.float64), (len(pairs),))):
            if v > 0:
                self.sharp_h[(min(int(a), int(b)), max(int(a), int(b)))] = float(v)

    def full(self, P_half):
        """the full mesh (the half and its mirror x -> -x, welded on the midline): QuadMesh, the half -> mirror map, the
        full sharpness dict"""
        mid = self.midline()
        is_mid = np.zeros(self.n_half, bool)
        is_mid[mid] = True
        off = np.cumsum(~is_mid) - 1 + self.n_half
        mir = np.where(is_mid, np.arange(self.n_half), off)
        n = self.n_half + int((~is_mid).sum())
        V = np.zeros((n, 3))
        V[:self.n_half] = P_half
        V[mid, 0] = 0.0
        Pm = np.asarray(P_half, np.float64).copy()
        Pm[:, 0] *= -1.0
        V[mir[~is_mid]] = Pm[~is_mid]
        Q = np.vstack([self.Qh, mir[self.Qh][:, ::-1]])
        sharp = {}
        for (a, b), s in self.sharp_h.items():
            sharp[(min(a, b), max(a, b))] = s
            sharp[(min(mir[a], mir[b]), max(mir[a], mir[b]))] = s
        return QuadMesh(V, Q), mir, sharp

    def adjacency(self, n, Q):
        E = np.concatenate([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]]])
        E = np.unique(np.sort(E, axis=1), axis=0)
        return sp.csr_matrix((np.ones(2 * len(E)), (np.concatenate([E[:, 0], E[:, 1]]),
                                                    np.concatenate([E[:, 1], E[:, 0]]))), shape=(n, n))


# ============================================================================================ the placement
def coons(top, bot, left, right):
    """a Coons patch: top[a], bot[a] (a = 0..na), left[b], right[b] (b = 0..nb) -> P[a, b] (corners shared)"""
    na, nb = len(top) - 1, len(left) - 1
    P = np.zeros((na + 1, nb + 1, top.shape[1]))
    for a in range(na + 1):
        u = a / na
        for b in range(nb + 1):
            v = b / nb
            P[a, b] = ((1 - v) * top[a] + v * bot[a] + (1 - u) * left[b] + u * right[b]
                       - ((1 - u) * (1 - v) * top[0] + u * (1 - v) * top[na] + (1 - u) * v * bot[0] + u * v * bot[na]))
    return P


def eye_frame(spec):
    """the eye's axis (unit, the left eye) and two chart axes across it"""
    a = np.asarray(spec['rig']['eye_axis'], np.float64)
    a = a / np.linalg.norm(a)
    u = np.cross(a, [0.0, 0.0, 1.0])
    if np.linalg.norm(u) < 1e-6:
        u = np.cross(a, [0.0, 1.0, 0.0])
    u /= np.linalg.norm(u)
    v = np.cross(a, u)
    return a, u, v


def build_cage(spec, log=print):
    """the targets, the topology, the creases, the weights and the features' records (module docstring)"""
    t0 = time.time()
    from ..families import sprawl as SPR
    body = Body(spec)
    stations, idx = make_stations(spec)
    topo = Topo(len(stations), idx)
    L, J = LAYOUT, LAYOUT['J']
    hx, ny = L['cap']
    tx, ty = L['tail_cap']
    bm = L['b_mouth']
    jm = hx + bm
    st, hd = spec['stations'], spec['head']
    TL, HW = body.TL, body.HW
    P = np.full((topo.n_half, 3), np.nan)
    w = np.full(topo.n_half, FIT['w_free'])
    tags = {}
    # ---- the frontal box (the bind's head): the top's highest point and the head's lowest, for p13's fractions
    ss = np.linspace(0.0, st['gill_base'], 400)
    tb = np.array([body.top_bot(s) for s in ss])
    y_top_max, y_bot_min = float(tb[:, 0].max()), float(tb[:, 1].min())
    H = y_top_max - y_bot_min
    y_mouth = y_top_max - hd['mouth_frontal'][0] * H
    s_c = st['commissure']
    a7 = spec.get('ax7b')
    smile = (a7['smile_up_built'], a7['smile_down_built'], a7['smile_power'], s_c) if a7 else (0.0, 0.0, 1.0, s_c)
    fr_rec = dict(mouth=y_mouth, smile=smile)
    y_line = lambda s: float(mouth_height(fr_rec, s))                  # noqa: E731  the smile (mouth_height)
    a7c = spec.get('ax7c')
    if a7c:
        # AX7c: the smile across the front (smile_y): the corner `corner_up` over p13's level (AX2 gate 5 holds it), its
        # offset x_c on the commissure's section, the U's depth D at the midline, its end x_U; then the lobes' station,
        # where the line (without its lobes) reaches lobe_x HW off the midline
        y_corner = y_mouth + a7c['corner_up']
        f_c = frac_at_y(body, s_c, y_corner)
        x_c = float(body.at_frac(s_c, [f_c])[0, 0])
        x_U = min(float(a7c['smile_xU']) * HW, x_c - 0.5)
        fr_rec['smile_x'] = (float(y_corner), float(a7c['smile_U']), float(a7c['smile_c']), x_c, x_U)
        # the line without its lobes, as a polyline from the midline: across the snout cap on its natural front surface
        # at the U's height, then the rings' points to the commissure; its arc length is the lobes' coordinate
        ss_ = np.linspace(L['s0'], s_c, 60)
        ring_pts = np.array([mouth_point(body, fr_rec, s_)[1:] for s_ in ss_])          # (x, y)
        assert np.all(np.diff(ring_pts[:, 0]) > 0), 'the mouth line\'s offset must grow toward the corner'
        xs_cap = np.linspace(0.0, ring_pts[0, 0], 41)[:-1]
        cap_pts = np.array([(x_, smile_y(fr_rec, x_), float(body.z(body.front_station(x_, smile_y(fr_rec, x_), L['s0']))))
                            for x_ in xs_cap])
        poly = np.vstack([cap_pts, np.column_stack([ring_pts, body.z(ss_)])])
        lam = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(poly, axis=0), axis=1))])
        n_cap = len(cap_pts)
        lam_L = float(np.interp(a7c['lobe_x'] * HW, poly[:, 0], lam))
        a8 = spec.get('ax8') or {}
        a10 = spec.get('ax10') or {}
        pearl = None
        if 'beads_x' in a10:
            # AX10: THE BEADS AS PEARLS (p14 / p15: round, proud, glassy, hanging under the margin at each end of the U;
            # AX8's two bumps along the line were flat lobes, a third as proud as they were wide): each a dome over a
            # ROUND footprint in the lip's own chart (the line's arc along, the arc down the column across), its centre
            # bead_dc mm under the margin, bead_ra / bead_rb its half-sizes there (bead_up of rb above the centre: the
            # top pinched under the margin); the controls in it move bead_h x (1 - r^2)^bead_p out along the skin's
            # normal tipped down the column by bead_hang, and out from its centre within the skin by bead_out (its
            # equator wider than its foot); the lower lip's rows dense under it (LAYOUT lip_rows), the rings finer
            beads = [(float(np.interp(bx * HW, poly[:, 0], lam)), float(a10['bead_ra'])) for bx in a10['beads_x']]
            bulge, drop = float(a10['bead_h']), float(a10['bead_drop'])
            pearl = dict(ra=float(a10['bead_ra']), rb=float(a10['bead_rb']), dc=float(a10['bead_dc']),
                         p=float(a10['bead_p']), hang=float(a10['bead_hang']), up=float(a10['bead_up']),
                         out=float(a10['bead_out']))
        elif 'beads_x' in a8:
            # AX8: TWO BEADS A SIDE in the lobe's place (p15 / p14: round glassy beads side by side under the margin),
            # each its own bump along the line's arc length; lobe_weight sums them
            beads = [(float(np.interp(bx * HW, poly[:, 0], lam)), float(a8['bead_w'])) for bx in a8['beads_x']]
            bulge, drop = float(a8['bead_bulge']), float(a8['bead_drop'])
        else:
            beads = [(lam_L, float(a7c['lobe_w']))]
            bulge, drop = float(a7c['lobe_bulge']), float(a7c['lobe_drop'])
        if pearls_are_parts(spec):
            # AX13: THE BEADS OFF THE SKIN (pearls_are_parts): the record keeps their places along the line (the
            # droplets' chart, species/axolotl_pearls.py) at no bulge, no margin dip and no pearl domes
            pearl, bulge, drop = None, 0.0, 0.0
        fr_rec['lobe'] = dict(lam_L=lam_L, w=float(a7c['lobe_w']), bulge=bulge, drop=drop, beads=beads,
                              s_beads=[float(np.interp(lc, lam[n_cap:], ss_)) for lc, _ in beads], s0=float(L['s0']),
                              s_tab=ss_, lam_s=lam[n_cap:], x_tab=poly[:n_cap + 1, 0], lam_x=lam[:n_cap + 1],
                              s_L=float(np.interp(lam_L, lam[n_cap:], ss_)))
        if pearl is not None:
            fr_rec['lobe']['pearl'] = pearl
        if 'fold_s' in a10:
            # AX10: the corner's fold (fold_weight): its sag in the line (smile_y), its roll and tuck (below); set after
            # the line's arc tables (the beads' chart, at the front: the sag, behind the U, sinks the line where the
            # section curves in, so its offset stops growing toward the corner)
            # (it starts where the line reaches the U's end, or later: AX2 gate 5b reads the U's shape to x_U, and a
            # sag begun before it moved the U's shares, 0.31 / 0.67 against p15's 0.25 / 0.58)
            s_U = float(np.interp(x_U, ring_pts[:, 0], ss_))
            # (AX13, with the pearls as parts: the LOWER LIP UNDER THE FOLD MEETS IT (SPEC ax13 fold_tuck / fold_lift):
            # tucked along the skin's normal, which points out and DOWN there, the lower lip row went up and in, above
            # the fold's hem, so the clay's fold overhung a 2.5 mm shelf and the low's slit, cut between the hem and
            # that row, opened UPWARD: the dark wedge at each corner from the front (ax13_notes/try/lip_sections.png).
            # And its sag RISES over three of the low's rings (SPEC ax13 fold_s): over AX10's two (the eye block's 1.68
            # mm cells) the lip loop sampled it as a V, the hem's point at the corner and a zigzag in both runs)
            a13_ = (spec.get('ax13') or {}) if pearls_are_parts(spec) else {}
            fs = [float(v) for v in a13_.get('fold_s', a10['fold_s'])]
            fs[0] = max(fs[0], s_U)
            fr_rec['fold'] = dict(s=tuple(fs), s_c=float(s_c),
                                  drop=float(a10['fold_drop']), corner=float(a10['fold_corner']),
                                  out=float(a10['fold_out']), tuck=float(a13_.get('fold_tuck', a10['fold_tuck'])),
                                  lift=float(a13_.get('fold_lift', 0.0)), end=float(a10['fold_end']))
        y_line = lambda s: float(mouth_point(body, fr_rec, s)[2])      # noqa: E731  (the rings' heights, lobes in)
    # ---- the gill bases (AX1's joints, the bind) and their columns' fractions on the gill ring
    chain = SPR.rest_chain(spec)
    k_m = chain['k']
    gpos = {r: np.asarray(chain['mm'][f'gill_{r}_0_L'], np.float64) for r in (1, 2, 3)}
    ig = idx['gill']
    s_g = stations[ig]
    f_gill = {}
    yc_g = 0.5 * sum(body.top_bot(s_g))
    for r in (1, 2, 3):
        b = gpos[r]
        # project radially from the section's centre (0, yc) through the base onto the curve
        P_, L_ = body.half_section(s_g)
        ang_b = np.arctan2(b[0], b[1] - yc_g)
        angs = np.arctan2(P_[:, 0], P_[:, 1] - yc_g)
        i = int(np.argmin(np.abs(angs - ang_b)))
        f_gill[r] = float(L_[i] / L_[-1])
    # ---- the rings
    fr_mouth_lock = []
    for i, s in enumerate(stations):
        # anchors: the mouth line on the head, the widest point behind the commissure
        f_w = body.frac_of_point(s, body.hw(s), body.yw(s))
        if a7c and s <= s_c:
            f_m = mouth_point(body, fr_rec, s)[0]                               # AX7c: the smile across the front
        elif s <= s_c:
            f_m = body.frac_at_height(s, y_line(s), lower=True)
        else:
            if a7c:
                f_mouth_c = frac_at_y(body, s, fr_rec['smile_x'][0])            # AX7c: the corner's height
            else:
                f_mouth_c = body.frac_at_height(s, y_line(s_c), lower=True)    # AX7b: the raised corner's height
            f_m = f_mouth_c + (f_w - f_mouth_c) * smooth01((s - s_c) / 0.03)
        anchors = [(0, 0.0), (jm, f_m), (J, 1.0)]
        fr0 = np.interp(np.arange(J + 1), [a[0] for a in anchors], [a[1] for a in anchors])
        lr = L.get('lip_rows')
        if lr and spec.get('ax10', {}).get('beads_x') and s <= s_c and not pearls_are_parts(spec):
            # AX10: the lower lip's first rows dense under the beads (LAYOUT lip_rows' note; AX13: none with the beads
            # off the skin, the even columns as AX8's)
            sa, sb = lr['s']
            w_b = 1.0 - smooth01(max(sa - s, s - sb, 0.0) / lr['ease'])
            if w_b > 0.0:
                f_b = f_m + lr['n'] * lr['step'] / float(body.half_section(s)[1][-1])
                ab = [(0, 0.0), (jm, f_m), (jm + lr['n'], f_b), (J, 1.0)]
                fr0 = (1.0 - w_b) * fr0 + w_b * np.interp(np.arange(J + 1), [a[0] for a in ab], [a[1] for a in ab])
        gb = L['gill_blend']
        wg = max(0.0, 1.0 - abs(i - ig) / (gb + 1.0))
        if wg > 0:
            ag = [(0, 0.0)] + [(L['gill_j'][r - 1], f_gill[r]) for r in (1, 2, 3)] + [(jm, f_m), (J, 1.0)]
            frg = np.interp(np.arange(J + 1), [a[0] for a in ag], [a[1] for a in ag])
            fr = (1 - wg) * fr0 + wg * frg
        else:
            fr = fr0
        xy = body.at_frac(s, fr)
        z = float(body.z(s))
        for j in range(J + 1):
            P[topo.R[i, j]] = (xy[j, 0], xy[j, 1], z)
        P[topo.R[i, 0], 0] = 0.0
        P[topo.R[i, J], 0] = 0.0
    # ---- the snout cap: a Coons patch of ring 0's boundary in (x, y), domed forward to the snout tip
    r0 = P[topo.R[0]]
    top = r0[:hx + 1, :2]
    bot = r0[::-1][:hx + 1, :2]                      # columns J .. J - hx  ->  C[a, ny] = R[0, J - a]
    right = r0[hx:hx + ny + 1, :2]
    t_y, b_y = r0[0, 1], r0[J, 1]
    # the midline column (a = 0): the top, the snout tip at its height, the mouth row at the mouth's height, the bottom
    y_tip = body.y_tip
    y_front = smile_y(fr_rec, 0.0) if a7c else y_line(0.0)            # AX7c: the U's midline (no lobe at the front)
    yb = np.interp(np.arange(ny + 1), [0, 0.5 * bm, bm, ny], [t_y, y_tip + 0.35 * (t_y - y_tip), y_front, b_y])
    left = np.column_stack([np.zeros(ny + 1), yb])
    Cxy = coons(top, bot, left, right)
    # each interior vertex on the snout's NATURAL front surface (the sections below s0 shrink to the tip): the cap is
    # the same surface as the rings, no dome of its own
    for a in range(hx + 1):
        for b in range(ny + 1):
            v = topo.C[a, b]
            if a == hx or b == 0 or b == ny:
                continue
            x_, y_ = Cxy[a, b, 0], Cxy[a, b, 1]
            P[v] = (x_, y_, float(body.z(body.front_station(x_, y_, L['s0']))))
    # ---- the tail cap
    rl = P[topo.R[-1]]
    top_t = rl[:tx + 1, :2]
    bot_t = rl[::-1][:tx + 1, :2]
    right_t = rl[tx:tx + ty + 1, :2]
    yc_t = 0.5 * (rl[0, 1] + rl[J, 1])
    left_t = np.column_stack([np.zeros(ty + 1), np.linspace(rl[0, 1], rl[J, 1], ty + 1)])
    Txy = coons(top_t, bot_t, left_t, right_t)
    for a in range(tx + 1):
        for b in range(ty + 1):
            v = topo.T[a, b]
            if a == tx or b == 0 or b == ty:
                continue
            x_, y_ = Txy[a, b, 0], Txy[a, b, 1]
            P[v] = (x_, y_, float(body.z(body.back_station(x_, y_, L['s_end']))))
    for v in topo.C[0, :]:
        P[v, 0] = 0.0
    for v in topo.T[0, :]:
        P[v, 0] = 0.0

    # ---- outward normals of the natural targets (for the offsets): the half mesh's vertex normals
    def normals_of(Pt):
        Qh = topo.Qh
        n = np.zeros_like(Pt)
        valid = ~np.isnan(Pt[:, 0])
        Pz = np.where(valid[:, None], Pt, 0.0)
        fn = np.cross(Pz[Qh[:, 2]] - Pz[Qh[:, 0]], Pz[Qh[:, 3]] - Pz[Qh[:, 1]])
        for k in range(4):
            np.add.at(n, Qh[:, k], fn)
        ln = np.linalg.norm(n, axis=1)
        return n / np.maximum(ln, 1e-12)[:, None]

    # ---- the eye: its tube's rings placed in the eye's chart (every ring shares the rim's spokes)
    fe = FEATURES['eye']
    r_e = 0.5 * hd['eye_d_TL'] * TL
    a_ax, u_ax, v_ax = eye_frame(spec)
    Ej = np.asarray(chain['mm']['eye_L'], np.float64)               # AX1's eye joint: the visible disc's centre
    Es, t_s = body.surface_along(Ej, a_ax)
    if Es is None:
        Es, t_s = Ej, 0.0
    # the edge's centre: from AX1's joint (p13's place) `out` of the way to the natural surface along the axis, so the
    # ball sits proud and the skin meets it without a socket (the front view moves by out x t_s x 0.8 mm)
    E = Ej + fe['out'] * t_s * a_ax
    i0, i1, j0, j1 = topo.eye_block
    rim = topo.eye_rim
    # each rim vertex: its spoke angle in the chart; pulled toward the rim radius on the natural surface
    ang = []
    for v in rim:
        d = P[v] - E
        ang.append(np.arctan2(d @ v_ax, d @ u_ax))
    ang = np.array(ang)
    for k, v in enumerate(rim):
        d = P[v] - E
        rr = np.hypot(d @ u_ax, d @ v_ax)
        rt = fe['rim'] * r_e
        r_new = rr + fe['rim_pull'] * (rt - rr)
        q = E + r_new * (np.cos(ang[k]) * u_ax + np.sin(ang[k]) * v_ax)
        sp_, _ = body.surface_along(q, a_ax)
        if sp_ is not None:
            P[v] = sp_
        w[v] = FIT['w_feat'] * 0.5
    crest, edge, tuck = topo.eye_rings
    # the inner rings at EVEN spoke angles, phased to the rim's (AX7's eye round, 10-29: on the rim's own angles, which
    # the square block's loop spaces 18.4-26.6 deg, the clay's skin met the ball in a D with corners, the ball bare
    # 0.12 mm past the edge ring at one of them; AX4's port ring is even, 22.5 deg)
    n_r = len(rim)
    stp = 2.0 * np.pi / n_r * (1.0 if np.unwrap(ang)[-1] > np.unwrap(ang)[0] else -1.0)
    ang_in = np.angle(np.mean(np.exp(1j * (ang - stp * np.arange(n_r))))) + stp * np.arange(n_r)
    for k in range(len(rim)):
        c, sn_ = np.cos(ang_in[k]), np.sin(ang_in[k])
        q = E + fe['crest'] * r_e * (c * u_ax + sn_ * v_ax)
        sp_, _ = body.surface_along(q, a_ax)
        base = sp_ if sp_ is not None else q
        # the collar: halfway from the edge plane to the natural surface (when that lies above it), raised crest_h: the
        # skin slopes down to the ball without a ring of its own
        h_n = (base - E) @ a_ax
        P[crest[k]] = q + (0.5 * max(h_n, 0.0) + fe['crest_h']) * a_ax
        P[edge[k]] = E + fe['edge'] * r_e * (c * u_ax + sn_ * v_ax)
        P[tuck[k]] = E + fe['tuck'] * r_e * (c * u_ax + sn_ * v_ax) + fe['tuck_h'] * a_ax
        w[crest[k]] = FIT['w_feat']
        w[edge[k]] = FIT['w_feat']
        w[tuck[k]] = FIT['w_feat'] * 0.5
    # the enclosed 3 x 3: shrunk toward the axis, inside the ball
    ci, cj = (i0 + i1) / 2.0, (j0 + j1) / 2.0
    for i in range(i0 + 1, i1):
        for j in range(j0 + 1, j1):
            v = topo.R[i, j]
            du, dv = (j - cj) / (j1 - cj), (i - ci) / (i1 - ci)
            P[v] = E + fe['core'] * r_e * (du * u_ax + dv * v_ax) + fe['core_h'] * a_ax
            w[v] = FIT['w_inner']
    r_ball = fe['ball'] * r_e
    d_ball = np.sqrt(max(r_ball ** 2 - (fe['edge'] * r_e) ** 2, 0.0))
    eye = dict(E=E, axis=a_ax, u=u_ax, v=v_ax, r_e=r_e, r_ball=r_ball, centre=E - d_ball * a_ax,
               surface_offset=float(t_s), surface_point=Es)

    # ---- the mouth line: column jm on the head's rings and the cap's row b_mouth, creased; the lower lip tucked
    fm = FEATURES['mouth']
    Nn = normals_of(P)
    ic = idx['commissure']
    mouth_ids, lower_ids = [], []
    for b_ in range(hx + 1):
        mouth_ids.append(int(topo.C[b_, bm]) if b_ < hx else int(topo.R[0, jm]))
    for i in range(0, ic + 1):
        mouth_ids.append(int(topo.R[i, jm])) if i > 0 else None
        lower_ids.append(int(topo.R[i, jm + 1]))
    for a in range(hx):
        lower_ids.append(int(topo.C[a, bm + 1]))
    # the line's height: every mouth vertex moved onto the mouth level along its section (the cap's row by y); AX7b:
    # the level is the smile's at the vertex's station (mouth_height)
    cap_row = set(int(topo.C[b_, bm]) for b_ in range(hx))
    for v in mouth_ids:
        if a7c:
            # AX7c: the cap's row at the U's height for its own offset, then back on the snout's natural front surface
            # (its z was placed at the Coons patch's height); the rings' vertices are re-placed just below
            if v in cap_row:
                P[v, 1] = smile_y(fr_rec, P[v, 0])
                P[v, 2] = float(body.z(body.front_station(P[v, 0], P[v, 1], L['s0'])))
        else:
            P[v, 1] = y_line(float(body.s_of(P[v, 2]))) if not np.isnan(P[v, 1]) else P[v, 1]
    # re-place the head rings' mouth column at the mouth level on their natural section (keeps it on the surface)
    for i in range(0, ic + 1):
        s = stations[i]
        f = mouth_point(body, fr_rec, s)[0] if a7c else body.frac_at_height(s, y_line(s), lower=True)
        xy = body.at_frac(s, [f])[0]
        P[topo.R[i, jm], :2] = xy
    Nn = normals_of(P)
    for v in mouth_ids:
        P[v] = P[v] + fm['proud'] * Nn[v]
        w[v] = FIT['w_feat']
    fd = fr_rec.get('fold')
    if fd is not None:
        # AX10: THE FOLD'S ROLL (fold_weight): the margin and the two rows above it stand out, a thick rounded upper lip
        # over the corner (the line's sag is smile_y's), fading past the commissure into the cheek
        for i, s in enumerate(stations):
            wf = fold_weight(fr_rec, s)
            if wf <= 0.0:
                if s > s_c:
                    break
                continue
            for d, share in ((0, 1.0), (1, 0.75), (2, 0.35)):
                v = int(topo.R[i, jm - d])
                P[v] = P[v] + fd['out'] * share * wf * Nn[v]
                w[v] = max(w[v], FIT['w_feat'] * (1.0 if d == 0 else 0.5))
    # AX7c: THE LOBES (p14 / p15's round lobes, p13's fleshy corners, under the ends of the U): the rows of FEATURES mouth
    # lobe_rows stand out along the skin's normal, `bulge` x each row's share x the bump over the line's arc length, so
    # the fleshy swell hangs under the margin and the margin stays one smooth U; the low (AX4) casts its lips onto this
    # clay, so it carries the lobes (AX6's displacement-only lobes baked into the normals read as dots in the engine)
    lob = fr_rec.get('lobe')
    post = np.zeros_like(P)              # AX8: the beads as a displacement of the FITTED controls (FEATURES mouth's note)
    if lob is not None and lob.get('pearl') is not None:
        # AX10: THE PEARLS (the a10 note above) on the fitted controls (bead_post: AX8's lesson, displaced targets rippled
        # the face): each column under the line (a ring's jm, jm + 1, ...; the cap's bm, bm + 1, ... down to ring 0), its
        # vertices placed in the bead's chart by the line's arc at the column (along) and the column's own arc under
        # the line (across)
        pr = lob['pearl']
        h_b = lob['bulge']
        cols = [([int(topo.R[i, jm + d]) for d in range(0, min(10, J - jm) + 1)],
                 float(np.interp(stations[i], lob['s_tab'], lob['lam_s']))) for i in range(ic + 1)]
        cols += [([int(topo.C[a, bm + d]) for d in range(0, ny - bm + 1)],
                  float(np.interp(abs(P[topo.C[a, bm], 0]), lob['x_tab'], lob['lam_x']))) for a in range(hx)]
        lobe_v = []
        # the line's tangent at each column (toward the corner), by differences over the columns sorted along the line
        order = np.argsort([lv for _, lv in cols])
        Pl = np.array([P[cols[o][0][0]] for o in order])
        Tl = np.gradient(Pl, axis=0)
        Tl /= np.maximum(np.linalg.norm(Tl, axis=1, keepdims=True), 1e-12)
        T_of = {int(o): Tl[k] for k, o in enumerate(order)}
        for ci, (col, lam_v) in enumerate(cols):
            Pc = P[col]
            arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pc, axis=0), axis=1))])
            hit = False
            for k in range(1, len(col)):
                best = None
                for lc, _ in lob['beads']:
                    ac = arc[k] - pr['dc']
                    rb = pr['rb'] * (pr['up'] if ac < 0.0 else 1.0)          # the pearl's top under the margin: tighter
                    ua, ub = (lam_v - lc) / pr['ra'], ac / rb
                    r2 = ua * ua + ub * ub
                    if r2 < 1.0 and (best is None or (1.0 - r2) ** pr['p'] > best[0]):
                        best = ((1.0 - r2) ** pr['p'], ua, ub, r2)
                if best is None:
                    continue
                prof, ua, ub, r2 = best
                hit = True
                down = Pc[min(k + 1, len(col) - 1)] - Pc[k - 1]
                down = down / max(np.linalg.norm(down), 1e-12)
                dvec = Nn[col[k]] + pr['hang'] * down
                d_ = h_b * prof * dvec / np.linalg.norm(dvec)
                if pr['out'] > 0.0:
                    # the equator wider than the foot: pushed out from the pearl's centre within the skin, most at r ~0.7
                    # (r sqrt(1 - r^2)), none at the centre or the rim
                    rad = ua * T_of[ci] + ub * down
                    rad -= Nn[col[k]] * (rad @ Nn[col[k]])
                    nr = np.linalg.norm(rad)
                    if nr > 1e-9:
                        d_ += h_b * pr['out'] * math.sqrt(r2) * math.sqrt(1.0 - r2) * rad / nr
                post[col[k]] = post[col[k]] + d_
            if hit:
                lobe_v.append(int(col[0]))
        tags['lobe_verts'] = lobe_v
    elif lob is not None:
        bulge = lob['bulge']
        lobe_v = []
        as_post = bool(fm.get('bead_post')) and len(lob.get('beads') or []) > 1
        # (on the controls the row above the margin stays: its tenth of the swell would sit on the face over the crease)
        rows = [r for r in fm['lobe_rows'] if not (as_post and r[0] < 0)]
        # the rings' columns jm + d (by station), the cap's rows bm + d (by offset)
        pairs_ = [([(topo.R[i, jm + d], k) for d, k in rows], topo.R[i, jm], lobe_weight(fr_rec, stations[i], None))
                  for i in range(ic + 1)]
        pairs_ += [([(topo.C[a, bm + d], k) for d, k in rows], topo.C[a, bm], lobe_weight(fr_rec, None, P[topo.C[a, bm], 0]))
                   for a in range(hx)]
        for vs, v_m, wl in pairs_:
            if wl <= 0.0:
                continue
            for v, k in vs:
                if as_post:
                    post[v] = post[v] + k * bulge * wl * Nn[v]
                    continue
                P[v] = P[v] + k * bulge * wl * Nn[v]
                w[v] = max(w[v], FIT['w_feat'] * fm.get('lobe_fit_w', 0.6))
            lobe_v.append(int(v_m))
        tags['lobe_verts'] = lobe_v
    e0, e1 = fm['ease']
    for v in lower_ids:
        s = float(body.s_of(P[v, 2]))
        u_ = np.clip(s / s_c, 0.0, 1.0)
        if 'tuck_s' in fm:
            tk = tab(fm['tuck_s'], s)                               # AX8: by station (FEATURES mouth's note)
        else:
            tk = fm['tuck_front'] + (fm['tuck_corner'] - fm['tuck_front']) * u_ ** 2
        if lob is not None:
            tk += fm['lobe_tuck'] * lob['bulge'] * lobe_weight(fr_rec, s if s >= lob['s0'] else None, P[v, 0])
            if pearls_are_parts(spec):
                # AX13: under the droplets the lower lip comes forward to meet the margin (SPEC ax13 drop_lift: the
                # tuck's share taken back by the beads' weight along the line), so no slit opens up behind them
                tk *= 1.0 - float(spec['ax13'].get('drop_lift', 0.0)) * lobe_weight(
                    fr_rec, s if s >= lob['s0'] else None, P[v, 0])
        if fd is not None:
            tk *= 1.0 - fd.get('lift', 0.0) * fold_weight(fr_rec, s)   # AX13: the lower lip meets the fold (its note)
            tk += fd['tuck'] * fold_weight(fr_rec, s)            # AX10: the lower lip under the corner's fold
        tk *= 1.0 - smooth01((s - (s_c - e0)) / (e0 + e1))      # the fold eases out across the corner, never cut
        P[v] = P[v] - tk * Nn[v]
        w[v] = FIT['w_feat'] * 0.6
    # the creases along the line (fading at the commissure)
    pairs, vals = [], []
    line = [int(topo.C[a, bm]) for a in range(hx)] + [int(topo.R[i, jm]) for i in range(0, ic + 1)]
    for k in range(len(line) - 1):
        pairs.append((line[k], line[k + 1]))
        vals.append(SHARP['mouth_front'] if k < hx else SHARP['mouth'])
        if lob is not None and lob['bulge'] > 0.0:
            # AX7c: the crease softens a little through each lobe (lobe_soft of it at the lobe's middle), where the lip's
            # row beneath it stands out (AX13: not with the beads off the skin, bulge 0: the margin one even crease)
            if k < hx:
                wl = lobe_weight(fr_rec, None, 0.5 * (P[line[k], 0] + P[line[k + 1], 0]))
            else:
                wl = lobe_weight(fr_rec, 0.5 * (stations[k - hx] + stations[k - hx + 1]), None)
            vals[-1] *= 1.0 - fm['lobe_soft'] * wl
    if len(vals) >= 2:
        vals[-1], vals[-2] = SHARP['mouth_end'][1], SHARP['mouth_end'][0]
    topo.crease(pairs, vals)
    tags['mouth_line'] = line
    tags['lower_lip'] = lower_ids
    corner = P[topo.R[ic, jm]].copy()

    # ---- the nares: the nearest vertex to each naris pinned on the natural surface and dimpled
    yn = y_top_max - hd['naris_frontal'][0] * H
    xn = hd['naris_frontal'][1] * HW
    zn = float(body.z(st['naris']))
    pn = np.array([xn, yn, zn])
    cand = [int(v) for v in np.concatenate([topo.R[:4].ravel(), topo.C.ravel()]) if not np.isnan(P[v, 0])
            and v not in mouth_ids and v not in lower_ids]
    vn = min(cand, key=lambda v: np.linalg.norm(P[v] - pn))
    sp_, _ = body.surface_along(pn, [0.0, 0.0, 1.0])
    if sp_ is None:
        sp_ = pn
    Nn = normals_of(P)
    P[vn] = sp_ - FEATURES['nares']['dimple'] * Nn[vn]
    w[vn] = FIT['w_feat']
    tags['naris'] = int(vn)

    # ---- the gular loop: the gill ring's ventral edges, creased, its vertices tucked a little
    gc = L['gular_cols']
    gpairs = [(int(topo.R[ig, j]), int(topo.R[ig, j + 1])) for j in range(J - gc, J)]
    topo.crease(gpairs, SHARP['gular'])
    Nn = normals_of(P)
    for j in range(J - gc + 1, J + 1):
        v = topo.R[ig, j]
        P[v] = P[v] - FEATURES['gular']['tuck'] * Nn[v]
        w[v] = FIT['w_feat'] * 0.4
    tags['gular'] = [int(topo.R[ig, j]) for j in range(J - gc, J + 1)]
    tags['gill_cols'] = {r: int(topo.R[ig, L['gill_j'][r - 1]]) for r in (1, 2, 3)}

    assert not np.isnan(P).any(), f'{int(np.isnan(P[:, 0]).sum())} vertices unplaced'
    log(f'[caudate] {len(stations)} rings, {topo.n_half} half vertices, {len(topo.Qh)} half quads; the frontal box: top '
        f'{y_top_max:.2f}, bottom {y_bot_min:.2f} ({H:.2f} mm = {H / HW:.3f} HW), the mouth line at {y_mouth:.2f} mm; '
        f'the eye joint {Ej.round(2).tolist()} is {t_s:+.2f} mm along its axis from the natural surface; placed in '
        f'{time.time() - t0:.1f}s')
    frontal = dict(top=y_top_max, bot=y_bot_min, H=H, mouth=y_mouth, naris=pn, corner=corner, smile=smile)
    frontal.update({k: fr_rec[k] for k in ('smile_x', 'lobe', 'fold') if k in fr_rec})   # AX7c: the low reads these too
    if a7c:
        log(f'[caudate] AX7c smile: the corner {fr_rec["smile_x"][0]:.2f} mm at x {fr_rec["smile_x"][3]:.2f}, the front '
            f'{smile_y(fr_rec, 0.0):.2f} (U {fr_rec["smile_x"][1]:.2f} mm to x {fr_rec["smile_x"][4]:.2f}, c '
            f'{fr_rec["smile_x"][2]}); ring 0 (s '
            f'{L["s0"]}) bottom {b_y:.2f}; the lobes ' +
            ', '.join(f'{lc:.2f} mm along the line (s ~{s_:.4f}, +- {w_:.2f} mm)' for (lc, w_), s_ in
                      zip(fr_rec['lobe']['beads'], fr_rec['lobe']['s_beads'])) +
            f' from the midline ({len(tags.get("lobe_verts", []))} margin vertices), bulge {fr_rec["lobe"]["bulge"]:.2f}, '
            f'drop {fr_rec["lobe"]["drop"]:.2f} mm')
    return dict(topo=topo, P=P, w=w, stations=stations, idx=idx, body=body, eye=eye, tags=tags,
                frontal=frontal, gill_bases=gpos, k_m=k_m, P_post=post)


# ============================================================================================ the fit and the limit
def fit_cage(cg, log=print):
    """the controls: least squares of the limit at the cage's vertices against the targets, weighted, plus the
    fairness lam |L (V - T)|^2 (module docstring). Returns (cage QuadMesh, sharp, residual stats)"""
    t0 = time.time()
    topo = cg['topo']
    tgt, mir, sharp = topo.full(cg['P'])
    n = len(tgt.V)
    wf = np.zeros(n)
    wf[:topo.n_half] = cg['w']
    wf[mir[:topo.n_half]] = cg['w']
    A, _ = SS.limit_operator(tgt, sharp, LEVELS['fit'])
    Adj = topo.adjacency(n, tgt.Q)
    deg = np.asarray(Adj.sum(1)).ravel()
    Lp = sp.identity(n) - sp.diags(1.0 / np.maximum(deg, 1)) @ Adj
    W = sp.diags(wf)
    M = (A.T @ W @ A + FIT['lam'] * (Lp.T @ Lp)).tocsc()
    T = tgt.V
    rhs = A.T @ (W @ T) + FIT['lam'] * (Lp.T @ (Lp @ T))
    lu = spla.splu(M)
    V0 = np.column_stack([lu.solve(rhs[:, k]) for k in range(3)])
    res = np.linalg.norm(A @ V0 - T, axis=1)
    post = cg.get('P_post')
    if post is not None and np.any(post):
        # AX8: THE BEADS ON THE FITTED CONTROLS (FEATURES mouth bead_post): the half's displacement and its mirror
        side = ~np.isin(np.arange(topo.n_half), topo.midline())
        V0[:topo.n_half] += post
        V0[mir[:topo.n_half][side]] += post[side] * np.array([-1.0, 1.0, 1.0])
        log(f'[caudate] the beads on the fitted controls: {int(np.any(post != 0, axis=1).sum())} half controls moved, up to '
            f'{np.linalg.norm(post, axis=1).max():.2f} mm')
    feat = wf >= FIT['w_feat'] * 0.5
    stats = dict(p50=float(np.median(res)), p95=float(np.percentile(res, 95)), max=float(res.max()),
                 feat_max=float(res[feat].max()) if feat.any() else 0.0)
    log(f'[caudate] fitted {n} controls ({len(tgt.Q)} quads, {len(sharp)} crease edges) in {time.time() - t0:.1f}s: '
        f'the limit off its targets p50 {stats["p50"]:.3f}, p95 {stats["p95"]:.3f}, max {stats["max"]:.3f} mm (features '
        f'max {stats["feat_max"]:.3f})')
    return QuadMesh(V0, tgt.Q), sharp, stats, tgt, mir


def limit(cage, sharp, levels=None):
    lim, s_e, par, _ = SS.subdivide(cage, sharp, LEVELS['out'] if levels is None else levels)
    return lim, par


def bead_profile(V1, V0, line_ids, HW, floor=0.02, peak_share=0.5, prominence=0.15, merge_mm=1.0):
    """AX8: THE LIP'S BEADS MEASURED on the limit (life mm): V1 the limit with its beads, V0 the same topology without
    (the SPEC's bulge and drop 0), line_ids the mouth line's cage vertices (their limit points lead the limit's
    vertices). Each left vertex's stand-off d = |V1 - V0| over `floor` is put on the line by its nearest point (the
    line's arc length from the midline); the profile is the largest d per 0.1 mm of arc (3-bin smoothed: the pass
    between two beads, whatever row it crosses at); a BEAD is a peak of at least peak_share of the largest (a bead's low
    skirt, put on the line nearer the midline than its body, reads as a small peak of its own: 0.40 of the largest on
    the control-displaced beads) that stands
    `prominence` of the largest over the higher of the lowest points between it and its neighbouring peaks (a shoulder
    on a bead's flank is not one), peaks within merge_mm one bead. Per bead: its peak (mm), its arc, its centre off the
    midline (the stand-off-weighted x of the vertices over half its peak within its span, HW), its width across x and
    its height across y there (HW), and the valley to the next (the lowest point between, as a share of the lower
    peak: the gate's measure of two DISTINCT beads). Returns a dict"""
    V1, V0 = np.asarray(V1, np.float64), np.asarray(V0, np.float64)
    d = np.linalg.norm(V1 - V0, axis=1)
    sel = (d > floor) & (V1[:, 0] > 0.0)
    line = V0[np.asarray(line_ids, int)]
    line = line[np.argsort(line[:, 0])]                 # (the line's offset grows toward the corner: build_cage)
    ts = np.linspace(0.0, 1.0, 20, endpoint=False)[:, None]
    dense = np.vstack([line[k] + (line[k + 1] - line[k]) * ts for k in range(len(line) - 1)] + [line[-1:]])
    arc_d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))])
    if not sel.any():
        return dict(beads=[], n=0, max_mm=0.0, profile=[])
    from scipy.spatial import cKDTree
    _, j = cKDTree(dense).query(V1[sel])
    t = arc_d[j]
    dv, Pv = d[sel], V1[sel]
    nb = int(np.ceil(arc_d[-1] / 0.1)) + 1
    prof = np.zeros(nb)
    np.maximum.at(prof, np.clip((t / 0.1).astype(int), 0, nb - 1), dv)
    prof = np.convolve(np.pad(prof, 1, mode='edge'), np.ones(3) / 3.0, mode='valid')
    top = float(prof.max())
    pk = [i for i in range(1, nb - 1) if prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1] and prof[i] >= peak_share * top]
    merged = []
    for i in pk:
        if merged and (i - merged[-1]) * 0.1 < merge_mm:
            if prof[i] > prof[merged[-1]]:
                merged[-1] = i
        else:
            merged.append(i)
    # prominence: drop the least prominent peak while any stands less than `prominence` x top over its higher saddle
    while len(merged) > 1:
        prom = []
        for k, i in enumerate(merged):
            sad = [prof[merged[k - 1]:i + 1].min()] if k > 0 else []
            sad += [prof[i:merged[k + 1] + 1].min()] if k + 1 < len(merged) else []
            prom.append(prof[i] - max(sad))
        k_min = int(np.argmin(prom))
        if prom[k_min] >= prominence * top:
            break
        merged.pop(k_min)
    beads, edges = [], [0]
    for a, b in zip(merged[:-1], merged[1:]):
        edges.append(a + int(np.argmin(prof[a:b + 1])))
    edges.append(nb - 1)
    for k, i in enumerate(merged):
        lo_, hi_ = edges[k] * 0.1, edges[k + 1] * 0.1
        m = (t >= lo_) & (t <= hi_) & (dv >= 0.5 * prof[i])
        if not m.any():
            continue
        w8 = dv[m]
        val = float(prof[edges[k + 1]] / min(prof[i], prof[merged[k + 1]])) if k + 1 < len(merged) else None
        xc = float((Pv[m, 0] * w8).sum() / w8.sum())
        m2 = (t >= lo_) & (t <= hi_) & (dv >= 0.2)                    # its whole extent (over 0.2 mm), for the rim's drop
        drop_mm = float(np.interp(xc, line[:, 0], line[:, 1]) - Pv[m2, 1].min()) if m2.any() else 0.0
        beads.append(dict(peak_mm=float(prof[i]), arc_mm=float(i * 0.1), centre_HW=xc / HW,
                          width_HW=float((Pv[m, 0].max() - Pv[m, 0].min()) / HW),
                          height_HW=float((Pv[m, 1].max() - Pv[m, 1].min()) / HW),
                          x_HW=(float(Pv[m, 0].min() / HW), float(Pv[m, 0].max() / HW)), valley_next=val,
                          drop_mm=drop_mm))
    return dict(beads=beads, n=len(beads), max_mm=top, profile=prof.round(3).tolist())


# ============================================================================================ the field
_K = {}


def _kernels():
    if _K:
        return _K
    import warp as wp

    @wp.kernel
    def k_sdf_pts(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=wp.float32)):
        tid = wp.tid()
        p = pts[tid]
        q = wp.mesh_query_point_sign_winding_number(mesh, p, maxd, 2.0, 0.5)
        if q.result:
            c = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
            out[tid] = wp.length(p - c) * q.sign
        else:
            out[tid] = maxd
    _K['pts'] = k_sdf_pts
    return _K


def mesh_distance(V, F, pts, maxd=60.0):
    """the signed distance (V's units) of points to the closed triangle mesh (V, F): Warp's BVH, the winding number"""
    import warp as wp
    kk = _kernels()
    dev = wp.get_preferred_device()
    m = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device=dev),
                indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32, device=dev),
                support_winding_number=True)
    out = np.empty(len(pts), np.float32)
    for s0 in range(0, len(pts), 4_000_000):
        P = np.asarray(pts[s0:s0 + 4_000_000], np.float32)
        o = wp.zeros(len(P), dtype=wp.float32, device=dev)
        wp.launch(kk['pts'], dim=len(P), inputs=[m.id, wp.array(P, dtype=wp.vec3, device=dev), float(maxd), o],
                  device=dev)
        out[s0:s0 + len(P)] = o.numpy()
    return out


def body_field(V, F, log=print, h=None):
    """the limit mesh's signed distance on a box grid (BODY_FIELD; mm): exact within `band` of the surface, the coarse
    pass beyond, clamped, the far part blurred. Returns (values, lo, h)"""
    from scipy import ndimage as nd
    bf = BODY_FIELD
    h = bf['h'] if h is None else h
    c = bf['coarse']
    t0 = time.time()
    lo = np.floor((V.min(0) - bf['pad']) / h) * h
    lo[0] = -np.ceil((np.abs(V[:, 0]).max() + bf['pad']) / h) * h          # symmetric about the midline
    hi = V.max(0) + bf['pad']
    hi[0] = -lo[0]
    n = tuple(int(c * np.ceil((hi[a] - lo[a]) / (c * h) - 1e-9)) + 1 for a in range(3))
    nc = tuple((n[a] - 1) // c + 1 for a in range(3))
    G = np.stack(np.meshgrid(*[lo[a] + np.arange(nc[a]) * c * h for a in range(3)], indexing='ij'), -1).reshape(-1, 3)
    dc = np.clip(mesh_distance(V, F, G), *bf['clamp']).reshape(nc).astype(np.float32)
    d = nd.zoom(dc, [n[a] / nc[a] for a in range(3)], order=1, grid_mode=False, mode='nearest').astype(np.float32)
    assert d.shape == n
    reach = bf['band'] + c * h * np.sqrt(3.0)
    near = np.abs(d) < reach
    if bf['s_far'] > 0:
        d = nd.gaussian_filter(d, bf['s_far'] / h, mode='nearest')
    ii = np.argwhere(near)
    pts = lo[None, :] + ii * h
    dn = np.clip(mesh_distance(V, F, pts), *bf['clamp'])
    wgt = smooth01((reach - np.abs(dn)) / (reach - bf['band'])).astype(np.float32)
    d[near] = wgt * dn + (1.0 - wgt) * d[near]
    if bf.get('s_near', 0) > 0:
        d = nd.gaussian_filter(d, bf['s_near'] / h, mode='nearest')
    d = np.clip(d, *bf['clamp']).astype(np.float32)
    log(f'[caudate] the body field on {n} ({int(np.prod(n)):,} points at {h} mm): exact at {len(pts):,} near the '
        f'surface, the {nc} coarse pass beyond; in {time.time() - t0:.1f}s')
    return d, lo, h


# ============================================================================================ the cached build
def _key(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode('utf-8')).hexdigest()[:16]


def cage_key(spec):
    keys = ('a1', 'stations', 'profile', 'widths', 'head', 'rig', 'rest', 'limbs', 'gills')
    sub = {k: spec[k] for k in keys}
    if 'ax7b' in spec:
        # AX7b: the cage reads the smile only (build_cage's a7); the gills' and digits' rows (the rami's oval, its
        # graft share) change no body cage, so they stay out of the key (the whole ax7b dict was in it at first)
        sub['ax7b'] = {k: spec['ax7b'][k] for k in ('smile_up_built', 'smile_down_built', 'smile_power')}
    if 'ax7c' in spec:
        # AX7c: the smile across the front and the lobes (build_cage's a7c); the digit and foot rows stay out
        sub['ax7c'] = {k: spec['ax7c'][k] for k in SMILE_KEYS}
    if 'ax8' in spec:
        # AX8: the beads (build_cage's a8); its digit rows stay out
        sub['ax8'] = {k: spec['ax8'][k] for k in BEAD_KEYS if k in spec['ax8']}
    if 'ax10' in spec:
        # AX10: the pearls and the corner's fold (build_cage's a10); its limb rows stay out (the cage reads rest_chain
        # for the gill bases and the eye only, which the limbs' bind does not move)
        sub['ax10'] = {k: spec['ax10'][k] for k in BEAD10_KEYS if k in spec['ax10']}
    if pearls_are_parts(spec):
        # AX13: the beads off the skin (pearls_are_parts), the lower lip meeting the margin under the droplets and the
        # fold; the droplets' own rows change no body cage
        sub['ax13'] = {k: spec['ax13'][k] for k in ('pearls', 'drop_lift', 'fold_tuck', 'fold_lift', 'fold_s')
                       if k in spec['ax13']}
    return _key(dict(v=VERSION, layout=LAYOUT, section=SECTION, features=FEATURES, sharp=SHARP, levels=LEVELS, fit=FIT,
                     spec=sub))


def build(spec, log=print, use_cache=True):
    """the cage, its fit and its limit mesh (life mm, the bind), cached by every input. Returns a dict"""
    key = cage_key(spec)
    path = os.path.join(CACHE, f'axolotl_cage_{key}.npz')
    cg = build_cage(spec, log)
    if use_cache and os.path.exists(path):
        Z = np.load(path, allow_pickle=False)
        cage = QuadMesh(Z['cage_V'], Z['cage_Q'])
        sharp = {(int(a), int(b)): float(v) for (a, b), v in zip(Z['sharp_pairs'], Z['sharp_vals'])}
        stats = json.loads(str(Z['stats']))
        tgt = QuadMesh(Z['tgt_V'], Z['cage_Q'])
        mir = Z['mir']
        log(f'[caudate] the fitted cage from the cache {os.path.relpath(path, REPO)}')
    else:
        cage, sharp, stats, tgt, mir = fit_cage(cg, log)
        os.makedirs(CACHE, exist_ok=True)
        np.savez_compressed(path, cage_V=cage.V, cage_Q=cage.Q, tgt_V=tgt.V, mir=mir,
                            sharp_pairs=np.array([k for k in sharp], np.int64).reshape(-1, 2),
                            sharp_vals=np.array([v for v in sharp.values()], np.float64), stats=json.dumps(stats))
    cg.update(cage=cage, sharp=sharp, fit=stats, targets=tgt, mir=mir, key=key)
    return cg
