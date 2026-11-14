"""The human's T-TIER RELIEF (HUMAN_PLAN §5.1's relief tiers; human_sculpt.py's T tier): the device functions that
compose the pores, the primary lines and the lip lines per texel, as a solid function of the high's surface point in
millimetres. Moved here verbatim from work/bestiary/human/h3/h3_bake.py on 10-30 by the H3 integrator, so the bake's
compose kernel (h3_bake.k_compose) and the integrator's T-tier recompose on a finished run
(work/bestiary/human/h3/integrate/i00_tier.py) read ONE copy: a recomposed map cannot drift from the baked one.

    relief_grad(p_mm, n, dens, rad, pdep, ldep, lip, seed) -> vec4(h mm, the 3-D gradient)
    relief_v4(p_mm, n, fade, lip, seed, the network's hash grids and arrays) -> vec4(h mm, the 3-D gradient)

(h3b, the H3b forge builder, 10-30) relief_v4 reads THE NETWORK (human_sculpt.network: the pores and the furrows' nodes
as blue noise on the surface, the furrows the Gabriel graph of the nodes, so the lines meet at the pores) through two
Warp hash grids, the pores' centres and the furrows' midpoints: each pore a pit (bump profile) of its own radius and
depth on its tangent plane, each furrow a groove (bump profile across the segment) of its own depth and width; the
deepest term wins where they meet (so a junction is one pit, not a sum), the lip lines as v3. relief_grad (v3) stays
unchanged for H3's recompose (work/bestiary/human/h3/integrate/i00_tier.py).
(h3b-sculpt-5, the forge builder's successor) relief_v5 replaces v4 in the bake: v4's narrow grooves on flat plateaus read as
CRACKED TILE at macro (forge probe p03) where the photo shows pillowy plateaus between soft valleys (research/human_web/
skin_photos/human_skin_close_up.jpg; the sandbox p06 compared the profiles through a 0.09 mm texel and a scattered diffuse).
It returns the HEIGHT alone, and the compose takes the normal from finite differences of a 5 x 5 lattice across the texel,
which frees the height to be any function: each furrow a WIDE valley with a narrow crease at its floor, the sample point
warped by a smooth noise (the lines wander instead of running straight between their nodes), the depth wandering along a
line, and a CRUMPLE on the plateaus that fades into the valleys.
(h3c-sculpt-8, 11-01, the H4 round's close-up builder) A FACE'S LINES ARE STRAIGHT: the warp's peak a quarter of H3b's (the
lines wandered ~0.05 mm sd over a 0.6 mm lattice, which with the hand's depths read as crinkled leather at the macros; the
face photo's strokes run straight between their ends, h3b_photos/freckles_after_summertime.jpg), and the crumple 0.0025 mm
(at 0.006 it stood out of a face's 3-15 um lines as pebbling).
"""
import warp as wp

# (h3b-sculpt-5) [E] the look, fitted in the sandbox p06 beside the photo; each noise a value noise of the given lattice (mm)
WAVE_AMP = 0.035            # mm: the warp's peak; value noise's sd is ~0.18 of its range, so the lines wander ~0.013 mm sd
#                             (h3c-sculpt-8; H3b's 0.14: ~0.05 mm sd)
WAVE_LAT = 0.60             # mm
ALONG = 0.35                # the depth's relative sd along a line
ALONG_LAT = 0.90            # mm
CRUMPLE = 0.0025            # mm: the plateaus' crumple (0.010 until h3b-sculpt-7: with the lines shallower it read as pebbling;
#                             0.006 until h3c-sculpt-8, beside the face's 3-15 um lines)
CRUMPLE_LAT1 = 0.20         # mm: two octaves, the coarse one folded (|n|) so it reads as creases, not bumps
CRUMPLE_LAT2 = 0.10         # mm
MIX_WIDE = 0.65             # a furrow's profile: this share the wide valley, the rest its narrow crease
PORE_CORE = 0.45            # (h3b-sculpt-7) a pore is a FUNNEL: a soft dimple of its radius round a core of this share of it. A bump alone
PORE_CORE_MIX = 0.40        # has no centre, and through the skin's scattered diffuse only a centre reads as a dot; this share of the depth
PORE_DARK_MIN = 0.35        # (h3b-sculpt-7) the pores' own darkness (pore_dot): the palest pore's share of the darkest's, the photos' spread [E]


