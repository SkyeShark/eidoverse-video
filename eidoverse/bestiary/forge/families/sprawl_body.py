"""THE AXOLOTL'S BODY CAGE (AX4, AXOLOTL_PLAN.md §5.5 / §5.6, the lead's calls of 10-29): the body loft with the head,
the shared gill-base regions and the limbs' port blocks, the horn / wing / back ports, the mouth, the lidless eye ports
and the gular loop; the fin membranes and the eyeballs as separate pieces. Life mm in the plan frame (x left, y up, z
forward: caudate.Body's frame); x4 metres only for the program (km). The limbs and the rami are sprawl_cage's: the body
ends on COPIES of their footprint and graft rings, welded by position when the whole animal is assembled
(work/bestiary/tests/ax04_cage.py).

THE LOFT, built on the half body x >= 0 and mirrored:
- K 64 rings at stations from the snout to past the vent, each cast from its station plane's origin (the midline at
  mid-height) through caudate's analytic half-section at the ring's ARC FRACTIONS; the poll ring is AX3's record (its
  own vertices). The fractions come from one COLUMN TABLE F[ring, h] (h 0 the dorsal midline .. 32 the ventral): every
  port block a rectangle of grid cells pinned at its own size (layout()), the free columns between two pinned ones on
  a ring spread evenly, the rest harmonic (a sparse solve over the grid).
- REDUCTIONS 64 -> 32 -> 16 -> 8, each a two-row band of T / R / S units: T three outer chords onto one inner (its
  5-pole on the middle row, its 3-pole on the outer ring: sprawl_cage's tile), R the same reversed, S one onto one; 3-
  and 5-poles only (loft.reduce_ring's units make 6-poles), the ventral half in R units so that no pole lands on the
  mirror line. The tail root (K 32) and the tail mid (K 16) are AX3's records.
- THE TAIL TIP: K 8 rings to tip_gap mm short of the clay's tip (bisection on the field: its blur ends the tail near s
  0.985, the analytic body at 1.0) and a 1 x 2 cap per half on that tip.
- THE SNOUT CAP: hx x ny cells per half on ring 0: two 3D Coons patches (above the mouth, below it) moved onto the
  nearest clay; the midline column even by arc along the snout's profile; the two lip rows cast along +z.

THE PORTS (seams.json's blocks): the EYE (4 x 4 cells; the octopus eye port without its lid: the loop rounded halfway to
the rim circle, the crest on the clay, the edge on the ball, the tuck under it, those three rings evenly spaced round
the eye (the octopus's t14 lesson), a 4 x 4 socket cap; designed, fixed but the crest); the GILL SOCKETS (three 3 x 3
blocks side by side on the gill rings, each bridged by two fillet rings to a copy of its ramus's graft ring); the LIMB
BLOCKS (3 x 5 round each footprint plus a margin, a halfway ring to a copy of
the footprint; the forelimb's block shares the gill block's last ring, so its loop runs under r3's socket: one shared
gill-base region per side); the GRAFT SITES horn_L / horn_R / horn_mid (4 x 4), wing_L / wing_R (5 x 7) and back_0..2
(6 x 6 across the midline: a block on the mirror line needs an even width, so AX3's 5 x 7 became 6 x 6, the same
24-edge loop), left in place as the records of their loops; the MOUTH (the strip between the upper lip's column and the
lower lip's, from the snout cap's row to the commissure, cut: the lip loop, five bag rings, a 1 x n strip closing the
last; designed, fixed) with the upper lip creased before each corner; the GULAR loop (the gill ring's ventral edges below
r3's socket, creased as caudate's: the fold the clay carries).

THE FIT: sprawl_cage.fit_cage on the clay (the records, the copies and the designed parts fixed), then an EVEN
relaxation (retopo.fit, preserve=False) where the designed spacing does not hold on the clay (the snout cap above the
mouth; the gill region, whose casts met the rami's fleshy roots; rings 0-1, the lip's turn round the snout's corner),
then symmetric again (each right vertex its left's mirror; the records keep their own vertices).

THE FINS (§5.6): each of seams.json's fin segments its own membrane: a left and a right face lofted from a buried root
line to the margin, meeting at a creased rim, open at the root and at both cut lines (neighbours share the cut line's
positions). Heights axolotl_fins.heights (the clay's SHELL patches); the root max(0.25 mm, 0.07 h) plus a lift under
the clay's outline and under the body's LOW (the fitted cage) above it, never past the core's mid-depth, its
half-thickness fins.half_thickness's but at most 0.6 of the core's half-width there (the tail's thin tip) and of the
low's; 6 rows on the tail's tall part (tail root to tail mid), 3 elsewhere (the 3-row cut columns are subsets of the
6-row ones, and the half-thickness follows the 3-row profile, so a 6-row column's own vertices lie on the 3-row edges);
a column about every 2 mm (8 mm x4), closer where the fin is low (at most FIN['aspect'] rows' heights). THE EYES:
cube-sphere balls at caudate's ball centres and radius, scaled so their limit surfaces lie on the ball the eye port's
edge ring sits on.
"""
import math

import numpy as np

from .. import loft as LF
from ..mesh import QuadMesh

TAU = 2.0 * math.pi
MIRROR = np.array([-1.0, 1.0, 1.0])
BREGIONS = ('head', 'neck', 'trunk', 'tail', 'cap', 'mouth', 'eye', 'socket', 'port', 'tailcap')
DESIGNED = ('mouth', 'eye')          # regions the clay does not judge (designed geometry, fixed)

LAY = dict(
    hx=12, ny=8,               # the snout cap per half (2 hx + ny = 32): its mouth row h_mouth - hx (an 8 x 16 cap's
    #                            five rows under the mouth, which sits ~1.3 mm above the snout's bottom at the front,
    #                            were 0.12 mm apart: aspect 8.8)
    h_mouth=18,                # the upper lip's column (the lower lip the next, lip_gap mm below on the mouth's rings)
    lip_gap=0.9,               # (0.45 put the lower lip in the clay's tuck under the upper: rows 0.16-0.19 mm apart)
    lip_meet=5,                # AX8: the snout cap's last columns over which its lower lip's drop eases to ring 0's (assemble)
    lip_gap_corner=0.3,        # AX8: the gap's share left at the commissure, tapering from the U's end (caudate smile_x's
    #                            x_U): at a full 0.9 to the corner ring the slit ended in a 0.9 mm cap, the AX7c check's
    #                            "flat strip ending bluntly" in three-quarter, where p14's line narrows into the fold
    # AX10: THE PEARLS IN THE LOW (the AX8 check: the low makes the silhouette). bead_ring: the snout's rings from ring 0
    # to the eye block's first, about this far apart (mm; the graded 0.8-1.25 left 1.6-1.9 mm of line between lip
    # vertices over the beads, 1.5 per bead); bead_rows: the lower lip's next n rows `step` mm of arc apart on those
    # rings (the pearls hang from the lower lip, SPEC ax10 bead_dc); lip_gap_bead: the lips' gap at the pearls (mm of
    # arc, by the pearls' weight along the line; None keeps lip_gap: AX4's first try closed it to 0.30 over pearls
    # hanging right under the margin, and the lips zigzagged over their tops, the mouth's quads 18 deg / aspect 5.6)
    bead_ring=0.40, lip_gap_bead=None, bead_rows=dict(n=4, step=0.50),
    # AX13 (the pearls as separate glass droplets, species/axolotl_pearls.py; caudate.pearls_are_parts): the lips CLOSED
    # onto each other behind the droplets and on to the corner: the gap eases from lip_gap to lip_gap_drop (mm of arc)
    # between |x| lip_gap_drop_x (HW) on the mouth line, the corner's own taper (lip_gap_corner) below it there; the
    # bead rows are off (layout's `pearls` reads the clay's pearl record: none). Behind a clear droplet the 0.9 mm slit
    # of the U showed as a dark gap through it (the lead's AX13 call: no dark slit behind the droplets). Ring 0 (its
    # mouth point at x ~8.15 mm) closes too: left open, the slit wedged open behind the first droplet (1.06 mm between
    # ring 0's lips) and its seat slid off it. band_from: the clay_band respacing from ring 1 on, ring 0's columns as
    # cast, as the snout cap's Coons patch reads them (cap_cast): ring 0's band, respaced along the snout front's own
    # section, curled medially under the cap's last lower-lip vertex (closed: a quad folded flat, aspect 79; open, as
    # AX10b shipped: 7 crossings at the bind between the cap and that band, 0.06 mm deep, the rig's "jaw x jaw")
    lip_gap_drop=0.30, lip_gap_drop_x=(0.16, 0.205), band_from=1,
    # AX13 restart (11-02 15:2x): lip_meet_drop, the snout cap's lip_meet with the droplets: its lower lip's drop eases to
    # ring 0's over the last 8 columns, not 5. With the lips closed behind the droplets the cap's lower-lip row ran ON ring
    # 0's band below it from x 4.8 to 7.8 mm (the one strip of cap quads under the lower lip 0.07-0.14 mm tall, one pair
    # inverted by 0.006 mm: the bind's 24 "jaw x jaw" crossings of gate 13 on the whole skin, <= 0.012 mm deep, the cap's
    # loop-to-bag strip against ring 0's band; ax13_notes/try/bind_cross2.py, snout_sections.py): eased sooner, the lower
    # lip rides higher on its front face there, in front of ring 0
    lip_meet_drop=8,
    # AX10 (successor, 11-02): clay_band (a, b): on the mouth's rings (0 .. the commissure's) the columns between
    # h_mouth + a and h_mouth + b (both kept) evenly by the CLAY's arc (respace_clay): the table's fractions are the
    # analytic section's, which has no pearls and no fold, so a dome stretched one column to 2.3 mm beside 0.5 mm ones
    # and the fold's overhang collapsed one to 0.16 mm (AX4 gate 10's head quads, ax10_notes/try/cage_lab.py)
    # (with clay_band ring 0's band stays out of fit()'s even relaxation: build's keep)
    clay_band=(1, 6),
    cap_cast=1.0,              # AX10: the snout cap's Coons patch from ring 0 this far back toward ring 0 as cast
    #                            (before clay_band moved it; assemble's note)
    cap_align=3,               # AX10: the cap's lip rows' x on its bottom row's, the last cap_align columns before
    #                            ring 0 linear to its lip (0: off; assemble's note)
    eye_cols=(7, 11), eye_r=3.35,                     # the eye block's columns, its rim radius (caudate's 1.70 r_e)
    horn_cols=(5, 9), horn_half=(3.10, 3.0),          # horn_L
    hmid_cols=(0, 2),                                 # horn_mid (its half)
    gill_cols=dict(r1=8, r2=13, r3=17), gill_w=dict(r1=1.25, r2=0.90, r3=1.00),   # each socket's first column, width
    fore_cols=(21, 24), fore_margin=1.6, hind_cols=(15, 18), hind_margin=1.6,
    wing_cols=(8, 13),         # (from (9, 14) its top line crossed r1's within two rings: a column 0.41 mm wide)
    back_cols=(0, 3), back_cell=1.5, strip=1.1,
    tip_gap=0.8,               # mm from the last K 8 ring to the clay's tail tip
)
RED1 = 'TxxTxxTxxTxxSSSSSSSSRxxRxxRxxRxx'     # 64 -> 32, per half from the dorsal midline (32 outer chords)
RED2 = 'TxxTxxSSSSRxxRxx'                     # 32 -> 16
RED3 = 'TxxSSRxx'                             # 16 -> 8 at the tip
# (T: the tile with its 5-pole at its END on the middle row, R the same reversed, its 5-pole at its START: a T ending on
# the ventral midline put its 5-pole there, a 6-pole once mirrored)
MOUTH = dict(depth=(0.8, 1.6, 2.4, 3.2, 4.0), open=(-0.42, -0.30, 0.0, 0.30, 0.30), sharp=1.5, sharp_share=1 / 3,
             even=10.0, half_min=0.12)
