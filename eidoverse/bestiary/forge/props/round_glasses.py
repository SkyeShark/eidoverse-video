"""ROUND METAL EYEGLASSES: the second Bestiary accessory (DESIGN.md "Accessories"), a small RIGGED prop built the forge
way at real size (work/bestiary/research/ACCESSORY_REFERENCE.md §7, work/bestiary/patches/accessories_fit.md §4).

  parts -> block-out SDF:  the eyewires and the lenses as REVOLVEs about the lens axes (the eyewire a grooved D
                           section, the lens a plano crown-glass meniscus with a 115 deg V-bevel seated in the groove), a
                           C-bridge band as a SWEEP, ivory pads in metal cups (REVOLVEs) on wire pad arms, the endpiece's
                           lug and its three-knuckle hinge barrel (the knuckles parted by hairline gaps, the endpiece cut
                           back round the temple's knuckle: a slot, so the hinge could turn) under a pan-head screw, the
                           temples as one SWEEP each from the hinge strap through the shaft and the cable's crimp sleeve
                           to the riding-bow ear hook and its ferrule
  -> the low:              one designed piece per part (rings round each wire, revolve rings round each disc and the
                           barrel, quad-grid caps: the screw's head is the barrel's top cap), the left half mirrored to
                           the right
  -> UV islands:           analytic (each wire unrolled along its length and round its section, discs projected flat);
                           the right half STACKED on the left's texels (house rule: repeats share one set of texels) but
                           for the right lens (its own prints), the bridge its own island, the lenses' outer faces at 0.70
                           of the frame's density, their inner faces at 0.45
  -> sculpt plan:          the screw slots, the lug's rim-lock line, the cable's crimp
  -> voxel high + bake     (the frame without its lenses: the glass is not baked; forge() below)
  -> material pass:        rolled gold over nickel silver (the plating rubbed through where skin and fingers touch it),
                           micro-scratches along each wire, the cable's coil, milgrain on the bridge, grime in the groove
                           and the seams, aged ivory pads, the lenses' crown-glass tint and oily prints
  -> a SKINNED glb with its FIT data, 15 joints: glasses_root at the bridge's contact point (the bridge skinned from it
     to the lens joints, so it bends over a head when the lenses splay); lens_L / lens_R at the bridge's ends (the fit
     turns each lens onto its eye); temple_L / temple_R at the hinge pins (aimed at the hooks; the whole barrel rides
     the lens joint); hook_L / hook_R at the ear bends: the shaft is skinned between its temple and its hook joint, so
     it shortens or lengthens to reach the hook while the ear hook keeps its shape (a scaled temple bone squashed the
     15 mm curl to a hairpin on the octopus, whose hooks lie 34 mm behind the hinges where a man's lie 95 mm), and the
     hook joint carries the roll that hangs the ear hook down the skin (rolled at the hinge, the temple's knuckle stood
     26 deg out of the barrel; now the temple turns 3.7 deg off its pin); pad_L / pad_R at the pad arms' roots and
     cable_X1..3 down each ear hook: an optician bends pad arms to the face and a cable temple wraps its wearer, and on
     the v4 octopus neither fits rigid (the pads stood in the turrets 3.6 mm deep, the curl 16-23 mm in the head at every
     roll): validate_fit bends and drapes them against the creature's SDF, the seat's validated entry for this prop
     (seat_hat's pattern), which fit_pose and the runtime apply
  -> the fit: fit_pose (the runtime's math; runtime/accessories.js glassesPose is its port, parity 4e-16), validate_fit
     (the forge's check and the validated entry), checked in work/bestiary/tests/t25_glasses_look.py
BUDGETS: 5936 triangles (the frame 5456: the eyewires 1920, the ear hooks 880, the barrels 768, the bridge 608 (39
stations: the splayed lenses stretch it 37 -> 68 mm), the cups 512, the temples 320, the pads 192, the pad arms 192,
the lugs 64; the glass 480); one 1024^2 texture set at 14302 px/m (0.070 mm a texel: ~1.6x study T's glasses, ~9000
px/m, ACCESSORY_REFERENCE §1.4), the lenses' outer faces at 10011 px/m and their inner at 6436

Frame: metres, the glasses' own frame = their seat's (accessories_fit.md §1, §4): +Z the way the lenses face (the
bridge's skin normal), +Y up, +X the wearer's left; the origin at the bridge's CONTACT point (the C-bridge apex's lowest
point along -Z: where the bridge rests on the skin).

The forge calls it makes: sdf.Program (.revolve, .sweep, .roundcone, .begin_group, .eval, .project, .normals),
  voxel.SparseSDF (+ STROKE_CYL, STROKE_TORUS carves), bake.bake / low_frames / dilate_all, uv.pack / self_overlap /
  footprint, material.low_at / to_world / to_tangent / surface_grad / uv_bvh / corner_arrays / driver_arrays,
  calib.relief_drivers, proc.noise3 / fbm3 / cellular3 / smoothstep, rig.Skeleton / lbs, gltf.GLB.

MEASURED on the references (refs/accessories/round_metal_glasses/, work/bestiary/patches/glasses/measure_refs.py;
the scale from the Auckland Museum records on their Commons pages: ref 02 "length: 122mm, width: 38mm", ref 01
"length: 120mm, width: 33mm", ref 03 "HxWxL; 39 x 122 x 125 mm", "depth: 110mm"):
  * ref 02 (C-bridge, pads, cable temples): the eyewire 38 mm outside (the record); rim ellipses fitted (RANSAC conics:
    the band 37.1-37.6 mm across, the aperture 36.1-37.2), tilt 38 deg; the lens centres 55.4-56.4 mm apart in the
    lens plane: DBL 19.2 mm; the front ~104 mm hinge to hinge; the eyewire's face 0.53 mm (FWHM of its dark dip: low,
    the highlights reach the white ground) to 0.89-0.93 (its silhouette at 30 % depth: high, the photo's blur), its depth
    ~1.1 mm (the crops at the rim's minor-axis ends); the bridge joins each rim 54 deg above the horizontal, its band 1.25
    mm across the face and 0.73 edge-on; the pads ivory or bone discs in metal cups, 8.6 mm long with the cup and 0.99
    mm thick, measured colour linear (0.65, 0.43, 0.22) lit (white-balanced on the ground); the hinge barrel 3.8-4.3 mm
    across (silhouette, end-on, with its screw head); the temple shaft 1.07-1.16 mm; the curl a coiled cable, 0.90 mm
    near its tip, the coil's dashes ~0.27 mm apart; grime along the lens edge in the groove (brown deposits)
  * ref 01 (steel, brow bar, cable temples): the eyewire 33 mm outside (the record), its wire 0.72-0.79 mm
    (silhouette), the temple 1.11 mm, the cable ending in a teardrop ferrule 2.7 x 1.7 mm; DBL ~20-23 mm
  * ref 03 (gold panto, keyhole bridge): the front 122 mm wide and 39 high, the temples reaching 110 mm behind it; a
    hinge block with a slotted screw; milled bead (milgrain) edges on the bridge
BUILT TO (SPEC): the aperture 37.0 mm in a 38.7 mm eyewire of 0.85 x 1.20 mm (between ref 02's two face readings and
its depth), DBL 19.5, the C-bridge at 52 deg rising 5.5 mm with a 5.0 mm setback, a 1.25 x 0.75 mm band, 8.0 mm ivory
pads 1.0 mm thick, a 3.0 mm three-knuckle barrel 3.6 mm tall, a 1.05 -> 0.95 mm shaft 95 mm to the ear bend, a 0.90 mm
cable curling 200 deg at 15 mm radius, a 2.7 x 1.7 mm ferrule; the front 103.9 mm hinge to hinge. The lens is plano
crown glass (ior 1.523 [P1/R25]), 1.9 mm thick, base 4 front. The curl's radius and sweep, the pad arm's offsets and
the knuckle split are typical-construction estimates [E]; the metals' F0 are physicallybased.info's [P1].
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc
from .. import sdf
from ..mesh import QuadMesh

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})   # forward-only; noise neighbour loops left rolled

SPEC = dict(
    lens_a=0.0370,          # the lens aperture (the boxing A): ref 02 36.1-37.2 mm inside its 38 mm eyewire
    dbl=0.0195,             # the distance between the lenses: ref 02 19.2 mm, ref 01 ~20-23
    rim_face=0.00085,       # the eyewire's radial face and its depth along the lens axis (ref 02: 0.53-0.93, ~1.1)
    rim_depth=0.00120,
    rim_round=0.00020,      # the section's outer corners, the inner lips' corners
    lip_round=0.00012,
    rim_bulge=0.00006,      # the outer face's convexity: a D section
    groove_d=0.00030,       # the lens groove: a V cut this deep into the inner face, this wide at it
    groove_w=0.00070,
    lens_t=0.0019,          # plano crown glass: centre and edge 1.9 mm
    lens_base=4.0,          # its front curve in dioptres at n 1.523 (R 130.8 mm: 1.35 mm of sag at the edge)
    lens_ior=1.523,
    bevel=115.0,            # the edge's V-bevel (included angle), its apex in the groove
    bridge_phi=52.0,        # the C-bridge leaves each rim this far above the horizontal (ref 02: ~54 deg)
    bridge_rise=0.0055,     # its arch above the junctions and its setback behind the rims' plane
    bridge_back=0.0050,
    band_w=0.00125,         # its band across the face and edge-on (ref 02: 1.25, 0.73)
    band_t=0.00075,
    pad_d=0.0080,           # the ivory pads: diameter, thickness, the face's dome (ref 02: 8.6 with the cup, 0.99)
    pad_t=0.0010,
    pad_dome=0.0003,
    cup_lip=0.00025,        # the cup's lip over the disc's edge, its back's depth
    cup_back=0.00045,
    pad_phi=176.0,          # the pad arm leaves the rim's back here (degrees round the lens from +X toward +Y)
    pad_off=(-0.0006, -0.0020, -0.0032),   # the pad's centre from the arm's root (toward the nose, down, back): close
                            # behind the rim (8.6 mm back, as a modern pad sits, the v4 turrets took them 3.6 mm in;
                            # here the fit bends the arm 20 deg and they clear by 0.34 mm)
    pad_face=(-0.78, -0.06, -0.62),        # the pad's face normal: toward the nose's flank
    pad_arm_d=0.00070,
    end_phi=8.0,            # the endpiece on the rim's outer side, this far above the horizontal
    lug_len=0.0022,         # the lug from the rim's face to the barrel; its height and depth (its upper half holds
    lug_h=0.0020,           # the top knuckle, its lower half the bottom one, the rim-lock split between them: at
    lug_d=0.0013,           # 1.6 mm it met the outer knuckles by 0.25 mm slivers once the slot was cut)
    barrel_r=0.0015,        # the hinge barrel (ref 02: 3.8-4.3 mm across with its screw head) and its height
    barrel_h=0.0036,
    knuckle_mid=0.0011,     # the temple's (middle) knuckle; the endpiece's two take the rest
    knuckle_gap=0.00008,    # the hairline between knuckles (2 voxels of the high: it survives the plan's smooth)
    knuckle_cham=0.00005,   # each knuckle end's chamfer
    screw_r=0.00095,        # the hinge screw's domed head: a pan head, its slot cut across it (plan_glasses)
    screw_h=0.00030,
    strap_len=0.0070,       # the temple's flat strap from the knuckle, then the round shaft (the strap 0.2 mm
    strap_h=0.0009,         # shorter than its knuckle: as tall, its fillet bridged the gaps to the outer knuckles)
    strap_w=0.00075,
    temple_d=0.00105,       # the shaft at the hinge and at the bend (ref 02: 1.07-1.16; ref 01: 1.11)
    temple_d_end=0.00095,
    temple_len=0.095,       # the hinge to the ear bend (ref 03: the temples reach 110 mm behind the front)
    temple_splay=2.0,       # degrees outward
    sleeve_len=0.0030,      # the cable's crimp sleeve at the bend
    sleeve_d=0.00125,
    hook_r=0.0150,          # the riding-bow ear hook: its radius, its sweep, its plane tilted in toward the head
    hook_sweep=200.0,
    hook_tilt=10.0,
    cable_d=0.00090,        # the coiled cable (ref 02: 0.90 mm near the tip, the coil ~0.27 mm a turn)
    coil_pitch=0.00030,
    tip_len=0.0027,         # ref 01's teardrop ferrule
    tip_d=0.0017,
)
FIT_EYE = 1.25              # the lens radius per eye radius (accessories_fit.md §4: the old creator's eyeSize * 1.25)
REGIONS = ('rim', 'bridge', 'lug', 'knuckle', 'temple', 'hook', 'pad_arm', 'cup', 'pad', 'lens')
METAL = tuple(range(8))     # regions 0-7 are the frame's metal; 8 the ivory, 9 the glass
JOINTS = ('glasses_root', 'lens_L', 'lens_R', 'temple_L', 'temple_R', 'hook_L', 'hook_R', 'pad_L', 'pad_R',
          'cable_L1', 'cable_L2', 'cable_L3', 'cable_R1', 'cable_R2', 'cable_R3')
PARENT = {'lens': 'glasses_root', 'temple': 'lens', 'hook': 'temple', 'pad': 'lens', 'cable1': 'hook',
          'cable2': 'cable1', 'cable3': 'cable2'}
N_CABLE = 3                 # joints down the ear hook's cable past the bend: a cable temple conforms to its wearer
LENS_SHARE = 0.70           # the lenses' texel density relative to the frame's: ~9000 px/m, the study's for glasses
                            # (ACCESSORY_REFERENCE §1.4: a study-T glass material), a print's 0.45 mm ridges 4 texels (at a
                            # quarter, 3739 px/m, they were under 2 and the prints were drawn as 0.8 mm bullseyes);
LENS_BACK_SHARE = 0.45      # the inner faces less (one print a lens, seen through the glass): all four caps at 0.70
                            # filled the sheet so the outer faces stopped at 8897 px/m

MATERIAL = dict(
    # linear F0 (physicallybased.info, ACCESSORY_REFERENCE §1.2): the plating a rolled gold a shade paler than fine gold
    # (1.0, 0.773, 0.307) [E], worn through to nickel silver: nickel (0.697, 0.641, 0.563)
    gold=(1.0, 0.78, 0.36), nickel=(0.697, 0.641, 0.563), tarnish=(0.30, 0.22, 0.12),
    ivory=(0.70, 0.56, 0.34),             # ref 02's pad measured (0.65, 0.43, 0.22) lit; paler: at that chroma the
                                          # disc read as the gold's own hue in look-dev (t25 smoke)
    grime=(0.16, 0.10, 0.05),             # ref 02's groove deposits, brown
    glass=(0.93, 0.97, 0.95),             # crown glass's faint green (its iron) at 2 mm
    gold_rough=0.16, nickel_rough=0.26, ivory_rough=0.38, glass_rough=0.02, print_rough=0.24,
    scratch_rough=0.10,                   # the micro-scratches' roughness swing along the wire
    coil_amp=0.000035,                    # the cable's coil relief (half its groove depth)
    bead_amp=0.000030,                    # the bridge's milgrain beads
    # the lenses' FINGERPRINTS: a lens is taken by its edge, so three a lens near the rim, each (x, y from the lens's
    # centre in mm, +x toward +X; the long axis's angle in degrees; the semi-axis in mm (a fingertip leaves ~12 x 16);
    # its aspect; the whorl's core off the centre, in semi-axes; strength, its sign the face: + the outer, - the
    # inner (one face each: on both, a print doubled through the glass)) [E]; the left lens's then the right's
    prints=(((11.5, -9.0, 35.0, 7.0, 0.78, 0.25, 0.9), (-9.5, 12.0, -60.0, 6.0, 0.82, 0.30, -0.55),
             (2.5, -15.5, 95.0, 6.5, 0.75, 0.20, 0.7)),
            ((-12.5, -7.5, -25.0, 7.0, 0.80, 0.28, 0.85), (10.0, 11.5, 50.0, 5.5, 0.85, 0.22, -0.5),
             (-3.5, 15.0, 80.0, 6.5, 0.76, 0.30, 0.65))),
    print_ridge=0.00045,                  # an adult's ridge period (~0.45-0.5 mm)
    seed=53,
)


# ----------------------------------------------------------------------------------------------------- dimensions
def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _arch_plane(spec):
    """the C-bridge's plane: the apex's tangent X and the line down to the junction's height and setback; returns its
    unit normal P (up-forward: the band's top face faces it, the face ref 02's engraving shows from above)"""
    u = _unit([0.0, -spec['bridge_rise'], spec['bridge_back']])
    return _unit(np.cross([1.0, 0.0, 0.0], u)) * -1.0


def _apex_extent(spec):
    """how far the band's oval section reaches below its centreline along -Z at the apex (the contact's depth)"""
    P = _arch_plane(spec)
    n = np.cross(P, [1.0, 0.0, 0.0])
    a, b = 0.5 * spec['band_t'], 0.5 * spec['band_w']
    return float(np.hypot(a * n[2], b * P[2]))


def dims(spec=SPEC):
    """the left half's key points (the right mirrors x): the lens centre C, the aperture and eyewire radii, the rims'
    plane z, the bridge's junction J (its centreline's end on the rim's outer face), the apex's centreline point A, the
    endpiece's rim point, the hinge pin H and the ear bend; the origin is the bridge's contact point"""
    r_a = 0.5 * spec['lens_a']
    r_o = r_a + spec['rim_face']
    phi_j = np.radians(180.0 - spec['bridge_phi'])
    ez = _apex_extent(spec)
    A = np.array([0.0, 0.0, ez])                                   # the apex's centreline over the contact
    zl = ez + spec['bridge_back']
    C = np.array([0.5 * spec['dbl'] + r_a, -spec['bridge_rise'] - r_o * np.sin(phi_j), zl])
    J = C + r_o * np.array([np.cos(phi_j), np.sin(phi_j), 0.0])
    pe = np.radians(spec['end_phi'])
    E = C + r_o * np.array([np.cos(pe), np.sin(pe), 0.0])          # the endpiece's foot on the rim's outer face
    zb = zl - 0.0002                                               # the lug and the barrel a hair behind the rims
    H = np.array([E[0] + spec['lug_len'] + spec['barrel_r'] - 0.0004, E[1], zb])
    sp = np.radians(spec['temple_splay'])
    s0 = H + np.array([spec['barrel_r'] * 0.55, 0.0, -spec['barrel_r'] * 0.8])     # the strap leaves the knuckle
    Bd = s0 + spec['temple_len'] * np.array([np.sin(sp), 0.0, -np.cos(sp)])
    return dict(r_a=r_a, r_o=r_o, r_c=r_a + 0.5 * spec['rim_face'], zl=zl, C=C, J=J, A=A, E=E, H=H, s0=s0, Bd=Bd,
                phi_j=phi_j, ez=ez)


def mirror(P, side):
    """the right half (side -1) is the left's mirror in x"""
    P = np.array(P, np.float64)
    if side < 0:
        P[..., 0] = -P[..., 0]
    return P


