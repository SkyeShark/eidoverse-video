"""THE CUTICLE PASS: the arthropod family's material (work/bestiary/research/BEETLE_PLAN.md §5, the cuticle stack), first
used on the stag beetle's leg shells grafted onto the octopus (CROSSBREED M2), written for the beetle's own shells too.
Per texel of a bake (forge/bake_mesh.py's drivers, or bake.py's): the zone's measured chitin, its relief, its packs.

  ZONES     (M2b) the beetle's own rows, one source (species/stag_beetle_skin.ZONE: tibia, tarsus, claw, membrane)
  ALBEDO    the zone's linear albedo (§5.2: the legs black-brown; the claws a reddish black at their tips), lnL += a_ao
            AO_local + a_cf conv_fine + a_cm conv_mid (§5.3's chitin row: 0.53-1.76 / 0.07-0.26 / 0.22-0.48: the
            middles), cavities toward red-purple and convex edges toward amber (§5.3), a slow 3D mottle (+-6 % L); the
            membranes (sleeves) pale to amber (§5.4)
  NORMAL    the bake's tangent normal; the shells' fine PUNCTATION (the tibiae and tarsi: sparse shallow pits, a hash
            of 3D cells on the bake's position driver) and their MICROSCULPTURE (shallow grooves on a 3D cell net), the
            slopes taken within each island only, so no island edge prints [E: §4.8's T tier; Skye's look]; the coat's
            satin-to-gloss patches and the soil settled in the crevices (the B8 round's dirt term) in the ORM and albedo
  ORM       R the bake's AO; G the BASE roughness (the pigmented exo- / endocuticle under the coat), crevices rougher by
            0.20 AO_local (REF R5), bump tops glossier; B the COAT roughness (the epicuticle, the one strong specular
            interface: polished on the high points, duller in the crevices and the punctation; the shiniest the claws):
            the B8 round's layer model (forge/species/stag_beetle_skin.py: three's clear coat over a base at
            specularIntensity 0.2; the runtime's skinMaterial reads it on chitin texels; metalness stays 0, §5.1)
  MASKS     (§5.5) R soft and thin: the membranes, and the thin rims of teeth, spurs and claws (thickness under 2.5 mm
            at the part's scale: the faint warm rim, shell transmission 0.06-0.12); G 0 (M2c's real-scale path: the
            setae's SHEEN amount, the runtime's chitin sheen); B ACCENT (teeth, spurs, claws,
            keels and margins: the glow mask, from convexity); A the pattern zone 0 (M2c's real-scale path: the COAT
            LOST under the setae, the runtime's clear coat x (1 - A) on chitin: SETAE_COAT_LOSS)
  DISPLAY   (§5.5) R the per-part id; G the IRIDOPHORE mask (the jewel-beetle remix: the runtime's thin film, strength 0
            on the realistic base, §5.5 "no iridescence on B1"); B wax bloom 0; A a per-cell random
Encoding: the forge's albedo encoder (material.srgb_oetf once INFRA-1 lands, else the frozen base's x^(1/2.2): a part
matches the base it ships with), data maps linear.

(M2c, the lead's call 4: the chitin read as grey hammered metal: M2b's microsculpture cells raised to 2.0 mm and pits
of 0.9 mm radius to span texels at 3,492 px/m, under a coat that mirrored the sky.) With run(..., author_scale=a) the
relief is the DONOR'S OWN AT ITS REAL SCALE: the beetle's micro relief function itself (species/stag_beetle_sculpt.relief:
its RECIPE rows for the tibia, the tarsus and the claw, one source) at its ABSOLUTE size (REAL['scale'] 'life': the point
in millimetres, never divided by the author scale: a cuticle's microsculpture is the print of its epidermal cells, ~0.1 mm
on a beetle of any size, and a lobster's shell is smooth at arm's length; read at the author scale, as the first M2c pass
did, the tibia's 0.12 mm cells became 3 mm hammer marks again), SUPERSAMPLED per texel over the texel's own footprint on
the surface (REAL['subsamples']^2 sub-cells from the position driver's derivatives: 5 um at 3,604 px/m, the punctures'
12-15 um radius over two to three of them): the sub-samples' mean normal goes into the normal map (what a texel
resolves: at this size nothing), their spread into BOTH roughness channels as the von Mises-Fisher variance of the
mean's length (Toksvig at mip 0: alpha^2 + 2 (1 - r^2) / (3 r - r^3); the beetle's own nlen rule,
stag_beetle_skin.k_skin): the relief, finer than a texel, becomes a satin, never raised into visible cells. The masks are
the beetle's own rules (stag_beetle_sculpt.micro_masks: the tibia's punctures at 0.7, the tarsi's at 0.5, the cells at
1), read in the donor's frame (the placement's inverse rotation). The SETAE the beetle's own too: the tibia's fringe on
its inner (medial-ventral) edge, the tarsi's golden brushes on their ventral faces, their coverage from a second pass of
the same relief with the hairs alone; as on the beetle (B5: hairs too fine to draw read as matte cork when their relief
roughens the coat) they never join the slope variance: SETAE_ALB of their gold goes into the albedo, the base under them
rougher, and their forward-scattered gold is the runtime's sheen, its amount (coverage x the zone's SHEEN_W) in the
masks' G. The coat, the base and the dust are the beetle's k_skin terms (polished on the high points, duller in the
pits and where dust lies; no satin patches); the runtime adds each mip's own spread (Toksvig) and the pixel's (specular
AA), as the beetle's own runtime does (patches/crossbreed_m2_bestiary.md, the chitin's coat)
"""
import numpy as np

# per zone: the LINEAR albedo, the coat's and the base's roughness, the ior and the iridophore weight: ONE SOURCE, the
# beetle's own material (forge/species/stag_beetle_skin.ZONE: its tibia, tarsus, claw and membrane rows, read at import;
# CROSSBREED M2b, the lead's call: M2 carried a copy of the B8 round's rows of 10-28, which the beetle's B5-B7 rounds have
# since moved: the legs redder and darker, glossier coats, the membranes M3v's dark red-brown). `pits` is this family's
# own relief flag (the beetle's micro relief is its bake's, not a row). L50: the zone albedo's own luminance, the median
# the relief keeps (the v1 rows, sRGB guesses with one lobe at roughness 0.24-0.34, rendered as grey plastic)
from ..species import stag_beetle_skin as _SBS  # noqa: E402


