"""REVIEW RENDERS for the groom (Warp: GPU when the ledger allows, else Warp's CPU device): the base, strands, cards.

Not the runtime's look: a forge instrument, like HAIR_STUDY's raster.py / strand_raster.py (§5), here as Warp kernels.
  * the base: one primary ray per (supersampled) pixel against the skin (wp.Mesh), shaded by a key + fill + ambient
    Lambert over its albedo maps (each set's map resampled into one stack) or a per-vertex debug colour, with the coat
    maps optionally blended over the albedo (the under-fur layer: render_base(..., coat=...));
  * strands: every segment splatted as sub-pixel samples into the same depth buffer (nearest wins: a depth pass with
    atomic_min, then a colour pass at that depth), shaded along the strand with two Kajiya-Kay style lobes (a white
    primary, a tinted broader secondary), a wrap diffuse and root darkening;
  * cards: rays through the card mesh, each hit alpha-tested against the atlas coverage (u = (side + 1) / 2,
    v = rootToTip inside the card's tile, the ABI's own rule) and re-cast past a rejected hit (up to 32 layers), shaded
    along the card's strand tangent like the strands.
Supersampled ss x ss, box-filtered down, a gentle filmic curve, sRGB out.
"""
import numpy as np
import warp as wp

wp.set_module_options({'enable_backward': False})


class Cam:
    """a perspective camera: eye, target, up, vertical fov (degrees), output w x h"""

    def __init__(self, eye, target, up=(0.0, 1.0, 0.0), fov=30.0, w=1024, h=1024):
        self.eye = np.asarray(eye, np.float64)
        self.target = np.asarray(target, np.float64)
        f = self.target - self.eye
        self.fwd = f / np.linalg.norm(f)
        r = np.cross(self.fwd, np.asarray(up, np.float64))
        self.right = r / np.linalg.norm(r)
        self.up = np.cross(self.right, self.fwd)
        self.fov = fov
        self.w, self.h = w, h

    def tan(self):
        return float(np.tan(np.radians(self.fov) * 0.5))

    def px_size(self, dist):
        """metres per output pixel at a distance along the view"""
        return 2.0 * dist * self.tan() / self.h


def views_around(center, radius, elev_deg=20.0, fov=30.0, w=900, h=900, names=('front', 'right', 'back', 'left'),
                 front=(0.0, 0.0, 1.0)):
    """cameras on a circle round the centre (the base's +Z = front, forge convention), elevated"""
    fr = np.asarray(front, np.float64)
    fr /= np.linalg.norm(fr)
    up = np.array([0.0, 1.0, 0.0])
    side = np.cross(up, fr)
    dist = radius / np.sin(np.radians(fov) * 0.5) * 1.05
    out = []
    for k, nm in enumerate(names):
        a = np.radians(90.0 * k)
        d = np.cos(a) * fr + np.sin(a) * side
        e = np.radians(elev_deg)
        eye = np.asarray(center) + dist * (np.cos(e) * d + np.sin(e) * up)
        out.append((nm, Cam(eye, center, fov=fov, w=w, h=h)))
    return out


@wp.func
def _ray(px: float, py: float, W: int, H: int, eye: wp.vec3, fwd: wp.vec3, right: wp.vec3, up: wp.vec3, tanf: float):
    aspect = float(W) / float(H)
    x = (2.0 * px / float(W) - 1.0) * tanf * aspect
    y = (1.0 - 2.0 * py / float(H)) * tanf
    return wp.normalize(fwd + right * x + up * y)


@wp.func
def _tex(T: wp.array3d(dtype=wp.vec3), s: int, u: float, v: float):
    """bilinear, clamped; T is (sets, h, w)"""
    h = T.shape[1]
    w = T.shape[2]
    x = wp.clamp(u * float(w) - 0.5, 0.0, float(w - 1))
    y = wp.clamp(v * float(h) - 0.5, 0.0, float(h - 1))
    x0 = int(x)
    y0 = int(y)
    x1 = wp.min(x0 + 1, w - 1)
    y1 = wp.min(y0 + 1, h - 1)
    fx = x - float(x0)
    fy = y - float(y0)
    a = T[s, y0, x0] * (1.0 - fx) + T[s, y0, x1] * fx
    b = T[s, y1, x0] * (1.0 - fx) + T[s, y1, x1] * fx
    return a * (1.0 - fy) + b * fy


