"""The HARD HAT: a worker's cap-style hard hat (ROADMAP B5; Skye, 11-11: "also a hardhat! like a worker hardhat"),
built at real size the forge way (top_hat.py's stages; cowboy_hat.py's authored low, stacked UVs and fit contract:
work/bestiary/accessories_b5/slice_NOTES.md THE RECIPE; this prop's log: accessories_b5/hard_NOTES.md).

THE OBJECT (accessories_b5/hard_hat/refs_photos/SOURCES.txt; the board of three candidates is in the showcase): the
RIBBED CAP-STYLE hard hat: an injection-moulded shell with three ribs front to back over the crown, a rain gutter
rolled up round the rim, a short peak in front, an accessory slot at each side and four bosses that hold the
suspension's keys; inside it a 4-point suspension (a pin-lock headband with a brow pad, two webbing straps crossing
over the crown, four hangers) and a chin-strap lug under each front boss. Safety yellow; white and orange are
material variants of the same maps (MATERIAL / VARIANTS).

  parts -> block-out SDF:  the SHELL (one SHELL primitive over its mid-surface: the dome, a superellipse meridian
                           over an elliptical plan, the ribs a lift along its normal, then the flange: fillet, floor,
                           the lip rolled up; the flange is the gutter all round and widens to the peak in front),
                           the bosses and the slot shelves (round boxes, blended once), the suspension (SHELLs over
                           strips, round boxes), the lugs
  -> the low:              AUTHORED (WORKING_RULES 2): a cube-sphere layout: a 12 x 12 grid cap whose lines lie ON the
                           ribs' crests and feet, rings from it down to the waist whose front and back columns carry
                           the ribs on, the flange's rings, the inside; the bosses are extruded from the shell's own
                           quads; the suspension's strips
  -> UVs, voxel high + bake, material pass, a static glb with its FIT data (top_hat's contract)

Frame: metres, +Y up = the seat axis, the origin at the centre of the head opening on the SEAT PLANE (y = 0: the
lower edge of the headband and its brow pad), +Z forward (the wearer's face, the peak), +X the wearer's left. `a` is
the plan PARAMETER angle from +Z toward +X: a point of the waist is (rx sin a, y, rz cos a).

NUMBERS and their sources (SPEC; [C] published, [M] measured on the photo through a [C] scale, [E] estimate):
  * the shell 280 x 220 mm over its peak and gutter, 2-4 mm of ABS [C: a maker's product sheet for a cap-style ABS
    hard hat, accessories_b5/hard_hat/refs_docs/: "Dimensions: 28 cm x 22 cm x 15.2 cm", "Shell thickness: 2 - 4 mm",
    "Weight: 358 gm", a 4-point suspension of HDPE and nylon, "Suspension adjust sizing: 6.5 - 8"];
  * the headband set at 570 mm (hat size 7 1/8, the other hats' [C]), inside its 6 1/2 - 8 range;
  * everything tagged [M]: read off the reference photo through a fitted pinhole camera with the rim held at
    280 x 220 mm (accessories_b5/hard_hat/scripts/m05_fit_photo.py prints "my constant | the photo").
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})   # forward-only; noise neighbour loops left rolled

SPEC = dict(
    length=0.280,           # over the peak's tip and the back gutter's lip [C]
    width=0.220,            # over the gutter's lips at the sides [C]
    height=0.127,           # from the rim plane (the flange's under face where it leaves the wall) to the centre rib's
    #                         crest [M: the photo's outline at the published length and width: three fits gave 0.124,
    #                         0.126, 0.128. The maker's sheet says 15.2 cm for ITS hat (with its suspension hanging
    #                         under the shell): at 0.152 the model stood 25 px rms (5 mm) off the photo's outline and
    #                         its clay read as a taller, narrower dome than the photographed hat; at 0.127: 9 px]
    shell_t=0.0025,         # the ABS wall [C: 2 - 4 mm]
    head_circ=0.570,        # the headband as set: hat size 7 1/8 [C: adjustable 6 1/2 - 8]
    open_ratio=1.22,        # its length / width [E: between a hatter's regular oval (1.2) and the ANSUR mean head]
    y_rim=-0.008,           # the rim plane under the seat plane: the shell hangs this far below the headband's lower
    #                         edge [E]
    # ---- the dome (its MID-surface; the plan an ellipse)
    dome_p=2.15,            # the meridian's superellipse exponent: 2 an ellipsoid, larger a squarer shoulder [M: the
    #                         photo's fits gave 2.04 - 2.25]
    # ---- the ribs: a lift along the dome's normal: [0] the centre rib, [1] the two side ribs at x = +- rib_x on the
    #      crown; flat-topped bands (the photo: each rib shows a highlight line along BOTH its edges)
    rib_h=(0.0030, 0.0026),         # heights [M-eye]
    rib_x=0.028,                    # the side ribs' distance from the midplane at the crown [M: the fits 0.025 - 0.035]
    rib_conv=0.300,                 # the side ribs CONVERGE toward the front and the back (the photo: they close in on
    #                                 the centre rib over the brow): their distance goes as (yy + this) / (H + this),
    #                                 yy the height over the waist: 28 mm on the crown, 23 where they die out [M-eye;
    #                                 no closer: the grooves between the ribs keep 3.7 mm of floor for the low's lines]
    rib_top=(0.006, 0.005),         # half-width of the flat crest [M-eye]
    rib_foot=(0.010, 0.009),        # half-width at the foot [M-eye]
    rib_fade=(0.038, 0.062),        # the ribs die out between these heights above the waist [M-eye]
    # ---- the flange: the gutter all round, the peak in front
    gutter_w=0.016,         # plan width from the dome's outer wall to the lip's outer edge [M: the photo's near side
    #                         shows 15 - 18 mm between the bosses' feet and the lip; the fits gave 15 - 22]
    peak_w=0.038,           # the same at the front's middle [M: the fits 0.031 - 0.036; by eye 2.5 gutters]
    peak_a=(34.0, 72.0),    # the peak's window: full inside the first angle from the front, gone by the second [M-eye]
    gutter_slope=4.0,       # the floor's fall outward (degrees) round the gutter and across the peak [M-eye; the fits
    peak_slope=18.0,        #   asked 21 - 25 for the peak]
    fillet_r=0.004,         # the mid-surface's radius where the wall turns out into the floor [E]
    lip_r=0.003,            # the lip: the floor rolled up by lip_turn degrees on this radius, then lip_l straight [M-eye]
    lip_turn=62.0,
    lip_l=0.0015,
    # ---- the bosses (the suspension's key sockets: front and rear on each side) and the accessory slot's shelf
    boss_a=(54.0, 126.0),   # their plan parameter angles from the front, each side [M]
    boss_w=0.044,           # along the rim [M-eye: 250 px on the photo's near side at about 5 px a mm]
    boss_h=0.020,           # above the gutter's floor [M-eye]
    boss_d=0.0075,          # proud of the wall at the waist [M-eye]
    shelf_a=90.0,
    shelf_w=0.062,
    shelf_h=0.013,
    shelf_d=0.0075,
    slot=(0.028, 0.0042, 0.009),    # the slot in the shelf's top: along the rim, across, deep [M-eye]
    boss_r=0.0018,          # the bosses' edge radius, and their blend into the shell [E]
    boss_k=0.0025,
    # ---- the suspension
    band_h=0.026,           # the headband: a strip of HDPE [E: typical]
    band_t=0.0020,
    band_y=0.003,           # its lower edge over the seat plane (the brow pad wraps under it)
    pad_half=58.0,          # the brow pad: over the band's front, to this plan angle each side; its thickness; how far
    pad_t=0.0045,           #   it wraps over the band's edges [E: a polyester and foam sweat band, the product sheet]
    pad_wrap=0.003,
    lock_half=30.0,         # the pin-lock overlap at the back: the band doubled within this angle of the back [E]
    strap_w=0.019,          # the cradle's two woven nylon straps [E: 3/4 in webbing]
    strap_t=0.0016,
    cradle_y=0.084,         # the cradle's crown over the seat plane: the wearing height [E: EN 397 asks >= 80 mm; the
    #                         shell's inner top stands 24 mm over it]
    cradle_n=2.2,           # the straps' arch (a superellipse exponent)
    hanger_w=0.020,         # the four hangers (the keys): strips from the band's top edge to the boss sockets
    hanger_t=0.0020,
    hanger_y=0.040,         # where a hanger's key meets the wall, over the seat plane
    lug=(0.012, 0.011, 0.0022, 0.0026),     # the chin-strap lug under each front boss: wide, tall, thick, hole radius
)


# ----------------------------------------------------------------------------------------------------- helpers
def _smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-20)


def dims(spec=SPEC):
    """the shell's ovals and heights (m): the dome's OUTER wall at the waist (rx_o, rz_o: the overall size less the
    gutter and the peak), its mid-surface (rx, rz), the waist's height y_w (mid-surface: where the wall ends and the
    fillet into the floor begins), the dome's height H over it (to the mid-surface's apex, no rib), and the head
    opening's semi-axes (an ellipse of the headband's circumference and ratio: Ramanujan's perimeter)"""
    t = spec['shell_t']
    rx_o = 0.5 * spec['width'] - spec['gutter_w']
    rz_o = 0.5 * (spec['length'] - spec['gutter_w'] - spec['peak_w'])
    y_w = spec['y_rim'] + 0.5 * t + spec['fillet_r']
    y_apex = spec['y_rim'] + spec['height'] - spec['rib_h'][0] - 0.5 * t           # the mid-surface's apex
    k = spec['open_ratio']
    per = np.pi * (3.0 * (k + 1.0) - np.sqrt((3.0 * k + 1.0) * (k + 3.0)))        # perimeter of semi-axes (1, k)
    rx_h = spec['head_circ'] / per
    return dict(t=t, rx_o=rx_o, rz_o=rz_o, rx=rx_o - 0.5 * t, rz=rz_o - 0.5 * t, y_w=y_w, H=y_apex - y_w,
                y_top=spec['y_rim'] + spec['height'], rx_h=rx_h, rz_h=k * rx_h)


# ----------------------------------------------------------------------------------------------------- the dome
def dome_height(rho, spec=SPEC):
    """the un-ribbed mid-surface's height over the waist at the plan share rho (0 the apex, 1 the waist)"""
    p = spec['dome_p']
    return dims(spec)['H'] * (1.0 - np.clip(np.asarray(rho, np.float64), 0.0, 1.0) ** p) ** (1.0 / p)


def rho_at_height(yy, spec=SPEC):
    """the plan share at which the un-ribbed mid-surface stands yy over the waist"""
    p = spec['dome_p']
    return (1.0 - np.clip(np.asarray(yy, np.float64) / dims(spec)['H'], 0.0, 1.0) ** p) ** (1.0 / p)


def rib_lift(x, yy, spec=SPEC):
    """the ribs: how far the shell is lifted along the dome's normal at the plan distance x from the midplane and
    the height yy over the waist: a flat-crested bank on the midline, one each side at rib_x, all three dying out
    between rib_fade's two heights (a common level front and back)"""
    hc, hs = spec['rib_h']
    (tc, ts), (fc, fs) = spec['rib_top'], spec['rib_foot']
    x = np.abs(np.asarray(x, np.float64))
    xs = side_rib_x(yy, spec)
    fade = _smoothstep(spec['rib_fade'][0], spec['rib_fade'][1], yy)
    return fade * (hc * (1.0 - _smoothstep(tc, fc, x)) + hs * (1.0 - _smoothstep(ts, fs, np.abs(x - xs))))


def side_rib_x(yy, spec=SPEC):
    """the side ribs' distance from the midplane at the height yy over the waist: rib_x on the crown, closing in on
    the centre rib toward the front and the back (rib_conv)"""
    c = spec['rib_conv']
    return spec['rib_x'] * np.clip((np.asarray(yy, np.float64) + c) / (dims(spec)['H'] + c), 0.0, 1.0)


def dome_base(u, v, spec=SPEC):
    """the un-ribbed dome's mid-surface at the plan coordinates u = x / rx, v = z / rz (inside the unit disk): the
    points and the outward unit normals (the gradient of its implicit form: exact, the apex and the waist included)"""
    d = dims(spec)
    p = spec['dome_p']
    u, v = np.broadcast_arrays(np.asarray(u, np.float64), np.asarray(v, np.float64))
    rho = np.minimum(np.hypot(u, v), 1.0)
    yy = dome_height(rho, spec)
    P = np.stack([d['rx'] * u, d['y_w'] + yy, d['rz'] * v], -1)
    g = rho ** (p - 1.0) / np.maximum(rho, 1.0e-12)      # rho^(p - 2), finite at the apex for any p > 1
    N = np.stack([g * u / d['rx'], (yy / d['H']) ** (p - 1.0) / d['H'], g * v / d['rz']], -1)
    return P, _unit(N)


def dome_point(u, v, spec=SPEC):
    """the dome's MID-surface with its ribs at (u, v), (..., 3)"""
    P, N = dome_base(u, v, spec)
    return P + rib_lift(P[..., 0], P[..., 1] - dims(spec)['y_w'], spec)[..., None] * N


def dome_frame(u, v, spec=SPEC, e=2.0e-5):
    """the ribbed mid-surface's points and outward unit normals at (u, v) (finite differences in the plan; near the
    waist, where the plan degenerates, the un-ribbed normal: the ribs have died out there)"""
    u, v = np.broadcast_arrays(np.asarray(u, np.float64), np.asarray(v, np.float64))
    P = dome_point(u, v, spec)
    P0, N0 = dome_base(u, v, spec)
    rho = np.hypot(u, v)
    s = np.minimum(1.0, (1.0 - 4.0 * e) / np.maximum(rho, 1e-12))               # the stencil kept inside the disk
    uc, vc = u * s, v * s
    Pu = dome_point(uc + e, vc, spec) - dome_point(uc - e, vc, spec)
    Pv = dome_point(uc, vc + e, spec) - dome_point(uc, vc - e, spec)
    N = _unit(np.cross(Pv, Pu))
    lifted = rib_lift(P0[..., 0], P0[..., 1] - dims(spec)['y_w'], spec) > 1.0e-7
    return P, np.where(lifted[..., None], N, N0)


