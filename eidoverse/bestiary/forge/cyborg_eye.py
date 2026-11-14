"""CYBORG EYES, the forge side of the EYES layer (work/bestiary/research/CYBORG_PLAN.md §4.3.1, §4.3.2, §5.5, §8 C4; its
addendum A.3, A.5.1, A.7 (U3, U4, U5, U11, U12), A.8's C4 row and the lead's A.9 decisions; PLAN.md 10-22 "C4"): THE EYE
IMPLANT 'lens', a part that REPLACES the organic eyeball on its own joint. Skye's standing rule, said twice: parts MATCH
THE BODY SLOT; an eye implant goes in an eye socket and nothing else (remix/slots.py: eye_implant fits kind 'eye',
interface 'ball'). It lies inside the eyeball's sphere (every low vertex within Re + 0.1 mm of its centre: G4), so the
lids, the socket carve and the head set's baked eyeball occluder stay valid and the skin is not rebaked.

THE RINGS come from the MEASURED LENS (research/cyborg_work/REFS.md §4.8, photo p10: a 50 mm f/1.4's front, scaled by
its own Ø58 filter thread; refs_data/photos/p10_measure.json [M-rf]), with the front lip at the radius the plan holds
always visible (§4.3.1: everything within 40 deg of the axis, Re sin 40 = 9.64 mm):
    front lip (the BEZEL)   r 8.884 - 9.642 mm   the lip's outer edge (p10: 1170 px = 72.81 mm, the lip's D)
    name ring (EMISSIVE)    r 7.860 - 8.884 mm   p10 1078 / 1170 = 0.9214 of the lip: the plan's name-ring band
    filter thread (groove)  r 7.680 mm           p10  932 / 1170 = 0.7966 (the thread, the photo's scale)
    stepped BAFFLE          r 4.689 - 7.680 mm   2.992 mm wide; about 8 concentric black steps (REFS §4.8's look)
    GLASS                   r < 4.689 mm         p10  569 / 1170 = 0.4863 (the visible glass)
and the glass RECESSED 2.7 mm below the lens's cavity rim (A.3.1 / A.9: a study-T companion character's lens 25.6 mm below its rim on a
90.0 mm disc, 0.569 of its radius [D-ad C2 from R-tt]; inward only, A.3.3: a ball implant takes no ring proud of it).

THE FRONT FOLLOWS THE EYEBALL. The bezel and the name ring lie on the eyeball's sphere (the ring in a 0.2 mm channel),
the bezel parted from the housing by a 0.3 mm gap (the machinist's gap round a part in a bore, A.4.3 [H via kb]), the
cavity stepping down to the glass. A FLAT front (the lens's own) puts the lip face on the 40 deg plane and the ring
0.3 mm under it: its outer edge then sits 38.4 deg off the axis, and the head-on ray test put a third of the ring's
width under the lid's tuck at the diagonal saccade (yaw and pitch at once: an 11.26 deg tilt, not the plan's 10). On
the sphere the ring's edge sits at 36.3 deg and clears the lid's tuck by 0.49 mm there (gates: visibility()).

THE SACCADES (runtime/bestiary.js radialMotion): yaw (hash - 0.5) x 0.35 rad about the eye bone's y, pitch x 0.18 about
its z, applied as rest x Ry(yaw) x Rz(pitch): +-10.03 deg and +-5.16 deg, and both at once tilt the optical axis 11.26
deg, so the always-visible cone is 50 - 11.26 = 38.74 deg (r 9.39 mm on the sphere), not the plan's 40 (the yaw alone).

THE PART (the props' pipeline, §4.3.1): a REVOLVE profile about the optical axis (forge/sdf.py), sampled into its own
voxel grid (voxel.SparseSDF) and baked onto a low of revolved rings on the front (32 columns: U5's sagitta rule asks 20
for the eyeball at 0.2 mm) welded to an EQUI-ANGULAR cube-sphere back half (octopus_eye.eye_mesh's cube, its grid on
equal angles so its rim ring is the revolved part's 32 even columns), UV-charted POLAR (U4: a turned low charted
polar): the front a developed disc from the axis to 65 deg (true length along the profile, no seam on the visible
part; the seam ring at 65 deg stays under the lid at every saccade: 65 - 11.26 > 50), the hidden back a second disc
from the back pole at a tenth of the density, in its corner. One 512^2 set (A.9: 10 px/mm or more).

THE MATERIAL (§5.5, the cyborg rows of forge/cyborg.py, read only): the housing bead-blasted titanium (cyb_titanium),
the bezel machined titanium, the name ring the glazed glow strip (cyb_glow, its EMISSIVE MASK with the house's hot
centre: emit_centre 0.4 at the edges, A.5.3 / U12), the thread and the baffle black oxide (cyb_steel's black_oxide: a
dielectric film, metal 0, A.9 decision 1), the glass the robot body's glass row (A.5.1's cyb_glass: linear 0.005 at
roughness 0.03 [H via kb], ior 1.52 [C]). Packs: ORM (AO, roughness, metal), MASKS (R the primary tint region, G the
accent region, B the emissive mask, A wear: forge/cyborg_limb.py's channels, so one runtime cyborgMaterial reads both).

THE OCTOPUS WEARING IT: a STAGED EXPORT (splice()): a copy of an exported octopus glb with the eyeball on eye_L dropped
from the eye primitive (eye_R keeps the organic eye) and the implant appended as its own primitive and material,
skinned rigidly to eye_L (as t13 skins the eyes); t13 itself is not touched (C7 moves it there).

    D = design(); prog = build_sdf(D); L = build_low(D)
    res, info = bake_implant(D, L)                 (GPU)
    maps, st = material(D, L, res); export_glb(path, D, L, maps); splice(src_glb, dst_glb, D, L, maps)

Read with numpy, scipy and warp.
"""
import json
import math
import os
import struct

import numpy as np
import warp as wp

wp.set_module_options({'enable_backward': False})    # forward-only kernels: no adjoint code to compile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
TAU = 2.0 * math.pi

# ============================================================================================ the measured lens
# REFS §4.8, p10_measure.json 'lines': each ring's widest horizontal extent on the photo rotated so the front ellipse's
# major axis is horizontal (px), and its mm by the filter thread's own 'Ø58' [M-rf]
P10_PX = dict(lip=1170.0, name_ring=1078.0, thread=932.0, glass=569.0)
P10_MM = dict(lip=72.81, name_ring=67.09, thread=58.0, glass=35.41)
LENS = {k: v / P10_PX['lip'] for k, v in P10_PX.items()}          # fractions of the front lip's diameter
N_BAFFLE = 8                # "about 8 concentric black stepped baffle rings" (REFS §4.8, p10's look) [M-rf]
COMPANION_EYE = dict(lens_d=0.0900, recess=0.0256)    # a study-T companion character's head eye: a 90.0 mm disc 25.6 mm below its rim [R-tt]
RECESS = 2.7e-3             # A.9 / A.3.1: 0.568 of the glass radius (the companion character's 0.569) [D-ad C2]
SET_SIZE = 512              # A.9: the eye set 512^2
N_COLS = 32                 # the low's columns round the axis (U5: 20 for the eyeball at the 0.2 mm sagitta)
CUBE_N = 8                  # the cube-sphere back half's grid per face edge (4 x 8 = 32 rim columns)
SEAM_DEG = 65.0             # the front chart's rim (the visible part ends at 50 + 11.26 = 61.3 deg)
BACK_DENSITY = 0.10         # the hidden back's texel density relative to the front's (never seen: inside the socket)

# the [E] dimensions (each the look's to judge; the measured ones above set the radii)
DESIGN = dict(
    gap=0.30e-3,            # the bezel's gap in the housing's bore (A.4.3: 0.3 mm round a part [H via kb])
    gap_wall_min=0.01e-3,   # the housing's bore wall left under its rim round (sets the gap's floor)
    r_break=0.15e-3,        # the gap's rounds (the bezel's edge, the housing's rim, the floor's U: half the gap)
    channel=0.20e-3,        # the name ring's channel under the bezel's sphere (a light pipe set in its groove)
    r_ch_top=0.08e-3,       # the channel wall's top round (the bezel's inner edge)
    r_ch_foot=0.06e-3,      # its foot (concave)
    thread_w=0.36e-3,       # the filter thread's groove across its top, centred on the thread's radius (5 texels)
    thread_floor=0.12e-3,   # its floor's width
    thread_d=0.25e-3,       # its depth under the ring's face
    baffle_top=0.05e-3,     # the baffle's top tread under the ring's sphere at its radius
    glass_sag=0.35e-3,      # the glass's dome (a convex front element) [E: the look]
)

# ============================================================================================ the envelope
YAW_AMP = 0.35              # runtime/bestiary.js radialMotion: yaw = (pick - 0.5) x 0.35 rad (pick in [0, 1))
PITCH_AMP = 0.18            # pitch = (pick - 0.5) x 0.18 rad


def envelope(spec=None):
    """the octopus eye's numbers the implant must respect: the eyeball's radius, the lid aperture's half-angle, the
    saccades' extremes and the axis tilt with both at once, the always-visible cone (the plan's 40 deg from the yaw
    alone, and the true one), as dict (metres, degrees, radians where named)"""
    if spec is None:
        from .species import octopus
        spec = octopus.SPEC
    Re = float(spec['eyeball_r'])
    ap = float(min(spec['eye_ap']))
    yaw, pitch = 0.5 * YAW_AMP, 0.5 * PITCH_AMP
    x = pose_bone(yaw, pitch) @ np.array([1.0, 0.0, 0.0])
    tilt = math.degrees(math.acos(min(1.0, float(x[0]))))
    return dict(Re=Re, ap_deg=ap, yaw=yaw, pitch=pitch, yaw_deg=math.degrees(yaw), pitch_deg=math.degrees(pitch),
                tilt_deg=tilt, vis_plan_deg=40.0, r_vis_plan=Re * math.sin(math.radians(40.0)),
                vis_true_deg=ap - tilt, r_vis_true=Re * math.sin(math.radians(ap - tilt)))


def pose_bone(yaw, pitch):
    """the saccade's turn in the eye BONE's frame (x the optical axis): Ry(yaw) Rz(pitch), as radialMotion composes
    rest x Ry x Rz"""
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    Ry = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    Rz = np.array([[cp, -sp, 0.0], [sp, cp, 0.0], [0.0, 0.0, 1.0]])
    return Ry @ Rz


# the bone's axes in the implant's frame (x = h, y = u, z = out): x_b = out, y_b = u, z_b = out x u = -h
# (forge/rig.frame_from(out, +Y): y = up made perpendicular = octopus_eye.eye_axes' u)
B_IMP = np.array([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]])


def pose_matrix(yaw, pitch):
    """the saccade's turn in the IMPLANT's frame (z the optical axis)"""
    return B_IMP @ pose_bone(yaw, pitch) @ B_IMP.T


def saccade_poses(spec=None):
    """the nine extremes: rest, the four single-axis ones, the four diagonals: [(name, yaw, pitch)]"""
    env = envelope(spec)
    Y, P = env['yaw'], env['pitch']
    out = [('rest', 0.0, 0.0)]
    for nm, y, p in (('yaw+', Y, 0.0), ('yaw-', -Y, 0.0), ('pitch+', 0.0, P), ('pitch-', 0.0, -P),
                     ('yaw+ pitch+', Y, P), ('yaw+ pitch-', Y, -P), ('yaw- pitch+', -Y, P), ('yaw- pitch-', -Y, -P)):
        out.append((nm, y, p))
    return out


