"""ARTHROPOD family generator: hexapods, the stag beetle first (work/bestiary/research/BEETLE_PLAN.md §4.1, §2.7,
§6.1). Every sclerite is a rigid closed shell on one joint (plan §4.2), so the skeleton is the animal's articulation.

B1: the rest chain and the 104-joint skeleton. The per-part programs and the clay come at B3, the cages at B4.

UNITS AND FRAME: rest_chain(spec) works in LIFE MILLIMETRES (the SPEC's) in the plan frame: the clypeal tip at z 0,
+z forward, +y up from the GROUND, +x the creature's LEFT. A body landmark's height h above the venter sits at
y = h + the venter's clearance (rest.coxa_h - procoxa_low.h - rest.coxa_over_procoxa: the coxa joints level at the
bind, the body keeps M1's attitude, plan §2.7). skeleton(spec, chain) multiplies ONCE by SPEC author_scale: rig.Skeleton
in metres at x10 (plan §4.3).

THE LEGS (plan §2.7, placement B; B3c, the lead 10-21: the stance from the live photographs, the evidence in this
order, each step taking what the earlier ones left free):
  (a) LENGTHS  each segment the MAX over its projections (a projection can only shorten): M1d's two sides, M3v's left
               legs scaled by EW, M1l's near legs where visible (SPEC legs.<pair>.coxa_knee / tibia / tarsus_claw)
  (b) COXAE    the fore leg's joint by M1l's procoxa (rest.coxa_h); the meso- and metacoxae's joints at their OWN height,
               the venter's lower surface where M3v puts them (rest.coxa_h_mh: B3b used the procoxa's rule for all
               three, which buried the mid and hind femora 1.9 mm in the venter)
  (c) FEET     t1-t4 lie flat at rest.ankle_h along P1's tarsus plan direction, t5 ARCHES up to the claw joint and the
               claws STAND ON THEIR TIPS at P3's measured angle (rest.claw_stand): the claw joint stands claw x
               sin(claw_stand) up, the claw tip on the ground beyond it in the tarsus's vertical plane
  (d) TIBIAE   B3d (the lead 10-22: both photos solved as PERSPECTIVE cameras, "the cameras" below): the mid and hind
               tibiae's ELEVATIONS P2's reconstruction measures (rest.tibia_e_P2), the fore leg its femur's (rest.
               femur_e_P2_fore: P2's fore foot stands on raised litter); the plan directions P3's image directions
               through its camera (rest.tibia_P3; fore, mid; on P2's side of the knee, B3c's rule) and P1's mean for the
               hind (P3 hides it). B3c read P2 and P3 as orthographic projections (tibia_from_photos, kept for the record)
  (e) HEIGHT   B3d: the venter off the ground the CONSENSUS of P2's and P3's perspective readings (rest.stand; B3c read P2
               as an orthographic side view, 8.67 mm: the clay on stilts, the knees under the venter)
  then P1 YIELDS LAST: the knee lies on the circle its femur reaches at the knee's height; its plan direction is taken
  within rest.femur_band of P1's own knee direction, where the tarsus tip lands nearest P1's point (P1's "claw" point
  is the tarsus's tip between the claws, res_c02); how far each tip moves is reported (solve_leg 'foot_moved').
The coxa-to-knee span includes the trochanter: the trochanter joint sits at the femur's exit (the coxa point), the
femur joint rig.trochanter along the span. The coxa's own pivot lies rig.coxa_medial medial and dorsal of the exit by
rig.coxa_len (plan §6.1, M3v).

skeleton(): §6.1's 104 joints; parents come before children; IK targets are leaves of the root (AG 05.19). Frames
(rig.frame_from) are the limbed family's: x along the bone to its child (or to a leaf's tip), y the side the child
folds toward, so a positive rotation about z = x cross y folds the joint the anatomical way (AG 05.7):
  body, pronotum, head, abdomen  ventral flexion
  mandible                       opens (the tip swings out), like the wolf's jaw
  antenna_0 (the scape)          tucks back along the head, like the wolf's ears; antenna_1..3 flex toward the scape
  lamella_0..3                   fan (each tip toward the club's end)
  palps                          curl ventrally
  elytron                        lifts (opens); wing_0..2 spread out (a convention: the folded rest is the closed
                                 limit, B14)
  coxa                           remotion (the leg swings back: no anatomical flexion, the wolf's scapula convention)
  trochanter                     levation (the knee rises); femur (the trochanter-femur joint, +-10) the knee back
  tibia                          flexion (the ankle toward the femur)
  tarsus_1..5, claw              curl ventrally (the wolf's digits; B3c: t5 arches up and the claw stands down, so
                                 the bind's t5 is dorsiflexed and its claw flexed past the B3 limits, plan §6.3)
The right side is the left reflected under one written rule (AG 05.8): p_R = M p_L and F_R = M F_L diag(1, 1, -1),
M = diag(-1, 1, 1). sk.meta[name]: role, tier (0 body, 1 tarsi / wings / lamellae / IK, 2 face), side, fold, tip,
driver, parent, axis (the mandible's true hinge axis, world, where it differs from z; mirrored as z is, a_R = -M a_L,
so a positive turn about it opens either mandible, as about z).
"""
import numpy as np
from scipy.optimize import brentq

from .. import rig as RG
from ..heads import insect as HEAD

M_MIRROR = np.diag([-1.0, 1.0, 1.0])
FLIP_Z = np.diag([1.0, 1.0, -1.0])
CRANIAL, CAUDAL = np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, -1.0])
DORSAL, VENTRAL = np.array([0.0, 1.0, 0.0]), np.array([0.0, -1.0, 0.0])
LATERAL = np.array([1.0, 0.0, 0.0])          # the left side's outward
LEGS = (('f', 'fore', 'pro', 0), ('m', 'mid', 'meso', 1), ('h', 'hind', 'meta', 2))


