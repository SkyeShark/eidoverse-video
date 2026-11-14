"""H3 (HUMAN_PLAN §5.1's relief tiers, §9.2's H3 row; the lead's H3 brief to the forge builder: "the sculpt plan's tiers
(pores, fine wrinkles, age) on the voxel highs per grid"): THE HUMAN'S SCULPT PLAN. Step script:
work/bestiary/human/h3/h3_bake.py.

THE TIERS (plan §5.1, SKIN_AND_DETAIL.md:25-30):
  S (>= about 1 mm, in the high): the clay already carries GNM's nasolabial fold, lid creases and lip forms and hm08's
    navel, knuckles and folds. What this plan ADDS to the voxel high as carve strokes (voxel.SparseSDF.strokes, capsule
    runs on the surface, fillet k, then the house's smooth and relevel): the NECK RINGS (horizontal neck lines, present
    young) and the AGE LINES by region (forehead, glabellar, crow's feet, under-eye), each weighted by age_weight().
  T (>= about 3 texels, the HEAD set at ~10,500 px/m: 0.095 mm a texel): composed per texel at the bake (relief_at in
    h3_bake's compose kernel, the beetle's micro method: n' = normalize(n_macro - grad_s h) at the high's own surface
    point), not in the voxels: a 0.45 mm pore is 3 voxels of the head's 0.15 mm grid, which a trilinear field blurs to a
    smudge, while the composed relief is exact at the texel. PORES (a jittered lattice in 3-D, one pore per cell, its
    cell 1 / sqrt(density)), the PRIMARY LINES (the microrelief network: grooves on the cell walls of a finer jittered
    lattice), the LIP LINES (vertical furrows on the vermilion). Per cage vertex params() gives each term's amount, the
    bake interpolates them over the low's triangles.
  R (the runtime): the body's pores and finer (about 1 texel at the BODY set's 3,100 px/m): the material builder's
    tiling micro-normal. The BODY bake composes no T relief (it would alias at 0.32 mm a texel).
  (h3b-sculpt-4, the H3b forge builder) THE T TIER AS A NETWORK: network() lays the pores and the furrow network's nodes
    as blue noise on the surface (repulsion on the LOW, projected onto the high), the furrows the Gabriel graph of all the
    nodes, so the lines meet at the pores; the primary lines at the plan's 30-100 um (LINE). The compose kernel reads them
    through two hash grids (human_relief.relief_v4); relief_grad (v3) stays for H3's recompose. The neck rings start at 33
    / 30, so the baselines carve none (AGE_SIGNS).
  (h3b-sculpt-5, the forge builder's successor) A HIERARCHY, as real skin has: the long PRIMARY lines (walks on the graph that
    keep their heading across many cells, the literature's 30-100 um: here 34-52) and the fine SECONDARY lines between them
    (its 5-40 um: here 9-21); each furrow a wide valley with a narrow crease, so the plateaus are pillows, not tiles
    (human_relief.relief_v5; forge probe p06 compared the profiles beside the photo through the map's own texel).
  (h3b-sculpt-7, 10-31) A FACE'S SCALE (LINE's note), the pores FUNNELS with a core (human_relief.PORE_CORE) and a PORE MAP
    (human_relief.pore_dot, the bake's T_HEAD_pore.png): the colour a pit needs, since a scattered diffuse cannot shade one.
  (h3c-sculpt-8, 11-01, the H4 round's close-up builder) A FACE, NOT A HAND. The H3b check and integrator held the eye
    close-up and the macros: there the network read as crinkled, cracked leather (worst on the man's lids). It was fitted
    beside a HAND's macro (research/human_web/skin_photos/human_skin_close_up.jpg: deep straight furrows round raised
    plateaus); the face photos at the same scale (h3b_photos/freckles_after_summertime.jpg at ~0.04 mm / px: the lower
    lid, the cheek) show the pores and a FAINT, FINE texture of short straight strokes, mostly along one direction. So:
    the lines SHALLOW (LINE depth 14 um, x FACE_LINE's region factor: the lids 0.45, under the eye 0.6, the cheek and
    forehead 0.8; the man x SEX_LINE 1.2), FINER (CELL 0.24-0.36 mm on the face), STRAIGHTER (human_relief.WAVE_AMP),
    SHORTER (walk_mm), ALIGNED where the face's skin lines run (FACE_LINE's direction and strength: an edge across it is
    shallower; the walks start along it), each valley as wide as its cell allows (wide x cell / 0.45). The PORES a soft
    hard-core pattern (PORE_RELAX: Clark-Evans ~1.3, where H3b's 14 full relaxations made 1.69 on both heads: rows), the
    network's nodes less regular (NODE_RELAX). params() gains columns 6-10 (the line factor, the direction, the strength).

SOURCES (HUMAN_BODY_PHOTOS.md §6.1, literature_values.json): pores, Flament et al. 2015 (cheek, women 18-29: 21-91 per
cm2 by origin, Caucasian 64; mean pore area 0.16 mm2 -> radius ~0.23 mm; visible 250-500 um; growing with age); the
primary lines 30-100 um deep, secondary 5-40 um (Gougeon et al. 2022); the age signs' correlations (Flament et al. 2013:
crow's feet 0.60, glabellar 0.55, under-eye 0.55, forehead 0.34; "wrinkles only after 50" in women) and Luebberding et al.
2014 (wrinkles earlier and deeper in men; glabellar lines not before 40). Region factors and depths not in those sources
are marked [E] where they are set.
"""
import numpy as np

