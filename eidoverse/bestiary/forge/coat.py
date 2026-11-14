"""THE COAT (WOLF_PLAN.md §4.3): a furred creature's envelope is its approved skin minus a smooth coat-depth field c(p).

The skin is sculpted bald at true mass and approved as clay first (CG 16.9: slimming for fur, or building ruffs into
the body, gives gaunt anatomy and wrong silhouettes); the coat is a layer on it. c is the depth at which the coat turns
visually opaque, about 0.55 of the coat depth (WOLF_PLAN §5.1). It lives on a regular grid and enters the shape as the
program's LAST primitive (sdf.Program.offset_grid, the OFFSET patch: work/bestiary/patches/sdf_offset.md):

    d_env(p) = (d_skin(p) - s c(p)) / (1 + s g)      s the coat scale: 0 the bare skin, 1 the coat, ~0.3 under a hat

with g a bound on |grad c| of the grid's trilinear interpolant, so d_env stays a distance bound (the sphere tracers,
the voxel band and the bake's rays rely on it).

    c, origin, g = coat_grid(prog_skin, SPEC)                                   the grid: §4.3's three stages
    prog_env = envelope(prog_skin, c, origin, g, SPEC['coat']['cell'])          the skin's program plus the coat

WHERE THE DEPTHS COME FROM: region_table(spec), in anatomical coordinates. The skin builder TAGS each skin primitive
with its coat part and the chain it is measured on (tag(); untagged primitives own no coat: carves, inner parts). Bare
skin that is no primitive of its own (the eyelids, which are the sculpt plan's carves; later each growth's footprint
and its parted ring, §5.5) is a bare_volume(). Every grid point then takes
  * its OWNER: the tagged primitive whose own field is least there (outside the skin the nearest surface; inside it,
    among the coated parts only, so a buried bare part never thins the coat over it);
  * its anatomical coordinates on the owner's chain: s, the normalized arclength at the nearest chain point, and the
    outward direction from it, split into the chain's cross-section (dorsal / ventral, or cranial / caudal on a hanging
    limb, and lateral / medial) and its axis (past the chain's ends: a rump, a tail tip);
  * c = the part's table at s, blended by the squared direction components (they sum to 1), or c = 0 and BARE for a
    bare class (nose leather, lips, lids, pads, ears) from half a cell inside the skin to spec['coat']['bare_reach']
    (one cell) outside it. Farther out a bare part's points take the nearest coated part's depths: a bare part that
    owned the open air round it would pull the coat down there (the toy's lips owned the air under the chin, in front
    of the throat, and thinned the apron through the clamp; w02_coat.py).
The bare mask is dilated by one cell, so every cell that touches bare skin has all eight corners at 0 and the trilinear
c is exactly 0 on the bare skin itself (the cage's lip seam and lid rings settle on the skin). Then the three stages
(wolf_checks.py §4's coat_grid is the reference; clamp_grid reproduces it bit for bit):
  1. a Gaussian (sigma 6 mm) smooths the table's steps; a convolution never raises a Lipschitz constant;
  2. c = min(c, g_t EDT(~bare) cell) puts the zeros back exactly on the bare points, with a cone of slope g_t round them;
  3. a min-plus clamp c(p) <= c(q) + g_t |p - q| over the 26 neighbours, iterated until nothing changes, shaves every
     step still too steep.
g = lipschitz_bound(c, cell) of the float32 values the program reads: in each cell each gradient component of the
trilinear interpolant is a bilinear blend of the cell's four edge differences along its axis, so |grad c| is at most
the norm of the three largest edge slopes. W1 clamps at g_t 0.30 (g about 0.52: the envelope's analytic steps shrink by
1 / (1 + g), about 0.66; inside the voxel band the redistanced values are true distances again).
"""
import sys
import time

import numpy as np
from scipy import ndimage as nd
from scipy.spatial import cKDTree

BARE = ('nose', 'lip', 'lid', 'pad', 'ear', 'bare')     # bare classes: c = 0 exactly (WOLF_PLAN §4.3)

