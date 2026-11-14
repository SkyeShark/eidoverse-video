"""THE AVIATOR SUNGLASSES: the sunglasses' classic frame of its own (ROADMAP B5; DESIGN.md "glasses, sunglasses"; the
old creator's `sunglasses`), a small RIGGED prop built the forge way at real size. Its log: accessories_b5/hard_NOTES.md
(THE SUNGLASSES). The round glasses with a G-15 lens are the other sunglasses (wear()'s palette, no file).

THE OBJECT (ACCESSORY_REFERENCE.md section 9; the board of three candidates is in the showcase): the 1930s pilot's
frame as it has been made since by many makers: TEARDROP lenses (the top nearly straight, the inner lower side cut
away for the nose), a thin metal rim, a DOUBLE BRIDGE (the brow bar over the lower bridge), pads on arms, a small
hinge at the rim's outer side, SKULL temples (straight, turning down behind the ear into acetate tips); G-15 glass
(15 % transmission, measured: linear sRGB 0.125, 0.153, 0.122), a gold plated frame (gunmetal, silver: the palette).

REUSED (WORKING_RULES 4, 13): round_glasses.py gives its tube and revolve pieces (`ring_tube`, `revolve_piece`,
`_piece`, `_weights`), its UV unwrap and arrays (`unwrap`, `low_arrays`), its JOINTS and their parents (so the
runtime's glassesPose, accessories.js, poses this prop by the same fit contract) and `fit_pose`; soft_common.py gives
the maps' finish. New here: the front's geometry (the teardrop outline MEASURED on a CC0 front view, the double
bridge, the skull temples), its own high, its own material pass (plated wire, acetate, silicone, tinted glass).

  parts (the LEFT half, mirrored and STACKED; the two bridges whole):
    rim       a wire round the lens on its front sphere (40 stations, 4 round: a 1.5 x 1.0 mm wire is 3.5 x 2.3 px
              at the closest view; its round is the bake's)
    lens      the G-15 glass: 24 stations placed by the outline's turning, its two faces 6 x 6 grids on their spheres
    brow      the brow bar from rim top to rim top (6 round); bridge: the lower bridge's arch (4 round)
    lug, barrel   the endpiece and its hinge;  temple: the shaft and the acetate tip (8 round, a domed end)
    pad_arm, pad  a wire arm and a silicone pad (an ellipsoid)
  -> RG.unwrap (analytic islands, one density, the lenses at 0.70 / 0.45), the voxel high of the left half and the
     bridges (the glass too: it is baked here, so one material pass paints every region), the material pass, a SKINNED
     glb with the round glasses' 15 joints and fit data

Frame: as round_glasses: metres, +Z the way the lenses face, +Y up, +X the wearer's left; the origin at the bridge's
CONTACT point (the lower bridge's arch at its rearmost: where it would rest on a nose).

NUMBERS ([C] published, [M] measured, [E] estimate): the Ray-Ban RB3025 "Large Metal" 58-14-135 [C: ACCESSORY_REFERENCE
R28]: the lens 58 mm wide (the boxing A), the bridge 14 mm, the temple 135 mm; the lens's height about 49-50 mm [C];
THE OUTLINE [M: accessories_b5/sunglasses/scripts/m01_outline.py on research/refs/accessories/aviator_sunglasses/02
(CC0, two wearers nearly square to the camera): four lenses' radius about the box centre per degree, their mean; the
spread between the four 0.7-4 % of the half-width; the box's aspect 0.82-0.90 (built 0.853); the hinge 8-10 degrees
above the box's middle on the outer side, the brow bar's foot at 112 degrees, the lower bridge's at 154]; the wires'
sections [E: a typical metal frame: the rim 1.5 x 1.0 mm, the brow bar 1.8 mm, the lower bridge 1.2 mm, the temple
1.4 mm]; the lens base 6 [C: the RB3139's description], 2.2 mm thick [E].
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc
from .. import sdf
from ..mesh import QuadMesh
from . import round_glasses as RG
from . import soft_common as SC
from .round_glasses import JOINTS, _piece, _weights, ring_tube, revolve_piece

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})

NAME = 'aviator'

SPEC = dict(
    lens_a=0.058,           # the boxing width [C: 58-14-135]
    lens_b=0.0495,          # the boxing height [C: about 49-50]
    dbl=0.014,              # the bridge: the distance between the lenses [C]
    temple_len=0.135,       # the temple's length, hinge to tip [C]
    # the outline: the radius about the boxing centre every 15 degrees from +X (the wearer's left = outward on the left
    # lens) counter-clockwise, as shares of the half-width [M: m01_outline.py's mean of four lenses]
    outline=(0.981, 1.025, 1.045, 0.999, 0.921, 0.870, 0.861, 0.881, 0.953, 1.062, 1.107, 1.015, 0.879, 0.791, 0.745,
             0.733, 0.743, 0.785, 0.832, 0.890, 0.942, 0.979, 0.979, 0.970),
    rim_w=0.0015,           # the rim's section: across the lens plane (its face) and along the lens axis [E]
    rim_d=0.0010,
    lens_t=0.0022,          # the G-15 glass [E: ACCESSORY_REFERENCE 9]
    lens_base=6.0,          # its front curve in dioptres at n 1.523 [C: base 6]: R = 523 / 6 = 87 mm
    lens_ior=1.523,
    brow_d=0.0018,          # the brow bar ("bullet"): a round bar from rim top to rim top, standing proud [E]
    brow_phi=112.0,         # its foot on the rim (degrees round the lens from +X toward +Y) [M]
    brow_rise=0.0035,       # its middle this far above its ends, and this far in front of the rims' plane
    brow_fwd=0.0010,
    bridge_d=0.0012,        # the lower bridge: a wire arching between the rims' inner sides [E]
    bridge_phi=154.0,       # it leaves each rim here [M]
    bridge_rise=0.0030,     # its arch over its ends, its setback behind the rims at its ends
    bridge_back=0.0040,
    pad_phi=205.0,          # the pad arm leaves the rim's back here
    pad_off=(-0.0010, -0.0040, -0.0060),     # the pad's centre from the arm's root (toward the nose, down, back) [E]
    pad_len=0.0130,         # the pad: a clear silicone oval [E: a modern pad]
    pad_w=0.0075,
    pad_t=0.0024,
    pad_arm_d=0.0008,
    end_phi=10.0,           # the endpiece on the rim's outer side [M: 8-10 degrees]
    end_len=0.0040,         # from the rim to the hinge's pin
    lug_d=0.0011,
    hinge_r=0.0012,
    hinge_h=0.0030,
    temple_d=0.0014,        # the skull temple's shaft
    temple_splay=3.0,       # degrees outward
    bend_at=0.098,          # the shaft runs this far from the hinge to the ear bend; the tip turns down past it
    tip_drop=35.0,          # the tip's turn down (degrees) over its arc, and the arc's radius
    tip_r=0.030,
    tip_len=0.040,          # the acetate tip past the bend, and its sleeve over the shaft before it
    tip_sleeve=0.014,
    tip_d=0.0032,
)
FIT_EYE = 1.55              # the lens's mean radius per eye radius: aviators want 1.5-1.7 x (ACCESSORY_REFERENCE 9)
REGIONS = RG.REGIONS        # ('rim', 'bridge', 'lug', 'knuckle', 'temple', 'hook', 'pad_arm', 'cup', 'pad', 'lens'):
#                             the round glasses' meanings: the brow bar and the lower bridge are 'bridge'; the endpiece
#                             'lug'; the hinge 'knuckle'; the shaft 'temple'; the acetate tip 'hook'; the pad 'pad'
ZONES = ('plating', 'base', 'ivory', 'glass')    # the runtime's glasses palette (accessories.js wearGlasses): masks B
#                                                  0 the plating, 1/3 the base metal, 2/3 'ivory' (here the acetate
#                                                  tips and the pads), 1 the glass
N_RIM = 40                  # the rim's stations round the lens
N_LENS = 24                 # the glass's, placed by the outline's turning (its edge lies under the rim's wire)
N_CABLE = RG.N_CABLE
LENS_SHARE, LENS_BACK_SHARE = RG.LENS_SHARE, RG.LENS_BACK_SHARE


# ------------------------------------------------------------------------------------------------------ outline
def _fourier(vals, harm=5):
    """the outline's radius as a smooth periodic function of the angle: a least-squares Fourier fit of the samples
    (at even angles from 0)"""
    th = np.radians(np.arange(len(vals)) * 360.0 / len(vals))
    cols = [np.ones_like(th)]
    for k in range(1, harm + 1):
        cols += [np.cos(k * th), np.sin(k * th)]
    A = np.column_stack(cols)
    c, *_ = np.linalg.lstsq(A, np.asarray(vals, np.float64), rcond=None)

    def f(t):
        t = np.asarray(t, np.float64)
        out = c[0] * np.ones_like(t)
        for k in range(1, harm + 1):
            out = out + c[2 * k - 1] * np.cos(k * t) + c[2 * k] * np.sin(k * t)
        return out
    return f


def outline(spec=SPEC, n=N_RIM):
    """the LEFT lens's outline in its plane (metres; x outward, y up; the origin at the boxing centre), scaled so the
    box is lens_a x lens_b exactly; n points at even angles (counter-clockwise from +X), and a dense copy (720)"""
    f = _fourier(spec['outline'])
    t = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)
    r = f(t)
    P = np.column_stack([r * np.cos(t), r * np.sin(t)])
    lo, hi = P.min(0), P.max(0)
    sx, sy = spec['lens_a'] / (hi[0] - lo[0]), spec['lens_b'] / (hi[1] - lo[1])
    c = 0.5 * (lo + hi)
    tt = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    rr = f(tt)
    Q = np.column_stack([rr * np.cos(tt), rr * np.sin(tt)])
    return (Q - c) * np.array([sx, sy]), (P - c) * np.array([sx, sy])


def _out_normals(o):
    """a closed counter-clockwise polygon's outward normals at its vertices"""
    t = np.roll(o, -1, axis=0) - np.roll(o, 1, axis=0)
    n = _unit(np.column_stack([t[:, 1], -t[:, 0]]))
    return n if (n * o).sum() > 0 else -n