@wp.func
def hash3(i: int, j: int, k: int, s: int):
    h = wp.uint32(i * 73856093) ^ wp.uint32(j * 19349663) ^ wp.uint32(k * 83492791) ^ wp.uint32(s * 1597334677)
    h = h ^ (h >> wp.uint32(13))
    h = h * wp.uint32(1274126177)
    h = h ^ (h >> wp.uint32(16))
    return h


@wp.func
def u01(h: wp.uint32):
    return float(h & wp.uint32(16777215)) / 16777216.0


@wp.func
def jit(i: int, j: int, k: int, s: int):
    h1 = hash3(i, j, k, s)
    h2 = hash3(i, j, k, s + 17)
    h3 = hash3(i, j, k, s + 41)
    return wp.vec3(u01(h1), u01(h2), u01(h3))


@wp.func
def vnoise(p: wp.vec3, s: int):
    """value noise in 0..1 (trilinear over the integer lattice, smoothstepped)"""
    i0 = int(wp.floor(p[0]))
    j0 = int(wp.floor(p[1]))
    k0 = int(wp.floor(p[2]))
    fx = p[0] - float(i0)
    fy = p[1] - float(j0)
    fz = p[2] - float(k0)
    fx = fx * fx * (3.0 - 2.0 * fx)
    fy = fy * fy * (3.0 - 2.0 * fy)
    fz = fz * fz * (3.0 - 2.0 * fz)
    acc = float(0.0)
    for di in range(2):
        for dj in range(2):
            for dk in range(2):
                wx = fx
                if di == 0:
                    wx = 1.0 - fx
                wy = fy
                if dj == 0:
                    wy = 1.0 - fy
                wz = fz
                if dk == 0:
                    wz = 1.0 - fz
                acc = acc + wx * wy * wz * u01(hash3(i0 + di, j0 + dj, k0 + dk, s))
    return acc


@wp.func
def bump(x: float):
    """(1 - x^2)^2 on [0, 1)"""
    if x >= 1.0:
        return 0.0
    t = 1.0 - x * x
    return t * t


@wp.func
def dbump(x: float):
    if x >= 1.0:
        return 0.0
    return -4.0 * x * (1.0 - x * x)


