"""THE CRYSTAL BEETLE's growth plan (the crystal builder's round, 10-29): crystal clusters grown out of the finished stag
beetle (work/bestiary/beetle/out_b58: parts.npz, uv.npz, the static glb 51ff7539) with forge/growth.py, in metres at x10
(the glb's frame).

WHERE THEY ROOT (the builder's calls, each with its reason):
  * the DORSAL ARMOUR: the head capsule, the pronotum and the elytra's dorsal faces. REF R11 puts growth feet on
    up-facing skin at 2-2.6x its share; the armour is where a crystal can stand on a thick part; the legs, antennae and
    mandibles are STACKED texels (a crystal's foot would print on every copy) and move.
  * the ELYTRA's dorsal face only (dorsal_chart: the elytron master's largest chart, 2.38 M texels): its texels are given to the
    right elytron in a page of its own (the variant's page 2), so each side's crystals are its own; its other charts stay
    stacked, so no crystal reaches them (a margin inside the chart's boundary).
  * a clear zone round every OTHER part (the eyes, the mandibles' condyles, the antennal and palp insertions, the
    sleeves, the pronotum / head / elytra / scutellum junctions): growths there would block the joints that move.
THE BODY they root into (growth.py's INSIDE-THE-BODY test and the part radius by the half-thickness): the union of the
closed shells (each placed limit at level 3, signed by the winding number) and the HIND BODY's convex hull under the
elytra (the venter with the elytra's inner faces): the elytron is a 0.27 mm plate (2.7 mm at x10) over a 1.5 mm air
gap (cr00), so a crystal's buried base passes through the plate into the subelytral cavity, hidden as a real root would
be; the convex hull keeps the cavity from reading as a thin part (an exit and re-entry) without counting the air over
the elytra.
SIZES: BEETLE_PLAN §2.9's rule, remix/elements.place_scale on the BODY's extent (BL 0.436 m at x10): growth.grow's sizes
scaled so its k_size is extent / creature_m of the preset's reference (crystal: 0.436 / 3.3 = 0.132).
STABLE ROOTS (growth.stable_sites): every placed piece's own low, a seed per piece (its instance name's hash), so a
part's cage edit moves only that part's crystals.
"""
import json
import os
import zlib

import numpy as np
import warp as wp

from .. import growth as GR
from ..mesh import QuadMesh
from . import stag_beetle_parts as BP

EXTENT_M = 0.436                     # BEETLE_PLAN §2.9: the body's extent for growth sizing at x10 (BL)
CREATURE_M = dict(crystal=3.3, ice_shards=5.5)    # the presets' reference creatures (remix/elements.py placement)
SCALE = 0.01                         # life mm -> metres at x10
ROOT_PARTS = ('head', 'pronotum', 'elytron_L', 'elytron_R')
CLEAR_M = 0.010                      # the clear zone round every other part (1.0 mm life)
EDGE_M = 0.008                       # the elytra's margin inside their dorsal chart (0.8 mm life)
BODY_SHELLS = ('head', 'pronotum', 'scutellum', 'elytron', 'venter', 'eye', 'mandible')


def inst_seed(name, seed):
    """a placed piece's own seed: crc32 of its instance name mixed with the plan's seed"""
    return int(GR.stable_hash(seed, zlib.crc32(name.encode()) & 0xFFFFFFFF, 0, 21))


def dorsal_chart(chart):
    """(10-30, B8) the elytron master's dorsal face: its LARGEST chart (1,686 triangles; the next 564), from the per-triangle chart
    ids of uv.npz. It was the constant 19 until a re-pack renumbered the charts: 19 is then a 48-triangle sliver on page 1"""
    n = np.bincount(np.asarray(chart))
    c = int(n.argmax())
    assert n[c] > 2 * np.sort(n)[-2], f'the elytron\'s dorsal chart: the largest ({n[c]}) should dwarf the next'
    return c


# ============================================================================================ the base's pieces
def load_base(base_dir):
    """the finished base's parts and UVs: parts (stag_beetle_parts.load), uvs {master: arrays}, meta (uv.npz's)"""
    P = BP.load(os.path.join(base_dir, 'parts.npz'))
    Z = np.load(os.path.join(base_dir, 'uv.npz'), allow_pickle=False)
    meta = json.loads(str(Z['meta']))
    uvs = {nm: {k: Z[nm + '__' + k] for k in ('V', 'F', 'UV', 'page', 'N', 'orig', 'chart', 'cls')
                if nm + '__' + k in Z.files} for nm in meta['masters']}
    return P, uvs, meta