def mirror_point(p):
    return M_MIRROR @ np.asarray(p, np.float64)


def mirror_frame(F):
    """AG 05.8's written rule: reflect across the sagittal plane, then negate only the bend axis z"""
    return M_MIRROR @ np.asarray(F, np.float64) @ FLIP_Z


def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


def plan_dir(deg, elev=0.0):
    """a unit vector deg from forward toward the left side in plan, raised elev (degrees)"""
    a, e = np.radians(deg), np.radians(elev)
    return np.array([np.sin(a) * np.cos(e), np.sin(e), np.cos(a) * np.cos(e)])


def clearance(spec):
    """the venter's height off the ground at the bind (plan §2.7: 0.55 mm)"""
    r = spec['rest']
    return r['coxa_h'] - (spec['landmarks']['procoxa_low'][1] + r['coxa_over_procoxa'])


# --------------------------------------------------------------------------------------------- the cameras (B3d)
# The lead, B3d 10-22: P2 is a close PERSPECTIVE photo (its near mid tibia images 1.24x+ its true length against the
# body's depth scale: a projection can only shorten, so the near legs are magnified), not the orthographic side view B3c
# read it as (the venter at 8.67 mm stood the clay on stilts, the knees under the venter). Both standing photos are
# solved as PINHOLE cameras in the rest frame (y up from the ground, x the left side, z forward), each from the known
# lengths in its own frame:
#   P3  the Coolpix S6's focal length from its EXIF (rest.P3_f_px), the scale and so the distance from the elytral width
#       (rest.P3_EW_px at the elytra's widest station), the pitch from the mid and hind ground contacts at P1's foot
#       layout (rest.P3_pitch); the venter's lowest point and the mid tarsus tips stand at one depth (within 0.7 mm), so
#       its reading barely moves with the camera
#   P2  no EXIF: f = s D, the midline scale s and the body's pitch fitted on the traced body points and the venter's
#       silhouette (rest.P2_body_px, P2_venter_px), the camera level with its horizon at the far litter's edge
#       (rest.P2_horizon_px); the near mid and hind legs free on their known lengths through their traced knees and
#       feet (rest.P2_knee_px, P2_foot_px, within P2_tol_px; a foot at or past the traced end: the litter hides it) with
#       both ankles on one level ground; D is where that fits best (p2_reconstruct)
def pinhole(C, fwd, f, c, up=(0.0, 1.0, 0.0)):
    """a pinhole camera at C looking along fwd (image right = fwd x up, image y down), focal f px, principal point c"""
    fwd = _unit(fwd)
    right = _unit(np.cross(fwd, np.asarray(up, np.float64)))
    return dict(C=np.asarray(C, np.float64), Rw=np.vstack([right, np.cross(fwd, right), fwd]), f=float(f),
                c=(float(c[0]), float(c[1])))


def cam_project(P, cam):
    """world points (n, 3) -> image px (n, 2)"""
    Q = (np.atleast_2d(np.asarray(P, np.float64)) - cam['C']) @ cam['Rw'].T
    return np.column_stack([cam['c'][0] + cam['f'] * Q[:, 0] / Q[:, 2], cam['c'][1] + cam['f'] * Q[:, 1] / Q[:, 2]])


def cam_ray(px, cam):
    d = np.array([(px[0] - cam['c'][0]) / cam['f'], (px[1] - cam['c'][1]) / cam['f'], 1.0]) @ cam['Rw']
    return cam['C'], d / np.linalg.norm(d)


def _ray_sphere(O, d, Cs, r):
    oc = O - Cs
    b = float(d @ oc)
    disc = b * b - float(oc @ oc - r * r)
    if disc < 0.0:
        return []
    s = np.sqrt(disc)
    return [-b - s, -b + s]


def p3_camera(spec, pitch=None, axis_h=None):
    """P3 (rest frame): f from its EXIF, the camera f / (EW px / EW) from the elytra's widest station (z of M1d's
    ely_widest), looking back along -z pitched down; its axis axis_h over the ground at that station"""
    r, b = spec['rest'], spec['body']
    f = r['P3_f_px']
    D = f * b['EW'] / r['P3_EW_px']
    th = np.radians(r['P3_pitch'] if pitch is None else pitch)
    z_ew = -(b['BL'] - b['EL']) - b['ely_widest']
    fwd = np.array([0.0, -np.sin(th), -np.cos(th)])
    h = r['P3_axis_h'] if axis_h is None else axis_h
    return pinhole(np.array([0.0, h, z_ew]) - D * fwd, fwd, f, (0.5 * r['P3_size'][0], 0.5 * r['P3_size'][1]))


def p3_pitch(spec):
    """P3's pitch and axis height from its mid and hind ground contacts (rest.P3_contact_rows) at P1's foot points
    (the fore feet are braced forward in the display: P1's layout does not hold for them). Returns (pitch, axis_h)"""
    from scipy.optimize import least_squares
    r = spec['rest']

    def res(p):
        cam = p3_camera(spec, np.degrees(p[0]), p[1])
        out = []
        for i, pair in ((1, 'mid'), (2, 'hind')):
            P = p1_point(spec, pair, i)
            a = cam_project(np.array([P, mirror_point(P)]), cam)
            out.append(float(a[:, 1].mean()) - r['P3_contact_rows'][i - 1])
        return out
    sol = least_squares(res, [np.radians(15.0), 15.0])
    return float(np.degrees(sol.x[0])), float(sol.x[1])


