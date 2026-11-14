"""PORTS: openings in a cage grid that grow a designed structure (an eye socket, a funnel, a nostril, a horn root).

cut(mesh, faces) removes a block of faces and returns the hole's boundary loop, ordered the way the REMAINING faces
run along it (boundary_loop's order). extend(mesh, loop, rings) adds rings of new vertices, ring m's vertex i
corresponding to the loop's vertex i (positions designed per loop vertex: no alignment search), each band of quads
(X[i+1], X[i], Y[i], Y[i+1]) running against the ring before it, so a chain of rings stays consistently wound and a
cap closes the last one (loft.cap picks its winding topologically).

loop_frame gives each loop vertex's angle about a port's axis (for designing rings: the lid's ellipse, a funnel's
circle) in the plane perpendicular to the axis, the reference direction projected off it.
"""
import numpy as np

from .loft import boundary_loop
from .mesh import QuadMesh


def cut(mesh: QuadMesh, faces):
    faces = np.unique(np.asarray(faces, np.int64))
    keep = np.ones(len(mesh.Q), bool)
    keep[faces] = False
    before = {tuple(l) for l in []}
    out = QuadMesh(mesh.V, mesh.Q[keep], mesh.attrs)
    removed_verts = set(np.unique(mesh.Q[faces]).tolist())
    loops = [l for l in boundary_loop(out) if set(l) & removed_verts]
    assert len(loops) == 1, f'expected one hole loop, found {len(loops)}'
    return out, np.array(loops[0])


def extend(mesh: QuadMesh, loop, rings, attrs=None):
    """rings: list of (len(loop), 3) position arrays; attrs: optional dict name -> list of per-ring arrays (else the
    loop's values are copied). Returns the mesh and the list of ring id arrays (the loop first)."""
    loop = np.asarray(loop)
    K = len(loop)
    V = [mesh.V]
    A = {k: [a] for k, a in mesh.attrs.items()}
    ids = [loop]
    nid = len(mesh.V)
    Q = [mesh.Q]
    for m, pos in enumerate(rings):
        pos = np.asarray(pos, np.float64).reshape(K, 3)
        V.append(pos)
        for k, a in mesh.attrs.items():
            A[k].append(attrs[k][m] if attrs and k in attrs else a[loop])
        new = np.arange(nid, nid + K)
        nid += K
        X, Y = ids[-1], new
        i1 = (np.arange(K) + 1) % K
        Q.append(np.column_stack([X[i1], X, Y, Y[i1]]))
        ids.append(new)
    out = QuadMesh(np.vstack(V), np.vstack(Q), {k: np.vstack(v) for k, v in A.items()})
    return out, ids


def rounding_ring(V, loop, center, axis, ref, amount=0.7, lift=0.0):
    """the first ring off a port's loop: each loop vertex's distance from the axis eased `amount` of the way to the
    loop's mean (the grid block's rectangle -> a circle), its height along the axis kept, lifted by `lift`. A cut
    block's corners meeting a round tube directly make skewed corner quads, spiked after subdivision (t05's funnel)"""
    ang, (e1, e2, ax) = loop_frame(V, loop, center, axis, ref)
    q = V[loop] - center
    h = q @ ax
    rho = np.linalg.norm(q - np.outer(h, ax), axis=1)
    r_new = rho + amount * (rho.mean() - rho)
    d = np.cos(ang)[:, None] * e1 + np.sin(ang)[:, None] * e2
    return center + np.outer(h + lift, ax) + r_new[:, None] * d


def cone_footprint(base_prog, ang, frame, a, b, ra, rb, t_range=(-0.4, 0.8), samples=96, lift=0.0015,
                   return_t=False):
    """where a cone (axis a -> b, radii ra -> rb) leaves a base surface: per angle (about the cone's axis, in
    `frame` = (e1, e2, axis) as loop_frame returns it), the first point along the cone's surface line, from inside
    the base outward, where the base's field turns positive; lifted `lift` along the base's normal. The TRUE junction
    curve of an oblique branch (t05's funnel: rounding the cut loop toward a circle about the axis folded the band at
    the top of an oblique footprint)"""
    e1, e2, ax = frame
    ts = np.linspace(t_range[0], t_range[1], samples)
    d = np.cos(ang)[:, None] * e1 + np.sin(ang)[:, None] * e2
    r = ra + (rb - ra) * ts
    P = a[None, None, :] + (b - a)[None, None, :] * ts[None, :, None] + r[None, :, None] * d[:, None, :]
    f = base_prog.eval(P.reshape(-1, 3)).reshape(len(ang), samples)
    out = np.zeros((len(ang), 3))
    tout = np.zeros(len(ang))
    for i in range(len(ang)):
        k = np.nonzero((f[i, :-1] <= 0) & (f[i, 1:] > 0))[0]
        k = k[0] if len(k) else int(np.argmin(np.abs(f[i])))
        if k + 1 < samples and f[i, k + 1] != f[i, k]:
            u = -f[i, k] / (f[i, k + 1] - f[i, k])
        else:
            u = 0.0
        out[i] = P[i, k] * (1 - u) + P[i, min(k + 1, samples - 1)] * u
        tout[i] = ts[k] * (1 - u) + ts[min(k + 1, samples - 1)] * u
    if lift:
        out = out + base_prog.normals(out) * lift
    return (out, tout) if return_t else out


def loop_frame(V, loop, center, axis, ref):
    """per loop vertex: its angle about axis (radians, from ref toward axis x ref), and the frame (e1, e2, axis)"""
    axis = np.asarray(axis, np.float64)
    axis /= np.linalg.norm(axis)
    e1 = np.asarray(ref, np.float64) - np.dot(ref, axis) * axis
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    q = V[loop] - center
    ang = np.arctan2(q @ e2, q @ e1)
    return ang, (e1, e2, axis)