def outline_by_turning(spec=SPEC, n=N_LENS):
    """n points of the outline placed by its TURNING (half by the tangent's turn, half by arc length): close where
    the outline bends (the upper inner corner, the nose cut's ends), sparse along the straight top: every chord then
    sags about alike (at even angles 24 chords cut the tight corners by over 1 mm)"""
    _, P = outline(spec)
    d = np.roll(P, -1, axis=0) - P
    seg = np.linalg.norm(d, axis=1)
    ang = np.arctan2(d[:, 1], d[:, 0])
    turn = np.abs((np.roll(ang, -1) - ang + np.pi) % (2.0 * np.pi) - np.pi)
    w = 0.5 * np.cumsum(turn) / turn.sum() + 0.5 * np.cumsum(seg) / seg.sum()
    w = np.concatenate([[0.0], w[:-1]])
    idx = np.searchsorted(w, np.arange(n) / n)
    return P[np.clip(idx, 0, len(P) - 1)]


def lens_sag(spec, x, y):
    """the lens's front surface's sag (m, toward -Z) at (x, y) from its centre: a sphere of radius 523 / base mm"""
    R = 0.523 / spec['lens_base']
    rr = np.minimum(np.hypot(x, y), 0.999 * R)
    return R - np.sqrt(R * R - rr * rr)


def dims(spec=SPEC):
    """the LEFT half's key points (the right mirrors x), the origin at the bridge's contact point: C the lens's boxing
    centre (its front face's apex), J the lower bridge's junction on the rim (the lens joint), the brow bar's end B0
    and middle B1, the endpiece's foot E and the hinge pin H, the ear bend Bd"""
    o, _ = outline(spec, 360)

    def at(phi):                                               # the outline's point at an angle (degrees from +X)
        a = np.degrees(np.arctan2(o[:, 1], o[:, 0])) % 360.0
        i = int(np.argmin(np.abs(((a - phi + 180.0) % 360.0) - 180.0)))
        return o[i]
    pj = at(spec['bridge_phi'])
    # C: the lens's inner edge stands dbl / 2 from the middle; the junction bridge_rise under the contact's height and
    # bridge_back in front of it (the lens's edge lies its sag behind its apex: 4.6 mm at the junction)
    Cx = 0.5 * spec['dbl'] - o[:, 0].min()
    Cy = -spec['bridge_rise'] - pj[1]
    zl = spec['bridge_back'] + float(lens_sag(spec, pj[0], pj[1]))
    C = np.array([Cx, Cy, zl])
    lift = lambda p2: C + np.array([p2[0], p2[1], -float(lens_sag(spec, p2[0], p2[1]))])
    out_ = lambda p2: p2 * (1.0 + 0.5 * spec['rim_w'] / np.linalg.norm(p2))     # the rim's centreline over a point
    J = lift(out_(pj))
    tin = at(spec['brow_phi'])
    B0 = lift(out_(tin)) + np.array([0.0, 0.25 * spec['rim_w'] + 0.3 * spec['brow_d'], spec['brow_fwd']])
    B1 = np.array([0.0, B0[1] + spec['brow_rise'], B0[2] + 0.0005])
    pe = at(spec['end_phi'])
    E = lift(out_(pe))
    nE = _unit(pe)
    H = E + np.array([nE[0], nE[1], 0.0]) * spec['end_len'] + np.array([0.0, 0.0, -0.0015])
    sp = np.radians(spec['temple_splay'])
    Bd = H + spec['bend_at'] * np.array([np.sin(sp), 0.0, -np.cos(sp)])
    r_mean = float(np.linalg.norm(o, axis=1).mean())
    return dict(C=C, J=J, B0=B0, B1=B1, E=E, H=H, Bd=Bd, zl=zl, outline=o, r_mean=r_mean, at=at)


def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def mirror(P, side):
    P = np.array(P, np.float64)
    if side < 0:
        P[..., 0] = -P[..., 0]
    return P


# ------------------------------------------------------------------------------------------------------- curves
def rim_curve(spec=SPEC, n=N_RIM):
    """the rim's centreline on the left lens (n stations, closed: the first repeated at the end) on the lens's front
    sphere, pushed out across the lens plane by half the rim's face (the rim wraps the lens's edge), and its frame
    normals (outward in the lens plane)"""
    d = dims(spec)
    o, _ = outline(spec, n)
    nrm2 = _out_normals(o)
    p2 = o + nrm2 * (0.5 * spec['rim_w'])
    P = d['C'] + np.column_stack([p2[:, 0], p2[:, 1], -lens_sag(spec, p2[:, 0], p2[:, 1]) - 0.5 * spec['lens_t']])
    N3 = np.column_stack([nrm2, np.zeros(len(nrm2))])
    return np.vstack([P, P[:1]]), np.vstack([N3, N3[:1]])


