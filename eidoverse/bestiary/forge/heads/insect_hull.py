"""B3c: the stag beetle's HEAD CAPSULE as a VOLUME built from the photographs (the lead, B3c 10-21: "clay built from
primitives reads as primitives however well measured"; B3b's station loft read as a flat-walled box with a ball eye).
The method is the wolf's W2c head (heads/canid_hull.py, read, not imported): the VISUAL HULL of the head's traced
silhouettes, rounded by a CONSTRAINED CURVATURE FLOW on its level set, then sculpted with STROKES, entering the head's
program as ONE sampled signed-distance GRID member (the staged patch work/bestiary/patches/sdf_grid.md, read-only:
sdf.Program.grid). Everything here is this module's own code (the wolf's round may move its machinery while this runs).

THE FRAME: the plan frame in LIFE millimetres, x the creature's left, h above the venter's lowest point, z forward from
the clypeal tip. The grid's axes are (x, h, z); the flow runs on the x >= 0 half with a mirror plane at x = 0 (the head
is symmetric), the finished grid is the full width.

1. THE HULL: a voxel survives if it lies inside every view's limit (OUTER limits: the views can only bound the head,
   so the flow's pressure inflates the surface up to them):
     DORSAL   M1d's head outline (|x|, z): the front margin over the mandible bases (B3b's LIP edge from
              outline.mand_plan's base edge), the clypeal process's two lobes (res_s01a fp_L / fp_R), the anterior
              angles and the side (SPEC outline.head_half), the side under the eye (head_half less the eye's sliver:
              the dome stands proud of it on M1d), behind the eye M1d's head_post, the back [E] into the collar
     LATERAL  M1l's head outline (z, h): the top M1l's dorsal line (outline.dorsal_line) from the frons top back to the
              crest arms' bases (the crest itself is a stroke, below), the frons bevel to the mandible's dorsal base
              (landmarks), the underside traced on M1l (B3c, LATERAL's rows: the gula and genae under the eye, the
              postgena dropping to the prothorax), the face below the mandible base
     SECTIONS rounded cross-sections (|x|, h) at every z: the dorsal half-width, the lateral top and bottom, the widest
              point at SEC_WIDE's height, superellipse quadrants above and below it (SEC exponents [E]): an outer limit
              that rounds the two extrusions' box corners (the wolf's skull sections play this part)
     FRONTS   P3 (the front view, the head reared, seen from below-front) and c03 (behind-left, above) through their
              solved cameras (FRONTS: traced outlines, landmarks, the camera fitted on them): OUTER limits only, with
              their tolerances
2. THE FLOW: phi_t = (kappa - F) |grad phi| (kappa the mean curvature, the sum of the principal curvatures; F an
   inflation pressure 1 / (c r), r the hull's local half-thickness), each step clamped between the outer limits
   (lower bound) and the INNER limits (upper bound): balls round the mandible condyles (the head holds the mandible's
   base) and the eye's centre (the head holds the dome's socket), pins on the landmarks (the frons top, the head top
   at the eye, the head under the eye) and along M1l's top line (on the midline) and M1d's outline (at its widest
   height); stage A at BUILD h_A, stage B at h_B, then a short pure-curvature relax.
3. THE STROKES (STROKES): the dish of the top between the front margin and the crest (c03, M1d); the CREST along M1d's
   arcs (its top M1l's line on the midline, the arms tapering into the rims: no knob where an arm ends); the SIDE
   SWOLLEN round the eye and the CANTHUS lobe over its front; the SUPRAOCULAR ridge from the canthus over the orbit to
   the crest arm; the ORBIT, the capsule opened round the eye along M1l's eye outline on the dome (the eye shell sits
   in it: B3b's eye was a ball on a flat wall); the CLYPEAL PROCESS a rounded plate and the MENTUM a trapezoid slab
   (M1d, M3v); B3d: the orbit's raised rim, the frontal ridge across the frons top, the raised front and lateral
   margins, the mentum's surroundings recessed (STROKES' B3d rows). Then
   the exact distance to the zero set (marching cubes and Warp's BVH), the far field clamped, a light blur, and the
   GRID member's proved divisor (sdf_grid.md).
Deterministic from this module's tables and the SPEC, cached on disk by its inputs' hash (work/bestiary/beetle/
cache_hull).
"""
import hashlib
import json
import os
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))          # heads -> forge -> bestiary -> eidoverse
CACHE = os.path.join(REPO, 'work', 'bestiary', 'beetle', 'cache_hull')
VERSION = 'b3f-12'               # b3f-12 (the B3f check, 10-27): the dish floor's clip a SOFT-MIN of the nearby crests
#                                  (FEAT bowl3 soft_lam / soft_mu: no creases along the dish corners' bisectors) and fT's
#                                  normalisation capped (FEAT fT_slope: no ridges or beads where U steps behind the lobes).
#                                  b3f-11: no slot behind the crest's lateral end (lip z_back), the lip's cove 0.30 (the
#                                  head's |grad| p1 0.589 at b3f-8, f17); the clypeal plate's blend stays 0.10 (0.30 filled
#                                  the front margin's outer face over it: its apex at x 0 fitted 0.076, b3f-10).
#                                  b3f-8: the lobes a convex ellipse from |x| 1.9 (FEAT lobe x_sh, fall 0).
#                                  b3f-7: no void under the clypeal plate (the cut above its underside).
#                                  b3f-6: the crest's lateral half sharper, the lip release held past the slit (z_off).
#                                  b3f-5: the lobes fall off laterally past the shoulder (FEAT lobe fall).
#                                  b3f-3: the lobes one dome falling to the side line behind the lip zone (top_field's mass
#                                  argument, the side circle released there), the anterior circle raised to contain the
#                                  knob's rim, the release past the crest's lateral end, the bowl a little deeper and rounder.
#                                  b3f-2: the side circle from the mass's widest line (SEC_WIDE raised behind the eye and at
#                                  the anterior angles, the mass rebuilt), the front margin turning ~138 deg (wall_p_front,
#                                  its outer face 68 deg), the lip's drip edge (beta -10), the crest's opening 0.11, the
#                                  bowl's cross curvature easing at the front margin (kx_front).
#                                  b3f-1 (the lead's B3f, 10-27: every surface curved, the edges crisp by their turning): the
#                                  floor a bowl (FEAT bowl3), the inner walls C2 (wall_p), the outer faces arcs (face_R), the
#                                  side a circle per section met near-tangentially by the mass's round gena (side; the gena
#                                  ellipsoid gone), the supraocular lip the side's release along M1l's line (lip), the lobes
#                                  broad transverse domes (lobe), the clypeal process a rounded plate under the front margin's
#                                  crest (process), the mentum part of the underside (mentum3), no mandible-base cover.
#                                  b3e-5 (the B3e check, 10-26): the mandible bases' cover faired into the dish's floor (FEAT
#                                  skin_*: a cone dilation, smoothed, a smooth max; b3e-2..4's raw raster left a rough lump
#                                  with a 0.27 mm rear drop, a dark slit from above).
#                                  b3e-4 (the B3e check, 10-26): the top's block no longer stands under the clypeal process in
#                                  front of the front margin (FEAT clypeus_floor: its vertical walls and flat bottom stood
#                                  0.31-0.39 mm proud of the mass, up to 0.62 past M1l's face, the ragged block between the
#                                  mandible bases).
#                                  b3e-3: the orbit's opening on the SPEC's eye ellipse (b3e-2: a spline through the traced
#                                  outline; b3e-1: the traced 10-point polygon, a decagon rim); the dish's floor over the
#                                  mandibles' bases (FEAT mand_skin; the key carries insect.MAND).
#                                  b3e-1 (the lead's B3e, 10-22): the mass (hull + flow) cached alone; every feature CSG with
#                                  measured fillets (FEAT); b3d-3 (the B3d check, 10-22): c03's front held out (FRONT_HELD: its camera is the
#                                  depth-reversed fit); b3d-2: the fronts' partial runs bound their traced side only (b3d-1
#                                  cut the head);
#                                  b3d-1 (10-22): tolerances, frontal limits, the strokes at measured heights, the rim,
#                                  the frontal ridge and margins, the mentum's trapezoid; b3c-2 (the B3c check, 10-22):
#                                  the orbit's rim from M1l's outline clipped to the dome

# ============================================================================================ the frozen tables (mm)
# DORSAL: M1d's half outline of the capsule (|x|, z), front to back, the midline at both ends. The clypeal process's
# lobes at res_s01a fp_L / fp_R (1.48 / 1.62, z +0.68 / +0.71; the notch between them at the clypeal tip, z 0); its
# sides meet the front margin at the mandibles' inner bases (mand_base_in, |x| 1.72-1.86, z -0.31 .. -0.53); the
# front margin (B3b's LIP edge: outline.mand_plan's base edge, where M1d's head covers the mandibles) to the outer
# bases (mand_base_out, 7.17-7.39); the anterior angle (head_ant 8.35-8.39 at z -0.71 .. -0.79) and the side (SPEC
# outline.head_half, z -0.75 .. -3.0); under the eye the capsule's side (head_half at z -3.5 .. -4.5 is the eye's
# sliver, 0.79 proud of it: eye.sliver); behind the eye head_half (z -5.0) and head_post (7.94 at z -5.94); behind
# that [E] the side narrowing into the pronotum's collar (the head's back is buried)
DORSAL = ((0.00, 0.00), (0.45, 0.38), (1.05, 0.66), (1.55, 0.70), (1.95, 0.05), (2.60, -0.38), (2.90, -0.42),
          (5.00, -0.30), (7.00, -0.30), (7.70, -0.50), (8.35, -0.75), (8.53, -1.00), (8.74, -1.50), (8.755, -2.00),
          (8.59, -2.50), (8.40, -3.00), (8.20, -3.30), (7.86, -3.60), (7.78, -4.00), (7.84, -4.40), (8.00, -4.80),
          (8.12, -5.00), (7.94, -5.94), (7.80, -6.50), (7.62, -7.20), (7.40, -7.90), (7.15, -8.50), (6.90, -9.05),
          (6.60, -9.60), (6.25, -10.20), (5.70, -10.90), (0.00, -11.20))
# LATERAL: M1l's head outline (z, h), clockwise from the clypeal process's front: the process (CLYPEUS's front, z
# +0.70); the mandible's dorsal base (landmarks.mand_base_dors); the frons bevel to the frons top; M1l's dorsal line
# (outline.dorsal_line) to z -6.5; the crest arms' bases (the rim under the crest, [E] under M1l's line: the crest is
# a stroke) and the head's top falling into the pronotum's collar (M1l: 13.89 at z -9.5); the back [E], buried; the
# underside TRACED (B3c 10-21, bview.py grid beetle/scratch_b03c/g_m1l_headlow.png, M1l px through b3_outlines.Frames:
# (3450, 3110) (3400, 3070) (3330, 3020) (3250, 3001) (3180, 2999) (3100, 2997) (3050, 2998) (3000, 2995) (2960,
# 2985)), at z -5.02 the mean of that trace (8.13) and the landmark head_under_eye (7.75, read by eye +-10 px);
# behind z -7.6 the prothorax hides it [E]; the face below the mandible base rising to its ventral base (landmarks)
LATERAL = ((0.70, 13.85), (0.20, 14.15), (-0.55, 14.25), (-1.10, 14.24), (-1.60, 14.75), (-2.00, 15.33), (-2.50, 15.12),
           (-3.00, 15.09), (-3.50, 14.78), (-4.00, 14.47), (-4.50, 14.50), (-5.00, 14.54), (-5.50, 14.59),
           (-6.00, 14.59), (-6.50, 14.64), (-7.00, 14.70), (-7.50, 14.74), (-8.00, 14.72), (-8.50, 14.55),
           (-9.00, 14.15), (-9.50, 13.55), (-10.00, 12.90), (-10.60, 12.20), (-11.10, 11.00), (-11.10, 7.60),
           (-10.20, 7.10), (-9.00, 6.65), (-8.20, 6.55), (-7.61, 6.69), (-6.96, 7.22), (-6.06, 7.87), (-5.02, 7.94),
           (-4.11, 8.16), (-3.07, 8.19), (-2.42, 8.18), (-1.78, 8.22), (-1.26, 8.36), (-0.55, 9.30), (0.20, 9.70),
           (0.45, 9.95), (0.05, 10.60), (-0.15, 12.00), (0.15, 12.85), (0.70, 13.25))
#                                  (the front: the clypeal process on top, the face under it set back, the mandible's
#                                  ventral condyle forward at the bottom, landmarks.mand_base_vent z +0.63, h 9.84)
SEC_WIDE = ((0.70, 13.30), (-0.80, 13.30), (-2.00, 13.35), (-3.00, 12.60), (-4.10, 11.50), (-5.20, 11.90),
            (-6.50, 12.25), (-8.00, 12.10), (-9.50, 11.60), (-11.0, 10.90))      # [E] the section's widest height (z,
#                                  h): the anterior angles high (M1d's margin), the eye's level at the eye (eye_c 11.46),
#                                  the postgena behind; gate b03's outlines and landmarks. B3f (the lead: the walls under the
#                                  margins convex): raised at the anterior angles (12.8 -> 13.35 at z -2.0) and behind the
#                                  eye (11.4-11.6 -> 11.9-12.25): the side above the widest line must reach the margin's
#                                  outer face (or the lip, M1l's line 13.5-14.0) 0.5 mm inside M1d's outline and stay convex
#                                  (radius <= 3.1 for no run flat within 0.01 mm over 0.5 mm); from 11.5 that is a 0.7-1.0 mm
#                                  shelf under the lip (beetle/scratch_b03f/f05 _f1, f07 _lip_f1); from 12.25 a 0.25-0.35 one.
#                                  No photo gives the widest height behind the eye (M1d the width only, M1l the side)
SEC = dict(p_top=2.1, q_top=2.0, p_bot=2.0, q_bot=1.8, tol=0.05)   # [E] the sections' superellipse quadrants (a
#                                  B3d: near-elliptic (B3c 2.6 / 2.2, flatter, under the extrusions' zero tolerance), the
#                                  limit that rounds the faces;
#                                  rounded top corner over the rims, a round bottom) and their outer tolerance
FRONTS = {}                        # P3 / c03, filled in BUILD order by front_views() (their tables below)
BUILD = dict(box_lo=(-10.6, 5.8, -11.6), box_hi=(10.6, 17.6, 1.9), h_A=0.15, h_B=0.075, steps_A=120, dt_A=0.1,
             reinit_A=20, steps_B=30, dt_B=0.12, reinit_B=10, relax=10, pressure_c=0.4, size_r=2.2,
             tol_dorsal=0.14, tol_lateral=0.14, pin_r=0.55, rim_r=0.70, clamp=(-1.9, 2.5), blur=0.12)
#                                  B3d (the lead: the hull's tolerances were 0, so the flow pressed the surface onto the
#                                  extrusions: flat runs of 1-1.9 mm): the wolf head's outer tolerances on its profile and
#                                  top (canid_hull BUILD: 2 mm) scaled by the heads' sizes (the hull boxes' diagonals,
#                                  27.8 / 407 mm: 0.068): 0.14, so the flat EXTRUSIONS stand off and the ROUNDED SECTIONS
#                                  bind (SEC: elliptic quadrants, tol 0.05). The wolf's pressure c 1.0 does not carry: its
#                                  r is the depth within 16 mm (30-90 mm), ours within 2.2 mm (1.2-2.2), and at c 1.0 the
#                                  curvature won and the head fell away from every view (dorsal p90 1.70, build h01 _d1)
#                                  the grids (the flow's at h_A then h_B mm), its steps and time steps IN CELLS (dt x
#                                  h^2 mm^2: the explicit curvature term is stable below ~1/6; the wolf's 0.1 and
#                                  0.12 at its 2 and 1 mm cells), the pressure F = 1 / (c r) with r the hull's depth
#                                  over size_r mm, the views' outer tolerances, the pins' radii, the finished field's
#                                  clamp (mm: inside beyond the deepest it is read, SINK + the collar's blend, and past
#                                  the meshing band's coarse test 1.77; outside past that test) and blur (mm, 1.6 cells:
#                                  the exact distance's creases at thin parts' medial axes set the GRID divisor)
STROKES = dict(
    dish=dict(depth=0.42, z=(-2.4, -7.6), x=6.2, soft=1.8),            # [E] the top dished between the margin and the
    #                                                                     crest (c03, M1d), inside the rims (v6's soft 1.0
    #                                                                     left a crease across the top at its front)
    crest=dict(arc=((0.0, -8.653), (2.0, -8.15), (4.0, -7.35), (5.25, -7.15), (6.5, -6.95), (7.6, -6.35)),
               top=((0.0, None), (2.0, 15.70), (4.0, 14.98), (5.25, 14.86), (6.5, 14.78), (7.6, 14.62)),
               front=0.72, back=0.48, end_ramp=2.2),                      # [M-ph M1d] the ridge line (B3b's CREST_ARC
    #                                  on head_grid_M1d_60_s.png), its top M1l's line on the midline (landmarks.
    #                                  head_crest) and [E] under M1l's line along the arms; its half-widths ahead /
    #                                  behind the line [M-ph M1l: the dorsal line's rise ahead of the peak, 0.37 of it
    #                                  at 1.15 mm, 0.69 at 0.65; behind, 0.24 at 0.85: v6's 0.45 / 0.26 stood a fin]
    #                                  and the ramp over which each arm fades into the rim (no knob)
    # B3d (the lead: make the strokes READ at measured heights; B3c's 0.18-0.42 mm did not read): the swollen side, the
    # canthus plate over the eye's front and the supraocular ridge raised to what M1l shows (beetle/scratch_b03d/
    # v_m1l_head.png at 77 px / mm: the supraocular ridge a band 0.5 mm deep standing off the side above the eye, the
    # canthus a plate over the eye's front 0.4-0.5 mm proud, the gena below and behind the eye bulging); the ORBIT's raised
    # rim, the FRONTAL ridge (M1d's transverse raised margin at the frons top: B3c's pin there left a nub), the raised
    # front and lateral MARGINS (M1d, c03: a lip along the anterior margin and the anterior angles) [E heights, gated by
    # the renders beside M1l and c03]
    frons=dict(z=-2.08, half=0.45, x0=3.4, fade=2.2, height=0.24),
    margin=dict(height=0.22, inset=0.32, width=0.20, z_back=-3.3, fade=0.7),
    rim=dict(height=0.17, out=0.16, width=0.15),
    swell=dict(height=0.45, r=2.3, below=1.20, behind=1.10),  # [E] the side swollen round the eye: a smooth dome
    #                                  about the eye's axis (Gaussian radius r), more below and behind (M1l: the gena and
    #                                  the postocular side), the orbit opened in it (v6's ring at r0 1.7 left a groove
    #                                  between the eye and its crest: the crease behind the eye)
    canthus=dict(height=0.42, centre=(-3.05, 11.5), half=(0.32, 1.25)),  # [E] the lobe over the eye's front (M1l):
    #                                  its centre (z, h) and half extents along z and h, raised outward, a vertical
    #                                  lobe at the orbit's front (the anterior angle above it is M1d's outline)
    supra=dict(points=((8.05, 13.35, -2.70), (7.95, 13.55, -3.60), (7.80, 13.55, -4.60), (7.65, 13.65, -5.60),
                       (7.55, 14.10, -6.30)), height=0.50, width=0.38),   # [E] the supraocular ridge (M1l): from the
    #                                  canthus's top over the orbit to the crest arm's end, its height and half-width
    orbit=dict(k=0.06, collar=0.05, collar_k=0.45, rim_clip=0.995),   # the capsule first closed over the whole dome
    #                                  (its sphere grown by collar, smooth-unioned by collar_k: the socket's margin), then
    #                                  opened along M1l's rim (the opening blended by k), so the eye sits IN the orbit (mm);
    #                                  M1l's outline clipped to the dome's lateral disc at rim_clip x R first (B3c check:
    #                                  its back-under corner past the disc left a gap in the rim, the crease behind the eye)
    clypeus=dict(c=(0.0, 13.45, -0.15), half=(1.80, 0.40, 0.85), pitch=-10.0, k=0.22),
    #                                  [E] the clypeal process, a rounded (ellipsoidal) plate between the mandible bases,
    #                                  its front at M1d's frontal process (fp, z +0.70)
    mentum=dict(trap=((3.90, -1.30), (4.10, -2.20), (2.50, -3.70)), low=8.17, thick=0.62, r=0.24, k=0.30,
                recess=0.26, recess_w=0.55),
    #                                  [M-ph M3v] B3d (the lead: M3v's TRAPEZOID plate; B3c's ellipsoid did not read): the
    #                                  mentum's half outline (|x|, z) front / widest / rear, read on beetle/scratch_b03d/
    #                                  v_m3v_head.png (1.0x) against M3v's head width (1043 px) x B1's HW: its front edge
    #                                  230 px each side 75 px behind M3v's head front, widest 245 px at 130 px, its rear
    #                                  150 px at 220 px; a slab, its lower face on M1l's traced underside (8.16-8.22), its
    #                                  corners rounded by r, the underside round it recessed by `recess` within recess_w
    #                                  (its edges then step) [E: thickness, the recess]
)


