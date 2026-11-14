"""THE HUMAN'S SEATS AND FITS (H4, the rig builder, 11-01; HUMAN_PLAN §4.4, §6.5): fit.py's seats measured on each
identity's REST LOW (the glb's T-pose rest: the surface the engine draws), and the library's accessories placed and
CHECKED on them, as t13's octopus export does for its block-out (work/bestiary/tests/t13_octopus_export.py:280-362).

  * MeshSDF: fit.py's `prog` contract (eval, project, normals) on a CLOSED triangle mesh. sdf.Program has no signed mesh
    primitive (its SHELL is unsigned), and the human's surface IS a mesh (the low, drawn as it is):
      eval     signed distance, negative inside, the sign by Warp's winding number (the refined low is closed: 0 boundary
               edges, 0 non-manifold, r01);
      project  sdf.Program.project's convention (fit.py's docstring: it takes the OUTWARD direction; from outside it
               marches against it, from inside along it): a ray cast, the first crossing within maxd, status 0; with no
               crossing the closest point, status 1 (k_project's Newton fallback ends on the skin's nearest point too);
      normals  the low's own vertex normals interpolated at the closest point: the shading normal, so fit.seat's test
               ("on a smooth convex top the skin's normal at its highest point IS up") reads the surface the engine
               lights, not a facet.
  * seat_hat: fit.seat on the scalp along the head joint's up (the VRM rest: identity rotations, so world +Y), from the
    vertex landmark; its section table (fit.seat_table, monotone rows) down past the band's depth.
  * seat_glasses: fit.eye_rig with bridge_lift 0 (the plan: "the nose's root at sellion") and the HOOKS GIVEN, per the
    plan: the top of each ear root ring (recs['head']['ear_<s>']['loop'], the auricle's attachment, at its highest
    point). Each eye's EXIT is the cornea's apex: the eye centre lies in the lid pocket, OUTSIDE the closed skin, so
    eye_rig's own projection from it marches into the socket. The eye RADIUS the seat carries is the lens's own over
    FIT_EYE (round_glasses.fit_pose scales the frame to FIT_EYE x the eye radius: the human wears the glasses at the size
    they were drawn for, "a man's"), and the STANDOFF puts the lens VERTEX_MM before the cornea (a spectacle's vertex
    distance).
  * the fits: the top hat by fit.fit_hat at the BAND's depth (BAND_OVER_BROW_MM over the brow line: the hat scales per
    axis to the head's own oval, within fit.py's 1.25); the peaked cap by peaked_cap.validate_fit (scales round the
    section's own at the band, shifts and tilts for a person); the round glasses by round_glasses.validate_fit (the pads
    bent, the temples rolled, the cable temples draped behind the ears).

    prog = MeshSDF(V_m, F)                    the rest low in metres
    hat = hat_seat(prog, vertex_m, brow_y_m)  dict(R, origin, normal, table, band_depth)
    gl = glasses_seat(prog, eyes_m, cornea_front_m, hooks_m)
"""
import numpy as np
import warp as wp

from .. import fit as FIT

VERSION = 'h4-seats-1'
BAND_OVER_BROW_MM = 20.0        # a hat's band over the brow line (the forehead's lower third; the brims' rule of thumb)
VERTEX_MM = 12.0                # a spectacle lens's vertex distance before the cornea (12-14 mm in optometry)
HAT_DEPTHS = np.arange(0.004, 0.1201, 0.002)     # the seat table's rows (m below the seat): to the ears' tops and past


@wp.kernel
def _k_closest(mesh: wp.uint64, P: wp.array(dtype=wp.vec3), maxd: float, sgn: wp.array(dtype=float),
               dist: wp.array(dtype=float), cp: wp.array(dtype=wp.vec3), face: wp.array(dtype=int),
               bu: wp.array(dtype=float), bv: wp.array(dtype=float)):
    i = wp.tid()
    q = wp.mesh_query_point_sign_winding_number(mesh, P[i], maxd, 2.0, 0.5)
    if q.result:
        c = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        sgn[i] = q.sign
        dist[i] = wp.length(P[i] - c)
        cp[i] = c
        face[i] = q.face
        bu[i] = q.u
        bv[i] = q.v
    else:
        sgn[i] = 1.0
        dist[i] = maxd
        cp[i] = P[i]
        face[i] = -1
        bu[i] = 0.0
        bv[i] = 0.0


@wp.kernel
def _k_ray(mesh: wp.uint64, P: wp.array(dtype=wp.vec3), D: wp.array(dtype=wp.vec3), maxd: float,
           t_out: wp.array(dtype=float), hit: wp.array(dtype=int)):
    i = wp.tid()
    q = wp.mesh_query_ray(mesh, P[i], D[i], maxd)
    if q.result:
        t_out[i] = q.t
        hit[i] = 1
    else:
        t_out[i] = maxd
        hit[i] = 0


def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _rot_min(a, b):
    """the minimal rotation taking unit a onto unit b (Rodrigues)"""
    a, b = _unit(a), _unit(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-12:
        return np.eye(3) if c > 0 else -np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1.0 / (1.0 + c))


