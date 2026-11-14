"""THE HOSE'S CLAMPS (C5c, the lead's decision 2): each a soft rubber SADDLE PAD seated on the arm's skin, its underside
the skin's own surface under it (sampled per vertex: seated on, never pressed in, no feet), a cradle in its top the hose
lies in, and a black-oxide steel STRAP over the hose whose two tabs lie on the pad's shoulders, each held by a domed
RIVET. Built in the clamp's frame in the hose's reference pose (forge/cyborg_hose.py: x along the hose, y off the skin,
z = x cross y, the origin the hose's centre); the hose drapes the pad's weights per vertex (the skin's under it), so the
pad rides the arm in every frame, the strap and the rivets the hose's own weights there.

Their own small texture set (one material, three rows on one 256 x 256 sheet: the house rubber, the black oxide, bare
steel; forge/cyborg.py's rows through cyborg_limb._rows, read only), every pad's texels stacked (one look, one set of
texels: the house's rule for identical parts), composed from height fields (no bake).

Read with numpy.
"""
import math

import numpy as np

TAU = 2.0 * math.pi
# the pad and the strap in units of the hose's radius r
PAD = dict(L=2.9,               # the pad's length along the hose
           W=3.1,               # its width across
           T=0.40,              # its cradle's thickness under the hose (the hose's underside this far off the skin)
           cradle=0.55,         # the cradle's lips this far under the hose's axis (it holds the lower 0.28 of the hose)
           shoulder=0.50,       # each shoulder's flat this wide beyond the lip (the strap's tab lies on it)
           chamfer=0.22,        # the pad's ends rounded to this radius (x r; C5d: C5c's 0.10 chamfer, a sharp block)
           round=0.24,          # C5d: the top edges (flank to shoulder) rounded to this radius (x r)
           seat=0.12e-3,        # the underside this far off the skin (m): seated on it, never in it (C5d: 0.03 mm let
                                # the skin's facets rise into the pad between its underside samples by up to 0.038 mm
                                # at rest, 0.063 in the swim: c05c's gate 11)
           strap_w=1.10,        # the strap's width along the hose
           strap_t=0.16,        # its thickness
           strap_gap=0.012,     # its inside this far off the hose
           tab=0.42,            # each tab's length on its shoulder
           rivet=0.20,          # the rivets' head radius
           rivet_h=0.55)        # the rivets' dome height over its radius
SHEET = 256                     # the pads' set (px); the islands' rectangles (u0, v0, u1, v1) in the sheet's UV (v up),
#                                 none overlapping another with its 2-texel paint margin: the loop stops short of the
#                                 rivets' corner (sharing it painted 36 of every pad's loop triangles bare steel)
ISLANDS = dict(loop=(0.02, 0.62, 0.84, 0.98), cap0=(0.02, 0.44, 0.48, 0.58), cap1=(0.52, 0.44, 0.98, 0.58),
               strap_out=(0.02, 0.27, 0.98, 0.40), strap_in=(0.02, 0.16, 0.98, 0.25), strap_e0=(0.02, 0.10, 0.98, 0.14),
               strap_e1=(0.02, 0.04, 0.98, 0.08), rivet=(0.86, 0.86, 0.98, 0.98))
ROW_OF = dict(loop='rubber', cap0='rubber', cap1='rubber', strap_out='oxide', strap_in='oxide', strap_e0='oxide',
              strap_e1='oxide', rivet='steel')


