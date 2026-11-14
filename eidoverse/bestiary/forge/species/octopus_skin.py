"""The octopus's MATERIAL PASS (research/SD_SKIN_BRIEF.md R1 + R1b): the texture tier and the colour stack, per
texel from the bake's drivers, on the GPU. Runs in seconds, so the look iterates without re-baking.

Per sub-sample (ss x ss per texel): the low under it (material.low_at), its point on the unsculpted block-out (the
bake's BASE offset along the normal) and on the high (the bake's HEIGHT), then:
  * arm or not: the nearest arm by azimuth, rotated onto the reference arm, the nearest centreline point (on the head
    set the sweep's own foot point, polish 1); inside 1.15 x the local radius it is ARM skin with its (s, alpha)
    (alpha from the aboral side toward +b);
  * the anatomical coordinate q: the point itself (head, mantle, webs) or arm_coord(s, alpha) (arms; the straightened,
    radius-normalised coordinate the sculpt planned its arm papillae in);
  * HEIGHT (metres): skin patches and their grooves (proc.cellular3 on the SAME network as the papillae: they sit at
    the patch centres), a crevice grain, transverse arm wrinkles, the suckers' radial cuticle grooves and rim folds;
    every band-limited feature fades below ~2.5 texels;
  * the NORMAL: the baked tangent normal to world, tilted by the height's surface gradient (from the two neighbouring
    sub-sample positions, material.surface_grad), back to the tangent frame;
  * COLOUR (linear): desaturated warm browns (brief §2.1 spectra) mottled per patch, pale grooves, lighter papilla
    tips, the pale oral side, cream sucker discs with greyish-pink cups, cavity darkening; ROUGHNESS wet (0.25-0.4);
    MASKS for the runtime: thinness (subsurface), ventralness, sucker parts, the patch random;
  * GROWTHS (work/bestiary/patches/material_ids_v2.md): the bake's packed material ids per texel; where a growth id
    holds a share f, the skin result blends toward that family's surface (growth.growth_texel), the skin's texture
    tier and display masks fade by f, metalness goes into the ORM's B, and the GROWTH pack (R the id mask, G
    iridescence, B emissive mask, A pulse phase) carries the runtime's view-dependent terms. The VEIN families (ember,
    arc) are painted here along a coarse cellular network (no strokes, no voxel ids). Round each root the skin answers
    (growth.growth_halo, work/bestiary/patches/halo_v2.md): the family's element infusion as a local halo written into
    the skin's own channels (its albedo's chroma and L spread, the ORM's B, the thin mask), so the runtime's skin terms
    act on it; the pack's R stays the growth share.
"""
import numpy as np
import warp as wp

from .. import growth as GR
from .. import material as M
from .. import proc

# forward-only kernels: no adjoint code, and the cellular noises' 3 x 3 x 3 neighbour loops left rolled (k_skin inlines
# skin_at three times, each with several cellular3 calls; generated with adjoints and 27-way unrolls it took ~14 min to
# compile, t11 10-20)
wp.set_module_options({'enable_backward': False, 'max_unroll': 1})


@wp.struct
class Skin:
    h: float
    groove: float
    prand: float
    mottle: float
    ventral: float
    aboral: float
    arm: float
    armw: float          # a soft arm weight (1 on the arm's tube, 0 past 1.6 r): colour splits by arm with no line
    disc: float
    rim: float
    cup: float
    stalk: float
    # the PAINT passes (structure places, noise only shapes the edge; craft guide 10.14, 10.22)
    midline: float       # the aboral midline's denser pigment (arms)
    band: float          # broken transverse arm bands
    blotch: float        # bilaterally symmetric dark blotches (mantle, head, webs)
    eyering: float       # the darker ring round each eye
    spots: float         # the leucophore white spots (a display mask: shown by the runtime, not baked into colour)
    chrom: float         # dark chromatophore clusters, one off the centre of most skin patches
    # the reference study's layers (research/REF_SKIN_STUDY.md §9-§10a)
    oct: float           # the albedo's own mottling, ln L octaves 2-128 mm (R6)
    speck: float         # chromatophore specks, ln L, light and dark (R6)
    rnoise: float        # roughness's flat-octave noise (R5)
    lip: float           # the mouth's lip (prog.mouth)
    lining: float        # the mouth's lining, inside the opening
    funnel: float        # the funnel's skin (smooth: no patch network)
    vein: float          # the VEIN families' crust (growth.vein_texel), 0 without a vein family
    vcore: float         # the vein's glowing centre line
    vrand: float         # the vein cell's random (the pulse's phase, cell by cell)
    tile: float          # the patch relief about its median (crown +, groove -; x the relief fade): the halo's L spread


@wp.func
def soft_spot(p: wp.vec3, c: wp.vec3, r: float, edge: float, n: float):
    """a painted spot: distance from its centre, its edge wandered by signed noise, then a narrow threshold"""
    d = wp.length(p - c) / r + edge * (n - 0.5)
    return 1.0 - proc.smoothstep(0.85, 1.0, d)


@wp.func
def rot_y(p: wp.vec3, phi: float):
    c = wp.cos(phi)
    s = wp.sin(phi)
    return wp.vec3(c * p[0] + s * p[2], p[1], -s * p[0] + c * p[2])


@wp.func
def table(t: wp.array(dtype=wp.float32), s: float):
    n = t.shape[0]
    x = wp.clamp(s, 0.0, 1.0) * float(n - 1)
    i = wp.min(int(x), n - 2)
    f = x - float(i)
    return t[i] * (1.0 - f) + t[i + 1] * f


@wp.func
def wrap_pi(a: float):
    return a - 6.283185307 * wp.floor((a + 3.141592654) / 6.283185307)


@wp.func
def foot_g(q: wp.vec3, u: float, refP: wp.array(dtype=wp.vec3), refT: wp.array(dtype=wp.vec3)):
    """sdf.foot_g on the reference arm's centreline: g(u) = (q - C(u)) . T(u) at the node parameter u (C the polyline, T
    its node tangents interpolated, so g is continuous in u), zero at the foot point"""
    n = refP.shape[0]
    j = wp.min(int(wp.floor(u)), n - 2)
    f = u - float(j)
    c = refP[j] + (refP[j + 1] - refP[j]) * f
    t = wp.normalize(refT[j] * (1.0 - f) + refT[j + 1] * f)
    return wp.dot(q - c, t)


@wp.func
def sec_k(alpha: float, P: wp.array(dtype=wp.float32)):
    """the arm's section radius over the local r at the angle alpha from the aboral side: sdf.sd_sweep's profile with
    the arms' harmonics (ARM_SECTION in P[48..53]: a2, phi2, a3, phi3, a4, aspect); 1.11 aboral, 0.86 lateral, 1.01
    oral"""
    k = 1.0 + P[48] * wp.cos(2.0 * (alpha - P[49])) + P[50] * wp.cos(3.0 * (alpha - P[51])) + P[52] * wp.cos(
        4.0 * alpha)
    cs = wp.cos(alpha)
    sn = wp.sin(alpha)
    return k * P[53] / wp.sqrt(P[53] * P[53] * cs * cs + sn * sn)


