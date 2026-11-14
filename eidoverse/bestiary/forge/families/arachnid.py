"""ARACHNID family generator: the Mexican redknee tarantula first (work/bestiary/research/TARANTULA_PLAN.md §10, §11,
§13 step D4.1 with its CRITIC 11-10 and LEAD 11-10 marks). The recipe family stays `arthropod` with the body plan
`arachnid` (plan §5.1). families/arthropod.py's frame and mirror rules and families/decapod.py's vector helpers and
posing functions are IMPORTED here, never copied or edited.

D4.1 (11-10): the rest chain, the plan's 94-joint skeleton (§10.1) bound in the WALKING STANCE, the three poses
(crouch, threat, and the kick's REACH: two ends of a stroke, not yet a kick's look) as pose records, and the runtime's
tarsus step solver in Python (TarsusLeg.solve: locomotion.js makeSolvers.tarsus, line for line) so the walk and the
skitter are proven on the stick figure before any shell exists (the lead's F4 and F13 calls). The clay programs (D4.2)
and the cages (D4.4) come later. OPEN from D4.1 (plan §10.3's note): in the walk the femora of legs I and II pass 1.7
mm through each other as round bars; no solver-side change cures it; D4.2's clay settles it.

UNITS AND FRAME: LIFE MILLIMETRES (species/tarantula.py's SPEC) in the plan frame: the carapace's front edge on the
midline at z 0, +z forward, +y up from the GROUND, +x the creature's LEFT. skeleton(spec, chain) multiplies ONCE by SPEC
author_scale: rig.Skeleton in metres at x8.

THE BIND (rest_chain(spec)): every number is a SPEC row.
  - HEIGHTS (levels): the coxa joints rig.ride above the ground; the sternum's plane rig.coxa_h under them; the carapace's
    top body.height above that plane. The body joint on the midline at the coxa joints' mean z, rig.body_frac of the way
    up the prosoma; its bone runs to the carapace's front edge. The root on the ground under it.
  - A LEG (leg_points) is five straight runs, each with a plan azimuth and a slope:
      the COXA level, from its joint on the sternum's margin along c37's own azimuth (legs.coxae) to the knob (the
      coxa-trochanter joint);
      TROCHANTER + FEMUR straight, rising rig.femur_rise[pair] (each pair's two sides' mean on i01: legs I lie low,
      legs II and IV stand steep, so femora I and II, side by side in plan, are stacked and not in one sheet);
      PATELLA + TIBIA straight, falling s_pt;  the METATARSUS falling s_pt + rig.tm_bend;  the TARSUS flat: its joint
      rig.tarsus_h up (its half-thickness with the pad), its tip on the ground.
    s_pt closes the heights (stance): knob + femur's rise = tarsus_h + metatarsus's fall + (patella + tibia)'s fall.
    The three plan azimuths are solved so the KNEE, the TIBIA-METATARSUS JOINT and the TIP stand on i01's own
    directions seen from the coxa joint (rest.mid: each pair's two sides' mean, a symmetric stance between the
    photo's two sides; i01 is a standing or turning animal, not two phases of one walk). The leg's plane is
    therefore TILTED, as the photo shows it: the femur runs forward beside the carapace, the tibia turns out.
  - THE PALP (palp_points): the maxilla level along c37's azimuth; trochanter + femur rising rig.palp.femur_e in the
    vertical plane at rig.palp.az; patella + tibia falling by the angle that hovers the tarsus's tip rig.palp.tip_h up,
    the tarsus bent rig.palp.tarsus_bend further. Not a foot.
  - CHELICERA AND FANG: the chelicera's joint under the carapace's front (rig.chelicera), its bone to the fang's joint
    where c37 shows the fang's base (rig.fang.base); the fang folded back along c37's own run (rig.fang.back).
  - PEDICEL, OPISTHOSOMA, SPINNERETS: one short waist (rig.pedicel, rig.opisthosoma_z); the abdomen's bone to its rear
    pole at mid-height (its underside rig.abd_sag under the sternum's plane); the spinnerets under the rear pole,
    pointing back, pitched up and splayed (rig.spinneret).

skeleton(spec, chain): §10.1's 94 joints; parents before children; IK targets leaves of the root. Frames
(rig.frame_from): x along the bone to its child (or a leaf's tip), y the side it folds toward, so a positive turn
about z = x cross y folds the joint the anatomical way (AG 05.7):
  body                 ventral flexion (the front dips); pedicel, opisthosoma: the abdomen's rear dips (pitch + down)
  coxa                 remotion: the leg swings BACK about the body's up (z is up on a level coxa: the solver's yaw)
  trochanter           levation: the knee rises (the coxa-trochanter joint's lift: the solver's aim)
  femur                the trochanter-femur joint (+-10): the knee swings back
  patella              THE KNEE (femur-patella): closes. Its z is the tilted leg plane's normal: the solver's one hinge
  tibia                the patella-tibia joint (sideways, +-15): the distal leg swings back, about an axis in the leg's plane
  metatarsus, tarsus   curl ventrally (the beetle tarsus's convention: the solver's swing lift is a NEGATIVE turn)
  palp_*               as the leg's; chelicera: lifts; fang: opens (0 folded, 90 struck); spinnerets: curl ventrally
The right side is the left reflected under arthropod.py's written rule (AG 05.8): p_R = M p_L, F_R = M F_L diag(1, 1,
-1). sk.meta[name]: role, tier (0 body and legs, 1 tarsi, palps, spinnerets, IK, 2 chelicerae and fangs), side, fold,
tip, driver, parent.

THE SOLVER'S JOINT MAP (SPEC rig.ik): coxa = coxa_<n> (yaw) and femur = trochanter_<n> (lift) are the lead's F4 call;
tibia = patella_<n> (the knee's hinge) is the plan's; tarsus = tarsus_<n> is D4.1's finding on the stick figure
(tests/d4_01_skeleton.py prints both ways every run): the PLANTED joint is the metatarsus-tarsus joint, so the tarsus
lies flat as it rests and the knee is the one hinge between trochanter + femur and patella + tibia + metatarsus. The
plan's tarsus = metatarsus_<n> keeps a third of the leg rigid: it drove the tibia-metatarsus joint straight (178-179
deg included, its limit 175) in every gait and folded leg I's knee under its 40 deg in the skitter.
"""
import numpy as np
from scipy.optimize import brentq, least_squares, minimize

from .. import rig as RG
from .arthropod import DORSAL, VENTRAL, mirror_frame, mirror_point
from .decapod import _unit, angle, azimuth, heading, perp, posed, rotm, rz, tip_world  # noqa: F401  (re-exported)

UP = DORSAL
LEGS = ('I', 'II', 'III', 'IV')
NUM = {'I': 1, 'II': 2, 'III': 3, 'IV': 4}
SEGS = ('coxa', 'trochanter', 'femur', 'patella', 'tibia', 'metatarsus', 'tarsus')
PALP_SEGS = ('coxa', 'trochanter', 'femur', 'patella', 'tibia', 'tarsus')
LABELS = ('L1', 'R1', 'L2', 'R2', 'L3', 'R3', 'L4', 'R4')          # the gait's phase order (SPEC gait.phase)


def ry(deg):
    """a turn about the body's up (+ swings a left leg back: forward toward the left side)"""
    return rotm([0.0, 1.0, 0.0], deg)


def least_turn(a, b):
    """the least rotation carrying the unit vector a onto b (THREE.Quaternion.setFromUnitVectors)"""
    a, b = _unit(a), _unit(b)
    ax = np.cross(a, b)
    s, c = float(np.linalg.norm(ax)), float(a @ b)
    if s < 1e-14:
        return np.eye(3) if c > 0 else rotm(np.cross(a, [1.0, 0.0, 0.0] if abs(a[0]) < 0.9 else [0.0, 0.0, 1.0]), 180.0)
    return rotm(ax / s, np.degrees(np.arctan2(s, c)))


# --------------------------------------------------------------------------------------------- heights
def levels(spec):
    """the bind's heights and midline points, life mm: the coxa joints' height, the sternum's plane, the carapace's top
    and rim, the body joint, the carapace's front edge"""
    b, rg = spec['body'], spec['rig']
    y_cox = rg['ride']
    y_st = y_cox - rg['coxa_h']
    body_z = float(np.mean([spec['legs']['coxae'][R][1] for R in LEGS]))
    return dict(y_cox=y_cox, y_st=y_st, top=y_st + b['height'], rim=y_st + b['edge_h'], body_z=body_z,
                body=np.array([0.0, y_st + rg['body_frac'] * b['height'], body_z]),
                front=np.array([0.0, y_st + b['front_h'], 0.0]))


# --------------------------------------------------------------------------------------------- the legs
def leg_lengths(spec, R):
    """(coxa, trochanter, femur, patella, tibia, metatarsus, tarsus) of leg 'I'..'IV', life mm"""
    L = spec['legs'][R]
    return (L['coxa'], spec['legs']['trochanter'], L['femur'], L['patella'], L['tibia'], L['metatarsus'], L['tarsus'])