# --------------------------------------------------------------------------------------------------- the flange
def peak_window(a, spec=SPEC):
    """1 across the peak's front, 0 round the gutter, at the plan angle a (radians from +Z)"""
    a = np.abs((np.asarray(a, np.float64) + np.pi) % (2.0 * np.pi) - np.pi)
    return 1.0 - _smoothstep(spec['peak_a'][0], spec['peak_a'][1], np.degrees(a))


def waist(a, spec=SPEC):
    """the waist's mid-surface points at the plan angles a, the plan's outward unit normals and unit tangents (toward
    growing a), each (..., 3)"""
    d = dims(spec)
    a = np.asarray(a, np.float64)
    s, c = np.sin(a), np.cos(a)
    P = np.stack([d['rx'] * s, np.full(a.shape, d['y_w']), d['rz'] * c], -1)
    N = _unit(np.stack([s / d['rx'], np.zeros(a.shape), c / d['rz']], -1))
    T = _unit(np.stack([d['rx'] * c, np.zeros(a.shape), -d['rz'] * s], -1))
    return P, N, T


def flange_terms(a, spec=SPEC):
    """per plan angle: the flange's plan width W (from the dome's outer wall to the lip's outer edge = from the
    waist's mid-surface to the mid-surface's last point), its floor's fall delta (radians), the floor's length Lf,
    and the meridian's arc lengths at the fillet's end, the floor's end, the lip's arc's end and the edge (q1..q4)"""
    S = peak_window(a, spec)
    W = spec['gutter_w'] + (spec['peak_w'] - spec['gutter_w']) * S
    dl = np.radians(spec['gutter_slope'] + (spec['peak_slope'] - spec['gutter_slope']) * S)
    rf, rl, g, lt = spec['fillet_r'], spec['lip_r'], np.radians(spec['lip_turn']), spec['lip_l']
    beta = 0.5 * np.pi - dl
    X1 = rf * (1.0 - np.cos(beta))
    Lf = (W - X1 - rl * (np.sin(g - dl) + np.sin(dl)) - lt * np.cos(g - dl)) / np.cos(dl)
    q1 = rf * beta
    q2 = q1 + Lf
    q3 = q2 + rl * g
    return dict(W=W, delta=dl, Lf=Lf, q1=q1, q2=q2, q3=q3, q4=q3 + lt)


def flange_profile(q, ft, spec=SPEC):
    """the flange's meridian at the arc lengths q from the waist (broadcast against flange_terms' arrays): the outward
    offset X, the height Y (from the waist, negative: down) and the tangent's angle above the outward horizontal"""
    rf, rl = spec['fillet_r'], spec['lip_r']
    dl = ft['delta']
    q = np.asarray(q, np.float64)
    beta = 0.5 * np.pi - dl
    X1, Y1 = rf * (1.0 - np.cos(beta)), -rf * np.sin(beta)
    X2, Y2 = X1 + ft['Lf'] * np.cos(dl), Y1 - ft['Lf'] * np.sin(dl)
    g = (ft['q3'] - ft['q2']) / rl
    X3, Y3 = X2 + rl * (np.sin(g - dl) + np.sin(dl)), Y2 + rl * (np.cos(dl) - np.cos(g - dl))
    t1 = np.clip(q / rf, 0.0, beta)                                  # the fillet's turn
    s2 = np.clip(q - ft['q1'], 0.0, ft['Lf'])                        # along the floor
    t3 = np.clip((q - ft['q2']) / rl, 0.0, g)                        # the lip's turn
    s4 = np.clip(q - ft['q3'], 0.0, None)                            # along the lip's straight end
    in1, in2, in3 = q <= ft['q1'], q <= ft['q2'], q <= ft['q3']
    X = np.where(in1, rf * (1.0 - np.cos(t1)),
                 np.where(in2, X1 + s2 * np.cos(dl),
                          np.where(in3, X2 + rl * (np.sin(t3 - dl) + np.sin(dl)), X3 + s4 * np.cos(g - dl))))
    Y = np.where(in1, -rf * np.sin(t1),
                 np.where(in2, Y1 - s2 * np.sin(dl),
                          np.where(in3, Y2 + rl * (np.cos(dl) - np.cos(t3 - dl)), Y3 + s4 * np.sin(g - dl))))
    th = np.where(in1, t1 - 0.5 * np.pi, np.where(in2, -dl, np.where(in3, t3 - dl, g - dl)))
    return X, Y, th


def flange_frame(a, q, spec=SPEC, e=1.0e-5):
    """the flange's MID-surface at the plan angles a and the arc lengths q from the waist (broadcast): the points,
    the unit normals of its UPPER face (toward the dome's outside: up on the floor) and the meridian's unit
    tangents (outward), each (..., 3)"""
    a, q = np.broadcast_arrays(np.asarray(a, np.float64), np.asarray(q, np.float64))

    def pos(aa):
        Pw, Nw, _ = waist(aa, spec)
        X, Y, th = flange_profile(q, flange_terms(aa, spec), spec)
        return Pw + X[..., None] * Nw + Y[..., None] * np.array([0.0, 1.0, 0.0]), Nw, th
    P, Nw, th = pos(a)
    T = np.cos(th)[..., None] * Nw + np.sin(th)[..., None] * np.array([0.0, 1.0, 0.0])
    Pa = pos(a + e)[0] - pos(a - e)[0]
    N = _unit(np.cross(T, Pa))
    return P, N, T


# -------------------------------------------------------------------------------------- the shell's mid-surface
def meridian_shares(spec=SPEC, step=0.00035):
    """the dome's meridian resampled to about `step` of arc length on its longest meridian (front to back): the plan
    shares rho from the apex (0, left out) to the waist (1)"""
    d = dims(spec)
    th = np.linspace(0.0, 0.5 * np.pi, 40001)
    p = spec['dome_p']
    rho, yy = np.sin(th) ** (2.0 / p), d['H'] * np.cos(th) ** (2.0 / p)
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(rho) * d['rz'], np.diff(yy)))])
    n = int(np.ceil(1.1 * s[-1] / step)) + 1
    return np.interp(np.linspace(0.0, s[-1], n), s, rho)[1:]


def shell_patch(spec=SPEC, n_a=1440, step=0.00035):
    """the shell's MID-surface as one triangle patch for the SHELL: a fan at the apex, the ribbed dome's rows down
    to the waist, the flange's rows out to the lip's edge. Returns V (n, 3), F (m, 3)"""
    a = np.linspace(0.0, 2.0 * np.pi, n_a, endpoint=False)
    rho = meridian_shares(spec, step)
    A, R = np.meshgrid(a, rho, indexing='ij')
    Vd = dome_point(R * np.sin(A), R * np.cos(A), spec)                             # (n_a, n_rho, 3)
    ft = flange_terms(a, spec)
    n_f = int(np.ceil(1.1 * float(ft['q4'].max()) / step)) + 1
    sh = np.linspace(0.0, 1.0, n_f)[1:]                                             # (the waist is the dome's last row)
    Vf = flange_frame(a[:, None], ft['q4'][:, None] * sh[None, :], spec)[0]
    rows = np.concatenate([Vd, Vf], 1)
    nr = rows.shape[1]
    V = np.vstack([rows.reshape(-1, 3), dome_point(0.0, 0.0, spec).reshape(1, 3)])
    i = np.arange(n_a)[:, None]
    j = np.arange(nr - 1)[None, :]
    p0 = i * nr + j
    p1 = ((i + 1) % n_a) * nr + j
    F = [np.stack([p0, p1 + 1, p1], -1).reshape(-1, 3), np.stack([p0, p0 + 1, p1 + 1], -1).reshape(-1, 3)]
    top = np.arange(n_a) * nr
    F.append(np.stack([top, np.full(n_a, len(V) - 1), np.roll(top, -1)], -1))
    return V, np.concatenate(F)


# ---------------------------------------------------------------------------------------------------- the bosses
def boss_boxes(spec=SPEC):
    """the four suspension bosses and the two slot shelves as boxes: [dict(name, c (centre), axes (3 x 3: columns =
    along the rim, up, outward), half (3,), a (its plan angle), kind)], and the slots cut in the shelves' tops (the
    same fields). A box stands on the gutter's floor (sunk 1.5 mm in it), its back 4 mm inside the wall's
    mid-surface, its face boss_d proud of the outer wall at the waist"""
    d = dims(spec)
    out, slots = [], []
    y_floor = d['y_w'] - spec['fillet_r'] + 0.5 * d['t']                            # the floor's upper face at its root
    back = 0.004
    items = [(f'boss_{s}{n}', sg * np.radians(ab), spec['boss_w'], spec['boss_h'], spec['boss_d'], 'boss')
             for s, sg in (('L', 1.0), ('R', -1.0)) for n, ab in zip('FB', spec['boss_a'])]
    items += [(f'shelf_{s}', sg * np.radians(spec['shelf_a']), spec['shelf_w'], spec['shelf_h'], spec['shelf_d'],
               'shelf') for s, sg in (('L', 1.0), ('R', -1.0))]
    for nm, a, w, h, dp, kind in items:
        Pw, Nw, Tw = waist(np.array(a), spec)
        up = np.array([0.0, 1.0, 0.0])
        r0, r1 = -back, 0.5 * d['t'] + dp                                           # along the normal from the waist's mid
        # how deep the box is sunk: 1.5 mm at the wall, and under the floor all the way out to its face (the floor
        # falls outward: 4 degrees round the gutter, up to 18 across the peak, where a box sunk 1.5 mm at the wall
        # stood on air at its face)
        da = 0.5 * w / float(np.hypot(Pw[0], Pw[2]))
        aa = a + np.linspace(-1.0, 1.0, 5) * da
        ft = flange_terms(aa, spec)
        qq = ft['q1'][:, None] + np.linspace(0.0, 1.0, 9)[None, :] * (ft['q2'] - ft['q1'])[:, None]
        Pf, Nf, _ = flange_frame(aa[:, None], qq, spec)
        up_f = Pf + 0.5 * d['t'] * Nf
        near = ((up_f - Pw) @ Nw) <= r1 + 0.001
        sink = max(0.0015, y_floor - float(up_f[..., 1][near].min()) + 0.0008)
        c = Pw + Nw * 0.5 * (r0 + r1) + up * (y_floor - sink + 0.5 * (h + sink) - d['y_w'])
        half = np.array([0.5 * w, 0.5 * (h + sink), 0.5 * (r1 - r0)])
        box = dict(name=nm, c=c, axes=np.column_stack([Tw, up, Nw]), half=half, a=float(a), kind=kind, w=w, h=h,
                   y_top=y_floor + h, y_bot=y_floor - sink, r_face=r1, da=da)
        out.append(box)
        if kind == 'shelf':
            sl, sw, sd = spec['slot']
            cs = Pw + Nw * (0.5 * d['t'] + 0.5 * dp) + up * (y_floor + h - 0.5 * sd + 0.001 - d['y_w'])
            slots.append(dict(name='slot' + nm[5:], c=cs, axes=box['axes'],
                              half=np.array([0.5 * sl, 0.5 * sd + 0.001, 0.5 * sw]), a=float(a), kind='slot'))
    return out, slots


def boss_clip_patch(b, spec=SPEC, T=0.0035, n_a=24, step=0.0006):
    """the boss b's CLIP for the high: the shell's MID-surface offset T toward the inside and under, over the plan
    angles the boss spans (+ 40 %), from 6 mm over the boss's top down the wall to the waist and out along the flange
    to the floor's end: as a SHELL of half-thickness T it is the slab [mid - 2 T, mid]. SUBTRACTED inside the bosses'
    group, it cuts what a box would show inside the hat or under the gutter (a box's back stands 4 mm inside the
    wall's mid-surface and its bottom is sunk under the floor: hidden outside, but 2.9 mm proud under the rim's inside
    below the waist and 2.75 mm proud of the inner wall). Returns V, F"""
    d = dims(spec)
    a = b['a'] + np.linspace(-1.4, 1.4, n_a) * b['da']
    y_hi = b['y_top'] + 0.006 - d['y_w']
    ys = np.linspace(y_hi, 0.0, max(int(np.ceil(y_hi / step)), 2) + 1)[:-1]
    rho = rho_at_height(ys, spec)
    A, R = np.meshgrid(a, rho, indexing='ij')
    Pd, Nd = dome_base(R * np.sin(A), R * np.cos(A), spec)
    ft = flange_terms(a, spec)
    n_f = int(np.ceil(float(ft['q2'].max()) / step)) + 1
    Pf, Nf, _ = flange_frame(a[:, None], (ft['q2'][:, None] + 0.001) * np.linspace(0.0, 1.0, n_f)[None, :], spec)
    G = np.concatenate([Pd, Pf], 1) - T * np.concatenate([Nd, Nf], 1)                 # (n_a, rows, 3)
    nr = G.shape[1]
    i = np.arange(n_a - 1)[:, None]
    j = np.arange(nr - 1)[None, :]
    p0 = i * nr + j
    p1 = p0 + nr
    F = np.concatenate([np.stack([p0, p1, p1 + 1], -1).reshape(-1, 3), np.stack([p0, p1 + 1, p0 + 1], -1).reshape(-1, 3)])
    return G.reshape(-1, 3), F


# ------------------------------------------------------------------------------------------------ the suspension
def band_terms(a, spec=SPEC):
    """the headband at the plan angle a: its half-thickness, the height of its lower and upper edges and the pad's
    share (1 on the brow pad, which is thicker and wraps the band's two edges; the pin-lock overlap at the back
    doubles the band)"""
    ad = np.degrees(np.abs((np.asarray(a, np.float64) + np.pi) % (2.0 * np.pi) - np.pi))
    pad = 1.0 - _smoothstep(spec['pad_half'] - 4.0, spec['pad_half'], ad)
    lock = _smoothstep(180.0 - spec['lock_half'], 180.0 - spec['lock_half'] + 1.5, ad)
    ht = 0.5 * spec['band_t'] * (1.0 + lock) + 0.5 * (spec['pad_t'] - spec['band_t']) * pad
    y0 = spec['band_y'] * (1.0 - pad)
    y1 = spec['band_y'] + spec['band_h'] + spec['pad_wrap'] * pad
    return ht, y0, y1, pad


