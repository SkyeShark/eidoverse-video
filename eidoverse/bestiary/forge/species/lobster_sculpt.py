"""X6 (work/bestiary/research/LOBSTER_PLAN.md §5.5, §12's X6 row; the lead's calls at X5b / X6, PLAN.md 11-09): THE
LOBSTER'S HIGHS on the accepted X4 cages (work/bestiary/lobster/cage_x04_crusher.npz) with the BEETLE'S CUTICLE METHOD
(species/stag_beetle_sculpt.py, B6-B9: the macro high the creased LIMIT as the house voxel.SparseSDF, the micro relief
evaluated per bake sub-sample with its masks per limit vertex), read and called, extended here. The step script is
work/bestiary/tests/x06_high.py. X7's pilot bake reads what this writes.

THE MACRO HIGH, per PRIMARY shell (uv_x05's: the stacked copies bake from their primary):
  LIMIT    the shell's creased limit (subdiv_sharp.subdivide of x04's controls, LEVEL; the low's own surface) as the
           house SparseSDF (stag_beetle_sculpt.MeshProg: the exact signed distance to the closed limit mesh; a sleeve is
           open: the house SHELL, its half thickness SLEEVE_HALF), at VOXEL m x4 (plan §5.5: 0.30 mm, 75 um at life;
           the claw parts with cutting edges at VOXEL_EDGE, plan's 0.25), its band BAND, grown round every stroke
           planned BEFORE the grid (voxel's `extra`: octopus_sculpt's rule, plan §5.5);
  FILLETS  the lead's call 3 (X4h check: the clay's zero-radius INSIDE corners, the crusher dactyl's base A / B, the
           cutter's knob lip, which the limit bridges ~0.35 mm over): real chitin has fillets, so each clay is CLOSED
           at radius FILLET r (morphological closing on its own SparseSDF: relevel, grow r, relevel, shrink r, relevel:
           every inside corner sharper than r rounded to r, the rest unchanged; near the corners it marks, the closed
           field recomputed EXACTLY, closing_exact_near_corners) and the high CARVED to it where the
           limit BRIDGES such a corner (the limit within FILLET near of it): H = L + w clip(smax(L, Cc) - L, 0, cut), w
           fading from 1 to 0 over FILLET fade, only near the limit's surface, only where the closed clay is solid a
           cut further in (a plate the clay does not have is never cut through); it only removes the limit's bridge;
  ZONES    planned before the grid with the strokes (voxel's `extra`): the fillets' reach, and every LOW point standing
           more than LOW_ZONE over off the limit: past the band MeshProg's fallback is UNSIGNED (a false surface 0.45 mm
           under the high), so the bake must find every low point in true voxels; the strokes also ride in that
           fallback program (a ray leaving the band still meets them: AO, cavity);
  WRINKLES the joint membranes (the sleeves; the shells' membrane faces): soft folds (plan §5.5's sleeve wrinkles, S
           tier 0.1-0.3 mm) as a DISPLACEMENT of the field: a cosine valley of WRINKLE depth every WRINKLE pitch of
           the membrane's distance from its rim (the signed distance smoothed across the rim: fold_stations), read
           at each voxel's closest point on the limit (fold_values, fold_carve), fading in over WRINKLE fade from
           the rim; build_high's report counts the membrane area the folds cover;
  STROKES  x04's S-tier records (strokes_x04_crusher.json: anchor on the clay, its normal, the leaned axis, the foot
           d, the height, the kind, the source photo) as round cones / domes (voxel.STROKE_CONE) in smooth union
           (STROKE_SHAPE per kind: the tip, the foot's sink, the fillet k): the claws' white-tipped tubercles, the
           crusher's beads and blunt teeth, the cutter's saw denticles, the carpus's tubercles and knobs, the merus's
           denticles, the hinge condyles (c11's low cushions) where x04 left them as strokes (the cutter's lip, the lead's
           third corner, lies under one: its fillet is that condyle's foot blend);
  then the house relevel (voxel.redistance).
THE MICRO LAYER (the beetle's: stag_beetle_sculpt.relief and its B9 granules at sites on the limit, unchanged): lobster
  rows (MICRO) ridden onto its RECIPE at import (as b06's trial recipes ride: the beetle's file is not edited), keyed
  by the cage regions, with the plan's measured sizes (§2.3: palm granules 0.25-0.40 mm at 0.8-1.2 mm, setal pits
  0.40-0.65 mm on n04; [L5] "only slightly granular"): micro_params gives the bake a shell's rows, parameters, sites'
  table, offsets and masks (micro_masks per limit vertex; the material pass reads the same numbers).
THE MAPS for X7's bake (bake.py's own passes run on this high: AO, cavity, curvature, height, position): x06 measures
  them on the high's surface and wear_maps turns them into the WEAR and GRIME drivers (convex x open, the stroke tips,
  the ventral drag; the crevices, silt on up-facing shell), so X6's view checks what X7 will bake; the FEATURE masks
  (feature_masks: tubercle tips, teeth, cutting edges) are analytic from the strokes' own primitives (no new
  material-id range in the shared id space).
UNITS: grids in METRES AT x4 (the lows' and the bake's units); records, recipes and gates in LIFE mm (x SC_M = 0.004)."""
import json

import numpy as np
import warp as wp

from .. import sdf as S_
from .. import subdiv_sharp as SS
from .. import voxel as VX
from ..mesh import QuadMesh
from . import stag_beetle_sculpt as SC

SC_M = 0.004                    # metres at x4 per life mm
LEVEL = 4                       # the limit's level (the propodus's 4.4 mm cage quads -> 0.28 mm at life: a 1 mm radius
#                                 sags 0.01 mm between its vertices, under the 0.075 mm voxel)
VOXEL, VOXEL_EDGE = 0.0003, 0.00025     # m at x4 (plan §5.5)
EDGE_SHELLS = ('cheliped_propodus_L', 'cheliped_dactyl_L', 'cheliped_propodus_cutter_L', 'cheliped_dactyl_cutter_L')
BAND = 0.0018                   # m at x4: +-0.45 mm at life (voxel.SparseSDF's house band)
SLEEVE_HALF = 0.15              # life mm: an open sleeve's half thickness (2 voxels at x4; the beetle's 0.012 mm at x10)
# THE FILLETS (life mm): r the fillet radius (the lead's 0.3-0.5 mm); eps the closing's least change that marks a corner;
# fade: w 1 within fade[0] of a marked voxel, 0 past fade[1]; k the smooth max's blend; the clay grid's voxel (m x4) and
# its band (it must hold 2 r and two voxels). TARGETED (the prototype, x6_proto / x6_section: the closing also marks the
# clay's corners where the cage does not follow the clay at all, the crusher dactyl's hidden base fan, the clay solid 1.3
# mm where the limit is air, and an untargeted max cut that fan's 0.4 mm plate): a corner counts only where the LIMIT
# lies within near mm of it (a corner the limit bridges), and a voxel is cut only near the limit's surface (|L| <= near)
# and by at most cut mm (the bridges the X4h check measured: 0.31-0.35 mm)
FILLET = dict(r=0.40, eps=0.010, fade=(1.0, 2.0), k=0.08, voxel=0.0004, band=0.0042, near=0.6, cut=0.45)
# THE STROKES' SHAPES per record kind (life mm, x4's records): tip the rounded tip's radius as a share of the foot's
# radius (d / 2), sink how deep the cone's foot sphere starts below the anchor (a share of d / 2), k the smooth union's
# fillet; 'dome' kinds are spherical caps of foot d and height h (the beads, the blunt teeth); 'cushion' is the hinge
# condyle's capsule lying on the shell (stroke_prims)
STROKE_SHAPE = dict(
    tubercle=dict(tip=0.85, sink=0.30, k=0.35, foot=0.45, shape='cone'),   # c11 at 3x (11-12): BLUNT PEGS, a round
    #                                                                       white cap 3.1-3.5 mm on a ~4.2 mm collar.
    #                                                                       (tip 0.26 read as thorns, 0.45 (A0) still
    #                                                                       as thorns in profile: the strokes' lab,
    #                                                                       sheet_margin_base / _v1; tip 0.85: the cap
    #                                                                       3.06 mm on the 3.6 mm foot)
    knob=dict(tip=0.75, sink=0.30, k=0.25, foot=0.45, shape='cone'),       # c11: a low rounded peg
    spine=dict(tip=0.12, sink=0.30, k=0.25, foot=0.45, shape='cone'),      # c11 / r57282_7-8: the carpus's sharp spines
    denticle=dict(tip=0.30, sink=0.30, k=0.15, shape='cone'),     # the saw's conical denticles, the merus's (n04)
    tooth=dict(k=0.20, shape='dome'),                             # n04: the crusher dactyl's rounded blunt teeth: a
    #                                                               row of beads (as a cone of tip 0.5 they read as a
    #                                                               saw's points in profile: x06's look shot beside n04)
    bead=dict(k=0.20, shape='dome'),                              # n04: the fixed finger's rounded blunt beads
    condyle=dict(k=0.24, foot=0.20, shape='cushion', h_max=1.30, half_w=2.3, long=0.47, inset=0.3))
