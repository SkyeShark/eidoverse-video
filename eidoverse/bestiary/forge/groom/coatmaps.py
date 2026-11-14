"""THE COAT MAPS: the groom baked into the base's own UV space, the UNDER-FUR LAYER (HAIR_STUDY §9.6, WOLF_PLAN §5.4's
"baked coat maps on the envelope": study T's painted haircap / the cow's painted skin, from our strands instead of paint).

The skin material blends this layer in where the coat is: it is what hides the skin between cards, and at the far LOD
(no cards) it is the coat. Per base texture set, at the set's resolution (style maps.res: {set: px}):

  coat     RGBA8  R coverage: how much of the skin the coat hides seen along the normal (the style's mask times the
                  strands' projected density, saturated by maps.density_gain: the groom samples tens of strands per
                  cm2 of a pelt that has hundreds);
                  G height: the coat's top above the skin over maps.height_mm (the full-scale height, in the manifest);
                  B root-to-tip of the visible fibre (0 skin / roots .. 1 tips): the layer's own occlusion and the
                  root-to-tip colour ramp;
                  A strand id of the visible fibre (a random per strand): value / hue jitter, as on the cards
  coatflow RGBA8  RG the visible fibre's direction in the base's tangent frame (TANGENT, bitangent = cross(N, T) w),
                  x 0.5 + 0.5; B lift (sine of its elevation off the skin); A the mask (domain x not bare)
  coatN    RGB8   the fur surface's normal in the same tangent frame (glTF +Y = bitangent, as the base's own normal
                  maps): the skin normal leaned against each fibre's lift, plus strand grooves across the flow

How: a UV G-buffer per set (a Warp ray cast in UV space: wp.Mesh over (u, v, 0) gives each texel its face and
barycentrics), then every strand sample is moved to its closest point on the skin (wp.mesh_query_point_no_sign:
face, barycentrics -> uv, set, height) and splatted into its set's texels (numpy add.at / maximum.at); the topmost
sample of a texel gives B, A, the flow and the normal. Everything outside the UV islands is push-pull dilated, so mips
never bleed black.
"""
import json

import numpy as np
import warp as wp

from .fields import Pts
from .tiles import push_pull

wp.set_module_options({'enable_backward': False})


@wp.kernel
def k_uv_gbuf(mesh: wp.uint64, R: int, face: wp.array(dtype=wp.int32), bu: wp.array(dtype=wp.float32),
              bv: wp.array(dtype=wp.float32)):
    i = wp.tid()
    y = i / R
    x = i - y * R
    o = wp.vec3((float(x) + 0.5) / float(R), (float(y) + 0.5) / float(R), 1.0)
    q = wp.mesh_query_ray(mesh, o, wp.vec3(0.0, 0.0, -1.0), 2.0)
    if q.result:
        face[i] = q.face
        bu[i] = q.u
        bv[i] = q.v
    else:
        face[i] = -1


@wp.kernel
def k_closest(mesh: wp.uint64, P: wp.array(dtype=wp.vec3), face: wp.array(dtype=wp.int32),
              bu: wp.array(dtype=wp.float32), bv: wp.array(dtype=wp.float32), h: wp.array(dtype=wp.float32),
              FN: wp.array(dtype=wp.vec3)):
    i = wp.tid()
    q = wp.mesh_query_point_no_sign(mesh, P[i], 10.0)
    face[i] = q.face
    bu[i] = q.u
    bv[i] = q.v
    s = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
    h[i] = wp.dot(P[i] - s, FN[q.face])


def uv_gbuffer(base, set_k, R, device):
    """per texel of set k at R x R (glTF uv: row 0 = v 0): face index (-1 outside), barycentrics (corner weights)"""
    m = base.face_set == set_k
    fids = np.nonzero(m)[0]
    UV = base.UV
    F = base.F[fids]
    pts = np.column_stack([UV[:, 0], UV[:, 1], np.zeros(len(UV))]).astype(np.float32)
    mesh = wp.Mesh(points=wp.array(pts, dtype=wp.vec3, device=device),
                   indices=wp.array(F.astype(np.int32).reshape(-1), dtype=wp.int32, device=device))
    n = R * R
    face = wp.zeros(n, dtype=wp.int32, device=device)
    bu = wp.zeros(n, dtype=wp.float32, device=device)
    bv = wp.zeros(n, dtype=wp.float32, device=device)
    wp.launch(k_uv_gbuf, dim=n, device=device, inputs=[mesh.id, R, face, bu, bv])
    f = face.numpy()
    inside = f >= 0
    tri = np.full(n, -1, np.int64)
    tri[inside] = fids[f[inside]]
    u, v = bu.numpy(), bv.numpy()
    bary = np.column_stack([u, v, 1.0 - u - v])          # warp: p0 u + p1 v + p2 (1 - u - v)
    return tri.reshape(R, R), bary.reshape(R, R, 3)


