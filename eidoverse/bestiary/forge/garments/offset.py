"""THE RUNTIME CLOTH OFFSET (B2b, the lead's call 11-08): each garment vertex carries an amount (metres, the glb's
_CLOTH_OFFSET attribute) by which the engine pushes it out along its normal (garment_material.js's positionNode).
THE ORDER IS THE ENGINE'S: three r184 runs a material's positionNode BEFORE the bones' blend (the compiled WGSL, the
groom builder's dump work/bestiary/coat/g5/g5_groom/scratch/shader/all_1.wgsl: positionLocal = the attribute, then the
node, then the skin), so the push is along the BIND normal and the bones carry it: posed = A (V + N off). In a crease
the blended matrix shortens it by |A3 N| (<= 1), and the fit below measures exactly that, so what it fits is what the
engine draws. (A post-skin push would only ever be longer: this gate is the conservative one.)

The amounts are FITTED, not painted: over the controller's own clips (the engine's joint matrices, b2walk 'gdump': walk,
wave, crouch) every drawn inner point (the culled body, the head, the drawn trousers under a top, the shirt under the tie)
is tested the strict gate's way (outer side of its nearest posed cloth triangle within 3 cm and no cloth along its normal
within 8 cm); each miss asks the covering triangle's three vertices for (depth + `clear`, 1 mm: the margin); the asks
are dilated over the cloth (a smooth swell, never a
spike: rings of decay) and added; repeated until no point is through. Where the fit lands (the hip crease, the
waistband, the hem over the seat, the collar) is reported, so the map is seen, not assumed.

    off, rep = fit(outer, inners, mats_frames)
outer / inners: dict(V, F, J, W, N[, off]) in the T rest (the glb's arrays); mats_frames (frames, joints, 4, 4).
"""
import numpy as np
import warp as wp

from . import meshops as mo


@wp.kernel
def _k_q(mesh: wp.uint64, P: wp.array(dtype=wp.vec3), N: wp.array(dtype=wp.vec3), dmax: float, rmax: float,
         sd: wp.array(dtype=float), dist: wp.array(dtype=float), face: wp.array(dtype=int), rayhit: wp.array(dtype=int)):
    i = wp.tid()
    p = P[i]
    q = wp.mesh_query_point_no_sign(mesh, p, dmax)
    face[i] = -1
    if q.result:
        c = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        m = wp.mesh_get(mesh)
        a = m.points[m.indices[q.face * 3 + 0]]
        b = m.points[m.indices[q.face * 3 + 1]]
        cc = m.points[m.indices[q.face * 3 + 2]]
        n = wp.normalize(wp.cross(b - a, cc - a))
        sd[i] = wp.dot(p - c, n)
        dist[i] = wp.length(p - c)
        face[i] = q.face
    else:
        sd[i] = -1.0
        dist[i] = 1.0
    r = wp.mesh_query_ray(mesh, p - N[i] * 0.0005, N[i], rmax)
    rayhit[i] = 0
    if r.result:
        rayhit[i] = 1


def vnormals(V, F):
    n = np.zeros_like(V)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    for k in range(3):
        np.add.at(n, F[:, k], fn)
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-20)


def pose(m, Mk, off=None):
    """three r184's vertex stage: the offset along the BIND normal first (the positionNode), then the bones' blend"""
    A = np.einsum('vk,vkij->vij', m['W'], Mk[m['J']])
    off = m.get('off') if off is None else off
    V = m['V'] if off is None else m['V'] + m['N'] * off[:, None]
    return np.einsum('vij,vj->vi', A[:, :3, :3], V) + A[:, :3, 3]


def _query(Po, Fo, Pi, Ni):
    mesh = wp.Mesh(points=wp.array(Po.astype(np.float32), dtype=wp.vec3),
                   indices=wp.array(Fo.astype(np.int32).ravel(), dtype=int))
    n = len(Pi)
    sd, di, fc, rh = wp.zeros(n, float), wp.zeros(n, float), wp.zeros(n, int), wp.zeros(n, int)
    wp.launch(_k_q, n, [mesh.id, wp.array(Pi.astype(np.float32), dtype=wp.vec3),
                        wp.array(Ni.astype(np.float32), dtype=wp.vec3), 0.04, 0.08, sd, di, fc, rh])
    return sd.numpy(), di.numpy(), fc.numpy(), rh.numpy()