def _ear_clip(P):
    """a simple polygon (n, 2), counter-clockwise or not, triangulated by ear clipping: (m, 3) indices"""
    P = np.asarray(P, np.float64)
    n = len(P)
    idx = list(range(n))
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    sgn = 1.0 if area > 0 else -1.0
    tris = []

    def inside(p, a, b, c):
        d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
        d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
        d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
        neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
        return not (neg and pos)
    guard = 0
    while len(idx) > 3 and guard < 10 * n:
        guard += 1
        m = len(idx)
        for k in range(m):
            i0, i1, i2 = idx[(k - 1) % m], idx[k], idx[(k + 1) % m]
            a, b, c = P[i0], P[i1], P[i2]
            cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cr * sgn <= 1e-14:
                continue
            if any(inside(P[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
        else:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return np.array(tris, np.int64)


def _uv_rect(key, u, v):
    """local (u, v) in [0, 1] into the island's rectangle on the sheet"""
    u0, v0, u1, v1 = ISLANDS[key]
    return np.column_stack([u0 + (u1 - u0) * np.asarray(u), v0 + (v1 - v0) * np.asarray(v)])


def _normals(V, F):
    """area-weighted vertex normals of a mesh (n, 3)"""
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for c in range(3):
        np.add.at(N, F[:, c], fn)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)


def pad_section(r, skin_y, x, p=PAD, inset=0.0):
    """the pad's closed cross-section at x (the clamp frame's (z, y)), from the underside's middle round: the underside
    (the skin under each z, skin_y(x, z) -> y, plus the seat), the outer flank, the shoulder's flat, the cradle's arc under
    the hose (radius r + inset, its lips `cradle` r under the axis), the other shoulder and flank. inset: an end's chamfer
    (the shoulders and flanks drawn in, the cradle opened). Returns (points (n, 2), per point its part: 0 underside,
    1 flank, 2 shoulder, 3 cradle)"""
    rc = r * (1.0 + 0.004) + inset
    y1 = -p['cradle'] * r - 0.5 * inset
    ph1 = math.acos(min(0.99, -y1 / rc))
    z1 = rc * math.sin(ph1)
    zs = z1 + p['shoulder'] * r - inset
    zw = 0.5 * p['W'] * r - inset
    nu = 25                     # (15: a crease under clamp 1 in some seeds' poses stood the underside 0.6 mm off between
                                # samples 0.45 mm apart, c05c)
    zu = np.linspace(zw, -zw, nu)
    yu = np.array([skin_y(x, z_) for z_ in zu]) + p['seat']
    pts, part = [], []
    # the underside, from +z to -z (the loop's seam at its middle is on the underside: never seen)
    for z_, y_ in zip(zu, yu):
        pts.append((z_, y_))
        part.append(0)
    # the left flank up (a drafted wall, its foot rounded)
    yb = yu[-1]
    for t in (0.18, 0.55, 1.0):
        zz = -zw + (zw - zs) * (t ** 1.6) * 0.92
        pts.append((zz, yb + (y1 - yb) * t))
        part.append(1)
    # the left shoulder's flat
    for t in np.linspace(0.0, 1.0, 4)[1:]:
        pts.append((-zs + (zs - z1) * t, y1))
        part.append(2)
    # the cradle under the hose
    for ph in np.linspace(-ph1, ph1, 17)[1:-1]:
        pts.append((rc * math.sin(ph), -rc * math.cos(ph)))
        part.append(3)
    for t in np.linspace(0.0, 1.0, 4)[:-1]:
        pts.append((z1 + (zs - z1) * t, y1))
        part.append(2)
    yb = yu[0]
    for t in (1.0, 0.55, 0.18):
        zz = zw - (zw - zs) * (t ** 1.6) * 0.92
        pts.append((zz, yb + (y1 - yb) * t))
        part.append(1)
    return _round_tops(np.array(pts), np.array(part), p.get('round', 0.0) * r)


def _round_tops(P, part, rho, n=6):
    """C5d: the section's two top corners (where a flank meets its shoulder) rounded: each corner point replaced by a
    quadratic Bezier from rho down its flank to rho along its shoulder (n points; the flank's half part 1, the
    shoulder's part 2)"""
    if rho <= 0.0:
        return P, part
    out, op = [], []
    m = len(P)
    for i in range(m):
        a, b = part[i - 1] if i > 0 else -1, part[(i + 1) % m] if i + 1 < m else -1
        corner = part[i] == 1 and ((b == 2 and a == 1) or (a == 2 and b == 1))
        if not corner:
            out.append(P[i])
            op.append(part[i])
            continue
        pa, pb = P[i - 1], P[i + 1]
        da, db = pa - P[i], pb - P[i]
        la, lb = np.linalg.norm(da), np.linalg.norm(db)
        q0 = P[i] + da / la * min(rho, 0.9 * la)
        q2 = P[i] + db / lb * min(rho, 0.9 * lb)
        for k in range(n):
            t = k / (n - 1)
            out.append((1 - t) ** 2 * q0 + 2 * t * (1 - t) * P[i] + t * t * q2)
            op.append(part[i - 1] if t < 0.5 else part[i + 1])
    return np.array(out), np.array(op)


def pad_mesh(r, skin_y, p=PAD, nx=15):
    """THE SADDLE PAD in the clamp frame: the cross-section swept along x over its length (its two ends chamfered), its
    two end caps. skin_y(x, z): the skin's y under (x, z) in the clamp frame. Returns dict(V, N, UV, F) and the part of
    every vertex (0 underside ... 3 cradle, 4 cap)"""
    L = p['L'] * r
    ch = p['chamfer'] * r
    # C5d: each end a QUARTER ROUND of radius chamfer r (four sections, their insets ch (1 - cos phi)), not one chamfer
    ph_ = np.radians([90.0, 67.5, 45.0, 22.5])
    ex_, ei_ = 0.5 * L - ch + ch * np.sin(ph_), ch * (1.0 - np.cos(ph_))
    xs = np.concatenate([-ex_, np.linspace(-0.5 * L + ch, 0.5 * L - ch, nx), ex_[::-1]])
    ins = np.concatenate([ei_, np.zeros(nx), ei_[::-1]])
    secs = [pad_section(r, skin_y, x_, p, inset=in_) for x_, in_ in zip(xs, ins)]
    m = len(secs[0][0])
    V, UV, part = [], [], []
    # the loop: per section its m points and the seam's copy (u from 0 to 1 by the section's arc length)
    per = []
    for (S, pt), x_ in zip(secs, xs):
        S2 = np.vstack([S, S[:1]])
        d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(S2, axis=0), axis=1))])
        per.append(d[-1])
        for (z_, y_), dd, pp in zip(S2, d, np.append(pt, pt[0])):
            V.append((x_, y_, z_))
            UV.append((dd / d[-1], (x_ + 0.5 * L) / L))
            part.append(int(pp))
    nr = m + 1
    F = []
    for i in range(len(xs) - 1):
        for j in range(m):
            a, b, c, d_ = i * nr + j, i * nr + j + 1, (i + 1) * nr + j, (i + 1) * nr + j + 1
            F += [(a, c, d_), (a, d_, b)]
    V = np.array(V)
    UVl = _uv_rect('loop', np.array(UV)[:, 0], np.array(UV)[:, 1])
    F = np.array(F, np.int64)
    # the caps: the end sections' polygons, ear-clipped, planar UVs on their islands
    caps_V, caps_UV, caps_F, caps_part = [], [], [], []
    n0 = len(V)
    for ci, (S, _) in ((0, secs[0]), (1, secs[-1])):
        x_ = xs[0] if ci == 0 else xs[-1]
        T = _ear_clip(S)
        zmin, zmax = S[:, 0].min(), S[:, 0].max()
        ymin, ymax = S[:, 1].min(), S[:, 1].max()
        sc = max(zmax - zmin, ymax - ymin)
        uv = _uv_rect(f'cap{ci}', (S[:, 0] - zmin) / sc, (S[:, 1] - ymin) / sc)
        base = n0 + sum(len(v_) for v_ in caps_V)
        caps_V.append(np.column_stack([np.full(len(S), x_), S[:, 1], S[:, 0]]))
        caps_UV.append(uv)
        # outward: -x at the start, +x at the end
        tri = T if ci == 1 else T[:, ::-1]
        caps_F.append(tri + base)
        caps_part.append(np.full(len(S), 4))
    V = np.vstack([V] + caps_V)
    UVa = np.vstack([UVl] + caps_UV)
    F = np.vstack([F] + caps_F)
    part = np.concatenate([np.array(part)] + caps_part)
    # wind outward: the loop's normals point away from the section's inside
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    cen = V[:n0].mean(0)
    loop_f = np.arange(len(F)) < 2 * (len(xs) - 1) * m
    mid = V[F[loop_f]].mean(1)
    out_ = np.einsum('ij,ij->i', fn[loop_f], mid - np.column_stack([mid[:, 0], np.full(len(mid), cen[1]),
                                                                     np.full(len(mid), cen[2])]))
    if np.mean(out_ < 0) > 0.5:
        F[loop_f] = F[loop_f][:, ::-1]
    # the cradle's faces point UP into the hose (the loop's inside there is the pad): checked by the same rule above
    return dict(V=V, N=_normals(V, F), UV=UVa, F=F, part=part, perimeter=float(np.mean(per)))


