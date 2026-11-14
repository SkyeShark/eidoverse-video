"""CYBORG C5b: THE FIRST FULL CYBORG OCTOPUS, the forge side of its assembly (work/bestiary/research/CYBORG_PLAN.md
§4.4, §5.5, §8 C5; its addendum A.4, A.7, A.8 and the lead's A.9 decisions; work/bestiary/PLAN.md 10-27 "C5b" and the
lead's C5b decisions 1-6). Skye's standing rule, said twice: parts MATCH THE BODY SLOT (a mech tentacle replaces an
octopus arm and nothing else).

The parts stay as they were made (C5a's mech tentacle, forge/cyborg_limb.py; C4's eye implant, forge/cyborg_eye.py;
C3 / C3b / C3c's plated octopus with its feed lines, forge/cyborg.py, read only here). This module adds what JOINS them,
and the gates on the joins:

  THE ARM      one arm by a recipe parameter (the limbs row's chain: a chain name or its label, R1..L1); the default
               L1 (arm7), the LEFT FRONT arm: of the house's hero stations (cyborg_c3/engine: front, three-quarter,
               side) the front and three-quarter see its proximal half NEAREST of all eight arms (joint 8 0.37 / 0.35 m
               in front of the body along their view axes; the side station 0.16 m), and it is on the side of the C4
               implant's eye (eye_L, +X) and of the front-left plate the hose starts from
  THE CUT      every arm of the octopus's low split at cut 8's ring (the low's ring nearest the share where the weight ramp
               gives joint 7 the whole weight; s 0.5004) into PROXIMAL and DISTAL triangles, and its geometric suckers
               likewise (those beyond the ring and those whose footprint reaches the flange's soft roll): t13
               (BESTIARY_CUT=8, patches/cyborg_c5b_t13.md) ships each arm's distal triangles as one contiguous index range
               of the arms primitive and of the suckers primitive, so the runtime hides the replaced arm's and nothing
               else changes; the cut ring and the ring before it (every split copy) are listed per arm, for the runtime
               to PIN them to joint 7 on the replaced arm (CYBORG_PLAN §4.4.2: then the flange, rigid on 7, holds the
               skin exactly, whatever the motion); the open ring hides in the collar's bore under the roll
  THE MOUNT    the asset's joints arm_07..arm_23 on the octopus's arm{j}_07..23 by the bind's chord frames: bone k's
               inverse bind [M_k | -M_k X_k] (M_k its chord frame in its own axes, the runtime's chordQ inverted; X_k the
               joint on the asset's straight bind; M_23 = I, cyborg_limb.pose_from_motion's tip), each helper joint a
               new bone under its parent, posed by its rule every frame (cyborg_limb.pose_joints, HELPER_RULES), inverse
               bind T(-X_k); one skeleton per creature (the octopus's own bones); the replaced arm's ground line from the
               asset's radius table (ground_profile)
  THE HOSE     forge/cyborg_hose.py
  THE GATES    per frame of the rest motion (the runtime's radialMotion.solveArm, ported here with the profile) and of
               the swim rig (t12's wave motion): no skin or sucker through the flange, roll or band; the roll on the skin
               within 0.3 mm all round; the helper joints against pose_joints; the knuckles and the asset's hose on the
               new motion (cyborg_limb's replays)

Read with numpy and scipy; warp only for the SDF programs (the CPU device is enough).
"""
import json
import math
import os
import struct

import numpy as np

from . import cyborg_limb as CL
from . import gltf

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
OCT_CANON = os.path.join(REPO, 'work', 'bestiary', 'octopus')
MECH_GLB = os.path.join(REPO, 'work', 'bestiary', 'cyborg_c5', 'mech_tentacle.glb')
IMPLANT_GLB = os.path.join(REPO, 'work', 'bestiary', 'cyborg_c4', 'eye_implant_lens.glb')
TAU = 2.0 * math.pi
N_JOINTS = CL.N_JOINTS
CUT = CL.CUT
J0 = CL.J0
ARM_LABELS = ('R1', 'R2', 'R3', 'R4', 'L4', 'L3', 'L2', 'L1')     # chain j = arm<j> (remix/slots.py PLATE_ARMS)
ARM_DEFAULT = 7                                                   # L1, the left front arm (the notes above)
FIRST_CARDAN = min(CL.CARDAN)
ROLL_CLEAR = 1.0e-3         # a kept sucker's farthest point stays this far short of the roll's proximal extent (the
                            # roll's section overhangs its footprint on the skin; the gate measures the clearance posed)
SEAT_BAR = 0.3e-3           # the lead's decision 3: the roll on the skin within 0.3 mm all round
REST_LOWER = 0.020          # STAGE 2B (patches/landing2b_tent.md): the runtime's rest crown height (bestiary.js
REST_TENT = 0.0             # radialMotion P.lower 0.040 and P.tent 1 before): the crown 20 mm higher and joint 1 on its
                            # flesh line, the root falling from the crown to the sand (a tent near the crown), the
                            # defaults of solve_arm and every rest function below


# ============================================================================================ glb readers
def quat_mat(q):
    return CL._quat_mat(q)


def trs(T=None, R=None, S=None):
    """a 4x4 from translation, a 3x3 rotation and a scale (three's compose: T R S)"""
    M = np.eye(4)
    Rm = np.eye(3) if R is None else np.asarray(R, np.float64)
    Sv = np.ones(3) if S is None else np.asarray(S, np.float64)
    M[:3, :3] = Rm * Sv[None, :]
    if T is not None:
        M[:3, 3] = T
    return M


def chord_basis(loc):
    """the runtime's chord frame of a bone in its own axes (bestiary.js radialMotion: loc the child's rest offset made
    unit, yref world-up made normal to it, z = loc x yref): the columns loc, yref, z (chordQ is its inverse)"""
    loc = np.asarray(loc, np.float64) / np.linalg.norm(loc)
    y = np.array([0.0, 1.0, 0.0]) - loc * loc[1]
    y /= np.linalg.norm(y)
    return np.column_stack([loc, y, np.cross(loc, y)])


