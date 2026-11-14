"""THE FACE MASKS: the SMILE mask and the FROWN mask (ACCESSORIES B5, 11-11; work/bestiary/accessories_b5/
soft_NOTES.md), the old creator's `mask: 'smile' | 'frown'` ("circular emoji mask strapped over the face",
creature_builder.js:2396) built the forge way, at real size, as the two SHOGGOTH MEME MASKS made real (the brief: a
circular yellow smile face mask and a circular blue angry frown face mask, after the shoggoth meme's two face masks).

THE OBJECT (one mould, two faces): a slightly DOMED moulded disc 210 mm across, 2.2 mm thick, in gloss enamel; the
drawing's black outline is a black rubber EDGE TRIM pressed on the rim (what a moulded mask's cut edge wears); the
eyes are OPENINGS (a round punch drawn 5 mm: a stadium) backed by black mesh glued inside, so the wearer sees out and
the face shows two solid dark eyes; the mouth (and the frown's brows) are shallow DEBOSSED channels filled with gloss
black; a 20 mm woven ELASTIC strap is riveted at each side (a nickel dome rivet on the face, a washer inside).

  profile -> block-out SDF:  the shell and its edge trim as ONE closed (r, z) profile REVOLVED about +Z; the eye
                             openings SUBTRACTED (rounded boxes along +Z, their edges filleted); the mesh patches and
                             the strap as SHELLs; the rivets and washers REVOLVED about the shell's normal at the anchors
  -> the low:                lathe rings at the profile's own stations (48 columns), a reduced centre and a grid cap,
                             each eye a 16-gon whose spokes run to a 6 x 2 patch of the polar grid; the trim's bead in
                             three facets; every vertex on the block-out
  -> UV islands:             the FRONT one unique disc (the showpiece: its wear must not mirror); the trim's eight
                             45 degree arcs stacked on one, the inside's two halves on one, the four mesh caps, the
                             two rivets, the two washers, the strap's eight tiles and two faces each on one
  -> voxel high + bake       ONE bake for the mould (both faces share it)
  -> material pass:          the FACE is drawn here (DESIGNS: a signed-distance table of the ink per design), so a
                             new face is a new table, no new bake: the debossed channels as height, the enamel's
                             orange peel, chips by curvature, scuffs, grime by AO; rubber, raw laminate inside,
                             nylon mesh, nickel (metallic 1), woven elastic
  -> a static glb carrying its FIT data (the rim's contact circle, probes inside, the eyes, the strap's anchors)
     and the strap's shape per wearer as MORPH TARGETS (an elastic strap is the one part that is not rigid)

Frame (remix.js's item contract): metres, +Y up, +Z the mask's FRONT (the dome rises toward +Z), +X the wearer's left;
the origin the centre of the RIM PLANE (z = 0: where the edge trim's back touches a table).

SIZES and their sources (SPEC; [C] the kit's own catalog, [M] measured on the two drawings, [E] my estimate of a
real moulded mask):
  * radius 105 mm [C]: recipe.ACCESSORIES['mask_smile'].authored.radius (the old creator's crownR x 1.15);
  * the face (eyes, mouth, brows) [M]: soft/masks/scripts/s01, s02 (each feature's centre in units of the face's
    half-width; the two drawings share one outline and one pair of eyes); the eyes moved 0.03 up so each stands on a
    column line of the low (60 degrees from the top);
  * the dome 28 mm deep [E] ("slightly domed"; a 3D model of the shoggoth has it deeper, an ellipsoid 0.16 x 0.18 x 0.06),
    flatter at the centre (exponent 2.5); shell 2.2 mm [E: the Fibrosport fibreglass goalie mask's cut openings, CC0];
  * edge trim 7.5 x 5 mm, strap 20 x 1.2 mm, rivet head 9 mm, washer 13 mm [E: common hardware].
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc
from .. import sdf
from . import soft_common as SC

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})

SPEC = dict(
    R=0.105,                # the rim's outer radius (the trim's bead) [C]
    depth=0.028,            # the dome's rise at the centre over the shell's edge (outer face) [E]
    p=2.5,                  # the dome's profile exponent: z = depth (1 - (r / Rs)^p): flatter in the middle [E]
    shell_t=0.0022,         # the moulded shell [E]
    trim_w=0.0075,          # the edge trim: how far it laps onto each face, its wall thickness
    trim_t=0.0014,
    eye_u=0.45, eye_v=0.26,             # an eye's centre (face units: the enamel field's radius Rf = 1) [M, see top]
    eye_rx=0.110, eye_ry=0.136,         # its half-width and half-height: a stadium (a round punch drawn vertically)
    eye_fillet=0.0006,                  # the opening's rounded edges
    mesh_margin=0.005, mesh_t=0.0005,   # the black mesh patch glued inside: its lap round the opening, its thickness
    stroke=0.16,                        # the painted lines' width (face units) [M: 0.147 and 0.175 on the drawings]
    deboss=0.00045,                     # the channels' depth under the enamel [E]
    anchor_u=0.80, anchor_v=0.26,       # the strap's rivets: at the eyes' height, near the rim
    rivet_r=0.0045, rivet_h=0.0016,     # the rivet's dome head (front)
    washer_r=0.0065, washer_h=0.0008, tail_r=0.0026, tail_h=0.0010,     # inside: the washer and the set end
    strap_w=0.020, strap_t=0.0012,      # the elastic
    strap_tab=0.012, strap_run=0.006,   # the strap's end lies on the inside from tab inboard of the rivet to run
    #                                     outboard of it, then leaves the shell. (0.83 and 9 mm put the strap's
    #                                     corners 1.28 mm INSIDE the trim's inner lap where it turns: measured)
    strap_lift=0.00040,                 # the flat tab's centre line stands this far off the concave inner face (its
    #                                     edges, 10 mm out, were 0.15-0.20 mm inside the shell at a lift of 0.1 mm,
    #                                     and 0.05 mm inside at 0.25 where it leaves)
    strap_bend=0.005,                   # the bend where it turns back round the head
    head_a=0.076, head_c=0.096, head_z=-0.086,      # THE REST SHAPE's head: an oval 152 x 192 mm (a person's, at the
    #                                     strap's height), its centre 86 mm behind the rim plane: the strap as worn
    #                                     on the head the mask is authored for
)
K = 48                      # columns round the lathe (column k at phi = 2 pi k / K from +Y toward +X)
K_CAP = 24                  # the reduced centre ring
EYE_COL = 8                 # the left eye's column line (60 degrees): its patch spans columns EYE_COL - 3 .. + 3
RING_R = (0.172, None, None, None, 0.84, 0.94)      # the front's rings in face units (None: set by the eye patch)
EYE_BAND = 0.176            # the eye patch's rings stand this far (face units) inside and outside the eye's centre
RIVET_K = 12
N_STATION = 33              # the strap's stations (32 segments: 8 tiles of 4)
N_ARC = 20                  # of them, the segments round the back of the head
REGIONS = ('front', 'trim', 'back', 'eye_wall', 'mesh', 'rivet', 'washer', 'strap')
SHARES = dict(front=1.0, trim=1.0, back=0.5, eye_wall=1.0, mesh=1.0, rivet=1.4, washer=0.7, strap=0.8)
ZONES = ('face', 'inside', 'ink', 'strap')          # masks B = 0, 1/3, 2/3, 1 (the runtime's four palette zones). The
#                                                     chips' bare laminate and the hardware ride in 'inside' (beside
#                                                     'face': a chip's edge never blends through 'ink')
# the recorded placing order and density (soft_common.pack's search, 11-11 05:05: 75.2 % of one 2048 sheet, least
# gutter 9.4 px, no overlap; `k05_forge.py low` with both set to None searches again, 70 s)
UV_ORDER = ['front', 'back', 'trim', 'strap', 'mesh', 'eye_wall', 'rivet', 'washer']
UV_PPM = 8978.99342476786

# the two faces, in FACE UNITS (x right as the viewer sees it = the wearer's left, y up; the enamel field's radius 1)
DESIGNS = dict(
    smile=dict(
        name='smile_mask',
        face=(0.800, 0.530, 0.028),     # the kit's yellow (creature_builder.js 0xf2c930), a real enamel's level
        lines=[dict(kind='parabola', v0=-0.51, k=1.33, half=0.385)],        # v = v0 + k u^2, |u| <= half [M: s02]
    ),
    frown=dict(
        name='frown_mask',
        face=(0.128, 0.531, 0.800),     # her picture's blue (sRGB 111 / 212 / 254), a real enamel's level
        lines=[dict(kind='parabola', v0=-0.276, k=-1.92, half=0.43),        # [M: s01; her SDF port: -2.24]
               dict(kind='segment', a=(0.256, 0.458), b=(0.454, 0.656)),    # the brows, inner ends LOWER [M: s01]
               dict(kind='segment', a=(-0.256, 0.458), b=(-0.454, 0.656))],
    ),
)
MATERIAL = dict(
    ink=(0.012, 0.011, 0.010),          # gloss black enamel (the kit's 0x14100c is darker than any paint)
    laminate=(0.70, 0.68, 0.60),        # the bare moulding: off-white (inside, and under a chip)
    rubber=(0.022, 0.022, 0.024),
    mesh=(0.011, 0.011, 0.012),
    nickel=(0.66, 0.61, 0.53),
    zinc=(0.70, 0.71, 0.72),
    elastic=(0.017, 0.017, 0.019),
    dust=(0.105, 0.090, 0.072),
    enamel_rough=0.11, ink_rough=0.15, laminate_rough=0.56, rubber_rough=0.62, mesh_rough=0.78, nickel_rough=0.20,
    zinc_rough=0.36, elastic_rough=0.82,
    peel_amp=0.0000022,                 # the enamel's orange peel (2.8 mm), metres
    chip=1.0,                           # how readily the enamel chips on a convex edge (0: never; 0.55 chipped nothing)
    scuff=0.45,                         # fine scratches on the dome's crown, where it lies face down
    grime=0.60,                         # dust held in the corners (AO)
    haze=0.05,                          # the handled rim's dulling (roughness)
    table_n=1024,
    seed=47,
)


# ------------------------------------------------------------------------------------------------ the meridian
def dims(spec=SPEC, n=8001):
    """the dome's OUTER meridian as tables over its arc length s, and the derived sizes: Rs (the shell's edge
    radius, solved so that the trim's bead reaches R), S_e (the edge's arc length), s1 (where the trim's lip begins),
    Rf (the enamel field's radius there), z0 (the shift putting the bead's back on z = 0)"""
    t, ht = spec['shell_t'], spec['trim_t']
    rho = 0.5 * t + ht
    Rs = spec['R'] - rho
    for _ in range(4):
        slope = -spec['depth'] * spec['p'] / Rs                      # dz/dr at the edge
        nr = -slope / np.hypot(1.0, slope)                           # the outward normal's radial part there
        Rs = spec['R'] - rho + nr * 0.5 * t
    r = Rs * np.linspace(0.0, 1.0, n) ** 0.75                        # (denser toward the edge)
    r = np.linspace(0.0, Rs, n)
    z = spec['depth'] * (1.0 - (r / Rs) ** spec['p'])
    ds = np.hypot(np.diff(r), np.diff(z))
    s = np.concatenate([[0.0], np.cumsum(ds)])
    tr, tz = np.gradient(r, s), np.gradient(z, s)
    ln = np.hypot(tr, tz)
    tr, tz = tr / ln, tz / ln
    nr_, nz_ = -tz, tr                                               # the outward (front) normal
    S_e = float(s[-1])
    Ez = float(z[-1] - nz_[-1] * 0.5 * t)
    z0 = -(Ez - rho)
    s1 = S_e - spec['trim_w']
    Rf = float(np.interp(s1, s, r))
    return dict(Rs=float(Rs), S_e=S_e, s1=float(s1), Rf=Rf, z0=float(z0), rho=float(rho), s=s, r=r, z=z + z0,
                tr=tr, tz=tz, nr=nr_, nz=nz_)


def mer(d, s, h=0.0):
    """the point at arc length s (array) of the outer meridian, offset h along its outward normal: (r, z)"""
    s = np.asarray(s, np.float64)
    f = lambda a: np.interp(s, d['s'], a)
    return f(d['r']) + h * f(d['nr']), f(d['z']) + h * f(d['nz'])


def s_of_r(d, r):
    return np.interp(np.asarray(r, np.float64), d['r'], d['s'])


def inner_tables(d, spec=SPEC):
    """the INNER face as (r, z, s_in) tables (the outer meridian offset by the shell's thickness)"""
    ri, zi = mer(d, d['s'], -spec['shell_t'])
    si = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(ri), np.diff(zi)))])
    return ri, zi, si