#                                                                   the hinge condyle (x4f: a stroke). 11-12: A LOW
#                                                                   OVAL CUSHION lying along the socket's rim (c11 at
#                                                                   8x: ~7.7 x 5.0 mm, low and glossy; the cutter's a
#                                                                   round knob ~5 mm). It WAS n04's ball (a spherical
#                                                                   cap 8.2 mm across, 3.36 proud, ~80 deg at its
#                                                                   foot): on the hinge's convex corner it overhung
#                                                                   the rim, read as a ball stuck on (the lead's A0
#                                                                   point 2) and BAKED IN SHARDS (X7: its disc on the
#                                                                   page ~600 texels at the reach / far, the normal
#                                                                   map in wedges). h_max caps the record's height
#                                                                   (under the house's 1.5 mm cage: an ordinary
#                                                                   search bakes it), half_w its half width, long x d
#                                                                   its half length along the claw's width
#                                                                   (claw_wide), inset the end caps' share; a
#                                                                   condyle narrower than 2 half_w is a round dome
#                                                                   (the cutter's). Its foot's blend IS the cutter
#                                                                   lip's fillet (the lead's call 3; x06 gate 4)
# A0 (x6fix_x7, the lead's shape audit, point 2: "spheres stuck on"; c11 / c04 / n04 / r57282_5 at full size: the
# tubercles, knobs and the hinge condyle GROW out of the shell on broad blended feet, where k 0.24-0.35 mm met the shell
# at the cone's or the ball's own flank, ~80 deg at a condyle's foot): `foot` sets the smooth union's k as a share of
# the stroke's own foot radius (d / 2: a 3.4 mm tubercle 0.94 mm, the 8.2 mm condyle 1.43 mm), so the foot flares into
# the shell; the tip and the record's height are unchanged (x06 gate 3). Kinds without `foot` keep their k (the saw's
# denticles and the occlusal beads and teeth stay crisp on their rims)
# THE MEMBRANES' WRINKLES (life mm; plan §5.5 sleeve wrinkles 0.1-0.3 mm, soft carve runs): valleys of `depth` every
# `pitch` of the station field, parallel to the membrane's rim (fold_stations, fold_carve: a displacement of the
# field); smooth: the station field's smoothing length (mm), never more than `narrow` x a membrane piece's half width
# (a strip 4 mm wide keeps its own two or three wrinkles), over the piece and `margin` x that length of the chitin
# beside it; wobble = (the lines' wander as a share of the pitch, its feature size mm); vary = (the share of the depth
# a valley loses where it fades, its size mm); reach: how far from the limit a voxel still moves (mm); fade: the
# folds' share rises from 0 at the rim's furthest step to 1 this far inside it (mm).
# (11-09, the craft guide 03.39: an organic crease is broad, shallow and faded, its walls well under the key light's
# elevation; the first values, 0.35 mm carve balls every 0.6 mm, cut 55 degree walls every 3.6 pixels of the 1 m
# frame.) A cosine valley 0.15 deep every 1.2 mm: walls 21 degrees at the steepest, 7 pixels apart at 1 m, each
# fading to 0.06 along its run
WRINKLE = dict(depth=0.15, pitch=1.2, smooth=1.5, narrow=0.25, margin=4.0, wobble=(0.35, 3.0), vary=(0.6, 4.0),
               reach=0.9, fade=1.0)
# THE MICRO ROWS (stag_beetle_sculpt.RECIPE's layout: cells (spacing, amp, border), pits (spacing, r, depth), setae
# (spacing, len, w, ht), groove; life mm): granules as BEADS (cell_mode 2: round domes at one layer of sites) at the plan's
# 0.8-1.2 mm spacing and 0.25-0.40 mm size (radius share 0.16 of a 1.0 mm spacing = 0.32 mm across), low ([L5] "only
# slightly granular": 0.03 mm amplitude, flanks ~10 deg, a first-order relief under the voxel, as the beetle's micro
# layer is); setal pits ONE layer (pit_mode 1) of 0.40-0.65 mm rings (r 0.26) at ~1.6 mm with a slight lip; the fingers'
# and dactyls' chitin smoother; the membranes the beetle's vermiculate folds at the lobster's size; the strokes' polished
# tips no relief (micro_masks zero the cells and pits there)
# (11-09, the first look shots beside n04's palm crop, LOOKED: the first rows' pits, ringed, 0.52 mm at 1.6 mm, as deep as
# the granules stood, drew a foam of bubbles with doubled and tripled rings, the granules faint specks under them. n04's
# palm is the other way round: pale granules at ~1 mm the whole texture, a setal pit only every ~10-13 mm (about 10 in
# the crop's 45 x 40 mm). So: the granules taller, the pits SPARSE with a slight lip.)
# THE GRANULES AT SITES ON THE LIMIT (the beetle's B9 method, cell_mode 5: stag_beetle_sculpt.grain_sites / grain_table /
# grain_granules, called from micro_params below): the same station showed mode 2's beads (one layer of a jittered 3D
# lattice: a near-Poisson set) in clumps of two and three with bare gaps, where n04's granules stand evenly, one per ~1
# mm. GRANULES: the sites' spacing and the granule's size (mm; plan 2.3: 0.25-0.40 at 0.8-1.2), their jitters, the
# relaxation, the table's cell; each row's `grain` its amplitude (mm) and ground. size_jit 0.35 (lognormal, cut at two
# sigmas: 0.17-0.68 mm, median 0.34): a few large among many small, as n04's palm has (0.6-0.8 mm ones every 2-3 mm
# among the 0.3 mm ones; the craft guide 03.42: same-size stamps on an even layout read as polka dots)
GRANULES = dict(spacing=1.0, size=0.34, size_jit=0.35, ht_jit=0.25, iters=12, step=0.5, cell=1.0, seed=29)
BROAD_N = np.array([0.94, 0.0, 0.34])      # the claws' broad faces' normal at the bind (the propodi's thin axis) AS X6 WAS
#                                            BUILT, the fingers' plane vertical. A0 (11-11): read it with broad_n()
_BROAD = []


def broad_n():
    """the crusher's broad faces' normal at the bind (unit; the sign means nothing): its dactyl's HINGE AXIS, which is the
    claw's thin axis, from the rig (decapod.rest_chain on the SPEC: claws.crusher.a_h). A0: the fingers' plane is flat
    since rig.cheliped.claw_plane 0, so the constant BROAD_N, the vertical plane's (0.94, 0, 0.34), now lies IN the
    claw's plane: the molars' polish (micro_params) would have kept the granules on the occlusal faces and bared the
    broad ones. Only the crusher has molars"""
    if not _BROAD:
        from ..families import decapod as DP
        from . import lobster as LB
        a = np.asarray(DP.rest_chain(LB.SPEC)['claws']['crusher']['a_h'], np.float64)
        _BROAD.append(a / np.linalg.norm(a))
    return _BROAD[0]


_WIDE = []


def claw_wide():
    """the claws' WIDTH direction at the bind (unit; the sign means nothing): in the fingers' plane, across the claw's
    axis, from the rig (rest_chain's claws.crusher.n; the cutter's is the same). The hinge condyle's cushion lies along
    it (STROKE_SHAPE condyle): the socket's rim runs across the claw"""
    if not _WIDE:
        from ..families import decapod as DP
        from . import lobster as LB
        n = np.asarray(DP.rest_chain(LB.SPEC)['claws']['crusher']['n'], np.float64)
        _WIDE.append(n / np.linalg.norm(n))
    return _WIDE[0]