# W1's winter coat (WOLF_PLAN §5.1, its 'envelope c' column, all [E]; to be fitted by eye at W3 against furred
# photographs at matched scale). Per part: stations s along its chain (normalized arclength, in the direction named)
# and c in MILLIMETRES for each direction of the chain's cross-section. axis 'up': the first pair is dorsal (pos) /
# ventral (neg), for a chain that runs along the body; 'fwd': cranial (pos) / caudal (neg), for a hanging limb. lat /
# med: away from / toward the midline (a midline chain is lateral on both sides; med None = lat). end: along the
# chain's own axis, past its ends. species/wolf.py's SPEC['coat']['table'] overrides or adds parts in this layout.
W1_TABLE = dict(
    # the trunk-and-neck sweep (§4.2), C1 (s 0) to the ischia (s 1), T1 (the withers) near s 0.27: the mane and crest
    # (30-35) over the neck and withers, the dorsal stripe (20), the flanks (15), the throat and chest apron (22), the
    # belly (6-10), the rump
    body=dict(axis='up', s=(0.00, 0.12, 0.27, 0.40, 0.55, 0.80, 1.00),
              pos=(30, 33, 34, 26, 20, 20, 20), neg=(22, 22, 22, 15, 8, 8, 10),
              lat=(18, 19, 20, 16, 15, 15, 15), med=None, end=(22, 22, 22, 16, 15, 15, 18)),
    # the head's axis, the nose tip (s 0) to the occiput (s 1), the stop at 0.42 and the eyes at 0.49 (§2.5): the
    # muzzle (2), the crown and forehead (5), the cheek ruff (15-18) behind the eyes, the throat under the jaw running
    # into the apron
    head=dict(axis='up', s=(0.00, 0.42, 0.49, 0.62, 0.80, 1.00),
              pos=(2, 2, 5, 5, 5, 6), neg=(2, 4, 6, 10, 18, 22),
              lat=(2, 2, 5, 15, 17, 16), med=None, end=(2, 2, 5, 5, 6, 8)),
    # the muzzle sweep, the nose tip (s 0) to the stop (s 1)
    muzzle=dict(axis='up', s=(0.0, 1.0), pos=(2, 2), neg=(3, 3), lat=(2, 2), med=None, end=(2, 2)),
    # a forelimb's sweep, from inside the trunk (s 0) to the MCP (s 1): the upper limb's outer coat (9), the lower limb
    # (4), the inner faces shorter
    forelimb=dict(axis='fwd', s=(0.00, 0.35, 0.55, 1.00),
                  pos=(12, 9, 5, 4), neg=(12, 9, 6, 4), lat=(12, 9, 5, 4), med=(9, 7, 4, 3), end=(12, 9, 5, 2)),
    # a hindlimb's sweep, from inside the trunk (s 0) to the MTP (s 1): the britches on the caudal thigh (21), the upper
    # limb (9), the inner thigh (6-10), the lower limb (4)
    hindlimb=dict(axis='fwd', s=(0.00, 0.30, 0.50, 0.70, 1.00),
                  pos=(10, 9, 6, 4, 4), neg=(21, 21, 12, 5, 4), lat=(12, 9, 7, 4, 4), med=(8, 8, 6, 3, 3),
                  end=(12, 9, 6, 4, 2)),
    # the paws' dorsal coat (1.5; the pads are bare primitives of their own)
    paw=dict(axis='up', s=(0.0, 1.0), pos=(1.5, 1.5), neg=(1.0, 1.0), lat=(1.5, 1.5), med=None, end=(1.5, 1.5)),
    # the tail sweep, the root (s 0) to the tip (s 1): the brush (35), longest in the middle third
    tail=dict(axis='up', s=(0.00, 0.33, 0.66, 1.00),
              pos=(25, 35, 35, 28), neg=(20, 30, 30, 25), lat=(22, 35, 35, 28), med=None, end=(25, 35, 35, 30)),
)


