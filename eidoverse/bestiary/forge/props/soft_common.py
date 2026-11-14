"""soft_common: what the SOFT accessories' forge files share (face_mask.py: the smile and frown masks; then the bow
tie and the beanie). Written 11-11 for ACCESSORIES B5 (work/bestiary/accessories_b5/soft_NOTES.md).

A prop here is built as PARTS, each its own closed description:
    part = dict(name, region (int), V (n, 3), Q (m, 4), uv (n, 2) METRES in its island's own frame,
                island (m,) names per quad, primary (m,) bool, attr (n, 4), smooth (bool: one smoothing group))
A STACKED island (a mirror half, a lathe's repeated arc, a strap's repeated tile) carries the SAME island-frame UVs as
its primary by construction (the same formula on the mirrored / turned coordinates), so stacking needs no vertex
twins: `assemble` splits the vertices per island, `pack` places the PRIMARY islands and every island of that name
takes the same placement. bake.low_frames gives a mirrored island its handedness (-1).

    low = assemble(parts)                                  the export's vertex set (split per island), triangles, groups
    fill, place, ppm, order = pack(low, shares, ...)       the primaries on the sheet (raster packer, order searched)
    L = low_arrays(low, place, ppm, size)                  V, F, UV, N, TAN, region, primary, ATTR (the bake's arrays)
    maps = finish_maps(outs, cov, zones, size)             the kernel's outputs -> uint8 maps (dilated), palette base
    export_glb(path, name, L, maps, fit, zones, ...)       a static glb with fit data (+ morph targets)

pack_raster / _raster / _disc are COPIED from forge/props/cowboy_hat.py (11-11; that file is the felt hats builder's
and is being rebuilt this round, so nothing here imports it): the hawk's raster packer as the hat slice changed it
(disc gutters, most-contact placement, the square sheet, `turns` orientations)."""
import numpy as np

UV_PAD = 8


# ------------------------------------------------------------------------------------------------- small helpers
def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-30)


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def orient(Q, V=None, toward=None, centre=None):
    """the quads wound consistently (each shared edge run opposite by its two faces: a flood over the edges), per
    connected piece; then the whole flipped so that the summed face normals agree with `toward` (a direction) or
    point away from `centre` (a point), when one is given"""
    Q = np.array(Q, np.int64).reshape(-1, 4).copy()
    m = len(Q)
    edge = {}
    for f in range(m):
        for k in range(4):
            a, b = int(Q[f, k]), int(Q[f, (k + 1) % 4])
            edge.setdefault((min(a, b), max(a, b)), []).append((f, a, b))
    done = np.zeros(m, bool)
    for f0 in range(m):
        if done[f0]:
            continue
        done[f0] = True
        stack = [f0]
        while stack:
            f = stack.pop()
            for k in range(4):
                a, b = int(Q[f, k]), int(Q[f, (k + 1) % 4])
                for g, ga, gb in edge[(min(a, b), max(a, b))]:
                    if g == f or done[g]:
                        continue
                    # g's own direction along this edge as it stands now
                    q = Q[g]
                    i = [int(x) for x in q].index(a)
                    same = int(q[(i + 1) % 4]) == b
                    if same:
                        Q[g] = q[::-1]
                    done[g] = True
                    stack.append(g)
    if V is not None and (toward is not None or centre is not None):
        V = np.asarray(V, np.float64)
        n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
        if toward is not None:
            s = float((n @ np.asarray(toward, np.float64)).sum())
        else:
            c = V[Q].mean(1) - np.asarray(centre, np.float64)
            s = float((n * c).sum())
        if s < 0.0:
            Q = Q[:, ::-1].copy()
    return Q