@wp.func
def skin_at(pb: wp.vec3, ph: wp.vec3, set_kind: int, P: wp.array(dtype=wp.float32), az: wp.array(dtype=wp.float32),
            refP: wp.array(dtype=wp.vec3), refN: wp.array(dtype=wp.vec3), refB: wp.array(dtype=wp.vec3),
            refT: wp.array(dtype=wp.vec3),
            tabU: wp.array(dtype=wp.float32), tabR: wp.array(dtype=wp.float32), tabRad: wp.array(dtype=wp.float32),
            axP: wp.array(dtype=wp.vec3), axN: wp.array(dtype=wp.vec3), sgrid: wp.uint64,
            sp: wp.array(dtype=wp.vec3), sn: wp.array(dtype=wp.vec3), sd: wp.array(dtype=wp.float32),
            region: int, rim_a: float, seed_head: int, seed_arm: int, want_col: int):
    S_head = P[0]
    S_arm = P[1]
    disorder = P[2]
    texel = P[3]
    r0 = P[4]
    az0 = P[6]
    out = Skin()
    # ---------------------------------------------------------------- arm or not, and (s, alpha) on the reference arm
    a_p = wp.atan2(pb[0], pb[2])
    best = float(1.0e9)
    phi = float(0.0)
    for j in range(az.shape[0]):
        d = wp.abs(wrap_pi(a_p - az[j]))
        if d < best:
            best = d
            phi = az0 - az[j]
    q0 = rot_y(pb, phi)
    qh = rot_y(ph, phi)
    n_pts = refP.shape[0]
    bi = int(0)
    bd = float(1.0e9)
    for i in range(0, n_pts, 4):
        d = wp.length(q0 - refP[i])
        if d < bd:
            bd = d
            bi = i
    s_best = float(0.0)
    bd = float(1.0e9)
    seg = int(0)
    i0 = wp.max(bi - 5, 0)
    i1 = wp.min(bi + 5, n_pts - 2)
    for i in range(i0, i1 + 1):
        a = refP[i]
        e = refP[i + 1] - a
        t = wp.clamp(wp.dot(q0 - a, e) / wp.max(wp.dot(e, e), 1.0e-12), 0.0, 1.0)
        d = wp.length(q0 - (a + e * t))
        if d < bd:
            bd = d
            s_best = (float(i) + t) / float(n_pts - 1)
            seg = i
    s = s_best
    r = table(tabRad, s)                   # the arm's radius (octopus.arm_radius: v4's PCHIP taper)
    ta = wp.normalize(refP[seg + 1] - refP[seg])
    ft = wp.clamp(s * float(n_pts - 1) - float(seg), 0.0, 1.0)
    na = wp.normalize(refN[seg] * (1.0 - ft) + refN[seg + 1] * ft)
    ba = wp.normalize(refB[seg] * (1.0 - ft) + refB[seg + 1] * ft)
    c = refP[seg] + (refP[seg + 1] - refP[seg]) * ft
    v = q0 - c
    v = v - ta * wp.dot(v, ta)
    alpha = wp.atan2(wp.dot(v, ba), wp.dot(v, na))
    if set_kind == 0:
        # (polish 1) on the head set, the FOOT POINT, sdf.sd_sweep's own: the root of g(u) = (q0 - C(u)) . T(u) (C the
        # polyline, T its node tangents interpolated) bracketed round the polyline's nearest point and bisected. The
        # nearest point on the 128-node polyline JUMPS on the concave side of every node and holds over a wedge of its
        # convex side (the streak audit's tears across every arm root and its fans at R3 / R4 s 0.10), and on the tube
        # it lay up to 1.3 mm along the arm off the sweep's parameter, which the sculpt planted the arm's papillae by;
        # the foot point is continuous inside the curvature radius, and on the bare tube bd is the section's radius
        # (the arms set keeps the polyline's nearest point: within 0.01 mm of this at the sets' seam, s 0.30-0.36)
        un = s * float(n_pts - 1)
        umax = float(n_pts - 1) - 1.0e-6
        lo = wp.max(un - 2.0, 0.0)
        hi = wp.min(un + 2.0, umax)
        glo = foot_g(q0, lo, refP, refT)
        ghi = foot_g(q0, hi, refP, refT)
        if glo > 0.0 and ghi < 0.0:
            for it in range(20):
                mid = 0.5 * (lo + hi)
                if foot_g(q0, mid, refP, refT) > 0.0:
                    lo = mid
                else:
                    hi = mid
            un = 0.5 * (lo + hi)
        elif glo <= 0.0 and lo <= 0.0:
            un = 0.0
        elif ghi >= 0.0 and hi >= umax:
            un = umax
        seg = wp.min(int(wp.floor(un)), n_pts - 2)
        ft = un - float(seg)
        s = un / float(n_pts - 1)
        r = table(tabRad, s)
        c = refP[seg] + (refP[seg + 1] - refP[seg]) * ft
        t_f = wp.normalize(refT[seg] * (1.0 - ft) + refT[seg + 1] * ft)
        n_f = wp.normalize(refN[seg] * (1.0 - ft) + refN[seg + 1] * ft)
        n_f = wp.normalize(n_f - t_f * wp.dot(n_f, t_f))
        v = q0 - c
        bd = wp.length(v)
        alpha = wp.atan2(wp.dot(v, wp.cross(t_f, n_f)), wp.dot(v, n_f))
    out.armw = 1.0 - proc.smoothstep(1.0 * r, 1.6 * r, bd)
    if set_kind == 1:
        out.armw = 1.0
    # ---------------------------------------------------------------- the anatomical coordinate and the patches
    # the ARM's patch network or the HEAD's, chosen PER CELL: near an arm (armw between 0 and 1) a cell takes the arm's
    # network where armw beats its hash, so the switch follows the patch grooves (r4 review: a binary is_arm test drew
    # a ruler-straight seam along every arm root, every layer switching on it); every layer below keys on this choice
    U = table(tabU, s)
    R = table(tabR, s)
    # crown v5: the arm coordinate CONTINUES off the tube (head set only; on the tube it is the sculpt's arm_coord as
    # before): past 1.15 local radii the distance from the axis scales the circle, and behind the first centreline node
    # (s clamped to 0: the crown top between the head and the arm roots) U runs on backward by the distance along the
    # first segment. Clamped, every line through the arm's first node and every perpendicular off the tube mapped to one
    # q_a, and the arm network painted the crown top round the head in RADIAL STREAKS (patches, grooves, folds, grain,
    # mottle: 36 % of the junction band at s = 0; CODE_MAP §3, its A/B: coherence p50 0.63 -> 0.39)
    # (polish 1) the circle scales from the SECTION's own radius (sec_k: the sweep's harmonics, 0.86 r on the flanks to
    # 1.11 r on top), not from 1.15 r: with the bare tube anywhere inside 1.15 r, q_a held still along the radius from
    # the flank's 0.86 r out to 1.15 r, and the web's and the crown's fillets there wore the arm network SMEARED along
    # it (the audit's 14 smearing clusters at the lateral arm bases, s 0.18-0.21, the blocky band where the web meets
    # the arm in the close A/B stations); on the bare tube rad_k stays 1 (bd / r_s 0.995-1.005 there, so 1 %)
    behind = float(0.0)
    rad_k = float(1.0)
    if set_kind == 0:
        if seg == 0:
            t0a = wp.normalize(refP[1] - refP[0])
            behind = wp.max(-wp.dot(q0 - refP[0], t0a), 0.0)
        rad_k = wp.max(bd / wp.max(1.01 * r * sec_k(alpha, P), 1.0e-6), 1.0)
    q_a = wp.vec3(U - behind * (R / wp.max(r, 1.0e-6)), R * rad_k * wp.cos(alpha), R * rad_k * wp.sin(alpha))
    # and the arm NETWORK held to its own arm's territory (the colour splits keep armw): it fades out behind the arm's
    # first node (the crown top round the head, 10 mm) and near the sector's bisector, where the nearest arm by azimuth
    # switches and two arms' frames meet edge to edge (4-12 mm of arc); the head network (3D) runs there
    armw_net = out.armw
    if set_kind == 0:
        d_bis = (0.39269908 - best) * wp.sqrt(pb[0] * pb[0] + pb[2] * pb[2])
        armw_net = out.armw * (1.0 - proc.smoothstep(0.0, 0.010, behind)) * proc.smoothstep(0.004, 0.012, d_bis)
    qw_a = proc.warp3(proc.warp3(q_a, 0.008, 0.00055, seed_arm + 5), 0.0026, 0.00022, seed_arm + 6)
    cl_a = proc.cellular3(qw_a / S_arm, disorder, seed_arm)
    is_arm = int(0)
    if set_kind == 1:
        is_arm = 1
    elif armw_net > 0.0:
        if armw_net > proc.u01(proc.hash3i(int(cl_a.rand * 16777216.0), 29, 31, seed_arm + 7)):
            is_arm = 1
    out.arm = float(is_arm)
    q = pb
    S = S_head
    seed = seed_head
    scale = float(1.0)
    if is_arm == 1:
        q = q_a
        S = S_arm
        seed = seed_arm
        scale = wp.max(r / r0, 0.3)
    # two warp octaves so the patches stop reading as polygons (t11: crazy paving), and a broken network: some borders
    # fade out (structure places the grooves, noise only thins them; craft guide 10.14)
    qw = qw_a
    cl = cl_a
    if is_arm == 0:
        qw = proc.warp3(proc.warp3(q, 0.008, 0.00055, seed + 5), 0.0026, 0.00022, seed + 6)
        cl = proc.cellular3(qw / S, disorder, seed)
    edge_d = cl.edge * S
    # the groove at least ~1.6 texels wide, its profile a soft U (r4 review: a 0.2 mm groove on 0.21 mm texels aliased
    # into beaded stair-steps and fed the 1-4 mm normal octaves)
    wg = wp.max(0.00010 * wp.max(scale, 0.5), 1.6 * texel)
    brk = 0.35 + 0.65 * proc.smoothstep(-0.25, 0.30, proc.fbm3(q / 0.006, 2, 2.0, 0.5, seed + 9))
    groove = (1.0 - proc.smoothstep(0.0, wg, edge_d)) * brk
    # the patches as living TILES (refs/colour/08, an O. vulgaris mantle: a mosaic of rounded, raised tiles ~2-4 mm
    # parted by narrow grooves): a cushion rising smoothly from the groove to a rounded crown, so the borders are soft
    # valleys and the domes dominate. (A sqrt profile 13 um high made flat plates parted by crisp cracks, t14's cracked
    # mud; a pillow profile started steep at the border and kept a crease there)
    e_t = wp.clamp(edge_d / (0.5 * S), 0.0, 1.0)
    dome = e_t * e_t * (3.0 - 2.0 * e_t)
    # band-limit: the patch network fades where a patch spans under ~5 texels
    patch_px = S * scale / texel
    fade_p = proc.smoothstep(4.0, 7.0, patch_px)
    # the oral (ventral) weight: the arm's own (where its chromatophores thin out at the sucker field's edge: a narrow
    # unwarped edge, the dark stipple carries it; r4 review: a cloud-warped ramp read as fog) mixed by armw with the
    # region's (the oral crown 1; the mantle and head by side, below), so no line where the web meets the arm
    v_arm = proc.smoothstep(0.26, 0.50, -wp.cos(alpha))
    a_arm = proc.smoothstep(-0.25, 0.45, wp.cos(alpha))
    v_reg = float(0.0)
    if region == 2:
        v_reg = 1.0
    elif region == 0:
        # the ventral mantle and head: pale like the oral crown (REAL_OCTOPUS_COLOUR §1 row 8, ref 03 (171,165,162); r4
        # review: the funnel side carried the dorsal brick), the edge on the flanks broken by noise into a stipple.
        # Ventral = away from the body axis's dorsal normal at the nearest axis node: down under the mantle that lies
        # back, back toward the funnel on the head (v4; r4's rule, world -Z, fitted only the upright mantle)
        # (the ventral THIRD, at 0.6 of the crown's strength: ref 03 is a blanched trawl animal, the pale bound; over
        # the whole ventral half at full strength the mantle turned near-white with dark dots, engine probe 5)
        ia = int(0)
        da = float(1.0e9)
        for i in range(axP.shape[0]):
            dd_a = wp.length(pb - axP[i])
            if dd_a < da:
                da = dd_a
                ia = i
        ta_x = wp.normalize(axP[wp.min(ia + 1, axP.shape[0] - 1)] - axP[wp.max(ia - 1, 0)])
        qa = pb - axP[ia]
        qa = qa - ta_x * wp.dot(qa, ta_x)
        side = -wp.dot(qa, axN[ia]) / wp.max(wp.length(qa), 1.0e-6)
        v_reg = 0.6 * proc.smoothstep(0.35, 0.85, side + 0.30 * proc.fbm3(pb / 0.008, 2, 2.0, 0.5, seed_head + 59))
    # (polish 1) on the crown's two layers near a web's free margin, the oral weight by the margin's SECTION (rim_a: the
    # arc distance from its crest round the half-cylinder edge, negative over the aboral face, positive over the oral
    # face; run's web_rim, RIM_NONE away from every margin): 0 over the aboral face and the crest, rising over the oral
    # face's first 6 mm. By layer alone the colour stepped at the crest where the cage put its layers' boundary, the
    # oral side pale right from the edge (the pale line along every margin from the low orbit, the teeth on the back
    # tent where the boundary zigzags); live webs carry the aboral colour over the margin to the paler oral side with
    # no band (CROWN_STUDY §6)
    if (region == 1 or region == 2) and rim_a < 0.5:
        v_reg = proc.smoothstep(0.0, 0.006, rim_a)
    ventral = v_reg + (v_arm - v_reg) * out.armw
    aboral = (1.0 - v_reg) + (a_arm - (1.0 - v_reg)) * out.armw
    if region == 2:
        # crown v5: the bottom layer is ORAL off the arms' tubes (the webs' oral faces): the arm frame's alpha, 90-110 deg
        # on a web's oral face beside an arm, pulled ventral to 0.18-0.36 there (1.1-1.3 local radii), a band of aboral
        # brown along every arm on the oral side (CODE_MAP §5); on the tube itself (within ~1.1 radii of the axis) the
        # arm's own rule by alpha holds, as on the arms set past the tube's first ring (no step there)
        # (polish 1: off the tube the layer's own weight, 1 past the margin's ramp, as v_reg above)
        w_tube = 1.0 - proc.smoothstep(1.05 * r, 1.25 * r, bd)
        ventral = v_reg + (v_arm - v_reg) * w_tube
        aboral = (1.0 - v_reg) * (1.0 - w_tube) + a_arm * w_tube
    # the mouth (its centre on the axis at height P[27]; the lip's crest radius P[28], the opening's P[30]) and the
    # funnel (P[31..38]): smooth skin, no patch network (a siphon is smooth; the lip carries its sculpted folds)
    lip = float(0.0)
    lining = float(0.0)
    funnel = float(0.0)
    if is_arm == 0:
        rho_m = wp.sqrt(pb[0] * pb[0] + pb[2] * pb[2])
        dym = pb[1] - P[27]
        near = 1.0 - proc.smoothstep(0.010, 0.016, wp.abs(dym))
        lip = (1.0 - proc.smoothstep(1.22 * P[28], 1.42 * P[28], rho_m)) * near
        # inside the opening: an elliptical metric (semi-axes P[42] lateral, P[43] fore and aft; both the round
        # opening's radius when it is round)
        rho_e = wp.sqrt((pb[0] / P[42]) * (pb[0] / P[42]) + (pb[2] / P[43]) * (pb[2] / P[43]))
        lining = (1.0 - proc.smoothstep(0.95, 1.12, rho_e)) * proc.smoothstep(-0.0016, -0.0002, dym) * near
        fa = wp.vec3(P[31], P[32], P[33])
        fx = wp.vec3(P[34], P[35], P[36]) - fa
        fl = wp.length(fx)
        fx = fx / fl
        tt = wp.clamp(wp.dot(pb - fa, fx) / fl, 0.0, 1.0)
        dd = wp.length(pb - (fa + fx * (tt * fl)))
        funnel = wp.clamp(1.0 - (dd - (P[37] + (P[38] - P[37]) * tt) - 0.003) / 0.004, 0.0, 1.0) * wp.clamp(
            (tt - 0.30) / 0.20, 0.0, 1.0)
    amp = fade_p * (1.0 - 0.95 * ventral) * (1.0 - 0.85 * funnel) * (1.0 - 0.9 * lip)
    h = (-0.000050 * groove + 0.00009 * dome * wp.max(scale, 0.5)) * amp
    # the skin's FOLDS: broad low domes ~12 mm across between soft creases, warped and broken (calib: the normal's
    # 9-18 mm octave read 0.043 against the study's 0.07-0.10; narrow creases alone put their energy in the fine bands,
    # round 2, so the domes carry it). On the arms, scaled to the arm and mostly aboral
    qf = proc.warp3(q, 0.020, 0.0030, seed + 61)
    cf = proc.cellular3(qf / (0.012 * scale), 0.85, seed + 63)
    brk_f = proc.smoothstep(-0.30, 0.25, proc.fbm3(q / 0.018, 2, 2.0, 0.5, seed + 65))
    crease = (1.0 - proc.smoothstep(0.0, 0.0016, cf.edge * 0.012 * scale)) * brk_f
    dome_f = 1.0 - proc.smoothstep(0.05, 0.60, cf.f1)
    fade_f = proc.smoothstep(4.0, 7.0, 0.012 * scale / texel) * (1.0 - 0.7 * ventral) * (1.0 - funnel) * (1.0 - lip)
    if is_arm == 1:
        fade_f = fade_f * (0.25 + 0.75 * aboral) * 0.7
    h = h + (0.00035 * scale * dome_f - 0.00006 * crease) * fade_f
    # the crevice grain (ridged fBm through a histogram scan)
    rg = 1.0 - wp.abs(proc.fbm3(q / (0.0009 * wp.max(scale, 0.6)), 3, 2.0, 0.5, seed + 31))
    grain = proc.histogram_scan(rg, 0.55, 0.8)
    fade_g = proc.smoothstep(3.0, 5.0, 0.0009 * wp.max(scale, 0.6) / texel)
    h = h - 0.000012 * grain * fade_g * (1.0 - 0.5 * ventral) * (1.0 - 0.6 * funnel) * (1.0 - 0.7 * lip)
    # transverse arm wrinkles: creases round the arm, wavefronts across its length, broken up
    if is_arm == 1:
        lam = 0.0015
        ph_ = q[0] / lam + 0.6 * proc.fbm3(q / 0.004, 2, 2.0, 0.5, seed + 47)
        cr = proc.smoothstep(0.80, 1.0, 0.5 + 0.5 * wp.cos(6.283185307 * ph_))
        brk = proc.smoothstep(-0.25, 0.35, proc.fbm3(q / 0.006, 2, 2.0, 0.5, seed + 53))
        fade_w = proc.smoothstep(3.0, 6.0, lam * scale / texel)
        # on the arm's own tube only, fading out across the web root, and mostly aboral (t14: the creases ran on as
        # fan stripes over the oral webs near the arm bases)
        tube = 1.0 - proc.smoothstep(0.95 * r, 1.12 * r, bd)
        h = h - 0.000028 * cr * brk * fade_w * (0.10 + 0.90 * aboral) * tube
    # ---------------------------------------------------------------- suckers (the reference arm's, in its frame); on
    # the head set too, where the proximal rows cross the oral disc to the mouth
    disc = float(0.0)
    rim = float(0.0)
    cup = float(0.0)
    stalk = float(0.0)
    if set_kind == 1 or out.armw > 0.0 or region == 2:
        qr = wp.hash_grid_query(sgrid, qh, 0.0065)
        k = int(0)
        bestr = float(1.0e9)
        while wp.hash_grid_query_next(qr, k):
            w = qh - sp[k]
            y = wp.dot(w, sn[k])
            rad = w - sn[k] * y
            Rk = 0.5 * sd[k]
            rho = wp.length(rad) / Rk
            if rho < 1.2 and rho < bestr and y > -0.15 * sd[k]:
                bestr = rho
                top = proc.smoothstep(0.18 * sd[k], 0.30 * sd[k], y)
                disc = top * proc.smoothstep(0.28, 0.36, rho) * (1.0 - proc.smoothstep(0.70, 0.80, rho))
                rim = top * proc.smoothstep(0.70, 0.80, rho) * (1.0 - proc.smoothstep(0.95, 1.05, rho))
                cup = (1.0 - proc.smoothstep(0.26, 0.34, rho)) * proc.smoothstep(-0.05 * sd[k], 0.1 * sd[k], y)
                stalk = (1.0 - top) * (1.0 - proc.smoothstep(1.0, 1.15, rho))
                # radial cuticle grooves on the infundibulum, finer folds on the rim
                t1 = ta - sn[k] * wp.dot(ta, sn[k])
                t1 = wp.normalize(t1)
                b1 = wp.cross(sn[k], t1)
                ang = wp.atan2(wp.dot(rad, b1), wp.dot(rad, t1))
                nr = 36.0 + 8.0 * proc.u01(proc.hash3i(k, 7, 11, 3))
                pitch = 6.283185307 * rho * Rk / nr
                fg = proc.smoothstep(2.0, 4.0, pitch / texel)
                grv = 0.5 + 0.5 * wp.cos(nr * ang)
                h = h - 0.000025 * wp.clamp(sd[k] / 0.005, 0.3, 1.0) * grv * disc * fg
                fr = proc.smoothstep(2.0, 4.0, pitch / 2.5 / texel)
                fold = 0.5 + 0.5 * wp.cos(2.5 * nr * ang + 2.0 * proc.noise3(qh / 0.0008, 9))
                h = h - 0.000015 * fold * rim * fr
    out.h = h
    out.groove = groove * amp
    # (the patch's crown-to-groove coordinate: the distance to its border in half patches, scale-free, so the arms'
    # network and the head's spread alike; square-rooted for an even spread, about its median, to unit spread)
    out.tile = (wp.sqrt(e_t) - 0.46) * 4.8 * amp
    out.prand = cl.rand
    # ---------------------------------------------------------------- the PAINT passes and the colour layers: only for
    # the texel's own sample (the two neighbours exist for the height's gradient alone; t11: computing these three
    # times made the head set's pass 463 s)
    if want_col == 1:
        if is_arm == 1:
            # the aboral midline carries the densest pigment; broken transverse bands ~1.8 crown radii apart (in the
            # straightened coordinate, so they close up toward the tip), on the aboral half
            out.midline = proc.smoothstep(0.55, 0.95, wp.cos(alpha))
            # APERIODIC along the arm: the phase drifts with a slow noise and the width varies ~40 % (r4 review: even,
            # equal, crisp rings read as a striped sock); broken on the patch cells
            nb = proc.fbm3(q / 0.012, 2, 2.0, 0.5, seed + 91)
            drift = 1.2 * proc.fbm3(wp.vec3(q[0] / 0.09, 0.0, 0.0), 2, 2.0, 0.5, seed + 95)
            bb = 0.5 + 0.5 * wp.cos(6.283185307 * (q[0] / 0.034 + 0.35 * nb + drift))
            det = proc.fbm3(q / 0.003, 2, 2.0, 0.5, seed + 93)
            wv = 0.10 * proc.fbm3(wp.vec3(q[0] / 0.05, 3.0, 0.0), 2, 2.0, 0.5, seed + 97)
            out.band = proc.smoothstep(0.62 + wv, 0.78 + wv, bb + 0.18 * det) * aboral * 0.7 * out.armw \
                * (0.6 + 0.4 * proc.smoothstep(0.2, 0.35, cl.rand))
        if is_arm == 0:
            # dark blotches mirrored about the sagittal plane (octopus body patterns are bilateral), quantized per
            # patch
            sq = cl.site * S
            sq = wp.vec3(wp.abs(sq[0]), sq[1], sq[2])
            # three scales: ~5 cm saddles and patches (calib: the head's 71-143 mm ln L octave read 0.066 against the
            # study's 0.10-0.24 once the noise stepped back there), the ~2 cm blotches, their ~7 mm edges
            nbl = 0.45 * proc.fbm3(sq / 0.050, 2, 2.0, 0.5, seed + 105) + 0.40 * proc.fbm3(sq / 0.022, 3, 2.0, 0.5,
                                                                                         seed + 101) \
                + 0.15 * proc.fbm3(sq / 0.0075, 2, 2.0, 0.5, seed + 103)
            out.blotch = proc.smoothstep(0.10, 0.30, nbl) * (1.0 - ventral) * (1.0 - 0.6 * out.armw)
        EL = wp.vec3(P[7], P[8], P[9])
        ER = wp.vec3(P[10], P[11], P[12])
        de = wp.min(wp.length(pb - EL), wp.length(pb - ER)) / P[13]
        out.eyering = proc.smoothstep(1.08, 1.18, de) * (1.0 - proc.smoothstep(1.30, 1.55, de))
        nsp = 0.5 + 0.5 * proc.fbm3(pb / 0.002, 2, 2.0, 0.5, seed + 111)
        spots = float(0.0)
        for ks in range(4):
            spots = wp.max(spots, soft_spot(pb, wp.vec3(P[14 + 3 * ks], P[15 + 3 * ks], P[16 + 3 * ks]), P[26], 0.5,
                                            nsp))
        out.spots = spots
        # the body pattern's mottle, a QUARTER quantized per patch (the site's value blended with the point's: fully
        # quantized it read as stained glass, t11; half still gave each cell its own flat tint, r4 review)
        site = cl.site * S
        m_site = 0.6 * proc.fbm3(site / 0.014, 3, 2.0, 0.5, seed + 71) + 0.4 * proc.fbm3(site / 0.005, 2, 2.0, 0.5,
                                                                                            seed + 73)
        m_pt = 0.6 * proc.fbm3(q / 0.014, 3, 2.0, 0.5, seed + 71) + 0.4 * proc.fbm3(q / 0.005, 2, 2.0, 0.5,
                                                                                      seed + 73)
        out.mottle = 0.25 * m_site + 0.75 * m_pt
        # dark chromatophore CLUSTERS (r4 review: the 1-10 mm variance came from soft noise, 2-9x short of the live
        # photos): on most patches one cluster off the patch's centre (the papillae stand at the centres), 0.3-2 mm
        # across, more and larger where a ~6 cm density field is high; fewer on the pale side
        hc = int(cl.rand * 16777216.0)
        oc3 = wp.vec3(proc.u01(proc.hash3i(hc, 5, 9, seed + 161)), proc.u01(proc.hash3i(hc, 7, 3, seed + 162)),
                      proc.u01(proc.hash3i(hc, 2, 13, seed + 163))) - wp.vec3(0.5, 0.5, 0.5)
        dens = 0.5 + 0.5 * proc.fbm3(q / 0.06, 2, 2.0, 0.5, seed + 165)
        r_c = (0.10 + 0.22 * dens) * (0.6 + 0.8 * proc.u01(proc.hash3i(hc, 11, 17, seed + 166)))
        d_c = wp.length(qw / S - (cl.site + oc3 * 0.55))
        has = 1.0 - proc.smoothstep(0.30 + 0.50 * dens - 0.05, 0.30 + 0.50 * dens + 0.05,
                                    proc.u01(proc.hash3i(hc, 19, 23, seed + 167)))
        out.chrom = has * (1.0 - proc.smoothstep(0.7 * r_c, r_c, d_c)) * (1.0 - 0.8 * ventral) \
            * proc.smoothstep(1.0, 2.0, r_c * S * scale / texel)
        # the albedo's own mottling (R6, cephalopod; octopus §10a): ln L octaves 2-128 mm with RMS a (lambda / 10 mm)
        # ^0.34, a = P[39]; x4: gradient noise's RMS ~0.25 (calib.report measures what lands); band-limited
        oc = float(0.0)
        lo_ = float(0.002)
        for ko in range(7):
            fo = proc.smoothstep(2.5, 4.0, lo_ * scale / texel)
            # above ~24 mm the noise gives way to STRUCTURE (blotches, bands): isotropic noise there read as clouds
            # (t11) while the study's large-scale variance comes from feature zones (REF R6)
            big = 1.0 - 0.75 * proc.smoothstep(0.016, 0.128, lo_)
            oc = oc + P[39] * wp.pow(lo_ / 0.010, 0.34) * 4.0 * fo * big * proc.noise3(q / lo_, seed + 131 + ko)
            lo_ = lo_ * 2.0
        out.oct = oc
        # chromatophore specks (octopus §10a: 2-4.5 mm across, 6-11 mm apart, light and dark alike): half the cells of
        # an 8.5 mm network carry one, its radius and sign from the cell's own random
        cs = proc.cellular3(q / 0.0085, 0.9, seed + 141)
        hr = int(cs.rand * 16777216.0)
        rad_s = (1.0 + 1.25 * proc.u01(proc.hash3i(hr, 3, 7, seed + 143))) / 8.5
        spk = (1.0 - proc.smoothstep(0.6 * rad_s, rad_s, cs.f1)) * (1.0 - proc.smoothstep(0.45, 0.5, cs.rand))
        sgn = float(1.0)
        if proc.u01(proc.hash3i(hr, 11, 5, seed + 147)) < 0.5:
            sgn = -1.0
        out.speck = P[41] * spk * sgn * proc.smoothstep(2.5, 4.0, 0.002 * scale / texel) * (1.0 - 0.3 * float(is_arm))
        # roughness's flat-octave noise (R5: 0.007-0.03 RMS per octave)
        rn = proc.noise3(q / 0.0012, seed + 151) + proc.noise3(q / 0.005, seed + 152) + proc.noise3(q / 0.02,
                                                                                                    seed + 153)
        out.rnoise = 0.015 * 4.0 * rn / 1.73
        # the VEIN families (ember, arc; P[45] the family id, 0 = none): the borders of a coarse cellular network
        # P[46] patches across, in the same anatomical coordinate (structure first: a slow field picks about half the
        # borders), P[44] the vein's half width, clamped to the band limit (at least 1.6 texels on the skin: q is the
        # skin / scale on the arms, so the floor is / scale there; faded out below ~2 texels instead, the recipe's
        # 0.5 mm painted no texel on either set, halo_v2.md); not over suckers, lining or funnel. The cells at least
        # 12.8 texels across on the skin: 4 wall widths (2 vw) at the width's floor (the distal arms below scale ~0.34,
        # where the walls closed the cells into char blots); the mantle's net and the rest of the arms' unchanged.
        # Toward the tip the reticulation fines out and fades, the suckers lead: where the walls sit at their floor and
        # can fine no further, their contrast fades by the cells per wall there, min(1, cells / 6) (4 at the tips, 6 at
        # scale ~0.51 on the arms set); where the recipe's width holds (the head, the mantle, the arm roots) none fades
        if P[45] > 0.5:
            vw = wp.max(P[44] * wp.max(scale, 0.5), 1.6 * texel / scale)
            Sv = P[46] * S
            qv = qw / Sv
            qs = q / (2.5 * Sv)
            Sm = 12.8 * texel / scale
            if Sm > Sv:
                # (the lattice anchored at U = P[47], where the minimum starts on the arm: there the cell grows toward
                # the tip, and from the arm's root the growth, multiplied by U, would fold the lattice back on itself;
                # anchored, it stretches the cells along the arm by at most ~12 % on the arms set)
                ca = wp.vec3(P[47], 0.0, 0.0)
                qv = (qw - ca) / Sm + ca / Sv
                qs = (q - ca) / (2.5 * Sm) + ca / (2.5 * Sv)
                Sv = Sm
            fv = float(1.0)
            if vw > P[44] * wp.max(scale, 0.5):
                fv = wp.min(Sv / (12.0 * vw), 1.0)
            cv = proc.cellular3(qv, 0.85, seed + 163)
            sel = proc.smoothstep(-0.05, 0.25, proc.fbm3(qs, 2, 2.0, 0.5, seed + 165))
            keep = sel * (1.0 - wp.clamp(disc + rim + cup, 0.0, 1.0)) * (1.0 - funnel) * (1.0 - lining) * fv
            out.vein = (1.0 - proc.smoothstep(0.4 * vw, vw, cv.edge * Sv)) * keep
            out.vcore = (1.0 - proc.smoothstep(0.0, 0.4 * vw, cv.edge * Sv)) * keep
            out.vrand = cv.rand
    out.lip = lip
    out.lining = lining
    out.funnel = funnel
    out.ventral = ventral
    out.aboral = aboral
    out.disc = disc
    out.rim = rim
    out.cup = cup
    out.stalk = stalk
    return out


