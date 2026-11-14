"""UVs, THE BAKE and the MAPS of a garment.

UVS: the cloth split into its PANELS (a pattern's pieces: a top's front, back and two sleeves; a trouser's four leg
panels; a shoe's upper and sole; the collar; the buttons), each panel an island (LSCM, forge/uv.py), scaled to the
TARGET DENSITY (3,600 px/m at the set's size: over the body's 3,430 with room for the conformal map's spread) and packed
(forge/uv.pack). SHARED REPEATS: a panel with a mirror twin (the right sleeve, the right trouser panels, the right
shoe) takes its twin's UVs (each vertex its mirror's: the body's topology is mirrored, the drape symmetric to a few mm)
and is left out of the bake, so the two share every texel.

THE BAKE (forge/bake_mesh.py, Warp): the low = the draped game mesh, the high = the same cloth one level finer and
draped again from the low's shape (its own finer folds), the body and the other cloth as AO occluders. Normal, AO,
cavity, curvature.

THE CONSTRUCTION'S HEIGHT FIELD (texel space, mm, added to the baked normal): every island border that is a SEAM gets
the pressed allowance's ridge (0.35 mm over 6 mm) and a topstitch 5 mm in (2.5 mm stitches); every OPENING its hem band
(the hem's width raised 0.5 mm, its fold rounded, a twin-needle stitch line at the hem's inner edge); and the garment's
own lines from the cloth's pattern coordinates rasterised per texel: a shirt's placket (two stitch lines, the
buttonholes), its back yoke, its cuffs' seam; a tee's rib neckband; a trouser's waistband, fly J-stitch, front crease,
belt loops and back welt pockets; a shoe's vamp / quarter seam, its lacing and eyelets, the welt's stitch row.

THE PACKS (the human's convention: forge gltf ORM = occlusion, roughness, metal):
  T_<g>_N        the baked + construction normal (tangent space, the runtime's frame)
  T_<g>_ALBEDO   the undyed cloth (luminance: the colour options multiply it in the shader), thread and wear
  T_<g>_ORM      AO, roughness, metal 0
  T_<g>_MASKS    R the DYE zone (the old outfit colour), G the TRIM zone (thread, buttons, rib, laces: a second colour),
                 B the third zone (a shoe's sole, a trouser's pocket bag), A wear (edges, hems, the knees, the toe)
"""
import numpy as np
import warp as wp
from scipy import ndimage

from .. import uv as fuv
from .. import lookdev
from . import meshops as mo  # noqa: F811

TARGET_PX_PER_M = 3600.0


# ------------------------------------------------------------------------------------------------ panels and islands
def split_islands(F, face_label):
    """duplicate vertices along panel borders: returns (Fs (faces into the split set), src (split vertex -> original),
    island label per split vertex)"""
    key = {}
    src, lab = [], []
    Fs = np.empty_like(F)
    for t, (tri, l) in enumerate(zip(F, face_label)):
        for c in range(3):
            k = (int(tri[c]), int(l))
            if k not in key:
                key[k] = len(src)
                src.append(int(tri[c]))
                lab.append(int(l))
            Fs[t, c] = key[k]
    return Fs, np.array(src), np.array(lab)