def p3_stand(spec):
    """the venter's lowest point over the ground read through P3's camera: the camera's axis height and the venter's
    height solved so the mid tarsus tips (P1's points, the claws' lift up) and the venter's midline silhouette point
    (rest.P3_venter_px) project on their traced rows (rest.P3_tip_rows). Returns (v, axis_h)"""
    from scipy.optimize import least_squares
    r, lm = spec['rest'], spec['landmarks']
    P = p1_point(spec, 'mid', 1) + np.array([0.0, claw_lift(spec, 'mid'), 0.0])

    def res(p):
        cam = p3_camera(spec, axis_h=p[0])
        a = cam_project(np.array([P, mirror_point(P), [0.0, p[1], lm['venter'][0]]]), cam)
        return [float(a[:2, 1].mean()) - float(np.mean(r['P3_tip_rows'])), float(a[2, 1]) - r['P3_venter_px'][1]]
    sol = least_squares(res, [15.0, 4.0])
    return float(sol.x[1]), float(sol.x[0])


def _p2_body(spec):
    """P2's body points (rest frame at clearance 0, the near side the RIGHT: x < 0) and the ventral line"""
    from . import arthropod_parts as AP
    lm = spec['landmarks']
    body = [(0.0, lm[k][1], lm[k][0]) for k in ('ely_apex', 'ely_top', 'ely_base_top')]
    vb = dict(AP.VENTER['bot'])
    vb[lm['venter'][0]] = lm['venter'][1]
    vz = np.array(sorted(vb))
    return np.array(body), np.column_stack([np.zeros(len(vz)), [vb[z] for z in vz], vz])


def p2_camera_fit(spec, D, eye_row):
    """P2's camera at distance D from the midline (A): the body pitched beta about its venter landmark (placed 10 mm
    over a provisional ground), the scale s and the axis point fitted on the body points and the venter's silhouette
    row; the camera level, its horizon at eye_row (its pitch from it). Returns dict(cam, beta, s, low (the venter's
    lowest world height), to_world)"""
    from scipy.optimize import least_squares
    r, lm = spec['rest'], spec['landmarks']
    W, H = r['P2_size']
    cc = (0.5 * W, 0.5 * H)
    body, vprof = _p2_body(spec)
    bpx = np.asarray(r['P2_body_px'], np.float64)

    def to_world(Pb, beta):
        Pb = np.atleast_2d(np.asarray(Pb, np.float64)) - np.array([0.0, 0.0, lm['venter'][0]])
        c_, s_ = np.cos(beta), np.sin(beta)
        Rb = np.array([[1.0, 0.0, 0.0], [0.0, c_, s_], [0.0, -s_, c_]]).T     # nose up: +z toward +y
        return Pb @ Rb.T + np.array([0.0, 10.0, 0.0])

    def cam_of(s, u0, w0):
        th = np.arctan((cc[1] - eye_row) / (s * D))
        fwd = np.array([np.cos(th), -np.sin(th), 0.0])                   # from the right side (-x) looking +x
        return pinhole(np.array([0.0, w0, u0]) - D * fwd, fwd, s * D, cc)

    def res(p):
        beta, s, u0, w0 = p
        cam = cam_of(s, u0, w0)
        rr = list(((cam_project(to_world(body, beta), cam) - bpx) / 6.0).ravel())
        vp = cam_project(to_world(vprof, beta), cam)
        rr.append((vp[:, 1].max() - r['P2_venter_px'][1]) / 15.0)
        return np.array(rr)
    sol = least_squares(res, [np.radians(7.0), 22.5, -26.0, 14.0], x_scale=[0.05, 1.0, 3.0, 3.0])
    beta, s, u0, w0 = sol.x
    cam = cam_of(s, u0, w0)
    return dict(cam=cam, beta=float(beta), s=float(s), low=float(to_world(vprof, beta)[:, 1].min()),
                to_world=lambda Pb: to_world(Pb, beta), rms=float(np.sqrt(np.mean(sol.fun[:-1] ** 2)) * 6.0))


def p2_legs(spec, A_, tol=None):
    """(C) P2's near mid and hind legs free on their known lengths with both ankles on one level ground: the knee on
    the femur sphere about its coxa joint, the tibia's direction; residuals the knees' images against the trace, the
    ankles' images on the traced tibia line at or past the traced foot (tol px), the ankles ankle_h over the ground.
    Returns dict(cost, ground, legs {pair: K, A (world), femur / tibia elevation, the tibia's plan direction (from
    forward toward the near side)})"""
    from scipy.optimize import least_squares
    r, lg, cx = spec['rest'], spec['legs'], spec['coxae']
    tol = r['P2_tol_px'] if tol is None else tol
    cam = A_['cam']
    kn, ft = np.asarray(r['P2_knee_px'], np.float64), np.asarray(r['P2_foot_px'], np.float64)
    pairs = ((1, 'mid', 'meso'), (2, 'hind', 'meta'))
    Cw = {p: A_['to_world']((-cx[c][0], r['coxa_h_mh'][i - 1], cx[c][1]))[0] for i, p, c in pairs}

    def legpts(p, q):
        az, el, taz, tel = q
        K = Cw[p] + lg[p]['coxa_knee'] * np.array([-np.cos(el) * np.cos(az), np.sin(el), np.cos(el) * np.sin(az)])
        return K, K + lg[p]['tibia'] * np.array([-np.cos(tel) * np.cos(taz), -np.sin(tel), np.cos(tel) * np.sin(taz)])

    def res(x):
        out = []
        for j, (i, p, _) in enumerate(pairs):
            K, A = legpts(p, x[1 + 4 * j:5 + 4 * j])
            ik, ia = cam_project(np.vstack([K, A]), cam)
            out += list((ik - kn[i]) / tol)
            dl = (ft[i] - kn[i]) / np.linalg.norm(ft[i] - kn[i])
            out.append(float((ia - ft[i]) @ np.array([-dl[1], dl[0]])) / tol)
            out.append(min(float((ia - ft[i]) @ dl), 0.0) / tol)
            out.append((A[1] - (x[0] + r['ankle_h'])) / 0.1)
        return np.array(out)
    best = None
    for g0 in (A_['low'] - 3.0, A_['low'] - 5.0, A_['low'] - 7.0):
        for az0 in (-0.5, 0.2):
            for taz0 in (0.3, 0.9):
                x0 = [g0, az0, 0.15, taz0, 0.7, az0, 0.15, -taz0, 0.7]
                sol = least_squares(res, x0)
                if best is None or sol.cost < best.cost:
                    best = sol
    legs = {}
    for j, (i, p, _) in enumerate(pairs):
        K, A = legpts(p, best.x[1 + 4 * j:5 + 4 * j])
        t = A - K
        legs[p] = dict(K=K, A=A, femur_elev=float(np.degrees(np.arcsin((K[1] - Cw[p][1]) / lg[p]['coxa_knee']))),
                       tibia_elev=float(np.degrees(np.arcsin(-t[1] / lg[p]['tibia']))),
                       tibia_plan=float(np.degrees(np.arctan2(-t[0], t[2]))), knee_over_venter=float(K[1] - A_['low']))
    return dict(cost=float(best.cost), ground=float(best.x[0]), legs=legs)


