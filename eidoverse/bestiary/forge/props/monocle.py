"""THE MONOCLE: a Bestiary accessory (DESIGN.md "Accessories"; remix/recipe.py ACCESSORIES['monocle']: archetype 'monocle',
authored radius 16 mm, gold and glass), built the forge way at real size, as the round glasses were (round_glasses.py: its
eyewire, lens and material pass are this prop's, read with this prop's SPEC).

  parts -> block-out SDF:  the EYEWIRE a REVOLVE of the glasses' grooved D section about the lens axis, the LENS a plano
                           crown-glass meniscus seated in its groove (the glasses' lens_profile), the CORD RING a torus at the
                           rim's foot, its top fused into the rim's outer face; the chain's LINK (a cable chain's oval wire
                           link) and the chain's END (a domed stud with a bail ring: where the chain is fixed on the
                           wearer) each beside the monocle in the bake's space (each exported at its own origin)
  -> the low:              revolve rings (the eyewire 56 round its 10-point section, the lens's bevel band and grid caps, the
                           ring, the stud), the link a torus stretched to its oval
  -> UV islands:           analytic (round_glasses.revolve_piece), packed at one density (the lens's faces at the glasses'
                           shares), one 1024^2 set
  -> voxel high + bake     (the metal: the eyewire, the ring, the link, the stud; the glass is not baked)
  -> material pass:        round_glasses.k_glasses on this prop's regions (micro-scratches round the eyewire and along each
                           wire, the lens's crown-glass tint, a light edge haze, three oily prints where it is held), then
                           (B10c) THE KEPT GILDED GOLD over its metal (kept_finish): fine gold's F0 over brass, the plating worn
                           through only where the shared pass wore it fully, a quarter of its grime, polished (B10b's rolled
                           gold over nickel silver, rubbed and grimed, read as old brass in the studio: the B10b check)
  -> a static glb: the monocle (the frame's and the glass's primitives) in the scene, its fit data in the node's and the
     file's extras; the chain's link and end as two meshes outside the scene (accessories.js instances the link along the
     chain it hangs, and places the end on the wearer)

Frame: metres, the prop's own frame = its seat's (remix.js's item contract): the origin the LENS CENTRE, +Z the lens's outer face
(away from the eye), +Y up, +X its left. The CHAIN hangs from the cord ring's foot (fit.eyelet.attach) to the end's bail
(fit.chain.end_attach, in the end's frame: +Y the wearer's skin normal, the origin on the skin). The fit on a creature (the
socket's fit.monocle: offset and rotation in the eye socket's frame, radius = the lens's radius as worn, the chain's anchor on
the wearer) is the creature's (work/bestiary/beetle/b10/r01_rig.py writes the beetle's); this prop carries the octopus's as a
CONFORM record (its glb predates the monocle: octopus_conform() measures it, read only).

MEASURED / CHOSEN [E: typical construction; real monocles: a 30-38 mm lens in a fine gold or rolled-gold rim, a cord ring on
the rim, a fine cable chain or a silk cord to a button]: the aperture 32 mm (recipe's authored radius 16 mm), the eyewire 0.95 x
1.70 mm (a shade heavier than the glasses': it carries the chain), the lens plano crown glass (ior 1.523) 1.7 mm thick on a 3
dioptre front curve; the cord ring 2.2 mm across its centreline in 0.64 mm wire; the cable chain's links 2.4 x 1.25 mm inside
in 0.45 mm wire (pitch 2.4 mm); the end a 2.8 mm domed stud with a 1.7 mm bail.

    from eidoverse.bestiary.forge.props import monocle
    monocle.forge('work/bestiary/props', octopus='work/bestiary/octopus/octopus.glb')        (GPU: the voxel high + bake)
"""
import numpy as np
import warp as wp

from .. import material as M
from ..mesh import QuadMesh
from . import round_glasses as RG

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})

SPEC = dict(RG.SPEC)               # round_glasses' eyewire / lens functions read these keys
SPEC.update(
    lens_a=0.0320,                 # the aperture: radius 16 mm, recipe.ACCESSORIES['monocle'].authored.radius
    rim_face=0.00095, rim_depth=0.00170, rim_round=0.00025, lip_round=0.00012, rim_bulge=0.00006,
    groove_d=0.00030, groove_w=0.00070,
    lens_t=0.0017, lens_base=3.0, lens_ior=1.523, bevel=115.0,
    ring_R=0.0011, ring_r=0.00032, ring_sink=0.00022,      # the cord ring: centreline radius, wire radius, how far its top
    #                                                         sits in the rim's outer face
    link_d=0.00045, link_L=0.0024, link_W=0.00125,          # the cable chain's link: wire, inside length and width (a
    #                                                         chain ~5 cm long as worn: ~45 links of 140 triangles)
    stud_r=0.0014, stud_h=0.0008, bail_R=0.00085, bail_r=0.00030, bail_sink=0.00015,
)
# the low's regions in round_glasses' numbering (its finish_at reads them): 0 the eyewire (scratches round the rim, wear on its
# outer face below the lens, grime at the glass), 2 the ring and the stud (a lug's: rubbed on its convex edges), 4 the chain's
# wire (a temple's: scratches along it), 9 the glass
REG_NAMES = {0: 'eyewire', 2: 'ring_stud', 4: 'chain_wire', 9: 'lens'}
PART = ('monocle', 'link', 'end')
OFF = {'monocle': np.zeros(3), 'link': np.array([0.026, -0.024, 0.0]), 'end': np.array([-0.026, -0.024, 0.0])}
LENS_SHARE, LENS_BACK_SHARE = RG.LENS_SHARE, RG.LENS_BACK_SHARE
MATERIAL = dict(RG.MATERIAL)
# three prints, each on one face, where a monocle is held (by its rim, between thumb and finger: at the edge), the left half's
# (x > 0) then the right half's (round_glasses' kernel reads a lens's prints by the half the point lies in) [E]
MATERIAL.update(prints=(((10.5, -7.5, 40.0, 6.5, 0.80, 0.25, 0.85), (8.0, 10.0, -55.0, 5.5, 0.82, 0.30, -0.5),
                         (13.0, 2.0, 85.0, 5.0, 0.78, 0.22, 0.0)),
                        ((-10.0, -8.5, -35.0, 6.5, 0.80, 0.28, 0.0), (-11.5, 6.5, 60.0, 5.5, 0.84, 0.22, 0.7),
                         (-4.0, -13.0, 95.0, 5.0, 0.76, 0.30, -0.45))), seed=61)