# ------------------------------------------------------------------------------------------------- the profiles
def _arc(c, rad, a0, a1, n):
    a = np.linspace(a0, a1, n)
    return np.column_stack([c[0] + rad * np.cos(a), c[1] + rad * np.sin(a)])


def _chain(parts):
    out = [np.asarray(parts[0], np.float64)]
    for p in parts[1:]:
        p = np.asarray(p, np.float64)
        out.append(p[1:] if np.allclose(p[0], out[-1][-1], rtol=0.0, atol=1e-10) else p)
    return np.concatenate(out)


def rim_profile(spec=SPEC, n_arc=7):
    """the eyewire's section as a closed (rho, zeta) polygon for REVOLVE about the lens axis (rho from the axis, zeta
    along it from the rims' plane): the front face, its rounded outer corner, the slightly convex outer face (a D), the
    back, the inner lips and the V-groove between them that seats the lens's bevel (counter-clockwise)"""
    r_a = 0.5 * spec['lens_a']
    r_o = r_a + spec['rim_face']
    h = 0.5 * spec['rim_depth']
    rc, rl, gw, gd = spec['rim_round'], spec['lip_round'], 0.5 * spec['groove_w'], spec['groove_d']
    z = np.linspace(h - rc, -(h - rc), 9)
    bulge = spec['rim_bulge'] * (1.0 - (z / (h - rc)) ** 2)
    parts = [
        [[r_a + rl, h], [r_o - rc, h]],
        _arc([r_o - rc, h - rc], rc, np.pi / 2, 0.0, n_arc),
        np.column_stack([r_o + bulge, z]),
        _arc([r_o - rc, -(h - rc)], rc, 0.0, -np.pi / 2, n_arc),
        [[r_o - rc, -h], [r_a + rl, -h]],
        _arc([r_a + rl, -(h - rl)], rl, -np.pi / 2, -np.pi, n_arc),
        [[r_a, -(h - rl)], [r_a, -gw], [r_a + gd, 0.0], [r_a, gw], [r_a, h - rl]],
        _arc([r_a + rl, h - rl], rl, np.pi, np.pi / 2, n_arc),
    ]
    P = _chain(parts)
    return P[:-1] if np.allclose(P[0], P[-1]) else P


def lens_geom(spec=SPEC):
    """the lens: plano crown glass, front radius R1 = (n - 1) / base, back R2 = R1 - t (n - 1) / n (zero power), its
    edge a V-bevel whose apex sits in the groove 0.03 mm short of its bottom, the edge's mid-thickness on the rims'
    plane. Returns dict(R1, R2, rho_e (the apex), rho_b (where the bevel meets the faces), zf0, zb0 (the faces'
    centres), te (the edge thickness)) in (rho, zeta)"""
    n = spec['lens_ior']
    R1 = (n - 1.0) / spec['lens_base']
    t = spec['lens_t']
    R2 = R1 - t * (n - 1.0) / n
    rho_e = 0.5 * spec['lens_a'] + spec['groove_d'] - 0.00003
    sag = lambda R, r: R - np.sqrt(R * R - r * r)
    te = t - sag(R1, rho_e) + sag(R2, rho_e)
    zf0 = 0.5 * te + sag(R1, rho_e)
    half = np.radians(0.5 * spec['bevel'])
    # the bevel's radial run on each face: each face leaves the apex `half` off the radial, so it climbs te / 2 over
    # (te / 2) / tan(half): 0.61 mm at 115 deg (te / 2 x tan built a 65 deg V whose shoulders stood 1.23 mm inside
    # the aperture, a frosted second rim round every lens: review)
    db = 0.5 * te / np.tan(half)
    return dict(R1=R1, R2=R2, rho_e=rho_e, rho_b=rho_e - db, zf0=zf0, zb0=zf0 - t, te=te, t=t)


def lens_front(spec, rho):
    g = lens_geom(spec)
    return g['zf0'] - (g['R1'] - np.sqrt(g['R1'] ** 2 - np.asarray(rho) ** 2))


def lens_back(spec, rho):
    g = lens_geom(spec)
    return g['zb0'] - (g['R2'] - np.sqrt(g['R2'] ** 2 - np.asarray(rho) ** 2))


def lens_profile(spec=SPEC, n=24):
    """the lens as a closed (rho, zeta) polygon from the axis: the front surface out to the bevel, the bevel's apex,
    back in along the back surface to the axis (the axis segment closes it)"""
    g = lens_geom(spec)
    rf = np.linspace(0.0, g['rho_b'], n)
    front = np.column_stack([rf, lens_front(spec, rf)])
    back = np.column_stack([rf[::-1], lens_back(spec, rf[::-1])])
    return np.vstack([front, [[g['rho_e'], 0.0]], back])


def pad_profiles(spec=SPEC, n=6):
    """the pad as two closed (rho, zeta) polygons about its face normal, zeta 0 at the cup's seat: the ivory DISC
    (its domed face, its rounded edge) and the metal CUP (the lip rolled over the disc's edge, the domed back, the boss
    the pad arm holds)"""
    rp, t, dome, lip, cb = 0.5 * spec['pad_d'], spec['pad_t'], spec['pad_dome'], spec['cup_lip'], spec['cup_back']
    re = 0.30 * t                                                  # the disc's edge radius
    rr = np.linspace(0.0, rp - re, n)
    face = np.column_stack([rr, t + dome * (1.0 - (rr / (rp - re)) ** 2)])
    disc = np.vstack([face, _arc([rp - re, t - re], re, np.pi / 2, -np.pi / 2, n)[1:], [[rp - re, 0.0], [0.0, 0.0]]])
    ro = rp + lip
    rb, lb = 0.00060, 0.00070                                      # the boss
    cup = _chain([[[0.0, 0.0], [rp - 0.6 * lip, 0.0], [rp - 0.6 * lip, 0.45 * t]],
                  _arc([ro - 0.5 * lip, 0.45 * t], 0.5 * lip, np.pi, 0.0, n),
                  [[ro, 0.45 * t], [ro, 0.0]],
                  _arc([ro - cb, 0.0], cb, 0.0, -np.pi / 2, n),
                  [[ro - cb, -cb], [rb + 0.0002, -cb - 0.00005], [rb, -cb - 0.0002], [rb, -cb - lb], [0.0, -cb - lb]]])
    return disc, cup


def barrel_profiles(spec=SPEC):
    """the hinge barrel's three knuckles as closed (rho, y) polygons about the vertical pin (y from the middle
    knuckle's centre): the endpiece's top knuckle (crowned by the screw's domed head), the temple's middle knuckle,
    the endpiece's bottom knuckle, each with its ends' small chamfer, a hairline GAP between them (separate knuckles
    on one pin: carved V seams over 0.12 mm chamfers read as three stacked coins, t25), and the SLOT: the space round
    the middle knuckle the endpiece is cut back from (build_sdf subtracts it before the middle knuckle goes in: run
    into the barrel whole, the lug welded the temple's knuckle to the endpiece's)"""
    r, hh, hm = spec['barrel_r'], 0.5 * spec['barrel_h'], 0.5 * spec['knuckle_mid']
    cham, g = spec['knuckle_cham'], 0.5 * spec['knuckle_gap']

    def knuckle(y0, y1):
        return np.array([[0.0, y0], [r - cham, y0], [r, y0 + cham], [r, y1 - cham], [r - cham, y1], [0.0, y1]])
    sr, sh = spec['screw_r'], spec['screw_h']
    a = np.linspace(0.0, np.pi / 2, 9)[:-1]
    dome = np.column_stack([sr * np.cos(a), hh - 0.00005 + sh * np.sin(a)])
    screw = np.vstack([[[0.0, hh - 0.0001]], [[sr, hh - 0.0001]], dome, [[0.0, hh - 0.00005 + sh]]])
    slot = np.array([[0.0, -hm - g], [r + 2.0 * g, -hm - g], [r + 2.0 * g, hm + g], [0.0, hm + g]])
    return dict(top=knuckle(hm + g, hh), mid=knuckle(-hm + g, hm - g), bot=knuckle(-hh, -hm - g), screw=screw,
                slot=slot)


# ------------------------------------------------------------------------------------------ the parts' centrelines
def _bezier(P0, P1, P2, P3, n):
    t = np.linspace(0.0, 1.0, n)[:, None]
    return (1 - t) ** 3 * P0 + 3 * t * (1 - t) ** 2 * P1 + 3 * t * t * (1 - t) * P2 + t ** 3 * P3


def _resample(P, step):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(2, int(np.ceil(s[-1] / step)) + 1)
    st = np.linspace(0.0, s[-1], n)
    return np.column_stack([np.interp(st, s, P[:, k]) for k in range(3)]), st


def bridge_curve(spec=SPEC, step=0.00025):
    """the C-bridge's centreline from the RIGHT junction over the apex to the LEFT one (dense), each end buried 0.3 mm
    in its eyewire (a solder joint: the union's fillet forms the bead), and per node the frame normal n (the band's
    thickness direction, in the arch's plane) and its arc length from the apex (signed: + toward the left). The band's
    width runs along the arch plane's normal P (its broad top face up-forward)"""
    d = dims(spec)
    P = _arch_plane(spec)
    A, J = d['A'], d['J']
    # leaving the rim: radially out from the lens (its rim normal), made to lie in the arch's plane
    rad = np.array([np.cos(d['phi_j']), np.sin(d['phi_j']), 0.0])
    lv = _unit(rad - P * np.dot(rad, P))
    Jb = J - rad * 0.0003                                           # buried in the eyewire's outer face
    half = _bezier(A, A + np.array([0.0070, 0.0, 0.0]), J + lv * 0.0050, Jb, 400)
    half, s = _resample(half, step)
    pts = np.vstack([mirror(half[::-1], -1)[:-1], half])
    sgn = np.concatenate([-s[::-1][:-1], s])
    t = np.gradient(pts, axis=0)
    t = _unit(t)
    n = _unit(np.cross(P, t))
    return pts, n, sgn


def pad_frame(spec, side):
    """a pad arm's root on the rim's back (inner side, below the horizontal), the pad's centre (the cup's seat) and its
    face normal (toward the nose's flank), mirrored for the right"""
    d = dims(spec)
    ph = np.radians(spec['pad_phi'])
    root = d['C'] + (d['r_o'] - 0.00025) * np.array([np.cos(ph), np.sin(ph), 0.0]) + np.array([0, 0, -0.00035])
    pc = root + np.asarray(spec['pad_off'])
    nf = _unit(spec['pad_face'])
    return mirror(root, side), mirror(pc, side), mirror(nf, side)


def pad_arm_curve(spec, side, step=0.00025):
    """the pad arm: from its root on the rim back and down to the boss behind the cup (a cubic: leaving the rim
    back and down, arriving along the pad's axis; its tightest bend 0.55 mm, a wire bent round a pin: the handles
    2.8 / 2.2 mm long bent it at 0.33 mm, under the wire's own radius, a crease in the high and two kinks in the low)"""
    root, pc, nf = pad_frame(spec, 1)
    cb = spec['cup_back'] + 0.0007
    boss_end = pc - nf * cb
    P = _bezier(root, root + np.array([0.0, -0.0008, -0.0018]), boss_end - nf * 0.0012, boss_end + nf * 0.0002, 200)
    P, s = _resample(P, step)
    return mirror(P, side), s


def endpiece(spec, side):
    """the endpiece: the lug's straight centreline (from 0.3 mm inside the rim's outer face out to inside the barrel)
    and the hinge pin H (the barrel's axis at the middle knuckle's centre), mirrored"""
    d = dims(spec)
    E = d['E'].copy()
    E[2] = d['H'][2]
    a = E + np.array([-0.0003, 0.0, 0.0])
    b = np.array([d['H'][0] - 0.3 * spec['barrel_r'], E[1], d['H'][2]])
    return mirror(a, side), mirror(b, side), mirror(d['H'], side)


def temple_curve(spec, side, step=0.0003):
    """the temple's centreline from inside the middle knuckle: the strap back from the knuckle, the shaft (splayed
    outward) to the ear bend, then the riding-bow ear hook (a circular curl down and forward in a plane tilted in
    toward the head) and the ferrule at its end. Returns points, the arc length s, and the bend's s"""
    d = dims(spec)
    H, s0, Bd = d['H'], d['s0'], d['Bd']
    u = _unit(Bd - s0)
    start = H + np.array([0.3 * spec['barrel_r'], 0.0, -0.1 * spec['barrel_r']])
    strap = _bezier(start, start + np.array([0.0006, 0.0, -0.0006]), s0 - u * 0.0012, s0, 40)
    shaft = np.linspace(s0, Bd, 160)
    # the curl: down (-Y turned in by the tilt about the shaft) and forward again
    tl = np.radians(spec['hook_tilt'])
    side_in = _unit(np.cross(u, [0.0, 1.0, 0.0]))                  # -X-ish for the left: toward the head
    down = _unit(-np.array([0.0, 1.0, 0.0]) * np.cos(tl) + side_in * np.sin(tl))
    down = _unit(down - u * np.dot(down, u))
    a = np.radians(np.linspace(0.0, spec['hook_sweep'], 240))
    R = spec['hook_r']
    curl = Bd + R * (np.sin(a)[:, None] * u + (1.0 - np.cos(a))[:, None] * down)
    P = _chain([strap, shaft, curl])
    P, s = _resample(P, step)
    sb = float(np.linalg.norm(np.diff(_chain([strap, shaft]), axis=0), axis=1).sum())
    return mirror(P, side), s, sb


