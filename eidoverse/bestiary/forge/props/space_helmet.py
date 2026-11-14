"""The SPACE HELMET: the Apollo moon helmet (ROADMAP B5; DESIGN.md "Helmets: space, hardhat"; the old creator's
helmet 'space'), built at real size the forge way (the hard hat's recipe: accessories_b5/hard_NOTES.md; the parts,
UVs, maps and export of soft_common.py, the SOFT builder's kit). Its log: accessories_b5/hard_NOTES.md.

THE OBJECT (accessories_b5/space_helmet/refs_photos/SOURCES.txt; the board of three candidates is in the showcase): the
A7L PRESSURE BUBBLE inside its LUNAR EXTRAVEHICULAR VISOR ASSEMBLY (the LEVA), the GOLD SUN VISOR down, as on the Moon:
the white thermal cover over a shell, a thick rolled rim round the visor's window, the central eyeshade folded up over
the brow, the visor's pivot hubs at the temples, the anodized NECK RING below (blue on Apollo 11 and 12, red later:
the palette). The clear bubble shows only below the visor's lower edge (a creature's face behind clear plastic needs
a transmissive material the hat path does not have: hard_NOTES.md, the visor-up variant).

  parts (each its own closed description; soft_common's part dicts):
    hood     the cover's shell: a mid-surface r(a, y) = smooth max of an ellipsoid round the bubble and a sphere round
             the visor (the brow and the cheeks bulge round the window), cut by the WINDOW (an arch from the hem up)
    rim      the rolled edge round the window: a tube on the window's boundary
    shade    the central eyeshade, up: a raised strip over the brow and the crown
    hem      the cover's lower edge ALL ROUND: a tube on the hem; across the front it is the window's SILL (11-12)
    hub      the visor's pivot at each temple: a short drum
    visor    the gold visor: a sphere patch behind the window, and its lower edge
    seal     (11-12) black rubber that closes the shells: a BEAD in the slot between the rim's roll and the visor
             (the window's sides and top), an APRON on the visor's sphere from its lower edge down to the sill, the
             LEDGE from the apron's foot to the sill, the PLATE under the cover from the hem in to the ring. (Before
             it the far visor's inner face showed through the slot from three-quarter views, and the cheeks were
             see-through from below: a prop's material is single-sided)
    cavity   the bubble's inner surface, seen up through the neck ring
    ring     the neck ring: a lathe profile (its bayonet lip), anodized aluminium
  -> the AUTHORED low (WORKING_RULES 2): rows of constant height and columns of constant azimuth ON the analytic
     surfaces (the window's sides on columns, its top on a row), a grid cap, tubes of rings, lathes: no algorithm picks
     a vertex; the budget from the closest view (the 0.4 m portrait, 0.43 mm a pixel)
  -> UVs (mirror halves stacked, lathes' sectors stacked; the visor's mirror at a low texel share: a polished gold
     film carries almost no texture), voxel high + bake, material pass, the shipped set delivered at what the closest
     view samples (soft_common.deliver_maps), a static glb with its FIT data

Frame: metres, +Y up (the bubble's axis), the origin at the centre of the NECK RING's lower face, +Z forward (the
visor), +X the wearer's left. `a`: the plan azimuth from +Z toward +X.

NUMBERS ([C] published, [M] measured on a photo, [E] estimate): the Smithsonian NASM's records [C] (numbers only):
"Helmet, Pressure Bubble, Apollo" (A19980122000) 26 x 30.5 x 27.9 cm; the visor assembly (A19730040001) 35.6 x 30.5 x
36.8 cm; the gold visor (A20050453000) 23.2 x 28.9 x 20.6 cm. The LEVA's 35.6 cm height and 36.8 depth include its
thermal cover's drape over the suit's shoulders: a creature has no suit, so the cover here ends at the neck ring and
the prop stays rigid and clear of the body [E: the design's one simplification]. Proportions of the window and the
brow from the JSC display photo (front) and the Apollo 11 helmet on its table (three-quarter) [M-eye].
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc
from . import soft_common as SC

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})

NAME = 'space_helmet'

SPEC = dict(
    # ---- the PRESSURE BUBBLE (its outer surface): an ellipsoid about (0, yc, 0), cut by the neck ring
    bub=(0.140, 0.160, 0.135),      # semi-axes x, y, z [C: 30.5 wide less its bonded flange, 27.9 deep; the height
    #                                 TALLER than the bubble's 26 cm (yc + by = 0.288): the LEVA seen from the front
    #                                 stands about as tall as it is wide over the visor's lower edge (the JSC photo; the
    #                                 NASM 35.6 x 30.5); the first clay at 0.268 read squat beside both photos]
    yc=0.128,                       # its centre over the ring's lower face
    bub_t=0.0025,                   # blow-moulded polycarbonate [E: 2 - 3 mm]
    # ---- the NECK RING (anodized aluminium): a lathe; its section, (r, y) from the inside's foot round the outside
    ring=((0.1105, 0.0285), (0.1105, 0.0), (0.1235, 0.0), (0.1262, 0.0030), (0.1262, 0.0175), (0.1302, 0.0200),
          (0.1302, 0.0255), (0.1272, 0.0290), (0.1105, 0.0285)),   # [E: a 22 cm opening that passes a head; the
    #                                                                 bayonet lip proud 4 mm; closed over its top]
    # ---- the HOOD (the LEVA's thermal cover over its shell): the mid-surface, the wall
    hood_gap=0.012,                 # the mid-surface outside the bubble's [E: the shell and the cover]
    hood_t=0.006,
    hood_k=0.030,                   # the smooth max's reach where the brow and the cheeks meet the dome
    hem_y=0.034,                    # the cover's lower edge round the back, over the ring's lip
    hem_r=0.0055,
    # ---- the GOLD VISOR: a sphere about (0, yc, vis_z) [C: 23.2 x 28.9 x 20.6 cm: its chord 28.9 at +-74 deg]
    vis_R=0.150,
    vis_z=0.035,
    vis_t=0.0025,
    vis_off=0.014,                  # the hood's mid-surface this far outside the visor round the window: the cheeks and
    #                                 the brow stand proud of the visor (the JSC photo's thick white frame)
    vis_a=62.0,                     # its half-width (degrees about its own centre: under the rim and the cover beyond)
    vis_y=(0.046, 0.262),           # its lower edge (free: the bubble shows under it) and its top (under the brow)
    vis_lift=0.040,                 # its lower edge RISES toward the sides by this much at vis_a (as the square of the
    #                                 angle): the JSC photo's visor is rounded at its lower corners, not cut straight
    # ---- the WINDOW in the hood: an arch from the hem up [M-eye: the JSC front view, the visor 0.85 of the cover's
    #      width, its height 0.73 of its width; the first clay's +-56 deg read as a wraparound windscreen]
    win_a=45.0,                     # its sides on the columns at +-45 deg (4 of the 32)
    win_top=0.236,
    win_round=0.036,                # the top corners' radius along the rim's path
    rim_r=0.0125,                   # the rolled edge (the table photo: a fat roll of the cover round the visor)
    # ---- the CENTRAL EYESHADE, up over the brow (the JSC front view: a white shell above the visor, as wide as it)
    shade_w=0.100,                  # its half-width
    shade_s=(0.252, -0.045),        # from its front edge's height over the window to its back edge's z on the crown
    shade_h=0.0065,                 # proud of the cover
    shade_t=0.0030,
    # ---- the visor's PIVOT HUBS at the temples
    hub_a=92.0,
    hub_y=0.122,
    hub_r=0.021,
    hub_h=0.0075,
    # ---- the SEAL (11-12): black rubber round the visor, and what closes the cover: a BEAD in the slot between the
    #      rolled rim and the visor (the window's sides and top), an APRON on the visor's sphere from its lower edge
    #      down to the sill, the LEDGE from the apron's foot out to the sill, and the PLATE under the cover from the
    #      hem in to the ring. Before it the helmet was open shells: from three-quarter views the far visor's inner
    #      face showed through the slot (white stairs of 1.6 mm texels), from below the cheeks were see-through
    seal_u=0.006,                   # the bead's face this far inside the window's boundary (under the rim's overhang)
    seal_r=0.0032,                  # the bead's radius (the high: a sweep)
    seal_v=-0.0104,                 # its centre under the hood's mid-surface: between the rim's roll and the visor
    apron_a=58.0,                   # the apron's half-width about the visor's centre (past the bead's foot)
    apron_t=0.0018,                 # its thickness: its outer face 0.65 mm behind the visor's
    apron_y=0.0310,                 # its foot: in the ledge
    floor_t=0.0030,                 # the ledge (its top) and the plate (its underside): one sheet from the ring's top
    floor_r=0.1270,                 # .. (its inner edge, under the chamfer of the ring's lip) out to the hem's centreline
    floor_a=112.5,                  # round to where the cover's hem comes in onto the ring (the hood's column 10)
)

K = 32                              # the hood's columns: column k at a = 2 pi k / K (k = 0 the front's middle)
ROWS_WIN = (0.034, 0.060, 0.086, 0.112, 0.138, 0.164, 0.190, 0.214, 0.236)      # the hem .. the window's top
ROWS_TOP = (0.256, 0.274)           # full rings over the window; the cap above the last
N_CAP = 8                           # the cap: a 9 x 9 grid (8 x 8 quads), its 32 boundary vertices the last ring's
RIM_SIDES = 8
HEM_SIDES = 6
VIS_COLS, VIS_ROWS = 16, 8
RING_K = 32
CAV_K, CAV_ROWS = 16, 5
HUB_SIDES = 8
REGIONS = ('hood', 'rim', 'hem', 'shade', 'visor', 'visor_in', 'bubble', 'cavity', 'ring', 'hub', 'seal')
#           (11-12: 'visor_in' and 'bubble' are no longer drawn: the seal closes every view of them; their numbers stay)
ZONES = ('cover', 'visor', 'ring', 'trim')       # masks B = 0, 1/3, 2/3, 1: the runtime's four palette zones
SHARES = dict(hood=1.0, rim=1.0, hem=1.0, shade=1.0, hub=1.0, ring=1.0, visor=0.35, visor_edge=0.5, cavity=0.15,
              seal_wall=0.6, seal_apron=0.6, seal_ledge=0.4, seal_plate=0.25)
UV_ORDER = ['hood_side', 'hem', 'hood_back', 'rim', 'shade', 'hood_cap', 'visor', 'hood_front', 'shade_wall',
            'seal_apron', 'ring', 'hub_wall', 'hub', 'seal_wall', 'cavity', 'seal_ledge', 'rim_cap', 'seal_plate',
            'cavity_cap', 'visor_edge']
UV_PPM = 4084.4959474774632         # the recorded placing order and density (11-12 11:16, on the CLOSED low: 'random
#                                     2' of the search; 20 primary islands of 47, the sheet 78.7 % covered, gutters
#                                     10.3 px, the largest empty rectangle 0.8 %): a re-placement in seconds. (11-11's
#                                     record for the open low: 4,208 px/m, 80.2 %; out/uv_v1_before_the_seal.json)
PX_MM = 0.43                        # a pixel at the closest view (the 0.4 m portrait at 1080 lines)


# ----------------------------------------------------------------------------------------------------- helpers
def _smax(a, b, k):
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.maximum(a, b) + h * h * k * 0.25


def _unit(v):
    return SC.unit(v)


def hood_f(P, spec=SPEC):
    """the hood's MID-surface as the zero set of a smooth UNION of two solids: the ellipsoid hood_gap outside the bubble
    and the sphere vis_off outside the visor (the brow and the cheeks round the window). (The first version took a
    smooth MAX of two radial functions: where both vanish over the crown it left k/4 = 7.5 mm: a spike up the axis)"""
    P = np.asarray(P, np.float64)
    bx, by, bz = spec['bub']
    g = spec['hood_gap']
    R = np.array([bx + g, by + g, bz + g])
    q = (P - np.array([0.0, spec['yc'], 0.0])) / R
    fe = (np.linalg.norm(q, axis=-1) - 1.0) * R.min()
    fs = np.linalg.norm(P - np.array([0.0, spec['yc'], spec['vis_z']]), axis=-1) - (spec['vis_R'] + spec['vis_off'])
    k = spec['hood_k']
    h = np.maximum(k - np.abs(fe - fs), 0.0) / k
    return np.minimum(fe, fs) - h * h * k * 0.25


def hood_r(a, y, spec=SPEC, iters=44):
    """the hood's MID-surface: its horizontal distance from the axis at plan azimuth a (radians) and height y (0 over
    the crown): bisection on hood_f along the horizontal ray"""
    a, y = np.asarray(a, np.float64), np.asarray(y, np.float64)
    sh = np.broadcast(a, y).shape
    a, y = np.broadcast_to(a, sh), np.broadcast_to(y, sh)
    d = np.stack([np.sin(a), np.zeros(sh), np.cos(a)], -1)
    base = np.stack([np.zeros(sh), y, np.zeros(sh)], -1)
    lo, hi = np.zeros(sh), np.full(sh, 0.32)
    for _ in range(iters):
        m = 0.5 * (lo + hi)
        inside = hood_f(base + m[..., None] * d, spec) < 0.0
        lo, hi = np.where(inside, m, lo), np.where(inside, hi, m)
    r = 0.5 * (lo + hi)
    return np.where(hood_f(base, spec) < 0.0, r, 0.0)


def hood_point(a, y, spec=SPEC):
    """the hood's MID-surface at (a, y)"""
    r = hood_r(a, y, spec)
    a = np.asarray(a, np.float64)
    return np.stack([r * np.sin(a), np.broadcast_to(y, np.shape(r)), r * np.cos(a)], -1)


