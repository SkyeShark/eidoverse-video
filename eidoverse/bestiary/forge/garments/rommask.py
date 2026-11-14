"""THE ROM-REFINED CULL MASKS (B2b): the forge culls what each garment's pattern region covers (outfit.hidden_tris, the
layer mask); the controller's own clips then say what of that can still SHOW, and those faces are drawn again.

A culled face SHOWS in a frame when its outward ray (the posed face normal) escapes to the open (nothing drawn within
1 m: the body, the head, every garment as drawn) AND no garment lies right behind it (within 3 cm along the inward
ray: a culled trousers face poking through the tee leaves the tee in view, not a hole) AND it is not THROUGH a garment
(on the outer side of its nearest garment triangle: a culled face gone through is hidden, the cull at work). Up a short
sleeve in the wave,
under a hem that lifts in the crouch: those faces (and one ring of culled neighbours round them) go back into the drawn
index, and out of every garment's hidden list, so a runtime's wear / take-off arithmetic stays exact.

    rec = refine(glb_in, rom_paths, glb_out)
"""
import numpy as np
import warp as wp

from .offset import pose, load_rom, _query


@wp.kernel
def _k_ray(mesh: wp.uint64, O: wp.array(dtype=wp.vec3), D: wp.array(dtype=wp.vec3), rmax: float,
           hit: wp.array(dtype=int)):
    i = wp.tid()
    r = wp.mesh_query_ray(mesh, O[i], D[i], rmax)
    hit[i] = 0
    if r.result:
        hit[i] = 1


def _rays(V, F, O, D, rmax):
    m = wp.Mesh(points=wp.array(V.astype(np.float32), dtype=wp.vec3), indices=wp.array(F.astype(np.int32).ravel(), dtype=int))
    h = wp.zeros(len(O), int)
    wp.launch(_k_ray, len(O), [m.id, wp.array(O.astype(np.float32), dtype=wp.vec3),
                               wp.array(D.astype(np.float32), dtype=wp.vec3), float(rmax), h])
    return h.numpy() == 1


def _merge(Ps, meshes, names):
    Vs, Fs, o = [], [], 0
    for nm in names:
        Vs.append(Ps[nm])
        Fs.append(meshes[nm]['F'] + o)
        o += len(Ps[nm])
    return np.concatenate(Vs), np.concatenate(Fs)


def shows(meshes, inner, faces, M):
    """which of the inner mesh's faces (full-index triangles, not drawn) show in any frame of M; and the first time"""
    names = [n for n in meshes if n.startswith('garment_') or n in ('skin_BODY', 'skin_HEAD')]
    gnames = [n for n in names if n.startswith('garment_') and n != inner]
    out = np.zeros(len(faces), bool)
    first = np.full(len(faces), -1, int)
    for k, Mk in enumerate(M):
        Ps = {n: pose(meshes[n], Mk) for n in names}
        P = Ps[inner]
        n = np.cross(P[faces[:, 1]] - P[faces[:, 0]], P[faces[:, 2]] - P[faces[:, 0]])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-20
        c = P[faces].mean(1)
        Va, Fa = _merge(Ps, meshes, names)
        escaped = ~_rays(Va, Fa, c + n * 0.001, n, 1.0)
        if gnames:
            Vg, Fg = _merge(Ps, meshes, gnames)
            behind = _rays(Vg, Fg, c - n * 0.001, -n, 0.03)
            # a culled face gone THROUGH the cloth (on the outer side of its nearest garment triangle: a thigh in the
            # crouch's collapse) is the cull doing its work, not a hole: it stays culled (the first dry fit drew such
            # faces again and the trousers swelled to the 30 mm cap over them)
            sd, di, fc, rh = _query(Vg, Fg, c, n)
            through = (sd > 0) & (di < 0.04) & (fc >= 0)
        else:
            behind = np.zeros(len(c), bool)
            through = np.zeros(len(c), bool)
        s = escaped & ~behind & ~through
        first[s & ~out] = k
        out |= s
    return out, first


def _openings(meshes, full_of):
    """sample points along every garment's openings (T rest; the garment's full mesh welded by position, so a UV seam
    is not an edge of it)"""
    from scipy.spatial import cKDTree
    from . import meshops as mo
    S = []
    for nm, m in meshes.items():
        if not nm.startswith('garment_') or nm == 'garment_tie':
            continue
        F = full_of.get(nm, m['F'])
        key = np.round(m['V'] * 1e5).astype(np.int64)
        u, rep, wid = np.unique(key, axis=0, return_index=True, return_inverse=True)
        Fw = wid.ravel()[F]
        for lp in mo.boundary_loops(Fw):
            P = m['V'][rep[lp]]
            Q = np.roll(P, -1, axis=0)
            for p, q in zip(P, Q):
                k = max(1, int(np.ceil(np.linalg.norm(q - p) / 0.004)))
                S.append(p + (q - p) * (np.arange(k)[:, None] / k))
    return cKDTree(np.concatenate(S)) if S else None