class Rig:
    """a glb's node hierarchy and skin as three.js builds it (GLTFLoader: each node's local T R S; a SkinnedMesh bound
    at the identity: world = sum w bone.matrixWorld x inverse bind x v)"""

    def __init__(self, path):
        self.path = path
        G = gltf.read(path)
        self.G = G
        j = G['json']
        self.json = j
        self.nodes = j['nodes']
        self.names = [n.get('name', str(i)) for i, n in enumerate(self.nodes)]
        self.index = {n: i for i, n in enumerate(self.names)}
        self.parent = np.full(len(self.nodes), -1)
        for i, n in enumerate(self.nodes):
            for c in n.get('children', []):
                self.parent[c] = i
        self.T = np.array([n.get('translation', [0.0, 0.0, 0.0]) for n in self.nodes], np.float64)
        self.R = np.stack([quat_mat(n['rotation']) if 'rotation' in n else np.eye(3) for n in self.nodes])
        self.S = np.array([n.get('scale', [1.0, 1.0, 1.0]) for n in self.nodes], np.float64)
        sk = j['skins'][0]
        self.joints = list(sk['joints'])
        self.jnames = [self.names[i] for i in self.joints]
        self.ibm = G['accessor'](sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
        self.order = self._order()

    def _order(self):
        seen, out = set(), []

        def visit(i):
            if i in seen:
                return
            if self.parent[i] >= 0:
                visit(self.parent[i])
            seen.add(i)
            out.append(i)
        for i in range(len(self.nodes)):
            visit(i)
        return out

    def local(self, i):
        return trs(self.T[i], self.R[i], self.S[i])

    def worlds(self, over=None):
        """every node's world 4x4; over = {node index: local 4x4} replaces those nodes' local transforms"""
        over = over or {}
        W = np.zeros((len(self.nodes), 4, 4))
        for i in self.order:
            L = over[i] if i in over else self.local(i)
            p = self.parent[i]
            W[i] = L if p < 0 else W[p] @ L
        return W

    def skin_mats(self, W):
        return np.einsum('jab,jbc->jac', W[self.joints], self.ibm)


def lbs(V, J, Wt, M):
    """linear blend skinning of points V (n, 3) on skin matrices M (J, 4, 4): joints / weights (n, k)"""
    Vh = np.concatenate([np.asarray(V, np.float64), np.ones((len(V), 1))], 1)
    out = np.zeros((len(V), 3))
    for c in range(J.shape[1]):
        w = Wt[:, c]
        m = w > 0.0
        if m.any():
            out[m] += w[m, None] * np.einsum('nij,nj->ni', M[J[m, c]], Vh[m])[:, :3]
    return out


class Octopus:
    """the shipped octopus (t13's glb) with its low's face sets and regions (low.npz beside it) and the geometric
    suckers' instances (part_mesh, deterministic, as t13 builds them)"""

    def __init__(self, glb, low_npz=None):
        self.rig = Rig(glb)
        G, j = self.rig.G, self.rig.json
        self.mesh = j['meshes'][0]
        self.prims = self.mesh['primitives']
        mats = [m.get('name', '') for m in j['materials']]
        self.mat_of = [mats[p['material']] for p in self.prims]
        p0 = self.prims[0]
        self.V = G['accessor'](p0['attributes']['POSITION']).astype(np.float64)
        self.J = G['accessor'](p0['attributes']['JOINTS_0']).astype(np.int64)
        self.W = G['accessor'](p0['attributes']['WEIGHTS_0']).astype(np.float64)
        self.N = G['accessor'](p0['attributes']['NORMAL']).astype(np.float64)
        Lw = np.load(low_npz or os.path.join(os.path.dirname(glb), 'low.npz'), allow_pickle=True)
        self.low = {k: Lw[k] for k in ('V', 'F', 'UV', 'region', 'face_set', 'order')}
        assert np.abs(self.V[:len(self.low['V'])] - self.low['V']).max() < 1e-6, 'the glb is not this low'
        self.F = self.low['F']
        self.region = self.low['region']
        self.fset = self.low['face_set']
        self.bone = {n: k for k, n in enumerate(self.rig.jnames)}
        self.extras = j.get('extras', {}).get('bestiary', {})

    def prim(self, name):
        """(index, triangles (m, 3) in its own vertex numbering) of the primitive whose material is `name`"""
        for i, (p, m) in enumerate(zip(self.prims, self.mat_of)):
            if m == name:
                return i, self.rig.G['accessor'](p['indices']).reshape(-1, 3).astype(np.int64)
        raise KeyError(name)

    def sucker_prim(self):
        """the suckers primitive's own vertex set: V, J, W, N and its triangles"""
        i, F = self.prim('octopus_suckers')
        a = self.prims[i]['attributes']
        acc = self.rig.G['accessor']
        return dict(index=i, V=acc(a['POSITION']).astype(np.float64), J=acc(a['JOINTS_0']).astype(np.int64),
                    W=acc(a['WEIGHTS_0']).astype(np.float64), N=acc(a['NORMAL']).astype(np.float64), F=F)

    def arm_bind(self, j):
        """arm j's 24 bind joint positions (the creature's frame) and every bone's rest local rotation and offset"""
        W = self.rig.worlds()
        ids = [self.rig.index[f'arm{j}_{k:02d}'] for k in range(N_JOINTS)]
        return dict(ids=ids, P=W[ids][:, :3, 3].copy(), Rw=W[ids][:, :3, :3].copy(), T=self.rig.T[ids].copy(),
                    R=self.rig.R[ids].copy())

    def chord_M(self, j):
        """M_k (24, 3, 3): arm j's bone k chord frame in its own axes (the runtime's chordQ^-1), M_23 = I"""
        T = self.rig.T
        M = np.tile(np.eye(3), (N_JOINTS, 1, 1))
        for k in range(N_JOINTS - 1):
            M[k] = chord_basis(T[self.rig.index[f'arm{j}_{k + 1:02d}']])
        return M

    def flesh_reach(self, j):
        """C5c (the lead's decision 6): arm j's TRUE REACH below each joint's chord axis in the bind, as the runtime
        measures it at create() (patches/cyborg_c5b_bestiary.md fleshReach): over the low's vertices and the geometric
        suckers' whose heaviest bone is arm{j}_kk, the farthest under bone k's chord frame (its y the chord's 'up');
        0 where no vertex names the bone. The runtime's flesh ground line (solve_arm) sets the centreline that high so
        the arm rests on its lowest point (r4's 0.92 x taper put it 3-8 mm into the sand, its suckers 6-14 mm).
        Returns (24,) metres"""
        if not hasattr(self, '_reach'):
            self._reach = {}
        if j in self._reach:
            return self._reach[j]
        b = self.arm_bind(j)
        M = self.chord_M(j)
        Y = np.einsum('kab,kb->ka', b['Rw'], M[:, :, 1])
        S = self.sucker_prim()
        nV = len(self.low['V'])
        out = np.zeros(N_JOINTS)
        ids = {self.bone[f'arm{j}_{k:02d}']: k for k in range(N_JOINTS)}
        for V_, J_, W_ in ((self.V[:nV], self.J[:nV], self.W[:nV]), (S['V'], S['J'], S['W'])):
            top = J_[np.arange(len(J_)), W_.argmax(1)]
            for bid, k in ids.items():
                m = top == bid
                if m.any():
                    out[k] = max(out[k], float(-((V_[m] - b['P'][k]) @ Y[k]).min()))
        out = out.view(Reach)
        out.hulls = self.flesh_support(j)        # C5d: the support outlines ride on the reach (solve_arm reads them)
        self._reach[j] = out
        return out

    def flesh_support(self, j):
        """C5d (the lead's call 1): arm j's SUPPORT OUTLINES, as the runtime measures them at create() (patches/
        cyborg_c5d_bestiary.md fleshSupport): per joint k its section (the low's vertices and the geometric suckers'
        whose heaviest bone is arm{j}_kk) in the frame its pitch is read in (chord k's; the last joint chord n - 2's),
        from the joint, reduced to the convex outline of its (x, y): solve_arm aims every chord with no roll (its y
        from world up), so the section's reach along world down at pitch phi is max -(x sin phi + y cos phi) over the
        outline (reach_v). Returns [24] (m_k, 2) arrays (empty where no vertex names the bone)"""
        b = self.arm_bind(j)
        M = self.chord_M(j)
        C = np.einsum('kab,kbc->kac', b['Rw'], M)
        S = self.sucker_prim()
        nV = len(self.low['V'])
        ids = {self.bone[f'arm{j}_{k:02d}']: k for k in range(N_JOINTS)}
        pts = {k: [] for k in range(N_JOINTS)}
        for V_, J_, W_ in ((self.V[:nV], self.J[:nV], self.W[:nV]), (S['V'], S['J'], S['W'])):
            top = J_[np.arange(len(J_)), W_.argmax(1)]
            for bid, k in ids.items():
                m = top == bid
                if m.any():
                    pts[k].append((V_[m] - b['P'][k]) @ C[min(k, N_JOINTS - 2)])
        return [hull2(np.concatenate(pts[k])[:, :2]) if pts[k] else np.zeros((0, 2)) for k in range(N_JOINTS)]


# ============================================================================================ the cut
class LowView:
    """the arrays the cut reads, from t13's own (the low's V, F, region; each arm's bind joint positions, world
    rotations and rest local offsets from its skeleton), so t13 and the gates run the same code"""

    def __init__(self, V, F, region, joints):
        self.low = dict(V=np.asarray(V, np.float64))
        self.F = np.asarray(F, np.int64)
        self.region = np.asarray(region, np.int64)
        self._j = joints                                  # {arm: dict(P (24, 3), Rw (24, 3, 3), T (24, 3))}

    def arm_bind(self, j):
        return self._j[j]

    def chord_M(self, j):
        T = self._j[j]['T']
        M = np.tile(np.eye(3), (N_JOINTS, 1, 1))
        for k in range(N_JOINTS - 1):
            M[k] = chord_basis(T[k + 1])
        return M


def low_view_from_skeleton(V, F, region, sk, n_arms=8):
    """a LowView from t13's skeleton (forge/rig.Skeleton: names, world frames, parents)"""
    joints = {}
    for j in range(n_arms):
        ids = [sk.index(f'arm{j}_{k:02d}') for k in range(N_JOINTS)]
        Wm = np.stack([sk.world[i] for i in ids])
        T = np.stack([sk.local(i)[:3, 3] for i in ids])
        joints[j] = dict(P=Wm[:, :3, 3].copy(), Rw=Wm[:, :3, :3].copy(), T=T)
    return LowView(V, F, region, joints)


def arm_shares(oct_, j, P=None):
    """per vertex of arm j's tube (region 3 + j) its share s along the arm's joint polyline (cyborg_limb.arm_chain's
    rule), and the low's ring shares (clustered at 0.002)"""
    from .species import octopus as O
    from .species import octopus_rig as OR
    spec = O.low_spec(O.SPEC)
    js = OR.arm_joint_s(spec)
    if P is None:
        P = oct_.arm_bind(j)['P']
    V, F, reg = oct_.low['V'], oct_.F, oct_.region
    arm_v = np.unique(F[reg == 3 + j])
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
    return dict(js=js, arm_v=arm_v, s=s_arm, ring_s=ring_s)


def cut_arm(oct_, j, cut=CUT):
    """arm j cut at joint `cut`'s ring: the ring (the low's ring nearest the share where the weight ramp gives joint
    cut - 1 the whole weight) and the ring before it, every vertex on each (split copies too), and the arm's DISTAL
    triangles (all three corners at or beyond the ring), as indices into the low's F"""
    sh = arm_shares(oct_, j)
    js, rs = sh['js'], sh['ring_s']
    s_cut = 0.5 * (js[cut - 1] + js[cut])
    ir = int(np.argmin(np.abs(rs - s_cut)))
    ring_s, before_s = float(rs[ir]), float(rs[ir - 1])
    sv = np.full(len(oct_.low['V']), -1.0)
    sv[sh['arm_v']] = sh['s']
    on = lambda s0: sh['arm_v'][np.abs(sh['s'] - s0) < 0.0015]
    fa = np.nonzero(oct_.region == 3 + j)[0]
    distal = fa[(sv[oct_.F[fa]] >= ring_s - 1.0e-4).all(1)]
    return dict(arm=j, cut=cut, s_cut=float(s_cut), ring_s=ring_s, before_s=before_s, ring=on(ring_s),
                before=on(before_s), distal=distal, js=js)


def flange_frame(oct_, j):
    """arm j's bone 7 chord frame in the bind: (origin P_7, rotation C_7 = Rw_7 M_7): the asset's frame (x from joint
    7 along the chord, y aboral)"""
    b = oct_.arm_bind(j)
    M = oct_.chord_M(j)
    return b['P'][J0], b['Rw'][J0] @ M[J0]


def roll_extent(chain=None):
    """the soft roll's proximal extent along chord 7 (m from joint 7) as the asset builds it (cyborg_limb.design's
    flange stack: the collar's lip at x8 - band / 2 - collar_h, the roll at the lip + 0.15 roll, its section roll wide)"""
    D = CL.DESIGN
    seg7 = float(chain['seg'][J0]) if chain is not None else float(_mech_extras()['seg'][0])
    collar0 = seg7 - 0.5 * D['band'] - D['collar_h']
    roll_x = collar0 + 0.15 * D['roll']
    return roll_x - 0.5 * D['roll'], dict(collar0=collar0, roll_x=roll_x, x8=seg7)


_MECH_X = {}


def _mech_extras(path=MECH_GLB):
    if path not in _MECH_X:
        with open(path, 'rb') as f:
            data = f.read()
        jl = struct.unpack_from('<I', data, 12)[0]
        _MECH_X[path] = json.loads(data[20:20 + jl])['extras']['bestiary']
    return _MECH_X[path]


def sucker_split(I, S, arm_frames, ring_s, x_roll0, clear=ROLL_CLEAR):
    """which geometric suckers the cut HIDES with an arm's distal part: those beyond the ring (their share past it) and
    those whose farthest bind vertex along chord 7 reaches within `clear` of the roll's proximal extent x_roll0.
    arm_frames: {arm: (P_7, C_7)}. Returns per instance a bool (hidden) and its x reach"""
    inst = S['inst']
    hide = np.zeros(len(I['d']), bool)
    reach = np.full(len(I['d']), -np.inf)
    for a, (P7, C7) in arm_frames.items():
        on = I['arm'] == a
        if not on.any():
            continue
        vm = on[inst]
        x = (S['V'][vm] - P7) @ C7[:, 0]
        np.maximum.at(reach, inst[vm], x)
    hide = (I['s'] > ring_s) | (reach >= x_roll0 - clear)
    return hide, reach


def cut_record(lv, fset, cut=CUT, n_arms=8):
    """THE CUT on every arm for t13 (BESTIARY_CUT): per arm its ring and the ring before (the pin's vertices, every
    split copy), its distal triangles, and the ARMS PRIMITIVE's triangles reordered [kept..., arm 0's distal, ...,
    arm 7's distal] with each arm's range (three's index units). lv: a LowView (t13's arrays); fset the low's face sets.
    Returns dict(arms {j: dict(ring_s, before_s, ring, before, distal, range)}, perm (the arms set's triangle order, as
    positions in F[fset == 'arms']))"""
    fa_all = np.nonzero(np.asarray(fset) == 'arms')[0]
    pos_in = -np.ones(len(lv.F), np.int64)
    pos_in[fa_all] = np.arange(len(fa_all))
    recs, groups = {}, []
    for j in range(n_arms):
        c = cut_arm(lv, j, cut)
        assert (pos_in[c['distal']] >= 0).all(), 'a distal triangle outside the arms set'
        m = np.zeros(len(fa_all), bool)
        m[pos_in[c['distal']]] = True
        groups.append((f'arm{j}', m))
        recs[j] = c
    perm, ranges = reorder_ranges(groups)
    for j in range(n_arms):
        recs[j]['range'] = ranges[f'arm{j}']
    return dict(arms=recs, perm=perm, cut=cut)


def sucker_record(lv, I, S, rec, x_roll0=None, clear=ROLL_CLEAR):
    """the geometric suckers the cut hides with each arm's distal part (sucker_split), and the suckers primitive's
    triangles reordered [kept..., arm 0's hidden, ..., arm 7's hidden] with each arm's range. I, S: octopus_suckers'
    instances and mesh (part_mesh). Returns dict(perm (S['F']'s triangle order), ranges {j: [start, count]}, hidden
    (per instance), reach)"""
    if x_roll0 is None:
        x_roll0, _ = roll_extent()
    frames = {j: flange_frame(lv, j) for j in rec['arms']}
    ring_s = max(r['ring_s'] for r in rec['arms'].values())
    hide, reach = sucker_split(I, S, frames, ring_s, x_roll0, clear)
    tri_inst = S['inst'][S['F'][:, 0]]
    groups = [(f'arm{j}', hide[tri_inst] & (I['arm'][tri_inst] == j)) for j in sorted(rec['arms'])]
    perm, ranges = reorder_ranges(groups)
    kept = ~hide
    tri_arm = np.where(hide[tri_inst], I['arm'][tri_inst], -1)[perm]
    return dict(perm=perm, ranges={j: ranges[f'arm{j}'] for j in sorted(rec['arms'])}, hidden=hide, reach=reach,
                x_roll0=x_roll0, counts={j: int((hide & (I['arm'] == j)).sum()) for j in sorted(rec['arms'])},
                kept_reach={j: float(reach[kept & (I['arm'] == j)].max()) for j in sorted(rec['arms'])},
                F_perm=S['F'][perm], tri_arm=tri_arm)


def export_suckers_split(g, mesh_index, low, order, spec, oct_dir, tx, lv, rec, log=print):
    """octopus_suckers.export_part's steps with the suckers primitive's triangles in the cut's order (sucker_record):
    the same vertices, weights, colours and material, only the triangles permuted. Returns (primitive index, record)"""
    import os as _os
    from PIL import Image
    from .species import octopus_suckers as OS
    I, S = OS.part_mesh(low, order, spec, oct_dir, log=log)
    sr = sucker_record(lv, I, S, rec)
    S2 = dict(S)
    S2['F'] = S['F'][sr['perm']]
    maps, wall_ref = OS.part_maps(oct_dir)
    img = lambda n: np.asarray(Image.open(_os.path.join(oct_dir, n)))
    colours = OS.skin_colours(I, low, {'head': img('T_head_albedo.png'), 'arms': img('T_arms_albedo.png')},
                              {'head': img('T_head_display.png'), 'arms': img('T_arms_display.png')}, log=log)
    pi, _ = OS.add_to_glb(g, mesh_index, S2, colours, maps, tx, wall_ref)
    log(f'[suckers] exported (the cut\'s order): primitive {pi}, {len(S["V"]):,} vertices, {len(S["F"]):,} triangles; '
        f'hidden with each arm\'s distal part {int(sr["hidden"].sum() // max(len(rec["arms"]), 1))} per arm')
    return pi, sr


def cut_extras(rec, sr, n_eye_tris, joint_name=lambda j, k: f'arm{j}_{k:02d}'):
    """the octopus MESH's extras cyborg_cut (meshes[0].extras: what the runtime reads to hide a replaced arm; the scene
    extras stay C0b's and the cap's): per arm its distal range in the arms primitive and the suckers primitive (three's
    index units), the vertices it pins and the joint, the ring shares; the eyes' ranges in the eye primitive (an implant
    hides its eye's)"""
    arms = {}
    for j, c in rec['arms'].items():
        arms[f'arm{j}'] = dict(ring_s=round(c['ring_s'], 6), before_s=round(c['before_s'], 6),
                               distal=[int(v) for v in c['range']], suckers=[int(v) for v in sr['ranges'][j]],
                               hidden_suckers=int(sr['counts'][j]),
                               kept_sucker_reach_mm=round(1e3 * sr['kept_reach'][j], 3),
                               pin=dict(joint=joint_name(j, rec['cut'] - 1),
                                        vertices=sorted(int(v) for v in np.concatenate([c['ring'], c['before']]))))
    nL = int(n_eye_tris[0])
    return dict(cut=int(rec['cut']), primitives=dict(arms='octopus_arms', suckers='octopus_suckers', eye='octopus_eye'),
                arms=arms, eyes=dict(eye_L=[0, 3 * nL], eye_R=[3 * nL, 3 * int(n_eye_tris[1])]),
                units='index offsets and counts into each primitive\'s index buffer (3 per triangle)',
                rule='the runtime hides a replaced arm\'s distal range in the arms and suckers primitives and pins its '
                     'listed vertices to the joint at weight 1 (forge/cyborg_octopus.py; patches/cyborg_c5b_t13.md)')


def reorder_ranges(groups):
    """triangles ordered as [kept..., group 1, group 2, ...]: groups a list of (name, bool mask over the triangles);
    the kept are the triangles in no group. Returns (permutation, {name: [start index, index count]}) in INDEX units
    (3 per triangle: three's geometry.index offsets)"""
    n = len(groups[0][1])
    any_ = np.zeros(n, bool)
    for _, m in groups:
        assert not (any_ & m).any(), 'a triangle in two groups'
        any_ |= m
    perm = [np.nonzero(~any_)[0]]
    ranges = {}
    at = int((~any_).sum())
    for name, m in groups:
        idx = np.nonzero(m)[0]
        perm.append(idx)
        ranges[name] = [3 * at, 3 * len(idx)]
        at += len(idx)
    return np.concatenate(perm), ranges


# ============================================================================================ the motion (the runtime's)
RAMP = 3                    # the flesh joints before the flange's bone that ease the arm up onto the flange's height


def ground_profile(table, lens, cut=CUT, r0=0.026, r_tip=0.0011, ramp=RAMP, reach=None):
    """the REPLACED arm's ground line (the lead's decision 3: the runtime reads the asset's radius table in place of r4's
    taper): per joint 0..23 the centreline's height over the ground (m), None where the flesh's r4 line holds. From the
    table T (joint -> the machine's reach below its centreline, cyborg_limb.radius_table):
      the CARDAN section (16..23: its knuckles take pitch) rests on each joint's reach, H = T;
      the CLEVIS section (cut..16) cannot pitch (knuckles 9-15 turn in yaw alone, +-1.2 deg designed): ONE straight
        line from joint cut to joint 16, as low as it can be while no joint's reach sinks under it and never under the
        table's joint-cut reach (the flange's soft roll, the lowest piece near joint 8: T at joint 8 is the roll's);
      joint cut - 1 (the flange's own bone starts there) level with joint cut, so the flange lies flat on its roll;
      the `ramp` flesh joints before it rise linearly (by arc length) from the flesh line at joint cut - 1 - ramp to
        that height, so the arm drapes up onto the flange over three segments, not at one joint (a 9 deg kink at joint 7).
    lens: the arm's 23 bind segment lengths; r0, r_tip: r4's taper (bestiary.js SPECIES body); reach: the arm's true
    reach per joint (C5c: Octopus.flesh_reach; the flesh line flesh_line; None: r4's 0.92 x taper). Returns 24 (None
    or m)"""
    T = {int(r['joint']): float(r['oral']) for r in table}
    lens = np.asarray(lens, np.float64)
    s = np.concatenate([[0.0], np.cumsum(lens)])
    L = float(lens.sum()) / 0.985
    r4 = lambda k: flesh_line(reach, k, r_tip + (r0 - r_tip) * max(1.0 - s[k] / L, 0.0) ** 0.92)
    H = [None] * N_JOINTS
    for k in range(FIRST_CARDAN, N_JOINTS):
        H[k] = T[k]
    k0, k1 = cut, FIRST_CARDAN
    t = lambda k: (s[k] - s[k0]) / (s[k1] - s[k0])
    g0 = T[k0]
    for k in range(k0 + 1, k1):
        g0 = max(g0, (T[k] - T[k1] * t(k)) / (1.0 - t(k)))
    for k in range(k0, k1):
        H[k] = g0 + (T[k1] - g0) * t(k)
    H[k0 - 1] = H[k0]
    ka = k0 - 1 - ramp
    if ramp > 0 and ka >= 1:
        ha = r4(ka)
        for k in range(ka + 1, k0 - 1):
            H[k] = ha + (H[k0 - 1] - ha) * (s[k] - s[ka]) / (s[k0 - 1] - s[ka])
    return H


GROUND_PRESS = 0.5e-3       # C5c: a flesh arm's lowest point (skin or sucker) rests this far into the sand


def flesh_line(reach, k, rad):
    """C5c, the FLESH arms' ground line (the lead's decision 6; the runtime's fleshY): joint k's centreline height over
    the ground, its true reach (Octopus.flesh_reach) less GROUND_PRESS, or r4's 0.92 rad where no reach was measured"""
    if reach is not None and reach[k] > 0.0:
        return float(reach[k]) - GROUND_PRESS
    return 0.92 * rad


BISECT = 48                 # C5d: the contact pitch's bisection steps (to ~1e-14 rad over pi)


class Reach(np.ndarray):
    """C5d: the bind reach per joint (Octopus.flesh_reach: what ground_profile reads) carrying the joints' support
    outlines (hulls: Octopus.flesh_support)"""
    hulls = None


def hull2(P):
    """C5d: the 2D convex hull's vertices (Andrew's monotone chain), counter-clockwise"""
    P = np.unique(np.asarray(P, np.float64), axis=0)
    if len(P) < 3:
        return P
    P = P[np.lexsort((P[:, 1], P[:, 0]))]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in P[::-1]:
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return np.array(lo[:-1] + up[:-1])


def reach_v(hull, phi):
    """C5d: an outline's (m, 2) support reach along world down at pitches phi (T,): (T,) (0 for an empty outline)"""
    phi = np.asarray(phi, np.float64)
    if not len(hull):
        return np.zeros_like(phi)
    return (-(hull[None, :, 0] * np.sin(phi)[:, None] + hull[None, :, 1] * np.cos(phi)[:, None])).max(1)


def contact_pitch(hull, y, floor, sin_lo):
    """C5d: a segment's pitch with its section resting on `floor` (the runtime's contactPitch): per frame the least
    steep phi >= asin(sin_lo) at which y - reach(phi) reaches floor (y the joint's height), by bisection below the top
    of y - reach on [asin(sin_lo), pi / 2] (a scan of 65), where y - reach(asin(sin_lo)) < floor; sin_lo elsewhere.
    (The lowest point rises as the segment levels, its far part leading; past that top it falls again, the near end
    dipping.) Returns sines (T,)"""
    out = np.array(sin_lo, np.float64, copy=True)
    lo = np.arcsin(np.clip(sin_lo, -1.0, 1.0))
    need = (y - reach_v(hull, lo)) < floor
    if not need.any():
        return out
    a = lo[need].copy()
    yy, ff = y[need], floor[need]
    grid = np.linspace(0.0, 1.0, 65)[None, :]
    ph = a[:, None] + (0.5 * math.pi - a[:, None]) * grid
    hh = yy[:, None] + (-(hull[None, None, :, 0] * np.sin(ph)[..., None]
                          + hull[None, None, :, 1] * np.cos(ph)[..., None])).max(2) * -1.0
    b = ph[np.arange(len(a)), hh.argmax(1)]
    ok = hh.max(1) >= ff
    for _ in range(BISECT):
        m = 0.5 * (a + b)
        up = (yy - reach_v(hull, m)) >= ff
        b = np.where(up, m, b)
        a = np.where(up, a, m)
    out[need] = np.where(ok, np.sin(b), np.sin(ph[np.arange(len(ph)), hh.argmax(1)]))
    return out


def solve_arm(P_bind, ts, j, seed, lower=REST_LOWER, r0=0.026, r_tip=0.0011, ground=0.0, H=None, reach=None,
              tent=REST_TENT):
    """runtime/bestiary.js radialMotion.solveArm, term by term (cyborg_limb.solve_arm, its port), with the replaced
    arm's ground line: where H[k + 1] is a number the joint's target height is ground + H[k + 1]; elsewhere (C5c) the
    flesh line, the arm's true reach (flesh_line), in place of r4's 0.92 rad. Returns pos (T, 24, 3) and the chord
    frames F (T, 23, 3, 3). C5d (the lead's call 1): with the support outlines on `reach` (Octopus.flesh_reach carries
    them) the drape is anchored on the flesh line it blends into at joint 1 and scaled so joint 1 lies AT the crown's
    height, and within the drape each segment is turned up where its section would reach under the sand
    (contact_pitch); a plain reach (or none): C5c's. STAGE 2B: the drape times `tent` (the runtime's P.tent: 1 C5d's,
    joint 1 at the crown's height; 0 joint 1 on its flesh line, the root falling from the crown to the sand)"""
    p = CL.arm_params(j, seed)
    P = np.asarray(P_bind, np.float64) - np.array([0.0, lower, 0.0])
    lens = np.linalg.norm(np.diff(P, axis=0), axis=1)
    n = len(P)
    L = float(lens.sum()) / 0.985
    t = np.atleast_1d(np.asarray(ts, np.float64))
    T_ = len(t)
    d0 = P[1] - P[0]
    d0[1] = 0.0
    d0 /= np.linalg.norm(d0)
    coilMul = 1.0 + 0.10 * np.sin(TAU * 0.06 * t + p['ph0'])
    theta = np.full(T_, math.atan2(d0[0], d0[2]) + p['dAz'])
    cur = np.tile(P[0], (T_, 1))
    y0 = P[0, 1]
    s = 0.0
    pos = np.zeros((T_, n, 3))
    pos[:, 0] = cur
    F = np.zeros((T_, n - 1, 3, 3))
    UP = np.array([0.0, 1.0, 0.0])
    sm_ = CL._smooth
    # C5d: the drape's crown anchor the flesh line it blends into at joint 1 (its level reach; C5c: r4's 0.92 r0, the
    # roots rose up to 6.1 mm above the crown), the drape scaled so that joint 1 lies AT the crown's height
    hulls = getattr(reach, 'hulls', None)
    sup = hulls is not None and reach[1] > 0.0
    anchor = float(reach[1]) - GROUND_PRESS if sup else 0.92 * r0
    drape_at = lambda s_: 1.0 - sm_(0.0, p['drape'], s_)
    crown_k = drape_at(lens[0]) if sup else 1.0
    for k in range(n - 1):
        sm = s + 0.5 * lens[k]
        u = sm / L
        kap = p['wanderK'] * np.sin(TAU * sm / p['wanderL'] + p['wanderPh']) * (0.3 + 0.7 * sm_(0.05, 0.3, u))
        rem = max(L - sm, 0.0)
        kap = kap + p['coilSide'] * coilMul * sm_(p['coilS0'], p['coilS0'] + 0.12, u) / (0.010 + p['coilG'] * rem)
        kap = kap + 0.9 * np.sin(TAU * 0.21 * t - 9.0 * u + p['ph1']) * sm_(0.75, 1.0, u)
        theta = theta + kap * lens[k]
        s1 = s + lens[k]
        u1 = s1 / L
        rad = r_tip + (r0 - r_tip) * max(1.0 - u1, 0.0) ** 0.92
        hk = H[k + 1] if H is not None else None
        yg = ground + (hk if hk is not None else flesh_line(reach, k + 1, rad))
        drape = (y0 - (ground + anchor)) * tent * drape_at(s1) / crown_k
        yT = yg + drape + p['tipLift'] * sm_(0.82, 1.0, u1) * (1.0 + 0.4 * np.sin(TAU * 0.17 * t + p['ph1']))
        sinPhi = np.clip((yT - cur[:, 1]) / lens[k], -1.0, 1.0)
        if sup and hk is None and len(hulls[k]) and s < p['drape']:
            # C5d: in the drape (the segments starting short of it: the root falling from the crown) the segment's
            # section never under the sand: its lowest point along world down at the pitch it takes no lower than
            # ground - GROUND_PRESS + the drape at the next joint, turned up where it would be (past the drape every
            # section's far part stood 0.1-0.6 mm under the level line, and held out of it the lift ran down the arm)
            floor = np.broadcast_to(ground - GROUND_PRESS + drape, (T_,)).astype(np.float64)
            sinPhi = contact_pitch(hulls[k], cur[:, 1], floor, sinPhi)
        cosPhi = np.sqrt(1.0 - sinPhi * sinPhi)
        d = np.stack([cosPhi * np.sin(theta), sinPhi, cosPhi * np.cos(theta)], -1)
        yv = UP[None] - d * d[:, 1:2]
        yv /= np.linalg.norm(yv, axis=1, keepdims=True)
        F[:, k] = np.stack([d, yv, np.cross(d, yv)], -1)
        cur = cur + d * lens[k]
        pos[:, k + 1] = cur
        s = s1
    return pos, F


def arm_bone_worlds(oct_, j, pos, F):
    """arm j's 24 bone world matrices (per frame) from solveArm's output: bone k's world rotation Rb_k = F_k M_k^T (the
    runtime's qa = aimed x chordQ), its origin the joint; bone 23 at its rest local rotation under bone 22 (the runtime
    leaves the last joint at rest). pos (T, 24, 3), F (T, 23, 3, 3) -> (T, 24, 4, 4)"""
    M = oct_.chord_M(j)
    b = oct_.arm_bind(j)
    T_ = len(pos)
    W = np.tile(np.eye(4), (T_, N_JOINTS, 1, 1))
    for k in range(N_JOINTS - 1):
        W[:, k, :3, :3] = F[:, k] @ M[k].T
    W[:, N_JOINTS - 1, :3, :3] = W[:, N_JOINTS - 2, :3, :3] @ b['R'][N_JOINTS - 1]
    W[:, :, :3, 3] = pos
    return W


def rest_pose_overrides(oct_, t, lower=REST_LOWER, mantle_pitch=0.0):
    """the runtime's radialMotion at time t for every bone but the arms (bestiary.js): the body lowered onto its web,
    mantle_0 tilted by mantlePitch (0: the bind's), mantle_1 and funnel_1 breathing (scale), the eyes in their seeded
    saccades are left at rest (no gate reads them). Returns {node index: local 4x4}"""
    rg = oct_.rig
    over = {}
    ib = rg.index['body']
    over[ib] = trs(rg.T[ib] - np.array([0.0, lower, 0.0]), rg.R[ib], rg.S[ib])
    vent = math.sin(TAU * 0.4 * t)
    for nm, sc in (('mantle_1', (1.0, 1.0 + 0.035 * vent, 1.0 + 0.035 * vent)),
                   ('funnel_1', (1.0, 1.0 - 0.06 * vent, 1.0 - 0.06 * vent))):
        i = rg.index[nm]
        over[i] = trs(rg.T[i], rg.R[i], sc)
    if mantle_pitch:
        i = rg.index['mantle_0']
        c, s_ = math.cos(mantle_pitch), math.sin(mantle_pitch)
        over[i] = trs(rg.T[i], rg.R[i] @ np.array([[c, -s_, 0.0], [s_, c, 0.0], [0.0, 0.0, 1.0]]), rg.S[i])
    return over


def rest_worlds(oct_, arms_pose, t, lower=REST_LOWER):
    """every node's world at one frame of the rest motion: arms_pose = {arm j: (24, 4, 4) bone worlds} for the arms the
    caller solved (the others stay at their rest locals under the lowered body)"""
    over = rest_pose_overrides(oct_, t, lower)
    W = oct_.rig.worlds(over)
    for j, Wa in arms_pose.items():
        ids = [oct_.rig.index[f'arm{j}_{k:02d}'] for k in range(N_JOINTS)]
        W[ids] = Wa
    return W


def rest_arm_frames(oct_, j, H, seeds=range(1, 17), dur=60.0, fps=10.0, lower=REST_LOWER):
    """arm j's bone worlds over the rest motion (the runtime's solveArm with the replaced arm's ground profile H; every
    seed, dur seconds at fps): (n, 24, 4, 4), and per frame (seed, t)"""
    P = oct_.arm_bind(j)['P']
    ts = np.arange(0.0, dur, 1.0 / fps)
    out, tag = [], []
    for seed in seeds:
        pos, F = solve_arm(P, ts, j, seed, lower=lower, H=H, reach=oct_.flesh_reach(j))
        out.append(arm_bone_worlds(oct_, j, pos, F))
        tag += [(seed, float(t)) for t in ts]
    return np.concatenate(out), tag


def rest_frame(oct_, seed, t, replaced=None, H=None, lower=REST_LOWER):
    """every node's world at one frame of the runtime's rest motion: all eight arms solved (the replaced arm with the
    ground profile H), the body lowered, the mantle breathing"""
    arms = {}
    for j in range(8):
        P = oct_.arm_bind(j)['P']
        pos, F = solve_arm(P, [t], j, seed, lower=lower, H=H if j == replaced else None, reach=oct_.flesh_reach(j))
        arms[j] = arm_bone_worlds(oct_, j, pos, F)[0]
    return rest_worlds(oct_, arms, t, lower)


def swim_arm_frames(oct_, j, dur=10.0, fps=24.0):
    """arm j's bone worlds over t12's swim rig: (n, 24, 4, 4) and the times"""
    sp = swim_params()
    ts = np.arange(0.0, dur, 1.0 / fps)
    ids = [oct_.rig.index[f'arm{j}_{k:02d}'] for k in range(N_JOINTS)]
    return np.stack([swim_worlds(oct_, t, sp)[ids] for t in ts]), ts


# t12's swim rig (work/bestiary/tests/t12_octopus_rig.py pose(t), its rng(3) draws): every arm's joints turned by waves
# in their rest local frames, the mantle breathing
def swim_params():
    rng = np.random.default_rng(3)
    return dict(ph=rng.uniform(0, 2 * np.pi, (8, 3)), curl=rng.uniform(-0.6, 1.4, 8), lift=rng.uniform(0.15, 0.55, 8))


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def swim_worlds(oct_, t, sp=None):
    """every node's world at time t of t12's rig motion (its pose(t): arm joint k of arm j turned rz(bend) ry(side) in
    its rest local frame, mantle_1 and mantle_2 rz(breathe))"""
    sp = sp or swim_params()
    rg = oct_.rig
    over = {}
    nk = N_JOINTS
    for j in range(8):
        for k in range(nk):
            u = k / (nk - 1)
            amp = 0.07 * (0.25 + u)
            bend = (amp * math.sin(2 * math.pi * 0.31 * t - 0.42 * k + sp['ph'][j, 0]) - sp['curl'][j] * 0.035 * u * u
                    + (sp['lift'][j] * 0.10 if k < 3 else 0.0))
            side = 0.06 * (0.2 + u) * math.sin(2 * math.pi * 0.19 * t - 0.35 * k + sp['ph'][j, 1])
            i = rg.index[f'arm{j}_{k:02d}']
            over[i] = trs(rg.T[i], rg.R[i] @ _rz(bend) @ _ry(side), rg.S[i])
    br = 0.03 * math.sin(2 * math.pi * 0.4 * t)
    for nm in ('mantle_1', 'mantle_2'):
        i = rg.index[nm]
        over[i] = trs(rg.T[i], rg.R[i] @ _rz(br), rg.S[i])
    return rg.worlds(over)


def arm_chords_from_worlds(oct_, j, W):
    """arm j's joint positions and chord frames from node worlds (one frame): pos (24, 3), F (24, 3, 3) with F[k] =
    Rb_k M_k (the chord frame) for k < 23 and F[23] = Rb_23 (cyborg_limb.pose_from_motion's tip)"""
    M = oct_.chord_M(j)
    ids = [oct_.rig.index[f'arm{j}_{k:02d}'] for k in range(N_JOINTS)]
    Wa = W[ids]
    pos = Wa[:, :3, 3].copy()
    F = np.einsum('kab,kbc->kac', Wa[:, :3, :3], M)
    return pos, F


# ============================================================================================ the mech tentacle, mounted
class Mech:
    """the shipped mech tentacle (C5a's glb): its low, skin (joint indices into its skin's joint list, two weights) and
    the extras pose_joints needs (the bind x, the rings, the cranks), as a minimal asset dict for cyborg_limb"""

    def __init__(self, path=MECH_GLB):
        G = gltf.read(path)
        j = G['json']
        p = j['meshes'][0]['primitives'][0]
        acc = G['accessor']
        self.V = acc(p['attributes']['POSITION']).astype(np.float64)
        self.N = acc(p['attributes']['NORMAL']).astype(np.float64)
        self.TAN = acc(p['attributes']['TANGENT']).astype(np.float64)
        self.UV = acc(p['attributes']['TEXCOORD_0']).astype(np.float64)
        self.F = acc(p['indices']).reshape(-1, 3).astype(np.int64)
        self.J = acc(p['attributes']['JOINTS_0']).astype(np.int64)
        self.Wt = acc(p['attributes']['WEIGHTS_0']).astype(np.float64)
        names = [n['name'] for n in j['nodes']]
        self.jnames = [names[i] for i in j['skins'][0]['joints']]
        self.ibm = acc(j['skins'][0]['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
        self.ext = j['extras']['bestiary']
        cy = self.ext['cardan']
        x = np.zeros(N_JOINTS)
        x[J0:] = self.ext['bind_x']
        self.chain = dict(x=x)
        self.des = dict(joints=list(self.jnames), ring=set(int(k) for k in cy['rings']),
                        act=set(int(k) for k in cy['actuators']), crest=set(int(k) for k in cy['crests']),
                        kn={int(k): dict(lc=float(v)) for k, v in cy['crank_lc'].items()})
        self.helpers = self.ext['helpers']
        self.table = self.ext['radius_table']
        self.X = np.array([x[CL.body_k(nm)] for nm in self.jnames])

    def pose(self, pos, F):
        """every skin joint's world transform for one pose of the octopus arm (pos (24, 3), F (24, 3, 3): its chord
        frames, the tip's own frame): cyborg_limb.pose_joints (the bones as given, the helpers by their rules)"""
        return CL.pose_joints(self.chain, self.des, pos, F)

    def posed(self, pos, F, which=None):
        """the low's vertices posed (linear blend skinning on the posed joints): V (n, 3) (rows `which` only)"""
        P, R, X = self.pose(pos, F)
        idx = np.arange(len(self.V)) if which is None else np.asarray(which)
        V = self.V[idx]
        out = np.zeros((len(idx), 3))
        for c in range(4):
            w = self.Wt[idx, c]
            m = w > 0.0
            if not m.any():
                continue
            jj = self.J[idx[m], c]
            loc = V[m] - np.column_stack([X[jj], np.zeros(m.sum()), np.zeros(m.sum())])
            out[m] += w[m, None] * (np.einsum('nij,nj->ni', R[jj], loc) + P[jj])
        return out


def mount_inverse_binds(oct_, mech, j):
    """THE MOUNT as the runtime builds it: per skin joint of the mech tentacle the octopus bone it rides (a bone
    arm_kk -> arm{j}_kk; a helper -> a new bone under its parent) and its inverse bind in the octopus's bind space:
    bone k [M_k | -M_k X_k] (M_k its chord frame in its own axes, M_23 = I), a helper T(-X_k). Returns (names, (n, 4, 4))"""
    M = oct_.chord_M(j)
    out, names = [], []
    for nm in mech.jnames:
        k = CL.body_k(nm)
        if CL.body_kind(nm) == 'bone':
            B = np.eye(4)
            B[:3, :3] = M[k]
            B[:3, 3] = -M[k] @ np.array([mech.chain['x'][k], 0.0, 0.0])
            names.append(f'arm{j}_{k:02d}')
        else:
            B = np.eye(4)
            B[0, 3] = -mech.chain['x'][k]
            names.append(f'arm{j}_{nm[4:]}')
        out.append(B)
    return names, np.stack(out)


def design_asset(arm=0):
    """the mech tentacle's design as C5a built it (cyborg_limb: arm 0's chain, the rest motion's limits, the design):
    the flange's and the band's programs read it (every arm's chain is the same, rotated)"""
    chain = CL.arm_chain(arm=arm)
    lim = CL.motion_limits(chain)
    return chain, lim, CL.design(chain, lim)


def pinned_weights(oct_, cutrec):
    """the RUNTIME'S PIN on the replaced arm (CYBORG_PLAN §4.4.2): the cut ring's and the ring before's vertices (every
    split copy) at weight 1 on joint cut - 1. Returns (J, W) for prim 0's vertex set with those rows replaced"""
    J, W = oct_.J.copy(), oct_.W.copy()
    b = oct_.bone[f'arm{cutrec["arm"]}_{cutrec["cut"] - 1:02d}']
    for v in np.concatenate([cutrec['ring'], cutrec['before']]):
        J[v] = [b, 0, 0, 0]
        W[v] = [1.0, 0.0, 0.0, 0.0]
    return J, W


def skin_band(oct_, cutrec, back=3):
    """the arm's KEPT triangles from the ring `back` rings before the cut ring up to it (the skin round the flange and
    just short of it: what can reach the roll), as indices into the low's F"""
    sh = arm_shares(oct_, cutrec['arm'])
    rs = sh['ring_s']
    ir = int(np.argmin(np.abs(rs - cutrec['ring_s'])))
    s_lo = float(rs[ir - back]) - 1.0e-4
    sv = np.full(len(oct_.low['V']), -1.0)
    sv[sh['arm_v']] = sh['s']
    fa = np.nonzero(oct_.region == 3 + cutrec['arm'])[0]
    S = sv[oct_.F[fa]]
    keep = (S >= s_lo).all(1) & ~(S >= cutrec['ring_s'] - 1.0e-4).all(1)
    return fa[keep], s_lo


def tri_samples(V, F, n=6):
    """points on triangles: barycentric grid of n subdivisions per triangle. Returns (bary (m, 3), tri index (m,))"""
    ii, jj = np.meshgrid(np.arange(n + 1), np.arange(n + 1))
    sel = ii + jj <= n
    a, b = ii[sel] / n, jj[sel] / n
    bc = np.column_stack([1.0 - a - b, a, b])
    return np.tile(bc, (len(F), 1)), np.repeat(np.arange(len(F)), len(bc))


def roll_tube(chain, des, n_phi=120, n_alpha=36):
    """the soft roll's surface (the asset frame: x from joint 7 along chord 7) as cyborg_limb.group_program builds it:
    the tube of radius roll / 2 round the loop (the flesh outline at roll_x, scaled to the taper there, pushed out
    roll / 2 - roll_sink along its normal). Returns points (n_phi, n_alpha, 3) and each loop point's angle phi about the
    chord (from the aboral side toward +z)"""
    D = CL.DESIGN
    fl = des['flange']
    rr = 0.5 * D['roll']
    th = np.linspace(0.0, TAU, n_phi, endpoint=False)
    r0 = chain['ring']['r_nominal']
    f = CL.flesh_profile(th) * r0
    Pf = np.column_stack([f * np.cos(th), f * np.sin(th)])
    d = np.roll(Pf, -1, 0) - np.roll(Pf, 1, 0)
    n = np.column_stack([d[:, 1], -d[:, 0]])
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    if (n * Pf).sum() < 0:
        n = -n
    r_roll = float(CL.radius_at(chain, fl['roll_x'])) / r0
    loop = Pf * r_roll + (rr - D['roll_sink']) * n
    al = np.linspace(0.0, TAU, n_alpha, endpoint=False)
    out = np.zeros((n_phi, n_alpha, 3))
    for i in range(n_phi):
        c = np.array([fl['roll_x'], loop[i, 0], loop[i, 1]])
        nn = np.array([0.0, n[i, 0], n[i, 1]])
        out[i] = c + rr * (np.cos(al)[:, None] * nn + np.sin(al)[:, None] * np.array([1.0, 0.0, 0.0]))
    return out, np.arctan2(loop[:, 1], loop[:, 0])


def point_tri_signed(P, A, B, C, chunk=2048):
    """the signed distance from points P (n, 3) to a triangle soup (A, B, C (m, 3)): the closest triangle's distance,
    signed by its face normal (outward by the soup's winding). Brute force, chunked"""
    P = np.asarray(P, np.float64)
    out = np.full(len(P), np.inf)
    sgn = np.ones(len(P))
    nrm = np.cross(B - A, C - A)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-30)
    for i0 in range(0, len(P), chunk):
        p = P[i0:i0 + chunk][:, None, :]
        ab, ac, ap = (B - A)[None], (C - A)[None], p - A[None]
        d1, d2 = (ab * ap).sum(2), (ac * ap).sum(2)
        bp = p - B[None]
        d3, d4 = (ab * bp).sum(2), (ac * bp).sum(2)
        cp = p - C[None]
        d5, d6 = (ab * cp).sum(2), (ac * cp).sum(2)
        va = d3 * d6 - d5 * d4
        vb = d5 * d2 - d1 * d6
        vc = d1 * d4 - d3 * d2
        den = np.maximum(va + vb + vc, 1e-30)
        v = vb / den
        w = vc / den
        qp = A[None] + ab * v[..., None] + ac * w[..., None]
        inside = (va >= 0) & (vb >= 0) & (vc >= 0)
        # outside the face: the nearest point of its three edges
        qe_best, de_best = None, None
        for (e0, e1) in ((A, B), (B, C), (C, A)):
            e = (e1 - e0)[None]
            t = np.clip(((p - e0[None]) * e).sum(2) / np.maximum((e * e).sum(2), 1e-30), 0.0, 1.0)
            qe = e0[None] + e * t[..., None]
            de = np.linalg.norm(p - qe, axis=2)
            if qe_best is None:
                qe_best, de_best = qe, de
            else:
                b_ = de < de_best
                qe_best = np.where(b_[..., None], qe, qe_best)
                de_best = np.where(b_, de, de_best)
        q = np.where(inside[..., None], qp, qe_best)
        dist = np.linalg.norm(p - q, axis=2)
        k = dist.argmin(1)
        r = np.arange(len(k))
        out[i0:i0 + len(k)] = dist[r, k]
        sgn[i0:i0 + len(k)] = np.sign(((p[:, 0] - q[r, k]) * nrm[k]).sum(1) + 1e-30)
    return out * sgn


def helper_locals(oct_, mech, j, F_parent_child):
    """the runtime's helper rule as LOCAL transforms (what bestiary.js writes into each new bone): per helper (name, its
    parent's name, 4x4 local) from the knuckle's relative rotation R = F_{k-1}^T F_k (cardan_angles); the forge's
    reference is pose_joints (world). F_parent_child: per knuckle k the relative rotation (3, 3). Returns a list"""
    M = oct_.chord_M(j)
    Tl = oct_.rig.T
    out = []
    for h in mech.helpers:
        k, kind = int(h['knuckle']), h['kind']
        yw, pt, rl = (float(v) for v in CL.cardan_angles(F_parent_child[k]))
        L = np.eye(4)
        if kind in ('cross', 'crest'):
            L[:3, :3] = M[k - 1] @ CL.rot_y(yw if kind == 'cross' else 0.5 * yw)
            L[:3, 3] = Tl[oct_.rig.index[f'arm{j}_{k:02d}']]
        elif kind == 'shell':
            L[:3, :3] = M[k] @ CL.rot_x(-rl)
        elif kind == 'rod':
            d = np.array([mech.des['kn'][k]['lc'] * math.sin(pt), 0.0, 0.0])
            if h['parent'].endswith('_shell'):
                L[:3, 3] = d
            else:
                L[:3, :3] = M[k]
                L[:3, 3] = M[k] @ d
        out.append((f'arm{j}_{h["name"][4:]}', h['parent'], L))
    return out


def runtime_mech_mats(oct_, mech, j, Wa):
    """THE RUNTIME'S MOUNT for one frame, as bestiary.js builds it (mountCyborgParts + poseHelpers): every skin joint of
    the mech tentacle's matrix (the octopus bone's world x its inverse bind; a helper's world from its parent's x its
    rule's local x T(-X_k)). Wa: arm j's 24 bone worlds (4x4). Returns (n, 4, 4) in mech.jnames' order"""
    names, IB = mount_inverse_binds(oct_, mech, j)
    M = oct_.chord_M(j)
    F = np.einsum('kab,kbc->kac', Wa[:, :3, :3], M)
    Frel = {k: F[k - 1].T @ F[k] for k in range(1, N_JOINTS)}
    loc = {nm: (par, L) for nm, par, L in helper_locals(oct_, mech, j, Frel)}
    world = {f'arm{j}_{k:02d}': Wa[k] for k in range(N_JOINTS)}

    def W_of(nm):
        if nm not in world:
            par, L = loc[nm]
            world[nm] = W_of(f'arm{j}_{par[4:]}') @ L
        return world[nm]
    return np.stack([W_of(nm) @ B for nm, B in zip(names, IB)])


# ============================================================================================ the gates' tools
def closest_on_tri(p, a, b, c):
    """the closest point on triangles (a, b, c) to points p, broadcast over leading axes (..., 3) (Ericson's Voronoi
    regions, the face last overwritten by the edges and the corners in their priority)"""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    bp = p - b
    d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    cp = p - c
    d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    safe = lambda x: np.where(np.abs(x) < 1e-30, 1e-30, x)
    den = safe(va + vb + vc)
    q = a + ab * (vb / den)[..., None] + ac * (vc / den)[..., None]
    t = (d4 - d3) / safe((d4 - d3) + (d5 - d6))
    q = np.where(((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0))[..., None], b + (c - b) * t[..., None], q)
    t = d2 / safe(d2 - d6)
    q = np.where(((vb <= 0) & (d2 >= 0) & (d6 <= 0))[..., None], a + ac * t[..., None], q)
    q = np.where(((d6 >= 0) & (d5 <= d6))[..., None], c, q)
    t = d1 / safe(d1 - d3)
    q = np.where(((vc <= 0) & (d1 >= 0) & (d3 <= 0))[..., None], a + ab * t[..., None], q)
    q = np.where(((d3 >= 0) & (d4 <= d3))[..., None], b, q)
    q = np.where(((d1 <= 0) & (d2 <= 0))[..., None], a, q)
    return q


def point_tri_near(P, A, B, C, k=10, tree=None):
    """the signed distance from points P (n, 3) to a closed triangle soup (A, B, C (m, 3), outward winding), exact over
    each point's k nearest triangles by centroid: the closest one's distance, signed by the summed face normals of the
    candidates sharing the closest point (an edge's or a corner's pseudo-normal). Returns (sd (n,), triangle (n,))"""
    from scipy.spatial import cKDTree
    P = np.asarray(P, np.float64)
    if tree is None:
        tree = cKDTree((A + B + C) / 3.0)
    k = min(k, len(A))
    _, idx = tree.query(P, k=k)
    idx = np.asarray(idx).reshape(len(P), k)
    a, b, c = A[idx], B[idx], C[idx]
    q = closest_on_tri(P[:, None, :], a, b, c)
    d = np.linalg.norm(P[:, None, :] - q, axis=2)
    i = d.argmin(1)
    r = np.arange(len(P))
    dmin = d[r, i]
    nrm = np.cross(b - a, c - a)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-30)
    share = d <= dmin[:, None] + 1e-9
    nav = (nrm * share[..., None]).sum(1)
    sgn = np.sign(((P - q[r, i]) * nav).sum(1) + 1e-30)
    return dmin * sgn, idx[r, i]


def rest_node_worlds(oct_, nodes, seeds, ts, H=None, replaced=None, lower=REST_LOWER):
    """the named nodes' worlds over the runtime's rest motion, every seed x every time (seed-major): (n_frames,
    len(nodes), 4, 4). Each arm a node belongs to is solved once per seed over all times (the replaced arm with the
    ground profile H); the other nodes per time under the lowered body with the mantle and the funnel breathing
    (rest_pose_overrides; a node under an arm bone is not supported)"""
    rg = oct_.rig
    ts = np.asarray(ts, np.float64)
    idx = [rg.index[n] for n in nodes]
    arm_of = {}
    for c, n in enumerate(nodes):
        a, _, k = n.partition('_')
        if a.startswith('arm') and a[3:].isdigit() and k.isdigit():
            arm_of[c] = (int(a[3:]), int(k))
    base = np.zeros((len(ts), len(nodes), 4, 4))
    for i, t in enumerate(ts):
        base[i] = rg.worlds(rest_pose_overrides(oct_, float(t), lower))[idx]
    arms = sorted({a for a, _ in arm_of.values()})
    out = []
    for seed in seeds:
        fr = base.copy()
        for j in arms:
            pos, F = solve_arm(oct_.arm_bind(j)['P'], ts, j, seed, lower=lower, H=H if j == replaced else None,
                               reach=oct_.flesh_reach(j))
            Wa = arm_bone_worlds(oct_, j, pos, F)
            for c, (a, k) in arm_of.items():
                if a == j:
                    fr[:, c] = Wa[:, k]
        out.append(fr)
    return np.concatenate(out)


def swim_node_worlds(oct_, nodes, ts):
    """the named nodes' worlds over t12's swim rig: (len(ts), len(nodes), 4, 4)"""
    idx = [oct_.rig.index[n] for n in nodes]
    sp = swim_params()
    return np.stack([swim_worlds(oct_, float(t), sp)[idx] for t in ts])


def flange_envelope(V, F, x0, x1, dx=0.25e-3, nphi=144, n=8):
    """the flange's OUTER envelope about chord 7 (the asset frame: x along it, phi from the aboral +y toward +z): per
    (x, phi) bin the largest radius of its surface (triangles sampled n per edge); a skin point at (x, phi, rho) with rho
    under it is under the flange's skin of metal and rubber, one over it shows through. Empty bins take their phi
    neighbours'. Returns (R (nx, nphi), x0, dx, nphi)"""
    bc, ti = tri_samples(V, F, n)
    P = (bc[:, :, None] * V[F[ti]]).sum(1)
    x = P[:, 0]
    keep = (x >= x0) & (x <= x1)
    P = P[keep]
    nx = int(math.ceil((x1 - x0) / dx)) + 1
    ix = np.clip(((P[:, 0] - x0) / dx).astype(int), 0, nx - 1)
    ip = (((np.arctan2(P[:, 2], P[:, 1]) % TAU) / TAU) * nphi).astype(int) % nphi
    R = np.full((nx, nphi), -np.inf)
    np.maximum.at(R, (ix, ip), np.hypot(P[:, 1], P[:, 2]))
    for _ in range(nphi):
        bad = ~np.isfinite(R)
        if not bad.any():
            break
        R = np.where(bad, np.maximum(np.roll(R, 1, 1), np.roll(R, -1, 1)), R)
    return R, x0, dx, nphi


def envelope_excess(Q, env):
    """points Q (n, 3) in the asset frame against flange_envelope's R: rho - R at their bin (> 0: outside the flange's
    outer surface), nan for points outside its x span"""
    R, x0, dx, nphi = env
    ix = np.floor((Q[:, 0] - x0) / dx).astype(int)
    ok = (ix >= 0) & (ix < R.shape[0])
    ip = (((np.arctan2(Q[:, 2], Q[:, 1]) % TAU) / TAU) * nphi).astype(int) % nphi
    out = np.full(len(Q), np.nan)
    out[ok] = np.hypot(Q[ok, 1], Q[ok, 2]) - R[ix[ok], ip[ok]]
    return out