MICRO = dict(
    lobster_palm=dict(cells=(1.00, 0.0, 0.22), pits=(9.0, 0.26, 0.050), setae=(0.5, 1.5, 0.05, 0.0), groove=0.0,
                      cell_mode=5.0, cell_prof=1.5, cell_flat=2.0, grain=dict(amp=0.040, base=0.05), pit_mode=1.0,
                      pit_rim=0.20),
    lobster_finger=dict(cells=(1.00, 0.0, 0.22), pits=(7.0, 0.24, 0.045), setae=(0.5, 1.5, 0.05, 0.0), groove=0.0,
                        cell_mode=5.0, cell_prof=1.5, cell_flat=2.0, grain=dict(amp=0.028, base=0.05), pit_mode=1.0,
                        pit_rim=0.20),
    lobster_chitin=dict(cells=(1.00, 0.0, 0.22), pits=(8.0, 0.24, 0.045), setae=(0.5, 1.5, 0.05, 0.0), groove=0.0,
                        cell_mode=5.0, cell_prof=1.5, cell_flat=2.0, grain=dict(amp=0.034, base=0.05), pit_mode=1.0,
                        pit_rim=0.20),
    lobster_membrane=dict(cells=(0.60, 0.020, 0.30), pits=(1.0, 0.0, 0.0), setae=(0.5, 1.5, 0.05, 0.0), groove=0.0,
                          warp=(1.6, 0.5), cell_mode=1.0, cell_shape=0.0))
REGION_ROW = dict(palm='lobster_palm', lump='lobster_palm', finger='lobster_finger', molar='lobster_finger',
                  chitin='lobster_chitin', spine='lobster_chitin', cap='lobster_chitin', opening='lobster_chitin',
                  condyle='lobster_chitin', tubercle='lobster_chitin', membrane='lobster_membrane',
                  sleeve='lobster_membrane')
for _k, _v in MICRO.items():               # ridden onto the beetle's RECIPE (b06's trial mechanism; its file unedited)
    SC.RECIPE.setdefault(_k, _v)


# ============================================================================================ the limit
def limit(C_life, Q, sharp, level=LEVEL):
    """the creased limit (subdiv_sharp.subdivide pushed to the limit) of x04's controls (life mm): (V, quads, each quad's
    level-0 ancestor)"""
    lim, _, parent, _ = SS.subdivide(QuadMesh(np.asarray(C_life, np.float64), np.asarray(Q, int)), sharp, level)
    return lim.V, np.asarray(lim.Q, np.int64), np.asarray(parent, np.int64)


def tris(Q):
    return np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])


def vertex_normals(V, Q):
    n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    vn = np.zeros_like(V)
    for j in range(4):
        np.add.at(vn, Q[:, j], n)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-20)


# ============================================================================================ the strokes
def stroke_prims(records):
    """x4's records -> round-cone primitives in LIFE mm: rows dict(name, kind, a, b, ra, rb, k, top, foot_r, axis)"""
    out = []
    for r_ in records:
        kind = 'condyle' if r_['name'].startswith('hinge_condyle') else r_['kind']
        sh = STROKE_SHAPE[kind]
        P = np.asarray(r_['anchor'], np.float64)
        ax = np.asarray(r_['axis'], np.float64)
        ax /= np.linalg.norm(ax)
        d, h = float(r_['d']), float(r_['height'])
        k_ = float(sh['foot']) * 0.5 * d if 'foot' in sh else float(sh['k'])     # A0: the foot's blend (STROKE_SHAPE)
        if sh['shape'] == 'cushion':
            # a capsule lying ON the shell along the claw's width: its section a spherical cap of half width hw and
            # height h (the ball's radius R, its centre h - R along the axis), its half length hl; the record's height
            # capped at h_max (the prim's 'height' and 'top' are the cushion's: x06 gates 1 / 3 read them)
            h = min(h, float(sh['h_max']))
            hw = min(0.5 * d, float(sh['half_w']))
            hl = max(hw, float(sh['long']) * d)
            R = (hw * hw + h * h) / (2.0 * h)
            e = claw_wide() - ax * float(claw_wide() @ ax)
            e /= np.linalg.norm(e)
            t = max(hl - hw - float(sh['inset']), 0.0)
            c = P + ax * (h - R)
            a, b, ra, rb = c - e * t, c + e * t, R, R
        elif sh['shape'] == 'dome':
            # a spherical cap of foot radius d / 2 and height h: the ball's radius R, its centre h - R along the axis
            R = ((0.5 * d) ** 2 + h * h) / (2.0 * h)
            c = P + ax * (h - R)
            a, b, ra, rb = c, c, R, R
        else:
            rf = 0.5 * d
            ra, rb = rf, sh['tip'] * rf
            a = P - ax * (sh['sink'] * rf)
            b = P + ax * (h - rb)
        out.append(dict(name=r_['name'], kind=kind, a=a, b=b, ra=float(ra), rb=float(rb), k=round(k_, 3),
                        top=(P + ax * h), foot_r=0.5 * d, axis=ax, height=h, anchor=P, source=r_.get('source', '')))
    return out


def mirror_prims(prims):
    """the left records' primitives on the right (x -> -x): the right carpus's strokes"""
    M = np.array([-1.0, 1.0, 1.0])
    return [dict(p, a=p['a'] * M, b=p['b'] * M, top=p['top'] * M, axis=p['axis'] * M, anchor=p['anchor'] * M)
            for p in prims]