def weld(V, tol=1e-7):
    key = np.round(np.asarray(V, np.float64) / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return first, inv.ravel()


# --------------------------------------------------------------------------------------------------- the low
def assemble(parts):
    """the parts joined into the export's arrays. Vertices are split per ISLAND within a part (a UV seam), never
    shared between parts (a hard edge). Normals: area-weighted over each part's WELDED positions (one smoothing group
    a part). Returns dict(V, Q, uv (metres, island frame), island (per quad, index into names), names, primary (per
    quad), region (per quad), part (per quad), ATTR, Nw (the smooth normals per export vertex), parts [names])"""
    Vs, Qs, UVs, As, Ns, isl, prim, reg, prt = [], [], [], [], [], [], [], [], []
    names = []
    off = 0
    for pi, p in enumerate(parts):
        V = np.asarray(p['V'], np.float64)
        Q = np.asarray(p['Q'], np.int64).reshape(-1, 4)
        uv = np.asarray(p['uv'], np.float64)
        attr = np.asarray(p.get('attr', np.zeros((len(V), 4))), np.float64)
        il = list(p['island']) if not isinstance(p['island'], str) else [p['island']] * len(Q)
        pr = np.broadcast_to(np.asarray(p['primary'], bool), (len(Q),))
        # smooth normals on the welded part
        first, inv = weld(V)
        fn = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
        acc = np.zeros((len(first), 3))
        for k in range(4):
            np.add.at(acc, inv[Q[:, k]], fn)
        Nv = unit(acc)[inv]
        # split per island
        remap = {}
        Vn, UVn, An, Nn = [], [], [], []
        Qn = np.zeros_like(Q)
        for f in range(len(Q)):
            for k in range(4):
                key = (il[f], int(Q[f, k]))
                if key not in remap:
                    remap[key] = len(Vn)
                    Vn.append(V[Q[f, k]])
                    UVn.append(uv[Q[f, k]] if uv.ndim == 2 else uv[f, k])
                    An.append(attr[Q[f, k]])
                    Nn.append(Nv[Q[f, k]])
                Qn[f, k] = remap[key]
        for nm in il:
            if nm not in names:
                names.append(nm)
        Vs.append(np.array(Vn))
        UVs.append(np.array(UVn))
        As.append(np.array(An))
        Ns.append(np.array(Nn))
        Qs.append(Qn + off)
        isl += [names.index(nm) for nm in il]
        prim += list(pr)
        reg += [int(p['region'])] * len(Q)
        prt += [pi] * len(Q)
        off += len(Vn)
    return dict(V=np.vstack(Vs), Q=np.vstack(Qs), uv=np.vstack(UVs), ATTR=np.vstack(As), Nw=np.vstack(Ns),
                island=np.array(isl), names=names, primary=np.array(prim, bool), region=np.array(reg, np.int32),
                part=np.array(prt), parts=[p['name'] for p in parts])


def triangles(V, Q):
    """two triangles per quad along its shorter diagonal; returns (F, quad index per triangle)"""
    d02 = np.linalg.norm(V[Q[:, 0]] - V[Q[:, 2]], axis=1)
    d13 = np.linalg.norm(V[Q[:, 1]] - V[Q[:, 3]], axis=1)
    s = (d02 <= d13)[:, None]
    F = np.concatenate([np.where(s, Q[:, [0, 1, 2]], Q[:, [0, 1, 3]]), np.where(s, Q[:, [0, 2, 3]], Q[:, [1, 2, 3]])])
    return F, np.tile(np.arange(len(Q)), 2)


def welded_mesh(low):
    """the whole low welded by position as a forge QuadMesh (its check(), the gates)"""
    from ..mesh import QuadMesh
    first, inv = weld(low['V'])
    return QuadMesh(low['V'][first], inv[low['Q']])


# ---------------------------------------------------------------------------------------------------- packing
def _disc(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r + 0.25


def _raster(T, tri, g):
    """the cells (g texels a side) an island's triangles touch, T in texels: the mask and its first cell (copied from
    cowboy_hat._raster)"""
    from PIL import Image, ImageDraw
    lo = np.floor(T.min(0) / g).astype(int)
    T2 = T / g - lo
    W, H = (np.ceil(T2.max(0)).astype(int) + 1)
    im = Image.new('L', (int(W), int(H)), 0)
    dr = ImageDraw.Draw(im)
    for a, b, c in T2[tri]:
        dr.polygon([(float(a[0]), float(a[1])), (float(b[0]), float(b[1])), (float(c[0]), float(c[1]))], fill=1,
                   outline=1)
    return np.asarray(im, bool), lo


def pack_raster(isls, size, pad=UV_PAD, g=4, turns=8, order=None):
    """a raster packer on the square sheet (copied from cowboy_hat.pack_raster, itself the hawk's _pack_raster
    changed: a DISC's dilation for the gutter, an island placed where its outline touches the most occupied cells or
    the border, the sheet the square itself (a layout that does not fit FAILS), `turns` orientations). isls: [(T (n,
    2) texels, tri (m, 3))]; returns each island's UVs (0-1) and its turn, or None when one finds no place"""
    from scipy import fft as sfft
    from scipy.ndimage import binary_dilation
    Wc = size // g
    pc = int(np.ceil(pad / g)) + 1
    B = pc + 3
    n_ = Wc + 2 * B
    O = np.zeros((n_, n_))
    O[:B], O[-B:], O[:, :B], O[:, -B:] = 1.0, 1.0, 1.0, 1.0
    s = sfft.next_fast_len(n_, real=True)
    cand = []
    for T, tri in isls:
        opts = []
        for k in range(turns):
            a = 2.0 * np.pi * k / turns
            Tr = T @ np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]).T
            M, lo = _raster(Tr, tri, g)
            Mp = np.pad(M, pc + 2)
            if max(Mp.shape) > n_:
                continue
            fd = np.conj(sfft.rfft2(binary_dilation(Mp, structure=_disc(pc)).astype(np.float64), (s, s)))
            fc = np.conj(sfft.rfft2(binary_dilation(Mp, structure=_disc(pc + 2)).astype(np.float64), (s, s)))
            opts.append((Tr, lo, Mp, fd, fc))
        cand.append(opts)
    if order is None:
        order = sorted(range(len(isls)), key=lambda i: -max([int(o[2].sum()) for o in cand[i]] or [0]))
    out = [None] * len(isls)
    for i in order:
        best = None
        FO = sfft.rfft2(O, (s, s))
        for Tr, lo, Mp, fd, fc in cand[i]:
            h, w = Mp.shape
            free = sfft.irfft2(FO * fd, (s, s))[:n_ - h + 1, :n_ - w + 1] < 0.5
            if not free.any():
                continue
            touch = np.where(free, sfft.irfft2(FO * fc, (s, s))[:n_ - h + 1, :n_ - w + 1], -1.0)
            ys, xs = np.nonzero(touch >= touch.max() - 0.5)
            k = np.lexsort((xs, ys))[0]
            c = (float(touch.max()), -int(ys[k]), -int(xs[k]), Tr, lo, Mp)
            if best is None or c[:3] > best[:3]:
                best = c
        if best is None:
            return None
        _, y, x, Tr, lo, Mp = best
        y, x = -y, -x
        O[y:y + Mp.shape[0], x:x + Mp.shape[1]] += Mp
        out[i] = (Tr - lo * g + (np.array([x, y]) - B + pc + 2) * g) / size
    return out