# ============================================================================================ small machinery
class Grid:
    """a dense grid in the plan frame (mm): index (i, j, k) at (x0 + i h, h0 + j h, z0 + k h)"""

    def __init__(self, lo, hi, h):
        self.lo = np.asarray(lo, np.float64)
        self.h = float(h)
        self.n = tuple(int(np.ceil((hi[a] - lo[a]) / h - 1e-9)) + 1 for a in range(3))
        self.x = self.lo[0] + np.arange(self.n[0]) * h
        self.y = self.lo[1] + np.arange(self.n[1]) * h
        self.z = self.lo[2] + np.arange(self.n[2]) * h

    def mesh(self):
        return np.meshgrid(self.x, self.y, self.z, indexing='ij')


def poly_raster(poly, lo, hi, res):
    """the 2D signed distance (mm, negative inside) of the closed polygon poly (k, 2) on a raster (u, v) from lo to hi at
    res mm: inside by the even-odd rule at the pixel centres, the two EDTs' difference"""
    from matplotlib.path import Path
    from scipy import ndimage as nd
    lo, hi = np.asarray(lo, np.float64), np.asarray(hi, np.float64)
    nu, nv = (np.ceil((hi - lo) / res).astype(int) + 1)
    U, V = np.meshgrid(lo[0] + np.arange(nu) * res, lo[1] + np.arange(nv) * res, indexing='ij')
    ins = Path(np.asarray(poly, np.float64)).contains_points(np.column_stack([U.ravel(), V.ravel()])).reshape(nu, nv)
    d = nd.distance_transform_edt(~ins) - nd.distance_transform_edt(ins) + np.where(ins, 0.5, -0.5)
    return (d * res).astype(np.float32), lo, res


def raster_at(img, lo, res, u, v):
    """a raster's value at (u, v) mm, bilinear, clamped to the raster (beyond it the far value grows by the excess)"""
    from scipy import ndimage as nd
    fu = (np.asarray(u, np.float64) - lo[0]) / res
    fv = (np.asarray(v, np.float64) - lo[1]) / res
    cu, cv = np.clip(fu, 0, img.shape[0] - 1), np.clip(fv, 0, img.shape[1] - 1)
    s = nd.map_coordinates(img, [cu.ravel(), cv.ravel()], order=1, mode='nearest').reshape(np.shape(u))
    return s + np.hypot(fu - cu, fv - cv) * res


def smooth_closed(P, n=600, sigma=2.0):
    """a closed polygon resampled evenly to n points and smoothed along itself (sigma in samples)"""
    from scipy.ndimage import gaussian_filter1d
    P = np.asarray(P, np.float64)
    Q = np.vstack([P, P[:1]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
    t = np.linspace(0.0, s[-1], n, endpoint=False)
    R = np.column_stack([np.interp(t, s, Q[:, 0]), np.interp(t, s, Q[:, 1])])
    return np.column_stack([gaussian_filter1d(R[:, k], sigma, mode='wrap') for k in range(2)])


def redistance(phi, h):
    """signed distance to phi's zero set: each voxel's nearest interface voxel (an EDT on the interface mask), its foot
    point there (s - phi grad / |grad|^2), the distance to it, phi's sign"""
    from scipy import ndimage as nd
    ins = phi < 0
    face = np.zeros_like(ins)
    for a in range(3):
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[a], sl1[a] = slice(0, -1), slice(1, None)
        ch = ins[tuple(sl0)] != ins[tuple(sl1)]
        face[tuple(sl0)] |= ch
        face[tuple(sl1)] |= ch
    g = np.stack(np.gradient(phi, h), 0)
    g2 = np.maximum((g * g).sum(0), 1e-12)
    idx = nd.distance_transform_edt(~face, return_distances=False, return_indices=True)
    I = tuple(idx[a] for a in range(3))
    pv, g2v = phi[I], g2[I]
    d2 = np.zeros(phi.shape, np.float64)
    for a in range(3):
        foot = idx[a] * h - pv * g[a][I] / g2v
        d2 += (np.arange(phi.shape[a]).reshape([-1 if b == a else 1 for b in range(3)]) * h - foot) ** 2
    return np.where(ins, -np.sqrt(d2), np.sqrt(d2)).astype(np.float32)


def redistance_half(phi, h):
    """redistance on the x >= 0 half (index 0 the mirror plane): mirrored to the full width, redistanced, cut back"""
    full = np.concatenate([phi[:0:-1], phi], axis=0)
    return redistance(full, h)[phi.shape[0] - 1:]


# ---- the flow, a Warp kernel (the wolf's scheme, written here): mean curvature by central differences, the pressure's
# outward motion by the upwind (Godunov) gradient norm, clamped each step; axis 0's first sample a mirror plane
def _kernels():
    import warp as wp

    @wp.func
    def nb(i: int, n: int, sym: int):
        if i < 0:
            if sym == 1:
                return wp.min(-i, n - 1)
            return 0
        if i > n - 1:
            return n - 1
        return i

    @wp.kernel
    def step(phi: wp.array3d(dtype=wp.float32), lo: wp.array3d(dtype=wp.float32), up: wp.array3d(dtype=wp.float32),
             pr: wp.array3d(dtype=wp.float32), h: float, dt: float, out: wp.array3d(dtype=wp.float32)):
        i, j, k = wp.tid()
        nx = phi.shape[0]
        ny = phi.shape[1]
        nz = phi.shape[2]
        im = nb(i - 1, nx, 1)
        ip = nb(i + 1, nx, 0)
        jm = nb(j - 1, ny, 0)
        jp = nb(j + 1, ny, 0)
        km = nb(k - 1, nz, 0)
        kp = nb(k + 1, nz, 0)
        c = phi[i, j, k]
        dx = (phi[ip, j, k] - phi[im, j, k]) / (2.0 * h)
        dy = (phi[i, jp, k] - phi[i, jm, k]) / (2.0 * h)
        dz = (phi[i, j, kp] - phi[i, j, km]) / (2.0 * h)
        dxx = (phi[ip, j, k] - 2.0 * c + phi[im, j, k]) / (h * h)
        dyy = (phi[i, jp, k] - 2.0 * c + phi[i, jm, k]) / (h * h)
        dzz = (phi[i, j, kp] - 2.0 * c + phi[i, j, km]) / (h * h)
        dxy = (phi[ip, jp, k] - phi[ip, jm, k] - phi[im, jp, k] + phi[im, jm, k]) / (4.0 * h * h)
        dxz = (phi[ip, j, kp] - phi[ip, j, km] - phi[im, j, kp] + phi[im, j, km]) / (4.0 * h * h)
        dyz = (phi[i, jp, kp] - phi[i, jp, km] - phi[i, jm, kp] + phi[i, jm, km]) / (4.0 * h * h)
        g2 = dx * dx + dy * dy + dz * dz
        num = dxx * (dy * dy + dz * dz) + dyy * (dx * dx + dz * dz) + dzz * (dx * dx + dy * dy) \
            - 2.0 * (dx * dy * dxy + dx * dz * dxz + dy * dz * dyz)
        kg = num / wp.max(g2, 1.0e-8)
        a = (c - phi[im, j, k]) / h
        b = (phi[ip, j, k] - c) / h
        gp = wp.max(a, 0.0) * wp.max(a, 0.0) + wp.min(b, 0.0) * wp.min(b, 0.0)
        a = (c - phi[i, jm, k]) / h
        b = (phi[i, jp, k] - c) / h
        gp = gp + wp.max(a, 0.0) * wp.max(a, 0.0) + wp.min(b, 0.0) * wp.min(b, 0.0)
        a = (c - phi[i, j, km]) / h
        b = (phi[i, j, kp] - c) / h
        gp = gp + wp.max(a, 0.0) * wp.max(a, 0.0) + wp.min(b, 0.0) * wp.min(b, 0.0)
        new = c + dt * (kg - pr[i, j, k] * wp.sqrt(gp))
        out[i, j, k] = wp.min(wp.max(new, lo[i, j, k]), up[i, j, k])

    @wp.kernel
    def mesh_dist(mesh: wp.uint64, lo: wp.vec3, h: float, ny: int, nz: int, maxd: float,
                  out: wp.array(dtype=wp.float32)):
        tid = wp.tid()
        i = tid // (ny * nz)
        j = (tid // nz) % ny
        k = tid % nz
        p = lo + wp.vec3(float(i) * h, float(j) * h, float(k) * h)
        q = wp.mesh_query_point_no_sign(mesh, p, maxd)
        if q.result:
            out[tid] = wp.length(p - wp.mesh_eval_position(mesh, q.face, q.u, q.v))
        else:
            out[tid] = maxd
    return step, mesh_dist


_K = {}


def kernels():
    if not _K:
        _K['step'], _K['mesh_dist'] = _kernels()
    return _K


def flow(phi, lower, upper, pressure, h, steps, dt, reinit, log=None):
    """the constrained flow on the x >= 0 half (Warp's preferred device): returns phi and the per-chunk largest change
    in the band"""
    import warp as wp
    K = kernels()
    lo_ = np.ascontiguousarray(lower, np.float32)
    up_ = np.ascontiguousarray(upper, np.float32)
    phi = np.minimum(np.maximum(phi, lo_), up_).astype(np.float32)
    L, U = wp.array(lo_, dtype=wp.float32), wp.array(up_, dtype=wp.float32)
    Pr = wp.array(np.ascontiguousarray(pressure, np.float32), dtype=wp.float32)
    A = wp.array(phi, dtype=wp.float32)
    B = wp.zeros(phi.shape, dtype=wp.float32)
    hist, done = [], 0
    while done < steps:
        n = min(reinit, steps - done)
        prev = A.numpy().copy()                                   # (on the CPU device numpy() is a view of A)
        for _ in range(n):
            wp.launch(K['step'], dim=phi.shape, inputs=[A, L, U, Pr, float(h), float(dt), B])
            A, B = B, A
        done += n
        new = A.numpy()
        band = np.abs(new) < 6 * h
        hist.append(float(np.abs(new - prev)[band].max()) if band.any() else 0.0)
        new = np.minimum(np.maximum(redistance_half(new, h), lo_), up_).astype(np.float32)
        A = wp.array(new, dtype=wp.float32)
        if log:
            log(f'[hull]   flow {done}/{steps}: max |dphi| in the band over the last {n} steps {hist[-1]:.4f} mm')
    return A.numpy().copy(), hist


def exact_distance(phi, G, maxd):
    """phi's zero set triangulated (marching cubes), every grid point's exact distance to it (Warp's BVH), phi's sign"""
    import warp as wp
    from skimage.measure import marching_cubes
    V, F, _, _ = marching_cubes(phi, 0.0, spacing=(G.h, G.h, G.h))
    V = (V + G.lo).astype(np.float32)
    m = wp.Mesh(points=wp.array(V, dtype=wp.vec3), indices=wp.array(F.astype(np.int32).ravel(), dtype=wp.int32))
    n = int(np.prod(G.n))
    out = wp.zeros(n, dtype=wp.float32)
    wp.launch(kernels()['mesh_dist'], dim=n, inputs=[m.id, wp.vec3(*G.lo.astype(np.float32)), float(G.h), int(G.n[1]),
                                                     int(G.n[2]), float(maxd), out])
    d = out.numpy().reshape(G.n)
    return np.where(phi < 0, -d, d).astype(np.float32)


def grid_divisor(V, h):
    """sdf_grid.md's proved bound for these values: per cell the root sum of squares of the steepest edge per axis"""
    s = []
    for a in range(3):
        e = np.abs(np.diff(V, axis=a)).astype(np.float64) / h
        others = [b for b in range(3) if b != a]
        m = None
        for o0 in (slice(0, -1), slice(1, None)):
            for o1 in (slice(0, -1), slice(1, None)):
                sl = [slice(None)] * 3
                sl[others[0]], sl[others[1]] = o0, o1
                m = e[tuple(sl)] if m is None else np.maximum(m, e[tuple(sl)])
        s.append(m)
    return max(1.0, float(np.sqrt(s[0] ** 2 + s[1] ** 2 + s[2] ** 2).max()))


def smin(a, b, k):
    hh = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - hh) + a * hh - k * hh * (1 - hh)


def smax(a, b, k):
    return -smin(-a, -b, k)


def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def cache_key(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=lambda o: np.asarray(o).tolist()).encode()).hexdigest()[:16]


def cached(name, key, build, log=print):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f'{name}_{key}.npz')
    if os.path.exists(path):
        z = np.load(path, allow_pickle=False)
        return {k: z[k] for k in z.files}
    t = time.time()
    out = build()
    np.savez_compressed(path, **out)
    log(f'[hull] built {name} in {time.time() - t:.0f}s -> {os.path.relpath(path, REPO)}')
    return out


# ============================================================================================ the views
VIEW_SMOOTH = (9.0, 12.0)          # the dorsal and lateral polygons smoothed along themselves over this many of 900
#                                    samples (~0.45 / 0.55 mm): the 0.5 mm rows' kinks printed as bands across the
#                                    flowed surface (the top line's across the dish, B3c probes h02 v3-v4)


def dorsal_poly():
    """the dorsal outline's closed polygon (x, z), both sides, smoothed"""
    H = np.array(DORSAL, np.float64)
    return smooth_closed(np.vstack([H, (H[-2:0:-1] * np.array([-1.0, 1.0]))]), 900, VIEW_SMOOTH[0])


def lateral_poly():
    """the lateral outline's closed polygon (z, h), smoothed"""
    return smooth_closed(np.array(LATERAL, np.float64), 900, VIEW_SMOOTH[1])


def lateral_at(z):
    """the lateral polygon's top and bottom h at z (the vertical line's crossings)"""
    P = lateral_poly()
    out = []
    for a, b in zip(P, np.roll(P, -1, axis=0)):
        if (a[0] - z) * (b[0] - z) <= 0 and a[0] != b[0]:
            out.append(a[1] + (b[1] - a[1]) * (z - a[0]) / (b[0] - a[0]))
    return (min(out), max(out)) if len(out) >= 2 else None


def half_width_at(z):
    """the dorsal half outline's largest |x| at z (its horizontal line's crossings)"""
    P = dorsal_poly()
    xs = []
    for a, b in zip(P, np.roll(P, -1, axis=0)):
        if (a[1] - z) * (b[1] - z) <= 0 and a[1] != b[1]:
            xs.append(abs(a[0] + (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1])))
    return max(xs) if xs else 0.0