# ============================================================================================ the design
def design(spec=None, bezel_deg=40.0, recess=RECESS, n_baffle=N_BAFFLE, d=None):
    """every dimension of the 'lens' (metres; z along the optical axis from the eyeball's centre, r off it). bezel_deg:
    the plan's always-visible half-angle (the lip's outer edge on the sphere there)"""
    env = envelope(spec)
    d = dict(DESIGN, **(d or {}))
    Re = env['Re']
    Rb = Re * math.sin(math.radians(bezel_deg))                     # 9.642 mm
    r_name = LENS['name_ring'] * Rb
    r_thread = LENS['thread'] * Rb
    r_glass = LENS['glass'] * Rb
    Rr = Re - d['channel']                                          # the name ring's sphere (the channel's floor)
    r_bo = r_thread - 0.5 * d['thread_w']                           # the baffle's outer edge (the groove's inner lip)
    r_ri = r_thread + 0.5 * d['thread_w']                           # the ring's inner edge (the groove's outer lip)
    zs = lambda R, r: math.sqrt(R * R - r * r)
    th_w = math.asin(r_name / Re)                                   # the channel wall: radial from the centre
    z_b0 = zs(Rr, r_bo) - d['baffle_top']                           # the baffle's top tread
    z_ga = z_b0 - recess                                            # the glass's apex: the recess below the rim
    z_gr = z_ga - d['glass_sag']                                    # the glass's rim
    t = (r_bo - r_glass) / n_baffle                                 # the steps' treads and risers
    h = (z_b0 - z_gr) / n_baffle
    Rd = (r_glass ** 2 + d['glass_sag'] ** 2) / (2.0 * d['glass_sag'])     # the glass dome's radius
    # the gap: the bezel's outer wall at Rb - gap / 2, the housing's bore at Rb + gap / 2; the rounds where each meets
    # the sphere (centres inside the solid, r_break off the wall and off the sphere), the floor a U of half the gap
    g = d['gap']
    rb, rh = Rb - 0.5 * g, Rb + 0.5 * g
    q = d['r_break']
    cb = np.array([rb - q, zs(Re - q, rb - q)])                     # the bezel's edge round
    tb = cb * Re / (Re - q)
    ch = np.array([rh + q, zs(Re - q, rh + q)])                     # the housing's rim round
    th = ch * Re / (Re - q)
    z_gc = ch[1] - d['gap_wall_min']                                # the floor U's centre
    return dict(env=env, Re=Re, Rb=Rb, r_name=r_name, r_thread=r_thread, r_glass=r_glass, Rr=Rr, r_bo=r_bo, r_ri=r_ri,
                th_w=th_w, z_b0=z_b0, z_ga=z_ga, z_gr=z_gr, t=t, h=h, Rd=Rd, n_baffle=n_baffle, recess=recess,
                rb=rb, rh=rh, cb=cb, tb=tb, ch=ch, th=th, z_gc=z_gc, z_floor=z_gc - 0.5 * g, d=d,
                # derived edges: the ring's outer edge on its sphere at the wall, the bezel's inner edge on Re
                r_ring_out=Rr * math.sin(th_w), z_ring_out=Rr * math.cos(th_w), z_bez_in=Re * math.cos(th_w),
                th_t=math.atan2(th[0], th[1]))


def channel(D):
    """the name ring's channel wall, RADIAL from the eyeball's centre at th_w, and its two rounds: the foot's (concave,
    its centre in the channel's air at Rr + q from the centre, q off the wall on the ring's side) and the top's
    (convex, its centre inside the bezel at Re - qt, qt off the wall on the bezel's side); their tangent points"""
    Re, Rr, d, th_w = D['Re'], D['Rr'], D['d'], D['th_w']
    w = np.array([math.sin(th_w), math.cos(th_w)])                  # the wall's direction (out from the centre)
    nw = np.array([-math.cos(th_w), math.sin(th_w)])                # its normal toward the ring (smaller theta)
    q, qt = d['r_ch_foot'], d['r_ch_top']
    s_f = math.sqrt((Rr + q) ** 2 - q * q)
    cf = w * s_f + nw * q
    s_t = math.sqrt((Re - qt) ** 2 - qt * qt)
    ct = w * s_t - nw * qt
    return dict(w=w, nw=nw, q=q, qt=qt, cf=cf, tf_ring=cf * Rr / (Rr + q), tf_wall=w * s_f, ct=ct, tt_wall=w * s_t,
                tt_sph=ct * Re / (Re - qt))


def _arc(c, rad, a0, a1, max_step=2.0e-5, max_turn=math.radians(2.0)):
    """points on a circle (centre c, radius rad) from angle a0 to a1 (either sense), both ends included"""
    n = max(2, int(math.ceil(abs(a1 - a0) * rad / max_step)) + 1, int(math.ceil(abs(a1 - a0) / max_turn)) + 1)
    a = np.linspace(a0, a1, n)
    return np.column_stack([c[0] + rad * np.cos(a), c[1] + rad * np.sin(a)])


def profile(D, max_turn_deg=1.0):
    """the closed (r, z) profile for sdf.Program.revolve (metres), from the glass's apex out over the front (the glass
    dome, the stepped baffle, the thread's groove, the name ring's face in its channel, the bezel's sphere, the gap) and
    round the housing's sphere to the back pole; the axis closes it (not surface). Corners carry the rounds of DESIGN;
    the baffle's steps and the thread's groove stay sharp (a knife-edge baffle: the voxels break them at ~a voxel)"""
    Re, Rr, d = D['Re'], D['Rr'], D['d']
    mt = math.radians(max_turn_deg)
    parts = []
    # the glass dome: centre on the axis, from the apex to the rim
    zc = D['z_ga'] - D['Rd']
    a_rim = math.atan2(D['z_gr'] - zc, D['r_glass'])
    parts.append(_arc((0.0, zc), D['Rd'], math.pi / 2, a_rim, max_turn=math.radians(0.25)))
    # the stair: riser up, tread out, n times
    st = [(D['r_glass'], D['z_gr'])]
    for k in range(D['n_baffle']):
        r0 = D['r_glass'] + k * D['t']
        z1 = D['z_gr'] + (k + 1) * D['h']
        st += [(r0, z1), (r0 + D['t'], z1)]
    parts.append(np.array(st))
    # the thread's groove (a trapezoid V) to the ring's inner edge on its sphere
    zr = lambda r: math.sqrt(Rr * Rr - r * r)
    z_fl = zr(D['r_ri']) - d['thread_d']
    parts.append(np.array([(D['r_bo'], D['z_b0']), (D['r_thread'] - 0.5 * d['thread_floor'], z_fl),
                           (D['r_thread'] + 0.5 * d['thread_floor'], z_fl), (D['r_ri'], zr(D['r_ri']))]))
    # the name ring's face: the sphere Rr from the ring's inner edge to the channel wall's foot round (channel(): the
    # wall radial at th_w, the foot round concave, its centre in the air; the top round convex)
    a_in = math.atan2(zr(D['r_ri']), D['r_ri'])                     # angle on the circle (atan2(z, r))
    C = channel(D)
    q, cf, tf_ring, tf_wall = C['q'], C['cf'], C['tf_ring'], C['tf_wall']
    a_tf = math.atan2(tf_ring[1], tf_ring[0])
    parts.append(_arc((0.0, 0.0), Rr, a_in, a_tf, max_turn=mt))
    a0 = math.atan2(tf_ring[1] - cf[1], tf_ring[0] - cf[0])
    a1 = math.atan2(tf_wall[1] - cf[1], tf_wall[0] - cf[0])
    if a1 < a0:                                                     # concave: round the centre's underside (CCW)
        a1 += TAU
    parts.append(_arc(cf, q, a0, a1))
    # up the wall to the top round (CONVEX: its centre inside the bezel, Re - qt from the origin, qt off the wall on the
    # bezel's side)
    qt, ct, tt_wall, tt_sph = C['qt'], C['ct'], C['tt_wall'], C['tt_sph']
    a0 = math.atan2(tt_wall[1] - ct[1], tt_wall[0] - ct[0])
    a1 = math.atan2(tt_sph[1] - ct[1], tt_sph[0] - ct[0])
    if a1 > a0:
        a1 -= TAU
    parts.append(np.array([tf_wall, tt_wall]))
    parts.append(_arc(ct, qt, a0, a1))
    # the bezel's sphere (Re) out to the gap's bezel round
    a_s0 = math.atan2(tt_sph[1], tt_sph[0])
    a_s1 = math.atan2(D['tb'][1], D['tb'][0])
    parts.append(_arc((0.0, 0.0), Re, a_s0, a_s1, max_turn=mt))
    # the bezel round (convex) to its wall, down the wall to the floor's U, across, up the bore to the housing's rim
    # round (convex), onto the housing's sphere
    qb = d['r_break']
    cb, tb = D['cb'], D['tb']
    a0 = math.atan2(tb[1] - cb[1], tb[0] - cb[0])
    parts.append(_arc(cb, qb, a0, 0.0))                              # ends at (rb, cb_z): the wall's top
    g2 = 0.5 * d['gap']
    parts.append(np.array([(D['rb'], cb[1]), (D['rb'], D['z_gc'])]))
    parts.append(_arc((D['Rb'], D['z_gc']), g2, math.pi, 2.0 * math.pi))
    ch, th = D['ch'], D['th']
    parts.append(np.array([(D['rh'], D['z_gc']), (D['rh'], ch[1])]))
    a1 = math.atan2(th[1] - ch[1], th[0] - ch[0])
    parts.append(_arc(ch, qb, math.pi, a1))
    # the housing's sphere to the back pole
    parts.append(_arc((0.0, 0.0), Re, math.atan2(th[1], th[0]), -math.pi / 2, max_turn=math.radians(0.5)))
    P = [parts[0]]
    for p in parts[1:]:
        p = np.asarray(p, np.float64)
        P.append(p[1:] if np.linalg.norm(p[0] - P[-1][-1]) < 2.0e-8 else p)
    P = np.concatenate(P)
    P[-1] = (0.0, -Re)
    # drop zero-length segments (rounds meeting walls)
    keep = np.concatenate([[True], np.linalg.norm(np.diff(P, axis=0), axis=1) > 1.0e-9])
    return P[keep]


def build_sdf(D):
    """the block-out: ONE REVOLVE of the profile about +z through the eyeball's centre (the implant's frame)"""
    from . import sdf
    prog = sdf.Program()
    prog.revolve(profile(D), [0.0, 0.0, 0.0], [0.0, 0.0, 1.0], name='eye implant lens')
    prog.eye_implant = dict(variant='lens')
    return prog


# ============================================================================================ the low
REGIONS = ('glass', 'baffle', 'ring', 'bezel', 'housing', 'back')
REG = {n: i for i, n in enumerate(REGIONS)}


def low_rings(D):
    """the low's meridian (r, z) per ring and the region of the band that ENDS at it: the front (axis to SEAM_DEG),
    then the back's revolved zone to the equator (the cube-sphere half closes it)"""
    Re, Rr = D['Re'], D['Rr']
    zd = lambda r: (D['z_ga'] - D['Rd']) + math.sqrt(D['Rd'] ** 2 - r * r)
    zr = lambda r: math.sqrt(Rr * Rr - r * r)
    th_w = D['th_w']
    sph = lambda deg: (Re * math.sin(math.radians(deg)), Re * math.cos(math.radians(deg)))
    rings = [('c0 apex', 0.0, D['z_ga'], None),
             ('c1 glass', 0.55 * D['r_glass'], zd(0.55 * D['r_glass']), 'glass'),
             ('c2 glass rim', D['r_glass'], D['z_gr'], 'glass'),
             ('c3 baffle top', D['r_bo'], D['z_b0'], 'baffle'),
             ('c4 ring in', D['r_ri'], zr(D['r_ri']), 'baffle'),
             ('c5 ring out', Rr * math.sin(th_w), Rr * math.cos(th_w), 'ring'),
             ('c6 bezel in', Re * math.sin(th_w), Re * math.cos(th_w), 'bezel'),
             ('c7 bezel edge', float(D['tb'][0]), float(D['tb'][1]), 'bezel'),
             ('c8 housing edge', float(D['th'][0]), float(D['th'][1]), 'bezel')]
    t0 = math.degrees(D['th_t'])
    for i, deg in enumerate(np.linspace(t0, SEAM_DEG, 5)[1:]):
        rings.append((f'h{i + 1}', *sph(float(deg)), 'housing'))
    back = [('b0 seam', *sph(SEAM_DEG), None), ('b1', *sph(0.5 * (SEAM_DEG + 90.0)), 'back'),
            ('b2 equator', *sph(90.0), 'back')]
    return rings, back