def stance(spec, R, lv):
    """the bind's slopes of one leg (deg): e the femur's rise, s_pt the patella + tibia's fall, s_mt the metatarsus's,
    s_ta the tarsus's, and the joints' heights (module docstring: the height closure)"""
    rg = spec['rig']
    _, Ltr, Lfe, Lpa, Lti, Lmt, Lta = leg_lengths(spec, R)
    e, bend, h = rg['femur_rise'][R], rg['tm_bend'], rg['tarsus_h']
    Ky = lv['y_cox'] + (Ltr + Lfe) * np.sin(np.radians(e))
    s_pt = brentq(lambda s: h + Lmt * np.sin(np.radians(s + bend)) + (Lpa + Lti) * np.sin(np.radians(s)) - Ky,
                  0.0, 75.0, xtol=1e-13)
    return dict(e=float(e), s_pt=float(s_pt), s_mt=float(s_pt + bend), s_ta=float(np.degrees(np.arcsin(h / Lta))),
                knee_h=float(Ky), tm_h=float(Ky - (Lpa + Lti) * np.sin(np.radians(s_pt))))


def _on_ray(C, az, O, r):
    """the far point of the plan circle (centre O, radius r) on the plan ray from C at azimuth az; points are (x, z)"""
    d = np.array([np.sin(np.radians(az)), np.cos(np.radians(az))])
    w = np.asarray(O, np.float64) - np.asarray(C, np.float64)
    b = float(d @ w)
    disc = b * b - float(w @ w) + r * r
    assert disc >= 0.0, f'the ray at {az:.1f} deg misses the circle (radius {r:.2f}) by {np.sqrt(-disc):.2f} mm'
    return np.asarray(C, np.float64) + (b + np.sqrt(disc)) * d


def leg_points(spec, R, lv):
    """one LEFT leg at the bind (module docstring): the joints C (body-coxa), T (coxa-trochanter: the knob), F
    (trochanter-femur), K (femur-patella: the knee), PT (patella-tibia), TM (tibia-metatarsus), MT (metatarsus-tarsus),
    the tarsus's tip; the bone directions hc, uf, ut, um, uta; the plan azimuths phi = (femur, tibia, foot); stance()'s
    slopes"""
    Lc, Ltr, Lfe, Lpa, Lti, Lmt, Lta = leg_lengths(spec, R)
    cx, mid = spec['legs']['coxae'][R], spec['rest']['mid'][R]
    st = stance(spec, R, lv)
    cr = lambda a: np.cos(np.radians(a))                                  # noqa: E731
    C = np.array([cx[0], lv['y_cox'], cx[1]])
    hc = heading(cx[2])
    T = C + Lc * hc
    pl = lambda p: np.array([p[0], p[2]])                                 # noqa: E731
    Kp = _on_ray(pl(C), mid[0], pl(T), (Ltr + Lfe) * cr(st['e']))
    phi_f = float(np.degrees(np.arctan2(Kp[0] - T[0], Kp[1] - T[2])))
    uf = heading(phi_f, st['e'])
    F, K = T + Ltr * uf, T + (Ltr + Lfe) * uf
    TMp = _on_ray(pl(C), mid[1], pl(K), (Lpa + Lti) * cr(st['s_pt']))
    phi_t = float(np.degrees(np.arctan2(TMp[0] - K[0], TMp[1] - K[2])))
    ut = heading(phi_t, -st['s_pt'])
    PT, TM = K + Lpa * ut, K + (Lpa + Lti) * ut
    tp = _on_ray(pl(C), mid[2], pl(TM), Lmt * cr(st['s_mt']) + Lta * cr(st['s_ta']))
    phi_m = float(np.degrees(np.arctan2(tp[0] - TM[0], tp[1] - TM[2])))
    um, uta = heading(phi_m, -st['s_mt']), heading(phi_m, -st['s_ta'])
    MT = TM + Lmt * um
    return dict(C=C, T=T, F=F, K=K, PT=PT, TM=TM, MT=MT, tip=MT + Lta * uta, hc=hc, uf=uf, ut=ut, um=um, uta=uta,
                phi=(phi_f, phi_t, phi_m), knee=180.0 - angle(uf, ut), tm=180.0 - angle(ut, um),
                swing=float(cx[2] - phi_f), **st)


def palp_points(spec, lv):
    """the LEFT palp at the bind (module docstring): C, T, F, K, PT, TA (tibia-tarsus), the tip; the bone directions"""
    p, rp = spec['palp'], spec['rig']['palp']
    Lc, Ltr, Lfe, Lpa, Lti, Lta = (p[k] for k in PALP_SEGS)
    C = np.array([p['coxae'][0], lv['y_st'] + rp['coxa_h'], p['coxae'][1]])
    hc = heading(p['coxae'][2])
    T = C + Lc * hc
    uf = heading(rp['az'], rp['femur_e'])
    F, K = T + Ltr * uf, T + (Ltr + Lfe) * uf
    sn = lambda a: np.sin(np.radians(a))                                  # noqa: E731
    s = brentq(lambda v: K[1] - (Lpa + Lti) * sn(v) - Lta * sn(v + rp['tarsus_bend']) - rp['tip_h'], 0.0, 80.0,
               xtol=1e-13)
    ut, uta = heading(rp['az'], -s), heading(rp['az'], -(s + rp['tarsus_bend']))
    PT, TA = K + Lpa * ut, K + (Lpa + Lti) * ut
    return dict(C=C, T=T, F=F, K=K, PT=PT, TA=TA, tip=TA + Lta * uta, hc=hc, uf=uf, ut=ut, uta=uta,
                e=float(rp['femur_e']), s_pt=float(s), knee=180.0 - angle(uf, ut))


# --------------------------------------------------------------------------------------------- face, waist, abdomen
def chelicera_points(spec, lv):
    """the LEFT chelicera's joint J, the fang's joint B (the chelicera's bone ends there) and the folded fang's tip"""
    rc, rf = spec['rig']['chelicera'], spec['rig']['fang']
    J = np.array([rc['x'], lv['y_st'] + rc['up'], rc['z']])
    B = np.array([rf['base_xz'][0], lv['y_st'] + rf['base_h'], rf['base_xz'][1]])
    return dict(J=J, B=B, tip=B + np.array([rf['back_xz'][0], rf['back_h'], rf['back_xz'][1]]))


def abdomen_points(spec, lv):
    """the pedicel's and the opisthosoma's joints, the abdomen's centre, rear pole and half-axes (x, y, z), and the LEFT
    spinnerets' joints and tips"""
    b, rg = spec['body'], spec['rig']
    ped = np.array([0.0, lv['y_st'] + rg['pedicel'][1], rg['pedicel'][0]])
    op = np.array([0.0, ped[1], rg['opisthosoma_z']])
    half = np.array([0.5 * b['abd_W'], 0.5 * b['abd_H'], 0.5 * b['abd_len']])
    cy = lv['y_st'] - rg['abd_sag'] + half[1]
    z_rear = b['abd_front_z'] - b['abd_len']
    out = dict(pedicel=ped, opisthosoma=op, abd_c=np.array([0.0, cy, b['abd_front_z'] - half[2]]),
               abd_rear=np.array([0.0, cy, z_rear]), abd_half=half)
    sp = rg['spinneret']
    u = heading(180.0 - sp['splay'], sp['pitch'])
    p = np.array([sp['pls'][0], lv['y_st'] + sp['pls'][1], z_rear + sp['pls'][2]])
    for k, L in enumerate(spec['spinnerets']['PLS']):
        out[f'spinneret_pl_{k}_L'] = p
        p = p + L * u
    out['spinneret_pl_tip_L'] = p
    q = np.array([sp['pms'][0], lv['y_st'] + sp['pms'][1], z_rear + sp['pms'][2]])
    out['spinneret_pm_L'], out['spinneret_pm_tip_L'] = q, q + spec['spinnerets']['PMS'] * u
    return out


def abdomen_top(spec, chain, along, across=0.0):
    """a point on the abdomen's dorsal surface at the bind: `along` its length from the front, `across` its half-width
    from the midline (the kick's patch, SPEC rig.kick.patch), and the surface's outward normal there; life mm"""
    P = chain['pos']
    c, h = P['abd_c'], P['abd_half']
    z = spec['body']['abd_front_z'] - along * spec['body']['abd_len']
    wz = np.sqrt(max(0.0, 1.0 - ((z - c[2]) / h[2]) ** 2))
    x = across * h[0] * wz
    y = c[1] + h[1] * np.sqrt(max(0.0, 1.0 - (x / h[0]) ** 2 - ((z - c[2]) / h[2]) ** 2))
    p = np.array([x, y, z])
    return p, _unit((p - c) / h ** 2)


# --------------------------------------------------------------------------------------------- the rest chain
def rest_chain(spec):
    """the bind's points in life mm (module docstring): dict(pos={name: (3,)}, legs={'I'..: leg_points' dict},
    palp=palp_points' dict, chel=chelicera_points' dict, lv=levels(), scale_m (metres per life mm at the author scale))"""
    lv = levels(spec)
    P = {'root': np.array([0.0, 0.0, lv['body_z']]), 'body': lv['body'], 'front': lv['front']}
    ab = abdomen_points(spec, lv)
    P.update(ab)
    ch = chelicera_points(spec, lv)
    P['chelicera_L'], P['fang_L'], P['fang_tip_L'] = ch['J'], ch['B'], ch['tip']
    pp = palp_points(spec, lv)
    for seg, key in zip(PALP_SEGS, ('C', 'T', 'F', 'K', 'PT', 'TA')):
        P[f'palp_{seg}_L'] = pp[key]
    P['palp_tip_L'] = pp['tip']
    legs = {}
    for R in LEGS:
        g = leg_points(spec, R, lv)
        legs[R] = g
        for seg, key in zip(SEGS, ('C', 'T', 'F', 'K', 'PT', 'TM', 'MT')):
            P[f'{seg}_{NUM[R]}_L'] = g[key]
        P[f'tarsus_tip_{NUM[R]}_L'] = g['tip']
    for k in [k for k in P if k.endswith('_L')]:
        P[k[:-2] + '_R'] = mirror_point(P[k])
    return dict(pos=P, legs=legs, palp=pp, chel=ch, lv=lv, scale_m=spec['author_scale'] * 1e-3)


