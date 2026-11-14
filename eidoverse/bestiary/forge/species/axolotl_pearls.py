"""AX13 (11-02, the lead's call; work/bestiary/PLAN.md "AXOLOTL AX10b DONE"): THE AXOLOTL'S PEARLS AS SEPARATE GLASS
DROPLETS, in place of AX10's pearls in the skin. p14 / p15 show round clear droplets with a glint at each end of the
mouth's U, two a side, touching, lying OVER the lower lip's pale band with their tops tucked under the upper lip's
margin, the lip's grey and its spots seen through them. AX10 built them as domes of the clay's lower lip; the low (the
AX4 cage at level 0) gave each a ~4 x 4 control peg, and the pegs' outline, a light lump hanging into a dark slit,
read as teeth (AX10b found a K 64 ring cannot refine locally). So the clay's beads come off the skin (heads/caudate.py
pearls_are_parts: the lower lip runs smooth there and the bake shows the lip under the droplets) and the droplets are
their own part, built here on the FITTED LOW, the eyes' way:

  * ONE TEMPLATE: a cube-sphere (six n x n grids projected onto the unit sphere; n = SPEC ax13 drop_n), welded, its
    UVs ONE SHELL (the cube's cross net laid in 0..1, split along the net's cut edges only), the analytic normals;
  * FOUR INSTANCES (two a side, the right the exact mirror of the left, its faces reversed): each the template under
    an ellipsoid frame [e1 a, e2 b, e3 c] (a along the lip line, b down the lip, c out of the skin: SPEC ax13 drop_r;
    a capped so the pair touch but never merge, drop_touch), placed on the low's lower lip: at drop_x HW off the
    midline on the lip loop's lower run, walked down the lower lip's skin so its top sits drop_top under the lower lip's
    row (just under the upper lip's margin), out along the skin's normal by c (1 - drop_embed) (a contact: it rests on
    the band), then lowered step by step while any of its vertices lies inside the UPPER lip (the welded animal's
    winding number, the nearest skin above the margin line): it never passes through the upper lip;
  * their CLARITY is the material's (tests/ax07_skin.py writes 'axolotl_pearl': an opacity FACTOR, transmission, ior,
    a clear coat, a low roughness; never a texture alpha, which the engine's image decode divides), skinned RIGID on the
    lower lip's weights at each droplet's contact point (species/axolotl_rig.pearl_weights).

Units: life mm in the plan frame of the bind (x lateral, + the left; y up; z forward), as families/sprawl_body.
"""
import numpy as np
import warp as wp

MIRROR = np.array([-1.0, 1.0, 1.0])


@wp.kernel
def k_inside(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, inside: wp.array(dtype=wp.int32),
             near: wp.array(dtype=wp.vec3), dist: wp.array(dtype=float)):
    """each point: inside the closed mesh (its winding number), its closest point and the distance to it"""
    i = wp.tid()
    q = wp.mesh_query_point_sign_winding_number(mesh, pts[i], maxd, 2.0, 0.5)
    inside[i] = 0
    if q.result:
        p = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        near[i] = p
        dist[i] = wp.length(p - pts[i])
        if q.sign < 0.0:
            inside[i] = 1


class Inside:
    """the closed welded animal for inside / closest-point queries (life mm, Warp on the CPU)"""

    def __init__(self, V, F, device='cpu'):
        self.dev = device
        self.V = np.asarray(V, np.float64)
        self.mesh = wp.Mesh(points=wp.array(self.V.astype(np.float32), dtype=wp.vec3, device=device),
                            indices=wp.array(np.asarray(F).ravel().astype(np.int32), dtype=wp.int32, device=device))

    def query(self, P, maxd=50.0):
        P = np.atleast_2d(np.asarray(P, np.float64))
        n = len(P)
        ins = wp.zeros(n, dtype=wp.int32, device=self.dev)
        nr = wp.zeros(n, dtype=wp.vec3, device=self.dev)
        ds = wp.zeros(n, dtype=float, device=self.dev)
        wp.launch(k_inside, dim=n, inputs=[self.mesh.id, wp.array(P.astype(np.float32), dtype=wp.vec3, device=self.dev),
                                           float(maxd), ins, nr, ds], device=self.dev)
        return ins.numpy().astype(bool), nr.numpy().astype(np.float64), ds.numpy().astype(np.float64)


def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-30)