FACE_MIN = 0.2              # the bake's own facing bar (forge/bake.py face_min): a hit within ~78 deg of its triangle


def _front_bands(D, rings):
    """the high's profile segments on the front matched to the low's front bands: per segment its outward normal's
    angle in the meridian plane (deg from +r), its length, its nearest band and the fraction along it, and each band's
    own normal angle"""
    P = profile(D)
    d = np.diff(P, axis=0)
    ln = np.linalg.norm(d, axis=1)
    keep = ln > 1e-12
    nrm = np.column_stack([-d[:, 1], d[:, 0]])[keep] / ln[keep, None]      # the path runs apex -> front: out = +90 deg
    mid = (0.5 * (P[1:] + P[:-1]))[keep]
    ang = np.degrees(np.arctan2(nrm[:, 1], nrm[:, 0]))
    rz = np.array([(r, z) for _, r, z, _ in rings])
    A, B = rz[:-1], rz[1:]
    AB = B - A
    t = np.clip(((mid[:, None, :] - A[None]) * AB[None]).sum(2) / (AB * AB).sum(1)[None], 0.0, 1.0)
    dist = np.linalg.norm(mid[:, None, :] - (A[None] + t[..., None] * AB[None]), axis=2)
    band = dist.argmin(1)
    frac = t[np.arange(len(mid)), band]
    bn = np.column_stack([-AB[:, 1], AB[:, 0]])
    bang = np.degrees(np.arctan2(bn[:, 1], bn[:, 0]))
    front = np.degrees(np.arctan2(mid[:, 0], mid[:, 1])) < SEAM_DEG
    return dict(ang=ang[front], len=ln[keep][front], band=band[front], frac=frac[front], bang=bang, mid=mid[front])


def ring_normals(D, rings, upto=8):
    """the front rings' normal angles in the meridian plane (deg from +r): each the middle of the angular range of the
    high's outward normals over the two half-bands the ring joins, counting only the faces the bake keeps on that
    band (within acos(FACE_MIN) of the band's own normal), so a band's interpolated normal sees every face its search
    can reach from the front (a smooth low round the lens's corners: the thread's groove, the channel, the steps).
    Rings 1..upto; the apex keeps +z, the sphere's rings their radial normal"""
    fb = _front_bands(D, rings)
    lim = math.degrees(math.acos(FACE_MIN))
    wrap = lambda a: (a + 180.0) % 360.0 - 180.0
    out = {}
    for i in range(1, min(upto, len(rings) - 1) + 1):
        sel = ((fb['band'] == i - 1) & (fb['frac'] >= 0.5)) | ((fb['band'] == i) & (fb['frac'] < 0.5))
        reach = np.abs(wrap(fb['ang'] - fb['bang'][fb['band']])) < lim
        # the angles relative to the two bands' bisector (a riser's normal is +-180 deg: no wrap across it)
        b0, b1 = np.radians(fb['bang'][i - 1]), np.radians(fb['bang'][min(i, len(fb['bang']) - 1)])
        ref = math.degrees(math.atan2(math.sin(b0) + math.sin(b1), math.cos(b0) + math.cos(b1)))
        a = wrap(fb['ang'][sel & reach] - ref)
        if len(a):
            out[i] = ref + 0.5 * (float(a.min()) + float(a.max()))
    return out


def _seg_hits(O, d, A, B, nrm):
    """2D rays O + t d (k, 2) against segments A -> B (m, 2) with outward normals nrm: the nearest t > 0 on a segment
    facing the ray (entering the solid) and that segment's index (-1: none)"""
    E = B - A
    den = d[:, None, 0] * E[None, :, 1] - d[:, None, 1] * E[None, :, 0]
    w = A[None] - O[:, None, :]
    t = (w[..., 0] * E[None, :, 1] - w[..., 1] * E[None, :, 0]) / np.where(np.abs(den) < 1e-18, 1e-18, den)
    u = (w[..., 0] * d[:, None, 1] - w[..., 1] * d[:, None, 0]) / np.where(np.abs(den) < 1e-18, 1e-18, den)
    face = (d[:, None, 0] * nrm[None, :, 0] + d[:, None, 1] * nrm[None, :, 1]) < 0.0
    ok = (t > 0.0) & (u >= 0.0) & (u <= 1.0) & face & (np.abs(den) > 1e-18)
    t = np.where(ok, t, np.inf)
    j = t.argmin(1)
    tj = t[np.arange(len(O)), j]
    return np.where(np.isfinite(tj), j, -1), tj


def facing_check(D, L, n=400, start=0.6e-3):
    """the bake's BACK-FACING share predicted in the meridian plane, the bake's own search simulated: along each front
    band of the low, the interpolated normal (the two rings' normals mixed, then normalised, as the shader does), the
    search turned toward the band's own normal as the two part 15 -> 45 deg (forge/bake.py), a ray from `start` out
    inward to the first face of the high it enters; a hit facing the band's normal under FACE_MIN is retried along the
    band's normal (the bake's retry). The tangent z of a hit is its normal on the interpolated normal: < 0 back-facing.
    Returns the band-length share back-facing, the least tangent z, and the ring angles"""
    rings = L['rings']
    n_cols = L['n_cols']
    na = [90.0]
    for i in range(1, len(rings)):
        v = 1 + (i - 1) * n_cols
        na.append(math.degrees(math.atan2(L['N'][v, 2], L['N'][v, 0])))
    na = np.array(na)
    P = profile(D)
    dd = np.diff(P, axis=0)
    ln = np.linalg.norm(dd, axis=1)
    kp = ln > 1e-12
    A, B = P[:-1][kp], P[1:][kp]
    nrm = np.column_stack([-dd[kp, 1], dd[kp, 0]]) / ln[kp, None]
    rz = np.array([(r, z) for _, r, z, _ in rings])
    tz_all, w_all = [], []
    c15, c45 = math.cos(math.radians(15.0)), math.cos(math.radians(45.0))
    for b in range(len(rz) - 1):
        f = (np.arange(n) + 0.5) / n
        Pl = rz[b][None] * (1 - f[:, None]) + rz[b + 1][None] * f[:, None]
        n0 = np.array([math.cos(math.radians(na[b])), math.sin(math.radians(na[b]))])
        n1 = np.array([math.cos(math.radians(na[b + 1])), math.sin(math.radians(na[b + 1]))])
        Ni = n0[None] * (1 - f[:, None]) + n1[None] * f[:, None]
        Ni /= np.linalg.norm(Ni, axis=1, keepdims=True)
        e = rz[b + 1] - rz[b]
        Nt = np.array([-e[1], e[0]]) / np.linalg.norm(e)
        c = Ni @ Nt
        k = np.clip((c15 - c) / (c15 - c45), 0.0, 1.0)              # 0 within 15 deg, 1 past 45
        S = Ni * (1 - k[:, None]) + Nt[None] * k[:, None]
        S /= np.linalg.norm(S, axis=1, keepdims=True)
        j, t = _seg_hits(Pl + start * S, -S, A, B, nrm)
        good = (j >= 0) & ((nrm[np.maximum(j, 0)] @ Nt) >= FACE_MIN)
        retry = ~good
        if retry.any():
            j2, t2 = _seg_hits(Pl[retry] + start * Nt[None], -np.tile(Nt, (int(retry.sum()), 1)), A, B, nrm)
            g2 = (j2 >= 0) & ((nrm[np.maximum(j2, 0)] @ Nt) >= FACE_MIN)
            jj = j.copy()
            jj[retry] = np.where(g2, j2, -1)
            j = jj
        hit = j >= 0
        tz = np.full(n, np.nan)
        tz[hit] = (nrm[j[hit]] * Ni[hit]).sum(1)
        tz_all.append(tz)
        w_all.append(np.full(n, np.linalg.norm(e) / n))
    tz = np.concatenate(tz_all)
    w = np.concatenate(w_all)
    ok = np.isfinite(tz)
    return dict(back_share=float((w * ok * (np.nan_to_num(tz) < 0)).sum() / max((w * ok).sum(), 1e-30)),
                least_dot=float(np.nanmin(tz)), missed_share=float((w * ~ok).sum() / w.sum()), ring_angles=na.tolist(),
                per_band=[float(np.nanmin(t_)) if np.isfinite(t_).any() else float('nan') for t_ in tz_all])