def sd_cone(P, a, b, ra, rb):
    """the round cone's exact signed distance (life mm), numpy (Inigo Quilez's sdRoundCone, voxel.STROKE_CONE's)"""
    P = np.atleast_2d(P)
    ba = b - a
    l2 = float(ba @ ba)
    if l2 < 1e-12:
        return np.linalg.norm(P - a, axis=1) - ra
    rr = ra - rb
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = P - a
    y = pa @ ba
    z = y - l2
    x2v = pa * l2 - y[:, None] * ba[None, :]
    x2 = (x2v * x2v).sum(1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    out = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - ra
    m1 = np.sign(z) * a2 * z2 > k
    m2 = np.sign(y) * a2 * y2 < k
    out = np.where(m1, np.sqrt(x2 + z2) * il2 - rb, out)
    out = np.where(m2 & ~m1, np.sqrt(x2 + y2) * il2 - ra, out)
    return out


# ============================================================================================ the macro high
def macro_high(V_life, Q, prims, open_=False, voxel=VOXEL, band=BAND, log=print, zones=None):
    """the limit (life mm) as the house SparseSDF in metres at x4 (stag_beetle_sculpt.MeshProg: exact signed distance;
    an open sleeve the SHELL of half SLEEVE_HALF), its band grown round the planned strokes and ZONES (voxel's `extra`:
    each stroke's bounding sphere; zones (centres, radii) life mm: the fillets' carve, so a carved surface never meets
    the band's inner edge, where MeshProg's fallback reads an UNSIGNED distance: x6_spots found a false back face 0.1
    mm under a 0.35 mm carve)"""
    Vm = np.asarray(V_life, np.float64) * SC_M
    F = tris(Q)
    prog = SC.MeshProg(Vm, F, open_=open_, half=SLEEVE_HALF * SC_M if open_ else 0.0)
    # the strokes in the FALLBACK too (MeshProg.prog: the field past the band): the strokes live in the voxels, and a ray
    # that leaves the band (the bake's AO / cavity, trace_views' AO) read the limit alone there: x06's close-ups drew a
    # crisp dark ring round every stroke where its activated voxels ended. Smooth-unioned as add_strokes does
    for p in prims:
        prog.prog.roundcone(p['a'] * SC_M, p['b'] * SC_M, p['ra'] * SC_M, p['rb'] * SC_M, op=S_.UNION, k=p['k'] * SC_M,
                            name=p['name'])
    lo = Vm.min(0) - 0.004
    hi = Vm.max(0) + 0.004
    cen, rad = np.zeros((0, 3)), np.zeros(0)
    if prims:
        cen = np.array([0.5 * (p['a'] + p['b']) for p in prims]) * SC_M
        rad = np.array([0.5 * np.linalg.norm(p['b'] - p['a']) + max(p['ra'], p['rb']) + p['k'] for p in prims]) * SC_M
    if zones is not None and len(zones[0]):
        cen = np.concatenate([cen, np.asarray(zones[0], np.float64) * SC_M])
        rad = np.concatenate([rad, np.asarray(zones[1], np.float64) * SC_M])
    ex = None
    if len(cen):
        ex = (cen, rad)
        lo = np.minimum(lo, (cen - rad[:, None]).min(0) - 0.002)
        hi = np.maximum(hi, (cen + rad[:, None]).max(0) + 0.002)
    G = VX.SparseSDF(prog, lo, hi, voxel=voxel, band=band, log=log, extra=ex)
    G._prog_keep = prog
    return G


def corner_zones(prog_lim, Gc, v0, vc, step=0.5):
    """the clay's inside corners the LIMIT bridges (fillet_carve's K and test), thinned to one every `step` mm (life):
    (centres life mm, radii life mm: the carve's reach FILLET fade[1] + cut)"""
    r = FILLET['r'] * SC_M
    K = ((v0 - vc) > FILLET['eps'] * SC_M) & (np.abs(v0) < 2.0 * r)
    if not K.any():
        return np.zeros((0, 3)), np.zeros(0)
    KP = Gc.positions()[K]
    KP = KP[np.abs(prog_lim.eval(KP)) <= FILLET['near'] * SC_M] / SC_M
    keep = []
    if len(KP):
        from scipy.spatial import cKDTree
        tr = cKDTree(KP)
        taken = np.zeros(len(KP), bool)
        for j in range(len(KP)):
            if not taken[j]:
                keep.append(j)
                taken[tr.query_ball_point(KP[j], step)] = True
    C = KP[keep] if keep else np.zeros((0, 3))
    return C, np.full(len(C), FILLET['fade'][1] + FILLET['cut'])


LOW_ZONE = dict(over=0.30, pad=0.30)    # life mm: where the LOW stands more than `over` off the limit, a zone of that
#                                         distance + pad: every low point in the high's true voxels (past the band the
#                                         fallback is MeshProg's UNSIGNED distance, positive inside the solid: x6_strokesec
#                                         drew that false surface 0.45 mm under the high, and x06's envelope found the
#                                         dactyl's low 0.78 mm in, where the bake would read the fallback)


def low_zones(prog_lim, low):
    """zones (centres, radii; life mm) at the low's vertices and face centres that stand more than LOW_ZONE over off the
    limit (prog_lim: its exact signed distance, x4 m)"""
    Vl, Qlow = low
    P = np.concatenate([Vl, Vl[Qlow].mean(1)])
    d = np.abs(prog_lim.eval(P * SC_M)) / SC_M
    far = d > LOW_ZONE['over']
    return P[far], d[far] + LOW_ZONE['pad']


def build_high(V_life, Q, parent, region, prims, clay_prog=None, open_=False, wrinkle_axis=None, voxel=VOXEL,
               log=print, low=None):
    """ONE shell's high (module docstring), in order: the clay closed (its corners the limit bridges, planned as zones);
    the low's far points planned as zones (low = (V life mm, quads): low_zones); the limit's grid with the strokes and the
    zones planned; the fillets carved; the membranes' wrinkles carved; the strokes added; the relevel. Returns (G,
    report)"""
    import time
    rep = dict(voxel_mm_x4=voxel * 1e3)
    t0 = time.time()
    Gc = v0 = vc = None
    zc, zr = [np.zeros((0, 3))], [np.zeros(0)]
    Vm = np.asarray(V_life, np.float64) * SC_M
    prog_lim = SC.MeshProg(Vm, tris(Q), open_=open_)
    if low is not None:
        lz = low_zones(prog_lim, low)
        zc.append(lz[0])
        zr.append(lz[1])
        rep['low_zones'] = int(len(lz[0]))
        rep['low_off_max_mm'] = float(lz[1].max() - LOW_ZONE['pad']) if len(lz[1]) else 0.0
    if clay_prog is not None:
        Gc, v0, vc = closed_clay(clay_prog, Vm.min(0) - 0.006, Vm.max(0) + 0.006, log=log)
        rep['clay_voxels'] = int(Gc.n)
        cz = corner_zones(prog_lim, Gc, v0, vc)
        zc.append(cz[0])
        zr.append(cz[1])
        rep['corner_zones'] = int(len(cz[0]))
    del prog_lim
    zones = (np.concatenate(zc), np.concatenate(zr))
    G = macro_high(V_life, Q, prims, open_=open_, voxel=voxel, log=log, zones=zones)
    rep['voxels'] = int(G.n)
    if Gc is not None:
        fr = fillet_carve(G, Gc, v0, vc, log=log)
        rep['fillets'] = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in fr.items()}
        del Gc, v0, vc
    log(f'[lobster_sculpt] the grid and its fillets ({time.time() - t0:.0f}s)')
    if wrinkle_axis is not None:
        ft, fm = fold_stations(V_life, Q, region[parent], wrinkle_axis[0], wrinkle_axis[1], log=log)
        rep['fold_voxels'], rep['fold_deepest_mm'] = fold_carve(G, V_life, Q, ft, fm,
                                                                open_half=SLEEVE_HALF if open_ else 0.0, log=log)
        rep['fold_vertices'] = int((fm > 0.0).sum())
        # the folds' COVER of the membranes, by area (the first displacement left them bare from the rim inward and
        # nothing counted it): the share's mean, and the area it leaves at 0
        mq = np.isin(np.asarray(region)[parent], ('membrane', 'sleeve'))
        Vl = np.asarray(V_life, np.float64)
        qa = 0.5 * np.linalg.norm(np.cross(Vl[Q[mq, 2]] - Vl[Q[mq, 0]], Vl[Q[mq, 3]] - Vl[Q[mq, 1]]), axis=1)
        qs = fm[Q[mq]].mean(1)
        rep['fold_area_mm2'] = float(qa.sum())
        rep['fold_cover'] = float((qa * qs).sum() / max(qa.sum(), 1e-12))
        rep['fold_bare'] = float(qa[qs <= 1.0e-3].sum() / max(qa.sum(), 1e-12))
        log(f'[lobster_sculpt] the folds: {rep["fold_vertices"]:,} membrane vertices folded, their share\'s mean '
            f'{rep["fold_cover"] * 100:.0f} % of {rep["fold_area_mm2"]:.0f} mm^2 of membrane (bare {rep["fold_bare"] * 100:.1f} '
            f'%), {rep["fold_voxels"]:,} voxels moved, the deepest {rep["fold_deepest_mm"]:.3f} mm '
            f'({time.time() - t0:.0f}s)')
    if prims:
        add_strokes(G, prims, log=log)
    G.redistance()
    rep['seconds'] = float(time.time() - t0)
    log(f'[lobster_sculpt] the strokes and the relevel ({rep["seconds"]:.0f}s)')
    return G, rep


def add_strokes(G, prims, log=print):
    """the strokes into the field (x4 m), one batch per kind and k (voxel.strokes: the batch's exact union, smooth-unioned
    with the field at its k; A0: a kind's k follows each stroke's foot, STROKE_SHAPE foot)"""
    for kind, k in sorted(set((p['kind'], p['k']) for p in prims)):
        ps = [p for p in prims if p['kind'] == kind and p['k'] == k]
        A = np.array([p['a'] for p in ps]) * SC_M
        B = np.array([p['b'] for p in ps]) * SC_M
        G.strokes(VX.STROKE_CONE, A, B, np.array([p['ra'] for p in ps]) * SC_M,
                  np.array([p['rb'] for p in ps]) * SC_M, 'add', k=k * SC_M)
        log(f'[lobster_sculpt] strokes: {len(ps)} {kind} (k {k} mm)')


def _wobble(P, seed, size):
    """a smooth scalar field in -1..1 over points (life mm): six sines along seeded directions, wavelengths size..2 size"""
    rng = np.random.default_rng(seed)
    w = np.zeros(len(P))
    for _ in range(6):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        w += np.sin(P @ d * (2.0 * np.pi / (size * rng.uniform(1.0, 2.0))) + rng.uniform(0.0, 2.0 * np.pi))
    return w / 6.0 * 1.8