def hood_outer(a, y, spec=SPEC):
    """the hood's OUTER face at (a, y): the mid-surface + half the wall along its normal (where the low's cover
    lies: the first low on the mid-surface stood 3.0 mm inside the high's face)"""
    return hood_point(a, y, spec) + 0.5 * spec['hood_t'] * hood_normal(a, y, spec)


def hood_normal(a, y, spec=SPEC, e=2e-5):
    """the mid-surface's outward normal at (a, y): the gradient of hood_f there (central differences; the (a, y)
    parameters degenerate at the crown)"""
    return hood_grad(hood_point(a, y, spec), spec, e)


def hood_grad(P, spec=SPEC, e=2e-5):
    P = np.asarray(P, np.float64)
    g = np.stack([hood_f(P + e * np.eye(3)[k], spec) - hood_f(P - e * np.eye(3)[k], spec) for k in range(3)], -1)
    return _unit(g)


def hood_height(x, z, spec=SPEC, y0=0.20, iters=48):
    """the height of the hood's top surface over the plan point (x, z) (the cap: bisection on r(a, y) = |(x, z)|,
    r falling with y over the dome's top)"""
    x, z = np.asarray(x, np.float64), np.asarray(z, np.float64)
    lo = np.full_like(x, y0)
    hi = np.full_like(x, spec['yc'] + spec['bub'][1] + spec['hood_gap'] + 0.03)
    for _ in range(iters):
        m = 0.5 * (lo + hi)
        inside = hood_f(np.stack([x, m, z], -1), spec) < 0.0
        lo = np.where(inside, m, lo)
        hi = np.where(inside, hi, m)
    return 0.5 * (lo + hi)


def visor_point(al, y, spec=SPEC, off=0.0):
    """the gold visor's outer surface (off: along its normal) at the azimuth al about its own centre and height y"""
    al, y = np.asarray(al, np.float64), np.asarray(y, np.float64)
    sh = np.broadcast(al, y).shape
    al, y = np.broadcast_to(al, sh), np.broadcast_to(y, sh)
    R = spec['vis_R'] + off
    s = np.sqrt(np.maximum(R * R - (y - spec['yc']) ** 2, 0.0))
    return np.stack([s * np.sin(al), y, spec['vis_z'] + s * np.cos(al)], -1)


def bubble_point(a, y, spec=SPEC, off=0.0):
    """the bubble's outer surface (off < 0: inward) at plan azimuth a and height y"""
    bx, by, bz = (b + off for b in spec['bub'])
    a, y = np.asarray(a, np.float64), np.asarray(y, np.float64)
    sh = np.broadcast(a, y).shape
    a, y = np.broadcast_to(a, sh), np.broadcast_to(y, sh)
    t = np.clip((y - spec['yc']) / by, -1.0, 1.0)
    q = np.sqrt(np.maximum(1.0 - t * t, 0.0))
    r = 1.0 / np.sqrt((np.sin(a) / (bx * q + 1e-12)) ** 2 + (np.cos(a) / (bz * q + 1e-12)) ** 2)
    return np.stack([r * np.sin(a), y, r * np.cos(a)], -1)


def col_a(k):
    return 2.0 * np.pi * np.asarray(k, np.float64) / K