@wp.kernel
def k_skin(uv_mesh: wp.uint64, size: int, ss: int, set_kind: int, lpos: wp.array(dtype=wp.vec3),
           lnrm: wp.array(dtype=wp.vec3), ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4),
           d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_cav: wp.array(dtype=wp.float32),
           d_thk: wp.array(dtype=wp.float32), d_curv: wp.array(dtype=wp.float32), d_hgt: wp.array(dtype=wp.float32),
           d_base: wp.array(dtype=wp.vec4), d_reg: wp.array(dtype=wp.int32), d_aol: wp.array(dtype=wp.float32),
           d_conv: wp.array(dtype=wp.float32), d_convm: wp.array(dtype=wp.float32), P: wp.array(dtype=wp.float32),
           az: wp.array(dtype=wp.float32), refP: wp.array(dtype=wp.vec3), refN: wp.array(dtype=wp.vec3),
           refB: wp.array(dtype=wp.vec3), refT: wp.array(dtype=wp.vec3), tabU: wp.array(dtype=wp.float32),
           tabR: wp.array(dtype=wp.float32),
           tabRad: wp.array(dtype=wp.float32), axP: wp.array(dtype=wp.vec3), axN: wp.array(dtype=wp.vec3),
           sgrid: wp.uint64, sp: wp.array(dtype=wp.vec3), sn: wp.array(dtype=wp.vec3), sd: wp.array(dtype=wp.float32),
           seed_head: int, seed_arm: int, o_alb: wp.array(dtype=wp.vec3), o_nrm: wp.array(dtype=wp.vec3),
           o_orm: wp.array(dtype=wp.vec3), o_mask: wp.array(dtype=wp.vec4), o_disp: wp.array(dtype=wp.vec4),
           o_grow: wp.array(dtype=wp.vec4), d_mat: wp.array(dtype=wp.int32), ggrid: wp.uint64, grq: float,
           gA: wp.array(dtype=wp.vec3), gB: wp.array(dtype=wp.vec3), gQ: wp.array(dtype=wp.vec4),
           gZ: wp.array(dtype=wp.vec4), FT: wp.array(dtype=wp.float32), ghq: float, d_rim: wp.array(dtype=wp.float32)):
    tid = wp.tid()
    x = tid % size
    y = tid // size
    dn = d_nrm[tid]
    if dn[3] <= 0.0:
        return
    tn_b = wp.normalize(wp.vec3(dn[0], dn[1], dn[2]))
    reg = d_reg[tid]
    rim_a = d_rim[tid]                  # (polish 1) the web margin's section coordinate here (run's web_rim)
    hgt = d_hgt[tid]
    base = d_base[tid]
    # the texel's material ids (the bake's vote): the growth share fg fades the skin's texture tier
    code = d_mat[tid]
    fg = GR.unpack_ids(code)[1]
    acc_met = float(0.0)
    acc_g = wp.vec4(0.0)
    inv = 1.0 / float(ss)
    dlt = 0.5 * inv
    acc_a = wp.vec3(0.0)
    acc_n = wp.vec3(0.0)
    acc_r = float(0.0)
    acc_ao = float(0.0)
    acc_x = float(0.0)
    acc_m = wp.vec4(0.0)
    acc_d = wp.vec4(0.0)
    hits = int(0)
    hb = float(0.0)
    have_hb = int(0)
    # palette (sRGB -> linear), measured on live O. vulgaris (research/REAL_OCTOPUS_COLOUR.md §1): the mantle about half
    # the chroma the study-T-derived brick had, the arms a little more saturated than the mantle, the light end a greyish
    # buff (the old ochre was too yellow and too chromatic for either end), orange chromatophore spots
    c_dark = M.srgb(wp.vec3(0.358, 0.210, 0.161))
    c_brick_m = M.srgb(wp.vec3(0.493, 0.331, 0.261))      # mantle, head, webs
    c_brick_a = M.srgb(wp.vec3(0.534, 0.312, 0.224))      # arms
    c_light = M.srgb(wp.vec3(0.724, 0.545, 0.449))
    c_spot = M.srgb(wp.vec3(0.588, 0.372, 0.247))
    c_cream = M.srgb(wp.vec3(0.88, 0.80, 0.71))
    # suckers (§1 rows 9-12, 24 face-on suckers in live photos): a near-neutral pale disc, a darker pigmented band at its
    # rim, the cup a little warm (never rosier than round it); the mouth's lining (R3: L ~0.05; a dark wine-red)
    c_disc = M.srgb(wp.vec3(0.668, 0.636, 0.621))
    c_rim = M.srgb(wp.vec3(0.495, 0.386, 0.347))
    c_cup = M.srgb(wp.vec3(0.544, 0.441, 0.381))
    c_lining = M.srgb(wp.vec3(0.20, 0.15, 0.13))         # near-black brown (r4 review: L at most ~0.03)
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
            # two neighbours for the height's surface gradient (toward -x / -y when +x / +y leaves the island)
            sx = float(1.0)
            lx = M.low_at(uv_mesh, fx + dlt, fy, lpos, lnrm, ltan, lattr)
            if lx.ok == 0:
                sx = -1.0
                lx = M.low_at(uv_mesh, fx - dlt, fy, lpos, lnrm, ltan, lattr)
            ly = M.low_at(uv_mesh, fx, fy + dlt, lpos, lnrm, ltan, lattr)
            if ly.ok == 0:
                ly = M.low_at(uv_mesh, fx, fy - dlt, lpos, lnrm, ltan, lattr)
            pb0 = lo.p + lo.n * hb
            ph0 = lo.p + lo.n * hgt
            sk = skin_at(pb0, ph0, set_kind, P, az, refP, refN, refB, refT, tabU, tabR, tabRad, axP, axN, sgrid, sp,
                         sn, sd, reg, rim_a, seed_head, seed_arm, 1)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1:
                pbx = lx.p + lx.n * hb
                pby = ly.p + ly.n * hb
                hx = skin_at(pbx, lx.p + lx.n * hgt, set_kind, P, az, refP, refN, refB, refT, tabU, tabR, tabRad, axP,
                             axN, sgrid, sp, sn, sd, reg, rim_a, seed_head, seed_arm, 0).h
                hy = skin_at(pby, ly.p + ly.n * hgt, set_kind, P, az, refP, refN, refB, refT, tabU, tabR, tabRad, axP,
                             axN, sgrid, sp, sn, sd, reg, rim_a, seed_head, seed_arm, 0).h
                g = M.surface_grad(pb0, pbx, pby, sk.h, hx, hy) * (1.0 - fg)     # (none over a growth)
            nw = M.to_world(lo, tn_b)
            g = g - nw * wp.dot(g, nw)
            nf = wp.normalize(nw - g)
            acc_n = acc_n + M.to_tangent(lo, nf)
            # ------------------------------------------------------------------------ colour: the reference study's
            # stack order (REF_SKIN_STUDY §9 R12) with its octopus numbers (§10a); calib.report prints the result
            # against its bars
            aol = d_aol[tid]
            conv = d_conv[tid]
            convm = d_convm[tid]
            thk = d_thk[tid]
            # 2. the dorsal pigment: the chromatophores' state (the mottle) across a dark red-brown / brick / buff
            # ramp, its strength P[40]; the light end mixed at 0.6 so the ramp spans the live animal's (mantle q95/q05
            # ~5-8; S falls and hue rises toward the light end by construction)
            # (crown v5) the chromatophores' state is the DORSAL pigment's: on the oral crown and webs (ventral, off the
            # arms) few chromatophores open, so the mottle fades there as the clusters, blotches and octaves do (at full
            # strength, then the countershading's S x0.15, it painted the oral webs' dark grey smudges: CODE_MAP §5, live
            # oral webs pale and near-neutral, research/CROWN_STUDY.md 6); the bottom layer only (crown v5b: by ventral
            # alone it faded the ventral mantle's and head's mottle too)
            m_or = float(1.0)
            if reg == 2:
                m_or = 1.0 - 0.85 * sk.ventral * (1.0 - sk.armw)
            dark = proc.smoothstep(-0.05, 0.45, sk.mottle) * P[40] * m_or
            light = proc.smoothstep(0.0, 0.45, -sk.mottle) * m_or
            col = M.mix3(M.mix3(c_brick_m, c_brick_a, sk.armw), c_dark, dark)
            col = M.mix3(col, c_light, 0.6 * light)
            col = col * (0.975 + 0.05 * sk.prand)
            # the dark chromatophore clusters (brown-purple, L ~0.04)
            col = M.mix3(col, c_dark * 0.75, 0.75 * sk.chrom)
            # the light specks as orange chromatophore spots (the most saturated tenth above the median L in the live
            # photos), not just lighter skin
            col = M.mix3(col, c_spot, 0.7 * wp.clamp(wp.max(sk.speck, 0.0) / wp.max(P[41], 1.0e-6), 0.0, 1.0))
            # 3. features at their resting strength (the runtime deepens them from the display masks)
            col = M.mix3(col, c_dark * 0.80, 0.40 * sk.blotch)
            col = M.mix3(col, c_dark * 0.85, 0.30 * sk.band)
            col = col * (1.0 - 0.18 * sk.midline)
            col = M.mix3(col, c_dark * 0.70, 0.30 * sk.eyering)
            # the pale RETICULATION in the furrows between the tiles (the leucophore network; refs/colour/08): now that
            # the tiles are domes and the furrows soft, wide valleys, a moderate pale network reads as living skin (on
            # flat plates parted by hairlines it read as cracked mud, t14)
            col = M.mix3(col, c_light, 0.16 * sk.groove * (1.0 - sk.ventral))
            # countershading (R2, cephalopod): the oral side is the same pigment with fewer chromatophores open, its
            # hue held (t11 painted a separate cream: x7 the dorsal L), split by tissue (REAL_OCTOPUS_COLOUR §1 row 7):
            # the arms' oral faces between the suckers keep their pigment (L x1.5, S x0.85; live x1.3-1.6), the oral
            # crown goes pale and near-grey (L x2.6, S x0.15; one x2.6 / x0.55 rule for both was the salmon-pink);
            # thin margins show the pale tissue through
            # (crown v5) the oral WEBS at L x2.0, S x0.21 (live: the oral web x1.85, the web strip beside an arm x2.51 the
            # aboral arm, S x0.21 [M c03]); the oral disc round the mouth inside ~3 arm radii keeps x2.6 / x0.15 (the
            # ventral mantle x2.55 [M c03]): the whole bottom layer at x2.6 stood almost twice the top's L at the margin
            # from the low orbit, the pale paper band
            w_web = float(0.0)
            if reg == 2:
                w_web = proc.smoothstep(2.5 * P[4], 3.5 * P[4], wp.sqrt(pb0[0] * pb0[0] + pb0[2] * pb0[2]))
            kl = 1.0 + sk.ventral * (0.5 * sk.armw + (1.6 - 0.6 * w_web) * (1.0 - sk.armw))
            ks = 1.0 - sk.ventral * (0.15 * sk.armw + (0.85 - 0.06 * w_web) * (1.0 - sk.armw))
            col = M.lsh(col, kl, ks)
            thin = 1.0 - proc.smoothstep(0.0012, 0.006, thk)
            col = M.mix3(col, M.lsh(col, 1.5, 0.7), 0.20 * thin * (1.0 - sk.ventral))
            # the mouth: the lip derived from the oral skin it sits on, a little darker and greyer and translucent
            # (ORAL_REFERENCE §5: 3-6 L* darker and cooler than the oral skin, no source has rosier lips; a separate
            # rosy flesh was wrong); the lining inside the opening dark and wet
            # (r4 review, ORAL_REFERENCE §5: darker AND cooler than the oral skin, S at most ~0.10)
            lipc = M.lsh(col, 0.88, 0.35) + wp.vec3(-0.018, 0.0, 0.022)
            col = M.mix3(col, wp.vec3(wp.max(lipc[0], 0.0), lipc[1], lipc[2]), sk.lip)
            col = M.mix3(col, c_lining, sk.lining)
            # suckers: the pale disc, the darker pigmented band at its rim (x0.38 the disc's L; the study-T rule's pale
            # rim came from squid hooks), the cup; the stalk keeps the arm's oral skin (live: orange outside the rim)
            sk_mask = wp.clamp(sk.disc + sk.rim + sk.cup + 0.6 * sk.stalk, 0.0, 1.0)
            col = M.mix3(col, c_disc, sk.disc)
            col = M.mix3(col, c_rim, sk.rim)
            col = M.mix3(col, c_cup, sk.cup)
            # 4. the albedo's own mottling and the specks, ln L, independent of the relief (R6): skin only, quieter on
            # the pale oral side (fewer chromatophores open; t14: noise fog over it)
            lnl = (sk.oct + wp.min(sk.speck, 0.0)) * (1.0 - sk_mask) * (1.0 - sk.lining) * (1.0 - 0.85 * sk.ventral)
            # 5. relief (R4 octopus: lnL += 1.5 AO_local + 0.1 conv_mid, cavities richer) and the texture tier's
            # grooves; on the sucker cuticle a third of it (calib: the rims' convex tops brightened into the clamp,
            # L 0.64 against the study's 0.41-0.58)
            # and gentler on the lip, whose inner rim the deep opening occludes (t14: a dirty grey ring round the mouth)
            rel = (1.0 - 0.7 * sk_mask) * (1.0 - 0.6 * sk.lip)
            # the occluded side of AO_local darkens fully only in true crevices (the cavity driver low); on a papilla's
            # broad skirt a third of it (r4 review: every papilla stood in a dark, bruise-like halo, relief darker than
            # skin, the opposite of the animal)
            # (and none where the fine convexity is positive; at 1.0 rather than 1.5)
            crev = 0.35 + 0.65 * (1.0 - proc.smoothstep(0.70, 0.90, d_cav[tid]))
            # (polish 1) not the web margin's own roundness: within 3 mm of its crest (rim_a) the convex parts of
            # AO_local, conv_mid and conv are the rim's 0.9 mm radius, not the skin's relief, easing back in by 9 mm
            # (conv_mid +2.0-2.6 and AO_local +0.05-0.11 there lit both faces' last 4-8 mm by x1.5: the oral side's L
            # 0.37 at the crest against 0.22 in the web, the top's 0.19 against 0.125, a pale band along every margin
            # with no live counterpart, CROWN_STUDY §6; the gloss too, below). 1 exactly away from every margin
            k_rim = proc.smoothstep(0.003, 0.009, wp.abs(rim_a))
            aol_r = wp.min(aol, 0.0) + wp.max(aol, 0.0) * k_rim
            convm_r = wp.min(convm, 0.0) + wp.max(convm, 0.0) * k_rim
            conv_r = wp.min(conv, 0.0) + wp.max(conv, 0.0) * k_rim
            aol_e = wp.min(aol_r, 0.0) * crev * (1.0 - proc.smoothstep(0.0, 0.5, conv)) + wp.max(aol_r, 0.0)
            lnl = lnl + (1.0 * wp.min(aol_e, 0.0) + 1.5 * wp.max(aol_e, 0.0) + 0.10 * convm_r) * rel - 0.04 * sk.groove
            col = M.lsh(col * wp.exp(lnl), 1.0, 1.0 - 0.3 * aol_e)
            # pale papilla TIPS (live ref 10; REF R4: lnL rises with height on skin): the most convex fine relief toward
            # cream, lighter and greyer
            # (crown v5: not on a web margin's rounded rim, under ~2 mm thick, whose convexity is the rim's, not a
            # papilla's: conv +1.7-3.0 there lightened the last mm by 22-49 %, CODE_MAP §4)
            tip = proc.smoothstep(0.9, 2.2, conv) * (1.0 - sk_mask) * (1.0 - sk.lip) * proc.smoothstep(0.0012, 0.0020, thk)
            col = M.mix3(col, M.lsh(col, 1.3, 0.65), 0.6 * tip)
            # the envelope (R2): linear L 0.010-0.65
            lc = M.lum(col)
            col = col * (wp.clamp(lc, 0.010, 0.65) / wp.max(lc, 1.0e-6))
            # 7. the GROWTH families (the bake's material ids) and the VEIN families (painted here): the skin result
            # blends toward each by its share (REF R12: element overlays and growths last); sh = the id mask. First
            # the skin's response round each root: the family's element infusion as a local halo (growth.growth_halo:
            # the metal nodules' metal in and chroma out) written into the skin's own channels, so the runtime's skin terms (the
            # tint, the display, the remix's edits, the subsurface floor) act on it as on the skin round it. Its L
            # spreads about the skin's own median: on the skin's relief (the patch crowns and the bake's convex tail,
            # papillae and ridges, brighter: worn; the grooves darker; the bake's concavity and occlusion inside a halo
            # are the crystal's own crease and shadow, which would darken every root) and a TARNISH, unit-RMS noise in
            # units of the crystal's R at the reference's band split, never finer than its resolution (growth.
            # halo_tarnish: the reference's spread is mostly a new pattern, corr(ln L) with its base .40, and the arms'
            # relief is band-limited away: halo_v2.md); the envelope again after
            hl = GR.growth_halo(ph0, ggrid, ghq, gA, gB, gQ, gZ, FT)
            if hl.w > 0.0:
                zl = sk.tile + proc.smoothstep(0.3, 1.0, conv) + hl.tar
                col = M.lsh(col, wp.exp(hl.kl * zl), hl.ks)
                lc = M.lum(col)
                col = col * (wp.clamp(lc, 0.010, 0.65) / wp.max(lc, 1.0e-6))
            gt = GR.growth_texel(code, ph0, ggrid, grq, gA, gB, gQ, gZ, FT, d_ao[tid], aol, conv, nf[1], P[3], col)
            vt = GR.vein_texel(int(P[45] + 0.5), sk.vein, sk.vcore, sk.vrand, FT, aol)
            fv = vt.f * (1.0 - gt.f)
            sh = wp.max(gt.share, vt.share * (1.0 - gt.f))
            col = M.mix3(M.mix3(col, gt.col, gt.f), vt.col, fv)
            acc_a = acc_a + col
            # 6. roughness (R5 wet skin, octopus §10a): 0.17 - 0.4 AO_local - 0.035 conv and a flat-octave noise,
            # the oral side rougher, the sucker cups and the mouth's lining wet-glossy (t11: a flat 0.38 damp)
            # (calib round 1: p5/p50/p95 0.14/0.20/0.44 against 0.08-0.12/0.14-0.20/0.29-0.40: a lower base, bump
            # tops glossier, the oral and groove terms and Toksvig gentler)
            # (r4 review: tips hit the clamp as glitter and the rims were the glossiest skin on the animal: the convexity
            # term halved, a floor at 0.11, the rims soft, the cups and lining wet-glossy)
            rough = 0.14 - 0.40 * aol_r - 0.02 * conv_r + sk.rnoise + 0.04 * sk.ventral + 0.01 * sk.groove
            rough = wp.max(rough, 0.11)
            rough = rough + (0.24 - rough) * sk.rim
            rough = rough + (0.12 - rough) * sk.disc
            rough = rough + (0.05 - rough) * wp.max(sk.cup, sk.lining)
            rough = wp.clamp(rough, 0.04, 0.60)
            rough = rough + (gt.rough - rough) * gt.f
            acc_r = acc_r + rough + (vt.rough - rough) * fv
            # (the root gradient on d_ao first: d_ao x exactly 1.0 stays d_ao, so a skin texel keeps the live line's
            # fused multiply-add on CUDA; behind the groove factor it moved 15 plain head texels' AO by one level)
            acc_ao = acc_ao + d_ao[tid] * (1.0 + (gt.ao - 1.0) * gt.f) * (1.0 - 0.30 * sk.groove * (1.0 - fg))
            # (Toksvig kept off the sucker parts too: it pushed the 0.05 cups to 0.12-0.28, r4 review)
            acc_x = acc_x + wp.clamp(wp.max(wp.max(sk.cup, sk.lining), wp.max(0.7 * sk.groove, sk.disc + sk.rim)),
                                     0.0, 1.0)
            acc_met = acc_met + gt.metal * gt.f + vt.metal * fv + hl.metal * (1.0 - gt.f - fv)
            # (the lip counts as thin tissue: the runtime's subsurface makes it translucent, ORAL_REFERENCE §5)
            # (no flesh subsurface under a growth: the growths mesh carries its own; the display patterns fade off
            # growth texels, the mottle to its neutral 0.5)
            # (the halo's raised transmission: its thin mask, at least hl.trans, 0 off a halo)
            acc_m = acc_m + wp.vec4(wp.max(wp.max(thin, 0.5 * sk.lip), hl.trans) * (1.0 - sh), sk.ventral,
                                    wp.clamp(sk.rim + 0.66 * sk.disc + 0.33 * sk.cup, 0.0, 1.0), sk.prand)
            acc_d = acc_d + wp.vec4(sk.spots * (1.0 - sh), sk.eyering * (1.0 - sh),
                                    wp.max(sk.band, sk.blotch) * (1.0 - sh), wp.clamp(0.5 + sk.mottle * (1.0 - sh),
                                                                                     0.0, 1.0))
            # the GROWTH pack: R the id mask, G iridescence, B emissive mask, A the pulse's phase (the crystal's or
            # the vein cell's random: R10's cellular phase field)
            gph = gt.phase
            if fv > gt.f:
                gph = vt.phase
            # (R: the growth's share alone; the halo is the skin's, in its own channels)
            acc_g = acc_g + wp.vec4(sh, gt.irid * gt.f, wp.max(gt.emis * gt.f, vt.emis * (1.0 - gt.f)), gph)
            hits = hits + 1
    if hits == 0:
        return
    fh = float(hits)
    # Toksvig (craft guide 00.48, 11.44): the averaged normal's lost length is sub-texel relief the map can no longer
    # show; it widens the highlight instead
    ln = wp.length(acc_n) / fh
    # (not on the wet cups and lining, and gentler in the grooves: r4 review, every groove lit a white polygon halo)
    var = 0.5 * wp.clamp((1.0 - ln) / wp.max(ln, 1.0e-4), 0.0, 1.0) * (1.0 - acc_x / fh)
    r = acc_r / fh
    a = r * r
    r = wp.sqrt(wp.sqrt(a * a + var))
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    o_orm[tid] = wp.vec3(acc_ao / fh, wp.clamp(r, 0.0, 1.0), acc_met / fh)
    o_mask[tid] = acc_m / fh
    o_disp[tid] = acc_d / fh
    o_grow[tid] = acc_g / fh