def cube_back(n=CUBE_N):
    """the EQUI-ANGULAR cube-sphere's back half (z <= 0) on the unit sphere: vertices (welded) and quads facing out"""
    t = np.tan(np.linspace(-math.pi / 4, math.pi / 4, n + 1))
    th = np.tan(np.linspace(-math.pi / 4, 0.0, n // 2 + 1))          # the side faces' back halves (z from -1 to 0)
    faces = [(np.array([0, 0, -1.0]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), t, t)]
    for nrm, a in ((np.array([1.0, 0, 0]), np.array([0, 1.0, 0])), (np.array([-1.0, 0, 0]), np.array([0, 1.0, 0])),
                   (np.array([0, 1.0, 0]), np.array([1.0, 0, 0])), (np.array([0, -1.0, 0]), np.array([1.0, 0, 0]))):
        faces.append((nrm, a, np.array([0, 0, 1.0]), t, th))
    V, Q = [], []
    for c0, a, b, ta, tb in faces:
        base = len(V)
        for j in range(len(tb)):
            for i in range(len(ta)):
                p = c0 + a * ta[i] + b * tb[j]
                V.append(p / np.linalg.norm(p))
        na = len(ta)
        for j in range(len(tb) - 1):
            for i in range(na - 1):
                k = base + j * na + i
                Q.append([k, k + 1, k + na + 1, k + na])
    V = np.array(V)
    Q = np.array(Q)
    key = np.round(V * 1e9).astype(np.int64)
    _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    V = V[idx]
    Q = inv.reshape(-1)[Q]
    # face out (the sphere's outward normal is the position)
    fn = np.cross(V[Q[:, 1]] - V[Q[:, 0]], V[Q[:, 2]] - V[Q[:, 0]])
    flip = (fn * V[Q].mean(1)).sum(1) < 0.0
    Q[flip] = Q[flip][:, ::-1]
    return V, Q


def _tri(Q, V):
    """quads to triangles along each quad's shorter diagonal"""
    d02 = np.linalg.norm(V[Q[:, 0]] - V[Q[:, 2]], axis=1)
    d13 = np.linalg.norm(V[Q[:, 1]] - V[Q[:, 3]], axis=1)
    s = d02 <= d13
    return np.concatenate([np.where(s[:, None], Q[:, [0, 1, 2]], Q[:, [0, 1, 3]]),
                           np.where(s[:, None], Q[:, [0, 2, 3]], Q[:, [1, 2, 3]])])


def build_low(D, size=SET_SIZE, pad_px=4, margin_px=3, n_cols=N_COLS, design_normals=True, log=print):
    """the low in the implant's frame: revolved rings on the front, the cube-sphere back half; UVs (forge convention,
    v up): the front a developed polar disc centred in the set, the back a polar disc from the back pole in the lower
    left corner. Returns dict(V, F, UV, N, TAN, region, island, rings, px_per_m, ...)"""
    from . import bake
    Re = D['Re']
    rings, back = low_rings(D)
    phi = TAU * np.arange(n_cols) / n_cols
    cphi, sphi = np.cos(phi), np.sin(phi)
    V, UV, Fq, Ft, reg_q, reg_t = [], [], [], [], [], []
    # ---- the front island: s along the low's meridian from the axis (true length), the polar disc
    rz = np.array([(r, z) for _, r, z, _ in rings])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(rz, axis=0), axis=1))])
    s_max = float(s[-1])
    R_uv = (0.5 * size - pad_px) / size
    px_per_m = (0.5 * size - pad_px) / s_max
    ids = []
    V.append([0.0, 0.0, rings[0][2]])
    UV.append([0.5, 0.5])
    ids.append(np.zeros(n_cols, np.int64))                          # the apex (one vertex)
    for i in range(1, len(rings)):
        r, z = rings[i][1], rings[i][2]
        base = len(V)
        for k in range(n_cols):
            V.append([r * cphi[k], r * sphi[k], z])
            UV.append([0.5 + R_uv * s[i] / s_max * cphi[k], 0.5 + R_uv * s[i] / s_max * sphi[k]])
        ids.append(base + np.arange(n_cols))
    k1 = (np.arange(n_cols) + 1) % n_cols
    for k in range(n_cols):                                         # the fan (outward: +z)
        Ft.append([0, ids[1][k], ids[1][k1[k]]])
        reg_t.append(REG[rings[1][3]])
    for i in range(1, len(rings) - 1):
        a, b = ids[i], ids[i + 1]
        for k in range(n_cols):
            Fq.append([a[k], b[k], b[k1[k]], a[k1[k]]])
            reg_q.append(REG[rings[i + 1][3]])
    n_front = len(V)
    # ---- the back island: polar from the back pole (u mirrored so it is not mirrored seen from outside)
    rho_px = (math.sqrt(2.0) * (0.5 * size - margin_px) - (0.5 * size - pad_px) - pad_px) / (1.0 + math.sqrt(2.0))
    cb_uv = np.array([margin_px + rho_px, margin_px + rho_px]) / size
    sb_max = Re * (math.pi - math.radians(SEAM_DEG))
    rho_uv = rho_px / size
    back_density = (rho_px / sb_max) / px_per_m
    sb = lambda th: Re * (math.pi - th)

    def back_uv(p):
        th = math.atan2(math.hypot(p[0], p[1]), p[2])
        ph = math.atan2(p[1], p[0])
        rr = sb(th) / sb_max * rho_uv
        return [cb_uv[0] - rr * math.cos(ph), cb_uv[1] + rr * math.sin(ph)]
    bids = []
    for i, (nm, r, z, rg) in enumerate(back):
        base = len(V)
        for k in range(n_cols):
            p = [r * cphi[k], r * sphi[k], z]
            V.append(p)
            UV.append(back_uv(p))
        bids.append(base + np.arange(n_cols))
    for i in range(len(back) - 1):
        a, b = bids[i], bids[i + 1]
        for k in range(n_cols):
            Fq.append([a[k], b[k], b[k1[k]], a[k1[k]]])
            reg_q.append(REG['back'])
    # the cube-sphere back half, welded to the equator ring b2
    Vc, Qc = cube_back(CUBE_N)
    eq = np.abs(Vc[:, 2]) < 1e-9
    assert eq.sum() == n_cols, f'the cube back half rim has {eq.sum()} vertices, the revolved rings {n_cols}'
    kc = np.round(np.arctan2(Vc[eq, 1], Vc[eq, 0]) / (TAU / n_cols)).astype(int) % n_cols
    assert len(set(kc.tolist())) == n_cols
    vmap = -np.ones(len(Vc), np.int64)
    vmap[np.nonzero(eq)[0]] = bids[-1][kc]
    for i in np.nonzero(~eq)[0]:
        p = (Vc[i] * Re).tolist()
        vmap[i] = len(V)
        V.append(p)
        UV.append(back_uv(p))
    for q in Qc:
        Fq.append(vmap[q].tolist())
        reg_q.append(REG['back'])
    V = np.array(V, np.float64)
    UV = np.array(UV, np.float64)
    Fq = np.array(Fq, np.int64)
    # the revolved front's quads: wound so the fan's sense carries over (checked against the SDF below)
    Ftq = _tri(Fq, V)
    reg = np.concatenate([np.array(reg_t, np.int32), np.tile(np.array(reg_q, np.int32), 2)])
    F = np.concatenate([np.array(Ft, np.int64), Ftq])
    # normals: area-weighted within each island (the islands share no vertex), the exact radial normal on the sphere's
    # rings (the housing, the back zone, the cube: |p| = Re)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for c in range(3):
        np.add.at(N, F[:, c], fn)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-30)
    on_sph = np.abs(np.linalg.norm(V, axis=1) - Re) < 1e-9
    on_sph[:1 + n_cols * 8] = False                                 # the front's detail rings keep theirs (c8 too)
    N[on_sph] = V[on_sph] / Re
    # the lens's detail rings c1..c7: their normals so every face their bands reach is seen from the front
    # (ring_normals; area-weighted, the groove's steep outer wall baked back-facing: 3.1 % of the baffle region)
    rn = ring_normals(D, rings, upto=7) if design_normals else {}
    for i, a in rn.items():
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        N[ids[i]] = np.column_stack([ca * cphi, ca * sphi, np.full(n_cols, sa)])
    N_, TAN = bake.low_frames(V, F, UV, N)
    island = np.concatenate([np.zeros(len(Ft), np.int32), np.where(np.tile(np.array(reg_q), 2) == REG['back'], 1,
                                                                    0).astype(np.int32)])
    log(f'[cyborg_eye] low: {len(V)} vertices, {len(F)} triangles ({len(rings)} front rings x {n_cols} + the back '
        f'zone + the cube half (n {CUBE_N})); front chart s_max {s_max * 1e3:.2f} mm, {px_per_m:.0f} px/m '
        f'({px_per_m / 1000:.2f} px/mm) at {size}^2; back disc radius {rho_px:.1f} px at {back_density:.3f} of the '
        f'front density')
    return dict(V=V, F=F, UV=UV, N=N_, TAN=TAN, region=reg, island=island, rings=rings, back=back, s=s,
                s_max=s_max, px_per_m=px_per_m, size=size, n_front=n_front, n_cols=n_cols,
                back_density=back_density, back_uv=dict(centre=cb_uv, rho=rho_uv), ring_normals=rn)


def orient_low(L, prog, log=print):
    """turn every triangle to face out of the solid (its normal against the block-out's gradient at its centroid; the
    construction already does: this asserts it and fixes any it did not)"""
    V, F = L['V'], L['F']
    c = V[F].mean(1)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    g = prog.normals(c)
    bad = np.einsum('ij,ij->i', fn, g) < 0.0
    if bad.any():
        F[bad] = F[bad][:, ::-1]
        from . import bake
        L['N'], L['TAN'] = bake.low_frames(V, F, L['UV'], L['N'])
    log(f'[cyborg_eye] low orientation: {int(bad.sum())} of {len(F)} triangles turned to face out')
    return int(bad.sum())


# ============================================================================================ the gates (CPU)
def low_gates(D, L):
    """G4 (every low vertex within Re + 0.1 mm of the eyeball's centre) and the high's profile's reach; U4 (stretch,
    texel shape, UV folds) per island; U5 (the chord sagitta round each ring); the triangle count"""
    Re = D['Re']
    V, F, UV = L['V'], L['F'], L['UV']
    rad = np.linalg.norm(V, axis=1)
    P = profile(D)
    out = dict(g4_low_max=float(rad.max()), g4_bar=Re + 1.0e-4, g4_high_max=float(np.linalg.norm(P, axis=1).max()))
    out['g4_ok'] = out['g4_low_max'] <= out['g4_bar'] and out['g4_high_max'] <= out['g4_bar']
    # U4: per triangle the UV map's singular values in texels per metre
    size = L['size']
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    u1, u2 = (UV[F[:, 1]] - UV[F[:, 0]]) * size, (UV[F[:, 2]] - UV[F[:, 0]]) * size
    # an orthonormal 2D frame in each triangle's plane
    x_ = e1 / np.linalg.norm(e1, axis=1, keepdims=True)
    nrm = np.cross(e1, e2)
    area3 = 0.5 * np.linalg.norm(nrm, axis=1)
    y_ = np.cross(nrm / np.linalg.norm(nrm, axis=1, keepdims=True), x_)
    P2 = np.stack([np.stack([(e1 * x_).sum(1), (e1 * y_).sum(1)], -1), np.stack([(e2 * x_).sum(1), (e2 * y_).sum(1)],
                                                                                    -1)], 1)
    U2 = np.stack([u1, u2], 1)
    J = np.linalg.solve(P2, U2)                    # (n, 2, 2): uv = p @ J  (rows: the 2D surface axes)
    sv = np.linalg.svd(J, compute_uv=False)
    shape = sv[:, 0] / np.maximum(sv[:, 1], 1e-12)
    dens = np.sqrt(sv[:, 0] * sv[:, 1])
    signed = u1[:, 0] * u2[:, 1] - u1[:, 1] * u2[:, 0]
    rows = {}
    for isl in (0, 1):
        m = L['island'] == isl
        w = area3[m]
        mean = float(np.sqrt((dens[m] ** 2 * w).sum() / w.sum()))
        st = dens[m] / mean
        rows['front' if isl == 0 else 'back (hidden)'] = dict(
            tris=int(m.sum()), px_per_m=mean, stretch_lo=float(st.min()), stretch_hi=float(st.max()),
            shape_p50=float(np.percentile(shape[m], 50)), shape_p99=float(np.percentile(shape[m], 99)),
            shape_max=float(shape[m].max()), folds=int((signed[m] <= 0).sum()) if m.any() else 0)
    out['u4'] = rows
    # U5: the chord sagitta round each ring (and the eyeball's back at its rim)
    n = L['n_cols']
    sag = [(nm, r * (1.0 - math.cos(math.pi / n))) for nm, r, z, _ in L['rings'][1:]]
    out['u5_max_mm'] = max(s_ for _, s_ in sag) * 1e3
    out['u5_rows'] = [(nm, s_ * 1e3) for nm, s_ in sag]
    out['tris'] = int(len(F))
    out['tris_visible_island'] = int((L['island'] == 0).sum())
    out['facing'] = facing_check(D, L)
    return out


def head_patch(base_dir, spec=None, side=1, reach=0.030):
    """the head low near an eye, in the IMPLANT's frame (q = R^T (p - E)): its triangles within `reach` of the eye's
    centre, with UV / N / TAN for look-dev; and the vertices INSIDE the eyeball's sphere (the socket's tuck and cap)"""
    from .species import octopus_eye
    if spec is None:
        from .species import octopus
        spec = octopus.SPEC
    Lw = np.load(os.path.join(base_dir, 'low.npz'), allow_pickle=True)
    V, F, fs = Lw['V'], Lw['F'], Lw['face_set']
    E, Re, out, h, u = octopus_eye.eye_axes(spec, side)
    R = np.column_stack([h, u, out])
    q = (V - E) @ R
    Fh = F[fs == 'head']
    near = np.linalg.norm(q[Fh].mean(1), axis=1) < reach
    Fh = Fh[near]
    us = np.unique(Fh)
    remap = -np.ones(len(V), np.int64)
    remap[us] = np.arange(len(us))
    inside = np.linalg.norm(q, axis=1) < Re
    return dict(V=q[us], F=remap[Fh], UV=Lw['UV'][us], N=Lw['N'][us] @ R,
                TAN=np.column_stack([Lw['TAN'][us, :3] @ R, Lw['TAN'][us, 3]]), inside=q[inside],
                tri_all=q[F[fs == 'head']], E=E, R=R)


def _tri_samples(T, n=4):
    """barycentric samples (a grid of n per edge) of triangles T (m, 3, 3)"""
    out = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            a, b = i / n, j / n
            out.append(T[:, 0] * (1 - a - b) + T[:, 1] * a + T[:, 2] * b)
    return np.concatenate(out)