def in_window(k, spec=SPEC):
    """the hood's column k lies inside the window's span (strictly between its side columns)"""
    kk = ((np.asarray(k) + K // 2) % K) - K // 2
    return np.abs(kk) < round(spec['win_a'] / (360.0 / K))


# ------------------------------------------------------------------------------------------------- the low's parts
def _orient_part(V, Q, uvc, desired):
    """each quad turned (its corners and their UVs reversed) where its normal points against `desired` (per quad)"""
    Q = np.array(Q, np.int64).copy()
    uvc = np.array(uvc, np.float64).copy()
    n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    flip = (n * desired).sum(-1) < 0.0
    Q[flip] = Q[flip][:, ::-1]
    uvc[flip] = uvc[flip][:, ::-1]
    return Q, uvc, int(flip.sum())


def _quads_grid(nr, nc, wrap=False):
    """quad ids of an (nr, nc) vertex grid, row-major; wrap: the columns close"""
    Q = []
    cols = nc if wrap else nc - 1
    for i in range(nr - 1):
        for j in range(cols):
            j1 = (j + 1) % nc
            Q.append([i * nc + j, i * nc + j1, (i + 1) * nc + j1, (i + 1) * nc + j])
    return np.array(Q, np.int64)


def _corner_uv(V, Q, island_quads):
    """per-corner island UVs (metres) for the quads listed: hard_hat._flatten on those quads (LSCM then ARAP)"""
    from .hard_hat import _flatten
    uvm, info = _flatten(V, Q[island_quads])
    return np.array([[uvm[int(v)] for v in Q[f]] for f in island_quads]), info


def _mirror_part(name, region, V, Q, island, uvc, attr, smooth=True):
    """a part from its +X half: the half (primary) and its mirror in x (stacked: the same corner UVs, the winding
    reversed); island: per quad names of the half's islands (the mirror's get '_m')"""
    Vm = V * np.array([-1.0, 1.0, 1.0])
    n = len(V)
    Qm = Q[:, ::-1] + n
    uvm = uvc[:, ::-1]
    am = attr.copy()
    am[:, 0] = -am[:, 0]
    return dict(name=name, region=region, V=np.vstack([V, Vm]), Q=np.vstack([Q, Qm]),
                uv=np.concatenate([uvc, uvm]), island=list(island) + [f'{nm}_m' for nm in island],
                primary=np.concatenate([np.ones(len(Q), bool), np.zeros(len(Q), bool)]),
                attr=np.vstack([attr, am]), smooth=smooth)


def _islands_uv(V, Q, names):
    """per-corner UVs for every island named in `names` (per quad), each flattened on its own"""
    uvc = np.zeros((len(Q), 4, 2))
    rep = {}
    for nm in dict.fromkeys(names):
        sel = np.array([i for i, x in enumerate(names) if x == nm])
        uvc[sel], rep[nm] = _corner_uv(V, Q, sel)
    return uvc, rep


def window_corner(spec=SPEC):
    """the window's top corner on its LEFT (+X) side: the low's corner vertex pulled in along the diagonal onto the
    rim path's round (win_round): (a, y)"""
    a0, y0 = np.radians(spec['win_a']), spec['win_top']
    r = hood_r(a0, y0, spec)
    da = spec['win_round'] * (1.0 - np.sqrt(0.5)) / r
    dy = spec['win_round'] * (1.0 - np.sqrt(0.5))
    return a0 - da, y0 - dy


def hood_half(spec=SPEC):
    """the hood's +X half (columns 0 .. K/2, the front's middle to the back's): rows ROWS_WIN + ROWS_TOP over the
    columns, the window's cells left out, then the cap's half; the window's top corner pulled onto its round.
    Returns V, Q, island names per quad, attr (a, y, 0, 0)"""
    rows = list(ROWS_WIN) + list(ROWS_TOP)
    ncol = K // 2 + 1                                   # columns 0 .. 16 (a = 0 .. pi)
    kw = round(spec['win_a'] / (360.0 / K))             # the window's side column (5)
    A = col_a(np.arange(ncol))
    V = np.zeros((len(rows), ncol, 3))
    att = np.zeros((len(rows), ncol, 4))
    for i, y in enumerate(rows):
        V[i] = hood_point(A, np.full(ncol, y), spec)
        att[i, :, 0], att[i, :, 1] = A, y
    # the window's top corner (row win_top, column kw) onto the round
    iw = rows.index(spec['win_top'])
    ac, yc_ = window_corner(spec)
    V[iw, kw] = hood_point(ac, yc_, spec)
    att[iw, kw, :2] = ac, yc_
    Vf = V.reshape(-1, 3)
    attf = att.reshape(-1, 4)
    Q, names = [], []
    for i in range(len(rows) - 1):
        for j in range(ncol - 1):
            if rows[i] < spec['win_top'] and j < kw:
                continue                                # the window
            q = [i * ncol + j, (i + 1) * ncol + j, (i + 1) * ncol + j + 1, i * ncol + j + 1]
            Q.append(q)
            a_mid = 0.5 * (A[j] + A[j + 1])
            names.append('hood_front' if j < kw else ('hood_side' if a_mid < np.radians(123.75) else 'hood_back'))
    # the cap's half: a 9 x 9 grid whose boundary is the last ring (32 columns) and whose middle column lies on x = 0
    nV = len(Vf)
    Vc, Qc, attc, bnd = cap_half(spec, Vf[(len(rows) - 1) * ncol:(len(rows)) * ncol])
    # boundary ids of the cap's vertices map to the last ring's vertices
    ids = np.arange(len(Vc)) + nV
    for ci, rk in bnd.items():
        ids[ci] = (len(rows) - 1) * ncol + rk
    keep = np.ones(len(Vc), bool)
    keep[list(bnd)] = False
    new_ids = -np.ones(len(Vc), np.int64)
    new_ids[keep] = nV + np.arange(int(keep.sum()))
    new_ids[~keep] = ids[~keep]
    Vf = np.vstack([Vf, Vc[keep]])
    attf = np.vstack([attf, attc[keep]])
    for q in Qc:
        Q.append([int(new_ids[v]) for v in q])
        names.append('hood_cap')
    Q = SC.orient(np.array(Q, np.int64), Vf, centre=np.array([0.0, spec['yc'], 0.0]))
    # every vertex onto the OUTER face (the mid-surface's points pushed out by half the wall along hood_f's gradient)
    Vf = Vf + 0.5 * spec['hood_t'] * hood_grad(Vf, spec)
    return Vf, Q, names, attf


def cap_half(spec, ring):
    """the cap's +X half: the grid (N_CAP + 1)^2 over the square [-1, 1]^2 (u along x, v along z), its boundary on
    the ring's vertices (columns 0 .. 16 of the half: the square's perimeter from (0, +1) through (+1, *) to (0, -1)),
    its inside by a Coons patch in plan, faired, lifted onto the hood. Returns V (the half grid: columns u >= 0),
    Q, attr and {grid vertex: ring column} for the boundary"""
    n = N_CAP
    h = n // 2
    # the perimeter of the full square in grid coordinates (i along u: 0..n, j along v: 0..n), walking the ring's
    # columns 0 .. K-1 from the front (v = n, u = h) toward +X (u increasing)
    per = []
    i, j = h, n
    for _ in range(K):
        per.append((i, j))
        if j == n and i < n:
            i += 1
        elif i == n and j > 0:
            j -= 1
        elif j == 0 and i > 0:
            i -= 1
        else:
            j += 1
    plan = {}
    full_ring = np.vstack([ring, ring[1:-1][::-1] * np.array([-1.0, 1.0, 1.0])])     # columns 0 .. 31
    for k, (i_, j_) in enumerate(per):
        plan[(i_, j_)] = full_ring[k][[0, 2]]
    G = np.zeros((n + 1, n + 1, 2))
    fixed = np.zeros((n + 1, n + 1), bool)
    for (i_, j_), p in plan.items():
        G[i_, j_] = p
        fixed[i_, j_] = True
    # Coons patch from the four sides
    for i_ in range(1, n):
        for j_ in range(1, n):
            s, t = i_ / n, j_ / n
            L = (1 - s) * G[0, j_] + s * G[n, j_]
            Bt = (1 - t) * G[i_, 0] + t * G[i_, n]
            C = ((1 - s) * (1 - t) * G[0, 0] + s * (1 - t) * G[n, 0] + (1 - s) * t * G[0, n] + s * t * G[n, n])
            G[i_, j_] = L + Bt - C
    for _ in range(40):                                  # fairing in plan, the boundary held
        Gn = G.copy()
        Gn[1:-1, 1:-1] = 0.25 * (G[2:, 1:-1] + G[:-2, 1:-1] + G[1:-1, 2:] + G[1:-1, :-2])
        G = np.where(fixed[..., None], G, Gn)
    G[h, :, 0] = 0.0                                     # the middle column on x = 0 exactly
    # the +X half: columns i = h .. n
    sub = G[h:, :]
    nu, nv = sub.shape[:2]
    X, Z = sub[..., 0], sub[..., 1]
    Y = hood_height(X, Z, spec)
    V = np.stack([X, Y, Z], -1).reshape(-1, 3)
    for (i_, j_), p in plan.items():                    # the boundary keeps the ring's own heights
        if i_ >= h:
            V[(i_ - h) * nv + j_] = np.array([p[0], ring[0, 1], p[1]])
    att = np.zeros((len(V), 4))
    att[:, 0] = np.arctan2(V[:, 0], V[:, 2])
    att[:, 1] = V[:, 1]
    Q = []
    for i_ in range(nu - 1):
        for j_ in range(nv - 1):
            Q.append([i_ * nv + j_, i_ * nv + j_ + 1, (i_ + 1) * nv + j_ + 1, (i_ + 1) * nv + j_])
    bnd = {}
    for k, (i_, j_) in enumerate(per):
        if i_ >= h and k <= K // 2:
            bnd[(i_ - h) * nv + j_] = k
    # the boundary's y from the ring (exact ids are mapped by the caller)
    return V, np.array(Q, np.int64), att, bnd


def rim_path(spec=SPEC, n_round=4):
    """the window's boundary on the hood's +X half as the rim's centreline stations: up the side from the hem (column
    kw, the rows), round the corner, across the top (the row win_top, columns kw-1 .. 0). Returns the boundary's
    (a, y) per station"""
    kw = round(spec['win_a'] / (360.0 / K))
    a0, y0 = col_a(kw), spec['win_top']
    Rc = spec['win_round']
    r0 = float(hood_r(a0, y0, spec))
    # the side's rows below the round, the round (a quarter circle of radius win_round in the cover's own metres:
    # from the side at y0 - Rc to the top at a0 - Rc / r0), the top's columns past it
    st = [(a0, y) for y in ROWS_WIN if y < y0 - Rc - 1e-9]
    for ph in np.linspace(0.0, 0.5 * np.pi, n_round + 1):
        st.append((a0 - (Rc - Rc * np.cos(ph)) / r0, y0 - Rc + Rc * np.sin(ph)))
    st += [(col_a(j), y0) for j in range(kw - 1, -1, -1) if col_a(j) < a0 - Rc / r0 - 1e-9]
    return np.array(st)


def rim_frames(spec=SPEC, full=False):
    """the rim's path on the hood with its frames: st (a, y), P0 on the mid-surface, Nn the cover's normal, Bn along
    the cover INTO the window. full: the whole window (-X foot .. the top's middle .. +X foot), else the +X half (foot
    .. middle). The rim (low and high) and the seal's bead (low and high) all stand on these"""
    st = rim_path(spec)
    if full:
        st = np.vstack([st * np.array([-1.0, 1.0]), st[::-1][1:]])
    P0 = hood_point(st[:, 0], st[:, 1], spec)
    toward = hood_point(st[:, 0] * 0.0, np.full(len(st), 0.13), spec) - P0
    Nn, Bn = _frames_on_hood(st[:, 0], st[:, 1], P0, spec, _unit(toward))
    return st, P0, Nn, Bn


def window_top(a, spec=SPEC):
    """the height of the window's upper boundary at the plan azimuth a: its top row, then the corner's round"""
    a = np.abs(np.asarray(a, np.float64))
    a0, y0, Rc = np.radians(spec['win_a']), spec['win_top'], spec['win_round']
    r0 = float(hood_r(a0, y0, spec))
    u = np.clip((a - (a0 - Rc / r0)) * r0, 0.0, Rc)
    return y0 - Rc + np.sqrt(np.maximum(Rc * Rc - u * u, 0.0))


def _mid_radius(sides):
    """a tube's low is drawn BETWEEN the inscribed and the circumscribed polygon: its vertices this factor outside
    the true radius and its faces' middles as far inside (drawn inscribed, the rim's 8 sides stood 0.95 mm inside the
    high at their middles and its outline 0.95 mm thin)"""
    return 0.5 * (1.0 + 1.0 / np.cos(np.pi / sides))


def hem_centre(a, spec=SPEC):
    """the hem's centreline at the plan azimuth a (all round: across the front it is the window's sill)"""
    a = np.asarray(a, np.float64)
    y = np.full(a.shape, spec['hem_y'])
    # 1 mm down: round the back the hem then sits IN the ring's top (as drawn first its six-sided low kissed the ring:
    # 12 see-through pixels from behind and below, and a ragged dark line in the bake)
    return hood_point(a, y, spec) + hood_normal(a, y, spec) * (0.25 * spec['hem_r']) - np.array([0.0, 0.001, 0.0])


def floor_mid(a, tau, spec=SPEC):
    """the closure sheet's mid-surface at the plan azimuth a: from the ring's top (tau 0) out to the hem's centreline
    (tau 1). a and tau: arrays of one shape"""
    a, tau = np.asarray(a, np.float64), np.asarray(tau, np.float64)
    inner = np.stack([spec['floor_r'] * np.sin(a), np.full(a.shape, 0.0290), spec['floor_r'] * np.cos(a)], -1)
    return inner + (hem_centre(a, spec) - inner) * tau[..., None]


def _face(Q, V, desired):
    """the quads turned to face `desired` (per quad, or one direction)"""
    Q = np.array(Q, np.int64).copy()
    n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    flip = (n * desired).sum(-1) < 0.0
    Q[flip] = Q[flip][:, ::-1]
    return Q


def seal_half(spec=SPEC, cols=8):
    """THE SEAL's +X half (see SPEC): the bead's face, the apron, the ledge, the plate. Returns V, Q, island names per
    quad, attr. Every edge of it ends INSIDE a neighbour (the rim's roll, the visor's shell, the sill, the ring), so no
    view finds a slit"""
    up = np.array([0.0, 1.0, 0.0])
    c = np.array([0.0, spec['yc'], spec['vis_z']])
    ht = 0.5 * spec['floor_t']
    Vs, Qs, names = [], [], []

    def add(V, Q, name):
        base = sum(len(v) for v in Vs)
        Vs.append(V)
        Qs.append(np.asarray(Q, np.int64) + base)
        names.extend([name] * len(Q))

    # ---- the bead's face: per rim station from inside the roll (3.5 mm under the cover's mid-surface) down into the
    #      visor's shell (0.8 mm under its mid radius, along the cover's normal), seal_u inside the boundary
    st, P0, Nn, Bn = rim_frames(spec)
    X0 = P0 + Bn * spec['seal_u']
    top = X0 - Nn * 0.0035
    Rw = spec['vis_R'] - 0.0008
    d = X0 - c
    b = (d * Nn).sum(-1)
    s = b - np.sqrt(np.maximum(b * b - ((d * d).sum(-1) - Rw * Rw), 0.0))
    bot = X0 - s[:, None] * Nn
    # .. and one station under the first: straight down into the ledge (the bead's foot behind the sill)
    y_f = 0.0320
    t_f = top[0] * np.array([1.0, 0.0, 1.0]) + up * y_f
    b_f = visor_point(np.arctan2(bot[0, 0], bot[0, 2] - spec['vis_z']), y_f, spec, -0.0008)
    top, bot = np.vstack([t_f[None], top]), np.vstack([b_f[None], bot])
    Bq = np.vstack([Bn[:1], Bn])
    n = len(top)
    V = np.vstack([top, bot])
    Q = np.array([[i, i + 1, n + i + 1, n + i] for i in range(n - 1)], np.int64)
    add(V, _face(Q, V, 0.5 * (Bq[:-1] + Bq[1:])), 'seal_wall')
    # ---- the apron: on the visor's sphere, its outer face 0.65 mm behind the visor's, from its foot in the ledge up
    #      to 2 mm behind the visor's lower edge
    AL = np.radians(np.linspace(0.0, spec['apron_a'], cols + 1))
    y_hi = visor_bottom(AL, spec) + 0.002
    t = np.array([0.0, 0.5, 1.0])[:, None]
    Y = spec['apron_y'] + (y_hi[None, :] - spec['apron_y']) * t
    V = visor_point(np.broadcast_to(AL[None, :], Y.shape), Y, spec, 0.5 * spec['apron_t'] - 0.0003).reshape(-1, 3)
    Q = _quads_grid(3, cols + 1)
    add(V, _face(Q, V, V[Q].mean(1) - c), 'seal_apron')
    # ---- the ledge: the sheet's top from the sill's centreline in to 1 mm behind the apron's face, across the window
    kw = round(spec['win_a'] / (360.0 / K))
    A = col_a(np.arange(kw + 1))
    outer = floor_mid(A, np.ones(len(A)), spec) + up * ht
    lo, hi = np.zeros(len(A)), np.ones(len(A))
    for _ in range(40):
        m = 0.5 * (lo + hi)
        inside = np.linalg.norm(floor_mid(A, m, spec) + up * ht - c, axis=1) < spec['vis_R'] - 0.001
        lo, hi = np.where(inside, m, lo), np.where(inside, hi, m)
    inner = floor_mid(A, 0.5 * (lo + hi), spec) + up * ht
    V = np.vstack([outer, inner])
    Q = np.array([[j, j + 1, len(A) + j + 1, len(A) + j] for j in range(len(A) - 1)], np.int64)
    add(V, _face(Q, V, up), 'seal_ledge')
    # ---- the plate: the sheet's underside from the hem's centreline in to the ring's top, round to floor_a
    kf = round(spec['floor_a'] / (360.0 / K))
    A = col_a(np.arange(kf + 1))
    V = np.vstack([floor_mid(A, np.ones(len(A)), spec) - up * ht, floor_mid(A, np.zeros(len(A)), spec) - up * ht])
    Q = np.array([[j, j + 1, len(A) + j + 1, len(A) + j] for j in range(len(A) - 1)], np.int64)
    add(V, _face(Q, V, -up), 'seal_plate')
    V = np.vstack(Vs)
    V[np.abs(V[:, 0]) < 1e-9, 0] = 0.0
    attr = np.zeros((len(V), 4))
    attr[:, :3] = V
    return V, np.vstack(Qs), names, attr


def tube_part(name, region, P, Nn, Bn, radius, sides, island, t_range=(0.0, 2.0 * np.pi), attr3=0.0):
    """a tube round the centreline P (n, 3) with frames (Nn the out-of-surface normal, Bn the binormal); one ring of
    `sides` per station (closed round), quads between stations; island UVs: (arc length along, radius x angle)"""
    n = len(P)
    th = np.linspace(t_range[0], t_range[1], sides, endpoint=False)
    V = (P[:, None, :] + radius * (np.cos(th)[None, :, None] * Nn[:, None, :] + np.sin(th)[None, :, None] * Bn[:, None, :]))
    V = V.reshape(-1, 3)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    Q, uvc = [], []
    for i in range(n - 1):
        for j in range(sides):
            j1 = (j + 1) % sides
            Q.append([i * sides + j, (i + 1) * sides + j, (i + 1) * sides + j1, i * sides + j1])
            u0, u1 = s[i], s[i + 1]
            v0, v1 = radius * th[j], radius * (th[j] + 2.0 * np.pi / sides)
            uvc.append([[u0, v0], [u1, v0], [u1, v1], [u0, v1]])
    attr = np.zeros((len(V), 4))
    attr[:, 0] = np.repeat(s, sides)
    attr[:, 1] = np.tile(th, n)
    attr[:, 2] = attr3
    Q = np.array(Q, np.int64)
    # facing out of the tube: away from the centreline at each quad's station
    ii = np.arange(len(Q)) // sides
    desired = V[Q].mean(1) - 0.5 * (P[ii] + P[ii + 1])
    Q, uvc, _ = _orient_part(V, Q, np.array(uvc), desired)
    return Q, V, uvc, attr


def _frames_on_hood(A, Y, P, spec, inward_dir):
    """frames along a centreline lying on the hood: N the hood's outward normal at (a, y), B along the path x N
    (oriented by inward_dir: the tube's +B side faces into the window)"""
    Nn = hood_normal(A, Y, spec)
    T = np.gradient(P, axis=0)
    # (11-12) a centreline that meets the MIRROR PLANE crosses it square: the one-sided difference at the rim's last
    # station (the window's top middle) leaned its ring 6 degrees out of the plane (T = -1, 0, 0.1), and the mirror
    # half left a wedge-shaped CRACK there: a dark notch in every front view
    on = np.abs(P[:, 0]) < 1e-9
    T[on] = np.sign(T[on, 0:1] + 1e-30) * np.array([1.0, 0.0, 0.0])
    T = _unit(T)
    Bn = _unit(np.cross(T, Nn))
    # ONE orientation for the whole path (a frame flipped per station twists the tube's quads: 40 edges ran the same
    # way by both faces in the first rim): the middle station's B toward the window
    m = len(P) // 2
    d = np.asarray(inward_dir, np.float64)
    if (Bn[m] * (d[m] if d.ndim == 2 else d)).sum() < 0.0:
        Bn = -Bn
    return Nn, Bn


def build_low(spec=SPEC, log=print):
    """the AUTHORED low as soft_common parts (see the module's header). Returns (parts, info)"""
    parts, info = [], {}
    # ---- the hood
    V, Q, names, attr = hood_half(spec)
    uvc, rep = _islands_uv(V, Q, names)
    parts.append(_mirror_part('hood', 0, V, Q, names, uvc, attr))
    info['hood'] = dict(quads=2 * len(Q), islands={k: round(v['aniso'], 3) for k, v in rep.items()})
    # ---- the rim round the window: the boundary stations, the tube pulled a little into the window
    st, P0, Nn, Bn = rim_frames(spec)
    Pc = P0 + Nn * (0.35 * spec['rim_r']) + Bn * (0.25 * spec['rim_r'])
    # the lowest station: down to the hem's centre (into the hem tube)
    Pc[0] = Pc[0] + np.array([0.0, -0.4 * spec['rim_r'], 0.0])
    r_low = spec['rim_r'] * _mid_radius(RIM_SIDES)
    Qr, Vr, uvr, ar = tube_part('rim', 1, Pc, Nn, Bn, r_low, RIM_SIDES, 'rim')
    Vr[np.abs(Vr[:, 0]) < 1e-9, 0] = 0.0
    # (11-12) the roll's FOOT is closed: three quads over its first ring (from below the open tube showed the sky
    # through the roll: 5,466 of the 10,152 see-through pixels s03b_closed.py counted)
    assert RIM_SIDES == 8
    th = 2.0 * np.pi * np.arange(RIM_SIDES) / RIM_SIDES
    cuv = r_low * np.column_stack([np.cos(th), np.sin(th)])
    Qc = np.array([[0, 1, 2, 3], [0, 3, 4, 7], [7, 4, 5, 6]], np.int64)
    Qc = _face(Qc, Vr, Pc[0] - Pc[1])
    Qr = np.vstack([Qr, Qc])
    uvr = np.concatenate([uvr, cuv[Qc]])
    parts.append(_mirror_part('rim', 1, Vr, Qr, ['rim'] * (len(Qr) - 3) + ['rim_cap'] * 3, uvr, ar))
    # ---- the hem, ALL ROUND (+X half: the front's middle to the back's middle). (11-12) Across the front it is the
    #      window's SILL: the first hem ran round the back only and the window stood open from the neck ring up
    ah = col_a(np.arange(K // 2 + 1)).astype(np.float64)
    yh = np.full(len(ah), spec['hem_y'])
    Ph = hood_point(ah, yh, spec)
    Nh, Bh = _frames_on_hood(ah, yh, Ph, spec, np.array([0.0, -1.0, 0.0]))
    Pc = hem_centre(ah, spec)
    Qh, Vh, uvh, ahh = tube_part('hem', 2, Pc, Nh, Bh, spec['hem_r'] * _mid_radius(HEM_SIDES), HEM_SIDES, 'hem')
    Vh[np.abs(Vh[:, 0]) < 1e-9, 0] = 0.0
    parts.append(_mirror_part('hem', 2, Vh, Qh, ['hem'] * len(Qh), uvh, ahh))
    # ---- the central eyeshade (up)
    Vs, Qs, ns, attr_s = shade_half(spec)
    uvs, reps = _islands_uv(Vs, Qs, ns)
    parts.append(_mirror_part('shade', 3, Vs, Qs, ns, uvs, attr_s))
    # ---- the gold visor (outer) and its lower edge. (11-12: its inner face and the bubble's band under it are no
    #      longer drawn: the seal closes every view of them: 68 quads less)
    Vv, Qv, nv_, av = visor_half(spec)
    uvv, repv = _islands_uv(Vv, Qv, nv_)
    parts.append(_mirror_part('visor', 4, Vv, Qv, nv_, uvv, av))
    Ve, Qe, ne, ae = visor_edge_half(spec)
    uve, repe = _islands_uv(Ve, Qe, ne)
    parts.append(_mirror_part('visor_edge', 4, Ve, Qe, ne, uve, ae))
    # ---- the seal: the bead round the visor, the apron and the ledge under it, the plate under the cover
    Vz, Qz, nz, az = seal_half(spec)
    uvz, repz = _islands_uv(Vz, Qz, nz)
    parts.append(_mirror_part('seal', 10, Vz, Qz, nz, uvz, az))
    # ---- the cavity (the bubble's inner face, up through the ring): its quarters stacked
    parts.append(cavity_part(spec))
    # ---- the neck ring: one eighth, stacked eight times
    prof = np.array(spec['ring'], np.float64)
    parts.append(lathe_part('ring', 8, prof[:, 0], prof[:, 1], RING_K, 8, inward=False, cap=False, spec=spec))
    # ---- the hubs
    Vu, Qu, nu_, au = hub_half(spec)
    uvu, repu = _islands_uv(Vu, Qu, nu_)
    parts.append(_mirror_part('hub', 9, Vu, Qu, nu_, uvu, au))
    for p in parts:
        info.setdefault(p['name'], {})['quads'] = len(p['Q'])
    info['quads'] = int(sum(len(p['Q']) for p in parts))
    log(f'[space_helmet] low: {info["quads"]} quads ({2 * info["quads"]} tris): '
        + ', '.join(f'{p["name"]} {len(p["Q"])}' for p in parts))
    return parts, info


def shade_half(spec=SPEC, nx=3, ns=8):
    """the central eyeshade's +X half: its top face (offset shade_h + its half thickness over the hood) over x in
    [0, shade_w] and along the meridian from its front edge to its back edge, and its side and end walls down into the
    cover. Returns V, Q, names, attr"""
    y0, zb = spec['shade_s']
    # along: the meridian's directions from (0, yc, 0): from the front edge to the back edge. (11-12) THE FRONT EDGE
    # IS TUCKED INTO THE RIM'S ROLL on every column (shade_front): at y0 it stood 3.5 mm clear of the roll at the
    # middle and more toward the corners: a slot too narrow to bake or to light, ragged and dark in the engine
    yb = hood_height(np.array([0.0]), np.array([zb]), spec)[0]
    c0 = np.array([0.0, spec['yc'], 0.0])
    t1 = np.arctan2(yb - c0[1], zb)
    X = np.linspace(0.0, spec['shade_w'], nx + 1)
    Tg = np.array([np.linspace(shade_front(x / 0.16, spec), t1, ns + 1) for x in X]).T      # (ns + 1, nx + 1)
    off = spec['shade_h'] + 0.5 * spec['hood_t']           # proud of the cover's OUTER face by shade_h
    top = np.zeros((ns + 1, nx + 1, 3))
    foot = np.zeros((ns + 1, nx + 1, 3))
    for i in range(ns + 1):
        for j, x in enumerate(X):
            t = Tg[i, j]
            d = _unit(np.array([x / 0.16, np.sin(t), np.cos(t)]))
            P = _hood_ray(c0, d, spec)
            n = _hood_normal_at(P, spec)
            top[i, j] = P + n * off
            foot[i, j] = P - n * 0.001
    V = [top.reshape(-1, 3)]
    Q, names = [], []
    nc = nx + 1
    for i in range(ns):
        for j in range(nx):
            Q.append([i * nc + j, i * nc + j + 1, (i + 1) * nc + j + 1, (i + 1) * nc + j])
            names.append('shade')
    base = len(V[0])
    # the side wall (x = shade_w) and the back end down to their feet (the front end is inside the rim's roll: no wall)
    side_top = [i * nc + nx for i in range(ns + 1)]
    Vside = foot[:, nx]
    V.append(Vside)
    for i in range(ns):
        Q.append([side_top[i], base + i, base + i + 1, side_top[i + 1]])
        names.append('shade_wall')
    b3 = base + ns + 1
    V.append(foot[ns])
    for j in range(nx):
        Q.append([ns * nc + j, b3 + j, b3 + j + 1, ns * nc + j + 1])
        names.append('shade_wall')
    V = np.vstack(V)
    Q = np.array(Q, np.int64)
    Q = SC.orient(Q, V, centre=np.array([0.0, spec['yc'] - 0.05, 0.0]))
    attr = np.zeros((len(V), 4))
    attr[:, 0] = V[:, 0]
    attr[:, 1] = V[:, 1]
    return V, Q, names, attr


def shade_front(xn, spec=SPEC, tuck=0.0035):
    """the eyeshade's front edge on the column xn (= x / 0.16): the meridian angle t at which its ray meets the cover
    `tuck` above the window's upper boundary (its top row, lower round the corners): inside the rim's roll"""
    c0 = np.array([0.0, spec['yc'], 0.0])
    lo, hi = np.radians(15.0), np.radians(70.0)
    for _ in range(36):
        t = 0.5 * (lo + hi)
        P = _hood_ray(c0, _unit(np.array([abs(xn), np.sin(t), np.cos(t)])), spec)
        if P[1] < float(window_top(np.arctan2(P[0], P[2]), spec)) + tuck:
            lo = t
        else:
            hi = t
    return 0.5 * (lo + hi)


def _hood_ray(c0, d, spec, iters=48):
    """the hood's mid-surface along the ray c0 + t d (bisection on the inside test r(a, y) > horizontal distance)"""
    lo, hi = 0.0, 0.4
    for _ in range(iters):
        m = 0.5 * (lo + hi)
        inside = float(hood_f(c0 + m * d, spec)) < 0.0
        lo, hi = (m, hi) if inside else (lo, m)
    return c0 + 0.5 * (lo + hi) * d


def _hood_normal_at(P, spec):
    return hood_grad(np.asarray(P, np.float64)[None, :], spec)[0]


def visor_half(spec=SPEC, inner=False):
    """the visor's +X half on its sphere (outer face; inner=True: the inner face, coarser, facing in): columns of
    azimuth about its own centre 0 .. vis_a, rows of height over vis_y"""
    nc = VIS_COLS // 2 + 1 if not inner else VIS_COLS // 4 + 1
    nr = VIS_ROWS + 1 if not inner else VIS_ROWS // 2 + 1
    AL = np.radians(np.linspace(0.0, spec['vis_a'], nc))
    yb = visor_bottom(AL, spec)
    t = np.linspace(0.0, 1.0, nr)[:, None]
    Y = yb[None, :] + (spec['vis_y'][1] - yb[None, :]) * t
    off = 0.5 * spec['vis_t'] if not inner else -0.5 * spec['vis_t']
    V = visor_point(np.broadcast_to(AL[None, :], Y.shape), Y, spec, off).reshape(-1, 3)
    Q = _quads_grid(nr, nc)
    Q = Q[:, ::-1] if inner else Q
    c = np.array([0.0, spec['yc'], spec['vis_z']])
    Q = SC.orient(Q, V, centre=c) if not inner else SC.orient(Q, V, toward=np.array([0.0, 0.0, -1.0]))
    attr = np.zeros((len(V), 4))
    attr[:, 0] = np.tile(AL, nr)
    attr[:, 1] = Y.ravel()
    return V, Q, ['visor_in' if inner else 'visor'] * len(Q), attr


def visor_bottom(al, spec=SPEC):
    """the visor's lower edge's height at its azimuth al (radians): vis_y[0] in the middle, rising by vis_lift at
    vis_a as the square of the angle"""
    s = np.asarray(al, np.float64) / np.radians(spec['vis_a'])
    return spec['vis_y'][0] + spec['vis_lift'] * s * s


def visor_edge_half(spec=SPEC):
    """the visor's lower edge between its outer and inner faces (+X half), on the outer face's columns"""
    nc = VIS_COLS // 2 + 1
    AL = np.radians(np.linspace(0.0, spec['vis_a'], nc))
    y = visor_bottom(AL, spec)
    Vo = visor_point(AL, y, spec, 0.5 * spec['vis_t'])
    Vi = visor_point(AL, y, spec, -0.5 * spec['vis_t'])
    V = np.vstack([Vo, Vi])
    Q = np.array([[j, j + 1, nc + j + 1, nc + j] for j in range(nc - 1)], np.int64)
    Q = SC.orient(Q, V, toward=np.array([0.0, -1.0, 0.0]))
    attr = np.zeros((len(V), 4))
    attr[:, 0] = np.concatenate([AL, AL])
    attr[:, 1] = np.concatenate([y, y])
    return V, Q, ['visor_edge'] * len(Q), attr


def bubble_half(spec=SPEC, cols=6, ys=(0.0285, 0.046, 0.064, 0.082)):
    """the bubble's outer face where it shows under the visor's lower edge (+X half: plan azimuth 0 .. cols columns
    of the hood's 11.25 degrees)"""
    A = col_a(np.arange(cols + 1))
    Y = np.array(ys)
    V = bubble_point(A[None, :], Y[:, None], spec, 0.0).reshape(-1, 3)
    Q = _quads_grid(len(Y), len(A))
    Q = SC.orient(Q, V, centre=np.array([0.0, spec['yc'], 0.0]))
    attr = np.zeros((len(V), 4))
    attr[:, 0] = np.tile(A, len(Y))
    attr[:, 1] = np.repeat(Y, len(A))
    return V, Q, ['bubble'] * len(Q), attr


def cavity_part(spec=SPEC, ys=(0.0285, 0.075, 0.130, 0.185, 0.230, 0.262)):
    """the bubble's INNER face (elliptical in plan, as the bubble), CAV_K columns x the rows ys, then a grid cap on
    the ellipsoid's own top; facing the axis. Quarter 0 (columns 0 .. CAV_K / 4) is the primary island; the others
    take its corner UVs by column (the ellipse's quarters are mirror images: the stretch is the same)"""
    t = spec['bub_t']
    A = 2.0 * np.pi * np.arange(CAV_K) / CAV_K
    Y = np.array(ys)
    V = bubble_point(A[None, :], Y[:, None], spec, -t).reshape(-1, 3)
    # its foot row INSIDE the ring's wall (11-12): at the ring's inner radius its 16 sides cut 1.6 mm inside the ring's
    # 32, and from below a view passed up through those crescents behind the bubble's face
    rf = spec['ring'][0][0] + 0.003
    V[:CAV_K] = np.column_stack([rf * np.sin(A), np.full(CAV_K, ys[0] - 0.002), rf * np.cos(A)])
    Q = _quads_grid(len(Y), CAV_K, wrap=True)
    per = CAV_K // 4
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(V[::CAV_K], axis=0), axis=1))])
    rm = float(np.mean(np.linalg.norm(V[:, [0, 2]], axis=1)))
    uvc, isl, prim = [], [], []
    for qi in range(len(Q)):
        i, j = divmod(qi, CAV_K)
        jj = j % per
        u0, u1 = rm * 2.0 * np.pi * jj / CAV_K, rm * 2.0 * np.pi * (jj + 1) / CAV_K
        uvc.append([[u0, s[i]], [u1, s[i]], [u1, s[i + 1]], [u0, s[i + 1]]])
        isl.append('cavity' if j // per == 0 else f'cavity_{j // per}')
        prim.append(j // per == 0)
    uvc = np.array(uvc)
    # the cap on the top ring, its inside lifted onto the inner ellipsoid
    Vc, Qc, ucc, ic, pc = _lathe_cap(V[-CAV_K:], len(V) - CAV_K, CAV_K, 4, 'cavity', True, rm)
    bx, by, bz = (b - t for b in spec['bub'])
    q = (Vc[:, 0] / bx) ** 2 + (Vc[:, 2] / bz) ** 2
    Vc[:, 1] = spec['yc'] + by * np.sqrt(np.maximum(1.0 - q, 0.0))
    Vall = np.vstack([V, Vc])
    Qall = np.vstack([Q, Qc])
    uvc = np.concatenate([uvc, ucc])
    isl += ic
    prim += pc
    cen = Vall[Qall].mean(1)
    desired = np.array([0.0, spec['yc'], 0.0]) - cen               # toward the bubble's centre
    Qall, uvc, _ = _orient_part(Vall, Qall, uvc, desired)
    attr = np.zeros((len(Vall), 4))
    attr[:, 0] = np.arctan2(Vall[:, 0], Vall[:, 2])
    attr[:, 1] = Vall[:, 1]
    return dict(name='cavity', region=7, V=Vall, Q=Qall, uv=uvc, island=isl, primary=np.array(prim, bool), attr=attr,
                smooth=True)


def cavity_profile(spec=SPEC):
    """the bubble's inner face as a lathe profile (r at the azimuth 0 plane is the z semi-axis: the lathe here is
    round in plan at the mean of x and z, its rows' heights from the ring's foot to near the top)"""
    bx, by, bz = spec['bub']
    t = spec['bub_t']
    ys = np.array([0.0285, 0.070, 0.130, 0.190, 0.235, 0.258])
    yy = np.clip((ys - spec['yc']) / (by - t), -1.0, 1.0)
    r = 0.5 * (bx + bz - 2.0 * t) * np.sqrt(np.maximum(1.0 - yy * yy, 0.0))
    r[0] = spec['ring'][0][0]
    return r, ys


def lathe_part(name, region, r, y, k_cols, n_sect, inward=False, cap=False, spec=SPEC):
    """a lathe (plan-round) of the profile (r, y) with k_cols columns; the first 1 / n_sect of the turn is the PRIMARY
    island, the others stacked on it (the same corner UVs); cap: a grid cap closing the top (cavity)"""
    r, y = np.asarray(r, np.float64), np.asarray(y, np.float64)
    A = 2.0 * np.pi * np.arange(k_cols) / k_cols
    V = np.stack([r[:, None] * np.sin(A)[None, :], np.broadcast_to(y[:, None], (len(r), k_cols)),
                  r[:, None] * np.cos(A)[None, :]], -1).reshape(-1, 3)
    Q = _quads_grid(len(r), k_cols, wrap=True)
    per = k_cols // n_sect
    # island UVs: u = the arc at the profile's mean radius, v = the profile's arc length
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(r), np.diff(y)))])
    rm = float(np.mean(r))
    uvc, isl, prim = [], [], []
    for qi, q in enumerate(Q):
        i, j = divmod(qi, k_cols)
        jj = j % per
        u0, u1 = rm * 2.0 * np.pi * jj / k_cols, rm * 2.0 * np.pi * (jj + 1) / k_cols
        uvc.append([[u0, s[i]], [u1, s[i]], [u1, s[i + 1]], [u0, s[i + 1]]])
        sec = j // per
        isl.append(name if sec == 0 else f'{name}_{sec}')
        prim.append(sec == 0)
    Q = np.array(Q, np.int64)
    uvc = np.array(uvc)
    centre = np.array([0.0, float(np.mean(y)), 0.0])
    if inward:
        Q = Q[:, ::-1]
        uvc = uvc[:, ::-1]
    Vall, Qall = V, Q
    if cap:
        # a grid cap over the top ring (k_cols = 16: a 5 x 5 grid, boundary 16)
        Vc, Qc, ucc, ic, pc = _lathe_cap(V[-k_cols:], len(V) - k_cols, k_cols, n_sect, name, inward, rm)
        Vall = np.vstack([V, Vc])
        Qall = np.vstack([Q, Qc])
        uvc = np.concatenate([uvc, ucc])
        isl += ic
        prim += pc
    attr = np.zeros((len(Vall), 4))
    attr[:, 0] = np.arctan2(Vall[:, 0], Vall[:, 2])
    attr[:, 1] = Vall[:, 1]
    cen = Vall[Qall].mean(1)
    if inward:
        # the cavity faces the axis (seen from inside the bubble): toward (0, y, 0) at each quad's height
        Qall, uvc, _ = _orient_part(Vall, Qall, uvc, np.column_stack([-cen[:, 0], np.zeros(len(cen)), -cen[:, 2]])
                                    + np.array([0.0, -1.0, 0.0]) * (cen[:, 1:2] > 0.25))
    else:
        # a solid ring's faces point away from its section's centroid at their azimuth
        rc, yc0 = float(np.mean(r)), float(np.mean(y))
        aq = np.arctan2(cen[:, 0], cen[:, 2])
        sc = np.column_stack([rc * np.sin(aq), np.full(len(aq), yc0), rc * np.cos(aq)])
        Qall, uvc, _ = _orient_part(Vall, Qall, uvc, cen - sc)
    return dict(name=name, region=region, V=Vall, Q=Qall, uv=uvc, island=isl, primary=np.array(prim, bool), attr=attr,
                smooth=True)