def placed_lows(P, uvs):
    """every placed piece's LOW (the runtime's mesh): {instance name: dict(V (x10 m), F (winding of the copy), N, master,
    region, side, flip, chart (per triangle), page, UV)}"""
    out = {}
    for m in P['masters']:
        U = uvs[m['name']]
        for it in m['instances']:
            V = BP.place(U['V'], it) * SCALE
            N = U['N'] @ it['M'].T
            N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)
            F = U['F'][:, ::-1].copy() if it['flip'] else U['F'].copy()
            out[it['name']] = dict(V=V, F=F, N=N, master=m['name'], region=m['region'], side=it['side'],
                                   flip=bool(it['flip']), chart=U.get('chart'), page=U['page'], UV=U['UV'],
                                   kind=m['kind'], it=it)
    return out


def placed_limits(P, names=BODY_SHELLS, level=3):
    """the closed shells' limit surfaces at `level` (subdiv_sharp), placed: {instance name: (V (x10 m), F, vertex N)}"""
    out = {}
    for m in P['masters']:
        if m['name'] not in names or m['kind'] != 'shell':
            continue
        lim = BP.limit_mesh(m, level)
        Nv = lim.vertex_normals()
        for it in m['instances']:
            V = BP.place(lim.V, it) * SCALE
            Q = BP.place_Q(lim.Q, it)
            F = QuadMesh(V, Q).tris()
            N = Nv @ it['M'].T
            N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)
            out[it['name']] = (V, F, N)
    return out


# ============================================================================================ the body
@wp.kernel
def k_shell_sd(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=wp.float32)):
    i = wp.tid()
    q = wp.mesh_query_point_sign_winding_number(mesh, pts[i], maxd, 2.0, 0.5)
    if q.result:
        c = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        out[i] = q.sign * wp.length(pts[i] - c)
    else:
        out[i] = maxd


@wp.kernel
def k_hull_sd(planes: wp.array(dtype=wp.vec4), pts: wp.array(dtype=wp.vec3), out: wp.array(dtype=wp.float32)):
    """a convex hull's signed distance (exact inside, a lower bound outside): the largest plane distance"""
    i = wp.tid()
    p = pts[i]
    best = float(-1.0e9)
    for k in range(planes.shape[0]):
        h = planes[k]
        best = wp.max(best, h[0] * p[0] + h[1] * p[1] + h[2] * p[2] + h[3])
    out[i] = best


@wp.kernel
def k_settle(mesh: wp.uint64, vn: wp.array(dtype=wp.vec3), tri: wp.array(dtype=wp.int32), pts: wp.array(dtype=wp.vec3),
             maxd: float, op: wp.array(dtype=wp.vec3), on: wp.array(dtype=wp.vec3), ok: wp.array(dtype=wp.int32)):
    i = wp.tid()
    q = wp.mesh_query_point_no_sign(mesh, pts[i], maxd)
    ok[i] = 0
    if q.result:
        op[i] = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        w = 1.0 - q.u - q.v
        n = vn[tri[3 * q.face]] * q.u + vn[tri[3 * q.face + 1]] * q.v + vn[tri[3 * q.face + 2]] * w
        on[i] = wp.normalize(n)
        ok[i] = 1