def fold_stations(V_life, Q, region, axis_o, axis_d, which=('membrane', 'sleeve'), log=None):
    """the membranes' folds run parallel to the membrane's RIM (a flexing arthrodial membrane folds along the joint's
    margin; the prototype's stations across the shell's long axis drew straight cuts over the dactyl's base face): the
    station field t per limit vertex is its distance from where the membrane meets the chitin, SIGNED (+ in the
    membrane, - in the chitin beside it) and smoothed ACROSS that rim, piece by piece (the rim is the cage's region
    boundary, stepping from quad to quad: the raw distance's iso-lines drew a stepped zigzag of folds over the
    carpus's wrist membrane); a shell all membrane (a sleeve) has no rim, so its stations run along the joint's axis
    (o, d: life mm). The lines wander (WRINKLE wobble: t displaced by a smooth field). fold_carve sinks a valley every
    WRINKLE pitch of t, by the folds' share (0 from the rim to its furthest step, the rim's largest smoothed station,
    +0.04..+1.05 mm on the claws' pieces; 1 from WRINKLE fade further in: a bare strip along every rim).
    (Two earlier versions carved primitives: a ball at every limit vertex within 0.06 mm of a level drew rows of
    separate dents, the socket's membrane a dotted lace; capsules along the iso-lines were continuous, but a carve of
    radius r holds its depth only on a flat: on the wrist's concave membrane the 0.9 mm ones cut 0.4 mm into the walls
    and the low's points left the true voxels, x06 gate 5. And the first displacement smoothed the membrane's own
    distance alone, each edge one step, its ends free: on the limit's long thin quads (0.04 x 0.3-0.46 mm) the 1.5
    mm reached ~6 mm, the rim's stations rose to 1-7.7 mm, and with the share's zero at the rim's largest station the
    membranes stood BARE from the rim inward, the part that shows: no fold on 37 % of the carpus's membrane, 70 % of
    the crusher dactyl's, all of the cutter dactyl's; measured 11-09, scratch x6_fold_share_probe. A smoothing across
    the rim leaves a linear field as it is: the rim stays at 0 and the pitch holds.)
    Returns (t per limit vertex: the membranes and the chitin margin, 0 elsewhere; the folds' share per limit vertex)"""
    import scipy.sparse as sp_
    from scipy.sparse.csgraph import connected_components, dijkstra
    from scipy.sparse.linalg import spsolve
    V_life = np.asarray(V_life, np.float64)
    n = len(V_life)
    fq = np.isin(np.asarray(region), which)
    if not fq.any():
        return np.zeros(n), np.zeros(n)
    Qm = Q[fq]
    vm = np.unique(Qm)
    vc = np.unique(Q[~fq]) if (~fq).any() else np.zeros(0, np.int64)
    rim = np.intersect1d(vm, vc)
    mem = np.zeros(n, bool)
    mem[vm] = True
    t = np.zeros(n)
    amp = mem.astype(np.float64)                       # (a sleeve has no rim: its folds run to its ends)
    wv = vm
    if len(rim):
        def graph(Qs, diagonals):
            """the quads' edges (and diagonals) as a symmetric length graph over all the limit's vertices"""
            pr = [(0, 1), (1, 2), (2, 3), (3, 0)] + ([(0, 2), (1, 3)] if diagonals else [])
            a_ = np.concatenate([Qs[:, i] for i, _ in pr])
            b_ = np.concatenate([Qs[:, j] for _, j in pr])
            key = np.unique(np.minimum(a_, b_) * n + np.maximum(a_, b_))
            a_, b_ = key // n, key % n
            L = np.linalg.norm(V_life[a_] - V_life[b_], axis=1)
            return sp_.coo_matrix((np.r_[L, L], (np.r_[a_, b_], np.r_[b_, a_])), shape=(n, n)).tocsr()
        # the limit near the membranes only (a big shell's Dijkstra would walk all of it)
        pad = WRINKLE['margin'] * WRINKLE['smooth'] + 1.0
        lo, hi = V_life[vm].min(0) - pad, V_life[vm].max(0) + pad
        Qn = Q[((V_life[Q] >= lo) & (V_life[Q] <= hi)).all((1, 2))]
        # each vertex's distance from the rim and its nearest rim vertex (over edges and quad diagonals: edges alone
        # measure a slanted rim's distance up to 41 % long); the membrane's pieces by its own edges
        d, _, src = dijkstra(graph(Qn, True), indices=rim, min_only=True, return_predecessors=True)
        ok = np.isfinite(d)
        _, lab = connected_components(graph(Qm, False), directed=False)
        piece = np.where(ok, lab[np.where(ok, src, 0)], -1)
        sd = np.where(mem, d, -d)
        Tn = tris(Qn)
        wv = np.zeros(n, bool)
        amp[:] = 0.0
        for k in np.unique(lab[vm]):
            mk = mem & (lab == k)
            half = float(d[mk].max())
            if not np.isfinite(half):                  # (a piece with no rim in reach: no station, no share)
                continue
            s = min(WRINKLE['smooth'], WRINKLE['narrow'] * half)
            dom = mk | (~mem & (piece == k) & (d <= WRINKLE['margin'] * s))
            T = Tn[dom[Tn].all(1)]
            vk = np.unique(T)
            loc = -np.ones(n, np.int64)
            loc[vk] = np.arange(len(vk))
            m_ = len(vk)
            # the cotangent Laplacian and lumped masses: the smoothing a length in mm, the same along a long thin
            # quad's two sides; an obtuse pair's negative weight clamped
            r_, c_, w_ = [], [], []
            for a, b, c in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
                u, v = V_life[T[:, a]] - V_life[T[:, c]], V_life[T[:, b]] - V_life[T[:, c]]
                r_.append(loc[T[:, a]])
                c_.append(loc[T[:, b]])
                w_.append(0.5 * (u * v).sum(1) / np.maximum(np.linalg.norm(np.cross(u, v), axis=1), 1e-12))
            r_, c_, w_ = np.concatenate(r_), np.concatenate(c_), np.concatenate(w_)
            Wm = sp_.coo_matrix((np.r_[w_, w_], (np.r_[r_, c_], np.r_[c_, r_])), shape=(m_, m_)).tocsr()
            Wm.data = np.maximum(Wm.data, 1.0e-4)
            Lap = sp_.diags(np.asarray(Wm.sum(1)).ravel()) - Wm
            M = np.zeros(m_)
            ar = 0.5 * np.linalg.norm(np.cross(V_life[T[:, 1]] - V_life[T[:, 0]], V_life[T[:, 2]] - V_life[T[:, 0]]), axis=1)
            for j in range(3):
                np.add.at(M, loc[T[:, j]], ar / 3.0)
            t[vk] = spsolve((sp_.diags(M) + s * s * Lap).tocsc(), M * sd[vk])
            wv[vk] = True
            # the folds' share, on the SMOOTHED stations: 0 up to the rim's largest (the rim is the cage's stepped
            # region boundary: every step of it stays at 0, so no valley ends in a step there), 1 from WRINKLE fade
            # further in. (From the raw distance the share's edge followed the steps, and the first valleys along a
            # stepped rim broke into a zigzag: x06's knee, LOOKED)
            rk = t[rim[lab[rim] == k]]
            a0 = float(rk.max())
            x = np.clip((t[mk] - a0) / WRINKLE['fade'], 0.0, 1.0)
            amp[mk] = x * x * (3.0 - 2.0 * x)
            if log:
                log(f'[lobster_sculpt]   a membrane piece: {int(mk.sum()):,} vertices, half width {half:.2f} mm, smoothed '
                    f'over {s:.2f} mm on {m_:,} vertices; its rim\'s station p5 / p95 / max {np.percentile(rk, 5):+.2f} / '
                    f'{np.percentile(rk, 95):+.2f} / {a0:+.2f} mm (the share\'s zero), its deepest {float(t[mk].max()):.2f}')
        wv = np.nonzero(wv)[0]
    else:
        dd = np.asarray(axis_d, np.float64)
        dd /= np.linalg.norm(dd)
        t[vm] = (V_life[vm] - np.asarray(axis_o)) @ dd
        t[vm] -= float(np.floor(t[vm].min() / WRINKLE['pitch']) * WRINKLE['pitch'])
    t[wv] = t[wv] + WRINKLE['wobble'][0] * WRINKLE['pitch'] * _wobble(V_life[wv], 11, WRINKLE['wobble'][1])
    return t, amp