def _lathe_cap(ring, ring0, k_cols, n_sect, name, inward, rm):
    """a (k/4 + 1)^2 grid capping a lathe's top ring of k columns (its boundary the ring's vertices); its quads are
    one island of their own, primary (a cavity's cap is dark and small)"""
    n = k_cols // 4
    per = []
    i, j = n // 2, n
    for _ in range(k_cols):
        per.append((i, j))
        if j == n and i < n:
            i += 1
        elif i == n and j > 0:
            j -= 1
        elif j == 0 and i > 0:
            i -= 1
        else:
            j += 1
    G = np.zeros((n + 1, n + 1, 3))
    fixed = np.zeros((n + 1, n + 1), bool)
    gid = -np.ones((n + 1, n + 1), np.int64)
    for k, (i_, j_) in enumerate(per):
        G[i_, j_] = ring[k]
        fixed[i_, j_] = True
        gid[i_, j_] = ring0 + k
    for _ in range(60):
        Gn = G.copy()
        Gn[1:-1, 1:-1] = 0.25 * (G[2:, 1:-1] + G[:-2, 1:-1] + G[1:-1, 2:] + G[1:-1, :-2])
        G = np.where(fixed[..., None], G, Gn)
    newV = []
    base = ring0 + k_cols
    for i_ in range(n + 1):
        for j_ in range(n + 1):
            if gid[i_, j_] < 0:
                gid[i_, j_] = base + len(newV)
                newV.append(G[i_, j_] + np.array([0.0, 0.006, 0.0]))
    Q, uvc = [], []
    for i_ in range(n):
        for j_ in range(n):
            q = [gid[i_, j_], gid[i_, j_ + 1], gid[i_ + 1, j_ + 1], gid[i_ + 1, j_]]
            Q.append(q)
            P = [G[i_, j_], G[i_, j_ + 1], G[i_ + 1, j_ + 1], G[i_ + 1, j_]]
            uvc.append([[p[0], p[2]] for p in P])
    Q = np.array(Q, np.int64)
    uvc = np.array(uvc)
    if not inward:
        Q = Q[:, ::-1]
        uvc = uvc[:, ::-1]
    return np.array(newV), Q, uvc, [f'{name}_cap'] * len(Q), [True] * len(Q)