def strap_path(r, p=PAD):
    """the strap's centreline in the clamp frame's (z, y): the left tab on its shoulder, up the hose's side, over the top
    at r + gap + t / 2, down the other side, the right tab; points (n, 2)"""
    t = p['strap_t'] * r
    rs = r * (1.0 + p['strap_gap']) + 0.5 * t
    y1 = -p['cradle'] * r
    rc = r * 1.004
    z1 = rc * math.sqrt(max(1.0 - (y1 / rc) ** 2, 0.0))
    yt = y1 + 0.5 * t - 0.03e-3                       # the tab's centreline: lying on the shoulder (0.03 mm into it)
    # the arc over the top from the hose's widest point down to where it meets the tab's height (a short straight leg
    # to the tab's bend)
    dl = math.asin(min(max(-yt / rs, 0.0), 0.99))
    th = np.linspace(-0.5 * math.pi - dl, 0.5 * math.pi + dl, 31)
    arc = np.column_stack([rs * np.sin(th), rs * np.cos(th)])
    zl = rs * math.cos(dl)
    tb = min(p['tab'] * r, z1 + p['shoulder'] * r - zl - 0.02 * r)
    tab = lambda s_: np.array([[s_ * (zl + tb * f_), yt] for f_ in (0.35, 0.7, 1.0)])
    return np.vstack([tab(-1.0)[::-1], arc, tab(1.0)])