# (AX10, 11-02: the bag is built from the SLIT (mouth()'s note); open's last two 0.35 / 0.45 -> 0.30 / 0.30 and even
# 4 -> 10: the closing strip across the deepest ring 1.5 mm tall over vertices evened to 0.41-0.44 mm at the U (1.8 over
# 0.33-0.37 before: aspect 4.1-4.6, AX4 gate 10's mouth); ax10_notes/try/cage_lab.py's runs cl0-cl34)
# (even: AX7c, 10-30, each ring's evening rounds per mm of depth, three at every depth before: the rounder snout (AX7c's
# snout_apex) tightens the lip's plan curve at x ~6.6 mm, the offsets inward bunched there to 0.19 mm on the deepest ring,
# and the closing strip across it (1.96 mm long) made AX4 gate 10's aspect 10.4; ax7c_notes/bag_test.py replays the rings
# from the saved loop: 4 per mm gives 0.48 mm there, the first ring off the lip as it was, 0.85-1.16 mm)
# (the bag's rings: the inner lip, the gum line, three bag rings, `depth` mm in and `open` mm up / down from the slit's
# mid height plus half the lip gap (mouth()); 0.4-0.9 mm first steps made bag quads of aspect 4-5 against the lip's 0.5
# mm edges.
# AX7b, 10-30: the round-6 bag opened from the lips inward (open 0.05, 0.2, 0.4, 0.55, 0.45), so the lip_gap's 0.9 mm
# between the lips showed the inner lip ring face-on: the "flat maroon ribbon" in the look. Every photo's closed mouth is
# a thin dark line over a pale lower lip (p13, p14, p15): the inner lips MEET behind the lips (the first ring's two walls
# 2 half_min = 0.24 mm apart at 0.8 mm deep), so the gap is a V-groove the bake's occlusion darkens; the bag opens
# behind it)
EYE_CREST = 1.30           # the crest's radius over r_e (caudate's clay has 1.14: 0.28 mm outside the edge ring, a band
#                            of aspect 4.8 in the cage)
GULAR = 0.7                # caudate's SHARP['gular'] (the plan says s ~ 1; the clay was made with 0.7)
GRAFT = ('horn_L', 'horn_mid', 'wing_L', 'back_0', 'back_1', 'back_2')
FIN = dict(step=2.0, aspect=3.0, step_min=0.3, bury_min=0.25, bury_k=0.07, lift=0.10, rows=3, rows_tall=6,
           s_end=0.990, crease=10.0, root_share=0.6, t_floor=0.02)
# (s_end: the two tip segments stop at s 0.990, the fins there 1.1 / 0.5 mm tall over a core that ends at 0.987; past
# it their rows fell under 0.1 mm. crease: the rim's sharpness, past any level used)


def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


# ============================================================================================ the stations
def tail_stations(body, s_from, s_to, TL, step=2.5, k_chord=1.25, K=16):
    """ring stations from s_from to s_to: step mm, but at most k_chord x the K-ring's chord near the thin tip"""
    out, s = [s_from], s_from
    while True:
        Pp, L = body.half_section(min(s, 0.999))
        chord = 2.0 * float(L[-1]) / K
        ds = min(step, k_chord * chord) / TL
        if s + ds >= s_to - 0.3 * ds:
            break
        s += ds
        out.append(s)
    return out


def even(a, b, step):
    """stations strictly between a and b, about step apart (both ends excluded)"""
    n = max(1, int(round((b - a) / step)))
    return list(a + (b - a) * np.arange(1, n) / n)


def stations(spec, body, rec, e_c=0.0394):
    """the K 64 rings (snout -> the first reduction), the reduction bands' middle rows, the K 32, K 16 and K 8 rings,
    and the named stations of the blocks' ring ranges. e_c: the eye's edge centre's station (layout passes caudate's;
    0.0394 was AX4's, the edge centre before AX7's eye round moved it 0.18 mm forward)"""
    from ..heads import caudate as CD
    TL = spec['a1']['TL']
    st = spec['stations']
    mm = 1.0 / TL
    s0 = CD.LAYOUT['s0']        # AX7c: the clay's snout cap (0.012; was 0.008 here and there: the smile's front dips)
    # the eye block: 5 lines 1.68 mm apart round the eye; the horns: lines 1.5 mm apart from horn_L's first
    eye = [e_c + (k - 2) * 1.68 * mm for k in range(5)]
    horn0 = 0.0725 - 2 * 1.5 * mm
    horns = [horn0 + k * 1.5 * mm for k in range(7)]         # horn_L lines 0..4, horn_mid 2..6
    poll = rec['poll']['station']
    gill = [0.1785 + (k - 1.5) * 1.15 * mm for k in range(4)]
    # (the snout's rings graded 0.8 -> 1.25 mm: the lip runs round the snout's corner 2.8 mm between rings 1.4 mm apart
    # in station, against columns ~0.6 mm wide at the front ring: aspect 5-6)
    snout = list(np.cumsum([s0] + [0.8 * mm, 0.95 * mm, 1.1 * mm, 1.25 * mm]))
    snout = [s for s in snout if s < eye[0] - 0.9 * mm]
    snout += even(snout[-1], eye[0], 1.4 * mm)
    if LAY.get('bead_ring'):
        # AX10: the pearls' rings (LAY bead_ring), evenly from ring 0 to the eye block's first
        n_b = max(1, int(round((eye[0] - s0) / (LAY['bead_ring'] * mm))))
        snout = [s0 + (eye[0] - s0) * k / n_b for k in range(n_b)]
    head = snout + eye + even(eye[-1], horns[0], 1.6 * mm) + horns + \
        even(horns[-1], poll, 1.6 * mm) + [poll] + even(poll, gill[0], 1.6 * mm) + gill
    grooves = list(spec['trunk']['groove_stations'])
    # the trunk: the gill block's end, the grooves, the hind block, the vent, the reduction's start
    hind = [0.4355 + k * (0.482 - 0.4355) / 5 for k in range(6)]
    pins = [gill[-1]] + [g for g in grooves] + hind[1:] + [st['vent'], st['vent'] + 0.010]
    pins = sorted(set([round(p, 6) for p in pins] + [round(hind[0], 6)]))
    trunk = []
    for a, b in zip(pins[:-1], pins[1:]):
        trunk += even(a, b, 2.3 * mm) + [b]
    k64 = sorted(set([round(x, 7) for x in head + trunk]))
    s_red1 = st['vent'] + 0.010                                 # the last K 64 ring
    s_mid1, s_k32 = s_red1 + 2.3 * mm, s_red1 + 4.6 * mm
    tr = rec['tail_root']['station']
    k32 = [s_k32] + even(s_k32, tr, 2.4 * mm) + [tr] + even(tr, 0.7322, 2.5 * mm) + [0.7322]
    s_mid2, s_k16 = 0.7322 + 2.5 * mm, 0.7322 + 5.0 * mm
    tm = rec['tail_mid']['station']
    k16 = [s_k16] + even(s_k16, tm, 2.5 * mm) + [tm] + tail_stations(body, tm, 0.925, TL)[1:]
    # the tip: 16 -> 8 (the tail's blade is 4.6 x 1.9 mm at 0.93), K 8 rings and the cap: off a K 16 ring 2.4 mm short of
    # the tip (its blade 1.2 x 0.25 mm) the cap's quads ran 4.9 mm against 0.14 mm chords
    s_mid3 = k16[-1] + 0.6 * (k16[-1] - k16[-2])
    s_k8 = k16[-1] + 1.2 * (k16[-1] - k16[-2])
    k8 = tail_stations(body, s_k8, 0.990, TL, K=8)
    named = dict(eye=eye, horns=horns, gill=gill, hind=hind)
    return dict(k64=k64, mid1=s_mid1, k32=k32, mid2=s_mid2, k16=k16, mid3=s_mid3, k8=k8, named=named, s0=s0)


# ============================================================================================ the casts
def origin(body, s):
    t, b = body.top_bot(s)
    return np.array([0.0, 0.5 * (t + b), float(body.z(s))])


def frac_dirs(body, s, fracs):
    """the directions (in the station plane, from the ring's origin) to the analytic half section's points at the arc
    fractions (0 the dorsal midline .. 1 the ventral)"""
    Pp, L = body.half_section(min(s, 0.9995))
    f = np.asarray(fracs, np.float64) * L[-1]
    x, y = np.interp(f, L, Pp[:, 0]), np.interp(f, L, Pp[:, 1])
    O = origin(body, s)
    D = np.column_stack([x - O[0], y - O[1], np.zeros_like(x)])
    D[np.asarray(fracs) <= 0.0] = (0.0, 1.0, 0.0)
    D[np.asarray(fracs) >= 1.0] = (0.0, -1.0, 0.0)
    return O, unit(D)


def cast_half(field, body, s, fracs):
    O, D = frac_dirs(body, s, fracs)
    P, ok = field.cast(O, D, 80.0)
    P[np.asarray(fracs) <= 0.0, 0] = 0.0
    P[np.asarray(fracs) >= 1.0, 0] = 0.0
    return P, ok


def band_contour(field, s_z, P, h_a, h_b, step=0.04, pad=1.5):
    """AX10: a half ring's vertices strictly between h_a and h_b (P[h_a], P[h_b] kept) moved onto the clay's own
    SECTION CONTOUR in their station plane (z = s_z), evenly by its arc (LAY clay_band's note). The contour is traced
    by marching squares on the field sampled `step` mm apart over the band's box padded by `pad`; the casts through the
    analytic section's fractions jump across the pearls' undercuts (8-12 mm between neighbouring rays at the U's end).
    Returns (P, ok): P unchanged when the two kept vertices are not on one traced piece"""
    from skimage.measure import find_contours
    Pb = np.asarray(P, np.float64)[h_a:h_b + 1]
    lo, hi = Pb[:, :2].min(0) - pad, Pb[:, :2].max(0) + pad
    xs = np.arange(lo[0], hi[0] + step, step)
    ys = np.arange(lo[1], hi[1] + step, step)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    G = field.eval(np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, s_z)])).reshape(X.shape)
    best = None
    for c in find_contours(G, 0.0):
        C = np.column_stack([lo[0] + c[:, 0] * step, lo[1] + c[:, 1] * step])
        ia = int(np.argmin(np.linalg.norm(C - Pb[0, :2], axis=1)))
        ib = int(np.argmin(np.linalg.norm(C - Pb[-1, :2], axis=1)))
        d = float(np.linalg.norm(C[ia] - Pb[0, :2]) + np.linalg.norm(C[ib] - Pb[-1, :2]))
        if best is None or d < best[0]:
            best = (d, C, ia, ib)
    if best is None or best[0] > 4.0 * step:
        return np.asarray(P, np.float64), False
    _, C, ia, ib = best
    path = C[ia:ib + 1] if ia <= ib else C[ib:ia + 1][::-1]
    path = np.vstack([Pb[0, :2], path, Pb[-1, :2]])
    acc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    n = h_b - h_a
    t = acc[-1] * np.arange(1, n) / n
    out = np.array(P, np.float64)
    out[h_a + 1:h_b, 0] = np.interp(t, acc, path[:, 0])
    out[h_a + 1:h_b, 1] = np.interp(t, acc, path[:, 1])
    out[h_a + 1:h_b, 2] = s_z
    return out, True


def frac_of(body, P):
    """each point's arc fraction on the analytic half section at its station, by its direction from the origin"""
    out = []
    for p in np.atleast_2d(P):
        s = float(body.s_of(p[2]))
        Pp, L = body.half_section(min(s, 0.9995))
        O = origin(body, s)
        a_p = math.atan2(abs(p[0]) - O[0], p[1] - O[1])
        a = np.arctan2(Pp[:, 0] - O[0], Pp[:, 1] - O[1])          # 0 dorsal .. pi ventral, monotone
        out.append(float(np.interp(a_p, a, L) / L[-1]))
    return np.array(out)


# ============================================================================================ the column table
def column_table(n, H, cons, w_ring=1.0):
    """F[i, h] (h = 0 .. H) for n rings: the constraints cons = list of (i, h, f) as Dirichlet values (plus F[:, 0] = 0,
    F[:, H] = 1); the rest HARMONIC over the (ring, column) grid (a sparse solve; w_ring weights the neighbours along
    the body against those round the ring; the first and last rings have one neighbour along)"""
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla
    F = np.tile(np.linspace(0.0, 1.0, H + 1), (n, 1))
    fix = np.zeros((n, H + 1), bool)
    fix[:, 0] = fix[:, H] = True
    for i, h, f in cons:
        F[i, h] = f
        fix[i, h] = True
    idx = -np.ones((n, H + 1), int)
    unk = np.argwhere(~fix)
    idx[~fix] = np.arange(len(unk))
    rows, cols, vals = [], [], []
    b = np.zeros(len(unk))
    for r, (i, h) in enumerate(unk):
        nbs = [(i, h - 1, 1.0), (i, h + 1, 1.0)]
        if i > 0:
            nbs.append((i - 1, h, w_ring))
        if i < n - 1:
            nbs.append((i + 1, h, w_ring))
        diag = 0.0
        for ii, hh, w in nbs:
            diag += w
            if fix[ii, hh]:
                b[r] += w * F[ii, hh]
            else:
                rows.append(r)
                cols.append(idx[ii, hh])
                vals.append(-w)
        rows.append(r)
        cols.append(r)
        vals.append(diag)
    A = sp.csr_matrix((vals, (rows, cols)), shape=(len(unk), len(unk)))
    F[~fix] = spla.spsolve(A.tocsc(), b)
    return F, fix