def band_point(a, y, off=0.0, spec=SPEC):
    """the point `off` outside the headband's MID-surface (negative: toward the head) at the plan angle a and the
    height y, and the plan's outward unit normal there. The band's INNER face is the head opening's ellipse all
    round: the mid-surface stands its own half-thickness outside it"""
    d = dims(spec)
    a, y, off = np.broadcast_arrays(np.asarray(a, np.float64), np.asarray(y, np.float64), np.asarray(off, np.float64))
    s, c = np.sin(a), np.cos(a)
    N = _unit(np.stack([s / d['rx_h'], np.zeros(a.shape), c / d['rz_h']], -1))
    P = np.stack([d['rx_h'] * s, y, d['rz_h'] * c], -1)
    return P + (band_terms(a, spec)[0] + off)[..., None] * N, N


def band_patch(spec=SPEC, n_a=1440, step=0.0004):
    """the headband with its brow pad and pin-lock overlap as a patch for its SHELL: V, F and the per-vertex
    half-thickness"""
    a = np.linspace(0.0, 2.0 * np.pi, n_a, endpoint=False)
    ht, y0, y1, _ = band_terms(a, spec)
    n_y = int(np.ceil((spec['band_h'] + spec['band_y'] + spec['pad_wrap']) / step)) + 1
    sh = np.linspace(0.0, 1.0, n_y)
    Y = y0[:, None] + (y1 - y0)[:, None] * sh[None, :]
    V = band_point(a[:, None], Y, 0.0, spec)[0].reshape(-1, 3)
    i = np.arange(n_a)[:, None]
    j = np.arange(n_y - 1)[None, :]
    p0 = i * n_y + j
    p1 = ((i + 1) % n_a) * n_y + j
    F = np.concatenate([np.stack([p0, p1, p1 + 1], -1).reshape(-1, 3), np.stack([p0, p1 + 1, p0 + 1], -1).reshape(-1, 3)])
    return V, F, np.repeat(ht, n_y)


def inner_wall(a, y, spec=SPEC):
    """the shell's INNER face at the plan angle a and the height y (the un-ribbed dome's wall: for the hangers and
    the straps, low on the wall where no rib runs): the points and the plan's outward unit normals"""
    d = dims(spec)
    a, y = np.broadcast_arrays(np.asarray(a, np.float64), np.asarray(y, np.float64))
    rho = rho_at_height(np.maximum(y - d['y_w'], 0.0), spec)
    P, N = dome_base(rho * np.sin(a), rho * np.cos(a), spec)
    P = P - 0.5 * d['t'] * N
    P[..., 1] = y
    return P, N


def hanger_angles(spec=SPEC):
    """the four hangers' plan angles (radians): the bosses' own"""
    return [sg * np.radians(ab) for sg in (1.0, -1.0) for ab in spec['boss_a']]


def hanger_path(a, spec=SPEC, n=24):
    """one hanger's centre line at the plan angle a, from the headband's top edge out and up to its key on the
    shell's inner wall: (n, 3) points, the strip's unit normals (toward the head) and its unit width direction"""
    d = dims(spec)
    y_b = spec['band_y'] + spec['band_h']
    A = band_point(np.array(a), np.array(y_b - 0.006), 0.5 * spec['band_t'] + 0.5 * spec['hanger_t'], spec)[0]
    Bw, Nw = inner_wall(np.array(a), np.array(spec['hanger_y']), spec)
    B = Bw - Nw * (0.5 * spec['hanger_t'] + 0.0004)
    C = inner_wall(np.array(a), np.array(spec['hanger_y'] + 0.012), spec)[0] - Nw * (0.5 * spec['hanger_t'] + 0.0004)
    # up the band's outer face, a round elbow out to the wall, up the wall to the key
    A1 = A + np.array([0.0, 0.008, 0.0])
    t = np.linspace(0.0, 1.0, n)[:, None]
    bez = (1 - t) ** 3 * A1 + 3 * (1 - t) ** 2 * t * (A1 + [0.0, 0.006, 0.0]) + 3 * (1 - t) * t ** 2 * (B - [0.0, 0.006, 0.0]) \
        + t ** 3 * B
    P = np.vstack([A[None], bez, C[None]])
    T = _unit(np.gradient(P, axis=0))
    Wd = waist(np.array(a), spec)[2]
    Nn = _unit(np.cross(T, Wd))
    Nn = np.where((Nn * Nw).sum(-1, keepdims=True) > 0.0, -Nn, Nn)                  # toward the head
    return P, Nn, Wd


def strip_patch(P, Wd, width, per=6):
    """a strip of `width` about the centre line P (n, 3) along the width direction Wd ((3,) or (n, 3)), `per` + 1
    points across: V, F"""
    Wd = np.broadcast_to(np.asarray(Wd, np.float64), P.shape)
    s = np.linspace(-0.5, 0.5, per + 1) * width
    V = (P[:, None, :] + s[None, :, None] * Wd[:, None, :]).reshape(-1, 3)
    n = len(P)
    i = np.arange(n - 1)[:, None]
    j = np.arange(per)[None, :]
    p0 = i * (per + 1) + j
    p1 = p0 + per + 1
    F = np.concatenate([np.stack([p0, p1, p1 + 1], -1).reshape(-1, 3), np.stack([p0, p1 + 1, p0 + 1], -1).reshape(-1, 3)])
    return V, F


def strap_path(k, spec=SPEC, n=400):
    """the cradle's strap k (0: from the front left key over the crown to the rear right key; 1: front right to rear
    left) as its MID-surface's centre line: (n, 3) points, its unit normals (down, toward the head) and its unit
    width direction. An arch in the vertical plane through the seat axis and the two keys (a superellipse of
    exponent cradle_n) from where the hangers' keys meet the wall up to the wearing height; strap 1 passes OVER
    strap 0 at the crown (its own thickness higher over the middle)"""
    a = hanger_angles(spec)[0 if k == 0 else 2]
    Bw, Nw = inner_wall(np.array(a), np.array(spec['hanger_y']), spec)
    e = _unit(np.array([Bw[0], 0.0, Bw[2]]))
    Ra = float(np.hypot(Bw[0], Bw[2])) - spec['hanger_t'] - 0.5 * spec['strap_t'] - 0.0008
    ya, yc, nn = spec['hanger_y'] + 0.004, spec['cradle_y'] + 0.5 * spec['strap_t'], spec['cradle_n']
    # the arch's own foot stands 12 mm under the strap's end, so the strap leaves its key already leaning in (16
    # degrees, the wall 17.6): from a foot AT the end it rose square and the wall closed on it, 0.86 mm into the
    # high's shell 53 - 63 mm over the waist
    m = 2.0 / nn
    y0 = ya - 0.012
    th0 = float(np.arcsin(((ya - y0) / (yc - y0)) ** (1.0 / m)))
    R0 = Ra / np.cos(th0) ** m
    th = np.linspace(th0, np.pi - th0, n)
    h = -R0 * np.sign(np.cos(th)) * np.abs(np.cos(th)) ** m
    yy = y0 + (yc - y0) * np.sin(th) ** m
    if k == 1:
        yy = yy + (spec['strap_t'] + 0.0003) * np.exp(-(h / 0.022) ** 2)
    P = h[:, None] * e[None, :] + yy[:, None] * np.array([0.0, 1.0, 0.0])
    T = _unit(np.gradient(P, axis=0))
    W0 = np.array([e[2], 0.0, -e[0]])                    # square across the arch's plane (the crown)
    # near the keys the webbing turns flat to the wall: its width along the waist's tangent at each key. (Square to
    # the arch's plane all the way, it met the elliptical wall 10 degrees off square at the keys: one edge stood 1.6
    # mm nearer the wall and entered the high's shell by 1.24 mm, and came out through the low's wall: the two spikes
    # on the side of try 2 and try 3)
    Wk = [waist(np.array(x), spec)[2] for x in (a, a + np.pi)]
    Wk = [w * np.sign(w @ W0) for w in Wk]
    f = (np.minimum(th, np.pi - th) - th0) / (np.pi - 2.0 * th0)
    wgt = (1.0 - _smoothstep(0.0, 0.35, f))[:, None]
    Wend = np.where((th < 0.5 * np.pi)[:, None], Wk[1][None, :], Wk[0][None, :])     # (th = 0 is h = -Ra: the key at a + pi)
    Wd = wgt * Wend + (1.0 - wgt) * W0[None, :]
    Wd = _unit(Wd - (Wd * T).sum(-1, keepdims=True) * T)
    Nn = _unit(np.cross(T, Wd))
    Nn = np.where(Nn[:, 1:2] > 0.0, -Nn, Nn)
    return P, Nn, Wd


def lug_frames(spec=SPEC):
    """the two chin-strap lugs (under the front bosses, hanging from the rim's inner edge): [dict(name, c, axes
    (columns = along the rim, up, outward), half)], and each hole's two axis ends"""
    d = dims(spec)
    w, h, t, r = spec['lug']
    out = []
    for nm, sg in (('lug_L', 1.0), ('lug_R', -1.0)):
        a = sg * np.radians(spec['boss_a'][0])
        Pw, Nw, Tw = waist(np.array(a), spec)
        up = np.array([0.0, 1.0, 0.0])
        c = Pw - Nw * (0.5 * d['t'] + 0.5 * t - 0.0002) + up * (spec['y_rim'] - 0.5 * h + 0.003 - d['y_w'])
        hole = c - up * (0.5 * h - r - 0.0022)
        out.append(dict(name=nm, c=c, axes=np.column_stack([Tw, up, Nw]), half=np.array([0.5 * w, 0.5 * h, 0.5 * t]),
                        hole=(hole - Nw * t, hole + Nw * t), a=float(a)))
    return out


# ----------------------------------------------------------------------------------------------------- block-out
def build_sdf(spec=SPEC, parts=('shell', 'bosses', 'suspension', 'lugs'), n_a=1440, step=0.00035):
    """the block-out: the SHELL over its mid-surface (hard), the bosses and shelves as round boxes blended into it
    once (a group: boss_k), the slots cut, then the suspension (hard unions: its parts touch the shell only at the
    keys) and the lugs"""
    from .. import sdf
    d = dims(spec)
    prog = sdf.Program()
    if 'shell' in parts:
        V, F = shell_patch(spec, n_a, step)
        prog.shell(V, F, 0.5 * d['t'], k=0.0, maxd=0.02, name='shell')
    if 'bosses' in parts:
        boxes, slots = boss_boxes(spec)
        prog.begin_group(op=sdf.UNION, k=spec['boss_k'])
        for b in boxes:
            prog.roundbox(b['c'], b['half'], spec['boss_r'], b['axes'], k=0.0, name=b['name'])
        for b in boxes:                       # (the boxes cut back to the shell's mid-surface: boss_clip_patch)
            Vc, Fc = boss_clip_patch(b, spec)
            prog.shell(Vc, Fc, 0.0035, op=sdf.SUBTRACT, k=0.0, maxd=0.02, name=b['name'] + ' clip')
        prog.end_group()
        for s in slots:
            prog.roundbox(s['c'], s['half'], 0.0008, s['axes'], op=sdf.SUBTRACT, k=0.0006, name=s['name'])
    if 'lugs' in parts:
        for lg in lug_frames(spec):
            prog.roundbox(lg['c'], lg['half'], 0.0009, lg['axes'], k=0.0, name=lg['name'])
            prog.roundcone(lg['hole'][0], lg['hole'][1], spec['lug'][3], spec['lug'][3], op=sdf.SUBTRACT, k=0.0003,
                           name=lg['name'] + ' hole')
    if 'suspension' in parts:
        Vb, Fb, Hb = band_patch(spec)
        prog.shell(Vb, Fb, Hb, k=0.0, maxd=0.02, name='headband')
        for i, a in enumerate(hanger_angles(spec)):
            P, Nn, Wd = hanger_path(a, spec)
            Pd = np.vstack([np.linspace(P[j], P[j + 1], 6, endpoint=False) for j in range(len(P) - 1)] + [P[-1:]])
            Vh, Fh = strip_patch(Pd, Wd, spec['hanger_w'])
            prog.shell(Vh, Fh, 0.5 * spec['hanger_t'], k=0.0, maxd=0.02, name=f'hanger {i}')
        for k in range(2):
            P, Nn, Wd = strap_path(k, spec)
            Vs, Fs = strip_patch(P, Wd, spec['strap_w'], per=24)
            prog.shell(Vs, Fs, 0.5 * spec['strap_t'], k=0.0, maxd=0.02, name=f'strap {k}')
    prog.hat = dict(spec=spec, dims=d)
    return prog


def extents(spec=SPEC):
    """the hat's own box (m)"""
    d = dims(spec)
    a = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
    ft = flange_terms(a, spec)
    P = flange_frame(a[:, None], ft['q4'][:, None] * np.linspace(0.0, 1.0, 12)[None, :], spec)[0].reshape(-1, 3)
    lo, hi = P.min(0) - d['t'], P.max(0) + d['t']
    hi[1] = d['y_top'] + 0.0005
    lo[1] = min(lo[1], min(float(lg['c'][1] - lg['half'][1]) for lg in lug_frames(spec)) - 0.0005)
    return lo, hi


def bounds(spec=SPEC, pad=0.006):
    """the voxel grid's box (the hat's extents plus pad)"""
    lo, hi = extents(spec)
    return lo - pad, hi + pad


# ------------------------------------------------------------------------------------------- a clay of the shell
def clay_mesh(spec=SPEC, n_a=240, step=0.002, face=+1.0):
    """the shell's outer (face +1) or inner (-1) surface as a coarse triangle mesh, for the photo fit and quick
    looks (not the high: build_sdf is; not the low: build_low is): V, F"""
    d = dims(spec)
    a = np.linspace(0.0, 2.0 * np.pi, n_a, endpoint=False)
    rho = meridian_shares(spec, step)
    A, R = np.meshgrid(a, rho, indexing='ij')
    Pd, Nd = dome_frame(R * np.sin(A), R * np.cos(A), spec)
    ft = flange_terms(a, spec)
    n_f = int(np.ceil(float(ft['q4'].max()) / (0.5 * step))) + 1
    sh = np.linspace(0.0, 1.0, n_f)[1:]
    Pf, Nf, _ = flange_frame(a[:, None], ft['q4'][:, None] * sh[None, :], spec)
    rows = np.concatenate([Pd + face * 0.5 * d['t'] * Nd, Pf + face * 0.5 * d['t'] * Nf], 1)
    nr = rows.shape[1]
    Pa, Na = dome_frame(np.array(0.0), np.array(0.0), spec)
    V = np.vstack([rows.reshape(-1, 3), (Pa + face * 0.5 * d['t'] * Na).reshape(1, 3)])
    i = np.arange(n_a)[:, None]
    j = np.arange(nr - 1)[None, :]
    p0 = i * nr + j
    p1 = ((i + 1) % n_a) * nr + j
    F = [np.stack([p0, p1 + 1, p1], -1).reshape(-1, 3), np.stack([p0, p0 + 1, p1 + 1], -1).reshape(-1, 3)]
    top = np.arange(n_a) * nr
    F.append(np.stack([top, np.full(n_a, len(V) - 1), np.roll(top, -1)], -1))
    F = np.concatenate(F)
    return V, (F if face > 0 else F[:, ::-1])


