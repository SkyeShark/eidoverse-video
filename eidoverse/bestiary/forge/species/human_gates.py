"""HUMAN H1: the GATES of the baseline figure (HUMAN_PLAN §9.2 H1, §11; the lead's H1 decision 4).

PER REGION: the two-way distance between the clay (the limit surface) and its reference, its p95 AND its p99.9 and max
(p95 cannot see a thin fin: H0's ears passed p95 at 0.5 mm with fins to 4.5 mm), AND a FOLD check: the share of the
clay's area whose normal turns more than 90 deg against the reference's normal at the CORRESPONDING point (the limit of
the targets carried to the reference; a closest point lands on the opposite lip across a closed seam, the H0 review's
120-150 mm2 of false folds). Bars per region (the technician's, HUMAN_BODY_PHOTOS §5.1): face 1.0, nose 0.8, lips 0.8,
lids 0.8, nostrils 0.8, ears 1.5, cranium 2.0, neck 2.0 mm; the body's regions (against the pinned MakeHuman) take the
cranium's 2.0 [E: the plan names no body bar; the body is read at normal viewing, 1.8 mm a pixel]. Folds: 0 % outside
a tolerance of 0.5 % of a region's area [E: H1].

THE CAGE: manifold, mirrored, poles listed (and where), loops per hinge, min angle p1 >= 25 deg, aspect p99 <= 4.
THE RINGS: K (mod 4), planarity (max distance from the best plane over the mean radius, <= 0.02), the collar (no pole,
crease or other ring within h), the chord sag r_max (1 - cos pi / K) in texels at the set's density.
"""
import numpy as np

from . import human_ref as HR

HEAD_BARS = dict(lids=0.8, lips=0.8, nostrils=0.8, ears=1.5, nose=0.8, face=1.0, cranium=2.0, neck=2.0, inner=None)
HEAD_ORDER = ('lids', 'lips', 'nostrils', 'ears', 'nose', 'face', 'cranium', 'neck', 'inner')
FOLD_TOL = 0.005


def d_poly(P, C, closed=True):
    A = C
    B = np.roll(C, -1, axis=0) if closed else C[1:]
    A = A if closed else C[:-1]
    best = np.full(len(P), np.inf)
    for a, b in zip(A, B):
        ab = b - a
        t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        best = np.minimum(best, np.linalg.norm(P - (a + t[:, None] * ab), axis=1))
    return best


def gnm_regions(g, fz, margin_pts, keep=None):
    """GNM's vertices labelled with the technician's regions (probe 1's rules; the lids measured from the cage's own
    margin ring, which runs to the inner canthus); keep: the vertices on the head's side of the neck ring"""
    V, grp = g.V, g.grp
    dm = np.minimum(d_poly(V, margin_pts), d_poly(V, margin_pts * np.array([-1, 1, 1])))
    dv = d_poly(V, V[fz['vermilion_v']])
    di = d_poly(V, V[fz['inner_lip_v']])
    rx = g.uv_to_3d(fz['nostril_rim_uv'])[0]
    dn = np.minimum(d_poly(V, rx), d_poly(V, rx * np.array([-1, 1, 1])))
    from matplotlib.path import Path as MPath
    vuv = fz['vuv']
    ruv = fz['nostril_rim_uv']
    pocket = MPath(ruv).contains_points(np.nan_to_num(vuv)) | \
        MPath(ruv * np.array([-1, 1]) + np.array([1, 0])).contains_points(np.nan_to_num(vuv))
    ext, sock, socket = grp['skin_exterior'], grp['mouth_sock'], grp['eye_sockets']
    lab = np.full(len(V), 'neck', dtype=object)
    # the cranium: the exterior above the eye joints' height less 70 mm, off the face (probe 1 used y >= 230 on GNM's
    # mean; carried by the eyes for every identity)
    ye = 0.5 * (g.joints['left_eye'][1] + g.joints['right_eye'][1])
    lab[ext & (V[:, 1] >= ye - 73.0)] = 'cranium'
    lab[grp['hockey_mask']] = 'face'
    lab[grp['nose_region']] = 'nose'
    lab[grp['ears']] = 'ears'
    lab[sock | socket] = 'inner'
    lab[(dn <= 3.0) | (pocket & grp['nose_region'])] = 'nostrils'
    lab[(ext & (dm <= 6.0)) | (socket & (dm <= 3.0))] = 'lids'
    lab[grp['upper_lip'] | grp['lower_lip'] | (ext & (dv <= 2.5)) | (sock & (di <= 3.0))] = 'lips'
    if keep is not None:
        lab[~keep] = 'out'
    return lab