def region_table(spec):
    """the coat-depth table in METRES: {part: dict(axis, s, pos, neg, lat, med, end, bare=False)} for the coated parts
    and {part: dict(bare=True)} for the bare classes. W1_TABLE (millimetres) with spec['coat']['table'] overriding or
    adding parts (the same layout; a part's keys merge over W1's), every depth times spec['coat']['depth_scale']
    (default 1; a summer coat is about 0.5-0.6, §5.1)"""
    cs = (spec or {}).get('coat', {})
    rows = {k: dict(v) for k, v in W1_TABLE.items()}
    for k, v in (cs.get('table') or {}).items():
        rows[k] = {**rows.get(k, {}), **v}
    ds = float(cs.get('depth_scale', 1.0))
    out = {}
    for part, r in rows.items():
        assert part not in BARE, f'{part!r} is a bare class: c = 0 there by definition'
        s = np.asarray(r['s'], np.float64)
        assert s.ndim == 1 and len(s) >= 1 and np.all(np.diff(s) >= 0.0), f'{part}: stations s must ascend'
        axis = r.get('axis', 'up')
        assert axis in ('up', 'fwd'), f'{part}: axis is up or fwd'
        cols = {}
        for col in ('pos', 'neg', 'lat', 'med', 'end'):
            v = r.get(col)
            v = r['lat'] if v is None else v
            v = np.broadcast_to(np.asarray(v, np.float64), s.shape) * (1.0e-3 * ds)
            assert np.all(v >= 0.0), f'{part}.{col}: a coat depth is >= 0'
            cols[col] = v.copy()
        out[part] = dict(axis=axis, s=s, bare=False, **cols)
    for b in BARE:
        out[b] = dict(bare=True)
    return out


def tag(prog, index, part, chain=None):
    """mark skin primitive `index` (what every sdf.Program method returns) as coat part `part`: a region_table part or
    a bare class (BARE). chain: what its anatomical coordinates are measured on, an (N, 3) polyline in the direction
    the part's table names (a limb's joint chain, the head's axis from the nose to the occiput) or the index of a SWEEP
    (its centreline); default its own centreline (a SWEEP) or axis (a ROUNDCONE). A bare class needs no chain. Only
    UNION primitives own skin (carves stay untagged). Returns index, so a builder can wrap its calls"""
    tags = getattr(prog, 'coat_tags', None)
    if tags is None:
        tags = prog.coat_tags = {}
    tags[int(index)] = (str(part), chain)
    return index


def bare_volume(prog, center, radii, axes=None):
    """an ellipsoid of bare skin that is no primitive of its own (the eyelids: the sculpt plan's carves; later each
    growth's footprint plus its parted ring, §5.5): the grid points inside it from half a cell inside the skin to the
    bare reach outside it are bare. axes: 3 x 3, columns the ellipsoid's local axes (default the world's)"""
    R = np.eye(3) if axes is None else np.asarray(axes, np.float64)
    R = R / np.linalg.norm(R, axis=0, keepdims=True)
    vols = getattr(prog, 'coat_bare', None)
    if vols is None:
        vols = prog.coat_bare = []
    vols.append((np.asarray(center, np.float64), np.asarray(radii, np.float64), R))


def lipschitz_bound(c, cell):
    """the exact bound on |grad| of the trilinear interpolant of the grid values c (cell apart): in each cell each
    gradient component is a bilinear blend of the cell's four edge differences along its axis, so |dc/dx| <= the
    largest of them / cell, and |grad c| <= the norm of the three (wolf_checks.py §4, the reference)"""
    c = np.asarray(c, np.float64)
    dx = np.abs(np.diff(c, axis=0)) / cell
    dy = np.abs(np.diff(c, axis=1)) / cell
    dz = np.abs(np.diff(c, axis=2)) / cell
    gx = np.maximum.reduce([dx[:, :-1, :-1], dx[:, 1:, :-1], dx[:, :-1, 1:], dx[:, 1:, 1:]])
    gy = np.maximum.reduce([dy[:-1, :, :-1], dy[1:, :, :-1], dy[:-1, :, 1:], dy[1:, :, 1:]])
    gz = np.maximum.reduce([dz[:-1, :-1, :], dz[1:, :-1, :], dz[:-1, 1:, :], dz[1:, 1:, :]])
    return float(np.sqrt(gx ** 2 + gy ** 2 + gz ** 2).max())