def _bezier(P0, P1, P2, P3, n):
    t = np.linspace(0.0, 1.0, n)[:, None]
    return (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t * t * P2 + t ** 3 * P3


def brow_curve(spec=SPEC, n=13):
    """the brow bar from the RIGHT rim's top over the middle to the left's (one piece: its middle on x = 0)"""
    d = dims(spec)
    B0, B1 = d['B0'], d['B1']
    h = (B1[1] - B0[1]) / 0.75
    g = (B1[2] - B0[2]) / 0.75
    return _bezier(mirror(B0, -1), mirror(B0, -1) + np.array([0.010, h, g]), B0 + np.array([-0.010, h, g]), B0, n)


def bridge_curve(spec=SPEC, n=11):
    """the lower bridge: from the right junction over the arch to the left; its middle the CONTACT: the wire's back at
    the origin"""
    d = dims(spec)
    J = d['J']
    Jr = mirror(J, -1)
    h = (0.0 - J[1]) / 0.75
    g = (0.5 * spec['bridge_d'] - J[2]) / 0.75
    return _bezier(Jr, Jr + np.array([0.003, h, g]), J + np.array([-0.003, h, g]), J, n)


def temple_path(spec, side):
    """the skull temple's centreline stations, their arc lengths and the bend's: the hinge, the straight shaft (the
    acetate tip's sleeve starts tip_sleeve before the ear bend), the tip's arc turning down, its straight end"""
    d = dims(spec)
    H, Bd = mirror(d['H'], side), mirror(d['Bd'], side)
    ds = _unit(Bd - H)
    sb = spec['bend_at']
    s0 = np.array([0.0, 0.030, 0.060, sb - spec['tip_sleeve'], sb - spec['tip_sleeve'] + 0.004, sb])
    shaft = H + s0[:, None] * ds
    down = np.array([0.0, -1.0, 0.0])
    ang = np.radians(np.linspace(0.0, spec['tip_drop'], 6))[1:]
    arc = np.array([Bd + spec['tip_r'] * (np.sin(a) * ds + (1.0 - np.cos(a)) * down) for a in ang])
    end_dir = _unit(np.sin(np.radians(spec['tip_drop'])) * down + np.cos(np.radians(spec['tip_drop'])) * ds)
    Lt = spec['tip_len'] - spec['tip_r'] * np.radians(spec['tip_drop'])
    tail = arc[-1] + np.array([0.5, 1.0])[:, None] * Lt * end_dir
    s = np.concatenate([s0, sb + spec['tip_r'] * ang, sb + spec['tip_r'] * ang[-1] + np.array([0.5, 1.0]) * Lt])
    return np.vstack([shaft, arc, tail]), s, sb


def temple_r(spec, s, sb):
    """the temple's radius at the arc length s: the shaft's wire, swelling over 4 mm into the acetate tip"""
    a = sb - spec['tip_sleeve']
    return 0.5 * spec['temple_d'] + (0.5 * spec['tip_d'] - 0.5 * spec['temple_d']) * RG._smoothstep(a, a + 0.004, s)


def cable_s(spec=SPEC):
    """the tip's arc length from the bend to each cable joint (the round glasses' rule: the first AT the bend, then
    thirds of the tip)"""
    return spec['tip_len'] * np.arange(N_CABLE) / N_CABLE


def pad_frame(spec, side):
    """a pad arm's root on the rim's back at pad_phi, the pad's centre, the pad's face normal (toward the nose)"""
    d = dims(spec)
    p2 = d['at'](spec['pad_phi'])
    root = d['C'] + np.array([p2[0], p2[1], -float(lens_sag(spec, p2[0], p2[1])) - spec['lens_t'] - 0.0003])
    pc = root + np.array(spec['pad_off'])
    nf = _unit(np.array([-0.80, -0.10, -0.59]))
    return mirror(root, side), mirror(pc, side), mirror(nf, side)


def pad_axis(spec, side):
    """a pad arm's fold axis (the prop frame): the rim's tangent at the arm's root"""
    ph = np.radians(spec['pad_phi'])
    return mirror([-np.sin(ph), np.cos(ph), 0.0], side)


# ----------------------------------------------------------------------------------------------------- the rig
def rest_joints(spec=SPEC):
    """the skeleton at rest, round_glasses.rest_joints' layout on this frame: glasses_root at the contact (identity);
    each lens joint at its lower bridge's junction; each temple at its hinge pin, its local -Z along the shaft; the
    hook joint at the ear bend; the cable joints down the tip (the runtime turns them to drape the tip); each pad
    joint at its arm's root"""
    d = dims(spec)
    out = {'glasses_root': (None, np.eye(4))}
    for side, sfx in ((1, 'L'), (-1, 'R')):
        W = np.eye(4)
        W[:3, 3] = mirror(d['J'], side)
        out[f'lens_{sfx}'] = ('glasses_root', W)
        H, Bd = mirror(d['H'], side), mirror(d['Bd'], side)
        z = _unit(H - Bd)
        y = _unit(np.array([0.0, 1.0, 0.0]) - z * z[1])
        x = np.cross(y, z)
        Wt = np.eye(4)
        Wt[:3, :3] = np.column_stack([x, y, z])
        Wt[:3, 3] = H
        out[f'temple_{sfx}'] = (f'lens_{sfx}', Wt)
        Wh = Wt.copy()
        Wh[:3, 3] = Bd
        out[f'hook_{sfx}'] = (f'temple_{sfx}', Wh)
        Pt, st, sb = temple_path(spec, side)
        par = f'hook_{sfx}'
        for i, sc in enumerate(cable_s(spec)):
            Wc = Wt.copy()
            Wc[:3, 3] = [np.interp(sb + sc, st, Pt[:, k]) for k in range(3)]
            out[f'cable_{sfx}{i + 1}'] = (par, Wc)
            par = f'cable_{sfx}{i + 1}'
        root, pc, nf = pad_frame(spec, side)
        Wp = np.eye(4)
        Wp[:3, 3] = root
        out[f'pad_{sfx}'] = (f'lens_{sfx}', Wp)
    return out


def skeleton(spec=SPEC):
    from ..rig import Skeleton
    sk = Skeleton()
    rj = rest_joints(spec)
    for nm in JOINTS:
        par, W = rj[nm]
        sk.add(nm, par, W[:3, 3], W[:3, :3])
    return sk


# ----------------------------------------------------------------------------------------------------- the low
def _ellipse(a, b):
    """ring_tube's section: an ellipse of half-axes a (along the frame normal) and b"""
    return lambda i, th: a * b / np.sqrt((b * np.cos(th)) ** 2 + (a * np.sin(th)) ** 2)


def lens_piece(spec=SPEC):
    """the glass (left): its edge band between the back and the front outline rings (N_LENS stations placed by the
    outline's turning, 0.35 mm outside the outline: under the rim's wire), and its two faces as 6 x 6 quad grids
    lifted onto their spheres. Islands: the band unrolled, the faces flat (the front at LENS_SHARE, the back less)"""
    from .. import loft
    d = dims(spec)
    C = d['C']
    o = outline_by_turning(spec, N_LENS)
    p2 = o + _out_normals(o) * 0.00035
    n = len(p2)
    Vf = C + np.column_stack([p2[:, 0], p2[:, 1], -lens_sag(spec, p2[:, 0], p2[:, 1])])
    Vb = Vf - np.array([0.0, 0.0, spec['lens_t']])
    V = np.vstack([Vb, Vf])
    i = np.arange(n)
    Q = np.stack([i, (i + 1) % n, n + (i + 1) % n, n + i], -1)
    fn = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    flip = bool((fn * (V[Q].mean(1) - C)).sum() < 0.0)
    if flip:
        Q = Q[:, ::-1].copy()
    sa = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.roll(p2, -1, axis=0) - p2, axis=1))])
    attr = np.column_stack([np.tile(sa[:n], 2), V[:, 0] - C[0], V[:, 1] - C[1], np.full(2 * n, 9.0)])
    mesh = QuadMesh(V, Q, {'attr': attr})
    mesh, Gf = loft.cap(mesh, np.arange(n, 2 * n), np.array([0.0, 0.0, 1.0]))
    nqf = len(mesh.Q) - n
    mesh, Gb = loft.cap(mesh, np.arange(n), np.array([0.0, 0.0, -1.0]))
    nqb = len(mesh.Q) - n - nqf
    V2, A2 = mesh.V, mesh.attrs['attr']
    for G, back in ((Gf, False), (Gb, True)):
        ids = np.unique(G)
        ids = ids[ids >= 2 * n]
        x, y = V2[ids, 0] - C[0], V2[ids, 1] - C[1]
        V2[ids, 2] = C[2] - lens_sag(spec, x, y) - (spec['lens_t'] if back else 0.0)
        A2[ids] = np.column_stack([np.zeros(len(ids)), x, y, np.full(len(ids), 9.0)])
    # islands
    sid = np.arange(2 * (n + 1)).reshape(2, n + 1)
    orig = np.concatenate([np.r_[np.arange(n), 0], n + np.r_[np.arange(n), 0]])
    UV = np.column_stack([np.tile(sa, 2), np.repeat([0.0, spec['lens_t']], n + 1)])
    k = np.arange(n)
    Qs = np.stack([sid[0, k], sid[0, k + 1], sid[1, k + 1], sid[1, k]], -1)
    if flip:
        Qs = Qs[:, ::-1].copy()
    islands = [dict(Q=Qs, orig=orig, UV=UV, quads=np.arange(n), share=LENS_SHARE)]
    q_off = n
    for G, nq, back, share in ((Gf, nqf, False, LENS_SHARE), (Gb, nqb, True, LENS_BACK_SHARE)):
        vs = np.unique(G)
        loc = -np.ones(len(V2), np.int64)
        loc[vs] = np.arange(len(vs))
        uv = np.column_stack([V2[vs, 0] - C[0], V2[vs, 1] - C[1]])
        if back:
            uv[:, 0] = -uv[:, 0]
        islands.append(dict(Q=loc[mesh.Q[q_off:q_off + nq]], orig=vs, UV=uv, quads=np.arange(q_off, q_off + nq),
                            share=share))
        q_off += nq
    return _piece(V2, mesh.Q, 9, A2, _weights(len(V2), {'lens_L': 1.0}), islands)