def _row(zone, pits, membrane=False):
    r = _SBS.ZONE[zone]
    d = dict(albedo=tuple(float(c) for c in r['albedo']), coat=float(r['coat_r']), rough=float(r['base_r']),
             ior=float(r['ior']), irid=float(r['irid']), pits=pits, source=f'stag_beetle_skin.ZONE[{zone!r}]')
    if membrane:
        d['membrane'] = True
    return d


ZONES = dict(tibia=_row('tibia', True), tarsus=_row('tarsus', True), claw=_row('claw', False),
             sleeve=_row('membrane', False, membrane=True))
for _z in ZONES.values():
    _z['L50'] = 0.2126 * _z['albedo'][0] + 0.7152 * _z['albedo'][1] + 0.0722 * _z['albedo'][2]
# the iridescent option's remix families: the beetle's own table (one source: b10 writes the same rows into the beetle's
# glb; ASSEMBLE writes them into a graft's part material, which the runtime's chitin reads by name)
IRID_FAMILIES = _SBS.IRID_FAMILIES
RELIEF = dict(a_ao=1.10, a_cf=0.15, a_cm=0.35)
PITS = dict(cell=0.0036, radius=0.0009, depth=0.00016, density=0.55, rough=0.12)     # metres at the part's scale
# the chitin's MICROSCULPTURE (reticulation: shallow grooves on a cell net, the beetle's ~0.05 mm life cells at the part's
# scale) and its COAT PATCHES (satin to gloss, value noise on 12 mm cells): at an author scale of ~25 the life surface's
# texture is millimetres across, and without it the coat reflected the sky over the whole shell as a smooth pipe does
# (the M2 stills, 10-28) [E: look]
MICRO = dict(cell=0.0020, edge=0.35, depth=0.00005)     # (the groove band ~0.7 mm: over two texels at 3,492 px/m)
COAT_PATCH = dict(cell=0.012, amp=0.18)
# the soft DIRT term (the B8 round's: dry soil dust settling in the crevices, dulling the coat there), linear
DIRT = dict(albedo=(0.090, 0.075, 0.058), gain=3.0, max=0.55)
# (M2c) the REAL-SCALE relief (run's author_scale path): the beetle's own relief per zone (stag_beetle_sculpt.RECIPE's
# rows, by name) at its absolute size (scale 'life': the point in mm; 'author': the first M2c pass's point / the author
# scale), its masks (pit density, setae, groove, cells: stag_beetle_sculpt.micro_masks's leg rules, the claws smooth; the
# setae in their own pass), the sub-cells per texel side for the slopes and for the setae's coverage (the relief read at
# their (n + 1)^2 corners), the texels per launch, the setae's colour weight (SETAE_W), sheen weight (SHEEN_W) and colour
# per zone (the beetle's own rows: stag_beetle_skin), and the beetle's k_skin coat / base / dust terms
REAL = dict(recipe=dict(tibia='tibia', tarsus='tarsus', claw='claw'), scale='life',
            masks=dict(tibia=(0.7, 0.0, 0.0, 1.0), tarsus=(0.5, 0.0, 0.0, 1.0), claw=(0.0, 0.0, 0.0, 0.0)),
            setae=dict(tibia=0.55, tarsus=1.0, claw=0.0), subsamples=56, setae_subsamples=8, chunk=16384, seed=5,
            setae_w=dict(tibia=_SBS.SETAE_W.get('tibia', 1.0), tarsus=_SBS.SETAE_W.get('tarsus', 1.0), claw=0.0),
            sheen_w=dict(tibia=_SBS.SHEEN_W.get('tibia', 0.5), tarsus=_SBS.SHEEN_W.get('tarsus', 0.5), claw=0.0),
            setae_col=dict(tibia=_SBS.SETAE['default'], tarsus=_SBS.SETAE['tarsus'], claw=_SBS.SETAE['default']),
            setae_alb=0.40, setae_base_r=0.62,
            coat_polish=0.30, coat_pit=0.10, coat_dirt=0.15, coat_ao=0.05, base_pit=0.10, base_dirt=0.10,
            dirt=dict(cavity=(0.35, 0.85), w_cavity=0.25, w_pit=0.08, max=0.4), cavity_w=0.35)