class MeshSDF:
    """fit.py's prog on a closed triangle mesh (module docstring). V (n, 3) metres, F (m, 3); N the vertex normals
    (default: area-weighted from the mesh)"""

    def __init__(self, V, F, N=None, device=None, far=10.0):
        self.V = np.asarray(V, np.float64)
        self.F = np.asarray(F, np.int32)
        if N is None:
            P = self.V[self.F]
            fn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
            N = np.zeros_like(self.V)
            for k in range(3):
                np.add.at(N, self.F[:, k], fn)
        self.N = _unit(N)
        self.device = device or ('cuda:0' if wp.is_cuda_available() else 'cpu')
        self.far = float(far)
        self.mesh = wp.Mesh(points=wp.array(self.V.astype(np.float32), dtype=wp.vec3, device=self.device),
                            indices=wp.array(self.F.ravel(), dtype=int, device=self.device),
                            support_winding_number=True)

    def _closest(self, pts):
        P = np.asarray(pts, np.float64).reshape(-1, 3)
        n = len(P)
        d = self.device
        Pw = wp.array(P.astype(np.float32), dtype=wp.vec3, device=d)
        out = [wp.zeros(n, dtype=float, device=d), wp.zeros(n, dtype=float, device=d),
               wp.zeros(n, dtype=wp.vec3, device=d), wp.zeros(n, dtype=int, device=d),
               wp.zeros(n, dtype=float, device=d), wp.zeros(n, dtype=float, device=d)]
        wp.launch(_k_closest, dim=n, inputs=[self.mesh.id, Pw, self.far] + out, device=d)
        sgn, dist, cp, face, u, v = (a.numpy() for a in out)
        return P, sgn.astype(np.float64), dist.astype(np.float64), cp.astype(np.float64), face, u, v

    def eval(self, pts):
        _, sgn, dist, _, _, _, _ = self._closest(pts)
        return (sgn * dist).astype(np.float32)

    def project(self, pts, dirs, maxd=0.05):
        P, sgn, dist, cp, _, _, _ = self._closest(pts)
        D = _unit(np.asarray(dirs, np.float64).reshape(-1, 3))
        D = np.where((sgn * dist >= 0.0)[:, None], -D, D)          # outside: against the outward direction
        d = self.device
        t = wp.zeros(len(P), dtype=float, device=d)
        hit = wp.zeros(len(P), dtype=int, device=d)
        wp.launch(_k_ray, dim=len(P), inputs=[self.mesh.id, wp.array(P.astype(np.float32), dtype=wp.vec3, device=d),
                                              wp.array(D.astype(np.float32), dtype=wp.vec3, device=d), float(maxd), t,
                                              hit], device=d)
        t, hit = t.numpy().astype(np.float64), hit.numpy()
        out = np.where(hit[:, None] == 1, P + D * t[:, None], cp)
        return out, np.where(hit == 1, 0, 1).astype(np.int32)

    def normals(self, pts, h=None):
        _, _, _, _, face, u, v = self._closest(pts)
        f = self.F[np.maximum(face, 0)]
        n = (u[:, None] * self.N[f[:, 0]] + v[:, None] * self.N[f[:, 1]]
             + (1.0 - u - v)[:, None] * self.N[f[:, 2]])
        return _unit(n)

    def check(self, n=2000, seed=0):
        """the barycentric convention read back: the closest points rebuilt from (face, u, v) against Warp's own"""
        rng = np.random.default_rng(seed)
        lo, hi = self.V.min(0), self.V.max(0)
        P = lo + rng.random((n, 3)) * (hi - lo)
        _, _, _, cp, face, u, v = self._closest(P)
        f = self.F[face]
        q = u[:, None] * self.V[f[:, 0]] + v[:, None] * self.V[f[:, 1]] + (1.0 - u - v)[:, None] * self.V[f[:, 2]]
        return float(np.abs(q - cp).max())


def hat_seat(prog, vertex_m, brow_y_m, up=(0.0, 1.0, 0.0), forward=(0.0, 0.0, 1.0)):
    """seat_hat: fit.seat from the vertex landmark along up (tilt 0: the head joint's up IS the axis), the table, and the
    band's depth below the seat (BAND_OVER_BROW_MM over the brow line, clipped into the table)"""
    R, o, n = FIT.seat(prog, np.asarray(vertex_m, np.float64), np.asarray(up, np.float64), forward, tilt=0.0)
    T = FIT.monotone_rows(FIT.seat_table(prog, o, R, HAT_DEPTHS))
    band = float(np.dot(o, R[:, 1]) - (brow_y_m + BAND_OVER_BROW_MM * 1e-3))
    band = float(np.clip(band, T[0, 0], T[-1, 0]))
    off = float(np.degrees(np.arccos(np.clip(np.dot(_unit(n), R[:, 1]), -1.0, 1.0))))
    return dict(R=R, origin=o, normal=n, table=T, band_depth=band, normal_off_deg=off)