def island_sets(low):
    """per island NAME: its PRIMARY quads' vertices (export ids), their island-frame UVs (metres) and triangles (local
    ids), and its UV area"""
    F, fq = triangles(low['V'], low['Q'])
    out = {}
    for i, nm in enumerate(low['names']):
        sel = (low['island'][fq] == i) & low['primary'][fq]
        if not sel.any():
            continue
        Fi = F[sel]
        vs = np.unique(Fi)
        loc = -np.ones(len(low['V']), np.int64)
        loc[vs] = np.arange(len(vs))
        uv = low['uv'][vs]
        t = loc[Fi]
        d1, d2 = uv[t[:, 1]] - uv[t[:, 0]], uv[t[:, 2]] - uv[t[:, 0]]
        out[nm] = dict(vs=vs, uv=uv, tri=t, area=float(0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum()))
    return out


def pack(low, shares, size=2048, pad=UV_PAD, turns=8, g=4, tries=16, seed=3, floor=0.45, order=None, ppm=None,
         log=print):
    """the PRIMARY islands on the sheet at one texel density (x each island's share). order + ppm given: ONE
    placement (a recorded result again, in seconds); else the placing order is searched (by area, by long side, then
    `tries` random orders) and the density bisected per order (cowboy_hat.pack_search's way). Returns (fill, {name:
    affine (2 x 3) from island metres to UV 0-1}, px_per_m, [order names])"""
    S = island_sets(low)
    prim = list(S)
    sh = np.array([float(shares.get(nm, 1.0)) for nm in prim])
    area = float(sum(S[nm]['area'] * s * s for nm, s in zip(prim, sh)))
    dens = lambda fill: float(np.sqrt(fill * size * size / area))

    def place(p, od):
        out = pack_raster([(S[nm]['uv'] * p * s, S[nm]['tri']) for nm, s in zip(prim, sh)], size, pad, g=g,
                          turns=turns, order=od)
        return out

    def affines(p, out):
        A = {}
        for nm, s, uv01 in zip(prim, sh, out):
            src = S[nm]['uv']
            # the similarity taking island metres to the sheet: least squares over the island's vertices (exact: the
            # packer only turns, scales and shifts)
            X = np.column_stack([src, np.ones(len(src))])
            M, *_ = np.linalg.lstsq(X, uv01, rcond=None)
            A[nm] = M.T
        return A

    if order is not None and ppm is not None:
        out = place(float(ppm), [prim.index(nm) for nm in order])
        if out is not None:
            return float(ppm * ppm * area / size / size), affines(ppm, out), float(ppm), list(order)
        log('[soft] uv pack: the recorded order no longer fits at its density: searching')
    a_of = np.array([S[nm]['area'] for nm in prim]) * sh * sh
    ext = [float((S[nm]['uv'].max(0) - S[nm]['uv'].min(0)).max() * s) for nm, s in zip(prim, sh)]
    orders = [('area', list(np.argsort(-a_of))), ('long side', list(np.argsort(-np.array(ext))))]
    rng = np.random.default_rng(seed)
    for t in range(tries):
        orders.append((f'random {t}', [int(i) for i in np.argsort(-a_of * np.exp(0.6 * rng.normal(size=len(prim))))]))
    got, seen = None, []
    for onm, od in orders:
        od = [int(i) for i in od]
        if od in seen:
            continue
        seen.append(od)
        f0 = floor if got is None else got[0] + 0.004
        out = place(dens(f0), od)
        if out is None:
            continue
        lo_f, hi_f, mine = f0, 0.95, (f0, out)
        for _ in range(7):
            f = 0.5 * (lo_f + hi_f)
            out = place(dens(f), od)
            if out is None:
                hi_f = f
            else:
                lo_f, mine = f, (f, out)
        log(f'[soft] uv pack, order {onm}: {mine[0] * 100:.1f} %')
        got = (mine[0], mine[1], od)
    assert got is not None, f'the islands do not pack at a {floor * 100:.0f} % fill'
    p = dens(got[0])
    return float(got[0]), affines(p, got[1]), p, [prim[i] for i in got[2]]


