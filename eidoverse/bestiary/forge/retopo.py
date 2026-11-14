"""Fitting a designed cage to the anatomy: proxies projected onto the SDF, then tangential relaxation (umbrella
smoothing in the tangent plane) with re-projection, so the designed edge flow lands evenly spaced on the shape.

Pinned vertices (feature loops: a web's rim, a lid's edge, a seam ring) are projected but never relaxed.
"""
import numpy as np


def neighbours(Q, n):
    """vertex adjacency through quad edges as a CSR pair (ptr, idx)"""
    d = np.stack([Q, np.roll(Q, -1, axis=1)], -1).reshape(-1, 2)
    d = np.concatenate([d, d[:, ::-1]])
    d = np.unique(d, axis=0)
    order = np.argsort(d[:, 0], kind='stable')
    d = d[order]
    ptr = np.zeros(n + 1, np.int64)
    np.add.at(ptr, d[:, 0] + 1, 1)
    ptr = np.cumsum(ptr)
    return ptr, d[:, 1]


def umbrella(V, ptr, idx):
    cnt = np.diff(ptr)
    S = np.zeros_like(V)
    np.add.at(S, np.repeat(np.arange(len(V)), cnt), V[idx])
    return S / np.maximum(cnt, 1)[:, None]


def edge_scale(V, ptr, idx):
    """each vertex's mean incident edge length"""
    cnt = np.diff(ptr)
    src = np.repeat(np.arange(len(V)), cnt)
    el = np.linalg.norm(V[idx] - V[src], axis=1)
    return np.bincount(src, el, minlength=len(V)) / np.maximum(cnt, 1)


def fit(mesh, prog, iters=6, relax=0.5, pinned=None, maxd=0.06, first_dirs=None, preserve=True, fixed=None):
    """project every vertex along the field's gradient (the nearest surface), then `iters` rounds of SAFEGUARDED
    tangential relaxation: each free vertex moves `relax` of the way toward its neighbours' mean within its tangent
    plane, clamped to a quarter of its mean edge, and is re-projected; the move is KEPT only if the re-projection is
    short (< 0.3 edge) and the normal turns < 37 deg, else the vertex stays (t04: unguarded moves slid vertices over a
    web rim or round a thin arm onto another sheet: 21-30 mm dents). Returns the last status counts and the share of
    moves accepted per round. first_dirs (n, 3), NaN where unset: the first projection's ray for chosen vertices (a
    web rim's vertices go out in the web's plane: the gradient would drop them onto a face of the membrane)."""
    n = len(mesh.V)
    pin = np.zeros(n, bool) if pinned is None else np.asarray(pinned, bool).copy()
    # fixed: designed off the shape (an eyelid's edge on its eyeball, a funnel's lumen): never projected or relaxed
    fix = np.zeros(n, bool) if fixed is None else np.asarray(fixed, bool)
    pin |= fix
    V_fixed = mesh.V[fix].copy()
    ptr, idx = neighbours(mesh.Q, n)
    # preserve: relax toward the DESIGNED differential coordinates (the proxies' umbrella offsets), not toward
    # uniform spacing: a layout that is intentionally uneven (rows compressing into a scalloped margin) stays so, and
    # only the projection's noise is smoothed (t04: uniform pull dragged the rows next to a pinned rim onto it)
    delta0 = (umbrella(mesh.V, ptr, idx) - mesh.V) if preserve else 0.0
    g = prog.normals(mesh.V)
    if first_dirs is not None:
        has = ~np.isnan(first_dirs[:, 0])
        g[has] = first_dirs[has]
    mesh.V, st = prog.project(mesh.V, g, maxd=maxd)
    mesh.V[fix] = V_fixed
    accepted = []
    for _ in range(iters):
        N = prog.normals(mesh.V)
        L = umbrella(mesh.V, ptr, idx) - mesh.V - delta0
        L -= (L * N).sum(1, keepdims=True) * N             # tangential only
        h = edge_scale(mesh.V, ptr, idx)
        step = relax * L
        ln = np.linalg.norm(step, axis=1)
        step *= np.minimum(1.0, 0.25 * h / np.maximum(ln, 1e-12))[:, None]
        Vm = mesh.V + step * (~pin)[:, None]
        Vp, st = prog.project(Vm, prog.normals(Vm), maxd=maxd)
        Np = prog.normals(Vp)
        ok = (np.linalg.norm(Vp - Vm, axis=1) < 0.3 * h) & ((N * Np).sum(1) > 0.8) & (st == 0) & ~pin
        mesh.V = np.where(ok[:, None], Vp, mesh.V)
        accepted.append(float(ok[~pin].mean()))
    return np.bincount(st, minlength=3), accepted