def hub_half(spec=SPEC):
    """the +X hub: a drum on the cover at the temple, its axis the cover's normal there: its wall (HUB_SIDES quads,
    its foot 2 mm into the cover) and its face (a 3 x 3 grid whose 8 boundary vertices are the wall's top)"""
    a, y = np.radians(spec['hub_a']), spec['hub_y']
    P0 = hood_point(np.array([a]), np.array([y]), spec)[0]
    n = hood_normal(np.array([a]), np.array([y]), spec)[0]
    u = _unit(np.cross(n, np.array([0.0, 1.0, 0.0])))
    v = np.cross(n, u)
    th = 2.0 * np.pi * np.arange(HUB_SIDES) / HUB_SIDES       # on the face grid's 8 boundary directions exactly
    ring = np.cos(th)[:, None] * u + np.sin(th)[:, None] * v
    R = spec['hub_r']
    foot = P0 + n * (0.5 * spec['hood_t'] - 0.002) + R * ring
    top = P0 + n * (0.5 * spec['hood_t'] + spec['hub_h']) + R * ring
    V = np.vstack([foot, top])
    Q = [[j, (j + 1) % HUB_SIDES, HUB_SIDES + (j + 1) % HUB_SIDES, HUB_SIDES + j] for j in range(HUB_SIDES)]
    names = ['hub_wall'] * HUB_SIDES
    # the face: a 3 x 3 grid, its corners at the octagon's 4 diagonal vertices' neighbours
    sq = []
    for gy in range(3):
        for gx in range(3):
            sq.append((gx - 1, gy - 1))
    # boundary of the 3 x 3 grid walked round: 8 points matched to the 8 top vertices by angle
    bnd = [(1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (0, 1), (0, 0)]
    ang = [np.arctan2(by - 1, bx - 1) for bx, by in bnd]
    tops = np.arctan2(np.sin(th), np.cos(th))
    gid = {}
    for (bx, by), an in zip(bnd, ang):
        k = int(np.argmin(np.abs(np.angle(np.exp(1j * (tops - an))))))
        gid[(bx, by)] = HUB_SIDES + k
    centre_id = len(V)
    V = np.vstack([V, P0 + n * (0.5 * spec['hood_t'] + spec['hub_h'] + 0.0005)])
    gid[(1, 1)] = centre_id
    for gy in range(2):
        for gx in range(2):
            Q.append([gid[(gx, gy)], gid[(gx + 1, gy)], gid[(gx + 1, gy + 1)], gid[(gx, gy + 1)]])
            names.append('hub')
    Q = SC.orient(np.array(Q, np.int64), V, centre=P0 - n * 0.05)
    attr = np.zeros((len(V), 4))
    attr[:, :3] = V - P0
    return V, Q, names, attr


# --------------------------------------------------------------------------------------------- the low's arrays
def make_low(size=2048, spec=SPEC, log=print, order=None, ppm=None):
    """the low with its UVs as the export's arrays (CPU): parts -> assemble -> pack -> low_arrays"""
    parts, info = build_low(spec, log)
    low = SC.assemble(parts)
    shares = {}
    for nm in low['names']:
        base = SC.primary_name(nm, {k: 1 for k in low['names'] if not k.endswith('_m') and not k[-1].isdigit()}) \
            if (nm.endswith('_m') or nm[-1].isdigit()) else nm
        key = base if base in SHARES else base.split('_')[0]
        shares[nm] = SHARES.get(key, 1.0)
    if isinstance(order, str) and order == 'search':
        order, ppm = None, None             # the placing order SEARCHED again (s05_forge.py uv, after the low changes)
    else:
        order, ppm = (order if order is not None else UV_ORDER), (ppm if ppm is not None else UV_PPM)
    fill, place, p, od = SC.pack(low, shares, size=size, order=order, ppm=ppm, log=log)
    L = SC.low_arrays(low, place, p, size)
    log(f'[space_helmet] uv: {len(place)} primary islands of {len(low["names"])}; {p:.0f} px/m at {size} '
        f'({1000 / p:.3f} mm a texel), fill {fill * 100:.1f} %; order {od}')
    return L, low, info, dict(fill=fill, order=od, ppm=p)


# ==================================================================================================== THE HIGH
def _grid_tris(nr, nc, keep=None, wrap=False):
    """triangles of an (nr, nc) vertex grid (keep: (nr - 1, nc') bool per cell)"""
    T = []
    cols = nc if wrap else nc - 1
    for i in range(nr - 1):
        for j in range(cols):
            if keep is not None and not keep[i, j]:
                continue
            j1 = (j + 1) % nc
            a, b, c, d = i * nc + j, i * nc + j1, (i + 1) * nc + j1, (i + 1) * nc + j
            T += [[a, b, c], [a, c, d]]
    return np.array(T, np.int32)


def hood_patch(spec=SPEC, da=0.5, dy=0.0012):
    """the hood's mid-surface, dense, with the WINDOW cut as the low cuts it (the sides on +-win_a up to the round,
    the round, the top), from the hem to the crown"""
    y_top = float(hood_height(np.array([0.0]), np.array([0.0]), spec)[0])
    Y = np.arange(spec['hem_y'], y_top - 0.002, dy)
    A = np.radians(np.arange(-180.0, 180.0, da))
    V = hood_point(A[None, :], Y[:, None], spec).reshape(-1, 3)
    Am, Ym = np.meshgrid(0.5 * (A + np.roll(A, -1)), 0.5 * (Y[:-1] + Y[1:]))
    Am[:, -1] = np.pi
    keep = ~window_mask(Am, Ym, spec)
    T = _grid_tris(len(Y), len(A), keep, wrap=True)
    # the crown: a fan from the last row to the top point
    top = len(V)
    V = np.vstack([V, [[0.0, y_top, float(hood_r(0.0, y_top - 1e-4, spec) * 0.0)]]])
    n = len(A)
    last = (len(Y) - 1) * n
    T = np.vstack([T, [[last + j, last + (j + 1) % n, top] for j in range(n)]]).astype(np.int32)
    return V, T


def window_mask(a, y, spec=SPEC):
    """True inside the window (the cut): |a| under the side column, under the top, outside the top corners' round"""
    a, y = np.abs(np.asarray(a, np.float64)), np.asarray(y, np.float64)
    a0, y0, Rc = np.radians(spec['win_a']), spec['win_top'], spec['win_round']
    r0 = float(hood_r(a0, y0, spec))
    inside = (a < a0) & (y < y0)
    # the round: within Rc of the corner, outside the quarter circle centred (a0 - Rc / r0, y0 - Rc)
    ca, cy = a0 - Rc / r0, y0 - Rc
    corner = (a > ca) & (y > cy)
    dist = np.hypot((a - ca) * r0, y - cy)
    return inside & ~(corner & (dist > Rc))


def rim_centreline(spec=SPEC, n=400):
    """the rim's centreline over the whole window (the +X half's stations mirrored, resampled densely) and its frames:
    as build_low places it"""
    # (11-12) -X foot .. the top's middle .. +X foot (rim_frames). The first version stacked the halves in the wrong
    # order (the middle, down the -X side, then a JUMP to the +X foot): the high had a rim-thick bar straight across
    # the window's bottom, through the bubble's band, and no roll on the -X side's lowest span
    st, P0, Nn, Bn = rim_frames(spec, full=True)
    Pc = P0 + Nn * (0.35 * spec['rim_r']) + Bn * (0.25 * spec['rim_r'])
    Pc[0] += np.array([0.0, -0.4 * spec['rim_r'], 0.0])
    Pc[-1] += np.array([0.0, -0.4 * spec['rim_r'], 0.0])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pc, axis=0), axis=1))])
    t = np.linspace(0.0, s[-1], n)
    P = np.column_stack([np.interp(t, s, Pc[:, k]) for k in range(3)])
    Nd = _unit(np.column_stack([np.interp(t, s, Nn[:, k]) for k in range(3)]))
    return P, Nd