def spot_centres(prog, spec):
    """the leucophore white spots, paired: frontal (between and in front of the turrets) and dorsal mantle (two-fifths
    of the axis from the apex, either side of the midline), placed from the anatomy and settled onto the block-out
    (r4's fixed world points sat on its upright mantle)"""
    from .octopus import axis_s, body_axis, eye_level
    from .octopus_sculpt import settle
    ye, ze = eye_level(spec)
    P, n, b, t = body_axis(spec)
    i = int(np.searchsorted(axis_s(P), 0.42))
    top = P[i] + n[i] * 0.07                         # above the mantle's dorsal surface: settle pulls it down onto it
    pts = np.array([[0.008, ye - 0.012, ze + 0.030], [-0.008, ye - 0.012, ze + 0.030], top + b[i] * 0.024,
                    top - b[i] * 0.024])
    return settle(prog, pts)[0]


# ------------------------------------------------------------------------------------------- (polish 1) the arm's section
# and the web margin's section
# the arms' section harmonics as octopus.build_sdf sweeps them (a2, phi2, a3, phi3, a4, aspect; sdf.sd_sweep's profile:
# rounder aboral, flatter oral): skin_at continues the arm coordinate off the tube from this radius (sec_k), the
# sculpt's skin_net and the streak audit replicate it, and run checks it against the block-out program's own nodes
ARM_SECTION = (0.06, 0.0, 0.05, 0.0, 0.0, 0.92)
RIM_NONE = 1.0          # web_rim's value away from every web margin (metres, past every ramp: skin_at reads < 0.5)


