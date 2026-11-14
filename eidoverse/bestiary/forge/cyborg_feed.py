"""THE FEED AS CABLES (C3d: the lead's C3d calls 1-3, PLAN.md 10-27; Skye 10-27: "i'm not sure baking down those wires on
the plate addition to flat looks great when you actually have geo wires on other parts of the cyborg mutation"): the feed
lines forge/cyborg.py lays (feed_layout: the routes C3b and C3c computed, unchanged) built as GEOMETRY, ONE CABLE SYSTEM
with the hose: every line is C5d's cable data (forge/cyborg_cable.py's format: runtime/cyborg_cable.js's mountCable
re-makes it every frame on the rendered skin), its sleeve the hose's tiling set, its collars and clamps copies of the mech
tentacle's own islands (no new texture set, no new island).

  THE CABLE    cyborg.feed_line over the LOW (the route's points on the canonical low: the body chart's exact rays, smoothed
               along the route over the low's facets and put back at its height: route_on_low; the low's smooth normals;
               the cable lying LIE_CLEAR over it), its riding points pushed back to their clearance where the low's facets
               still come nearer (push_off: spread along the line, eased at the rigid runs), resampled into RINGS piece by
               piece (at most 1.6 r apart and 0.10 rad of turn: the hose's resample; a piece's last two steps shared
               evenly when its last is short, ring_samples); SIDES sides; its UVs the hose's tile read at
               the cable's radius (u round, v the arc length over the tile's length at this radius: TILE_PERIODS braid
               periods of 1.25 x 2 pi r / 16)
  THE RINGS    RIGID in a frame: the run inside a collar's ferrule and the descent's first arc after it (the collar's:
               COLLAR_AT_JOINT of the skin's weights where its arc meets the landing, the rest those over its run), the
               run inside a clamp's band, the plunge under the skin, each a 'blend' frame (the skin's weights at its site,
               the hose's plate fitting's rule; the hardware skinned on the same weights moves with its rings exactly);
               every other ring ANCHORED on the skin as cyborg_cable.py anchors the hose's (Phong's projection onto the
               bind skin, its offset in the anchor's frame, its contact points round its lower half, its rest LIFT
               over its contact), drawn toward a rigid run's frame within
               CLAMP_BLEND r of it (ring_blend, weight w), its anchor keeping 1 - w of its rest lift (a fitting can take
               the rings by it down to the skin). THE REST POSE EXACT (REST_EXACT): the anchoring places are those the
               runtime's relay lays onto the drawn rings (relay_inverse: across the cable) and each blended ring's
               strongest blend is aimed so the blends give its anchoring place back at rest, so the runtime's rest is
               the drawn cable to under 0.002 mm. THE LANDINGS FAIRED where a landing is a whole run between a collar's
               arc and a clamp (ring_fair, ring_fair_d: the runtime's relay draws them as the cubic Hermite between the
               two rigid rings, with their rest detail, never under the skin), so the swim's climb at the joint spreads
               along the landing. No free span: tried for the landings (C5d's inextensible Hermite), they buckled
               0.5 mm in the swim where the skin under them shortened 16 %; an anchored arc (blended toward the collar
               over the descent) shortened with the skin to a 7.1 mm bend in the film
  THE HARDWARE the COLLARS (C3e: the hose's plate fitting rebuilt CLOSED on its own texels, its ferrule leaned
               FERRULE_LEAN: a 12-gon boss whose wall runs down into the plate all the way round, one fan for its top, a
               10-gon ferrule capped at both ends; collar_mesh's notes) and the CLAMPS (the tentacle's segment-8 band and
               lug, scaled by r / rh, the lug on top, the saddle left out), skinned rigidly on their frames' weights,
               their UVs on the tentacle's islands: material 'mech_tentacle', shares 'mech_tentacle' (the runtime gives
               them the mounted tentacle's material), its maps carried so a look without the tentacle renders them
  THE ASSETS   per line a glb in the hose's form (one skinned mesh, its sleeve primitive; the cable's data in the extras
               bestiary.cable: the runtime mounts it as a cyborg 'feed' part down the hose's path, c05d_runtime.mjs reads
               it), the look's hardware one glb more (its record names every part's vertex range and each collar's rim),
               all in FEED_DIR (the official feed look's) or a build's own out_dir, with a record (cyborg_feed.json:
               the run, the inputs' sha1s, the LOOK it serves: feed_look)
  THE MOUNT    (C3e) a recipe whose cyborg section has a feed row mounts its lines and their hardware as 'feed' parts
               (recipe.resolve_cyborg_runtime, each carrying the look), and the assembly maps them to their glbs
               (recipe.runtime_assets -> feed_assets: the record's look checked, a stale build rebuilt from its run):
               patches/cyborg_c3e_recipe.md, staged

Read with numpy and scipy (warp's CPU device for the rays and the closest points).
"""
import math
import os

import numpy as np

from . import cyborg as CY
from . import cyborg_cable as CC
from . import cyborg_hose as CH
from . import cyborg_octopus as CO

REPO = CO.REPO
TAU = 2.0 * math.pi
SIDES = CH.SIDES
RING_STEP = 1.6             # x r: the rings' most spacing (the hose's resample)
RING_TURN = 0.10            # rad: their most turn per step (the hose's)
RIGID = ('fitA', 'arcA', 'arcB', 'fitB', 'plunge')
# one source for the numbers the high's occluders and the runtime share
assert abs(CY.FEED_C3D['lie_clear'] - CC.LIE_CLEAR) < 1e-12, 'cyborg.FEED_C3D lie_clear is not C5d\'s LIE_CLEAR'
assert abs(CY.FEED_C3D['fit_lean'] - CH.FERRULE_LEAN) < 1e-9, 'cyborg.FEED_C3D fit_lean is not the hose\'s FERRULE_LEAN'
FEED_DIR = os.path.join(REPO, 'work', 'bestiary', 'cyborg_c3', 'feed_glb')     # the feed look's cables (C3e: the
                            # official output, beside the C3 looks; a round's build passes its own out_dir)


class FeedContext:
    """what the feed's cables read, loaded once: the octopus (its glb's shared vertex set, skin and rig: the anchors'
    vertex indices and the frames' bone names are the runtime's), the look's plates and feed (a t10 run's
    cyborg_plates.pkl beside its low.npz), the body chart on the low, the mech tentacle and its islands (the hardware's
    source)"""

    def __init__(self, run_dir, oct_glb=CH.OCT_GLB, log=print):
        self.run_dir = run_dir
        self.oct_ = CO.Octopus(oct_glb, os.path.join(run_dir, 'low.npz'))
        self.rec = CY.load_plates(run_dir)
        assert self.rec is not None and self.rec['layout'].get('feed'), f'{run_dir}: no feed laid there'
        self.lay = self.rec['layout']
        self.fd = self.lay['feed']
        L = self.oct_.low
        self.low = dict(V=np.asarray(L['V'], np.float64), F=np.asarray(L['F'], np.int64), UV=L['UV'],
                        region=np.asarray(L['region']), face_set=np.asarray(L['face_set']).astype(str))
        self.chart = CY.body_chart(self.low, device='cpu')
        self.F_head = self.low['F'][self.low['face_set'] == 'head']
        self.mech = CO.Mech()
        self.I = CH.mech_islands()
        self.r8 = float(self.I['r8'])
        self.log = log
        self.inputs = feed_inputs(run_dir, oct_glb)


def feed_inputs(run_dir, oct_glb=CH.OCT_GLB):
    """what a feed build reads, by sha1 (its record's 'inputs'; feed_assets rebuilds a look when one changed): the
    octopus, the mech tentacle, the run's plates and feed, this module and cyborg.py; C5f (the C3e check's
    recommendation, the lead's call 11): the hose's module (the sleeve's tile, the ring layout), the cable's (the relay
    math the lines' data mirror), the tentacle's forge (cyborg_limb.py: the fitting and the clamp the hardware copies),
    its island index (mech_islands.json: the pieces collar_source reads) and the tentacle's maps the hardware embeds
    (C5-UV b re-stacked the tentacle under the same names at 09:18: only the glb's own sha1 caught it); stage 4 (the
    lead's call after the stage-3 check): cyborg_octopus.py, whose Octopus and Mech this build reads the octopus and the
    mech tentacle through (the hose's record keys it; this one did not, so stage 3's port change left the feed record
    current)"""
    here = os.path.dirname(os.path.abspath(__file__))
    tent = os.path.join(REPO, 'work', 'bestiary', 'cyborg_c5')
    return {os.path.basename(p_): CH._sha1(p_)[:12] for p_ in (
        oct_glb, CO.MECH_GLB, os.path.join(run_dir, 'cyborg_plates.pkl'), os.path.abspath(__file__),
        os.path.join(here, 'cyborg.py'), os.path.join(here, 'cyborg_hose.py'), os.path.join(here, 'cyborg_cable.py'),
        os.path.join(here, 'cyborg_limb.py'), os.path.join(here, 'cyborg_octopus.py'),
        os.path.join(REPO, 'work', 'bestiary', 'cyborg_c5b', 'mech_islands.json'))
        + tuple(os.path.join(tent, f'T_mech_tentacle_{k}.png') for k in ('albedo', 'normal', 'orm'))}


# ============================================================================================ the cable on the low
ROUTE_SIGMA = 2.0e-3        # the route's points and normals smoothed along it by a Gaussian of this (m): the low's facets
                            # turn a chart line a few degrees at every edge, and the cable drawn over them bent at the rings
                            # 3-7 mm (s06)
PUSH_SIGMA = 1.5e-3         # the push of the riding points back to their clearance spread along the line by a moving max
                            # over 2 of this and a Gaussian of this (m), eased to nothing over 2 of this at the rigid runs


def smooth_odd(Y, sig):
    """Y (n, ...) smoothed along its first axis by a Gaussian of sig samples, each end extended by its POINT reflection
    (Y(-i) = 2 Y(0) - Y(i)): the ends stay exactly where they are and keep their slope (a mirror, 'reflect', flattens the
    slope there and moves the end: it lifted the ports 0.23-0.50 mm and the sockets 0.57-0.64 mm off the low, s11)"""
    from scipy.ndimage import gaussian_filter1d
    Y = np.asarray(Y, np.float64)
    m = min(len(Y) - 1, int(math.ceil(4.0 * sig)))
    ext = np.concatenate([2.0 * Y[0] - Y[m:0:-1], Y, 2.0 * Y[-1] - Y[-2:-m - 2:-1]], axis=0)
    return gaussian_filter1d(ext, sig, axis=0, mode='nearest')[m:m + len(Y)]