@wp.kernel(module='unique')     # (its own small module, as x06's kernels are)
def k_fold(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), F: wp.array(dtype=wp.int32), tv: wp.array(dtype=float),
           av: wp.array(dtype=float), reach: float, out_t: wp.array(dtype=float), out_a: wp.array(dtype=float),
           out_s: wp.array(dtype=float)):
    """a voxel's station, share and side (fold_carve): the limit's closest point within reach, its triangle's three
    corners weighed by the point's barycentric coordinates; the side +1 where the voxel stands on the triangle's
    outward face, -1 behind it; the share -1 where the limit lies further off"""
    i = wp.tid()
    q = wp.mesh_query_point_no_sign(mesh, pts[i], reach)
    if q.result:
        a0 = F[3 * q.face]
        a1 = F[3 * q.face + 1]
        a2 = F[3 * q.face + 2]
        w = 1.0 - q.u - q.v
        out_t[i] = tv[a0] * q.u + tv[a1] * q.v + tv[a2] * w
        out_a[i] = av[a0] * q.u + av[a1] * q.v + av[a2] * w
        p0 = wp.mesh_eval_position(mesh, q.face, 1.0, 0.0)
        p1 = wp.mesh_eval_position(mesh, q.face, 0.0, 1.0)
        p2 = wp.mesh_eval_position(mesh, q.face, 0.0, 0.0)
        c = p0 * q.u + p1 * q.v + p2 * w
        out_s[i] = 1.0
        if wp.dot(pts[i] - c, wp.cross(p1 - p0, p2 - p0)) < 0.0:
            out_s[i] = -1.0
    else:
        out_a[i] = -1.0


def fold_values(V_life, Q, t, amp, P_life, reach):
    """the stations and shares (fold_stations, per limit vertex) at points P (life mm): each point's closest point on
    the limit within reach, linear over its triangle (k_fold). Returns (t, share, side; the share -1 past the reach;
    the side +1 before the limit's outward face, -1 behind it).
    (The first version weighed the 4 nearest limit VERTICES by inverse squared distance: flat at every vertex, a jump
    where the four change: on the limit's long thin quads each valley came out as steps at the vertex rings, fine
    contour lines in x06's close-ups, the normal off by p50 5 / p90 18 degrees; scratch x6_fold_terrace_probe)"""
    V_life = np.asarray(V_life, np.float64)
    P_life = np.asarray(P_life, np.float64)
    c0 = 0.5 * (P_life.min(0) + P_life.max(0))         # (about the points' middle: float32 keeps a hundredth of a micron)
    T = tris(Q).astype(np.int32)
    F = wp.array(T.ravel(), dtype=wp.int32)
    mesh = wp.Mesh(points=wp.array((V_life - c0).astype(np.float32), dtype=wp.vec3), indices=F)
    ot = wp.zeros(len(P_life), dtype=float)
    oa = wp.zeros(len(P_life), dtype=float)
    os_ = wp.zeros(len(P_life), dtype=float)
    wp.launch(k_fold, dim=len(P_life), inputs=[mesh.id, wp.array((P_life - c0).astype(np.float32), dtype=wp.vec3), F,
                                               wp.array(np.asarray(t, np.float32), dtype=float),
                                               wp.array(np.asarray(amp, np.float32), dtype=float), float(reach), ot, oa,
                                               os_])
    return ot.numpy().astype(np.float64), oa.numpy().astype(np.float64), os_.numpy().astype(np.float64)


def fold_carve(G, V_life, Q, t, amp, open_half=0.0, log=print):
    """the membranes' folds as a DISPLACEMENT of the high's field (x4 m): each voxel within WRINKLE reach of the limit
    takes the station t and share of its closest point there (fold_stations, fold_values) and sinks by depth x (1 -
    cos(2 pi t / pitch)) / 2 x the share: valleys of exactly `depth` on any curvature, a crest every pitch. A closed
    shell's field takes the move as it is (its surface sinks into its solid). An OPEN sleeve (open_half: its SHELL's
    half thickness, life mm) is a sheet |s| - half: there the SHEET moves, both faces together (|s + move| - half, s
    signed by the side): added to the field as on a solid, the move thinned the sheet from both faces, and a valley as
    deep as the half thickness (0.15 of 0.15 mm) cut it through: rows of holes along every valley of all four sleeves
    (333-536 of a sleeve's 8,448-10,560 limit vertices found no high; x06's sleeve views, LOOKED 11-09). Returns
    (voxels moved, the deepest move mm)"""
    mem = amp > 0.0
    if not mem.any():
        return 0, 0.0
    V_life = np.asarray(V_life, np.float64)
    reach = WRINKLE['reach']
    lo, hi = V_life[mem].min(0) - 2.0 * reach, V_life[mem].max(0) + 2.0 * reach
    ijk = G.ijk.numpy()                                # (the box by voxel index: positions only for its voxels)
    i_lo = np.floor(((lo + reach) * SC_M - G.origin) / G.vs).astype(np.int64)
    i_hi = np.ceil(((hi - reach) * SC_M - G.origin) / G.vs).astype(np.int64)
    box = np.nonzero(((ijk >= i_lo) & (ijk <= i_hi)).all(1))[0]
    if not len(box):
        return 0, 0.0
    Pb = (G.origin + ijk[box].astype(np.float64) * G.vs) / SC_M
    del ijk
    inside = ((V_life >= lo) & (V_life <= hi)).all(1)
    tv, sh, side = fold_values(V_life, Q[inside[Q].any(1)], t, amp, Pb, reach)        # (the limit's quads touching that box)
    near = sh > 0.0
    box, Pb, tv, sh, side = box[near], Pb[near], tv[near], sh[near], side[near]
    dep = WRINKLE['depth'] * (1.0 - WRINKLE['vary'][0] * (0.5 + 0.5 * _wobble(Pb, 29, WRINKLE['vary'][1])))
    dv = dep * sh * 0.5 * (1.0 - np.cos(2.0 * np.pi * tv / WRINKLE['pitch']))
    L = G.val.numpy().astype(np.float64)
    if open_half > 0.0:
        h = open_half * SC_M                           # the sheet's own signed offset s = side x (L + half): it moves in
        L[box] = np.abs(side * np.maximum(L[box] + h, 0.0) + dv * SC_M) - h
    else:
        L[box] += dv * SC_M                            # (+: the surface moves in)
    G.val = wp.array(L.astype(np.float32), dtype=wp.float32)
    return int((dv > 1.0e-4).sum()), float(dv.max()) if len(dv) else 0.0


# ============================================================================================ the fillets
def closed_clay(prog, lo, hi, log=print):
    """the clay (its sdf.Program, x4 m) as a SparseSDF, relevelled to true distance, then CLOSED at FILLET r (grow r,
    relevel, shrink r, relevel: inside corners sharper than r rounded to r). Returns (the clay's grid relevelled, its
    values before the closing, the closed values) on one topology"""
    r = FILLET['r'] * SC_M
    G = VX.SparseSDF(prog, lo, hi, voxel=FILLET['voxel'], band=FILLET['band'], log=log)
    G.redistance()
    v0 = G.val.numpy().copy()
    # X6 fix (the X5b / X6 check, 11-10: voxel.SparseSDF.offset(d) does val -= d, so offset(+r) GROWS the solid): grow
    # first, then shrink, a CLOSING. The two calls stood the other way round, an opening, which leaves inside corners
    # sharp (the crusher dactyl's base A / B measured r 0.188 / 0.176 mm on the high; swapped, the check's in-memory
    # run read 0.421 / 0.414)
    G.offset(r)
    G.redistance()
    G.offset(-r)
    G.redistance()
    # x6fix_x7 (11-11, Opus 5.5): the grid's closing only MARKS the corners; near them the closed field is EXACT
    # (closing_exact_near_corners: the grid's fillet radius erred with the crease's run across the grid)
    vc, _ = closing_exact_near_corners(G, v0, G.val.numpy().copy(), log=log)
    G.val = wp.array(vc, dtype=wp.float32)
    return G, v0, vc