# (B10c) THE KEPT GILDED GOLD (kept_finish, after the shared kernel): B10b's metal was the glasses' rolled gold over nickel silver,
# rubbed through on its exposed faces, tarnished at the wear's edge and grimed (31 % of the frame's texels over 0.2 grime, the whole
# inner face of the eyewire at the glass): in the grey studio it read as old rolled gold or brass (the B10b check: S 0.40, V 0.38
# against a gilded monocle's 0.67 / 0.80). A monocle kept in a waistcoat pocket and wiped: the gilding is fine gold (linear F0,
# physicallybased.info, as round_glasses' MATERIAL cites it) over BRASS (the reference, a modern gilded brass monocle: brass's F0
# from the same table), worn through only where the shared pass wore it fully (its masks G past wear_from, at most wear_max toward
# the brass), no tarnish band, `dirt` of the shared pass's grime (what stays lies in the groove's crevice), polished (rough), the
# micro-scratches kept: their grooves in the normal map and their roughness streaks (scratch_rough) [E]
MATERIAL.update(kept=dict(gold=(1.0, 0.773, 0.307), base=(0.887, 0.789, 0.434), grime=(0.20, 0.14, 0.06), dirt=0.25,
                          wear_from=0.55, wear_max=0.6, rough=0.10, scratch_rough=0.08, base_rough=0.20, grime_rough=0.55))


def dims(spec=SPEC):
    r_a = 0.5 * spec['lens_a']
    r_o = r_a + spec['rim_face']
    y_ring = -r_o + spec['ring_sink'] - spec['ring_R'] - spec['ring_r']        # the cord ring's centre (its top in the rim)
    y_bail = spec['stud_h'] + spec['bail_R'] + spec['bail_r'] - spec['bail_sink']
    return dict(r_a=r_a, r_o=r_o, r_c=r_a + 0.5 * spec['rim_face'], ring=np.array([0.0, y_ring, 0.0]),
                attach=np.array([0.0, y_ring - spec['ring_R'], 0.0]), bail=np.array([0.0, y_bail, 0.0]),
                end_attach=np.array([0.0, y_bail + spec['bail_R'], 0.0]))


def circle(c, rad, n, phase=0.0):
    a = phase + 2.0 * np.pi * np.arange(n) / n
    return np.column_stack([c[0] + rad * np.cos(a), c[1] + rad * np.sin(a)])


STUD_TOP = np.radians(70.0)        # the low's last ring on the dome (its grid cap lifted onto the dome above it)


def stud_dome(spec, rho):
    """the stud's dome height at radius rho: a quarter ellipse from the collar (0.3 h) to the crown (h)"""
    r, h = spec['stud_r'], spec['stud_h']
    return 0.3 * h + 0.7 * h * np.sqrt(np.clip(1.0 - (np.asarray(rho) / r) ** 2, 0.0, 1.0))


def stud_profile(spec=SPEC, n=7, low=False):
    """the stud as a (rho, zeta) polygon about its +Y (zeta up from the skin): a flat base, a short collar, a dome; closed on
    the axis for the block-out, or (low) from the base's ring to the dome's ring at STUD_TOP, both capped by the low"""
    r, h = spec['stud_r'], spec['stud_h']
    a = np.linspace(0.0, STUD_TOP if low else 0.5 * np.pi, n)
    dome = np.column_stack([r * np.cos(a), 0.3 * h + 0.7 * h * np.sin(a)])
    body = np.vstack([[[r * 0.97, 0.0], [r, 0.04 * h]], dome])
    return body if low else np.vstack([[[0.0, 0.0]], body[:-1], [[0.0, h]]])


# ----------------------------------------------------------------------------------------------------- block-out
def build_sdf(spec=SPEC, lens=False):
    """the block-out in the bake's space (the link and the end beside the monocle at OFF): the eyewire (REVOLVE) with the
    cord ring blended into it (0.2 mm: the solder), the link a torus stretched to its oval (two tori and two rods), the stud
    (REVOLVE) and its bail (a torus, blended 0.15 mm). lens: the glass too (previews; the bake leaves it out)"""
    from .. import sdf
    d = dims(spec)
    prog = sdf.Program()
    prog.revolve(RG.rim_profile(spec), OFF['monocle'], [0.0, 0.0, 1.0], name='eyewire')
    prog.torus(OFF['monocle'] + d['ring'], [1.0, 0.0, 0.0], spec['ring_R'], spec['ring_r'], k=0.0002, name='cord ring')
    # the link: a round wire SWEPT along its stadium centreline in the XY plane (long axis X; dense, closed on itself)
    hx = 0.5 * (spec['link_L'] - spec['link_W'])
    Rc = 0.5 * (spec['link_W'] + spec['link_d'])
    a = np.linspace(-0.5 * np.pi, 0.5 * np.pi, 33)
    st = np.linspace(-hx, hx, 9)[1:-1]
    P2 = np.vstack([np.column_stack([hx + Rc * np.cos(a), Rc * np.sin(a)]), np.column_stack([st[::-1], np.full(len(st), Rc)]),
                    np.column_stack([-hx - Rc * np.cos(a), -Rc * np.sin(a)]), np.column_stack([st, np.full(len(st), -Rc)]),
                    [[hx, -Rc]]])
    Pl = np.column_stack([P2, np.zeros(len(P2))]) + OFF['link']
    prog.sweep(Pl, np.tile([0.0, 0.0, 1.0], (len(Pl), 1)), 0.5 * spec['link_d'], name='link')
    prog.revolve(stud_profile(spec), OFF['end'], [0.0, 1.0, 0.0], name='stud')
    prog.torus(OFF['end'] + d['bail'], [1.0, 0.0, 0.0], spec['bail_R'], spec['bail_r'], k=0.00015, name='bail')
    if lens:
        prog.revolve(RG.lens_profile(spec), OFF['monocle'], [0.0, 0.0, 1.0], name='lens')
    return prog