def route_on_low(ctx, ln):
    """a line's route on the low, smoothed over the low's facets (ROUTE_SIGMA; smooth_odd, so the ports and the socket
    stay put with their ways), then put back at the low's height (the smoothing draws a curved route inside the low, a
    convex one by ~kappa sigma^2 / 2: the route's height off the low smoothed the same way and taken off along the
    normals, so the facets' own wobble stays out): (lam, the points, the normals, their arc lengths)"""
    lam, X = CY.feed_samples(ln, ctx.chart, 0.15e-3)
    Xc, fc, u, v = CH.skin_closest(ctx.oct_, X)
    N, _, _ = CH.skin_frames(ctx.oct_, fc, u, v)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Xc, axis=0), axis=1))])
    sig = ROUTE_SIGMA / max(float(s[-1]) / (len(s) - 1), 1e-9)
    Xs = smooth_odd(Xc, sig)
    Ns = smooth_odd(N, sig)
    Ns /= np.linalg.norm(Ns, axis=1, keepdims=True)
    V, F = ctx.low['V'], ctx.F_head
    sd, _ = CO.point_tri_near(Xs, V[F[:, 0]], V[F[:, 1]], V[F[:, 2]], k=32)
    Xs = Xs - smooth_odd(sd, sig)[:, None] * Ns
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Xs, axis=0), axis=1))])
    return lam, Xs, Ns, s


def push_off(ctx, P, piece, rho):
    """a centreline's RIDING points (the descents, the lying run, the clamps' bands; the ferrules' runs and the plunge
    held) pushed out along the low's normals to the cable's clearance rho where they come nearer: the push spread along
    the line (PUSH_SIGMA: a moving max, then a Gaussian) and eased to nothing at each rigid run's end (a smoothstep over 2
    PUSH_SIGMA: no turn at the joint; a push on one ring alone kinked the run there, 9.8-12.9 deg, s06); three rounds.
    Returns (the points, what each still lacks of rho)"""
    from scipy.ndimage import gaussian_filter1d, maximum_filter1d
    V, F = ctx.low['V'], ctx.F_head
    A_, B_, C_ = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    P = np.array(P, np.float64)
    ride = np.array([str(p_) not in RIGID for p_ in piece])
    t = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    t_rig = t[~ride]
    far = (np.abs(t[:, None] - t_rig[None]).min(1) if len(t_rig) else np.full(len(t), np.inf)) / (2.0 * PUSH_SIGMA)
    far = np.clip(far, 0.0, 1.0)
    ease = np.where(ride, far * far * (3.0 - 2.0 * far), 0.0)
    dt = 0.05e-3
    tg = np.arange(0.0, t[-1] + dt, dt)
    for _ in range(3):
        sd, ti = CO.point_tri_near(P, A_, B_, C_, k=32)
        need = np.where(ride, np.maximum(rho - sd, 0.0), 0.0)
        if need.max() < 1e-7:
            break
        g = maximum_filter1d(np.interp(tg, t, need), 2 * int(math.ceil(2.0 * PUSH_SIGMA / dt)) + 1, mode='nearest')
        push = np.interp(t, tg, gaussian_filter1d(g, PUSH_SIGMA / dt, mode='nearest')) * ease
        nrm = np.cross(B_[ti] - A_[ti], C_[ti] - A_[ti])
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        P = P + push[:, None] * nrm
    sd, _ = CO.point_tri_near(P, A_, B_, C_, k=32)
    return P, np.where(ride, np.maximum(rho - sd, 0.0), 0.0)


def ring_samples(P, piece, r):
    """the centreline's RINGS, piece by piece (each piece resampled at most RING_STEP r apart and RING_TURN of turn, its
    first point shared with the piece before; a ring two pieces share belongs to the rigid one, so every rigid run holds
    its two end rings; a piece's last two steps shared evenly when its last is under 0.7 of the one before: the greedy
    steps left one as short as 0.42 mm by a rigid run's end, where a 0.06 mm move of the skin read a 4.4 mm bend, c03d
    K6, s15): (rings (m, 3), their pieces (m,))"""
    names = [str(p_) for p_ in piece]
    cuts = [0] + [i for i in range(1, len(P)) if names[i] != names[i - 1]] + [len(P)]
    out, lab = [], []
    for a, b in zip(cuts[:-1], cuts[1:]):
        seg = P[a:min(b + 1, len(P))]
        if len(seg) < 2:
            seg = P[max(a - 1, 0):a + 1]
        sg_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(seg, axis=0), axis=1))])
        Q, t = CH.resample(seg, RING_STEP * r, RING_TURN)
        if len(Q) >= 3 and t[-1] - t[-2] < 0.7 * (t[-2] - t[-3]):
            tm = 0.5 * (t[-3] + t[-1])
            Q[-2] = [np.interp(tm, sg_, seg[:, d_]) for d_ in range(3)]
        if out:
            Q = Q[1:]
            if rigid_label(names[a]):
                lab[-1] = names[a]                       # the shared ring: the rigid run's own end
        if not len(Q):
            continue
        out.append(Q)
        lab += [names[a]] * len(Q)
    return np.vstack(out), np.array(lab, dtype=object)


def rigid_label(p_):
    return p_ in RIGID or p_.startswith('clamp')


def build_line(ctx, li, ln, log=print):
    """ONE LINE'S CABLE on the low (the notes above): its rings and their pieces, its collars, clamps and socket, ready for
    cable_data; the rings riding the skin relaxed off the low's facets with the rigid runs held, each clamp then re-seated
    on the relaxed line (its band on the line's tangent at its place, its rings on the band's axis)"""
    r = 0.5 * ctx.fd['params']['D']
    c = CY.FEED_C3D['lie_clear']
    lam, X, N, s = route_on_low(ctx, ln)
    geo = CY.feed_line(ln, X, N, s, np.full(len(s), r + c), np.zeros(len(s)), r, lam)
    # the riding points pushed back to the cable's clearance off the low's own triangles where the smoothed route left
    # them nearer (push_off: spread, eased at the rigid runs), THEN the rings (their turn cap sees the push's bends)
    P, lack = push_off(ctx, geo['P'], geo['piece'], r + c)
    Q, lab = ring_samples(P, geo['piece'], r)
    # the clamps re-seated on the relaxed line
    s_q = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
    clamps = []
    for cl in geo['clamps']:
        m = lab == f'clamp{cl["k"]}'
        if not m.any():
            raise CY.CyborgError('cyborg.feed', f'line {li}: clamp {cl["k"]} took no ring')
        k_ = np.nonzero(m)[0]
        sc = 0.5 * (s_q[k_[0]] + s_q[k_[-1]])
        Cc = np.array([np.interp(sc, s_q, Q[:, d_]) for d_ in range(3)])
        T = np.array([np.interp(sc + 0.5e-3, s_q, Q[:, d_]) - np.interp(sc - 0.5e-3, s_q, Q[:, d_]) for d_ in range(3)])
        _, fc, u, v = CH.skin_closest(ctx.oct_, Cc[None])
        Nc, _, _ = CH.skin_frames(ctx.oct_, fc, u, v)
        cl2 = CY.feed_clamp(Cc, T, Nc[0], r)
        cl2.update(k=cl['k'], seam=cl['seam'], why=cl['why'])
        # its rings on the band's axis (rigid in its frame: the band holds the cable straight)
        for q in k_:
            a = float((Q[q] - Cc) @ cl2['x'])
            Q[q] = Cc + a * cl2['x']
        clamps.append(cl2)
    s_q = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
    rb, turn = CY.feed_bends(Q)
    log(f'[feed] line {li} ({ln["kind"]}): {len(Q)} rings ({int(sum(rigid_label(p_) for p_ in lab))} rigid), '
        f'{s_q[-1] * 1e3:.1f} mm; at rest the least bend {rb * 1e3:.2f} mm, the largest turn {turn:.2f} deg; the riding '
        f'centreline lacks at most {lack.max() * 1e3:.3f} mm of its clearance')
    return dict(li=li, kind=ln['kind'], r=r, rings=Q, piece=lab, collars=geo['collars'], clamps=clamps,
                socket=geo['socket'], s=s_q, bend_min=rb, turn_max=turn, lack=float(lack.max()),
                route=dict(X=X, N=N, s=s, lam=lam))


def site_weights(ctx, P):
    """the skin's weights at the low's closest point to P: (bone names, weights): its four heaviest, normalised"""
    _, fc, u, v = CH.skin_closest(ctx.oct_, np.asarray(P, np.float64)[None])
    _, J, W = CH.skin_frames(ctx.oct_, fc, u, v)
    nm = ctx.oct_.rig.jnames
    keep = W[0] > 0
    return [nm[int(j)] for j in J[0][keep]], [float(w) for w in W[0][keep] / W[0][keep].sum()]


def run_weights(ctx, P):
    """the skin's weights over points P (k, 3): their sites' weights averaged, the four heaviest bones, normalised, in
    order of weight: (bone names, weights)"""
    acc = {}
    for p_ in np.atleast_2d(np.asarray(P, np.float64)):
        bn, bw = site_weights(ctx, p_)
        for b_, w_ in zip(bn, bw):
            acc[b_] = acc.get(b_, 0.0) + w_
    top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
    s_ = sum(w_ for _, w_ in top)
    return [b_ for b_, _ in top], [float(w_ / s_) for _, w_ in top]


REST_EXACT = True           # the runtime's rest pose the drawn rings (relay_inverse; the blends' aims in cable_data)
ARCS = ('arcA', 'arcB')     # a collar's descent arc (rigid in the collar's frame)
LANDINGS = ('humpA', 'humpB')   # the landing that takes the cable from it onto the plate
FAIR_LIE = 2                # the lying rings past a landing faired with it (C5d's: the two lying rings next to each ramp)
COLLAR_AT_JOINT = 0.6       # a collar's frame: this share of the skin's weights at its arc's joint with the landing, the
                            # rest the weights over its rigid run (cable_data's notes; s19 and c03d K5 / K6, 10-28)
FAIR_CLEAR = 0.05e-3        # runtime/cyborg_cable.js FAIR_CLEAR: a faired ring kept this far over its contact (c03d K1
                            # reads the runtime's own constant against this)


def anchored_runs(kind):
    """the runs the runtime's relay lays: each run of three or more anchored rings, (first, last)"""
    runs, N_, i = [], len(kind), 0
    while i < N_:
        if kind[i] != 1:
            i += 1
            continue
        j = i
        while j + 1 < N_ and kind[j + 1] == 1:
            j += 1
        if j - i >= 2:
            runs.append((i, j))
        i = j + 1
    return runs


def relay_rest(P, runs, frac):
    """runtime/cyborg_cable.js relay at rest on the places P: each run's inner places smoothed once ([1 2 1] / 4, its
    two end rings held), then its inner rings laid at their rest arc fractions frac along the smoothed run"""
    out = np.array(P, np.float64)
    for i, j in runs:
        RP = out[i:j + 1].copy()
        RP[1:-1] = 0.25 * (RP[:-2] + 2.0 * RP[1:-1] + RP[2:])
        RC = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(RP, axis=0), axis=1))])
        for k in range(i + 1, j):
            out[k] = [np.interp(frac[k] * RC[-1], RC, RP[:, d_]) for d_ in range(3)]
    return out


