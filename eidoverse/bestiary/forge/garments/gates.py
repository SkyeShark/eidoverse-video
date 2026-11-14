"""THE GATES of the garments.

  rom(B, garments, mats)   NO BODY POINT THROUGH A GARMENT over the controller's clips: the engine's own joint matrices per
                           frame (the scene's 'gdump': bone world x inverse bind, mesh space), the body and every garment
                           posed by the same LBS three runs. Per garment, the body points it COVERS: on the T rest a ray
                           along the skin's normal meets it within 8 cm, 15 mm or more from its openings; that hit (its
                           triangle and barycentrics) is the point's OWN cloth. Each frame: the posed body point against
                           its posed cloth point, along the posed triangle's outward normal: > 0 = THROUGH (a nearest-point
                           test reads a hanging sleeve's inside as the torso's cloth). Counted for all covered points and
                           for the VISIBLE ones (a vertex with a drawn triangle under the hidden-face mask). The LAYER
                           pairs (the trousers under a top's hem) the same way.
  density(rec)             the texel density against the body's (3,430 px/m p50 at 4096)
"""
import numpy as np
import warp as wp

from . import meshops as mo
from .body import vertex_normals

BODY_PX_PER_M = 3430.0


def covered(P, Nrm, GV, GF, margin=0.015, maxd=0.08):
    """(ids of the covered points, their cloth triangle, barycentrics)"""
    from scipy.spatial import cKDTree
    from .outfit import _ray_hits
    hit, hp, face, bc = _ray_hits(GV, GF, P + Nrm * 0.0005, Nrm, maxd, full=True)
    loops = mo.boundary_loops(GF)
    if loops:
        b = np.concatenate([GV[l] for l in loops])
        d = cKDTree(b).query(hp)[0]
        hit &= d > margin
    idx = np.nonzero(hit)[0]
    # the covering triangle's normal must face AWAY from the covered point (along the ray): a two-sheet piece (the tie's
    # back sheet) faces the shirt; the sign per point is read on the rest geometry, from the ray, not from the depth
    tri = GF[face[idx]]
    n = np.cross(GV[tri[:, 1]] - GV[tri[:, 0]], GV[tri[:, 2]] - GV[tri[:, 0]])
    sgn = np.sign(np.einsum('ij,ij->i', n, Nrm[idx]))
    sgn[sgn == 0] = 1.0
    return idx, face[idx], bc[idx] * sgn[:, None]


def through(Pb, Pg, GF, face, bc):
    """bc carries the facing sign (covered()): |bc| the barycentrics"""
    sgn = np.sign(bc.sum(1))
    bc = bc * sgn[:, None]
    tri = GF[face]
    A, Bv, C = Pg[tri[:, 0]], Pg[tri[:, 1]], Pg[tri[:, 2]]
    hit = bc[:, 0:1] * A + bc[:, 1:2] * Bv + bc[:, 2:3] * C
    n = np.cross(Bv - A, C - A)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-20
    return np.einsum('ij,ij->i', Pb - hit, n) * sgn


def _visible(V, F, hidden_tris):
    vis = np.ones(len(V), bool)
    if hidden_tris is not None and len(hidden_tris):
        cnt = np.zeros(len(V), int)
        np.add.at(cnt, F[hidden_tris].ravel(), 1)
        tri_of = np.zeros(len(V), int)
        np.add.at(tri_of, F.ravel(), 1)
        vis = cnt < tri_of
    return vis


def _gmesh(g):
    if g['rec']['garment'] == 'shoes':
        return g['V'], g['F'], g['J4'], g['W4']
    return g['XT_low'], g['F_low'], g['J4_low'], g['W4_low']


def rom(B, garments, mats_frames, hidden_tris=None, tol=0.0, layers=(), log=print, times=None, layer_hidden=None):
    """mats_frames (frames, joints, 4, 4) in the skin's joint order. Returns a report dict"""
    wp.init()
    V, F = B.V, B.F
    Nv = vertex_normals(V, F)
    vis = _visible(V, F, hidden_tris)
    rep = {}
    pairs = [(None, g) for g in garments] + [(next(g for g in garments if g['rec']['garment'] == a),
                                               next(g for g in garments if g['rec']['garment'] == b)) for a, b in layers]
    for inner, g in pairs:
        GV, GF, J4, W4 = _gmesh(g)
        if inner is None:
            name = g['rec']['garment']
            SV, SJ, SW, svis = V, B.J4, B.W4, vis
            SN = Nv
        else:
            name = f'{inner["rec"]["garment"]}_under_{g["rec"]["garment"]}'
            SV, SF, SJ, SW = _gmesh(inner)
            SN = vertex_normals(SV, SF)
            svis = np.ones(len(SV), bool)
            lh = (layer_hidden or {}).get(inner['rec']['garment'])
            if lh is not None and len(lh):
                # the inner's game mesh faces the outer hides, carried to its low vertices by position
                from scipy.spatial import cKDTree
                GVg, GFg = inner['V'], inner['F']
                gvis = _visible(GVg, GFg, np.asarray(lh, int))
                d, j = cKDTree(GVg).query(SV)
                svis = gvis[j] | (d > 0.003)
        idx, face, bc = covered(SV, SN, GV, GF)
        n_all = n_vis = frames_bad = 0
        worst = -1.0
        depth = np.full(len(idx), -1.0)
        when = np.zeros(len(idx), int)
        for k, M in enumerate(mats_frames):
            Pb = B.lbs(mats=M, V=SV[idx], J4=SJ[idx], W4=SW[idx])
            Pg = B.lbs(mats=M, V=GV, J4=J4, W4=W4)
            sd = through(Pb, Pg, GF, face, bc)
            out = sd > tol
            n_all += int(out.sum())
            nv = int((out & svis[idx]).sum())
            n_vis += nv
            frames_bad += nv > 0
            up = sd > depth
            depth[up] = sd[up]
            when[up] = k
            worst = max(worst, float(sd.max()))
        bad = depth > tol
        dom = {}
        for i in np.nonzero(bad)[0]:
            j = B.jnames[SJ[idx[i]][np.argmax(SW[idx[i]])]]
            d = dom.setdefault(j, [0, 0.0, set()])
            d[0] += 1
            d[1] = max(d[1], depth[i] * 1000)
            d[2].add(float(times[when[i]]) if times is not None else int(when[i]))
        rep[name] = dict(covered=int(len(idx)), points_ever_through=int(bad.sum()),
                         visible_points_ever_through=int((bad & svis[idx]).sum()), through_point_frames=n_all,
                         visible_point_frames=n_vis, frames=len(mats_frames), frames_with_visible=frames_bad,
                         worst_mm=worst * 1000,
                         by_joint={j: dict(points=v[0], depth_mm=round(v[1], 1), t=sorted(v[2])[:10])
                                   for j, v in sorted(dom.items(), key=lambda x: -x[1][0])})
        log(f'[rom] {name}: {len(idx)} covered points x {len(mats_frames)} frames: {int(bad.sum())} ever through '
            f'({int((bad & svis[idx]).sum())} visible), point-frames {n_all} (visible {n_vis}, in {frames_bad} frames), '
            f'worst {worst * 1000:.1f} mm; {list(rep[name]["by_joint"].items())[:4]}')
    return rep


def load_joints(path, B):
    import json
    d = json.load(open(path))
    names = d['joints']
    order = [names.index(n) for n in B.jnames]
    M = np.asarray(d['mats_colmajor'], np.float64).reshape(len(d['mats_colmajor']), len(names), 4, 4).transpose(0, 1, 3, 2)
    return M[:, order], np.asarray(d['t'])
