"""UV STACKING for the mech tentacle (Skye, 10-27: "most of these pieces seem to be the same piece repeated and
shrunk/rotated, because of that, it makes more sense to simply repeatedly use the UV shells for the largest/highest
pixel space ones rather than repeat new UV islands for every sections"; the lead's calls 1-4 of the same day).

THE UNIT is a SPEC: one piece of cyborg_limb's low at one joint (a knuckle part from knuckle_parts, a segment's shell,
a clamp ring, its lug, its saddle). C5-UV b (the lead's call, 10-28: "group by geometry rather than by name"): a CLASS
is every spec of one kind, one region (the material paints by region: a drum and a lug never share texels) and one
primitive type, whatever its name (C5d's families, the name with its joint number dropped, left identical pieces whose
names differ in a side word, oral / aboral, +z / -z, packed and baked twice). In a class the spec with the largest texel
need (its islands' area x density^2; between equals the one with the most visible surface) is the PRIMARY. Every other
spec is rebuilt with the primary's TOPOLOGY (its side count; a clamp ring's end faces) and fitted to it by a scaled
Kabsch (Umeyama: rotation, uniform scale, translation) under a CORRESPONDENCE: the lows' own index order where both are
one element at two joints (one name but for the joint number: one code path built both, so the order is the design's);
else the best of the vertex maps that the whole rotations of a cube induce (each vertex to the other low's nearest
after the similarity), by their CONTEXT (context_score: the other pieces' distance at corresponding points and above
them along their normals, which is what each surface is baked in; an oral lug's outer face fits an aboral lug's inner
face exactly, index for index, but its texels hold the open side and the machined rim). One whose residual stays within
RELTOL of its size, and whose clipped features match (a shell's chamfers), joins the primary's GROUP. The rest form
groups of their own the same way (the next largest their primary) or stay unique.

THE STACK: a member is GIVEN its primary's low: the primary's final islands (after the chamfer cuts, clip_buried and
clip_nested; oriented) with their topology, vertex order and UVs, each vertex carried onto the member by the
correspondence of the two UNCLIPPED lows (its barycentric place on its unclipped island, read on the member's island
of the same index and triangle). For an exact similarity this IS the Umeyama placement; for a near one (the forge
sizes each knuckle from its own motion range and each shell from the flesh's taper between fixed joints) the member
keeps its own designed surface and the shared texels absorb the deviation, the reported residual, as a stretch of at
most RELTOL. A member whose own visible surface the carried low does not cover (a face the primary's neighbours bury
that its own do not) is UN-STACKED: its own islands, packed and baked on its own. C5-UV b: so is a member that reads its
primary's texels so many mips coarser that it would show its neighbours' colour (margin_check: its mip offset log2(1/s)
past what its primary's measured gutter holds, less C5f's MIP_HEADROOM) when un-stacking it costs fewer texels than
widening that gutter. C5f: such members are first planned again among themselves (a class's fall-outs under the
largest of them, when their own margin holds them), and only what still falls out is un-stacked.

Only primaries and unique pieces are packed and baked (bake_view); every member still stands in the bake's highs (its
body's program), so it occludes in the AO and contact passes. Stacked primaries pack with PAD_STACKED texels of
gutter (their members show them minified: the memory's rule, repeated islands get more padding); C5f: the rubber
band with PAD_BAND (its thin strip seen edge on reads far mips).
"""
import math
import re

import numpy as np

try:                                        # in the forge package
    from . import cyborg_limb as CL
except ImportError:                         # (scratch: imported as a top-level module beside an overlaid forge)
    from eidoverse.bestiary.forge import cyborg_limb as CL

RELTOL = 0.05               # a member's Umeyama residual at most this share of its size (its largest extent): the shared
                            # texels' stretch on it stays within 5 %
PAD, PAD_STACKED = 3, 6     # gutters (texels): every island as cyborg_limb packs it; a stacked primary's islands at most
                            # (PAD + ceil(log2(1 / its smallest member's s)): the mips its members read it at)
PX_TODAY = 5179.29807346007     # C5c's shipped density (px/m): the largest instance never below it (the lead's call 3)
SIZES = ((1024, 512), (1024, 1024), (2048, 512), (2048, 1024))   # the sets tried, fewest texels first (W the wide
                            # side, H <= W; 1024 x 1024 and 2048 x 512 hold the same texels: the square first)
COVER_TOL = 0.05e-3         # a member's visible sample is covered when it lies this near its carried low (a quarter of a
                            # texel at 5.18 px/mm, a fifth of the low's sagitta: a HOLE is what it finds, not the 0.02 mm
                            # a member's own chamfer plane stands off its primary's carried one)
VISIBLE = 0.01e-3           # a sample is visible when it stands this far outside every other piece (the machine at rest)
BAD_MM2 = 0.01              # a member's visible surface the carried low misses: at most this (mm2), else un-stacked
U4_RANGE = 1.5 * 1.5        # C5a's U4 on a member: its densest over its sparsest triangle (each over its primary island's
                            # density) at most this, so its own density centred they all lie within 1/1.5 .. 1.5
SUFFIX = re.compile(r' (band\d+ part\d+|band\d+|face\d+|sides|end-?1|proximal end|distal end|aboral chamfer|'
                    r'oral chamfer)$')
JOINT = re.compile(r'(?<![\w.+-])(\d+)(?![\w.])')
CTX_OFFS = (0.0, 0.3e-3, 0.6e-3, 1.2e-3)    # C5-UV b: the context score reads the other pieces' distance at a sample and
                            # this far above it along its outward normal (the primary's units, the member's x s): the near
                            # field the bake's AO and cavity rays see
CTX_CLIP = 1.0e-3           # each distance clipped to +-this (the primary's units)
CTX_STEP = 0.30e-3          # the context's samples on the primary's unclipped low about this far apart
CTX_TIE = 0.75              # the index order (where both lows are of one code path) wins unless another correspondence's
                            # context score is at most this share of its own
MARGIN_CAP = 16.0           # the maps' gutters are grown 16 texels at most (bake.dilate_all): a margin never counts past it
MIP_BILINEAR = 1.5          # a mip m read is bilinear IN that mip: past the 2^(m - 1) texels its box reaches it takes in
                            # the next mip texel, half a mip texel more (w10_member_mips.py on the shipped albedo: the
                            # one member past log2(2 x margin / 1.5), clamp lug 22, read up to 0.18 of its neighbours')
MIP_HEADROOM = 1.0          # C5f (the lead's call 2): a member's mip offset stays this many mips inside what its primary's
                            # gutter holds. The round-5 rule held at the screen size where the primary reads mip 0 only:
                            # at half that size the members nearest it read their neighbours (clamp 23 on 29 % of its
                            # texels, clamp lugs 21 / 20 on 9 / 4 %; the uvb look's k04_small.py, all 0 % in C5c)
PAD_BAND = 19               # C5f (the lead's call 3): the rubber band's gutter (texels). Its strip's light neighbours'
                            # gutter fill stood 5-8 texels off it (C5c: 11-23) and a 4 deg facet of the band, read
                            # isotropically, averaged it in: the last collar mark. With a 3-texel neighbour and the dark
                            # gutter's 2 (cyborg_limb.GUTTER_DARK) the light fill starts (19 + 3) / 2 + 1 = 12 texels off


# ============================================================================================ names
def spec_of(piece):
    """an island's spec: its name without the island suffix ('drum 9 aboral band1' -> 'drum 9 aboral', 'shell 12 band0
    part3' -> 'shell 12', 'clamp lug 8 end-1' -> 'clamp lug 8'); the flange's, the band's and the hose's as they are"""
    return SUFFIX.sub('', piece)


def joint_of(spec):
    m = JOINT.search(spec)
    return int(m.group(1)) if m else None


def family_of(spec):
    """the spec's family: its joint number as '#' (None for the unnumbered: flange, band, hose)"""
    m = JOINT.search(spec)
    if m is None or spec.startswith('hose') or spec.startswith('collar') or spec in ('band', 'roll'):
        return None
    return spec[:m.start()] + '#' + spec[m.end():]


def rename(name, k_from, k_to):
    """a primary's island name for a member: its first joint number k_from as k_to"""
    m = JOINT.search(name)
    assert m and int(m.group(1)) == k_from, f'{name!r}: no joint {k_from}'
    return name[:m.start()] + str(k_to) + name[m.end():]


def carry_name(nm, p, q):
    """C5-UV b: a primary p's island (smooth group, primitive) name as its member q carries it: p's spec replaced by
    q's (the member's island keeps its primary's island suffix whichever of its own faces it lies on: it carries that
    island's texels; 'yaw lug 16 oral face0' -> 'yaw lug 16 aboral face0'); a name not under p (a split spec's primitive,
    'drum 9 ring') takes q's joint number for p's"""
    if nm == p or nm.startswith(p + ' '):
        return q + nm[len(p):]
    kp, kq = joint_of(p), joint_of(q)
    m = JOINT.search(nm)
    if m and kp is not None and kq is not None and int(m.group(1)) == kp:
        return rename(nm, kp, kq)
    return nm


def primary_name(nm, q, p):
    """C5-UV b: carry_name's inverse: the name of the primary p's island a member q's island carries"""
    return carry_name(nm, q, p)


# ============================================================================================ geometry helpers
def area_of(V, F):
    return 0.5 * float(np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1).sum()) \
        if len(F) else 0.0


def need_of(islands):
    """the texel need: the islands' area x their density factor squared (pack_islands' weighting)"""
    return sum(area_of(it['V'], it['F']) * it['dens'] ** 2 for it in islands)


def umeyama(P, Q):
    """the similarity (s, R, t) with Q ~ s R P + t in least squares (R proper), and its largest vertex residual"""
    mp, mq = P.mean(0), Q.mean(0)
    X, Y = P - mp, Q - mq
    C = Y.T @ X / len(P)
    U, S, Vt = np.linalg.svd(C)
    d = 1.0 if np.linalg.det(U @ Vt) >= 0.0 else -1.0
    Dm = np.diag([1.0, 1.0, d])
    R = U @ Dm @ Vt
    s = float(np.trace(np.diag(S) @ Dm) / max((X ** 2).sum(1).mean(), 1e-30))
    t = mq - s * R @ mp
    E = (s * (R @ P.T)).T + t - Q
    return s, R, t, float(np.linalg.norm(E, axis=1).max())


def locate(P, V, F, chunk=256):
    """each point's place on the mesh (V, F): (triangle, barycentric (n, 3), plane distance, outside share): the
    triangle whose plane holds it best inside (a point on the mesh lands at 0 / 0; an off-mesh one at its foot's)"""
    P = np.asarray(P, np.float64)
    A, B, C = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    v0, v1 = B - A, C - A
    nrm = np.cross(v0, v1)
    nl = np.linalg.norm(nrm, axis=1)
    nrm = nrm / np.maximum(nl, 1e-30)[:, None]
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    den = np.where(np.abs(d00 * d11 - d01 * d01) > 1e-40, d00 * d11 - d01 * d01, 1e-40)
    scale = np.sqrt(np.maximum(d00, d11))
    tri = np.zeros(len(P), np.int64)
    bary = np.zeros((len(P), 3))
    pdist = np.zeros(len(P))
    outs = np.zeros(len(P))
    for i0 in range(0, len(P), chunk):
        p = P[i0:i0 + chunk][:, None, :]
        v2 = p - A[None]
        d20, d21 = (v2 * v0[None]).sum(2), (v2 * v1[None]).sum(2)
        v = (d11[None] * d20 - d01[None] * d21) / den[None]
        w = (d00[None] * d21 - d01[None] * d20) / den[None]
        u = 1.0 - v - w
        out = np.maximum(0.0, np.maximum(-u, np.maximum(-v, -w))) * scale[None]
        pl = np.abs((v2 * nrm[None]).sum(2))
        j = np.argmin(out + pl, axis=1)
        r = np.arange(len(j))
        tri[i0:i0 + chunk] = j
        b = np.stack([u[r, j], v[r, j], w[r, j]], 1)
        b = np.clip(b, 0.0, None)
        bary[i0:i0 + chunk] = b / np.maximum(b.sum(1, keepdims=True), 1e-30)
        pdist[i0:i0 + chunk] = pl[r, j]
        outs[i0:i0 + chunk] = out[r, j]
    return tri, bary, pdist, outs


def at(V, F, tri, bary):
    return (bary[:, :, None] * V[F[tri]]).sum(1)


def tri_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)


def island_density(V, F, UV):
    """an island's UV units per metre (forge/uv.py island_density: what pack_islands scales by)"""
    from eidoverse.bestiary.forge import uv as U
    return float(U.island_density(V, F, UV))


def tri_sv(V, F, UV):
    """per triangle the singular values (largest first) of its UV map's Jacobian, UV units per metre: c05's U4 formula"""
    e1 = V[F[:, 1]] - V[F[:, 0]]
    e2 = V[F[:, 2]] - V[F[:, 0]]
    nn = np.cross(e1, e2)
    ok = 0.5 * np.linalg.norm(nn, axis=1) > 1e-14
    if not ok.any():
        return np.zeros((0, 2))
    e1, e2, nn = e1[ok], e2[ok], nn[ok]
    t1 = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-20)
    t2 = np.cross(nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-20), t1)
    Pm = np.stack([np.einsum('ij,ij->i', e1, t1), np.einsum('ij,ij->i', e1, t2), np.einsum('ij,ij->i', e2, t1),
                   np.einsum('ij,ij->i', e2, t2)], 1).reshape(-1, 2, 2)
    Fo = F[ok]
    Um = np.stack([UV[Fo[:, 1]] - UV[Fo[:, 0]], UV[Fo[:, 2]] - UV[Fo[:, 0]]], 1)
    return np.linalg.svd(np.linalg.solve(Pm, Um), compute_uv=False)


def tri_samples(V, F, step):
    """points on every triangle at about `step` apart, each with its triangle and its share of the area"""
    pts, tri, wts = [], [], []
    for t, f in enumerate(F):
        p = V[f]
        e = max(np.linalg.norm(p[1] - p[0]), np.linalg.norm(p[2] - p[1]), np.linalg.norm(p[0] - p[2]))
        m = max(1, int(math.ceil(e / step)))
        ii, jj = np.meshgrid(np.arange(m + 1), np.arange(m + 1))
        sel = ii + jj <= m
        a_, b_ = ii[sel] / m, jj[sel] / m
        q = p[0] + a_[:, None] * (p[1] - p[0]) + b_[:, None] * (p[2] - p[0])
        pts.append(q)
        tri.append(np.full(len(q), t))
        wts.append(np.full(len(q), area_of(p, np.array([[0, 1, 2]])) / len(q)))
    if not pts:
        return np.zeros((0, 3)), np.zeros(0, np.int64), np.zeros(0)
    return np.concatenate(pts), np.concatenate(tri), np.concatenate(wts)


