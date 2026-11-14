"""The TOP HAT: the first Bestiary accessory (DESIGN.md "Accessories"), built the forge way, at real size.

  profile -> block-out SDF:  the crown, tip, band and sweatband as ONE closed (r, y) profile REVOLVED about +Y
                             (work/bestiary/patches/sdf_revolve.md), unioned with the brim as a SHELL: the brim's
                             side roll (up at the sides, a slight flange dip front and back) is not a surface of
                             revolution
  -> the low:                quad rings revolved from the same profile, the brim's rings bent by the same roll, two
                             16 x 16 quad caps (the tip, the lining's tip): 2560 quads, 5120 triangles (study T's worn
                             top hat: 4858)
  -> UV islands:             top, crown side, band, brim upper, brim under, inner wall, inner tip (the inside at a
                             quarter of the density: hidden islands give their texels back)
  -> sculpt plan:            the binding's rolled edge, tension puckers where the side roll compresses it, the band's
                             flat half bow on the wearer's left (knot, loop, tail, gathers)
  -> voxel high + bake       (voxel.SparseSDF + bake.bake: GPU, driven as t10 drives them; forge() below)
  -> material pass:          felt (fibre-tuft relief, the brushed nap through roughness, the rim fuzz mask,
                             charcoal), grosgrain (a ribbed weave normal at 20 ribs per inch: band, bow, binding),
                             a leather sweatband, a silk lining
  -> a static glb carrying its FIT data (work/bestiary/patches/accessories_fit.md: the head opening, the seat frame,
     clearance probes)

Frame: metres, +Y up = the seat axis, the origin at the centre of the head opening on the SEAT PLANE (y = 0: the
opening's lower edge = the brim's underside at the crown), +Z forward (the wearer's face), +X the wearer's left (the
bow's side).

REQUIRES the REVOLVE patch (sdf.Program.revolve). The forge calls it makes:
  sdf.Program(); .revolve(profile, [0, 0, 0], [0, 1, 0], name=...); .shell(V, F, half_thickness, k=0.0, maxd=0.02,
    name='brim'); .eval(points); .project(points, dirs); .normals(points)
  mesh.QuadMesh; loft.cap(mesh, ring, axis); gates.quad_quality(mesh, prog)
  uv.islands, .split, .lscm, .arap, .self_overlap, .footprint, .island_density, .pack
  bake.low_frames(V, F, UV, N); bake.bake(field, V, F, UV, N, TAN, region, size=, ss=, cage=, ...); bake.dilate_all
  voxel.SparseSDF(prog, lo, hi, voxel=, band=, extra=plan.bounds(prog, band)); voxel.STROKE_CONE, .STROKE_CYL
  species.octopus_sculpt.Plan (.add, .bounds, .apply)
  material.low_at, .to_world, .to_tangent, .surface_grad, .mix3, .uv_bvh, .corner_arrays, .driver_arrays
  calib.relief_drivers(drivers, px_per_m); proc.fbm3, .noise3, .cellular3, .smoothstep
  gltf.GLB (.texture, .material, .mesh, .node, .save)

    prog = build_sdf();  low, info = build_low(prog=prog);  uvs = unwrap(low, info);  L = low_arrays(low, info, uvs)
    plan = plan_hat(prog);  G = SparseSDF(...); plan.apply(G);  res = bake.bake(G, ...)          (GPU)
    maps = run_material(L, res, size, 1 / px_per_m);  export_glb(path, L, maps)
    or all of it: forge('work/bestiary/props') (the runtime's default path for the prop: accessories_fit.md §7)

REAL-SIZE NUMBERS and their sources (SPEC):
  * the head opening 57 cm round (hat size 7 1/8, a men's medium): R_open 90.7 mm, circular in the glb (the fit's
    per-axis scale makes it each wearer's oval);
  * the crown 160 mm above the brim: V&A O356026 (Henry Heath, c.1850) crown height 17 cm; V&A O356044 (Christy's,
    London, c.1880) 19 cm overall with the side roll, its crown 17 x 19 cm across (here 18.6 cm round at the base);
  * the bell: "the crown spreads slightly at the top" (V&A O356044): a 1.3 % waist at 30 % of the height, a 3.2 % flare
    at the top (my reading of the record, not a measurement);
  * the brim 48 mm along its surface: V&A O356026 4 cm, Connecticut Historical Society (CHS) top hat 1856-1870 2 in;
    the roll tuned (work/bestiary/scratch_accessories/brim_roll_study.py) to V&A O356044's brim, 21 cm side to side and
    27.5 cm front to back, "very much rolled at the sides": here 28.1 cm front to back, the sides rolled up 27 mm;
  * the band 32 mm of grosgrain: museum hats run 1/2 in to 1 5/8 in (CHS records), 1 in the most common; a half bow on
    the wearer's left (CHS: "tied with a half bow on the proper left side");
  * the binding: 10 mm of ribbon folded over the edge (V&A O356026: ribbon width 1 cm, matching the band);
  * grosgrain at 20 ribs per inch (1.27 mm): standard grosgrain 18-22 RPI (Seek Ribbon), 8-20 RPI by grade (Bernard
    Hats). The felt's 1.2 mm, the sweatband's 45 x 1 mm and the ribs' 80 um relief are UNVERIFIED trade figures;
  * colours and felt statistics MEASURED from a shipped AAA top hat (study T, numbers only, nothing copied):
    MI_Headwear_Pickups_TopHat_001_M felt R COLOR linear 0.0573 (#434343), band G_COLOR 0.0208 (#272727), both
    roughness ~0.96 on the pickup; the worn hat's cloth layer (MI_ARK_CHAR_AC_Marketing_Oversuit_Hat_001): roughness
    low 0.7, fuzz Fresnel exponent 1.97, fuzz mask T_Char_DT_Pattern_Felt_001_M (B) p5 / p50 / p95 0.06 / 0.32 / 0.71,
    felt detail normal T_Char_DT_Pattern_Felt_001_N peaking at 0.64 mm wavelength (tiled x12 at 3033 px/m).
"""
import numpy as np
import warp as wp
from scipy.interpolate import PchipInterpolator

from .. import material as M
from .. import proc
from .. import sdf
from ..mesh import QuadMesh

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})   # forward-only; noise neighbour loops left rolled

SPEC = dict(
    head_circ=0.570,        # the head opening's circumference (m): hat size 7 1/8
    felt_t=0.0012,          # stiffened fur felt (UNVERIFIED trade figure)
    sweat_h=0.045,          # the leather sweatband's height and thickness (UNVERIFIED typical)
    sweat_t=0.0010,
    crown_h=0.160,          # the crown above the brim's top surface (V&A O356026 17 cm; O356044 19 cm with the roll)
    waist=0.013,            # the bell: in by `waist` at `waist_at` of the height, out by `flare` at the top
    waist_at=0.30,
    flare=0.032,
    taper=0.0,              # a linear taper on top of the bell (+ spreads, - narrows toward the tip)
    tip_r=0.003,            # the tip edge's outer radius
    tip_dome=0.0012,        # the tip's rise at its centre
    band_h=0.032,           # the grosgrain band's height and thickness
    band_t=0.0005,
    brim_w=0.048,           # the brim along its surface
    roll=125.0,             # the side roll: the brim's meridian turns up to `roll` degrees at the side edge, growing
    roll_p=1.6,             #   as (rho / W)^roll_p and concentrated at the sides as |sin phi|^roll_q
    roll_q=2.2,
    dip=7.0,                # the front/back flange: the meridian dips by up to `dip` degrees mid-brim
    curl=10.0,              # the all-round edge curl (degrees, over the outer 30 % of the brim)
    bind_w=0.005,           # the binding: a 10 mm ribbon folded over the edge, 5 mm on each face, 0.35 mm thick
    bind_t=0.00035,
    bead_r=0.0012,          # the binding's rolled edge (sculpt)
    reed_r=0.0005,          # the head opening's edge rounding
    stub=0.003,             # the crown profile's brim stub (buried inside the SHELL brim)
    bow_phi=90.0,           # degrees from +Z toward +X: the wearer's left
    knot_w=0.011,           # the half bow: the knot's width, the loop's and the tail's lengths along the band
    loop_l=0.026,
    tail_l=0.016,
)
K_LOW = 64                  # columns round the low (the back seam at column K / 2)
REGIONS = ('top', 'crown', 'band', 'brim_upper', 'brim_under', 'inner_wall', 'inner_tip')
SEAM_RINGS = ('tipc', 'bt', 'b0', 'e0', 'oc', 'ic')       # the rings between islands, in station order
BRIM_CUTS = tuple(4 + 8 * m for m in range(8))            # each brim face in 8 arcs, cut at 22.5 + 45 m degrees (off
                                                          # the front, back and side centre lines): a whole annulus
                                                          # packs as a C whose hole wastes half its box (t-smoke: 2414
                                                          # px/m at 2048)