def section_poly(z, n=120):
    """the rounded cross-section limit at z (x, h): superellipse quadrants from the widest point (W at SEC_WIDE's
    height) to the lateral top and bottom; None where the views leave nothing"""
    tb = lateral_at(z)
    W = half_width_at(z)
    if tb is None or W < 0.2:
        return None
    bot, top = tb
    sw = np.array(SEC_WIDE, np.float64)
    hw = float(np.clip(np.interp(z, sw[::-1, 0], sw[::-1, 1]), bot + 0.3, top - 0.3))
    t = np.linspace(0.0, 0.5 * np.pi, n // 2)
    up = np.column_stack([W * np.cos(t) ** (2.0 / SEC['p_top']), hw + (top - hw) * np.sin(t) ** (2.0 / SEC['q_top'])])
    dn = np.column_stack([W * np.cos(t) ** (2.0 / SEC['p_bot']), hw - (hw - bot) * np.sin(t) ** (2.0 / SEC['q_bot'])])
    right = np.vstack([dn[::-1], up])                                  # bottom centre -> widest -> top centre
    return np.vstack([right, right[-2:0:-1] * np.array([-1.0, 1.0])])


def view_fields(G, fronts):
    """each view's 2D signed distance at every voxel (mm): dorsal (x, z), lateral (z, h), the sections per z, the
    fronts in their cameras (the head symmetric: a voxel and its mirror must both project inside)"""
    X, Y, Z = G.mesh()
    out = {}
    img, lo, res = poly_raster(dorsal_poly(), (-12.0, -12.5), (12.0, 3.0), 0.02)
    out['dorsal'] = raster_at(img, lo, res, X, Z).astype(np.float32)
    img, lo, res = poly_raster(lateral_poly(), (-12.5, 4.5), (2.5, 18.5), 0.02)
    out['lateral'] = raster_at(img, lo, res, Z, Y).astype(np.float32)
    sec = np.full(G.n, -1.0e3, np.float32)            # (no section beyond the views' reach: the others bound it)
    for k, z in enumerate(G.z):
        P = section_poly(z)
        if P is None:
            continue
        img, lo, res = poly_raster(P, (-12.0, 4.5), (12.0, 18.5), 0.025)
        sec[:, :, k] = raster_at(img, lo, res, X[:, :, k], Y[:, :, k])
    from scipy.ndimage import gaussian_filter1d
    have = (sec[0, 0, :] > -999.0).astype(np.float32)               # smoothed along z among the slices that have one
    sm = gaussian_filter1d(np.where(have[None, None, :] > 0, sec, 0.0), 0.45 / G.h, axis=2, mode='nearest')
    ws = gaussian_filter1d(have, 0.45 / G.h, mode='nearest')
    out['sections'] = np.where(have[None, None, :] > 0, sm / np.maximum(ws, 1e-6)[None, None, :], sec).astype(np.float32)
    for nm, fr in fronts.items():
        img, lo, res = fr['raster']
        u, v = project(fr['cam'], X, Y, Z)
        um, vm = project(fr['cam'], -X, Y, Z)
        out['front_' + nm] = np.maximum(raster_at(img, lo, res, u, v), raster_at(img, lo, res, um, vm)).astype(
            np.float32)
    return out


def project(cam, X, Y, Z):
    """a camera's orthographic image coordinates (mm): (P . r, P . u) about its centre"""
    r, u, c0 = cam['r'], cam['u'], cam['c0']
    Px, Py, Pz = X - c0[0], Y - c0[1], Z - c0[2]
    return Px * r[0] + Py * r[1] + Pz * r[2], Px * u[0] + Py * u[1] + Pz * u[2]


# ============================================================================================ the fronts (P3, c03)
# Each front: its photo's traced head outline (px, the image-right half where the head is symmetric about its axis),
# the landmark pairs (px, plan-frame mm) the camera is fitted on (a scaled orthographic camera: a rotation, one scale
# and the image offset, least squares), and the outer tolerance (mm). B3c 10-21, read on bview.py grids in
# beetle/scratch_b03c (g_p3_head.png 1.58x; g_c03_head.png). The head in P3 is reared (a defence display), so P3 sees it
# from the front and below; c03 from behind-left and above.
FRONT_TABLES = dict(
    # B3d (the lead: the FRONTAL outer limits, P3 and c03 through solved cameras), read on bview.py grids
    # beetle/scratch_b03d/v_p3_head.png (1.63x) and v_c03_head.png (2.17x), px +-6. P3: the head reared, seen from the
    # front and below; the traced run its LEFT side (image right: the anterior angle's top, the eye's bulge, down to where
    # the head meets the prothorax; the mandible bases hide the front margin's corners); landmarks the anterior angles
    # (DORSAL's corner at z -0.75, at SEC_WIDE's height) and the eye domes' apices (heads/insect.py EYE_APEX), both sides
    P3=dict(outline=((1648, 625), (1662, 645), (1676, 672), (1686, 700), (1691, 728), (1690, 758), (1684, 788),
                     (1668, 815), (1645, 842), (1620, 866), (1600, 884)),
            axis=((1345, 600), (1345, 900)), tol=0.30,
            landmarks=dict(angle_L=((1650, 628), (8.35, 13.15, -0.75)), angle_R=((1050, 632), (-8.35, 13.15, -0.75)),
                           eye_L=((1676, 742), (8.55, 11.46, -4.15)), eye_R=((1040, 742), (-8.55, 11.46, -4.15)))),
)
# HELD OUT of the build (the B3d check, 10-22; beetle/scratch_b3dcheck/q04_c03_camera.py, q05_c03_constrained.py,
# q06_head_noc03.py, q03_c03_head.png): c03's only good scaled orthographic fit on these 4 landmarks (5.2 px rms; the next
# basin 43.6 px) is the DEPTH-REVERSED camera: behind and to the head's RIGHT (toward the camera -0.35, 0.77, -0.53), where
# the traced eye_L faces away from it (its outward normal . view -0.24), while c03 shows that eye and the head's left side
# face lit on the near side (the clay rendered through it shows its right eye on the image's right). The crest reading
# forces it: angle_L, angle_R and eye_L alone fit exactly a camera behind-LEFT and above (0.42, 0.68, -0.60; eye_L lit,
# +0.54), and that camera puts the crest landmark 137 px (5.6 mm) off its reading. Through the reversed camera the limit
# BOUND the head behind the eye (x 5.5-7.8, h 9.7-12.6, z -6.9 .. -10.0: 2,157 surface voxels on it, 0.34 mm median
# inside the next tightest limit), the dorsal silhouette 0.09-0.61 mm inside DORSAL at z -7.5 .. -10 (built without it:
# within -0.12 .. +0.21 mm). Re-read c03's landmarks (the crest point, or more of them) before it bounds anything again.
FRONT_HELD = dict(
    # c03 (behind-left, above): the traced run the head's left side (image left: the anterior angle, the canthus and the
    # eye, down under the eye to the gena); landmarks both anterior angles, the left eye, the crest's midline peak
    # (landmarks.head_crest) (the front margin's midpoint, read at (2335, 905), stood 26 px off the fit: left out)
    c03=dict(outline=((2147, 985), (2138, 1005), (2133, 1030), (2140, 1055), (2150, 1080), (2160, 1105), (2172, 1130),
                      (2190, 1155), (2215, 1175)),
             axis=((2335, 890), (2290, 1150)), tol=0.30,
             landmarks=dict(angle_L=((2147, 985), (8.35, 13.15, -0.75)), angle_R=((2535, 945), (-8.35, 13.15, -0.75)),
                            eye_L=((2168, 1077), (8.30, 11.46, -4.10)), crest=((2298, 1088), (0.0, 16.03, -8.65)))),
)


def fit_camera(px, X3):
    """the scaled orthographic camera taking plan-frame points X3 (n, 3) to photo px (n, 2) (image y down): returns
    dict(r, u (unit, the image's right and up in the plan frame), s px per mm, c0 the points' centroid, t its image,
    resid px)"""
    from scipy.optimize import least_squares
    px = np.asarray(px, np.float64)
    X3 = np.asarray(X3, np.float64)
    c0 = X3.mean(0)
    q = np.column_stack([px[:, 0], -px[:, 1]])                     # image up positive

    def rot(w):
        th = np.linalg.norm(w)
        if th < 1e-12:
            return np.eye(3)
        k = w / th
        Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
        return np.eye(3) + np.sin(th) * Kx + (1 - np.cos(th)) * Kx @ Kx

    def res(p):
        R = rot(p[:3])
        s, t = np.exp(p[3]), p[4:6]
        return (s * (X3 - c0) @ R[:2].T + t - q).ravel()
    best = None
    for w0 in ([0, 0, 0], [0.8, 0, 0], [-0.8, 0, 0], [0, 0.8, 0], [0, -0.8, 0], [0.6, 0.6, 0], [-0.6, 0.6, 0]):
        s0 = np.log(np.ptp(q[:, 0]) / max(np.ptp(X3[:, 0]), 1e-6) + 1e-9)
        r_ = least_squares(res, np.r_[w0, s0, q.mean(0)], method='lm')
        if best is None or r_.cost < best.cost:
            best = r_
    R = rot(best.x[:3])
    return dict(r=R[0], u=R[1], s=float(np.exp(best.x[3])), c0=c0, t=best.x[4:6],
                resid=float(np.sqrt(np.mean(best.fun.reshape(-1, 2) ** 2) * 2)))


def front_views(spec, log=print):
    """the solved cameras and the outer-limit rasters of the traced front outlines (in each camera's image mm about
    the landmarks' centroid): the traced outline (a run of the head's silhouette, px) offset outward by its tolerance,
    closed far beyond the untraced side across its photo's head axis (two px points); a voxel's projection must fall
    inside"""
    from scipy.ndimage import gaussian_filter1d
    out = {}
    for nm, tb in FRONT_TABLES.items():
        lm = tb['landmarks']
        px = [v[0] for v in lm.values()]
        X3 = [v[1] for v in lm.values()]
        cam = fit_camera(px, X3)
        to_mm = lambda Q: (np.column_stack([np.asarray(Q, float)[:, 0], -np.asarray(Q, float)[:, 1]]) - cam['t']) \
            / cam['s']                                                                          # noqa: E731
        img_mm = to_mm(tb['outline'])
        ax = to_mm(tb['axis'])
        d = (ax[1] - ax[0]) / np.linalg.norm(ax[1] - ax[0])
        nrm = np.array([d[1], -d[0]])
        if nrm @ (img_mm.mean(0) - ax[0]) < 0:
            nrm = -nrm                                                # toward the traced side
        T = np.gradient(img_mm, axis=0)
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
        N = np.column_stack([T[:, 1], -T[:, 0]])
        N *= np.where(np.sum(N * (img_mm - img_mm.mean(0)), axis=1) < 0, -1.0, 1.0)[:, None]   # outward
        outer = img_mm + tb['tol'] * N
        outer = np.column_stack([gaussian_filter1d(outer[:, k], 1.0, mode='nearest') for k in range(2)])
        far = 40.0
        # B3d: the run is a PARTIAL side (the mandibles hide the rest), so the limit bounds the traced side only: the run
        # carried on straight along the head's axis past both its ends (closed only between them, the head's parts beyond
        # the run's span along the axis fell outside: the first build cut the head's front away, h01 _d2)
        sg = 1.0 if (outer[-1] - outer[0]) @ d > 0 else -1.0
        a0, a1 = outer[0] - sg * d * far, outer[-1] + sg * d * far
        poly = np.vstack([a0[None], outer, a1[None], ax[0] + d * ((a1 - ax[0]) @ d) - nrm * far,
                          ax[0] + d * ((a0 - ax[0]) @ d) - nrm * far])
        lo, hi = poly.min(0) - 2.0, poly.max(0) + 2.0
        out[nm] = dict(cam=dict(r=cam['r'], u=cam['u'], c0=cam['c0']), scale=cam['s'], resid=cam['resid'],
                       raster=poly_raster(poly, lo, hi, 0.03), outline_mm=img_mm, poly=poly)
        log(f'[hull] front {nm}: camera fitted on {len(px)} landmarks, residual {cam["resid"]:.1f} px, {cam["s"]:.2f} '
            f'px/mm; view direction (plan frame) {np.round(np.cross(cam["r"], cam["u"]), 3)}')
    return out


# ============================================================================================ the build
def inner_balls(spec):
    """(centre (x, h, z), radius) balls the head must contain: the landmark pins, M1l's top line on the midline, M1d's
    outline at the widest height, the mandible condyles, the eye's socket"""
    lm, md = spec['landmarks'], spec['mandible']
    r, rr = BUILD['pin_r'], BUILD['rim_r']
    balls = []
    for k in ('head_top_eye',):                        # (the head under the eye: the lateral underside's own line)
        z, h = lm[k]
        balls.append(((0.0, h - r, z), r))
    # B3d: no pin at the frons top (B3c's midline pin there left a nub: the frons stroke raises M1d's transverse margin
    # instead, the lateral limit holds its height); the front margin held at M1d's line (z -0.30 between the mandible
    # bases and the anterior angles: the flow pulled it 0.06-0.27 mm back, the B3c check's k12), the pins inside the
    # rounded sections there
    rm = 0.32
    for x in (3.2, 4.2, 5.0):
        balls.append(((x, 13.60, -0.30 - rm), rm))
    # M1l's top line pinned on the midline (z -2.0 .. -6.5: the crest is a stroke)
    for z in np.arange(-2.2, -6.51, 0.3):
        tb = lateral_at(z)
        balls.append(((0.0, tb[1] - r, z), r))
    # M1d's outline at its widest height, the anterior angles and the side ahead of the eye, behind it (from z -1.3: a
    # pin's ball nearer the front corner stands out of the front margin)
    for z in list(np.arange(-1.3, -3.11, 0.3)) + list(np.arange(-5.0, -6.51, 0.3)):
        W = half_width_at(z)
        sw = np.array(SEC_WIDE)
        hw = float(np.interp(z, sw[::-1, 0], sw[::-1, 1]))
        balls.append(((W - rr, hw, z), rr))
    # the mandible condyles: the head holds the mandible's base (the hinge, M1d's outer base x, M1l's base height)
    x0, z0 = 0.5 * md['base_span'], -md['base_behind']
    h0 = 0.5 * (lm['mand_base_dors'][1] + lm['mand_base_vent'][1])
    balls.append(((x0 - 1.1, h0, z0 - 1.15), 0.85))             # (its front 0.3 behind the front margin)
    # the eye's socket: inside the dome's base disc (heads/insect.py eye_descs: its base plane SINK under the side)
    balls.append(((6.65, lm['eye_c'][1], -3.95), 0.95))
    return balls


def bounds(G, fields, balls):
    """the lower bound (the outer limits, their tolerances) and the upper bound (the inner balls) per voxel"""
    lower = np.maximum(fields['dorsal'] - BUILD['tol_dorsal'], fields['lateral'] - BUILD['tol_lateral'])
    lower = np.maximum(lower, fields['sections'] - SEC['tol'])
    for k, v in fields.items():
        if k.startswith('front_'):
            lower = np.maximum(lower, v)
    upper = np.full(G.n, np.inf, np.float32)
    X, Y, Z = G.mesh()
    for (cx, cy, cz), rad in balls:
        for sg in ((1.0,) if abs(cx) < 1e-9 else (1.0, -1.0)):
            d = np.sqrt((X - sg * cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2) - rad
            upper = np.minimum(upper, d)
    clash = lower > upper
    return lower.astype(np.float32), upper.astype(np.float32), int(clash.sum())


def silhouette_errors(G, phi, res=0.02, fronts=None):
    """the solid's silhouettes against the traced views: dorsal (the head's half outline z -0.75 .. -5.94 and the
    margin), lateral (the top line z -2 .. -6.5 and the underside trace), per view n, median, p90, max |e| mm (+ = the
    traced line outside the solid)"""
    from scipy import ndimage as nd
    full = np.concatenate([phi[:0:-1], phi], axis=0) if G.lo[0] >= -1e-9 else phi
    x0 = -G.x[-1] if G.lo[0] >= -1e-9 else G.lo[0]

    def sdmap(mn, lo2, h2, pts):
        nu, nv = int((mn.shape[0] - 1) * h2 / res) + 1, int((mn.shape[1] - 1) * h2 / res) + 1
        U, V = np.meshgrid(np.arange(nu) * res / h2, np.arange(nv) * res / h2, indexing='ij')
        zz = nd.map_coordinates(mn, [U.ravel(), V.ravel()], order=1, mode='nearest').reshape(nu, nv)
        m = zz < 0
        sd = (nd.distance_transform_edt(~m) - nd.distance_transform_edt(m) + np.where(m, 0.5, -0.5)) * res
        return nd.map_coordinates(sd, [(pts[:, 0] - lo2[0]) / res, (pts[:, 1] - lo2[1]) / res], order=1, mode='nearest')

    def stats(e):
        a = np.abs(e)
        return dict(n=int(len(e)), med=float(np.median(a)), p90=float(np.percentile(a, 90)), max=float(a.max()),
                    mean=float(np.mean(e)))
    out = {}
    H = np.array(DORSAL)
    keep = (H[:, 1] <= -0.75) & (H[:, 1] >= -5.94)
    D = np.vstack([H[keep], H[keep] * np.array([-1.0, 1.0])])
    out['dorsal'] = stats(sdmap(full.min(axis=1), np.array([x0, G.lo[2]]), G.h, D))
    L = np.array(LATERAL)
    keep = ((L[:, 0] <= -2.0) & (L[:, 0] >= -6.5) & (L[:, 1] > 13.0)) | ((L[:, 0] <= -1.26) & (L[:, 0] >= -7.61) &
                                                                          (L[:, 1] < 9.0))
    # the minimum over x: axes (h, z)
    out['lateral'] = stats(sdmap(full.min(axis=0), np.array([G.lo[1], G.lo[2]]), G.h,
                                 np.column_stack([L[keep, 1], L[keep, 0]])))
    # B3d: the FRONTS (P3, c03): the solid's inside voxels (the full width) through each solved camera, its silhouette
    # rasterised, the traced run's points against its boundary (+ = the trace outside the solid)
    for nm, fr in (fronts or {}).items():
        ii = np.nonzero(full < 0)
        Xs = x0 + ii[0] * G.h
        Ys, Zs = G.lo[1] + ii[1] * G.h, G.lo[2] + ii[2] * G.h
        u, v = project(fr['cam'], Xs, Ys, Zs)
        lo2 = np.array([u.min() - 1.0, v.min() - 1.0])
        nu, nv = int((u.max() - lo2[0] + 1.0) / res) + 1, int((v.max() - lo2[1] + 1.0) / res) + 1
        m = np.zeros((nu, nv), bool)
        m[((u - lo2[0]) / res).astype(int), ((v - lo2[1]) / res).astype(int)] = True
        m = nd.binary_closing(nd.binary_dilation(m, iterations=int(np.ceil(0.6 * G.h / res))), iterations=2)
        sd = (nd.distance_transform_edt(~m) - nd.distance_transform_edt(m) + np.where(m, 0.5, -0.5)) * res
        pts = fr['outline_mm']
        e = nd.map_coordinates(sd, [(pts[:, 0] - lo2[0]) / res, (pts[:, 1] - lo2[1]) / res], order=1, mode='nearest')
        out['front_' + nm] = stats(e)
    return out


def build_flow(spec, log=print):
    """stage A and stage B: the hull, its bounds, the flow, the relax; returns phi (the x >= 0 half), its grid, the
    silhouette errors of the hull and after the flow, the fronts"""
    fronts = front_views(spec, log)
    lo, hi = np.array(BUILD['box_lo'], float), np.array(BUILD['box_hi'], float)
    lo[0] = 0.0
    balls = inner_balls(spec)
    hist = []
    phi = None
    errs = {}
    for stage, h, steps, dt, reinit in (('A', BUILD['h_A'], BUILD['steps_A'], BUILD['dt_A'], BUILD['reinit_A']),
                                        ('B', BUILD['h_B'], BUILD['steps_B'], BUILD['dt_B'], BUILD['reinit_B'])):
        t = time.time()
        G = Grid(lo, hi, h)
        F = view_fields(G, fronts)
        lower, upper, clash = bounds(G, F, balls)
        hull = np.max(np.stack([F['dorsal'], F['lateral'], F['sections']] +
                               [v for k, v in F.items() if k.startswith('front_')]), axis=0)
        if phi is None:
            phi = redistance_half(hull, h)
            errs['hull'] = silhouette_errors(G, phi, fronts=fronts)
        else:
            from scipy import ndimage as nd
            fz = [G.n[a] / prev.n[a] for a in range(3)]
            phi = nd.zoom(phi, fz, order=1, mode='nearest', grid_mode=False)[:G.n[0], :G.n[1], :G.n[2]]
            phi = np.pad(phi, [(0, G.n[a] - phi.shape[a]) for a in range(3)], mode='edge')
            phi = redistance_half(phi.astype(np.float32), h)
        from scipy import ndimage as nd
        k = max(3, int(2 * BUILD['size_r'] / h) | 1)
        r_loc = -nd.minimum_filter(hull, size=k, mode='nearest')
        pressure = (1.0 / (BUILD['pressure_c'] * np.clip(r_loc, 1.2, 6.0))).astype(np.float32)
        log(f'[hull] stage {stage}: grid {G.n} at {h} mm, fields in {time.time() - t:.1f}s; {clash} voxels where an '
            f'outer limit meets an inner one (the inner wins)')
        t = time.time()
        phi, hs = flow(phi, np.minimum(lower, upper), upper, pressure, h, steps, dt * h * h, reinit, log)
        hist += hs
        log(f'[hull] stage {stage} flow: {steps} steps in {time.time() - t:.0f}s')
        prev = G
    # the relax: pure curvature, held by the inner balls only (the views' faint creases)
    if BUILD['relax']:
        _, up_b, _ = bounds(G, F, balls)
        phi, _ = flow(phi, np.full(G.n, -np.inf, np.float32), up_b, np.zeros(G.n, np.float32), G.h, BUILD['relax'],
                      BUILD['dt_B'] * G.h * G.h, BUILD['relax'], None)
    errs['flow'] = silhouette_errors(G, phi, fronts=fronts)
    return dict(phi=phi, grid=G, errors=errs, fronts=fronts, hist=hist)


# ============================================================================================ the strokes
def eye_geometry(spec):
    """the eye dome as heads/insect.py builds it (life mm, h above the venter): centre, axis, radius, the side plane's
    offset, and M1l's exposed outline (z, h) (src_s01c outlines.eye_lat through b3_outlines.Frames)"""
    from . import insect as HD
    ey, lm = spec['eye'], spec['landmarks']
    a = np.array([np.sin(np.radians(ey['splay'])), 0.0, np.cos(np.radians(ey['splay']))])
    apex = np.array([HD.EYE_APEX[0], lm['eye_c'][1], HD.EYE_APEX[1]])
    R = ey['radius']
    C = apex - R * a
    proud = ey['sliver'] / a[0]
    return dict(C=C, a=a, R=R, plane=R - proud, apex=apex)


def eye_outline(spec):
    """M1l's traced eye outline (z, h), closed (the photo strand's src_s01c outlines.eye_lat)"""
    import sys
    sys.path.insert(0, os.path.join(REPO, 'work', 'bestiary', 'research', 'beetle_scripts'))
    import b3_outlines as B3O
    F = B3O.Frames()
    return F.lat(np.array(F.sc['outlines']['eye_lat'], np.float64))


def sculpt(phi, G, spec, log=print):
    """the STROKES on the x >= 0 half (module docstring 3): displacements of the level set within a band, then the
    orbit's opening, the plates by smooth union. Returns phi and the strokes' curves"""
    from matplotlib.path import Path
    from scipy.spatial import cKDTree
    st = STROKES
    lm = spec['landmarks']
    X, Y, Z = G.mesh()
    band = np.abs(phi) < 2.5
    idx = np.nonzero(band)
    P = np.column_stack([X[idx], Y[idx], Z[idx]])
    D = np.zeros(len(P), np.float64)
    gy = np.gradient(phi, G.h, axis=1)[idx]
    curves = {}
    # ---- the dish: the top's centre lowered between the margin and the crest, inside the rims (c03, M1d)
    ds = st['dish']
    wz = smooth01((P[:, 2] - ds['z'][1]) / ds['soft']) * smooth01((ds['z'][0] - P[:, 2]) / ds['soft'])
    wx = 1.0 - smooth01((P[:, 0] - 0.35 * ds['x']) / (0.65 * ds['x']))
    top = smooth01((np.clip(gy, -1.0, 1.0) - 0.4) / 0.4)               # the top surface (its normal near +h)
    D -= ds['depth'] * wz * wx * top
    # ---- the crest along M1d's arc: a ridge on the top, its height reaching the measured top, its ends ramping out
    cr = st['crest']
    ax_ = np.array(cr['arc'])
    xs = np.linspace(0.0, ax_[-1, 0], 400)
    zc = np.interp(xs, ax_[:, 0], ax_[:, 1])
    tops = np.array([lm['head_crest'][1] if t is None else t for _, t in cr['top']])
    tc = np.interp(xs, ax_[:, 0], tops)
    tree = cKDTree(np.column_stack([xs, zc]))
    dd, j = tree.query(np.column_stack([P[:, 0], P[:, 2]]))
    # signed: ahead (+) or behind the line (the arc's local normal in plan points forward)
    tz = np.gradient(zc)
    tx = np.gradient(xs)
    nz_ = tx / np.hypot(tx, tz)
    nx_ = -tz / np.hypot(tx, tz)
    sgn = np.sign((P[:, 0] - xs[j]) * nx_[j] + (P[:, 2] - zc[j]) * nz_[j])
    w = np.where(sgn >= 0, cr['front'], cr['back'])
    prof = np.exp(-0.5 * (dd / w) ** 2)
    ramp = smooth01((ax_[-1, 0] - xs[j]) / cr['end_ramp'])
    # the base: the surface's own top at that column (the first crossing from above), so the ridge's top meets the
    # measured line
    top_h = surface_top(phi, G, xs[::10], zc[::10])
    base = np.interp(xs[j], xs[::10], top_h)
    rise = np.maximum(tc[j] - base, 0.0)
    D += rise * prof * ramp * top
    curves['crest'] = np.column_stack([xs, np.interp(xs, xs[::10], top_h), zc])
    # ---- the eye: the side swollen round it, the canthus lobe over its front, the supraocular ridge
    eg = eye_geometry(spec)
    C, a = eg['C'], eg['a']
    rel = P - C
    along = rel @ a
    lat = rel - along[:, None] * a
    rad = np.linalg.norm(lat, axis=1)
    sw = st['swell']
    ann = np.exp(-0.5 * (rad / sw['r']) ** 2)                      # a smooth dome about the eye's axis
    below = 1.0 + (sw['below'] - 1.0) * smooth01(-(P[:, 1] - C[1]) / 2.0 + 0.5)
    behind = 1.0 + (sw['behind'] - 1.0) * smooth01(-(P[:, 2] - C[2]) / 2.0 + 0.5)
    outward = smooth01((P[:, 0] - 5.5) / 1.5)
    D += sw['height'] * ann * below * behind * outward
    ca = st['canthus']
    cz, ch = ca['centre']
    lobe = np.exp(-0.5 * (((P[:, 2] - cz) / ca['half'][0]) ** 2 + ((P[:, 1] - ch) / ca['half'][1]) ** 2))
    D += ca['height'] * lobe * smooth01((P[:, 0] - 6.5) / 1.0)
    sp = st['supra']
    spts = np.array(sp['points'])
    sg = np.linspace(0.0, 1.0, 200)
    from scipy.interpolate import CubicSpline
    cs = CubicSpline(np.linspace(0, 1, len(spts)), spts, axis=0)
    curve = cs(sg)
    curve[:, 0] = surface_x(phi, G, curve[:, 1], curve[:, 2])
    dr, js = cKDTree(curve).query(P)
    ends = smooth01(np.minimum(sg[js], 1.0 - sg[js]) * 6.0)
    D += sp['height'] * np.exp(-0.5 * (dr / sp['width']) ** 2) * ends
    curves['supra'] = curve
    # ---- B3d: the frontal ridge across the frons top (M1d's transverse raised margin; B3c's midline pin left a nub)
    fr = st['frons']
    wfx = 1.0 - smooth01((P[:, 0] - fr['x0']) / fr['fade'])
    D += fr['height'] * np.exp(-0.5 * ((P[:, 2] - fr['z']) / fr['half']) ** 2) * wfx * top
    # ---- B3d: the raised front and lateral margins (M1d, c03): a lip just inside M1d's outline on the upper surface,
    # from the front margin back along the anterior angles, fading out behind z_back
    mg = st['margin']
    img_, lo_, res_ = poly_raster(dorsal_poly(), (-12.0, -12.5), (12.0, 3.0), 0.02)
    dpl = raster_at(img_, lo_, res_, P[:, 0], P[:, 2])           # the plan distance to M1d's outline (- inside)
    wzb = smooth01((P[:, 2] - mg['z_back']) / mg['fade'])
    upper = smooth01((np.clip(gy, -1.0, 1.0) + 0.1) / 0.5)
    D += mg['height'] * np.exp(-0.5 * ((dpl + mg['inset']) / mg['width']) ** 2) * wzb * upper
    # ---- B3d: the mentum's surroundings recessed (M3v's trapezoid plate then steps out of the underside, below)
    mt = st['mentum']
    tr = np.array(mt['trap'], np.float64)
    tpoly = np.vstack([tr, tr[::-1] * np.array([-1.0, 1.0])])
    img_m, lo_m, res_m = poly_raster(tpoly, (-7.0, -7.0), (7.0, 1.5), 0.02)
    dm_b = raster_at(img_m, lo_m, res_m, P[:, 0], P[:, 2])
    lower = smooth01((-np.clip(gy, -1.0, 1.0) - 0.3) / 0.4)
    D -= mt['recess'] * (1.0 - smooth01(dm_b / mt['recess_w'])) * (dm_b > -0.05) * lower
    out = phi.copy()
    out[idx] = (phi[idx] - D).astype(np.float32)
    # ---- the orbit: the capsule closed over the whole dome (its socket's margin), then opened round the eye along
    # M1l's outline on the dome (the cone from the dome's centre through the rim), so the eye shell sits in it
    ob = st['orbit']
    out[idx] = smin(out[idx], np.linalg.norm(P - C, axis=1) - (eg['R'] + ob['collar']), ob['collar_k']).astype(
        np.float32)
    EO = eye_outline(spec)
    # (B3c check 10-22) M1l's outline runs past the dome's lateral disc at its back-under corner (6 of the rim's 240
    # samples, z -4.99 .. -4.92, h 10.70-10.81, by up to 0.023 mm): those rim samples have no dome point and were dropped,
    # so the angular distance that sets the opening's depth was measured there to rim points far away, and the carve cut a
    # hard groove behind and under the eye (the crease: 0.43 mm deep at z -5.2, 0.22 at z -6.0, 0.65 in the section at
    # h 10.56). The outline is clipped radially to the disc (orbit rim_clip x R) before the rim and the cone are built
    # (probes beetle/scratch_b3ccheck/k05 / k09: the crease behind the eye gone, the exposed outline -0.004 / -0.003)
    r_ = np.hypot(EO[:, 0] - C[2], EO[:, 1] - C[1])
    k_ = np.minimum(1.0, ob['rim_clip'] * eg['R'] / np.maximum(r_, 1e-9))
    EO = np.column_stack([C[2] + (EO[:, 0] - C[2]) * k_, C[1] + (EO[:, 1] - C[1]) * k_])
    path = Path(EO)
    near = np.linalg.norm(P - C, axis=1) < eg['R'] + 3.5
    Pn = P[near]
    v = Pn - C
    vn = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
    on = C + eg['R'] * vn                                           # the point's direction on the dome
    inside = path.contains_points(np.column_stack([on[:, 2], on[:, 1]])) & (vn @ a > 0.15) & \
        (np.linalg.norm(v, axis=1) > 0.8 * eg['R'])                # (the cone opened only near and beyond the dome)
    rim = []
    for zq, hq in smooth_closed(EO, 240, 1.0):                     # the rim on the dome's outer side
        dz_, dh_ = zq - C[2], hq - C[1]
        rx = eg['R'] ** 2 - dz_ ** 2 - dh_ ** 2
        if rx > 0:
            rim.append(C + np.array([np.sqrt(rx), dh_, dz_]))
    rim = np.array(rim)
    rimn = (rim - C) / np.linalg.norm(rim - C, axis=1, keepdims=True)
    chord, _ = cKDTree(rimn).query(vn)                              # the angular distance to the rim, as a chord
    ang = 2.0 * np.arcsin(np.minimum(0.5 * chord, 1.0))
    dist = np.linalg.norm(v, axis=1) * np.sin(np.minimum(ang, 0.5 * np.pi))
    cav = np.where(inside, -dist, dist)                             # the cavity's signed distance (negative inside)
    sel = tuple(a_[near] for a_ in idx)
    # B3d: the orbit's RAISED RIM just outside the opening (M1l: the eye sits in a socket with a rim; B3c's eye a ball
    # proud of a near-vertical wall with a thin collar)
    rr = st['rim']
    rimd = np.where(inside, 0.0, rr['height'] * np.exp(-0.5 * ((dist - rr['out']) / rr['width']) ** 2))
    out[sel] = (out[sel] - rimd).astype(np.float32)
    out[sel] = smax(out[sel], -cav, st['orbit']['k']).astype(np.float32)
    curves['orbit_rim'] = rim
    # ---- the plates: the clypeal process and the mentum, ellipsoids (iq's bound-corrected estimate; the exact distance
    # follows) smooth-unioned
    for nm in ('clypeus',):
        pl = st[nm]
        c = np.array(pl['c'])
        R = np.eye(3)
        if 'pitch' in pl:
            t_ = np.radians(pl['pitch'])
            R = np.array([[1, 0, 0], [0, np.cos(t_), -np.sin(t_)], [0, np.sin(t_), np.cos(t_)]])
        q = (np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]) - c) @ R
        hb = np.array(pl['half'])
        k0 = np.linalg.norm(q / hb, axis=1)
        k1 = np.linalg.norm(q / hb ** 2, axis=1)
        sd = np.where(k1 > 1e-12, k0 * (k0 - 1.0) / np.maximum(k1, 1e-12), -hb.min())
        out = smin(out, sd.reshape(G.n).astype(np.float32), pl['k']).astype(np.float32)
    # B3d: the MENTUM a TRAPEZOID slab (M3v), its lower face on M1l's traced underside, its corners rounded by r
    dxz = raster_at(img_m, lo_m, res_m, X, Z)
    dy = np.abs(Y - (mt['low'] + 0.5 * mt['thick'])) - 0.5 * mt['thick']
    qx, qy = dxz + mt['r'], dy + mt['r']
    sd = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2) + np.minimum(np.maximum(qx, qy), 0.0) - mt['r']
    out = smin(out, sd.astype(np.float32), mt['k']).astype(np.float32)
    log(f'[hull] sculpt: {len(P):,} band voxels; the dish, the crest ({len(xs)} arc samples), the swollen side and the '
        f'canthus, the supraocular ridge, the orbit (M1l\'s rim, {len(rim)} points on the dome), the clypeal process '
        f'and the mentum')
    return out, curves