def bounds(spec=SPEC, pad=0.002):
    d = dims(spec)
    lo = np.array([OFF['end'][0] - spec['stud_r'], d['ring'][1] - spec['ring_R'] - spec['ring_r'], -0.003]) - pad
    lo[1] = min(lo[1], OFF['link'][1] - 0.002 - pad)
    hi = np.array([OFF['link'][0] + 0.003, d['r_o'] + 0.0005, 0.003]) + pad
    return lo, hi


# ----------------------------------------------------------------------------------------------------------- low
def _torus_piece(c, axis, e1, R, r, K, n_sect, region, part, share=1.0):
    """a ring's low: a circle of n_sect points (radius r at R from the axis; closed: its first point again at the end, the
    seam on the ring's inside) revolved K round `axis` through c"""
    prof = circle([R, 0.0], r, n_sect, phase=np.pi)
    prof = np.vstack([prof, prof[:1]])
    return RG.revolve_piece(prof, np.asarray(c, np.float64), axis, K, e1=e1, region_of=lambda j: region, phi0=np.pi / K,
                            part=float(part), cuts=[K // 2], share=share)


def _link_piece(spec, c, K=5, n_arc=6):
    """the cable chain's link as a WIRE: round_glasses.ring_tube along its stadium centreline in the XY plane (long axis X:
    two half circles of radius (W + d) / 2 joined by straights; the first station again at the end), K round its wire, its
    UVs unrolled along the wire's true length"""
    hx = 0.5 * (spec['link_L'] - spec['link_W'])
    Rc = 0.5 * (spec['link_W'] + spec['link_d'])
    a = np.linspace(-0.5 * np.pi, 0.5 * np.pi, n_arc + 1)
    right = np.column_stack([hx + Rc * np.cos(a), Rc * np.sin(a)])
    left = np.column_stack([-hx - Rc * np.cos(a), -Rc * np.sin(a)])
    P2 = np.vstack([right, left, right[:1]])
    P = np.column_stack([P2, np.zeros(len(P2))]) + c
    N = np.tile([0.0, 0.0, 1.0], (len(P), 1))
    V, Q, attr, isl = RG.ring_tube(P, N, lambda i, th: 0.5 * spec['link_d'], K, theta0=0.0, part=4.0, cut_len=0.01)
    return V, Q, np.full(len(Q), 4), attr, isl


def weld_normals(L, tol=1e-9):
    """the export's normals averaged over coincident vertices (a closed profile's seam, a wire's closing station: the low
    keeps them apart so their attributes run on, their shading must not crease) and the tangents rebuilt"""
    from .. import bake
    key = np.round(L['V'] / tol).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    acc = np.zeros((inv.max() + 1, 3))
    np.add.at(acc, inv, L['N'])
    N = acc[inv]
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)
    L['N'], L['TAN'] = bake.low_frames(L['V'], L['F'], L['UV'], N)
    return L


def build_low(spec=SPEC, log=print):
    """the designed low: the eyewire, the lens, the cord ring (the monocle), the link and the end (the stud and its bail),
    in the bake's space. Returns round_glasses' low dict (V, Q (welded), region, attr, W, side, bake, split) plus 'part'
    per quad (PART's index)"""
    d = dims(spec)
    r_a, r_o, h = d['r_a'], d['r_o'], 0.5 * spec['rim_depth']
    rc, rl = spec['rim_round'], spec['lip_round']
    c45 = np.cos(np.pi / 4)
    pieces = []
    # ---- the eyewire: the glasses' D section at its corners (10 points), 56 round, cut in quarters
    sect = np.array([[r_a, 0.0], [r_a, h - rl], [r_a + rl - rl * c45, h - rl + rl * c45], [r_o - rc, h],
                     [r_o - rc + rc * c45, h - rc + rc * c45], [r_o + spec['rim_bulge'], 0.0],
                     [r_o - rc + rc * c45, -(h - rc + rc * c45)], [r_o - rc, -h],
                     [r_a + rl - rl * c45, -(h - rl + rl * c45)], [r_a, -(h - rl)]])
    sect = np.vstack([sect, sect[:1]])
    Kr = 56
    V, Q, reg, attr, isl = RG.revolve_piece(sect[::-1], OFF['monocle'].copy(), [0.0, 0.0, 1.0], Kr, e1=[1.0, 0.0, 0.0],
                                            phi0=-0.5 * np.pi, cuts=[14, 28, 42], region_of=lambda j: 0, part=0.0)
    pieces.append(('eyewire', 'monocle', V, Q, reg, attr, isl, True))
    # ---- the lens (the glasses' construction): its bevel band, grid caps lifted onto the faces' spheres
    g = RG.lens_geom(spec)
    lp = np.array([[g['rho_b'], RG.lens_back(spec, g['rho_b'])], [g['rho_e'], 0.0], [g['rho_b'], RG.lens_front(spec, g['rho_b'])]])
    V, Q, reg, attr, isl = RG.revolve_piece(lp, OFF['monocle'].copy(), [0.0, 0.0, 1.0], 32, e1=[1.0, 0.0, 0.0], cap0=True,
                                            cap1=True, region_of=lambda j: 9, part=9.0, share=LENS_SHARE, cuts=[8, 16, 24])
    isl[4]['share'] = LENS_BACK_SHARE                              # the inner face's cap (cap0: lp starts at the back)
    rr = np.hypot(V[:, 0], V[:, 1])
    fr = V[:, 2] > 0.0
    inner = rr < g['rho_b'] - 1e-7
    V[inner & fr, 2] = RG.lens_front(spec, rr[inner & fr])
    V[inner & ~fr, 2] = RG.lens_back(spec, rr[inner & ~fr])
    # (in the paint set as the glasses' left lens is: the bake leaves region 9 out, the material paints it unbaked)
    pieces.append(('lens', 'monocle', V, Q, reg, attr, isl, True))
    # ---- the cord ring: 16 round, 8 round its wire, its axis +X (it hangs in the YZ plane)
    V, Q, reg, attr, isl = _torus_piece(OFF['monocle'] + d['ring'], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], spec['ring_R'],
                                        spec['ring_r'], 16, 8, 2, 2)
    pieces.append(('ring', 'monocle', V, Q, reg, attr, isl, True))
    # ---- the link: a wire round its oval (long axis X), 14 stations, 5 round
    V, Q, reg, attr, isl = _link_piece(spec, OFF['link'])
    pieces.append(('link', 'link', V, Q, reg, attr, isl, True))
    # ---- the end: the stud (16 round, a grid cap on its dome lifted onto the dome, a flat one under its base) and its bail
    # (12 round, 6 round its wire)
    V, Q, reg, attr, isl = RG.revolve_piece(stud_profile(spec, low=True), OFF['end'].copy(), [0.0, 1.0, 0.0], 16,
                                            e1=[1.0, 0.0, 0.0], cap0=True, cap1=True, region_of=lambda j: 2, part=3.0, cuts=[8])
    q_ = V - OFF['end']
    rr = np.hypot(q_[:, 0], q_[:, 2])
    top = (q_[:, 1] > 0.5 * spec['stud_h']) & (rr < spec['stud_r'] * np.cos(STUD_TOP) - 1e-9)
    V[top, 1] = OFF['end'][1] + stud_dome(spec, rr[top])
    pieces.append(('stud', 'end', V, Q, reg, attr, isl, True))
    V, Q, reg, attr, isl = _torus_piece(OFF['end'] + d['bail'], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], spec['bail_R'],
                                        spec['bail_r'], 12, 6, 4, 5)
    pieces.append(('bail', 'end', V, Q, reg, attr, isl, True))
    # ---- assemble (round_glasses.build_low's split layout; no mirror, no skin: W is one column of ones)
    Vs, Qs, R, A, Ws, S, Bk, P = [], [], [], [], [], [], [], []
    split = dict(Q=[], orig=[], UV=[], island=[], wq=[], share=[], groups=[])
    cnt = dict(v=0, q=0, s=0, isl=0)
    for nm, part, V, Q, reg, attr, isl, bake in pieces:
        Vs.append(V)
        Qs.append(Q + cnt['v'])
        R.append(np.broadcast_to(np.asarray(reg, np.int64), (len(Q),)).copy())
        A.append(attr)
        Ws.append(np.ones((len(V), 1)))
        S.append(np.ones(len(Q), np.int64))
        Bk.append(np.full(len(Q), bake))
        P.append(np.full(len(Q), PART.index(part)))
        for it in isl:
            split['share'].append(it['share'])
            split['Q'].append(it['Q'] + cnt['s'])
            split['orig'].append(it['orig'] + cnt['v'])
            split['UV'].append(it['UV'])
            split['island'].append(np.full(len(it['Q']), cnt['isl']))
            split['wq'].append(it['quads'] + cnt['q'])
            split['groups'].append((cnt['isl'], cnt['s'], len(it['orig'])))
            cnt['isl'] += 1
            cnt['s'] += len(it['orig'])
        cnt['v'] += len(V)
        cnt['q'] += len(Q)
    low = dict(V=np.concatenate(Vs), Q=np.concatenate(Qs), region=np.concatenate(R), attr=np.concatenate(A),
               W=np.concatenate(Ws), side=np.concatenate(S), bake=np.concatenate(Bk), part=np.concatenate(P),
               names=[p[0] for p in pieces],
               split=dict(Q=np.concatenate(split['Q']), orig=np.concatenate(split['orig']),
                          UV=np.concatenate(split['UV']), island=np.concatenate(split['island']),
                          wq=np.concatenate(split['wq']), share=np.asarray(split['share']), groups=split['groups']))
    chk = QuadMesh(low['V'], low['Q']).check()
    log(f'[monocle] low: {len(low["V"])} verts, {len(low["Q"])} quads ({2 * len(low["Q"])} tris) in {len(pieces)} pieces: '
        + ', '.join(f'{p[0]} {2 * len(p[3])}' for p in pieces) + f' tris; check {chk}')
    return low


