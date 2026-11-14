"""The octopus's RIG (animation craft guide: AG 05 skeletons, 06 skinning, 16.21 lagged chains on intent).

Skeleton (203 joints): root -> body (the crown's centre) -> head (eye level) -> the mantle chain from the collar to the
apex; head -> eye_L / eye_R (the eyeballs' centres) and funnel_0 -> funnel_1; body -> eight arm chains of 24 joints
each, placed at EQUAL steps of the straightened arm coordinate (octopus_sculpt.arm_tables), so joints crowd toward the
thin tips where an arm bends tightest. Arm joint frames: x along the arm, y its aboral normal (so a positive rotation
about z curls the arm toward its suckers' side... sign asserted by the pose test), z = x cross y.

Weights live on the WELDED cage (AG 00.43) and ramp along the anatomy (AG 00.45): arm tubes by their s on their own
arm; the crown blends its two nearest arms by their share lam across the web, the body near the crown's centre; the
body and mantle by the body axis's s; the eye ports to the head, the funnel along its own axis; then the whole field
is smoothed and cut to four influences.
"""
import numpy as np

from .. import rig as RG
from .octopus import arm_azimuths, arm_radius, axis_s, body_axis, collar, eye_geom, eye_level, funnel_geom
from .octopus_sculpt import arm_tables

N_ARM_JOINTS = 24


def arm_joint_s(spec, n=N_ARM_JOINTS):
    st, U, R = arm_tables(spec)
    u = np.linspace(0.0, np.interp(0.985, st, U), n)
    return np.interp(u, U, st)


def body_joint_s(spec):
    """the body axis's share s at each body joint: mantle_0 at the collar (the mantle's front), the head where the axis
    passes under the eyes, the mantle chain spaced toward the apex (by geometry: the v4 mantle lies back nearly level,
    so the r4 rule by height along the axis found neither)"""
    P, n, b, t = body_axis(spec)
    sP = axis_s(P)
    ye, ze = eye_level(spec)
    s_col = float(sP[np.argmin(np.linalg.norm(P - collar(spec), axis=1))])
    fwd = sP > s_col
    s_eye = float(sP[fwd][np.argmin(np.abs(P[fwd, 2] - ze))])
    # apex -> crown order: mantle_3, mantle_2, mantle_1, mantle_0 (collar), head, body
    return dict(mantle_3=0.12 * s_col, mantle_2=0.36 * s_col, mantle_1=0.66 * s_col, mantle_0=s_col, head=s_eye,
                body=1.0)


def build(spec, arms, order):
    sk = RG.Skeleton()
    P, n, b, t = body_axis(spec)
    sP = axis_s(P)
    at = lambda s: np.array([np.interp(s, sP, P[:, k]) for k in range(3)])
    tan = lambda s: np.array([np.interp(s, sP, t[:, k]) for k in range(3)])
    dors = lambda s: np.array([np.interp(s, sP, n[:, k]) for k in range(3)])
    bs = body_joint_s(spec)
    sk.add('root', None, [0.0, 0.0, 0.0])
    sk.add('body', 'root', [0.0, spec['crown_y'], 0.0], RG.frame_from([0.0, 1.0, 0.0], [0.0, 0.0, 1.0]))
    # head and mantle: x along the axis toward the apex, y the dorsal side
    prev = 'body'
    for name in ('head', 'mantle_0', 'mantle_1', 'mantle_2', 'mantle_3'):
        s = bs[name]
        sk.add(name, prev, at(s), RG.frame_from(-tan(s), dors(s)))
        prev = name
    for side, nm in ((1, 'eye_L'), (-1, 'eye_R')):
        c, out, E, Re = eye_geom(spec, side)
        sk.add(nm, 'head', E, RG.frame_from(out, [0.0, 1.0, 0.0]))
    fa, fb, fra, frb = funnel_geom(spec)
    sk.add('funnel_0', 'head', fa, RG.frame_from(fb - fa, [0.0, 1.0, 0.0]))
    sk.add('funnel_1', 'funnel_0', 0.5 * (fa + fb), RG.frame_from(fb - fa, [0.0, 1.0, 0.0]))
    js = arm_joint_s(spec)
    for j in range(len(order)):
        Pa, na, ba, ta = arms[order[j]]
        sa = np.linspace(0, 1, len(Pa))
        ip = lambda X, s: np.array([np.interp(s, sa, X[:, k]) for k in range(3)])
        prev = 'body'
        for k, s in enumerate(js):
            x = ip(ta, s)
            name = f'arm{j}_{k:02d}'
            sk.add(name, prev, ip(Pa, s), RG.frame_from(x, ip(na, s)))
            prev = name
    return sk