# ============================================================================================ the layout
def half_section_len(body, s):
    return float(body.half_section(min(s, 0.9995))[1][-1])


def red_aligned(units, n_in):
    """the outer ring's arc fractions (half, dorsal 0 .. ventral 1) that line each reduction unit up with its inner
    chord on an equal-arc inner ring of n_in chords: a T's three outer chords share one inner chord, an S's one"""
    f, out = 0.0, [0.0]
    for u in units:
        if u == 'x':
            continue
        n_out = 3 if u in 'TR' else 1
        for _ in range(n_out):
            f += 1.0 / n_in / n_out
            out.append(f)
    out[-1] = 1.0
    return np.array(out)


def red_units(units):
    """the units' start indices: (outer chord index, inner chord index, kind) per unit"""
    out, j_in = [], 0
    for j, u in enumerate(units):
        if u == 'x':
            continue
        out.append((j, j_in, u))
        j_in += 1
    return out


def layout(spec, body, rec, ports, cg, foot_fore, foot_hind):
    """the K 64 rings' column table: the blocks (each a rectangle of grid cells), the mouth line, the poll, harmonic
    between. Returns a dict"""
    L_ = LAY
    TL = spec['a1']['TL']
    st = spec['stations']
    S_ = stations(spec, body, rec, e_c=float(st['hip'] - np.asarray(cg['eye']['E'], np.float64)[2] / TL))
    k64 = np.array(S_['k64'])
    n64 = len(k64)
    ix = lambda s: int(np.argmin(np.abs(k64 - s)))                     # noqa: E731
    hp = lambda s: half_section_len(body, s)                           # noqa: E731
    cons, blocks, notes = [], {}, []

    def block(name, ia, ib, h_a, h_b, fracs_of_ring):
        for i in range(ia, ib + 1):
            fr = fracs_of_ring(k64[i])
            for h, f in zip(range(h_a, h_b + 1), fr):
                cons.append((i, h, float(f)))
        blocks[name] = dict(rings=(ia, ib), cols=(h_a, h_b))

    # ---- the mouth line (to the commissure's ring) and the lower lip's column lip_gap below it; AX7b: the line's
    # height is caudate's smile at each ring (heads/caudate.mouth_height)
    from ..heads import caudate as CD
    i_c = ix(st['commissure'])
    sm_x = cg['frontal'].get('smile_x')
    lob_ = cg['frontal'].get('lobe') or {}
    pearls = lob_.get('pearl') is not None and L_.get('bead_rows') is not None
    eye0 = S_['named']['eye'][0]
    gaps, n_rows = [], 0
    for i in range(0, i_c + 1):
        s_i = max(k64[i], CD.LAYOUT['s0'])
        fm, x_m, y_m = CD.mouth_point(body, cg['frontal'], s_i)   # AX7c: the smile across the front (or AX7b's law)
        gap = L_['lip_gap']
        if sm_x is not None:
            # AX8: the gap narrows from the U's end to the commissure (LAY lip_gap_corner's note)
            x_U, x_c = sm_x[4], sm_x[3]
            gap *= 1.0 - (1.0 - L_['lip_gap_corner']) * CD.smooth01((abs(x_m) - x_U) / max(x_c - x_U, 1e-6))
        if pearls and L_.get('lip_gap_bead') is not None:
            # AX10: the gap closes to lip_gap_bead under the pearls (LAY's note), by their weight along the line
            w_p = CD.lobe_weight(cg['frontal'], s_i, None)
            gap = gap + (min(gap, L_['lip_gap_bead']) - gap) * w_p
        if CD.pearls_are_parts(spec) and L_.get('lip_gap_drop') is not None:
            # AX13: the lips closed behind the droplets and on to the corner (LAY lip_gap_drop's note)
            xd0, xd1 = (float(v) * spec['a1']['HW'] for v in L_['lip_gap_drop_x'])
            w_d = CD.smooth01((abs(x_m) - xd0) / max(xd1 - xd0, 1e-6))
            gap = gap + (min(gap, L_['lip_gap_drop']) - gap) * w_d
        gaps.append(gap)
        # (the lower lip `gap` mm of ARC down the section; AX8 tried `gap` mm BELOW, as the snout cap's row is placed: on
        # the rounder snout sections (caudate SECTION yw_floor) 0.9 mm down is 1.8 mm in at ring 0, the cap's lower row
        # followed it inward and AX4 gate 10 failed (mouth aspect p99 6.20, the head's max 10.07). The cap now meets the
        # ring instead: assemble()'s cap row eases its drop to ring 0's own)
        cons += [(i, L_['h_mouth'], fm), (i, L_['h_mouth'] + 1, fm + gap / hp(k64[i]))]
        if pearls and 0 < i and k64[i] < eye0 - 1e-9:
            # AX10: the lower lip's next rows dense on the pearls' rings (LAY bead_rows)
            br = L_['bead_rows']
            for k in range(1, br['n'] + 1):
                cons.append((i, L_['h_mouth'] + 1 + k, fm + (gap + k * br['step']) / hp(k64[i])))
            if br.get('above'):
                # the upper lip's next column `above` mm of arc over the margin on those rings: the dense rings
                # against the free columns over the lip made a band of quads 0.4 x 2 mm there (gate 10)
                cons.append((i, L_['h_mouth'] - 1, fm - br['above'] / hp(k64[i])))
            n_rows += 1
    notes.append(f'the lips\' gap {gaps[0]:.2f} mm at the front ring, {gaps[-1]:.2f} at the commissure\'s (ring {i_c})' +
                 (f'; under the pearls down to {min(gaps):.2f} mm, the lower lip\'s next {L_["bead_rows"]["n"]} rows '
                  f'{L_["bead_rows"]["step"]} mm apart on {n_rows} rings' if pearls else ''))
    # ---- the eye block (4 x 4 cells round the rim)
    E = cg['eye']
    f_e = float(frac_of(body, np.asarray(E['surface_point']))[0])
    eye = S_['named']['eye']
    block('eye_L', ix(eye[0]), ix(eye[-1]), *L_['eye_cols'],
          lambda s: f_e + (np.arange(5) - 2) * (0.5 * L_['eye_r'] / hp(s)))
    # ---- the horn ports (4 x 4)
    hr = S_['named']['horns']
    f_hl = float(frac_of(body, np.asarray(ports['horn_L']['centre_mm']))[0])
    block('horn_L', ix(hr[0]), ix(hr[4]), *L_['horn_cols'],
          lambda s: f_hl + (np.arange(5) - 2) * (0.5 * L_['horn_half'][0] / hp(s)))
    block('horn_mid', ix(hr[2]), ix(hr[6]), *L_['hmid_cols'], lambda s: np.arange(3) * (0.5 * L_['horn_half'][0] / hp(s)))
    # ---- the poll (the record's own columns)
    i_poll = ix(rec['poll']['station'])
    Vp = np.array(rec['poll']['verts_mm'])
    f_poll = frac_of(body, Vp[[(16 - h) % 64 for h in range(33)]])
    for h in range(1, 32):
        cons.append((i_poll, h, float(f_poll[h])))
    # ---- the gill block: three sockets side by side on the gill rings, strips between
    gl = S_['named']['gill']
    f_r = {r: float(frac_of(body, np.asarray(ports[f'gill_port_{r[1]}_L']['centre_mm']))[0]) for r in ('r1', 'r2', 'r3')}

    def gill_fr(s):
        out = {}
        for r in ('r1', 'r2', 'r3'):
            d = L_['gill_w'][r] / hp(s)
            for k in range(4):
                out[L_['gill_cols'][r] + k] = f_r[r] + (k - 1.5) * d
        h1, h2 = L_['gill_cols']['r1'] + 3, L_['gill_cols']['r2']
        for h in range(h1 + 1, h2):
            out[h] = out[h1] + (out[h2] - out[h1]) * (h - h1) / (h2 - h1)
        return [out[h] for h in range(L_['gill_cols']['r1'], L_['gill_cols']['r3'] + 4)]
    ig0, ig1 = ix(gl[0]), ix(gl[-1])
    block('gill', ig0, ig1, L_['gill_cols']['r1'], L_['gill_cols']['r3'] + 3, gill_fr)
    for r in ('r1', 'r2', 'r3'):
        blocks[f'gill_{r}'] = dict(rings=(ig0, ig1), cols=(L_['gill_cols'][r], L_['gill_cols'][r] + 3))
    # ---- the limbs' port blocks: 3 across x 5 along round each footprint (+ margin)
    for nm, foot, cols, i0 in (('fore', foot_fore, L_['fore_cols'], ig1),
                               ('hind', foot_hind, L_['hind_cols'], ix(S_['named']['hind'][0]))):
        cf = frac_of(body, foot)
        sf = body.s_of(foot[:, 2])
        notes.append(f'the {nm} block: rings {k64[i0]:.4f}-{k64[i0 + 5]:.4f} round the footprint {sf.min():.4f}-'
                     f'{sf.max():.4f} (margins {(sf.min() - k64[i0]) * TL:.2f} / {(k64[i0 + 5] - sf.max()) * TL:.2f} '
                     f'mm), arc fractions {cf.min():.3f}-{cf.max():.3f}')
        margin = L_[f'{nm}_margin']
        block(f'{nm}_L', i0, i0 + 5, cols[0], cols[1],
              lambda s, cf=cf, margin=margin: np.linspace(cf.min() - margin / hp(s), cf.max() + margin / hp(s), 4))
        # the columns under the block, linear to the ventral midline on its rings (its wide cells sit lower than the
        # natural columns; left harmonic the ones under it crossed where they relaxed: an edge of 0.002 mm)
        for i in range(i0, i0 + 6):
            f_b = cf.max() + margin / hp(k64[i])
            for h in range(cols[1] + 1, 32):
                cons.append((i, h, f_b + (1.0 - f_b) * (h - cols[1]) / (32 - cols[1])))
            # and a strip of L_['strip'] mm above it (the free column there narrowed to 0.23 mm toward the block's
            # last ring, dragged by the rings relaxing after it)
            if not (nm == 'fore' and i == i0):                  # (the first fore ring: r3's own bottom line)
                cons.append((i, cols[0] - 1, cf.min() - (margin + L_['strip']) / hp(k64[i])))
    # ---- the wing port (5 across x 7 along) and the back ports (6 x 6, the half 3 across): the ring span nearest
    # each port's centre
    f_w = float(frac_of(body, np.asarray(ports['wing_L']['centre_mm']))[0])
    iw0 = int(np.argmin([abs(0.5 * (k64[i] + k64[i + 7]) - ports['wing_L']['station']) for i in range(n64 - 7)]))
    block('wing_L', iw0, iw0 + 7, *L_['wing_cols'],
          lambda s: f_w + (np.arange(6) - 2.5) * (2 * ports['wing_L']['half_across_mm'] / 5 / hp(s)))
    for b in ('back_0', 'back_1', 'back_2'):
        ib0 = int(np.argmin([abs(0.5 * (k64[i] + k64[i + 6]) - ports[b]['station']) for i in range(n64 - 6)]))
        block(b, ib0, ib0 + 6, *L_['back_cols'], lambda s: np.arange(4) * L_['back_cell'] / hp(s))
    # ---- before the reduction: the last ring aligned with the T units (each unit's outer columns spanning its inner
    # chord on the equal-arc K 32 ring), the hips' rings harmonic from the hind block to it (equal arc pinned 0.027 TL
    # before it left one ring step for the change: column edges 5.1-5.4 mm long)
    for h, f in enumerate(red_aligned(RED1, 16)):
        if 0 < h < 32:
            cons.append((n64 - 1, h, f))
    seen, count = {}, {}
    for i, h, f in cons:
        seen[(i, h)] = f
        count[(i, h)] = count.get((i, h), 0) + 1
    clash = [k for k, c in count.items() if c > 1]
    # on each ring the free columns between two pinned ones (neither on a midline) evenly between them: the harmonic
    # fill let the rings after a block drag the columns beside it (a cell of 0.43 mm between the wing and the fore
    # block); the rings with no pinned columns stay harmonic
    for i in range(n64):
        hs = sorted(h for (ii, h) in seen if ii == i)
        for a, b in zip(hs[:-1], hs[1:]):
            if b - a > 1 and a > 0 and b < 32 and i != n64 - 1:
                for h in range(a + 1, b):
                    seen[(i, h)] = seen[(i, a)] + (seen[(i, b)] - seen[(i, a)]) * (h - a) / (b - a)
    F, fix = column_table(n64, 32, [(i, h, f) for (i, h), f in seen.items()])
    notes.append(f'the K 64 column table: {n64} rings, {int(fix.sum())} fixed entries, the narrowest column '
                 f'{np.diff(F, axis=1).min():.4f} of the half arc; cells pinned twice (the blocks\' shared lines): '
                 f'{len(clash)}')
    return dict(stations=S_, k64=k64, F=F, fix=fix, blocks=blocks, i_c=i_c, i_poll=i_poll, ig=(ig0, ig1), notes=notes)


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


