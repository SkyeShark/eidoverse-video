"""THE SCALE SKIN FAMILY (MONITOR_PLAN §5): a scale skin is a FUNCTION of the anatomical chart point (u, v) in life
millimetres -> height, and the scale INSTANCE the point belongs to (id, side, class, local position, distance to its
border). Everything else is read from that: the normal (the height's gradient), the groove mask (border distance),
the wear mask (height and local position), the tint and pattern (hash(id, side)).

PRIVATE COPY of the Komodo dragon's round (D2.2, 11-11, Fable 5.2): it lands as eidoverse/bestiary/forge/families/
scale_skin.py. New code (no scale generator exists in the forge: recipe.SCULPT_KINDS lists scales / plates / ridges
as planned). CPU, numpy + scipy.spatial.cKDTree; nothing here needs a GPU. The bake will call evaluate() on its
sub-samples' chart points (the beetle's MICRO layer does the same with stag_beetle_sculpt.relief).

THE ONE IDEA IN CODE
  plan(spec, seed)        ONE INSTANCE LIST on a chart: every scale a SITE (place, class, its own 2 x 2 frame in mm,
                          height, id). Built for v >= 0 only; the other half is its mirror (v = 0 is the dorsal
                          midline: "the body's halves stacked"), sites near the midline are snapped ONTO it.
  evaluate(plan, u, v)    per point: the nearest sites in EACH SITE'S OWN METRIC (a multiplicatively weighted Voronoi:
                          exponent 2 = ovals and polygons, 4 = rounded rectangles), the class's profile, and the
                          granules of the skin the scales leave. h(u, v) is computed at (u, |v|): the mirror is exact.
HOW THE SITES ARE LAID (what makes it read as skin and not as a stamp; each step is a real animal's doing):
  1. each region's lattice by its MEASURED steps (two basis vectors in mm: the adult's upper flank lattice of the
     check, MONITOR_PLAN §2.5), under a SIZE MAP across the chart (larger on the back, finer down the flank); ROWS
     (belly, tail rings, the hand) are laid row by row, every row its own width and every scale its own step, the
     rows bending together;
  2. BORDER BANDS seeded as rows whose scales shrink to granules and grow again (classes never cross-fade);
  3. a few sites removed and added (rows BREAK), then every free site moved to its cell's centre a few times (Lloyd
     in the sites' own metrics): rows bend round the breaks and lock into the lattices beside them;
  4. each scale's SIZE is read back from the room its neighbours leave it (its cell's area), then jittered.
Units: millimetres on the chart, heights in millimetres. Deterministic: one seed, the same arrays (G-S5).

FIX ROUND 1 (11-11, after the D2.2 check, research/monitor_notes/d22_check_NOTES.md): THE FIELD IS ONE SHEET. The
check measured h stepping at cell borders (dome / dome up to 0.44 mm, dome / granule 0.66, granule / ring 94 % of
borders over 0.05 mm): every cell's profile met its border at its OWN height. Now every point also gets a SHARED
GROUND G: softmin weights on the k candidates' metric distances (they hold no cell membership, so G is continuous
everywhere), each candidate's border level beta_j (a dome's skirt foot, a plate's in-row level or row groove, a young
bead's cushion), G = sum w_j beta_j; and each cell's own profile is LERPED to G over a band at its border, so at a
border both cells give G. Whether a border lies between ROWS is the row ids' weights (2R: 1 between rows, 0 within a
row), continuous too; the old switch on the nearest border's direction drew creases inside cells.

FIX ROUND 1, THIRD SITTING (11-12, Fable 5.2): WHAT A MONITOR'S SCALE IS, READ OFF THE PHOTOS AT x4 (c208's forearm
and hand, c168o's nape, J1): a raised scale whose smooth, glossy, pigmented CROWN is ringed by a FROSTED MARGIN of
tiny pale granules (the varanid's granule ring), with soil in the crease between scales. The build painted a clean
pill on a flat pale field. New, all off by default: `pig_t` / `pig_f` (the pigment ends at a level of the scale's own
crown, feathered and wobbling), `frost_on` (the skin granules also stand on whatever of the scale is not pigmented),
`metric_n` (a region's own cell exponent: 2 on a ROWS region = almond plates in a brick bond), `crease` / `cap_rim` /
`cap_h` (a dome's mounds meeting in a shallower valley, its cap in a low socket ring), and the spec's `wander`
(amp mm, cell mm): the field read at gently displaced points, so no cell border is a ruled line.
"""
import numpy as np
from scipy.spatial import cKDTree

GRANULE, BEAD, DOME, PLATE, WHORL, RIDGE = 0, 1, 2, 3, 4, 5
CLASS_NAMES = ('granule', 'bead', 'dome', 'plate', 'whorl', 'ridge')
CLASS_ID = {n: i for i, n in enumerate(CLASS_NAMES)}
METRIC_N = np.array([2.0, 2.0, 2.0, 4.0, 4.0, 4.0])            # the cell metric's exponent per class
TIER = ('T', 'T', 'S', 'T', 'T', 'S')                          # T = baked field, S = sculpt tier (§5.5)
HEX = np.array([[1.0, 0.5], [0.0, 0.8660254037844386]])        # a unit hexagonal lattice's basis (columns)
A_HEX = 2.0 * np.sqrt(3.0)                                      # area of a hexagon over (its mid-border half size)^2
TAU = 0.10                  # the shared ground's softmin width, in metric units (d = 1 at an ideal cell's mid border)
TAPER0 = 0.75               # (eighth sitting, 11-14) a candidate's weight tapers from 1 at this share of the k-th
                            # candidate's plain distance to 0 at it. THE k NEAREST ARE A SET THAT CHANGES INSIDE A CELL:
                            # a member leaving it with any weight stepped the ground, 2R, e and the soft least (the hand
                            # swatch: 509 steps up to 0.55 mm, 227 inside cells; the forearm 31 up to 0.038). The k-th
                            # distance is itself continuous, so a member weighs 0 as it goes (K_ROW, the 6 metric-nearest
                            # that decided 2R, is gone: 2R reads every candidate, tapered)


def hash_u32(x):
    """lowbias32: an integer hash any shader can repeat bit for bit (Warp / TSL: G-S5's second half, at D2.9)"""
    x = np.asarray(x, np.uint64) & 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x7FEB352D) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x846CA68B) & 0xFFFFFFFF
    x ^= x >> 16
    return x.astype(np.uint32)


def rand01(ids, salt=0):
    """a number in [0, 1) per (id, salt)"""
    return hash_u32(np.asarray(ids, np.int64) * 2654435761 + salt * 40503 + 12345).astype(np.float64) / 4294967296.0


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def smin(a, b, k):
    """a smooth minimum (polynomial, width k): no crease where two distance fields hand over"""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def vnoise(x, y, cell, salt):
    """a smooth value noise in [0, 1] (bilinear over hashed lattice points)"""
    gx, gy = np.asarray(x, float) / cell, np.asarray(y, float) / cell
    ix, iy = np.floor(gx).astype(np.int64), np.floor(gy).astype(np.int64)
    fx, fy = gx - ix, gy - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    r = lambda a, b: rand01(a * 7919 + b * 104729, salt)                                        # noqa: E731
    return ((1 - fx) * (1 - fy) * r(ix, iy) + fx * (1 - fy) * r(ix + 1, iy) + (1 - fx) * fy * r(ix, iy + 1) + fx * fy * r(ix + 1, iy + 1))


# ------------------------------------------------------------------------------------------------ seeding
def _seed_hex(reg, rng):
    """lattice points i a + j b under the region's size map k(v): u = uc + k(v) U, v = Vinv(V) (rows fan a little
    where the size changes: what a size gradient does on skin). Returns (xy, k, None)"""
    u0, u1, v0, v1 = reg['box']
    a, b = np.asarray(reg['a'], float), np.asarray(reg['b'], float)
    kf = reg.get('size_map')
    vv = np.linspace(0.0, max(v1, 1.0) + 20.0, 2000)
    kk = np.array([kf(x) for x in vv]) if kf else np.ones_like(vv)
    VV = np.concatenate([[0.0], np.cumsum(0.5 * (1.0 / kk[1:] + 1.0 / kk[:-1]) * np.diff(vv))])     # V(v) = int dv / k
    uc = 0.5 * (u0 + u1)
    R = int(2.5 * max(u1 - u0, v1 - v0) / min(np.linalg.norm(a), np.linalg.norm(b))) + 4
    ii, jj = np.meshgrid(np.arange(-R, R + 1), np.arange(-R, R + 1), indexing='ij')
    ph = reg.get('phase', (0.0, 0.0))
    U = ii * a[0] + jj * b[0] + ph[0]
    V = ii * a[1] + jj * b[1] + ph[1]
    ok = (V >= -1e-9) & (V <= VV[-1])
    U, V = U[ok], V[ok]
    v = np.interp(V, VV, vv)
    k = np.interp(v, vv, kk)
    u = uc + k * U
    w = reg.get('warp', 0.0)
    if w:
        # ROWS THAT BEND: a smooth displacement a few pitches long (a skin is never a ruled lattice: S2's and c274's
        # rows wander); none across the midline (the mirror stays exact), Lloyd then knits the cells to it
        pitch = np.sqrt(abs(np.linalg.det(np.column_stack([a, b]))))
        cell = reg.get('warp_cell', 8.0 * pitch)
        salt = int(reg.get('salt', 0))
        du = w * pitch * (2.0 * vnoise(u, v, cell, 60 + salt) - 1.0)
        dv = w * pitch * (2.0 * vnoise(u, v + 333.0, cell, 61 + salt) - 1.0) * smoothstep(0.0, 2.0 * pitch, v)
        u, v = u + du, v + dv
    keep = (u >= u0) & (u < u1) & (v >= v0) & (v < v1)
    # (sixth sitting, 11-13) A LATTICE'S OWN ROWS (`rows_along` = 'a' or 'b': the step the rows run along): the sites
    # that share the count along the OTHER step are one row. c208's forearm: its scales stand in arcing rows 60 px
    # a step along a row, the rows 44 px apart, the crease BETWEEN rows deep, dark and continuous, the one between
    # two scales of a row a thin line; a lattice whose every border is alike reads as a quilt. The row index feeds
    # the shared ground's 2R (evaluate), which is then returned as `rown` for this region's scales too
    lr = None
    ra = reg.get('rows_along')
    if ra in ('a', 'b'):
        lr = (ii if ra == 'b' else jj)[ok][keep]
        lr = lr - (lr.min() if len(lr) else 0)
    return np.column_stack([u[keep], v[keep]]), k[keep], None, lr


def _seed_rect(reg, rng):
    """ROWS (belly rows, tail rings, the hand's rows): a row is a strip across u; every row has ITS OWN width, every
    scale in it ITS OWN step along v, each row starts where it likes (a brick bond no machine laid), and the rows
    bend together (one smooth displacement field). Returns (xy, 1, frames, rows): frames = each scale's (width, step)
    mm; rows = each scale's row number (the shared ground's 2R: a border between rows, fix round 1)"""
    u0, u1, v0, v1 = reg['box']
    A, B = reg['pitch']
    wj, sj, bend = reg.get('row_width_jit', 0.10), reg.get('row_step_jit', 0.15), reg.get('row_bend', 0.22)
    ridge = bool(reg.get('ridge')) and v0 == 0.0
    # (fourth sitting, 11-12; c208's hand: its plates are 2.5 x 1.2 mm at one corner of the crop and 4.5 x 2.6 at the
    # other: a skin's scales GROW across a region, they are not one size): `grow_u` = (rate per mm, origin mm): the
    # rows' width times 1 + rate (u - origin); `grow_v` the same for the scales' step along a row. Absent = 1
    gu, gv = reg.get('grow_u'), reg.get('grow_v')
    fu = (lambda u_: float(np.clip(1.0 + gu[0] * (u_ - gu[1]), 0.45, 2.5))) if gu else (lambda u_: 1.0)
    fv = (lambda v_: float(np.clip(1.0 + gv[0] * (v_ - gv[1]), 0.45, 2.5))) if gv else (lambda v_: 1.0)
    xy, fr, rows = [], [], []
    u = u0
    while u < u1 - 0.35 * A:
        Ar = min(A * fu(u) * (1.0 + wj * (2.0 * rng.random() - 1.0)), u1 - u)
        if u1 - (u + Ar) < 0.35 * A:
            Ar = u1 - u
        uc = u + 0.5 * Ar
        if ridge:                                               # the crest: one narrow scale ON the midline in every ring
            edges = [-0.3 * B, 0.3 * B]
        elif v0 == 0.0:                                         # a scale astride the midline (the vertebral row)
            edges = [-0.5 * B * (1.0 + sj * (2.0 * rng.random() - 1.0))]
            edges.append(-edges[0])
        else:
            edges = [v0 - B * rng.random()]
            edges.append(edges[0] + B * fv(edges[0]) * (1.0 + sj * (2.0 * rng.random() - 1.0)))
        while edges[-1] < v1:
            edges.append(edges[-1] + B * fv(edges[-1]) * (1.0 + sj * (2.0 * rng.random() - 1.0)))
        e = np.array(edges)
        c, w = 0.5 * (e[1:] + e[:-1]), np.diff(e)
        keep = (c >= v0 - 1e-9) & (c < v1)
        xy.append(np.column_stack([np.full(keep.sum(), uc), np.maximum(c[keep], 0.0)]))
        fr.append(np.column_stack([np.full(keep.sum(), Ar), w[keep]]))
        rows.append(np.full(int(keep.sum()), len(rows)))
        u += Ar
    xy, fr, rows = np.concatenate(xy), np.concatenate(fr), np.concatenate(rows)
    salt = int(reg.get('salt', 0))
    du = bend * A * (2.0 * vnoise(xy[:, 0], xy[:, 1], reg.get('bend_cell', 28.0), 40 + salt) - 1.0)
    du *= smoothstep(0.0, 1.5 * A, np.minimum(xy[:, 0] - u0, u1 - xy[:, 0]))       # the region's own ends stay put
    xy[:, 0] += du
    return xy, np.ones(len(xy)), fr, rows