INNER_SHARE = 0.25          # the inside's texel density relative to the outside

MATERIAL = dict(
    # linear colours: felt and band MEASURED on study T's top hat (#434343, #272727), nudged a hair warm / blue-black
    felt=(0.060, 0.057, 0.054),
    band=(0.020, 0.021, 0.024),
    binding=(0.020, 0.021, 0.024),
    leather=(0.33, 0.19, 0.095),          # a tan sweatband (sRGB ~0.61 0.48 0.35)
    silk=(0.62, 0.56, 0.44),              # an ivory lining
    ink=(0.55, 0.38, 0.12),               # the lining's printed gold oval
    # roughness: felt between study T's pickup (0.96) and its cloth layer's low end (0.7); the nap's streaks move it
    # +-nap ("the sheen through roughness"), handling polishes it by up to wear; grosgrain crests / valleys
    felt_rough=0.78, nap_rough=0.06, wear_rough=0.12, rib_rough=(0.50, 0.68), leather_rough=0.55, silk_rough=0.32,
    rib_pitch=0.00127,                    # 20 ribs per inch
    rib_amp=0.00008,                      # the weft cords' peak-to-valley relief (UNVERIFIED)
    felt_amp=0.000043,                    # the fibre tufts' height amplitude (tuned on CPU at 3343 px/m, ss 2: felt normal
                                          # XY RMS ~0.03, a pounced felt's quiet mm texture; the octopus's skin: 0.03-0.06)
    nap_amp=0.0000025,                    # (its 0.6 mm streaks fade below 3 texels: at 2048 the nap acts as roughness)
    cloud=0.05,                           # the felt's density cloud, ln L amplitude
    seed=31,
)


# ----------------------------------------------------------------------------------------------------- dimensions
def dims(spec=SPEC):
    R_open = spec['head_circ'] / (2.0 * np.pi)
    R0 = R_open + spec['sweat_t'] + spec['felt_t']          # the crown's outer radius at the base
    y0 = spec['felt_t']                                      # the brim's top surface at the crown
    y_edge = y0 + spec['crown_h']                            # the tip's top at its edge
    return dict(R_open=R_open, R0=R0, y0=y0, y_mid=0.5 * spec['felt_t'], y_edge=y_edge,
                y_c=y_edge - spec['tip_r'], y_bt=y0 + spec['band_h'])


def crown_radius(y, spec=SPEC):
    """the crown's OUTER radius at height y (the felt; the band adds band_t over it): the bell and the taper"""
    d = dims(spec)
    t = np.clip((np.asarray(y, np.float64) - d['y0']) / spec['crown_h'], 0.0, 1.0)
    w, f = spec['waist'], spec['flare']
    bell = PchipInterpolator([0.0, spec['waist_at'], 0.66, 1.0], [1.0, 1.0 - w, 1.0 - 0.35 * w + 0.25 * f, 1.0 + f])
    return d['R0'] * (bell(t) + spec['taper'] * t)


def _smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# -------------------------------------------------------------------------------------------- the crown's profile
def _seg(p, q, step):
    n = max(2, int(np.ceil(np.hypot(q[0] - p[0], q[1] - p[1]) / step)) + 1)
    t = np.linspace(0.0, 1.0, n)[:, None]
    return np.asarray(p, np.float64) * (1.0 - t) + np.asarray(q, np.float64) * t


def _arc(c, rad, a0, a1, step, turn=np.radians(2.0)):
    n = max(2, int(np.ceil(abs(a1 - a0) * rad / step)) + 1, int(np.ceil(abs(a1 - a0) / turn)) + 1)
    a = np.linspace(a0, a1, n)
    return np.column_stack([c[0] + rad * np.cos(a), c[1] + rad * np.sin(a)])


def _curve(f, t0, t1, step, turn=np.radians(2.0)):
    """a parametric curve f(t) -> (n, 2) resampled so every segment is <= step long and turns <= turn"""
    t = np.linspace(t0, t1, 4097)
    P = f(t)
    d = np.diff(P, axis=0)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(d, axis=1))])
    ang = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    a = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(ang))), [0.0]])[:len(s)]
    b = s / step + np.maximum.accumulate(a) / turn
    n = max(2, int(np.ceil(b[-1])) + 1)
    return f(np.interp(np.linspace(0.0, b[-1], n), b, t))


def _chain(parts):
    out = [np.asarray(parts[0], np.float64)]
    for p in parts[1:]:
        p = np.asarray(p, np.float64)
        out.append(p[1:] if np.allclose(p[0], out[-1][-1], rtol=0.0, atol=1e-10) else p)
    return np.concatenate(out)


def landmarks(spec=SPEC):
    d = dims(spec)
    Rc = float(crown_radius(d['y_c'], spec))
    return dict(Rc=Rc, rd=Rc - spec['tip_r'], R_bt=float(crown_radius(d['y_bt'], spec)))


def dome(r, spec=SPEC):
    """the tip's top surface height at radius r (a shallow dome down to the tip edge's start)"""
    d, lm = dims(spec), landmarks(spec)
    return d['y_edge'] + spec['tip_dome'] * (1.0 - (np.asarray(r, np.float64) / lm['rd']) ** 2)


def sweat_face(y, spec=SPEC):
    """the sweatband's face (the head opening's wall) at height y"""
    d = dims(spec)
    return crown_radius(np.maximum(y, d['y0']), spec) - spec['felt_t'] - spec['sweat_t']


def crown_profile(spec=SPEC, step=0.0004):
    """the crown, tip, band and sweatband as ONE closed (r, y) polygon for sdf.Program.revolve (metres): the tip's top
    from the axis, its rounded edge, the crown down (the bell), the band's rounded top edge and face, the brim stub
    (buried in the SHELL brim), the seat plane in to the head opening's rounded edge, the sweatband up to its rounded
    top, the felt's inner wall, the lining's tip back to the axis (the closing axis segment is not surface)"""
    d, lm = dims(spec), landmarks(spec)
    ft, tr, bt = spec['felt_t'], spec['tip_r'], spec['band_t']
    R0, y0, yc, ybt, sh = d['R0'], d['y0'], d['y_c'], d['y_bt'], spec['sweat_h']
    rd, R_bt = lm['rd'], lm['R_bt']
    hb, rr, hs = 0.5 * bt, spec['reed_r'], 0.5 * spec['sweat_t']
    swh = float(sweat_face(sh, spec))
    parts = [
        _curve(lambda t: np.column_stack([t, dome(t, spec)]), 0.0, rd, step),
        _arc([rd, yc], tr, np.pi / 2, 0.0, step),
        _curve(lambda y: np.column_stack([crown_radius(y, spec), y]), yc, ybt, step),
        _seg([R_bt, ybt], [R_bt + hb, ybt], step),
        _arc([R_bt + hb, ybt - hb], hb, np.pi / 2, 0.0, step),
        _curve(lambda y: np.column_stack([crown_radius(y, spec) + bt, y]), ybt - hb, y0, step),
        _seg([R0 + bt, y0], [R0 + spec['stub'], y0], step),
        _seg([R0 + spec['stub'], y0], [R0 + spec['stub'], 0.0], step),
        _seg([R0 + spec['stub'], 0.0], [d['R_open'] + rr, 0.0], step),
        _arc([d['R_open'] + rr, rr], rr, -np.pi / 2, -np.pi, step),
        _curve(lambda y: np.column_stack([sweat_face(y, spec), y]), rr, sh - hs, step),
        _arc([swh + hs, sh - hs], hs, np.pi, np.pi / 2, step),
        _seg([swh + hs, sh], [float(crown_radius(sh, spec)) - ft, sh], step),
        _curve(lambda y: np.column_stack([crown_radius(y, spec) - ft, y]), sh, yc, step),
        _arc([rd, yc], tr - ft, 0.0, np.pi / 2, step),
        _curve(lambda t: np.column_stack([t, dome(t, spec) - ft]), rd, 0.0, step),
    ]
    return _chain(parts)