def hem_centreline(spec=SPEC, n=400):
    """the hem's centreline all round (closed: the first point again at the end)"""
    A = np.linspace(0.0, 2.0 * np.pi, n)
    return hem_centre(A, spec), hood_normal(A, np.full(n, spec['hem_y']), spec)


def seal_bead(spec=SPEC, n=500):
    """the seal's bead under the rim's roll, round the whole window: its dense centreline (its face seal_u inside the
    boundary, where the low's wall stands) and frame normals; its feet run straight down into the closure sheet"""
    st, P0, Nn, Bn = rim_frames(spec, full=True)
    C = P0 + Bn * (spec['seal_u'] - spec['seal_r']) + Nn * spec['seal_v']
    f0, f1 = C[0].copy(), C[-1].copy()
    f0[1], f1[1] = 0.0290, 0.0290
    C = np.vstack([f0[None], C, f1[None]])
    Nx = np.vstack([Nn[:1], Nn, Nn[-1:]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    t = np.linspace(0.0, s[-1], n)
    P = np.column_stack([np.interp(t, s, C[:, k]) for k in range(3)])
    return P, _unit(np.column_stack([np.interp(t, s, Nx[:, k]) for k in range(3)]))


def apron_patch(spec=SPEC, n_a=200, n_y=50):
    """the apron's mid-surface (dense): the visor's sphere 0.3 mm under its mid radius, from under the ledge up to 4 mm
    behind the visor's lower edge"""
    AL = np.radians(np.linspace(-(spec['apron_a'] + 1.0), spec['apron_a'] + 1.0, n_a))
    y_hi = visor_bottom(np.minimum(np.abs(AL), np.radians(spec['vis_a'])), spec) + 0.004
    t = np.linspace(0.0, 1.0, n_y)[:, None]
    Y = 0.0300 + (y_hi[None, :] - 0.0300) * t
    V = visor_point(np.broadcast_to(AL[None, :], Y.shape), Y, spec, -0.0003).reshape(-1, 3)
    return V, _grid_tris(n_y, n_a)


def floor_patch(spec=SPEC, n_a=180, n_t=10):
    """the closure sheet's mid-surface (dense): floor_mid over the azimuths +-(floor_a + 2 degrees)"""
    A = np.radians(np.linspace(-(spec['floor_a'] + 2.0), spec['floor_a'] + 2.0, n_a))
    Ag, Tg = np.meshgrid(A, np.linspace(0.0, 1.0, n_t))
    V = floor_mid(Ag.ravel(), Tg.ravel(), spec)
    return V, _grid_tris(n_t, n_a)


def shade_patch(spec=SPEC, nx=40, ns=60):
    """the eyeshade as a dense patch at half its height over the cover (a SHELL of half-thickness shade_h / 2 + 1 mm:
    from 1 mm into the cover to its top face); its front edge tucked into the rim's roll as the low's (shade_front)"""
    y0, zb = spec['shade_s']
    c0 = np.array([0.0, spec['yc'], 0.0])
    yb = hood_height(np.array([0.0]), np.array([zb]), spec)[0]
    t1 = np.arctan2(yb - c0[1], zb)
    X = np.linspace(-spec['shade_w'], spec['shade_w'], nx)
    t0 = np.array([shade_front(x / 0.16, spec) for x in X])
    Tg = t0[None, :] + (t1 - t0[None, :]) * np.linspace(0.0, 1.0, ns)[:, None]
    Xg = np.broadcast_to(X[None, :], Tg.shape)
    D = _unit(np.stack([Xg / 0.16, np.sin(Tg), np.cos(Tg)], -1)).reshape(-1, 3)
    # (13:15) the rays together (the first loop of 2,400 scalar bisections took minutes of CPU; on a full machine the
    # memcapped bake, at below-normal priority, got 3 s of it in 8 minutes)
    lo, hi = np.zeros(len(D)), np.full(len(D), 0.4)
    for _ in range(40):
        m = 0.5 * (lo + hi)
        inside = hood_f(c0 + m[:, None] * D, spec) < 0.0
        lo, hi = np.where(inside, m, lo), np.where(inside, hi, m)
    P = c0 + (0.5 * (lo + hi))[:, None] * D
    V = P + hood_grad(P, spec) * shade_centre(spec)
    return V, _grid_tris(ns, nx)


def shade_half_t(spec=SPEC):
    """the eyeshade's SHELL half-thickness in the high: from 1.6 mm inside the cover's mid-surface to its top face"""
    return 0.5 * (spec['shade_h'] + 0.5 * spec['hood_t']) + 0.0008


def shade_centre(spec=SPEC):
    """its SHELL's patch offset over the mid-surface: the top face exactly where the low's top lies"""
    return spec['shade_h'] + 0.5 * spec['hood_t'] - shade_half_t(spec)


def visor_patch(spec=SPEC, n_a=180, n_y=120):
    AL = np.radians(np.linspace(-spec['vis_a'], spec['vis_a'], n_a))
    # (11-12) the mid-surface ends half the visor's thickness ABOVE its lower edge: a shell rounds its boundary outward
    # by its half-thickness, and the round now bottoms where the low's edge strip lies (it stood 1.25 mm under it:
    # 11 % of the strip's texels found no surface)
    yb = visor_bottom(np.abs(AL), spec) + 0.5 * spec['vis_t']
    t = np.linspace(0.0, 1.0, n_y)[:, None]
    Y = yb[None, :] + (spec['vis_y'][1] - yb[None, :]) * t
    V = visor_point(np.broadcast_to(AL[None, :], Y.shape), Y, spec, 0.0).reshape(-1, 3)
    return V, _grid_tris(n_y, n_a)


def bubble_patch(spec=SPEC, n_a=240, dy=0.0015):
    """the bubble's mid-surface from the ring up over the top (a lathe of its ellipsoid; the top a fan)"""
    bx, by, bz = spec['bub']
    t = 0.5 * spec['bub_t']
    Y = np.arange(0.0285, spec['yc'] + by - t - 0.002, dy)
    A = np.linspace(0.0, 2.0 * np.pi, n_a, endpoint=False)
    V = bubble_point(A[None, :], Y[:, None], spec, -t).reshape(-1, 3)
    T = _grid_tris(len(Y), n_a, wrap=True)
    top = len(V)
    V = np.vstack([V, [[0.0, spec['yc'] + by - t, 0.0]]])
    last = (len(Y) - 1) * n_a
    T = np.vstack([T, [[last + j, last + (j + 1) % n_a, top] for j in range(n_a)]]).astype(np.int32)
    return V, T


def hub_frame(sign, spec=SPEC):
    a, y = sign * np.radians(spec['hub_a']), spec['hub_y']
    P0 = hood_point(np.array([a]), np.array([y]), spec)[0]
    n = hood_normal(np.array([a]), np.array([y]), spec)[0]
    return P0, n


def high_parts(spec=SPEC):
    """the high's dense patches and centrelines (CPU; s05_forge.py `prep` saves them so the ledger job only builds the
    voxels and bakes)"""
    Vh, Th = hood_patch(spec)
    Pr, Nr = rim_centreline(spec)
    Pm, Nm = hem_centreline(spec)
    Vs, Ts = shade_patch(spec)
    Vv, Tv = visor_patch(spec)
    Vb, Tb = bubble_patch(spec)
    Pz, Nz = seal_bead(spec)
    Va, Ta = apron_patch(spec)
    Vf, Tf = floor_patch(spec)
    return dict(Vh=Vh, Th=Th, Pr=Pr, Nr=Nr, Pm=Pm, Nm=Nm, Vs=Vs, Ts=Ts, Vv=Vv, Tv=Tv, Vb=Vb, Tb=Tb, Pz=Pz, Nz=Nz,
                Va=Va, Ta=Ta, Vf=Vf, Tf=Tf)


def build_sdf(spec=SPEC, parts=None):
    """the HIGH: the hood (a SHELL over its dense mid-surface, the window cut) with the rim and the hem (SWEEPs) and
    the eyeshade (a SHELL) blended onto it; the hubs (REVOLVEs on the cover's normal); the visor (a SHELL); the bubble
    (a SHELL over its whole ellipsoid: its band under the visor and its inside up through the ring); the ring (a
    REVOLVE). The texture tier (the cover's weave, its seams and folds, the ring's turning) is the material pass's.
    parts: high_parts' dict (saved), else built here"""
    from .. import sdf
    H = parts if parts is not None else high_parts(spec)
    prog = sdf.Program()
    prog.begin_group(op=sdf.UNION, k=0.0025)
    prog.shell(H['Vh'], H['Th'], 0.5 * spec['hood_t'], k=0.0, maxd=0.03, name='hood')
    prog.sweep(H['Pr'], H['Nr'], spec['rim_r'], name='rim')
    prog.sweep(H['Pm'], H['Nm'], spec['hem_r'], name='hem')
    prog.shell(H['Vs'], H['Ts'], shade_half_t(spec), k=0.0, maxd=0.03, name='shade')
    for sg in (1.0, -1.0):
        P0, n = hub_frame(sg, spec)
        # (14:5x) the hub's height is `hh`: named `H` it rebound the parts dict above and the visor's shell read a float
        # (sh_bake2 died on it at 13:43 in 36 s)
        R, hh = spec['hub_r'], spec['hub_h'] + 0.5 * spec['hood_t']
        prof = [(0.0, -0.003), (R, -0.003), (R, hh - 0.0015), (R - 0.0015, hh), (0.0, hh)]
        prog.revolve(prof, P0, n, name=f'hub_{"L" if sg > 0 else "R"}')
    prog.end_group()
    prog.shell(H['Vv'], H['Tv'], 0.5 * spec['vis_t'], k=0.0, maxd=0.03, name='visor')
    # the seal (hard unions: rubber against cloth and gold meets in a crisp line)
    prog.sweep(H['Pz'], H['Nz'], spec['seal_r'], name='seal_bead')
    prog.shell(H['Va'], H['Ta'], 0.5 * spec['apron_t'], k=0.0, maxd=0.03, name='seal_apron')
    prog.shell(H['Vf'], H['Tf'], 0.5 * spec['floor_t'], k=0.0, maxd=0.03, name='seal_floor')
    prog.shell(H['Vb'], H['Tb'], 0.5 * spec['bub_t'], k=0.0, maxd=0.03, name='bubble')
    prof = np.array(spec['ring'], np.float64)[:-1]
    prog.revolve(prof[:, [0, 1]], np.zeros(3), np.array([0.0, 1.0, 0.0]), name='ring')
    return prog


def bounds(spec=SPEC, pad=0.006):
    lo = np.array([-0.19, -0.002, -0.17]) - pad
    hi = np.array([0.19, 0.33, 0.20]) + pad
    return lo, hi


# =========================================================================================== THE MATERIAL PASS
MATERIAL = dict(
    seed=17,
    cover=(0.80, 0.79, 0.75),       # the Beta cloth's white (linear) [E: a white woven glass fibre, Teflon coated; the
    #                                 museum pieces read a warm white]
    gold=(0.98, 0.76, 0.33),        # the sun visor's gold film: gold's F0 (metal: base colour = F0)
    anod=(0.085, 0.20, 0.62),       # the ring's blue anodize (metal: the dye over aluminium) [E: Apollo 11's blue]
    alu=(0.91, 0.92, 0.92),         # bare aluminium: the hubs, the ring where the anodize is worn
    glass=(0.012, 0.013, 0.016),    # the clear bubble over the dark inside
    dust=(0.36, 0.34, 0.31),        # dust and grime held in the folds
    amber=(0.045, 0.032, 0.016),    # the visor's inner face (the film seen through its polycarbonate)
    rubber=(0.020, 0.020, 0.022),   # the seal's black rubber
    rubber_rough=0.62,
    cover_rough=0.62,
    gold_rough=0.035,
    anod_rough=0.30,
    alu_rough=0.34,
    glass_rough=0.035,
    weave=1.0,                      # the cover's weave relief (0: none)
    grime=1.0,
    smudge=1.0,                     # finger smudges on the visor and the bubble
    scuff=1.0,                      # wear on the ring's edges, scratches on the visor
    folds=1.0,                      # the cover's soft folds near its hem and round the hubs
)
VARIANTS = dict(                    # wear()'s palette per variant
    apollo11=dict(),                # as baked: the gold visor, the BLUE neck ring (Apollo 11 and 12)
    apollo15=dict(ring=0xb32420),   # the RED neck ring of the later suits (A7LB)
    silver=dict(visor=0xd8d8dc),    # a silver mirror visor
)


@wp.struct
class SSurf:
    h: float
    col: wp.vec3
    rough: float
    metal: float
    fuzz: float
    zone: float
    wear: wp.vec4


@wp.func
def _seam(d: float, width: float, along: float, pitch: float):
    """a stitched seam: a groove (negative height) of `width`, stitches every `pitch` along it: (height, line mask)"""
    g = proc.smoothstep(width, 0.0, wp.abs(d))
    st = proc.smoothstep(0.30, 0.10, wp.abs(along / pitch - wp.floor(along / pitch) - 0.5)) * \
        proc.smoothstep(0.7 * width, 0.25 * width, wp.abs(d))
    return wp.vec2(-0.00028 * g + 0.00012 * st, g)


@wp.func
def sh_surf(p: wp.vec3, nw: wp.vec3, reg: int, at: wp.vec4, conv: float, convm: float, ao: float, aol: float,
            texel: float, C: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32), seed: int, full: int):
    """the helmet's surface at the point p of the low's region reg (nw: the baked normal, world; at: the vertex
    attributes). full = 0: the height only"""
    o = SSurf()
    h = float(0.0)
    col = wp.vec3(0.5, 0.5, 0.5)
    rough = float(0.5)
    metal = float(0.0)
    fuzz = float(0.0)
    zone = float(0.0)
    w_grime = float(0.0)
    w_smudge = float(0.0)
    w_scuff = float(0.0)
    occl = wp.clamp(1.6 * (1.0 - ao) + 3.0 * wp.max(-aol, 0.0), 0.0, 1.0)
    if reg <= 3:
        # THE COVER: a fine twill of glass fibre (0.6 mm), soft folds near the hem and round the hubs, stitched seams
        # (the back's middle, two at the sides, the rim's and the hem's own stitch lines)
        tw = wp.sin(6.2831853 * (p[0] + p[1] + p[2]) / 0.0006) * wp.sin(6.2831853 * (p[0] - p[1] + 0.5 * p[2]) / 0.0006)
        h = S[5] * 0.000018 * tw * proc.smoothstep(2.0, 3.5, 0.0006 / texel)
        fold_w = proc.smoothstep(0.075, 0.034, p[1]) + 0.6 * proc.smoothstep(0.045, 0.015, wp.length(
            wp.vec3(wp.abs(p[0]) - 0.150, p[1] - 0.122, p[2] + 0.004)))
        fold = proc.fbm3(wp.vec3(p[0] / 0.022, p[1] / 0.008, p[2] / 0.022), 3, 2.0, 0.5, seed + 3)
        h = h + S[9] * 0.00045 * fold * (0.25 + 0.75 * wp.clamp(fold_w, 0.0, 1.0))
        seam_mask = float(0.0)
        if reg == 0:
            # the back's middle seam (x = 0 behind the crown) and the two side seams (a = +-118 deg)
            if p[2] < -0.02:
                # (11-12: named sm1; as `sm` it shared a name with the visor's FLOAT smudge below and warp refused the
                # function: "where() true value type (vec) must be of the same type as the false type (float32)")
                sm1 = _seam(p[0], 0.0011, p[1] - p[2], 0.0032)
                h = h + sm1[0]
                seam_mask = sm1[1]
            a = wp.atan2(wp.abs(p[0]), p[2])
            r = wp.sqrt(p[0] * p[0] + p[2] * p[2])
            sm2 = _seam((a - 2.06) * r, 0.0011, p[1], 0.0032)
            h = h + sm2[0]
            seam_mask = wp.max(seam_mask, sm2[1])
        elif reg == 1 or reg == 2:
            # the tube's own stitch line where it meets the cover (at[1]: the angle round the tube)
            sm3 = _seam((wp.abs(at[1] - 3.14159) - 1.15) * 0.010, 0.0010, at[0], 0.0030)
            h = h + sm3[0]
            seam_mask = sm3[1]
        if full == 1:
            g = S[6] * wp.clamp(0.55 * occl * occl + 0.35 * seam_mask + 0.25 * wp.max(fold, 0.0) *
                                wp.clamp(fold_w, 0.0, 1.0), 0.0, 1.0)
            g = g * (0.55 + 0.45 * proc.smoothstep(-0.3, 0.6, proc.fbm3(p / 0.03, 2, 2.0, 0.5, seed + 5)))
            w_grime = g
            tint = 1.0 + 0.035 * proc.fbm3(p / 0.05, 2, 2.0, 0.5, seed + 7)
            col = M.mix3(C[0] * tint, C[5], 0.45 * g)
            rough = S[0] + 0.06 * proc.noise3(p / 0.01, seed + 9) + 0.10 * g
            fuzz = 0.22
            zone = 0.0
    elif reg == 4:
        # THE GOLD VISOR: a polished film; finger smudges in patches, a few fine scratches
        sc = proc.smoothstep(0.62, 0.70, proc.noise3(wp.vec3(p[0] / 0.06, p[1] / 0.0004, p[2] / 0.06), seed + 11))
        h = -0.000004 * sc * S[8]
        if full == 1:
            sm = S[7] * proc.smoothstep(0.15, 0.55, proc.fbm3(p / 0.018, 3, 2.0, 0.5, seed + 13)) * \
                proc.smoothstep(0.0, 0.4, proc.noise3(p / 0.07, seed + 15))
            w_smudge = sm
            w_scuff = sc
            col = C[1] * (1.0 - 0.06 * sm)
            rough = S[1] + 0.13 * sm + 0.10 * sc
            metal = 1.0
            zone = 1.0 / 3.0
    elif reg == 5:
        if full == 1:
            col = C[6]
            rough = 0.06
            zone = 1.0 / 3.0
    elif reg == 6 or reg == 7:
        # the bubble (its outside under the visor; its inside up through the ring): dark glass
        if full == 1:
            sm = S[7] * proc.smoothstep(0.2, 0.6, proc.fbm3(p / 0.02, 3, 2.0, 0.5, seed + 17))
            w_smudge = sm
            col = C[4]
            rough = S[4] + 0.10 * sm
            if reg == 7:
                rough = 0.20
            zone = 1.0
    elif reg == 8:
        # THE NECK RING: anodized aluminium, turned (fine grooves round it), the anodize worn off its edges
        rr = wp.sqrt(p[0] * p[0] + p[2] * p[2])
        h = 0.000006 * wp.sin(6.2831853 * (p[1] + rr) / 0.00045) * proc.smoothstep(2.0, 3.5, 0.00045 / texel)
        if full == 1:
            # (11-12: 0.8 .. 2.2 and 0.85 wore the whole bayonet lip to bare metal: a chrome band with dark blotches
            # between the cover and the blue; now only its sharpest corners, as a thin bright line)
            edge = proc.smoothstep(1.2, 2.6, conv) * (0.4 + 0.6 * proc.smoothstep(-0.2, 0.5, proc.noise3(p / 0.004,
                                                                                                           seed + 19)))
            w_scuff = S[8] * edge
            col = M.mix3(C[2], C[3], 0.6 * w_scuff)
            rough = S[2] + 0.06 * proc.noise3(p / 0.006, seed + 21) - 0.06 * w_scuff
            metal = 1.0
            zone = 2.0 / 3.0
    elif reg == 10:
        # THE SEAL: black rubber (the bead round the visor, the apron and the ledge under it, the plate under the
        # cover): matte, a little pale dust where it is sheltered
        if full == 1:
            g = S[6] * wp.clamp(0.8 * occl, 0.0, 1.0) * (0.5 + 0.5 * proc.smoothstep(-0.3, 0.6, proc.fbm3(
                p / 0.012, 2, 2.0, 0.5, seed + 23)))
            w_grime = g
            col = M.mix3(C[7], C[5], 0.22 * g)
            rough = S[10] + 0.07 * proc.noise3(p / 0.004, seed + 25) + 0.10 * g
            zone = 1.0
    else:
        # THE HUBS: turned aluminium, a screw in the middle (at: the position from the hub's centre on the cover)
        rr = wp.length(wp.vec3(at[0], at[1], at[2]) - nw * wp.dot(wp.vec3(at[0], at[1], at[2]), nw))
        h = 0.000005 * wp.sin(6.2831853 * rr / 0.0005) * proc.smoothstep(2.0, 3.5, 0.0005 / texel)
        h = h - 0.0006 * proc.smoothstep(0.0042, 0.0036, rr)
        if full == 1:
            col = C[3]
            rough = S[3]
            metal = 1.0
            zone = 1.0
    o.h = h
    o.col = col
    o.rough = rough
    o.metal = metal
    o.fuzz = fuzz
    o.zone = zone
    o.wear = wp.vec4(w_grime, w_smudge, w_scuff, 0.0)
    return o


@wp.kernel
def k_helmet(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
             ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32),
             d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_base: wp.array(dtype=wp.vec4),
             d_aol: wp.array(dtype=wp.float32), d_conv: wp.array(dtype=wp.float32),
             d_convm: wp.array(dtype=wp.float32), C: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32),
             texel: float, seed: int, o_alb: wp.array(dtype=wp.vec3), o_nrm: wp.array(dtype=wp.vec3),
             o_orm: wp.array(dtype=wp.vec3), o_mask: wp.array(dtype=wp.vec4), o_wear: wp.array(dtype=wp.vec4),
             o_hit: wp.array(dtype=wp.int32)):
    """face_mask.k_mask's frame (the bake's normal carried, the texture tier's height differenced over the low, the
    roughness widened by the normals' spread inside the texel), with the helmet's surface function"""
    tid = wp.tid()
    x = tid % size
    y = tid // size
    dn = d_nrm[tid]
    if dn[3] <= 0.0:
        return
    tn_b = wp.normalize(wp.vec3(dn[0], dn[1], dn[2]))
    base = d_base[tid]
    inv = 1.0 / float(ss)
    dlt = 0.5 * inv
    acc_a = wp.vec3(0.0)
    acc_n = wp.vec3(0.0)
    acc_r = float(0.0)
    acc_m = float(0.0)
    acc_k = wp.vec4(0.0)
    acc_w = wp.vec4(0.0)
    hits = int(0)
    hb = float(0.0)
    have_hb = int(0)
    for i in range(ss):
        for j in range(ss):
            fx = float(x) + (float(i) + 0.5) * inv
            fy = float(y) + (float(j) + 0.5) * inv
            lo = M.low_at(uv_mesh, fx, fy, lpos, lnrm, ltan, lattr)
            if lo.ok == 0:
                continue
            if have_hb == 0:
                if base[3] > 0.5:
                    hb = wp.dot(wp.vec3(base[0], base[1], base[2]) - lo.p, lo.n)
                have_hb = 1
            lx = M.low_at(uv_mesh, fx + dlt, fy, lpos, lnrm, ltan, lattr)
            if lx.ok == 0:
                lx = M.low_at(uv_mesh, fx - dlt, fy, lpos, lnrm, ltan, lattr)
            ly = M.low_at(uv_mesh, fx, fy + dlt, lpos, lnrm, ltan, lattr)
            if ly.ok == 0:
                ly = M.low_at(uv_mesh, fx, fy - dlt, lpos, lnrm, ltan, lattr)
            reg = lreg[lo.face]
            pb0 = lo.p + lo.n * hb
            nw = M.to_world(lo, tn_b)
            sf = sh_surf(pb0, nw, reg, lo.attr, d_conv[tid], d_convm[tid], d_ao[tid], d_aol[tid], texel, C, S, seed, 1)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1:
                pbx = lx.p + lx.n * hb
                pby = ly.p + ly.n * hb
                hx = sh_surf(pbx, nw, reg, lx.attr, 0.0, 0.0, 1.0, 0.0, texel, C, S, seed, 0).h
                hy = sh_surf(pby, nw, reg, ly.attr, 0.0, 0.0, 1.0, 0.0, texel, C, S, seed, 0).h
                h0 = sh_surf(pb0, nw, reg, lo.attr, 0.0, 0.0, 1.0, 0.0, texel, C, S, seed, 0).h
                g = M.surface_grad(pb0, pbx, pby, h0, hx, hy)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            acc_a = acc_a + sf.col
            acc_r = acc_r + wp.clamp(sf.rough, 0.03, 1.0)
            acc_m = acc_m + sf.metal
            acc_k = acc_k + wp.vec4(sf.fuzz, 0.0, sf.zone, 0.0)
            acc_w = acc_w + sf.wear
            hits = hits + 1
    if hits == 0:
        return
    fh = float(hits)
    ln = wp.length(acc_n) / fh
    var = wp.clamp((1.0 - ln) / wp.max(ln, 1.0e-4), 0.0, 1.0)
    rr = acc_r / fh
    a = rr * rr
    rr = wp.sqrt(wp.sqrt(a * a + var))
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    o_orm[tid] = wp.vec3(d_ao[tid], wp.clamp(rr, 0.0, 1.0), wp.clamp(acc_m / fh, 0.0, 1.0))
    o_mask[tid] = acc_k / fh
    o_wear[tid] = acc_w / fh
    o_hit[tid] = 1


