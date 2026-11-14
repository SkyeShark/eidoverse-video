"""Look-only previews (for my eyes, never shipped): the SDF program's zero set by marching cubes on a GPU-evaluated
grid. The delivered meshes never come from here (the designed cage + projection make them)."""
import numpy as np


def sdf_mesh(prog, lo, hi, res=0.002, chunk=4_000_000):
    """marching cubes of prog over the box lo..hi at spacing res (m); returns V, F"""
    from skimage.measure import marching_cubes
    lo = np.asarray(lo, np.float64)
    hi = np.asarray(hi, np.float64)
    n = np.ceil((hi - lo) / res).astype(int) + 1
    xs = [lo[k] + np.arange(n[k]) * res for k in range(3)]
    G = np.stack(np.meshgrid(*xs, indexing='ij'), -1).reshape(-1, 3)
    vals = np.concatenate([prog.eval(G[i:i + chunk]) for i in range(0, len(G), chunk)])
    vol = vals.reshape(n)
    V, F, _, _ = marching_cubes(vol, 0.0, spacing=(res, res, res))
    return V + lo, F[:, ::-1].copy()