def temple_radius(spec, s, sb):
    """the temple's section along s: the strap (flat: its half-height; the width through the aspect), the shaft
    tapering, the crimp sleeve at the bend, the cable, the teardrop ferrule at the end. Returns (r0 along the frame
    normal (up), aspect (across / up), a4 squareness)"""
    s = np.asarray(s, np.float64)
    L = s[-1]
    sl, st = spec['strap_len'], spec['sleeve_len']
    r0 = np.full(len(s), 0.5 * spec['cable_d'])
    asp = np.ones(len(s))
    a4 = np.zeros(len(s))
    shaft = s <= sb
    f = np.clip((s - sl) / max(sb - sl, 1e-9), 0.0, 1.0)
    r_sh = 0.5 * (spec['temple_d'] + (spec['temple_d_end'] - spec['temple_d']) * f)
    w = _smoothstep(sl - 0.0015, sl + 0.0015, s)                   # the strap eases into the round shaft
    r0[shaft] = (0.5 * spec['strap_h'] * (1.0 - w) + r_sh * w)[shaft]
    asp[shaft] = ((spec['strap_w'] / spec['strap_h']) * (1.0 - w) + w)[shaft]
    a4[shaft] = (-0.10 * (1.0 - w))[shaft]
    # the sleeve: a short collar centred a little past the bend, its ends eased over 0.3 mm
    sv = _smoothstep(sb - 0.0003, sb + 0.0001, s) * (1.0 - _smoothstep(sb + st - 0.0001, sb + st + 0.0003, s))
    r0 = np.maximum(r0, sv * 0.5 * spec['sleeve_d'])
    # the ferrule: swelling over its length to the tip, rounded off (the sweep's end cap is its hemisphere)
    tl = spec['tip_len']
    g = np.clip((s - (L - tl)) / tl, 0.0, 1.0)
    tip = 0.5 * spec['cable_d'] + (0.5 * spec['tip_d'] - 0.5 * spec['cable_d']) * np.sin(np.pi * 0.5 * np.minimum(g / 0.75, 1.0))
    r0 = np.where(s > L - tl, np.maximum(r0, tip), r0)
    return r0, asp, a4


def temple_frames(P):
    """the temple's frame normals: up made perpendicular along the strap and shaft (so the strap stands on edge),
    carried round the curl by rotation-minimising frames"""
    from ..loft import rmf
    n, b, t = rmf(P, ref=np.array([0.0, 1.0, 0.0]))
    return n


# --------------------------------------------------------------------------------------------------- block-out
class _ProgField:
    """a Program as a field for voxel.trace_views (its one dummy voxel lies far away, so every sample is analytic)"""

    def __init__(self, prog, vs=0.0001):
        self.prog, self.vs = prog, vs
        self.origin = np.array([10.0, 10.0, 10.0])
        self.vol = wp.Volume.allocate_by_voxels(wp.array(np.zeros((1, 3), np.int32), dtype=wp.vec3i), voxel_size=vs,
                                                translation=(10.0, 10.0, 10.0))
        self.val = wp.array(np.ones(1, np.float32), dtype=wp.float32)
        self.ijk = wp.array(np.zeros((1, 3), np.int32), dtype=wp.vec3i)

    def _args(self):
        return [self.vol.id, self.val] + self.prog._args()


def build_sdf(spec=SPEC, lenses=False, sides=(1, -1)):
    """the block-out. The eyewires (REVOLVE) hard-unioned; the bridge band (SWEEP) blended onto them by 0.3 mm (the
    solder's bead); the endpieces' lugs blended onto the rims (0.25 mm) and the barrels' knuckles (REVOLVE, hard: their
    seams are carved); each temple one SWEEP from inside its middle knuckle (blended 0.15 mm) to the ferrule; the pad
    arms (SWEEP, 0.2 mm onto the rim and the boss), the cups and the ivory discs (REVOLVE). lenses: the glass too (the
    previews; the bake's field leaves it out: glass is not baked)"""
    d = dims(spec)
    prog = sdf.Program()
    rp = rim_profile(spec)
    for side in sides:
        prog.revolve(rp, mirror(d['C'], side), [0.0, 0.0, 1.0], name=f'eyewire {side:+d}')
    Pb, nb, _ = bridge_curve(spec)
    asp = spec['band_w'] / spec['band_t']
    prog.sweep(Pb, nb, 0.5 * spec['band_t'], aspect=asp, k=0.0003, name='bridge')
    disc, cup = pad_profiles(spec)
    bp = barrel_profiles(spec)
    for side in sides:
        a, b, H = endpiece(spec, side)
        L = np.linspace(a, b, 12)
        nl = np.tile([0.0, 1.0, 0.0], (len(L), 1))
        r0 = 0.5 * spec['lug_h'] / 0.88
        prog.sweep(L, nl, r0, a4=-0.12, aspect=spec['lug_d'] / spec['lug_h'], k=0.00025, name=f'lug {side:+d}')
        for nm in ('top', 'bot', 'screw'):
            prog.revolve(bp[nm], H, [0.0, 1.0, 0.0], k=0.0 if nm != 'screw' else 0.00005, name=f'{nm} {side:+d}')
        # the slot the temple's knuckle turns in (the endpiece cut back round it by the gap), then that knuckle
        prog.revolve(bp['slot'], H, [0.0, 1.0, 0.0], op=sdf.SUBTRACT, name=f'slot {side:+d}')
        prog.revolve(bp['mid'], H, [0.0, 1.0, 0.0], k=0.0, name=f'mid {side:+d}')
        Pt, st, sb = temple_curve(spec, side)
        r0, aspc, a4 = temple_radius(spec, st, sb)
        # (its fillet 0.08 mm: at 0.15 it reached across the 0.14 mm between the strap and the outer knuckles)
        prog.sweep(Pt, temple_frames(Pt), r0, a4=a4, aspect=aspc, k=0.00008, name=f'temple {side:+d}')
        Pa, sa = pad_arm_curve(spec, side)
        Na = temple_frames(Pa)
        prog.sweep(Pa, Na, 0.5 * spec['pad_arm_d'], k=0.0002, name=f'pad arm {side:+d}')
        root, pc, nf = pad_frame(spec, side)
        prog.revolve(cup, pc, nf, k=0.0, name=f'cup {side:+d}')
        prog.revolve(disc, pc, nf, k=0.0, name=f'pad {side:+d}')
    if lenses:
        lp = lens_profile(spec)
        for side in sides:
            prog.revolve(lp, mirror(d['C'], side), [0.0, 0.0, 1.0], name=f'lens {side:+d}')
    prog.glasses = dict(spec=spec, dims=d)
    return prog


def bounds(spec=SPEC, pad=0.003, half=False):
    """the voxel grid's box (half: the left half and the whole bridge, the bake's set)"""
    d = dims(spec)
    Pt, st, sb = temple_curve(spec, 1)
    lo = np.minimum(Pt.min(0), [-d['J'][0] - 0.002, d['C'][1] - d['r_o'] - 0.002, -0.002]) - pad
    hi = np.maximum(Pt.max(0), [d['H'][0] + spec['barrel_r'] + 0.001, 0.003, d['zl'] + 0.004]) + pad
    if not half:
        lo[0] = -hi[0]
    return lo, hi


# ----------------------------------------------------------------------------------------------------------- rig
def cable_s(spec=SPEC):
    """the ear hook's arc length from the bend to each cable joint: the first AT the bend (the cable's own joint: the
    hook joint only slides, so turning the cable never bends the shaft skinned to it), then thirds of the curl"""
    Lc = spec['hook_r'] * np.radians(spec['hook_sweep'])
    return Lc * np.arange(N_CABLE) / N_CABLE


def _jname(kind, sfx):
    return f'cable_{sfx}{kind[-1]}' if kind.startswith('cable') else f'{kind}_{sfx}'


def rest_joints(spec=SPEC):
    """the skeleton at rest (prop frame): name -> (parent, world 4x4). glasses_root at the contact (identity); each
    lens joint at its bridge junction (identity: the lens faces +Z); each pad joint at its arm's root on the rim
    (identity: an optician bends the arm there); each temple at its hinge pin, its local -Z along the shaft (hinge ->
    ear bend, so the shaft's length is the hook joint's distance) and its +Y up; the hook joint at the ear bend and the
    cable joints down the curl, all framed as the temple (a local rotation then turns the rest of the cable about
    that joint)"""
    d = dims(spec)
    out = {'glasses_root': (None, np.eye(4))}
    for side, sfx in ((1, 'L'), (-1, 'R')):
        W = np.eye(4)
        W[:3, 3] = mirror(d['J'], side)
        out[f'lens_{sfx}'] = ('glasses_root', W)
        H, Bd = mirror(d['H'], side), mirror(d['Bd'], side)
        z = _unit(H - Bd)                                          # local +Z points from the bend to the hinge
        y = _unit(np.array([0.0, 1.0, 0.0]) - z * z[1])
        x = np.cross(y, z)
        Wt = np.eye(4)
        Wt[:3, :3] = np.column_stack([x, y, z])
        Wt[:3, 3] = H
        out[f'temple_{sfx}'] = (f'lens_{sfx}', Wt)
        Wh = Wt.copy()
        Wh[:3, 3] = Bd
        out[f'hook_{sfx}'] = (f'temple_{sfx}', Wh)
        Pt, st, sb = temple_curve(spec, side)
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


def pad_axis(spec, side):
    """a pad arm's fold axis (the prop frame): the rim's tangent at the arm's root"""
    ph = np.radians(spec['pad_phi'])
    return mirror([-np.sin(ph), np.cos(ph), 0.0], side)


def _rotvec(v):
    """the rotation matrix of a rotation vector (axis x angle, radians)"""
    v = np.asarray(v, np.float64)
    a = float(np.linalg.norm(v))
    if a < 1e-12:
        return np.eye(3)
    k = v / a
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1.0 - np.cos(a)) * (K @ K)


def _vecrot(R):
    """the rotation vector of a rotation matrix"""
    c = np.clip(0.5 * (np.trace(R) - 1.0), -1.0, 1.0)
    a = float(np.arccos(c))
    if a < 1e-9:
        return np.zeros(3)
    w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    if np.pi - a < 1e-6:
        Bm = 0.5 * (R + np.eye(3))
        k = _unit(Bm[:, int(np.argmax(np.diag(Bm)))])
        return k * a
    return w / (2.0 * np.sin(a)) * a


def skeleton(spec=SPEC):
    """the rest skeleton in JOINTS order (the skin's joint list IS the weights' index space: built in rest_joints'
    order, the glb's JOINTS_0 pointed at the wrong joints and t25's skin check posed the glasses 44.9 mm into the
    head; every parent precedes its children in JOINTS)"""
    from ..rig import Skeleton
    sk = Skeleton()
    rj = rest_joints(spec)
    for nm in JOINTS:
        par, W = rj[nm]
        sk.add(nm, par, W[:3, 3], W[:3, :3])
    return sk


def _rot_between(a, b):
    """the minimal rotation taking unit a onto unit b (Rodrigues)"""
    a, b = _unit(a), _unit(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -1.0 + 1e-9:
        p = _unit(np.cross(a, [1.0, 0.0, 0.0] if abs(a[0]) < 0.9 else [0.0, 1.0, 0.0]))
        return 2.0 * np.outer(p, p) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1.0 + c)


def fit_pose(fit, seat, up=None, clearance=0.0004, gap=0.0003, adjust=None):
    """the glasses posed on a seat (the RUNTIME's math, accessories.js wear() for archetype 'glasses', mirrored here
    for the forge's fit looks and checks). fit: fit_data(); seat: seat_glasses' fit (its frame: +Z the bridge's skin
    normal, +Y the creature's up made perpendicular; eyes [left, right]: centre, radius, axis, hook, optional exit and
    hook_normal), up: the creature's up in the seat frame (default: the seat's +Y). Returns the root's (position,
    scale) in the seat frame and per joint its posed LOCAL (rotation 3x3, translation) and its posed world 4x4 (seat
    frame, the root's scale applied).
      * the root: at the seat's origin, `clearance` out along +Z (a low's facets lie inside the true surface), scaled
        so each lens's aperture radius is FIT_EYE x its eye's radius;
      * each lens: its centre on its eye's axis, the seat's standoff past the eye's front (the axis's skin exit when
        the seat carries it, else the eyeball's front: centre + radius), facing along the axis, rolled so its endpiece
        points at the eye's hook (in the lens plane): the temple then leaves toward the hook as on a face;
      * each temple: hinged where its lens put it, aimed at the hook pushed `gap` + the cable's radius off the skin
        (along the hook's skin normal when the seat carries one, else the seat's lateral); its hook joint slides along
        the temple's axis to the hook (the shaft between them is skinned to both, so it shortens) and rolls about that
        axis so the ear hook hangs along the skin (down the skin's tangent: the hook normal's, else the creature's
        up's)"""
    eyes = seat['eyes']
    adj = adjust if adjust is not None else (seat.get('validated') or {}).get(fit['prop'], {})
    rad = np.mean([e['radius'] for e in eyes])
    s = FIT_EYE * rad / fit['lens']['radius']
    up = _unit(up if up is not None else [0.0, 1.0, 0.0])
    root = np.array([0.0, 0.0, clearance])
    so = seat.get('standoff', 0.003) + float(adj.get('standoff', 0.0))
    local = {'glasses_root': (np.eye(3), root.copy())}
    world = {}
    Wr = np.eye(4)
    Wr[:3, :3] = np.eye(3) * s
    Wr[:3, 3] = root
    world['glasses_root'] = Wr
    to_root = lambda p: (np.asarray(p, np.float64) - root) / s     # seat frame -> the root's (prop) space
    for k, (e, sfx, side) in enumerate(zip(eyes, ('L', 'R'), (1, -1))):
        F = fit['sides'][sfx]
        a = _unit(e['axis'])
        c = np.asarray(e['centre'], np.float64)
        front = float(np.dot(np.asarray(e['exit']) - c, a)) if e.get('exit') is not None else float(e['radius'])
        P = to_root(c + a * (max(front, float(e['radius'])) + so))
        hook = to_root(e['hook'])
        hd = (hook - P) - a * np.dot(hook - P, a)
        hd = _unit(hd) if np.linalg.norm(hd) > 1e-9 else _unit(np.cross(up, a)) * side
        e0 = _unit(F['end_dir'])
        B_rest = np.column_stack([e0, np.cross([0.0, 0.0, 1.0], e0), [0.0, 0.0, 1.0]])
        B_pose = np.column_stack([hd, np.cross(a, hd), a])
        Rl = B_pose @ B_rest.T
        Lj = P - Rl @ (np.asarray(F['lens_centre']) - np.asarray(F['junction']))
        local[f'lens_{sfx}'] = (Rl, Lj)
        # the pad arm, bent at its root by the validated rotation (a rotation vector in the lens's frame, radians)
        pv = (adj.get('pad') or [[0.0, 0.0, 0.0]] * 2)[k]
        local[f'pad_{sfx}'] = (_rotvec(pv), np.asarray(F['pad_root']) - np.asarray(F['junction']))
        # the temple rides the lens to its hinge, then is aimed and rolled
        Rt0 = np.asarray(F['temple_rot'])
        Hp = Lj + Rl @ (np.asarray(F['hinge']) - np.asarray(F['junction']))
        nh = np.asarray(e['hook_normal'], np.float64) if e.get('hook_normal') is not None else \
            np.array([float(side), 0.0, 0.0])
        T = hook + nh * (gap + 0.5 * fit['cable_d'] + float((adj.get('lift') or [0.0, 0.0])[k])) / s
        if (adj.get('target') or [None, None])[k] is not None:          # a validated aim point (the seat frame)
            T = to_root(adj['target'][k])
        dt = _unit(T - Hp)
        cur = Rl @ Rt0
        Rt = _rot_between(-cur[:, 2], dt) @ cur
        # the roll: the ear hook's curl leaves along the temple's local -Y; turn it about the aim onto the skin's
        # downward tangent at the hook. The HOOK joint carries it (a turn about the aim = about the hook joint's own
        # -Z, which lies on it: the hook and the cable land exactly where a rolled temple put them), not the temple:
        # rolled at the hinge, the temple's knuckle stood 26 deg out of the barrel on the v4 octopus (review_fit.py);
        # the shaft between the two joints is round, so the twist its skin blend takes does not show
        roll = 0.0
        g = -up + nh * np.dot(nh, up) if e.get('hook_normal') is not None else -up
        g = g - dt * np.dot(g, dt)
        if np.linalg.norm(g) > 1e-6:
            g = _unit(g)
            cd = -Rt[:, 1]
            cd = _unit(cd - dt * np.dot(cd, dt))
            roll = float(np.arctan2(np.dot(np.cross(cd, g), dt), np.dot(cd, g)))
        roll += np.radians(float((adj.get('roll') or [0.0, 0.0])[k]))   # a validated extra roll (degrees)
        local[f'temple_{sfx}'] = (Rl.T @ Rt, np.asarray(F['hinge']) - np.asarray(F['junction']))
        Lh = float(np.linalg.norm(T - Hp))
        # the ear hook's cable: the hook joint slides to the aim point and takes the roll (a turn of -roll about its
        # local Z: Rot(dt, roll) Rt = Rt Rz(-roll), dt being the temple's -Z); it and the cable joints take the
        # validated local rotations (the cable draped on the skin: validate_fit), else the rest curl
        cab = (adj.get('cable') or {}).get(sfx) or [[0.0, 0.0, 0.0]] * N_CABLE
        c_, s_ = np.cos(-roll), np.sin(-roll)
        local[f'hook_{sfx}'] = (np.array([[c_, -s_, 0.0], [s_, c_, 0.0], [0.0, 0.0, 1.0]]), np.array([0.0, 0.0, -Lh]))
        for i in range(N_CABLE):
            local[f'cable_{sfx}{i + 1}'] = (_rotvec(cab[i]), np.asarray(F['cable_local'][i]))
    # world matrices (seat frame) down the chain
    for nm in JOINTS[1:]:
        kind = nm.split('_')[0] if not nm.startswith('cable') else f'cable{nm[-1]}'
        sfx = nm[6] if nm.startswith('cable') else nm[-1]
        par = PARENT[kind]
        par = par if par == 'glasses_root' else _jname(par, sfx)
        Rm, t = local[nm]
        Lm = np.eye(4)
        Lm[:3, :3] = Rm
        Lm[:3, 3] = t
        world[nm] = world[par] @ Lm
    return dict(root=root, scale=s, local=local, world=world)