SUBSAMPLES = REAL['subsamples']
# (M2c, the third builder; the lead's call 4: "dark glossy chitin under the beach sky, not pewter") the leg chitin's
# PIGMENT hue on the real-scale path: the M3v tibia's own (beetle/out_b58/photo/crop_M3v_tibia_hind.png, its chitin
# pixels, linear: the darkest quartile 1 : 0.30 : 0.27, the darker half 1 : 0.37 : 0.31; their median WITH the coat's grey
# highlights 1 : 0.57 : 0.38, where the beetle's leg rows sit, tibia 1 : 0.57 : 0.44). The beetle's own rule for its
# elytra (stag_beetle_skin's ZONE notes: "the photo's mean carries the coat's grey highlights, the pigment is redder than
# the mean"), applied to the legs at each zone's own luminance (L50 kept: the level stays the beetle's row, one source;
# the hue is the photo's, for the beetle's owner to adopt in the rows). Under the octopus's full beach sky the coat's
# grey reflection outweighs a dark diffuse on every sky-facing face (measured: 18 % of the sky's radiance at a 70 deg
# view, against the sun's diffuse ~1/4 of it), and the rows' brown, a third grey already, summed with it to the grey
# satin the look found (the engine A/B, m2c_look_*: the tarsus close-ups)
PIGMENT = dict(hue=(1.0, 0.33, 0.29), zones=('tibia', 'tarsus', 'claw'))
# (M2c, the third builder) the COAT a quarter LOST under full setae coverage: the beetle's own rule (stag_beetle_skin's
# SETAE notes, B5: "the coat stays (a quarter lost under full coverage)"), which the part's coat lacked: its hairs kept the
# whole coat and mirrored the sky over the tarsal brushes. The loss per texel in the masks' A
SETAE_COAT_LOSS = 0.25
# (M2d, the lead's call 3) the tarsal brushes are drawn as HAIRS now (graft_socket.tarsal_setae, rooted where this pass
# paints the brush): the painted gold under them HALVED, so between the hairs the cuticle reads dark, as c07's and M3v's
# tarsi show golden setae over black-brown chitin (M2c's full weight read as flat khaki paint at macro range). Their
# coverage still drives the sheen, the coat loss and the base's roughness here (the hairs too fine to draw at distance),
# and the hairs' own density (the chain's setae stage reads the sheen it writes)
REAL['setae_w']['tarsus'] = 0.5 * REAL['setae_w']['tarsus']
# (M2d, the lead's call 5: from creature distance the leg read as a thin dark limb, a smooth pipe; measured beside the
# photos, m2d/tools/leg_measure.py: the dorsal views' highlight share 0.001-0.012 and p99 / p50 2.6-3.0, where c03's legs
# carry 0.20 and 6-9 and c07's 0.13 and 4.7: the photos' chitin draws its form in crisp highlights along its keels, teeth
# and beads, the part's coat spread one soft band over the round tibia) the coat POLISHED HARDER on the high points (k_skin's
# own rule: polished where convex, duller in the pits and crevices): 0.30 -> 0.55 of the coat's roughness taken off at full
# convexity, so the keels, the teeth's edges, the beads and the claws' backs catch the sun as lines while the faces between
# keep the beetle's satin
REAL['coat_polish'] = 0.55


def _micro_kernel():
    """the real-scale relief, supersampled per texel (a Warp kernel over the beetle's own relief_grad; built on first use)"""
    import warp as wp
    from ..species import stag_beetle_sculpt as SC
    if getattr(_micro_kernel, 'k', None) is not None:
        return _micro_kernel.k

    @wp.kernel
    def k_micro(P: wp.array(dtype=wp.vec3), Tx: wp.array(dtype=wp.vec3), Tv: wp.array(dtype=wp.vec3),
                zone: wp.array(dtype=wp.int32), par: wp.array(dtype=wp.float32), mz: wp.array(dtype=wp.vec4),
                npar: int, inv_s: float, nsub: int, hgrid: wp.array(dtype=wp.float32),
                o_n: wp.array(dtype=wp.vec3), o_h: wp.array(dtype=wp.vec3)):
        # the relief at the (nsub + 1)^2 CORNERS of nsub^2 sub-cells over the texel's footprint (ONE call of the beetle's
        # relief per corner: its gradient function inlines it five times, which the CUDA compiler could not hold), each
        # sub-cell's slope from its four corners (the bilinear patch's mean gradient), its normal; the mean over the
        # sub-cells and the relief / pit / seta means. (M2c restart) the masks per TEXEL (mz[i]: the beetle's leg rules
        # are directional, the setae on the inner edge and the ventral face); i indexes the launch's chunk
        i = wp.tid()
        z = zone[i]
        if z < 0:
            return
        tx = Tx[i]
        tv = Tv[i]
        n = wp.normalize(wp.cross(tx, tv))
        ux = wp.normalize(tx)
        sx = wp.length(tx) * inv_s / float(nsub)                  # a sub-cell's side along u and v (life mm)
        sv = wp.length(tv) * inv_s / float(nsub)
        m = mz[i]
        g1 = nsub + 1
        base = i * g1 * g1
        hs = float(0.0)
        ps = float(0.0)
        ss = float(0.0)
        for a in range(g1):
            for b in range(g1):
                fa = float(a) / float(nsub) - 0.5
                fb = float(b) / float(nsub) - 0.5
                q = (P[i] + tx * fa + tv * fb) * inv_s
                r0 = SC.relief(q, n, m, ux, par, z * npar)
                hgrid[base + a * g1 + b] = r0[0]
                hs = hs + r0[0]
                ps = ps + r0[1]
                ss = ss + r0[2]
        acc = wp.vec3(0.0, 0.0, 0.0)
        for a in range(nsub):
            for b in range(nsub):
                h00 = hgrid[base + a * g1 + b]
                h10 = hgrid[base + (a + 1) * g1 + b]
                h01 = hgrid[base + a * g1 + b + 1]
                h11 = hgrid[base + (a + 1) * g1 + b + 1]
                gu = 0.5 * ((h10 - h00) + (h11 - h01)) / sx
                gv = 0.5 * ((h01 - h00) + (h11 - h10)) / sv
                acc = acc + wp.normalize(wp.vec3(-gu, -gv, 1.0))
        k = float(nsub * nsub)
        o_n[i] = acc / k
        kk = float(g1 * g1)
        o_h[i] = wp.vec3(hs / kk, ps / kk, ss / kk)
    _micro_kernel.k = k_micro
    return k_micro


def texel_frames(P, cov, region):
    """per texel the surface's footprint vectors (metres per texel step): Tx along +u (the image's columns), Tv along +v
    (up the image), by central differences of the position driver within the same region and coverage (one-sided at an
    island's edge); texels with no neighbour on an axis take the other axis' perpendicular in the plane of the other's
    neighbours, else 0 (left out)"""
    out = []
    for axis, sign in ((1, 1.0), (0, -1.0)):
        Pp, Pm = np.roll(P, -1, axis), np.roll(P, 1, axis)
        okp = np.roll(cov, -1, axis) & (np.roll(region, -1, axis) == region) & cov
        okm = np.roll(cov, 1, axis) & (np.roll(region, 1, axis) == region) & cov
        T = np.zeros_like(P)
        both = okp & okm
        T[both] = 0.5 * (Pp - Pm)[both]
        T[okp & ~okm] = (Pp - P)[okp & ~okm]
        T[okm & ~okp] = (P - Pm)[okm & ~okp]
        out.append(sign * T)
    return out[0], out[1]


