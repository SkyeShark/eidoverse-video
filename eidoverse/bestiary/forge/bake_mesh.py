"""THE MESH BAKE (Warp): a TRIANGLE high onto the low's UVs, per texel at ss x ss sub-samples: forge/bake.py's model (the
UV layout as a BVH in texel space, the runtime's own tangent frame, the matched inverse) with each low triangle's own
PIECE's triangle high in place of the SDF. For the CROSSBREED's rigid SHELLS (CROSSBREED_DESIGN §2.9: each shell its own
program and bake; the beetle's B4 leg cages: the low the cage at its limit positions, the high its L4 limit mesh, both
from families/arthropod_cage.py), whose creases and extruded teeth live in the cage, not in any field:

  1. the low under the sub-sample: its point, normal and tangent frame (the exported per-vertex tangent, bitangent =
     cross(N, T) * sign, interpolated: three's frame, bake.py's);
  2. the search: rays from the low point along +n and -n against the texel's OWN piece's high (each texel samples its
     own piece: C5a-3's rule, so a neighbouring shell never takes a texel), at most `cage` each way; a hit counts when
     the high's normal faces the low's (dot > face_min); the nearer accepted hit wins; else a miss (the gate sees it);
  3. the normal: the high's smooth vertex normal interpolated at the hit, through the inverse of mat3(T, B, N);
  4. AO: cosine rays from the hit about the high's normal against EVERY occluder (all pieces' highs and any extra
     meshes: the collar the tibia sinks in), out to ao_r (visibility, 1 = open: bake.py's convention); CAVITY the same
     at cav_r;
  5. THICKNESS: rays into the piece's high until they leave it (thk_max);
  6. CURVATURE: the high's per-vertex 2 H (the cotangent Laplacian's normal component: bake.py's field Laplacian is 2 H
     for a distance field) interpolated at the hit;
  7. HEIGHT: the hit's offset along the low's normal (+ above); POSITION and BASE the hit (a shell has no block-out).
Outputs as bake.py's (size x size, rows top-down): normal (rgb tangent, a coverage), ao, cavity, thickness, curvature,
height, position, base, region (the piece), miss; and the gate's numbers per piece (coverage, misses whole and partly,
|height| p95 / max, the hits farther than the nearest surface by more than far_tol: a fold crossed).
"""
import numpy as np
import warp as wp

wp.set_module_options({'enable_backward': False})


@wp.func
def frame_inv(t: wp.vec3, b: wp.vec3, n: wp.vec3, v: wp.vec3):
    m = wp.mat33(t[0], b[0], n[0], t[1], b[1], n[1], t[2], b[2], n[2])
    if wp.abs(wp.determinant(m)) < 1.0e-9:
        return wp.vec3(0.0, 0.0, 1.0)
    return wp.inverse(m) @ v


@wp.func
def cos_dir(n: wp.vec3, r1: float, r2: float):
    a = wp.vec3(0.0, 0.0, 1.0)
    if wp.abs(n[2]) > 0.9:
        a = wp.vec3(1.0, 0.0, 0.0)
    t1 = wp.normalize(wp.cross(n, a))
    t2 = wp.cross(n, t1)
    phi = 6.283185307 * r1
    sr = wp.sqrt(r2)
    return wp.normalize(t1 * (sr * wp.cos(phi)) + t2 * (sr * wp.sin(phi)) + n * wp.sqrt(wp.max(0.0, 1.0 - r2)))


@wp.func
def hi_normal(hn: wp.array(dtype=wp.vec3), htri: wp.array(dtype=wp.int32), foff: int, f: int, u: float, v: float):
    i0 = htri[3 * (foff + f)]
    i1 = htri[3 * (foff + f) + 1]
    i2 = htri[3 * (foff + f) + 2]
    return wp.normalize(hn[i0] * u + hn[i1] * v + hn[i2] * (1.0 - u - v))


@wp.func
def hi_scalar(hs: wp.array(dtype=wp.float32), htri: wp.array(dtype=wp.int32), foff: int, f: int, u: float, v: float):
    i0 = htri[3 * (foff + f)]
    i1 = htri[3 * (foff + f) + 1]
    i2 = htri[3 * (foff + f) + 2]
    return hs[i0] * u + hs[i1] * v + hs[i2] * (1.0 - u - v)


