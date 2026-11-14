"""THE HORN MATERIAL STAGE: ONE stage and ONE runtime material for antler bone, keratin sheaths (horns, hoof walls),
fibre horn and ivory (work/bestiary/research/DEER_PLAN.md §5.5 with DEER_CRITIC.md §2-§3; the build's notes
work/bestiary/deer/horns/build_NOTES.md). "Horn" is the hoof wall's own tissue name, so the hoof generator's rows come
here as DATA (a row of RECIPES): it writes no stage of its own.

THE INTERFACE
    maps, rep = material(drivers, fields, recipe, px_per_m)
      drivers  a bake's arrays in image order (forge/bake.py or bake_mesh.py): normal (tangent rgb, coverage a), ao,
               cavity, curvature, position (world xyz, the host's axes at rest: x left, y up, z forward), region,
               and mat (the strokes' packed ids; optional)
      fields   what the part's generator knows about each texel, rasterised from its low by raster(): every key is
               optional and reads 0 when absent
                 along   0 at the part's root (the burr, the coronet) .. 1 at its far end: the stain's slow gradient
                 tip     0 .. 1 along a branch that ENDS IN A TIP (a tine, a beam's top, a whole horn); 0 where the
                         surface is on no such branch. The polish zone grows from 1 downward
                 young   0 .. 1 the young root / soft horn (a sheath's base band, a hoof's periople and bulb)
                 bare    1 on a cut or cast face (an antler's seal): unstained bone
                 shared  1 on texels a stack shares (a class template): the world-axis rules are left out there (the
                         copies face other ways) and ride per vertex instead (vertex_colors)
                 nx, ny, nz   the LOW's world normal (the broad form's facing, for the world-axis rules)
                 qa, qb, qs   the texel's place in ITS BRANCH'S OWN FRAME, metres: qa, qb across (the offsets from
                         the centreline along the frame's two section axes), qs along (the arc length; a part adds
                         a constant per branch so two branches are not twins). The stain's blotches and the
                         polished bone's fine streaks are a noise on (qa, qb, qs / stretch): they follow the
                         branch round every bend, with no seam round it. A CURVED BRANCH NEEDS THESE (11-11: with
                         tx ty tz s alone the streaks lay up to 60 deg off the branch on the curled tines and ran
                         ACROSS the trunk where it turns at the brow; `stretched` below has the measurement)
                 qa2, qb2, qs2, mix2   a SECOND frame and its weight 0..1, on a fork's saddle: the pattern there
                         is the first frame's (the beam's) cross-faded into the second's (the tine's) by mix2, so
                         it runs unbroken from the beam onto the saddle and from the saddle up the tine. (One
                         frame's coordinates blended into the other's by interpolation squeeze the noise into
                         bars round the tine's foot instead.)
                 tx, ty, tz, s   the branch's unit tangent and its arc length (metres) under the texel, for a
                         STRAIGHT part that gives no qa qb qs: the blotches stretch along it (with neither, the
                         blotches are round)
                 fork    1 where the blotches must fade (a part that cannot carry a frame across a fork; the
                         antler does: mix2, h09_material.vertex_fields)
                 tipvar  a shift added to `tip` where the polish is decided, one value per branch (fix round 1:
                         each tine its own ivory length; absent: 0)
      recipe   a row of RECIPES: colours in linear light, roughnesses and each rule's weights. Data only
      returns  maps: albedo (sRGB8), normal (the bake's tangent normal, uint8), orm (R occlusion, G roughness, B
               metalness 0), masks (RGBA uint8); rep: the medians a look is judged by
    MASKS (the runtime's hornMaterial reads them; a plain PBR viewer ignores them)
      R  the TINT ZONE: the stained or pigmented share of the surface (hornColor / hoofColor tint here; polished
         ivory and bare bone keep their own colour)
      G  POLISH: worn smooth (tips, convex tops, the rubbed side)
      B  YOUNG ROOT / SOFT HORN
      A  WEAR in the world's axes (dust settled on faces that look up, rubbing on faces that look forward)
    COLOR_0 per vertex (vertex_colors): rgb a tint per branch (a stack's copies must not be identical twins), a the
      dust for vertices whose texels are shared
    IDS  the strokes' material ids are 96-111 (horn_surface.HORN_IDS: bead 96, pearl 97, gutter 98, ring 99), above
      growth.ID_RANGES' growth 1-63 and cyborg 64-95 (staged there as horn=(96, 111): deer/STAGED.md)

OPTIONS FOR OTHER TISSUES (the hoof builder's, 11-10, staged in work/bestiary/deer/STAGED.md and taken in here on
11-10 23:10; a recipe that names none of them, the antler's, is painted exactly as before):
      recipe['young']   dict(albedo, rough): the young root's OWN colour and roughness (a hoof's periople is a pale
                        matte film; without the row `young` only takes the stain off)
      recipe['rough']['flat']   an offset on the base row's roughness (growth's keratin 0.60 is a dry sheath; a hoof's
                        wall is glossier)
      recipe['layers']  an ordered list of rows, each painting one more TISSUE ZONE or MARK over the rules' result
                        where its field says so (a hoof's bulb, bearing rim, white line, sole; scuffs, scratches,
                        chips; later a sheath's broomed tip, a tusk's cementum):
                          field    the `fields` key that holds its weight 0..1 (the part's generator makes it)
                          amount   the weight's gain (1); within / outside: fields that multiply it (f / 1 - f)
                          albedo   linear rgb the colour mixes toward; gain=(field, amp): that colour scaled by
                                   1 + amp (2 f - 1) (the zone's own mottle); cavity: how much the bake's crevices
                                   darken it (0)
                          rough    the roughness it mixes toward (absent: untouched)
                          tint     the share of the layer that stays in MASKS R (1; 0: not pigmented horn)
                          young, polish, wear   what it adds to MASKS B, G, A (0)
      fields['dust']    dust the generator knows of (a hoof's line by height above its sole, in the stand frame),
                        added to the world's up-facing dust
      recipe['polish']['climb']   dict(amp, cell, stretch) (fix round 1): a noise stretched along the branch added to
                        the polish threshold, so the ivory climbs the ridges in streaks (needs qa qb qs for a curved
                        part: `stretched`)
      recipe['rough']['bead']   (fix round 1, continued, 11-11) an offset on the roughness of the burr's beads (the
                        stroke id 96): a living stag's coronet is a matte crust; with the tops' smoothing alone its
                        knobs shone as glossy beads at 0.5 m (build/tmp/fix2/close_burr_crop.png)

THE RULES, each a weight in the recipe (0 switches it off):
  STAIN   how much of the stained colour a texel carries: its flat share, more in cavities (the bake's cavity and
          the AO's local dip) and on channel floors (the gutter id), less on convex tops (pearls and ridges are worn
          pale), less up the part (`along`); none where polished, none on a bare face
  POLISH  from `tip`: a band round the recipe's `from` (0.62 on a red deer's tines), convex tops polishing lower
          down than the channels beside them (the line is ragged, as on the photos); + the rubbed side
  COLOUR  bare < pale (worn tops) < mid (stained flats) < dark (channel floors) by the stain, toward `ivory` by
          the polish; a slow 3D mottle
  ROUGH   the base's, rougher in cavities, smoother on worn tops, the polished value where polished
  WEAR    dust on up-facing texels (more in cavities: paler, rougher), rubbing on forward-facing convex tops
"""
import numpy as np

