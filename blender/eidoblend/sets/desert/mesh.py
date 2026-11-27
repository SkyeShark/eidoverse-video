"""eidoblend.sets.desert.mesh: the desert's mesh from the composed land (build/land_A/B/C.npz). Plain Python (numpy,
scipy, Pillow; no Blender):

    python blender/eidoblend/sets/desert/mesh.py --work work/desert [--k 0.0016] [--max-level 10] [--line -400,400]

Dense where the land needs it, coarse where it does not, and NO CRACKS: a restricted quadtree over +-32.8 km, every
leaf a 32 x 32 grid; a leaf is split while its height error (its own grid against the land sampled at twice its
resolution) is over what one or two pixels span at its distance from the line the lenses fly along (k x distance;
--line: x0,x1 at y 0), down to 2 m cells round the town (--max-level 10; 8: 8 m); neighbours differ by one level at
most, and along a coarser neighbour's edge the finer leaf's odd vertices are drawn onto the even ones, so both sides
share exactly the same edge (no T-junctions). The leaves are welded into one mesh. What lies wholly under the town's
plane (z < -0.25 within its 1.6 km) is left out. Out: build/desert_mesh.npz (vertices, faces, the masks per vertex)
and the scrub's places (build/scrub.npz: along the wadis and their bars, sparse on the open floor, none on sand,
rock, tracks or the town).
"""
import json
import math
import os
import sys
import time

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT_HALF = 32768.0
N = 32                                                               # cells per leaf side
MAX_LEVEL = 10                                                        # 64 m leaves, 2 m cells
MASKS = ('town', 'sand', 'sheet', 'bed', 'bar', 'esc', 'mtn', 'apron', 'rill')
FLIGHT = (-400.0, 400.0)                                              # the line the lenses fly along: x, at y 0


def load_levels(build):
    out = []
    for name in ('C', 'B', 'A'):                                      # coarsest first
        z = np.load(os.path.join(build, f'land_{name}.npz'))
        out.append({k: z[k] for k in z.files})
    return out


def sampler(levels, field):
    def f(x, y):
        out = None
        for L in levels:
            half, cell, n = float(L['half']), float(L['cell']), int(L['n'])
            fi, fj = (x + half) / cell - 0.5, (y + half) / cell - 0.5
            inside = np.minimum(np.minimum(fi, n - 1 - fi), np.minimum(fj, n - 1 - fj))
            if out is None:
                out = ndi.map_coordinates(L[field], [fj, fi], order=1, mode='nearest').astype(np.float64)
                continue
            w = np.clip((inside - 4.0) / 40.0, 0.0, 1.0)
            sel = w > 0
            if sel.any():
                s = ndi.map_coordinates(L[field], [fj[sel], fi[sel]], order=1, mode='nearest')
                out[sel] += (s - out[sel]) * w[sel]
        return out
    return f


def node_box(level, i, j):
    S = 2 * ROOT_HALF / (1 << level)
    return -ROOT_HALF + i * S, -ROOT_HALF + j * S, S


def flight_dist(x0, y0, S):
    """horizontal distance from a node's square to the flight line"""
    dx = np.maximum(np.maximum(FLIGHT[0] - (x0 + S), x0 - FLIGHT[1]), 0.0)
    dy = np.maximum(np.maximum(-(y0 + S), y0), 0.0)
    return np.hypot(dx, dy)