def p2_fore(spec, A_):
    """P2's near fore femur: the knee on its ray at the femur's length from the procoxa joint (the near root); its
    elevation (P2's fore foot stands on raised litter, so its tibia is not a flat-ground direction: the femur is)"""
    r, lg, cx = spec['rest'], spec['legs'], spec['coxae']
    C = A_['to_world']((-cx['pro'][0], r['coxa_h'] - clearance(spec), cx['pro'][1]))[0]
    O, d = cam_ray(np.asarray(r['P2_knee_px'][0], np.float64), A_['cam'])
    t = _ray_sphere(O, d, C, lg['fore']['coxa_knee'])
    if not t:
        return None
    K = O + t[0] * d
    return dict(K=K, femur_elev=float(np.degrees(np.arcsin((K[1] - C[1]) / lg['fore']['coxa_knee']))),
                knee_over_venter=float(K[1] - A_['low']))


P2_FIT = 1.0e-3        # p2_legs' cost below which the near legs meet the trace within its tolerance (no strain)


def p2_reconstruct(spec, Ds=None):
    """P2 solved: per horizon row (rest.P2_horizon_px) THE FARTHEST CAMERA THE NEAR LEGS ALLOW. The legs fit the trace
    exactly (cost under P2_FIT) at every D up to a limit and strain beyond it (the near mid tibia's image is too long
    for its length at a weaker magnification): the fit does not pick D below the limit, and the venter's height falls
    with D there (a closer camera magnifies the near ankles more, so they stand higher). A real macro rig stands
    FARTHER than the limit (a 50 mm lens at P2's 23 px / mm on a 35 mm frame stands about 160 mm off; at the limit
    the lens would be about 17 mm), so the limit is the reading, and the venter there is an upper bound at P2's own
    proportions. Bisected to 0.05 mm on D. Returns dict(per row: D, f, cost, v, legs, fore, beta, s), and the means"""
    r = spec['rest']
    Ds = np.arange(44.0, 90.01, 2.0) if Ds is None else Ds
    out = {}
    for eye in r['P2_horizon_px']:
        ok = None
        for D in Ds:
            A_ = p2_camera_fit(spec, D, eye)
            L = p2_legs(spec, A_)
            if L['cost'] < P2_FIT:
                ok = D
            elif ok is not None:
                break
        assert ok is not None, f'P2 (horizon {eye}): the near legs meet the trace at no camera distance'
        lo, hi = ok, ok + float(Ds[1] - Ds[0])
        while hi - lo > 0.05:
            m = 0.5 * (lo + hi)
            if p2_legs(spec, p2_camera_fit(spec, m, eye))['cost'] < P2_FIT:
                lo = m
            else:
                hi = m
        D = lo
        A_ = p2_camera_fit(spec, D, eye)
        L = p2_legs(spec, A_)
        out[eye] = dict(D=float(D), f=A_['s'] * D, s=A_['s'], beta=float(np.degrees(A_['beta'])), cost=L['cost'],
                        v=A_['low'] - L['ground'], legs=L['legs'], fore=p2_fore(spec, A_), rms=A_['rms'],
                        horizon=float(eye))
    rows = list(out.values())
    out['mean'] = dict(v=float(np.mean([q['v'] for q in rows])), D=float(np.mean([q['D'] for q in rows])),
                       tibia_elev=tuple(float(np.mean([q['legs'][p]['tibia_elev'] for q in rows])) for p in ('mid', 'hind')),
                       femur_elev_fore=float(np.mean([q['fore']['femur_elev'] for q in rows])))
    return out


# --------------------------------------------------------------------------------------------- the legs (B3c)
def tibia_dir(phi, e):
    """the tibia's unit direction, knee to ankle: phi deg from forward toward the left side in plan, e deg down"""
    return plan_dir(phi, -e)


def image_p2(d):
    """the image direction of the knee-to-ankle vector d in P2's projection (a side view, level camera, the creature
    facing image-right): degrees below the image horizontal measured from forward (90 + = the ankle behind the knee)"""
    return float(np.degrees(np.arctan2(-d[1], d[2])))