BASE_AGE = 30.0            # [E] the baselines' age: ANSUR II's soldiers (means ~28-30); the generator (H5) drives `age`

# ---------------------------------------------------------------------------------------------------- the T tier
# per region (GNM's region groups; the LOW's islands for the hidden ones): pore density (per cm2), pore radius (mm), the
# pore's depth (mm), the primary lines' depth (mm), the network's cell (mm). Cheek: Flament's Caucasian 18-29 (64 / cm2,
# 0.16 mm2); the others [E] by the usual dermatology ordering (the nose and its sides densest and largest, the forehead
# and chin next, the temples, lids and neck sparse)
PORE = dict(cheek=(64.0, 0.225), nose=(110.0, 0.27), forehead=(60.0, 0.21), chin=(70.0, 0.22), upper_lip=(50.0, 0.18),
            zygomatic=(55.0, 0.21), infraorbital=(35.0, 0.17), temple=(35.0, 0.18), brow=(40.0, 0.19),
            parotid=(40.0, 0.19), orbital=(12.0, 0.13), neck=(18.0, 0.16), scalp=(25.0, 0.17), ear=(15.0, 0.14))
PORE_DEPTH = 0.070          # [E] mm: a visible pore's opening reads as a 50-80 um dimple at the texel (the duct is
#                             deeper and narrower than the bake can see)
LINE = dict(depth=0.014, cell=0.50, width=0.12, wide=0.14, secondary=0.50, walk_spacing=2.5, walk_mm=(0.6, 1.8))
#                             mm. (h3b-sculpt-4) THE PRIMARY LINES AT THE PLAN'S 30-100 um (Gougeon et al. 2022; HUMAN_PLAN
#                             §5.1's T row). (h3b-sculpt-5) the walks' furrows 1-1.5 x depth, the others secondary x
#                             0.5-1.3 x depth; a furrow's valley wide x 1.15 (primary) / 0.65 (secondary) in half-width, its
#                             crease 0.045 mm + 0.4 x its depth. (v2-v3 baked 15 um on a Worley lattice's walls: at macro
#                             scale the check saw round pits and no furrow network, c10_macro; v4's narrow grooves alone
#                             read as cracked tile, p03)
#                             (h3b-sculpt-7, 10-31) A FACE, NOT A FOREARM: sculpt-5 was fitted beside a forearm macro (cells 1-2 mm):
#                             depth 0.055 (primary 57-89 um), valleys +-0.25 mm, walks 3-8 mm. Through the engine's shading (the
#                             textured twin, probe p14) that read as cracked leather at 60 mm and the deepest-wins rule hid the
#                             pores. Now primary 34-52 um (the low end of the plan's range: a young cheek), secondary 9-21 um,
#                             +-0.16 / 0.09 mm, walks 1.5-4 mm: a faint fine mesh the pores stand out of. Overall rms 12.7 um
#                             (facial Ra 10-25 um; sculpt-5 stood at 26)
#                             (h3c-sculpt-8, 11-01) STILL A FOREARM'S at the macros (the H3b check: crinkled leather at k7 and
#                             0.027 mm / px): the slope reads, not the height, and a 34-52 um line in a 0.05 mm crease stands at
#                             20-30 deg. Now 14 um x FACE_LINE's factor (primary 1-1.5 x, secondary 0.5 x 0.5-1.3 x: the cheek's
#                             primaries 10-15 um, its secondaries 3-6 um, the lids' 6-9 um); the walks 0.6-1.8 mm x cell / 0.45
# (h3b-sculpt-4) THE NETWORK'S CELL per region (mm): the spacing of its nodes, blue noise on the surface; the pores are
# nodes of it, so the furrows meet at the pores as on real skin. [E] after the photos (research/human_web/skin_photos/
# human_skin_close_up.jpg) and the dermatology ordering: finest round the eyes, coarser on the neck and scalp
# (h3c-sculpt-8) finer on the face: the face photo's strokes lie 0.25-0.4 mm apart (freckles_after_summertime.jpg, the cheek
# at ~0.04 mm / px), the hand photo's plateaus 1-2 mm; a cell is 2.5-3.8 of the HEAD's 0.095 mm texels
CELL = dict(cheek=0.32, nose=0.30, forehead=0.32, chin=0.34, upper_lip=0.30, zygomatic=0.32, infraorbital=0.26,
            temple=0.34, brow=0.34, parotid=0.36, orbital=0.24, neck=0.45, scalp=0.50, ear=0.32)
