"""STABLE ROOTS on a base's low: (triangle index, barycentrics), never a global draw.

The crystals' lesson (growth.py: placement follows the cage's site count, so every cage change re-rolls every crystal):
a coat root here is a pure function of (seed, its triangle, its slot k on that triangle) and the triangle's area:
  * each triangle t holds n_t = floor(area_t x d_max x oversample + h(t, 0)) CANDIDATE slots, h the forge's lowbias32
    hash (bestiary.js hash01's twin), so the slots of a triangle depend on nothing but that triangle;
  * slot k sits at an R2 low-discrepancy point (Roberts 2018, plastic-number steps) rotated by h(t, 1..2) and warped
    to the triangle (the sqrt map), so a triangle's slots spread evenly (blue-ish within it);
  * a slot is KEPT when h(t, k, 4) < density(p) x mask(p) / d_max: thinning by the spec's maps, still per slot;
  * optional Poisson thinning (clump centres, cards): slots in their hash PRIORITY order, each kept unless a kept slot
    of higher priority lies within r(p) = alpha / sqrt(density(p)). A decision depends only on its neighbours, so an
    edit far away changes nothing here.
Roots are then DATA (groom.npz: tri, bary): a refit that keeps the topology re-evaluates their positions from the same
(tri, bary) (they ride the surface); a graft carries them with its donor's triangles; only a new spec (density, masks)
or a new seed re-draws, and then only where the maps changed.
"""
import numpy as np

from .fields import Pts

M32 = np.uint64(0xFFFFFFFF)


def h32(x):
    """lowbias32 on uint64 arrays holding uint32 values (the forge's / bestiary.js's integer hash)"""
    x = np.asarray(x, np.uint64) & M32
    x ^= x >> np.uint64(16)
    x = (x * np.uint64(0x7FEB352D)) & M32
    x ^= x >> np.uint64(15)
    x = (x * np.uint64(0x846CA68B)) & M32
    x ^= x >> np.uint64(16)
    return x


def hash01(i, seed):
    """bestiary.js hash01(i, seed): to [0, 1)"""
    i = np.asarray(i, np.uint64) & M32
    s = np.asarray(seed, np.uint64) & M32
    x = ((i * np.uint64(0x9E3779B1)) & M32) ^ ((s * np.uint64(0x85EBCA77)) & M32)
    return (h32(x) >> np.uint64(8)).astype(np.float64) / 16777216.0


def hkey(seed, tri, k=0, ch=0):
    """a stable hash in [0, 1) of (seed, triangle, slot, channel)"""
    a = h32(np.asarray(tri, np.uint64) * np.uint64(2654435761) + np.uint64(seed) * np.uint64(97))
    b = h32(a ^ (np.asarray(k, np.uint64) * np.uint64(0x27D4EB2F) + np.uint64(ch) * np.uint64(0x165667B1)))
    return hash01(b, seed)


_G = 1.32471795724474602596        # the plastic number: R2's steps
_A1, _A2 = 1.0 / _G, 1.0 / (_G * _G)


def candidates(base, d_max_cm2, seed, oversample=1.0, tris=None):
    """every candidate slot: (tri, k, bary); d_max in roots per cm2"""
    tris = np.arange(len(base.F)) if tris is None else np.asarray(tris, np.int64)
    lam = base.area[tris] * 1.0e4 * d_max_cm2 * oversample
    n = np.floor(lam + hkey(seed, tris, 0, 0)).astype(np.int64)
    tri = np.repeat(tris, n)
    starts = np.repeat(np.cumsum(n) - n, n)
    k = np.arange(len(tri)) - starts
    u = (hkey(seed, tri, 0, 1) + _A1 * (k + 1)) % 1.0
    v = (hkey(seed, tri, 0, 2) + _A2 * (k + 1)) % 1.0
    su = np.sqrt(u)
    bary = np.column_stack([1.0 - su, su * (1.0 - v), su * v])
    return tri, k, bary


def poisson_keep(P, r, prio):
    """greedy Poisson-disk selection in priority order (highest first): keep i unless a kept point lies within
    max(r_i, r_j); returns the kept indices"""
    from scipy.spatial import cKDTree
    order = np.argsort(-prio, kind='stable')
    tree = cKDTree(P)
    kept = np.zeros(len(P), bool)
    rmax = float(r.max())
    rank = np.empty(len(P), np.int64)
    rank[order] = np.arange(len(P))
    nbrs = tree.query_ball_point(P, rmax)
    for i in order:
        ok = True
        ri = r[i]
        for j in nbrs[i]:
            if kept[j] and rank[j] < rank[i]:
                d = np.linalg.norm(P[i] - P[j])
                if d < max(ri, r[j]):
                    ok = False
                    break
        kept[i] = ok
    return np.nonzero(kept)[0]


def roots(base, fields, density, mask, d_max_cm2, seed, oversample=1.0, poisson_alpha=None):
    """the kept roots as Pts (tri, bary and their surface data) plus the per-root density (per cm2).
    density: a fields expression in roots per cm2; mask: an expression in 0..1 (domain x (1 - bare))"""
    tri, k, bary = candidates(base, d_max_cm2, seed, oversample)
    pts = Pts(base, tri, bary)
    d = np.clip(fields.eval(density, pts), 0.0, None)
    m = np.clip(fields.eval(mask, pts), 0.0, 1.0)
    p = np.clip(d * m / (d_max_cm2 * oversample if poisson_alpha is None else d_max_cm2), 0.0, 1.0)
    if poisson_alpha is not None:
        p = np.clip(p * oversample, 0.0, 1.0)
    keep = hkey(seed, tri, k, 4) < p
    tri, k, bary, d = tri[keep], k[keep], bary[keep], d[keep]
    if poisson_alpha is not None and len(tri):
        P = base.tri_points(tri, bary)[0]
        r = poisson_alpha / np.sqrt(np.maximum(d, 1e-6) * 1.0e4)       # metres (density per m2)
        sel = poisson_keep(P, r, hkey(seed, tri, k, 3))
        tri, k, bary, d = tri[sel], k[sel], bary[sel], d[sel]
    out = Pts(base, tri, bary)
    out.slot = k
    out.density = d
    return out