@wp.func
def relief_grad(p: wp.vec3, n: wp.vec3, dens: float, rad: float, pdep: float, ldep: float, lip: float, seed: int):
    """the T tier's height (mm, negative into the skin) and its 3-D gradient at p (mm; n the surface's unit normal
    there): pores (v3, below), the primary lines (soft broken grooves on the cell walls of a 0.5 mm jittered lattice: the
    Worley distance F2 - F1), the lip lines (furrows along x with a wobble). Returns vec4(h, gx, gy, gz)
    PORES v3 (the forge builder's successor, 10-30): v2's pores were SPHERES on a 3-D jittered lattice whose cell
    (2 rad / dens)^(1/3), ~1.1 mm, let the surface see only the seeds within a slab a third of a cell thick: a thinned
    lattice, nearly Poisson, so the cheek's pores clumped in twos and threes with bare gaps, and each one's size shrank
    with its seed's distance off the surface (look_F_cheek_on, F4). Now each pore is a COLUMN along the normal: its
    profile reads the TANGENTIAL distance to its seed, and a seed counts while it lies within half a cell along n (full
    to 0.3 c, gone at 0.5 c), ~0.8 seeds per lattice column: a jittered grid on the surface, every pore its own size
    (the 0.6-1.4 jitter, the sizes' spread [B §6.1]). The cell c = sqrt(0.8 / dens) keeps `dens` visible pores per mm2."""
    h = float(0.0)
    g = wp.vec3(0.0)
    if dens > 1.0e-4 and pdep > 0.0 and rad > 0.0:
        c = wp.sqrt(0.8 / dens)
        q = p / c
        i0 = int(wp.floor(q[0]))
        j0 = int(wp.floor(q[1]))
        k0 = int(wp.floor(q[2]))
        for di in range(-1, 2):
            for dj in range(-1, 2):
                for dk in range(-1, 2):
                    ii = i0 + di
                    jj = j0 + dj
                    kk = k0 + dk
                    ctr = (wp.vec3(float(ii), float(jj), float(kk)) + jit(ii, jj, kk, seed)) * c
                    d = p - ctr
                    dn = wp.dot(d, n)
                    adn = wp.abs(dn)
                    if adn < 0.5 * c:
                        dt = d - n * dn
                        rt = wp.length(dt)
                        rr = rad * (0.6 + 0.8 * u01(hash3(ii, jj, kk, seed + 5)))  # a size jitter per pore (0.6-1.4)
                        if rt < rr:
                            sv = wp.clamp((adn - 0.3 * c) / (0.2 * c), 0.0, 1.0)
                            vw = 1.0 - sv * sv * (3.0 - 2.0 * sv)
                            h = h - pdep * vw * bump(rt / rr)
                            if rt > 1.0e-9:
                                g = g - pdep * vw * dbump(rt / rr) / rr * (dt / rt)
    if ldep > 0.0:
        # (v2, after the first full look: uniform 0.85 mm Voronoi cells with a 40 um groove on EVERY wall read as cracked
        # paint at close range) a finer 0.5 mm network of SOFT, BROKEN furrows: each cell wall carries a groove with a
        # random weight (two in five none, the rest 0.3-1), the depth wandering slowly (value noise over 3 mm, 0.4-1)
        cl = 0.5
        w = 0.06
        q = p / cl
        i0 = int(wp.floor(q[0]))
        j0 = int(wp.floor(q[1]))
        k0 = int(wp.floor(q[2]))
        d1 = float(1.0e9)
        d2 = float(1.0e9)
        v1 = wp.vec3(0.0)
        v2 = wp.vec3(0.0)
        h1 = wp.uint32(0)
        h2 = wp.uint32(0)
        for di in range(-1, 2):
            for dj in range(-1, 2):
                for dk in range(-1, 2):
                    ii = i0 + di
                    jj = j0 + dj
                    kk = k0 + dk
                    ctr = (wp.vec3(float(ii), float(jj), float(kk)) + jit(ii, jj, kk, seed + 101)) * cl
                    d = p - ctr
                    r = wp.length(d)
                    hc = hash3(ii, jj, kk, seed + 211)
                    if r < d1:
                        d2 = d1
                        v2 = v1
                        h2 = h1
                        d1 = r
                        v1 = d
                        h1 = hc
                    elif r < d2:
                        d2 = r
                        v2 = d
                        h2 = hc
        e = 0.5 * (d2 - d1)
        if e < w and d1 > 1.0e-9 and d2 > 1.0e-9:
            ew = u01((h1 ^ h2) * wp.uint32(507952121))
            ewt = float(0.0)
            if ew > 0.4:
                ewt = 0.3 + 0.7 * (ew - 0.4) / 0.6
            wander = 0.4 + 0.6 * vnoise(p / 3.0, seed + 307)
            dep = ldep * ewt * wander
            if dep > 0.0:
                h = h - dep * bump(e / w)
                ge = 0.5 * (v2 / d2 - v1 / d1)
                g = g - dep * dbump(e / w) / w * ge
    if lip > 0.0:
        sp = 0.75
        wl = 0.11
        wob = 0.18 * wp.sin(1.3 * p[1] + 0.7 * p[2])
        s = (p[0] + wob) / sp
        k = wp.floor(s + 0.5)
        dx = (s - k) * sp
        jt = (u01(hash3(int(k), 3, 7, seed + 7)) - 0.5) * 0.3 * sp
        dd = dx - jt
        ad = wp.abs(dd)
        dep = 0.045 * lip * (0.6 + 0.8 * u01(hash3(int(k), 5, 9, seed + 9)))
        if ad < wl:
            h = h - dep * bump(ad / wl)
            sg = float(1.0)
            if dd < 0.0:
                sg = -1.0
            gx = -dep * dbump(ad / wl) / wl * sg
            dwob_y = 0.18 * 1.3 * wp.cos(1.3 * p[1] + 0.7 * p[2])
            dwob_z = 0.18 * 0.7 * wp.cos(1.3 * p[1] + 0.7 * p[2])
            g = g + wp.vec3(gx, gx * dwob_y, gx * dwob_z)
    return wp.vec4(h, g[0], g[1], g[2])