def glasses_seat(prog, eyes_m, cornea_front_m, hooks_m, lens_radius, fit_eye, forward=(0.0, 0.0, 1.0),
                 up=(0.0, 1.0, 0.0), vertex_mm=VERTEX_MM, bridge_off_mm=0.0, size=1.0, panto_deg=0.0, hook_lift_mm=0.0,
                 glasses=None, drop_mm=0.0, root='nose', roll='hook'):
    """seat_glasses (module docstring): eyes_m [(centre L), (centre R)] metres, the optical axis = forward; hooks_m the
    ear roots' tops [L, R]; lens_radius the glasses' own aperture radius (fit_data()['lens']['radius']). vertex_mm the
    lens's distance before the cornea; size the frame's scale over its drawn size (fit_pose: FIT_EYE x the eye radius
    over the lens's). The fitter's adjustments fit_glasses makes (H4, 11-01): drop_mm THE FRAME'S HEIGHT, its lens
    centres this far under the pupils (the seat's eye centres lowered: fit_pose puts each lens on its eye's axis; an
    optician's fitting height: this C-bridge's apex stands 20.7 mm over the lens centres, where a face has its brow
    ridge, so the frame sits low on the nose); hook_lift_mm each hook pushed off the skin along its normal (a temple
    splayed out over a head wider at the temples than the line from the hinge to the ear root); panto_deg a
    PANTOSCOPIC TILT (the lenses' axes turned down; kept 0 by fit_glasses: fit_pose rolls each lens until its
    endpiece points at its hook in the lens plane, and a tilted lens plane sees the hook below, 20 deg of roll at
    12 deg of tilt, which swings the bridge's junctions and stands the C-bridge up over the brows).
    THE SEAT FRAME AND ORIGIN (H4 11-01, after the first fits): +Z the lenses' axis, +Y the head's up made perpendicular
    (the nose root's skin normal, the octopus's +Z, tilts up 30-40 deg on a face: the frame's root turned with it and the
    bridge stood up); the origin, where fit_pose puts the bridge's root (its apex's contact point): root='nose' (the
    default) the skin point straight before the (lowered) eyes' midpoint (fit.eye_rig's bridge): the root rests on the
    nose and the band, skinned from the root to the lens joints, bends down to it; root='natural' (`glasses` given)
    where the band's own rest shape puts it once fit_pose has set the lenses (the root's rest point carried rigidly by
    each lens joint, the two averaged): that keeps the band's shape but stands it 28 mm over a woman's pupils, on her
    forehead, because fit_pose rolls each lens until its endpiece points at its hook (her ear roots' tops lie ~10 mm
    under the eyes: 17 deg of roll swings the junctions up). bridge_off_mm shifts the origin along +Z.
    roll='none' (`glasses` given): NO LENS ROLL. fit_pose turns each lens until its endpiece points at the seat's
    'hook' in the lens plane, and aims each temple at the validated target when the seat's entry carries one (the
    runtime's glassesPose the same): so each eye's 'hook' becomes an ANCHOR in the lens's own endpiece direction (40 mm
    out along it, 60 mm back), the true ear point is kept as 'ear', and validate_human aims the temples at the ears.
    A person's lenses do not roll toward the ears; the temple's hinge takes the angle. Returns (seat record in the seat
    frame, R_g, the seat origin (world), rig)"""
    a = _unit(forward)
    u = _unit(up)
    r_eye = float(size) * float(lens_radius) / float(fit_eye)
    dropv = -u * (float(drop_mm) * 1e-3)
    eyes = [(np.asarray(eyes_m[0], np.float64) + dropv, r_eye, a), (np.asarray(eyes_m[1], np.float64) + dropv, r_eye, a)]
    rig = FIT.eye_rig(prog, eyes, forward, up, bridge_lift=0.0)        # the bridge met along the untilted axes
    t = np.radians(float(panto_deg))
    a_t = _unit(np.cos(t) * a - np.sin(t) * (u - a * np.dot(u, a)))     # the lenses' axis, tilted
    for e, h in zip(rig['eyes'], hooks_m):
        h = np.asarray(h, np.float64)
        n_h = np.asarray(prog.normals(h[None])[0], np.float64)
        e['hook'] = h + n_h * (float(hook_lift_mm) * 1e-3)
        e['axis'] = a_t
        e['exit'] = e['centre'] + a_t * float(cornea_front_m)
    R_g = FIT.frame(u, a_t)
    standoff = max(0.0, float(cornea_front_m) + float(vertex_mm) * 1e-3 - r_eye)
    if glasses is not None and roll == 'none':
        fit = glasses.fit_data()
        q = _rot_min(np.array([0.0, 0.0, 1.0]), R_g.T @ a_t)          # the rest lens frame onto the tilted axis
        for e, sfx in zip(rig['eyes'], 'LR'):
            P = e['centre'] + a_t * (max(float(cornea_front_m), r_eye) + standoff)     # fit_pose's lens centre (world)
            e0 = R_g @ (q @ np.asarray(fit['sides'][sfx]['end_dir'], np.float64))
            e['ear'] = e['hook']
            e['hook'] = P + e0 * 0.040 - a_t * 0.060

    def make(B):
        to_seat = lambda p: (R_g.T @ (np.asarray(p) - B)).round(6).tolist()
        return dict(
            archetype='glasses', spacing=round(rig['spacing'], 5), standoff=round(standoff, 5),
            ok=bool(rig['bridge_ok']),
            eyes=[dict(centre=to_seat(e['centre']), radius=round(e['radius'], 5),
                       axis=(R_g.T @ e['axis']).round(6).tolist(), splay=round(e['splay'], 2), pitch=round(e['pitch'], 2),
                       hook=to_seat(e['hook']), exit=to_seat(e['exit']),
                       **({'ear': to_seat(e['ear'])} if 'ear' in e else {})) for e in rig['eyes']],
            hooks=('the ear roots\' tops (recs head ear_<s> loop, highest point), given (HUMAN_PLAN §4.4)' if roll != 'none'
                   else 'each eye\'s hook is the NO-ROLL ANCHOR (its lens\'s endpiece direction); its ear root\'s top is '
                        '\'ear\', where validated.round_glasses.target aims the temple'),
            vertex_distance_mm=round(float(vertex_mm), 2), bridge_off_mm=round(float(bridge_off_mm), 2),
            size=round(float(size), 4), pantoscopic_deg=round(float(panto_deg), 2),
            hook_lift_mm=round(float(hook_lift_mm), 2), drop_mm=round(float(drop_mm), 2),
            eye_centres='the pupils\' centres lowered by drop_mm (the frame\'s fitting height)')
    B = np.asarray(rig['bridge'], np.float64)
    seat = make(B)
    if glasses is not None and root == 'natural':
        fit = glasses.fit_data()
        pose = glasses.fit_pose(fit, seat, up=R_g.T @ u)
        nat = np.mean([pose['local'][f'lens_{k}'][1] - pose['local'][f'lens_{k}'][0] @ np.asarray(fit['sides'][k]['junction'])
                       for k in 'LR'], axis=0)                      # the root's rest point carried by the lenses (prop)
        B = B + R_g @ (pose['scale'] * nat)                            # the lenses stay put in the world: one step
        seat = make(B)
        seat['root_natural_mm'] = (pose['scale'] * nat * 1e3).round(2).tolist()
    if float(bridge_off_mm):
        B = B + R_g[:, 2] * (float(bridge_off_mm) * 1e-3)
        seat = make(B)
    return seat, R_g, B, rig