def section_k(alpha, sec=ARM_SECTION, xp=np):
    """sec_k in numpy (or cupy, xp): the arm's section radius over the local r at the angle alpha from the aboral side"""
    a2, p2, a3, p3, a4, asp = sec
    k = 1.0 + a2 * xp.cos(2.0 * (alpha - p2)) + a3 * xp.cos(3.0 * (alpha - p3)) + a4 * xp.cos(4.0 * alpha)
    return k * asp / xp.sqrt(asp * asp * xp.cos(alpha) ** 2 + xp.sin(alpha) ** 2)


def foot_frame(q0, P, N, T, s0, xp=np, iters=20):
    """skin_at's head-set arm frame (polish 1) in numpy or cupy (xp), for the sculpt's skin_net and the streak audit's
    replica: the FOOT POINT near the polyline's nearest point s0 (0..1) on the reference centreline P (node frames N,
    node tangents T: node_tangents), by sdf.sd_sweep's bracket of two nodes and bisection on g(u) = (q0 - C(u)) . T(u);
    the sweep's frame there (T interpolated, N interpolated and made normal to it, B = T x N). Returns dict(s (0..1),
    seg, ft, bd = |q0 - C(u)|, alpha)"""
    n = P.shape[0]
    umax = (n - 1) - 1.0e-6

    def at(u):
        j = xp.minimum(xp.floor(u).astype(xp.int64), n - 2)
        f = (u - j)[:, None]
        t = T[j] * (1.0 - f) + T[j + 1] * f
        return j, f, P[j] + (P[j + 1] - P[j]) * f, t / xp.linalg.norm(t, axis=1, keepdims=True)

    def g(u):
        _, _, c, t = at(u)
        return ((q0 - c) * t).sum(1)
    un = s0 * (n - 1)
    lo = xp.maximum(un - 2.0, 0.0)
    hi = xp.minimum(un + 2.0, umax)
    glo, ghi = g(lo), g(hi)
    br = (glo > 0.0) & (ghi < 0.0)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        pos = g(mid) > 0.0
        lo = xp.where(br & pos, mid, lo)
        hi = xp.where(br & ~pos, mid, hi)
    un = xp.where(br, 0.5 * (lo + hi), un)
    c0 = ~br & (glo <= 0.0) & (lo <= 0.0)
    un = xp.where(c0, 0.0, un)
    un = xp.where(~br & ~c0 & (ghi >= 0.0) & (hi >= umax), umax, un)
    j, f, c, t = at(un)
    nn = N[j] * (1.0 - f) + N[j + 1] * f
    nn = nn / xp.linalg.norm(nn, axis=1, keepdims=True)
    nn = nn - t * (nn * t).sum(1, keepdims=True)
    nn = nn / xp.linalg.norm(nn, axis=1, keepdims=True)
    v = q0 - c
    return dict(s=un / (n - 1), seg=j, ft=f[:, 0], bd=xp.linalg.norm(v, axis=1),
                alpha=xp.arctan2((v * xp.cross(t, nn)).sum(1), (v * nn).sum(1)))