def z_outer(d, r):
    return np.interp(np.asarray(r, np.float64), d['r'], d['z'])


def z_inner(d, r, spec=SPEC):
    ri, zi, _ = inner_tables(d, spec)
    return np.interp(np.asarray(r, np.float64), ri, zi)


def normal_outer(d, x, y):
    """the dome's unit outward normal at (x, y) (arrays)"""
    r = np.hypot(x, y)
    nr = np.interp(r, d['r'], d['nr'])
    nz = np.interp(r, d['r'], d['nz'])
    rr = np.maximum(r, 1e-12)
    return np.stack([nr * x / rr, nr * y / rr, nz], -1)


def body_profile(spec=SPEC, step=0.00025):
    """the shell and its edge trim as ONE closed (r, z) polygon for sdf.Program.revolve about +Z: the outer face from
    the axis to the trim's lip, the lip (a quarter round), the trim's front wall, its bead round the shell's edge,
    its back wall, the back lip, the inner face back to the axis"""
    d = dims(spec)
    t, ht, rho = spec['shell_t'], spec['trim_t'], d['rho']
    s1, Se = d['s1'], d['S_e']
    n = lambda a, b: max(2, int(np.ceil(abs(b - a) / step)) + 1)
    P = []
    s = np.linspace(0.0, s1, n(0.0, s1))
    P.append(np.column_stack(mer(d, s)))
    a = np.linspace(0.0, 0.5 * np.pi, 13)[1:]                        # the lip: h = ht sin a over s1 .. s1 + ht
    P.append(np.column_stack(mer(d, s1 + ht * (1.0 - np.cos(a)), ht * np.sin(a))))
    s = np.linspace(s1 + ht, Se, n(s1 + ht, Se))[1:]
    P.append(np.column_stack(mer(d, s, ht)))
    Er, Ez = mer(d, Se, -0.5 * t)                                    # the bead's centre: the shell edge's middle
    f = lambda arr: float(np.interp(Se, d['s'], arr))
    N, T = np.array([f(d['nr']), f(d['nz'])]), np.array([f(d['tr']), f(d['tz'])])
    a = np.linspace(0.0, np.pi, 41)[1:]
    P.append(np.array([Er, Ez]) + rho * (np.cos(a)[:, None] * N + np.sin(a)[:, None] * T))
    s = np.linspace(Se, s1 + ht, n(s1 + ht, Se))[1:]
    P.append(np.column_stack(mer(d, s, -(t + ht))))
    a = np.linspace(0.5 * np.pi, 0.0, 13)[1:]
    P.append(np.column_stack(mer(d, s1 + ht * (1.0 - np.cos(a)), -t - ht * np.sin(a))))
    s = np.linspace(s1, 0.0, n(0.0, s1))[1:]
    P.append(np.column_stack(mer(d, s, -t)))
    P = np.vstack(P)
    P[:, 0] = np.maximum(P[:, 0], 0.0)
    return P


# ---------------------------------------------------------------------------------------------------- the face
def stadium(spec=SPEC, grow=0.0, d=None):
    """an eye opening in metres: (centre x of the LEFT eye, centre y, corner radius, half straight), grown by `grow`"""
    d = d or dims(spec)
    Rf = d['Rf']
    return (spec['eye_u'] * Rf, spec['eye_v'] * Rf, spec['eye_rx'] * Rf + grow,
            (spec['eye_ry'] - spec['eye_rx']) * Rf)


def stadium_sd(x, y, rad, hs):
    """signed distance to a vertical stadium centred at the origin (radius rad, half straight hs)"""
    return np.hypot(x, np.maximum(np.abs(y) - hs, 0.0)) - rad


def stadium_ray(dx, dy, rad, hs):
    """where the ray from the stadium's centre along the unit direction (dx, dy) leaves it: its length"""
    dx, dy = np.asarray(dx, np.float64), np.asarray(dy, np.float64)
    t = np.full(dx.shape, np.inf)
    with np.errstate(divide='ignore', invalid='ignore'):
        ts = rad / np.abs(dx)                                        # the straight sides x = +-rad
        ok = np.abs(dy * ts) <= hs
        t = np.where(ok, ts, t)
        b = -np.abs(dy) * hs                                         # the caps: |p - (0, +-hs)| = rad
        tc = -b + np.sqrt(np.maximum(b * b - (hs * hs - rad * rad), 0.0))
        t = np.where(ok, t, tc)
    return t


def line_points(ln, n=96):
    if ln['kind'] == 'parabola':
        u = np.linspace(-ln['half'], ln['half'], n)
        return np.column_stack([u, ln['v0'] + ln['k'] * u * u])
    a, b = np.asarray(ln['a'], np.float64), np.asarray(ln['b'], np.float64)
    return a + (b - a) * np.linspace(0.0, 1.0, 2)[:, None]


def ink_sd(design, u, v, spec=SPEC, eyes=True):
    """the signed distance (face units, - inside the ink) to a design's dark features at (u, v) (arrays): the two
    eyes and every line as a round-ended stroke"""
    u, v = np.asarray(u, np.float64), np.asarray(v, np.float64)
    out = np.full(u.shape, 1.0e3)
    if eyes:
        for sx in (1.0, -1.0):
            out = np.minimum(out, stadium_sd(u - sx * spec['eye_u'], v - spec['eye_v'], spec['eye_rx'],
                                             spec['eye_ry'] - spec['eye_rx']))
    for ln in DESIGNS[design]['lines']:
        P = line_points(ln)
        best = np.full(u.shape, 1.0e3)
        for a, b in zip(P[:-1], P[1:]):
            e = b - a
            w = np.clip(((u - a[0]) * e[0] + (v - a[1]) * e[1]) / (e @ e), 0.0, 1.0)
            best = np.minimum(best, np.hypot(u - a[0] - w * e[0], v - a[1] - w * e[1]))
        out = np.minimum(out, best - 0.5 * spec['stroke'])
    return out


def ink_table(design, n=1024, spec=SPEC, eyes=True):
    """ink_sd on an n x n grid over [-1.05, 1.05]^2 (row j: v, column i: u): the material kernel's lookup"""
    g = np.linspace(-1.05, 1.05, n)
    U, V = np.meshgrid(g, g)
    return ink_sd(design, U, V, spec, eyes).astype(np.float32)


# ------------------------------------------------------------------------------------------------- the strap
def _ellipse(a, c, zc, n=256):
    th = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    return np.column_stack([a * np.cos(th), zc + c * np.sin(th)])


def _hull(P):
    """the convex hull of 2D points, counter-clockwise"""
    from scipy.spatial import ConvexHull
    return P[ConvexHull(P).vertices]


def _side_tangent(L, t0, rb, H):
    """the LEFT side's turn (x > 0, in the (x, z) plane): from the leave point L with direction t0, a clockwise arc of
    radius rb until its tangent line touches the convex polygon H (the head, on the path's right). Returns (arc
    points incl. both ends, the touched hull vertex's index)"""
    nin = np.array([t0[1], -t0[0]])                                  # toward the arc's centre (the right-hand side)
    c = L + rb * nin

    def at(al):
        ca, sa = np.cos(-al), np.sin(-al)                            # clockwise by al
        Rm = np.array([[ca, -sa], [sa, ca]])
        A = c + Rm @ (L - c)
        t = Rm @ t0
        nr = np.array([t[1], -t[0]])
        dist = (H - A) @ nr
        ahead = (H - A) @ t
        return A, t, dist, ahead
    lo, hi = 0.0, np.pi
    for _ in range(60):
        m = 0.5 * (lo + hi)
        _, _, dist, _ = at(m)
        if dist.min() > 0.0:
            lo = m
        else:
            hi = m
    al = lo
    A, t, dist, ahead = at(al)
    i = int(np.argmin(dist))
    arc = np.array([at(a_)[0] for a_ in np.linspace(0.0, al, 9)])
    return arc, i


def strap_pivot(spec=SPEC, d=None):
    """where the strap's centre line leaves the shell on the left side (x, y, z in the mask's frame): the point the
    band's plane turns about (strap_path's tilt)"""
    d = d or dims(spec)
    x, y = spec['anchor_u'] * d['Rf'] + spec['strap_run'], spec['anchor_v'] * d['Rf']
    n3 = normal_outer(d, np.array([x]), np.array([y]))[0]
    return np.array([x, y, float(z_inner(d, np.hypot(x, y), spec))]) - n3 * (0.5 * spec['strap_t'] + spec['strap_lift'])