# --------------------------------------------------------------------------------------------- the skeleton
def skeleton(spec, chain, scale=None):
    """§10.1's 94 joints as rig.Skeleton in metres at the author scale (module docstring); sk.meta holds each joint's
    role, tier, side, fold, tip (metres), driver and parent"""
    s = chain['scale_m'] if scale is None else scale
    P, legs, pp = chain['pos'], chain['legs'], chain['palp']
    sk = RG.Skeleton()
    sk.meta = {}

    def add(name, parent, pos, x=None, fold=None, role='', tier=0, tip=None, driver=None, frame=None):
        if frame is None:
            frame = RG.frame_from(x, fold)
        sk.add(name, parent, np.asarray(pos, np.float64) * s, frame)
        side = 'L' if name.endswith('_L') else ('R' if name.endswith('_R') else '')
        sk.meta[name] = dict(role=role, tier=tier, side=side, parent=parent, driver=driver,
                             fold=None if fold is None else np.asarray(fold, np.float64),
                             tip=None if tip is None else np.asarray(tip, np.float64) * s)

    sw = lambda n: n[:-2] + '_R' if (n and n.endswith('_L')) else n          # noqa: E731

    def mirror(names):
        for n in names:
            m = sk.meta[n]
            W = sk.world[sk.index(n)]
            add(sw(n), sw(m['parent']), mirror_point(W[:3, 3]) / s, role=m['role'], tier=m['tier'],
                driver=sw(m['driver']), fold=None if m['fold'] is None else mirror_point(m['fold']),
                tip=None if m['tip'] is None else mirror_point(m['tip']) / s, frame=mirror_frame(W[:3, :3]))

    def toward(p, j, x):
        return perp(np.asarray(p, np.float64) - np.asarray(j, np.float64), _unit(x))

    def sideways(prev, K, ut):
        """the patella-tibia joint's fold: the knee's hinge axis, on the side that swings the distal leg back"""
        nk = _unit(np.cross(_unit(ut), toward(prev, K, ut)))
        return nk if float(nk @ np.cross(UP, ut)) >= 0.0 else -nk

    # ---- root, body, pedicel, opisthosoma, spinnerets
    add('root', None, P['root'], role='root', frame=np.eye(3))
    add('body', 'root', P['body'], P['front'] - P['body'], VENTRAL, 'body', tip=P['front'])
    add('pedicel', 'body', P['pedicel'], P['opisthosoma'] - P['pedicel'], VENTRAL, 'pedicel')
    add('opisthosoma', 'pedicel', P['opisthosoma'], P['abd_rear'] - P['opisthosoma'], VENTRAL, 'opisthosoma',
        tip=P['abd_rear'])
    pls = [f'spinneret_pl_{k}_L' for k in range(3)]
    for k, n in enumerate(pls):
        nxt = P[pls[k + 1]] if k < 2 else P['spinneret_pl_tip_L']
        x = nxt - P[n]
        add(n, 'opisthosoma' if k == 0 else pls[k - 1], P[n], x, perp(VENTRAL, _unit(x)), 'spinneret', 1,
            tip=P['spinneret_pl_tip_L'] if k == 2 else None)
    x = P['spinneret_pm_tip_L'] - P['spinneret_pm_L']
    add('spinneret_pm_L', 'opisthosoma', P['spinneret_pm_L'], x, perp(VENTRAL, _unit(x)), 'spinneret', 1,
        tip=P['spinneret_pm_tip_L'])
    mirror(pls + ['spinneret_pm_L'])
    # ---- chelicerae and fangs
    x = P['fang_L'] - P['chelicera_L']
    add('chelicera_L', 'body', P['chelicera_L'], x, perp(DORSAL, _unit(x)), 'chelicera', 2)
    x = P['fang_tip_L'] - P['fang_L']
    add('fang_L', 'chelicera_L', P['fang_L'], x, perp(VENTRAL, _unit(x)), 'fang', 2, tip=P['fang_tip_L'])
    mirror(['chelicera_L', 'fang_L'])
    # ---- palps
    nm = [f'palp_{seg}_L' for seg in PALP_SEGS]
    add(nm[0], 'body', pp['C'], pp['hc'], np.cross(UP, pp['hc']), 'palp', 1)
    add(nm[1], nm[0], pp['T'], pp['uf'], perp(DORSAL, pp['uf']), 'palp', 1)
    add(nm[2], nm[1], pp['F'], pp['uf'], np.cross(UP, pp['uf']), 'palp', 1)
    add(nm[3], nm[2], pp['K'], pp['ut'], toward(pp['T'], pp['K'], pp['ut']), 'palp', 1)
    add(nm[4], nm[3], pp['PT'], pp['ut'], sideways(pp['T'], pp['K'], pp['ut']), 'palp', 1)
    add(nm[5], nm[4], pp['TA'], pp['uta'], perp(VENTRAL, pp['uta']), 'palp', 1, tip=pp['tip'])
    mirror(nm)
    # ---- the eight legs
    for R in LEGS:
        g = legs[R]
        nm = [f'{seg}_{NUM[R]}_L' for seg in SEGS]
        add(nm[0], 'body', g['C'], g['hc'], np.cross(UP, g['hc']), 'coxa')
        add(nm[1], nm[0], g['T'], g['uf'], perp(DORSAL, g['uf']), 'trochanter')
        add(nm[2], nm[1], g['F'], g['uf'], np.cross(UP, g['uf']), 'femur')
        add(nm[3], nm[2], g['K'], g['ut'], toward(g['T'], g['K'], g['ut']), 'patella')
        add(nm[4], nm[3], g['PT'], g['ut'], sideways(g['T'], g['K'], g['ut']), 'tibia')
        add(nm[5], nm[4], g['TM'], g['um'], perp(VENTRAL, g['um']), 'metatarsus')
        add(nm[6], nm[5], g['MT'], g['uta'], perp(VENTRAL, g['uta']), 'tarsus', 1, tip=g['tip'])
        mirror(nm)
    # ---- IK targets (AG 05.19): leaves of the root on the solver's PLANTED joint (SPEC rig.ik.tarsus) with the frame of
    # the segment that ends there; the palp's on its tibia-tarsus joint
    k = SEGS.index(spec['rig']['ik']['tarsus'])
    key = ('C', 'T', 'F', 'K', 'PT', 'TM', 'MT')[k]
    iks = [(f'ik_foot_{NUM[R]}_L', legs[R][key], f'{SEGS[k - 1]}_{NUM[R]}_L') for R in LEGS]
    iks.append(('ik_palp_L', pp['TA'], 'palp_tibia_L'))
    for n, p, drv in iks:
        add(n, 'root', p, role='ik', tier=1, driver=drv, frame=sk.world[sk.index(drv)][:3, :3])
    mirror([n for n, _, _ in iks])
    return sk


def plan_table():
    """§10.1's joint names, in the plan's rows: {row: [names]}"""
    sides = ('L', 'R')
    return {
        'root, body, pedicel, opisthosoma': ['root', 'body', 'pedicel', 'opisthosoma'],
        'legs': [f'{seg}_{n}_{sd}' for n in (1, 2, 3, 4) for sd in sides for seg in SEGS],
        'palps': [f'palp_{seg}_{sd}' for sd in sides for seg in PALP_SEGS],
        'chelicerae and fangs': [f'{j}_{sd}' for sd in sides for j in ('chelicera', 'fang')],
        'spinnerets': [f'spinneret_pl_{k}_{sd}' for sd in sides for k in range(3)] + [f'spinneret_pm_{sd}' for sd in sides],
        'ik': [f'ik_foot_{n}_{sd}' for n in (1, 2, 3, 4) for sd in sides] + [f'ik_palp_{sd}' for sd in sides],
    }