def primary_name(nm, place):
    """the PRIMARY island a stacked island lies on: the longest placed name that is this name or its leading words
    ('trim_5' -> 'trim', 'back_L' -> 'back', 'strap_in_3' -> 'strap', 'mesh_R_back' -> 'mesh')"""
    best = None
    for p in place:
        if (nm == p or nm.startswith(p + '_')) and (best is None or len(p) > len(best)):
            best = p
    assert best is not None, f'the island {nm!r} has no primary among {sorted(place)}'
    return best


def low_arrays(low, place, ppm, size):
    """the export's and the bake's arrays: every island (primary or stacked) through its PRIMARY's placement
    (primary_name); tangents by bake.low_frames (a mirrored island's handedness -1)"""
    from .. import bake
    UV = np.zeros((len(low['V']), 2))
    done = np.zeros(len(low['V']), bool)
    prim = {nm: primary_name(nm, place) for nm in low['names']}
    for f in range(len(low['Q'])):
        A = place[prim[low['names'][low['island'][f]]]]
        for v in low['Q'][f]:
            if not done[v]:
                UV[v] = A[:, :2] @ low['uv'][v] + A[:, 2]
                done[v] = True
    F, fq = triangles(low['V'], low['Q'])
    N, TAN = bake.low_frames(low['V'], F, UV, low['Nw'])
    return dict(V=low['V'], F=F, UV=UV, N=N, TAN=TAN, region=low['region'][fq].astype(np.int32),
                primary=low['primary'][fq], ATTR=low['ATTR'], island=low['island'][fq], part=low['part'][fq],
                px_per_m=float(ppm), size=int(size))


