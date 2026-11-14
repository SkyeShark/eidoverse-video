"""CYBORG LIMBS, the forge side of the LIMBS layer (work/bestiary/research/CYBORG_PLAN.md §4.4, §5.5, §8 C5; its addendum
A.4, A.7, A.8 and the lead's A.9 decisions; PLAN.md 10-22 "C5a"): THE MECH TENTACLE as its own asset. It replaces an
octopus ARM from the cut at joint 8 to the tip (Skye's standing rule, said twice: parts MATCH THE BODY SLOT; a mech
tentacle replaces an octopus arm and nothing else), on the arm's OWN joints: one rigid piece per joint, the arm's own
spacing and taper, so the runtime's rest motion (runtime/bestiary.js radialMotion.solveArm) drives it unchanged.

C5a is the asset alone; the octopus integration (the cut low, the pinned weights, the suckers dropped, t13's parts and
the runtime's per-arm radius table) is C5b, after C3 lands. forge/cyborg.py (C3 edits it live) is READ here, never
edited: its id names and material rows (CYBORG_ID, row_values) are the materials' source.

THE PARTS (rigid BODIES; the asset's own straight bind: x along the arm, y aboral, z = x cross y, the origin at joint
7; every piece is built in its body's frame, a bone's CHORD frame (the frame solveArm aims) or a helper joint's at the
same pivot, so a body of joint k sits at joint k with its chord along +x):
  bone 7     the FLANGE (§4.4.4) rigid on the last flesh bone: the soft ROLL where flesh meets the collar, the COLLAR
             (its lug, the six-bolt face), the hose's bulkhead fitting
  joint 8    the RUBBER BAND between the collar and the first segment: a short bellows round joint 8's pivot, skinned
             across bones 7 and 8 (the one flexible coupling; joint 8 bends at most 10.3 deg, pure yaw)
  joints 9-15 CLEVIS knuckles (the rest motion turns them in yaw alone: pitch <= 0.2, roll <= 0.7 deg): an octagonal
             shell following the flesh's own section at 0.95 of its size, a clevis DRUM at its distal joint (two cheeks
             about the joint's yaw axis, the slot between them) with a coaxial MOTOR CAN on the aboral cheek (the old
             kit's drum, K8), the next segment's TONGUE (a disc and neck) turning in the slot. C5a-2: the drums shrink
             so each knuckle spans at most 35 % of its segment (the lead's call 3)
  joints 16-22 UNIVERSAL (CARDAN) knuckles (C5a-2, the lead's call 1: the rest motion bends them up to 14.8 deg in pitch
             and 24.6 in tilt): the parent's YAW YOKE (top and bottom tines, the yaw MOTOR CAN on the top lug), the
             CROSS (a hub and four trunnions, helper joint arm_kk_cross: it turns with the yaw), the child's PITCH YOKE
             (side tines; a pitch MOTOR CAN on the +z tine at 16-19); the trunnions' ends stand out of the lugs as the
             visible axles. Where the motion's roll about the child's own axis passes 3 deg (18-22) the child segment's
             shell, its pitch yoke and its actuator turn on a ROLL BEARING RING at the segment's distal end (helper
             joint arm_kk_shell), before the next knuckle's yoke, which stays on the bone
  segments 20-22 Minsky's (length over width 2.23-3.76, CYBORG_PLAN §3.6 / REFS §4.6): waisted shells between junction
             blocks, an ACTUATOR along the +z side that drives its knuckle's PITCH AXLE: the cylinder rigid on the
             segment, the rod (helper joint arm_kk_rod) on a crank keyed to the cross's +z trunnion (the lead's call 2)
  bone 23    the tip: a tapered end and its gripper boss (socket_arm{j}_tip, kind limb_tip, rides it), on a clevis
             wrist (the runtime leaves joint 23 at rest)
  the HOSE   one bundle 0.25 of the machine's width (Minsky's), outside the chain along its aboral midline, clamped to
             every segment by clamp collars (p02's 1.12 / 1.30 / 0.54 D) and ARCHING OVER each knuckle's motor can: on
             the joint's yaw axis, where the coils neither stretch nor crush it (yaw is almost all of the rest motion);
             each arch skinned across its two clamps' bodies (A.4.2; G10's one listed exemption, with the band), and
             over the knuckles whose yaw passes 35 deg (19-22) through a CREST joint at the pivot turning half the yaw
             (C5a-2: the two-bone arch made a corner at its crest under 60-77 deg)

Read with numpy, scipy and warp (the SDFs, the voxel high, the bake and the renders run on warp's device).

THE BAKE (C5a-3, the lead's call 1): every texel bakes from its OWN PIECE's high alone (a piece: one union primitive of
the bake's program and the cuts of its group; the band; the hose). A second voxel high holds every piece in its own slot,
SLOT_GAP apart, its voxels carrying the piece's id; each sub-sample's search there is TWO-SIDED, the nearest crossing of
its own piece's surface along its ray within the cage, and a crossing whose voxels name another piece is refused. The
shade (AO, cavity, thickness, curvature) is read at that hit in the body layout's union high, unchanged, so a neighbour
still darkens the corner it makes; a hit lying inside another piece there is COVERED (the face is under that piece).
"""
import math
import os

import numpy as np
import warp as wp

from . import bake as BK
from . import sdf as SD
from . import voxel as VX

wp.set_module_options({'enable_backward': False})    # forward-only kernels (as bake.py and voxel.py)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
OCTOPUS_DIR = os.path.join(REPO, 'work', 'bestiary', 'octopus')
TAU = 2.0 * math.pi
M32 = 0xFFFFFFFF

CUT = 8                     # the cut joint (CYBORG_PLAN §4.4.1: cut 8, half the arm machine)
N_JOINTS = 24               # the octopus arm's joints (forge/species/octopus_rig.py N_ARM_JOINTS)
J0 = CUT - 1                # the flange's bone (the last flesh bone, k - 1)
MINSKY_FROM = 20            # the first segment whose length over width reaches Minsky's 2.19-2.29 (§4.4.3)
CARDAN = tuple(range(16, 23))   # C5a-2: the distal knuckles 16-22 are universal (cardan) joints (the lead's call 1)
SET = (2048, 1024)          # C5a-2: the texture set (the lead's call 4): the plan's 5,046 px/m does not fit 1024^2 (C5a:
                            # 3,646), so the smallest larger set; the islands pack into the bottom half of a 2048^2 canvas
                            # (bake and material at 2048^2, the maps cropped to 2048 x 1024, the export's v doubled)
PX_TARGET = 5046.0          # CYBORG_PLAN §4.4.3: a unique set at 5,046 px/m; the details are sized in texels of it
# the flesh section (forge/species/octopus.py build_sdf, the arm SWEEP: "rounder aboral, flatter oral"): r(theta) =
# r0 (1 + a2 cos 2 theta + a3 cos 3 theta), its b axis squeezed by the aspect; theta from the aboral side toward b
FLESH = dict(a2=0.06, a3=0.05, aspect=0.92)
CORE = 0.95                 # the machine's section at 0.95 of the flesh's (§4.4.3 [E-fo])


# ============================================================================================ the arm it replaces
def _quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def glb_worlds(gj):
    """{node name: 4x4 world matrix} of a glb's JSON"""
    nodes = gj['nodes']
    parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    W = {}

    def wm(i):
        if i in W:
            return W[i]
        n = nodes[i]
        M = np.eye(4)
        if 'rotation' in n:
            M[:3, :3] = _quat_mat(n['rotation'])
        if 'translation' in n:
            M[:3, 3] = n['translation']
        W[i] = M if i not in parent else wm(parent[i]) @ M
        return W[i]
    return {n.get('name', str(i)): wm(i) for i, n in enumerate(nodes)}


def flesh_profile(th):
    """the flesh section's radius over r0 at angle th (radians from the aboral side toward b): octopus.build_sdf's arm
    SWEEP profile (forge/sdf.py sd_sweep's formula)"""
    th = np.asarray(th, np.float64)
    r = 1.0 + FLESH['a2'] * np.cos(2.0 * th) + FLESH['a3'] * np.cos(3.0 * th)
    a = FLESH['aspect']
    return r * a / np.sqrt(a * a * np.cos(th) ** 2 + np.sin(th) ** 2)


def flesh_outline(n=720):
    """the flesh section's outline over r0 as (y, z) points (y aboral, z = b), counter-clockwise from the aboral side"""
    th = np.linspace(0.0, TAU, n, endpoint=False)
    r = flesh_profile(th)
    return np.column_stack([r * np.cos(th), r * np.sin(th)])


def support(theta, n=4096):
    """the flesh outline's support function h(theta) over r0: max over the outline of p . (cos theta, sin theta)"""
    P = flesh_outline(n)
    d = np.stack([np.cos(theta), np.sin(theta)], -1)
    return (P @ np.atleast_2d(d).T).max(0)


def arm_chain(cut=CUT, arm=0, glb=None, low=None):
    """the canonical octopus's arm as the machine needs it, read from work/bestiary/octopus/octopus.glb (the joints, the
    bind segment lengths, every bone's chord frame) and the species' arm table (forge/species/octopus.py arm_radius,
    octopus_rig.arm_joint_s), with the low's ring at the cut (low.npz: the ring the flange's bore holds, and the ring
    before it, both pinned to bone cut - 1 at C5b).
    Returns a dict (metres): js (24 shares), r (the flesh radius at each joint), seg (23 bind segment lengths), x (each
    joint along the asset's straight chain, joint J0 at 0), P / W (the bind's joint positions and world frames), chordB
    (per bone 0..22 the chord frame in the bone's local axes: the runtime's chordQ is its inverse), tip_rel (bone 23 in
    bone 22's chord frame), ring (s, x, the ring before's s and x, the section's extents there in the chord-J0 frame),
    L_arm (the arm's length)"""
    from . import gltf
    from .species import octopus as O
    from .species import octopus_rig as OR
    glb = glb or os.path.join(OCTOPUS_DIR, 'octopus.glb')
    low = low or os.path.join(OCTOPUS_DIR, 'low.npz')
    R = gltf.read(glb)
    Wn = glb_worlds(R['json'])
    spec = O.low_spec(O.SPEC)
    js = OR.arm_joint_s(spec)
    assert len(js) == N_JOINTS
    W = np.stack([Wn[f'arm{arm}_{k:02d}'] for k in range(N_JOINTS)])
    P = W[:, :3, 3].copy()
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    r = O.arm_radius(js, spec)
    chordB = []
    for k in range(N_JOINTS - 1):
        loc = np.linalg.inv(W[k][:3, :3]) @ (P[k + 1] - P[k])
        loc /= np.linalg.norm(loc)
        yref = np.array([0.0, 1.0, 0.0]) - loc * loc[1]
        yref /= np.linalg.norm(yref)
        chordB.append(np.column_stack([loc, yref, np.cross(loc, yref)]))
    chordB = np.stack(chordB)
    tip_rel = chordB[-1].T @ (np.linalg.inv(W[-2][:3, :3]) @ W[-1][:3, :3])
    x = np.concatenate([[0.0], np.cumsum(seg[J0:])])           # joints J0 .. 23 along the straight chain
    xs = np.zeros(N_JOINTS)
    xs[J0:] = x
    xs[:J0] = -np.cumsum(seg[:J0][::-1])[::-1]
    L_arm = float(seg.sum() / js[-1])
    # the low's rings on this arm: their share along the joint polyline (forge_cyborg_numbers.py's rule)
    Lw = np.load(low, allow_pickle=True)
    V, F, reg = Lw['V'], Lw['F'], Lw['region']
    arm_v = np.unique(F[reg == 3 + arm])
    Va = V[arm_v]
    q = Va[:, None, :] - P[None, :-1]
    ab = P[1:] - P[:-1]
    tt = np.clip((q * ab[None]).sum(2) / (ab * ab).sum(1)[None], 0, 1)
    dist = np.linalg.norm(q - tt[..., None] * ab[None], axis=2)
    ib = dist.argmin(1)
    s_arm = js[ib] + tt[np.arange(len(Va)), ib] * (js[ib + 1] - js[ib])
    ss = np.sort(s_arm)
    gaps = np.diff(ss)
    a0 = np.concatenate([[0], np.nonzero(gaps > 0.002)[0] + 1])
    a1 = np.concatenate([np.nonzero(gaps > 0.002)[0] + 1, [len(ss)]])
    ring_s = np.array([np.median(ss[a:b]) for a, b in zip(a0, a1)])
    s_cut = 0.5 * (js[cut - 1] + js[cut])
    ir = int(np.argmin(np.abs(ring_s - s_cut)))
    x_of = lambda s: float((s - js[J0]) / (js[J0 + 1] - js[J0]) * seg[J0])   # along chord J0 (the ring lies in it)
    Fj = chord_frame(W[J0], P[J0], P[J0 + 1])
    on = np.abs(s_arm - ring_s[ir]) < 0.0015
    Qr = (Va[on] - P[J0]) @ Fj
    ring = dict(s=float(ring_s[ir]), x=x_of(ring_s[ir]), s_before=float(ring_s[ir - 1]), x_before=x_of(ring_s[ir - 1]),
                s_cut=float(s_cut), x_cut=x_of(s_cut), n=int(on.sum()), r_nominal=float(O.arm_radius(ring_s[ir], spec)),
                y=(float(Qr[:, 1].min()), float(Qr[:, 1].max())), z=(float(Qr[:, 2].min()), float(Qr[:, 2].max())),
                pts=Qr)
    return dict(cut=cut, arm=arm, js=js, r=r, seg=seg, x=xs, P=P, W=W, chordB=chordB, tip_rel=tip_rel, ring=ring,
                L_arm=L_arm, spec=spec, ring_s=ring_s)


def chord_frame(Wk, Pk, Pk1):
    """a bone's chord frame in world: x along the chord to the next joint, y the bone's aboral axis made normal to it
    (the runtime's yref), z = x cross y"""
    xk = (Pk1 - Pk) / np.linalg.norm(Pk1 - Pk)
    yk = Wk[:3, 1] - xk * (Wk[:3, 1] @ xk)
    yk /= np.linalg.norm(yk)
    return np.column_stack([xk, yk, np.cross(xk, yk)])


def radius_at(chain, x):
    """the flesh's nominal radius at a point x along the straight chain (the species' taper, s interpolated linearly
    between the joints as the runtime's segments are)"""
    from .species import octopus as O
    s = np.interp(x, chain['x'], chain['js'])
    beyond = np.asarray(x) > chain['x'][-1]
    s = np.where(beyond, chain['js'][-1] + (np.asarray(x) - chain['x'][-1]) / chain['L_arm'], s)
    return O.arm_radius(np.clip(s, 0.0, 1.0), chain['spec'])


# ============================================================================================ the rest motion
def hash01(i, seed):
    """runtime/bestiary.js hash01 (lowbias32), bit for bit: the twin of remix/recipe.py hash01 (kept here so the forge
    does not import the remix layer)"""
    x = ((int(i) * 0x9E3779B1) & M32) ^ ((int(seed) * 0x85EBCA77) & M32)
    x ^= x >> 16
    x = (x * 0x7FEB352D) & M32
    x ^= x >> 15
    x = (x * 0x846CA68B) & M32
    x ^= x >> 16
    return (x >> 8) / 16777216.0


def _smooth(a, b, x):
    u = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def arm_params(j, seed):
    """radialMotion's per-arm seeded parameters (runtime/bestiary.js:432-442)"""
    h = lambda i: hash01(j * 31 + i, seed)
    return dict(dAz=(h(1) - 0.5) * 0.45, wanderK=(h(2) - 0.5) * 2.0 * 2.2, wanderL=0.30 + 0.30 * h(3),
                wanderPh=h(4) * TAU, coilSide=-1.0 if h(5) < 0.5 else 1.0, coilS0=0.50 + 0.22 * h(6),
                coilG=0.28 + 0.30 * h(7), tipLift=0.015 + 0.03 * h(9) if h(8) < 0.35 else 0.0,
                drape=0.10 + 0.08 * h(10), ph0=h(11) * TAU, ph1=h(12) * TAU)


def solve_arm(P_bind, ts, j, seed, lower=0.040, r0=0.026, r_tip=0.0011, ground=0.0):
    """runtime/bestiary.js radialMotion.solveArm, term by term, vectorised over the times ts: each segment's chord
    direction and its aimed frame (x the chord, y the world up made normal to it: 'its aboral side (local y) up', z =
    x cross y), and the joints' positions. P_bind: the arm's 24 bind joint positions in the creature's space (the crown
    lowered by `lower` as radialMotion does). Returns pos (T, 24, 3) and F (T, 23, 3, 3), F[:, k] the chord frame of
    bone k (columns x, y, z)"""
    p = arm_params(j, seed)
    P = np.asarray(P_bind, np.float64) - np.array([0.0, lower, 0.0])
    lens = np.linalg.norm(np.diff(P, axis=0), axis=1)
    n = len(P)
    L = float(lens.sum()) / 0.985
    t = np.asarray(ts, np.float64)
    T = len(t)
    d0 = P[1] - P[0]
    d0[1] = 0.0
    d0 /= np.linalg.norm(d0)
    coilMul = 1.0 + 0.10 * np.sin(TAU * 0.06 * t + p['ph0'])
    theta = np.full(T, math.atan2(d0[0], d0[2]) + p['dAz'])
    cur = np.tile(P[0], (T, 1))
    y0 = P[0, 1]
    s = 0.0
    pos = np.zeros((T, n, 3))
    pos[:, 0] = cur
    F = np.zeros((T, n - 1, 3, 3))
    UP = np.array([0.0, 1.0, 0.0])
    for k in range(n - 1):
        sm = s + 0.5 * lens[k]
        u = sm / L
        kap = p['wanderK'] * np.sin(TAU * sm / p['wanderL'] + p['wanderPh']) * (0.3 + 0.7 * _smooth(0.05, 0.3, u))
        rem = max(L - sm, 0.0)
        kap = kap + p['coilSide'] * coilMul * _smooth(p['coilS0'], p['coilS0'] + 0.12, u) / (0.010 + p['coilG'] * rem)
        kap = kap + 0.9 * np.sin(TAU * 0.21 * t - 9.0 * u + p['ph1']) * _smooth(0.75, 1.0, u)
        theta = theta + kap * lens[k]
        s1 = s + lens[k]
        u1 = s1 / L
        rad = r_tip + (r0 - r_tip) * max(1.0 - u1, 0.0) ** 0.92
        yg = ground + 0.92 * rad
        yT = yg + (y0 - (ground + 0.92 * r0)) * (1.0 - _smooth(0.0, p['drape'], s1)) \
            + p['tipLift'] * _smooth(0.82, 1.0, u1) * (1.0 + 0.4 * np.sin(TAU * 0.17 * t + p['ph1']))
        sinPhi = np.clip((yT - cur[:, 1]) / lens[k], -1.0, 1.0)
        cosPhi = np.sqrt(1.0 - sinPhi * sinPhi)
        d = np.stack([cosPhi * np.sin(theta), sinPhi, cosPhi * np.cos(theta)], -1)
        yv = UP[None] - d * d[:, 1:2]
        yv /= np.linalg.norm(yv, axis=1, keepdims=True)
        F[:, k] = np.stack([d, yv, np.cross(d, yv)], -1)
        cur = cur + d * lens[k]
        pos[:, k + 1] = cur
        s = s1
    return pos, F


def rel_rotations(F, tip_rel=None):
    """the relative rotation at each joint k = 1..23 (bone k's chord frame in bone k - 1's): R[:, k - 1]; joint 23's
    child is bone 23 at its rest local rotation (the runtime leaves the last joint at rest: tip_rel, constant)"""
    R = np.einsum('tkji,tkjl->tkil', F[:, :-1], F[:, 1:])           # F[k-1]^T F[k]
    if tip_rel is not None:
        R = np.concatenate([R, np.broadcast_to(tip_rel, (len(F), 1, 3, 3))], axis=1)
    return R


def yaw_pitch(R):
    """a relative rotation's yaw (about the parent's y, + taking +x toward -z) and pitch (the child's x above the
    parent's xz plane), radians, and the whole bend angle"""
    xc = R[..., :, 0]
    yaw = np.arctan2(-xc[..., 2], xc[..., 0])
    pitch = np.arcsin(np.clip(xc[..., 1], -1.0, 1.0))
    bend = np.arccos(np.clip((np.trace(R, axis1=-2, axis2=-1) - 1.0) * 0.5, -1.0, 1.0))
    return yaw, pitch, bend


def tilt(R):
    """the angle between the child's aboral axis and the parent's (radians): how far the child's slot plane tilts
    against the parent's drum, pitch and ROLL together (solveArm keeps every bone's y up, so a large yaw between two
    pitched segments twists the child about its axis: at joint 20 the tilt reaches ~4x the pitch)"""
    return np.arccos(np.clip(np.asarray(R)[..., 1, 1], -1.0, 1.0))


def _rx_n(a):
    a = np.asarray(a, np.float64)
    c, s, z, o = np.cos(a), np.sin(a), np.zeros_like(a), np.ones_like(a)
    return np.stack([np.stack([o, z, z], -1), np.stack([z, c, -s], -1), np.stack([z, s, c], -1)], -2)


def _ry_n(a):
    a = np.asarray(a, np.float64)
    c, s, z, o = np.cos(a), np.sin(a), np.zeros_like(a), np.ones_like(a)
    return np.stack([np.stack([c, z, s], -1), np.stack([z, o, z], -1), np.stack([-s, z, c], -1)], -2)


def _rz_n(a):
    a = np.asarray(a, np.float64)
    c, s, z, o = np.cos(a), np.sin(a), np.zeros_like(a), np.ones_like(a)
    return np.stack([np.stack([c, -s, z], -1), np.stack([s, c, z], -1), np.stack([z, z, o], -1)], -2)


def cardan_angles(R):
    """a relative rotation as a CARDAN knuckle takes it: the parent holds the yaw pin, the cross the pitch pin, and what
    is left is a ROLL about the child's own axis: R = Ry(yaw) Rz(pitch) Rx(roll), radians (yaw and pitch are
    yaw_pitch's). C5a-2's probe (c5a2/y01, y02): over the rest motion this order leaves the least roll (joint 22: 24.5
    deg; the pitch pin on the parent 32.5; the roll factored first, about the parent's axis, 47 deg of roll and of
    pitch), so a roll bearing on the child's axis takes it"""
    R = np.asarray(R, np.float64)
    yaw, pitch, _ = yaw_pitch(R)
    M = np.einsum('...ji,...jk->...ik', _ry_n(yaw) @ _rz_n(pitch), R)
    return yaw, pitch, np.arctan2(M[..., 2, 1], M[..., 1, 1])


def motion_limits(chain, seeds=range(1, 17), arms=range(8), ts=None, keep=400):
    """the rest motion's reach at every joint, over 16 seeds x 8 arms x 60 s at 10 fps (the plan's sample,
    forge_cyborg_numbers.py §C): per joint 1..23 the max |yaw|, |pitch|, |roll| (cardan_angles), bend and tilt, their
    p99, every arm-frame's relative rotations (R, float32: a knuckle's gates need the PREVIOUS joint's roll at the same
    frame, the roll ring of its parent segment) and a KEPT set of arm-frames per joint for the clash gates (the `keep`
    largest bends, every sign quadrant of yaw and pitch with its largest bends, pitches, tilts and rolls, and an even
    subsample). Every arm shares the canonical's bind lengths; each arm's own azimuth and bind positions are read from
    the glb"""
    from . import gltf
    R_ = gltf.read(os.path.join(OCTOPUS_DIR, 'octopus.glb'))
    Wn = glb_worlds(R_['json'])
    ts = np.arange(0.0, 60.0, 0.1) if ts is None else ts
    allR = []
    for seed in seeds:
        for j in arms:
            Pb = np.stack([Wn[f'arm{j}_{k:02d}'][:3, 3] for k in range(N_JOINTS)])
            _, F = solve_arm(Pb, ts, j, seed)
            allR.append(rel_rotations(F, chain['tip_rel']))
    Rall = np.concatenate(allR, 0)                                  # (samples, 23, 3, 3)
    yaw, pitch, roll = cardan_angles(Rall)
    _, _, bend = yaw_pitch(Rall)
    tl = tilt(Rall)
    out = dict(samples=int(len(Rall)), joint=list(range(1, N_JOINTS)), R=Rall.astype(np.float32))
    for nm, a in (('yaw', np.abs(yaw)), ('pitch', np.abs(pitch)), ('roll', np.abs(roll)), ('bend', bend),
                  ('tilt', tl)):
        out[nm + '_max'] = np.degrees(a.max(0))
        out[nm + '_p99'] = np.degrees(np.percentile(a, 99, axis=0))
    rng = np.random.default_rng(5)
    kept, kidx = {}, {}
    for jt in range(1, N_JOINTS):
        c = jt - 1
        b = bend[:, c]
        sel = set(np.argsort(-b)[:keep].tolist())
        for sy in (-1, 1):
            for sp in (-1, 1):
                m = np.nonzero((np.sign(yaw[:, c]) == sy) & (np.sign(pitch[:, c]) == sp))[0]
                if len(m):
                    sel |= set(m[np.argsort(-b[m])[:keep // 4]].tolist())
                    sel |= set(m[np.argsort(-np.abs(pitch[m, c]))[:keep // 8]].tolist())
                    sel |= set(m[np.argsort(-tl[m, c])[:keep // 8]].tolist())
                    sel |= set(m[np.argsort(-np.abs(roll[m, c]))[:keep // 8]].tolist())
                    if c >= 1:                                       # the parent segment's roll at the same frame
                        sel |= set(m[np.argsort(-np.abs(roll[m, c - 1]))[:keep // 16]].tolist())
        sel |= set(rng.choice(len(b), size=min(keep, len(b)), replace=False).tolist())
        kidx[jt] = np.array(sorted(sel))
        kept[jt] = Rall[kidx[jt], c]
    out['kept'] = kept
    out['kept_idx'] = kidx
    return out


# ============================================================================================ the design
# Every ratio with its source; [E] marks my estimate with the gate that decides it (C5a's look, the clash replay).
DESIGN = dict(
    core=CORE,              # the shell at 0.95 of the flesh's section, in each of eight directions (§4.4.3 [E-fo])
    rho=0.10,               # the octagon's corner radius over r [E: the look]
    drum=0.80,              # a clevis drum's (cheek's) radius over the section's half-width [E: the look]
    tongue=0.70,            # the tongue's disc radius over the drum's (a clevis lug smaller than its fork [E])
    neck=0.50,              # the neck's half-width over the drum's radius [E]
    tongue_t=0.40,          # the tongue's thickness over r [E]
    gap=(0.12e-3, 0.025),   # every running clearance: max(0.12 mm, 0.025 r): 0.40 mm at joint 9, the machinist's rotor
                            # over stator 0.50 / a shaft in its bore 0.30 [H via kb, A.4.3]; the voxel's 0.12 mm at the tip
    yaw=(1.10, 2.0),        # each knuckle clears 1.10 x its rest motion's largest yaw + 2 deg (motion_limits)
    pitch=(1.20, 1.0),      # and 1.20 x its largest pitch + 1 deg
    yaw_tip=45.0,           # joint 23 never moves in the rest motion (the runtime leaves it at rest): a 45 deg wrist
    can=(0.72, 0.32),       # K8's MOTOR CAN coaxial on the aboral cheek: radius 0.72 of the drum's (the old kit's drum,
                            # RK:277-293 [H]); 0.32 of it tall: a pancake can, not the old 0.85 (the hose arches over it
                            # in a gentle wave; at 0.42 the arches read as bent pipe, C5a's first block-out look)
    can_ring=(0.80, 0.07),  # a bright machined ring at the can's foot ("black anodized joint housings with bright machined
                            # rings", the robot body [H via kb])
    cap=(0.50, 0.10),       # the can's end cap (the old kit's 0.5 x 0.12 of the drum [H], a little flatter)
    axle=(0.62, 0.10),      # the Minsky segments' bolt-circle axle cap (the RoboEnemy's knee [R-rf]; REFS §2.8)
    hose=0.25,              # the bundle over the machine's width (Minsky p11 [M-rf]); width = 2 x 0.95 r (the plan's
                            # machine width: 8.26 mm at joint 8, CYBORG_PLAN §4.4.3)
    clamp=(1.12, 1.30, 0.54),   # clamp collars: across / with the lug / tall, in hose diameters (p02 [M-rf], REFS §4.1)
    saddle=0.90,            # the hose rides this many of its radii above the shell's top flat on its clamp's saddle
                            # (outside the chain; the arches over the cans stay a gentle wave)
    minsky_block=0.12,      # Minsky's junction blocks: 0.12 of the segment long (p11 [M-rf])
    minsky_waist=(0.85, 0.70),  # the waist between them (y, z scale of the section) [E: the look]
    actuator=0.18,          # the actuator cylinder's diameter over the envelope width (p11 [M-rf])
    collar_proud=1.20e-3,   # the collar stands 1.20 mm proud of the flesh (§4.4.4, A.4.1: inside study T's 1.0-3.0 mm p50)
    collar_h=17.0e-3,       # its height: at most 17.0 mm at cut 8 (A.9: study T's per-piece cuff span)
    lug=6.16e-3,            # the screw lug reaches 6.16 mm past the collar: p02's collar has ONE radial lug, so its
                            # 1.30 / 1.12 tube D across (39.1 / 33.7 mm) is 0.18 D on one side: 44.52 - 38.36 mm at cut 8
                            # (C5a's check: 3.08 mm halved it, as if a lug stood on each side)
    roll=6.13e-3,           # the soft roll where the flesh meets the collar (p01's cuff roll, 0.17 of the flesh [M-rf])
    roll_sink=0.9e-3,       # the roll's inner side pressed into the skin (the flesh tucked under it, the crease rule)
    band=11.12e-3,          # the rubber band between the collar and the first segment (p01's distal band, 0.31 [M-rf])
    band_od=0.965,          # its outline over the collar's (a seal 0.95-0.98 of the part beside it [H via kb, A.4.3])
    band_ribs=3,            # a short bellows read [E: the look; the robot body's rubber bellows]
    # ---- C5a-2 (the lead's calls, 10-22)
    span=0.35,              # every knuckle's span (the parent's shell end to the child's shell start) at most 0.35 of the
                            # segment where the clearance allows (call 3: C5a's 23-54 % read as equal white blocks and black
                            # drums): the clevis drums shrink to fit, the cardans are sized to it (c5a2/y02)
    roll_ring=2.0,          # deg: a ROLL BEARING RING where the rest motion's roll about the child's own axis passes this
                            # (call 1; cardan_angles): 17-22 (2.4-24.5 deg); 16 (0.8) takes its roll in the pitch bores'
                            # running clearance (the axle cocks 0.05 mm of its 0.19). At 3 deg, 17's 2.4 cocked its axle
                            # through 95 % of the clearance (the replay's least 0.009 mm, c5a2/y09): a ring there too
    crest_yaw=35.0,         # deg: a hose CREST joint at the pivot turning half the knuckle's yaw where its yaw passes this
                            # (call 5; c5a2/y03: the two-bone arch's least bend radius 1.9 D at joint 22, a corner at its
                            # crest; with the crest joint 3.8 D)
    cardan=dict(            # the cardan's proportions [E: the look; sized by c5a2/y02 and the clash replay]
        hub=0.34,           #   the cross's hub half-size over the section's side apothem A2
        trunnion=0.40,      #   the trunnions' radius over the hub half-size
        lug=0.92,           #   the yokes' lug radius over the hub half-size (at most the hub plus the clearance: the two forks
                            #   interleave, each one's tines narrower than the other's slot, and meet at no angle)
        yaw_out=0.96,       #   the yaw tines' outer faces at +-0.96 A2 (inside the shell's inscribed circle)
        pitch_out=0.66,     #   the pitch tines' outer faces at +-0.66 A2 (a narrow pitch fork swings back less under yaw)
        can=(1.00, 0.42),   #   the yaw motor can: radius over the lug, height over its radius (the proximal cans' 0.72 /
                            #   0.32 of the drum, about the same can over the smaller lug)
        pcan=(0.85, 0.32),  #   the pitch motor can on the +z tine (16-19; 20-22's pitch is the actuator's): a pancake, it
                            #   swings back with the yaw (at 0.90 / 0.40 knuckle 16 spanned 36.4 %)
        pin=(1.30, 0.28),   #   the visible axle ends: a head 1.30 trunnion radii across, 0.28 of them tall
        disc=(0.95, 0.14),  #   the roll ring's disc under the next yoke: radius and thickness over A2
        crank=(1.10, 0.35), #   the pitch axle's crank (20-22): its reach (pin over the axle) and plate thickness over the lug
        eye=(2.2, 0.45),    #   the rod's eye: its radius over the crank pin's, the pin's radius over the trunnion's
        chamfer=1.15),      #   the child faces' chamfers: slope 1.15 x tan(the design pitch or tilt), from the hub / the slot
)


def octagon(A):
    """the sharp octagon whose eight flats lie at apothems A (8,) (metres or r units) in the directions theta_i = 45 i deg
    from the aboral side (+y) toward +z: (8, 2) vertices in (y, z), counter-clockwise in (y, z)"""
    th = np.radians(45.0 * np.arange(8))
    n = np.column_stack([np.cos(th), np.sin(th)])
    V = []
    for i in range(8):
        j = (i + 1) % 8
        M = np.array([n[i], n[j]])
        V.append(np.linalg.solve(M, [A[i], A[j]]))
    return np.array(V)


def section_apothems():
    """the machine's octagon in r units: CORE x the flesh outline's support function in the eight directions (so the
    shell follows the arm's own section: taller than wide, flatter oral, CYBORG_PLAN §4.4.3's 0.95)"""
    return CORE * support(np.radians(45.0 * np.arange(8)))


def rounded_ring(A, rho, m):
    """the octagon of apothems A (metres) with its corners rounded by rho: (8 (m + 1), 2) points in (y, z), m segments
    per corner arc; the flats join each corner's last point to the next corner's first"""
    from . import sdf
    C = sdf.Program.section_core(octagon(A), rho)
    th = np.radians(45.0 * np.arange(8))
    pts = []
    for i in range(8):
        a0, a1 = th[i], th[(i + 1) % 8] + (TAU if i == 7 else 0.0)
        for t in np.linspace(a0, a1, m + 1):
            pts.append(C[i] + rho * np.array([np.cos(t), np.sin(t)]))
    return np.array(pts)


def knuckle_dims(chain, lim, k, ring_parent=False):
    """the CLEVIS knuckle at joint k (9..15, 23), metres, in the pivot's frame (x the parent's chord, y aboral): the drum
    (cheeks) radius rd and its slot half-height hs, the tongue's disc rt, neck half-width wn, thickness ts; the parent's
    shell ends a_p before the pivot, the child's begins a_c after it (its mid-height face), its chamfers ch = (the height
    from which the face leans back, the slope); the design range (yaw_d, pitch_d, tilt_d) and the clearance g.
    C5a-2: the drum's radius is the largest (at most C5a's 0.80 A2) that keeps the span a_p + a_c within DESIGN['span']
    of the segment (the lead's call 3); the chamfers lean back at 1.15 x tan(tilt) from the slot's top (C5a cut 45 deg
    ones). ring_parent: the parent segment's shell turns on a roll ring (segment 22 before the tip's wrist): the drum
    stands on the ring's disc, wholly in front of the turning shell"""
    D = DESIGN
    r = float(chain['r'][k])
    A = section_apothems() * r
    g = max(D['gap'][0], D['gap'][1] * r)
    if k >= N_JOINTS - 1:
        yaw_d, pitch_d = math.radians(D['yaw_tip']), math.radians(D['pitch'][1] + 2.0)
        tilt_d = math.radians(3.0)
    else:
        yaw_d = math.radians(lim['yaw_max'][k - 1] * D['yaw'][0] + D['yaw'][1])
        pitch_d = math.radians(lim['pitch_max'][k - 1] * D['pitch'][0] + D['pitch'][1])
        # the TILT (pitch and roll together, the angle between the two aboral axes) is what the slot and the faces
        # must take (the clash replay found it: tilt())
        tilt_d = math.radians(lim['tilt_max'][k - 1] * D['yaw'][0] + D['yaw'][1])
    tilt_d = max(tilt_d, pitch_d)
    st_, ct_, tt_ = math.sin(tilt_d), math.cos(tilt_d), math.tan(tilt_d)
    ts = D['tongue_t'] * r
    can = k <= MINSKY_FROM
    seg_k = float(chain['seg'][min(k, N_JOINTS - 2)])
    s_ch = D['cardan']['chamfer'] * tt_

    def faces(rd):
        rt = D['tongue'] * rd
        # the tongue tilts inside the slot: any of its points within the drum's footprint (about rd from the pivot, and
        # its own half-thickness more for the tilt's sideways shift) rises by at most that distance x sin(tilt)
        hs = 0.5 * ts + g + (rd + 0.5 * ts) * st_
        # the parent's flat end clears the tongue's disc: its rim's back edge moves back by its half-thickness x sin(tilt)
        a_p = max(rt + g, rt * ct_ + 0.5 * ts * st_ + g)
        rc_ = (D['can'][0] if can else D['axle'][0]) * rd
        s = s_ch if (A[0] - hs) * s_ch >= 0.25e-3 else 0.0
        # the child's face: its foot (the slot's top) clears the drum's front line, inclined by the tilt; above it the
        # chamfer leans back at s >= tan(tilt); over A0 the can's front line; the two-cylinder rule for the yaw (the
        # plan's tan(theta / 2) = a / w); the parent's face
        a_c = max(rd / ct_ + hs * tt_ + g, rc_ / ct_ + A[0] * tt_ + g - (A[0] - hs) * s,
                  A[2] * math.tan(0.5 * yaw_d) + g, a_p + g)
        if s == 0.0:
            a_c = max(a_c, rd / ct_ + A[0] * tt_ + g)
        return rt, hs, a_p, a_c, s
    rd = D['drum'] * A[2]
    if k < N_JOINTS - 1 and sum(faces(rd)[2:4]) > D['span'] * seg_k:
        lo, hi = 0.30 * A[2], rd                         # the span's largest drum, by bisection (a floor at 0.30 A2)
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if sum(faces(mid)[2:4]) <= D['span'] * seg_k else (lo, mid)
        rd = lo
    rt, hs, a_p, a_c, s = faces(rd)
    disc = None
    if ring_parent:                                      # on the roll ring's disc, in front of the turning shell
        Rb, wb = D['cardan']['disc'][0] * A[2], D['cardan']['disc'][1] * A[2]
        x_d0 = 0.88 * rd                                 # the disc's front: under the cheeks' backs, behind the tongue
        disc = (Rb, wb, x_d0)
        a_p = max(a_p, x_d0 + wb + g)
    out = dict(kind='clevis', k=k, r=r, A=A, g=g, yaw_d=yaw_d, pitch_d=pitch_d, tilt_d=tilt_d, rd=rd, rt=rt,
               wn=D['neck'] * rd, ts=ts, hs=hs, a_p=a_p, a_c=a_c, ch=(hs, s), can=can, rolls=False,
               hc=D['can'][1] * rd if can else D['axle'][1] * rd, disc=disc)
    out['top'] = A[0] + out['hc']
    out['can_r'] = (D['can'][0] if can else D['axle'][0]) * rd
    return out


def cardan_dims(chain, lim, k, ring_parent=False, act=False):
    """the CARDAN knuckle at joint k (16..22), metres, in the pivot's frame (x the parent's chord, y aboral, z lateral):
    the cross (hub half-size h, trunnion radius t), the forks' lugs b, the yaw tines' outer faces +-Yo (the parent's yaw
    yoke) and the pitch tines' +-Zo (the child's pitch yoke), the yaw can (Rc, Hc) on the top lug, the pitch can pcan
    on the +z tine (16-19) or the actuator's crank, eye and rod (act: 20-22), the visible axle heads (pin), the roll
    ring's disc (ring_parent: the parent segment's shell turns on it). The parent's shell end x_S (= a_p) stands behind
    everything of the child's pitch side swung through the design yaw and pitch (x_Y the yaw yoke's root, the disc's
    front), the child's face x_P (= a_c) clears the yaw lugs, the can and the axle head through the pitch (its chamfers
    ch lean back from the hub's top), both faces under the two-cylinder rule for the yaw. rolls: the motion's roll about
    the child's axis passes DESIGN['roll_ring'] (cardan_angles), so the child segment's shell turns on a roll ring at
    its distal end"""
    D = DESIGN
    C = D['cardan']
    r = float(chain['r'][k])
    A = section_apothems() * r
    A0, A2 = A[0], A[2]
    g = max(D['gap'][0], D['gap'][1] * r)
    yaw_d = math.radians(lim['yaw_max'][k - 1] * D['yaw'][0] + D['yaw'][1])
    pitch_d = math.radians(lim['pitch_max'][k - 1] * D['pitch'][0] + D['pitch'][1])
    roll_m = float(lim['roll_max'][k - 1])
    h = C['hub'] * A2
    t = C['trunnion'] * h
    b = C['lug'] * h
    Yo, Zo = C['yaw_out'] * A2, C['pitch_out'] * A2
    Rc, Hc = C['can'][0] * b, C['can'][1] * C['can'][0] * b
    # the axle heads: their step over the trunnion and their height at least two of the bake's voxels (BAKE_STEP: at
    # 0.3 t the small knuckles' steps, 0.09-0.15 mm, baked to nothing, C5a-2's first forge gate)
    pin_r, pin_h = max(C['pin'][0] * t, t + BAKE_STEP), max(C['pin'][1] * t, BAKE_STEP)
    pcan = None if act else (C['pcan'][0] * b, C['pcan'][1] * C['pcan'][0] * b)
    out = dict(kind='cardan', k=k, r=r, A=A, g=g, yaw_d=yaw_d, pitch_d=pitch_d, tilt_d=pitch_d, roll_max=roll_m,
               rolls=roll_m > D['roll_ring'], act=act, h=h, t=t, b=b, Yo=Yo, Zo=Zo, Rc=Rc, Hc=Hc, pin=(pin_r, pin_h),
               pcan=pcan, can=True, top=Yo + Hc, can_r=Rc)
    # the child's pitch side in its frame from the pivot (it turns with the yaw about the yaw axis, and with the pitch
    # about its own): the lugs' rims, the pitch can's or the crank's, eye's and pin head's outlines, the -z axle head
    a = np.linspace(0.0, TAU, 72, endpoint=False)
    rim = lambda rr, zz, cy=0.0: np.column_stack([rr * np.cos(a), cy + rr * np.sin(a), np.full_like(a, zz)])
    pts = [rim(b, s_ * zz) for s_ in (1.0, -1.0) for zz in (h + g, Zo)]
    pts.append(rim(pin_r, -(Zo + g + pin_h)))
    if act:
        rm = float(radius_at(chain, chain['x'][k] + 0.5 * float(chain['seg'][k])))
        r_cyl = 0.5 * D['actuator'] * 2.0 * CORE * rm
        r_rod = 0.45 * r_cyl
        r_pin = C['eye'][1] * t
        # the rod's root ends inside the eye's solid wall: past the pin's bore (r_pin + g) by 0.3 r_rod, its disc
        # (r_rod across) inside the eye's rim by 10 % (at 2.2 r_pin alone 22's wall was 0.04 mm and the root stood in
        # the bore's hole, 0.013 mm off the pin: C5a-2's replay, c5a2/y09)
        x_r0 = r_pin + g + 0.3 * r_rod
        r_eye = max(C['eye'][0] * r_pin, math.sqrt(x_r0 ** 2 + (1.1 * r_rod) ** 2))
        lc, ct = C['crank'][0] * b, C['crank'][1] * b
        et = max(0.8 * ct, 2.2 * r_rod)                # the eye at least the rod's thickness (thinner, the rod's root
                                                       # grazed the crank plate: C5a-2's low replay, 0.02 mm)
        z_a = A2 + g + r_rod                          # the rod passes the child's proximal block a clearance off its side
        ze0, ze1 = z_a - 0.5 * et, z_a + 0.5 * et     # the eye on the crank pin
        zc1 = ze0 - g                                 # the crank plate's outer face
        zc0 = zc1 - ct
        assert zc0 > Zo + g, f'knuckle {k}: the crank plate ({zc0 * 1e3:.2f} mm) inside the +z tine ({Zo * 1e3:.2f} mm)'
        wc = max(1.3 * t, 1.8 * r_pin)
        # the crank pin's head over the eye: its step and height at least two of the bake's voxels
        ph_r, ph = max(1.35 * r_pin, r_pin + BAKE_STEP), max(0.6 * r_pin, BAKE_STEP)
        out.update(r_cyl=r_cyl, r_rod=r_rod, r_pin=r_pin, r_eye=r_eye, x_r0=x_r0, lc=lc, ct=ct, et=et, z_a=z_a,
                   ze=(ze0, ze1), zc=(zc0, zc1), wc=wc, pin_head=(ph_r, ph))
        for zz in (zc0, zc1):                         # the crank plate: a lever from the axle to the pin
            pts += [rim(wc, zz), rim(wc, zz, lc)]
        pts.append(rim(r_eye, ze0, lc))               # the eye and the pin's head over it
        pts.append(rim(max(r_eye, ph_r), ze1 + g + ph, lc))
    else:
        pts += [rim(pcan[0], zz) for zz in (Zo, Zo + pcan[1])]
    Q = np.concatenate(pts)
    Yg, Pg = np.meshgrid(np.linspace(-yaw_d, yaw_d, 61), np.linspace(-pitch_d, pitch_d, 9))
    W = np.einsum('rij,nj->rni', _ry_n(Yg.ravel()) @ _rz_n(Pg.ravel()), Q).reshape(-1, 3)
    back = lambda lat: max(0.0, float(-W[(np.abs(W[:, 1]) <= A0) & (np.abs(W[:, 2]) <= lat), 0].min(initial=0.0)))
    disc = None
    if ring_parent:
        Rb, wb = C['disc'][0] * A2, C['disc'][1] * A2
        x_Y = back(Rb) + g                            # the disc's front
        x_S = max(x_Y + wb + g, back(A2) + g)         # the turning shell's end behind it
        disc = (Rb, wb, x_Y)
    else:
        x_Y = x_S = back(A2) + g
    # the child's face at mid-height and its chamfers leaning back at s from y_ch = h + g: the hub's front corners, the
    # yaw lugs' front line (inclined by the pitch) at the chamfer's foot, the yaw can's and the bottom axle head's
    tp, cp = math.tan(pitch_d), math.cos(pitch_d)
    y_ch = h + g
    s = C['chamfer'] * tp
    if (A0 - y_ch) * s < 0.25e-3:
        s = 0.0
    yb = Yo + g + pin_h
    x_P = max(h * (cp + math.sin(pitch_d)) + g, b / cp + y_ch * tp + g,
              Rc / cp + Yo * tp + g - (Yo - y_ch) * s, pin_r / cp + yb * tp + g - (yb - y_ch) * s)
    if s == 0.0:
        x_P = max(x_P, b / cp + Yo * tp + g, Rc / cp + (Yo + Hc) * tp + g)
    # the two-cylinder rule for the yaw (flat faces of half-width A2): x_P + x_S cos > A2 sin and its mirror
    sy, cy = math.sin(yaw_d), math.cos(yaw_d)
    x_P = max(x_P, A2 * sy - x_S * cy + g)
    x_S = max(x_S, A2 * sy - x_P * cy + g)
    if ring_parent:                                   # the disc stays a bearing's clearance in front of the shell's end
        x_Y = x_S - disc[1] - g
        disc = (disc[0], disc[1], x_Y)
    else:
        x_Y = x_S
    out.update(x_Y=x_Y, x_S=x_S, x_P=x_P, a_p=x_S, a_c=x_P, ch=(y_ch, s), disc=disc)
    return out


def hose_radius(chain, x):
    """the bundle's radius at x: 0.25 of the machine's width 2 x 0.95 r (DESIGN['hose'])"""
    return 0.5 * DESIGN['hose'] * 2.0 * CORE * radius_at(chain, x)


def body_k(body):
    """the joint a body's (or joint's) name belongs to: its origin is that joint's x on the straight bind (a helper of
    knuckle k sits at its pivot, joint k)"""
    return int(body) if isinstance(body, (int, np.integer)) else int(body[4:6])


def body_kind(body):
    """'bone', or a helper's kind: 'cross', 'shell', 'rod', 'crest'"""
    return 'bone' if isinstance(body, (int, np.integer)) or len(body) == 6 else body[7:]


def bone_name(k):
    return f'arm_{int(k):02d}'


def shell_body(des, k):
    """the body that carries segment k's shell: its bone, or on a ring segment the turning shell's helper"""
    return f'arm_{k:02d}_shell' if k in des['ring'] else bone_name(k)


def helper_joints(chain, des):
    """the skeleton's helper joints after the bones (C5a-2), each dict(name, parent, T its rest translation in the
    parent, kind, k): the CROSS of every cardan knuckle (child of the parent bone at the pivot; turns Ry(yaw)), the
    turning SHELL of every ring segment (child of its bone; turns Rx(-roll)), the actuator ROD of 20-22 (child of its
    segment's shell; slides along x by the crank's reach x sin(pitch)), the hose CREST of every knuckle whose yaw passes
    DESIGN['crest_yaw'] (child of the parent bone at the pivot; turns Ry(yaw / 2)). pose_joints applies the rules,
    export_glb writes them with the rules in the extras"""
    seg = chain['seg']
    H = [dict(name=f'arm_{k:02d}_cross', parent=bone_name(k - 1), T=[float(seg[k - 1]), 0.0, 0.0], kind='cross', k=k)
         for k in CARDAN]
    H += [dict(name=f'arm_{k:02d}_shell', parent=bone_name(k), T=[0.0, 0.0, 0.0], kind='shell', k=k)
          for k in sorted(des['ring'])]
    H += [dict(name=f'arm_{k:02d}_rod', parent=shell_body(des, k), T=[0.0, 0.0, 0.0], kind='rod', k=k)
          for k in sorted(des['act'])]
    H += [dict(name=f'arm_{k:02d}_crest', parent=bone_name(k - 1), T=[float(seg[k - 1]), 0.0, 0.0], kind='crest', k=k)
          for k in sorted(des['crest'])]
    return H


def design(chain, lim):
    """the whole machine's dimensions (asset frame, metres; see the module notes): the knuckles 9..23 (clevis or
    cardan), every segment's shell span (local to its body: x from its joint), the segments whose shells turn on a roll
    ring (ring), carry an actuator (act), the knuckles whose hose arch has a crest joint (crest), the flange's stack,
    the hose's path and its clamps, the skeleton's helper joints, the joints' and the bodies' names"""
    D = DESIGN
    x = chain['x']
    seg = chain['seg']
    kn, rings = {}, set()
    for k in range(CUT + 1, N_JOINTS):
        if k in CARDAN:
            kn[k] = cardan_dims(chain, lim, k, ring_parent=(k - 1) in rings, act=k >= MINSKY_FROM)
            if kn[k]['rolls']:
                rings.add(k)
        else:
            kn[k] = knuckle_dims(chain, lim, k, ring_parent=(k - 1) in rings)
    act = {k for k in CARDAN if k >= MINSKY_FROM}
    crest = {k for k in range(CUT + 1, N_JOINTS - 1) if lim['yaw_max'][k - 1] > D['crest_yaw']}
    ring = chain['ring']
    # ---- the flange stack (group J0's frame: x from joint J0 along chord J0)
    x8 = float(seg[J0])                                      # joint 8's pivot
    band0, band1 = x8 - 0.5 * D['band'], x8 + 0.5 * D['band']
    collar1 = band0                                          # the band starts at the collar's distal face
    collar0 = collar1 - D['collar_h']
    lap = ring['x'] - collar0                                # the collar's lip reaches this far above the cut ring
    roll_x = collar0 + 0.15 * D['roll']                      # the roll rides the lip
    # the stack beyond the cut ring: the collar's part past the ring and half the band, against the ring-to-pivot run
    fl = dict(x8=x8, band=(band0, band1), collar=(collar0, collar1), lap=lap, roll_x=roll_x,
              roll_reach=ring['x'] - (roll_x - 0.5 * D['roll']), pinned=ring['x'] - ring['x_before'],
              ring_to_pivot=x8 - ring['x'], stack=(D['collar_h'] - lap) + 0.5 * D['band'])
    # ---- the segments' shells: group k spans joint k -> k + 1 (the tip: to the arm's end)
    segs = {}
    for k in range(CUT, N_JOINTS):
        L = float(seg[k]) if k < N_JOINTS - 1 else float(chain['L_arm'] * (1.0 - chain['js'][-1]))
        x0 = kn[k]['a_c'] if k > CUT else band1 - x8 - 0.18 * D['band']     # segment 8: from its band boss
        x1 = L - kn[k + 1]['a_p'] if k + 1 < N_JOINTS else L
        segs[k] = dict(k=k, L=L, x0=x0, x1=x1, minsky=k >= MINSKY_FROM and k < N_JOINTS - 1, tip=k == N_JOINTS - 1,
                       ring=k in rings, act=k in act)
    # ---- the hose: ONE clamp collar on every segment's top flat, at the middle of its shell (each loop then spans one
    # knuckle, Minsky's "looping across each joint"), an arch over each knuckle's can between them
    rh = lambda xa: float(hose_radius(chain, xa))
    top = lambda xa: float(section_apothems()[0] * radius_at(chain, xa))
    clamps = []
    for k in range(CUT, N_JOINTS):
        s_ = segs[k]
        xa = x[k] + s_['x0']
        xb = x[k] + s_['x1']
        xc = xa + (0.40 if s_['tip'] else 0.5) * (xb - xa)
        r_ = rh(xc)
        clamps.append(dict(k=k, x=xc, rh=r_, D=2.0 * r_, y=top(xc) + (1.0 + D['saddle']) * r_,
                           L=D['clamp'][2] * 2.0 * r_, R=0.5 * D['clamp'][0] * 2.0 * r_,
                           # the lug's reach from the axis: the collar's radius plus p02's one-sided 0.18 D (1.30 D
                           # across with the lug, 1.12 without); 0.65 D read 1.30 D as a symmetric diameter (1.21 D)
                           R_lug=(0.5 * D['clamp'][0] + D['clamp'][1] - D['clamp'][0]) * 2.0 * r_))
    des = dict(kn=kn, segs=segs, flange=fl, clamps=clamps, rh=rh, top=top, ring=rings, act=act, crest=crest)
    des['helpers'] = helper_joints(chain, des)
    des['joints'] = [bone_name(k) for k in range(J0, N_JOINTS)] + [h_['name'] for h_ in des['helpers']]
    des['bodies'] = [bone_name(k) for k in range(J0, N_JOINTS)] + [h_['name'] for h_ in des['helpers']
                                                                    if h_['kind'] != 'crest']
    des['hose'] = hose_path(chain, des)
    return des


def collar_outline(chain, M=96):
    """the collar's section (y, z), metres, M points counter-clockwise from the aboral side: the flesh outline at the cut
    ring offset 1.20 mm outward (a socket shaped to the limb, as study T's cuffs and a prosthetic socket are), and the
    flesh outline there itself"""
    th = np.linspace(0.0, TAU, M, endpoint=False)
    r0 = chain['ring']['r_nominal']
    f = flesh_profile(th) * r0
    P = np.column_stack([f * np.cos(th), f * np.sin(th)])
    d = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    n = np.column_stack([d[:, 1], -d[:, 0]])
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    if (n * P).sum() < 0:
        n = -n
    return P + DESIGN['collar_proud'] * n, P, n


def resample_polygon(P, M, th0=0.0):
    """a closed polygon (y, z) re-sampled at M points by angle about the origin (star-shaped polygons: the octagon,
    the flesh outline), from theta th0 counter-clockwise"""
    ang = np.unwrap(np.arctan2(P[:, 1], P[:, 0]))
    if ang[-1] < ang[0]:
        P, ang = P[::-1], np.unwrap(np.arctan2(P[::-1, 1], P[::-1, 0]))
    out = []
    for t in th0 + np.linspace(0.0, TAU, M, endpoint=False):
        d = np.array([math.cos(t), math.sin(t)])
        best = None
        for i in range(len(P)):
            a, b = P[i], P[(i + 1) % len(P)]
            # the ray from the origin along d against edge a-b
            Mx = np.array([d, a - b]).T
            if abs(np.linalg.det(Mx)) < 1e-15:
                continue
            s, u = np.linalg.solve(Mx, a)
            if s > 0 and -1e-9 <= u <= 1 + 1e-9 and (best is None or s < best):
                best = s
        out.append(d * best)
    return np.array(out)


def hose_path(chain, des, step=0.4e-3):
    """the bundle's centreline (asset frame, z = 0) and radius: from its bulkhead fitting on the collar's top, over the
    band, through every clamp (where it runs straight along the clamp's axis), arching over each knuckle so its
    underside clears the can (or axle cap) by the knuckle's clearance plus a margin, to its end past the tip's clamp.
    Returns dict(P (n, 3), r (n,), x the clamps' and fitting's stations, bone weights per point (n, 2) of (bone, w) pairs:
    rigid on a clamp's bone inside the clamp, a smooth ramp across each knuckle centred on its pivot)"""
    x = chain['x']
    kn, fl, cl = des['kn'], des['flange'], des['clamps']
    rh, top = des['rh'], des['top']
    Pc, _, _ = collar_outline(chain)
    y_collar = float(Pc[:, 0].max())
    xf = 0.5 * (fl['collar'][0] + fl['collar'][1])
    r8 = rh(xf)
    # the fitting is a 45 deg ELBOW (C5a-2): its boss on the collar's top, its ferrule leaning 45 deg along the arm; the
    # hose leaves it straight and turns the other 45 deg on an arc of 3 of its radii (U4: a tube bent to R stretches its
    # chart (R - r) / R inside and (R + r) / R outside, inside the 1/1.5 .. 1.5 band from R = 2.8 r; C5a's upright
    # ferrule turned 90 deg on 1.4 r, 2.2 r at most before joint 8)
    d0 = np.array([math.sin(math.pi / 4.0), math.cos(math.pi / 4.0), 0.0])
    E = np.array([xf, y_collar + 0.5 * r8, 0.0])           # the boss's top, where the ferrule stands
    A0 = E + 0.95 * r8 * d0                                 # out of the ferrule (its tip at 0.72 r)
    Rr = 3.0 * r8
    Cc = A0 + Rr * np.array([d0[1], -d0[0], 0.0])
    # the stations: (x, y, slope 0) at the fitting's exit (the arc's level end), every clamp; peaks over the band and
    # every knuckle
    st = [dict(x=float(Cc[0]), y=float(Cc[1] + Rr), kind='fitting', bone=J0, body=bone_name(J0))]
    band_top = DESIGN['band_od'] * y_collar
    st.append(dict(x=fl['x8'], y=band_top + rh(fl['x8']) + 1.5e-3, kind='peak', joint=CUT, w=0.5 * DESIGN['band']))
    for c in cl:
        st.append(dict(x=c['x'], y=c['y'], kind='clamp', bone=c['k'], body=shell_body(des, c['k']), L=c['L']))
        k1 = c['k'] + 1
        if k1 < N_JOINTS:
            K = kn[k1]
            # the can's (or axle cap's) rim plus half the hose's radius must pass under the wave: the peak height
            # solved below from the smoothstep's fall at that distance
            w = K['can_r'] + 0.5 * rh(x[k1])
            st.append(dict(x=x[k1], y=K['top'] + K['g'] + rh(x[k1]) + max(0.3e-3, 0.04 * K['r']), kind='peak',
                           joint=k1, w=w))
    # each peak raised so the wave (smoothstep from the stations either side) clears its floor at +-w, and rising at
    # least 5 % of its span above its higher neighbour: the SLACK (an arch never taut when the knuckle's tilt lifts the
    # clamps apart; the hose gate measures it per joint)
    drop = set()
    for i, s_ in enumerate(st):
        if s_['kind'] != 'peak' or i == 0 or i + 1 >= len(st):
            continue
        need = s_['y']
        if s_['joint'] == CUT:
            # over the band (joint 8): it turns in pure yaw, and with the fitting 2.3 mm before the pivot and the clamp
            # past it the yaw only SHORTENS that arch: no slack wanted. No peak at all where the fitting's own descent to
            # the clamp clears the band's floor over its width (a peak there, 2.3 mm past the fitting's level end and
            # 0.4 mm over it, bent the tube to 0.8 of its radii: c5a2/y04)
            a_, b_ = st[i - 1], st[i + 1]
            xa_, xb_ = a_['x'], b_['x'] - 0.5 * b_.get('L', 0.0)
            curve = lambda xq: a_['y'] + (b_['y'] - a_['y']) * (lambda t_: t_ * t_ * (3.0 - 2.0 * t_))(
                min(max((xq - xa_) / max(xb_ - xa_, 1e-9), 0.0), 1.0))
            if min(curve(s_['x'] - s_['w']), curve(s_['x'] + s_['w'])) >= need:
                drop.add(i)
                continue
        y_p = need
        spans = []
        for nb, sgn in ((st[i - 1], -1.0), (st[i + 1], 1.0)):
            edge = nb['x'] + sgn * -0.5 * nb.get('L', 0.0) if nb['kind'] == 'clamp' else nb['x']
            span = abs(s_['x'] - edge)
            spans.append(span)
            u = min(0.95, s_['w'] / max(span, 1e-9))
            f = 3.0 * u * u - 2.0 * u ** 3
            y_p = max(y_p, (need - nb['y'] * f) / (1.0 - f))
        # (over the band, joint 8, none: pure yaw only shortens its arch, the note above)
        y_p = max(y_p, max(st[i - 1]['y'], st[i + 1]['y']) + (0.0 if s_['joint'] == CUT else 0.05) * sum(spans))
        s_['y'] = y_p
    st = [s_ for i, s_ in enumerate(st) if i not in drop]
    # the distal end DIVES into the tip segment's top flat and ends a diameter under it (a cable entering the machine;
    # the feed lines' ends dive 0.91-1.74 D, A.2.1): never a free end. C5a's check: it stopped 1.2 D past its last
    # clamp, in the air, a flat cap over the tip
    c_end = cl[-1]
    end_x = c_end['x'] + 0.5 * c_end['L'] + 2.5 * c_end['D']     # its rounded end inside the shell, short of the boss
    st.append(dict(x=end_x, y=top(end_x) - c_end['D'], kind='end', bone=N_JOINTS - 1, body=bone_name(N_JOINTS - 1)))
    # a C1 curve: straight through each clamp (its length), Hermite arcs with level tangents between stations
    pts = []
    xs = [s_['x'] for s_ in st]
    for i in range(len(st) - 1):
        a, b = st[i], st[i + 1]
        xa = a['x'] + (0.5 * a['L'] if a['kind'] == 'clamp' else 0.0)
        xb = b['x'] - (0.5 * b['L'] if b['kind'] == 'clamp' else 0.0)
        if a['kind'] == 'clamp':
            n = max(2, int(math.ceil(a['L'] / step)))
            for t in np.linspace(-0.5, 0.5, n, endpoint=False):
                pts.append((a['x'] + t * a['L'], a['y']))
        n = max(4, int(math.ceil((xb - xa) / step)))
        for t in np.linspace(0.0, 1.0, n, endpoint=False):
            h = t * t * (3.0 - 2.0 * t)
            pts.append((xa + (xb - xa) * t, a['y'] + (b['y'] - a['y']) * h))
    pts.append((st[-1]['x'], st[-1]['y']))
    P = np.array([[p[0], p[1], 0.0] for p in pts])
    # the elbow's run: from inside its ferrule straight along it, then the arc from 45 deg to level at the station
    P0 = E - 0.6 * r8 * d0
    run = np.array([P0 + t * (A0 - P0) for t in np.linspace(0.0, 1.0, 4, endpoint=False)])
    arc = np.array([Cc + Rr * np.array([-math.cos(a_), math.sin(a_), 0.0])
                    for a_ in np.linspace(0.25 * math.pi, 0.5 * math.pi, 10, endpoint=False)])
    P = np.vstack([run, arc, P])
    keep = np.concatenate([[True], np.linalg.norm(np.diff(P, axis=0), axis=1) > 1.0e-7])
    P = P[keep]
    r = np.array([rh(min(max(p[0], xf), end_x)) for p in P])
    # the end: the bundle tapers into a rounded end cap past the tip's clamp
    w = hose_skin(P[:, 0], st, chain, des)
    return dict(P=P, r=r, stations=st, w=w, x_fitting=xf, y_collar=y_collar, end_x=end_x,
                fitting=dict(E=E, d0=d0, r8=r8))


def _ramp(u, ease_lo=True, ease_hi=True, e=0.25):
    """a blend weight over u in [0, 1]: linear, its slope eased in over e at the clamped end(s), so the hose leaves a
    clamp straight (C5a's smoothstep centred on the pivot put the whole turn there: a corner at the crest)"""
    u = float(np.clip(u, 0.0, 1.0))
    lo = (min(u, e) ** 2 / (2.0 * e)) if ease_lo else min(u, e)
    mid = max(0.0, min(u, 1.0 - e) - e)
    hi = 0.0
    if u > 1.0 - e:
        hi = ((e * e - (1.0 - u) ** 2) / (2.0 * e)) if ease_hi else u - (1.0 - e)
    tot = (0.5 * e if ease_lo else e) + (1.0 - 2.0 * e) + (0.5 * e if ease_hi else e)
    return (lo + mid + hi) / tot


def hose_skin(xh, st, chain, des):
    """per hose point: two (joint index, weight) pairs, the indices into des['joints']. Rigid on a hold's body inside it
    (the fitting's bone, a clamp's shell body, the end's bone); between two holds a (segment k - 1) and b (segment k)
    across knuckle k a linear blend eased at both clamps (_ramp), or where knuckle k has a CREST joint (it turns half the
    yaw at the pivot) a -> crest over the parent half and crest -> b over the child half, each eased at its clamp only:
    each half takes half the turn (c5a2/y03: the least bend radius 3.8 hose diameters at joint 22 against C5a's 1.9)"""
    x = chain['x']
    J = {n: i for i, n in enumerate(des['joints'])}
    holds = [s_ for s_ in st if s_['kind'] in ('fitting', 'clamp', 'end')]
    out = np.zeros((len(xh), 2, 2))
    for i, xv in enumerate(xh):
        j = 0
        while j + 1 < len(holds) and holds[j + 1]['x'] <= xv:
            j += 1
        a = holds[j]
        b = holds[min(j + 1, len(holds) - 1)]
        xa, xb = a['x'] + 0.5 * a.get('L', 0.0), b['x'] - 0.5 * b.get('L', 0.0)
        if a is b or a['body'] == b['body'] or xv <= xa or xv >= xb:
            near = a if abs(xv - a['x']) <= abs(xv - b['x']) else b
            out[i] = [[J[near['body']], 1.0], [J[near['body']], 0.0]]
            continue
        ja, jb = J[a['body']], J[b['body']]
        kk = body_k(b['body'])                               # the knuckle between them
        xp = x[kk]
        if kk in des['crest']:
            jc = J[f'arm_{kk:02d}_crest']
            if xv < xp:
                w = _ramp((xv - xa) / max(xp - xa, 1e-9), True, False)
                out[i] = [[ja, 1.0 - w], [jc, w]]
            else:
                w = _ramp((xv - xp) / max(xb - xp, 1e-9), False, True)
                out[i] = [[jc, 1.0 - w], [jb, w]]
        else:
            w = _ramp((xv - xa) / max(xb - xa, 1e-9), True, True)
            out[i] = [[ja, 1.0 - w], [jb, w]]
    return out


# ============================================================================================ the high (SDFs)
def _brk(size):
    """an edge break: the machinist's 0.4 mm (A.4.3), held under 7 % of the part it breaks"""
    return min(0.4e-3, 0.07 * size)


def cheek_profiles(K):
    """the clevis drum at a knuckle as two (r, y) profiles about its yaw axis (y through the pivot): the aboral cheek
    with its motor can (ring, can, cap) or axle cap, and the oral cheek; and the tongue's disc"""
    D = DESIGN
    rd, hs, A = K['rd'], K['hs'], K['A']
    b = _brk(rd)
    A0, A4 = A[0], A[4]
    top = [(0.0, hs), (rd - b, hs), (rd, hs + b), (rd, A0 - b), (rd - b, A0)]
    if K['can']:
        # the foot ring and the can; the can's end cap (0.5 x 0.10 of the drum) is the texture tier's (a bright disc
        # with its bolt dots and status lamp): at 0.1-1.1 mm tall it is under 4 texels on most of the chain
        rg, hg = D['can_ring'][0] * rd, D['can_ring'][1] * rd
        rc, hc = D['can'][0] * rd, K['hc']
        bc = _brk(rc)
        top += [(rg, A0), (rg, A0 + hg), (rc, A0 + hg), (rc, A0 + hc - bc), (rc - bc, A0 + hc), (0.0, A0 + hc)]
    else:
        ra, ha = D['axle'][0] * rd, K['hc']
        ba = _brk(ha * 2.0)
        top += [(ra, A0), (ra, A0 + ha - ba), (ra - ba, A0 + ha), (0.0, A0 + ha)]
    bot = [(0.0, -hs), (0.0, -A4), (rd - b, -A4), (rd, -A4 + b), (rd, -hs - b), (rd - b, -hs)]
    rt, ts = K['rt'], K['ts']
    bt = _brk(ts)
    tongue = [(0.0, -0.5 * ts), (rt - bt, -0.5 * ts), (rt, -0.5 * ts + bt), (rt, 0.5 * ts - bt), (rt - bt, 0.5 * ts),
              (0.0, 0.5 * ts)]
    return np.array(top), np.array(bot), np.array(tongue)


def cheek_split(K, sink=0.15e-3):
    """C5a-3: the aboral cheek (cheek_profiles' top) as primitives for the bake's own-piece search: the cheek, and the
    motor can or the axle cap standing on it, sunk `sink` (at most half the ring) into what it stands on so the pieces
    are one solid, the same solid as top. C5c (the lead's decision 4): a can's FOOT RING is its own primitive between
    them (the cheek's top a plain face at A0, the ring a disc of the ring's radius and height sunk into the cheek, the
    can sunk into the ring), and the low's face is split at the ring's radius (knuckle_parts): the ring's 0.26-0.51 mm
    step inside the cheek's piece let the texels beside its wall slide up the wall's voxel fillet, a dotted dark line round
    every foot ring (C5a-3's check, chk04_drum9_ring). One primitive held the face and the can's wall together in C5a-2:
    a speckled ring at every can's base. Returns [(name suffix, profile)]: ('aboral', cheek), ('ring', ring) for a can,
    ('can' | 'cap', feature)"""
    D = DESIGN
    rd, hs, A = K['rd'], K['hs'], K['A']
    b = _brk(rd)
    A0 = A[0]
    cheek = [(0.0, hs), (rd - b, hs), (rd, hs + b), (rd, A0 - b), (rd - b, A0), (0.0, A0)]
    if K['can']:
        rg, hg = D['can_ring'][0] * rd, D['can_ring'][1] * rd
        rc, hc = D['can'][0] * rd, K['hc']
        bc = _brk(rc)
        s = min(sink, 0.5 * hg)
        ring = [(0.0, A0 - s), (rg, A0 - s), (rg, A0 + hg), (0.0, A0 + hg)]
        feat = [(0.0, A0 + hg - s), (rc, A0 + hg - s), (rc, A0 + hc - bc), (rc - bc, A0 + hc), (0.0, A0 + hc)]
        return [('aboral', np.array(cheek)), ('ring', np.array(ring)), ('can', np.array(feat))]
    ra, ha = D['axle'][0] * rd, K['hc']
    ba = _brk(ha * 2.0)
    feat = [(0.0, A0 - sink), (ra, A0 - sink), (ra, A0 + ha - ba), (ra - ba, A0 + ha), (0.0, A0 + ha)]
    return [('aboral', np.array(cheek)), ('cap', np.array(feat))]


def body_nodes(chain, des, k, n_min=6):
    """segment k's shell as PSWEEP nodes in its group's frame: x positions, the key per node (0 the full octagon, 1 the
    chamfered proximal end, 2 Minsky's waist), the scale (the flesh's r at the node), and the keys (in r units: the
    octagon apothems with the chamfers / the waist applied, each a CORE for the corner radius rho)"""
    from . import sdf
    D = DESIGN
    s_ = des['segs'][k]
    x0, x1, L = s_['x0'], s_['x1'], s_['L']
    xk = chain['x'][k]
    rm = float(radius_at(chain, xk + 0.5 * (x0 + x1)))
    rho = D['rho'] * rm
    Au = section_apothems()
    K = des['kn'].get(k)
    if s_['tip']:
        x1 = x0 + 0.62 * (L - x0)                             # the turned end boss takes the rest
    # the keys in an order no blend passes through a third: full, [waist] (the proximal chamfers are a cut:
    # chamfer_cuts, group_program)
    keys = []
    i_full = float(len(keys))
    keys.append(Au.copy())
    # the PSWEEP is its core's extrusion between the end nodes' planes, offset by rho (sdf.py sd_psweep): the nodes
    # sit rho inside the span so the solid's flat ends fall exactly on x0 and x1
    xa, xb = x0 + rho, x1 - rho
    xs, kk = [xa], [i_full]
    if s_['minsky']:
        bl = D['minsky_block'] * L
        tr = 0.5 * bl
        Aw = Au.copy()
        sy, sz = D['minsky_waist']
        Aw[[0, 4]] *= sy
        Aw[[2, 6]] *= sz
        Aw[[1, 3, 5, 7]] *= 0.5 * (sy + sz)
        keys.append(Aw)
        iw = float(len(keys) - 1)
        for xv, kv in ((x0 + bl, i_full), (x0 + bl + tr, iw), (x1 - bl - tr, iw), (x1 - bl, i_full)):
            if xb - 1e-5 > xv > xs[-1] + 1e-5:
                xs.append(xv)
                kk.append(kv)
    xs.append(xb)
    kk.append(i_full)
    # densify (the taper is a curve: nodes every ~(x1 - x0) / n_min); a node's key is the breakpoints' linear blend,
    # which is what the PSWEEP does between nodes anyway
    X = [xs[0]]
    for i in range(1, len(xs)):
        n = max(1, int(math.ceil((xs[i] - xs[i - 1]) / max((x1 - x0) / n_min, 1e-4))))
        X += list(xs[i - 1] + (xs[i] - xs[i - 1]) * np.linspace(0.0, 1.0, n + 1)[1:])
    X = np.array(X)
    KK = np.interp(X, xs, kk)
    BK = np.array(xs)                                         # the key breakpoints (the low's rings sit on them)
    scale = radius_at(chain, xk + X)
    cores = np.stack([sdf.Program.section_core(octagon(a * rm), rho) / rm for a in keys])
    return dict(x=X, key=np.array(KK), scale=np.asarray(scale), cores=cores, rho=rho, rm=rm, keys=np.stack(keys),
                x0=x0, x1=x1, xa=xa, xb=xb, breaks=BK, break_keys=np.array(kk))


ACT_SINK = 0.30e-3          # Minsky's actuator sunk this far into the waist's side (a piece sunk into its neighbour)


def shell_side(chain, des, k, x):
    """the shell's +z extent (its lateral flat) at group-local x: the PSWEEP's core keys blended at the node key there,
    scaled by the flesh radius, offset by rho (body_nodes' section, read back)"""
    bn = body_nodes(chain, des, k)
    xq = np.atleast_1d(np.asarray(x, np.float64))
    kq = np.interp(xq, bn['x'], bn['key'])
    sc = np.asarray(radius_at(chain, chain['x'][k] + xq), np.float64)
    out = np.zeros(len(xq))
    for i, (kv, s) in enumerate(zip(kq, sc)):
        i0 = int(min(math.floor(kv), len(bn['cores']) - 1))
        i1 = min(i0 + 1, len(bn['cores']) - 1)
        w = kv - i0
        core = (1.0 - w) * bn['cores'][i0] + w * bn['cores'][i1]
        out[i] = float(core[:, 1].max()) * s + bn['rho']
    return out if np.ndim(x) else float(out[0])


def actuator_span(chain, des, k):
    """the actuator of segment k (20-22) along its +z side, in the segment's frame (origin at joint k, its pivot): the
    cylinder from its gland x_g (past the proximal junction block) to its base x_b (in the distal block, where its lug
    holds it), the rod's inner end x_rod (inside the cylinder at rest), the block's length bl"""
    s_ = des['segs'][k]
    bl = DESIGN['minsky_block'] * s_['L']
    x_g, x_b = s_['x0'] + 1.25 * bl, s_['x1'] - 0.55 * bl
    return dict(x_g=x_g, x_b=x_b, x_rod=x_g + 0.45 * (x_b - x_g), bl=bl)


BAKE_WALL = 0.30e-3         # the bake's high holds a clamp collar's wall at least two voxels thick (inward, into the
                            # bore the hose fills: never seen); the true surface (the gates) keeps the designed wall
BAKE_STEP = 0.30e-3         # a turned part's smallest step (an axle's or the crank pin's head over its shank): two of
                            # the bake's 0.15 mm voxels, so the voxel high carries it
AX = dict(x=np.array([1.0, 0.0, 0.0]), y=np.array([0.0, 1.0, 0.0]), z=np.array([0.0, 0.0, 1.0]))


def _lug(b, lo, hi):
    """a lug's (r, axial) profile between lo and hi (lo < hi): a disc of radius b with its edges broken"""
    bk = _brk(min(b, hi - lo))
    return [(0.0, lo), (b - bk, lo), (b, lo + bk), (b, hi - bk), (b - bk, hi), (0.0, hi)]


def _can(base, rr, hr, rc, hc, sink=0.15e-3):
    """a motor can's (r, axial) profile on a face at `base` (axial up): its bright foot ring (rr, hr), the can (rc,
    hc), sunk `sink` into the face; and its low's corners (the foot's face on the lug left out: buried)"""
    bc = _brk(rc)
    prof = [(0.0, base - sink), (rr, base - sink), (rr, base + hr), (rc, base + hr), (rc, base + hc - bc),
            (rc - bc, base + hc), (0.0, base + hc)]
    low = [(rr, base - sink), (rr, base + hr), (rc, base + hr), (rc, base + hc), (0.0, base + hc)]
    return prof, low


def can_sink(des, k):
    """C5d (UV stacking): how far knuckle k's motor cans sink into the face they stand on: 0.15 mm at the first cardan
    (knuckle 16, the cans' primary), in proportion on the smaller knuckles, so every can is an exact scaled copy of
    the first's (its sunk foot is never seen; the absolute 0.15 mm was half the height of knuckle 22's cans)"""
    return 0.15e-3 * float(des['kn'][k]['A'][2]) / float(des['kn'][min(CARDAN)]['A'][2])


def saddle_sink(des, c):
    """C5d (UV stacking): how far a clamp's saddle sinks into its shell's top flat: 0.6 mm under clamp 8 (the saddles'
    primary), in proportion to the bundle's radius under the others, so every saddle is an exact scaled copy of
    clamp 8's (the sunk foot is never seen; the absolute 0.6 mm was two thirds of clamp 23's saddle). On Minsky's
    segments (20-22) the clamp stands over the waist, 0.15 of the section under the octagon's top: there the
    saddle keeps its 0.6 mm (in proportion it would stand 0.4 mm clear of the waist at 20)"""
    if des['segs'][c['k']]['minsky']:
        return 0.6e-3
    return 0.6e-3 * float(c['rh']) / float(des['clamps'][0]['rh'])


def pin_head(chain, K):
    """C5d (UV stacking): a cardan axle's head (radius, height) with cardan_dims' BAKE_STEP floor taken in proportion
    to the first cardan's (knuckle 16, the axles' primary, where it is BAKE_STEP itself), so every axle is an exact
    scaled copy of 16's: only the primary is baked, and at the full 0.3 mm the small knuckles' heads were relatively up
    to three times 16's (their shared texels stretched 3x, U4). Never larger than cardan_dims' head, so every clearance
    sized on that head still holds"""
    C = DESIGN['cardan']
    t = K['t']
    stp = BAKE_STEP * float(K['A'][2]) / (float(section_apothems()[2]) * float(chain['r'][min(CARDAN)]))
    return max(C['pin'][0] * t, t + stp), max(C['pin'][1] * t, stp)


def crank_pin_head(chain, des, K):
    """C5d (UV stacking): an actuator crank pin's head (radius, height), cardan_dims' BAKE_STEP floor in proportion to
    the first actuator knuckle's (20, the crank pins' primary), as pin_head; never larger than cardan_dims'"""
    stp = BAKE_STEP * float(K['A'][2]) / (float(section_apothems()[2]) * float(chain['r'][min(des['act'])]))
    return max(1.35 * K['r_pin'], K['r_pin'] + stp), max(0.6 * K['r_pin'], stp)


def knuckle_parts(chain, des, k):
    """knuckle k's pieces as primitive specs in its PIVOT's frame (x the parent's chord, y aboral), each naming the body
    that carries it: the parent's bone (the drum, or the yaw yoke and its can, the roll ring's disc), the child's shell
    body (the tongue, or the pitch yoke and its can, the actuator's cylinder), the cross, the rod. One geometry for the
    high (group_program) and the low (build_low). A spec: t 'rev' (prof the SDF's profile with its breaks, low the
    low's corners or None, axis, c) or 'box' (c, half, r; low_c / low_half the low's box, inset its inset axes), name,
    region, dens, grp (the pieces of one group: their cuts take them alone), sub (a cut), nobake (left out of the bake's
    high: the bores the trunnions and the pin fill, a hole the low does not carry)"""
    D = DESIGN
    K = des['kn'][k]
    par, chi = bone_name(k - 1), shell_body(des, k)
    out = []
    add = lambda **kw: out.append(kw)
    z3 = (0.0, 0.0, 0.0)
    if K['disc'] is not None:                         # the roll ring's disc under this knuckle's parent pieces
        Rb, wb, xd = K['disc']
        bk = _brk(wb)
        add(t='rev', body=par, name=f'ring disc {k}', axis='x', c=z3, region='disc',
            prof=[(0.0, -xd - wb), (Rb - bk, -xd - wb), (Rb, -xd - wb + bk), (Rb, -xd - bk), (Rb - bk, -xd), (0.0, -xd)],
            low=[(0.0, -xd - wb), (Rb, -xd - wb), (Rb, -xd), (0.0, -xd)])
    if K['kind'] == 'clevis':
        top, bot, ton = cheek_profiles(K)
        rd, hs, A, rc = K['rd'], K['hs'], K['A'], K['can_r']
        # (C5a-3) bake_split: the own-piece search's primitives (cheek_split); low_prim: the low's edges another piece
        # owns. C5c: a can's foot ring is its own piece and the low's top face splits at its radius: edges 3 / 4 (the
        # ring's wall and top) the ring's, 5 / 6 (the can's band and cap face) the can's; an axle cap's band and face
        # (edges 3 / 4) the cap's
        split_ = [(f'drum {k} {sfx}', pr_) for sfx, pr_ in cheek_split(K)]
        if K['can']:
            rg_, hg_ = D['can_ring'][0] * rd, D['can_ring'][1] * rd
            low_ = [(0.0, hs), (rd, hs), (rd, A[0]), (rg_, A[0]), (rg_, A[0] + hg_), (rc, A[0] + hg_),
                    (rc, A[0] + K['hc']), (0.0, A[0] + K['hc'])]
            lp_ = {3: f'drum {k} ring', 4: f'drum {k} ring', 5: f'drum {k} can', 6: f'drum {k} can'}
        else:
            low_ = [(0.0, hs), (rd, hs), (rd, A[0]), (rc, A[0]), (rc, A[0] + K['hc']), (0.0, A[0] + K['hc'])]
            lp_ = {3: f'drum {k} cap', 4: f'drum {k} cap'}
        add(t='rev', body=par, name=f'drum {k} aboral', prof=top, axis='y', c=z3, region='drum', dens={0: HIDDEN},
            sag=0.30e-3, low=low_, bake_split=split_, low_prim=lp_)
        add(t='rev', body=par, name=f'drum {k} oral', prof=bot, axis='y', c=z3, region='drum', dens={0: HIDDEN},
            sag=0.30e-3, low=[(0.0, -hs), (rd, -hs), (rd, -A[4]), (0.0, -A[4])])
        rt, ts = K['rt'], K['ts']
        add(t='rev', body=chi, name=f'tongue {k}', prof=ton, axis='y', c=z3, region='tongue', dens={0: 0.35, 2: 0.35},
            sag=0.30e-3, lo=6, low=[(0.0, -0.5 * ts), (rt, -0.5 * ts), (rt, 0.5 * ts), (0.0, 0.5 * ts)])
        # the neck's low starts inside the disc (at 0.6 rt its end face lies wholly inside it)
        reach = K['a_c'] + 0.6e-3
        x_n0 = 0.6 * rt
        add(t='box', body=chi, name=f'neck {k}', c=(0.5 * reach, 0.0, 0.0), half=(0.5 * reach, 0.5 * ts, K['wn']),
            r=_brk(ts), region='tongue', low_c=(0.5 * (x_n0 + reach), 0.0, 0.0),
            low_half=(0.5 * (reach - x_n0), 0.5 * ts, K['wn']), inset=(1, 2))
        return out
    C = D['cardan']
    h, t, b, g, Yo, Zo = K['h'], K['t'], K['b'], K['g'], K['Yo'], K['Zo']
    pin_r, pin_h = pin_head(chain, K)            # C5d: the bake floor in proportion (cardan_dims sizes on K['pin'])
    # ---- the yaw yoke on the parent: two tines (a bar rooted in the shell's end or the ring's disc, a lug round the
    # yaw axis bored for the cross's trunnion), the yaw can on the top lug
    xr = K['x_Y'] + (0.5 * K['disc'][1] if K['disc'] is not None else 0.3e-3)
    for sg, nm in ((1.0, 'aboral'), (-1.0, 'oral')):
        lo, hi = (h + g, Yo) if sg > 0 else (-Yo, -(h + g))
        grp = f'yaw tine {k} {nm}'
        # an actuator's crank, eye and rod (on the cross, at least zc0 off the yaw axis: past the lug) swing round the
        # yaw axis into the aboral tine's bar past ~64 deg of yaw (C5a-2's replay, knuckle 22 at -75 deg): the bar's
        # underside relieved above them, the lug kept whole round its bore
        lb = max(lo, K['lc'] + max(K['wc'], K['r_eye'], K['pin_head'][0]) + 2.0 * g) if (sg > 0 and K['act']) else lo
        # the bar a hair narrower than its lug's broken rim, so its end face lies wholly inside the lug (cut from the
        # low: at the lug's full width its corners stood out past the rim's breaks, a 2-texel sliver the bake missed)
        bw = b - _brk(min(b, hi - lo))
        add(t='box', body=par, name=grp, grp=grp, c=(-0.5 * xr, 0.5 * (lb + hi), 0.0), region='yoke',
            half=(0.5 * xr, 0.5 * (hi - lb), bw), r=min(_brk(0.5 * (hi - lb)), 0.3 * bw), inset=(0, 1, 2))
        add(t='rev', body=par, name=f'yaw lug {k} {nm}', grp=grp, prof=_lug(b, lo, hi), axis='y', c=z3, region='yoke',
            low=[(0.0, lo), (b, lo), (b, hi), (0.0, hi)], lo=6)
        add(t='rev', body=par, name=f'yaw bore {k} {nm}', grp=grp, sub=True, nobake=True, axis='y', c=z3,
            region='yoke', prof=[(0.0, lo - 1e-3), (t + g, lo - 1e-3), (t + g, hi + 1e-3), (0.0, hi + 1e-3)], low=None)
    # the can bored for the axle's end (its rotor) at the running clearance, as the lugs are (C5a-2's replay: a solid
    # can read the turning axle's end 0.25-0.40 mm deep)
    prof, low = _can(Yo, 1.08 * K['Rc'], 0.22 * K['Hc'], K['Rc'], K['Hc'], sink=can_sink(des, k))
    y_end = Yo + 0.3 * K['Hc']
    grp = f'yaw can {k}'
    add(t='rev', body=par, name=grp, grp=grp, prof=prof, low=low, axis='y', c=z3, region='can', lo=6)
    add(t='rev', body=par, name=f'yaw can bore {k}', grp=grp, sub=True, nobake=True, axis='y', c=z3, region='can',
        prof=[(0.0, Yo - 1e-3), (t + g, Yo - 1e-3), (t + g, y_end + g), (0.0, y_end + g)], low=None)
    # ---- the pitch yoke on the child: two side tines (a bar rooted in the child's face, a lug round the pitch axis
    # bored for the trunnion), the pitch can on the +z tine (16-19)
    xpr = K['x_P'] + 0.3e-3
    for sg, nm in ((1.0, '+z'), (-1.0, '-z')):
        lo, hi = (h + g, Zo) if sg > 0 else (-Zo, -(h + g))
        grp = f'pitch tine {k} {nm}'
        bw = b - _brk(min(b, hi - lo))                 # inside the lug's broken rim (the yaw tines' note)
        add(t='box', body=chi, name=grp, grp=grp, c=(0.5 * xpr, 0.0, 0.5 * (lo + hi)), region='yoke',
            half=(0.5 * xpr, bw, 0.5 * (hi - lo)), r=min(_brk(0.5 * (hi - lo)), 0.3 * bw), inset=(0, 1, 2))
        add(t='rev', body=chi, name=f'pitch lug {k} {nm}', grp=grp, prof=_lug(b, lo, hi), axis='z', c=z3,
            region='yoke', low=[(0.0, lo), (b, lo), (b, hi), (0.0, hi)], lo=6)
        add(t='rev', body=chi, name=f'pitch bore {k} {nm}', grp=grp, sub=True, nobake=True, axis='z', c=z3,
            region='yoke', prof=[(0.0, lo - 1e-3), (t + g, lo - 1e-3), (t + g, hi + 1e-3), (0.0, hi + 1e-3)], low=None)
    if K['pcan'] is not None:
        prof, low = _can(Zo, 1.08 * K['pcan'][0], 0.22 * K['pcan'][1], K['pcan'][0], K['pcan'][1],
                         sink=can_sink(des, k))
        z_end = Zo + 0.3 * K['pcan'][1]
        grp = f'pitch can {k}'
        add(t='rev', body=chi, name=grp, grp=grp, prof=prof, low=low, axis='z', c=z3, region='can', lo=6)
        add(t='rev', body=chi, name=f'pitch can bore {k}', grp=grp, sub=True, nobake=True, axis='z', c=z3,
            region='can', prof=[(0.0, Zo - 1e-3), (t + g, Zo - 1e-3), (t + g, z_end + g), (0.0, z_end + g)], low=None)
    # ---- the cross: the hub, the yaw trunnion (its head under the oral lug, its top end inside the can), the pitch
    # trunnion (its head outside the -z lug; its +z end inside the pitch can, or carrying the actuator's crank)
    X = f'arm_{k:02d}_cross'
    add(t='box', body=X, name=f'cross hub {k}', c=z3, half=(h, h, h), r=0.18 * h, region='cross')
    bp = _brk(pin_h)
    yb, yt = Yo + g + pin_h, Yo + 0.3 * K['Hc']
    add(t='rev', body=X, name=f'yaw axle {k}', axis='y', c=z3, region='pin', lo=6,
        prof=[(0.0, -yb), (pin_r - bp, -yb), (pin_r, -yb + bp), (pin_r, -(Yo + g)), (t, -(Yo + g)), (t, yt), (0.0, yt)],
        low=[(0.0, -yb), (pin_r, -yb), (pin_r, -(Yo + g)), (t, -(Yo + g)), (t, yt), (0.0, yt)])
    zb = Zo + g + pin_h
    zt = Zo + 0.3 * K['pcan'][1] if K['pcan'] is not None else K['zc'][1]
    add(t='rev', body=X, name=f'pitch axle {k}', axis='z', c=z3, region='pin', lo=6,
        prof=[(0.0, -zb), (pin_r - bp, -zb), (pin_r, -zb + bp), (pin_r, -(Zo + g)), (t, -(Zo + g)), (t, zt), (0.0, zt)],
        low=[(0.0, -zb), (pin_r, -zb), (pin_r, -(Zo + g)), (t, -(Zo + g)), (t, zt), (0.0, zt)])
    if not K['act']:
        return out
    # ---- the actuator (20-22): the crank keyed to the pitch trunnion's +z end (a lever up to its pin), the rod's eye
    # on the pin and the rod into the cylinder, the cylinder on the segment's +z side held by a lug on the distal block
    lc, ct, wc, r_pin, r_eye = K['lc'], K['ct'], K['wc'], K['r_pin'], K['r_eye']
    zc0, zc1 = K['zc']
    ze0, ze1 = K['ze']
    z_a = K['z_a']
    bkc = _brk(ct)
    grp = f'crank {k}'
    add(t='box', body=X, name=grp, grp=grp, c=(0.0, 0.5 * lc, 0.5 * (zc0 + zc1)), half=(wc, 0.5 * lc, 0.5 * ct),
        r=min(0.45 * ct, 0.3 * wc), region='crank', inset=(0, 2))
    for cy, nm in ((0.0, 'axle'), (lc, 'pin')):
        add(t='rev', body=X, name=f'crank {k} {nm} end', grp=grp, axis='z', c=(0.0, cy, 0.0), region='crank', lo=6,
            prof=[(0.0, zc0), (wc - bkc, zc0), (wc, zc0 + bkc), (wc, zc1 - bkc), (wc - bkc, zc1), (0.0, zc1)],
            low=[(0.0, zc0), (wc, zc0), (wc, zc1), (0.0, zc1)])
    ph_r, ph = crank_pin_head(chain, des, K)     # C5d: the bake floor in proportion (cardan_dims: K['pin_head'])
    add(t='rev', body=X, name=f'crank pin {k}', axis='z', c=(0.0, lc, 0.0), region='pin', lo=6,
        prof=[(0.0, zc0 + 0.3 * ct), (r_pin, zc0 + 0.3 * ct), (r_pin, ze1 + g), (ph_r, ze1 + g),
              (ph_r, ze1 + g + ph), (0.0, ze1 + g + ph)],
        low=[(r_pin, ze1 + g), (ph_r, ze1 + g), (ph_r, ze1 + g + ph), (0.0, ze1 + g + ph)])
    Rd = f'arm_{k:02d}_rod'
    span = actuator_span(chain, des, k)
    bke = _brk(ze1 - ze0)
    grp = f'rod eye {k}'
    add(t='rev', body=Rd, name=grp, grp=grp, axis='z', c=(0.0, lc, 0.0), region='rod', lo=6,
        prof=[(0.0, ze0), (r_eye - bke, ze0), (r_eye, ze0 + bke), (r_eye, ze1 - bke), (r_eye - bke, ze1), (0.0, ze1)],
        low=[(0.0, ze0), (r_eye, ze0), (r_eye, ze1), (0.0, ze1)])
    add(t='rev', body=Rd, name=f'rod eye bore {k}', grp=grp, sub=True, nobake=True, axis='z', c=(0.0, lc, 0.0),
        region='rod', prof=[(0.0, ze0 - 1e-3), (r_pin + g, ze0 - 1e-3), (r_pin + g, ze1 + 1e-3), (0.0, ze1 + 1e-3)],
        low=None)
    # the rod's root ends inside the eye's WALL, between its bore and its rim (cardan_dims: x_r0)
    x_r0 = K['x_r0']
    add(t='rev', body=Rd, name=f'rod {k}', axis='x', c=(0.0, lc, z_a), region='rod', lo=6,
        prof=[(0.0, x_r0), (K['r_rod'], x_r0), (K['r_rod'], span['x_rod']), (0.0, span['x_rod'])],
        low=[(K['r_rod'], x_r0), (K['r_rod'], span['x_rod']), (0.0, span['x_rod'])])
    r_cyl = K['r_cyl']
    bcy = _brk(r_cyl)
    grp = f'actuator {k}'
    add(t='rev', body=chi, name=grp, grp=grp, axis='x', c=(0.0, lc, z_a), region='actuator', lo=6,
        prof=[(0.0, span['x_g']), (r_cyl - bcy, span['x_g']), (r_cyl, span['x_g'] + bcy), (r_cyl, span['x_b']),
              (0.0, span['x_b'])],
        low=[(0.0, span['x_g']), (r_cyl, span['x_g']), (r_cyl, span['x_b']), (0.0, span['x_b'])])
    stroke = lc * math.sin(K['pitch_d']) + 1e-3
    add(t='rev', body=chi, name=f'actuator bore {k}', grp=grp, sub=True, nobake=True, axis='x', c=(0.0, lc, z_a),
        region='actuator', low=None, prof=[(0.0, span['x_g'] - 1e-3), (K['r_rod'] + g, span['x_g'] - 1e-3),
                                           (K['r_rod'] + g, span['x_rod'] + stroke), (0.0, span['x_rod'] + stroke)])
    xl = span['x_b'] - 0.10 * span['bl']
    z_side = float(shell_side(chain, des, k, xl)) - 0.3e-3
    add(t='box', body=chi, name=f'actuator lug {k}', c=(xl, lc, 0.5 * (z_side + z_a)), region='actuator',
        half=(0.30 * span['bl'], 0.55 * r_cyl, 0.5 * (z_a - z_side)), r=min(_brk(r_cyl), 0.25 * r_cyl), inset=(0, 1))
    return out


def body_specs(chain, des, body):
    """the knuckle pieces a body carries: [(spec, the knuckle's pivot in the body's frame)]"""
    k = body_k(body)
    out = []
    for j in (k, k + 1):
        if CUT < j < N_JOINTS:
            pv = np.array([chain['x'][j] - chain['x'][k], 0.0, 0.0])
            out += [(sp, pv) for sp in knuckle_parts(chain, des, j) if sp['body'] == body]
    return out


def spec_names(sp, split=False):
    """the union primitives' names a spec emits (C5a-3: a bake_split spec, split, emits its two)"""
    if split and sp.get('bake_split') is not None:
        return [nm for nm, _ in sp['bake_split']]
    return [sp['name']]


def _emit(prog, sp, o, bake, split=False, only=None):
    """one spec into the Program at o. split (C5a-3, the own-piece search's high): a bake_split spec as its two
    primitives; only: emit nothing but the union primitive of that name (a cut always: its group's caller decides)"""
    from . import sdf
    if bake and sp.get('nobake'):
        return
    op = sdf.SUBTRACT if sp.get('sub') else sdf.UNION
    if split and sp.get('bake_split') is not None:
        for nm, prof in sp['bake_split']:
            if only is None or nm == only:
                prog.revolve(prof, o + np.asarray(sp['c'], np.float64), AX[sp['axis']], op=op, name=nm)
        return
    if only is not None and not sp.get('sub') and sp['name'] != only:
        return
    if sp['t'] == 'rev':
        prog.revolve(sp['prof'], o + np.asarray(sp['c'], np.float64), AX[sp['axis']], op=op, name=sp['name'])
    else:
        prog.roundbox(o + np.asarray(sp['c'], np.float64), sp['half'], r=sp['r'], axes=sp.get('axes'), op=op,
                      name=sp['name'])


def emit_specs(prog, specs, o, bake, split=False, only=None):
    """specs [(spec, pivot)] into a Program at offset o: a run of one 'grp' as one group (its cuts take it alone: in an
    assembled program a bare SUBTRACT cuts everything folded before it, C5a's run 2). only (C5a-3): the one union
    primitive of that name with the cuts of its group, nothing else"""
    from . import sdf
    i = 0
    while i < len(specs):
        sp, pv = specs[i]
        if sp.get('grp'):
            j = i
            while j < len(specs) and specs[j][0].get('grp') == sp['grp']:
                j += 1
            run = specs[i:j]
            if only is None or any(only in spec_names(s, split) for s, _ in run if not s.get('sub')):
                prog.begin_group(op=sdf.UNION, k=0.0)
                for s, p in run:
                    _emit(prog, s, o + p, bake, split, only)
                prog.end_group()
            i = j
        else:
            if only is None or only in spec_names(sp, split):
                _emit(prog, sp, o + pv, bake, split, only)
            i += 1


def group_program(chain, des, k, prog=None, offset=(0.0, 0.0, 0.0), bake=False, split=False, only=None):
    """the sdf.Program of a rigid BODY in ITS OWN frame (origin at its joint, x along its chord; a body is a bone's
    name, an int bone, or a helper's name: cross, shell, rod), translated by `offset` (the exploded bake). Bone J0 is
    the flange (roll, collar, lug, screw, fitting); a segment's shell body carries its shell, its clamp collar (and the
    tip's boss on 23) and its proximal knuckle's child pieces; a bone carries its distal knuckle's parent pieces (a
    segment that does not turn on a roll ring: its bone is its shell body too); the cross and the rod their own. All
    hard unions: rigid pieces sunk into each other. bake: the voxel high's variant (no bores; a collar's wall, 0.04-0.48
    mm, under two 0.15 mm voxels for the small collars, sampled porous: their bands missed; there it is thickened inward
    to BAKE_WALL). C5a-3, the own-piece search's high: split (with bake) emits a clevis drum's can or cap as its own
    primitive (cheek_split); only = a union primitive's name emits that PIECE alone (with its group's cuts)"""
    from . import sdf
    D = DESIGN
    prog = prog or sdf.Program()
    want = lambda nm: only is None or only == nm
    o = np.asarray(offset, np.float64)
    X = np.array([1.0, 0.0, 0.0])
    Y = np.array([0.0, 1.0, 0.0])
    body = bone_name(k) if isinstance(k, (int, np.integer)) else k
    k = body_k(body)
    kind = body_kind(body)
    xk = chain['x'][k]
    if k == J0:
        fl = des['flange']
        C, F, n = collar_outline(chain)
        c0, c1 = fl['collar']
        b = 0.4e-3
        core_full = sdf.Program.section_core(C, b)
        # the lip: the flesh outline at the lip, 0.5 mm under the skin; it flares to full over 2 mm
        r_lip = float(radius_at(chain, c0)) / chain['ring']['r_nominal']
        lip = F * r_lip - 0.5e-3 * n
        core_lip = sdf.Program.section_core(lip, b)
        nodes = np.array([[c0 + b, 0, 0], [c0 + 2.0e-3, 0, 0], [c1 - 4.0e-3, 0, 0], [c1 - b, 0, 0]]) + o
        # the split clamp's lug on the -z side (p02: one radial screw lug) and its tangential screw
        zc = float(-C[:, 1].min())                           # the collar's half-width
        xm = 0.5 * (c0 + c1) + 1.0e-3
        lw = D['lug']
        hl = np.array([0.30 * (c1 - c0), 0.20 * zc, 0.5 * lw + 0.8e-3])
        # the collar and its lug: ONE GROUP. The clamp's split is the texture tier's (material: a dark line with a
        # groove in the normal across the lug and down the collar): carved into the high, a through-slit baked
        # back-facing on 12 % of the lug's sides (its walls square to the low's faces) and a 1 mm groove opened a
        # notch in the lug's end faces that their search ran down (misses)
        if want('flange collar') or want('collar lug'):
            prog.begin_group(op=sdf.UNION, k=0.0)
            if want('flange collar'):
                prog.psweep(nodes, np.stack([core_full, core_lip]), rho=b, key=[1.0, 0.0, 0.0, 0.0], normal=Y,
                            name='flange collar')
            if want('collar lug'):
                prog.roundbox(o + [xm, 0.0, -(zc + 0.5 * lw - 0.8e-3)], hl, r=0.6e-3, name='collar lug')
            prog.end_group()
        hd = 2.2e-3                                          # the screw's head (the kit's 1.9-2.3 mm heads, A.4.3)
        sh = [(0.0, hl[1] - 0.3e-3), (0.5 * hd - 0.2e-3, hl[1] - 0.3e-3), (0.5 * hd, hl[1] - 0.1e-3),
              (0.5 * hd, hl[1] + 1.1e-3), (0.5 * hd - 0.25e-3, hl[1] + 1.35e-3), (0.0, hl[1] + 1.35e-3)]
        if want('lug screw'):
            prog.revolve(sh, o + [xm, 0.0, -(zc + 0.5 * lw)], Y, name='lug screw')
        # the hose's bulkhead fitting on the collar's top, a 45 deg elbow (hose_path): its boss upright, its ferrule
        # leaning along the arm; the bundle leaves the ferrule straight
        H = des['hose']
        Fi = H['fitting']
        r8 = Fi['r8']
        boss = [(0.0, -1.5e-3), (1.55 * r8, -1.5e-3), (1.55 * r8, 0.35 * r8), (1.40 * r8, 0.50 * r8), (0.0, 0.50 * r8)]
        if want('hose fitting'):
            prog.revolve(boss, o + [Fi['E'][0], H['y_collar'] - 0.3e-3, 0.0], Y, name='hose fitting')
        ferrule = [(0.0, -0.9 * r8), (1.18 * r8, -0.9 * r8), (1.18 * r8, 0.60 * r8), (1.05 * r8, 0.72 * r8),
                   (0.0, 0.72 * r8)]
        if want('hose fitting ferrule'):
            prog.revolve(ferrule, o + Fi['E'], Fi['d0'], name='hose fitting ferrule')
        # the soft roll where the flesh meets the collar: a closed tube round the flesh, pressed into it
        rr = 0.5 * D['roll']
        r_roll = float(radius_at(chain, fl['roll_x'])) / chain['ring']['r_nominal']
        Ploop = F * r_roll + (rr - D['roll_sink']) * n
        loop = np.column_stack([np.full(len(Ploop), fl['roll_x']), Ploop[:, 0], Ploop[:, 1]])
        loop = np.vstack([loop, loop[:2]])
        if want('flange roll'):
            prog.sweep(loop + o, np.tile(X, (len(loop), 1)), rr, name='flange roll')
        return prog
    if kind in ('cross', 'rod') or (kind == 'bone' and k in des['ring']):
        emit_specs(prog, body_specs(chain, des, body), o, bake, split, only)
        return prog
    s_ = des['segs'][k]
    bn = body_nodes(chain, des, k)
    nodes = np.column_stack([bn['x'], np.zeros(len(bn['x'])), np.zeros(len(bn['x']))]) + o
    # the shell and its proximal chamfers (knuckle_dims / cardan_dims: shallow cuts above and below the slot or the
    # hub). ONE GROUP: its members combine among themselves first, so the cut takes the shell alone (in an assembled
    # program a bare SUBTRACT cuts everything folded before it: the exploded bake's previous group, 22 mm away, lost its
    # shell to a 60 mm cutting box: C5a's run 2)
    if want(f'shell {k}'):
        prog.begin_group(op=sdf.UNION, k=0.0)
        prog.psweep(nodes, bn['cores'], rho=bn['rho'], key=bn['key'], scale=bn['scale'], normal=Y, name=f'shell {k}')
        for (p0, u, v, nm) in chamfer_cuts(chain, des, k):
            big = 0.012
            R3 = np.column_stack([u, v, [0.0, 0.0, 1.0]])
            prog.roundbox(o + p0 + v * big, [big, big, big], r=0.0, axes=R3, op=sdf.SUBTRACT, name=nm)
        prog.end_group()
    # the knuckle pieces: the proximal knuckle's child pieces (the tongue, or the pitch yoke, its can and the
    # actuator), and on a bone the distal knuckle's parent pieces (the drum, or the yaw yoke and its can)
    emit_specs(prog, body_specs(chain, des, body), o, bake, split, only)
    if s_['tip'] and want('tip boss'):
        rt_ = float(radius_at(chain, xk + bn['x1']))
        x1 = bn['x1']
        L = s_['L']
        e = 0.62 * rt_
        bk = _brk(e)
        boss = [(0.0, x1 - 0.8e-3), (0.88 * rt_, x1 - 0.8e-3), (0.88 * rt_, x1 + 0.10 * (L - x1)),
                (e, x1 + 0.30 * (L - x1)), (e, L - bk), (e - bk, L), (0.45 * e, L), (0.45 * e, L - 0.35 * e),
                (0.0, L - 0.35 * e)]
        prog.revolve(boss, o, X, name='tip boss')
    for c in des['clamps']:
        if c['k'] != k:
            continue
        xc = c['x'] - xk
        rh_, R, L_ = c['rh'], c['R'], c['L']
        b = _brk(L_)
        rb = min(rh_, R - BAKE_WALL) if bake else rh_
        ring = [(rb, -0.5 * L_), (R - b, -0.5 * L_), (R, -0.5 * L_ + b), (R, 0.5 * L_ - b), (R - b, 0.5 * L_),
                (rb, 0.5 * L_)]
        cpos = o + [xc, c['y'], 0.0]
        if want(f'clamp {k}'):
            prog.revolve(ring, cpos, X, name=f'clamp {k}')
        # the lug (1.30 D across) on the clamp's +z side, and the saddle down into the shell's top
        if want(f'clamp lug {k}'):
            prog.roundbox(cpos + [0.0, 0.0, 0.5 * (c['R_lug'] + rh_)],
                          [0.42 * L_, 0.30 * c['D'], 0.5 * (c['R_lug'] - rh_)], r=min(b, 0.1 * c['D']),
                          name=f'clamp lug {k}')
        ytop = des['top'](c['x'])
        y0, y1 = ytop - saddle_sink(des, c), c['y'] - 0.5 * (R + rh_)   # up into the ring's wall, never the hose
        if want(f'saddle {k}'):
            prog.roundbox(o + [xc, 0.5 * (y0 + y1), 0.0], [0.45 * L_, 0.5 * (y1 - y0), 0.75 * R],
                          r=min(b, 0.2 * (y1 - y0)), name=f'saddle {k}')
    return prog


def chamfer_cuts(chain, des, k):
    """segment k's proximal chamfer planes in its body's frame: [(a point on the plane, the plane's direction u, its
    normal v toward the removed side, name)]: the face leans back at the knuckle's slope s from the height y_ch (the
    clevis slot's top, the cross's hub top) upward, and its mirror below (C5a-2: shallow, 1.15 x tan(the design tilt or
    pitch), where C5a cut 45 deg)"""
    K = des['kn'].get(k)
    if K is None or K['ch'][1] <= 0.0:
        return []
    x0 = des['segs'][k]['x0']
    y_ch, s = K['ch']
    n = math.sqrt(1.0 + s * s)
    return [(np.array([x0, y_ch, 0.0]), np.array([s, 1.0, 0.0]) / n, np.array([-1.0, s, 0.0]) / n, f'chamfer {k} aboral'),
            (np.array([x0, -y_ch, 0.0]), np.array([s, -1.0, 0.0]) / n, np.array([-1.0, -s, 0.0]) / n, f'chamfer {k} oral')]


def chamfer_setback(des, k, r0=None):
    """how far the chamfers lean the face back at the shell's top flat (the panel details start past it)"""
    K = des['kn'].get(k)
    if K is None or K['ch'][1] <= 0.0:
        return 0.0
    return max(0.0, (K['A'][0] - K['ch'][0]) * K['ch'][1])


def band_nodes(des):
    """the bellows' stations (group J0's frame): a crest at each lip and between the convolutions, a trough between,
    the section blending from the collar's outline (t = 0) to the octagon (t = 1); linear between stations (a
    V-convoluted bellows); its lips 1 mm past the band's span, sunk into the collar and the segment"""
    b0, b1 = des['flange']['band']
    n = 2 * DESIGN['band_ribs']
    t = np.linspace(0.0, 1.0, n + 1)
    xs = (b0 - 1.0e-3) + t * ((b1 + 1.0e-3) - (b0 - 1.0e-3))
    wave = np.where(np.arange(n + 1) % 2 == 0, 1.0, 1.0 - 0.035)
    return xs, t, wave


def band_program(chain, des, prog=None, offset=(0.0, 0.0, 0.0), M=96):
    """the rubber band round joint 8 (group J0's frame): a short bellows whose section blends from the collar's outline
    (x band_od) to the first segment's octagon, its lips sunk 1 mm into the collar's face and the segment's start"""
    from . import sdf
    D = DESIGN
    prog = prog or sdf.Program()
    o = np.asarray(offset, np.float64)
    fl = des['flange']
    b0, b1 = fl['band']
    C, _, _ = collar_outline(chain, M)
    Ac = section_apothems() * float(chain['r'][CUT])
    oct8 = resample_polygon(octagon(Ac), M)
    rho = 0.6e-3
    k0 = sdf.Program.section_core(C * D['band_od'], rho)
    k1 = sdf.Program.section_core(oct8 * 1.03, rho)
    xs, t, wave = band_nodes(des)
    nodes = np.column_stack([xs, np.zeros_like(xs), np.zeros_like(xs)]) + o
    prog.psweep(nodes, np.stack([k0, k1]), rho=rho, key=t, scale=wave, normal=np.array([0.0, 1.0, 0.0]),
                name='rubber band')
    return prog


GROUPS = tuple(range(J0, N_JOINTS))          # the bones (C5a's rigid groups); C5a-2's rigid bodies: des['bodies']


def assembled_program(chain, des, groups=None, band=True, hose=True, offsets=None, bake=False, split=False):
    """one Program of the machine in the asset frame (the straight bind: a body of joint k translated to joint k);
    offsets {body or 'band' / 'hose': (3,)} add an extra translation per piece (the exploded bake); bake: group_program's
    voxel-high variant (split: the own-piece search's, C5a-3)"""
    from . import sdf
    prog = sdf.Program()
    off = offsets or {}
    for b_ in (des['bodies'] if groups is None else groups):
        b_ = bone_name(b_) if isinstance(b_, (int, np.integer)) else b_
        o = np.array([chain['x'][body_k(b_)], 0.0, 0.0]) + np.asarray(off.get(b_, (0.0, 0.0, 0.0)))
        group_program(chain, des, b_, prog, o, bake=bake, split=split)
    if band:
        band_program(chain, des, prog, np.asarray(off.get('band', (0.0, 0.0, 0.0))))
    if hose:
        hose_program(chain, des, prog, np.asarray(off.get('hose', (0.0, 0.0, 0.0))))
    return prog


class ProgField:
    """a plain Program wearing voxel.SparseSDF's query interface (an empty 1-voxel grid far away, so the hybrid field
    is the program everywhere): for voxel.trace_views and the clash probes"""

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


# ============================================================================================ the low
# region codes: the low's per-triangle material class (the material pass reads them; the bake logs islands by name)
REGIONS = ('shell', 'shell_end', 'drum', 'can', 'cap', 'tongue', 'clamp', 'actuator', 'rod', 'boss', 'collar',
           'collar_end', 'screw', 'fitting', 'roll', 'band', 'hose', 'yoke', 'cross', 'pin', 'disc', 'crank', 'chamfer')
REG = {n: i for i, n in enumerate(REGIONS)}
HIDDEN = 0.5                # texel density for faces the knuckles mostly hide (end faces in the slots, the bore side)
SAG = 0.25e-3               # the low's chord sagitta (the body's 0.2 mm face rule, U5, eased for a 1024 set)


def n_sides(R, lo=8, hi=24, sag=SAG):
    """sides for a circle of radius R at the chord sagitta (U5), even"""
    if R <= sag:
        return lo
    n = math.pi / math.acos(max(-1.0, 1.0 - sag / R))
    return int(min(hi, max(lo, 2 * math.ceil(n / 2.0))))


def _grid(P, closed=True):
    """an island from a grid of points P (R rows, C columns, 3): triangles on each quad's shorter diagonal; when closed,
    column 0 repeats at the end (the UV seam); UVs unrolled: u each column's arc length round the rows AVERAGED over
    the rows (C5a centred each row on its own length: a strip whose rows differ in length, a bevel, a cone, a bellows,
    sheared to a stretch of 1.6-2.0; averaged, the only error is a row's length against the mean), v the mean distance
    between rows"""
    P = np.asarray(P, np.float64)
    if closed:
        P = np.concatenate([P, P[:, :1]], 1)
    R, C = P.shape[:2]
    du = np.linalg.norm(np.diff(P, axis=1), axis=2)
    u = np.concatenate([np.zeros((R, 1)), np.cumsum(du, 1)], 1).mean(0)
    u = np.tile(u - 0.5 * u[-1], (R, 1))
    dv = np.linalg.norm(np.diff(P, axis=0), axis=2).mean(1)
    v = np.concatenate([[0.0], np.cumsum(dv)])
    UV = np.stack([u, np.repeat(v[:, None], C, 1)], -1).reshape(-1, 2)
    V = P.reshape(-1, 3)
    F = []
    for r in range(R - 1):
        for c in range(C - 1):
            a, b, cc, d = r * C + c, r * C + c + 1, (r + 1) * C + c + 1, (r + 1) * C + c
            if np.linalg.norm(V[a] - V[cc]) <= np.linalg.norm(V[b] - V[d]):
                F += [(a, b, cc), (a, cc, d)]
            else:
                F += [(a, b, d), (b, cc, d)]
    return V, np.array(F, np.int64), UV


def _fan(ring, centre=None):
    """a flat cap: the ring (n, 3) fanned from its centroid (or `centre`), UVs projected on its plane"""
    ring = np.asarray(ring, np.float64)
    c = ring.mean(0) if centre is None else np.asarray(centre, np.float64)
    n = np.cross(ring[1] - ring[0], ring[len(ring) // 3] - ring[0])
    for i in range(len(ring)):
        n2 = np.cross(ring[i] - c, ring[(i + 1) % len(ring)] - c)
        n = n2 if np.linalg.norm(n2) > np.linalg.norm(n) else n
    n /= np.linalg.norm(n)
    e1 = ring[0] - c - n * ((ring[0] - c) @ n)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    V = np.vstack([c[None], ring])
    m = len(ring)
    F = np.array([(0, 1 + i, 1 + (i + 1) % m) for i in range(m)], np.int64)
    Q = V - c
    return V, F, np.column_stack([Q @ e1, Q @ e2])


def _island(V, F, UV, region, bone, piece, dens=1.0, smooth=None, body=None):
    """an island: its triangles, UVs, region, its frame's joint (bone: the body's joint index k, its origin x[k]), its
    piece's name, texel-density factor, and its rigid BODY (a bone's or a helper's name)"""
    return dict(V=np.asarray(V, np.float64), F=np.asarray(F, np.int64), UV=np.asarray(UV, np.float64),
                region=REG[region], bone=int(bone), piece=piece, dens=float(dens), smooth=smooth or piece,
                body=body or bone_name(bone))


def _frame_axis(axis):
    """an orthonormal (e1, e2) normal to an axis"""
    a = np.asarray(axis, np.float64)
    a = a / np.linalg.norm(a)
    t = np.array([1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(a, t)
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(a, e1)


def revolve_islands(profile, centre, axis, n, region, bone, piece, dens=None, seam_phi=0.0):
    """a REVOLVE part's low: the (r, y) profile (its corners only; breaks and small steps bake) revolved at n sides
    about `axis` through `centre`. Each profile edge is a band (|dy| > |dr|: one unrolled strip per run of bands) or a
    face (an annulus, or a disc where it reaches the axis: planar). Returns islands; dens: per edge index, a density
    factor (default 1)"""
    P = np.asarray(profile, np.float64)
    a = np.asarray(axis, np.float64)
    a /= np.linalg.norm(a)
    e1, e2 = _frame_axis(a)
    c = np.asarray(centre, np.float64)
    phi = seam_phi + np.linspace(0.0, TAU, n, endpoint=False)
    ring = lambda r, y: c + a * y + r * (np.cos(phi)[:, None] * e1 + np.sin(phi)[:, None] * e2)
    out = []
    i = 0
    E = len(P) - 1
    while i < E:
        (r0, y0), (r1, y1) = P[i], P[i + 1]
        d_ = 1.0 if dens is None else dens.get(i, 1.0)
        if abs(y1 - y0) > abs(r1 - r0):
            j = i                                            # a run of bands: one strip
            while j + 1 < E and abs(P[j + 2][1] - P[j + 1][1]) > abs(P[j + 2][0] - P[j + 1][0]):
                j += 1
            rows = np.stack([ring(P[q][0], P[q][1]) for q in range(i, j + 2)])
            V, F, UV = _grid(rows, closed=True)
            out.append(_island(V, F, UV, region, bone, f'{piece} band{i}', d_, smooth=f'{piece} band{i}'))
            i = j + 1
            continue
        if r0 < 1e-9 or r1 < 1e-9:                           # a disc
            rr, yy = (r1, y1) if r0 < 1e-9 else (r0, y0)
            V, F, UV = _fan(ring(rr, yy), c + a * yy)
        else:                                                # an annulus
            V, F, UV = _grid(np.stack([ring(r0, y0), ring(r1, y1)]), closed=True)
            UVp = np.column_stack([(V - c) @ e1, (V - c) @ e2])
            UV = UVp
        out.append(_island(V, F, UV, region, bone, f'{piece} face{i}', d_, smooth=f'{piece} face{i}'))
        i += 1
    return out


LOW_INSET = 0.075e-3        # half a voxel: a box's or a ring's low faces stand this far inside the high's, so no low
                            # edge lies on a neighbouring face's plane (the bake found that face, square to the low's,
                            # along the rims of the small clamp collars, saddles, necks and the collar's lug)


def _inset(half, axes=(0, 1, 2), frac=0.12):
    """box half extents with the named axes pulled in by LOW_INSET (at most `frac` of the smallest of them)"""
    h = np.array(half, np.float64)
    d = min(LOW_INSET, frac * float(min(h[a] for a in axes)))
    for a in axes:
        h[a] -= d
    return h


def box_islands(centre, half, region, bone, piece, axes=None, dens=1.0):
    """a box's low (its rounded edges bake): the four faces round its x axis as one strip, its two x faces flat"""
    R = np.eye(3) if axes is None else np.asarray(axes, np.float64)
    c = np.asarray(centre, np.float64)
    h = np.asarray(half, np.float64)
    sq = np.array([[1, 1], [-1, 1], [-1, -1], [1, -1]], np.float64)     # (y, z) corners round x
    ring = lambda xs: c + (xs * h[0]) * R[:, 0] + (sq[:, 0:1] * h[1]) * R[:, 1] + (sq[:, 1:2] * h[2]) * R[:, 2]
    V, F, UV = _grid(np.stack([ring(-1.0), ring(1.0)]), closed=True)
    out = [_island(V, F, UV, region, bone, f'{piece} sides', dens)]
    for s_ in (-1.0, 1.0):
        V, F, UV = _fan(ring(s_))
        out.append(_island(V, F, UV, region, bone, f'{piece} end{int(s_)}', dens))
    return out


def shell_islands(chain, des, k, o, body=None, cut=True):
    """segment k's shell low: the octagon's rings (one chamfer per corner: the rounding bakes) at the PSWEEP's key
    breakpoints, a bevel ring at each end (the rho round), flat end caps on the core. Charted in BANDS (U4, the lead's
    call 4): each run of one section a grid strip (_grid), each change of section (Minsky's waist transitions) its own
    island laid flat quad by quad (_develop; C5a's one strip stretched them to 2.7); the proximal chamfers CUT out of the
    strips and the face along their planes (clip_mesh) and charted as their own planar islands (each the cut's outline,
    a convex polygon). Returns (islands, body_nodes)"""
    body = body or shell_body(des, k)
    bn = body_nodes(chain, des, k)
    rho, rm = bn['rho'], bn['rm']
    keys = bn['keys']
    xk = chain['x'][k]

    def section(xv, kq, off):
        i0 = min(int(kq), len(keys) - 2) if len(keys) > 1 else 0
        w = kq - i0
        A = keys[i0] if len(keys) == 1 else keys[i0] * (1.0 - w) + keys[min(i0 + 1, len(keys) - 1)] * w
        s = float(radius_at(chain, xk + xv))
        from . import sdf
        C = sdf.Program.section_core(octagon(A * rm), rho) * (s / rm)
        th = np.radians(45.0 * np.arange(8))
        pts = []
        for i in range(8):
            for t in (th[i], th[(i + 1) % 8] + (TAU if i == 7 else 0.0)):
                pts.append(C[i] + off * rho * np.array([math.cos(t), math.sin(t)]))
        return np.array(pts)

    X, KQ = list(bn['breaks']), list(bn['break_keys'])
    to3 = lambda xv, S: np.column_stack([np.full(len(S), xv), S[:, 0], S[:, 1]]) + o
    xe0, xe1 = bn['x0'] + rho * (1 - math.sqrt(0.75)), bn['x1'] - rho * (1 - math.sqrt(0.75))
    rows = [to3(xe0, section(X[0], KQ[0], 0.5))] + [to3(xv, section(xv, kq, 1.0)) for xv, kq in zip(X, KQ)] + \
        [to3(xe1, section(X[-1], KQ[-1], 0.5))]
    rk = [KQ[0]] + list(KQ) + [KQ[-1]]
    # the end bevels (a half-offset ring against a full one: centring each row's arc length sheared them to a stretch
    # of 2.0) and each change of section laid flat; the runs between them grid strips
    bands, i = [], 0
    while i < len(rows) - 1:
        if i == 0 or i == len(rows) - 2 or abs(rk[i + 1] - rk[i]) > 1e-9:
            bands.append(('dev', i, i + 1))
            i += 1
        else:
            j = i
            while j < len(rows) - 2 and abs(rk[j + 1] - rk[j]) <= 1e-9:
                j += 1
            bands.append(('grid', i, j))
            i = j
    pieces = []
    for kind_, i0, i1 in bands:
        P = np.stack(rows[i0:i1 + 1])
        if kind_ == 'grid':
            V, F, UV = _grid(P, closed=True)
            pieces.append((V, F, UV, f'shell {k} band{i0}', 'shell'))
            continue
        # a band laid flat curls (its two rings' lengths differ: the bevel's by ~3 rho over a width of ~rho, a turn of
        # ~175 deg in all; a waist transition's by ~22 %): cut into short arcs that pack (8 per bevel: four curled
        # arcs wasted more of the sheet than eight straight ones; 4 per transition)
        npc = 8 if i0 == 0 or i1 == len(rows) - 1 else 4
        for s_i, (V, F, UV) in enumerate(_dev_pieces(P, npc)):
            pieces.append((V, F, UV, f'shell {k} band{i0} part{s_i}', 'shell'))
    V, F, UV = _fan(rows[0])
    pieces.append((V, F, UV, f'shell {k} proximal end', 'shell_end'))
    cuts = chamfer_cuts(chain, des, k) if cut else []       # C5d: cut=False, the unclipped low (cyborg_stack)
    cutpts = {cn: [] for (_, _, _, cn) in cuts}
    out = []
    for V, F, UV, nm, reg in pieces:
        for p0, u, v, cn in cuts:
            P0 = o + p0
            V, F, UV, cp = clip_mesh(V, F, UV, lambda P, P0=P0, v=v: -((P - P0) @ v), 0.0)
            if len(cp):
                cutpts[cn].append(cp.reshape(-1, 3))
        if len(F):
            out.append(_island(V, F, UV, reg, k, nm, 1.0, body=body))
    from scipy.spatial import ConvexHull
    for p0, u, v, cn in cuts:
        if not cutpts[cn]:
            continue
        Q = np.concatenate(cutpts[cn])
        q2 = np.column_stack([(Q - (o + p0)) @ np.array([0.0, 0.0, 1.0]), (Q - (o + p0)) @ u])
        if len(Q) < 3 or np.ptp(q2[:, 0]) < 1e-6 or np.ptp(q2[:, 1]) < 1e-6:
            continue
        V, F, UV = _fan(Q[ConvexHull(q2).vertices])
        out.append(_island(V, F, UV, 'chamfer', k, f'shell {k} {cn.split()[-1]} chamfer', 1.0, body=body))
    V, F, UV = _fan(rows[-1])
    out.append(_island(V, F, UV, 'shell_end', k, f'shell {k} distal end', HIDDEN if k + 1 < N_JOINTS else 1.0,
                       body=body))
    return out, bn


def _dev_pieces(P, npc):
    """a closed band between two rings P (2, C, 3) cut into npc open pieces, each laid flat (_develop): a band whose
    rings' lengths differ curls when laid flat whole"""
    C_ = P.shape[1]
    return [_develop(P[:, [(c_ % C_) for c_ in range(s_i * C_ // npc, (s_i + 1) * C_ // npc + 1)]], closed=False)
            for s_i in range(npc)]


def _develop(P, closed=True):
    """a band between two rings P (2, C, 3) laid flat quad by quad, each quad's two triangles at their true shape edge
    to edge (zero stretch where its quads are planar: a pyramid frustum's faces, Minsky's waist transitions): V, F, UV
    as _grid's (closed: the ring's first column repeated at the end, the UV seam; else an open strip)"""
    P = np.asarray(P, np.float64)
    if closed:
        P = np.concatenate([P, P[:, :1]], 1)
    C = P.shape[1]
    A, B = P[0], P[1]
    ua, ub = np.zeros((C, 2)), np.zeros((C, 2))
    ub[0] = [0.0, float(np.linalg.norm(B[0] - A[0]))]

    def place(p, q, P3p, P3q, P3s):
        dp, dq, L = float(np.linalg.norm(P3s - P3p)), float(np.linalg.norm(P3s - P3q)), float(np.linalg.norm(q - p))
        al = math.acos(float(np.clip((dp * dp + L * L - dq * dq) / max(2.0 * dp * L, 1e-30), -1.0, 1.0)))
        ang = math.atan2(q[1] - p[1], q[0] - p[0]) - al
        return p + dp * np.array([math.cos(ang), math.sin(ang)])
    for j in range(C - 1):
        ua[j + 1] = place(ua[j], ub[j], A[j], B[j], A[j + 1])
        ub[j + 1] = place(ua[j + 1], ub[j], A[j + 1], B[j], B[j + 1])
    V = np.concatenate([A, B])
    UV = np.concatenate([ua, ub])
    F = []
    for j in range(C - 1):
        F += [(j, j + 1, C + j), (C + j, j + 1, C + j + 1)]
    return V, np.array(F, np.int64), UV


CLIP_DEPTH = 0.30e-3        # a buried face is cut where it passes this far inside its body's other pieces (their lows sit
                            # up to their sagitta, 0.25-0.30 mm, inside the highs: the kept edge must reach under them)


def clip_mesh(V, F, UV, fn, keep_level=0.0, iters=6):
    """the part of a triangle mesh where fn(points) >= keep_level; the triangles crossing the level cut along it (each
    crossing found on its edge by bisection on fn, shared by the two triangles of that edge), UVs interpolated. fn:
    points (n, 3) -> values (n,). Returns V, F, UV (unused vertices dropped) and per cut triangle its cut segment
    (m, 2, 3)"""
    V, F, UV = np.asarray(V, np.float64), np.asarray(F, np.int64).reshape(-1, 3), np.asarray(UV, np.float64)
    if not len(F):
        return V, F, UV, np.zeros((0, 2, 3))
    kin = (np.asarray(fn(V), np.float64) - keep_level) >= 0.0
    n_in = kin[F].sum(1)
    if (n_in == 3).all():
        return V, F, UV, np.zeros((0, 2, 3))
    mixed = (n_in > 0) & (n_in < 3)
    Fm = F[mixed]
    E = np.sort(np.concatenate([Fm[:, [0, 1]], Fm[:, [1, 2]], Fm[:, [2, 0]]]), axis=1)
    E = np.unique(E[kin[E[:, 0]] != kin[E[:, 1]]], axis=0)
    a, b = E[:, 0], E[:, 1]
    # the linear crossing first (exact for a plane), then bisection on the bracket it leaves (a curved field)
    da = np.asarray(fn(V[a]), np.float64) - keep_level
    db = np.asarray(fn(V[b]), np.float64) - keep_level
    tl = np.clip(da / np.where(np.abs(da - db) > 1e-30, da - db, 1e-30), 0.0, 1.0)
    dl = np.asarray(fn(V[a] + tl[:, None] * (V[b] - V[a])), np.float64) - keep_level
    sa = kin[a]
    exact = np.abs(dl) < 1e-9
    side_a = (dl >= 0.0) == sa
    lo, hi = np.where(side_a, tl, 0.0), np.where(side_a, 1.0, tl)
    for _ in range(0 if exact.all() else iters):
        mid = 0.5 * (lo + hi)
        same = ((np.asarray(fn(V[a] + mid[:, None] * (V[b] - V[a])), np.float64) - keep_level) >= 0.0) == sa
        lo, hi = np.where(same, mid, lo), np.where(same, hi, mid)
    t = np.where(exact, tl, 0.5 * (lo + hi))
    base = len(V)
    key = {(int(p), int(q)): base + i for i, (p, q) in enumerate(E)}
    newF = [tuple(f) for f in F[n_in == 3]]
    cuts = []
    for tri in Fm:
        poly, cp = [], []
        for i in range(3):
            p, q = int(tri[i]), int(tri[(i + 1) % 3])
            if kin[p]:
                poly.append(p)
            if kin[p] != kin[q]:
                e = key[(min(p, q), max(p, q))]
                poly.append(e)
                cp.append(e)
        for j in range(1, len(poly) - 1):
            newF.append((poly[0], poly[j], poly[j + 1]))
        if len(cp) == 2:
            cuts.append(cp)
    V2 = np.vstack([V, V[a] + t[:, None] * (V[b] - V[a])])
    UV2 = np.vstack([UV, UV[a] + t[:, None] * (UV[b] - UV[a])])
    F2 = np.array(newF, np.int64).reshape(-1, 3)
    cut = V2[np.array(cuts, np.int64)] if cuts else np.zeros((0, 2, 3))
    if not len(F2):
        return V2[:0], F2, UV2[:0], cut
    used = np.unique(F2)
    remap = -np.ones(len(V2), np.int64)
    remap[used] = np.arange(len(used))
    return V2[used], remap[F2], UV2[used], cut


def split_components(V, F, UV):
    """a mesh's connected pieces (by shared vertices): [(V, F, UV)]"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(V)
    a = np.concatenate([F[:, 0], F[:, 1], F[:, 2]])
    b = np.concatenate([F[:, 1], F[:, 2], F[:, 0]])
    nc, lab = connected_components(coo_matrix((np.ones(len(a), np.int8), (a, b)), shape=(n, n)), directed=False)
    tl = lab[F[:, 0]]
    out = []
    for c in np.unique(tl):
        Fc = F[tl == c]
        used = np.unique(Fc)
        remap = -np.ones(n, np.int64)
        remap[used] = np.arange(len(used))
        out.append((V[used], remap[Fc], UV[used]))
    return out


def clip_buried(isl, progs_bake, log=print):
    """every island's BURIED part cut away (the lead's call 4: buried faces get no texels): where it passes CLIP_DEPTH
    inside the other pieces of its own body (its body's bake program without the island's own primitive); what is left
    split into its connected pieces, each its own island. The band, the hose and the flange's roll are left whole"""
    out = []
    a0 = a1 = 0.0
    area = lambda V, F: 0.5 * float(np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]),
                                                   axis=1).sum()) if len(F) else 0.0
    for it in isl:
        a_in = area(it['V'], it['F'])
        a0 += a_in
        if REGIONS[it['region']] in ('band', 'hose', 'roll'):
            out.append(it)
            a1 += a_in
            continue
        prog = progs_bake[it['body']]
        p = prim_of_piece(it['piece'], prog.names)
        sub = subset_program(prog, {p}) if p is not None else prog
        if not len(sub.kind):
            out.append(it)
            a1 += a_in
            continue
        V, F, UV, _ = clip_mesh(it['V'], it['F'], it['UV'], sub.eval, keep_level=-CLIP_DEPTH)
        if not len(F):
            continue
        for V_, F_, UV_ in split_components(V, F, UV):
            out.append(dict(it, V=V_, F=F_, UV=UV_))
            a1 += area(V_, F_)
    log(f'[cyborg_limb] buried faces cut away: {len(isl)} islands -> {len(out)}, low surface {a0 * 1e4:.1f} -> '
        f'{a1 * 1e4:.1f} cm2 ({100.0 * (1.0 - a1 / max(a0, 1e-12)):.1f} % buried)')
    return out


def clip_nested(isl, des, progs_bake, log=print):
    """the NESTED pieces' faces buried in ANOTHER body (clip_buried cuts within a body), cut away at CLIP_DEPTH as
    clip_buried does: a cardan's yaw axle inside its parent's yaw lugs and can, its pitch axle inside the child's pitch
    lugs and can (each turns about its own axis, coaxial with them: buried in every pose; the tines' bars, not round
    about it, left out), an actuator's rod inside its cylinder (it slides lc sin(pitch) along it: cut where it stays
    inside at its most retracted, the design pitch)"""
    out = []
    a0 = a1 = 0.0
    area = lambda V, F: 0.5 * float(np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]),
                                                   axis=1).sum()) if len(F) else 0.0
    for it in isl:
        pc = it['piece']
        part = None
        for k in CARDAN:
            if pc == f'yaw axle {k}' or pc.startswith(f'yaw axle {k} '):
                part = (bone_name(k - 1), (f'yaw lug {k} aboral', f'yaw lug {k} oral', f'yaw can {k}'), 0.0, CLIP_DEPTH)
            elif pc == f'pitch axle {k}' or pc.startswith(f'pitch axle {k} '):
                part = (shell_body(des, k), (f'pitch lug {k} +z', f'pitch lug {k} -z', f'pitch can {k}'), 0.0,
                        CLIP_DEPTH)
            elif k in des['act'] and (pc == f'rod {k}' or pc.startswith(f'rod {k} ')):
                K = des['kn'][k]
                # the rod's surface lies only r_cyl - r_rod inside the cylinder's: 0.285 / 0.20 mm at 21 / 22, under
                # CLIP_DEPTH, so their whole shanks inside kept their texels (C5a-2's check): cut at half that depth
                part = (shell_body(des, k), (f'actuator {k}',), K['lc'] * math.sin(K['pitch_d']),
                        min(CLIP_DEPTH, 0.5 * (K['r_cyl'] - K['r_rod'])))
        if part is None:
            out.append(it)
            continue
        body, keep, s, depth = part
        prog = progs_bake[body]
        sub = subset_program(prog, {nm for nm in prog.names if nm not in keep})
        a_in = area(it['V'], it['F'])
        a0 += a_in
        if not len(sub.kind):
            out.append(it)
            a1 += a_in
            continue
        sh = np.array([s, 0.0, 0.0])
        fn = (lambda P, sub=sub, sh=sh: sub.eval(np.asarray(P, np.float64) - sh))
        V, F, UV, _ = clip_mesh(it['V'], it['F'], it['UV'], fn, keep_level=-depth)
        if not len(F):
            continue
        for V_, F_, UV_ in split_components(V, F, UV):
            out.append(dict(it, V=V_, F=F_, UV=UV_))
            a1 += area(V_, F_)
    log(f'[cyborg_limb] nested pieces\' faces buried in their partners (axles in lugs and cans, rods in cylinders) cut '
        f'away: {a0 * 1e6:.1f} -> {a1 * 1e6:.1f} mm2 ({len(isl)} islands -> {len(out)})')
    return out


def _spec_islands(sp, o, k):
    """a knuckle piece's low islands (its spec, its pivot's place o in the asset frame; k its body's joint)"""
    if sp.get('sub') or (sp['t'] == 'rev' and sp.get('low') is None):
        return []
    if sp['t'] == 'rev':
        prof = sp['low']
        n = sp.get('n') or n_sides(max(r_ for r_, _ in prof), lo=sp.get('lo', 8), sag=sp.get('sag', SAG))
        out = revolve_islands(prof, o + np.asarray(sp['c'], np.float64), AX[sp['axis']], n, sp['region'], k,
                              sp['name'], dens=sp.get('dens'))
        # (C5a-3) the islands of the low's edges another piece owns in the own-piece search (a drum's can band and cap)
        for it in out:
            e = int(it['piece'][len(sp['name']):].lstrip(' bandface'))
            if e in sp.get('low_prim', {}):
                it['prim'] = sp['low_prim'][e]
    else:
        c = np.asarray(sp.get('low_c', sp['c']), np.float64)
        half = sp.get('low_half', sp['half'])
        out = box_islands(o + c, _inset(half, axes=sp.get('inset', (0, 1, 2))), sp['region'], k, sp['name'],
                          axes=sp.get('axes'), dens=sp.get('dens', 1.0))
    for it in out:
        it['body'] = sp['body']
    return out


def build_low(chain, des, log=print):
    """every piece's low as UV islands in the asset frame (the straight bind), each with its region, its bone (a rigid
    group's joint; the band's and the hose's carry per-vertex weights instead) and a texel-density factor"""
    D = DESIGN
    isl = []
    X = np.array([1.0, 0.0, 0.0])
    Y = np.array([0.0, 1.0, 0.0])
    x = chain['x']
    # ---- the flange (bone J0)
    fl = des['flange']
    o = np.array([x[J0], 0.0, 0.0])
    C, Fo, n_ = collar_outline(chain, 96)
    Mc = 24
    Cs = resample_polygon(C, Mc)
    c0, c1 = fl['collar']
    r_lip = float(radius_at(chain, c0)) / chain['ring']['r_nominal']
    lip = resample_polygon(Fo * r_lip - 0.5e-3 * n_, Mc)
    b = 0.4e-3
    Cb = resample_polygon(C - 0.5 * b * n_, Mc)
    to3 = lambda xv, S: np.column_stack([np.full(len(S), xv), S[:, 0], S[:, 1]]) + o
    rows = [to3(c0, lip), to3(c0 + 2.0e-3, Cs), to3(0.5 * (c0 + c1), Cs), to3(c1 - b, Cs), to3(c1, Cb)]
    # the lip's flare and the face's bevel laid flat in short pieces (U4: in one grid strip with the collar they
    # stretched to 2.3 and 1.85: their two rings' lengths differ)
    for i0, nm in ((0, 'flare'), (3, 'bevel')):
        for j_, (V, F, UV) in enumerate(_dev_pieces(np.stack(rows[i0:i0 + 2]), 8)):
            isl.append(_island(V, F, UV, 'collar', J0, f'collar {nm} part{j_}'))
    V, F, UV = _grid(np.stack(rows[1:4]), closed=True)
    isl.append(_island(V, F, UV, 'collar', J0, 'collar'))
    for row, nm in ((rows[0], 'lip'), (rows[-1], 'face')):
        V, F, UV = _fan(row)
        isl.append(_island(V, F, UV, 'collar_end', J0, f'collar {nm}', HIDDEN))
    zc = float(-C[:, 1].min())
    xm = 0.5 * (c0 + c1) + 1.0e-3
    lw = D['lug']
    hl = np.array([0.30 * (c1 - c0), 0.20 * zc, 0.5 * lw + 0.8e-3])
    isl += box_islands(o + [xm, 0.0, -(zc + 0.5 * lw - 0.8e-3)], _inset(hl), 'collar', J0, 'collar lug')
    hd = 2.2e-3
    isl += revolve_islands([(0.5 * hd, hl[1] - 0.3e-3), (0.5 * hd, hl[1] + 1.35e-3), (0.0, hl[1] + 1.35e-3)],
                           o + [xm, 0.0, -(zc + 0.5 * lw)], Y, 8, 'screw', J0, 'lug screw')
    H = des['hose']
    Fi = H['fitting']
    r8 = Fi['r8']
    isl += revolve_islands([(1.55 * r8, -1.5e-3), (1.55 * r8, 0.5 * r8), (0.0, 0.5 * r8)],
                           o + [Fi['E'][0], H['y_collar'] - 0.3e-3, 0.0], Y, n_sides(1.55 * r8), 'fitting', J0,
                           'hose fitting')
    isl += revolve_islands([(1.18 * r8, -0.9 * r8), (1.18 * r8, 0.72 * r8), (0.0, 0.72 * r8)], o + Fi['E'], Fi['d0'],
                           n_sides(1.18 * r8), 'fitting', J0, 'hose fitting ferrule')
    rr = 0.5 * D['roll']
    r_roll = float(radius_at(chain, fl['roll_x'])) / chain['ring']['r_nominal']
    Ploop = resample_polygon(Fo * r_roll + (rr - D['roll_sink']) * n_, 20)
    tl = np.roll(Ploop, -1, 0) - np.roll(Ploop, 1, 0)
    tl /= np.linalg.norm(tl, axis=1, keepdims=True)
    tl3 = np.column_stack([np.zeros(len(tl)), tl])
    cen = np.column_stack([np.full(len(Ploop), fl['roll_x']), Ploop]) + o
    na = n_sides(rr)                    # C5a-2: 8 sides at the module's sagitta (C5a's 6: 0.41 mm, U5 over SAG)
    rows = []
    for i in range(len(cen)):
        e1 = X
        e2 = np.cross(tl3[i], e1)
        ang = np.linspace(0.0, TAU, na, endpoint=False)
        rows.append(cen[i] + rr * (np.cos(ang)[:, None] * e1 + np.sin(ang)[:, None] * e2))
    rows.append(rows[0])
    V, F, UV = _grid(np.stack(rows), closed=True)
    isl.append(_island(V, F, UV, 'roll', J0, 'roll'))
    # ---- the segments (8..23): each shell on its shell body (its bone, or the turning shell's helper), the tip's boss,
    # the clamp collars; then every body's knuckle pieces (knuckle_parts: the high's own specs)
    shells = {}
    for k in range(CUT, N_JOINTS):
        o = np.array([x[k], 0.0, 0.0])
        s_ = des['segs'][k]
        sb = shell_body(des, k)
        si, bn = shell_islands(chain, des, k, o, body=sb)
        shells[k] = bn
        isl += si
        if s_['tip']:
            rt_ = float(radius_at(chain, x[k] + bn['x1']))
            x1, L = bn['x1'], s_['L']
            e = 0.62 * rt_
            isl += revolve_islands([(0.88 * rt_, x1 - 0.8e-3), (0.88 * rt_, x1 + 0.10 * (L - x1)),
                                    (e, x1 + 0.30 * (L - x1)), (e, L), (0.0, L)], o, X, n_sides(rt_), 'boss', k,
                                   'tip boss')
        for c in des['clamps']:
            if c['k'] != k:
                continue
            rh_, R, L_ = c['rh'], c['R'], c['L']
            cpos = np.array([c['x'], c['y'], 0.0])
            # the collar's wall is 0.12 of the hose's radius: its low's sagitta held to half the wall (the six-sided
            # low of the small collars put its flats' middles INSIDE the bore, under the hose's own surface, and their
            # centroids nearer the bore than the outer face, so orient_islands turned the band inward)
            wall = R - rh_
            ns = n_sides(R, lo=6, hi=12, sag=min(0.30e-3, 0.5 * wall))
            # the ring's low ends stand LOW_INSET inside the high's (its rim at a flat's middle sat ON the high's end
            # face where the flat's sagitta reached the edge break: misses along one rim of every small collar)
            hx = 0.5 * L_ - min(LOW_INSET, 0.12 * L_)
            # a wall under a texel (0.25 mm) keeps no end faces: the band alone (its annuli under half a texel wide)
            prof = [(rh_, -hx), (R, -hx), (R, hx), (rh_, hx)] if wall >= 0.25e-3 else [(R, -hx), (R, hx)]
            ci = revolve_islands(prof, cpos, X, ns, 'clamp', k, f'clamp {k}')
            ci += box_islands(cpos + [0.0, 0.0, 0.5 * (c['R_lug'] + rh_)],
                              _inset([0.42 * L_, 0.30 * c['D'], 0.5 * (c['R_lug'] - rh_)]), 'clamp', k,
                              f'clamp lug {k}')
            ytop = des['top'](c['x'])
            y0, y1 = ytop - saddle_sink(des, c), c['y'] - 0.5 * (R + rh_)
            ci += box_islands([c['x'], 0.5 * (y0 + y1), 0.0], _inset([0.45 * L_, 0.5 * (y1 - y0), 0.75 * R], axes=(0, 2)),
                              'clamp', k, f'saddle {k}')
            for it in ci:
                it['body'] = sb
            isl += ci
    for body in des['bodies']:
        if body == bone_name(J0):
            continue
        ob = np.array([x[body_k(body)], 0.0, 0.0])
        for sp, pv in body_specs(chain, des, body):
            isl += _spec_islands(sp, ob + pv, body_k(body))
    # ---- the band (skinned 7 -> 8)
    Mb = 24
    b0, b1 = fl['band']
    Cf, _, _ = collar_outline(chain, 96)
    Ac = section_apothems() * float(chain['r'][CUT])
    k0 = resample_polygon(Cf * D['band_od'], Mb)
    k1 = resample_polygon(octagon(Ac) * 1.03, Mb)
    xs, t, wave = band_nodes(des)
    rows = []
    for xv, tv, wv in zip(xs, t, wave):
        S = (k0 * (1.0 - tv) + k1 * tv) * wv
        rows.append(np.column_stack([np.full(Mb, x[J0] + xv), S[:, 0], S[:, 1]]))
    V, F, UV = _grid(np.stack(rows), closed=True)
    band = _island(V, F, UV, 'band', J0, 'band')
    wb = np.clip((V[:, 0] - (x[J0] + b0)) / (b1 - b0), 0.0, 1.0)
    wb = wb * wb * (3.0 - 2.0 * wb)
    # its skin: joint indices into des['joints'] (bone k is k - J0)
    band['skin'] = np.stack([np.stack([np.full(len(V), 0), 1.0 - wb], 1), np.stack([np.full(len(V), CUT - J0), wb], 1)],
                            1)
    isl.append(band)
    # ---- the hose (skinned), cut into islands that fit the sheet
    isl += hose_islands(chain, des)
    return isl, shells


HOSE_RING_TURN = 0.20       # rad: the most a ring step may turn the tube, at rest plus what the skinning adds posed (C5a-2's
                            # check: rings every 0.30 rad of the REST curvature alone left 3-6 rings per arch, each arch a
                            # polyline: 10-18 deg at one ring at rest, 23-29 deg posed at the knuckles' largest yaws (at the
                            # crests of 19-21 too), 17-28 in the curl; at 0.20 with the posed bend, on the low: 6.5-11 at rest,
                            # 9-10 posed at 16-19, 14-17 at 20-22 (the 0.5 r floor), 9-17 in the curl; c5a2_check/chk04)


def hose_islands(chain, des):
    """the bundle's tube, one island per arch: from the middle of one clamp to the middle of the next (every island's
    end ring hides inside a clamp collar, so the side count can step down along the arm without a visible crack).
    Rings at stations at least 0.5 and at most 3.5 radii apart, each step turning the tube at most HOSE_RING_TURN: the
    path's own curvature plus the bend the skinning adds posed (the second weight's rate along the path times the
    largest turn between the two joints it blends: the knuckle's design yaw and pitch and the parent shell's roll; over
    a crest half, half the yaw), integrated over the step (a look-ahead: a station's own curvature sample missed the
    fitting's elbow, one 35 deg ring); sides by the island's largest radius at a 0.3 mm sagitta (4 to 8); the weights per
    vertex from the path's (hose_skin: joint indices)"""
    H = des['hose']
    P, r, w = H['P'], H['r'], H['w']
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    T = np.gradient(P, s, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    curv = np.linalg.norm(np.gradient(T, s, axis=0), axis=1)
    # the posed bend rate: where the path blends joints a -> b, d(w_b)/ds x the largest turn between them (radians)
    kn, jn = des['kn'], des['joints']
    w2 = w[:, 1, 1]
    th = np.zeros(len(P))
    for i in range(len(P)):
        if w[i, 1, 1] <= 0.0 or w[i, 0, 1] >= 1.0:
            continue
        na, nb = jn[int(w[i, 0, 0])], jn[int(w[i, 1, 0])]
        kk = max(body_k(na), body_k(nb))
        K = kn.get(kk)
        if K is None:
            continue
        Kp = kn.get(kk - 1)
        roll_p = math.radians(Kp['roll_max']) if (Kp is not None and (kk - 1) in des['ring']) else 0.0
        crest = body_kind(na) == 'crest' or body_kind(nb) == 'crest'
        th[i] = (0.5 if crest else 1.0) * K['yaw_d'] + K['pitch_d'] + roll_p
    bend = np.abs(np.gradient(w2, s)) * th
    jump = np.abs(np.diff(w2)) > 0.5                       # a hold or the crest swaps the joint pair: no rate there
    bend[np.concatenate([jump, [False]]) | np.concatenate([[False], jump])] = 0.0
    rate = curv + bend
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (rate[1:] + rate[:-1]) * seg)])     # the turn integral along s
    # the island ends: each clamp's centre on the path (on its straight run, where the arc length is x's); and a ring at
    # each clamp's two FACES, so the tube runs straight and rigid through its collar. With a ring at the centre only,
    # the next ring stood 1-3.5 radii out on the arch: the run tilted inside the collar (a kink at every clamp, the
    # tube poking through the collar's band at rest and through its lug in motion: C5a's check)
    def s_on_run(c):
        on = np.nonzero((np.abs(P[:, 1] - c['y']) < 1e-12) & (np.abs(P[:, 0] - c['x']) <= 0.5 * c['L'] + 1e-9))[0]
        i0 = int(on.min())
        return float(s[i0] + (c['x'] - P[i0, 0]))
    s_cl = [s_on_run(c) for c in des['clamps']]
    faces = sorted(sc + sg * 0.5 * c['L'] for sc, c in zip(s_cl, des['clamps']) for sg in (-1.0, 1.0))
    ends = [0.0] + s_cl + [float(s[-1])]
    Z = np.array([0.0, 0.0, 1.0])
    out = []
    for a, b in zip(ends[:-1], ends[1:]):
        cuts = [f_ for f_ in faces if a + 1e-6 < f_ < b - 1e-6] + [b]
        st = [a]
        for b2 in cuts:
            while st[-1] < b2 - 1e-6:
                i = min(int(np.searchsorted(s, st[-1])), len(s) - 1)
                # (at least half a radius apart on a tight bend: at 1.0 r the riser's 2.2 r arc took 26 deg per ring
                # and its tapered quads sheared to a stretch of 1.68, U4); the longest step whose turn, at rest and
                # posed, stays within HOSE_RING_TURN
                lo_, stp = 0.5 * r[i], 3.5 * r[i]
                while stp > lo_ and (np.interp(min(st[-1] + stp, b2), s, cum) - np.interp(st[-1], s, cum)
                                     > HOSE_RING_TURN):
                    stp *= 0.85
                stp = max(stp, lo_)
                nxt = st[-1] + stp
                st.append(b2 if nxt > b2 - 0.4 * stp else nxt)
        st = np.array(st)
        Pi = np.column_stack([np.interp(st, s, P[:, j]) for j in range(3)])
        ri = np.interp(st, s, r)
        Ti = np.column_stack([np.interp(st, s, T[:, j]) for j in range(3)])
        Ti /= np.linalg.norm(Ti, axis=1, keepdims=True)
        na = n_sides(float(ri.max()), lo=4, hi=8, sag=0.30e-3)
        ang = np.linspace(0.0, TAU, na, endpoint=False) + math.pi / na
        rows = []
        for i in range(len(Pi)):
            e2 = np.cross(Ti[i], Z)
            e2 /= np.linalg.norm(e2)
            e1 = np.cross(e2, Ti[i])
            rows.append(Pi[i] + ri[i] * (np.cos(ang)[:, None] * e2 + np.sin(ang)[:, None] * e1))
        rows = np.stack(rows)
        wi = np.stack([w[min(int(np.searchsorted(s, v)), len(s) - 1)] for v in st])
        V, F, UV = _grid(rows, closed=True)
        it = _island(V, F, UV, 'hose', CUT, f'hose {a * 1e3:.0f}-{b * 1e3:.0f}', smooth='hose')
        it['skin'] = np.repeat(wi, na + 1, axis=0)
        out.append(it)
    # the end cap past the tip's clamp
    V, F, UV = _fan(rows[-1])
    it = _island(V, F, UV, 'hose', N_JOINTS - 1, 'hose end')
    it['skin'] = np.repeat(wi[-1:], len(V), axis=0)
    out.append(it)
    return out


def orient_islands(isl, field_of):
    """every island's triangles turned to face out: the majority vote of their normals against the SDF's gradient at
    their centroids (field_of(island) -> the Program its piece belongs to)"""
    for it in isl:
        V, F = it['V'], it['F']
        c = V[F].mean(1)
        fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
        g = field_of(it).normals(c)
        if (np.einsum('ij,ij->i', fn, g) < 0.0).sum() > 0.5 * len(F):
            it['F'] = F[:, ::-1].copy()
    return isl


def pack_rect(isl_uvs, isl_scale, W, H, pad):
    """forge.uv.pack's skyline for a W x H sheet (W the wide side): each island laid flat (its long side along x, a
    quarter turn when needed), the tallest first, at the lowest skyline over its width (a sliding maximum). Returns the
    UVs in canvas units (x / W, y / W: the sheet is the bottom H / W of a W x W canvas) and the height used (texels)"""
    from scipy.ndimage import maximum_filter1d
    boxes = []
    for i, (Uu, s) in enumerate(zip(isl_uvs, isl_scale)):
        T = (Uu - Uu.min(0)) * s
        pd = pad if T.max() >= 32.0 else min(pad, 2)          # small islands: 4-texel gutters between them
        w, h = T.max(0) + 2 * pd
        if h > w:
            T = np.column_stack([T[:, 1], T.max(0)[0] - T[:, 0]])
            w, h = h, w
        boxes.append((i, T, int(np.ceil(w)), int(np.ceil(h)), pd))
    sky = np.zeros(W, np.int64)
    out = [None] * len(isl_uvs)
    for i, T, w, h, pd in sorted(boxes, key=lambda b_: (-b_[3], -b_[2])):
        if w > W:
            raise ValueError(f'island {i} ({w}x{h} texels) wider than the sheet')
        m = maximum_filter1d(sky, size=w, mode='constant', cval=1 << 40, origin=-(w // 2))[:W - w + 1]
        x0 = int(np.argmin(m))
        y0 = int(m[x0])
        sky[x0:x0 + w] = y0 + h
        out[i] = (T + np.array([x0 + pd, y0 + pd])) / W
    return out, int(sky.max())


def pack_islands(isl, size=SET, pad=3, log=print):
    """one texel density over the set (each island at its own factor), packed into the W x H sheet (pack_rect): at
    least PX_TARGET (the plan's 5,046 px/m, the lead's call 4), raised while the sheet holds it (its height used to
    99 % at most). Returns px_per_m and the height share used; writes each island's 'UVp' (canvas units)"""
    from . import uv as U
    W, H = size
    area = 0.0
    for it in isl:
        V, F = it['V'], it['F']
        a = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1).sum()
        it['area'] = a
        area += a * it['dens'] ** 2
    dens = [U.island_density(it['V'], it['F'], it['UV']) for it in isl]
    uvs = [it['UV'] for it in isl]
    sc = lambda px_: [px_ * it['dens'] / max(d, 1e-12) for it, d in zip(isl, dens)]
    packed, used = pack_rect(uvs, sc(PX_TARGET), W, H, pad)
    if used > H:
        raise ValueError(f'[cyborg_limb] the {W} x {H} set cannot hold {PX_TARGET:.0f} px/m ({used} rows)')
    best = (PX_TARGET, packed, used)
    lo, hi = PX_TARGET, PX_TARGET * math.sqrt(H / max(used, 1)) * 1.08
    for _ in range(10):
        mid = 0.5 * (lo + hi)
        try:
            p2, u2 = pack_rect(uvs, sc(mid), W, H, pad)
        except ValueError:
            hi = mid
            continue
        if u2 <= 0.99 * H:
            lo, best = mid, (mid, p2, u2)
        else:
            hi = mid
    px, packed, used = best
    for it, pk in zip(isl, packed):
        it['UVp'] = pk
    log(f'[cyborg_limb] uv: {len(isl)} islands, {px:.0f} px/m on a {W} x {H} set ({1000.0 / px:.3f} mm/texel; the plan\'s '
        f'{PX_TARGET:.0f} fills {100.0 * (PX_TARGET / px) ** 2 * used / H:.0f} % of it), height used {used} of {H}, '
        f'surface {area * 1e4:.1f} cm2 (density-weighted)')
    return px, used / H


def low_arrays(isl, des=None):
    """the islands merged: V, F, UV (canvas units), per-vertex N (each island's own smooth normals, welded by position
    inside it: hard edges at every island border, as the body's lows: hard edges on UV seams), TAN (bake.low_frames),
    region and piece per triangle, the skin per vertex (joint INDICES into des['joints'], weights: a rigid piece's body
    at 1, the band's and the hose's pairs)"""
    from . import bake
    jidx = {n: i for i, n in enumerate(des['joints'])} if des is not None else None
    Vs, Fs, UVs, Ns, reg, piece, J, W = [], [], [], [], [], [], [], []
    n0 = 0
    names = []
    for ii, it in enumerate(isl):
        V, F = it['V'], it['F']
        fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
        key = np.round(V / 1.0e-7).astype(np.int64)
        _, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.reshape(-1)
        acc = np.zeros((inv.max() + 1, 3))
        for c in range(3):
            np.add.at(acc, inv[F[:, c]], fn)
        N = acc[inv]
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)
        Vs.append(V)
        Fs.append(F + n0)
        UVs.append(it['UVp'])
        Ns.append(N)
        reg.append(np.full(len(F), it['region'], np.int32))
        piece.append(np.full(len(F), ii, np.int32))
        names.append(it['piece'])
        if 'skin' in it:
            J.append(it['skin'][:, :, 0].astype(np.int32))
            W.append(it['skin'][:, :, 1])
        else:
            j_ = jidx[it['body']] if jidx is not None else it['bone'] - J0
            J.append(np.tile([j_, j_], (len(V), 1)).astype(np.int32))
            W.append(np.tile([1.0, 0.0], (len(V), 1)))
        n0 += len(V)
    V = np.concatenate(Vs)
    F = np.concatenate(Fs)
    UV = np.concatenate(UVs)
    N = np.concatenate(Ns)
    _, TAN = bake.low_frames(V, F, UV, N)
    return dict(V=V, F=F, UV=UV, N=N, TAN=TAN, region=np.concatenate(reg), piece=np.concatenate(piece),
                names=names, joints=np.concatenate(J), weights=np.concatenate(W))


# ============================================================================================ details (bake tier)
SEAM_TX = 3.0               # panel seams 3 texels wide (A.2.1: the default; C1's texel rule), depth 0.5 x the width
HEAD_TX = 10.0              # fastener heads 10 texels (A.2.1, C1 / C2), one physical size on the set
SCREW_SINK = 0.3e-3         # a head 0.3 mm below its face, in a counterbore 0.3 mm radial over it (the body's grammar,
CB_RADIAL = 0.3e-3          # A.4.3 / kit_body §2.6: 0.3-0.9 below, 0.25-0.5 radial)
HEAD_H_D = 0.31             # head height over its diameter (study G's 0.31 D [R-rf])
SCREW_LAND = 0.5e-3         # a seam stops this short of a head's mouth (A.2.2)


def flat_frame(k, flat):
    """an octagon flat's direction in a shell's section: the unit normal (y, z) and the in-plane axis (y, z)"""
    th = math.radians(45.0 * flat)
    n = np.array([math.cos(th), math.sin(th)])
    return n, np.array([-n[1], n[0]])


def details(chain, des, px_per_m):
    """the panels, seams and fasteners in each rigid group's own frame, sized in TEXELS of the set (seams 3, heads 10):
    on every shell an access panel on each lateral flat and a skid plate on the oral flat (a rounded-rectangle seam
    inset on the flat, 'ends' heads: one at each end where the flat is at least 2.5 heads wide: the body's "none on
    lands narrower than ~2.5 heads"), and four radial set screws in the collar. Returns {group: dict(seams [polylines
    (n, 3)], heads [dict(p, n, D)], panels [...])} and the sizes"""
    tex = 1.0 / px_per_m
    w = SEAM_TX * tex
    D = HEAD_TX * tex
    Au = section_apothems()
    out = {}
    for k in range(CUT, N_JOINTS):
        s_ = des['segs'][k]
        bn = body_nodes(chain, des, k)
        rho = bn['rho']
        g = dict(seams=[], heads=[], panels=[])
        xk = chain['x'][k]
        # the flats' extents in r units: (normal index, half-width along the flat)
        V8 = octagon(Au)
        x_lo, x_hi = bn['x0'], bn['x1']
        if s_['minsky']:
            bl = DESIGN['minsky_block'] * s_['L']
            x_lo, x_hi = x_lo + bl, x_hi - bl
        x_lo += chamfer_setback(des, k)
        for flat in (2, 6, 4):
            n2, t2 = flat_frame(k, flat)
            a, b = V8[flat - 1], V8[flat % 8]          # the flat's two sharp corners (r units)
            ta, tb = sorted([float(a @ t2), float(b @ t2)])
            r_mid = float(radius_at(chain, xk + 0.5 * (x_lo + x_hi)))
            if s_['minsky'] and flat in (2, 6):
                continue                                 # the waist: no lateral panels on Minsky's frames
            inset = rho + 1.2 * w + 0.4e-3
            hu0, hu1 = ta * r_mid + inset, tb * r_mid - inset
            hx0, hx1 = x_lo + 1.0 * w + 0.6e-3, x_hi - 1.0 * w - 0.6e-3
            if hu1 - hu0 < 3.0 * w + 1.0e-3 or hx1 - hx0 < 4.0 * w + 2.0e-3:
                continue
            rc = min(0.25 * (hu1 - hu0), 0.25 * (hx1 - hx0), 2.0e-3)
            # the outline in (x, u), u along the flat; its points on the surface: the flat's plane at each x
            P2 = _rrect(hx0, hx1, hu0, hu1, rc, step=0.4e-3)
            pts = []
            for xv, uv_ in P2:
                rr = float(radius_at(chain, xk + xv))
                apo = Au[flat] * rr
                yz = n2 * apo + t2 * (uv_ * rr / r_mid)
                pts.append([xv, yz[0], yz[1]])
            g['seams'].append(np.array(pts))
            pan = dict(flat=flat, x=(hx0, hx1), u=(hu0, hu1), heads=0)
            # a head 2 D in from each end where they stand at least 1.5 D apart (centre to centre); on a shorter
            # panel ONE head at its middle (two ends' heads 2 D in from a 4-5.5 D panel overlapped: a figure 8)
            span = hx1 - hx0
            hxs = (hx0 + 2.0 * D, hx1 - 2.0 * D) if span >= 5.5 * D else \
                ((0.5 * (hx0 + hx1),) if span >= 3.0 * D else ())
            if hu1 - hu0 >= 2.5 * D:
                for xv in hxs:
                    rr = float(radius_at(chain, xk + xv))
                    um = 0.5 * (hu0 + hu1) * rr / r_mid
                    yz = n2 * Au[flat] * rr + t2 * um
                    g['heads'].append(dict(p=np.array([xv, yz[0], yz[1]]), n=np.array([0.0, n2[0], n2[1]]), D=D))
                    pan['heads'] += 1
            g['panels'].append(pan)
        out[shell_body(des, k)] = g
    # the collar's four radial set screws (p01's receiver: four set screws), on its proximal half, clear of the
    # fitting (aboral) and the lug (-z)
    fl = des['flange']
    C, _, n_ = collar_outline(chain, 360)
    th = np.arctan2(C[:, 1], C[:, 0])
    gc = dict(seams=[], heads=[], panels=[])
    xs = fl['collar'][0] + 0.42 * DESIGN['collar_h']
    for deg in (55.0, 125.0, 235.0, 305.0):
        i = int(np.argmin(np.abs(((th - math.radians(deg)) + math.pi) % TAU - math.pi)))
        gc['heads'].append(dict(p=np.array([xs, C[i, 0], C[i, 1]]), n=np.array([0.0, n_[i, 0], n_[i, 1]]), D=D,
                                kind='set'))
    # the collar's distal edge: a bright machined ring (a material band) and a seam where the clamp splits (the slit)
    out[bone_name(J0)] = gc
    return out, dict(seam_w=w, seam_d=0.5 * w, head_D=D, texel=tex)


def _rrect(x0, x1, u0, u1, rc, step=0.4e-3):
    """a rounded rectangle's outline in (x, u), closed, sampled every `step`"""
    pts = []
    corners = [(x1 - rc, u1 - rc, 0.0), (x0 + rc, u1 - rc, 0.5 * math.pi), (x0 + rc, u0 + rc, math.pi),
               (x1 - rc, u0 + rc, 1.5 * math.pi)]
    for cx, cu, a0 in corners:
        for a in np.linspace(a0, a0 + 0.5 * math.pi, max(3, int(math.ceil(0.5 * math.pi * rc / step))) + 1):
            pts.append((cx + rc * math.cos(a), cu + rc * math.sin(a)))
    pts.append(pts[0])
    P = np.array(pts)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.linspace(0.0, s[-1], max(8, int(math.ceil(s[-1] / step))) + 1)
    return np.column_stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])])


def detail_plan(det, sizes, offsets):
    """the details as voxel stroke batches (octopus_sculpt.Plan): the seams as capsule chains centred on the surface
    (radius w / 2 at depth w / 2: the body's round capsule tube, A.2.1), each fastener a counterbore carve then its pan
    head (STROKE_CYL), a set screw a socket hole; into the exploded frame by offsets {group: (3,)}, each group's whole
    translation (its joint's x plus its explode offset)"""
    from .species.octopus_sculpt import Plan
    from .voxel import STROKE_CONE, STROKE_CYL
    plan = Plan()
    w = sizes['seam_w']
    for k, g in det.items():
        o = np.asarray(offsets[k], np.float64)
        heads = g['heads']
        for P in g['seams']:
            P = P + o
            A, B = P[:-1], P[1:]
            if heads:
                Hp = np.array([h['p'] + o for h in heads])
                Hr = np.array([0.5 * h['D'] + CB_RADIAL + SCREW_LAND for h in heads])
                mid = 0.5 * (A + B)
                dd = np.linalg.norm(mid[:, None] - Hp[None], axis=2) - Hr[None] - 0.5 * w
                keep = dd.min(1) > 0.0
                A, B = A[keep], B[keep]
            plan.add(STROKE_CONE, A, B, 0.5 * w, 0.5 * w, 'carve', 0.06e-3, f'seam {k}')
        for h in heads:
            p = h['p'] + o
            n = h['n'] / np.linalg.norm(h['n'])
            D = h['D']
            hh = HEAD_H_D * D
            if h.get('kind') == 'set':
                plan.add(STROKE_CYL, [p - n * 0.9e-3], [p + n * 0.6e-3], 0.5 * D * 0.62, 0.05e-3, 'carve', 0.05e-3,
                         f'set screw {k}')
                continue
            plan.add(STROKE_CYL, [p - n * (SCREW_SINK + hh)], [p + n * 0.6e-3], 0.5 * D + CB_RADIAL, 0.05e-3, 'carve',
                     0.05e-3, f'counterbore {k}')
            plan.add(STROKE_CYL, [p - n * (SCREW_SINK + hh + 0.2e-3)], [p - n * SCREW_SINK], 0.5 * D,
                     min(0.25 * hh, 0.2e-3), 'add', 0.04e-3, f'head {k}')
    return plan


def pack_explode(isl, des, gap=0.022, lift=0.12):
    """the bake's exploded layout from the low (make_asset keeps it in des['explode']): the rigid bodies one after
    another along x, each `gap` past the previous one's low (wider than the cage and the AO radius together: nothing of
    one part can occlude or be found from another, A.4.3 / U11 "AO against the part's own rigid group only"), the band
    and the hose lifted clear above. C5a-2: with every body at its own x plus i x gap, the helpers (after the bones)
    landed on the distal bones, 16_cross 6 mm from bone 21: 15-100 % of the crosses' texels baked another part"""
    ext = {}
    for it in isl:
        b_ = it.get('body')
        if b_ is None or REGIONS[it['region']] in ('band', 'hose'):
            continue
        lo_, hi_ = float(it['V'][:, 0].min()), float(it['V'][:, 0].max())
        e = ext.get(b_, (np.inf, -np.inf))
        ext[b_] = (min(e[0], lo_), max(e[1], hi_))
    off = {}
    cur = None
    for b_ in des['bodies']:
        lo_, hi_ = ext.get(b_, (0.0, 0.0))
        cur = lo_ if cur is None else cur
        off[b_] = np.array([cur - lo_, 0.0, 0.0])
        cur = hi_ + (cur - lo_) + gap
    off['band'] = np.array([0.0, lift, 0.0])
    off['hose'] = np.array([0.0, 2.0 * lift, 0.0])
    return off


def explode_offsets(chain, des, gap=0.022, lift=0.12):
    """the bake's exploded layout: des['explode'] (pack_explode, from the low) once make_asset has set it; before that
    every rigid body shifted along x by its own multiple of `gap`, the band and the hose lifted clear above"""
    if 'explode' in des:
        return {k_: np.array(v_, np.float64) for k_, v_ in des['explode'].items()}
    off = {b_: np.array([i * gap, 0.0, 0.0]) for i, b_ in enumerate(des['bodies'])}
    off['band'] = np.array([0.0, lift, 0.0])
    off['hose'] = np.array([0.0, 2.0 * lift, 0.0])
    return off


def piece_offset(it, off):
    """an island's exploded offset: its body's, or the band's / the hose's"""
    rn = REGIONS[it['region']]
    if rn in ('band', 'hose'):
        return off[rn]
    return off[it['body']]


# ---- C5a-3: the OWN-PIECE search's layout and high
SLOT_GAP = 0.010            # the slots stand this far apart (more than the cage, 4 mm, from either side)


def prog_bounds(prog):
    """a Program's extent: its union primitives' padded bounds (sdf.Program keeps each one's AABB in par[24:30])"""
    from . import sdf
    P = np.array([p[24:30] for p, o_ in zip(prog.par, prog.op) if o_ != sdf.SUBTRACT], np.float64).reshape(-1, 6)
    assert len(P) and np.all(np.abs(P) < 1.0e3), 'a piece without bounds'
    return P[:, :3].min(0), P[:, 3:].max(0)


def piece_program(A, kp):
    """a piece's Program in the asset frame (the assembled place): its union primitive with its group's cuts, the band,
    the hose"""
    b_, p_ = kp
    if b_ in ('band', 'hose'):
        return A['band_prog'] if b_ == 'band' else A['hose_prog']
    if (b_, p_) not in A['own']:
        A['own'][(b_, p_)] = own_program(A['progs_piece'][b_], p_)
    return A['own'][(b_, p_)]


def pack_slots(A, vs, gap=SLOT_GAP):
    """the own-piece search's layout: every piece of A['pieces'] alone, the rigid ones one after another along x, each
    `gap` past the previous one's bounds, the band and the hose where the body layout lifts them (clear already). A slot's
    offset differs from its body's explode offset by whole voxels, so the slot high samples a piece at the places the body
    high does. Returns per piece its offset (3,) from the assembled place and its box in the slot layout"""
    off_b = explode_offsets(A['chain'], A['des'])
    offs, boxes = [], []
    cur = None
    for kp in A['pieces']:
        lo, hi = prog_bounds(piece_program(A, kp))
        ob = np.asarray(off_b[kp[0]], np.float64)
        if kp[0] in ('band', 'hose'):
            o = ob.copy()
        else:
            cur = lo[0] if cur is None else cur
            o = ob + np.array([np.round((cur - lo[0] - ob[0]) / vs) * vs, 0.0, 0.0])
            cur = hi[0] + o[0] + gap
        offs.append(o)
        boxes.append((lo + o, hi + o))
    return np.array(offs), boxes


def slot_layout(A, E, vs, gap=SLOT_GAP):
    """the own-piece search's high, its parts: the slots (pack_slots), the Program of every piece in its slot, the detail
    plan on the pieces that carry the details (a shell's panels and heads on its shell, the collar's set screws on the
    collar), the low in the slot layout, per triangle the slot -> body layout translation, the bounds (the origin on the
    body high's voxel lattice)"""
    from . import sdf
    chain, des = A['chain'], A['des']
    offs, boxes = pack_slots(A, vs, gap)
    prog = sdf.Program()
    for i, kp in enumerate(A['pieces']):
        n0 = len(prog.kind)
        if kp[0] == 'band':
            band_program(chain, des, prog, offs[i])
        elif kp[0] == 'hose':
            hose_program(chain, des, prog, offs[i])
        else:
            group_program(chain, des, kp[0], prog, np.array([chain['x'][body_k(kp[0])], 0.0, 0.0]) + offs[i], bake=True,
                          split=True, only=kp[1])
        assert len(prog.kind) > n0, f'piece {kp} emitted nothing'
    pk = {kp: i for i, kp in enumerate(A['pieces'])}
    tr = {}
    for b_ in A['det']:
        p_ = 'flange collar' if b_ == bone_name(J0) else f'shell {body_k(b_)}'
        tr[b_] = np.array([chain['x'][body_k(b_)], 0.0, 0.0]) + offs[pk[(b_, p_)]]
    plan = detail_plan(A['det'], A['sizes'], tr)
    off_b = E['off']
    isl_off = offs[A['isl_pid']]                                   # per island: its slot's offset
    dlt_isl = np.array([piece_offset(it, off_b) for it in A['isl']]) - isl_off
    Vs = A['L']['V'] + np.concatenate([np.tile(isl_off[i], (len(it['V']), 1)) for i, it in enumerate(A['isl'])])
    lo = np.min([b[0] for b in boxes], axis=0) - 0.012
    hi = np.max([b[1] for b in boxes], axis=0) + 0.012
    lo = E['lo'] + np.floor((lo - E['lo']) / vs) * vs
    return dict(off=offs, boxes=boxes, prog=prog, plan=plan, V=Vs, dlt_isl=dlt_isl, dlt_tri=dlt_isl[A['L']['piece']],
                lo=lo, hi=hi)


@wp.kernel
def k_slot_ids(ijk: wp.array(dtype=wp.vec3i), vol: wp.uint64, lo: wp.array(dtype=wp.vec3), hi: wp.array(dtype=wp.vec3),
               n_box: int, out: wp.array(dtype=wp.int32), dist: wp.array(dtype=wp.float32)):
    """each voxel of the slot high: the piece whose slot box lies nearest (and how far: 0 inside it)"""
    t = wp.tid()
    c = ijk[t]
    p = wp.volume_index_to_world(vol, wp.vec3(float(c[0]), float(c[1]), float(c[2])))
    best = int(-1)
    bd = float(1.0e9)
    for b in range(n_box):
        q = wp.vec3(wp.max(wp.max(lo[b][0] - p[0], p[0] - hi[b][0]), 0.0),
                    wp.max(wp.max(lo[b][1] - p[1], p[1] - hi[b][1]), 0.0),
                    wp.max(wp.max(lo[b][2] - p[2], p[2] - hi[b][2]), 0.0))
        d = wp.length(q)
        if d < bd:
            bd = d
            best = b
    out[t] = best
    dist[t] = bd


def slot_voxel_ids(S, slots):
    """THE PART IDS IN THE VOXEL HIGH: every voxel of the slot high names the piece of its slot. Returns the id array
    (device) and the farthest any voxel lies outside its slot's box (m)"""
    lo = wp.array(np.array([b[0] for b in slots['boxes']], np.float32), dtype=wp.vec3)
    hi = wp.array(np.array([b[1] for b in slots['boxes']], np.float32), dtype=wp.vec3)
    out = wp.zeros(S.n, dtype=wp.int32)
    dist = wp.zeros(S.n, dtype=wp.float32)
    wp.launch(k_slot_ids, dim=S.n, inputs=[S.ijk, S.vol.id, lo, hi, len(slots['boxes']), out, dist])
    return out, float(dist.numpy().max())


# ============================================================================================ the asset: low, high, bake
def make_asset(size=SET, log=print, stack=True):
    """the CPU half: the arm, its motion's reach, the design, the low (buried faces cut away, oriented, packed into the
    W x H set), the details sized on the plan's density. Returns a dict the GPU half (bake_asset) and the material pass
    read: size the bake's square canvas (W), set (W, H) the shipped maps, UV the canvas UVs, UV_tex the maps' (v x W/H)"""
    if stack:
        # C5d (Skye 10-27, the lead's calls 1-4): every repeated piece GIVEN its family's largest's low and texels;
        # only the primaries and the unique pieces packed (the smallest set that holds them at C5c's density) and
        # baked (A['bake']); A's own 'isl' / 'L' are the whole low as exported, posed and gated
        from . import cyborg_stack
        return cyborg_stack.stacked_asset(size=None if size == SET else size, log=log)
    chain = arm_chain()
    lim = motion_limits(chain)
    des = design(chain, lim)
    isl, shells = build_low(chain, des, log=log)
    X0 = lambda b_: (chain['x'][body_k(b_)], 0.0, 0.0)
    progs = {b_: group_program(chain, des, b_, offset=X0(b_)) for b_ in des['bodies']}
    progs_bake = {b_: group_program(chain, des, b_, offset=X0(b_), bake=True) for b_ in des['bodies']}
    # C5a-3: the same with a clevis drum's can or cap as its own primitive: the PIECES the own-piece search bakes from
    progs_piece = {b_: group_program(chain, des, b_, offset=X0(b_), bake=True, split=True) for b_ in des['bodies']}
    pb = band_program(chain, des, offset=(chain['x'][J0], 0.0, 0.0))
    ph = hose_program(chain, des)
    isl = clip_buried(isl, progs_bake, log=log)
    isl = clip_nested(isl, des, progs_bake, log=log)
    des['explode'] = pack_explode(isl, des)
    pieces, isl_pid = island_pieces(isl, progs_piece, des['bodies'])
    for it, p_ in zip(isl, isl_pid):
        it['pid'] = int(p_)
    own = {}

    def field_of(it):
        """an island's OWN piece's Program (C5a-3: orient_islands turns each island out of its own piece; against its
        body's union a face buried under a neighbour, a lug's top under its can, a tine bar's end in its shell, took the
        neighbour's gradient: 483 triangles faced inward, C5a-2's check)"""
        b_, p_ = pieces[it['pid']]
        if b_ in ('band', 'hose'):
            return pb if b_ == 'band' else ph
        if (b_, p_) not in own:
            own[(b_, p_)] = own_program(progs_piece[b_], p_)
        return own[(b_, p_)]
    orient_islands(isl, field_of)
    px, used = pack_islands(isl, size, log=log)
    L = low_arrays(isl, des)
    L['UV_tex'] = np.column_stack([L['UV'][:, 0], L['UV'][:, 1] * size[0] / size[1]])
    L['pid'] = isl_pid[L['piece']]
    det, sizes = details(chain, des, PX_TARGET)
    return dict(chain=chain, lim=lim, des=des, isl=isl, L=L, px=px, used=used, size=size[0], set=size, det=det,
                sizes=sizes, progs=progs, progs_bake=progs_bake, progs_piece=progs_piece, pieces=pieces,
                isl_pid=isl_pid, own=own, band_prog=pb, hose_prog=ph, field_of=field_of)


def exploded(A):
    """the low and the high in the bake's exploded layout: per vertex the island's offset; the assembled Program; the
    voxel bounds"""
    off = explode_offsets(A['chain'], A['des'])
    L = A['L']
    offv = np.concatenate([np.tile(piece_offset(it, off), (len(it['V']), 1)) for it in A['isl']])
    Vx = L['V'] + offv
    prog = assembled_program(A['chain'], A['des'], offsets=off, bake=True)
    lo = Vx.min(0) - 0.012
    hi = Vx.max(0) + 0.012
    return dict(off=off, V=Vx, offv=offv, prog=prog, lo=lo, hi=hi)


FLAG_COVERED = 64           # gate_flags (bake.py's FLAG_* take 1-32): a sub-sample's own surface lies inside another piece
FLAG_PART = 128             # a crossing whose voxels name another piece, refused (the slots make it impossible)
COVER_EPS = 0.075e-3        # covered: deeper than half a voxel inside the body high (its fillets at a contact line, the
                            # union's own rounding of the corner, stay under it)
NEAR_SURF = wp.constant(0.03e-3)    # a surface this near the low point (a fifth of a voxel) is the one it lies on: facing only has
                            # to hold at all there (a low face's edge row ON its piece's rounded corner, 80-85 deg off its
                            # face: the yaw lugs' band edges); facing arbitrates between surfaces farther off


REFINE_MAX = 0.20e-3        # C5c: a hit this near the EXACT surface of its own piece is moved onto it (the voxel high rounds
                            # a small part's edges 0.05-0.10 mm inside it and runs up a step's fillet: the exact truth)
AO_PUSH = wp.constant(0.03e-3)   # C5c: an AO ray's origin inside the body high's voxel fillet (a contact crease) marches
AO_CLEAR = wp.constant(0.12e-3)  # out along the hit's normal in these steps until it has this much air, at most AO_REACH
AO_REACH = wp.constant(0.45e-3)  # out, kept at its most open point (a running clearance is never crossed)


@wp.func
def prog_others(p: wp.vec3, skip: int, n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32),
                kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3),
                node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4),
                shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """C5c, THE COVER TEST'S FIELD: the EXACT field of every piece but one (primitive `skip` reads empty) at p, for a
    hit on that piece: sdf.program's groups and ops without its culling (inside an earlier group it skips every later
    one, so a hit 0.02 mm inside its own rounded edge hid its neighbour), but a UNION member whose padded box does not
    hold p reads empty (only a value under -COVER_EPS matters: p inside it). Positive values are bounds only"""
    d = float(1.0e9)
    gd = float(1.0e9)
    g0 = int(0)
    first_group = int(1)
    for i in range(n_prim):
        o = i * 32
        new_group = int(0)
        if i == 0:
            new_group = 1
        elif par[o - 32 + 20] != par[o + 20]:
            new_group = 1
        if new_group == 1 and i > 0:
            if first_group == 1:
                d = gd
                first_group = 0
            else:
                d = SD.combine(d, gd, int(par[g0 * 32 + 21]), par[g0 * 32 + 22])
        if new_group == 1:
            gd = float(1.0e9)
            g0 = i
        di = float(1.0e9)
        ev = int(1)
        if i == skip:
            ev = 0
        elif op[i] == 0:
            if SD.aabb_dist(p, wp.vec3(par[o + 24], par[o + 25], par[o + 26]),
                            wp.vec3(par[o + 27], par[o + 28], par[o + 29])) > 0.0:
                ev = 0
        if ev == 1:
            if kind[i] == 0:
                di = SD.sd_ellipsoid(p, wp.vec3(par[o], par[o + 1], par[o + 2]),
                                     wp.vec3(par[o + 3], par[o + 4], par[o + 5]),
                                     wp.vec3(par[o + 6], par[o + 7], par[o + 8]),
                                     wp.vec3(par[o + 9], par[o + 10], par[o + 11]),
                                     wp.vec3(par[o + 12], par[o + 13], par[o + 14]))
            elif kind[i] == 1:
                di = SD.sd_roundcone(p, wp.vec3(par[o], par[o + 1], par[o + 2]),
                                     wp.vec3(par[o + 3], par[o + 4], par[o + 5]), par[o + 6], par[o + 7])
            elif kind[i] == 2:
                di = SD.sd_sweep(p, int(par[o]), int(par[o + 1]), node_p, node_n, node_r, node_h)
            elif kind[i] == 4:
                di = SD.sd_torus(p, wp.vec3(par[o], par[o + 1], par[o + 2]), wp.vec3(par[o + 3], par[o + 4], par[o + 5]),
                                 par[o + 6], par[o + 7])
            elif kind[i] == 5:
                di = SD.sd_revolve(p, int(par[o]), int(par[o + 1]), wp.vec3(par[o + 2], par[o + 3], par[o + 4]),
                                   wp.vec3(par[o + 5], par[o + 6], par[o + 7]), node_p, node_n, node_r, node_h)
            elif kind[i] == 7:
                di = SD.sd_psweep(p, int(par[o]), int(par[o + 1]), int(par[o + 2]), int(par[o + 3]), int(par[o + 4]),
                                  par[o + 5], par[o + 6], node_p, node_n, node_r, node_h)
            elif kind[i] == 8:
                di = SD.sd_roundbox(p, wp.vec3(par[o], par[o + 1], par[o + 2]),
                                    wp.vec3(par[o + 3], par[o + 4], par[o + 5]),
                                    wp.vec3(par[o + 6], par[o + 7], par[o + 8]),
                                    wp.vec3(par[o + 9], par[o + 10], par[o + 11]),
                                    wp.vec3(par[o + 12], par[o + 13], par[o + 14]), par[o + 15])
        if new_group == 1:
            gd = di
        else:
            gd = SD.combine(gd, di, op[i], kk[i])
    if first_group == 1:
        d = gd
    else:
        d = SD.combine(d, gd, int(par[g0 * 32 + 21]), par[g0 * 32 + 22])
    return d


@wp.func
def exact_normal(p: wp.vec3, h: float, n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32),
                 kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3),
                 node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4),
                 shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """the exact program's gradient at p (central differences, step h), unit; (0, 0, 0) where it vanishes"""
    ex = wp.vec3(h, 0.0, 0.0)
    ey = wp.vec3(0.0, h, 0.0)
    ez = wp.vec3(0.0, 0.0, h)
    g = wp.vec3(SD.program(p + ex, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
                - SD.program(p - ex, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri),
                SD.program(p + ey, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
                - SD.program(p - ey, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri),
                SD.program(p + ez, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
                - SD.program(p - ez, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri))
    if wp.length(g) < 1.0e-20:
        return wp.vec3(0.0, 0.0, 0.0)
    return wp.normalize(g)


@wp.func
def exact_on_line(q0: wp.vec3, d: wp.vec3, span: float, n_prim: int, kind: wp.array(dtype=wp.int32),
                  op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32),
                  node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
                  node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
                  tri: wp.array(dtype=wp.int32)):
    """C5c: the EXACT program's zero on the line q0 + t d, |t| <= span, nearest q0: fixed steps of span / 20 outward on
    both sides from q0, the first sign change, then 24 bisections. Returns (t, 1) or (0, 0)"""
    f0 = SD.program(q0, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    s0 = int(0)
    if f0 < 0.0:
        s0 = 1
    st = span / 20.0
    best_a = float(1.0e9)
    best_t = float(0.0)
    for side in range(2):
        sg = 1.0 - 2.0 * float(side)
        tp = float(0.0)
        for k in range(20):
            t = float(k + 1) * st
            if t >= best_a:
                break
            f = SD.program(q0 + d * (sg * t), n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                           tri)
            sb = int(0)
            if f < 0.0:
                sb = 1
            if sb != s0:
                lo = tp
                hi = t
                for it in range(24):
                    mid = 0.5 * (lo + hi)
                    fm = SD.program(q0 + d * (sg * mid), n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h,
                                    shells, thick, tri)
                    sm = int(0)
                    if fm < 0.0:
                        sm = 1
                    if sm == s0:
                        lo = mid
                    else:
                        hi = mid
                tc = 0.5 * (lo + hi)
                if tc < best_a:
                    best_a = tc
                    best_t = sg * tc
                break
            tp = t
    if best_a > 1.0e8:
        return wp.vec2(0.0, 0.0)
    return wp.vec2(best_t, 1.0)


@wp.func
def slot_pid(vol: wp.uint64, pid: wp.array(dtype=wp.int32), q: wp.vec3):
    """the piece id the slot high's voxel nearest q carries (-1: no voxel there)"""
    c = wp.volume_world_to_index(vol, q)
    idx = wp.volume_lookup_index(vol, int(wp.floor(c[0] + 0.5)), int(wp.floor(c[1] + 0.5)), int(wp.floor(c[2] + 0.5)))
    if idx < 0:
        return int(-1)
    return pid[idx]


@wp.func
def own_cross(p: wp.vec3, d: wp.vec3, f0: float, reach: float, vol: wp.uint64, val: wp.array(dtype=wp.float32),
              n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
              par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
              node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64),
              thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """the FIRST crossing of the field's zero along d from p (f0 = f(p)), at most `reach` along it: inside the solid the
    march of bake.exit_out (steps 0.8 |f|, at least 10 um: |f| bounds the distance to the boundary there), outside the
    sphere trace of bake.trace_in (0.8 f, at least 2 um); then a bisection. Returns (t, 1), or (0, 0): none"""
    ins = int(0)
    if f0 < 0.0:
        ins = 1
    t = float(0.0)
    t_prev = float(0.0)
    f = f0
    found = int(0)
    for it in range(256):
        sd = int(0)
        if f < 0.0:
            sd = 1
        if sd != ins:
            found = 1
            break
        t_prev = t
        if ins == 1:
            t = t + wp.max(-f * 0.8, 1.0e-5)
        else:
            t = t + wp.max(f * 0.8, 2.0e-6)
        if t > reach:
            break
        f = VX.hybrid(p + d * t, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    if found == 0:
        return wp.vec2(0.0, 0.0)
    lo = t_prev
    hi = t
    for it in range(22):
        mid = 0.5 * (lo + hi)
        fm = VX.hybrid(p + d * mid, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                       tri)
        sm = int(0)
        if fm < 0.0:
            sm = 1
        if sm == ins:
            lo = mid
        else:
            hi = mid
    return wp.vec2(hi, 1.0)


@wp.kernel
def k_bake_own(uv_mesh: wp.uint64, size: int, ss: int, cage: float, ao_r: float, cav_r: float, n_ao: int, n_cav: int,
               n_thk: int, thk_max: float, seed: int, h_grad: float, face_min: float, tilt0: float, tilt1: float,
               far_max: float, proj_iters: int, proj_tol: float, cov_eps: float, t0: int,
               lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3), ltan: wp.array(dtype=wp.vec4),
               lreg: wp.array(dtype=wp.int32), lisl: wp.array(dtype=wp.int32), lpid: wp.array(dtype=wp.int32),
               ldlt: wp.array(dtype=wp.vec3),
               o_isl: wp.array(dtype=wp.int32), o_flags: wp.array(dtype=wp.uint8), o_normal: wp.array(dtype=wp.vec4),
               o_shade: wp.array(dtype=wp.vec4), o_hgt: wp.array(dtype=wp.float32), o_pos: wp.array(dtype=wp.vec4),
               o_low: wp.array(dtype=wp.vec4), o_hn: wp.array(dtype=wp.vec4), o_reg: wp.array(dtype=wp.int32),
               o_miss: wp.array(dtype=wp.int32), o_part: wp.array(dtype=wp.int32), o_cnt: wp.array(dtype=wp.vec4i),
               pid_s: wp.array(dtype=wp.int32), pskip: wp.array(dtype=wp.int32), det: wp.array(dtype=wp.int32),
               refine_max: float, o_oth: wp.array(dtype=wp.float32), o_air: wp.array(dtype=wp.float32),
               vol_s: wp.uint64, val_s: wp.array(dtype=wp.float32), n_s: int, kind_s: wp.array(dtype=wp.int32),
               op_s: wp.array(dtype=wp.int32), kk_s: wp.array(dtype=wp.float32), par_s: wp.array(dtype=wp.float32),
               np_s: wp.array(dtype=wp.vec3), nn_s: wp.array(dtype=wp.vec3), nr_s: wp.array(dtype=wp.vec4),
               nh_s: wp.array(dtype=wp.vec4), sh_s: wp.array(dtype=wp.uint64), th_s: wp.array(dtype=wp.float32),
               tr_s: wp.array(dtype=wp.int32),
               vol_b: wp.uint64, val_b: wp.array(dtype=wp.float32), n_b: int, kind_b: wp.array(dtype=wp.int32),
               op_b: wp.array(dtype=wp.int32), kk_b: wp.array(dtype=wp.float32), par_b: wp.array(dtype=wp.float32),
               np_b: wp.array(dtype=wp.vec3), nn_b: wp.array(dtype=wp.vec3), nr_b: wp.array(dtype=wp.vec4),
               nh_b: wp.array(dtype=wp.vec4), sh_b: wp.array(dtype=wp.uint64), th_b: wp.array(dtype=wp.float32),
               tr_b: wp.array(dtype=wp.int32),
               n_x: int, kind_x: wp.array(dtype=wp.int32), op_x: wp.array(dtype=wp.int32),
               kk_x: wp.array(dtype=wp.float32), par_x: wp.array(dtype=wp.float32), np_x: wp.array(dtype=wp.vec3),
               nn_x: wp.array(dtype=wp.vec3), nr_x: wp.array(dtype=wp.vec4), nh_x: wp.array(dtype=wp.vec4),
               sh_x: wp.array(dtype=wp.uint64), th_x: wp.array(dtype=wp.float32), tr_x: wp.array(dtype=wp.int32),
               n_e: int, kind_e: wp.array(dtype=wp.int32), op_e: wp.array(dtype=wp.int32),
               kk_e: wp.array(dtype=wp.float32), par_e: wp.array(dtype=wp.float32), np_e: wp.array(dtype=wp.vec3),
               nn_e: wp.array(dtype=wp.vec3), nr_e: wp.array(dtype=wp.vec4), nh_e: wp.array(dtype=wp.vec4),
               sh_e: wp.array(dtype=wp.uint64), th_e: wp.array(dtype=wp.float32), tr_e: wp.array(dtype=wp.int32)):
    """C5c (the lead's decision 4): every accepted hit off a detail (det[texel] 0: no seam, head or set screw within
    reach) is moved onto its piece's EXACT surface (the slot layout's exact program, _e: along its search line within
    refine_max, its normal the exact gradient's), the voxel high's rounding and fillets out of the drivers; the COVER
    test reads the EXACT field of every other piece of the body at the hit (prog_others on the exploded program with
    the pieces split, _x; pskip[piece] its own primitive there), not the union voxel high (its fillet, deeper than
    COVER_EPS out to ~0.15 mm from a neighbour's wall, hid 532 visible texels and blackened the creases); the AO, cavity,
    thickness and curvature are the VISIBLE sub-samples' alone (a covered one's rays start inside its neighbour: AO 0),
    an AO ray's origin pushed out of the body high's voxel fillet into air; o_oth the least exact distance of a visible
    hit to another piece (the creases, for the gates).
    THE OWN-PIECE BAKE per texel, ss x ss sub-samples (bake.k_bake's frame, drivers and outputs). Per sub-sample: the
    low under it in the SLOT layout (lpos) and its piece (lpid); the search direction as k_bake turns it (the welded
    normal toward the triangle's past tilt0 -> tilt1); the TWO-SIDED search in the slot high: the first crossing of the
    piece's surface forward and backward along the ray, each within the cage, the NEARER one whose normal faces the
    triangle (bake.attempt()'s rule: through air dot >= face_min, an exit from inside dot >= 0; within NEAR_SURF of the
    low point dot >= 0) and whose voxels name this piece (else refused: FLAG_PART); again along the triangle's own normal
    where the search was turned; then the piece's closest point (bake.project_high, facing at face_min, at 0 within
    NEAR_SURF); else a miss. The hit's
    height and normal from the slot high; at the hit carried into the BODY layout (ldlt) the AO, cavity, thickness and
    curvature read in the body high (the whole of each rigid body: a neighbour still shades the corner it makes), and the
    sub-sample COVERED where the hit lies deeper than cov_eps inside it (the face is under another piece there). Each
    texel records one sub-sample's low point, hit (body layout), hit normal and piece: its centre's where that shows, else
    the first that shows, else the first"""
    tid = wp.tid() + t0
    x = tid % size
    y = tid // size
    state = wp.rand_init(seed, tid)
    acc_n = wp.vec3(0.0)
    acc_ao = float(0.0)
    acc_cav = float(0.0)
    acc_thk = float(0.0)
    acc_curv = float(0.0)
    acc_h = float(0.0)
    hits = int(0)
    low_hits = int(0)
    covered = int(0)
    flags = int(0)
    rec = int(0)
    inv = 1.0 / float(ss)
    mid_i = ss // 2
    vis = int(0)                                  # C5c: the visible sub-samples (their shade is the texel's)
    c_ao = float(0.0)                             # and the covered ones' (a texel with no visible one keeps theirs)
    c_cav = float(0.0)
    c_thk = float(0.0)
    c_curv = float(0.0)
    oth_min = float(1.0e9)
    air_min = float(1.0e9)                        # the least air a visible sub-sample's AO origin found (a gap: < AO_CLEAR)
    det_t = det[tid]
    for i in range(ss):
        for j in range(ss):
            s = wp.mesh_query_ray(uv_mesh, wp.vec3(float(x) + (float(i) + 0.5) * inv, float(y) + (float(j) + 0.5) * inv,
                                                   1.0), wp.vec3(0.0, 0.0, -1.0), 2.0)
            if not s.result:
                continue
            low_hits = low_hits + 1
            o_isl[tid] = lisl[s.face]
            c0 = 3 * s.face
            u = s.u
            v = s.v
            w = 1.0 - u - v
            p = lpos[c0] * u + lpos[c0 + 1] * v + lpos[c0 + 2] * w
            nn = wp.normalize(lnrm[c0] * u + lnrm[c0 + 1] * v + lnrm[c0 + 2] * w)
            ta = ltan[c0]
            tb = ltan[c0 + 1]
            tc = ltan[c0 + 2]
            t3 = wp.normalize(wp.vec3(ta[0], ta[1], ta[2]) * u + wp.vec3(tb[0], tb[1], tb[2]) * v
                              + wp.vec3(tc[0], tc[1], tc[2]) * w)
            ba = wp.cross(lnrm[c0], wp.vec3(ta[0], ta[1], ta[2])) * ta[3]
            bb = wp.cross(lnrm[c0 + 1], wp.vec3(tb[0], tb[1], tb[2])) * tb[3]
            bc = wp.cross(lnrm[c0 + 2], wp.vec3(tc[0], tc[1], tc[2])) * tc[3]
            b3 = wp.normalize(ba * u + bb * v + bc * w)
            fg = wp.cross(lpos[c0 + 1] - lpos[c0], lpos[c0 + 2] - lpos[c0])
            if wp.length(fg) > 1.0e-20:
                fg = wp.normalize(fg)
                if wp.dot(fg, lnrm[c0] + lnrm[c0 + 1] + lnrm[c0 + 2]) < 0.0:
                    fg = -fg
            else:
                fg = nn
            tw = wp.clamp((tilt0 - wp.dot(nn, fg)) / wp.max(tilt0 - tilt1, 1.0e-6), 0.0, 1.0)
            tw = tw * tw * (3.0 - 2.0 * tw)
            d0 = wp.normalize(nn * (1.0 - tw) + fg * tw)
            own = lpid[s.face]
            f0 = VX.hybrid(p, vol_s, val_s, n_s, kind_s, op_s, kk_s, par_s, np_s, nn_s, nr_s, nh_s, sh_s, th_s, tr_s)
            af = wp.abs(f0)
            # bake.attempt()'s rule: a crossing reached through air must face the triangle (face_min); an EXIT, the low
            # point inside its piece, is the wrong side only when it turns away from it (a voxel normal at a low face's
            # edge, against its piece's break, leans past face_min: the yaw lugs' band edges, the second full run)
            fmin = face_min
            if f0 < 0.0:
                fmin = 0.0
            ok = int(0)
            hp = p
            hn = nn
            best = float(1.0e9)
            src = int(0)
            seen = int(0)
            hdir = d0
            for att in range(2):
                sd = d0
                if att == 1:
                    sd = fg
                if ok == 0 and (att == 0 or wp.dot(d0, fg) < 0.999):
                    for side in range(2):
                        sg = 1.0 - 2.0 * float(side)
                        r = own_cross(p, sd * sg, f0, cage, vol_s, val_s, n_s, kind_s, op_s, kk_s, par_s, np_s, nn_s,
                                      nr_s, nh_s, sh_s, th_s, tr_s)
                        if r[1] > 0.5:
                            seen = 1
                            q = p + sd * (sg * r[0])
                            hq = VX.hnormal(q, h_grad, vol_s, val_s, n_s, kind_s, op_s, kk_s, par_s, np_s, nn_s, nr_s,
                                            nh_s, sh_s, th_s, tr_s)
                            thr = fmin
                            if r[0] < NEAR_SURF:
                                thr = 0.0
                            if wp.dot(hq, fg) < thr:
                                flags = flags | 1                     # FLAG_FACING: the piece's far side
                            elif slot_pid(vol_s, pid_s, q) != own:
                                flags = flags | 128                   # FLAG_PART
                            elif r[0] < best:
                                best = r[0]
                                hp = q
                                hn = hq
                                ok = 1
                                src = att
                                hdir = sd
            if ok == 1 and best > af + far_max:
                flags = flags | 2                                     # FLAG_FAR: kept, the nearest in the cage
            if ok == 0:
                # the piece's closest point, facing the triangle as a crossing must (dot >= face_min: at dot > 0, as
                # bake.py keeps it, a neck's end face buried in its disc took the neck's flank beside it, coplanar with
                # the disc's face and so not covered: the first full run's 432 texels)
                m = BK.project_high(p, proj_iters, h_grad, vol_s, val_s, n_s, kind_s, op_s, kk_s, par_s, np_s, nn_s,
                                    nr_s, nh_s, sh_s, th_s, tr_s)
                mf = m[2]
                cthr = face_min
                if wp.length(m[0] - p) < NEAR_SURF:
                    cthr = 0.0
                if wp.abs(mf[0]) <= proj_tol and wp.dot(m[1], fg) >= cthr and slot_pid(vol_s, pid_s, m[0]) == own:
                    ok = 1
                    hp = m[0]
                    hn = m[1]
                    src = 2
                    flags = flags | 8                                 # FLAG_CLOSEST
            if ok == 0:
                if seen == 0:
                    flags = flags | 16                                # FLAG_LIMIT: no surface within the cage
                continue
            if src == 1 or (src == 0 and tw > 0.0):
                flags = flags | 4                                     # FLAG_TRI
            # C5c: the hit onto its piece's EXACT surface (off the details): along its search line (a closest point's:
            # the exact gradient's) within refine_max, kept where the exact normal faces the triangle as the hit did
            if det_t == 0 and refine_max > 0.0:
                fe = SD.program(hp, n_e, kind_e, op_e, kk_e, par_e, np_e, nn_e, nr_e, nh_e, sh_e, th_e, tr_e)
                if wp.abs(fe) < refine_max:
                    ld = hdir
                    if src == 2:
                        ge = exact_normal(hp, 1.0e-5, n_e, kind_e, op_e, kk_e, par_e, np_e, nn_e, nr_e, nh_e, sh_e, th_e,
                                          tr_e)
                        if wp.length(ge) > 0.5:
                            ld = ge
                    rr_ = exact_on_line(hp, ld, refine_max, n_e, kind_e, op_e, kk_e, par_e, np_e, nn_e, nr_e, nh_e, sh_e,
                                        th_e, tr_e)
                    if rr_[1] > 0.5:
                        qe = hp + ld * rr_[0]
                        ne = exact_normal(qe, 1.0e-5, n_e, kind_e, op_e, kk_e, par_e, np_e, nn_e, nr_e, nh_e, sh_e, th_e,
                                          tr_e)
                        thr2 = fmin
                        if wp.length(qe - p) < NEAR_SURF:
                            thr2 = 0.0
                        if wp.length(ne) > 0.5 and wp.dot(ne, fg) >= thr2:
                            hp = qe
                            hn = ne
            hgt = wp.dot(hp - p, nn)
            dl = ldlt[s.face]
            hb = hp + dl
            cv = int(0)
            # C5c: COVERED by the exact field of the body's other pieces (not the union voxel high's fillets)
            fo = prog_others(hb, pskip[own], n_x, kind_x, op_x, kk_x, par_x, np_x, nn_x, nr_x, nh_x, sh_x, th_x, tr_x)
            if fo < -cov_eps:
                cv = 1
                covered = covered + 1
                flags = flags | 64                                    # FLAG_COVERED
            else:
                oth_min = wp.min(oth_min, fo)
            tn = wp.normalize(BK.frame_inv(t3, b3, nn, hn))
            acc_n = acc_n + tn
            acc_h = acc_h + hgt
            hits = hits + 1
            pr = int(1)
            if cv == 0:
                pr = 2
                if ss % 2 == 1 and i == mid_i and j == mid_i:
                    pr = 3
            if pr > rec:
                rec = pr
                o_pos[tid] = wp.vec4(hb[0], hb[1], hb[2], 1.0)
                o_low[tid] = wp.vec4(p[0] + dl[0], p[1] + dl[1], p[2] + dl[2], float(s.face) + 1.0)
                o_hn[tid] = wp.vec4(hn[0], hn[1], hn[2], float(cv))
                o_reg[tid] = lreg[s.face]
                o_part[tid] = slot_pid(vol_s, pid_s, hp)
            # AO and cavity: cosine rays sphere-traced in the body high, from an origin in air (C5c: at a contact crease
            # the voxel fillet holds hb + 0.2 mm hn, and an origin pushed just past the fillet's zero read every ray
            # occluded at its first step: the origin marches out along hn in AO_PUSH steps to AO_CLEAR of air at most
            # AO_REACH out, kept at its most open point, so it never crosses a running clearance into the next piece)
            org = hb + hn * 2.0e-4
            fz = VX.hybrid(org, vol_b, val_b, n_b, kind_b, op_b, kk_b, par_b, np_b, nn_b, nr_b, nh_b, sh_b, th_b, tr_b)
            if fz < AO_CLEAR:
                best_o = org
                best_f = fz
                q_o = org
                for it in range(int(AO_REACH / AO_PUSH)):
                    q_o = q_o + hn * AO_PUSH
                    fq = VX.hybrid(q_o, vol_b, val_b, n_b, kind_b, op_b, kk_b, par_b, np_b, nn_b, nr_b, nh_b, sh_b,
                                   th_b, tr_b)
                    if fq > best_f:
                        best_f = fq
                        best_o = q_o
                    if fq >= AO_CLEAR:
                        break
                    if fq < best_f - AO_PUSH:
                        break
                org = best_o
                fz = best_f
            if cv == 0:
                air_min = wp.min(air_min, fz)
            occ = int(0)
            for a in range(n_ao):
                d = BK.cos_dir(hn, wp.sample_unit_disk(state))
                tt = float(0.0)
                for it in range(40):
                    fd = VX.hybrid(org + d * tt, vol_b, val_b, n_b, kind_b, op_b, kk_b, par_b, np_b, nn_b, nr_b, nh_b,
                                   sh_b, th_b, tr_b)
                    if fd < 1.0e-5:
                        occ = occ + 1
                        break
                    tt = tt + wp.max(fd * 0.9, 1.0e-4)
                    if tt > ao_r:
                        break
            s_ao = 1.0 - float(occ) / float(wp.max(n_ao, 1))
            occ = int(0)
            for a in range(n_cav):
                d = BK.cos_dir(hn, wp.sample_unit_disk(state))
                tt = float(0.0)
                for it in range(24):
                    fd = VX.hybrid(org + d * tt, vol_b, val_b, n_b, kind_b, op_b, kk_b, par_b, np_b, nn_b, nr_b, nh_b,
                                   sh_b, th_b, tr_b)
                    if fd < 1.0e-5:
                        occ = occ + 1
                        break
                    tt = tt + wp.max(fd * 0.9, 5.0e-5)
                    if tt > cav_r:
                        break
            s_cav = 1.0 - float(occ) / float(wp.max(n_cav, 1))
            # thickness: inward rays (a cone about -hn) marched until they leave the body high
            th = float(0.0)
            for a in range(n_thk):
                dd = wp.sample_unit_disk(state) * 0.5
                d = BK.cos_dir(-hn, dd)
                tt = float(5.0e-4)
                for it in range(64):
                    fd = VX.hybrid(hb + d * tt, vol_b, val_b, n_b, kind_b, op_b, kk_b, par_b, np_b, nn_b, nr_b, nh_b,
                                   sh_b, th_b, tr_b)
                    if fd > 0.0:
                        break
                    tt = tt + wp.max(-fd * 0.9, 2.0e-4)
                    if tt > thk_max:
                        tt = thk_max
                        break
                th = th + tt
            s_thk = th / float(wp.max(n_thk, 1))
            # curvature: the body high's Laplacian at the hit (h = 4 voxels' worth of the gradient step, as k_bake)
            hc = h_grad * 4.0
            f0c = VX.hybrid(hb, vol_b, val_b, n_b, kind_b, op_b, kk_b, par_b, np_b, nn_b, nr_b, nh_b, sh_b, th_b, tr_b)
            lap = float(0.0)
            for a in range(3):
                e = wp.vec3(0.0)
                if a == 0:
                    e = wp.vec3(hc, 0.0, 0.0)
                elif a == 1:
                    e = wp.vec3(0.0, hc, 0.0)
                else:
                    e = wp.vec3(0.0, 0.0, hc)
                lap = lap + VX.hybrid(hb + e, vol_b, val_b, n_b, kind_b, op_b, kk_b, par_b, np_b, nn_b, nr_b, nh_b, sh_b,
                                      th_b, tr_b) + \
                    VX.hybrid(hb - e, vol_b, val_b, n_b, kind_b, op_b, kk_b, par_b, np_b, nn_b, nr_b, nh_b, sh_b, th_b,
                              tr_b) - 2.0 * f0c
            s_curv = lap / (hc * hc)
            if cv == 0:
                vis = vis + 1
                acc_ao = acc_ao + s_ao
                acc_cav = acc_cav + s_cav
                acc_thk = acc_thk + s_thk
                acc_curv = acc_curv + s_curv
            else:
                c_ao = c_ao + s_ao
                c_cav = c_cav + s_cav
                c_thk = c_thk + s_thk
                c_curv = c_curv + s_curv
    o_miss[tid] = low_hits - hits
    o_flags[tid] = wp.uint8(flags)
    o_cnt[tid] = wp.vec4i(low_hits, hits, covered, 0)
    o_oth[tid] = oth_min
    o_air[tid] = air_min
    if hits > 0:
        fh = float(hits)
        mn = wp.normalize(acc_n / fh)
        o_normal[tid] = wp.vec4(mn[0], mn[1], mn[2], fh / float(ss * ss))
        if vis > 0:
            fv = float(vis)
            o_shade[tid] = wp.vec4(acc_ao / fv, acc_cav / fv, acc_thk / fv, acc_curv / fv)
        else:
            o_shade[tid] = wp.vec4(c_ao / fh, c_cav / fh, c_thk / fh, c_curv / fh)
        o_hgt[tid] = acc_h / fh


def bake_own(A, G, S, pid_s, slots, Vb, size, ss=3, cage=4.0e-3, ao_r=6.0e-3, cav_r=1.0e-3, n_ao=24, n_cav=12, n_thk=2,
             thk_max=0.02, seed=7, band_rows=128, face_min=0.2, tilt=(15.0, 45.0), far_max=0.002, proj_iters=8,
             proj_tol=0.02e-3, cov_eps=COVER_EPS, exclude=None, region_names=None, spans=None, log=print, ex_prog=None,
             pskip=None, det=None, refine_max=REFINE_MAX):
    """the own-piece bake (k_bake_own) over the size^2 canvas, launched in bands of rows (spans: [(first texel, count)]
    in the kernel's order, tid = row * size + column with v = 0 at the bottom, to bake only those: the probes; the gate
    then reads the rest as empty); the outputs as bake.bake returns them (image
    order; 'gate_flags', the hidden texels by exclude(), bake.gate's tables), with 'low' (the recorded sub-sample's low
    point, body layout; w its triangle + 1), 'hnormal' (its hit's normal; w 1 where covered), 'part' (the piece its hit's
    voxels name),
    'low_hits' / 'hits' / 'cov_n' (sub-samples on the low, with a hit, covered); 'base', 'mat', 'gocc' zero (the bake.py
    channels a plain hard part leaves empty). The closest point converges (proj_iters 8, |f| <= 0.02 mm; bake.py's 3 and
    0.1 mm left a fallback hit up to 0.1 mm off its surface, beside a small lug's rounded edge)"""
    import time
    t0 = time.time()
    L = A['L']
    F = np.asarray(L['F'], np.int32)
    corner = F.ravel()
    luv = np.asarray(L['UV'], np.float64)[corner] * size
    uv_mesh = wp.Mesh(points=wp.array(np.column_stack([luv, np.zeros(len(luv))]).astype(np.float32), dtype=wp.vec3),
                      indices=wp.array(np.arange(len(luv), dtype=np.int32), dtype=wp.int32))
    isl = BK.islands(F, L['UV'])
    n = size * size
    outs = dict(island=wp.full(n, -1, dtype=wp.int32), gate_flags=wp.zeros(n, dtype=wp.uint8),
                normal=wp.zeros(n, dtype=wp.vec4), shade=wp.zeros(n, dtype=wp.vec4), height=wp.zeros(n, dtype=wp.float32),
                position=wp.zeros(n, dtype=wp.vec4), low=wp.zeros(n, dtype=wp.vec4), hnormal=wp.zeros(n, dtype=wp.vec4),
                region=wp.full(n, -1, dtype=wp.int32), miss=wp.zeros(n, dtype=wp.int32),
                part=wp.full(n, -1, dtype=wp.int32), cnt=wp.zeros(n, dtype=wp.vec4i))
    o_oth = wp.full(n, 1.0e9, dtype=wp.float32)
    o_air = wp.full(n, 1.0e9, dtype=wp.float32)
    head = [uv_mesh.id, size, ss, float(cage), float(ao_r), float(cav_r), n_ao, n_cav, n_thk, float(thk_max), seed,
            float(S.vs * 0.9), float(face_min), float(np.cos(np.radians(tilt[0]))), float(np.cos(np.radians(tilt[1]))),
            float(far_max), int(proj_iters), float(proj_tol), float(cov_eps)]
    # C5c: the exact programs (the body layout's with its pieces split: the cover test; the slot layout's: the hits'
    # refinement), each piece's own primitive there, the details' texels (kernel order: v = 0 at the bottom)
    assert ex_prog is not None and pskip is not None and det is not None, 'bake_own: C5c needs ex_prog, pskip, det'
    det_k = np.ascontiguousarray(np.asarray(det, bool)[::-1]).astype(np.int32).ravel()
    tail = [wp.array(np.asarray(slots['V'], np.float32)[corner], dtype=wp.vec3),
            wp.array(np.asarray(L['N'], np.float32)[corner], dtype=wp.vec3),
            wp.array(np.asarray(L['TAN'], np.float32)[corner], dtype=wp.vec4),
            wp.array(np.asarray(L['piece'], np.int32), dtype=wp.int32), wp.array(isl.astype(np.int32), dtype=wp.int32),
            wp.array(np.asarray(L['pid'], np.int32), dtype=wp.int32),
            wp.array(np.asarray(slots['dlt_tri'], np.float32), dtype=wp.vec3)] + \
        [outs[k] for k in ('island', 'gate_flags', 'normal', 'shade', 'height', 'position', 'low', 'hnormal', 'region',
                           'miss', 'part', 'cnt')] + \
        [pid_s, wp.array(np.asarray(pskip, np.int32), dtype=wp.int32), wp.array(det_k, dtype=wp.int32),
         float(refine_max), o_oth, o_air] + S._args() + G._args() + ex_prog._args() + slots['prog']._args()
    nrow = max(1, min(size, band_rows))
    bands = [(r0 * size, min(nrow, size - r0) * size) for r0 in range(0, size, nrow)] if spans is None else spans
    for bi, (s0, ns) in enumerate(bands):
        wp.launch(k_bake_own, dim=ns, inputs=head + [s0] + tail)
        wp.synchronize()
        if bi == 0:
            log(f'[bake_own] first band of {ns // size} rows: {time.time() - t0:.1f}s (incl. compile)')
    res = {}
    for k, a in outs.items():
        arr = a.numpy()
        arr = arr.reshape(size, size, -1) if arr.ndim > 1 else arr.reshape(size, size)
        res[k] = arr[::-1].copy()                    # rows top-down: image row 0 is v = 1
    res['oth'] = o_oth.numpy().reshape(size, size)[::-1].copy()
    res['air'] = o_air.numpy().reshape(size, size)[::-1].copy()
    res['detail'] = np.asarray(det, bool).copy()
    sh = res.pop('shade')
    res['ao'], res['cavity'], res['thickness'], res['curvature'] = (sh[..., c].copy() for c in range(4))
    cnt = res.pop('cnt')
    res['low_hits'], res['hits'], res['cov_n'] = cnt[..., 0].copy(), cnt[..., 1].copy(), cnt[..., 2].copy()
    res['base'] = np.zeros((size, size, 4), np.float32)
    res['mat'] = np.zeros((size, size), np.int32)
    res['gocc'] = np.zeros((size, size), np.int32)
    # texels whose low point lies BURIED in the high (exclude: the body high's program): left out as bake.bake does
    hidden = np.zeros((size, size), bool)
    if exclude is not None:
        ys, xs = np.nonzero(res['miss'] > 0)
        if len(ys):
            Vb32 = wp.array(np.asarray(Vb, np.float32)[corner], dtype=wp.vec3)
            lp = wp.zeros(len(ys), dtype=wp.vec4)
            wp.launch(BK.k_low_point, dim=len(ys), inputs=[uv_mesh.id, wp.array(xs.astype(np.int32), dtype=wp.int32),
                                                           wp.array((size - 1 - ys).astype(np.int32), dtype=wp.int32),
                                                           Vb32, lp])
            lp = lp.numpy()
            on = lp[:, 3] > 0.5
            hid = np.zeros(len(ys), bool)
            hid[on] = np.asarray(exclude(lp[on, :3]), bool)
            hidden[ys[hid], xs[hid]] = True
    res['hidden'] = hidden
    cov = res['normal'][..., 3] > 0
    inside = (cov | (res['miss'] > 0)) & ~hidden
    full_miss = (res['miss'] > 0) & ~cov & ~hidden
    part_miss = (res['miss'] > 0) & cov & ~hidden
    hgt = np.abs(res['height'][cov & ~hidden])
    hgt = hgt if hgt.size else np.zeros(1)
    log(f'[bake_own] {size}^2 x ss {ss}: {time.time() - t0:.1f}s, coverage {cov.mean() * 100:.1f} %; missed: '
        f'{full_miss.sum() / max(inside.sum(), 1) * 100:.3f} % of texels whole, {part_miss.sum() / max(inside.sum(), 1) * 100:.2f} '
        f'% partly (bar 0.5 %); low-to-high |d| p95 {np.percentile(hgt, 95) * 1000:.2f} mm, max {hgt.max() * 1000:.2f} mm '
        f'(bar p95 3 mm); sub-samples covered (inside another piece) {int(res["cov_n"].sum()):,} of '
        f'{int(res["hits"].sum()):,}; refused on another piece\'s voxels: texels {int(((res["gate_flags"] & FLAG_PART) > 0).sum())}')
    BK.gate(res, res.pop('island'), Vb, F, L['UV'], isl, size, L['piece'], cage, fix=True, region_names=region_names,
            log=log)
    return res


def bake_asset(A, voxel_size=0.15e-3, band=0.9e-3, ss=3, cage=4.0e-3, ao_r=6.0e-3, cav_r=1.0e-3, log=print, spans=None):
    """the GPU half: the exploded voxel high (the block-out sampled, the details' strokes applied: seams carved,
    counterbores carved, heads added, then the plan's smooth and relevel: C5a-2's, unchanged: the shade's and the gates'
    high), the OWN-PIECE search's high (C5a-3: every piece alone in its slot, the details on their pieces, the same plan
    of smooth and relevel; its voxels carry their piece's id), the own-piece bake onto the low (region = the island, so
    every gate reads per part). Returns the bake's dict (image order) and the fields"""
    E = exploded(A)
    # the details live in each group's own frame: into the exploded frame by the group's whole translation, its
    # joint's x AND its explode offset (as assembled_program places the group; the offset alone carved every
    # segment's seams and heads x[k] short of their shell, into air or a neighbouring part)
    det_all = A.get('det_all', A['det'])          # C5d: every body's details in the body high (the bake view's own)
    tr = {b_: np.array([A['chain']['x'][body_k(b_)], 0.0, 0.0]) + E['off'][b_] for b_ in det_all}
    plan = detail_plan(det_all, A['sizes'], tr)
    G = VX.SparseSDF(E['prog'], E['lo'], E['hi'], voxel=voxel_size, band=band, extra=plan.bounds(E['prog'], band),
                     log=log)
    plan.apply(G, log=log)
    Sx = slot_layout(A, E, voxel_size)
    S = VX.SparseSDF(Sx['prog'], Sx['lo'], Sx['hi'], voxel=voxel_size, band=band,
                     extra=Sx['plan'].bounds(Sx['prog'], band), log=log)
    Sx['plan'].apply(S, log=log)
    pid_s, far_v = slot_voxel_ids(S, Sx)
    log(f'[cyborg_limb] the own-piece search\'s high: {len(A["pieces"])} pieces in their slots ({SLOT_GAP * 1e3:.0f} mm '
        f'apart), {S.n:,} voxels, each named by its slot\'s piece (the farthest {far_v * 1e3:.2f} mm outside its slot\'s box)')
    names = {i: it['piece'] for i, it in enumerate(A['isl'])}
    # a texel whose low point lies BURIED inside the high (deeper than 0.25 mm: the faces each piece sinks into its
    # neighbour of the same group, the shells' ends inside their drums' cheeks, the necks' ends, the saddles' feet) is
    # never seen: the bake's exclude() leaves it out of the miss bar and the gate as it does a texel under a growth
    buried = lambda pts: E['prog'].eval(pts) < -0.25e-3
    # C5c: the exact programs the bake reads beside the voxel highs (the cover test, the hits' refinement) and the
    # texels a detail reaches (their hits stay the voxel high's: the details live only there)
    Ex, pskip = exact_split_program(A, E)
    det = detail_texels(A)
    log(f'[cyborg_limb] C5c: the exact cover program {len(Ex.kind)} primitives (the pieces split; every piece\'s own '
        f'found: {bool((pskip >= 0).all())}); texels a detail reaches (their hits stay the voxel high\'s): '
        f'{int(det.sum()):,}')
    res = bake_own(A, G, S, pid_s, Sx, E['V'], A['size'], ss=ss, cage=cage, ao_r=ao_r, cav_r=cav_r, n_thk=2,
                   thk_max=0.02, exclude=buried, region_names=names, spans=spans, log=log, ex_prog=Ex, pskip=pskip,
                   det=det)
    return res, dict(voxels=int(G.n), voxels_slot=int(S.n), strokes=int(sum(len(o['A']) for o in plan.ops)), E=E,
                     plan=plan, G=G, S=S, slots=Sx, pid_s=pid_s, Ex=Ex, pskip=pskip, det=det)


def exact_split_program(A, E):
    """C5c: the machine's EXACT program in the bake's body layout (exploded) with the drums' pieces split (cheek, foot
    ring, can or cap: the own-piece search's pieces), and per piece of A['pieces'] its own union primitive's index there
    (the cover test reads every other primitive). Returns (Program, (n_pieces,) int32)"""
    from . import sdf
    chain, des = A['chain'], A['des']
    off = E['off']
    prog = sdf.Program()
    span = {}
    for b_ in des['bodies']:
        n0 = len(prog.kind)
        group_program(chain, des, b_, prog, np.array([chain['x'][body_k(b_)], 0.0, 0.0]) + np.asarray(off[b_]),
                      bake=True, split=True)
        span[b_] = (n0, len(prog.kind))
    n0 = len(prog.kind)
    band_program(chain, des, prog, np.asarray(off['band']))
    span['band'] = (n0, len(prog.kind))
    n0 = len(prog.kind)
    hose_program(chain, des, prog, np.asarray(off['hose']))
    span['hose'] = (n0, len(prog.kind))
    out = np.full(len(A['pieces']), -1, np.int32)
    for i, (b_, p_) in enumerate(A['pieces']):
        a, b = span[b_]
        names = prog.names[a:b]
        hit = [a + j for j, nm in enumerate(names) if nm == p_ and prog.op[a + j] != sdf.SUBTRACT]
        if hit:
            out[i] = hit[0]
    return prog, out


def detail_texels(A, margin=0.6e-3):
    """C5c: the texels (image order) whose low point lies within reach of a detail (a seam's tube, a head or a set screw
    with its counterbore, plus `margin`): the details live only in the voxel high, so these texels' hits stay its own
    (no exact refinement) and the wrong-surface gate reads them against the voxel truth. Grown by one texel"""
    from scipy import ndimage
    from scipy.spatial import cKDTree
    pts, rr = [], []
    sz = A['sizes']
    for k_, g in A['det'].items():
        o = np.array([A['chain']['x'][body_k(k_)], 0.0, 0.0])
        for Ps in g['seams']:
            Pw = np.asarray(Ps, np.float64) + o
            for a_, b_ in zip(Pw[:-1], Pw[1:]):
                nn_ = max(2, int(np.ceil(np.linalg.norm(b_ - a_) / 0.1e-3)))
                for t_ in np.linspace(0.0, 1.0, nn_):
                    pts.append(a_ + t_ * (b_ - a_))
                    rr.append(0.5 * sz['seam_w'] + margin)
        for h in g['heads']:
            pts.append(np.asarray(h['p'], np.float64) + o)
            rr.append(0.5 * h['D'] + CB_RADIAL + margin)
    size = A['size']
    out = np.zeros((size, size), bool)
    if not pts:
        return out
    P, R = np.array(pts), np.array(rr)
    Lx = rasterise(A, A['L']['V'])
    ok = np.all(np.isfinite(Lx), axis=2)
    ys, xs = np.nonzero(ok)
    dd, ii = cKDTree(P).query(Lx[ys, xs], k=8)
    near = np.min(dd - R[ii], axis=1) < 0.0
    out[ys[near], xs[near]] = True
    return ndimage.binary_dilation(out, structure=np.ones((3, 3), bool))


def subset_program(prog, drop):
    """a copy of a Program without the primitives named in `drop`, and without any group left with no union member
    (a group's cuts with nothing to cut). The node arrays are shared: the kept primitives' parameters index them as
    before. Read-only use of sdf.Program's host lists"""
    from . import sdf
    gid = [int(p[20]) for p in prog.par]
    keep = [nm not in drop for nm in prog.names]
    solid = {g for g, kp, op in zip(gid, keep, prog.op) if kp and op != sdf.SUBTRACT}
    keep = [kp and g in solid for kp, g in zip(keep, gid)]
    P = sdf.Program()
    for name in ('kind', 'op', 'k', 'par', 'names'):
        setattr(P, name, [v for v, kp in zip(getattr(prog, name), keep) if kp])
    P.node_p, P.node_n, P.node_r, P.node_h = prog.node_p, prog.node_n, prog.node_r, prog.node_h
    P.shell_meshes, P.shell_thick, P.shell_tri = prog.shell_meshes, prog.shell_thick, prog.shell_tri
    P._next_gid = prog._next_gid
    return P


def prim_of_piece(piece, names):
    """the program primitive an island belongs to: the longest primitive name (a leading 'flange ' dropped) that the
    island's name equals or starts with before a space ('collar lug sides' -> 'collar lug', 'collar lip' -> 'flange
    collar', 'drum 9 aboral band1' -> 'drum 9 aboral')"""
    best, bl = None, -1
    for nm in set(names):
        s = nm[7:] if nm.startswith('flange ') else nm
        if (piece == s or piece.startswith(s + ' ')) and len(s) > bl:
            best, bl = nm, len(s)
    return best


def own_program(prog, prim):
    """C5a-3: one PIECE's Program: the union primitive `prim` of a body's program and the cuts of its group (a
    subset_program: positions as the body's)"""
    from . import sdf
    gid = [int(p[20]) for p in prog.par]
    i = prog.names.index(prim)
    keep = {prim} | {nm for nm, g, o_ in zip(prog.names, gid, prog.op) if g == gid[i] and o_ == sdf.SUBTRACT}
    return subset_program(prog, {nm for nm in prog.names if nm not in keep})


def island_pieces(isl, progs_piece, bodies):
    """C5a-3: every island's PIECE, the high it alone is baked from: (body, primitive) for a rigid part (the island's
    'prim' where knuckle_parts names one, else prim_of_piece over its body's split bake program), ('band', 'rubber
    band'), ('hose', 'hose'). Returns (the pieces: by body, then by the primitive's place in its body's program; the
    band and the hose last), each island's piece index"""
    keys = []
    for it in isl:
        rn = REGIONS[it['region']]
        if rn in ('band', 'hose'):
            keys.append((rn, 'rubber band' if rn == 'band' else 'hose'))
            continue
        names = progs_piece[it['body']].names
        p = it.get('prim') or prim_of_piece(it['piece'], names)
        assert p is not None and p in names, f'island {it["piece"]!r}: no primitive of {it["body"]} ({p!r})'
        keys.append((it['body'], p))
    rank = {b_: i for i, b_ in enumerate(list(bodies) + ['band', 'hose'])}
    at = lambda kp: progs_piece[kp[0]].names.index(kp[1]) if kp[0] in progs_piece else 0
    pieces = sorted(set(keys), key=lambda kp: (rank[kp[0]], at(kp)))
    pid = {kp: i for i, kp in enumerate(pieces)}
    return pieces, np.array([pid[kp] for kp in keys], np.int32)


def low_points(A, E):
    """per texel (image order) the exploded low point and the low's normal; an island's BORDER texels (centre outside
    its triangles, sub-samples inside) take their nearest interior texel's (within 1.5 texels, the same island: the
    pack keeps islands 3 texels apart), so a buried face's rim reads buried with it. Returns (points, normals,
    island raster)"""
    from scipy import ndimage
    isl_r, _ = island_raster(A)
    Lx = rasterise(A, E['V'])
    Ln = rasterise(A, A['L']['N'])
    valid = np.all(np.isfinite(Lx), axis=2) & np.all(np.isfinite(Ln), axis=2)
    d, (iy, ix) = ndimage.distance_transform_edt(~valid, return_indices=True)
    fill = ~valid & (isl_r >= 0) & (d <= 1.5) & (isl_r[iy, ix] == isl_r)
    Lx[fill] = Lx[iy[fill], ix[fill]]
    Ln[fill] = Ln[iy[fill], ix[fill]]
    return Lx, Ln, isl_r


def covered_texels(A, E, mask, depth=SAG):
    """the texels (of `mask`) whose low point lies inside ANOTHER piece of its rigid group: deeper than `depth` (the
    low's own sagitta: the neighbour's low may sit that far inside its high), or inside it and still inside it
    `depth` out along the low's normal (a sign test: a PSWEEP's distance is divided by its Lipschitz bound, so its
    depth under-reads, its sign does not). Covered by that neighbour, never seen, whatever the bake found there (A.7
    U3's "covered texels"). Each island's points against the exploded program without the island's own primitive.
    Returns a bool (size, size)"""
    size = A['size']
    out = np.zeros((size, size), bool)
    Lx, Ln, isl_r = low_points(A, E)
    names = E['prog'].names
    by_prim = {}
    for i, it in enumerate(A['isl']):
        if REGIONS[it['region']] in ('band', 'hose'):
            continue
        p = prim_of_piece(it['piece'], names)
        if p is not None:
            by_prim.setdefault(p, []).append(i)
    for p, ids in by_prim.items():
        m = np.isin(isl_r, ids) & mask
        ys, xs = np.nonzero(m)
        if not len(ys):
            continue
        Q = Lx[ys, xs]
        Nq = Ln[ys, xs]
        ok = np.all(np.isfinite(Q), axis=1) & np.all(np.isfinite(Nq), axis=1)
        if not ok.any():
            continue
        Nq = Nq[ok] / np.maximum(np.linalg.norm(Nq[ok], axis=1, keepdims=True), 1e-12)
        sub = subset_program(E['prog'], {p})
        d = sub.eval(Q[ok])
        d_out = sub.eval(Q[ok] + depth * Nq)
        hit = (d < -depth) | ((d < 0.0) & (d_out < 0.0))
        out[ys[ok][hit], xs[ok][hit]] = True
    return out


def hide_buried(A, res, E, log=print):
    """the texels whose low point is BURIED (inside the high, its search finding no surface within its reach: bake.py's
    FLAG_LIMIT) and the COVERED ones (C5a-3: every sub-sample's own-surface hit inside another piece, bake_own's cov_n)
    join res['hidden'], and the bake's gate tables are recomputed without them. The program's union is culled (a later
    primitive is skipped once a point is inside an earlier one: sdf.program), so its depth under-reads inside
    overlapping pieces and exclude()'s depth test misses some; the search's own failure does not. Returns the count
    added"""
    from . import bake as BK
    size = A['size']
    L = A['L']
    cov = res['normal'][..., 3] > 0
    full = (res['miss'] > 0) & ~cov & ~res['hidden']
    lim = (np.asarray(res['gate_flags'], np.int64) & BK.FLAG_LIMIT) > 0
    cand = full & lim
    ys, xs = np.nonzero(cand)
    added = 0
    if len(ys):
        Pl = low_points(A, E)[0][ys, xs]
        ok = np.all(np.isfinite(Pl), axis=1)
        inside = np.zeros(len(ys), bool)
        inside[ok] = E['prog'].eval(Pl[ok]) < 0.0
        res['hidden'][ys[inside], xs[inside]] = True
        added = int(inside.sum())
    isl_r, _ = island_raster(A)
    # the COVERED texels (C5a-3, by construction): every sub-sample's own-surface hit lies inside another piece (the
    # bake's cov_n against its hits): the face is under that piece there, never seen. (C5a-2 judged the low point by a
    # sign test along the low's normal: an island wound inward, a lug's top under its can, went the wrong way)
    cv = (res['hits'] > 0) & (res['cov_n'] >= res['hits']) & (isl_r >= 0) & ~res['hidden']
    old = covered_texels(A, E, (isl_r >= 0) & ~res['hidden'])
    # a texel with NO visible hit and a missed sub-sample (a face buried deeper than its piece's surface is in reach, a
    # neck's end inside its disc) falls back to its low point: inside another piece at all (C5a-2's test at a hair's
    # depth: such a texel has nothing to show), it is covered too. A texel with any visible hit is never hidden this way
    cand = (res['cov_n'] >= res['hits']) & (res['miss'] > 0) & (isl_r >= 0) & ~res['hidden'] & ~cv
    unseen = covered_texels(A, E, cand, depth=0.01e-3) & cand
    res['covered'] = cv | unseen
    res['hidden'] = res['hidden'] | cv | unseen
    added += int(cv.sum() + unseen.sum())
    log(f'[cyborg_limb]    covered (every sub-sample\'s own surface deeper than {COVER_EPS * 1e3:.3f} mm inside another '
        f'piece): {int(cv.sum()):,} texels more, and {int(unseen.sum()):,} with no visible hit and a miss whose low point '
        f'lies in another piece (C5a-2\'s low-point test alone would hide {int(old.sum()):,}: with the bake '
        f'{int((old & (cv | unseen)).sum()):,}, it alone {int((old & ~cv & ~unseen).sum()):,}, the bake alone '
        f'{int((cv & ~old).sum()):,})')
    isl_t = BK.islands(L['F'], L['UV'])
    # the JUNCTION band (the 2 texels bordering a buried region) is only reported (res['contact']): C5a-2's gate keeps it
    # IN (the lead's call 5; C5a's passed only with it left out). The buried faces are cut out of the low (clip_buried),
    # so little is left to bury
    from scipy import ndimage
    near = ndimage.binary_dilation(res['hidden'], structure=np.ones((3, 3), bool), iterations=2)
    res['contact'] = near & ~res['hidden'] & (isl_r >= 0)
    BK.gate(res, isl_r, E['V'], L['F'], L['UV'], isl_t, size, L['piece'], 4.0e-3,
            region_names={i: it['piece'] for i, it in enumerate(A['isl'])}, log=log)
    return added


def island_raster(A):
    """the island id at every texel centre a low triangle covers (image order, -1 none) and the texels two islands
    claim (the UV overlap)"""
    from PIL import Image, ImageDraw
    size = A['size']
    if A.get('_raster') is not None:
        return A['_raster'][0].copy(), A['_raster'][1].copy()
    ids = np.full((size, size), -1, np.int64)
    claim = np.zeros((size, size), np.int32)
    for i, it in enumerate(A['isl']):
        uv = it['UVp']
        px_ = np.column_stack([uv[:, 0] * size, (1.0 - uv[:, 1]) * size])
        x0, y0 = np.floor(px_.min(0)).astype(int) - 1
        x1, y1 = np.ceil(px_.max(0)).astype(int) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size), min(y1, size)
        im = Image.new('L', (x1 - x0, y1 - y0), 0)
        dr = ImageDraw.Draw(im)
        for f in it['F']:
            dr.polygon([(float(px_[j, 0] - x0), float(px_[j, 1] - y0)) for j in f], fill=1)
        m = np.asarray(im, bool)
        claim[y0:y1, x0:x1] += m
        ids[y0:y1, x0:x1][m] = i
    A['_raster'] = (ids, claim)
    return ids.copy(), claim.copy()


def part_of_island(A):
    """each island's PART for the per-part gates: its rigid group, or the band, or the hose"""
    out = []
    for it in A['isl']:
        rn = REGIONS[it['region']]
        out.append(rn if rn in ('band', 'hose') else it['body'])
    return out


def part_gates(A, res, E, border=2, bar=0.05, junction=True):
    """the hard-part bake gates (A.7 U3: the robot body's): per part, the shares of its covered texels that are
    MISSED (no sub-sample found the high), WRONG-PART (C5a-3: the part its hit's voxels name in the own-piece search's
    high is another; drivers without part ids: the hit outside its part's box in the exploded layout, 'wrong_box' kept
    beside it), BACK-FACING (the baked normal faces away from the low: tangent z < 0) and UV OVERLAP (a texel two
    islands claim), each at most `bar` %, a `border`-texel band at every island's edge left out. Returns rows"""
    from scipy import ndimage
    size = A['size']
    # the low's own coverage (a texel the bake missed whole carries no region in its output): the islands rasterised
    isl, claim = island_raster(A)
    cov = res['normal'][..., 3] > 0
    hidden = np.asarray(res.get('hidden', np.zeros((size, size), bool)), bool)
    inside = (isl >= 0)
    mx = ndimage.maximum_filter(isl, size=2 * border + 1, mode='constant', cval=-1)
    mn = ndimage.minimum_filter(isl, size=2 * border + 1, mode='constant', cval=-1)
    edge = inside & ((mx != isl) | (mn != isl))
    core = inside & ~edge & ~hidden
    if junction and res.get('contact') is not None:
        core &= ~np.asarray(res['contact'], bool)
    over = claim > 1
    parts = part_of_island(A)
    # the parts' boxes in the exploded layout (the hit's owner by position)
    boxes = {}
    offv = E['offv']
    n0 = 0
    for it, p in zip(A['isl'], parts):
        V = it['V'] + offv[n0:n0 + len(it['V'])]
        n0 += len(it['V'])
        lo, hi = V.min(0) - 0.003, V.max(0) + 0.003
        if p in boxes:
            boxes[p] = (np.minimum(boxes[p][0], lo), np.maximum(boxes[p][1], hi))
        else:
            boxes[p] = (lo, hi)
    pos = res['position'][..., :3]
    rows = []
    part_tex = np.full((size, size), -1, np.int64)
    pid = {p: i for i, p in enumerate(boxes)}
    isl_part = np.array([pid[p] for p in parts])
    part_tex[inside] = isl_part[isl[inside]]
    owner = np.full((size, size), -1, np.int64)
    for p, (lo, hi) in boxes.items():
        m = cov & np.all((pos >= lo) & (pos <= hi), axis=-1)
        owner[m & (owner < 0)] = pid[p]
    # C5a-3: the hit's part read from the PART IDS IN THE VOXEL HIGH (bake_own's 'part': the piece its hit's voxels
    # name, that piece's body / the band / the hose); the boxes stay as a second reading (C5a-2's: a hit past the box of
    # its part's CLIPPED low read 'wrong' on its own trunnion's top, arm_17_cross)
    by_id = res.get('part') is not None and 'pieces' in A
    if by_id:
        pp = np.array([pid.get(kp[0], -1) for kp in A['pieces']])
        hp_ = np.asarray(res['part'], np.int64)
        hit_part = np.where(hp_ >= 0, pp[np.clip(hp_, 0, len(pp) - 1)], -1)
    miss = (res['miss'] > 0) & ~cov
    back = cov & (res['normal'][..., 2] < 0.0)
    for p, i in pid.items():
        m = core & (part_tex == i)
        n = int(m.sum())
        if not n:
            continue
        wrong_box = float((m & cov & (owner != i)).sum()) / n * 100.0
        r = dict(part=p, texels=n, missed=float((miss & m).sum()) / n * 100.0,
                 wrong=float((m & cov & (hit_part != i)).sum()) / n * 100.0 if by_id else wrong_box,
                 wrong_box=wrong_box, back=float((back & m).sum()) / n * 100.0,
                 overlap=float((over & m).sum()) / n * 100.0)
        r['ok'] = all(r[q] <= bar for q in ('missed', 'wrong', 'back', 'overlap'))
        rows.append(r)
    return rows, dict(border_texels=int(edge.sum()), overlap_texels=int((over & core).sum()), wrong_by='part id' if by_id
                      else 'box')


# ---- C5a-3: THE WRONG-SURFACE GATE (the lead's call 2)
WS_TOL_D = 0.10e-3          # wrong: the hit stands more than this off the true surface on its line (two thirds of a voxel;
                            # C5a-2's slid hits stood 0.3-3.8 mm out)
WS_TOL_A = 30.0             # deg, or its normal more than this off the true surface's there
WS_TOL_D_STRICT = 0.15e-3   # the whole-high reading (a diagnostic): beyond the high's nearest surface by one voxel
WS_STEP = 10.0e-6           # the truth's fixed steps along the line (then a bisection)


@wp.kernel
def k_line_cross(pts: wp.array(dtype=wp.vec3), dirs: wp.array(dtype=wp.vec3), lnr: wp.array(dtype=wp.vec3),
                 reach: float, step: float, face_min: float, h_grad: float, o_q: wp.array(dtype=wp.vec3),
                 o_n: wp.array(dtype=wp.vec3), o_t: wp.array(dtype=wp.vec2), vol: wp.uint64,
                 val: wp.array(dtype=wp.float32), n_prim: int, kind: wp.array(dtype=wp.int32),
                 op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32),
                 node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
                 node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
                 tri: wp.array(dtype=wp.int32)):
    """THE TRUTH on a line, independent of the bake's search: from each point along +-dir in FIXED steps (no sphere
    trace) to `reach`, the nearer of the two sides' first zero crossing (a bisection) whose normal faces lnr, the low
    TRIANGLE's normal (bake.attempt()'s rule: reached through air dot >= face_min, an exit from inside dot >= 0; within
    NEAR_SURF of the point dot >= 0, as bake_own); o_t (t, 1 found / 0 none)"""
    i = wp.tid()
    p = pts[i]
    d = dirs[i]
    f0 = VX.hybrid(p, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    thr = face_min
    if f0 < 0.0:
        thr = 0.0
    best = float(1.0e9)
    bq = p
    bn = d
    n_steps = int(reach / step) + 1
    for side in range(2):
        sg = 1.0 - 2.0 * float(side)
        fp = f0
        tp = float(0.0)
        for k in range(n_steps):
            t = float(k + 1) * step
            if t >= best:
                break
            f = VX.hybrid(p + d * (sg * t), vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                          thick, tri)
            sa = int(0)
            sb = int(0)
            if fp < 0.0:
                sa = 1
            if f < 0.0:
                sb = 1
            if sa != sb:
                lo = tp
                hi = t
                for it in range(24):
                    mid = 0.5 * (lo + hi)
                    fm = VX.hybrid(p + d * (sg * mid), vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r,
                                   node_h, shells, thick, tri)
                    sm = int(0)
                    if fm < 0.0:
                        sm = 1
                    if sm == sa:
                        lo = mid
                    else:
                        hi = mid
                tc = 0.5 * (lo + hi)
                q = p + d * (sg * tc)
                n = VX.hnormal(q, h_grad, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                               thick, tri)
                th_c = thr
                if tc < NEAR_SURF:
                    th_c = 0.0                          # the surface the point lies on (bake_own's NEAR_SURF)
                if wp.dot(n, lnr[i]) >= th_c:
                    best = tc
                    bq = q
                    bn = n
                    break
            fp = f
            tp = t
    o_q[i] = bq
    o_n[i] = bn
    if best < 1.0e8:
        o_t[i] = wp.vec2(best, 1.0)
    else:
        o_t[i] = wp.vec2(0.0, 0.0)


@wp.kernel
def k_line_cross_exact(pts: wp.array(dtype=wp.vec3), dirs: wp.array(dtype=wp.vec3), lnr: wp.array(dtype=wp.vec3),
                       reach: float, step: float, face_min: float, h_n: float, o_q: wp.array(dtype=wp.vec3),
                       o_n: wp.array(dtype=wp.vec3), o_t: wp.array(dtype=wp.vec2), n_prim: int,
                       kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
                       par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
                       node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4),
                       shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
                       tri: wp.array(dtype=wp.int32)):
    """C5c (the lead's decision 4): k_line_cross on the EXACT program (the slot layout's: every piece alone, no
    voxels), its normal the exact gradient's: the wrong-surface gate's truth off the details"""
    i = wp.tid()
    p = pts[i]
    d = dirs[i]
    f0 = SD.program(p, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    thr = face_min
    if f0 < 0.0:
        thr = 0.0
    best = float(1.0e9)
    bq = p
    bn = d
    n_steps = int(reach / step) + 1
    for side in range(2):
        sg = 1.0 - 2.0 * float(side)
        fp = f0
        tp = float(0.0)
        for k in range(n_steps):
            t = float(k + 1) * step
            if t >= best:
                break
            f = SD.program(p + d * (sg * t), n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                           tri)
            sa = int(0)
            sb = int(0)
            if fp < 0.0:
                sa = 1
            if f < 0.0:
                sb = 1
            if sa != sb:
                lo = tp
                hi = t
                for it in range(26):
                    mid = 0.5 * (lo + hi)
                    fm = SD.program(p + d * (sg * mid), n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h,
                                    shells, thick, tri)
                    sm = int(0)
                    if fm < 0.0:
                        sm = 1
                    if sm == sa:
                        lo = mid
                    else:
                        hi = mid
                tc = 0.5 * (lo + hi)
                q = p + d * (sg * tc)
                n = exact_normal(q, h_n, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
                th_c = thr
                if tc < NEAR_SURF:
                    th_c = 0.0
                if wp.dot(n, lnr[i]) >= th_c:
                    best = tc
                    bq = q
                    bn = n
                    break
            fp = f
            tp = t
    o_q[i] = bq
    o_n[i] = bn
    if best < 1.0e8:
        o_t[i] = wp.vec2(best, 1.0)
    else:
        o_t[i] = wp.vec2(0.0, 0.0)


@wp.kernel
def k_near_surface(pts: wp.array(dtype=wp.vec3), iters: int, h_grad: float, o_q: wp.array(dtype=wp.vec3),
                   o_n: wp.array(dtype=wp.vec3), o_f: wp.array(dtype=wp.vec2), vol: wp.uint64,
                   val: wp.array(dtype=wp.float32), n_prim: int, kind: wp.array(dtype=wp.int32),
                   op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32),
                   node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
                   node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
                   tri: wp.array(dtype=wp.int32)):
    """per point: the field there and its CLOSEST POINT on the field's zero (bake.project_high: p -= f grad f), the
    normal there; o_f (f(p), f at the closest point)"""
    i = wp.tid()
    p = pts[i]
    f0 = VX.hybrid(p, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    m = BK.project_high(p, iters, h_grad, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                        thick, tri)
    mf = m[2]
    o_q[i] = m[0]
    o_n[i] = m[1]
    o_f[i] = wp.vec2(f0, mf[0])


@wp.kernel
def k_field_normal(pts: wp.array(dtype=wp.vec3), h_grad: float, o_n: wp.array(dtype=wp.vec3), vol: wp.uint64,
                   val: wp.array(dtype=wp.float32), n_prim: int, kind: wp.array(dtype=wp.int32),
                   op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32),
                   node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
                   node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
                   tri: wp.array(dtype=wp.int32)):
    """the field's normal at each point as the bake reads it (voxel.hnormal)"""
    i = wp.tid()
    o_n[i] = VX.hnormal(pts[i], h_grad, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                        thick, tri)


@wp.kernel
def k_first_sub(uv_mesh: wp.uint64, xs: wp.array(dtype=wp.int32), ys: wp.array(dtype=wp.int32), ss: int,
                lpos: wp.array(dtype=wp.vec3), out: wp.array(dtype=wp.vec4)):
    """per texel (kernel rows): the low point under its FIRST sub-sample on the low, in bake.k_bake's order (C5a-2's
    drivers kept that sub-sample's hit); w its triangle + 1 (0: none)"""
    i = wp.tid()
    inv = 1.0 / float(ss)
    for a in range(ss):
        for b in range(ss):
            s = wp.mesh_query_ray(uv_mesh, wp.vec3(float(xs[i]) + (float(a) + 0.5) * inv,
                                                   float(ys[i]) + (float(b) + 0.5) * inv, 1.0),
                                  wp.vec3(0.0, 0.0, -1.0), 2.0)
            if s.result:
                c0 = 3 * s.face
                p = lpos[c0] * s.u + lpos[c0 + 1] * s.v + lpos[c0 + 2] * (1.0 - s.u - s.v)
                out[i] = wp.vec4(p[0], p[1], p[2], float(s.face) + 1.0)
                return


def _launch_pts(kernel, field, pts, extra_in, outs):
    """a per-point kernel over a field (its args last), in chunks of 4M points"""
    n = len(pts)
    res = [np.zeros((n,) + o_[1], o_[0]) for o_ in outs]
    for s in range(0, n, 4_000_000):
        P = wp.array(np.asarray(pts[s:s + 4_000_000], np.float32), dtype=wp.vec3)
        dev = [wp.zeros(len(P), dtype=o_[2]) for o_ in outs]
        wp.launch(kernel, dim=len(P), inputs=[P] + extra_in + dev + field._args())
        for r_, d_ in zip(res, dev):
            r_[s:s + len(P)] = d_.numpy().reshape((len(P),) + r_.shape[1:])
    return res


def wrong_surface(A, res, G, S, slots, E, tol_d=WS_TOL_D, tol_a=WS_TOL_A, legacy=False, region=None):
    """THE WRONG-SURFACE GATE (C5a-3, the lead's call 2). Per covered texel its RECORDED sub-sample: its low point p, its
    bake hit h, its hit's normal (bake_own's 'low', 'position', 'hnormal'; legacy: C5a-2's drivers, which kept the first
    sub-sample's hit and no normal: p under that sub-sample, the normal the body high's at h, as its bake read it).
    THE TRUTH, from the SDF, independent of the bake's search: the NEAREST surface of the texel's own piece's high (the slot
    high: the high the lead's call 1 bakes it from) on the line through p and h, either side of p within the cage, whose
    normal faces the recorded sub-sample's low triangle as the bake requires (through air at face_min, an exit at 0)
    (fixed 10 um steps and a bisection: k_line_cross). WRONG where the hit stands more than tol_d
    off it (the search ran past the nearest surface, or the hit is another piece's), its normal is more than tol_a off
    the truth's there, or the piece has no such surface on that line. (The whole high's nearest surface itself, |f(p)| of
    the body high and its normal at its nearest point, cannot be the bar: a step the low leaves to the bake, a drum's can
    foot ring, has its WALL nearest the texels under its rim while their rays rightly meet its top; it is reported
    beside, 'whole_*'.) Counted per part over part_gates' core (the islands' 2-texel border and the hidden texels out),
    in its junction band (res['contact']) and in the border band; region = (hidden, contact) counts over those in place
    of res's own. Returns a dict"""
    from scipy import ndimage
    size = A['size']
    L = A['L']
    isl_r, _ = island_raster(A)
    cov = res['normal'][..., 3] > 0
    hidden, contact = (res['hidden'], res['contact']) if region is None else region
    hidden, contact = np.asarray(hidden, bool), np.asarray(contact, bool)
    inside = isl_r >= 0
    mx = ndimage.maximum_filter(isl_r, size=5, mode='constant', cval=-1)
    mn = ndimage.minimum_filter(isl_r, size=5, mode='constant', cval=-1)
    edge = inside & ((mx != isl_r) | (mn != isl_r))
    core = inside & ~edge & ~hidden
    bord = inside & edge & ~hidden
    reg = np.asarray(res['region'], np.int64)
    ys, xs = np.nonzero(cov & (core | bord) & (reg >= 0))
    reg = reg[ys, xs]
    h = np.asarray(res['position'], np.float64)[ys, xs, :3]
    if legacy:
        F = np.asarray(L['F'], np.int32)
        corner = F.ravel()
        luv = np.asarray(L['UV'], np.float64)[corner] * size
        uv_mesh = wp.Mesh(points=wp.array(np.column_stack([luv, np.zeros(len(luv))]).astype(np.float32),
                                          dtype=wp.vec3), indices=wp.array(np.arange(len(luv), dtype=np.int32),
                                                                           dtype=wp.int32))
        lp = wp.zeros(len(ys), dtype=wp.vec4)
        wp.launch(k_first_sub, dim=len(ys), inputs=[uv_mesh.id, wp.array(xs.astype(np.int32), dtype=wp.int32),
                                                    wp.array((size - 1 - ys).astype(np.int32), dtype=wp.int32), 3,
                                                    wp.array(np.asarray(E['V'], np.float32)[corner], dtype=wp.vec3), lp])
        lp = lp.numpy()
        p = lp[:, :3].astype(np.float64)
        face = np.rint(lp[:, 3]).astype(np.int64) - 1
        hn = _launch_pts(k_field_normal, G, h, [float(G.vs * 0.9)], [(np.float32, (3,), wp.vec3)])[0].astype(np.float64)
    else:
        p = np.asarray(res['low'], np.float64)[ys, xs, :3]
        face = np.rint(np.asarray(res['low'], np.float64)[ys, xs, 3]).astype(np.int64) - 1
        hn = np.asarray(res['hnormal'], np.float64)[ys, xs, :3]
    hn /= np.maximum(np.linalg.norm(hn, axis=1, keepdims=True), 1e-12)
    ang = lambda a, b: np.degrees(np.arccos(np.clip((a * b).sum(1), -1.0, 1.0)))
    # the facing test's reference: the recorded sub-sample's low TRIANGLE, its normal turned to its corners' normals'
    # side (as the bake reads it; the texel's rasterised normal can be its neighbour face's across a box strip's edge)
    V, Ft, Nv = np.asarray(L['V'], np.float64), np.asarray(L['F'], np.int64), np.asarray(L['N'], np.float64)
    fgt = np.cross(V[Ft[:, 1]] - V[Ft[:, 0]], V[Ft[:, 2]] - V[Ft[:, 0]])
    fgt /= np.maximum(np.linalg.norm(fgt, axis=1, keepdims=True), 1e-20)
    fgt *= np.where((fgt * Nv[Ft].sum(1)).sum(1) < 0.0, -1.0, 1.0)[:, None]
    ln = np.where((face >= 0)[:, None], fgt[np.clip(face, 0, len(Ft) - 1)], hn)
    # 1. THE GATE: the truth on the line through p and h in the own piece's high. C5c (the lead's decision 4): the
    # EXACT program's (the slot layout's, every piece alone) off the details; a texel a detail reaches (a seam, a head,
    # a set screw: they live only in the voxel high) keeps the slot voxel high's truth
    dl = slots['dlt_isl'][reg]
    p_s, h_s = p - dl, h - dl
    v = h_s - p_s
    nv = np.linalg.norm(v, axis=1, keepdims=True)
    dirs = np.where(nv > 1.0e-7, v / np.maximum(nv, 1e-12), ln)
    n = len(p_s)
    det_m = res.get('detail')
    det_m = np.asarray(det_m, bool) if det_m is not None and np.shape(det_m) == (size, size) else detail_texels(A)
    det_t = det_m[ys, xs]
    q, nq, tt = np.zeros((n, 3)), np.zeros((n, 3)), np.zeros((n, 2), np.float32)
    for sel, kern, args, h_ in ((~det_t, k_line_cross_exact, slots['prog']._args(), 1.0e-5),
                                (det_t, k_line_cross, S._args(), float(S.vs * 0.9))):
        m_ = int(sel.sum())
        if not m_:
            continue
        o_q, o_n, o_t = wp.zeros(m_, dtype=wp.vec3), wp.zeros(m_, dtype=wp.vec3), wp.zeros(m_, dtype=wp.vec2)
        wp.launch(kern, dim=m_, inputs=[wp.array(p_s[sel].astype(np.float32), dtype=wp.vec3),
                                        wp.array(dirs[sel].astype(np.float32), dtype=wp.vec3),
                                        wp.array(ln[sel].astype(np.float32), dtype=wp.vec3), 4.0e-3, WS_STEP, 0.2,
                                        h_, o_q, o_n, o_t] + args)
        q[sel], nq[sel], tt[sel] = o_q.numpy(), o_n.numpy(), o_t.numpy()
    found = tt[:, 1] > 0.5
    nq /= np.maximum(np.linalg.norm(nq, axis=1, keepdims=True), 1e-12)
    e_l = np.where(found, np.linalg.norm(h_s - q, axis=1), np.inf)
    e_n = np.where(found, ang(hn, nq), 180.0)
    bad_l, bad_n = e_l > tol_d, e_n > tol_a
    bad = bad_l | bad_n
    # 2. the whole high's nearest surface (a diagnostic): |h - p| - |f(p)| of the body high, its normal at its nearest point
    fG = G.eval(p).astype(np.float64)
    e_d = np.linalg.norm(h - p, axis=1) - np.abs(fG)
    _, nG, _ = _launch_pts(k_near_surface, G, p, [6, float(G.vs * 0.9)],
                           [(np.float32, (3,), wp.vec3), (np.float32, (3,), wp.vec3), (np.float32, (2,), wp.vec2)])
    nG = nG.astype(np.float64)
    nG /= np.maximum(np.linalg.norm(nG, axis=1, keepdims=True), 1e-12)
    e_g = ang(hn, nG)
    whole = (e_d > WS_TOL_D_STRICT) | (e_g > tol_a)
    in_core, in_jun, in_bord = core[ys, xs], (core & contact)[ys, xs], bord[ys, xs]
    parts = part_of_island(A)
    pt = np.array([str(parts[i]) for i in reg])
    rows = []
    for pp in dict.fromkeys(str(x_) for x_ in parts):
        m = in_core & (pt == pp)
        if m.any():
            rows.append(dict(part=pp, texels=int(m.sum()), wrong=int((bad & m).sum()), far=int((bad_l & m).sum()),
                             tilted=int((bad_n & m).sum()), junction=int((bad & m & in_jun).sum()),
                             whole=int((whole & m).sum())))
    pick = lambda score, m_: [dict(x=int(xs[k]), y=int(ys[k]), piece=A['isl'][reg[k]]['piece'],
                                   off_mm=float(min(e_l[k], 99.0) * 1e3), normal_deg=float(e_n[k]),
                                   hit_mm=float(np.linalg.norm(h[k] - p[k]) * 1e3), beyond_mm=float(e_d[k] * 1e3),
                                   whole_deg=float(e_g[k])) for k in np.argsort(-score)[:12] if m_[k]]
    chk = in_core | in_bord
    q_ = lambda a, m: [float(np.percentile(a[m], 50)), float(np.percentile(a[m], 99)), float(a[m].max())] if m.any() \
        else [0.0] * 3
    e_lf = np.where(np.isfinite(e_l), e_l, 99.0)
    return dict(tol_d_mm=tol_d * 1e3, tol_a_deg=tol_a, legacy=bool(legacy), texels=int(chk.sum()),
                truth='exact program off the details, the slot voxel high within a detail\'s reach',
                core_detail=int((in_core & det_t).sum()), core_detail_wrong=int((bad & in_core & det_t).sum()),
                junction_detail_wrong=int((bad & in_jun & det_t).sum()),
                core=int(in_core.sum()), core_wrong=int((bad & in_core).sum()), core_far=int((bad_l & in_core).sum()),
                core_tilted=int((bad_n & in_core).sum()), core_none=int((~found & in_core).sum()),
                junction=int(in_jun.sum()), junction_wrong=int((bad & in_jun).sum()), border=int(in_bord.sum()),
                border_wrong=int((bad & in_bord).sum()),
                hit_over_1mm_core=int(((np.linalg.norm(h - p, axis=1) > 1e-3) & in_core).sum()),
                off_mm=[v_ * 1e3 for v_ in q_(e_lf, chk)], normal_deg=q_(e_n, chk),
                whole_tol_d_mm=WS_TOL_D_STRICT * 1e3, whole_core=int((whole & in_core).sum()),
                whole_junction=int((whole & in_jun).sum()), whole_border=int((whole & in_bord).sum()),
                whole_beyond_mm=[v_ * 1e3 for v_ in q_(e_d, chk)], whole_deg=q_(e_g, chk), rows=rows,
                worst=pick(e_lf / tol_d + e_n / tol_a, np.ones(len(e_l), bool)),
                worst_whole=pick((e_d / WS_TOL_D_STRICT + e_g / tol_a) * (~bad), whole & ~bad),
                ys=ys, xs=xs, bad=bad, whole=whole, e_l=e_lf, e_n=e_n, e_d=e_d, e_g=e_g)


# ============================================================================================ the material pass
# the finishes per region (forge/cyborg.py CYBORG_ROWS through row_values: the house white paint wearing to titanium,
# black oxide (the body's black anodised housings: a dark dielectric film, metal 0, A.9 decision 1) wearing to bare
# steel, bare titanium, bare steel, the house rubber (A.9 decision 2)); the bright machined rings and mouths the robot
# body's ("black anodized joint housings with bright machined rings", kit_body §2.6)
FINISH = dict(shell='paint', shell_end='paint', drum='oxide', can='oxide', cap='titanium', tongue='titanium',
              clamp='oxide', actuator='oxide', rod='steel', boss='titanium', collar='oxide', collar_end='oxide',
              screw='oxide', fitting='titanium', roll='rubber', band='rubber', hose='rubber',
              # C5a-2's cardans: black-oxide yokes, the roll ring's disc and the crank; a titanium cross; the visible axle
              # ends and the crank pin bare steel; the chamfer faces the shell's paint
              yoke='oxide', cross='titanium', pin='steel', disc='oxide', crank='oxide', chamfer='paint')
COVER_SS = 4                # the chip mask's sub-texel samples per side, for its stats (the mask reads cyborg.py's WEAR_SS)
WEAR = 0.06                 # the share of painted texels worn through (edges; A.9 left the level to Skye: light here)
STRETCH_SHARE = (0.25, 0.75)  # C5f (the lead's call 1): a stacked primary reads the wear's stretches (the 9 mm noise
                            # that breaks the edges into worn clusters and clean runs) at a phase where this share of its
                            # exposed edges lies in a stretch: its own place's when that is inside (C5c's clusters for
                            # it: shell 9 at 0.27, the drums at 0.46 / 0.63), else the first of STRETCH_PHASES that is (a
                            # part wholly inside a clean run could not wear its family's share: clamp 8 at 0.02, clamp
                            # lug 8 and saddle 8 at 0.00 there wore 1.05 / 0 / 0.20 % of 2.73 / 4.35 / 0.88 %; one
                            # wholly inside a stretch wears every edge evenly again). 0.35-0.65 moved shell 9 off its
                            # own place to phase 11, where its chips gathered into a few rounded corner blobs
STRETCH_PHASES = 24         # the phases tried: shifts of the stretch noise by whole fractions of its cell
BRAID = dict(carriers=16, pitch=2.2, depth=0.06)   # the sleeve: 16 carriers, a 2.2-diameter lay length [E: the look]


def _rows():
    """the cyborg rows the parts use, as linear colours / roughness / metal (forge/cyborg.py read only)"""
    from . import cyborg as CY
    rv = {nm: CY.row_values(nm) for nm in ('cyb_paint', 'cyb_titanium', 'cyb_gasket')}
    ox = CY.row_values('cyb_steel', fastener_finish='black_oxide')
    st = CY.row_values('cyb_steel', fastener_finish='bare')
    c = lambda v, p='c0': np.array([v[p + 'r'], v[p + 'g'], v[p + 'b']])
    return dict(
        paint=dict(base=c(rv['cyb_paint']), rough=rv['cyb_paint']['rough'], facet=rv['cyb_paint']['rough_facet'],
                   metal=0.0, worn=c(rv['cyb_paint'], 'c1'), worn_rough=rv['cyb_paint']['rough1'], worn_metal=1.0),
        titanium=dict(base=c(rv['cyb_titanium']), rough=rv['cyb_titanium']['rough'],
                      facet=rv['cyb_titanium']['rough_facet'], metal=1.0),
        oxide=dict(base=c(ox), rough=ox['rough'], facet=ox['rough_facet'], metal=ox['metal'], worn=c(ox, 'c1'),
                   worn_rough=ox['rough1'], worn_metal=ox['metal1']),
        steel=dict(base=c(st), rough=st['rough'], facet=0.0, metal=1.0),
        rubber=dict(base=c(rv['cyb_gasket']), rough=rv['cyb_gasket']['rough'], facet=rv['cyb_gasket']['rough_facet'],
                    metal=0.0))


def vnoise3(P, cell, seed):
    """3D value noise in [0, 1] at points P (n, 3), lattice `cell` (m), smoothstep-weighted (this module's own: the
    material pass does not lean on a private helper of a file other rounds edit)"""
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


def fbm3(P, cell, seed, octaves=3):
    """octaves of vnoise3, each half the cell and half the weight, normalised to [0, 1]"""
    a, s, n = 1.0, 0.0, 0.0
    for o in range(octaves):
        s += a * vnoise3(P, cell / (2 ** o), seed + 101 * o)
        n += a
        a *= 0.5
    return s / n


def texel_map(A, res):
    """per covered texel (image order): its island, region, rigid group / piece kind, the hit point in the asset frame
    (the exploded offset removed) and in its group's own frame; the low's normal there (rasterised)"""
    size = A['size']
    isl = res['region']
    cov = (res['normal'][..., 3] > 0) & (isl >= 0)
    ys, xs = np.nonzero(cov)
    ii = isl[ys, xs]
    off = explode_offsets(A['chain'], A['des'])
    I = A['isl']
    off_i = np.array([piece_offset(it, off) for it in I])
    reg_i = np.array([it['region'] for it in I])
    bone_i = np.array([it['bone'] for it in I])
    P = res['position'][ys, xs, :3].astype(np.float64) - off_i[ii]
    grp = bone_i[ii]
    Pl = P - np.column_stack([A['chain']['x'][grp], np.zeros(len(P)), np.zeros(len(P))])
    return dict(ys=ys, xs=xs, isl=ii, reg=reg_i[ii], grp=grp, P=P, Pl=Pl, cov=cov, size=size)


def _ss(x, a, b):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


MARK_REGIONS = ('drum', 'yoke', 'can', 'disc', 'clamp')     # C5-UV b: the regions part_marks writes marks on


def part_marks(chain, des, P, Pl, rn, grp, names, tex, unit=1.0):
    """the TEXTURE TIER's marks on the knuckles' and the clamps' parts (material(): moved here unchanged, C5-UV b, so the
    stack's features check reads the very rules at a member's own place and scale): at points P (n, 3) in the asset
    frame, Pl the same less their group's joint origin, rn each point's region name, grp its group's joint (the
    island's bone), names its island's piece name, tex the texel (m); unit scales the rules' absolute lengths (their
    0.05-0.6 mm margins and floors, the dots' relief: 1 in material(); a member's s in the features check, so they are
    read at its own scale). The drums (pivot frames): the bright rims, the can's foot ring, its cap, the axle caps' bolt
    circles, the lamp; C5a-2's cardans in each knuckle's pivot frame (the knuckle from the piece's name): the lugs' outer
    faces a bright machined rim, the motor cans' foot rings and caps bright (the cap's four bolt dots, its dark centre,
    the status lamp), the roll ring's disc a bright bearing band (its texels and frame in `discs`, by coverage in
    material()); the clamps' lug screws (a dark socket on each lug's outer face). Returns dict(bright, dark, height,
    emis (n,), discs [(indices, x_k, disc dims, rim width)])"""
    u = float(unit)
    import re
    from scipy.spatial import cKDTree
    n = len(P)
    rn = np.asarray(rn)
    grp = np.asarray(grp)
    disc_jobs = []
    bright, dark, height, emis = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    m_d = rn == 'drum'
    if m_d.any():
        Ld = np.array([des['segs'][g]['L'] for g in grp[m_d]])
        q = Pl[m_d] - np.column_stack([Ld, np.zeros(len(Ld)), np.zeros(len(Ld))])
        rho = np.hypot(q[:, 0], q[:, 2])
        y = q[:, 1]
        Ks = [des['kn'][g + 1] for g in grp[m_d]]
        rd = np.array([K['rd'] for K in Ks])
        A0 = np.array([K['A'][0] for K in Ks])
        A4 = np.array([K['A'][4] for K in Ks])
        can = np.array([K['can'] for K in Ks])
        hc = np.array([K['hc'] for K in Ks])
        w_r = np.maximum(0.6e-3 * u, 2.2 * tex)
        rim = ((rho > rd - w_r) & ((np.abs(y - A0) < 0.5e-3 * u + 0.02 * rd) | (np.abs(y + A4) < 0.5e-3 * u + 0.02 * rd)))
        ring = can & (rho > DESIGN['can'][0] * rd - 0.2e-3 * u) & (y > A0 - 0.2e-3 * u) & \
            (y < A0 + DESIGN['can_ring'][1] * rd + 0.25e-3 * u)
        capm = can & (rho < DESIGN['cap'][0] * rd + 0.15e-3 * u) & (y > A0 + hc - 0.15e-3 * u)
        axle = ~can & (rho < DESIGN['axle'][0] * rd + 0.1e-3 * u) & (y > A0 - 0.1e-3 * u)
        b_ = np.zeros(len(q))
        b_[rim | ring | capm | axle] = 1.0
        bright[m_d] = b_
        ang = np.arctan2(q[:, 2], q[:, 0])
        nb = np.where(can, 4, 6)
        rb = np.where(can, 0.62 * DESIGN['cap'][0], 0.62 * DESIGN['axle'][0]) * rd
        da = (ang * nb / TAU) % 1.0
        da = np.minimum(da, 1.0 - da) * TAU / nb * rb
        dot = np.hypot(da, rho - rb) < np.maximum(0.10 * rd, 1.2 * tex)
        ctr = rho < np.maximum(0.12 * rd, 1.5 * tex)
        d_ = np.zeros(len(q))
        d_[(capm | axle) & (dot | ctr)] = 1.0
        dark[m_d] = d_
        h_ = np.zeros(len(q))
        h_[(capm | axle) & dot] = 0.05e-3 * u
        height[m_d] = h_
        lamp = capm & (np.hypot(q[:, 0] - 0.30 * rd, q[:, 2]) < np.maximum(0.07 * rd, 1.2 * tex))
        e_ = np.zeros(len(q))
        e_[lamp] = 1.0
        emis[m_d] = e_
    m_c = np.isin(rn, ('yoke', 'can', 'disc'))
    if m_c.any():
        sub = np.nonzero(m_c)[0]
        names_c = [names[i] for i in sub]
        kk = np.array([int(re.search(r'(\d+)', nm).group(1)) for nm in names_c])
        q = P[m_c] - np.column_stack([chain['x'][kk], np.zeros(len(kk)), np.zeros(len(kk))])
        w_r = np.maximum(0.25e-3 * u, 2.0 * tex)
        for k_ in np.unique(kk):
            K = des['kn'][k_]
            if K['kind'] != 'cardan' and not K.get('disc'):
                continue
            s_ = kk == k_
            qs = q[s_]
            nm_s = [nm for nm, f_ in zip(names_c, s_) if f_]
            pre = np.array([nm.split(' ')[0] + ' ' + nm.split(' ')[1] for nm in nm_s])
            b_ = np.zeros(s_.sum())
            d_ = np.zeros(s_.sum())
            e_ = np.zeros(s_.sum())
            h_ = np.zeros(s_.sum())
            if K['kind'] == 'cardan':
                bb, Yo, Zo = K['b'], K['Yo'], K['Zo']
                ry_, rz_ = np.hypot(qs[:, 0], qs[:, 2]), np.hypot(qs[:, 0], qs[:, 1])
                b_[np.isin(pre, ('yaw lug', 'yaw tine')) & (np.abs(qs[:, 1]) > Yo - w_r) & (ry_ > bb - w_r)] = 1.0
                b_[np.isin(pre, ('pitch lug', 'pitch tine')) & (np.abs(qs[:, 2]) > Zo - w_r) & (rz_ > bb - w_r)] = 1.0
                for can_nm, ax, base_, (Rc, Hc) in (('yaw can', 1, Yo, (K['Rc'], K['Hc'])),
                                                    ('pitch can', 2, Zo, K['pcan'] or (0.0, 0.0))):
                    mc = pre == can_nm
                    if not mc.any() or Rc <= 0.0:
                        continue
                    ax_ = qs[mc, ax]
                    o1, o2 = [a for a in (0, 1, 2) if a != ax]
                    rho_ = np.hypot(qs[mc, o1], qs[mc, o2])
                    foot = ax_ < base_ + 0.22 * Hc + 0.05e-3 * u
                    capm = (ax_ > base_ + Hc - 0.05e-3 * u) & (rho_ < 0.55 * Rc)
                    ang = np.arctan2(qs[mc, o2], qs[mc, o1])
                    rb = 0.62 * 0.5 * Rc
                    da = (ang * 4 / TAU) % 1.0
                    da = np.minimum(da, 1.0 - da) * TAU / 4 * rb
                    dot = np.hypot(da, rho_ - rb) < np.maximum(0.10 * Rc, 1.2 * tex)
                    ctr = rho_ < np.maximum(0.12 * Rc, 1.5 * tex)
                    lamp = capm & (np.hypot(qs[mc, o1] - 0.30 * Rc, qs[mc, o2]) < np.maximum(0.07 * Rc, 1.2 * tex))
                    b_[np.nonzero(mc)[0][foot | capm]] = 1.0
                    d_[np.nonzero(mc)[0][capm & (dot | ctr)]] = 1.0
                    h_[np.nonzero(mc)[0][capm & dot]] = 0.03e-3 * u
                    e_[np.nonzero(mc)[0][lamp]] = 1.0
            idx = sub[np.nonzero(s_)[0]]
            if K.get('disc') is not None:
                md = pre == 'ring disc'
                if md.any():
                    disc_jobs.append((idx[md], chain['x'][k_], K['disc'], w_r))
            bright[idx] = np.maximum(bright[idx], b_)
            dark[idx] = np.maximum(dark[idx], d_)
            emis[idx] = np.maximum(emis[idx], e_)
            height[idx] += h_
    m_k = rn == 'clamp'
    if m_k.any():
        CP = np.array([[c['x'], c['y'], 0.5 * (c['R_lug'] + c['rh']) + 0.5 * (c['R_lug'] - c['rh'])] for c in des['clamps']])
        tree = cKDTree(CP)
        dist, ci = tree.query(P[m_k])
        Dc = np.array([c['D'] for c in des['clamps']])[ci]
        onface = np.abs(P[m_k, 2] - CP[ci, 2]) < 0.05e-3 * u + 0.6 * tex
        lat = np.hypot(P[m_k, 0] - CP[ci, 0], P[m_k, 1] - CP[ci, 1])
        sockc = onface & (lat < np.maximum(0.11 * Dc, 1.3 * tex))
        dark[np.nonzero(m_k)[0][sockc]] = 1.0
    return dict(bright=bright, dark=dark, height=height, emis=emis, discs=disc_jobs)


def instance_weights(A):
    """C5-UV b (the lead's call 2): per island of A['isl'] (the bake view's) the share of the C5c texel population its
    texels stand for: 1 for a piece of its own; for a stacked primary's island 1 plus every member's carried island's
    area over its own (a member baked its own texels in C5c, as many as its area at the one density), over its group's
    texel scale-up squared (boost: the primary's texels are that much denser than C5c's)"""
    I = A['isl']
    w = np.ones(len(I))
    S = A.get('stack')
    if not S:
        return w
    from . import cyborg_stack as ST
    area = lambda it: 0.5 * float(np.linalg.norm(np.cross(it['V'][it['F'][:, 1]] - it['V'][it['F'][:, 0]],
                                                          it['V'][it['F'][:, 2]] - it['V'][it['F'][:, 0]]), axis=1).sum())
    pos = {}
    for i, it in enumerate(I):
        pos.setdefault(ST.spec_of(it['piece']), []).append(i)
    for q, rec in S['members'].items():
        ii = pos.get(rec['primary'], [])
        if len(ii) != len(rec['islands']):
            continue
        for i, it_q in zip(ii, rec['islands']):
            w[i] += area(it_q) / max(area(I[i]), 1e-30)
    for p_, b_ in S.get('boost', {}).items():
        for i in pos.get(p_, []):
            w[i] /= b_ ** 2
    return w


def stack_texels(A, T, P, Tx, Ty):
    """C5-UV b: per stacked group of the bake view A (its 'stack'), its primary's texels and under each of them every
    member's corresponding point: [(primary, texel indices (sorted), [(Pm, Txm, Tym, gm, wm, sm) per member])]. A
    texel's place on its island (its centre located in the island's packed UVs: triangle, barycentric), the same place
    on the member's carried island, plus the texel's hit over its low turned and scaled by the member's similarity: Pm;
    the texel's footprint turned and scaled: Txm, Tym; the member island's joint: gm; its area over the primary
    island's (instance_weights'): wm; the member's scale s: sm"""
    S = A.get('stack')
    if not S:
        return []
    from . import cyborg_stack as ST
    I = A['isl']
    size = T['size']
    area = lambda it: 0.5 * float(np.linalg.norm(np.cross(it['V'][it['F'][:, 1]] - it['V'][it['F'][:, 0]],
                                                          it['V'][it['F'][:, 2]] - it['V'][it['F'][:, 0]]), axis=1).sum())
    pos, by_p = {}, {}
    for i, it in enumerate(I):
        pos.setdefault(ST.spec_of(it['piece']), []).append(i)
    for q, rec in S['members'].items():
        by_p.setdefault(rec['primary'], []).append(rec)
    out = []
    for p_, recs in sorted(by_p.items()):
        ii = pos.get(p_, [])
        recs = [r for r in recs if len(r['islands']) == len(ii)]
        if not ii or not recs:
            continue
        tt_all, mem = [], [([], [], [], [], [], []) for _ in recs]
        for j, i_ in enumerate(ii):
            tt = np.nonzero(T['isl'] == i_)[0]
            if not len(tt):
                continue
            it = I[i_]
            uv = np.column_stack([(T['xs'][tt] + 0.5) / size, 1.0 - (T['ys'][tt] + 0.5) / size, np.zeros(len(tt))])
            tri, bary, _, _ = ST.locate(uv, np.column_stack([it['UVp'], np.zeros(len(it['UVp']))]), it['F'])
            off = P[tt] - ST.at(it['V'], it['F'], tri, bary)
            tt_all.append(tt)
            for r, m in zip(recs, mem):
                iq = r['islands'][j]
                Rm, s_ = np.asarray(r['R'], np.float64), float(r['s'])
                m[0].append(ST.at(iq['V'], iq['F'], tri, bary) + s_ * off @ Rm.T)
                m[1].append(s_ * Tx[tt] @ Rm.T)
                m[2].append(s_ * Ty[tt] @ Rm.T)
                m[3].append(np.full(len(tt), int(iq['bone'])))
                m[4].append(np.full(len(tt), area(iq) / max(area(it), 1e-30)))
                m[5].append(np.full(len(tt), s_))
        if not tt_all:
            continue
        tt = np.concatenate(tt_all)
        o = np.argsort(tt, kind='stable')
        out.append((p_, tt[o], [tuple(np.concatenate(x)[o] for x in m) for m in mem]))
    return out


def _wquantile(v, w, q):
    """the q quantile of v under weights w (the step quantile; np.quantile's, on v as given, when the weights are all
    equal)"""
    w = np.asarray(w, np.float64).ravel()
    if np.all(w == w[0]):
        return float(np.quantile(v, q))
    v = np.asarray(v, np.float64).ravel()
    o = np.argsort(v, kind='stable')
    cw = np.cumsum(w[o])
    return float(v[o][min(int(np.searchsorted(cw, q * cw[-1])), len(v) - 1)])


GUTTER_DARK = 2.0           # C5-UV b (the lead's call 4): where a dark texel (albedo luminance under DARK_LUM, linear: black
DARK_LUM = 0.15             # oxide, rubber) and a light one (white paint, titanium, steel, a bright ring) share a gutter, the
                            # dark one's values fill it this many texels further (dark_gutter)


def dark_gutter(dil, base, T, size, steps=16):
    """C5-UV b: the gutters re-split between dark and light texels. bake.dilate_all splits a gutter down the middle; at a
    far mip (a band seen edge on) a dark island's edge then averages in its light neighbour's half, a light dash on
    black rubber (the rubber band against shell 17's white paint, the C5d check's "collar dashes"), where a light
    island's edge averaging in dark reads as the crease it is. Each gutter texel within `steps` of a texel takes the
    nearest DARK texel's values when that lies at most GUTTER_DARK further than its nearest texel of any kind; every
    map alike (dil: dilate_all's dict). Returns the dict"""
    from scipy import ndimage
    cov = T['cov']
    lum = base @ np.array([0.2126, 0.7152, 0.0722])
    dk = np.zeros((size, size), bool)
    dk[T['ys'][lum < DARK_LUM], T['xs'][lum < DARK_LUM]] = True
    if not dk.any() or dk.sum() == cov.sum():
        return dil
    d_all, (ay, ax) = ndimage.distance_transform_edt(~cov, return_indices=True)
    d_dk, (iy, ix) = ndimage.distance_transform_edt(~dk, return_indices=True)
    # only where dilate_all gave the gutter texel a LIGHT texel's values (a dark one's stays as it was)
    take = ~cov & (d_all <= steps) & (d_dk <= steps) & (d_dk <= d_all + GUTTER_DARK) & ~dk[ay, ax]
    out = {}
    for k, a in dil.items():
        if np.ndim(a) < 2 or np.shape(a)[:2] != cov.shape:
            out[k] = a
            continue
        b = a.copy()
        b[take] = a[iy[take], ix[take]]
        out[k] = b
    return out


def material(A, res, log=print):
    """the material pass over the set (numpy, from the bake's drivers): albedo (sRGB), normal (the baked one with the
    texture tier composed in: hex sockets, the sleeve's braid, the caps' bolt dots), ORM (AO, roughness, metal), masks
    (R the primary tint region (the white paint), G the accent region, B the emissive mask (a status lamp on every motor
    can's cap), A the wear). Returns (maps, stats)"""
    import time
    from scipy import ndimage
    from scipy.spatial import cKDTree

    from . import bake as BK
    from . import cyborg as CY
    t0 = time.time()
    R = _rows()
    T = texel_map(A, res)
    size = T['size']
    ys, xs, reg, grp, P, Pl = T['ys'], T['xs'], T['reg'], T['grp'], T['P'], T['Pl']
    n = len(ys)
    des, chain = A['des'], A['chain']
    tex = 1.0 / A['px']
    rn = np.array(REGIONS)[reg]
    fin = np.array([FINISH[r] for r in rn])
    base = np.zeros((n, 3))
    rough = np.zeros(n)
    metal = np.zeros(n)
    for nm, row in R.items():
        m = fin == nm
        base[m] = row['base']
        rough[m] = row['rough']
        metal[m] = row['metal']
    # per-part variation: each island draws its own value and roughness inside the row's range (study T's per-plate jitter)
    rng = np.random.default_rng(55)
    jl = 1.0 + 0.025 * rng.standard_normal(len(A['isl']))
    jr = rng.uniform(-1.0, 1.0, len(A['isl']))
    base *= jl[T['isl']][:, None]
    facet = np.array([R[f].get('facet', 0.0) for f in fin])
    rough += facet * jr[T['isl']] * 0.6
    height = np.zeros(n)                                     # the texture tier (m), composed into the normal below
    emis = np.zeros(n)
    cav = res['cavity'][ys, xs].astype(np.float64)
    ao = res['ao'][ys, xs].astype(np.float64)
    curv = res['curvature'][ys, xs].astype(np.float64)
    thk = res['thickness'][ys, xs].astype(np.float64)
    nrm_b = res['normal'][ys, xs, :3].astype(np.float64)
    # C5c: a HIDDEN texel (under a neighbour) next to the visible face takes its nearest visible texel's AO and cavity
    # (same island, within 3 texels): a covered texel's own shade is its rays' from inside the neighbour (0), and the
    # filtering at the contact line read it in as a 1-texel black line
    hid_t = np.asarray(res.get('hidden', np.zeros((size, size), bool)), bool)[ys, xs]
    if hid_t.any() and (~hid_t).any():
        vm_ = np.zeros((size, size), bool)
        vm_[ys[~hid_t], xs[~hid_t]] = True
        Ig_ = np.full((size, size), -1, np.int64)
        Ig_[ys, xs] = T['isl']
        Ga_, Gc_ = np.zeros((size, size)), np.zeros((size, size))
        Ga_[ys, xs], Gc_[ys, xs] = ao, cav
        dd_, (iy_, ix_) = ndimage.distance_transform_edt(~vm_, return_indices=True)
        hi_ = np.nonzero(hid_t)[0]
        yh_, xh_ = ys[hi_], xs[hi_]
        ok_ = (dd_[yh_, xh_] <= 3.0) & (Ig_[iy_[yh_, xh_], ix_[yh_, xh_]] == T['isl'][hi_])
        ao[hi_[ok_]] = Ga_[iy_[yh_[ok_], xh_[ok_]], ix_[yh_[ok_], xh_[ok_]]]
        cav[hi_[ok_]] = Gc_[iy_[yh_[ok_], xh_[ok_]], ix_[yh_[ok_], xh_[ok_]]]
    # the knuckles' and the clamps' marks (C5-UV b: part_marks, the same rules, so the stack's features check reads them)
    mk_ = part_marks(chain, des, P, Pl, rn, grp, [A['isl'][i]['piece'] for i in T['isl']], tex)
    disc_jobs = mk_['discs']                                 # C5c: the roll discs' bands, by sub-sample coverage below
    bright = mk_['bright']                                   # a machined bright ring: titanium over the black oxide
    dark = mk_['dark']                                       # a socket or a recess: darker, rougher
    height, emis = mk_['height'], mk_['emis']
    # ---- the shells' heads and the collar's set screws (analytic: the heads' list in each body's frame)
    heads = []
    for g, d in A['det'].items():
        for h in d['heads']:
            heads.append((g, h['p'], h['n'] / np.linalg.norm(h['n']), h['D'], h.get('kind', 'pan')))
    m_h = np.isin(rn, ('shell', 'collar'))
    hmask = np.zeros(n)
    if heads and m_h.any():
        HP = np.array([np.array([chain['x'][body_k(h[0])], 0.0, 0.0]) + h[1] for h in heads])
        tree = cKDTree(HP)
        dist, hi = tree.query(P[m_h])
        hD = np.array([h[3] for h in heads])[hi]
        hN = np.array([h[2] for h in heads])[hi]
        kind = np.array([h[4] for h in heads])[hi]
        v = P[m_h] - HP[hi]
        lat = np.linalg.norm(v - hN * np.einsum('ij,ij->i', v, hN)[:, None], axis=1)
        r_h = 0.5 * hD
        head = (lat < r_h) & (kind == 'pan')
        mouth = (lat >= r_h + CB_RADIAL - 0.35e-3) & (lat < r_h + CB_RADIAL + 0.15e-3) & (kind == 'pan')
        # the hex socket: a hexagon of circumradius 0.26 D in the head's plane (cyborg_texel's), and the set screws'
        e1 = np.cross(hN, [0.0, 0.0, 1.0])
        bad = np.linalg.norm(e1, axis=1) < 0.1
        e1[bad] = np.cross(hN[bad], [1.0, 0.0, 0.0])
        e1 /= np.linalg.norm(e1, axis=1, keepdims=True)
        e2 = np.cross(hN, e1)
        a_, b2 = np.einsum('ij,ij->i', v, e1), np.einsum('ij,ij->i', v, e2)
        hexd = np.maximum(np.abs(a_) * 0.8660254 + np.abs(b2) * 0.5, np.abs(b2))
        sock = (hexd < 0.26 * hD) & ((kind == 'pan') & head | (kind == 'set') & (lat < 0.31 * hD))
        hm = np.zeros(m_h.sum())
        hm[head | ((kind == 'set') & (lat < 0.31 * hD))] = 1.0
        hmask[m_h] = hm
        sub = np.nonzero(m_h)[0]
        fin_h = fin.copy()
        base[sub[hm > 0]] = R['oxide']['base']
        rough[sub[hm > 0]] = R['oxide']['rough']
        metal[sub[hm > 0]] = R['oxide']['metal']
        bright[sub[mouth]] = 1.0
        dark[sub[sock]] = 1.0
        height[sub[sock]] = -0.25e-3
    # ---- the collar's distal edge (a bright machined ring) and the band of its lip
    m_c = rn == 'collar'
    if m_c.any():
        c0, c1 = des['flange']['collar']
        xc = Pl[m_c, 0]
        bright[np.nonzero(m_c)[0][(xc > c1 - 1.1e-3)]] = 1.0
        # the clamp's SPLIT (p02's split collar): a dark line 1.5 texels wide in the lug's mid-plane (y = 0), over
        # its outer face, down its end faces and along the collar's -z flat the length of the collar, with a groove
        # 0.2 mm deep in the normal (the texture tier: carved into the high it baked back-facing and missed)
        zc_ = float(-collar_outline(chain)[0][:, 1].min())
        spl = (np.abs(Pl[m_c, 1]) < 0.75 * tex) & (Pl[m_c, 2] < -(zc_ - 0.3e-3))
        dark[np.nonzero(m_c)[0][spl]] = 1.0
        height[np.nonzero(m_c)[0][spl]] = -0.2e-3
    # ---- the tongues and the crosses: brushed (radial streaks through roughness); the rods mirror-bright
    m_t = np.isin(rn, ('tongue', 'cross'))
    if m_t.any():
        ang = np.arctan2(Pl[m_t, 2], Pl[m_t, 0])
        streak = np.sin(ang * 260.0 + 7.0 * np.sin(ang * 13.0)) * 0.5 + 0.5
        rough[m_t] += 0.05 * (streak - 0.5)
    # ---- the tip's socket (a dark recess), the clamps' lug screws (a dark socket on each lug's outer face)
    m_b = rn == 'boss'
    if m_b.any():
        Lt = des['segs'][N_JOINTS - 1]['L']
        rr_ = np.hypot(Pl[m_b, 1], Pl[m_b, 2])
        e = 0.62 * float(radius_at(chain, chain['x'][N_JOINTS - 1] + body_nodes(chain, des, N_JOINTS - 1)['x1']))
        dark[np.nonzero(m_b)[0][(Pl[m_b, 0] > Lt - 0.4 * e) & (rr_ < 0.5 * e)]] = 1.0
    # (the clamps' lug screws: part_marks, above)
    # ---- the hose: a braided sleeve (two helical families over and under), in its own (s, phi) on the path
    m_s = rn == 'hose'
    if m_s.any():
        H = des['hose']
        Pp = H['P']
        segl = np.linalg.norm(np.diff(Pp, axis=0), axis=1)
        sP = np.concatenate([[0.0], np.cumsum(segl)])
        Tg = np.gradient(Pp, sP, axis=0)
        Tg /= np.linalg.norm(Tg, axis=1, keepdims=True)
        tree = cKDTree(Pp)
        _, j = tree.query(P[m_s])
        v = P[m_s] - Pp[j]
        s_ = sP[j] + np.einsum('ij,ij->i', v, Tg[j])
        e2 = np.cross(Tg[j], [0.0, 0.0, 1.0])
        e2 /= np.maximum(np.linalg.norm(e2, axis=1, keepdims=True), 1e-12)
        e1 = np.cross(e2, Tg[j])
        phi = np.arctan2(np.einsum('ij,ij->i', v, e1), np.einsum('ij,ij->i', v, e2))
        rh_ = H['r'][j]
        # the weave: two families of N tows each, one along each hand of the helix (phase N phi / 2 pi +- s / P, P the
        # tows' advance along the hose: diamonds a little longer than wide), over and under in a plain weave (the top
        # family where the two tow indices' sum is even); each visible tow a crown across its own width, its edges the
        # crevices. Band-limited: the relief fades where a tow is under 3 texels wide (the distal sleeve reads flat)
        N = BRAID['carriers']
        Pb = 1.25 * TAU * rh_ / N
        phA = N * phi / TAU + s_ / Pb
        phB = N * phi / TAU - s_ / Pb
        fA, fB = phA - np.floor(phA), phB - np.floor(phB)
        topA = (np.floor(phA) + np.floor(phB)) % 2 == 0
        crown = np.where(topA, np.sin(np.pi * fA), np.sin(np.pi * fB))
        tow_tx = TAU * rh_ / N / tex
        amp = _ss(tow_tx, 2.5, 4.0)
        hb = 0.5 + amp * (crown ** 0.6 - 0.5)
        height[m_s] = BRAID['depth'] * 2.0 * rh_ * (hb - 0.5)
        base[m_s] *= (0.80 + 0.35 * hb)[:, None]
        rough[m_s] = 0.70 - 0.16 * hb
    # ---- wear: an EDGE rule on the paint (convex curvature, broken in stretches, a lip guard off the seams and the
    # counterbores), the oxide's rims chipped to bare steel more sparsely; contact scuffs on the oral side
    paint = fin == 'paint'
    oxide = (fin == 'oxide') & (hmask == 0)
    # convex rounds: the shells' rho (~600 /m) and smaller, AND rounds against the arm's local radius r: the bake reads
    # curvature over ~1 mm, so the small distal segments' whole flats read 100-900 /m (0.45-1.5 r against their rounds'
    # 2.4-5.6 r and the proximal rounds' 10 r). The absolute ramp alone wore 26-51 % of the flats of segments 20, 22 and
    # 23, a mottle (C5a's check; the bar is flats at most 4.4 %, A.2.1), as it had the oxide's small parts
    r_loc = np.asarray(radius_at(chain, np.clip(P[:, 0], chain['x'][J0], chain['x'][-1])), np.float64)
    expo = _ss(curv, 180.0, 700.0) * _ss(curv * r_loc, 1.8, 3.2)
    seam_near = np.zeros((size, size), bool)
    seam_near[ys[cav < 0.80], xs[cav < 0.80]] = True
    dist_seam = ndimage.distance_transform_edt(~seam_near)[ys, xs] * tex
    guard = _ss(dist_seam, 0.6e-3, 1.2e-3)
    noise = lambda Q, cell, sd: fbm3(Q, cell, sd, 3)
    # the chip mask by COVERAGE, C3b's (forge/cyborg.py, the lead's C3b call 1; his C5a-2 call 5): every paint (oxide)
    # texel reads the wear field on CY.WEAR_SS x CY.WEAR_SS sub-samples over its own footprint on the surface (the high's
    # position per texel step within its island, as C3b's texel Jacobian places them), each with a crisp edge
    # CY.WEAR_SUB_SOFT x the threshold, and takes their mean: a chip's edge falls inside its texels instead of on their
    # grid (C5a's per-texel threshold left 81 % of the worn texels at full value, hard texel stairs up close). The slow
    # terms (the exposure, the seam guard) carried across the texel by their texel gradients, the noise terms (the
    # stretches, the chips) read at each sub-sample; the threshold the sub-samples' quantile, as C3b's. The oxide chips
    # only on its parts' RIMS: the curvature against the arm's local radius (an edge break or a rim turns past 15 / r; a
    # collar's or a small drum's whole band, 1/R at 1.5-7.5 / r, never does: the absolute ramp chipped the small distal
    # parts' and the hose collars' bodies all over, a mottle), a floor under its threshold (few rims: the quantile must
    # not fall to zero and half-wear every texel)
    Pm = np.full((size, size, 3), np.nan)
    Pm[ys, xs] = P
    Im_ = np.full((size, size), -1, np.int64)
    Im_[ys, xs] = T['isl']

    def nbr(dx, dy):
        x1, y1 = np.clip(xs + dx, 0, size - 1), np.clip(ys + dy, 0, size - 1)
        x0, y0 = np.clip(xs - dx, 0, size - 1), np.clip(ys - dy, 0, size - 1)
        return (y1, x1, Im_[y1, x1] == T['isl']), (y0, x0, Im_[y0, x0] == T['isl'])

    def step(dx, dy):
        (y1, x1, ok1), (y0, x0, ok0) = nbr(dx, dy)
        p1 = np.where(ok1[:, None], Pm[y1, x1], P)
        p0 = np.where(ok0[:, None], Pm[y0, x0], P)
        return (p1 - p0) / np.where(ok1 & ok0, 2.0, 1.0)[:, None]

    def tgrad(v):
        G = np.zeros((size, size))
        G[ys, xs] = v
        out = []
        for dx, dy in ((1, 0), (0, 1)):
            (y1, x1, ok1), (y0, x0, ok0) = nbr(dx, dy)
            out.append((np.where(ok1, G[y1, x1], v) - np.where(ok0, G[y0, x0], v)) / np.where(ok1 & ok0, 2.0, 1.0))
        return out
    Tx, Ty = step(1, 0), step(0, 1)
    SS = CY.WEAR_SS
    o1 = (np.arange(SS) + 0.5) / SS - 0.5
    ox_, oy_ = (a_.ravel() for a_ in np.meshgrid(o1, o1, indexing='xy'))
    # C5c: the roll discs' bright bearing band and seal line by coverage of the texel's footprint (its SS x SS
    # sub-samples on the surface, as the chips read): the band's inner circle anti-aliased, no saw-tooth
    for idx_d, xk_d, (Rb, wb, xd), w_r in disc_jobs:
        Qd = (P[idx_d, None, :] - np.array([xk_d, 0.0, 0.0]) + ox_[None, :, None] * Tx[idx_d, None, :]
              + oy_[None, :, None] * Ty[idx_d, None, :])
        # the band follows the low's POLYGON (revolve_islands' n-gon at Rb, its corners at 2 pi i / n in _frame_axis's
        # basis), not the circle: a circle inside the polygon read as a band swelling at every corner, scalloped
        n_d = n_sides(Rb)
        e1_, e2_ = _frame_axis(AX['x'])
        u_d, v_d = Qd @ e1_, Qd @ e2_
        rho_ = np.hypot(u_d, v_d)
        ph_ = np.arctan2(v_d, u_d) % TAU
        ph_c = (np.floor(ph_ * n_d / TAU) + 0.5) * TAU / n_d
        R_poly = Rb * math.cos(math.pi / n_d) / np.maximum(np.cos(ph_ - ph_c), 0.5)
        band = rho_ > R_poly - 0.6 * w_r
        seal = band & (np.abs(Qd[..., 0] + xd + 0.5 * wb) < 0.5 * w_r)
        fb, fs = (band & ~seal).mean(1), seal.mean(1)
        bright[idx_d] = np.maximum(bright[idx_d], fb)
        dark[idx_d] = np.maximum(dark[idx_d], fs)
        height[idx_d] += -0.04e-3 * fs
    # C5c: each rigid part's chips at its OWN scale (the noise's cells x the part's radius over the flange's, the
    # stretches at least 0.25 x, the chips at least 2.5 texels), the chips' outline warped (a domain warp at twice the
    # chip cell) and their edge sharpened: on the Minsky shells (r 3-4 mm) the arm-wide 9 mm stretches and 1.2 mm chips
    # wore whole edge runs, blocky (c05_close_cardan_roll)
    r_ref = float(radius_at(chain, chain['x'][CUT]))
    r_grp = np.array([float(radius_at(chain, chain['x'][k_])) for k_ in range(N_JOINTS)])
    sc_g = np.clip(r_grp / r_ref, 0.0, 1.0)
    sc_st = np.maximum(sc_g, 0.25)[grp]
    sc_ch = np.maximum(sc_g, 2.5 * tex / 1.2e-3)[grp]

    sc_st_k = np.maximum(sc_g, 0.25)                       # (per joint: a stacked member's own, C5-UV b)
    sc_ch_k = np.maximum(sc_g, 2.5 * tex / 1.2e-3)

    def field_at(slow, ii, Pq, Txq, Tyq, gq, chunk=150_000, stretch=True, slow_rows=None, stretch_off=None):
        """the wear field at the sub-samples of the texels ii, read at the points Pq with the footprints Txq / Tyq and
        the group joints gq (the texels' own; C5-UV b: or a stacked member's corresponding points), the slow term and
        its texel gradients the texels' own (C5-UV b: or slow_rows, one value per row of ii, read flat over the texel:
        a stacked member's own slow term at its own scale); without the stretches when stretch is False; C5f: the
        stretches' noise read stretch_off (its scaled domain's shift, stretch_phase) along: (m, SS * SS) float32"""
        gx_, gy_ = tgrad(slow) if slow_rows is None else (None, None)
        out = np.zeros((len(ii), SS * SS), np.float32)
        for c0_ in range(0, len(ii), chunk):
            jj = ii[c0_:c0_ + chunk]
            sel_ = slice(c0_, c0_ + len(jj))
            Q = (Pq[sel_, None, :] + ox_[None, :, None] * Txq[sel_, None, :] + oy_[None, :, None] * Tyq[sel_, None, :])
            Q = Q.reshape(-1, 3)
            if slow_rows is None:
                sl = np.maximum(slow[jj, None] + gx_[jj, None] * ox_[None] + gy_[jj, None] * oy_[None], 0.0)
            else:
                sl = np.maximum(np.asarray(slow_rows, np.float64)[sel_, None], 0.0)
            ss_ = np.repeat(sc_st_k[gq[sel_]], SS * SS)[:, None]
            sc_ = np.repeat(sc_ch_k[gq[sel_]], SS * SS)[:, None]
            st_ = _ss(noise(Q / ss_ + (0.0 if stretch_off is None else np.asarray(stretch_off, np.float64)), 9.0e-3, 11),
                      0.46, 0.58).reshape(len(jj), -1) if stretch else 1.0
            Qc = Q / sc_
            warp = np.column_stack([vnoise3(Qc, 2.4e-3, 41 + 2 * a_) for a_ in range(3)]) - 0.5
            ch_ = noise(Qc + 1.2e-3 * warp, 1.2e-3, 23).reshape(len(jj), -1)
            out[c0_:c0_ + len(jj)] = sl * st_ * (0.25 + 0.75 * _ss(ch_, 0.30, 0.72))
        return out

    def stretch_phase(slow, ii, gq):
        """C5f (the lead's call 1): the shift of the stretches' noise a stacked primary reads (field_at's stretch_off):
        the share of its exposed edges in a stretch (the stretch term at its texels' centres, weighted by the slow
        term: where chips can fall) at its own place when that lies in STRETCH_SHARE, else at the first of
        STRETCH_PHASES shifts (whole fractions of the 9 mm cell along three incommensurate directions) that does, else
        the nearest to the middle. Returns (the shift (3,), the share, the phase index)"""
        w_ = np.maximum(np.asarray(slow, np.float64)[ii], 0.0)
        if w_.sum() <= 0.0:
            return np.zeros(3), 0.0, 0
        Qs = P[ii] / sc_st_k[gq][:, None]
        best = None
        for k_ in range(STRETCH_PHASES):
            o_ = 9.0e-3 * np.array([(0.61803 * k_) % 1.0, (0.41421 * k_ + 0.5 * (k_ > 0)) % 1.0,
                                   (0.73205 * k_) % 1.0]) * (k_ > 0)
            sh_ = float((w_ * _ss(noise(Qs + o_, 9.0e-3, 11), 0.46, 0.58)).sum() / w_.sum())
            if STRETCH_SHARE[0] <= sh_ <= STRETCH_SHARE[1]:
                return o_, sh_, k_
            if best is None or abs(sh_ - 0.5) < abs(best[1] - 0.5):
                best = (o_, sh_, k_)
        return best

    def sub_field(slow, mask, chunk=150_000):
        """the wear field at the sub-samples of the masked texels: (their indices, (m, SS * SS) float32)"""
        ii = np.nonzero(mask)[0]
        return ii, field_at(slow, ii, P[ii], Tx[ii], Ty[ii], grp[ii], chunk)

    def coverage(ii, Ws, thr):
        """the chips' coverage at threshold thr (C5-UV b: one per row of Ws, or one for all)"""
        cov = np.zeros(n)
        if np.ndim(thr):
            thr = np.asarray(thr, np.float64)[:, None]
            soft = np.maximum(CY.WEAR_SUB_SOFT * thr, 1e-5)
        else:
            soft = max(CY.WEAR_SUB_SOFT * thr, 1e-5)
        cov[ii] = _ss(Ws, thr - soft, thr + soft).mean(1)
        return cov

    from .cyborg_stack import spec_of as _spec_of
    isl_b2 = np.array([float((A.get('stack') or {}).get('boost', {}).get(_spec_of(it['piece']), 1.0)) ** 2
                       for it in A['isl']])

    def shown_wear(ii, Ws, slow, q, floor=0.0, slow_of=None):
        """C5-UV b (the lead's call 2): the chips over the instances as C5c baked them. A member shows its primary's
        texels; over those alone the thresholds' quantiles moved, and the chips come in STRETCHES (a 9 mm noise along
        the arm), so each group took its primary's stretch: clamp 8 lay outside one (0.0-0.1 % worn in C5c) where clamps
        9-12 lay in one (3-19 %), drum 9 in one (3.3 %) where drums 12-15 were clean. So each member's field is read at
        its own place and scale (stack_texels: its point under each of its primary's texels, its own joint's noise
        scale; the slow terms slow_of(texels, s, points): the primary's readings at those texels taken to the member's
        own scale, its seam distance and wall thickness x s, the arm's radius at its own place, the curvature as read:
        the absolute ramps (a 0.9-1.3 mm wall's trust, a 0.6-1.2 mm seam guard, the rims' curvature x radius) that a
        smaller copy's own bake read smaller), and
          the threshold is the q quantile over every baked texel (a stacked primary's at 1 / boost^2: C5c had that many
            fewer of its texels) and every member's field (its area share / boost^2): the C5c population (instance count
            by area, the lead's weighting), at least `floor`;
          each group wears, on its primary's texels, the instances' area-weighted share WORN PAST HALF (coverage > 0.5,
            the stats' and the checks' reading) at that threshold: its primary's field read WITH the stretches (C5f,
            the lead's call 1: its irregular clusters repeat on its members, as Skye accepts identical wear on
            stacked parts; read without them, C5-UV b's choice as its members lie in many, the chips ran as one even
            row of dashes along every edge, shell to shell) at the phase stretch_phase chose, its own chips' noise
            kept, the group's threshold set by bisection to that share.
        Returns (the common threshold, per-row thresholds (or the common one), the field (a stacked primary's rows
        replaced), {primary: (the instances' share, the primary's own at the common threshold, the group's threshold,
        the share it gives weighted, over the primary's texels alone, the primary's texels, C5f: its stretches' share
        and phase)})"""
        if not len(ii):
            return 1.0, 1.0, Ws, {}
        cov_rows = lambda W_, t_: _ss(W_, t_ - max(CY.WEAR_SUB_SOFT * t_, 1e-5),
                                      t_ + max(CY.WEAR_SUB_SOFT * t_, 1e-5)).mean(1)
        past_half = lambda W_, t_: (cov_rows(W_, t_) > 0.5).astype(np.float64)
        gl = []
        for p_, tt, mems in groups_t:
            rows = np.searchsorted(ii, tt)
            hit = (rows < len(ii)) & (ii[np.minimum(rows, len(ii) - 1)] == tt)
            if hit.sum() < 4:
                continue
            sel = np.nonzero(hit)[0]
            gl.append((p_, rows[hit], tt[sel], [(field_at(slow, tt[sel], Pm[sel], Txm[sel], Tym[sel], gm[sel],
                                                          slow_rows=(slow_of(tt[sel], sm[sel], Pm[sel])
                                                                     if slow_of is not None else None)), wm[sel])
                                                for Pm, Txm, Tym, gm, wm, sm in mems]))
        b2 = isl_b2[T['isl'][ii]]
        vs, ws = [Ws.ravel()], [np.repeat(1.0 / b2, Ws.shape[1])]
        for p_, rows, ts, fm in gl:
            for W_m, w_m in fm:
                vs.append(W_m.ravel())
                ws.append(np.repeat(w_m / b2[rows], Ws.shape[1]))
        tau0 = max(_wquantile(np.concatenate(vs), np.concatenate(ws), q), floor)
        if not gl:
            return tau0, tau0, Ws, {}
        thr = np.full(len(ii), tau0)
        Wout = Ws.copy()
        rep = {}
        for p_, rows, ts, fm in gl:
            c_p = past_half(Ws[rows], tau0)
            wsum = 1.0 + sum(w_m for _, w_m in fm)
            target = (c_p.sum() + sum(float((w_m * past_half(W_m, tau0)).sum()) for W_m, w_m in fm)) / float(wsum.sum())
            o_st, sh_st, k_st = stretch_phase(slow, ts, grp[ts])
            W_ns = field_at(slow, ts, P[ts], Tx[ts], Ty[ts], grp[ts], stretch_off=o_st)
            own = lambda t_: float((wsum * past_half(W_ns, t_)).sum() / wsum.sum())
            # (the threshold never under twice the soft edge's 1e-5 floor: below it a texel with NO field reads 0.49
            # worn, under the past-half count: clamp 15's chipless group read light grey all over)
            floor_t = 2.0e-5
            lo, hi = floor_t, max(float(W_ns.max()) * 1.05, floor_t) + 1e-6
            if target <= 0.0:
                tg = hi
            elif own(lo) <= target:
                tg = lo
            else:
                for _ in range(32):
                    mid = 0.5 * (lo + hi)
                    lo, hi = (mid, hi) if own(mid) > target else (lo, mid)
                tg = hi
            Wout[rows] = W_ns
            thr[rows] = tg
            # (the report: the instances' share, its primary's own at the common threshold, the group's threshold, the
            # share it gives, weighted and over the primary's texels alone, and the primary's texels)
            rep[p_] = (float(target), float(c_p.mean()), float(tg), own(tg), float(past_half(W_ns, tg).mean()),
                       int(len(rows)), float(sh_st), int(k_st))
        return tau0, thr, Wout, rep
    w_i = instance_weights(A)
    groups_t = stack_texels(A, T, P, Tx, Ty)
    # a stacked member's own slow terms (C5-UV b): its primary's readings at the shared texels taken to its scale s: the
    # seam distance and the wall thickness x s, the arm's radius at its own place; the curvature as read (the bake's
    # fixed 0.54 mm window reads an edge break smaller than itself by its turn, whatever its radius: C5c's drums 9-15
    # wore 3.1, 1.9, 0.4 ... 0.05 % by their own readings against their own arm radius, not 1 / s more)
    r_of = lambda Pm_: np.asarray(radius_at(chain, np.clip(Pm_[:, 0], chain['x'][J0], chain['x'][-1])), np.float64)
    slow_of_p = lambda tt_, s_, Pm_: (_ss(curv[tt_], 180.0, 700.0) * _ss(curv[tt_] * r_of(Pm_), 1.8, 3.2) *
                                      _ss(dist_seam[tt_] * s_, 0.6e-3, 1.2e-3))
    slow_of_o = lambda tt_, s_, Pm_: (_ss(curv[tt_] * r_of(Pm_), 15.0, 40.0) *
                                      _ss(dist_seam[tt_] * s_, 0.6e-3, 1.2e-3) * _ss(thk[tt_] * s_, 0.9e-3, 1.3e-3))
    slow_p = expo * guard
    ip, Wps = sub_field(slow_p, paint)
    tau_u = float(np.quantile(Wps, 1.0 - WEAR)) if len(ip) else 1.0
    tau, thr_p, Wps, cal_p = shown_wear(ip, Wps, slow_p, 1.0 - WEAR, slow_of=slow_of_p)
    wear = coverage(ip, Wps, thr_p)
    # C5c: an oxide rim chips only where its wall is thicker than the curvature reading's reach (the bake's Laplacian
    # steps 0.54 mm each way: across a clamp collar's 0.47 mm wall it read 2,000-3,500 /m over the whole band, so the
    # rule took the collar's body for a rim: the white fleck at clamp 8's mouth, a bare-steel chip on its top)
    trust = _ss(thk, 0.9e-3, 1.3e-3)
    slow_o = _ss(curv * r_loc, 15.0, 40.0) * guard * trust
    io, Wos = sub_field(slow_o, oxide)
    tau_ou = max(float(np.quantile(Wos, 1.0 - 0.5 * WEAR)), 0.25) if len(io) else 1.0
    tau_o, thr_o, Wos, cal_o = shown_wear(io, Wos, slow_o, 1.0 - 0.5 * WEAR, floor=0.25, slow_of=slow_of_o)
    wear_o = coverage(io, Wos, thr_o)
    del Wps, Wos
    # the oral side drags on the ground (A.5.2): scuffs where the low faces down, on the shells and the drums
    Nl = rasterise_normals(A, T)
    down = _ss(-Nl[:, 1], 0.75, 0.95) * np.isin(fin, ('paint', 'oxide'))
    scuff = down * _ss(noise(P * np.array([0.35, 1.0, 1.0]), 1.6e-3, 37), 0.62, 0.78)
    chip = wear.copy()              # the coverage chips alone, for their stats (the scuffs, at most 0.55, are partial by
                                    # construction: counted in, they read as the chips' partial texels, C5a-2's check)
    wear = np.maximum(wear, 0.55 * scuff * paint)
    # compose: bright rings, wear, darks (C5c: by their coverage, 0..1; the per-texel masks are 0 or 1, as before)
    tb = R['titanium']
    bw_ = np.clip(bright, 0.0, 1.0)
    base = (1.0 - bw_)[:, None] * base + bw_[:, None] * tb['base']
    rough = (1.0 - bw_) * rough + bw_ * (tb['rough'] - 0.07)
    metal = (1.0 - bw_) * metal + bw_ * 1.0
    pw, ow = R['paint'], R['oxide']
    base = (1.0 - wear)[:, None] * base + wear[:, None] * pw['worn']
    rough = (1.0 - wear) * rough + wear * pw['worn_rough']
    metal = (1.0 - wear) * metal + wear * pw['worn_metal']
    base = (1.0 - wear_o)[:, None] * base + wear_o[:, None] * ow['worn']
    rough = (1.0 - wear_o) * rough + wear_o * ow['worn_rough']
    metal = (1.0 - wear_o) * metal + wear_o * ow['worn_metal']
    dw_ = np.clip(dark, 0.0, 1.0)
    base = base * (1.0 - 0.65 * dw_)[:, None]
    rough = (1.0 - dw_) * rough + dw_ * np.minimum(rough + 0.15, 0.9)
    rough += 0.10 * scuff
    # dirt: grime by MULTIPLY in the cavities (the body's rule: never add-then-threshold), lighter on the rubber
    dirt = (1.0 - _ss(cav, 0.55, 0.95)) * (0.75 + 0.25 * noise(P, 3.0e-3, 71))
    base *= (1.0 - np.where(fin == 'rubber', 0.15, 0.40) * dirt)[:, None]
    rough = np.clip(rough + 0.10 * dirt, 0.04, 1.0)
    diel = metal < 0.5
    base = np.where(diel[:, None], np.clip(base, 0.013, 0.87), np.clip(base, 0.0, 1.0))
    # the texture tier's height into the normal: finite differences within each island, in texel units along u / v
    Hm = np.zeros((size, size))
    Hm[ys, xs] = height
    Im = np.full((size, size), -1, np.int64)
    Im[ys, xs] = T['isl']
    dens_i = np.array([it['dens'] for it in A['isl']])
    tex_i = tex / dens_i[T['isl']]
    gx = np.zeros(n)
    gy = np.zeros(n)
    for dx, dy, gout, sgn in ((1, 0, gx, 1.0), (0, -1, gy, 1.0)):
        x1, y1 = np.clip(xs + dx, 0, size - 1), np.clip(ys + dy, 0, size - 1)
        x0, y0 = np.clip(xs - dx, 0, size - 1), np.clip(ys - dy, 0, size - 1)
        ok1 = Im[y1, x1] == T['isl']
        ok0 = Im[y0, x0] == T['isl']
        h1 = np.where(ok1, Hm[y1, x1], height)
        h0 = np.where(ok0, Hm[y0, x0], height)
        span = np.where(ok1 & ok0, 2.0, np.where(ok1 | ok0, 1.0, 1.0))
        gout[:] = (h1 - h0) / (span * tex_i)
    nd = np.column_stack([-gx, -gy, np.ones(n)])
    nrm = nrm_b / np.maximum(np.linalg.norm(nrm_b, axis=1, keepdims=True), 1e-9)
    nrm = nrm + np.column_stack([nd[:, 0], nd[:, 1], np.zeros(n)])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    # the maps (image order), every gutter grown from the covered texels (bake.dilate_all)
    img = lambda k: np.zeros((size, size, k))
    alb, nmp, orm, msk = img(3), img(3), img(3), img(4)
    alb[ys, xs] = base
    nmp[ys, xs] = nrm
    orm[ys, xs] = np.column_stack([ao, rough, metal])
    tint = (fin == 'paint').astype(np.float64) * (hmask == 0)
    msk[ys, xs] = np.column_stack([tint, np.zeros(n), emis, np.maximum(wear, wear_o)])
    cov4 = np.zeros((size, size, 4), np.float32)
    cov4[..., 3] = T['cov']
    dil, grown = BK.dilate_all(dict(normal=np.concatenate([nmp, T['cov'][..., None].astype(np.float64)], -1), alb=alb,
                                    orm=orm, msk=msk), 16)
    dil = dark_gutter(dil, base, T, size)       # C5-UV b: a dark texel's values fill GUTTER_DARK more of a shared gutter
    enc = lambda x: np.clip(x * 255.0 + 0.5, 0, 255).astype(np.uint8)
    # the shipped set: the canvas's bottom H rows (image order: row 0 is v = 1), where every island lies
    H_ = A.get('set', (size, size))[1]
    out = dict(albedo=enc(np.where(grown[..., None], dil['alb'], 0.05) ** (1.0 / 2.2))[size - H_:],
               normal=enc(np.where(grown[..., None], dil['normal'][..., :3], [0.0, 0.0, 1.0]) * 0.5 + 0.5)[size - H_:],
               orm=enc(np.where(grown[..., None], dil['orm'], [1.0, 0.6, 0.0]))[size - H_:],
               masks=enc(np.where(grown[..., None], dil['msk'], 0.0))[size - H_:])
    assert not T['cov'][:size - H_].any(), 'a covered texel above the set: the pack left its sheet'
    worn = (chip > 0.0) & paint
    st = dict(texels=int(n), paint=int(paint.sum()), wear_paint=float(((wear > 0.5) & paint).sum() / max(paint.sum(), 1)),
              wear_edge=float(((wear > 0.5) & paint & (expo > 0.3)).sum() / max((paint & (expo > 0.3)).sum(), 1)),
              wear_flat=float(((wear > 0.5) & paint & (expo <= 0.05)).sum() / max((paint & (expo <= 0.05)).sum(), 1)),
              chip_full=float(((chip >= 0.99) & paint).sum() / max(worn.sum(), 1)),
              chip_partial=float((worn & (chip < 0.99)).sum() / max(worn.sum(), 1)),
              chip_levels=int(len(np.unique(np.round(chip[worn] * COVER_SS * COVER_SS)))),
              scuffed=float(((0.55 * scuff * paint > chip) & (wear > 0.0) & paint).sum() / max(paint.sum(), 1)),
              oxide_chips=float(((wear_o > 0.5) & oxide).sum() / max(oxide.sum(), 1)),
              # C3b's G9 reading: the worn metal on FULLY worn texels (coverage >= 0.99)
              worn_metal_p50=float(np.median(metal[(wear >= 0.99) & paint])) if ((wear >= 0.99) & paint).any() else 0.0,
              ss=int(SS), sub_soft=float(CY.WEAR_SUB_SOFT), tau=float(tau),
              # C5-UV b: the thresholds over the texels as shown (instance_weights) and over the baked texels alone;
              # the paint and oxide worn past half, each texel weighted as shown
              tau_baked=float(tau_u), tau_oxide=float(tau_o), tau_oxide_baked=float(tau_ou),
              wear_paint_shown=float(((wear > 0.5) & paint) @ w_i[T['isl']] / max(paint @ w_i[T['isl']], 1e-9)),
              oxide_chips_shown=float(((wear_o > 0.5) & oxide) @ w_i[T['isl']] / max(oxide @ w_i[T['isl']], 1e-9)),
              # per stacked group: the share worn past half its instances would wear, its primary's own at the common
              # threshold, the group's threshold that gives its primary that share, the share it gives (weighted as
              # the instances, and over the primary's texels alone), the primary's texels (shown_wear)
              groups_paint={p_: list(v_) for p_, v_ in cal_p.items()},
              groups_oxide={p_: list(v_) for p_, v_ in cal_o.items()},
              heads=int((hmask > 0).sum()), bright=int((bright > 0).sum()), lamps=int((emis > 0).sum()),
              seconds=time.time() - t0)
    log(f'[cyborg_limb] material {size}^2 canvas, the {size} x {H_} set: {n:,} texels; paint {st["paint"]:,} (worn '
        f'{st["wear_paint"] * 100:.1f} %: edges {st["wear_edge"] * 100:.1f} %, flats {st["wear_flat"] * 100:.2f} %); the chip '
        f'mask by coverage (cyborg.py\'s {SS}x{SS} sub-samples, edge {CY.WEAR_SUB_SOFT:.2f} tau): of the texels the chips '
        f'touch {st["chip_full"] * 100:.1f} % full, {st["chip_partial"] * 100:.1f} % partial ({st["chip_levels"]} levels; '
        f'the oral scuffs apart, on {st["scuffed"] * 100:.1f} % of the paint), worn metal p50 {st["worn_metal_p50"]:.2f}; '
        f'oxide rims chipped {st["oxide_chips"] * 100:.2f} %; head texels {st["heads"]:,}, bright rings {st["bright"]:,}, '
        f'lamp texels {st["lamps"]}; {st["seconds"]:.1f}s')
    return out, st


def rasterise(A, values):
    """a per-vertex quantity (n, k) interpolated at every texel centre a triangle covers (barycentric in UV, numpy):
    (size, size, k) in image order, NaN where no triangle"""
    L = A['L']
    size = A['size']
    vals = np.asarray(values, np.float64).reshape(len(L['V']), -1)
    out = np.full((size, size, vals.shape[1]), np.nan)
    UVt = np.column_stack([L['UV'][:, 0] * size - 0.5, (1.0 - L['UV'][:, 1]) * size - 0.5])   # texel centres at ints
    for f in L['F']:
        p = UVt[f]
        x0, x1 = int(max(0, math.floor(p[:, 0].min()))), int(min(size - 1, math.ceil(p[:, 0].max())))
        y0, y1 = int(max(0, math.floor(p[:, 1].min()))), int(min(size - 1, math.ceil(p[:, 1].max())))
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(d) < 1e-12:
            continue
        l0 = ((p[1, 1] - p[2, 1]) * (gx - p[2, 0]) + (p[2, 0] - p[1, 0]) * (gy - p[2, 1])) / d
        l1 = ((p[2, 1] - p[0, 1]) * (gx - p[2, 0]) + (p[0, 0] - p[2, 0]) * (gy - p[2, 1])) / d
        l2 = 1.0 - l0 - l1
        m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not m.any():
            continue
        out[gy[m], gx[m]] = l0[m, None] * vals[f[0]] + l1[m, None] * vals[f[1]] + l2[m, None] * vals[f[2]]
    return out


def rasterise_normals(A, T):
    """the low's interpolated normal at each covered texel: the oral-side test"""
    Nm = rasterise(A, A['L']['N'])
    out = Nm[T['ys'], T['xs']]
    out = np.where(np.isfinite(out), out, [0.0, 1.0, 0.0])
    out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
    return out


# ============================================================================================ rig and export
JOINT_NAMES = tuple(f'arm_{k:02d}' for k in range(J0, N_JOINTS))     # the asset's joints (C5b maps arm{j}_kk onto them)


def skeleton(chain, des=None):
    """the asset's bind skeleton: joints J0..23 on the straight chain, each frame its bone's CHORD frame (x along the
    arm, y aboral, z = x cross y): what solveArm aims, so C5b maps each onto the octopus's bone by its chordQ; then the
    helper joints (C5a-2, helper_joints: crosses, turning shells, rods, hose crests) at their knuckles' pivots, their
    rest frames the same (the runtime turns them by their rules each frame, pose_joints)"""
    from . import rig as RG
    sk = RG.Skeleton()
    prev = None
    for k in range(J0, N_JOINTS):
        sk.add(JOINT_NAMES[k - J0], prev, [chain['x'][k], 0.0, 0.0], np.eye(3))
        prev = JOINT_NAMES[k - J0]
    for h_ in (des['helpers'] if des is not None else []):
        sk.add(h_['name'], h_['parent'], [chain['x'][h_['k']], 0.0, 0.0], np.eye(3))
    return sk


HELPER_RULES = dict(
    cross='local rotation Ry(yaw_k): the cardan cross turns with the knuckle\'s yaw about the parent\'s yaw pin',
    shell='local rotation Rx(-roll_k): the segment\'s shell, pitch yoke and actuator turn back by the knuckle\'s roll '
          'on the roll ring at the segment\'s distal end (the next yoke stays on the bone)',
    rod='local translation (lc_k sin(pitch_k), 0, 0): the actuator\'s rod slides with its crank on the pitch axle',
    crest='local rotation Ry(yaw_k / 2): the hose arch\'s crest turns half the knuckle\'s yaw')


def radius_table(A):
    """the machine's reach below its centreline at each joint (the per-arm radius table, A.9 decision 5): the lowest
    point of the low within half a segment of each joint, over the flesh's nominal radius there; the runtime's ground
    line reads it at C5b in place of r4's taper"""
    L, x = A['L'], A['chain']['x']
    out = []
    fl = A['des']['flange']
    for k in range(CUT, N_JOINTS):
        half = 0.5 * float(A['chain']['seg'][min(k, N_JOINTS - 2)])
        lo_x, hi_x = x[k] - half, x[k] + half
        if k == CUT:
            # C5c (the lead's decision 6): joint cut's reach takes in the whole soft roll (it sits 19.8-25.9 mm past
            # joint 7, half outside joint 8's half segment: the flange's level left its lowest point 0.9 mm in the sand)
            lo_x = min(lo_x, x[J0] + fl['roll_x'] - 0.5 * DESIGN['roll'])
        ymin = float(L['V'][(L['V'][:, 0] > lo_x) & (L['V'][:, 0] < hi_x), 1].min())    # the hose rides on top: never lowest
        out.append(dict(joint=k, oral=-ymin, flesh_r=float(A['chain']['r'][k]), ratio=-ymin / float(A['chain']['r'][k])))
    return out


def export_glb(path, A, maps, sock_extra=None):
    """the mech tentacle as a SKINNED glb: one mesh, one material (base, normal, ORM; the masks in the volume slot as the
    props carry theirs, extras.bestiary 'cyborg'), joints arm_07..arm_23 on the straight bind, every rigid piece one
    joint at weight 1, the band and the hose arches two (the listed exemption, A.8's G10 row), socket_arm_tip (kind
    limb_tip) on arm_23 at the gripper boss's face; the chain record, the radius table and the design in the extras"""
    from . import gltf
    from . import rig as RG
    from ..remix import slots as SL     # (L1, KIT_PORT §5.4) socket_arm_tip's full MOUNT dims
    chain, des, L = A['chain'], A['des'], A['L']
    sk = skeleton(chain, des)
    g = gltf.GLB()
    t_base = g.texture(maps['albedo'], fmt='jpeg', quality=94)
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='png')
    t_msk = g.texture(maps['masks'], fmt='png')
    mat = g.material('mech_tentacle', base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='cyborg', part='mech_tentacle', masks=t_msk,
        masks_channels='R primary tint region (the white paint), G accent region, B emissive (the motor cans\' status '
                       'lamps), A wear',
        rows='forge/cyborg.py row_values: cyb_paint (house white), cyb_titanium, cyb_steel black_oxide / bare, '
             'cyb_gasket'))
    skin, jnodes = g.skeleton(sk)
    J = L['joints']                                  # joint indices into des['joints'] (the skeleton's order)
    W = L['weights']
    J4 = np.zeros((len(J), 4), np.int64)
    W4 = np.zeros((len(J), 4), np.float64)
    J4[:, :2] = J
    W4[:, :2] = W
    # one joint where the second weight is zero (rigid): both slots the same bone, the second at 0
    W4 /= W4.sum(1, keepdims=True)
    mesh = g.mesh('mech_tentacle', L['V'], L['N'], L['TAN'], L.get('UV_tex', L['UV']), [(L['F'], mat)], joints=J4,
                  weights=W4)
    root = g.node('mech_tentacle', mesh=mesh, skin=skin, root=True)
    tip = des['segs'][N_JOINTS - 1]['L']
    rt_ = float(radius_at(chain, chain['x'][N_JOINTS - 1] + body_nodes(chain, des, N_JOINTS - 1)['x1']))
    g.node('socket_arm_tip', T=[tip, 0.0, 0.0], parent=jnodes[N_JOINTS - 1 - J0], extras=dict(slot=dict(
        kind='limb_tip', interface='mount', joint=JOINT_NAMES[-1], frame=dict(normal=[1.0, 0.0, 0.0],
                                                                                tangent=[0.0, 1.0, 0.0]),
        dims=SL.mount_dims(0.62 * rt_), **(sock_extra or {}))))
    rt = radius_table(A)
    ext = dict(bestiary=dict(
        part='mech_tentacle', family='mech_tentacle', fits='tentacle (a chain kind: the octopus arm it replaces, from '
                                                           'its cut to the tip; remix/slots.py)',
        units='m', up='+Y', forward='+X (along the arm)', cut=CUT, joints=list(JOINT_NAMES),
        bind_x=[round(float(v), 6) for v in chain['x'][J0:]], seg=[round(float(v), 6) for v in chain['seg'][J0:]],
        flesh_r=[round(float(v), 6) for v in chain['r'][J0:]], ring=dict(s=chain['ring']['s'], x=chain['ring']['x'],
                                                                        x_before=chain['ring']['x_before']),
        chord_frames='every joint frame is its bone\'s chord frame (x the chord to the next joint, y aboral): '
                     'C5b maps arm{j}_kk by the octopus bind\'s chordQ (cyborg_limb.arm_chain chordB)',
        radius_table=[dict(joint=r['joint'], oral=round(r['oral'], 6), ratio=round(r['ratio'], 4)) for r in rt],
        triangles=int(len(L['F'])), px_per_m=round(float(A['px']), 1), texture=list(A.get('set', (A['size'],) * 2)),
        two_bone='the band (joint 8) and the hose arches (each across its knuckle, or its crest joint): A.8 G10\'s listed '
                 'exemption',
        cardan=dict(knuckles=list(CARDAN), angles='per cardan knuckle k, of arm_k\'s local rotation R (the child\'s chord '
                                                    'frame in the parent\'s): R = Ry(yaw) Rz(pitch) Rx(roll), yaw = '
                                                    'atan2(-R[2,0], R[0,0]), pitch = asin(R[1,0]), roll = atan2(M[2,1], '
                                                    'M[1,1]) with M = (Ry(yaw) Rz(pitch))^T R (cyborg_limb.cardan_angles)',
                    rings=sorted(int(k) for k in des['ring']), actuators=sorted(int(k) for k in des['act']),
                    crests=sorted(int(k) for k in des['crest']),
                    crank_lc={str(k): round(float(des['kn'][k]['lc']), 6) for k in sorted(des['act'])}),
        helpers=[dict(name=h_['name'], parent=h_['parent'], kind=h_['kind'], knuckle=int(h_['k']),
                      rule=HELPER_RULES[h_['kind']]) for h_ in des['helpers']],
        helpers_note='C5b: after solveArm sets arm_07..arm_23, the runtime sets every helper joint\'s local transform by '
                     'its rule each frame (cyborg_limb.pose_joints is the reference); a helper left at rest leaves its '
                     'pieces on the bind (the crosses, rods and shells would not follow the knuckles)'))
    return g.save(path, extras=ext)


# ============================================================================================ the motion gates
def rot_y(a):
    """a yaw turn about +y (taking +x toward -z for a > 0: yaw_pitch's sign)"""
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def curl_rels(lim, t, side=1.0, reach=1.0):
    """a CURL: every joint 8..23 yawed toward one side by `reach` of its rest motion's largest yaw (joint 23, never
    moved by the runtime, by half its 45 deg wrist), all at once with a smooth ramp t in [0, 1]: (24, 3, 3) per joint
    (index = joint; 0..J0 identity)"""
    R = np.tile(np.eye(3), (N_JOINTS, 1, 1))
    for k in range(CUT, N_JOINTS):
        amax = math.radians(lim['yaw_max'][k - 1]) if k < N_JOINTS - 1 else math.radians(0.5 * DESIGN['yaw_tip'])
        R[k] = rot_y(side * reach * amax * t)
    return R


def pose_from_rels(chain, rels):
    """group transforms (pos (24, 3), F (24, 3, 3)) for relative rotations rels[k] (joint k's child in its parent),
    the chain starting at joint J0 at the origin along +x"""
    pos = np.zeros((N_JOINTS, 3))
    F = np.tile(np.eye(3), (N_JOINTS, 1, 1))
    for k in range(J0 + 1, N_JOINTS):
        pos[k] = pos[k - 1] + F[k - 1] @ np.array([chain['seg'][k - 1], 0.0, 0.0])
        F[k] = F[k - 1] @ rels[k]
    return pos, F


def pose_from_motion(chain, pos_t, F_t):
    """group transforms from solve_arm's output at one time: bones J0..22 their chord frames, bone 23 at rest in 22"""
    pos = np.array(pos_t, np.float64)
    F = np.concatenate([np.array(F_t, np.float64), (F_t[-1] @ chain['tip_rel'])[None]], 0)
    return pos, F


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def pose_joints(chain, des, pos, F):
    """every skeleton joint's world transform (des['joints'] order) for one pose of the bones (pos (24, 3), F (24, 3,
    3): their chord frames; J0..23 read): the bones as given, each helper by its rule (helper_joints; HELPER_RULES)
    from the cardan angles of its knuckle's relative rotation F[k-1]^T F[k]: cross F[k-1] Ry(yaw), shell F[k]
    Rx(-roll), rod its shell slid by lc sin(pitch) along its x, crest F[k-1] Ry(yaw / 2), all at the pivot pos[k].
    Returns P (n, 3), R (n, 3, 3) and the rest origins X (n,) (each joint's x on the straight bind)"""
    names = des['joints']
    P, R, X = np.zeros((len(names), 3)), np.zeros((len(names), 3, 3)), np.zeros(len(names))
    ang = {}
    for i, nm in enumerate(names):
        k, kind = body_k(nm), body_kind(nm)
        X[i] = chain['x'][k]
        if kind == 'bone':
            P[i], R[i] = pos[k], F[k]
            continue
        if k not in ang:
            ang[k] = [float(v) for v in cardan_angles(F[k - 1].T @ F[k])]
        yw, pt, rl = ang[k]
        P[i] = pos[k]
        if kind == 'cross':
            R[i] = F[k - 1] @ rot_y(yw)
        elif kind == 'crest':
            R[i] = F[k - 1] @ rot_y(0.5 * yw)
        elif kind == 'shell':
            R[i] = F[k] @ rot_x(-rl)
        elif kind == 'rod':
            R[i] = F[k] @ rot_x(-rl) if k in des['ring'] else F[k]
            P[i] = pos[k] + R[i] @ np.array([des['kn'][k]['lc'] * math.sin(pt), 0.0, 0.0])
    return P, R, X


def surface_samples(A, k, step=0.35e-3, near=None):
    """points on a rigid BODY's TRUE surface (its local Program, bores and all), from its low's triangles subdivided to
    ~step and projected along the low's normals; near(points_local) -> mask keeps only the knuckle's neighbourhood. k:
    a body's name (or an int bone); its frame's origin is its joint's x"""
    from . import sdf
    body = bone_name(k) if isinstance(k, (int, np.integer)) else k
    prog = group_program(A['chain'], A['des'], body)
    xk = A['chain']['x'][body_k(body)]
    pts, nrm = [], []
    for it in A['isl']:
        if it['body'] != body or REGIONS[it['region']] in ('band', 'hose'):
            continue
        V = it['V'] - np.array([xk, 0.0, 0.0])
        for f in it['F']:
            p = V[f]
            e = max(np.linalg.norm(p[1] - p[0]), np.linalg.norm(p[2] - p[1]), np.linalg.norm(p[0] - p[2]))
            m = max(1, int(math.ceil(e / step)))
            ii, jj = np.meshgrid(np.arange(m + 1), np.arange(m + 1))
            sel = ii + jj <= m
            a_, b_ = ii[sel] / m, jj[sel] / m
            q = p[0] + a_[:, None] * (p[1] - p[0]) + b_[:, None] * (p[2] - p[0])
            fn = np.cross(p[1] - p[0], p[2] - p[0])
            fn /= max(np.linalg.norm(fn), 1e-20)
            pts.append(q)
            nrm.append(np.tile(fn, (len(q), 1)))
    P = np.concatenate(pts)
    N = np.concatenate(nrm)
    if near is not None:
        m = near(P)
        P, N = P[m], N[m]
    Q, st = prog.project(P, N, maxd=3.5e-3)
    ok = st < 2
    return Q[ok], prog


def joint_set(des, k):
    """the bodies around knuckle k for the clash replay, each (name, role): the parent's bone P (its distal knuckle's
    pieces, and its shell unless that turns on a ring), the parent's turning shell PS (a ring segment), the cross X,
    the child's shell body C (the tongue or the pitch yoke, the actuator), the rod ROD"""
    out = [(bone_name(k - 1), 'P')]
    if (k - 1) in des['ring']:
        out.append((f'arm_{k - 1:02d}_shell', 'PS'))
    if k in CARDAN:
        out.append((f'arm_{k:02d}_cross', 'X'))
    out.append((shell_body(des, k), 'C'))
    if k in des['act']:
        out.append((f'arm_{k:02d}_rod', 'ROD'))
    return out


def rel_poses(chain, des, k, R_prev, R_k):
    """per sample, every body of joint_set(k) in the parent bone's frame (origin at joint k - 1): {name: (rotation (n,
    3, 3), translation (n, 3))}; R_prev the previous knuckle's relative rotation at the same frame (the parent
    segment's roll ring), R_k this knuckle's"""
    R_k = np.asarray(R_k, np.float64)
    n = len(R_k)
    piv = np.broadcast_to(np.array([float(chain['seg'][k - 1]), 0.0, 0.0]), (n, 3))
    yw, pt, rl = cardan_angles(R_k)
    out = {bone_name(k - 1): (np.broadcast_to(np.eye(3), (n, 3, 3)), np.zeros((n, 3)))}
    if (k - 1) in des['ring']:
        _, _, rl_p = cardan_angles(np.asarray(R_prev, np.float64))
        out[f'arm_{k - 1:02d}_shell'] = (_rx_n(-rl_p), np.zeros((n, 3)))
    if k in CARDAN:
        out[f'arm_{k:02d}_cross'] = (_ry_n(yw), piv)
    Rc = _ry_n(yw) @ _rz_n(pt) if k in des['ring'] else R_k
    out[shell_body(des, k)] = (Rc, piv)
    if k in des['act']:
        out[f'arm_{k:02d}_rod'] = (Rc, piv + Rc[:, :, 0] * (des['kn'][k]['lc'] * np.sin(pt))[:, None])
    return out


def clash_gate(A, rel_sets, step=0.35e-3, chunk=8_000_000, log=print, joints=None):
    """THE KNUCKLE REPLAY (§4.4.5; A.7 U14's clash probe), C5a-2: at every knuckle k every PAIR of its bodies (joint_set:
    the parent's bone, its turning shell, the cross, the child's shell body, the rod), for every sample in rel_sets[k] =
    (R_prev, R_k) (the previous and this knuckle's relative rotations at the same arm-frame), each body posed by its
    rule (rel_poses); one body's surface points carried into the other's frame and evaluated in its field (bores and
    all: a trunnion in its bore reads the running clearance), both ways: the least distance (> 0: no contact; the rigid
    pieces never meet). Returns rows per knuckle (its least gap, the pair, every pair's least, per sample); joints: a
    subset of the knuckles"""
    chain, des = A['chain'], A['des']
    rows = []
    for k in (range(CUT, N_JOINTS) if joints is None else joints):
        R_prev, R_k = (np.asarray(a, np.float64) for a in rel_sets[k])
        n = len(R_k)
        Lp = float(chain['seg'][k - 1])
        K = des['kn'].get(k)
        reach = (K['a_c'] + 0.45 * float(des['segs'][k]['L'])) if K is not None else 0.025
        st_k = step if K is None or K['kind'] != 'cardan' else float(np.clip(0.2 * K['b'], 0.08e-3, step))
        bodies = joint_set(des, k)
        poses = rel_poses(chain, des, k, R_prev, R_k)
        samp = {}
        for nm, role in bodies:
            if role in ('P', 'PS'):
                near = lambda P: P[:, 0] > Lp - max(0.03, 0.6 * Lp)
            elif role == 'C':
                near = lambda P: P[:, 0] < reach
            else:
                near = None
            samp[nm] = surface_samples(A, nm, st_k, near=near)
        per = np.full(n, np.inf)
        pairs = {}
        best = (np.inf, '', 0)
        names = [nm for nm, _ in bodies]
        for ia in range(len(names)):
            for ib in range(ia + 1, len(names)):
                a_, b_ = names[ia], names[ib]
                dmin = np.inf
                for src, dst in ((b_, a_), (a_, b_)):
                    Ps, _ = samp[src]
                    _, prog_d = samp[dst]
                    if not len(Ps):
                        continue
                    Rs, ts_ = poses[src]
                    Rd, td = poses[dst]
                    # one transform per sample, the source's frame straight into the destination's: Rd^T (Rs p + ts -
                    # td), in float32 (the field's own precision) by a BLAS matmul
                    M = np.einsum('rji,rjk->rki', Rd, Rs).astype(np.float32)             # (Rd^T Rs)^T
                    o_ = np.einsum('rji,rj->ri', Rd, ts_ - td).astype(np.float32)
                    P32 = np.ascontiguousarray(Ps, np.float32)
                    ch = max(1, chunk // max(len(Ps), 1))
                    for i0 in range(0, n, ch):
                        sl = slice(i0, min(n, i0 + ch))
                        Q = np.matmul(P32[None], M[sl]) + o_[sl][:, None]
                        d = prog_d.eval(Q.reshape(-1, 3)).reshape(len(Q), len(Ps))
                        dm = d.min(1)
                        per[sl] = np.minimum(per[sl], dm)
                        j = int(np.argmin(dm))
                        if dm[j] < dmin:
                            dmin = float(dm[j])
                        if dm[j] < best[0]:
                            best = (float(dm[j]), f'{src} in {dst}', i0 + j)
                pairs[f'{a_} / {b_}'] = dmin * 1e3
        yw, pt, rl = cardan_angles(R_k[best[2]:best[2] + 1]) if n else (np.zeros(1),) * 3
        Y, Pi, Ro = cardan_angles(R_k)
        rows.append(dict(joint=k, n_rot=int(n), min_mm=best[0] * 1e3, side=best[1], at_yaw=float(np.degrees(yw[0])),
                         at_pitch=float(np.degrees(pt[0])), at_roll=float(np.degrees(rl[0])), pairs=pairs, per=per,
                         yaw_max=float(np.degrees(np.abs(Y).max())), pitch_max=float(np.degrees(np.abs(Pi).max())),
                         roll_max=float(np.degrees(np.abs(Ro).max())), ok=best[0] > 0.0,
                         n_pts={nm: int(len(samp[nm][0])) for nm in names}))
        log(f'   knuckle {k:2d}: {n:5d} samples (|yaw| <= {rows[-1]["yaw_max"]:.1f}, |pitch| <= {rows[-1]["pitch_max"]:.1f}, '
            f'|roll| <= {rows[-1]["roll_max"]:.1f} deg), {len(names)} bodies, {sum(rows[-1]["n_pts"].values())} surface '
            f'points: least gap {best[0] * 1e3:+.3f} mm ({best[1]}, yaw {rows[-1]["at_yaw"]:+.1f} pitch '
            f'{rows[-1]["at_pitch"]:+.1f} roll {rows[-1]["at_roll"]:+.1f}) -> {"clear" if best[0] > 0 else "CLASH"}; '
            + ', '.join(f'{p_.replace("arm_", "")} {v_:+.3f}' for p_, v_ in pairs.items()))
    return rows


def hose_samples(A, n_around=12, step=0.4e-3):
    """points on the bundle's TRUE surface (its path's tube) and their two (bone, weight) pairs"""
    H = A['des']['hose']
    P, r, w = H['P'], H['r'], H['w']
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    T = np.gradient(P, s, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    Z = np.array([0.0, 0.0, 1.0])
    out, ws = [], []
    ang = np.linspace(0.0, TAU, n_around, endpoint=False)
    for i in range(len(P)):
        e2 = np.cross(T[i], Z)
        e2 /= np.linalg.norm(e2)
        e1 = np.cross(e2, T[i])
        out.append(P[i] + r[i] * (np.cos(ang)[:, None] * e2 + np.sin(ang)[:, None] * e1))
        ws.append(np.repeat(w[i][None], n_around, 0))
    return np.concatenate(out), np.concatenate(ws)


def hose_gate(A, rel_sets, log=print, joints=None):
    """the HOSE gate per knuckle k: every surface point of the arch over k, skinned as the glb's weights are (on its two
    clamps' bodies, and over a crest knuckle through the crest joint: linear blend skinning, the runtime's), against
    every body of the knuckle (joint_set), for every sample in rel_sets[k] = (R_prev, R_k); points rigid on a body are
    not tested against it (the clamp holds them). And its SLACK: the arch's rest length between its clamps' faces
    against their farthest separation over the samples (> 0: never taut)"""
    chain, des = A['chain'], A['des']
    Ph, Wh = hose_samples(A)
    H = des['hose']
    cl = {c['k']: c for c in des['clamps']}
    J = {n_: i for i, n_ in enumerate(des['joints'])}
    rows = []
    for kc in (range(CUT, N_JOINTS) if joints is None else joints):
        kp = kc - 1
        R_prev, R = (np.asarray(a, np.float64) for a in rel_sets[kc])
        n = len(R)
        xp = chain['x'][kp]
        piv = np.array([chain['seg'][kp], 0.0, 0.0])
        poses = rel_poses(chain, des, kc, R_prev, R)
        jpa = bone_name(J0) if kc == CUT else shell_body(des, kp)     # the parent clamp's (the fitting's) body
        jch = shell_body(des, kc)
        use = {J[jpa]: jpa, J[jch]: jch}
        if kc in des['crest']:
            cr = f'arm_{kc:02d}_crest'
            use[J[cr]] = cr
            yw_, _, _ = cardan_angles(R)
            poses[cr] = (_ry_n(0.5 * yw_), np.broadcast_to(piv, (n, 3)))
        b0, b1 = Wh[:, 0, 0].astype(int), Wh[:, 1, 0].astype(int)
        w0, w1 = Wh[:, 0, 1], Wh[:, 1, 1]
        held = (np.isin(b0, list(use)) | (w0 < 1e-9)) & (np.isin(b1, list(use)) | (w1 < 1e-9))
        moving = ~((b0 == J[jpa]) & (w0 > 1.0 - 1e-9))                  # not rigid on the parent's clamp
        m = held & (np.abs(Ph[:, 0] - chain['x'][kc]) < 0.6 * (chain['seg'][kp] + chain['seg'][min(kc, N_JOINTS - 2)]))
        m &= moving | (np.abs(Ph[:, 0] - chain['x'][kc]) < 0.3 * chain['seg'][kp])
        Pm, B0, B1, W0, W1 = Ph[m], b0[m], b1[m], w0[m], w1[m]
        X0 = np.array([chain['x'][body_k(des['joints'][j])] for j in B0])
        X1 = np.array([chain['x'][body_k(des['joints'][j])] for j in B1])
        tests = [(nm_, group_program(chain, des, nm_), J.get(nm_, -1)) for nm_, _ in joint_set(des, kc)]
        dmin = np.inf
        at = 0
        per = np.full(n, np.inf)
        chunk = max(1, 4_000_000 // max(len(Pm), 1))
        f32 = lambda a: np.asarray(a, np.float32)
        for i0 in range(0, n, chunk):
            sl = slice(i0, min(n, i0 + chunk))
            Q = np.zeros((sl.stop - sl.start, len(Pm), 3), np.float32)
            for Bj, Wj, Xj in ((B0, W0, X0), (B1, W1, X1)):
                for j_ in np.unique(Bj):
                    mj = (Bj == j_) & (Wj > 0.0)
                    if not mj.any():
                        continue
                    Rj, tj = poses[use[j_]]                  # the joint's pose in the parent bone's frame
                    loc = f32(Pm[mj] - np.column_stack([Xj[mj], np.zeros(mj.sum()), np.zeros(mj.sum())]))
                    Q[:, mj] += f32(Wj[mj])[None, :, None] * (np.matmul(loc[None], f32(np.swapaxes(Rj[sl], 1, 2)))
                                                              + f32(tj[sl])[:, None])
            d_all = np.full((sl.stop - sl.start, len(Pm)), np.inf, np.float32)
            for nm_, prog_, jn in tests:
                rigid = ((B0 == jn) & (W0 > 1.0 - 1e-9)) | ((B1 == jn) & (W1 > 1.0 - 1e-9))
                Rd, td = poses[nm_]
                Qd = np.matmul(Q - f32(td[sl])[:, None], f32(Rd[sl]))                      # Rd^T (Q - td), rows
                d = prog_.eval(Qd.reshape(-1, 3)).reshape(len(Qd), -1)
                d_all = np.minimum(d_all, np.where(rigid[None], np.inf, d))
            per[sl] = d_all.min(1)
            j = int(np.argmin(per[sl]))
            if per[sl][j] < dmin:
                dmin, at = float(per[sl][j]), sl.start + j
        # slack: the centreline between the two clamps' facing ends, each carried by its clamp's body
        ca, cb = (cl.get(kp), cl.get(kc))
        if ca is None:                                   # joint 8: from the fitting's exit
            xa_, ya_ = H['stations'][0]['x'], H['stations'][0]['y']
        else:
            xa_, ya_ = ca['x'] + 0.5 * ca['L'], ca['y']
        xb_, yb_ = cb['x'] - 0.5 * cb['L'], cb['y']
        sel = (H['P'][:, 0] >= xa_ - 1e-6) & (H['P'][:, 0] <= xb_ + 1e-6)
        Pa = H['P'][sel]
        L_arch = float(np.linalg.norm(np.diff(Pa, axis=0), axis=1).sum()) if len(Pa) > 1 else 0.0
        Ra, ta = poses[jpa]
        Rb_, tb = poses[jch]
        A_ = np.einsum('rij,j->ri', Ra, np.array([xa_ - xp, ya_, 0.0])) + ta
        B_ = np.einsum('rij,j->ri', Rb_, np.array([xb_ - chain['x'][kc], yb_, 0.0])) + tb
        chord = np.linalg.norm(B_ - A_, axis=1)
        rest = float(np.linalg.norm(np.array([xb_ - xa_, yb_ - ya_, 0.0])))
        yw, pt, rl = cardan_angles(R[at:at + 1])
        rows.append(dict(joint=kc, n_rot=int(n), n_pts=int(len(Pm)), min_mm=dmin * 1e3, at_yaw=float(np.degrees(yw[0])),
                         at_pitch=float(np.degrees(pt[0])), arch_mm=L_arch * 1e3, chord_rest_mm=rest * 1e3,
                         chord_max_mm=float(chord.max()) * 1e3, chord_min_mm=float(chord.min()) * 1e3,
                         slack_mm=(L_arch - float(chord.max())) * 1e3, ok=dmin > -0.05e-3 and L_arch > chord.max(),
                         per=per, crest=kc in des['crest']))
        r_ = rows[-1]
        log(f'   hose over {kc:2d}: {len(R):5d} rotations, {len(Pm)} points: least gap {r_["min_mm"]:+.3f} mm (yaw '
            f'{r_["at_yaw"]:+.1f} pitch {r_["at_pitch"]:+.1f}); arch {r_["arch_mm"]:.2f} mm over a chord of '
            f'{r_["chord_rest_mm"]:.2f} at rest, {r_["chord_min_mm"]:.2f}-{r_["chord_max_mm"]:.2f} in motion: slack '
            f'{r_["slack_mm"]:+.2f} mm -> {"ok" if r_["ok"] else "FAIL"}')
    return rows


def video_motion(A, fps=30, rest_s=8.0, curl_s=5.0, seeds=range(1, 17), arms=range(8)):
    """the motion video's clip: the REST MOTION of the (seed, arm) that TILTS most at the distal knuckles 16-22 within
    30 s (the largest pitch plus roll there at one moment, cardan_angles; C5a-2, the lead's call 6: C5a's clip, chosen
    for its coils, tilted 2.4 deg at most and hid the clevises' flaw), its 8 s window around that moment (the runtime's
    solveArm port), then a CURL (every joint yawed to its rest maximum and back, one side then the other: the hose's
    loops at the largest yaws). Returns frames [dict(pos (24, 3), F (24, 3, 3), kind, t)] in the asset's view frame
    (joint J0 at the origin at t = 0, the arm's base chord along +x, y up), per joint the relative rotations of every
    frame (rels[k] (n, 3, 3)) and the clip's record"""
    from . import gltf
    chain, lim = A['chain'], A['lim']
    Wn = glb_worlds(gltf.read(os.path.join(OCTOPUS_DIR, 'octopus.glb'))['json'])
    ts = np.arange(0.0, 30.0, 0.1)
    best = None
    for seed in seeds:
        for j in arms:
            Pb = np.stack([Wn[f'arm{j}_{k:02d}'][:3, 3] for k in range(N_JOINTS)])
            _, F = solve_arm(Pb, ts, j, seed)
            Rr = rel_rotations(F, chain['tip_rel'])
            _, pt, rl = cardan_angles(Rr[:, 15:22])
            sc_t = np.degrees(np.abs(pt).max(1) + np.abs(rl).max(1))
            i_ = int(np.argmax(sc_t))
            if best is None or sc_t[i_] > best[0]:
                best = (float(sc_t[i_]), seed, j, Pb, float(ts[i_]), float(np.degrees(np.abs(pt[i_]).max())),
                        float(np.degrees(np.abs(rl[i_]).max())))
    _, seed, j, Pb, t_peak, p_peak, r_peak = best
    t0_ = max(0.0, min(t_peak - 0.5 * rest_s, 30.0 - rest_s))
    tt = t0_ + np.arange(int(round(rest_s * fps))) / fps
    pos, F = solve_arm(Pb, tt, j, seed)
    base = pos[0, J0].copy()
    d0 = F[0, J0][:, 0].copy()
    d0[1] = 0.0
    d0 /= np.linalg.norm(d0)
    Ry = np.array([[d0[0], 0.0, d0[2]], [0.0, 1.0, 0.0], [-d0[2], 0.0, d0[0]]])      # d0 -> +x
    frames = []
    for i in range(len(tt)):
        p_, F_ = pose_from_motion(chain, pos[i], F[i])
        p_ = (p_ - base) @ Ry.T
        F_ = np.einsum('ij,kjl->kil', Ry, F_)
        frames.append(dict(pos=p_, F=F_, kind='rest', t=float(tt[i])))
    # the curl, from the rest clip's last pose (the flange held where it was): each joint's yaw blends from its rest
    # value to the curl's target (its rest motion's largest yaw, toward one side) and back, then to the other side and
    # back; its pitch eases out with the curl and back in
    pe, Fe = frames[-1]['pos'], frames[-1]['F']
    y_rest = np.zeros(N_JOINTS)
    p_rest = np.zeros(N_JOINTS)
    for k in range(J0 + 1, N_JOINTS):
        yw, pt, _ = yaw_pitch(Fe[k - 1].T @ Fe[k])
        y_rest[k], p_rest[k] = float(yw), float(pt)
    tgt = np.zeros(N_JOINTS)
    for k in range(CUT, N_JOINTS):
        tgt[k] = math.radians(lim['yaw_max'][k - 1]) if k < N_JOINTS - 1 else math.radians(0.5 * DESIGN['yaw_tip'])
    rz = lambda a: np.array([[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]])
    nc = int(round(curl_s * fps))
    for i in range(nc):
        u = (i + 1) / nc
        ph = math.sin(TAU * u)                       # 0 -> +1 -> 0 -> -1 -> 0: one side, then the other
        a = abs(ph) ** 0.8
        side = 1.0 if ph >= 0.0 else -1.0
        rels = np.tile(np.eye(3), (N_JOINTS, 1, 1))
        for k in range(J0 + 1, N_JOINTS):
            yk = (1.0 - a) * y_rest[k] + a * side * tgt[k] if k >= CUT else y_rest[k]
            rels[k] = rot_y(yk) @ rz((1.0 - a) * p_rest[k])
        p_, F_ = pose_from_rels(chain, rels)
        p_ = np.einsum('ij,kj->ki', Fe[J0], p_) + pe[J0]
        F_ = np.einsum('ij,kjl->kil', Fe[J0], F_)
        frames.append(dict(pos=p_, F=F_, kind='curl', t=float(u)))
    rels = {}
    for k in range(J0 + 1, N_JOINTS):
        rels[k] = np.stack([fr['F'][k - 1].T @ fr['F'][k] for fr in frames])
    return frames, rels, dict(seed=seed, arm=j, t0=t0_, t_peak=t_peak, pitch_peak=p_peak, roll_peak=r_peak)


def posed_mesh(A, pos, F, extra=None):
    """the low posed: every vertex by linear blend skinning of its (up to) two joints, the bones and the helper joints
    posed by their rules (pose_joints: the runtime's, C5b): V (n, 3), N (n, 3), TAN (n, 4)"""
    L = A['L']
    Pj, Rj, Xj = pose_joints(A['chain'], A['des'], pos, F)
    V, N, Tn = L['V'], L['N'], L['TAN'][:, :3]
    J, W = L['joints'], L['weights']
    Vo = np.zeros_like(V)
    No = np.zeros_like(V)
    To = np.zeros_like(V)
    for c in range(2):
        j = J[:, c]
        w = W[:, c:c + 1]
        Fj = Rj[j]
        loc = V - np.column_stack([Xj[j], np.zeros(len(j)), np.zeros(len(j))])
        Vo += w * (np.einsum('nij,nj->ni', Fj, loc) + Pj[j])
        No += w * np.einsum('nij,nj->ni', Fj, N)
        To += w * np.einsum('nij,nj->ni', Fj, Tn)
    No /= np.maximum(np.linalg.norm(No, axis=1, keepdims=True), 1e-12)
    To /= np.maximum(np.linalg.norm(To, axis=1, keepdims=True), 1e-12)
    return Vo, No, np.column_stack([To, L['TAN'][:, 3]])


def hose_program(chain, des, prog=None, offset=(0.0, 0.0, 0.0)):
    """the bundle as one SWEEP along its path (asset frame), its end rounded by the sweep's end cap"""
    from . import sdf
    prog = prog or sdf.Program()
    H = des['hose']
    P = H['P'] + np.asarray(offset, np.float64)
    N = np.tile([0.0, 0.0, 1.0], (len(P), 1))
    prog.sweep(P, N, H['r'], name='hose')
    return prog