# --------------------------------------------------------------------------------------------- the bind's angles
def bind_angles(spec, chain):
    """every articulated joint class's bind angle against its SPEC range: a list of dict(joint, value, range, how); the
    LEFT side (the right mirrors it)"""
    R_ = spec['rig']['ranges']
    out = []
    for R in LEGS:
        g, n = chain['legs'][R], NUM[R]
        out += [dict(joint=f'coxa_{n}', value=0.0, range=R_['coxa'], how='yaw from c37\'s own azimuth (the bind\'s zero)'),
                dict(joint=f'trochanter_{n} (lift)', value=g['e'], range=R_['trochanter'],
                     how='the femur\'s rise above the level coxa'),
                dict(joint=f'trochanter_{n} (swing)', value=g['swing'], range=R_['trochanter_swing'],
                     how='the femur forward of the coxa\'s axis, in plan'),
                dict(joint=f'femur_{n}', value=0.0, range=R_['femur'], how='straight (the bind\'s zero)'),
                dict(joint=f'patella_{n}', value=g['knee'], range=R_['patella'], how='the knee\'s included angle'),
                dict(joint=f'tibia_{n}', value=0.0, range=R_['tibia'], how='straight (the bind\'s zero)'),
                dict(joint=f'metatarsus_{n}', value=g['tm'], range=R_['metatarsus'],
                     how='the tibia-metatarsus included angle'),
                dict(joint=f'tarsus_{n}', value=-(g['s_mt'] - g['s_ta']), range=R_['tarsus'],
                     how='from the metatarsus\'s line (+ curls ventrally): lifted so the tarsus lies flat')]
    pp = chain['palp']
    out += [dict(joint='palp_trochanter (lift)', value=pp['e'], range=R_['trochanter'], how='the femur\'s rise'),
            dict(joint='palp_patella', value=pp['knee'], range=R_['patella'], how='the knee\'s included angle'),
            dict(joint='chelicera (lift)', value=0.0, range=R_['chelicera_lift'], how='the bind\'s zero'),
            dict(joint='fang', value=spec['rig']['fang']['rest'], range=R_['fang'], how='folded, a little open'),
            dict(joint='pedicel (pitch)', value=0.0, range=R_['pedicel_pitch'], how='level (the bind\'s zero)'),
            dict(joint='spinnerets', value=0.0, range=R_['spinneret'], how='straight')]
    return out


# --------------------------------------------------------------------------------------------- THE TARSUS STEP SOLVER
def foot_path(N, ph, duty, stride, lift, center, stride0=None):
    """the scheduler's foot target (locomotion.js gaitScheduler.footAt) in the ROOT's frame, for a straight walk at a
    constant speed: N the foot's rest place, ph its phase in [0, 1), stride the body's travel a cycle. In stance the
    foot stands still on the ground, so in the body's frame it runs back from stride x duty x center ahead of N; in
    swing it travels plant to plant on the scheduler's ease (it rises before it moves) and lifts sin^2. Returns
    (foot (3,), up in 0..1)"""
    stride0 = stride if stride0 is None else stride0
    if ph < duty:
        dz, up = stride * (duty * center - ph), 0.0
    else:
        s = (ph - duty) / (1.0 - duty)
        sh = min(1.0, max(0.0, (s - 0.1) / 0.9))
        e = sh * sh * (3.0 - 2.0 * sh)
        dz = stride * (duty * center - ph + e)
        up = np.sin(np.pi * s) ** 2 * min(1.0, stride / (0.35 * stride0))
    return np.asarray(N, np.float64) + np.array([0.0, lift * up, dz]), float(up)


H2_TOL = 1e-12               # rad: a rule's root-find stops when its bracket is this narrow (the staged runtime patch has
                             # the same). D4.1b fix (11-11): the ITP root-find (toward) replaced 40 halvings, which placed
                             # the hinge to about the same (d41b_NOTES E2)
H2_N0 = 1                    # ITP's slack: a rule never takes more than H2_N0 steps past what plain halving would take
H2_SOFT = np.radians(2.0)    # each rule engages over this much of its measure past the edge (smoothstep): a rule whose
                             # edge the hinge cannot reach ramps to its limit instead of jumping there in one sample
                             # (d41b_NOTES D3b: leg II's femur under its band near full reach, dm 0 -> -9 deg at once)


def _soft(v):
    """0 at or inside an edge, 1 from H2_SOFT past it, smoothstep between (v rad past the edge)"""
    x = min(1.0, max(0.0, v / H2_SOFT))
    return x * x * (3.0 - 2.0 * x)


def _about(axis, ang, v):
    """v turned ang (rad) about the unit axis (Rodrigues)"""
    c, s = np.cos(ang), np.sin(ang)
    return v * c + np.cross(axis, v) * s + axis * float(axis @ v) * (1.0 - c)