def arm_section(prog):
    """the arms' section harmonics as the block-out program holds them (the nodes of sweeps 'arm 0'..'arm 7'): (a2,
    phi2, a3, phi3, a4, aspect), one section for every arm and node"""
    out = []
    for i, nm in enumerate(prog.names):
        if nm.startswith('arm ') and nm[4:].isdigit():
            start, cnt = int(prog.par[i][0]), int(prog.par[i][1])
            Rn = np.asarray(prog.node_r[start:start + cnt], np.float64)
            Hn = np.asarray(prog.node_h[start:start + cnt], np.float64)
            out.append(np.column_stack([Rn[:, 1], Rn[:, 2], Hn[:, 0], Hn[:, 1], Hn[:, 2], Rn[:, 3]]))
    S = np.concatenate(out)
    assert np.allclose(S, S[0], atol=1e-6), 'the arms carry more than one section'
    return tuple(float(v) for v in S[0])


def node_tangents(P):
    """sdf.node_tangent at every node of a centreline: normalize(P[j+1] - P[j-1]), one-sided at the ends (loft.rmf's
    tangents, the arms' frames)"""
    n = len(P)
    T = P[np.minimum(np.arange(n) + 1, n - 1)] - P[np.maximum(np.arange(n) - 1, 0)]
    return T / np.linalg.norm(T, axis=1, keepdims=True)