@wp.kernel
def k_mbake(uv_mesh: wp.uint64, size: int, ss: int, row0: int, cage: float, face_min: float, ao_r: float, cav_r: float,
            n_ao: int, n_cav: int, n_thk: int, thk_max: float, seed: int,
            lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3), ltan: wp.array(dtype=wp.vec4),
            tri_piece: wp.array(dtype=wp.int32), piece_mesh: wp.array(dtype=wp.uint64),
            piece_foff: wp.array(dtype=wp.int32), hn: wp.array(dtype=wp.vec3), hcurv: wp.array(dtype=wp.float32),
            htri: wp.array(dtype=wp.int32), occ_mesh: wp.uint64,
            o_nrm: wp.array(dtype=wp.vec4), o_ao: wp.array(dtype=wp.float32), o_cav: wp.array(dtype=wp.float32),
            o_thk: wp.array(dtype=wp.float32), o_curv: wp.array(dtype=wp.float32), o_hgt: wp.array(dtype=wp.float32),
            o_pos: wp.array(dtype=wp.vec4), o_reg: wp.array(dtype=wp.int32), o_miss: wp.array(dtype=wp.int32),
            o_low: wp.array(dtype=wp.vec4)):
    tid = wp.tid() + row0 * size
    px = tid % size
    py = tid // size
    state = wp.rand_init(seed, tid)
    acc_n = wp.vec3(0.0)
    acc_ao = float(0.0)
    acc_cav = float(0.0)
    acc_thk = float(0.0)
    acc_curv = float(0.0)
    acc_h = float(0.0)
    acc_p = wp.vec3(0.0)
    acc_l = wp.vec3(0.0)
    got = int(0)
    cov = int(0)
    miss = int(0)
    reg = int(-1)
    for i in range(ss):
        for j in range(ss):
            fx = float(px) + (float(i) + 0.5) / float(ss)
            fy = float(py) + (float(j) + 0.5) / float(ss)
            q = wp.mesh_query_ray(uv_mesh, wp.vec3(fx, fy, 1.0), wp.vec3(0.0, 0.0, -1.0), 2.0)
            if not q.result:
                continue
            cov += 1
            f = q.face
            w = 1.0 - q.u - q.v
            p = lpos[3 * f] * q.u + lpos[3 * f + 1] * q.v + lpos[3 * f + 2] * w
            n = wp.normalize(lnrm[3 * f] * q.u + lnrm[3 * f + 1] * q.v + lnrm[3 * f + 2] * w)
            t4 = ltan[3 * f] * q.u + ltan[3 * f + 1] * q.v + ltan[3 * f + 2] * w
            t = wp.normalize(wp.vec3(t4[0], t4[1], t4[2]))
            sg = float(1.0)
            if ltan[3 * f][3] < 0.0:
                sg = -1.0
            b = wp.cross(n, t) * sg
            pc = tri_piece[f]
            reg = pc
            mid = piece_mesh[pc]
            foff = piece_foff[pc]
            best_t = float(1.0e9)
            best_f = int(-1)
            best_u = float(0.0)
            best_v = float(0.0)
            best_s = float(0.0)
            for sgn in range(2):
                d = n
                if sgn == 1:
                    d = -n
                h = wp.mesh_query_ray(mid, p, d, cage)
                if h.result:
                    nh = hi_normal(hn, htri, foff, h.face, h.u, h.v)
                    if wp.dot(nh, n) > face_min and h.t < best_t:
                        best_t = h.t
                        best_f = h.face
                        best_u = h.u
                        best_v = h.v
                        best_s = 1.0 - 2.0 * float(sgn)
            acc_l = acc_l + p
            if best_f < 0:
                miss += 1
                continue
            got += 1
            hp = p + n * (best_t * best_s)
            nh = hi_normal(hn, htri, foff, best_f, best_u, best_v)
            acc_n = acc_n + frame_inv(t, b, n, nh)
            acc_h = acc_h + best_t * best_s
            acc_p = acc_p + hp
            acc_curv = acc_curv + hi_scalar(hcurv, htri, foff, best_f, best_u, best_v)
            o = hp + nh * 1.0e-5
            vis = float(0.0)
            for k in range(n_ao):
                d = cos_dir(nh, wp.randf(state), wp.randf(state))
                r = wp.mesh_query_ray(occ_mesh, o, d, ao_r)
                if not r.result:
                    vis += 1.0
            acc_ao = acc_ao + vis / float(n_ao)
            vis_c = float(0.0)
            for k in range(n_cav):
                d = cos_dir(nh, wp.randf(state), wp.randf(state))
                r = wp.mesh_query_ray(occ_mesh, o, d, cav_r)
                if not r.result:
                    vis_c += 1.0
            acc_cav = acc_cav + vis_c / float(n_cav)
            th = float(0.0)
            oi = hp - nh * 1.0e-5
            for k in range(n_thk):
                d = cos_dir(-nh, wp.randf(state), wp.randf(state) * 0.25)
                r = wp.mesh_query_ray(mid, oi, d, thk_max)
                if r.result:
                    th += r.t
                else:
                    th += thk_max
            acc_thk = acc_thk + th / float(n_thk)
    o_reg[tid] = reg
    o_miss[tid] = miss
    if cov > 0:
        o_low[tid] = wp.vec4(acc_l[0] / float(cov), acc_l[1] / float(cov), acc_l[2] / float(cov), 1.0)
    if got > 0:
        g = float(got)
        nn = wp.normalize(acc_n)
        o_nrm[tid] = wp.vec4(nn[0], nn[1], nn[2], float(got) / float(ss * ss))
        o_ao[tid] = acc_ao / g
        o_cav[tid] = acc_cav / g
        o_thk[tid] = acc_thk / g
        o_curv[tid] = acc_curv / g
        o_hgt[tid] = acc_h / g
        o_pos[tid] = wp.vec4(acc_p[0] / g, acc_p[1] / g, acc_p[2] / g, 1.0)