class TarsusLeg:
    """one leg slot of the runtime's TARSUS step solver, on the bound skeleton, in the ROOT's frame (the body rigid on
    the root): locomotion.js tarsusFrames + makeSolvers.tarsus ported line for line (the runtime is the authority;
    this is the forge's instrument). The slot's four joints are SPEC rig.ik's (the lead's F4 map). Lengths in the
    skeleton's units (metres at the author scale), so the solver's own 1e-5 clamps mean what they mean in the glb.

    D4.1b (11-11, the lead's call): A SECOND HINGE, opt-in. When the joint map names one (SPEC rig.ik.hinge2: the
    tibia-metatarsus joint) the leg is solved by solve2 below (the staged runtime patch's tarsus2, the same steps in
    the same order): the far leg can shorten and lengthen at that hinge, and its one free turn keeps (1) the femur's
    elevation inside its band and (2) the knee inside its range (SPEC rig.hinge2). hinge2=False forces the runtime's
    one-hinge solver whatever the SPEC says (the pose records are made with it and stay as they were).

    D4.1b FIX (11-11, the check's F1): N is the foot's WALK place (walk_cycle moves it by SPEC gait.place), N0 its REST
    place (the bind's). solve(..., walk) takes the PLANT's walk weight (the staged runtime's L.w: 1 on a plant made while
    the body moves, 0 on one made standing or on the settling step after a stop, between them through the swing from one
    to the other): the coxa's yaw is measured from the place the foot stands on (ref) and the second hinge's rules are
    scaled by it, so a STANDING leg (walk 0, its foot on N0) is the bind exactly."""

    def __init__(self, spec, sk, label, coxa_range=None, ik=None, hinge2=None):
        side, n = label[0], label[1]
        ik = spec['rig']['ik'] if ik is None else ik
        self.label, self.names = label, [f'{seg}_{n}_{side}' for seg in SEGS]
        self.c, self.f, self.t, self.a = (SEGS.index(ik[k]) for k in ('coxa', 'femur', 'tibia', 'tarsus'))
        W = [sk.world[sk.index(nm)] for nm in self.names]
        root = sk.world[sk.index('root')][:3, 3]
        self.R0 = [w[:3, :3].copy() for w in W]
        self.p0 = [w[:3, 3] - root for w in W]                       # the root's frame (its rest rotation is I)
        self.lt = [None] + [self.R0[k - 1].T @ (self.p0[k] - self.p0[k - 1]) for k in range(1, 7)]
        self.lR = [None] + [self.R0[k - 1].T @ self.R0[k] for k in range(1, 7)]
        self.tip0 = sk.meta[self.names[6]]['tip'] - root
        self.ltip = self.R0[6].T @ (self.tip0 - self.p0[6])
        self.Lf = float(np.linalg.norm(self.p0[self.f] - self.p0[self.t]))
        self.Lt = float(np.linalg.norm(self.p0[self.t] - self.p0[self.a]))
        self.N, self.cR, self.qTar = self.p0[self.a].copy(), self.p0[self.c].copy(), self.R0[self.a].copy()
        self.N0 = self.N.copy()                                      # the rest place (walk_cycle moves N to the walk's)
        self.range = np.radians(spec['gait']['coxa_range'] if coxa_range is None else coxa_range)
        # ---- the second hinge's rest data (D4.1b), every vector in the femur slot's or the tibia slot's own frame
        self.h2 = None
        h2 = ik.get('hinge2') if hinge2 is None else (ik.get('hinge2') if hinge2 is True else hinge2)
        if h2:
            row = spec['rig']['hinge2']
            f, t, a, m = self.f, self.t, self.a, SEGS.index(h2)
            RF, RT, RM = self.R0[f], self.R0[t], self.R0[m]
            self.m = m
            self.kF = RF.T @ (self.p0[t] - self.p0[f])               # the knee from the knob, the femur slot's frame
            self.RFT = RF.T @ RT                                     # the tibia slot's rest rotation in it
            self.kT = RT.T @ (self.p0[t] - self.p0[f])               # the knee from the knob, the tibia slot's frame
            self.mT = RT.T @ (self.p0[m] - self.p0[t])               # the second hinge's joint from the knee
            self.zM = (RT.T @ RM)[:, 2].copy()                       # the second hinge's axis, the tibia slot's frame
            self.aT = RT.T @ (self.p0[a] - self.p0[m])               # the ankle from the second hinge's joint
            self.lk, self.lm = float(np.linalg.norm(self.kF)), float(np.linalg.norm(self.mT))
            # the hinge's own included angle at rest, and its turn limits (a + turn closes it): the walk's range
            tm0 = angle(self.p0[m - 1] - self.p0[m], self.p0[m + 1] - self.p0[m])
            pair = LEGS[int(n) - 1]
            band = row['band'][pair]
            # range (the hinge's included angle) and knee: one (lo, hi) for every pair, or {pair: (lo, hi)} (D4.1b: each
            # pair's own walking range from L7)
            rng = row['range'][pair] if isinstance(row['range'], dict) else row['range']
            kne = row['knee'][pair] if isinstance(row['knee'], dict) else row['knee']
            self.h2 = dict(joint=h2, band=(np.radians(band[0]), np.radians(band[1])),
                           turn=(np.radians(tm0 - rng[1]), np.radians(tm0 - rng[0])),
                           knee=(np.radians(kne[0]), np.radians(kne[1])), rest=float(tm0))

    def chain(self, Rc, pc, dl=0.0, Q=None, Ra=None):
        """the joints' rotations and places with the coxa slot at (Rc, pc), the knee turned dl (rad) about its own z,
        the femur slot aimed by the world turn Q, the tarsus slot's rotation set to Ra"""
        R, p = [None] * 7, [None] * 7
        R[self.c], p[self.c] = Rc, pc
        for k in range(self.c + 1, 7):
            p[k] = p[k - 1] + R[k - 1] @ self.lt[k]
            R[k] = R[k - 1] @ self.lR[k]
            if k == self.f and Q is not None:
                R[k] = Q @ R[k]
            if k == self.t and dl:
                R[k] = R[k] @ rotm([0.0, 0.0, 1.0], np.degrees(dl))
            if k == self.a and Ra is not None:
                R[k] = Ra
        return R, p

    def ref(self, walk=1.0):
        """the place the coxa's yaw is measured from: the walk's stance place N on a walking plant (walk 1), the rest
        place N0 on a standing one (walk 0), between them through a step from one to the other (the staged runtime's
        refN: L.Nw, L.N, L.w; d41b fix F1)"""
        if walk == 1.0:
            return self.N
        if walk == 0.0:
            return self.N0
        return self.N0 + walk * (self.N - self.N0)

    def solve(self, foot, up=0.0, dth=0.0, B=None, yaw=None, walk=1.0):
        """locomotion.js tarsus(L, foot, th, up, body): foot the planted joint's target in the root's frame; up the
        swing's lift 0..1; dth the foot's heading less the body's; walk the plant's walk weight (the runtime's L.w: 1
        walking, 0 standing; the class's note). B = (R, t), a rigid move of the BODY from its bind place (the poses: a
        crouch, a rear), and yaw (deg) a forced coxa yaw (the poses pass 0), are this port's own extensions; the walk
        passes neither. Returns dict(yaw deg, err, knee deg, R, p, tip, d, dmin, dmax, rot)"""
        if self.h2 is not None:
            return self.solve2(foot, up, dth, B, yaw, walk)
        c, f, t, a = self.c, self.f, self.t, self.a
        BR, Bt = (np.eye(3), np.zeros(3)) if B is None else B
        foot = np.asarray(foot, np.float64)
        if yaw is None:
            Nr = self.ref(walk)
            a0 = np.arctan2(Nr[0] - self.cR[0], Nr[2] - self.cR[2])
            a1 = np.arctan2(foot[0] - self.cR[0], foot[2] - self.cR[2])
            y = a1 - a0
            y = np.arctan2(np.sin(y), np.cos(y))
            y = max(-self.range, min(self.range, y))
        else:
            y = np.radians(yaw)
        Rc, pc = BR @ ry(np.degrees(y)) @ self.R0[c], BR @ self.p0[c] + Bt
        R, p = self.chain(Rc, pc)
        F = p[f]
        to_foot = foot - F
        dmin, dmax = abs(self.Lf - self.Lt) + 1e-5, self.Lf + self.Lt - 1e-5
        d_raw = float(np.linalg.norm(to_foot))
        d = max(dmin, min(dmax, d_raw))
        want = np.arccos(max(-1.0, min(1.0, (self.Lf ** 2 + self.Lt ** 2 - d * d) / (2.0 * self.Lf * self.Lt))))

        def incl(dl):
            _, q = self.chain(Rc, pc, dl)
            return np.radians(angle(F - q[t], q[a] - q[t]))
        x0, f0, x1 = 0.0, incl(0.0) - want, -0.05
        f1 = incl(x1) - want
        it = 0
        while it < 10 and abs(f1) > 1e-7 and abs(f1 - f0) > 1e-12:
            x2 = x1 - f1 * (x1 - x0) / (f1 - f0)
            x0, f0, x1 = x1, f1, x2
            f1 = incl(x1) - want
            it += 1
        R, p = self.chain(Rc, pc, x1)
        Q = least_turn(p[a] - F, to_foot)
        # the tarsus slot: its rest lie in the root's frame, turned with the foot's heading, its tip lifted through the
        # swing (a planted foot under a moved body keeps that lie on the ground: B does not enter)
        Ra = ry(np.degrees(dth)) @ self.qTar
        if up > 0:
            Ra = Ra @ rotm([0.0, 0.0, 1.0], np.degrees(-0.45 * up))
        Rn, pn = self.chain(Rc, pc, x1, Q)
        err = float(np.linalg.norm(pn[a] - foot))
        knee = angle(F - pn[t], pn[a] - pn[t])
        R, p = self.chain(Rc, pc, x1, Q, Ra)
        rot = {self.names[k]: self.lR[k].T @ R[k - 1].T @ R[k] for k in range(c + 1, 7)}
        rot[self.names[c]] = self.R0[c].T @ BR.T @ Rc
        return dict(yaw=float(np.degrees(y)), err=err, knee=float(knee), R=R, p=p, tip=p[6] + R[6] @ self.ltip,
                    d=d_raw, dmin=dmin, dmax=dmax, rot=rot, iters=it)

    # ------------------------------------------------------------------------------------- THE TWO-HINGE SOLVE (D4.1b)
    def far(self, dm):
        """the far leg with the second hinge turned dm (rad): the ankle in the tibia slot's frame, and the reach's law
        |knob to ankle|^2 = C + rho cos(dl - phi) in the knee's turn dl"""
        AT = self.mT + _about(self.zM, dm, self.aT)
        k = self.kT
        C = float(k @ k + AT @ AT + 2.0 * k[2] * AT[2])
        P = 2.0 * (k[0] * AT[0] + k[1] * AT[1])
        S = 2.0 * (k[1] * AT[0] - k[0] * AT[1])
        return AT, C, float(np.hypot(P, S)), float(np.arctan2(S, P))

    def pose2(self, dm, d_raw, kFw, RFTw, u_foot, aim=True):
        """the leg for one turn dm of the second hinge, in closed form: (the knee's turn dl, the femur slot's aim Q, the
        femur's elevation rad, the knee's included angle rad, the reach's margin dmax - d_raw: the foot is in reach when
        it is >= 0). kFw = RFw kF and RFTw = RFw RFT, the femur slot's world turn applied once a solve. aim=False leaves
        out the aim and the elevation (Q and e None): rule 2 reads only the knee and the reach. The reach is clamped to
        what the hinge can give (sqrt(C -+ rho)), 1e-5 inside; dl is on the rest's branch"""
        AT, C, rho, phi = self.far(dm)
        dmin, dmax = np.sqrt(max(0.0, C - rho)) + 1e-5, np.sqrt(C + rho) - 1e-5
        d = max(dmin, min(dmax, d_raw))
        dl = phi - (1.0 if phi >= 0.0 else -1.0) * np.arccos(max(-1.0, min(1.0, (d * d - C) / rho)))
        c, s = np.cos(dl), np.sin(dl)
        knee = float(np.arccos(max(-1.0, min(1.0, -float(self.kT[0] * (self.mT[0] * c - self.mT[1] * s)
                                                          + self.kT[1] * (self.mT[0] * s + self.mT[1] * c)
                                                          + self.kT[2] * self.mT[2]) / (self.lk * self.lm)))))
        if not aim:
            return dl, None, None, knee, dmax - d_raw
        A2 = np.array([AT[0] * c - AT[1] * s, AT[0] * s + AT[1] * c, AT[2]])
        Q = least_turn(kFw + RFTw @ A2, u_foot)
        e = float(np.arcsin(max(-1.0, min(1.0, float((Q @ kFw)[1]) / self.lk))))
        return dl, Q, e, knee, dmax - d_raw

    @staticmethod
    def toward(f, x_from, f_from, x_to):
        """the turn nearest x_from, between x_from (where the rule fails: f_from = f(x_from) < 0) and x_to, at which it
        holds (f >= 0); x_to itself when it fails there too (the hinge goes as far as it can). D4.1b fix (11-11): the
        ITP root-find of f along the bracket (Oliveira & Takahashi 2020, ACM TOMS 47(1) 5: the regula falsi point,
        truncated toward the middle by 0.2 w^2, projected into what halving would keep), stopped when the bracket is
        H2_TOL wide, the good end returned. It never takes more steps than halving would + H2_N0, and far fewer on
        these smooth rules; the 40 halvings it replaced cost 41 poses a rule (d41b_NOTES E2). Bracket in t: x =
        x_from + t (x_to - x_from), t in [0, 1]"""
        f_to = f(x_to)
        if f_to < 0.0:
            return x_to
        span = x_to - x_from
        eps = 0.5 * H2_TOL / abs(span)
        n_max = int(np.ceil(np.log2(1.0 / (2.0 * eps)))) + H2_N0
        a, fa, b, fb, j = 0.0, f_from, 1.0, f_to, 0
        while b - a > 2.0 * eps and fb != 0.0:
            xh = 0.5 * (a + b)
            r = eps * 2.0 ** (n_max - j) - 0.5 * (b - a)
            delta = 0.2 * (b - a) * (b - a)
            xf = (fb * a - fa * b) / (fb - fa)
            sg = 1.0 if xh >= xf else -1.0
            xt = xf + sg * delta if delta <= abs(xh - xf) else xh
            x = xt if abs(xt - xh) <= r else xh - sg * r
            y = f(x_from + x * span)
            if y >= 0.0:
                b, fb = x, y
            else:
                a, fa = x, y
            j += 1
        return x_from + b * span

    def solve2(self, foot, up=0.0, dth=0.0, B=None, yaw=None, walk=1.0):
        """the tarsus solve with the second hinge (the staged patch's makeSolvers.tarsus2, step for step). The coxa
        yaws as before (from the place its foot stands on: ref(walk)). Then the second hinge's turn dm is chosen, from 0
        (the one-hinge solution), by two rules:
          1. the femur's elevation (the knob-to-knee line above level) back INTO ITS BAND: over the band's top the far
             leg is shortened (dm > 0) until the femur stands on it, under its bottom lengthened (dm < 0);
          2. the knee INSIDE ITS RANGE and the foot in reach (this wins over the band): a knee folded under the range
             is opened by a shorter far leg, one past it (or a foot out of reach) closed by a longer one;
        dm never leaves the hinge's own range. For each dm the knee's turn, the aim and both measures are closed form
        (pose2); each rule is one root-find (toward). Both rules are the WALKING animal's: scaled by walk (0 standing:
        the bind). Returns solve()'s dict, with dm and dl (deg)"""
        c, f, t, a, m = self.c, self.f, self.t, self.a, self.m
        BR, Bt = (np.eye(3), np.zeros(3)) if B is None else B
        foot = np.asarray(foot, np.float64)
        if yaw is None:
            Nr = self.ref(walk)
            a0 = np.arctan2(Nr[0] - self.cR[0], Nr[2] - self.cR[2])
            a1 = np.arctan2(foot[0] - self.cR[0], foot[2] - self.cR[2])
            y = a1 - a0
            y = np.arctan2(np.sin(y), np.cos(y))
            y = max(-self.range, min(self.range, y))
        else:
            y = np.radians(yaw)
        Rc, pc = BR @ ry(np.degrees(y)) @ self.R0[c], BR @ self.p0[c] + Bt
        R, p = self.chain(Rc, pc)
        F, RFw = p[f], R[f]
        to_foot = foot - F
        d_raw = float(np.linalg.norm(to_foot))
        u_foot = to_foot / d_raw
        kFw, RFTw = RFw @ self.kF, RFw @ self.RFT
        (lo, hi), (mlo, mhi), (klo, khi) = self.h2['band'], self.h2['turn'], self.h2['knee']
        P = lambda x, aim=True: self.pose2(x, d_raw, kFw, RFTw, u_foot, aim)   # noqa: E731
        dm = 0.0
        dl, Q, e, knee, fr = P(0.0)
        # each rule's turn is scaled by _soft(how far past its edge): the edge is held exactly from H2_SOFT past it on,
        # and a rule the hinge cannot satisfy ramps to its limit (no jump between two samples). And by (1 - up): the
        # band and the knee's range are the PLANTED leg's (the femur held while the foot is down); through a swing they
        # fade out and back with the swing's own sin^2 (in mid-swing a rule crossed its 2 deg in 0.004 of a cycle: the
        # hinge opened 8 deg inside one frame; d41b_NOTES D3j). And by walk (the fix's F1: a standing leg is the bind).
        # The reach (a foot out of reach) is answered whole. A rule whose weight is 0 is not searched (its turn is 0)
        ws = (1.0 - up) * walk
        if fr >= 0.0 and e > hi:                                               # rule 1 (a foot out of reach is
            w = ws * _soft(e - hi)                                             # never answered by a shorter leg)
            if w > 0.0:
                dm = w * self.toward(lambda x: hi - P(x)[2], 0.0, hi - e, mhi)
        elif e < lo:
            w = ws * _soft(lo - e)
            if w > 0.0:
                dm = w * self.toward(lambda x: P(x)[2] - lo, 0.0, e - lo, mlo)
        if dm != 0.0:
            dl, Q, e, knee, fr = P(dm)
        if knee < klo:                                                         # rule 2
            w = ws * _soft(klo - knee)
            if w > 0.0:
                dm = dm + w * (self.toward(lambda x: P(x, False)[3] - klo, dm, knee - klo, mhi) - dm)
                dl, Q, e, knee, fr = P(dm)
        elif knee > khi or fr < 0.0:
            w = 1.0 if fr < 0.0 else ws * _soft(knee - khi)
            if w > 0.0:
                g = lambda x: (lambda r: min(khi - r[3], r[4] / self.lk))(P(x, False))     # noqa: E731
                dm = dm + w * (self.toward(g, dm, min(khi - knee, fr / self.lk), mlo) - dm)
                dl, Q, e, knee, fr = P(dm)
        Ra = ry(np.degrees(dth)) @ self.qTar
        if up > 0:
            Ra = Ra @ rotm([0.0, 0.0, 1.0], np.degrees(-0.45 * up))
        Rn, pn = [None] * 7, [None] * 7
        Rn[c], pn[c] = Rc, pc
        for k in range(c + 1, 7):
            pn[k] = pn[k - 1] + Rn[k - 1] @ self.lt[k]
            Rn[k] = Rn[k - 1] @ self.lR[k]
            if k == f:
                Rn[k] = Q @ Rn[k]
            if k == t:
                Rn[k] = Rn[k] @ rotm([0.0, 0.0, 1.0], np.degrees(dl))
            if k == m:
                Rn[k] = Rn[k] @ rotm([0.0, 0.0, 1.0], np.degrees(dm))
        err = float(np.linalg.norm(pn[a] - foot))
        Rn[a] = Ra
        rot = {self.names[k]: self.lR[k].T @ Rn[k - 1].T @ Rn[k] for k in range(c + 1, 7)}
        rot[self.names[c]] = self.R0[c].T @ BR.T @ Rc
        _, C, rho, _ = self.far(dm)
        return dict(yaw=float(np.degrees(y)), err=err, knee=float(angle(F - pn[t], pn[a] - pn[t])), R=Rn, p=pn,
                    tip=pn[6] + Rn[6] @ self.ltip, d=d_raw, dmin=float(np.sqrt(max(0.0, C - rho))),
                    dmax=float(np.sqrt(C + rho)), rot=rot, iters=0, dm=float(np.degrees(dm)), dl=float(np.degrees(dl)))

    def measures(self, sol):
        """the joint angles AS DRIVEN in a solved step (deg): the femur's rise above level (the coxa-trochanter joint's
        lift), the femur forward of the coxa's axis in plan (that joint's swing), the knee's and the tibia-metatarsus
        joint's included angles"""
        p = sol['p']
        side = -1.0 if self.label[0] == 'R' else 1.0
        uf, uc = _unit(p[self.t] - p[self.f]), _unit(p[self.f] - p[self.c])
        az = lambda v: np.degrees(np.arctan2(side * v[0], v[2]))             # noqa: E731
        sw = az(uc) - az(uf)
        um, uta = _unit(p[6] - p[5]), _unit(sol['tip'] - p[6])
        return dict(lift=float(np.degrees(np.arcsin(uf[1]))), swing=float((sw + 180.0) % 360.0 - 180.0),
                    # the ANATOMICAL knee (femur against patella); sol['knee'] is the solver's own, between its slots
                    knee=float(angle(p[2] - p[3], p[4] - p[3])), tm=float(angle(p[4] - p[5], p[6] - p[5])),
                    # the tarsus from the metatarsus's line, in the joint's own sign (+ curls ventrally: steeper than
                    # the metatarsus; a tarsus lying flatter than its metatarsus reads NEGATIVE, as bind_angles has it.
                    # The first run had this sign turned over, so the walk read +20..+64 beside the bind's -32)
                    mt=float(-angle(um, uta) if uta[1] > um[1] else angle(um, uta)))

    def fk(self, ang, B=None):
        """forward kinematics with a turn about each joint's own z (deg; ang[k] for SEGS[k]) and, on the trochanter,
        the coxa-trochanter joint's SWING ang[7] about the BODY's up (+ carries the femur BACK on either side). The
        coxa is level, so the body's up is that joint's own dorso-ventral axis: a swing turns the leg's plane and
        keeps the femur's rise, and ang[7] is exactly the change of bind_angles' "trochanter (swing)".
        (Until 11-10 22:40 the swing was a turn about the trochanter's own y, an axis tilted off the body's up by the
        femur's bind rise, 48 deg on leg IV: a lifted femur could not then be turned to face the abdomen, and the kick
        stopped 12 mm short of its patch with every turn on its limit.)  Returns (R, p, the tarsus's tip, rot)"""
        BR, Bt = (np.eye(3), np.zeros(3)) if B is None else B
        sgn = -1.0 if self.label[0] == 'R' else 1.0
        R, p = [None] * 7, [None] * 7
        for k in range(7):
            base = BR @ self.R0[0] if k == 0 else R[k - 1] @ self.lR[k]
            p[k] = BR @ self.p0[0] + Bt if k == 0 else p[k - 1] + R[k - 1] @ self.lt[k]
            R[k] = base @ rotm([0.0, 0.0, 1.0], ang[k])
            if k == 1 and len(ang) > 7:
                R[k] = BR @ ry(sgn * ang[7]) @ BR.T @ R[k]
        rot = {self.names[k]: self.lR[k].T @ R[k - 1].T @ R[k] for k in range(1, 7)}
        rot[self.names[0]] = self.R0[0].T @ BR.T @ R[0]
        return R, p, p[6] + R[6] @ self.ltip, rot