def refine(path_in, rom_paths, path_out, log=print, every=1, ring=1, reach=0.10):
    """reach: only a culled face within `reach` (T rest) of some garment's opening may be drawn again (what shows
    through an opening is near it; a deep face 'showing' is a crease's collapse, which the cull hides: the first dry
    fit drew such hip-crease faces again and they went through the trousers in the crouch)"""
    from .export import GlbEdit
    from .. import gltf
    g = gltf.read(path_in)
    j, acc = g['json'], g['accessor']
    bx = j['extras']['bestiary']
    skin_j = [j['nodes'][k]['name'] for k in j['skins'][0]['joints']]
    M = np.concatenate([load_rom(p, skin_j)[0][::every] for p in rom_paths])
    meshes = {}
    for m in j['meshes']:
        p = m['primitives'][0]
        a = p['attributes']
        if 'JOINTS_0' not in a:
            continue
        meshes[m['name']] = dict(V=acc(a['POSITION']).astype(np.float64), F=acc(p['indices']).reshape(-1, 3).astype(np.int64),
                                 J=acc(a['JOINTS_0']).astype(np.int64), W=acc(a['WEIGHTS_0']).astype(np.float64),
                                 N=acc(a['NORMAL']).astype(np.float64), off=None)
    full_of = {f'garment_{r["garment"]}': acc(r['index_full']).reshape(-1, 3).astype(np.int64)
               for r in bx['garments'] if 'index_full' in r}
    T_open = _openings(meshes, full_of)
    # each inner mesh: (its full index, the garments' hidden lists over it)
    plans = []
    if 'body_index_full' in bx:
        plans.append(('skin_BODY', acc(bx['body_index_full']).reshape(-1, 3).astype(np.int64), 'hidden_tris', None))
    if 'head_index_full' in bx:
        plans.append(('skin_HEAD', acc(bx['head_index_full']).reshape(-1, 3).astype(np.int64), 'hidden_tris_head', None))
    for r in bx['garments']:
        if 'index_full' in r:
            plans.append((f'garment_{r["garment"]}', acc(r['index_full']).reshape(-1, 3).astype(np.int64),
                          'layer_hidden_tris', r['garment']))
    rec = {}
    new_index = {}
    for inner, full, key, own in plans:
        recs = [r for r in bx['garments'] if (own is None or r['garment'] == own) and key in r]
        hidden = sorted(set(int(t) for r in recs for t in r[key]))
        if not hidden:
            continue
        hid = np.array(hidden, np.int64)
        near = np.ones(len(hid), bool)
        if T_open is not None:
            near = T_open.query(meshes[inner]['V'][full[hid]].mean(1))[0] < reach
        show = np.zeros(len(hid), bool)
        first = np.full(len(hid), -1, int)
        if near.any():
            show[near], first[near] = shows(meshes, inner, full[hid[near]], M)
        back = set(hid[show].tolist())
        if back and ring:
            # one ring of culled neighbours round each face that shows (no single-face jaggies at the mask's edge)
            vs = set(full[hid[show]].ravel().tolist())
            for t in hid:
                if any(v in vs for v in full[t]):
                    back.add(int(t))
        for r in recs:
            r[key] = [int(t) for t in r[key] if int(t) not in back]
        hidden2 = sorted(set(hidden) - back)
        keep = np.ones(len(full), bool)
        if hidden2:
            keep[np.array(hidden2, np.int64)] = False
        new_index[inner] = full[keep]
        rec[inner] = dict(culled=len(hidden), show=int(show.sum()), drawn_again=len(back), culled_after=len(hidden2),
                          first_frames=sorted(set(first[show].tolist()))[:12])
        log(f'[rommask] {inner}: {int(show.sum())} of {len(hidden)} culled faces show over {len(M)} frames; '
            f'{len(back)} drawn again (with one ring), {len(hidden2)} stay culled')
    E = GlbEdit(path_in)
    for m in E.j['meshes']:
        if m['name'] in new_index:
            m['primitives'][0]['indices'] = E.accessor(np.asarray(new_index[m['name']], np.uint32).reshape(-1), 'SCALAR', 34963)
    eb = E.j['extras']['bestiary']
    eb['garments'] = bx['garments']
    eb['rom_mask'] = dict(rom=[str(p) for p in rom_paths], frames=int(len(M)), refined=rec)
    n = E.save(path_out)
    return rec, n