# ------------------------------------------------------------------------------------------------------ the brim
def brim_theta(phi, rho, spec=SPEC):
    """the brim meridian's angle above the horizontal (radians) at azimuth phi and arc length rho: the side roll, the
    front/back flange dip, the all-round edge curl"""
    W = spec['brim_w']
    u = np.clip(np.asarray(rho, np.float64) / W, 0.0, 1.0)
    phi = np.asarray(phi, np.float64)
    S = np.abs(np.sin(phi)) ** spec['roll_q']
    C = np.cos(phi) ** 2
    return (S * np.radians(spec['roll']) * u ** spec['roll_p'] - C * np.radians(spec['dip']) * 4.0 * u * (1.0 - u)
            + np.radians(spec['curl']) * _smoothstep(0.7, 1.0, u))


def _meridian(phi, rho, spec, n=2048):
    """the meridian at azimuths phi (M,): its horizontal offset X and rise Y from the crown's base and its angle, at the
    arc lengths rho (N,) (negative rho: straight inward, inside the crown wall), each (M, N)"""
    W = spec['brim_w']
    g = np.linspace(0.0, W, n + 1)
    th = brim_theta(phi[:, None], g[None, :], spec)
    dx = 0.5 * (np.cos(th[:, 1:]) + np.cos(th[:, :-1])) * (W / n)
    dy = 0.5 * (np.sin(th[:, 1:]) + np.sin(th[:, :-1])) * (W / n)
    xg = np.concatenate([np.zeros((len(phi), 1)), np.cumsum(dx, 1)], 1)
    yg = np.concatenate([np.zeros((len(phi), 1)), np.cumsum(dy, 1)], 1)
    rc = np.clip(rho, 0.0, W)
    f = rc / (W / n)
    i0 = np.clip(np.floor(f).astype(np.int64), 0, n - 1)
    w = (f - i0)[None, :]
    X = xg[:, i0] * (1.0 - w) + xg[:, i0 + 1] * w
    Y = yg[:, i0] * (1.0 - w) + yg[:, i0 + 1] * w
    TH = brim_theta(phi[:, None], rc[None, :], spec)
    neg = rho < 0.0
    X[:, neg] = rho[neg][None, :]
    Y[:, neg] = 0.0
    TH[:, neg] = 0.0
    return X, Y, TH


def brim_frame(phi, rho, spec=SPEC):
    """the brim's MID-SURFACE at azimuths phi (M,) and arc lengths rho (N,) from the crown's outer wall at the base:
    positions P, unit normals N (the upper face's side) and meridian tangents T, each (M, N, 3)"""
    phi = np.atleast_1d(np.asarray(phi, np.float64))
    rho = np.atleast_1d(np.asarray(rho, np.float64))
    d = dims(spec)

    def pos(ph):
        X, Y, TH = _meridian(ph, rho, spec)
        rad = d['R0'] + X
        return np.stack([rad * np.sin(ph)[:, None], d['y_mid'] + Y, rad * np.cos(ph)[:, None]], -1), TH
    P, TH = pos(phi)
    T = np.stack([np.cos(TH) * np.sin(phi)[:, None], np.sin(TH), np.cos(TH) * np.cos(phi)[:, None]], -1)
    e = 1.0e-4
    Pphi = (pos(phi + e)[0] - pos(phi - e)[0]) / (2.0 * e)
    N = np.cross(T, Pphi)
    N /= np.linalg.norm(N, axis=-1, keepdims=True)
    return P, N, T


def half_thickness(rho, spec=SPEC):
    """the brim's half-thickness: the felt, plus the binding's ribbon on both faces over its last bind_w (a 0.6 mm
    ramp: a ribbon's edge is not a knife)"""
    e = spec['brim_w'] - spec['bind_w']
    return 0.5 * spec['felt_t'] + spec['bind_t'] * _smoothstep(e - 0.0003, e + 0.0003, rho)


def brim_patch(spec=SPEC, n_phi=1280, d_rho=0.0003, rho_in=0.001):
    """the brim's mid-surface as a closed ring of triangles for the SHELL: ~0.3 mm facets across (the roll's tightest
    radius ~11 mm turns 1.6 degrees per facet) and ~0.5 mm round (an offset thinner than its facets keeps them: the
    octopus web's lesson), its inner edge buried rho_in inside the crown's base. Returns V (n, 3), F (m, 3) and the
    per-vertex half-thickness"""
    W = spec['brim_w']
    rho = np.linspace(-rho_in, W, int(np.ceil((W + rho_in) / d_rho)) + 1)
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    P, N, T = brim_frame(phi, rho, spec)
    nr = len(rho)
    i = np.arange(n_phi)[:, None]
    j = np.arange(nr - 1)[None, :]
    a = i * nr + j
    b = ((i + 1) % n_phi) * nr + j
    F = np.concatenate([np.stack([a, b, b + 1], -1).reshape(-1, 3), np.stack([a, b + 1, a + 1], -1).reshape(-1, 3)])
    return P.reshape(-1, 3), F, np.tile(half_thickness(rho, spec), n_phi)


# ----------------------------------------------------------------------------------------------------- block-out
def build_sdf(spec=SPEC):
    """the block-out: REVOLVE (crown, tip, band, sweatband, lining) hard-unioned with the SHELL brim (their faces
    coincide over the buried stub: a smooth union would bulge them by k / 4 there)"""
    prog = sdf.Program()
    prog.revolve(crown_profile(spec), [0.0, 0.0, 0.0], [0.0, 1.0, 0.0], name='crown, tip, band, sweatband, lining')
    Vb, Fb, Hb = brim_patch(spec)
    prog.shell(Vb, Fb, Hb, k=0.0, maxd=0.02, name='brim')
    prog.hat = dict(spec=spec, dims=dims(spec), landmarks=landmarks(spec))
    return prog


def bounds(spec=SPEC, pad=0.006):
    """the voxel grid's box (the brim's dip and roll, the bow, the dome, plus pad)"""
    d = dims(spec)
    Rb = d['R0'] + spec['brim_w'] + 0.003
    return (np.array([-Rb, -0.010, -Rb]) - pad, np.array([Rb, d['y_edge'] + spec['tip_dome'] + 0.001, Rb]) + pad)


# ----------------------------------------------------------------------------------------------------------- low
def stations(spec=SPEC):
    """the low's rings in order, from the tip's cap ring down the outside, round the brim's bound edge, back under
    it, up the inside to the lining's cap ring: kind 'rev' (r, y), 'brim' (rho, side) or 'edge' (a: the angle round
    the bound edge from the upper face's normal: 0 the upper face, pi / 2 the apex, pi the under face)"""
    d, lm = dims(spec), landmarks(spec)
    ft, tr, bt, W = spec['felt_t'], spec['tip_r'], spec['band_t'], spec['brim_w']
    y0, yc, ybt, sh = d['y0'], d['y_c'], d['y_bt'], spec['sweat_h']
    rd, Rc, R_bt = lm['rd'], lm['Rc'], lm['R_bt']
    hb, rr, hs = 0.5 * bt, spec['reed_r'], 0.5 * spec['sweat_t']
    c45 = np.cos(np.pi / 4)
    S = []
    rev = lambda nm, r, y: S.append(dict(name=nm, kind='rev', r=float(r), y=float(y)))
    brim = lambda nm, rho, side: S.append(dict(name=nm, kind='brim', rho=float(rho), side=int(side)))
    rev('tip0', rd, d['y_edge'])
    rev('tipc', rd + tr * c45, yc + tr * c45)                                  # top | crown
    rev('tipw', Rc, yc)
    for k, f in enumerate((0.80, 0.52, 0.22)):
        y = ybt + f * (yc - ybt)
        rev(f'w{k}', crown_radius(y, spec), y)
    rev('bt', R_bt + hb + hb * c45, ybt - hb + hb * c45)                       # crown | band (its rounded top edge)
    rev('bs', crown_radius(y0 + 0.0015, spec) + bt, y0 + 0.0015)
    brim('b0', bt, +1)                                                          # band | brim upper (the band's foot)
    brim('u1', bt + 0.0015, +1)
    for k, u in enumerate((0.20, 0.42, 0.62, 0.78)):
        brim(f'u{k + 2}', u * W, +1)
    brim('ub', W - spec['bind_w'], +1)                                          # the binding's edge, upper
    brim('eu', W, +1)
    S.append(dict(name='e0', kind='edge', a=0.5 * np.pi))                       # brim upper | under (the edge's apex)
    brim('ed', W, -1)
    brim('db', W - spec['bind_w'], -1)
    for k, u in enumerate((0.78, 0.62, 0.42, 0.20)):
        brim(f'd{5 - k}', u * W, -1)
    brim('d1', 0.0020, -1)
    rev('os', d['R_open'] + 0.0012, 0.0)
    rev('oc', d['R_open'] + rr - rr * c45, rr - rr * c45)                      # brim under | inner (the reed)
    rev('ou', sweat_face(0.0012, spec), 0.0012)
    rev('st', float(sweat_face(sh, spec)) + hs - hs * c45, sh - hs + hs * c45)
    for k, f in enumerate((0.30, 0.70)):
        y = sh + f * (yc - sh)
        rev(f'i{k}', crown_radius(y, spec) - ft, y)
    rev('iw', Rc - ft, yc)
    rev('ic', rd + (tr - ft) * c45, yc + (tr - ft) * c45)                      # inner wall | inner tip
    rev('it0', rd, d['y_edge'] - ft)
    return S