def strap_path(spec=SPEC, hull=None, y=None, tabs=None, d=None, tilt=0.0):
    """the strap's centre line as STATIONS (N_STATION, 3) with its width directions W and outward normals O, from
    the left tab's inboard end, out along the inside of the shell, round the back of the head and in along the right
    tab. hull: the head's outline in the strap's plane, a convex polygon (m, 2) of (x, z) in the mask's frame (None:
    the rest shape's oval). The stations: 3 on each tab (its end, the rivet, where it leaves the shell), 3 on each
    bend, the two points where the strap meets the head, N_ARC - 1 between them.
    tilt (radians): the band's plane turned about the line through the two leave points (strap_pivot), its back
    LIFTED in the mask's frame: a mask leaned back by a pitch keeps a level strap with tilt = that pitch. The hull is
    then the head's outline in THAT plane: (x, zp), zp counted from the pivot's z along the plane's forward axis
    (0, -sin tilt, cos tilt); at tilt 0 it is the mask's own z"""
    d = d or dims(spec)
    Rf = d['Rf']
    ya = spec['anchor_v'] * Rf if y is None else y
    xa = spec['anchor_u'] * Rf
    off = 0.5 * spec['strap_t'] + spec['strap_lift']
    st, ct = float(np.sin(tilt)), float(np.cos(tilt))

    def tab_point(x):
        """the strap's centre on the inside of the shell at (x, ya): the inner face, off along its own normal"""
        n3 = normal_outer(d, np.array([x]), np.array([ya]))[0]
        p = np.array([x, ya, float(z_inner(d, np.hypot(x, ya), spec))]) - n3 * off
        return p, n3
    x_in, x_out = xa - spec['strap_tab'], xa + spec['strap_run']
    T3 = [tab_point(x) for x in (x_in, xa, x_out)]
    pL, nL = T3[2]
    p2 = tab_point(x_out - 0.001)[0]
    t0 = SC.unit(np.array([pL[0] - p2[0], pL[2] - p2[2]]))            # the tab's direction where it leaves (x, z)
    H = _hull(_ellipse(spec['head_a'] + off, spec['head_c'] + off, spec['head_z'])) if hull is None \
        else _hull(np.asarray(hull, np.float64))
    arcL, iL = _side_tangent(np.array([pL[0], pL[2]]), t0, spec['strap_bend'], H)
    Hm = H * np.array([-1.0, 1.0])
    arcR, iR = _side_tangent(np.array([pL[0], pL[2]]), t0, spec['strap_bend'], Hm[::-1])
    iR = len(H) - 1 - iR                                             # back to H's own index
    arcR = arcR * np.array([-1.0, 1.0])
    # the hull from the left contact round the BACK (clockwise seen with x right, z up: decreasing index on a
    # counter-clockwise hull) to the right contact
    idx = [iL]
    while idx[-1] != iR:
        idx.append((idx[-1] - 1) % len(H))
        assert len(idx) <= len(H) + 1
    back = H[idx]
    sb = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(back, axis=0), axis=1))])
    if sb[-1] < 1e-9:                                                 # a head narrower than a point: one contact
        mid = np.repeat(back[:1], N_ARC + 1, axis=0)
    else:
        g = np.linspace(0.0, sb[-1], N_ARC + 1)
        mid = np.column_stack([np.interp(g, sb, back[:, 0]), np.interp(g, sb, back[:, 1])])
    P2 = np.vstack([arcL[[3, 6, 8]], mid, arcR[[8, 6, 3]]])          # (x, zp): bends (3 each) + the back
    # the band's plane: through the leave points, turned by `tilt` about the line through them
    zL = float(pL[2])
    lift3 = lambda x, zp: np.column_stack([x, ya - (zp - zL) * st, zL + (zp - zL) * ct])
    mid3 = lift3(P2[:, 0], P2[:, 1])
    left = np.array([p for p, _ in T3])
    right = left[::-1] * np.array([-1.0, 1.0, 1.0])
    P = np.vstack([left, mid3, right])
    assert len(P) == N_STATION, len(P)
    # width directions: on the tabs +Y laid into the shell's tangent plane, then turning to the plane's own normal
    # over the bend
    Y0 = np.array([0.0, 1.0, 0.0])
    Yv = np.array([0.0, ct, st])
    W = np.tile(Yv, (len(P), 1))
    for j, (p, n3) in enumerate(T3):
        w = SC.unit(Y0 - n3 * (Y0 @ n3))
        W[j] = w
        W[len(P) - 1 - j] = w * np.array([-1.0, 1.0, 1.0]) * np.array([1.0, 1.0, 1.0])
        W[len(P) - 1 - j][0] = -w[0]
    # (the twist is spread over the bend's END and the free run to the head: over the bend alone, 8 degrees in 9 mm,
    # the low's quads folded off the band; begun at the bend's first station it swung the band's upper corner 0.13 mm
    # into the shell, which is still beside it there)
    for j, f in ((3, 1.0), (4, 0.7), (5, 0.4)):
        W[j] = SC.unit(f * W[2] + (1.0 - f) * Yv)
        W[len(P) - 1 - j] = SC.unit(f * W[len(P) - 3] + (1.0 - f) * Yv)
    Tn = SC.unit(np.gradient(P, axis=0))
    O = SC.unit(np.cross(W, Tn))
    c = lift3(np.array([0.0]), np.array([spec['head_z'] if hull is None else float(H[:, 1].mean())]))[0]
    # outward: away from the head on the back, and on the tabs the face that lies on the SHELL (+Z): the same face of
    # the band all the way (the first version named the wearer's side outward on the tabs: the band's four corners
    # swapped sides between the tab and the bend, a half twist in 2.3 mm)
    sgn = np.sign(np.einsum('ij,ij->i', O, P - c))
    sgn[:3] = np.sign(O[:3, 2])
    sgn[-3:] = np.sign(O[-3:, 2])
    O = O * np.where(sgn == 0, 1.0, sgn)[:, None]
    W = SC.unit(np.cross(Tn, O)) * np.sign(np.einsum('ij,ij->i', np.cross(Tn, O), W))[:, None]
    return P, W, O


def strap_dense(P, W, O, step=0.001):
    """the stations' polyline resampled every `step` (linear in P; W and O renormalised): the high's mid-surface"""
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    g = np.linspace(0.0, s[-1], int(np.ceil(s[-1] / step)) + 1)
    f = lambda A: np.column_stack([np.interp(g, s, A[:, k]) for k in range(3)])
    return f(P), SC.unit(f(W)), SC.unit(f(O))


def strap_verts(P, W, O, spec=SPEC):
    """the strap's low vertices per station: its four corners (outer + W, outer - W, inner - W, inner + W)"""
    hw, ht = 0.5 * spec['strap_w'], 0.5 * spec['strap_t']
    return np.stack([P + hw * W + ht * O, P - hw * W + ht * O, P - hw * W - ht * O, P + hw * W - ht * O], 1)


# ---------------------------------------------------------------------------------------------------- anchors
def anchors(spec=SPEC, d=None):
    """per side (left +x first): the rivet's point on the OUTER face, the shell's unit normal there"""
    d = d or dims(spec)
    out = []
    for sx in (1.0, -1.0):
        x, y = sx * spec['anchor_u'] * d['Rf'], spec['anchor_v'] * d['Rf']
        n = normal_outer(d, np.array([x]), np.array([y]))[0]
        out.append((np.array([x, y, float(z_outer(d, np.hypot(x, y)))]), n))
    return out


def rivet_height(r, spec=SPEC):
    a, h = spec['rivet_r'], spec['rivet_h']
    Rr = (a * a + h * h) / (2.0 * h)
    return np.sqrt(np.maximum(Rr * Rr - np.asarray(r, np.float64) ** 2, 0.0)) - (Rr - h)


def rivet_profile(spec=SPEC, n=24):
    """the dome head as a closed (r, y) polygon about its axis (y from the shell's face; a foot sunk 0.4 mm)"""
    r = np.linspace(0.0, spec['rivet_r'], n)
    return np.vstack([np.column_stack([r, rivet_height(r, spec)]), [[spec['rivet_r'], -0.0004], [0.0, -0.0004]]])


def washer_profile(spec=SPEC, n=12):
    """the washer and the rivet's set end as a closed (r, y) polygon (y from the washer's seat on the strap)"""
    wr, wh, tr, th = spec['washer_r'], spec['washer_h'], spec['tail_r'], spec['tail_h']
    a = np.linspace(0.0, 0.5 * np.pi, n)
    dome = np.column_stack([tr * np.sin(a), wh + th * np.cos(a)])            # the set end: a low dome
    return np.vstack([dome, [[wr - 0.0002, wh], [wr, wh - 0.0002], [wr, 0.0], [0.0, 0.0]]])


def washer_seat(spec=SPEC):
    """how far behind the OUTER face (along the shell's normal) the washer sits: through the shell, the lift and the
    strap, bitten 0.05 mm into the elastic"""
    return spec['shell_t'] + spec['strap_lift'] + spec['strap_t'] - 0.00005


def _frame(a):
    a = SC.unit(a)
    e1 = SC.unit(np.array([0.0, 1.0, 0.0]) - a * a[1])
    return e1, np.cross(a, e1)