def image_p3(d, elev):
    """the image direction of d in P3's projection (the front view, the camera elev deg above the ground, the left
    side on the image's right): degrees below the image horizontal measured outward"""
    a = np.radians(elev)
    return float(np.degrees(np.arctan2(-(d[1] * np.cos(a) - d[2] * np.sin(a)), d[0])))


def coxa_joint(spec, pair, cox, clear):
    """the femur's exit (the trochanter joint) at the bind, life mm: placement B's (x, z) (SPEC coxae); its height the
    procoxa's rule for the fore leg (rest.coxa_h, M1l's procoxa + coxa_over_procoxa over the venter) and the meso- and
    metacoxa's own (rest.coxa_h_mh: the venter's lower surface there, B3c) above the venter's lowest point"""
    r = spec['rest']
    cx, cz = spec['coxae'][cox]
    h = r['coxa_h'] if pair == 'fore' else clear + r['coxa_h_mh'][0 if pair == 'mid' else 1]
    return np.array([cx, h, cz])


def claw_lift(spec, pair):
    """(c) the claw joint's height: the claw standing on its tip at P3's angle"""
    return spec['legs'][pair]['claw'] * np.sin(np.radians(spec['rest']['claw_stand']))


def tarsus_points(spec, pair, i, A):
    """(c) the tarsus from the ankle A (on the ground at rest.ankle_h): t1-t4 FLAT along P1's tarsus plan direction by
    B1's tarsomeres, t5 ARCHING up from the t4 joint to the claw joint (claw_lift), the claw STANDING on its tip on the
    ground beyond it at rest.claw_stand. Returns the points (7, 3): tarsus_1 (the ankle) .. tarsus_5, the claw joint
    (the tip), the claw tip"""
    r, L = spec['rest'], spec['legs'][pair]
    u = plan_dir(r['tarsus_dir'][i])
    tm = np.asarray(L['tarsomeres'], np.float64)
    J = [np.asarray(A, np.float64)]
    for n in range(4):
        J.append(J[-1] + tm[n] * u)
    rise = claw_lift(spec, pair) - r['ankle_h']
    J.append(J[-1] + np.sqrt(tm[4] ** 2 - rise ** 2) * u + np.array([0.0, rise, 0.0]))
    g = np.radians(r['claw_stand'])
    J.append(J[-1] + L['claw'] * (np.cos(g) * u - np.array([0.0, np.sin(g), 0.0])))
    return np.vstack(J)


def image_p3_persp(K, A, cam):
    """the image direction of the left tibia K -> A through P3's pinhole camera: degrees below the image horizontal,
    measured outward (the left side on the image's right)"""
    a = cam_project(np.vstack([K, A]), cam)
    d = a[1] - a[0]
    return float(np.degrees(np.arctan2(d[1], d[0])))


def image_p2_persp(K, A, spec, cam_fit):
    """the image direction of the left tibia K -> A (rest frame) through P2's camera (cam_fit: p2_camera_fit's), the
    leg mirrored to P2's near (right) side with the rest skeleton's venter landmark under P2's: degrees below the image
    horizontal measured from forward (printed beside the reconstruction)"""
    P = np.vstack([K, A]) * np.array([-1.0, 1.0, 1.0]) - np.array([0.0, clearance(spec), spec['landmarks']['venter'][0]])
    a = cam_project(P + np.array([0.0, cam_fit['low'], 0.0]), cam_fit['cam'])
    d = a[1] - a[0]
    return float(np.degrees(np.arctan2(d[1], d[0])))


def tibia_persp(spec, pair, i, K, e, cam3=None):
    """(d), B3d: the tibia's plan direction at elevation e from the knee K: P3's traced image direction (rest.tibia_P3)
    through P3's camera (fore, mid; brentq over the plan directions); the hind keeps P1's mean plan direction (P3 hides
    it). Returns phi"""
    r = spec['rest']
    if pair == 'hind':
        return r['tibia_dir'][i]
    cam3 = p3_camera(spec) if cam3 is None else cam3
    Lt = spec['legs'][pair]['tibia']
    f = lambda ph: image_p3_persp(K, K + Lt * tibia_dir(ph, e), cam3) - r['tibia_P3'][i]      # noqa: E731
    ph = np.arange(0.5, 179.6, 1.0)
    rv = np.array([f(p) for p in ph])
    k = [j for j in range(len(ph) - 1) if rv[j] * rv[j + 1] < 0.0 and max(abs(rv[j]), abs(rv[j + 1])) < 60.0]
    assert k, f'{pair} tibia: no plan direction meets P3\'s image direction at elevation {e:.2f}'
    # P3's direction admits a forward and a backward reading: B3c's rule, the one on P2's side of the knee (forward
    # where P2's traced ankle stands ahead of its knee, P2 facing image-right), nearest P1's mean among them
    roots = [brentq(f, ph[j], ph[j + 1], xtol=1e-10) for j in k]
    fwd = r['P2_foot_px'][i][0] > r['P2_knee_px'][i][0]
    side = [q for q in roots if (q < 90.0) == fwd] or roots
    return float(min(side, key=lambda q: abs(q - r['tibia_dir'][i])))