def box_mesh(b):
    """a boss's box as 12 triangles (the clay's stand-in for it)"""
    c, R, h = b['c'], b['axes'], b['half']
    s = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], float)
    V = c + (s * h) @ R.T
    F = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7],
                  [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    return V, F


# ================================================================================================= THE LOW
# AUTHORED (WORKING_RULES 2; craft guide 05): loops drawn where the object's form turns, every vertex ON the block-out
# by construction (the same dome_frame / flange_frame), the hat its own mirror in x to the bit.
#   the CAP      a 16 x 8 grid over the crown: its x-lines ARE the ribs' lines (the centre rib's two crest edges and
#                two feet, each side rib's two feet and two crest edges: they close in toward the front and back with
#                the ribs), one free line more each side, the edge; its corners rounded (a square grid's corners droop)
#   the WALL     rings from the cap's edge down to the waist at the heights where the meridian turns; the 13 columns
#                on the front and on the back stay on the ribs' lines until the ribs have died out
#   the FLANGE   fillet, floor, lip, the lip's own edge; then the under face back in to the wall's inside
#   the INSIDE   the wall's and the cap's inner faces at fewer rings (seen only from below)
#   the BOSSES   five quads each: a face, a top in two halves whose back edge lies INSIDE the wall's thickness (a
#                straight back edge would show a gap at its ends: the wall curves 2 mm over a boss's width), two sides
#   the SUSPENSION  the headband as a thin closed section (outer face, inner face, its two edges), the hangers and the
#                cradle's straps as two faces each, the lugs with their holes ("holes stay geometry")
# The parts go through soft_common (the soft builder's shared layer, imported as it stands: assemble / pack /
# low_arrays): a part is a smoothing group, an island a UV shell, a STACKED island carries its primary's own UVs.
REGIONS = ('shell', 'inside', 'boss', 'band', 'pad', 'strap', 'lug')
R_SHELL, R_INSIDE, R_BOSS, R_BAND, R_PAD, R_STRAP, R_LUG = range(7)
ZONES = ('shell', 'suspension', 'pad', 'webbing')     # masks B = 0, 1/3, 2/3, 1: the runtime's four palette zones
NX, NZ = 8, 4               # the cap's half counts: 2 NX cells across, 2 NZ along: its edge has 4 (NX + NZ) = 48 vertices
K_LOW = 4 * (NX + NZ)
CAP_U, CAP_V = 0.60, 0.62   # the cap's half extents in the plan's own units (x / rx, z / rz) at its edges' middles
CAP_ROUND = 0.9             # how far the grid's corners are drawn in (0 a rectangle in plan, 1 an ellipse)
WALL_Y = (0.080, 0.062, 0.050, 0.038, 0.019)    # the wall's rings: heights over the waist (62 and 38: where the ribs
#                                                 begin to die out and are gone)
INNER_Y = (0.080, 0.062, 0.038)    # the inside's rings (of WALL_Y). 62 brackets the suspension's keys (42 - 55 mm
#                                    over the waist): with 80 and 38 alone the inner wall's chord sagged 2.4 mm there
#                                    and the hangers' top corners came out through the low's wall (try 2)
EDGE_OUT = 0.0006           # the lip's edge band stands this far out along the lip (it cuts the rounded edge halfway)
N_STRAP = 14                # a cradle strap's segments
N_HANGER = 5
PX_MM = 0.43                # a pixel at the closest view the budget is derived from (the cowboy hat's: a 0.4 m portrait
#                             at 1080 lines)
# each island's texel density beside the outside's (hidden when worn: the inside, the under face, the suspension)
SHARES = dict(cap=1.0, wall=1.0, flange=1.0, under=0.5, inner_wall=0.3, inner_cap=0.3, boss_face=1.0, boss_top=1.0,
              boss_side=1.0, shelf_face=1.0, shelf_top=1.0, shelf_side=1.0, slot=0.6, band_out=0.6, band_in=0.6,
              strap=0.6, hanger=0.6, lug=0.8)
UV_ORDER = None             # the recorded placing order and density (set after the first search: seconds instead)
UV_PPM = None
# the long curved islands cut into KEYSTONES by plan angle (pieces a mirror half): whole, the half wall flattened to an
# annulus sector of about 80 degrees and the thin flange and under face to half rings, and the pack stopped at 65.0 %
# (the gate is 75; the cowboy hat's brim the same: "30-degree keystones nest")
SPLIT = dict(wall=2, flange=4, under=4, inner_wall=2)


def rib_line_x(i, yy, spec=SPEC):
    """the plan distance from the midplane of the cap's x-line i (|i| <= 6: the ribs' own lines) at the height yy
    over the waist: 0 the midline, 1 / 2 the centre rib's crest edge and foot, 3 / 4 a side rib's inner foot and
    crest edge, 5 / 6 its outer crest edge and foot. Signed like i"""
    a = abs(int(i))
    xs = side_rib_x(yy, spec)
    (tc, ts), (fc, fs) = spec['rib_top'], spec['rib_foot']
    x = (0.0 * xs, tc + 0.0 * xs, fc + 0.0 * xs, xs - fs, xs - ts, xs + ts, xs + fs)[a]
    return np.sign(i) * x


def _outer(u, v, spec):
    """the shell's OUTER and INNER faces over the plan point (u, v), and the height over the waist of the un-ribbed
    mid-surface there"""
    d = dims(spec)
    P, N = dome_frame(u, v, spec)
    yy = dome_base(u, v, spec)[0][..., 1] - d['y_w']
    return P + 0.5 * d['t'] * N, P - 0.5 * d['t'] * N, yy


def cap_grid(spec=SPEC):
    """the cap's grid in plan: (2 NX + 1, 2 NZ + 1) points (u, v), index [i + NX, j + NZ]: i across (x), j along (z)"""
    d = dims(spec)
    k = CAP_ROUND
    U = np.zeros((2 * NX + 1, 2 * NZ + 1))
    Vv = np.zeros_like(U)
    for j in range(-NZ, NZ + 1):
        b = j / NZ
        for i in range(-NX, NX + 1):
            if abs(i) <= 6:
                x = 0.0
                for _ in range(5):                                       # the line's x with its own height
                    a = x / (CAP_U * d['rx'])
                    v = CAP_V * b * np.sqrt(1.0 - 0.5 * k * a * a)
                    yy = float(dome_base(np.array(x / d['rx']), np.array(v), spec)[0][1] - d['y_w'])
                    x = float(rib_line_x(i, yy, spec))
                U[i + NX, j + NZ], Vv[i + NX, j + NZ] = x / d['rx'], v
            elif abs(i) == NX:
                U[i + NX, j + NZ] = np.sign(i) * CAP_U * np.sqrt(1.0 - 0.5 * k * b * b)
                Vv[i + NX, j + NZ] = CAP_V * b * np.sqrt(1.0 - 0.5 * k)
        for s in (-1, 1):                                                # the free line: midway to the edge
            U[s * 7 + NX, j + NZ] = 0.5 * (U[s * 6 + NX, j + NZ] + U[s * 8 + NX, j + NZ])
            Vv[s * 7 + NX, j + NZ] = 0.5 * (Vv[s * 6 + NX, j + NZ] + Vv[s * 8 + NX, j + NZ])
    return U, Vv


def cap_ring():
    """the cap's edge as a loop of K_LOW grid indices (i, j), from the front's middle toward the wearer's left, the
    back, the right"""
    r = [(i, NZ) for i in range(0, NX + 1)] + [(NX, j) for j in range(NZ - 1, -NZ, -1)]
    r += [(i, -NZ) for i in range(NX, -NX - 1, -1)] + [(-NX, j) for j in range(-NZ + 1, NZ)]
    r += [(i, NZ) for i in range(-NX, 0)]
    assert len(r) == K_LOW
    return r


def wall_columns(spec=SPEC):
    """the wall's rings in plan: for the cap's edge and each height of WALL_Y and the waist, the K_LOW plan points
    (u, v). A column on a rib's line (the front's and the back's |i| <= 6) keeps the line's x down to where the ribs
    are gone, then runs straight down; every other column turns evenly from its place on the cap's edge to its place
    on the waist (the corners keep their plan angle, the sides' columns are spread evenly between the corners).
    Returns uv (n_rings, K, 2), the heights (n_rings, K) and the waist's plan angles (K,), unwrapped"""
    d = dims(spec)
    Ug, Vg = cap_grid(spec)
    ring = cap_ring()
    K = K_LOW
    uc = np.array([Ug[i + NX, j + NZ] for i, j in ring])
    vc = np.array([Vg[i + NX, j + NZ] for i, j in ring])
    yc = dome_base(uc, vc, spec)[0][:, 1] - d['y_w']
    phi_c = np.unwrap(np.arctan2(uc, vc))
    rib = np.array([abs(j) == NZ and abs(i) <= 6 for i, j in ring])
    y_f = spec['rib_fade'][0]
    # the waist's plan angles: the four corners keep theirs, every other column stands EVENLY between its corners
    # (5.5 degrees apart across the front and the back, 11.5 along the sides). (First try, refused on the flat-shaded
    # picture: the ribs' columns run straight down to the waist: 13 of them inside +- 20 degrees and one vertex
    # between there and the corner, so the peak's outline was a polygon with five corners)
    phi_w = np.full(K, np.nan)
    for k, (i, j) in enumerate(ring):
        if abs(i) == NX and abs(j) == NZ:
            phi_w[k] = phi_c[k]
    # unwrap the known ones along the loop (the back's lie near pi, the right's near 3 pi / 2 .. 2 pi)
    for k in range(K):
        if not np.isnan(phi_w[k]):
            while phi_w[k] - phi_c[k] > np.pi:
                phi_w[k] -= 2.0 * np.pi
            while phi_w[k] - phi_c[k] < -np.pi:
                phi_w[k] += 2.0 * np.pi
    known = np.nonzero(~np.isnan(phi_w))[0]
    for k in range(K):                                                   # the rest: evenly between their neighbours
        if np.isnan(phi_w[k]):
            lo = known[known < k].max() if (known < k).any() else known[-1] - K
            hi = known[known > k].min() if (known > k).any() else known[0] + K
            p_lo = phi_w[lo % K] - (2.0 * np.pi if lo < 0 else 0.0)
            p_hi = phi_w[hi % K] + (2.0 * np.pi if hi >= K else 0.0)
            phi_w[k] = p_lo + (p_hi - p_lo) * (k - lo) / (hi - lo)
    ys = list(WALL_Y) + [0.0]
    uv = [np.column_stack([uc, vc])]
    hh = [yc]
    for y in ys:
        rho = float(rho_at_height(y, spec))
        u = np.zeros(K)
        v = np.zeros(K)
        for k, (i, j) in enumerate(ring):
            if rib[k] and y >= y_f:
                x = float(rib_line_x(i, y, spec))
                u[k] = x / d['rx']
                v[k] = np.sign(j) * np.sqrt(max(rho * rho - u[k] * u[k], 0.0))
            elif rib[k]:
                # under the ribs: from the line's own angle where the ribs are gone to its even place on the waist
                rf = float(rho_at_height(y_f, spec))
                uf = float(rib_line_x(i, y_f, spec)) / d['rx']
                pf = np.arctan2(uf, np.sign(j) * np.sqrt(max(rf * rf - uf * uf, 0.0)))
                pf += 2.0 * np.pi * np.round((phi_w[k] - pf) / (2.0 * np.pi))
                ph = pf + (phi_w[k] - pf) * (y_f - y) / y_f
                u[k], v[k] = rho * np.sin(ph), rho * np.cos(ph)
            else:
                s = (yc[k] - y) / yc[k]
                ph = phi_c[k] + (phi_w[k] - phi_c[k]) * s
                u[k], v[k] = rho * np.sin(ph), rho * np.cos(ph)
        for k, (i, j) in enumerate(ring):
            if abs(i) == 7 and abs(j) == NZ:
                # the free line beside the ribs stands midway between its two neighbours at every height (the last
                # rib line bows in to +- 20 degrees where the ribs end: held at its own angle, the cell between
                # them was 18.5 degrees wide there, 1.2 mm of sag)
                pa, pb = np.arctan2(u[k - 1], v[k - 1]), np.arctan2(u[(k + 1) % K], v[(k + 1) % K])
                pb += 2.0 * np.pi * np.round((pa - pb) / (2.0 * np.pi))
                u[k], v[k] = rho * np.sin(0.5 * (pa + pb)), rho * np.cos(0.5 * (pa + pb))
        uv.append(np.column_stack([u, v]))
        hh.append(np.full(K, y))
    return np.array(uv), np.array(hh), np.arctan2(uv[-1][:, 0], uv[-1][:, 1])


def _strip(a, b):
    """the quads between two loops of vertex ids (closed)"""
    a, b = np.asarray(a), np.asarray(b)
    return np.stack([a, np.roll(a, -1), np.roll(b, -1), b], -1)


def shell_low(spec=SPEC):
    """the shell's low: V (n, 3), quads [dict(q (4,), part 'out' | 'in', island, col (its column 0 .. K - 1 round
    the hat, or the cap's cell), half 'R' | 'L')], the vertex mirror map, and the rings' ids (for the reports)"""
    from . import soft_common as SC
    d = dims(spec)
    K = K_LOW
    t = d['t']
    V = []

    def add(P):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        i0 = len(V)
        V.extend(P)
        return np.arange(i0, i0 + len(P))
    Ug, Vg = cap_grid(spec)
    Po, Pi, _ = _outer(Ug, Vg, spec)                                     # (2 NX + 1, 2 NZ + 1, 3)
    g_out = add(Po).reshape(2 * NX + 1, 2 * NZ + 1)
    g_in = add(Pi).reshape(2 * NX + 1, 2 * NZ + 1)
    ring = cap_ring()
    uvr, hh, a_w = wall_columns(spec)
    rings_o = [np.array([g_out[i + NX, j + NZ] for i, j in ring])]
    rings_i = {None: np.array([g_in[i + NX, j + NZ] for i, j in ring])}
    for r in range(1, len(uvr)):
        Po, Pi, _ = _outer(uvr[r][:, 0], uvr[r][:, 1], spec)
        rings_o.append(add(Po))
        y = float(hh[r][0])
        if y in INNER_Y or y == 0.0:
            rings_i[y] = add(Pi)
    # the flange: the waist's own angles carried out: fillet's end, floor's end, the lip's edge (upper, under)
    ft = flange_terms(a_w, spec)
    fl_o, fl_u = [], []
    for q in (ft['q1'], ft['q2']):
        P, N, _ = flange_frame(a_w, q, spec)
        fl_o.append(add(P + 0.5 * t * N))
        fl_u.append(add(P - 0.5 * t * N))
    P, N, T = flange_frame(a_w, ft['q4'], spec)
    e_up = add(P + 0.5 * t * N + EDGE_OUT * T)
    e_dn = add(P - 0.5 * t * N + EDGE_OUT * T)
    e_dn2 = add(P - 0.5 * t * N + EDGE_OUT * T)                           # the under face's own copy (a hard edge)
    V = np.array(V)
    # its own mirror in x to the bit
    from scipy.spatial import cKDTree
    dist, mir = cKDTree(V).query(V * [-1.0, 1.0, 1.0])
    assert dist.max() < 1.0e-7, f'the shell low is not its own mirror ({dist.max() * 1e6:.3f} um)'
    # (the two copies of the under edge find each other's twin: keep each with its own)
    for a_ in (e_dn, e_dn2):
        mir[a_] = a_[(K - np.arange(K)) % K]
    V = 0.5 * (V + V[mir] * [-1.0, 1.0, 1.0])
    V[mir == np.arange(len(V)), 0] = 0.0
    quads = []

    def put(Q, part, island, cols):
        for q, c in zip(np.asarray(Q).reshape(-1, 4), cols):
            quads.append(dict(q=q, part=part, island=island, col=int(c)))
    kk = np.arange(K)
    cap_cells = [(i, j) for i in range(-NX, NX) for j in range(-NZ, NZ)]
    cq = lambda g: np.array([[g[i + NX, j + NZ], g[i + 1 + NX, j + NZ], g[i + 1 + NX, j + 1 + NZ], g[i + NX, j + 1 + NZ]]
                             for i, j in cap_cells])
    cap_col = [0 if i >= 0 else K - 1 for i, j in cap_cells]              # (a cell's half: left = low columns)
    put(cq(g_out), 'out', 'cap', cap_col)
    for r in range(len(rings_o) - 1):
        put(_strip(rings_o[r], rings_o[r + 1]), 'out', 'wall', kk)
    put(_strip(rings_o[-1], fl_o[0]), 'out', 'flange', kk)
    put(_strip(fl_o[0], fl_o[1]), 'out', 'flange', kk)
    put(_strip(fl_o[1], e_up), 'out', 'flange', kk)
    put(_strip(e_up, e_dn), 'out', 'flange', kk)
    put(_strip(e_dn2, fl_u[1]), 'in', 'under', kk)
    put(_strip(fl_u[1], fl_u[0]), 'in', 'under', kk)
    put(_strip(fl_u[0], rings_i[0.0]), 'in', 'under', kk)
    seq = [rings_i[0.0]] + [rings_i[y] for y in sorted(INNER_Y)] + [rings_i[None]]
    for a_, b_ in zip(seq[:-1], seq[1:]):
        put(_strip(a_, b_), 'in', 'inner_wall', kk)
    put(cq(g_in), 'in', 'inner_cap', cap_col)
    # the winding: the outside faces away from the hat's middle, the inside toward it
    c0 = np.array([0.0, 0.04, 0.0])
    for part, flip in (('out', False), ('in', True)):
        idx = [n for n, q in enumerate(quads) if q['part'] == part]
        Q = SC.orient(np.array([quads[n]['q'] for n in idx]), V, centre=c0)
        if flip:
            Q = Q[:, ::-1].copy()
        for n, q in zip(idx, Q):
            quads[n]['q'] = q
    for q in quads:
        q['half'] = 'L' if q['col'] < K // 2 else 'R'
    # the keystones (SPLIT): a quad's piece by the plan angle of its column's middle on the RIGHT half (a left quad
    # takes its mirror twin's, column K - 1 - c, so the halves stack piece on piece)
    ar = np.where(a_w > 0.0, a_w - 2.0 * np.pi, a_w)                    # the right half's angles in [-pi, 0]
    ar[0] = 0.0
    for q in quads:
        n = SPLIT.get(q['island'])
        if not n:
            continue
        c = q['col'] if q['half'] == 'R' else K - 1 - q['col']
        mid = 0.5 * (ar[c] + (ar[(c + 1) % K] if (c + 1) % K else 0.0))
        q['island'] = f"{q['island']}_{int(np.clip(np.floor((mid + np.pi) / (np.pi / n)), 0, n - 1))}"
    return V, quads, mir, dict(g_out=g_out, g_in=g_in, rings_o=rings_o, rings_i=rings_i, fl_o=fl_o, fl_u=fl_u,
                               e_up=e_up, e_dn=e_dn, a_w=a_w, uvr=uvr, hh=hh)


def _flatten(V, Q, arap_iters=8):
    """an island's quads (ids into V) unwrapped on the triangles of their shorter diagonals: LSCM, then the ARAP
    depth with the smallest worst-direction footprint among those that lie flat (cowboy_hat.flatten's rule, top_hat's
    before it), turned to its least-area box, in METRES (1 UV unit = 1 m of surface). Returns {vertex id: (u, v)} and
    dict(fp, arap, aniso (p95 of the stretch ratio))"""
    from .. import uv as U
    from ..species import red_tailed_hawk_uv as HU
    Q = np.asarray(Q, np.int64)
    vs = np.unique(Q)
    loc = -np.ones(int(vs.max()) + 1, np.int64)
    loc[vs] = np.arange(len(vs))
    P = V[vs]
    Ql = loc[Q]
    s = (np.linalg.norm(P[Ql[:, 0]] - P[Ql[:, 2]], axis=1) <= np.linalg.norm(P[Ql[:, 1]] - P[Ql[:, 3]], axis=1))[:, None]
    Fl = np.concatenate([np.where(s, Ql[:, [0, 1, 2]], Ql[:, [0, 1, 3]]), np.where(s, Ql[:, [0, 2, 3]], Ql[:, [1, 2, 3]])])
    uv = U.lscm(P, Fl)
    best, cand, done = None, uv, 0
    for it in (0, 2, max(arap_iters // 2, 3), arap_iters):
        if it > done:
            cand, done = U.arap(P, Fl, cand, it - done), it
        if U.self_overlap(cand, Fl):
            continue
        fp = U.footprint(P, Fl, cand)
        if best is None or fp < best[0]:
            best = (fp, it, cand)
    if best is None:
        best = (U.footprint(P, Fl, uv), 0, uv)
    uv = np.array(best[2], np.float64)
    d1, d2 = uv[Fl[:, 1]] - uv[Fl[:, 0]], uv[Fl[:, 2]] - uv[Fl[:, 0]]
    if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
        uv[:, 0] = -uv[:, 0]
    uv = HU._min_box(uv)
    uv = uv / U.island_density(P, Fl, uv)
    s1, s2, ok = U.stretch(P, Fl, uv)
    return ({int(v): uv[i] for i, v in enumerate(vs)},
            dict(fp=float(best[0]), arap=int(best[1]), aniso=float(np.percentile((s1 / s2)[ok], 95))))


def _wall_point(a0, s, y, spec):
    """the point of the wall's MID-surface at the height y (prop frame) whose offset along the waist's tangent at the
    plan angle a0 is s (m): where a boss's back edge lies, inside the wall's thickness"""
    d = dims(spec)
    Pw, _, Tw = waist(np.array(a0), spec)
    rho = float(rho_at_height(max(y - d['y_w'], 0.0), spec))
    aa = a0 + s / float(np.hypot(Pw[0], Pw[2]))
    for _ in range(4):
        P = dome_base(np.array(rho * np.sin(aa)), np.array(rho * np.cos(aa)), spec)[0]
        aa -= (float((P - Pw) @ Tw) - s) / float(np.hypot(P[0], P[2]))
    P = np.array(dome_base(np.array(rho * np.sin(aa)), np.array(rho * np.cos(aa)), spec)[0])
    P[1] = y
    return P - Tw * (float((P - Pw) @ Tw) - s)                          # exactly in the plane


def _fillet_point(a0, s, share, spec):
    """the point of the flange's MID-surface whose offset along the waist's tangent at the plan angle a0 is s, at
    `share` of the fillet's arc (0 the waist, 1 where the floor begins): the path a boss's side face takes back to
    the wall INSIDE the shell's thickness (a straight edge there stood 2.9 mm under the rim's inside)"""
    Pw, _, Tw = waist(np.array(a0), spec)
    aa = a0 + s / float(np.hypot(Pw[0], Pw[2]))

    def at(aa):
        q = share * float(flange_terms(np.array(aa), spec)['q1'])
        return np.array(flange_frame(np.array(aa), np.array(q), spec)[0])
    for _ in range(5):
        P = at(aa)
        aa -= (float((P - Pw) @ Tw) - s) / float(np.hypot(P[0], P[2]))
    P = at(aa)
    return P - Tw * (float((P - Pw) @ Tw) - s)


def boss_parts(b, spec=SPEC, slot=None, primary=False):
    """a boss's (or the slot shelf's) parts: its face, its top (two halves; the shelf's: a frame round the slot),
    its two sides, each a part of its own (hard edges, a UV shell each); the slot's four walls and floor. UVs by
    construction in metres: the face (along the rim, up from its top edge), the top (along, back from the face), a
    side (back from the face, up)"""
    d = dims(spec)
    kind = b['kind']
    ins = 0.0003                                     # the low's flat faces stand this far inside the rounded box
    a0 = b['a']
    Tw, up, Nw = b['axes'][:, 0], b['axes'][:, 1], b['axes'][:, 2]
    Pw = waist(np.array(a0), spec)[0]
    w2, r1 = 0.5 * b['w'] - ins, b['r_face'] - ins
    yt, yb = b['y_top'] - ins, b['y_bot']
    f = lambda s, y, r=r1: Pw + Tw * s + Nw * r + up * (y - d['y_w'])
    A, B, C, D, Mf = f(-w2, yb), f(w2, yb), f(w2, yt), f(-w2, yt), f(0.0, yt)
    El, Em, Er = (_wall_point(a0, s, yt, spec) for s in (-w2, 0.0, w2))
    # a side's way back to the wall runs on the shell's MID-surface: the waist, the fillet's middle, the floor's start
    Wl, Wr = (_wall_point(a0, s, d['y_w'], spec) for s in (-w2, w2))
    Hl, Hr = (_fillet_point(a0, s, 0.5, spec) for s in (-w2, w2))
    Kl, Kr = (_fillet_point(a0, s, 1.0, spec) for s in (-w2, w2))
    dep = lambda P: r1 - float((P - Pw) @ Nw)        # how far behind the face a point lies
    alo = lambda P: float((P - Pw) @ Tw)
    out = []

    def part(name, pts, uvs, quads, island, toward):
        Vp = np.array(pts)
        Q = np.array(quads)
        n = np.cross(Vp[Q[:, 2]] - Vp[Q[:, 0]], Vp[Q[:, 3]] - Vp[Q[:, 1]]).sum(0)
        if n @ toward < 0.0:
            Q = Q[:, ::-1].copy()
        out.append(dict(name=f'{b["name"]}_{name}', region=R_BOSS, V=Vp, Q=Q, uv=np.array(uvs), island=island,
                        primary=primary, attr=np.zeros((len(Vp), 4))))
    part('face', [A, B, C, D], [(alo(P), P[1] - yt) for P in (A, B, C, D)], [[0, 1, 2, 3]], f'{kind}_face', Nw)
    top_uv = lambda P: (alo(P), dep(P))
    if slot is None:
        pts = [D, Mf, C, Er, Em, El]
        part('top', pts, [top_uv(P) for P in pts], [[0, 1, 4, 5], [1, 2, 3, 4]], f'{kind}_top', up)
    else:
        sl, sw, sd = spec['slot']
        rs = float((slot['c'] - Pw) @ Nw)                                 # the slot's middle, out from the waist
        h = [f(-0.5 * sl, yt, rs + 0.5 * sw), f(0.5 * sl, yt, rs + 0.5 * sw), f(0.5 * sl, yt, rs - 0.5 * sw),
             f(-0.5 * sl, yt, rs - 0.5 * sw)]                            # front left, front right, back right, back left
        hm = 0.5 * (h[2] + h[3])
        pts = [D, C, Er, Em, El] + h + [hm]                              # 0 D 1 C 2 Er 3 Em 4 El 5..8 the hole 9 hm
        part('top', pts, [top_uv(P) for P in pts],
             [[0, 1, 6, 5], [1, 2, 7, 6], [2, 3, 9, 7], [3, 4, 8, 9], [4, 0, 5, 8]], f'{kind}_top', up)
        # the slot: its walls as one strip round the hole (u along the rim of the hole, v down), then its floor
        lo = [p - up * sd for p in h]
        per = np.concatenate([[0.0], np.cumsum([np.linalg.norm(h[(k + 1) % 4] - h[k]) for k in range(4)])])
        pts, uvs, quads = [], [], []
        for k in range(4):
            i0 = len(pts)
            pts += [h[k], h[(k + 1) % 4], lo[(k + 1) % 4], lo[k]]
            uvs += [(per[k], 0.0), (per[k + 1], 0.0), (per[k + 1], -sd), (per[k], -sd)]
            quads.append([i0, i0 + 1, i0 + 2, i0 + 3])
        # (wound by the first wall: it faces the slot's middle)
        mid = np.mean(h, 0) - up * 0.5 * sd
        Vp = np.array(pts)
        Q = np.array(quads)
        n0 = np.cross(Vp[Q[0, 2]] - Vp[Q[0, 0]], Vp[Q[0, 3]] - Vp[Q[0, 1]])
        if n0 @ (mid - Vp[Q[0]].mean(0)) < 0.0:
            Q = Q[:, ::-1].copy()
        out.append(dict(name=f'{b["name"]}_slot', region=R_BOSS, V=Vp, Q=Q, uv=np.array(uvs), island='slot',
                        primary=primary, attr=np.zeros((len(Vp), 4))))
        part('slot_floor', lo, [(alo(P) + 0.05, dep(P)) for P in lo], [[0, 1, 2, 3]], 'slot', up)
    # a side: two quads, its lower back edge on the shell's mid-surface (A D El K, then K El W H)
    sa = [A, D, El, Kl, Wl, Hl]
    part('side_a', sa, [(dep(P), P[1] - yt) for P in sa], [[0, 1, 2, 3], [3, 2, 4, 5]], f'{kind}_side', -Tw)
    sb = [B, Kr, Er, C, Hr, Wr]
    part('side_b', sb, [(dep(P), P[1] - yt) for P in sb], [[0, 1, 2, 3], [1, 4, 5, 2]], f'{kind}_side', Tw)
    return out


def band_parts(spec=SPEC):
    """the headband with its brow pad: a thin closed section round the head opening (K_BAND columns): the outer face,
    the inner face (the pad's cloth in front), its top and bottom edges. The right half's faces are the primaries (the
    left their mirrors); an EDGE takes a 2 mm border of the face it belongs to (the pad's edges the inner face's, the
    band's the outer face's): it is that face's own material, and a strip 2 mm wide and 0.6 m long has no place on a
    sheet. attr = (the arc length from the front, the height over the band's lower edge, the pad's share, the face:
    +1 outer / -1 inner)"""
    # the columns stand where the section changes: at both ends of the pad's ramp and of the pin-lock's step (evenly
    # spaced at 15 degrees the low ramped over 15 degrees what the block-out does in 4 and in 1.5: 1.8 - 1.95 mm off)
    half = [0.0, 15.0, 30.0, 45.0, spec['pad_half'] - 4.0, spec['pad_half'], 72.0, 88.0, 104.0, 120.0, 135.0,
            180.0 - spec['lock_half'], 180.0 - spec['lock_half'] + 1.5, 165.0, 180.0]
    a = np.radians(np.array(half + [360.0 - x for x in half[-2::-1]]))
    K = len(a) - 1
    ht, y0, y1, pad = band_terms(a, spec)
    Po0, Po1 = band_point(a, y0, ht, spec)[0], band_point(a, y1, ht, spec)[0]
    Pi0, Pi1 = band_point(a, y0, -ht, spec)[0], band_point(a, y1, -ht, spec)[0]
    for P in (Po0, Po1, Pi0, Pi1):                                       # the loop closes on itself to the bit
        P[K] = P[0]
        P[:] = 0.5 * (P + P[::-1] * [-1.0, 1.0, 1.0])                    # and is its own mirror
    mid = 0.5 * (Po0 + Pi0)
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(mid, axis=0), axis=1))])
    s = np.where(np.arange(K + 1) <= K // 2, arc, arc[K] - arc)          # from the front, each way round
    out = []
    brd = 0.002
    for half, cols, prim in (('L', range(0, K // 2), False), ('R', range(K // 2, K), True)):
        cols = list(cols)
        idx = np.array(cols + [cols[-1] + 1])
        n = len(idx)
        is_pad = np.array([0.5 * (pad[c] + pad[c + 1]) > 0.5 for c in cols])

        def strip(name, Pa, Pb, uva, uvb, island, region, toward_out, face):
            Vp = np.vstack([Pa[idx], Pb[idx]])
            Q = np.array([[i, i + 1, n + i + 1, n + i] for i in range(n - 1)])
            nrm = np.cross(Vp[Q[:, 2]] - Vp[Q[:, 0]], Vp[Q[:, 3]] - Vp[Q[:, 1]])
            c = Vp[Q].mean(1)
            ref = toward_out if toward_out is not None else None
            sgn = (nrm * (c * [1.0, 0.0, 1.0] if ref is None else ref)).sum()
            if (sgn < 0.0) != (face < 0 and toward_out is None):
                Q = Q[:, ::-1].copy()
            at = np.column_stack([np.concatenate([s[idx], s[idx]]), np.concatenate([uva[:, 1], uvb[:, 1]]),
                                  np.concatenate([pad[idx], pad[idx]]), np.full(2 * n, float(face))])
            isl = island if isinstance(island, list) else [island] * (n - 1)
            reg = region if isinstance(region, (list, np.ndarray)) else [region] * (n - 1)
            for r in sorted(set(reg)):                                   # one part a region
                m = np.array([x == r for x in reg])
                out.append(dict(name=f'band_{name}_{half}_{REGIONS[r]}', region=r, V=Vp, Q=Q[m],
                                uv=np.vstack([uva, uvb]), island=[x for x, k in zip(isl, m) if k],
                                primary=prim and name in ('out', 'in'), attr=at, group=f'band_{name}'))
        hb = y0[idx]
        uo0, uo1 = np.column_stack([s[idx], y0[idx] - hb]), np.column_stack([s[idx], y1[idx] - hb])
        strip('out', Po0, Po1, uo0, uo1, 'band_out', R_BAND, None, +1)
        strip('in', Pi1, Pi0, uo1, uo0, 'band_in', [R_PAD if p else R_BAND for p in is_pad], None, -1)
        # the edges: a border of the face they belong to
        e_isl = ['band_in' if p else 'band_out' for p in is_pad]
        e_reg = [R_PAD if p else R_BAND for p in is_pad]
        up = np.array([0.0, 1.0, 0.0])
        strip('top', Po1, Pi1, uo1, uo1 - [0.0, brd], e_isl, e_reg, up, +1)
        strip('bot', Pi0, Po0, uo0 + [0.0, brd], uo0, e_isl, e_reg, -up, +1)
    return out


def ribbon_parts(name, P, Nn, Wd, width, thick, island, region, primary, attr3=0.0):
    """a flat strip (a hanger, a cradle strap) as two faces on the block-out's own two faces: the one toward the head
    (along +Nn) and the one toward the shell; UVs (the arc length along it, the place across it) in metres, the same
    on both faces. attr = (along, across, attr3, 0)"""
    Wd = np.broadcast_to(np.asarray(Wd, np.float64), P.shape)
    n = len(P)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    out = []
    for face, sg in (('head', 1.0), ('shell', -1.0)):
        c = P + sg * 0.5 * thick * Nn
        Vp = np.vstack([c - 0.5 * width * Wd, c + 0.5 * width * Wd])
        uv = np.vstack([np.column_stack([s, np.full(n, -0.5 * width)]), np.column_stack([s, np.full(n, 0.5 * width)])])
        Q = np.array([[i, i + 1, n + i + 1, n + i] for i in range(n - 1)])
        nrm = np.cross(Vp[Q[:, 2]] - Vp[Q[:, 0]], Vp[Q[:, 3]] - Vp[Q[:, 1]])
        if (nrm * (sg * Nn[:-1])).sum() < 0.0:
            Q = Q[:, ::-1].copy()
        out.append(dict(name=f'{name}_{face}', region=region, V=Vp, Q=Q, uv=uv, island=island,
                        primary=primary and face == 'head',
                        attr=np.column_stack([uv, np.full(2 * n, attr3), np.zeros(2 * n)])))
    return out


def lug_parts(lg, spec=SPEC, primary=False):
    """a chin-strap lug: a tab with its hole through it (an octagon): the two faces, the rim, the hole's wall. The
    faces' UVs are the tab's own plan (metres); the rim and the hole's wall take a border of the face (its own
    material; a strip 2 mm wide has no place on a sheet)"""
    Tw, up, Nw = lg['axes'][:, 0], lg['axes'][:, 1], lg['axes'][:, 2]
    w2, h2, t2 = lg['half']
    c = lg['c']
    hc = 0.5 * (lg['hole'][0] + lg['hole'][1])
    hx, hy = float((hc - c) @ Tw), float((hc - c) @ up)
    r = spec['lug'][3]
    o2 = np.array([(-w2, -h2), (0.0, -h2), (w2, -h2), (w2, hy), (w2, h2), (0.0, h2), (-w2, h2), (-w2, hy)])
    ang = np.arctan2(o2[:, 1] - hy, o2[:, 0] - hx)
    h2d = np.column_stack([hx + r * np.cos(ang), hy + r * np.sin(ang)])
    to3 = lambda p2, z: c + p2[:, 0:1] * Tw + p2[:, 1:2] * up + z * Nw
    out = []
    k = np.arange(8)
    k1 = (k + 1) % 8
    brd = 0.0015
    pull = lambda p2, sgn: p2 + sgn * brd * (p2 - [hx, hy]) / np.linalg.norm(p2 - [hx, hy], axis=1, keepdims=True)
    for face, z, flip in (('front', t2, False), ('back', -t2, True)):
        Vp = np.vstack([to3(o2, z), to3(h2d, z)])
        Q = np.stack([k, k1, 8 + k1, 8 + k], -1)
        nrm = np.cross(Vp[Q[:, 2]] - Vp[Q[:, 0]], Vp[Q[:, 3]] - Vp[Q[:, 1]]).sum(0)
        if (nrm @ Nw < 0.0) != flip:
            Q = Q[:, ::-1].copy()
        out.append(dict(name=f'{lg["name"]}_{face}', region=R_LUG, V=Vp, Q=Q, uv=np.vstack([o2, h2d]), island='lug',
                        primary=primary and face == 'front', attr=np.zeros((16, 4))))
    for nm, p2, uva, uvb, inward in (('rim', o2, o2, pull(o2, -1.0), False), ('hole', h2d, h2d, pull(h2d, 1.0), True)):
        Vp = np.vstack([to3(p2, t2), to3(p2, -t2)])
        Q = np.stack([k, k1, 8 + k1, 8 + k], -1)
        nrm = np.cross(Vp[Q[:, 2]] - Vp[Q[:, 0]], Vp[Q[:, 3]] - Vp[Q[:, 1]])
        cq = Vp[Q].mean(1) - (c + hx * Tw + hy * up)
        if ((nrm * cq).sum() < 0.0) != inward:
            Q = Q[:, ::-1].copy()
        out.append(dict(name=f'{lg["name"]}_{nm}', region=R_LUG, V=Vp, Q=Q, uv=np.vstack([uva, uvb]), island='lug',
                        primary=False, attr=np.zeros((16, 4))))
    return out


def build_low(spec=SPEC, log=print):
    """the whole low as soft_common parts (+ info): the shell (its right half's islands flattened, the left half
    taking its twin's UVs), the bosses and shelves (the front right boss and the right shelf are the primaries: the
    front bosses stand deepest in the peak's floor, so every other boss's UVs lie inside theirs), the headband, the
    hangers, the cradle's straps, the lugs"""
    V, quads, mir, sh = shell_low(spec)
    parts, stats = [], {}
    zero = np.zeros((len(V), 4))
    for part, region in (('out', R_SHELL), ('in', R_INSIDE)):
        uvI = {}
        for nm in sorted({q['island'] for q in quads if q['part'] == part}):
            Qr = np.array([q['q'] for q in quads if q['part'] == part and q['island'] == nm and q['half'] == 'R'])
            uvI[nm], stats[nm] = _flatten(V, Qr)
        for half in 'RL':
            sel = [q for q in quads if q['part'] == part and q['half'] == half]
            src = (lambda v: int(v)) if half == 'R' else (lambda v: int(mir[v]))
            uvc = np.array([[uvI[q['island']][src(v)] for v in q['q']] for q in sel])
            parts.append(dict(name=f'shell_{part}_{half}', region=region, V=V, Q=np.array([q['q'] for q in sel]),
                              uv=uvc, island=[q['island'] for q in sel], primary=half == 'R', attr=zero,
                              group=f'shell_{part}'))
    boxes, slots = boss_boxes(spec)
    slot_of = {s['name'][4:]: s for s in slots}                           # 'slot_L' -> '_L'
    for b in boxes:
        sl = slot_of.get(b['name'][5:]) if b['kind'] == 'shelf' else None
        parts += boss_parts(b, spec, slot=sl, primary=b['name'] in ('boss_RF', 'shelf_R'))
    parts += band_parts(spec)
    for i, a in enumerate(hanger_angles(spec)):
        P, Nn, Wd = hanger_path(a, spec, n=N_HANGER)
        parts += ribbon_parts(f'hanger_{i}', P, Nn, Wd, spec['hanger_w'], spec['hanger_t'], 'hanger', R_BAND, i == 0,
                              attr3=2.0)
    for k in range(2):
        P, Nn, Wd = strap_path(k, spec, n=N_STRAP + 1)
        parts += ribbon_parts(f'strap_{k}', P, Nn, Wd, spec['strap_w'], spec['strap_t'], 'strap', R_STRAP, k == 0)
    for lg in lug_frames(spec):
        parts += lug_parts(lg, spec, primary=lg['name'] == 'lug_R')
    nq = sum(len(p['Q']) for p in parts)
    log(f'[hard_hat] low: {len(parts)} parts, {nq} quads ({2 * nq} triangles); the shell\'s islands: '
        + ', '.join(f'{k} (fp {v["fp"]:.2f}, aniso p95 {v["aniso"]:.2f}, ARAP {v["arap"]})' for k, v in stats.items()))
    return parts, dict(shell=sh, mir=mir, stats=stats, n_shell_v=len(V))


def smooth_groups(low, parts):
    """the normals SMOOTH across the parts of one group (a part's key `group`: the shell's two mirror halves, the
    headband's two): soft_common.assemble shades each part by itself (a hard edge between parts), which stands a
    crease down the hat's midline; here each group's quads are welded by position and its vertices take the
    area-weighted normals of the whole group"""
    from . import soft_common as SC
    V, Q = low['V'], low['Q']
    grp = np.array([p.get('group', p['name']) for p in parts])[low['part']]
    first, inv = SC.weld(V, tol=1e-7)
    fn = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    Nw = np.array(low['Nw'], np.float64)
    for g in np.unique(grp):
        m = grp == g
        if len({parts[i]['name'] for i in np.unique(low['part'][m])}) < 2:
            continue
        acc = np.zeros((len(first), 3))
        for k in range(4):
            np.add.at(acc, inv[Q[m, k]], fn[m])
        vs = np.unique(Q[m])
        Nw[vs] = SC.unit(acc[inv[vs]])
    low['Nw'] = Nw
    return low


def make_low(size=2048, spec=SPEC, log=print, order=None, ppm=None, tries=16):
    """the low with its UVs as the export's arrays (CPU, about a minute with the pack's search): parts -> assemble ->
    smooth_groups -> pack -> low_arrays. Returns L (V, F, UV, N, TAN, region, primary, ATTR, island, part), the
    assembled low, the parts, info and the pack's record"""
    from . import soft_common as SC
    parts, info = build_low(spec, log)
    low = smooth_groups(SC.assemble(parts), parts)
    share = lambda nm: SHARES[nm] if nm in SHARES else SHARES[nm.rsplit('_', 1)[0]]      # (a keystone: its island's)
    fill, place, dens, od = SC.pack(low, {nm: share(nm) for nm in low['names']}, size=size,
                                    order=order if order is not None else UV_ORDER,
                                    ppm=ppm if ppm is not None else UV_PPM, tries=tries, log=log)
    L = SC.low_arrays(low, place, dens, size)
    log(f'[hard_hat] uv: {len(place)} primary islands of {len(low["names"])} names; {dens:.0f} px/m at {size} '
        f'({1000 / dens:.3f} mm/texel), fill {fill * 100:.1f} %; order {od}')
    return L, low, parts, info, dict(fill=fill, order=od, ppm=dens)


# ============================================================================================ THE MATERIAL PASS
# One set of maps for every colour (HIGH_TO_LOW "Variants": colours are material variants of one set of maps). The
# runtime recolours a prop by palette zone, MULTIPLYING the baked albedo by (the zone's colour / the zone's baked
# median). So the SHELL's zone is baked as its colour TIMES ONE NUMBER per texel (scuffs lighter, dirt and shadowed
# dust darker: no hue of their own): then any colour of shell comes out exact, wear and all. (A brown dirt on a
# yellow shell, tinted to white, turns blue: yellow's blue channel is 0.03, and white asks 27 times that.) The
# safety yellow keeps 0.027 of blue (sRGB 46) for the same reason: 13 levels of it lie under the wear's range, where
# a purer yellow would band the white variant. What kills the gloss (dust, scuffs) is carried by the ROUGHNESS.
MATERIAL = dict(
    seed=11,
    shell=(0.92, 0.64, 0.021),      # safety yellow (linear): sRGB 246 / 210 / 40 (the first, 239 / 190 / 46, read
    #                                 mustard in the judging look beside the reference board's lemon-yellow hat)
    band=(0.76, 0.76, 0.70),        # natural HDPE: the headband, its hangers
    pad=(0.050, 0.050, 0.055),      # the brow pad's charcoal terry
    strap=(0.66, 0.64, 0.56),       # undyed nylon webbing
    soil=(0.16, 0.13, 0.10),        # sweat and site dust on the suspension (its zones are not tinted by default)
    shell_rough=0.20,               # moulded ABS, glossy (the photo shows the shop's windows in it; 0.26 read satin)
    inside_rough=0.52,              # the mould's matte inner face
    band_rough=0.42,
    pad_rough=0.95,
    strap_rough=0.85,
    scuff=1.0,                      # the wear's amounts (0 = a new hat): fine scratches,
    nick=1.0,                       #   the small dents a site leaves,
    dust=1.0,                       #   dust lying on what faces the sky and in the gutter,
    grime=1.0,                      #   dirt held in the corners and rubbed in where hands take the peak
    sweat=1.0,                      #   the suspension's staining
)
VARIANTS = dict(                    # the palette each colour of hat is worn with (accessories.js wear(): opts.palette)
    yellow=dict(),                  # as baked
    white=dict(shell=0xf0efe9),
    orange=dict(shell=0xf26a1b),
)


@wp.struct
class HSurf:
    h: float            # the texture tier's height (m)
    col: wp.vec3        # linear albedo
    rough: float
    fuzz: float         # masks R
    zone: float         # masks B (0 shell, 1/3 suspension, 2/3 pad, 1 webbing)
    wear: wp.vec4       # scuffs, nicks, dust, grime (for the eye)


@wp.func
def _segments(p: wp.vec3, n: wp.vec3, cell: float, width: float, share: float, seed: int, per: int):
    """STRAIGHT scratches: in each cell of a `cell` lattice (a share of the cells) one segment through a random site,
    in a random direction laid into the surface's tangent plane, 0.15 - 0.9 cell long, `width` wide, its ends
    tapered; distances measured in the tangent plane (a segment floating in 3D would cut the shell in dots); `per`
    segments a cell. 0..1. (The stretched-noise scratches before it drew the noise's iso-lines: on the dome's front
    they read as wood grain; one segment a cell covered 0.3 % of the shell: none to see)"""
    q = p / cell
    c0x = int(wp.floor(q[0]))
    c0y = int(wp.floor(q[1]))
    c0z = int(wp.floor(q[2]))
    best = float(0.0)
    for i in range(-1, 2):
        for j in range(-1, 2):
            for k in range(-1, 2):
              for m in range(per):
                cx = c0x + i
                cy = c0y + j
                cz = c0z + k
                r = proc.rnd3(proc.hash3i(cx, cy, cz, seed + 7919 * m))
                r2 = proc.rnd3(proc.hash3i(cx, cy, cz, seed + 101 + 7919 * m))
                if r2[2] < share:
                    site = (wp.vec3(float(cx), float(cy), float(cz)) + r) * cell
                    d = r2 * 2.0 - wp.vec3(1.0, 1.0, 1.0)
                    dt = d - n * wp.dot(d, n)
                    ln = wp.length(dt)
                    if ln > 0.2:
                        dt = dt / ln
                        v = p - site
                        vn = wp.dot(v, n)
                        vt = v - n * vn
                        along = wp.dot(vt, dt)
                        perp = wp.length(vt - dt * along)
                        half = (0.075 + 0.375 * r[0]) * cell
                        if wp.abs(vn) < 0.5 * cell and wp.abs(along) < half:
                            s = proc.smoothstep(width, 0.35 * width, perp) * proc.smoothstep(half, 0.6 * half, wp.abs(along))
                            best = wp.max(best, s * (0.55 + 0.45 * r[1]))
    return best


@wp.func
def _scratch(p: wp.vec3, ax: wp.vec3, ay: wp.vec3, length: float, width: float, seed: int):
    """straight scratches along ax: 0..1 (face_mask.streaks' form). (At smoothstep(0.50, 0.72) the first bake's
    scuffs averaged 0.007 over the shell: no scratch could be seen beside the photo's)"""
    q = wp.vec3(wp.dot(p, ax) / length, wp.dot(p, ay) / width, 0.37 * float(seed))
    return proc.smoothstep(0.28, 0.52, proc.noise3(q, seed))


@wp.func
def hsurf_at(p: wp.vec3, nw: wp.vec3, reg: int, at: wp.vec4, conv: float, convm: float, ao: float, aol: float,
             texel: float, C: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32), seed: int, full: int):
    """the surface at the point p of the low's region reg (nw: the baked normal there, world; at: the vertex
    attributes). full = 0: the height only"""
    ny = nw[1]
    o = HSurf()
    h = float(0.0)
    col = wp.vec3(0.5, 0.5, 0.5)
    rough = float(0.5)
    fuzz = float(0.0)
    zone = float(0.0)
    w_scuff = float(0.0)
    w_nick = float(0.0)
    w_dust = float(0.0)
    w_grime = float(0.0)
    occl = wp.clamp(1.5 * (1.0 - ao) + 3.0 * wp.max(-aol, 0.0), 0.0, 1.0)      # how shut in the place is
    if reg == 0 or reg == 2 or reg == 6:
        # ABS, injection moulded: glossy, a faint orange peel; a site's nicks; fine scratches in three directions,
        # most on what sticks out (the ribs, the bosses, the crown); dust on what faces the sky and in the gutter
        # nicks: small dents a site leaves, held dark by the grime in them (the photo: dark specks 1 - 2 mm, a few
        # to every 10 cm^2). (f1 in lattice units of 12 mm: 0.5 - 1.2 mm dents; at 17 mm cells and 0.03 - 0.075 the
        # first bake had none to see)
        cel = proc.cellular3(p / 0.010, 0.9, seed + 3)
        gate = proc.smoothstep(-0.05, 0.40, proc.noise3(p / 0.045, seed + 5))
        nick = S[5] * gate * proc.smoothstep(0.13, 0.05, cel.f1)
        h = -0.00012 * nick + 0.0000025 * proc.noise3(p / 0.0011, seed + 7) * proc.smoothstep(2.0, 3.5, 0.0011 / texel)
        if full == 1:
            # straight scratches at two scales (the photo, at its own 0.2 mm a pixel: fine ones crowded in patches, a
            # few long ones; three a cell were sparse beside it)
            patch = proc.smoothstep(-0.45, 0.25, proc.noise3(p / 0.04, seed + 19))
            sc = _segments(p, nw, 0.008, 0.00018, 0.90, seed + 11, 5)
            sc = wp.max(sc, 0.8 * _segments(p, nw, 0.020, 0.00024, 0.50, seed + 13, 1))
            proud = proc.smoothstep(-0.2, 1.2, convm) * (0.45 + 0.55 * proc.smoothstep(0.3, 0.9, ny))
            w_scuff = S[4] * sc * patch * (0.55 + 0.45 * proud)
            # a rubbed haze on the sharpest convex edges (the ribs' edges, the lip, the bosses' corners)
            rub = S[4] * proc.smoothstep(1.0, 2.4, conv) * (0.5 + 0.5 * proc.noise3(p / 0.006, seed + 23))
            w_scuff = wp.max(w_scuff, 0.7 * rub)
            # dust: thin on sky-facing plastic in 3-4 cm patches, thick where the gutter and the corners hold it
            lie = proc.smoothstep(0.35, 0.9, ny) * proc.smoothstep(-0.5, 0.5, proc.fbm3(p / 0.035, 3, 2.0, 0.5, seed + 29))
            w_dust = S[6] * wp.clamp(0.35 * lie + 0.9 * occl * proc.smoothstep(0.0, 0.6, ny + 0.4), 0.0, 1.0)
            # grime: in the corners; and where a hand takes the peak (its front edge, prop frame: z > 0.11)
            hand = proc.smoothstep(0.105, 0.145, p[2]) * (0.5 + 0.5 * proc.fbm3(p / 0.012, 2, 2.0, 0.5, seed + 31))
            # dirt held in a few scratches: short dark streaks (the photo's brown lines)
            streak = _segments(p, nw, 0.014, 0.00030, 0.30, seed + 43, 1) * patch
            w_grime = S[7] * wp.clamp(0.75 * occl * occl + 0.35 * hand + 0.8 * streak, 0.0, 1.0)
            w_nick = nick
            # ONE number over the shell's colour (the palette's law above)
            cloud = 0.03 * proc.fbm3(p / 0.05, 2, 2.0, 0.5, seed + 37)
            # (a scratch in coloured ABS scatters: lighter and matte; a nick holds dirt: darker)
            k = wp.exp(cloud) * (1.0 + 0.55 * w_scuff) * (1.0 - 0.40 * nick) * (1.0 - 0.06 * w_dust) * \
                (1.0 - 0.55 * w_grime)
            col = C[0] * k
            # the gloss itself worn unevenly: a haze in hand-sized patches (the photo's dull sheen round its highlight)
            haze = proc.smoothstep(-0.3, 0.6, proc.fbm3(p / 0.05, 2, 2.0, 0.5, seed + 47))
            rough = S[0] + 0.14 * haze + 0.35 * w_scuff + 0.25 * nick
            rough = rough + (0.80 - rough) * w_dust
            rough = rough + (0.70 - rough) * 0.6 * w_grime
    elif reg == 1:
        # the shell's inner face and the rim's under face: the mould's matte texture, no scuffs; dust and grime
        h = 0.000006 * proc.noise3(p / 0.0007, seed + 41) * proc.smoothstep(2.0, 3.5, 0.0007 / texel) + \
            0.000004 * proc.noise3(p / 0.0021, seed + 43)
        if full == 1:
            w_grime = S[7] * wp.clamp(0.6 * occl, 0.0, 1.0) * (0.6 + 0.4 * proc.noise3(p / 0.008, seed + 45))
            k = wp.exp(0.03 * proc.fbm3(p / 0.05, 2, 2.0, 0.5, seed + 47)) * 0.94 * (1.0 - 0.45 * w_grime)
            col = C[0] * k
            rough = S[1] + 0.2 * w_grime
    elif reg == 3:
        # natural HDPE: the headband (at[3] the face: +1 outer, -1 inner) and its hangers (at[2] = 2). The pin-lock's
        # holes: a row along the band's middle over its last 45 mm at the back
        flow = proc.noise3(wp.vec3(at[0] / 0.03, at[1] / 0.0015, 0.0), seed + 51)
        h = 0.000004 * flow * proc.smoothstep(2.0, 3.5, 0.0015 / texel)
        hole = float(0.0)
        if at[2] < 1.5:
            back = S[9] - at[0]
            if back < 0.045 and back > 0.004:
                du = back / 0.008 - wp.floor(back / 0.008) - 0.5
                dv = (at[1] - 0.013) / 0.008
                hole = proc.smoothstep(0.21, 0.15, wp.sqrt(du * du + dv * dv))
        h = h - 0.0004 * hole
        if full == 1:
            sweat = float(0.0)
            if at[3] < 0.0:
                sweat = S[8] * (0.45 + 0.35 * proc.fbm3(p / 0.02, 2, 2.0, 0.5, seed + 53))
            w_grime = wp.clamp(S[7] * 0.7 * occl + sweat, 0.0, 1.0)
            col = M.mix3(C[1] * (1.0 + 0.04 * flow), C[4], 0.55 * w_grime)
            col = M.mix3(col, wp.vec3(0.02, 0.02, 0.02), hole)
            rough = S[2] + 0.25 * w_grime
            zone = 1.0 / 3.0
    elif reg == 4:
        # the brow pad: charcoal terry over foam: loops 0.7 mm apart; a paler salt line near its lower edge
        loops = proc.noise3(p / 0.0007, seed + 61)
        h = 0.00010 * loops * proc.smoothstep(1.5, 3.0, 0.0007 / texel) + 0.00015 * proc.noise3(p / 0.004, seed + 63)
        if full == 1:
            salt = S[8] * proc.smoothstep(0.012, 0.003, at[1]) * proc.smoothstep(-0.3, 0.5, proc.noise3(p / 0.011, seed + 65))
            w_grime = salt
            col = C[2] * (0.8 + 0.35 * loops)
            col = M.mix3(col, wp.vec3(0.30, 0.29, 0.27), 0.35 * salt)
            rough = S[3]
            fuzz = 0.35
            zone = 2.0 / 3.0
    else:
        # the cradle's webbing (at: along, across, metres): a plain weave, 1 mm picks, cords 1.6 mm apart
        pick = wp.cos(6.2831853 * at[0] / 0.0010)
        cord = wp.cos(6.2831853 * at[1] / 0.0016)
        wv = 0.5 + 0.5 * pick * cord
        h = 0.00007 * wv * proc.smoothstep(2.0, 3.5, 0.0010 / texel) + 0.00003 * cord
        if full == 1:
            mid = wp.exp(-(at[1] * at[1]) / (0.006 * 0.006))
            w_grime = S[8] * (0.30 * mid + 0.25 * occl) * (0.6 + 0.4 * proc.noise3(p / 0.013, seed + 71))
            col = C[3] * (0.86 + 0.20 * wv)
            col = M.mix3(col, C[4], 0.6 * w_grime)
            rough = S[10]
            fuzz = 0.22
            zone = 1.0
    o.h = h
    o.col = col
    o.rough = rough
    o.fuzz = fuzz
    o.zone = zone
    o.wear = wp.vec4(w_scuff, w_nick, w_dust, w_grime)
    return o


@wp.kernel
def k_hard(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
           ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32),
           d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_base: wp.array(dtype=wp.vec4),
           d_aol: wp.array(dtype=wp.float32), d_conv: wp.array(dtype=wp.float32),
           d_convm: wp.array(dtype=wp.float32), C: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32),
           texel: float, seed: int, o_alb: wp.array(dtype=wp.vec3), o_nrm: wp.array(dtype=wp.vec3),
           o_orm: wp.array(dtype=wp.vec3), o_mask: wp.array(dtype=wp.vec4), o_wear: wp.array(dtype=wp.vec4),
           o_hit: wp.array(dtype=wp.int32)):
    """face_mask.k_mask's frame (the bake's normal carried, the texture tier's height differenced over the low, the
    roughness widened by the normals' spread inside the texel), with this prop's surface function"""
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
            sf = hsurf_at(pb0, nw, reg, lo.attr, d_conv[tid], d_convm[tid], d_ao[tid], d_aol[tid], texel, C, S,
                          seed, 1)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1:
                pbx = lx.p + lx.n * hb
                pby = ly.p + ly.n * hb
                hx = hsurf_at(pbx, nw, reg, lx.attr, 0.0, 0.0, 1.0, 0.0, texel, C, S, seed, 0).h
                hy = hsurf_at(pby, nw, reg, ly.attr, 0.0, 0.0, 1.0, 0.0, texel, C, S, seed, 0).h
                h0 = hsurf_at(pb0, nw, reg, lo.attr, 0.0, 0.0, 1.0, 0.0, texel, C, S, seed, 0).h
                g = M.surface_grad(pb0, pbx, pby, h0, hx, hy)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            acc_a = acc_a + sf.col
            acc_r = acc_r + wp.clamp(sf.rough, 0.04, 1.0)
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
    o_orm[tid] = wp.vec3(d_ao[tid], wp.clamp(rr, 0.0, 1.0), 0.0)
    o_mask[tid] = acc_k / fh
    o_wear[tid] = acc_w / fh
    o_hit[tid] = 1


def band_arc_half(spec=SPEC):
    """the headband's arc length from the front's middle to the back's (the pin-lock's holes are placed from it)"""
    a = np.linspace(0.0, np.pi, 2001)
    P = band_point(a, np.zeros_like(a), 0.0, spec)[0]
    return float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())