def relay_inverse(Q, kind):
    """the ANCHORING PLACES whose relay lays the drawn rings Q at rest (relay_rest): each run's inner places moved
    ACROSS the cable against what the pass does to them until it gives Q (the along-cable placement the pass's rest
    fractions keep; moved along it too, the places went up to 7 mm off the drawn rings on line 0's lying run, where
    uneven steps draw the [1 2 1] / 4 pass along the cable). Laid on the drawn rings themselves, the pass drew a
    landing's inner rings toward its chord (+0.015 mm on line 4's far landing) and its last ring by the collar's arc
    bent to 7.35 mm at rest, 6.9 in the rest motion (c03d K6, s15, 10-27). Returns (the places, the rest's residual
    (m) across the cable and along it)"""
    Q = np.asarray(Q, np.float64)
    runs = anchored_runs(kind)
    frac = np.zeros(len(Q))
    inner = np.zeros(len(Q), bool)
    for i, j in runs:
        cs_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q[i:j + 1], axis=0), axis=1))])
        frac[i:j + 1] = cs_ / cs_[-1]
        inner[i + 1:j] = True
    T = np.zeros_like(Q)
    T[1:-1] = Q[2:] - Q[:-2]
    T[0], T[-1] = Q[1] - Q[0], Q[-1] - Q[-2]
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    P = Q.copy()
    for _ in range(200):
        R = relay_rest(P, runs, frac) - Q
        Rx = R - (R * T).sum(1, keepdims=True) * T
        Rx[~inner] = 0.0
        if np.abs(Rx).max() < 1.0e-8:
            break
        P -= Rx
    R = relay_rest(P, runs, frac) - Q
    along = (R * T).sum(1)
    return P, float(np.linalg.norm(R - along[:, None] * T, axis=1).max()), float(np.abs(along).max())