def clamp_grid(c_raw, bare, cell, g_t=0.30, sigma=0.006, iters=200, crisp=None, g_t_crisp=0.45):
    """§4.3's three stages on a raw coat grid (metres) and its bare mask (bool, c = 0 exactly there): the Gaussian
    (sigma metres), the bare zeros restored as a cone of slope g_t, then the min-plus clamp c(p) <= c(q) + g_t |p - q|
    over the 26 neighbours until nothing changes. With crisp None this is wolf_checks.py's coat_grid, operation for
    operation. crisp (bool grid, optional): those points clamp at g_t_crisp instead (an edge that must stay sharp, the
    mane's border: §4.3; g is one number for the whole envelope, so it costs every step everywhere). Returns (c float64,
    the clamp's iterations, settled: False if `iters` ran out; lipschitz_bound measures the result either way)"""
    c = nd.gaussian_filter(np.where(bare, 0.0, c_raw), sigma / cell, mode='nearest')
    gt = g_t if crisp is None else np.where(crisp, g_t_crisp, g_t)
    if bare.any():
        c = np.minimum(c, gt * nd.distance_transform_edt(~bare) * cell)
    off = np.linalg.norm(np.stack(np.meshgrid(*[np.arange(-1, 2)] * 3, indexing='ij'), -1), axis=-1)
    S = -g_t * cell * off                                   # grey_erosion: min over (c(x + y) - S(y))
    Sc = -g_t_crisp * cell * off
    for it in range(iters):
        c2 = nd.grey_erosion(c, structure=S, mode='nearest')
        if crisp is not None:
            c2 = np.where(crisp, nd.grey_erosion(c, structure=Sc, mode='nearest'), c2)
        if np.array_equal(c2, c):
            return c, it, True
        c = c2
    return c, iters, False


def trilinear(c, origin, cell, P):
    """c at the points P (n, 3), float64, as the OFFSET kernel samples it: trilinear, the point clamped to the box"""
    c = np.asarray(c, np.float64)
    n = np.array(c.shape)
    q = np.clip((np.asarray(P, np.float64) - np.asarray(origin, np.float64)) / cell, 0.0, n - 1.0)
    i = np.minimum(np.floor(q).astype(np.int64), n - 2)
    f = q - i
    out = np.zeros(len(q))
    for a in (0, 1):
        for b in (0, 1):
            for e in (0, 1):
                w = (f[:, 0] if a else 1 - f[:, 0]) * (f[:, 1] if b else 1 - f[:, 1]) * (f[:, 2] if e else 1 - f[:, 2])
                out += w * c[i[:, 0] + a, i[:, 1] + b, i[:, 2] + e]
    return out


# ---------------------------------------------------------------------------------------------------- the grid
def _sdf_of(prog):
    """the sdf module that built prog (the forge's, or a private patched copy under test)"""
    return sys.modules[type(prog).__module__]


def _view(prog, i):
    """primitive i of prog alone, as a UNION of one (the same node, shell and thickness data: nothing is copied)"""
    S = _sdf_of(prog)
    v = S.Program()
    v.node_p, v.node_n, v.node_r, v.node_h = prog.node_p, prog.node_n, prog.node_r, prog.node_h
    v.shell_meshes, v.shell_thick, v.shell_tri = prog.shell_meshes, prog.shell_thick, prog.shell_tri
    p = np.array(prog.par[i], np.float32, copy=True)
    p[20:23] = (0.0, float(S.UNION), 0.0)
    v.kind, v.op, v.k, v.par, v.names = [prog.kind[i]], [S.UNION], [0.0], [p], [prog.names[i]]
    return v


def _box_dist(P, lo, hi):
    q = np.maximum(np.maximum(lo - P, P - hi), 0.0)
    return np.sqrt((q * q).sum(1))