def unwrap(V, F, face_label, twins=None, size=4096, density=TARGET_PX_PER_M, pad=10, extra=()):
    """V: positions (the draped low), F, face_label: the panel id per face; twins: {panel: (master panel, mirror map
    (n,) original vertex -> its mirror vertex)}; extra: [(V, F)] separate small islands (collar, buttons) appended.
    Returns dict(UV per split vertex, Fs, src, lab, used, density per island)"""
    Fs, src, lab = split_islands(F, face_label)
    Vs = V[src]
    UV = np.zeros((len(Vs), 2))
    panels = sorted(set(int(x) for x in face_label))
    twins = twins or {}
    masters = [p for p in panels if p not in twins]
    isl, scl, ids = [], [], []
    comp = mo.components(Fs, len(Vs))
    for p in masters:
        fm0 = face_label == p
        # a panel may fall in pieces (a stray triangle fan at the armpit): each connected piece its own island
        for cpart in np.unique(comp[Fs[fm0][:, 0]]):
            fm = fm0 & (comp[Fs[:, 0]] == cpart)
            vids = np.unique(Fs[fm])
            loc = -np.ones(len(Vs), np.int64)
            loc[vids] = np.arange(len(vids))
            Fl = loc[Fs[fm]]
            if len(Fl) < 2:
                U = np.zeros((len(vids), 2))
                U[:, 0] = np.arange(len(vids)) * 1e-4
                isl.append(U)
                scl.append(1.0)
                ids.append((p, vids))
                continue
            U0 = fuv.lscm(Vs[vids], Fl)
            U = _arap_safe(Vs[vids], Fl, U0)
            # (the test is LSCM's OWN spread: ARAP from a collapsed start reads 0.7 while it overlaps itself)
            if _spread(Vs[vids], Fl, U0) < 0.3:
                # (B2b) LSCM COLLAPSED part of the island (the man's trousers' front panel: 1,492 faces at ~0 area, and
                # ARAP from there curled the leg into a self-overlapping blob: patches on his shins): seed ARAP from
                # the island's own best plane instead, keep whichever spreads the texels more evenly
                Pc = Vs[vids] - Vs[vids].mean(0)
                _, _, Vt = np.linalg.svd(Pc, full_matrices=False)
                Ub = Pc @ Vt[:2].T
                e1, e2 = Ub[Fl[:, 1]] - Ub[Fl[:, 0]], Ub[Fl[:, 2]] - Ub[Fl[:, 0]]
                if np.sum(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) < 0:
                    Ub[:, 0] = -Ub[:, 0]
                Ub = _arap_safe(Vs[vids], Fl, Ub)

                def folds(X):
                    a, b = X[Fl[:, 1]] - X[Fl[:, 0]], X[Fl[:, 2]] - X[Fl[:, 0]]
                    s = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
                    return min((s > 0).sum(), (s < 0).sum())
                if folds(Ub) <= folds(U) or _spread(Vs[vids], Fl, Ub) > _spread(Vs[vids], Fl, U):
                    U = Ub
            d = fuv.island_density(Vs[vids], Fl, U)
            isl.append(U)
            scl.append(density / max(d, 1e-9))
            ids.append((p, vids))
    for k, (Ve, Fe) in enumerate(extra):
        # each connected piece of an extra (a button) its own island
        ce = mo.components(Fe, len(Ve))
        for cpart in np.unique(ce[Fe[:, 0]]):
            fm = ce[Fe[:, 0]] == cpart
            vids = np.unique(Fe[fm])
            loc = -np.ones(len(Ve), np.int64)
            loc[vids] = np.arange(len(vids))
            Fl = loc[Fe[fm]]
            U0e = fuv.lscm(Ve[vids], Fl)
            U = _arap_safe(Ve[vids], Fl, U0e)
            if len(Fl) > 50 and _spread(Ve[vids], Fl, U0e) < 0.3:
                # (B2b) the same collapse on an extra: the man's collar fall (a 40 cm curved strip) rendered one wing grey
                Pc = Ve[vids] - Ve[vids].mean(0)
                _, _, Vt = np.linalg.svd(Pc, full_matrices=False)
                Ub = Pc @ Vt[:2].T
                e1, e2 = Ub[Fl[:, 1]] - Ub[Fl[:, 0]], Ub[Fl[:, 2]] - Ub[Fl[:, 0]]
                if np.sum(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) < 0:
                    Ub[:, 0] = -Ub[:, 0]
                Ub = _arap_safe(Ve[vids], Fl, Ub)
                if _spread(Ve[vids], Fl, Ub) > _spread(Ve[vids], Fl, U):
                    U = Ub
            d = fuv.island_density(Ve[vids], Fl, U)
            isl.append(U)
            scl.append(density / max(d, 1e-9))
            ids.append((('extra', k), vids))
    out, used = fuv.pack(isl, scl, size=size, pad=pad)
    extra_uv = [np.zeros((len(Ve), 2)) for Ve, _ in extra]
    for (p, vids), U in zip(ids, out):
        if isinstance(p, tuple) and p[0] == 'extra':
            extra_uv[p[1]][vids] = U
        else:
            UV[vids] = U
    # the twins: each vertex its mirror's UV in the master panel
    for p, (mp, mirror) in twins.items():
        fm = face_label == p
        vids = np.unique(Fs[fm])
        mvid = {}
        mmask = lab == mp
        for i, s in enumerate(src):
            if mmask[i]:
                mvid[s] = i
        for v in vids:
            m = mirror[src[v]]
            UV[v] = UV[mvid[m]] if m in mvid else UV[v]
    return dict(UV=UV, Fs=Fs, src=src, lab=lab, used=used, extra_uv=extra_uv)