FRONT_PARTS = ('rim', 'lens', 'cup', 'pad', 'bridge', 'pad_arm')    # what sits before the face
SIDE_PARTS = ('temple', 'hook')                                      # what runs back to the ears


DROP_MAX_MM = 8.0               # the lens centres at most this under the pupils (the eyes still look through the upper
                                # half of a 37 mm aperture)
VERTEX_MAX_MM = 22.0            # past this a frame no longer sits on its wearer's nose (the pads ride the lenses)


def _glasses_dist(glasses, prog, L, pose, R_g, B):
    """every vertex of the posed glasses: its seat-frame position and its signed skin distance (m)"""
    P = glasses.posed_vertices(glasses.SPEC, L, pose)
    return P, np.asarray(prog.eval(P @ R_g.T + B), np.float64)


def validate_human(glasses, prog, R_g, B, seat, up_seat, L, target=0.0003, lift=0.0):
    """round_glasses.validate_fit for a seat with NO LENS ROLL (glasses_seat roll='none'): the same steps and bars,
    the prop's own helpers, with one change: each temple's TARGET is its eye's EAR (the ear root's top) pushed `target`
    + the cable's radius + `lift` off the skin along its normal there, where validate_fit takes the seat's 'hook'
    (here the no-roll anchor). Then, as validate_fit: the roll that hangs each ear hook down the skin's tangent at its
    ear, over the runtime's fallback (the creature's up); each pad arm's smallest bend (about the rim's tangent or
    radius at its root, at most 45 deg) that clears the skin and keeps the pad behind the rims' plane; the cable
    draped down its chain (pushed out where it cuts, drawn in where it floats, 20 deg a step at most). fit_pose with
    this entry is exactly the runtime's glassesPose with it. Returns (validated dict, the final pose, per-region
    minimum skin distance in metres)"""
    G = glasses
    spec = G.SPEC
    fit = G.fit_data(spec)
    to_w = lambda P: np.asarray(P) @ R_g.T + B
    seat_n = {k: v for k, v in seat.items() if k != 'validated'}
    up = _unit(up_seat)
    tg, nrm = [], []
    for e in seat_n['eyes']:
        ew = to_w(np.asarray(e['ear'], np.float64)[None])[0]
        n_s = R_g.T @ np.asarray(prog.normals(ew[None])[0], np.float64)
        nrm.append(n_s)
        tg.append((np.asarray(e['ear'], np.float64) + n_s * (target + 0.5 * fit['cable_d'] + lift)).round(6).tolist())
    adj = dict(pad=[[0.0] * 3, [0.0] * 3], roll=[0.0, 0.0], target=tg,
               cable={'L': [[0.0] * 3 for _ in range(G.N_CABLE)], 'R': [[0.0] * 3 for _ in range(G.N_CABLE)]})
    p_base = G.fit_pose(fit, seat_n, up=up_seat, gap=target, adjust=adj)
    for k, sfx in enumerate('LR'):
        Wh = p_base['world'][f'hook_{sfx}'][:3, :3]
        dt = _unit(-Wh[:, 2])
        g = -up + nrm[k] * np.dot(nrm[k], up)
        g = _unit(g - dt * np.dot(g, dt))
        cd = -Wh[:, 1]
        cd = _unit(cd - dt * np.dot(cd, dt))
        adj['roll'][k] = round(float(np.degrees(np.arctan2(np.dot(np.cross(cd, g), dt), np.dot(cd, g)))), 3)
    reg_v = np.full(len(L['V']), -1)
    for r in range(len(G.REGIONS)):
        reg_v[np.unique(L['F'][L['region'] == r])] = r
    jn = {nm: G.JOINTS.index(nm) for nm in G.JOINTS}
    dom = L['joints'][np.arange(len(L['V'])), np.argmax(L['weights'], axis=1)]

    def dist_of(a):
        P = G.posed_vertices(spec, L, G.fit_pose(fit, seat_n, up=up_seat, gap=target, adjust=a))
        return np.asarray(prog.eval(to_w(P)), np.float64), P
    d = G.dims(spec)
    for k, (sfx, side) in enumerate(zip('LR', (1, -1))):
        sel = dom == jn[f'pad_{sfx}']
        ph = np.radians(spec['pad_phi'])
        axes = [G.mirror([-np.sin(ph), np.cos(ph), 0.0], side), G.mirror([np.cos(ph), np.sin(ph), 0.0], side)]
        Vr = L['V'][sel]
        root = np.asarray(fit['sides'][sfx]['pad_root'])
        C = G.mirror(d['C'], side)
        best = ([0.0, 0.0, 0.0], -np.inf)
        for al in sorted(np.arange(-45.0, 46.0, 5.0), key=abs):
            for ax in (axes[:1] if al == 0.0 else axes):
                rv = (np.asarray(ax) * np.radians(al)).tolist()
                Pr = (Vr - root) @ G._rotvec(rv).T + root
                over = np.hypot(Pr[:, 0] - C[0], Pr[:, 1] - C[1]) < d['r_o']
                if over.any() and Pr[over, 2].max() > d['zl'] - 0.0003:
                    continue
                adj['pad'][k] = rv
                dmin = float(dist_of(adj)[0][sel].min())
                if dmin > best[1]:
                    best = (rv, dmin)
                if dmin >= target:
                    break
            if best[1] >= target:
                break
        adj['pad'][k] = [round(x, 6) for x in best[0]]
    Pt_, st_, sb_ = G.temple_curve(spec, 1)
    sc = np.concatenate([G.cable_s(spec), [np.inf]])
    s_c = L['ATTR'][:, 0] - sb_
    hug = target + 0.0004
    for k, sfx in enumerate('LR'):
        chain = [f'cable_{sfx}{i + 1}' for i in range(G.N_CABLE)]
        mine = (reg_v == 5) & np.isin(dom, [jn[c] for c in chain + [f'hook_{sfx}']])
        for it in range(24):
            moved = False
            for i, cn in enumerate(chain):
                dist, P = dist_of(adj)
                cand = mine & (s_c >= sc[i] + 0.0015) & (s_c < sc[i + 1] + 0.0015)
                if not cand.any():
                    continue
                j = np.nonzero(cand)[0][np.argmin(dist[cand])]
                if dist[j] >= target:
                    if it >= 18:
                        continue
                    ring = cand & (s_c >= s_c[cand].max() - 0.0004)
                    j = np.nonzero(ring)[0][np.argmin(dist[ring])]
                    if dist[j] <= hug:
                        continue
                    want = target + 0.00015 - dist[j]
                else:
                    want = target - dist[j] + 0.0001
                pose = G.fit_pose(fit, seat_n, up=up_seat, gap=target, adjust=adj)
                pj = pose['world'][cn][:3, 3]
                n = R_g.T @ prog.normals(to_w(P[j][None]))[0]
                v = P[j] - pj
                if np.linalg.norm(v) < 0.002:
                    continue
                dw = G._rot_between(v, v + n * want)
                ang = np.arccos(np.clip(0.5 * (np.trace(dw) - 1.0), -1.0, 1.0))
                if ang > np.radians(20.0):
                    dw = G._rotvec(G._vecrot(dw) * (np.radians(20.0) / ang))
                par = pose['world'][f'hook_{sfx}' if i == 0 else chain[i - 1]][:3, :3]
                Rp = par / np.linalg.norm(par[:, 0])
                Lc = G._rotvec(adj['cable'][sfx][i])
                adj['cable'][sfx][i] = G._vecrot((Rp.T @ dw @ Rp) @ Lc).round(6).tolist()
                moved = True
            if not moved:
                break
    dist, P = dist_of(adj)
    per = {G.REGIONS[r]: float(dist[reg_v == r].min()) for r in range(len(G.REGIONS)) if (reg_v == r).any()}
    adj['clearance_min'] = round(float(dist.min()), 6)
    adj['ok'] = bool(dist.min() >= 0.0)
    adj['how'] = 'human_seats.validate_human: no lens roll (the seat\'s hooks are anchors), the temples aimed at the ears'
    return adj, G.fit_pose(fit, seat_n, up=up_seat, gap=target, adjust=adj), per