# ============================================================================================ the template
def template(n=8):
    """the unit cube-sphere: dict(V (m, 3) on the unit sphere, F (k, 3) outward-wound triangles, Q quads, UV (m, 2) one
    shell in 0..1 (v up), N = V, orig (m,) the welded vertex of each UV vertex, n_weld). The six faces' grids in the
    cube's cross net:
            [+y]
       [-x] [+z] [+x] [-z]
            [-y]
    each face a cell of a 4 x 3 grid of cells (1/4 of u by 1/3 of v), the cells ABUTTING where the faces meet in the net
    (the front with its four neighbours, +x with -z: their shared cube edges run the same way in both grids), so a
    vertex on such an edge is one UV vertex; the net's cut edges stay split; the whole net in 0.01 .. 0.99. The grid
    at EQUAL ANGLES (t = tan of an even step over +-45 deg): 4 n even segments round every great circle through the
    faces' middles (equal steps in t crowd the cube's edges: 14 deg a segment at a face's middle against 8 at its edge)"""
    t = np.tan(np.linspace(-0.25 * np.pi, 0.25 * np.pi, n + 1))
    # (centre, a, b, net cell (col, row)): the face's grid point = c + a t_i + b t_j; its UV = (cell + (i, j) / n) / (4, 3)
    faces = [((0, 0, 1.0), (1.0, 0, 0), (0, 1.0, 0), (1, 1)),           # +z front
             ((1.0, 0, 0), (0, 0, -1.0), (0, 1.0, 0), (2, 1)),          # +x right of it
             ((0, 0, -1.0), (-1.0, 0, 0), (0, 1.0, 0), (3, 1)),         # -z
             ((-1.0, 0, 0), (0, 0, 1.0), (0, 1.0, 0), (0, 1)),          # -x left of the front
             ((0, 1.0, 0), (1.0, 0, 0), (0, 0, -1.0), (1, 2)),          # +y above the front
             ((0, -1.0, 0), (1.0, 0, 0), (0, 0, 1.0), (1, 0))]          # -y below the front
    P, UV, Qs = [], [], []
    for c0, a, b, (col, row) in faces:
        c0, a, b = np.array(c0), np.array(a), np.array(b)
        base = len(P)
        for j in range(n + 1):
            for i in range(n + 1):
                p = c0 + a * t[i] + b * t[j]
                P.append(p / np.linalg.norm(p))
                UV.append((0.01 + 0.98 * (col + i / n) / 4.0, 0.01 + 0.98 * (row + j / n) / 3.0))
        for j in range(n):
            for i in range(n):
                k = base + j * (n + 1) + i
                Qs.append([k, k + 1, k + n + 2, k + n + 1])
    P, UV, Qs = np.array(P), np.array(UV), np.array(Qs)
    # the welded sphere (by position) and the UV vertices (by position AND uv: the net's joined edges weld, its cut
    # edges stay split)
    _, widx, winv = np.unique(np.round(P * 1e6).astype(np.int64), axis=0, return_index=True, return_inverse=True)
    winv = winv.reshape(-1)
    kk = np.column_stack([np.round(P * 1e6), np.round(UV * 1e7)]).astype(np.int64)
    _, uidx, uinv = np.unique(kk, axis=0, return_index=True, return_inverse=True)
    uinv = uinv.reshape(-1)
    Vo, UVo = P[uidx], UV[uidx]
    out_orig = winv[uidx]
    Qo = uinv[Qs]
    F = np.concatenate([Qo[:, [0, 1, 2]], Qo[:, [0, 2, 3]]])
    # outward winding: the cube faces' (a, b) frames are right-handed with c (a x b = c), so (k, k+1, k+n+2) is CCW
    # seen from outside
    fn = np.cross(Vo[F[:, 1]] - Vo[F[:, 0]], Vo[F[:, 2]] - Vo[F[:, 0]])
    assert (np.einsum('ij,ij->i', fn, Vo[F].mean(1)) > 0).all(), 'the template is not wound outward'
    return dict(V=Vo, F=F, Q=Qo, UV=UVo, N=Vo.copy(), orig=np.asarray(out_orig), n_weld=len(widx), n=n)


# ============================================================================================ measures
def zigzag(P, thr=0.03):
    """a saw edge along a polyline P (k, 3) in its own order (life mm): each interior point's offset from its two
    neighbours' midpoint, across the chord (r_k); a ZIG is two successive turns of r against each other (r_k . r_k+1 < 0
    and r_k+1 . r_k+2 < 0), each over thr mm (one turn is an inflection, a curve's own; a saw alternates). Returns (zigs,
    the largest alternating amplitude in mm)"""
    P = np.asarray(P, np.float64)
    if len(P) < 5:
        return 0, 0.0
    ch = unit(P[2:] - P[:-2])
    r = P[1:-1] - 0.5 * (P[:-2] + P[2:])
    r -= ch * np.einsum('ij,ij->i', r, ch)[:, None]
    nr = np.linalg.norm(r, axis=1)
    dots = np.einsum('ij,ij->i', r[:-1], r[1:])
    turn = (dots < 0) & (np.minimum(nr[:-1], nr[1:]) > thr)
    zig = turn[:-1] & turn[1:]
    amp = float(np.max(np.minimum(nr[:-2], np.minimum(nr[1:-1], nr[2:]))[zig])) if zig.any() else 0.0
    return int(zig.sum()), amp