def cable_data(ctx, B, log=print):
    """THE CABLE'S DATA for one built line (build_line's B) in C5d's format (forge/cyborg_cable.py cable_data's keys, as
    runtime/cyborg_cable.js mountCable reads them), built in the BIND pose (the skin matrices the identity: a rigid ring's
    place in its 'blend' frame is its bind position): frames (each collar, each clamp, the socket: 'blend' at its site),
    anchors and skin_verts, ring_kind / ring_ref / ring_loc, the contacts (ring_contact_start, ring_contact, rho), the
    rest lifts (a blended ring's the skin's share), the runs' arc fractions, the blends by the rigid runs, no span, e1_0
    (the first collar's normal in its frame), tan_w. Returns (data, the rings' skin weights for the sleeve's fallback
    skin)"""
    oct_ = ctx.oct_
    r = B['r']
    Q, lab = B['rings'], B['piece']
    N_ = len(Q)
    V = ctx.low['V']
    nV = len(V)
    F = ctx.F_head
    Nb = oct_.N[:nV]
    import hashlib
    key = ('feed_bind', hashlib.sha1(np.ascontiguousarray(V).tobytes()).hexdigest(),
           hashlib.sha1(np.ascontiguousarray(F).tobytes()).hexdigest())
    anchors, skin_v, aP = [], {}, []

    def add_anchors(tri, bc):
        out = []
        for t_, b_ in zip(tri, bc):
            for v_ in t_:
                skin_v.setdefault(int(v_), len(skin_v))
            anchors.append([skin_v[int(t_[0])], skin_v[int(t_[1])], skin_v[int(t_[2])], float(b_[0]), float(b_[1]),
                            float(b_[2])])
            aP.append((np.asarray(b_, np.float64)[:, None] * V[np.asarray(t_)]).sum(0))
            out.append(len(anchors) - 1)
        return np.array(out, np.int64)

    def anchor(P):
        """anchors under points P on the bind skin: Phong's projection (the foot whose smooth normal points at the point,
        from the closest point, a few casts back along the normal: cyborg_cable.py's), its triangle, barycentrics and
        frame. Returns (indices, feet, e1, n, e2)"""
        P = np.asarray(P, np.float64)
        fc, bc, X = CC._closest(key, V, F, P)
        for _ in range(8):
            tri = F[fc]
            n_ = (bc[:, :, None] * Nb[tri]).sum(1)
            n_ /= np.linalg.norm(n_, axis=1, keepdims=True)
            hit, fh = CH._ray_mesh(key + ('rays',), V, F, P + 1.0e-6 * n_, -n_, 0.08)
            ok = (fh >= 0) & np.isfinite(hit).all(1)
            if not ok.any():
                break
            bc2 = CC.bary(hit[ok], V[F[fh[ok], 0]], V[F[fh[ok], 1]], V[F[fh[ok], 2]])
            moved = np.linalg.norm(hit[ok] - X[ok], axis=1)
            bc2 = np.clip(bc2, 0.0, 1.0)
            fc[ok], bc[ok], X[ok] = fh[ok], bc2 / bc2.sum(1, keepdims=True), hit[ok]
            if moved.max() < 1.0e-9:
                break
        tri = F[fc]
        out = add_anchors(tri, bc)
        X = (bc[:, :, None] * V[tri]).sum(1)
        n_ = (bc[:, :, None] * Nb[tri]).sum(1)
        n_ /= np.linalg.norm(n_, axis=1, keepdims=True)
        e1, n, e2 = CC.anchor_frame(V[tri[:, 0]], V[tri[:, 1]], n_)
        return out, X, e1, n, e2
    # ---------------------------------------------------------------- the frames: 'blend' at each hardware's site. A
    # COLLAR's (its ferrule's run and its descent's rigid arc, 5-7 mm of cable off the port) leans to the skin's weights
    # where its arc meets the landing, the joint the cable has to keep (COLLAR_AT_JOINT of them, the rest the weights
    # over its rigid run). Line 4 crosses from mantle_2 to mantle_1: on the run's weights alone (mantle_2 0.77 on its
    # first collar; 0.70 at the arc's end, 0.67 -> 0.62 under the landing) the swim lifted the skin under the landing
    # 0.1-0.15 mm against the arc, a 5.4 mm bend at the joint for 22 frames of each stroke (c03d K6, s19); wholly on the
    # joint's (with the landings faired, below) the swim held 6.3 deg and 8.0 mm but the far collar's boss foot, the
    # port's end of the frame, rose 0.018 mm out of the skin (K5); on the port's weights alone the arc's far end left its
    # skin, 0.22 mm in the swim (s15). At 0.6: the swim 7.0 deg and 8.0 mm (the arc's own bend), the foot 0.030 mm under
    frames, frame_w = [], []
    col_f, cl_f = [], []
    lab_s = np.asarray(lab, dtype=str)
    runs_of = ({0: ('fitA', 'arcA'), len(B['collars']) - 1: ('arcB', 'fitB')} if len(B['collars']) > 1 else
               {0: ('fitA', 'arcA')})
    for k_c, col in enumerate(B['collars']):
        on_run = np.isin(lab_s, runs_of[k_c])
        k_a = np.nonzero(lab_s == runs_of[k_c][1 if k_c == 0 else 0])[0]
        if not len(k_a):
            bn, bw = site_weights(ctx, col['S'])
        else:
            wd = {}
            for share, (bn_, bw_) in ((COLLAR_AT_JOINT, run_weights(ctx, Q[[k_a.max() if k_c == 0 else k_a.min()]])),
                                      (1.0 - COLLAR_AT_JOINT, run_weights(ctx, Q[on_run]))):
                for b_, w_ in zip(bn_, bw_):
                    wd[b_] = wd.get(b_, 0.0) + share * w_
            top = sorted(wd.items(), key=lambda kv: -kv[1])[:4]
            s_ = sum(w_ for _, w_ in top)
            bn, bw = [b_ for b_, _ in top], [float(w_ / s_) for _, w_ in top]
        col_f.append(len(frames))
        frames.append(dict(kind='blend', bones=bn, w=bw))
        frame_w.append(dict(zip(bn, bw)))
    for cl in B['clamps']:
        bn, bw = site_weights(ctx, cl['C'])
        cl_f.append(len(frames))
        frames.append(dict(kind='blend', bones=bn, w=bw))
        frame_w.append(dict(zip(bn, bw)))
    sock_f = None
    if B['socket'] is not None:
        bn, bw = site_weights(ctx, B['socket']['E'])
        sock_f = len(frames)
        frames.append(dict(kind='blend', bones=bn, w=bw))
        frame_w.append(dict(zip(bn, bw)))
    # ---------------------------------------------------------------- the rings' kinds
    kind = np.full(N_, 1)
    ref = np.zeros(N_, np.int64)
    loc = np.zeros((N_, 3))
    fit_end = {'fitA': col_f[0], 'arcA': col_f[0], 'arcB': col_f[-1], 'fitB': col_f[-1]}
    for i, p_ in enumerate(lab):
        if p_ in fit_end:
            kind[i], ref[i] = 0, fit_end[p_]
        elif p_ == 'plunge':
            kind[i], ref[i] = 0, sock_f
        elif p_.startswith('clamp'):
            kind[i], ref[i] = 0, cl_f[int(p_[5:])]
        if kind[i] == 0:
            loc[i] = Q[i]                                     # the bind: every skin matrix the identity
    # (the anchors under the drawn rings; the anchoring places those whose relay gives the drawn rings at rest:
    # relay_inverse)
    ia = np.nonzero(kind == 1)[0]
    ai, X, e1, n, e2 = anchor(Q[ia])
    ref[ia] = ai
    Qa, res_x, res_t = relay_inverse(Q, kind) if REST_EXACT else (Q, 0.0, 0.0)
    loc[ia] = np.column_stack([((Qa[ia] - X) * e1).sum(1), ((Qa[ia] - X) * n).sum(1), ((Qa[ia] - X) * e2).sum(1)])
    # ---------------------------------------------------------------- the contacts and the rest lifts (C5d s22)
    Tl = np.zeros_like(Q)
    Tl[1:-1] = Q[2:] - Q[:-2]
    Tl[0], Tl[-1] = Q[1] - Q[0], Q[-1] - Q[-2]
    Tl /= np.linalg.norm(Tl, axis=1, keepdims=True)
    rho = r + CC.LIE_CLEAR
    th_ = np.radians(np.asarray(CC.LIP_DEG, np.float64))
    u_ = n - (n * Tl[ia]).sum(1, keepdims=True) * Tl[ia]
    u_ /= np.linalg.norm(u_, axis=1, keepdims=True)
    w_ = np.cross(Tl[ia], u_)
    org = np.repeat(Qa[ia], len(th_), 0)
    dirs = (-np.cos(th_)[None, :, None] * u_[:, None] + np.sin(th_)[None, :, None] * w_[:, None]).reshape(-1, 3)
    hit, fh = CH._ray_mesh(key + ('rays',), V, F, org, dirs, CC.LIP_REACH * r)
    okh = (fh >= 0) & np.isfinite(hit).all(1)
    lip_a = np.full(len(org), -1, np.int64)
    if okh.any():
        tri_h = F[fh[okh]]
        bc_h = np.clip(CC.bary(hit[okh], V[tri_h[:, 0]], V[tri_h[:, 1]], V[tri_h[:, 2]]), 0.0, 1.0)
        bc_h /= bc_h.sum(1, keepdims=True)
        lip_a[okh] = add_anchors(tri_h, bc_h)
    lip_a = lip_a.reshape(len(ia), len(th_))
    c_count = np.zeros(N_, np.int64)
    c_list = []
    lift = np.zeros(N_)
    held = 0
    for q, i_ in enumerate(ia):
        lst = [int(ai[q])] + [int(x_) for x_ in lip_a[q] if x_ >= 0]
        c_count[i_] = len(lst)
        c_list += lst
        Bq = Qa[i_] - loc[i_, 1] * n[q]
        hc = -np.inf
        for a2 in lst:
            d_ = Bq - aP[a2]
            dn_ = float(d_ @ n[q])
            disc = dn_ * dn_ - float(d_ @ d_) + rho * rho
            if disc >= 0.0:
                hc = max(hc, -dn_ + math.sqrt(disc))
        if not np.isfinite(hc):
            hc = rho
        held += int(hc > math.sqrt(max(rho * rho - loc[i_, 0] ** 2 - loc[i_, 2] ** 2, 0.0)) + 1e-6)
        lift[i_] = loc[i_, 1] - hc
    c_start = np.concatenate([[0], np.cumsum(c_count)])
    # ---------------------------------------------------------------- the runs' arc fractions
    frac_r = np.zeros(N_)
    i = 0
    while i < N_:
        if kind[i] != 1:
            i += 1
            continue
        j_ = i
        while j_ + 1 < N_ and kind[j_ + 1] == 1:
            j_ += 1
        if j_ - i >= 2:
            cs_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q[i:j_ + 1], axis=0), axis=1))])
            frac_r[i:j_ + 1] = cs_ / cs_[-1]
        i = j_ + 1
    # ---------------------------------------------------------------- the blends by the rigid runs (cyborg_cable's rule:
    # an anchored ring within CLAMP_BLEND r of a rigid run's end drawn toward where that run's frame carries it, by
    # w = 1 - smoothstep(d / CLAMP_BLEND r), d along the cable at rest)
    blend = []
    s = B['s']
    for f_ in sorted(set(int(x_) for x_ in ref[kind == 0])):
        rc = np.nonzero((kind == 0) & (ref == f_))[0]
        for e_, sgn in ((rc.min(), -1), (rc.max(), 1)):
            q = e_ + sgn
            while 0 <= q < N_ and kind[q] == 1 and abs(s[q] - s[e_]) < CC.CLAMP_BLEND * r:
                uq = abs(s[q] - s[e_]) / (CC.CLAMP_BLEND * r)
                wq = 1.0 - uq * uq * (3.0 - 2.0 * uq)
                blend.append([int(q), int(f_), *map(float, Qa[q]), float(wq)])
                q += sgn
    # ---------------------------------------------------------------- the blended rings' lifts: the skin's share only
    # (the runtime draws a blended ring toward its frame's target by w and never lower than its anchored place, its
    # contact plus its lift: ringsFixed. A landing's rings stand up to 0.3 mm over the skin; held at their whole lift,
    # they could follow the collar's frame up but never down, and where the skin rose against the collar (the mantle's
    # weights change along line 4: mantle_1 0.83 at its far port, 0.69 six mm on) the cable folded at the arc's end,
    # 30 deg in the swim, c03d K6, s15. So the anchor keeps 1 - w of a ring's rest lift (its floor its contact plus
    # that, w its strongest blend): in motion it follows the frame by w down to its contact; at rest it stands w (1 - w)
    # of its lift under its drawn place (at most 0.015 mm; aiming its first blend that much higher put it exactly there
    # but bent line 3's far landing to 6.8-7.1 mm in the film, against 7.7: c03d K6, 10-27). A ring pressed into a crease
    # at rest (a negative lift) keeps it)
    w_bl = np.zeros(N_)
    lift_drawn = lift.copy()
    for b_ in blend:
        w_bl[b_[0]] = max(w_bl[b_[0]], b_[5])
    lift = np.where(lift > 0.0, lift * (1.0 - w_bl), lift)
    # (the rest pose exact, REST_EXACT: each blended ring's strongest blend aimed over its anchoring place by what its
    # anchor gave up, so the blends before it and it bring the ring back onto that place (along the anchor's normal:
    # at rest every move is along it), the blends after it then aimed at where it already stands; the relay's pass
    # then lays the anchoring places onto the drawn rings)
    aim = np.zeros(N_)
    if REST_EXACT:
        pos = {int(i_): q for q, i_ in enumerate(ia)}
        by_ring = {}
        for k_b, b_ in enumerate(blend):
            by_ring.setdefault(int(b_[0]), []).append(k_b)
        for i_, ks in by_ring.items():
            q = pos[i_]
            k_s = max(ks, key=lambda k_b: blend[k_b][5])
            y = float(lift[i_] - lift_drawn[i_])                     # the anchor's place off the anchoring place
            for k_b in ks[:ks.index(k_s)]:
                y += blend[k_b][5] * (0.0 - y)
            w_s = blend[k_s][5]
            c_ = -y * (1.0 - w_s) / w_s
            blend[k_s][2:5] = [float(x_) for x_ in Qa[i_] + c_ * n[q]]
            aim[i_] = c_
    # ---------------------------------------------------------------- the FAIRED rings (C5d's ring_fair: the runtime's
    # relay fairStretch re-draws each stretch of them as the cubic Hermite between the held control points either side,
    # along the tangents beyond them, plus each ring's rest detail ring_fair_d, never under its contact by FAIR_CLEAR):
    # every LANDING in a relay run by a collar's rigid arc, and FAIR_LIE lying rings past it (the whole run when it ends
    # on a clamp sooner). Anchored ring by ring, a landing followed the skin while the arc held the collar's frame:
    # where the mantle's weights change along line 4 (mantle_2 0.77 under its first collar's frame, 0.67 -> 0.62 under
    # its landing) the swim lifted the skin 0.1-0.15 mm under the landing against the arc and the cable folded at the
    # joint, 10.5 deg and a 5.3 mm bend for 22 frames of each 60-frame stroke at ring 8 (its far landing 6.2 mm at ring
    # 16), c03d K6, s19. Faired, the climb spreads from the arc's end to the next held point as a stiff cable takes it.
    sm_ = np.zeros(N_)
    for i0, j0 in anchored_runs(kind):
        for end, step, nb in ((i0, 1, i0 - 1), (j0, -1, j0 + 1)):
            if not (0 <= nb < N_ and lab[nb] in ARCS):
                continue
            k = end
            while i0 <= k <= j0 and lab[k] in LANDINGS:
                sm_[k] = 1.0
                k += step
            for _ in range(FAIR_LIE):
                if i0 <= k <= j0:
                    sm_[k] = 1.0
                    k += step
        # (only a run that is all landing between two rigid pieces: a dive's landing goes on into its long lying run,
        # whose rings ride the skin; faired there, line 1's lying rings stood up to 0.048 mm under the floor at rest, the
        # anchoring places relay_inverse lifts over a curved run, and the runtime would have lifted them)
        if not sm_[i0:j0 + 1].all():
            sm_[i0:j0 + 1] = 0.0
    # and each faired ring's REST DETAIL (cyborg_cable.py's, term by term as fairStretch draws it at rest): its control
    # point's offset, in its anchor's frame, off its stretch's rest Hermite; the control points at rest those the relay
    # reads there (the rigid rings' bind places, the anchored rings' anchoring places: the blends give them back at rest)
    # smoothed RUN_SMOOTH times. With it the fairing is the identity at rest (relay_inverse's rest pose stands) and a
    # pose bends each stretch as its Hermite bends. (The floor at rest, each faired control point's height over its
    # contact less min(FAIR_CLEAR, its lift), logged: under zero the runtime would lift it there)
    a_fr = {int(i_): (e1[q], n[q], e2[q]) for q, i_ in enumerate(ia)}
    fair_d = np.zeros((N_, 3))
    floor_rest = np.inf
    for i0, j0 in anchored_runs(kind):
        if not sm_[i0:j0 + 1].any():
            continue
        pre = 0
        while pre < 2 and i0 - pre - 1 >= 0 and kind[i0 - pre - 1] == 0:
            pre += 1
        post = 0
        while post < 2 and j0 + post + 1 < N_ and kind[j0 + post + 1] == 0:
            post += 1
        idx = np.arange(i0 - pre, j0 + post + 1)
        m_ = j0 - i0 + 1
        RP = np.where((kind[idx] == 1)[:, None], Qa[idx], Q[idx])
        for _ in range(CC.RUN_SMOOTH):
            T_ = RP.copy()
            RP[pre + 1:pre + m_ - 1] = 0.25 * (T_[pre:pre + m_ - 2] + 2.0 * T_[pre + 1:pre + m_ - 1] + T_[pre + 2:pre + m_])
        M_ = len(idx)
        k = 1
        while k <= M_ - 2:
            if not (kind[idx[k]] == 1 and sm_[idx[k]] > 0):
                k += 1
                continue
            k2 = k
            while k2 + 1 <= M_ - 2 and kind[idx[k2 + 1]] == 1 and sm_[idx[k2 + 1]] > 0:
                k2 += 1
            A_, B_ = k - 1, k2 + 1
            u0_ = RP[A_] - RP[A_ - 1] if A_ >= 1 else RP[B_] - RP[A_]
            u1_ = RP[B_ + 1] - RP[B_] if B_ <= M_ - 2 else RP[B_] - RP[A_]
            u0_, u1_ = u0_ / np.linalg.norm(u0_), u1_ / np.linalg.norm(u1_)
            cs_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(RP[A_:B_ + 1], axis=0), axis=1))])
            L_ = float(np.linalg.norm(RP[B_] - RP[A_]))
            for q_ in range(1, B_ - A_):
                tt = cs_[q_] / cs_[-1]
                Hq = ((2 * tt ** 3 - 3 * tt ** 2 + 1) * RP[A_] + (tt ** 3 - 2 * tt ** 2 + tt) * L_ * u0_
                      + (-2 * tt ** 3 + 3 * tt ** 2) * RP[B_] + (tt ** 3 - tt ** 2) * L_ * u1_)
                ring = int(idx[A_ + q_])
                e1f, nf, e2f = a_fr[ring]
                dq = RP[A_ + q_] - Hq
                fair_d[ring] = [dq @ e1f, dq @ nf, dq @ e2f]
                cc_ = Qa[ring] - lift_drawn[ring] * nf
                floor_rest = min(floor_rest, float((RP[A_ + q_] - cc_) @ nf) - min(FAIR_CLEAR, float(lift[ring])))
            k = k2 + 2
    # ---------------------------------------------------------------- the rings' skin weights (the sleeve's fallback skin)
    ring_w = []
    for i in range(N_):
        if kind[i] == 0:
            ring_w.append(frame_w[int(ref[i])])
        else:
            bn, bw = site_weights(ctx, aP[int(ref[i])])
            ring_w.append(dict(zip(bn, bw)))
    col0 = B['collars'][0]
    data = dict(version=1, r=float(r), sides=int(SIDES), rings=int(N_), skin='octopus_head',
                skin_verts=[int(v_) for v_ in sorted(skin_v, key=skin_v.get)],
                anchors=[float(x_) if q % 6 >= 3 else int(x_) for a_ in anchors for q, x_ in enumerate(a_)],
                frames=frames, ring_kind=[int(k_) for k_ in kind], ring_ref=[int(x_) for x_ in ref],
                ring_loc=[float(x_) for x_ in loc.ravel()], ring_blend=blend,
                ring_frac=[float(x_) for x_ in frac_r], spans=[],
                rho=float(rho), ring_contact_start=[int(x_) for x_ in c_start], ring_contact=c_list,
                ring_lift=[float(x_) for x_ in lift], ring_fair=[float(x_) for x_ in sm_],
                ring_fair_d=[float(x_) for x_ in fair_d.ravel()],
                e1_0=[int(col_f[0]), *map(float, col0['y'])], tan_w=1.0, contacts=[])
    dl = (lift_drawn - lift)[w_bl > 0]
    dq = np.linalg.norm(Qa - Q, axis=1)
    log(f'[feed] line {B["li"]}: {N_} rings ({int((kind == 0).sum())} rigid in {len(frames)} blend frames, '
        f'{int((kind == 1).sum())} anchored), {len(anchors)} anchors on {len(skin_v)} skin vertices, '
        f'{len(c_list)} contact points ({held} rings held by a lip at rest), {len(blend)} blends on '
        f'{int((w_bl > 0).sum())} rings (their anchors\' lifts the skin\'s share: at most {dl.max(initial=0.0) * 1e3:.3f} mm '
        f'off; ' + (f'the rest exact: the anchoring places at most {dq.max() * 1e3:.3f} mm off the drawn rings, the '
                    f'strongest blends aimed at most {aim.max(initial=0.0) * 1e3:.3f} mm over them, the relay at rest '
                    f'{res_x * 1e3:.4f} mm across the cable and {res_t * 1e3:.4f} mm along it off the drawn rings)'
                    if REST_EXACT else
                    f'the rest pose at most {float((np.maximum(lift_drawn, 0.0) * w_bl * (1.0 - w_bl)).max(initial=0.0)) * 1e3:.3f} '
                    f'mm under its drawn rings)'))
    if sm_.any():
        log(f'[feed] line {B["li"]}: {int(sm_.sum())} rings faired (rings '
            f'{", ".join(str(int(i_)) for i_ in np.nonzero(sm_)[0])}: the landings by the arcs and up to {FAIR_LIE} lying '
            f'rings past them), their rest detail at most {np.abs(fair_d).max() * 1e3:.3f} mm off their stretches\' '
            f'Hermites; the floor at rest {floor_rest * 1e3:+.4f} mm (under zero the runtime lifts a faired ring at rest)')
    return data, ring_w