def candidates(outer, inner, off):
    """the inner's drawn points under the cloth at rest (the strict gate's set)"""
    I = np.broadcast_to(np.eye(4), (int(max(inner['J'].max(), outer['J'].max())) + 1, 4, 4)).copy()
    drawn = np.unique(inner['F'])
    Pi = pose(inner, I)
    Ni = vnormals(Pi, inner['F'])
    sd, di, fc, rh = _query(pose(outer, I, off), outer['F'], Pi[drawn], Ni[drawn])
    return drawn[(sd < 0) & (di < 0.04) & (rh == 1)]


def fit(outer, inners, mats_frames, clear=0.001, cap=0.008, rings=4, decay=0.75, iters=4, log=print, name=''):
    # (B2b) cap 8 mm, 4 passes: the offset is a MARGIN. In a collapsed crease (the hip in the crouch) a bind-space push
    # turns into the opposite limb, and the first dry fit's through-points GREW with the offset to its 30 mm cap, an
    # inner layer's swell then cascading into the layer over it (the tee: 3,288 -> 8,656 point-frames); creases are
    # the culls' and the weights' to fix
    nV = len(outer['V'])
    off = np.zeros(nV) if outer.get('off') is None else outer['off'].copy()
    A = mo.adjacency(outer['F'], nV)
    A.data[:] = 1.0
    deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
    L = mo.laplacian(outer['V'], outer['F'])
    cands = [candidates(outer, m, off) for m in inners]
    hist = []
    for it in range(iters):
        need = np.zeros(nV)
        n_bad = n_near = 0
        for M in mats_frames:
            Po = pose(outer, M, off)
            for m, ci in zip(inners, cands):
                if not len(ci):
                    continue
                Pi = pose(m, M)
                Ni = vnormals(Pi, m['F'])[ci]
                sd, di, fc, rh = _query(Po, outer['F'], Pi[ci], Ni)
                bad = (sd > 0) & (di < 0.03) & (rh == 0)
                # (B2b) only a point THROUGH asks, for its depth + `clear` (round 2's first fit also pushed every point
                # within 2 mm on either side: the ankle above the shoe's collar is outside it by right, and the shoes
                # swelled 14 mm in three passes)
                near = np.zeros_like(bad)
                n_bad += int(bad.sum())
                n_near += int(near.sum())
                ask = bad
                if not ask.any():
                    continue
                amt = sd[ask] + clear
                tri = outer['F'][fc[ask]]
                for c in range(3):
                    np.maximum.at(need, tri[:, c], amt)
        hist.append((n_bad, n_near, float(off.max())))
        log(f'[offset] {name} it {it}: through point-frames {n_bad}, within the clearance {n_near}; '
            f'offset max {off.max() * 1000:.1f} mm, >1 mm on {(off > 0.001).sum()} of {nV} vertices')
        if n_bad == 0 and n_near == 0:
            break
        # the swell: max-dilation with decay over `rings` rings, then two smoothing steps that never lower the ask
        s = need.copy()
        for _ in range(rings):
            nb = np.zeros(nV)
            Ac = A.tocoo()
            np.maximum.at(nb, Ac.row, s[Ac.col])
            s = np.maximum(s, decay * nb)
        for _ in range(2):
            s = np.maximum(s, s + 0.5 * (L @ s))
        off = np.minimum(off + s, cap)
    # the final field smoothed a little (no tent on the surface: a crease of the offset draws as a fold)
    for _ in range(3):
        off = np.maximum(off, off + 0.5 * (L @ off))
    off = np.minimum(off, cap)
    rep = dict(iterations=len(hist), history=hist, max_mm=float(off.max() * 1000),
               p95_mm=float(np.percentile(off, 95) * 1000), verts_gt_1mm=int((off > 0.001).sum()),
               verts_gt_5mm=int((off > 0.005).sum()), verts=nV, candidates=[int(len(c)) for c in cands])
    return off, rep


ORDER = ['garment_shoes', 'garment_trousers', 'garment_tee', 'garment_shirt_ss', 'garment_shirt_ls', 'garment_tie']