# ------------------------------------------------------------------------------------------------- material pass
def _smooth(e0, e1, x):
    t = np.clip((np.asarray(x, np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def kept_finish(alb, orm, msk, cov, recipe=MATERIAL):
    """(B10c) THE KEPT GILDED GOLD over the shared kernel's metal texels (covered, masks B 0 or 1/3: the eyewire, the cord ring, the
    stud and the chain's wire), read from that pass's own masks (G worn through, R grime, A micro-scratch density) per texel:
    albedo the gold over the brass by the kept wear, then the grime's thin share; metalness 1 - 0.9 x the grime; roughness the
    kept law with the same widening the kernel gave each texel from its normals' spread (Toksvig: the kernel's output^4 less its
    own law's^4, re-read from the same masks); the masks rewritten to what the texel now shows (R the grime, G the wear, B the
    zone). The glass (B 1) is left as it is. Linear arrays in, the same out"""
    k = recipe.get('kept')
    if not k:
        return alb, orm, msk
    fr = cov & (msk[..., 2] * 3.0 < 1.5)
    w0, d0, s0 = msk[fr, 1].astype(np.float64), msk[fr, 0].astype(np.float64), msk[fr, 3].astype(np.float64)
    w = k['wear_max'] * _smooth(k['wear_from'], 1.0, w0)
    d = k['dirt'] * d0
    col = np.outer(1.0 - w, k['gold']) + np.outer(w, k['base'])
    col = col * (1.0 - 0.85 * d)[:, None] + np.outer(0.85 * d, k['grime'])
    t0 = 4.0 * w0 * (1.0 - w0)
    r_old = recipe['gold_rough'] + recipe['scratch_rough'] * s0 + (recipe['nickel_rough'] - recipe['gold_rough']) * w0 + 0.18 * t0
    r_old = np.clip(r_old + (0.75 - r_old) * d0, 0.03, 1.0)
    var = np.clip(orm[fr, 1].astype(np.float64) ** 4 - r_old ** 4, 0.0, 1.0)
    r_new = k['rough'] + k['scratch_rough'] * s0 + (k['base_rough'] - k['rough']) * w
    r_new = np.clip(r_new + (k['grime_rough'] - r_new) * d, 0.03, 1.0)
    alb, orm, msk = alb.copy(), orm.copy(), msk.copy()
    alb[fr] = col
    orm[fr, 1] = np.clip((r_new ** 4 + var) ** 0.25, 0.0, 1.0)
    orm[fr, 2] = 1.0 - 0.9 * d
    msk[fr, 0], msk[fr, 1], msk[fr, 2] = d, w, w / 3.0
    return alb, orm, msk


def run_material(L, drivers, size, texel, spec=SPEC, ss=2, recipe=MATERIAL, log=print):
    """round_glasses' material kernel (k_glasses) over this prop's set: the bake's drivers on the metal, the lens unbaked.
    Its arrays (round_glasses.run_material's) carry the monocle's geometry: G3 the lens centre (the hinge, the pad and the bridge
    far away: no region here reads them), S the aperture and bevel radii, the rim's centre radius, the prints' ridge period (the
    temple's bend and the coil set out of reach: the chain's wire scratches along itself, unworn but by its convex edges).
    Returns round_glasses' maps (albedo sRGB, normal GL, ORM, masks, palette_base, coverage)"""
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
    g = RG.lens_geom(spec)
    far = np.array([9.0, 9.0, 9.0])
    C = wp.array(np.array([recipe['gold'], recipe['nickel'], recipe['tarnish'], recipe['ivory'], recipe['grime'],
                           recipe['glass']], np.float32), dtype=wp.vec3)
    R = wp.array(np.array([recipe['gold_rough'], recipe['nickel_rough'], recipe['ivory_rough'], recipe['glass_rough'],
                           recipe['print_rough'], recipe['scratch_rough']], np.float32), dtype=wp.float32)
    G3 = wp.array(np.array([OFF['monocle'], far, far, [0.0, -1.0, 0.0], [0.0, 1.0, 0.0]], np.float32), dtype=wp.vec3)
    S = wp.array(np.array([1.0e3, 0.0, 1.0e3, 1.0, 0.0, 0.0, d['r_a'], g['rho_b'], d['r_c'], 0.001, 0.001, 0.001, 0.0001,
                           recipe['print_ridge'], 0.001, 0.0005, 0.00004], np.float32), dtype=wp.float32)
    pr = []
    for k, lens in enumerate(recipe['prints']):
        for i, (x, y, ang, semi, asp, core, strength) in enumerate(lens):
            pr += [[0.001 * x, 0.001 * y, np.radians(ang), 0.001 * semi], [asp, core, strength, 1.0 + 3 * k + i]]
    PR = wp.array(np.array(pr, np.float32), dtype=wp.vec4)
    n = size * size
    o_alb, o_nrm, o_orm = (wp.zeros(n, dtype=wp.vec3) for _ in range(3))
    o_mask = wp.zeros(n, dtype=wp.vec4)
    o_cov = wp.zeros(n, dtype=wp.float32)
    wp.launch(RG.k_glasses, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
                                           wp.array(np.asarray(L['region'][sel], np.int32), dtype=wp.int32), D['normal'],
                                           D['ao'], D['cavity'], D['ao_local'], D['conv'], D['position'], C, R, G3, S, PR,
                                           float(texel), int(recipe['seed']), o_alb, o_nrm, o_orm, o_mask, o_cov])
    wp.synchronize()
    img = lambda a, k: np.asarray(a.numpy()).reshape(size, size, k)[::-1]            # noqa: E731
    alb, nrm, orm, msk = img(o_alb, 3), img(o_nrm, 3), img(o_orm, 3), img(o_mask, 4)
    cov = img(o_cov, 1)[..., 0] > 0
    alb, orm, msk = kept_finish(alb, orm, msk, cov, recipe)              # (B10c) the kept gilded gold over the metal
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
    log(f'[monocle] material {size}^2 x ss {ss}: {time.time() - t0:.1f}s; coverage {cov.mean() * 100:.1f} %; palette base '
        f'(linear) ' + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in pal.items()))
    return out


# ------------------------------------------------------------------------------------------------------ fit data
def fit_data(spec=SPEC, conform=None):
    """what accessories.js wear() (the 'monocle' archetype) and remix.js's item contract read, prop space (metres): the lens
    (its aperture radius: a fit's radius over it is the prop's scale), the cord ring's foot where the chain hangs from, the
    chain's link (its pitch, its size) and its end (where the last link hooks, in the end's frame); conform: per species, per
    socket, the fit of a creature whose glb carries none (octopus_conform)"""
    d = dims(spec)
    rnd = lambda a: np.round(np.asarray(a, np.float64), 6).tolist()             # noqa: E731
    out = dict(archetype='monocle', prop='monocle',
               lens=dict(radius=round(d['r_a'], 6), rim_outer=round(d['r_o'], 6), thickness=spec['lens_t'],
                         ior=spec['lens_ior']),
               seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0], left=[1.0, 0.0, 0.0],
                         note='the origin the lens centre; +Z the lens\'s outer face (away from the eye)'),
               eyelet=dict(centre=rnd(d['ring']), attach=rnd(d['attach']), axis=[1.0, 0.0, 0.0], R=spec['ring_R'],
                           r=spec['ring_r'], radii=round(float(-d['attach'][1] / d['r_a']), 4)),
               chain=dict(link='monocle_chain_link', end='monocle_chain_end', pitch=spec['link_L'],
                          link_size=dict(L=spec['link_L'], W=spec['link_W'], d=spec['link_d']),
                          end_attach=rnd(d['end_attach']), end_up=[0.0, 1.0, 0.0]))
    if conform:
        out['conform'] = conform
    return out