def surface_top(phi, G, xs, zs):
    """the surface's highest crossing at columns (x, z) (the first inside point from above, linear)"""
    from scipy import ndimage as nd
    ys = G.y[::-1]
    out = np.zeros(len(xs))
    for n_, (x, z) in enumerate(zip(xs, zs)):
        f = nd.map_coordinates(phi, [np.full(len(ys), (x - G.lo[0]) / G.h), (ys - G.lo[1]) / G.h,
                                     np.full(len(ys), (z - G.lo[2]) / G.h)], order=1, mode='nearest')
        k = int(np.argmax(f < 0))
        out[n_] = ys[k] + G.h * f[k] / (f[k] - f[k - 1]) if k > 0 and f[k - 1] != f[k] else ys[k]
    return out


def surface_x(phi, G, hs, zs):
    """the surface's outermost crossing along +x at (h, z)"""
    from scipy import ndimage as nd
    xs = G.x[::-1]
    out = np.zeros(len(hs))
    for n_, (h, z) in enumerate(zip(hs, zs)):
        f = nd.map_coordinates(phi, [(xs - G.lo[0]) / G.h, np.full(len(xs), (h - G.lo[1]) / G.h),
                                     np.full(len(xs), (z - G.lo[2]) / G.h)], order=1, mode='nearest')
        k = int(np.argmax(f < 0))
        out[n_] = xs[k] + G.h * f[k] / (f[k] - f[k - 1]) if k > 0 and f[k - 1] != f[k] else xs[k]
    return out


# ============================================================================================ B3e: the mass, cached
MASS_KEYS = ('box_lo', 'box_hi', 'h_A', 'h_B', 'steps_A', 'dt_A', 'reinit_A', 'steps_B', 'dt_B', 'reinit_B', 'relax',
             'pressure_c', 'size_r', 'tol_dorsal', 'tol_lateral', 'pin_r', 'rim_r')


def head_mass(spec, log=print):
    """B3e: THE MASS alone (the lead: keep the hull + flow for the MASS): build_flow's phi on the x >= 0 half (index 0 the
    mirror plane) at BUILD h_B, cached on the hull's own inputs, so the FEATURES (CSG, below) iterate without the flow.
    Returns dict(phi, lo, h, errors (per stage and view), fronts (resid, scale))"""
    key = cache_key(dict(v='mass-b3d-3', dorsal=DORSAL, lateral=LATERAL, sec_wide=SEC_WIDE, sec=SEC,
                         build={k: BUILD[k] for k in MASS_KEYS}, fronts=FRONT_TABLES, eye=spec['eye'],
                         lm=spec['landmarks'], md=spec['mandible']))

    def build():
        R = build_flow(spec, log)
        G = R['grid']
        out = dict(phi=R['phi'].astype(np.float32), lo=G.lo, h=np.float64(G.h))
        for stage, E in R['errors'].items():
            for v, e in E.items():
                out[f'err_{stage}_{v}'] = np.array([e['n'], e['med'], e['p90'], e['max'], e['mean']])
        for nm, fr in R['fronts'].items():
            out[f'front_{nm}'] = np.array([fr['resid'], fr['scale']])
        return out
    return cached('beetle_head_mass', key, build, log)