def web_margins(spec, arms, n=801):
    """every web's free MARGIN, densely, with the analytic sheet's frame there: octopus.web_patch's sheet (1 - l) SA(s)
    + l SB(s) between two arms' facing side lines out to s = margin_s(l) (at most its cap), lifted near the margin as
    web_patch lifts it (crown v6b: octopus.web_lift, the webs' tent: it keeps the margin's middle, lowers its ends 3-5
    mm toward the arms and tilts the sheet's frame along it); the block-out's web is that sheet's shell, so its edge is
    a half-cylinder of the margin's half-thickness (0.9 mm) round this curve. Returns dict(M (k, 3) the curve, T along
    it, O outward in the sheet (+s), N aboral (up), web (k,))"""
    from .octopus import N_ARMS, arm_side, margin_s, web_lift, web_plan
    plan = web_plan(spec, arms)
    order = plan['order']
    lam = 0.5 - 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, n))     # dense toward the arms, as web_patch's columns
    out = dict(M=[], T=[], O=[], N=[], web=[])
    for j in range(N_ARMS):
        ia, ib = order[j], order[(j + 1) % N_ARMS]
        cap = max(plan['sw'][ia], plan['sw'][ib]) + 0.002

        def sheet(s):
            A = np.array([arm_side(arms[ia], si, spec, +1) for si in s])
            B = np.array([arm_side(arms[ib], si, spec, -1) for si in s])
            M_ = (1.0 - lam)[:, None] * A + lam[:, None] * B
            M_[:, 1] += web_lift(spec, plan, j, lam, s)
            return M_
        sm = np.minimum(margin_s(lam, plan, j), cap)
        Mj = sheet(sm)
        Sj = (Mj - sheet(np.maximum(sm - 1.0e-4, 0.0))) / 1.0e-4
        Tj = np.gradient(Mj, axis=0)
        Tj /= np.maximum(np.linalg.norm(Tj, axis=1, keepdims=True), 1e-12)
        Nj = np.cross(Tj, Sj)
        Nj /= np.maximum(np.linalg.norm(Nj, axis=1, keepdims=True), 1e-12)
        Nj[Nj[:, 1] < 0.0] *= -1.0
        Oj = np.cross(Nj, Tj)
        Oj[np.einsum('ij,ij->i', Oj, Sj) < 0.0] *= -1.0
        for k, v in (('M', Mj), ('T', Tj), ('O', Oj), ('N', Nj)):
            out[k].append(v)
        out['web'].append(np.full(n, j))
    return {k: np.concatenate(v) for k, v in out.items()}


def web_rim(P, fr, reach=0.020):
    """the web margin's SECTION coordinate at points P (n, 3): the signed arc distance from its crest round the
    half-cylinder edge (h = (P - m).N, e = (P - m).O at the nearest margin point m, segment-refined within its web): on
    the edge (e > 0) |P - m| atan2(-h, e), on the faces (e <= 0) -sign(h) (|h| pi/2 + |e|). Negative over the aboral
    face, 0 on the crest, positive over the oral face; continuous across the crest and blind to where the cage put its
    layers' boundary. RIM_NONE past `reach` from every margin or beside its ends (more than 1 mm along it)"""
    from scipy.spatial import cKDTree
    P = np.asarray(P, np.float64)
    Mf, Tf, Of, Nf, W = fr['M'], fr['T'], fr['O'], fr['N'], fr['web']
    _, k = cKDTree(Mf).query(P)
    best_d = np.full(len(P), np.inf)
    best_i = np.zeros(len(P), np.int64)
    best_t = np.zeros(len(P))
    for dk in (-1, 0):
        i0 = np.clip(k + dk, 0, len(Mf) - 2)
        e_ = Mf[i0 + 1] - Mf[i0]
        t = np.clip(np.einsum('ij,ij->i', P - Mf[i0], e_) / np.maximum(np.einsum('ij,ij->i', e_, e_), 1e-20), 0.0, 1.0)
        d = np.linalg.norm(P - (Mf[i0] + e_ * t[:, None]), axis=1)
        d = np.where(W[i0] == W[i0 + 1], d, np.inf)
        b = d < best_d
        best_d, best_i, best_t = np.where(b, d, best_d), np.where(b, i0, best_i), np.where(b, t, best_t)
    tt = best_t[:, None]
    lerp = lambda X: X[best_i] * (1.0 - tt) + X[best_i + 1] * tt
    dv = P - lerp(Mf)
    h = np.einsum('ij,ij->i', dv, lerp(Nf))
    e = np.einsum('ij,ij->i', dv, lerp(Of))
    along = np.einsum('ij,ij->i', dv, lerp(Tf))
    a = np.where(e > 0.0, np.hypot(h, e) * np.arctan2(-h, e), -np.sign(h) * (np.abs(h) * 0.5 * np.pi + np.abs(e)))
    ok = np.isfinite(best_d) & (best_d < reach) & (np.abs(along) < 0.001)
    return np.where(ok, a, RIM_NONE)