def build_low(spec=SPEC, K=K_LOW, prog=None, log=print):
    """the designed quad low: one ring of K per station (columns at phi = 2 pi k / K, k = 0 forward, K / 2 the back),
    quads between consecutive rings, 16 x 16 quad caps on the first and last; each vertex sits on the block-out by
    construction (the revolve rings on the profile, the brim rings on the SHELL's offset of the same mid-surface).
    attrs['attr'] = (rho / W on the brim (1 on the edge), else -1; +1 upper / -1 under / 0; 0; 0). Returns the
    QuadMesh and an info dict (stations, ring ids, quad regions, the caps' grids)"""
    from .. import loft
    S = stations(spec)
    phi = 2.0 * np.pi * np.arange(K) / K
    W = spec['brim_w']
    rhos = sorted({st['rho'] for st in S if st['kind'] == 'brim'} | {W})
    P, N, T = brim_frame(phi, np.array(rhos), spec)
    col = {r: i for i, r in enumerate(rhos)}
    rings, attr = [], []
    for st in S:
        if st['kind'] == 'rev':
            pos = np.column_stack([st['r'] * np.sin(phi), np.full(K, st['y']), st['r'] * np.cos(phi)])
            a = (-1.0, 0.0)
        elif st['kind'] == 'brim':
            j = col[st['rho']]
            pos = P[:, j] + st['side'] * float(half_thickness(st['rho'], spec)) * N[:, j]
            a = (st['rho'] / W, float(st['side']))
        else:
            j = col[W]
            h = float(half_thickness(W, spec))
            pos = P[:, j] + h * (np.cos(st['a']) * N[:, j] + np.sin(st['a']) * T[:, j])
            a = (1.0, 0.0)
        rings.append(pos)
        attr.append(np.tile([a[0], a[1], 0.0, 0.0], (K, 1)))
    V = np.concatenate(rings)
    A4 = np.concatenate(attr)
    ids = np.arange(len(S) * K).reshape(len(S), K)
    k = np.arange(K)
    k1 = (k + 1) % K
    Q = np.concatenate([np.stack([ids[i, k], ids[i, k1], ids[i + 1, k1], ids[i + 1, k]], -1)
                        for i in range(len(S) - 1)])
    # the winding: the crown wall's quads face away from the axis (one strip: the rest follows)
    i_w = [st['name'] for st in S].index('tipw')
    qs = np.arange(i_w * K, (i_w + 1) * K)
    mesh = QuadMesh(V, Q, {'attr': A4})
    c = V[Q[qs]].mean(1)
    if (mesh.face_normals()[qs] * (c * [1.0, 0.0, 1.0])).sum() < 0.0:
        Q = Q[:, ::-1].copy()
        mesh = QuadMesh(V, Q, {'attr': A4})
    # the band regions (an island per region; the seam rings switch region)
    names = [st['name'] for st in S]
    reg_of_band, r = [], 0
    for i in range(len(S) - 1):
        if names[i] in SEAM_RINGS:
            r += 1
        reg_of_band.append(r)
    quad_region = np.repeat(reg_of_band, K)
    # the caps; their inner vertices onto the tip's dome and the lining's
    mesh, G_top = loft.cap(mesh, ids[0], [0.0, 1.0, 0.0])
    mesh, G_in = loft.cap(mesh, ids[-1], [0.0, -1.0, 0.0])
    for G, off in ((G_top, 0.0), (G_in, -spec['felt_t'])):
        inner = G[1:-1, 1:-1].ravel()
        rr = np.hypot(mesh.V[inner, 0], mesh.V[inner, 2])
        mesh.V[inner, 1] = dome(rr, spec) + off
    n_top = (G_top.shape[0] - 1) * (G_top.shape[1] - 1)       # loft.cap appends its s x t quads in order
    n_in = (G_in.shape[0] - 1) * (G_in.shape[1] - 1)
    quad_region = np.concatenate([quad_region, np.zeros(n_top, np.int64), np.full(n_in, len(REGIONS) - 1)])
    assert len(quad_region) == len(mesh.Q), (len(quad_region), len(mesh.Q))
    info = dict(stations=S, names=names, ids=ids, K=K, phi=phi, quad_region=quad_region, G_top=G_top, G_in=G_in)
    chk = mesh.check()
    log(f'[top_hat] low: {len(mesh.V)} verts, {len(mesh.Q)} quads ({2 * len(mesh.Q)} tris), {len(S)} rings x {K}; '
        f'check {chk}')
    if prog is not None:
        f = prog.eval(mesh.V)
        log(f'[top_hat] low on the block-out: |sdf| p50 {np.median(np.abs(f))*1e6:.1f} um, p99 '
            f'{np.percentile(np.abs(f), 99)*1e6:.1f} um, max {np.abs(f).max()*1e6:.1f} um')
    return mesh, info


# ----------------------------------------------------------------------------------------------------------- UVs
def _min_box(uv, steps=180):
    """the island turned to its minimum-area bounding box (LSCM leaves strips at an arbitrary angle; uv.pack only
    turns by 0 / 90 degrees)"""
    c = uv.mean(0)
    best = None
    for a in np.linspace(0.0, np.pi, steps, endpoint=False):
        Rm = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        q = (uv - c) @ Rm.T
        e = q.max(0) - q.min(0)
        if best is None or e[0] * e[1] < best[0]:
            best = (e[0] * e[1], q)
    return best[1] + c