def _seed_band(band, rng):
    """a BORDER BAND: rows parallel to it whose pitch runs from one neighbour's size down to a granule's and up to the
    other neighbour's: each row its own 1-D lattice (the right number of scales everywhere), every site then knocked
    off its row; Lloyd knits them into an even, unordered pavement"""
    u0, u1, v0, v1 = band['box']
    across = band['across']                                    # 'u' or 'v': the direction ACROSS the band
    t0, t1 = (u0, u1) if across == 'u' else (v0, v1)
    l0, l1 = (v0, v1) if across == 'u' else (u0, u1)
    s_lo, s_mid, s_hi = band['sizes']

    def size(t):
        x = (t - t0) / (t1 - t0)
        w = abs(2.0 * x - 1.0) ** 1.4
        return s_mid + ((s_lo if x < 0.5 else s_hi) - s_mid) * w
    pts, sz = [], []
    t = t0 + 0.45 * size(t0)
    while t < t1 - 0.3 * size(t1):
        s = size(t)
        on_mid = across == 'u' and l0 == 0.0                    # the band crosses the midline: its vertebral granule first
        ls = np.arange((0.0 if on_mid else l0 + s * rng.random()), l1, s)
        tt = t + 0.30 * s * (2.0 * rng.random(len(ls)) - 1.0)
        jl = 0.30 * s * (2.0 * rng.random(len(ls)) - 1.0)
        if on_mid:
            jl[0] = 0.0
            jl[1:] = np.maximum(jl[1:], -0.15 * s)
        ls = ls + jl
        ok = (ls >= l0) & (ls < l1) & (tt >= t0) & (tt < t1)
        pts.append(np.column_stack([tt[ok], ls[ok]]) if across == 'u' else np.column_stack([ls[ok], tt[ok]]))
        sz.append(np.full(int(ok.sum()), s))
        t += 0.866 * 0.5 * (s + size(min(t + 0.866 * s, t1)))
    return np.concatenate(pts), np.concatenate(sz)


def _bend_frame(reg):
    """(the rows' direction d, its normal, the box's middle) of a region's BEND: rows along `bend_dir` (deg from +u;
    a lattice's default 0, a ROWS region's 90: its rows run along v)"""
    t = np.radians(reg.get('bend_dir', 0.0 if 'a' in reg else 90.0))
    u0, u1, v0, v1 = reg['box']
    # (fix round 2, `bend_c`: the bend's centre (u, v) mm; default the box's middle. ON THE MIDLINE (v = 0, the bend
    # along v) a bend is mirror-symmetric: the displacement bend v^2 along the body is even in v and the frames' turn
    # atan(2 bend v) odd, as h(u, |v|) and the mirror ghosts' frames need, and both are 0 on the midline: the trunk's
    # rows arc across the back as a real one's do, and its beads turn with them (the check's round 2, F3: on the plate
    # every bead lay one way, R 0.99))
    c = np.asarray(reg['bend_c'], float) if 'bend_c' in reg else np.array([0.5 * (u0 + u1), 0.5 * (v0 + v1)])
    return np.array([np.cos(t), np.sin(t)]), np.array([-np.sin(t), np.cos(t)]), c


def _bend(reg, p):
    """ROWS THAT ARC (round a joint: c208's forearm toward the wrist, the hand's rows round the knuckles): the rows
    bow by bend * s^2 along their normal (s = mm along them from the box's middle; a radius of 1 / (2 bend)). Each
    site's FRAME turns with its row (`_bend_turn`): left square to the chart, a 40 deg arc shears every cell. Not for
    a region on the midline (the mirror would fold the arcs) UNLESS its centre `bend_c` lies on the midline and the
    bend runs along v (fix round 2: then it is mirror-symmetric, `_bend_frame` says why)"""
    bend = reg.get('bend', 0.0)
    if not bend:
        return p
    d, nrm, c = _bend_frame(reg)
    s = (p - c) @ d
    return p + bend * (s * s)[:, None] * nrm[None, :]


def _bend_turn(reg, p):
    """the angle (rad) each site's frame turns by: its row's tangent at s, atan(2 bend s)"""
    bend = reg.get('bend', 0.0)
    if not bend:
        return np.zeros(len(p))
    d, _, c = _bend_frame(reg)
    return np.arctan(2.0 * bend * ((p - c) @ d))


# ------------------------------------------------------------------------------------------------ the sites' metrics
def _pack(xy, M, cls, mid, ghost_reach, mn=None):
    """the search structure: the sites and the MIRROR GHOSTS of those near the midline (so cells and the field are
    symmetric across v = 0). W = the inverse of half the site's frame: |W (x - site)|_n = 1 on an ideal cell's mid border.
    mn: each site's own metric exponent (a region's `metric_n`); None = its class's"""
    W = 2.0 * np.linalg.inv(M)
    g = np.nonzero((xy[:, 1] < ghost_reach) & ~mid)[0]
    S = np.diag([1.0, -1.0])
    xy_e = np.concatenate([xy, xy[g] * np.array([1.0, -1.0])])
    W_e = np.concatenate([W, W[g] @ S])
    src = np.concatenate([np.arange(len(xy)), g])
    ghost = np.concatenate([np.zeros(len(xy), bool), np.ones(len(g), bool)])
    n_e = (METRIC_N[cls] if mn is None else mn)[src]
    # one contiguous row a site (x, y, W row by row, n): `_nearest` gathers it in one go (fix round 1, the speed)
    block = np.ascontiguousarray(np.column_stack([xy_e, W_e.reshape(-1, 4), n_e]))
    return dict(xy=xy_e, W=W_e, src=src, ghost=ghost, n=n_e, tree=cKDTree(xy_e), site_block=block)


def _nearest(P, X, k=12, full=True, cand=False):
    """per point: its scale = the nearest site in the sites' OWN metrics (found among the k nearest by plain
    distance). Returns the packed index i1, the metric distance d1, the point's local coordinates in that site's
    frame, and (full) e = millimetres to the cell's border with the step to the neighbour beyond it.
    e IS THE LEAST OVER ALL NEIGHBOURS of 0.25 (d_j - d1) |site_j - site_1| (exact between two equal scales): taken
    from the SECOND nearest alone it jumps where the second nearest changes, and every profile built on it showed a
    crease running from each cell's corner to its middle (seen on the first plate).
    cand=True also returns the k candidates (packed indices) and their metric distances (the shared ground's input).
    FIX ROUND 1 (Skye: "make sure they're also optimized as best you can"): the tree's query on every core
    (`workers=-1`, the same answer), and the two metrics' exponents by products and square roots, not array powers."""
    k = min(k, len(P['xy']))
    dist, idx = P['tree'].query(X, k=k, workers=-1)
    tap = 1.0 - smoothstep(TAPER0, 1.0, dist / np.maximum(dist[:, -1:], 1e-12))     # (eighth sitting: TAPER0)
    Sb = P['site_block'][idx]                       # one gather: x, y, W00, W01, W10, W11, n of each candidate
    dx0, dx1 = X[:, 0, None] - Sb[..., 0], X[:, 1, None] - Sb[..., 1]
    xi = Sb[..., 2] * dx0 + Sb[..., 3] * dx1
    et = Sb[..., 4] * dx0 + Sb[..., 5] * dx1
    a2, b2 = xi * xi, et * et
    d = np.where(Sb[..., 6] > 3.0, np.sqrt(np.sqrt(a2 * a2 + b2 * b2)), np.sqrt(a2 + b2))   # exponent 4 or 2 (METRIC_N)
    r = np.arange(len(X))
    o1 = np.argmin(d, axis=1)
    i1, d1 = idx[r, o1], d[r, o1]
    if not full:
        return i1, d1
    own_xy = P['xy'][i1]
    sx = np.stack([Sb[..., 0] - own_xy[:, 0, None], Sb[..., 1] - own_xy[:, 1, None]], -1)
    ej = 0.25 * (d - d1[:, None]) * np.hypot(sx[..., 0], sx[..., 1])
    ej[r, o1] = np.inf
    ej = np.where(tap > 0.0, ej / np.maximum(tap, 1e-12), np.inf)     # (eighth sitting) a leaving candidate is never the least
    o2 = np.argmin(ej, axis=1)
    e, ds = ej[r, o2], sx[r, o2]
    if 'adj_block' in P:
        # THE BORDER'S NEIGHBOUR MAY LIE BEYOND THE k NEAREST (fix round 1): twelve small granules can crowd out the
        # bead beyond a trunk bead's nearest border (the jump finder: e jumped 3.25 -> 3.72 mm inside a bead by the
        # tail-base band; k = 24 gave 3.25). e is the least over the k nearest AND the cell's own neighbours (P['adj'],
        # read off a label raster in plan()). A neighbour j outside the k nearest lies farther than the k-th, dist_k,
        # and its border at least dist_k - (its circumradius) away: where that bound is under e, the neighbours'
        # block is gathered and taken in; elsewhere none of them can be nearer, so the least is the k nearest's
        # (EIGHTH SITTING, 11-14: THE CELL'S NEIGHBOURS ARE TAKEN IN AT EVERY POINT. The bound above holds only where a
        # cell is no larger than its frame; where a bend or a growth stretches cells past their frames it let points
        # through whose border neighbour was hidden, and e jumped inside the cell: with the bound, the hand swatch kept
        # 90 steps in its proper cells (54 over 0.05 mm), without it 0 inside any cell. A cell's neighbours are one set
        # inside the cell, so e is continuous there and 0 at every border. It costs a quarter to a third of evaluate()'s
        # speed (d22_NOTES.md, eighth sitting); `circ_adj` stays for a cheaper exact bound, not written yet)
        risky = np.arange(len(X))
        if len(risky):
            Ab = P['adj_block'][i1[risky]]              # one gather: neighbours' x, y, W row by row, n, real slot
            xr = X[risky]
            dxa0, dxa1 = xr[:, 0, None] - Ab[..., 0], xr[:, 1, None] - Ab[..., 1]
            xa = Ab[..., 2] * dxa0 + Ab[..., 3] * dxa1
            ya = Ab[..., 4] * dxa0 + Ab[..., 5] * dxa1
            a2, b2 = xa * xa, ya * ya
            da = np.where(Ab[..., 6] > 3.0, np.sqrt(np.sqrt(a2 * a2 + b2 * b2)), np.sqrt(a2 + b2))
            sa = np.stack([Ab[..., 0] - own_xy[risky, 0, None], Ab[..., 1] - own_xy[risky, 1, None]], -1)
            ea = np.where(Ab[..., 7] > 0.5, np.maximum(0.25 * (da - d1[risky, None]) * np.hypot(sa[..., 0], sa[..., 1]), 0.0), np.inf)
            oa = np.argmin(ea, axis=1)
            ra = np.arange(len(risky))
            better = ea[ra, oa] < e[risky]
            e[risky[better]] = ea[ra, oa][better]
            ds[risky[better]] = sa[ra, oa][better]
    res = (i1, d1, xi[r, o1], et[r, o1], e, ds)
    # (third sitting: cand=True also returns ej, each candidate's own border distance (inf for the point's own scale):
    # the input of a SOFT least distance, `soft_e`)
    return res + (idx, d, ej, tap) if cand else res