def socket_clearance(D, prog, head, spec=None, n=4):
    """the head's socket (its low inside the eyeball's sphere: the lid's tuck rings, the cap, and the triangles
    between them) against the implant at every saccade extreme: the implant's field at each sample after the pose's
    inverse (negative = inside the implant's solid, hidden behind its surface). Returns rows (pose, worst field, the
    share of samples inside); the samples are the triangles' grids whose points lie inside the sphere"""
    Re = D['Re']
    T = head['tri_all']
    keep = np.linalg.norm(T, axis=2).min(1) < Re
    S = _tri_samples(T[keep], n)
    S = S[np.linalg.norm(S, axis=1) < Re - 1.0e-6]
    th = np.degrees(np.arctan2(np.hypot(S[:, 0], S[:, 1]), S[:, 2]))
    open_ = th < D['env']['ap_deg'] - 5.0           # inside the lid's opening (the lid's own tuck lies at 47-50 deg)
    rows = []
    for nm, y, p in saccade_poses(spec):
        M = pose_matrix(y, p)
        f = prog.eval(S @ M).astype(np.float64)    # p_imp = M^T q  (row vectors: q @ M)
        i = int(np.argmax(f))
        rows.append(dict(pose=nm, samples=int(len(S)), worst_mm=float(f.max()) * 1e3, worst_theta=float(th[i]),
                         worst_open_mm=float(f[open_].max()) * 1e3, open_samples=int(open_.sum()),
                         inside=float((f < 0).mean())))
    return rows


def feature_points(D, n=360):
    """sample rings of the features the gates watch (implant frame): the glass's edge, the ring's inner and outer edges
    (on the ring's face), the bezel's outer edge (on the sphere at the gap's round)"""
    ph = TAU * np.arange(n) / n
    ring = lambda r, z: np.column_stack([r * np.cos(ph), r * np.sin(ph), np.full(n, z)])
    zr = lambda r: math.sqrt(D['Rr'] ** 2 - r * r)
    pts = dict(glass_edge=ring(D['r_glass'] - 1e-5, D['z_gr'] + 1e-6),
               glass_mid=ring(0.5 * D['r_glass'], (D['z_ga'] - D['Rd']) + math.sqrt(D['Rd'] ** 2 -
                                                                                   (0.5 * D['r_glass']) ** 2)),
               ring_in=ring(D['r_ri'] + 2e-5, zr(D['r_ri'] + 2e-5)),
               ring_out=ring(D['r_ring_out'] - D['d']['r_ch_foot'] - 2e-5,
                             zr(D['r_ring_out'] - D['d']['r_ch_foot'] - 2e-5)),
               bezel_out=ring(float(D['tb'][0]), float(D['tb'][1])))
    return pts


VIEW_CONE_DEG = 15.0        # the oblique views the visibility gate also casts from (8 round the head-on one)


@wp.kernel
def _k_occluded(mesh: wp.uint64, org: wp.array(dtype=wp.vec3), d: wp.vec3, tmax: float, hit: wp.array(dtype=wp.int32)):
    i = wp.tid()
    q = wp.mesh_query_ray(mesh, org[i], d, tmax)
    if q.result:
        hit[i] = 1


def self_occluded(prog, P, d, reach=0.03, steps=400, eps=2.0e-6):
    """sphere-trace the implant's own block-out from points P (n, 3) on its surface along directions d (n, 3) (both
    in the implant's frame): True where the ray re-enters the solid (the bezel or the cavity's wall in the way)"""
    n = len(P)
    t = np.full(n, 3.0e-5)
    occ = np.zeros(n, bool)
    live = np.ones(n, bool)
    for _ in range(steps):
        idx = np.nonzero(live)[0]
        if not len(idx):
            break
        f = prog.eval(P[idx] + d[idx] * t[idx, None]).astype(np.float64)
        hit = f < -eps
        occ[idx[hit]] = True
        live[idx[hit]] = False
        t[idx] += np.maximum(f, 1.0e-6) * 0.9
        live[idx[t[idx] > reach]] = False
    return occ


def visibility(D, head, prog=None, spec=None, device='cpu'):
    """per saccade extreme and feature: the largest angle off the aperture's axis (the plan's proxy: inside the 50 deg
    lid cone) and the share of the feature's samples a ray reaches from the viewer, head-on along the aperture's axis
    and from 8 directions VIEW_CONE_DEG off it: past the head's low (the lids' rims and tucks) and past the implant's
    own block-out (the bezel and the cavity's walls). Returns rows"""
    wp.init()
    prog = prog or build_sdf(D)
    T = head['tri_all']
    keep = np.linalg.norm(T.mean(1), axis=1) < 0.03
    Tk = T[keep].reshape(-1, 3)
    Vm = wp.array(Tk.astype(np.float32), dtype=wp.vec3, device=device)
    mesh = wp.Mesh(points=Vm, indices=wp.array(np.arange(len(Tk), dtype=np.int32), dtype=wp.int32, device=device))
    a = math.radians(VIEW_CONE_DEG)
    dirs = [np.array([0.0, 0.0, 1.0])] + [np.array([math.sin(a) * math.cos(b), math.sin(a) * math.sin(b), math.cos(a)])
                                          for b in TAU * np.arange(8) / 8]
    feats = feature_points(D)
    names = list(feats)
    nper = len(feats[names[0]])
    P_all = np.concatenate([feats[k] for k in names])
    rows = []
    for nm, y, p in saccade_poses(spec):
        M = pose_matrix(y, p)
        Q = P_all @ M.T
        ang = np.degrees(np.arctan2(np.hypot(Q[:, 0], Q[:, 1]), Q[:, 2]))
        by_head = np.zeros((len(dirs), len(Q)), bool)
        for di, d_ in enumerate(dirs):
            org = wp.array((Q + d_ * 2e-6).astype(np.float32), dtype=wp.vec3, device=device)
            hit = wp.zeros(len(Q), dtype=wp.int32, device=device)
            wp.launch(_k_occluded, dim=len(Q), inputs=[mesh.id, org, wp.vec3(*d_.astype(np.float32)), 0.05, hit],
                      device=device)
            by_head[di] = hit.numpy() > 0
        Dl = np.repeat(np.stack([M.T @ d_ for d_ in dirs]), len(P_all), axis=0)       # the views in the implant's frame
        by_self = self_occluded(prog, np.tile(P_all, (len(dirs), 1)), Dl).reshape(len(dirs), len(P_all))
        for fi, fk in enumerate(names):
            sl = slice(fi * nper, (fi + 1) * nper)
            vis = [1.0 - (by_head[di, sl] | by_self[di, sl]).mean() for di in range(len(dirs))]
            lid = [1.0 - by_head[di, sl].mean() for di in range(len(dirs))]
            rows.append(dict(pose=nm, feature=fk, max_angle=float(ang[sl].max()),
                             margin_deg=D['env']['ap_deg'] - float(ang[sl].max()), head_on=float(vis[0]),
                             head_on_lid=float(lid[0]), cone_min=float(min(vis)), cone_mean=float(np.mean(vis)),
                             cone_min_lid=float(min(lid))))
    return rows


# ============================================================================================ the bake (GPU)
def bake_implant(D, L, voxel=0.04e-3, band=0.25e-3, ss=3, cage=1.5e-3, ao_r=3.0e-3, cav_r=0.4e-3, keep_deg=75.0,
                 log=print):
    """its own voxel grid (voxel.SparseSDF over the front: the cells within keep_deg of the axis; the hidden back reads
    the exact REVOLVE through the hybrid field) and the bake onto the low (forge/bake.py: the forge's island and
    cluster gate; region = REGIONS). Returns (res, info)"""
    from . import bake as BK
    from . import voxel as VX
    prog = build_sdf(D)
    lo = np.array([-D['Re'], -D['Re'], -D['Re']]) - 0.002
    hi = np.array([D['Re'], D['Re'], D['Re']]) + 0.002
    ck = math.cos(math.radians(keep_deg))
    keep = lambda pts: (pts[:, 2] / np.maximum(np.linalg.norm(pts, axis=1), 1e-12)) > ck - 0.08
    G = VX.SparseSDF(prog, lo, hi, voxel=voxel, band=band, keep=keep, log=log)
    names = {i: n for i, n in enumerate(REGIONS)}
    res = BK.bake(G, L['V'], L['F'], L['UV'], L['N'], L['TAN'], L['region'], size=L['size'], ss=ss, cage=cage,
                  ao_r=ao_r, cav_r=cav_r, n_thk=2, thk_max=0.01, region_names=names, log=log)
    return res, dict(voxels=int(G.n), voxel=voxel, band=band, ss=ss, cage=cage, ao_r=ao_r, cav_r=cav_r, G=G, prog=prog)


CLASSES = ('glass', 'baffle', 'thread', 'ring', 'bezel', 'gap', 'housing')
CLASS_REGION = dict(glass='glass', baffle='baffle', thread='baffle', ring='ring', bezel='bezel', gap='bezel',
                    housing='housing')


def band_edges(D):
    """the material bands' outer radii on the front, in CLASSES order (the last, the housing, runs to the back). The
    radius never falls along the front's profile (the walls hold it), so one radius orders every point of the front:
    the glass to the stair's first riser (which is the baffle's), the stair to the thread's inner lip, the groove, the
    name ring's face to its channel's foot round (the round and the radial wall are the bezel's), the bezel to the
    gap's floor, the floor, the bore and the housing's rim round to the housing's sphere"""
    return np.array([D['r_glass'] - 0.02e-3, D['r_bo'], D['r_ri'], D['r_ring_out'] - D['d']['r_ch_foot'],
                     D['rb'] + 0.01e-3, float(D['th'][0])])


def band_weights(D, P, width):
    """per point (n, 3) the weight of each class (n, len(CLASSES)), each band edge antialiased over `width` in radius
    (a texel's reach); the back half (z <= 0) is all housing"""
    r = np.hypot(P[:, 0], P[:, 1])
    e = band_edges(D)
    S = np.clip((r[:, None] - e[None, :]) / max(width, 1e-12) + 0.5, 0.0, 1.0)      # past each edge
    W = np.empty((len(P), len(CLASSES)))
    W[:, 0] = 1.0 - S[:, 0]
    for k in range(1, len(CLASSES) - 1):
        W[:, k] = S[:, k - 1] - S[:, k]
    W[:, -1] = S[:, -1]
    back = P[:, 2] <= 0.0
    W[back] = 0.0
    W[back, -1] = 1.0
    return W


def classify(D, P):
    """the material class of hit points P (n, 3) on the high (implant frame), CLASSES' index: the band its radius falls
    in on the front half, the housing on the back"""
    return band_weights(D, P, 1e-9).argmax(1).astype(np.int32)


def chart_s(L, xs, ys):
    """per texel (columns xs, rows ys: image order) its arc length s (metres) along the low's meridian, read off the
    FRONT polar chart: every front triangle lies in one column's wedge with its corners on the wedge's two rays at
    px_per_m * s_i from the chart's centre (build_low), and the chart is linear in each triangle, so at a point p of the
    chart s = p . m / (px_per_m cos(pi / n_cols)), m the wedge's middle direction: exactly the low's own interpolated s
    (the 32-gon's sagitta included). Returns (s, front: on the front island; else the back's chart)"""
    size, n = L['size'], int(L['n_cols'])
    du = (np.asarray(xs, np.float64) + 0.5) - 0.5 * size
    dv = 0.5 * size - (np.asarray(ys, np.float64) + 0.5)
    pm = (np.floor(np.mod(np.arctan2(dv, du), TAU) / (TAU / n)) + 0.5) * (TAU / n)
    s = (du * np.cos(pm) + dv * np.sin(pm)) / (L['px_per_m'] * math.cos(math.pi / n))
    return s, s <= L['s_max'] + 1.0 / L['px_per_m']


def band_weights_s(D, L, s, front):
    """per texel the weight of each class (n, len(CLASSES)) BY THE LOW: band_edges' radii carried to s along the front
    rings' meridian (its radius rises ring by ring), each edge antialiased over one texel of the chart; off the front
    island all housing. Returns (W, the edges in s)"""
    r_m = np.array([float(r) for _, r, _, _ in L['rings']])
    assert np.all(np.diff(r_m) > 0.0), 'the front rings\' radius must rise along the meridian'
    s_e = np.interp(band_edges(D), r_m, np.asarray(L['s'], np.float64))
    S = np.clip((np.asarray(s)[:, None] - s_e[None, :]) * L['px_per_m'] + 0.5, 0.0, 1.0)
    W = np.empty((len(s), len(CLASSES)))
    W[:, 0] = 1.0 - S[:, 0]
    for k in range(1, len(CLASSES) - 1):
        W[:, k] = S[:, k - 1] - S[:, k]
    W[:, -1] = S[:, -1]
    W[~front] = 0.0
    W[~front, -1] = 1.0
    return W, s_e