def owners(prog, P, table=None):
    """per point of P (n, 3): (owner, coated owner, field). owner: the tagged primitive whose own field is least (the
    nearest surface outside the skin, the deepest primitive inside it); coated owner: the same over the coated parts
    only; field: that least value, the tagged skin's hard union. -1 / inf where nothing is tagged. Each primitive is
    evaluated alone (_view), only where its padded box is not farther than the best so far; a SHELL's 'nothing within
    maxd' reads as infinitely far"""
    S = _sdf_of(prog)
    tags = prog.coat_tags
    table = table if table is not None else region_table({})
    P32 = np.ascontiguousarray(P, np.float32)
    n = len(P32)
    best = np.full(n, np.inf)
    own = np.full(n, -1, np.int32)
    best_c = np.full(n, np.inf)
    own_c = np.full(n, -1, np.int32)
    for i in sorted(tags):
        part = tags[i][0]
        assert prog.op[i] == S.UNION, f'coat: tagged primitive {i} ({prog.names[i]!r}) is not a UNION: carves own no skin'
        bare = table[part]['bare']
        lo, hi = prog.par[i][24:27].astype(np.float32), prog.par[i][27:30].astype(np.float32)
        thr = np.maximum(best if bare else best_c, 0.0)
        m = np.nonzero(_box_dist(P32, lo, hi) <= thr)[0]
        if len(m) == 0:
            continue
        d = _view(prog, i).eval(P32[m]).astype(np.float64)
        if prog.kind[i] == S.SHELL:
            d[d >= float(prog.par[i][2]) * (1.0 - 1.0e-6)] = np.inf
        b = d < best[m]
        best[m[b]] = d[b]
        own[m[b]] = i
        if not bare:
            b = d < best_c[m]
            best_c[m[b]] = d[b]
            own_c[m[b]] = i
    return own, own_c, best


class _Chain:
    """a polyline resampled every `step` (m): arclength s in [0, 1], unit tangents, a k-d tree; side: the sign of its
    mean x (0 for a midline chain, whose lateral side is each point's own)"""

    def __init__(self, C, step=0.001):
        C = np.asarray(C, np.float64).reshape(-1, 3)
        keep = np.concatenate([[True], np.linalg.norm(np.diff(C, axis=0), axis=1) > 1.0e-12])
        C = C[keep]
        L = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
        assert len(C) >= 2 and L[-1] > 1.0e-6, 'a coat chain needs length'
        u = np.linspace(0.0, L[-1], max(2, int(np.ceil(L[-1] / step)) + 1))
        self.P = np.column_stack([np.interp(u, L, C[:, k]) for k in range(3)])
        self.s = u / L[-1]
        T = np.gradient(self.P, axis=0)
        self.T = T / np.linalg.norm(T, axis=1, keepdims=True)
        self.tree = cKDTree(self.P)
        mx = float(np.mean(C[:, 0]))
        self.side = 0.0 if abs(mx) < 0.005 else float(np.sign(mx))


def _chain_points(prog, i, chain):
    S = _sdf_of(prog)
    if chain is None:
        if prog.kind[i] == S.ROUNDCONE:
            return np.array([prog.par[i][0:3], prog.par[i][3:6]], np.float64)
        if prog.kind[i] != S.SWEEP:
            raise ValueError(f'coat: primitive {i} ({prog.names[i]!r}) needs a chain= to be measured on')
        chain = i
    if isinstance(chain, (int, np.integer)):
        j = int(chain)
        assert prog.kind[j] == S.SWEEP, f'coat: chain {j} is not a SWEEP'
        st, cnt = int(prog.par[j][0]), int(prog.par[j][1])
        return np.asarray(prog.node_p[st:st + cnt], np.float64)
    return np.asarray(chain, np.float64)


_UP = np.array([0.0, 1.0, 0.0])
_FWD = np.array([0.0, 0.0, 1.0])