@wp.kernel
def k_closest(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=wp.float32)):
    i = wp.tid()
    q = wp.mesh_query_point_no_sign(mesh, pts[i], maxd)
    if q.result:
        c = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        out[i] = wp.length(pts[i] - c)
    else:
        out[i] = maxd


def vertex_normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-20)


def mean_curvature2(V, F, N):
    """2 H per vertex (1/m, + convex): the cotangent Laplacian of the positions dotted with the outward normal, over the
    vertex's mixed area (a third of its triangles' areas)"""
    V = np.asarray(V, np.float64)
    L = np.zeros_like(V)
    area = np.zeros(len(V))
    for a, b, c in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
        i, j, k = F[:, a], F[:, b], F[:, c]
        u, v = V[i] - V[k], V[j] - V[k]
        cot = (u * v).sum(1) / np.maximum(np.linalg.norm(np.cross(u, v), axis=1), 1e-30)
        d = (V[j] - V[i]) * cot[:, None]
        np.add.at(L, i, d)
        np.add.at(L, j, -d)
    A = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    for k in range(3):
        np.add.at(area, F[:, k], A / 3.0)
    Lv = 0.5 * L / np.maximum(area, 1e-30)[:, None]
    return -(Lv * N).sum(1)


def bake(low, pieces, size, occluders=(), ss=2, cage=0.004, face_min=0.2, ao_r=0.025, cav_r=0.0025, n_ao=24, n_cav=12,
         n_thk=6, thk_max=0.05, seed=7, band_rows=128, far_tol=1.0e-4, log=print):
    """low: dict(V, F, UV (forge v up, 0-1), N, TAN (n, 4), piece (per triangle: an index into pieces)); pieces: list of
    dict(V, F) highs (metres, the creature frame); occluders: more (V, F) meshes the AO and cavity rays also meet.
    Returns bake.py's arrays (rows top-down) plus 'low_point', and 'gate': per piece numbers"""
    import time
    t0 = time.time()
    F = np.asarray(low['F'], np.int32)
    corner = F.ravel()
    luv = np.asarray(low['UV'], np.float64)[corner] * size
    uv_mesh = wp.Mesh(points=wp.array(np.column_stack([luv, np.zeros(len(luv))]).astype(np.float32), dtype=wp.vec3),
                      indices=wp.array(np.arange(len(luv), dtype=np.int32), dtype=wp.int32))
    lpos = wp.array(np.asarray(low['V'], np.float32)[corner], dtype=wp.vec3)
    lnrm = wp.array(np.asarray(low['N'], np.float32)[corner], dtype=wp.vec3)
    ltan = wp.array(np.asarray(low['TAN'], np.float32)[corner], dtype=wp.vec4)
    tri_piece = wp.array(np.asarray(low['piece'], np.int32), dtype=wp.int32)
    meshes, foffs, hn_all, hc_all, ht_all = [], [], [], [], []
    voff, foff = 0, 0
    curv_stats = []
    for pc in pieces:
        V, Fh = np.asarray(pc['V'], np.float64), np.asarray(pc['F'], np.int64)
        N = vertex_normals(V, Fh)
        C = mean_curvature2(V, Fh, N)
        curv_stats.append(float(np.percentile(np.abs(C), 95)))
        meshes.append(wp.Mesh(points=wp.array(V.astype(np.float32), dtype=wp.vec3),
                              indices=wp.array(Fh.astype(np.int32).ravel(), dtype=wp.int32)))
        foffs.append(foff)
        hn_all.append(N)
        hc_all.append(C)
        ht_all.append(Fh + voff)
        voff += len(V)
        foff += len(Fh)
    piece_mesh = wp.array(np.array([m.id for m in meshes], np.uint64), dtype=wp.uint64)
    piece_foff = wp.array(np.array(foffs, np.int32), dtype=wp.int32)
    hn = wp.array(np.concatenate(hn_all).astype(np.float32), dtype=wp.vec3)
    hcurv = wp.array(np.concatenate(hc_all).astype(np.float32), dtype=wp.float32)
    htri = wp.array(np.concatenate(ht_all).astype(np.int32).ravel(), dtype=wp.int32)
    OV, OF, off = [], [], 0
    for pc in list(pieces) + [dict(V=o[0], F=o[1]) for o in occluders]:
        OV.append(np.asarray(pc['V'], np.float32))
        OF.append(np.asarray(pc['F'], np.int64) + off)
        off += len(pc['V'])
    occ = wp.Mesh(points=wp.array(np.concatenate(OV), dtype=wp.vec3),
                  indices=wp.array(np.concatenate(OF).astype(np.int32).ravel(), dtype=wp.int32))
    n = size * size
    outs = dict(normal=wp.zeros(n, dtype=wp.vec4), ao=wp.zeros(n, dtype=wp.float32), cavity=wp.zeros(n, dtype=wp.float32),
                thickness=wp.zeros(n, dtype=wp.float32), curvature=wp.zeros(n, dtype=wp.float32),
                height=wp.zeros(n, dtype=wp.float32), position=wp.zeros(n, dtype=wp.vec4),
                region=wp.full(n, -1, dtype=wp.int32), miss=wp.zeros(n, dtype=wp.int32), low_point=wp.zeros(n, dtype=wp.vec4))
    rows = max(1, min(size, band_rows))
    for r0 in range(0, size, rows):
        nr = min(rows, size - r0)
        wp.launch(k_mbake, dim=nr * size, inputs=[
            uv_mesh.id, size, ss, r0, float(cage), float(face_min), float(ao_r), float(cav_r), int(n_ao), int(n_cav),
            int(n_thk), float(thk_max), int(seed), lpos, lnrm, ltan, tri_piece, piece_mesh, piece_foff, hn, hcurv,
            htri, occ.id, outs['normal'], outs['ao'], outs['cavity'], outs['thickness'], outs['curvature'],
            outs['height'], outs['position'], outs['region'], outs['miss'], outs['low_point']])
        wp.synchronize()
    res = {}
    for k, a in outs.items():
        arr = a.numpy()
        arr = arr.reshape(size, size, -1) if arr.ndim > 1 else arr.reshape(size, size)
        res[k] = arr[::-1].copy()
    res['base'] = res['position'].copy()
    # ---- the gate, per piece
    cov = res['normal'][..., 3] > 0
    inside = cov | (res['miss'] > 0)
    gate = []
    for i in range(len(pieces)):
        m = res['region'] == i
        ins = inside & m
        full = (res['miss'] > 0) & ~cov & m
        part = (res['miss'] > 0) & cov & m
        hg = np.abs(res['height'][cov & m])
        # a hit farther from the low point than the nearest surface by more than far_tol (a fold crossed)
        ys, xs = np.nonzero(cov & m)
        far = 0
        if len(ys):
            P = res['low_point'][ys, xs, :3].astype(np.float32)
            o = wp.zeros(len(P), dtype=wp.float32)
            wp.launch(k_closest, dim=len(P), inputs=[meshes[i].id, wp.array(P, dtype=wp.vec3), float(cage), o])
            dc = o.numpy()
            far = int(((np.abs(res['height'][ys, xs]) - dc) > far_tol).sum())
        gate.append(dict(piece=i, texels=int(ins.sum()), full_miss_pct=float(full.sum() / max(ins.sum(), 1) * 100),
                         part_miss_pct=float(part.sum() / max(ins.sum(), 1) * 100),
                         height_p95_mm=float(np.percentile(hg, 95) * 1e3) if len(hg) else 0.0,
                         height_max_mm=float(hg.max() * 1e3) if len(hg) else 0.0, far_hits=far,
                         curv_p95=curv_stats[i]))
    res['gate'] = gate
    ok = all(g['full_miss_pct'] <= 0.5 and g['part_miss_pct'] <= 0.5 and g['height_p95_mm'] <= 3.0 for g in gate)
    res['gate_ok'] = ok
    log(f'[mbake] {size}^2 x ss {ss}: {time.time() - t0:.1f}s, coverage {cov.mean() * 100:.1f} %, pieces {len(pieces)}; '
        f'worst full miss {max(g["full_miss_pct"] for g in gate):.3f} %, partly {max(g["part_miss_pct"] for g in gate):.3f} %'
        f', |height| p95 {max(g["height_p95_mm"] for g in gate):.2f} mm (bars 0.5 %, 0.5 %, 3 mm): '
        f'{"PASS" if ok else "FAIL"}')
    return res