# (h3c-sculpt-8) THE FACE'S LINES per region: (the lines' depth x this, the anisotropy 0..1, the direction the lines run).
# An edge's depth x (1 - strength x (1 - cos^2)) of its angle to the direction, so lines along it keep their depth and
# lines across it lose up to `strength` of it; the primary walks start along it. Directions: 'h' the head's horizontal
# (x, projected onto the surface), 'v' its vertical, 'cheek' rising laterally at 35 deg ((sign x) cos 35, sin 35, 0): the
# face photo's cheek strokes (freckles_after_summertime.jpg); '' none. [E] the factors: the lids the thinnest skin of the
# body (0.57 mm, HUMAN_BODY_PHOTOS §6.1) and the finest texture, the under-eye next, the cheek and forehead the face's
# usual, the neck and scalp coarsest; the directions after the face's relaxed skin tension lines as the photos show them
# (the lids and the forehead horizontal, the upper lip's skin vertical)
FACE_LINE = dict(cheek=(0.90, 0.5, 'cheek'), nose=(0.70, 0.3, 'h'), forehead=(0.80, 0.5, 'h'), chin=(0.90, 0.3, 'h'),
                 upper_lip=(0.80, 0.5, 'v'), zygomatic=(0.90, 0.4, 'cheek'), infraorbital=(0.70, 0.5, 'h'),
                 temple=(0.80, 0.3, 'h'), brow=(0.80, 0.3, 'h'), parotid=(0.90, 0.3, 'cheek'), orbital=(0.60, 0.5, 'h'),
                 neck=(1.00, 0.4, 'h'), scalp=(1.00, 0.0, ''), ear=(0.80, 0.0, ''))
# (the first trial, t1 at 11-01 02:4x on a crop round the left eye: the crinkle gone and the pores leading on both heads, but
# the lower lid read plastic-smooth beside the freckled woman's (a faint fine crepe there) and the cheek's strokes hardly
# showed: the lids 0.45 -> 0.60, under the eye 0.60 -> 0.70, the cheek and the cheekbone 0.80 -> 0.90)
SEX_LINE = dict(F=1.0, M=1.2)     # [E] men's microrelief deeper (Luebberding et al. 2014: wrinkles earlier and deeper in men)
# (h3c-sculpt-8) THE RELAXATIONS (human_sculpt._relax: pairs within reach x the pair's mean spacing pushed apart): H3b's
# reach 1.5 x 14 iterations made the pores a near-lattice, Clark-Evans 1.69 on both heads (probe h4/close/probes/q01), the
# man's in rows at 15 mm. reach 0.6 x 6 gives a soft hard core, R 1.30, no pair under ~0.57 x the spacing at p5 (q03 on a
# flat patch; a Poisson pattern is R 1.0, a hexagonal lattice 2.15); the nodes at reach 0.9 x 4, R ~1.56: cells of
# varied size, still no slivers
PORE_RELAX = dict(reach=0.6, iters=6)
NODE_RELAX = dict(reach=0.9, iters=4)
VERSION = 'h3c-sculpt-8'
LIP_LINE = dict(depth=0.045, spacing=0.75, width=0.22)  # [E] mm: the vermilion's vertical furrows
SEX_PORE = dict(F=1.0, M=1.25)   # [E] the man's pores larger (area x ~1.5: radius x 1.25) and a touch denser
NECK_FADE_MM = 25.0         # the T relief fades to 0 over the neck island's last 25 mm above the neck ring (the HEAD |
#                             BODY seam: the BODY bake carries none, and the seam gate reads the decoded normal there)
PORE_R_CAP = 4.0            # mm: the largest pore spacing the blue noise uses, above every region's own (orbital 2.9). (h3b-sculpt-6)
#                             params() fades the density towards the neck ring, so 1 / sqrt(density) grew to 31.6 mm there: one
#                             faded pore set the relax's neighbour radius for ALL of them (98 M pairs on the man, 12 GB) and
#                             shoved its real neighbours aside. Forge proof bq_M, 10-31


