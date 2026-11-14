"""The HIGH: the fitted cage subdivided (Catmull-Clark, the sparse operator) and projected EXACTLY onto the anatomy
SDF along its own normals (the parameterization is the low's own: bake rays meet it near-orthogonally), the fixed
regions (designed off the shape: a lid's tuck, a funnel's lumen) kept where subdivision puts them, blended across the
attribute 'fixed'.

Detail displacement comes after (detail.py): the high returned here is the clean anatomical surface.
"""
import numpy as np
import scipy.sparse as sp

from . import subdiv


def adjacency(Q, n):
    """the row-normalised vertex adjacency through quad edges (sparse): A @ V = each vertex's neighbours' mean"""
    d = np.stack([Q, np.roll(Q, -1, axis=1)], -1).reshape(-1, 2)
    d = np.unique(np.concatenate([d, d[:, ::-1]]), axis=0)
    A = sp.csr_matrix((np.ones(len(d)), (d[:, 0], d[:, 1])), shape=(n, n))
    deg = np.asarray(A.sum(1)).ravel()
    return sp.diags(1.0 / np.maximum(deg, 1)) @ A


def build(cage, prog, levels=3, maxd=0.02, creases=None, relax_iters=3, relax=0.5):
    """subdivide, project along the normals, then `relax_iters` rounds of tangential smoothing re-projected (the
    projection's per-vertex noise, a fold of one tiny quad here and there, shading streaks: t05) with each move
    kept only where the re-projection is short. Fixed regions are blended out of every move."""
    hi, parent = subdiv.subdivide(cage, levels, creases=creases)
    n0 = hi.vertex_normals()
    P, st = prog.project(hi.V, n0, maxd=maxd)
    w = hi.attrs['fixed'][:, 0] if 'fixed' in hi.attrs else np.zeros(len(hi.V))
    w = np.clip(w, 0.0, 1.0)[:, None]
    hi.V = P * (1.0 - w) + hi.V * w
    if relax_iters:
        A = adjacency(hi.Q, len(hi.V))
        crease_v = np.zeros(len(hi.V), bool)
        if getattr(hi, 'creases', None) is not None and len(hi.creases):
            crease_v[np.unique(hi.creases)] = True       # a membrane's rim stays put
        for _ in range(relax_iters):
            N = hi.vertex_normals()
            L = A @ hi.V - hi.V
            L -= (L * N).sum(1, keepdims=True) * N
            Vm = hi.V + relax * L * (1.0 - w) * (~crease_v)[:, None]
            Vp, st = prog.project(Vm, N, maxd=0.003)
            ok = (np.linalg.norm(Vp - Vm, axis=1) < 0.0006) & (st == 0)
            hi.V = np.where(ok[:, None], Vp * (1.0 - w) + Vm * w, hi.V)
    return hi, parent, st