# ============================================================================================ the specs' lows
class Ctx:
    """the design's specs indexed: every knuckle spec by name (its spec, its pivot's place in the asset frame, its
    body's joint), every clamp by its segment, every shell's body"""

    def __init__(self, chain, des):
        self.chain, self.des = chain, des
        x = chain['x']
        self.spec = {}
        for body in des['bodies']:
            if body == CL.bone_name(CL.J0):
                continue
            ob = np.array([x[CL.body_k(body)], 0.0, 0.0])
            for sp, pv in CL.body_specs(chain, des, body):
                if sp.get('sub') or (sp['t'] == 'rev' and sp.get('low') is None):
                    continue
                self.spec[sp['name']] = (sp, ob + pv, CL.body_k(body))
        self.clamp = {c['k']: c for c in des['clamps']}

    def kind(self, spec):
        """'knuckle', 'shell', 'clamp', 'clamp lug', 'saddle' or None (unique by construction)"""
        if spec in self.spec:
            return 'knuckle'
        for pre in ('shell ', 'clamp lug ', 'saddle ', 'clamp '):
            if spec.startswith(pre) and spec[len(pre):].isdigit():
                return pre.strip()
        return None

    def topology(self, spec):
        """the topology parameters a member takes from its primary: a revolve spec's side count; a clamp ring's side
        count and its end faces; nothing for a box or a shell (their structure follows from the design)"""
        kd = self.kind(spec)
        if kd == 'knuckle':
            sp = self.spec[spec][0]
            if sp['t'] != 'rev':
                return None
            prof = sp['low']
            return dict(n=sp.get('n') or CL.n_sides(max(r_ for r_, _ in prof), lo=sp.get('lo', 8),
                                                    sag=sp.get('sag', CL.SAG)))
        if kd == 'clamp':
            c = self.clamp[joint_of(spec)]
            wall = c['R'] - c['rh']
            return dict(ns=CL.n_sides(c['R'], lo=6, hi=12, sag=min(0.30e-3, 0.5 * wall)), four=wall >= 0.25e-3)
        return None

    def own_final(self, spec, topo, progs_bake):
        """the spec's islands as its OWN design shows them: with the given topology, a shell cut by its own chamfers,
        then clipped in its own place (clip_buried, clip_nested): what the cover test reads"""
        isl = self.unclipped(spec, topo, cut=True)
        isl = CL.clip_buried(isl, progs_bake, log=lambda *a: None)
        return CL.clip_nested(isl, self.des, progs_bake, log=lambda *a: None)

    def unclipped(self, spec, topo=None, cut=False):
        """the spec's islands as build_low builds them, UNCLIPPED (a shell without its chamfer cuts unless cut), with
        the given topology (None: its own)"""
        kd = self.kind(spec)
        chain, des = self.chain, self.des
        x = chain['x']
        if kd == 'knuckle':
            sp, o, k = self.spec[spec]
            sp2 = dict(sp)
            if topo is not None and sp['t'] == 'rev':
                sp2['n'] = topo['n']
            return CL._spec_islands(sp2, o, k)
        k = joint_of(spec)
        if kd == 'shell':
            si, _ = CL.shell_islands(chain, des, k, np.array([x[k], 0.0, 0.0]), body=CL.shell_body(des, k), cut=cut)
            return si
        c = self.clamp[k]
        sb = CL.shell_body(des, k)
        rh_, R, L_ = c['rh'], c['R'], c['L']
        cpos = np.array([c['x'], c['y'], 0.0])
        if kd == 'clamp':
            tp = topo or self.topology(spec)
            hx = 0.5 * L_ - min(CL.LOW_INSET, 0.12 * L_)
            prof = [(rh_, -hx), (R, -hx), (R, hx), (rh_, hx)] if tp['four'] else [(R, -hx), (R, hx)]
            out = CL.revolve_islands(prof, cpos, CL.AX['x'], tp['ns'], 'clamp', k, f'clamp {k}')
        elif kd == 'clamp lug':
            out = CL.box_islands(cpos + [0.0, 0.0, 0.5 * (c['R_lug'] + rh_)],
                                 CL._inset([0.42 * L_, 0.30 * c['D'], 0.5 * (c['R_lug'] - rh_)]), 'clamp', k,
                                 f'clamp lug {k}')
        else:
            ytop = des['top'](c['x'])
            y0, y1 = ytop - CL.saddle_sink(des, c), c['y'] - 0.5 * (R + rh_)
            out = CL.box_islands([c['x'], 0.5 * (y0 + y1), 0.0],
                                 CL._inset([0.45 * L_, 0.5 * (y1 - y0), 0.75 * R], axes=(0, 2)), 'clamp', k,
                                 f'saddle {k}')
        for it in out:
            it['body'] = sb
        return out


def structure(islands):
    return [(it['piece'].split(' ', 1)[0], spec_suffix(it['piece']), len(it['V']), len(it['F'])) for it in islands]


def spec_suffix(piece):
    m = SUFFIX.search(piece)
    return m.group(1) if m else ''


# ============================================================================================ the groups
def spec_class(ctx, spec, by_spec):
    """C5-UV b: the spec's CLASS, whatever its name: its kind (knuckle, shell, clamp, clamp lug, saddle), its islands'
    regions (the material paints by region and finish) and, for a knuckle part, its primitive type (rev / box)"""
    kd = ctx.kind(spec)
    regs = tuple(sorted({CL.REGIONS[it['region']] for it in by_spec[spec]}))
    return (kd, regs, ctx.spec[spec][0]['t'] if kd == 'knuckle' else kd)


def _cube_rotations():
    """the 24 proper rotations of a cube (the axis permutations with signs, det +1), the identity first"""
    import itertools
    out = []
    for perm in itertools.permutations(range(3)):
        for sg in itertools.product((1.0, -1.0), repeat=3):
            M = np.zeros((3, 3))
            for i, (j, s_) in enumerate(zip(perm, sg)):
                M[i, j] = s_
            if np.linalg.det(M) > 0.5:
                out.append(M)
    return out


CUBE = _cube_rotations()


def correspondences(Up, Uq, size, index_only=False):
    """C5-UV b: the vertex maps that carry the primary's unclipped low Up onto a member's Uq (rebuilt on Up's
    topology): [(label, s, R, t, residual, src)], src {Up's island name: Uq's positions in that island's vertex order}
    (what the carry reads). The lows' own index order when their islands line up; unless index_only, every map a whole
    rotation of the cube induces (Up turned by it about its centroid and scaled to Uq's RMS size, each vertex to Uq's
    nearest, the similarity refined on those pairs; the map must reach every distinct vertex of Uq); each kept when its
    Umeyama residual stays within RELTOL of the size; one map once"""
    from scipy.spatial import cKDTree
    Pp = np.concatenate([a['V'] for a in Up])
    Pq = np.concatenate([a['V'] for a in Uq])
    out = []
    if [(len(a['V']), len(a['F'])) for a in Up] == [(len(a['V']), len(a['F'])) for a in Uq]:
        s, R, t, e = umeyama(Pp, Pq)
        if e <= RELTOL * size:
            out.append(('index', s, R, t, e, {a['piece']: b['V'] for a, b in zip(Up, Uq)}))
    if index_only or len(Pp) != len(Pq):
        return out
    cp, cq = Pp.mean(0), Pq.mean(0)
    s0 = math.sqrt(((Pq - cq) ** 2).sum(1).mean() / max(((Pp - cp) ** 2).sum(1).mean(), 1e-30))
    tree = cKDTree(Pq)
    n_pos = len(np.unique(np.round(Pq / 1e-7).astype(np.int64), axis=0))
    seen = [np.concatenate([c[5][a['piece']] for a in Up]) for c in out]
    for G in CUBE[1:]:
        d, j = tree.query(cq + s0 * (Pp - cp) @ G.T)
        if d.max() > 0.25 * size:
            continue
        if len(np.unique(np.round(Pq[j] / 1e-7).astype(np.int64), axis=0)) < n_pos:
            continue
        s, R, t, e = umeyama(Pp, Pq[j])
        if e > RELTOL * size:
            continue
        key = Pq[j]
        if any(np.allclose(key, k2, atol=1e-10) for k2 in seen):
            continue
        seen.append(key)
        ang = math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(R) - 1.0) / 2.0))))
        o, src = 0, {}
        for a in Up:
            src[a['piece']] = Pq[j[o:o + len(a['V'])]]
            o += len(a['V'])
        out.append((f'turned {ang:.0f} deg', s, R, t, e, src))
    return out


def samples_bary(V, F, step):
    """tri_samples' points as (triangle, barycentric) (they map onto another low of the same topology)"""
    tri, bary = [], []
    for t, f in enumerate(F):
        p = V[f]
        e = max(np.linalg.norm(p[1] - p[0]), np.linalg.norm(p[2] - p[1]), np.linalg.norm(p[0] - p[2]))
        m = max(1, int(math.ceil(e / step)))
        ii, jj = np.meshgrid(np.arange(m + 1), np.arange(m + 1))
        sel = ii + jj <= m
        a_, b_ = ii[sel] / m, jj[sel] / m
        tri.append(np.full(len(a_), t))
        bary.append(np.column_stack([1.0 - a_ - b_, a_, b_]))
    if not tri:
        return np.zeros(0, np.int64), np.zeros((0, 3))
    return np.concatenate(tri), np.concatenate(bary)


def context_score(prog_all, p, q, Up, src, s, step=CTX_STEP):
    """C5-UV b: how differently a correspondence lays the primary's surface into the member's surroundings: samples
    on p's unclipped low (about `step` apart, area-weighted) and their images on q; at each and CTX_OFFS above it along
    its outward normal (q's x s) the signed distance to every OTHER piece of the machine (the assembled bake program less
    the piece's own primitive), q's / s, both clipped to +-CTX_CLIP; the mean |difference| (m, the primary's units).
    What the bake's AO and cavity rays meet near a surface is what its texels hold: a turned map that puts a face's
    open side on a face that looks into a neighbour scores high"""
    names = prog_all.names
    pp_, pq_ = CL.prim_of_piece(p, names), CL.prim_of_piece(q, names)
    oth_p, oth_q = CL.subset_program(prog_all, {pp_}), CL.subset_program(prog_all, {pq_})
    own_p = CL.subset_program(prog_all, {nm for nm in names if nm != pp_})
    own_q = CL.subset_program(prog_all, {nm for nm in names if nm != pq_})
    Pp, Pq, Np, Nq, W = [], [], [], [], []
    for a in Up:
        tri, bary = samples_bary(a['V'], a['F'], step)
        if not len(tri):
            continue
        Pp.append(at(a['V'], a['F'], tri, bary))
        Pq.append(at(src[a['piece']], a['F'], tri, bary))
        Np.append(tri_normals(a['V'], a['F'])[tri])
        Nq.append(tri_normals(src[a['piece']], a['F'])[tri])
        ar = 0.5 * np.linalg.norm(np.cross(a['V'][a['F'][:, 1]] - a['V'][a['F'][:, 0]],
                                           a['V'][a['F'][:, 2]] - a['V'][a['F'][:, 0]]), axis=1)
        W.append(ar[tri] / np.maximum(np.bincount(tri, minlength=len(a['F']))[tri], 1))
    Pp, Pq, Np, Nq, W = (np.concatenate(x) for x in (Pp, Pq, Np, Nq, W))
    for P_, N_, own, sc in ((Pp, Np, own_p, 1.0), (Pq, Nq, own_q, s)):
        e_ = 0.05e-3 * sc                    # outward: the side where the piece's own field grows
        out_ = np.asarray(own.eval(P_ + e_ * N_), np.float64) >= np.asarray(own.eval(P_ - e_ * N_), np.float64)
        N_[~out_] *= -1.0
    diff = np.zeros(len(Pp))
    for h in CTX_OFFS:
        dp = np.clip(np.asarray(oth_p.eval(Pp + h * Np), np.float64), -CTX_CLIP, CTX_CLIP)
        dq = np.clip(np.asarray(oth_q.eval(Pq + h * s * Nq), np.float64) / s, -CTX_CLIP, CTX_CLIP)
        diff += np.abs(dp - dq) / len(CTX_OFFS)
    return float((W * diff).sum() / max(W.sum(), 1e-30))


def visible_area(ctx, spec, progs_bake, prog_all, step=0.25e-3):
    """C5-UV b: a spec's visible surface (its own design's low, clipped in its place; its samples outside every other
    piece by VISIBLE), m2: which of two equal pieces leads (its twin's visible surface lies inside its own, so the twin
    reads only texels it sees: the containment test's direction)"""
    tot = 0.0
    for it in ctx.own_final(spec, None, progs_bake):
        P, tri, w = tri_samples(it['V'], it['F'], step)
        if not len(P):
            continue
        prim = CL.prim_of_piece(it['piece'], prog_all.names)
        others = CL.subset_program(prog_all, {prim}) if prim is not None else prog_all
        tot += float(w[np.asarray(others.eval(P)) > VISIBLE].sum())
    return tot


def match(ctx, p, q, tp, Up, by_spec, prog_all):
    """C5-UV b: the spec q as a member of primary p, or why not: (member dict, None) or (None, why). q is rebuilt on
    p's topology; one element at two joints (family_of equal) keeps the index order (C5d's carry), any other pair
    takes the best of its correspondences by context_score (the index order unless another scores under CTX_TIE of
    it). The member: spec, k, s, R, t, resid, rel, size, corr (the map's label), context (its score, m; None for the
    index order of one element), src (the carry's vertex map), unclipped (q's low on p's topology)"""
    Uq = ctx.unclipped(q, tp)
    sig = lambda U: [(len(a['V']), len(a['F'])) for a in U]
    if sorted(sig(Uq)) != sorted(sig(Up)):
        return None, 'topology'
    same = family_of(p) == family_of(q)
    if same and [(spec_suffix(a['piece']), len(a['V']), len(a['F'])) for a in Uq] != \
            [(spec_suffix(a['piece']), len(a['V']), len(a['F'])) for a in Up]:
        return None, 'topology'
    Pq = np.concatenate([a['V'] for a in Uq])
    size = float(np.ptp(Pq, axis=0).max())
    cands = correspondences(Up, Uq, size, index_only=same)
    if not cands:
        if sig(Uq) == sig(Up):
            s, R, t, e = umeyama(np.concatenate([a['V'] for a in Up]), Pq)
            return None, f'residual {e * 1e3:.3f} mm = {e / size:.3f} of {size * 1e3:.2f} mm'
        return None, 'no correspondence within the residual bar'
    score = None
    if len(cands) > 1 or not same:
        sc = [context_score(prog_all, p, q, Up, c[5], c[1]) for c in cands]
        eff = [v * (CTX_TIE if c[0] == 'index' else 1.0) for v, c in zip(sc, cands)]
        i = int(np.argmin(eff))
        score = sc[i]
    else:
        i = 0
    lab, s, R, t, e, src = cands[i]
    return dict(spec=q, k=joint_of(q), s=s, R=R, t=t, resid=e, rel=e / size, size=size, corr=lab, context=score,
                src=src, unclipped=Uq, n_corr=len(cands)), None


