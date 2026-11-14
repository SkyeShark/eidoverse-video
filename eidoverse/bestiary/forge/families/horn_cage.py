"""THE HORN'S LOW: our own cage, drawn as fair loops from the SAME sections the block-out is swept from
(work/bestiary/research/DEER_PLAN.md §5.3 with DEER_CRITIC §4; WORKING_RULES 2; HIGH_TO_LOW.md "the one idea": every
loop is a clean curve fitted to the form, never a mesh an algorithm chose). No decimation, no remesh, no marching
cubes: every vertex is a point of a branch's own section at a station and an angle I chose, pushed along that
section's radius onto the SMOOTH block-out (never onto the voxel high with its beads and pearls).

THE DRAWING, for an antler:
  BEAM      a tube of K columns; rings at the burr's rim (seal edge, under the rim, crest, over it), at each fork's
            block, and between them only where the outline turns (a horn is rigid: `stations` adds a ring when the
            straight loft between two rings would leave the form by more than the LOD's tolerance)
  FORK      a PORT (forge/ports.py): a block of a x b quads is cut from the beam where a tine's saddle stands
            (2(a + b) = the tine's root count), bridged (forge/loft.py bridge) to a TILTED ring on the tine where it
            is clear of the blend (far up the crotch side, near on the open side), the bridge rings seated on the
            saddle: one form flowing into the next, as the block-out has it
  TINE      a 4 -> 2 reducer (loft.reduce_ring) after the saddle, then rings where its outline turns, a quad-grid
            cap on the tip (loft.cap: no fan, no pole)
  SEAL      a quad-grid cap on the first ring
A CLASS of tines (the preset's `classes`: the hero rule keeps beam, brow and tray their own) is drawn with ONE ring
table (stations as shares of the shaft), so every member has the template's topology and stacks on its UVs.

LODS (authored from the same tables, never decimated): the columns, the fork block and the tolerance per level.
`cage()` returns the QuadMesh and the STRUCTURE the UV stage needs (rings in column order per island).
"""
import numpy as np

from .. import loft, ports
from ..mesh import QuadMesh
from . import horn_surface as HS

# K: the beam's columns; block: the fork's (columns, ring intervals), 2(a + b) = the tine's root ring; shaft: the
# tine's columns after its saddle (half the root: a reducer; the same: none); tol: the loft's chord sag, metres at
# life (0.5 px at the 1 m hero view of a 1080-line frame is 0.34 mm; K 24 at the burr's r 39 sags 0.33 mm)
# burr: which rows the burr is drawn with (BURR_ROWS below); gap: the longest ring interval on the beam and on a
# tine, metres at life (absent: 0.060, 0.075)
LODS = (dict(K=24, block=(8, 4), shaft=12, tol=0.35e-3, bridge=2, sag=0.337e-3, ring_K=(24, 16, 12), burr='full'),
        dict(K=16, block=(5, 1), shaft=12, tol=1.0e-3, bridge=1, burr='crest'),
        dict(K=12, block=(3, 1), shaft=8, tol=2.6e-3, bridge=1, burr='crest'),
        # THE FAR RUNGS (11-12, check 2's failure 3: "there is no LOD past 7.2 m": the pair's 2,556 LOD2 triangles
        # were 4.6 a pixel at 20 m, 19 at 40 m, 75 at 80 m; craft guide 05.34 / 05.35 "3-5 sides once a tube covers
        # only a few pixels", 14.55). Drawn from the same tables, as LOD1 and LOD2 are: the beam's columns, the
        # fork's block and the tine's columns go down together (8 / 6, then 6 / 4), the rings stand further apart
        # (`tol`, `gap`), and the burr's rim, under a pixel from 13 m, is not drawn (`burr`). Their triangles and
        # the distance each is for (its worst measured chord sag at half a pixel, as h10_glb prints it for every
        # LOD): work/bestiary/deer/horns/build_NOTES.md step 46. TRIED AND NOT KEPT: a beam of 4 columns with
        # blocks of one (316 triangles): a square tube stands 13 mm inside the clay its saddles are seated on, and
        # they cross it and each other (70 pairs). A rung under LOD4 is tines as separate spikes, another drawing
        dict(K=8, block=(2, 1), shaft=6, tol=5.0e-3, bridge=1, burr='none', gap=(0.12, 0.15), widen=True),
        dict(K=6, block=(1, 1), shaft=4, tol=10.0e-3, bridge=1, burr='none', gap=(0.20, 0.25)))
# THE LODS' BEAM, BALANCED WITH THEIR TINES (fix round 1, continued, 11-11; Skye with this run: "make sure they're
# also optimized as best you cant!"). A LOD is drawn from the distance where its WORST region's measured chord sag is
# half a pixel (1080 lines, 40 deg: 0.337 mm at 1 m). As first drawn (beam K 12 / 8, blocks (4, 2) / (3, 1)) the BEAM
# alone set both distances (LOD1 2.12 mm on the trunk by the burr and the forks, its tines at most 1.00: from 6.3 m;
# LOD2 as it ships, on LOD0's chart, 5.34 mm, its tines at most 2.42: from 15.8 m), so LOD0's 5,772 triangles stayed
# on screen to 6.3 m. Measured (work/bestiary/deer/horns/build/scripts/fix2/f28_lod_trials.py -> out/fix2/
# lod_trials_1.json, _2.json; the shipped LODs, both sides, the right one warped): LOD1 beam K 16, block (5, 1) (the
# fork's 12-vertex loop, 5 columns = 112 deg of the beam): 2,280 triangles (+218), beam 1.39 / tines <= 1.06 mm, from
# 4.1 m; 0 self-intersections, 0 UV flips. (Block (4, 2), 90 deg, is narrower than the forks' blends: 13 crossings,
# 6 flips.) LOD2 beam K 12, block (3, 1) (8-vertex loop, tines K 8): 1,278 (+212), beam 2.12 / tines <= 2.43 mm, from
# 7.2 m (was 15.8), clean. So LOD0 0-4.1 m, LOD1 4.1-7.2 m, LOD2 past 7.2 m
# LOD0's tines and the beam's top (fix round 1, 11-11, the check's items 1 and 2): `sag` is half a pixel at the 1 m
# hero view (1080 lines, 40 deg: 0.337 mm) and every ring takes the FEWEST columns of `ring_K` whose chord sag on its
# own radius stays under it (r (1 - cos(pi / K)): K 24 to r 39.4 mm, K 16 to 17.5, K 12 to 9.9). The first drawing
# reduced every fork's 24-vertex ring C to 12 at once: the tines' roots sagged 0.41-0.61 mm (the check's
# chart_sag_per_ring.png), and that reducer's inner ring, pulled half way flat, ran BACK under ring C's high side on a
# slanted tine: the tray's saddle passed 4.1 mm through its own shaft (check1/out/tray_cross.json). Now the shaft
# starts at ring C itself and its rings UN-TILT along the tine (`_untilt`), every vertex's station rising at least half
# as fast as the ring's mean, so no ring can run back under the one before it
# THE BURR'S ROWS (station mm on the beam, what the row is). A rim row's station is nominal: its vertices are placed
# from the rim's own centreline (RIM_ROW). (11-12, check 2's failure 2, "a low drawn as a flat washer: a flat
# annulus on a vertical wall": the first drawing had the rim's lower and upper EDGE, both at the rim's full depth,
# so its profile was a rectangle, a disc cut by two planes. Now the rim is three rows on its own round section,
# under / crest / shoulder: a rope's profile, and its outline is the clay rim's own, thick and thin round the beam.)
# LOD1 and LOD2 keep the crest alone; from LOD3 the rim is under a pixel and is not drawn
BURR_ROWS = dict(full=((0.4, 'seal'), (4.2, 'under'), (8.0, 'crest'), (12.0, 'shoulder'), (16.0, 'over')),
                 crest=((0.4, 'seal'), (8.0, 'crest'), (16.0, 'over')),
                 none=((0.4, 'seal'), (16.0, 'over')))