def island_raster(L):
    """per texel (image order) the low's region and island under the texel centre (-1: none), and the texels two
    triangles of different islands claim"""
    from PIL import Image, ImageDraw
    size = L['size']
    reg = np.full((size, size), -1, np.int64)
    isl = np.full((size, size), -1, np.int64)
    claim = np.zeros((size, size), np.int32)
    for i in (0, 1):
        im = Image.new('I', (size, size), -1)
        dr = ImageDraw.Draw(im)
        m = Image.new('L', (size, size), 0)
        dm = ImageDraw.Draw(m)
        for f, rg in zip(L['F'][L['island'] == i], L['region'][L['island'] == i]):
            pts = [(float(L['UV'][j, 0] * size - 0.5), float((1.0 - L['UV'][j, 1]) * size - 0.5)) for j in f]
            dr.polygon(pts, fill=int(rg))
            dm.polygon(pts, fill=1)
        a = np.asarray(im, np.int64)
        mm = np.asarray(m, bool)
        reg[mm] = a[mm]
        isl[mm] = i
        claim += mm
    return reg, isl, claim


def part_gates(D, L, res, border=2, bar=0.05, internal=1.5):
    """the hard-part bake gates (A.7 U3: the robot body's), per REGION of the one rigid part: the shares of its texels
    MISSED (no sub-sample found the high), WRONG-REGION (the hit's material class belongs to another region: the
    low's bands follow the material's radii), BACK-FACING (tangent z < 0) and UV OVERLAP, each at most `bar` %; out:
    the `border`-texel band at each island's edge and the texels within `internal` texels of a region boundary inside
    an island (where a texel straddles two bands). Returns (rows, extra)"""
    from scipy import ndimage
    size = L['size']
    reg, isl, claim = island_raster(L)
    cov = res['normal'][..., 3] > 0
    inside = isl >= 0
    mx = ndimage.maximum_filter(isl, size=2 * border + 1, mode='constant', cval=-1)
    mn = ndimage.minimum_filter(isl, size=2 * border + 1, mode='constant', cval=-1)
    edge = inside & ((mx != isl) | (mn != isl))
    rmx = ndimage.maximum_filter(reg, size=int(2 * internal + 1), mode='nearest')
    rmn = ndimage.minimum_filter(reg, size=int(2 * internal + 1), mode='nearest')
    rb = inside & ((rmx != reg) | (rmn != reg))
    core = inside & ~edge & ~rb
    P = res['position'][..., :3]
    cls = np.full((size, size), -1, np.int64)
    cls[cov] = classify(D, P[cov].astype(np.float64))
    want = np.array([REG[CLASS_REGION[c]] for c in CLASSES])
    # the hidden back: its class is the housing's sphere, its region 'back'
    creg = np.where(cls >= 0, want[np.maximum(cls, 0)], -1)
    creg = np.where((reg == REG['back']) & (creg == REG['housing']), REG['back'], creg)
    miss = (res['miss'] > 0) & ~cov
    back = cov & (res['normal'][..., 2] < 0.0)
    over = claim > 1
    rows = []
    for nm in REGIONS:
        m = core & (reg == REG[nm])
        n = int(m.sum())
        if not n:
            continue
        r = dict(region=nm, texels=n, missed=float((miss & m).sum()) / n * 100.0,
                 wrong=float((m & cov & (creg != REG[nm])).sum()) / n * 100.0,
                 back=float((back & m).sum()) / n * 100.0, overlap=float((over & m).sum()) / n * 100.0,
                 wrong_raw=float((inside & (reg == REG[nm]) & cov & (creg != REG[nm])).sum()) /
                 max(int((inside & (reg == REG[nm])).sum()), 1) * 100.0)
        r['ok'] = all(r[q] <= bar for q in ('missed', 'wrong', 'back', 'overlap'))
        rows.append(r)
    return rows, dict(border_texels=int(edge.sum()), boundary_texels=int(rb.sum()), overlap_texels=int(over.sum()),
                      cls=cls, reg=reg)


# ============================================================================================ the material pass
def rows():
    """the cyborg rows the implant uses (forge/cyborg.py CYBORG_ROWS through row_values, read only), plus the parts'
    glass row (A.5.1: cyb_glass, the robot body's glass [H via kb]; its own set, no skin id)"""
    from . import cyborg as CY
    ti = CY.row_values('cyb_titanium')
    ox = CY.row_values('cyb_steel', fastener_finish='black_oxide')
    gl = CY.row_values('cyb_glow', glow_finish='glazed')
    c = lambda v: np.array([v['c0r'], v['c0g'], v['c0b']])
    lohi = lambda v: (v['rough'] - v['rough_facet'], v['rough'] + v['rough_facet'])
    return dict(
        titanium=dict(base=c(ti), rough=lohi(ti), metal=ti['metal']),
        oxide=dict(base=c(ox), rough=lohi(ox), metal=ox['metal']),
        glow=dict(base=c(gl), rough=lohi(gl), metal=gl['metal'], colour=tuple(CY.CYBORG_ROWS['cyb_glow']['glow'])),
        glass=dict(base=np.array([0.005, 0.005, 0.005]), rough=(0.03, 0.03), metal=0.0, ior=1.52,
                   src='the robot body\'s glass: sRGB 14-16 (linear 0.0044-0.0052) at roughness 0.03 [H via kb]; '
                       'BK7 / soda-lime ior 1.52, F0 0.043 [C]'))


FINISH = dict(housing=0.40, bezel=0.30)     # titanium's 0.30-0.45 [E-fo]: bead-blasted near its top, machined at the
#                                             kit's bright machined 0.29-0.30 [R-kb]
EMIT_EDGE = 0.4                             # the house's hot centre: emit_centre 0.4 at the ring's edges (U12 [H via kb])


def _ss(x, a, b):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _vnoise(P, cell, seed):
    """3D value noise in [0, 1] (this module's own)"""
    Q = np.asarray(P, np.float64).reshape(-1, 3) / cell
    i0 = np.floor(Q).astype(np.int64)
    f = Q - i0
    w = f * f * (3.0 - 2.0 * f)
    out = np.zeros(len(Q))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                k = ((i0[:, 0] + dx) * np.int64(374761393)) ^ ((i0[:, 1] + dy) * np.int64(668265263)) ^ \
                    ((i0[:, 2] + dz) * np.int64(2246822519)) ^ np.int64((seed * 3266489917) % (1 << 31))
                k = (k ^ (k >> 15)) * np.int64(2654435761)
                k = k ^ (k >> 13)
                h = (k & np.int64(0xFFFFFF)).astype(np.float64) / float(0x1000000)
                wt = (w[:, 0] if dx else 1 - w[:, 0]) * (w[:, 1] if dy else 1 - w[:, 1]) * (w[:, 2] if dz else 1 - w[:, 2])
                out += wt * h
    return out


def material(D, L, res, log=print):
    """the material pass over the set (numpy, from the bake's drivers): by the hit's material class (classify()):
    albedo (sRGB), normal (the baked one), ORM (AO, roughness, metal), masks (R primary tint, G accent, B emissive, A
    wear). Returns (maps, stats)"""
    import time
    from . import bake as BK
    t0 = time.time()
    R = rows()
    size = L['size']
    cov = res['normal'][..., 3] > 0
    ys, xs = np.nonzero(cov)
    P = res['position'][ys, xs, :3].astype(np.float64)
    n = len(P)
    r = np.hypot(P[:, 0], P[:, 1])
    tex = 1.0 / L['px_per_m']
    # every class's weight per texel BY THE LOW (a turned part's material bands are its low's own bands): the texel's
    # arc length along the low's meridian, exact in the front's polar chart (chart_s), against band_edges' radii carried
    # to s along the low (band_weights_s), each edge antialiased over one texel: the edges are the low's own rings in
    # UV. Classed by the HIT's radius, which flips across a corner (the ring's lip, the channel's foot), every edge drew
    # a texel staircase (dots of glow on the titanium, teeth of black glaze in the close-ups); the hit keeps the detail
    # (the steps' own roughness, the turned rings, the dirt). The back's chart is all housing
    s_t, front = chart_s(L, xs, ys)
    W, s_e = band_weights_s(D, L, s_t, front)
    cls = W.argmax(1)
    # where the hit's class and the low's disagree farther than 1.5 texels from every edge (the bake reached another
    # feature than the band it bakes: the U3 gates hold that at 0 in each region's core)
    far = np.abs(s_t[:, None] - s_e[None, :]).min(1) * L['px_per_m'] > 1.5
    disagree = (classify(D, P) != cls) & front & (P[:, 2] > 0.0)
    jit = lambda cell, seed: _vnoise(P, cell, seed) - 0.5
    rows_c = []
    # glass: the body's glass row
    g = R['glass']
    rows_c.append((np.tile(g['base'], (n, 1)), np.full(n, g['rough'][0]), np.zeros(n)))
    # black oxide: the baffle's steps each their own roughness inside the row's range, the thread's groove the middle
    ox = R['oxide']
    lo_, hi_ = ox['rough']
    step = np.clip(np.floor((r - D['r_glass']) / D['t']), 0, D['n_baffle'] - 1).astype(int)
    sj = np.random.default_rng(41).uniform(-1.0, 1.0, D['n_baffle'])
    rows_c.append((np.tile(ox['base'], (n, 1)), 0.5 * (lo_ + hi_) + 0.3 * (hi_ - lo_) * sj[step], np.full(n, ox['metal'])))
    rows_c.append((np.tile(ox['base'], (n, 1)), np.full(n, 0.5 * (lo_ + hi_)), np.full(n, ox['metal'])))
    # the name ring: the glazed glow strip
    gw = R['glow']
    rows_c.append((np.tile(gw['base'], (n, 1)), np.full(n, 0.5 * (gw['rough'][0] + gw['rough'][1])), np.zeros(n)))
    # titanium: the bezel (with the channel's wall) and the gap machined, turned rings through the bezel's roughness
    # (band-limited below 2.5 texels a pitch); the housing bead-blasted, a fine cloud
    ti = R['titanium']
    turned = np.sin(TAU * r / 0.22e-3) * _ss(0.22e-3 / tex, 2.5, 4.0)
    rows_c.append((np.tile(ti['base'], (n, 1)), FINISH['bezel'] + 0.025 * turned, np.full(n, ti['metal'])))
    rows_c.append((np.tile(ti['base'], (n, 1)), np.full(n, FINISH['bezel']), np.full(n, ti['metal'])))
    rows_c.append((ti['base'][None, :] * (1.0 + 0.04 * jit(1.5e-3, 5))[:, None], FINISH['housing'] + 0.03 * jit(0.4e-3, 3),
                   np.full(n, ti['metal'])))
    base = sum(W[:, k:k + 1] * rows_c[k][0] for k in range(len(CLASSES)))
    rough = sum(W[:, k] * rows_c[k][1] for k in range(len(CLASSES)))
    metal = sum(W[:, k] * rows_c[k][2] for k in range(len(CLASSES)))
    # the name ring's EMISSIVE mask: the ring's weight x the house's hot centre (1 mid-band, EMIT_EDGE at its edges),
    # across the ring's band of the low
    u = (s_t - 0.5 * (s_e[2] + s_e[3])) / (0.5 * (s_e[3] - s_e[2]))
    prof = EMIT_EDGE + (1.0 - EMIT_EDGE) * np.clip(1.0 - u * u, 0.0, 1.0)
    emis = W[:, 3] * prof
    # dirt: grime by multiply in the cavities (the gap, the groove's lip, the channel's foot), the titanium only
    cav = res['cavity'][ys, xs].astype(np.float64)
    dirt = (1.0 - _ss(cav, 0.55, 0.95)) * (0.8 + 0.2 * _vnoise(P, 0.8e-3, 9))
    wt = W[:, 4] + W[:, 5] + W[:, 6]
    base = base * (1.0 - 0.30 * dirt * wt)[:, None]
    rough = np.clip(rough + 0.06 * dirt * wt, 0.02, 1.0)
    # opaque dielectrics clamped to the house's 0.013-0.87 (U8: the black oxide); the glass and the glazed strip keep
    # the body's glass 0.005 (their diffuse is the dark behind the glass)
    wo = W[:, 1] + W[:, 2]
    base = np.clip(base, 0.0, 1.0) * (1.0 - wo)[:, None] + np.clip(base, 0.013, 0.87) * wo[:, None]
    mr = cls == 3
    ao = res['ao'][ys, xs].astype(np.float64)
    img = lambda k: np.zeros((size, size, k))
    alb, nmp, orm, msk = img(3), img(3), img(3), img(4)
    alb[ys, xs] = base
    nmp[ys, xs] = res['normal'][ys, xs, :3]
    orm[ys, xs] = np.column_stack([ao, rough, metal])
    msk[ys, xs] = np.column_stack([np.zeros(n), np.zeros(n), emis, np.zeros(n)])
    dil, grown = BK.dilate_all(dict(normal=np.concatenate([nmp, cov[..., None].astype(np.float64)], -1), alb=alb, orm=orm,
                                    msk=msk), 16)
    enc = lambda x: np.clip(x * 255.0 + 0.5, 0, 255).astype(np.uint8)
    maps = dict(albedo=enc(np.where(grown[..., None], dil['alb'], 0.05) ** (1.0 / 2.2)),
                normal=enc(np.where(grown[..., None], dil['normal'][..., :3], [0.0, 0.0, 1.0]) * 0.5 + 0.5),
                orm=enc(np.where(grown[..., None], dil['orm'], [1.0, 0.4, 1.0])),
                masks=enc(np.where(grown[..., None], dil['msk'], 0.0)))
    counts = {c: int((cls == k).sum()) for k, c in enumerate(CLASSES)}
    st = dict(texels=int(n), classes=counts, emissive_texels=int((emis > 0.01).sum()),
              emis_mean_on_ring=float(emis[mr].mean()) if mr.any() else 0.0,
              rough=dict({c: float(np.median(rough[cls == k])) for k, c in enumerate(CLASSES) if (cls == k).any()}),
              metal_titanium=float(np.median(metal[np.isin(cls, (4, 5, 6))])), seconds=time.time() - t0,
              blended=int(((W > 0.02) & (W < 0.98)).any(1).sum()),
              classes_by='the low: chart_s + band_weights_s (edges in s, mm: ' +
                         ', '.join(f'{x * 1e3:.4f}' for x in s_e) + ')',
              hit_disagree=int(disagree.sum()), hit_disagree_far=int((disagree & far).sum()),
              rows={k: dict(base=[float(x) for x in v['base']], rough=[float(x) for x in v['rough']],
                            metal=float(v['metal'])) for k, v in R.items()})
    log(f'[cyborg_eye] material {size}^2: {n:,} texels; classes ' + ', '.join(f'{c} {v:,}' for c, v in counts.items())
        + f'; emissive texels {st["emissive_texels"]:,}; classes by the low\'s own bands (the hit\'s radius class differs '
          f'on {st["hit_disagree"]:,} texels, {st["hit_disagree_far"]} of them over 1.5 texels from every edge); '
          f'{st["seconds"]:.1f}s')
    return maps, st


