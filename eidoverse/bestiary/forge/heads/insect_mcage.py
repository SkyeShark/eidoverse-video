"""B3g (the lead's call 2, 10-27): the stag beetle's MANDIBLE as ONE creased subdivision cage (forge/subdiv_sharp.py), the way
the head is built (heads/insect_cage.py): B3c-B3f built it as a convex arm sweep, round cones for the teeth, the tine and
the hook, a round-cone keel and a fork blade, intersected with two prisms: from below the hook, the tine and the keel read
as separate stuck-on pieces (beetle/scratch_b3fcheck/k08 tiles 9-11).

THE CAGE (left mandible, the closed pose's frame, then the pose's turn about the hinge; B3h m7: VERSION's note supersedes the
TEETH paragraph below: even stations, the inner edge's features (KNOBS, the large tooth's FINGER, the TINE) re-laid on M1d):
  ARM    a TUBE of rings along the arm at MCAGE stations (u along the chord, 0 the outer base, 1 the tip), each ring 16 points
         on the arm's measured section: insect.lens_section's rolled lens (its OUTER, TOP, INNER and BOTTOM extremes among
         them) scaled by the B3f solve's width and depth at that u and set in its frame (insect.mandible_geometry: the
         lens's extreme points on M1d's outer edge and inner envelope and on M1l's dorsal edge and lower line). In the side
         view every ring point within M1l's lines at its own z, each ring's highest point on the dorsal line and its lowest
         on the lower line: the base's on the ventral line (the KEEL is the arm's own underside: landmarks.mand_base_vent),
         the distal rings' on the FORK EDGE (the blade is the arm's own lower half to the tip). Both ends capped.
  TEETH  EXTRUSIONS of the arm's inner-edge faces (the ring's three points round the inner extreme, between two stations
         at the tooth's base): the basal tooth (u 0.483), the LARGE tooth (0.599) and the fork's TINE (0.737) along M1d's
         outline (mandible_geometry's levels: the outline's midline and half-width per protrusion level), the tine falling
         to M1l's fork bottom and HOOKING back (M1l's contour: its rear at z 10.58, its bottom 4.31-4.33 over z 10.98-11.5,
         BEETLE_BODY_PHOTOS 7c); the small denticles (u 0.403, 0.685, 0.995) are not built (MCAGE teeth). The tine's distal
         side meets the blade's underside at the fork's bottom: one continuous crotch (M3v), the tine merging broadly into
         the arm (M1d).
The limit mesh's exact distance (insect_cage.mesh_sdf) on a grid round the posed mandible is its GRID member; the arm alone
(the tube without the teeth) is a second grid for b03's section gate (the arm's own convexity).
"""
import hashlib
import json
import os
import time

import numpy as np

from ..mesh import QuadMesh
from .. import subdiv_sharp as SS

VERSION = 'b3h-m7o'              # m7o (the beetle's B5, 10-29): the limit no longer crosses itself on the inner teeth or at the
#                                  tip (b5_cage c01 / c03): the KNOBS' rings in their base patch's own plane (MCAGE knob_frame;
#                                  over the comb the inner face leans 45-53 deg, so vertical rings folded a wall under on every
#                                  knob) and ~10 % narrower (knob_shape); the side view's clip eased out over the tip's last
#                                  stations (tip_clip) and its bow capped by the ring's depth (bow_depth). Only the base cap,
#                                  inside the head (1.5 mm under its surface), still crosses (its dorsal bound's dive)
#                                  m7n (the B3h checker, 10-27): the base's 'p' pushes at u 0.20 / 0.25 a GAUSSIAN along the arm
#                                  (MCAGE push_sigma 0.025 u): on single stations (1, 0.5, 0.5) station 19 sat half-pushed between
#                                  full ones, two dents on the arm's inner face at u 0.20 / 0.25 and a step in its inner outline
#                                  (beetle/scratch_b3hcheck x07: the inner half's second difference along the arm, rms 2.77 um over
#                                  u 0.17-0.29, spikes 6.0 / 3.6 / 4.0 at u 0.200 / 0.224 / 0.248 -> 1.14, max 2.38; the rest of
#                                  the arm 1.0). (m7m, withdrawn: the same + the dorsal clip C1; it did not remove the crease at u
#                                  0.355, which is the lens depth's kink, mandible_geometry's linear depth at the dorsal table's
#                                  z 6.0 vertex, and only moved which stations b03's binary section contour flags)
#                                  m7l (b03 _b3h: the sections failed at u 0.10 / 0.20 / 0.30 / 0.80, flat runs 0.34 / 0.52 / 0.40
#                                  / 0.30, a concavity 0.026 at u 0.10): the outward pushes at u 0.20 / 0.25 PROPORTIONAL (the
#                                  inner half scaled across, not flattened by a sine weight; u 0.20's run 0.52 -> 0.35), the
#                                  keel's crease ending at u 0.09 (0.11: the section at u 0.10 sat on its end). (m7k's flanks
#                                  bulged 0.04 lengthened the runs at u 0.40 / 0.60 / 0.80 to 0.30 / 0.80 / 0.38: back to 0.03)
#                                  m7g-j: the large tooth's and the tine's widths re-traced on M1d at 45 px/mm (h17, both sides):
#                                  the large tooth a broad tooth (1.49 mm at x 3.0 to a rounded point), the tine 0.36-0.84 mm
#                                  (MCAGE finger_large / tine_path); m7's by-eye 120 px/mm widths were half the teeth; both on
#                                  round (superellipse) sections; the tine's first ring further out (0.18) in the base's frame
#                                  m7f: the inner patch's points a feature's faces replaced (no quad uses them) had free
#                                  controls (fitted to -95 mm) that stretched the GRID's box to 13.8 x 36.4 x 29.4 mm (b03
#                                  _b3h1 ran out of memory): pinned to their targets in limit(), the box from the faces' vertices
#                                  m7 (the lead's B3h call 4): the stations EVEN (n_st over u_range, 0.27 mm apart) and the side
#                                  view's snaps smoothed along them (b3g's stations 0.016 apart at u 0.083 / 0.099 snapped to
#                                  different points of M1l's lower line: the base's seam ring, the B3g check c02); the inner
#                                  edge's FEATURES re-laid on M1d: the large tooth and the tine FINGERS (round sections, the widths
#                                  traced on M1d at 120 px/mm, h12: near-parallel sides, rounded tips; b3g's flat 6-point flaps
#                                  tapered to 0.08 mm points), their bases where M1d's traced contour rises (the large tooth's at u
#                                  0.509-0.601, b3g's 0.562-0.636 and its push at 0.511 filled the notch b03's width envelope reads
#                                  at u 0.50: the +0.185 at u 0.55), the tine's base flared broad (no crevice); the denticles small
#                                  rounded KNOBS on single faces (the comb of four between the large tooth and the tine, one beside
#                                  the large tooth's distal side, the broad basal knob and the denticle at u 0.408); the flanks
#                                  bulged (flank_bulge: the section gate's flat runs)
#                                  m6: the base's dorsal bound dives under the dish (base_dive). m4: the bound bowed (line_bow),
#                                  u 0.722 on the fork edge (partly), the keel's crease, the inner pushes (w_add). (A trial m5,
#                                  the pushes moved to u 0.455 and the bow 0.045, failed the tip landmark +0.37 and u 0.50
#                                  -0.176: reverted to m4's values.)
#                                  m3: 16-point rings; the side view on M1l's lines ring point by ring point; a station on the
#                                  base's ventral corner; no denticle bumps; the basal tooth's base broad (b03 _b3g's gates).
#                                  m2: narrower large-tooth and tine bases, the teeth tilted with M1l's lower line
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
CACHE = os.path.join(REPO, 'work', 'bestiary', 'beetle', 'cache_hull')