class Body:
    """THE BODY the crystals root into (the module notes): sd(points) = min(the closed shells' signed distance, the hind
    body's convex hull under the elytra); settle(points) = the nearest point on the shells' SKIN and its normal (the
    limits' interpolated vertex normals); a part id per shell triangle for the masks"""

    def __init__(self, limits, device=None):
        self.device = device
        names = list(limits)
        V = np.concatenate([limits[k][0] for k in names])
        offs = np.cumsum([0] + [len(limits[k][0]) for k in names])
        F = np.concatenate([limits[k][1] + o for k, o in zip(names, offs[:-1])]).astype(np.int32)
        N = np.concatenate([limits[k][2] for k in names])
        self.names = names
        self.tri_part = np.concatenate([np.full(len(limits[k][1]), j) for j, k in enumerate(names)])
        self.V, self.F, self.N = V, F, N
        self.mesh = wp.Mesh(points=wp.array(V.astype(np.float32), dtype=wp.vec3, device=device),
                            indices=wp.array(F.ravel(), dtype=wp.int32, device=device), support_winding_number=True)
        self.vn = wp.array(N.astype(np.float32), dtype=wp.vec3, device=device)
        self.tri = wp.array(F.ravel(), dtype=wp.int32, device=device)
        # the hind body's hull under the elytra: the venter and the elytra's INNER faces (their downward vertices)
        from scipy.spatial import ConvexHull
        hp = [limits['venter'][0][::12]]                         # (a coarse set: the hull of every point had 40 k planes)
        for k in ('elytron_L', 'elytron_R'):
            v, f, n = limits[k]
            hp.append(v[n[:, 1] < -0.2][::12])
        H = ConvexHull(np.concatenate(hp))
        self.hull = H.equations.astype(np.float64)              # n . x + d <= 0 inside
        self.hull_d = wp.array(self.hull.astype(np.float32), dtype=wp.vec4, device=device)
        # its triangles oriented outward by its planes (a winding number on the low then counts the cavity as inside)
        HF = H.simplices.copy()
        fn = np.cross(H.points[HF[:, 1]] - H.points[HF[:, 0]], H.points[HF[:, 2]] - H.points[HF[:, 0]])
        flip = (fn * H.equations[:, :3]).sum(1) < 0
        HF[flip] = HF[flip][:, ::-1]
        self.hull_mesh = (H.points.astype(np.float64), HF)

    def skin_low(self, lows):
        """the runtime's mesh round the body for growth.trim_planes' second test (a face point outside it shows: the
        low's flat triangles cut chords under the limit, up to ~1 mm at x10 on the pronotum's curved flanks, cr02b): the
        closed pieces' lows plus the hind hull's oriented triangles (the subelytral cavity is inside, never 'showing')"""
        Vs, Fs, off = [], [], 0
        for nm, L in lows.items():
            if L['master'] not in BODY_SHELLS:
                continue
            Vs.append(L['V'])
            Fs.append(L['F'] + off)
            off += len(L['V'])
        Vs.append(self.hull_mesh[0])
        Fs.append(self.hull_mesh[1] + off)
        return np.concatenate(Vs), np.concatenate(Fs)

    def sd_hull(self, pts):
        pts = np.asarray(pts, np.float32).reshape(-1, 3)
        if not len(pts):
            return np.zeros(0)
        o = wp.zeros(len(pts), dtype=wp.float32, device=self.device)
        wp.launch(k_hull_sd, dim=len(pts), inputs=[self.hull_d, wp.array(pts, dtype=wp.vec3, device=self.device), o],
                  device=self.device)
        return o.numpy().astype(np.float64)

    def sd_shells(self, pts, maxd=0.2):
        pts = np.asarray(pts, np.float32).reshape(-1, 3)
        if not len(pts):
            return np.zeros(0)
        P = wp.array(pts, dtype=wp.vec3, device=self.device)
        o = wp.zeros(len(pts), dtype=wp.float32, device=self.device)
        wp.launch(k_shell_sd, dim=len(pts), inputs=[self.mesh.id, P, float(maxd), o], device=self.device)
        return o.numpy().astype(np.float64)

    def sd(self, pts):
        return np.minimum(self.sd_shells(pts), self.sd_hull(pts))

    def settle(self, pts, maxd=0.02):
        pts = np.asarray(pts, np.float32).reshape(-1, 3)
        P = wp.array(pts, dtype=wp.vec3, device=self.device)
        op = wp.zeros(len(pts), dtype=wp.vec3, device=self.device)
        on = wp.zeros(len(pts), dtype=wp.vec3, device=self.device)
        ok = wp.zeros(len(pts), dtype=wp.int32, device=self.device)
        wp.launch(k_settle, dim=len(pts), inputs=[self.mesh.id, self.vn, self.tri, P, float(maxd), op, on, ok],
                  device=self.device)
        p, n, k = op.numpy().astype(np.float64), on.numpy().astype(np.float64), ok.numpy() > 0
        p[~k], n[~k] = pts[~k], np.array([0.0, 1.0, 0.0])
        return p, n


# ============================================================================================ the masks
def surface_samples(V, F, spacing):
    """points on a triangle mesh about `spacing` apart (each triangle's barycentric grid)"""
    out = []
    for f in F:
        a, b, c = V[f[0]], V[f[1]], V[f[2]]
        m = max(1, int(np.ceil(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / spacing)))
        i, j = np.meshgrid(np.arange(m + 1), np.arange(m + 1), indexing='ij')
        k = i + j <= m
        u, v = (i[k] / m)[:, None], (j[k] / m)[:, None]
        out.append(a + u * (b - a) + v * (c - a))
    return np.concatenate(out) if out else np.zeros((0, 3))