def posed_vertices(spec, L, pose):
    """the low (low_arrays) skinned by a fit pose: positions in the seat frame"""
    from ..rig import lbs
    return lbs(L['V'], L['joints'].astype(np.int64), L['weights'].astype(np.float64), skin_matrices(spec, pose))


def validate_fit(prog, R_g, B, seat, up_seat, L, spec=SPEC, target=0.0003, log=print):
    """the glasses CHECKED on a creature (the forge's twin of fit.fit_hat): fit_pose on the seat, then what the seat
    alone cannot tell the runtime, measured against the creature's block-out SDF (prog, world; the seat frame maps to
    world by R_g, B) and returned as the seat's validated entry for this prop (seat_glasses.fit.validated[
    'round_glasses'], which fit_pose and the runtime read):
      * target / roll: each temple's aim point pushed `target` + the cable's radius off the skin along the hook's TRUE
        skin normal, and the roll that hangs the ear hook down the skin's tangent there, expressed over the runtime's
        own fallback (the seat's lateral, the creature's up);
      * pad: each pad arm bent at its root (the smallest angle that clears the skin by `target`: the v4 octopus's
        turrets stand where a nose's flanks would be, 8.6 mm behind the lens);
      * cable: the ear hook DRAPED: down the chain (the hook joint, then each cable joint) the deepest point of the
        cable beyond each joint is turned out to `target` off the skin about that joint, a few passes (a cable temple
        conforms to its wearer; a rigid 15 mm curl went 16-23 mm into the octopus's head at every roll).
    Returns (validated dict, the final pose, per-region minimum skin distance in metres)"""
    fit = fit_data(spec)
    to_w = lambda P: np.asarray(P) @ R_g.T + B
    seat_n = {k: v for k, v in seat.items() if k != 'validated'}
    eyes = [dict(e) for e in seat_n['eyes']]
    for e in eyes:
        hw = to_w(np.asarray(e['hook'])[None])[0]
        e['hook_normal'] = (R_g.T @ prog.normals(hw[None])[0]).tolist()
    seat_t = dict(seat_n, eyes=eyes)
    adj = dict(pad=[[0.0] * 3, [0.0] * 3], roll=[0.0, 0.0], target=[None, None],
               cable={'L': [[0.0] * 3 for _ in range(N_CABLE)], 'R': [[0.0] * 3 for _ in range(N_CABLE)]})
    # the temples: the true pose with the hook normal, then the same as an aim point and a roll over the fallback
    p_true = fit_pose(fit, seat_t, up=up_seat, gap=target, adjust=adj)
    for k, sfx in enumerate('LR'):
        Wh = p_true['world'][f'hook_{sfx}']
        adj['target'][k] = Wh[:3, 3].round(6).tolist()
    p_base = fit_pose(fit, seat_n, up=up_seat, gap=target, adjust=adj)
    for k, sfx in enumerate('LR'):
        Rt_t = p_true['world'][f'hook_{sfx}'][:3, :3]                 # (the hook joint carries the roll)
        Rt_b = p_base['world'][f'hook_{sfx}'][:3, :3]
        dt = _unit(-Rt_t[:, 2])
        a_, b_ = _unit(-Rt_b[:, 1]), _unit(-Rt_t[:, 1])
        adj['roll'][k] = round(float(np.degrees(np.arctan2(np.dot(np.cross(a_, b_), dt), np.dot(a_, b_)))), 3)
    reg_v = np.full(len(L['V']), -1)
    for r in range(len(REGIONS)):
        reg_v[np.unique(L['F'][L['region'] == r])] = r
    jn = {nm: JOINTS.index(nm) for nm in JOINTS}
    dom = L['joints'][np.arange(len(L['V'])), np.argmax(L['weights'], axis=1)]

    def dist_of(a):
        P = posed_vertices(spec, L, fit_pose(fit, seat_n, up=up_seat, gap=target, adjust=a))
        return prog.eval(to_w(P)).astype(np.float64), P
    # the pads: the smallest bend (about the rim's tangent or its radius at the arm's root, at most 45 deg) that clears
    # the skin and keeps the pad behind the rims' plane (in front of the glass it would read as a stray disc)
    d = dims(spec)
    for k, (sfx, side) in enumerate(zip('LR', (1, -1))):
        sel = dom == jn[f'pad_{sfx}']
        ph = np.radians(spec['pad_phi'])
        axes = [mirror([-np.sin(ph), np.cos(ph), 0.0], side), mirror([np.cos(ph), np.sin(ph), 0.0], side)]
        Vr = L['V'][sel]                                           # the pad's rest points (prop frame)
        root = np.asarray(fit['sides'][sfx]['pad_root'])
        C = mirror(d['C'], side)
        best = ([0.0, 0.0, 0.0], -np.inf)
        for al in sorted(np.arange(-45.0, 46.0, 5.0), key=abs):
            for ax in (axes[:1] if al == 0.0 else axes):
                rv = (np.asarray(ax) * np.radians(al)).tolist()
                Pr = (Vr - root) @ _rotvec(rv).T + root
                over = np.hypot(Pr[:, 0] - C[0], Pr[:, 1] - C[1]) < d['r_o']
                if over.any() and Pr[over, 2].max() > d['zl'] - 0.0003:
                    continue                                       # it would stand over the glass's face
                adj['pad'][k] = rv
                dmin = float(dist_of(adj)[0][sel].min())
                if dmin > best[1]:
                    best = (rv, dmin)
                if dmin >= target:
                    break
            if best[1] >= target:
                break
        adj['pad'][k] = [round(x, 6) for x in best[0]]
    # the cable: drape down the chain. Segment i is the cable between joint i and joint i + 1 by arc length past the
    # bend (the last runs to the ferrule); its deepest point is turned out about joint i, at most 20 deg a step (a
    # point next to its joint would ask for a huge turn: the next pass's parent turn serves it better)
    Pt_, st_, sb_ = temple_curve(spec, 1)
    sc = np.concatenate([cable_s(spec), [np.inf]])
    s_c = L['ATTR'][:, 0] - sb_
    hug = target + 0.0004                                          # a segment's end floating past this is drawn in
    for k, sfx in enumerate('LR'):
        chain = [f'cable_{sfx}{i + 1}' for i in range(N_CABLE)]
        mine = (reg_v == 5) & np.isin(dom, [jn[c] for c in chain + [f'hook_{sfx}']])
        for it in range(24):
            moved = False
            for i, cn in enumerate(chain):
                dist, P = dist_of(adj)
                cand = mine & (s_c >= sc[i] + 0.0015) & (s_c < sc[i + 1] + 0.0015)
                if not cand.any():
                    continue
                j = np.nonzero(cand)[0][np.argmin(dist[cand])]
                if dist[j] >= target:
                    # clear: draw the segment's end ring in to the skin if it floats (the cable HUGS its wearer: pushed
                    # out only, the curl stood off the octopus's head as a loop 15 mm wide); the last passes only push
                    if it >= 18:
                        continue
                    ring = cand & (s_c >= s_c[cand].max() - 0.0004)
                    j = np.nonzero(ring)[0][np.argmin(dist[ring])]
                    if dist[j] <= hug:
                        continue
                    want = target + 0.00015 - dist[j]
                else:
                    want = target - dist[j] + 0.0001
                pose = fit_pose(fit, seat_n, up=up_seat, gap=target, adjust=adj)
                pj = pose['world'][cn][:3, 3]
                n = R_g.T @ prog.normals(to_w(P[j][None]))[0]
                v = P[j] - pj
                if np.linalg.norm(v) < 0.002:
                    continue
                dw = _rot_between(v, v + n * want)
                ang = np.arccos(np.clip(0.5 * (np.trace(dw) - 1.0), -1.0, 1.0))
                if ang > np.radians(20.0):
                    dw = _rotvec(_vecrot(dw) * (np.radians(20.0) / ang))
                par = pose['world'][f'hook_{sfx}' if i == 0 else chain[i - 1]][:3, :3]
                Rp = par / np.linalg.norm(par[:, 0])
                Lc = _rotvec(adj['cable'][sfx][i])
                adj['cable'][sfx][i] = _vecrot((Rp.T @ dw @ Rp) @ Lc).round(6).tolist()
                moved = True
            if not moved:
                break
    dist, P = dist_of(adj)
    per = {REGIONS[r]: float(dist[reg_v == r].min()) for r in range(len(REGIONS)) if (reg_v == r).any()}
    adj['clearance_min'] = round(float(dist.min()), 6)
    adj['ok'] = bool(dist.min() >= 0.0)
    log('[round_glasses] validate_fit: pads bent ' + ', '.join(f'{np.degrees(np.linalg.norm(a)):.0f}'
                                                               for a in adj['pad']) + ' deg; temple rolls '
        + ', '.join(f'{r:+.1f}' for r in adj['roll']) + ' deg over the fallback; cable draped; skin distance min '
        + ', '.join(f'{k} {v * 1000:+.2f}' for k, v in per.items()) + ' mm')
    return adj, fit_pose(fit, seat_n, up=up_seat, gap=target, adjust=adj), per


def skin_matrices(spec, pose):
    """per joint (JOINTS order) the skinning matrix posed world x rest world^-1 (seat frame)"""
    rj = rest_joints(spec)
    return np.stack([pose['world'][nm] @ np.linalg.inv(rj[nm][1]) for nm in JOINTS])


# ----------------------------------------------------------------------------------------------------------- low
# A PIECE is one closed-or-buried part of the low: welded vertices V, quads Q (outward), per quad its region, per
# vertex ATTR (s along the part (m), cos and sin of the angle round its section, a part parameter) and its joint
# weights W (n, len(JOINTS)); and its UV ISLANDS: split vertices (each a welded id) with analytic UVs in metres and
# the island's texel share
def _piece(V, Q, region, attr, W, islands, bake=True):
    return dict(V=np.asarray(V, np.float64), Q=np.asarray(Q, np.int64), region=np.broadcast_to(
        np.asarray(region, np.int64), (len(Q),)).copy(), attr=np.asarray(attr, np.float64),
        W=np.asarray(W, np.float64), islands=islands, bake=bake)


def _weights(n, spec_w):
    """dense weights (n, len(JOINTS)) from {joint: per-vertex weight}"""
    W = np.zeros((n, len(JOINTS)))
    for nm, w in spec_w.items():
        W[:, JOINTS.index(nm)] += np.broadcast_to(np.asarray(w, np.float64), (n,))
    return W


def ring_tube(P, N, sect, K, s=None, theta0=0.0, region=0, cut_len=0.045, part=0.0):
    """a wire's low: K vertices round each station i at P_i + sect_i(theta) (cos theta n_i + sin theta b_i), b = t x n;
    sect(i, theta) -> radius. Quads wound outward. Its UV islands unroll it: u the arc length along the wire, v the
    perimeter round the section (the seam column duplicated at theta0 + 2 pi), cut into islands of at most cut_len
    (long strips do not pack). ATTR = (s, cos theta, sin theta, part)"""
    P = np.asarray(P, np.float64)
    Nn = len(P)
    t = _unit(np.gradient(P, axis=0))
    n = _unit(np.asarray(N, np.float64) - t * (np.asarray(N) * t).sum(1, keepdims=True))
    b = np.cross(t, n)
    th = theta0 + 2.0 * np.pi * np.arange(K + 1) / K
    R = np.array([[sect(i, th[k]) for k in range(K + 1)] for i in range(Nn)])
    Vs = P[:, None, :] + R[..., None] * (np.cos(th)[None, :, None] * n[:, None, :] + np.sin(th)[None, :, None]
                                          * b[:, None, :])
    if s is None:
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    V = Vs[:, :K].reshape(-1, 3)
    ids = np.arange(Nn * K).reshape(Nn, K)
    i = np.arange(Nn - 1)[:, None]
    k = np.arange(K)[None, :]
    Q = np.stack([ids[i, k], ids[i + 1, k], ids[i + 1, (k + 1) % K], ids[i, (k + 1) % K]], -1).reshape(-1, 4)
    c = Vs[:-1, :K].mean(1)
    fn = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    out = (V[Q].mean(1) - np.repeat(c, K, axis=0))
    flip = (fn * out).sum() < 0.0
    if flip:
        Q = Q[:, ::-1].copy()
    attr = np.column_stack([np.repeat(s, K), np.tile(np.cos(th[:K]), Nn), np.tile(np.sin(th[:K]), Nn),
                            np.full(Nn * K, part)])
    # the islands: perimeter coordinate per station (the polygon's own edge lengths), u = s
    per = np.concatenate([np.zeros((Nn, 1)), np.cumsum(np.linalg.norm(np.diff(Vs, axis=1), axis=2), axis=1)], 1)
    islands = []
    edges = [0]
    while edges[-1] < Nn - 1:
        j = edges[-1] + 1
        while j < Nn - 1 and s[j + 1] - s[edges[-1]] <= cut_len:
            j += 1
        edges.append(j)
    for a, z in zip(edges[:-1], edges[1:]):
        rows = np.arange(a, z + 1)
        sid = np.arange(len(rows) * (K + 1)).reshape(len(rows), K + 1)
        orig = ids[rows][:, np.r_[np.arange(K), 0]]
        UV = np.stack([np.repeat(s[rows][:, None], K + 1, 1), per[rows]], -1).reshape(-1, 2)
        ii = np.arange(len(rows) - 1)[:, None]
        kk = np.arange(K)[None, :]
        Qs = np.stack([sid[ii, kk], sid[ii + 1, kk], sid[ii + 1, kk + 1], sid[ii, kk + 1]], -1).reshape(-1, 4)
        if flip:
            Qs = Qs[:, ::-1].copy()
        quads = ((rows[:-1] - 0)[:, None] * K + np.arange(K)[None, :]).ravel()
        islands.append(dict(Q=Qs, orig=orig.ravel(), UV=UV, quads=quads, share=1.0))
    return V, Q, attr, islands