def material_tables(recipe=MATERIAL):
    C = np.array([recipe['cover'], recipe['gold'], recipe['anod'], recipe['alu'], recipe['glass'], recipe['dust'],
                  recipe['amber'], recipe['rubber']], np.float32)
    S = np.array([recipe['cover_rough'], recipe['gold_rough'], recipe['anod_rough'], recipe['alu_rough'],
                  recipe['glass_rough'], recipe['weave'], recipe['grime'], recipe['smudge'], recipe['scuff'],
                  recipe['folds'], recipe['rubber_rough']], np.float32)
    return C, S


def run_material(L, drivers, size, texel, ss=2, recipe=MATERIAL, log=print):
    """the material pass over the helmet's one texture set, on the PRIMARY triangles. Returns soft_common.finish_maps'
    dict (albedo, normal, orm with METALNESS in B, masks RGB (R fuzz, G 0, B zone), wear, palette_base)"""
    import time

    from .. import calib
    t0 = time.time()
    pr = np.asarray(L['primary'], bool)
    F = L['F'][pr]
    uvm = M.uv_bvh(F, L['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(L['V'], F, L['N'], L['TAN'], L['ATTR'])
    keep = {k: drivers[k] for k in ('normal', 'ao', 'curvature', 'base', 'mat') if k in drivers}
    Dv = M.driver_arrays({**keep, **calib.relief_drivers(keep, 1.0 / texel)})
    C, S = material_tables(recipe)
    n = size * size
    o_alb, o_nrm, o_orm = (wp.zeros(n, dtype=wp.vec3) for _ in range(3))
    o_mask, o_wear = wp.zeros(n, dtype=wp.vec4), wp.zeros(n, dtype=wp.vec4)
    o_hit = wp.zeros(n, dtype=wp.int32)
    wp.launch(k_helmet, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
                                       wp.array(np.asarray(L['region'], np.int32)[pr], dtype=wp.int32), Dv['normal'],
                                       Dv['ao'], Dv['base'], Dv['ao_local'], Dv['conv'], Dv['conv_mid'],
                                       wp.array(C, dtype=wp.vec3), wp.array(S, dtype=wp.float32), float(texel),
                                       int(recipe['seed']), o_alb, o_nrm, o_orm, o_mask, o_wear, o_hit])
    wp.synchronize()
    img = lambda a, k: np.asarray(a.numpy()).reshape(size, size, k)[::-1]
    cov = np.asarray(o_hit.numpy()).reshape(size, size)[::-1] > 0
    wear = img(o_wear, 4)
    maps = SC.finish_maps(img(o_alb, 3), img(o_nrm, 3), img(o_orm, 3), img(o_mask, 4), wear, cov, ZONES)
    wm = wear[cov]
    log(f'[space_helmet] material {size}^2 x ss {ss}: {time.time() - t0:.1f}s over {int(cov.sum())} texels '
        f'({cov.mean() * 100:.1f} % of the sheet); palette base (linear) '
        + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in maps['palette_base'].items())
        + '; wear, mean / p95: ' + ', '.join(f'{nm} {wm[:, i].mean():.3f} / {np.percentile(wm[:, i], 95):.3f}'
                                            for i, nm in enumerate(('grime', 'smudge', 'scuff'))))
    return maps