def plan_groups(ctx, by_spec, refused=None, log=print, prog_all=None, progs_bake=None, prefer=(), memo=None):
    """the classes and their groups: {class label: [group]}, a group dict(primary, k, topo, label, members [match()'s
    dicts], refused [(spec, why)]). C5-UV b: a class is every stackable spec of one kind, region and primitive type
    (spec_class), whatever its name; taken by texel need (between equal needs the preferred, then the most visible
    surface: visible_area), the largest is a group's primary and every other spec that match() accepts its member;
    refused: {(member, primary): why} pairs an earlier pass turned down (the member then joins a later group of its
    class, under the largest of the refused: the clearance floor's knuckles 20-22 together); prefer: specs to lead
    among equals (a twin the containment test wants as the primary); memo: {(primary, member): match()} across passes"""
    refused = refused or {}
    memo = {} if memo is None else memo
    classes = {}
    for spec in by_spec:
        if family_of(spec) is not None and ctx.kind(spec) is not None:
            classes.setdefault(spec_class(ctx, spec, by_spec), []).append(spec)
    need = {s_: need_of(by_spec[s_]) for ss in classes.values() for s_ in ss}
    vis = {}

    def visible(s_):
        if s_ not in vis:
            vis[s_] = visible_area(ctx, s_, progs_bake, prog_all) if progs_bake is not None else 0.0
        return vis[s_]
    out = {}
    for ck, specs in classes.items():
        specs = sorted(specs, key=lambda s_: -need[s_])
        order, i = [], 0
        while i < len(specs):                          # equal needs (the twins): the preferred, then the most visible
            j = i + 1
            while j < len(specs) and need[specs[j]] >= need[specs[i]] * (1.0 - 1e-9):
                j += 1
            run = specs[i:j]
            if len(run) > 1:
                run = sorted(run, key=lambda s_: (s_ not in prefer, -visible(s_), s_))
            order += run
            i = j
        rest, groups = order, []
        while rest:
            p = rest[0]
            tp = ctx.topology(p)
            Up = ctx.unclipped(p)
            feat_p = sorted({spec_suffix(it['piece']) for it in by_spec[p]})
            g = dict(primary=p, k=joint_of(p), topo=tp, members=[], refused=[])
            left = []
            for q in rest[1:]:
                why = refused.get((q, p))
                if why is None and ctx.kind(p) == 'shell' and \
                        sorted({spec_suffix(it['piece']) for it in by_spec[q]}) != feat_p:
                    why = 'features (chamfers)'
                if why is None:
                    if (p, q) not in memo:
                        memo[(p, q)] = match(ctx, p, q, tp, Up, by_spec, prog_all)
                    m, why = memo[(p, q)]
                    if m is not None:
                        g['members'].append(m)
                        continue
                g['refused'].append((q, why))
                left.append(q)
            g['label'] = ' | '.join(sorted({family_of(s_) for s_ in [p] + [m['spec'] for m in g['members']]}))
            groups.append(g)
            rest = left
        out[f'{ck[0]} {"/".join(ck[1])} {ck[2]}'] = groups
    return out


# ============================================================================================ the carry
def carry(final_p, src_p, src_q):
    """the primary's final islands carried onto a member: each vertex located on its source unclipped island (same
    name) of the primary, read at the same triangle and barycentric on the member's (same topology). src_*: {island
    name: (V, F)}. Returns [(V, worst on-mesh error)] per final island"""
    out = []
    for it in final_p:
        Vs, Fs = src_p[it['piece']]
        Vq = src_q[it['piece']]
        tri, bary, pd, ou = locate(it['V'], Vs, Fs)
        err = float(np.max(pd + ou)) if len(pd) else 0.0
        out.append((at(Vq, Fs, tri, bary), err))
    return out


def stack_islands(ctx, groups, by_spec, final, unclipped_own, log=print):
    """every member's islands: its primary's final islands carried onto it. final: {spec: [final islands]} of the
    primaries (clipped, oriented); unclipped_own: {spec: [islands]} the primaries' unclipped lows (their topology).
    Returns {member spec: dict(islands, primary, s, R, t, resid, rel, carry_err)}"""
    out = {}
    for f, gs in groups.items():
        for g in gs:
            if not g['members']:
                continue
            p, kp = g['primary'], g['k']
            Up = unclipped_own[p]
            src_p = {it['piece']: (it['V'], it['F']) for it in Up}
            # a shell's chamfer islands (built from its cut points: not on any unclipped island of their own name):
            # their rim on the shell's unclipped islands (its bands and its proximal end face: the chamfer plane cuts
            # both), their centre the rim's mean (as cyborg_limb._fan builds them)
            bands = [it for it in Up if ctx.kind(p) == 'shell']
            for m in g['members']:
                q, kq = m['spec'], m['k']
                Uq = m.get('unclipped') or ctx.unclipped(q, g['topo'])
                # C5-UV b: the member's positions in the primary's vertex order by its correspondence (match(): the
                # index order, or a turned map for a twin of another name)
                src_q = m.get('src') or {a['piece']: b['V'] for a, b in zip(Up, Uq)}
                # the member's unclipped islands use the PRIMARY's triangulation (its own may break a quad's tie the
                # other way): same vertices, the primary's faces
                isl = []
                worst = 0.0
                for it in final[p]:
                    nm = it['piece']
                    if nm.endswith(' chamfer') and nm not in src_p:
                        Vb = np.concatenate([b['V'] for b in bands])
                        Fb = np.concatenate([b['F'] + o_ for b, o_ in zip(bands, np.cumsum([0] + [len(b['V'])
                                                                                                  for b in bands])[:-1])])
                        Vqb = np.concatenate([src_q[b['piece']] for b in bands])
                        rim = it['V'][1:]
                        tri, bary, pd, ou = locate(rim, Vb, Fb)
                        rq = at(Vqb, Fb, tri, bary)
                        Vn = np.vstack([rq.mean(0)[None], rq])
                        worst = max(worst, float(np.max(pd + ou)))
                        assert np.allclose(it['V'][0], it['V'][1:].mean(0), atol=1e-12), f'{nm}: not a centred fan'
                    else:
                        Vs, Fs = src_p[nm]
                        tri, bary, pd, ou = locate(it['V'], Vs, Fs)
                        Vn = at(src_q[nm], Fs, tri, bary)
                        worst = max(worst, float(np.max(pd + ou)) if len(pd) else 0.0)
                    own = by_spec[q][0] if by_spec.get(q) else None
                    isl.append(dict(it, V=Vn, F=it['F'].copy(), UV=it['UV'].copy(), piece=carry_name(nm, p, q),
                                    smooth=carry_name(it.get('smooth', nm), p, q), bone=(own['bone'] if own else
                                                                                        it['bone'] - kp + kq),
                                    body=(own['body'] if own else it['body']), dens=it['dens'] / m['s'],
                                    stacked_on=None, inst=dict(primary=p, k=kq, s=m['s'])))
                    if 'prim' in it:
                        isl[-1]['prim'] = carry_name(it['prim'], p, q)
                out[q] = dict(islands=isl, primary=p, s=m['s'], R=m['R'], t=m['t'], resid=m['resid'], rel=m['rel'],
                              carry_err=worst, unclipped=Uq, src=src_q, corr=m.get('corr', 'index'),
                              context=m.get('context'))
    return out


# ============================================================================================ the pack
TURN_GAIN = 0.10            # C5-UV b: an island is turned off its own axes only for a box at least this much smaller
                            # (min_box_turn took any gain: a can's cap, a fan with a vertex on its own u axis, turned
                            # 30 deg (a hexagon, for a box no smaller) and the texture tier's marks on it, the four
                            # bolt dots in the knuckle's axes, stood on a turned texel grid: the C5d check's "cross
                            # recess turned ~30 deg"). An island carrying marks keeps its own axes whatever the gain
                            # (pack(): an octagon's cap turned 22.5 deg boxes 14.6 % smaller and passes this bar)


def min_box_turn(UV):
    """the island's UVs turned so its bounding box is the smallest any turn gives (rotating calipers over its convex
    hull's edges): a curled bevel piece or a diagonal strip packs in a tighter box (cyborg_limb.pack_rect tries only
    the quarter turn). The texel density is unchanged (a rotation); the tangents follow the packed UVs. C5-UV b: kept on
    its own axes (or a quarter turn of them) unless the turn saves TURN_GAIN of the box"""
    from scipy.spatial import ConvexHull
    P = np.asarray(UV, np.float64)
    if len(P) < 3 or np.ptp(P[:, 0]) < 1e-12 or np.ptp(P[:, 1]) < 1e-12:
        return P
    try:
        H = P[ConvexHull(P).vertices]
    except Exception:
        return P
    best, R_best = None, np.eye(2)
    for i in range(len(H)):
        e = H[(i + 1) % len(H)] - H[i]
        n = np.linalg.norm(e)
        if n < 1e-15:
            continue
        c, s = e / n
        R = np.array([[c, s], [-s, c]])
        Q = H @ R.T
        a = np.ptp(Q[:, 0]) * np.ptp(Q[:, 1])
        if best is None or a < best - 1e-18:
            best, R_best = a, R
    if best is None or best > (1.0 - TURN_GAIN) * float(np.ptp(H[:, 0]) * np.ptp(H[:, 1])):
        return P
    return P @ R_best.T


ORDERS = (lambda b_: (-b_[3], -b_[2]), lambda b_: (-b_[2] * b_[3], -b_[3]), lambda b_: (-max(b_[2], b_[3]), -b_[3]),
          lambda b_: (-(b_[2] + b_[3]), -b_[3]))