# --------------------------------------------------------------------------------------------------- block-out
def build_sdf(spec=SPEC, strap=None):
    """the block-out: the REVOLVED shell and trim, the eye openings SUBTRACTED, then the mesh patches, the rivets and
    washers and the strap (strap: (P, W, O) stations of another wearer's path; None: the rest shape)"""
    d = dims(spec)
    prog = sdf.Program()
    prog.revolve(np.column_stack([body_profile(spec)[:, 0], body_profile(spec)[:, 1]]), [0.0, 0.0, 0.0],
                 [0.0, 0.0, 1.0], name='shell + edge trim')
    ex, ey, rad, hs = stadium(spec, d=d)
    zc = float(z_outer(d, np.hypot(ex, ey))) - 0.5 * spec['shell_t']
    for sx in (1.0, -1.0):
        prog.roundbox([sx * ex, ey, zc], [rad, rad + hs, 0.02], r=rad, op=sdf.SUBTRACT, k=spec['eye_fillet'],
                      name='eye opening')
    # the mesh patches: the inner face behind each opening, lapped mesh_margin round it
    g = np.linspace(-1.0, 1.0, 41)
    GX, GY = np.meshgrid(g, g, indexing='ij')
    rg, hg = rad + spec['mesh_margin'], hs
    X, Y = GX * rg, GY * (rg + hg)
    keep = stadium_sd(X, Y, rg, hg) <= 0.0006
    for sx in (1.0, -1.0):
        Px, Py = sx * ex + X, ey + Y
        Pz = z_inner(d, np.hypot(Px, Py), spec) - 0.5 * spec['mesh_t'] - 0.00005
        V = np.stack([Px, Py, Pz], -1).reshape(-1, 3)
        idx = np.arange(41 * 41).reshape(41, 41)
        q = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], -1).reshape(-1, 4)
        kq = keep.ravel()[q].all(1)
        q = q[kq]
        F = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
        prog.shell(V, F, 0.5 * spec['mesh_t'], k=0.0, maxd=0.01, name='mesh patch')
    for (A, n), sx in zip(anchors(spec, d), (1.0, -1.0)):
        prog.revolve(rivet_profile(spec), A, n, name='rivet head')
        B = A - n * washer_seat(spec)
        prog.revolve(washer_profile(spec), B, -n, name='washer + set end')
    P, W, O = strap if strap is not None else strap_path(spec, d=d)
    Pd, Wd, Od = strap_dense(P, W, O)
    hw = 0.5 * spec['strap_w'] - 0.5 * spec['strap_t']
    V = np.stack([Pd - hw * Wd, Pd, Pd + hw * Wd], 1).reshape(-1, 3)
    i = np.arange(len(Pd) - 1)[:, None] * 3 + np.arange(2)[None, :]
    q = np.stack([i, i + 3, i + 4, i + 1], -1).reshape(-1, 4)
    F = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
    prog.shell(V, F, 0.5 * spec['strap_t'], k=0.0, maxd=0.01, name='strap')
    prog.mask = dict(spec=spec, dims=d)
    return prog


def bounds(spec=SPEC, pad=0.004):
    P, W, O = strap_path(spec)
    lo = np.minimum(P.min(0) - 0.012, [-spec['R'], -spec['R'], -0.004])
    hi = np.maximum(P.max(0) + 0.012, [spec['R'], spec['R'], spec['depth'] + 0.006])
    return lo - pad, hi + pad


# ---------------------------------------------------------------------------------------------------- the low
def _polar(r, phi, z):
    return np.column_stack([r * np.sin(phi), r * np.cos(phi), np.broadcast_to(z, np.shape(phi))])


def _ring_s(spec, d):
    """the face rings' arc lengths: the cap ring, the eye patch's three, two more, the lip"""
    Rf = d['Rf']
    re = float(np.hypot(spec['eye_u'], spec['eye_v']))
    rr = [RING_R[0], re - EYE_BAND, re, re + EYE_BAND, RING_R[4], RING_R[5], 1.0]
    return [float(s_of_r(d, x * Rf)) for x in rr[:-1]] + [d['s1']]


def stadium_ring(cx, cy, rad, hs, loop_xy, n=16):
    """n points EVENLY spaced along a stadium's outline (a fair loop: equal chords), running the way the polygon
    loop_xy (n, 2) runs round it and turned to the start that brings point j nearest loop vertex j (least summed
    squared distance over 256 starts): the spokes from a patch's boundary to the opening's edge"""
    ang = np.linspace(0.0, 2.0 * np.pi, 2881)
    tt = stadium_ray(np.cos(ang), np.sin(ang), rad, hs)
    D = np.column_stack([cx + tt * np.cos(ang), cy + tt * np.sin(ang)])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(D, axis=0), axis=1))])
    per = s[-1]
    L = np.asarray(loop_xy, np.float64)
    c = L - np.array([cx, cy])
    ccw = (c[:, 0] * np.roll(c[:, 1], -1) - np.roll(c[:, 0], -1) * c[:, 1]).sum() > 0.0
    best = None
    for s0 in np.linspace(0.0, per, 256, endpoint=False):
        g = (s0 + (1.0 if ccw else -1.0) * per * np.arange(n) / n) % per
        P = np.column_stack([np.interp(g, s, D[:, 0]), np.interp(g, s, D[:, 1])])
        cost = float(((P - L) ** 2).sum())
        if best is None or cost < best[0]:
            best = (cost, P)
    return best[1]


def _disc_face(spec, d, inner, eye_xy=None):
    """one face of the disc (the outer, or the inner with inner=True) as a welded quad part: rings f1 .. lip at K
    columns, the 4 -> 2 reduction to the cap ring and its grid cap, each eye a 16-gon in a 6 x 2 patch (eye_xy: the
    openings' ring points from the other face, so the walls between them stand along +Z). Returns (V, Q, eye rings
    {+1: ids, -1: ids}, eye_xy)"""
    from .. import loft
    from ..mesh import QuadMesh
    S = _ring_s(spec, d)
    h = -spec['shell_t'] if inner else 0.0
    phi = 2.0 * np.pi * np.arange(K) / K
    rings = []
    for s in S[1:]:
        r, z = mer(d, s, h)
        rings.append(_polar(r, phi, z))
    V = np.vstack(rings)
    ids = np.arange(len(V)).reshape(len(rings), K)
    cols = {+1: EYE_COL, -1: K - EYE_COL}
    patch = {sx: [(c + j) % K for j in range(-3, 3)] for sx, c in cols.items()}       # the 6 removed columns' starts
    Q = []
    for i in range(len(rings) - 1):
        for k in range(K):
            if i < 2 and any(k in patch[sx] for sx in patch):
                continue
            Q.append([ids[i, k], ids[i, (k + 1) % K], ids[i + 1, (k + 1) % K], ids[i + 1, k]])
    ex, ey, rad, hs = stadium(spec, d=d)
    zf = (lambda x, y: z_inner(d, np.hypot(x, y), spec)) if inner else (lambda x, y: z_outer(d, np.hypot(x, y)))
    eye_ring = {}
    xy_out = {}
    for sx, c in cols.items():
        ks = [(c + j) % K for j in range(-3, 4)]
        loop = [ids[0, k] for k in ks] + [ids[1, ks[-1]]] + [ids[2, k] for k in ks[::-1]] + [ids[1, ks[0]]]
        cx = sx * ex
        Pe = stadium_ring(cx, ey, rad, hs, V[loop][:, :2]) if eye_xy is None else eye_xy[sx]
        xy_out[sx] = Pe
        px, py = Pe[:, 0], Pe[:, 1]
        n0 = len(V)
        V = np.vstack([V, np.column_stack([px, py, zf(px, py)])])
        ring = list(range(n0, n0 + 16))
        for j in range(16):
            Q.append([loop[j], loop[(j + 1) % 16], ring[(j + 1) % 16], ring[j]])
        eye_ring[sx] = ring
    m = QuadMesh(V, np.array(Q))
    r_c, z_c = mer(d, S[0], h)
    phi2 = 2.0 * np.pi * np.arange(K_CAP) / K_CAP
    m, inner_ring = loft.reduce_ring(m, ids[0], _polar(r_c, phi2, z_c))
    m, G = loft.cap(m, [int(x) for x in inner_ring], [0.0, 0.0, 1.0])
    V = m.V.copy()
    new = np.arange(len(V)) >= n0 + 16                                # the reduction's and the cap's vertices
    rr = np.hypot(V[new, 0], V[new, 1])
    V[new, 2] = zf(V[new, 0], V[new, 1])
    used = np.unique(m.Q)
    remap = -np.ones(len(V), np.int64)
    remap[used] = np.arange(len(used))
    Q = SC.orient(remap[m.Q], V[used], toward=[0.0, 0.0, -1.0 if inner else 1.0])
    return V[used], Q, {sx: remap[np.array(r)] for sx, r in eye_ring.items()}, xy_out