def temple_piece(spec=SPEC):
    """the left temple: 8 round, the shaft's wire swelling into the acetate tip, the tip's end domed (two rings and a
    2 x 2 grid cap, as the round glasses' ferrule). Weights: the temple joint at the hinge, a linear ramp to the hook
    joint at the ear bend (the shaft shortens uniformly when the hook joint slides), the cable joints down the tip"""
    from .. import loft
    Pt, st, sb = temple_path(spec, 1)
    r = temple_r(spec, st, sb)
    tdir = _unit(Pt[-1] - Pt[-2])
    f_ = np.array([0.5, 0.85])
    Pk = np.vstack([Pt, Pt[-1] + np.outer(f_ * r[-1], tdir)])
    sk = np.concatenate([st, st[-1] + f_ * r[-1]])
    rk = np.concatenate([r, r[-1] * np.sqrt(1.0 - f_ ** 2)])
    Nk = np.tile([1.0, 0.0, 0.0], (len(Pk), 1))
    V, Q, attr, isl = ring_tube(Pk, Nk, lambda i, th: rk[i], 8, s=sk, theta0=np.pi / 8, part=4.0, cut_len=0.050)
    sv = attr[:, 0]
    ws = np.clip((sv - 0.004) / (sb - 0.004), 0.0, 1.0)
    h = 1.0 - RG._smoothstep(sb - 0.001, sb + 0.001, sv)
    W = _weights(len(V), {'temple_L': (1.0 - ws) * h, 'hook_L': ws * h})
    chain = [f'cable_L{i + 1}' for i in range(N_CABLE)]
    sj = sb + cable_s(spec)
    for i in range(len(chain)):
        t = (sv - sj[i]) / (sj[i + 1] - sj[i]) if i + 1 < len(chain) else np.zeros_like(sv)
        lo = (sv < sj[i]) if i == 0 else np.zeros(len(sv), bool)
        on = ((t >= 0.0) & (t < 1.0)) if i + 1 < len(chain) else (sv >= sj[i])
        W[lo, JOINTS.index(chain[i])] += 1.0 - h[lo]
        W[on, JOINTS.index(chain[i])] += ((1.0 - t) * (1.0 - h))[on]
        if i + 1 < len(chain):
            W[on, JOINTS.index(chain[i + 1])] += (t * (1.0 - h))[on]
    regq = np.where(attr[Q[:, 0], 0] < sb - spec['tip_sleeve'] + 0.002, 4, 5)
    m = QuadMesh(V, Q, {'attr': attr})
    ring = np.arange(len(V) - 8, len(V))
    m, G = loft.cap(m, ring, tdir)
    pole = Pk[-3] + tdir * r[-1]
    m.V[G[1:-1, 1:-1].ravel()] = pole
    nv = len(m.V) - len(V)
    W = np.vstack([W, np.tile(W[-1], (nv, 1))])
    regq = np.concatenate([regq, np.full(len(m.Q) - len(Q), 5)])
    vs = np.unique(G)
    loc = -np.ones(len(m.V), np.int64)
    loc[vs] = np.arange(len(vs))
    e1 = _unit(np.cross(tdir, [1.0, 0.0, 0.0]))
    e2 = np.cross(tdir, e1)
    isl.append(dict(Q=loc[m.Q[len(Q):]], orig=vs, UV=np.column_stack([(m.V[vs] - pole) @ e1, (m.V[vs] - pole) @ e2]),
                    quads=np.arange(len(Q), len(m.Q)), share=1.0))
    return _piece(m.V, m.Q, regq, m.attrs['attr'], W, isl)


def pad_piece(spec=SPEC):
    """the left pad: an ellipsoid pad_len x pad_w x pad_t, its short axis the face normal: a revolve of five rings
    about the normal, stretched along its long axis; capped at both poles"""
    root, pc, nf = pad_frame(spec, 1)
    rw, ht = 0.5 * spec['pad_w'], 0.5 * spec['pad_t']
    ph = np.radians([25.0, 58.0, 90.0, 122.0, 155.0])
    prof = np.column_stack([rw * np.sin(ph), -ht * np.cos(ph)])
    e_long = _unit(np.array([0.0, 1.0, 0.0]) - nf * nf[1])
    e1 = np.cross(e_long, nf)
    V, Q, reg, attr, isl = revolve_piece(prof, pc, nf, 8, e1=e1, cap0=True, cap1=True, region_of=lambda j: 8,
                                         part=8.0)
    k = spec['pad_len'] / spec['pad_w']
    V = V + np.outer((V - pc) @ e_long, e_long) * (k - 1.0)
    return _piece(V, Q, reg, attr, _weights(len(V), {'pad_L': 1.0}), isl), (pc, nf, e_long, e1)