@wp.func
def lip_lines(p: wp.vec3, lip: float, seed: int):
    """v3's lip lines alone (furrows along x with a wobble): vec4(h, gradient)"""
    h = float(0.0)
    g = wp.vec3(0.0)
    if lip > 0.0:
        sp = 0.75
        wl = 0.11
        wob = 0.18 * wp.sin(1.3 * p[1] + 0.7 * p[2])
        s = (p[0] + wob) / sp
        k = wp.floor(s + 0.5)
        dx = (s - k) * sp
        jt = (u01(hash3(int(k), 3, 7, seed + 7)) - 0.5) * 0.3 * sp
        dd = dx - jt
        ad = wp.abs(dd)
        dep = 0.045 * lip * (0.6 + 0.8 * u01(hash3(int(k), 5, 9, seed + 9)))
        if ad < wl:
            h = -dep * bump(ad / wl)
            sg = float(1.0)
            if dd < 0.0:
                sg = -1.0
            gx = -dep * dbump(ad / wl) / wl * sg
            dwob_y = 0.18 * 1.3 * wp.cos(1.3 * p[1] + 0.7 * p[2])
            dwob_z = 0.18 * 0.7 * wp.cos(1.3 * p[1] + 0.7 * p[2])
            g = wp.vec3(gx, gx * dwob_y, gx * dwob_z)
    return wp.vec4(h, g[0], g[1], g[2])


@wp.func
def relief_v4(p: wp.vec3, n: wp.vec3, fade: float, lip: float, seed: int, pgrid: wp.uint64,
              ppos: wp.array(dtype=wp.vec3), prad: wp.array(dtype=float), pdep: wp.array(dtype=float), pq: float,
              egrid: wp.uint64, ea: wp.array(dtype=wp.vec3), eb: wp.array(dtype=wp.vec3),
              edep: wp.array(dtype=float), ewid: wp.array(dtype=float), eq: float):
    """THE NETWORK at p (mm; n the surface's unit normal there; fade 0..1 the T tier's amount there: the neck's fade,
    the lips' none): the deepest of the pores' pits and the furrows' grooves, then the lip lines added. pq / eq: the
    two grids' query radii (the largest pore radius; the largest half-furrow plus its width). Returns vec4(h, grad)"""
    hm = float(0.0)
    gm = wp.vec3(0.0)
    if fade > 1.0e-3:
        idx = int(0)
        q = wp.hash_grid_query(pgrid, p, pq)
        while wp.hash_grid_query_next(q, idx):
            d = p - ppos[idx]
            dn = wp.dot(d, n)
            if wp.abs(dn) < 0.6:
                dt = d - n * dn
                rt = wp.length(dt)
                rr = prad[idx]
                if rt < rr:
                    hh = -pdep[idx] * fade * bump(rt / rr)
                    if hh < hm:
                        hm = hh
                        gm = wp.vec3(0.0)
                        if rt > 1.0e-9:
                            gm = -pdep[idx] * fade * dbump(rt / rr) / rr * (dt / rt)
        q2 = wp.hash_grid_query(egrid, p, eq)
        while wp.hash_grid_query_next(q2, idx):
            a = ea[idx]
            ab = eb[idx] - a
            t = wp.clamp(wp.dot(p - a, ab) / wp.max(wp.dot(ab, ab), 1.0e-12), 0.0, 1.0)
            d = p - (a + ab * t)
            dn = wp.dot(d, n)
            if wp.abs(dn) < 0.6:
                dt = d - n * dn
                r = wp.length(dt)
                w = ewid[idx]
                if r < w:
                    hh = -edep[idx] * fade * bump(r / w)
                    if hh < hm:
                        hm = hh
                        gm = wp.vec3(0.0)
                        if r > 1.0e-9:
                            gm = -edep[idx] * fade * dbump(r / w) / w * (dt / r)
    ll = lip_lines(p, lip, seed)
    return wp.vec4(hm + ll[0], gm[0] + ll[1], gm[1] + ll[2], gm[2] + ll[3])