@wp.func
def _tex1(T: wp.array3d(dtype=wp.float32), s: int, u: float, v: float):
    h = T.shape[1]
    w = T.shape[2]
    x = wp.clamp(u * float(w) - 0.5, 0.0, float(w - 1))
    y = wp.clamp(v * float(h) - 0.5, 0.0, float(h - 1))
    x0 = int(x)
    y0 = int(y)
    x1 = wp.min(x0 + 1, w - 1)
    y1 = wp.min(y0 + 1, h - 1)
    fx = x - float(x0)
    fy = y - float(y0)
    a = T[s, y0, x0] * (1.0 - fx) + T[s, y0, x1] * fx
    b = T[s, y1, x0] * (1.0 - fx) + T[s, y1, x1] * fx
    return a * (1.0 - fy) + b * fy


@wp.func
def _light(n: wp.vec3, key: wp.vec3, fill: wp.vec3):
    return 0.18 + 1.05 * wp.max(wp.dot(n, key), 0.0) + 0.30 * wp.max(wp.dot(n, fill), 0.0)


@wp.kernel
def k_base(mesh: wp.uint64, F: wp.array(dtype=wp.int32), UV: wp.array(dtype=wp.vec2), VC: wp.array(dtype=wp.vec3),
           fset: wp.array(dtype=wp.int32), ALB: wp.array3d(dtype=wp.vec3), use_tex: int,
           COAT: wp.array3d(dtype=wp.vec3), COATA: wp.array3d(dtype=wp.float32), use_coat: int,
           COATN: wp.array3d(dtype=wp.vec3), TAN: wp.array(dtype=wp.vec4), VN: wp.array(dtype=wp.vec3),
           n_skin: int, PC: wp.array(dtype=wp.vec3),
           W: int, H: int, eye: wp.vec3, fwd: wp.vec3, right: wp.vec3, up: wp.vec3, tanf: float,
           key: wp.vec3, fill: wp.vec3, bg: wp.vec3, depth: wp.array(dtype=wp.float32), col: wp.array(dtype=wp.vec3)):
    i = wp.tid()
    py = i / W
    px = i - py * W
    d = _ray(float(px) + 0.5, float(py) + 0.5, W, H, eye, fwd, right, up, tanf)
    q = wp.mesh_query_ray(mesh, eye, d, 1.0e6)
    if not q.result:
        depth[i] = 1.0e9
        col[i] = bg
        return
    f = q.face
    u = q.u
    v = q.v
    n = q.normal
    if wp.dot(n, d) > 0.0:
        n = -n
    if f >= n_skin:                                   # a prop (eye, beak, sucker): its flat colour
        depth[i] = q.t
        col[i] = PC[f - n_skin] * _light(n, key, fill)
        return
    i0 = F[f * 3 + 0]
    i1 = F[f * 3 + 1]
    i2 = F[f * 3 + 2]
    alb = VC[i0] * u + VC[i1] * v + VC[i2] * (1.0 - u - v)
    rim = float(0.0)
    if use_tex == 1:
        uv = UV[i0] * u + UV[i1] * v + UV[i2] * (1.0 - u - v)
        s = fset[f]
        alb = _tex(ALB, s, uv[0], uv[1])
        if use_coat == 1:
            a = _tex1(COATA, s, uv[0], uv[1])
            alb = alb * (1.0 - a) + _tex(COAT, s, uv[0], uv[1]) * a
            # the coat layer's normal (the base's tangent frame: TANGENT, bitangent = cross(N, T) w), blended by
            # coverage, and a soft fur rim (the pile seen edge-on)
            sn = wp.normalize(VN[i0] * u + VN[i1] * v + VN[i2] * (1.0 - u - v))
            t4 = TAN[i0] * u + TAN[i1] * v + TAN[i2] * (1.0 - u - v)
            tt = wp.vec3(t4[0], t4[1], t4[2])
            tt = wp.normalize(tt - sn * wp.dot(tt, sn))
            ws = float(1.0)
            if t4[3] < 0.0:
                ws = -1.0
            bt = wp.cross(sn, tt) * ws
            cn = _tex(COATN, s, uv[0], uv[1]) * 2.0 - wp.vec3(1.0, 1.0, 1.0)
            fn = wp.normalize(tt * cn[0] + bt * cn[1] + sn * cn[2])
            if wp.dot(fn, d) > 0.0:
                fn = fn - d * (2.0 * wp.dot(fn, d))
            n = wp.normalize(n * (1.0 - a) + fn * a)
            rim = a * 0.35 * wp.pow(1.0 - wp.abs(wp.dot(sn, d)), 3.0)
    depth[i] = q.t
    col[i] = alb * (_light(n, key, fill) + rim)