# ============================================================================================ B3e: the FEATURES (CSG)
# The lead (B3e, 10-22): the wolf's method (hull + flow + gaussian strokes) makes SOFT TISSUE; HARD CHITIN needs its crisp
# features BY CONSTRUCTION. The hull + flow make the MASS (head_mass, unchanged); every FEATURE is CSG with SMALL FILLETS
# whose radii are MEASURED on the photographs' edge highlights (beetle/scratch_b03e/e03_fillets.py): the NHM rig's RING
# LIGHT, calibrated on M1l's compound eye (a sphere of SPEC eye.radius; its ring reflection 0.383 mm out: beta/2 17.6 deg),
# shows a rounded edge of radius r as two lines 2 r sin(beta/2) = 0.604 r apart; on every edge here the aligned strips
# (60-240 rows each, the rows' median) show ONE unresolved line, so each radius is bounded by the line's width (FWHM, the
# image blur removed: M1l 51 um, M1d 37 um) over 0.604 (or 0.747 with each line's own thickness):
#   front margin (M1d)      36 um -> r <= 0.060 (0.049)          lateral margins (M1d)  47-57 um -> <= 0.078-0.094
#   crest (M1d)             97-110 um -> r <= 0.16-0.18 (0.13-0.15) supraocular ridge (M1l) 39 um -> <= 0.065 (0.052)
#   pronotal carina (M1l)   62 um -> r <= 0.10 (0.083)
# and the edges seen IN PROFILE, a circle on the traced contour within +-0.12 mm of the corner: the crest's peaks (M1l)
# 0.13-0.20, the anterior knob (M1l) 0.15-0.18, the anterior angles in plan (M1d) 0.18-0.19, the head's hind corner (M1d)
# 0.12. Every convex radius below is the measured one; the concave fillets (the features' feet) are [E].
#
# THE TOP (dish, margins, anterior angles, crest, swellings, groove) is a HEIGHT FIELD U(x, z) on a plan raster: a RIM LOOP
# (FEAT rim, x >= 0, mirrored) carries each margin's crest line, its height, its inner wall's width, its outer face's angle
# and its convex radius; inside the loop the DISH floor (the rim's heights less dish_depth, solved harmonic, less a slight
# bowl) and the inner walls; outside, the outer faces; the SWELLINGS (elliptic caps) and the GROOVE (a V channel) on top;
# then every concave crease filleted by rolling a ball of foot_r UNDER the field from above (a grey CLOSING) and every
# convex crest rounded by rolling a ball of the rim's measured radius (a grey OPENING with a spherical structuring function:
# the exact rolling-ball rounding, not a blur). In 3D the head is the mass PLUS the block {h <= U} above the mass's widest
# line (inside a draft side, so the dorsal outline stays the mass's), MINUS everything above U inside the loop and in front
# of the front margin (the dish carved, the mass's front bevel cut back to the front margin's face).
# THE SIDES are 3D CSG: the SUPRAOCULAR RIDGE a swept rounded wedge (its upper face continuing the lateral margin's outer
# face, its lower face undercut toward the orbit), the CANTHUS a rounded plate over the eye's front, the GENA a convex
# ellipsoid behind and under the eye, the ORBIT a collar round the eye opened along M1l's exposed outline with a crisp rim.
FEAT = dict(
    h=0.05,            # the features' grid (mm): the mass (0.075) resampled onto it (cubic)
    blur=0.03,         # the exact distance's blur (mm; B3d's 0.12 rounded every edge past the measured radii): unblurred, the
    #                    medial-axis kinks set the GRID's proved divisor to 1.60 and the head's |grad| p1 to 0.53 (b03's
    #                    gate 0.6); at 0.03 (0.6 cells) the divisor is 1.215 and p1 0.650 (beetle/scratch_b03e/e07_divisor.py),
    #                    and a convex edge of radius r moves by ~blur^2 / 2r (0.009 mm at r 0.05): sub-grid creases round to
    #                    ~0.03-0.04, under the measured radii
    plan_res=0.0125,   # the height field's plan raster (mm)
    # the RIM LOOP, x >= 0, from the front margin's midline to the crest's midline: (x, z, crest h, the inner wall's width,
    # the outer face's angle deg, the convex radius). Positions: M1d's highlight lines (e03 aligned strips: the front margin
    # z -1.13 on the midline, -1.24 / -1.30 at |x| 0.7 / 1.2; the lateral margins at |x| 7.41, the mean of both sides, which
    # M1d's 0.4 mm axis offset splits into 7.60 / 7.23; the crest at |x| 3.8 -> 5.9, z -7.59 -> -7.40) and M1d's outline
    # (the anterior angle's lobe, its widest 8.73-8.81 at z -2.0, e05); heights: M1l's TRUE top silhouette (contour_s01c,
    # e05: the knob 15.33 at z -2.00, the notches 14.14 at -1.10 and 14.46 at -4.05, the crest rising 15.10 / 15.39 / 15.70
    # at -7.50 / -7.75 / -8.00), each crest point the silhouette's height at its z (the silhouette is the max over x; LATERAL
    # leaves the crest out); widths, angles [E] (M1d: the margins' smooth inner bands 0.35-0.6 mm wide, dark: steep; c03)
    # (B3f: the outer faces are arcs from the crest at the angle given (face_R): the front margin 58 and the lateral
    # margins 52 deg at the crest, steepening to 72-76 by the lip line; B3e's 60-73 were straight faces' angles)
    rim=((0.00, -1.13, 14.12, 0.50, 68.0, 0.05), (0.70, -1.24, 14.14, 0.50, 68.0, 0.05),
         (1.20, -1.30, 14.16, 0.50, 68.0, 0.05), (2.50, -1.24, 14.19, 0.55, 68.0, 0.05),
         (4.00, -1.16, 14.23, 0.60, 68.0, 0.05), (5.50, -1.08, 14.28, 0.60, 68.0, 0.05),
         (6.60, -1.02, 14.30, 0.50, 66.0, 0.06),
         (7.40, -1.18, 14.30, 0.50, 66.0, 0.10), (7.80, -1.50, 14.58, 0.65, 65.0, 0.15),
         (8.00, -1.75, 14.85, 0.80, 65.0, 0.15), (8.08, -2.00, 15.33, 0.85, 65.0, 0.15),
         (7.98, -2.40, 15.14, 0.80, 66.0, 0.15), (7.80, -2.85, 15.08, 0.60, 66.0, 0.10),
         (7.58, -3.25, 14.89, 0.35, 58.0, 0.06), (7.46, -3.60, 14.78, 0.35, 52.0, 0.06),
         (7.42, -3.90, 14.58, 0.35, 52.0, 0.06), (7.41, -4.10, 14.47, 0.35, 52.0, 0.06),
         (7.41, -4.70, 14.49, 0.35, 52.0, 0.06), (7.41, -5.30, 14.53, 0.35, 52.0, 0.06),
         (7.40, -5.90, 14.58, 0.35, 52.0, 0.06), (7.36, -6.50, 14.62, 0.35, 52.0, 0.06),
         (7.25, -6.90, 14.74, 0.35, 56.0, 0.08),
         (6.75, -7.25, 14.85, 0.40, 50.0, 0.10), (5.90, -7.40, 15.02, 0.40, 52.0, 0.07),
         (5.05, -7.50, 15.10, 0.40, 52.0, 0.07), (4.20, -7.55, 15.16, 0.40, 52.0, 0.07),
         (3.40, -7.62, 15.25, 0.45, 48.0, 0.09), (2.60, -7.74, 15.38, 0.50, 45.0, 0.11),
         (1.80, -7.88, 15.55, 0.55, 45.0, 0.11), (1.00, -7.98, 15.68, 0.60, 45.0, 0.11),
         (0.00, -8.04, 15.70, 0.60, 45.0, 0.11)),
    #    (B3f: the crest's opening 0.13 -> 0.11, inside its bound 0.16-0.18 with margin: the lobes now stand behind it, its
    #    back face meets them higher and the crest turns less, fitted 0.12-0.17 at b3f-1 against B3e's 0.12-0.13;
    #    b3f-6: its lateral half (|x| 3.4-5.9) 0.07-0.09 with a 48-52 deg back face, where the lobes fall away: at 0.11 /
    #    45 deg the apex turned 74 deg only and was rounder than the inner wall's cell-face kinks, which the r01 rule then
    #    picked (x 4.8: 0.60 there, 0.106 at the apex; f10))
    dish_depth=0.30,   # [E] the dish's floor under the rim (M1l cannot see it; M1d's margin bands read dark, steep, over
    #                    0.35-0.6 mm: gated by the renders beside c03). (Tried 10-22: 0.12 with the bowl 0.40, a bowl
    #                    meeting the walls shallow: the transverse floor runs stayed 2.4-3.5 mm flat within 0.01, the
    #                    anisotropic bowl varies along z, e06 _q11)
    bowl=0.15,         # [E] the floor's centre lower still (a dish, not a flat tray: P3's front margin's middle 0.3-1.0 mm
    #                    under the anterior angles, c03's concave face)
    bowl_x=((-1.2, 0.15), (-3.0, 0.40), (-5.0, 0.55), (-7.0, 0.65), (-8.0, 0.65)),   # [E] (z, depth): the floor
    #                    concave ACROSS too, its midline this much under its sides (x 7.4): the harmonic floor alone domes
    #                    across toward the crest's high middle (e06 _q5: 14.84 on the midline, 14.35 at x 7, z -6)
    # the CLYPEAL PROCESS's top, ahead of the front margin between the mandibles (DORSAL's front: the lobes fp_L / fp_R, the
    # notch on the midline, its sides to the mandibles' inner bases): (z, h) along it, LATERAL's front rows (0.70, 13.85),
    # (0.20, 14.15) under the front margin's crest; its plan outline's half (x, z)
    clypeus_top=((-1.13, 14.12), (-0.55, 14.08), (0.20, 13.98), (0.70, 13.82)),
    clypeus_plan=((0.00, 0.00), (0.45, 0.38), (1.05, 0.66), (1.55, 0.70), (1.95, 0.05), (2.45, -0.45), (2.45, -1.70),
                  (0.00, -1.70)),
    # b3e-4 (the B3e check, 10-26): the process's UNDERSIDE, M1l's (LATERAL's rows (0.70, 13.25) -> (0.15, 12.85): the
    # plate's lower front edge, then the face set back under it), (z, h): in front of the front margin over the process
    # the top's block stands only above it and the face under it stays the mass's (features)
    clypeus_floor=((0.15, 12.85), (0.70, 13.25)),
    out_bend=1.5,      # [E] the outer faces steepen away from the crest: O(d) = d tan(angle) + out_bend d^2 (curved faces)
    foot_r=0.10,       # [E] the concave fillets (the closing's ball): the features' feet, the groove's floor, the valleys
    mand_skin=None,    # B3f: off (the lead: the mandible-base covers lowered or shortened so the floor does not rise over them:
    #                    heads/insect.py MAND base_dive dives the hidden base under the front margin, its top under the bowl's
    #                    floor by >= 0.1, so no cover is needed). B3e:
    #                    [E] b3e-2: the head's skin over each mandible base's top inside the dish (features, mandible_top):
    #                    the bases' tops stand 14.1-14.2 at |x| 4.5-5.5 behind the front margin's crest (14.23-14.28,
    #                    M1l's mandible base 14.18 at z -1.10), so the floor there stays under the crest
    skin_fall=30.0, skin_sigma=0.06, skin_k=0.10,   # [E] b3e-5 (the B3e check, 10-26): that cover FAIRED into the floor
    #                    (mandible_top): it falls away from the base no steeper than skin_fall (deg; a cone dilation),
    #                    smoothed by a gaussian of skin_sigma (mm), and meets the floor in a smooth max of width skin_k
    #                    (mm). b3e-2..4: the raw scan (0.02 mm terraces) by the nearest cell and a hard max left a rough
    #                    oval lump whose rear edge fell 0.27 mm within 0.1 mm: a dark slit from above (e16, r06)
    # the SWELLINGS (M1d: paired dark rounded humps behind the crest either side of the midline groove, |x| 0.5-3.4, z -7.9 ..
    # -9.2; M1l: the silhouette's top 16.03 at z -8.60, 16.00 at -8.75, 15.50 at -9.00 behind, 15.72 at -8.25 in front): an
    # elliptic hump (|x| centre, z centre, half-widths outward / inward to the midline's saddle, half-lengths ahead / behind,
    # its height over its base, its top): the base under the mass, so its back falls steeply but continuously into the
    # neck (M1l: 77 deg between z -9.00 and -9.25), not off a cap's vertical edge; the half-lengths solved on M1l's heights
    # at z -8.25, -8.75 and -9.00
    swell=dict(x=2.20, z=-8.58, a_out=2.40, a_in=4.00, b_front=0.675, b_back=0.67, cap=2.43, top=16.03),
    # the GROOVE (M1d: a dark line on the midline from z -7.1 to -9.35, 0.15-0.25 mm wide): a V channel, its walls' angle
    # (75: 0.29 mm wide at the swellings' saddle), its floor's height [E], its ends (it fades over `fade`), its edges' convex
    # radius (the margins' class)
    groove=dict(z=(-7.30, -9.30), floor=15.05, wall=80.0, fade=0.30, r=0.05),   # (B3f: 80 deg, the broad lobes stand
    #                                                                             0.7 over its floor: 0.26 mm wide at the top,
    #                                                                             M1d's dark line 0.15-0.25)
    # the block's DRAFT side: from its base line (the mass's widest line, or M1d's outline less `draft_in` where the mass
    # stands inside it: the anterior angles, the flow's dorsal error) it leans inward by draft_c1 (h - hw) + draft_c2
    # (h - hw)^2 (a convex shoulder, no flat wall)
    draft_in=0.05, draft_c1=0.05, draft_c2=0.03, draft_cb=0.50,   # (tried 10-22: c2 0.12 for a rounder side cut the
    #                                                                 lateral margins' tops, the side silhouette 0.3-0.6 mm
    #                                                                 under M1l's at z -2 .. -6, e06 _q11)
    # the SUPRAOCULAR RIDGE (M1l: the crisp line BEHIND the eye from (z -5.35, h 13.4) up to (z -7.05, h 13.97), e03's
    # aligned strip, rising to the crest's lateral end; M1d: the band outside the lateral margin, the ridge at |x| 7.55-7.75
    # behind the eye): the convex EDGE where the lateral margin's outer face (the rim's angles 72-80 there, set so it meets
    # the draft side on M1l's line: the side under it is the block's convex draft, no undercut, M1l shows the gena convex
    # under the line) meets the block's draft side, rounded in 3D by ridge_r (z, r): the measured 0.05 along M1l's line; over
    # the eye the orbit's convex upper wall (no line on M1l: 0.25 [E]); the anterior angle's lateral edge the knob's 0.15
    ridge_r=((-0.5, 0.15), (-3.0, 0.15), (-3.4, 0.25), (-4.8, 0.25), (-5.2, 0.10), (-7.0, 0.10), (-7.4, 0.10),
             (-11.0, 0.10)),
    # the supraocular LIP behind the eye on that edge (the U / draft edge alone turns 15-20 deg: no line, e06 _q7): a swept
    # wedge on M1l's line (path (h, z)), its apex `proud` outside the draft side there, its upper face at `up` (it meets the
    # margin's steeper outer face above in a filleted crease), its lower face undercut at `down` (the apex turns ~60 deg:
    # M1l's strong line), its convex radius (measured), bounded within `reach`, blended by k, its ends retreating over
    # `ends` mm [E: proud, the angles]
    supra=dict(path=((13.38, -5.00), (13.58, -5.55), (13.62, -6.00), (13.64, -6.40), (13.74, -6.75), (13.97, -7.05),
                     (14.25, -7.25)),
               proud=0.15, up=62.0, down=45.0, r=0.05, reach=0.45, k=0.08, ends=0.40),
    # the CANTHUS (M1d: the plate over the eye's front, its lateral edge M1d's outline from (8.60, -2.5) to (8.29, -3.25);
    # M1l: in front of the eye, h 10.85-12.95): a PLATE, its outline in its own plane a rounded rectangle (corner radius
    # `corner`), centre (x, h, z), half extents (across, up, half-thickness), its normal in plan (deg off forward toward +x),
    # its edges' radius (the margins' class), its blend [E]
    canthus=dict(c=(8.00, 11.92, -2.92), half=(0.45, 1.05, 0.14), corner=0.35, turn=22.0, r=0.05, k=0.12),
    # the GENA (M1l: the side behind and under the eye convex; B3c's check: 1.3-2.0 mm flat runs there): an ellipsoid inside
    # M1d's outline behind the eye (head_post 7.94 at z -5.94), its blend [E]
    gena=dict(c=(6.80, 10.40, -6.00), half=(0.90, 1.55, 1.70), k=0.50),
    # the ORBIT: the capsule raised round the eye as a COLLAR (the dome's sphere grown by `collar`, within `band` mm of the
    # opening), blended in by collar_k, then opened along M1l's exposed outline (the cone from the dome's centre) with a
    # crisp rim (rim_r: the margins' class) [E: collar, band]
    orbit=dict(collar=0.18, band=0.90, band_r=0.30, collar_k=0.15, rim_r=0.05, rim_clip=0.995),
    # ======================================================================== B3f (the lead, 10-27: every surface curved)
    # The B3e head made the EDGES crisp; the SURFACES between them stayed planar where nothing curved them (the dish's
    # floor a plane, the walls under the margins DORSAL's outline extruded, the clypeal process's walls vertical). B3f
    # curves every surface by construction, the edges kept crisp (their fitted radius rides on the TURNING angle at the
    # edge: beetle/scratch_b03f/f04_edge_calib.py, the GRID chain at 0.05 mm with the 0.03 blur fits a perfect crest of
    # 107-126 deg at 0.043-0.057 over +-0.06 mm of arc, of 73 deg at 0.09-0.10, of 60 deg at 0.12-0.14, whatever its built
    # radius: an edge reads crisp only if it turns ~95 deg or more).
    # THE FLOOR: a BOWL curving both ways (B3e: harmonic in the rim + a torsion bowl, flat within 0.01 mm over 1.9-3.4 mm
    # across): a paraboloid with a tilt toward the crest, h0 + kx x^2 + kz (z - zc)^2 + tz (z - zc) [E: the rims bound it
    # (it stays under the front margin by >= min_drop and under the lateral margins), M1d's ring highlights bound its
    # slopes to <= 17 deg, no photo gives its section], kept min_drop under the nearest rim crest (a smooth min of width k)
    bowl3=dict(h0=13.42, zc=-4.30, kx=0.016, kx_front=0.010, kz=0.064, tz=-0.060, min_drop=0.25, k=0.15, soft_lam=0.20,
               soft_mu=0.10),
    #                  (kx, the curvature across, eases to kx_front at the front margin, which stands nearly level across
    #                  (14.12-14.28 over |x| 0-5.5) where the lateral margins stand 0.3-0.4 higher: b3f-1's uniform 0.012 met
    #                  the front margin's min_drop clip at |x| 3-5, a 4 mm flat run along it, f05 _f1)
    #                  (b3f-12, the B3f check: the clip's crest a SOFT-MIN over the loop's crests weighted by their distance
    #                  over the nearest one's, soft_crest: weights exp(-(d - d_min) / soft_lam), temperature soft_mu. b3f-1..11
    #                  clipped under the NEAREST loop point's crest, which jumps across the loop's medial axis (each corner's
    #                  bisector: the front margin's 14.1-14.3 against the anterior angle's 14.6-15.3, the lateral margin's
    #                  14.6 against the crest's 14.85-15.0), so wherever the clip held the bowl the floor jumped by up to 0.13
    #                  mm there: a crease 1-1.5 mm long into the dish from each of its four corners, which M1d does not show
    #                  (its margins curve smoothly into the crest: beetle/scratch_b3fcheck/k05_m1d_postcorner.png). The
    #                  soft-min floor jumps by <= 0.008 mm, stays >= 0.20 under the nearest crest and differs from b3f-11's by
    #                  > 0.02 mm over 3 % of the floor: beetle/scratch_b3fcheck/k04_floor.py)
    wall_p=3.0,        # the inner walls U = F + (H - F)(1 - t)^p over their measured widths (B3e p 2: C1 at the foot, its
    #                    curvature jumping from 1 / 0.42 mm to the floor's at a crisp foot line, the tray's look; p 3: C2,
    #                    the wall steeper at the crest (the crest turns ~125 deg) and curving into the bowl with no foot line)
    wall_p_front=4.0,  # the front margin's inner wall steeper still (with its outer face at 68 deg the crest turns ~138 deg:
    #                    f04 'steep' fits 130-140 deg at 0.041-0.048 over +-0.06 mm, the photo's <= 0.060; b3f-1 at ~122 deg
    #                    fitted 0.057-0.065)
    # THE OUTER FACES: convex ARCS (B3e: d tan(angle) + out_bend d^2, steep faces nearly straight in section, the walls
    # under the margins flat): from the crest at the rim's angle the face steepens along an arc of radius face_R (its
    # section curved everywhere, the curvature 1 / face_R), vertical by do = face_R (1 - sin angle), then a cliff
    face_R=2.6,
    fT_slope=86.0,     # b3f-12 (the B3f check, 10-27): the block's top field fT = (h - U) / sqrt(1 + |grad U|^2) takes |grad U|
    #                    at most tan(fT_slope) (the steepest face U builds, the outer faces' cliff). Where U STEPS (the lobes'
    #                    switches to the -1e3 sentinel: past the shoulder where T_r <= hl + 0.2, and behind the lobes at |x| =
    #                    x_sh) np.gradient spiked to ~1e3 and fT collapsed to ~0 along a thin vertical sheet at every height,
    #                    which the smooth union with the mass (foot_r) raised into lines on the head: two ridges at x +-1.90
    #                    behind the lobes (z -9.7 .. -10.4, 14-29 um) and a row of BEADS 0.05 mm apart (the features' grid)
    #                    along the lobes' rear boundary (z -9.25 .. -9.55, |x| 2.2-5.6, 20-39 um), seen from behind-above
    #                    beside the pronotum (beetle/scratch_b3fcheck/k02_back_f11.png, k03_ctx_b3f.png). The zero set h = U
    #                    is unchanged by the normalisation, so the head's shape is too
    # THE SIDES (the lead: the walls under the margins CONVEX, the gena convex behind and below the eye with no crease
    # where it meets the wall): the block's draft (B3e: near vertical from the mass's widest line up to the margins, flat
    # within 0.01 mm over 1.0-1.8 mm at h 10.6-13.7) is now a CIRCLE in each transverse section, radius R, vertical at
    # (Wd, hw_side): the mass's own side, round below its widest line (radius 1.3-2.5: beetle/scratch_b03f/f06), meets it
    # near-tangentially where both are near vertical (hw_side = the mass's hw + up: the crossing ~0.4 over the mass's hw),
    # so the gena needs no ellipsoid (B3e's gena, smin'd at k 0.5, left the crease from under the eye). (z, value) tables
    side=dict(R=((-0.8, 2.6), (-7.2, 2.6), (-8.0, 2.8), (-11.5, 2.8)),
              up=((-0.8, 0.0), (-11.5, 0.0))),
    #                  (b3f-1 stood the circle 0.8-1.4 over the mass's widest line: the two met near vertical over 0.8-1.3
    #                  mm, runs flat within 0.01 mm over 1.0-1.35 mm at h 11.7-12.0, f05 _f1; b3f-2: SEC_WIDE raised, the
    #                  circle starts AT the mass's widest line, the block's bottom there: above it the circle (radius R),
    #                  below it the mass's own round gena, one tangent, no flat band, no crease)
    # THE SUPRAOCULAR LIP (M1l's crisp line from over the eye to the crest's lateral end; BEETLE_BODY_PHOTOS 7b: r <= 0.065):
    # the circle cannot reach the lateral margin's crest (0.5 mm inside the widest line, 3 mm above it) and stay convex, so
    # above the LIP LINE the side is released to the margin's outer face (the arc), and under it a SHELF: the underside
    # plane through the apex (where the outer face reaches the line), inclined beta inward-down, its cove into the circle
    # filleted at r_cove; the apex rounded by r (the line: the B3e path (e03's strip behind the eye) and, over the eye, M1l
    # read again on beetle/scratch_b03f/f02_m1l_ridge.png: 13.99 at z -4.0); active between z_on and z_off, faded over fade
    lip=dict(path=((-3.30, 14.20), (-4.00, 13.97), (-4.60, 13.70), (-5.00, 13.52), (-5.55, 13.58), (-6.00, 13.62),
                   (-6.40, 13.64), (-6.75, 13.74), (-7.05, 13.97), (-7.25, 14.25), (-7.45, 14.55)),
             beta=-10.0, r=0.03, r_cove=0.30, z_on=-3.25, z_off=-7.95, z_back=-7.10, fade=0.30, fade_on=0.30),
    #        (b3f-6: z_off -7.65 -> -7.95, so the lip's release holds until the back zone's is complete.
    #        b3f-9: z_back -7.40 -> -7.10: just behind the crest's lateral run (z -7.3 .. -7.45, |x| 6.0-7.1) the lip's
    #        plane stood over the circle's top there, and U over both, so the band between them was neither: a slot 0.15-0.2
    #        wide, 0.3 tall, a tunnel under the crest's lateral end opening at the side (f07 _f8, f16); the circle now
    #        released from z -7.10. The lip's cove 0.12 -> 0.30 (the field's |grad| 0.30-0.48 outside in it, the head's p1
    #        0.589 at b3f-8, f17). fade_on: the lip's onset and the anterior raise's end; 0.6 rounded the lateral margin
    #        off at z -3.6, b3f-9)
    #        (b3f-3: the release reaches past the crest's lateral end, z_off -7.65, and behind z_back the side circle is
    #        released too, the lobes' dome falling to the side line there)
    #        (beta < 0: the underside rises inward a little, a drip edge, so the apex turns ~115 deg (the outer face's arc
    #        arrives at ~74 deg): f04 'steep' fits 111-120 deg at 0.047-0.054 over +-0.06 mm; b3f-1's +5 deg (~100 deg) fitted
    #        0.062-0.082)
    # THE LOBES behind the crest (the lead: BROAD and DOMED, filling the back from the crest to the neck, to |x| 5.5-6, the
    # midline groove between; their height M1l's top line): each lobe a transverse dome, its ridge along x at z_top(x) (M1l's
    # top 16.03 at z -8.60, curving forward laterally behind the crest's arc), its height P(x) (the top at |x| 1.4-3.0 where
    # M1d's glossy highlights lie, 1.3-3.6; falling to the groove and out to |x| 5.5-6), its section along z the parabola
    # through M1l's top line (15.72 at z -8.25, 16.03 at -8.60, 15.50 at -9.00, 14.43 at -9.25: front curvature c_f, back
    # c_b; the ridge's radius 1 / 2c 0.14-0.20, M1l's knob over the lobes 0.15-0.18), the front broadening laterally (c_f
    # falling to c_f_out) so the lobe rises straight from the crest's back there
    lobe=dict(P=((0.20, 15.78), (0.80, 15.95), (1.40, 16.03), (3.00, 16.03)), x_sh=1.9,
              z_top=(-8.60, 0.45, 2.6, 2.9), c_f=2.5, c_f_out=1.3, c_b=3.6, fall=0.0),
    #         (b3f-8: the shoulder x_sh 3.0 -> 1.9, the plain ellipse (fall 0): at |x| 4.8 the lobe stands >= 0.2 under the
    #         crest beside it, so the crest stays an edge, and the flank is convex everywhere; b3f-5..7's (1 - 0.9 s^2)
    #         fall-off had an inflection whose straight stretch ran flat within 0.01 mm over 1.5-1.9 mm at z -8.2 .. -8.7.
    #         A gaussian trough behind the crest instead cut a slit and left a ledge mid-crest, f07 _f4)
    #         (b3f-3: past the shoulder x_sh each transverse section of the lobe a quarter ellipse down to the block's side
    #         line (Wd, the mass's hw), vertical there: the back of the head one dome over the mass's round gena; it stands
    #         ~15.3 at |x| 5.5, ~14.9 at 6.0 on the ridge (M1d's lobes reach |x| 5.5-6); b3f-1/2's P table fell to 15.0 at 5.6)
    # THE CLYPEAL PROCESS (the lead: a clean ROUNDED front, no vertical polygon walls): a rounded PLATE, its plan the
    # process's outline (clypeus_plan: DORSAL's lobes and notch to the mandibles' inner bases) offset in by its edge radius,
    # its top proc_top (B3f: under the front margin's crest, so the margin turns as a crest there too: B3e's top at the
    # crest's height made the front margin a 50 deg bend at the midline, fitted 0.08-0.13; c08 shows the margin's outer face
    # falling to the process), its underside M1l's (clypeus_floor), every edge rounded by r (half its thickness at most: the
    # front a rounded profile), blended in by k; the head's top over it cut to its top
    process=dict(top=((-1.13, 13.86), (-0.55, 13.88), (0.20, 13.84), (0.70, 13.72)), r=0.22, k=0.10, plan_smooth=6.0,
                 back=-1.40),
    # THE MENTUM (the lead: part of the underside's surface as M3v / c08 show it, not a proud bevelled tile; M3v: a broad
    # punctate plate flush with the genae, bounded by sutures, its front edge raised): the underside itself, a SUTURE (a
    # rounded groove `suture_d` deep, `suture_w` half-wide) along M3v's trapezoid (STROKES mentum trap), the plate inside it
    # bulging `bulge` at most (rising over `bulge_w` from the suture), its front edge a transverse roll `front` high
    mentum3=dict(suture_d=0.06, suture_w=0.10, bulge=0.06, bulge_w=0.70, front=0.06, front_w=0.25, band=0.9),
)