def revolve_piece(prof, c, axis, K, e1=None, region_of=None, cap0=False, cap1=False, phi0=0.0, part=0.0,
                  cuts=None, share=1.0):
    """a revolve's low: the profile's points (rho, zeta) swept round `axis` through c at K azimuths (closed), quads
    wound outward (the profile runs counter-clockwise in (rho, zeta)); cap0 / cap1 close the first / last ring with a
    quad grid (K = 4 s) whose inner points lie on the plane of that ring. UV islands: the band unrolled (u round the
    azimuth at the profile's mean radius, v along the profile), cut at the azimuth indices `cuts`; caps projected flat.
    region_of(j): the region of the band between profile points j and j + 1. ATTR = (arc along the band, cos phi,
    sin phi, part)"""
    from .. import loft
    prof = np.asarray(prof, np.float64)
    a = _unit(axis)
    if e1 is None:
        e1 = _unit(np.cross(a, [0.0, 0.0, 1.0] if abs(a[2]) < 0.9 else [1.0, 0.0, 0.0]))
    e1 = _unit(e1 - a * np.dot(e1, a))
    e2 = np.cross(a, e1)
    ph = phi0 + 2.0 * np.pi * np.arange(K) / K
    m = len(prof)
    Vg = c[None, None, :] + prof[None, :, 0, None] * (np.cos(ph)[:, None, None] * e1 + np.sin(ph)[:, None, None]
                                                       * e2) + prof[None, :, 1, None] * a
    V = Vg.reshape(-1, 3)
    ids = np.arange(K * m).reshape(K, m)
    i = np.arange(K)[:, None]
    j = np.arange(m - 1)[None, :]
    Q = np.stack([ids[i, j], ids[(i + 1) % K, j], ids[(i + 1) % K, j + 1], ids[i, j + 1]], -1).reshape(-1, 4)
    reg = np.array([region_of(int(jj)) if region_of else 0 for _ in range(K) for jj in range(m - 1)])
    sp = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(prof, axis=0), axis=1))])
    attr = np.column_stack([np.tile(sp, K), np.repeat(np.cos(ph), m), np.repeat(np.sin(ph), m), np.full(K * m, part)])
    mesh = QuadMesh(V, Q, {'attr': attr})
    # outward: a counter-clockwise profile's right-hand normal (d zeta, -d rho) points out of the solid; the band's
    # first column of quads (at phi0) must agree with it
    fn = mesh.face_normals()
    q0 = np.arange(m - 1)
    d = prof[1:] - prof[:-1]
    pn = np.column_stack([d[:, 1], -d[:, 0]])
    wn = pn[:, 0, None] * (np.cos(ph[0]) * e1 + np.sin(ph[0]) * e2) + pn[:, 1, None] * a
    flipped = bool((fn[q0] * wn).sum() < 0.0)
    if flipped:
        Q = Q[:, ::-1].copy()
        mesh = QuadMesh(V, Q, {'attr': attr})
    caps = []
    for end, on in ((0, cap0), (m - 1, cap1)):
        if not on:
            continue
        ring = ids[:, end]
        ax = -a if end == 0 else a
        if prof[end, 0] < 1e-9:
            raise ValueError('revolve_piece: cap a ring off the axis, not a point')
        mesh, G = loft.cap(mesh, ring, ax)
        caps.append((end, G))
    Q = mesh.Q
    reg = np.concatenate([reg, np.concatenate([np.full((G.shape[0] - 1) * (G.shape[1] - 1),
                                                       region_of(max(end - 1, 0)) if region_of else 0)
                                               for end, G in caps]) if caps else np.zeros(0, np.int64)])
    V = mesh.V
    attr = mesh.attrs['attr']
    # islands: the band per azimuth arc (cuts), each row at its own radius (u = (phi - the arc's middle) rho_j: a
    # disc-like band unrolls as a fan of true arc lengths, not sheared), v along the profile; then each cap flat
    cuts = sorted(set([0] + list(cuts or []) + [K]))
    islands = []
    for a0, a1 in zip(cuts[:-1], cuts[1:]):
        cols = np.arange(a0, a1 + 1)
        sid = np.arange(len(cols) * m).reshape(len(cols), m)
        orig = ids[cols % K]
        dphi = 2.0 * np.pi * (cols - 0.5 * (a0 + a1)) / K
        UV = np.stack([dphi[:, None] * np.maximum(prof[None, :, 0], 0.15 * prof[:, 0].max()),
                       np.tile(sp, (len(cols), 1))], -1).reshape(-1, 2)
        ii = np.arange(len(cols) - 1)[:, None]
        jj = np.arange(m - 1)[None, :]
        Qs = np.stack([sid[ii, jj], sid[ii + 1, jj], sid[ii + 1, jj + 1], sid[ii, jj + 1]], -1).reshape(-1, 4)
        if flipped:
            Qs = Qs[:, ::-1].copy()
        quads = (cols[:-1, None] * (m - 1) + np.arange(m - 1)[None, :]).ravel()
        islands.append(dict(Q=Qs, orig=orig.ravel(), UV=UV, quads=quads, share=share))
    q_off = K * (m - 1)
    for end, G in caps:
        vs = np.unique(G)
        loc = -np.ones(len(V), np.int64)
        loc[vs] = np.arange(len(vs))
        nq = (G.shape[0] - 1) * (G.shape[1] - 1)
        Qc = Q[q_off:q_off + nq]
        UV = np.column_stack([(V[vs] - c) @ e1, (V[vs] - c) @ e2])
        if end == 0:
            UV[:, 0] = -UV[:, 0]
        islands.append(dict(Q=loc[Qc], orig=vs, UV=UV, quads=np.arange(q_off, q_off + nq), share=share))
        q_off += nq
    return V, Q, reg, attr, islands


def build_low(spec=SPEC, log=print):
    """the designed low: the LEFT half's pieces (eyewire, lens, endpiece lug and barrel, temple, pad and pad arm),
    the bridge, then the left half mirrored to the right (its UVs STACKED on the left's: the right pieces' islands
    reuse the left's UVs, so bake and paint run on the left half and the bridge only; the right lens alone has its
    own, painted). Returns a dict: V, Q (welded),
    region per quad, ATTR, W (joint weights), the split mesh (Vs index -> welded orig, UV in metres, the island id per
    split quad, share per island), bake (per quad: in the bake and paint set), side per quad"""
    d = dims(spec)
    pieces = []
    # ---- the eyewire: the D section sampled at its corners (8 points), 56 stations round the lens; the seam column
    # in the groove (behind the glass), the ring cut into arcs under the lug, the bridge's foot and the pad arm's root
    rp = rim_profile(spec)
    r_a, r_o, h = d['r_a'], d['r_o'], 0.5 * spec['rim_depth']
    rc, rl = spec['rim_round'], spec['lip_round']
    c45 = np.cos(np.pi / 4)
    sect = np.array([[r_a, 0.0], [r_a, h - rl], [r_a + rl - rl * c45, h - rl + rl * c45], [r_o - rc, h],
                     [r_o - rc + rc * c45, h - rc + rc * c45], [r_o + spec['rim_bulge'], 0.0],
                     [r_o - rc + rc * c45, -(h - rc + rc * c45)], [r_o - rc, -h],
                     [r_a + rl - rl * c45, -(h - rl + rl * c45)], [r_a, -(h - rl)]])
    sect = np.vstack([sect, sect[:1]])                               # closed: the groove's middle twice
    Kr = 48                                                          # 7.5 deg a station: 0.04 mm off the true ring
    cut_phi = [spec['end_phi'], 180.0 - spec['bridge_phi'], spec['pad_phi']]
    cuts = sorted(int(round(((p - spec['end_phi']) % 360.0) / 360.0 * Kr)) for p in cut_phi)
    V, Q, reg, attr, isl = revolve_piece(sect[::-1], d['C'], [0.0, 0.0, 1.0], Kr, e1=[1.0, 0.0, 0.0],
                                         phi0=np.radians(spec['end_phi']), cuts=cuts,
                                         region_of=lambda j: 0, part=0.0)
    pieces.append(('eyewire', _piece(V, Q, 0, attr, _weights(len(V), {'lens_L': 1.0}), isl)))
    # ---- the lens: the front and back faces' boundary rings at the bevel's start, the apex between; grid caps
    g = lens_geom(spec)
    lp = np.array([[g['rho_b'], lens_back(spec, g['rho_b'])], [g['rho_e'], 0.0], [g['rho_b'],
                                                                                   lens_front(spec, g['rho_b'])]])
    # (the edge band in four arcs: whole, at the lens's density it ran 1060 texels long, past the sheet)
    V, Q, reg, attr, isl = revolve_piece(lp, d['C'], [0.0, 0.0, 1.0], 24, e1=[1.0, 0.0, 0.0], cap0=True, cap1=True,
                                         region_of=lambda j: 9, part=9.0, share=LENS_SHARE, cuts=[6, 12, 18])
    isl[4]['share'] = LENS_BACK_SHARE                              # the inner face's cap (cap0: lp starts at the back)
    # the caps' inner points onto the faces' spheres (loft.cap leaves them on the rings' planes)
    rr = np.hypot(V[:, 0] - d['C'][0], V[:, 1] - d['C'][1])
    fr = V[:, 2] - d['C'][2] > 0.0
    inner = rr < g['rho_b'] - 1e-7
    V[inner & fr, 2] = d['C'][2] + lens_front(spec, rr[inner & fr])
    V[inner & ~fr, 2] = d['C'][2] + lens_back(spec, rr[inner & ~fr])
    pieces.append(('lens', _piece(V, Q, reg, attr, _weights(len(V), {'lens_L': 1.0}), isl)))
    # ---- the endpiece: the lug (8 round a squarish section) and the barrel (below); the lug's low ends
    # 0.1 mm inside the barrel (run to the SDF lug's buried end, 1 mm in, its hidden faces failed the bake gate: 3.4 %
    # of its island found no surface)
    a, b, H = endpiece(spec, 1)
    b = np.array([H[0] - spec['barrel_r'] + 0.0001, b[1], b[2]])
    L = np.linspace(a, b, 3)
    r0 = 0.5 * spec['lug_h'] / 0.88
    asp = spec['lug_d'] / spec['lug_h']

    def lug_sect(i, th, r0=r0, asp=asp):
        r = r0 * (1.0 - 0.12 * np.cos(4.0 * th))
        return r * asp / np.sqrt(asp * asp * np.cos(th) ** 2 + np.sin(th) ** 2)
    V, Q, attr, isl = ring_tube(L, np.tile([0.0, 1.0, 0.0], (3, 1)), lug_sect, 8, theta0=np.pi / 8, part=2.0)
    pieces.append(('lug', _piece(V, Q, 2, attr, _weights(len(V), {'lens_L': 1.0}), isl)))
    # the barrel: ONE low over the three knuckles, all on the lens joint (a knuckle turns about its own pin, so it
    # never needs the temple's: riding the temple joint, the middle knuckle stood out of the barrel wherever the fit
    # turned the temple off its pin, review_fit.py), 24 round, the seams baked from the high's hairline gaps; the
    # screw's pan head is the top CAP, its 6 x 6 grid lifted onto the head's quarter ellipse (barrel_profiles): one
    # flat island with the slot straight across it (as rings of the band, the head's UVs fanned to a seam through its
    # centre and the slot baked as a smear, t25); 384 triangles a side where three 16-round pieces took 512
    hh, rb, cham = 0.5 * spec['barrel_h'], spec['barrel_r'], spec['knuckle_cham']
    sr, sh = spec['screw_r'], spec['screw_h']
    prof = np.array([[rb * 0.55, -hh], [rb - cham, -hh], [rb, -hh + cham], [rb, hh - cham], [rb - cham, hh], [sr, hh]])
    V, Q, reg, attr, isl = revolve_piece(prof, H, [0.0, 1.0, 0.0], 24, e1=[0.0, 0.0, -1.0], cap0=True, cap1=True,
                                         region_of=lambda j: 3, part=3.0)
    rr = np.hypot(V[:, 0] - H[0], V[:, 2] - H[2])
    head = (V[:, 1] > H[1] + hh - 1e-7) & (rr < sr - 1e-7)
    V[head, 1] = H[1] + np.maximum(hh, hh - 0.00005 + sh * np.sqrt(np.clip(1.0 - (rr[head] / sr) ** 2, 0.0, 1.0)))
    pieces.append(('barrel', _piece(V, Q, reg, attr, _weights(len(V), {'lens_L': 1.0}), isl)))
    # ---- the temple: 8 round, the stations dense where the section or the path turns (the strap's ease, the
    # sleeve, the curl, the ferrule), sparse along the straight shaft; its start buried in the middle knuckle, its end
    # capped. Weights: the temple joint to the strap's end, then a linear ramp to the hook joint at the ear bend (the
    # shaft shortens uniformly when the hook joint slides), the hook joint beyond
    Pt, st, sb = temple_curve(spec, 1)
    r0t, aspt, a4t = temple_radius(spec, st, sb)
    i0 = int(np.searchsorted(st, 0.0009))                          # the strap's buried start: 0.3-0.5 mm inside the
    keep = [i0]                                                    # knuckle (deeper, the bake missed 1.2 % of its island)
    for i in range(i0 + 1, len(st) - 1):
        dr = abs(r0t[i] - r0t[keep[-1]]) > 0.00004
        turn = np.degrees(np.arccos(np.clip(np.dot(_unit(Pt[i] - Pt[keep[-1]]), _unit(Pt[i + 1] - Pt[i])), -1, 1)))
        far = st[i] - st[keep[-1]] > (0.016 if spec['strap_len'] + 0.002 < st[i] < sb - 0.002 else 0.0026)
        if dr or turn > 10.0 or far:
            keep.append(i)
    keep.append(len(st) - 1)
    keep = np.array(sorted(set(keep)))
    Pk, sk = Pt[keep], st[keep]
    Nk = temple_frames(Pt)[keep]
    # the ferrule's end domes as the high's does (the sweep's end is a hemisphere of its end radius): two rings on it
    # before the cap's apex (a flat cap lay 0.3 mm inside the high, read as buried, was never baked and rendered black)
    tdir = _unit(Pk[-1] - Pk[-2])
    r_end = r0t[keep][-1]
    f_ = np.array([0.5, 0.85])
    Pk = np.vstack([Pk, Pk[-1] + np.outer(f_ * r_end, tdir)])
    sk = np.concatenate([sk, sk[-1] + f_ * r_end])
    Nk = np.vstack([Nk, Nk[-1:], Nk[-1:]])
    r_dome = np.concatenate([r0t[keep], r_end * np.sqrt(1.0 - f_ ** 2)])
    asp_dome = np.concatenate([aspt[keep], aspt[keep][-1:].repeat(2)])
    a4_dome = np.concatenate([a4t[keep], a4t[keep][-1:].repeat(2)])

    def tsect(i, th, r0=r_dome, asp=asp_dome, a4=a4_dome):
        r = r0[i] * (1.0 + a4[i] * np.cos(4.0 * th))
        return r * asp[i] / np.sqrt(asp[i] ** 2 * np.cos(th) ** 2 + np.sin(th) ** 2)
    V, Q, attr, isl = ring_tube(Pk, Nk, tsect, 8, s=sk, theta0=np.pi / 8, part=4.0, cut_len=0.040)
    sv = attr[:, 0]
    ws = np.clip((sv - spec['strap_len']) / (sb - spec['strap_len']), 0.0, 1.0)
    h = 1.0 - _smoothstep(sb - 0.001, sb + 0.001, sv)              # 1 on the shaft, 0 on the cable (eased at the bend)
    W = _weights(len(V), {'temple_L': (1.0 - ws) * h, 'hook_L': ws * h})
    # past the bend the cable's chain: each vertex between its two joints by arc length, the ferrule on the last
    chain = [f'cable_L{i + 1}' for i in range(N_CABLE)]
    sj = sb + cable_s(spec)
    for i in range(len(chain)):
        t = (sv - sj[i]) / (sj[i + 1] - sj[i]) if i + 1 < len(chain) else np.zeros_like(sv)
        lo = (sv < sj[i]) if i == 0 else np.zeros(len(sv), bool)    # the sleeve before the bend: the first joint
        on = ((t >= 0.0) & (t < 1.0)) if i + 1 < len(chain) else (sv >= sj[i])
        W[lo, JOINTS.index(chain[i])] += 1.0 - h[lo]
        W[on, JOINTS.index(chain[i])] += ((1.0 - t) * (1.0 - h))[on]
        if i + 1 < len(chain):
            W[on, JOINTS.index(chain[i + 1])] += (t * (1.0 - h))[on]
    regq = np.where(attr[Q[:, 0], 0] < sb - 0.0003, 4, 5)
    # the ferrule's end: a 2 x 2 grid cap over the last ring
    from .. import loft
    m = QuadMesh(V, Q, {'attr': attr})
    ring = np.arange(len(V) - 8, len(V))
    m, G = loft.cap(m, ring, tdir)
    tipc = Pk[-3] + tdir * r_end                                   # the hemisphere's pole
    inner = G[1:-1, 1:-1].ravel()
    m.V[inner] = tipc
    nv = len(m.V) - len(V)
    W = np.vstack([W, np.tile(W[-1], (nv, 1))])
    regq = np.concatenate([regq, np.full(len(m.Q) - len(Q), 5)])
    vs = np.unique(G)
    loc = -np.ones(len(m.V), np.int64)
    loc[vs] = np.arange(len(vs))
    e1 = _unit(np.cross(Pk[-1] - Pk[-2], [0.0, 1.0, 0.0]))
    e2 = np.cross(_unit(Pk[-1] - Pk[-2]), e1)
    isl.append(dict(Q=loc[m.Q[len(Q):]], orig=vs, UV=np.column_stack([(m.V[vs] - tipc) @ e1, (m.V[vs] - tipc) @ e2]),
                    quads=np.arange(len(Q), len(m.Q)), share=1.0))
    pieces.append(('temple', _piece(m.V, m.Q, regq, m.attrs['attr'], W, isl)))
    # ---- the pad arm (6 round) and the pad: the ivory disc and its cup as ONE revolve (the region switches at the lip)
    # its stations where it turns: one when the path has turned 10 deg since the last, or 0.6 mm on (9 stations,
    # 0.24 mm apart round the bend; evenly every 0.48 mm the bend fell between two and read as two kinks)
    Pa, sa = pad_arm_curve(spec, 1)
    keep = [0]
    for i in range(1, len(Pa) - 1):
        t0, t1 = _unit(Pa[i] - Pa[keep[-1]]), _unit(Pa[i + 1] - Pa[i])
        if np.degrees(np.arccos(np.clip(np.dot(t0, t1), -1.0, 1.0))) > 10.0 or sa[i] - sa[keep[-1]] > 0.0006:
            keep.append(i)
    sel = np.array(keep + [len(Pa) - 1])
    V, Q, attr, isl = ring_tube(Pa[sel], temple_frames(Pa)[sel], lambda i, th: 0.5 * spec['pad_arm_d'], 6,
                                s=sa[sel], part=6.0)
    pieces.append(('pad_arm', _piece(V, Q, 6, attr, _weights(len(V), {'pad_L': 1.0}), isl)))
    root, pc, nf = pad_frame(spec, 1)
    rp_, t_, dome = 0.5 * spec['pad_d'], spec['pad_t'], spec['pad_dome']
    lip, cb = spec['cup_lip'], spec['cup_back']
    ro = rp_ + lip
    re = 0.30 * t_
    pp = np.array([[0.00060, -cb - 0.0007], [0.00060, -cb - 0.0002], [ro - cb, -cb],
                   [ro - cb + cb * c45, -cb + cb * c45], [ro, 0.0], [ro, 0.45 * t_], [ro - 0.5 * lip, 0.45 * t_ + 0.5 * lip],
                   [rp_ - 0.08 * lip, 0.45 * t_ + 0.15 * lip], [rp_ - re + re * c45, t_ - re + re * c45],
                   [0.62 * (rp_ - re), t_ + dome * (1.0 - 0.62 ** 2)]])
    nf_e1 = _unit(np.cross(nf, [0.0, 1.0, 0.0]))
    V, Q, reg, attr, isl = revolve_piece(pp, pc, nf, 16, e1=nf_e1, cap0=True, cap1=True,
                                         region_of=lambda j: 7 if j < 7 else 8, part=7.0, cuts=[8])
    # the face cap's inner points onto the dome
    loc_r = np.linalg.norm((V - pc) - np.outer((V - pc) @ nf, nf), axis=1)
    face = ((V - pc) @ nf > 0.5 * t_) & (loc_r < 0.62 * (rp_ - re) - 1e-7)
    V[face] = V[face] + np.outer(t_ + dome * (1.0 - (loc_r[face] / (rp_ - re)) ** 2) - (V[face] - pc) @ nf, nf)
    pieces.append(('pad', _piece(V, Q, reg, attr, _weights(len(V), {'pad_L': 1.0}), isl)))
    # ---- the bridge (both halves, its own island: unstacked): 8 round its oval band, stations every 1.0 mm;
    # weights: the root at the apex easing to each lens joint over the whole half (a smootherstep, C2 at both ends),
    # the last 1.5 mm rigid with its rim (the solder joint). (The root alone over the middle 4 mm then a 12 mm
    # smoothstep, stations every 1.75 mm: on the v4 octopus the lenses splay 55 deg and the bridge stretched 37 ->
    # 69 mm through two narrow blends: a W with single-station kinks of 25-31 deg, review_fit.py)
    Pb, nb, sgn = bridge_curve(spec)
    selb = np.unique(np.r_[np.arange(0, len(Pb), 4), len(Pb) - 1])
    rb0, aspb = 0.5 * spec['band_t'], spec['band_w'] / spec['band_t']
    V, Q, attr, isl = ring_tube(Pb[selb], nb[selb], lambda i, th: rb0 * aspb / np.sqrt(
        aspb ** 2 * np.cos(th) ** 2 + np.sin(th) ** 2), 8, s=sgn[selb] - sgn[selb][0], part=1.0, cut_len=0.08)
    sv = attr[:, 0] + sgn[selb][0]
    s_half = float(sgn.max()) - 0.0015

    def smoother(t):
        t = np.clip(t, 0.0, 1.0)
        return t * t * t * (t * (6.0 * t - 15.0) + 10.0)
    wl = smoother(sv / s_half)
    wr = smoother(-sv / s_half)
    W = _weights(len(V), {'glasses_root': 1.0 - wl - wr, 'lens_L': wl, 'lens_R': wr})
    attr[:, 0] = sv
    bridge = _piece(V, Q, 1, attr, W, isl)
    # ---- assemble: the left pieces, the bridge, the left's mirrors (winding flipped, joints swapped L <-> R, the
    # islands SHARED: each mirrored island copy carries its left twin's island id)
    Vs, Qs, R, A, Ws, S, B = [], [], [], [], [], [], []
    split = dict(Q=[], orig=[], UV=[], island=[], wq=[], share=[], groups=[])
    cnt = dict(v=0, q=0, s=0, isl=0)
    swap = {JOINTS.index(f'{j}_L'): JOINTS.index(f'{j}_R') for j in ('lens', 'temple', 'hook', 'pad')}
    swap.update({JOINTS.index(f'cable_L{i + 1}'): JOINTS.index(f'cable_R{i + 1}') for i in range(N_CABLE)})
    perm = np.arange(len(JOINTS))
    for i_, j_ in swap.items():
        perm[i_], perm[j_] = j_, i_

    def add(pc_, side, isl_ids=None, paint=False):
        V_ = mirror(pc_['V'], side)
        Q_ = pc_['Q'] if side >= 0 else pc_['Q'][:, ::-1]
        Vs.append(V_)
        Qs.append(Q_ + cnt['v'])
        R.append(pc_['region'])
        A.append(pc_['attr'])
        Ws.append(pc_['W'] if side >= 0 else pc_['W'][:, perm])
        S.append(np.full(len(Q_), side))
        B.append(np.full(len(Q_), (bool(pc_['bake']) and side >= 0) or paint))
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
    add(bridge, 0)
    for (nm, pc_), ids_ in zip(pieces, left_isl):
        # the right LENS on texels of its own, painted (not baked: glass is not): stacked, its fingerprints were the
        # left's mirrored, a pair no hand leaves
        own = nm == 'lens'
        add(pc_, -1, None if own else ids_, paint=own)
    low = dict(V=np.concatenate(Vs), Q=np.concatenate(Qs), region=np.concatenate(R), attr=np.concatenate(A),
               W=np.concatenate(Ws), side=np.concatenate(S), bake=np.concatenate(B), names=[nm for nm, _ in pieces],
               split=dict(Q=np.concatenate(split['Q']), orig=np.concatenate(split['orig']),
                          UV=np.concatenate(split['UV']), island=np.concatenate(split['island']),
                          wq=np.concatenate(split['wq']), share=np.asarray(split['share']),
                          groups=split['groups']))
    mesh = QuadMesh(low['V'], low['Q'])
    chk = mesh.check()
    log(f'[round_glasses] low: {len(low["V"])} verts, {len(low["Q"])} quads ({2 * len(low["Q"])} tris) in '
        f'{len(pieces) * 2 + 1} pieces; ' + ', '.join(f'{REGIONS[r]} {int((low["region"] == r).sum()) * 2}'
                                                      for r in range(len(REGIONS))) + f' tris; check {chk}')
    return low