# ===================================================================================================== THE FIT
def fit_data(spec=SPEC, conform=None):
    """what the fit and the runtime need (prop space, metres). The runtime's wear() seats it by the HAT path (its seat
    and a validated pose: translation, ONE scale, tilt: accessories.js), so archetype 'hat'; `encloses` and `cavity`
    say what it is: a helmet that closes over the whole head (recipe.ACCESSORY_ENCLOSES), its neck ring round the
    head's base and the bubble's inner surface the head must clear (an ellipsoid). RIGID (the fit law)"""
    bx, by, bz = spec['bub']
    t = spec['bub_t']
    ri = spec['ring'][0][0]
    rnd = lambda v: round(float(v), 5)
    return dict(archetype='hat', kind='helmet', prop=NAME, rigid=True, encloses=True,
                seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0], left=[1.0, 0.0, 0.0]),
                opening=dict(rx=rnd(ri), rz=rnd(ri), y=0.0, note='the neck ring\'s inner circle on its lower face'),
                cavity=dict(kind='ellipsoid', centre=[0.0, rnd(spec['yc']), 0.0],
                            radii=[rnd(bx - t), rnd(by - t), rnd(bz - t)], floor_y=rnd(spec['ring'][0][1]),
                            note='the bubble\'s inner surface: everything of the head inside it with a clearance'),
                volume=dict(kind='cylinders', axis='+Y',
                            parts=[dict(name='helmet', y=[-0.002, 0.312], radius=0.200)]),
                variants={k: {z: f'#{c:06x}' for z, c in v.items()} for k, v in VARIANTS.items()},
                conform=conform or {})


# ========================================================================================== THE FORGE'S STAGES
def hidden_inside(prog, inset=0.0006):
    """exclude(points) for the bake: the low's points more than `inset` INSIDE the high's solid: the cover's edge under
    the rim and the hem, the rim's and the hem's ends inside each other, the eyeshade's and the hubs' feet in the cover,
    the bubble's band behind the visor and the cover (s05_forge.py sdf: those vertices stood 4 - 13 mm under the
    union's face, beyond the 5 mm cage). Hidden: kept out of the bake's miss bar and its gate"""
    def exclude(P):
        return np.asarray(prog.eval(np.asarray(P, np.float64))) < -inset
    return exclude


def forge_bake(out_dir, size=2048, voxel_size=0.00045, band=0.0015, ss=2, seed=7, spec=SPEC, order=None, ppm=None,
               log=print):
    """block-out -> low + UVs -> voxel high (GPU) -> the bake; writes low_space_helmet.npz and drivers_space_helmet.npz
    (the material pass reads them in a process of its own)"""
    import os
    import time

    from .. import bake, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    prep = os.path.join(out_dir, 'high_parts.npz')
    if os.path.exists(prep) and os.path.exists(os.path.join(out_dir, f'low_{NAME}.npz')):
        # (13:15) the CPU stages done beforehand by `s05_forge.py prep` at normal priority: the ledger job (memcapped,
        # below-normal) only builds the voxels and bakes
        z = np.load(os.path.join(out_dir, f'low_{NAME}.npz'))
        L = {k: z[k] for k in z.files}
        L['px_per_m'] = float(L['px_per_m'])
        L['size'] = int(L['size'])
        H = dict(np.load(prep))
        log(f'[space_helmet] the low and the high\'s parts from prep ({len(L["F"])} tris)')
    else:
        L, low, info, uvr = make_low(size, spec, log, order, ppm)
        np.savez_compressed(os.path.join(out_dir, f'low_{NAME}.npz'),
                            **{k: v for k, v in L.items() if isinstance(v, np.ndarray)}, px_per_m=L['px_per_m'],
                            size=L['size'], Q=low['Q'], quad_part=low['part'], quad_island=low['island'],
                            names=np.array(low['names']), parts=np.array(low['parts']))
        H = None
    prog = build_sdf(spec, H)
    f = np.abs(prog.eval(L['V']))
    log(f'[space_helmet] low on the block-out: |sdf| p50 {np.median(f) * 1e3:.2f} mm, p95 '
        f'{np.percentile(f, 95) * 1e3:.2f} mm, max {f.max() * 1e3:.2f} mm')
    lo, hi = bounds(spec)
    G = voxel.SparseSDF(prog, lo, hi, voxel=voxel_size, band=band, log=log)
    pr = L['primary']
    res = bake.bake(G, L['V'], L['F'][pr], L['UV'], L['N'], L['TAN'], L['region'][pr], size=size, ss=ss, cage=0.005,
                    ao_r=0.025, cav_r=0.002, n_thk=2, thk_max=0.01, seed=seed, log=log,
                    region_names=dict(enumerate(REGIONS)), exclude=hidden_inside(prog))
    keep = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
            if k != 'position' and isinstance(v, np.ndarray)}
    np.savez_compressed(os.path.join(out_dir, f'drivers_{NAME}.npz'), **keep)
    log(f'[space_helmet] the bake is saved (drivers_{NAME}.npz) after {time.time() - t0:.0f}s')
    return L


DELIVER_SIZE = 1024                 # the shipped set (soft_common.deliver_maps; hard_NOTES TECHNIQUES 11): set from the
#                                     packed density against the closest view's pixel (the log of the UV step)


def export(out_dir, L, maps, spec=SPEC, conform=None, deliver=DELIVER_SIZE):
    """soft_common.export_glb's layout (one mesh, one material: base, normal, ORM; the masks in KHR_materials_volume's
    thickness slot; the fit in the root node's and the file's extras), the maps DELIVERED by soft_common.deliver_maps,
    with the ALBEDO LOSSLESS (PNG): the red ring is the blue one through the palette, R x 5.3, and a JPEG's blocks
    would show (the hard hat's white: hard_NOTES)"""
    import os

    from .. import gltf
    if deliver:
        maps = SC.deliver_maps(maps, deliver)
    g = gltf.GLB()
    t_base = g.texture(maps['albedo'], fmt='png')
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='jpeg', quality=95)
    t_msk = g.texture(maps['masks'], fmt='png')
    fit = fit_data(spec, conform)
    tex = dict(size=int(maps['albedo'].shape[0]))
    if 'delivered' in maps:
        tex.update(master=maps['delivered']['master'])
    mat = g.material(NAME, base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='prop', prop=NAME, masks=t_msk,
        masks_channels='R fuzz / sheen amount (the cover), G 0, B palette zone (0 cover, 1/3 visor, 2/3 ring, 1 trim: '
                       'the seal, the hubs, the bubble\'s inside); RGB, no alpha',
        palette_zones=list(ZONES), palette_base=maps.get('palette_base', {}),
        palette_variants={k: {z: f'#{c:06x}' for z, c in v.items()} for k, v in VARIANTS.items()}))
    mesh = g.mesh(NAME, L['V'], L['N'], L['TAN'], L['UV'], [(L['F'], mat)])
    g.node(NAME, mesh=mesh, root=True, extras=dict(bestiary='prop', fit=fit))
    return g.save(os.path.join(out_dir, f'{NAME}.glb'),
                  extras=dict(bestiary=dict(prop=NAME, archetype='hat', kind='helmet', units='m', up='+Y',
                                            forward='+Z', left='+X', triangles=int(len(L['F'])), fit=fit,
                                            textures=tex)))