def uv_report(L, size, pad=UV_PAD):
    """the layout's numbers: fill (primaries' UV area), overlapping texels among primaries, the least gutter between
    two primary islands and to the sheet's edge (texels), the largest empty rectangle's share"""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    pr = L['primary']
    T = np.column_stack([L['UV'][:, 0], 1.0 - L['UV'][:, 1]]) * size
    cnt = np.zeros((size, size), np.int32)
    lab = np.zeros((size, size), np.int32)
    for i in np.unique(L['island'][pr]):
        im = Image.new('L', (size, size), 0)
        dr = ImageDraw.Draw(im)
        for f in L['F'][pr & (L['island'] == i)]:
            dr.polygon([(float(T[v, 0]), float(T[v, 1])) for v in f], fill=1)
        m = np.asarray(im, bool)
        cnt += m
        lab[m] = i + 1
    cov = cnt > 0
    gut = 1e9
    for i in np.unique(lab[lab > 0]):
        d = ndimage.distance_transform_edt(lab != i)
        other = (lab > 0) & (lab != i)
        if other.any():
            gut = min(gut, float(d[other].min()))
    ys, xs = np.nonzero(cov)
    edge = float(min(xs.min(), ys.min(), size - 1 - xs.max(), size - 1 - ys.max()))
    # the largest empty axis-aligned rectangle (a histogram sweep on a 4 x coarser grid)
    c = ~cov.reshape(size // 4, 4, size // 4, 4).any((1, 3))
    h = np.zeros(c.shape[1], int)
    best = 0
    for row in c:
        h = np.where(row, h + 1, 0)
        st = []
        for j, hj in enumerate(list(h) + [0]):
            s0 = j
            while st and st[-1][1] >= hj:
                s0, hh = st.pop()
                best = max(best, hh * (j - s0))
            st.append((s0, hj))
    return dict(fill=float(cov.mean()), overlap_texels=int((cnt > 1).sum()), gutter_px=gut, edge_px=edge,
                empty_rect_share=float(best * 16 / size / size))


# ------------------------------------------------------------------------------------------------- the maps
def finish_maps(alb, nrm, orm, msk, wear, cov, zones, steps=16):
    """the material kernel's image-order float outputs -> uint8 maps with their gutters filled (bake.dilate_all) and
    the palette base (each zone's median linear albedo: masks B = zone / 3). The masks ship as RGB, NO ALPHA (the
    hat slice's finding: the engine's decode divides a PNG's colour by a partial alpha)"""
    from .. import material as M
    from ..bake import dilate_all
    zone = np.rint(msk[..., 2] * 3.0).astype(int)
    pal = {}
    for zi, nm in enumerate(zones):
        sel = cov & (zone == zi)
        if sel.sum() > 16:
            pal[nm] = [float(x) for x in np.median(alb[sel], axis=0)]
    dil, grown = dilate_all(dict(normal=np.concatenate([nrm, cov[..., None].astype(np.float32)], -1), alb=alb,
                                 orm=orm, msk=msk, wear=wear), steps)
    g3 = grown[..., None]
    u8 = lambda a: np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)
    return dict(albedo=u8(M.srgb_oetf(np.where(g3, dil['alb'], 0.05))),
                normal=u8(np.where(g3, dil['normal'][..., :3], [0.0, 0.0, 1.0]) * 0.5 + 0.5),
                orm=u8(np.where(g3, dil['orm'], [1.0, 0.8, 0.0])), masks=u8(np.where(g3, dil['msk'][..., :3], 0.0)),
                wear=u8(np.where(g3, dil['wear'], 0.0)), palette_base=pal, coverage=cov)