# ----------------------------------------------------------------------------------------------------------- UVs
def unwrap(low, size=1024, pad=6, log=print):
    """the islands (analytic, in metres: each at density 1 already) packed at ONE texel density, the lenses at
    LENS_SHARE of it; the right half's copies take their left twins' places (stacked). The density is searched so the
    sheet fills (uv.pack's skyline height 93-98.5 %), as top_hat's unwrap does"""
    from .. import uv as U
    sp = low['split']
    n_isl = len(sp['share'])
    first = {}
    for iid, v0, nv in sp['groups']:
        first.setdefault(iid, (v0, nv))
    uvs = [sp['UV'][first[i][0]:first[i][0] + first[i][1]] for i in range(n_isl)]
    area = 0.0
    for i in range(n_isl):
        q = sp['Q'][sp['island'] == i]
        v0 = first[i][0]
        mine = (q >= v0).all(1) & (q < v0 + first[i][1]).all(1)
        Pq = low['V'][sp['orig'][q[mine]]]
        area += 0.5 * np.linalg.norm(np.cross(Pq[:, 2] - Pq[:, 0], Pq[:, 3] - Pq[:, 1]), axis=1).sum() * \
            sp['share'][i] ** 2
    px = np.sqrt(0.60 * size * size / area)
    for _ in range(16):
        try:
            packed, used = U.pack(uvs, [px * sp['share'][i] for i in range(n_isl)], size, pad)
        except ValueError:
            used = 9.9
        if 0.93 <= used <= 0.985:
            break
        px *= (0.965 / used) ** 0.5 if used < 9.0 else 0.8
    while used > 1.0:
        px *= 0.97
        packed, used = U.pack(uvs, [px * sp['share'][i] for i in range(n_isl)], size, pad)
    UV = np.zeros_like(sp['UV'])
    for iid, v0, nv in sp['groups']:
        UV[v0:v0 + nv] = packed[iid]
    # each island's worst-direction footprint and its own overlaps (both copies share them)
    worst, over = 0.0, 0
    for i in range(n_isl):
        v0, nv = first[i]
        q = sp['Q'][(sp['island'] == i)]
        q = q[(q >= v0).all(1) & (q < v0 + nv).all(1)] - v0
        F = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
        Pv = low['V'][sp['orig'][v0:v0 + nv]]
        worst = max(worst, U.footprint(Pv, F, packed[i]))
        over += U.self_overlap(packed[i], F, res=256)
    log(f'[round_glasses] uv: {n_isl} islands (the right half stacked on the left), {px:.0f} px/m at {size} '
        f'({1000 / px:.3f} mm/texel; the lenses {px * LENS_SHARE:.0f}), height used {used * 100:.0f} %, worst '
        f'footprint p95 {worst:.2f}, self-overlapping texels {over}')
    return dict(UV=UV, px_per_m=float(px), size=size, used=float(used))


def low_arrays(low, uvs):
    """the export's arrays per SPLIT vertex: triangles along each quad's shorter diagonal (the split the bake and the
    export share), normals from the WELDED low, MikkT-style tangents, the region, bake flag and side per triangle,
    ATTR and the joint weights (4 influences: never more than 3 here)"""
    from .. import bake
    sp = low['split']
    Vn = low['V'][sp['orig']]
    Qn = sp['Q']
    d02 = np.linalg.norm(Vn[Qn[:, 0]] - Vn[Qn[:, 2]], axis=1)
    d13 = np.linalg.norm(Vn[Qn[:, 1]] - Vn[Qn[:, 3]], axis=1)
    short = d02 <= d13
    F = np.concatenate([np.where(short[:, None], Qn[:, [0, 1, 2]], Qn[:, [0, 1, 3]]),
                        np.where(short[:, None], Qn[:, [0, 2, 3]], Qn[:, [1, 2, 3]])])
    fq = np.concatenate([sp['wq'], sp['wq']])
    Nw = QuadMesh(low['V'], low['Q']).vertex_normals()
    N, TAN = bake.low_frames(Vn, F, uvs['UV'], Nw[sp['orig']])
    W = low['W'][sp['orig']]
    order = np.argsort(-W, axis=1)[:, :4]
    J = order.astype(np.uint16)
    Wt = np.take_along_axis(W, order, axis=1)
    Wt = (Wt / Wt.sum(1, keepdims=True)).astype(np.float32)
    return dict(V=Vn, F=F, UV=uvs['UV'], N=N, TAN=TAN, region=low['region'][fq].astype(np.int32),
                bake=low['bake'][fq], side=low['side'][fq], ATTR=low['attr'][sp['orig']], joints=J, weights=Wt,
                orig=sp['orig'], px_per_m=uvs['px_per_m'], size=uvs['size'])


# ------------------------------------------------------------------------------------------------------ fit data
def fit_data(spec=SPEC, low=None, n_probe=400):
    """what the runtime's glasses fit (accessories.js wear(): fit_pose's twin) and a validator need, prop space
    (metres): the lens's aperture radius (the fit scales it to FIT_EYE x the eye's radius), per side the rest lens
    centre, the lens joint (the bridge's junction), the endpiece's direction in the lens plane (the fit turns it toward
    the hook), the hinge pin and the temple's rest rotation, the ear bend (the hook joint), the cable's diameter; with
    a low, clearance PROBES (points of every part with their joint weights) for a validator to pose"""
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
    out = dict(archetype='glasses', prop='round_glasses', joints=list(JOINTS),
               lens=dict(radius=round(d['r_a'], 6), rim_outer=round(d['r_o'], 6), thickness=spec['lens_t'],
                         ior=spec['lens_ior']),
               eye_factor=FIT_EYE, cable_d=spec['cable_d'], sides=sides,
               seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0], left=[1.0, 0.0, 0.0]))
    if low is not None:
        rng = np.random.default_rng(5)
        pick = rng.choice(len(low['V']), min(n_probe, len(low['V'])), replace=False)
        W = low['W'][pick]
        out['probes'] = dict(points=rnd(low['V'][pick]), weights=np.round(W, 4).tolist(),
                             region=[int(np.bincount(low['region'][np.nonzero((low['Q'] == i).any(1))[0]]).argmax())
                                     for i in pick])
    return out


# --------------------------------------------------------------------------------------------------- sculpt plan
def plan_glasses(prog=None, spec=SPEC, rng=None, sides=(1, -1), log=print):
    """the sculpt plan (the fine hard-surface cuts a block-out's booleans leave out, every stroke placed analytically;
    the knuckles' seams are real gaps in the block-out now, barrel_profiles):
      * the SCREW SLOT across the hinge screw's pan head, 0.24 mm wide, its round bottom 0.24 mm under the crown, so
        it runs out at the head's edge as a real slot does (a capsule 0.10 mm under a 0.40 mm dome stopped short of
        both edges and baked as a pinched smear, t25), each turned its own way;
      * the RIM-LOCK line: the endpiece split where its two halves hold the eyewire's ends, a 0.06 mm cut along the
        lug from the rim to 0.2 mm short of the barrel (centred on the lug's middle at 1.2 mm round, it ran 0.55 mm
        into the temple's knuckle);
      * the cable's CRIMP: two rings pressed into the sleeve at the ear bend"""
    from ..species.octopus_sculpt import Plan
    from ..voxel import STROKE_CYL, STROKE_TORUS
    rng = rng or np.random.default_rng(11)
    plan = Plan()
    hh = 0.5 * spec['barrel_h']
    up = np.array([0.0, 1.0, 0.0])
    for side in sides:
        a, b, H = endpiece(spec, side)
        top = H[1] + hh - 0.00005 + spec['screw_h']
        ang = rng.uniform(0.0, np.pi)
        u = np.array([np.cos(ang), 0.0, np.sin(ang)]) * (spec['screw_r'] + 0.0002)
        c = np.array([H[0], top - 0.00012, H[2]])
        plan.add(STROKE_CYL, c - u, c + u, 0.00012, 0.00002, 'carve', 0.00002, 'screw slot')
        c = a + 0.35 * (b - a)
        r_lock = min(0.0012, float(np.linalg.norm((H - c)[[0, 2]])) - spec['barrel_r'] - 0.0002)
        plan.add(STROKE_CYL, c - up * 0.00003, c + up * 0.00003, r_lock, 0.00001, 'carve', 0.00001, 'rim lock')
        Pt, st, sb = temple_curve(spec, side)
        for s in (sb + 0.0004, sb + spec['sleeve_len'] - 0.0004):
            i = int(np.searchsorted(st, s))
            c = Pt[i]
            t = _unit(Pt[min(i + 1, len(Pt) - 1)] - Pt[max(i - 1, 0)])
            plan.add(STROKE_TORUS, c, c + t * 0.0001, 0.5 * spec['sleeve_d'] + 0.00002, 0.00006, 'carve', 0.00002,
                     'crimp')
    log('[round_glasses] plan: ' + ', '.join(f'{o["tag"]} {len(o["A"])}' for o in plan.ops))
    return plan