def unwrap(low, info, size=2048, pad=8, arap_iters=8, log=print):
    """seams: the six rings between islands; down every annulus island the back column (k = K / 2), except the brim's
    two faces, cut into 8 arcs each (BRIM_CUTS); LSCM, then per island the ARAP depth with the smallest worst-direction
    footprint among those that lie flat (octopus_uv's rule), turned to its minimum-area box; one texel density for
    the set, the inside at INNER_SHARE; packed by uv.pack"""
    from .. import uv as U
    ids, K, names = info['ids'], info['K'], info['names']
    rows = [names.index(nm) for nm in SEAM_RINGS]
    seams = []
    for i in rows:
        seams += [(int(ids[i, k]), int(ids[i, (k + 1) % K])) for k in range(K)]
    kb = K // 2
    b0, b1 = names.index('b0'), names.index('oc')
    cuts = [round(c * K / 64) for c in BRIM_CUTS]
    for i in range(rows[0], rows[-1]):
        for k in (cuts if b0 <= i < b1 else [kb]):
            seams.append((int(ids[i, k]), int(ids[i + 1, k])))
    lab = U.islands(low.Q, seams)
    Vn, Qn, orig = U.split(low.V, low.Q, lab, seams)
    n_isl = int(lab.max()) + 1
    isl_reg = np.array([int(np.bincount(info['quad_region'][lab == i]).argmax()) for i in range(n_isl)])
    UVn = np.zeros((len(Vn), 2))
    dens, tris = {}, {}
    for i in range(n_isl):
        F = U._tri(Qn[lab == i])
        vs = np.unique(F)
        loc = -np.ones(len(Vn), np.int64)
        loc[vs] = np.arange(len(vs))
        Fl = loc[F]
        Pv = Vn[vs]
        uv = U.lscm(Pv, Fl)
        best, cand, done = None, uv, 0
        for it in (0, 2, max(arap_iters // 2, 3), arap_iters):
            if it > done:
                cand, done = U.arap(Pv, Fl, cand, it - done), it
            if U.self_overlap(cand, Fl):
                continue
            fp = U.footprint(Pv, Fl, cand)
            if best is None or fp < best[0]:
                best = (fp, it, cand)
        if best is None:
            log(f'[top_hat] uv island {i} ({REGIONS[isl_reg[i]]}): every ARAP depth folded it, LSCM kept')
            best = (U.footprint(Pv, Fl, uv), 0, uv)
        uv = best[2]
        d1, d2 = uv[Fl[:, 1]] - uv[Fl[:, 0]], uv[Fl[:, 2]] - uv[Fl[:, 0]]
        if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
            uv[:, 0] = -uv[:, 0]
        uv = _min_box(uv)
        UVn[vs] = uv
        dens[i] = U.island_density(Pv, Fl, uv)
        tris[i] = (vs, Fl, best[0], best[1])
    share = lambda i: INNER_SHARE if REGIONS[isl_reg[i]].startswith('inner') else 1.0
    area = 0.0
    for i in range(n_isl):
        vs, Fl = tris[i][0], tris[i][1]
        Pv = Vn[vs]
        a = 0.5 * np.linalg.norm(np.cross(Pv[Fl[:, 1]] - Pv[Fl[:, 0]], Pv[Fl[:, 2]] - Pv[Fl[:, 0]]), axis=1).sum()
        area += a * share(i) ** 2
    px_per_m = np.sqrt(0.55 * size * size / area)
    uvs = [UVn[tris[i][0]] for i in range(n_isl)]
    for _ in range(14):
        try:
            packed, used = U.pack(uvs, [px_per_m * share(i) / dens[i] for i in range(n_isl)], size, pad)
        except ValueError:
            used = 9.9
        if 0.93 <= used <= 0.985:
            break
        px_per_m *= (0.97 / used) ** 0.5 if used < 9.0 else 0.8
    while used > 1.0:
        px_per_m *= 0.97
        packed, used = U.pack(uvs, [px_per_m * share(i) / dens[i] for i in range(n_isl)], size, pad)
    for i, pk in enumerate(packed):
        UVn[tris[i][0]] = pk
    overl = sum(U.self_overlap(UVn[tris[i][0]], tris[i][1]) for i in range(n_isl))
    per = {}
    for i in range(n_isl):
        r_ = REGIONS[isl_reg[i]]
        n_, fpm, arm = per.get(r_, (0, 0.0, 0))
        per[r_] = (n_ + 1, max(fpm, tris[i][2]), max(arm, tris[i][3]))
    log(f'[top_hat] uv: {n_isl} islands: ' + ', '.join(f'{r_} x{n_} (worst footprint p95 {fpm:.2f}, ARAP <= {arm})'
                                                      for r_, (n_, fpm, arm) in per.items())
        + f'; {px_per_m:.0f} px/m at {size} ({1000 / px_per_m:.3f} mm/texel), height used {used * 100:.0f} %, '
          f'self-overlapping texels {overl}')
    return dict(V=Vn, Q=Qn, orig=orig, UV=UVn, label=lab, isl_reg=isl_reg, px_per_m=float(px_per_m), size=size,
                used=float(used))


def low_arrays(low, info, uvs):
    """the export's arrays: triangles along each quad's shorter diagonal (the split the bake and the export share),
    normals from the WELDED low, MikkT-style tangents, the region per triangle, ATTR per split vertex"""
    from .. import bake
    Vn, Qn, UVn, orig = uvs['V'], uvs['Q'], uvs['UV'], uvs['orig']
    d02 = np.linalg.norm(Vn[Qn[:, 0]] - Vn[Qn[:, 2]], axis=1)
    d13 = np.linalg.norm(Vn[Qn[:, 1]] - Vn[Qn[:, 3]], axis=1)
    short = d02 <= d13
    F = np.concatenate([np.where(short[:, None], Qn[:, [0, 1, 2]], Qn[:, [0, 1, 3]]),
                        np.where(short[:, None], Qn[:, [0, 2, 3]], Qn[:, [1, 2, 3]])])
    fq = np.concatenate([np.arange(len(Qn)), np.arange(len(Qn))])
    N, TAN = bake.low_frames(Vn, F, UVn, low.vertex_normals()[orig])
    ATTR = np.asarray(low.attrs['attr'], np.float64)[orig]
    return dict(V=Vn, F=F, UV=UVn, N=N, TAN=TAN, region=info['quad_region'][fq].astype(np.int32), ATTR=ATTR,
                orig=orig, px_per_m=uvs['px_per_m'], size=uvs['size'])


# --------------------------------------------------------------------------------------------------- sculpt plan
def band_point(phi, y, lift, spec=SPEC):
    """a point `lift` off the band's face at azimuth phi and height y, and the face's outward normal (radial: the
    bell tilts it ~1 degree, which the strokes' fillets absorb)"""
    phi = np.asarray(phi, np.float64)
    y = np.asarray(y, np.float64)
    phi, y, lift = np.broadcast_arrays(phi, y, np.asarray(lift, np.float64))
    rad = crown_radius(y, spec) + spec['band_t'] + lift
    n = np.stack([np.sin(phi), np.zeros_like(phi), np.cos(phi)], -1)
    return np.stack([rad * np.sin(phi), y, rad * np.cos(phi)], -1), n


def plan_hat(prog=None, spec=SPEC, rng=None, log=print):
    """the sculpt plan (tier S: features of ~0.5 mm and up, the sculpt brief's soft details: filleted at
    least their radius, depth well under it), every stroke placed analytically on the block-out:
      * the binding's ROLLED EDGE: capsules along the brim's edge, 1.2 mm radius against the bound edge's 0.95 mm
        half-thickness, a gentle unevenness along it;
      * TENSION PUCKERS on the binding's under face where the side roll compresses the ribbon (|sin phi|^q > 0.55);
      * the HALF BOW on the band at the wearer's left: a knot (flat pills, a convex face, two gathers), a loop toward
        the back (pinched at the knot, 2.7 mm proud at mid-length, a folded rounded end, its face bulged), a tail toward
        the front with a fishtail notch, three gathers fanning from the knot over the loop"""
    from ..species.octopus_sculpt import Plan
    from ..voxel import STROKE_CONE, STROKE_CYL
    rng = rng or np.random.default_rng(7)
    plan = Plan()
    d = dims(spec)
    W = spec['brim_w']
    # 1. the binding's rolled edge
    n = int(np.ceil(2.0 * np.pi * (d['R0'] + W) / 0.0002))
    phi = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    Pm, Nm, Tm = brim_frame(phi, [W - 0.00025], spec)
    A = Pm[:, 0]
    knots = rng.normal(0.0, 1.0, 40)                                # a gentle unevenness, periodic round the edge
    wob = 1.0 + 0.04 * np.interp(phi, np.linspace(0.0, 2.0 * np.pi, 41), np.append(knots, knots[0]))
    plan.add(STROKE_CONE, A, np.roll(A, -1, axis=0), spec['bead_r'] * wob, spec['bead_r'] * np.roll(wob, -1), 'add',
             0.0006, 'binding roll')
    # 2. tension puckers: where the roll curls the edge, the ribbon's inner edge has to shrink
    S = np.abs(np.sin(phi)) ** spec['roll_q']
    step = max(1, int(round(0.0025 / 0.0002)))
    pick = [i for i in range(0, n, step) if S[i] > 0.55]
    if pick:
        pp = phi[pick] + rng.normal(0.0, 0.0006 / (d['R0'] + W), len(pick))
        rr_ = np.array([W - spec['bind_w'] + 0.0004, W - 0.5 * spec['bind_w'] - 0.0006, W - 0.0016])
        P0, N0, _ = brim_frame(pp, rr_, spec)                          # three points on the face: the roll curves it
        depth = 0.00010 * np.clip((np.abs(np.sin(pp)) ** spec['roll_q'] - 0.55) / 0.45, 0.0, 1.0) + 0.00003
        rp = 0.00025
        off = half_thickness(rr_, spec)[None, :] + rp - depth[:, None]   # under face: outward is -N
        pts = P0 - N0 * off[..., None]
        for s0 in range(2):
            plan.add(STROKE_CONE, pts[:, s0], pts[:, s0 + 1], rp, rp, 'carve', 0.00015, 'binding pucker')
    # 3. the half bow
    pb = np.radians(spec['bow_phi'])
    Rb = float(crown_radius(d['y0'] + 0.5 * spec['band_h'], spec)) + spec['band_t']
    hk = 0.5 * spec['knot_w'] / Rb
    ylo, yhi = d['y0'] + 0.0003, d['y_bt'] + 0.0006
    ym, hh = 0.5 * (ylo + yhi), 0.5 * (yhi - ylo)
    ra = 0.0025
    gp = np.arange(pb - hk + ra / Rb, pb + hk - ra / Rb + 1e-9, 0.0008 / Rb)
    gy = np.arange(ylo + ra, yhi - ra + 1e-9, 0.0008)
    GP, GY = np.meshgrid(gp, gy, indexing='ij')
    tk = 0.0011 + 0.0004 * (1.0 - ((GP - pb) / hk) ** 2) - 0.0002 * ((GY - ym) / hh) ** 2
    a, nrm = band_point(GP.ravel(), GY.ravel(), -0.0003, spec)
    b, _ = band_point(GP.ravel(), GY.ravel(), tk.ravel(), spec)
    plan.add(STROKE_CYL, a, b, ra, 0.0006, 'add', 0.0004, 'bow knot')
    for off in (-0.007, 0.007):
        g = np.linspace(pb - hk + 0.001 / Rb, pb + hk - 0.001 / Rb, 12)
        lift = 0.0011 + 0.0004 * (1.0 - ((g - pb) / hk) ** 2) + 0.0002
        p, _ = band_point(g, ym + off, lift, spec)
        plan.add(STROKE_CONE, p[:-1], p[1:], 0.00035, 0.00035, 'carve', 0.0003, 'knot gather')
    # the loop, toward the back (phi increasing), starting under the knot
    s = np.arange(-0.0015, spec['loop_l'] + 1e-9, 0.0005)
    u = np.clip(s / spec['loop_l'], 0.0, 1.0)
    hl = spec['band_h'] * (0.62 + 0.38 * np.sin(np.pi * np.clip(u / 0.7, 0.0, 1.0) * 0.5)) - 0.002
    hl = hl * (1.0 - 0.15 * _smoothstep(0.85, 1.0, u))
    tl = 0.0007 + 0.0020 * np.sin(np.pi * u) ** 0.8
    pl = pb + hk + s / Rb
    a, _ = band_point(pl, ym, -0.0003, spec)
    b, _ = band_point(pl, ym, tl, spec)
    plan.add(STROKE_CYL, a, b, 0.5 * hl, 0.0007, 'add', 0.0004, 'bow loop')
    b2, _ = band_point(pl, ym, tl + 0.0004 * np.sin(np.pi * u), spec)
    plan.add(STROKE_CYL, a, b2, 0.28 * hl, 0.0007, 'add', 0.0004, 'bow loop bulge')
    # the tail, toward the front, with a fishtail notch
    s = np.arange(-0.0015, spec['tail_l'] + 1e-9, 0.0005)
    u = np.clip(s / spec['tail_l'], 0.0, 1.0)
    ht = spec['band_h'] * (0.78 - 0.08 * u) - 0.002
    tt = 0.0006 + 0.0006 * np.sin(np.pi * u * 0.8)
    pt = pb - hk - s / Rb
    a, _ = band_point(pt, ym, -0.0003, spec)
    b, _ = band_point(pt, ym, tt, spec)
    plan.add(STROKE_CYL, a, b, 0.5 * ht, 0.0006, 'add', 0.0004, 'bow tail')
    pe = pb - hk - spec['tail_l'] / Rb
    tip_c, _ = band_point(pe + 0.004 / Rb, ym, 0.0012, spec)
    for sgn in (-1.0, 1.0):
        corner, _ = band_point(pe - 0.0012 / Rb, ym + sgn * 0.5 * ht[-1], 0.0012, spec)
        plan.add(STROKE_CONE, tip_c, corner, 0.0012, 0.0012, 'carve', 0.0003, 'tail notch')
    # gathers fanning from the knot over the loop
    for off in (-0.007, 0.0, 0.007):
        sg = np.linspace(0.0005, 0.010 + 0.002 * rng.random(), 10)
        ug = sg / spec['loop_l']
        p, _ = band_point(pb + hk + sg / Rb, ym + off * (1.0 + 0.4 * ug), 0.0007 + 0.0020 * np.sin(np.pi * ug) ** 0.8
                          + 0.00015, spec)
        plan.add(STROKE_CONE, p[:-1], p[1:], 0.0004, 0.0004, 'carve', 0.0003, 'loop gather')
    log(f'[top_hat] plan: ' + ', '.join(f'{o["tag"]} {len(o["A"])}' for o in plan.ops))
    return plan


# ------------------------------------------------------------------------------------------------- material pass
@wp.struct
class Cloth:
    h: float            # the texture tier's height (m)
    mat: int            # 0 felt, 1 grosgrain, 2 leather, 3 silk
    rib: float          # grosgrain: 1 on a weft cord's crest, 0 in the valley
    nap: float          # felt: the brushed nap's streak value (about -1..1)
    fuzz: float         # the runtime's fuzz / sheen amount
    cloud: float        # felt: its density cloud (ln L)
    zone: float         # the palette zone: 0 felt, 1/3 band and bow, 2/3 binding, 1 inside
    wear: float         # felt: handling polish
    ink: float          # silk: the printed oval


@wp.func
def _wrap_pi(a: float):
    return a - 6.283185307 * wp.floor((a + 3.141592654) / 6.283185307)


@wp.func
def _table(t: wp.array(dtype=wp.float32), u: float):
    n = t.shape[0]
    x = wp.clamp(u, 0.0, 1.0) * float(n - 1)
    i = wp.min(int(x), n - 2)
    f = x - float(i)
    return t[i] * (1.0 - f) + t[i + 1] * f


@wp.func
def cloth_at(p: wp.vec3, reg: int, rho_n: float, texel: float, Wb: float, bind_lo: float, sweat_h: float,
             bow_phi: float, knot_half: float, r_band: float, pitch: float, rib_amp: float, felt_amp: float,
             nap_amp: float, cloud_amp: float, edge_s: wp.array(dtype=wp.float32), seed: int):
    out = Cloth()
    phi = wp.atan2(p[0], p[2])
    r = wp.sqrt(p[0] * p[0] + p[2] * p[2])
    mat = int(0)
    zone = float(0.0)
    if reg == 2:
        mat = 1
        zone = 1.0 / 3.0
    if (reg == 3 or reg == 4) and rho_n > bind_lo:
        mat = 1
        zone = 2.0 / 3.0
    if reg == 5:
        mat = 3
        zone = 1.0
        if p[1] < sweat_h:
            mat = 2
    if reg == 6:
        mat = 3
        zone = 1.0
    h = float(0.0)
    rib = float(0.0)
    nap = float(0.0)
    fuzz = float(0.0)
    cloud = float(0.0)
    wear = float(0.0)
    ink = float(0.0)
    if mat == 0:
        # fibre tufts, three octaves 2.4 / 1.2 / 0.6 mm (study T's felt detail peaks at 0.64 mm), each faded below ~3
        # texels (finer fibres are roughness, Toksvig's job)
        lam = float(0.0024)
        amp = float(1.0)
        for k in range(3):
            fo = proc.smoothstep(2.5, 4.0, lam / texel)
            h = h + felt_amp * amp * fo * proc.noise3(p / lam, seed + 11 + k)
            lam = lam * 0.5
            amp = amp * 0.7
        # the brushed nap: streaks 4 mm along the circumference, 0.6 mm across it, on a circle (no seam); across = the
        # height on the crown, the radius on the tip, rho on the brim
        across = p[1]
        if reg == 0:
            across = r
        if reg == 3 or reg == 4:
            across = rho_n * Wb
        q = wp.vec3(across / 0.0006, 0.11 * wp.cos(phi) / 0.004, 0.11 * wp.sin(phi) / 0.004)
        nap = proc.fbm3(q, 2, 2.0, 0.5, seed + 23)
        h = h + nap_amp * nap * proc.smoothstep(2.5, 4.0, 0.0006 / texel)
        cloud = cloud_amp * 4.0 * (0.6 * proc.fbm3(p / 0.02, 3, 2.0, 0.5, seed + 31)
                                   + 0.4 * proc.noise3(p / 0.006, seed + 37))
        # (study T's felt fuzz mask: p5 / p50 / p95 0.06 / 0.32 / 0.71)
        fuzz = wp.clamp(0.33 + 0.9 * proc.fbm3(p / 0.0035, 3, 2.0, 0.5, seed + 41), 0.0, 1.0)
        # handling polish: a top hat is lifted by the brim's front and back
        if reg == 3 or reg == 4:
            cf = wp.cos(phi)
            wear = proc.smoothstep(0.70, 0.95, rho_n) * cf * cf * (0.6 + 0.4 * proc.fbm3(p / 0.008, 2, 2.0, 0.5,
                                                                                        seed + 43))
    elif mat == 1:
        x = float(0.0)
        if reg == 2:
            dphi = phi - bow_phi
            dphi = dphi - 6.283185307 * wp.floor(dphi / 6.283185307)    # 0..2 pi: the ribbon's ends under the knot
            x = dphi * r_band / pitch
            if wp.abs(_wrap_pi(phi - bow_phi)) < knot_half:
                x = p[1] / pitch                                          # the knot's ribbon wraps vertically
        else:
            x = _table(edge_s, (phi + 3.141592654) / 6.283185307) / pitch  # along the edge from the back
        c = 0.5 + 0.5 * wp.cos(6.283185307 * x)
        rib = wp.pow(c, 0.6)
        h = rib_amp * (rib - 0.6) * proc.smoothstep(2.5, 4.0, pitch / texel)
        fuzz = 0.15
    elif mat == 2:
        cl = proc.cellular3(p / 0.0011, 0.9, seed + 51)
        g = proc.smoothstep(0.0, 0.18, cl.edge)
        h = 0.00002 * (g - 0.5) * proc.smoothstep(2.5, 4.0, 0.0011 / texel)
        # the stitch line 4 mm above the opening's edge, 3 mm stitches
        st = r * phi / 0.003
        st = st - wp.floor(st)
        sl = (1.0 - proc.smoothstep(0.00025, 0.0004, wp.abs(p[1] - 0.004))) * proc.smoothstep(0.15, 0.25, st) * (
            1.0 - proc.smoothstep(0.75, 0.85, st))
        h = h - 0.00005 * sl
        rib = g
        fuzz = 0.05
    else:
        if reg == 6:
            ink = 1.0 - proc.smoothstep(0.00045, 0.00075, wp.abs(r - 0.031))
    out.h = h
    out.mat = mat
    out.rib = rib
    out.nap = nap
    out.fuzz = fuzz
    out.cloud = cloud
    out.zone = zone
    out.wear = wear
    out.ink = ink
    return out


@wp.kernel
def k_hat(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
          ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32),
          d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_cav: wp.array(dtype=wp.float32),
          d_hgt: wp.array(dtype=wp.float32), d_base: wp.array(dtype=wp.vec4), d_aol: wp.array(dtype=wp.float32),
          d_convm: wp.array(dtype=wp.float32), edge_s: wp.array(dtype=wp.float32), C: wp.array(dtype=wp.vec3),
          R: wp.array(dtype=wp.float32), texel: float, Wb: float, bind_lo: float, sweat_h: float, bow_phi: float,
          knot_half: float, r_band: float, pitch: float, rib_amp: float, felt_amp: float, nap_amp: float,
          cloud_amp: float, seed: int, o_alb: wp.array(dtype=wp.vec3), o_nrm: wp.array(dtype=wp.vec3),
          o_orm: wp.array(dtype=wp.vec3), o_mask: wp.array(dtype=wp.vec4)):
    tid = wp.tid()
    x = tid % size
    y = tid // size
    dn = d_nrm[tid]
    if dn[3] <= 0.0:
        return
    tn_b = wp.normalize(wp.vec3(dn[0], dn[1], dn[2]))
    hgt = d_hgt[tid]
    base = d_base[tid]
    inv = 1.0 / float(ss)
    dlt = 0.5 * inv
    acc_a = wp.vec3(0.0)
    acc_n = wp.vec3(0.0)
    acc_r = float(0.0)
    acc_ao = float(0.0)
    acc_m = wp.vec4(0.0)
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
            cl = cloth_at(pb0, reg, lo.attr[0], texel, Wb, bind_lo, sweat_h, bow_phi, knot_half, r_band, pitch,
                          rib_amp, felt_amp, nap_amp, cloud_amp, edge_s, seed)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1:
                pbx = lx.p + lx.n * hb
                pby = ly.p + ly.n * hb
                hx = cloth_at(pbx, reg, lx.attr[0], texel, Wb, bind_lo, sweat_h, bow_phi, knot_half, r_band, pitch,
                              rib_amp, felt_amp, nap_amp, cloud_amp, edge_s, seed).h
                hy = cloth_at(pby, reg, ly.attr[0], texel, Wb, bind_lo, sweat_h, bow_phi, knot_half, r_band, pitch,
                              rib_amp, felt_amp, nap_amp, cloud_amp, edge_s, seed).h
                g = M.surface_grad(pb0, pbx, pby, cl.h, hx, hy)
            nw = M.to_world(lo, tn_b)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            aol = d_aol[tid]
            convm = d_convm[tid]
            col = wp.vec3(0.0)
            rough = float(0.5)
            if cl.mat == 0:
                # charcoal felt: the density cloud and the local AO in ln L (cloth crevices darker, gently)
                col = C[0] * wp.exp(cl.cloud + 0.8 * aol + 0.04 * convm)
                # the sheen through roughness: the nap lying flat (its streaks' crests) is smoother; handling polishes
                rough = R[0] - R[1] * proc.smoothstep(-0.1, 0.5, cl.nap) + 0.5 * R[1] * proc.smoothstep(0.1, -0.5,
                                                                                                   cl.nap)
                rough = rough - R[2] * cl.wear
            elif cl.mat == 1:
                cb = C[1]
                if cl.zone > 0.5:
                    cb = C[2]
                col = cb * (0.92 + 0.08 * cl.rib) * wp.exp(0.5 * aol)
                rough = R[4] + (R[3] - R[4]) * cl.rib
            elif cl.mat == 2:
                col = C[3] * (0.90 + 0.10 * cl.rib) * wp.exp(1.0 * aol)
                rough = R[5] + 0.06 * (cl.rib - 0.5)
            else:
                col = M.mix3(C[4], C[5], cl.ink) * wp.exp(0.5 * aol)
                rough = R[6] + (0.45 - R[6]) * cl.ink
            acc_a = acc_a + col
            acc_r = acc_r + wp.clamp(rough, 0.04, 1.0)
            acc_ao = acc_ao + d_ao[tid]
            acc_m = acc_m + wp.vec4(cl.fuzz, float(cl.mat) / 3.0, cl.zone, cl.wear)
            hits = hits + 1
    if hits == 0:
        return
    fh = float(hits)
    # Toksvig (craft guide 00.48, 11.44): the averaged normal's lost length widens the highlight
    ln = wp.length(acc_n) / fh
    var = wp.clamp((1.0 - ln) / wp.max(ln, 1.0e-4), 0.0, 1.0)
    rr = acc_r / fh
    a = rr * rr
    rr = wp.sqrt(wp.sqrt(a * a + var))
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    o_orm[tid] = wp.vec3(acc_ao / fh, wp.clamp(rr, 0.0, 1.0), 0.0)
    o_mask[tid] = acc_m / fh


def edge_table(spec=SPEC, n=1025):
    """the brim edge's arc length from the back (phi = -pi) round to the back again (the binding's rib coordinate)"""
    phi = np.linspace(-np.pi, np.pi, n)
    P, _, _ = brim_frame(phi, [spec['brim_w']], spec)
    seg = np.linalg.norm(np.diff(P[:, 0], axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)]).astype(np.float32)