def smin_c(a, b, r):
    """the CIRCULAR smooth union: two distance fields joined by a circular fillet of radius r (exact for orthogonal
    planes); r 0 the hard union"""
    if r <= 0.0:
        return np.minimum(a, b)
    u = np.maximum(r - a, 0.0)
    v = np.maximum(r - b, 0.0)
    return np.maximum(r, np.minimum(a, b)) - np.sqrt(u * u + v * v)


def smax_c(a, b, r):
    return -smin_c(-a, -b, r)


def ball(r, res):
    """a spherical structuring function on its disk footprint: sqrt(r^2 - t^2) (mm), the footprint"""
    n = int(np.ceil(r / res))
    t = np.arange(-n, n + 1) * res
    T2 = t[:, None] ** 2 + t[None, :] ** 2
    fp = T2 <= r * r + 1e-12
    return np.where(fp, np.sqrt(np.maximum(r * r - T2, 0.0)), 0.0), fp


def roll_open(U, r, res):
    """the convex crests rounded to radius r: a ball of radius r rolled UNDER the graph (grey opening, spherical)"""
    from scipy import ndimage as nd
    s, fp = ball(r, res)
    return nd.grey_dilation(nd.grey_erosion(U, footprint=fp, structure=s), footprint=fp, structure=s)


def roll_close(U, r, res):
    """the concave creases filleted to radius r: a ball of radius r rolled OVER the graph (grey closing, spherical)"""
    from scipy import ndimage as nd
    s, fp = ball(r, res)
    return nd.grey_erosion(nd.grey_dilation(U, footprint=fp, structure=s), footprint=fp, structure=s)


def rim_dense(step=0.005):
    """the rim loop resampled along its plan arc every `step` mm: points (x, z), and per point (h, width, angle, r);
    the closed loop: the x >= 0 run then its mirror back"""
    R = np.array(FEAT['rim'], np.float64)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(R[:, :2], axis=0), axis=1))])
    t = np.arange(0.0, s[-1] + 1e-9, step)
    from scipy.interpolate import PchipInterpolator
    P = np.column_stack([PchipInterpolator(s, R[:, k])(t) for k in range(R.shape[1])])
    half = P
    other = P[-2:0:-1].copy()
    other[:, 0] *= -1.0
    return np.vstack([half, other])


def soft_crest(loop, lo, hi, X, Z, lam, mu, res=0.05, every=10):
    """b3f-12 (the B3f check, 10-27): the rim's crest height seen from each plan point as a SOFT-MIN over the loop's points
    weighted by their distance over the nearest one's: w = exp(-(d - d_min) / lam), H_s = H_0 - mu ln(sum w exp(-(H - H_0)
    / mu) / sum w). Continuous across the loop's medial axis, where the nearest point's own crest jumps, and biased toward
    the lower of two nearby crests (the floor stays under both). On a `res` mm raster over the loop's points every
    `every` samples, read bilinearly at (X, Z)"""
    from scipy import ndimage as nd
    from scipy.spatial import cKDTree
    xs = np.arange(lo[0], hi[0] + res, res)
    zs = np.arange(lo[1], hi[1] + res, res)
    XX, ZZ = np.meshgrid(xs, zs, indexing='ij')
    P = np.column_stack([XX.ravel(), ZZ.ravel()])
    dmin, _ = cKDTree(loop[:, :2]).query(P)
    L2 = loop[::every]
    H0 = float(L2[:, 2].min())
    eH = np.exp(-(L2[:, 2] - H0) / mu)
    out = np.empty(len(P))
    for a in range(0, len(P), 20000):
        D = np.linalg.norm(P[a:a + 20000, None, :] - L2[None, :, :2], axis=2)
        W = np.exp(-(D - dmin[a:a + 20000, None]) / lam)
        out[a:a + 20000] = H0 - mu * np.log((W * eH[None, :]).sum(1) / W.sum(1))
    Hr = out.reshape(XX.shape)
    return nd.map_coordinates(Hr, [(X - lo[0]) / res, (Z - lo[1]) / res], order=1, mode='nearest')