# ============================================================================================ the meshes
def sleeve_mesh(B, data, ring_w):
    """the SLEEVE in the bind pose as the runtime frames it (rotation-minimising frames from e1_0, each ring's vertices
    round its centre), its UVs the hose's tile at this radius (u round the ring, v the arc length over the tile's length
    at this radius), quads as the hose's; per vertex its ring's skin weights (the fallback skin)"""
    Q, r = B['rings'], B['r']
    T, E1 = CH.rmf(Q, np.asarray(data['e1_0'][1:], np.float64))
    E2 = np.cross(T, E1)
    ang = np.linspace(0.0, TAU, SIDES + 1)
    nr, nc = len(Q), SIDES + 1
    Nt = np.cos(ang)[None, :, None] * E1[:, None, :] + np.sin(ang)[None, :, None] * E2[:, None, :]
    Vt = Q[:, None, :] + r * Nt
    L_tile = CH.TILE_PERIODS * 1.25 * TAU * r / CH.CL.BRAID['carriers']
    UV = np.stack([np.tile(np.linspace(0.0, 1.0, nc)[None, :], (nr, 1)), np.tile((B['s'] / L_tile)[:, None], (1, nc))],
                  -1).reshape(-1, 2)
    Ft = []
    for a_ in range(nr - 1):
        for c_ in range(SIDES):
            p00, p01, p10, p11 = a_ * nc + c_, a_ * nc + c_ + 1, (a_ + 1) * nc + c_, (a_ + 1) * nc + c_ + 1
            Ft += [(p00, p10, p11), (p00, p11, p01)]
    Ft = np.array(Ft, np.int64)
    Vt, Nt = Vt.reshape(-1, 3), Nt.reshape(-1, 3)
    fn = np.cross(Vt[Ft[:, 1]] - Vt[Ft[:, 0]], Vt[Ft[:, 2]] - Vt[Ft[:, 0]])
    if (np.einsum('ij,ij->i', fn, Nt[Ft[:, 0]]) < 0).mean() > 0.5:
        Ft = Ft[:, ::-1].copy()
    from . import bake as BK
    _, TAN = BK.low_frames(Vt, Ft, UV, Nt)
    W = [ring_w[i] for i in range(nr) for _ in range(nc)]
    return dict(V=Vt, N=Nt, TAN=TAN, UV=UV, F=Ft, W=W, L_tile=L_tile,
                tan_w=float(np.sign(np.median(TAN[:, 3])) or 1.0))


# THE COLLAR CLOSED (C3e; the C3d check, p06: on the tentacle's fitting copied, the boss wall's bottom edge stood up to
# 0.82 mm off the plate over 147 of 360 deg (the tentacle's arm had cut it, and the fillers copied the cut), its top edge
# fell open where a filler window started, and the pieces met in notches and standing plates): the plate fitting REBUILT
# as closed solids on the fitting's own texels, in its own frame (the boss's axis at x = x_fitting, z = 0, y up), placed
# as C3d placed the fitting (its axis on the port's point S, the fitting's foot collar_sink under it, scaled by r / r8):
#   THE BOSS     the fitting's 12-gon (band0's corners every 30 deg at R_b, its top at y_top), every face a copy of ONE
#                full-height wall face (WALL_SRC: band0's cleanest, p03) at its own scale from the top down to the
#                fitting's foot, then on down to WALL_DEEP under the lowest skin point under its rim (the low, bind, read
#                along the collar's y under RIM_SAMPLES points of every edge) on that face's bottom texel row: closed into
#                the plate all the way round however the plate curves under it
#   THE TOP      one 12-gon fan on the ferrule's END DISC's texels (its bevel ring at the boss's top edge; the disc's cut
#                sector at the back, under the ferrule's back cap; laid with the disc's own handedness, no mirror): no
#                hole and no disc set in an annulus
#   THE FERRULE  the fitting's 10-gon leaned FERRULE_LEAN off the boss's axis about E (C3d's lean), CLOSED: every side a
#                copy of one band face (TUBE_SRC: its cleanest, p03) at full length from the back cap (fer_a[0], the
#                occluder's own) to the front disc (the end disc's own fan; the cable leaves through it), the back end
#                capped with the same fan mirrored. It lies wholly over the boss's footprint (its lower half in the boss
#                and the plate), so only the top is pierced, by the ferrule, and the front of the boss by the leaving
#                cable: closed solids meeting. Leaned 20 deg off the plate, a tube of 1.79 mm (at r 1.51 mm) cannot sink its
#                back into a boss 1.0 mm tall: the back cap stands up to 1.3 mm over the boss's top, a flat disc nearly
#                upright that read as a slab at the grazing views (C3e's renders). So its rim is CHAMFERED (BACK_CHAMFER
#                of R_f in and along, 45 deg; the sides end that far forward): a machined tube end, its band on the end
#                disc's outer ring of texels and the cap on its inner part
# Every vertex's UV is a point inside one of the fitting's islands (no new texel: c03d K2), its normal the source's (the
# wall and the tube smooth, as the tentacle's; the top and the discs flat), its tangent the forge's own (bake.low_frames:
# the tentacle's shipped tangents to 0.013 deg on these islands, p03). The bake's boss occluder (cyborg.feed_collar, on
# foot + e_off r x) stands 0.25 mm toward the route from this boss; the plate it covers past the boss lies under the
# leaving cable (its AO 0.00-0.15 from the cable's own occluder), and round the rest of the boss the visible plate reads
# its contact shade from 0.3-0.5 at the wall's foot (p04, the C3d run's AO): the boss stays on S, as the hose's fitting
WALL_DEEP = 0.5e-3          # the wall's bottom row this far under the lowest skin point under its rim (bind)
BOSS_SIDES = 12             # the fitting's boss: band0's corners every 30 deg
FER_SIDES = 10              # its ferrule: corners every 36 deg from 18
WALL_SRC = (60.0, 90.0)     # the band0 face every boss face copies (its normal map the flattest, its occlusion >= 181)
TUBE_SRC = (-18.0, 18.0)    # the ferrule band face every tube face copies (its occlusion >= 174 / 255; the others 87-94)
RIM_SAMPLES = 8             # points read under every boss edge
BACK_CHAMFER = 0.18         # the ferrule's back rim chamfered this share of R_f in and along (0.32 mm at r 1.51 mm)


def _turn(vec, axis, angle):
    """vectors (n, 3) turned about the unit axis by angle (rad: one, or one per vector), right-handed (Rodrigues)"""
    vec = np.atleast_2d(np.asarray(vec, np.float64))
    a = np.broadcast_to(np.asarray(angle, np.float64), (len(vec),))
    c, s_ = np.cos(a)[:, None], np.sin(a)[:, None]
    k = np.asarray(axis, np.float64)
    return vec * c + np.cross(k[None], vec) * s_ + k[None] * (vec @ k)[:, None] * (1.0 - c)