def run_material(low, drivers, size, texel, spec=SPEC, ss=2, recipe=MATERIAL, log=print):
    """the material pass over the hat's texture set. low: low_arrays(); drivers: the bake's result (image order).
    Returns image-order uint8 maps: albedo (sRGB), normal (GL), orm (AO, roughness, metalness 0), masks (R fuzz /
    sheen, G material id / 3, B palette zone, A handling wear), and palette_base (the zones' mean linear albedo, for
    the runtime's recolour)"""
    import time
    from .. import calib
    from ..bake import dilate_all
    t0 = time.time()
    uvm = M.uv_bvh(low['F'], low['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(low['V'], low['F'], low['N'], low['TAN'], low['ATTR'])
    D = M.driver_arrays({**drivers, **calib.relief_drivers(drivers, 1.0 / texel)})
    d = dims(spec)
    W = spec['brim_w']
    Rb = float(crown_radius(d['y0'] + 0.5 * spec['band_h'], spec)) + spec['band_t']
    C = wp.array(np.array([recipe['felt'], recipe['band'], recipe['binding'], recipe['leather'], recipe['silk'],
                           recipe['ink']], np.float32), dtype=wp.vec3)
    R = wp.array(np.array([recipe['felt_rough'], recipe['nap_rough'], recipe['wear_rough'], recipe['rib_rough'][0],
                           recipe['rib_rough'][1], recipe['leather_rough'], recipe['silk_rough']], np.float32),
                 dtype=wp.float32)
    n = size * size
    o_alb = wp.zeros(n, dtype=wp.vec3)
    o_nrm = wp.zeros(n, dtype=wp.vec3)
    o_orm = wp.zeros(n, dtype=wp.vec3)
    o_mask = wp.zeros(n, dtype=wp.vec4)
    wp.launch(k_hat, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
                                    wp.array(np.asarray(low['region'], np.int32), dtype=wp.int32), D['normal'],
                                    D['ao'], D['cavity'], D['height'], D['base'], D['ao_local'], D['conv_mid'],
                                    wp.array(edge_table(spec), dtype=wp.float32), C, R, float(texel), float(W),
                                    float(1.0 - spec['bind_w'] / W), float(spec['sweat_h']),
                                    float(np.radians(spec['bow_phi'])), float(0.5 * spec['knot_w'] / Rb), float(Rb),
                                    float(recipe['rib_pitch']), float(recipe['rib_amp']), float(recipe['felt_amp']),
                                    float(recipe['nap_amp']), float(recipe['cloud']), int(recipe['seed']),
                                    o_alb, o_nrm, o_orm, o_mask])
    wp.synchronize()
    cov = np.asarray(drivers['normal'])[..., 3] > 0
    img = lambda a, k: np.asarray(a.numpy()).reshape(size, size, k)[::-1]
    alb, nrm, orm, msk = img(o_alb, 3), img(o_nrm, 3), img(o_orm, 3), img(o_mask, 4)
    zone = np.rint(msk[..., 2] * 3.0).astype(int)
    pal = {}
    for zi, nm in enumerate(('felt', 'band', 'binding', 'inside')):
        sel = cov & (zone == zi)
        if sel.sum() > 16:
            pal[nm] = [float(x) for x in np.median(alb[sel], axis=0)]
    dil, grown = dilate_all(dict(normal=np.concatenate([nrm, cov[..., None].astype(np.float32)], -1), alb=alb,
                                 orm=orm, msk=msk), 16)
    alb_s = M.srgb_oetf(np.where(grown[..., None], dil['alb'], 0.05))
    nrm_t = np.where(grown[..., None], dil['normal'][..., :3], [0.0, 0.0, 1.0])
    out = dict(albedo=(alb_s * 255 + 0.5).astype(np.uint8),
               normal=np.clip((nrm_t * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8),
               orm=np.clip(np.where(grown[..., None], dil['orm'], [1.0, 0.8, 0.0]) * 255 + 0.5, 0, 255).astype(np.uint8),
               masks=np.clip(np.where(grown[..., None], dil['msk'], 0.0) * 255 + 0.5, 0, 255).astype(np.uint8),
               palette_base=pal)
    log(f'[top_hat] material {size}^2 x ss {ss}: {time.time() - t0:.1f}s; palette base (linear) '
        + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in pal.items()))
    return out


# ------------------------------------------------------------------------------------------------------ fit data
def fit_data(spec=SPEC, n_probe=32):
    """what accessories_fit.md's seat solver and the runtime need from the hat (prop space, metres): the seat frame,
    the head opening (semi-axes on the seat plane), the crown's inner ceiling (the head may rise this far), the
    brim's extents, and clearance probes (the brim's underside at three widths and the opening's rim)"""
    d, lm = dims(spec), landmarks(spec)
    W = spec['brim_w']
    phi = np.linspace(0.0, 2.0 * np.pi, n_probe, endpoint=False)
    rho = np.array([0.25 * W, 0.6 * W, W])
    P, N, _ = brim_frame(phi, rho, spec)
    under = P - half_thickness(rho, spec)[None, :, None] * N
    opening = np.column_stack([d['R_open'] * np.sin(phi), np.zeros_like(phi), d['R_open'] * np.cos(phi)])
    Pe, Ne, Te = brim_frame(np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False), [W], spec)
    he = float(half_thickness(W, spec))
    edge = Pe[:, 0] + he * Te[:, 0]
    r_edge = np.hypot(edge[:, 0], edge[:, 2])
    rnd = lambda a: np.round(np.asarray(a, np.float64), 5).tolist()
    return dict(archetype='hat', prop='top_hat',
                seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0], left=[1.0, 0.0, 0.0]),
                opening=dict(rx=round(d['R_open'], 5), rz=round(d['R_open'], 5), y=0.0,
                             circumference=spec['head_circ']),
                crown_inner_height=round(d['y_edge'] - spec['felt_t'], 5),
                crown_outer=dict(r_base=round(d['R0'], 5), r_top=round(lm['Rc'], 5),
                                 height=round(d['y_edge'] + spec['tip_dome'], 5)),
                brim=dict(width=W, y_min=round(float((Pe[:, 0, 1] - he).min()), 5),
                          y_max=round(float(edge[:, 1].max() + he), 5), r_front=round(float(r_edge[0]), 5),
                          r_side=round(float(r_edge[90]), 5)),
                bow_side='+X',
                probes=dict(brim_under=rnd(under.reshape(-1, 3)), opening=rnd(opening)))