def fit_glasses(prog, eyes_m, cornea_front_m, hooks_m, glasses, clear=0.0003, rounds=16, log=print):
    """the round glasses per identity, FITTED as an optician fits a frame (H4 11-01; the levers are the ones that move
    the part that touches, read from round_glasses.fit_pose: the LENSES sit on the eye axes at the vertex distance,
    the PADS and their cups ride the lenses, the C-BRIDGE is skinned from the root (the seat origin) to the lenses,
    each TEMPLE runs straight from its hinge to its hook). glasses_seat with NO LENS ROLL and the root where the
    bridge's own shape puts it (both reasons in its docstring; the looks of 11-01 07:2x-07:4x: rolled lenses stood the
    bridge on her forehead, a root pulled onto the nose bent it into a W) + validate_human (validate_fit's steps with
    the temples aimed at the ears: the pads bent, the hooks rolled, the cables draped), then per round, by what touched
    (each part's deepest vertex, signed skin distance), until every part clears the skin by `clear`:
      * a RIM or a LENS: above its lens's centre (a brow ridge) the frame 2 mm lower on the nose, up to DROP_MAX_MM
        under the pupils; below it, or at the drop's limit, the lenses farther before the corneas by the shortfall
        + 0.5 mm;
      * a PAD, CUP or PAD ARM still in the nose after the bend, or the C-BRIDGE (rigid with the lenses): the frame
        farther out the same way;
      * a TEMPLE or an EAR HOOK: the hooks farther off the skin by the shortfall + 0.5 mm (the temples splayed).
    The frame keeps its drawn size ("a man's", round_glasses.py: both sexes wear the one frame). `glasses` is the
    round_glasses module. Returns (seat, R_g, B, rig, adj, pose, per, L)"""
    L = glasses.low_arrays(*_glasses_low(glasses))
    fit = glasses.fit_data()
    reg_v = np.full(len(L['V']), -1)
    for r in range(len(glasses.REGIONS)):
        reg_v[np.unique(L['F'][L['region'] == r])] = r
    rid = {nm: glasses.REGIONS.index(nm) for nm in glasses.REGIONS}
    st = dict(v=VERTEX_MM, panto=0.0, b=0.0, lift=0.0, drop=0.0)
    hist = []
    for k in range(rounds):
        seat, R_g, B, rig = glasses_seat(prog, eyes_m, cornea_front_m, hooks_m, fit['lens']['radius'],
                                         glasses.FIT_EYE, vertex_mm=st['v'], bridge_off_mm=st['b'],
                                         panto_deg=st['panto'], hook_lift_mm=st['lift'], glasses=glasses,
                                         drop_mm=st['drop'], root='natural', roll='none')
        up_s = R_g.T @ np.array([0.0, 1.0, 0.0])
        adj, pose, per = validate_human(glasses, prog, R_g, B, seat, up_s, L)
        P, dist = _glasses_dist(glasses, prog, L, pose, R_g, B)
        short = {g: min(per.get(p, 1.0) for p in parts) for g, parts in
                 (('face', ('rim', 'lens')), ('pads', ('pad', 'cup', 'pad_arm')), ('bridge', ('bridge',)),
                  ('side', ('temple', 'hook')))}
        # where the face touches: the deepest rim / lens vertex's height over its own lens's rim centre (seat frame)
        fm = np.isin(reg_v, [rid['rim'], rid['lens']])
        j = np.nonzero(fm)[0][int(np.argmin(dist[fm]))]
        side_m = fm & (np.sign(P[:, 0]) == np.sign(P[j, 0]))
        upper = bool(P[j, 1] > P[side_m, 1].mean())
        hist.append(dict(vertex_mm=round(st['v'], 2), drop_mm=round(st['drop'], 1), hook_lift_mm=round(st['lift'], 2),
                         root_natural_mm=seat.get('root_natural_mm'),
                         **{f'{g}_mm': round(v * 1e3, 2) for g, v in short.items()}, face_touch='upper' if upper else 'lower'))
        log(f'[human_seats] glasses round {k}: vertex {st["v"]:.1f} mm, the frame {st["drop"]:.0f} mm under the pupils, '
            f'hooks out {st["lift"]:.1f} mm, the bridge root {seat.get("root_natural_mm")} mm off the nose point: '
            f'rims/lens {short["face"] * 1e3:+.2f} mm ({"upper" if upper else "lower"} arc), pads '
            f'{short["pads"] * 1e3:+.2f}, bridge {short["bridge"] * 1e3:+.2f}, temples/hooks {short["side"] * 1e3:+.2f}')
        if min(short.values()) >= clear:
            break
        if short['face'] < clear:
            if upper and st['drop'] < DROP_MAX_MM:
                st['drop'] = min(DROP_MAX_MM, st['drop'] + 2.0)
            else:
                st['v'] = min(VERTEX_MAX_MM, st['v'] + (clear - short['face']) * 1e3 + 0.5)
        elif min(short['pads'], short['bridge']) < clear:
            st['v'] = min(VERTEX_MAX_MM, st['v'] + (clear - min(short['pads'], short['bridge'])) * 1e3 + 0.5)
        if short['side'] < clear:
            st['lift'] += (clear - short['side']) * 1e3 + 0.5
    seat['validated'] = {'round_glasses': adj}
    seat['up'] = up_s.round(5).tolist()
    seat['fit_rounds'] = hist
    seat['fit_ok'] = bool(min(short.values()) >= clear)
    seat['clear_m'] = clear
    return seat, R_g, B, rig, adj, pose, per, L