@wp.func
def pore_dot(p: wp.vec3, n: wp.vec3, fade: float, seed: int, pore_ref: float, pgrid: wp.uint64, ppos: wp.array(dtype=wp.vec3),
             prad: wp.array(dtype=float), pdep: wp.array(dtype=float), pq: float):
    """(h3b-sculpt-7) THE PORE'S COLOUR at p, 0..1: the core of the pore here, each pore its own darkness (its depth's random part, pore_ref
    the depth it was scaled from: human_sculpt.network's pore_d = PORE_DEPTH x (0.8 + 0.4 r)). Under the skin's scattered diffuse a pit
    cannot shade itself, so the photos' dark dots are colour. Pores only: the height can't carry this (a deep stretch of a furrow is as
    deep as a pore, and darkened it reads as a stray hair). The same warped point as relief_v5, so the dot sits in its pit"""
    if fade <= 1.0e-3:
        return 0.0
    q0 = p * (1.0 / WAVE_LAT)
    pw = p + wp.vec3(vnoise(q0, seed + 401) - 0.5, vnoise(q0, seed + 402) - 0.5, vnoise(q0, seed + 403) - 0.5) * (2.0 * WAVE_AMP)
    best = float(0.0)
    idx = int(0)
    q = wp.hash_grid_query(pgrid, pw, pq)
    while wp.hash_grid_query_next(q, idx):
        d = pw - ppos[idx]
        dn = wp.dot(d, n)
        if wp.abs(dn) < 0.6:
            rt = wp.length(d - n * dn)
            rc = PORE_CORE * prad[idx]
            if rt < rc:
                u = wp.clamp((pdep[idx] / pore_ref - 0.8) / 0.4, 0.0, 1.0)
                v = bump(rt / rc) * (PORE_DARK_MIN + (1.0 - PORE_DARK_MIN) * u * u)
                if v > best:
                    best = v
    return best * fade


@wp.func
def relief_v5(p: wp.vec3, n: wp.vec3, fade: float, lip: float, seed: int, line_ref: float, pgrid: wp.uint64,
              ppos: wp.array(dtype=wp.vec3), prad: wp.array(dtype=float), pdep: wp.array(dtype=float), pq: float,
              egrid: wp.uint64, ea: wp.array(dtype=wp.vec3), eb: wp.array(dtype=wp.vec3),
              edep: wp.array(dtype=float), ewid: wp.array(dtype=float), ewide: wp.array(dtype=float), eq: float):
    """THE T TIER'S HEIGHT at p (mm, negative into the skin; the module's docstring has the design): the deepest of the
    pores' pits and the furrows' valleys at the warped point, the crumple on the plateaus, the lip lines added"""
    hm = float(0.0)
    if fade > 1.0e-3:
        q0 = p * (1.0 / WAVE_LAT)
        pw = p + wp.vec3(vnoise(q0, seed + 401) - 0.5, vnoise(q0, seed + 402) - 0.5, vnoise(q0, seed + 403) - 0.5) * \
            (2.0 * WAVE_AMP)
        al = 1.0 + ALONG * (vnoise(p * (1.0 / ALONG_LAT), seed + 411) - 0.5) / 0.18
        al = wp.clamp(al, 0.25, 2.0)
        idx = int(0)
        q = wp.hash_grid_query(pgrid, pw, pq)
        while wp.hash_grid_query_next(q, idx):
            d = pw - ppos[idx]
            dn = wp.dot(d, n)
            if wp.abs(dn) < 0.6:
                rt = wp.length(d - n * dn)
                rr = prad[idx]
                if rt < rr:
                    hh = pdep[idx] * ((1.0 - PORE_CORE_MIX) * bump(rt / rr) + PORE_CORE_MIX * bump(rt / (PORE_CORE * rr)))
                    if hh > hm:
                        hm = hh
        q2 = wp.hash_grid_query(egrid, pw, eq)
        while wp.hash_grid_query_next(q2, idx):
            a = ea[idx]
            ab = eb[idx] - a
            t = wp.clamp(wp.dot(pw - a, ab) / wp.max(wp.dot(ab, ab), 1.0e-12), 0.0, 1.0)
            d = pw - (a + ab * t)
            dn = wp.dot(d, n)
            if wp.abs(dn) < 0.6:
                r = wp.length(d - n * dn)
                wd = ewide[idx]
                if r < wd:
                    hh = edep[idx] * al * (MIX_WIDE * bump(r / wd) + (1.0 - MIX_WIDE) * bump(r / ewid[idx]))
                    if hh > hm:
                        hm = hh
        n1 = wp.abs(vnoise(p * (1.0 / CRUMPLE_LAT1), seed + 421) - 0.5) / 0.18
        n2 = (vnoise(p * (1.0 / CRUMPLE_LAT2), seed + 422) - 0.5) / 0.18
        plateau = wp.clamp(1.0 - hm / (0.5 * line_ref), 0.0, 1.0)
        hm = hm - CRUMPLE * (0.7 * n1 + 0.3 * n2) * plateau
    return -hm * fade + lip_lines(p, lip, seed)[0]