def material_tables(spec=SPEC, recipe=MATERIAL):
    C = np.array([recipe['shell'], recipe['band'], recipe['pad'], recipe['strap'], recipe['soil']], np.float32)
    S = np.array([recipe['shell_rough'], recipe['inside_rough'], recipe['band_rough'], recipe['pad_rough'],
                  recipe['scuff'], recipe['nick'], recipe['dust'], recipe['grime'], recipe['sweat'],
                  band_arc_half(spec), recipe['strap_rough']], np.float32)
    return C, S


def run_material(L, drivers, size, texel, spec=SPEC, ss=2, recipe=MATERIAL, log=print):
    """the material pass over the hat's one texture set, on the PRIMARY triangles (a stacked island shows its
    primary's texels). Returns soft_common.finish_maps' dict: albedo (sRGB), normal (GL), orm (AO, roughness,
    metalness 0: nothing on this hat is metal), masks (R fuzz, G 0, B palette zone; RGB, no alpha), wear (scuffs,
    nicks, dust, grime: for the eye) and palette_base (each zone's median linear albedo)"""
    import time

    from . import soft_common as SC
    from .. import calib
    t0 = time.time()
    pr = np.asarray(L['primary'], bool)
    F = L['F'][pr]
    uvm = M.uv_bvh(F, L['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(L['V'], F, L['N'], L['TAN'], L['ATTR'])
    keep = {k: drivers[k] for k in ('normal', 'ao', 'curvature', 'base', 'mat') if k in drivers}
    Dv = M.driver_arrays({**keep, **calib.relief_drivers(keep, 1.0 / texel)})
    C, S = material_tables(spec, recipe)
    n = size * size
    o_alb, o_nrm, o_orm = (wp.zeros(n, dtype=wp.vec3) for _ in range(3))
    o_mask, o_wear = wp.zeros(n, dtype=wp.vec4), wp.zeros(n, dtype=wp.vec4)
    o_hit = wp.zeros(n, dtype=wp.int32)
    wp.launch(k_hard, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
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
    log(f'[hard_hat] material {size}^2 x ss {ss}: {time.time() - t0:.1f}s over {int(cov.sum())} texels '
        f'({cov.mean() * 100:.1f} % of the sheet); palette base (linear) '
        + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in maps['palette_base'].items())
        + '; wear, mean / p95: ' + ', '.join(f'{nm} {wm[:, i].mean():.3f} / {np.percentile(wm[:, i], 95):.3f}'
                                            for i, nm in enumerate(('scuffs', 'nicks', 'dust', 'grime'))))
    return maps


# ====================================================================================================== THE FIT
def fit_data(spec=SPEC, conform=None):
    """what the fit (accessories_b5/cowboy_hat/scripts/f07_fit.py) and the runtime's wear() need from the hat (prop
    space, metres; top_hat.fit_data's contract as the cowboy hat keeps it): the seat frame, the head OPENING (the
    headband's own oval on the seat plane), the height of the cradle (what the head's top meets) and of the shell's
    inner ceiling, the brim's reach, the FIT VOLUME (two upright cylinders that hold the whole hat: the rim with its
    peak, the dome), and `conform`: {species: {pose: {translation, scale, tilt_deg}}}. RIGID (the fit law): a
    placement and ONE scale, no morph target"""
    d = dims(spec)
    lo, hi = extents(spec)
    a = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
    ft = flange_terms(a, spec)
    P, N, T = flange_frame(a, ft['q4'], spec)
    edge = P + 0.5 * d['t'] * T
    r_edge = np.hypot(edge[:, 0], edge[:, 2])
    pad = 0.002
    r_dome = float(max(d['rx_o'], d['rz_o'])) + spec['boss_d'] + pad
    y_fl = float(d['y_w'] + 0.004)
    rnd = lambda v: round(float(v), 5)
    return dict(archetype='hat', prop=NAME, rigid=True,
                volume=dict(kind='cylinders', axis='+Y',
                            parts=[dict(name='rim', y=[rnd(lo[1] - pad), rnd(y_fl + pad)], radius=rnd(r_edge.max() + pad)),
                                   dict(name='dome', y=[rnd(lo[1] - pad), rnd(d['y_top'] + pad)], radius=rnd(r_dome))],
                            note='the whole hat inside two upright cylinders about the seat axis (prop space, metres)'),
                seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0], left=[1.0, 0.0, 0.0]),
                opening=dict(rx=rnd(d['rx_h']), rz=rnd(d['rz_h']), y=0.0, circumference=spec['head_circ']),
                crown_inner_height=rnd(spec['cradle_y']),
                shell_inner_height=rnd(d['y_top'] - spec['rib_h'][0] - d['t']),
                brim=dict(y_min=rnd(edge[:, 1].min()), y_max=rnd(edge[:, 1].max()), r_front=rnd(r_edge[0]),
                          r_side=rnd(r_edge[90]), r_back=rnd(r_edge[180])),
                variants={k: {z: f'#{c:06x}' for z, c in v.items()} for k, v in VARIANTS.items()},
                conform=conform or {})