@wp.kernel
def k_seg_depth(A: wp.array(dtype=wp.vec3), B: wp.array(dtype=wp.vec3), W: int, H: int, eye: wp.vec3, fwd: wp.vec3,
                right: wp.vec3, up: wp.vec3, tanf: float, width: float, base_depth: wp.array(dtype=wp.float32),
                zbuf: wp.array(dtype=wp.float32)):
    s = wp.tid()
    aspect = float(W) / float(H)
    pa = A[s] - eye
    pb = B[s] - eye
    za = wp.dot(pa, fwd)
    zb = wp.dot(pb, fwd)
    if za < 1.0e-3 or zb < 1.0e-3:
        return
    xa = (wp.dot(pa, right) / (za * tanf * aspect) + 1.0) * 0.5 * float(W)
    ya = (1.0 - wp.dot(pa, up) / (za * tanf)) * 0.5 * float(H)
    xb = (wp.dot(pb, right) / (zb * tanf * aspect) + 1.0) * 0.5 * float(W)
    yb = (1.0 - wp.dot(pb, up) / (zb * tanf)) * 0.5 * float(H)
    L = wp.sqrt((xb - xa) * (xb - xa) + (yb - ya) * (yb - ya))
    n = wp.min(int(L * 1.5) + 1, 256)
    r = int(width * 0.5)
    for k in range(n + 1):
        t = float(k) / float(n)
        x = xa + (xb - xa) * t
        y = ya + (yb - ya) * t
        z = za + (zb - za) * t
        for oy in range(-r, r + 1):
            for ox in range(-r, r + 1):
                ix = int(x) + ox
                iy = int(y) + oy
                if ix >= 0 and ix < W and iy >= 0 and iy < H:
                    p = iy * W + ix
                    dist = z / wp.dot(_ray(float(ix) + 0.5, float(iy) + 0.5, W, H, eye, fwd, right, up, tanf), fwd)
                    if dist < base_depth[p]:
                        wp.atomic_min(zbuf, p, dist)


@wp.kernel
def k_seg_col(A: wp.array(dtype=wp.vec3), B: wp.array(dtype=wp.vec3), TA: wp.array(dtype=wp.float32),
              TB: wp.array(dtype=wp.float32), CR: wp.array(dtype=wp.vec3), W: int, H: int, eye: wp.vec3,
              fwd: wp.vec3, right: wp.vec3, up: wp.vec3, tanf: float, width: float, key: wp.vec3, fill: wp.vec3,
              spec: float, base_depth: wp.array(dtype=wp.float32), zbuf: wp.array(dtype=wp.float32),
              col: wp.array(dtype=wp.vec3)):
    s = wp.tid()
    aspect = float(W) / float(H)
    pa = A[s] - eye
    pb = B[s] - eye
    za = wp.dot(pa, fwd)
    zb = wp.dot(pb, fwd)
    if za < 1.0e-3 or zb < 1.0e-3:
        return
    T = wp.normalize(B[s] - A[s])
    xa = (wp.dot(pa, right) / (za * tanf * aspect) + 1.0) * 0.5 * float(W)
    ya = (1.0 - wp.dot(pa, up) / (za * tanf)) * 0.5 * float(H)
    xb = (wp.dot(pb, right) / (zb * tanf * aspect) + 1.0) * 0.5 * float(W)
    yb = (1.0 - wp.dot(pb, up) / (zb * tanf)) * 0.5 * float(H)
    L = wp.sqrt((xb - xa) * (xb - xa) + (yb - ya) * (yb - ya))
    n = wp.min(int(L * 1.5) + 1, 256)
    r = int(width * 0.5)
    V = -wp.normalize(A[s] - eye)
    for k in range(n + 1):
        t = float(k) / float(n)
        x = xa + (xb - xa) * t
        y = ya + (yb - ya) * t
        z = za + (zb - za) * t
        rt = TA[s] + (TB[s] - TA[s]) * t
        for oy in range(-r, r + 1):
            for ox in range(-r, r + 1):
                ix = int(x) + ox
                iy = int(y) + oy
                if ix >= 0 and ix < W and iy >= 0 and iy < H:
                    p = iy * W + ix
                    dist = z / wp.dot(_ray(float(ix) + 0.5, float(iy) + 0.5, W, H, eye, fwd, right, up, tanf), fwd)
                    # the strand depth pass's winner, and never behind the base (a pixel no visible strand won keeps
                    # zbuf at 1e9, so the base test is what hides strands behind the body)
                    if dist <= zbuf[p] * 1.00002 and dist < base_depth[p]:
                        tl = wp.dot(T, key)
                        diff = wp.sqrt(wp.max(1.0 - tl * tl, 0.0))
                        tf = wp.dot(T, fill)
                        dfill = wp.sqrt(wp.max(1.0 - tf * tf, 0.0))
                        Hh = wp.normalize(key + V)
                        th = wp.dot(T, Hh)
                        s1 = wp.pow(wp.sqrt(wp.max(1.0 - th * th, 0.0)), 80.0)
                        Hs = wp.normalize(Hh + T * 0.12)
                        th2 = wp.dot(T, Hs)
                        s2 = wp.pow(wp.sqrt(wp.max(1.0 - th2 * th2, 0.0)), 18.0)
                        c = CR[s] * (0.55 + 0.45 * rt)
                        lit = c * (0.16 + 0.85 * diff * 0.75 + 0.25 * dfill) + wp.vec3(1.0, 1.0, 1.0) * (spec * s1) + c * (spec * 2.2 * s2)
                        col[p] = lit