def walk_cycle(spec, sk, duty, stride, center, coxa_range=None, n=240, lift=None, ik=None, labels=LABELS,
               hinge2=None, place=None):
    """one cycle of the straight walk on the bound skeleton, every leg through the tarsus solver: stride the body's
    travel a cycle (life mm), center {'I'..'IV': the stance's share at which the foot stands under its rest place}.
    D4.1b: hinge2 as TarsusLeg's (None: as the joint map says; False: the runtime's one-hinge solver); lift a number
    or {pair: mm}; place {pair: (dx, dz) mm}: the WALK's stance place of the pair's foot from the bind's (dx outward
    on either side), None = the SPEC's gait.place when it has one.
    Returns {label: dict(ph, yaw, err, knee, lift, swing, tm, mt, d, dm, dmin, dmax, up, p (n, 7, 3), tip (n, 3))},
    the errors and the places in LIFE mm; sample i is the gait's cycle i / n for every leg (ph is the leg's own phase)"""
    s = spec['author_scale'] * 1e-3
    g = spec['gait']
    if lift is None:                       # the gait's one lift, or per pair where the SPEC has gait.lift_by (D4.1b)
        lift = {R: g['lift_by'].get(R, g['lift']) for R in LEGS} if g.get('lift_by') else g['lift']
    place = g.get('place') if place is None else place
    out = {}
    for label in labels:
        off = g['phase'][LABELS.index(label)]
        L = TarsusLeg(spec, sk, label, coxa_range, ik, hinge2)
        R = LEGS[int(label[1]) - 1]
        if place and R in place:
            L.N = L.N + np.array([(-1.0 if label[0] == 'R' else 1.0) * place[R][0], 0.0, place[R][1]]) * s
        lf = lift[R] if isinstance(lift, dict) else lift
        rows = {k: [] for k in ('ph', 'yaw', 'err', 'knee', 'lift', 'swing', 'tm', 'mt', 'd', 'dm', 'up', 'p', 'tip')}
        for i in range(n):
            ph = (i / n + off) % 1.0
            foot, up = foot_path(L.N, ph, duty, stride * s, lf * s, center[R], g['walk'][1] * s)
            sol = L.solve(foot, up)
            m = L.measures(sol)
            for k, v in (('ph', ph), ('yaw', sol['yaw']), ('err', sol['err'] / s), ('knee', m['knee']),
                         ('lift', m['lift']), ('swing', m['swing']), ('tm', m['tm']), ('mt', m['mt']),
                         ('d', sol['d'] / s), ('dm', sol.get('dm', 0.0)), ('up', up), ('p', np.array(sol['p']) / s),
                         ('tip', sol['tip'] / s)):
                rows[k].append(v)
        out[label] = {k: np.array(v) for k, v in rows.items()}
        out[label].update(dmin=abs(L.Lf - L.Lt) / s, dmax=(L.Lf + L.Lt) / s, N=L.N / s, C=L.cR / s)
    return out