def params(V, n_head, grp, isl_of_v, neck_ring, sex):
    """per cage vertex (the LOW's ids) the T tier's amounts: (n, 11) float32 = pore density (per mm2), pore radius (mm),
    pore depth (mm), line depth (mm), lip-line weight (0..1), and (h3b-sculpt-4) the network's cell (mm; 0 where no
    network: the lips, the hidden islands, the body); (h3c-sculpt-8) 6 the lines' depth factor (FACE_LINE x SEX_LINE),
    7-9 the direction the lines run (the head's frame, unit, not yet on the surface: network() projects it; 0 where
    none), 10 the anisotropy's strength. grp: GNM's groups per cage vertex (head vertices; zero past them);
    isl_of_v: per vertex its LOW island's class ('face', 'scalp', 'ear', 'lid', 'mouth', 'nostril', 'neck', ... or '' on
    the body); neck_ring: its vertex ids"""
    n = len(V)
    out = np.zeros((n, 11), np.float32)
    dens = np.zeros(n)
    rad = np.zeros(n)
    cell = np.zeros(n)
    wsum = np.zeros(n)
    # (h3c-sculpt-8) the lines' factor, direction and strength, summed like the others and divided by the weight
    lfac = np.zeros(n)
    ldir = np.zeros((n, 3))
    lstr = np.zeros(n)
    c35, s35 = np.cos(np.radians(35.0)), np.sin(np.radians(35.0))
    sx = np.where(np.asarray(V)[:, 0] >= 0.0, 1.0, -1.0)

    def dir_of(kind):
        d = np.zeros((n, 3))
        if kind == 'h':
            d[:, 0] = 1.0
        elif kind == 'v':
            d[:, 1] = 1.0
        elif kind == 'cheek':
            d[:, 0] = sx * c35
            d[:, 1] = s35
        return d
    reg = dict(cheek=('left_cheek_region', 'right_cheek_region'), nose=('nose_region',),
               forehead=('forehead_region',), chin=('chin_region',), upper_lip=('upper_lip_region',),
               zygomatic=('left_zygomatic_region', 'right_zygomatic_region'),
               infraorbital=('left_infraorbital_region', 'right_infraorbital_region'),
               temple=('left_temple_region', 'right_temple_region'),
               brow=('left_brow_region', 'middle_brow_region', 'right_brow_region'),
               parotid=('left_parotid_region', 'right_parotid_region'),
               orbital=('left_orbital_region', 'right_orbital_region'))
    for k, groups in reg.items():
        m = np.zeros(n, bool)
        for g in groups:
            if g in grp:
                m |= grp[g][:n]
        d, r = PORE[k]
        dens[m] += d
        rad[m] += r
        cell[m] += CELL[k]
        wsum[m] += 1.0
        f, a, kind = FACE_LINE[k]
        lfac[m] += f
        lstr[m] += a
        ldir[m] += dir_of(kind)[m]
    cls = np.asarray(isl_of_v)
    for k in ('neck', 'scalp', 'ear'):
        m = (cls == k) & (wsum == 0)
        d, r = PORE[k]
        dens[m] = d
        rad[m] = r
        cell[m] = CELL[k]
        wsum[m] = 1.0
        f, a, kind = FACE_LINE[k]
        lfac[m] = f
        lstr[m] = a
        ldir[m] = dir_of(kind)[m]
    face_left = (cls == 'face') & (wsum == 0)            # face vertices outside every named region: the cheek's values
    dens[face_left] = PORE['cheek'][0]
    rad[face_left] = PORE['cheek'][1]
    cell[face_left] = CELL['cheek']
    wsum[face_left] = 1.0
    lfac[face_left] = FACE_LINE['cheek'][0]
    lstr[face_left] = FACE_LINE['cheek'][1]
    ldir[face_left] = dir_of(FACE_LINE['cheek'][2])[face_left]
    ok = wsum > 0
    dens[ok] /= wsum[ok]
    rad[ok] /= wsum[ok]
    cell[ok] /= wsum[ok]
    lfac[ok] /= wsum[ok]
    lstr[ok] /= wsum[ok]
    ln = np.linalg.norm(ldir, axis=1)
    ldir = np.where(ln[:, None] > 1e-6, ldir / np.maximum(ln, 1e-12)[:, None], 0.0)
    lstr = np.where(ln > 1e-6, lstr, 0.0)
    s = SEX_PORE[sex]
    out[:, 0] = dens * s / 100.0                          # per mm2
    out[:, 1] = rad * s
    out[:, 2] = np.where(ok, PORE_DEPTH, 0.0)
    out[:, 3] = np.where(ok, LINE['depth'], 0.0)
    out[:, 5] = np.where(ok, cell, 0.0)
    out[:, 6] = np.where(ok, lfac * SEX_LINE[sex], 0.0)
    out[:, 7:10] = ldir
    out[:, 10] = lstr
    lip = np.zeros(n, bool)
    for g in ('upper_lip', 'lower_lip'):
        if g in grp:
            lip |= grp[g][:n]
    out[lip, 0] = 0.0                                     # the vermilion has no pores; its own furrows instead
    out[lip, 3] *= 0.4
    out[lip, 4] = 1.0
    out[lip, 5] = 0.0                                     # nor the network (its lip lines run across it)
    hidden = np.isin(cls, ['lid', 'mouth', 'nostril'])
    out[hidden] = 0.0
    out[n_head:] = 0.0                                    # the BODY: the runtime's micro-normal (the R tier)
    # the fade above the neck ring
    if len(neck_ring):
        from scipy.spatial import cKDTree
        d, _ = cKDTree(V[np.asarray(neck_ring)]).query(V[:n_head])
        f = np.clip(d / NECK_FADE_MM, 0.0, 1.0)
        f = f * f * (3.0 - 2.0 * f)
        out[:n_head, :5] *= f[:, None].astype(np.float32)
    return out