@wp.kernel
def k_cards(cmesh: wp.uint64, CF: wp.array(dtype=wp.int32), SIDE: wp.array(dtype=wp.float32),
            RT: wp.array(dtype=wp.float32), TILE: wp.array(dtype=wp.int32), CT: wp.array(dtype=wp.vec3),
            CC: wp.array(dtype=wp.vec3), tiles: wp.array(dtype=wp.vec4), COV: wp.array2d(dtype=wp.float32),
            ATTR: wp.array2d(dtype=wp.vec4), use_attr: int,
            thr: float, W: int, H: int, eye: wp.vec3, fwd: wp.vec3, right: wp.vec3, up: wp.vec3, tanf: float,
            key: wp.vec3, fill: wp.vec3, spec: float, base_depth: wp.array(dtype=wp.float32),
            depth: wp.array(dtype=wp.float32), col: wp.array(dtype=wp.vec3), layers: wp.array(dtype=wp.int32)):
    i = wp.tid()
    py = i / W
    px = i - py * W
    d = _ray(float(px) + 0.5, float(py) + 0.5, W, H, eye, fwd, right, up, tanf)
    tmax = base_depth[i]
    t0 = float(0.0)
    o = eye
    hits = int(0)
    for it in range(48):
        q = wp.mesh_query_ray(cmesh, o, d, tmax - t0)
        if not q.result:
            break
        hits = hits + 1
        f = q.face
        u = q.u
        v = q.v
        i0 = CF[f * 3 + 0]
        i1 = CF[f * 3 + 1]
        i2 = CF[f * 3 + 2]
        side = SIDE[i0] * u + SIDE[i1] * v + SIDE[i2] * (1.0 - u - v)
        rt = RT[i0] * u + RT[i1] * v + RT[i2] * (1.0 - u - v)
        tb = tiles[TILE[i0]]
        au = tb[0] + (tb[2] - tb[0]) * (side + 1.0) * 0.5
        av = tb[1] + (tb[3] - tb[1]) * rt
        hh = COV.shape[0]
        ww = COV.shape[1]
        x = wp.clamp(int(au * float(ww)), 0, ww - 1)
        y = wp.clamp(int(av * float(hh)), 0, hh - 1)
        a = COV[y, x]
        if a >= thr:
            T = wp.normalize(CT[i0] * u + CT[i1] * v + CT[i2] * (1.0 - u - v))
            c = CC[i0]
            V = -d
            tl = wp.dot(T, key)
            diff = wp.sqrt(wp.max(1.0 - tl * tl, 0.0))
            tf = wp.dot(T, fill)
            dfill = wp.sqrt(wp.max(1.0 - tf * tf, 0.0))
            Hh = wp.normalize(key + V)
            th = wp.dot(T, Hh)
            s1 = wp.pow(wp.sqrt(wp.max(1.0 - th * th, 0.0)), 80.0)
            Hs = wp.normalize(Hh + T * 0.12)
            th2 = wp.dot(T, Hs)
            s2 = wp.pow(wp.sqrt(wp.max(1.0 - th2 * th2, 0.0)), 18.0)
            cc = c * (0.55 + 0.45 * rt)
            if use_attr == 1:
                # the attribute page: strand id -> value jitter, depth behind the card -> occlusion, the strand's own
                # root-to-tip -> root darkening (what the runtime's material reads)
                ah = ATTR.shape[0]
                aw = ATTR.shape[1]
                at = ATTR[wp.clamp(int(av * float(ah)), 0, ah - 1), wp.clamp(int(au * float(aw)), 0, aw - 1)]
                cc = c * (0.72 + 0.28 * at[2]) * (0.90 + 0.20 * at[1]) * wp.clamp(0.85 + 0.30 * at[0], 0.8, 1.05)
            col[i] = cc * (0.16 + 0.64 * diff + 0.25 * dfill) + wp.vec3(1.0, 1.0, 1.0) * (spec * s1) + cc * (spec * 2.2 * s2)
            depth[i] = t0 + q.t
            break
        t0 = t0 + q.t + 1.0e-5
        o = eye + d * t0
    layers[i] = hits