def collar_source(ctx):
    """the plate fitting's pieces the closed collar copies (the notes above), read once in the fitting's frame: the boss
    (R_b, y_top, the foot y_lo, the wall face WALL_SRC's four vertices' UVs and normals, bottom then top at each of its
    two corners), the ferrule (its axis E + t d leaned FERRULE_LEAN, its frame e1 = the boss's up made square to d and
    e2 = d x e1, its corner radius R_f, its front t_f and back t_b, the face TUBE_SRC's four vertices back then front at
    each corner, their normals leaned with it) and its end disc (its centre's UV, its boundary by angle round d)"""
    src = getattr(ctx, '_collar_src', None)
    if src is not None:
        return src
    I = ctx.I
    isl = [it_ for it_ in I['islands'] if it_['region'] == 'fitting']
    fitting = CH.copy_islands(ctx.mech, I['islands'], lambda it: it['region'] == 'fitting')
    V, N, UV = fitting['V'], fitting['N'], fitting['UV']
    piece = np.concatenate([[it_['piece']] * (it_['v'][1] - it_['v'][0]) for it_ in isl])
    on_fer = np.array(['ferrule' in p_ for p_ in piece])
    band = np.array(['band' in p_ for p_ in piece])
    xb = float(I['x_fitting'])
    ang = np.degrees(np.arctan2(V[:, 2], V[:, 0] - xb))
    rad = np.hypot(V[:, 0] - xb, V[:, 2])
    wall = band & ~on_fer
    R_b = float(rad[wall].max())
    y_top = float(V[~on_fer & ~band, 1].max())
    y_lo = float(V[:, 1].min())
    wsrc = []
    for a_ in WALL_SRC:
        for y_ in (y_lo, y_top):
            k = np.nonzero(wall & (rad > R_b - 1e-7) & (np.abs(ang - a_) < 1e-3) & (np.abs(V[:, 1] - y_) < 1e-7))[0]
            assert len(k) == 1, f'the fitting\'s wall: {len(k)} vertices at {a_} deg, y {y_}'
            wsrc.append(int(k[0]))
    # the ferrule as the tentacle leans it (d0), its angles round d0 from the boss's up; then the lean (cyborg_hose's:
    # turned about E in the plane of up and d0 to FERRULE_LEAN off the boss's axis, which keeps every angle)
    E_a = np.asarray(I['E'], np.float64)
    d0 = np.asarray(I['d0'], np.float64) / np.linalg.norm(I['d0'])
    up = np.array([0.0, 1.0, 0.0])
    f1 = up - (up @ d0) * d0
    f1 /= np.linalg.norm(f1)
    q = V - E_a
    t = q @ d0
    p = q - t[:, None] * d0
    phi = np.degrees(np.arctan2(p @ np.cross(d0, f1), p @ f1))
    rho = np.linalg.norm(p, axis=1)
    fb = on_fer & band
    R_f = float(rho[fb].max())
    tsrc = []
    for a_ in TUBE_SRC:
        k = np.nonzero(fb & (np.abs(phi - a_) < 1e-2) & (rho > R_f - 1e-7))[0]
        assert len(k) >= 2, f'the ferrule\'s band: {len(k)} corner vertices at {a_} deg'
        tsrc += [int(k[np.argmin(t[k])]), int(k[np.argmax(t[k])])]
    disc = on_fer & ~band
    kc = np.nonzero(disc & (rho < 1e-7))[0]
    kb = np.nonzero(disc & (rho >= 1e-7))[0]
    assert len(kc) == 1 and len(kb) >= FER_SIDES, 'the ferrule\'s end disc: one centre and its boundary'
    kb = kb[np.argsort(phi[kb])]
    lean = math.radians(CH.FERRULE_LEAN) - math.acos(float(np.clip(d0[1], -1.0, 1.0)))
    ax_l = np.cross(up, d0)
    ax_l /= np.linalg.norm(ax_l)
    d = _turn(d0, ax_l, lean)[0]
    e1 = up - (up @ d) * d
    e1 /= np.linalg.norm(e1)
    src = dict(xb=xb, R_b=R_b, y_top=y_top, y_lo=y_lo, wall_UV=UV[wsrc], wall_N=N[wsrc],
               E=E_a, d=d, e1=e1, e2=np.cross(d, e1), R_f=R_f, t_f=float(t[fb].max()),
               t_b=float(CY.FEED_C3D['fer_a'][0]) * ctx.r8, tube_UV=UV[tsrc], tube_N=_turn(N[tsrc], ax_l, lean),
               disc_uv_c=UV[kc[0]], disc_phi=phi[kb], disc_rho=rho[kb], disc_UV=UV[kb],
               verts=dict(wall=wsrc, tube=tsrc, disc_centre=int(kc[0])))
    ctx._collar_src = src
    return src


def _fan_uv(src, alpha):
    """the end disc's UV where a ray from its centre at angle alpha (deg, round d from e1) meets its boundary: the hit
    edge's two UVs interpolated (the disc's own triangles are affine, so the point lies in its island): (n, 2)"""
    P = np.column_stack([src['disc_rho'] * np.cos(np.radians(src['disc_phi'])),
                         src['disc_rho'] * np.sin(np.radians(src['disc_phi']))])
    n = len(P)
    out = []
    for a_ in np.radians(np.atleast_1d(np.asarray(alpha, np.float64))):
        u_ = np.array([math.cos(a_), math.sin(a_)])
        for i in range(n):
            A_, B_ = P[i], P[(i + 1) % n]
            M = np.column_stack([u_, A_ - B_])
            if abs(np.linalg.det(M)) < 1e-18:
                continue
            tt, ss = np.linalg.solve(M, A_)
            if tt > 0.0 and -1e-9 <= ss <= 1.0 + 1e-9:
                out.append((1.0 - ss) * src['disc_UV'][i] + ss * src['disc_UV'][(i + 1) % n])
                break
        else:
            raise CY.CyborgError('cyborg.feed', f'the end disc\'s boundary has no point at {math.degrees(a_):.2f} deg')
    return np.array(out)


def collar_mesh(ctx, col, sink=None):
    """A COLLAR, CLOSED (C3e; the notes above): the boss's wall (12 faces from its top to the fitting's foot, then on down
    to WALL_DEEP under the skin under its rim), its top (one fan), the ferrule (10 sides at full length, its front disc,
    its back cap), built in the fitting's frame and placed on the collar's (x along the route, y the port's normal), its
    axis on S, its foot sink (m, FEED_C3D's collar_sink by default; C5f: the hose's plate fitting passes its own
    SADDLE_SINK) under it. Returns the part, its 'feet' (the wall's bottom vertex under each boss corner, in order round
    the boss: the rim c03d K5 and K7 read) and its 'rim' (the skin's lowest point under the rim and the bottom row, m
    over S along y)"""
    import hashlib
    from . import bake as BK
    src = collar_source(ctx)
    r = col['r']
    sc = r / ctx.r8
    o_f = np.array([src['xb'], src['y_lo'] + (CY.FEED_C3D['collar_sink'] if sink is None else sink) / sc, 0.0])
    R_f = np.column_stack([col['x'], col['y'], col['z']])
    S, y = np.asarray(col['S'], np.float64), np.asarray(col['y'], np.float64)
    nb, nf = BOSS_SIDES, FER_SIDES
    th = np.radians(np.arange(nb + 1) * 360.0 / nb)
    cx, cz = src['xb'] + src['R_b'] * np.cos(th), src['R_b'] * np.sin(th)

    def ring(y_):
        return np.column_stack([cx, np.full(nb + 1, y_), cz])
    # the skin under the rim, bind: the low along -y under RIM_SAMPLES points of every edge, from over the boss's top
    key = getattr(ctx, '_low_rays', None)
    if key is None:
        key = ('feed_collar_rim', hashlib.sha1(np.ascontiguousarray(ctx.low['V']).tobytes()).hexdigest(),
               hashlib.sha1(np.ascontiguousarray(ctx.F_head).tobytes()).hexdigest())
        ctx._low_rays = key
    s_ = np.arange(RIM_SAMPLES) / RIM_SAMPLES
    top = ring(src['y_top'])
    Er = (top[:-1, None] * (1.0 - s_)[None, :, None] + top[1:, None] * s_[None, :, None]).reshape(-1, 3)
    Pw = S + sc * (Er - o_f) @ R_f.T
    hit, fh = CH._ray_mesh(key, ctx.low['V'], ctx.F_head, Pw + 2.0e-3 * y, np.tile(-y, (len(Pw), 1)), 8.0e-3)
    if (fh < 0).any():
        raise CY.CyborgError('cyborg.feed', f'a collar\'s rim stands off the low ({int((fh < 0).sum())} of {len(fh)} '
                                            f'points under it hit nothing)')
    h_min = float(((hit - S) @ y).min())
    y_deep = min(o_f[1] + (h_min - WALL_DEEP) / sc, src['y_lo'] - 1.0e-6)
    Vs, Ns, UVs, Fs = [], [], [], []

    def add(V_, N_, UV_, F_):
        base = sum(len(v_) for v_ in Vs)
        Vs.append(np.asarray(V_, np.float64))
        Ns.append(np.asarray(N_, np.float64))
        UVs.append(np.asarray(UV_, np.float64))
        Fs.append(np.asarray(F_, np.int64) + base)
        return base
    up = np.array([0.0, 1.0, 0.0])
    feet = []
    # THE WALL, face k from corner k to k + 1: the source face turned onto it (a right-handed turn about +y lowers the
    # boss's angle), its rows the top, the fitting's foot and the deep row (the foot's texel row stretched over it)
    rows = [ring(src['y_top']), ring(src['y_lo']), ring(y_deep)]
    wUV, wN = src['wall_UV'], src['wall_N']                       # (a lo, a top, b lo, b top)
    for k in range(nb):
        nk = _turn(wN, up, -(th[k] - math.radians(WALL_SRC[0])))
        Vk = [rows[0][k], rows[1][k], rows[2][k], rows[0][k + 1], rows[1][k + 1], rows[2][k + 1]]
        Nk = [nk[1], nk[0], nk[0], nk[3], nk[2], nk[2]]
        Uk = [wUV[1], wUV[0], wUV[0], wUV[3], wUV[2], wUV[2]]
        b0 = add(Vk, Nk, Uk, [(0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4)])
        feet.append(b0 + 2)
    # THE TOP: one fan, its corners on the end disc's boundary at the angle -theta (the disc's handedness round its
    # normal is the top's round -y)
    add(np.vstack([[src['xb'], src['y_top'], 0.0], top[:nb]]), np.tile(up, (nb + 1, 1)),
        np.vstack([src['disc_uv_c'][None], _fan_uv(src, -np.degrees(th[:nb]))]),
        [(0, 1 + k, 1 + (k + 1) % nb) for k in range(nb)])
    # THE FERRULE: corners at TUBE_SRC[0] + 36 k round d (a right-handed turn about d raises the angle); its sides from
    # the chamfer's foot (BACK_CHAMFER R_f forward of the back cap) to the front disc, on the band face's texels from the
    # same share of its length
    E_a, d, e1, e2 = src['E'], src['d'], src['e1'], src['e2']
    ph = np.radians(TUBE_SRC[0] + np.arange(nf + 1) * 360.0 / nf)
    radial = np.cos(ph)[:, None] * e1[None] + np.sin(ph)[:, None] * e2[None]
    rim_f = src['R_f'] * radial
    ch = BACK_CHAMFER * src['R_f']
    t_s = src['t_b'] + ch
    back, front = E_a + t_s * d + rim_f, E_a + src['t_f'] * d + rim_f
    back_in = E_a + src['t_b'] * d + (1.0 - BACK_CHAMFER) * rim_f
    tUV, tN = src['tube_UV'], src['tube_N']                       # (a back, a front, b back, b front)
    f_s = ch / (src['t_f'] - src['t_b'])
    tUV = np.array([tUV[0] + f_s * (tUV[1] - tUV[0]), tUV[1], tUV[2] + f_s * (tUV[3] - tUV[2]), tUV[3]])
    for k in range(nf):
        nk = _turn(tN, d, ph[k] - math.radians(TUBE_SRC[0]))
        add([back[k], front[k], back[k + 1], front[k + 1]], nk, tUV, [(0, 1, 3), (0, 3, 2)])
    dphi = np.degrees(ph[:nf])
    duv = []
    for a_ in dphi:
        a_ = (a_ + 180.0) % 360.0 - 180.0
        k = np.nonzero(np.abs(src['disc_phi'] - a_) < 1e-2)[0]
        assert len(k) == 1, f'the end disc: no boundary vertex at {a_:.2f} deg'
        duv.append(src['disc_UV'][k[0]])
    duv = np.vstack([src['disc_uv_c'][None], np.array(duv)])
    add(np.vstack([E_a + src['t_f'] * d, front[:nf]]), np.tile(d, (nf + 1, 1)), duv,
        [(0, 1 + k, 1 + (k + 1) % nf) for k in range(nf)])
    # the back: the chamfer's band (outer edge the sides' end, inner edge the cap's ring; on the end disc's outer ring of
    # texels, its normals half outward and half back) and the cap (the disc's inner part, its centre the disc's)
    duv_in = duv[0][None] + (1.0 - BACK_CHAMFER) * (duv[1:] - duv[0][None])
    n_ch = (radial - d[None]) / math.sqrt(2.0)
    for k in range(nf):
        k1 = (k + 1) % nf
        add([back_in[k], back[k], back_in[k + 1], back[k + 1]], [n_ch[k], n_ch[k], n_ch[k + 1], n_ch[k + 1]],
            [duv_in[k], duv[1 + k], duv_in[k1], duv[1 + k1]], [(0, 1, 3), (0, 3, 2)])
    add(np.vstack([E_a + src['t_b'] * d, back_in[:nf]]), np.tile(-d, (nf + 1, 1)),
        np.vstack([duv[0][None], duv_in]), [(0, 1 + (k + 1) % nf, 1 + k) for k in range(nf)])
    V, N, UV, F = np.vstack(Vs), np.vstack(Ns), np.vstack(UVs), np.vstack(Fs)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    # every triangle wound to face its vertices' normals
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    flip = np.einsum('ij,ij->i', fn, N[F].sum(1)) < 0.0
    F[flip] = F[flip][:, ::-1]
    _, TAN = BK.low_frames(V, F, UV, N)
    part = CH.place(dict(V=V, N=N, TAN=TAN, UV=UV, F=F, pieces=['collar (C3e: closed)']), R_f, S, o_f, sc)
    part['feet'] = np.array(feet, np.int64)
    part['rim'] = dict(skin_low=h_min, bottom=float((y_deep - o_f[1]) * sc), flipped=int(flip.sum()))
    return part