# ------------------------------------------------------------------------------------------------- material pass
@wp.struct
class Finish:
    h: float            # the texture tier's height (m)
    col: wp.vec3        # base colour (a metal's F0)
    rough: float
    metal: float
    zone: float         # the palette zone: 0 the plating, 1/3 the base metal it wore through to, 2/3 ivory, 1 glass
    wear: float         # the plating worn through (0..1)
    dirt: float         # grime on the frame, prints and dust on the glass
    scratch: float      # micro-scratch density (along each wire)


@wp.func
def finish_at(p: wp.vec3, n: wp.vec3, reg: int, at: wp.vec4, texel: float, conv: float, cav: float, aol: float,
              C: wp.array(dtype=wp.vec3), R: wp.array(dtype=wp.float32), G3: wp.array(dtype=wp.vec3),
              S: wp.array(dtype=wp.float32), PR: wp.array(dtype=wp.vec4), seed: int):
    """one surface point's finish. G3: the (left) lens centre, the hinge pin, the pad's centre, the bridge's contact
    direction, the pad's face normal; S: the bend's s, the sleeve's length, where the ferrule starts, the coil's pitch
    and relief, the beads' relief, the aperture radius, where the lens bevel starts, the rim's centre radius, the
    barrel's radius, the pad's radius, thickness and the cup's lip, the prints' ridge period, the barrel's half-height,
    the middle knuckle's half-height and half the gap between knuckles; PR: the fingerprints, three a lens (left, then
    right), two vec4 each (MATERIAL['prints'])"""
    out = Finish()
    s = at[0]
    th = wp.atan2(at[2], at[1])
    lc = G3[0]
    sb = S[0]
    h = float(0.0)
    col = C[0]
    rough = R[0]
    metal = float(1.0)
    zone = float(0.0)
    wear = float(0.0)
    dirt = float(0.0)
    scr = float(0.0)
    if reg == 9:
        # crown glass: the faint green tint, oily FINGERPRINTS where the lens is held (at its edge: three a lens, PR),
        # a light haze toward the rim, dust; the bevel's ground edge frosted where it shows inside the rim. The right
        # lens has texels of its own, so it takes its own centre and its own prints
        lcx = lc[0]
        k0 = int(0)
        if p[0] < 0.0:
            lcx = -lc[0]
            k0 = 3
        dx = p[0] - lcx
        dy = p[1] - lc[1]
        rho = wp.sqrt(dx * dx + dy * dy)
        face = float(1.0)                      # the outer face (+Z) or the inner: a print is on one of them
        if n[2] < 0.0:
            face = -1.0
        prints = float(0.0)
        for i in range(3):
            a0 = PR[2 * (k0 + i)]              # the print's centre (x, y), its long axis's angle, its semi-axis
            a1 = PR[2 * (k0 + i) + 1]          # its aspect, its core's offset (of the semi-axis), strength (its sign
                                               # the face: + outer, - inner), a seed
            # a whorl's ridges 0.45 mm apart round a core off the patch's centre, the coordinates warped by ~2 ridge
            # periods (no two ridges alike: unwarped, evenly spaced and centred, the rings read as a bullseye, t25)
            w = proc.warp3(wp.vec3(dx, dy, a1[3] * 0.013), 0.0024, 0.0009, seed + 61 + 17 * (k0 + i))
            ux = w[0] - a0[0]
            uy = w[1] - a0[1]
            ca = wp.cos(a0[2])
            sa = wp.sin(a0[2])
            qx = (ca * ux + sa * uy) / (a0[3] * a1[0])
            qy = (-sa * ux + ca * uy) / a0[3]
            rr = wp.sqrt(qx * qx + (qy - a1[1]) * (qy - a1[1])) * a0[3]
            ridge = 0.5 + 0.5 * wp.cos(6.2831853 * rr / S[13])
            # breaks and pores (ridge endings, sweat pores ~0.15 mm), and a smear across part of the patch where the
            # finger slid: the ridges there blur into the oily film
            brk = proc.smoothstep(-0.25, 0.15, proc.noise3(p / 0.0006, seed + 63 + k0 + i))
            pore = proc.smoothstep(0.02, 0.09, proc.cellular3(p / 0.00035, 0.9, seed + 64).f1)
            smear = proc.smoothstep(0.05, 0.45, proc.fbm3(wp.vec3(qx * 1.5, qy * 0.4, a1[3]), 3, 2.0, 0.5, seed + 65))
            vis = (ridge * brk * pore) * (1.0 - smear) + 0.55 * smear
            # the patch: an ellipse with a ragged edge, pressed hardest at its middle
            edge = wp.sqrt(qx * qx + qy * qy) + 0.22 * proc.fbm3(wp.vec3(qx * 2.2, qy * 2.2, a1[3] + 3.1), 3, 2.0,
                                                                   0.5, seed + 66)
            patch = (1.0 - proc.smoothstep(0.62, 1.0, edge)) * (0.7 + 0.3 * (1.0 - proc.smoothstep(0.0, 0.9, edge)))
            prints = wp.max(prints, wp.max(a1[2] * face, 0.0) * patch * (0.25 + 0.75 * vis))
        haze = 0.18 * proc.smoothstep(0.55, 0.95, rho / S[6]) * proc.smoothstep(-0.1, 0.5, proc.fbm3(p / 0.007, 3,
                                                                                                   2.0, 0.5, seed + 75))
        prints = wp.clamp(wp.max(prints, haze), 0.0, 1.0)
        sp = proc.cellular3(p / 0.0016, 0.9, seed + 77)          # dust: a speck in one cell of eight, 0.1-0.2 mm
        dust = (1.0 - proc.smoothstep(0.03, 0.07, sp.f1)) * proc.smoothstep(0.86, 0.9, sp.rand)
        col = C[5]
        rough = R[3] + R[4] * prints
        # the ground bevel, frosted from the 24-gon low's inscribed circle out (cos(pi / 24) of the bevel's start: by
        # the true radius alone, the polygon's chords dipped under it and the frost came as 24 ticks round each lens)
        if rho > S[7] * 0.99144 - 0.00002:
            rough = 0.55
            col = wp.vec3(0.82, 0.86, 0.84)
        metal = 0.0
        zone = 1.0
        dirt = wp.max(prints, dust)
    elif reg == 8:
        # aged ivory: a fine grain and the bone's canal flecks, yellowed toward the edge, the face polished by skin
        pc = G3[2]
        rr = wp.length(p - pc) / 0.004
        grain = proc.fbm3(wp.vec3(p[0] / 0.0004, p[1] / 0.0016, p[2] / 0.0004), 3, 2.0, 0.5, seed + 81)
        fleck = proc.smoothstep(0.06, 0.0, proc.cellular3(p / 0.0007, 0.9, seed + 83).edge)
        col = C[3] * wp.exp(0.10 * grain - 0.25 * proc.smoothstep(0.6, 1.0, rr) - 0.18 * fleck)
        rough = R[2] - 0.08 * (1.0 - proc.smoothstep(0.0, 0.8, rr)) + 0.05 * grain
        h = 0.000003 * grain * proc.smoothstep(2.5, 4.0, 0.0004 / texel)
        metal = 0.0
        zone = 2.0 / 3.0
        dirt = 0.4 * proc.smoothstep(0.75, 1.0, rr) * proc.smoothstep(0.0, 0.5, -aol * 40.0 + 0.2)
    else:
        # MICRO-SCRATCHES along each wire: streaks long along it (3.5 mm), thin across (0.06 mm); the rim's run round
        # the lens, a knuckle's or a cup's round its own axis (turned parts). The angle round a part enters as its
        # cosine and sine, so the pattern closes on itself (through atan2 it jumped at +-pi: a seam down the front of
        # each barrel and on every rim's nose side, t25)
        q = wp.vec3(s / 0.0035 + float(reg) * 7.1, at[1] * 8.33, at[2] * 8.33)     # a wire: 52 streaks round it
        if reg == 0 or reg == 3 or reg == 7:
            rad = S[8]                         # round the part at its own radius: the rim's, the barrel's, the cup's
            if reg == 3:
                rad = S[9]
            if reg == 7:
                rad = S[10]
            q = wp.vec3(at[1] * rad / 0.0035, at[2] * rad / 0.0035, s / 0.00006 + float(reg) * 7.1)
        n1 = proc.noise3(q, seed + 91) + 0.5 * proc.noise3(q * 2.3, seed + 93)
        scr = proc.smoothstep(0.62, 0.95, wp.abs(n1)) * (0.5 + 0.5 * proc.noise3(p / 0.004, seed + 95))
        rough = R[0] + R[5] * scr
        h = -0.000004 * scr * proc.smoothstep(2.5, 4.0, 0.00006 / texel)
        # the cable's coil (past the sleeve, before the ferrule): a helical rib of pitch S[3]
        if reg == 5 and s > sb + S[1] + 0.0003 and s < S[2]:
            ph = s / S[3] - th / 6.2831853
            c = 0.5 + 0.5 * wp.cos(6.2831853 * ph)
            h = h + S[4] * (wp.pow(c, 0.7) - 0.6) * proc.smoothstep(2.5, 4.0, S[3] / texel)
        # the bridge's milgrain: a bead row along both edges of the band
        if reg == 1:
            x = s / 0.00032
            f = x - wp.floor(x)
            bead = 1.0 - (2.0 * f - 1.0) * (2.0 * f - 1.0)
            edge = proc.smoothstep(0.86, 0.96, wp.abs(at[2]))
            h = h + S[5] * (bead - 0.45) * edge * proc.smoothstep(2.5, 4.0, 0.00032 / texel)
        # WEAR, each by its cause: the pad arms (fingers set them), the bridge's underside at the apex (skin), the
        # temples' inner side round the ear bend and down the cable (skin, the ear), the knuckles' and the lug's edges
        # (opening, closing), the rims' outer face below the lens (set down on tables), every edge a little
        # (the barrel: its knuckles' ends and gaps are at known heights off the pin, its side at the barrel's radius)
        yk = p[1] - G3[1][1]
        dy_gap = wp.min(wp.abs(wp.abs(yk) - S[15] - S[16]), wp.abs(wp.abs(yk) - S[15] + S[16]))
        dy = wp.min(wp.abs(wp.abs(yk) - S[14]), dy_gap)
        rk = wp.sqrt((p[0] - G3[1][0]) * (p[0] - G3[1][0]) + (p[2] - G3[1][2]) * (p[2] - G3[1][2]))
        cause = float(0.0)
        if reg == 6:
            cause = 0.6
        if reg == 1:
            cause = proc.smoothstep(0.2, 0.8, wp.dot(n, G3[3])) * (1.0 - proc.smoothstep(0.003, 0.007, wp.abs(s)))
        if reg == 4 or reg == 5:
            inner = proc.smoothstep(0.1, 0.6, -n[0])
            near = proc.smoothstep(sb - 0.020, sb - 0.008, s) * (1.0 - proc.smoothstep(sb + 0.040, sb + 0.050, s))
            cause = 0.6 * inner * near
        if reg == 2:
            cause = 0.8 * proc.smoothstep(0.3, 0.9, conv)
        if reg == 3:
            # the knuckles' ends, rubbed as the temple opens and closes: a clean rim along each (driven by the bake's
            # convexity it came as blocky patches beside the strap, where the barrel's low meets the strap and the lug
            # and the bake fell back to the closest point, t25); the barrel's side and its ends' outer edges only
            if rk > S[9] - 0.00012:
                cause = 0.75 * (1.0 - proc.smoothstep(0.00004, 0.00028, dy))
        if reg == 0:
            radial = wp.normalize(wp.vec3(p[0] - lc[0], p[1] - lc[1], 0.0))
            low = proc.smoothstep(-0.55, -0.85, (p[1] - lc[1]) / S[8])
            cause = 0.45 * low * proc.smoothstep(0.3, 0.8, wp.dot(n, radial))
        # worn through past 0.30 (soft over 0.12, a texel or two in close-ups), tarnish only on the worn zone's edge
        # where the plating thins (fbm3's spread is ~+-0.2: through 0.42-0.66 a pad arm's 0.65 cause wore through 0.0 %
        # of its texels, the temple 0.4 %, the bridge 1.7 %, and a band of wv under the wear painted brown smudges
        # wherever a cause was middling: the rims' undersides, review_maps.py)
        patch = 0.55 + 1.2 * proc.fbm3(p / 0.0018, 3, 2.0, 0.5, seed + 97)
        wv = cause * patch + 0.18 * proc.smoothstep(0.5, 1.5, conv)
        wear = proc.smoothstep(0.30, 0.42, wv)
        tarn = 4.0 * wear * (1.0 - wear)
        col = M.mix3(C[0], C[1], wear)
        col = M.mix3(col, C[2], 0.55 * tarn)
        rough = rough + (R[1] - R[0]) * wear + 0.18 * tarn
        zone = wear / 3.0
        # GRIME: the rim's groove at the glass (ref 02's brown deposits), the knuckle seams, the screw slot, the lug's
        # split, the cup's lip at the ivory: the bake's cavity and local AO, gathered by a patchy noise
        # (the bake's cavity is the open share of a 0.6 mm hemisphere: low in a crevice; octopus_skin's 0.70-0.90)
        g = wp.clamp(-aol * 30.0, 0.0, 1.0) * 0.5 + (1.0 - proc.smoothstep(0.55, 0.85, cav)) * 0.8
        if reg == 0:
            inward = proc.smoothstep(0.5, 0.85, -wp.dot(n, wp.normalize(wp.vec3(p[0] - lc[0], p[1] - lc[1], 0.0))))
            g = g + 0.5 * inward
        if reg == 3 and rk > S[9] - 0.0004:
            # the barrel's side: grime in its seams, at their known heights (by the bake's cavity, the texels beside
            # the strap and the lug, fallen back to the closest point, painted pixelated matte blotches, t25); the
            # screw's head keeps the bake's cavity, its slot
            g = 0.9 * (1.0 - proc.smoothstep(0.00003, 0.00016, dy_gap))
        dirt = wp.clamp(g * (0.45 + 0.8 * proc.fbm3(p / 0.0011, 2, 2.0, 0.5, seed + 99)), 0.0, 1.0)
        col = M.mix3(col, C[4], 0.85 * dirt)
        metal = 1.0 - 0.9 * dirt
        rough = rough + (0.75 - rough) * dirt
    out.h = h
    out.col = col
    out.rough = rough
    out.metal = metal
    out.zone = zone
    out.wear = wear
    out.dirt = dirt
    out.scratch = scr
    return out


@wp.func
def pad_zone(p: wp.vec3, reg: int, G3: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32)):
    """the pad piece's region by a point of the HIGH (the bake's hit, where the baked lip is): ivory (8) where the
    disc's face stands clear of the cup's lip (its height off the cup's seat, its radius about the pad's axis), else
    the metal cup (7). By the low's quads the ivory-metal border ran jagged across the baked lip, by the low's points
    it still stepped where the 16-round disc left the true lip (t25)"""
    if reg != 7 and reg != 8:
        return reg
    q = p - G3[2]
    hp = wp.dot(q, G3[4])
    rp = wp.length(q - G3[4] * hp)
    if hp > 0.45 * S[11] + 0.3 * S[12] and rp < S[10] - 0.45 * S[12]:
        return 8
    return 7