def tri_labels(F, lab):
    # ties (1:1:1) go to the alphabetically first label: max() over a bare set broke them by the set's order, which
    # python's per-process string hashing reshuffles, so a region's border triangles (its area, folded share and
    # p95) changed from run to run on the same clay (look:h2: H2's gates.json, two runs of one cage)
    out = []
    for f in F:
        ls = [lab[v] for v in f]
        out.append(max(sorted(set(ls)), key=ls.count))
    return np.array(out, dtype=object)


def surface_samples(V, F, nsub=5):
    bc = np.array([(i / nsub, j / nsub, 1 - (i + j) / nsub) for i in range(nsub + 1) for j in range(nsub + 1 - i)])
    S = np.einsum('sk,tkd->tsd', bc, V[F]).reshape(-1, 3)
    return S, len(bc)


def regional(lim_V, lim_F, ref, ref_F_lab, ref_V, ref_F, tri_ref_normal, tri_ref_label, bars, order, nsub=5,
             clay_full=None):
    """the two-way distances and folds per region. lim: the clay (vertices, triangles); ref: a TriMesh of the reference
    (its triangles ref_F, labels ref_F_lab); tri_ref_normal, tri_ref_label: per clay TRIANGLE the reference's normal
    and region at its ANCESTOR cage quad (the mean of the reference's normals at that quad's four targets, read from
    their own reference triangles: the correspondence a closed seam cannot fool); clay_full: (V, F) of the WHOLE clay
    for the reference -> clay direction (the region's own clay alone leaves reference skin by its border, under the neck
    base, with no clay near it: a false 3.8 mm trunk p95). Returns a dict per region"""
    S, nbc = surface_samples(ref_V, ref_F, nsub)
    S_lab = np.repeat(ref_F_lab, nbc)
    M = HR.TriMesh(*clay_full) if clay_full is not None else HR.TriMesh(lim_V, lim_F)
    p, _, _ = M.closest(S)
    d_rf = np.linalg.norm(p - S, axis=1)
    q, rf, rb = ref.closest(lim_V)
    d_fr = np.linalg.norm(q - lim_V, axis=1)
    fr_lab = ref_F_lab[rf]
    # folds: the clay's triangle normals against the reference's at their ancestor quads
    fn = np.cross(lim_V[lim_F[:, 1]] - lim_V[lim_F[:, 0]], lim_V[lim_F[:, 2]] - lim_V[lim_F[:, 0]])
    area = 0.5 * np.linalg.norm(fn, axis=1)
    fn = fn / np.maximum(2 * area, 1e-12)[:, None]
    cosv = np.einsum('ij,ij->i', fn, tri_ref_normal)
    folded = cosv < 0.0
    t_lab = tri_ref_label
    out = {}
    for r in order:
        a = d_rf[S_lab == r]
        bb = d_fr[fr_lab == r]
        if not len(a) or not len(bb):
            continue
        row = dict(ref_to_clay_p95=float(np.percentile(a, 95)), ref_to_clay_p999=float(np.percentile(a, 99.9)),
                   ref_to_clay_max=float(a.max()), clay_to_ref_p95=float(np.percentile(bb, 95)),
                   clay_to_ref_p999=float(np.percentile(bb, 99.9)), clay_to_ref_max=float(bb.max()))
        row['p95'] = max(row['ref_to_clay_p95'], row['clay_to_ref_p95'])
        row['p999'] = max(row['ref_to_clay_p999'], row['clay_to_ref_p999'])
        row['max'] = max(row['ref_to_clay_max'], row['clay_to_ref_max'])
        m = t_lab == r
        row['area_mm2'] = float(area[m].sum())
        row['folded_mm2'] = float(area[m & folded].sum())
        row['folded_pct'] = 100.0 * row['folded_mm2'] / max(row['area_mm2'], 1e-9)
        row['bar'] = bars.get(r)
        if row['bar'] is not None:
            row['pass_p95'] = bool(row['p95'] <= row['bar'])
            row['pass_folds'] = bool(row['folded_pct'] <= 100.0 * FOLD_TOL)
        out[r] = row
    return out, dict(d_fr=d_fr, folded=folded, cosv=cosv, d_rf=d_rf, fr_lab=fr_lab, t_lab=t_lab)