class Half:
    """a mesh under construction (the half body, later the full one): vertices (life mm), a region per vertex, fixed
    flags, quads, the midline vertices"""

    def __init__(self):
        self.V, self.R, self.fx, self.Q, self.mid = [], [], [], [], set()

    def add(self, P, region, fixed=False, midline=None):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        n0 = sum(len(v) for v in self.V)
        self.V.append(P)
        self.R.append(np.full(len(P), BREGIONS.index(region)))
        self.fx.append(np.broadcast_to(np.asarray(fixed, bool), (len(P),)).copy())
        ids = np.arange(n0, n0 + len(P))
        if midline is not None:
            for k in midline:
                self.mid.add(int(ids[k]))
        return ids

    def quad(self, a, b, c, d):
        self.Q.append((int(a), int(b), int(c), int(d)))

    def band(self, ra, rb):
        """quads between two half rings of equal length, h increasing down the left side"""
        for h in range(len(ra) - 1):
            self.quad(ra[h], ra[h + 1], rb[h + 1], rb[h])

    def arrays(self):
        return np.concatenate(self.V), np.concatenate(self.R), np.concatenate(self.fx), np.array(self.Q, np.int64)


def region_of(s, st):
    return 'head' if s < st['poll'] else ('neck' if s < st['shoulder_joint'] else ('trunk' if s < st['vent'] else 'tail'))


def reduction(hb, outer, f_out, inner, f_in, s_mid, units, body, field, region):
    """a two-row REDUCTION band between the half rings outer (its fractions f_out) and inner (f_in): the middle row
    (one vertex per inner column, cast halfway between the inner column and its unit's first outer column) and the
    units: S one outer chord to one inner, T three to one (its 5-pole the middle row's vertex, its 3-pole on the
    outer ring: sprawl_cage's tile, 3 / 5 poles only), R a T reversed"""
    uu = red_units(units)
    anchor = [j for j, _, _ in uu] + [len(outer) - 1]
    f_mid = 0.5 * (np.asarray(f_in) + np.asarray(f_out)[anchor])
    P, ok = cast_half(field, body, s_mid, f_mid)
    mid = hb.add(P, region, midline=(0, len(f_mid) - 1))
    poles = []
    for j, k, u in uu:
        if u == 'S':
            hb.quad(outer[j], outer[j + 1], mid[k + 1], mid[k])
        elif u == 'T':                                           # 5-pole mid[k + 1], 3-pole outer[j + 2]
            hb.quad(outer[j], outer[j + 1], mid[k + 1], mid[k])
            hb.quad(outer[j + 1], outer[j + 2], outer[j + 3], mid[k + 1])
            poles += [int(mid[k + 1]), int(outer[j + 2])]
        else:                                                    # 'R': 5-pole mid[k], 3-pole outer[j + 1]
            hb.quad(outer[j], outer[j + 1], outer[j + 2], mid[k])
            hb.quad(outer[j + 2], outer[j + 3], mid[k + 1], mid[k])
            poles += [int(mid[k]), int(outer[j + 1])]
    hb.band(mid, inner)
    return mid, poles, bool(ok.all())