def build_low(spec=SPEC, log=print):
    """the designed low: the LEFT half's pieces, the brow bar and the lower bridge (whole), then the left half
    mirrored to the right with its UVs STACKED on the left's (both lenses too: their dust is symmetric). Returns
    round_glasses.build_low's dict (V, Q welded, region per quad, attr, W, split, bake, side, names)"""
    d = dims(spec)
    pieces, centre = [], []
    # ---- the rim: 4 round its 1.5 x 1.0 mm wire (its vertices on the section's axes), cut into four islands
    P, N3 = rim_curve(spec)
    V, Q, attr, isl = ring_tube(P, N3, _ellipse(0.5 * spec['rim_w'], 0.5 * spec['rim_d']), 4, part=0.0, cut_len=0.045)
    pieces.append(('rim', _piece(V, Q, 0, attr, _weights(len(V), {'lens_L': 1.0}), isl)))
    # ---- the glass
    pieces.append(('lens', lens_piece(spec)))
    # ---- the endpiece: a short bar from inside the rim's wire to the hinge's middle; the hinge: a drum on its pin
    E, H = d['E'], d['H']
    L = np.array([E - 0.0003 * _unit(H - E), H])
    V, Q, attr, isl = ring_tube(L, np.tile([0.0, 1.0, 0.0], (2, 1)), _ellipse(0.5 * spec['lug_d'], 0.5 * spec['lug_d']),
                                4, theta0=np.pi / 4, part=2.0)
    pieces.append(('lug', _piece(V, Q, 2, attr, _weights(len(V), {'lens_L': 1.0}), isl)))
    hh, rb = 0.5 * spec['hinge_h'], spec['hinge_r']
    prof = np.array([[0.55 * rb, -hh], [rb, -hh], [rb, hh], [0.55 * rb, hh]])
    V, Q, reg, attr, isl = revolve_piece(prof, H, [0.0, 1.0, 0.0], 8, e1=[0.0, 0.0, -1.0], cap0=True, cap1=True,
                                         region_of=lambda j: 3, part=3.0)
    pieces.append(('barrel', _piece(V, Q, reg, attr, _weights(len(V), {'lens_L': 1.0}), isl)))
    # ---- the temple
    pieces.append(('temple', temple_piece(spec)))
    # ---- the pad arm (a bent wire, 4 round) and the pad
    root, pc, nf = pad_frame(spec, 1)
    Pa = np.array([root, root + 0.45 * np.array(spec['pad_off']) + np.array([0.0005, 0.0, -0.0012]),
                   pc - nf * (0.35 * spec['pad_t'])])
    V, Q, attr, isl = ring_tube(Pa, np.tile([0.0, 1.0, 0.0], (3, 1)), lambda i, th: 0.5 * spec['pad_arm_d'], 4,
                                theta0=np.pi / 4, part=6.0)
    pieces.append(('pad_arm', _piece(V, Q, 6, attr, _weights(len(V), {'pad_L': 1.0}), isl)))
    pieces.append(('pad', pad_piece(spec)[0]))
    # ---- the brow bar (6 round) and the lower bridge (4 round): whole, the root at the middle easing to each lens
    #      joint (a smootherstep), as the round glasses' bridge
    def smoother(t):
        t = np.clip(t, 0.0, 1.0)
        return t * t * t * (t * (6.0 * t - 15.0) + 10.0)
    for nm, Pc, rad, K in (('brow', brow_curve(spec), 0.5 * spec['brow_d'], 6),
                           ('bridge', bridge_curve(spec), 0.5 * spec['bridge_d'], 4)):
        V, Q, attr, isl = ring_tube(Pc, np.tile([0.0, 1.0, 0.0], (len(Pc), 1)), lambda i, th, rad=rad: rad, K,
                                    part=1.0, cut_len=0.08)
        sv = attr[:, 0] - 0.5 * attr[:, 0].max()
        s_half = 0.5 * attr[:, 0].max() - 0.0012
        wl, wr = smoother(sv / s_half), smoother(-sv / s_half)
        W = _weights(len(V), {'glasses_root': 1.0 - wl - wr, 'lens_L': wl, 'lens_R': wr})
        centre.append((nm, _piece(V, Q, 1, attr, W, isl)))
    return assemble(pieces, centre, log)


def assemble(pieces, centre, log=print):
    """round_glasses.build_low's assembly (copied 11-12: it is closed over that function's pieces): the left pieces,
    the centre pieces, the left's mirrors (winding flipped, joints swapped L <-> R, the islands SHARED: each mirrored
    island copy carries its left twin's island id)"""
    Vs, Qs, R, A, Ws, S, B = [], [], [], [], [], [], []
    split = dict(Q=[], orig=[], UV=[], island=[], wq=[], share=[], groups=[])
    cnt = dict(v=0, q=0, s=0, isl=0)
    swap = {JOINTS.index(f'{j}_L'): JOINTS.index(f'{j}_R') for j in ('lens', 'temple', 'hook', 'pad')}
    swap.update({JOINTS.index(f'cable_L{i + 1}'): JOINTS.index(f'cable_R{i + 1}') for i in range(N_CABLE)})
    perm = np.arange(len(JOINTS))
    for i_, j_ in swap.items():
        perm[i_], perm[j_] = j_, i_

    def add(pc_, side, isl_ids=None):
        V_ = mirror(pc_['V'], side)
        Q_ = pc_['Q'] if side >= 0 else pc_['Q'][:, ::-1]
        Vs.append(V_)
        Qs.append(Q_ + cnt['v'])
        R.append(pc_['region'])
        A.append(pc_['attr'])
        Ws.append(pc_['W'] if side >= 0 else pc_['W'][:, perm])
        S.append(np.full(len(Q_), side))
        B.append(np.full(len(Q_), bool(pc_['bake']) and side >= 0))
        ids_here = []
        for k_, isl_ in enumerate(pc_['islands']):
            Qi = isl_['Q'] if side >= 0 else isl_['Q'][:, ::-1]
            iid = cnt['isl'] if isl_ids is None else isl_ids[k_]
            if isl_ids is None:
                split['share'].append(isl_['share'])
                cnt['isl'] += 1
            split['Q'].append(Qi + cnt['s'])
            split['orig'].append(isl_['orig'] + cnt['v'])
            split['UV'].append(isl_['UV'])
            split['island'].append(np.full(len(Qi), iid))
            split['wq'].append(isl_['quads'] + cnt['q'])
            split['groups'].append((iid, cnt['s'], len(isl_['orig'])))
            ids_here.append(iid)
            cnt['s'] += len(isl_['orig'])
        cnt['v'] += len(V_)
        cnt['q'] += len(Q_)
        return ids_here
    left_isl = [add(pc_, 1) for nm, pc_ in pieces]
    for nm, pc_ in centre:
        add(pc_, 0)
    for (nm, pc_), ids_ in zip(pieces, left_isl):
        add(pc_, -1, ids_)
    low = dict(V=np.concatenate(Vs), Q=np.concatenate(Qs), region=np.concatenate(R), attr=np.concatenate(A),
               W=np.concatenate(Ws), side=np.concatenate(S), bake=np.concatenate(B),
               names=[nm for nm, _ in pieces] + [nm for nm, _ in centre],
               split=dict(Q=np.concatenate(split['Q']), orig=np.concatenate(split['orig']),
                          UV=np.concatenate(split['UV']), island=np.concatenate(split['island']),
                          wq=np.concatenate(split['wq']), share=np.asarray(split['share']),
                          groups=split['groups']))
    chk = QuadMesh(low['V'], low['Q']).check()
    log(f'[aviator] low: {len(low["V"])} verts, {len(low["Q"])} quads ({2 * len(low["Q"])} tris) in '
        f'{len(pieces) * 2 + len(centre)} pieces; ' + ', '.join(
            f'{REGIONS[r]} {int((low["region"] == r).sum()) * 2}' for r in range(len(REGIONS))
            if (low['region'] == r).any()) + f' tris; check {chk}')
    return low


def make_low(size=1024, spec=SPEC, log=print):
    """the low with its UVs as the export's arrays: build_low -> round_glasses.unwrap -> round_glasses.low_arrays"""
    low = build_low(spec, log)
    uvs = RG.unwrap(low, size, log=log)
    return RG.low_arrays(low, uvs), low, uvs