MCAGE = dict(
    n_st=69, u_range=(-0.06, 0.985),                     # m7: EVEN stations (0.0154 of the chord, 0.27 mm)
    snap_smooth=1.5,                                     # the side view's snap displacements smoothed along the stations
    #                                                      (gaussian, stations): no ring snapped apart from its neighbours
    flank_bulge=0.030,                                   # mm: each ring's flank points pushed out along their normals by this
    #                                                      x sin(pi t) between the lens's extremes (t 0 .. 1): the lens flanks'
    #                                                      arcs (radius ~2.2 mm) are flat within 0.004 over ~0.27 mm, the
    #                                                      section gate's 0.30 (b03 _b3gchk2: 0.303 at u 0.10 / 0.50)
    ring_split=(3, 3, 3, 3),                             # ring points between outer->top, top->inner, inner->bottom,
    #                                                      bottom->outer (m1's 1/2/1/2 and m2's 2/3/2/3 left the lens flanks
    #                                                      flat between them: the sections gate's 0.30-0.35 mm runs)
    # the inner edge's FEATURES on M1d (the photo strand's traced inner contour against the SPEC envelope, b3_outlines raw
    # md_L_inner, h11's print: the protrusion per u; the 120 px/mm crop h12_teeth_m1d.png): (name, kind, u0, u1, value). Each
    # an extrusion of the arm's inner-edge faces (the two faces round the inner extreme) between the stations nearest u0 and u1.
    #   knob    a small rounded denticle, value its protrusion (mm): M1d's traced peaks (0.24 at u 0.408; the broad basal knob
    #           0.30-0.36 over u 0.454-0.487; 0.15 at 0.611-0.617); the COMB between the large tooth and the tine, four knobs
    #           in the photo (h12: rounded, 0.25-0.3 mm across), which the tracing renders as one ramp 0.10 -> 0.37 over u
    #           0.634-0.690: their peaks on the ramp's rise
    #   finger  the large tooth: its base where M1d's protrusion rises (0.135 at u 0.510 to its tip; its distal side short, back
    #           at 0.598), its plan path and widths `finger_large`
    #   tine    the fork's tine: its base from the rise at u 0.709 to the fall at 0.778, its path `tine_path`
    features=(('denticle', 'knob', 0.401, 0.417, 0.24), ('basal knob', 'knob', 0.447, 0.493, 0.34),
              ('large tooth', 'finger', 0.509, 0.601, 0.599), ('knob', 'knob', 0.601, 0.616, 0.15),
              ('comb 1', 'knob', 0.632, 0.647, 0.14), ('comb 2', 'knob', 0.647, 0.662, 0.21),
              ('comb 3', 'knob', 0.662, 0.678, 0.28), ('comb 4', 'knob', 0.678, 0.693, 0.36),
              ('tine', 'tine', 0.709, 0.785, 0.737)),
    knob_shape=((0.45, 0.80), (0.80, 0.64), (1.0, 0.38)),   # a knob's rings: (the share of its protrusion, the share of the
    #                                                      base's size) each: a rounded bump (m7 v1's two rings, (0.70, 0.62) /
    #                                                      (1.0, 0.40), stood boxy tiles, h11 _m7a teeth_inside). (m7o) 0.90 /
    #                                                      0.72 / 0.42 -> 0.80 / 0.64 / 0.38: on the comb's adjacent knobs the
    #                                                      first rings stood 0.03 mm apart at their shared station, and with the
    #                                                      patch frame 14 L4 vertices still crossed there; at 0.80, none (c03
    #                                                      knobPA); the knobs ~10 % narrower, the notches between them deeper
    knob_frame='patch',                                  # (m7o, the beetle's B5) a knob's rings: 'patch', scaled copies of its
    #                                                      base patch IN THE PATCH'S OWN PLANE (its along-arm and i6 -> i4
    #                                                      axes), translated along the protrusion (n_out, horizontal: M1d's
    #                                                      plan protrusion); 'world' (m7n) vertical sections (world up). Over the
    #                                                      comb the inner face leans 45-53 deg off vertical (the lens's roll),
    #                                                      so a vertical first ring stood BEHIND the patch's lower vertices along
    #                                                      the protrusion: the wall folded under, and the limit crossed itself
    #                                                      on every knob (b5_cage c01 / c03: clusters of 1,200-1,400 L4
    #                                                      vertices at z 9.7-10.7, the engineering check's reversed inner teeth)
    # the large tooth (M1d at 45 px/mm in the plan frame, h17_teeth_trace.py: the dark cuticle's run per plan x, its holes
    # (the specular streaks) filled): its midline (x, z) from the arm out to the tip and its half-width IN PLAN there: 1.49 mm
    # wide at x 3.0, 1.09 at 2.5, 0.76 at 2.0, 0.53 at 1.5, 0.40 at 1.3, the tip rounded at (1.08, 8.28): a broad tooth tapering
    # 0.58 mm per mm to a rounded point; the right mandible's (its tip at x -2.06) the same width at the same distance from the
    # tip within 0.04 (0.82 / 0.84 at 1.0 mm, 1.16 / 1.19 at 1.5). (m7's h12 reading by eye at 120 px/mm, 0.63 at x 3.0 .. 0.30 at
    # 1.5, measured the dark core between the streaks: half the tooth.) Round-topped (a highlight streak along its ridge): the
    # half-height b = finger_b x the half-width, at most bmax
    finger_large=dict(path=((3.40, 8.66, 0.80), (3.00, 8.544, 0.745), (2.50, 8.411, 0.545), (2.00, 8.333, 0.378),
                            (1.50, 8.311, 0.267), (1.30, 8.289, 0.200)), tip=(1.08, 8.28), b=0.80, bmax=0.36),
    finger_section=2.2,                                  # the large tooth's and the tine's rings on this superellipse (template)
    tine_frame_blend=(0.0, 0.5, 1.0),                    # per tine ring from the root: the share of the run's own frame (the
    #                                                      rest the base's: up and along the arm). (A collar ring, the base loop
    #                                                      offset 0.12 along the jaw's inside, stood a square plinth with corners
    #                                                      and widened the width gate's u 0.65-0.70 to +0.11: not kept)
    hook_u=(0.66, 0.70),                                 # the stations over the hook: the tine is the side view's lower
    #                                                      contour there, the arm's rings only bounded by the lines (m4: u
    #                                                      0.722 out of it, its bottom on the fork edge, 4.31 at z 11.39: the
    #                                                      blade's crotch; left free it stood at 5.77, the depth gate's -0.318
    #                                                      at z 12.0 and -0.191 at 12.5)
    snap_frac=((0.715, 0.735, 0.6),),                    # (u0, u1, share): the bottom's snap partial there (m4 first try,
    #                                                      whole: the fork edge's 4.31 at z 11.39 sank the crotch, +0.18 at z
    #                                                      12.0)
    keel_sharp=(0.0, 0.09, 1.4),                         # (u0, u1, s): the bottom point's edges along the arm creased between
    #                                                      these u (DKT s): the base's ventral corner (u 0.083, z 0.58) without
    #                                                      the limit's undershoot past it (smooth: 0.19 under M1l's line at z
    #                                                      1.0, +0.12); m7 1.4 over the even stations (m6's 2.0 over 0.02 ..
    #                                                      0.14, four stations: m7's seven would make a long crisp keel)
    base_dive=1.2,                                       # mm per mm: the dorsal bound's fall behind M1l's dorsal line, inside
    #                                                      the head (the base under the dish floor: 13.70 by z -1.5, the floor
    #                                                      13.9-14.1 at the front corners)
    line_bow=0.03,                                       # mm per ring step squared: a bounded point keeps clear of M1l's line
    #                                                      by this times its steps from the lens's top / bottom point (m3's
    #                                                      plain clip set runs of points ON the line: flat flanks, the sections
    #                                                      gate's 0.32-0.37 mm at u 0.10, 0.30, 0.80)
    tip_clip=(0.93, 0.985),                              # (m7o, the beetle's B5) the side view's clip and snaps eased out over
    #                                                      these u (1 -> 0): M1l's dorsal line ends at z 15.5 and the fork edge's
    #                                                      last 0.6 mm rises 1 mm per mm into the tip point (15.66, 5.96), while
    #                                                      the last rings, oblique to z, span z +-0.2 mm and reach 0.2 mm past
    #                                                      the lines' end: per point, half of station 67's and 68's rings were
    #                                                      clipped to the dorsal line and half not (a step inside the ring), the
    #                                                      rest pressed up by the rising edge (station 68 0.22 mm deep against
    #                                                      its lens's 0.39), and the end cap folded; past u 0.93 the rings keep
    #                                                      their lens sections round the solve's centreline
    bow_depth=0.15,                                      # (m7o, the beetle's B5) the bow at most this share of the station's
    #                                                      lens depth: the full bow (0.27 mm at 3 steps) is a ninth of the arm's
    #                                                      2.4 mm, but over the tip's last stations (0.39-0.65 mm deep) it
    #                                                      pressed the flanks into a band narrower than the ring: station 67's
    #                                                      ring crossed itself (its outer points above its top), 66's inner face
    #                                                      0.07 mm tall, and the limit crossed itself at the tip (b5_cage c03:
    #                                                      ~1,200 L4 vertices at (0.9, 11.3, 15.7)); the arm's rings unchanged
    push_sigma=0.025,                                    # (m7m, the B3h check) a 'p' push's gaussian along the arm (u; 1.6
    #                                                      stations, 0.44 mm): the base's narrowing one smooth trough
    w_add=((0.20, -0.10, 'p'), (0.25, -0.05, 'p'), (0.505, 0.10), (0.624, -0.05), (0.700, -0.14), (0.955, 0.10), (0.985, 0.05)),   # the ring's
    #                                                      inner half pushed inward (sine-weighted, TOP
    #                                                      to BOTTOM, at the station nearest u and half at its neighbours):
    #                                                      at the tip where M1d's envelope is wider than the B3f solve's lens
    #                                                      (0.57 at u 0.95, -0.104); outward at u 0.20 (b03 _b3gchk2 +0.114: the
    #                                                      cage's lens has no plan prism to trim it, B3f's had). m7: the notch
    #                                                      between the basal knob and the large tooth (u 0.497-0.505 on M1d's
    #                                                      trace) 0.10 in, once (m4-m6's 0.20 at 0.511 filled it: +0.185 at u
    #                                                      0.55); the notches either side of the comb OUT (M1d's trace at the
    #                                                      arm's edge, +0.018 at u 0.625, and 0.13 outside it at 0.695-0.704:
    #                                                      between single-face knobs the subdivision bridges a one-face gap, h11
    #                                                      _m7b +0.087-0.097 at u 0.60-0.70)
    lift=0.05,                                           # a tooth's underside over M1l's lower line at least
    hook=((10.58, 4.57), (10.76, 4.42), (10.98, 4.32), (11.30, 4.31)),   # [M-ph M1l contour_s01c] the hook's end (z, h)
    # the TINE's rings: (x fraction to the tip, z fraction to tine_tip_z, its underside's fraction down to the hook's 4.31, the
    # half-width across in plan, the half-height); the tip ring's rear at M1l's 10.58. m7: a FINGER out of a BROAD flare (the
    # first ring close to the base's own size: b3g's 0.62 x the base read as a crevice round its narrow base, the B3g check);
    # m7g its widths from M1d at 45 px/mm (h17_teeth_trace.py, both mandibles by the distance from the tip: 0.36 at 0.1 mm, 0.49
    # at 0.25, 0.58 at 0.45, 0.63 at 0.6, 0.75 at 1.0, 0.84 at 1.2-1.45, left and right within 0.03: near-parallel sides, the tip
    # rounded); its tip's reach the two sides' mean (the specimen's left tine crosses the midline to x -0.2, its right stops at
    # -1.45: the left mandible closed further), as b3f's; the half-heights from M1l (the depth gate) [the vertical fractions E]
    tine_path=((0.18, 0.11, 0.30, 0.80, 0.85), (0.32, 0.21, 0.72, 0.42, 0.29), (0.52, 0.38, 0.95, 0.38, 0.23),
               (0.74, 0.58, 1.00, 0.31, 0.19), (0.88, 0.78, 1.00, 0.245, 0.165), (0.96, 0.92, 1.00, 0.175, 0.13),
               (1.0, 1.0, 1.0, 0.10, 0.07)), tine_tip_z=10.80,
    #                                                      (m7 v1's underside fractions 0.18 / 0.45 / 0.72 at the first rings
    #                                                      left the tine 0.24 short of M1l's 4.31 at z 11.5, h11 _m7a)
    #                                                      (the first ring's half-length / half-height as SHARES of the base's)
    rho=0.05, sharp_inner=0.0, levels=4, grid_h=0.04, clamp=(-1.2, 1.8), blur=0.025, pad=0.6)