def rim_map(drivers, spec, arms):
    """web_rim per texel of a head set (image order, float32): on the bake's base points of the crown's two layers
    (regions 1 and 2) where it agrees with the layer to within 2 mm of the crest (the cage's boundary sits on the crest:
    99.1-100 % of the texels within 1 mm either side are their side's layer; 1,017 oral texels at mid-sector in webs B
    and D, 130 mm out, read 20 mm aboral, where the sheet's frame no longer describes that face), RIM_NONE elsewhere"""
    base = np.asarray(drivers['base'])
    reg = np.asarray(drivers['region'])
    out = np.full(reg.shape, RIM_NONE, np.float32)
    sel = (base[..., 3] > 0.5) & np.isin(reg, (1, 2))
    a = web_rim(base[sel][:, :3], web_margins(spec, arms))
    rg = reg[sel]
    a = np.where(((rg == 2) & (a < -0.002)) | ((rg == 1) & (a > 0.002) & (a < 0.5)), RIM_NONE, a)
    out[sel] = a.astype(np.float32)
    return out


SKIN_RECIPE = dict(
    oct_a10=0.075,         # the mottling octaves' ln L RMS at 10 mm (study §10a: 0.05-0.10)
    mottle=1.0,            # the chromatophore-state ramp's strength (dark <-> brick)
    speck=0.30,            # the specks' ln L amplitude (the lightest and darkest few per cent of the paint)
    vein=None,             # a VEIN family painted over the skin ('ember', 'arc': growth.RECIPES), None = none
    vein_w=0.001,          # its half width (m) at the crown's scale, at least 1.6 texels (skin_at) [I]
    vein_scale=6.0,        # its network's cell size in patch spacings (~17 mm on the head) [I]
)


def run(low, drivers, set_kind, size, spec, arms, order, inst, tables, texel, prog, ss=2, log=print,
        recipe=SKIN_RECIPE, conv_scale=None):
    """the material pass over one texture set. low: dict(V, F (the set's triangles), UV, N, TAN, ATTR);
    drivers: the bake's result dict (image order; 'mat' = its packed material ids, absent on older bakes: all skin);
    conv_scale: this set's convexity scales (calib.conv_scale: the base's own, measured once; on a look, its base's
    frozen record, calib.conv_set), None = measured here on these drivers' skin texels.
    Returns image-order uint8 maps: albedo (sRGB), normal (GL), orm (AO, roughness, metalness), masks (thin, ventral,
    sucker, patch random), display (white spots, eye ring, dark bands and blotches, mottle: what the runtime's colour
    change drives), growth (R the growth id mask, G iridescence, B emissive mask, A pulse phase; all zero on a
    creature without growths or veins: export it only when it is not)"""
    import time
    from .. import calib
    from .octopus import arm_azimuths, arm_radius, body_axis, eye_geom, funnel_geom
    from .octopus_sculpt import PATCH
    t0 = time.time()
    uvm = M.uv_bvh(low['F'], low['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(low['V'], low['F'], low['N'], low['TAN'], low['ATTR'])
    # the relief drivers at the reference study's physical scales (AO_local, convexity fine and mid)
    # (polish 1) and on the head set the web margins' section coordinate per texel (rim_map), with the arms' section
    # (the continued arm coordinate's start) checked against the block-out program it was baked from
    rim = np.full((size, size), RIM_NONE, np.float32)
    if set_kind == 0:
        sec = arm_section(prog)
        assert np.allclose(sec, ARM_SECTION, atol=1e-6), f'octopus.build_sdf sweeps the arms with {sec}, not ARM_SECTION'
        rim = rim_map(drivers, spec, arms)
    D = M.driver_arrays({**drivers, **calib.relief_drivers(drivers, 1.0 / texel, scale=conv_scale), 'rim': rim})
    # the GROWTHS (material_ids_v2.md): the bake's packed ids, the planned pieces, the family table
    if 'mat' not in D:
        D['mat'] = wp.zeros(size * size, dtype=wp.int32)
    ggrid, grq, gA, gB, gQ, gZ = GR.gpu_instances(GR.saved_instances(inst))
    ghq = GR.halo_query(GR.saved_instances(inst))         # the halo's reach from a piece's midpoint (0: no halo here)
    FT = wp.array(GR.family_table(), dtype=wp.float32)
    az = arm_azimuths()
    ref = arms[order[0]]
    eL, eR = eye_geom(spec, 1), eye_geom(spec, -1)
    mo = prog.mouth
    fa, fb, fra, frb = funnel_geom(spec)
    # the vein network's minimum cell (skin_at): its lattice's anchor, U on the reference arm where the 12.8 texels
    # first exceed the arm network's cell (P[46] x the arm's patch, both in the arm's anatomical coordinate)
    sc_v = np.maximum(arm_radius(tables[0], spec) / spec['arm_r0'], 0.3)
    b_v = 12.8 * texel / sc_v > recipe.get('vein_scale', 6.0) * PATCH['arm']
    u_c = float(tables[1][np.argmax(b_v)]) if b_v.any() else 0.0
    P = np.concatenate([[PATCH['head'], PATCH['arm'], PATCH['disorder'], texel, spec['arm_r0'], spec['arm_tip_r'],
                         az[order[0]]], eL[2], eR[2], [eL[3]], spot_centres(prog, spec).ravel(), [0.0045],
                        [mo['c'][1], mo['R'], mo['r'], mo['r_open']], fa, fb, [fra, frb],
                        [recipe['oct_a10'], recipe['mottle'], recipe['speck']],
                        [mo.get('ax', mo['r_open']), mo.get('az', mo['r_open'])],
                        [recipe.get('vein_w', 0.0), float(GR.FAMILY_ID.get(recipe.get('vein'), 0)),
                         recipe.get('vein_scale', 6.0), u_c], ARM_SECTION]).astype(np.float32)
    assert len(P) == 54, len(P)
    sp = np.asarray(inst['suckers_p'], np.float32)
    grid = wp.HashGrid(64, 64, 64)
    spd = wp.array(sp, dtype=wp.vec3)
    grid.build(spd, 0.0065)
    n = size * size
    o_alb = wp.zeros(n, dtype=wp.vec3)
    o_nrm = wp.zeros(n, dtype=wp.vec3)
    o_orm = wp.zeros(n, dtype=wp.vec3)
    o_mask = wp.zeros(n, dtype=wp.vec4)
    o_disp = wp.zeros(n, dtype=wp.vec4)
    o_grow = wp.zeros(n, dtype=wp.vec4)
    st, U, R = tables
    # the arm's true radius on the tables' s (R is the straightened coordinate's, clamped) and the body axis at 64
    # nodes with its dorsal normals (the ventral side of the mantle and head)
    rad = arm_radius(st, spec)
    P_ax, n_ax, _, _ = body_axis(spec)
    sel = np.linspace(0, len(P_ax) - 1, 64).round().astype(int)
    wp.launch(k_skin, dim=n, inputs=[uvm.id, size, ss, set_kind, lpos, lnrm, ltan, lattr, D['normal'], D['ao'],
                                     D['cavity'], D['thickness'], D['curvature'], D['height'], D['base'], D['region'],
                                     D['ao_local'], D['conv'], D['conv_mid'],
                                     wp.array(P, dtype=wp.float32), wp.array(az.astype(np.float32), dtype=wp.float32),
                                     wp.array(ref[0].astype(np.float32), dtype=wp.vec3),
                                     wp.array(ref[1].astype(np.float32), dtype=wp.vec3),
                                     wp.array(ref[2].astype(np.float32), dtype=wp.vec3),
                                     wp.array(node_tangents(np.asarray(ref[0], np.float64)).astype(np.float32),
                                              dtype=wp.vec3),
                                     wp.array(U.astype(np.float32), dtype=wp.float32),
                                     wp.array(R.astype(np.float32), dtype=wp.float32),
                                     wp.array(rad.astype(np.float32), dtype=wp.float32),
                                     wp.array(P_ax[sel].astype(np.float32), dtype=wp.vec3),
                                     wp.array(n_ax[sel].astype(np.float32), dtype=wp.vec3), grid.id, spd,
                                     wp.array(np.asarray(inst['suckers_n'], np.float32), dtype=wp.vec3),
                                     wp.array(np.asarray(inst['suckers_d'], np.float32), dtype=wp.float32),
                                     PATCH['seed_head'], PATCH['seed_arm'], o_alb, o_nrm, o_orm, o_mask, o_disp,
                                     o_grow, D['mat'], ggrid.id, float(grq), gA, gB, gQ, gZ, FT, float(ghq), D['rim']])
    wp.synchronize()
    cov = np.asarray(drivers['normal'])[..., 3] > 0
    alb = np.asarray(o_alb.numpy()).reshape(size, size, 3)[::-1]
    nrm = np.asarray(o_nrm.numpy()).reshape(size, size, 3)[::-1]
    orm = np.asarray(o_orm.numpy()).reshape(size, size, 3)[::-1]
    msk = np.asarray(o_mask.numpy()).reshape(size, size, 4)[::-1]
    dsp = np.asarray(o_disp.numpy()).reshape(size, size, 4)[::-1]
    grw = np.asarray(o_grow.numpy()).reshape(size, size, 4)[::-1]
    from ..bake import dilate_all
    dil, grown = dilate_all(dict(normal=np.concatenate([nrm, cov[..., None].astype(np.float32)], -1), alb=alb,
                                 orm=orm, msk=msk, dsp=dsp, grw=grw), 24)
    alb_s = M.srgb_oetf(np.where(grown[..., None], dil['alb'], 0.5))
    nrm_t = np.where(grown[..., None], dil['normal'][..., :3], [0.0, 0.0, 1.0])
    out = dict(albedo=(alb_s * 255 + 0.5).astype(np.uint8),
               normal=np.clip((nrm_t * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8),
               orm=np.clip(np.where(grown[..., None], dil['orm'], [1.0, 0.5, 0.0]) * 255 + 0.5, 0, 255).astype(np.uint8),
               masks=np.clip(np.where(grown[..., None], dil['msk'], 0.0) * 255 + 0.5, 0, 255).astype(np.uint8),
               display=np.clip(np.where(grown[..., None], dil['dsp'], 0.0) * 255 + 0.5, 0, 255).astype(np.uint8),
               growth=np.clip(np.where(grown[..., None], dil['grw'], 0.0) * 255 + 0.5, 0, 255).astype(np.uint8))
    log(f'[skin] set {"arms" if set_kind else "head"} {size}^2 x ss {ss}: {time.time()-t0:.1f}s')
    return out