def _relax(P, r, tm, fixed=None, r_fixed=None, iters=14, step=0.25, log=None, name='', reach=1.5):
    """blue noise by repulsion on a surface: each point pushed off its neighbours within `reach` x the pair's mean radius
    (a linear falloff), the move kept tangent and snapped back onto the surface (tm.closest: the LOW, flat per
    triangle); fixed points (and their radii) repel without moving. (h3c-sculpt-8) `reach` and `iters` set how regular the
    pattern ends: 1.5 x 14 (H3b's) a near-lattice, 0.6 x 6 a soft hard core (PORE_RELAX)"""
    from scipy.spatial import cKDTree
    P = P.copy()
    nP = len(P)
    if fixed is not None and len(fixed):
        Fx, rF = np.asarray(fixed, np.float64), np.asarray(r_fixed, np.float64)
    else:
        Fx, rF = np.zeros((0, 3)), np.zeros(0)
    for it in range(iters):
        A = np.vstack([P, Fx])
        rA = np.concatenate([r, rF])
        tree = cKDTree(A)
        pairs = tree.query_pairs(reach * float(rA.max()), output_type='ndarray')
        i, j = pairs[:, 0], pairs[:, 1]
        d = A[i] - A[j]
        L = np.linalg.norm(d, axis=1)
        R = reach * 0.5 * (rA[i] + rA[j])
        keep = (L < R) & (L > 1e-9)
        i, j, d, L, R = i[keep], j[keep], d[keep], L[keep], R[keep]
        f = ((R - L) / R)[:, None] * d / L[:, None]
        mv = np.zeros_like(A)
        np.add.at(mv, i, f)
        np.add.at(mv, j, -f)
        mv = mv[:nP] * (step * r)[:, None]
        p, _, _ = tm.closest(P + mv)
        P = p
        if log and it in (0, iters - 1):
            log(f'[sculpt]   {name} relax {it}: {len(i):,} close pairs, mean move {np.linalg.norm(mv, axis=1).mean():.3f} mm')
    return P


def primary_walks(Ph, Nh, i, j, cell, rng, pdir=None):
    """(h3b-sculpt-5) THE LONG PRIMARY LINES: walks on the furrow graph (nodes Ph, normals Nh, edges i, j; cell: per node
    the network's cell), one per (walk_spacing x cell)^2 of surface, each starting along one of the two diagonal directions
    (the up axis on the surface turned +-35 deg about the normal, 12 deg of jitter), keeping its heading, 3-8 mm x cell /
    0.45 long, ending where no edge continues within ~70 deg. Returns per edge True when a walk used it.
    (h3c-sculpt-8) pdir: per node the direction the region's lines run, on the surface (0 where none): a walk starting
    there sets out along it (12 deg of jitter, either way) instead of the diagonals; LINE['walk_mm'] sets the length"""
    adj = [[] for _ in range(len(Ph))]
    for k, (a, b) in enumerate(zip(i.tolist(), j.tolist())):
        adj[a].append((b, k))
        adj[b].append((a, k))
    major = np.zeros(len(i), bool)
    used = np.nonzero(np.array([len(a) > 0 for a in adj]))[0]
    a_per_node = cell[used] ** 2
    n_walks = int(a_per_node.sum() / (LINE['walk_spacing'] * float(np.median(cell[used]))) ** 2)
    up = np.array([0.0, 1.0, 0.0])
    for w, v in enumerate(rng.choice(used, size=n_walks, p=a_per_node / a_per_node.sum()).tolist()):
        nv = Nh[v]
        t1 = up - (nv @ up) * nv
        ln = float(np.linalg.norm(t1))
        t1 = t1 / ln if ln > 1e-6 else np.array([1.0, 0.0, 0.0])
        t2 = np.cross(nv, t1)
        ang = np.radians(35.0 if w % 2 else -35.0) + rng.normal(0.0, np.radians(12.0))
        if pdir is not None and float(np.linalg.norm(pdir[v])) > 0.5:
            t1 = pdir[v] - (nv @ pdir[v]) * nv
            t1 = t1 / max(float(np.linalg.norm(t1)), 1e-12)
            t2 = np.cross(nv, t1)
            ang = rng.normal(0.0, np.radians(12.0))
        head = np.cos(ang) * t1 + np.sin(ang) * t2
        if rng.random() < 0.5:
            head = -head
        left = float(rng.uniform(*LINE['walk_mm'])) * float(cell[v]) / 0.45
        prev = -1
        while left > 0.0:
            best, bk, bd = -1, -1, 0.35
            for o, k in adj[v]:
                if o == prev:
                    continue
                d = Ph[o] - Ph[v]
                c = float((d @ head) / max(float(np.linalg.norm(d)), 1e-12))
                if c > bd:
                    best, bk, bd = o, k, c
            if best < 0:
                break
            major[bk] = True
            d = Ph[best] - Ph[v]
            L = float(np.linalg.norm(d))
            left -= L
            head = 0.7 * head + 0.3 * d / max(L, 1e-12)
            head = head - (head @ Nh[best]) * Nh[best]
            head /= max(float(np.linalg.norm(head)), 1e-12)
            prev, v = v, best
    return major