def cache_key(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=lambda o: np.asarray(o).tolist()).encode()).hexdigest()[:16]


def smooth01_(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ring_index():
    """the ring's size and its extremes' indices (outer 0, top, inner, bottom) from MCAGE ring_split"""
    a, b, c, d = MCAGE['ring_split']
    top = a + 1
    inner = top + b + 1
    bottom = inner + c + 1
    return bottom + d + 1, top, inner, bottom


def ring_lens(core):
    """the unit lens's ring points (CCW from the OUTER extreme: outer, ring_split's points, TOP, ..., INNER, ..., BOTTOM, ...)
    and their outward normals"""
    c = np.asarray(core, np.float64)
    n = len(c)
    io, it, ii, ib = int(np.argmax(c[:, 0])), int(np.argmax(c[:, 1])), int(np.argmin(c[:, 0])), int(np.argmin(c[:, 1]))
    k1, k2, k3, k4 = MCAGE['ring_split']

    def between(a, b, k):
        idx = [(a + j) % n for j in range(((b - a) % n) + 1)]
        P = c[idx]
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        t = s[-1] * np.arange(1, k + 1) / (k + 1)
        return [idx[int(np.argmin(np.abs(s - tt)))] for tt in t]
    order = [io] + between(io, it, k1) + [it] + between(it, ii, k2) + [ii] + between(ii, ib, k3) + [ib] + \
        between(ib, io, k4)
    P = c[order]
    e = np.roll(c, -1, axis=0) - np.roll(c, 1, axis=0)
    nrm = np.column_stack([e[:, 1], -e[:, 0]])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    return P, nrm[order]


def build_cage(spec, clear, log=print):
    """the closed pose's cage targets (world, y = h + clear): QuadMesh with the targets as V, the arm-only mesh, the
    creases, the tooth records"""
    from . import insect as HD
    from scipy.interpolate import CubicSpline
    from scipy.ndimage import gaussian_filter1d
    g = HD.mandible_geometry(spec, clear, 'closed')
    mc = MCAGE
    u_all = g['u']
    sol = g['sol']
    C = g['centre']
    Nn, Bn = sol['N'], sol['B']
    W, H = g['width'], g['depth']
    core = HD.lens_section()
    LP, LN = ring_lens(core)
    st = np.linspace(mc['u_range'][0], mc['u_range'][1], mc['n_st'])          # m7: EVEN stations
    nr, I_TOP, I_IN, I_BOT = ring_index()
    ns = len(st)
    rho = mc['rho']
    Cs = CubicSpline(u_all, C, axis=0)(st)
    Ns = CubicSpline(u_all, Nn, axis=0)(st)
    Bs = CubicSpline(u_all, Bn, axis=0)(st)
    Ns /= np.linalg.norm(Ns, axis=1, keepdims=True)
    Bs /= np.linalg.norm(Bs, axis=1, keepdims=True)
    Ws, Hs = np.interp(st, u_all, W), np.interp(st, u_all, H)
    ring = np.zeros((ns, nr, 3))
    for j in range(ns):
        sx, sy = max(Ws[j] - 2 * rho, 0.05), max(Hs[j] - 2 * rho, 0.05)
        for k in range(nr):
            a_ = LP[k, 0] * sx + rho * LN[k, 0]
            b_ = LP[k, 1] * sy + rho * LN[k, 1]
            ring[j, k] = Cs[j] + a_ * Ns[j] + b_ * Bs[j]
        # (m7) the FLANKS bulged out along their normals by flank_bulge x sin(pi t) between the lens's extremes (the extremes
        # themselves, which carry the width and the depth, unmoved)
        for k0, k1 in ((0, I_TOP), (I_TOP, I_IN), (I_IN, I_BOT), (I_BOT, nr)):
            for k in range(k0 + 1, k1):
                nl = np.array([LN[k % nr, 0] / sx, LN[k % nr, 1] / sy])
                nl /= np.linalg.norm(nl)
                ring[j, k % nr] += mc['flank_bulge'] * np.sin(np.pi * (k - k0) / (k1 - k0)) * (nl[0] * Ns[j] + nl[1] * Bs[j])
    for wa in mc['w_add']:
        u_w, d_w = wa[0], wa[1]
        prop = len(wa) > 2 and wa[2] == 'p'
        j0 = int(np.argmin(np.abs(st - u_w)))
        if prop:
            # (m7m, the B3h check) a 'p' push (the base's narrowing at u 0.20 / 0.25) a GAUSSIAN along the arm over push_sigma
            # (u): on single stations (1, 0.5, 0.5) the two pushes left station 19 (u 0.233) half-pushed between full ones, two
            # dents striping the arm's inner face (x02: the high-pass dark at u 0.19 and 0.25 on the inner half), which b03's
            # width envelope (the most lateral inner point within +-0.06 u) read as narrowing over its whole window
            wts_w = [(j, float(np.exp(-0.5 * ((st[j] - u_w) / mc['push_sigma']) ** 2))) for j in range(ns)]
            wts_w = [(j, w_) for j, w_ in wts_w if w_ > 0.01]
        else:
            wts_w = ((j0, 1.0), (j0 - 1, 0.5), (j0 + 1, 0.5))             # (m7: eased over the even stations' neighbours)
        for j, wgt in wts_w:
            if 0 <= j < ns:
                a_in = float((ring[j, I_IN] - Cs[j]) @ Ns[j])
                for k in range(I_TOP + 1, I_BOT):
                    if prop:
                        # (m7k) PROPORTIONAL: each point by its own offset across the arm over the inner extreme's (the
                        # inner half scaled across, its curvature kept: the sine-weighted outward push at u 0.20 / 0.25
                        # flattened the inner flank, b03 _b3h's flat runs 0.52 / 0.40 at u 0.20 / 0.30)
                        w_k = float(np.clip(((ring[j, k] - Cs[j]) @ Ns[j]) / a_in, 0.0, 1.0)) if abs(a_in) > 1e-9 else 0.0
                    else:
                        w_k = np.sin(np.pi * (k - I_TOP) / (I_BOT - I_TOP))
                    ring[j, k] -= wgt * d_w * w_k * Ns[j]  # (-N: toward the inside)
    # the arm's SIDE VIEW on M1l's lines (SPEC outline mand_dorsal / mand_ventral / mand_fork, extended as b03 extends them):
    # every ring point within [the lower line, the dorsal line] at its own z; the lens's TOP point (with its neighbours) onto
    # the dorsal line and its BOTTOM onto the lower line (the KEEL at the base, the arm's underside, the BLADE on the fork
    # edge: one surface, no separate cone or blade), except over the hook, where the tine is the lower contour
    # (m3: the rings stand normal to the arm, oblique to z where it plunges: their side points dipped 0.15 under the line at z
    # 10.0, the depth gate's +0.106; the tops sat 0.13 under the dorsal line at z 1.0, its -0.167)
    o_ = spec['outline']
    fk = np.array(o_['mand_fork'], np.float64)
    fk = fk[np.argsort(fk[:, 0])]
    zd_, hd_ = np.array(o_['mand_dorsal'], np.float64).T
    zv_, hv_ = np.array(o_['mand_ventral'], np.float64).T
    zL_ = np.concatenate([zv_, fk[fk[:, 0] > zv_[-1], 0]])
    hL_ = np.concatenate([hv_, fk[fk[:, 0] > zv_[-1], 1]])
    zD_, hD_ = np.append(zd_, fk[-1, 0]), np.append(hd_, fk[-1, 1])
    wts = (0.25, 0.6, 1.0, 0.6, 0.25)
    kk = np.arange(nr)
    step_b = np.minimum(np.abs(kk - I_BOT), nr - np.abs(kk - I_BOT))      # ring steps from the BOTTOM point / the TOP
    step_t = np.minimum(np.abs(kk - I_TOP), nr - np.abs(kk - I_TOP))
    bow_b = mc['line_bow'] * np.minimum(step_b, 3) ** 2                    # (the bow only near the extreme point: 3 steps,
    bow_t = mc['line_bow'] * np.minimum(step_t, 3) ** 2                    # 0.27 mm at most; m4's first try bowed by 8 steps
    #                                                                        and crossed the bounds on the tip's small rings)

    def low_line(z):
        """M1l's lower line: before mand_ventral's first point the base's ventral corner (mandible_geometry's Vz, through
        landmarks.mand_base_vent at z 0.63), then the table and the fork edge"""
        return np.array([float(g['Vz'](zz)) if zz < zv_[0] else float(np.interp(zz, zL_, hL_)) for zz in np.atleast_1d(z)])
    over_hook = (mc['hook_u'][0] < st) & (st < mc['hook_u'][1])
    frac = np.ones(ns)
    for u0_, u1_, f_ in mc['snap_frac']:
        frac[(st >= u0_) & (st <= u1_)] = f_
    kt, kb = I_TOP, I_BOT

    def bounds(j):
        lo_ = low_line(ring[j, :, 2]) + clear
        # (the dorsal line only over mand_dorsal's own run: b03 extends it to the tip by a chord, which runs under M1l's
        # convex dorsal contour at z 12-13 (m3 first try: the depth at z 12.0 -0.30))
        on_d = ring[j, :, 2] <= zd_[-1]
        # (behind the dorsal line's first point, inside the head, the bound DIVES base_dive per mm: held at M1l's 14.18 the
        # base's rings stood over the dish floor (13.7-13.9 at the front corners) and showed through it, b03 _b3g4m)
        hi_line = np.interp(ring[j, :, 2], zD_, hD_) - mc['base_dive'] * np.maximum(zd_[0] - ring[j, :, 2], 0.0)
        return lo_, np.where(on_d, hi_line + clear, np.inf), on_d
    # (m7o) the clip's and the snaps' weight per station: 1, eased to 0 over MCAGE tip_clip (the tip's last rings)
    tcl = mc.get('tip_clip')
    w_clip = np.ones(ns) if tcl is None else 1.0 - smooth01_((st - tcl[0]) / (tcl[1] - tcl[0]))
    for rep in range(3):
        dts, dbs = np.zeros(ns), np.zeros(ns)
        for j in range(ns):
            lo_, hi_, on_d = bounds(j)
            # the bound bowed: clear of the line by line_bow x steps^2 away from the extreme point (no run of points on it);
            # where the ring is too shallow for both bows, the plain lines; (m7o) the bow at most bow_depth of the lens's
            # depth at the station (the tip's small rings)
            sc_b = min(1.0, mc.get('bow_depth', np.inf) * float(Hs[j]) / max(float(bow_b.max()), 1e-9))
            lob, hib = lo_ + sc_b * bow_b, hi_ - sc_b * bow_t
            tight = lob > hib
            lob[tight], hib[tight] = lo_[tight], hi_[tight]
            yc = np.clip(ring[j, :, 1], lob, hib)
            ring[j, :, 1] = ring[j, :, 1] + w_clip[j] * (yc - ring[j, :, 1])
            dts[j] = w_clip[j] * ((hi_[kt] - ring[j, kt, 1]) if on_d[kt] else 0.0)
            dbs[j] = w_clip[j] * frac[j] * (lo_[kb] - ring[j, kb, 1])
        if rep == 2:
            break
        # (m7) the snaps SMOOTHED along the stations (normalised over the snapping ones; none over the hook): each ring's top
        # and bottom moved as its neighbours are, no ring snapped apart from them (m3-m6's close stations at the base's ventral
        # corner snapped to different points of the lower line: a seam ring)
        msk = (~over_hook).astype(float)
        sm = lambda v: gaussian_filter1d(v * msk, mc['snap_smooth'], mode='nearest') / np.maximum(    # noqa: E731
            gaussian_filter1d(msk, mc['snap_smooth'], mode='nearest'), 1e-9)
        dts, dbs = sm(dts) * msk, sm(dbs) * msk
        for j in range(ns):
            for o, w_ in zip(range(-2, 3), wts):
                ring[j, (kt + o) % nr, 1] += w_ * dts[j]
                ring[j, (kb + o) % nr, 1] += w_ * dbs[j]
    # ---- the tube's quads and caps (a 2 x 3 patch: the ring's 10 points its boundary, 2 interior points)
    V = [ring.reshape(-1, 3)]
    vid = lambda j, k: j * nr + (k % nr)                                    # noqa: E731
    Q = []
    for j in range(ns - 1):
        for k in range(nr):
            Q.append((vid(j, k), vid(j, k + 1), vid(j + 1, k + 1), vid(j + 1, k)))
    nxt = ns * nr

    def cap(j, flip):
        nonlocal nxt
        # the patch: an m x 2 grid whose boundary is the ring's loop (m = (nr - 4) / 2): its bottom row the loop's 0 .. m, its
        # right end m + 1 (the middle row's), its top row m + 2 .. 2m + 2 (reversed), its left end 2m + 3; the middle row's
        # m - 1 interior points between them
        m = (nr - 4) // 2
        L_ = [vid(j, k) for k in range(nr)]
        cen = ring[j].mean(0)
        # (bulged outward along the arm by a third of the ring's radius: a flat cap's interior points left a notch at the tip, m3)
        tj = Cs[min(j + 1, ns - 1)] - Cs[max(j - 1, 0)]
        tj = tj / np.linalg.norm(tj) * (1.0 if j == ns - 1 else -1.0)
        bul = 0.33 * float(np.mean(np.linalg.norm(ring[j] - cen, axis=1))) * tj
        Bv = L_[0:m + 1]
        Tv = [L_[2 * m + 2 - c] for c in range(m + 1)]
        mids = []
        for c in range(1, m):
            pm = 0.5 * (ring[j, c] + ring[j, 2 * m + 2 - c])
            mids.append(0.6 * pm + 0.4 * cen + bul)
        ids = list(range(nxt, nxt + m - 1))
        V.append(np.array(mids))
        nxt += m - 1
        Mv = [L_[2 * m + 3]] + ids + [L_[m + 1]]
        qs = [(Bv[c], Bv[c + 1], Mv[c + 1], Mv[c]) for c in range(m)] + [(Mv[c], Mv[c + 1], Tv[c + 1], Tv[c])
                                                                       for c in range(m)]
        for q in qs:
            Q.append(q[::-1] if flip else q)
    cap(0, True)
    cap(ns - 1, False)
    arm_V = np.concatenate(V)
    arm_Q = np.array(Q, int)
    # ---- the FEATURES (m7): extrusions of the inner edge's faces (the two faces round the inner extreme I_IN) over the
    # stations nearest each feature's u0 .. u1 (MCAGE features): KNOBS, the large tooth's FINGER, the TINE. A patch nj gaps
    # long has a boundary of 2 nj + 4 points; every ring of its extrusion the same count, on a rounded rectangle (template)
    recs = []
    Qx = [q for q in Q]
    Vx = [arm_V]
    nV = len(arm_V)
    i4, i5, i6 = I_IN - 1, I_IN, I_IN + 1                     # (i4 above the inner extreme, i6 below it)
    up = np.array([0.0, 1.0, 0.0])
    low = float(np.min(np.array(mc['hook'])[:, 1]))

    def template(nj, n_exp=None):
        """the section's (along, up) points for a patch nj gaps long, in its boundary's order: the proximal side (top, middle,
        bottom), the bottom edge, the distal side (bottom, middle, top), the top edge back; a rectangle, its corners in. n_exp
        (m7g, the large tooth and the tine): each point pulled onto the superellipse |x|^n + |y|^n = 1 along its ray (n 2: an
        ellipse): a round-topped finger whose ridge carries M1d's highlight streak (the rectangle's flat top and crisp rims
        read as a plate)"""
        cor = 0.80
        P = [(-cor, cor), (-1.0, 0.0), (-cor, -cor)] + [(-1.0 + 2.0 * m / nj, -1.0) for m in range(1, nj)]
        P += [(cor, -cor), (1.0, 0.0), (cor, cor)] + [(-1.0 + 2.0 * m / nj, 1.0) for m in range(nj - 1, 0, -1)]
        P = np.array(P, np.float64)
        if n_exp is not None:
            P = P / ((np.abs(P[:, 0]) ** n_exp + np.abs(P[:, 1]) ** n_exp) ** (1.0 / n_exp))[:, None]
        return P

    for name, kind, u0_, u1_, val in mc['features']:
        ja, jb = int(np.argmin(np.abs(st - u0_))), int(np.argmin(np.abs(st - u1_)))
        nj = jb - ja
        rem = set()
        for j in range(ja, jb):
            rem.add((vid(j, i4), vid(j, i5), vid(j + 1, i5), vid(j + 1, i4)))
            rem.add((vid(j, i5), vid(j, i6), vid(j + 1, i6), vid(j + 1, i5)))
        n0_ = len(Qx)
        Qx = [q for q in Qx if q not in rem]
        assert n0_ - len(Qx) == 2 * nj, f'{name}: its patch overlaps another feature'
        bl = [vid(ja, i4), vid(ja, i5), vid(ja, i6)] + [vid(j, i6) for j in range(ja + 1, jb)] + \
            [vid(jb, i6), vid(jb, i5), vid(jb, i4)] + [vid(j, i4) for j in range(jb - 1, ja, -1)]
        nb = len(bl)
        TP = template(nj, None if kind == 'knob' else mc['finger_section'])
        base_c = np.mean([arm_V[v] for v in bl], axis=0)
        e_al = arm_V[vid(jb, i5)] - arm_V[vid(ja, i5)]
        a0 = 0.5 * np.linalg.norm(e_al)
        b0 = 0.5 * np.linalg.norm(arm_V[vid(ja, i4)] - arm_V[vid(ja, i6)])
        al0 = e_al - up * (e_al @ up)
        al0 /= np.linalg.norm(al0)
        n_out = -np.mean(Ns[ja:jb + 1], axis=0)                     # toward the jaw's inside
        n_out -= up * (n_out @ up)
        n_out /= np.linalg.norm(n_out)
        h_bot0 = 0.5 * (arm_V[vid(ja, i6)][1] + arm_V[vid(jb, i6)][1]) - clear      # the inner edge's underside at the base
        rings = []                                                  # (centre, the section's along-axis, a, b[, its up-axis])
        if kind == 'knob' and mc.get('knob_frame', 'world') == 'patch':
            # (m7o) the rings in the base patch's own plane (MCAGE knob_frame): its up the patch's i6 -> i4 axis, its along
            # axis the arm's direction square to that, half-height b0 measured along it; each ring a scaled copy of the
            # base translated along the plan protrusion n_out, so every wall runs forward from its base vertex
            u_p = (arm_V[vid(ja, i4)] + arm_V[vid(jb, i4)]) - (arm_V[vid(ja, i6)] + arm_V[vid(jb, i6)])
            u_p /= np.linalg.norm(u_p)
            al_p = e_al - u_p * (e_al @ u_p)
            al_p /= np.linalg.norm(al_p)
            b_p = 0.25 * float(((arm_V[vid(ja, i4)] - arm_V[vid(ja, i6)]) + (arm_V[vid(jb, i4)] - arm_V[vid(jb, i6)])) @ u_p)
            rings += [(base_c + s_ * val * n_out, al_p, f_ * a0, f_ * b_p, u_p) for s_, f_ in mc['knob_shape']]
        elif kind == 'knob':
            rings += [(base_c + s_ * val * n_out, al0, f_ * a0, f_ * b0) for s_, f_ in mc['knob_shape']]
        elif kind == 'finger':
            fl = mc['finger_large']
            path = np.array(fl['path'], np.float64)
            b2 = np.array([base_c[0], base_c[2]])
            # the flare a third of the way out to the path's first point at the base's own size, then the traced sections, then
            # the rounded tip
            secs = [(b2 + 0.35 * (path[0, :2] - b2), 0.85 * a0, 0.85 * b0)] + \
                [(p[:2], p[2], min(fl['b'] * p[2], fl['bmax'])) for p in path]
            tip = np.array(fl['tip'], np.float64)
            d_ = (tip - secs[-1][0]) / np.linalg.norm(tip - secs[-1][0])
            secs.append((tip - 0.05 * d_, 0.55 * secs[-1][1], 0.55 * secs[-1][2]))
            h_base = float(base_c[1]) - clear
            kseg_f = 0                                      # (the flare ring, the base's own size, is not a traced width)
            for c2, a_k, b_k in secs:
                # the section TILTED with M1l's lower line along the arm, its underside at least `lift` over the line at both
                # of its ends (m2: level sections hung under the climbing line, the depth gate's +0.18-0.37 at z 8-10)
                z_c = c2[1]
                sl_ = (float(g['Vz'](z_c + 0.1)) - float(g['Vz'](z_c - 0.1))) / 0.2
                al = np.array([al0[0], sl_ * al0[2], al0[2]])
                al /= np.linalg.norm(al)
                if kseg_f > 0:
                    a_k = a_k / float(np.hypot(al[0], al[2]))   # (m7g) the traced half-width is in PLAN: the tilted axis's
                    #                                             plan share (0.85-0.88 on the line's slope -0.6 .. -0.8)
                kseg_f += 1
                need = max(float(g['Vz'](z_c + sg_ * a_k * al[2])) - sg_ * a_k * al[1] for sg_ in (-1.0, 1.0))
                rings.append((np.array([c2[0], max(h_base, need + b_k + mc['lift']) + clear, c2[1]]), al, a_k, b_k))
        else:
            # THE TINE (M1d: inward to its tip and BACK; M1l: down, its lower edge 4.31-4.33 over z 10.98-11.5 rising to its rear
            # at 10.58, BEETLE_BODY_PHOTOS 7c: the tine's whole length foreshortened in the side view): MCAGE tine_path
            t = min(g['teeth'], key=lambda tt: abs(tt['u'] - val))
            tip2 = np.asarray(t['tip'], np.float64)
            npth = len(mc['tine_path'])
            for kseg, (fx, fz, fb, a_t, b_t) in enumerate(mc['tine_path'], start=1):
                if kseg == 1:
                    a_t, b_t = a_t * a0, b_t * b0
                x_ = base_c[0] + (tip2[0] + 0.10 - base_c[0]) * fx
                z_ = base_c[2] + (mc['tine_tip_z'] - base_c[2]) * fz
                hb_ = h_bot0 + (low - h_bot0) * fb + (0.02 if kseg == npth else 0.0)
                rings.append((np.array([x_, hb_ + b_t + clear, z_]), al0 if kseg < npth else np.array([0.0, 0.0, 1.0]),
                              a_t, b_t))
        prev = bl
        for kr, ring_k in enumerate(rings):
            cen, al, a_k, b_k = ring_k[:4]
            upk = ring_k[4] if len(ring_k) > 4 else up
            if kind == 'tine':
                # (the tine FALLS: its section normal to its own run, not to the horizontal; in the (along, vertical) plane
                # it was sheared into a flat blade from below, h11 _m7a fork_below)
                dk = rings[min(kr + 1, len(rings) - 1)][0] - (rings[kr - 1][0] if kr > 0 else base_c)
                dk /= np.linalg.norm(dk)
                upk = up - dk * (up @ dk)
                upk /= np.linalg.norm(upk)
                al = np.cross(upk, dk)
                al *= np.sign(al @ al0) if abs(al @ al0) > 1e-9 else 1.0
                # (m7g) the root's rings keep the base's own frame, the run's frame blended in over the next (the first ring
                # turned square to the steep fall leaned its top out over the base's top edge: a curled lip over a crevice
                # at the tine's upper root, and its bottom back into the arm; h11 _m7h fork_inside / teeth_inside)
                w_ = mc['tine_frame_blend'][min(kr, len(mc['tine_frame_blend']) - 1)]
                upk = (1.0 - w_) * up + w_ * upk
                upk /= np.linalg.norm(upk)
                al = (1.0 - w_) * al0 + w_ * al
                al -= upk * (al @ upk)
                al /= np.linalg.norm(al)
            pts = cen[None, :] + TP[:, :1] * a_k * al[None, :] + TP[:, 1:] * b_k * upk[None, :]
            ids = list(range(nV, nV + nb))
            Vx.append(pts)
            nV += nb
            for m in range(nb):
                Qx.append((prev[m], prev[(m + 1) % nb], ids[(m + 1) % nb], ids[m]))
            prev = ids
        # the cap across the last ring: its middle row (the proximal middle, nj - 1 interior points, the distal middle)
        r, Pl = prev, Vx[-1]
        top = [r[0]] + [r[4 + 2 * nj - m] for m in range(1, nj)] + [r[4 + nj]]
        bot = [r[2]] + [r[2 + m] for m in range(1, nj)] + [r[2 + nj]]
        mids = [r[1]]
        if nj > 1:
            ax_ = rings[-1][0] - (rings[-2][0] if len(rings) > 1 else base_c)
            ax_ /= np.linalg.norm(ax_)
            rad = float(np.mean(np.linalg.norm(Pl - Pl.mean(0), axis=1)))
            mp = [0.5 * (Pl[4 + 2 * nj - m] + Pl[2 + m]) + 0.30 * rad * ax_ for m in range(1, nj)]
            mids += list(range(nV, nV + nj - 1))
            Vx.append(np.array(mp))
            nV += nj - 1
        mids.append(r[3 + nj])
        for m in range(nj):
            Qx.append((top[m], mids[m], mids[m + 1], top[m + 1]))
            Qx.append((mids[m], bot[m], bot[m + 1], mids[m + 1]))
        recs.append(dict(name=name, kind=kind, u0=float(st[ja]), u1=float(st[jb]), segments=len(rings)))
    Vfull = np.concatenate(Vx)
    mesh = QuadMesh(Vfull, np.array(Qx, int))
    arm = QuadMesh(arm_V, arm_Q)
    # orientation: outward (the signed volume positive)
    for m_ in (mesh, arm):
        Vv, Qq = m_.V, m_.Q
        vol = np.sum(np.einsum('ij,ij->i', Vv[Qq[:, 0]], np.cross(Vv[Qq[:, 1]] - Vv[Qq[:, 0]], Vv[Qq[:, 2]] - Vv[Qq[:, 0]])))
        if vol < 0:
            m_.Q = m_.Q[:, ::-1].copy()
    # the KEEL's crease: the bottom point's edges along the arm between MCAGE keel_sharp's u (the same ids in the arm)
    u0_, u1_, s_k = mc['keel_sharp']
    sharp = {(vid(j, I_BOT), vid(j + 1, I_BOT)): float(s_k) for j in range(ns - 1) if st[j] >= u0_ and st[j + 1] <= u1_}
    return mesh, arm, sharp, recs, g


def limit(mesh, sharp, levels):
    """the controls fitted (the limit through the targets) and the limit mesh. (m7f) The vertices no quad uses (the inner
    patch's points where a feature replaced its faces) are left out of the fit and the subdivision (left in, their free
    controls went to -95 mm and the subdivision carried them as stray points); V0 keeps the cage's numbering (those
    vertices at their targets)"""
    Q = np.asarray(mesh.Q)
    used = np.zeros(len(mesh.V), bool)
    used[Q.ravel()] = True
    new = -np.ones(len(mesh.V), int)
    new[used] = np.arange(int(used.sum()))
    mc_ = QuadMesh(np.asarray(mesh.V)[used], new[Q])
    sh_ = {(int(new[a]), int(new[b])): s for (a, b), s in sharp.items() if used[a] and used[b]}
    V0c, res = SS.fit_controls(mc_, sh_, mc_.V, levels + 1)
    lim, _, _, _ = SS.subdivide(QuadMesh(V0c, mc_.Q), sh_, levels)
    V0 = np.array(mesh.V, float, copy=True)
    V0[used] = V0c
    return lim, V0, res


def grid_of(V, F, log=print):
    """the posed limit mesh's GRID values on a box round it (MCAGE grid_h, pad), clamped and blurred"""
    from . import insect_cage as IC
    from scipy import ndimage as nd
    mc = MCAGE
    h = mc['grid_h']
    Vu = V[np.unique(np.asarray(F).ravel())]          # (m7f) the box round the surface's own vertices
    lo = Vu.min(0) - mc['pad']
    hi = Vu.max(0) + mc['pad']
    n = tuple(int(np.ceil((hi[a] - lo[a]) / h)) + 1 for a in range(3))
    d = IC.mesh_sdf(V, F, lo, h, n, log, band=max(abs(mc['clamp'][0]), abs(mc['clamp'][1])))
    d = np.clip(d, mc['clamp'][0], mc['clamp'][1])
    d = nd.gaussian_filter(d, mc['blur'] / h, mode='nearest').astype(np.float32)
    return d, lo


def mandible_grids(spec, clear, pose, log=print):
    """the left mandible's GRID values at the pose (world, life mm, y = h + clear) and the arm alone's, cached"""
    from . import insect as HD
    key = cache_key(dict(v=VERSION, mc=MCAGE, md=spec['mandible'], o={k: spec['outline'][k] for k in
                         ('mand_outer', 'mand_inner', 'mand_dorsal', 'mand_ventral', 'mand_plan', 'mand_fork')},
                         lm=spec['landmarks'], clear=round(float(clear), 6), pose=pose, mand=HD.MAND))
    path = os.path.join(CACHE, f'beetle_subd_mand_{key}.npz')
    if not os.path.exists(path):
        t0 = time.time()
        mesh, arm, sharp, recs, g = build_cage(spec, clear, log)
        R, hinge = g['R'], g['hinge']
        if pose != 'bind':
            R = np.eye(3)
        out = {}
        for nm, m_ in (('whole', mesh), ('arm', arm)) if pose == 'closed' else (('whole', mesh),):
            lim, V0, res = limit(m_, sharp, MCAGE['levels'])
            Vw = hinge + (lim.V - hinge) @ (R.T if pose == 'bind' else np.eye(3))
            d, lo = grid_of(Vw, lim.tris(), log)
            out[f'{nm}_values'] = d
            out[f'{nm}_lo'] = lo
            out[f'{nm}_cage'] = m_.V
            out[f'{nm}_cageQ'] = m_.Q
            out[f'{nm}_ctrl'] = V0
            log(f'[mcage] {pose} {nm}: cage {len(m_.V)} vertices / {len(m_.Q)} quads, fit residual {res:.1e}, grid {d.shape}')
        np.savez_compressed(path, **out)
        log(f'[mcage] built the subdivision mandible ({pose}) in {time.time() - t0:.0f}s -> {os.path.relpath(path, REPO)}')
    Z = np.load(path, allow_pickle=False)
    return {k: Z[k] for k in Z.files}