# -------------------------------------------------------------------------------------------------------- export
def export_glb(path, low, maps, spec=SPEC):
    """a static glb: one mesh, one material (base, normal, ORM; the masks in KHR_materials_volume's thickness slot as
    the creatures carry theirs), the fit data in the root node's and the file's extras"""
    from .. import gltf
    g = gltf.GLB()
    t_base = g.texture(maps['albedo'], fmt='jpeg', quality=94)
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='jpeg', quality=94)
    t_msk = g.texture(maps['masks'], fmt='png')
    mat = g.material('top_hat', base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='prop', prop='top_hat', masks=t_msk,
        masks_channels='R fuzz / sheen amount, G material (0 felt, 1/3 grosgrain, 2/3 leather, 1 silk), B palette '
                       'zone (0 felt, 1/3 band and bow, 2/3 binding, 1 inside), A handling wear',
        palette_base=maps.get('palette_base', {})))
    mesh = g.mesh('top_hat', low['V'], low['N'], low['TAN'], low['UV'], [(low['F'], mat)])
    fit = fit_data(spec)
    g.node('top_hat', mesh=mesh, root=True, extras=dict(bestiary='prop', fit=fit))
    return g.save(path, extras=dict(bestiary=dict(prop='top_hat', archetype='hat', units='m', up='+Y', forward='+Z',
                                                  left='+X', triangles=int(len(low['F'])), fit=fit)))