def network(Vl, Fl, par_l, tm_high, seed=11, log=print):
    """(h3b-sculpt-4) THE T TIER'S SITES on the head, as blue noise ON THE SURFACE: the PORES at their region's density
    (Flament's), then the NETWORK'S NODES at their region's cell (CELL), the pores fixed among them, each set relaxed by
    repulsion on the LOW (Vl mm, Fl its head triangles, par_l the per-vertex params of params()) and projected onto the
    high (tm_high: a human_ref.TriMesh of the level-4 head); the FURROWS the Gabriel graph of all nodes (a pair joins
    when no other node lies in the ball on its segment), a fifth of the edges not touching a pore dropped (broken lines),
    each furrow LINE['depth'] x 0.5-1.6 deep (the plan's 30-100 um; the ones into a pore x 1.15, the ones along the
    region's two diagonal directions deeper: the rhombic network of the photos), its half-width 0.045 mm + 0.4 x its
    depth. H3's pores (v3) were a 3-D jittered lattice read through the surface: pairs and bare gaps (forge looks,
    pores_v2_v3.png); its lines (15 um on a Worley lattice) did not read at macro scale (the H3 check's c10_macro).
    Returns dict(pore_P, pore_N, pore_r, pore_d, edge_A, edge_B, edge_d, edge_w (mm), stats)"""
    from scipy.spatial import cKDTree
    from . import human_ref as HR
    rng = np.random.default_rng(seed)
    Vl = np.asarray(Vl, np.float64)
    Fl = np.asarray(Fl, np.int64)
    tm_low = HR.TriMesh(Vl, Fl)
    A = 0.5 * np.linalg.norm(np.cross(Vl[Fl[:, 1]] - Vl[Fl[:, 0]], Vl[Fl[:, 2]] - Vl[Fl[:, 0]]), axis=1)
    pf = par_l[Fl].mean(1)                               # per triangle: the corners' mean params

    def sample(rate, n):
        """n points on the triangles, each triangle's share by area x rate, uniform inside"""
        w = A * rate
        f = rng.choice(len(Fl), size=n, p=w / w.sum())
        u = rng.random((n, 2))
        u = np.where(u.sum(1, keepdims=True) > 1.0, 1.0 - u, u)
        b = np.column_stack([1.0 - u.sum(1), u[:, 0], u[:, 1]])
        return np.einsum('nk,nkd->nd', b, Vl[Fl[f]])

    def at(P, col):
        """a param column interpolated at surface points (barycentric on the LOW)"""
        _, f, b = tm_low.closest(P)
        return np.einsum('nk,nk->n', b, par_l[Fl[np.maximum(f, 0)], col])

    def dir_at(P, N):
        """(h3c-sculpt-8) the lines' direction at surface points (columns 7-9 interpolated, put on the plane of the normals
        N, unit) and the anisotropy's strength (column 10); both 0 where the region has no direction"""
        _, f, b = tm_low.closest(P)
        cor = Fl[np.maximum(f, 0)]
        d = np.einsum('nk,nkd->nd', b, par_l[cor][:, :, 7:10])
        d = d - np.einsum('nd,nd->n', d, N)[:, None] * N
        ln = np.linalg.norm(d, axis=1)
        s = np.einsum('nk,nk->n', b, par_l[cor, 10])
        return np.where(ln[:, None] > 0.3, d / np.maximum(ln, 1e-12)[:, None], 0.0), np.where(ln > 0.3, s, 0.0)
    has_dirs = par_l.shape[1] > 10
    # ---- the pores
    dens = pf[:, 0]
    n_p = int(round(float((A * dens).sum())))
    stats = dict(area_mm2=float(A[pf[:, 5] > 0].sum()), pores=n_p)
    Pp = sample(dens, n_p) if n_p else np.zeros((0, 3))
    rp = np.minimum(1.0 / np.sqrt(np.maximum(at(Pp, 0), 1e-3)), PORE_R_CAP) if n_p else np.zeros(0)
    if n_p:
        Pp = _relax(Pp, rp, tm_low, log=log, name='pores', iters=PORE_RELAX['iters'], reach=PORE_RELAX['reach'])
    # ---- the network's nodes (the pores fixed among them)
    cell = pf[:, 5]
    rate = np.where(cell > 0, 1.0 / np.maximum(cell, 1e-3) ** 2, 0.0)
    n_n = max(int(round(float((A * rate).sum()))) - n_p, 0)
    Pn = sample(rate, n_n)
    rn = np.maximum(at(Pn, 5), 0.2)
    Pn = _relax(Pn, rn, tm_low, fixed=Pp, r_fixed=np.maximum(at(Pp, 5), 0.2) if n_p else None, log=log, name='nodes',
                iters=NODE_RELAX['iters'], reach=NODE_RELAX['reach'])
    # drop nodes that fall off the network's region (cell 0: the lips, the hidden islands) after the relax
    cn = at(Pn, 5)
    Pn = Pn[cn > 0.05]
    stats['nodes'] = int(len(Pn))
    # ---- onto the high
    Ph, fph, bph = tm_high.closest(np.vstack([Pp, Pn]))
    Nh = tm_high.normal_at(fph, bph)
    is_pore = np.zeros(len(Ph), bool)
    is_pore[:len(Pp)] = True
    c_all = np.maximum(at(Ph, 5), 0.2)
    # ---- the furrows: the Gabriel graph
    tree = cKDTree(Ph)
    pairs = tree.query_pairs(2.2 * float(c_all.max()), output_type='ndarray')
    i, j = pairs[:, 0], pairs[:, 1]
    L = np.linalg.norm(Ph[i] - Ph[j], axis=1)
    ok = L < 2.2 * 0.5 * (c_all[i] + c_all[j])
    i, j, L = i[ok], j[ok], L[ok]
    mid = 0.5 * (Ph[i] + Ph[j])
    inside = tree.query_ball_point(mid, 0.5 * L - 1e-6, return_length=True)
    g = inside == 0
    i, j, L = i[g], j[g], L[g]
    touch = is_pore[i] | is_pore[j]
    keep = touch | (rng.random(len(i)) > 0.2)
    i, j, L, touch = i[keep], j[keep], L[keep], touch[keep]
    # (h3b-sculpt-5) the hierarchy: the walks' furrows the primary lines, the others the secondary; x 1.15 into a pore
    # (h3c-sculpt-8) the walks set out along the region's direction where it has one
    pdir = dir_at(Ph, Nh)[0] if has_dirs else None
    major = primary_walks(Ph, Nh, i, j, c_all, rng, pdir=pdir)
    # (the depths stored UNFADED: the compose kernel scales the whole relief by the texel's own fade, the line depth
    # param over LINE['depth'], once; a furrow is dropped only where that fade is ~0)
    mid = 0.5 * (Ph[i] + Ph[j])
    ldep = at(mid, 3)
    r_d = rng.random(len(i))
    dep = LINE['depth'] * np.where(major, 1.0 + 0.5 * r_d, LINE['secondary'] * (0.5 + 0.8 * r_d)) * np.where(touch, 1.15, 1.0)
    wide = LINE['wide'] * np.where(major, 1.15, 0.65)
    if has_dirs:
        # (h3c-sculpt-8) the region's line factor, the anisotropy (an edge across the region's direction keeps 1 - strength
        # of its depth), and each valley as wide as its cell allows (H3b's 0.14 mm was set at 0.45 mm cells)
        Nm = Nh[i] + Nh[j]
        Nm = Nm / np.maximum(np.linalg.norm(Nm, axis=1, keepdims=True), 1e-12)
        dm, sm = dir_at(mid, Nm)
        e = (Ph[j] - Ph[i]) / np.maximum(np.linalg.norm(Ph[j] - Ph[i], axis=1, keepdims=True), 1e-12)
        al = np.abs(np.einsum('nd,nd->n', e, dm))
        dep = dep * np.maximum(at(mid, 6), 0.0) * (1.0 - sm * (1.0 - al * al))
        wide = wide * np.clip(0.5 * (c_all[i] + c_all[j]) / 0.45, 0.4, 1.0)
        stats['aligned_share'] = float((al > np.cos(np.radians(30.0)))[sm > 0.05].mean()) if (sm > 0.05).any() else 0.0
    good = ldep > 0.02 * LINE['depth']
    i, j, dep, wide, major = i[good], j[good], dep[good], wide[good], major[good]
    wid = 0.045 + 0.4 * dep
    # the pores' own params at their projected sites (params() fades its columns near the neck ring: un-faded here)
    f_site = np.clip(at(Ph[:len(Pp)], 3) / LINE['depth'], 0.05, 1.0) if len(Pp) else np.zeros(0)
    pr = at(Ph[:len(Pp)], 1) / f_site * (0.6 + 0.8 * rng.random(len(Pp)))
    pd = PORE_DEPTH * (0.8 + 0.4 * rng.random(len(Pp)))
    deg = np.bincount(np.concatenate([i, j]), minlength=len(Ph))
    stats.update(edges=int(len(i)), edge_len_mm=dict(p50=float(np.median(np.linalg.norm(Ph[i] - Ph[j], axis=1))),
                                                     max=float(np.linalg.norm(Ph[i] - Ph[j], axis=1).max())),
                 depth_um=dict(p10=float(np.percentile(dep, 10) * 1000), p50=float(np.median(dep) * 1000),
                               p90=float(np.percentile(dep, 90) * 1000)),
                 primary=dict(share=float(major.mean()), depth_um=[float(np.percentile(dep[major], 5) * 1000),
                                                                  float(np.percentile(dep[major], 95) * 1000)]),
                 secondary_depth_um=[float(np.percentile(dep[~major], 5) * 1000), float(np.percentile(dep[~major], 95) * 1000)],
                 node_degree=dict(mean=float(deg[deg > 0].mean()), pores=float(deg[:len(Pp)].mean()) if len(Pp) else 0))
    log(f'[sculpt] the network: {len(Pp):,} pores, {stats["nodes"]:,} nodes, {len(i):,} furrows on {stats["area_mm2"]:.0f} '
        f'mm2; primary {stats["primary"]["share"] * 100:.0f} % of them, {stats["primary"]["depth_um"][0]:.0f}-'
        f'{stats["primary"]["depth_um"][1]:.0f} um, secondary {stats["secondary_depth_um"][0]:.0f}-'
        f'{stats["secondary_depth_um"][1]:.0f} um (p5-p95); length p50 {stats["edge_len_mm"]["p50"]:.2f} mm, node degree '
        f'{stats["node_degree"]["mean"]:.2f} (at a pore {stats["node_degree"]["pores"]:.2f})')
    return dict(pore_P=Ph[:len(Pp)], pore_N=Nh[:len(Pp)], pore_r=pr, pore_d=pd, edge_A=Ph[i], edge_B=Ph[j],
                edge_d=dep, edge_w=wid, edge_wide=wide, edge_major=major, stats=stats)