@wp.kernel
def k_glasses(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
              ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32),
              d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_cav: wp.array(dtype=wp.float32),
              d_aol: wp.array(dtype=wp.float32), d_conv: wp.array(dtype=wp.float32), d_pos: wp.array(dtype=wp.vec4),
              C: wp.array(dtype=wp.vec3),
              R: wp.array(dtype=wp.float32), G3: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32),
              PR: wp.array(dtype=wp.vec4),
              texel: float, seed: int, o_alb: wp.array(dtype=wp.vec3), o_nrm: wp.array(dtype=wp.vec3),
              o_orm: wp.array(dtype=wp.vec3), o_mask: wp.array(dtype=wp.vec4), o_cov: wp.array(dtype=wp.float32)):
    tid = wp.tid()
    x = tid % size
    y = tid // size
    dn = d_nrm[tid]
    baked = int(0)
    tn_b = wp.vec3(0.0, 0.0, 1.0)
    if dn[3] > 0.0:
        baked = 1
        tn_b = wp.normalize(wp.vec3(dn[0], dn[1], dn[2]))
    inv = 1.0 / float(ss)
    dlt = 0.5 * inv
    acc_a = wp.vec3(0.0)
    acc_n = wp.vec3(0.0)
    acc_r = float(0.0)
    acc_m = float(0.0)
    acc_ao = float(0.0)
    acc_k = wp.vec4(0.0)
    hits = int(0)
    for i in range(ss):
        for j in range(ss):
            fx = float(x) + (float(i) + 0.5) * inv
            fy = float(y) + (float(j) + 0.5) * inv
            lo = M.low_at(uv_mesh, fx, fy, lpos, lnrm, ltan, lattr)
            if lo.ok == 0:
                continue
            hp = lo.p
            if baked == 1 and d_pos[tid][3] > 0.0:
                hp = wp.vec3(d_pos[tid][0], d_pos[tid][1], d_pos[tid][2])
            reg = pad_zone(hp, lreg[lo.face], G3, S)
            if reg != 9 and baked == 0:
                continue                       # a frame texel the bake missed (the gate reports it)
            lx = M.low_at(uv_mesh, fx + dlt, fy, lpos, lnrm, ltan, lattr)
            if lx.ok == 0:
                lx = M.low_at(uv_mesh, fx - dlt, fy, lpos, lnrm, ltan, lattr)
            ly = M.low_at(uv_mesh, fx, fy + dlt, lpos, lnrm, ltan, lattr)
            if ly.ok == 0:
                ly = M.low_at(uv_mesh, fx, fy - dlt, lpos, lnrm, ltan, lattr)
            ao = float(1.0)
            cav = float(0.0)
            aol = float(0.0)
            conv = float(0.0)
            if baked == 1:
                ao = d_ao[tid]
                cav = d_cav[tid]
                aol = d_aol[tid]
                conv = d_conv[tid]
            nw = M.to_world(lo, tn_b)
            f = finish_at(lo.p, nw, reg, lo.attr, texel, conv, cav, aol, C, R, G3, S, PR, seed)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1 and reg != 9:
                hx = finish_at(lx.p, nw, reg, lx.attr, texel, conv, cav, aol, C, R, G3, S, PR, seed).h
                hy = finish_at(ly.p, nw, reg, ly.attr, texel, conv, cav, aol, C, R, G3, S, PR, seed).h
                g = M.surface_grad(lo.p, lx.p, ly.p, f.h, hx, hy)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            acc_a = acc_a + f.col
            acc_r = acc_r + wp.clamp(f.rough, 0.03, 1.0)
            acc_m = acc_m + f.metal
            acc_ao = acc_ao + ao
            acc_k = acc_k + wp.vec4(f.dirt, f.wear, f.zone, f.scratch)
            hits = hits + 1
    if hits == 0:
        return
    fh = float(hits)
    # Toksvig: the averaged normal's lost length widens the highlight
    ln = wp.length(acc_n) / fh
    var = wp.clamp((1.0 - ln) / wp.max(ln, 1.0e-4), 0.0, 1.0)
    rr = acc_r / fh
    a = rr * rr
    rr = wp.sqrt(wp.sqrt(a * a + var))
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    o_orm[tid] = wp.vec3(acc_ao / fh, wp.clamp(rr, 0.0, 1.0), acc_m / fh)
    o_mask[tid] = acc_k / fh
    o_cov[tid] = 1.0


def run_material(L, drivers, size, texel, spec=SPEC, ss=2, recipe=MATERIAL, log=print):
    """the material pass over the glasses' texture set: the bake set's frame texels (left half + bridge) from the
    bake's drivers, the left lens's texels unbaked (a flat normal, AO 1). Returns image-order uint8 maps: albedo
    (sRGB), normal (GL), orm (AO, roughness, metalness), masks (R grime / prints, G plating worn through, B palette
    zone, A micro-scratch density) and palette_base (each zone's median linear albedo, for the runtime's recolour)"""
    import time
    from .. import calib
    from ..bake import dilate_all
    t0 = time.time()
    sel = L['bake']
    F = L['F'][sel]
    uvm = M.uv_bvh(F, L['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(L['V'], F, L['N'], L['TAN'], L['ATTR'])
    rel = calib.relief_drivers(drivers, 1.0 / texel, ao_sigma_mm=1.2, fine_sigma_mm=0.08, mid_sigma_mm=0.35)
    D = M.driver_arrays({**drivers, **rel})
    d = dims(spec)
    Pt, st, sb = temple_curve(spec, 1)
    root, pc, nf = pad_frame(spec, 1)
    P = _arch_plane(spec)
    contact = _unit(-P)                                            # the bridge's underside faces down-back
    C = wp.array(np.array([recipe['gold'], recipe['nickel'], recipe['tarnish'], recipe['ivory'], recipe['grime'],
                           recipe['glass']], np.float32), dtype=wp.vec3)
    R = wp.array(np.array([recipe['gold_rough'], recipe['nickel_rough'], recipe['ivory_rough'], recipe['glass_rough'],
                           recipe['print_rough'], recipe['scratch_rough']], np.float32), dtype=wp.float32)
    G3 = wp.array(np.array([d['C'], d['H'], pc, contact, nf], np.float32), dtype=wp.vec3)
    g = lens_geom(spec)
    S = wp.array(np.array([sb, spec['sleeve_len'], st[-1] - spec['tip_len'], spec['coil_pitch'], recipe['coil_amp'],
                           recipe['bead_amp'], d['r_a'], g['rho_b'], d['r_c'], spec['barrel_r'], 0.5 * spec['pad_d'],
                           spec['pad_t'], spec['cup_lip'], recipe['print_ridge'], 0.5 * spec['barrel_h'],
                           0.5 * spec['knuckle_mid'], 0.5 * spec['knuckle_gap']], np.float32), dtype=wp.float32)
    pr = []
    for k, lens in enumerate(recipe['prints']):
        for i, (x, y, ang, semi, asp, core, strength) in enumerate(lens):
            pr += [[0.001 * x, 0.001 * y, np.radians(ang), 0.001 * semi], [asp, core, strength, 1.0 + 3 * k + i]]
    PR = wp.array(np.array(pr, np.float32), dtype=wp.vec4)
    n = size * size
    o_alb, o_nrm, o_orm = (wp.zeros(n, dtype=wp.vec3) for _ in range(3))
    o_mask = wp.zeros(n, dtype=wp.vec4)
    o_cov = wp.zeros(n, dtype=wp.float32)
    wp.launch(k_glasses, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
                                        wp.array(np.asarray(L['region'][sel], np.int32), dtype=wp.int32), D['normal'],
                                        D['ao'], D['cavity'], D['ao_local'], D['conv'], D['position'], C, R, G3, S, PR,
                                        float(texel),
                                        int(recipe['seed']), o_alb, o_nrm, o_orm, o_mask, o_cov])
    wp.synchronize()
    img = lambda a, k: np.asarray(a.numpy()).reshape(size, size, k)[::-1]
    alb, nrm, orm, msk = img(o_alb, 3), img(o_nrm, 3), img(o_orm, 3), img(o_mask, 4)
    cov = img(o_cov, 1)[..., 0] > 0
    zone = np.rint(msk[..., 2] * 3.0).astype(int)
    pal = {}
    for zi, nm in enumerate(('plating', 'base', 'ivory', 'glass')):
        s_ = cov & (zone == zi)
        if s_.sum() > 16:
            pal[nm] = [float(x) for x in np.median(alb[s_], axis=0)]
    dil, grown = dilate_all(dict(normal=np.concatenate([nrm, cov[..., None].astype(np.float32)], -1), alb=alb,
                                 orm=orm, msk=msk), 8)
    alb_s = M.srgb_oetf(np.where(grown[..., None], dil['alb'], 0.05))
    nrm_t = np.where(grown[..., None], dil['normal'][..., :3], [0.0, 0.0, 1.0])
    out = dict(albedo=(alb_s * 255 + 0.5).astype(np.uint8),
               normal=np.clip((nrm_t * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8),
               orm=np.clip(np.where(grown[..., None], dil['orm'], [1.0, 0.5, 1.0]) * 255 + 0.5, 0, 255).astype(np.uint8),
               masks=np.clip(np.where(grown[..., None], dil['msk'], 0.0) * 255 + 0.5, 0, 255).astype(np.uint8),
               palette_base=pal, coverage=float(cov.mean()))
    log(f'[round_glasses] material {size}^2 x ss {ss}: {time.time() - t0:.1f}s; coverage {cov.mean() * 100:.1f} %; '
        f'palette base (linear) ' + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in pal.items()))
    return out


# -------------------------------------------------------------------------------------------------------- export
def export_glb(path, L, maps, spec=SPEC, low=None):
    """a SKINNED glb: one mesh, two primitives sharing its vertices (the frame: base, normal, ORM, the masks in
    KHR_materials_volume's thickness slot as the creatures carry theirs; the glass: the same maps, with
    KHR_materials_transmission, _ior and _volume's real thickness), the skeleton (JOINTS) with its inverse bind
    matrices, the fit data in the mesh node's and the file's extras"""
    from .. import gltf
    g = gltf.GLB()
    t_base = g.texture(maps['albedo'], fmt='jpeg', quality=95)
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='png')
    t_msk = g.texture(maps['masks'], fmt='png')
    chans = ('R grime on the frame / prints and dust on the glass, G plating worn through, B palette zone (0 the '
             'plating, 1/3 the base metal, 2/3 ivory, 1 glass), A micro-scratch density')
    m_frame = g.material('round_glasses', base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='prop', prop='round_glasses', masks=t_msk, masks_channels=chans,
        palette_base=maps.get('palette_base', {})))
    m_lens = g.material('round_glasses_lens', base=t_base, normal=t_nrm, orm=t_orm, extras=dict(
        bestiary='prop', prop='round_glasses', part='lens', masks=t_msk, masks_channels=chans))
    lens = g.j['materials'][m_lens]
    lens['pbrMetallicRoughness']['metallicFactor'] = 0.0
    lens['extensions'] = {'KHR_materials_transmission': {'transmissionFactor': 1.0},
                          'KHR_materials_ior': {'ior': spec['lens_ior']},
                          'KHR_materials_volume': {'thicknessFactor': spec['lens_t'],
                                                   'attenuationColor': list(MATERIAL['glass']),
                                                   'attenuationDistance': 0.03}}
    lens['alphaMode'] = 'OPAQUE'
    g.ext_used.update({'KHR_materials_transmission', 'KHR_materials_ior', 'KHR_materials_volume'})
    sk = skeleton(spec)
    skin, joint_nodes = g.skeleton(sk)
    glass = L['region'] == 9
    mesh = g.mesh('round_glasses', L['V'], L['N'], L['TAN'], L['UV'], [(L['F'][~glass], m_frame),
                                                                      (L['F'][glass], m_lens)],
                  joints=L['joints'], weights=L['weights'])
    fit = fit_data(spec, low)
    g.node('round_glasses', mesh=mesh, skin=skin, root=True, extras=dict(bestiary='prop', fit=fit))
    return g.save(path, extras=dict(bestiary=dict(prop='round_glasses', archetype='glasses', units='m', up='+Y',
                                                  forward='+Z', left='+X', triangles=int(len(L['F'])), fit=fit)))


# --------------------------------------------------------------------------------------------- the whole forge
def forge(out_dir, size=1024, voxel_size=0.00004, band=0.0003, ss=2, seed=7, spec=SPEC, log=print):
    """block-out -> low -> UVs -> plan -> voxel high of the left half and the bridge (GPU) -> bake (GPU) -> material
    -> skinned glb; returns the glb's path. The heavy steps one at a time (the voxel high ~18M voxels at 0.04 mm in a
    +-0.3 mm band round ~13 cm^2 of metal; the bake at 1024 x ss 2)"""
    import os
    import time

    from PIL import Image

    from .. import bake, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    prog = build_sdf(spec)
    low = build_low(spec, log=log)
    uvs = unwrap(low, size, log=log)
    L = low_arrays(low, uvs)
    plan = plan_glasses(prog, spec, np.random.default_rng(seed), log=log)
    d = dims(spec)
    lo, hi = bounds(spec, half=True)
    keep = lambda cc: cc[:, 0] > -(d['J'][0] + 0.003)              # the left half and the whole bridge
    # faces BURIED in another part (a strap's root over its knuckle, a lug's or a bridge's end in its rim) are hidden:
    # left out of the bake and the paint, their texels dilate from their neighbours (baked, the knuckle under the
    # temple's strap found no surface for 1.6 % of its island and failed the gate). Buried = the way out along the
    # face's own normal is long (under a strap, inside a barrel: 0.4 mm and more); a facet whose own round lies just
    # over it is not (an 8-round 0.5 mm wire's middle is 38 um in, the 16-round pad's disc edge 0.1 mm: by depth alone
    # half the set, then the pad's edge band, read as buried and dilated gold notches into the ivory)
    cen = L['V'][L['F']].mean(1)
    fnm = np.cross(L['V'][L['F'][:, 1]] - L['V'][L['F'][:, 0]], L['V'][L['F'][:, 2]] - L['V'][L['F'][:, 0]])
    fnm /= np.maximum(np.linalg.norm(fnm, axis=1, keepdims=True), 1e-20)
    pex, _ = prog.project(cen, fnm, maxd=0.003)
    buried = (prog.eval(cen) < -0.00003) & (np.linalg.norm(pex - cen, axis=1) > 0.00025) & (L['region'] != 9) & \
        L['bake']
    L['bake'] = L['bake'] & ~buried
    log(f'[round_glasses] {int(buried.sum())} of the bake set\'s triangles buried in another part (not baked: their '
        f'texels dilate)')
    G = voxel.SparseSDF(prog, lo, hi, voxel=voxel_size, band=band, extra=plan.bounds(prog, band), keep=keep, log=log)
    plan.apply(G, log=log)
    sel = L['bake'] & (L['region'] != 9)
    res = bake.bake(G, L['V'], L['F'][sel], L['UV'], L['N'], L['TAN'], L['region'][sel], size=size, ss=ss,
                    cage=0.0006, ao_r=0.004, cav_r=0.0006, n_ao=96, n_cav=48, n_thk=2, thk_max=0.003, cage_min=0.00003,
                    reach_margin=0.0002, far_max=0.0003, proj_tol=2.0e-5, seed=seed,
                    region_names={i: r for i, r in enumerate(REGIONS)}, log=log)
    keep_ = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
             if k != 'position'}
    np.savez_compressed(os.path.join(out_dir, 'drivers_round_glasses.npz'), **keep_)
    maps = run_material(L, res, size, 1.0 / L['px_per_m'], spec, ss=ss, log=log)
    for k in ('albedo', 'normal', 'orm', 'masks'):
        Image.fromarray(maps[k]).save(os.path.join(out_dir, f'T_round_glasses_{k}.png'))
    path = os.path.join(out_dir, 'round_glasses.glb')
    nbytes = export_glb(path, L, maps, spec, low)
    log(f'[round_glasses] wrote {path} ({nbytes / 1e6:.1f} MB, {len(L["F"])} triangles) in {time.time() - t0:.0f}s')
    return path