@wp.kernel
def k_shells(smesh: wp.uint64, SF: wp.array(dtype=wp.int32), LAY: wp.array(dtype=wp.float32),
             SUV: wp.array(dtype=wp.vec2), SSET: wp.array(dtype=wp.int32), SCOV: wp.array(dtype=wp.float32),
             SCOL: wp.array(dtype=wp.vec3), SN: wp.array(dtype=wp.vec3), TILE: wp.array2d(dtype=wp.vec4),
             upt: wp.array(dtype=wp.float32), W: int, H: int, eye: wp.vec3, fwd: wp.vec3, right: wp.vec3,
             up: wp.vec3, tanf: float, key: wp.vec3, fill: wp.vec3, base_depth: wp.array(dtype=wp.float32),
             depth: wp.array(dtype=wp.float32), col: wp.array(dtype=wp.vec3)):
    """shells: every layer an offset copy of the coated skin; a hit shows the strand tile's dot at that layer when the
    dot's height fraction reaches the layer's (and the coat covers the spot)"""
    i = wp.tid()
    py = i / W
    px = i - py * W
    d = _ray(float(px) + 0.5, float(py) + 0.5, W, H, eye, fwd, right, up, tanf)
    tmax = base_depth[i]
    t0 = float(0.0)
    o = eye
    for it in range(40):
        q = wp.mesh_query_ray(smesh, o, d, tmax - t0)
        if not q.result:
            break
        f = q.face
        u = q.u
        v = q.v
        i0 = SF[f * 3 + 0]
        i1 = SF[f * 3 + 1]
        i2 = SF[f * 3 + 2]
        hk = LAY[i0]
        uv = SUV[i0] * u + SUV[i1] * v + SUV[i2] * (1.0 - u - v)
        s = SSET[i0]
        cov = SCOV[i0] * u + SCOV[i1] * v + SCOV[i2] * (1.0 - u - v)
        tu = uv[0] / upt[s]
        tv = uv[1] / upt[s]
        tu = tu - wp.floor(tu)
        tv = tv - wp.floor(tv)
        th = TILE.shape[0]
        tw = TILE.shape[1]
        tx = TILE[wp.clamp(int(tv * float(th)), 0, th - 1), wp.clamp(int(tu * float(tw)), 0, tw - 1)]
        if tx[3] > 0.5 and tx[0] >= hk and cov > 0.35:
            n = wp.normalize(SN[i0] * u + SN[i1] * v + SN[i2] * (1.0 - u - v))
            c = (SCOL[i0] * u + SCOL[i1] * v + SCOL[i2] * (1.0 - u - v)) * (0.55 + 0.45 * hk) * (0.9 + 0.2 * tx[1])
            col[i] = c * _light(n, key, fill)
            depth[i] = t0 + q.t
            break
        t0 = t0 + q.t + 1.0e-6
        o = eye + d * t0