def top_field(log=print, mass=None):
    """THE TOP's height field (FEAT's block comment): U on the plan raster (full width), its gradient, the loop's signed
    distance (- inside), the front band's mask, the rim's nearest parameters. mass: (z, Wd, hw) per z, the block's side
    line (B3f: the lobes' dome reaches it). Returns dict"""
    from matplotlib.path import Path
    from scipy import ndimage as nd
    from scipy.spatial import cKDTree
    res = FEAT['plan_res']
    lo = np.array([-10.6, -11.6])
    hi = np.array([10.6, 1.9])
    nx, nz = (np.round((hi - lo) / res).astype(int) + 1)
    xs = lo[0] + np.arange(nx) * res
    zs = lo[1] + np.arange(nz) * res
    X, Z = np.meshgrid(xs, zs, indexing='ij')
    loop = rim_dense()
    ins = Path(loop[:, :2]).contains_points(np.column_stack([X.ravel(), Z.ravel()])).reshape(X.shape)
    d, j = cKDTree(loop[:, :2]).query(np.column_stack([X.ravel(), Z.ravel()]))
    d, j = d.reshape(X.shape), j.reshape(X.shape)
    sd = np.where(ins, -d, d)
    Hn, Wn, An, Rn = (loop[j, k] for k in (2, 3, 4, 5))
    # B3f: the dish's floor a BOWL (FEAT bowl3: a paraboloid with a tilt toward the crest, curving both ways everywhere),
    # kept min_drop under the nearest rim crest by a smooth min (B3e: harmonic in the rim + a torsion bowl, flat within
    # 0.01 mm over 1.9-3.4 mm across, the tray)
    bw = FEAT['bowl3']
    kx_ = bw['kx_front'] + (bw['kx'] - bw['kx_front']) * smooth01((-Z - 1.8) / 1.5)
    F0 = bw['h0'] + kx_ * X * X + bw['kz'] * (Z - bw['zc']) ** 2 + bw['tz'] * (Z - bw['zc'])
    # (b3f-12, the B3f check: under the SOFT-MIN of the nearby crests, soft_crest; b3f-11's nearest crest Hn jumps across
    # the loop's medial axis and creased the floor along the dish corners' bisectors, FEAT bowl3's comment)
    F = smin(F0, soft_crest(loop, lo, hi, X, Z, bw['soft_lam'], bw['soft_mu']) - bw['min_drop'], bw['k'])
    cin = ins
    # B3f: the LOBES behind the crest (FEAT lobe; B3e's swellings, elliptic caps 1.35 mm long reaching |x| 4.6 at their
    # base, read as two narrow rolls): transverse domes, the ridge along x at z_top(x), its height P(x), its section along
    # z a parabola (front c_f broadening to c_f_out laterally, back c_b); outside the loop only (the dish keeps its floor)
    from scipy.interpolate import PchipInterpolator
    lb = FEAT['lobe']
    ax = np.abs(X)
    zt0, zt_d, zt_x0, zt_w = lb['z_top']
    lat = smooth01((ax - zt_x0) / zt_w)
    z_top = zt0 + zt_d * lat
    Pt = np.array(lb['P'], np.float64)
    xsh = lb['x_sh']
    P_x = PchipInterpolator(Pt[:, 0], Pt[:, 1])(np.clip(ax, Pt[0, 0], xsh))     # the ridge's height, level past x_sh
    dzl = Z - z_top
    c_f = lb['c_f'] + (lb['c_f_out'] - lb['c_f']) * lat
    T_r = P_x - np.where(dzl > 0.0, c_f, lb['c_b']) * dzl * dzl                # the ridge's section along z, per x
    if mass is not None:
        # b3f-3: past the shoulder (x_sh) the lobe falls as a quarter ELLIPSE to the block's side line (Wd, hw) per z,
        # vertical there, where the mass's own round gena takes over: the back of the head one dome (b3f-2's circle side
        # cut the lobes' outer slopes and the crest's lateral end: its top stands at hw + R, under the lobes)
        zg_, Wd_, hw_ = mass
        Wl = np.interp(Z, zg_, Wd_)
        hl = np.interp(Z, zg_, hw_)
        s_e = np.clip((ax - xsh) / np.maximum(Wl - xsh, 0.5), 0.0, 1.0)
        # b3f-4: the quarter ellipse eased by (1 - fall s^2): level at the shoulder, vertical at the side line as before,
        # but falling off laterally (b3f-3's plain ellipse held 92 % of the lobe's height at |x| 4.8, so the lobe rose
        # straight from the crest's back there: the crest a ledge, fitted 0.40 against the photos' <= 0.18; M1d's lobes
        # glossy at |x| 1.5-4.5, dark (falling away) past 5)
        U_dm = hl + (T_r - hl) * np.sqrt(np.maximum(1.0 - s_e * s_e, 0.0)) * (1.0 - lb['fall'] * s_e * s_e)
        T_r = np.where(ax <= xsh, T_r, np.where((T_r > hl + 0.2) & (ax < Wl), U_dm, -1e3))
    U_sw = np.where(ins, -1e3, T_r)
    # (the clypeal process is a rounded plate of its own now, features(): no longer a top over its plan outline)
    # the groove: a V channel on the midline, its floor rising out at its ends
    gr = FEAT['groove']
    z0, z1 = gr['z']
    endw = np.clip(np.minimum(Z - z1, z0 - Z) / gr['fade'], 0.0, 1.0)
    U_g = np.where((Z < z0 + gr['fade']) & (Z > z1 - gr['fade']),
                   gr['floor'] + (1.0 - endw) * 5.0 + np.abs(X) * np.tan(np.radians(gr['wall'])), 1e3)
    radii = sorted(set([float(r) for r in np.array(FEAT['rim'])[:, 5]] + [gr['r']]))
    rq = np.where((np.abs(X) < 1.2) & (Z < z0 + 0.2) & (Z > z1 - 0.2), gr['r'], Rn)
    t = np.clip(-sd / Wn, 0.0, 1.0)
    do = np.maximum(sd, 0.0)
    # B3f: the outer faces ARCS (FEAT face_R): from the crest at the rim's angle An, steepening along an arc of radius face_R
    # (curved in section everywhere), vertical by do = face_R (1 - sin An), beyond it a cliff at 86 deg
    Rf = FEAT['face_R']
    sa, ca = np.sin(np.radians(An)), np.cos(np.radians(An))
    s86 = np.sin(np.radians(86.0))
    st_ = np.minimum(sa + do / Rf, s86)
    drop = Rf * (ca - np.sqrt(np.maximum(1.0 - st_ * st_, 0.0))) + np.maximum(do - Rf * (s86 - sa), 0.0) * np.tan(
        np.radians(86.0))
    # (the inner walls' exponent: wall_p_front along the front margin's run, the loop's points ahead of z -1.6 inside |x|
    # 7.0, eased; wall_p elsewhere)
    wf_ = smooth01((loop[j, 1] + 1.6) / 0.2) * (1.0 - smooth01((np.abs(loop[j, 0]) - 7.0) / 0.3))
    pw = FEAT['wall_p'] + (FEAT['wall_p_front'] - FEAT['wall_p']) * wf_

    def assemble(Hl):
        """U from the rim's build heights Hl: the inner walls into the bowl inside, the outer faces' arcs outside, the
        lobes, the groove; the closing; the openings at the rim's radii, blended"""
        Hn_ = Hl[j]
        U_ = np.where(ins, F + (Hn_ - F) * (1.0 - t) ** pw, Hn_ - drop)
        U_ = np.minimum(np.maximum(U_, U_sw), U_g)
        U_ = roll_close(U_, FEAT['foot_r'], res)
        out = np.zeros_like(U_)
        wsum = np.zeros_like(U_)
        for i, r in enumerate(radii):
            lo_r = radii[i - 1] if i else r - 1e-3
            hi_r = radii[i + 1] if i + 1 < len(radii) else r + 1e-3
            w = np.where(rq <= r, np.clip((rq - lo_r) / max(r - lo_r, 1e-9), 0.0, 1.0),
                         np.clip((hi_r - rq) / max(hi_r - r, 1e-9), 0.0, 1.0))
            if w.any():
                out += w * roll_open(U_, r, res)
                wsum += w
        return out / np.maximum(wsum, 1e-9)

    # the crests' heights compensated for the rounding: each rim point's rounded crest (the field's highest within 0.1 mm
    # of it) brought to its measured height in two passes (a ball of radius r lowers a crest of apex angle a by r (1 /
    # sin(a / 2) - 1), more at a peak along the rim: the knob)
    Hl = loop[:, 2].copy()
    fp = ball(0.10, res)[1]
    for it in range(2):
        U = assemble(Hl)
        Ud = nd.grey_dilation(U, footprint=fp)
        Ur = nd.map_coordinates(Ud, [(loop[:, 0] - lo[0]) / res, (loop[:, 1] - lo[1]) / res], order=1)
        dH = nd.gaussian_filter1d(loop[:, 2] - Ur, 8.0, mode='wrap')
        Hl = Hl + np.clip(dH, -0.2, 0.6)
    U = assemble(Hl)
    Ud = nd.grey_dilation(U, footprint=fp)
    Ur = nd.map_coordinates(Ud, [(loop[:, 0] - lo[0]) / res, (loop[:, 1] - lo[1]) / res], order=1)
    gx, gz = np.gradient(U, res)
    log(f'[hull] B3f top: plan raster {U.shape} at {res} mm; the rim loop {len(loop)} points; the floor a bowl over '
        f'{int(cin.sum())} cells; fillets: closing {FEAT["foot_r"]}, openings {radii}; the crests raised by '
        f'{np.median(Hl - loop[:, 2]):.3f} (max {np.max(Hl - loop[:, 2]):.3f}) to land within '
        f'{np.abs(Ur - loop[:, 2]).max():.3f} of the measured heights')
    return dict(U=U, gx=gx, gz=gz, sd=sd, lo=lo, res=res, xs=xs, zs=zs, loop=loop, F=F, H_build=Hl)


def dense_closed(P, step):
    """a closed polygon's boundary sampled every `step` (or closer)"""
    P = np.asarray(P, np.float64)
    out = []
    for a, b in zip(P, np.roll(P, -1, axis=0)):
        n = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        out.append(a + np.outer(np.arange(n) / n, b - a))
    return np.vstack(out)


def plan_at(field, T, X, Z):
    """a plan raster's value at plan points (bilinear, clamped)"""
    from scipy import ndimage as nd
    return nd.map_coordinates(field, [(X - T['lo'][0]) / T['res'], (Z - T['lo'][1]) / T['res']], order=1,
                              mode='nearest')


def mass_profile(phi, G, smooth=0.30):
    """the mass's widest line per z (x >= 0 half): its half-width W(z) (each row's zero crossing along x, linear: sub-voxel)
    and the height of that widest point hw(z), both smoothed along z over `smooth` mm (per-voxel values striped the block's
    draft side in vertical bands, e06 _q4)"""
    from scipy.ndimage import gaussian_filter1d
    W = np.full(G.n[2], np.nan)
    hw = np.full(G.n[2], np.nan)
    for k in range(G.n[2]):
        sl = phi[:, :, k]
        ins = sl < 0
        if not ins.any():
            continue
        best, bh = -1.0, np.nan
        for j in np.nonzero(ins.any(0))[0]:
            col = sl[:, j]
            i = int(np.nonzero(col < 0)[0].max())
            if i + 1 < len(col):
                xc = G.x[i] + G.h * col[i] / (col[i] - col[i + 1])
            else:
                xc = G.x[i]
            if xc > best:
                best, bh = xc, G.y[j]
        W[k], hw[k] = best, bh
    ok = np.isfinite(W)
    W = np.interp(G.z, G.z[ok], W[ok])
    hw = np.interp(G.z, G.z[ok], hw[ok])
    s = smooth / G.h
    return gaussian_filter1d(W, s, mode='nearest'), gaussian_filter1d(hw, 2.0 * s, mode='nearest')


def rounded_wedge(a, b, r):
    """the intersection of two half-space distances a, b with its edge rounded to radius r (exact for the wedge)"""
    qa, qb = a + r, b + r
    return np.sqrt(np.maximum(qa, 0.0) ** 2 + np.maximum(qb, 0.0) ** 2) + np.minimum(np.maximum(qa, qb), 0.0) - r


def mandible_top(spec, X, Z, res=0.05):
    """b3e-2: the highest point of either mandible's solid (heads/insect.mandible_descs at clearance 0, the bind and the
    closed pose, the plan frame's h above the venter) over each (x, z) of the grid (|x| read off the left one), NaN where
    neither lies under it: on a plan raster over the bases (x 1.5 .. 9.5, z -4.5 .. 1.0), scanned down from h 16.5"""
    from . import insect as HD
    from ..families import arthropod_parts as AP
    s = spec['author_scale'] * 1e-3
    xs = np.arange(1.5, 9.5 + 1e-9, res)
    zs = np.arange(-4.5, 1.0 + 1e-9, res)
    ys = np.arange(16.5, 10.0, -0.02)
    XX, ZZ = np.meshgrid(xs, zs, indexing='ij')
    top = np.full(XX.shape, -np.inf)
    P3 = np.stack([np.broadcast_to(XX[..., None], XX.shape + ys.shape), np.broadcast_to(ys, XX.shape + ys.shape),
                   np.broadcast_to(ZZ[..., None], XX.shape + ys.shape)], -1).reshape(-1, 3)
    for pose in ('bind', 'closed'):
        f = AP.field_mm(HD.mandible_descs(spec, 0.0, pose=pose)[0], s)
        ins = np.concatenate([f(P3[i:i + 2_000_000]) for i in range(0, len(P3), 2_000_000)]).reshape(XX.shape + ys.shape) < 0
        first = np.argmax(ins, axis=-1)                            # ys descend: the first inside sample is the highest
        top = np.maximum(top, np.where(ins.any(-1), ys[first], -np.inf))
    # b3e-5 (the B3e check, 10-26): the cover FAIRED (FEAT skin_*), not the raw scan by the nearest cell: the scan's top
    # raised by its step (ys[first] lies up to one step under the solid's top), dilated by a cone falling at skin_fall away
    # from the base (never steeper), floored at 12.0 (under every floor height: no cover), smoothed by skin_sigma, read
    # bilinearly; 12.0 off the raster
    from scipy import ndimage as nd
    T0 = np.where(np.isfinite(top), top + 0.02, -1e3)
    reach = 0.80
    n = int(np.ceil(reach / res))
    t = np.arange(-n, n + 1) * res
    Dk = np.sqrt(t[:, None] ** 2 + t[None, :] ** 2)
    fp = Dk <= reach + 1e-9
    T1 = nd.grey_dilation(T0, footprint=fp, structure=np.where(fp, -np.tan(np.radians(FEAT['skin_fall'])) * Dk, 0.0))
    T1 = nd.gaussian_filter(np.maximum(T1, 12.0), FEAT['skin_sigma'] / res, mode='nearest')
    out = nd.map_coordinates(T1, [(np.abs(X) - xs[0]) / res, (Z - zs[0]) / res], order=1, mode='nearest')
    return np.where((np.abs(X) >= xs[0]) & (np.abs(X) <= xs[-1]) & (Z >= zs[0]) & (Z <= zs[-1]), out, 12.0)