def assemble(spec, body, field, rec, cg, lay):
    """the half body's loft (the module docstring): K 64 rings with the snout cap, the 64 -> 32 band, the K 32 rings
    with the tail root, the 32 -> 16 band, the K 16 rings with the tail mid, the 16 -> 8 band, the K 8 rings and the
    tip cap. field: the body's clay alone. Returns (Half, info)"""
    L_ = LAY
    TL = spec['a1']['TL']
    st = spec['stations']
    S_ = lay['stations']
    k64, F = lay['k64'], lay['F']
    n64 = len(k64)
    hb = Half()
    notes = []
    # ---- the K 64 rings (the poll the record's own vertices, its left half)
    R64 = []
    band = L_.get('clay_band')
    n_band = 0
    for i, s in enumerate(k64):
        if i == lay['i_poll']:
            P = np.array(rec['poll']['verts_mm'])[[(16 - h) % 64 for h in range(33)]]
            R64.append(hb.add(P, region_of(s, st), fixed=True, midline=(0, 32)))
            continue
        P, ok = cast_half(field, body, s, F[i])
        assert ok.all(), f'a K 64 ring at s {s:.4f} missed the clay'
        if i == 0:
            r0_cast = P.copy()             # the snout cap's Coons patch reads ring 0 as cast (below)
        if band and L_.get('band_from', 0) <= i <= lay['i_c']:
            # AX10: the band under the lower lip on the clay's own section, evenly by its arc (LAY clay_band; AX13: from
            # ring LAY band_from on)
            P, ok_b = band_contour(field, float(body.z(s)), P, L_['h_mouth'] + band[0], L_['h_mouth'] + band[1])
            n_band += int(ok_b)
        R64.append(hb.add(P, region_of(s, st), midline=(0, 32)))
    for i in range(n64 - 1):
        hb.band(R64[i], R64[i + 1])
    if band:
        notes.append(f'the band under the lower lip (columns {L_["h_mouth"] + band[0]}-{L_["h_mouth"] + band[1]}) on the '
                     f'clay\'s section contour: {n_band} of the mouth\'s {lay["i_c"] + 1} rings')
    # ---- the snout cap: C[a, b] (a 0 = the midline .. hx = ring 0; b 0 = the top .. ny = the bottom)
    hx, ny = L_['hx'], L_['ny']
    bm = L_['h_mouth'] - hx
    V0 = np.concatenate(hb.V)
    r0 = V0[R64[0]]
    # (AX10: the patch's (x, y) from ring 0 moved LAY cap_cast of the way back to ring 0 AS CAST: its band moved onto
    # the first pearl's front pulled the patch's lower-lip row 0.4 mm out past ring 0's own lower lip, and the +z casts
    # from there landed behind ring 0: a fold)
    r0_xy = r0 + L_['cap_cast'] * (r0_cast - r0)
    top = np.array([r0_xy[a, :2] for a in range(hx + 1)])
    bot = np.array([r0_xy[32 - a, :2] for a in range(hx + 1)])
    right = np.array([r0_xy[hx + b, :2] for b in range(ny + 1)])
    t_y, b_y = r0[0, 1], r0[32, 1]
    from ..heads import caudate as CD
    y_m = float(CD.smile_y(cg['frontal'], 0.0))            # the smile's front (AX7c: caudate.smile_y; AX7b's law without)
    yb = np.concatenate([np.linspace(t_y, y_m, bm + 1), np.linspace(y_m - L_['lip_gap'], b_y, ny - bm)])
    left = np.column_stack([np.zeros(ny + 1), yb])
    Cxy = coons(top, bot, left, right)                      # the cap in (x, y): where the lip rows' casts start
    if L_.get('cap_align'):
        # AX10: both lip rows' x on the cap's bottom row's (ring 0's ventral columns as built), easing back to the
        # Coons x over the last cap_align columns before ring 0: the Coons x at the lower lip row was 0.8 the way to
        # that bottom row and ~17 % narrower, so the strip under the lower lip (0.2-0.5 mm tall there) ran diagonally,
        # quads of 21-25 deg
        # (the last n_al columns linear in x from there to ring 0's own lip vertex: left to the Coons patch, the last
        # one came 0.16 mm from ring 0's, the lip's edge there 0.18 mm long)
        n_al = int(L_['cap_align'])
        a1 = hx - 1 - n_al
        for b in (bm, bm + 1):
            for a in range(1, a1 + 1):
                Cxy[a, b, 0] = r0[32 - a, 0]
            for a in range(a1 + 1, hx):
                Cxy[a, b, 0] = Cxy[a1, b, 0] + (r0[hx + b, 0] - Cxy[a1, b, 0]) * (a - a1) / float(hx - a1)
    if cg['frontal'].get('smile_x') is not None:
        # AX7c: the two lip rows at the clay's U for their own offsets (its lobes in), not the Coons patch's straight
        # run between the midline and ring 0 (the U is curved across the cap: up to 0.2 mm off the clay's crease).
        # AX8: THE CAP'S LOWER LIP MEETS RING 0'S: its drop under the upper eases from lip_gap to ring 0's own (the ring's
        # lower lip is lip_gap of ARC down a section that curves in under the mouth: 0.35 mm under the upper on the AX8
        # clay) over the cap's last LAY lip_meet columns; at a full lip_gap to the last column the lower lip jumped 0.7 mm
        # in its place between the cap and ring 0 (ax8_notes/lip_pairs.py), the groove's facing turning there: the AX7c
        # check's nick
        drop0 = float(r0[hx + bm, 1] - r0[hx + bm + 1, 1])
        # (AX13: lip_meet_drop with the droplets, LAY's note)
        lm_ = int(L_['lip_meet_drop']) if CD.pearls_are_parts(spec) and L_.get('lip_meet_drop') else int(L_['lip_meet'])
        a0 = hx - lm_
        for a in range(1, hx):
            Cxy[a, bm, 1] = CD.smile_y(cg['frontal'], Cxy[a, bm, 0])
            t_m = CD.smooth01((a - a0) / float(lm_))
            Cxy[a, bm + 1, 1] = Cxy[a, bm, 1] - (L_['lip_gap'] + (drop0 - L_['lip_gap']) * t_m)
        notes.append(f'the cap\'s lower lip: its drop {L_["lip_gap"]:.2f} mm easing to ring 0\'s {drop0:.2f} over the last '
                     f'{lm_} columns')
    z0 = float(r0[:, 2].mean())
    C = -np.ones((hx + 1, ny + 1), int)
    for a in range(hx + 1):
        C[a, 0] = R64[0][a]
        C[a, ny] = R64[0][32 - a]
    for b in range(ny + 1):
        C[hx, b] = R64[0][hx + b]
    inner = [(a, b) for a in range(hx) for b in range(1, ny)]
    # the midline column and the two lip rows cast along +z from behind (the lips' rows at the mouth's heights); each
    # half of the cap (above the mouth, below it) a 3D Coons patch of its four boundary curves moved onto the nearest
    # clay (any cast of the whole grid from inside the head landed the rows under the lip on the lower lip's narrow
    # front face: rows 0.1 mm apart)
    P3 = np.zeros((hx + 1, ny + 1, 3))
    for a in range(hx + 1):
        P3[a, 0], P3[a, ny] = V0[C[a, 0]], V0[C[a, ny]]
    for b in range(ny + 1):
        P3[hx, b] = V0[C[hx, b]]
    cast_ab = [(0, bm), (0, bm + 1)] + [(a, b) for a in range(1, hx) for b in (bm, bm + 1)]
    O = np.array([(Cxy[a, b, 0] if a else 0.0, Cxy[a, b, 1], z0 - 1.5) for a, b in cast_ab])
    Pcast, ok = field.cast(O, np.tile([0.0, 0.0, 1.0], (len(O), 1)), 12.0)
    assert ok.all(), 'a snout cap cast missed the snout'
    for (a, b), p in zip(cast_ab, Pcast):
        P3[a, b] = p
    # the midline column evenly by ARC along the snout's midline profile (the plane x = 0): from ring 0's dorsal
    # vertex to the upper lip, from the lower lip to its ventral vertex (rows at even heights crowded where the chin
    # curves back under)
    O_m = np.array([0.0, y_m, z0 - 3.0])
    for b0, b1 in ((0, bm), (bm + 1, ny)):
        pa, pb = P3[0, b0] - O_m, P3[0, b1] - O_m
        a0, a1 = math.atan2(pa[1], pa[2]), math.atan2(pb[1], pb[2])
        angs = np.linspace(a0, a1, 129)
        Dm = np.column_stack([np.zeros_like(angs), np.sin(angs), np.cos(angs)])
        Pm, okm = field.cast(np.tile(O_m, (len(angs), 1)), Dm, 30.0)
        assert okm[1:-1].all(), 'a snout profile cast missed'
        Pm[0], Pm[-1] = P3[0, b0], P3[0, b1]
        acc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pm, axis=0), axis=1))])
        for b in range(b0 + 1, b1):
            t = (b - b0) / (b1 - b0) * acc[-1]
            P3[0, b] = np.array([np.interp(t, acc, Pm[:, k]) for k in range(3)])
    P3[0, :, 0] = 0.0
    for b0, b1 in ((0, bm), (bm + 1, ny)):
        patch = coons(P3[:, b0], P3[:, b1], P3[0, b0:b1 + 1], P3[hx, b0:b1 + 1])
        for a in range(1, hx):
            for b in range(b0 + 1, b1):
                P3[a, b] = patch[a, b - b0]
    fill = [(a, b) for a in range(1, hx) for b in range(1, ny) if b not in (bm, bm + 1)]
    Pf = field.nearest(np.array([P3[a, b] for a, b in fill]), iters=10)
    for (a, b), p in zip(fill, Pf):
        P3[a, b] = p
    P = np.array([P3[a, b] for a, b in inner])
    P[[k for k, (a, b) in enumerate(inner) if a == 0], 0] = 0.0
    cid = hb.add(P, 'cap', midline=[k for k, (a, b) in enumerate(inner) if a == 0])
    for k, (a, b) in enumerate(inner):
        C[a, b] = cid[k]
    for a in range(hx):
        for b in range(ny):
            hb.quad(C[a, b], C[a, b + 1], C[a + 1, b + 1], C[a + 1, b])
    # ---- the 64 -> 32 band and the K 32 rings (the tail root the record's), their columns harmonic from the band's
    # equal arc through the record to the second band's aligned ring
    k32 = S_['k32']
    i_tr = int(np.argmin(np.abs(np.array(k32) - rec['tail_root']['station'])))
    Vtr = np.array(rec['tail_root']['verts_mm'])
    P_tr = Vtr[[(24 + h) % 32 for h in range(17)]]
    f_tr = frac_of(body, P_tr)
    cons32 = [(0, h, h / 16.0) for h in range(1, 16)] + [(i_tr, h, float(f_tr[h])) for h in range(1, 16)] + \
        [(len(k32) - 1, h, float(f)) for h, f in enumerate(red_aligned(RED2, 8)) if 0 < h < 16]
    F32, _ = column_table(len(k32), 16, cons32)
    R32 = []
    for i, s in enumerate(k32):
        if i == i_tr:
            R32.append(hb.add(P_tr, 'tail', fixed=True, midline=(0, 16)))
            continue
        P, ok = cast_half(field, body, s, F32[i])
        assert ok.all(), f'a K 32 ring at s {s:.4f} missed'
        R32.append(hb.add(P, region_of(s, st), midline=(0, 16)))
    mid1, poles1, ok1 = reduction(hb, R64[-1], F[-1], R32[0], F32[0], S_['mid1'], RED1, body, field, 'tail')
    for i in range(len(k32) - 1):
        hb.band(R32[i], R32[i + 1])
    # ---- the 32 -> 16 band and the K 16 rings: equal arc after the band, the tail mid's own columns on the rings beside
    # it, the record, and equal arc again toward the tip (the record's sag spacing, crowded at the lens's tips, carried
    # to the thin tip made quads of aspect 7-15 there)
    k16 = S_['k16']
    i_tm = int(np.argmin(np.abs(np.array(k16) - rec['tail_mid']['station'])))
    Vtm = np.array(rec['tail_mid']['verts_mm'])
    P_tm = Vtm[[(12 + h) % 16 for h in range(9)]]
    f_tm = frac_of(body, P_tm)
    cons16 = [(0, h, h / 8.0) for h in range(1, 8)] + \
        [(i, h, float(f_tm[h])) for i in range(i_tm - 1, min(i_tm + 2, len(k16))) for h in range(1, 8)] + \
        [(i, h, h / 8.0) for i in range(len(k16) - 2) if k16[i] >= 0.88 for h in range(1, 8)] + \
        [(len(k16) - 1, h, float(f)) for h, f in enumerate(red_aligned(RED3, 4)) if 0 < h < 8]
    F16, _ = column_table(len(k16), 8, cons16)
    R16 = []
    for i, s in enumerate(k16):
        if i == i_tm:
            R16.append(hb.add(P_tm, 'tail', fixed=True, midline=(0, 8)))
            continue
        P, ok = cast_half(field, body, s, F16[i])
        assert ok.all(), f'a K 16 ring at s {s:.4f} missed'
        R16.append(hb.add(P, 'tail', midline=(0, 8)))
    mid2, poles2, ok2 = reduction(hb, R32[-1], F32[-1], R16[0], F16[0], S_['mid2'], RED2, body, field, 'tail')
    for i in range(len(k16) - 1):
        hb.band(R16[i], R16[i + 1])

    # ---- the tip: the 16 -> 8 band, K 8 rings (equal arc), a 1 x 2 cap per half on the field's tip (bisection along
    # the midline at the tail's mid-height for the last station inside)
    def inside(s):
        t, b = body.top_bot(min(s, 0.9995))
        return float(field.eval(np.array([[0.0, 0.5 * (t + b), float(body.z(s))]]))[0]) < 0.0
    lo, hi = S_['k8'][0], 1.0
    for _ in range(40):
        m_ = 0.5 * (lo + hi)
        lo, hi = (m_, hi) if inside(m_) else (lo, m_)
    s_tip = lo
    k8 = [s for s in S_['k8'] if s <= s_tip - LAY['tip_gap'] / TL] or S_['k8'][:1]
    R8 = []
    for s in k8:
        P, ok = cast_half(field, body, s, np.arange(5) / 4.0)
        assert ok.all(), f'a K 8 ring at s {s:.4f} missed'
        R8.append(hb.add(P, 'tail', midline=(0, 4)))
    mid3, poles3, ok3 = reduction(hb, R16[-1], F16[-1], R8[0], np.arange(5) / 4.0, S_['mid3'], RED3, body, field,
                                  'tail')
    for i in range(len(k8) - 1):
        hb.band(R8[i], R8[i + 1])
    rl = R8[-1]
    t_, b_ = body.top_bot(min(s_tip, 0.9995))
    Pt = field.nearest(np.array([[0.0, 0.5 * (t_ + b_), float(body.z(s_tip))]]), iters=12)
    Pt[:, 0] = 0.0
    okt = abs(float(field.eval(Pt)[0])) < 0.01
    tid = hb.add(Pt, 'tailcap', midline=(0,))
    T = np.array([[rl[0], tid[0], rl[4]], [rl[1], rl[2], rl[3]]])
    for b in range(2):
        hb.quad(T[0, b], T[1, b], T[1, b + 1], T[0, b + 1])
    notes.append(f'the loft: {n64} K 64 rings (s {k64[0]:.4f}-{k64[-1]:.4f}), the snout cap {hx} x {ny} per half, the '
                 f'64 -> 32 band at s {k64[-1]:.4f}-{k32[0]:.4f} ({RED1}), {len(k32)} K 32 rings (the tail root '
                 f'{k32[i_tr]:.4f}), the 32 -> 16 band at {k32[-1]:.4f}-{k16[0]:.4f} ({RED2}), {len(k16)} K 16 rings '
                 f'(the tail mid {k16[i_tm]:.4f}) to {k16[-1]:.4f}, the 16 -> 8 band ({RED3}), {len(k8)} K 8 rings to '
                 f'{k8[-1]:.4f}, a 1 x 2 tip cap per half on the clay\'s tip (s {s_tip:.4f}, z {float(Pt[0, 2]):.2f}); '
                 f'the casts ok {ok1 and ok2 and ok3}, the tip on the clay {okt}')
    info = dict(R64=R64, R32=R32, R16=R16, R8=R8, C=C, T=T, mid1=mid1, mid2=mid2, mid3=mid3, s_tip=s_tip,
                poles_red=poles1 + poles2 + poles3, i_tr=i_tr, i_tm=i_tm, F32=F32, F16=F16, notes=notes)
    return hb, info