def evaluate(H, nodes, Fm=None):
    """per node: the error of its 32-grid against the land at 64, its lowest and highest point, and how much of it
    is dune or escarpment (where crests and rims want a finer mesh than the floor at the same distance)"""
    nodes = np.asarray(nodes, np.int64)
    out_err = np.zeros(len(nodes))
    out_lo = np.zeros(len(nodes))
    out_hi = np.zeros(len(nodes))
    out_fm = np.zeros(len(nodes))
    g = np.linspace(0.0, 1.0, 2 * N + 1)
    GU, GV = np.meshgrid(g, g)
    for s in range(0, len(nodes), 400):
        b = nodes[s:s + 400]
        S = 2 * ROOT_HALF / (1 << b[:, 0]).astype(np.float64)
        x0 = -ROOT_HALF + b[:, 1] * S
        y0 = -ROOT_HALF + b[:, 2] * S
        X = x0[:, None, None] + GU[None] * S[:, None, None]
        Y = y0[:, None, None] + GV[None] * S[:, None, None]
        h = H(X.ravel(), Y.ravel()).reshape(X.shape)
        c = h[:, ::2, ::2]                                            # the leaf's own grid
        # bilinear from the coarse grid at the fine points
        up = np.empty_like(h)
        up[:, ::2, ::2] = c
        up[:, ::2, 1::2] = 0.5 * (c[:, :, :-1] + c[:, :, 1:])
        up[:, 1::2, ::2] = 0.5 * (c[:, :-1, :] + c[:, 1:, :])
        up[:, 1::2, 1::2] = 0.25 * (c[:, :-1, :-1] + c[:, 1:, :-1] + c[:, :-1, 1:] + c[:, 1:, 1:])
        out_err[s:s + 400] = np.abs(h - up).reshape(len(b), -1).max(1)
        out_lo[s:s + 400] = h.reshape(len(b), -1).min(1)
        out_hi[s:s + 400] = h.reshape(len(b), -1).max(1)
        if Fm is not None:
            out_fm[s:s + 400] = Fm(X[:, ::4, ::4].ravel(), Y[:, ::4, ::4].ravel()).reshape(len(b), -1).max(1)
    return out_err, out_lo, out_hi, out_fm


def build_tree(H, k, Fm=None):
    t0 = time.time()
    leaves = {}
    frontier = [(1, i, j) for i in range(2) for j in range(2)]
    hidden = set()
    while frontier:
        err, lo, hi, fm = evaluate(H, frontier, Fm)
        nxt = []
        for (lv, i, j), e, l_, h_, f_ in zip(frontier, err, lo, hi, fm):
            x0, y0, S = node_box(lv, i, j)
            d = max(60.0, float(flight_dist(x0, y0, S)))
            tol = max(0.06, k * d * (0.45 if f_ > 1.0 else 1.0))     # (finer on dunes and rims: crests stay crests)
            near_town = (x0 < 1700 and x0 + S > -1700 and y0 < 1700 and y0 + S > -1700)
            if near_town and h_ < -0.25 and x0 >= -1590 and x0 + S <= 1590 and y0 >= -1590 and y0 + S <= 1590:
                hidden.add((lv, i, j))                                # wholly under the town's plane
                continue
            need = e > tol or (near_town and l_ < 0.8 and h_ > -0.6 and lv < MAX_LEVEL)  # (the crossing through z 0: finest)
            if lv < 3 or (need and lv < MAX_LEVEL):
                nxt += [(lv + 1, 2 * i + a, 2 * j + b) for a in (0, 1) for b in (0, 1)]
            else:
                leaves[(lv, i, j)] = True
        print(f'MESH tree: level {frontier[0][0]}: {len(frontier)} nodes evaluated, {len(nxt)} to split into, {len(leaves)} leaves so far '
              f'({time.time() - t0:.1f} s)', flush=True)
        frontier = nxt
    return leaves, hidden


def depth_at(leaves, hidden, x, y):
    """the level of the leaf (or hidden node) holding the point, or -1 outside everything"""
    for lv in range(MAX_LEVEL, -1, -1):
        S = 2 * ROOT_HALF / (1 << lv)
        key = (lv, int(math.floor((x + ROOT_HALF) / S)), int(math.floor((y + ROOT_HALF) / S)))
        if key in leaves or key in hidden:
            return lv
    return -1


def balance(leaves, hidden):
    """no leaf beside one more than a level finer: split until it holds"""
    t0 = time.time()
    changed = True
    rounds = 0
    while changed:
        changed = False
        rounds += 1
        for key in list(leaves):
            if key not in leaves:
                continue
            lv, i, j = key
            x0, y0, S = node_box(lv, i, j)
            e = S * 1e-4
            probes = []
            for f in (0.125, 0.375, 0.625, 0.875):
                probes += [(x0 - e, y0 + f * S), (x0 + S + e, y0 + f * S), (x0 + f * S, y0 - e), (x0 + f * S, y0 + S + e)]
            if any(depth_at(leaves, {}, px, py) > lv + 1 for px, py in probes):
                del leaves[key]
                for a in (0, 1):
                    for b in (0, 1):
                        leaves[(lv + 1, 2 * i + a, 2 * j + b)] = True
                changed = True
    print(f'MESH balanced in {rounds} rounds: {len(leaves)} leaves ({time.time() - t0:.1f} s)', flush=True)