def load_rom(jpath, skin_jnames):
    """the scene's gdump (the engine's joint matrices per frame) in the glb skin's joint order"""
    import json
    d = json.load(open(jpath))
    order = [d['joints'].index(n) for n in skin_jnames]
    M = np.asarray(d['mats_colmajor'], np.float64).reshape(len(d['t']), len(d['joints']), 4, 4).transpose(0, 1, 3, 2)
    return M[:, order], np.asarray(d['t'])


def apply_to_glb(path_in, rom_paths, path_out, log=print, every=1):
    """the clothed glb (outfit.write_outfit's) -> the same with every garment's _CLOTH_OFFSET fitted, inner to outer:
    the shoes and trousers against the drawn body; a top against the body, the head and the drawn trousers WITH their
    offset; the tie against the top with its offset. The fit and its map are recorded in extras.bestiary.cloth_offset."""
    from .export import GlbEdit
    from .. import gltf
    g = gltf.read(path_in)
    j, acc = g['json'], g['accessor']
    skin_j = [j['nodes'][k]['name'] for k in j['skins'][0]['joints']]
    Ms = []
    for p in rom_paths:
        M, _ = load_rom(p, skin_j)
        Ms.append(M[::every])
    Mall = np.concatenate(Ms)
    meshes = {}
    for m in j['meshes']:
        p = m['primitives'][0]
        a = p['attributes']
        if 'JOINTS_0' not in a:
            continue
        meshes[m['name']] = dict(V=acc(a['POSITION']).astype(np.float64),
                                 F=acc(p['indices']).reshape(-1, 3).astype(np.int64),
                                 J=acc(a['JOINTS_0']).astype(np.int64), W=acc(a['WEIGHTS_0']).astype(np.float64),
                                 N=acc(a['NORMAL']).astype(np.float64), off=None)
    body = [meshes[n] for n in ('skin_BODY', 'skin_HEAD') if n in meshes]
    tops = [n for n in ORDER[2:5] if n in meshes]
    recs = {}
    for name in [n for n in ORDER if n in meshes]:
        cap = 0.008
        if name == 'garment_tie':
            inners = [meshes[t] for t in tops]
            # (B2b) the tie INHERITS its shirt's offset at the point it lies on (the shirt's 8 mm swell over the
            # trousers at the belt went through the blade's tip in 378 of 390 frames, M), then fits its own margin
            if tops and meshes[tops[0]]['off'] is not None:
                sh = meshes[tops[0]]
                q, t, bc, _ = mo.closest_on_mesh(sh['V'], sh['F'], meshes[name]['V'])
                meshes[name]['off'] = np.einsum('nk,nk->n', bc, sh['off'][sh['F'][t]])
                cap = float(meshes[name]['off'].max()) + 0.008
        elif name in tops:
            inners = body + ([meshes['garment_trousers']] if 'garment_trousers' in meshes else [])
        else:
            inners = body[:1]
        off, rep = fit(meshes[name], inners, Mall, log=log, name=name, cap=cap)
        meshes[name]['off'] = off
        # where the swell sits: the dominant joints of the vertices over 3 mm
        big = off > 0.003
        dom = {}
        if big.any():
            Jd = meshes[name]['J'][big, np.argmax(meshes[name]['W'][big], axis=1)]
            for jj, c in zip(*np.unique(Jd, return_counts=True)):
                dom[skin_j[int(jj)]] = int(c)
        rep['over_3mm_by_joint'] = dict(sorted(dom.items(), key=lambda x: -x[1])[:8])
        recs[name] = rep
        log(f'[offset] {name}: max {rep["max_mm"]:.1f} mm, p95 {rep["p95_mm"]:.2f} mm, >5 mm on {rep["verts_gt_5mm"]} '
            f'verts; {rep["over_3mm_by_joint"]}')
    E = GlbEdit(path_in)
    for m in E.j['meshes']:
        if m['name'] in meshes and meshes[m['name']]['off'] is not None:
            m['primitives'][0]['attributes']['_CLOTH_OFFSET'] = E.accessor(
                meshes[m['name']]['off'].astype(np.float32), 'SCALAR', 34962)
    E.j.setdefault('extras', {}).setdefault('bestiary', {})['cloth_offset'] = dict(
        attribute='_CLOTH_OFFSET (metres, along the skinned normal after skinning)', rom=[str(p) for p in rom_paths],
        frames=int(len(Mall)), fits=recs)
    n = E.save(path_out)
    return recs, n