def border_band(cov, vis, inside, coated, band_px=3, inner_px=(8, 40)):
    """(round 2) the seam gate: the coated texels within band_px of their island's border against those inner_px deep
    (same islands): the coverage's median ratio (1 = no rim along the seams) and the share of texels no strand reached
    (B / A / flow at their defaults there)"""
    from scipy import ndimage as nd
    dist = nd.distance_transform_edt(inside)
    band = coated & (dist <= band_px)
    inner = coated & (dist >= inner_px[0]) & (dist <= inner_px[1])
    if not band.any() or not inner.any():
        return None
    return dict(cov_p50_band=round(float(np.median(cov[band])), 3), cov_p50_inner=round(float(np.median(cov[inner])), 3),
                cov_ratio=round(float(np.median(cov[band]) / max(np.median(cov[inner]), 1e-6)), 3),
                no_fibre_band=round(float((~vis[band]).mean()), 3), no_fibre_inner=round(float((~vis[inner]).mean()), 3))


class CoatMaps:
    def __init__(self, base, style, fields, device='cpu'):
        self.base = base
        self.style = style
        self.fields = fields
        self.device = device
        self.cfg = style.get('maps', {})

    def bake(self, groom_npz, log=print):
        b = self.base
        z = groom_npz
        cfg = self.cfg
        P = z['points'].astype(np.float64)
        S, K = P.shape[:2]
        rnd = z['rnd'].astype(np.float64)
        d = self.device
        # every strand point's closest skin point (unwelded skin: faces carry the uv sets)
        mesh = wp.Mesh(points=wp.array(b.V.astype(np.float32), dtype=wp.vec3, device=d),
                       indices=wp.array(b.F.astype(np.int32).reshape(-1), dtype=wp.int32, device=d))
        X = P.reshape(-1, 3)
        n = len(X)
        face = wp.zeros(n, dtype=wp.int32, device=d)
        bu = wp.zeros(n, dtype=wp.float32, device=d)
        bv = wp.zeros(n, dtype=wp.float32, device=d)
        hh = wp.zeros(n, dtype=wp.float32, device=d)
        wp.launch(k_closest, dim=n, device=d,
                  inputs=[mesh.id, wp.array(X.astype(np.float32), dtype=wp.vec3, device=d), face, bu, bv, hh,
                          wp.array(b.FN.astype(np.float32), dtype=wp.vec3, device=d)])
        f = face.numpy().astype(np.int64)
        u, v = bu.numpy().astype(np.float64), bv.numpy().astype(np.float64)
        bary = np.column_stack([u, v, 1.0 - u - v])
        Fv = b.F[f]
        uv = np.einsum('nk,nkd->nd', bary, b.UV[Fv])
        S_ = np.einsum('nk,nkd->nd', bary, b.V[Fv])            # the closest skin points
        setk = b.face_set[f]
        h = hh.numpy().astype(np.float64)
        uv = uv.reshape(S, K, 2)
        S_ = S_.reshape(S, K, 3)
        setk = setk.reshape(S, K)
        h = h.reshape(S, K)
        # per-segment: the fibre's direction (3-D), its projected length on the skin, its root-to-tip
        seg3 = np.diff(P, axis=1)
        segp = np.linalg.norm(np.diff(S_, axis=1), axis=2)       # metres along the skin
        t = np.linspace(0, 1, K)
        width = cfg.get('fibre_um', 70.0) * 1e-6
        ppm = b.px_per_m()
        Rs = [int(cfg.get('res', {}).get(s_, b.tex(s_, 'base').shape[0])) for s_ in b.sets]
        tex_m = np.array([1.0 / (ppm[s_] * Rs[j] / b.tex(s_, 'base').shape[0]) for j, s_ in enumerate(b.sets)])
        # (round 2) SEGMENTS ACROSS A SEAM. A segment is splatted by interpolating its ends' uvs, which only holds when
        # both ends lie in one set on one side of every uv seam; the first pass dropped every other segment, so a band
        # along each island border (up to half a segment wide) lost the strands that cross it: the coverage fell
        # toward the border and the visible fibre's B / A / flow fell back to their defaults there (the streak audit's
        # border bands, coat/g4/g4_groom/audit/). Those segments are resampled along the strand in 3-D instead, each
        # sample moved to its own closest skin point (its own face, uv, set and height), so a strand that crosses a
        # seam deposits on both sides of it
        k0 = setk[:, :-1]
        jump_px = np.linalg.norm(uv[:, 1:] - uv[:, :-1], axis=2) * np.array(Rs, np.float64)[k0]
        clean = (k0 == setk[:, 1:]) & (jump_px < 3.0 * segp / tex_m[k0] + 4.0)
        ci, ck = np.nonzero(~clean)
        xs = None
        if len(ci):
            L3 = np.linalg.norm(seg3[ci, ck], axis=1)
            nsx = np.clip(np.ceil(L3 / (0.5 * tex_m.min())).astype(np.int64), 2, 256)
            rpx = np.repeat(np.arange(len(ci)), nsx)
            frx = (np.arange(len(rpx)) - np.repeat(np.cumsum(nsx) - nsx, nsx) + 0.5) / np.repeat(nsx, nsx)
            Q = P[ci[rpx], ck[rpx]] + seg3[ci[rpx], ck[rpx]] * frx[:, None]
            nq = len(Q)
            fq = wp.zeros(nq, dtype=wp.int32, device=d)
            uq = wp.zeros(nq, dtype=wp.float32, device=d)
            vq = wp.zeros(nq, dtype=wp.float32, device=d)
            hq = wp.zeros(nq, dtype=wp.float32, device=d)
            wp.launch(k_closest, dim=nq, device=d,
                      inputs=[mesh.id, wp.array(Q.astype(np.float32), dtype=wp.vec3, device=d), fq, uq, vq, hq,
                              wp.array(b.FN.astype(np.float32), dtype=wp.vec3, device=d)])
            fqn = fq.numpy().astype(np.int64)
            bq = np.column_stack([uq.numpy(), vq.numpy(), 1.0 - uq.numpy() - vq.numpy()]).astype(np.float64)
            xs = dict(uv=np.einsum('nk,nkd->nd', bq, b.UV[b.F[fqn]]), set=b.face_set[fqn],
                      h=hq.numpy().astype(np.float64), s=ci[rpx], k=ck[rpx],
                      t=t[ck[rpx]] + (t[ck[rpx] + 1] - t[ck[rpx]]) * frx, dl=(segp[ci, ck] / nsx)[rpx])
        self.seam_resampled = dict(segments=int(len(ci)), share=round(float(len(ci) / max(clean.size, 1)), 4),
                                   samples=0 if xs is None else int(len(xs['h'])))
        self.maps = {}
        self.stats = {}
        for k, sname in enumerate(b.sets):
            R = Rs[k]
            tri_g, bary_g = uv_gbuffer(b, k, R, d)
            inside = tri_g >= 0
            # tangent frame per texel (the base's TANGENT, bitangent = cross(N, T) w)
            tg = np.where(inside, tri_g, 0)
            Fg = b.F[tg]
            Ng = np.einsum('hwk,hwkd->hwd', bary_g, b.N[Fg])
            Ng /= np.maximum(np.linalg.norm(Ng, axis=2, keepdims=True), 1e-12)
            Tg = np.einsum('hwk,hwkd->hwd', bary_g, b.TAN[Fg][..., :3])
            Tg -= Ng * np.sum(Tg * Ng, axis=2, keepdims=True)
            Tg /= np.maximum(np.linalg.norm(Tg, axis=2, keepdims=True), 1e-12)
            wsign = np.sign(np.einsum('hwk,hwk->hw', bary_g, b.TAN[Fg][..., 3]))
            wsign[wsign == 0] = 1.0
            Bg = np.cross(Ng, Tg) * wsign[..., None]
            # the mask at every texel (style domain x not bare), on the texel's surface point
            pts = Pts(b, tg.reshape(-1), bary_g.reshape(-1, 3))
            mexp = {'mul': [self.style.get('domain', 1.0), {'not': self.style.get('bare', 0.0)}]}
            mask = np.clip(self.fields.eval(mexp, pts), 0, 1).reshape(R, R) * inside
            # samples along every clean segment of this set (both ends in the set, not across a seam: a seam crossing
            # is a segment whose uv length runs far beyond its length on the skin, in texels), interpolated in uv
            texel_m = tex_m[k]
            si, ki = np.nonzero(clean & (k0 == k))
            uva, uvb = uv[si, ki], uv[si, ki + 1]
            jump = np.linalg.norm((uvb - uva) * R, axis=1)
            ns = np.clip(np.ceil(jump * 1.5).astype(np.int64), 1, 64)
            rep = np.repeat(np.arange(len(si)), ns)
            frac = (np.arange(len(rep)) - np.repeat(np.cumsum(ns) - ns, ns) + 0.5) / np.repeat(ns, ns)
            q = uva[rep] + (uvb[rep] - uva[rep]) * frac[:, None]
            sseg = si[rep]
            kseg = ki[rep]
            hs = h[sseg, kseg] + (h[sseg, kseg + 1] - h[sseg, kseg]) * frac
            ts = t[kseg] + (t[kseg + 1] - t[kseg]) * frac
            dl = segp[sseg, kseg] / np.repeat(ns, ns)
            if xs is not None:
                # plus the seam-crossing segments' samples that landed in this set (each on its own closest point)
                xm = xs['set'] == k
                q = np.concatenate([q, xs['uv'][xm]])
                sseg = np.concatenate([sseg, xs['s'][xm]])
                kseg = np.concatenate([kseg, xs['k'][xm]])
                hs = np.concatenate([hs, xs['h'][xm]])
                ts = np.concatenate([ts, xs['t'][xm]])
                dl = np.concatenate([dl, xs['dl'][xm]])
            ix = np.clip((q[:, 0] * R).astype(np.int64), 0, R - 1)
            iy = np.clip((q[:, 1] * R).astype(np.int64), 0, R - 1)
            pix = iy * R + ix
            dens = np.zeros(R * R)
            np.add.at(dens, pix, dl * width / (texel_m * texel_m))
            top = np.full(R * R, -1.0)
            np.maximum.at(top, pix, hs)
            win = hs >= top[pix] - 1e-9
            # the visible fibre's attributes (the topmost sample)
            tt = np.zeros(R * R)
            sid = np.zeros(R * R)
            dvec = np.zeros((R * R, 3))
            tt[pix[win]] = ts[win]
            sid[pix[win]] = rnd[sseg[win]]
            dvec[pix[win]] = seg3[sseg[win], kseg[win]]
            hmax = np.where(top > 0, top, 0.0).reshape(R, R)
            # coverage: the projected density saturated by the gain (auto: median coated texel -> 0.9), times the mask
            dens = dens.reshape(R, R)
            from scipy import ndimage as nd
            # (round 2) the blur normalised by the island (a texel at the border averages its island's texels only:
            # the plain blur pulled the empty texels past the border in and darkened a rim along every seam)
            ins_f = inside.astype(np.float64)
            blur = cfg.get('blur_px', 1.0)
            dens_b = nd.gaussian_filter(dens * ins_f, blur) / np.maximum(nd.gaussian_filter(ins_f, blur), 1e-6) * ins_f
            gain = cfg.get('density_gain')
            sel = (mask > 0.5) & (dens_b > 0)
            if gain is None:
                med = np.median(dens_b[sel]) if sel.any() else 1.0
                gain = -np.log(0.1) / max(med, 1e-9)
            cov = mask * (1.0 - np.exp(-gain * dens_b))
            Hfull = cfg.get('height_mm', float(np.percentile(hmax[sel], 99)) * 1e3 if sel.any() else 1.0)
            # flow / lift / normal in the tangent frame
            dvec = dvec.reshape(R, R, 3)
            dl_ = np.linalg.norm(dvec, axis=2, keepdims=True)
            dn = np.where(dl_ > 0, dvec / np.maximum(dl_, 1e-12), 0.0)
            fx = np.sum(dn * Tg, axis=2)
            fy = np.sum(dn * Bg, axis=2)
            fz = np.sum(dn * Ng, axis=2)
            fl = np.sqrt(fx * fx + fy * fy)
            fx2, fy2 = fx / np.maximum(fl, 1e-9), fy / np.maximum(fl, 1e-9)
            lift = np.clip(fz, 0, 1)
            # the fur normal: the skin normal leaned against the fibre's lift, then grooves across the flow from the
            # strand ids (a ridge per fibre), both faded by coverage
            nxt = -fz * fx
            nyt = -fz * fy
            nzt = 1.0 - fz * fz
            groove = (sid.reshape(R, R) - 0.5) * cfg.get('groove', 0.35)
            nxt += -fy2 * groove
            nyt += fx2 * groove
            nn = np.stack([nxt, nyt, nzt], -1)
            nn /= np.maximum(np.linalg.norm(nn, axis=2, keepdims=True), 1e-9)
            c3 = cov[..., None]
            nn = nn * c3 + np.array([0.0, 0.0, 1.0]) * (1 - c3)
            nn /= np.maximum(np.linalg.norm(nn, axis=2, keepdims=True), 1e-9)
            vis = (top.reshape(R, R) > -0.5) & inside
            coat = np.stack([cov, np.clip(hmax * 1e3 / Hfull, 0, 1) * mask, np.where(vis, tt.reshape(R, R), 0.0),
                             np.where(vis, sid.reshape(R, R), 0.5)], -1)
            flow = np.stack([np.where(vis, fx2 * 0.5 + 0.5, 0.5), np.where(vis, fy2 * 0.5 + 0.5, 0.5),
                             np.where(vis, lift, 0.0), mask], -1)
            nrm = nn * 0.5 + 0.5
            # dilate everything past the islands (mips never pull black in)
            coat = push_pull(coat, inside)
            flow = push_pull(flow, inside)
            nrm = push_pull(nrm, inside)
            self.maps[sname] = dict(coat=coat.astype(np.float32), flow=flow.astype(np.float32),
                                    normal=nrm.astype(np.float32), res=R, height_mm=float(Hfull),
                                    density_gain=float(gain), texel_mm=float(texel_m * 1e3))
            cm = mask > 0.5
            self.stats[sname] = dict(res=R, texel_mm=round(texel_m * 1e3, 3), samples=int(len(pix)),
                                     coated_texels=int(cm.sum()),
                                     coverage_p10_50_90=np.round(np.percentile(cov[cm], [10, 50, 90]), 3).tolist()
                                     if cm.any() else None,
                                     height_full_mm=round(float(Hfull), 2), density_gain=round(float(gain), 3),
                                     seam_samples=int(xm.sum()) if xs is not None else 0,
                                     border_band=border_band(cov, vis, inside, cm))
            log(f'[coatmaps] {sname}: {R}^2, {len(pix)} samples, {self.stats[sname]}')
        log(f'[coatmaps] seam-crossing segments resampled in 3-D: {self.seam_resampled}')
        return self

    def shell_tile(self, groom_npz, tile_mm=10.0, px=256, children=6, dot_mm=0.11, log=print):
        """a tiling strand-dot texture for SHELLS, cut from a real tile_mm x tile_mm window of the groom (in the uv
        space of the set with the most coated area, where its texel density is uniform): every root in the window,
        plus `children` jittered copies (a pelt is denser than the groom's sample), drawn as a dot wrapped
        periodically. RGBA: R the strand's height as a fraction of the tallest (shell k shows it while R >= its
        height fraction), G strand id, B lean (the strand's run along the skin per unit height, / 2), A the dot mask"""
        from .roots import hkey
        b = self.base
        z = groom_npz
        tri = z['tri'].astype(np.int64)
        bary = z['bary'].astype(np.float64)
        P = z['points'].astype(np.float64)
        L = z['length'].astype(np.float64)
        _, N, UV, sets = b.tri_points(tri, bary)
        k = int(np.argmax([np.sum(sets == i) for i in range(len(b.sets))]))
        sname = b.sets[k]
        res = b.tex(sname, 'base').shape[0]
        mm_per_uv = res / b.px_per_m()[sname] * 1e3          # millimetres of skin per uv unit
        m = sets == k
        # the window: the FULLEST one of the set, so all of it lies on coated skin. (It was the window round the median
        # root, which nothing kept off an island's edge: about 45 % of it was empty uv, and the shells drew a dark stripe
        # every tile_mm across the mantle: the runtime builder's find, g5_runtime/look/i_shell_tile.png)
        w = tile_mm / mm_per_uv
        lo = UV[m].min(axis=0)
        nb = np.maximum(np.ceil((UV[m].max(axis=0) - lo) / w).astype(np.int64), 1)
        H, ex, ey = np.histogram2d(UV[m, 0], UV[m, 1], bins=[int(nb[0]), int(nb[1])],
                                   range=[[lo[0], lo[0] + nb[0] * w], [lo[1], lo[1] + nb[1] * w]])
        i_, j_ = np.unravel_index(int(np.argmax(H)), H.shape)
        c = np.array([ex[i_] + 0.5 * w, ey[j_] + 0.5 * w])
        sel = m & (np.abs(UV[:, 0] - c[0]) < w / 2) & (np.abs(UV[:, 1] - c[1]) < w / 2)
        assert sel.sum() >= 5, f'no roots in the shell window ({sel.sum()})'
        xy = (UV[sel] - (c - w / 2)) * mm_per_uv              # mm inside the window
        # the gate: roots in each eighth of the window, across and along, against their mean: an empty stretch shows as stripes
        fill = np.concatenate([np.histogram(xy[:, q], bins=8, range=(0.0, tile_mm))[0] for q in (0, 1)]) / max(sel.sum() / 8.0, 1e-9)
        assert fill.min() >= 0.25, f'the shell window has an empty stretch: eighths over their mean {np.round(fill, 2).tolist()}'
        dtip = P[sel, -1] - P[sel, 0]                         # root to tip
        hgt = np.abs(np.sum(dtip * N[sel], axis=1))           # the tip's height over the root's skin
        run = np.linalg.norm(dtip, axis=1)
        lean = np.sqrt(np.maximum(run ** 2 - hgt ** 2, 0.0)) / np.maximum(hgt, 1e-6)
        hf = hgt / max(float(hgt.max()), 1e-9)
        ids = np.nonzero(sel)[0]
        R = np.zeros((px, px), np.float32)
        G = np.zeros((px, px), np.float32)
        B = np.zeros((px, px), np.float32)
        A = np.zeros((px, px), np.float32)
        s = px / tile_mm
        rr = max(dot_mm * s, 1.0)
        yy, xx = np.mgrid[-int(rr) - 1:int(rr) + 2, -int(rr) - 1:int(rr) + 2]
        disk = (xx ** 2 + yy ** 2) <= rr * rr
        n_dots = 0
        for i, (x, y) in enumerate(xy):
            for j in range(children + 1):
                jx = (hkey(71, ids[i], j, ch=1) - 0.5) * 0.6 if j else 0.0
                jy = (hkey(71, ids[i], j, ch=2) - 0.5) * 0.6 if j else 0.0
                f = hf[i] * ((0.6 + 0.4 * hkey(71, ids[i], j, ch=3)) if j else 1.0)
                cx, cy = int(round((x + jx) * s)) % px, int(round((y + jy) * s)) % px
                X = (cx + xx[disk]) % px
                Y = (cy + yy[disk]) % px
                upd = f > R[Y, X]
                R[Y[upd], X[upd]] = f
                G[Y[upd], X[upd]] = hkey(73, ids[i], j, ch=1)
                B[Y[upd], X[upd]] = min(lean[i] / 2.0, 1.0)
                A[Y[upd], X[upd]] = 1.0
                n_dots += 1
        tile = np.stack([R, G, B, A], -1)
        self.shell = dict(tile=tile, tile_mm=tile_mm, px=px, set=sname, roots=int(sel.sum()), dots=n_dots,
                          coverage=float(A.mean()), lean_p50=float(np.median(lean)), fill_min=round(float(fill.min()), 3),
                          uv_per_tile={s_: tile_mm / (b.tex(s_, 'base').shape[0] / b.px_per_m()[s_] * 1e3)
                                       for s_ in b.sets})
        log(f'[coatmaps] shell tile: {sel.sum()} roots in a {tile_mm} mm window of {sname} (x{children + 1} '
            f'children) -> {n_dots} dots, base coverage {A.mean():.2f}, lean p50 {np.median(lean):.2f}, the emptiest eighth '
            f'{fill.min():.2f} x the mean')
        return self.shell

    def scalp(self, groom_npz, cfg, log=print):
        """(B3, HAIR_FUR H6) THE SCALP PRESET: the skin under human hair, baked on one skin set's UVs (cfg: set, res,
        near_mm, part_show, part_mm, stripe_um), RGBA:
          R  the hair's COVER of the skin: the style's root mask (the hairline's fade) with the parting opened
             (x 1 - part_show exp(-(d / part_mm)^2): skin shows along a part's line) - the runtime takes the skin toward
             the hair's root colour by it (root darkening in the hair colour: study T's haircap, HS §9.6's skin layer)
          G  painted STRANDS: the strands lying within near_mm of the scalp splatted as fine fibres (stripe_um wide) and
             saturated: the haircap's flow-aligned short strands, the crown whorl's spiral and the part drawn by the groom
          BA the visible fibre's direction in the set's tangent frame x 0.5 + 0.5 (the near strands' topmost, else the
             groom's flow field): the strand normal's / anisotropy's direction
        Works on a base without albedo maps (the texel size from the set's own uv area against its world area)"""
        b = self.base
        z = groom_npz
        d = self.device
        k = b.sets.index(cfg['set'])
        R = int(cfg.get('res', 2048))
        m = b.face_set == k
        Fv = b.F[m]
        uva = 0.5 * np.abs((b.UV[Fv[:, 1], 0] - b.UV[Fv[:, 0], 0]) * (b.UV[Fv[:, 2], 1] - b.UV[Fv[:, 0], 1])
                           - (b.UV[Fv[:, 2], 0] - b.UV[Fv[:, 0], 0]) * (b.UV[Fv[:, 1], 1] - b.UV[Fv[:, 0], 1]))
        texel_m = float(np.median(np.sqrt(b.area[m] / np.maximum(uva, 1e-20)))) / R
        tri_g, bary_g = uv_gbuffer(b, k, R, d)
        inside = tri_g >= 0
        tg = np.where(inside, tri_g, 0)
        Fg = b.F[tg]
        Ng = np.einsum('hwk,hwkd->hwd', bary_g, b.N[Fg])
        Ng /= np.maximum(np.linalg.norm(Ng, axis=2, keepdims=True), 1e-12)
        Tg = np.einsum('hwk,hwkd->hwd', bary_g, b.TAN[Fg][..., :3])
        Tg -= Ng * np.sum(Tg * Ng, axis=2, keepdims=True)
        Tg /= np.maximum(np.linalg.norm(Tg, axis=2, keepdims=True), 1e-12)
        wsign = np.sign(np.einsum('hwk,hwk->hw', bary_g, b.TAN[Fg][..., 3]))
        wsign[wsign == 0] = 1.0
        Bg = np.cross(Ng, Tg) * wsign[..., None]
        pts = Pts(b, tg.reshape(-1), bary_g.reshape(-1, 3))
        mask = np.clip(self.fields.eval(self.style.get('domain', 1.0), pts), 0, 1).reshape(R, R) * inside
        # the parting opened (the style's part lines, rebuilt on the welded low, blended at the texels)
        from .flow import Flow
        fl = Flow(b, self.fields)
        fl._sources(self.style['flow'])
        part_open = np.zeros((R, R))
        for pr in fl.parts:
            dv = pr['dist'][b.wid]
            dt = np.einsum('nk,nk->n', pts.bary, dv[b.F[pts.tri]]).reshape(R, R)
            part_open = np.maximum(part_open, np.exp(-(dt / (float(cfg.get('part_mm', 1.6)) * 1e-3)) ** 2))
        cover = mask * (1.0 - float(cfg.get('part_show', 0.55)) * part_open)
        # the groom's flow at every texel (fallback direction)
        fw = z['flow'].astype(np.float64)[b.wid]
        fv = np.einsum('nk,nkd->nd', pts.bary, fw[b.F[pts.tri]]).reshape(R, R, 3)
        # the near-scalp strand samples, splatted (every segment sampled at half a texel, closest skin point, height)
        P = z['points'].astype(np.float64)
        S, K = P.shape[:2]
        near = float(cfg.get('near_mm', 6.0)) * 1e-3
        seg = np.diff(P, axis=1)
        L = np.linalg.norm(seg, axis=2)
        ns = np.clip(np.ceil(L / (0.5 * texel_m)).astype(np.int64), 1, 64)
        mesh = wp.Mesh(points=wp.array(b.V.astype(np.float32), dtype=wp.vec3, device=d),
                       indices=wp.array(b.F.astype(np.int32).reshape(-1), dtype=wp.int32, device=d))
        # only the segments with an end near the scalp (the hanging lengths never reach it)
        X = P.reshape(-1, 3)
        nx_ = len(X)
        f0 = wp.zeros(nx_, dtype=wp.int32, device=d)
        u0 = wp.zeros(nx_, dtype=wp.float32, device=d)
        v0 = wp.zeros(nx_, dtype=wp.float32, device=d)
        h0 = wp.zeros(nx_, dtype=wp.float32, device=d)
        wp.launch(k_closest, dim=nx_, device=d,
                  inputs=[mesh.id, wp.array(X.astype(np.float32), dtype=wp.vec3, device=d), f0, u0, v0, h0,
                          wp.array(b.FN.astype(np.float32), dtype=wp.vec3, device=d)])
        hp = h0.numpy().reshape(S, K)
        si, ki = np.nonzero(np.minimum(hp[:, :-1], hp[:, 1:]) < near)
        nsf = ns[si, ki]
        rep = np.repeat(np.arange(len(si)), nsf)
        fr = (np.arange(len(rep)) - np.repeat(np.cumsum(nsf) - nsf, nsf) + 0.5) / np.repeat(nsf, nsf)
        Q = P[si[rep], ki[rep]] + seg[si[rep], ki[rep]] * fr[:, None]
        n = len(Q)
        face = wp.zeros(n, dtype=wp.int32, device=d)
        bu = wp.zeros(n, dtype=wp.float32, device=d)
        bv = wp.zeros(n, dtype=wp.float32, device=d)
        hh = wp.zeros(n, dtype=wp.float32, device=d)
        wp.launch(k_closest, dim=n, device=d,
                  inputs=[mesh.id, wp.array(Q.astype(np.float32), dtype=wp.vec3, device=d), face, bu, bv, hh,
                          wp.array(b.FN.astype(np.float32), dtype=wp.vec3, device=d)])
        f = face.numpy().astype(np.int64)
        h = hh.numpy().astype(np.float64)
        sel = (b.face_set[f] == k) & (h < near)
        f, h = f[sel], h[sel]
        bq = np.column_stack([bu.numpy()[sel], bv.numpy()[sel], 1.0 - bu.numpy()[sel] - bv.numpy()[sel]]).astype(np.float64)
        uv = np.einsum('nk,nkd->nd', bq, b.UV[b.F[f]])
        dl = (L[si[rep], ki[rep]] / np.repeat(nsf, nsf))[sel]
        dvec = seg[si[rep], ki[rep]][sel]
        ix = np.clip((uv[:, 0] * R).astype(np.int64), 0, R - 1)
        iy = np.clip((uv[:, 1] * R).astype(np.int64), 0, R - 1)
        pix = iy * R + ix
        width = float(cfg.get('stripe_um', 80.0)) * 1e-6
        dens = np.zeros(R * R)
        np.add.at(dens, pix, dl * width / (texel_m * texel_m))
        top = np.full(R * R, np.inf)
        np.minimum.at(top, pix, -h)                              # the topmost (largest h) wins: min of -h
        win = -h <= top[pix] + 1e-12
        dsel = np.zeros((R * R, 3))
        dsel[pix[win]] = dvec[win]
        has = np.isfinite(top).reshape(R, R)
        dmap = np.where(has[..., None], dsel.reshape(R, R, 3), fv)
        dmap -= Ng * np.sum(dmap * Ng, axis=2, keepdims=True)
        fx, fy = np.sum(dmap * Tg, axis=2), np.sum(dmap * Bg, axis=2)
        fl_ = np.maximum(np.sqrt(fx * fx + fy * fy), 1e-9)
        stripe = (1.0 - np.exp(-1.2 * dens.reshape(R, R))) * mask
        pack = np.stack([cover, stripe, fx / fl_ * 0.5 + 0.5, fy / fl_ * 0.5 + 0.5], -1) * inside[..., None]
        pack = push_pull(pack, inside)
        cm = mask > 0.5
        stats = dict(set=cfg['set'], res=R, texel_mm=round(texel_m * 1e3, 3), near_samples=int(sel.sum()),
                     scalp_texels=int(cm.sum()), cover_p10_50_90=np.round(np.percentile(cover[cm], [10, 50, 90]), 3).tolist(),
                     stripe_p10_50_90=np.round(np.percentile(stripe[cm], [10, 50, 90]), 3).tolist(),
                     part_texels_open_over_0p3=int(((part_open > 0.3) & cm).sum()))
        log(f'[coatmaps] scalp {json.dumps(stats)}')
        return dict(pack=pack.astype(np.float32), stats=stats,
                    channels='R the hair\'s cover of the skin (hairline fade x the part opened), G painted near-scalp '
                             'strands, BA the fibre direction in the set\'s tangent frame x 0.5 + 0.5')

    def save(self, folder, prefix):
        import os
        from PIL import Image
        os.makedirs(folder, exist_ok=True)
        files = {}
        for sname, m in self.maps.items():
            f = {}
            for key, mode in (('coat', 'RGBA'), ('flow', 'RGBA'), ('normal', 'RGB')):
                p = os.path.join(folder, f'{prefix}_{sname}_{key}.png')
                Image.fromarray((np.clip(m[key], 0, 1) * 255 + 0.5).astype(np.uint8), mode).save(p)
                f[key] = os.path.basename(p)
            files[sname] = f
        return files