def shell_mesh(base, cov_v, height_v, layers):
    """the shell layers as one mesh: the skin's faces with any coverage, copied per layer k = 1..layers at
    h_k = k / layers of the local coat height along the vertex normal"""
    keep = cov_v[base.F].max(1) > 0.05
    F0 = base.F[keep]
    used = np.unique(F0)
    remap = -np.ones(len(base.V), np.int64)
    remap[used] = np.arange(len(used))
    Fl = remap[F0]
    Vs, Fs, L, U, S, C, N = [], [], [], [], [], [], []
    vset = np.zeros(len(base.V), np.int64)
    vset[base.F.reshape(-1)] = np.repeat(base.face_set, 3)
    for k in range(1, layers + 1):
        hk = k / layers
        Vs.append(base.V[used] + base.N[used] * (hk * height_v[used])[:, None])
        Fs.append(Fl + (k - 1) * len(used))
        L.append(np.full(len(used), hk - 0.5 / layers))
        U.append(base.UV[used])
        S.append(vset[used])
        C.append(cov_v[used])
        N.append(base.N[used])
    return dict(P=np.concatenate(Vs), F=np.concatenate(Fs), lay=np.concatenate(L), uv=np.concatenate(U),
                set=np.concatenate(S), cov=np.concatenate(C), n=np.concatenate(N), used=used, layers=layers)


def _wa(a, dt, dev):
    return wp.array(np.ascontiguousarray(a), dtype=dt, device=dev)


def _filmic(x):
    x = np.maximum(x, 0.0)
    y = x * (2.51 * x + 0.03) / (x * (2.43 * x + 0.59) + 0.14)
    return np.clip(y, 0.0, 1.0)


def to_srgb8(lin):
    c = np.clip(lin, 0.0, 1.0)
    s = np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)
    return (np.clip(s, 0, 1) * 255 + 0.5).astype(np.uint8)