NAME = 'hard_hat'


def export_glb(path, L, maps, spec=SPEC, conform=None):
    """a static glb as the other hats write it (soft_common.export_glb's layout, with the albedo LOSSLESS: the white
    variant multiplies this map's blue channel by 27, and a JPEG's chroma blocks would show): one mesh, one material
    (base, normal, ORM; the masks in KHR_materials_volume's thickness slot), the fit data in the root node's and the
    file's extras"""
    from .. import gltf
    g = gltf.GLB()
    t_base = g.texture(maps['albedo'], fmt='png')
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='jpeg', quality=95)
    t_msk = g.texture(maps['masks'], fmt='png')
    mat = g.material(NAME, base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='prop', prop=NAME, masks=t_msk,
        masks_channels='R fuzz / sheen amount (the pad, the webbing), G 0, B palette zone (0 shell, 1/3 suspension, '
                       '2/3 pad, 1 webbing); RGB, no alpha',
        palette_zones=list(ZONES), palette_base=maps.get('palette_base', {}),
        palette_variants={k: {z: f'#{c:06x}' for z, c in v.items()} for k, v in VARIANTS.items()}))
    mesh = g.mesh(NAME, L['V'], L['N'], L['TAN'], L['UV'], [(L['F'], mat)])
    fit = fit_data(spec, conform)
    g.node(NAME, mesh=mesh, root=True, extras=dict(bestiary='prop', fit=fit))
    return g.save(path, extras=dict(bestiary=dict(prop=NAME, archetype='hat', units='m', up='+Y', forward='+Z',
                                                  left='+X', triangles=int(len(L['F'])), fit=fit)))