# hard antler: the bone under everything is growth.RECIPES['bone'] (physicallybased.info Bone scaled into the skin
# envelope: its roughness, ior and sss are read from that row at run time); the zones are mine. Colours in LINEAR
# light. [M-ph]: medians of the brightness bands of refs c11 Cervus_elaphus_AM_LM369-6 (a tine close, studio light):
# p05 (0.159, 0.078, 0.054), p25 (0.262, 0.136, 0.078), p50 (0.474, 0.319, 0.235); a museum antler is handled and
# pale, a stag's in September is darker, so mid and dark are taken down [E: beside the photos at the engine render]
RECIPES = dict(
    antler_hard=dict(
        base='bone',
        # 11-11, the first WHOLE antler lit beside the shed-antler photo (build/look/h09_look_whole_a_first_recipe
        # .png -> _b): (1) the tips read as dipped in grey-white paint: the polish came on inside 0.21 of a tine's
        # length (u 0.48 -> 0.69) to a grey ivory. On the photos the stain thins over most of a tine: ridges go pale
        # first, grooves hold their dark far up, only the last part is smooth ivory. So the band is u 0.36 -> 1.02
        # with tops polishing 0.30 earlier and crevices 0.38 later, and the ivory is warmer. (2) the pearls read as
        # pale dashes scattered evenly from the burr to the tips: on the photo's lower beam the ridges are only a
        # little paler than the dark ground, the burr's knobs alone are white-topped; the tops' paleness now starts
        # at `top_base` of its weight at a tine's root and reaches all of it at `top_rise` (the burr's beads keep
        # all of it: `bead_top`). (3) mid and pale a little darker and warmer (a stag in September, not a museum's
        # handled antler)
        ivory=(0.640, 0.555, 0.380),            # the polished tips: the bone row warmed [E]
        pale=(0.380, 0.285, 0.185),             # worn pearl tops and ridges: LM369-6 p50 x 0.8 [M-ph + E]
        mid=(0.088, 0.048, 0.026),              # stained flats: LM369-6 p25 x 0.34 [M-ph + E]
        dark=(0.024, 0.013, 0.008),             # channel floors, between pearls: LM369-6 p05 x 0.16 [M-ph + E]
        bare=(0.520, 0.480, 0.390),             # the cast face (the seal): dry bone
        dust=(0.330, 0.290, 0.230),
        # conc / conc_mid: the fine (0.6 mm) and mid (3 mm) CONCAVITY (the grain's floors are too shallow for the
        # cavity rays: 6 % of the trunk read as crevice and the stain lay flat, h09_look_trunk_b_grain.png); streak:
        # the stain's own blotches, stretched along the branch (LM369-6: dark patches 3-6 mm wide, 10-25 mm long)
        stain=dict(flat=0.60, cavity=1.6, ao_local=2.2, conc=0.55, conc_mid=0.35, gutter=0.86, top=-0.52,
                   top_from=0.15, top_base=0.50, top_rise=(0.05, 0.60), bead_top=1.0, along=-0.20, streak=0.28),
        streak=dict(cell=0.0042, stretch=5.0),
        polish=dict(start=0.62, band=(0.58, 1.65), top=0.30, cavity=-0.38, rub=0.22, noise=0.09, streak=0.10,
                    fine_cell=0.0016, fine_stretch=12.0),
        rough=dict(cavity=0.14, top=-0.17, polished=0.30, fine=0.07, dust=0.08, bare=0.74),
        wear=dict(dust=0.24, rub_dir=(0.0, 0.25, 1.0)),
        mottle=dict(cell=0.016, amp=0.11),
    ),
    # THE PLAN'S DEFAULT (DEER_PLAN §12, Skye's question 2 on its bracketed default; fix round 1, 11-11): a LIVING
    # prime stag in hard antler, late summer to the rut. `antler_hard` above was tuned beside ONE sun-bleached CAST
    # antler (refs c11 Cervus_elaphus_01_by-dpc): kept, as the cast state's look. Beside it the check (check1 item 5)
    # read the brow, bay and tray as smooth glossy ivory FANGS: every tine the same dipped gradient, ivory half way
    # at u 0.575-0.625, tips 0.53, polish 0.30. On living stags (refs c11 Richmond Park 2025 01, Lyme Park, LM369-9)
    # the antler is near-black to warm grey-brown and coarsely pearled up to SHORT ivory ends, each tine its own:
    #   - flats L 0.036, channel floors 0.009, worn pearl tops ~2.5x the flats, patchy (the photo in sun: shafts
    #     p50 0.03-0.09 linear with tops p90 0.23-0.29 under the same light as the face's fur at 0.46);
    #   - the ivory over the last 12-30 % of a tine (Pz start 0.80, band 0.88-1.12: polish 0 -> 1 from u 0.70 to
    #     0.90), moved per branch by the generator's `tipvar` field and climbing the ridges in streaks (`climb`:
    #     a noise stretched along the branch on the polish threshold);
    #   - the polished ends satin, not glossy (rough 0.40); little dust on a living animal; the stain's blotches
    #     shorter and weaker (the check's "bark": stretch 5 -> 2.5, weight 0.28 -> 0.12)
    # (11-11 10:5x, the same round, after its engine stills: build/tmp/fix2/f09_engine_board_chain0930.png) the check's
    # tine measure passed (half way at u 0.72-0.82, photos 0.43-0.88), but past the half way every tine was ONE flat
    # cream (L 0.50-0.53, r/b 1.5) and the burr's knobs shone: so the ends whiter and less yellow (Richmond Park's
    # sunlit tips read near white), the ivory's fine streaks and its climb up the ridges stronger (0.10 -> 0.16,
    # 0.07 -> 0.12: a polished end with grain in it, not a smooth fang), the burr's knobs matte (`rough.bead` +0.18)
    # and less pale-topped (bead_top 0.55 -> 0.35: the Rothirsch Geweihansatz burr is a dull crust, not pale beads)
    antler_hard_living=dict(
        base='bone',
        ivory=(0.630, 0.580, 0.480),            # the ends, near white (r/b 1.31; lit tips 1.1-1.6) [M-ph + E]
        pale=(0.112, 0.088, 0.066),             # worn pearl tops [M-ph + E]
        mid=(0.044, 0.034, 0.027),              # stained flats, L 0.036 [M-ph + E]
        dark=(0.012, 0.009, 0.007),             # channel floors, between pearls [E]
        bare=(0.520, 0.480, 0.390),
        dust=(0.300, 0.270, 0.220),
        stain=dict(flat=0.62, cavity=1.5, ao_local=2.0, conc=0.55, conc_mid=0.35, gutter=0.86, top=-0.42,
                   top_from=0.15, top_base=0.40, top_rise=(0.05, 0.60), bead_top=0.35, along=-0.08, streak=0.12,
                   top_patch=dict(cell=0.030, amp=0.60)),
        streak=dict(cell=0.0060, stretch=2.5),
        polish=dict(start=0.80, band=(0.88, 1.12), top=0.10, cavity=-0.12, rub=0.10, noise=0.05, streak=0.16,
                    fine_cell=0.0016, fine_stretch=12.0, climb=dict(amp=0.12, cell=0.0035, stretch=7.0)),
        rough=dict(cavity=0.12, top=-0.12, polished=0.40, fine=0.07, dust=0.08, bare=0.74, bead=0.18),
        wear=dict(dust=0.10, rub_dir=(0.0, 0.25, 1.0)),
        mottle=dict(cell=0.016, amp=0.10),
    ),
)