def build_low(spec=SPEC, strap=None, log=print):
    """the designed low as PARTS (soft_common.assemble's): front, trim, back, the eye walls, the mesh patches, the
    rivets, the washers, the strap. Every vertex on the block-out by construction. Returns (parts, info)"""
    from .. import loft
    from ..mesh import QuadMesh
    d = dims(spec)
    Rf = d['Rf']
    t, ht, rho = spec['shell_t'], spec['trim_t'], d['rho']
    phi = 2.0 * np.pi * np.arange(K) / K
    parts = []
    ri_t, zi_t, si_t = inner_tables(d, spec)
    # ---- the front: one unique island, laid out by the meridian's arc length (azimuthal, equidistant)
    Vf, Qf, eyeF, eye_xy = _disc_face(spec, d, False)
    rf = np.hypot(Vf[:, 0], Vf[:, 1])
    sf = s_of_r(d, rf)
    uvf = Vf[:, :2] * (sf / np.maximum(rf, 1e-12))[:, None]
    parts.append(dict(name='front', region=0, V=Vf, Q=Qf, uv=uvf, island='front', primary=True,
                      attr=np.column_stack([Vf[:, 0] / Rf, Vf[:, 1] / Rf, np.zeros(len(Vf)), np.zeros(len(Vf))])))
    # ---- the back: its two halves folded on one (x >= 0 the primary)
    Vb, Qb, eyeB, _ = _disc_face(spec, d, True, eye_xy)
    rb = np.hypot(Vb[:, 0], Vb[:, 1])
    sb = np.interp(rb, ri_t, si_t)
    uvb = np.column_stack([np.abs(Vb[:, 0]), Vb[:, 1]]) * (sb / np.maximum(rb, 1e-12))[:, None]
    cxq = Vb[Qb][:, :, 0].mean(1)
    parts.append(dict(name='back', region=2, V=Vb, Q=Qb, uv=uvb, island=['back' if c >= 0 else 'back_L' for c in cxq],
                      primary=cxq >= 0,
                      attr=np.column_stack([np.abs(Vb[:, 0]) / Rf, Vb[:, 1] / Rf, np.sign(Vb[:, 0]),
                                            np.zeros(len(Vb))])))
    # ---- the trim: 8 rings, K columns; eight 45 degree arcs stacked on the first
    s1, Se = d['s1'], d['S_e']
    Er, Ez = mer(d, Se, -0.5 * t)
    f = lambda arr: float(np.interp(Se, d['s'], arr))
    Nn, Tt = np.array([f(d['nr']), f(d['nz'])]), np.array([f(d['tr']), f(d['tz'])])
    bead = lambda a: np.array([Er, Ez]) + rho * (np.cos(a) * Nn + np.sin(a) * Tt)
    prof = [mer(d, s1, 0.0), mer(d, s1 + ht, ht), mer(d, Se, ht), bead(np.pi / 3), bead(2 * np.pi / 3),
            mer(d, Se, -(t + ht)), mer(d, s1 + ht, -(t + ht)), mer(d, s1, -t)]
    prof = np.array([[float(a), float(b)] for a, b in prof])
    vt = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(prof, axis=0), axis=1))])
    vt[3:5] = vt[2] + rho * np.array([np.pi / 3, 2 * np.pi / 3])      # the bead by its true arc
    vt[5:] = vt[5:] - vt[5] + vt[2] + rho * np.pi
    Vt = np.vstack([_polar(r, phi, z) for r, z in prof])
    idt = np.arange(len(Vt)).reshape(len(prof), K)
    Qt, uvt, isl_t = [], [], []
    R_ref = 0.5 * (Rf + spec['R'])
    arc = K // 8
    for i in range(len(prof) - 1):
        for k in range(K):
            Qt.append([idt[i, k], idt[i, (k + 1) % K], idt[i + 1, (k + 1) % K], idt[i + 1, k]])
            j = k % arc
            u0, u1 = j * 2 * np.pi / K * R_ref, (j + 1) * 2 * np.pi / K * R_ref
            uvt.append([[u0, vt[i]], [u1, vt[i]], [u1, vt[i + 1]], [u0, vt[i + 1]]])
            isl_t.append('trim' if k // arc == 0 else f'trim_{k // arc}')
    Qt = np.array(Qt)
    Qo = SC.orient(Qt, Vt)
    q3 = 3 * K                                                        # a bead quad: its normal must point outward
    nq = np.cross(Vt[Qo[q3, 2]] - Vt[Qo[q3, 0]], Vt[Qo[q3, 3]] - Vt[Qo[q3, 1]])
    flip = nq @ (Vt[Qo[q3]].mean(0) * np.array([1.0, 1.0, 0.0])) < 0
    uvt = np.array(uvt)
    if flip:
        Qo, uvt = Qo[:, ::-1].copy(), uvt[:, ::-1].copy()
    # (orient keeps each quad's vertex order or reverses it: its corner UVs follow)
    for f_ in range(len(Qt)):
        if not np.array_equal(Qo[f_], Qt[f_][::-1] if flip else Qt[f_]):
            uvt[f_] = uvt[f_][::-1]
    at = np.zeros((len(Vt), 4))
    at[:, 0] = np.repeat(vt, K)                                       # the profile coordinate (the die lines' across)
    at[:, 1] = np.tile(phi * R_ref, len(prof))
    parts.append(dict(name='trim', region=1, V=Vt, Q=Qo, uv=uvt, island=isl_t,
                      primary=np.array([nm == 'trim' for nm in isl_t]), attr=at))
    # ---- the eye walls, the mesh patches
    ex, ey, rad, hs = stadium(spec, d=d)
    for sx in (1.0, -1.0):
        F3, B3 = Vf[eyeF[int(sx)]], Vb[eyeB[int(sx)]]
        per = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.vstack([F3, F3[:1]]), axis=0), axis=1))])
        Vw = np.vstack([F3, F3[:1], B3, B3[:1]])
        dep = np.linalg.norm(Vw[:17] - Vw[17:], axis=1)
        Qw = np.array([[j, j + 1, 17 + j + 1, 17 + j] for j in range(16)])
        Qw = SC.orient(Qw, Vw)
        cen = np.array([sx * ex, ey, Vw[:, 2].mean()])
        nq = np.cross(Vw[Qw[:, 2]] - Vw[Qw[:, 0]], Vw[Qw[:, 3]] - Vw[Qw[:, 1]])
        if (nq * (cen - Vw[Qw].mean(1))).sum() < 0:
            Qw = Qw[:, ::-1].copy()
        uw = per if sx > 0 else per[-1] - per                         # the right eye's wall mirrored onto the left's
        uvw = np.vstack([np.column_stack([uw, np.zeros(17)]), np.column_stack([uw, dep])])
        aw = np.column_stack([np.concatenate([uw, uw]), np.concatenate([np.zeros(17), dep]),
                              np.full(34, sx), np.zeros(34)])
        parts.append(dict(name=f'eye_wall_{"L" if sx > 0 else "R"}', region=3, V=Vw, Q=Qw, uv=uvw,
                          island='eye_wall' if sx > 0 else 'eye_wall_R', primary=sx > 0, attr=aw))
        # the mesh patch: a lens of two 4 x 4 caps on one rim ring (the stadium grown by the lap)
        ang = np.linspace(0.0, 2.0 * np.pi, 16, endpoint=False)
        dn = np.column_stack([np.cos(ang), np.sin(ang)])
        tt = stadium_ray(dn[:, 0], dn[:, 1], rad + spec['mesh_margin'], hs)
        px, py = sx * ex + tt * dn[:, 0], ey + tt * dn[:, 1]
        zi_ = lambda x, y: z_inner(d, np.hypot(x, y), spec)
        rim = np.column_stack([px, py, zi_(px, py) - 0.5 * spec['mesh_t'] - 0.00005])
        m = QuadMesh(rim, np.zeros((0, 4), np.int64))
        m, G1 = loft.cap(m, list(range(16)), [0.0, 0.0, 1.0], shape=(4, 4))
        n1 = len(m.V)
        m, G2 = loft.cap(m, list(range(16)), [0.0, 0.0, -1.0], shape=(4, 4), flip=True)
        Vm = m.V.copy()
        Vm[16:n1, 2] = zi_(Vm[16:n1, 0], Vm[16:n1, 1]) - 0.00005
        Vm[n1:, 2] = zi_(Vm[n1:, 0], Vm[n1:, 1]) - spec['mesh_t'] - 0.00005
        Qm = m.Q.copy()
        nq = np.cross(Vm[Qm[:, 2]] - Vm[Qm[:, 0]], Vm[Qm[:, 3]] - Vm[Qm[:, 1]])[:, 2]
        Qm[:16] = np.where((nq[:16] < 0)[:, None], Qm[:16, ::-1], Qm[:16])
        Qm[16:] = np.where((nq[16:] > 0)[:, None], Qm[16:, ::-1], Qm[16:])
        uvm = np.column_stack([sx * (Vm[:, 0] - sx * ex), Vm[:, 1] - ey])
        nm = 'L' if sx > 0 else 'R'
        parts.append(dict(name=f'mesh_{nm}', region=4, V=Vm, Q=Qm, uv=uvm,
                          island=['mesh' if sx > 0 else 'mesh_R'] * 16 + [f'mesh_{nm}_back'] * 16,
                          primary=np.array([sx > 0] * 16 + [False] * 16),
                          attr=np.column_stack([uvm, np.full(len(Vm), sx), np.zeros(len(Vm))])))
    # ---- the rivets (front) and the washers with the set ends (inside): lathes of RIVET_K columns about the shell's
    #      normal at each anchor, the two sides stacked
    th = 2.0 * np.pi * np.arange(RIVET_K) / RIVET_K
    for (A, n), sx in zip(anchors(spec, d), (1.0, -1.0)):
        nm = 'L' if sx > 0 else 'R'
        for kind in ('rivet', 'washer'):
            if kind == 'rivet':
                o, a = A, n
                rr = np.array([spec['rivet_r'], 0.74 * spec['rivet_r'], 0.42 * spec['rivet_r']])
                hh = rivet_height(rr, spec)
                top = float(rivet_height(0.0, spec))
                Rr = (spec['rivet_r'] ** 2 + spec['rivet_h'] ** 2) / (2.0 * spec['rivet_h'])
                sa = Rr * np.arcsin(rr / Rr)                          # the dome's arc from its pole
                hfun = lambda r_: rivet_height(r_, spec)
                sfun = lambda r_: Rr * np.arcsin(np.clip(r_ / Rr, 0.0, 1.0))
            else:
                o, a = A - n * washer_seat(spec), -n
                wr, wh, tr_, th_ = spec['washer_r'], spec['washer_h'], spec['tail_r'], spec['tail_h']
                rr = np.array([wr, wr, tr_, 0.6 * tr_])
                hh = np.array([0.0, wh, wh, wh + th_ * np.sqrt(1.0 - 0.36)])
                top = wh + th_
                hfun = lambda r_: wh + th_ * np.sqrt(np.maximum(1.0 - (r_ / tr_) ** 2, 0.0))
                sfun = lambda r_: r_ * 1.15
                sa = np.array([wr + wh, wr, tr_ * 1.15, 0.6 * tr_ * 1.15])
            e1, e2 = _frame(a)
            e2 = e2 * sx                                              # the right side's frame mirrored: stacked UVs
            ring = lambda r_, h_: o + a * h_ + r_ * (np.cos(th)[:, None] * e1 + np.sin(th)[:, None] * e2)
            Vr = np.vstack([ring(r_, h_) for r_, h_ in zip(rr, hh)])
            uvr = np.vstack([s_ * np.column_stack([np.cos(th), np.sin(th)]) for s_ in sa])
            idr = np.arange(len(Vr)).reshape(len(rr), RIVET_K)
            Qr = [[idr[i, k], idr[i, (k + 1) % RIVET_K], idr[i + 1, (k + 1) % RIVET_K], idr[i + 1, k]]
                  for i in range(len(rr) - 1) for k in range(RIVET_K)]
            m = QuadMesh(Vr, np.array(Qr))
            m, G = loft.cap(m, [int(x) for x in idr[-1]], a, shape=(3, 3))
            Vr2 = m.V.copy()
            new = np.arange(len(Vr2)) >= len(Vr)
            loc = Vr2[new] - o
            lr = np.hypot(loc @ e1, loc @ e2)
            Vr2[new] = o + (loc @ e1)[:, None] * e1 + (loc @ e2)[:, None] * e2 + a * hfun(lr)[:, None]
            dirs = np.column_stack([loc @ e1, loc @ e2]) / np.maximum(lr, 1e-12)[:, None]
            uvr = np.vstack([uvr, sfun(lr)[:, None] * dirs])
            Qr = SC.orient(m.Q, Vr2, centre=o - a * 0.01)
            reg = 5 if kind == 'rivet' else 6
            parts.append(dict(name=f'{kind}_{nm}', region=reg, V=Vr2, Q=Qr, uv=uvr,
                              island=kind if sx > 0 else f'{kind}_R', primary=sx > 0,
                              attr=np.column_stack([uvr, np.full(len(Vr2), sx), np.zeros(len(Vr2))])))
    # ---- the strap: 4 faces round, N_STATION stations, 8 tiles of 4 segments each stacked on the first; the inner
    #      face on the outer; the two thin edges beside it
    P, W, O = strap if strap is not None else strap_path(spec, d=d)
    C4 = strap_verts(P, W, O, spec)                                   # (stations, 4, 3)
    Vs = C4.reshape(-1, 3)
    ids = np.arange(len(Vs)).reshape(N_STATION, 4)
    Ls = np.linalg.norm(np.diff(P, axis=0), axis=1)
    tile_len = 4.0 * float(Ls.mean())
    w_, t_ = spec['strap_w'], spec['strap_t']
    vcorner = {0: (t_ + w_, t_), 1: (t_, 0.0), 2: (t_, t_ + w_), 3: (t_ + w_ + t_, t_ + w_)}
    # faces round the section: 0 outer (corner 0 -> 1), 1 edge at -W (1 -> 2), 2 inner (2 -> 3), 3 edge at +W (3 -> 0)
    span = {0: (t_ + w_, t_), 1: (t_, 0.0), 2: (t_, t_ + w_), 3: (t_ + w_ + t_, t_ + w_)}
    Qs, uvs, isl_s, prim_s = [], [], [], []
    for j in range(N_STATION - 1):
        tile, k4 = divmod(j, 4)
        u0, u1 = k4 * tile_len / 4.0, (k4 + 1) * tile_len / 4.0
        for fc in range(4):
            a, b = fc, (fc + 1) % 4
            Qs.append([ids[j, a], ids[j, b], ids[j + 1, b], ids[j + 1, a]])
            va, vb = span[fc]
            uvs.append([[u0, va], [u0, vb], [u1, vb], [u1, va]])
            base = 'strap' if fc in (0, 1, 3) else 'strap_in'
            isl_s.append(base if (tile == 0 and fc != 2) else f'{base}_{tile}')
            prim_s.append(tile == 0 and fc != 2)
    for j, rev in ((0, False), (N_STATION - 1, True)):                # the two cut ends
        q = [ids[j, 0], ids[j, 3], ids[j, 2], ids[j, 1]]
        Qs.append(q[::-1] if rev else q)
        uvs.append([[0.0, t_ + w_], [0.0, t_ + w_ + t_], [0.002, t_ + w_ + t_], [0.002, t_ + w_]])
        isl_s.append(f'strap_end_{j}')
        prim_s.append(False)
    Qs, uvs = np.array(Qs), np.array(uvs)
    Qo = SC.orient(Qs, Vs)
    q0 = 0                                                            # the first outer face: its normal along O
    nq = np.cross(Vs[Qo[q0, 2]] - Vs[Qo[q0, 0]], Vs[Qo[q0, 3]] - Vs[Qo[q0, 1]])
    flip = bool(nq @ O[0] < 0)
    if flip:
        Qo = Qo[:, ::-1].copy()
    for f_ in range(len(Qs)):
        if not np.array_equal(Qo[f_], Qs[f_]):
            uvs[f_] = uvs[f_][::-1] if np.array_equal(Qo[f_], Qs[f_][::-1]) else uvs[f_]
    a_s = np.zeros((len(Vs), 4))
    a_s[:, 0] = np.repeat((np.arange(N_STATION) % 4) * tile_len / 4.0, 4)
    a_s[:, 1] = np.tile([w_, 0.0, 0.0, w_], N_STATION)
    a_s[:, 2] = np.repeat(np.concatenate([[0.0], np.cumsum(Ls)]), 4)
    parts.append(dict(name='strap', region=7, V=Vs, Q=Qo, uv=uvs, island=isl_s, primary=np.array(prim_s), attr=a_s))
    info = dict(dims=d, strap=(P, W, O), tile_len=tile_len, n_strap=len(Vs))
    nq_ = sum(len(p['Q']) for p in parts)
    log(f'[face_mask] low: {len(parts)} parts, {nq_} quads ({2 * nq_} triangles): '
        + ', '.join(f'{p["name"]} {len(p["Q"])}' for p in parts))
    return parts, info