def emit(leaves, H):
    t0 = time.time()
    keys = sorted(leaves)
    g = np.arange(N + 1)
    GI, GJ = np.meshgrid(g, g)                                        # [j, i]
    allx, ally, allf = [], [], []
    base = 0
    quad = np.stack([GJ[:-1, :-1] * (N + 1) + GI[:-1, :-1], GJ[:-1, 1:] * (N + 1) + GI[:-1, 1:],
                     GJ[1:, 1:] * (N + 1) + GI[1:, 1:], GJ[1:, :-1] * (N + 1) + GI[1:, :-1]], -1).reshape(-1, 4)
    for (lv, i, j) in keys:
        x0, y0, S = node_box(lv, i, j)
        cell = S / N
        ii, jj = GI.copy(), GJ.copy()
        e = S * 1e-4
        # a coarser neighbour across an edge: that edge's odd vertices drawn onto the even ones before them
        if depth_at(leaves, {}, x0 - e, y0 + S / 2) == lv - 1:
            jj[:, 0] = jj[:, 0] - (jj[:, 0] % 2)
        if depth_at(leaves, {}, x0 + S + e, y0 + S / 2) == lv - 1:
            jj[:, N] = jj[:, N] - (jj[:, N] % 2)
        if depth_at(leaves, {}, x0 + S / 2, y0 - e) == lv - 1:
            ii[0, :] = ii[0, :] - (ii[0, :] % 2)
        if depth_at(leaves, {}, x0 + S / 2, y0 + S + e) == lv - 1:
            ii[N, :] = ii[N, :] - (ii[N, :] % 2)
        allx.append((x0 + ii * cell).ravel())
        ally.append((y0 + jj * cell).ravel())
        allf.append(quad + base)
        base += (N + 1) ** 2
    X = np.concatenate(allx)
    Y = np.concatenate(ally)
    F = np.concatenate(allf)
    key = np.round(X * 100).astype(np.int64) * 10_000_000 + np.round(Y * 100).astype(np.int64)
    uniq, first, inv = np.unique(key, return_index=True, return_inverse=True)
    VX, VY = X[first], Y[first]
    F = inv[F]
    # quads that lost a corner to the drawing-in become triangles; those that lost two, nothing
    a, b, c, d = F[:, 0], F[:, 1], F[:, 2], F[:, 3]
    tri_drop = np.full(len(F), -1)
    keep4 = (a != b) & (b != c) & (c != d) & (d != a) & (a != c) & (b != d)
    tris, quads = [], F[keep4]
    rest = F[~keep4]
    for r in rest:
        u = []
        for v in r:
            if v not in u:
                u.append(v)
        if len(u) == 3:
            tris.append(u)
    tris = np.array(tris, np.int64).reshape(-1, 3)
    Z = H(VX, VY)
    print(f'MESH emitted {len(keys)} leaves: {len(VX)} vertices, {len(quads)} quads + {len(tris)} triangles = {len(quads) + len(tris)} faces '
          f'({time.time() - t0:.1f} s)', flush=True)
    return VX, VY, Z, quads, tris