def tibia_from_photos(spec, pair, i):
    """B3c's (d), ORTHOGRAPHIC (kept for the record: b01 prints it; B3d reads both photos in perspective, solve_leg):
    the tibia's plan direction and elevation (degrees) from its image directions: P2's (rest.tibia_P2, every
    leg) gives the elevation at a plan direction exactly (brentq); for the fore and mid legs P3's (rest.tibia_P3) then
    fixes the plan direction (brentq over the plan directions on P2's side of the knee: forward where P2's ankle stands
    ahead of its knee); the hind tibia keeps P1's mean plan direction (rest.tibia_dir). Returns (phi, e, how)"""
    r = spec['rest']
    t2 = r['tibia_P2'][i]

    def elev(phi):
        f = lambda e: image_p2(tibia_dir(phi, e)) - t2          # noqa: E731
        return brentq(f, 1e-6, 89.999, xtol=1e-12) if f(1e-6) * f(89.999) < 0.0 else None
    if pair == 'hind':
        phi = r['tibia_dir'][i]
        return phi, elev(phi), 'P2\'s image direction at P1\'s plan direction (P3 does not show the hind tibia)'
    t3 = r['tibia_P3'][i]
    lo, hi = (0.5, 89.5) if t2 < 90.0 else (90.5, 179.5)

    def res(phi):
        e = elev(phi)
        return 1e3 if e is None else image_p3(tibia_dir(phi, e), r['P3_elev']) - t3
    ph = np.arange(lo, hi + 1e-9, 0.5)
    rv = np.array([res(p) for p in ph])
    k = [j for j in range(len(ph) - 1) if rv[j] * rv[j + 1] < 0.0 and max(abs(rv[j]), abs(rv[j + 1])) < 90.0]
    assert k, f'{pair} tibia: no plan direction meets P2\'s and P3\'s image directions'
    phi = brentq(res, ph[k[0]], ph[k[0] + 1], xtol=1e-12)
    return phi, elev(phi), 'P2\'s and P3\'s image directions'


def p1_point(spec, pair, i):
    """P1's "claw" point (the tarsus tip between the claws), life mm in the plan frame on the ground: its span and its
    station in P1's pronotum widths x B1's PW (the fore from the clypeal tip, the mid and hind from the elytral base)"""
    b, r = spec['body'], spec['rest']
    zref = 0.0 if pair == 'fore' else -(b['BL'] - b['EL'])
    return np.array([0.5 * r['claw_span_PW'][i] * b['PW'], 0.0, zref + r['claw_z_PW'][i] * b['PW']])


def solve_leg(spec, pair, cox, i, clear):
    """one left leg at the bind (module docstring (a)-(e), then P1 yields last): its joint points and the numbers of
    each step"""
    b, r, rg, L = spec['body'], spec['rest'], spec['rig'], spec['legs'][pair]
    PW = b['PW']
    C = coxa_joint(spec, pair, cox, clear)
    Lt, Lf = L['tibia'], L['coxa_knee']
    # (d), B3d: the ELEVATIONS from P2's perspective reconstruction (p2_reconstruct): the mid and hind tibiae's
    # (rest.tibia_e_P2); the fore femur's (rest.femur_e_P2_fore: P2's fore foot stands on raised litter, so its tibia is
    # no flat-ground direction, its femur is), the fore tibia then the closure's
    if pair == 'fore':
        Ky = C[1] + Lf * np.sin(np.radians(r['femur_e_P2_fore']))
        e = float(np.degrees(np.arcsin((Ky - r['ankle_h']) / Lt)))
        how = 'the elevation from P2\'s reconstructed fore femur, the plan direction P3\'s image direction (perspective)'
    else:
        e = r['tibia_e_P2'][i - 1]
        Ky = r['ankle_h'] + Lt * np.sin(np.radians(e))
        how = ('the elevation P2\'s reconstruction, the plan direction ' +
               ('P3\'s image direction (perspective)' if pair == 'mid' else 'P1\'s (P3 hides the hind tibia)'))
    if abs(Ky - C[1]) >= Lf:
        raise ValueError(f'{pair} leg: the knee at h {Ky:.3f} (the tibia {e:.2f} deg down) lies beyond the femur\'s '
                         f'{Lf} from the coxa joint at {C[1]:.3f}')
    Rk = float(np.sqrt(Lf ** 2 - (Ky - C[1]) ** 2))
    P1 = p1_point(spec, pair, i)
    kd = r['knee_dir_P1'][i]
    cam3 = p3_camera(spec)
    phi = r['tibia_dir'][i]
    for _ in range(12):
        d = tibia_dir(phi, e)
        # the tarsus tip relative to the knee (the tarsus is rigid in plan once the tibia's direction is set)
        off = tarsus_points(spec, pair, i, Lt * d)[5]
        # P1 yields last: the femur's plan direction within femur_band of P1's own knee direction, where the tip lands
        # nearest P1's point (on the knee's circle the nearest point is the direction of P1 - C - off, clamped)
        w = (P1 - C - off)[[0, 2]]
        best = float(np.degrees(np.arctan2(w[0], w[1])))
        fdir = float(np.clip(best, kd - r['femur_band'], kd + r['femur_band']))
        K = np.array([C[0] + Rk * np.sin(np.radians(fdir)), Ky, C[2] + Rk * np.cos(np.radians(fdir))])
        phi_new = tibia_persp(spec, pair, i, K, e, cam3)              # P3's direction seen from where the knee stands
        if abs(phi_new - phi) < 1e-10:
            break
        phi = phi_new
    d = tibia_dir(phi, e)
    A = K + Lt * d
    tar = tarsus_points(spec, pair, i, A)
    F = C + rg['trochanter'] * _unit(K - C)
    pivot = C + np.array([-rg['coxa_medial'], np.sqrt(rg['coxa_len'] ** 2 - rg['coxa_medial'] ** 2), 0.0])
    bound_pw = float(np.degrees(np.arccos(min(1.0, r['tibia_plan_PW'][i] * PW / Lt))))
    bound_el = float(np.degrees(np.arccos(min(1.0, r['tibia_plan_EL'][i] * b['EL'] / Lt))))
    moved = tar[5] - P1
    return dict(pivot=pivot, coxa=C, femur=F, knee=K, ankle=A, tip=tar[5], claw=tar[6], tarsus=tar, tibia_elev=e,
                femur_elev=float(np.degrees(np.arcsin((K[1] - C[1]) / Lf))), femur_dir=fdir, femur_dir_free=best,
                knee_bend=float(np.degrees(np.arccos(np.clip(_unit(K - C) @ d, -1.0, 1.0)))),
                bound_PW=bound_pw, bound_EL=bound_el, tibia_dir=phi, tibia_dir_from=how,
                image_P2=image_p2(d), image_P3=image_p3(d, r['P3_elev']), image_P3_persp=image_p3_persp(K, A, cam3),
                P1=P1,
                foot_moved=float(np.linalg.norm(moved[[0, 2]])), foot_moved_xz=moved[[0, 2]].copy(),
                lift=float(claw_lift(spec, pair)))