def _spread(V, F, U):
    """(B2b) an island's texel evenness: the area-weighted p5 of its faces' density over the median (1 = even)"""
    a3 = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    e1, e2 = U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]]
    s = np.sqrt(0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) / np.maximum(a3, 1e-12))
    if a3.sum() <= 0 or not np.all(np.isfinite(s)):
        return 0.0
    o = np.argsort(s)
    c = np.cumsum(a3[o]) / a3.sum()
    return float(s[o][np.searchsorted(c, 0.05)] / max(s[o][np.searchsorted(c, 0.5)], 1e-12))


def _bbox_px(V, F, U, density):
    d = fuv.island_density(V, F, U)
    T = (U - U.min(0)) * density / d
    return float(np.prod(T.max(0)))


def _arap_safe(V, F, U0, density=TARGET_PX_PER_M):
    """ARAP evens the island's area, unless it folds or balloons the island (a fan cap, a sliver): then the LSCM map.
    The island's own triangles must not flip (signed UV area against the majority)."""
    try:
        # (B2b) 40 passes: LSCM folded 1,492 faces of the man's trousers' front panel (the hip's front) to ~0 area and
        # 6 passes only brought that island's p5 to 0.43 of its median density (p5 2,146 px/m); 40 bring it to ~0.7
        U = fuv.arap(V, F, U0, iters=40)
    except Exception:
        return U0
    if not np.all(np.isfinite(U)):
        return U0

    def flips(X):
        e1, e2 = X[F[:, 1]] - X[F[:, 0]], X[F[:, 2]] - X[F[:, 0]]
        s = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
        return min((s > 0).sum(), (s < 0).sum())
    if flips(U) > flips(U0) or _bbox_px(V, F, U, density) > 1.3 * _bbox_px(V, F, U0, density):
        return U0
    return U


def mirror_map(V, tol=0.004):
    """each vertex's mirror (x -> -x) by nearest neighbour; -1 where none within tol"""
    from scipy.spatial import cKDTree
    t = cKDTree(V)
    d, i = t.query(V * [-1, 1, 1])
    i[d > tol] = -1
    return i, d


def frames(V, F, UV):
    """per-vertex normal and tangent (x, y, z, w) in forge's bake / gltf convention. (B2b) The NORMAL is the position-
    welded one: a UV seam's split copies share it (each copy's own faces only gave the mirrored centre front a lighting
    crease from the neck to the hem, the engine's b2close); the tangent stays per copy (its UVs)"""
    from .body import vertex_normals
    key = np.round(np.asarray(V) * 1e6).astype(np.int64)
    _, wid = np.unique(key, axis=0, return_inverse=True)
    wid = wid.ravel()
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    Nw = np.zeros((wid.max() + 1, 3))
    for k in range(3):
        np.add.at(Nw, wid[F[:, k]], fn)
    N = Nw[wid]
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-20
    if not np.all(np.isfinite(N)):
        N = vertex_normals(V, F)
    Tf, Bf = lookdev.tangent_frames(V, F, UV)
    T = np.zeros_like(V)
    B = np.zeros_like(V)
    for k in range(3):
        np.add.at(T, F[:, k], Tf)
        np.add.at(B, F[:, k], Bf)
    T -= N * np.einsum('ij,ij->i', T, N)[:, None]
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-20
    w = np.sign(np.einsum('ij,ij->i', np.cross(N, T), B))
    w[w == 0] = 1.0
    return N, np.column_stack([T, w])


# ------------------------------------------------------------------------------------------------ texel rasteriser
@wp.kernel
def k_raster(uvm: wp.uint64, size: int, attr: wp.array2d(dtype=float), tri: wp.array(dtype=wp.int32), na: int,
             out: wp.array2d(dtype=float), face: wp.array(dtype=int)):
    t = wp.tid()
    px = t % size
    py = t // size
    p = wp.vec3((float(px) + 0.5), (float(py) + 0.5), 0.0)
    q = wp.mesh_query_point_no_sign(uvm, p + wp.vec3(0.0, 0.0, 1.0), 2.0)
    if q.result:
        c = wp.mesh_eval_position(uvm, q.face, q.u, q.v)
        if wp.length(c - p) < 0.71:
            face[t] = q.face
            a = tri[q.face * 3 + 0]
            b = tri[q.face * 3 + 1]
            d = tri[q.face * 3 + 2]
            for k in range(na):
                out[t, k] = q.u * attr[a, k] + q.v * attr[b, k] + (1.0 - q.u - q.v) * attr[d, k]
            return
    face[t] = -1