def chart_boundary(V, F, chart, c):
    """the outline of chart c on a UV-split low: the edges of its triangles that no other triangle of it shares"""
    sel = np.nonzero(chart == c)[0]
    E = np.concatenate([F[sel][:, [0, 1]], F[sel][:, [1, 2]], F[sel][:, [2, 0]]])
    Es = np.sort(E, axis=1)
    u, cnt = np.unique(Es, axis=0, return_counts=True)
    return u[cnt == 1]


def edge_samples(V, E, spacing):
    out = []
    for a, b in E:
        m = max(1, int(np.ceil(np.linalg.norm(V[b] - V[a]) / spacing)))
        t = np.linspace(0.0, 1.0, m + 1)[:, None]
        out.append(V[a] + t * (V[b] - V[a]))
    return np.concatenate(out) if out else np.zeros((0, 3))


def smooth01(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def root_masks(lows, sites, log=print):
    """per site (sites['inst'] names its piece) its eligibility 0..1 (the module notes' WHERE THEY ROOT): the dorsal armour
    only; a clear zone round every other part; the elytra on their dorsal chart, inside its outline"""
    from scipy.spatial import cKDTree
    mask = np.zeros(len(sites['p']))
    inst = sites['inst']
    for nm in ROOT_PARTS:
        sel = np.nonzero(inst == nm)[0]
        if not len(sel):
            continue
        L = lows[nm]
        others = [k for k, o in lows.items() if k != nm and o['kind'] in ('shell', 'sleeve')]
        # the other parts as dense samples (0.25 mm life apart), only those within reach of this piece's box
        lo, hi = L['V'].min(0) - 3 * CLEAR_M, L['V'].max(0) + 3 * CLEAR_M
        pts = []
        for k in others:
            o = lows[k]
            if np.any(o['V'].max(0) < lo) or np.any(o['V'].min(0) > hi):
                continue
            pts.append(surface_samples(o['V'], o['F'], 0.0025))
        d_other = cKDTree(np.concatenate(pts)).query(sites['p'][sel])[0] if pts else np.full(len(sel), np.inf)
        m = smooth01(CLEAR_M, 1.6 * CLEAR_M, d_other)
        tri = sites['tri'][sel]
        if L['master'] == 'elytron':
            dc = dorsal_chart(L['chart'])
            on = (L['chart'][tri] == dc).astype(np.float64)
            bE = chart_boundary(L['V'], L['F'], L['chart'], dc)
            d_edge = cKDTree(edge_samples(L['V'], bE, 0.0015)).query(sites['p'][sel])[0]
            m *= on * smooth01(EDGE_M, 1.5 * EDGE_M, d_edge)
        elif L['master'] == 'head':
            # the head's upper face only: its margins are the canthi and the flanges over the eyes, where a crystal
            # juts sideways like a stray antenna (cr02 r1)
            m *= smooth01(0.20, 0.50, sites['n'][sel][:, 1])
        else:
            # the pronotum's disc and upper flanks: its lower flanks wrap down to the fore coxae, where a crystal stood
            # over the fore leg's swing (cr02 r3, the close still)
            m *= smooth01(0.05, 0.35, sites['n'][sel][:, 1])
        mask[sel] = m
        log(f'[beetle crystal] {nm}: {len(sel)} candidate slots, eligible share {m.mean():.3f}')
    return mask


# ============================================================================================ the plan
def plan(base_dir, family='crystal', seed=29, d_max=30000.0, count_scale=1.0, voxel=0.00012, texel=1.0 / 9257.0,
         device=None, crust_S=None, reroll=(), log=print, **kw):
    """the crystal beetle's growth plan: stable sites over EVERY placed piece (mask 0 off the armour: grow() measures the
    whole skin's dorsal share), the body, growth.grow (sizes by BEETLE_PLAN's rule), each crystal's part and its trim
    cut (growth.trim_planes against the body; the low's chord sag, ~0.13 mm at x10, under the trim's margin). Returns
    (cr, ctx): cr = growth.grow's arrays + 'cut' and 'part' (per crystal entry, its piece's instance name); ctx = the
    lows, the body, the sites"""
    P, uvs, meta = load_base(base_dir)
    lows = placed_lows(P, uvs)
    limits = placed_limits(P)
    body = Body(limits, device)
    log(f'[beetle crystal] body: {len(body.F):,} shell triangles ({len(body.names)} pieces), hull {len(body.hull)} '
        f'planes under the elytra')
    S = []
    for nm, L in lows.items():
        # (reroll: these pieces' slots from another seed, as a cage edit of that piece would re-key them: the other
        # pieces' crystals stay where they were)
        st = GR.stable_sites(L['V'], L['F'], d_max, inst_seed(nm, seed + (7919 if nm in reroll else 0)))
        if not len(st['p']):
            continue                                    # (a claw or a tarsomere under one slot's area)
        st['inst'] = np.full(len(st['p']), nm, dtype=object)
        S.append(st)
    sites = {k: np.concatenate([s[k] for s in S]) for k in S[0]}
    skin_area = float(sum(0.5 * np.linalg.norm(np.cross(L['V'][L['F'][:, 1]] - L['V'][L['F'][:, 0]],
                                                         L['V'][L['F'][:, 2]] - L['V'][L['F'][:, 0]]), axis=1).sum()
                          for L in lows.values()))
    # the roots on the skin: the low's slots projected onto the shells' limits (the others keep their low point)
    p, n = body.settle(sites['p'])
    on_shell = np.isin(sites['inst'], [k for k in lows if lows[k]['master'] in BODY_SHELLS])
    sites['p'] = np.where(on_shell[:, None], p, sites['p'])
    Nl = []
    for s in S:                                         # the low's interpolated normal (the pieces off the body)
        L, t, b = lows[s['inst'][0]], s['tri'], s['bary']
        Nl.append(L['N'][L['F'][t, 0]] * b[:, :1] + L['N'][L['F'][t, 1]] * b[:, 1:2] + L['N'][L['F'][t, 2]] * b[:, 2:])
    Nl = np.concatenate(Nl)
    Nl /= np.maximum(np.linalg.norm(Nl, axis=1, keepdims=True), 1e-20)
    sites['n'] = np.where(on_shell[:, None], n, Nl)
    sites['mask'] = root_masks(lows, sites, log)
    sites['mult'] = np.ones(len(sites['p']))
    if crust_S is not None:
        sites['crust_S'] = float(crust_S)          # the crust's waves at 0.33 crust_S (growth.grow's stable path)
    preset = GR.PAIRING[family]
    k_rule = EXTENT_M / CREATURE_M.get(preset, 3.3)
    Sg = np.sqrt(skin_area) / np.sqrt(GR.PLACEMENT[preset]['A_ref'])
    log(f'[beetle crystal] {len(sites["p"])} stable slots on {len(lows)} pieces (d_max {d_max:.0f} / m2), skin '
        f'{skin_area:.4f} m2 at x10; {family}/{preset}: sizes x{k_rule:.4f} by the body-extent rule '
        f'(size_scale {k_rule / Sg:.4f} over the area scaling x{Sg:.4f})')
    cr = GR.grow({k: v for k, v in sites.items() if k != 'inst'}, preset, family, skin_area,
                 np.random.default_rng(seed), gamma=1.0, voxel=voxel, texel=texel, size_scale=k_rule / Sg,
                 count_scale=count_scale, settle=body.settle, sdf=body.sd, ground=0.0, log=log, **kw)
    site_of = np.asarray([pc['site'] for pc in cr['pieces']], np.int64)
    cr['part'] = sites['inst'][site_of[cr['piece']]] if len(cr['a']) else np.zeros(0, dtype=object)
    cr['stack_of'] = np.arange(len(cr['a']))
    low = body.skin_low(lows)
    cr['cut'] = GR.trim_planes(cr, body.sd, voxel, skin_low=low)
    ts = GR.trim_slits(cr, cr['cut'], body.sd, voxel, skin_low=low)
    cr['report']['trim'] = ts
    log(f'[beetle crystal] trim: {ts["showing"]} of {ts["points"]} face samples show ({ts["by_low"]} only outside the '
        f'low); slits under the cut {ts["slits"]} on {ts["slit_crystals"]} crystals')
    for nm in ROOT_PARTS:
        k = cr['part'] == nm
        log(f'[beetle crystal]   {nm}: {int(k.sum())} crystal entries, {len(np.unique(cr["piece"][k]))} pieces')
    return cr, dict(lows=lows, limits=limits, body=body, sites=sites, skin_area=skin_area, meta=meta, P=P, uvs=uvs)