def depths(row, ch, P):
    """c (m) at the points P (n, 3) of a coated part (a region_table row) measured on its _Chain"""
    _, idx = ch.tree.query(P)
    s, t, foot = ch.s[idx], ch.T[idx], ch.P[idx]
    q = P - foot
    q = q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1.0e-12)
    a = np.einsum('ij,ij->i', q, t)
    u = q - a[:, None] * t
    un = np.linalg.norm(u, axis=1)
    A, A2 = (_UP, _FWD) if row['axis'] == 'up' else (_FWD, _UP)
    d = A[None] - (t @ A)[:, None] * t
    dn = np.linalg.norm(d, axis=1)
    weak = dn < 0.2                                     # the chain runs along A: the section's pair from the other axis
    if weak.any():
        d[weak] = A2[None] - (t[weak] @ A2)[:, None] * t[weak]
        dn[weak] = np.linalg.norm(d[weak], axis=1)
    d /= dn[:, None]
    lat = np.cross(t, d)
    lat /= np.linalg.norm(lat, axis=1, keepdims=True)
    side = np.full(len(P), ch.side) if ch.side != 0.0 else np.where(P[:, 0] < 0.0, -1.0, 1.0)
    lat[lat[:, 0] * side < 0.0] *= -1.0                 # lateral: away from the midline
    ok = un > 1.0e-9
    wd = np.where(ok, np.einsum('ij,ij->i', u, d) / np.maximum(un, 1.0e-12), 1.0)
    wl = np.where(ok, np.einsum('ij,ij->i', u, lat) / np.maximum(un, 1.0e-12), 0.0)
    v = {k: np.interp(s, row['s'], row[k]) for k in ('pos', 'neg', 'lat', 'med', 'end')}
    sec = (v['pos'] * np.maximum(wd, 0.0) ** 2 + v['neg'] * np.maximum(-wd, 0.0) ** 2
           + v['lat'] * np.maximum(wl, 0.0) ** 2 + v['med'] * np.maximum(-wl, 0.0) ** 2)
    return (1.0 - a * a) * sec + a * a * v['end']


def grid_frame(prog, cell, pad):
    """the coat grid's origin and shape: the tagged skin primitives' padded boxes plus pad (m), in cells"""
    tags = prog.coat_tags
    lo = np.min([prog.par[i][24:27] for i in tags], axis=0).astype(np.float64) - pad
    hi = np.max([prog.par[i][27:30] for i in tags], axis=0).astype(np.float64) + pad
    assert np.all(np.abs(lo) < 1.0e3) and np.all(np.abs(hi) < 1.0e3), 'coat: a tagged primitive has no bounds'
    shape = tuple(int(np.ceil((hi[a] - lo[a]) / cell)) + 1 for a in range(3))
    return lo, shape


