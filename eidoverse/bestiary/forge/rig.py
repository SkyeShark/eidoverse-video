"""RIGGING helpers (the animation craft guide, chapters 05-06: cited as AG 06.4 etc.): a skeleton of named joints with
rest world frames, weight fields kept to the invariants, linear blend skinning for verification.

Invariants (AG 00.43): weights non-negative, summing to one, every vertex weighted, identical on coincident vertices
(weights live on the WELDED mesh and are scattered to split copies), at most four influences cut CONTINUOUSLY (the
fifth-largest weight is subtracted before renormalising, so weights do not jump where ranks swap).
"""
import numpy as np


class Skeleton:
    def __init__(self):
        self.names, self.parent, self.world = [], [], []

    def add(self, name, parent, pos, frame=None):
        """a joint at pos (world) with its rest frame (3x3, columns = local x, y, z in world); parent: name or None"""
        W = np.eye(4)
        W[:3, :3] = np.eye(3) if frame is None else np.asarray(frame, np.float64)
        W[:3, 3] = pos
        self.names.append(name)
        self.parent.append(-1 if parent is None else self.names.index(parent))
        self.world.append(W)
        return len(self.names) - 1

    def index(self, name):
        return self.names.index(name)

    def local(self, i):
        p = self.parent[i]
        return self.world[i] if p < 0 else np.linalg.inv(self.world[p]) @ self.world[i]

    def posed_world(self, local_rot):
        """world matrices for local rotations {joint index: 3x3} applied in each joint's rest local frame"""
        out = [None] * len(self.names)
        for i in range(len(self.names)):          # parents are always added before their children
            L = self.local(i).copy()
            if i in local_rot:
                L[:3, :3] = L[:3, :3] @ local_rot[i]
            p = self.parent[i]
            out[i] = L if p < 0 else out[p] @ L
        return out

    def skin_matrices(self, local_rot):
        Wp = self.posed_world(local_rot)
        return np.stack([Wp[i] @ np.linalg.inv(self.world[i]) for i in range(len(self.names))])


def frame_from(x, up):
    """a right-handed frame whose x is the given direction and whose y is up made orthogonal to it"""
    x = np.asarray(x, np.float64)
    x = x / np.linalg.norm(x)
    y = np.asarray(up, np.float64) - x * np.dot(up, x)
    if np.linalg.norm(y) < 1e-9:
        y = np.cross(x, [0.0, 0.0, 1.0])
    y /= np.linalg.norm(y)
    return np.column_stack([x, y, np.cross(x, y)])


def hat_weights(s, joints_s):
    """a ramp along the anatomy (AG 00.45): each vertex blends the two bones whose segment midpoints bracket it;
    bone k owns the segment from joint k to joint k+1; before the first midpoint bone 0, past the last the last bone.
    Returns (k0, k1, t) arrays"""
    js = np.asarray(joints_s, np.float64)
    mids = 0.5 * (js[:-1] + js[1:])
    mids = np.concatenate([mids, [js[-1] + (js[-1] - mids[-1])]])
    s = np.asarray(s, np.float64)
    k1 = np.clip(np.searchsorted(mids, s), 0, len(mids) - 1)
    k0 = np.maximum(k1 - 1, 0)
    lo = np.where(k1 > 0, mids[k0], mids[0] - 1.0)
    t = np.clip((s - lo) / np.maximum(mids[k1] - lo, 1e-12), 0.0, 1.0)
    t = np.where(k1 == 0, 1.0, t)
    t = t * t * (3.0 - 2.0 * t)
    return k0, k1, t


def smooth_field(W, Q, iters=4, alpha=0.5, pinned=None):
    """Laplacian smoothing of a per-vertex weight field (n, J) over the quad mesh's edges (AG 00.45: smooth the whole
    field last); pinned vertices keep their weights"""
    n = len(W)
    e = np.concatenate([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]]])
    e = np.unique(np.sort(e, axis=1), axis=0)
    import scipy.sparse as sp
    A = sp.coo_matrix((np.ones(2 * len(e)), (np.concatenate([e[:, 0], e[:, 1]]), np.concatenate([e[:, 1], e[:, 0]]))),
                      shape=(n, n)).tocsr()
    deg = np.asarray(A.sum(1)).ravel()
    deg[deg == 0] = 1.0
    for _ in range(iters):
        M = (A @ W) / deg[:, None]
        Wn = (1 - alpha) * W + alpha * M
        if pinned is not None:
            Wn[pinned] = W[pinned]
        W = Wn
    return W


def limit_influences(W, k=4):
    """the top k per vertex with a continuous cut (subtract the (k+1)-th largest), renormalised: (joints, weights)"""
    W = np.maximum(W, 0.0)
    order = np.argsort(-W, axis=1)
    top = np.take_along_axis(W, order[:, :k + 1], axis=1)
    cut = top[:, k:k + 1] if top.shape[1] > k else np.zeros((len(W), 1))
    w = np.maximum(top[:, :k] - cut, 0.0)
    s = w.sum(1, keepdims=True)
    bad = s[:, 0] <= 1e-12
    w = np.where(bad[:, None], np.eye(1, k).repeat(len(W), 0), w / np.maximum(s, 1e-12))
    return order[:, :k].astype(np.int32), w.astype(np.float32)


def lbs(V, joints, weights, M):
    """linear blend skinning: V (n, 3), joints/weights (n, 4), skin matrices M (J, 4, 4)"""
    Vh = np.concatenate([V, np.ones((len(V), 1))], 1)
    out = np.zeros((len(V), 3))
    for c in range(joints.shape[1]):
        Mc = M[joints[:, c]]
        out += weights[:, c:c + 1] * np.einsum('nij,nj->ni', Mc, Vh)[:, :3]
    return out


def check_weights(joints, weights, n_joints):
    """the invariants as numbers: every vertex weighted, sums, negatives, indices in range"""
    s = weights.sum(1)
    return dict(min_sum=float(s.min()), max_sum=float(s.max()), negatives=int((weights < 0).sum()),
                unweighted=int((s < 0.999).sum()), bad_index=int(((joints < 0) | (joints >= n_joints)).sum()))