# ============================================================================================ THE FORGE'S STAGES
def hidden_under_bosses(spec=SPEC, inset=0.0004):
    """exclude(points) for the bake: texels that lie more than `inset` INSIDE the high's solid where no camera can see
    them: under a boss or a slot shelf (the low's wall and gutter run on under them; the boxes as the high builds them,
    cut back to the shell's mid-surface by boss_clip_patch), or inside the shell's wall WITHIN A BOX'S FOOTPRINT (a
    boss's side running back to the wall on the mid-surface; anywhere else a point inside the wall is only a low's
    chord, up to 0.5 mm under the high's face, and stays judged). Hidden: kept out of the bake's miss bar and its gate.
    (The first version, 11-11 07:41, tested each box against a PLANE at the wall's mid-surface: along a 44 mm box the
    wall curves 2.4 mm behind that plane, and 59,617 hidden texels under the bosses failed the gate as missed)"""
    from .. import sdf
    boxes = boss_boxes(spec)[0]
    prog = sdf.Program()
    prog.begin_group(op=sdf.UNION, k=0.0)
    for b in boxes:
        prog.roundbox(b['c'], b['half'], spec['boss_r'], b['axes'], k=0.0, name=b['name'])
    for b in boxes:
        Vc, Fc = boss_clip_patch(b, spec)
        prog.shell(Vc, Fc, 0.0035, op=sdf.SUBTRACT, k=0.0, maxd=0.02, name=b['name'] + ' clip')
    prog.end_group()
    wall = sdf.Program()
    Vs, Fs = shell_patch(spec, n_a=720, step=0.0007)
    wall.shell(Vs, Fs, 0.5 * dims(spec)['t'], k=0.0, maxd=0.02, name='shell')

    def exclude(P):
        P = np.asarray(P, np.float64)
        near = np.zeros(len(P), bool)
        for b in boxes:
            near |= (np.abs((P - b['c']) @ b['axes']) <= b['half'] + 0.001).all(1)
        # (inside the wall within a box's footprint: at ANY depth: a boss face's bottom edge runs 0.05 - 2 mm inside
        # the gutter's floor, and with the inset an 81-texel line of it failed the gate as a crack)
        return (np.asarray(prog.eval(P)) < -inset) | (near & (np.asarray(wall.eval(P)) < 0.0))
    return exclude