def weights(spec, cage, info, arms, sk, smooth_iters=4):
    """per WELDED cage vertex: (joints (n, 4), weights (n, 4))"""
    V = cage.V
    reg = cage.attrs['part'].argmax(1)
    st = cage.attrs['st']
    J = len(sk.names)
    W = np.zeros((len(V), J))
    order = info['order']
    js = arm_joint_s(spec)
    arm_j = [[sk.index(f'arm{j}_{k:02d}') for k in range(len(js))] for j in range(len(order))]
    # ---- body and mantle by the body axis's s
    bs = body_joint_s(spec)
    names = sorted(bs, key=lambda k: bs[k])
    bj = [sk.index(nm) for nm in names]
    body = reg == 0
    k0, k1, tt = RG.hat_weights(st[body, 0], [bs[nm] for nm in names])
    idx = np.nonzero(body)[0]
    np.add.at(W, (idx, np.array(bj)[k0]), 1.0 - tt)
    np.add.at(W, (idx, np.array(bj)[k1]), tt)
    # ---- arms and crown: the two nearest arms by azimuth, each arm's nearest centreline point
    az = arm_azimuths()[order]
    a_p = np.arctan2(V[:, 0], V[:, 2])
    dA = (a_p[:, None] - az[None, :] + np.pi) % (2 * np.pi) - np.pi
    near = np.argsort(np.abs(dA), axis=1)[:, :2]
    s_on = np.zeros((len(V), 2))
    d_on = np.zeros((len(V), 2))
    for c in range(2):
        for j in range(len(order)):
            m = near[:, c] == j
            if not m.any():
                continue
            Pa = arms[order[j]][0]
            sa = np.linspace(0, 1, len(Pa))
            seg = Pa[1:] - Pa[:-1]
            q = V[m][:, None, :] - Pa[None, :-1, :]
            tseg = np.clip((q * seg[None]).sum(2) / (seg * seg).sum(1)[None], 0.0, 1.0)
            dist = np.linalg.norm(q - tseg[..., None] * seg[None], axis=2)
            ib = dist.argmin(1)
            s_on[m, c] = (ib + tseg[np.arange(m.sum()), ib]) / (len(Pa) - 1)
            d_on[m, c] = dist[np.arange(m.sum()), ib]
    rest = ~body
    for i in np.nonzero(rest)[0]:
        if reg[i] >= 3:                                   # an arm tube: its own arm
            j = reg[i] - 3
            c = 0 if near[i, 0] == j else 1
            parts = [(j, s_on[i, c], 1.0)]
        else:                                             # the crown: blend the two arms across the web
            a0, a1 = near[i]
            lam = abs(dA[i, a0]) / max(abs(dA[i, a0]) + abs(dA[i, a1]), 1e-9)
            wa = 1.0 - (lam * lam * (3 - 2 * lam) if lam < 1.0 else 1.0)
            if d_on[i, 0] < 1.15 * arm_radius(np.array([s_on[i, 0]]), spec)[0]:
                wa = 1.0                                  # on the nearer arm's tube
            parts = [(a0, s_on[i, 0], wa), (a1, s_on[i, 1], 1.0 - wa)]
        s_min = min(p[1] for p in parts)
        w_body = 1.0 - float(np.clip((s_min - 0.03) / 0.06, 0.0, 1.0)) if reg[i] < 3 else 0.0
        for j, s, w in parts:
            if w <= 0.0:
                continue
            a, bb, t = RG.hat_weights(np.array([s]), js)
            W[i, arm_j[j][a[0]]] += (1 - w_body) * w * (1 - t[0])
            W[i, arm_j[j][bb[0]]] += (1 - w_body) * w * t[0]
        W[i, sk.index('body')] += w_body
    # ---- the eye ports to the head; the funnel along its axis
    for side in (1, -1):
        c, out, E, Re = eye_geom(spec, side)
        m = body & (np.linalg.norm(V - E, axis=1) < 1.35 * Re)
        W[m] = 0.0
        W[m, sk.index('head')] = 1.0
    fa, fb, fra, frb = funnel_geom(spec)
    ax = fb - fa
    tf = np.clip(((V - fa) @ ax) / (ax @ ax), -0.2, 1.2)
    rf = fra + (frb - fra) * np.clip(tf, 0, 1)
    df = np.linalg.norm(V - (fa + tf[:, None] * ax), axis=1)
    m = body & (df < 1.35 * rf) & (tf > 0.1)
    w1 = np.clip((tf[m] - 0.35) / 0.5, 0.0, 1.0)
    W[m] = 0.0
    W[m, sk.index('funnel_0')] = 1.0 - w1
    W[m, sk.index('funnel_1')] = w1
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    W = RG.smooth_field(W, cage.Q, iters=smooth_iters, alpha=0.5)
    return RG.limit_influences(W, 4)