def closing_exact_near_corners(G, v0, vc, log=print):
    """x6fix_x7 (11-11, Opus 5.5): the closed field recomputed EXACTLY within the carve's reach of the corners the grid's
    closing marked. WHY: at r 0.40 mm = 4 voxels of 0.1 mm the relevel's error sizes a fillet by how its crease runs
    across the grid: on the A0 clay the crusher dactyl's base corner A read r 0.41-0.50, corner B 0.27 over a third of
    its crease (the closed clay alone, scratch x6fix_x7/x6_fillet_closed.py; x06 gate 4 on the high: B p50 0.346, 33 %
    under 0.30). A 0.05 mm grid halves the error (B 0.32-0.40) at 8 x the clay grid's memory; a smoothing pass lifts B
    but pushes A past 0.50. HOW, by the closing's definition: closing = the complement of (V' + B_r), V' = {v0 >= r}
    (the void eroded by r), so closed(x) = v0(x) where v0 >= r, else r - dist(x, S_r), S_r = {v0 = r} the clay's offset
    surface, sampled by projecting the voxels within one voxel of it onto it (two Newton steps on the field's B-spline
    normal), searched with a k-d tree. The fillet is then the envelope of radius-r spheres round S_r: radius r whichever
    way the crease runs (between neighbouring samples ~0.1 mm apart the envelope dips 3 um). Recomputed: every voxel of
    the relevelled band within FILLET fade[1] + cut + 0.1 mm (the carve's reach and its guard's step) + 2 voxels of a
    marked voxel; elsewhere the grid's values stand. Measured on the whole crusher dactyl (CPU, 7.66 M voxels): A r
    0.42-0.48 mm (p50 0.456), B 0.385-0.447 (p50 0.430), none under 0.30; the exact values moved from the grid's at the
    corners p50 0.004 / max 0.018 mm, on the plain shell beside them p50 0.0006 / p99 0.007 mm. Returns (values, report)"""
    from scipy.spatial import cKDTree
    F = FILLET
    r = F['r'] * SC_M
    vs = G.vs
    K = ((v0 - vc) > F['eps'] * SC_M) & (np.abs(v0) < 2.0 * r)
    rep = dict(marked=int(K.sum()))
    if not K.any():
        return vc, rep
    P = G.positions()
    reach = (F['fade'][1] + F['cut'] + 0.1) * SC_M + 2.0 * vs
    inb = np.abs(v0) < F['band']                    # the relevelled band (FILLET band is in metres at x4)
    dK = np.full(len(P), np.inf)
    dK[inb] = cKDTree(P[K]).query(P[inb], k=1, distance_upper_bound=reach + 2.0 * r + 0.0016, workers=-1)[0]
    redo = dK <= reach
    # S_r's samples: the voxels within one voxel of v0 = r near the corners, projected onto it with the field v0 (the
    # grid's values set back to v0 for the reads)
    near_s = (np.abs(v0 - r) < vs) & np.isfinite(dK)
    keep_val = G.val
    G.val = wp.array(v0.astype(np.float32), dtype=wp.float32)
    Q = P[near_s]
    for _ in range(2):
        Q = Q - (G.eval(Q).astype(np.float64) - r)[:, None] * G.normals(Q)
    f = G.eval(Q).astype(np.float64)
    G.val = keep_val
    Q = Q[np.abs(f - r) < 0.05 * vs]
    rep.update(redo=int(redo.sum()), samples=int(len(Q)))
    if len(Q) < 8:
        return vc, rep
    d = cKDTree(Q).query(P[redo], k=1, workers=-1)[0]
    ve = np.where(v0[redo] >= r, v0[redo], r - d)
    dv = np.abs(ve - vc[redo]) / SC_M
    ns = np.abs(vc[redo]) < 2.0 * r                 # (near the surface: at the corners, and on the plain shell beside)
    kc, pl = K[redo] & ns, ~K[redo] & ns
    rep.update(dv_corner_p50=float(np.median(dv[kc])) if kc.any() else 0.0, dv_corner_max=float(dv[kc].max()) if kc.any()
               else 0.0, dv_plain_p50=float(np.median(dv[pl])) if pl.any() else 0.0,
               dv_plain_p99=float(np.percentile(dv[pl], 99)) if pl.any() else 0.0)
    out = vc.copy()
    out[redo] = ve
    log(f'[lobster_sculpt] the closing exact near {rep["marked"]:,} marked voxels: {rep["redo"]:,} voxels from '
        f'{rep["samples"]:,} points of the offset surface; moved from the grid\'s closing near the surface: at the corners '
        f'p50 {rep["dv_corner_p50"]:.3f} max {rep["dv_corner_max"]:.3f} mm, on the plain shell p50 {rep["dv_plain_p50"]:.4f} '
        f'p99 {rep["dv_plain_p99"]:.3f} mm')
    return out.astype(np.float32), rep


def fillet_carve(Gh, Gc, v0, vc, log=print):
    """the high's voxels near the clay's inside corners carved to the closed clay (module docstring): K = the clay grid's
    voxels the closing changed by more than FILLET eps (within 2 r of the clay's surface); w from their distance; H = L +
    w (smax(L, Cc, k) - L). Returns a dict of what it did"""
    from scipy.spatial import cKDTree
    r = FILLET['r'] * SC_M
    nr, cut = FILLET['near'] * SC_M, FILLET['cut'] * SC_M
    Pc = Gc.positions()
    K = ((v0 - vc) > FILLET['eps'] * SC_M) & (np.abs(v0) < 2.0 * r)
    rep = dict(marked=int(K.sum()))
    if not K.any():
        return rep
    KP = Pc[K]
    Kb = np.abs(Gh.eval(KP)) <= nr                  # a corner the limit bridges: the limit within `near` of it
    rep['bridged'] = int(Kb.sum())
    if not Kb.any():
        return rep
    tree = cKDTree(KP[Kb])
    Ph = Gh.positions()
    L = Gh.val.numpy().astype(np.float64)
    near = np.abs(L) <= nr
    dist, _ = tree.query(Ph[near], distance_upper_bound=FILLET['fade'][1] * SC_M)
    f0, f1 = FILLET['fade'][0] * SC_M, FILLET['fade'][1] * SC_M
    t = np.clip((dist - f0) / (f1 - f0), 0.0, 1.0)
    w = np.where(np.isfinite(dist), 1.0 - t * t * (3.0 - 2.0 * t), 0.0)
    idx = np.nonzero(near)[0][w > 0]
    w = w[w > 0]
    # a voxel is cut only where the closed clay is SOLID one cut (+0.1 mm) further in along the limit's normal: true under
    # a bridged corner (the clay's corner lies under the limit's chord), false under a plate the clay does not have (x06's
    # first dactyl run cut through its 0.43 mm base fan, the holes a blocky staircase in the views)
    nh = Gh.normals(Ph[idx])
    deep = Gc.eval(Ph[idx] - nh * ((FILLET['cut'] + 0.1) * SC_M)) < 0.0
    rep['guarded'] = int((~deep).sum())
    idx, w = idx[deep], w[deep]
    Cc = Gc.eval(Ph[idx]).astype(np.float64)        # the closed clay (its band; past it the clay's program)
    Lh = L[idx]
    k = FILLET['k'] * SC_M
    hh = np.clip(0.5 - 0.5 * (Cc - Lh) / k, 0.0, 1.0)
    smax = Cc * (1.0 - hh) + Lh * hh + k * hh * (1.0 - hh)          # smooth max (the house smin's polynomial, mirrored)
    H = Lh + w * np.clip(smax - Lh, 0.0, cut)                         # only removes, at most `cut`
    L[idx] = H
    import warp as wp
    Gh.val = wp.array(L.astype(np.float32), dtype=wp.float32)
    rep.update(touched=int(len(idx)), carved_mm_max=float((H - Lh).max() / SC_M), carved_voxels=int(((H - Lh) >
                                                                                                     1e-7).sum()),
               corners=KP[Kb] / SC_M)
    log(f'[lobster_sculpt] fillets: {rep["marked"]} clay voxels the closing changed ({rep["bridged"]} by the limit), '
        f'{rep["touched"]} high voxels in reach, {rep["carved_voxels"]} carved, deepest {rep["carved_mm_max"]:.3f} mm at '
        f'life')
    return rep


# ============================================================================================ the micro masks
def micro_masks(V_life, N, region_v, prims, occlusal=None):
    """per limit vertex: M4 = (pit density, setae amount, groove profile, cells amount), D3 = the setae direction (the
    beetle's micro_masks layout); the strokes' footprints and the occlusal band polished (no cells, no pits)"""
    n = len(V_life)
    M4 = np.zeros((n, 4), np.float32)
    D3 = np.zeros((n, 3), np.float32)
    mem = np.isin(region_v, ('membrane', 'sleeve'))
    M4[:, 0] = np.where(mem, 0.0, 1.0)
    M4[:, 3] = 1.0
    if occlusal is not None:
        M4[occlusal, 0] = 0.0
        M4[occlusal, 3] = 0.0
    for p in prims:
        dd = sd_cone(V_life, p['a'], p['b'], p['ra'], p['rb'])
        pol = dd < 0.6 * p['foot_r']
        M4[pol, 0] = 0.0
        M4[pol, 3] *= np.clip(dd[pol] / (0.6 * p['foot_r']), 0.0, 1.0).astype(np.float32)
    D3[:] = np.array([0.0, 0.0, 1.0], np.float32)
    return M4, D3