# --------------------------------------------------------------------------------------------- the rest chain
def rest_chain(spec):
    """the bind pose's points in life mm (module docstring): dict(pos={name: (3,)}, legs={pair: solve_leg's dict},
    head=dict(origin, p, q, lm), clearance, scale_m (metres per life mm at the author scale))"""
    b, lm, rg = spec['body'], spec['landmarks'], spec['rig']
    clear = clearance(spec)
    Y = lambda h: h + clear
    at = lambda z, h, x=0.0: np.array([x, Y(h), z])
    P = {}
    z_base = -(b['BL'] - b['EL'])
    P['body'] = at(rg['body'][0], rg['body'][1])
    P['root'] = np.array([0.0, 0.0, rg['body'][0]])
    P['pronotum'] = at(z_base, rg['waist_h'])
    hd = HEAD.neck(spec)
    P['head'] = at(hd[2], hd[1])
    for k, (z, h) in zip(('abdomen_0', 'abdomen_1', 'abdomen_tip'), rg['abdomen']):
        P[k] = at(z, h)
    e = rg['elytron']
    P['elytron_L'] = at(e[1], e[2], e[0])
    P['elytron_tip_L'] = at(lm['ely_apex'][0], lm['ely_apex'][1], rg['elytron_tip_x'])
    for k, (x, z, h) in zip(('wing_0_L', 'wing_1_L', 'wing_2_L', 'wing_tip_L'), rg['wing']):
        P[k] = at(z, h, x)
    legs = {}
    for c, pair, cox, i in LEGS:
        g = solve_leg(spec, pair, cox, i, clear)
        legs[pair] = g
        P[f'coxa_{c}_L'], P[f'trochanter_{c}_L'], P[f'femur_{c}_L'] = g['pivot'], g['coxa'], g['femur']
        P[f'tibia_{c}_L'] = g['knee']
        for n in range(5):
            P[f'tarsus_{n + 1}_{c}_L'] = g['tarsus'][n]
        P[f'claw_{c}_L'] = g['tarsus'][5]
        P[f'claw_tip_{c}_L'] = g['tarsus'][6]
    # the head: the archetype's landmarks in its frame, at the bind p = +z, q = +y (M1's attitude, plan §2.7)
    p_ax, q_ax = CRANIAL.copy(), DORSAL.copy()
    lmw = HEAD.landmarks(spec, P['head'], p_ax, q_ax)
    for k in [k for k in lmw if k.endswith('_L') and not np.isscalar(lmw[k])]:
        lmw[k[:-2] + '_R'] = mirror_point(lmw[k])              # points and directions alike: M is linear
    for k in [k for k in P if k.endswith('_L')]:
        P[k[:-2] + '_R'] = mirror_point(P[k])
    return dict(pos=P, legs=legs, head=dict(origin=P['head'], p=p_ax, q=q_ax, lm=lmw), clearance=clear,
                scale_m=spec['author_scale'] * 1e-3)