# ==================================================================================================== THE HIGH
def lens_patch(spec=SPEC, n_r=14, n_a=120):
    """the left glass's MID-surface as a dense polar patch (the outline + 0.35 mm, scaled in toward the centre)"""
    d = dims(spec)
    _, P = outline(spec)
    P = P[::len(P) // n_a]
    P = P + _out_normals(P) * 0.00035
    t = np.linspace(1.0, 0.04, n_r)
    G = (P[None, :, :] * t[:, None, None]).reshape(-1, 2)
    V = d['C'] + np.column_stack([G[:, 0], G[:, 1], -lens_sag(spec, G[:, 0], G[:, 1]) - 0.5 * spec['lens_t']])
    na = len(P)
    T = []
    for i in range(n_r - 1):
        for j in range(na):
            a, b, c, e = i * na + j, i * na + (j + 1) % na, (i + 1) * na + (j + 1) % na, (i + 1) * na + j
            T += [[a, b, c], [a, c, e]]
    ctr = len(V)
    V = np.vstack([V, d['C'] + np.array([0.0, 0.0, -0.5 * spec['lens_t']])])
    last = (n_r - 1) * na
    T += [[last + j, last + (j + 1) % na, ctr] for j in range(na)]
    return V, np.array(T, np.int32)


def build_sdf(spec=SPEC, sides=(1,)):
    """the HIGH (the bake's field: the left half and the two bridges): the rim a SWEEP of its oval section round the
    lens; the glass a SHELL over its mid-surface (its edge inside the rim); the brow bar and the lower bridge SWEEPs
    blended onto the rims by 0.3 mm (the solder); the endpiece a ROUNDCONE onto the hinge's drum (a REVOLVE, its
    edges eased); the temple one SWEEP whose radius swells into the acetate tip; the pad arm a SWEEP, the pad an
    ELLIPSOID"""
    d = dims(spec)
    prog = sdf.Program()
    up = np.array([0.0, 1.0, 0.0])

    def dense(P, n):
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        t = np.linspace(0.0, s[-1], n)
        return np.column_stack([np.interp(t, s, P[:, k]) for k in range(3)]), t
    for side in sides:
        P, N3 = rim_curve(spec, 360)
        prog.sweep(mirror(P, side), mirror(N3, side), 0.5 * spec['rim_w'], aspect=spec['rim_d'] / spec['rim_w'],
                   name=f'rim {side:+d}')
        Vl, Tl = lens_patch(spec)
        if side < 0:
            Vl, Tl = mirror(Vl, side), Tl[:, ::-1]
        prog.shell(Vl, Tl, 0.5 * spec['lens_t'], k=0.0, maxd=0.01, name=f'lens {side:+d}')
        E, H = mirror(d['E'], side), mirror(d['H'], side)
        prog.roundcone(E, H, 0.5 * spec['lug_d'], 0.5 * spec['lug_d'], k=0.0002, name=f'lug {side:+d}')
        hh, rb, c = 0.5 * spec['hinge_h'], spec['hinge_r'], 0.00025
        prog.revolve([(0.0, -hh), (rb - c, -hh), (rb, -hh + c), (rb, hh - c), (rb - c, hh), (0.0, hh)], H, up,
                     name=f'hinge {side:+d}')
        Pt, st, sb = temple_path(spec, side)
        Pd, sd = dense(Pt, 260)
        prog.sweep(Pd, np.tile([1.0, 0.0, 0.0], (len(Pd), 1)), temple_r(spec, sd, sb), k=0.0001,
                   name=f'temple {side:+d}')
        root, pc, nf = pad_frame(spec, side)
        Pa = np.array([root, root + 0.45 * mirror(np.array(spec['pad_off']) + np.array([0.0005 / 0.45, 0.0,
                                                                                         -0.0012 / 0.45]), side),
                       pc - nf * (0.35 * spec['pad_t'])])
        Pad, _ = dense(_bezier(Pa[0], Pa[1], Pa[1], Pa[2], 12), 40)
        prog.sweep(Pad, np.tile(up, (len(Pad), 1)), 0.5 * spec['pad_arm_d'], k=0.0002, name=f'pad arm {side:+d}')
        e_long = _unit(up - nf * nf[1])
        e1 = np.cross(e_long, nf)
        prog.ellipsoid(pc, [0.5 * spec['pad_w'], 0.5 * spec['pad_len'], 0.5 * spec['pad_t']],
                       axes=np.column_stack([e1, e_long, nf]), name=f'pad {side:+d}')
    Pb, _ = dense(brow_curve(spec, 60), 200)
    prog.sweep(Pb, np.tile(up, (len(Pb), 1)), 0.5 * spec['brow_d'], k=0.0003, name='brow')
    Pg, _ = dense(bridge_curve(spec, 60), 160)
    prog.sweep(Pg, np.tile(up, (len(Pg), 1)), 0.5 * spec['bridge_d'], k=0.0003, name='bridge')
    return prog


def bounds(spec=SPEC, pad=0.003):
    """the voxel grid's box: the left half and the whole bridges (the bake's set)"""
    d = dims(spec)
    Pt, st, sb = temple_path(spec, 1)
    lo = np.minimum(Pt.min(0), [-d['J'][0] - 0.004, d['C'][1] - 0.5 * spec['lens_b'] - 0.003, -0.012]) - pad
    hi = np.maximum(Pt.max(0), [d['H'][0] + 0.003, d['B1'][1] + 0.002, d['zl'] + 0.003]) + pad
    return lo, hi


# =========================================================================================== THE MATERIAL PASS
MATERIAL = dict(
    seed=29,
    gold=(1.00, 0.77, 0.34),        # the plating: gold's F0 (physicallybased.info, as the round glasses')
    nickel=(0.66, 0.61, 0.53),      # the base metal where the plating is rubbed through
    acetate=(0.020, 0.019, 0.019),  # the tips: polished black acetate
    silicone=(0.78, 0.77, 0.73),    # the pads: clear silicone, a little yellowed
    grime=(0.16, 0.13, 0.10),
    g15=(0.125, 0.153, 0.122),      # the G-15 glass: its measured transmittance (ACCESSORY_REFERENCE 9), the lens's
    #                                 base colour: the runtime's lens transmits through it (and wear()'s palette
    #                                 `glass` recolours it: brown, mirror blue, clear)
    gold_rough=0.16,
    acetate_rough=0.20,
    silicone_rough=0.42,
    glass_rough=0.04,
    worn=1.0,                       # the plating rubbed through on the sharpest edges
    grime_amt=1.0,
    dust=1.0,                       # dust and smears on the glass
)
VARIANTS = dict(
    gold_g15=dict(),                                    # as baked: a gold frame, G-15 glass
    gunmetal=dict(plating=0x4a4c50),                    # a gunmetal frame
    silver_blue=dict(plating=0xd8d8dc, glass=0x3a5f8a),  # a silver frame, a blue lens
    gold_brown=dict(glass=0x7a5230),                    # a gold frame, a brown (B-15) lens
)


@wp.struct
class ASurf:
    h: float
    col: wp.vec3
    rough: float
    metal: float
    zone: float
    wear: wp.vec4


@wp.func
def av_surf(p: wp.vec3, reg: int, at: wp.vec4, conv: float, ao: float, aol: float, texel: float,
            C: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32), seed: int, full: int):
    """the aviator's surface at the point p of the low's region reg. full = 0: the height only"""
    o = ASurf()
    h = float(0.0)
    col = wp.vec3(0.5, 0.5, 0.5)
    rough = float(0.5)
    metal = float(0.0)
    zone = float(0.0)
    w_grime = float(0.0)
    w_worn = float(0.0)
    w_dust = float(0.0)
    occl = wp.clamp(1.6 * (1.0 - ao) + 3.0 * wp.max(-aol, 0.0), 0.0, 1.0)
    if reg <= 4 or reg == 6:
        # THE PLATED FRAME: polished gold; a fine drawn grain along each wire; the plating rubbed through on its
        # sharpest edges; grime where two parts meet
        h = 0.0000012 * proc.noise3(wp.vec3(p[0] / 0.00012, p[1] / 0.00012, p[2] / 0.00012), seed + 1) * \
            proc.smoothstep(2.0, 3.5, 0.00012 / texel)
        if full == 1:
            edge = proc.smoothstep(1.3, 2.6, conv) * (0.35 + 0.65 * proc.smoothstep(-0.2, 0.5, proc.noise3(
                p / 0.0025, seed + 3)))
            w_worn = S[4] * edge
            g = S[5] * wp.clamp(0.9 * occl * occl, 0.0, 1.0) * (0.5 + 0.5 * proc.smoothstep(-0.3, 0.6, proc.fbm3(
                p / 0.003, 2, 2.0, 0.5, seed + 5)))
            w_grime = g
            col = M.mix3(M.mix3(C[0], C[1], 0.8 * w_worn), C[4], 0.55 * g)
            rough = S[0] + 0.05 * proc.noise3(p / 0.0012, seed + 7) + 0.30 * g + 0.04 * w_worn
            metal = 1.0 - 0.6 * g
            zone = 0.0
    elif reg == 5:
        # THE ACETATE TIPS: polished black
        if full == 1:
            g = S[5] * wp.clamp(0.7 * occl, 0.0, 1.0)
            w_grime = g
            col = M.mix3(C[2], C[4], 0.25 * g)
            rough = S[1] + 0.05 * proc.noise3(p / 0.002, seed + 9) + 0.2 * g
            zone = 2.0 / 3.0
    elif reg == 7 or reg == 8:
        # THE PADS: clear silicone
        if full == 1:
            g = S[5] * wp.clamp(0.8 * occl, 0.0, 1.0)
            w_grime = g
            col = M.mix3(C[3], C[4], 0.35 * g)
            rough = S[2] + 0.05 * proc.noise3(p / 0.002, seed + 11)
            zone = 2.0 / 3.0
    else:
        # THE G-15 GLASS: polished; faint dust in soft patches and along the rim
        if full == 1:
            d = S[6] * (0.55 * proc.smoothstep(0.25, 0.75, proc.fbm3(p / 0.007, 3, 2.0, 0.5, seed + 13))
                        * proc.smoothstep(-0.2, 0.5, proc.noise3(p / 0.021, seed + 15)) + 0.6 * occl)
            d = wp.clamp(d, 0.0, 1.0)
            w_dust = d
            col = C[5] * (1.0 + 0.5 * d)
            rough = S[3] + 0.22 * d
            zone = 1.0
    o.h = h
    o.col = col
    o.rough = rough
    o.metal = metal
    o.zone = zone
    o.wear = wp.vec4(w_grime, w_worn, w_dust, 0.0)
    return o