def strap_shape(L, low, hull, y, spec=SPEC, tilt=0.0):
    """the export's vertices and normals with the STRAP on another wearer's head (hull: the head's outline in the
    strap's plane, strap_path's (x, zp); tilt: that plane's turn): the same stations, so the same vertices in the
    same order; everything else is the rigid mask, untouched. Returns (V, N, (P, W, O)) for a morph target"""
    P, W, O = strap_path(spec, hull=hull, y=y, tilt=tilt)
    C4 = strap_verts(P, W, O, spec).reshape(-1, 3)
    sel = np.nonzero(np.asarray(low['part'])[np.arange(len(low['Q']))] == low['parts'].index('strap'))[0]
    V2 = np.asarray(L['V'], np.float64).copy()
    # the strap part's export vertices keep their source corner (assemble splits per island: nearest REST corner)
    P0, W0, O0 = strap_path(spec)
    rest = strap_verts(P0, W0, O0, spec).reshape(-1, 3)
    vs = np.unique(low['Q'][sel])
    from scipy.spatial import cKDTree
    _, j = cKDTree(rest).query(V2[vs])
    V2[vs] = C4[j]
    F = np.asarray(L['F'])
    fn = np.cross(V2[F[:, 1]] - V2[F[:, 0]], V2[F[:, 2]] - V2[F[:, 0]])
    first, inv = SC.weld(V2)
    acc = np.zeros((len(first), 3))
    for k in range(3):
        np.add.at(acc, inv[F[:, k]], fn)
    Nw = np.asarray(L['N'], np.float64).copy()
    Nw[vs] = SC.unit(acc)[inv][vs]
    return V2, Nw, (P, W, O)


# ------------------------------------------------------------------------------------------------- material pass
@wp.struct
class Surf:
    h: float            # the texture tier's height (m)
    col: wp.vec3        # linear albedo
    rough: float
    metal: float
    fuzz: float
    mat: float          # masks G
    zone: float         # masks B (0 face, 1/3 inside, 2/3 ink, 1 strap)
    ao: float           # an occlusion factor of its own (the channels' walls)
    wear: wp.vec4       # chips, scuffs, grime, handling (for the eye)


@wp.func
def tab2(t: wp.array2d(dtype=wp.float32), u: float, v: float):
    """the ink table at (u, v) in face units (bilinear; [-1.05, 1.05]^2)"""
    n = t.shape[0]
    x = wp.clamp((u + 1.05) / 2.1, 0.0, 1.0) * float(n - 1)
    y = wp.clamp((v + 1.05) / 2.1, 0.0, 1.0) * float(n - 1)
    i = wp.min(int(x), n - 2)
    j = wp.min(int(y), n - 2)
    fx = x - float(i)
    fy = y - float(j)
    return (t[j, i] * (1.0 - fx) + t[j, i + 1] * fx) * (1.0 - fy) + (t[j + 1, i] * (1.0 - fx) + t[j + 1, i + 1] * fx) * fy


@wp.func
def streaks(p: wp.vec3, ax: wp.vec3, ay: wp.vec3, length: float, width: float, seed: int):
    """sparse straight scratches along ax: 0..1"""
    q = wp.vec3(wp.dot(p, ax) / length, wp.dot(p, ay) / width, 0.37 * float(seed))
    # (11-11 07:20: 0.52-0.72 drew scuffs on 0.2 % of the dome, mean 0.002: none to see)
    return proc.smoothstep(0.30, 0.55, proc.noise3(q, seed))


