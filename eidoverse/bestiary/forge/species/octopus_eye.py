"""The octopus's EYE: its own part (craft guide 16.4-16.5: an eye is a layered assembly seated in a socket, not
painted skin), with a procedurally PAINTED iris.

  * the EYEBALL: a cube-sphere quad mesh (no poles) of radius Re at the eye's centre E, its front face on the eye's
    outward axis; UVs are the orthographic projection onto the iris plane, so the painting lands in eye space;
  * the IRIS (Octopus vulgaris; the live eyes of research/refs/colour/05, 06, 08 and refs/body/04, 08, measured in
    work/bestiary/patches/eye.md) is GRANULAR, not fibrous: chromatophore dots 0.1-0.3 mm across (yellow, orange,
    red, brown) packed in clusters over a gold iridophore layer, the gold showing between the clusters as flecks and
    a broken net of short vermiculate runs (cells ~1.3 mm: body ref 08) over the whole iris, denser under the pupil
    (ref 05). Its colour is the chromatophores', so it follows the skin's display state (red-orange in 05, pale gold
    in 06): the masks carry their cover for the runtime's tint. The FLECKS (patches/iris_flecks.md) are painted to the
    live eyes' numbers at their own pixel scale (refs 05, body 08: count per mm2, sizes, contrast and colour against
    the iris round them): peach to yellow gold over a saturated red-orange whose net cells darken toward the middle;
    the gold specks and runs are reflectors, so they carry the masks' G (a glint that turns with the view) and the
    engine's lowest roughness;
  * the PUPIL in daylight (the scenes' light): a crisp dark horizontal bar 4.4 : 1 at its middle with round ends a
    little fuller than it (1.10 x its height; body ref 04 in daylight: 4.4 : 1 at its middle, a dumbbell with ends
    1.45 x; body ref 08 in bright light: ~4 : 1, ends ~1.05 x; ref 05 under a flash, dilated: 2.33 : 1, 0.72 of the
    visible eye's width, which sets the length), with no halo or collar round it, level with the horizon (the
    statocysts hold it as the body tilts, so its long axis is the iris plane's world-horizontal direction);
  * the iridophore BAND under the pupil is a reflector, bright or dark with the view (refs 05, 06, 08; body 04, 08):
    its reflection lives in a view-dependent channel (the masks' G, the runtime's iridescence), not in the albedo;
  * the OUTER SURFACE (the wet skin over the eye) is smooth: no relief, roughness 0.06 (the reflective flecks at the
    engine's floor, 0.0525), so its highlight stays whole (all iris detail is albedo and the masks);
  * the socket and lids are the HEAD's (the sculpt plan carves the socket and lays the lid rims).

    eye_mesh(spec, side) -> dict(V, Q, UV, N, axes)
    paint_iris(size, seed, masks=False, Re=None) -> albedo (sRGB uint8), height (zeros: the outer surface is smooth),
        roughness (uint8) [, masks (RGBA uint8, linear data): R chromatophore cover (the display tint), G iridophore
        reflectors (view-dependent: the band and the gold flecks), B pupil, A the cover the chromatophores add when the
        display darkens]
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc
from .octopus import SPEC, eye_geom

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})   # forward-only; the dot search loop left rolled

PUP_A = wp.constant(0.52)       # the pupil (eyeball radii) in DAYLIGHT, the scenes' light: half-length a (0.72 of the
PUP_B = wp.constant(0.118)      # visible eye's width, ref 05), half-height b at the middle (4.4 : 1, body ref 04), the
PUP_E = wp.constant(0.130)      # end bulbs' radius e (1.10 x b: a rounded bar, as refs 05 / 06 / 08 and body 08; only
PUP_K = wp.constant(0.05)       # the low-res body 04 swells 1.45 x, and 1.25 x read as a dog bone) and the fillet k
CHROM_MM = wp.constant(0.16)    # the chromatophore lattice (mm): dots 0.1-0.3 mm across, touching when expanded
ROUGH = wp.constant(0.06)       # the outer surface: wet, smooth (the flecks: ROUGH_FL)
# the FLECKS (patches/iris_flecks.md; measured on refs colour 05 and body 08 at their own pixel scale): the gold specks
# and runs are reflectors, so they carry the masks' G (the runtime's thin film: a glint that turns with the view) and
# the lowest roughness the engine renders (three's getRoughness floors it at 0.0525); the chromatophores darken in the
# cells the gold net rings (the photos' darks: 0.40-0.48 of the iris round them at q05, the paint's were 0.62)
ROUGH_FL = wp.constant(0.0525)  # the flecks' roughness: the engine's floor (any lower renders the same)
FLECK_G = wp.constant(0.88)     # their G outside the band: ref 05's flecks over the pupil are 0.88 as pale (B/R lift
#                                 over the iris round them) as those under it, where the band's G is 1
SPECK_RATE = wp.constant(0.20)  # the lone specks' share of the drawn-back dots, x the zone's gold share over 0.09 (so
#                                 they gather under the pupil, ref 05: 0.70 flecks / mm2 over it, 1.25 under)
CELL_DK = wp.constant(wp.vec3(0.50, 0.44, 0.28))   # the chromatophores in the middle of the net's cells, x RGB
#                                 (linear): darker and redder, as the photos' darks (sat 1.2 x the iris's, hue -1 deg)
IRIS_GAIN = wp.constant(1.06)   # the iris's albedo, whole: the fewer flecks the photos allow (the old paint had more
#                                 per mm2 than any of them) left t23's iris / skin L at 1.31; x 1.06 lifts it a little
#                                 over the old 1.35 (contrasts are ratios: unchanged)


def eye_axes(spec, side):
    """the eye's frame: out (the optical axis), h (iris-plane world-horizontal, the pupil's long axis), u (up)"""
    c, out, E, Re = eye_geom(spec, side)
    Y = np.array([0.0, 1.0, 0.0])
    h = np.cross(Y, out)
    h /= np.linalg.norm(h)
    u = np.cross(out, h)
    return E, Re, out, h, u


def eye_mesh(spec, side, n=10):
    """the eyeball: six n x n quad grids on a cube projected onto the sphere, the front face on the optical axis"""
    E, Re, out, h, u = eye_axes(spec, side)
    R = np.column_stack([h, u, out])                 # local (x = h, y = u, z = out) -> world
    t = np.linspace(-1.0, 1.0, n + 1)
    V, Q = [], []
    faces = [(np.array([0, 0, 1.0]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0])),     # front
             (np.array([0, 0, -1.0]), np.array([-1.0, 0, 0]), np.array([0, 1.0, 0])),   # back
             (np.array([1.0, 0, 0]), np.array([0, 0, -1.0]), np.array([0, 1.0, 0])),
             (np.array([-1.0, 0, 0]), np.array([0, 0, 1.0]), np.array([0, 1.0, 0])),
             (np.array([0, 1.0, 0]), np.array([1.0, 0, 0]), np.array([0, 0, -1.0])),
             (np.array([0, -1.0, 0]), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))]
    for c0, a, b in faces:
        base = len(V)
        for j in range(n + 1):
            for i in range(n + 1):
                p = c0 + a * t[i] + b * t[j]
                V.append(p / np.linalg.norm(p))
        for j in range(n):
            for i in range(n):
                k = base + j * (n + 1) + i
                Q.append([k, k + 1, k + n + 2, k + n + 1])
    Vl = np.array(V)
    Q = np.array(Q)
    # weld the cube's shared edges
    key = np.round(Vl * 1e6).astype(np.int64)
    _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    Vl = Vl[idx]
    Q = inv.reshape(-1)[Q]
    Vw = E + (Vl * Re) @ R.T
    N = Vl @ R.T
    # the iris plane's orthographic projection (front hemisphere; the hidden back maps onto it too)
    UV = np.column_stack([0.5 + 0.5 * Vl[:, 0], 0.5 + 0.5 * Vl[:, 1]])
    return dict(V=Vw, Q=Q, UV=UV, N=N, E=E, Re=Re, axes=(out, h, u))


@wp.func
def pupil_sd(x: float, y: float):
    """the signed distance (eyeball radii) to the pupil, negative inside: a bar (a box out to the bulbs' centres,
    half-height b) united smoothly (polynomial smooth min, k) with the two round end bulbs of radius e whose outer edges
    reach x = +-a (exact distances both, so the outline the edge is drawn on is exact away from the fillet)"""
    ax = wp.abs(x)
    ay = wp.abs(y)
    xe = PUP_A - PUP_E
    dx = ax - xe
    dy = ay - PUP_B
    bar = wp.length(wp.vec2(wp.max(dx, 0.0), wp.max(dy, 0.0))) + wp.min(wp.max(dx, dy), 0.0)
    bulb = wp.length(wp.vec2(dx, ay)) - PUP_E
    h = wp.clamp(0.5 + 0.5 * (bulb - bar) / PUP_K, 0.0, 1.0)
    return bulb * (1.0 - h) + bar * h - PUP_K * h * (1.0 - h)


@wp.func
def gold_frac(x: float, y: float):
    """the share of the gold layer left exposed between the chromatophore clusters, by zone (x, y in eyeball radii): a
    base share over the whole iris (body ref 08's net), more in the band under the pupil and at its ends (ref 05); the
    albedo under / over the pupil 1.43 (t23), the rest of ref 05's flash-lit brightness under it is the band's
    reflection (the masks' G), not pigment (body refs 04 / 08 under top light: darker under the pupil). The band's
    share 0.18 -> 0.13 (iris_flecks.md: the gold there covered more of the iris than any photo's)"""
    t = -(y + PUP_B) - 0.09                            # from a line 0.09 below the pupil's lower edge
    ax = wp.abs(x)
    under = wp.exp(-t * t / 0.030) * (1.0 - proc.smoothstep(PUP_A * 0.70, PUP_A * 1.50, ax))
    lower = proc.smoothstep(0.05, -0.55, y) * (1.0 - proc.smoothstep(0.55, 0.90, ax))
    ex = ax - PUP_A
    ends = wp.exp(-(ex * ex + y * y) / 0.008)
    return 0.13 + 0.13 * under + 0.08 * lower + 0.10 * ends


@wp.func
def runs(q: wp.vec2, seed: int):
    """the meandering ~1.2 mm network the gold gathers on (ref 05's lower iris: its flecks 0.5 mm across, 1.2 mm
    apart, t23): |n| of a warped noise, 0 on its zero set"""
    p = wp.vec3(q[0], q[1], 0.0)
    wq = wp.vec3(proc.noise3(p * 0.67, seed + 3), proc.noise3(p * 0.67 + wp.vec3(5.2, 1.3, 0.0), seed + 4), 0.0)
    return wp.abs(proc.fbm3((p + wq * 0.36) * 0.75, 2, 2.0, 0.45, seed + 5))


@wp.func
def retract(q: wp.vec2, frac: float, seed: int):
    """how far the chromatophores at q (mm) are drawn back from the gold layer, 0..1: the zone's share (frac), more
    along the network, so the chromatophores thin out round the gold runs"""
    run = 1.0 - proc.smoothstep(0.0, 0.16, runs(q, seed))
    return wp.clamp(frac * (0.3 + 2.4 * run), 0.0, 1.0)


@wp.func
def gold_run(q: wp.vec2, frac: float, px_mm: float, seed: int):
    """the gold runs themselves, 0..1: the network's zero set about 0.2 mm thick (w 0.045 -> 0.052, iris_flecks.md: the
    photos' flecks run larger at the top), cut into pieces 0.3-1 mm long by a second noise that keeps more of it where
    the zone's share (frac) is larger"""
    p = wp.vec3(q[0], q[1], 0.0)
    w = 0.052
    aa = 0.45 * px_mm
    line = 1.0 - proc.smoothstep(w - aa, w + aa, runs(q, seed))
    keep = wp.clamp(frac / 0.45, 0.0, 1.0)
    thr = 0.74 - 0.40 * keep
    cut = proc.smoothstep(thr - 0.02, thr + 0.02, 0.5 + 0.5 * proc.noise3(p * 1.33 + wp.vec3(0.0, 0.0, 7.0), seed + 6))
    return line * cut


@wp.func
def chrom_colour(u: float, v: float):
    """one chromatophore's colour, linear (O. vulgaris: yellow, orange, red, brown; Froesch & Messenger 1978), with a
    small per-cell brightness jitter"""
    # (t23: the iris over the forge skin round the eye at L 1.5, ref 05's 1.59 with its band flash-lit, refs 06 / 08
    # 1.1-0.8; G/R 0.33 linear, between ref 05's red display 0.27 and the forge skin's 0.44; the first pass sat at
    # 0.36, a dull brick-pink. iris_flecks.md: blue lowered, the iris's saturation 0.64 -> toward the photos' 0.59-0.81)
    c = M.srgb(wp.vec3(0.60, 0.27, 0.08))             # red
    if u < 0.05:
        c = M.srgb(wp.vec3(0.70, 0.46, 0.10))         # yellow
    elif u < 0.40:
        c = M.srgb(wp.vec3(0.65, 0.35, 0.08))         # orange
    elif u > 0.90:
        c = M.srgb(wp.vec3(0.42, 0.17, 0.06))         # brown: a deep red-brown (the photos' darks are saturated reds)
    return c * (0.96 + 0.08 * v)


@wp.kernel
def k_iris(size: int, seed: int, re_mm: float, alb: wp.array(dtype=wp.vec3), msk: wp.array(dtype=wp.vec4),
           rough: wp.array(dtype=wp.float32)):
    tid = wp.tid()
    px = tid % size
    py = tid // size
    # iris-plane coordinates in eyeball radii (x along the pupil, y up) and in millimetres
    x = (float(px) + 0.5) / float(size) * 2.0 - 1.0
    y = (float(py) + 0.5) / float(size) * 2.0 - 1.0
    r = wp.sqrt(x * x + y * y)
    q = wp.vec2(x * re_mm, y * re_mm)
    px_mm = 2.0 * re_mm / float(size)
    # the pupil: crisp (one texel of antialiasing), no rim, no collar
    pupil = wp.clamp(0.5 - pupil_sd(x, y) / (2.0 / float(size)), 0.0, 1.0)
    # the chromatophores: a jittered lattice of dots 0.1-0.3 mm across, each drawn back by the retraction at its own
    # site (expanded they touch and the iris reads red-orange; drawn back, gold specks open between them; a few drawn
    # back to a point alone, the isolated specks over the pupil), the texel taking the colour of the dot that covers it
    # most; the expanded radii (the dark display) too
    gx = q[0] / CHROM_MM
    gy = q[1] / CHROM_MM
    i0 = int(wp.floor(gx))
    j0 = int(wp.floor(gy))
    cov = float(0.0)
    cov_e = float(0.0)
    dcol = wp.vec3(0.0)
    dmin = float(1.0e9)
    gnear = float(0.0)
    speck = float(0.0)
    spk_t = float(0.0)
    for k in range(9):
        i = i0 + k % 3 - 1
        j = j0 + k // 3 - 1
        h = proc.hash3i(i, j, 0, seed + 101)
        rr = proc.rnd3(h)
        rc = proc.rnd3(proc.lowbias32(h ^ wp.uint32(0x2C1B3C6D)))
        sx = (float(i) + 0.5 + (rr[0] - 0.5) * 0.9) * CHROM_MM
        sy = (float(j) + 0.5 + (rr[1] - 0.5) * 0.9) * CHROM_MM
        fs = gold_frac(sx / re_mm, sy / re_mm)
        g = retract(wp.vec2(sx, sy), fs, seed)
        if rc[2] < SPECK_RATE * (fs - 0.09):
            # a lone gold speck 0.14-0.30 mm across where this dot is drawn back to a point (ref 05), its own place
            # between the peach and the yellow golds
            rs = 0.07 + 0.08 * rc[1]
            ds = wp.sqrt((q[0] - sx) * (q[0] - sx) + (q[1] - sy) * (q[1] - sy))
            sc = wp.clamp((rs - ds) / px_mm + 0.5, 0.0, 1.0)
            if sc > speck:
                speck = sc
                spk_t = proc.rnd3(proc.lowbias32(h ^ wp.uint32(0x68E31DA4)))[0]
            g = wp.max(g, 0.9)
        base_r = 0.13 + 0.02 * rr[2]
        rad = base_r * (1.0 - 0.70 * g)
        rad_e = 1.25 * base_r               # the dark display: every dot spread past its resting size, over the gold
        dx = q[0] - sx
        dy = q[1] - sy
        d = wp.sqrt(dx * dx + dy * dy)
        c = wp.clamp((rad - d) / px_mm + 0.5, 0.0, 1.0) * wp.clamp(rad / (0.5 * px_mm), 0.0, 1.0)
        ce = wp.clamp((rad_e - d) / px_mm + 0.5, 0.0, 1.0) * wp.clamp(rad_e / (0.5 * px_mm), 0.0, 1.0)
        if c > cov:
            cov = c
            dcol = chrom_colour(rc[0], rc[1])
        cov_e = wp.max(cov_e, ce)
        if d < dmin:
            dmin = d
            gnear = g
    # under the dots: the gold iridophore layer where the nearest dot is drawn back, the chromatophores' own tissue in
    # the hairline gaps between expanded dots. The gold per fleck between a peach near the chromatophores' hue and a
    # yellow gold (the photos' bright flecks: hue +1..+5 deg over the iris round them at the median, +6..+11 at q90,
    # saturation 0.79-0.90 x the iris's; refs colour 05, body 08), a lone speck its own, the runs and the gaps a slow
    # drift; a fine glint jitter within
    gf = gold_frac(x, y)
    run_v = gold_run(q, gf, px_mm, seed)
    t_col = wp.clamp(0.40 + 0.90 * proc.noise3(wp.vec3(q[0], q[1], 9.0) * 1.1, seed + 21), 0.0, 1.0)
    if speck > run_v:
        t_col = spk_t
    # (in the band under the pupil the gold keeps about its old brightness: the band's reflection, the masks' G,
    # carries the rest there, as eye.md's under / over)
    band_z = proc.smoothstep(0.16, 0.26, gf)
    gold = M.mix3(M.srgb(wp.vec3(0.95, 0.61, 0.37)), M.srgb(wp.vec3(0.96, 0.78, 0.30)), t_col * t_col)
    gold = gold * (0.86 + 0.22 * (0.5 + 0.5 * proc.noise3(wp.vec3(q[0], q[1], 3.0) * 6.0, seed + 17))) * (
        1.0 - 0.15 * band_z)                                                                           # glints
    speck = wp.max(speck, run_v)
    # the cells the gold net rings: their chromatophores denser, darker toward the middle (body 08's dark cells
    # ringed in gold; the photos' darks), not in the band's dense net (its darks are dots); the gold between drawn-back
    # dots a little sparser (0.12 -> 0.15: the old paint had more flecks per mm2 than any photo)
    dk = M.mix3(wp.vec3(1.0, 1.0, 1.0), CELL_DK, proc.smoothstep(0.20, 0.48, runs(q, seed)) * (1.0 - band_z))
    col = M.mix3(wp.cw_mul(M.srgb(wp.vec3(0.56, 0.27, 0.09)), dk), gold,
                 wp.max(proc.smoothstep(0.15, 0.43, gnear), speck))
    cov = cov * (1.0 - speck)
    # the chromatophores' mix drifts slowly (redder and browner patches about 1 mm across)
    patch = 0.5 + 0.5 * proc.fbm3(wp.vec3(q[0], q[1], 5.0) * 0.9, 2, 2.0, 0.5, seed + 13)
    dcol = wp.cw_mul(wp.cw_mul(dcol, M.mix3(wp.vec3(1.10, 0.94, 0.92), wp.vec3(0.84, 0.92, 0.98), patch)), dk)
    col = M.mix3(col, dcol, 0.96 * cov)
    # the periphery runs on under the lids, a little shaded; the whole iris IRIS_GAIN (the fewer, stronger flecks)
    col = col * (1.0 - 0.22 * proc.smoothstep(0.86, 1.0, r)) * IRIS_GAIN
    col = M.mix3(col, wp.vec3(0.0035, 0.0040, 0.0055), pupil)
    alb[tid] = col
    # the iridophore band: under the pupil, seen through the gaps between the chromatophores (so it is granular)
    sd = pupil_sd(x, y)
    band = proc.smoothstep(-0.02, -0.10, y) * proc.smoothstep(-0.005, 0.02, sd) * (
        1.0 - proc.smoothstep(0.07, 0.22, sd)) * (1.0 - proc.smoothstep(PUP_A * 0.75, PUP_A * 1.15, wp.abs(x)))
    band = band * (0.25 + 0.75 * (1.0 - cov)) * (1.0 - pupil)
    out = 1.0 - pupil
    # the flecks (lone specks and runs) reflect too: their G (FLECK_G, the band's where it is more), their roughness
    # the engine's floor
    fl = speck * out
    msk[tid] = wp.vec4(cov * out, wp.max(band, FLECK_G * fl), pupil, wp.max(cov_e - cov, 0.0) * out)
    rough[tid] = ROUGH + (ROUGH_FL - ROUGH) * fl


def paint_iris(size=1024, seed=5, masks=False, Re=None):
    """the iris maps in image order (top row = the eye's up): albedo (sRGB uint8), height (zeros: the outer surface is
    smooth), roughness (uint8) and, with masks=True, the masks (RGBA uint8, linear: R chromatophore cover, G iridophore
    reflectors (the band, the gold flecks), B pupil, A the dark display's added cover). Re: the eyeball radius in
    metres, the painting's physical scale (default: the species' eye)"""
    if Re is None:
        Re = eye_geom(SPEC, 1)[3]
    n = size * size
    alb = wp.zeros(n, dtype=wp.vec3)
    msk = wp.zeros(n, dtype=wp.vec4)
    rgh = wp.zeros(n, dtype=wp.float32)
    wp.launch(k_iris, dim=n, inputs=[size, seed, float(Re) * 1000.0, alb, msk, rgh])
    A = alb.numpy().reshape(size, size, 3)[::-1]
    Mk = msk.numpy().reshape(size, size, 4)[::-1]
    Rg = rgh.numpy().reshape(size, size)[::-1]
    out = ((M.srgb_oetf(A) * 255 + 0.5).astype(np.uint8), np.zeros((size, size), np.float32),
           (np.clip(Rg, 0, 1) * 255 + 0.5).astype(np.uint8))
    if masks:
        out = out + ((np.clip(Mk, 0, 1) * 255 + 0.5).astype(np.uint8),)
    return out


def height_to_normal(H, metres_per_px):
    """a tangent-space normal map (GL, +Y up in the image) from a height map in metres"""
    gy, gx = np.gradient(H, metres_per_px)
    # image rows run down: +v (image up) is -row
    n = np.dstack([-gx, gy, np.ones_like(H)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return np.clip((n * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)