@wp.kernel
def k_aviator(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
              ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32),
              d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_base: wp.array(dtype=wp.vec4),
              d_aol: wp.array(dtype=wp.float32), d_conv: wp.array(dtype=wp.float32), C: wp.array(dtype=wp.vec3),
              S: wp.array(dtype=wp.float32), texel: float, seed: int, o_alb: wp.array(dtype=wp.vec3),
              o_nrm: wp.array(dtype=wp.vec3), o_orm: wp.array(dtype=wp.vec3), o_mask: wp.array(dtype=wp.vec4),
              o_wear: wp.array(dtype=wp.vec4), o_hit: wp.array(dtype=wp.int32)):
    """space_helmet.k_helmet's frame (the bake's normal carried, the texture tier's height differenced over the low,
    the roughness widened by the normals' spread inside the texel), with the aviator's surface function"""
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
    acc_z = float(0.0)
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
            sf = av_surf(pb0, reg, lo.attr, d_conv[tid], d_ao[tid], d_aol[tid], texel, C, S, seed, 1)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1:
                pbx = lx.p + lx.n * hb
                pby = ly.p + ly.n * hb
                hx = av_surf(pbx, reg, lx.attr, 0.0, 1.0, 0.0, texel, C, S, seed, 0).h
                hy = av_surf(pby, reg, ly.attr, 0.0, 1.0, 0.0, texel, C, S, seed, 0).h
                h0 = av_surf(pb0, reg, lo.attr, 0.0, 1.0, 0.0, texel, C, S, seed, 0).h
                g = M.surface_grad(pb0, pbx, pby, h0, hx, hy)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            acc_a = acc_a + sf.col
            acc_r = acc_r + wp.clamp(sf.rough, 0.03, 1.0)
            acc_m = acc_m + sf.metal
            acc_z = acc_z + sf.zone
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
    wr = acc_w / fh
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    o_orm[tid] = wp.vec3(d_ao[tid], wp.clamp(rr, 0.0, 1.0), wp.clamp(acc_m / fh, 0.0, 1.0))
    o_mask[tid] = wp.vec4(wp.max(wr[0], wr[2]), wr[1], acc_z / fh, 0.0)
    o_wear[tid] = wr
    o_hit[tid] = 1


def run_material(L, drivers, size, texel, ss=2, recipe=MATERIAL, log=print):
    """the material pass over the aviator's one texture set, on the bake set's triangles (the left half and the two
    bridges). Returns soft_common.finish_maps' dict (albedo, normal, orm with METALNESS in B, masks RGB (R grime /
    dust, G the plating worn through, B the palette zone), wear, palette_base)"""
    import time

    from .. import calib
    t0 = time.time()
    sel = np.asarray(L['bake'], bool)
    F = L['F'][sel]
    uvm = M.uv_bvh(F, L['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(L['V'], F, L['N'], L['TAN'], L['ATTR'])
    keep = {k: drivers[k] for k in ('normal', 'ao', 'curvature', 'base', 'mat') if k in drivers}
    Dv = M.driver_arrays({**keep, **calib.relief_drivers(keep, 1.0 / texel, ao_sigma_mm=1.2, fine_sigma_mm=0.08,
                                                         mid_sigma_mm=0.35)})
    C = np.array([recipe['gold'], recipe['nickel'], recipe['acetate'], recipe['silicone'], recipe['grime'],
                  recipe['g15']], np.float32)
    S = np.array([recipe['gold_rough'], recipe['acetate_rough'], recipe['silicone_rough'], recipe['glass_rough'],
                  recipe['worn'], recipe['grime_amt'], recipe['dust']], np.float32)
    n = size * size
    o_alb, o_nrm, o_orm = (wp.zeros(n, dtype=wp.vec3) for _ in range(3))
    o_mask, o_wear = wp.zeros(n, dtype=wp.vec4), wp.zeros(n, dtype=wp.vec4)
    o_hit = wp.zeros(n, dtype=wp.int32)
    wp.launch(k_aviator, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
                                        wp.array(np.asarray(L['region'], np.int32)[sel], dtype=wp.int32), Dv['normal'],
                                        Dv['ao'], Dv['base'], Dv['ao_local'], Dv['conv'], wp.array(C, dtype=wp.vec3),
                                        wp.array(S, dtype=wp.float32), float(texel), int(recipe['seed']), o_alb, o_nrm,
                                        o_orm, o_mask, o_wear, o_hit])
    wp.synchronize()
    img = lambda a, k: np.asarray(a.numpy()).reshape(size, size, k)[::-1]
    cov = np.asarray(o_hit.numpy()).reshape(size, size)[::-1] > 0
    wear = img(o_wear, 4)
    maps = SC.finish_maps(img(o_alb, 3), img(o_nrm, 3), img(o_orm, 3), img(o_mask, 4), wear, cov, ZONES)
    log(f'[aviator] material {size}^2 x ss {ss}: {time.time() - t0:.1f}s over {int(cov.sum())} texels '
        f'({cov.mean() * 100:.1f} % of the sheet); palette base (linear) '
        + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in maps['palette_base'].items()))
    return maps