class Renderer:
    """renders a base and its coat layers; device: a Warp device string ('cpu' or 'cuda:0')"""

    def __init__(self, base, device='cpu', tex_res=1024, albedo=True, props=True):
        self.base = base
        self.dev = device
        d = device
        # the ray-cast mesh: the skin first (its faces index the uv / set arrays), then the props as flat colours
        Vs, Fs, PC = [base.V], [base.F], []
        off = len(base.V)
        for _, V, F, c in (base.props() if props else []):
            Vs.append(V)
            Fs.append(F + off)
            off += len(V)
            PC.append(np.tile(np.clip(c * 1.2, 0, 1), (len(F), 1)))
        self.n_skin = len(base.F)
        self.PC = _wa((np.concatenate(PC) if PC else np.zeros((1, 3))).astype(np.float32), wp.vec3, d)
        self.mesh = wp.Mesh(points=_wa(np.concatenate(Vs).astype(np.float32), wp.vec3, d),
                            indices=_wa(np.concatenate(Fs).astype(np.int32).reshape(-1), wp.int32, d))
        self.F = _wa(base.F.astype(np.int32).reshape(-1), wp.int32, d)
        self.UV = _wa(base.UV.astype(np.float32), wp.vec2, d)
        self.TAN = _wa((base.TAN if base.TAN is not None else np.tile([1.0, 0, 0, 1.0], (len(base.V), 1)))
                       .astype(np.float32), wp.vec4, d)
        self.VN = _wa(base.N.astype(np.float32), wp.vec3, d)
        self.fset = _wa(base.face_set.astype(np.int32), wp.int32, d)
        self.tex_res = tex_res
        if albedo:
            stack = []
            from PIL import Image
            for s in base.sets:
                img = base.tex(s, 'base')
                im = Image.fromarray((img[..., :3] * 255).astype(np.uint8)).resize((tex_res, tex_res), Image.BILINEAR)
                stack.append((np.asarray(im, np.float32) / 255.0) ** 2.2)
            self.ALB = _wa(np.stack(stack).astype(np.float32), wp.vec3, d)
        else:
            self.ALB = wp.zeros((1, 1, 1), dtype=wp.vec3, device=d)
        self.no_coat = (wp.zeros((1, 1, 1), dtype=wp.vec3, device=d), wp.zeros((1, 1, 1), dtype=wp.float32, device=d),
                        wp.zeros((1, 1, 1), dtype=wp.vec3, device=d))
        self.key = np.array([0.45, 0.80, 0.40])
        self.key /= np.linalg.norm(self.key)
        self.fill = np.array([-0.6, 0.3, -0.5])
        self.fill /= np.linalg.norm(self.fill)
        self.bg = np.array([0.20, 0.21, 0.23])

    def coat_stack(self, coat_rgb, coat_a, coat_n=None):
        """per-set coat colour (linear), blend weight and tangent-space normal (0..1 encoded) maps, same size, as
        device stacks"""
        if coat_n is None:
            coat_n = [np.broadcast_to(np.array([0.5, 0.5, 1.0], np.float32), a.shape + (3,)) for a in coat_a]
        return (_wa(np.stack(coat_rgb).astype(np.float32), wp.vec3, self.dev),
                _wa(np.stack(coat_a).astype(np.float32), wp.float32, self.dev),
                _wa(np.stack(coat_n).astype(np.float32), wp.vec3, self.dev))

    def render(self, cam, ss=2, vcol=None, strands=None, cards=None, coat=None, exposure=1.0, out_layers=False,
               shells=None):
        """strands: dict(A, B (segments' ends), ta, tb (root-to-tip), col (linear per segment), width_px, spec)
        cards: dict(mesh points/indices, side, rt, tile, tan, col, tiles (n, 4), cov (h, w), thr, spec)"""
        d = self.dev
        W, H = cam.w * ss, cam.h * ss
        n = W * H
        depth = wp.zeros(n, dtype=wp.float32, device=d)
        col = wp.zeros(n, dtype=wp.vec3, device=d)
        vc = vcol if vcol is not None else np.full((len(self.base.V), 3), 0.5)
        args = [wp.vec3(*cam.eye), wp.vec3(*cam.fwd), wp.vec3(*cam.right), wp.vec3(*cam.up), cam.tan()]
        C, CA, CN = coat if coat is not None else self.no_coat
        wp.launch(k_base, dim=n, device=d,
                  inputs=[self.mesh.id, self.F, self.UV, _wa(vc.astype(np.float32), wp.vec3, d), self.fset, self.ALB,
                          1 if vcol is None else 0, C, CA, 1 if coat is not None else 0, CN, self.TAN, self.VN,
                          self.n_skin, self.PC, W, H, *args,
                          wp.vec3(*self.key), wp.vec3(*self.fill), wp.vec3(*self.bg), depth, col])
        layers = None
        if cards is not None:
            cm = wp.Mesh(points=_wa(cards['P'].astype(np.float32), wp.vec3, d),
                         indices=_wa(cards['F'].astype(np.int32).reshape(-1), wp.int32, d))
            cdepth = wp.full(n, 1.0e9, dtype=wp.float32, device=d)
            ccol = wp.zeros(n, dtype=wp.vec3, device=d)
            lay = wp.zeros(n, dtype=wp.int32, device=d)
            wp.launch(k_cards, dim=n, device=d,
                      inputs=[cm.id, _wa(cards['F'].astype(np.int32).reshape(-1), wp.int32, d),
                              _wa(cards['side'].astype(np.float32), wp.float32, d),
                              _wa(cards['rt'].astype(np.float32), wp.float32, d),
                              _wa(cards['tile'].astype(np.int32), wp.int32, d),
                              _wa(cards['tan'].astype(np.float32), wp.vec3, d),
                              _wa(cards['col'].astype(np.float32), wp.vec3, d),
                              _wa(cards['tiles'].astype(np.float32), wp.vec4, d),
                              _wa(cards['cov'].astype(np.float32), wp.float32, d),
                              _wa(cards['attr'].astype(np.float32), wp.vec4, d) if 'attr' in cards
                              else wp.zeros((1, 1), dtype=wp.vec4, device=d), 1 if 'attr' in cards else 0,
                              float(cards.get('thr', 0.34)),
                              W, H, *args, wp.vec3(*self.key), wp.vec3(*self.fill), float(cards.get('spec', 0.12)),
                              depth, cdepth, ccol, lay])
            cd = cdepth.numpy()
            bd = depth.numpy()
            m = cd < bd
            cn = col.numpy()
            cn[m] = ccol.numpy()[m]
            bd[m] = cd[m]
            col = _wa(cn, wp.vec3, d)
            depth = _wa(bd.astype(np.float32), wp.float32, d)
            layers = lay.numpy().reshape(H, W)
        if shells is not None:
            sm = wp.Mesh(points=_wa(shells['P'].astype(np.float32), wp.vec3, d),
                         indices=_wa(shells['F'].astype(np.int32).reshape(-1), wp.int32, d))
            sdepth = wp.full(n, 1.0e9, dtype=wp.float32, device=d)
            scol = wp.zeros(n, dtype=wp.vec3, device=d)
            wp.launch(k_shells, dim=n, device=d,
                      inputs=[sm.id, _wa(shells['F'].astype(np.int32).reshape(-1), wp.int32, d),
                              _wa(shells['lay'].astype(np.float32), wp.float32, d),
                              _wa(shells['uv'].astype(np.float32), wp.vec2, d),
                              _wa(shells['set'].astype(np.int32), wp.int32, d),
                              _wa(shells['cov'].astype(np.float32), wp.float32, d),
                              _wa(shells['col'].astype(np.float32), wp.vec3, d),
                              _wa(shells['n'].astype(np.float32), wp.vec3, d),
                              _wa(shells['tile'].astype(np.float32), wp.vec4, d),
                              _wa(np.asarray(shells['upt'], np.float32), wp.float32, d), W, H, *args,
                              wp.vec3(*self.key), wp.vec3(*self.fill), depth, sdepth, scol])
            sd = sdepth.numpy()
            bd = depth.numpy()
            m = sd < bd
            cn = col.numpy()
            cn[m] = scol.numpy()[m]
            bd[m] = sd[m]
            col = _wa(cn, wp.vec3, d)
            depth = _wa(bd.astype(np.float32), wp.float32, d)
        if strands is not None and len(strands['A']):
            zb = wp.full(n, 1.0e9, dtype=wp.float32, device=d)
            A = _wa(strands['A'].astype(np.float32), wp.vec3, d)
            B = _wa(strands['B'].astype(np.float32), wp.vec3, d)
            wpx = float(strands.get('width_px', 1.0))
            wp.launch(k_seg_depth, dim=len(strands['A']), device=d, inputs=[A, B, W, H, *args, wpx, depth, zb])
            wp.launch(k_seg_col, dim=len(strands['A']), device=d,
                      inputs=[A, B, _wa(strands['ta'].astype(np.float32), wp.float32, d),
                              _wa(strands['tb'].astype(np.float32), wp.float32, d),
                              _wa(strands['col'].astype(np.float32), wp.vec3, d), W, H, *args, wpx,
                              wp.vec3(*self.key), wp.vec3(*self.fill), float(strands.get('spec', 0.10)), depth, zb,
                              col])
        img = col.numpy().reshape(H, W, 3) * exposure
        img = img.reshape(cam.h, ss, cam.w, ss, 3).mean(axis=(1, 3))
        out = to_srgb8(_filmic(img))
        if out_layers:
            return out, layers
        return out