def micro_params(V_life, Q, parent, region, prims, seed0=7, log=None):
    """ONE shell's micro layer as the bake and the views read it (life mm): the rows its regions use (REGION_ROW), each
    limit triangle's offset into `par`, the vertex normals and masks (micro_masks), and `par`: each row's parameters
    (stag_beetle_sculpt.params) and, for a granular row (its recipe's `grain`), the GRANULES' table after them
    (params_full's layout). The granules' sites are ONE set per shell over all its chitin (grain_sites with GRANULES:
    relaxed on this limit; no site on a membrane or a stroke's polished foot), so a region boundary cuts no granule:
    the rows differ in amplitude and pits only. Returns dict(rows, par, tri, off, vn, m4, d3, census)"""
    V_life = np.asarray(V_life, np.float64)
    rows = sorted(set(REGION_ROW.get(str(r_), 'lobster_chitin') for r_ in region))
    regq = np.array([str(region[p_]) for p_ in parent])
    rq = np.array([rows.index(REGION_ROW.get(r_, 'lobster_chitin')) for r_ in regq], np.int64)
    T = tris(Q).astype(np.int32)
    VN = vertex_normals(V_life, Q)
    reg_v = np.full(len(V_life), 'chitin', object)
    for j in range(4):
        reg_v[Q[:, j]] = regq
    M4, D3 = micro_masks(V_life, VN, reg_v, prims)
    # the crushing molars' OCCLUSAL faces are worn smooth (n04's molars: polished lumps; x06's teeth shot drew the
    # granules marching over them). The cage's `molar` region also runs down the finger's broad flank (polishing all
    # of it left a bald window on the fixed finger's face, LOOKED), so only where the molar turns off the broad faces'
    # normal (broad_n(): the claw's thin axis from the rig): the cells fade out between |n . broad| 0.75 and 0.45, the
    # pits go with them
    mol = reg_v == 'molar'
    if mol.any():
        x = np.clip((0.75 - np.abs(VN @ broad_n())) / 0.30, 0.0, 1.0)
        pol = np.where(mol, x * x * (3.0 - 2.0 * x), 0.0)
        M4[:, 3] *= (1.0 - pol).astype(np.float32)
        M4[pol > 0.5, 0] = 0.0
    gran = [r_ for r_ in rows if SC.RECIPE[r_].get('grain')]
    hdr = tail = census = None
    if gran:
        d0 = GRANULES['spacing']
        cfg = dict(density=2.0 / (np.sqrt(3.0) * d0 * d0), aniso=1.0, flow_rot=0.0, rot_jit=0.0, mod_amp=0.0,
                   kappa=GRANULES['size'] / d0, **{k_: GRANULES[k_] for k_ in ('size_jit', 'ht_jit', 'iters', 'step', 'seed')})
        w = np.where(np.isin(reg_v, ('membrane', 'sleeve')), 0.0, M4[:, 3])
        if (w > 0.005).any():
            S = SC.grain_sites(V_life, T, VN, w, cfg=cfg, log=log)
            hdr, tail = SC.grain_table(S, cell=GRANULES['cell'])
            census = S['census']
    blocks, offs, o = [], [], 0
    for k_, r_ in enumerate(rows):
        p = SC.params(r_, seed0 + k_, grain_ok=True)
        if r_ in gran and tail is not None:
            p[27] = 1.0
            p[30:33] = hdr['origin']
            p[33] = hdr['cell']
            p[34:37] = hdr['dims']
            p = np.concatenate([p, tail])
        offs.append(o)
        blocks.append(p)
        o += len(p)
    off = np.asarray(offs, np.int32)[rq]
    return dict(rows=rows, par=np.concatenate(blocks).astype(np.float32), tri=T, off=np.concatenate([off, off]), vn=VN,
                m4=M4, d3=D3, census=census)


def feature_masks(P_life, prims):
    """per point (life mm): the strokes' paint masks for the material pass (plan §9: the tubercle tips cream / white, the
    teeth and denticles cream): (tip, any stroke), each 0..1 from the point's height up its stroke"""
    P = np.atleast_2d(P_life)
    tip = np.zeros(len(P))
    anyf = np.zeros(len(P))
    for p in prims:
        dd = sd_cone(P, p['a'], p['b'], p['ra'], p['rb'])
        inside = dd < 0.05
        if not inside.any():
            continue
        u = np.clip(((P - p['anchor']) @ p['axis']) / max(p['height'], 1e-6), 0.0, 1.0)
        anyf = np.maximum(anyf, inside * np.clip(u / 0.15, 0.0, 1.0))
        tip = np.maximum(tip, inside * np.clip((u - 0.45) / 0.35, 0.0, 1.0))
    return tip, anyf


# per life mm; AO shares; the WORLD-SPACE terms (the bind pose: y up, the ground y 0): drag = (the down-facing share -n_y
# where it starts, its ramp, the height over the ground it fades out by in mm, its amount): a claw rests and is pushed
# along on its ventral margin; silt = (the up-facing share n_y where it starts, its ramp, its amount): fines settle on
# up-facing shell that nothing rubs
# cav = (the fine occlusion's share where the crevice term starts, its ramp): the craft guide 10.8's broad and fine
# occlusion: AO at 6 mm for the forms, the cavity at 0.6 mm (bake.py's cav_r 2.5 mm at x4) for the stroke feet, the
# folds and the fillets
WEAR = dict(curv=1.5, ao=(0.55, 0.40), tip=0.8, grime=(0.75, 0.50), cav=(0.80, 0.40), drag=(0.25, 0.60, 14.0, 0.6),
            silt=(0.60, 0.35, 0.3))


def wear_maps(curv, ao, tip, up=None, y_mm=None, cav=None):
    """the WEAR and GRIME drivers from the bake's maps (x06 gate 7 draws them; X9's material reads them; each with its
    physical cause, the craft guide 10.1): wear where the shell is CONVEX (2H per life mm over WEAR curv: radius ~1.3
    mm and tighter) AND OPEN (AO over ao[0], full at ao[0] + ao[1]): the arrises that meet rock and other claws (10.29),
    plus the strokes' tips (feature_masks: the white-tipped tubercles, the teeth' crowns) at WEAR tip; grime where
    nothing rubs (10.32): the broad AO under grime[0] (full by grime[0] - grime[1]) and the fine CAVITY under cav[0]
    (the crevices: the stroke feet, the folds, the fillets). WORLD SPACE (up = the macro normal's world y (10.12), y_mm
    = the height over the ground; the bake's normal and position passes carry both): the ventral DRAG added to the
    wear (down-facing and near the ground: 10.39), SILT added to the grime (up-facing, where the wear leaves it: 10.35)"""
    wear = np.clip(curv / WEAR['curv'], 0, 1) * np.clip((ao - WEAR['ao'][0]) / WEAR['ao'][1], 0, 1) + WEAR['tip'] * tip
    if up is not None and y_mm is not None:
        d0, d1, dy, da = WEAR['drag']
        wear = wear + da * np.clip((-up - d0) / d1, 0, 1) * np.clip(1.0 - y_mm / dy, 0, 1)
    wear = np.clip(wear, 0, 1)
    grime = np.clip((WEAR['grime'][0] - ao) / WEAR['grime'][1], 0, 1)
    if cav is not None:
        grime = np.maximum(grime, np.clip((WEAR['cav'][0] - cav) / WEAR['cav'][1], 0, 1))
    if up is not None:
        s0, s1, sa = WEAR['silt']
        grime = np.clip(grime + sa * np.clip((up - s0) / s1, 0, 1) * (1.0 - wear), 0, 1)
    return wear, grime


def save_prims(path, per_shell):
    """the strokes' primitives per shell (life mm) for X7's bake and X9's masks"""
    def row(p):
        return {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in p.items()}
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump({nm: [row(p) for p in ps] for nm, ps in per_shell.items()}, fh, indent=1)