def octopus_conform(path, spec=SPEC, slack=1.10, log=print):
    """THE OCTOPUS'S FIT, read from its glb (read only): on each eye socket (socket_eye_L / R: the eye joint's frame, the
    slot's normal its axis) the lens where remix/recipe.py FIT_PROPOSALS seats a monocle on it (3 mm proud of the mound,
    1.15 eyeball radii), turned so the prop's +Y is the world's up made perpendicular to the eye's axis at the bind (the
    proposal's rotation left the eyelet wherever the eye joint's +Y points); the CHAIN's anchor: of the skin vertices held by
    one joint (weight >= 0.8; not an eye's) below the eyelet and 1.4-6 lens radii from it, the one whose chain (`slack` x the
    span) clears the skin most at the bind, less a tenth of its distance from a point 1.8 lens radii down and 1.6 back of the
    eyelet (the head or the mantle's collar only). Returns {'socket_eye_L': fit, ...}"""
    from .. import gltf as GLT
    from ..species.human_seats import MeshSDF
    from ...remix import recipe as RC
    G = GLT.read(path)
    j, acc = G['json'], G['accessor']
    names = [n.get('name') for n in j['nodes']]
    sk = j['skins'][0]
    jn = [j['nodes'][i].get('name') for i in sk['joints']]
    IBM = acc(sk['inverseBindMatrices']).astype(np.float64).reshape(-1, 4, 4).transpose(0, 2, 1)
    Wb = {jn[i]: np.linalg.inv(IBM[i]) for i in range(len(jn))}
    # the skin at the bind: every skinned primitive's drawn triangles, and each vertex's heaviest joint and weight
    Vs, Fs, Js, Ww, off = [], [], [], [], 0
    for m in j['meshes']:
        for pr in m['primitives']:
            a = pr['attributes']
            if 'JOINTS_0' not in a or pr.get('mode', 4) != 4:
                continue
            V = acc(a['POSITION']).astype(np.float64)
            J4 = acc(a['JOINTS_0']).astype(np.int64)
            W4 = acc(a['WEIGHTS_0']).astype(np.float64)
            F = acc(pr['indices']).astype(np.int64).reshape(-1, 3)
            k = np.argmax(W4, axis=1)
            Vs.append(V)
            Fs.append(F + off)
            Js.append(J4[np.arange(len(J4)), k])
            Ww.append(W4[np.arange(len(W4)), k])
            off += len(V)
    V, F, Jv, Wv = np.concatenate(Vs), np.concatenate(Fs), np.concatenate(Js), np.concatenate(Ww)
    skin = MeshSDF(V, F, device='cpu')
    used = np.zeros(len(V), bool)
    used[F.ravel()] = True
    # the anchor's candidates: skin vertices held by the HEAD or the mantle's collar (weight >= 0.8: the point rides that joint;
    # left free, the search fixed the left chain on the funnel)
    hold = [jn.index(n) for n in ('head', 'mantle_0') if n in jn]
    cand = np.nonzero(used & (Wv >= 0.8) & np.isin(Jv, hold))[0]
    prop = RC.FIT_PROPOSALS['octopus']['monocle']
    d = dims(spec)
    up = np.array([0.0, 1.0, 0.0])
    out = {}
    for s, sg in (('L', 1.0), ('R', -1.0)):
        sock = f'socket_eye_{s}'
        node = j['nodes'][names.index(sock)]
        jname = node['extras']['slot']['joint']
        Wj = Wb[jname].copy()
        Wj[:3, 3] = Wj[:3, :3] @ np.asarray(node.get('translation', [0.0, 0.0, 0.0])) + Wj[:3, 3]
        Rj = Wj[:3, :3]
        axw = RG._unit(Rj @ np.asarray(node['extras']['slot']['frame']['normal'], np.float64))
        # (the proposal is the left eye's: its offset lies along the slot's normal, +X of the eye joint, which both eyes'
        # slots share, so the right eye takes the same offset in its own joint's frame)
        lens = Rj @ np.asarray(prop['offset'], np.float64) + Wj[:3, 3]
        upp = RG._unit(up - axw * (up @ axw))
        Rm = np.column_stack([np.cross(upp, axw), upp, axw])          # the prop's axes in the world
        radius = float(prop['radius'])
        k = radius / d['r_a']
        eyelet = lens + Rm @ (d['attach'] * k)
        tgt = eyelet + np.array([-sg * 0.25 * radius, -1.8 * radius, -1.6 * radius])     # down, back (-Z), a little in
        # the anchor: among the head's vertices below the eyelet and 1.6-4 lens radii from it, the one whose chain clears the
        # skin most at the bind (its middle: the ends lie on the skin), less a tenth of its distance from the target (the
        # vertex nearest the target alone hung the chain 2.9 mm into the head's bulge between the eye and it)
        dv = V[cand] - eyelet
        dist = np.linalg.norm(dv, axis=1)
        cc = cand[(dist > 1.4 * radius) & (dist < 6.0 * radius) & (dv[:, 1] < -0.3 * radius)]
        if len(cc) > 800:
            cc = np.random.default_rng(3).choice(cc, 800, replace=False)
        # (each chain sampled every half pitch as worn, its ends' 2.5 pitches left out: there it reaches the eyelet and the skin)
        def mid_pts(i, n=48):
            Lc = slack * float(np.linalg.norm(V[i] - eyelet))
            P_ = catenary(eyelet, V[i], Lc, n=n)
            sarc = np.linspace(0.0, Lc, n)
            e_ = 2.5 * spec['link_L'] * k
            return P_[(sarc > e_) & (sarc < Lc - e_)][:max(1, n - 2)] if Lc > 2.2 * e_ else P_[n // 2:n // 2 + 1]
        mids = [mid_pts(i) for i in cc]
        sd_ = skin.eval(np.concatenate(mids))
        clr_all = np.array([float(x.min()) for x in np.split(sd_, np.cumsum([len(m_) for m_ in mids])[:-1])])
        # (those whose chain clears by its half-width as worn and 0.3 mm more first; nearest the target among them)
        need = (0.5 * spec['link_W'] + spec['link_d']) * k + 0.0003
        score = np.where(clr_all >= need, 1.0, 0.0) * 10.0 + clr_all - 0.1 * np.linalg.norm(V[cc] - tgt, axis=1)
        i = cc[int(np.argmax(score))]
        anchor = V[i]
        _, _, _, cp, face, u, v = skin._closest(anchor[None])
        nrm = skin.normals(cp)[0]
        span = float(np.linalg.norm(anchor - eyelet))
        clr = float(skin.eval(mid_pts(i, 96)).min())
        aj = jn[int(Jv[i])]
        Wh = Wb[aj]
        out[sock] = dict(offset=np.round(Rj.T @ (lens - Wj[:3, 3]), 6).tolist(),
                         rotation=[float(x) for x in GLT.quat_from_matrix(Rj.T @ Rm)], radius=round(radius, 6),
                         chain=dict(joint=aj, point=np.round(Wh[:3, :3].T @ (anchor - Wh[:3, 3]), 6).tolist(),
                                    normal=np.round(Wh[:3, :3].T @ nrm, 5).tolist(), slack=slack, span=round(span, 6),
                                    clearance=round(clr, 6), weight=round(float(Wv[i]), 4)),
                         source='forge/props/monocle.py octopus_conform: remix/recipe.py FIT_PROPOSALS octopus monocle (3 mm '
                                'proud of the mound, 1.15 eyeball radii), the prop\'s +Y the world\'s up; the chain to the head')
        log(f'[monocle] octopus {sock}: lens {np.round(lens * 1000, 1).tolist()} mm (skin {float(skin.eval(lens[None])[0]) * 1000:+.2f}), '
            f'axis {np.round(axw, 3).tolist()}, radius {radius * 1000:.1f} mm (scale {k:.4f}); eyelet {np.round(eyelet * 1000, 1).tolist()} '
            f'(skin {float(skin.eval(eyelet[None])[0]) * 1000:+.2f}; {len(cc)} candidates, best clearance {clr_all.max() * 1000:+.2f}) -> the skin '
            f'{np.round(anchor * 1000, 1).tolist()} on {aj} (weight {Wv[i]:.2f}), span {span * 1000:.1f} mm; the catenary clears the '
            f'skin by {clr * 1000:+.2f} mm at the bind')
    return out


def catenary(p0, p1, L, n=64, up=(0.0, 1.0, 0.0)):
    """n points at equal arc length along a chain of length L hung between p0 and p1 under -up (accessories.js's
    monocleChain is its twin; b10/r01_rig.py's catenary the beetle's gate's)"""
    up = np.asarray(up, np.float64)
    d = np.asarray(p1, np.float64) - np.asarray(p0, np.float64)
    v = float(d @ up)
    hv = d - v * up
    h = float(np.linalg.norm(hv))
    if L <= np.hypot(h, v) * (1.0 + 1e-9) or h < 1e-12:
        return np.asarray(p0) + np.outer(np.linspace(0.0, 1.0, n), d)
    eh = hv / h
    k = np.sqrt(L * L - v * v)
    lo, hi = h / 1400.0, 1e4 * h
    for _ in range(200):
        a = np.sqrt(lo * hi)
        if 2.0 * a * np.sinh(h / (2.0 * a)) > k:
            lo = a
        else:
            hi = a
    a = np.sqrt(lo * hi)
    x0 = 0.5 * h - a * np.arctanh(v / L)
    c0 = -a * np.cosh(-x0 / a)
    s = a * np.sinh(-x0 / a) + np.linspace(0.0, L, n)
    x = x0 + a * np.arcsinh(s / a)
    y = a * np.cosh((x - x0) / a) + c0
    return np.asarray(p0) + np.outer(x, eh) + np.outer(y, up)


# -------------------------------------------------------------------------------------------------------- export
def _sub(L, sel_tri, shift):
    """a part's own vertex set from the export arrays (its triangles' vertices, renumbered), its positions moved by shift"""
    Fp = L['F'][sel_tri]
    u, inv = np.unique(Fp, return_inverse=True)
    return dict(V=L['V'][u] + shift, N=L['N'][u], TAN=L['TAN'][u], UV=L['UV'][u], F=inv.reshape(-1, 3),
                region=L['region'][sel_tri])


def export_glb(path, L, low, maps, spec=SPEC, conform=None):
    """a static glb: the monocle (the frame's primitive with base, normal, ORM and the masks in KHR_materials_volume's
    thickness slot as the creatures carry theirs; the glass's with KHR_materials_transmission, _ior and _volume) at the
    scene's root with its fit data; the chain's link and end as meshes on nodes outside the scene (their own origins)"""
    from .. import gltf
    g = gltf.GLB()
    t_base = g.texture(maps['albedo'], fmt='jpeg', quality=95)
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='png')
    t_msk = g.texture(maps['masks'], fmt='png')
    chans = ('R grime on the metal / prints and dust on the glass, G plating worn through, B palette zone (0 the plating, '
             '1/3 the base metal, 1 glass), A micro-scratch density')
    m_frame = g.material('monocle', base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='prop', prop='monocle', masks=t_msk, masks_channels=chans, palette_base=maps.get('palette_base', {})))
    m_lens = g.material('monocle_lens', base=t_base, normal=t_nrm, orm=t_orm, extras=dict(
        bestiary='prop', prop='monocle', part='lens', masks=t_msk, masks_channels=chans))
    lens = g.j['materials'][m_lens]
    lens['pbrMetallicRoughness']['metallicFactor'] = 0.0
    lens['extensions'] = {'KHR_materials_transmission': {'transmissionFactor': 1.0},
                          'KHR_materials_ior': {'ior': spec['lens_ior']},
                          'KHR_materials_volume': {'thicknessFactor': spec['lens_t'],
                                                   'attenuationColor': list(MATERIAL['glass']), 'attenuationDistance': 0.03}}
    lens['alphaMode'] = 'OPAQUE'
    g.ext_used.update({'KHR_materials_transmission', 'KHR_materials_ior', 'KHR_materials_volume'})
    sp = low['split']
    part_tri = np.concatenate([low['part'][sp['wq']], low['part'][sp['wq']]])
    fit = fit_data(spec, conform)
    tris = {}
    for pi, nm in enumerate(PART):
        sub = _sub(L, part_tri == pi, -OFF[nm])
        glass = sub['region'] == 9
        prims = [(sub['F'][~glass], m_frame)] + ([(sub['F'][glass], m_lens)] if glass.any() else [])
        mesh = g.mesh(f'monocle_{nm}' if nm != 'monocle' else 'monocle', sub['V'], sub['N'], sub['TAN'], sub['UV'], prims)
        tris[nm] = int(len(sub['F']))
        if nm == 'monocle':
            g.node('monocle', mesh=mesh, root=True, extras=dict(bestiary='prop', fit=fit))
        else:
            g.node(f'monocle_chain_{nm}', mesh=mesh, extras=dict(bestiary='prop', part=f'chain_{nm}',
                                                                  note='outside the scene: accessories.js instances it'))
    return g.save(path, extras=dict(bestiary=dict(prop='monocle', archetype='monocle', units='m', up='+Y', forward='+Z',
                                                  left='+X', triangles=tris, fit=fit))), tris