# --------------------------------------------------------------------------------------------- the skeleton
def skeleton(spec, chain, scale=None):
    """§6.1's 104 joints as rig.Skeleton in metres at the author scale (module docstring); sk.meta holds each joint's
    role, tier, side, fold, tip (metres), driver, parent and axis"""
    s = chain['scale_m'] if scale is None else scale
    P, lm = chain['pos'], chain['head']['lm']
    sk = RG.Skeleton()
    sk.meta = {}

    def add(name, parent, pos, x=None, fold=None, role='', tier=0, tip=None, driver=None, frame=None, axis=None):
        if frame is None:
            frame = RG.frame_from(x, fold)
        sk.add(name, parent, np.asarray(pos, np.float64) * s, frame)
        side = 'L' if name.endswith('_L') else ('R' if name.endswith('_R') else '')
        sk.meta[name] = dict(role=role, tier=tier, side=side, parent=parent, driver=driver,
                             fold=None if fold is None else np.asarray(fold, np.float64),
                             tip=None if tip is None else np.asarray(tip, np.float64) * s,
                             axis=None if axis is None else np.asarray(axis, np.float64))

    def frame(name):
        return sk.world[sk.index(name)][:3, :3]

    def mirror(names):
        sw = lambda n: n[:-2] + '_R' if (n and n.endswith('_L')) else n
        for n in names:
            m = sk.meta[n]
            W = sk.world[sk.index(n)]
            add(sw(n), sw(m['parent']), mirror_point(W[:3, 3]) / s, role=m['role'], tier=m['tier'],
                driver=sw(m['driver']), fold=None if m['fold'] is None else mirror_point(m['fold']),
                tip=None if m['tip'] is None else mirror_point(m['tip']) / s,
                axis=None if m['axis'] is None else -(M_MIRROR @ m['axis']), frame=mirror_frame(W[:3, :3]))

    def toward(p, j, x):
        """the direction from the joint j toward the point p, made perpendicular to x (a hinge's fold side)"""
        v = np.asarray(p, np.float64) - np.asarray(j, np.float64)
        return v - x * (v @ x) / (x @ x)

    # ---- root, body, abdomen, pronotum, head
    add('root', None, P['root'], role='root', frame=np.eye(3))
    add('body', 'root', P['body'], P['pronotum'] - P['body'], VENTRAL, 'body')
    add('abdomen_0', 'body', P['abdomen_0'], P['abdomen_1'] - P['abdomen_0'], VENTRAL, 'abdomen')
    add('abdomen_1', 'abdomen_0', P['abdomen_1'], P['abdomen_tip'] - P['abdomen_1'], VENTRAL, 'abdomen',
        tip=P['abdomen_tip'])
    add('pronotum', 'body', P['pronotum'], P['head'] - P['pronotum'], VENTRAL, 'pronotum')
    add('head', 'pronotum', P['head'], lm['clypeal_tip'] - P['head'], VENTRAL, 'head', tip=lm['clypeal_tip'])
    # ---- the head's members (heads/insect.py): mandible, antenna and lamellae, palps
    mx = lm['mandible_tip_L'] - lm['mandible_L']
    opens = np.cross(lm['mandible_axis_L'], mx)
    opens = opens if opens[0] > 0.0 else -opens
    add('mandible_L', 'head', lm['mandible_L'], mx, opens, 'mandible', tip=lm['mandible_tip_L'],
        axis=lm['mandible_axis_L'])
    ant = ['antenna_0_L', 'antenna_1_L', 'antenna_2_L', 'antenna_3_L']
    s0 = lm['antenna_0_L']
    add('antenna_0_L', 'head', s0, lm['antenna_1_L'] - s0, CAUDAL, 'antenna', 2)
    for k in (1, 2, 3):
        a = lm[f'antenna_{k}_L']
        nxt = lm[f'antenna_{k + 1}_L'] if k < 3 else lm['antenna_tip_L']
        add(f'antenna_{k}_L', f'antenna_{k - 1}_L', a, nxt - a, toward(s0, a, nxt - a), 'antenna', 2,
            tip=lm['antenna_tip_L'] if k == 3 else None)
    club = lm['antenna_tip_L'] - lm['antenna_3_L']
    for k in range(4):
        a, t = lm[f'lamella_{k}_L'], lm[f'lamella_tip_{k}_L']
        add(f'lamella_{k}_L', 'antenna_3_L', a, t - a, club, 'lamella', 1, tip=t)
        ant.append(f'lamella_{k}_L')
    add('palp_max_0_L', 'head', lm['palp_max_0_L'], lm['palp_max_1_L'] - lm['palp_max_0_L'], VENTRAL, 'palp', 2)
    add('palp_max_1_L', 'palp_max_0_L', lm['palp_max_1_L'], lm['palp_max_tip_L'] - lm['palp_max_1_L'], VENTRAL,
        'palp', 2, tip=lm['palp_max_tip_L'])
    add('palp_lab_0_L', 'head', lm['palp_lab_0_L'], lm['palp_lab_tip_L'] - lm['palp_lab_0_L'], VENTRAL, 'palp', 2,
        tip=lm['palp_lab_tip_L'])
    mirror(['mandible_L'] + ant + ['palp_max_0_L', 'palp_max_1_L', 'palp_lab_0_L'])
    # ---- elytra and hindwings (on the body)
    add('elytron_L', 'body', P['elytron_L'], P['elytron_tip_L'] - P['elytron_L'], DORSAL, 'elytron',
        tip=P['elytron_tip_L'])
    wings = ['wing_0_L', 'wing_1_L', 'wing_2_L']
    for k, n in enumerate(wings):
        nxt = P[wings[k + 1]] if k < 2 else P['wing_tip_L']
        add(n, 'body' if k == 0 else wings[k - 1], P[n], nxt - P[n], LATERAL, 'wing', 1,
            tip=P['wing_tip_L'] if k == 2 else None)
    mirror(['elytron_L'] + wings)
    # ---- legs: the fore legs on the pronotum, the others on the body
    iks = []
    for c, pair, cox, i in LEGS:
        names = [f'coxa_{c}_L', f'trochanter_{c}_L', f'femur_{c}_L', f'tibia_{c}_L'] + [
            f'tarsus_{n}_{c}_L' for n in range(1, 6)] + [f'claw_{c}_L']
        pts = [P[n] for n in names] + [P[f'claw_tip_{c}_L']]
        add(names[0], 'pronotum' if c == 'f' else 'body', pts[0], pts[1] - pts[0], CAUDAL, 'coxa')
        add(names[1], names[0], pts[1], pts[2] - pts[1], DORSAL, 'trochanter')
        add(names[2], names[1], pts[2], pts[3] - pts[2], CAUDAL, 'femur')
        add(names[3], names[2], pts[3], pts[4] - pts[3], toward(pts[1], pts[3], pts[4] - pts[3]), 'tibia')
        for n in range(4, 10):
            add(names[n], names[n - 1], pts[n], pts[n + 1] - pts[n], VENTRAL, 'claw' if n == 9 else 'tarsus', 1,
                tip=pts[10] if n == 9 else None)
        mirror(names)
        iks.append((f'ik_foot_{c}_L', P[f'tarsus_1_{c}_L'], f'tibia_{c}_L'))
    # ---- IK targets (AG 05.19): under the root, on the ankles with the tibiae's frames (the femur and tibia solve a
    # two-bone IK to the ankle, the tarsus is laid on the ground from it: plan §6.4)
    for n, p, drv in iks:
        add(n, 'root', p, role='ik', tier=1, driver=drv, frame=frame(drv))
    mirror([n for n, _, _ in iks])
    return sk