def forge_bake(out_dir, size=2048, voxel_size=0.0003, band=0.0015, ss=2, seed=7, spec=SPEC, order=None, ppm=None,
               log=print):
    """block-out -> low + UVs -> voxel high (GPU) -> the bake; writes low_hard_hat.npz and drivers_hard_hat.npz (the
    material pass reads them in a process of its own: seconds, and a look trial never bakes again)"""
    import os
    import time

    from .. import bake, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    L, low, parts, info, uvr = make_low(size, spec, log, order, ppm)
    np.savez_compressed(os.path.join(out_dir, f'low_{NAME}.npz'),
                        **{k: v for k, v in L.items() if isinstance(v, np.ndarray)}, px_per_m=L['px_per_m'],
                        size=L['size'], Q=low['Q'], quad_part=low['part'], quad_island=low['island'],
                        names=np.array(low['names']), parts=np.array(low['parts']))
    prog = build_sdf(spec)
    lo, hi = bounds(spec)
    G = voxel.SparseSDF(prog, lo, hi, voxel=voxel_size, band=band, log=log)
    pr = L['primary']
    res = bake.bake(G, L['V'], L['F'][pr], L['UV'], L['N'], L['TAN'], L['region'][pr], size=size, ss=ss, cage=0.004,
                    ao_r=0.02, cav_r=0.002, n_thk=2, thk_max=0.01, seed=seed, log=log,
                    region_names=dict(enumerate(REGIONS)), exclude=hidden_under_bosses(spec))
    keep = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
            if k != 'position' and isinstance(v, np.ndarray)}
    np.savez_compressed(os.path.join(out_dir, f'drivers_{NAME}.npz'), **keep)
    log(f'[hard_hat] the bake is saved (drivers_{NAME}.npz) after {time.time() - t0:.0f}s')
    return L