# ---------------------------------------------------------------------------------------------------- the S tier
AGE_SIGNS = {
    # sign: (F onset, F span, M onset, M span, depth at full weight mm, width mm) [B §6.1: women's wrinkles after 50,
    # men's earlier and deeper; glabellar lines not before 40]; the onsets and depths [E]
    'forehead': (45.0, 30.0, 38.0, 30.0, 0.22, 0.9),
    'glabellar': (50.0, 25.0, 42.0, 25.0, 0.25, 0.8),
    'crows_feet': (42.0, 30.0, 36.0, 30.0, 0.15, 0.6),
    'under_eye': (40.0, 30.0, 36.0, 30.0, 0.12, 0.7),
    # (h3b-sculpt-4) the neck rings start at 33 (F) / 30 (M), so both baselines (30) carve none. H3's onset 20 put the
    # woman's two rings at 0.05 mm deep and ~0.9 mm wide, constant over 200 deg, and they read as two drawn lines in every
    # face and head-turn frame (the H3 check's c02). The photos decided (research/human_web/neck_photos/SOURCES.txt):
    # three young women's necks show no transverse line at all, only the SCM's relief; a woman in her forties shows
    # flexion folds and short fine crepe at the side, never long rings. KNOWN for H5's ages past ~40: these capsule runs
    # are narrow (R_MAX caps the capsule, so a groove cannot be wide and shallow) and constant along the arc; a real neck
    # line is a broad soft fold fading at the sides: it belongs in the T-tier compose as a wide profile, not a carve
    'neck_rings': (33.0, 40.0, 30.0, 40.0, 0.20, 1.0),
}