# where a rim row stands on the rim's section: degrees from straight out of the beam toward its distal side, and
# the share of the preset's `low_proud` (the nodules' middle height) it stands out of the clay by
RIM_ROW = dict(under=(-50.0, 0.5), crest=(4.0, 1.0), shoulder=(56.0, 0.5))
# a 4 -> 2 reducer's middle vertex, as a share of the way from the outer ring to the inner. At loft.reduce_ring's
# 0.5 its quad (three outer vertices and the middle one) was split by the exporter along the ring (the shorter
# diagonal): a sliver lying in the ring's plane, folded 90 deg on the beam's top. At 1/3 the short diagonal is the
# one up the branch, and the quad folds only by the ring's own turn
MID_PULL = 0.33


def _unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-30)


def stations(br, s_from, s_to, K, tol, max_gap, theta0=0.0, probe=0.003):
    """ring stations in [s_from, s_to]: the FEWEST such that the straight loft between consecutive rings stays
    within tol of the branch's own section everywhere between (greedy from s_from; probes every `probe` metres).
    Rings land where the outline turns: at a bend, a swelling, a taper's knee"""
    th = theta0 + np.arange(K) * (2.0 * np.pi / K)
    out = [float(s_from)]
    cand = np.arange(s_from + probe, s_to, probe)
    ring = lambda s: br.surface(np.full(K, s), th)                                   # noqa: E731
    while out[-1] < s_to - 1e-9:
        a = out[-1]
        Ra = ring(a)
        best = None
        for c in list(cand[cand > a + 1e-9]) + [float(s_to)]:
            if c - a > max_gap:
                break
            Rc = ring(c)
            okc = True
            for m in cand[(cand > a) & (cand < c)]:
                f = (m - a) / (c - a)
                if np.linalg.norm(ring(m) - (Ra * (1 - f) + Rc * f), axis=1).max() > tol:
                    okc = False
                    break
            if not okc:
                break
            best = c
        out.append(float(best) if best is not None else float(min(a + probe, s_to)))
    return np.array(out)


def k_for(r, sag, ks):
    """the fewest columns of `ks` (largest first) whose chord sag on radius r stays under `sag` (a 2 % margin)"""
    for K in sorted(ks):
        if r * (1.0 - np.cos(np.pi / K)) <= 0.98 * sag:
            return K
    return max(ks)


def split_sag(prog, V, ring_ids, bar, floor=0.85):
    """A RING THAT CLIMBS OVER A TINE'S ROOT SPLITS ITS SAG (11-12, check 2's failure 4: 14 of the beam's whole rings
    beside the five forks had edge midpoints 0.34-0.61 mm under the clay against half a pixel, 0.337). The ring's
    vertices are ON the clay, so all of a chord's error is on one side, and where the ring crosses a root the clay
    between two columns curves on the TINE's radius (15 mm: a 7.9 mm edge sags 0.52), not the beam's (30 mm:
    0.26). More columns there would cost reducers in the beam's strip; the polygon that errs least is neither
    inscribed nor circumscribed: each vertex beside an edge deeper than floor x bar moves OUT along the clay's
    normal by half that edge's depth, so the edge's middle lies half as deep and its ends stand as far proud.
    ring_ids: one ring's vertex ids in order (a closed ring). Returns the moved positions and (worst depth before,
    worst depth after, the largest move), metres"""
    P = V[ring_ids].copy()
    depth = lambda Q: np.maximum(-prog.eval(0.5 * (Q + np.roll(Q, -1, axis=0))), 0.0)       # noqa: E731
    d0 = depth(P)
    if d0.max() <= floor * bar:
        return P, (float(d0.max()), float(d0.max()), 0.0)
    need = np.where(d0 > floor * bar, d0, 0.0)                    # edge j joins vertex j and j + 1
    off = 0.5 * np.maximum(need, np.roll(need, 1))
    P = P + _unit(prog.normals(P)) * off[:, None]
    return P, (float(d0.max()), float(depth(P).max()), float(off.max()))