def lip_runs(V, loop):
    """the lip loop (families/sprawl_body.mouth: the upper run first, from the left corner) split into its runs, each
    from the midline to the LEFT corner, as (upper, lower) id arrays, paired (upper k with lower K - 1 - k)"""
    loop = np.asarray(loop)
    K = len(loop)
    up = loop[:K // 2]
    lo = loop[K // 2:][::-1]
    if V[up, 1].mean() < V[lo, 1].mean():
        up, lo = lo, up
    left = V[up, 0] >= -1e-9
    up, lo = up[left], lo[left]
    # (along the run from the midline: the run as stored goes corner -> midline on the left)
    if np.abs(V[up[0], 0]) > np.abs(V[up[-1], 0]):
        up, lo = up[::-1], lo[::-1]
    return up, lo


def _at_x(P, x):
    """the polyline P (from the midline outward) at |x| = x: (point, its index segment, the unit tangent outward)"""
    ax = np.abs(P[:, 0])
    k = int(np.clip(np.searchsorted(ax, x) - 1, 0, len(P) - 2))
    while k < len(P) - 2 and ax[k + 1] < x:
        k += 1
    t = (x - ax[k]) / max(ax[k + 1] - ax[k], 1e-12)
    p = P[k] + (P[k + 1] - P[k]) * np.clip(t, 0.0, 1.0)
    return p, k, unit(P[k + 1] - P[k])


# ============================================================================================ the placement
def place(spec, V, Q, loop, animal_V, animal_F, log=print):
    """the four droplets on the fitted low (module docstring). V / Q: the body cage (life mm); loop: its lip loop;
    animal_V / animal_F: the welded closed animal (life mm, triangles) for the inside tests. Returns dict(tpl, frames
    (4, 3, 3) the ellipsoid frames' columns, origins (4, 3), side (4,), contact (4, 3) each droplet's contact point on
    the lower lip, V (all four instances' vertices, life mm), F, UV, N, inst (per vertex), report)"""
    a13 = spec['ax13']
    HW = float(spec['a1']['HW'])
    a0, b0, c0 = (float(x) for x in a13['drop_r'])
    tpl = template(int(a13['drop_n']))
    wp.init()
    query = Inside(animal_V, animal_F).query

    # the low's vertex normals (the body cage's quads, the bag left out so the lips' normals face out)
    Fq = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    fn = np.cross(V[Fq[:, 1]] - V[Fq[:, 0]], V[Fq[:, 2]] - V[Fq[:, 0]])
    VN = np.zeros_like(V)
    for k in range(3):
        np.add.at(VN, Fq[:, k], fn)
    VN = unit(VN)
    up, lo = lip_runs(V, loop)
    Pu, Pl = V[up], V[lo]

    def surf(p):
        """the low's closest point and its (interpolated vertex) normal"""
        ins, nr, ds = query(p[None, :])
        k = np.argsort(np.linalg.norm(V - nr[0], axis=1))[:6]
        w = 1.0 / np.maximum(np.linalg.norm(V[k] - nr[0], axis=1), 1e-6)
        return nr[0], unit((VN[k] * w[:, None]).sum(0))

    def margin_y(x):
        return float(np.interp(abs(x), np.abs(Pu[:, 0]), Pu[:, 1]))

    def slit_y(x):
        """the slit's middle height at |x|: a skin point above it is the UPPER lip's (the lower lip, lifted to meet the
        margin under the droplets, comes within 0.05 mm of the margin's height, so the margin alone misread it)"""
        return 0.5 * (margin_y(x) + float(np.interp(abs(x), np.abs(Pl[:, 0]), Pl[:, 1])))

    def upper_of(ins, nr):
        return ins & (nr[:, 1] > np.array([slit_y(x) for x in nr[:, 0]]))

    def seat(xq, a, extra=0.0):
        """a droplet started at |x| = xq on the lower lip's row: walked down the lower lip's skin so its top sits
        drop_top (+ extra) under the row, out along the skin's normal by c (1 - embed): (centre, frame, the skin
        point). Re-seated with a longer walk while it touches the upper lip: it slides down the lip's front, seated"""
        q, _, t = _at_x(Pl, xq)
        d = unit(np.cross(surf(q)[1], t))
        if d[1] > 0:
            d = -d
        dist_ = b0 + float(a13['drop_top']) + extra
        p = q.copy()
        nseg = 6
        for _ in range(nseg):
            n_p = surf(p)[1]
            dd = unit(d - n_p * (d @ n_p))
            p, _ = surf(p + dd * dist_ / nseg)
        ps, ns = surf(p)
        e3 = ns
        e1 = unit(t - e3 * (t @ e3))
        e2 = np.cross(e3, e1)
        if e2[1] > 0:                      # e2 down the lip, the frame right-handed
            e1 = -e1
            e2 = np.cross(e3, e1)
        c = ps + e3 * c0 * (1.0 - float(a13['drop_embed']))
        return c, np.column_stack([e1 * a, e2 * b0, e3 * c0]), ps
    # each droplet's start moved along the line until its CENTRE lands at drop_x HW off the midline (the walk down
    # the lip and out along its normal carry it ~0.6 mm outward); the along-line semi-axis then capped so the pair
    # touch (drop_touch of half their distance), never past drop_r's
    xs = [float(x) * HW for x in a13['drop_x']]
    starts = list(xs)
    for _ in range(4):
        cs = [seat(xq, a0)[0] for xq in starts]
        starts = [xq - (abs(c_[0]) - xd) for xq, c_, xd in zip(starts, cs, xs)]
    cs = [seat(xq, a0)[0] for xq in starts]
    a = min(a0, float(a13['drop_touch']) * 0.5 * float(np.linalg.norm(cs[1] - cs[0])))
    out = []
    rep = []
    for j, xq in enumerate(starts):
        c, Mf, ps = seat(xq, a)
        lowered = 0.0
        for it in range(40):
            P = c + tpl['V'] @ Mf.T
            ins, nr, ds = query(P)
            upper = upper_of(ins, nr)
            if not upper.any():
                break
            # (slid down the lip's front by the deepest touch, re-seated: moved along the frame's own e2 it left the
            # skin where the lower lip turns forward at the snout, floating with its top over the margin)
            lowered += max(0.03, float(ds[upper].max()) + 0.02)
            c, Mf, ps = seat(xq, a, lowered)
        e2 = Mf[:, 1] / b0
        P = c + tpl['V'] @ Mf.T
        ins, nr, ds = query(P)
        upper = upper_of(ins, nr)
        lower = ins & ~upper
        contact = float(ds[lower].max()) if lower.any() else 0.0
        # the contact point: the droplet's point deepest in the lower lip, carried back to the skin (the rig's anchor)
        cp = nr[np.argmax(np.where(lower, ds, -1.0))] if lower.any() else surf(c - Mf[:, 2])[0]
        out.append(dict(origin=c, frame=Mf, contact=cp, contact_depth=contact, upper_in=int(upper.sum()),
                        lowered=lowered, top_under_margin=float(margin_y(c[0]) - (c - e2 * b0)[1])))
        rep.append(f'droplet {j} at x {c[0]:.2f} mm ({abs(c[0]) / HW:.3f} HW): a / b / c {a:.2f} / {b0:.2f} / {c0:.2f} '
                   f'mm, sunk {contact:.2f} mm into the lower lip ({contact / c0:.2f} of c), {int(upper.sum())} vertices '
                   f'in the upper lip after lowering it {lowered:.2f} mm; its top {out[-1]["top_under_margin"]:.2f} mm '
                   f'under the margin')
    # both sides: the right the mirror (frame's det < 0: its faces reversed)
    inst = []
    for side in ('L', 'R'):
        for j, o in enumerate(out):
            if side == 'L':
                inst.append(dict(side='L', j=j, origin=o['origin'], frame=o['frame'], contact=o['contact']))
            else:
                inst.append(dict(side='R', j=j, origin=o['origin'] * MIRROR, frame=np.diag(MIRROR) @ o['frame'],
                                 contact=o['contact'] * MIRROR))
    Vs, Fs, UVs, Ns, IN = [], [], [], [], []
    off = 0
    for k, it in enumerate(inst):
        Mf = it['frame']
        Pv = it['origin'] + tpl['V'] @ Mf.T
        Nv = unit(tpl['V'] @ np.linalg.inv(Mf))                         # (M^-T u, as rows)
        Fk = tpl['F'] if np.linalg.det(Mf) > 0 else tpl['F'][:, ::-1]
        Vs.append(Pv)
        Ns.append(Nv)
        UVs.append(tpl['UV'])
        Fs.append(Fk + off)
        IN.append(np.full(len(Pv), k))
        off += len(Pv)
    for line in rep:
        log(f'[pearls] {line}')
    return dict(tpl=tpl, inst=inst, a=a, b=b0, c=c0, V=np.vstack(Vs), F=np.vstack(Fs), UV=np.vstack(UVs),
                N=np.vstack(Ns), inst_of=np.concatenate(IN), report=out, notes=rep)


def load(out_a):
    """AX4's droplets (cage_ax04_pearls.npz in out_a) as a dict of arrays, or None (no droplets: AX10's skin pearls)"""
    import os
    p = os.path.join(out_a, 'cage_ax04_pearls.npz')
    if not os.path.exists(p):
        return None
    Z = np.load(p, allow_pickle=False)
    return {k: Z[k] for k in Z.files}


def glb_arrays(P, off=0):
    """the droplets' vertex arrays for a glb's shared vertex buffers (x4 m): positions, the ellipsoids' analytic
    normals, MikkT-style tangents from the one UV shell (forge/bake.low_frames), UVs; their triangles offset by off"""
    from .. import bake as BK
    V = np.asarray(P['V_x4'], np.float64)
    F = np.asarray(P['F'], np.int64)
    N, T = BK.low_frames(V, F, np.asarray(P['UV'], np.float64), np.asarray(P['N'], np.float64))
    return dict(V=V, N=N, TAN=T, UV=np.asarray(P['UV'], np.float64), F=F + off)


def _lin(h):
    c = np.array([(int(h.lstrip('#'), 16) >> s) & 255 for s in (16, 8, 0)], np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def glb_material(g, spec):
    """the droplets' material on a forge/gltf GLB: 'axolotl_pearl', its CLARITY in factors only (SPEC ax13 drop_*: the
    opacity in baseColorFactor's alpha with alphaMode BLEND, KHR_materials_transmission, ior, a clear coat, a low
    roughness, KHR_materials_volume's thickness at x4); no texture, so no texture alpha (the engine's image decode
    divides an RGBA texture's colour by its alpha). Returns the material index"""
    a13 = spec['ax13']
    m = g.material('axolotl_pearl', extras=dict(
        bestiary='axolotl_pearl', part='the pearls: four glass droplets on the lower lip (species/axolotl_pearls.py)',
        clarity='material factors only: opacity (alpha BLEND), transmission, ior, clear coat, roughness, thickness; '
                'no textures; the UVs one shell the four share'))
    mat = g.j['materials'][m]
    tint = [float(x) for x in _lin(a13['drop_tint'])]
    mat['pbrMetallicRoughness'] = {'baseColorFactor': tint + [float(a13['drop_alpha'])], 'metallicFactor': 0.0,
                                   'roughnessFactor': float(a13['drop_rough'])}
    mat['alphaMode'] = 'BLEND'
    mat['doubleSided'] = False
    km = 0.004                                     # x4 metres per life mm (the glb's units)
    mat['extensions'] = {
        'KHR_materials_transmission': {'transmissionFactor': float(a13['drop_transmission'])},
        'KHR_materials_ior': {'ior': float(a13['drop_ior'])},
        'KHR_materials_clearcoat': {'clearcoatFactor': float(a13['drop_coat']),
                                    'clearcoatRoughnessFactor': float(a13['drop_coat_rough'])},
        'KHR_materials_volume': {'thicknessFactor': float(a13['drop_thick']) * km, 'attenuationColor': tint,
                                 'attenuationDistance': 4.0 * float(a13['drop_thick']) * km}}
    g.ext_used |= {'KHR_materials_transmission', 'KHR_materials_ior', 'KHR_materials_clearcoat',
                   'KHR_materials_volume'}
    return m


def roundness(tpl, frame):
    """the silhouette's largest turn between neighbouring equator vertices (deg) seen along the frame's out axis (e3):
    the template's ring at the equator of e3, its normals' angle step"""
    U = tpl['V']
    ring = np.abs(U[:, 2]) < 1e-6
    P = U[ring] @ np.asarray(frame).T
    ang = np.arctan2(U[ring, 1], U[ring, 0])
    o = np.argsort(ang)
    N = unit(U[ring][o] @ np.linalg.inv(np.asarray(frame)))
    d = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', N, np.roll(N, -1, axis=0)), -1.0, 1.0)))
    return float(d.max()), int(ring.sum()), P