def label(img, text, scale=2, color=(255, 255, 255)):
    """burn a small label into the top-left corner (PIL's default bitmap font, scaled)"""
    from PIL import Image, ImageDraw
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im)
    tw = int(dr.textlength(text) * scale) + 12
    small = Image.new('RGB', (max(tw // scale, 1), 14), (0, 0, 0))
    ImageDraw.Draw(small).text((3, 1), text, fill=color)
    big = small.resize((small.width * scale, small.height * scale), Image.NEAREST)
    im.paste(big, (0, 0))
    return np.asarray(im)


def sheet(rows, pad=4, bg=(30, 30, 30)):
    """rows of images (each a list of equally tall uint8 images) -> one image"""
    out_rows = []
    width = 0
    for r in rows:
        h = max(i.shape[0] for i in r)
        parts = []
        for i in r:
            if i.shape[0] < h:
                i = np.concatenate([i, np.full((h - i.shape[0], i.shape[1], 3), bg, np.uint8)])
            parts += [i, np.full((h, pad, 3), bg, np.uint8)]
        row = np.concatenate(parts[:-1], axis=1)
        out_rows.append(row)
        width = max(width, row.shape[1])
    full = []
    for r in out_rows:
        if r.shape[1] < width:
            r = np.concatenate([r, np.full((r.shape[0], width - r.shape[1], 3), bg, np.uint8)], axis=1)
        full += [r, np.full((pad, width, 3), bg, np.uint8)]
    return np.concatenate(full[:-1], axis=0)