def quad_reference(Q, tgt_normals, tgt_labels):
    """per cage quad: the mean of its four targets' reference normals (normalised) and its region (the most common of
    its corners' labels)"""
    n = tgt_normals[Q].sum(1)
    n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    lab = []
    for q in Q:
        ls = [tgt_labels[v] for v in q]
        lab.append(max(sorted(set(ls)), key=ls.count))      # ties (2:2): the alphabetically first (see tri_labels)
    return n, np.array(lab, dtype=object)


def print_regional(rows, say, title):
    say(f'{title}')
    say(f'  {"region":10s} {"p95":>6s} {"p99.9":>7s} {"max":>7s} {"folded":>9s} {"bar":>5s}  verdict')
    for r, row in rows.items():
        bar = '' if row['bar'] is None else f'{row["bar"]:.1f}'
        v = ''
        if row['bar'] is not None:
            v = ('PASS' if row['pass_p95'] else 'FAIL p95') + (', folds ok' if row['pass_folds'] else ', FOLDS')
        say(f'  {r:10s} {row["p95"]:6.3f} {row["p999"]:7.3f} {row["max"]:7.3f} {row["folded_pct"]:8.2f}% {bar:>5s}  {v}')


# ============================================================================================ the cage's quality
def cage_quality(V, Q, mirror=None, mid=None, regions=None):
    """manifold, mirror, poles (valence != 4 off the boundary), angles and aspect (on the low: the cage at its limit)"""
    from ..mesh import QuadMesh
    qm = QuadMesh(V, Q)
    chk = qm.check()
    E, _ = qm.edges()
    val = np.bincount(E.ravel(), minlength=len(V))
    bnd = qm.edge_faces()[:, 1] < 0
    onb = np.zeros(len(V), bool)
    onb[E[bnd].ravel()] = True
    poles = np.nonzero((val != 4) & ~onb)[0]
    ang = np.zeros((len(Q), 4))
    for c in range(4):
        a, b, d = V[Q[:, c]], V[Q[:, (c + 1) % 4]], V[Q[:, (c - 1) % 4]]
        u, w = b - a, d - a
        ang[:, c] = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', u, w) /
                                                 (np.linalg.norm(u, axis=1) * np.linalg.norm(w, axis=1) + 1e-12), -1, 1)))
    e = np.stack([np.linalg.norm(V[Q[:, c]] - V[Q[:, (c + 1) % 4]], axis=1) for c in range(4)], 1)
    asp = (e[:, 0] + e[:, 2]) / np.maximum(e[:, 1] + e[:, 3], 1e-9)
    asp = np.maximum(asp, 1.0 / np.maximum(asp, 1e-9))
    out = dict(check=chk, vertices=int(len(V)), quads=int(len(Q)), poles=int(len(poles)),
               valence={int(k): int(v) for k, v in zip(*np.unique(val[~onb], return_counts=True))},
               angle_p1=float(np.percentile(ang.min(1), 1)), angle_min=float(ang.min()),
               aspect_p99=float(np.percentile(asp, 99)), aspect_max=float(asp.max()))
    if mirror is not None:
        out['mirror_err'] = float(np.abs(V[:, 0] + V[mirror, 0]).max() + np.abs(V[:, 1:] - V[mirror, 1:]).max())
    return out, poles, ang, asp


# ============================================================================================ the rings
def ring_gate(low, ids, density_px_mm, closed=True, poles=None, creases=None, collar_ids=None):
    """a ring on the LOW (the cage at its limit): K, planarity / mean radius, chord sag in texels, collar cleanliness"""
    P = low[ids]
    c = P.mean(0)
    U, s, Vt = np.linalg.svd(P - c)
    n = Vt[2]
    dev = np.abs((P - c) @ n)
    r = np.linalg.norm((P - c) - np.outer((P - c) @ n, n), axis=1)
    K = len(ids)
    sag = r.max() * (1.0 - np.cos(np.pi / K)) * density_px_mm
    out = dict(K=int(K), K_mod4=bool(K % 4 == 0), r_mean=float(r.mean()), r_max=float(r.max()),
               planarity=float(dev.max() / max(r.mean(), 1e-9)), planar_max_mm=float(dev.max()),
               sag_px=float(sag), normal=n.tolist(), centre=c.tolist())
    out['planar_ok'] = bool(out['planarity'] <= 0.02)
    if collar_ids is not None:
        cs = set(int(v) for v in collar_ids)
        out['collar_poles'] = int(len(cs & set(int(v) for v in (poles if poles is not None else []))))
        out['collar_creases'] = int(sum(1 for (a, b) in (creases or {}) if a in cs and b in cs))
    return out