def _encode_albedo(lin):
    from .. import material as M
    f = getattr(M, 'srgb_oetf', None)
    if f is not None:
        return np.asarray(f(np.clip(lin, 0, 1)))
    return np.clip(lin, 0, 1) ** (1 / 2.2)


def _decode_srgb8(c):
    from .. import material as M
    f = getattr(M, 'srgb_eotf', None)
    c = np.asarray(c, np.float64) / 255.0
    if f is not None:
        return np.asarray(f(c))
    return c ** 2.2


def _hash3(i, j, k, s):
    h = (i * 73856093) ^ (j * 19349663) ^ (k * 83492791) ^ (s * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def pits_height(P, cell, radius, depth, density, seed=5):
    """sparse shallow pits on 3D points P (n, 3): a jittered point per cell (kept with probability density), each a
    smooth bowl of the radius and depth; returns the height (n,) (negative in a pit) and the pit mask (n,)"""
    g = np.floor(P / cell).astype(np.int64)
    h = np.zeros(len(P))
    best = np.full(len(P), np.inf)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for dk in (-1, 0, 1):
                c = g + np.array([di, dj, dk])
                i, j, k = c[:, 0], c[:, 1], c[:, 2]
                keep = _hash3(i, j, k, seed) < density
                jit = np.column_stack([_hash3(i, j, k, seed + 1), _hash3(i, j, k, seed + 2), _hash3(i, j, k, seed + 3)])
                q = (c + 0.2 + 0.6 * jit) * cell
                d = np.linalg.norm(P - q, axis=1)
                d = np.where(keep, d, np.inf)
                best = np.minimum(best, d)
    t = np.clip(1.0 - (best / radius) ** 2, 0.0, 1.0)
    h = -depth * t * t
    return h, t > 0


def reticulation(P, cell, seed=31):
    """a 3D cell net on points P (n, 3): the Voronoi edge measure (F2 - F1) / cell of jittered points one per cell (0 on
    a cell border); returns (n,)"""
    g = np.floor(P / cell).astype(np.int64)
    d1 = np.full(len(P), np.inf)
    d2 = np.full(len(P), np.inf)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for dk in (-1, 0, 1):
                c = g + np.array([di, dj, dk])
                i, j, k = c[:, 0], c[:, 1], c[:, 2]
                jit = np.column_stack([_hash3(i, j, k, seed), _hash3(i, j, k, seed + 1), _hash3(i, j, k, seed + 2)])
                d = np.linalg.norm(P - (c + 0.15 + 0.7 * jit) * cell, axis=1)
                d2 = np.where(d < d1, d1, np.minimum(d2, d))
                d1 = np.minimum(d1, d)
    return (d2 - d1) / cell


def value_noise(P, cell, seed):
    """trilinear value noise in [0, 1] on 3D points P (n, 3), cells of the given size"""
    g = np.floor(P / cell).astype(np.int64)
    fr = P / cell - g
    s3 = fr * fr * (3 - 2 * fr)
    out = np.zeros(len(P))
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                w = (s3[:, 0] if di else 1 - s3[:, 0]) * (s3[:, 1] if dj else 1 - s3[:, 1]) * (s3[:, 2] if dk else 1 - s3[:, 2])
                out += w * _hash3(g[:, 0] + di, g[:, 1] + dj, g[:, 2] + dk, seed)
    return out


def island_slopes(h, region, cov, texel_m):
    """dh/dx, dh/dy (per metre; x along +u = the image's columns, y along +v = up the image) by central differences
    within the same region and coverage only (one-sided at an island's edge, 0 where alone)"""
    gx = np.zeros_like(h)
    gy = np.zeros_like(h)
    ok = cov
    for axis, out, sign in ((1, gx, 1.0), (0, gy, -1.0)):
        hp = np.roll(h, -1, axis)
        hm = np.roll(h, 1, axis)
        okp = np.roll(ok, -1, axis) & (np.roll(region, -1, axis) == region)
        okm = np.roll(ok, 1, axis) & (np.roll(region, 1, axis) == region)
        both = okp & okm & ok
        onlyp = okp & ~okm & ok
        onlym = okm & ~okp & ok
        out[both] = (hp - hm)[both] / (2 * texel_m)
        out[onlyp] = (hp - h)[onlyp] / texel_m
        out[onlym] = (h - hm)[onlym] / texel_m
        out *= sign                 # (image rows run down, v runs up)
    return gx, gy


def _sm(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def outward_normals(P, Tx, Tv, reg, sel):
    """(M2c restart) per texel the surface's unit normal from its footprint (Tx x Tv), turned OUTWARD per region (each
    region one shell: away from its texels' principal axis; an island's UVs may be mirrored, so the cross product's sign
    is not the surface's)"""
    n = np.cross(Tx, Tv)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-30)
    for rid in np.unique(reg[sel]):
        m = sel & (reg == rid)
        Pm = P[m]
        c = Pm.mean(0)
        w, U = np.linalg.eigh(np.cov((Pm - c).T))
        a = U[:, 2]
        rad = (Pm - c) - ((Pm - c) @ a)[:, None] * a[None]
        flip = np.einsum('ij,ij->i', n[m], rad) < 0.0
        nm_ = n[m]
        nm_[flip] *= -1.0
        n[m] = nm_
    return n


def real_relief(P, cov, reg, zone_of_region, author_scale, frame=None, log=print):
    """(M2c) the donor's own relief at its real scale, supersampled per texel (module docstring): returns per texel the
    sub-samples' mean normal in the texel's tangent frame (x +u, y +v, z out; zeros off the zones), the mean relief height
    and pit weight (life mm, 0..1), the vMF variance of the mean's length, the zone ids and the setae's coverage (0..1).
    frame: the donor's placement (graft_socket.placement: R, P_lip), for the beetle's directional masks read in the
    beetle's own frame (None: no setae). REAL['scale'] 'life': the relief at its absolute size (the point in mm)"""
    import warp as wp
    from ..species import stag_beetle_sculpt as SC
    Tx, Tv = texel_frames(P, cov, reg)
    zones = [z for z in REAL['recipe']]
    zid = -np.ones(reg.shape, np.int32)
    for rid, zn in zone_of_region.items():
        if zn in REAL['recipe']:
            zid[cov & (reg == rid)] = zones.index(zn)
    ok = (zid >= 0) & (np.linalg.norm(Tx, axis=-1) > 0) & (np.linalg.norm(Tv, axis=-1) > 0)
    zid[~ok] = -1
    par = np.concatenate([SC.params(REAL['recipe'][z], REAL['seed']) for z in zones]).astype(np.float32)
    ys, xs = np.nonzero(zid >= 0)
    zz = zid[ys, xs]
    inv_s = 1000.0 if REAL.get('scale', 'life') == 'life' else 1.0 / (author_scale * 1e-3)
    # the masks per texel: the slopes' pass the punctures and the cells (the beetle's leg rules), the setae's pass the
    # hairs alone, directional in the beetle's frame (stag_beetle_sculpt.micro_masks: the tibia's fringe on its inner
    # edge, medial and ventral; the tarsi's brushes on their ventral faces)
    mz = np.array([REAL['masks'][z] for z in zones], np.float32)[zz]
    ms_ = np.zeros((len(ys), 4), np.float32)
    if frame is not None:
        nw = outward_normals(P, Tx, Tv, reg, zid >= 0)[ys, xs]
        R = np.asarray(frame['R'], np.float64)
        nbf = nw @ R                                         # the donor's (beetle's) frame: d_b = d_oct R
        medx = -np.sign(float(np.asarray(frame['P_lip'])[0])) or 1.0     # the medial side: toward the midline
        med = nbf @ np.array([0.7 * medx, -0.7, 0.0])
        down = -nbf[:, 1]
        amt = np.array([REAL['setae'][z] for z in zones])[zz]
        rule = np.where(np.array(zones)[zz] == 'tibia', _sm(0.45, 0.9, med),
                        np.where(np.array(zones)[zz] == 'tarsus', _sm(-0.1, 0.5, down), 0.0))
        ms_[:, 1] = amt * rule
    k = _micro_kernel()
    P32, Tx32, Tv32 = (np.ascontiguousarray(a[ys, xs], np.float32) for a in (P, Tx, Tv))
    parw = wp.array(par, dtype=wp.float32)

    def launch(masks, ns):
        on = np.zeros((len(ys), 3), np.float32)
        oh = np.zeros((len(ys), 3), np.float32)
        ch = int(REAL['chunk'])
        hgrid = wp.zeros(min(ch, len(ys)) * (ns + 1) ** 2, dtype=wp.float32)
        for a in range(0, len(ys), ch):
            b = min(a + ch, len(ys))
            o_n = wp.zeros(b - a, dtype=wp.vec3)
            o_h = wp.zeros(b - a, dtype=wp.vec3)
            wp.launch(k, dim=b - a, inputs=[wp.array(P32[a:b], dtype=wp.vec3), wp.array(Tx32[a:b], dtype=wp.vec3),
                                            wp.array(Tv32[a:b], dtype=wp.vec3), wp.array(zz[a:b], dtype=wp.int32),
                                            parw, wp.array(masks[a:b], dtype=wp.vec4), int(SC.NPAR), float(inv_s),
                                            int(ns), hgrid, o_n, o_h])
            on[a:b], oh[a:b] = o_n.numpy(), o_h.numpy()
        return on, oh
    on, oh = launch(mz, int(REAL['subsamples']))
    seta = np.zeros(reg.shape)
    if ms_[:, 1].any():
        _, oh_s = launch(ms_, int(REAL['setae_subsamples']))
        seta[ys, xs] = np.clip(oh_s[:, 2], 0.0, 1.0)
    nb = np.zeros(P.shape)
    hh = np.zeros(reg.shape)
    pit = np.zeros(reg.shape)
    nb[ys, xs] = on
    hh[ys, xs], pit[ys, xs] = oh[:, 0], oh[:, 1]
    r = np.clip(np.linalg.norm(nb, axis=-1), 0.0, 1.0)
    v0 = np.where(zid >= 0, np.clip(2.0 * (1.0 - r * r) / np.maximum(3.0 * r - r ** 3, 1e-4), 0.0, 0.5), 0.0)
    sel = zid >= 0
    per = ', '.join(f'{z} v0 p50 {np.median(v0[zid == k_]):.2e} p95 {np.percentile(v0[zid == k_], 95):.2e} setae p50 '
                    f'{np.median(seta[zid == k_]):.3f} p95 {np.percentile(seta[zid == k_], 95):.3f}'
                    for k_, z in enumerate(zones) if (zid == k_).any())
    log(f'[cuticle] the donor\'s relief at its real scale ({REAL.get("scale", "life")}: the point x {inv_s:.2f} in the '
        f'beetle\'s RECIPE rows {[REAL["recipe"][z] for z in zones]}), {REAL["subsamples"]}^2 sub-cells on {len(ys):,} '
        f'texels: the mean normal\'s length p50 {np.median(r[sel]):.5f} p1 {np.percentile(r[sel], 1):.5f}; its variance '
        f'into the roughness p50 {np.median(v0[sel]):.2e} p99 {np.percentile(v0[sel], 99):.2e}; per zone {per}')
    return nb, hh, pit, v0, zid, seta


def run(drivers, zone_of_region, px_per_m, part_id=None, log=print, author_scale=None, frame=None):
    """drivers: a bake's arrays (image order, size x size): normal (tangent rgb, coverage a), ao, curvature,
    thickness, position (xyz, w), region (an id per texel); zone_of_region {region id: zone name in ZONES}; part_id
    {region id: 0..1 for the display's R}; author_scale (M2c): the part's life-mm -> metres scale x 1e3: the relief at
    the donor's real scale with the beetle's own coat (module docstring); None: the M2b relief (PITS, MICRO at the part's
    scale); frame (M2c restart): the donor's placement (R, P_lip) for the beetle's directional masks (the setae). Returns
    (maps {albedo, normal, orm, masks, display, growth} uint8 image-order, cov, the per-zone report)"""
    from .. import calib
    size = drivers['normal'].shape[0]
    reg = np.asarray(drivers['region'])
    nrm = np.asarray(drivers['normal'], np.float64)
    cov = (nrm[..., 3] > 0) & np.isin(reg, list(zone_of_region))
    D = dict(normal=np.where(cov[..., None], nrm, 0.0), ao=np.where(cov, np.asarray(drivers['ao'], np.float64), 0.0),
             curvature=np.where(cov, np.asarray(drivers['curvature'], np.float64), 0.0))
    rel = calib.relief_drivers(D, px_per_m)
    aol, conv, convm = (np.asarray(rel[k], np.float64) for k in ('ao_local', 'conv', 'conv_mid'))
    P = np.asarray(drivers['position'], np.float64)[..., :3]
    texel = 1.0 / px_per_m
    if author_scale is not None:
        return _run_real(drivers, zone_of_region, px_per_m, part_id, log, author_scale, size, reg, nrm, cov, aol, conv,
                         convm, P, frame)
    alb = np.zeros((size, size, 3))
    rough = np.full((size, size), 0.5)
    coat = np.full((size, size), 0.5)
    thin = np.zeros((size, size))
    accent = np.zeros((size, size))
    irid = np.zeros((size, size))
    pid = np.zeros((size, size))
    h = np.zeros((size, size))
    pit = np.zeros((size, size), bool)
    rep = {}
    # a slow 3D mottle (+-6 % in lnL): value noise on 9 mm cells
    ys, xs = np.nonzero(cov)
    Pc = P[ys, xs]
    g = np.floor(Pc / 0.009).astype(np.int64)
    fr = Pc / 0.009 - g
    s3 = fr * fr * (3 - 2 * fr)
    mot = np.zeros(len(Pc))
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                w = (s3[:, 0] if di else 1 - s3[:, 0]) * (s3[:, 1] if dj else 1 - s3[:, 1]) * (s3[:, 2] if dk else 1 - s3[:, 2])
                mot += w * (_hash3(g[:, 0] + di, g[:, 1] + dj, g[:, 2] + dk, 11) - 0.5)
    mottle = np.zeros((size, size))
    mottle[ys, xs] = mot * 0.12
    for rid, zn in zone_of_region.items():
        m = cov & (reg == rid)
        if not m.any():
            continue
        Z = ZONES[zn]
        base = np.asarray(Z['albedo'], np.float64)
        if Z.get('membrane'):
            lnL = 0.55 * aol[m] + 0.10 * conv[m]
            c = base[None] * np.exp(lnL)[:, None]
            alb[m] = c
            rough[m] = Z['rough'] - 0.05 * np.clip(conv[m], 0, 1)
            coat[m] = Z['coat']
            thin[m] = 0.85
        else:
            lnL = RELIEF['a_ao'] * aol[m] + RELIEF['a_cf'] * conv[m] + RELIEF['a_cm'] * convm[m] + mottle[m]
            c = base[None] * np.exp(lnL)[:, None]
            tc = np.clip(-aol[m] * 4.0, 0, 1)[:, None]
            te = np.clip(conv[m] * 0.5, 0, 1)[:, None]
            c = c * (1 + 0.35 * tc * np.array([0.10, -0.08, 0.06])) * (1 + 0.5 * te * np.array([0.25, 0.10, -0.15]))
            Lz = 0.2126 * c[:, 0] + 0.7152 * c[:, 1] + 0.0722 * c[:, 2]
            c = c * (Z['L50'] / max(float(np.median(Lz)), 1e-6))
            alb[m] = c
            rough[m] = Z['rough'] + 0.20 * np.clip(-aol[m], 0, 1) - 0.05 * np.clip(conv[m], 0, 1)
            # the coat: polished on the high points, duller in the crevices (the pits add theirs below)
            coat[m] = Z['coat'] + 0.25 * np.clip(-aol[m], 0, 1) - 0.04 * np.clip(conv[m], 0, 1)
            thk = np.asarray(drivers['thickness'], np.float64)[m]
            thin[m] = 0.6 * np.clip(1.0 - thk / 0.0025, 0, 1) ** 2
            accent[m] = np.clip(conv[m] * 0.6, 0, 1) if zn != 'claw' else np.clip(0.5 + conv[m] * 0.4, 0, 1)
            irid[m] = Z.get('irid', 1.0)                 # (the beetle's own iridophore weight per zone, M2b)
            if Z.get('pits'):
                hh, pp = pits_height(P[m], PITS['cell'], PITS['radius'], PITS['depth'], PITS['density'])
                h[m] = hh
                pit[m] = pp
            # the microsculpture's grooves (normals only), the coat's satin-to-gloss patches, the soil in the crevices
            e = reticulation(P[m], MICRO['cell'])
            h[m] += -MICRO['depth'] * (1.0 - np.clip(e / MICRO['edge'], 0.0, 1.0) ** 2)
            coat[m] += COAT_PATCH['amp'] * value_noise(P[m], COAT_PATCH['cell'], 41)
            wd = np.clip(-aol[m] * DIRT['gain'], 0.0, 1.0) * DIRT['max']
            alb[m] = alb[m] * (1.0 - wd[:, None]) + np.asarray(DIRT['albedo'])[None] * wd[:, None]
            coat[m] += 0.25 * wd
            rough[m] += 0.15 * wd
        pid[m] = (part_id or {}).get(rid, 0.0)
        L = 0.2126 * alb[m][:, 0] + 0.7152 * alb[m][:, 1] + 0.0722 * alb[m][:, 2]
        rep[zn] = dict(texels=int(m.sum()), L_p50=float(np.median(L)), L_p5=float(np.percentile(L, 5)),
                       L_p95=float(np.percentile(L, 95)), rough_p50=float(np.median(rough[m])),
                       coat_p50=float(np.median(coat[m])))
    # the pits' normals (within islands) and roughness
    gx, gy = island_slopes(h, reg, cov, texel)
    tn = nrm[..., :3].copy()
    tn[..., 0] -= gx
    tn[..., 1] -= gy
    tn /= np.maximum(np.linalg.norm(tn, axis=-1, keepdims=True), 1e-12)
    rough = np.where(pit, rough + PITS['rough'] * np.clip(-h / PITS['depth'], 0, 1), rough)
    coat = np.where(pit, coat + PITS['rough'] * np.clip(-h / PITS['depth'], 0, 1), coat)
    alb = np.where(pit[..., None], alb * (1 - 0.25 * np.clip(-h / PITS['depth'], 0, 1))[..., None], alb)
    alb = np.clip(alb, 0.010, 0.65)                      # the albedo envelope (remix/elements.py:48, REF R2)
    rough = np.clip(rough, 0.05, 1.0)
    coat = np.clip(coat, 0.03, 1.0)
    cell = np.zeros((size, size))
    cell[ys, xs] = _hash3(g[:, 0], g[:, 1], g[:, 2], 23)
    a8 = lambda x: np.clip(np.asarray(x) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    maps = dict(albedo=a8(np.where(cov[..., None], _encode_albedo(alb), 0.5)),
                normal=a8(np.where(cov[..., None], tn * 0.5 + 0.5, [0.5, 0.5, 1.0])),
                orm=a8(np.where(cov[..., None], np.stack([np.asarray(drivers['ao'], np.float64), rough, coat], -1),
                                [1.0, 0.5, 0.5])),
                masks=a8(np.stack([thin, np.zeros_like(thin), accent, np.zeros_like(thin)], -1) * cov[..., None]),
                display=a8(np.stack([pid, irid, np.zeros_like(pid), cell], -1) * cov[..., None]),
                growth=np.zeros((size, size, 4), np.uint8))
    log(f'[cuticle] {size}^2: ' + ', '.join(f'{z} L p50 {r["L_p50"]:.4f} (p5 {r["L_p5"]:.4f}, p95 {r["L_p95"]:.4f}) '
                                            f'base rough {r["rough_p50"]:.2f}, coat {r["coat_p50"]:.2f} '
                                            f'({r["texels"]:,} texels)'
                                            for z, r in rep.items()) + f'; pits on {int(pit.sum()):,} texels')
    return maps, cov, rep


def _sstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _run_real(drivers, zone_of_region, px_per_m, part_id, log, author_scale, size, reg, nrm, cov, aol, conv, convm, P,
              frame=None):
    """(M2c) run()'s author_scale path: the donor's relief at its real scale (real_relief) and the beetle's own coat (its
    setae included: the colour, the base under them, the sheen's amount)"""
    nb, hh, pitw, v0, zid, seta = real_relief(P, cov, reg, zone_of_region, author_scale, frame=frame, log=log)
    R = REAL
    alb = np.zeros((size, size, 3))
    rough = np.full((size, size), 0.5)
    coat = np.full((size, size), 0.5)
    thin = np.zeros((size, size))
    accent = np.zeros((size, size))
    irid = np.zeros((size, size))
    pid = np.zeros((size, size))
    sheen = np.zeros((size, size))
    coat_loss = np.zeros((size, size))
    rep = {}
    ys, xs = np.nonzero(cov)
    Pc = P[ys, xs]
    g = np.floor(Pc / 0.009).astype(np.int64)
    fr = Pc / 0.009 - g
    s3 = fr * fr * (3 - 2 * fr)
    mot = np.zeros(len(Pc))
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                w = (s3[:, 0] if di else 1 - s3[:, 0]) * (s3[:, 1] if dj else 1 - s3[:, 1]) * (s3[:, 2] if dk else 1 - s3[:, 2])
                mot += w * (_hash3(g[:, 0] + di, g[:, 1] + dj, g[:, 2] + dk, 11) - 0.5)
    mottle = np.zeros((size, size))
    mottle[ys, xs] = mot * 0.12
    cav = np.asarray(drivers['cavity'], np.float64) if 'cavity' in drivers else np.ones((size, size))
    ao = np.asarray(drivers['ao'], np.float64)
    hc = np.clip(hh / 0.003, -1.0, 1.0)                    # (k_skin's micro cavity, the relief height normalised)
    for rid, zn in zone_of_region.items():
        m = cov & (reg == rid)
        if not m.any():
            continue
        Z = ZONES[zn]
        base = np.asarray(Z['albedo'], np.float64)
        if zn in PIGMENT['zones']:
            # (M2c) the pigment's hue at the row's own luminance
            hue = np.asarray(PIGMENT['hue'], np.float64)
            base = hue * (Z['L50'] / float(hue @ [0.2126, 0.7152, 0.0722]))
        if Z.get('membrane'):
            lnL = 0.55 * aol[m] + 0.10 * conv[m]
            alb[m] = base[None] * np.exp(lnL)[:, None]
            rough[m] = Z['rough'] - 0.05 * np.clip(conv[m], 0, 1)
            coat[m] = Z['coat']
            thin[m] = 0.85
        else:
            lnL = RELIEF['a_ao'] * aol[m] + RELIEF['a_cf'] * conv[m] + RELIEF['a_cm'] * convm[m] + mottle[m] \
                + R['cavity_w'] * hc[m]
            c = base[None] * np.exp(lnL)[:, None]
            tc = np.clip(-aol[m] * 4.0, 0, 1)[:, None]
            te = np.clip(conv[m] * 0.5, 0, 1)[:, None]
            c = c * (1 + 0.35 * tc * np.array([0.10, -0.08, 0.06])) * (1 + 0.5 * te * np.array([0.25, 0.10, -0.15]))
            Lz = 0.2126 * c[:, 0] + 0.7152 * c[:, 1] + 0.0722 * c[:, 2]
            c = c * (Z['L50'] / max(float(np.median(Lz)), 1e-6))
            # the beetle's soft dust (k_skin): only in real crevices (the cavity under its band) and the pits, half of it
            # into the albedo
            dr = R['dirt']
            dirt = np.clip(dr['w_cavity'] * _sstep(dr['cavity'][0], dr['cavity'][1], 1.0 - cav[m]) + dr['w_pit'] * pitw[m],
                           0.0, dr['max'])
            c = c * (1.0 - 0.5 * dirt[:, None]) + np.asarray(DIRT['albedo'])[None] * (0.5 * dirt[:, None])
            # (M2c restart) the SETAE (k_skin's rule): their coverage x 0.85, SETAE_ALB of the zone's golden weight in the
            # albedo; the rest of their gold is the runtime's sheen (the amount below, in the masks' G)
            sc = np.clip(seta[m] * 0.85, 0.0, 1.0)
            sw = float(R['setae_w'].get(zn, 0.0)) * float(R['setae_alb'])
            c = c * (1.0 - (sc * sw)[:, None]) + np.asarray(R['setae_col'][zn], np.float64)[None] * (sc * sw)[:, None]
            sheen[m] = np.clip(sc * float(R['sheen_w'].get(zn, 0.0)), 0.0, 1.0)
            coat_loss[m] = SETAE_COAT_LOSS * sc
            alb[m] = c
            # the coat (k_skin): polished on the high points, duller in the pits, the dust and the occluded crevices;
            # the base under it a little rougher in the pits and the dust, and toward the hairs' own under them
            hi = np.clip(convm[m], 0.0, 1.5) / 1.5
            coat[m] = Z['coat'] * (1.0 - R['coat_polish'] * hi) + R['coat_pit'] * pitw[m] + R['coat_dirt'] * dirt \
                + R['coat_ao'] * (1.0 - ao[m])
            rough[m] = (Z['rough'] + R['base_pit'] * pitw[m] + R['base_dirt'] * dirt) * (1.0 - sc) + R['setae_base_r'] * sc
            thk = np.asarray(drivers['thickness'], np.float64)[m]
            thin[m] = 0.6 * np.clip(1.0 - thk / 0.0025, 0, 1) ** 2
            accent[m] = np.clip(conv[m] * 0.6, 0, 1) if zn != 'claw' else np.clip(0.5 + conv[m] * 0.4, 0, 1)
            irid[m] = Z.get('irid', 1.0)
        pid[m] = (part_id or {}).get(rid, 0.0)
    # the sub-texel spread folded into both lobes (Toksvig / LEAN at mip 0: alpha^2 + v0, alpha = roughness^2)
    rough = np.where(zid >= 0, np.minimum((np.clip(rough, 0.0, 1.0) ** 4 + v0) ** 0.25, 1.0), rough)
    coat = np.where(zid >= 0, np.minimum((np.clip(coat, 0.0, 1.0) ** 4 + v0) ** 0.25, 0.9), coat)
    for rid, zn in zone_of_region.items():
        m = cov & (reg == rid)
        if not m.any():
            continue
        L = 0.2126 * alb[m][:, 0] + 0.7152 * alb[m][:, 1] + 0.0722 * alb[m][:, 2]
        rep[zn] = dict(texels=int(m.sum()), L_p50=float(np.median(L)), L_p5=float(np.percentile(L, 5)),
                       L_p95=float(np.percentile(L, 95)), rough_p50=float(np.median(rough[m])),
                       coat_p50=float(np.median(coat[m])), coat_p5=float(np.percentile(coat[m], 5)),
                       coat_p95=float(np.percentile(coat[m], 95)),
                       v0_p50=float(np.median(v0[m])), v0_p99=float(np.percentile(v0[m], 99)),
                       sheen_p50=float(np.median(sheen[m])), sheen_p95=float(np.percentile(sheen[m], 95)),
                       sheen_cover=float((sheen[m] > 0.05).mean()))
    # the normal: the bake's tangent normal tilted by the relief's mean slope over each texel (what a texel resolves)
    tn = nrm[..., :3].copy()
    sel = zid >= 0
    nz = np.maximum(nb[..., 2], 1e-6)
    tn[..., 0] = np.where(sel, tn[..., 0] - nb[..., 0] / nz, tn[..., 0])
    tn[..., 1] = np.where(sel, tn[..., 1] - nb[..., 1] / nz, tn[..., 1])
    tn /= np.maximum(np.linalg.norm(tn, axis=-1, keepdims=True), 1e-12)
    alb = np.clip(alb, 0.010, 0.65)
    rough = np.clip(rough, 0.05, 1.0)
    coat = np.clip(coat, 0.03, 1.0)
    cell = np.zeros((size, size))
    cell[ys, xs] = _hash3(g[:, 0], g[:, 1], g[:, 2], 23)
    a8 = lambda x: np.clip(np.asarray(x) * 255.0 + 0.5, 0, 255).astype(np.uint8)         # noqa: E731
    maps = dict(albedo=a8(np.where(cov[..., None], _encode_albedo(alb), 0.5)),
                normal=a8(np.where(cov[..., None], tn * 0.5 + 0.5, [0.5, 0.5, 1.0])),
                orm=a8(np.where(cov[..., None], np.stack([ao, rough, coat], -1), [1.0, 0.5, 0.5])),
                masks=a8(np.stack([thin, sheen, accent, coat_loss], -1) * cov[..., None]),
                display=a8(np.stack([pid, irid, np.zeros_like(pid), cell], -1) * cov[..., None]),
                growth=np.zeros((size, size, 4), np.uint8))
    log(f'[cuticle] {size}^2 (real scale): ' + ', '.join(
        f'{z} L p50 {r["L_p50"]:.4f} (p5 {r["L_p5"]:.4f}, p95 {r["L_p95"]:.4f}) base rough {r["rough_p50"]:.2f}, coat '
        f'{r["coat_p50"]:.2f} (p5 {r["coat_p5"]:.2f}, p95 {r["coat_p95"]:.2f}), sub-texel variance p50 {r["v0_p50"]:.1e}, '
        f'the setae\'s sheen p95 {r.get("sheen_p95", 0.0):.2f} on {100.0 * r.get("sheen_cover", 0.0):.0f} % '
        f'({r["texels"]:,} texels)' for z, r in rep.items()))
    return maps, cov, rep