CAP_TILTS = (0.0, 3.0, 6.0, 9.0, 12.0, 15.0)      # the cap's tilt back (deg): a worn cap's band runs brow -> occiput
CAP_SHIFTS = tuple(np.round(np.arange(-0.020, 0.0101, 0.005), 4))
CAP_BAND_OVER_BROW = 0.020      # where the cap's band foot reads right in front: about 2 cm over the brow line


def fit_cap(prog, cap, o_s, R_s, T_s, band_depth, L_c, avoid, scene, brow_y, log=print):
    """the peaked cap WORN by a person (H4 11-01): validate_fit's machinery (the band's horizontal give, the visor's
    hinge, the rest found by lowering, the support gates, the clearances of the eyes and the glasses) with the
    person's pose space in place of the octopus's perched one:
      * THE SIZE is the head's: from the opening's mean radius over the head's at the band's depth (the seat table's
        r_mean, BAND_OVER_BROW_MM over the brow) to the size whose long axis reaches the head's there (four sizes); a
        cap is bought to fit its wearer, where on the octopus's mantle the least size that perches was the call
        (validate_fit keeps that when a scene is passed, so it is called without one here and the daylight is cast
        below);
      * THE REST is searched from the band's depth: validate_fit lowers the cap from 40 mm over its origin to 40 mm
        under it, and the human band lies 64-70 mm under the scalp's top (the seat origin), so the origin it gets is
        the seat's lowered by the band's depth less 25 mm (the tilt pivots about the cap's own opening, so the shift
        changes no pose, only where the search starts);
      * per tilt (CAP_TILTS) and size the best rest validate_fit finds over the shifts (supported, clear), then the
        daylight under the band from the cap's standard views with the scene (the head, the eyes, the glasses), the
        band's foot at the front over the brow line; the choice: supported and clear, the band's front foot nearest
        CAP_BAND_OVER_BROW over the brow (5 mm bins), the least daylight from dead front and back, then from all six
        views, the smallest largest gap.
    Returns (entry, conform, M, Wf, report) or (None, None, None, None, report)"""
    d = cap.dims()
    r_open = float(np.sqrt(d['rx_o'] * d['rz_o']))
    r_band = float(np.interp(band_depth, T_s[:, 0], T_s[:, 5]))
    s_fit = r_band / r_open
    # the LENGTH's size: the cap's oval (1.059 long : wide, the GDR crown's) is rounder than a head's section (a
    # cephalic index ~0.8: 1.25), its front gives nothing (the visor's root), its axes part by at most FIT_ANISO; at the
    # perimeter's size its front and back meet the head's 10 mm over the band (the first worn fits: the band's foot
    # +30 mm over the brow line at tilt 0); the size whose long axis reaches the head's at the band lets it down there,
    # its sides standing off the temples within the band's give
    rz_band = float(np.interp(band_depth, T_s[:, 0], T_s[:, 2]))
    s_len = max(s_fit, rz_band / (d['rz_o'] * (1.0 + cap.FIT_ANISO)))
    scales = tuple(np.round(np.linspace(s_fit, s_len * 1.01, 4), 5))
    up = R_s[:, 1]
    origin_c = np.asarray(o_s, np.float64) - up * (float(band_depth) - 0.025)
    Pi, Po, Nr, phs = cap.rim_stations()
    cands = []
    for tilt, s in [(t_, s_) for t_ in CAP_TILTS for s_ in scales]:
        entry, rows, conform = cap.validate_fit(prog, origin_c, R_s, T_s, L_c, avoid=avoid, species='human', scene=None,
                                                eyes=None, tilts=(tilt,), scales=(s,), shifts=CAP_SHIFTS,
                                                refine=False, log=lambda *a: None)
        if entry is None:
            log(f'[human_seats] cap tilt {tilt:.0f}, s {s:.4f}: no pose rests clear')
            continue
        S3 = entry['scale'] if np.ndim(entry['scale']) else [entry['scale']] * 3
        M = cap.pose_matrix(origin_c, R_s, entry['translation'], S3, entry['tilt_deg'])
        D = cap.conform_disp(L_c, conform['g'], conform['phs'], conform['hinge'])
        Wf = (np.asarray(L_c['V'], np.float64) + D) @ M[:3, :3].T + M[:3, 3]
        rim_w = (Po + conform['g'][:, None] * Nr) @ M[:3, :3].T + M[:3, 3]
        dl = cap.daylight(Wf, np.asarray(L_c['F']), scene[0], scene[1], M, rim_w, prog)
        front = int(np.argmin(np.abs(np.angle(np.exp(1j * np.asarray(phs))))))
        foot_over_brow = float(rim_w[front, 1] - brow_y)
        rep = dict(tilt_deg=float(entry['tilt_deg']), s=float(entry['s']), s_fit=round(s_fit, 5),
                   supported=bool(entry['supported']), clear_ok=bool(entry['clear_ok']),
                   daylight=[x[0] for x in dl], daylight_sum=int(sum(x[0] for x in dl)),
                   front_foot_over_brow_mm=round(foot_over_brow * 1e3, 1),
                   largest_gap_mm=round(entry['largest_gap'] * 1e3, 2), contact_share=entry['contact_share'],
                   sectors=entry['sectors'], span_deg=entry['span_deg'], dz_mm=round(entry['dz'] * 1e3, 1),
                   visor_min_mm=round(entry['visor_min'] * 1e3, 2),
                   avoid_mm={k: round(float(entry[k]) * 1e3, 2) for k in avoid if k in entry})
        log(f'[human_seats] cap tilt {tilt:.0f}: s {entry["s"]:.4f} (head {s_fit:.4f}), supported {entry["supported"]}, '
            f'daylight {rep["daylight"]}, the band foot {foot_over_brow * 1e3:+.1f} mm over the brow line in front, the '
            f'largest gap {entry["largest_gap"] * 1e3:.1f} mm, contact {entry["contact_share"] * 100:.0f} %, '
            f'{entry["sectors"]} sectors over {entry["span_deg"]:.0f} deg, shift {entry["dz"] * 1e3:+.0f} mm, '
            f'clearances {rep["avoid_mm"]} mm')
        cands.append((rep, entry, conform, M, Wf))
    if not cands:
        return None, None, None, None, dict(s_fit=s_fit, candidates=[])
    dead = lambda r: sum(r['daylight'][k] for k in cap.DEAD_VIEWS)
    key = lambda c: (not (c[0]['supported'] and c[0]['clear_ok']),
                     abs(c[0]['front_foot_over_brow_mm'] - CAP_BAND_OVER_BROW * 1e3) // 5, dead(c[0]),
                     c[0]['daylight_sum'], c[0]['largest_gap_mm'])
    rep, entry, conform, M, Wf = min(cands, key=key)
    report = dict(s_fit=round(s_fit, 5), s_len=round(s_len, 5), scales=list(scales), r_band_mm=round(r_band * 1e3, 2),
                  rz_band_mm=round(rz_band * 1e3, 2), r_open_mm=round(r_open * 1e3, 2),
                  origin_lowered_mm=round((float(band_depth) - 0.025) * 1e3, 1), chosen=rep,
                  candidates=[c[0] for c in cands],
                  rule='supported and clear; the band\'s front foot nearest '
                       f'{CAP_BAND_OVER_BROW * 1e3:.0f} mm over the brow line (5 mm bins); the least daylight from dead '
                       'front and dead back, then from all six standard views; the smallest largest gap')
    # the pose's translation re-expressed from the lowered search origin to the SEAT's (the runtime's wear() places the
    # cap at seat origin + R t): the same matrix, pose_matrix(o_s, R_s, t_seat, ...) == pose_matrix(origin_c, R_s, t, ...)
    t_seat = np.asarray(entry['translation'], np.float64) + R_s.T @ (origin_c - np.asarray(o_s, np.float64))
    entry = dict(entry, translation=t_seat.round(6).tolist(), translation_frame='seat origin',
                 origin_used=origin_c.round(6).tolist(), daylight=rep['daylight'],
                 front_foot_over_brow_mm=rep['front_foot_over_brow_mm'])
    # strict JSON for the glb's extras: validate_fit's front read is NaN without eyes
    entry = {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in entry.items()}
    return entry, conform, M, Wf, report


_GL_CACHE = {}


def _glasses_low(glasses):
    if 'low' not in _GL_CACHE:
        low = glasses.build_low(log=lambda *a: None)
        _GL_CACHE['low'] = (low, glasses.unwrap(low, 1024, log=lambda *a: None))
    return _GL_CACHE['low']