def raster(UV, F, attr, size):
    """per texel (rows top-down, forge v up) the attributes interpolated on the UV triangles; face -1 off the islands"""
    wp.init()
    dev = 'cuda:0' if wp.is_cuda_available() else 'cpu'
    P = np.column_stack([UV * size, np.zeros(len(UV))]).astype(np.float32)
    m = wp.Mesh(points=wp.array(P, dtype=wp.vec3, device=dev),
                indices=wp.array(F.astype(np.int32).ravel(), dtype=wp.int32, device=dev))
    A = np.asarray(attr, np.float32)
    if A.ndim == 1:
        A = A[:, None]
    out = wp.zeros((size * size, A.shape[1]), float, device=dev)
    face = wp.zeros(size * size, int, device=dev)
    wp.launch(k_raster, size * size, [m.id, size, wp.array(A, dtype=float, device=dev),
                                      wp.array(F.astype(np.int32).ravel(), dtype=wp.int32, device=dev), A.shape[1],
                                      out, face], device=dev)
    o = out.numpy().reshape(size, size, -1)[::-1]
    f = face.numpy().reshape(size, size)[::-1]
    return o, f


def draw_lines(UV, segs, size, width_px=1.5):
    """a mask of UV polylines' segments (pairs of vertex ids)"""
    m = np.zeros((size, size), bool)
    for a, b in segs:
        p, q = UV[a] * size, UV[b] * size
        n = int(max(2, np.ceil(np.linalg.norm(q - p) * 2)))
        t = np.linspace(0, 1, n)[:, None]
        P = p + (q - p) * t
        x = np.clip(P[:, 0].astype(int), 0, size - 1)
        y = np.clip(size - 1 - P[:, 1].astype(int), 0, size - 1)
        m[y, x] = True
    if width_px > 1:
        m = ndimage.binary_dilation(m, iterations=int(width_px))
    return m


# ------------------------------------------------------------------------------------------------ the height field
def stitch(dist_mm, at_mm, phase_mm, length=2.6, width=0.45, depth=0.18):
    """a running stitch line: thread raised along the line at at_mm, gaps between stitches (the needle holes sink)"""
    across = np.clip(1.0 - np.abs(dist_mm - at_mm) / width, 0, 1)
    along = (phase_mm / length) % 1.0
    on = np.clip((0.82 - np.abs(along - 0.5) * 2.0) * 6.0, 0, 1)
    return across * (on * depth - (1 - on) * depth * 0.6)


def construction_height(cov, d_seam, d_open, px_mm, open_width, phase_seam, phase_open, extra=None):
    """the construction's height field (mm) from the distances (px) to seam and opening borders"""
    ds, do = d_seam * px_mm, d_open * px_mm
    H = np.zeros(cov.shape, np.float32)
    # the seam allowance pressed under the cloth: a soft ridge, the topstitch 5 mm in
    H += 0.35 * np.clip(1.0 - ds / 6.5, 0, 1) ** 0.7 * (ds > 0.4)
    H += stitch(ds, 5.0, phase_seam)
    H -= 0.25 * np.clip(1.0 - ds / 0.9, 0, 1)                 # the seam's own line sinks
    # the hem: the folded band, rounded at the fold; the twin-needle line at its inner edge
    band = np.clip((open_width - do) / 1.2, 0, 1)
    H += 0.45 * band
    H -= 0.5 * np.clip(1.0 - do / 1.2, 0, 1) ** 2
    H += stitch(do, open_width - 1.5, phase_open) + stitch(do, open_width - 4.5, phase_open) * (open_width > 12)
    if extra is not None:
        H += extra
    return H * cov


def height_to_normal(H, px_mm, strength=1.0):
    gx = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) / (2 * px_mm)
    gy = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) / (2 * px_mm)
    N = np.stack([-gx * strength, gy * strength, np.ones_like(H)], -1)
    return N / np.linalg.norm(N, axis=-1, keepdims=True)


def combine_normals(Nb, Nd):
    """whiteout / RNM-style detail over base (both tangent-space unit vectors)"""
    t = Nb + np.array([0, 0, 1.0])
    u = Nd * np.array([-1, -1, 1.0])
    r = t * np.einsum('...i,...i->...', t, u)[..., None] / t[..., 2:3] - u
    return r / (np.linalg.norm(r, axis=-1, keepdims=True) + 1e-12)


def dilate(img, cov, iters=16):
    """push island colours outward into the padding (mip-safe)"""
    img = img.astype(np.float32).copy()
    if not cov.any():
        return img
    d, (iy, ix) = ndimage.distance_transform_edt(~cov, return_indices=True)
    fill = (~cov) & (d <= iters)
    img[fill] = img[iy[fill], ix[fill]]                  # every padding texel takes its nearest island texel
    return img


def to_u8(x):
    return np.clip(x * 255 + 0.5, 0, 255).astype(np.uint8)