def features(phi_mass, Gm, spec, log=print):
    """THE B3e HEAD on the FEAT grid (full width): the mass resampled, the top's block added and its dish cut, the
    supraocular ridges, the canthi, the genae, the orbits, the clypeal process and the mentum. Returns (field, grid,
    curves)"""
    from scipy import ndimage as nd
    from scipy.interpolate import CubicSpline
    t0 = time.time()
    h = FEAT['h']
    Gf = Grid((-Gm.x[-1], Gm.lo[1], Gm.lo[2]), (Gm.x[-1], Gm.y[-1], Gm.z[-1]), h)
    X, Y, Z = Gf.mesh()
    # the mass on the fine grid (cubic, the x >= 0 half mirrored)
    full = np.concatenate([phi_mass[:0:-1], phi_mass], axis=0)
    x0m = -Gm.x[-1]
    f = nd.map_coordinates(full, [(X - x0m) / Gm.h, (Y - Gm.lo[1]) / Gm.h, (Z - Gm.lo[2]) / Gm.h], order=3,
                           mode='nearest').astype(np.float32)
    W, hw = mass_profile(phi_mass, Gm)
    Wz = np.interp(Z, Gm.z, W)
    hwz = np.interp(Z, Gm.z, hw)
    Wd_z = np.maximum(np.interp(Gf.z, Gm.z, W), np.array([half_width_at(z) for z in Gf.z]) - FEAT['draft_in'])
    hw_z = np.interp(Gf.z, Gm.z, hw)
    # ---- the TOP: the block added, the dish cut (b3f-3: the lobes' dome down to the block's side line)
    T = top_field(log, mass=(Gf.z, Wd_z, hw_z))
    U = plan_at(T['U'], T, X, Z)
    gx, gz = plan_at(T['gx'], T, X, Z), plan_at(T['gz'], T, X, Z)
    sd_loop = plan_at(T['sd'], T, X, Z)
    # b3e-2: the dish's floor raised over each mandible's base to the base's top + FEAT mand_skin inside the loop (b03
    # _b3e2: the bases rose through the floor behind the front margin at |x| ~4.8, pink ovals from above and, once the
    # socket was carved, holes in the head); the socket carve (the base shrunk by SINK) stays under that skin
    # (b3e-5, the B3e check: the cover faired, mandible_top, and met in a smooth max of width skin_k, not a hard one)
    # B3f: off (FEAT mand_skin None): the hidden bases dive under the front margin instead (heads/insect.py MAND base_dive)
    if FEAT['mand_skin'] is not None:
        Cv = mandible_top(spec, X, Z) + FEAT['mand_skin']
        kq = FEAT['skin_k']
        U = np.where(sd_loop <= 0, np.maximum(U, Cv) + np.maximum(kq - np.abs(U - Cv), 0.0) ** 2 / (4.0 * kq), U)
    # (b3f-12, the B3f check: the normalisation's slope capped at FEAT fT_slope: where U steps, np.gradient spikes and the
    # uncapped fT collapsed to ~0 along a vertical sheet, raised into ridges and beads by the smooth union below; the zero
    # set h = U, the head's shape, is unchanged)
    fT = (Y - U) / np.sqrt(1.0 + np.minimum(gx * gx + gz * gz, np.tan(np.radians(FEAT['fT_slope'])) ** 2))
    # the block: above the mass's widest line, inside its SIDE; the edge where U's outer face meets the side rounded
    Wd = np.maximum(Wz, np.array([half_width_at(z) for z in Gf.z])[None, None, :] - FEAT['draft_in'])
    # ---- B3f: THE SIDE a CIRCLE in each transverse section (FEAT side: radius R, vertical at (Wd, the mass's hw + up)),
    # the union of the strip |x| <= Wd - R and that disc (B3e: a near-vertical draft, flat within 0.01 mm over 1.0-1.8 mm)
    sdt = FEAT['side']
    lp = FEAT['lip']
    R_t, up_t = np.array(sdt['R'], np.float64), np.array(sdt['up'], np.float64)
    Rz = np.interp(Z, R_t[::-1, 0], R_t[::-1, 1])
    # b3f-3: ahead of the lip (the anterior angles, the knob) no release, so the circle is raised where it must CONTAIN
    # the rim's outermost crest at that z (0.06 outside it): b3f-2 stood it on the mass's widest line there (12.6-12.8)
    # and cut the knob (15.33 at x 8.08) down to 14.4
    R_zq = np.interp(Gf.z, R_t[::-1, 0], R_t[::-1, 1])
    lpz, lpx, lph = T['loop'][:, 1], T['loop'][:, 0], T['loop'][:, 2]
    req = np.full(len(Gf.z), -1e3)
    for k_, zq in enumerate(Gf.z):
        m_ = (np.abs(lpz - zq) < 0.05) & (lpx > 0.0)
        if not m_.any():
            continue
        i_ = int(np.argmax(np.where(m_, lpx, -1.0)))
        dx_ = lpx[i_] + 0.06 - (Wd_z[k_] - R_zq[k_])
        if dx_ > 0.0:
            req[k_] = lph[i_] - np.sqrt(max(R_zq[k_] ** 2 - min(dx_, R_zq[k_]) ** 2, 0.0))
    w_ant = smooth01((Gf.z - (lp['z_on'] - lp['fade_on'])) / lp['fade_on'])
    from scipy.ndimage import gaussian_filter1d
    hws_z = gaussian_filter1d(hw_z + w_ant * np.maximum(req - hw_z, 0.0), 0.3 / (Gf.z[1] - Gf.z[0]), mode='nearest')
    hws = hwz + np.interp(Z, up_t[::-1, 0], up_t[::-1, 1]) + (hws_z - hw_z)[None, None, :]
    xc_ = Wd - Rz
    ax_ = np.abs(X)
    d_circ = np.minimum(ax_ - xc_, np.sqrt(np.maximum(ax_ - xc_, 0.0) ** 2 + (Y - hws) ** 2) - Rz)
    # b3f-3: behind the lip zone the circle is released: there the lobes' dome falls to the side line (top_field) and the
    # mass's gena continues it (b3f-2's circle, its top at hw + R, cut the lobes' outer slopes and the crest's lateral end)
    w_back = smooth01((lp['z_back'] - Z) / lp['fade'])
    d_circ = d_circ - w_back * 3.0
    # ---- B3f: THE SUPRAOCULAR LIP (FEAT lip): above the lip line the side is released to U's outer face (its arc); the
    # release's underside the plane through the APEX (where U's outer face reaches the line, read per z off the top's plan
    # raster) inclined beta (rising outward), its cove into the circle filleted at r_cove; faded in and out along z
    LP = np.array(lp['path'], np.float64)
    ha_z = np.interp(Gf.z, LP[::-1, 0], LP[::-1, 1])
    zi_ = np.clip(np.round((Gf.z - T['lo'][1]) / T['res']).astype(int), 0, T['U'].shape[1] - 1)
    xs_o = T['xs'][T['xs'] > 6.0]
    xa_z = np.full(len(Gf.z), np.nan)
    for k_, iz in enumerate(zi_):
        row = T['U'][T['xs'] > 6.0, iz]
        hi_ = np.nonzero(row >= ha_z[k_])[0]
        if len(hi_) and hi_.max() + 1 < len(row):
            i_ = int(hi_.max())
            xa_z[k_] = xs_o[i_] + T['res'] * (row[i_] - ha_z[k_]) / max(row[i_] - row[i_ + 1], 1e-9)
    xa_z = np.where(np.isfinite(xa_z), xa_z, np.nanmedian(xa_z))
    tb_ = np.tan(np.radians(lp['beta']))
    d_rel = ((ha_z[None, None, :] + (ax_ - xa_z[None, None, :]) * tb_) - Y) * np.cos(np.radians(lp['beta']))
    w_lip = smooth01((lp['z_on'] - Z) / lp['fade_on']) * smooth01((Z - lp['z_off']) / lp['fade'])
    d_rel = d_rel + (1.0 - w_lip) * 3.0
    draft = smin_c(d_circ.astype(np.float64), d_rel, lp['r_cove'])
    rr_ = np.array(FEAT['ridge_r'], np.float64)
    r_ridge = np.interp(Z, rr_[::-1, 0], rr_[::-1, 1]) * (1.0 - w_lip) + lp['r'] * w_lip
    qa, qb = fT + r_ridge, draft + r_ridge                                    # (rounded_wedge with a per-voxel radius)
    top_side = np.sqrt(np.maximum(qa, 0.0) ** 2 + np.maximum(qb, 0.0) ** 2) + np.minimum(np.maximum(qa, qb), 0.0) - r_ridge
    # (and only inside M1d's outline in plan: the outer faces and the clypeal process's skirt above the mass ahead of the
    # head built a beak, e06 _f1)
    img_d, lo_d, res_d = poly_raster(dorsal_poly(), (-12.0, -12.5), (12.0, 3.0), 0.02)
    # (B3f: the block above the side circle's tangent line, the mass's widest line: below it the mass's own side; B3e's
    # block reached hwz - 1.5 under its near-vertical draft)
    f_add = np.maximum.reduce([top_side, (hwz - 0.02) - Y, raster_at(img_d, lo_d, res_d, X, Z).astype(np.float32)])
    # b3e-4 (the B3e check): in front of the front margin, over the clypeal process, the block stands only above the
    # process's underside (FEAT clypeus_floor, M1l), its lower edge rounded by foot_r; under it the face stays the mass's,
    # as the cut below means it to (b3e-1..3 added the block there down to hwz - 1.5: its vertical walls, DORSAL's polygon,
    # and its flat bottom stood 0.31-0.39 mm proud of the mass and up to 0.62 mm past M1l's face at h 11.7-12.6, the
    # flat-faced block with ragged edges between the mandible bases, beetle/scratch_b3echeck/r05_front_profile.py, r06)
    rim_ = np.array(FEAT['rim'], np.float64)
    kn_ = int(np.argmax(rim_[:, 2] * (rim_[:, 1] > -3.0)))               # the knob ends the rim's front run
    zf = np.interp(np.abs(X), rim_[:kn_ + 1, 0], rim_[:kn_ + 1, 1], right=9.0)
    cfl = np.array(FEAT['clypeus_floor'], np.float64)
    under_cl = (sd_loop > 0) & (Z > zf - 0.05) & (np.abs(X) <= max(p[0] for p in FEAT['clypeus_plan']))
    f_add = np.where(under_cl, smax_c(f_add, (np.interp(Z, cfl[:, 0], cfl[:, 1]) - Y).astype(np.float32),
                                      FEAT['foot_r']), f_add).astype(np.float32)
    f = smin_c(f, f_add, FEAT['foot_r']).astype(np.float32)
    # (B3e's SUPRAOCULAR LIP, a rounded wedge stuck on the draft wall 0.15 proud, turned ~73 deg: fitted 0.12-0.19, a soft
    # crease; B3f's lip is the side's own release, above)
    # the cut: above U inside the loop, and in front of the rim (the front margin's and the anterior angles' outer faces
    # over the mandible bases), above the face (h 12.6: the mandibles' bases cover what lies under it; zf, the front
    # margin's z, above). B3f: over the clypeal process only above its underside (M1l's, FEAT clypeus_floor): the face under
    # it stays the mass's, and the process itself is its own rounded plate (below)
    in_proc = np.abs(X) <= max(p[0] for p in FEAT['clypeus_plan'])
    # (b3f-7: the cut 0.02 ABOVE the plate's underside, so the plate overlaps what the cut leaves: 0.02 under it left a
    # sliver void under the process (h 12.83-12.85, |x| < 1.9, z -0.95 .. -0.25) whose sign flip set the GRID's divisor to
    # 28: b03 _b3f, the head's |grad| p50 0.035)
    floor_cut = np.where(in_proc, np.interp(Z, cfl[:, 0], cfl[:, 1]) + 0.02, 12.6)
    front = (sd_loop > 0) & (Z > zf - 0.05) & (Y > floor_cut)
    in_cut = (sd_loop <= 0) | front
    f = np.where(in_cut, np.maximum(f, fT), f).astype(np.float32)              # (the region above U removed)
    # ---- B3f: THE CLYPEAL PROCESS (FEAT process): a rounded PLATE, its plan the process's outline smoothed (the lobes and
    # the notch rounded), between M1l's underside line and proc_top (under the front margin's crest: the margin turns as a
    # crest over it), every edge rounded by r; from just behind the front margin's crest (hidden in the head) forward
    pc = FEAT['process']
    cq = np.array(FEAT['clypeus_plan'], np.float64)
    cpoly = smooth_closed(np.vstack([cq, cq[-2:0:-1] * np.array([-1.0, 1.0])]), 700, pc['plan_smooth'])
    img_c, lo_c, res_c = poly_raster(cpoly, (-3.6, -2.6), (3.6, 1.6), 0.01)
    d2c = raster_at(img_c, lo_c, res_c, X, Z).astype(np.float64)
    ptt = np.array(pc['top'], np.float64)
    dvc = np.maximum(np.interp(Z, cfl[:, 0], cfl[:, 1]) - Y, Y - np.interp(Z, ptt[:, 0], ptt[:, 1]))
    q1_, q2_ = d2c + pc['r'], dvc + pc['r']
    sdp = np.sqrt(np.maximum(q1_, 0.0) ** 2 + np.maximum(q2_, 0.0) ** 2) + np.minimum(np.maximum(q1_, q2_), 0.0) - pc['r']
    sdp = np.where(Z > zf - 0.15, sdp, np.maximum(sdp, (zf - 0.15) - Z))
    f = smin_c(f, sdp.astype(np.float32), pc['k']).astype(np.float32)
    log(f'[hull] B3f top: block added (the side a circle R {R_t[0, 1]}-{R_t[-1, 1]}, the lip released along M1l\'s line), '
        f'the dish cut, the clypeal plate in {time.time() - t0:.0f}s')
    # ---- the CANTHUS: a plate over the eye's front, its outline in its plane a rounded rectangle, its edges rounded
    ca = FEAT['canthus']
    th = np.radians(ca['turn'])
    e3 = np.array([np.sin(th), 0.0, np.cos(th)])               # its normal (plan, off forward toward +x)
    e2 = np.array([0.0, 1.0, 0.0])
    e1 = np.cross(e2, e3)
    P = np.stack([np.abs(X) - ca['c'][0], Y - ca['c'][1], Z - ca['c'][2]], -1)
    pu, pv, pn = P @ e1, P @ e2, P @ e3
    hu, hv, ht = ca['half']
    rc, re = ca['corner'], ca['r']
    qu, qv = np.abs(pu) - (hu - rc - re), np.abs(pv) - (hv - rc - re)        # the outline, rounded by the corner, inset
    d2 = np.sqrt(np.maximum(qu, 0.0) ** 2 + np.maximum(qv, 0.0) ** 2) + np.minimum(np.maximum(qu, qv), 0.0) - rc
    wx, wy = d2, np.abs(pn) - (ht - re)                                      # extruded by the thickness, edges by re
    box = np.sqrt(np.maximum(wx, 0.0) ** 2 + np.maximum(wy, 0.0) ** 2) + np.minimum(np.maximum(wx, wy), 0.0) - re
    f = smin_c(f, box.astype(np.float32), ca['k']).astype(np.float32)
    # (B3e's GENA ellipsoid, smin'd at k 0.5 onto the side, left a curved crease back from under the eye; B3f: the gena is
    # the mass's own round side below its widest line, met near-tangentially by the side's circle, FEAT side)
    log(f'[hull] B3f sides: the canthi in {time.time() - t0:.0f}s')
    # ---- the ORBIT: the collar round the eye, opened along M1l's exposed outline with a crisp rim
    from matplotlib.path import Path
    from scipy.spatial import cKDTree
    ob = FEAT['orbit']
    eg = eye_geometry(spec)
    C, a = eg['C'], eg['a']
    Pm = np.stack([np.abs(X), Y, Z], -1)                        # (the right orbit is the mirror: |x|)
    near = np.linalg.norm(Pm - C, axis=-1) < eg['R'] + 3.0
    Pn = Pm[near]
    v = Pn - C
    vr = np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
    vn = v / vr
    on = C + eg['R'] * vn
    # (the opening's outline the SPEC's measured eye ELLIPSE, M1l's exposed length x height at the eye's centre landmark
    # (eye.along / across, landmarks.eye_c: b03's eye gate's own reference patch), for the inside test and the rim alike,
    # clipped as the traced outline was: the traced 10-point polygon (and a 1-sample blur of it) kept its straight edges,
    # the orbit's rim a decagon at 90 px / mm (b03 _b3e / _b3e2); a spline through its points exposed the dome 2.5 deg
    # further back than M1l's patch (_b3e3)
    zc_e, hc_e = spec['landmarks']['eye_c']
    th_e = np.linspace(0.0, 2.0 * np.pi, 240, endpoint=False)
    EOs = np.column_stack([zc_e + 0.5 * spec['eye']['along'] * np.cos(th_e), hc_e + 0.5 * spec['eye']['across'] * np.sin(th_e)])
    r_s = np.hypot(EOs[:, 0] - C[2], EOs[:, 1] - C[1])
    k_s = np.minimum(1.0, ob['rim_clip'] * eg['R'] / np.maximum(r_s, 1e-9))
    EOs = np.column_stack([C[2] + (EOs[:, 0] - C[2]) * k_s, C[1] + (EOs[:, 1] - C[1]) * k_s])
    inside = Path(EOs).contains_points(np.column_stack([on[:, 2], on[:, 1]]))
    rim = []
    for zq, hq in EOs:
        dz_, dh_ = zq - C[2], hq - C[1]
        rx = eg['R'] ** 2 - dz_ ** 2 - dh_ ** 2
        if rx > 0:
            rim.append(C + np.array([np.sqrt(rx), dh_, dz_]))
    rim = np.array(rim)
    rimn = (rim - C) / np.linalg.norm(rim - C, axis=1, keepdims=True)
    chord, _ = cKDTree(rimn).query(vn)
    ang = 2.0 * np.arcsin(np.minimum(0.5 * chord, 1.0))
    dist = vr[:, 0] * np.sin(np.minimum(ang, 0.5 * np.pi))
    cav = np.where(inside, -dist, dist)                          # the opening's signed distance (- inside the cone)
    # (the cone is the dome's NEAR side only: limited by the plane vn . a = 0.15 as part of its boundary, continuously; a
    # hard flag there left a crease behind and under the eye, e06 _q4)
    cav = np.maximum(cav, (0.15 - vn @ a) * vr[:, 0]).astype(np.float32)
    # (and only to the collar's depth: the cone carried on outward cut slits through the surfaces it grazed, e06 _q7)
    cav = np.maximum(cav, vr[:, 0] - (eg['R'] + ob['collar'] + 0.12)).astype(np.float32)
    # the collar: the sphere grown by `collar`, kept within `band` of the opening (outside it), its band's end eased
    collar = smax_c(vr[:, 0] - (eg['R'] + ob['collar']), np.maximum(-cav - 0.02, cav - ob['band']), ob['band_r'])
    fn = f[near]
    fn = smin_c(fn, collar.astype(np.float32), ob['collar_k'])
    fn = smax_c(fn, -cav.astype(np.float32), ob['rim_r'])
    f[near] = fn.astype(np.float32)
    log(f'[hull] B3e orbit: the collar ({ob["collar"]} mm, band {ob["band"]}) opened along M1l\'s outline ({len(rim)} rim '
        f'points), rim radius {ob["rim_r"]}; {time.time() - t0:.0f}s')
    # ---- B3f: THE MENTUM part of the underside (FEAT mentum3; B3d / B3e: a slab 0.62 thick with bevelled corners standing
    # 0.26 out of a recessed surround, a proud tile): M3v's trapezoid (STROKES mentum trap, smoothed) as a SUTURE in the
    # underside, the plate inside it bulging slightly, its front edge a low transverse roll; a displacement of the field
    # near the underside only (the band under h ~9.3), the surface moving by the displacement
    st = STROKES
    mt = st['mentum']
    m3 = FEAT['mentum3']
    tr = np.array(mt['trap'], np.float64)
    tpoly = smooth_closed(np.vstack([tr, tr[::-1] * np.array([-1.0, 1.0])]), 400, 3.0)
    img_m, lo_m, res_m = poly_raster(tpoly, (-7.0, -7.0), (7.0, 1.5), 0.02)
    dxz = raster_at(img_m, lo_m, res_m, X, Z).astype(np.float64)
    w_u = smooth01((mt['low'] + m3['band'] - Y) / 0.5)
    sut = m3['suture_d'] * np.maximum(1.0 - (dxz / m3['suture_w']) ** 2, 0.0) ** 2
    bul = m3['bulge'] * smooth01(-dxz / m3['bulge_w'])
    z_fr = float(tr[0, 1])
    fro = m3['front'] * np.exp(-((Z - (z_fr - 0.25)) / m3['front_w']) ** 2) * smooth01(-dxz / 0.25)
    f = (f + w_u * (sut - bul - fro)).astype(np.float32)
    log(f'[hull] B3f features done in {time.time() - t0:.0f}s on {Gf.n} at {h} mm')
    curves = dict(rim=T['loop'], orbit_rim=rim)
    return f, Gf, curves, T


# ============================================================================================ the volume
def head_volume(spec, log=print):
    """THE HEAD GRID (life mm, the plan frame, h above the venter): the hull, the flow, the strokes, the exact distance,
    clamped and blurred; the full width. Cached by every input. Returns dict(values (nx, ny, nz) mm, lo (x0, h0, z0),
    h, divisor, errors (hull / flow per view), curves, fronts)"""
    from . import insect as HD
    # (B3f: insect.MAND enters the key only while the head reads the mandible: the cover over its bases, FEAT mand_skin)
    key = cache_key(dict(v=VERSION, dorsal=DORSAL, lateral=LATERAL, sec_wide=SEC_WIDE, sec=SEC, build=BUILD,
                         feat=FEAT, plates={k: STROKES[k] for k in ('clypeus', 'mentum')}, orbit=STROKES['orbit'],
                         fronts=FRONT_TABLES, eye=spec['eye'], lm=spec['landmarks'], md=spec['mandible'],
                         mand=(HD.MAND if FEAT['mand_skin'] is not None else None)))

    def build():
        # B3e: the MASS (cached on its own inputs), then the FEATURES as CSG on the FEAT grid, then the exact distance to
        # their zero set, clamped, blurred by FEAT blur (BUILD blur is B3d's: it rounded every edge past the measured radii)
        from scipy import ndimage as nd
        M = head_mass(spec, log)
        lo_m = np.asarray(M['lo'], np.float64)
        phi = M['phi']
        Gm = Grid(lo_m, lo_m + (np.array(phi.shape) - 1) * float(M['h']), float(M['h']))
        f, Gf, curves, _ = features(phi, Gm, spec, log)
        t = time.time()
        f = exact_distance(f, Gf, max(abs(c) for c in BUILD['clamp']) + 1.0)
        f = np.clip(f, BUILD['clamp'][0], BUILD['clamp'][1])
        f = nd.gaussian_filter(f, FEAT['blur'] / Gf.h, mode='nearest').astype(np.float32)
        log(f'[hull] B3e exact distance on {Gf.n} in {time.time() - t:.0f}s')
        out = dict(values=f, lo=Gf.lo, h=np.float64(Gf.h))
        for k in M:
            if k.startswith(('err_', 'front_')):
                out[k] = M[k]
        for k, c in curves.items():
            out[f'curve_{k}'] = np.asarray(c, np.float64)
        return out
    C = cached('beetle_head', key, build, log)
    V = C['values']
    return dict(values=V, lo=C['lo'], h=float(C['h']), divisor=grid_divisor(V, float(C['h'])),
                errors={k[4:]: C[k] for k in C if k.startswith('err_')},
                curves={k[6:]: C[k] for k in C if k.startswith('curve_')})