def _sstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _hash3(i, j, k, s):
    # (families/arthropod_skin.py's hash and value noise, copied: that module pulls the beetle's whole skin in)
    h = (i * 73856093) ^ (j * 19349663) ^ (k * 83492791) ^ (s * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def value_noise(P, cell, seed):
    """trilinear value noise in [0, 1] on 3D points P (n, 3), cells of the given size"""
    g = np.floor(P / cell).astype(np.int64)
    fr = P / cell - g
    s3 = fr * fr * (3 - 2 * fr)
    out = np.zeros(len(P))
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                w = (s3[:, 0] if di else 1 - s3[:, 0]) * (s3[:, 1] if dj else 1 - s3[:, 1]) * \
                    (s3[:, 2] if dk else 1 - s3[:, 2])
                out += w * _hash3(g[:, 0] + di, g[:, 1] + dj, g[:, 2] + dk, seed)
    return out


def blur3d(P, X, sigma, cell_share=0.5):
    """a Gaussian of the columns of X (n, k) over the 3D points P (n, 3) (a bake's hit positions): SEAM-FREE. A
    blur in UV space stops at every island's border, so whatever is band-passed with it (the AO's local dip, a
    mid-scale convexity) steps at every seam, and the stain painted from it showed each island's outline (the
    trunk at a 55 mm frame, work/bestiary/deer/horns/build/tmp/h09d_zoom_rect.png). Here the points are binned in
    cells of cell_share * sigma, the cells blurred among themselves (pairs within 3 sigma, weighted by their
    counts), and every point reads the four cells nearest to it. Returns (n, k)"""
    from scipy.sparse import coo_matrix, diags
    from scipy.spatial import cKDTree
    P = np.asarray(P, np.float64)
    X = np.asarray(X, np.float64).reshape(len(P), -1)
    cell = float(sigma) * cell_share
    g = np.floor(P / cell).astype(np.int64)
    g -= g.min(0)
    dims = g.max(0) + 1
    key = (g[:, 0] * dims[1] + g[:, 1]) * dims[2] + g[:, 2]
    uq, inv = np.unique(key, return_inverse=True)
    m = len(uq)
    cnt = np.bincount(inv, minlength=m).astype(np.float64)
    C = np.column_stack([np.bincount(inv, P[:, a], m) for a in range(3)]) / cnt[:, None]
    V = np.column_stack([np.bincount(inv, X[:, a], m) for a in range(X.shape[1])]) / cnt[:, None]
    tree = cKDTree(C)
    S = tree.sparse_distance_matrix(tree, 3.0 * float(sigma), output_type='coo_matrix')
    off = S.row != S.col
    W = coo_matrix((np.exp(-0.5 * (S.data[off] / sigma) ** 2) * cnt[S.col[off]], (S.row[off], S.col[off])),
                   shape=(m, m)).tocsr() + diags(cnt)
    B = (W @ V) / np.maximum(W @ np.ones(m), 1e-30)[:, None]
    d, j = tree.query(P, k=min(4, m))
    d, j = d.reshape(len(P), -1), j.reshape(len(P), -1)
    w = np.exp(-0.5 * (d / cell) ** 2) + 1e-12
    return (B[j] * w[..., None]).sum(1) / w.sum(1)[:, None]


def raster(UV, F, attrs, size):
    """per-vertex attributes (n, k) rasterised into the UV layout: per texel (image order: row 0 is v = 1) the
    value under its centre, then every other texel filled from the nearest covered one (so a texel the bake covers
    by a sub-sample alone, and the gutters, read their island's value). Returns (size, size, k) float32"""
    from scipy import ndimage
    A = np.asarray(attrs, np.float64)
    T = np.asarray(UV, np.float64) * size
    out = np.zeros((size, size, A.shape[1]), np.float32)
    hit = np.zeros((size, size), bool)
    for f in np.asarray(F):
        a, b, c = T[f]
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if x1 < x0 or y1 < y0 or abs(den) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        l2 = 1.0 - l0 - l1
        ins = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        yy, xx = size - 1 - gy[ins].astype(int), gx[ins].astype(int)
        out[yy, xx] = (l0[ins][:, None] * A[f[0]] + l1[ins][:, None] * A[f[1]] + l2[ins][:, None] * A[f[2]])
        hit[yy, xx] = True
    idx = ndimage.distance_transform_edt(~hit, return_distances=False, return_indices=True)
    return out[idx[0], idx[1]]


def material(drivers, fields, recipe, px_per_m, log=print):
    """the horn material of a bake (module docstring). Returns (maps, rep)"""
    from .. import growth as GR
    from .. import material as MT
    R = recipe
    base = GR.RECIPES[R['base']]
    size = drivers['normal'].shape[0]
    nrm = np.asarray(drivers['normal'], np.float64)
    cov = nrm[..., 3] > 0
    f = lambda k: np.asarray(fields[k], np.float64) if k in fields else np.zeros((size, size))    # noqa: E731
    along, tip, young, bare, shared = f('along'), f('tip'), f('young'), f('bare') > 0.5, f('shared') > 0.5
    low_n = np.stack([f('nx'), f('ny'), f('nz')], -1)
    low_n /= np.maximum(np.linalg.norm(low_n, axis=-1, keepdims=True), 1e-12)
    cav = 1.0 - np.asarray(drivers['cavity'], np.float64)                  # 0 open .. 1 a closed cavity
    ids = (np.asarray(drivers['mat'], np.int64) & 255) if 'mat' in drivers else np.zeros((size, size), np.int64)
    gutter = ids == 98
    P = np.asarray(drivers['position'], np.float64)[..., :3]
    ys, xs = np.nonzero(cov)
    Pc = P[ys, xs]
    # ---- the relief's bands, IN SPACE (blur3d: no UV seam in them; calib.relief_drivers blurs in UV and stepped
    # at every island's border). conv: the bake's own curvature (a voxel's scale) over its p95, +-3, positive on a
    # bump; conv_mid: the same averaged over 3 mm; aol: the AO minus its average over 6 mm (negative in a dip)
    unit = lambda x: np.clip(x / max(float(np.percentile(np.abs(x), 95)), 1e-12), -3.0, 3.0)      # noqa: E731
    curv = np.asarray(drivers['curvature'], np.float64)[ys, xs]
    ao_c = np.asarray(drivers['ao'], np.float64)[ys, xs]
    aol, conv, conv_mid = np.zeros((size, size)), np.zeros((size, size)), np.zeros((size, size))
    conv[ys, xs] = unit(curv)
    conv_mid[ys, xs] = unit(blur3d(Pc, curv, R.get('mid_mm', 3.0) * 1.0e-3)[:, 0])
    aol[ys, xs] = ao_c - blur3d(Pc, ao_c, R.get('ao_mm', 6.0) * 1.0e-3)[:, 0]
    crev = np.zeros((size, size))
    top = np.zeros((size, size))
    S, Pz, Rg = R['stain'], R['polish'], R['rough']
    crev[cov] = np.clip(S['cavity'] * cav[cov] + S['ao_local'] * np.clip(-aol[cov], 0.0, 1.0)
                        + S.get('conc', 0.0) * np.clip(-conv[cov], 0.0, 2.0)
                        + S.get('conc_mid', 0.0) * np.clip(-conv_mid[cov], 0.0, 2.0), 0.0, 1.0)
    t0 = S.get('top_from', 0.0)
    top[cov] = np.clip((0.7 * conv[cov] + 0.5 * conv_mid[cov] - t0) / (1.0 - t0), 0.0, 1.0) * (1.0 - crev[cov])
    # ---- WHERE A PATTERN STRETCHED ALONG THE BRANCH LIVES. In the branch's OWN frame when the part gives it
    # (fields qa qb qs, with qa2 qb2 qs2 mix2 on a fork's saddle: the module docstring): the noise's domain is
    # (qa, qb, qs / stretch), which follows the branch round every bend. THE FIRST VERSION took the texel's WORLD
    # position less its share along the local tangent, + tangent x station / stretch: right on a straight branch
    # only. Where the tangent turns, the share taken off changes by (P . t) x the turn, so the pattern SLIDES
    # sideways by |P . t| x curvature per unit of length: 300 mm from the origin on a tine curled at 1 / 170 mm
    # that is 1.8 mm across per mm along, a streak 60 deg off the branch. The streak audit found it on 11-11
    # (build/scripts/h15_streak_audit.py: 10 clusters of bars, 11.3 cm2, on the curled tines' polished tips and
    # ACROSS the trunk where it turns 41 deg at the brow; build/tmp/now/audit_crops_0.jpg, _1.jpg).
    def stretched(stretch, octaves):
        """the octaves' value noise ((weight, cell, seed), ...; weights sum to 1) per covered texel, stretched
        `stretch` x along the branch"""
        mix = lambda D: sum(w_ * value_noise(D, c_, s_) for w_, c_, s_ in octaves)               # noqa: E731
        if 'qa' in fields:
            dom = lambda a_, b_, s_: np.stack([f(a_)[ys, xs], f(b_)[ys, xs], f(s_)[ys, xs] / stretch], -1)   # noqa
            v = mix(dom('qa', 'qb', 'qs'))
            w2 = np.clip(f('mix2')[ys, xs], 0.0, 1.0) if 'qa2' in fields else np.zeros(len(ys))
            m = w2 > 0.0
            if m.any():
                # a fork's saddle: the two frames' patterns cross-faded, their contrast kept (a plain mix of two
                # independent noises loses 29 % of it half way)
                v2 = mix(dom('qa2', 'qb2', 'qs2')[m])
                v[m] = 0.5 + ((1.0 - w2[m]) * (v[m] - 0.5) + w2[m] * (v2 - 0.5)) / np.sqrt((1.0 - w2[m]) ** 2
                                                                                           + w2[m] ** 2)
            return v
        if 'tx' in fields:                                   # a STRAIGHT part's tangent and station
            t = np.stack([f('tx'), f('ty'), f('tz')], -1)[ys, xs]
            t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
            return mix(Pc - (Pc * t).sum(1)[:, None] * t + t * (f('s')[ys, xs] / stretch)[:, None])
        return mix(Pc)

    # ---- the stain's own blotches: a noise stretched along the branch (`fork` 1 fades them, for a part that
    # cannot carry a frame across a fork)
    streak = np.zeros((size, size))
    if S.get('streak', 0.0) > 0.0:
        K = R['streak']
        sn = stretched(K['stretch'], ((0.65, K['cell'], 23), (0.35, K['cell'] * 0.37, 29)))
        streak[ys, xs] = (sn - 0.5) * 2.0 * (1.0 - np.clip(f('fork')[ys, xs], 0.0, 1.0))
    # ---- POLISH: toward the tips, convex tops first, channels last; a ragged line (a slow noise on the threshold)
    wob = np.zeros((size, size))
    wob[ys, xs] = (value_noise(Pc, 0.012, 61) - 0.5) * 2.0 * Pz['noise']
    u = tip + wob + Pz['top'] * top + Pz['cavity'] * crev
    # (fix round 1, both OPTIONAL: a part that gives no `tipvar` field and a recipe with no `climb` paint as before)
    # each branch's own polish line (the generator's per-branch shift of `tip`: every tine wore the same dipped
    # gradient), and the ivory CLIMBING THE RIDGES IN STREAKS (a noise stretched along the branch on the threshold)
    if 'tipvar' in fields:
        u = u + f('tipvar')
    if Pz.get('climb'):
        Cl = Pz['climb']
        cn = np.zeros((size, size))
        cn[ys, xs] = (stretched(Cl['stretch'], ((0.7, Cl['cell'], 47), (0.3, Cl['cell'] * 0.45, 53))) - 0.5) * 2.0
        u = u + Cl['amp'] * cn
    pol = _sstep(Pz['start'] * Pz['band'][0], Pz['start'] * Pz['band'][1], u) * (tip > 1e-4)
    # ---- the WORLD's axes (left out where a stack shares the texels)
    rd = np.asarray(R['wear']['rub_dir'], np.float64)
    rd = rd / np.linalg.norm(rd)
    own = cov & ~shared
    rub = np.where(own, _sstep(0.10, 0.85, low_n @ rd) * top, 0.0)
    dust = np.where(own, _sstep(0.25, 0.90, low_n[..., 1]) * (0.35 + 0.65 * crev), 0.0) * (1.0 - 0.7 * pol)
    if 'dust' in fields:                                     # the generator's own dust (a hoof's line by height)
        dust = np.clip(dust + np.where(cov, f('dust'), 0.0), 0.0, 1.0)
    pol = np.clip(pol + Pz['rub'] * rub * (1.0 - pol), 0.0, 1.0)
    # ---- STAIN. The worn tops' paleness by zone (a recipe that names no `top_base` paints as before): tw of its
    # weight at a tip-ended branch's root (and all along a branch that ends in no tip), all of it from top_rise[1]
    # of the way to the tip; the burr's beads (id 96) their own share
    tw = 1.0
    if 'top_base' in S:
        r0, r1 = S.get('top_rise', (0.05, 0.60))
        tw = S['top_base'] + (1.0 - S['top_base']) * _sstep(r0, r1, tip)
        if 'top_patch' in S:
            # RUBBED ZONES: the tops' paleness comes in patches (a slow noise in space), not evenly. With one weight
            # for the whole beam every pearl was the same pale dash on the same dark ground: rows of stitches at a
            # 300 mm frame, where the photo's lower beam has a few pale flecks here and none there
            tp = S['top_patch']
            pn = np.zeros((size, size))
            pn[ys, xs] = _sstep(0.30, 0.70, value_noise(Pc, tp['cell'], 71))
            tw = tw * np.clip(1.0 + tp['amp'] * (2.0 * pn - 1.0), 0.0, None)
        if S.get('bead_top') is not None:
            tw = np.where(ids == 96, S['bead_top'], tw)
    st = S['flat'] + (1.0 - S['flat']) * crev + S['top'] * top * tw + S['along'] * along \
        + S.get('streak', 0.0) * streak
    st = np.where(gutter, np.maximum(st, S['gutter']), st)
    st = np.clip(st, 0.0, 1.0) * (1.0 - pol) * (1.0 - young)
    st = np.where(bare, 0.0, st)
    # ---- COLOUR (linear): pale -> mid -> dark by the stain, toward ivory by the polish, the bare face its own
    pale, mid, dark, ivory = (np.asarray(R[k], np.float64) for k in ('pale', 'mid', 'dark', 'ivory'))
    a = np.clip(st / 0.55, 0.0, 1.0)[..., None]
    b = np.clip((st - 0.55) / 0.45, 0.0, 1.0)[..., None]
    col = (pale * (1.0 - a) + mid * a) * (1.0 - b) + dark * b
    # the polished bone's own fine streaks (recipe polish.streak; 0 or absent: a flat ivory, as before): a noise of
    # cells `fine_cell` stretched `fine_stretch` x along the branch darkens and warms the ivory a little and
    # roughens it (a smooth flat ivory read as plastic at a 200 mm frame: h09_look_whole_b, the brow tip)
    fine = np.zeros((size, size))
    if Pz.get('streak', 0.0) > 0.0:
        fc = Pz.get('fine_cell', 0.0016)
        fine[ys, xs] = np.clip(stretched(Pz.get('fine_stretch', 12.0), ((0.6, fc, 37), (0.4, fc * 0.41, 41))),
                               0.0, 1.0)
        fine = np.clip((fine - 0.35) / 0.45, 0.0, 1.0)
        ivory = ivory[None, None] * (1.0 - Pz['streak'] * fine[..., None] * np.array([1.0, 1.25, 1.9]))
    col = col * (1.0 - pol[..., None]) + ivory * pol[..., None]
    col = np.where(bare[..., None], np.asarray(R['bare'], np.float64) * (1.0 - 0.35 * crev[..., None]), col)
    # ---- THE YOUNG ROOT'S OWN COLOUR, then THE LAYERS: further tissue zones and marks by their fields (the hoof
    # builder's options, taken in from work/bestiary/deer/hooves/priv/forge/families/horn_skin.py)
    st_m, pol_m, young_m, wear_m, lay = st, pol, young, None, []
    Y = R.get('young')
    if Y is not None:
        col = col * (1.0 - young[..., None]) + np.asarray(Y['albedo'], np.float64) * young[..., None]
    for Ly in R.get('layers', ()):
        w = f(Ly['field']) * float(Ly.get('amount', 1.0))
        if 'within' in Ly:
            w = w * np.clip(f(Ly['within']), 0.0, 1.0)
        if 'outside' in Ly:
            w = w * (1.0 - np.clip(f(Ly['outside']), 0.0, 1.0))
        w = np.where(cov, np.clip(w, 0.0, 1.0), 0.0)
        if 'albedo' in Ly:
            a_l = np.asarray(Ly['albedo'], np.float64)[None, None] * np.ones((size, size, 1))
            if 'gain' in Ly:
                a_l = a_l * (1.0 + float(Ly['gain'][1]) * (2.0 * np.clip(f(Ly['gain'][0]), 0.0, 1.0) - 1.0))[..., None]
            if Ly.get('cavity'):
                a_l = a_l * (1.0 - float(Ly['cavity']) * crev)[..., None]
            col = col * (1.0 - w[..., None]) + a_l * w[..., None]
        st_m = st_m * (1.0 - w * (1.0 - float(Ly.get('tint', 1.0))))
        pol_m = np.maximum(pol_m * (1.0 - w), w * float(Ly.get('polish', 0.0)))
        young_m = np.maximum(young_m, w * float(Ly.get('young', 0.0)))
        if Ly.get('wear'):
            wear_m = w * float(Ly['wear']) if wear_m is None else np.maximum(wear_m, w * float(Ly['wear']))
        lay.append((w, Ly))
    mot = np.zeros((size, size))
    mot[ys, xs] = (value_noise(Pc, R['mottle']['cell'], 11) - 0.5) * 2.0 * R['mottle']['amp']
    col = col * np.exp(mot * (1.0 - 0.6 * pol))[..., None]
    wd = (R['wear']['dust'] * dust)[..., None]
    col = col * (1.0 - wd) + np.asarray(R['dust'], np.float64) * wd
    col = np.clip(col, 0.010, 0.65)                          # the albedo envelope (remix/elements.py, REF R2)
    # ---- ROUGHNESS
    rough = float(base['rough']) + Rg['cavity'] * crev + Rg['top'] * top
    if 'flat' in Rg:                                         # the recipe's own offset on the base row's roughness
        rough = rough + Rg['flat']
    if 'bead' in Rg:                                         # the burr's beads their own (OPTIONAL: absent, as before)
        rough = rough + Rg['bead'] * (ids == 96)
    rough = rough * (1.0 - pol) + (Rg['polished'] + Rg.get('fine', 0.0) * fine) * pol + Rg['dust'] * dust
    if Y is not None:                                        # the young root's, then each layer's
        rough = rough * (1.0 - young) + (Y['rough'] + Rg['dust'] * dust) * young
    for w, Ly in lay:
        if 'rough' in Ly:
            rough = rough * (1.0 - w) + (float(Ly['rough']) + Rg['dust'] * dust) * w
    rough = np.where(bare, Rg['bare'], rough)
    rough = np.clip(rough, 0.08, 1.0)
    wear = np.clip(0.6 * dust + 0.6 * rub, 0.0, 1.0)
    if wear_m is not None:
        wear = np.maximum(wear, wear_m)
    a8 = lambda x: np.clip(np.asarray(x) * 255.0 + 0.5, 0, 255).astype(np.uint8)                   # noqa: E731
    ao = np.asarray(drivers['ao'], np.float64)
    maps = dict(albedo=a8(np.where(cov[..., None], np.asarray(MT.srgb_oetf(col)), 0.5)),
                normal=a8(np.where(cov[..., None], nrm[..., :3] * 0.5 + 0.5, [0.5, 0.5, 1.0])),
                orm=a8(np.where(cov[..., None], np.stack([ao, rough, np.zeros_like(rough)], -1), [1.0, 0.6, 0.0])),
                masks=a8(np.stack([st_m, pol_m, young_m, wear], -1) * cov[..., None]))
    L = 0.2126 * col[..., 0] + 0.7152 * col[..., 1] + 0.0722 * col[..., 2]
    q = lambda x, m: [round(float(v), 4) for v in np.percentile(x[m], [5, 50, 95])] if m.any() else None   # noqa
    rep = dict(texels=int(cov.sum()), albedo_L_p5_p50_p95=q(L, cov), rough_p5_p50_p95=q(rough, cov),
               stain_p5_p50_p95=q(st, cov), polished_pct=round(float((pol[cov] > 0.5).mean()) * 100, 2),
               crevice_pct=round(float((crev[cov] > 0.5).mean()) * 100, 2),
               top_pct=round(float((top[cov] > 0.5).mean()) * 100, 2),
               dust_pct=round(float((dust[cov] > 0.3).mean()) * 100, 2),
               stained_L_p50=q(L, cov & (pol < 0.1) & ~bare), polished_L_p50=q(L, cov & (pol > 0.9)),
               base=dict(row=R['base'], rough=float(base['rough']), ior=float(base['ior']), sss=float(base['sss'])))
    log(f'[horn_skin] {size}^2: albedo L p5/p50/p95 {rep["albedo_L_p5_p50_p95"]}, rough {rep["rough_p5_p50_p95"]}, '
        f'polished {rep["polished_pct"]} %, crevices {rep["crevice_pct"]} %, worn tops {rep["top_pct"]} %')
    return maps, rep


def vertex_colors(N, branch_id, shared, seed=5, jitter=0.05):
    """COLOR_0 (n, 4) float32: rgb a tint per branch (a darkening of up to 2 x `jitter` in lnL, the same for every
    vertex of a branch, never over 1: the copies of a stack are not identical twins), a the up-facing dust for
    vertices whose texels are shared (0 elsewhere: their texels carry it)"""
    rng = np.random.default_rng(seed)
    ids = np.unique(branch_id)
    tint = {int(i): float(np.exp(rng.uniform(-2.0 * jitter, 0.0))) for i in ids}
    rgb = np.array([tint[int(i)] for i in branch_id])
    a = np.where(np.asarray(shared, bool), _sstep(0.25, 0.90, np.asarray(N)[:, 1]), 0.0)
    return np.column_stack([rgb, rgb, rgb, a]).astype(np.float32)