def coat_grid(prog_skin, spec, info=None, log=None):
    """the coat-depth grid of a tagged skin program: (c, origin, g). c (nx, ny, nz) float32 metres, c[i, j, k] at
    origin + cell (i, j, k) (spec['coat']['cell']: 6 mm for W1) over the tagged skin's box plus spec['coat']['pad']
    (0.1 m); g = lipschitz_bound(c, cell), what sdf.Program.offset_grid needs. spec['coat']: cell, g_t (0.30), and
    optional sigma (the cell), pad, bare_reach (the cell), iters (200), crisp (parts clamped at g_t_crisp, 0.45),
    table, depth_scale. info (a dict) receives the owner, bare and raw grids, counts and timings for the W3 gates"""
    S = _sdf_of(prog_skin)
    assert getattr(S, 'OFFSET', -1) not in prog_skin.kind, 'coat_grid takes the bare skin, not an envelope'
    tags = getattr(prog_skin, 'coat_tags', None)
    assert tags, 'coat_grid needs tagged skin primitives (coat.tag)'
    cs = spec['coat']
    cell, g_t = float(cs['cell']), float(cs['g_t'])
    sigma, pad = float(cs.get('sigma', cell)), float(cs.get('pad', 0.1))
    reach = float(cs.get('bare_reach', cell))
    table = region_table(spec)
    for i, (part, _) in tags.items():
        assert part in table, f'coat: primitive {i} ({prog_skin.names[i]!r}) has an unknown part {part!r}'
    origin, shape = grid_frame(prog_skin, cell, pad)
    t0 = time.time()
    P = np.stack(np.meshgrid(*[origin[a] + cell * np.arange(shape[a]) for a in range(3)], indexing='ij'),
                 -1).reshape(-1, 3)
    own, own_c, field = owners(prog_skin, P, table)
    t1 = time.time()
    near = field >= -0.5 * cell                         # outside the skin, or within half a cell of it
    shell = near & (field <= reach)                     # where a bare class is bare
    bare_of = np.zeros(len(prog_skin.kind) + 1, bool)   # (the last slot: no owner)
    for i, (part, _) in tags.items():
        bare_of[i] = table[part]['bare']
    use = np.where(near & (~bare_of[own] | shell), own, own_c)
    c_raw = np.zeros(len(P))
    bare = np.zeros(len(P), bool)
    order = np.argsort(use, kind='stable')
    ids, first, count = np.unique(use[order], return_index=True, return_counts=True)
    chains = {}
    for i, a, m in zip(ids, first, count):
        if i < 0:
            continue
        sel = order[a:a + m]
        part, chain = tags[int(i)]
        row = table[part]
        if row['bare']:
            bare[sel] = True                            # a bare owner is only used inside its shell
            continue
        key = id(chain) if chain is not None and not isinstance(chain, (int, np.integer)) else \
            int(i if chain is None else chain)
        if key not in chains:
            chains[key] = _Chain(_chain_points(prog_skin, int(i), chain))
        for b in range(0, len(sel), 1_000_000):
            sb = sel[b:b + 1_000_000]
            c_raw[sb] = depths(row, chains[key], P[sb])
    for cen, rad, R in getattr(prog_skin, 'coat_bare', []):
        L = ((P - cen) @ R) / rad
        bare |= ((L * L).sum(1) <= 1.0) & shell
    n_bare0 = int(bare.sum())
    bare = nd.binary_dilation(bare.reshape(shape), structure=np.ones((3, 3, 3), bool))
    c_raw = c_raw.reshape(shape)
    crisp_parts = tuple(cs.get('crisp', ()))
    crisp = None
    if crisp_parts:
        crisp_ids = np.array([i for i, (p, _) in tags.items() if p in crisp_parts] or [-2])
        crisp = np.isin(use, crisp_ids).reshape(shape)
    t2 = time.time()
    c, iters, settled = clamp_grid(c_raw, bare, cell, g_t, sigma, int(cs.get('iters', 200)), crisp,
                                   float(cs.get('g_t_crisp', 0.45)))
    c32 = c.astype(np.float32)
    g = lipschitz_bound(c32, cell)
    t3 = time.time()
    if info is not None:
        info.update(origin=origin, shape=shape, cell=cell, g_t=g_t, g=g, owner=use.reshape(shape),
                    field=field.reshape(shape).astype(np.float32), bare=bare, c_raw=c_raw.astype(np.float32),
                    n_bare_classified=n_bare0, n_bare=int(bare.sum()), bare_max=float(c32[bare].max()) if bare.any()
                    else 0.0, iters=iters, settled=settled, t_owners=t1 - t0, t_table=t2 - t1, t_stages=t3 - t2)
    if log:
        log(f'[coat] grid {shape} ({np.prod(shape) / 1e6:.2f} M, cell {cell * 1000:.1f} mm): owners {t1 - t0:.1f}s, '
            f'table {t2 - t1:.1f}s, stages {t3 - t2:.1f}s ({iters} clamp passes{"" if settled else ", NOT settled"}); '
            f'bare {int(bare.sum())} points, c {c32.min() * 1000:.1f}-{c32.max() * 1000:.1f} mm, g {g:.3f} '
            f'(g_t {g_t:.2f})')
    return c32, origin, g


def envelope(prog_skin, c, origin, g, cell, scale=1.0, name='coat'):
    """a NEW program: the skin's primitives (lists copied, node, shell and mesh data shared) and the coat on them as
    its last primitive (sdf.Program.offset_grid, the OFFSET patch). scale 1 the coat, ~0.3 pressed under a hat, 0 the
    skin itself; the skin program is left as it was"""
    S = _sdf_of(prog_skin)
    assert hasattr(S.Program, 'offset_grid'), 'this sdf module has no OFFSET (work/bestiary/patches/sdf_offset.md)'
    e = S.Program()
    e.kind, e.op, e.k, e.names = list(prog_skin.kind), list(prog_skin.op), list(prog_skin.k), list(prog_skin.names)
    e.par = [np.array(p, np.float32, copy=True) for p in prog_skin.par]
    e.node_p, e.node_n, e.node_r, e.node_h = (list(prog_skin.node_p), list(prog_skin.node_n), list(prog_skin.node_r),
                                              list(prog_skin.node_h))
    e.shell_meshes, e.shell_thick, e.shell_tri = (list(prog_skin.shell_meshes), list(prog_skin.shell_thick),
                                                  list(prog_skin.shell_tri))
    e._next_gid = prog_skin._next_gid
    e.offset_grid(origin, cell, c, g, scale=scale, name=name)
    return e