# ===================================================================================================== THE FIT
def fit_data(spec=SPEC, low=None, n_probe=400):
    """round_glasses.fit_data's record for this frame (the runtime's glassesPose reads it): the lens's mean aperture
    radius (the fit scales it to FIT_EYE x the eye's radius), per side the rest lens centre, the lens joint, the
    endpiece's direction in the lens plane, the hinge pin and the temple's rest rotation, the ear bend, the pad arm's
    root and fold axis, the cable joints; with a low, clearance PROBES for a validator to pose"""
    d = dims(spec)
    rj = rest_joints(spec)
    rnd = lambda a: np.round(np.asarray(a, np.float64), 6).tolist()
    sides = {}
    for side, sfx in ((1, 'L'), (-1, 'R')):
        pe = np.radians(spec['end_phi'])
        root, pc, nf = pad_frame(spec, side)
        cl = []
        for i in range(N_CABLE):
            par = rj[f'hook_{sfx}' if i == 0 else f'cable_{sfx}{i}'][1]
            cl.append(rnd((np.linalg.inv(par) @ rj[f'cable_{sfx}{i + 1}'][1])[:3, 3]))
        sides[sfx] = dict(lens_centre=rnd(mirror(d['C'], side)), junction=rnd(mirror(d['J'], side)),
                          end_dir=rnd(mirror([np.cos(pe), np.sin(pe), 0.0], side)),
                          hinge=rnd(mirror(d['H'], side)), temple_rot=rnd(rj[f'temple_{sfx}'][1][:3, :3]),
                          bend=rnd(mirror(d['Bd'], side)), pad_root=rnd(root), pad_axis=rnd(pad_axis(spec, side)),
                          cable_local=cl)
    out = dict(archetype='glasses', prop=NAME, joints=list(JOINTS),
               lens=dict(radius=round(d['r_mean'], 6), rim_outer=round(d['r_mean'] + spec['rim_w'], 6),
                         thickness=spec['lens_t'], ior=spec['lens_ior'],
                         box=[spec['lens_a'], spec['lens_b']]),
               eye_factor=FIT_EYE, cable_d=spec['tip_d'], sides=sides,
               seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0], left=[1.0, 0.0, 0.0]),
               variants={k: {z: f'#{c:06x}' for z, c in v.items()} for k, v in VARIANTS.items()})
    if low is not None:
        rng = np.random.default_rng(5)
        pick = rng.choice(len(low['V']), min(n_probe, len(low['V'])), replace=False)
        out['probes'] = dict(points=rnd(low['V'][pick]), weights=np.round(low['W'][pick], 4).tolist(),
                             region=[int(np.bincount(low['region'][np.nonzero((low['Q'] == i).any(1))[0]]).argmax())
                                     for i in pick])
    return out


# ========================================================================================== THE FORGE'S STAGES
def forge_bake(out_dir, size=1024, voxel_size=0.00006, band=0.0004, ss=2, seed=7, spec=SPEC, log=print):
    """the low + UVs -> the voxel high of the left half and the bridges (GPU) -> the bake; writes low_aviator.npz and
    drivers_aviator.npz (the material pass reads them in a process of its own)"""
    import os
    import pickle
    import time

    from .. import bake, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    L, low, uvs = make_low(size, spec, log)
    prog = build_sdf(spec)
    f = np.abs(prog.eval(L['V'][L['side'][np.repeat(np.arange(len(L['F'])), 1)][:0].astype(int)] if False else
                         low['V'][np.unique(low['Q'][low['side'] >= 0])]))
    log(f'[aviator] low (the bake set) on the block-out: |sdf| p50 {np.median(f) * 1e3:.3f} mm, p95 '
        f'{np.percentile(f, 95) * 1e3:.3f} mm, max {f.max() * 1e3:.3f} mm')
    # faces BURIED in another part (the lens's edge in the rim, a bar's foot in its rim, the temple's root in the
    # hinge) are left out of the bake and the paint: round_glasses.forge's rule (inside the solid, and the way out
    # along the face's own normal is long)
    cen = L['V'][L['F']].mean(1)
    fnm = np.cross(L['V'][L['F'][:, 1]] - L['V'][L['F'][:, 0]], L['V'][L['F'][:, 2]] - L['V'][L['F'][:, 0]])
    fnm /= np.maximum(np.linalg.norm(fnm, axis=1, keepdims=True), 1e-20)
    pex, _ = prog.project(cen, fnm, maxd=0.003)
    buried = (prog.eval(cen) < -0.00005) & (np.linalg.norm(pex - cen, axis=1) > 0.0004) & L['bake']
    L['bake'] = L['bake'] & ~buried
    log(f'[aviator] {int(buried.sum())} of the bake set\'s triangles buried in another part (not baked: their texels '
        f'dilate)')
    lo, hi = bounds(spec)
    d = dims(spec)
    keepv = lambda cc: cc[:, 0] > -(d['J'][0] + 0.004)             # the left half and the whole bridges
    G = voxel.SparseSDF(prog, lo, hi, voxel=voxel_size, band=band, keep=keepv, log=log)
    sel = L['bake']
    res = bake.bake(G, L['V'], L['F'][sel], L['UV'], L['N'], L['TAN'], L['region'][sel], size=size, ss=ss,
                    cage=0.0008, ao_r=0.004, cav_r=0.0006, n_ao=64, n_cav=32, n_thk=2, thk_max=0.003, cage_min=0.00003,
                    reach_margin=0.0002, far_max=0.0004, proj_tol=2.0e-5, seed=seed,
                    region_names={i: r for i, r in enumerate(REGIONS)}, log=log)
    keep_ = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
             if k != 'position' and isinstance(v, np.ndarray)}
    np.savez_compressed(os.path.join(out_dir, f'drivers_{NAME}.npz'), **keep_)
    np.savez_compressed(os.path.join(out_dir, f'low_{NAME}.npz'),
                        **{k: v for k, v in L.items() if isinstance(v, np.ndarray)}, px_per_m=L['px_per_m'],
                        size=L['size'])
    with open(os.path.join(out_dir, f'low_{NAME}.pkl'), 'wb') as fh:
        pickle.dump(low, fh)
    log(f'[aviator] the bake is saved (drivers_{NAME}.npz) after {time.time() - t0:.0f}s')
    return L, low


def export(out_dir, L, maps, spec=SPEC, low=None):
    """round_glasses.export_glb's layout (a SKINNED glb: one mesh, two primitives: the frame and the glass with
    KHR_materials_transmission / _ior / _volume; the masks in the frame's volume slot; the skeleton; the fit in the
    node's and the file's extras), the materials named `aviator` and `aviator_lens` (the runtime tells the glass by
    'lens' in its material's name), the masks RGB without alpha"""
    import os

    from .. import gltf
    g = gltf.GLB()
    t_base = g.texture(maps['albedo'], fmt='png')
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='png')
    t_msk = g.texture(maps['masks'], fmt='png')
    chans = ('R grime on the frame / dust on the glass, G the plating worn through, B palette zone (0 the plating, '
             '1/3 the base metal, 2/3 the acetate tips and the pads, 1 the glass); RGB, no alpha')
    m_frame = g.material(NAME, base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='prop', prop=NAME, masks=t_msk, masks_channels=chans, palette_zones=list(ZONES),
        palette_base=maps.get('palette_base', {}),
        palette_variants={k: {z: f'#{c:06x}' for z, c in v.items()} for k, v in VARIANTS.items()}))
    m_lens = g.material(f'{NAME}_lens', base=t_base, normal=t_nrm, orm=t_orm, extras=dict(
        bestiary='prop', prop=NAME, part='lens', masks=t_msk, masks_channels=chans))
    lens = g.j['materials'][m_lens]
    lens['pbrMetallicRoughness']['metallicFactor'] = 0.0
    lens['extensions'] = {'KHR_materials_transmission': {'transmissionFactor': 1.0},
                          'KHR_materials_ior': {'ior': spec['lens_ior']},
                          'KHR_materials_volume': {'thicknessFactor': spec['lens_t'],
                                                   'attenuationColor': list(MATERIAL['g15']),
                                                   'attenuationDistance': 0.03}}
    lens['alphaMode'] = 'OPAQUE'
    g.ext_used.update({'KHR_materials_transmission', 'KHR_materials_ior', 'KHR_materials_volume'})
    skin, joint_nodes = g.skeleton(skeleton(spec))
    glass = L['region'] == 9
    mesh = g.mesh(NAME, L['V'], L['N'], L['TAN'], L['UV'], [(L['F'][~glass], m_frame), (L['F'][glass], m_lens)],
                  joints=L['joints'], weights=L['weights'])
    fit = fit_data(spec, low)
    g.node(NAME, mesh=mesh, skin=skin, root=True, extras=dict(bestiary='prop', fit=fit))
    return g.save(os.path.join(out_dir, f'{NAME}.glb'),
                  extras=dict(bestiary=dict(prop=NAME, archetype='glasses', units='m', up='+Y', forward='+Z',
                                            left='+X', triangles=int(len(L['F'])), fit=fit)))