def reduce_pattern(k_out, k_in):
    """the strip from k_out to k_in columns as plain quads 'p' (one edge to one) and 4 -> 2 units 'u' (four edges to
    two), the units spread evenly with the plain quads split round each, so the strip leans at most half a unit
    (24 -> 16: p u p four times, a 7.5 deg lean; 16 -> 12: p p u p p twice, 15 deg). Position 0 is a plain quad's
    first edge (or a unit's), so the column at the ring's first vertex runs straight through (a UV seam's column),
    and so does the one half way round"""
    u = (k_out - k_in) // 2
    p = k_out - 4 * u
    assert u >= 0 and p >= 0 and k_out - k_in == 2 * u, (k_out, k_in)
    if u == 0:
        return ['p'] * k_out
    assert p % u == 0 and (p // u) % 2 == 0, (k_out, k_in, 'plain quads split unevenly round the units')
    h = p // u // 2
    return (['p'] * h + ['u'] + ['p'] * h) * u


def reduce_mixed(mesh, R, inner_pos, pattern, mid_pull=MID_PULL):
    """a k_out -> k_in strip after ring R (vertex ids ordered so the faces already there use R's edges BACKWARD:
    loft.reduce_ring's convention) by `pattern` (reduce_pattern). A 'u' is loft.reduce_ring's unit, four quads
    (o0 o1 m i0) (o1 o2 o3 m) (o3 o4 i2 m) (i0 m i2 i1) round one middle vertex m (mid_pull of the way from o2 to
    i1); a 'p' is (o0 o1 i1 i0). All quads, every inner edge twice and opposed; the inner ring keeps R's orientation.
    Returns the mesh, the inner ring's ids, the middle vertices' ids and each one's (o2, i1)"""
    from ..mesh import QuadMesh as _QM
    R = np.asarray(R)
    K = len(R)
    n_in = sum(1 if c == 'p' else 2 for c in pattern)
    assert sum(1 if c == 'p' else 4 for c in pattern) == K, (K, pattern)
    n0 = len(mesh.V)
    inner = np.arange(n0, n0 + n_in)
    n_u = pattern.count('u')
    mids = np.arange(n0 + n_in, n0 + n_in + n_u)
    Vin = np.asarray(inner_pos, np.float64).reshape(n_in, 3)
    Vm = np.zeros((n_u, 3))
    Q, pairs = [], []
    o = i = u = 0
    for c in pattern:
        if c == 'p':
            Q.append([R[o % K], R[(o + 1) % K], inner[(i + 1) % n_in], inner[i % n_in]])
            o, i = o + 1, i + 1
        else:
            oo = [R[(o + j) % K] for j in range(5)]
            i0, i1, i2 = inner[i % n_in], inner[(i + 1) % n_in], inner[(i + 2) % n_in]
            m = mids[u]
            Vm[u] = mesh.V[oo[2]] * (1.0 - mid_pull) + Vin[(i + 1) % n_in] * mid_pull
            Q += [[oo[0], oo[1], m, i0], [oo[1], oo[2], oo[3], m], [oo[3], oo[4], i2, m], [i0, m, i2, i1]]
            pairs.append((int(oo[2]), int(i1)))
            o, i, u = o + 4, i + 2, u + 1
    attrs = {k: np.vstack([a, np.repeat(a[R[:1]], n_in + n_u, axis=0)]) for k, a in mesh.attrs.items()}
    return _QM(np.vstack([mesh.V, Vin, Vm]), np.vstack([mesh.Q, np.array(Q)]), attrs), inner, mids, pairs


def asym(c, skel, seed=17, deg=9.0, length=0.08, bend_deg=4.0):
    """THE PAIR'S ASYMMETRY (the plan's `asym` knob, §5.4; fix round 1, the check's item 7: the pair was ONE antler
    mirrored to 0.000 mm, and perfect symmetry is a tell of geometry; every real pair differs side to side, refs c11
    Richmond Park 2025 01). A cage `c` (any LOD) WARPED, its topology and its UVs kept, so the right antler made from
    it still shares every texel of the left's bake:
      - each tine turned about its root on the beam's centreline by an angle drawn from +-deg (at least a third of
        it) about an axis square to its root direction, and stretched along its own path by 1 +- length (each
        vertex moved along the tine's tangent by the share x its station);
      - the beam bent from 40 % of its length up by up to +-bend_deg (rigidly for everything that leaves the beam
        there: the crown's tines ride their fork);
      - a tine's change blended in over its fork's saddle: 0 on the port's loop (the beam's quads), 1 from ring C.
    The tine stays a rigid tube under the turn, so the baked relief rides it as a stacked copy's does (the stack's
    FORM error, h08 `stack`: p95 under 3.5 deg). Returns a copy of `c` with the moved vertices and a report (mm)"""
    import copy
    rng = np.random.default_rng(seed)
    mm = skel.scale * 1.0e-3
    V = np.asarray(c['mesh'].V, np.float64).copy()
    Q = c['mesh'].Q
    lab = np.asarray(c['labels']).astype(str)
    s_v = np.asarray(c['s'], np.float64)
    n = len(V)
    # per vertex: its branch (the label of a quad that uses it; a saddle's vertices by their saddle row)
    owner = np.full(n, '', dtype=object)
    for q, lb in zip(Q, lab):
        for v in q:
            if owner[v] == '' or owner[v].startswith('beam'):
                owner[v] = lb
    # a tip cap's inner grid vertices carry no station in the cage (0): they take their shaft's last ring's, or the
    # stretch and the bend move the cap's rim and leave its middle behind (a spike at every tip, the first board)
    for cl in sorted({str(o) for o in owner if str(o).endswith('.cap')}):
        stem = cl[:-4]
        shaft = np.array([str(o) == stem for o in owner])
        capv = np.array([str(o) == cl for o in owner]) & (s_v == 0.0)
        if shaft.any() and capv.any():
            s_v[capv] = float(s_v[shaft].max())
    beam = skel.branches[0]
    W = np.zeros(n)
    TINE = np.full(n, -1)
    report = {}
    tines = [b for b in skel.branches if b.kind == 'tine']
    for ti, t in enumerate(tines):
        sad = c['islands'].get(t.name, {}).get('saddle')
        own = np.array([str(o).split('.')[0] == t.name for o in owner])
        W[own] = 1.0
        TINE[own] = ti
        if sad is not None:
            nr = len(sad) - 1
            for r_, row in enumerate(sad):
                row = np.asarray(row)
                row = row[row >= 0]
                W[row] = r_ / max(nr, 1)
                TINE[row] = ti if r_ > 0 else TINE[row]
                if r_ == 0:
                    TINE[row] = -1                                       # the port's loop is the beam's
    V0 = V.copy()
    for ti, t in enumerate(tines):
        m = TINE == ti
        if not m.any():
            continue
        p0, _, _, t0 = t.frame(0.0)
        ax = rng.normal(size=3)
        ax -= t0 * float(ax @ t0)
        ax /= np.linalg.norm(ax)
        ang = np.radians(rng.uniform(deg / 3.0, deg) * rng.choice([-1.0, 1.0]))
        stretch = rng.uniform(-length, length)
        # the stretch along the tine's own path (the tangent at each vertex's station), then the turn about the root
        _, _, _, tt = t.frame(np.clip(s_v[m], 0.0, t.length))
        P = V0[m] + (stretch * np.clip(s_v[m], 0.0, None))[:, None] * tt
        Kx = np.array([[0.0, -ax[2], ax[1]], [ax[2], 0.0, -ax[0]], [-ax[1], ax[0], 0.0]])
        Rm = np.eye(3) + np.sin(ang) * Kx + (1.0 - np.cos(ang)) * (Kx @ Kx)
        P = p0 + (P - p0) @ Rm.T
        w = W[m][:, None]
        V[m] = V0[m] * (1.0 - w) + P * w
        report[t.name] = dict(turn_deg=round(float(np.degrees(ang)), 2), stretch_pct=round(100.0 * stretch, 2),
                              moved_mm_max=round(float(np.linalg.norm(V[m] - V0[m], axis=1).max()) / mm, 1))
    # the beam's bend from 40 % of its length: every vertex by its ANCHOR station on the beam (a tine's: its fork's)
    s_b = 0.40 * beam.length
    anchor = np.where(TINE >= 0, np.array([tines[k].s_parent if k >= 0 else 0.0 for k in TINE]), s_v)
    up = (anchor > s_b) & np.array([not str(o).startswith('seal') for o in owner])
    if up.any():
        pb, nb_, bb_, tb = beam.frame(s_b)
        ax = nb_ * rng.normal() + bb_ * rng.normal()
        ax /= np.linalg.norm(ax)
        a_max = np.radians(rng.uniform(bend_deg / 2.0, bend_deg) * rng.choice([-1.0, 1.0]))
        f = np.clip((anchor[up] - s_b) / max(beam.length - s_b, 1e-9), 0.0, 1.0)
        a = a_max * (3.0 * f * f - 2.0 * f ** 3)
        Kx = np.array([[0.0, -ax[2], ax[1]], [ax[2], 0.0, -ax[0]], [-ax[1], ax[0], 0.0]])
        P = V[up] - pb
        # Rodrigues per vertex
        cr = np.cross(ax[None, :], P)
        V[up] = pb + P * np.cos(a)[:, None] + cr * np.sin(a)[:, None] + \
            ax[None, :] * (P @ ax)[:, None] * (1.0 - np.cos(a))[:, None]
        report['beam'] = dict(bend_deg=round(float(np.degrees(a_max)), 2),
                              moved_mm_max=round(float(np.linalg.norm(V[up] - V0[up], axis=1).max()) / mm, 1))
    out = copy.copy(c)
    out['mesh'] = QuadMesh(V, Q)
    out['asym'] = report
    return out


def _member_prog(br):
    from .. import sdf as S
    p = S.Program()
    p.sweep(br.P, br.n, br.r0, a2=br.a2, phi2=br.phi2, a3=br.a3, phi3=br.phi3, a4=br.a4, aspect=br.asp, name=br.name)
    return p


def cage(skel, prog, lod=0, log=print, uv_ref=None):
    """the antler's low at a LOD. Returns dict(mesh, labels (per quad: island name), islands (the structure per
    island for the UV stage), report). uv_ref: LOD0's layout charts for the beam (horn_uv.layout's
    `charts['beam']`: th_seam, s_cuts): a LOD that will wear LOD0's texture set (horn_uv.lod_layout) is drawn with
    a COLUMN ON THE BEAM'S SEAM (K 8 has none at 240 deg: its columns are turned 15) and a RING AT EACH CROSS CUT
    of the beam's strip, so none of its quads lies across a border of LOD0's islands. None: as before, to the bit"""
    T = LODS[lod]
    K, (ba, bb), Ks, tol = T['K'], T['block'], T['shaft'], T['tol'] * skel.scale
    mm = skel.scale * 1.0e-3
    beam = skel.branches[0]
    tines = [b for b in skel.branches[1:] if b.kind == 'tine']
    blend = skel.blend
    dth = 2.0 * np.pi / K
    th0 = float(np.mod(uv_ref['th_seam'], dth)) if uv_ref else 0.0
    th0 = 0.0 if dth - th0 < 1.0e-9 else th0
    th = th0 + np.arange(K) * dth
    pb = _member_prog(beam)
    # ---------------------------------------------------------------- each fork's block on the beam's (s, theta)
    forks = []
    s_fine = np.arange(0.0, beam.length, 0.002)
    for t in sorted(tines, key=lambda b: b.s_parent):
        pt = _member_prog(t)
        S2, TH2 = np.meshgrid(s_fine, th, indexing='ij')
        d = pt.eval(beam.surface(S2.ravel(), TH2.ravel())).reshape(S2.shape)
        m = d < 0.55 * blend
        rows = np.nonzero(m.any(1))[0]
        cols = m.any(0)
        # the block's columns: centred on the footprint's own middle angle
        ang = np.angle(np.sum(np.exp(1j * th[cols])))
        # `widen` (a far LOD's row): a fork whose footprint is wider round the beam than the block takes ONE more
        # column (LOD3: crown_c stands on the thin upper beam and its footprint wraps it; in a block of 2 of 8
        # columns its saddle ran through the beam, 17 crossing pairs; by the columns it touches alone it took 7
        # of the 8 and folded 71 deg). Its tine then starts with 2 more columns than the others. The width is
        # read on 96 angles, at the footprint's widest station
        baf = ba
        if T.get('widen'):
            thf = th0 + np.arange(96) * (2.0 * np.pi / 96.0)
            S3, TH3 = np.meshgrid(s_fine[rows[0]:rows[-1] + 1], thf, indexing='ij')
            wide = (pt.eval(beam.surface(S3.ravel(), TH3.ravel())).reshape(S3.shape) < 0.55 * blend).sum(1).max()
            baf = int(np.clip(np.ceil(wide / 96.0 * K - 0.5), ba, ba + 1))
        k0 = int(np.round((ang - th0 - 0.5 * baf * 2.0 * np.pi / K) / (2.0 * np.pi / K)))
        forks.append(dict(t=t, pt=pt, s_lo=s_fine[rows[0]] - 2.0 * mm, s_hi=s_fine[rows[-1]] + 2.0 * mm, k0=k0,
                          ba=baf))
    burr_rows = BURR_ROWS[T.get('burr', 'full')]
    gap_beam, gap_tine = T.get('gap', (0.060, 0.075))
    s_min = burr_rows[-1][0] * mm + 2.5 * mm
    for i, f in enumerate(forks):
        f['s_lo'] = max(f['s_lo'], s_min)
        if i:
            g = forks[i - 1]
            if f['s_lo'] < g['s_hi'] + 9.0 * mm:              # one row of quads in the crotch between two tines
                mid = 0.5 * (f['s_lo'] + g['s_hi'])
                g['s_hi'], f['s_lo'] = mid - 4.5 * mm, mid + 4.5 * mm
    # ---------------------------------------------------------------- the beam's ring stations
    s_red = forks[-1]['s_hi'] + 10.0 * mm                   # the beam's own reducer, past its last fork
    # (station, no ring may be added in the interval ENDING here): the burr's rows are one modelled step (a
    # ring added between its rim rows lay 0.2-1 mm from the next: ten slivers folded 160-179 deg), a block is b rows
    forced = [(v * mm, j > 0) for j, (v, _) in enumerate(burr_rows)]
    for f in forks:
        f['rings_s'] = np.linspace(f['s_lo'], f['s_hi'], bb + 1)
        forced += [(s_, j > 0) for j, s_ in enumerate(f['rings_s'])]
    forced = sorted(forced + [(s_red, False)])
    if uv_ref:
        # a ring at each cross cut of LOD0's beam strip (never inside a block, nor within 6 mm of a ring that is
        # already forced: a block's own edge then stands for the cut)
        for s_cut in uv_ref['s_cuts']:
            if forced[0][0] < s_cut < s_red and not any(f['s_lo'] - mm < s_cut < f['s_hi'] + mm for f in forks) \
                    and min(abs(s_cut - a) for a, _ in forced) > 6.0 * mm:
                forced.append((float(s_cut), False))
        forced = sorted(forced)
    st = [forced[0][0]]
    for (a, _), (c, in_block) in zip(forced[:-1], forced[1:]):
        # a block is exactly b ring intervals (its loop must count 2(a + b)): no ring is added inside one
        st += [c] if in_block else list(stations(beam, a, c, K, tol, max_gap=gap_beam * skel.scale, theta0=th0)[1:])
    st = np.array(st)
    N = len(st)
    # ---------------------------------------------------------------- the beam tube, seated on the block-out
    Sg, Tg = np.meshgrid(st, th, indexing='ij')
    P, _, ok = HS.seat(prog, beam, Sg.ravel(), Tg.ravel(), maxd=0.03 * skel.scale)
    P0 = beam.surface(Sg.ravel(), Tg.ravel())
    V = np.where(ok[:, None], P, P0)
    rings = np.arange(N * K).reshape(N, K)
    # THE BURR IS ONE MODELLED STEP: its rim rows (BURR_ROWS: under, crest, shoulder; the crest alone on LOD1 and
    # LOD2) stand on the rim's own round section, each vertex from the rim's OWN centreline at its column's angle
    # (the rim wanders along the beam and in and out: rings at fixed stations caught it at some columns and missed
    # it at others, a jagged ring that folded under the rim, build/tmp/h06_folds.png). The nodules on it are the
    # bake's
    rims = [b for b in skel.branches if b.kind == 'rim']
    if rims and any(kind in RIM_ROW for _, kind in burr_rows):
        rim = rims[0]
        pc, nc, bc, tc = beam.frame(rim.s_parent)
        q = rim.P[:-1] - pc
        ang_r = np.arctan2(q @ bc, q @ nc)
        order = np.argsort(ang_r)
        A3 = np.concatenate([ang_r[order] - 2.0 * np.pi, ang_r[order], ang_r[order] + 2.0 * np.pi])
        thw = np.angle(np.exp(1j * th))
        at = lambda arr: np.interp(thw, A3, np.tile(arr[order], 3))                      # noqa: E731
        cx = np.column_stack([at(rim.P[:-1, kk]) for kk in range(3)])
        rr = at(rim.r0[:-1])
        dep = rr * float(rim.asp[0])
        e_r = np.cos(th)[:, None] * nc + np.sin(th)[:, None] * bc
        # ... and stands `low_proud` OUT of the clay's rim: the knobs of the high stand 2-7 mm over that rim, so a
        # low on the rim itself drew the coronet a size too small in outline and baked its knobs from 7.6 mm away,
        # at the cage's limit (crescents of missed texels behind each knob: build/tmp/h08_burr_b_miss.png). At the
        # knobs' middle height the outline is the coronet's and the bake reaches both the tops and the notches
        proud = float(skel.preset.get('burr', {}).get('low_proud', 0.0)) * 1.0e-3 * skel.scale
        for row, (_, kind) in enumerate(burr_rows):
            if kind not in RIM_ROW:
                continue
            phi, share = np.radians(RIM_ROW[kind][0]), RIM_ROW[kind][1]
            # the rim's own section at this angle across it, then out to the clay along that direction (the rim
            # meets the beam in a fillet), then the row's share of `low_proud`
            d_phi = e_r * np.cos(phi) + tc[None, :] * np.sin(phi)
            Pd = cx + e_r * (np.cos(phi) * dep)[:, None] + tc[None, :] * (np.sin(phi) * rr)[:, None]
            Pn, _ = prog.project(Pd - d_phi * (0.0015 * skel.scale), d_phi, maxd=0.006 * skel.scale)
            good = np.abs(prog.eval(Pn)) < 2.0e-6
            V[rings[row]] = np.where(good[:, None], Pn, Pd) + d_phi * (share * proud)
    i = np.arange(N - 1)[:, None]
    k = np.arange(K)[None, :]
    k1 = (k + 1) % K
    Q = np.stack([rings[i, k], rings[i, k1], rings[i + 1, k1], rings[i + 1, k]], -1).reshape(-1, 4)
    mesh = QuadMesh(V, Q)
    v_s = list(Sg.ravel())                   # per vertex: its station on its branch and its angle (for the UVs)
    v_th = list(Tg.ravel())
    face_of = lambda ii, kk: ii * K + (kk % K)                                         # noqa: E731
    cut_faces = []
    for f in forks:
        i0 = int(np.argmin(np.abs(st - f['rings_s'][0])))
        i1 = int(np.argmin(np.abs(st - f['rings_s'][-1])))
        assert i1 - i0 == bb, (f['t'].name, i0, i1, 'the block is not b ring intervals: a ring fell inside it')
        f['i0'] = i0
        f['faces'] = [face_of(ii, f['k0'] + c) for ii in range(i0, i1) for c in range(f['ba'])]
        cut_faces += f['faces']
    # LOD0: every WHOLE ring of the beam above the seal's edge splits its sag where it climbs over a tine's root
    # or over a swell of the burr's rim (split_sag; a ring inside a block loses the block's columns and is not a
    # ring any more; the rim's rows stand out by their share of `low_proud` first)
    split = None
    if T.get('sag'):
        inside = {ii for f in forks for ii in range(f['i0'] + 1, f['i0'] + bb)}
        moved, before, after, most = 0, 0.0, 0.0, 0.0
        for ii in range(1, N):
            if ii in inside:
                continue
            Pn, (d0, d1, off) = split_sag(prog, mesh.V, rings[ii], T['sag'] * skel.scale)
            before, after = max(before, d0), max(after, d1)
            if off > 0.0:
                mesh.V[rings[ii]] = Pn
                moved, most = moved + 1, max(most, off)
        split = dict(rings_moved=moved, worst_depth_before_mm=round(before / mm, 3),
                     worst_depth_after_mm=round(after / mm, 3), largest_move_mm=round(most / mm, 3))
    # all the blocks leave together (face ids stay the tube's while I name them), then each hole's loop is found
    keep = np.ones(len(mesh.Q), bool)
    keep[cut_faces] = False
    mesh = QuadMesh(mesh.V, mesh.Q[keep])
    loops = loft.boundary_loop(mesh)
    labels = ['beam'] * len(mesh.Q)
    islands = dict(beam=dict(kind='tube', rings=rings, s=st, theta=th, branch='beam', burr_rows=len(burr_rows)))
    report = dict(K=K, rings_beam=N, forks={}, burr=T.get('burr', 'full'))
    if split:
        report['split_sag'] = split

    def on_form(br, s, ang):
        """ring points of a branch ON THE BLOCK-OUT (its own section pushed out along its radius: near a fork the
        form is the blend, a little outside the section; the first cage's reducer rings stood on the bare section
        there, inside the saddle, and folded 153 deg: build/look/h06_low_a.png). A buried foot keeps its section"""
        Pf, _, okf = HS.seat(prog, br, s, ang, maxd=0.03 * skel.scale)
        return np.where(okf[:, None], Pf, br.surface(s, ang))

    def grow(mesh, labels, name, ring_ids, col_of, br, s_of, th_of, s_start, s_end, r_cap, cls_frac=None):
        """a branch's shaft from an open ring: rings where the outline turns, a quad-grid cap. ring_ids: the ring
        to extend from, ordered so extend() runs against its faces; col_of: each vertex's column. Returns the mesh,
        the rows (id arrays), the cap grid, the stations"""
        Kr = len(ring_ids)
        ang = np.array([th_of[v] for v in ring_ids])
        ss = stations(br, s_start, s_end, Kr, tol, max_gap=gap_tine * skel.scale) if cls_frac is None else \
            s_start + cls_frac * (s_end - s_start)
        pos = [on_form(br, np.full(Kr, s), ang) for s in ss]
        n0 = len(mesh.V)
        mesh, ids = ports.extend(mesh, ring_ids, pos)
        for r_, s in enumerate(ss):
            for j in range(Kr):
                s_of[n0 + r_ * Kr + j] = s
                th_of[n0 + r_ * Kr + j] = ang[j]
        nq = len(mesh.Q)
        _, _, _, t_end = br.frame(ss[-1])
        shape = (Kr // 4, Kr // 4) if Kr % 4 == 0 else ((Kr // 2 + 1) // 2, Kr // 2 - (Kr // 2 + 1) // 2)
        mesh, G = loft.cap(mesh, ids[-1], t_end, dome=r_cap, shape=shape)
        labels += [name] * (nq - len(labels)) + [name + '.cap'] * (len(mesh.Q) - nq)
        return mesh, ids, G, ss

    s_of = {i_: v for i_, v in enumerate(v_s)}
    th_of = {i_: v for i_, v in enumerate(v_th)}
    templates = {}

    def ring_r(br, s):
        """a branch's mean section radius at station s (the K rule's radius)"""
        return float(np.mean(br.radius(float(np.clip(s, 0.0, br.length)), np.linspace(0.0, 2.0 * np.pi, 24,
                                                                                         endpoint=False))))

    def shaft_k(mesh, labels, name, E, br, s_end, r_cap, tilt=None, tmpl=None, margin=0.98):
        """LOD0's shaft (a tine's from its fork's ring C, or the beam's top past its last fork) from the open ring E
        (vertex ids in EXTEND ORDER: the faces before it run E[i] -> E[i + 1]; E[0] the column a UV seam runs up),
        rings where the outline turns (`stations`), each with the fewest columns of T['ring_K'] whose chord sag is
        under T['sag'] (reduce_mixed between two rings of different K), a quad-grid cap.
        tilt: (sigma0, tau(angle)) for a fork's tilted ring C: ring i's vertex at angle a stands at station
        sigma_i + w(sigma_i) tau(a), w falling from 1 at sigma0 to 0 over D = max(2 |tau|max, 1.5 r): every
        vertex's station then rises at least half as fast as the ring's mean (no ring runs back under the one
        before it, the tray's crossing), and the first ring stands 0.6 r past sigma0 (0.3 r clear on the high side).
        tmpl: a class template's (fractions of [first ring, s_end], K per ring): its members take its topology.
        Returns the mesh, the rings (extend order), K per ring, the stations, the reducers, the cap grid"""
        ks = T['ring_K']
        aE = np.array([th_of[int(v)] for v in E])
        if tilt is None:
            sig0, tau, D = float(np.mean([s_of[int(v)] for v in E])), (lambda a: np.zeros_like(a)), 1.0
        else:
            sig0, tau = tilt
            D = max(2.0 * float(np.abs(tau(aE)).max()), 1.5 * ring_r(br, sig0), 1.0e-3 * skel.scale)

        def st_at(sig, a):
            return sig + np.clip(1.0 - (sig - sig0) / D, 0.0, 1.0) * tau(a)
        sense0 = 1.0 if np.angle(np.exp(1j * (aE[1] - aE[0]))) > 0.0 else -1.0

        def depth(sg, K_):
            """how deep the edge midpoints of a ring of K_ columns at sg lie under the clay (its true chord sag: the
            formula on the mean radius read 0.30-0.33 mm where a flattened root ring measured 0.37-0.46)"""
            a = aE[0] + sense0 * np.arange(K_) * (2.0 * np.pi / K_)
            P = on_form(br, st_at(sg, a), a)
            return float(-prog.eval(0.5 * (P + np.roll(P, -1, axis=0))).min())
        r0_ = ring_r(br, sig0)
        sig1 = sig0 + (max(0.6 * r0_, 6.0 * mm) if tilt is not None else 0.0)
        if tmpl is None:
            if tilt is None:
                sig = stations(br, sig0, s_end, len(E), tol, max_gap=0.075 * skel.scale)[1:]
            else:
                sig = stations(br, sig1, s_end, len(E), tol, max_gap=0.075 * skel.scale)
            kk, k_prev = [], len(E)
            for sg in sig:
                k_ = next((K_ for K_ in sorted(ks) if K_ <= k_prev and depth(sg, K_) <= margin * T['sag'] * skel.scale),
                          k_prev)
                k_prev = min(k_prev, k_)
                kk.append(k_prev)
            # A REDUCER IS A SHORT BAND. Its quads ship split along their shorter diagonals: the middle quad (o1 o2
            # o3 m) must split along o2-m, so MID_PULL h < |o1 - o3| = 4 pi r / K_out; the inner quad (i0 m i2 i1)
            # along m-i1, so (1 - MID_PULL) h < |i0 - i2| = 4 pi r / K_in. Either split the wrong way ships a sliver
            # of three ring vertices lying in the ring's plane, folded 90-100 deg (this drawing's first runs: the
            # band 20-33 mm, then the 16 -> 12 inner quad at 14 mm). So h = 0.8 x the smaller bound on the inner
            # radius. A longer band gets one more ring of the LARGER K that short band below the ring that passed
            # the sag test with the smaller K (a ring of the smaller K inserted lower down, where the tine is
            # thicker, sagged 0.36-0.41 mm)
            sig2, kk2, k_prev, s_prev = [], [], len(E), sig0
            for sg, K_ in zip(sig, kk):
                if K_ < k_prev:
                    r_in = ring_r(br, sg)
                    h = 0.8 * min(4.0 * np.pi * r_in / (MID_PULL * k_prev), 4.0 * np.pi * r_in / ((1.0 - MID_PULL) * K_))
                    band = sg - s_prev
                    if band > h:
                        sig2.append(float(sg) - (0.5 * band if band <= 2.0 * h else h))
                        kk2.append(k_prev)
                sig2.append(float(sg))
                kk2.append(K_)
                k_prev, s_prev = K_, float(sg)
            sig, kk = np.array(sig2), kk2
        else:
            fr, kk = tmpl
            a_ = sig1 if tilt is not None else sig0
            sig = a_ + np.asarray(fr) * (s_end - a_)
            kk = list(kk)
        rings_, reds = [np.asarray(E)], []
        for sg, K_ in zip(sig, kk):
            nq = len(mesh.Q)
            if K_ == len(E):
                s_new = st_at(sg, aE)
                n0 = len(mesh.V)
                mesh, ids = ports.extend(mesh, E, [on_form(br, s_new, aE)])
                E = np.asarray(ids[-1])
                for j in range(len(E)):
                    s_of[n0 + j], th_of[n0 + j] = float(s_new[j]), float(aE[j])
            else:
                R = np.roll(np.asarray(E)[::-1], 1)                     # R[0] = E[0]; the faces use R backward
                aR = np.array([th_of[int(v)] for v in R])
                sense = 1.0 if np.angle(np.exp(1j * (aR[1] - aR[0]))) > 0.0 else -1.0
                aI = aR[0] + sense * np.arange(K_) * (2.0 * np.pi / K_)
                s_in = st_at(sg, aI)
                pat = reduce_pattern(len(R), K_)
                mesh, inner, mids, pairs = reduce_mixed(mesh, R, on_form(br, s_in, aI), pat)
                for j in range(K_):
                    s_of[int(inner[j])], th_of[int(inner[j])] = float(s_in[j]), float(aI[j])
                for m_, (o2, i1) in zip(mids, pairs):
                    s_of[int(m_)] = s_of[o2] + MID_PULL * (s_of[i1] - s_of[o2])
                    th_of[int(m_)] = th_of[o2]
                    mesh.V[int(m_)] = on_form(br, np.array([s_of[int(m_)]]), np.array([th_of[int(m_)]]))[0]
                reds.append(dict(row=len(rings_), mids=np.asarray(mids), pattern=''.join(pat), outer=R,
                                 inner=np.asarray(inner)))
                E = np.roll(np.asarray(inner)[::-1], 1)                 # extend order again, E[0] = inner[0]
                aE = np.array([th_of[int(v)] for v in E])
            labels += [name] * (len(mesh.Q) - nq)
            rings_.append(np.asarray(E))
        nq = len(mesh.Q)
        _, _, _, t_end = br.frame(float(sig[-1]))
        Kr = len(E)
        shape = (Kr // 4, Kr // 4) if Kr % 4 == 0 else ((Kr // 2 + 1) // 2, Kr // 2 - (Kr // 2 + 1) // 2)
        mesh, G = loft.cap(mesh, E, t_end, dome=r_cap, shape=shape)
        labels += [name + '.cap'] * (len(mesh.Q) - nq)
        a_ = sig1 if tilt is not None else sig0
        frac = (np.asarray(sig) - a_) / max(float(s_end - a_), 1e-12)
        return mesh, rings_, [len(rings_[0])] + list(kk), np.asarray(sig), reds, G, (frac, kk)
    for f in forks:
        t = f['t']
        blk = set(int(v) for ii in range(f['i0'], f['i0'] + bb + 1) for v in rings[ii, [(f['k0'] + c) % K
                                                                                       for c in range(f['ba'] + 1)]])
        loop = next(np.array(lp) for lp in loops if set(lp) <= blk and len(lp) == 2 * (f['ba'] + bb))
        Kc = len(loop)
        # THE SADDLE'S RINGS ARE LOOPS ROUND THE TINE (ports.extend: ring vertex j tied to loop vertex j, no
        # alignment search). The loop's vertices are read about the tine's own axis (its base frame carried
        # straight back into the beam): station along it, angle round it
        T0, n0_, b0_, base = t.T[0], t.n[0], t.b[0], t.P[0]
        qL = mesh.V[loop] - base
        sL = qL @ T0
        qL = qL - np.outer(sL, T0)
        aL = np.unwrap(np.arctan2(qL @ b0_, qL @ n0_))
        turn = 1.0 if aL[-1] > aL[0] else -1.0
        # ring C's angles: EVEN, in the loop's own sense, turned as a whole to lie nearest the loop's
        even = turn * np.arange(Kc) * (2.0 * np.pi / Kc)
        aC = even + np.angle(np.mean(np.exp(1j * (aL - even))))
        aC = aL + np.angle(np.exp(1j * (aC - aL)))
        # where the tine's own section clears the blend, per angle; ring C is the TILTED plane through those
        sc = np.zeros(Kc)
        probe = np.arange(0.4 * float(t.r0[0]), 0.6 * t.length, 0.002)
        for j, a in enumerate(aC):
            dd = pb.eval(t.surface(probe, np.full(len(probe), a)))
            clear = np.nonzero(dd > 0.85 * blend)[0]
            sc[j] = probe[clear[0]] if len(clear) else probe[-1]
        c1 = np.sum(sc * np.exp(-1j * aC)) * 2.0 / Kc
        s_c = sc.mean() + np.abs(c1) * np.cos(aC - (-np.angle(c1)))
        s_c = s_c + max(0.0, float((sc - s_c).max()))                 # the fitted plane, lifted clear everywhere
        # between the loop and ring C: each vertex where a ray from the tine's axis leaves the block-out, its
        # station and angle run evenly from the loop vertex's to ring C's. (A straight blend of the two loops
        # pushed to the nearest surface folded in the crotch: the tray's saddle 112 deg across a quad, and a loop
        # matched to ring C by distance crossed itself there: build/look/h06_low_a.png, tmp/h06_folds.png. Seen
        # from its axis a saddle is star-shaped: no fold.)
        ring_pos, ring_sa = [], []
        Pc = on_form(t, s_c, aC)
        for r_ in range(1, T['bridge'] + 1):
            h = r_ / (T['bridge'] + 1.0)
            s_r, a_r = sL + h * (s_c - sL), aL + h * (aC - aL)
            pa, na, ba_, _ = t.frame(np.maximum(s_r, 0.0))
            back = s_r < 0.0
            pa = np.where(back[:, None], base + np.outer(s_r, T0), pa)
            na = np.where(back[:, None], n0_, na)
            ba_ = np.where(back[:, None], b0_, ba_)
            dr = np.cos(a_r)[:, None] * na + np.sin(a_r)[:, None] * ba_
            Pn, _ = prog.project(pa, dr, maxd=0.12 * skel.scale)
            good = (np.abs(prog.eval(Pn)) < 2.0e-6) & (prog.eval(pa) < 0.0)
            ring_pos.append(np.where(good[:, None], Pn, (1.0 - h) * mesh.V[loop] + h * Pc))
            ring_sa.append((s_r, a_r))
        n0, nq = len(mesh.V), len(mesh.Q)
        mesh, ids = ports.extend(mesh, loop, ring_pos + [Pc])
        for r_, (s_r, a_r) in enumerate(ring_sa + [(s_c, aC)]):
            for j_ in range(Kc):
                s_of[n0 + r_ * Kc + j_], th_of[n0 + r_ * Kc + j_] = s_r[j_], a_r[j_]
        Bs = np.asarray(ids[-1])
        labels += [t.name + '.saddle'] * (len(mesh.Q) - nq)
        rows = [np.asarray(r_) for r_ in ids]                       # loop, bridge rings, C: aligned column by column
        isl = dict(kind='tine', branch=t.name, saddle=rows, cls=t.cls)
        if T.get('ring_K'):
            # LOD0 (fix round 1): the shaft starts AT ring C, un-tilting, K by the sag (shaft_k); E[0] is ring C's
            # vertex nearest the crotch (angle 0), the column the tine's UV seam runs up
            j0 = int(np.argmin(np.abs(np.angle(np.exp(1j * aC)))))
            E = np.roll(Bs, -j0)
            sig0 = float(s_c.mean())
            a_m = np.mod(aC, 2.0 * np.pi)
            o_ = np.argsort(a_m)
            A3 = np.concatenate([a_m[o_] - 2.0 * np.pi, a_m[o_], a_m[o_] + 2.0 * np.pi])
            T3 = np.tile((s_c - sig0)[o_], 3)
            tau = (lambda A3_, T3_: (lambda a: np.interp(np.mod(a, 2.0 * np.pi), A3_, T3_)))(A3, T3)
            r_end = float(t.meta['r_tip'])
            s_end = t.length - 0.8 * r_end
            tm = templates.get(t.cls) if (t.cls and t.cls != 'hero') else None
            # a class TEMPLATE's K table serves its members too (one topology to stack): its rings keep a 20 %
            # margin under the sag (crown_a, flatter than the bay, sagged 0.361 mm on the bay's table at 0.98)
            mesh, rings_, kr, sig, reds, G, tm_new = shaft_k(mesh, labels, t.name, E, t, s_end, 1.8 * r_end,
                                                             tilt=(sig0, tau), tmpl=tm,
                                                             margin=0.82 if (t.cls and t.cls != 'hero') else 0.98)
            if t.cls and t.cls != 'hero' and t.cls not in templates:
                templates[t.cls] = tm_new
            isl.update(shaft=rings_, K_rows=kr, reducers=reds, cap=G, s_shaft=sig, crotch=np.array([int(E[0])]),
                       tilt_mm=round(float(np.abs(s_c - sig0).max()) / mm, 1))
            islands[t.name] = isl
            report['forks'][t.name] = dict(block_s_mm=(round(f['s_lo'] / mm, 1), round(f['s_hi'] / mm, 1)),
                                           ring_c_mm=(round(float(s_c.min()) / mm, 1), round(float(s_c.max()) / mm, 1)),
                                           shaft_rings=len(sig), K_rows=kr,
                                           reducers=[(d_['row'], d_['pattern']) for d_ in reds])
            continue
        if Kc == 2 * Ks:
            # the reducer: the inner ring a little up the tine, half the tilt
            R = Bs[::-1]
            a_in = np.array([th_of[int(R[2 * j])] for j in range(Ks)])
            s_in = np.array([s_of[int(R[2 * j])] for j in range(Ks)])
            s_in = s_in.mean() + 0.45 * (s_in - s_in.mean()) + 0.55 * float(t.lerp(t.r0, s_c.mean()))
            n0 = len(mesh.V)
            nq = len(mesh.Q)
            mesh, inner = loft.reduce_ring(mesh, R, on_form(t, s_in, a_in))
            for j in range(Ks):
                s_of[n0 + j], th_of[n0 + j] = s_in[j], a_in[j]
            for u_ in range(Kc // 4):
                vm = n0 + Ks + u_
                s_o = s_of[int(R[(4 * u_ + 2) % Kc])]
                s_of[vm] = s_o + MID_PULL * (s_in[(2 * u_ + 1) % Ks] - s_o)
                th_of[vm] = th_of[int(R[(4 * u_ + 2) % Kc])]
                mesh.V[vm] = on_form(t, np.array([s_of[vm]]), np.array([th_of[vm]]))[0]
            labels += [t.name + '.saddle'] * (len(mesh.Q) - nq)
            start = np.asarray(inner)[::-1]
            isl['reducer'] = dict(outer=R, inner=np.asarray(inner), mids=np.arange(n0 + Ks, n0 + Ks + Kc // 4))
            s_top = float(s_in.max())
        else:
            start = Bs
            s_top = float(s_c.max())
        r_end = float(t.meta['r_tip'])
        s_end = t.length - 0.8 * r_end
        s_first = s_top + 0.5 * float(t.lerp(t.r0, s_top))
        frac = None
        if t.cls and t.cls != 'hero':
            if t.cls in templates:
                frac = templates[t.cls]
        mesh, ids2, G, ss = grow(mesh, labels, t.name, start, None, t, s_of, th_of, s_first, s_end,
                                 r_cap=1.8 * r_end, cls_frac=frac)
        if t.cls and t.cls != 'hero' and t.cls not in templates:
            templates[t.cls] = (ss - ss[0]) / (ss[-1] - ss[0])
        isl.update(shaft=[np.asarray(r_) for r_ in ids2], cap=G, s_shaft=ss)
        islands[t.name] = isl
        report['forks'][t.name] = dict(block_s_mm=(round(f['s_lo'] / mm, 1), round(f['s_hi'] / mm, 1)),
                                       ring_c_mm=(round(float(s_c.min()) / mm, 1), round(float(s_c.max()) / mm, 1)),
                                       shaft_rings=len(ss))
    # ---------------------------------------------------------------- the beam's top past its last fork
    last = rings[-1]
    # THE BEAM'S UV SEAM COLUMN (horn_uv.layout's rule, kept here so the top's reducers leave it straight): a column
    # no fork block's interior touches, a multiple of 4, nearest the back-medial side (225 deg)
    inner_cols = set()
    for f in forks:
        inner_cols |= {(f['k0'] + c_) % K for c_ in range(1, f['ba'])}
    cand = [k_ for k_ in range(0, K, 4 if K % 4 == 0 else 1) if k_ not in inner_cols]
    k_seam = min(cand, key=lambda k_: abs(np.angle(np.exp(1j * (th[k_] - 1.25 * np.pi))))) if cand else 0
    islands['beam']['k_seam'] = int(k_seam)
    if T.get('ring_K'):
        E = np.roll(last[::-1], -(K - 1 - k_seam))                 # extend order, E[0] = the seam column's vertex
        r_end = float(beam.meta['r_tip'])
        mesh, rings_, kr, sig, reds, G, _ = shaft_k(mesh, labels, 'beam_top', E, beam, beam.length - 0.8 * r_end,
                                                    1.8 * r_end)
        islands['beam_top'] = dict(kind='top', branch='beam', shaft=rings_, K_rows=kr, reducers=reds, cap=G,
                                   s_shaft=sig)
        report['beam_top'] = dict(K_rows=kr, rings=len(sig), reducers=[(d_['row'], d_['pattern']) for d_ in reds])
    elif K == 2 * Ks:
        s_in = st[-1] + 0.9 * float(beam.lerp(beam.r0, st[-1]))
        a_in = th[::2]
        n0 = len(mesh.V)
        nq = len(mesh.Q)
        mesh, inner = loft.reduce_ring(mesh, last, on_form(beam, np.full(Ks, s_in), a_in))
        for j in range(Ks):
            s_of[n0 + j], th_of[n0 + j] = s_in, a_in[j]
        for u_ in range(K // 4):
            vm = n0 + Ks + u_
            s_of[vm], th_of[vm] = st[-1] + MID_PULL * (s_in - st[-1]), th[(4 * u_ + 2) % K]
            mesh.V[vm] = on_form(beam, np.array([s_of[vm]]), np.array([th_of[vm]]))[0]
        labels += ['beam_top'] * (len(mesh.Q) - nq)
        islands['beam_top'] = dict(kind='top', branch='beam', reducer=dict(outer=last, inner=np.asarray(inner),
                                                                          mids=np.arange(n0 + Ks, n0 + Ks + K // 4)))
        start, s_first = np.asarray(inner)[::-1], s_in + 0.012 * skel.scale
    else:
        islands['beam_top'] = dict(kind='top', branch='beam')
        start, s_first = last[::-1], st[-1] + 0.012 * skel.scale
    if not T.get('ring_K'):
        r_end = float(beam.meta['r_tip'])
        mesh, ids2, G, ss = grow(mesh, labels, 'beam_top', start, None, beam, s_of, th_of, s_first,
                                 beam.length - 0.8 * r_end, r_cap=1.8 * r_end)
        islands['beam_top'].update(shaft=[np.asarray(r_) for r_ in ids2], cap=G, s_shaft=ss)
    # ---------------------------------------------------------------- the seal
    nq = len(mesh.Q)
    # (a ring of 6, LOD4's, is closed by a 2 x 1 grid: loft.cap's square grid needs K a multiple of 4)
    mesh, G = loft.cap(mesh, rings[0], -skel.z, dome=float(skel.meta.get('seal_dome', 0.0)),
                       shape=None if K % 4 == 0 else ((K // 2 + 1) // 2, K // 2 - (K // 2 + 1) // 2))
    labels += ['seal'] * (len(mesh.Q) - nq)
    islands['seal'] = dict(kind='cap', cap=G)
    # ---------------------------------------------------------------- compact (the blocks' inner vertices go)
    used = np.unique(mesh.Q)
    remap = np.full(len(mesh.V), -1, np.int64)
    remap[used] = np.arange(len(used))
    mesh = QuadMesh(mesh.V[used], remap[mesh.Q])

    def rm(x):
        if isinstance(x, dict):
            return {kk: rm(v) for kk, v in x.items()}
        if isinstance(x, list):
            return [rm(v) for v in x]
        if isinstance(x, np.ndarray) and x.dtype.kind == 'i' and x.ndim >= 1 and x.size and x.max() < len(remap):
            return remap[x]
        return x
    for nm in islands:
        for key in ('rings', 'saddle', 'shaft', 'cap', 'reducer', 'reducers', 'crotch'):
            if key in islands[nm]:
                islands[nm][key] = rm(islands[nm][key])
    n = len(mesh.V)
    s_arr, th_arr = np.zeros(n), np.zeros(n)
    for old, new in enumerate(remap):
        if new >= 0:
            s_arr[new], th_arr[new] = s_of.get(old, 0.0), th_of.get(old, 0.0)
    chk = mesh.check()
    lab = np.array(labels)
    tri = {nm: int(2 * (lab == nm).sum()) for nm in sorted(set(labels))}
    report.update(check=chk, quads=len(mesh.Q), tris=2 * len(mesh.Q), verts=n, tris_by_island=tri,
                  beam_stations_mm=(st / mm).round(1).tolist())
    log(f'[horn_cage] LOD{lod}: {2 * len(mesh.Q)} triangles, {n} vertices; check {chk}')
    return dict(mesh=mesh, labels=lab, islands=islands, report=report, s=s_arr, theta=th_arr, lod=lod)