def clamp_mesh(ctx, cl):
    """a CLAMP: the tentacle's segment-8 clamp (its band and its lug; its saddle would stand in the plate) scaled by
    r / rh about its axis's point, its axis along the cable, its lug toward the clamp's y (on top)"""
    I, mech = ctx.I, ctx.mech
    c8 = I['clamps'][0]
    part = CH.copy_islands(mech, I['islands'], lambda it: (it['body'] == 'arm_08' and it['region'] == 'clamp' and
                                                           not it['piece'].startswith('saddle')))
    sc = cl['r'] / float(c8['rh'])
    R_ = np.column_stack([cl['x'], -cl['z'], cl['y']])
    return CH.place(part, R_, cl['C'], np.array([float(c8['x']), float(c8['y']), 0.0]), sc)


# ============================================================================================ the glbs
def _skeleton(g, oct_, names):
    """the octopus's bones the skin names, each with its whole parent chain, at the bind (CH.export_glb's)"""
    from . import rig as RG
    rg = oct_.rig
    need = set()
    for nm in names:
        i = rg.index[nm]
        while i >= 0:
            need.add(i)
            i = rg.parent[i]
    W = rg.worlds()
    sk = RG.Skeleton()
    for i in [i for i in rg.order if i in need]:
        p = rg.parent[i]
        sk.add(rg.names[i], rg.names[p] if p >= 0 and p in need else None, W[i][:3, 3], W[i][:3, :3])
    skin, _ = g.skeleton(sk)
    return skin, {nm: k for k, nm in enumerate(sk.names)}


def _pack(wl, jidx):
    """per-vertex weight dicts {bone: w} -> (joints (n, 4), weights (n, 4)) on a skeleton's joint indices"""
    J = np.zeros((len(wl), 4), np.int64)
    W = np.zeros((len(wl), 4))
    for i, wd in enumerate(wl):
        items = sorted(wd.items(), key=lambda kv: -kv[1])[:4]
        s_ = sum(v_ for _, v_ in items)
        for k, (nm, v_) in enumerate(items):
            J[i, k], W[i, k] = jidx[nm], v_ / s_
        for k in range(len(items), 4):
            J[i, k] = jidx[items[0][0]]
    return J, W


def sleeve_maps(ctx):
    """the hose's own sleeve tile (cyborg_hose.sleeve_maps at the hose's radius r8, calibrated to the tentacle's hose
    texels): the same images as every hose's, so the cable reads the hose's set (at its own radius)"""
    calib = CH.tentacle_hose_texels(ctx.mech, ctx.I['islands'])
    return CH.sleeve_maps(ctx.r8, float(ctx.I['px']), calib)