# --------------------------------------------------------------------------------------------- the whole forge
def forge(out_dir, size=2048, voxel_size=0.00025, band=0.0015, ss=2, seed=7, spec=SPEC, log=print):
    """block-out -> low (+ gates) -> UVs -> plan -> voxel high (GPU) -> bake (GPU) -> material -> glb; returns the
    glb's path. The heavy steps are one at a time (SparseSDF ~50M voxels at 0.25 mm: a CPU Monte Carlo estimate,
    44.8M in the band and 4.8M more inside the plan's 5092 stroke spheres; the bake at 2048 x ss 2)"""
    import os
    import time

    from PIL import Image

    from .. import bake, gates, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    prog = build_sdf(spec)
    low, info = build_low(spec, prog=prog, log=log)
    q, txt = gates.quad_quality(low, prog, region_names=None)
    log('[top_hat] gates:\n' + txt)
    uvs = unwrap(low, info, size=size, log=log)
    L = low_arrays(low, info, uvs)
    plan = plan_hat(prog, spec, np.random.default_rng(seed), log=log)
    lo, hi = bounds(spec)
    G = voxel.SparseSDF(prog, lo, hi, voxel=voxel_size, band=band, extra=plan.bounds(prog, band), log=log)
    plan.apply(G, log=log)
    res = bake.bake(G, L['V'], L['F'], L['UV'], L['N'], L['TAN'], L['region'], size=size, ss=ss, cage=0.006,
                    ao_r=0.02, cav_r=0.002, n_thk=2, thk_max=0.01, seed=seed, log=log)
    keep = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
            if k != 'position'}
    np.savez_compressed(os.path.join(out_dir, 'drivers_top_hat.npz'), **keep)
    maps = run_material(L, res, size, 1.0 / L['px_per_m'], spec, ss=ss, log=log)
    for k in ('albedo', 'normal', 'orm', 'masks'):
        Image.fromarray(maps[k]).save(os.path.join(out_dir, f'T_top_hat_{k}.png'))
    path = os.path.join(out_dir, 'top_hat.glb')
    n = export_glb(path, L, maps, spec)
    log(f'[top_hat] wrote {path} ({n / 1e6:.1f} MB) in {time.time() - t0:.0f}s')
    return path