def strap_mesh(r, p=PAD):
    """THE STRAP: a band of width strap_w (along x) and thickness strap_t swept along strap_path; four strips (outer,
    inner, two edges) on their islands. Returns dict(V, N, UV, F) and the tabs' rivet sites ((2, 3), the outward normal)"""
    C = strap_path(r, p)
    w, t = p['strap_w'] * r, p['strap_t'] * r
    d = np.gradient(C, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    nrm = np.column_stack([-d[:, 1], d[:, 0]])          # the band's normal in (z, y): to the left of the travel
    # outward = away from the hose's axis on the arc, up on the tabs: make it point up / out
    if (nrm[len(C) // 2] @ np.array([0.0, 1.0])) < 0:
        nrm = -nrm
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    u = s / s[-1]
    out_ = C + 0.5 * t * nrm
    in_ = C - 0.5 * t * nrm
    V, UV, F = [], [], []

    def strip(A2, B2, xa, xb, key, flip=False):
        """a strip between two (n, 2) polylines at x = xa (A) and xb (B) (or the same polyline at two x)"""
        n0 = len(V)
        for k_ in range(len(C)):
            V.append((xa, A2[k_][1], A2[k_][0]))
            V.append((xb, B2[k_][1], B2[k_][0]))
            UV.append(_uv_rect(key, [u[k_]], [0.0])[0])
            UV.append(_uv_rect(key, [u[k_]], [1.0])[0])
        for k_ in range(len(C) - 1):
            a, b, c, d_ = n0 + 2 * k_, n0 + 2 * k_ + 1, n0 + 2 * k_ + 2, n0 + 2 * k_ + 3
            tri = [(a, c, d_), (a, d_, b)]
            F.extend([tt[::-1] for tt in tri] if flip else tri)
    strip(out_, out_, -0.5 * w, 0.5 * w, 'strap_out')
    strip(in_, in_, -0.5 * w, 0.5 * w, 'strap_in', flip=True)
    strip(in_, out_, -0.5 * w, -0.5 * w, 'strap_e0', flip=True)
    strip(in_, out_, 0.5 * w, 0.5 * w, 'strap_e1')
    V = np.array(V)
    F = np.array(F, np.int64)
    # wind outward: the outer strip's normals along +nrm
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    ref = np.column_stack([np.zeros(len(F)), np.zeros(len(F)), np.zeros(len(F))])
    k_out = slice(0, 2 * (len(C) - 1))
    want = np.column_stack([np.zeros(len(C) - 1), nrm[:-1, 1], nrm[:-1, 0]]).repeat(2, 0)
    if np.mean(np.einsum('ij,ij->i', fn[k_out], want) < 0) > 0.5:
        F = F[:, ::-1]
    del ref
    sites = []
    for sgn in (-1.0, 1.0):
        zt = C[-1][0] if sgn > 0 else C[0][0]
        zt = zt - sgn * 0.5 * (abs(C[-1][0]) - abs(C[-4][0]))       # (C5d: the tab's middle, its length the
        #                                                   path's: from the arc's end, C[-4], to its end)
        sites.append((0.0, C[-1][1] + 0.5 * t, zt))
    return dict(V=V, N=_normals(V, F), UV=np.array(UV), F=F, length=float(s[-1])), np.array(sites)


def rivet_mesh(r, site, p=PAD, n=10):
    """a domed rivet head (a spherical cap, radius rivet r, height rivet_h of it) on the tab at `site` (the clamp frame,
    its axis +y), its base 0.02 mm into the strap"""
    a = p['rivet'] * r
    h = p['rivet_h'] * a
    R = (a * a + h * h) / (2.0 * h)                       # the cap's sphere
    V, UV, F = [], [], []
    ring_t = np.linspace(0.0, 1.0, 4)
    c0 = np.asarray(site, np.float64) - np.array([0.0, 0.02e-3, 0.0])
    for t in ring_t:
        rho = a * (1.0 - t)
        y = math.sqrt(max(R * R - rho * rho, 0.0)) - (R - h)
        for k in range(n):
            ph = TAU * k / n
            V.append(c0 + np.array([rho * math.cos(ph), y, rho * math.sin(ph)]))
            UV.append(_uv_rect('rivet', [0.5 + 0.5 * (1.0 - t) * math.cos(ph)], [0.5 + 0.5 * (1.0 - t) * math.sin(ph)])[0])
    V = np.array(V)
    for i in range(len(ring_t) - 1):
        for k in range(n):
            a_, b_ = i * n + k, i * n + (k + 1) % n
            c_, d_ = (i + 1) * n + k, (i + 1) * n + (k + 1) % n
            F += [(a_, d_, c_), (a_, b_, d_)]
    F = np.array(F, np.int64)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if np.mean(fn[:, 1] < 0) > 0.5:
        F = F[:, ::-1]
    return dict(V=V, N=_normals(V, F), UV=np.array(UV), F=F)


def pad_maps(px=5180.0):
    """THE PADS' SET (SHEET x SHEET): per island its row (forge/cyborg.py's rows through cyborg_limb._rows): the pad's
    rubber with a fine moulded stipple and a darker band where the hose and the tabs bear on it, the strap's black oxide
    brushed along its length with lighter worn edges, the rivets' bare steel. Returns the maps (uint8: albedo, normal,
    ORM, masks) and a record"""
    from . import cyborg_limb as CL
    rows = CL._rows()
    n = SHEET
    # by construction: no island's painted rectangle (its 2-texel margin included) reaches into another's
    keys = list(ISLANDS)
    for a_ in range(len(keys)):
        for b_ in range(a_ + 1, len(keys)):
            p_, q_ = ISLANDS[keys[a_]], ISLANDS[keys[b_]]
            mg = 2.0 / n
            if (p_[0] - mg < q_[2] + mg and q_[0] - mg < p_[2] + mg and p_[1] - mg < q_[3] + mg
                    and q_[1] - mg < p_[3] + mg):
                raise ValueError(f'the pads\' islands {keys[a_]} and {keys[b_]} overlap on the sheet')
    i = (np.arange(n) + 0.5) / n
    U, Vv = np.meshgrid(i, i)                          # Vv: v up (row 0 = v near 0)
    base = np.zeros((n, n, 3))
    rough = np.full((n, n), 0.7)
    metal = np.zeros((n, n))
    ao = np.ones((n, n))
    height = np.zeros((n, n))
    rng = np.random.default_rng(31)
    grain = CL.fbm3(np.column_stack([U.ravel(), Vv.ravel(), np.zeros(n * n)]) * 0.05, 0.004, 7).reshape(n, n)
    fine = rng.random((n, n))
    for key, (u0, v0, u1, v1) in ISLANDS.items():
        m = (U >= u0 - 2.0 / n) & (U <= u1 + 2.0 / n) & (Vv >= v0 - 2.0 / n) & (Vv <= v1 + 2.0 / n)
        row = rows[ROW_OF[key]]
        lu = np.clip((U - u0) / (u1 - u0), 0.0, 1.0)
        lv = np.clip((Vv - v0) / (v1 - v0), 0.0, 1.0)
        b = np.asarray(row['base'], np.float64)[None, None, :] * np.ones((n, n, 1))
        rr = np.full((n, n), float(row['rough']))
        mt = np.full((n, n), float(row['metal']))
        hh = np.zeros((n, n))
        aa = np.ones((n, n))
        if ROW_OF[key] == 'rubber':
            b = b * (0.90 + 0.12 * grain)[..., None]
            rr = rr + 0.06 * (grain - 0.5)
            hh = 0.012e-3 * (fine - 0.5) + 0.02e-3 * (grain - 0.5)
            if key == 'loop':
                # the loop's u runs round the section from the underside's middle: the cradle's middle sits at u 0.5,
                # the shoulders either side: the hose bears on the cradle, the tabs on the shoulders
                aa = 1.0 - 0.30 * np.exp(-((lu - 0.5) / 0.10) ** 2) - 0.18 * (np.exp(-((lu - 0.31) / 0.035) ** 2)
                                                                            + np.exp(-((lu - 0.69) / 0.035) ** 2))
        elif ROW_OF[key] == 'oxide':
            streak = np.sin(lv * 41.0 * TAU + 3.0 * np.sin(lu * 7.0 * TAU)) * 0.5 + 0.5
            rr = rr + 0.07 * (streak - 0.5)
            edge = np.minimum(lv, 1.0 - lv)
            if key in ('strap_e0', 'strap_e1'):
                b = b * 1.6
                mt = np.maximum(mt, 0.6)
            else:
                b = b * (1.0 + 0.35 * np.exp(-(edge / 0.08) ** 2))[..., None]
            hh = 0.004e-3 * (streak - 0.5)
        else:
            rr = rr - 0.05 * np.exp(-((lu - 0.5) ** 2 + (lv - 0.5) ** 2) / 0.05)
        base[m] = b[m]
        rough[m] = rr[m]
        metal[m] = mt[m]
        height[m] = hh[m]
        ao[m] = aa[m]
    base = np.clip(base, 0.013, 0.87)
    du = 1.0 / (n * px / 1.0) if px else 1.0
    tex = 1.0 / px
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / (2.0 * tex)
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) / (2.0 * tex)
    nn = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    nn /= np.linalg.norm(nn, axis=-1, keepdims=True)
    enc = lambda x: np.clip(x * 255.0 + 0.5, 0, 255).astype(np.uint8)
    flipv = lambda a: a[::-1]
    maps = dict(albedo=flipv(enc(base ** (1.0 / 2.2))), normal=flipv(enc(nn * 0.5 + 0.5)),
                orm=flipv(enc(np.stack([ao, np.clip(rough, 0.04, 1.0), metal], -1))),
                masks=np.zeros((n, n, 4), np.uint8))
    del du
    return maps, dict(size=[n, n], rows={k: ROW_OF[k] for k in ISLANDS}, islands=ISLANDS)