# ============================================================================================ the part glb
def to_bone(V):
    """implant frame (x h, y u, z out) -> the eye bone's / socket's frame (x out, y u, z -h)"""
    V = np.asarray(V, np.float64)
    return np.column_stack([V[:, 2], V[:, 1], -V[:, 0]])


def part_record(D, L, maps_px=None):
    """the part's record (extras): family, variant, fits, the rings with their measured sources, the envelope"""
    env = D['env']
    return dict(
        family='eye_implant', variant='lens', fits='eye', interface='ball', rigid='one joint at weight 1 (the eye\'s)',
        frame='the eye bone\'s / socket_eye_*\'s: +X the optical axis, +Y up made perpendicular, origin the eyeball\'s '
              'centre (forge/rig.frame_from(out, +Y))',
        envelope=dict(Re_mm=round(D['Re'] * 1e3, 4), max_low_mm=round(float(np.linalg.norm(L['V'], axis=1).max()) * 1e3,
                                                                      4), bar_mm=round(D['Re'] * 1e3 + 0.1, 4)),
        rings_mm=dict(bezel=round(D['Rb'] * 1e3, 4), name_ring_outer=round(D['r_name'] * 1e3, 4),
                      ring_inner=round(D['r_ri'] * 1e3, 4), thread=round(D['r_thread'] * 1e3, 4),
                      glass=round(D['r_glass'] * 1e3, 4), baffle_band=round((D['r_thread'] - D['r_glass']) * 1e3, 4),
                      steps=D['n_baffle'], tread=round(D['t'] * 1e3, 4), riser=round(D['h'] * 1e3, 4),
                      recess=round(D['recess'] * 1e3, 4)),
        sources=dict(rings='research/cyborg_work/refs_data/photos/p10_measure.json (REFS §4.8): front lip 1170 px = '
                           '72.81 mm, name ring 1078 px, filter thread 932 px = 58.0 mm (the scale), visible glass 569 '
                           'px; the lip at the plan\'s always-visible radius Re sin 40 deg [M-rf, D-pl]',
                     recess='a study-T companion character: lens disc 90.0 mm, 25.6 mm below its rim (0.569 r) [R-tt, D-ad C2]; A.9',
                     baffle='p10: about 8 concentric black steps [M-rf]'),
        saccades=dict(yaw_deg=round(env['yaw_deg'], 3), pitch_deg=round(env['pitch_deg'], 3),
                      diagonal_tilt_deg=round(env['tilt_deg'], 3), always_visible_deg=round(env['vis_true_deg'], 3)),
        triangles=int(len(L['F'])), texture=int(L['size']), px_per_m=round(float(L['px_per_m']), 1))


def export_glb(path, D, L, maps):
    """the implant ALONE as a static glb in the eye socket's frame (a runtime attach parents it to socket_eye_* at
    identity): one mesh, one material (base, normal, ORM; the masks in KHR_materials_volume's thickness slot as the
    creatures and props carry theirs; extras.bestiary 'cyborg')"""
    from . import gltf
    g = gltf.GLB()
    t_base = g.texture(maps['albedo'], fmt='png')
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='png')
    t_msk = g.texture(maps['masks'], fmt='png')
    rec = part_record(D, L)
    mat = g.material('eye_implant_lens', base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='cyborg', part='eye_implant', variant='lens', masks=t_msk,
        masks_channels='R primary tint region (none: titanium, black oxide, glass), G accent region, B emissive '
                       '(the name ring, a hot centre), A wear',
        glow=list(rows()['glow']['colour']),
        rows='forge/cyborg.py row_values: cyb_titanium (housing 0.40, bezel 0.30), cyb_steel black_oxide, cyb_glow '
             'glazed; the glass the body\'s glass row (cyborg_eye.rows)'))
    Vb = to_bone(L['V'])
    Nb = to_bone(L['N'])
    Tb = np.column_stack([to_bone(L['TAN'][:, :3]), L['TAN'][:, 3]])
    mesh = g.mesh('eye_implant_lens', Vb, Nb, Tb, L['UV'], [(L['F'], mat)])
    g.node('eye_implant_lens', mesh=mesh, root=True, extras=dict(bestiary='cyborg', part=rec))
    return g.save(path, extras=dict(bestiary=dict(part='eye_implant', variant='lens', units='m', frame=rec['frame'],
                                                  record=rec)))


# ============================================================================================ the staged export
def _glb_load(path):
    with open(path, 'rb') as f:
        data = f.read()
    magic, ver, total = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67 and ver == 2 and total == len(data)
    jl, _ = struct.unpack_from('<II', data, 12)
    j = json.loads(data[20:20 + jl])
    bl, _ = struct.unpack_from('<II', data, 20 + jl)
    return j, bytearray(data[28 + jl:28 + jl + bl])


def splice(src, dst, D, L, maps, side=1, spec=None, log=print):
    """THE OCTOPUS WEARING THE IMPLANT, as a staged export: src's glb copied to dst with the organic eyeball on eye_L
    (side +1; eye_R for -1) dropped from the eye primitive and the implant appended as its own primitive (its own
    vertex set, as the geometric suckers') and material, every vertex on that eye's joint at weight 1 (t13's eyes).
    Every other byte of src's buffer and every other JSON entry is kept. Returns the record"""
    from . import gltf
    from .species import octopus_eye
    if spec is None:
        from .species import octopus
        spec = octopus.SPEC
    j, binb = _glb_load(src)
    g = gltf.GLB()
    g.j = j
    g.bin = binb
    g.ext_used = set(j.get('extensionsUsed', []))
    names = [n['name'] for n in j['nodes']]
    jname = 'eye_L' if side == 1 else 'eye_R'
    sname = 'socket_eye_L' if side == 1 else 'socket_eye_R'
    jnode = names.index(jname)
    jidx = j['skins'][0]['joints'].index(jnode)
    mesh = j['meshes'][0]
    mats = [m['name'] for m in j['materials']]
    pe = next(p for p in mesh['primitives'] if mats[p['material']] == 'octopus_eye')
    R_ = gltf.read(src)
    idx = R_['accessor'](pe['indices']).reshape(-1, 3).astype(np.int64)
    J0 = R_['accessor'](pe['attributes']['JOINTS_0'])[:, 0].astype(np.int64)
    on_eye = (J0[idx] == jidx).all(1)
    kept = idx[~on_eye]
    assert on_eye.sum() > 0 and (J0[kept] != jidx).all()
    pe['indices'] = g.accessor(kept.astype(np.uint32).reshape(-1), 'SCALAR', 34963)
    # the implant: implant frame -> the creature's bind (world) by the eye's frame
    E, Re, out, h, u = octopus_eye.eye_axes(spec, side)
    Rw = np.column_stack([h, u, out])
    Vw = E + L['V'] @ Rw.T
    Nw = L['N'] @ Rw.T
    Tw = np.column_stack([L['TAN'][:, :3] @ Rw.T, L['TAN'][:, 3]])
    t_base = g.texture(maps['albedo'], fmt='png')
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='png')
    t_msk = g.texture(maps['masks'], fmt='png')
    rec = part_record(D, L)
    mi = g.material('octopus_eye_implant', base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='cyborg', recipe='octopus', part='eye_implant', variant='lens', socket=sname, joint=jname,
        masks=t_msk, masks_channels='R primary tint region, G accent region, B emissive (the name ring), A wear',
        glow=list(rows()['glow']['colour'])))
    a = {'POSITION': g.accessor(Vw.astype(np.float32), 'VEC3', 34962, minmax=True),
         'NORMAL': g.accessor(Nw.astype(np.float32), 'VEC3', 34962),
         'TANGENT': g.accessor(Tw.astype(np.float32), 'VEC4', 34962),
         'TEXCOORD_0': g.accessor(np.column_stack([L['UV'][:, 0], 1.0 - L['UV'][:, 1]]).astype(np.float32), 'VEC2',
                                  34962),
         'JOINTS_0': g.accessor(np.tile(np.array([jidx, 0, 0, 0], np.uint16), (len(Vw), 1)), 'VEC4', 34962),
         'WEIGHTS_0': g.accessor(np.tile(np.array([1.0, 0.0, 0.0, 0.0], np.float32), (len(Vw), 1)), 'VEC4', 34962)}
    mesh['primitives'].append({'attributes': a, 'indices': g.accessor(L['F'].astype(np.uint32).reshape(-1), 'SCALAR',
                                                                      34963), 'material': mi, 'mode': 4})
    bx = j.setdefault('extras', {}).setdefault('bestiary', {})
    cy = bx.setdefault('cyborg', {})
    cy.setdefault('parts', []).append(dict(family='eye_implant', variant='lens', socket=sname, joint=jname,
                                           replaces=f'the organic eyeball on {jname} ({int(on_eye.sum())} triangles)',
                                           material='octopus_eye_implant', triangles=int(len(L['F'])),
                                           staged='forge/cyborg_eye.splice (t13 untouched; C7 moves it into t13)',
                                           record=rec))
    n = g.save(dst)
    log(f'[cyborg_eye] spliced {os.path.relpath(dst, REPO)}: {jname}\'s eyeball ({int(on_eye.sum())} triangles) dropped, '
        f'the implant ({len(L["F"])} triangles, {len(Vw)} vertices) on joint {jidx} ({jname}) at weight 1; '
        f'{n / 1e6:.1f} MB')
    return dict(dropped=int(on_eye.sum()), kept=int(len(kept)), joint=jidx, tris=int(len(L['F'])), bytes=n,
                material=mi, E=E, Rw=Rw)