def scrub(build, levels, H, rng):
    """the scrub's places: thick along the wadis' banks and bars, sparse on the open floor out to 2.4 km; never on the
    sand, the rock, a track, in the town or under its plane"""
    t0 = time.time()
    m = Image.open(os.path.join(build, 'near_marks.png'))
    marks = np.flipud(np.asarray(m)).astype(np.float32) / 255.0      # [j, i] from the south, over +-2048 m
    npx = marks.shape[0]
    cell = 4096.0 / npx
    n_try = 420000
    x = rng.uniform(-2400.0, 2400.0, n_try)
    y = rng.uniform(-2400.0, 2400.0, n_try)
    att = {k: sampler(levels, k)(x, y) for k in ('town', 'sand', 'bed', 'bar', 'esc', 'mtn', 'rill')}
    fi, fj = np.clip((x + 2048.0) / cell, 0, npx - 1).astype(int), np.clip((y + 2048.0) / cell, 0, npx - 1).astype(int)
    inside = (np.abs(x) < 2047) & (np.abs(y) < 2047)
    trk = np.where(inside, marks[fj, fi, 0], 0.0)
    rill = np.where(inside, marks[fj, fi, 2], att['rill'])
    # density by place: thick on the bars and the beds and along the floor's drainage lines, sparse on the open floor
    # (about 6,000 shrubs within 2.4 km)
    p = (0.022 + 0.13 * np.clip(att['bar'] / 0.4, 0, 1) + 0.05 * np.clip(att['bed'], 0, 1) + 0.09 * np.clip(rill, 0, 1)) * 1.0
    p *= (att['town'] > 25.0) * (att['sand'] < 0.4) * (att['esc'] < 0.5) * (att['mtn'] < 0.5) * (trk < 0.15)
    p *= np.clip(1.25 - np.hypot(x, y) / 2600.0, 0.15, 1.0)
    keep = rng.random(n_try) < p
    x, y = x[keep], y[keep]
    z = H(x, y)
    keep2 = z > 0.35                                                  # (above the town's plane, never under it)
    x, y, z = x[keep2], y[keep2], z[keep2]
    rot = rng.uniform(0, 2 * math.pi, len(x))
    sc = rng.uniform(0.55, 1.45, len(x)) * np.where(np.abs(y + 930) < 160, 1.25, 1.0)
    kind = rng.integers(0, 4, len(x))
    print(f'[desert] scrub: {len(x)} places ({time.time() - t0:.1f} s)', flush=True)
    return np.column_stack([x, y, z]).astype(np.float32), rot.astype(np.float32), sc.astype(np.float32), kind.astype(np.int32)


def make(work, k=0.0016, max_level=10, line=(-400.0, 400.0)):
    """the quadtree mesh and the scrub's places into <work>/build"""
    global MAX_LEVEL, FLIGHT
    MAX_LEVEL, FLIGHT = int(max_level), tuple(line)
    build = os.path.join(work, 'build')
    levels = load_levels(build)
    H = sampler(levels, 'h')
    S_sand, S_esc = sampler(levels, 'sand'), sampler(levels, 'esc')
    leaves, hidden = build_tree(H, k, lambda x, y: np.maximum(S_sand(x, y), S_esc(x, y)))
    balance(leaves, hidden)
    VX, VY, Z, quads, tris = emit(leaves, H)
    att = {m: sampler(levels, m)(VX, VY).astype(np.float32) for m in MASKS}
    np.savez(os.path.join(build, 'desert_mesh.npz'), co=np.column_stack([VX, VY, Z]).astype(np.float32), quads=quads.astype(np.int32),
             tris=tris.astype(np.int32), **{'a_' + m: v for m, v in att.items()})
    pos, rot, sc, kind = scrub(build, levels, H, np.random.default_rng(23))
    np.savez(os.path.join(build, 'scrub.npz'), pos=pos, rot=rot, scale=sc, kind=kind)
    lv = np.array([key[0] for key in leaves])
    rec = dict(k=k, max_level=MAX_LEVEL, line=list(FLIGHT), vertices=int(len(VX)), faces=int(len(quads) + len(tris)), shrubs=int(len(pos)),
               leaves_per_level={int(v): int((lv == v).sum()) for v in np.unique(lv)})
    with open(os.path.join(build, 'mesh.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    print(f'[desert] mesh saved: {rec}', flush=True)
    return rec


if __name__ == '__main__':
    A = sys.argv[1:]

    def opt(key, d):
        return A[A.index(key) + 1] if key in A else d
    make(os.path.abspath(opt('--work', 'work/desert')), float(opt('--k', '0.0016')), int(opt('--max-level', '10')),
         tuple(float(v) for v in opt('--line', '-400,400').split(',')))