def record_rings(rec, info, lay):
    """the three records on the loft: their half rings (h order), the records' own right halves, and each half
    vertex's record index on the left (kl) and of its mirror (kr)"""
    out = {}
    for name, ids, K, c, sgn in (('poll', info['R64'][lay['i_poll']], 64, 16, -1),
                                 ('tail_root', info['R32'][info['i_tr']], 32, 24, 1),
                                 ('tail_mid', info['R16'][info['i_tm']], 16, 12, 1)):
        Vr = np.array(rec[name]['verts_mm'])
        h = np.arange(K // 2 + 1)
        kl, kr = (c + sgn * h) % K, (c - sgn * h) % K
        out[name] = dict(ids=np.asarray(ids), right=Vr[kr], K=K, kl=kl, kr=kr)
    return out


def mirror(hb, rec_rings):
    """the full body: the half and its mirror x -> -x welded on the midline, the right half's quads reversed; the
    record rings' right halves set to the records' own vertices (AX3's casts are mirror-symmetric to ~4e-6 mm only,
    and the rings must stay bit for bit). rec_rings: [(half ids (h order), the record's right-half vertices by h)].
    Returns (V, Q, regions, fixed, mir (half id -> its mirror's id))"""
    V, R, fx, Q = hb.arrays()
    n = len(V)
    is_mid = np.zeros(n, bool)
    is_mid[list(hb.mid)] = True
    off = np.cumsum(~is_mid) - 1 + n
    mir = np.where(is_mid, np.arange(n), off)
    nf = n + int((~is_mid).sum())
    Vf = np.zeros((nf, 3))
    Vf[:n] = V
    Vm = V.copy()
    Vm[:, 0] *= -1.0
    Vf[mir[~is_mid]] = Vm[~is_mid]
    for ids, right in rec_rings:
        for h, v in enumerate(ids):
            if not is_mid[v]:
                Vf[mir[v]] = right[h]
    Qf = np.vstack([Q, mir[Q][:, ::-1]])
    Rf = np.concatenate([R, R[~is_mid]])
    fxf = np.concatenate([fx, fx[~is_mid]])
    return Vf, Qf, Rf, fxf, mir


# ============================================================================================ the port surgery
def half_V(hb):
    return np.concatenate(hb.V)


def half_cut(hb, cells):
    """remove the quads with these vertex sets (each a 4-tuple of ids); returns the hole's boundary loop, ordered the
    way the remaining faces run along it (loft.boundary_loop's order)"""
    keys = {frozenset(int(v) for v in c) for c in cells}
    removed = [q for q in hb.Q if frozenset(q) in keys]
    assert len(removed) == len(keys), f'{len(keys) - len(removed)} cells not found'
    hb.Q = [q for q in hb.Q if frozenset(q) not in keys]
    rv = set(v for q in removed for v in q)
    m = QuadMesh(half_V(hb), np.array(hb.Q, np.int64))
    loops = [lp for lp in LF.boundary_loop(m) if set(lp) & rv]
    assert len(loops) == 1, f'{len(loops)} hole loops'
    return np.array(loops[0])


def half_extend(hb, loop, rings, region, fixed=False):
    """rings of new vertices off the loop (ring m's vertex i over the loop's vertex i), each band of quads running
    against the ring before it (ports.extend's winding); fixed: one flag per ring. Returns the rings' ids (the loop
    first)"""
    ids = [np.asarray(loop)]
    K = len(loop)
    fl = fixed if isinstance(fixed, (list, tuple)) else [fixed] * len(rings)
    for P, f in zip(rings, fl):
        new = hb.add(np.asarray(P).reshape(K, 3), region, fixed=f)
        X, Y = ids[-1], new
        for i in range(K):
            i1 = (i + 1) % K
            hb.quad(X[i1], X[i], Y[i], Y[i1])
        ids.append(new)
    return ids


def match_ring(P_loop, P_ring):
    """the target ring's order that best follows the loop (cyclic shift and direction, the least summed distance):
    returns the index map (loop vertex i -> ring vertex m[i])"""
    K = len(P_loop)
    best = None
    for d in (1, -1):
        for s in range(K):
            m = (s + d * np.arange(K)) % K
            c = float(np.linalg.norm(P_loop - P_ring[m], axis=1).sum())
            if best is None or c < best[0]:
                best = (c, m)
    return best[1]


def half_cap(hb, ring, axis, dome, region, fixed=True, shape=None):
    """a quad-grid cap on a ring (loop order, its first vertex a grid corner): a Coons patch domed along axis, its
    winding the one whose boundary edges run against the ring's existing faces. Returns the grid's ids"""
    ring = [int(v) for v in ring]
    K = len(ring)
    s, t = shape if shape is not None else (K // 4, K // 4)
    loop = LF.grid_boundary(s, t)
    G = -np.ones((s + 1, t + 1), int)
    for k, (i, j) in enumerate(loop):
        G[i, j] = ring[k]
    V = half_V(hb)
    B = lambda i, j: V[G[i, j]]                                       # noqa: E731
    pts, cells = [], []
    for i in range(1, s):
        for j in range(1, t):
            u, v = i / s, j / t
            p = ((1 - v) * B(i, 0) + v * B(i, t) + (1 - u) * B(0, j) + u * B(s, j)
                 - ((1 - u) * (1 - v) * B(0, 0) + u * (1 - v) * B(s, 0) + (1 - u) * v * B(0, t) + u * v * B(s, t)))
            rho2 = ((2 * u - 1) ** 2 + (2 * v - 1) ** 2) / 2.0
            pts.append(p + unit(axis) * dome * (1 - rho2))
            cells.append((i, j))
    if pts:
        new = hb.add(np.array(pts), region, fixed=fixed)
        for (i, j), n in zip(cells, new):
            G[i, j] = n
    existing = set()
    rs = set(ring)
    for q in hb.Q:
        for a, b in zip(q, q[1:] + q[:1]):
            if a in rs and b in rs:
                existing.add((a, b))
    quads = [(G[i, j], G[i + 1, j], G[i + 1, j + 1], G[i, j + 1]) for i in range(s) for j in range(t)]
    clash = any((int(a), int(b)) in existing for q in quads for a, b in zip(q, q[1:] + q[:1]))
    for q in quads:
        hb.quad(*(q[::-1] if clash else q))
    return G


def rotate_to(loop, v0):
    """the loop started at vertex v0"""
    loop = list(loop)
    k = loop.index(int(v0))
    return np.array(loop[k:] + loop[:k])


def ports_half(hb, info, lay, body, field, cg, foot_fore, foot_hind, graft):
    """the half body's cut ports: the eye (crest on the clay, the edge on the ball, the tuck under it, a 4 x 4 socket
    cap: caudate's eye, fixed but the crest), the three gill sockets (two fillet rings each to a copy of the ramus's
    graft ring), the two limb blocks (a halfway ring to a copy of the footprint). graft: {r: the left graft ring (12, 3)};
    the copies are welded by position at the assembly. Returns a dict of loops and rings (half ids)"""
    from ..heads import caudate as CD
    R64 = info['R64']
    bl = lay['blocks']
    out, notes = {}, []

    def cells_of(name):
        (ia, ib), (ha, hb_) = bl[name]['rings'], bl[name]['cols']
        return [(R64[i][h], R64[i][h + 1], R64[i + 1][h + 1], R64[i + 1][h]) for i in range(ia, ib) for h in range(ha, hb_)]

    def corner(name):
        (ia, ib), (ha, hb_) = bl[name]['rings'], bl[name]['cols']
        return R64[ia][ha]

    # ---- the eye: the block's loop rounded toward the rim circle, crest / edge / tuck, the socket cap
    E = cg['eye']
    fe = CD.FEATURES['eye']
    Ec, ax_, u_, v_ = (np.asarray(E[k], np.float64) for k in ('E', 'axis', 'u', 'v'))
    r_e = float(E['r_e'])
    loop = rotate_to(half_cut(hb, cells_of('eye_L')), corner('eye_L'))
    V = half_V(hb)
    d = V[loop] - Ec
    ang = np.arctan2(d @ v_, d @ u_)
    rr = np.hypot(d @ u_, d @ v_)
    r_rim = fe['rim'] * r_e
    rim_new = Ec + (rr + 0.5 * (r_rim - rr))[:, None] * (np.cos(ang)[:, None] * u_ + np.sin(ang)[:, None] * v_) + \
        (d @ ax_)[:, None] * ax_
    Vall = half_V(hb)                                              # the loop is the grid's: moved, put back on the clay
    Vall[loop] = field.nearest(rim_new + 0.3 * ax_[None])
    hb.V, hb.R, hb.fx = [Vall], [np.concatenate(hb.R)], [np.concatenate(hb.fx)]
    # the crest, the edge and the tuck EVENLY spaced round the eye, the band out of the block's loop taking up the
    # change (check:ax4b, 10-29: on the loop's own angles their steps ran 15.3-34.5 deg, the edge's chords 0.52-1.17
    # mm; plan 5.5's "evenly spaced, so it never reads as a polygon", the octopus's t14 lesson: its lid rings,
    # octopus.py's eye ports)
    un = np.unwrap(ang)
    base_even = (1.0 if un[-1] > un[0] else -1.0) * TAU * np.arange(len(un)) / len(un)
    even = base_even + np.angle(np.exp(1j * (un - base_even)).mean())
    cdir = np.cos(even)[:, None] * u_ + np.sin(even)[:, None] * v_
    # the crest cast along the eye's axis at its designed radius (the nearest clay slid it to 0.16 mm from the edge
    # ring at the eye's top: a band of aspect 7.9)
    crest, okc = field.cast(Ec + EYE_CREST * r_e * cdir - 1.5 * ax_[None], np.tile(ax_, (len(cdir), 1)), 4.0)
    assert okc.all(), 'an eye crest cast missed'
    edge = Ec + fe['edge'] * r_e * cdir
    tuck = Ec + fe['tuck'] * r_e * cdir + fe['tuck_h'] * ax_[None]
    eids = half_extend(hb, loop, [crest, edge, tuck], 'eye', fixed=[False, True, True])
    G = half_cap(hb, eids[-1], -ax_, 0.6, 'eye', fixed=True)
    out['eye'] = dict(loop=loop, crest=eids[1], edge=eids[2], tuck=eids[3], cap=G.ravel())
    notes.append(f'the eye: the 4 x 4 block\'s loop (16) rounded halfway to the rim circle ({r_rim:.2f} mm), the crest '
                 f'on the clay at {EYE_CREST} r_e, the edge on the ball (r {fe["edge"] * r_e:.2f}), the tuck, a 4 x 4 '
                 f'socket cap (fixed)')
    # ---- the gill sockets: two fillet rings to each graft ring's copy
    for r in ('r1', 'r2', 'r3'):
        loop = half_cut(hb, cells_of(f'gill_{r}'))
        V = half_V(hb)
        Pg = np.asarray(graft[int(r[1])], np.float64)
        m = match_ring(V[loop], Pg)
        Pt = Pg[m]
        rings = [field.nearest((1 - t) * V[loop] + t * Pt) for t in (1 / 3, 2 / 3)] + [Pt]
        ids = half_extend(hb, loop, rings, 'socket', fixed=[False, False, True])
        out[f'gill_{r[1]}'] = dict(loop=loop, fillet_0=ids[1], fillet_1=ids[2], copy=ids[3], match=m)
        span = float(np.linalg.norm(V[loop] - Pt, axis=1).mean())
        notes.append(f'gill {r}: the 3 x 3 socket\'s loop (12) bridged to its graft ring by two fillet rings (the mean '
                     f'span {span:.2f} mm)')
    # ---- the limb blocks: a halfway ring to each footprint's copy
    for nm, foot in (('fore', foot_fore), ('hind', foot_hind)):
        loop = half_cut(hb, cells_of(f'{nm}_L'))
        V = half_V(hb)
        m = match_ring(V[loop], foot)
        Pt = foot[m]
        half = field.nearest(0.5 * (V[loop] + Pt))
        ids = half_extend(hb, loop, [half, Pt], 'port', fixed=[False, True])
        out[f'limb_{nm}'] = dict(loop=loop, half=ids[1], copy=ids[2], match=m)
        notes.append(f'the {nm}limb block: the 3 x 5 block\'s loop (16), a halfway ring, the footprint ring (the mean '
                     f'span {float(np.linalg.norm(V[loop] - Pt, axis=1).mean()):.2f} mm)')
    out['notes'] = notes
    return out


def full_from(V, Q, R, fx):
    """a Half holding the full mesh, for its surgery"""
    fb = Half()
    fb.V, fb.R, fb.fx, fb.Q = [np.asarray(V, np.float64)], [np.asarray(R)], [np.asarray(fx, bool)], \
        [tuple(int(v) for v in q) for q in Q]
    return fb


def mouth(fb, info, lay, mir):
    """the MOUTH on the full body: the strip between the upper lip's column (h_mouth) and the lower lip's (+1) from
    the snout cap's row across the front to the commissure's ring, both halves, cut: the lip loop (2 (i_c + hx) quads
    long, so 4 (i_c + hx) + 2 vertices: the upper lip, one edge at each corner, the lower lip); the bag's rings inside
    it (the inner lip, the gum, three bag rings: MOUTH) and a strip closing the last (the oropharynx); the lips fixed.
    Returns ids and the sharp edges (the upper lip's last third before each corner)"""
    L_ = LAY
    R64, C = info['R64'], info['C']
    hm, hx = L_['h_mouth'], L_['hx']
    bm = hm - hx
    cells = []
    for i in range(lay['i_c']):
        q = (R64[i][hm], R64[i][hm + 1], R64[i + 1][hm + 1], R64[i + 1][hm])
        cells += [q, tuple(int(mir[v]) for v in q)]
    for a in range(hx):
        q = (C[a, bm], C[a, bm + 1], C[a + 1, bm + 1], C[a + 1, bm])
        cells += [q, tuple(int(mir[v]) for v in q)]
    loop = half_cut(fb, cells)
    K = len(loop)
    V = half_V(fb)
    # the loop from the left corner's upper vertex: the upper lip first (the loop's own direction), then the lower
    c_up = int(R64[lay['i_c']][hm])
    up = set(int(R64[i][hm]) for i in range(lay['i_c'] + 1)) | set(int(C[a, bm]) for a in range(hx + 1))
    up |= set(int(mir[v]) for v in list(up))
    loop = rotate_to(loop, c_up)
    if int(loop[1]) not in up:                    # the loop runs down the corner first: start at the other corner
        loop = rotate_to(loop, int(mir[c_up]))
    assert int(loop[1]) in up, 'the lip loop does not run along the upper lip from its corner'
    is_up = np.array([int(v) in up for v in loop])
    P = V[loop]
    n_up = int(is_up.sum())
    assert is_up[:n_up].all() and not is_up[n_up:].any(), 'the lip loop\'s upper run is not its first n_up vertices'
    # AX10, 11-02: THE BAG FROM THE SLIT. Upper vertex k pairs with lower K - 1 - k (the same ring of the loft, or the
    # same cap column); both walls of ring j share one horizontal point: the pair's deeper lip along the slit's own
    # inward normal (the pairs' midline curve's normal in the horizontal plane, toward one point 6 mm behind: aimed at
    # the head's inside), dep_j further in, evened along the run (the corners keep theirs), at the pair's mid height
    # plus / minus half_j = lip_gap / 2 + open_j (at least half_min). Built from each lip on its own (AX7b-AX8), the
    # corner's fold (the upper lip's lobe hanging 2.8 mm out of and below the lower lip: caudate fold_weight) put the
    # upper wall's first rings outside the lower lip and the walls crossed (AX4 gate 10's mouth, bag quads 2 x 0.4 mm)
    assert K == 2 * n_up, 'the lip loop\'s runs differ in length'
    iu = np.arange(n_up)
    il = K - 1 - iu
    Pu, Pl = P[iu], P[il]
    Mid = 0.5 * (Pu + Pl)
    tg = np.gradient(Mid, axis=0)
    tg[:, 1] = 0.0
    dm = unit(np.cross(tg, [0.0, 1.0, 0.0]))
    ref = np.column_stack([np.zeros(n_up), Mid[:, 1], Mid[:, 2] - 6.0]) - Mid
    ref[:, 1] = 0.0
    dm = np.where(((dm * ref).sum(1) < 0)[:, None], -dm, dm)
    Bs = np.where(((Pu * dm).sum(1) >= (Pl * dm).sum(1))[:, None], Pu, Pl)
    Bs[:, 1] = Mid[:, 1]
    # (half_min: each ring's two walls meet in one corner edge 2 half long; at the inner lips' 0.03 the corner quads were
    # 0.06 x 0.8 mm)
    half = np.maximum(0.5 * LAY['lip_gap'] + np.asarray(MOUTH['open'], np.float64), MOUTH['half_min'])
    rings = []
    for j, dep in enumerate(MOUTH['depth']):
        Cm = Bs + dep * dm
        for _ in range(int(round(MOUTH['even'] * dep))):
            Cm[1:-1] = 0.5 * Cm[1:-1] + 0.25 * (Cm[:-2] + Cm[2:])
        Pm = np.zeros((K, 3))
        Pm[iu] = Cm + np.array([0.0, half[j], 0.0])
        Pm[il] = Cm - np.array([0.0, half[j], 0.0])
        rings.append(Pm)
    ids = half_extend(fb, loop, rings, 'mouth', fixed=True)
    fxa = np.concatenate(fb.fx)                    # the lips themselves designed on the clay's mouth line: fixed (the
    fxa[loop] = True                               # fit projected the tucked lower lip onto the upper: folds)
    fb.fx = [fxa]
    # the closing strip: the last ring's upper run (from the corner) against its lower run
    s_ = K // 2 - 1
    half_cap(fb, ids[-1], np.array([0.0, 0.0, -1.0]), 0.0, 'mouth', fixed=True, shape=(1, s_))
    sharp = {}
    up_run = [int(v) for v in loop if int(v) in up]
    n_s = max(1, int(round(MOUTH['sharp_share'] * lay['i_c'])))
    for run in (up_run[:n_s + 1], up_run[-(n_s + 1):]):
        for a, b in zip(run[:-1], run[1:]):
            sharp[(min(a, b), max(a, b))] = MOUTH['sharp']
    note = (f'the mouth: the lip loop {K} vertices ({int(is_up.sum())} on the upper lip), {len(MOUTH["depth"])} bag '
            f'rings and a 1 x {s_} closing strip, all designed (fixed); the upper lip creased {MOUTH["sharp"]} over '
            f'{n_s} edges before each corner')
    return dict(loop=loop, rings=ids[1:], sharp=sharp, is_up=is_up, note=note)


def compact(fb):
    """drop the vertices no quad uses (the cut blocks' interiors); returns the old -> new index map (-1 dropped)"""
    V = half_V(fb)
    R, fx = np.concatenate(fb.R), np.concatenate(fb.fx)
    Q = np.array(fb.Q, np.int64)
    used = np.zeros(len(V), bool)
    used[Q.ravel()] = True
    remap = -np.ones(len(V), int)
    remap[used] = np.arange(int(used.sum()))
    fb.V, fb.R, fb.fx = [V[used]], [R[used]], [fx[used]]
    fb.Q = [tuple(int(remap[v]) for v in q) for q in Q]
    return remap


def mirror_pairs(V, tol=1e-6):
    """each vertex's mirror partner by position (x -> -x), -1 where none (the midline: itself)"""
    from scipy.spatial import cKDTree
    t = cKDTree(V)
    d, j = t.query(V * MIRROR)
    return np.where(d < tol, j, -1)


def block_loop(cells, start):
    """the boundary loop of a set of quads (vertex 4-tuples, the mesh's winding), from vertex `start`, the way the
    quads run along it"""
    dirs = set()
    for q in cells:
        for k in range(4):
            dirs.add((int(q[k]), int(q[(k + 1) % 4])))
    nxt = {}
    for a, b in dirs:
        if (b, a) not in dirs:
            assert a not in nxt, 'the block\'s boundary touches itself'
            nxt[a] = b
    loop = [int(start)]
    while True:
        b = nxt[loop[-1]]
        if b == loop[0]:
            break
        loop.append(b)
    assert len(loop) == len(nxt), 'the block\'s boundary is not one loop'
    return np.array(loop)


# ============================================================================================ the fit
def fit(V, Q, R, fx, prg, km, body, cap_up, log=print, keep=None):
    """the body cage on the clay (prg in x4 metres): sprawl_cage.fit_cage (the fixed vertices held), an even relaxation
    where the designed spacing does not hold on the clay (cap_up: the snout cap above the mouth; the gill region; rings
    0-1), then symmetric again; keep: vertices left out of that relaxation (AX10: ring 0's band, placed evenly on the
    clay's own section already: relaxed, it slid 0.4 mm back past ring 1 and twisted the quads between). Returns (V life
    mm, a note)"""
    from . import sprawl_cage as SC
    from .. import retopo as RT
    pairs = mirror_pairs(V, tol=1e-4)
    cx4 = QuadMesh(V * km, Q)
    st_, acc, first = SC.fit_cage(cx4, prg, fx, km)
    s_v = body.s_of(V[:, 2])
    even_ = cap_up | ((s_v > 0.160) & (s_v < 0.205) & (R != BREGIONS.index('mouth'))) | \
        ((s_v < 0.0125) & (R == BREGIONS.index('head')))
    if keep is not None:
        even_ &= ~keep
    st2, acc2 = RT.fit(cx4, prg, iters=8, relax=0.5, pinned=~even_, fixed=fx, maxd=2.0 * km, preserve=False)
    Vf = cx4.V / km
    Vf[fx] = V[fx]                       # bit for bit (x km / km is not: the tail records came back 1.8e-15 mm off)
    left = (V[:, 0] > 1e-9) & (pairs >= 0) & ~fx
    Vf[pairs[left]] = Vf[left] * MIRROR
    midl = (np.abs(V[:, 0]) <= 1e-9) & ~fx
    Vf[midl, 0] = 0.0
    mv = np.linalg.norm(Vf - V, axis=1)
    note = (f'the fit: sprawl_cage.fit_cage accepted {[round(a, 2) for a in acc]} (the first projection {first:.3f} mm), '
            f'the even relaxation ({int((even_ & ~fx).sum())} vertices) accepted {[round(a, 2) for a in acc2]}; moves p50 '
            f'{np.median(mv):.3f} p99 {np.percentile(mv, 99):.3f} max {mv.max():.3f} mm; unpaired free vertices off the '
            f'midline {int(((np.abs(V[:, 0]) > 1e-9) & (pairs < 0) & ~fx).sum())}')
    return Vf, note


# ============================================================================================ the fins and the eyes
def fin_columns(spec, body, field, ss, kind):
    """the fin's root (buried) and margin heights at stations ss: (y_root, y_margin, z, h, the core's mid-height)
    arrays (the module docstring)"""
    from ..species import axolotl_fins as AF
    ss = np.atleast_1d(np.asarray(ss, np.float64))
    hh = np.array([AF.heights(spec, body, s)[0 if kind == 'dorsal' else 1] for s in ss])
    tb = np.array([body.top_bot(min(s, 0.9995)) for s in ss])
    z = np.array([float(body.z(s)) for s in ss])
    O = np.column_stack([np.zeros(len(ss)), tb.mean(1), z])
    up, okt = field.cast(O, np.tile([0.0, 1.0, 0.0], (len(ss), 1)), 40.0)
    dn, okb = field.cast(O, np.tile([0.0, -1.0, 0.0], (len(ss), 1)), 40.0)
    top = np.where(okt, up[:, 1], tb.mean(1))              # past the clay's tip: the analytic mid-height
    bot = np.where(okb, dn[:, 1], tb.mean(1))
    mid = 0.5 * (top + bot)
    bury = np.maximum(FIN['bury_min'], FIN['bury_k'] * hh) + FIN['lift']
    if kind == 'dorsal':
        return np.maximum(top - bury, mid), top + hh, z, hh, mid
    return np.minimum(bot + bury, mid), bot - hh, z, hh, mid


def low_cast(V, T, lo, hi, O, D):
    """the nearest hit (t > 0) of the axis-aligned ray O + t D on the triangles V[T] (lo / hi: their boxes), inf if
    none (check:ax4b: the fin roots measured on the body's low)"""
    O, D = np.asarray(O, np.float64), np.asarray(D, np.float64)
    ax = int(np.argmax(np.abs(D)))
    m = np.ones(len(T), bool)
    for k in range(3):
        if k != ax:
            m &= (lo[:, k] <= O[k]) & (hi[:, k] >= O[k])
    if not m.any():
        return np.inf
    P = V[T[m]]
    a, e1, e2 = P[:, 0], P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    h = np.cross(D, e2)
    det = (e1 * h).sum(1)
    ok = np.abs(det) > 1e-14
    f = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = O - a
    u = f * (s * h).sum(1)
    q = np.cross(s, e1)
    v = f * (q * D).sum(1)
    t = f * (e2 * q).sum(1)
    hit = ok & (u >= 0.0) & (v >= 0.0) & (u + v <= 1.0) & (t > 1e-9)
    return float(t[hit].min()) if hit.any() else np.inf


def fins(spec, body, field, segments, rec, low=None):
    """each fin segment a two-face membrane (the module docstring). field: the body's clay; low: the fitted body
    cage (V, Q, life mm), the roots buried under it (check:ax4b). Returns dict(V, Q, sharp (the rims), segs: per
    segment its name, fin, stations, rows, columns, vertex and quad ranges, root ids)"""
    TL = spec['a1']['TL']
    th0, th1 = spec['fins']['half_thickness']
    s_tr, s_tm = rec['tail_root']['station'], rec['tail_mid']['station']
    V, Q, sharp, segs = [], [], {}, []
    nv = 0
    if low is not None:
        Vlow = np.asarray(low[0], np.float64)
        Tlow = QuadMesh(Vlow, low[1]).tris()                  # the exporter's split: the triangles the engine draws
        lo_t, hi_t = Vlow[Tlow].min(1), Vlow[Tlow].max(1)
    for seg in segments:
        kind, s_a, s_b = seg['fin'], float(seg['s'][0]), min(float(seg['s'][1]), FIN['s_end'])
        tall = s_a >= s_tr - 1e-9 and s_b <= s_tm + 1e-9
        rows = FIN['rows_tall'] if tall else FIN['rows']
        # the columns: about every FIN['step'] mm, at most FIN['aspect'] rows' heights apart where the fin is low
        sx = np.linspace(s_a, s_b, 97)
        yr, ym, _, _, _ = fin_columns(spec, body, field, sx, kind)
        step = np.clip(FIN['aspect'] * np.abs(ym - yr) / rows, FIN['step_min'], FIN['step'])
        g = TL / step
        G = np.concatenate([[0.0], np.cumsum(0.5 * (g[1:] + g[:-1]) * np.diff(sx))])
        n = max(1, int(round(G[-1])))
        ss = np.interp(np.linspace(0.0, G[-1], n + 1), G, sx)
        ss[0], ss[-1] = s_a, s_b
        yr, ym, z, hh, mid = fin_columns(spec, body, field, ss, kind)
        # the root's half-thickness at most root_share of the core's half-width at the root's height, the margin's never
        # thicker than the root's (the tail's core narrows under 1 mm from s 0.935: a 0.5 mm root stood out of its
        # sides there, 0.30 mm at s 0.984); past the clay's tip t_floor
        Px, okx = field.cast(np.column_stack([np.zeros(len(ss)), yr, z]), np.tile([1.0, 0.0, 0.0], (len(ss), 1)), 10.0)
        tr = np.where(okx, np.minimum(FIN['root_share'] * Px[:, 0], th0), FIN['t_floor'])
        if low is not None:
            # the root under the body's LOW (check:ax4b, 10-29): plan 5.6 buries the root edge under the low, the cage
            # the engine draws; the K 16 / K 8 tail's chords cut well inside the clay's dorsal / ventral ridge, so on
            # the clay's width and depth alone the roots from s 0.74 on sat 0.0-0.2 mm under the low and past its
            # sides at s 0.927-0.935. So the half-thickness is at most root_share of the LOW's half-width at the
            # root's height, and the root edge at least the bury depth under the low's surface above (below) it,
            # never past the core's mid-depth; past the body's tip (no low) the clay's rule stands
            sg = 1.0 if kind == 'dorsal' else -1.0
            bury = np.maximum(FIN['bury_min'], FIN['bury_k'] * hh) + FIN['lift']
            for c in range(len(ss)):
                w = low_cast(Vlow, Tlow, lo_t, hi_t, (0.0, yr[c], z[c]), (1.0, 0.0, 0.0))
                if not np.isfinite(w):
                    continue
                tr[c] = min(tr[c], FIN['root_share'] * w)
                up = low_cast(Vlow, Tlow, lo_t, hi_t, (tr[c], yr[c], z[c]), (0.0, sg, 0.0))
                if np.isfinite(up) and up < bury[c]:
                    y_new = yr[c] - sg * (bury[c] - up)
                    yr[c] = max(y_new, mid[c]) if sg > 0 else min(y_new, mid[c])
        f = np.arange(rows + 1) / rows
        stride = 2 * rows + 1                        # per column: the left face's rows, the rim, the right face's rows
        # the half-thickness sampled on the 3-row profile (its rows' thickness, 0 at the rim), so a 6-row column's own
        # rows lie on the 3-row neighbour's edges at a shared cut line (check:ax4b, 10-29: on its own linear profile
        # the 6-row top row stood 0.06 mm proud of the 3-row band to the rim at the tail root and the tail mid)
        f3 = np.arange(FIN['rows'] + 1) / FIN['rows']
        P = []
        for c in range(len(ss)):
            y = yr[c] + (ym[c] - yr[c]) * f
            t3 = tr[c] + (min(th1, tr[c]) - tr[c]) * f3
            t3[-1] = 0.0
            t = np.interp(f, f3, t3)
            P += [(t[r], y[r], z[c]) for r in range(rows)] + [(0.0, y[rows], z[c])] + \
                [(-t[r], y[r], z[c]) for r in range(rows)]
        P = np.array(P)
        L = lambda c, r: nv + c * stride + r                                              # noqa: E731
        Rv = lambda c, r: nv + c * stride + (rows if r == rows else rows + 1 + r)         # noqa: E731
        qL = [(L(c, r), L(c + 1, r), L(c + 1, r + 1), L(c, r + 1)) for c in range(len(ss) - 1) for r in range(rows)]
        qR = [(Rv(c, r), Rv(c, r + 1), Rv(c + 1, r + 1), Rv(c + 1, r)) for c in range(len(ss) - 1) for r in range(rows)]
        a, b_, d_ = (P[qL[0][k] - nv] for k in (0, 1, 3))
        if np.cross(b_ - a, d_ - a)[0] < 0:                  # the left face's normal +x (the ventral fin runs down)
            qL, qR = [q[::-1] for q in qL], [q[::-1] for q in qR]
        q0 = len(Q)
        Q += qL + qR
        for c in range(len(ss) - 1):
            sharp[(L(c, rows), L(c + 1, rows))] = FIN['crease']
        segs.append(dict(name=seg['name'], fin=kind, owner=seg['owner'], s=(s_a, s_b), rows=rows, cols=len(ss),
                         v=(nv, nv + len(P)), q=(q0, len(Q)), root=np.array([[L(c, 0), Rv(c, 0)] for c in range(len(ss))]),
                         rim=np.array([L(c, rows) for c in range(len(ss))]), h_max=float(hh.max())))
        V.append(P)
        nv += len(P)
    return dict(V=np.vstack(V), Q=np.array(Q, np.int64), sharp=sharp, segs=segs)


def eyeballs(cg, n=6, levels=3):
    """the two eyeballs: six n x n grids on a cube projected onto the sphere (octopus_eye.eye_mesh's ball), the front
    face on the eye's axis, at caudate's ball centre and radius; scaled so the limit surface (Catmull-Clark, `levels`)
    lies on the ball. Returns dict(V, Q (left then right), n_side, scale)"""
    from .. import subdiv_sharp as SS
    E = cg['eye']
    c, r_b, out = np.asarray(E['centre'], np.float64), float(E['r_ball']), unit(E['axis'])
    h = unit(np.cross([0.0, 1.0, 0.0], out))
    u = np.cross(out, h)
    t = np.linspace(-1.0, 1.0, n + 1)
    faces = [((0, 0, 1.0), (1.0, 0, 0), (0, 1.0, 0)), ((0, 0, -1.0), (-1.0, 0, 0), (0, 1.0, 0)),
             ((1.0, 0, 0), (0, 0, -1.0), (0, 1.0, 0)), ((-1.0, 0, 0), (0, 0, 1.0), (0, 1.0, 0)),
             ((0, 1.0, 0), (1.0, 0, 0), (0, 0, -1.0)), ((0, -1.0, 0), (1.0, 0, 0), (0, 0, 1.0))]
    Vl, Q = [], []
    for c0, a, b in faces:
        c0, a, b = np.array(c0), np.array(a), np.array(b)
        base = len(Vl)
        for j in range(n + 1):
            for i in range(n + 1):
                p = c0 + a * t[i] + b * t[j]
                Vl.append(p / np.linalg.norm(p))
        for j in range(n):
            for i in range(n):
                k = base + j * (n + 1) + i
                Q.append([k, k + 1, k + n + 2, k + n + 1])
    Vl, Q = np.array(Vl), np.array(Q)
    key = np.round(Vl * 1e6).astype(np.int64)                 # weld the cube's shared edges
    _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    Vl, Q = Vl[idx], inv.reshape(-1)[Q]
    lim = SS.subdivide(QuadMesh(Vl, Q), {}, levels)[0]
    k = 1.0 / float(np.linalg.norm(lim.V, axis=1).mean())
    VL = c + r_b * k * (Vl @ np.column_stack([h, u, out]).T)
    return dict(V=np.vstack([VL, VL * MIRROR]), Q=np.vstack([Q, Q[:, ::-1] + len(VL)]), n_side=len(VL), scale=k,
                centre=c, r_ball=r_b)


# ============================================================================================ the build
def build(spec, body, field, bfield, prg, km, rec, ports, cg, foot_fore, foot_hind, graft, fin_segments, log=print):
    """the body cage, its ports and records, fitted; the fins and the eyes. body: caudate.Body; field / bfield: the
    clay with the limbs and rami / the body's alone (sprawl_cage.Field, life mm); prg: the clay's program (x4 metres);
    rec / ports / fin_segments: seams.json's; foot_fore / foot_hind: the left footprint rings, graft: {r: the left graft
    ring} (life mm). Returns a dict (life mm; ids into V)"""
    notes = []
    lay = layout(spec, body, rec, ports, cg, foot_fore, foot_hind)
    hb, info = assemble(spec, body, bfield, rec, cg, lay)
    pt = ports_half(hb, info, lay, body, field, cg, foot_fore, foot_hind, graft)
    notes += lay['notes'] + info['notes'] + pt.pop('notes')
    recs = record_rings(rec, info, lay)
    V, Q, R, fx, mir = mirror(hb, [(r_['ids'], r_['right']) for r_ in recs.values()])
    fb = full_from(V, Q, R, fx)
    mo = mouth(fb, info, lay, mir)
    notes.append(mo['note'])
    remap = compact(fb)
    V, R, fx = half_V(fb), np.concatenate(fb.R), np.concatenate(fb.fx)
    Q = np.array(fb.Q, np.int64)
    L_ = lambda ids: remap[np.asarray(ids)]                                  # noqa: E731
    R_ = lambda ids: remap[mir[np.asarray(ids)]]                             # noqa: E731
    # ---- the records in their own vertex order
    rings = {}
    for name, r_ in recs.items():
        ring = -np.ones(r_['K'], int)
        ring[r_['kl']] = L_(r_['ids'])
        ring[r_['kr']] = R_(r_['ids'])
        assert (ring >= 0).all()
        rings[name] = ring
    # ---- the ports (both sides), the copies to weld, the graft sites
    out_ports, copies = {}, {}
    for name, d in pt.items():
        for side, f in (('L', L_), ('R', R_)):
            nm = f'{name}_{side}'
            out_ports[nm] = {k: f(v) for k, v in d.items() if k != 'match'}
            if 'copy' in d:
                copies[nm] = dict(ids=f(d['copy']), match=d['match'])
    R64 = info['R64']
    qset = {frozenset(q) for q in Q.tolist()}
    for name in GRAFT:
        (ia, ib), (ha, hb_) = lay['blocks'][name]['rings'], lay['blocks'][name]['cols']
        cells = [(R64[i][h], R64[i][h + 1], R64[i + 1][h + 1], R64[i + 1][h]) for i in range(ia, ib) for h in range(ha, hb_)]
        cL = [tuple(int(v) for v in L_(c)) for c in cells]
        cR = [tuple(int(v) for v in R_(c)[::-1]) for c in cells]
        assert all(frozenset(c) in qset for c in cL + cR), f'{name}: a block cell is not a quad of the cage'
        if ha == 0:                                    # on the midline: one block across it
            out_ports[name] = dict(loop=block_loop(cL + cR, L_([R64[ia][0]])[0]), cells=np.array(cL + cR))
        else:
            out_ports[name] = dict(loop=block_loop(cL, L_([R64[ia][ha]])[0]), cells=np.array(cL))
            out_ports[name[:-2] + '_R'] = dict(loop=block_loop(cR, R_([R64[ia][ha]])[0]), cells=np.array(cR))
    # ---- the sharp edges: the lips' corners (the mouth's), the gular loop (the gill ring nearest caudate's gill base,
    # its ventral edges below r3's socket)
    sharp = {(int(remap[a]), int(remap[b])): s for (a, b), s in mo['sharp'].items()}
    ig0, ig1 = lay['ig']
    i_g = ig0 + int(np.argmin(np.abs(lay['k64'][ig0:ig1 + 1] - spec['stations']['gill_base'])))
    h0 = LAY['gill_cols']['r3'] + 3
    gular = []
    for h in range(h0, 32):
        a, b = R64[i_g][h], R64[i_g][h + 1]
        for f in (L_, R_):
            e = (int(f([a])[0]), int(f([b])[0]))
            sharp[(min(e), max(e))] = GULAR
            gular.append((min(e), max(e)))
    notes.append(f'the gular loop: ring s {lay["k64"][i_g]:.4f} (caudate\'s gill base {spec["stations"]["gill_base"]}), '
                 f'its edges from column {h0} to the ventral midline, {len(gular)} edges creased {GULAR}')
    # ---- the fit
    cap_up = np.zeros(len(V), bool)
    C = info['C']
    for a in range(C.shape[0]):
        for b in range(LAY['h_mouth'] - LAY['hx']):
            for f in (L_, R_):
                v = int(f([C[a, b]])[0])
                if v >= 0:
                    cap_up[v] = True
    V0 = V.copy()
    keep = None
    if LAY.get('clay_band'):
        # AX10: ring 0's band stays where band_contour put it (fit's keep)
        keep = np.zeros(len(V), bool)
        b_ = LAY['clay_band']
        for h in range(LAY['h_mouth'] + b_[0], LAY['h_mouth'] + b_[1] + 1):
            for f in (L_, R_):
                v = int(f([R64[0][h]])[0])
                if v >= 0:
                    keep[v] = True
    V, fnote = fit(V0, Q, R, fx, prg, km, body, cap_up, keep=keep)
    notes.append(fnote)
    fn = fins(spec, body, bfield, fin_segments, rec, low=(V, Q))
    ey = eyeballs(cg)
    notes.append(f'the fins: {len(fn["segs"])} membranes, {len(fn["Q"])} quads (rows ' +
                 ', '.join(f'{s["name"]} {s["rows"]} x {s["cols"] - 1}' for s in fn['segs']) + '); the eyes: two '
                 f'cube-sphere balls of {len(ey["Q"]) // 2} quads, scaled {ey["scale"]:.4f} so their limit lies on the '
                 f'ball (r {ey["r_ball"]:.3f} mm)')
    return dict(V=V, V_unfit=V0, Q=Q, R=R, fixed=fx, regions=BREGIONS, rings=rings, ports=out_ports, copies=copies,
                sharp=sharp, gular=gular, mouth=dict(loop=remap[mo['loop']], rings=[remap[r] for r in mo['rings']]),
                fins=fn, eyes=ey, lay=lay, info=info, notes=notes, poles_red=info['poles_red'])