def verify_splice(src, dst, D, L, side=1, spec=None):
    """the shipped file re-read: the eye primitive holds only the other eye; the implant's primitive maps back onto the
    low (the eye's frame) exactly, on one joint at weight 1, inside the sphere; every src accessor's data unchanged"""
    from . import gltf
    from .species import octopus_eye
    if spec is None:
        from .species import octopus
        spec = octopus.SPEC
    A, B = gltf.read(src), gltf.read(dst)
    ja, jb = A['json'], B['json']
    E, Re, out, h, u = octopus_eye.eye_axes(spec, side)
    Rw = np.column_stack([h, u, out])
    prims = jb['meshes'][0]['primitives']
    pi = prims[-1]
    V = B['accessor'](pi['attributes']['POSITION']).astype(np.float64)
    Jn = B['accessor'](pi['attributes']['JOINTS_0'])
    W = B['accessor'](pi['attributes']['WEIGHTS_0'])
    loc = (V - E) @ Rw
    names = [n['name'] for n in jb['nodes']]
    jidx = jb['skins'][0]['joints'].index(names.index('eye_L' if side == 1 else 'eye_R'))
    same = all(np.array_equal(A['accessor'](i), B['accessor'](i)) for i in range(len(ja['accessors'])))
    pe = next(p for p in prims if jb['materials'][p['material']]['name'] == 'octopus_eye')
    Ie = B['accessor'](pe['indices']).reshape(-1, 3)
    Je = B['accessor'](pe['attributes']['JOINTS_0'])[:, 0]
    return dict(pos_err=float(np.abs(loc - L['V']).max()), max_radius_mm=float(np.linalg.norm(loc, axis=1).max()) * 1e3,
                one_joint=bool((Jn[:, 0] == jidx).all() and (W[:, 0] == 1.0).all() and (W[:, 1:] == 0).all()),
                src_accessors_unchanged=same, eye_prim_tris=int(len(Ie)),
                eye_prim_other_eye_only=bool((Je[Ie] != jidx).all()), materials=[m['name'] for m in jb['materials']],
                images=len(jb['images']), images_src=len(ja['images']))


# ============================================================================================ looks
class ProgField:
    """a plain Program wearing voxel.SparseSDF's query interface (an empty 1-voxel grid far away): trace_views on the
    exact block-out (cyborg_limb.ProgField's pattern, this module's own copy)"""

    def __init__(self, prog, lo, hi, vs=1.0e-4):
        import warp as wp
        self.prog = prog
        self.vs = float(vs)
        self.origin = np.asarray(lo, np.float64)
        n = np.ceil((np.asarray(hi, np.float64) - self.origin) / vs).astype(np.int32)
        far = np.array([[n[0] + 4096, n[1] + 4096, n[2] + 4096]], np.int32)
        self.vol = wp.Volume.allocate_by_voxels(wp.array(far, dtype=wp.vec3i), voxel_size=self.vs,
                                                translation=tuple(self.origin))
        self.val = wp.array(np.full(1, 1.0e9, np.float32), dtype=wp.float32)
        self.ijk = wp.array(np.array([[0, 0, 0], n], np.int32), dtype=wp.vec3i)

    def _args(self):
        return [self.vol.id, self.val] + self.prog._args()


def cut_program(D, keep_x=True):
    """the block-out cut in half by the plane x = 0 (the half x >= 0 kept): a section to look at"""
    from . import sdf
    prog = sdf.Program()
    prog.begin_group()
    prog.revolve(profile(D), [0.0, 0.0, 0.0], [0.0, 0.0, 1.0], name='lens')
    prog.roundbox([0.5 * D['Re'] + 0.001, 0.0, 0.0], [0.5 * D['Re'] + 0.001, D['Re'] + 0.002, D['Re'] + 0.002],
                  op=sdf.INTERSECT, name='half')
    prog.end_group()
    return prog


def lookdev_materials(maps, glow_rgb=None):
    """the implant's look-dev material (lookdev.render's dict) and its EMISSIVE pass material: the emissive mask as an
    sRGB-encoded albedo (lit by a uniform unit sky with no key and no specular, its radiance is the mask)"""
    from . import lookdev
    m = dict(albedo=maps['albedo'][..., :3], normal=maps['normal'][..., :3], rough=maps['orm'][..., 1],
             metal=maps['orm'][..., 2], ao=maps['orm'][..., 0], ior=1.5)
    e = maps['masks'][..., 2].astype(np.float64) / 255.0
    es = (lookdev.srgb_oetf(e) * 255.0 + 0.5).astype(np.uint8)
    me = dict(albedo=np.repeat(es[..., None], 3, -1), rough=np.full(e.shape, 255, np.uint8),
              metal=np.zeros(e.shape, np.uint8), ao=np.full(e.shape, 255, np.uint8), f0=0.0, specular_intensity=0.0)
    return m, me


BLACK4 = np.zeros((4, 4, 3), np.uint8)


def glow_compose(aov_lit, aov_emis, glow_rgb, intensity, exposure=1.0, bg=(94, 94, 100), tone='agx'):
    """the lit render plus the emissive radiance (glow colour x intensity x the visible mask), tone mapped as the
    engine does (the emission added before AgX), laid over the background by the coverage: a display image"""
    from . import lookdev
    rgb = aov_lit['rgb'] + np.asarray(glow_rgb, np.float64)[None, None, :] * intensity * aov_emis['rgb'][..., :1]
    cov = aov_lit['cov']
    lin = rgb / np.maximum(cov, 1e-12)[..., None]
    d = lookdev.display(lin, tone, exposure)
    bgv = np.asarray(bg, np.float64) / 255.0
    o = d * cov[..., None] + bgv * (1.0 - cov[..., None])
    return (np.clip(o, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def section_png(D, L, head, path, posed=None):
    """the implant's meridian section, drawn: the high's profile, the low's rings, the eyeball's sphere and Re + 0.1,
    the lid's 50 deg cone, the always-visible cones (the plan's 40 deg, the true 38.74), the head's socket (its low's
    vertices near the eye, in this meridian's (r, z)), the rings' radii with their sources; and a zoom on the front"""
    from PIL import Image, ImageDraw
    P = profile(D)
    Re = D['Re']
    rows_ = []

    def panel(r0, r1, z0, z1, ppm, title):
        W, H = int((r1 - r0) * 1e3 * ppm), int((z1 - z0) * 1e3 * ppm)
        im = Image.new('RGB', (W, H), (250, 250, 248))
        dr = ImageDraw.Draw(im)
        X = lambda r: (r - r0) * 1e3 * ppm
        Y = lambda z: H - (z - z0) * 1e3 * ppm
        # the sphere, Re + 0.1, the cones
        for R_, col in ((Re, (150, 150, 150)), (Re + 1e-4, (200, 120, 120))):
            a = np.linspace(-0.2, math.pi, 2000)
            pts = [(X(R_ * math.sin(t)), Y(R_ * math.cos(t))) for t in a]
            dr.line(pts, fill=col, width=1)
        for deg, col, lab in ((50.0, (40, 110, 200), 'lid 50'), (40.0, (60, 170, 60), 'plan 40'),
                              (D['env']['vis_true_deg'], (220, 140, 0), f'true {D["env"]["vis_true_deg"]:.2f}')):
            t = math.radians(deg)
            dr.line([(X(0), Y(0)), (X(16e-3 * math.sin(t)), Y(16e-3 * math.cos(t)))], fill=col, width=1)
            rr, zz = 15.6e-3 * math.sin(t), 15.6e-3 * math.cos(t)
            if r0 <= rr <= r1 and z0 <= zz <= z1:
                dr.text((X(rr) + 3, Y(zz) - 12), lab, fill=col)
        # the head's socket (the left eye's low vertices within 1.06 Re, as (r, z) in this frame)
        if head is not None:
            q = head['inside']
            for p in q:
                rr, zz = math.hypot(p[0], p[1]), p[2]
                dr.ellipse([X(rr) - 2, Y(zz) - 2, X(rr) + 2, Y(zz) + 2], outline=(150, 60, 150))
            T = head['tri_all']
            near = np.linalg.norm(T.mean(1), axis=1) < 1.07 * Re
            for t3 in T[near]:
                for p in t3:
                    rr, zz = math.hypot(p[0], p[1]), p[2]
                    if np.linalg.norm(p) >= Re:
                        dr.point((X(rr), Y(zz)), fill=(180, 120, 180))
        # the high's profile and the low's meridian
        dr.line([(X(r), Y(z)) for r, z in P], fill=(10, 10, 10), width=2)
        rz = [(r, z) for _, r, z, _ in L['rings']] + [(r, z) for _, r, z, _ in L['back']]
        dr.line([(X(r), Y(z)) for r, z in rz], fill=(210, 40, 40), width=1)
        for r, z in rz:
            dr.ellipse([X(r) - 3, Y(z) - 3, X(r) + 3, Y(z) + 3], outline=(210, 40, 40))
        if posed is not None:
            for r, z, col in posed:
                dr.rectangle([X(r) - 3, Y(z) - 3, X(r) + 3, Y(z) + 3], outline=col, width=2)
        dr.text((8, 6), title, fill=(0, 0, 0))
        return im, X, Y
    a, Xa, Ya = panel(-0.5e-3, 16.5e-3, 5.5e-3, 16.0e-3, 62, 'C4 eye implant lens: meridian section (r right, z up the '
                      'optical axis, mm x 62 px)')
    da = ImageDraw.Draw(a)
    lab = [(D['r_glass'], 'glass r %.3f (p10 0.4863)' % (D['r_glass'] * 1e3)),
           (D['r_thread'], 'thread r %.3f (p10 0.7966)' % (D['r_thread'] * 1e3)),
           (D['r_name'], 'name ring r %.3f (p10 0.9214)' % (D['r_name'] * 1e3)),
           (D['Rb'], 'bezel r %.3f (Re sin 40)' % (D['Rb'] * 1e3))]
    for i, (rr, t) in enumerate(lab):
        da.line([(Xa(rr), Ya(5.6e-3)), (Xa(rr), Ya(7.2e-3 + 0.6e-3 * i))], fill=(90, 90, 200), width=1)
        da.text((Xa(rr) + 3, Ya(7.2e-3 + 0.6e-3 * i) - 10), t, fill=(60, 60, 170))
    da.text((Xa(0.3e-3), Ya(D['z_ga']) - 22), f'glass apex {D["recess"] * 1e3:.2f} mm under the cavity rim', fill=(0, 0, 0))
    da.text((8, 22), 'black: the high (REVOLVE); red: the low; grey: Re; pink: Re + 0.1 mm; purple: the head low '
                     '(the socket\'s tuck and cap inside, the lid outside)', fill=(60, 60, 60))
    b, Xb, Yb = panel(6.9e-3, 10.4e-3, 10.6e-3, 13.2e-3, 300, 'the front, x 300 px/mm: the stepped baffle, the thread, '
                      'the name ring in its channel, the bezel, the gap')
    W = max(a.size[0], b.size[0])
    out = Image.new('RGB', (W, a.size[1] + b.size[1]), (255, 255, 255))
    out.paste(a, (0, 0))
    out.paste(b, (0, a.size[1]))
    out.save(path)
    return path