def _adjacency(P, U, Vh, reach, step):
    """every cell's neighbours (packed indices, the mirror ghosts included), read off a raster of the cells' labels at
    `step` mm over u 0..U, v -reach..Vh: two raster points up to TWO steps apart (across, down, diagonal) with
    different labels make a pair, so an edge shorter than the step near a corner is still found (a cell two steps
    beyond a thin sliver may be listed too: harmless, e is a least). Returns an (n packed, most neighbours) array padded
    with -1, and sets P['adj_block'] and P['circ_adj'] for `_nearest` (fix round 1)"""
    gu = np.arange(0.5 * step, U, step)
    gv = np.arange(-reach + 0.5 * step, Vh, step)
    Gp = np.stack(np.meshgrid(gu, gv, indexing='xy'), -1).reshape(-1, 2)
    lab = np.concatenate([_nearest(P, Gp[s:s + 200000], full=False)[0] for s in range(0, len(Gp), 200000)])
    lab = lab.reshape(len(gv), len(gu))
    pa, pb = [], []
    Hh, Ww = lab.shape
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1), (0, 2), (2, 0), (2, 1), (1, 2), (2, -1), (1, -2), (2, 2), (2, -2)):
        a = lab[0:Hh - dy, max(0, -dx):Ww - max(0, dx)]
        b = lab[dy:Hh, max(0, dx):Ww - max(0, -dx)]
        m = a != b
        pa.append(a[m])
        pb.append(b[m])
    pa, pb = np.concatenate(pa), np.concatenate(pb)
    n = len(P['xy'])
    key = np.unique(np.concatenate([pa * n + pb, pb * n + pa]))           # each pair both ways, once (sorted by cell)
    pr = np.column_stack([key // n, key % n])
    deg = np.bincount(pr[:, 0], minlength=n)
    adj = np.full((n, max(int(deg.max()), 1)), -1, np.int64)
    start = np.concatenate([[0], np.cumsum(deg)[:-1]])
    col = np.arange(len(pr)) - start[pr[:, 0]]
    adj[pr[:, 0], col] = pr[:, 1]
    # the same as ONE CONTIGUOUS BLOCK a cell (Skye: "optimized as best you can": one gather a point instead of four):
    # each neighbour's x, y, its W row by row, its metric's exponent, and 1 where the slot is real
    ok = adj >= 0
    aj = np.where(ok, adj, 0)
    block = np.concatenate([P['xy'][aj], P['W'][aj].reshape(n, -1, 4), P['n'][aj][..., None], ok[..., None].astype(float)], -1)
    P['adj_block'] = np.ascontiguousarray(block)
    # each cell's neighbours' largest CIRCUMRADIUS (mm): 1.3 / the smallest singular value of W (W = 2 M^-1; a corner
    # of a cell lies at metric 1.15 (hexagon) to 1.19 (exponent-4 square) times the frame's half axis)
    circ = 1.3 / np.linalg.svd(P['W'], compute_uv=False)[:, -1]
    P['circ_adj'] = np.where(ok, circ[aj], 0.0).max(axis=1)
    P['cell_area'] = np.bincount(lab.ravel(), minlength=n) * step * step     # mm2 a cell, off the same raster
    return adj


# ------------------------------------------------------------------------------------------------ the plan
def plan(spec, seed=1, log=print):
    """the instance list of a chart. spec: dict(size=(U, Vhalf), regions=[...], bands=[...], micro=dict(...)).
    A region: dict(name, cls, box=(u0, u1, v0, v1), and 'a', 'b' (a lattice's two steps, mm) or 'pitch'=(A, B) (rows),
    relief (mm; a dome's: a share of its spacing), cover, elong, jitter, size_jit, h_jit, turn (deg), size_map(v),
    defects (share), ridge (mm: the crest's teeth on the midline row), free (bool)).
    A band: dict(box, across='u'|'v', sizes=(lo, mid, hi), relief (a share of each granule's size))."""
    rng = np.random.default_rng(seed)
    U, Vh = spec['size']
    xy, k0, reg_i, isband, frames, rowv, lrow = [], [], [], [], [], [], []
    for r, reg in enumerate(spec['regions']):
        lr = None                                               # (sixth sitting) a lattice's own row index (`rows_along`)
        if 'a' in reg:
            p, k, fr, lr = _seed_hex(reg, rng)
            rw = None
        else:
            p, k, fr, rw = _seed_rect(reg, rng)
        p = _bend(reg, p)
        if 'a' in reg and reg['box'][2] == 0.0 and reg.get('vertebral', True):
            # A VERTEBRAL ROW: scales astride the midline all along it. Without it the two mirrored lattices meet in a
            # ruler-straight groove down the back (seen on the first plate): the one line a real skin never draws
            kf = reg.get('size_map')
            k_mid = kf(0.0) if kf else 1.0
            pu = k_mid * np.sqrt(abs(np.linalg.det(np.column_stack([reg['a'], reg['b']])))) * 1.05
            far = p[:, 1] > 0.80 * pu
            um = np.arange(reg['box'][0] + pu * rng.random(), reg['box'][1], pu)
            p = np.concatenate([p[far], np.column_stack([um, np.zeros(len(um))])])
            k = np.concatenate([k[far], np.full(len(um), k_mid)])
            if lr is not None:                                  # a vertebral scale is its own row
                lr = np.concatenate([lr[far], np.full(len(um), -1)])
        nd = int(round(reg.get('defects', 0.0) * len(p)))
        if nd:                                                  # rows BREAK: a few scales lost, a few squeezed in
            keep = np.ones(len(p), bool)
            keep[rng.choice(len(p), nd, replace=False)] = False
            u0, u1, v0, v1 = reg['box']
            add = np.column_stack([rng.uniform(u0 + 3, u1 - 3, nd), rng.uniform(v0 + 3, v1 - 3, nd)])
            o = np.argsort(p[:, 1])
            p, k = np.concatenate([p[keep], add]), np.concatenate([k[keep], np.interp(add[:, 1], p[o, 1], k[o])])
            if rw is not None:                                  # a squeezed-in scale belongs to no row
                rw = np.concatenate([rw[keep], np.full(nd, -1)])
                fr = np.concatenate([fr[keep], np.repeat(np.median(fr, axis=0)[None], nd, axis=0)])
            if lr is not None:
                lr = np.concatenate([lr[keep], np.full(nd, -1)])
        xy.append(p)
        k0.append(k)
        frames.append(fr if fr is not None else np.zeros((len(p), 2)))
        reg_i.append(np.full(len(p), r))
        isband.append(np.zeros(len(p), bool))
        rowv.append(np.full(len(p), -1) if rw is None else rw)
        lrow.append(np.full(len(p), -1) if lr is None else lr)
    nreg = len(spec['regions'])
    for b, band in enumerate(spec.get('bands', [])):
        p, s = _seed_band(band, rng)
        xy.append(p)
        k0.append(np.ones(len(p)))
        frames.append(np.column_stack([s, s]))
        reg_i.append(np.full(len(p), nreg + b))
        isband.append(np.ones(len(p), bool))
        rowv.append(np.full(len(p), -1))
        lrow.append(np.full(len(p), -1))
    xy, k0, reg_i, isband, frames, rowv = (np.concatenate(xy), np.concatenate(k0), np.concatenate(reg_i),
                                           np.concatenate(isband), np.concatenate(frames), np.concatenate(rowv))
    lrow = np.concatenate(lrow)
    N = len(xy)
    # each scale's ROW ID (fix round 1): a ROWS region's row, else the scale alone (the shared ground's 2R);
    # (sixth sitting) a lattice region's own rows (`rows_along`) are rows too, in a number range of their own
    row_id = np.where(rowv >= 0, (reg_i + 1) * 100000 + rowv, 1000000000 + np.arange(N)).astype(np.int64)
    row_id = np.where((rowv < 0) & (lrow >= 0), (reg_i + 1) * 100000 + 50000 + lrow, row_id).astype(np.int64)
    cls = np.zeros(N, np.int64)
    M0 = np.zeros((N, 2, 2))                                    # the nominal frame (lattice cell -> mm), before size
    free = np.ones(N, bool)
    mn = np.zeros(N)                                            # each site's metric exponent (0 = its class's, below)
    for r, reg in enumerate(spec['regions']):
        m = reg_i == r
        cls[m] = CLASS_ID[reg['cls']]
        mn[m] = reg.get('metric_n', 0.0)
        if 'a' in reg:
            M0[m] = np.column_stack([reg['a'], reg['b']]) @ np.linalg.inv(HEX)
            if 'iso_dir' in reg:
                # A ROUND FRAME ON THE SAME LATTICE (third sitting, `iso_dir` deg: where the frame's first axis points):
                # the frame [a b] HEX^-1 makes every cell the image of a regular hexagon, which on a lattice whose steps
                # are far from 60 degrees apart is NOT its sites' plain Voronoi cell (c208's forearm: cells 1.9 x long
                # across the rows; the photo's pads 1.35 x long ALONG them). A round frame of the same area gives the
                # plain cells: what skin grown round those sites is
                s_iso = np.sqrt(abs(np.linalg.det(M0[m][0])))
                ti = np.radians(reg['iso_dir'])
                # (fix round 2, `iso_el`: the frame stretched along `iso_dir` by this much, its area kept; 1 = round.
                # c208's scales are 1.3-1.5 x longer along their rows, and the round cells of its skewed lattice meet
                # the next row in a STAIRCASE (a long edge nearly along the row, then a short step 52 deg off it):
                # the soil between rows drew a zigzag where the photo's row creases are smooth scalloped arcs. A frame
                # long along the row turns those border edges toward the row)
                el = float(reg.get('iso_el', 1.0))
                M0[m] = s_iso * (np.array([[np.cos(ti), -np.sin(ti)], [np.sin(ti), np.cos(ti)]]) @ np.diag([el, 1.0 / el]))
        else:
            M0[m, 0, 0], M0[m, 1, 1] = frames[m, 0], frames[m, 1]
        if reg.get('bend'):                                     # each frame turns with its arcing row
            bt = _bend_turn(reg, xy[m])
            cb, sb_ = np.cos(bt), np.sin(bt)
            Rb = np.stack([np.stack([cb, -sb_], -1), np.stack([sb_, cb], -1)], -2)
            M0[m] = Rb @ M0[m]
        free[m] = reg.get('free', 'a' in reg)
    M0[isband, 0, 0] = M0[isband, 1, 1] = frames[isband, 0]
    mn = np.where(mn > 0, mn, METRIC_N[cls])
    # the cell's nominal area: a lattice's hexagon (A_HEX / 4 of its frame), a ROWS region's rectangle whatever its
    # metric (the rows are laid as strips: an exponent-2 plate's cell is still its row's width by its step)
    rows_reg = rowv >= 0
    area0 = np.abs(np.linalg.det(M0)) * np.where((METRIC_N[cls] > 2.0) | rows_reg, 1.0, A_HEX / 4.0) * k0 ** 2
    # ---- sites near the midline go ONTO it (one scale astride the midline, never two half scales)
    hv = 0.5 * np.sqrt(area0)
    mid = xy[:, 1] < 0.32 * hv
    xy[mid, 1] = 0.0
    low = (~mid) & (xy[:, 1] < 0.62 * hv) & free
    xy[low, 1] = 0.62 * hv[low]
    ridge_reg = [r for r, reg in enumerate(spec['regions']) if reg.get('ridge')]
    for r in ridge_reg:
        cls[(reg_i == r) & mid] = RIDGE
    # a site whose cell runs off the chart is pinned and keeps its nominal size (Lloyd would pull the rim inward)
    edge = ((xy[:, 0] < 0.9 * np.sqrt(area0)) | (xy[:, 0] > U - 0.9 * np.sqrt(area0)) | (xy[:, 1] > Vh - 0.9 * np.sqrt(area0)))
    free &= ~edge
    # ---- Lloyd in the sites' own metrics: the free sites move to their cells' centres; sizes follow the cells
    size = k0.copy()
    h = spec.get('relax_raster', 0.25)
    gu, gv = np.meshgrid(np.arange(0.5 * h, U, h), np.arange(0.5 * h, Vh, h), indexing='xy')
    G = np.column_stack([gu.ravel(), gv.ravel()])
    reach = 2.5 * float(np.sqrt(area0.max()))
    n_it = spec.get('relax', 4)
    for it in range(n_it + 1):
        P = _pack(xy, M0 * size[:, None, None], cls, mid, reach, mn)
        i1 = np.concatenate([_nearest(P, G[s:s + 200000], full=False)[0] for s in range(0, len(G), 200000)])
        own = P['src'][i1]
        real = ~P['ghost'][i1]
        cnt = np.bincount(own[real], minlength=N).astype(float)
        area = cnt * h * h
        area[mid] *= 2.0                                        # a midline scale's other half lies under v < 0
        have = cnt > 3
        if it == n_it:
            break
        cu = np.bincount(own[real], weights=G[real, 0], minlength=N) / np.maximum(cnt, 1)
        cv = np.bincount(own[real], weights=G[real, 1], minlength=N) / np.maximum(cnt, 1)
        mv = free & have
        xy[mv, 0] = cu[mv]
        xy[mv & ~mid, 1] = cv[mv & ~mid]
        s_new = np.sqrt(np.maximum(area, 1e-9) / np.maximum(area0 / k0 ** 2, 1e-9))
        size[mv] = np.clip(0.5 * size[mv] + 0.5 * s_new[mv], 0.35 * k0[mv], 1.6 * k0[mv])
    s_fin = np.sqrt(np.maximum(area, 1e-9) / np.maximum(area0 / k0 ** 2, 1e-9))
    size = np.where(free & have, np.clip(s_fin, 0.35 * k0, 1.6 * k0), size)
    # ---- each instance's own numbers: place jitter, turn, size, height (all from its id: the list is the data).
    # `hash_salt` (spec) gives another skin on the SAME layout (the mirror seam's "unique" half: the same rows, its
    # own scale-by-scale randomness); a midline scale keeps salt 0, so both halves share it whole
    ids = np.arange(N)
    hs = int(spec.get('hash_salt', 0))
    if hs:
        ids = np.where(mid, ids, ids + hs * 1000003)
    keys = (('jitter', 0.08), ('size_jit', 0.08), ('h_jit', 0.15), ('turn', 5.0), ('relief', 0.5), ('cover', 0.9),
            ('elong', 1.0), ('gap', 0.4), ('shift', 0.0), ('grain', 0.012), ('moat', 0.0), ('plinth_h', 0.06),
            ('keel', 0.05), ('bead_p', 2.0), ('elong_jit', 0.10), ('bead_ax', 0.0), ('lens', 0.0), ('shift_jit', 0.0),
            ('mound_h', 0.0), ('mound_r', 0.9), ('shift_c', 0.0), ('imbricate', -1.0), ('spot', 0.0),
            ('row_groove', 0.45), ('inrow', 0.0),
            # FIX ROUND 1, THE LOOK (the check: "a stamped pattern": tops half as varied in size, all one way, flat
            # inside). Each 0 / its old value = off. bead_turn (deg): the bead turned in its cell; cover_jit / gap_jit:
            # the bead's size in its cell and its collar's width, per scale; bead_pp / bead_q: the crown's section
            # (2.0 / 0.5 = the old flat-topped pebble; rounder with q near 1); lean: the crown tilted across the bead;
            # wrinkle (mm): keratin wrinkles streaked along the scale (wrinkle_len / wrinkle_w mm); cap_elong / cap_jit
            # / cap_turn: a dome's cap elongated along the body, its size and turn per scale; crumple (share of H):
            # a dome's mound crumpled; pillow_p / pillow_c: a plate's pillow lower at its corners (scalloped rows)
            ('bead_turn', 0.0), ('cover_jit', 0.0), ('gap_jit', 0.0), ('bead_pp', 2.0), ('bead_q', 0.5),
            ('lean', 0.0), ('wrinkle', 0.0), ('wrinkle_len', 1.2), ('wrinkle_w', 0.25), ('cap_elong', 1.0),
            ('cap_jit', 0.0), ('cap_turn', 0.0), ('crumple', 0.0), ('pillow_p', 2.0), ('pillow_c', 0.0),
            ('turn_field', 0.0), ('turn_cell', 30.0), ('cover_fit', 0.0), ('ramp', 0.0), ('pig', 0.0), ('pig_jit', 0.0),
            ('edge_w', 0.0),
            # (resumed 14:4x) cush / cush_jit: a plate's or ring's PIGMENTED CUSHION, the raised face's colour inside
            # the level `cush` of its own metric (0 = the old face to its border); mark_at / mark_len / mark_w /
            # mark_jit: a ring scale's dark mark (and its pit): where along the scale, how long and how wide, and how
            # much each scale's own differs (the defaults are the old mark)
            ('cush', 0.0), ('cush_jit', 0.0), ('mark_at', 0.45), ('mark_len', 0.22), ('mark_w', 0.75), ('mark_jit', 0.0),
            ('cush_et', 1.0),
            # (third sitting, the module's header) pig_t / pig_f: the pigment ends at the level `pig_t` of the scale's
            # own crown (a bead's t: 0 at its edge, about 1 at its middle; a plate's: mm from its border over its half
            # size), feathered by `pig_f`, its edge wobbling, each scale its own (`pig_jit`); frost_on: the skin
            # granules also stand on the scale's unpigmented part; crease: how much lower a dome's mound stands at its
            # border than its round dome there (0.45 = the old notch); cap_rim: a low socket ring round a dome's cap (a
            # share of its height); cap_h: the cap's own height (0.42 of H, the old)
            ('pig_t', 0.0), ('pig_f', 0.12), ('frost_on', 0.0), ('crease', 0.45), ('cap_rim', 0.0), ('cap_h', 0.42),
            # soft_e: a bead shaped by its cell takes a SOFT least border distance (a share of its half size; 0 = the
            # hard least, creased along the cell's skeleton)
            ('soft_e', 0.0),
            # (fourth sitting, 11-12) rim_mm: the scale's UNPIGMENTED RIM as a width in mm from its own edge (each its
            # own by `pig_jit`): a level of t (`pig_t`) left small scales with no crown at all and large ones a wide
            # one; a rim is as wide on a small scale as on a large one. soft_valley: where two mounds meet the valley
            # is ROUND-bottomed (the border level read at a soft least of the candidates' distances; a share of the
            # cell's half size; 0 = the old V, which drew every border as a line under any light). mound_rag: the
            # mound's pigment ends at a ragged edge (a share of its radius)
            # lip: a plate's rim stands as a low raised LIP (a share of its height) along the middle of its unpigmented
            # rim (c208's hand: every plate's dark face lies inside a raised crusty margin that the sun lights)
            ('rim_mm', 0.0), ('soft_valley', 0.0), ('mound_rag', 0.0), ('lip', 0.0),
            # (fifth sitting, 11-12) facet (mm): glossy keratin is never glass: a fine two-octave relief on the raised
            # face only (cells of `facet_cell` mm), zero at every border; evaluate() says why. rim_bias (0..1): the
            # unpigmented rim (`rim_mm`) is a scale's RAISED FREE EDGE, not a ring: it widens toward the end its
            # `ramp` (a bead) or `imbricate` (a plate) raises, to (1 + rim_bias) x, and narrows to (1 - rim_bias) x
            # at the end tucked under the next scale (c208's forearm and hand: the pale crust on each scale's sunlit
            # upper-left edge, a dark crease at its lower right; a ring round every scale read as bubble-wrap and grout)
            ('facet', 0.0), ('facet_cell', 0.35), ('rim_bias', 0.0),
            # (sixth sitting, 11-13) patch: THE PIGMENT IS ITS OWN BLOB ON THE CROWN, not the scale's outline shrunk.
            # On c208's forearm at x4 every scale is one loaf from crease to crease and its navy is a soft-edged
            # roundish blot on the crown, about 0.6 of the scale's width, no two alike; every rim key before this
            # (`pig`, `pig_t`, `rim_mm`) cut the pigment at a level of the scale's own outline, so each dark top was
            # its cell's shape, all lying along the rows (direction R 0.95 against the photo's 0.44). patch = the
            # blot's mean radius as a share of the scale's half size (0 = off; its size per scale by `pig_jit`);
            # patch_el: its own length over width (each scale's between 1 and this); patch_turn: how freely its long
            # axis turns against the scale's own (0 = along it, 1 = any way); patch_soft: its feathered edge (a share
            # of its radius); patch_rag: its outline's wobble; patch_low (plates): how much lower the plate stands
            # outside its blot (the hand's almond shingles: the glossy almond is the raised part, the crust its skirt);
            # patch_p (plates): the exponent along the row (2 = an oval, nearer 1 = an almond with pointed ends);
            # patch_shift (beads): the blot's centre moved toward the scale's TUCKED end (the end its `ramp` lowers),
            # in the frame's units: the frost lies on the raised free edge, the navy runs down into the crease.
            # socket (domes; a share of the dome's height): fine wrinkles CONCENTRIC WITH THE CAP, dying out down the
            # mound (c168o at x7: every cap sits in a ring of fine folds; the build's ring wrinkles followed the
            # cell's border, so they drew the cell's polygon round each mound). evaluate() also returns `halo`: the
            # collar of thin grey skin round a cap (a mask for the look's pigment, 1 at the cap's edge)
            # crust_h (mm) / crust_cell (mm): THE CRUST'S OWN RELIEF on whatever of a scale is not its pigmented face
            # (c208's hand and forearm in a low sun: the pale crust is a harsh speckle of lit lumps and their shadows,
            # 0.2-0.6 mm across; the skin granules at 0.26-0.30 mm are under a camera pixel and average to a smooth
            # pale tone). Two octaves, zero at every border and under the pigment
            ('patch', 0.0), ('patch_el', 1.0), ('patch_turn', 1.0), ('patch_soft', 0.25), ('patch_rag', 0.15),
            # patch_base (deg): where a blot's long axis lies in the scale's frame before its own turn (90 = across the
            # frame's first axis: along the rows of a lattice whose frame's first axis crosses them)
            ('patch_low', 0.0), ('patch_p', 2.0), ('patch_shift', 0.0), ('socket', 0.0), ('crust_h', 0.0),
            ('crust_cell', 0.5), ('patch_base', 0.0),
            # (FIX ROUND 2, second sitting, 11-14) THE CUSHION'S OWN SECTION: mound_w (the share of the mound's radius
            # over which it rises from its edge; 0.55 = the old), mound_p / mound_q (its section's exponents, _dome's;
            # 1.8 / 0.7 = the old). S2 at x7 and its mean cell: an adult's scale is ONE DOME FROM CREASE TO CREASE, a
            # tan cushion that fills the cell and keeps rising under the dark bead, a thin crisp crease at every border;
            # the old section (a young skin's skirt) stands as a flat-topped tile with a bevelled rim, and the bead on
            # it read as an egg on a plate. mound_w 1 with 2 / 0.5 is a half ellipsoid over the cell's own metric:
            # steep at the crease, still rising at the bead's foot. Defaults = the old numbers, the old code path
            ('mound_w', 0.55), ('mound_p', 1.8), ('mound_q', 0.7),
            # swell_h (mm; 0 = off) / swell_w / swell_q: THE SCALE'S OWN SWELL FROM CREASE TO CREASE under a bead (an
            # adult's skin: S2, K1's trunk). The mound above is a young skin's skirt: its outline a level of the cell's
            # metric, bare skin left in pockets where three cells meet. An adult's scales meet in CREASES: the swell
            # is 0 at every border and rises with the distance to it (the bead's own soft least where `soft_e` is
            # set: a pillow, no hip roof) over `swell_w` of the scale's half size, by (1 - (1 - t)^2)^swell_q (0.5: a
            # round shoulder standing steep out of the crease). Each scale's own height (`h_jit`, as its bead's)
            ('swell_h', 0.0), ('swell_w', 1.0), ('swell_q', 0.5),
            # cut_k (1 = the old): how many times faster than the distance itself the CELL'S CUT on a bead's outline
            # rises. A bead is the soft least of its own form (oval or lens) and its cell's border distance less
            # `gap`; at 1 the two are of one size at the bead's middle, so a bead as large as its cell takes the
            # cell's distance field for its back (a blunt cone: the lamp drew a streak ACROSS every bead, toward the
            # light). At 2.5 the cell only TRIMS the outline (packed beads stand steeper where they press on their
            # neighbours) and the bead's own ridge runs from tip to tip
            ('cut_k', 1.0),
            # mound_pig (1 = the old): the radius at which a cushion's PIGMENT ends, as a share of the cushion's own
            # radius. J1 at x2: every scale is a dark granular DOME that fills its cell and meets its neighbours in a
            # narrow fold; the orange skin is the folds and each dome's own foot. One radius for the dome and its
            # pigment gave either dark coasters on a wide orange field (radius 1.0) or no orange at all (1.1)
            ('mound_pig', 1.0),
            # bead_n (2 = the old oval): the exponent on the bead's ALONG term. Over 2 the long sides run straight and
            # the ends stay round: a LOAF. J1's mean cell (the gate's centres, averaged): each bead carries one long
            # thin streak ALONG ITS UPPER EDGE, 0.3 pitch long; an oval's edge turns away from the lamp all along its
            # length, so its streak is a short arc; a loaf's straight upper shoulder faces the lamp over its length
            ('bead_n', 2.0),
            # (FIX ROUND 2, third sitting, 11-14) A DOME'S MOUND, ITS OWN SECTION: dome_n / dome_q (2 / 0.7 = the old):
            # the mound stands (1 - (d / 1.12)^dome_n)^dome_q of its height at the cell's metric distance d; crease_w
            # (0.35 = the old): the share of the scale's half size over which the mound drops into its crease. c168o's
            # nape at x3: every scale is ONE CREAM MOUND from crease to crease, packed like cobbles, the creases narrow.
            # The old section falls all the way from the cap (0.61 of its height at d 0.8) and its crease band takes
            # the outer third of the cell: the clay read as a small cone round each cap on wide flat ground, the
            # colour as "olives on plaster" (the check's round 2). 4 / 0.5 with a band of 0.16 keeps 0.81 at d 0.8
            # and drops in the last sixth: a cobble's shoulder
            ('dome_n', 2.0), ('dome_q', 0.7), ('crease_w', 0.35),
            # (FIX ROUND 2, fourth sitting, 11-18) A DOME'S CAP IS RIGID KERATIN: cap_wob (0.24 = the old): how much the
            # cap's outline wobbles (c168o's caps are neat ovals of nearly one size; at 0.24 some came out pointed);
            # cap_true (0 = the old): the cap is drawn at the TRUE chart point, not at the point the spec's `wander`
            # displaced: the borders between mounds wander (rounder, less ruled cobbles), and a wander strong enough
            # for that (0.55 mm over 3 mm) bent every cap with it. The mound under the cap still wanders; the cap's
            # term is 0 long before any border, so the field stays one sheet
            ('cap_wob', 0.24), ('cap_true', 0.0))
    par = {k: np.zeros(N) for k, _ in keys}
    for r, reg in enumerate(spec['regions']):
        m = reg_i == r
        for key, dflt in keys:
            par[key][m] = reg.get(key, dflt)
    for b, band in enumerate(spec.get('bands', [])):
        m = reg_i == nreg + b
        for key, val in (('jitter', 0.06), ('size_jit', 0.12), ('h_jit', 0.25), ('turn', 180.0), ('relief', 0.13),
                         ('cover', 0.95), ('elong', 1.0), ('gap', 0.25), ('shift', 0.0), ('grain', 0.012),
                         ('moat', 0.0), ('plinth_h', 0.06), ('keel', 0.0), ('bead_p', 2.0), ('elong_jit', 0.0),
                         ('bead_ax', 0.0), ('lens', 0.0), ('shift_jit', 0.0), ('mound_h', 0.0), ('mound_r', 0.9),
                         ('shift_c', 0.0), ('imbricate', -1.0), ('spot', 0.0), ('row_groove', 0.45), ('inrow', 0.0),
                         ('bead_turn', 0.0), ('cover_jit', 0.0), ('gap_jit', 0.0), ('bead_pp', 2.0), ('bead_q', 0.5),
                         ('lean', 0.0), ('wrinkle', 0.0), ('wrinkle_len', 1.2), ('wrinkle_w', 0.25), ('cap_elong', 1.0),
                         ('cap_jit', 0.0), ('cap_turn', 0.0), ('crumple', 0.0), ('pillow_p', 2.0), ('pillow_c', 0.0),
                         ('turn_field', 0.0), ('turn_cell', 30.0), ('cover_fit', 0.0), ('ramp', 0.0), ('pig', 0.0),
                         ('pig_jit', 0.0), ('edge_w', 0.0), ('cush', 0.0), ('cush_jit', 0.0), ('mark_at', 0.45),
                         ('mark_len', 0.22), ('mark_w', 0.75), ('mark_jit', 0.0), ('cush_et', 1.0), ('pig_t', 0.0),
                         ('pig_f', 0.12), ('frost_on', 0.0), ('crease', 0.45), ('cap_rim', 0.0), ('cap_h', 0.42),
                         ('soft_e', 0.0), ('rim_mm', 0.0), ('soft_valley', 0.0), ('mound_rag', 0.0), ('lip', 0.0),
                         ('facet', 0.0), ('facet_cell', 0.35), ('rim_bias', 0.0), ('patch', 0.0), ('patch_el', 1.0),
                         ('patch_turn', 1.0), ('patch_soft', 0.25), ('patch_rag', 0.15), ('patch_low', 0.0),
                         ('patch_p', 2.0), ('patch_shift', 0.0), ('socket', 0.0), ('crust_h', 0.0), ('crust_cell', 0.5),
                         ('patch_base', 0.0), ('mound_w', 0.55), ('mound_p', 1.8), ('mound_q', 0.7),
                         ('swell_h', 0.0), ('swell_w', 1.0), ('swell_q', 0.5), ('cut_k', 1.0), ('mound_pig', 1.0),
                         ('bead_n', 2.0), ('dome_n', 2.0), ('dome_q', 0.7), ('crease_w', 0.35), ('cap_wob', 0.24),
                         ('cap_true', 0.0)):
            par[key][m] = band.get(key, val)
    r_mm = 0.5 * np.sqrt(np.abs(np.linalg.det(M0))) * size      # the mid-border half size, mm (mean of the two axes)
    jit = par['jitter'] * 2.0 * r_mm
    ang = 2.0 * np.pi * rand01(ids, 1)
    rad = np.sqrt(rand01(ids, 2))
    xy[:, 0] += np.where(cls == RIDGE, 0.0, jit * rad * np.cos(ang))
    for r in ridge_reg:
        # (fix round 2, `ridge_ujit`: a crest tooth's place along its ring, a share of the ring's width either way; on the
        # midline, so the mirror holds. With stubs alone the teeth's spacing flipped between one ring and two)
        uj = float(spec['regions'][r].get('ridge_ujit', 0.0))
        if uj > 0.0:
            m = (reg_i == r) & (cls == RIDGE)
            xy[m, 0] += uj * frames[m, 0] * (2.0 * rand01(ids[m], 37) - 1.0)
    xy[~mid, 1] += (jit * rad * np.sin(ang))[~mid]
    xy[~mid, 1] = np.maximum(xy[~mid, 1], 0.55 * r_mm[~mid])
    size = size * (1.0 + par['size_jit'] * (2.0 * rand01(ids, 3) - 1.0))
    turn = np.radians(par['turn']) * (2.0 * rand01(ids, 4) - 1.0)
    turn[mid] = 0.0                                             # a midline scale is its own mirror image
    c, s = np.cos(turn), np.sin(turn)
    Rm = np.stack([np.stack([c, -s], -1), np.stack([s, c], -1)], -2)
    M = Rm @ (M0 * size[:, None, None])
    if mid.any():
        # A MIDLINE SCALE IS ITS OWN MIRROR IMAGE: on a tilted lattice (the flank's steps lean 18 deg) its frame would
        # be folded by h(u, |v|) into a chevron; give it the frame's own extents, square to the midline
        Uu, Ss, _ = np.linalg.svd(M[mid])
        along_u = np.abs(Uu[:, 0, 0]) >= np.abs(Uu[:, 1, 0])
        Mm = np.zeros((int(mid.sum()), 2, 2))
        Mm[:, 0, 0] = np.where(along_u, Ss[:, 0], Ss[:, 1])
        Mm[:, 1, 1] = np.where(along_u, Ss[:, 1], Ss[:, 0])
        M[mid] = Mm
    r_mm = 0.5 * np.sqrt(np.abs(np.linalg.det(M)))
    hj = 1.0 + par['h_jit'] * (2.0 * rand01(ids, 5) - 1.0)
    relief = par['relief'] * hj
    relief = np.where(isband | (cls == DOME), par['relief'] * 2.0 * r_mm * hj, relief)   # a share of ITS OWN spacing
    for r in ridge_reg:                                         # the crest's teeth: their own height row (mm), +-35 %
        m = (reg_i == r) & (cls == RIDGE)
        rv = spec['regions'][r]['ridge']                        # a number, or a function of u (the height along the tail)
        base = rv(xy[m, 0]) if callable(rv) else rv
        rs = float(spec['regions'][r].get('ridge_spread', 0.0))
        if rs > 0.0:
            # (fix round 2, `ridge_spread` / `ridge_skip`; the check's round 2: "the tail crest is a regular comb": its
            # teeth's heights spread (IQR over median) 0.22-0.37 by eighths against c274o's 0.39-2.26, their spacing
            # 0.04-0.13 against 0.21-0.97: one tooth a ring at +-35 %. A real crest's teeth are a skewed lot, many low,
            # a few tall, and some rings carry only a stub. The heights LOGNORMAL with median 1 (so the outline gate's
            # medians by eighths hold), sigma `ridge_spread`; a share `ridge_skip` of the rings a stub (0.12 of the
            # base). Both from the tooth's id (G-S5: deterministic; a midline tooth is shared by both halves)
            z = np.sqrt(-2.0 * np.log(np.maximum(rand01(ids[m], 6), 1e-12))) * np.cos(2.0 * np.pi * rand01(ids[m], 35))
            f = np.exp(rs * z)
            f = np.where(rand01(ids[m], 36) < float(spec['regions'][r].get('ridge_skip', 0.0)), 0.12, f)
            relief[m] = base * f
        else:
            relief[m] = base * (1.0 + 0.35 * (2.0 * rand01(ids[m], 6) - 1.0))
    par['elong'] = par['elong'] * (1.0 + par['elong_jit'] * (2.0 * rand01(ids, 7) - 1.0))   # no two beads one shape
    par['shift'] = par['shift'] + par['shift_jit'] * (2.0 * rand01(ids, 8) - 1.0)          # nor in one place in its cell
    par['shift'][mid] = 0.0                                     # a midline scale is its own mirror image
    par['shift_c'][mid] = 0.0
    # FIX ROUND 1, each scale its own (from its id; a midline scale keeps the mirror-symmetric values: no turn, no lean)
    bturn = np.radians(par['bead_turn']) * (2.0 * rand01(ids, 13) - 1.0)
    # ...plus a SMOOTH turn field (neighbours turn together, as the rows of a curved body do: S2's beads stand upright
    # on the crop's left and lie along the body on its right), read at the site; zero across the midline
    tf = np.radians(par['turn_field'])
    if np.any(tf > 0):
        hs_t = int(spec.get('hash_salt', 0))
        bturn = bturn + tf * (2.0 * vnoise(xy[:, 0], xy[:, 1] + 777.0 * hs_t, par['turn_cell'], 23) - 1.0) * smoothstep(0.0, 8.0, xy[:, 1])
    bturn[mid] = 0.0
    par['cover'] = par['cover'] * (1.0 + par['cover_jit'] * (2.0 * rand01(ids, 14) - 1.0))
    par['gap'] = par['gap'] * (1.0 + par['gap_jit'] * (2.0 * rand01(ids, 15) - 1.0))
    lean = par['lean'] * (0.5 + rand01(ids, 16))
    lean[mid] = 0.0
    capk = 1.0 + par['cap_jit'] * (2.0 * rand01(ids, 17) - 1.0)
    capturn = np.radians(par['cap_turn']) * (2.0 * rand01(ids, 18) - 1.0)
    capturn[mid] = 0.0
    noff = 1000.0 * rand01(ids, 19)
    out = dict(spec=spec, seed=seed, xy=xy, M=M, cls=cls, mid=mid, reg=reg_i, isband=isband, r_mm=r_mm, relief=relief,
               cover=par['cover'], elong=par['elong'], gap=par['gap'], shift=par['shift'], grain=par['grain'],
               moat=par['moat'], plinth_h=par['plinth_h'], keel=par['keel'], bead_p=par['bead_p'],
               bead_ax=par['bead_ax'], lens=par['lens'], mound_h=par['mound_h'], mound_r=par['mound_r'],
               shift_c=par['shift_c'], imbricate=par['imbricate'], spot=par['spot'], row_groove=par['row_groove'],
               inrow=par['inrow'], row_id=row_id, hid=ids, size=size, n=N,
               bturn=bturn, lean=lean, bead_pp=par['bead_pp'], bead_q=par['bead_q'], wrinkle=par['wrinkle'],
               wrinkle_len=par['wrinkle_len'], wrinkle_w=par['wrinkle_w'], cap_elong=par['cap_elong'], capk=capk,
               capturn=capturn, crumple=par['crumple'], pillow_p=par['pillow_p'], pillow_c=par['pillow_c'], noff=noff,
               cover_fit=par['cover_fit'], ramp=np.where(mid, 0.0, par['ramp']), edge_w=par['edge_w'],
               cush=par['cush'] * (1.0 + par['cush_jit'] * (2.0 * rand01(ids, 24) - 1.0)),
               mark_at=par['mark_at'] + 0.25 * par['mark_jit'] * (2.0 * rand01(ids, 25) - 1.0),
               mark_len=par['mark_len'] * (1.0 + par['mark_jit'] * (2.0 * rand01(ids, 26) - 1.0)),
               mark_w=par['mark_w'] * (1.0 + par['mark_jit'] * (2.0 * rand01(ids, 27) - 1.0)), mark_jit=par['mark_jit'],
               cush_et=par['cush_et'],
               pig_t=par['pig_t'] * (1.0 + par['pig_jit'] * (2.0 * rand01(ids, 20) - 1.0)), pig_f=par['pig_f'],
               frost_on=par['frost_on'], crease=par['crease'], cap_rim=par['cap_rim'], cap_h=par['cap_h'], mn=mn,
               soft_e=par['soft_e'], rim_mm=par['rim_mm'] * (1.0 + par['pig_jit'] * (2.0 * rand01(ids, 20) - 1.0)),
               soft_valley=par['soft_valley'], mound_rag=par['mound_rag'], lip=par['lip'],
               facet=par['facet'], facet_cell=par['facet_cell'], rim_bias=par['rim_bias'],
               # (sixth sitting) the pigment's own blot: its size, shape and turn per scale (a midline scale's blot
               # lies square to the midline: its own mirror image)
               patch=par['patch'] * (1.0 + par['pig_jit'] * (2.0 * rand01(ids, 30) - 1.0)),
               patch_el=1.0 + (par['patch_el'] - 1.0) * rand01(ids, 31),
               patch_ang=np.radians(par['patch_base']) + np.where(mid, 0.0, np.pi * par['patch_turn'] * (rand01(ids, 32) - 0.5)),
               patch_soft=par['patch_soft'], patch_rag=par['patch_rag'], patch_low=par['patch_low'],
               patch_p=par['patch_p'], patch_shift=np.where(mid, 0.0, par['patch_shift']), socket=par['socket'],
               crust_h=par['crust_h'], crust_cell=par['crust_cell'], rows_on=(lrow >= 0),
               mound_w=par['mound_w'], mound_p=par['mound_p'], mound_q=par['mound_q'],
               swell_h=par['swell_h'] * hj, swell_w=par['swell_w'], swell_q=par['swell_q'], cut_k=par['cut_k'],
               mound_pig=par['mound_pig'], bead_n=par['bead_n'],
               dome_n=par['dome_n'], dome_q=par['dome_q'], crease_w=par['crease_w'],
               cap_wob=par['cap_wob'], cap_true=par['cap_true'],
               mound_old=bool(np.all((par['mound_w'] == 0.55) & (par['mound_p'] == 1.8) & (par['mound_q'] == 0.7))),
               pig=par['pig'] * (1.0 + par['pig_jit'] * (2.0 * rand01(ids, 20) - 1.0)), P=_pack(xy, M, cls, mid, reach, mn))
    # every cell's neighbours (fix round 1: the border distance e is taken over them; `_nearest`)
    out['P']['adj'] = _adjacency(out['P'], U, Vh, reach, spec.get('adj_step', max(0.05, min(0.25, 0.25 * float(r_mm.min())))))
    # A BEAD SIZED BY ITS CELL (fix round 1, `cover_fit`): each scale's frame carries its own size, its cell its
    # neighbours' too, so a large scale among smaller ones leaves a wide collar (S2's swatch, try 4). fit = the side of
    # the cell's real area (the same raster) over its frame's ideal cell's; a bead with cover_fit 1 scales its oval by it
    ideal = np.abs(np.linalg.det(M)) * np.where((METRIC_N[cls] > 2.0) | rows_reg, 1.0, np.sqrt(3.0) / 2.0)
    out['fit'] = np.clip(np.sqrt(out['P']['cell_area'][:N] / np.maximum(ideal, 1e-9)), 0.70, 1.40)
    mc = spec.get('micro')
    if mc:                                                      # the skin between the scales: its own fine granules
        p = mc['pitch']
        R = int(max(U, Vh) / p) + 3
        ii, jj = np.meshgrid(np.arange(-R, 2 * R), np.arange(0, R), indexing='ij')
        q = (HEX @ np.stack([ii.ravel(), jj.ravel()]).astype(float)).T * p
        q = q[(q[:, 0] > -p) & (q[:, 0] < U + p) & (q[:, 1] < Vh + p)]
        mids = np.arange(len(q))
        q[:, 0] += mc.get('jitter', 0.28) * p * (2.0 * rand01(mids, 11) - 1.0)
        onmid = q[:, 1] < 0.25 * p
        q[~onmid, 1] += mc.get('jitter', 0.28) * p * (2.0 * rand01(mids, 12) - 1.0)[~onmid]
        q[onmid, 1] = 0.0
        q[~onmid, 1] = np.maximum(q[~onmid, 1], 0.5 * p)
        gh = (~onmid) & (q[:, 1] < 3.0 * p)
        qe = np.concatenate([q, q[gh] * np.array([1.0, -1.0])])
        out['micro'] = dict(xy=qe, tree=cKDTree(qe), pitch=p, h=mc['height'], src=np.concatenate([mids, mids[gh]]),
                            mound_boost=mc.get('mound_boost', 0.0))
    log(f'[scale_skin] plan: {N} scales (' + ', '.join(f'{CLASS_NAMES[c]} {int((cls == c).sum())}' for c in range(6) if (cls == c).any()) +
        f'), {int(mid.sum())} on the midline' + (f'; {len(out["micro"]["xy"])} skin granules at {mc["pitch"]} mm' if mc else ''))
    return out


# ------------------------------------------------------------------------------------------------ the profiles
def _dome(t, p=2.4, q=0.55):
    """a pebble's section: steep at its edge, flat on top (t = 0 at the edge, 1 at the middle)"""
    t = np.clip(t, 0.0, 1.0)
    return (1.0 - (1.0 - t) ** p) ** q


def _mound(pl, s, mr, d):
    """a bead's CUSHION at the metric distance d from its site (sites s, the cushion's radius mr in the same units): its
    height as a share of `mound_h`, by each site's own section (fix round 2, second sitting: `mound_w`, `mound_p`,
    `mound_q`; plan() says why). A site with the old numbers takes the old expression, bit for bit; evaluate() and
    `_border_level` both call this, so a cell and the shared ground agree at every border (one sheet)"""
    if pl['mound_old']:
        return _dome(np.clip((mr - d) / (0.55 * mr), 0.0, 1.0), 1.8, 0.7)
    w, p, q = pl['mound_w'][s], pl['mound_p'][s], pl['mound_q'][s]
    old = (w == 0.55) & (p == 1.8) & (q == 0.7)
    t = np.clip((mr - d) / (w * mr), 0.0, 1.0)
    res = (1.0 - (1.0 - t) ** p) ** q
    if old.any():
        res[old] = _dome(t[old], 1.8, 0.7)
    return res


def _dome_mound(pl, s, d):
    """a DOME's mound at the cell's metric distance d from its site (sites s), as a share of its height at its middle:
    (1 - (d / 1.12)^dome_n)^dome_q (fix round 2, third sitting; plan() says why). A site with the old numbers (2 / 0.7)
    takes the old expression, bit for bit; evaluate() and `_border_level` both call this, so a cell and the shared
    ground agree at every border (one sheet)"""
    rd = np.clip(1.0 - d / 1.12, 0.0, 1.0)
    res = (1.0 - (1.0 - rd) ** 2) ** 0.7
    n, q = pl['dome_n'][s], pl['dome_q'][s]
    new = (n != 2.0) | (q != 0.7)
    if np.any(new):
        res = np.where(new, (1.0 - np.clip(d / 1.12, 0.0, 1.0) ** n) ** q, res)
    return res


def _border_level(pl, src, dd, rown2, wob_mr):
    """beta_j (fix round 1): each candidate scale's OWN profile at its border (e = 0), written only with what both cells
    share there: the metric distance (equal on both sides of a border), 2R (between rows) and the point's own noise.
    A dome's skirt foot, a plate's or ring's in-row level (`inrow`) and row groove (`row_groove`), a young bead's
    cushion; 0 for adult beads, granules and the crest. src, dd, rown2, wob_mr broadcast to (n, k)"""
    cls = pl['cls'][src]
    b = np.zeros(src.shape)
    m = cls == DOME
    if m.any():
        b[m] = 0.55 * (1.0 - pl['crease'][src[m]]) * pl['relief'][src[m]] * _dome_mound(pl, src[m], np.broadcast_to(dd, src.shape)[m])   # = evaluate's skirt at e = 0
    m = (cls == PLATE) | (cls == WHORL)
    if m.any():
        s, rr = src[m], np.broadcast_to(rown2, src.shape)[m]
        b[m] = pl['relief'][s] * (pl['inrow'][s] * (1.0 - rr) - pl['row_groove'][s] * rr)
    # (sixth sitting) a lattice region with its own rows (`rows_along`): its beads meet their row-mates at `inrow` of
    # their height (a shallow saddle) and the next row in a groove `row_groove` of it below the skin, as plates do
    m = (cls == BEAD) & pl['rows_on'][src]
    if m.any():
        s, rr = src[m], np.broadcast_to(rown2, src.shape)[m]
        b[m] = pl['relief'][s] * (pl['inrow'][s] * (1.0 - rr) - pl['row_groove'][s] * rr)
    if wob_mr is not None:
        m = (cls == BEAD) & (pl['mound_h'][src] > 0)
        if m.any():
            s = src[m]
            mr = pl['mound_r'][s] * np.broadcast_to(wob_mr, src.shape)[m]
            b[m] = pl['mound_h'][s] * _mound(pl, s, mr, np.broadcast_to(dd, src.shape)[m])
    return b


def _bands(pl, own, cls, r):
    """per point, before the profiles (fix round 1): the band (mm) over which its cell's profile lerps to the shared
    ground at the border, and the REACH within which the ground (and 2R) must be known: a plate's or ring's band
    follows its rows (0.8 w, w up to 1.6875 x its nominal as it imbricates), so its reach is that largest w"""
    g_b = np.minimum(pl['gap'][own], 0.30 * r)
    g_g = np.minimum(pl['gap'][own], 0.25 * r)
    ew = pl['edge_w'][own]
    w0 = np.where(ew > 0, ew, np.minimum(0.45, 0.30 * r))
    band = np.select([cls == BEAD, cls == DOME, (cls == PLATE) | (cls == WHORL), cls == GRANULE, cls == RIDGE],
                     [np.maximum(0.6 * g_b, 0.05), 0.35 * r, 0.8 * w0, np.maximum(0.5 * g_g, 0.05), np.minimum(0.5, 0.35 * r)],
                     0.2)
    # (sixth sitting) a bead of a lattice region with rows reaches its saddle / its row groove over `edge_w` mm
    # (0.14 of its half size unless given): the 0.07 mm of a plain bead would make either a razor's edge
    lat = (cls == BEAD) & pl['rows_on'][own]
    band = np.where(lat, np.where(ew > 0, ew, 0.14 * r), band)
    reach = np.where((cls == PLATE) | (cls == WHORL), 1.6875 * w0, band)
    return band, reach


def evaluate(pl, u, v, chunk=150000):
    """the field at chart points (u, v) mm (any shape). Returns a dict of arrays of that shape:
    h (mm), id (the scale's index in the plan), side (+1 / -1 / 0: the side of the SCALE'S CENTRE; 0 on the midline),
    cls, top (0..1: the scale's raised face), groove (0..1: the skin between scales), e (mm to the cell's border),
    rho (0 at the scale's centre, 1 at an ideal cell's mid border), tier_s (1 where the relief is a sculpt-tier
    instance's: domes and ridges), hmicro (the skin granules' part of h)."""
    u = np.asarray(u, np.float64)
    v = np.asarray(v, np.float64)
    shp = u.shape
    X = np.column_stack([u.ravel(), np.abs(v.ravel())])
    sgn = np.where(v.ravel() < 0.0, -1.0, 1.0)
    wd = pl['spec'].get('wander')
    X0 = X.copy() if (wd and np.any(pl['cap_true'] > 0)) else None      # the true points (`cap_true`: plan() says why)
    if wd:
        # NO CELL BORDER IS A RULED LINE (third sitting; the check: "cut by ruler-straight polygon lines"): the field is
        # read at points displaced by a smooth noise (amp mm over cells of `cell` mm), so every border wanders; none
        # across the midline (v's part goes to 0 there: the mirror stays exact and a midline scale stays on it)
        amp, cell = wd
        Xu, Xv = X[:, 0].copy(), X[:, 1].copy()
        X[:, 0] = Xu + amp * (2.0 * vnoise(Xu, Xv, cell, 81) - 1.0)
        X[:, 1] = np.maximum(Xv + amp * (2.0 * vnoise(Xu + 311.0, Xv, cell, 82) - 1.0) * smoothstep(0.0, 4.0 * amp, Xv), 0.0)
    N = len(X)
    out = {k: np.zeros(N) for k in ('h', 'top', 'groove', 'e', 'rho', 'tier_s', 'hmicro', 'mark', 'mound', 'rown', 'ground', 'halo')}
    out['id'] = np.zeros(N, np.int64)
    out['side'] = np.zeros(N)
    out['cls'] = np.zeros(N, np.int64)
    P = pl['P']
    mc = pl.get('micro')
    for s0 in range(0, N, chunk):
        sl = slice(s0, min(N, s0 + chunk))
        x = X[sl]
        i1, d1, xi, et, e, dsite, cidx, cd, ej, ctap = _nearest(P, x, cand=True)
        own = P['src'][i1]
        gsg = np.where(P['ghost'][i1], -1.0, 1.0)              # a mirror ghost turns its scale the other way
        cls = pl['cls'][own]
        r = pl['r_mm'][own]
        H = pl['relief'][own]
        cov = pl['cover'][own]
        # ---- THE SHARED GROUND (fix round 1; the module's header). Softmin weights on the candidates' metric
        #      distances; 2R from the row ids of the K_ROW candidates nearest by metric (each candidate's row's total
        #      weight, the largest: 1 inside a cell or at a border within a row, 0.5 at a border between two rows).
        #      Computed only within each point's REACH of its border (deep in a cell the own profile stands alone: the
        #      ground's weight there is 0); the keratin grain's amount is blended the same way (shared at a border)
        band, reach = _bands(pl, own, cls, r)
        # (sixth sitting: a lattice region with its own rows (`rows_along`) needs 2R as far in as its soil band runs)
        lat_rows = pl['rows_on'][own]
        reach = np.where(lat_rows, np.maximum(reach, 0.35 * r), reach)
        wob = (1.0 + 0.07 * (2.0 * vnoise(x[:, 0], x[:, 1], 1.1, 33) - 1.0)) if pl['mound_h'].max() > 0 else None
        rown, G = np.zeros(len(x)), np.zeros(len(x))
        gr = pl['grain'][own].copy()
        B = np.nonzero(e < reach)[0]
        if len(B):
            csrc = P['src'][cidx[B]]
            # (eighth sitting: each weight tapered as its candidate nears the k-th's distance (TAPER0); 2R over every
            # candidate, not the 6 nearest by metric, whose choice switched inside a cell)
            wgt = np.exp(-(cd[B] - d1[B, None]) / TAU) * ctap[B]
            wgt /= wgt.sum(axis=1, keepdims=True)
            rid = pl['row_id'][csrc]
            srow = (wgt[:, None, :] * (rid[:, :, None] == rid[:, None, :])).sum(axis=2)
            rown[B] = np.clip(2.0 * (1.0 - srow.max(axis=1)), 0.0, 1.0)     # 2R: 1 at a border between ROWS
            dB = d1[B]
            sv = (wgt * pl['soft_valley'][csrc]).sum(axis=1)   # (fourth sitting, `soft_valley`; shared at a border)
            if np.any(sv > 0):
                # the border level read at a SOFT least of the candidates' metric distances: smooth across the border,
                # so two mounds meet in a round-bottomed valley, not a V (d1 itself has a kink at every border)
                svc = np.maximum(sv, 1e-6)
                dB = np.where(sv > 0, d1[B] - svc * np.log((ctap[B] * np.exp(-(cd[B] - d1[B, None]) / svc[:, None])).sum(axis=1)), d1[B])
            G[B] = (wgt * _border_level(pl, csrc, dB[:, None], rown[B, None], None if wob is None else wob[B, None])).sum(axis=1)
            sB = smoothstep(0.0, band[B], e[B])
            gr[B] = gr[B] + ((wgt * pl['grain'][csrc]).sum(axis=1) - gr[B]) * (1.0 - sB)
        h = np.zeros(len(x))
        top = np.zeros(len(x))
        inner = np.zeros(len(x))                                # mm inside the raised part's edge (for the skin's weight)
        ts = np.zeros(len(x))
        mark = np.zeros(len(x))                                 # the class's own pigment mark (a whorl's dark pit)
        mound = np.zeros(len(x))                                # 1 on a bead's mound (its cushion's pigment)
        halo = np.zeros(len(x))                                 # (sixth sitting) a dome's collar of thin skin round its cap
        # ---- bead: a pebble in a moat on a low plinth; its outline is its CELL's, rounded (it keeps `gap` mm clear
        #      of the border), or its own oval where the cell is roomier than the oval (cover < 1: a young skin)
        m = cls == BEAD
        if m.any():
            o = own[m]
            # the bead's LENGTH runs along its frame's first axis (bead_ax 0: the lattice's step `a`) or its second
            # (bead_ax 1: the cell's own vertex, (2b - a) / 3): a cell POINTED along the body (S2, the adult's flank:
            # the nearest neighbours across and on two diagonals) has no lattice step along the body, so its bead
            # lies along the vertex (D2.2, restart 2: measured on S2's crop, d22_crop_lattice.py)
            ax1 = pl['bead_ax'][o] > 0.5
            xa = np.where(ax1, et[m], xi[m]) - pl['shift'][o]
            xc = np.where(ax1, xi[m], et[m]) - pl['shift_c'][o]   # the bead off its cell's middle across as well (J1)
            # FIX ROUND 1: the bead TURNED in its cell, each its own way (a mirror ghost turns the other way)
            bt = pl['bturn'][o] * gsg[m]
            cb, sbt = np.cos(bt), np.sin(bt)
            xa, xc = cb * xa + sbt * xc, -sbt * xa + cb * xc
            fit = 1.0 + (pl['fit'][o] - 1.0) * pl['cover_fit'][o]     # the bead sized by its cell (fix round 1)
            cu, cv = cov[m] * fit, cov[m] * fit / pl['elong'][o]
            # bead_p: the exponent on the ACROSS term only: 2 = an oval; under 2 the two ends along the length come to
            # points (a grain of rice) while the sides stay round; the 0.15 softens the crease it would draw along the
            # axis into a faint keel
            bp = pl['bead_p'][o]
            q = (xc * xc / (cv * cv) + 0.0225) ** (0.5 * bp) - 0.0225 ** (0.5 * bp)
            q = q / ((1.0 + 0.0225) ** (0.5 * bp) - 0.0225 ** (0.5 * bp))       # 1 at the side, as the oval's
            bn = pl['bead_n'][o]
            rho = np.sqrt((xa / cu) ** 2 + q)
            if np.any(bn != 2.0):                               # (`bead_n`: a loaf's straight long sides; plan() says why)
                rho = np.where(bn != 2.0, np.sqrt(np.abs(xa / cu) ** bn + q), rho)
            lens = pl['lens'][o]
            if np.any(lens > 0):
                # A LENS: two discs through the tips (+-cu, 0) and the sides (0, +-cv); inside both. Its tips come to
                # points along the length (S2's beads are grains of rice, not eggs); the smooth max where the two
                # arcs meet leaves a soft lengthwise keel (the plan's "faint lengthwise keel", §5.4)
                Rl = (cu * cu + cv * cv) / (2.0 * cv)
                cl = Rl - cv
                # (fix round 1: these two were named d1, d2 and overwrote the chunk's metric distances d1, which the
                # other classes and `rho` read after this block; no plate used a lens, so nothing showed)
                la, lb = np.hypot(xa, xc - cl), np.hypot(xa, xc + cl)
                kk = 0.35 * cv
                hh = np.clip(0.5 + 0.5 * (la - lb) / kk, 0.0, 1.0)
                dmax = lb + (la - lb) * hh + kk * hh * (1.0 - hh)     # the smooth maximum of la, lb
                rho = (1.0 - lens) * rho + lens * (dmax - cl) / cv
            g = np.minimum(pl['gap'][o], 0.30 * r[m])            # plinth + moat width, mm
            rb = np.minimum(cv * r[m], r[m] - g)
            eb = e[m]
            se = pl['soft_e'][o]
            if np.any(se > 0):
                # A PAD SHAPED BY ITS CELL IS A PILLOW, NOT A HIP ROOF (third sitting, `soft_e`, a share of the scale's
                # half size): e is the LEAST of the borders' distances, creased along the cell's skeleton, and a dome
                # built on it showed facets like a cut gem (forearm try a2). A soft least over the same borders is
                # smooth inside the cell and equals e near any one border (so the pad's edge and the ground are as before)
                # (SIXTH SITTING, 11-13: THE PALE SHELF ROUND EVERY PAD WAS THIS LINE. The soft least was the exponential
                # one, e - k log(sum exp(-(e_j - e) / k)), k = soft_e x the half size: it is NOT e near a border unless
                # the other borders are many k away; with six borders 2-3 mm off and k 0.6-1.0 mm it stood 0.5-0.8 mm
                # UNDER e, so every pad's foot began 0.6-1.2 mm inside its cell (measured on a profile through a pad:
                # h = 0 out to e = 0.64 mm at soft_e 0.18, to 1.22 mm at 0.30) and a flat floor 1.2-2.4 mm wide lay
                # between pads: the "pale shelf", "bubble-wrap collar", "tray" of five sittings. A soft least WITHOUT
                # that bias: e x (sum (e / e_j)^p)^(-1/p), p = 1 / soft_e: equal to e wherever one border is nearest by
                # far (the ratio goes to 1 as e goes to 0), 6^(-1/p) of the half size at a hexagon's middle (0.64 at
                # p 4), smooth inside the cell)
                pn = 1.0 / np.maximum(se, 1e-3)
                es = e[m] * (np.clip(e[m][:, None] / np.maximum(ej[m], 1e-9), 0.0, 1.0) ** pn[:, None]).sum(axis=1).clip(1.0, None) ** (-1.0 / pn)
                eb = np.where(se > 0, np.minimum(es, e[m]), e[m])
            sb = smin((1.0 - rho) * cv * r[m], pl['cut_k'][o] * (eb - g), 0.30 * rb)    # (`cut_k`: plan() says why)
            t = sb / (0.92 * rb)
            keel = 1.0 + pl['keel'][o] * np.exp(-(xc / (0.30 * cv)) ** 2) * np.clip(t, 0, 1)
            pl_h = np.minimum(pl['plinth_h'][o], 0.05 * r[m])
            plinth = pl_h * smoothstep(0.0, 0.6 * g, e[m]) * (1.0 - pl['moat'][o] * np.exp(-(sb / (0.4 * g)) ** 2))
            # A MOUND under the bead (a young skin, J1: each glossy bead crowns a dark granular cushion, and the skin
            # shows in GAPS between the cushions, wide where three meet, narrow between two). Its outline is a level of
            # the cell's own metric (d1 = 1 at an edge's middle, 1.155 at a corner), wobbling a little; it rises as a
            # broad dome to the bead. mound_h 0 = none (an adult's flat collar)
            mh = pl['mound_h'][o]
            if np.any(mh > 0):
                mr = pl['mound_r'][o] * wob[m]                  # the same wobble as its border level (_border_level)
                plinth = plinth + mh * _mound(pl, o, mr, d1[m])
                # (fourth sitting, `mound_rag`: the skirt's pigment ends at a ragged edge, granule by granule: J1's black
                # skirts fray into the orange, they are not coasters)
                rag = pl['mound_rag'][o]
                mrc = mr * (1.0 + rag * (0.6 * (2.0 * vnoise(x[m, 0], x[m, 1], 0.9, 34) - 1.0) + 0.4 * (2.0 * vnoise(x[m, 0], x[m, 1], 0.4, 36) - 1.0)))
                mrc = mrc * pl['mound_pig'][o]                  # (`mound_pig`: plan() says why; 1 = the old, bit for bit)
                mound[m] = smoothstep(0.0, 0.10, mrc - d1[m])
            sw = pl['swell_h'][o]
            if np.any(sw > 0):
                # (fix round 2, second sitting, `swell_h`; plan() says why) THE SCALE'S OWN SWELL from crease to crease:
                # 0 at the border (so both cells agree there: one sheet), rising with the bead's own border distance
                tsw = np.clip(eb / np.maximum(pl['swell_w'][o] * r[m], 1e-6), 0.0, 1.0)
                plinth = plinth + np.where(sw > 0, sw * (1.0 - (1.0 - tsw) ** 2) ** pl['swell_q'][o], 0.0)
            # the crown (fix round 1): its section `bead_pp` / `bead_q` (2.0 / 0.5 the old flat-topped pebble), tilted
            # across the bead by `lean` (the young skin's beads lean; their keel then catches the light as a streak)
            crown = H[m] * _dome(t, pl['bead_pp'][o], pl['bead_q'][o]) * keel * (1.0 + pl['lean'][o] * np.clip(xc / cv, -1.0, 1.0))
            # ...and RAMPED toward its rear end along its length (`ramp`: imbricate pads, c208's forearm: each over the next)
            crown = crown * (1.0 + pl['ramp'][o] * np.clip(xa / cu, -1.0, 1.0))
            wr = pl['wrinkle'][o]
            if np.any(wr > 0):
                # KERATIN WRINKLES streaked along the bead (S2's dry beads are fibrous; the check: "flat inside", the
                # shading inside a top 0.10 against the photo's 0.29): a value noise stretched along the bead's length
                rr = r[m]
                wn = vnoise(xa * rr / pl['wrinkle_len'][o] + pl['noff'][o], xc * rr / pl['wrinkle_w'][o], 1.0, 61)
                crown = crown + wr * (2.0 * wn - 1.0) * smoothstep(0.05, 0.45, t)
            h[m] = plinth + crown                               # a pebble: a round section from its edge to its crown
            top[m] = smoothstep(0.0, 0.12, sb)                  # the pigment ends AT the bead's edge
            pg = pl['pig'][o]
            if np.any(pg > 0):
                # THE PIGMENT ENDS INSIDE THE SCALE (fix round 1, `pig`: c208's forearm pads are dark navy in their middle
                # and pale and crusty at their own raised margin; the dark crack is between pads): the dark top within
                # rho < pig (each its own size, `pig_jit`, its edge wobbling); the margin takes the skin's colour
                pr = pg * (1.0 + 0.10 * (2.0 * vnoise(x[m, 0], x[m, 1], 1.6, 41) - 1.0))
                top[m] = np.where(pg > 0, top[m] * (1.0 - smoothstep(pr - 0.10, pr + 0.06, rho)), top[m])
            pt = pl['pig_t'][o]
            if np.any(pt > 0):
                # THE PIGMENT ENDS AT A LEVEL OF THE SCALE'S OWN CROWN (third sitting, `pig_t`; c208 at x4: every pad's
                # dark glossy middle is its smooth crown, its sloping margin frosted pale by the granule ring; the dark
                # part is the pad's own outline shrunk, not an oval painted on it): top where t (0 at the pad's edge,
                # about 1 at its middle) passes pig_t, feathered by pig_f, the edge wobbling at two sizes
                # (a1: a wobble of 0.14 + 0.07 ate the crowns into ragged blots; c208's are smooth ovals whose edge only
                # the frost breaks)
                wob2 = 0.05 * (2.0 * vnoise(x[m, 0], x[m, 1], 1.4, 44) - 1.0) + 0.03 * (2.0 * vnoise(x[m, 0], x[m, 1], 0.45, 45) - 1.0)
                pf = pl['pig_f'][o]
                top[m] = np.where(pt > 0, top[m] * smoothstep(pt - pf, pt + pf, t + wob2), top[m])
            rmb = pl['rim_mm'][o]
            if np.any(rmb > 0):
                # (fourth sitting, `rim_mm`: the unpigmented rim a WIDTH from the pad's own edge, its inner line wobbling)
                wob4 = 0.10 * (2.0 * vnoise(x[m, 0], x[m, 1], 1.4, 48) - 1.0) + 0.06 * (2.0 * vnoise(x[m, 0], x[m, 1], 0.45, 49) - 1.0)
                # (fifth sitting, `rim_bias`: the rim wide at the end the ramp raises, none at the tucked end)
                rbs = pl['rim_bias'][o] * (-np.sign(pl['ramp'][o])) * np.clip(xa / cu, -1.0, 1.0)
                rmb = rmb * np.clip(1.0 + rbs, 0.0, 2.0)
                top[m] = np.where(rmb > 0, top[m] * smoothstep(rmb - 0.06, rmb + 0.06, sb + wob4), top[m])
            pch = pl['patch'][o]
            if np.any(pch > 0):
                # (sixth sitting, `patch`: THE PIGMENT IS ITS OWN SOFT BLOT ON THE CROWN; plan() says why.) In the
                # scale's own frame, turned its own way (a mirror ghost the other way), its own length over width, its
                # outline wobbling at two sizes (in units of the scale's own half size, so a small scale's blot is as
                # ragged as a large one's), its edge feathered: the frost then thins out into it (`frost_on`)
                pang = pl['patch_ang'][o] * gsg[m]
                cp, sp_ = np.cos(pang), np.sin(pang)
                pe = np.sqrt(pl['patch_el'][o])
                xs = xa - pl['patch_shift'][o] * np.where(pl['ramp'][o] > 0, -1.0, 1.0)     # toward the tucked end
                dp = np.hypot((cp * xs + sp_ * xc) / pe, (-sp_ * xs + cp * xc) * pe) / np.maximum(pch, 1e-6)
                xr, yr = x[m, 0] / r[m], x[m, 1] / r[m]
                dp = dp + pl['patch_rag'][o] * (0.6 * (2.0 * vnoise(xr, yr, 0.42, 57) - 1.0) + 0.4 * (2.0 * vnoise(xr + 9.0, yr, 0.16, 58) - 1.0))
                ps_ = pl['patch_soft'][o]
                top[m] = np.where(pch > 0, top[m] * (1.0 - smoothstep(1.0 - ps_, 1.0 + ps_, dp)), top[m])
            inner[m] = sb                                       # the skin's granules cover the mound too (J1's cushions)
            band[m] = np.where(pl['rows_on'][o], band[m], np.maximum(0.6 * g, 0.05))   # (a lattice's rows: `_bands`)
        # ---- dome (the neck): a dark cap on a broad mound that fills the cell, ring wrinkles round it
        m = cls == DOME
        if m.any():
            cc = 0.46 * cov[m] / 0.7
            # THE MOUND IS ROUND (restart 2: the first skirt rose from the cell's border to a flat top, so every mound
            # took its cell's polygon and the neck read as a pavement of tiles; c168o's mounds are puffy domes with
            # curved creases, lowest at the corners where the lone granules sit): a dome over the cell's own metric
            rd = np.clip(1.0 - d1[m] / 1.12, 0.0, 1.0)
            # (the plate, restart 2: a crease to zero at every cell border drew hexagonal sockets under grazing light:
            # the mounds now meet in a SHALLOW crease, so their outline is the round dome's, not the cell's polygon)
            # (third sitting, `crease`: how much lower the mound stands at its border than its round dome there; the old
            # 0.45 cut a V along every straight border, the nape's polygon net: c168o's mounds meet in soft valleys)
            cz = pl['crease'][own[m]]
            # (fix round 2, third sitting: the mound's own section `dome_n` / `dome_q` and crease band `crease_w`;
            # plan() says why; the old numbers take the old expressions, bit for bit)
            sk = 0.55 * H[m] * _dome_mound(pl, own[m], d1[m]) * ((1.0 - cz) + cz * smoothstep(0.0, pl['crease_w'][own[m]] * r[m], e[m]))
            # the cap's edge wobbles (no two caps one circle; `cap_wob`, 0.24 = the old: plan() says why)
            cc = cc * (1.0 + pl['cap_wob'][own[m]] * (vnoise(x[m, 0], x[m, 1], 1.3, 35) - 0.5))
            # FIX ROUND 1: THE CAP ITS OWN SHAPE (c168o's caps are 2.0 x longer than wide, sizes spread 0.37): in the
            # chart's own axes about the site, turned by its own `capturn`, `cap_elong` x longer along the body, its size
            # `capk` (1 and 0: the old round cap on the cell's metric)
            o = own[m]
            rc = cc * pl['capk'][o] * r[m]                      # the cap's radius, mm
            sxy = P['xy'][i1[m]]
            ct = pl['capturn'][o] * gsg[m]
            cct, sct = np.cos(ct), np.sin(ct)
            du_, dv_ = x[m, 0] - sxy[:, 0], x[m, 1] - sxy[:, 1]
            if X0 is not None:                                  # (`cap_true`: the cap at the true point; plan() says why)
                ctr = pl['cap_true'][o] > 0
                x0 = X0[sl][m]
                du_ = np.where(ctr, x0[:, 0] - sxy[:, 0], du_)
                dv_ = np.where(ctr, x0[:, 1] - sxy[:, 1], dv_)
            ce = pl['cap_elong'][o]
            dcap = np.hypot((cct * du_ + sct * dv_) / ce, (-sct * du_ + cct * dv_) * ce) / np.maximum(rc, 1e-6)
            round_cap = ce == 1.0
            dcap = np.where(round_cap & (pl['capk'][o] == 1.0) & (ct == 0.0), d1[m] / np.maximum(cc, 1e-6), dcap)
            sc = (1.0 - dcap) * rc
            outside = 1.0 - smoothstep(-0.10, 0.02, sc / r[m])
            wobr = 1.6 * (vnoise(x[m, 0], x[m, 1], 0.9, 31) - 0.5)       # the wrinkles wander: no two rings alike
            ring = 0.014 * H[m] * np.cos(2.0 * np.pi * (e[m] / (0.20 * r[m]) + rand01(pl['hid'][own[m]], 22) + wobr)) * smoothstep(0.03, 0.15, e[m] / r[m]) * outside
            cap = pl['cap_h'][o] * H[m] * _dome(sc / rc, 1.5, 0.85)   # a low cap flowing into its mound, not a marble
            # (third sitting, `cap_rim`: c168o's caps sit in a low wrinkled SOCKET RING, a fold of the mound round each
            # cap: a rounded ridge just outside the cap's edge, uneven round its length)
            cri = pl['cap_rim'][o]
            if np.any(cri > 0):
                rimn = 0.55 + 0.9 * vnoise(x[m, 0], x[m, 1], 1.1, 39)
                cap = cap + cri * H[m] * np.exp(-((sc / rc + 0.16) / 0.13) ** 2) * rimn
                # ...and a narrow groove between the cap and its ring (the dark line round every cap on the photo)
                cap = cap - 0.5 * cri * H[m] * np.exp(-((sc / rc + 0.03) / 0.05) ** 2)
            cr = pl['crumple'][o]
            if np.any(cr > 0):
                # THE MOUND CRUMPLED (c168o: "crumpled pale mounds", the check: "smooth white pillows"): two octaves of
                # noise on the mound, none on the cap, none at the border
                cn = 0.6 * (2.0 * vnoise(x[m, 0], x[m, 1], 0.85, 37) - 1.0) + 0.4 * (2.0 * vnoise(x[m, 0], x[m, 1], 0.38, 38) - 1.0)
                ring = ring + cr * H[m] * cn * outside * smoothstep(0.0, 0.25 * r[m], e[m])
            # (sixth sitting, `socket`: fine folds CONCENTRIC WITH THE CAP; plan() says why.) dn = cap radii outside
            # the cap's edge; the folds 0.24 of a cap radius apart, each cap's own phase, wandering, dying out down
            # the mound and at the cell's border (one sheet)
            dn = np.clip(-sc / np.maximum(rc, 1e-6), 0.0, None)
            so = pl['socket'][o]
            if np.any(so > 0):
                wob_s = 0.5 * (vnoise(x[m, 0], x[m, 1], 0.8, 59) - 0.5)
                ring = ring + (so * H[m] * np.cos(2.0 * np.pi * (dn / 0.24 + rand01(pl['hid'][o], 33) + wob_s)) * np.exp(-dn / 0.55)
                               * smoothstep(0.02, 0.10, dn) * smoothstep(0.0, 0.25 * r[m], e[m]))
            # (the collar is 0.35-0.5 of the cap's radius wide on c168o: full at the cap's edge, gone 0.8 radii out)
            halo[m] = (1.0 - smoothstep(0.10, 0.80, dn)) * outside * smoothstep(0.0, 0.15 * r[m], e[m])
            h[m] = sk + ring + cap
            top[m] = smoothstep(0.0, 0.10 * rc, sc)
            inner[m] = e[m] - 0.30
            ts[m] = 1.0
            band[m] = 0.35 * r[m]                               # the skirt's own band (its foot is G's: shared)
        # ---- plate (belly rows, the hand's rows) and whorl (tail rings): pillows in rounded rectangles; the grooves
        #      BETWEEN ROWS are the deeper; a whorl's rear edge stands free over the next ring
        for c in (PLATE, WHORL):
            m = cls == c
            if not m.any():
                continue
            ew = pl['edge_w'][own[m]]                       # (fix round 1: a pillow's own rise width, mm; 0 = the old)
            w = np.where(ew > 0, ew, np.minimum(0.45, 0.30 * r[m]))
            rear = np.clip(xi[m], -1.0, 1.0)
            # IMBRICATE (the plan's "imbricate option (a ramp to a free rear edge)", §5.4): each row rises to its rear
            # edge, which stands over the next row: steep there, gentle at the front. A whorl's default 0.40 (as it
            # was), a plate's 0 (the belly's flat pillows) unless its region asks (the hand's rows: 0.5)
            imb = pl['imbricate'][own[m]]
            imb = np.where(imb < 0.0, 0.40 if c == WHORL else 0.0, imb)
            # (fix round 1: rown is 2R, continuous; the old switch at rown > 0.5 jumped inside the cell)
            w = w * (1.0 - 1.375 * imb * rear * rown[m])
            t = np.clip(e[m] / w, 0.0, 1.0)
            pil = H[m] * (1.0 - (1.0 - t) ** 2.2) * (1.0 - 0.14 * np.minimum(d1[m], 1.0) ** 2)
            pc = pl['pillow_c'][own[m]]
            if np.any(pc > 0):
                # FIX ROUND 1: THE PILLOW LOWER AT ITS CORNERS (S2's belly: the groove between rows is SCALLOPED, each
                # plate's end rounded): where the round metric exceeds the cell's own exponent-4 one (0 at an edge's
                # middle, 0.2-0.3 at a corner)
                pil = pil * (1.0 - pc * smoothstep(0.0, 0.25, np.hypot(xi[m], et[m]) - d1[m]))
            # the grooves BETWEEN ROWS are the deeper (S2's belly and tail: they set the photo's strongest wavelength):
            # the row groove is now the shared ground's (_border_level), reached over the old groove's band 0.8 w
            band[m] = 0.8 * w
            pil = pil * (1.0 + imb * rear)
            lp = pl['lip'][own[m]]
            if np.any(lp > 0):                              # (fourth sitting, `lip`: a raised margin along the rim's middle)
                rml = np.maximum(pl['rim_mm'][own[m]], 0.05)
                lipn = 0.6 + 0.8 * vnoise(x[m, 0], x[m, 1], 0.8, 52)        # uneven along its length (a crust, not a bead of weld)
                pil = pil + lp * H[m] * lipn * np.exp(-((e[m] - 0.6 * rml) / (0.45 * rml)) ** 2)
            if c == PLATE:                                  # S2's belly: a dark brown spot near the front of some plates
                sp = rand01(pl['hid'][own[m]], 9) < pl['spot'][own[m]]
                mark[m] = sp * np.exp(-((xi[m] + 0.30) ** 2 / 0.45 ** 2 + (et[m] / 0.80) ** 2))
            if c == WHORL:
                o = own[m]
                ma, ml, mw = pl['mark_at'][o], pl['mark_len'][o], pl['mark_w'][o]
                old_mark = (ma == 0.45) & (ml == 0.22) & (mw == 0.75)
                # the keel: the whole scale long (the build), or only along its mark where the mark is shaped (resumed:
                # a keel the scale's length drew a lit line across every ring, S2's tail shows it only at each dash)
                kl = np.where(old_mark, 1.0, np.exp(-((xi[m] - ma) / (1.3 * ml)) ** 2))
                pil = pil + 0.22 * H[m] * np.exp(-(et[m] / 0.24) ** 2) * t * kl
                # (resumed: S2's tail marks are DASHES along the tail, a pit with a lit rim, each its own size and
                # place: `mark_at` / `mark_len` / `mark_w` / `mark_jit`; the pit follows its mark. The defaults: the
                # build's round blur)
                # each mark also its own place across the scale and its own strength (mark_jit; 0 = the old)
                mj = pl['mark_jit'][o]
                etm = et[m] - 0.35 * mj * (2.0 * rand01(pl['hid'][o], 28) - 1.0)
                pit = np.where(old_mark, np.exp(-((xi[m] - 0.50) ** 2 + (et[m] / 0.9) ** 2) / 0.12 ** 2),
                               np.exp(-(((xi[m] - ma - 0.04) / (0.6 * ml)) ** 2 + (etm / (0.6 * mw)) ** 2)))
                pil = pil - 0.55 * H[m] * pit
                mark[m] = np.where(old_mark, np.exp(-((xi[m] - ma) ** 2 / ml ** 2 + (et[m] / mw) ** 2)),
                                   np.exp(-((xi[m] - ma) ** 2 / ml ** 2 + (etm / mw) ** 2)) * (1.0 - 0.7 * mj * rand01(pl['hid'][o], 29)))
            pch = pl['patch'][own[m]]
            pmask = None
            if np.any(pch > 0):
                # (sixth sitting, `patch` on a plate; plan() says why.) c208's hand at x4: ALMOND shingles 2.7 long over
                # wide, pointed at both ends along the row, each a dark glossy almond standing proud of its own crusty
                # skirt; the build's and every fix's dark face was the plate's rounded rectangle less a rim ("slate
                # flagstones in pale mortar"). The blot in the plate's own frame (et along the row, xi across it), an
                # exponent `patch_p` under 2 along the row (pointed ends), turned a little its own way, its outline
                # wobbling; the plate stands `patch_low` lower outside it (lerped to the shared ground at the border
                # like the rest of the pillow: one sheet)
                o_ = own[m]
                pang = pl['patch_ang'][o_] * gsg[m]
                cp, sp_ = np.cos(pang), np.sin(pang)
                pe = np.sqrt(pl['patch_el'][o_])
                pa_, pc_ = cp * et[m] + sp_ * xi[m], -sp_ * et[m] + cp * xi[m]
                pq = np.maximum(pch, 1e-6)
                dp = np.sqrt((np.abs(pa_) / (pe * pq)) ** pl['patch_p'][o_] + (pc_ * pe / pq) ** 2)
                xr, yr = x[m, 0] / r[m], x[m, 1] / r[m]
                dp = dp + pl['patch_rag'][o_] * (0.6 * (2.0 * vnoise(xr, yr, 0.42, 57) - 1.0) + 0.4 * (2.0 * vnoise(xr + 9.0, yr, 0.16, 58) - 1.0))
                ps_ = pl['patch_soft'][o_]
                pmask = 1.0 - smoothstep(1.0 - ps_, 1.0 + ps_, dp)
                pil = np.where(pch > 0, pil * (1.0 - pl['patch_low'][o_] * (1.0 - pmask)), pil)
            h[m] = pil
            top[m] = smoothstep(0.3, 1.0, t)
            # (third sitting: this line was in the build and fell out of the edit of 11-11 13:13 that added the in-row
            # face: without it the skin granules stood at a third of their height all over every plate's face)
            inner[m] = e[m] - 0.5 * w
            ptp = pl['pig_t'][own[m]]
            if np.any(ptp > 0):
                # (third sitting, `pig_t` on a plate: c208's hand: each plate's dark middle inside its own frosted rim:
                # the pigment where the distance to the border, over the plate's half size, passes pig_t; feathered,
                # its edge wobbling)
                wob3 = 0.05 * (2.0 * vnoise(x[m, 0], x[m, 1], 1.1, 46) - 1.0) + 0.03 * (2.0 * vnoise(x[m, 0], x[m, 1], 0.4, 47) - 1.0)
                pfp = pl['pig_f'][own[m]]
                # (fourth sitting: the pigment's own edge ALONE; times the face's slow fade (t 0.3 to 1) it left no crisp
                # dark face at all: the hand's a3 was grey smears in white stipple)
                top[m] = np.where(ptp > 0, smoothstep(ptp - pfp, ptp + pfp, e[m] / r[m] + wob3), top[m])
            rmp = pl['rim_mm'][own[m]]
            if np.any(rmp > 0):                             # (fourth sitting, `rim_mm`: the rim a width in mm, as a bead's)
                wob5 = 0.05 * (2.0 * vnoise(x[m, 0], x[m, 1], 1.1, 46) - 1.0) + 0.03 * (2.0 * vnoise(x[m, 0], x[m, 1], 0.4, 47) - 1.0)
                # (fifth sitting, `rim_bias`: the rim wide at the rear edge the imbrication raises, none at the front)
                rmp = rmp * np.clip(1.0 + pl['rim_bias'][own[m]] * np.sign(imb) * rear, 0.0, 2.0)
                top[m] = np.where(rmp > 0, smoothstep(rmp - 0.05, rmp + 0.05, e[m] + wob5), top[m])
            # (fix round 1: within a row whose plates are fused (`inrow` > 0) the raised face CONTINUES across the in-row
            # crease, a faint line of skin left; between rows it ends at the groove. The build ended every plate's face at
            # every border: the dark skin drew every groove alike, "a brick wall")
            ir = pl['inrow'][own[m]]
            top[m] = top[m] + (1.0 - top[m]) * (1.0 - rown[m]) * np.clip(1.3 * ir, 0.0, 0.88)
            # (resumed 14:4x) A PIGMENTED CUSHION (`cush`, the level of the plate's own metric it fills; 0 = off): S2's
            # belly plates are each a yellow-cream cushion inside a paler tan margin, and the dark line is only the
            # groove; the build's and the first fix's faces ran to the border (one tan brick). Rounded by the metric's
            # own level sets, its edge wobbling; no in-row continuation (each plate its own cushion)
            cu = pl['cush'][own[m]]
            if np.any(cu > 0):
                # its extent ALONG the row (et) may differ (`cush_et`, a share of `cush`; 1 = the same): S2's cushions
                # run nearly to the in-row crease and stop well short of the row groove
                ce_ = cu * pl['cush_et'][own[m]]
                lvl = np.sqrt(np.sqrt((xi[m] / cu) ** 4 + (et[m] / np.maximum(ce_, 1e-6)) ** 4))
                lvl = lvl * (1.0 + 0.10 * (2.0 * vnoise(x[m, 0], x[m, 1], 0.9, 43) - 1.0))
                top[m] = np.where(cu > 0, smoothstep(1.12, 0.92, lvl) * smoothstep(0.0, 0.08, e[m]), top[m])
            if pmask is not None:                           # (sixth sitting, `patch`: the pigment is the plate's own blot)
                top[m] = np.where(pch > 0, pmask * smoothstep(0.0, 0.08, e[m]), top[m])
        # ---- granule (bands, pads): a small paver, its outline its cell's
        m = cls == GRANULE
        if m.any():
            # a ROUND bump (the plate, restart 2: a paver filling its cell drew Voronoi crazy-paving in every band);
            # skin shows at the corners where three granules meet, as on the animal's axilla and groin
            g = np.minimum(pl['gap'][own[m]], 0.25 * r[m])
            rg = np.clip(1.0 - d1[m] / 1.0, 0.0, 1.0)
            h[m] = H[m] * _dome(rg, 2.0, 0.6) * smoothstep(0.0, 0.5 * g, e[m])
            top[m] = smoothstep(0.02, 0.22, rg)
            inner[m] = (rg - 0.1) * r[m]
            band[m] = np.maximum(0.5 * g, 0.05)
        # ---- ridge (the tail's crest, one tooth a ring on the midline): a blade that rises to its rear
        m = cls == RIDGE
        if m.any():
            x1 = np.clip(xi[m], -1.0, 1.0)
            tri = np.where(x1 < 0.40, np.clip((x1 + 1.0) / 1.40, 0, 1) ** 1.25, np.clip((1.0 - x1) / 0.60, 0, 1) ** 0.75)
            t = np.clip(e[m] / np.minimum(0.5, 0.35 * r[m]), 0, 1)
            h[m] = H[m] * tri * np.exp(-(et[m] / 0.50) ** 2) * (0.2 + 0.8 * t) + 0.3 * (1.0 - (1.0 - t) ** 2)
            top[m] = smoothstep(0.15, 0.7, tri) * np.exp(-(et[m] / 0.6) ** 2)
            inner[m] = e[m] - 0.3
            ts[m] = 1.0
            band[m] = np.minimum(0.5, 0.35 * r[m])             # (its foot stood at 0.2 H: now the shared ground)
        # ---- ONE SHEET (fix round 1): every cell's own profile lerps to the shared ground over its band, so at a
        #      border (e = 0) both cells give G
        h = G + (h - G) * smoothstep(0.0, band, e)
        # ---- the skin the scales leave: fine granules, standing on the plinths and in the gaps, sunk in the creases
        #      (their weight is the same for every class at e = 0: `inner` at most e - 0.25 pitch, the cushion's boost 0)
        if mc is not None:
            dm, _ = mc['tree'].query(x, k=2, workers=-1)
            pm = mc['pitch']
            gd = np.clip(1.0 - (dm[:, 0] / (0.56 * pm)) ** 2, 0.0, 1.0) ** 0.8
            gd = gd * smoothstep(0.0, 0.12 * pm, 0.5 * (dm[:, 1] - dm[:, 0]))
            inner = np.minimum(inner, e - 0.25 * pm)
            wm = 1.0 - smoothstep(-0.25 * pm, 0.15 * pm, inner)
            # (third sitting, `frost_on`: the granules also stand on whatever of the scale is NOT pigmented: a pad's
            # frosted margin, a dome's crusty mound; they thin out with the pigment's feathered edge. At a border
            # top = 0 and wm = 1 for every class, as before: one sheet)
            wm = np.maximum(wm, pl['frost_on'][own] * (1.0 - top)) * (0.30 + 0.70 * smoothstep(0.0, 0.5 * pm, e))
            wm = wm * (1.0 + mc.get('mound_boost', 0.0) * mound * smoothstep(0.0, 0.15, e))   # coarser on a cushion (J1)
            hm = mc['h'] * gd * wm
            h = h + hm
            out['hmicro'][sl] = hm
        # ---- the keratin's own grain on the raised faces (rough plates on a hand, smooth beads on a back): its
        #      amount `gr` the candidates' blend at a border (above), the raised faces' share zero at the border
        h = h + gr * (2.0 * vnoise(x[:, 0], x[:, 1], 0.30, 51) - 1.0) * (0.25 + 0.75 * top * smoothstep(0.0, 0.10, e))
        # ---- (fifth sitting, 11-12) FACETS: glossy keratin is never glass. On every live photo (c208's forearm and
        #      hand, c168o's nape) the dark class the form gate segments is only FRAGMENTS of each face: the sky's sheen
        #      and the sun break into a graded patch and specks over a face rough at 0.1-0.4 mm, so the dark parts
        #      left point every way and vary inside; a smooth face is ONE uniform dark top, all of them lying one way
        #      (research/monitor_notes/d22_NOTES.md, fifth sitting: the masks). `facet` mm on the raised face only,
        #      two octaves (`facet_cell` and 0.45 of it), each turned off the chart's axes (a square value-noise
        #      lattice lines its grain up with u and v); its weight top x smoothstep(e) is 0 at every border, so the
        #      field stays one sheet, and it reads x = (u, |v|), so the mirror stays exact
        fa = pl['facet'][own]
        if np.any(fa > 0):
            fcl = pl['facet_cell'][own]
            u1, v1 = 0.799 * x[:, 0] - 0.602 * x[:, 1], 0.602 * x[:, 0] + 0.799 * x[:, 1]       # 37 deg
            u2, v2 = 0.326 * x[:, 0] - 0.946 * x[:, 1], 0.946 * x[:, 0] + 0.326 * x[:, 1]       # 71 deg
            fn = 0.62 * (2.0 * vnoise(u1, v1, fcl, 55) - 1.0) + 0.38 * (2.0 * vnoise(u2 + 17.0, v2, 0.45 * fcl, 56) - 1.0)
            h = h + fa * fn * top * smoothstep(0.0, 0.10, e)
        # ---- (sixth sitting) THE CRUST'S OWN RELIEF (`crust_h`; plan() says why): lumps on the unpigmented part of a
        #      scale, two octaves turned off the chart's axes, zero at every border (one sheet) and under the pigment;
        #      read at x = (u, |v|) (the mirror holds)
        ch = pl['crust_h'][own]
        if np.any(ch > 0):
            ccl = pl['crust_cell'][own]
            u3, v3 = 0.891 * x[:, 0] - 0.454 * x[:, 1], 0.454 * x[:, 0] + 0.891 * x[:, 1]       # 27 deg
            u4, v4 = 0.530 * x[:, 0] - 0.848 * x[:, 1], 0.848 * x[:, 0] + 0.530 * x[:, 1]       # 58 deg
            cn_ = 0.60 * (2.0 * vnoise(u3, v3, ccl, 63) - 1.0) + 0.40 * (2.0 * vnoise(u4 + 31.0, v4, 0.45 * ccl, 64) - 1.0)
            h = h + ch * cn_ * (1.0 - top) * smoothstep(0.0, 0.10, e)
        out['mark'][sl] = mark
        out['mound'][sl] = mound
        out['halo'][sl] = halo
        out['ground'][sl] = G
        out['rown'][sl] = np.where((cls == PLATE) | (cls == WHORL) | lat_rows, rown, 0.0)   # 1 at a border between ROWS
        out['h'][sl] = h
        out['top'][sl] = top
        out['groove'][sl] = 1.0 - smoothstep(0.0, np.minimum(0.45, 0.3 * r), e)
        out['e'][sl] = e
        out['rho'][sl] = d1
        out['tier_s'][sl] = ts
        out['id'][sl] = own
        out['cls'][sl] = cls
        gs = np.where(P['ghost'][i1], -1.0, 1.0)
        out['side'][sl] = np.where(pl['mid'][own], 0.0, gs * sgn[sl])
    return {k: a.reshape(shp) for k, a in out.items()}


def tint_random(ids, side, salt=0):
    """every per-scale random the eye can see is hash(id, side): stacked halves bake ONE id map, yet the two sides'
    speckles differ; a midline scale (side 0) is one colour (the critic's §5.6 point)"""
    return rand01(np.asarray(ids, np.int64) * 3 + (np.asarray(side, np.int64) + 1), 100 + salt)


def summary(pl):
    """per class: count, the mid-border half size and the relief (what G-S1 / G-S4 print)"""
    rows = {}
    for c in range(6):
        m = pl['cls'] == c
        if m.any():
            rows[CLASS_NAMES[c]] = dict(n=int(m.sum()), tier=TIER[c],
                                        pitch_mm=[float(np.percentile(2 * pl['r_mm'][m], q)) for q in (10, 50, 90)],
                                        relief_mm=[float(np.percentile(pl['relief'][m], q)) for q in (10, 50, 90)])
    return rows