def pack_rect(uvs, scales, pads, W, H):
    """cyborg_limb.pack_rect with a gutter per island (a stacked primary's wider) and a better skyline: over a W-wide
    sheet, each island placed where its top lands lowest of its two orientations (laid flat or stood up), the islands
    taken in each of ORDERS (tallest, largest, longest, widest first) and the order that uses the fewest rows kept.
    Returns UVs in canvas units (x / W, y / W) and the height used (texels)"""
    from scipy.ndimage import maximum_filter1d
    boxes = []
    for i, (Uu, s, pad) in enumerate(zip(uvs, scales, pads)):
        T = (Uu - Uu.min(0)) * s
        pd = pad if (T.max() >= 32.0 or pad > PAD_STACKED) else min(pad, 2 if pad <= PAD else 4)
        w, h = T.max(0) + 2 * pd
        if h > w:
            T = np.column_stack([T[:, 1], T.max(0)[0] - T[:, 0]])
            w, h = h, w
        boxes.append((i, T, int(np.ceil(w)), int(np.ceil(h)), pd))
    best = None
    for key in ORDERS:
        sky = np.zeros(W, np.int64)
        out = [None] * len(uvs)
        for i, T, w, h, pd in sorted(boxes, key=key):
            if w > W:
                raise ValueError(f'island {i} ({w}x{h} texels) wider than the sheet')
            pick = None
            for turn, (ww, hh) in enumerate(((w, h), (h, w))):
                if ww > W:
                    continue
                m = maximum_filter1d(sky, size=ww, mode='constant', cval=1 << 40, origin=-(ww // 2))[:W - ww + 1]
                x0 = int(np.argmin(m))
                y0 = int(m[x0])
                if pick is None or (y0 + hh, y0) < (pick[0] + pick[1], pick[0]):
                    pick = (y0, hh, x0, ww, turn)
            y0, hh, x0, ww, turn = pick
            Tt = T if turn == 0 else np.column_stack([T.max(0)[1] - T[:, 1], T[:, 0]])
            sky[x0:x0 + ww] = y0 + hh
            out[i] = (Tt + np.array([x0 + pd, y0 + pd])) / W
        if best is None or int(sky.max()) < best[1]:
            best = (out, int(sky.max()))
    return best


def _boxes(uvs, scales, pads):
    """each island's texel layout (laid flat) and its padded box (w, h) and gutter, as pack_rect makes them"""
    out = []
    for Uu, s, pad in zip(uvs, scales, pads):
        T = (Uu - Uu.min(0)) * s
        pd = pad if (T.max() >= 32.0 or pad > PAD_STACKED) else min(pad, 2 if pad <= PAD else 4)
        w, h = T.max(0) + 2 * pd
        if h > w:
            T = np.column_stack([T[:, 1], T.max(0)[0] - T[:, 0]])
            w, h = h, w
        out.append((T, int(np.ceil(w)), int(np.ceil(h)), pd))
    return out


def maxrects(wh, W, H, order):
    """MAXRECTS, best short side fit (Jylanki 2010): every box (w, h) into the W x H sheet, laid flat or stood up,
    each into the free rectangle that leaves the shortest side over; the free rectangles split round every placed box
    and pruned of the ones another contains. Returns (x, y, turned) per box, or None when one does not fit"""
    F = np.array([[0, 0, W, H]], np.int64)
    out = np.zeros((len(wh), 3), np.int64)
    big = np.int64(1 << 40)
    for i in order:
        w, h = int(wh[i][0]), int(wh[i][1])
        best = None
        for rot, (bw, bh) in enumerate(((w, h), (h, w))):
            ok = (F[:, 2] >= bw) & (F[:, 3] >= bh)
            if not ok.any():
                continue
            ss = np.minimum(F[:, 2] - bw, F[:, 3] - bh)
            ls = np.maximum(F[:, 2] - bw, F[:, 3] - bh)
            sc = np.where(ok, ss * (W + H + 1) + ls, big)
            j = int(np.argmin(sc))
            if best is None or sc[j] < best[0]:
                best = (sc[j], j, rot, bw, bh)
        if best is None:
            return None
        _, j, rot, bw, bh = best
        x, y = int(F[j, 0]), int(F[j, 1])
        out[i] = (x, y, rot)
        fx, fy, fw, fh = F[:, 0], F[:, 1], F[:, 2], F[:, 3]
        hit = (fx < x + bw) & (fx + fw > x) & (fy < y + bh) & (fy + fh > y)
        S, keep = F[hit], F[~hit]
        new = []
        for sx, sy, sw, sh in S:
            if x > sx:
                new.append((sx, sy, x - sx, sh))
            if x + bw < sx + sw:
                new.append((x + bw, sy, sx + sw - (x + bw), sh))
            if y > sy:
                new.append((sx, sy, sw, y - sy))
            if y + bh < sy + sh:
                new.append((sx, y + bh, sw, sy + sh - (y + bh)))
        N = np.array(new, np.int64).reshape(-1, 4)
        if len(N):
            # a new rectangle another (kept or new) contains goes; a kept one a new one contains goes
            allr = np.vstack([keep, N])
            cont = lambda a, b: ((a[:, None, 0] >= b[None, :, 0]) & (a[:, None, 1] >= b[None, :, 1]) &
                                 (a[:, None, 0] + a[:, None, 2] <= b[None, :, 0] + b[None, :, 2]) &
                                 (a[:, None, 1] + a[:, None, 3] <= b[None, :, 1] + b[None, :, 3]))
            cn = cont(N, allr)
            idx = np.arange(len(N))
            cn[idx, len(keep) + idx] = False
            # (two equal new rectangles: keep the first)
            same = cont(N, N) & cont(N, N).T
            dup = np.triu(same, 1).any(0)
            drop_n = (cn & ~np.hstack([np.zeros((len(N), len(keep)), bool), same]) ).any(1) | dup
            N = N[~drop_n]
            if len(keep) and len(N):
                drop_k = cont(keep, N).any(1)
                keep = keep[~drop_k]
        F = np.vstack([keep, N]) if len(N) else keep
        if not len(F):
            F = np.zeros((0, 4), np.int64)
    return out


def pack_maxrects(uvs, scales, pads, W, H):
    """the islands' boxes by MAXRECTS into W x 0.99 H (the orders of ORDERS tried, the first that fits kept): UVs in
    canvas units and the rows used, or raises ValueError when no order fits"""
    bx = _boxes(uvs, scales, pads)
    wh = [(w, h) for _, w, h, _ in bx]
    Hc = int(0.99 * H)
    for key in ORDERS:
        order = sorted(range(len(bx)), key=lambda i: key((i, None, wh[i][0], wh[i][1])))
        pl = maxrects(wh, W, Hc, order)
        if pl is None:
            continue
        out = []
        top = 0
        for (T, w, h, pd), (x, y, rot) in zip(bx, pl):
            Tt = T if rot == 0 else np.column_stack([T.max(0)[1] - T[:, 1], T[:, 0]])
            out.append((Tt + np.array([x + pd, y + pd])) / W)
            top = max(top, y + (h if rot == 0 else w))
        return out, top
    raise ValueError('maxrects: no order fits')


def pack(isl, pads, sizes=SIZES, px_floor=PX_TODAY, log=print):
    """the smallest set of `sizes` that holds every island at px_floor or more (its height used at most 99 %), the
    density raised as far as that set holds. Writes each island's 'UVp'; returns (px, (W, H), height share, trials)"""
    from eidoverse.bestiary.forge import uv as U
    dens = [U.island_density(it['V'], it['F'], it['UV']) for it in isl]
    # C5-UV b: an island carrying the texture tier's marks (CL.MARK_REGIONS: the drums', cans', yokes', discs' and
    # clamps' bolt dots, sockets, lamps and rims, painted per texel) keeps its own axes, the packers' quarter turns
    # only: turned, its marks stand on a turned texel grid (marks_drawn_check reads them as painted)
    uvs = [np.asarray(it['UV'], np.float64) if CL.REGIONS[it['region']] in CL.MARK_REGIONS else min_box_turn(it['UV'])
           for it in isl]
    sc = lambda px_: [px_ * it['dens'] / max(d, 1e-12) for it, d in zip(isl, dens)]
    trials = []

    def attempt(px_, W, H):
        """MAXRECTS into W x 0.99 H, else the skyline: (packed, rows used, packer) or None"""
        try:
            p_, u_ = pack_maxrects(uvs, sc(px_), pads, W, H)
            return p_, u_, 'maxrects'
        except ValueError:
            pass
        try:
            p_, u_ = pack_rect(uvs, sc(px_), pads, W, H)
        except ValueError:
            return None
        return (p_, u_, 'skyline') if u_ <= 0.99 * H else None
    for W, H in sizes:
        try:
            _, u_sky = pack_rect(uvs, sc(px_floor), pads, W, H)
        except ValueError:
            u_sky = None
        r0 = attempt(px_floor, W, H)
        trials.append((W, H, u_sky, r0 is not None))
        if r0 is None:
            continue
        best = (px_floor,) + r0
        lo, hi = px_floor, px_floor * 1.6
        for _ in range(10):
            mid = 0.5 * (lo + hi)
            r2 = attempt(mid, W, H)
            if r2 is not None:
                lo, best = mid, (mid,) + r2
            else:
                hi = mid
        px, packed, used, how = best
        for it, pk in zip(isl, packed):
            it['UVp'] = pk
        log(f'[cyborg_stack] pack ({how}): {len(isl)} islands on a {W} x {H} set at {px:.0f} px/m (floor '
            f'{px_floor:.0f}), height used {used} of {H}; tried ' + ', '.join(
                f'{w_}x{h_}: ' + ('holds' if ok_ else 'does not hold') + f' at the floor (the skyline alone '
                f'{u_} rows)' for w_, h_, u_, ok_ in trials))
        return px, (W, H), used / H, trials
    raise ValueError(f'[cyborg_stack] no set of {sizes} holds the islands at {px_floor:.0f} px/m: {trials}')


def deep_hidden(bake_isl, prim_specs, size, prog_all):
    """the texels (image order, a size^2 canvas) of the stacked PRIMARIES' islands the bake will hide and the material
    pass will not mend: the texel centre's low point covered by a neighbour (deeper than the bake's COVER_EPS inside
    another piece of the machine, the bake's highs) and more than 3 texels from every seen texel of its island (the
    material pass lends a hidden texel within 3 its nearest seen texel's AO and cavity: C5c's rule)"""
    from scipy import ndimage
    ids = np.full((size, size), -1, np.int64)
    P = np.zeros((size, size, 3))
    for i, it in enumerate(bake_isl):
        if spec_of(it['piece']) not in prim_specs:
            continue
        uvt = np.column_stack([it['UVp'][:, 0] * size - 0.5, (1.0 - it['UVp'][:, 1]) * size - 0.5])
        for f in it['F']:
            p = uvt[f]
            x0, x1 = int(max(0, math.floor(p[:, 0].min()))), int(min(size - 1, math.ceil(p[:, 0].max())))
            y0, y1 = int(max(0, math.floor(p[:, 1].min()))), int(min(size - 1, math.ceil(p[:, 1].max())))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
            if abs(d) < 1e-12:
                continue
            l0 = ((p[1, 1] - p[2, 1]) * (gx - p[2, 0]) + (p[2, 0] - p[1, 0]) * (gy - p[2, 1])) / d
            l1 = ((p[2, 1] - p[0, 1]) * (gx - p[2, 0]) + (p[0, 0] - p[2, 0]) * (gy - p[2, 1])) / d
            l2 = 1.0 - l0 - l1
            m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            if not m.any():
                continue
            V3 = it['V'][f]
            ids[gy[m], gx[m]] = i
            P[gy[m], gx[m]] = l0[m, None] * V3[0] + l1[m, None] * V3[1] + l2[m, None] * V3[2]
    covered = np.zeros((size, size), bool)
    for i in np.unique(ids[ids >= 0]):
        msk = ids == i
        pr = CL.prim_of_piece(bake_isl[i]['piece'], prog_all.names)
        oth = CL.subset_program(prog_all, {pr}) if pr is not None else prog_all
        covered[msk] = oth.eval(P[msk]) < -CL.COVER_EPS
    vis = (ids >= 0) & ~covered
    d_v, (iy, ix) = ndimage.distance_transform_edt(~vis, return_indices=True)
    return covered & ((d_v > 3.0) | (ids[iy, ix] != ids))


# ============================================================================================ the asset
REPLAN = 10                 # passes at most: a member the containment test turns down is planned again (its pair refused;
                            # C5-UV b: so is one the stretch, cover or highs test turns down; a twin of equal need the
                            # containment test turns down is first tried as the primary, its pair swapped; C5f: so is one
                            # past the mip margin, and its re-plans need passes of their own: 6 -> 10, the private
                            # forge's cascade took 9 and its last could only un-stack the pitch lug 22 twins)


def stacked_asset(size=None, log=print):
    """cyborg_limb.make_asset with the repeats STACKED (the module notes): the CPU half. Returns make_asset's dict over
    the WHOLE low (every member's islands carried from its primary; 'isl', 'L' as exported, posed and gated) with
    A['stack'] (the groups, the members' records, the cover test, the pack) and A['bake'] (bake_view: the primaries and
    the unique pieces alone, what the bake, its gates and the material pass read). A pass whose containment test turns
    members down plans the groups again with those (member, primary) pairs refused, so they group among themselves
    (under the largest of them) instead of each packing alone; the last pass un-stacks whatever is still turned down"""
    refused, prefer, memo, swapped = {}, set(), {}, set()
    for n in range(REPLAN):
        A, fail = _stacked_asset(size, log, refused, last=n == REPLAN - 1, prefer=prefer, memo=memo)
        if not fail:
            A['stack']['passes'] = n + 1
            A['stack']['refused_pairs'] = refused
            A['stack']['preferred'] = sorted(prefer)
            return A
        # C5-UV b: a member turned down by a primary of EQUAL need (a twin of another name: the containment test reads
        # a direction, the visible surface that chose it only predicts one) leads next pass instead, once; a pair
        # turned down both ways is refused
        n_sw = 0
        for (q, p), why in fail.items():
            if why.endswith('[twin]') and (q, p) not in swapped and (p, q) not in swapped:
                swapped.add((q, p))
                prefer.discard(p)
                prefer.add(q)
                n_sw += 1
            else:
                refused[(q, p)] = why
        log(f'[cyborg_stack] pass {n + 1}: the containment test or the mip margin turned down {len(fail)} members ({n_sw} '
            f'twins to lead next pass); planning again')
    A['stack']['passes'] = REPLAN
    A['stack']['refused_pairs'] = refused
    A['stack']['preferred'] = sorted(prefer)
    return A


def _stacked_asset(size, log, refused, last, prefer=(), memo=None):
    chain = CL.arm_chain()
    lim = CL.motion_limits(chain)
    des = CL.design(chain, lim)
    isl0, shells = CL.build_low(chain, des, log=log)
    X0 = lambda b_: (chain['x'][CL.body_k(b_)], 0.0, 0.0)
    progs = {b_: CL.group_program(chain, des, b_, offset=X0(b_)) for b_ in des['bodies']}
    progs_bake = {b_: CL.group_program(chain, des, b_, offset=X0(b_), bake=True) for b_ in des['bodies']}
    progs_piece = {b_: CL.group_program(chain, des, b_, offset=X0(b_), bake=True, split=True) for b_ in des['bodies']}
    pb = CL.band_program(chain, des, offset=(chain['x'][CL.J0], 0.0, 0.0))
    ph = CL.hose_program(chain, des)
    ctx = Ctx(chain, des)
    order, by_spec = [], {}
    for it in isl0:
        s_ = spec_of(it['piece'])
        if s_ not in by_spec:
            order.append(s_)
            by_spec[s_] = []
        by_spec[s_].append(it)
    prog_all = CL.assembled_program(chain, des, bake=True)
    groups = plan_groups(ctx, by_spec, refused, log=log, prog_all=prog_all, progs_bake=progs_bake, prefer=prefer,
                         memo=memo)
    member_of = {m['spec']: g for gs in groups.values() for g in gs for m in g['members']}
    need = {s_: need_of(by_spec[s_]) for s_ in by_spec}
    # every piece but the members: its own islands (a shell's cut by its chamfers), clipped and oriented as make_asset
    own = [it for s_ in order if s_ not in member_of for it in by_spec[s_]]
    own = CL.clip_buried(own, progs_bake, log=log)
    own = CL.clip_nested(own, des, progs_bake, log=log)
    final = {}
    for it in own:
        final.setdefault(spec_of(it['piece']), []).append(it)
    pieces_o, pid_o = CL.island_pieces(own, progs_piece, des['bodies'])
    owns = {}

    def field_of_own(it, pieces=pieces_o):
        b_, p_ = pieces[it['pid']]
        if b_ in ('band', 'hose'):
            return pb if b_ == 'band' else ph
        if (b_, p_) not in owns:
            owns[(b_, p_)] = CL.own_program(progs_piece[b_], p_)
        return owns[(b_, p_)]
    for it, p_ in zip(own, pid_o):
        it['pid'] = int(p_)
    CL.orient_islands(own, field_of_own)
    # the primaries' unclipped lows (their own topology) and the carry onto every member
    unc = {g['primary']: ctx.unclipped(g['primary']) for gs in groups.values() for g in gs if g['members']}
    st = stack_islands(ctx, groups, by_spec, final, unc, log=log)
    # THE STRETCH (C5a's U4 on the member): the shared texels' density on each of its triangles over its primary's
    # island density; a member whose densest and sparsest triangle differ by more than U4's range (1/1.5 .. 1.5 about
    # its own density, so 2.25) or whose texels' shape p99 passes 4 is refused (the global residual alone admitted a
    # slender actuator on a stout one's texels, a small axle's oversized head); the rest take their measured density
    # (the factor c: about 1 / s, "the smaller copies simply get more density") as their islands' density factor
    stretch = {}
    for q, rec in st.items():
        rmax, rmin, shp, sparse = 0.0, np.inf, [], 1.0
        prim_isl = final[rec['primary']]
        for it_p, it_q in zip(prim_isl, rec['islands']):
            d_p = island_density(it_p['V'], it_p['F'], it_p['UV'])
            sv = tri_sv(it_q['V'], it_q['F'], it_q['UV'])
            if not len(sv):
                continue
            rmax, rmin = max(rmax, float(sv[:, 0].max() / d_p)), min(rmin, float(sv[:, 1].min() / d_p))
            shp.append(sv[:, 0] / np.maximum(sv[:, 1], 1e-12))
            # the member's SPARSEST direction (its triangles' smaller singular value, 5th percentile) over its
            # primary's own on the same texels: above 1 the member is coarser than its primary along some direction
            # (a longer, thinner rod on a stout one's strip), and assemble() scales the group's texels up by it
            sv_p = tri_sv(it_p['V'], it_p['F'], it_p['UV'])
            if len(sv_p):
                sparse = max(sparse, float(np.percentile(sv_p[:, 1], 5) / max(np.percentile(sv[:, 1], 5), 1e-12)))
        shp = np.concatenate(shp) if shp else np.ones(1)
        c = math.sqrt(rmax * rmin) if rmin < np.inf else 1.0 / rec['s']
        stretch[q] = dict(rmax=rmax, rmin=rmin, c=c, range=rmax / max(rmin, 1e-12), shape_p99=float(np.percentile(shp, 99)),
                          sparse=sparse,
                          ok=rmax / max(rmin, 1e-12) <= U4_RANGE and float(np.percentile(shp, 99)) <= 4.0)
        for it_p, it_q in zip(prim_isl, rec['islands']):
            it_q['dens'] = it_p['dens'] * c
    # THE COVER TEST: a member's own visible surface (its own design's low with its primary's topology: cut by its own
    # chamfers, clipped in its own place; outside every other piece of the machine at rest by VISIBLE, read on the BAKE
    # programs as the clips read them: no bores, so a trunnion in its lug is buried) lies on its carried low; else it is
    # UN-STACKED
    cover = {}
    for q, rec in st.items():
        if not stretch[q]['ok']:
            cover[q] = dict(visible_mm2=0.0, bad_mm2=0.0, worst_mm=0.0, hidden_mm2=0.0, ok=True, skipped='stretch')
            continue
        Uq = ctx.own_final(q, member_of[q]['topo'], progs_bake)
        Vc = np.concatenate([it['V'] for it in rec['islands']])
        Fc = np.concatenate([it['F'] + o_ for it, o_ in zip(rec['islands'], np.cumsum(
            [0] + [len(it['V']) for it in rec['islands']])[:-1])]) if rec['islands'] else np.zeros((0, 3), np.int64)
        bad, tot, worst = 0.0, 0.0, 0.0
        names = prog_all.names
        vs_t, vs_b, vs_w = [], [], []
        for it in Uq:
            P, tri, w = tri_samples(it['V'], it['F'], 0.25e-3)
            if not len(P):
                continue
            prim = CL.prim_of_piece(it['piece'], names)
            others = CL.subset_program(prog_all, {prim}) if prim is not None else prog_all
            vis = others.eval(P) > VISIBLE
            if not vis.any():
                continue
            tot += float(w[vis].sum())
            if len(Fc):
                t2, b2, pd, ou = locate(P[vis], Vc, Fc)
                miss = (pd + ou) > COVER_TOL
                bad += float(w[vis][miss].sum())
                if miss.any():
                    worst = max(worst, float((pd + ou)[miss].max()))
                vs_t.append(t2[~miss])
                vs_b.append(b2[~miss])
                vs_w.append(w[vis][~miss])
            else:
                bad += float(w[vis].sum())
        # (its visible samples' places on the carried low, for the containment test once the pack gives the UVs)
        rec['visible'] = (np.concatenate(vs_t) if vs_t else np.zeros(0, np.int64),
                          np.concatenate(vs_b) if vs_b else np.zeros((0, 3)), np.concatenate(vs_w) if vs_w else
                          np.zeros(0), Fc)
        cover[q] = dict(visible_mm2=tot * 1e6, bad_mm2=bad * 1e6, worst_mm=worst * 1e3, hidden_mm2=0.0,
                        ok=bad * 1e6 <= BAD_MM2)
    # THE HIGHS (the lead's call 1): the primary's true surface carried onto every member lands on the member's own
    # (highs_core); a member whose high carries what its primary's does not (or the reverse) is UN-STACKED too
    highs = highs_core({q: r for q, r in st.items() if cover[q]['ok'] and stretch[q]['ok']}, final, unc, progs_bake,
                       prog_all, log=log)
    why_un = {}
    for q in st:
        if not stretch[q]['ok']:
            why_un[q] = (f'stretch: its densest / sparsest triangle {stretch[q]["range"]:.2f} (U4 range {U4_RANGE:.2f}), '
                         f'texel shape p99 {stretch[q]["shape_p99"]:.2f}')
        elif not cover[q]['ok']:
            why_un[q] = (f'cover test: {cover[q]["bad_mm2"]:.3f} mm2 of its visible surface off the carried low (up to '
                         f'{cover[q]["worst_mm"]:.3f} mm)')
        elif not highs[q]['ok']:
            why_un[q] = (f'highs: its own relief {highs[q]["rel_p99"]:.3f} mm (p99, the primary\'s units) off the carried '
                         f'one' if highs[q].get('rel_ok', True) is False else
                         f'highs: its own high {highs[q]["f_p99"]:.3f} mm (p99) off the carried one')

    def unstack(qs):
        """the members qs back to their own islands (their build_low low, clipped and oriented as every piece is),
        packed and baked on their own"""
        log(f'[cyborg_stack] UN-STACKED: ' + '; '.join(f'{q} ({why_un[q]})' for q in qs))
        extra = [it for q in qs for it in by_spec[q]]
        extra = CL.clip_buried(extra, progs_bake, log=log)
        extra = CL.clip_nested(extra, des, progs_bake, log=log)
        # turned to face out by the same vote as every other island (make_asset's orient_islands, each island's own
        # piece's field): un-oriented, a shell's chamfer caps and proximal end faced inward and the bake missed them
        CL.orient_islands(extra, lambda it: CL.own_program(progs_piece[it['body']], it.get('prim') or CL.prim_of_piece(
            it['piece'], progs_piece[it['body']].names)))
        for it in extra:
            final.setdefault(spec_of(it['piece']), []).append(it)
        for q in qs:
            g = member_of.pop(q)
            g['members'] = [m for m in g['members'] if m['spec'] != q]
            g['refused'].append((q, why_un[q]))
            del st[q]
            highs.pop(q, None)

    boost = {}

    def assemble():
        """the whole low in build_low's order (each piece's own final islands, or its carried ones), the bake view's
        islands and pieces, the pack (the primaries' islands with the wider gutter) and the members' UVs from it"""
        isl = []
        for s_ in order:
            isl += st[s_]['islands'] if s_ in st else final.get(s_, [])
        is_member = np.array([s_ in st for s_ in (spec_of(it['piece']) for it in isl)])
        des['explode'] = CL.pack_explode(isl, des)
        bake_isl = [it for it, m in zip(isl, is_member) if not m]
        # THE LARGEST INSTANCE PER DIRECTION (the lead's call 3: the largest instance's density at least C5c's): a
        # stacked primary's texels scaled up by its group's largest 'sparse', so no member is coarser than its primary
        # along any direction (only where a member is longer than its primary somewhere: the Minsky rods and
        # actuators); the members' density factors follow their primary's
        boost.clear()
        for gs in groups.values():
            for g in gs:
                if g['members']:
                    boost[g['primary']] = max([1.0] + [stretch[m['spec']]['sparse'] for m in g['members']])
        for it in bake_isl:
            it.setdefault('dens0', it['dens'])
            it['dens'] = it['dens0'] * boost.get(spec_of(it['piece']), 1.0)
        for q, rec in st.items():
            for it_q in rec['islands']:
                it_q.setdefault('dens0', it_q['dens'])
                it_q['dens'] = it_q['dens0'] * boost.get(rec['primary'], 1.0)
        pieces, isl_pid = CL.island_pieces(bake_isl, progs_piece, des['bodies'])
        for it, p_ in zip(bake_isl, isl_pid):
            it['pid'] = int(p_)
        prim_specs = {g['primary'] for gs in groups.values() for g in gs if g['members']}
        # a stacked primary's gutter: its smallest member (scale s) shows its texels log2(1 / s) mips higher, so its
        # islands keep PAD texels clean that many mips further: PAD + ceil(log2(1 / s_min)), at most PAD_STACKED
        # (C5-UV b: or the gutter margin_check chose for it, when widening it cost fewer texels than un-stacking)
        s_min = {g['primary']: min(m['s'] for m in g['members']) for gs in groups.values() for g in gs if g['members']}
        pad_of = {p_: int(min(PAD_STACKED, PAD + max(0, math.ceil(math.log2(1.0 / max(s_, 1e-6)) - 1e-9))))
                  for p_, s_ in s_min.items()}
        pad_of.update({p_: v_ for p_, v_ in widen.items() if p_ in pad_of})
        # (C5f, the lead's call 3: the rubber band's strip its own wide gutter)
        pads = [pad_of.get(spec_of(it['piece']), PAD_BAND if CL.REGIONS[it['region']] == 'band' else PAD)
                for it in bake_isl]
        pk = pack(bake_isl, pads, sizes=SIZES if size is None else (tuple(size),), log=log)
        uvp = {}
        for it in bake_isl:
            uvp.setdefault(it['piece'], []).append(it['UVp'])
        for q, rec in st.items():
            seen = {}
            for it in rec['islands']:
                nm = primary_name(it['piece'], q, rec['primary'])
                i_ = seen.get(nm, 0)
                seen[nm] = i_ + 1
                it['UVp'] = uvp[nm][i_].copy()
        return isl, is_member, bake_isl, pieces, isl_pid, prim_specs, pads, pk
    unstack_list = sorted(why_un)
    if unstack_list and not last:
        # C5-UV b: a member a test turns down (its stretch, the cover test, the highs) is planned again with its pair
        # refused, as the containment test's are: in its class it may join a later group (pitch axles 20-22, off yaw
        # axle 16's carried low, together under pitch axle 20 as in C5d) instead of packing alone
        return None, {(q, st[q]['primary']): why_un[q] for q in unstack_list}
    if unstack_list:
        unstack(unstack_list)
    widen, margins = {}, {}

    def fix_margins(replan=False):
        """THE MIP MARGIN (C5-UV b, the lead's call 3): a member at scale s reads its primary's texels log2(1 / s) mips
        coarser than the primary does at the same view; the dilated gutter keeps the primary's own colour only up to
        the mip its margin holds (margin_check, C5f: less MIP_HEADROOM). A member past it is UN-STACKED (its own
        islands, packed and baked on its own) when that costs fewer texels than widening its primary's gutter, else the
        primary's gutter is widened; the set packed again and measured again. C5f (the lead's call 4): with replan (a
        pass that may plan again) the members past it are returned as refused (member, primary) pairs instead, so the
        next pass groups a class's fall-outs among themselves (under the largest of them) where their own margin holds
        them. Returns (assemble()'s, None) or (None, the refusals)"""
        nonlocal margins
        state = assemble()
        for it_m in range(3):
            mc = margin_check(state[2], state[5], state[6], st, state[7], by_spec, progs_bake, des, ctx)
            margins = mc
            over = mc['over']
            if not over:
                break
            un_q, wid = [], {}
            for p_, r_ in over.items():
                if r_['unstack_texels'] <= r_['widen_texels']:
                    for q in r_['members']:
                        why_un[q] = (f'mip margin: it reads {p_}\'s texels {r_["offsets"][q]:.2f} mips coarser, past '
                                     f'the {r_["m_safe"]:.2f} its gutter holds (un-stacked: {r_["unstack_texels"]:.0f} '
                                     f'texels of their own against {r_["widen_texels"]:.0f} to widen {p_}\'s gutter to '
                                     f'{r_["pad_needed"]})')
                        un_q.append(q)
                else:
                    wid[p_] = r_['pad_needed']
            log(f'[cyborg_stack] the mip margin, pass {it_m + 1}: ' + '; '.join(
                f'{p_}: members {", ".join(r_["members"])} past {r_["m_safe"]:.2f} mips (margin {r_["margin"]:.2f}); '
                f'un-stacking them {r_["unstack_texels"]:.0f} texels, widening its gutter {r_["pad"]} -> '
                f'{r_["pad_needed"]} {r_["widen_texels"]:.0f} texels' for p_, r_ in over.items()))
            if un_q and replan:
                return None, {(q, st[q]['primary']): why_un.pop(q) for q in sorted(set(un_q))}
            if un_q:
                unstack(sorted(set(un_q)))
            widen.update(wid)
            state = assemble()
        return state, None
    state, refuse = fix_margins(replan=not last)
    if refuse:
        return None, refuse
    isl, is_member, bake_isl, pieces, isl_pid, prim_specs, pads, pk = state
    # THE CONTAINMENT (check_stacks' rule from the body's v2_bake, read before the bake): a member shows its primary's
    # texels through its carried UVs; none it SEES may be one the bake will hide on the primary beyond the material's
    # reach (covered there by a neighbour, more than 3 texels from every seen texel of its island: the material pass
    # lends a hidden texel its nearest seen texel's AO only within 3). A member that does is un-stacked, the set packed
    # again (a thinner tine's root on a small knuckle's disc or lug leaves open what the first cardan's tine covers)
    deep = deep_hidden(bake_isl, prim_specs, pk[1][0], prog_all)
    contain = {}
    for q, rec in st.items():
        t2, b2, w_, Fc = rec['visible']
        UVc = np.concatenate([it['UVp'] for it in rec['islands']])
        uv = at(UVc, Fc, t2, b2) if len(t2) else np.zeros((0, 2))
        xs = np.clip((uv[:, 0] * pk[1][0]).astype(np.int64), 0, pk[1][0] - 1)
        ys = np.clip(((1.0 - uv[:, 1]) * pk[1][0]).astype(np.int64), 0, pk[1][0] - 1)
        contain[q] = float(w_[deep[ys, xs]].sum()) * 1e6 if len(t2) else 0.0
        cover[q]['hidden_mm2'] = contain[q]
    fail = sorted(q for q, b in contain.items() if b > BAD_MM2)
    if fail:
        for q in fail:
            why_un[q] = (f'containment: {contain[q]:.3f} mm2 of its visible surface reads texels its primary\'s '
                         f'neighbours cover (baked hidden, beyond the material\'s 3-texel reach)')
        if not last:                         # planned again with these pairs refused (stacked_asset)
            twin = lambda q_: abs(need[q_] / max(need[st[q_]['primary']], 1e-30) - 1.0) < 1e-9
            return None, {(q, st[q]['primary']): f'containment against {st[q]["primary"]}: {contain[q]:.3f} mm2 of '
                                                 f'its visible surface reads texels that primary\'s neighbours cover'
                                                 + (' [twin]' if twin(q) else '') for q in fail}
        unstack(fail)
        isl, is_member, bake_isl, pieces, isl_pid, prim_specs, pads, pk = fix_margins()[0]
    unstack_list = sorted(why_un)
    px, set_, used, trials = pk
    # orientation of the members: the primary's winding carried; checked with the same vote (never flipped here)
    pieces_all, pid_all = CL.island_pieces(isl, progs_piece, des['bodies'])
    flips = []
    for it, p_ in zip(isl, pid_all):
        if spec_of(it['piece']) not in st:
            continue
        b_, p2 = pieces_all[p_]
        prog = pb if b_ == 'band' else ph if b_ == 'hose' else CL.own_program(progs_piece[b_], p2)
        V, F = it['V'], it['F']
        c = V[F].mean(1)
        fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
        if (np.einsum('ij,ij->i', fn, prog.normals(c)) < 0.0).sum() > 0.5 * len(F):
            flips.append(it['piece'])
    W, H = set_
    L = CL.low_arrays(isl, des)
    L['UV_tex'] = np.column_stack([L['UV'][:, 0], L['UV'][:, 1] * W / H])
    Lb = CL.low_arrays(bake_isl, des)
    Lb['UV_tex'] = np.column_stack([Lb['UV'][:, 0], Lb['UV'][:, 1] * W / H])
    Lb['pid'] = isl_pid[Lb['piece']]
    det, sizes_d = CL.details(chain, des, CL.PX_TARGET)
    det_all = map_details(ctx, det, st, unc)
    A = dict(chain=chain, lim=lim, des=des, isl=isl, L=L, px=px, used=used, size=W, set=(W, H), det=det_all,
             sizes=sizes_d, progs=progs, progs_bake=progs_bake, progs_piece=progs_piece, pieces=pieces_all,
             isl_pid=pid_all, own={}, band_prog=pb, hose_prog=ph)
    A['field_of'] = lambda it: CL.own_program(progs_piece[it['body']], it.get('prim') or CL.prim_of_piece(
        it['piece'], progs_piece[it['body']].names))
    A['stack'] = dict(groups=groups, members=st, cover=cover, highs=highs, stretch=stretch, unstacked=unstack_list,
                      why_unstacked=why_un, flips=flips, trials=trials, is_member=is_member, prim_specs=prim_specs,
                      isl0=len(isl0), pads=pads, ctx=ctx, unc=unc, boost=dict(boost), margins=margins,
                      widened=dict(widen))
    log('[cyborg_stack] the largest instance per direction: ' + (', '.join(
        f'{p_} x{b_:.3f}' for p_, b_ in sorted(boost.items()) if b_ > 1.0) or 'no primary scaled') +
        ' (its texels scaled up so no member of its group is coarser than it along any direction)')
    A['bake'] = bake_view(A, bake_isl, Lb, pieces, isl_pid)
    log(f'[cyborg_stack] {sum(len(g["members"]) for gs in groups.values() for g in gs)} pieces stacked on '
        f'{len(prim_specs)} primaries; islands {len(isl)} in the low, {len(bake_isl)} packed and baked; '
        f'{px:.0f} px/m on {W} x {H}; members\' islands the vote would turn: {len(flips)}')
    return A, None


def bake_view(A, bake_isl, Lb, pieces, isl_pid):
    """the asset as the bake, its gates and the material pass read it: the primaries' and the unique pieces' islands
    alone (their low, their pieces); the details carved into the body high every body's ('det_all'), the own-piece
    search's only the baked shells' and the collar's ('det')"""
    keep = {b_ for b_, p_ in pieces}
    det_b = {b_: g for b_, g in A['det'].items()
             if (b_, 'flange collar' if b_ == CL.bone_name(CL.J0) else f'shell {CL.body_k(b_)}') in set(pieces)}
    B = dict(A, isl=bake_isl, L=Lb, pieces=pieces, isl_pid=isl_pid, own={}, det=det_b, det_all=A['det'])
    B.pop('bake', None)
    B['_raster'] = None
    B['bodies_baked'] = keep
    return B


# ============================================================================================ the stack's gates
HIGH_TOL = 0.10e-3          # a primary's high carried onto a member lands within this of the member's own high (the
                            # wrong-surface gate's WS_TOL_D: what the bake itself is allowed off the true surface)
HIGH_DEG = 30.0             # and its normal within this (WS_TOL_A)
HIGH_REL = 0.05e-3          # C5-UV b: a member's relief at its own scale (d_q / s, the primary's units) within this of the
                            # primary's (p99 over its core samples, each island's median offset apart): half the
                            # wrong-surface tolerance, a third of a texel's height at the set's density


def _member_source(A, q):
    """a member's carry: its record, the primary's final islands (the bake view's), the primary's and the member's
    unclipped islands by the primary's island names"""
    S = A['stack']
    return _source(S['members'][q], S['unc'], [it for it in A['bake']['isl']
                                                 if spec_of(it['piece']) == S['members'][q]['primary']])


def _source(rec, unc, fin):
    p = rec['primary']
    Up = unc[p]
    src_p = {it['piece']: (it['V'], it['F']) for it in Up}
    src_q = rec.get('src') or {a['piece']: b['V'] for a, b in zip(Up, rec['unclipped'])}
    return rec, p, Up, src_p, src_q, fin


def highs_check(A, step=0.30e-3, log=print):
    """highs_core on the asset's stack (its gate's reading)"""
    S = A['stack']
    fin = {}
    for it in A['bake']['isl']:
        fin.setdefault(spec_of(it['piece']), []).append(it)
    return highs_core(S['members'], fin, S['unc'], A['progs_bake'],
                      CL.assembled_program(A['chain'], A['des'], bake=True), step=step, log=log)


def highs_core(members, fin_by_spec, unc, progs, prog_all, step=0.30e-3, log=print):
    """THE HIGHS under each member's carry (the lead's call 1): points of the primary's TRUE surface (its own piece's
    exact program; the bores and cuts its group carries), found from its final islands' samples along their normals,
    carried onto the member (the sample's barycentric place on the unclipped low, its height over the low scaled by
    the member's s along the member's normal), then read in the MEMBER's own piece program: |f| and the normal's turn
    against the carried one. A piece whose high carries a feature its low does not (a bolt, a slot) lands only under
    the right turn; the carry is the lows' own index-for-index correspondence, so there is one turn to test, and a
    lathe low's other whole steps are reported by turns_check. progs: the BAKE highs (the texels are baked from them:
    no bores, a lug's face whole). The bar: the CORE samples' |f| p99 within HIGH_TOL (the normals reported: the low's
    absolute 0.075 mm inset leaves a carried point that far off a small member's rounded box, where the field's
    gradient turns). Returns {member: dict(n, core, f_p99, f_max, deg_p99, deg_max, edge_f_max, within, ok)}

    C5-UV b (the lead's call 5: the features RELATIVE to each member's own scale): beside |f|, the RELIEF. At each core
    sample the primary's high stands d = -f_p over its low (its own piece's field at the low point: how deep the low
    point lies under the high), the member's own high d_q = -f_q over the corresponding point of its carried low; the
    relief error is d_q / s - d in the primary's units, less its median over the facet (the samples of one island whose
    low triangles share a plane: the low's absolute LOW_INSET, which does not scale with s, shifts a whole face alike,
    and a box's strip insets some faces and not others). An exact scaled copy reads 0 everywhere; a recess or a boss one
    high has and the other lacks, or one turned from where the other has it, stands out by its own depth wherever it
    lies, however small the member: rel_p99, rel_max and rel_area (the member's area, mm2 at its own scale, where the
    error passes HIGH_REL), the bar rel_p99 within HIGH_REL. ok needs both"""
    out = {}
    for q in sorted(members):
        rec, p, Up, src_p, src_q, fin = _source(members[q], unc, fin_by_spec[members[q]['primary']])
        kp, kq = joint_of(p), joint_of(q)
        fs, dg, cs, n_all = [], [], [], 0
        rl, rw = [], []
        for it in fin:
            nm = it['piece']
            if nm not in src_p:                      # a chamfer's planar cap: its rim lies on the bands (checked there)
                continue
            Vs, Fs = src_p[nm]
            P, tri, w = tri_samples(it['V'], it['F'], step)
            if not len(P):
                continue
            Nf = tri_normals(it['V'], it['F'])[tri]
            bp = it['body']
            names = progs[bp].names
            prim = CL.prim_of_piece(nm, names)
            if prim is None:
                continue
            # only what is SEEN (outside every other piece of the machine at rest, the bake's highs): a face the clips
            # keep under a neighbour (a neck's end in its tongue disc), a low chord inside a clamp's bore (behind the
            # hose) are never shown, by the primary or by any member
            pa = CL.prim_of_piece(nm, prog_all.names)
            vis = CL.subset_program(prog_all, {pa}).eval(P) > VISIBLE
            P, Nf = P[vis], Nf[vis]
            if not len(P):
                continue
            own_p = CL.own_program(progs[bp], prim)
            H, st = own_p.project(P, Nf, maxd=3.5e-3)
            ok = st < 2
            if not ok.any():
                continue
            P, H, Nf = P[ok], H[ok], Nf[ok]
            nh = own_p.normals(H)
            # the CORE samples: their hit lies on the face they came from (its high normal within 30 deg of the low
            # face's); the rest sit at a break or an edge the low does not carry (the wrong-surface gate's border band)
            nh_u = nh / np.maximum(np.linalg.norm(nh, axis=1, keepdims=True), 1e-20)
            core = (nh_u * Nf).sum(1) >= math.cos(math.radians(30.0))
            t2, b2, _, _ = locate(P, Vs, Fs)
            Np = tri_normals(Vs, Fs)[t2]
            Nq = tri_normals(src_q[nm], Fs)[t2]
            sg = np.where((Np * Nf).sum(1) < 0.0, -1.0, 1.0)[:, None]    # (orient_islands may have turned the
            Np, Nq = Np * sg, Nq * sg                                       # final island against its source)
            d = ((H - P) * Np).sum(1)
            Hq = at(src_q[nm], Fs, t2, b2) + (rec['s'] * d)[:, None] * Nq
            bq = rec['islands'][0]['body']
            prim_q = CL.prim_of_piece(carry_name(nm, p, q), progs[bq].names)
            own_q = CL.own_program(progs[bq], prim_q)
            f = np.abs(own_q.eval(Hq).astype(np.float64))
            # the relief at the member's own scale (C5-UV b): each high's depth over its own low point (its field there),
            # the member's / s against the primary's, each facet's median apart
            if core.any():
                Pq0 = at(src_q[nm], Fs, t2, b2)
                rr = (np.asarray(own_p.eval(P), np.float64) - np.asarray(own_q.eval(Pq0), np.float64) / rec['s'])[core]
                fk = np.unique(np.round(Np[core] * 50.0).astype(np.int64), axis=0, return_inverse=True)[1].reshape(-1)
                med = np.zeros(fk.max() + 1)
                for j_ in range(len(med)):
                    med[j_] = np.median(rr[fk == j_])
                rl.append(np.abs(rr - med[fk]))
                ar_ = np.linalg.norm(np.cross(src_q[nm][Fs[:, 1]] - src_q[nm][Fs[:, 0]],
                                              src_q[nm][Fs[:, 2]] - src_q[nm][Fs[:, 0]]), axis=1) * 0.5
                rw.append((ar_[t2] / np.maximum(np.bincount(t2, minlength=len(Fs))[t2], 1))[core])
            nq = own_q.normals(Hq)
            nc = nh @ rec['R'].T
            cosv = np.clip((nq * nc).sum(1) / np.maximum(np.linalg.norm(nq, axis=1) * np.linalg.norm(nc, axis=1),
                                                         1e-20), -1.0, 1.0)
            fs.append(f)
            dg.append(np.degrees(np.arccos(cosv)))
            cs.append(core)
            n_all += len(f)
        if not fs:
            out[q] = dict(n=0, core=0, f_p99=0.0, f_max=0.0, deg_p99=0.0, deg_max=0.0, edge_f_max=0.0, ok=True)
            continue
        f, g, c = np.concatenate(fs), np.concatenate(dg), np.concatenate(cs)
        fc, gc = (f[c], g[c]) if c.any() else (np.zeros(1), np.zeros(1))
        rl_ = np.concatenate(rl) if rl else np.zeros(1)
        rw_ = np.concatenate(rw) if rw else np.zeros(1)
        rel_p99 = float(np.percentile(rl_, 99))
        # the bar on the CORE samples' 99th percentile (their max and the edge samples' reported): a sample at a sharp
        # edge projects along its low normal onto the NEXT face (a pin head's shoulder, a thin collar's broken rim)
        out[q] = dict(n=n_all, core=int(c.sum()), f_p99=float(np.percentile(fc, 99)) * 1e3, f_max=float(fc.max()) * 1e3,
                      deg_p99=float(np.percentile(gc, 99)), deg_max=float(gc.max()),
                      edge_f_max=float(f[~c].max()) * 1e3 if (~c).any() else 0.0, within=float(np.mean(f <= HIGH_TOL)),
                      rel_p99=rel_p99 * 1e3, rel_max=float(rl_.max()) * 1e3,
                      rel_area=float(rw_[rl_ > HIGH_REL].sum()) * 1e6, rel_ok=bool(rel_p99 <= HIGH_REL),
                      ok=bool(np.percentile(fc, 99) <= HIGH_TOL and rel_p99 <= HIGH_REL))
    bad = [q for q, r in out.items() if not r['ok']]
    log(f'[cyborg_stack] HIGHS under the carry: {len(out)} members, {sum(r["n"] for r in out.values()):,} points of the '
        f'primaries\' true surfaces carried; |f| on the member\'s own high p99 / max '
        f'{max(r["f_p99"] for r in out.values()):.4f} / {max(r["f_max"] for r in out.values()):.4f} mm, normal p99 '
        f'{max(r["deg_p99"] for r in out.values()):.2f} deg; the relief at each member\'s own scale (the primary\'s '
        f'units, bar {HIGH_REL * 1e3:.2f} mm) p99 / max {max(r["rel_p99"] for r in out.values()):.4f} / '
        f'{max(r["rel_max"] for r in out.values()):.4f} mm -> ' + ('PASS' if not bad else f'FAIL {bad[:8]}'))
    return out


def turns_check(A, log=print):
    """the lead's call 2: a member of a LATHE family (a revolve spec) could take a whole-step turn about its axis so its
    primary's chips do not line up down the arm. A turn is only given where it maps the member's carried low onto
    itself (a buried face cut out of the low, a lug or a saddle sunk into it, moves with the turn otherwise: a hole
    where the primary was buried, a buried face where it shows) and the high onto itself. Per revolve group: the whole
    steps of its side count that keep the carried low's vertex set (within 1 um), and the reason when none does"""
    S = A['stack']
    ctx = S['ctx']
    out = {}
    for f0, gs in S['groups'].items():
        for g in gs:
            if not g['members']:
                continue
            f = g.get('label', f0)
            p = g['primary']
            if ctx.kind(p) not in ('knuckle', 'clamp') or g['topo'] is None:
                continue
            n = g['topo'].get('n') or g['topo'].get('ns')
            if ctx.kind(p) == 'knuckle':
                sp, o, k = ctx.spec[p]
                axis, c = CL.AX[sp['axis']], o + np.asarray(sp['c'], np.float64)
            else:
                cl = ctx.clamp[joint_of(p)]
                axis, c = CL.AX['x'], np.array([cl['x'], cl['y'], 0.0])
            fin = [it for it in A['bake']['isl'] if spec_of(it['piece']) == p]
            V = np.concatenate([it['V'] for it in fin]) - c
            from scipy.spatial import cKDTree
            tree = cKDTree(V)
            keep = []
            for j in range(1, n):
                a = 2.0 * math.pi * j / n
                K = np.array([[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]])
                Rj = np.eye(3) + math.sin(a) * K + (1.0 - math.cos(a)) * (K @ K)
                d, _ = tree.query(V @ Rj.T)
                if d.max() <= 1.0e-6:
                    keep.append(j)
            unc = sum(len(it['V']) for it in S['unc'][p])
            fv = sum(len(it['V']) for it in fin)
            out[f] = dict(primary=p, n=n, steps=keep, clipped=fv != unc,
                          why=None if keep else ('its low is cut by its neighbours (clip_buried / clip_nested / a sunk '
                                                 'piece): a turn moves the cut' if fv != unc else
                                                 'no whole step keeps its low'))
    log('[cyborg_stack] TURNS (whole steps keeping the carried low): ' + '; '.join(
        f'{f_}: ' + (f'steps {r["steps"]} of {r["n"]}' if r['steps'] else f'none ({r["why"]})') for f_, r in out.items()))
    return out


def hidden_check(A, res, step=0.25e-3, log=print):
    """after the bake (check_stacks' rule from the body's v2_bake): a member's VISIBLE surface (its own design, as the
    cover test reads it) reads its primary's texels through its carried UVs; none of them may be a texel the bake hid
    on the primary (buried or covered there: never baked as seen) or lie off every packed island. Per member the area
    (mm2) of such samples; at most BAD_MM2"""
    from scipy import ndimage
    S = A['stack']
    ctx = S['ctx']
    chain, des = A['chain'], A['des']
    prog_all = CL.assembled_program(chain, des, bake=True)
    size = A['bake']['size']
    isl_r, _ = CL.island_raster(A['bake'])
    # what the material pass still shows WRONG there: a hidden texel more than 3 texels from every visible texel of its
    # island keeps its own (dark) AO (nearer ones take their nearest visible texel's AO and cavity: material's C5c
    # rule); a point beyond an island's 1.5-texel border band reads only the gutter's dilation (a border texel, its
    # centre just outside the triangles, is the bake's own and every island has them)
    hid0 = np.asarray(res['hidden'], bool)
    vis_t = (isl_r >= 0) & ~hid0
    d_vis, (iy_, ix_) = ndimage.distance_transform_edt(~vis_t, return_indices=True)
    hid = hid0 & ((d_vis > 3.0) | (isl_r[iy_, ix_] != isl_r))
    d_isl = ndimage.distance_transform_edt(isl_r < 0)
    out = {}
    for q in sorted(S['members']):
        rec = S['members'][q]
        g = None
        for gs in S['groups'].values():
            for g_ in gs:
                if any(m['spec'] == q for m in g_['members']):
                    g = g_
        Uq = ctx.own_final(q, g['topo'], A['progs_bake'])
        Vc = np.concatenate([it['V'] for it in rec['islands']])
        UVc = np.concatenate([it['UVp'] for it in rec['islands']])
        Fc = np.concatenate([it['F'] + o_ for it, o_ in zip(rec['islands'], np.cumsum(
            [0] + [len(it['V']) for it in rec['islands']])[:-1])])
        bad = tot = off = 0.0
        for it in Uq:
            P, tri, w = tri_samples(it['V'], it['F'], step)
            if not len(P):
                continue
            prim = CL.prim_of_piece(it['piece'], prog_all.names)
            others = CL.subset_program(prog_all, {prim}) if prim is not None else prog_all
            vis = others.eval(P) > VISIBLE
            if not vis.any():
                continue
            t2, b2, pd, ou = locate(P[vis], Vc, Fc)
            uv = at(UVc, Fc, t2, b2)
            xs = np.clip((uv[:, 0] * size).astype(np.int64), 0, size - 1)
            ys = np.clip(((1.0 - uv[:, 1]) * size).astype(np.int64), 0, size - 1)
            ww = w[vis]
            tot += float(ww.sum())
            h_ = hid[ys, xs]
            o_ = d_isl[ys, xs] > 1.5
            bad += float(ww[h_].sum())
            off += float(ww[o_ & ~h_].sum())
        out[q] = dict(visible_mm2=tot * 1e6, hidden_mm2=bad * 1e6, off_mm2=off * 1e6,
                      ok=(bad + off) * 1e6 <= BAD_MM2)
    worst = sorted(out.items(), key=lambda kv: -kv[1]['hidden_mm2'])[:6]
    log(f'[cyborg_stack] HIDDEN on the primary, SEEN on a member: {sum(1 for r in out.values() if not r["ok"])} of '
        f'{len(out)} members over {BAD_MM2} mm2; worst ' + ', '.join(f'{q} {r["hidden_mm2"]:.4f} mm2 (off-island '
                                                                      f'{r["off_mm2"]:.4f})' for q, r in worst))
    return out


def margin_check(bake_isl, prim_specs, pads, st, pk, by_spec, progs_bake, des, ctx):
    """C5-UV b (the lead's call 3): the MIP MARGIN of every stacked primary on the packed set, measured as the C5d
    check's c15 did: the islands rasterised on the set (each texel centre to the island whose triangle holds it); per
    primary its MARGIN, the 5th percentile over its edge texels of half the distance to another island's texels (the
    gutters are grown from both sides and split down the middle: bake.dilate_all), at most MARGIN_CAP; the deepest mip
    that keeps its own colour m_safe = log2(2 x margin / MIP_BILINEAR) (a mip m box reaches 2^(m - 1) texels past an
    edge texel, the bilinear read in that mip half a mip texel more). Its
    member at scale s reads its texels log2(1 / s) mips coarser: past m_safe less MIP_HEADROOM (C5f: one mip, so it
    stays clean at half the screen size too) it counts as showing its neighbours' colour. Per
    primary with such members: the texels un-stacking them costs (their own islands, as build_low makes them, at the
    floor density with PAD's gutter) and the texels widening its gutter costs (its islands' boxes grown to the gutter
    that holds the coarsest member with the headroom: margin = (pad + 2) / 2, a small neighbour's gutter being 2).
    Returns dict(over
    {primary: dict(members, offsets, m_safe, margin, pad, pad_needed, unstack_texels, widen_texels)}, rows {primary:
    dict(margin, m_safe, s_min, offset)})"""
    from scipy import ndimage
    from eidoverse.bestiary.forge import uv as U
    px, (W, H) = pk[0], pk[1]
    size = W
    owner = np.full((size, size), -1, np.int64)
    sid = {}
    for it in bake_isl:
        sp = spec_of(it['piece'])
        j = sid.setdefault(sp, len(sid))
        uvt = np.column_stack([it['UVp'][:, 0] * size - 0.5, (1.0 - it['UVp'][:, 1]) * size - 0.5])
        for f in it['F']:
            p = uvt[f]
            x0, x1 = int(max(0, math.floor(p[:, 0].min()))), int(min(size - 1, math.ceil(p[:, 0].max())))
            y0, y1 = int(max(0, math.floor(p[:, 1].min()))), int(min(size - 1, math.ceil(p[:, 1].max())))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
            if abs(d) < 1e-12:
                continue
            l0 = ((p[1, 1] - p[2, 1]) * (gx - p[2, 0]) + (p[2, 0] - p[1, 0]) * (gy - p[2, 1])) / d
            l1 = ((p[2, 1] - p[0, 1]) * (gx - p[2, 0]) + (p[0, 0] - p[2, 0]) * (gy - p[2, 1])) / d
            m = (l0 >= -1e-6) & (l1 >= -1e-6) & (1.0 - l0 - l1 >= -1e-6)
            owner[gy[m], gx[m]] = j
    pad_p = {}
    for it, pd in zip(bake_isl, pads):
        pad_p.setdefault(spec_of(it['piece']), []).append((it, pd))
    rows, over = {}, {}
    for p_ in sorted(prim_specs):
        mem = [q for q, r in st.items() if r['primary'] == p_]
        if not mem or p_ not in sid:
            continue
        own = owner == sid[p_]
        if not own.any():
            continue
        d_other = ndimage.distance_transform_edt(~((owner >= 0) & ~own))
        edge = own & ~ndimage.binary_erosion(own)
        margin = float(np.percentile(np.minimum(MARGIN_CAP, 0.5 * d_other[edge]), 5))
        m_safe = math.log2(max(2.0 * margin / MIP_BILINEAR, 1.0))
        offs = {q: math.log2(1.0 / max(st[q]['s'], 1e-6)) for q in mem}
        rows[p_] = dict(margin=margin, m_safe=m_safe, s_min=min(st[q]['s'] for q in mem), offset=max(offs.values()))
        bad = sorted(q for q in mem if offs[q] > m_safe - MIP_HEADROOM + 1e-9)
        if not bad:
            continue
        # widening: the primary's islands' boxes with the gutter that holds the coarsest member
        need_m = MIP_BILINEAR * 2.0 ** (max(offs[q] for q in bad) + MIP_HEADROOM) / 2.0
        pad_need = int(math.ceil(2.0 * need_m - 2.0))
        wid = 0.0
        for it, pd in pad_p[p_]:
            dens = U.island_density(it['V'], it['F'], it['UV'])
            T = (it['UV'] - it['UV'].min(0)) * px * it['dens'] / max(dens, 1e-12)
            w, h = np.ptp(T, axis=0)
            pd_eff = pd if (T.max() >= 32.0 or pd > PAD_STACKED) else min(pd, 2 if pd <= PAD else 4)
            wid += (w + 2 * pad_need) * (h + 2 * pad_need) - (w + 2 * pd_eff) * (h + 2 * pd_eff)
        # un-stacking: the members' own islands (build_low's) at the floor density, PAD's gutter
        un = 0.0
        for q in bad:
            for it in by_spec[q]:
                dens = U.island_density(it['V'], it['F'], it['UV'])
                T = (it['UV'] - it['UV'].min(0)) * PX_TODAY * it['dens'] / max(dens, 1e-12)
                w, h = np.ptp(T, axis=0)
                pd_eff = PAD if T.max() >= 32.0 else 2
                un += (w + 2 * pd_eff) * (h + 2 * pd_eff)
        over[p_] = dict(members=bad, offsets={q: offs[q] for q in bad}, m_safe=m_safe, margin=margin,
                        pad=int(max(pd for _, pd in pad_p[p_])), pad_needed=pad_need, unstack_texels=un,
                        widen_texels=wid)
    return dict(over=over, rows=rows)


def features_check(A, step=0.20e-3, log=print):
    """C5-UV b (the lead's call 5): the TEXTURE TIER's marks a member shows against the ones its own design gives it, at
    its own scale. The material pass writes the knuckles' and the clamps' marks (cyborg_limb.part_marks: the drums' and
    the cans' bolt dots, dark centres and lamps, the bright rims of the lugs, tines, drums and cans' feet, the clamp
    lugs' screw sockets) from each texel's place in its knuckle's frame, in units of that knuckle's sizes; a member shows
    its primary's texels. At samples over each member's VISIBLE surface (its islands' samples outside every other piece),
    the marks evaluated twice: SHOWN, at the corresponding point of the primary (its name, its knuckle, the set's
    texel), and OWN, at the member's point in its own name and knuckle with the texel and the rules' absolute lengths x s
    (part_marks' unit: read at the member's own scale, an exact scaled copy's marks are its primary's, scaled; a
    member of an inexact family differs where its own sizes do). Per member and mark (bright, dark, emissive, the
    texture tier's relief) the area that differs (mm2, at the member's own scale) and its share of the area either
    marks. A can's dots turned from where its own design puts them, a lug's machined rim carried onto the face that
    looks into the cross, differ at every mark. Returns {member: dict(area_mm2, mark_mm2, share, by_mark, ok)}"""
    S = A['stack']
    chain, des = A['chain'], A['des']
    tex = 1.0 / A['px']
    fin = {}
    for it in A['bake']['isl']:
        fin.setdefault(spec_of(it['piece']), []).append(it)
    out = {}
    for q in sorted(S['members']):
        rec = S['members'][q]
        p = rec['primary']
        fp = fin.get(p, [])
        if len(fp) != len(rec['islands']):
            continue
        Pq, Pp, nq, npn, bq, bp, rq, Wt = [], [], [], [], [], [], [], []
        for it_p, it_q in zip(fp, rec['islands']):
            reg = CL.REGIONS[it_q['region']]
            if reg not in CL.MARK_REGIONS:
                continue
            tri, bary = samples_bary(it_q['V'], it_q['F'], step * max(rec['s'], 0.05))
            if not len(tri):
                continue
            Pq.append(at(it_q['V'], it_q['F'], tri, bary))
            Pp.append(at(it_p['V'], it_p['F'], tri, bary))
            ar = 0.5 * np.linalg.norm(np.cross(it_q['V'][it_q['F'][:, 1]] - it_q['V'][it_q['F'][:, 0]],
                                               it_q['V'][it_q['F'][:, 2]] - it_q['V'][it_q['F'][:, 0]]), axis=1)
            Wt.append(ar[tri] / np.maximum(np.bincount(tri, minlength=len(it_q['F']))[tri], 1))
            nq += [it_q['piece']] * len(tri)
            npn += [it_p['piece']] * len(tri)
            bq.append(np.full(len(tri), it_q['bone']))
            bp.append(np.full(len(tri), it_p['bone']))
            rq += [reg] * len(tri)
        if not Pq:
            continue
        Pq, Pp, bq, bp, Wt = (np.concatenate(x) for x in (Pq, Pp, bq, bp, Wt))
        rq = np.array(rq)
        # only what the member SHOWS: outside every other piece of the machine at rest (the cover test's reading)
        prog_all = S.get('_prog_all')
        if prog_all is None:
            prog_all = S['_prog_all'] = CL.assembled_program(chain, des, bake=True)
        vis = np.ones(len(Pq), bool)
        for nm in sorted(set(nq)):
            sel = np.array([n_ == nm for n_ in nq])
            pr = CL.prim_of_piece(nm, prog_all.names)
            oth = CL.subset_program(prog_all, {pr}) if pr is not None else prog_all
            vis[sel] = np.asarray(oth.eval(Pq[sel])) > VISIBLE
        if not vis.any():
            out[q] = dict(area_mm2=0.0, mark_mm2=0.0, share=0.0, by_mark={}, ok=True)
            continue
        Pq, Pp, bq, bp, Wt, rq = Pq[vis], Pp[vis], bq[vis], bp[vis], Wt[vis], rq[vis]
        nq = [n_ for n_, v_ in zip(nq, vis) if v_]
        npn = [n_ for n_, v_ in zip(npn, vis) if v_]
        Plq = Pq - np.column_stack([chain['x'][bq], np.zeros(len(bq)), np.zeros(len(bq))])
        Plp = Pp - np.column_stack([chain['x'][bp], np.zeros(len(bp)), np.zeros(len(bp))])
        shown = CL.part_marks(chain, des, Pp, Plp, rq, bp, npn, tex)
        own = CL.part_marks(chain, des, Pq, Plq, rq, bq, nq, tex * rec['s'], unit=rec['s'])
        by, tot_d, tot_m = {}, 0.0, 0.0
        for k_ in ('bright', 'dark', 'emis', 'height'):
            a_, b_ = shown[k_], own[k_]
            if k_ == 'height':                   # (the dots' relief: where it is, at either scale)
                a_, b_ = np.abs(a_) > 0.0, np.abs(b_) > 0.0
            else:
                a_, b_ = a_ > 0.5, b_ > 0.5
            dif = float(Wt[a_ != b_].sum()) * 1e6
            mk = float(Wt[a_ | b_].sum()) * 1e6
            sh = dif / mk if mk > 0 else 0.0
            by[k_] = dict(diff_mm2=dif, mark_mm2=mk, share=sh,
                          ok=bool(sh <= FEAT_SHARE or dif <= FEAT_MM2 * rec['s'] ** 2))
            tot_d, tot_m = tot_d + dif, tot_m + mk
        share = max((v_['share'] for v_ in by.values()), default=0.0)
        out[q] = dict(area_mm2=tot_d, mark_mm2=tot_m, share=share, by_mark=by, ok=all(v_['ok'] for v_ in by.values()))
    bad = sorted(q for q, r in out.items() if not r['ok'])
    worst = sorted(out.items(), key=lambda kv: -kv[1]['share'])[:6]
    log(f'[cyborg_stack] FEATURES (the texture tier\'s marks shown against the member\'s own design at its own scale, '
        f'per mark): {len(out)} members with marks; worst ' + ', '.join(
            f'{q} {r["share"] * 100:.1f} % ({max(r["by_mark"], key=lambda k_: r["by_mark"][k_]["share"])})'
            for q, r in worst) + ' -> ' + ('PASS' if not bad else f'FAIL {bad[:8]}'))
    return out


FEAT_SHARE = 0.10           # C5-UV b: per mark (bright, dark, emissive, relief) a member's may differ from its own design's
                            # on at most this share of the area either marks (an inexact family's own sizes, the low's
                            # chords at the marks' edges)...
FEAT_MM2 = 0.02             # ... or on at most this area x s^2 (mm2: half a texel at the primary's scale)


def island_turn(it):
    """C5-UV b: the in-plane turn (rad) of an island's packed UVs off its own UVs, modulo a quarter turn: (-pi/4,
    pi/4] (the packers' quarter turns keep a texel grid on the island's own axes; min_box_turn's do not)"""
    a = np.asarray(it['UV'], np.float64)
    b = np.asarray(it['UVp'], np.float64)
    a, b = a - a.mean(0), b - b.mean(0)
    th = math.atan2(float((a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]).sum()), float((a * b).sum()))
    return th - (math.pi / 2.0) * round(th / (math.pi / 2.0))


def _texel_centre(uv, size):
    """the canvas UV of the centre of the texel each canvas UV falls in (image rows from the top, v up)"""
    x = np.floor(uv[:, 0] * size)
    y = np.floor((1.0 - uv[:, 1]) * size)
    return np.column_stack([(x + 0.5) / size, 1.0 - (y + 0.5) / size])


def _rot2(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


def marks_drawn_check(A, step=0.06e-3, log=print, plant=None):
    """C5-UV b (the lead's call 5: a check that catches a TURNED RECESS): the texture tier's marks AS PAINTED on the
    texel grid. The C5d check's "pitch can 19 shows can 16's cross recess turned ~30 deg" is no recess in the high: a
    can's end cap is the texture tier's (cheek_profiles' note: a bright disc, four bolt dots, a dark centre, a lamp),
    painted per texel, and C5d's packer had turned the cap's island off its own axes (min_box_turn), so the dots, two
    texels each, were painted on a turned grid. features_check reads the marks continuously at corresponding points, so
    a turned grid passes it; this reads them where they are painted. Per member, at samples over its VISIBLE surface
    (about `step` apart at the primary's scale):
      SHOWN, the primary's marks at the centre of the texel the sample reads (its carried UVs are its primary's packed
        ones), mapped back onto the primary's island: what the material pass painted;
      OWN, the member's own marks (its names, its knuckle; the texel and the rules' lengths x s, part_marks' unit) at
        the centre of the texel the sample falls in on a grid laid along the ISLAND'S OWN AXES (the pack's turn off them
        taken out, quarter turns kept), mapped onto the member;
    per mark (bright, dark, emissive, the relief) the area that differs and its share of the area either marks, the
    bars features_check's. An island on its own axes reads one grid both ways: only the designs differ, at texel
    centres; a turned island differs along every mark's edge. Every primary and unique piece is read too, as its own
    member (s = 1, its own marks both ways: only a turn can differ). plant: {island name: turn (rad)} added to those
    packed islands for the reading (a probe's planted defect). Returns {piece: dict(primary, s, share, area_mm2, by_mark,
    turn_deg, ok)}"""
    S = A['stack']
    chain, des = A['chain'], A['des']
    B = A['bake']
    size = B['size']
    tex = 1.0 / A['px']
    prog_all = S.get('_prog_all')
    if prog_all is None:
        prog_all = S['_prog_all'] = CL.assembled_program(chain, des, bake=True)
    saved = {}
    for it in B['isl']:
        if plant and it['piece'] in plant:
            saved[id(it)] = it['UVp']
            c0 = it['UVp'].mean(0)
            it['UVp'] = (it['UVp'] - c0) @ _rot2(plant[it['piece']]).T + c0
    fin = {}
    for it in B['isl']:
        fin.setdefault(spec_of(it['piece']), []).append(it)
    jobs = [(q, rec['primary'], float(rec['s']), list(zip(fin.get(rec['primary'], []), rec['islands'])))
            for q, rec in S['members'].items() if len(fin.get(rec['primary'], [])) == len(rec['islands'])]
    jobs += [(sp, sp, 1.0, [(it, it) for it in its]) for sp, its in fin.items()]
    out = {}
    try:
        for q, p, s, pairs in jobs:
            Ps_, Po_, Wt_, rq_, bp_, bq_, np_, nq_, th_ = [], [], [], [], [], [], [], [], []
            for it_p, it_q in pairs:
                reg = CL.REGIONS[it_q['region']]
                if reg not in CL.MARK_REGIONS:
                    continue
                tri, bary = samples_bary(it_q['V'], it_q['F'], step * max(s, 0.05))
                if not len(tri):
                    continue
                pr = CL.prim_of_piece(it_q['piece'], prog_all.names)
                oth = CL.subset_program(prog_all, {pr}) if pr is not None else prog_all
                vis = np.asarray(oth.eval(at(it_q['V'], it_q['F'], tri, bary))) > VISIBLE
                if not vis.any():
                    continue
                tri, bary = tri[vis], bary[vis]
                F = it_p['F']
                UVp = np.asarray(it_p['UVp'], np.float64)
                U3 = np.column_stack([UVp, np.zeros(len(UVp))])
                uv = at(UVp, F, tri, bary)
                c_s = _texel_centre(uv, size)
                t1, b1, _, _ = locate(np.column_stack([c_s, np.zeros(len(c_s))]), U3, F)
                th = island_turn(it_p)
                c0 = UVp.mean(0)
                c_o = (_texel_centre((uv - c0) @ _rot2(-th).T + c0, size) - c0) @ _rot2(th).T + c0
                t2, b2, _, _ = locate(np.column_stack([c_o, np.zeros(len(c_o))]), U3, F)
                ar = 0.5 * np.linalg.norm(np.cross(it_q['V'][F[:, 1]] - it_q['V'][F[:, 0]],
                                                   it_q['V'][F[:, 2]] - it_q['V'][F[:, 0]]), axis=1)
                Ps_.append(at(it_p['V'], F, t1, b1))
                Po_.append(at(it_q['V'], F, t2, b2))
                Wt_.append(ar[tri] / np.maximum(np.bincount(tri, minlength=len(F))[tri], 1))
                rq_ += [reg] * len(tri)
                bp_.append(np.full(len(tri), it_p['bone']))
                bq_.append(np.full(len(tri), it_q['bone']))
                np_ += [it_p['piece']] * len(tri)
                nq_ += [it_q['piece']] * len(tri)
                th_.append(abs(math.degrees(th)))
            if not Ps_:
                continue
            Ps, Po, Wt, bp, bq = (np.concatenate(x) for x in (Ps_, Po_, Wt_, bp_, bq_))
            rq = np.array(rq_)
            Pl = lambda P_, g_: P_ - np.column_stack([chain['x'][g_], np.zeros(len(g_)), np.zeros(len(g_))])
            shown = CL.part_marks(chain, des, Ps, Pl(Ps, bp), rq, bp, np_, tex)
            own = CL.part_marks(chain, des, Po, Pl(Po, bq), rq, bq, nq_, tex * s, unit=s)
            by = {}
            for k_ in ('bright', 'dark', 'emis', 'height'):
                a_, b_ = shown[k_], own[k_]
                a_, b_ = (np.abs(a_) > 0.0, np.abs(b_) > 0.0) if k_ == 'height' else (a_ > 0.5, b_ > 0.5)
                dif = float(Wt[a_ != b_].sum()) * 1e6
                mk = float(Wt[a_ | b_].sum()) * 1e6
                sh = dif / mk if mk > 0 else 0.0
                by[k_] = dict(diff_mm2=dif, mark_mm2=mk, share=sh, ok=bool(sh <= FEAT_SHARE or dif <= FEAT_MM2 * s ** 2))
            out[q] = dict(primary=p, s=s, share=max(v_['share'] for v_ in by.values()), by_mark=by,
                          area_mm2=sum(v_['diff_mm2'] for v_ in by.values()), turn_deg=max(th_),
                          ok=all(v_['ok'] for v_ in by.values()))
    finally:
        for it in B['isl']:
            if id(it) in saved:
                it['UVp'] = saved[id(it)]
    bad = sorted(q for q, r in out.items() if not r['ok'])
    worst = sorted(out.items(), key=lambda kv: -kv[1]['share'])[:6]
    log(f'[cyborg_stack] MARKS AS PAINTED (the texel grid each piece reads against one on its island\'s own axes, its '
        f'own design at its own scale): {len(out)} pieces with marks, islands turned off their axes '
        f'{sum(1 for r in out.values() if r["turn_deg"] > 0.5)}; worst ' + ', '.join(
            f'{q} {r["share"] * 100:.1f} %' for q, r in worst) + ' -> ' + ('PASS' if not bad else f'FAIL {bad[:8]}'))
    return out


def map_details(ctx, det, st, unc):
    """the details of every stacked shell are its primary's carried onto it (its panels' seams and its heads as the
    shared texels show them: placed by the correspondence, the heads' diameters scaled by s; the seams' tube keeps the
    sizes' width, a member's high is carved into the body high only, never baked), so its high is what its texels show;
    every other body's as cyborg_limb.details made them"""
    out = dict(det)
    x = ctx.chain['x']
    for q, rec in st.items():
        if ctx.kind(q) != 'shell':
            continue
        p = rec['primary']
        kp, kq = joint_of(p), joint_of(q)
        bp, bq = CL.shell_body(ctx.des, kp), CL.shell_body(ctx.des, kq)
        if bp not in det:
            continue
        Up = unc[p]
        Uq = rec['unclipped']
        Vp = np.concatenate([it['V'] for it in Up])
        Fp = np.concatenate([it['F'] + o_ for it, o_ in zip(Up, np.cumsum([0] + [len(it['V']) for it in Up])[:-1])])
        Vq = np.concatenate([it['V'] for it in Uq])
        s = rec['s']
        op, oq = np.array([x[kp], 0.0, 0.0]), np.array([x[kq], 0.0, 0.0])
        Np = tri_normals(Vp, Fp)
        Nq = tri_normals(Vq, Fp)

        def carry_pts(P):
            P = np.asarray(P, np.float64) + op
            tri, bary, pd, ou = locate(P, Vp, Fp)
            foot = at(Vp, Fp, tri, bary)
            d = ((P - foot) * Np[tri]).sum(1)
            return at(Vq, Fp, tri, bary) + (s * d)[:, None] * Nq[tri] - oq, tri
        g = det[bp]
        seams = [carry_pts(P)[0] for P in g['seams']]
        heads = []
        for h in g['heads']:
            pq, tri = carry_pts(np.asarray(h['p'])[None])
            n = rec['R'] @ np.asarray(h['n'], np.float64)
            heads.append(dict(h, p=pq[0], n=n / np.linalg.norm(n), D=h['D'] * s))
        out[bq] = dict(seams=seams, heads=heads, panels=[dict(pn) for pn in g['panels']], carried_from=bp, scale=s)
    return out