def _srgb_to_lin(u8):
    s = np.asarray(u8, np.float64) / 255.0
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def _lin_to_srgb_u8(L):
    L = np.clip(L, 0.0, 1.0)
    s = np.where(L <= 0.0031308, 12.92 * L, 1.055 * np.power(L, 1.0 / 2.4) - 0.055)
    return np.clip(s * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _blocks(a, f):
    """(H, W, ...) -> (H/f, W/f, f*f, ...): each delivered texel's f x f master texels"""
    h, w = a.shape[:2]
    rest = a.shape[2:]
    b = a.reshape(h // f, f, w // f, f, *rest).swapaxes(1, 2)
    return b.reshape(h // f, w // f, f * f, *rest)


def deliver_maps(maps, size):
    """THE DELIVERED MAPS at `size` from the material pass's masters (OPTIMIZATION, 11-11: the masters are the
    supersampled bake's sheet; the runtime decodes every PNG / JPEG to RGBA8 + mips, so a map's GPU memory is its
    delivered size: craft guide 15.25 'derive runtime sizes from the masters', 07.18 'texels beyond about one per
    screen pixel only cost memory'). Each delivered texel is the AREA MEAN of the f x f master texels it covers (a 2 x 2
    box per halving, the guide's 15.27 minimum, which cannot ring at the ink's hard edges):
      albedo   decoded from sRGB, averaged in linear light, encoded once (15.21)
      normal   averaged as VECTORS and renormalized; the LENGTH LOST is the normals' spread, carried into the ORM's
               roughness by the material passes' own formula (face_mask / bow_tie k_*: var = (1 - |n|) / |n|,
               roughness = sqrt(sqrt(a^2 + var)) with a = roughness^2): 15.28
      orm      AO and metal averaged; roughness averaged, then the normals' spread added
      masks    R (fuzz) and G (material) averaged; B (the PALETTE ZONE, 0 / 1/3 / 2/3 / 1) by MAJORITY: a mean of
               face (0) and ink (2/3) would be 1/3, a false third zone along every ink edge
    maps: dict(albedo, normal, orm, masks (uint8 (S, S, 3)), palette_base, ...); returns the same keys (others copied)"""
    S = maps['albedo'].shape[0]
    if size >= S:
        return maps
    f = S // size
    assert f * size == S and f & (f - 1) == 0, f'deliver {S} -> {size}: not a power-of-two step'
    out = {k: v for k, v in maps.items() if k not in ('albedo', 'normal', 'orm', 'masks', 'wear', 'coverage')}
    out['albedo'] = _lin_to_srgb_u8(_blocks(_srgb_to_lin(maps['albedo']), f).mean(2))
    n = _blocks(np.asarray(maps['normal'], np.float64) / 255.0 * 2.0 - 1.0, f).mean(2)
    ln = np.linalg.norm(n, axis=-1)
    n = n / np.maximum(ln[..., None], 1e-8)
    out['normal'] = np.clip((n * 0.5 + 0.5) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    o = _blocks(np.asarray(maps['orm'], np.float64) / 255.0, f).mean(2)
    var = np.clip((1.0 - ln) / np.maximum(ln, 1e-4), 0.0, 1.0)
    a = o[..., 1] ** 2
    o[..., 1] = np.sqrt(np.sqrt(a * a + var))
    out['orm'] = np.clip(o * 255.0 + 0.5, 0, 255).astype(np.uint8)
    m = _blocks(np.asarray(maps['masks'], np.float64) / 255.0, f)
    mk = m.mean(2)
    zone = np.rint(m[..., 2] * 3.0).astype(int)                         # (h, w, f*f)
    counts = np.stack([(zone == z).sum(-1) for z in range(4)], -1)
    mk[..., 2] = np.argmax(counts, -1) / 3.0
    out['masks'] = np.clip(mk * 255.0 + 0.5, 0, 255).astype(np.uint8)
    out['delivered'] = dict(size=int(size), master=int(S), spread_texels=int((var > 0.002).sum()),
                            roughness_raised_p99=float(np.percentile(o[..., 1] - np.sqrt(a), 99)))
    return out


def export_glb(path, name, L, maps, fit, zones, masks_channels, archetype, shapes=None, skins=None, deliver=None):
    """a static glb as top_hat.export_glb writes it: one mesh (every triangle: a stacked island shows its primary's
    texels), one material (base, normal, ORM; the masks in KHR_materials_volume's thickness slot), the fit data in
    the root node's and the file's extras; shapes: {target name: (V, N)}: MORPH TARGETS (a shape that changes per
    wearer: an elastic strap's path).
    skins (11-11, the kit's way: accessories_b5/STAGED.md F5, cowboy_hat.export_glb): {colour: its maps} in order,
    the FIRST the default, `maps` ignored: ONE glb for every colour: one mesh, ONE normal map (every skin's normal must
    be that picture: checked), the default's maps on the material, every other skin's albedo / ORM / masks as textures
    of their own, named in extras `bestiary.skins` = {default, <colour>: {base, orm, masks: texture index,
    palette_base}}; a skin's ORM or masks IDENTICAL to the default's is not embedded twice (the same index).
    deliver: the maps' delivered size (deliver_maps; None: as given). The file's extras record it."""
    from .. import gltf
    g = gltf.GLB()
    variant = None
    if skins:
        names = list(skins)
        skins = {k: deliver_maps(v, deliver) if deliver else v for k, v in skins.items()}
        maps = skins[names[0]]
        for nm in names[1:]:
            if not np.array_equal(np.asarray(skins[nm]['normal']), np.asarray(maps['normal'])):
                raise ValueError(f'the skin {nm!r} has a normal map of its own: a skin changes colour, never relief')
        variant = names[0]
    elif deliver:
        maps = deliver_maps(maps, deliver)
    t_base = g.texture(maps['albedo'], fmt='jpeg', quality=95)
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='jpeg', quality=95)
    t_msk = g.texture(maps['masks'], fmt='png')
    extra = dict(variant=variant) if variant else {}
    if skins:
        sk = {'default': names[0], names[0]: dict(base=t_base, orm=t_orm, masks=t_msk,
                                                   palette_base=maps.get('palette_base', {}))}
        for nm in names[1:]:
            m = skins[nm]
            same_orm = np.array_equal(np.asarray(m['orm']), np.asarray(maps['orm']))
            same_msk = np.array_equal(np.asarray(m['masks']), np.asarray(maps['masks']))
            sk[nm] = dict(base=g.texture(m['albedo'], fmt='jpeg', quality=95),
                          orm=t_orm if same_orm else g.texture(m['orm'], fmt='jpeg', quality=95),
                          masks=t_msk if same_msk else g.texture(m['masks'], fmt='png'),
                          palette_base=m.get('palette_base', {}))
        extra['skins'] = sk
    tex = dict(size=int(maps['albedo'].shape[0]))
    if 'delivered' in maps:
        tex.update(master=maps['delivered']['master'])
    mat = g.material(name, base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='prop', prop=name, masks=t_msk, masks_channels=masks_channels, palette_zones=list(zones),
        palette_base=maps.get('palette_base', {}), **extra))
    mesh = g.mesh(name, L['V'], L['N'], L['TAN'], L['UV'], [(L['F'], mat)])
    if shapes:
        names_ = sorted(shapes)
        g.morph_targets(mesh, [(np.asarray(shapes[k][0], np.float64) - L['V'],
                                np.asarray(shapes[k][1], np.float64) - L['N']) for k in names_], names_)
    g.node(name, mesh=mesh, root=True, extras=dict(bestiary='prop', fit=fit))
    return g.save(path, extras=dict(bestiary=dict(prop=name, archetype=archetype, units='m', up='+Y', forward='+Z',
                                                  left='+X', triangles=int(len(L['F'])), fit=fit, textures=tex,
                                                  **extra)))