# --------------------------------------------------------------------------------------------- the poses
def _body_move(sk, rot, shift):
    """the BODY joint's rigid move (R, t) from its bind place under the pose (rot, shift), in the root's frame"""
    W = posed(sk, rot, shift)
    i = sk.index('body')
    root = sk.world[sk.index('root')][:3, 3]
    D = W[i] @ np.linalg.inv(sk.world[i])
    return D[:3, :3], D[:3, :3] @ root + D[:3, 3] - root


def _plant(spec, sk, labels, rot, shift):
    """the legs in labels re-solved with their feet where the bind put them, under the body's move in (rot, shift): each
    coxa stays as bound on the body, the trochanter aims, the knee bends, the foot keeps its lie on the ground. Adds
    their joints' rotations to rot; returns {label: the solver's miss, life mm}"""
    s = spec['author_scale'] * 1e-3
    B = _body_move(sk, rot, shift)
    idx, miss = {n: i for i, n in enumerate(sk.names)}, {}
    for label in labels:
        L = TarsusLeg(spec, sk, label, hinge2=False)       # the pose records are the one-hinge solver's (D4.1's)
        sol = L.solve(L.N, B=B, yaw=0.0)
        for nm, D in sol['rot'].items():
            rot[idx[nm]] = D
        miss[label] = sol['err'] / s
    return miss


def _follow_ik(sk, rot, shift):
    """the IK targets follow their drivers (as decapod.rest_pose)"""
    idx = {n: i for i, n in enumerate(sk.names)}
    W = posed(sk, rot, shift)
    for n in [n for n in sk.names if sk.meta[n]['role'] == 'ik']:
        i, drv = idx[n], sk.meta[n]['driver']
        child = [c for c in sk.names if sk.meta[c]['parent'] == drv and sk.meta[c]['role'] != 'ik'][0]
        shift[i] = W[idx[child]][:3, 3] - sk.world[i][:3, 3]
        rot[i] = sk.world[i][:3, :3].T @ W[idx[drv]][:3, :3]
    return posed(sk, rot, shift)


def _palps_hover(spec, sk, rot, shift, lift=0.0):
    """both palps' femora turned about their trochanters (plus lift deg) until their tips hover rig.palp.tip_h up again"""
    s = spec['author_scale'] * 1e-3
    idx = {n: i for i, n in enumerate(sk.names)}
    if lift:
        for sd in 'LR':
            rot[idx[f'palp_trochanter_{sd}']] = rz(lift)
        return lift

    def h(a):
        r2 = dict(rot)
        r2[idx['palp_trochanter_L']] = rz(a)
        return tip_world(sk, posed(sk, r2, shift), 'palp_tarsus_L')[1] / s - spec['rig']['palp']['tip_h']
    a = 0.0 if abs(h(0.0)) < 1e-9 else brentq(h, -60.0, 60.0, xtol=1e-12)
    for sd in 'LR':
        rot[idx[f'palp_trochanter_{sd}']] = rz(a)
    return float(a)


def crouch_pose(spec, sk, chain):
    """the REST pose: the body lowered until the sternum's plane is rig.crouch.clear off the ground (the abdomen's
    underside and the fangs' tips, both rig.abd_sag / the fang's drop under that plane, come to rest on it), every foot
    where the bind put it, the palps' tips hovering as bound. dict(rot, shift, W, miss, drop, palp)"""
    s = chain['scale_m']
    drop = chain['lv']['y_st'] - spec['rig']['crouch']['clear']
    idx = {n: i for i, n in enumerate(sk.names)}
    rot, shift = {}, {idx['body']: np.array([0.0, -drop * s, 0.0])}
    miss = _plant(spec, sk, LABELS, rot, shift)
    palp = _palps_hover(spec, sk, rot, shift)
    return dict(rot=rot, shift=shift, W=_follow_ik(sk, rot, shift), miss=miss, drop=float(drop), palp=palp)


def abdomen_low(spec, sk, chain, W):
    """the lowest point of the abdomen under the world matrices W, life mm above the ground: its ellipsoid (carried by
    the opisthosoma joint) and the spinnerets' joints and tips"""
    s = chain['scale_m']
    idx = {n: i for i, n in enumerate(sk.names)}
    io = idx['opisthosoma']
    D = W[io] @ np.linalg.inv(sk.world[io])
    c = (D[:3, :3] @ (chain['pos']['abd_c'] * s) + D[:3, 3]) / s
    low = float(c[1] - np.sqrt(np.sum((D[1, :3] * chain['pos']['abd_half']) ** 2)))
    for n in [n for n in sk.names if sk.meta[n]['role'] == 'spinneret']:
        low = min(low, float(W[idx[n]][1, 3]) / s)
        if sk.meta[n]['tip'] is not None:
            low = min(low, float(tip_world(sk, W, n)[1]) / s)
    return low


def threat_pose(spec, sk, chain):
    """the THREAT display (plan §11.3): the prosoma reared rig.threat.rear (its front up), the waist bent
    rig.threat.pedicel (the abdomen's rear UP against the prosoma: a negative turn, to its range's end), so the abdomen
    points down behind by the difference and RESTS ITS REAR ON THE GROUND: the body is lifted until the abdomen's lowest
    point touches, the waist keeping its place along the body (the animal leans back on its abdomen). Legs III and IV
    stay planted where the bind put them; legs I and II are raised (their femora lifted rig.threat.lift, their knees
    opened to rig.threat.knee), the palps raised, the chelicerae lifted, the fangs out.
    dict(rot, shift, W, miss, lift (the waist's rise, life mm))"""
    s, th = chain['scale_m'], spec['rig']['threat']
    idx = {n: i for i, n in enumerate(sk.names)}
    rot = {idx['body']: rz(-th['rear']), idx['pedicel']: rz(th['pedicel'])}
    i, j = idx['body'], idx['pedicel']
    W = posed(sk, rot, {})
    # the body's joint is moved so the pedicel's joint keeps its place in plan, then raised until the abdomen touches
    back = sk.world[j][:3, 3] - W[j][:3, 3]
    par = sk.world[sk.parent[i]][:3, :3].T
    waist_up = -abdomen_low(spec, sk, chain, posed(sk, rot, {i: par @ back}))
    shift = {i: par @ (back + np.array([0.0, waist_up * s, 0.0]))}
    miss = _plant(spec, sk, ('L3', 'R3', 'L4', 'R4'), rot, shift)
    for R, lift in zip(('I', 'II'), th['lift']):
        g, n = chain['legs'][R], NUM[R]
        for sd in 'LR':
            rot[idx[f'trochanter_{n}_{sd}']] = rz(lift)
            rot[idx[f'patella_{n}_{sd}']] = rz(g['knee'] - th['knee'])
    for sd in 'LR':
        rot[idx[f'chelicera_{sd}']] = rz(th['chelicera'])
        rot[idx[f'fang_{sd}']] = rz(th['fang'] - spec['rig']['fang']['rest'])
    _palps_hover(spec, sk, rot, shift, lift=th['palp_lift'])
    return dict(rot=rot, shift=shift, W=_follow_ik(sk, rot, shift), miss=miss, lift=float(waist_up))