@wp.func
def surf_at(p: wp.vec3, reg: int, at: wp.vec4, conv: float, convm: float, ao: float, aol: float, texel: float,
            ink: wp.array2d(dtype=wp.float32), C: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32), seed: int,
            full: int):
    """the surface at a point of the low's region reg (at: the vertex attributes). full = 0: the height only"""
    o = Surf()
    Rf = S[0]
    h = float(0.0)
    col = wp.vec3(0.5, 0.5, 0.5)
    rough = float(0.5)
    metal = float(0.0)
    fuzz = float(0.0)
    mat = float(0.0)
    zone = float(0.0)
    aof = float(1.0)
    w_chip = float(0.0)
    w_scuff = float(0.0)
    w_grime = float(0.0)
    w_hand = float(0.0)
    grime = wp.clamp(1.6 * (1.0 - ao) + 4.0 * wp.max(-aol, 0.0), 0.0, 1.0)
    if reg == 0:
        u = p[0] / Rf
        v = p[1] / Rf
        dmm = tab2(ink, u, v) * Rf                                   # metres to the ink's edge (- inside)
        inside = proc.smoothstep(0.0004, -0.0012, dmm)                # the channel's floor
        h = -S[1] * inside
        h = h + S[2] * (proc.noise3(p / 0.0028, seed + 3) + 0.35 * proc.noise3(p / 0.0011, seed + 5)) * \
            proc.smoothstep(1.5, 3.0, 0.0028 / texel)
        if full == 1:
            inkw = proc.smoothstep(0.00012, -0.00012, dmm)
            rr = wp.sqrt(u * u + v * v)
            # chips: the bake's convex edges (the eye openings' rims) and the channels' own lips, in 4 mm patches
            # along them. (11-11 07:20, measured on the bake: the front's fine convexity is p99 0.56, p99.9 1.98, max
            # 2.68, only along those rims; the first terms, 0.42 x conv + 0.30 x lip + noise over 0.78, chipped
            # nothing: chips mean 0.000, p95 0.000)
            lip = wp.exp(-(dmm - 0.0003) * (dmm - 0.0003) / (0.00035 * 0.00035))
            cn = proc.fbm3(p / 0.004, 3, 2.0, 0.5, seed + 11)
            # (07:25) by the 3 mm convexity (the fine one is striped by the low's 16-gon facets round each opening),
            # and SHARP: a chip is there or not (partial values lightened the whole rim into a pale streaky ring)
            drive = S[8] * (proc.smoothstep(0.25, 0.8, convm) + 0.35 * lip)
            w_chip = proc.smoothstep(0.45, 0.55, drive * proc.smoothstep(0.08, 0.16, cn))
            # a few nicks on the dome's crown (it lies face down on tables)
            cel = proc.cellular3(p / 0.021, 0.9, seed + 13)
            crown = proc.smoothstep(0.62, 0.20, rr)
            w_chip = wp.max(w_chip, S[8] * crown * proc.smoothstep(0.045, 0.02, cel.f1) *
                            proc.smoothstep(0.1, 0.5, proc.noise3(p / 0.03, seed + 17)))
            # scuffs: fine scratches in three directions, densest on the crown
            sc = streaks(p, wp.vec3(0.94, 0.34, 0.0), wp.vec3(-0.34, 0.94, 0.0), 0.022, 0.00028, seed + 21)
            sc = wp.max(sc, streaks(p, wp.vec3(0.26, 0.97, 0.0), wp.vec3(-0.97, 0.26, 0.0), 0.016, 0.00024, seed + 23))
            sc = wp.max(sc, streaks(p, wp.vec3(0.77, -0.64, 0.0), wp.vec3(0.64, 0.77, 0.0), 0.030, 0.00030, seed + 25))
            w_scuff = S[9] * sc * (0.25 + 0.75 * crown) * proc.smoothstep(-0.2, 0.4, proc.noise3(p / 0.035, seed + 27))
            # handled where it is picked up: the rim at the sides
            w_hand = proc.smoothstep(0.55, 0.95, rr) * proc.smoothstep(0.3, 0.9, wp.abs(u) / wp.max(rr, 0.001)) * \
                (0.5 + 0.5 * proc.fbm3(p / 0.012, 2, 2.0, 0.5, seed + 31))
            w_grime = S[10] * grime * (0.6 + 0.4 * proc.noise3(p / 0.006, seed + 33))
            # the channel's walls hold a little dust, and shade themselves
            wall = wp.exp(-(dmm + 0.0004) * (dmm + 0.0004) / (0.0006 * 0.0006))
            w_grime = wp.max(w_grime, 0.35 * S[10] * wall)
            aof = 1.0 - 0.18 * wall
            enamel = M.mix3(C[0], C[1], inkw)
            cloud = 0.025 * proc.fbm3(p / 0.03, 2, 2.0, 0.5, seed + 35)
            col = enamel * wp.exp(cloud)
            col = M.mix3(col, col * 1.22 + wp.vec3(0.012, 0.012, 0.012), 0.55 * w_scuff)
            col = M.mix3(col, C[2] * (0.86 + 0.14 * cn), w_chip)
            col = M.mix3(col, C[8], 0.75 * w_grime)
            rough = S[3] + (S[4] - S[3]) * inkw + S[11] * w_hand + 0.22 * w_scuff
            rough = rough + (S[5] - rough) * w_chip
            rough = rough + (0.85 - rough) * 0.8 * w_grime
            h = h - 0.00006 * w_chip
            zone = (2.0 / 3.0) * inkw
            if w_chip > 0.5:
                zone = 1.0 / 3.0
    elif reg == 1:
        # the rubber edge trim: the extrusion's die lines run round the rim (constant profile coordinate at[0])
        h = 0.000005 * wp.cos(6.2831853 * at[0] / 0.0007) * proc.smoothstep(2.0, 3.5, 0.0007 / texel)
        h = h + 0.000004 * proc.noise3(p / 0.0009, seed + 41) * proc.smoothstep(2.0, 3.5, 0.0009 / texel)
        if full == 1:
            rub = proc.smoothstep(0.6, 1.8, convm) * (0.5 + 0.5 * proc.noise3(p / 0.008, seed + 43))
            w_scuff = rub
            w_grime = S[10] * grime
            col = C[3] * (1.0 + 0.10 * proc.noise3(p / 0.004, seed + 45))
            col = M.mix3(col, wp.vec3(0.085, 0.085, 0.088), 0.55 * rub)
            col = M.mix3(col, C[8], 0.8 * w_grime)
            rough = S[6] - 0.10 * rub + 0.25 * w_grime
            zone = 2.0 / 3.0
    elif reg == 2:
        # the bare laminate inside: chopped strands under the resin, three directions of short fibres
        f1 = proc.noise3(wp.vec3(p[0] / 0.012, p[1] / 0.0005, 1.3), seed + 51)
        f2 = proc.noise3(wp.vec3((0.5 * p[0] + 0.866 * p[1]) / 0.012, (0.866 * p[0] - 0.5 * p[1]) / 0.0005, 4.1), seed + 53)
        f3 = proc.noise3(wp.vec3((0.5 * p[0] - 0.866 * p[1]) / 0.012, (0.866 * p[0] + 0.5 * p[1]) / 0.0005, 7.7), seed + 55)
        fib = wp.max(f1, wp.max(f2, f3))
        h = 0.00003 * fib * proc.smoothstep(1.5, 3.0, 0.0005 / texel) + 0.00002 * proc.noise3(p / 0.004, seed + 57)
        if full == 1:
            w_grime = S[10] * grime * (0.6 + 0.4 * proc.noise3(p / 0.006, seed + 59))
            col = C[2] * (0.93 + 0.09 * fib) * wp.exp(0.05 * proc.fbm3(p / 0.04, 2, 2.0, 0.5, seed + 61))
            col = M.mix3(col, C[8], 0.7 * w_grime)
            rough = S[5] + 0.06 * fib + 0.2 * w_grime
            zone = 1.0 / 3.0
    elif reg == 3:
        # the openings' cut walls: painted with the eyes, chipped at the front edge
        h = 0.000004 * proc.noise3(p / 0.0012, seed + 63)
        if full == 1:
            edge = proc.smoothstep(0.0009, 0.0, at[1])
            w_chip = proc.smoothstep(0.55, 0.8, S[8] * edge * (0.6 + 0.8 * proc.noise3(p / 0.003, seed + 65)))
            col = M.mix3(C[1], C[2], w_chip)
            rough = S[4] + 0.1 + (S[5] - S[4]) * w_chip
            zone = 2.0 / 3.0
            if w_chip > 0.5:
                zone = 1.0 / 3.0
    elif reg == 4:
        # the black mesh: a diamond net, 1.1 mm
        a = (at[0] + at[1]) * 0.7071 / 0.0011
        b = (at[0] - at[1]) * 0.7071 / 0.0011
        net = wp.max(wp.cos(6.2831853 * a), wp.cos(6.2831853 * b))
        h = 0.00006 * net * proc.smoothstep(2.0, 3.5, 0.0011 / texel)
        if full == 1:
            col = C[4] * (0.8 + 0.4 * proc.smoothstep(-0.2, 0.9, net))
            rough = S[7]
            fuzz = 0.22
            zone = 2.0 / 3.0
            mat = 1.0
    elif reg == 5 or reg == 6:
        # nickel rivet / zinc washer: turned and polished round the axis, METAL
        rr = wp.sqrt(at[0] * at[0] + at[1] * at[1])
        h = 0.0000015 * wp.cos(6.2831853 * rr / 0.00035) * proc.smoothstep(2.0, 3.5, 0.00035 / texel)
        if full == 1:
            w_grime = S[10] * grime
            w_scuff = proc.smoothstep(0.2, 0.7, proc.noise3(p / 0.0015, seed + 71))
            base = C[5]
            r0 = S[12]
            if reg == 6:
                base = C[6]
                r0 = S[13]
            col = base * (1.0 - 0.35 * w_grime) * (0.96 + 0.06 * proc.noise3(p / 0.002, seed + 73))
            rough = r0 + 0.10 * w_scuff + 0.30 * w_grime
            metal = 1.0
            zone = 1.0 / 3.0
    else:
        # the woven elastic: 12 cords along it (across = at[1]), the weft every 0.5 mm (along = at[0])
        rib = wp.pow(0.5 + 0.5 * wp.cos(6.2831853 * at[1] / 0.001667), 0.7)
        weft = wp.cos(6.2831853 * at[0] / 0.0005)
        h = 0.00009 * rib * proc.smoothstep(2.0, 3.5, 0.001667 / texel) + 0.00002 * weft * rib * \
            proc.smoothstep(2.5, 4.0, 0.0005 / texel)
        if full == 1:
            w_grime = 0.5 * S[10] * grime
            col = C[7] * (0.75 + 0.5 * rib) * (1.0 + 0.12 * proc.noise3(p / 0.003, seed + 81))
            col = M.mix3(col, C[8], 0.5 * w_grime)
            rough = S[14] - 0.06 * rib
            fuzz = 0.30
            zone = 1.0
            mat = 1.0 / 3.0
    o.h = h
    o.col = col
    o.rough = rough
    o.metal = metal
    o.fuzz = fuzz
    o.mat = mat
    o.zone = zone
    o.ao = aof
    o.wear = wp.vec4(w_chip, w_scuff, w_grime, w_hand)
    return o


@wp.kernel
def k_mask(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
           ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32),
           d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_base: wp.array(dtype=wp.vec4),
           d_aol: wp.array(dtype=wp.float32), d_conv: wp.array(dtype=wp.float32),
           d_convm: wp.array(dtype=wp.float32), ink: wp.array2d(dtype=wp.float32), C: wp.array(dtype=wp.vec3),
           S: wp.array(dtype=wp.float32), texel: float, seed: int, o_alb: wp.array(dtype=wp.vec3),
           o_nrm: wp.array(dtype=wp.vec3), o_orm: wp.array(dtype=wp.vec3), o_mask: wp.array(dtype=wp.vec4),
           o_wear: wp.array(dtype=wp.vec4), o_hit: wp.array(dtype=wp.int32)):
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
    acc_ao = float(0.0)
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
            sf = surf_at(pb0, reg, lo.attr, d_conv[tid], d_convm[tid], d_ao[tid], d_aol[tid], texel, ink, C, S, seed, 1)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1:
                pbx = lx.p + lx.n * hb
                pby = ly.p + ly.n * hb
                hx = surf_at(pbx, reg, lx.attr, 0.0, 0.0, 1.0, 0.0, texel, ink, C, S, seed, 0).h
                hy = surf_at(pby, reg, ly.attr, 0.0, 0.0, 1.0, 0.0, texel, ink, C, S, seed, 0).h
                h0 = surf_at(pb0, reg, lo.attr, 0.0, 0.0, 1.0, 0.0, texel, ink, C, S, seed, 0).h
                g = M.surface_grad(pb0, pbx, pby, h0, hx, hy)
            nw = M.to_world(lo, tn_b)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            acc_a = acc_a + sf.col
            acc_r = acc_r + wp.clamp(sf.rough, 0.04, 1.0)
            acc_m = acc_m + sf.metal
            acc_ao = acc_ao + d_ao[tid] * sf.ao
            acc_k = acc_k + wp.vec4(sf.fuzz, sf.mat, sf.zone, 0.0)
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
    o_orm[tid] = wp.vec3(acc_ao / fh, wp.clamp(rr, 0.0, 1.0), wp.clamp(acc_m / fh, 0.0, 1.0))
    o_mask[tid] = acc_k / fh
    o_wear[tid] = acc_w / fh
    o_hit[tid] = 1