def age_weight(sign, age, sex):
    """0 before the sign's onset, rising smoothly to 1 over its span"""
    fo, fs, mo, ms, _, _ = AGE_SIGNS[sign]
    o, s = (fo, fs) if sex == 'F' else (mo, ms)
    t = float(np.clip((age - o) / s, 0.0, 1.0))
    return t * t * (3.0 - 2.0 * t)


R_MAX = 1.5                 # mm: the largest groove capsule. (h3 M's bake: a 6 um neck ring wants r = (w^2/4 + d^2) / 2d =
#                             13 mm, a capsule standing 13 mm out in front of the neck that reached up into the chin and
#                             carved it hollow: 3,258 + 3,553 sign flips, caught by the sign gate). Past R_MAX the groove
#                             is narrower than its width asks: 2 sqrt(2 R d - d^2)
D_MIN = 0.010               # mm: a groove shallower than this is not carved (invisible at the 0.095 mm texel)


def surface_run(P, N, depth, width):
    """a carve run along the surface points P (k, 3) with normals N: capsule-cones whose axis stands (r - depth) off
    the surface, r chosen so the groove is `width` wide at the surface and `depth` deep, at most R_MAX. Returns (A, B,
    ra, rb, k)"""
    r = min((0.25 * width * width + depth * depth) / (2.0 * depth), R_MAX)
    C = P + N * (r - depth)
    w_eff = 2.0 * np.sqrt(max(2.0 * r * depth - depth * depth, 0.0))
    return C[:-1], C[1:], np.full(len(C) - 1, r), np.full(len(C) - 1, r), 0.15 * w_eff


def neck_ring_strokes(Vh, Nh, neck_loop, jaw_y, weight, sex, n_lines=2, arc_deg=200.0, step=1.5):
    """the NECK RINGS: n_lines horizontal lines round the front of the neck, at fractions 0.40 and 0.65 of the way from
    the neck ring up to the jaw's lowest midline point (jaw_y), over arc_deg of the front, on the high (Vh, Nh: its
    limit points and normals, mm). Returns a list of (A, B, ra, rb, k) batches (mm)"""
    if weight <= 0.02:
        return []
    _, _, _, _, dmax, width = AGE_SIGNS['neck_rings']
    depth = dmax * weight * (1.0 if sex == 'F' else 0.8)
    if depth < D_MIN:
        return []
    ring = np.asarray(neck_loop)
    c = ring.mean(0)
    y0 = float(ring[:, 1].mean())
    R = float(np.linalg.norm((ring - c)[:, [0, 2]], axis=1).mean())
    out = []
    for frac in (0.40, 0.65)[:n_lines]:
        y = y0 + frac * (jaw_y - y0)
        # the high's points in a thin slab at that height, on the neck (within 1.6 R of its axis), facing outward
        d = Vh[:, [0, 2]] - c[[0, 2]]
        rr = np.linalg.norm(d, axis=1)
        sel = (np.abs(Vh[:, 1] - y) < 0.6) & (rr < 1.6 * R) & ((Nh[:, [0, 2]] * d).sum(1) > 0.3 * rr)
        if sel.sum() < 20:
            continue
        ang = np.degrees(np.arctan2(d[sel, 0], d[sel, 1]))               # 0 at the front (+z)
        inside = np.abs(ang) <= arc_deg / 2
        idx = np.nonzero(sel)[0][inside]
        ang = ang[inside]
        # one point per angular bin of ~step mm arc: the one nearest the slab's height
        nb = max(int(np.radians(arc_deg) * R / step), 4)
        b = np.clip(((ang + arc_deg / 2) / arc_deg * nb).astype(int), 0, nb - 1)
        pick = []
        for k in range(nb):
            m = b == k
            if m.any():
                j = idx[m][np.argmin(np.abs(Vh[idx[m], 1] - y))]
                pick.append(j)
        if len(pick) > 3:
            P, Nn = Vh[pick], Nh[pick]
            out.append(surface_run(P, Nn, depth, width * (0.8 + 0.4 * weight)))
    return out