def export_line(path, ctx, B, data, sm, maps, srec):
    """ONE LINE as a glb in the hose's form: one skinned mesh, its SLEEVE primitive (material cyborg_feed_sleeve: the
    hose's tile, a REPEAT sampler), the octopus's bones by name, the cable's data and the line's record in the extras"""
    from . import gltf
    g = gltf.GLB()
    g.j['samplers'].append({'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497})
    rep = len(g.j['samplers']) - 1
    tex = []
    for key in ('albedo', 'normal', 'orm', 'masks'):
        ti = g.texture(maps[key], fmt='png')
        g.j['textures'][ti]['sampler'] = rep
        tex.append(ti)
    m_sl = g.material('cyborg_feed_sleeve', base=tex[0], normal=tex[1], orm=tex[2], volume_tex=tex[3], extras=dict(
        bestiary='cyborg', part='cyborg_feed', masks=tex[3], shares_tile='cyborg_hose_sleeve',
        masks_channels='R primary tint region (none: the rubber sleeve), G accent, B emissive, A wear (none)',
        sampler='REPEAT along and round: the hose\'s tile (cyborg_hose.sleeve_maps at the hose\'s radius), read at the '
                'cable\'s radius: one tile round, v the arc length over the tile\'s length at this radius',
        rows='forge/cyborg.py cyb_gasket (the rubber row) with cyborg_limb BRAID, matched to the tentacle\'s hose'))
    names = sorted({nm for wd in sm['W'] for nm in wd})
    skin, jidx = _skeleton(g, ctx.oct_, names)
    J4, W4 = _pack(sm['W'], jidx)
    TAN = sm['TAN'].copy()
    TAN[:, 3] = data['tan_w']
    mesh = g.mesh('cyborg_feed', sm['V'], sm['N'], TAN, sm['UV'], [(sm['F'], m_sl)], joints=J4, weights=W4)
    g.node(f'cyborg_feed_{B["li"]}', mesh=mesh, skin=skin, root=True)
    nv = len(sm['V'])
    rec = dict(part='cyborg_feed', family='cyborg_feed', line=int(B['li']), kind=B['kind'], units='m', up='+Y',
               forward='+Z', r_mm=B['r'] * 1e3, sides=SIDES, rings=int(len(B['rings'])),
               length_mm=float(B['s'][-1]) * 1e3, bend_min_mm=B['bend_min'] * 1e3, turn_max_deg=B['turn_max'],
               pieces={p_: int((B['piece'] == p_).sum()) for p_ in sorted(set(B['piece']))},
               ring_piece=[str(p_) for p_ in B['piece']],
               tile=dict(length_mm=sm['L_tile'] * 1e3, hose_tile=srec),
               triangles=dict(sleeve=int(len(sm['F']))), vertex_offsets=dict(sleeve=0, hardware=nv, pads=nv, end=nv),
               skin_note='the octopus\'s own bones by name (one skeleton per creature)',
               drawn_in='the bind pose (the cable\'s rings and frames: every skin matrix the identity)',
               cable=data)
    return g.save(path, extras=dict(bestiary=rec))


def export_hardware(path, ctx, parts, maps):
    """THE LOOK'S HARDWARE as one skinned glb: every collar and clamp (copies of the tentacle's islands), each rigid on its
    frame's weights; one material 'mech_tentacle' (shares 'mech_tentacle': the mounted tentacle's own material; the
    tentacle's maps carried for a look without it)"""
    from . import gltf
    g = gltf.GLB()
    ti = [g.texture(maps[k], fmt='png') for k in ('albedo', 'normal', 'orm')]
    m_hd = g.material('mech_tentacle', base=ti[0], normal=ti[1], orm=ti[2], extras=dict(
        bestiary='cyborg', part='cyborg_feed_hardware', shares='mech_tentacle',
        note='the feed\'s collars (the hose\'s plate fitting) and clamps (the tentacle\'s segment-8 band and lug): copies '
             'of the mech tentacle\'s own islands, their UVs on its set; the runtime renders them with the mounted '
             'tentacle\'s material, these maps (the tentacle\'s own) only where none is mounted'))
    names = sorted({nm for p_ in parts for nm in p_['w']})
    skin, jidx = _skeleton(g, ctx.oct_, names)
    cat = lambda key: np.concatenate([p_['mesh'][key] for p_ in parts])
    offs = np.cumsum([0] + [len(p_['mesh']['V']) for p_ in parts])
    J4, W4 = _pack([p_['w'] for p_ in parts for _ in range(len(p_['mesh']['V']))], jidx)
    Fall = np.concatenate([p_['mesh']['F'] + o_ for p_, o_ in zip(parts, offs[:-1])])
    mesh = g.mesh('cyborg_feed_hardware', cat('V'), cat('N'), cat('TAN'), cat('UV'), [(Fall, m_hd)], joints=J4,
                  weights=W4)
    g.node('cyborg_feed_hardware', mesh=mesh, skin=skin, root=True)
    rec = dict(part='cyborg_feed_hardware', family='cyborg_feed', units='m', up='+Y', forward='+Z',
               parts=[(p_['name'], int(o_), int(o_ + len(p_['mesh']['V']))) for p_, o_ in zip(parts, offs[:-1])],
               rims={p_['name']: [int(o_ + k) for k in p_['mesh']['feet']] for p_, o_ in zip(parts, offs[:-1])
                     if 'feet' in p_['mesh']},
               rims_note='each collar\'s wall bottom under its boss corners, in order round the boss (C3e: closed '
                         'into the plate; c03d K5 / K7 read the edges between them)',
               triangles=int(len(Fall)), shares='mech_tentacle')
    return g.save(path, extras=dict(bestiary=rec))


def tentacle_maps():
    """the mech tentacle's shipped maps (work/bestiary/cyborg_c5): albedo, normal, ORM"""
    from PIL import Image
    d = os.path.join(REPO, 'work', 'bestiary', 'cyborg_c5')
    return {k: np.asarray(Image.open(os.path.join(d, f'T_mech_tentacle_{k}.png')).convert('RGB')) for k in
            ('albedo', 'normal', 'orm')}


def build_feed(run_dir, out_dir=FEED_DIR, oct_glb=CH.OCT_GLB, log=print):
    """THE FEED'S CABLES for a t10 run's look (its cyborg_plates.pkl: the plates and the feed): per line its cable (build_line),
    its data (cable_data) and its glb (out_dir/cyborg_feed_<line>.glb), the hardware's glb (out_dir/cyborg_feed_hardware.glb)
    and a record (out_dir/cyborg_feed.json). Returns (the lines' builds with their data, the record)"""
    import json
    import time
    t0 = time.time()
    # (C3e) only a run whose high left the cables out and whose AO took them as occluders (C3d's t10 hunk, its log's
    # lines as c03b F3 reads them): over a run baked before C3d the cables sit on cables baked into the maps
    t10_log = os.path.join(run_dir, 'logs', 't10.log')
    txt = open(t10_log, encoding='utf-8', errors='replace').read() if os.path.exists(t10_log) else ''
    if not all(w in txt for w in ('[cyborg] feed in the high (C3d)', 'stand out of the high', '[cyborg] feed occluders (C3d)')):
        raise CY.CyborgError('cyborg.feed', f'{os.path.relpath(run_dir, REPO)}: its t10 log does not show C3d\'s feed (the '
                                            'cables out of the high, their occluders in the AO): bake the look with the '
                                            'staged t10 hunk (patches/cyborg_c3d_t10.md) first')
    ctx = FeedContext(run_dir, oct_glb, log=log)
    os.makedirs(out_dir, exist_ok=True)
    maps, srec = sleeve_maps(ctx)
    builds, parts = [], []
    for li, ln in enumerate(ctx.fd['lines']):
        B = build_line(ctx, li, ln, log=log)
        data, ring_w = cable_data(ctx, B, log=log)
        sm = sleeve_mesh(B, data, ring_w)
        data['tan_w'] = sm['tan_w']
        path = os.path.join(out_dir, f'cyborg_feed_{li}.glb')
        size = export_line(path, ctx, B, data, sm, maps, srec)
        B.update(data=data, sleeve=sm, glb=path)
        builds.append(B)
        fr = data['frames']
        for k, col in enumerate(B['collars']):
            parts.append(dict(name=f'collar {li}.{k}', mesh=collar_mesh(ctx, col),
                              w=dict(zip(fr[k]['bones'], fr[k]['w']))))
        for k, cl in enumerate(B['clamps']):
            f_ = fr[len(B['collars']) + k]
            parts.append(dict(name=f'clamp {li}.{k}', mesh=clamp_mesh(ctx, cl), w=dict(zip(f_['bones'], f_['w']))))
        log(f'[feed] line {li}: {os.path.relpath(path, REPO)} ({size / 1e6:.2f} MB)')
    hw = os.path.join(out_dir, 'cyborg_feed_hardware.glb')
    size = export_hardware(hw, ctx, parts, tentacle_maps())
    rec = dict(run=os.path.relpath(run_dir, REPO), octopus=os.path.relpath(oct_glb, REPO), inputs=ctx.inputs,
               look=feed_look(ctx), D_mm=ctx.fd['params']['D'] * 1e3, FEED_C3D=dict(CY.FEED_C3D), sleeve_tile=srec,
               lines=[dict(line=B['li'], kind=B['kind'], glb=os.path.relpath(B['glb'], REPO), rings=int(len(B['rings'])),
                           length_mm=float(B['s'][-1]) * 1e3, bend_min_mm=B['bend_min'] * 1e3,
                           turn_max_deg=B['turn_max'], pieces={p_: int((B['piece'] == p_).sum())
                                                               for p_ in sorted(set(B['piece']))},
                           anchors=len(B['data']['anchors']) // 6, skin_verts=len(B['data']['skin_verts']),
                           frames=len(B['data']['frames'])) for B in builds],
               hardware=dict(glb=os.path.relpath(hw, REPO), parts=[p_['name'] for p_ in parts],
                             triangles=int(sum(len(p_['mesh']['F']) for p_ in parts)),
                             collars={p_['name']: dict(skin_low_mm=p_['mesh']['rim']['skin_low'] * 1e3,
                                                       wall_bottom_mm=p_['mesh']['rim']['bottom'] * 1e3)
                                      for p_ in parts if 'rim' in p_['mesh']}),
               seconds=time.time() - t0)
    with open(os.path.join(out_dir, 'cyborg_feed.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rec, f, indent=1, default=float)
    log(f'[feed] {len(builds)} lines and the hardware ({len(parts)} parts, {size / 1e6:.2f} MB) in '
        f'{os.path.relpath(out_dir, REPO)}; {time.time() - t0:.1f}s')
    return builds, rec


# ============================================================================================ the mount path (C3e)
def feed_look(ctx):
    """THE LOOK a feed build serves (its record's 'look'; recipe.resolve_cyborg_runtime gives every feed part the same
    from the recipe, staged in patches/cyborg_c3e_recipe.md): the plates row t10 laid (as the run's record holds it) and
    the feed row as the layout resolved it (its region, links, dives, sleeve, and its seed: the row's, else the plates')"""
    p = ctx.fd['params']
    return dict(plates={k: v for k, v in ctx.rec['row'].items()},
                feed=dict(region=p['region'], links=int(p['links']), dives=int(p['dives']), sleeve=p['sleeve'],
                          seed=int(p['seed'])))


def feed_assets(block, assets=None, out_dir=FEED_DIR, log=print):
    """ASSEMBLY (C3e; recipe.runtime_assets, staged in patches/cyborg_c3e_recipe.md): the engine's asset map {name: path}
    gains every cyborg FEED part of a runtime block (a look with a feed row mounts its lines and their hardware) from
    the feed look's folder out_dir (FEED_DIR). Its record (cyborg_feed.json) must serve the parts' look ('look'), and
    every glb a part names must be there. When an input of the build changed since (the record's sha1s: feed_inputs) the
    look is rebuilt from the record's run (build_feed, about 2 s); with that run gone, or when the rebuild cannot be made
    on today's inputs (C3e check: an octopus re-made on another low than the run baked failed inside it as an
    AssertionError, 'the glb is not this low'), it is refused. Raises CyborgError (cyborg.feed): a look whose feed no
    build holds has no cables to mount (its run lays them: t10 with the feed row), and another look's cables would stand
    off its plates. Returns the map"""
    import json
    out = dict(assets or {})
    parts = [p_ for p_ in (block.get('cyborg') or {}).get('parts', []) if p_.get('kind') == 'feed']
    if not parts:
        return out
    where = os.path.relpath(out_dir, REPO)
    recp = os.path.join(out_dir, 'cyborg_feed.json')
    if not os.path.exists(recp):
        raise CY.CyborgError('cyborg.feed', f'no feed look built in {where} (no cyborg_feed.json): build it from the look\'s '
                                            't10 run (work/bestiary/tests/c03d_cables.py build run=<run> out=<folder>)')
    with open(recp, encoding='utf-8') as f:
        rec = json.load(f)
    looks = {json.dumps(p_.get('look'), sort_keys=True) for p_ in parts}
    if len(looks) != 1:
        raise CY.CyborgError('cyborg.feed', f'the block\'s feed parts name {len(looks)} looks: one feed row per region, one '
                                            'region with feed lines (slots.FEED_REGIONS)')
    # a stale build (an input changed since, or a record from before the look was recorded) rebuilt from its run first
    run = os.path.join(REPO, rec['run'])
    oct_glb = os.path.join(REPO, rec['octopus'])
    now = feed_inputs(run, oct_glb) if os.path.isdir(run) and os.path.exists(oct_glb) else None
    if now != rec.get('inputs') or 'look' not in rec:
        if now is None:
            raise CY.CyborgError('cyborg.feed', f'the feed look in {where} was built from {rec["run"]} on {rec["octopus"]}, '
                                                'which are gone: rebuild it from the look\'s t10 run')
        changed = sorted(k for k in now if now[k] != (rec.get('inputs') or {}).get(k)) or ['its record (no look)']
        log(f'[assembly] the feed look in {where}: {", ".join(changed)} changed since its build; rebuilt from {rec["run"]}')
        try:
            _, rec = build_feed(run, out_dir, oct_glb, log=log)
        except (AssertionError, ValueError) as e:
            # (the build's own checks: the octopus not the low the run baked, the tentacle's fitting islands not the
            # pieces collar_source copies; a numpy shape clash when the low's vertex count changed)
            raise CY.CyborgError('cyborg.feed', f'the feed look in {where} could not be rebuilt from {rec["run"]} after '
                                                f'{", ".join(changed)} changed ({type(e).__name__}: {e}): bake the look\'s '
                                                't10 run on today\'s octopus (patches/cyborg_c3d_t10.md) and build from it '
                                                '(work/bestiary/tests/c03d_cables.py build gates run=<that run>)') from e
        rec = json.loads(json.dumps(rec, default=float))
    want = parts[0].get('look')
    if want is not None and json.dumps(want, sort_keys=True) != json.dumps(rec.get('look'), sort_keys=True):
        raise CY.CyborgError('cyborg.feed', f'the feed parts\' look {want} is not the one built in {where} '
                                            f'({rec.get("look")}): its cables follow other plates')
    for p_ in parts:
        path = os.path.join(out_dir, f'{p_["asset"]}.glb')
        if not os.path.exists(path):
            raise CY.CyborgError('cyborg.feed', f'the feed part {p_["asset"]}: no {os.path.relpath(path, REPO)} (the look '
                                                f'built there has {len(rec["lines"])} lines and its hardware)')
        out[p_['asset']] = path
    log(f'[assembly] {len(parts)} feed parts: {where} ({", ".join(sorted(p_["asset"] for p_ in parts))})')
    return out