def material_tables(design, spec=SPEC, recipe=MATERIAL, d=None):
    d = d or dims(spec)
    D = DESIGNS[design]
    C = np.array([D['face'], recipe['ink'], recipe['laminate'], recipe['rubber'], recipe['mesh'], recipe['nickel'],
                  recipe['zinc'], recipe['elastic'], recipe['dust']], np.float32)
    S = np.array([d['Rf'], spec['deboss'], recipe['peel_amp'], recipe['enamel_rough'], recipe['ink_rough'],
                  recipe['laminate_rough'], recipe['rubber_rough'], recipe['mesh_rough'], recipe['chip'],
                  recipe['scuff'], recipe['grime'], recipe['haze'], recipe['nickel_rough'], recipe['zinc_rough'],
                  recipe['elastic_rough']], np.float32)
    return C, S


def run_material(L, drivers, size, texel, design, spec=SPEC, ss=2, recipe=MATERIAL, log=print):
    """the material pass for ONE face (design: 'smile' | 'frown') over the mould's shared bake, on the PRIMARY
    triangles. Returns soft_common.finish_maps' dict (albedo, normal, orm with METALNESS in B, masks RGB, wear,
    palette_base)"""
    import time

    from .. import calib
    t0 = time.time()
    pr = np.asarray(L['primary'], bool)
    F = L['F'][pr]
    uvm = M.uv_bvh(F, L['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(L['V'], F, L['N'], L['TAN'], L['ATTR'])
    keep = {k: drivers[k] for k in ('normal', 'ao', 'curvature', 'base', 'mat') if k in drivers}
    Dv = M.driver_arrays({**keep, **calib.relief_drivers(keep, 1.0 / texel)})
    C, S = material_tables(design, spec, recipe)
    tab = wp.array(ink_table(design, recipe['table_n'], spec, eyes=False), dtype=wp.float32)
    n = size * size
    o_alb, o_nrm, o_orm = (wp.zeros(n, dtype=wp.vec3) for _ in range(3))
    o_mask, o_wear = wp.zeros(n, dtype=wp.vec4), wp.zeros(n, dtype=wp.vec4)
    o_hit = wp.zeros(n, dtype=wp.int32)
    wp.launch(k_mask, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
                                     wp.array(np.asarray(L['region'], np.int32)[pr], dtype=wp.int32), Dv['normal'],
                                     Dv['ao'], Dv['base'], Dv['ao_local'], Dv['conv'], Dv['conv_mid'], tab,
                                     wp.array(C, dtype=wp.vec3), wp.array(S, dtype=wp.float32), float(texel),
                                     int(recipe['seed']), o_alb, o_nrm, o_orm, o_mask, o_wear, o_hit])
    wp.synchronize()
    img = lambda a, k: np.asarray(a.numpy()).reshape(size, size, k)[::-1]
    cov = np.asarray(o_hit.numpy()).reshape(size, size)[::-1] > 0
    wear = img(o_wear, 4)
    maps = SC.finish_maps(img(o_alb, 3), img(o_nrm, 3), img(o_orm, 3), img(o_mask, 4), wear, cov, ZONES)
    wm = wear[cov]
    log(f'[face_mask] material ({design}) {size}^2 x ss {ss}: {time.time() - t0:.1f}s over {int(cov.sum())} texels '
        f'({cov.mean() * 100:.1f} % of the sheet); palette base (linear) '
        + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in maps['palette_base'].items())
        + '; wear, mean / p95: ' + ', '.join(f'{nm} {wm[:, i].mean():.3f} / {np.percentile(wm[:, i], 95):.3f}'
                                            for i, nm in enumerate(('chips', 'scuffs', 'grime', 'handling'))))
    return maps


# ------------------------------------------------------------------------------------------------------ fit data
def fit_data(design, spec=SPEC, conform=None, n_rim=64):
    """what a mask's fitter and the runtime need (prop space, metres; remix.js's item contract): the seat frame, the
    authored radius (recipe.ARCHETYPES['mask']: scale = fit.radius / this), the RIM's contact circle and probes on
    it (the 2 mm rim rule's), probes on the inside of the dome and under the trim, the eyes, the strap's anchors and
    its targets, and `conform`: {species: {socket, pose: {offset, rotation (x, y, z, w), scale}, strap: target}}"""
    d = dims(spec)
    rho = d['rho']
    Er, Ez = mer(d, d['S_e'], -0.5 * spec['shell_t'])
    ph = np.linspace(0.0, 2.0 * np.pi, n_rim, endpoint=False)
    rim = np.column_stack([float(Er) * np.sin(ph), float(Er) * np.cos(ph), np.zeros(n_rim)])
    rr = np.linspace(0.0, 0.96, 13)[:, None] * d['Rf']
    pp = np.linspace(0.0, 2.0 * np.pi, 24, endpoint=False)[None, :]
    X, Y = (rr * np.sin(pp)).ravel(), (rr * np.cos(pp)).ravel()
    ins = np.column_stack([X, Y, z_inner(d, np.hypot(X, Y), spec)])
    ex, ey, rad, hs = stadium(spec, d=d)
    A = anchors(spec, d)
    rnd = lambda a: np.round(np.asarray(a, np.float64), 5).tolist()
    return dict(archetype='mask', prop=DESIGNS[design]['name'], design=design, radius=spec['R'],
                depth=round(float(spec['depth'] + d['z0']), 5),
                seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0], left=[1.0, 0.0, 0.0]),
                rim=dict(radius=round(float(Er), 5), z=0.0, bead=round(float(rho), 5), probes=rnd(rim)),
                inside=dict(probes=rnd(ins)),
                eyes=dict(centres=rnd([[ex, ey, float(z_outer(d, np.hypot(ex, ey)))],
                                       [-ex, ey, float(z_outer(d, np.hypot(ex, ey)))]]),
                          half=[round(rad, 5), round(rad + hs, 5)]),
                strap=dict(anchors=rnd([a for a, _ in A]), width=spec['strap_w'], thickness=spec['strap_t'],
                           rest_head=dict(a=spec['head_a'], c=spec['head_c'], z=spec['head_z']),
                           note='an ELASTIC strap: its path per wearer is a morph target named in conform[species]'
                                '.strap; the rest shape is the strap on a person\'s head'),
                volume=dict(kind='cylinders', axis='+Z',
                            parts=[dict(name='mask', z=[-0.002, round(float(spec['depth'] + d['z0'] + 0.004), 5)],
                                        radius=round(spec['R'] + 0.002, 5))]),
                conform=conform or {})


# --------------------------------------------------------------------------------------------- the forge's stages
def make_low(size=2048, spec=SPEC, strap=None, log=print):
    """the low with its UVs as the export's arrays (CPU, seconds): parts -> assemble -> pack -> low_arrays"""
    parts, info = build_low(spec, strap, log)
    low = SC.assemble(parts)
    fill, place, ppm, order = SC.pack(low, {nm: SHARES[nm.split('_')[0]] if nm.split('_')[0] in SHARES else
                                            SHARES.get(nm, 1.0) for nm in low['names']}, size=size, order=UV_ORDER,
                                      ppm=UV_PPM, log=log)
    L = SC.low_arrays(low, place, ppm, size)
    log(f'[face_mask] uv: {len(place)} primary islands of {len(low["names"])}; {ppm:.0f} px/m at {size} '
        f'({1000 / ppm:.3f} mm/texel), fill {fill * 100:.1f} %; order {order}')
    return L, low, info, dict(fill=fill, order=order, ppm=ppm)


def forge_bake(out_dir, size=2048, voxel_size=0.00025, band=0.0015, ss=2, seed=7, spec=SPEC, log=print):
    """block-out -> low + UVs -> voxel high (GPU) -> ONE bake for the mould; writes low_face_mask.npz and
    drivers_face_mask.npz (both faces' material passes read them)"""
    import os
    import time

    from .. import bake, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    L, low, info, uvr = make_low(size, spec, log=log)
    np.savez_compressed(os.path.join(out_dir, 'low_face_mask.npz'),
                        **{k: v for k, v in L.items() if isinstance(v, np.ndarray)}, px_per_m=L['px_per_m'],
                        size=L['size'], quad_part=low['part'], Q=low['Q'], parts=np.array(low['parts']))
    prog = build_sdf(spec)
    f = np.abs(prog.eval(L['V']))
    log(f'[face_mask] low on the block-out: |sdf| p50 {np.median(f) * 1e6:.0f} um, p99 '
        f'{np.percentile(f, 99) * 1e6:.0f} um, max {f.max() * 1e6:.0f} um')
    lo, hi = bounds(spec)
    G = voxel.SparseSDF(prog, lo, hi, voxel=voxel_size, band=band, log=log)
    pr = L['primary']
    res = bake.bake(G, L['V'], L['F'][pr], L['UV'], L['N'], L['TAN'], L['region'][pr], size=size, ss=ss, cage=0.004,
                    ao_r=0.02, cav_r=0.002, n_thk=2, thk_max=0.01, seed=seed, log=log,
                    region_names=dict(enumerate(REGIONS)))
    keep = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
            if k != 'position' and isinstance(v, np.ndarray)}
    np.savez_compressed(os.path.join(out_dir, 'drivers_face_mask.npz'), **keep)
    log(f'[face_mask] the bake is saved (drivers_face_mask.npz) after {time.time() - t0:.0f}s')
    return L


DELIVER_SIZE = 1024         # (11-11, OPTIMIZATION in soft_NOTES.md) the 2048 master sheet is 0.111 mm a texel, 3.9
#                             texels under a pixel of the closest view (0.43 mm); 1024 is 0.223 mm, 1.9 texels a pixel,
#                             a quarter of the GPU memory (85.3 -> 21.3 MiB a mask). The masters stay the bake's sheet


def export(out_dir, design, L, maps, spec=SPEC, conform=None, shapes=None, deliver=None):
    """deliver: the maps' delivered size (soft_common.deliver_maps; None: as given)"""
    import os
    name = DESIGNS[design]['name']
    return SC.export_glb(os.path.join(out_dir, f'{name}.glb'), name, L, maps, fit_data(design, spec, conform), ZONES,
                         'R fuzz / sheen amount (cloth only: the mesh, the elastic), G material (0 hard, 1/3 ribbed '
                         'elastic, 1 net), B palette zone (0 face, 1/3 inside + bare laminate + hardware, 2/3 ink + '
                         'trim + mesh, 1 strap); RGB, no alpha', 'mask', shapes=shapes, deliver=deliver)