# --------------------------------------------------------------------------------------------- the whole forge
def forge(out_dir, size=1024, voxel_size=0.00004, band=0.0003, ss=2, seed=7, spec=SPEC, octopus=None, log=print):
    """block-out -> low -> UVs -> voxel high of the metal (GPU) -> bake (GPU) -> material -> glb; returns (the glb's path,
    the bake's gate). octopus: the octopus glb's path, for its conform record"""
    import os
    import time

    from PIL import Image

    from .. import bake, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    conform = dict(octopus=octopus_conform(octopus, spec, log=log)) if octopus else None
    prog = build_sdf(spec)
    low = build_low(spec, log=log)
    uvs = RG.unwrap(low, size, log=log)
    L = weld_normals(RG.low_arrays(low, uvs))
    lo, hi = bounds(spec)
    # faces BURIED in another part (the cord ring's top in the eyewire, the bail's foot in the stud) are hidden: left out of the
    # bake and the paint, their texels dilate from their neighbours (round_glasses.forge's rule: buried = inside the block-out
    # and the way out along the face's own normal long)
    cen = L['V'][L['F']].mean(1)
    fnm = np.cross(L['V'][L['F'][:, 1]] - L['V'][L['F'][:, 0]], L['V'][L['F'][:, 2]] - L['V'][L['F'][:, 0]])
    fnm /= np.maximum(np.linalg.norm(fnm, axis=1, keepdims=True), 1e-20)
    pex, _ = prog.project(cen, fnm, maxd=0.003)
    buried = (prog.eval(cen) < -0.00003) & (np.linalg.norm(pex - cen, axis=1) > 0.00012) & (L['region'] != 9) & L['bake']
    L['bake'] = L['bake'] & ~buried
    log(f'[monocle] {int(buried.sum())} of the bake set\'s triangles buried in another part (not baked: their texels dilate)')
    sel = L['bake'] & (L['region'] != 9)
    G = voxel.SparseSDF(prog, lo, hi, voxel=voxel_size, band=band, log=log)
    res = bake.bake(G, L['V'], L['F'][sel], L['UV'], L['N'], L['TAN'], L['region'][sel], size=size, ss=ss,
                    cage=0.0006, ao_r=0.004, cav_r=0.0006, n_ao=96, n_cav=48, n_thk=2, thk_max=0.003, cage_min=0.00003,
                    reach_margin=0.0002, far_max=0.0003, proj_tol=2.0e-5, seed=seed, region_names=REG_NAMES, log=log)
    keep_ = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
             if k != 'position'}
    np.savez_compressed(os.path.join(out_dir, 'drivers_monocle.npz'), **keep_)
    maps = run_material(L, res, size, 1.0 / L['px_per_m'], spec, ss=ss, log=log)
    for k in ('albedo', 'normal', 'orm', 'masks'):
        Image.fromarray(maps[k]).save(os.path.join(out_dir, f'T_monocle_{k}.png'))
    path = os.path.join(out_dir, 'monocle.glb')
    nbytes, tris = export_glb(path, L, low, maps, spec, conform)
    log(f'[monocle] wrote {path} ({nbytes / 1e6:.2f} MB; triangles {tris}) in {time.time() - t0:.0f}s')
    return path, res.get('gate')