def kick_pose(spec, sk, chain, side='L'):
    """the URTICATING KICK's two reach poses (plan §11.3): the abdomen pitched up rig.kick.pedicel at the waist; one
    hind leg's tarsus tip laid on the patch at the START and at the END of its stroke (rig.kick.stroke: two places on
    the abdomen's dorsal surface, each (share of its length from the front, share of its half-width from the midline
    toward the leg's own side); the tip stands rig.tarsus_h, the tarsus's half-thickness, off the skin). The leg's
    eight turns (a turn about each joint's own z, and the coxa-trochanter joint's swing about the body's up) are
    solved inside the SPEC's ranges, with every joint and every segment's middle OUTSIDE the abdomen by its own
    radius and above the ground: the START as near the bind as the reach allows, the END as near the start. The
    runtime strokes between the two records (4-8 a second).
    WHERE THE STROKE LIES (d4_01's map, 11-10): leg IV is 68 mm long from its knob and its joints fold no tighter than
    40 (the knee) and 60 (tibia-metatarsus), so its TIP cannot come nearer than the patch's rear part: 0.78 along and
    back with the abdomen level, 0.85 and back pitched up 10, nothing at the plan's first 25 (5.9-9.7 mm short). The
    patch's front part is brushed by the metatarsus's underside (its 14-18 ventral spines, legs.spines_mt.IV) as the
    leg lies further over: D4.11's stroke, with a kick film beside it.
    dict(rot, shift, W (the start's), miss (the worse end, life mm), clear (the leg's least distance off the abdomen's
    skin less its radius, life mm), ends=[dict(rot, W, miss, angles, target, clear) x 2], lo, hi)"""
    s, rg = chain['scale_m'], spec['rig']
    R_ = rg['ranges']
    idx = {n: i for i, n in enumerate(sk.names)}
    rot0 = {idx['pedicel']: rz(rg['kick']['pedicel'])}
    W = posed(sk, rot0, {})
    io = idx['opisthosoma']
    D = W[io] @ np.linalg.inv(sk.world[io])
    root = sk.world[idx['root']][:3, 3]
    c0, half = chain['pos']['abd_c'], chain['pos']['abd_half']            # on the midline: the same for either side
    L = TarsusLeg(spec, sk, f'{side}4')
    g = chain['legs']['IV']
    girth = spec['legs']['pair_girth']['IV']
    rad = {k: 0.5 * spec['legs']['diam'][k] * girth for k in SEGS}

    def off_skin(x):
        """a point's distance off the abdomen's skin along the ray from the abdomen's centre, life mm (negative
        inside); x in the root's frame, metres. The ray's distance is never less than the true one"""
        v = D[:3, :3].T @ (x + root - D[:3, 3]) / s - c0
        lev = float(np.sqrt(np.sum((v / half) ** 2)))
        return (1.0 - 1.0 / max(lev, 1e-9)) * float(np.linalg.norm(v))

    def clear(q):
        """each checked point's distance off the skin less 1.25 x its segment's radius (life mm; all >= 0 = the leg is
        outside the abdomen): the femur's middle, the knee, the patella-tibia, tibia-metatarsus and metatarsus-tarsus
        joints, and the middles of the tibia, the metatarsus and the tarsus (a straight segment between two outside
        joints can still cut the corner of a convex body)"""
        _, p, tip, _ = L.fk(q)
        pts = [(0.5 * (p[2] + p[3]), rad['femur']), (p[3], rad['patella']), (p[4], rad['tibia']),
               (0.5 * (p[4] + p[5]), rad['tibia']), (p[5], rad['metatarsus']), (0.5 * (p[5] + p[6]), rad['metatarsus']),
               (p[6], rad['tarsus']), (0.5 * (p[6] + tip), 0.4 * rad['tarsus'])]
        return np.array([off_skin(x) - 1.25 * r for x, r in pts])

    def target_of(place):
        p0, nrm = abdomen_top(spec, chain, *place)
        if side == 'R':
            p0, nrm = mirror_point(p0), mirror_point(nrm)
        return D[:3, :3] @ ((p0 + rg['tarsus_h'] * nrm) * s) + D[:3, 3] - root
    # each turn's bounds from the SPEC's ranges, as turns from the bind: the lift raises the femur; a + turn closes the
    # knee and the tibia-metatarsus joint; the tarsus's range is its own turn (the bind's lie counted in it); a + swing
    # turn carries the femur BACK, so it takes from "the femur forward of the coxa's axis"
    t0 = -(g['s_mt'] - g['s_ta'])
    lo = np.array([R_['coxa'][0], R_['trochanter'][0] - g['e'], R_['femur'][0], g['knee'] - R_['patella'][1],
                   R_['tibia'][0], g['tm'] - R_['metatarsus'][1], R_['tarsus'][0] - t0,
                   g['swing'] - R_['trochanter_swing'][1]])
    hi = np.array([R_['coxa'][1], R_['trochanter'][1] - g['e'], R_['femur'][1], g['knee'] - R_['patella'][0],
                   R_['tibia'][1], g['tm'] - R_['metatarsus'][0], R_['tarsus'][1] - t0,
                   g['swing'] - R_['trochanter_swing'][0]])
    span = 0.5 * (hi - lo)
    eps = 1e-6 * (hi - lo)

    def under(q):
        """how far each of the leg's joints and its tip stand UNDER the ground (life mm, 0 when above): the nearest
        pose is searched among the poses an animal can stand in (the first search wrapped the leg through the floor)"""
        _, p, tip, _ = L.fk(q)
        return np.minimum(0.0, np.array([pk[1] for pk in p[1:]] + [tip[1]])) / s

    def reach(target, ref, n_rand):
        """one end of the stroke: the tip on target, the leg outside the abdomen and above the ground, the pose as near
        `ref` (eight turns) as the reach allows. 1. THE REACH from many starts (ref, three by hand, then a fixed
        random set inside the ranges): a bounded least squares on the tip's place, the floor and the abdomen. 2. THE
        NEAREST SUCH POSE TO ref: SLSQP from each reach that landed, the tip held on the target. (SLSQP alone, from a
        start off the target, stopped on its bounds 20 mm short: 11-10.)  Returns (the tip's miss life mm, q)"""
        gap = lambda q: np.concatenate([(L.fk(q)[2] - target) / s, 10.0 * under(q),            # noqa: E731
                                        10.0 * np.minimum(0.0, clear(q))])
        cost = lambda q: float(np.sum(((q - ref) / span) ** 2))                               # noqa: E731
        rng = np.random.default_rng(41)
        starts = [np.asarray(ref, np.float64)]
        starts += [np.array(sd, np.float64) for sd in ((0, 30, 0, -60, 0, 80, 40, 90), (0, 25, 0, -30, 0, 60, 20, 70),
                                                       (0, 30, 0, 0, 0, 0, 0, 60))]
        starts += [lo + rng.random(8) * (hi - lo) for _ in range(n_rand)]
        best = None
        for q0 in starts:
            r1 = least_squares(gap, np.clip(q0, lo + eps, hi - eps), bounds=(lo, hi), xtol=1e-13, ftol=1e-13,
                               gtol=1e-13)
            cands = [r1.x]
            if float(np.linalg.norm(gap(r1.x))) < 1e-4:
                r2 = minimize(cost, r1.x, method='SLSQP', bounds=list(zip(lo, hi)),
                              constraints=[dict(type='eq', fun=lambda q: (L.fk(q)[2] - target) / s / 10.0),
                                           dict(type='ineq', fun=lambda q: under(q) + 1e-9),
                                           dict(type='ineq', fun=lambda q: clear(q) + 1e-9)],
                              options=dict(ftol=1e-12, maxiter=600))
                cands.append(np.clip(r2.x, lo, hi))
            for q in cands:
                gq = gap(q)
                key = (round(float(np.linalg.norm(gq)), 5), cost(q))      # the miss, the floor, the abdomen; then ref
                if best is None or key < best[0]:
                    best = (key, float(np.linalg.norm(gq[:3])), q)
        return best[1], best[2]

    ends, ref = [], np.zeros(8)
    for k, place in enumerate(rg['kick']['stroke']):
        target = target_of(place)
        miss, q = reach(target, ref, 12 if k == 0 else 6)
        rot = dict(rot0)
        for nm, Dk in L.fk(q)[3].items():
            rot[idx[nm]] = Dk
        ends.append(dict(rot=rot, W=_follow_ik(sk, rot, {}), miss=miss, angles=q, target=(target + root) / s,
                         clear=float(clear(q).min())))
        ref = q
    return dict(rot=ends[0]['rot'], shift={}, W=ends[0]['W'], miss=max(e['miss'] for e in ends),
                clear=min(e['clear'] for e in ends), ends=ends, lo=lo, hi=hi)
